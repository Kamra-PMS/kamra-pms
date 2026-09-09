"""Seed default banquet department checklist templates for every property."""

import frappe

from kamra.banquet_ops import ensure_default_templates


def execute():
	for prop in frappe.get_all("Property", pluck="name"):
		ensure_default_templates(prop)
