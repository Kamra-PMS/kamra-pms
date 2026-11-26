# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from kamra.localization import money_text


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
		base = 0.0 if self.nc else subtotal - discount
		self.order_total = base + self.apply_levy(base)
		self.guard_room_posting()
		self.guard_bill_close()
		self.stamp_cashier()

	def apply_levy(self, base: float) -> float:
		"""The outlet's levy (a service charge) on the bill after discount, as one
		amount added to the order total. Kamra then taxes, settles and posts the
		total as it is; `levy_taxable` says whether the tax is charged on the levy
		too (see pos._bill_tax_base). Worked out while the bill is new or open; once
		it is paid or on a room, what was charged stays charged. NC bills get none."""
		if not self.is_new() and (self.paid or self.posted_to_folio
		                          or self.status == "Cancelled"):
			return float(self.levy_amount or 0)
		outlet = frappe.db.get_value(
			"POS Outlet", self.outlet,
			["levy_label", "levy_percent", "levy_taxable"], as_dict=True) or {}
		percent = float(outlet.get("levy_percent") or 0)
		self.levy_label = outlet.get("levy_label") or ""
		self.levy_percent = percent
		self.levy_taxable = 0 if outlet.get("levy_taxable") == 0 else 1
		self.levy_amount = round(base * percent / 100, 2) \
			if percent > 0 and base > 0 else 0.0
		return self.levy_amount

	def stamp_cashier(self):
		"""The cashier on the bill: whoever closes it (pay_order, a room
		posting or an NC close all land here). Set once, on the close, and
		only here: a value sent by a client is put back. A user with no till
		role (Guest, Administrator, an integration account) leaves it blank."""
		previous = self.get_doc_before_save()
		self.settled_by = previous.settled_by if previous else None
		if self.status != "Delivered" or self.settled_by or \
				(previous and previous.status == "Delivered"):
			return
		from kamra.authz import ADMIN
		from kamra.pos import POS_ROLES
		user = frappe.session.user
		if user not in ("Guest", "Administrator") and \
				set(POS_ROLES + ADMIN) & set(frappe.get_roles(user)):
			self.settled_by = user

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
				"outlet to close it.").format(where))

	def guard_bill_close(self):
		"""Delivered means the BILL is closed, not that the food left the
		pass (the kitchen tracks that per line: kot_status Prepared). A bill
		closes only when it is settled one of three ways:

		- paid at the outlet (pay_order: Cash / Card / the country's instant modes),
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
				frappe.throw(_("A paid bill needs its payment mode."))
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
			"This bill is not settled. Take payment at the outlet, "
			"charge it to an in-house guest's room, or mark it NC with "
			"an authorization before closing it."))

	def on_update(self):
		previous = self.get_doc_before_save()
		old_status = previous.status if previous else None
		if self.status != "Delivered" or old_status == "Delivered":
			return
		from kamra.business_date import get_business_date
		self.db_set("business_date", get_business_date(self.property), update_modified=False)
		if self.posted_to_folio or not self.reservation:
			return
		# settled at the outlet (cash, card...) - never also post to the room
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
		# the outlet's own rate, 0 included (the field defaults new outlets to 5;
		# `or 5` here charged tax at a 0% outlet)
		gst = frappe.db.get_value("POS Outlet", self.outlet, "gst_rate")
		gst = 5 if gst is None else gst
		from kamra.business_date import get_business_date
		detail = ", ".join(
			f"{it.item_name} ×{int(it.qty)}" for it in self.items if not it.voided)
		posting_date = get_business_date(self.property)
		where = self.outlet.split('-')[-1]
		# the items, and - when the outlet has a levy - the levy as its own line,
		# so the guest's folio shows it and the tax can differ between them
		levy = float(self.levy_amount or 0)
		items_total = float(self.order_total or 0) - levy
		folio.append("charges", {
			"posting_date": posting_date,
			"charge_type": "Food & Beverage",
			"reservation": self.reservation,
			"description": f"{where}: {detail} ({self.name})",
			"qty": 1,
			"rate": items_total,
			"amount": items_total,
			"gst_rate": float(gst),
			"auto_posted": 1,
			"is_alcohol": 1 if has_alcohol else 0,
		})
		if levy > 0:
			label = self.levy_label or "Service charge"
			folio.append("charges", {
				"posting_date": posting_date,
				"charge_type": "Food & Beverage",
				"reservation": self.reservation,
				# the bill's name stays in the text: move_room_bill finds its lines by it
				"description": f"{where}: {label} {float(self.levy_percent or 0):g}% ({self.name})",
				"qty": 1,
				"rate": levy,
				"amount": levy,
				"gst_rate": float(gst) if int(self.levy_taxable or 0) else 0.0,
				"auto_posted": 1,
				"is_alcohol": 1 if has_alcohol else 0,
			})
		_recalculate(folio)
		from kamra.ledger import save_folio
		save_folio(folio)
		self.db_set("posted_to_folio", 1, update_modified=False)
		from kamra.webhooks import emit_folio_posted
		lines = folio.charges[-2:] if levy > 0 else folio.charges[-1:]
		for line in lines:
			emit_folio_posted(folio, line)
		from kamra.whatsapp import queue_room_charge_alert
		# the guest is told the whole bill, levy included
		alert = lines[0].as_dict()
		alert["amount"] = float(self.order_total or 0)
		queue_room_charge_alert(folio, alert)

		from kamra.savings import log_action
		log_action("post_pos_order", "POS Order", self.name, self.property,
		           minutes_saved=5 if self.source in ("AI Agent", "QR") else 0,
		           rationale=f"{money_text(self.property, round(self.order_total or 0))} {detail} → {folio.name}",
		           channel="API")
