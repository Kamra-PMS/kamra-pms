# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class LongStayDiscount(Document):
	def validate(self):
		if int(self.min_nights or 0) < 1:
			frappe.throw(_("Minimum nights is at least 1."))
		if not 0 < float(self.discount_percent or 0) < 100:
			frappe.throw(_("The discount is more than 0% and under 100%."))
