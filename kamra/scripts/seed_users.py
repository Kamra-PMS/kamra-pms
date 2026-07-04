"""Seed demo roles and users for every module.

Run via bench console:
    from kamra.scripts.seed_users import execute; execute()

Idempotent. Creates roles with scoped permissions and one demo user each:
  - Front Desk       → operational doctypes (bookings, rooms, housekeeping)
  - Revenue Manager  → pricing doctypes (rate plans, seasons, vouchers)
  - Finance          → read money-bearing doctypes (invoicing comes with folios)
"""

import frappe

ALL_KAMRA_DOCTYPES = [
	"Property", "Room Type", "Room", "Rate Plan", "Guest", "Reservation",
	"Housekeeping Task", "Agent Action Log", "Meal Plan", "Season",
	"Discount Voucher", "Company", "Group Booking",
]

# role -> {doctype: (read, write, create)}
ROLE_GRANTS = {
	"Front Desk": {
		"Property": (1, 0, 0),
		"Room Type": (1, 0, 0),
		"Room": (1, 1, 1),
		"Rate Plan": (1, 0, 0),
		"Meal Plan": (1, 0, 0),
		"Season": (1, 0, 0),
		"Discount Voucher": (1, 0, 0),
		"Guest": (1, 1, 1),
		"Reservation": (1, 1, 1),
		"Housekeeping Task": (1, 1, 1),
		"Group Booking": (1, 1, 1),
		"Company": (1, 0, 0),
		"Agent Action Log": (1, 0, 1),
	},
	"Revenue Manager": {
		"Property": (1, 0, 0),
		"Room Type": (1, 1, 1),
		"Rate Plan": (1, 1, 1),
		"Meal Plan": (1, 1, 1),
		"Season": (1, 1, 1),
		"Discount Voucher": (1, 1, 1),
		"Reservation": (1, 0, 0),
		"Company": (1, 1, 1),
		"Agent Action Log": (1, 0, 0),
	},
	"Housekeeping": {
		"Property": (1, 0, 0),
		"Room": (1, 1, 0),
		"Room Type": (1, 0, 0),
		"Housekeeping Task": (1, 1, 1),
		"Reservation": (1, 0, 0),
		"Service Ticket": (1, 1, 1),
		"Lost And Found Item": (1, 1, 1),
	},
	"Finance": {
		"Property": (1, 0, 0),
		"Reservation": (1, 0, 0),
		"Guest": (1, 0, 0),
		"Company": (1, 1, 1),
		"Discount Voucher": (1, 0, 0),
		"Agent Action Log": (1, 0, 0),
	},
}

USERS = [
	{"email": "admin@kamra.local", "first_name": "Demo", "last_name": "Admin",
	 "password": "KamraAdmin1!", "roles": ["System Manager"]},
	{"email": "frontdesk@kamra.local", "first_name": "Ravi",
	 "last_name": "FrontDesk", "password": "KamraDesk1!",
	 "roles": ["Front Desk"]},
	{"email": "revenue@kamra.local", "first_name": "Anita",
	 "last_name": "Revenue", "password": "KamraRev1!",
	 "roles": ["Revenue Manager", "Front Desk"]},
	{"email": "finance@kamra.local", "first_name": "Suresh",
	 "last_name": "Finance", "password": "KamraFin1!",
	 "roles": ["Finance"]},
	{"email": "hk@kamra.local", "first_name": "Lakshmi",
	 "last_name": "Housekeeping", "password": "KamraHK1!",
	 "roles": ["Housekeeping"]},
]


def ensure_roles():
	for role, grants in ROLE_GRANTS.items():
		if not frappe.db.exists("Role", role):
			frappe.get_doc({
				"doctype": "Role", "role_name": role, "desk_access": 1,
			}).insert(ignore_permissions=True)
			print(f"created role: {role}")
		for doctype, (read, write, create) in grants.items():
			perm = frappe.db.get_value(
				"Custom DocPerm", {"parent": doctype, "role": role}, "name"
			)
			if perm:
				frappe.db.set_value("Custom DocPerm", perm, {
					"read": read, "write": write, "create": create,
				})
				continue
			frappe.get_doc({
				"doctype": "Custom DocPerm",
				"parent": doctype,
				"parenttype": "DocType",
				"parentfield": "permissions",
				"role": role,
				"read": read, "write": write, "create": create,
				"report": read, "email": read, "print": read,
			}).insert(ignore_permissions=True)
		print(f"granted {role} perms on {len(grants)} doctypes")


def ensure_users():
	from frappe.utils.password import update_password

	for spec in USERS:
		if frappe.db.exists("User", spec["email"]):
			user = frappe.get_doc("User", spec["email"])
			have = {r.role for r in user.roles}
			missing = [r for r in spec["roles"] if r not in have]
			if missing:
				for r in missing:
					user.append("roles", {"role": r})
				user.save(ignore_permissions=True)
				print(f"updated roles for {spec['email']}: +{missing}")
			continue
		user = frappe.get_doc({
			"doctype": "User",
			"email": spec["email"],
			"first_name": spec["first_name"],
			"last_name": spec["last_name"],
			"enabled": 1,
			"user_type": "System User",
			"send_welcome_email": 0,
			"roles": [{"role": r} for r in spec["roles"]],
		})
		user.insert(ignore_permissions=True)
		update_password(user.name, spec["password"])
		print(f"created user: {spec['email']}")


def execute():
	ensure_roles()
	ensure_users()
	frappe.db.commit()
	print("Roles and demo users ready.")
