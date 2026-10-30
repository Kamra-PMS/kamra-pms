"""Restaurant POS - digital menu, captain ordering, KOT to the kitchen,
and room posting.

Flow: a captain places an order -> confirm / fire KOT sends it to the
kitchen display -> the kitchen marks items prepared -> delivering the
order posts it to the guest's room folio (handled by the POS Order
controller) or it's settled at the outlet.

Auto KOT is an F&B setting (`pos_auto_kot`) that an outlet can override
with its `kot_mode`. When it's on, firing also accepts the ticket, so the
kitchen display shows it as started, and the till prints the slip without
a separate Start or a per-browser printer switch.
"""

import re

import frappe
from frappe import _
from frappe.utils import cint

from kamra.authz import assert_record_access, require_perm

POS_ROLES = ("Front Desk", "Finance", "Kamra Agent")
# Menus written before coursing existed have no course; they behave as mains.
DEFAULT_COURSE = "Main"
COURSE_ORDER = ("Starter", "Main", "Dessert", "Drink")


def _course_order(property: str | None = None) -> list[str]:
	"""Serving order for held courses - property list when set, else default."""
	from kamra.settings import list_setting
	custom = list_setting(property, "menu_courses") if property else []
	return custom or list(COURSE_ORDER)
# a bill still being served: not paid, posted, made NC or cancelled
OPEN_STATUSES = ("Placed", "Confirmed", "Preparing")


def _unfired_alert_min(outlet: str) -> int:
	from kamra.settings import get_setting
	prop = frappe.db.get_value("POS Outlet", outlet, "property")
	return max(1, cint(get_setting(prop, "pos_unfired_alert_min") or 15))


@frappe.whitelist()
@require_perm("POS Order", "take_orders")
def outlets(property: str):
	"""Open outlets, each with `auto_kot` already resolved against the F&B
	setting, so the till never has to know where the answer came from."""
	rows = frappe.get_all(
		"POS Outlet", filters={"property": property, "disabled": 0},
		fields=["name", "outlet_name", "outlet_type", "gst_rate", "kot_mode"],
		order_by="outlet_name")
	for r in rows:
		r["auto_kot"] = 1 if _auto_kot(property, r.kot_mode) else 0
	return rows


def _auto_kot(property: str, kot_mode: str | None) -> bool:
	"""Does sending an order accept and print the KOT? The outlet's own
	choice wins; "Use F&B setting" (or blank) falls back to the property."""
	if kot_mode == "Auto-accept and print":
		return True
	if kot_mode == "Kitchen presses Start":
		return False
	from kamra.settings import get_setting
	return bool(get_setting(property, "pos_auto_kot"))


def outlet_auto_kot(outlet: str) -> bool:
	prop, mode = frappe.db.get_value("POS Outlet", outlet, ["property", "kot_mode"]) or (None, None)
	return _auto_kot(prop, mode)


@frappe.whitelist()
@require_perm("POS Order", "take_orders")
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


def _courses_of(doc) -> dict:
	"""menu_item -> course, for every line on the order. A menu that predates
	coursing has no course set; treat it as a main so it fires with everything
	else rather than being silently held back forever."""
	ids = list({it.menu_item for it in doc.items if it.menu_item})
	if not ids:
		return {}
	return {m.name: (m.course or DEFAULT_COURSE) for m in frappe.get_all(
		"Menu Item", filters={"name": ["in", ids]}, fields=["name", "course"])}


def _allergy_hits(allergy_note: str | None, allergens: str | None) -> list:
	"""Which of a dish's allergens the guest actually declared. Loose on
	purpose: the captain types "nut allergy" and the menu says "Nuts", and
	the line must still light up. Matching is a guard, never a guarantee -
	the guest note is always shown in full alongside it."""
	if not (allergy_note or "").strip() or not (allergens or "").strip():
		return []
	note = allergy_note.lower()
	hits = []
	for a in (x.strip() for x in allergens.split(",")):
		if a and a.lower().rstrip("s") in note:
			hits.append(a)
	return hits


def _in_house_stay(property: str, room: str | None,
                   reservation: str | None) -> tuple[str | None, str | None]:
	"""(room, reservation) for a bill charged to a room, checked against a
	stay that is in house now. Both None when the bill isn't for a room."""
	if not (room or reservation):
		return None, None
	if reservation:
		res = frappe.db.get_value(
			"Reservation", reservation, ["status", "room", "property"],
			as_dict=True)
		if not res or res.status != "Checked In" or res.property != property:
			frappe.throw(_("That stay is not checked in here - a bill can "
			              "only be charged to an in-house guest."))
		if room and res.room and room != res.room:
			frappe.throw(_("That guest is not staying in this room."))
		assert_room_charges_allowed(reservation)
		return room or res.room, reservation
	reservation = frappe.db.get_value(
		"Reservation", {"room": room, "status": "Checked In",
		                "property": property}, "name")
	if not reservation:
		number = frappe.db.get_value("Room", room, "room_number") or room
		frappe.throw(_("Room {0} has no checked-in guest. Room charges need "
		              "an in-house stay - take this as a walk-in bill "
		              "instead.").format(number))
	assert_room_charges_allowed(reservation)
	return room, reservation


class RoomChargesBlocked(frappe.ValidationError):
	"""The desk blocked charges to this room at check-in."""


def assert_room_charges_allowed(reservation: str) -> None:
	"""The check-in's room-charges decision, enforced wherever an outlet,
	laundry or the minibar would post to the room (internal POS, the
	external POS interface, laundry, housekeeping consumables)."""
	allowed, room = frappe.db.get_value(
		"Reservation", reservation, ["room_charges_allowed", "room"]) or (1, None)
	if allowed is None or cint(allowed):
		return
	number = (frappe.db.get_value("Room", room, "room_number") if room else None) or room or ""
	frappe.throw(
		_("Room {0} cannot take charges to the room (set at check-in). "
		  "Take payment at the outlet, or ask the front desk.").format(number),
		exc=RoomChargesBlocked, title=_("Room charges blocked"))


@frappe.whitelist()
@require_perm("POS Order", "take_orders")
def in_house_rooms(property: str):
	"""Rooms with a checked-in guest, for the till's room picker: only these
	can take a room charge. "101 · Guest Name". `room_charges_allowed` is the
	check-in's decision; a blocked room is shown but cannot be charged."""
	from kamra.crs import assert_property_access
	assert_property_access(property)
	rows = frappe.get_all(
		"Reservation",
		filters={"property": property, "status": "Checked In",
		         "room": ["is", "set"]},
		fields=["name as reservation", "room", "guest_name",
		        "room_charges_allowed", "check_out_date"])
	for r in rows:
		r["room_charges_allowed"] = 0 if r.room_charges_allowed is not None \
			and not cint(r.room_charges_allowed) else 1
		r["check_out_date"] = str(r.check_out_date or "")
	numbers = dict(frappe.get_all(
		"Room", filters={"name": ["in", [r.room for r in rows] or [""]]},
		fields=["name", "room_number"], as_list=True))
	for r in rows:
		r["room_number"] = numbers.get(r.room) or r.room.split("-")[-1]
	rows.sort(key=lambda r: (len(str(r.room_number)), str(r.room_number)))
	return rows


@frappe.whitelist(methods=["POST"])
@require_perm("POS Order", "take_orders")
def charge_to_room(order: str, room: str):
	"""Point a running bill (a dine-in table, say) at an in-house guest's
	room, so Deliver posts it to their folio through the same controller
	path as room service - billing rules and the alcohol rule included."""
	doc = frappe.get_doc("POS Order", order)
	if doc.status in ("Delivered", "Cancelled"):
		frappe.throw(_("This order is already closed."))
	if doc.paid:
		frappe.throw(_("Already paid."))
	doc.room, doc.reservation = _in_house_stay(doc.property, room, None)
	doc.guest = _bill_guest(doc.reservation, None)
	doc.save()
	return {"ok": True, "room": doc.room, "reservation": doc.reservation}


@frappe.whitelist(methods=["POST"])
@require_perm("POS Order", "take_orders")
def create_order(outlet: str, items, property: str | None = None,
                 room: str | None = None, reservation: str | None = None,
                 table_no: str | None = None, source: str = "Manual",
                 notes: str | None = None, order_type: str | None = None,
                 guests=None, customer_name: str | None = None,
                 customer_phone: str | None = None,
                 delivery_address: str | None = None,
                 allergy_note: str | None = None, guest: str | None = None):
	"""Captain takes an order. A room (room service, or a dine-in guest
	charging to their room) must have a checked-in stay: it is resolved now
	so the bill posts to that folio on delivery. A room with nobody in house
	is refused - take it as a walk-in bill instead. Takeaway and delivery
	carry the customer's details instead of a table/room. `guest` ties the
	bill to a guest profile (a walk-in found or added with find_customer or
	attach_customer); a room bill takes the in-house guest by itself."""
	doc = _build_order(outlet, items, property, room, reservation, table_no,
	                   source, notes, order_type, guests, customer_name,
	                   customer_phone, delivery_address, allergy_note, guest)
	doc.insert()
	return {"ok": True, "order": doc.name, "order_total": doc.order_total,
	        "status": doc.status}


def _build_order(outlet, items, property=None, room=None, reservation=None,
                 table_no=None, source="Manual", notes=None, order_type=None,
                 guests=None, customer_name=None, customer_phone=None,
                 delivery_address=None, allergy_note=None, guest=None):
	"""A new, unsaved POS Order with its lines priced from the menu."""
	property = property or frappe.db.get_value("POS Outlet", outlet, "property")
	room, reservation = _in_house_stay(property, room, reservation)
	lines = _load_items(items)
	if not lines:
		frappe.throw(_("Add at least one available item."))
	if order_type not in ("Dine In", "Room Service", "Takeaway", "Delivery"):
		order_type = "Room Service" if room else "Dine In"
	if order_type == "Delivery" and not (customer_phone or customer_name):
		frappe.throw(_("Delivery needs the customer's name or phone."))
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
		"guests": int(guests) if guests else None,
		"customer_name": (customer_name or "").strip() or None,
		"customer_phone": (customer_phone or "").strip() or None,
		"delivery_address": (delivery_address or "").strip() or None,
		"captain": frappe.session.user if source != "QR" else None,
		"notes": notes or None,
		"allergy_note": (allergy_note or "").strip() or None,
		"guest": _bill_guest(reservation, guest),
		"items": lines,
	})
	if doc.guest and not doc.customer_name and not reservation:
		doc.customer_name = frappe.db.get_value("Guest", doc.guest, "full_name")
	return doc


