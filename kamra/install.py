import frappe


AGENT_EMAIL = "agent@kamra.local"
AGENT_ROLE = "Kamra Agent"


def after_install():
	set_site_home_and_favicon()
	ensure_agent_identity()


def after_migrate():
	# heals sites that were installed before the agent identity existed here
	ensure_agent_identity()


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
