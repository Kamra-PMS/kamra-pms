"""Guest laundry - the housekeeping side of the linen bag.

Flow: the desk (or the floor) logs a pickup request -> an attendant
collects and counts the items with the guest (priced from the property's
rate card, never by the caller) -> the bag moves In Process -> Ready ->
items are returned piece by piece -> delivery posts the bill to the
guest's folio at the services GST rate. Shortages block delivery unless
they're explicitly noted, so a missing shirt is a decision, not an
accident.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

from kamra.authz import require_roles

LAUNDRY_ROLES = ("Housekeeping", "Front Desk", "Kamra Agent")
RATE_ROLES = ("Front Desk", "Finance", "Kamra Agent")
SERVICES = ("Wash & Iron", "Dry Clean", "Iron Only")
LAUNDRY_GST = 18.0  # services rate; resolved server-side on posting


# ── the rate card ────────────────────────────────────────────────────────

@frappe.whitelist()
@require_roles(*LAUNDRY_ROLES, "Finance")
def laundry_rates(property: str):
	"""The property's laundry price list (the card the attendant quotes
	from). Grouped by item for the pickers."""
	rows = frappe.get_all(
		"Laundry Rate", filters={"property": property, "disabled": 0},
		fields=["name", "item_name", "service_type", "rate", "express_rate"],
		order_by="item_name, service_type")
	for r in rows:
		r["express_rate"] = float(r.express_rate or 0) or round(
			float(r.rate) * 1.5, 0)
	return rows


@frappe.whitelist(methods=["POST"])
@require_roles(*RATE_ROLES)
def save_laundry_rate(property: str, item_name: str, service_type: str,
                      rate: float, express_rate=None, name: str | None = None,
                      disabled: int = 0):
	"""Add or edit one line of the rate card."""
	if service_type not in SERVICES:
		frappe.throw(_("Service must be one of: ") + ", ".join(SERVICES))
	if float(rate) <= 0:
		frappe.throw(_("Rate must be positive."))
	if not (item_name or "").strip():
		frappe.throw(_("Item name is required."))
	if name:
		doc = frappe.get_doc("Laundry Rate", name)
	else:
		existing = frappe.db.get_value("Laundry Rate", {
			"property": property, "item_name": item_name.strip(),
			"service_type": service_type})
		doc = (frappe.get_doc("Laundry Rate", existing) if existing
		       else frappe.new_doc("Laundry Rate"))
	doc.update({
		"property": property, "item_name": item_name.strip()[:80],
		"service_type": service_type, "rate": float(rate),
		"express_rate": float(express_rate) if express_rate else None,
		"disabled": 1 if int(disabled or 0) else 0,
	})
	doc.save()
	return {"ok": True, "name": doc.name}


@frappe.whitelist(methods=["POST"])
@require_roles(*RATE_ROLES)
def delete_laundry_rate(name: str):
	frappe.delete_doc("Laundry Rate", name)
	return {"ok": True}


def _price(property: str, item_name: str, service_type: str,
           express: bool) -> float:
	row = frappe.db.get_value(
		"Laundry Rate",
		{"property": property, "item_name": item_name,
		 "service_type": service_type, "disabled": 0},
		["rate", "express_rate"], as_dict=True)
	if not row:
		frappe.throw(_("No rate for {0} ({1}) - add it to the rate card "
		              "first.").format(item_name, service_type))
	if express:
		return float(row.express_rate or 0) or round(float(row.rate) * 1.5, 0)
	return float(row.rate)


def _load_lines(property: str, items, express: bool):
	if isinstance(items, str):
		items = frappe.parse_json(items)
	lines = []
	for r in items or []:
		qty = int(r.get("qty") or 0)
		if qty <= 0:
			continue
		service = r.get("service_type") or "Wash & Iron"
		lines.append({
			"item_name": r.get("item_name"),
			"service_type": service,
			"qty": qty,
			"returned_qty": 0,
			"rate": _price(property, r.get("item_name"), service, express),
		})
	if not lines:
		frappe.throw(_("Count at least one item."))
	return lines


# ── the bag's life ───────────────────────────────────────────────────────

@frappe.whitelist(methods=["POST"])
@require_roles(*LAUNDRY_ROLES)
def request_pickup(property: str, room: str, notes: str | None = None,
                   express: int = 0):
	"""Log that a guest wants laundry picked up - it lands on the floor
	team's queue. Items are counted at the door, not here."""
	reservation = frappe.db.get_value(
		"Reservation", {"room": room, "status": "Checked In"}, "name")
	if not reservation:
		frappe.throw(_("No checked-in guest in that room."))
	doc = frappe.get_doc({
		"doctype": "Laundry Order", "property": property, "room": room,
		"reservation": reservation, "status": "Requested",
		"express": 1 if int(express or 0) else 0,
		"notes": (notes or "").strip()[:200] or None,
	})
	doc.insert()
	return {"ok": True, "order": doc.name}