def _bill_guest(reservation: str | None, guest: str | None) -> str | None:
	"""Who a bill is for: the in-house guest of a room bill, otherwise the
	walk-in profile the captain attached. Never a guest the caller cannot
	see."""
	if reservation:
		return frappe.db.get_value("Reservation", reservation, "guest")
	if not guest:
		return None
	if not frappe.db.exists("Guest", guest):
		frappe.throw(_("That guest profile was not found."))
	from kamra.authz import assert_guest_access
	assert_guest_access(guest)
	return guest


@frappe.whitelist()
@require_perm("POS Order", "take_orders")
def open_orders(outlet: str):
	"""Every running tab at an outlet - the tables/rooms being served right
	now, so a captain can juggle several at once. A bill nobody has sent to
	the kitchen carries its age in minutes and turns `stale` after the F&B
	setting's limit, so a forgotten order is sent or cancelled."""
	rows = frappe.get_all(
		"POS Order",
		filters={"outlet": outlet,
		         "status": ("in", list(OPEN_STATUSES))},
		fields=["name", "status", "source", "room", "table_no", "order_type",
		        "order_total", "kot_fired", "kot_no", "guests",
		        "customer_name", "creation", "modified"],
		order_by="creation asc")
	stale_after = _unfired_alert_min(outlet) if rows else 0
	now = frappe.utils.now_datetime()
	for r in rows:
		r["age_min"] = int((now - frappe.utils.get_datetime(r.creation)).total_seconds() // 60)
		r["stale"] = 1 if not r.kot_fired and r["age_min"] >= stale_after else 0
		r["room_no"] = (r.room or "").split("-")[-1]
		r["items"] = frappe.db.count(
			"POS Order Item", {"parent": r.name, "voided": 0})
		r["pending"] = frappe.db.count(
			"POS Order Item",
			{"parent": r.name, "kot_status": "Fired", "voided": 0})
		r["label"] = _label(r)
	# two parties on one table (or a split bill) share a label - number them
	groups: dict[str, list] = {}
	for r in rows:
		groups.setdefault(r["label"], []).append(r)
	for label, group in groups.items():
		if len(group) > 1:
			for i, r in enumerate(group, 1):
				r["label"] = f"{label} · {i}"
	return rows


def _kot_tickets_of(doc) -> list:
	raw = getattr(doc, "last_kot_ticket", None)
	data = frappe.parse_json(raw) if raw else []
	return data if isinstance(data, list) else []


def _label(r) -> str:
	"""A human tag for a bill: where it is, or who it's for."""
	if r.get("table_no") and r.get("order_type") == "Dine In":
		return f"Table {r['table_no']}"
	if r.get("room"):
		return f"Room {(r['room'] or '').split('-')[-1]}"
	if r.get("table_no"):
		return f"Table {r['table_no']}"
	who = (r.get("customer_name") or "").split(" ")[0]
	if r.get("order_type") in ("Takeaway", "Delivery"):
		return f"{r['order_type']} · {who}" if who else r["order_type"]
	return r["name"]


def _order_state(o) -> str:
	return ("running" if not o["kot_fired"]
	        else "fired" if o["pending"] else "ready")


def _cleaning_key(outlet: str, table_no: str) -> str:
	return f"kamra_pos_cleaning|{outlet}|{table_no}"


def _flag_cleaning_if_freed(doc):
	"""When the last bill on a dine-in table closes, flag the table for
	cleaning (auto-clears after 30 minutes, or on Mark clean)."""
	if not doc.table_no or doc.order_type != "Dine In":
		return
	still_open = frappe.db.count("POS Order", {
		"outlet": doc.outlet, "table_no": doc.table_no,
		"status": ("in", ["Placed", "Confirmed", "Preparing"])})
	if not still_open:
		frappe.cache.set_value(_cleaning_key(doc.outlet, doc.table_no), "1",
		                       expires_in_sec=30 * 60)


def _upcoming_reservations(outlet: str):
	"""Booked reservations inside the window in which a table should read
	as Reserved on the map - by default an hour ago to four hours out
	(Settings -> F&B)."""
	from frappe.utils import add_to_date, now_datetime
	from kamra.settings import get_setting
	prop = frappe.db.get_value("POS Outlet", outlet, "property")
	before = int(get_setting(prop, "pos_reservation_before_min"))
	after = int(get_setting(prop, "pos_reservation_after_min"))
	now = now_datetime()
	return frappe.get_all(
		"POS Table Reservation",
		filters={"outlet": outlet, "status": "Booked",
		         "reserved_at": ("between", [add_to_date(now, minutes=-before),
		                                     add_to_date(now, minutes=after)])},
		fields=["name", "table_no", "guest_name", "phone", "party_size",
		        "reserved_at", "notes"],
		order_by="reserved_at asc")


def _parse_tables(raw: str) -> list[tuple[str, int | None, str | None]]:
	"""An outlet's table list: "[Main Hall]" starts an area; "T1:4" = table
	T1 with 4 seats; plain "T1" works too."""
	tables = []
	area = None
	for line in (raw or "").replace(",", "\n").splitlines():
		line = line.strip()
		if not line:
			continue
		if line.startswith("[") and line.endswith("]"):
			area = line[1:-1].strip() or None
			continue
		name, _sep, seats = line.partition(":")
		tables.append((name.strip(),
		               int(seats) if seats.strip().isdigit() else None, area))
	return tables


@frappe.whitelist()
@require_perm("POS Order", "take_orders")
def table_map(outlet: str):
	"""The table view a captain starts from: every table at the outlet with
	its live state - vacant, running (open bill), fired (KOT in the kitchen)
	or ready (everything prepared, awaiting service/settle). A table holds
	any number of bills (separate parties, split bills); the tile carries
	them all and shows the most urgent state."""
	tables = _parse_tables(
		frappe.db.get_value("POS Outlet", outlet, "tables") or "")
	running = open_orders(outlet)
	by_table: dict[str, list] = {}
	for r in running:
		if r.get("table_no"):
			by_table.setdefault(r["table_no"], []).append(r)

	reserved = {}
	for r in _upcoming_reservations(outlet):
		reserved.setdefault(r.table_no, {
			"reservation": r.name, "res_guest": r.guest_name,
			"res_party": r.party_size, "res_phone": r.phone,
			"res_time": frappe.utils.get_datetime(r.reserved_at).strftime("%H:%M"),
		})

	def tile(t, seats, area, temp=False):
		orders = by_table.get(t, [])
		base = {"table": t, "seats": seats, "area": area, "temp": temp,
		        **reserved.get(t, {})}
		if not orders:
			# an empty table can still be reserved or waiting on a clean
			state = ("reserved" if t in reserved
			         else "cleaning"
			         if frappe.cache.get_value(_cleaning_key(outlet, t))
			         else "vacant")
			return {**base, "state": state, "bills": 0, "orders": []}
		states = [_order_state(o) for o in orders]
		state = ("fired" if "fired" in states
		         else "running" if "running" in states else "ready")
		return {
			**base, "state": state, "bills": len(orders),
			"order_total": sum(o["order_total"] or 0 for o in orders),
			"guests": sum(o.get("guests") or 0 for o in orders) or None,
			"since": str(min(o["creation"] for o in orders)),
			"orders": [{"order": o["name"], "label": o["label"],
			            "order_total": o["order_total"], "state": s}
			           for o, s in zip(orders, states, strict=True)],
		}

	out = [tile(t, seats, a) for t, seats, a in tables]
	# ad-hoc/temp tables (a named table outside the layout) get live tiles
	# too, so a parked "Patio X" bill stays visible
	configured = {t for t, _s, _a in tables}
	for t in sorted(t for t in by_table if t not in configured):
		out.append(tile(t, None, "Temp", temp=True))
	# tabs not on any tile (rooms, takeaway, delivery)
	shown = {b["order"] for t in out for b in t["orders"]}
	other = [r for r in running if r["name"] not in shown]
	return {"tables": out, "other": other}


@frappe.whitelist(methods=["POST"])
@require_perm("POS Order", "take_orders")
def reserve_table(outlet: str, table_no: str, guest_name: str,
                  reserved_at: str, phone: str | None = None,
                  party_size=None, notes: str | None = None):
	"""Reserve a table - it shows as Reserved on the map from an hour
	before the time until it's seated, cancelled or marked a no-show."""
	if not (guest_name or "").strip():
		frappe.throw(_("Whose reservation is it?"))
	doc = frappe.get_doc({
		"doctype": "POS Table Reservation",
		"outlet": outlet,
		"table_no": (table_no or "").strip(),
		"guest_name": guest_name.strip()[:100],
		"phone": (phone or "").strip() or None,
		"party_size": int(party_size) if party_size else None,
		"reserved_at": reserved_at,
		"notes": (notes or "").strip()[:200] or None,
	})
	doc.insert()
	return {"ok": True, "reservation": doc.name}


@frappe.whitelist(methods=["POST"])
@require_perm("POS Order", "take_orders")
def set_reservation(reservation: str, status: str):
	"""Seat / cancel / no-show a table reservation."""
	if status not in ("Seated", "Cancelled", "No Show"):
		frappe.throw(_("Status must be Seated, Cancelled or No Show."))
	doc = frappe.get_doc("POS Table Reservation", reservation)
	doc.status = status
	doc.save()
	return {"ok": True, "status": status}


@frappe.whitelist(methods=["POST"])
@require_perm("POS Order", "take_orders")
def mark_table_clean(outlet: str, table_no: str):
	"""Housekeeping done - the table goes back to vacant on the map."""
	frappe.cache.delete_value(_cleaning_key(outlet, table_no))
	return {"ok": True}


@frappe.whitelist()
@require_perm("POS Order", "take_orders")
def recent_orders(outlet: str, limit: int = 8):
	"""The outlet's latest bills, newest first - open or settled - so a
	captain can jump back to a running bill or reprint a settled one."""
	rows = frappe.get_all(
		"POS Order", filters={"outlet": outlet},
		fields=["name", "status", "order_type", "room", "table_no",
		        "customer_name", "order_total", "paid", "payment_mode",
		        "nc", "creation", "modified"],
		order_by="modified desc", limit=min(int(limit or 8), 25))
	for r in rows:
		r["label"] = _label(r)
		r["open"] = r.status in ("Placed", "Confirmed", "Preparing")
	return rows


@frappe.whitelist(methods=["POST"])
@require_perm("POS Order", "take_orders")
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
		"customer_name": src.customer_name,
		"customer_phone": src.customer_phone,
		"delivery_address": src.delivery_address,
		"nc": src.nc, "nc_authorized_by": src.nc_authorized_by,
		"nc_note": src.nc_note,
		"table_no": table_no or src.table_no,
		"captain": frappe.session.user,
		"kot_fired": 1 if any(it.kot_status != "New" for it in move) else 0,
		"kot_no": src.kot_no,  # shared: the kitchen knows it by this ticket
		"notes": src.notes,
		"items": [{
			"menu_item": it.menu_item, "item_name": it.item_name,
			"qty": it.qty, "rate": it.rate,
			"instructions": it.instructions, "kot_status": it.kot_status,
			# a split moves food that is already cooked and already deducted;
			# carrying the flag is what stops the new bill deducting it twice
			"stock_posted": it.stock_posted,
		} for it in move],
	})
	new.insert()
	for it in move:
		src.remove(it)
	src.save()
	return {"ok": True, "new_order": new.name,
	        "source_total": src.order_total, "new_total": new.order_total}


