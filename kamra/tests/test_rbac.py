"""Roles and access on Frappe's own permission system.

Every staff action is `@require_perm(doctype, ptype)`: a Permission Type
on the record it touches, granted by DocPerm and changed per site in
Role Permission Manager (Custom DocPerm). These tests pin:

- zero behaviour change: with no site edits, each endpoint lets in
  exactly the roles its old @require_roles list did (rbac_baseline.json,
  captured from develop before the switch);
- Role Permission Manager edits take effect on the endpoint, the MCP tool
  list and the copilot;
- the hard rules hold whatever is configured: property scope, IT-only
  actions, an AI agent never overriding money;
- a site that already customised a doctype gets new Permission Types too.
"""

import ast
import importlib
import json
import os
import pkgutil

import frappe
from frappe.permissions import add_permission, update_permission_property
from frappe.tests import IntegrationTestCase

from kamra import authz

ROLE = "TEST RBAC Concierge"
CUSTOM_USER = "rbac.concierge@test.local"
DESK_USER = "rbac.desk@test.local"
AGENT_USER = "rbac.agent@test.local"
HOME = "TEST RBAC Home"
OTHER = "TEST RBAC Other"
# low-traffic actions, so a shared test site isn't disturbed for long
SOP = ("SOP Template", "read_sops")
TICKETS = ("Service Ticket", "handle_requests")

BASELINE = json.load(open(os.path.join(os.path.dirname(__file__), "rbac_baseline.json")))
BUILTIN = ("Front Desk", "Finance", "Revenue Manager", "Night Auditor", "Housekeeping",
           "Housekeeping Supervisor", "F&B Manager", "Kamra Agent", "POS Integrator",
           "Hotel Admin", "System Manager")
_SKIP = ("kamra.tests", "kamra.patches", "kamra.scripts", "kamra.kamra", "kamra.www",
         "kamra.templates", "kamra.public", "kamra.translations")


def _endpoint(dotted: str):
	module, name = dotted.rsplit(".", 1)
	return getattr(importlib.import_module("kamra." + module), name)


def _user(email: str, *roles: str) -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc({
			"doctype": "User", "email": email, "first_name": email.split("@")[0],
			"enabled": 1, "user_type": "System User", "send_welcome_email": 0,
			"roles": [{"role": r} for r in roles],
		}).insert(ignore_permissions=True)
	frappe.clear_cache(user=email)
	return email


def _property(name: str) -> str:
	if not frappe.db.exists("Property", name):
		frappe.get_doc({"doctype": "Property", "property_name": name}).insert(
			ignore_permissions=True)
	return name


