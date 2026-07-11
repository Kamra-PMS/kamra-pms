"""Restaurant POS - digital menu, captain ordering, KOT to the kitchen,
and room posting.

Flow: a captain (or a guest via QR) places an order -> the captain confirms
it -> firing the KOT sends it to the kitchen display -> the kitchen marks
items prepared -> delivering the order posts it to the guest's room folio
(handled by the POS Order controller) or it's settled at the outlet.
"""

import frappe
from frappe import _

from kamra.authz import require_roles

POS_ROLES = ("Front Desk", "Finance", "Kamra Agent")


@frappe.whitelist()
@require_roles(*POS_ROLES)
def outlets(property: str):
	return frappe.get_all(
		"POS Outlet", filters={"property": property, "disabled": 0},
		fields=["name", "outlet_name", "outlet_type", "gst_rate"],
		order_by="outlet_name")


@frappe.whitelist()
@require_roles(*POS_ROLES)
def pos_menu(outlet: str):
	"""The digital menu for an outlet: available items grouped by category."""
	items = frappe.get_all(
		"Menu Item",
		filters={"outlet": outlet, "available": 1},
		fields=["name", "item_name", "category", "price", "is_veg",
		        "is_alcohol", "image", "description", "prep_station"],
		order_by="category, item_name")
	cats: dict[str, list] = {}
	for it in items:
		cats.setdefault(it.category or "Other", []).append(it)
	return {"outlet": outlet,
	        "categories": [{"category": c, "items": v} for c, v in cats.items()]}


def _load_items(rows):
	"""Normalise incoming order lines and price them from the menu (the
	guest/caller never sets the price - only qty and instructions)."""
	if isinstance(rows, str):
		rows = frappe.parse_json(rows)
	out = []
	for r in rows or []:
		mi = frappe.db.get_value(
			"Menu Item", r.get("menu_item"),
			["item_name", "price", "available"], as_dict=True)
		if not mi or not mi.available:
			continue
		out.append({
			"menu_item": r["menu_item"],
			"item_name": mi.item_name,
			"qty": max(1, float(r.get("qty") or 1)),
			"rate": float(mi.price or 0),
			"instructions": (r.get("instructions") or "")[:140] or None,
			"kot_status": "New",
		})
	return out


@frappe.whitelist(methods=["POST"])
@require_roles(*POS_ROLES)
def create_order(outlet: str, items, property: str | None = None,
                 room: str | None = None, reservation: str | None = None,
                 table_no: str | None = None, source: str = "Manual",
                 notes: str | None = None):
	"""Captain takes an order. If a room is given but no reservation, the
	in-house stay is resolved so it can post to the folio later."""
	property = property or frappe.db.get_value("POS Outlet", outlet, "property")
	if room and not reservation:
		reservation = frappe.db.get_value(
			"Reservation", {"room": room, "status": "Checked In"}, "name")
	lines = _load_items(items)
	if not lines:
		frappe.throw(_("Add at least one available item."))
	doc = frappe.get_doc({
		"doctype": "POS Order",
		"property": property,
		"outlet": outlet,
		"status": "Placed",
		"source": source,
		"room": room or None,
		"reservation": reservation or None,
		"table_no": table_no or None,
		"captain": frappe.session.user if source != "QR" else None,
		"notes": notes or None,
		"items": lines,
	})
	doc.insert()
	return {"ok": True, "order": doc.name, "order_total": doc.order_total,
	        "status": doc.status}


@frappe.whitelist()
@require_roles(*POS_ROLES)
def open_orders(outlet: str):
	"""Every running tab at an outlet - the tables/rooms being served right
	now, so a captain can juggle several at once."""
	rows = frappe.get_all(
		"POS Order",
		filters={"outlet": outlet,
		         "status": ("in", ["Placed", "Confirmed", "Preparing"])},
		fields=["name", "status", "source", "room", "table_no",
		        "order_total", "kot_fired", "modified"],
		order_by="creation asc")
	for r in rows:
		r["room_no"] = (r.room or "").split("-")[-1]
		r["items"] = frappe.db.count("POS Order Item", {"parent": r.name})
		r["label"] = (f"Room {r['room_no']}" if r.room
		              else f"Table {r.table_no}" if r.table_no else r.name)
	return rows