@frappe.whitelist(methods=["POST"])
@require_roles(*LAUNDRY_ROLES)
def collect_laundry(property: str, room: str, items,
                    order: str | None = None, express=None,
                    notes: str | None = None):
	"""The attendant counts the bag with the guest. Prices come from the
	rate card (express uses the express column, or 1.5x). Pass `order` to
	fulfil a pickup request, or omit it to log a walk-up collection."""
	if order:
		doc = frappe.get_doc("Laundry Order", order)
		if doc.status != "Requested":
			frappe.throw(_("This pickup was already collected."))
		if express is not None:
			doc.express = 1 if int(express) else 0
	else:
		reservation = frappe.db.get_value(
			"Reservation", {"room": room, "status": "Checked In"}, "name")
		if not reservation:
			frappe.throw(_("No checked-in guest in that room."))
		doc = frappe.get_doc({
			"doctype": "Laundry Order", "property": property, "room": room,
			"reservation": reservation,
			"express": 1 if int(express or 0) else 0,
			"notes": (notes or "").strip()[:200] or None,
		})
	doc.set("items", _load_lines(doc.property, items, bool(doc.express)))
	doc.status = "Collected"
	doc.collected_by = frappe.session.user
	doc.collected_at = now_datetime()
	doc.save() if order else doc.insert()
	return {"ok": True, "order": doc.name, "total": doc.total,
	        "pieces": sum(int(i.qty) for i in doc.items)}


@frappe.whitelist(methods=["POST"])
@require_roles(*LAUNDRY_ROLES)
def laundry_status(order: str, status: str):
	"""Move the bag along: Collected -> In Process -> Ready."""
	flow = {"Collected": "In Process", "In Process": "Ready"}
	doc = frappe.get_doc("Laundry Order", order)
	if flow.get(doc.status) != status:
		frappe.throw(_("A {0} bag can't move to {1}.").format(
			doc.status, status))
	doc.status = status
	doc.save()
	return {"ok": True, "status": doc.status}


@frappe.whitelist(methods=["POST"])
@require_roles(*LAUNDRY_ROLES)
def return_items(order: str, rows):
	"""Tick items back in as they return from the laundry. rows =
	{child_row_name: returned_qty} - counts, not deltas."""
	if isinstance(rows, str):
		rows = frappe.parse_json(rows)
	doc = frappe.get_doc("Laundry Order", order)
	if doc.status in ("Delivered", "Cancelled"):
		frappe.throw(_("This laundry order is closed."))
	for it in doc.items:
		if it.name in (rows or {}):
			back = int(rows[it.name] or 0)
			if back < 0 or back > int(it.qty):
				frappe.throw(_("{0}: returned count must be between 0 and "
				              "{1}.").format(it.item_name, int(it.qty)))
			it.returned_qty = back
	doc.save()
	pending = sum(int(i.qty) - int(i.returned_qty or 0) for i in doc.items)
	return {"ok": True, "pending_pieces": pending}


