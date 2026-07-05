# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class Folio(Document):
	def validate(self):
		self.guard_closed()

	def guard_closed(self):
		"""Once the GST invoice number is assigned the bill is frozen:
		no reopening, no renumbering, no touching charge lines — only
		settling payments may still be recorded. Adjustments belong on a
		new folio (credit note territory), not inside an issued invoice."""
		if self.is_new():
			return
		old = self.get_doc_before_save()
		if not old or old.status != "Closed":
			return
		if self.status != "Closed" or 				self.invoice_number != old.invoice_number:
			frappe.throw(_("A closed folio cannot be reopened or renumbered."))

		def sig(rows):
			return [(r.charge_type, str(r.posting_date),
			         round(float(r.amount or 0), 2),
			         float(r.gst_rate or 0)) for r in rows]
		if sig(self.charges) != sig(old.charges):
			frappe.throw(_(
				"Invoice {0} is issued — its charges are frozen. Post "
				"adjustments on a new folio.").format(old.invoice_number))
		if len(self.payments) < len(old.payments):
			frappe.throw(_("Payments cannot be removed from a closed folio."))