@frappe.whitelist()
@require_perm("POS Order", "take_orders")
def order_detail(order: str):
	"""One order's full contents - to load a running tab back into the till,
	or to look at a closed one from the orders list. `kitchen_lines` counts
	the live lines the kitchen already has: while it is zero the captain can
	cancel the bill alone; after that a supervisor approves."""
	from kamra.authz import is_supervisor
	doc = frappe.get_doc("POS Order", order)
	return {
		"state": _order_list_state(doc),
		"creation": str(doc.creation), "guest": doc.guest,
		"reservation": doc.reservation, "allergy_note": doc.allergy_note,
		"posted_to_folio": doc.posted_to_folio,
		"cancel_reason": doc.cancel_reason, "cancelled_by": doc.cancelled_by,
		"cancelled_at": str(doc.cancelled_at) if doc.cancelled_at else None,
		"cancel_approved_by": doc.cancel_approved_by,
		"kitchen_lines": len(_kitchen_lines(doc)),
		"can_approve": 1 if is_supervisor() else 0,
		"name": doc.name, "outlet": doc.outlet, "status": doc.status,
		"source": doc.source, "room": doc.room, "table_no": doc.table_no,
		"order_type": doc.order_type, "kot_no": doc.kot_no,
		"guests": doc.guests, "customer_name": doc.customer_name,
		"customer_phone": doc.customer_phone,
		"delivery_address": doc.delivery_address,
		"nc": doc.nc, "nc_authorized_by": doc.nc_authorized_by,
		"nc_note": doc.nc_note,
		"kot_tickets": _kot_tickets_of(doc),
		"paid": doc.paid, "payment_mode": doc.payment_mode,
		"discount_amount": doc.discount_amount, "discount_reason": doc.discount_reason,
		"subtotal": doc.subtotal, "order_total": doc.order_total,
		"kot_fired": doc.kot_fired, "notes": doc.notes,
		"items": [
			{"row": it.name, "menu_item": it.menu_item, "item_name": it.item_name,
			 "qty": it.qty, "rate": it.rate, "amount": it.amount,
			 "instructions": it.instructions, "kot_status": it.kot_status,
			 "voided": it.voided, "void_reason": it.void_reason,
			 "voided_by": it.voided_by, "void_approved_by": it.void_approved_by}
			for it in doc.items],
	}


@frappe.whitelist(methods=["POST"])
@require_perm("POS Order", "take_orders")
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
@require_perm("POS Order", "take_orders")
def confirm_order(order: str):
	"""Captain confirmation for a Placed order that has no captain yet
	(legacy guest QR). Sets the captain and moves Placed -> Confirmed."""
	doc = frappe.get_doc("POS Order", order)
	doc.status = "Confirmed"
	if not doc.captain:
		doc.captain = frappe.session.user
	doc.save()
	return {"ok": True, "status": "Confirmed"}


@frappe.whitelist(methods=["POST"])
@require_perm("POS Order", "take_orders")
def apply_discount(order: str, amount: float, reason: str = ""):
	"""The guest-discount popup - a captain grants a discount with a reason."""
	doc = frappe.get_doc("POS Order", order)
	doc.discount_amount = float(amount or 0)
	doc.discount_reason = reason or None
	doc.save()
	return {"ok": True, "discount": doc.discount_amount,
	        "order_total": doc.order_total}


@frappe.whitelist(methods=["POST"])
@require_perm("POS Order", "take_orders")
def fire_kot(order: str, course: str | None = None):
	"""Send the order to the kitchen: new lines become Fired and show on the
	kitchen display. Stamps the KOT number (a daily sequence per outlet) and
	returns just-fired lines so the till can print the thermal KOT ticket.

	Pass a course to send only that course and hold the rest - the table
	orders once, the kitchen cooks the mains when the starters are cleared.
	Each line is stamped with the moment it was fired: that, not when the
	captain opened the tab, is when the cook's clock starts.

	With auto KOT on (the F&B setting, or the outlet's override) this also
	accepts the ticket, so the kitchen does not press Start, and the
	response tells the till to print."""
	return _fire(frappe.get_doc("POS Order", order), course)


def _fire(doc, course: str | None = None) -> dict:
	"""fire_kot on a loaded order. Saves the order once, so a caller that
	has just changed it (send_round) pays for one write, not two."""
	courses = _courses_of(doc) if course else {}
	now = frappe.utils.now()
	fired = []
	fired_rows = []
	auto = outlet_auto_kot(doc.outlet)
	for it in doc.items:
		if it.kot_status == "New" and not it.voided:
			if course and courses.get(it.menu_item) != course:
				continue
			it.kot_status = "Fired"
			it.fired_at = now
			# what the till prints on the thermal ticket...
			fired.append({"item_name": it.item_name, "qty": it.qty,
			              "instructions": it.instructions})
			# ...and what the stock engine needs. Kept apart deliberately:
			# the ticket is a human artefact, this is bookkeeping. Rows, not
			# dicts: a line send_round just appended has no name until save.
			fired_rows.append(it)
	if course and not fired:
		frappe.throw(_("Nothing is held on that course."))
	if not doc.kot_no:
		# Site-local "today", not MariaDB UTC date(now()) — those diverge after
		# 18:30 UTC on IST sites and every KOT would reset to 1.
		from frappe.utils import today
		last = frappe.db.sql(
			"""select max(kot_no) from `tabPOS Order`
			   where outlet=%s and creation >= %s""",
			(doc.outlet, today()))[0][0] or 0
		doc.kot_no = int(last) + 1
	doc.kot_fired = 1
	if doc.status in ("Placed", "Confirmed"):
		doc.status = "Preparing"
	# Auto KOT: the pass has the ticket the moment it is punched. A manual
	# outlet still waits for accept_ticket, so a printed slip is not proof
	# anyone has seen it.
	if fired and auto and not doc.accepted_at:
		doc.accepted_at = now
	doc.save()
	# Ingredients leave the shelf now - when the chef starts cooking - not when
	# the bill is paid: a line voided after firing consumed real food and bills
	# nothing. Never blocks; a short count must not stop service, it just
	# reports itself as stale. See kamra/inventory.py.
	from kamra.inventory import consume_for_lines
	alerts = consume_for_lines(doc, [
		{"row": it.name, "menu_item": it.menu_item, "qty": it.qty,
		 "stock_posted": it.stock_posted} for it in fired_rows])
	ticket = {
		"kot_no": doc.kot_no, "at": now, "round": _next_kot_round(doc),
		"nc": bool(doc.nc), "nc_by": doc.nc_authorized_by,
		"label": _label(doc.as_dict()), "order_type": doc.order_type,
		"order": doc.name, "customer": doc.customer_name,
		"address": doc.delivery_address, "items": fired,
	}
	history = frappe.parse_json(doc.last_kot_ticket) if doc.last_kot_ticket else []
	if not isinstance(history, list):
		history = []
	history.append(ticket)
	doc.db_set("last_kot_ticket", frappe.as_json(history), update_modified=False)
	# Kitchen printers take the lines they serve; the till prints the rest
	# (all of them when the property has no printers set up).
	from kamra.printing import route_kot
	routed = route_kot(doc, fired_rows, ticket) if fired_rows else {"jobs": [], "unrouted": []}
	return {"ok": True, "status": doc.status, "kot_no": doc.kot_no,
	        "nc": bool(doc.nc), "fired_items": fired, "ticket": ticket,
	        "print_jobs": routed["jobs"],
	        "till_ticket": dict(ticket, items=routed["unrouted"]),
	        "auto_print": bool(auto and routed["unrouted"]),
	        "accepted_at": doc.accepted_at,
	        "stock_alerts": alerts}


@frappe.whitelist(methods=["POST"])
@require_perm("POS Order", "take_orders")
def send_order(outlet: str, items, property: str | None = None,
               room: str | None = None, reservation: str | None = None,
               table_no: str | None = None, notes: str | None = None,
               order_type: str | None = None, guests=None,
               customer_name: str | None = None,
               customer_phone: str | None = None,
               delivery_address: str | None = None,
               allergy_note: str | None = None,
               discount: float = 0, discount_reason: str = "",
               guest: str | None = None):
	"""A captain's new bill straight to the kitchen, in one call: what
	create_order, apply_discount, confirm_order and fire_kot do one after
	another, in one request and one transaction. The till waits for one
	round trip instead of four, and the kitchen gets a single update."""
	doc = _build_order(outlet, items, property, room, reservation, table_no,
	                   "Manual", notes, order_type, guests, customer_name,
	                   customer_phone, delivery_address, allergy_note, guest)
	doc.status = "Confirmed"
	if float(discount or 0) > 0:
		doc.discount_amount = float(discount)
		doc.discount_reason = discount_reason or None
	doc.insert()
	out = _fire(doc)
	out.update(order=doc.name, order_total=doc.order_total)
	return out


@frappe.whitelist(methods=["POST"])
@require_perm("POS Order", "take_orders")
def send_round(order: str, items):
	"""Another round on a running bill, straight to the kitchen: add_items
	and fire_kot in one call and one save."""
	doc = frappe.get_doc("POS Order", order)
	if doc.status in ("Delivered", "Cancelled"):
		frappe.throw(_("This order is already closed."))
	lines = _load_items(items)
	if not lines:
		frappe.throw(_("Add at least one available item."))
	for line in lines:
		doc.append("items", line)
	out = _fire(doc)
	out.update(order=doc.name, order_total=doc.order_total)
	return out


def _next_kot_round(doc) -> int:
	history = frappe.parse_json(doc.last_kot_ticket) if doc.last_kot_ticket else []
	return (len(history) if isinstance(history, list) else 0) + 1


