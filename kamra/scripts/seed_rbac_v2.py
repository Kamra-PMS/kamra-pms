"""RBAC v2: Hotel Admin role (full rights on all Kamra doctypes) and the
AI agent user with API keys for MCP access.

Roles, by intent:
  - System Manager  → IT admin (platform, users, everything incl. schema)
  - Hotel Admin     → owner/GM: full rights on every Kamra doctype
  - Front Desk / Revenue Manager / Finance → scoped (see seed_users)
  - Kamra Agent     → what AI agents get; Front Desk-equivalent ops rights,
                      every action attributable to the agent user

Run via bench console:
    from kamra.scripts.seed_rbac_v2 import execute; execute()
"""

import frappe

from kamra.scripts.fix_perms_fields import ALL_DOCTYPES, _grant

AGENT_EMAIL = "agent@kamra.local"


def ensure_hotel_admin():
	if not frappe.db.exists("Role", "Hotel Admin"):
		frappe.get_doc({
			"doctype": "Role", "role_name": "Hotel Admin", "desk_access": 1,
		}).insert(ignore_permissions=True)
		print("created role: Hotel Admin")
	for doctype in ALL_DOCTYPES:
		_grant(doctype, "Hotel Admin", 1, 1, 1, delete=1)
	print(f"Hotel Admin: full perms on {len(ALL_DOCTYPES)} doctypes")

	# demo admin wears both hats
	user = frappe.get_doc("User", "admin@kamra.local")
	if "Hotel Admin" not in {r.role for r in user.roles}:
		user.append("roles", {"role": "Hotel Admin"})
		user.save(ignore_permissions=True)
		print("admin@kamra.local: +Hotel Admin")


def ensure_agent_user():
	if not frappe.db.exists("Role", "Kamra Agent"):
		frappe.get_doc({
			"doctype": "Role", "role_name": "Kamra Agent", "desk_access": 0,
		}).insert(ignore_permissions=True)
		print("created role: Kamra Agent")
	# agent gets operational rights: everything Front Desk can do
	agent_grants = {
		"Property": (1, 0, 0), "Room Type": (1, 0, 0), "Room": (1, 1, 0),
		"Rate Plan": (1, 0, 0), "Meal Plan": (1, 0, 0), "Season": (1, 0, 0),
		"Discount Voucher": (1, 0, 0), "Guest": (1, 1, 1),
		"Reservation": (1, 1, 1), "Housekeeping Task": (1, 1, 1),
		"Group Booking": (1, 1, 1), "Company": (1, 0, 0),
		"Agent Action Log": (1, 0, 1), "Folio": (1, 1, 1),
		"Night Audit Run": (1, 0, 1), "Service Ticket": (1, 1, 1),
	}
	for doctype, (r, w, c) in agent_grants.items():
		_grant(doctype, "Kamra Agent", r, w, c)
	print("Kamra Agent: ops grants set")

	if not frappe.db.exists("User", AGENT_EMAIL):
		frappe.get_doc({
			"doctype": "User",
			"email": AGENT_EMAIL,
			"first_name": "Kamra",
			"last_name": "Agent",
			"enabled": 1,
			"user_type": "System User",
			"send_welcome_email": 0,
			"roles": [{"role": "Kamra Agent"}],
		}).insert(ignore_permissions=True)
		print(f"created user: {AGENT_EMAIL}")

	user = frappe.get_doc("User", AGENT_EMAIL)
	api_key = user.api_key or frappe.generate_hash(length=15)
	api_secret = frappe.generate_hash(length=15)
	user.api_key = api_key
	user.save(ignore_permissions=True)
	from frappe.utils.password import set_encrypted_password
	set_encrypted_password("User", AGENT_EMAIL, api_secret, "api_secret")
	print("AGENT CREDENTIALS (save these for the MCP server):")
	print(f"  KAMRA_API_KEY={api_key}")
	print(f"  KAMRA_API_SECRET={api_secret}")


def execute():
	ensure_hotel_admin()
	ensure_agent_user()
	frappe.clear_cache()
	frappe.db.commit()
	print("RBAC v2 ready.")
