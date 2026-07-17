"""Fix three v1 mistakes:

1. Reservation booking fields (booking_type, company, …) were inserted
   into DocType.fields as raw DocField docs and silently dropped —
   re-add them properly with dt.append().
2. Custom DocPerm rows REPLACE a doctype's built-in permissions in
   Frappe, so seeding role perms locked System Manager out. Grant
   System Manager full custom perms on every Kamra doctype, and give
   Front Desk / Finance their missing folio-era grants.
3. The same trap, one layer deeper: seed_rbac_v2.ensure_agent_user()
   writes Custom DocPerms for Kamra Agent, and the moment ONE lands the
   doctype's whole standard permission block stops applying — silently
   revoking Front Desk, Finance, Revenue Manager and Housekeeping on
   every doctype it touched. Symptom: "Insufficient Permission" for a
   Front Desk user on Reservation/Guest/Room/Property/Folio, while the
   SPA mostly keeps working because Kamra's whitelisted endpoints go
   through require_roles and db.set_value, which never consult doctype
   perms at all (see authz.py). sync_standard_perms() repairs it.

Run via bench console:
    from kamra.scripts.fix_perms_fields import execute; execute()
"""

import frappe

# The flags DocPerm and Custom DocPerm have in common - mirrored wholesale
# rather than cherry-picked, because a half-copied permission is how this mess
# started. (Custom DocPerm is a standalone doctype, not a child table: it has
# `parent` but no parenttype/parentfield, and no set_user_permissions column.
# Copying those across is what makes the insert fail.)
PERM_FLAGS = [
	"permlevel", "if_owner", "select", "read", "write", "create", "delete",
	"submit", "cancel", "amend", "report", "export", "import", "share",
	"print", "email",
]

ALL_DOCTYPES = [
	"Property", "Room Type", "Room", "Rate Plan", "Guest", "Reservation",
	"Housekeeping Task", "Agent Action Log", "Meal Plan", "Season",
	"Discount Voucher", "Company", "Group Booking", "Folio",
	"Night Audit Run", "Service Ticket",
]

EXTRA_GRANTS = {
	# role -> {doctype: (read, write, create)}
	"Front Desk": {
		"Folio": (1, 1, 1),
		"Night Audit Run": (1, 0, 1),
		"Service Ticket": (1, 1, 1),
	},
	"Finance": {
		"Folio": (1, 1, 0),
		"Night Audit Run": (1, 0, 0),
		"Service Ticket": (1, 0, 0),
	},
}

RESERVATION_FIELDS = [
	dict(fieldname="booking_type", fieldtype="Select",
	     options="Individual\nGroup\nCorporate", default="Individual",
	     label="Booking Type", insert_after="status"),
	dict(fieldname="company", fieldtype="Link", options="Company",
	     label="Company", insert_after="booking_type"),
	dict(fieldname="group_booking", fieldtype="Link", options="Group Booking",
	     label="Group Booking", insert_after="company"),
	dict(fieldname="meal_plan", fieldtype="Link", options="Meal Plan",
	     label="Meal Plan", insert_after="room"),
	dict(fieldname="rate_plan", fieldtype="Link", options="Rate Plan",
	     label="Rate Plan", insert_after="meal_plan"),
	dict(fieldname="voucher", fieldtype="Link", options="Discount Voucher",
	     label="Voucher", insert_after="is_pay_at_hotel"),
	dict(fieldname="discount_amount", fieldtype="Currency", label="Discount",
	     read_only=1, insert_after="voucher"),
	dict(fieldname="auto_price", fieldtype="Check", label="Auto Price",
	     default="1", insert_after="discount_amount"),
]


def fix_reservation_fields():
	dt = frappe.get_doc("DocType", "Reservation")
	existing = {df.fieldname for df in dt.fields}
	changed = False
	for spec in RESERVATION_FIELDS:
		spec = dict(spec)
		anchor = spec.pop("insert_after")
		if spec["fieldname"] in existing:
			continue
		row = dt.append("fields", spec)
		# move the appended row right after its anchor
		fields = list(dt.fields)
		fields.remove(row)
		idx = next(
			(i for i, df in enumerate(fields) if df.fieldname == anchor),
			len(fields) - 1,
		)
		fields.insert(idx + 1, row)
		for i, df in enumerate(fields):
			df.idx = i + 1
		dt.fields = fields
		changed = True
		print(f"Reservation: appended {spec['fieldname']}")
	if changed:
		dt.save(ignore_permissions=True)
		print("Reservation DocType saved.")


def _grant(doctype, role, read, write, create, delete=0):
	perm = frappe.db.get_value(
		"Custom DocPerm", {"parent": doctype, "role": role}, "name"
	)
	if perm:
		frappe.db.set_value("Custom DocPerm", perm, {
			"read": read, "write": write, "create": create, "delete": delete,
		})
		return
	frappe.get_doc({
		"doctype": "Custom DocPerm",
		"parent": doctype,
		"parenttype": "DocType",
		"parentfield": "permissions",
		"role": role,
		"read": read, "write": write, "create": create, "delete": delete,
		"report": read, "email": read, "print": read, "export": read,
	}).insert(ignore_permissions=True)


def fix_permissions():
	for doctype in ALL_DOCTYPES:
		_grant(doctype, "System Manager", 1, 1, 1, delete=1)
	print(f"System Manager: full custom perms on {len(ALL_DOCTYPES)} doctypes")
	for role, grants in EXTRA_GRANTS.items():
		for doctype, (r, w, c) in grants.items():
			_grant(doctype, role, r, w, c)
		print(f"{role}: extra grants on {list(grants)}")


def sync_standard_perms():
	"""Mirror each doctype's own DocPerm rows into Custom DocPerm.

	Frappe's rule: if a doctype has ANY Custom DocPerm row, its entire
	standard permission block is ignored. So granting one role a custom perm
	silently revokes every other role - which is exactly what happened here.

	The repair is deliberately data-driven. The doctype JSONs in this repo are
	the source of truth and already declare every role correctly; this copies
	whatever they say into Custom DocPerm for any role that is missing. No
	hardcoded role list, so it cannot drift from the JSONs and it stays right
	when a new doctype or role is added - just re-run it.

	Only touches doctypes that ALREADY have Custom DocPerm rows: adding rows
	to a clean doctype would switch off its standard perms and create the very
	bug this fixes. Never overwrites an existing custom row, so deliberate
	overrides (System Manager's full grant above) survive.
	"""
	parents = frappe.db.sql_list(
		"select distinct parent from `tabCustom DocPerm`")
	added = 0
	for doctype in parents:
		std = frappe.get_all("DocPerm", filters={"parent": doctype},
		                     fields=["role"] + PERM_FLAGS)
		have = {(c.role, c.permlevel or 0) for c in frappe.get_all(
			"Custom DocPerm", filters={"parent": doctype},
			fields=["role", "permlevel"])}
		for row in std:
			key = (row.role, row.permlevel or 0)
			if key in have:
				continue
			doc = frappe.get_doc({
				"doctype": "Custom DocPerm", "parent": doctype,
				"role": row.role,
				**{f: row.get(f) or 0 for f in PERM_FLAGS},
			})
			doc.insert(ignore_permissions=True)
			added += 1
			print(f"  {doctype}: restored {row.role}")
	print(f"sync_standard_perms: {added} role(s) restored across "
	      f"{len(parents)} doctype(s)")
	return added


def execute():
	fix_reservation_fields()
	fix_permissions()
	sync_standard_perms()
	frappe.clear_cache()
	frappe.db.commit()
	print("Fixed. Reload the UI.")
