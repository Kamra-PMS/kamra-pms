# Copyright (c) 2026, Kamra and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

# what was withheld: fixed once recorded; only the certificate is filled in
_WITHHELD = ("property", "account", "folio", "payment", "entry", "tax_code",
             "rate", "amount", "withheld_on")


class TaxWithheld(Document):
	def validate(self):
		"""Written only by kamra.receivables (a company payment with tax
		withheld). Desk or /api/resource may add the certificate, never
		change what was withheld."""
		if self.is_new():
			if not self.flags.kamra_withholding:
				frappe.throw(_("Tax withheld is recorded with the company's payment."),
				             frappe.PermissionError)
			return
		old = self.get_doc_before_save()
		if old and any(str(self.get(f) or "") != str(old.get(f) or "") for f in _WITHHELD):
			frappe.throw(_("What was withheld can't change. Reverse the payment instead."))