@frappe.whitelist()
@require_perm("POS Order", "take_orders")
def kitchen_queue(property: str, outlet: str | None = None,
                  station: str | None = None):
	"""The kitchen display: fired orders the kitchen still has work on. Scope
	to one outlet (each restaurant's own kitchen) and/or one station.

	Each line carries a `state` the screen renders directly:
	  cooking   - fired, still to make
	  held      - a later course, or a round added to a running tab; the
	              kitchen can see it coming but must not start it
	  cancelled - voided after the KOT fired; the chef may be cooking it right
	              now, so it stays on the ticket (loudly) until acknowledged
	  done      - already prepared; kept for context and to allow a recall

	A ticket is on the board while it has cooking, held or cancelled lines.
	Done lines ride along but never hold a ticket open, so "all ready" still
	clears it.

	`fired_at` per line is what the display ages against - a table that sat an
	hour over drinks must not hand the kitchen a ticket that is already red."""
	filters = {"property": property, "status": "Preparing", "kot_fired": 1}
	if outlet:
		filters["outlet"] = outlet
	fields = ["name", "outlet", "room", "table_no", "creation", "notes",
	          "kot_no", "order_type", "guests", "captain", "allergy_note",
	          "order_total", "accepted_at", "status"]
	orders = frappe.get_all("POS Order", filters=filters, fields=fields,
	                        order_by="creation asc")
	# A bill cancelled after its KOT went out keeps its ticket on the board,
	# every line struck as cancelled, until the chef acknowledges each one:
	# the food may be on the pass already. Only bills cancelled through
	# cancel_order (which stamps cancelled_at) in the last 12 hours.
	orders += frappe.get_all(
		"POS Order",
		filters={**filters, "status": "Cancelled",
		         "cancelled_at": [">=", frappe.utils.add_to_date(
		             frappe.utils.now_datetime(), hours=-12)]},
		fields=fields, order_by="creation asc")
	if not orders:
		return []
	orders.sort(key=lambda o: o.creation)
	cancelled_bill = {o.name for o in orders if o.status == "Cancelled"}

	# One query for every line, one for the menu meta, one for the outlet
	# names: the display polls this, so it must not scale with ticket count.
	rows = frappe.get_all(
		"POS Order Item", filters={"parent": ["in", [o.name for o in orders]]},
		fields=["name", "parent", "item_name", "qty", "instructions",
		        "kot_status", "menu_item", "voided", "void_reason",
		        "void_seen", "fired_at", "prepared_at", "idx"],
		order_by="idx asc")
	menu = {
		m.name: m for m in frappe.get_all(
			"Menu Item", filters={"name": ["in", list({r.menu_item for r in rows})]},
			fields=["name", "is_veg", "is_alcohol", "prep_station", "course",
			        "allergens"])
	} if rows else {}
	outlet_names = {
		o.name: o.outlet_name for o in frappe.get_all(
			"POS Outlet", filters={"name": ["in", list({o.outlet for o in orders})]},
			fields=["name", "outlet_name"])
	}
	allergy_of = {o.name: o.allergy_note for o in orders}

	by_order = {}
	for r in rows:
		if r.voided and (r.void_seen or r.kot_status not in ("Fired", "Prepared")):
			continue  # acknowledged, or voided before it ever reached the line
		if r.parent in cancelled_bill and not r.voided:
			continue  # a cancelled bill only shows what the cook must stop
		meta = menu.get(r.menu_item) or {}
		if station and meta.get("prep_station") != station:
			continue
		if r.voided:
			r["state"] = "cancelled"
		elif r.kot_status == "New":
			r["state"] = "held"
		elif r.kot_status == "Prepared":
			r["state"] = "done"
		else:
			r["state"] = "cooking"
		r["is_veg"] = meta.get("is_veg")
		r["is_alcohol"] = meta.get("is_alcohol")
		r["prep_station"] = meta.get("prep_station")
		r["course"] = meta.get("course") or DEFAULT_COURSE
		r["allergens"] = meta.get("allergens")
		r["allergy_hits"] = _allergy_hits(allergy_of.get(r.parent), meta.get("allergens"))
		by_order.setdefault(r.parent, []).append(r)

	out = []
	for o in orders:
		items = by_order.get(o.name) or []
		if not any(i["state"] in ("cooking", "held", "cancelled") for i in items):
			continue
		o["outlet_name"] = outlet_names.get(o.outlet)
		o["room_no"] = (o.room or "").split("-")[-1]
		o["items"] = items
		# courses still held back, in the order they would be served
		held = {i["course"] for i in items if i["state"] == "held"}
		serve = _course_order(property)
		o["held_courses"] = [c for c in serve if c in held] + \
			sorted(c for c in held if c not in serve)
		out.append(o)
	return out


@frappe.whitelist(methods=["POST"])
@require_perm("POS Order", "take_orders")
def mark_prepared(order: str, item_row: str | None = None):
	"""Kitchen marks one line (or every cooking line) prepared. Voided lines
	are never swept up by "all ready" - that food is cancelled, not cooked."""
	doc = frappe.get_doc("POS Order", order)
	now = frappe.utils.now()
	for it in doc.items:
		if it.voided:
			continue
		if (item_row and it.name == item_row) or (not item_row and it.kot_status == "Fired"):
			it.kot_status = "Prepared"
			it.prepared_at = now
	doc.save()
	live = [it for it in doc.items if not it.voided]
	all_done = bool(live) and all(it.kot_status == "Prepared" for it in live)
	return {"ok": True, "all_prepared": all_done}


@frappe.whitelist(methods=["POST"])
@require_perm("POS Order", "take_orders")
def accept_ticket(order: str):
	"""The kitchen takes the ticket on. Until a ticket is accepted the floor
	has no evidence anyone has seen it - a KOT can print to an empty pass."""
	doc = frappe.get_doc("POS Order", order)
	if not doc.accepted_at:
		doc.accepted_at = frappe.utils.now()
		doc.save()
	return {"ok": True, "accepted_at": doc.accepted_at}


@frappe.whitelist(methods=["POST"])
@require_perm("POS Order", "take_orders")
def recall_prepared(order: str, item_row: str | None = None):
	"""Undo a mark-prepared: the line goes back to Fired and reappears on the
	display. A mis-tap on a greasy touchscreen must not be one-way."""
	doc = frappe.get_doc("POS Order", order)
	if doc.status in ("Delivered", "Cancelled"):
		frappe.throw(_("This order has already left the kitchen."))
	for it in doc.items:
		if it.voided:
			continue
		if (item_row and it.name == item_row) or (not item_row and it.kot_status == "Prepared"):
			it.kot_status = "Fired"
			it.prepared_at = None
	doc.save()
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
@require_perm("POS Order", "take_orders")
def acknowledge_void(order: str, item_row: str):
	"""The chef has seen that a fired line was cancelled and can stop cooking
	it; drop it from the display. The void itself stays on the order."""
	doc = frappe.get_doc("POS Order", order)
	target = next((it for it in doc.items if it.name == item_row), None)
	if not target:
		frappe.throw(_("Order line not found."))
	if not target.voided:
		frappe.throw(_("That line is not voided."))
	target.void_seen = 1
	doc.save()
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
@require_perm("POS Order", "take_orders")
def deliver_order(order: str):
	"""Order served - moves to Delivered, which posts it to the room folio
	(controller) when there's a linked stay."""
	doc = frappe.get_doc("POS Order", order)
	doc.status = "Delivered"
	doc.save()
	_flag_cleaning_if_freed(doc)
	return {"ok": True, "status": "Delivered",
	        "posted_to_folio": bool(doc.posted_to_folio)}


@frappe.whitelist(methods=["POST"])
@require_perm("POS Order", "take_orders")
def pay_order(order: str, mode: str, pin: str | None = None):
	"""Settle a bill at the outlet (walk-ins, takeaway - or a guest who'd
	rather pay now than post to the room). Records the payment mode and
	closes the order without touching any folio. Posts into the open
	cashier session so FO + POS cash reconcile together."""
	if mode not in ("Cash", "Card", "UPI"):
		frappe.throw(_("Pick a payment mode: Cash, Card or UPI."))
	doc = frappe.get_doc("POS Order", order)
	if doc.status == "Cancelled":
		frappe.throw(_("This order was cancelled."))
	if doc.posted_to_folio:
		frappe.throw(_("Already posted to the room folio - settle it there."))
	if doc.paid:
		frappe.throw(_("Already paid."))
	if doc.nc:
		frappe.throw(_("This is an NC (complimentary) bill - close it with "
		              "Deliver, there is nothing to collect."))
	prop = doc.property
	from kamra.authz import require_cashier_pin
	require_cashier_pin(prop, pin)
	from kamra.cashier import record_cashier_txn, require_open_session
	sess = None
	try:
		sess = require_open_session(prop, doc.outlet)
	except Exception:
		if "Kamra Agent" not in frappe.get_roles() and \
		   frappe.session.user != "Administrator":
			raise
	doc.paid = 1
	doc.payment_mode = mode
	doc.status = "Delivered"
	doc.save()
	_flag_cleaning_if_freed(doc)
	record_cashier_txn(
		prop, "Payment", mode, float(doc.order_total or 0),
		pos_order=doc.name, reference=f"POS {doc.name}", session=sess)
	# a paid outlet bill is a (simplified) tax invoice where the pack says so
	from kamra import localization as loc
	loc.on_pos_bill_paid(
		loc.pack_for(prop), doc.name,
		float(frappe.db.get_value("POS Outlet", doc.outlet, "gst_rate") or 0))
	return {"ok": True, "status": "Delivered", "paid": True, "mode": mode,
	        "order_total": doc.order_total}


@frappe.whitelist(methods=["POST"])
@require_perm("POS Order", "take_orders")
def change_payment_mode(order: str, mode: str, reason: str = "",
                        pin: str | None = None):
	"""Correct the tender on a bill that was settled with the wrong mode (Card
	pressed for Cash). The till keeps its history: a reversing entry for the
	old mode and a new entry for the right one, same till session, with a
	comment on the bill. Only while that till is still open - once it is
	counted and closed, the day's cash is final and a manager must correct it
	from the till screens."""
	if mode not in ("Cash", "Card", "UPI"):
		frappe.throw(_("Pick a payment mode: Cash, Card or UPI."))
	doc = frappe.get_doc("POS Order", order)
	if not doc.paid or doc.status == "Cancelled":
		frappe.throw(_("Only a bill that was paid at the outlet can change its payment mode."))
	if doc.posted_to_folio or doc.nc:
		frappe.throw(_("This bill was posted to a room or made complimentary - "
		              "there is no payment mode to change."))
	old = doc.payment_mode
	if old == mode:
		frappe.throw(_("This bill is already marked {0}.").format(mode))
	from kamra.authz import require_cashier_pin
	require_cashier_pin(doc.property, pin)
	original = frappe.db.get_value(
		"Cashier Transaction",
		{"pos_order": doc.name, "kind": "Payment", "amount": [">", 0]},
		["name", "session", "amount"], as_dict=True, order_by="creation desc")
	if original and original.session:
		if frappe.db.get_value("Cashier Session", original.session, "status") != "Open":
			frappe.throw(_("The till this bill was taken on is already closed and "
			              "counted. Ask a manager to correct it."))
	from kamra.cashier import record_cashier_txn
	amt = float(original.amount if original else doc.order_total or 0)
	sess = original.session if original else None
	why = (reason or "").strip() or _("Wrong payment mode pressed")
	if original:
		record_cashier_txn(
			doc.property, "Payment", old or "Cash", -amt, pos_order=doc.name,
			reference=f"POS {doc.name}", notes=f"Mode corrected to {mode}: {why}",
			session=sess)
		record_cashier_txn(
			doc.property, "Payment", mode, amt, pos_order=doc.name,
			reference=f"POS {doc.name}", notes=f"Mode corrected from {old}: {why}",
			session=sess)
	doc.db_set("payment_mode", mode)
	doc.add_comment("Comment", _("Payment mode changed from {0} to {1}: {2}").format(
		old, mode, why))
	return {"ok": True, "order": doc.name, "mode": mode, "was": old}


