# Copyright (c) 2026, Kamra and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils import flt


class VendorBill(Document):
	def validate(self):
		# the money on a bill is always worked out here, never taken as typed
		self.amount = flt(self.amount, 2)
		self.tax_amount = flt(self.amount * flt(self.tax_rate) / 100, 2)
		self.total = flt(self.amount + self.tax_amount, 2)
		self.paid = flt(sum(flt(p.amount) for p in self.payments), 2)
		self.outstanding = flt(self.total - self.paid, 2)
		if self.status in ("Cancelled", "Awaiting Approval"):
			return
		self.status = ("Paid" if self.outstanding <= 0.005 else
		               "Part Paid" if self.paid > 0.005 else "Approved")
