# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SecurityDeposit(Document):
	def validate(self):
		req = float(self.required_amount or 0)
		col = float(self.collected_amount or 0)
		withheld = float(self.withheld_amount or 0)
		refunded = float(self.refunded_amount or 0)
		self.balance = max(0.0, col - withheld - refunded)
		if self.status == "Waived" and not (self.reason or "").strip():
			frappe.throw("Waiving a deposit requires a reason.")
		if self.status == "Withheld" and withheld <= 0:
			frappe.throw("Withheld status needs a withheld amount.")
		if req < 0 or col < 0 or withheld < 0 or refunded < 0:
			frappe.throw("Deposit amounts cannot be negative.")
