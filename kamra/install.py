import frappe


def after_install():
	set_site_home_and_favicon()
	# NOTE: the governed agent user (agent@kamra.local) is deliberately NOT
	# created here. seed_rbac_v2.ensure_agent_user() writes custom DocPerms,
	# and in Frappe ANY custom perm on a doctype replaces ALL its standard
	# perms - seeding just the agent's grants at install silently revoked
	# every other role's access to Property on fresh sites. The full RBAC
	# seed (setup wizard / seed scripts) creates the agent user with the
	# complete permission set instead.


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
