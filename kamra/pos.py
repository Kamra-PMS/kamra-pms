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
                 notes: str | None = None, order_type: str | None = None):
	"""Captain takes an order. If a room is given but no reservation, the
	in-house stay is resolved so it can post to the folio later."""
	property = property or frappe.db.get_value("POS Outlet", outlet, "property")
	if room and not reservation:
		reservation = frappe.db.get_value(
			"Reservation", {"room": room, "status": "Checked In"}, "name")
	lines = _load_items(items)
	if not lines:
		frappe.throw(_("Add at least one available item."))
	if order_type not in ("Dine In", "Room Service", "Takeaway"):
		order_type = "Room Service" if room else "Dine In"
	doc = frappe.get_doc({
		"doctype": "POS Order",
		"property": property,
		"outlet": outlet,
		"status": "Placed",
		"source": source,
		"order_type": order_type,
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
		fields=["name", "status", "source", "room", "table_no", "order_type",
		        "order_total", "kot_fired", "kot_no", "creation", "modified"],
		order_by="creation asc")
	for r in rows:
		r["room_no"] = (r.room or "").split("-")[-1]
		r["items"] = frappe.db.count(
			"POS Order Item", {"parent": r.name, "voided": 0})
		r["pending"] = frappe.db.count(
			"POS Order Item",
			{"parent": r.name, "kot_status": "Fired", "voided": 0})
		r["label"] = (f"Room {r['room_no']}" if r.room
		              else f"Table {r.table_no}" if r.table_no
		              else "Takeaway" if r.order_type == "Takeaway" else r.name)
	# two parties on one table (or a split bill) share a label - number them
	groups: dict[str, list] = {}
	for r in rows:
		groups.setdefault(r["label"], []).append(r)
	for label, group in groups.items():
		if len(group) > 1:
			for i, r in enumerate(group, 1):
				r["label"] = f"{label} · {i}"
	return rows


def _order_state(o) -> str:
	return ("running" if not o["kot_fired"]
	        else "fired" if o["pending"] else "ready")


@frappe.whitelist()
@require_roles(*POS_ROLES)
def table_map(outlet: str):
	"""The table view a captain starts from: every table at the outlet with
	its live state - vacant, running (open bill), fired (KOT in the kitchen)
	or ready (everything prepared, awaiting service/settle). A table holds
	any number of bills (separate parties, split bills); the tile carries
	them all and shows the most urgent state."""
	raw = frappe.db.get_value("POS Outlet", outlet, "tables") or ""
	tables = [t.strip() for t in raw.replace(",", "\n").splitlines()
	          if t.strip()]
	running = open_orders(outlet)
	by_table: dict[str, list] = {}
	for r in running:
		if r.get("table_no"):
			by_table.setdefault(r["table_no"], []).append(r)
	out = []
	for t in tables:
		orders = by_table.get(t, [])
		if not orders:
			out.append({"table": t, "state": "vacant", "bills": 0,
			            "orders": []})
			continue
		states = [_order_state(o) for o in orders]
		state = ("fired" if "fired" in states
		         else "running" if "running" in states else "ready")
		out.append({
			"table": t, "state": state, "bills": len(orders),
			"order_total": sum(o["order_total"] or 0 for o in orders),
			"orders": [{"order": o["name"], "label": o["label"],
			            "order_total": o["order_total"], "state": s}
			           for o, s in zip(orders, states)],
		})
	# tabs not shown on a tile (rooms, takeaway, ad-hoc/temp tables)
	shown = {b["order"] for t in out for b in t["orders"]}
	other = [r for r in running if r["name"] not in shown]
	return {"tables": out, "other": other}


@frappe.whitelist(methods=["POST"])
@require_roles(*POS_ROLES)
def split_order(order: str, item_rows, table_no: str | None = None):
	"""Split a bill: move the chosen lines to a new bill on the same table
	(or a named one) - separate bills for two parties sharing a table, or
	one party paying separately. Fired lines keep their kitchen status, and
	the two bills conserve the original total."""
	if isinstance(item_rows, str):
		item_rows = frappe.parse_json(item_rows)
	rows = {r for r in (item_rows or []) if r}
	if not rows:
		frappe.throw(_("Pick at least one line to move."))
	src = frappe.get_doc("POS Order", order)
	if src.status in ("Delivered", "Cancelled"):
		frappe.throw(_("This order is already closed."))
	move = [it for it in src.items if it.name in rows and not it.voided]
	if len(move) != len(rows):
		frappe.throw(_("Some lines were not found (or already voided)."))
	if not [it for it in src.items
	        if it.name not in rows and not it.voided]:
		frappe.throw(_("Every line is moving - rename the table on this "
		              "bill instead of splitting it."))
	new = frappe.get_doc({
		"doctype": "POS Order",
		"property": src.property,
		"outlet": src.outlet,
		"status": ("Preparing"
		           if any(it.kot_status != "New" for it in move)
		           else src.status),
		"source": src.source,
		"order_type": src.order_type,
		"room": src.room,
		"reservation": src.reservation,
		"table_no": table_no or src.table_no,
		"captain": frappe.session.user,
		"kot_fired": 1 if any(it.kot_status != "New" for it in move) else 0,
		"kot_no": src.kot_no,  # shared: the kitchen knows it by this ticket
		"notes": src.notes,
		"items": [{
			"menu_item": it.menu_item, "item_name": it.item_name,
			"qty": it.qty, "rate": it.rate,
			"instructions": it.instructions, "kot_status": it.kot_status,
		} for it in move],
	})
	new.insert()
	for it in move:
		src.remove(it)
	src.save()
	return {"ok": True, "new_order": new.name,
	        "source_total": src.order_total, "new_total": new.order_total}


@frappe.whitelist()
@require_roles(*POS_ROLES)
def order_detail(order: str):
	"""One order's full contents - to load a running tab back into the till."""
	doc = frappe.get_doc("POS Order", order)
	return {
		"name": doc.name, "outlet": doc.outlet, "status": doc.status,
		"source": doc.source, "room": doc.room, "table_no": doc.table_no,
		"order_type": doc.order_type, "kot_no": doc.kot_no,
		"paid": doc.paid, "payment_mode": doc.payment_mode,
		"discount_amount": doc.discount_amount, "discount_reason": doc.discount_reason,
		"subtotal": doc.subtotal, "order_total": doc.order_total,
		"kot_fired": doc.kot_fired, "notes": doc.notes,
		"items": [
			{"row": it.name, "menu_item": it.menu_item, "item_name": it.item_name,
			 "qty": it.qty, "rate": it.rate, "amount": it.amount,
			 "instructions": it.instructions, "kot_status": it.kot_status,
			 "voided": it.voided, "void_reason": it.void_reason}
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
	kitchen display. Stamps the KOT number (a daily sequence per outlet) and
	returns just-fired lines so the till can print the thermal KOT ticket."""
	doc = frappe.get_doc("POS Order", order)
	fired = []
	for it in doc.items:
		if it.kot_status == "New" and not it.voided:
			it.kot_status = "Fired"
			fired.append({"item_name": it.item_name, "qty": it.qty,
			              "instructions": it.instructions})
	if not doc.kot_no:
		last = frappe.db.sql(
			"""select max(kot_no) from `tabPOS Order`
			   where outlet=%s and date(creation)=date(now())""",
			doc.outlet)[0][0] or 0
		doc.kot_no = int(last) + 1
	doc.kot_fired = 1
	if doc.status in ("Placed", "Confirmed"):
		doc.status = "Preparing"
	doc.save()
	return {"ok": True, "status": doc.status, "kot_no": doc.kot_no,
	        "fired_items": fired}


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
			        "menu_item", "voided"])
		pending = [i for i in items if i.kot_status == "Fired" and not i.voided]
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


@frappe.whitelist(methods=["POST"])
@require_roles(*POS_ROLES)
def pay_order(order: str, mode: str):
	"""Settle a bill at the outlet (walk-ins, takeaway - or a guest who'd
	rather pay now than post to the room). Records the payment mode and
	closes the order without touching any folio."""
	if mode not in ("Cash", "Card", "UPI"):
		frappe.throw(_("Pick a payment mode: Cash, Card or UPI."))
	doc = frappe.get_doc("POS Order", order)
	if doc.status == "Cancelled":
		frappe.throw(_("This order was cancelled."))
	if doc.posted_to_folio:
		frappe.throw(_("Already posted to the room folio - settle it there."))
	if doc.paid:
		frappe.throw(_("Already paid."))
	doc.paid = 1
	doc.payment_mode = mode
	doc.status = "Delivered"
	doc.save()
	return {"ok": True, "status": "Delivered", "paid": True, "mode": mode,
	        "order_total": doc.order_total}


@frappe.whitelist(methods=["POST"])
@require_roles(*POS_ROLES)
def cancel_order(order: str, reason: str):
	"""Cancel a running order - needs a reason (it's kept on the order for
	the audit trail). Closed orders can't be cancelled."""
	if not (reason or "").strip():
		frappe.throw(_("A cancellation reason is required."))
	doc = frappe.get_doc("POS Order", order)
	if doc.status in ("Delivered", "Cancelled"):
		frappe.throw(_("This order is already closed."))
	doc.status = "Cancelled"
	doc.notes = (f"{doc.notes}\n" if doc.notes else "") + f"Cancelled: {reason}"
	doc.save()
	return {"ok": True, "status": "Cancelled"}


@frappe.whitelist(methods=["POST"])
@require_roles(*POS_ROLES)
def void_item(order: str, item_row: str, reason: str):
	"""Void one line with a reason - the line stays on the order (struck
	through, amount zero) so the KOT-vs-bill audit holds up."""
	if not (reason or "").strip():
		frappe.throw(_("A void reason is required."))
	doc = frappe.get_doc("POS Order", order)
	if doc.status in ("Delivered", "Cancelled"):
		frappe.throw(_("This order is already closed."))
	target = next((it for it in doc.items if it.name == item_row), None)
	if not target:
		frappe.throw(_("Order line not found."))
	target.voided = 1
	target.void_reason = reason.strip()[:140]
	doc.save()
	return {"ok": True, "order_total": doc.order_total,
	        "subtotal": doc.subtotal}


@frappe.whitelist()
@require_roles(*POS_ROLES)
def bill_data(order: str):
	"""Everything the thermal bill print needs: outlet and property names,
	live lines, the discount, and the CGST/SGST split at the outlet's rate."""
	doc = frappe.get_doc("POS Order", order)
	outlet = frappe.db.get_value(
		"POS Outlet", doc.outlet, ["outlet_name", "gst_rate"], as_dict=True)
	property_name = frappe.db.get_value(
		"Property", doc.property, "property_name") or doc.property
	gst_rate = float(outlet.gst_rate or 5)
	taxable = float(doc.order_total or 0)
	gst_amount = round(taxable * gst_rate / 100, 2)
	return {
		"order": doc.name, "kot_no": doc.kot_no, "status": doc.status,
		"property_name": property_name, "outlet_name": outlet.outlet_name,
		"order_type": doc.order_type, "table_no": doc.table_no,
		"room_no": (doc.room or "").split("-")[-1] if doc.room else None,
		"captain": doc.captain, "created": str(doc.creation),
		"items": [
			{"item_name": it.item_name, "qty": it.qty, "rate": it.rate,
			 "amount": it.amount}
			for it in doc.items if not it.voided],
		"subtotal": doc.subtotal, "discount_amount": doc.discount_amount,
		"taxable": taxable, "gst_rate": gst_rate,
		"cgst": round(gst_amount / 2, 2), "sgst": round(gst_amount / 2, 2),
		"grand_total": round(taxable + gst_amount, 2),
		"paid": doc.paid, "payment_mode": doc.payment_mode,
	}
