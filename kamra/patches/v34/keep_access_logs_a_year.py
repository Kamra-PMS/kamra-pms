"""DPDP Rules: access and activity logs are kept for at least a year."""

import frappe

MIN_DAYS = 365


def execute():
	ls = frappe.get_single("Log Settings")
	have = {row.ref_doctype: row for row in ls.logs_to_clear}
	for doctype in ("Access Log", "Activity Log"):
		row = have.get(doctype)
		if row and (row.days or 0) < MIN_DAYS:
			row.days = MIN_DAYS
		elif not row:
			ls.append("logs_to_clear", {"ref_doctype": doctype, "days": MIN_DAYS})
	ls.save(ignore_permissions=True)
