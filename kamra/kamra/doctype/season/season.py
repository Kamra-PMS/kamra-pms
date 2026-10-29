# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class Season(Document):
	def validate(self):
		# the advance is a share of the bill: over 100% would charge the
		# guest more than the stay costs (the booking page takes it online)
		if not 0 <= float(self.get("advance_percent") or 0) <= 100:
			frappe.throw(_("Advance % at booking is between 0 and 100."))
