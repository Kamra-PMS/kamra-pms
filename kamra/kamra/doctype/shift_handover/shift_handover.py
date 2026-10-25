# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from kamra.business_date import assert_transaction_date


class ShiftHandover(Document):
	def validate(self):
		if self.shift_date and self.property:
			self.shift_date = assert_transaction_date(
				self.property, self.shift_date, label="Date",
			)
