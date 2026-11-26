"""Unit owners (#639).

A property manager links each owner to the units they own and to one or
more logins. Those logins get the Owner role and Frappe User Permissions
on just those rooms (and the property, so the property switcher works).
The portal they see is this module: occupancy, bookings and room revenue.
Guest name and phone stay off unless the admin turns Show guest contact
on. Identity documents are never returned.

An owner holds units one by one and/or whole unit types (every unit of
the type, including ones added later). Several logins can belong to one
owner (the owner and their accountant).

Read only and Manage are stored on the owner record. Role Profiles from
the unmerged permissions work (#421) are not available yet, so this
record is the switch. Read only is the calendar, occupancy, bookings and
the monthly statement. Manage can also hold one of their own units out
of sale, book a stay in one of their own units, and set the rate of a
unit type they own outright. Bookings and rates go through the desk's
own functions (create_booking, set_room_rate) as the governed agent
login, so the clash, capacity, guardrail and hurdle checks all apply.
Neither level opens the desk.

The monthly statement is room revenue per unit, less commission (the
unit's own percent, else the owner's) and the owner's costs that month.
"""

from __future__ import annotations

from contextlib import contextmanager

import frappe
from frappe import _
from frappe.utils import (
	add_days,
	cint,
	date_diff,
	flt,
	get_last_day,
	getdate,
	nowdate,
	validate_email_address,
)

from kamra.authz import require_roles
from kamra.staff import ROLE_NAMES

OWNER_ROLE = "Owner"
# a login that also holds a desk role keeps the property permissions an
# admin already gave them; a dedicated owner login is scoped exactly
STAFF_ROLES = set(ROLE_NAMES) - {OWNER_ROLE}


def ensure_owner_role() -> None:
	if not frappe.db.exists("Role", OWNER_ROLE):
		frappe.get_doc({
			"doctype": "Role", "role_name": OWNER_ROLE, "desk_access": 0,
		}).insert(ignore_permissions=True)


def sync_user_access(user: str) -> None:
	"""Make this login's Owner role and room permissions match the Unit
	Owner records that list them. Called when an owner record is saved
	or deleted."""
	if not user or not frappe.db.exists("User", user):
		return
	ensure_owner_role()
	links = frappe.get_all("Unit Owner User", filters={"user": user}, pluck="parent")
	rooms: set[str] = set()
	properties: set[str] = set()
	for name in links:
		doc = frappe.get_doc("Unit Owner", name)
		properties.add(doc.property)
		rooms.update(owned_rooms(doc))
	user_doc = frappe.get_doc("User", user)
	held = {r.role for r in user_doc.roles}
	user_doc.flags.ignore_permissions = True
	if links and OWNER_ROLE not in held:
		user_doc.add_roles(OWNER_ROLE)
		held.add(OWNER_ROLE)
	if not links and OWNER_ROLE in held:
		user_doc.remove_roles(OWNER_ROLE)
		held.discard(OWNER_ROLE)
	want = {("Room", room) for room in rooms} | {("Property", prop) for prop in properties}
	existing = frappe.get_all(
		"User Permission",
		filters={"user": user, "allow": ["in", ["Room", "Property"]]},
		fields=["name", "allow", "for_value"])
	have = {(row.allow, row.for_value): row.name for row in existing}
	# a dedicated owner login must not keep a room they were taken off
	if not (held & STAFF_ROLES):
		for key, name in have.items():
			if key not in want:
				frappe.delete_doc("User Permission", name, ignore_permissions=True)
	for allow, value in want:
		if (allow, value) not in have:
			frappe.get_doc({
				"doctype": "User Permission",
				"user": user,
				"allow": allow,
				"for_value": value,
			}).insert(ignore_permissions=True)
	frappe.clear_cache(user=user)


