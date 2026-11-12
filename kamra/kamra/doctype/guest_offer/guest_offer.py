# Copyright (c) 2026, Kamra and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

# what was offered: fixed once the offer exists
_OFFERED = ("property", "guest", "reservation", "kind", "value", "experience",
            "room_type", "valid_to", "proposed_by")


class GuestOffer(Document):
	def validate(self):
		"""Only kamra.guest_offers moves an offer along (it sets the flag), so
		Desk or /api/resource can't approve one past the property's limits or
		change what was approved."""
		if self.flags.kamra_offer:
			return
		if self.is_new():
			frappe.throw(_("Propose a guest offer from the guest's profile."),
			             frappe.PermissionError)
		old = self.get_doc_before_save()
		if old and (self.status != old.status or any(
				str(self.get(f) or "") != str(old.get(f) or "") for f in _OFFERED)):
			frappe.throw(_("Approve, decline or redeem an offer from Guest offers."),
			             frappe.PermissionError)