@frappe.whitelist(methods=["POST"])
@require_perm("POS Order", "take_orders")
def mark_nc(order: str, authorized_by: str, note: str = "", undo: int = 0):
	"""Mark a bill NC (no charge / complimentary). Needs who authorized it
	(captain, chef, GM, management…) and takes a free-text reference (the
	occasion, the complaint ticket, the promise made). The items still fire
	to the kitchen and print on the KOT - the bill just closes at zero and
	never touches a folio. `undo=1` lifts it."""
	doc = frappe.get_doc("POS Order", order)
	if doc.status in ("Delivered", "Cancelled"):
		frappe.throw(_("This order is already closed."))
	if int(undo or 0):
		doc.nc = 0
		doc.nc_authorized_by = None
		doc.nc_note = None
	else:
		if not (authorized_by or "").strip():
			frappe.throw(_("Who authorized the NC? (captain / chef / GM…)"))
		doc.nc = 1
		doc.nc_authorized_by = authorized_by.strip()[:80]
		doc.nc_note = (note or "").strip()[:200] or None
	doc.save()
	return {"ok": True, "nc": bool(doc.nc), "order_total": doc.order_total}


# ── cancel, void, remove ──────────────────────────────────────────────────
#
# What a captain may undo depends on what the kitchen already has:
#   nothing sent    -> cancel the bill, or remove a line, alone (a reason
#                      for the cancel; a removed line was never cooked)
#   lines sent      -> those lines are voided, never deleted: they stay on
#                      the bill struck through, the kitchen gets a VOID slip
#                      and sees them as cancelled until it acknowledges, and
#                      a supervisor approves with their PIN
#   paid / posted   -> closed; corrections happen on the folio or as refunds
# An agent (MCP, the copilot) may cancel an unsent bill but never voids
# food the kitchen has started.


class SupervisorRequired(frappe.PermissionError):
	"""Voiding food the kitchen has started needs a supervisor."""


def _kitchen_lines(doc) -> list:
	"""Live lines the kitchen has: sent (Fired) or made (Prepared)."""
	return [it for it in doc.items
	        if not it.voided and (it.kot_status or "New") != "New"]


def _assert_open(doc):
	if doc.status in ("Delivered", "Cancelled") or doc.paid or doc.posted_to_folio:
		frappe.throw(_("This order is already closed."))


def _agent_call() -> bool:
	if getattr(frappe.flags, "kamra_agent_call", False) or \
			getattr(frappe.flags, "kamra_gate_bypass", False):
		return True
	from kamra.authz import is_supervisor
	return "Kamra Agent" in frappe.get_roles() and not is_supervisor()


def _channel() -> str:
	via = getattr(frappe.flags, "kamra_agent_call", None)
	return via if via in ("MCP", "Chat") else "Desk"


def _reason_text(reason: str | None, reason_code: str | None) -> str:
	"""The reason as it is kept: a void reason code (Settings, the same list
	the folio uses) and/or free text. One of them is required."""
	text = (reason or "").strip()
	if reason_code:
		from kamra.ledger import ensure_default_reason_codes
		ensure_default_reason_codes()
		row = frappe.db.get_value("Reason Code", reason_code,
		                          ["category", "disabled", "description"], as_dict=True)
		if not row or row.disabled or row.category != "Void":
			frappe.throw(_("Pick a void reason from the list."))
		text = f"{reason_code}: {text}" if text else f"{reason_code}: {row.description}"
	if not text:
		frappe.throw(_("A reason is required."))
	return text[:140]


def _approve_kitchen_void(doc, supervisor: str | None, supervisor_pin) -> str:
	"""Who approves voiding lines the kitchen already has. A supervisor at
	the till approves for themselves (with their cashier PIN where the
	property asks for PINs); anyone else needs a supervisor's user and PIN.
	Agents are always refused."""
	if _agent_call():
		frappe.throw(_("The kitchen already has items on this bill. An agent "
		              "cannot void them: a supervisor does that at the till."),
		             SupervisorRequired)
	from kamra.authz import is_supervisor, require_cashier_pin, verify_supervisor
	if is_supervisor() and (not supervisor or supervisor == frappe.session.user):
		require_cashier_pin(doc.property, supervisor_pin)
		return frappe.session.user
	if not supervisor:
		frappe.throw(_("SUPERVISOR_REQUIRED: the kitchen already has items on "
		              "this bill. A supervisor approves voiding them with "
		              "their PIN."), SupervisorRequired)
	return verify_supervisor(doc.property, supervisor, supervisor_pin)


def _void_lines(doc, lines, reason: str, approver: str | None):
	user = frappe.session.user
	for it in lines:
		was_sent = (it.kot_status or "New") != "New"
		it.voided = 1
		it.void_reason = reason
		it.voided_by = user
		if was_sent:
			it.void_approved_by = approver


def _value(lines) -> float:
	return round(sum(float(it.qty or 0) * float(it.rate or 0) for it in lines), 2)


@frappe.whitelist(methods=["POST"])
@require_perm("POS Order", "take_orders")
def cancel_order(order: str, reason: str = "", reason_code: str | None = None,
                 supervisor: str | None = None, supervisor_pin: str | None = None):
	"""Cancel an open bill with a reason. Nothing sent to the kitchen yet: the
	captain (or an agent) cancels alone. Items already sent: every live line
	is voided rather than deleted, the kitchen gets a VOID slip and sees the
	ticket as cancelled, and a supervisor approves (`supervisor` +
	`supervisor_pin`, or a supervisor's own session). Paid, posted or
	already cancelled bills are refused. Who, why and who approved are kept
	on the bill and in the activity log; the table is freed."""
	doc = frappe.get_doc("POS Order", order)
	_assert_open(doc)
	text = _reason_text(reason, reason_code)
	sent = _kitchen_lines(doc)
	approver = _approve_kitchen_void(doc, supervisor, supervisor_pin) if sent else None
	live = [it for it in doc.items if not it.voided]
	value = _value(live)
	_void_lines(doc, live, text, approver)
	doc.status = "Cancelled"
	doc.cancel_reason = text
	doc.cancelled_by = frappe.session.user
	doc.cancelled_at = frappe.utils.now()
	doc.cancel_approved_by = approver
	# kept for reports written before the cancel fields existed
	doc.notes = (f"{doc.notes}\n" if doc.notes else "") + f"Cancelled: {text}"
	doc.save()
	if sent:
		from kamra.printing import void_slip
		void_slip(doc, sent)
		# food reached the table: it needs clearing before the next party
		_flag_cleaning_if_freed(doc)
	from kamra.savings import log_action
	log_action("pos_cancel_order", "POS Order", doc.name, doc.property,
	           rationale=(f"{_label(doc.as_dict())}: cancelled "
	                      f"{len(live)} line(s), value {value:.2f}"
	                      f"{f', {len(sent)} already in the kitchen' if sent else ', nothing sent to the kitchen'}"
	                      f". Reason: {text}"),
	           approver=approver, channel=_channel(),
	           before_snapshot={"status": "open", "value": value,
	                            "lines": len(live), "sent": len(sent)},
	           after_snapshot={"status": "Cancelled"})
	return {"ok": True, "status": "Cancelled", "voided_value": value,
	        "kitchen_lines": len(sent), "approved_by": approver}


@frappe.whitelist(methods=["POST"])
@require_perm("POS Order", "take_orders")
def void_item(order: str, item_row: str, reason: str = "",
              reason_code: str | None = None, supervisor: str | None = None,
              supervisor_pin: str | None = None):
	"""Void one line with a reason. The line stays on the order (struck
	through, amount zero) so the KOT-vs-bill audit holds up. A line the
	kitchen already has needs a supervisor's approval (see cancel_order) and
	prints a VOID slip; a line never sent is simpler to remove_item."""
	doc = frappe.get_doc("POS Order", order)
	_assert_open(doc)
	target = next((it for it in doc.items if it.name == item_row), None)
	if not target:
		frappe.throw(_("Order line not found."))
	if target.voided:
		frappe.throw(_("That line is already voided."))
	text = _reason_text(reason, reason_code)
	was_sent = (target.kot_status or "New") != "New"
	approver = _approve_kitchen_void(doc, supervisor, supervisor_pin) if was_sent else None
	_void_lines(doc, [target], text, approver)
	doc.save()
	if was_sent:
		from kamra.printing import void_slip
		void_slip(doc, [target])
	from kamra.savings import log_action
	log_action("pos_void_item", "POS Order", doc.name, doc.property,
	           rationale=(f"{_label(doc.as_dict())}: voided {target.item_name} "
	                      f"x{float(target.qty or 0):g}, value {_value([target]):.2f}"
	                      f"{' (already in the kitchen)' if was_sent else ''}. Reason: {text}"),
	           approver=approver, channel=_channel())
	return {"ok": True, "order_total": doc.order_total,
	        "subtotal": doc.subtotal, "approved_by": approver}


@frappe.whitelist(methods=["POST"])
@require_perm("POS Order", "take_orders")
def remove_item(order: str, item_row: str):
	"""Take a line off a bill before it goes to the kitchen: a mis-tap or a
	change of mind. No reason and no approval, because nothing was cooked.
	A line the kitchen has is refused (void it instead), and so is the last
	line (cancel the bill instead)."""
	doc = frappe.get_doc("POS Order", order)
	_assert_open(doc)
	target = next((it for it in doc.items if it.name == item_row), None)
	if not target or target.voided:
		frappe.throw(_("Order line not found."))
	if (target.kot_status or "New") != "New":
		frappe.throw(_("The kitchen already has {0}. Void it with a reason "
		              "instead.").format(target.item_name))
	if not [it for it in doc.items if not it.voided and it.name != item_row]:
		frappe.throw(_("That is the last item on the bill. Cancel the bill "
		              "instead."))
	doc.remove(target)
	doc.save()
	return {"ok": True, "order_total": doc.order_total, "subtotal": doc.subtotal}