@contextmanager
def _without_desk_permission():
	"""Load or write a record the owner is not given a desk permission for.
	A desk permission on Unit Owner would show every owner at the property."""
	previous = bool(frappe.flags.ignore_permissions)
	frappe.flags.ignore_permissions = True
	try:
		yield
	finally:
		frappe.flags.ignore_permissions = previous


def _owner_docs(user: str, property: str) -> list:
	names = frappe.get_all("Unit Owner User", filters={"user": user}, pluck="parent")
	docs = []
	with _without_desk_permission():
		for name in names:
			doc = frappe.get_doc("Unit Owner", name)
			if doc.property == property:
				docs.append(doc)
	return docs


def owned_rooms(doc) -> list[str]:
	"""The units this owner record covers: those listed, then every unit of
	its unit types, in that order, once each."""
	rooms = [r.room for r in doc.units if r.room]
	types = [r.room_type for r in doc.get("room_types") or [] if r.room_type]
	if types:
		for room in frappe.get_all("Room", filters={"property": doc.property,
		                                            "room_type": ["in", types]},
		                           pluck="name", order_by="room_number asc"):
			if room not in rooms:
				rooms.append(room)
	return rooms


def on_room_change(doc, method=None):
	"""A unit added to, or moved into, a unit type an owner holds is theirs
	at once: re-scope the logins of the owners at that property who hold
	unit types."""
	parents = set(frappe.get_all("Unit Owner Room Type", pluck="parent",
	                             filters={"parenttype": "Unit Owner"}))
	if not parents:
		return
	users = set()
	for name in frappe.get_all("Unit Owner", pluck="name",
	                           filters={"property": doc.property,
	                                    "name": ["in", list(parents)]}):
		users.update(frappe.get_all("Unit Owner User", pluck="user",
		                            filters={"parent": name}))
	for user in users:
		sync_user_access(user)


def _portal(docs: list, property: str, from_date: str, to_date: str) -> dict:
	rooms = []
	seen = set()
	show = False
	access = "Read only"
	names = []
	for doc in docs:
		names.append(doc.owner_name)
		show = show or bool(doc.show_guest_contact)
		if doc.access == "Manage":
			access = "Manage"
		for room in owned_rooms(doc):
			if room not in seen:
				seen.add(room)
				rooms.append(room)
	meta = {
		r.name: r for r in frappe.get_all(
			"Room", filters={"name": ["in", rooms or ["-1"]]},
			fields=["name", "room_number", "occupancy_status"])
	}
	start, end = getdate(from_date), getdate(to_date)
	if end < start:
		start, end = end, start
	stays = frappe.get_all(
		"Reservation",
		filters={
			"property": property,
			"room": ["in", rooms or ["-1"]],
			"status": ["in", ["Confirmed", "Checked In", "Checked Out"]],
			"check_in_date": ["<=", str(end)],
			"check_out_date": [">", str(start)],
		},
		fields=["name", "room", "status", "check_in_date", "check_out_date",
		        "guest", "guest_name"],
		order_by="check_in_date asc",
		limit=200,
	)
	guests = {}
	if show:
		ids = list({s.guest for s in stays if s.guest})
		if ids:
			for g in frappe.get_all(
				"Guest", filters={"name": ["in", ids]},
				fields=["name", "first_name", "last_name", "phone"]):
				guests[g.name] = g
	span = date_diff(end, start) + 1
	sold = 0
	bookings = []
	for stay in stays:
		arrive = max(getdate(stay.check_in_date), start)
		leave = min(getdate(stay.check_out_date), add_days(end, 1))
		sold += max(0, date_diff(leave, arrive))
		guest = guests.get(stay.guest) if show else None
		full = ""
		phone = None
		if guest:
			full = " ".join(p for p in (guest.first_name, guest.last_name) if p)
			phone = guest.phone or None
		elif show and stay.guest_name:
			full = stay.guest_name
		bookings.append({
			"reservation": stay.name,
			"room": stay.room,
			"room_number": (meta.get(stay.room) or {}).get("room_number") or "",
			"status": stay.status,
			"check_in": str(stay.check_in_date),
			"check_out": str(stay.check_out_date),
			"guest": full or "Guest",
			"phone": phone if show else None,
		})
	blocks = frappe.get_all(
		"Room Block",
		filters={
			"property": property,
			"room": ["in", rooms or ["-1"]],
			"block_status": "Active",
			"from_date": ["<=", str(end)],
			"to_date": [">", str(start)],
		},
		fields=["name", "room", "from_date", "to_date", "reason"],
		order_by="from_date asc",
		limit=200,
	)
	block_rows = [{
		"name": row.name,
		"room": row.room,
		"room_number": (meta.get(row.room) or {}).get("room_number") or "",
		"from_date": str(row.from_date),
		"to_date": str(row.to_date),
		"reason": row.reason,
		"mine": row.reason == "Owner",
	} for row in blocks]
	revenue = 0.0
	by_room: dict[str, float] = {}
	if stays:
		room_of = {s.name: s.room for s in stays}
		for row in frappe.get_all(
			"Folio Charge",
			filters={
				"reservation": ["in", [s.name for s in stays]],
				"posting_date": ["between", [str(start), str(end)]],
				"charge_type": ["in", ["Room", "Extra Guests", "Cleaning Fee"]],
			},
			fields=["amount", "reservation"]):
			revenue += float(row.amount or 0)
			room = room_of.get(row.reservation)
			by_room[room] = by_room.get(room, 0.0) + float(row.amount or 0)
	units = [{
		"room": name,
		"room_number": (meta.get(name) or {}).get("room_number") or name,
		"occupancy_status": (meta.get(name) or {}).get("occupancy_status") or "",
		"revenue": round(by_room.get(name, 0.0), 2),
	} for name in rooms]
	occupancy = round(100 * sold / (len(rooms) * span), 1) if rooms and span else 0
	return {
		"owner_name": ", ".join(names),
		"access": access,
		"show_guest_contact": bool(show),
		"from_date": str(start),
		"to_date": str(end),
		"units": units,
		"occupancy_pct": occupancy,
		"room_nights": sold,
		"revenue": round(revenue, 2),
		"bookings": bookings,
		"blocks": block_rows,
	}


