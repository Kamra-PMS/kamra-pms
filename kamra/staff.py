"""Staff & access - who can sign in, with which roles, at which properties.

Replaces sending a GM to Frappe Desk's User list. The rules a hotel needs
and Desk doesn't know about:

- A Hotel Admin manages business roles only. System Manager (IT) is
  granted, removed and edited by IT alone.
- A Hotel Admin limited to some properties can only hand out access to
  those, and can't make anyone unrestricted.
- Nobody can lock themselves out: no self-deactivation, no dropping your
  own admin role.
- Only Kamra's roles are touched; anything else on the user stays.

Property access is Frappe User Permissions on Property - the same thing
`authz.restricted_properties` enforces on every endpoint.
"""

import json

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import validate_email_address

from kamra.authz import IT_ADMIN, require_roles, restricted_properties

ROLES = (
	("Hotel Admin", "Hotel Admin",
	 "Runs the property: every app, all settings, staff and access."),
	("Front Desk", "Front Desk",
	 "Bookings, check-in and out, guests, folios and the cashier till."),
	("Revenue Manager", "Revenue",
	 "Rates, seasons, guardrails, channels, the booking engine and banquet sales."),
	("Finance", "Finance",
	 "Billing, ledgers, night audit, exports, tax and cashier controls."),
	("Night Auditor", "Night Auditor",
	 "End of Day: arrivals, departures, cashier closure, room and tax posting, the audit pack."),
	("Housekeeping Supervisor", "Housekeeping Supervisor",
	 "The room board, inspections, task deadlines and laundry pricing."),
	("Housekeeping", "Housekeeping",
	 "Their own tasks, room status and lost & found - usually on the phone app."),
	("POS Integrator", "POS integration",
	 "A service account for a third-party POS: finds in-house rooms and posts room charges, nothing else."),
	("System Manager", "IT administrator",
	 "Site administration: developer keys, new properties, every setting."),
)
ROLE_NAMES = tuple(r for r, _l, _d in ROLES)
IT_ONLY = ("System Manager",)
NEVER_LISTED = ("Administrator", "Guest")


def _caller_is_it() -> bool:
	return bool(set(IT_ADMIN) & set(frappe.get_roles()))


def _visible_to(user_props: set | None, prop: str) -> bool:
	return user_props is None or prop in user_props


def _user_properties(user: str) -> list | None:
	rows = frappe.get_all("User Permission",
	                      filters={"user": user, "allow": "Property"},
	                      pluck="for_value")
	return sorted(rows) if rows else None


@frappe.whitelist()
@require_roles()
def staff_roles() -> list:
	"""The roles a person can hold, and whether the caller may hand each out."""
	it = _caller_is_it()
	return [{"role": r, "label": label, "description": desc,
	         "assignable": it or r not in IT_ONLY} for r, label, desc in ROLES]


@frappe.whitelist()
@require_roles()
def list_staff(property: str) -> list:
	"""Everyone with a Kamra role who can reach this property."""
	it = _caller_is_it()
	me = frappe.session.user
	holders = frappe.get_all("Has Role",
	                         filters={"role": ("in", ROLE_NAMES), "parenttype": "User"},
	                         fields=["parent", "role"])
	by_user: dict[str, list] = {}
	for h in holders:
		if h.parent not in NEVER_LISTED:
			by_user.setdefault(h.parent, []).append(h.role)
	if not by_user:
		return []
	users = frappe.get_all(
		"User",
		filters={"name": ("in", list(by_user)), "user_type": "System User"},
		fields=["name", "full_name", "email", "enabled", "last_login",
		        "last_active", "user_image"],
		order_by="enabled desc, full_name asc")
	perms: dict[str, list] = {}
	for p in frappe.get_all("User Permission",
	                        filters={"user": ("in", list(by_user)), "allow": "Property"},
	                        fields=["user", "for_value"]):
		perms.setdefault(p.user, []).append(p.for_value)
	pins = {p.name: p.must_reset for p in frappe.get_all(
		"Cashier PIN", filters={"name": ("in", list(by_user))}, fields=["name", "must_reset"])}

	out = []
	for u in users:
		props = sorted(perms[u.name]) if u.name in perms else None
		if not _visible_to(set(props) if props is not None else None, property):
			continue
		roles = [r for r in ROLE_NAMES if r in by_user[u.name]]
		is_it_user = any(r in IT_ONLY for r in roles)
		out.append({
			"user": u.name, "full_name": u.full_name or "", "email": u.email or u.name,
			"enabled": u.enabled, "roles": roles, "properties": props,
			"last_login": str(u.last_login) if u.last_login else None,
			"last_active": str(u.last_active) if u.last_active else None,
			"user_image": u.user_image,
			"pin": ("reset" if pins[u.name] else "set") if u.name in pins else "none",
			"is_self": u.name == me,
			"editable": u.name != me and (it or not is_it_user),
		})
	return out


def _parse_list(val) -> list | None:
	if val in (None, "", "all"):
		return None
	if isinstance(val, str):
		val = json.loads(val)
	return [v for v in val if v]