@frappe.whitelist(methods=["POST"])
@require_roles(*LAUNDRY_ROLES)
def deliver_laundry(order: str, shortage_note: str | None = None):
	"""Hand the bag back and bill the stay. If pieces are still pending, a
	shortage note is required - the discrepancy is recorded, never silent.
	Posting rides the governed agent path (HK can only bill laundry)."""
	doc = frappe.get_doc("Laundry Order", order)
	if doc.status in ("Delivered", "Cancelled"):
		frappe.throw(_("This laundry order is closed."))
	if not doc.items:
		frappe.throw(_("Nothing was collected on this order."))
	pending = [(it.item_name, int(it.qty) - int(it.returned_qty or 0))
	           for it in doc.items if int(it.qty) > int(it.returned_qty or 0)]
	if pending and not (shortage_note or "").strip():
		frappe.throw(_("Still pending: {0}. Return everything, or deliver "
		              "with a shortage note.").format(
			", ".join(f"{n}×{q}" for n, q in pending)))
	doc.status = "Delivered"
	doc.delivered_by = frappe.session.user
	doc.delivered_at = now_datetime()
	if pending:
		doc.shortage_note = (shortage_note or "").strip()[:200]

	posted = False
	if doc.reservation and float(doc.total or 0) > 0:
		detail = ", ".join(
			f"{int(it.qty)}× {it.item_name} ({it.service_type})"
			for it in doc.items)
		me = frappe.session.user
		frappe.set_user("agent@kamra.local")
		try:
			from kamra.api import post_stay_charge
			post_stay_charge(
				doc.reservation, "Laundry",
				f"Laundry{' (express)' if doc.express else ''}: "
				f"{detail} ({doc.name})",
				float(doc.total), gst_rate=LAUNDRY_GST)
			posted = True
		finally:
			frappe.set_user(me)
	doc.posted_to_folio = 1 if posted else 0
	doc.save()
	if posted:
		from kamra.savings import log_action
		log_action("laundry_bill", "Laundry Order", doc.name, doc.property,
		           rationale=f"₹{doc.total:,.0f} laundry → {doc.room} "
		                     f"({doc.reservation})", channel="API")
	return {"ok": True, "status": "Delivered", "posted_to_folio": posted,
	        "total": doc.total}


@frappe.whitelist(methods=["POST"])
@require_roles(*LAUNDRY_ROLES)
def cancel_laundry(order: str, reason: str):
	if not (reason or "").strip():
		frappe.throw(_("A cancellation reason is required."))
	doc = frappe.get_doc("Laundry Order", order)
	if doc.status in ("Delivered", "Cancelled"):
		frappe.throw(_("This laundry order is closed."))
	doc.status = "Cancelled"
	doc.notes = ((f"{doc.notes}\n" if doc.notes else "")
	             + f"Cancelled: {reason.strip()[:150]}")
	doc.save()
	return {"ok": True, "status": "Cancelled"}


# ── the board ────────────────────────────────────────────────────────────

@frappe.whitelist()
@require_roles(*LAUNDRY_ROLES, "Finance")
def laundry_board(property: str):
	"""Everything the floor and the desk need at a glance: open bags by
	status with piece counts and what's still pending, plus the last few
	delivered ones for reprints/queries."""
	def rows(filters, limit=None):
		out = frappe.get_all(
			"Laundry Order", filters=filters,
			fields=["name", "room", "guest_name", "status", "express",
			        "total", "notes", "collected_at", "delivered_at",
			        "shortage_note", "posted_to_folio", "modified"],
			order_by="modified desc", limit=limit)
		for o in out:
			o["room_no"] = (o.room or "").split("-")[-1]
			items = frappe.get_all(
				"Laundry Order Item", filters={"parent": o.name},
				fields=["name", "item_name", "service_type", "qty",
				        "returned_qty", "rate", "amount"])
			o["items"] = items
			o["pieces"] = sum(int(i.qty or 0) for i in items)
			o["pending"] = sum(
				int(i.qty or 0) - int(i.returned_qty or 0) for i in items)
		return out

	return {
		"open": rows({"property": property,
		              "status": ("in", ["Requested", "Collected",
		                                "In Process", "Ready"])}),
		"recent": rows({"property": property,
		                "status": ("in", ["Delivered", "Cancelled"])},
		               limit=8),
	}