@frappe.whitelist()
@require_roles("Hotel Admin")
def desk(property: str) -> dict:
	"""Owners and units for the admin screen."""
	owners = frappe.get_all(
		"Unit Owner", filters={"property": property},
		fields=["name", "owner_name", "access", "show_guest_contact",
		        "commission_percent"],
		order_by="owner_name asc")
	for row in owners:
		units = frappe.get_all("Unit Owner Unit", filters={"parent": row.name},
		                       fields=["room", "commission_percent"], order_by="idx asc")
		row["units"] = [u.room for u in units]
		row["unit_commission"] = {u.room: u.commission_percent for u in units
		                          if u.commission_percent}
		row["room_types"] = frappe.get_all(
			"Unit Owner Room Type", filters={"parent": row.name}, pluck="room_type")
		row["users"] = frappe.get_all(
			"Unit Owner User", filters={"parent": row.name}, pluck="user")
		row["costs"] = frappe.get_all(
			"Unit Owner Cost", filters={"parent": row.name},
			fields=["posting_date", "room", "description", "amount"],
			order_by="posting_date desc", limit=50)
	rooms = frappe.get_all(
		"Room", filters={"property": property},
		fields=["name", "room_number"], order_by="room_number asc")
	room_types = frappe.get_all(
		"Room Type", filters={"property": property},
		fields=["name", "room_type_name"], order_by="room_type_name asc")
	return {"owners": owners, "rooms": rooms, "room_types": room_types}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin")
