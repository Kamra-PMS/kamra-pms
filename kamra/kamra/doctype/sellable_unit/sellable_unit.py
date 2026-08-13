# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SellableUnit(Document):
	def validate(self):
		self.unit_name = (self.unit_name or "").strip()
		if not self.unit_name:
			frappe.throw("Unit Name is required.")
		if not self.competition_group:
			# Default: whole-property units compete within the property;
			# individual units compete within their room type.
			if self.unit_kind == "whole_property":
				self.competition_group = f"{self.property}::estate"
			else:
				self.competition_group = f"{self.property}::{self.room_type}"
		if self.unit_kind == "individual" and not self.physical_rooms:
			frappe.throw(
				"Individual sellable units need at least one physical Room."
			)
		if self.unit_kind == "composite" and len(self.physical_rooms or []) < 2:
			frappe.throw("Composite sellable units need at least two Rooms.")
