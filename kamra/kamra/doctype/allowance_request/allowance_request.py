# Copyright (c) 2026, Kamra and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

# what was asked for: fixed once the request exists
_ASKED = ("property", "folio", "reservation", "amount", "gst_rate",
          "reason_code", "reason", "requested_by")


class AllowanceRequest(Document):
	def validate(self):
		"""Only kamra.api.decide_allowance decides (it sets the flag), so
		Desk or /api/resource can't approve, re-open a decided request to
		post it twice, or change what is approved after it was asked."""
		if self.is_new():
			# an allowance posted at once is written already Approved
			if self.status != "Pending" and not self.flags.kamra_decision:
				frappe.throw(_("A new allowance request is always Pending."))
			return
		old = self.get_doc_before_save()
		if not old:
			return
		if old.status != "Pending":
			frappe.throw(_("This allowance was already {0}.").format(_(old.status).lower()))
		if any(str(self.get(f) or "") != str(old.get(f) or "") for f in _ASKED):
			frappe.throw(_("What was asked for can't change. Reject it and ask again."))
		if self.status != old.status and not self.flags.kamra_decision:
			frappe.throw(_("Approve or reject an allowance from Allowances to approve."),
			             frappe.PermissionError)