def save_owner(property: str, owner_name: str, rooms, users,
               access: str = "Read only", show_guest_contact: int = 0,
               commission_percent: float = 0, name: str | None = None,
               room_types=None, unit_commission=None) -> dict:
	"""Create or update one owner and rescope their logins. `room_types`
	gives the owner every unit of those types; `unit_commission`
	({room: percent}) overrides the owner's commission for single units.
	Costs are added with add_owner_cost and kept on a save."""
	if isinstance(rooms, str):
		rooms = frappe.parse_json(rooms)
	if isinstance(users, str):
		users = frappe.parse_json(users)
	if isinstance(room_types, str):
		room_types = frappe.parse_json(room_types)
	if isinstance(unit_commission, str):
		unit_commission = frappe.parse_json(unit_commission)
	unit_commission = unit_commission or {}
	rooms = [r for r in (rooms or []) if r]
	label = (owner_name or "").strip()
	users = [_ensure_login(u, label) for u in (users or []) if u]
	percent = flt(commission_percent)
	if percent < 0 or percent > 100:
		frappe.throw(_("Commission must be between 0 and 100."))
	payload = {
		"owner_name": label,
		"property": property,
		"access": access if access in ("Read only", "Manage") else "Read only",
		"show_guest_contact": 1 if cint(show_guest_contact) else 0,
		"commission_percent": percent,
		"units": [{"room": r, "commission_percent": flt(unit_commission.get(r)) or None}
		          for r in rooms],
		"room_types": [{"room_type": t} for t in (room_types or []) if t],
		"users": [{"user": u} for u in users],
	}
	if name and frappe.db.exists("Unit Owner", name):
		doc = frappe.get_doc("Unit Owner", name)
		if doc.property != property:
			frappe.throw(_("That owner belongs to another property."), frappe.PermissionError)
		doc.update(payload)
		doc.save()
	else:
		doc = frappe.get_doc({"doctype": "Unit Owner", **payload})
		doc.insert()
	return {"name": doc.name}


@frappe.whitelist()
@require_roles(OWNER_ROLE)
def my_portal(property: str, from_date: str | None = None,
              to_date: str | None = None) -> dict:
	"""The signed-in owner's own units. Another owner's units are absent,
	not redacted."""
	docs = _owner_docs(frappe.session.user, property)
	if not docs:
		frappe.throw(_("You don't have units at this property."), frappe.PermissionError)
	start = from_date or nowdate()
	end = to_date or start
	out = _portal(docs, property, start, end)
	out["priceable_types"] = _priceable_types(docs, property) if out["access"] == "Manage" else []
	return out


@frappe.whitelist()
@require_roles(OWNER_ROLE)
def my_overview(from_date: str | None = None, to_date: str | None = None,
                month: str | None = None) -> dict:
	"""Every property the signed-in owner has units at, side by side (#713):
	occupancy, room nights and room revenue per property, and with `month`
	each property's statement. Totals only when every property shares one
	currency: two currencies don't add up to one number."""
	from kamra.authz import restricted_properties
	from kamra.crs import _locale, _sum

	allowed = restricted_properties()
	by_property: dict[str, list] = {}
	with _without_desk_permission():
		for name in frappe.get_all("Unit Owner User", pluck="parent",
		                           filters={"user": frappe.session.user,
		                                    "parenttype": "Unit Owner"}):
			doc = frappe.get_doc("Unit Owner", name)
			if allowed is None or doc.property in allowed:
				by_property.setdefault(doc.property, []).append(doc)
	if not by_property:
		frappe.throw(_("You don't have units at any property."), frappe.PermissionError)
	start = from_date or nowdate()
	end = to_date or start
	span = date_diff(max(getdate(start), getdate(end)), min(getdate(start), getdate(end))) + 1
	rows = []
	for property, docs in by_property.items():
		part = _portal(docs, property, start, end)
		row = {
			"property": property,
			"property_name": frappe.get_cached_value("Property", property, "property_name") or property,
			**_locale(property),
			"units": len(part["units"]),
			"occupancy_pct": part["occupancy_pct"],
			"room_nights": part["room_nights"],
			"revenue": part["revenue"],
		}
		if month:
			s = statement(docs, property, month)
			row["statement"] = {k: s[k] for k in ("from_date", "to_date", "room_nights", "revenue",
			                                      "commission", "costs", "payout", "lines", "cost_lines")}
		rows.append(row)
	rows.sort(key=lambda r: r["property_name"])
	units = sum(r["units"] for r in rows)
	nights = sum(r["room_nights"] for r in rows)
	totals = {
		"units": units,
		"room_nights": nights,
		"occupancy_pct": round(100 * nights / (units * span), 1) if units and span else 0,
		"currency": rows[0]["currency"] if _sum(rows, "revenue") is not None else None,
		"revenue": _sum(rows, "revenue"),
	}
	if month:
		sheets = [{**r["statement"], "currency": r["currency"]} for r in rows]
		totals["statement"] = {k: _sum(sheets, k) for k in ("revenue", "commission", "costs", "payout")}
	return {"from_date": str(min(getdate(start), getdate(end))),
	        "to_date": str(max(getdate(start), getdate(end))),
	        "properties": rows, "totals": totals}