def _grant(doctype: str, ptype: str, role: str = ROLE):
	"""What ticking a box in Role Permission Manager does."""
	if frappe.db.get_value("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}):
		update_permission_property(doctype, role, 0, ptype, 1)
	else:
		add_permission(doctype, role, 0, ptype)
	frappe.clear_cache(doctype=doctype)


def _revoke(doctype: str, ptype: str, role: str):
	update_permission_property(doctype, role, 0, ptype, 0)
	frappe.clear_cache(doctype=doctype)


class RbacTestCase(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture setup
		if not frappe.db.exists("Role", ROLE):
			frappe.get_doc({"doctype": "Role", "role_name": ROLE, "desk_access": 1}).insert(
				ignore_permissions=True)
		_user(CUSTOM_USER, ROLE)
		_user(DESK_USER, "Front Desk")
		_user(AGENT_USER, "Kamra Agent", ROLE)
		self.touched = set()

	def tearDown(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture teardown
		frappe.flags.kamra_agent_call = None
		frappe.db.rollback()
		for dt in (SOP[0], TICKETS[0], "Corporate Account", "Folio", "Property"):
			frappe.clear_cache(doctype=dt)
		for u in (CUSTOM_USER, DESK_USER, AGENT_USER):
			frappe.clear_cache(user=u)

	def as_user(self, user: str):
		frappe.set_user(user)  # nosemgrep: frappe-setuser -- the role under test

	# --- zero behaviour change ------------------------------------------------

	def test_defaults_match_the_old_role_lists(self):
		self.assertGreater(len(BASELINE), 400)
		for dotted, roles in BASELINE.items():
			fn = _endpoint(dotted)
			self.assertTrue(getattr(fn, "_kamra_perm", None), f"{dotted} has no require_perm")
			got = set(fn._kamra_roles)
			for role in BUILTIN:
				self.assertEqual(role in got, role in roles,
				                 f"{dotted}: {role} {'gained' if role in got else 'lost'} access")
			# nobody beyond the old list: no Guest / All / Desk User grant
			self.assertEqual(got, set(roles), dotted)

	def test_each_builtin_role_passes_the_real_check_as_before(self):
		"""_kamra_roles reads the DocPerm rows; the gate is frappe.has_permission
		(if_owner, select-only rows...). Both must agree with the old lists."""
		users = {r: _user(f"rbac.{r.lower().replace(' ', '')}@test.local", r) for r in BUILTIN}
		for dotted, roles in BASELINE.items():
			perm = _endpoint(dotted)._kamra_perm
			for role, user in users.items():
				self.assertEqual(frappe.has_permission(*perm, user=user, ignore_share_permissions=True),
				                 role in roles, f"{dotted}: {role}")

	def test_a_real_user_passes_the_same_gate(self):
		from kamra import api
		self.as_user(DESK_USER)
		self.assertTrue(frappe.has_permission(*api.check_in._kamra_perm))
		self.assertFalse(frappe.has_permission(*api.set_room_rate._kamra_perm))
		with self.assertRaises(frappe.PermissionError) as e:
			api.set_room_rate(property=HOME, room_type="x", rate=1)
		self.assertIn("Revenue Manager", str(e.exception))

	def test_no_endpoint_uses_a_fixed_role_list(self):
		"""require_roles is legacy (a hotel can't change it): every endpoint
		in Kamra uses require_perm, and every gated one is introspectable."""
		import kamra
		root = os.path.dirname(kamra.__file__)
		for mod in pkgutil.walk_packages(kamra.__path__, "kamra."):
			if mod.name.startswith(_SKIP) or mod.ispkg:
				continue
			path = os.path.join(root, *mod.name.split(".")[1:]) + ".py"
			tree = ast.parse(open(path).read())
			for node in ast.walk(tree):
				if isinstance(node, ast.FunctionDef):
					for dec in node.decorator_list:
						name = getattr(getattr(dec, "func", None), "id", None)
						self.assertNotEqual(name, "require_roles",
						                    f"{mod.name}.{node.name} still uses require_roles")

	# --- Role Permission Manager drives it ---------------------------------------

	def test_granting_in_role_permission_manager_lets_a_custom_role_in(self):
		from kamra import sop
		self.as_user(CUSTOM_USER)
		with self.assertRaises(frappe.PermissionError):
			sop.list_sops(property=_property(HOME))
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- admin edits permissions
		_grant(*SOP)
		self.as_user(CUSTOM_USER)
		sop.list_sops(property=HOME)  # no PermissionError

	def test_revoking_refuses_a_builtin_role(self):
		from kamra import sop
		_revoke(*SOP, "Front Desk")
		self.as_user(DESK_USER)
		with self.assertRaises(frappe.PermissionError) as e:
			sop.list_sops(property=_property(HOME))
		self.assertIn("Kamra Agent", str(e.exception))
		self.assertNotIn("Front Desk", sop.list_sops._kamra_roles)
		self.assertIn("Hotel Admin", sop.list_sops._kamra_roles)

	def test_sharing_a_record_does_not_unlock_an_action(self):
		self.as_user(CUSTOM_USER)
		self.assertFalse(frappe.has_permission(*SOP))
		from kamra.sop import list_sops
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- admin shares a record
		name = frappe.db.get_value("SOP Template", {})
		if name:
			frappe.share.add("SOP Template", name, CUSTOM_USER, read=1)
			self.as_user(CUSTOM_USER)
			with self.assertRaises(frappe.PermissionError):
				list_sops(property=_property(HOME))

	def test_mcp_and_copilot_follow_the_permissions(self):
		from kamra import assistant
		from kamra.mcp_tools import TOOLS, allowed_tools, resolve_endpoint, tool_allowed
		ungated = {s.name for s in TOOLS
		           if not getattr(resolve_endpoint(s.dotted), "_kamra_perm", None)}
		self.assertEqual({s.name for s in allowed_tools(roles={ROLE})}, ungated)
		_grant(*TICKETS)
		want = {s.name for s in TOOLS
		        if getattr(resolve_endpoint(s.dotted), "_kamra_perm", None) == TICKETS}
		self.assertTrue(want)
		self.assertEqual({s.name for s in allowed_tools(roles={ROLE})} - ungated, want)
		self.as_user(CUSTOM_USER)
		self.assertEqual({s.name for s in TOOLS if tool_allowed(s)} - ungated, want)
		perms = {getattr(assistant._resolve(assistant.TOOLS[n][0]), "_kamra_perm", None)
		         for n in assistant.TOOLS if assistant._tool_allowed(n)}
		self.assertEqual(perms - {None}, {TICKETS})

	# --- hard rules ---------------------------------------------------------------

	def test_property_scope_still_applies(self):
		from kamra import api
		_property(HOME)
		_property(OTHER)
		frappe.get_doc({"doctype": "User Permission", "user": CUSTOM_USER,
		                "allow": "Property", "for_value": HOME}).insert(ignore_permissions=True)
		frappe.clear_cache(user=CUSTOM_USER)
		_grant(*TICKETS)
		self.as_user(CUSTOM_USER)
		api.tickets_list(property=HOME)
		with self.assertRaises(frappe.PermissionError):
			api.tickets_list(property=OTHER)

	def test_agent_money_refusals_ignore_permissions(self):
		from kamra import credit, pos
		_grant("Corporate Account", "override_credit")
		_grant("Folio", "approve")
		self.as_user(AGENT_USER)
		self.assertFalse(credit.can_override())
		self.assertFalse(authz.is_supervisor())
		self.assertTrue(pos._agent_call())
		frappe.flags.kamra_agent_call = "MCP"
		self.assertFalse(credit.can_override())

	# --- approvals are permissions too ---------------------------------------------

	def test_approvers_are_chosen_in_role_permission_manager(self):
		from kamra import credit
		self.assertEqual(set(authz.supervisor_roles()), {"Hotel Admin", "Finance", "System Manager"})
		self.as_user(CUSTOM_USER)
		self.assertFalse(authz.is_supervisor())
		self.assertFalse(credit.can_override())
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- admin edits permissions
		_grant("Folio", "approve")
		_grant("Corporate Account", "override_credit")
		self.as_user(CUSTOM_USER)
		self.assertTrue(authz.is_supervisor())
		self.assertTrue(credit.can_override())
		self.assertIn(ROLE, authz.supervisor_roles())
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- admin edits permissions
		_revoke("Folio", "approve", "Finance")
		self.assertFalse(authz.is_supervisor(_user("rbac.fin@test.local", "Finance")))

	# --- roles, profiles and what the SPA is told ----------------------------------

	def test_role_profiles_ship_as_job_bundles(self):
		from kamra.install import ROLE_PROFILES, ensure_role_profiles
		for name in ROLE_PROFILES:  # a rolled-back earlier run leaves its lock
			stale = frappe.new_doc("Role Profile")
			stale.name = name
			stale.unlock()
			# ship today's contents, not an earlier run's (rolled back on tearDown)
			frappe.db.delete("Has Role", {"parent": name, "parenttype": "Role Profile"})
			frappe.db.delete("Role Profile", name)
		# run the user resync inline, as it does during install / migrate
		frappe.flags.in_install = True
		try:
			ensure_role_profiles()
		finally:
			frappe.flags.in_install = False
		for name, roles in ROLE_PROFILES.items():
			got = {r.role for r in frappe.get_doc("Role Profile", name).roles}
			self.assertTrue(set(roles) <= got, name)
		self.assertIn("Finance", ROLE_PROFILES["General Manager"])
		fnb = _user("rbac.fnb@test.local", *ROLE_PROFILES["F&B Manager"])
		for doctype, ptype in (("POS Order", "take_orders"),  # charge to room
		                       ("POS Order", "approve_voids"),
		                       ("Ingredient", "manage_stock"),  # wastage, counts, goods-in
		                       ("Menu Item", "edit_menu"),
		                       ("Kitchen Printer", "configure_printers")):
			self.assertTrue(frappe.has_permission(doctype, ptype, user=fnb), (doctype, ptype))
		self.assertIn("take_orders", _endpoint("pos.charge_to_room")._kamra_perm)
		# a POS void approver, never a folio one
		self.assertTrue(authz.is_supervisor(fnb, authz.POS_APPROVE))
		self.assertFalse(authz.is_supervisor(fnb))

	def test_only_it_edits_what_a_role_allows(self):
		"""Hotel Admin assigns people to roles; what a role may do is IT's
		(System Manager) call, in Role Permission Manager."""
		from frappe.core.page.permission_manager import permission_manager as rpm
		self.as_user(_user("rbac.gm@test.local", "Hotel Admin"))
		for doctype in ("DocPerm", "Custom DocPerm"):
			for ptype in ("create", "write", "delete"):
				self.assertFalse(frappe.has_permission(doctype, ptype), (doctype, ptype))
		for call in (lambda: rpm.get_permissions("Folio"),
		             lambda: rpm.add("Folio", ROLE, 0),
		             lambda: rpm.update("Folio", "Front Desk", 0, "bill", 1),
		             lambda: rpm.reset("Folio")):
			with self.assertRaises(frappe.PermissionError):
				call()

	def test_a_desk_role_with_kamra_permissions_is_assignable(self):
		from kamra.staff import role_names, staff_roles
		self.assertNotIn(ROLE, role_names())
		_grant(*SOP)
		self.assertIn(ROLE, role_names())
		self.assertIn(ROLE, [r["role"] for r in staff_roles()])

	def test_whoami_tells_the_spa_what_the_user_can_do(self):
		from kamra import api
		self.as_user(DESK_USER)
		can = api.whoami()["can"]
		self.assertIn("app_front_desk", can["Property"])
		self.assertNotIn("app_revenue", can["Property"])
		self.assertIn("check_in_out", can["Reservation"])
		self.as_user(CUSTOM_USER)
		self.assertNotIn("Property", api.whoami()["can"])
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- admin edits permissions
		_grant("Property", "app_operations")
		self.as_user(CUSTOM_USER)
		apps = [p for p in api.whoami()["can"]["Property"] if p.startswith("app_")]
		self.assertEqual(apps, ["app_operations"])

	def test_it_only_actions_stay_it_only(self):
		from kamra import api
		self.assertFalse(getattr(api.generate_api_key, "_kamra_perm", None))
		_user("rbac.gm@test.local", "Hotel Admin")
		self.as_user("rbac.gm@test.local")
		with self.assertRaises(frappe.PermissionError):
			api.developer_info()

	# --- sites with their own Custom DocPerms ------------------------------------

	def test_new_permission_types_reach_customised_doctypes(self):
		from kamra.install import SYNCED_PTYPES, sync_permission_types
		dt, ptype = SOP
		name = f"sop_template_{ptype}"
		# the site customised SOP Template before this Permission Type shipped
		frappe.db.delete("Custom DocPerm", {"parent": dt})
		frappe.get_doc({"doctype": "Custom DocPerm", "parent": dt, "parenttype": "DocType",
		                "parentfield": "permissions", "role": "Front Desk", "permlevel": 0,
		                "read": 1}).insert(ignore_permissions=True)
		done = set(json.loads(frappe.db.get_default(SYNCED_PTYPES) or "[]")) - {name}
		frappe.db.set_default(SYNCED_PTYPES, json.dumps(sorted(done)))
		frappe.clear_cache(doctype=dt)
		self.assertEqual(authz.perm_roles(dt, ptype), {"Administrator"})
		sync_permission_types()
		self.assertEqual(authz.perm_roles(dt, ptype),
		                 {"Administrator", "Front Desk", "Kamra Agent", "Hotel Admin",
		                  "System Manager"})
		# once only: a later untick is the site's choice
		_revoke(dt, ptype, "Front Desk")
		sync_permission_types()
		frappe.clear_cache(doctype=dt)
		self.assertNotIn("Front Desk", authz.perm_roles(dt, ptype))

	# --- staff & access ---------------------------------------------------------

	def _save_staff(self, email, roles):
		from kamra.staff import save_staff
		return save_staff(property=_property(HOME), email=email, full_name="Rbac Person",
		                  roles=json.dumps(roles))

	def test_save_staff_removes_roles(self):
		target = _user("rbac.target@test.local", "Finance", "Front Desk")
		self.as_user(_user("rbac.gm@test.local", "Hotel Admin"))
		self._save_staff(target, ["Front Desk"])
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- read back the result
		self.assertNotIn("Finance", frappe.get_roles(target))
		self.assertIn("Front Desk", frappe.get_roles(target))

	def test_only_a_hotel_admin_sets_job_titles(self):
		from kamra.staff import save_staff
		target = _user("rbac.target@test.local", "Front Desk")
		_grant("Property", "configure")
		self.as_user(CUSTOM_USER)
		with self.assertRaises(frappe.PermissionError):
			save_staff(property=_property(HOME), email=target, full_name="Rbac Person",
			           roles=json.dumps(["Front Desk"]), job_title="Duty Manager")
		self.as_user(_user("rbac.gm@test.local", "Hotel Admin"))
		save_staff(property=HOME, email=target, full_name="Rbac Person",
		           roles=json.dumps(["Front Desk"]), job_title="Duty Manager")
		self.assertEqual(frappe.db.get_value("User", target, "kamra_job_title"), "Duty Manager")

	def test_property_configure_does_not_mint_hotel_admins(self):
		_grant("Property", "configure")
		self.as_user(CUSTOM_USER)
		with self.assertRaises(frappe.PermissionError):
			self._save_staff("rbac.sock@test.local", ["Hotel Admin"])
		self._save_staff("rbac.sock@test.local", [ROLE])  # its own role is fine

	def test_a_role_with_rights_outside_kamra_is_not_hotel_assignable(self):
		from kamra.staff import role_names
		_grant(*SOP)
		self.assertIn(ROLE, role_names())
		add_permission("ToDo", ROLE, 0, "read")
		self.assertNotIn(ROLE, role_names())

	def test_copilot_chats_stay_private_on_rest(self):
		frappe.get_doc({"doctype": "Copilot Conversation", "title": "GM only",
		                "property": _property(HOME)}).insert(ignore_permissions=True)
		self.as_user(DESK_USER)
		self.assertFalse(frappe.get_list("Copilot Conversation", filters={"title": "GM only"}))
