# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class POSTableReservation(Document):
	def validate(self):
		if not self.property:
			self.property = frappe.db.get_value(
				"POS Outlet", self.outlet, "property")
