# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Property(Document):
	def on_update(self):
		# Single-site tenants: keep Frappe's site clock aligned with the
		# property so night audit / now_datetime follow hotel local time.
		# Multi-property sites with different zones should leave System
		# Settings alone (only sync when this is the sole property).
		tz = (self.timezone or "").strip()
		if not tz or not self.has_value_changed("timezone"):
			return
		if frappe.db.count("Property") > 1:
			return
		current = frappe.db.get_single_value("System Settings", "time_zone")
		if current == tz:
			return
		frappe.db.set_single_value("System Settings", "time_zone", tz)
		frappe.clear_cache()
