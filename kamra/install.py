import frappe


def after_install():
	set_site_favicon()
	# NOTE: the governed agent user (agent@kamra.local) is deliberately NOT
	# created here. seed_rbac_v2.ensure_agent_user() writes custom DocPerms,
	# and in Frappe ANY custom perm on a doctype replaces ALL its standard
	# perms - seeding just the agent's grants at install silently revoked
	# every other role's access to Property on fresh sites. The full RBAC
	# seed (setup wizard / seed scripts) creates the agent user with the
	# complete permission set instead.


def set_site_favicon():
	"""A fresh site shows Frappe's favicon on /login and the Desk until
	Website Settings carries ours. Never overrides a hotelier's custom one."""
	ws = frappe.get_doc("Website Settings")
	if not ws.favicon:
		ws.favicon = "/assets/kamra/kamra-mark.svg"
		ws.flags.ignore_mandatory = True
		ws.save(ignore_permissions=True)
