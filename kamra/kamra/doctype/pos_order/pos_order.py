# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import nowdate


class POSOrder(Document):
	def validate(self):
		total = 0.0
		for it in self.items:
			it.amount = float(it.qty or 1) * float(it.rate or 0)
			total += it.amount
		self.order_total = total

	def on_update(self):
		previous = self.get_doc_before_save()
		old_status = previous.status if previous else None
		if self.status != "Delivered" or old_status == "Delivered":
			return
		if self.posted_to_folio or not self.reservation:
			return
		# room-service charge routed by the company's billing rules; any
		# alcohol on the order forces the whole order to the guest folio
		from kamra.folio import _recalculate, target_folio

		res = frappe.get_doc("Reservation", self.reservation)
		has_alcohol = any(
			frappe.db.get_value("Menu Item", it.menu_item, "is_alcohol")
			for it in self.items if it.menu_item
		)
		folio = frappe.get_doc(
			"Folio",
			target_folio(res, "Food & Beverage", is_alcohol=has_alcohol))
		if folio.status == "Closed":
			frappe.throw("Folio is closed — settle the order directly.")
		gst = frappe.db.get_value("POS Outlet", self.outlet, "gst_rate") or 5
		detail = ", ".join(
			f"{it.item_name} ×{int(it.qty)}" for it in self.items)
		folio.append("charges", {
			"posting_date": nowdate(),
			"charge_type": "Food & Beverage",
			"description": f"{self.outlet.split('-')[-1]}: {detail} ({self.name})",
			"qty": 1,
			"rate": self.order_total,
			"amount": self.order_total,
			"gst_rate": float(gst),
			"auto_posted": 1,
			"is_alcohol": 1 if has_alcohol else 0,
		})
		_recalculate(folio)
		folio.save(ignore_permissions=True)
		self.db_set("posted_to_folio", 1, update_modified=False)

		from kamra.savings import log_action
		log_action("post_pos_order", "POS Order", self.name, self.property,
		           minutes_saved=5 if self.source in ("AI Agent", "QR") else 0,
		           rationale=f"₹{self.order_total:,.0f} {detail} → {folio.name}",
		           channel="API")
