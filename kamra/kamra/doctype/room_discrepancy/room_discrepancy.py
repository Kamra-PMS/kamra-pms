# Copyright (c) 2026, Kamra and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class RoomDiscrepancy(Document):
	def validate(self):
		"""Opened and closed only through kamra.housekeeping (it sets the
		flag), so a case can't be closed without a reason from Desk or REST."""
		if self.flags.kamra_case:
			return
		old = None if self.is_new() else self.get_doc_before_save()
		if self.is_new() or (old and (old.status != self.status
		                              or old.close_reason != self.close_reason)):
			frappe.throw(_("Open and close room status cases from the Housekeeping Board."),
			             frappe.PermissionError)
