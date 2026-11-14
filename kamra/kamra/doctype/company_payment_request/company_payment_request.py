# Copyright (c) 2026, Kamra and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

# what was proposed: fixed once the request exists
_PROPOSED = ("property", "account", "amount", "mode", "reference",
             "received_on", "allocations", "requested_by")


class CompanyPaymentRequest(Document):
	def validate(self):
		"""Only kamra.ledger.decide_city_ledger_payment decides (it sets the
		flag), so Desk or /api/resource can't confirm, re-open a decided
		request to post it twice, or change what is confirmed."""
		if self.is_new():
			if self.status != "Pending":
				frappe.throw(_("A new company payment request is always Pending."))
			return
		old = self.get_doc_before_save()
		if not old:
			return
		if old.status != "Pending":
			frappe.throw(_("This payment was already {0}.").format(_(old.status).lower()))
		if any(str(self.get(f) or "") != str(old.get(f) or "") for f in _PROPOSED):
			frappe.throw(_("What was proposed can't change. Reject it and record it again."))
		if self.status != old.status and not self.flags.kamra_decision:
			frappe.throw(_("Confirm or reject it from the company account."),
			             frappe.PermissionError)
