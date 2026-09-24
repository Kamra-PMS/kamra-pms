"""New privacy defaults are for new properties. A hotel already running
keeps exactly what it had: no automatic erasure until it chooses a period."""

import frappe


def execute():
	frappe.db.sql("update `tabProperty` set guest_retention_months = 0")