def _priceable_types(docs: list, property: str) -> list[dict]:
	"""Unit types every unit of which this owner manages: the ones whose
	rate they may set (set_unit_rate)."""
	mine = set()
	for doc in docs:
		if doc.access == "Manage":
			mine.update(owned_rooms(doc))
	out = []
	for rt in frappe.get_all("Room Type", filters={"property": property},
	                         fields=["name", "room_type_name"]):
		units = set(frappe.get_all("Room", pluck="name",
		                           filters={"property": property, "room_type": rt.name}))
		if units and units <= mine:
			out.append({"room_type": rt.name, "name": rt.room_type_name or rt.name})
	return out


def _ensure_login(email: str, owner_name: str) -> str:
	"""A new address becomes an owner login. No welcome mail: the admin
	sets the password from Staff & Access."""
	email = (email or "").strip().lower()
	if not validate_email_address(email):
		frappe.throw(_("{0} is not an email address.").format(email))
	if frappe.db.exists("User", email):
		kind = frappe.db.get_value("User", email, "user_type")
		if kind and kind != "System User":
			frappe.throw(_("{0} is a guest account, not a login.").format(email))
		return email
	first = (owner_name or email.split("@")[0]).split(" ")[0][:140]
	frappe.get_doc({
		"doctype": "User",
		"email": email,
		"first_name": first or email.split("@")[0],
		"enabled": 1,
		"user_type": "System User",
		"send_welcome_email": 0,
	}).insert(ignore_permissions=True)
	return email


def _managed_rooms(user: str, property: str) -> list[str]:
	docs = _owner_docs(user, property)
	if not docs:
		frappe.throw(_("You don't have units at this property."), frappe.PermissionError)
	rooms = []
	for doc in docs:
		if doc.access != "Manage":
			continue
		for room in owned_rooms(doc):
			if room not in rooms:
				rooms.append(room)
	if not rooms:
		frappe.throw(_("This login is read only."), frappe.PermissionError)
	return rooms


@frappe.whitelist()
@require_roles(OWNER_ROLE)
def my_statement(property: str, month: str) -> dict:
	"""One calendar month for the signed-in owner: room revenue per unit,
	commission (the unit's percent, else the owner's), the owner's costs
	dated in the month, and the payout. Guest names are not on it."""
	docs = _owner_docs(frappe.session.user, property)
	if not docs:
		frappe.throw(_("You don't have units at this property."), frappe.PermissionError)
	return statement(docs, property, month)


