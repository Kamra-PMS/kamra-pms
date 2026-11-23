# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate


class RateRestriction(Document):
	def validate(self):
		if getdate(self.end_date) < getdate(self.start_date):
			frappe.throw(_("The end date is before the start date."))
		if cint(self.min_nights) < 0 or cint(self.max_nights) < 0:
			frappe.throw(_("Nights can't be below zero."))
		if cint(self.max_nights) and cint(self.min_nights) > cint(self.max_nights):
			frappe.throw(_("Minimum nights is more than maximum nights."))
		if not (cint(self.min_nights) or cint(self.max_nights) or self.closed_to_arrival
		        or self.closed_to_departure or self.stop_sell):
			frappe.throw(_("Set at least one restriction: minimum or maximum nights, "
			               "closed to arrival, closed to departure or stop-sell."))
		for link, doctype in (("rate_plan", "Rate Plan"), ("room_type", "Room Type")):
			if self.get(link) and frappe.db.get_value(doctype, self.get(link), "property") != self.property:
				frappe.throw(_("That {0} is not at this property.").format(_(doctype)))
