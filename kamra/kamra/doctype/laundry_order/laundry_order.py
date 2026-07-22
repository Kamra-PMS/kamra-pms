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
		if (self.order_type or "Guest") == "House":
			# staff uniforms / hotel linen - no guest, never billed
			self.reservation = None
			self.complimentary = 1
			if not self.guest_name:
				self.guest_name = self.house_label or "House laundry"
		else:
			if not self.room:
				frappe.throw("A room is required for guest laundry.")
			if not self.guest_name and self.reservation:
				self.guest_name = frappe.db.get_value(
					"Reservation", self.reservation, "guest_name")