def statement(docs: list, property: str, month: str) -> dict:
	text = (month or "").strip()
	if len(text) < 7 or text[4] != "-":
		frappe.throw(_("Pick a month."))
	start = getdate(text[:7] + "-01")
	end = getdate(get_last_day(start))
	lines, costs = [], []
	for doc in docs:
		part = _portal([doc], property, str(start), str(end))
		own = {r.room: flt(r.commission_percent) for r in doc.units if r.commission_percent}
		nights = {}
		for b in part["bookings"]:
			arrive = max(getdate(b["check_in"]), start)
			leave = min(getdate(b["check_out"]), add_days(end, 1))
			nights[b["room"]] = nights.get(b["room"], 0) + max(0, date_diff(leave, arrive))
		for unit in part["units"]:
			percent = own.get(unit["room"], flt(doc.commission_percent))
			cut = round(unit["revenue"] * percent / 100, 2)
			lines.append({
				"owner_name": doc.owner_name, "room": unit["room"],
				"room_number": unit["room_number"],
				"room_nights": nights.get(unit["room"], 0),
				"revenue": unit["revenue"], "commission_percent": percent,
				"commission": cut,
			})
		for c in doc.get("costs") or []:
			if c.posting_date and start <= getdate(c.posting_date) <= end:
				costs.append({"owner_name": doc.owner_name, "date": str(c.posting_date),
				              "room": c.room, "description": c.description,
				              "amount": round(flt(c.amount), 2)})
	revenue = round(sum(r["revenue"] for r in lines), 2)
	commission = round(sum(r["commission"] for r in lines), 2)
	cost = round(sum(c["amount"] for c in costs), 2)
	return {
		"from_date": str(start),
		"to_date": str(end),
		"room_nights": sum(r["room_nights"] for r in lines),
		"revenue": revenue,
		"commission": commission,
		"costs": cost,
		"payout": round(revenue - commission - cost, 2),
		"lines": lines,
		"cost_lines": costs,
	}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin")
def add_owner_cost(owner: str, posting_date: str, description: str, amount: float,
                   room: str | None = None) -> dict:
	"""Charge a cost to an owner (cleaning, a repair, a fee). It comes off
	the payout of the month it is dated in."""
	doc = frappe.get_doc("Unit Owner", owner)
	from kamra.authz import assert_property_access
	assert_property_access(doc.property)
	if not (description or "").strip() or not flt(amount):
		frappe.throw(_("A cost needs a description and an amount."))
	if room and room not in owned_rooms(doc):
		frappe.throw(_("{0} is not one of this owner's units.").format(room))
	doc.append("costs", {"posting_date": posting_date, "room": room or None,
	                     "description": description.strip()[:140],
	                     "amount": round(flt(amount), 2)})
	doc.save()
	return {"name": doc.name, "costs": len(doc.costs)}


@frappe.whitelist(methods=["POST"])
@require_roles(OWNER_ROLE)
def block_unit(property: str, room: str, from_date: str, to_date: str,
               note: str | None = None) -> dict:
	"""Hold one of this login's own units. The desk's room-block record
	is what takes it off sale. A read-only owner cannot call this, and a
	manage login cannot hold a unit that is not theirs."""
	owned = _managed_rooms(frappe.session.user, property)
	if room not in owned:
		frappe.throw(_("You can only hold a unit you manage."), frappe.PermissionError)
	from kamra.savings import log_action
	try:
		# the owner has no desk permission on Room Block: the ownership check
		# above is the guard, and the doctype's own clash check still runs
		doc = frappe.get_doc({
			"doctype": "Room Block", "property": property, "room": room,
			"from_date": from_date, "to_date": to_date, "reason": "Owner",
			"note": (note or "").strip() or _("Owner hold"),
			"block_status": "Active",
		}).insert(ignore_permissions=True)
		log_action("room_block", "Room Block", doc.name, property,
		           rationale=f"Owner: {room} {from_date}→{to_date}")
		return {"name": doc.name}
	except frappe.ValidationError as exc:
		# the desk's clash message names the guest; an owner does not get that
		if "booked" in str(exc).lower():
			frappe.throw(_("That unit is already booked for those dates."),
			             frappe.ValidationError)
		raise


