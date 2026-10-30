# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class Season(Document):
	def validate(self):
		# the advance is a share of the bill, from 25% to all of it: over
		# 100% would charge more than the stay costs (the booking page takes
		# it online). Empty or 0 means the property's usual deposit %.
		pct = float(self.get("advance_percent") or 0)
		if pct and not 25 <= pct <= 100:
			frappe.throw(_("Advance % at booking is between 25 and 100. Leave it "
			               "empty to use the property's usual deposit."))
