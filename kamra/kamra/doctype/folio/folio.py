# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class Folio(Document):
	def validate(self):
		self.guard_closed()
		self.stamp_payment_currency()

	def stamp_payment_currency(self):
		"""Every payment row carries the property's currency unless a writer
		set one (FX rows do). One guard here covers all writers (#341)."""
		missing = [p for p in self.payments if not p.currency]
		if missing:
			from kamra.localization import default_currency, pack_for
			cur = (frappe.get_cached_value("Property", self.property, "currency")
			       or default_currency(pack_for(self.property)))
			for p in missing:
				p.currency = cur

	def guard_closed(self):
		"""Once the GST invoice number is assigned the bill is frozen:
		no reopening, no renumbering, no touching charge lines — only
		settling payments may still be recorded. Adjustments belong on a
		new folio (credit note territory), not inside an issued invoice.

		The one sanctioned way through: kamra.folio.cancel_invoice, which
		first books the number into the Cancelled Invoice register (the
		sequence never loses a bill) and sets this flag for its own save."""
		if getattr(frappe.flags, "kamra_invoice_cancel", False):
			return
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
