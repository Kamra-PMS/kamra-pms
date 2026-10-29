# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Property(Document):
	def validate(self):
		# A kind switch in Settings (or Desk) gets the new kind's preset,
		# the same way setup_property applies it at creation. Only empty
		# preset fields are filled, so explicit admin values survive.
		if not self.is_new() and self.has_value_changed("property_kind"):
			from kamra.property_presets import apply_kind_change
			apply_kind_change(self)

	def after_insert(self):
		# A new property starts with allowances signed off by a Hotel Admin,
		# every amount. Existing properties keep the registry default (Off),
		# so an upgrade changes nothing.
		from kamra.settings import clear_cache, write_kv
		write_kv(self.name, "allowance_approval", "Hotel Admin")
		write_kv(self.name, "allowance_approval_above", 0)
		clear_cache(self.name)

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
