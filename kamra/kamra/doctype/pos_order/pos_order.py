# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class POSOrder(Document):
	def validate(self):
		subtotal = 0.0
		for it in self.items:
			it.amount = 0.0 if it.voided else float(it.qty or 1) * float(it.rate or 0)
			subtotal += it.amount
		self.subtotal = subtotal
		discount = min(float(self.discount_amount or 0), subtotal)
		self.discount_amount = discount
		# NC (no charge): the items stand for the kitchen and the audit,
		# but the bill is zero
		self.order_total = 0.0 if self.nc else subtotal - discount
		self.guard_room_posting()
		self.guard_bill_close()

	def charges_to_room(self) -> bool:
		"""The bill is meant for a guest's room: room service, or any order
		(a dine-in one too) tied to a room or an in-house stay."""
		return bool(self.room or self.reservation
		            or self.order_type == "Room Service")

	def guard_room_posting(self):
		"""A room bill closes (Delivered) only two ways: it posts to a
		checked-in stay's folio, or it was paid at the outlet. Anything else
		was food served with nothing billed and nothing paid."""
		if self.status != "Delivered" or self.paid or self.nc \
		   or self.posted_to_folio or not self.charges_to_room():
			return
		previous = self.get_doc_before_save()
		if previous and previous.status == "Delivered":
			return
		if self.room and not self.reservation:
			# the guest may have checked in since the order was taken
			self.reservation = frappe.db.get_value(
				"Reservation", {"room": self.room, "status": "Checked In",
				                "property": self.property}, "name")
		status = self.reservation and frappe.db.get_value(
			"Reservation", self.reservation, "status")
		if status != "Checked In":
			where = (_("Room {0}").format(frappe.db.get_value(
				"Room", self.room, "room_number") or self.room)
				if self.room else _("this bill"))
			frappe.throw(_(
				"{0} has no checked-in guest to post to. Take payment at the "
				"outlet (Cash, Card or UPI) to close it.").format(where))

	def guard_bill_close(self):
		"""Delivered means the BILL is closed, not that the food left the
		pass (the kitchen tracks that per line: kot_status Prepared). A bill
		closes only when it is settled one of three ways:

		- paid at the outlet (pay_order: Cash / Card / UPI),
		- signed to a checked-in guest's room (guard_room_posting checks the
		  stay; on_update posts it to the folio),
		- complimentary (NC) authorized through mark_nc.

		A bill with nothing left to charge (every line voided) also closes.
		Anything else was food served with nothing billed and nothing paid."""
		if self.status != "Delivered":
			return
		previous = self.get_doc_before_save()
		if previous and previous.status == "Delivered":
			return
		if self.paid:
			if not self.payment_mode:
				frappe.throw(_("A paid bill needs its payment mode "
				              "(Cash, Card or UPI)."))
			return
		if self.nc:
			if not (self.nc_authorized_by or "").strip():
				frappe.throw(_("An NC (complimentary) bill needs who "
				              "authorized it before it can close."))
			return
		if self.posted_to_folio or self.charges_to_room():
			# room bills: guard_room_posting has already insisted on a
			# checked-in stay; on_update posts the bill to its folio
			return
		if not any(not it.voided for it in self.items):
			return
		frappe.throw(_(
			"This bill is not settled. Take payment (Cash, Card or UPI), "
			"charge it to an in-house guest's room, or mark it NC with "
			"an authorization before closing it."))

	def on_update(self):
		previous = self.get_doc_before_save()
		old_status = previous.status if previous else None
		if self.status != "Delivered" or old_status == "Delivered":
			return
		if self.posted_to_folio or not self.reservation:
			return
		# settled at the outlet (cash/card/UPI) - never also post to the room
		if self.paid:
			return
		# complimentary - there is nothing to charge anywhere
		if self.nc:
			return
		# room-service charge routed by the company's billing rules; any
		# alcohol on the order forces the whole order to the guest folio
		from kamra.folio import _recalculate, target_folio

		res = frappe.get_doc("Reservation", self.reservation)
		has_alcohol = any(
			frappe.db.get_value("Menu Item", it.menu_item, "is_alcohol")
			for it in self.items if it.menu_item and not it.voided
		)
		folio = frappe.get_doc(
			"Folio",
			target_folio(res, "Food & Beverage", is_alcohol=has_alcohol))
		if folio.status == "Closed":
			frappe.throw("Folio is closed — settle the order directly.")
		gst = frappe.db.get_value("POS Outlet", self.outlet, "gst_rate") or 5
		from kamra.business_date import get_business_date
		detail = ", ".join(
			f"{it.item_name} ×{int(it.qty)}" for it in self.items if not it.voided)
		folio.append("charges", {
			"posting_date": get_business_date(self.property),
			"charge_type": "Food & Beverage",
			"reservation": self.reservation,
			"description": f"{self.outlet.split('-')[-1]}: {detail} ({self.name})",
			"qty": 1,
			"rate": self.order_total,
			"amount": self.order_total,
			"gst_rate": float(gst),
			"auto_posted": 1,
			"is_alcohol": 1 if has_alcohol else 0,
		})
		_recalculate(folio)
		from kamra.ledger import save_folio
		save_folio(folio)
		self.db_set("posted_to_folio", 1, update_modified=False)
		from kamra.webhooks import emit_folio_posted
		emit_folio_posted(folio, folio.charges[-1])

		from kamra.savings import log_action
		log_action("post_pos_order", "POS Order", self.name, self.property,
		           minutes_saved=5 if self.source in ("AI Agent", "QR") else 0,
		           rationale=f"₹{self.order_total:,.0f} {detail} → {folio.name}",
		           channel="API")