@frappe.whitelist()
@require_perm("POS Order", "take_orders")
def void_approvers(outlet: str):
	"""Who can approve a void at this outlet's till: enabled Hotel Admin and
	Finance users with access to the property and a cashier PIN set. Names
	only."""
	from kamra.authz import is_supervisor, restricted_properties, supervisor_roles
	prop = frappe.db.get_value("POS Outlet", outlet, "property")
	users = {u for u in frappe.get_all(
		"Has Role", filters={"role": ["in", supervisor_roles()], "parenttype": "User"},
		pluck="parent", distinct=True) if is_supervisor(u)}
	users &= set(frappe.get_all("Cashier PIN", pluck="name"))
	out = []
	for u in frappe.get_all("User", filters={"name": ["in", list(users) or [""]],
	                                         "enabled": 1, "user_type": "System User"},
	                        fields=["name", "full_name"], order_by="full_name"):
		allowed = restricted_properties(u.name)
		if allowed is None or prop in allowed:
			out.append({"user": u.name, "full_name": u.full_name or u.name})
	return out


# ── the orders list ───────────────────────────────────────────────────────

LIST_STATES = ("open", "sent", "paid", "room", "nc", "closed", "cancelled")


def _order_list_state(o) -> str:
	"""One word for where a bill stands:
	open (nothing sent to the kitchen), sent (the kitchen has it, not
	settled), paid (at the outlet), room (posted to a room folio), nc
	(complimentary), closed (closed at zero, every line voided) or
	cancelled."""
	status = o.get("status")
	if status == "Cancelled":
		return "cancelled"
	if status == "Delivered":
		if o.get("posted_to_folio"):
			return "room"
		if o.get("nc"):
			return "nc"
		if o.get("paid"):
			return "paid"
		return "closed"
	return "sent" if o.get("kot_fired") else "open"


# most bills one history query looks at; a year at a busy outlet fits easily
ORDERS_LIST_MAX = 5000


def _like(q: str) -> str:
	return "%" + q.replace("%", r"\%").replace("_", r"\_") + "%"


