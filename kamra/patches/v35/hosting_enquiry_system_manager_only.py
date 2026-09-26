"""Hosting Enquiry is sales PII — System Manager only (issue #93)."""

import frappe


def execute():
	frappe.db.delete("Custom DocPerm", {"parent": "Hosting Enquiry"})
	frappe.db.sql(
		"DELETE FROM `tabDocPerm` WHERE parent=%s AND role != %s",
		("Hosting Enquiry", "System Manager"),
	)
	frappe.clear_cache(doctype="Hosting Enquiry")
