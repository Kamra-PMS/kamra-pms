import frappe

AGENT_EMAIL = "agent@kamra.local"
AGENT_ROLE = "Kamra Agent"


# business roles a hotel assigns to staff that no doctype perm creates
STAFF_ROLES = ("Housekeeping Supervisor", "Night Auditor",
               # service account of a third-party POS (kamra.pos_interface)
               "POS Integrator")


def after_install():
	set_site_home_and_favicon()
	ensure_agent_identity()
	ensure_staff_roles()
	ensure_mcp_roles()
	ensure_role_profiles()


def after_migrate():
	# heals sites that were installed before the agent identity existed here
	ensure_agent_identity()
	ensure_staff_roles()
	ensure_mcp_roles()
	sync_permission_types()
	ensure_role_profiles()


def ensure_mcp_roles():
	from kamra.mcp_access import ensure_roles

	ensure_roles()


def ensure_staff_roles():
	"""Roles only - their grants live on the endpoints (@require_roles)
	and in the doctype JSON, never in custom DocPerms (see below)."""
	for role in STAFF_ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({
				"doctype": "Role", "role_name": role, "desk_access": 0,
			}).insert(ignore_permissions=True)
	_mirror_custom_perms("Housekeeping", "Housekeeping Supervisor")


def _mirror_custom_perms(from_role: str, to_role: str):
	"""Where a site already carries Custom DocPerms for a doctype, those
	replace the standard perms from the JSON - so a role added to the JSON
	stays locked out there. Give the new role the same custom grants the
	role it extends has, once; an admin's later edits are left alone."""
	flags = ("read", "write", "create", "delete", "submit", "cancel",
	         "amend", "report", "export", "print", "email", "share",
	         "if_owner", "permlevel")
	for cp in frappe.get_all("Custom DocPerm", filters={"role": from_role},
	                         fields=["parent", *flags]):
		if frappe.db.exists("Custom DocPerm", {"parent": cp.parent,
		                                       "role": to_role,
		                                       "permlevel": cp.permlevel}):
			continue
		frappe.get_doc({"doctype": "Custom DocPerm", "parent": cp.parent,
		                "parenttype": "DocType", "parentfield": "permissions",
		                "role": to_role,
		                **{f: cp.get(f) for f in flags}}).insert(
			ignore_permissions=True)
		frappe.clear_cache(doctype=cp.parent)


def ensure_agent_identity():
	"""The governed writer for guest bookings, OTA webhooks and automations.

	Only the Role and the User - never a DocPerm. Kamra Agent's grants ship
	in the doctype JSON as standard perms. seed_rbac_v2.ensure_agent_user()
	writes custom DocPerms, and in Frappe ANY custom perm on a doctype
	replaces ALL its standard perms, so running that at install silently
	revoked every other role's access to Property. No API key either: the
	MCP server and the seed scripts mint their own when they need one.
	"""
	if not frappe.db.exists("Role", AGENT_ROLE):
		frappe.get_doc({
			"doctype": "Role", "role_name": AGENT_ROLE, "desk_access": 0,
		}).insert(ignore_permissions=True)

	if not frappe.db.exists("User", AGENT_EMAIL):
		user = frappe.get_doc({
			"doctype": "User",
			"email": AGENT_EMAIL,
			"first_name": "Kamra",
			"last_name": "Agent",
			"enabled": 1,
			"user_type": "System User",
			"send_welcome_email": 0,
			"roles": [{"role": AGENT_ROLE}],
		})
		user.flags.no_welcome_mail = True
		user.insert(ignore_permissions=True)
	else:
		user = frappe.get_doc("User", AGENT_EMAIL)
		dirty = False
		if not user.enabled:
			user.enabled = 1
			dirty = True
		if AGENT_ROLE not in {r.role for r in user.roles}:
			user.append("roles", {"role": AGENT_ROLE})
			dirty = True
		if dirty:
			user.save(ignore_permissions=True)


def set_site_home_and_favicon():
	"""A fresh site shows Frappe's favicon and Desk until Website Settings
	carries ours. Point home at /kamra (WordPress-style: product, not Desk).
	Never overrides a hotelier's custom favicon or home page."""
	ws = frappe.get_doc("Website Settings")
	changed = False
	if not ws.favicon:
		ws.favicon = "/assets/kamra/kamra-mark.svg"
		changed = True
	if (ws.home_page or "").strip() in ("", "login", "me", "index"):
		ws.home_page = "kamra"
		changed = True
	if changed:
		ws.flags.ignore_mandatory = True
		ws.save(ignore_permissions=True)


# Back-compat for patches that import the old name.
set_site_favicon = set_site_home_and_favicon


SYNCED_PTYPES = "kamra_synced_permission_types"


def sync_permission_types():
	"""Kamra's actions are Permission Types on its doctypes (require_perm),
	granted in the doctype JSON. But a site that has edited a doctype in
	Role Permission Manager has Custom DocPerms, which replace the JSON
	perms wholesale - a Permission Type shipped later would grant nobody
	there and the action would lock everyone but Administrator out. Copy
	each new Permission Type's standard grants into the Custom DocPerms,
	once per Permission Type; what the site changes afterwards is theirs."""
	import json

	done = set(json.loads(frappe.db.get_default(SYNCED_PTYPES) or "[]"))
	ours = set(frappe.get_all("DocType", filters={"module": "Kamra"}, pluck="name"))
	customised = set(frappe.get_all("Custom DocPerm", pluck="parent", distinct=True))
	changed = False
	for pt in frappe.get_all("Permission Type", fields=["name", "doc_type", "perm_type"]):
		if pt.name in done or pt.doc_type not in ours:
			continue
		if pt.doc_type in customised:
			for role in frappe.get_all("DocPerm", pluck="role", filters={
					"parent": pt.doc_type, "permlevel": 0, pt.perm_type: 1}):
				row = frappe.db.get_value("Custom DocPerm", {
					"parent": pt.doc_type, "role": role, "permlevel": 0, "if_owner": 0})
				if row:
					frappe.db.set_value("Custom DocPerm", row, pt.perm_type, 1)
				else:
					frappe.get_doc({
						"doctype": "Custom DocPerm", "parent": pt.doc_type,
						"parenttype": "DocType", "parentfield": "permissions",
						# Frappe wants one basic right per row: select only
						# lets the role pick the record in a link field
						"role": role, "permlevel": 0, "select": 1, pt.perm_type: 1,
					}).insert(ignore_permissions=True)
			changed = True
		done.add(pt.name)
	frappe.db.set_default(SYNCED_PTYPES, json.dumps(sorted(done)))
	if changed:
		frappe.clear_cache()


# Job bundles: a Role Profile on a user sets their roles in one pick (Desk:
# User > Role Profiles). Created once; the hotel edits them freely after.
ROLE_PROFILES = {
	"Receptionist": ("Front Desk",),
	"Front Office Manager": ("Front Desk", "Night Auditor", "Revenue Manager"),
	"Duty Manager": ("Front Desk", "Night Auditor", "Housekeeping Supervisor"),
	"Night Auditor": ("Night Auditor", "Front Desk"),
	"F&B Manager": ("Front Desk", "Finance"),
	"Finance Manager": ("Finance", "Night Auditor"),
	"General Manager": ("Hotel Admin",),
}


def ensure_role_profiles():
	for name, roles in ROLE_PROFILES.items():
		if frappe.db.exists("Role Profile", name):
			continue
		frappe.get_doc({
			"doctype": "Role Profile", "role_profile": name,
			"roles": [{"role": r} for r in roles],
		}).insert(ignore_permissions=True)