@frappe.whitelist(methods=["POST"])
@require_roles(OWNER_ROLE, scope={"name": "Room Block"})
def release_block(name: str) -> dict:
	"""Release a hold this owner placed. A maintenance hold stays."""
	with _without_desk_permission():
		doc = frappe.get_doc("Room Block", name)
		if doc.reason != "Owner" or doc.block_status != "Active":
			frappe.throw(_("You can only release a hold you placed."), frappe.PermissionError)
		owned = _managed_rooms(frappe.session.user, doc.property)
		if doc.room not in owned:
			frappe.throw(_("You can only hold a unit you manage."), frappe.PermissionError)
		doc.block_status = "Released"
		doc.released_by = frappe.session.user
		doc.released_on = frappe.utils.now_datetime()
		doc.save(ignore_permissions=True)
	from kamra.savings import log_action
	log_action("room_unblock", "Room Block", doc.name, doc.property,
	           rationale=f"owner released {doc.room}")
	return {"name": doc.name, "block_status": "Released"}


def _room_type_of(room: str) -> str:
	return frappe.db.get_value("Room", room, "room_type")


@frappe.whitelist(methods=["POST"])
@require_roles(OWNER_ROLE)
def book_unit(property: str, room: str, check_in_date: str, check_out_date: str,
              guest_name: str, adults: int = 1, children: int = 0,
              phone: str | None = None) -> dict:
	"""A Manage owner books a stay in one of their own units: a guest they
	found, or their own stay. It is the desk's create_booking, run as the
	governed agent login, so availability, capacity and pricing apply
	exactly as at the desk."""
	if room not in _managed_rooms(frappe.session.user, property):
		frappe.throw(_("You can only book a unit you manage."), frappe.PermissionError)
	if not (guest_name or "").strip():
		frappe.throw(_("Enter the guest's name."))
	from kamra.api import create_booking
	from kamra.authz import act_as
	from kamra.install import AGENT_EMAIL
	me = frappe.session.user
	try:
		with act_as(AGENT_EMAIL):
			out = create_booking(
				property=property, room_type=_room_type_of(room),
				check_in_date=check_in_date, check_out_date=check_out_date,
				guest_name=guest_name.strip(), phone=phone or None,
				adults=cint(adults) or 1, children=cint(children),
				room=room, assign_room=1, booked_by_name=me,
				booker_relation="Other")
	except frappe.ValidationError as exc:
		# the desk's clash message can name another guest
		if "booked" in str(exc).lower() or "available" in str(exc).lower():
			frappe.throw(_("That unit is not free for those dates."), frappe.ValidationError)
		raise
	from kamra.savings import log_action
	log_action("owner_booking", "Reservation", out["reservation"],
	           property, rationale=f"Booked by owner {me}: {room} "
	                               f"{check_in_date}→{check_out_date}")
	return {"reservation": out["reservation"], "status": out["status"]}


@frappe.whitelist(methods=["POST"])
@require_roles(OWNER_ROLE)
def set_unit_rate(property: str, room_type: str, start_date: str, end_date: str,
                  rate: float, reason: str = "") -> dict:
	"""A Manage owner sets the nightly rate of a unit type they own outright
	(every unit of that type is theirs): a rate there prices nobody else's
	unit. The desk's set_room_rate does it, so the property's guardrails
	and hurdle rates still bound it."""
	rooms = set(_managed_rooms(frappe.session.user, property))
	of_type = set(frappe.get_all("Room", pluck="name",
	                             filters={"property": property, "room_type": room_type}))
	if not of_type or not of_type <= rooms:
		frappe.throw(_("You can set the rate only of a unit type whose units are all yours."),
		             frappe.PermissionError)
	from kamra.api import set_room_rate
	from kamra.authz import act_as
	from kamra.install import AGENT_EMAIL
	me = frappe.session.user
	note = (reason or "").strip()
	with act_as(AGENT_EMAIL):
		return set_room_rate(property, room_type, start_date, end_date, flt(rate),
		                     reason=f"Owner {me}" + (f": {note}" if note else ""))