@frappe.whitelist(methods=["POST"])
@require_roles()
@rate_limit(limit=120, seconds=3600)
def save_staff(property: str, email: str, full_name: str, roles, properties=None,
               enabled=1, send_welcome=0) -> dict:
	"""Add a person, or change an existing person's roles, property access
	and whether they can sign in."""
	it = _caller_is_it()
	me = frappe.session.user
	email = (email or "").strip().lower()
	full_name = (full_name or "").strip()
	if not validate_email_address(email):
		frappe.throw(_("Enter a valid email address."))
	if not full_name:
		frappe.throw(_("Enter their name."))
	if email in [n.lower() for n in NEVER_LISTED]:
		frappe.throw(_("That account can't be managed here."), frappe.PermissionError)

	want_roles = _parse_list(roles) or []
	unknown = [r for r in want_roles if r not in ROLE_NAMES]
	if unknown:
		frappe.throw(_("Unknown role: {0}").format(", ".join(unknown)))
	if not want_roles:
		frappe.throw(_("Pick at least one role."))
	want_props = _parse_list(properties)
	on = str(enabled).lower() in ("1", "true")

	# --- what the caller may grant ------------------------------------------
	mine = restricted_properties()
	if mine is not None:
		if want_props is None:
			frappe.throw(_("You can only give access to your own properties."),
			             frappe.PermissionError)
		outside = [p for p in want_props if p not in mine]
		if outside:
			frappe.throw(_("You don't have access to {0}.").format(", ".join(outside)),
			             frappe.PermissionError)
	for p in want_props or []:
		if not frappe.db.exists("Property", p):
			frappe.throw(_("Unknown property: {0}").format(p))

	exists = frappe.db.exists("User", email)
	before = {"roles": [], "properties": None, "enabled": None}
	if exists:
		if email == me.lower():
			frappe.throw(_("You can't change your own access - ask another admin."),
			             frappe.PermissionError)
		user = frappe.get_doc("User", email)
		if user.user_type != "System User":
			frappe.throw(_("{0} is a guest account, not staff.").format(email))
		held = [r.role for r in user.roles]
		if not it and any(r in IT_ONLY for r in held):
			frappe.throw(_("Only IT can change an IT administrator."), frappe.PermissionError)
		cur_props = _user_properties(email)
		if mine is not None and (cur_props is None or any(p not in mine for p in cur_props)):
			frappe.throw(_("This person has access beyond your properties - ask IT."),
			             frappe.PermissionError)
		before = {"roles": [r for r in ROLE_NAMES if r in held],
		          "properties": cur_props, "enabled": user.enabled}
	else:
		held = []
		user = frappe.get_doc({
			"doctype": "User", "email": email, "first_name": full_name,
			"user_type": "System User", "send_welcome_email": 0, "enabled": 1,
		})

	if not it:
		gained = set(want_roles) - set(held)
		lost = (set(held) & set(ROLE_NAMES)) - set(want_roles)
		if (gained | lost) & set(IT_ONLY):
			frappe.throw(_("Only IT can grant or remove the IT administrator role."),
			             frappe.PermissionError)

	# --- write ----------------------------------------------------------------
	names = full_name.split(" ", 1)
	user.first_name = names[0]
	user.last_name = names[1] if len(names) > 1 else ""
	user.enabled = 1 if on else 0
	keep = [r for r in user.roles if r.role not in ROLE_NAMES]
	user.set("roles", [])
	for r in keep:
		user.append("roles", {"role": r.role})
	for r in want_roles:
		user.append("roles", {"role": r})
	user.flags.ignore_permissions = True
	if exists:
		user.save()
	else:
		user.insert()

	existing = frappe.get_all("User Permission",
	                          filters={"user": email, "allow": "Property"},
	                          fields=["name", "for_value"])
	target = set(want_props or [])
	for row in existing:
		if want_props is None or row.for_value not in target:
			frappe.delete_doc("User Permission", row.name, ignore_permissions=True, force=True)
	have = {row.for_value for row in existing}
	for p in sorted(target - have):
		frappe.get_doc({"doctype": "User Permission", "user": email, "allow": "Property",
		                "for_value": p, "apply_to_all_doctypes": 1}).insert(ignore_permissions=True)

	if not exists and str(send_welcome).lower() in ("1", "true"):
		user.send_welcome_mail_to_user()

	after = {"roles": want_roles, "properties": want_props, "enabled": user.enabled}
	from kamra.savings import log_action
	log_action("staff_added" if not exists else "staff_changed", "User", email,
	           property=property,
	           rationale=f"{'Added' if not exists else 'Changed access for'} {full_name} <{email}>",
	           before_snapshot=before if exists else None, after_snapshot=after)
	return {"ok": True, "user": email, "created": not exists}


@frappe.whitelist()
@require_roles()
def role_matrix() -> dict:
	"""Per role, the settings pages it may change (admins: all of them)."""
	from kamra.authz import ADMIN
	from kamra.settings import MODULES
	out = {}
	for r in ROLE_NAMES:
		out[r] = [m.id for m in MODULES if r in ADMIN or r in m.editors]
	return out
