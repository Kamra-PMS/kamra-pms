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
from frappe.utils import add_to_date, get_datetime, now_datetime

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


@frappe.whitelist(methods=["POST"])
@require_roles(*RATE_ROLES)
def import_laundry_rates(property: str, csv_text: str):
	"""Bulk-load or bulk-update the rate card from a CSV - the same file
	the Export button produces (item, service, rate, express rate).
	Upserts by (item, service): existing rows update, new rows are
	created, nothing is deleted. Headers are matched tolerantly."""
	import csv as csvmod
	import io as iomod
	import re

	def norm(h):
		return re.sub(r"[^a-z]", "", (h or "").lower())

	SERVICE_ALIASES = {
		"washiron": "Wash & Iron", "washandiron": "Wash & Iron",
		"wi": "Wash & Iron", "wash": "Wash & Iron",
		"dryclean": "Dry Clean", "dc": "Dry Clean",
		"irononly": "Iron Only", "iron": "Iron Only", "press": "Iron Only",
		"pressonly": "Iron Only",
	}
	rows = [r for r in csvmod.reader(iomod.StringIO(
		(csv_text or "").lstrip("﻿"))) if any(c.strip() for c in r)]
	if len(rows) < 2:
		frappe.throw(_("The CSV needs a header row and at least one rate."))
	headers = [norm(h) for h in rows[0]]

	def col(*names):
		for n in names:
			if n in headers:
				return headers.index(n)
		return None

	c_item = col("item", "itemname", "garment")
	c_service = col("service", "servicetype")
	c_rate = col("rate", "price")
	c_express = col("expressrate", "express", "expressprice")
	if c_item is None or c_service is None or c_rate is None:
		frappe.throw(_("Couldn't find the item / service / rate columns."))

	created = updated = 0
	issues = []
	for i, r in enumerate(rows[1:], start=1):
		get = lambda c: (r[c].strip() if c is not None and c < len(r) else "")  # noqa: E731
		item = get(c_item)
		service = SERVICE_ALIASES.get(norm(get(c_service)), get(c_service))
		rate = re.sub(r"[^0-9.]", "", get(c_rate))
		express = re.sub(r"[^0-9.]", "", get(c_express)) if c_express is not None else ""
		if not item or service not in SERVICES or not rate or float(rate) <= 0:
			issues.append({"row": i, "item": item,
			               "error": "needs an item, a valid service "
			                        "(Wash & Iron / Dry Clean / Iron Only) "
			                        "and a positive rate"})
			continue
		existing = frappe.db.get_value("Laundry Rate", {
			"property": property, "item_name": item, "service_type": service})
		save_laundry_rate(property, item, service, float(rate),
		                  express_rate=float(express) if express else None,
		                  name=existing)
		updated += 1 if existing else 0
		created += 0 if existing else 1
	return {"created": created, "updated": updated, "issues": issues}


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

def _ready_by(express: bool):
	"""Promised turnaround: same-day for express, next-day for standard,
	both by 8pm (the last laundry-room drop of the day)."""
	base = now_datetime()
	day = base if express else add_to_date(base, days=1)
	return day.replace(hour=20, minute=0, second=0, microsecond=0)


@frappe.whitelist(methods=["POST"])
@require_roles(*LAUNDRY_ROLES)
def request_pickup(property: str, room: str | None = None,
                   notes: str | None = None, express: int = 0,
                   order_type: str = "Guest", house_label: str | None = None):
	"""Log that a guest wants laundry picked up - it lands on the floor
	team's queue. Items are counted at the door, not here. A House order
	(staff uniforms / hotel linen) needs no room or guest and is never billed."""
	order_type = "House" if order_type == "House" else "Guest"
	reservation = None
	if order_type == "Guest":
		reservation = frappe.db.get_value(
			"Reservation", {"room": room, "status": "Checked In"}, "name")
		if not reservation:
			frappe.throw(_("No checked-in guest in that room."))
	doc = frappe.get_doc({
		"doctype": "Laundry Order", "property": property,
		"order_type": order_type, "room": room or None,
		"reservation": reservation, "status": "Requested",
		"express": 1 if int(express or 0) else 0,
		"house_label": (house_label or "").strip()[:80] or None,
		"notes": (notes or "").strip()[:200] or None,
	})
	doc.insert()
	return {"ok": True, "order": doc.name}


