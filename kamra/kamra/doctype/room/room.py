# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Room(Document):
	def after_insert(self):
		# Keep Sellable Units in sync with physical inventory (ADR-001).
		try:
			from kamra.siu.units import ensure_individual_siu
			ensure_individual_siu(self.name)
		except Exception:
			frappe.log_error(title="Sellable Unit sync on Room insert")