@frappe.whitelist()
@require_perm("POS Order", "take_orders")
def orders_list(outlet: str, date: str | None = None, to_date: str | None = None,
                q: str | None = None, state: str | None = None, limit: int = 200,
                offset: int = 0, order_type: str | None = None, mode: str | None = None):
	"""The outlet's bills for a day, or a range of up to a year, newest
	first: open (not sent to the kitchen), sent, paid, posted to a room, NC,
	closed or cancelled, with the table, who it was for, the amount and the
	time. `q` searches the bill and KOT number, table, room, customer name
	and phone, and the in-house guest's name. `state` keeps one state,
	`order_type` one kind of order and `mode` one way of paying (Cash, Card,
	UPI, Room). Pages come back `limit` at a time from `offset`; `total`,
	`has_more`, `counts` and `totals` always cover every bill the filters
	match, not only the page, so nothing is hidden by paging.
	Looking at today also brings in bills still open from earlier days
	(`carried`), so a forgotten order cannot hide. Only this outlet's bills."""
	from frappe.utils import getdate, nowdate
	prop = frappe.db.get_value("POS Outlet", outlet, "property")
	today = getdate(nowdate())
	start = getdate(date) if date else today
	end = getdate(to_date) if to_date else start
	if end < start:
		start, end = end, start
	if (end - start).days > 366:
		frappe.throw(_("Pick a range of one year or less."))
	page = max(1, min(cint(limit) or 200, 500))
	skip = max(0, cint(offset))
	fields = ["name", "status", "order_type", "room", "reservation", "table_no",
	          "customer_name", "guest", "order_total", "paid", "payment_mode",
	          "nc", "posted_to_folio", "kot_fired", "kot_no", "guests",
	          "creation", "cancel_reason", "captain"]
	or_filters = None
	qq = (q or "").strip()[:60]
	if qq:
		like = _like(qq)
		or_filters = [["name", "like", like], ["customer_name", "like", like],
		              ["customer_phone", "like", like], ["table_no", "like", like],
		              ["room", "like", like]]
		if qq.isdigit():
			or_filters.append(["kot_no", "=", int(qq)])
		stays = frappe.get_all("Reservation", filters={
			"property": prop, "guest_name": ["like", like]}, pluck="name", limit=50)
		if stays:
			or_filters.append(["reservation", "in", stays])
	rows = frappe.get_all(
		"POS Order",
		filters={"outlet": outlet, "creation": ["between", [
			f"{start} 00:00:00", f"{end} 23:59:59.999999"]]},
		or_filters=or_filters, fields=fields, order_by="creation desc",
		limit=ORDERS_LIST_MAX)
	if end >= today:
		earlier = frappe.get_all(
			"POS Order",
			filters={"outlet": outlet, "status": ["in", list(OPEN_STATUSES)],
			         "creation": ["<", f"{start} 00:00:00"]},
			or_filters=or_filters, fields=fields, order_by="creation desc", limit=50)
		for r in earlier:
			r["carried"] = 1
		rows = earlier + rows

	# decide each bill's state and apply the filters over the whole range,
	# then page: the counts and totals must not depend on which page is shown
	typed = [r for r in rows if not order_type or r.order_type == order_type]
	scoped, counts = [], dict.fromkeys(LIST_STATES, 0)
	for r in typed:
		st = _order_list_state(r)
		paid_by = "Room" if st == "room" else (r.payment_mode if st == "paid" else None)
		if mode and paid_by != mode:
			continue
		counts[st] += 1
		scoped.append((r, st, paid_by))
	shown = [x for x in scoped if not state or x[1] == state]

	totals = {"bills": len(shown), "sales": 0.0, "cancelled": 0.0, "by_mode": {}, "by_type": {}}
	for r, st, paid_by in shown:
		amt = float(r.order_total or 0)
		if st in ("paid", "room"):
			totals["sales"] += amt
			totals["by_mode"][paid_by or "Other"] = totals["by_mode"].get(paid_by or "Other", 0.0) + amt
			key = r.order_type or "Other"
			totals["by_type"][key] = totals["by_type"].get(key, 0.0) + amt
		elif st == "cancelled":
			totals["cancelled"] += amt
	totals["sales"] = round(totals["sales"], 2)
	totals["cancelled"] = round(totals["cancelled"], 2)
	totals["by_mode"] = {k: round(v, 2) for k, v in totals["by_mode"].items()}
	totals["by_type"] = {k: round(v, 2) for k, v in totals["by_type"].items()}

	window = shown[skip:skip + page]
	names = [r.name for r, _, _ in window]
	lines: dict[str, dict] = {}
	for it in frappe.get_all(
			"POS Order Item", filters={"parent": ["in", names or [""]],
			                           "parenttype": "POS Order"},
			fields=["parent", "qty", "rate", "voided"]) if names else []:
		c = lines.setdefault(it.parent, {"live": 0, "voided": 0, "voided_value": 0.0})
		if it.voided:
			c["voided"] += 1
			c["voided_value"] += float(it.qty or 0) * float(it.rate or 0)
		else:
			c["live"] += 1
	stay_names = dict(frappe.get_all(
		"Reservation", filters={"name": ["in", [r.reservation for r, _, _ in window
		                                        if r.reservation] or [""]]},
		fields=["name", "guest_name"], as_list=True))
	stale_after = _unfired_alert_min(outlet) if window else 0
	now = frappe.utils.now_datetime()

	out = []
	for r, st, _paid_by in window:
		c = lines.get(r.name, {})
		age = int((now - frappe.utils.get_datetime(r.creation)).total_seconds() // 60)
		out.append({
			"name": r.name, "label": _label(r), "state": st, "status": r.status,
			"order_type": r.order_type, "table_no": r.table_no,
			"room_no": (r.room or "").split("-")[-1] if r.room else None,
			"who": r.customer_name or stay_names.get(r.reservation) or None,
			"guest": r.guest,
			# a cancelled bill's lines are all voided: show what it was worth
			"amount": round(c.get("voided_value", 0.0), 2) if st == "cancelled"
			          else float(r.order_total or 0),
			"items": c.get("live", 0), "voided": c.get("voided", 0),
			"kot_no": r.kot_no, "payment_mode": r.payment_mode,
			"guests": r.guests, "time": str(r.creation), "age_min": age,
			"stale": 1 if st == "open" and age >= stale_after else 0,
			"carried": r.get("carried", 0), "cancel_reason": r.cancel_reason,
		})
	return {"from": str(start), "to": str(end), "rows": out, "counts": counts,
	        "total": len(shown), "has_more": skip + page < len(shown),
	        "truncated": len(rows) >= ORDERS_LIST_MAX, "totals": totals}


EXPORT_COLUMNS = ("Bill", "KOT", "Date", "Time", "Outlet", "Type", "Table", "Room",
                  "Guest or customer", "Phone", "State", "Payment mode", "Lines",
                  "Discount", "Amount before tax", "Complimentary authorised by",
                  "Captain", "Cancel reason", "Cancelled by")


@frappe.whitelist()
@require_perm("POS Order", "take_orders")
def orders_export(outlet: str, date: str | None = None, to_date: str | None = None,
                  q: str | None = None, state: str | None = None,
                  mode: str | None = None, order_type: str | None = None):
	"""The outlet's bill history as CSV for a day or up to a year: every
	bill with its state, payment mode, amount, discount, who it was for and
	who cancelled it. Same search and state filters as the orders list;
	`mode` keeps one payment mode (Cash, Card, UPI). A phone number is masked
	except to a supervisor, as on the till. Returns {filename, csv, rows}."""
	import csv
	import io

	from frappe.utils import getdate, nowdate
	prop = frappe.db.get_value("POS Outlet", outlet, "property")
	from kamra.crs import assert_property_access
	assert_property_access(prop)
	today = getdate(nowdate())
	start = getdate(date) if date else today
	end = getdate(to_date) if to_date else start
	if end < start:
		start, end = end, start
	if (end - start).days > 366:
		frappe.throw(_("Pick a range of one year or less."))
	or_filters = None
	qq = (q or "").strip()[:60]
	if qq:
		like = _like(qq)
		or_filters = [["name", "like", like], ["customer_name", "like", like],
		              ["customer_phone", "like", like], ["table_no", "like", like],
		              ["room", "like", like]]
		if qq.isdigit():
			or_filters.append(["kot_no", "=", int(qq)])
	filters = {"outlet": outlet, "creation": ["between", [
		f"{start} 00:00:00", f"{end} 23:59:59.999999"]]}
	if mode in ("Cash", "Card", "UPI"):
		filters["payment_mode"] = mode
	elif mode == "Room":
		filters["posted_to_folio"] = 1
	if order_type:
		filters["order_type"] = order_type
	rows = frappe.get_all(
		"POS Order", filters=filters, or_filters=or_filters,
		fields=["name", "status", "order_type", "room", "reservation", "table_no",
		        "customer_name", "customer_phone", "order_total", "discount_amount",
		        "paid", "payment_mode", "nc", "nc_authorized_by", "posted_to_folio",
		        "kot_fired", "kot_no", "creation", "cancel_reason", "cancelled_by",
		        "captain"],
		order_by="creation desc", limit_page_length=20000)
	names = [r.name for r in rows]
	live: dict[str, int] = {}
	for it in frappe.get_all(
			"POS Order Item", filters={"parent": ["in", names], "parenttype": "POS Order",
			                           "voided": 0}, fields=["parent"]) if names else []:
		live[it.parent] = live.get(it.parent, 0) + 1
	stays = dict(frappe.get_all(
		"Reservation", filters={"name": ["in", [r.reservation for r in rows
		                                       if r.reservation] or [""]]},
		fields=["name", "guest_name"], as_list=True))
	outlet_name = frappe.db.get_value("POS Outlet", outlet, "outlet_name") or outlet
	buf = io.StringIO()
	w = csv.writer(buf)
	w.writerow(EXPORT_COLUMNS)
	n = 0
	for r in rows:
		st = _order_list_state(r)
		if state and st != state:
			continue
		n += 1
		created = frappe.utils.get_datetime(r.creation)
		w.writerow([
			r.name, r.kot_no or "", created.date().isoformat(),
			created.strftime("%H:%M"), outlet_name, r.order_type or "",
			r.table_no or "", (r.room or "").split("-")[-1] if r.room else "",
			r.customer_name or stays.get(r.reservation) or "",
			_shown_phone(r.customer_phone) or "", st,
			r.payment_mode if st == "paid" else ("Room" if st == "room" else ""),
			live.get(r.name, 0), float(r.discount_amount or 0),
			float(r.order_total or 0), r.nc_authorized_by or "", r.captain or "",
			r.cancel_reason or "", r.cancelled_by or ""])
	return {"filename": f"orders-{outlet_name}-{start}_{end}.csv".replace(" ", "-"),
	        "csv": "\ufeff" + buf.getvalue(), "rows": n}


# ── who the bill is for ───────────────────────────────────────────────────
#
# The till shows only what service needs: name, VIP, the guest's notes
# (preferences, allergies), the stay and whether it can take room charges,
# and what they had here before. Never ID documents, email, address, date
# of birth or nationality. A phone number shows only its last digits,
# except to a supervisor.


def _digits(s: str | None) -> str:
	return re.sub(r"\D", "", s or "")


def _shown_phone(phone: str | None) -> str | None:
	from kamra.authz import is_supervisor
	if not phone:
		return None
	if is_supervisor():
		return phone
	d = _digits(phone)
	return f"•••• {d[-4:]}" if len(d) >= 4 else "••••"


def _guest_by_phone(phone: str | None) -> str | None:
	"""The profile with this phone number, matched on its last 8+ digits
	so "98765 43210" finds "+91 98765 43210"."""
	d = _digits(phone)
	if len(d) < 8:
		return frappe.db.get_value("Guest", {"phone": (phone or "").strip()}) \
			if (phone or "").strip() else None
	tail = d[-10:]
	from kamra.authz import guest_scope_sql
	scope_sql, params = guest_scope_sql("g")
	params["tail"] = f"%{tail}"
	row = frappe.db.sql(  # nosemgrep: frappe-sql-format-injection -- values are parameterized; the interpolated scope clause is a constant from authz
		f"""SELECT g.name FROM `tabGuest` g
		    WHERE REPLACE(REPLACE(REPLACE(REPLACE(IFNULL(g.phone, ''), ' ', ''),
		          '-', ''), '+', ''), '(', '') LIKE %(tail)s AND {scope_sql}
		    ORDER BY g.modified DESC LIMIT 1""", params)
	return row[0][0] if row else None


@frappe.whitelist()
@require_perm("POS Order", "take_orders")
def find_customer(outlet: str, q: str):
	"""Find a guest profile for a bill by phone (4+ digits) or name (3+
	letters): the same guest records the front desk uses. Each match says
	how often they ate at this outlet and whether they are in house now.
	Phones show their last digits only."""
	q = (q or "").strip()[:60]
	d = _digits(q)
	if len(q) < 3 and len(d) < 4:
		return []
	prop = frappe.db.get_value("POS Outlet", outlet, "property")
	from kamra.authz import guest_scope_sql
	scope_sql, params = guest_scope_sql("g")
	params.update(q=_like(q), d=f"%{d}%" if len(d) >= 4 else "__no_match__")
	rows = frappe.db.sql(  # nosemgrep: frappe-sql-format-injection -- values are parameterized; the interpolated scope clause is a constant from authz
		f"""SELECT g.name, g.full_name, g.phone, g.vip
		    FROM `tabGuest` g
		    WHERE (g.full_name LIKE %(q)s
		           OR REPLACE(REPLACE(IFNULL(g.phone, ''), ' ', ''), '-', '') LIKE %(d)s)
		      AND IFNULL(g.full_name, '') != '' AND {scope_sql}
		    ORDER BY g.modified DESC LIMIT 8""", params, as_dict=True)
	if not rows:
		return []
	names = [r.name for r in rows]
	visits = dict(frappe.db.sql(
		"""SELECT guest, COUNT(*) FROM `tabPOS Order`
		   WHERE outlet = %s AND guest IN %s AND status != 'Cancelled'
		   GROUP BY guest""", (outlet, tuple(names))))
	in_house = {}
	for s in frappe.get_all("Reservation", filters={
			"property": prop, "status": "Checked In", "guest": ["in", names]},
			fields=["guest", "room"]):
		in_house[s.guest] = (s.room or "").split("-")[-1] or None
	return [{"guest": r.name, "full_name": r.full_name, "vip": r.vip,
	         "phone": _shown_phone(r.phone), "visits": cint(visits.get(r.name)),
	         "in_house_room": in_house.get(r.name)} for r in rows]


@frappe.whitelist(methods=["POST"])
@require_perm("POS Order", "take_orders")
def attach_customer(outlet: str, order: str | None = None, guest: str | None = None,
                    customer_name: str | None = None, phone: str | None = None,
                    clear: int = 0):
	"""Say who a walk-in bill is for: an existing guest profile (`guest`),
	or a name and phone. A phone that matches a profile reuses it; otherwise
	a lightweight guest profile is added (name and phone only), the same
	record the front desk uses. Without `order` it only finds or adds the
	profile, for a bill the till is about to create. `clear=1` takes the
	customer off the bill. A room bill is always for its in-house guest."""
	prop = frappe.db.get_value("POS Outlet", outlet, "property")
	doc = None
	if order:
		doc = frappe.get_doc("POS Order", order)
		if doc.outlet != outlet:
			frappe.throw(_("That bill belongs to another outlet."))
		_assert_open(doc)
		if doc.reservation:
			frappe.throw(_("This bill is for the in-house guest of its room."))
		if cint(clear):
			doc.guest = None
			doc.save()
			return {"ok": True, "guest": None}
	created = False
	name = (customer_name or "").strip()[:120]
	ph = (phone or "").strip()[:30]
	if not guest:
		guest = _guest_by_phone(ph) if ph else None
		if not guest:
			if not name:
				frappe.throw(_("No guest has that phone number yet. Add their "
				              "name to create one."))
			from kamra.api import _find_or_create_guest
			guest = _find_or_create_guest(name, ph or None, prop)
			created = True
	elif not frappe.db.exists("Guest", guest):
		frappe.throw(_("That guest profile was not found."))
	from kamra.authz import assert_guest_access
	assert_guest_access(guest)
	full_name = frappe.db.get_value("Guest", guest, "full_name") or name
	if doc:
		doc.guest = guest
		doc.customer_name = full_name
		if ph and doc.order_type in ("Takeaway", "Delivery") and not doc.customer_phone:
			doc.customer_phone = ph
		doc.save()
	return {"ok": True, "guest": guest, "full_name": full_name, "created": created}


@frappe.whitelist()
@require_perm("POS Order", "take_orders")
def guest_panel(outlet: str, order: str | None = None, guest: str | None = None,
                room: str | None = None):
	"""Who a bill is for, without leaving the till. For a room bill: the
	in-house guest, room, stay dates and whether the stay can take room
	charges (the check-in's decision, which posting also enforces). For a
	walk-in: the attached guest profile. Either way: VIP, the guest's notes
	(preferences, allergies), the bill's allergy note, and their past bills
	at this outlet. Pass `order`, or `guest` / `room` for a bill not created
	yet."""
	prop = frappe.db.get_value("POS Outlet", outlet, "property")
	reservation = allergy = None
	if order:
		o = frappe.db.get_value(
			"POS Order", order, ["outlet", "guest", "room", "reservation",
			                     "allergy_note"], as_dict=True)
		if not o or o.outlet != outlet:
			frappe.throw(_("That bill belongs to another outlet."))
		guest = o.guest or guest
		room = o.room or room
		reservation, allergy = o.reservation, o.allergy_note
	stay = None
	if reservation or room:
		stay = frappe.db.get_value(
			"Reservation",
			reservation or {"room": room, "status": "Checked In", "property": prop},
			["name", "property", "guest", "guest_name", "room", "status",
			 "check_in_date", "check_out_date", "room_charges_allowed"],
			as_dict=True)
		if stay and stay.property != prop:
			stay = None
	if stay and not guest:
		guest = stay.guest
	if not guest and not stay:
		return {"kind": "none"}
	g = None
	if guest:
		from kamra.authz import assert_guest_access
		assert_guest_access(guest)
		g = frappe.db.get_value(
			"Guest", guest, ["name", "full_name", "vip", "guest_category",
			                 "guest_notes", "phone"], as_dict=True)
	out = {
		"kind": "in_house" if stay else "customer",
		"guest": {
			"name": g.name, "full_name": g.full_name, "vip": g.vip,
			"category": g.guest_category, "notes": g.guest_notes,
			"phone": _shown_phone(g.phone),
		} if g else None,
		"allergy_note": allergy,
		"stay": {
			"reservation": stay.name, "guest_name": stay.guest_name,
			"room_number": frappe.db.get_value("Room", stay.room, "room_number")
			               or (stay.room or "").split("-")[-1] if stay.room else None,
			"status": stay.status,
			"check_in_date": str(stay.check_in_date or ""),
			"check_out_date": str(stay.check_out_date or ""),
			"room_charges_allowed": 0 if stay.room_charges_allowed is not None
			                        and not cint(stay.room_charges_allowed) else 1,
		} if stay else None,
	}
	out["history"] = _outlet_history(outlet, order, g, stay)
	return out


def _outlet_history(outlet: str, order: str | None, g, stay) -> dict:
	"""This guest's bills at this outlet: by profile, by the stay, or by the
	phone a takeaway was taken on."""
	or_filters = []
	if g:
		or_filters.append(["guest", "=", g.name])
		if g.phone:
			or_filters.append(["customer_phone", "=", g.phone])
	if stay:
		or_filters.append(["reservation", "=", stay.name])
	if not or_filters:
		return {"visits": 0, "spend": 0, "last_visit": None, "orders": []}
	filters = {"outlet": outlet, "status": ["!=", "Cancelled"]}
	if order:
		filters["name"] = ["!=", order]
	rows = frappe.get_all(
		"POS Order", filters=filters, or_filters=or_filters,
		fields=["name", "creation", "order_total", "status", "paid", "nc",
		        "posted_to_folio", "kot_fired", "order_type", "table_no", "room"],
		order_by="creation desc", limit=200)
	recent = rows[:8]
	what: dict[str, list] = {}
	if recent:
		for it in frappe.get_all(
				"POS Order Item",
				filters={"parent": ["in", [r.name for r in recent]],
				         "parenttype": "POS Order", "voided": 0},
				fields=["parent", "item_name", "qty"], order_by="idx asc"):
			what.setdefault(it.parent, []).append(
				f"{it.item_name} x{float(it.qty or 0):g}")
	spend = sum(float(r.order_total or 0) for r in rows
	            if r.status == "Delivered" and not r.nc)
	return {
		"visits": len({str(r.creation)[:10] for r in rows}),
		"bills": len(rows),
		"spend": round(spend, 2),
		"last_visit": str(rows[0].creation)[:10] if rows else None,
		"orders": [{
			"name": r.name, "time": str(r.creation), "amount": float(r.order_total or 0),
			"state": _order_list_state(r), "label": _label(r),
			"items": ", ".join(what.get(r.name, [])[:6]),
		} for r in recent],
	}


@frappe.whitelist()
@require_perm("POS Order", "take_orders")
def bill_data(order: str):
	"""Everything the thermal bill print needs: outlet and property names,
	live lines, the discount, and the CGST/SGST split at the outlet's rate."""
	doc = frappe.get_doc("POS Order", order)
	outlet = frappe.db.get_value(
		"POS Outlet", doc.outlet, ["outlet_name", "gst_rate"], as_dict=True)
	property_name = frappe.db.get_value(
		"Property", doc.property, "property_name") or doc.property
	gst_rate = 0.0 if doc.nc else float(outlet.gst_rate or 5)
	taxable = float(doc.order_total or 0)
	gst_amount = round(taxable * gst_rate / 100, 2)
	# the tax is named and split the country's way (CGST+SGST in India,
	# a single VAT line in the Gulf)
	from kamra import localization as loc
	pack = loc.pack_for(doc.property)
	prop_doc = frappe.get_cached_doc("Property", doc.property)
	tax_label = pack.locale(prop_doc).get("tax_label") or "Tax"
	split = loc.tax_split(pack, prop_doc, None)
	return {
		"tax_label": tax_label,
		"tax_parts": [
			{"label": label.upper(), "rate": round(gst_rate * float(share), 4),
			 "amount": round(gst_amount * float(share), 2)}
			for label, share in split],
		"statutory": loc.invoice_print_block(pack, "POS Order", doc.name)
		             if doc.paid else None,
		"order": doc.name, "kot_no": doc.kot_no, "status": doc.status,
		"property_name": property_name, "outlet_name": outlet.outlet_name,
		"order_type": doc.order_type, "table_no": doc.table_no,
		"room_no": (doc.room or "").split("-")[-1] if doc.room else None,
		"customer_name": doc.customer_name,
		"customer_phone": doc.customer_phone,
		"delivery_address": doc.delivery_address,
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
		"nc": doc.nc, "nc_authorized_by": doc.nc_authorized_by,
		"nc_note": doc.nc_note,
	}


@frappe.whitelist()
@require_perm("POS Order", "take_orders")
def outlet_dashboard(outlet: str, date: str | None = None,
                     to_date: str | None = None):
	"""One shift at a glance: what the outlet sold, what's still open, the
	exceptions that need a manager's eye (NC, voids, cancellations), and how
	fast the kitchen is turning tickets. Defaults to today."""
	assert_record_access("POS Outlet", outlet)
	from kamra.business_date import report_range_end

	day = frappe.utils.getdate(date) if date else frappe.utils.getdate()
	start, end = f"{day} 00:00:00", f"{report_range_end(day, to_date)} 23:59:59"

	orders = frappe.get_all(
		"POS Order",
		filters={"outlet": outlet, "creation": ["between", [start, end]]},
		fields=["name", "status", "order_type", "room", "table_no",
		        "customer_name", "order_total", "subtotal", "paid",
		        "payment_mode", "nc", "nc_authorized_by", "nc_note", "guests",
		        "posted_to_folio", "notes", "kot_no", "creation", "modified",
		        "cancel_reason"])
	names = [o.name for o in orders]
	items = frappe.get_all(
		"POS Order Item",
		filters={"parent": ["in", names], "parenttype": "POS Order"},
		fields=["parent", "item_name", "qty", "rate", "voided",
		        "void_reason", "fired_at", "prepared_at"]) if names else []

	closed = [o for o in orders if o.status == "Delivered"]
	sold = [o for o in closed if not o.nc]
	open_bills = [o for o in orders if o.status in ("Placed", "Confirmed", "Preparing")]
	cancelled = [o for o in orders if o.status == "Cancelled"]
	nc_bills = [o for o in closed if o.nc]

	gross = sum(float(o.order_total or 0) for o in sold)
	covers = sum(int(o.guests or 0) for o in closed)

	def bucket(rows, key):
		out: dict[str, dict] = {}
		for o in rows:
			k = key(o) or "Other"
			b = out.setdefault(k, {"bills": 0, "total": 0.0})
			b["bills"] += 1
			b["total"] += float(o.order_total or 0)
		return [{"label": k, **v} for k, v in
		        sorted(out.items(), key=lambda kv: -kv[1]["total"])]

	def tender(o) -> str:
		if o.posted_to_folio:
			return "Room folio"
		return o.payment_mode or "Unsettled"

	# what actually sold (live lines of closed, non-NC bills)
	sold_names = {o.name for o in sold}
	top: dict[str, dict] = {}
	for it in items:
		if it.parent not in sold_names or it.voided:
			continue
		t = top.setdefault(it.item_name, {"qty": 0.0, "amount": 0.0})
		t["qty"] += float(it.qty or 0)
		t["amount"] += float(it.qty or 0) * float(it.rate or 0)
	top_items = [{"item_name": k, **v} for k, v in
	             sorted(top.items(), key=lambda kv: -kv[1]["qty"])][:10]

	# a cancelled bill voids every line; those show once, as the cancellation
	cancelled_names = {o.name for o in cancelled}
	cancelled_value: dict[str, float] = {}
	for it in items:
		if it.parent in cancelled_names and it.voided:
			cancelled_value[it.parent] = cancelled_value.get(it.parent, 0.0) \
				+ float(it.qty or 0) * float(it.rate or 0)
	voids = [{
		"order": it.parent,
		"label": _label(next((o for o in orders if o.name == it.parent), {"name": it.parent})),
		"item_name": it.item_name, "qty": it.qty,
		"amount": float(it.qty or 0) * float(it.rate or 0),
		"reason": it.void_reason,
	} for it in items if it.voided and it.parent not in cancelled_names]

	# kitchen pace: fired -> prepared, over lines that finished today
	waits = []
	for it in items:
		if it.fired_at and it.prepared_at:
			secs = (frappe.utils.get_datetime(it.prepared_at)
			        - frappe.utils.get_datetime(it.fired_at)).total_seconds()
			if secs >= 0:
				waits.append(secs)
	avg_fire_to_ready = round(sum(waits) / len(waits) / 60, 1) if waits else None

	def cancel_reason(o) -> str | None:
		if o.get("cancel_reason"):
			return o.cancel_reason
		for line in reversed((o.notes or "").splitlines()):
			if line.startswith("Cancelled: "):
				return line[len("Cancelled: "):]
		return None

	return {
		"outlet": outlet, "date": str(day), "to_date": end[:10],
		"gross_sales": round(gross, 2),
		"bills": len(sold),
		"covers": covers,
		"avg_bill": round(gross / len(sold), 2) if sold else 0,
		"by_order_type": bucket(sold, lambda o: o.order_type),
		"by_tender": bucket(sold, tender),
		"open_bills": [{
			"name": o.name, "label": _label(o), "status": o.status,
			"order_type": o.order_type, "order_total": o.order_total,
			"kot_no": o.kot_no, "creation": str(o.creation),
		} for o in sorted(open_bills, key=lambda o: o.creation)],
		"nc": {
			"count": len(nc_bills),
			# an NC bill's order_total is forced to zero; what it *cost* the
			# house is the subtotal it would have billed
			"value": round(sum(float(o.subtotal or 0) for o in nc_bills), 2),
			"bills": [{
				"name": o.name, "label": _label(o), "subtotal": o.subtotal,
				"authorized_by": o.nc_authorized_by, "note": o.nc_note,
			} for o in nc_bills],
		},
		"voids": voids,
		"cancellations": [{
			"name": o.name, "label": _label(o),
			# cancelled bills void their lines; before that they kept a total
			"order_total": round(cancelled_value.get(o.name) or float(o.order_total or 0), 2),
			"reason": cancel_reason(o),
		} for o in cancelled],
		"top_items": top_items,
		"avg_fire_to_ready_mins": avg_fire_to_ready,
	}


@frappe.whitelist()
@require_perm("POS Order", "manage_outlet")
def speed_check(property: str, outlet: str | None = None, echo: int = 0):
	"""Why does the POS feel slow here? Times what a till and a kitchen
	display ask for on every refresh and reports the server's set-up, so
	support can tell our code from the hosting in a minute. Read-only.

	With echo=1 it also sends a realtime ping to the caller; the browser
	times how long it takes to arrive, which proves live updates work."""
	from time import perf_counter

	from kamra.authz import assert_property_access
	assert_property_access(property)
	outlet = outlet or frappe.db.get_value(
		"POS Outlet", {"property": property, "disabled": 0}, "name")

	timings = {}
	t0 = perf_counter()
	frappe.db.sql("select 1")
	timings["database_ms"] = round((perf_counter() - t0) * 1000, 1)
	if outlet:
		t0 = perf_counter()
		open_orders(outlet)
		timings["open_bills_ms"] = round((perf_counter() - t0) * 1000, 1)
		t0 = perf_counter()
		kitchen_queue(property, outlet=outlet)
		timings["kitchen_display_ms"] = round((perf_counter() - t0) * 1000, 1)

	try:
		from frappe.utils.background_jobs import get_workers
		workers = len(get_workers())
	except Exception:
		workers = None
	conf = frappe.conf
	setup = {
		"background_workers": workers,
		"developer_mode": bool(conf.get("developer_mode")),
		"socketio_configured": bool(conf.get("socketio_port")),
		"gunicorn_workers": conf.get("gunicorn_workers"),
	}
	if int(echo or 0):
		frappe.publish_realtime("kamra_speed_ping", {"at": frappe.utils.now()},
		                        user=frappe.session.user)
	return {"outlet": outlet, "server": timings, "setup": setup}
