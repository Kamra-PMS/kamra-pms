# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class POSRefund(Document):
	"""Money given back on a paid bill. Written only by kamra.pos_refunds
	(which checks the money, the till and the supervisor's PIN), and never
	edited or deleted - whoever is signed in."""

	def validate(self):
		self._only_the_till()

	def on_trash(self):
		self._only_the_till()

	def _only_the_till(self):
		if not self.flags.from_pos_refund:
			frappe.throw(_("Refunds are made at the till, and are never edited or deleted."))