@frappe.whitelist()
@require_roles(*POS_ROLES)
def order_detail(order: str):
	"""One order's full contents - to load a running tab back into the till."""
	doc = frappe.get_doc("POS Order", order)
	return {
		"name": doc.name, "outlet": doc.outlet, "status": doc.status,
		"source": doc.source, "room": doc.room, "table_no": doc.table_no,
		"discount_amount": doc.discount_amount, "discount_reason": doc.discount_reason,
		"subtotal": doc.subtotal, "order_total": doc.order_total,
		"kot_fired": doc.kot_fired, "notes": doc.notes,
		"items": [
			{"row": it.name, "menu_item": it.menu_item, "item_name": it.item_name,
			 "qty": it.qty, "rate": it.rate, "amount": it.amount,
			 "instructions": it.instructions, "kot_status": it.kot_status}
			for it in doc.items],
	}


@frappe.whitelist(methods=["POST"])
@require_roles(*POS_ROLES)
def add_items(order: str, items):
	"""Add rounds to a running tab - new lines are priced from the menu and
	start as New (a later fire_kot sends them to the kitchen)."""
	doc = frappe.get_doc("POS Order", order)
	if doc.status in ("Delivered", "Cancelled"):
		frappe.throw(_("This order is already closed."))
	for line in _load_items(items):
		doc.append("items", line)
	doc.save()
	return {"ok": True, "order_total": doc.order_total}


@frappe.whitelist(methods=["POST"])
@require_roles(*POS_ROLES)
def confirm_order(order: str):
	"""Captain confirmation - a guest's QR order isn't fired to the kitchen
	until a captain has vetted it."""
	doc = frappe.get_doc("POS Order", order)
	doc.status = "Confirmed"
	if not doc.captain:
		doc.captain = frappe.session.user
	doc.save()
	return {"ok": True, "status": "Confirmed"}


@frappe.whitelist(methods=["POST"])
@require_roles(*POS_ROLES)
def apply_discount(order: str, amount: float, reason: str = ""):
	"""The guest-discount popup - a captain grants a discount with a reason."""
	doc = frappe.get_doc("POS Order", order)
	doc.discount_amount = float(amount or 0)
	doc.discount_reason = reason or None
	doc.save()
	return {"ok": True, "discount": doc.discount_amount,
	        "order_total": doc.order_total}


@frappe.whitelist(methods=["POST"])
@require_roles(*POS_ROLES)
def fire_kot(order: str):
	"""Send the order to the kitchen: new lines become Fired and show on the
	kitchen display."""
	doc = frappe.get_doc("POS Order", order)
	for it in doc.items:
		if it.kot_status == "New":
			it.kot_status = "Fired"
	doc.kot_fired = 1
	if doc.status in ("Placed", "Confirmed"):
		doc.status = "Preparing"
	doc.save()
	return {"ok": True, "status": doc.status}


@frappe.whitelist()
@require_roles(*POS_ROLES)
def kitchen_queue(property: str, outlet: str | None = None,
                  station: str | None = None):
	"""The kitchen display: fired orders with items still to prepare. Scope
	to one outlet (each restaurant's own kitchen) and/or one station."""
	filters = {"property": property, "status": "Preparing", "kot_fired": 1}
	if outlet:
		filters["outlet"] = outlet
	orders = frappe.get_all(
		"POS Order", filters=filters,
		fields=["name", "outlet", "room", "table_no", "creation", "notes"],
		order_by="creation asc")
	out = []
	for o in orders:
		items = frappe.get_all(
			"POS Order Item", filters={"parent": o.name},
			fields=["name", "item_name", "qty", "instructions", "kot_status",
			        "menu_item"])
		pending = [i for i in items if i.kot_status == "Fired"]
		if station:
			pending = [
				i for i in pending
				if frappe.db.get_value("Menu Item", i.menu_item, "prep_station")
				== station]
		if not pending:
			continue
		o["outlet_name"] = frappe.db.get_value("POS Outlet", o.outlet, "outlet_name")
		o["room_no"] = (o.room or "").split("-")[-1]
		o["items"] = pending
		out.append(o)
	return out


@frappe.whitelist(methods=["POST"])
@require_roles(*POS_ROLES)
def mark_prepared(order: str, item_row: str | None = None):
	"""Kitchen marks one line (or the whole order) prepared."""
	doc = frappe.get_doc("POS Order", order)
	for it in doc.items:
		if (item_row and it.name == item_row) or (not item_row and it.kot_status == "Fired"):
			it.kot_status = "Prepared"
	doc.save()
	all_done = all(it.kot_status == "Prepared" for it in doc.items)
	return {"ok": True, "all_prepared": all_done}


@frappe.whitelist(methods=["POST"])
@require_roles(*POS_ROLES)
def deliver_order(order: str):
	"""Order served - moves to Delivered, which posts it to the room folio
	(controller) when there's a linked stay."""
	doc = frappe.get_doc("POS Order", order)
	doc.status = "Delivered"
	doc.save()
	return {"ok": True, "status": "Delivered",
	        "posted_to_folio": bool(doc.posted_to_folio)}
