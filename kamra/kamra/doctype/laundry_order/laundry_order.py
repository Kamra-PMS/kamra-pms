# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LaundryOrder(Document):
	def validate(self):
		total = 0.0
		for it in self.items:
			it.amount = float(it.qty or 0) * float(it.rate or 0)
			total += it.amount
		self.total = total
		if not self.guest_name and self.reservation:
			self.guest_name = frappe.db.get_value(
				"Reservation", self.reservation, "guest_name")
