# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class RoomType(Document):
	def on_update(self):
		# Villa room types get a whole_property Sellable Unit (ADR-001).
		if self.room_category == "Villa":
			try:
				from kamra.siu.units import ensure_whole_property_siu
				ensure_whole_property_siu(self.name)
			except Exception:
				frappe.log_error(title="Sellable Unit sync on Room Type update")