@frappe.whitelist(methods=["POST"])
@require_roles(*LAUNDRY_ROLES)
def collect_laundry(property: str, room: str | None = None, items=None,
                    order: str | None = None, express=None,
                    notes: str | None = None, order_type: str = "Guest",
                    house_label: str | None = None, complimentary=0):
	"""The attendant counts the bag with the guest. Prices come from the
	rate card (express uses the express column, or 1.5x). Pass `order` to
	fulfil a pickup request, or omit it to log a walk-up collection. A House
	walk-up (uniforms / linen) needs no room or guest and is never billed."""
	if order:
		doc = frappe.get_doc("Laundry Order", order)
		if doc.status != "Requested":
			frappe.throw(_("This pickup was already collected."))
		if express is not None:
			doc.express = 1 if int(express) else 0
	else:
		order_type = "House" if order_type == "House" else "Guest"
		reservation = None
		if order_type == "Guest":
			reservation = frappe.db.get_value(
				"Reservation", {"room": room, "status": "Checked In"}, "name")
			if not reservation:
				frappe.throw(_("No checked-in guest in that room."))
		doc = frappe.get_doc({
			"doctype": "Laundry Order", "property": property,
			"order_type": order_type, "room": room or None,
			"reservation": reservation,
			"express": 1 if int(express or 0) else 0,
			"house_label": (house_label or "").strip()[:80] or None,
			"complimentary": 1 if int(complimentary or 0) else 0,
			"notes": (notes or "").strip()[:200] or None,
		})
	doc.set("items", _load_lines(doc.property, items, bool(doc.express)))
	doc.status = "Collected"
	doc.collected_by = frappe.session.user
	doc.collected_at = now_datetime()
	doc.ready_by = _ready_by(bool(doc.express))
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
	billable = (
		(doc.order_type or "Guest") == "Guest"
		and not int(doc.complimentary or 0)
		and doc.reservation and float(doc.total or 0) > 0)
	if billable:
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
			        "shortage_note", "posted_to_folio", "modified",
			        "order_type", "complimentary", "house_label", "ready_by"],
			order_by="modified desc", limit=limit)
		now = now_datetime()
		for o in out:
			o["room_no"] = ((o.room or "").split("-")[-1]
			                or o.house_label or "House")
			o["overdue"] = bool(
				o.status in ("Collected", "In Process", "Ready")
				and o.ready_by and get_datetime(o.ready_by) < now)
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


@frappe.whitelist()
@require_roles("Finance", "Front Desk", "Hotel Admin", "Kamra Agent")
def laundry_revenue(property: str, days: int = 30):
	"""Delivered-laundry revenue over the last N days, with a per-service
	breakdown. Only billed guest orders count as revenue; House and
	complimentary bags are counted as volume but earn nothing."""
	since = add_to_date(now_datetime(), days=-int(days or 30))
	orders = frappe.get_all(
		"Laundry Order",
		filters={"property": property, "status": "Delivered",
		         "delivered_at": (">=", since)},
		fields=["name", "total", "posted_to_folio", "order_type",
		        "complimentary", "express"])
	billed = [o for o in orders if o.posted_to_folio]
	billed_names = {o.name for o in billed}
	revenue = sum(float(o.total or 0) for o in billed)

	pieces = 0
	by_service: dict[str, dict] = {}
	if orders:
		items = frappe.get_all(
			"Laundry Order Item",
			filters={"parent": ("in", [o.name for o in orders])},
			fields=["service_type", "qty", "amount", "parent"])
		for it in items:
			pieces += int(it.qty or 0)
			s = by_service.setdefault(
				it.service_type or "Other", {"pieces": 0, "revenue": 0.0})
			s["pieces"] += int(it.qty or 0)
			if it.parent in billed_names:
				s["revenue"] += float(it.amount or 0)

	return {
		"days": int(days or 30),
		"orders": len(orders),
		"billed_orders": len(billed),
		"pieces": pieces,
		"revenue": revenue,
		"express_orders": sum(1 for o in orders if o.express),
		"non_billable_orders": sum(
			1 for o in orders if o.order_type == "House" or o.complimentary),
		"by_service": [
			{"service_type": k, **v} for k, v in sorted(by_service.items())],
	}
