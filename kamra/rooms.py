"""Rooms - one place to see and manage every room.

The Rooms screen (/kamra/room-board) reads from here: a board of every
room with what is happening in it today, one room's full story (status,
current stay, the next weeks, who stayed, who cleaned, tickets, moves)
and per-room numbers (most used, least sold, revenue, out-of-order days,
cleaning time).

Everything here only reads. Changing a room goes through the writers that
already exist: set_housekeeping_status, create_room_block /
release_room_block, check_in / check_out and move_reservation.
"""

import json

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, get_datetime, getdate, nowdate

from kamra.api import HK_SUPERVISOR, _is_room_supervisor, _stay_balances
from kamra.authz import ADMIN, assert_property_access, require_roles

# who may look at rooms: the desk, housekeeping supervisors, night audit,
# revenue, and the agent. Admins always pass.
BOARD_ROLES = ("Front Desk", HK_SUPERVISOR, "Night Auditor", "Revenue Manager",
               "Finance", "Kamra Agent")
# who may take a room out of service (the Room Blocks endpoints' gate)
_BLOCK_ROLES = {"Front Desk", "Kamra Agent", *ADMIN}
# who sees money on the room screens
_MONEY_ROLES = {"Front Desk", "Revenue Manager", "Finance", "Night Auditor",
                "Kamra Agent", *ADMIN}
_DESK_ROLES = {"Front Desk", "Kamra Agent", *ADMIN}

INSIGHT_WINDOWS = (7, 30, 90, 180, 365)
INSIGHTS_CACHE_SECONDS = 600
# a clean that took longer than this was left open, not worked on
_MAX_CLEAN_MINUTES = 8 * 60


def _roles() -> set:
	return set(frappe.get_roles())


def _can(roles: set) -> bool:
	mine = _roles()
	admin = frappe.session.user == "Administrator"
	return bool(admin or (mine & roles))


def _surname(name: str | None) -> str | None:
	parts = (name or "").strip().split()
	return parts[-1] if parts else None


def _user_names(users) -> dict:
	users = sorted({u for u in users if u})
	if not users:
		return {}
	return {u.name: u.full_name or u.name for u in frappe.get_all(
		"User", filters={"name": ("in", users)}, fields=["name", "full_name"])}


def _room_or_404(room: str) -> dict:
	r = frappe.db.get_value(
		"Room", room,
		["name", "property", "room_number", "room_type", "floor",
		 "housekeeping_status", "occupancy_status", "notes"], as_dict=True)
	if not r:
		frappe.throw(_("Room {0} not found.").format(room), frappe.DoesNotExistError)
	assert_property_access(r.property)
	return r


# --- the board -----------------------------------------------------------------

@frappe.whitelist()
@require_roles(*BOARD_ROLES)
def rooms_board(property: str):
	"""Every room of the property as a tile: housekeeping status, who is in
	it, who arrives or leaves today, whether it is out of service, and its
	open housekeeping task. One call, a fixed number of queries."""
	assert_property_access(property)
	today = getdate(nowdate())
	rooms = frappe.get_all(
		"Room", filters={"property": property},
		fields=["name", "room_number", "room_type", "floor",
		        "housekeeping_status", "occupancy_status"],
		order_by="room_number asc")
	rt_names = {rt.name: rt.room_type_name for rt in frappe.get_all(
		"Room Type", filters={"property": property},
		fields=["name", "room_type_name"])}
	in_house = {r.room: r for r in frappe.get_all(
		"Reservation",
		filters={"property": property, "status": "Checked In", "room": ("is", "set")},
		fields=["name", "room", "guest_name", "check_in_date", "check_out_date",
		        "is_day_use"])}
	arrivals = {}
	for r in frappe.get_all(
			"Reservation",
			filters={"property": property, "status": "Confirmed",
			         "room": ("is", "set"), "check_in_date": today},
			fields=["name", "room", "guest_name", "eta"], order_by="creation asc"):
		arrivals.setdefault(r.room, r)
	blocks = {}
	for b in frappe.get_all(
			"Room Block",
			filters={"property": property, "block_status": "Active",
			         "from_date": ("<=", today), "to_date": (">", today)},
			fields=["name", "room", "reason", "from_date", "to_date", "note"],
			order_by="from_date asc"):
		blocks.setdefault(b.room, b)
	tasks = {}
	for t in frappe.get_all(
			"Housekeeping Task",
			filters={"property": property, "status": ("in", ["Pending", "In Progress"])},
			fields=["name", "room", "task_type", "status", "priority",
			        "assigned_to_user", "due_by"],
			order_by="creation asc"):
		tasks.setdefault(t.room, t)
	names = _user_names(t.assigned_to_user for t in tasks.values())
	for r in rooms:
		r["room_type_name"] = rt_names.get(r.room_type, r.room_type)
		stay = in_house.get(r.name)
		r["stay"] = {
			"reservation": stay.name, "guest_name": stay.guest_name,
			"surname": _surname(stay.guest_name),
			"check_in_date": str(stay.check_in_date),
			"check_out_date": str(stay.check_out_date),
			"departing_today": getdate(stay.check_out_date) <= today,
			"day_use": bool(stay.is_day_use),
		} if stay else None
		arr = arrivals.get(r.name)
		r["arrival"] = {
			"reservation": arr.name, "guest_name": arr.guest_name,
			"surname": _surname(arr.guest_name),
			"eta": str(arr.eta)[:5] if arr.eta else None,
		} if arr else None
		blk = blocks.get(r.name)
		r["block"] = {
			"name": blk.name, "reason": blk.reason,
			"from_date": str(blk.from_date), "to_date": str(blk.to_date),
			"note": blk.note,
		} if blk else None
		t = tasks.get(r.name)
		r["task"] = {
			"name": t.name, "type": t.task_type, "status": t.status,
			"priority": t.priority,
			"assignee": names.get(t.assigned_to_user) or t.assigned_to_user,
		} if t else None
	return {
		"date": str(today),
		"rooms": rooms,
		"room_types": [{"name": k, "room_type_name": v} for k, v in
		               sorted(rt_names.items(), key=lambda kv: kv[1] or "")],
		"can": _permissions(),
	}


def _permissions() -> dict:
	return {
		"supervise": _is_room_supervisor(),
		"block": _can(_BLOCK_ROLES),
		"desk": _can(_DESK_ROLES),
		"money": _can(_MONEY_ROLES),
	}


# --- one room ------------------------------------------------------------------

@frappe.whitelist()
@require_roles(*BOARD_ROLES)
def room_detail(room: str):
	"""Everything about one room right now: what it is, its status, who is
	in it (with the balance), who arrives next, whether it is held out of
	service, and its open housekeeping work."""
	r = _room_or_404(room)
	today = getdate(nowdate())
	rt = frappe.db.get_value(
		"Room Type", r.room_type,
		["name", "room_type_name", "room_category", "description", "bed_type",
		 "room_view", "amenities", "air_conditioning", "bathroom",
		 "smoking_allowed", "kitchen", "adults_capacity", "children_capacity",
		 "max_extra_beds", "image"], as_dict=True) or {}
	photos = []
	if rt.get("image"):
		photos.append(rt.get("image"))
	if rt:
		photos += [m.url for m in frappe.get_all(
			"Room Type Media", filters={"parent": rt.name, "parenttype": "Room Type"},
			fields=["url", "media_type"], order_by="idx asc")
			if m.url and (m.media_type or "Image") == "Image"]
	stay = frappe.get_all(
		"Reservation",
		filters={"room": room, "status": "Checked In"},
		fields=["name", "guest", "guest_name", "check_in_date", "check_out_date",
		        "nights", "adults", "children", "is_day_use", "company"],
		order_by="check_in_date desc", limit=1)
	stay = stay[0] if stay else None
	nxt = frappe.get_all(
		"Reservation",
		filters={"room": room, "status": "Confirmed", "check_in_date": (">=", today)},
		fields=["name", "guest", "guest_name", "check_in_date", "check_out_date",
		        "nights", "adults", "children", "eta"],
		order_by="check_in_date asc", limit=1)
	nxt = nxt[0] if nxt else None
	can = _permissions()
	if stay:
		stay["check_in_date"] = str(stay.check_in_date)
		stay["check_out_date"] = str(stay.check_out_date)
		stay["departing_today"] = getdate(stay.check_out_date) <= today
		if can["money"]:
			m = _stay_balances([stay.name]).get(stay.name) or {}
			stay["total"] = m.get("total", 0.0)
			stay["paid"] = m.get("paid", 0.0)
			stay["balance_due"] = m.get("due", 0.0)
	if nxt:
		nxt["arriving_today"] = getdate(nxt.check_in_date) == today
		nxt["check_in_date"] = str(nxt.check_in_date)
		nxt["check_out_date"] = str(nxt.check_out_date)
		nxt["eta"] = str(nxt.eta)[:5] if nxt.eta else None
	blocks = frappe.get_all(
		"Room Block",
		filters={"room": room, "block_status": "Active", "to_date": (">", today)},
		fields=["name", "reason", "from_date", "to_date", "note"],
		order_by="from_date asc")
	for b in blocks:
		b["current"] = getdate(b.from_date) <= today
		b["from_date"], b["to_date"] = str(b.from_date), str(b.to_date)
	tasks = frappe.get_all(
		"Housekeeping Task",
		filters={"room": room, "status": ("in", ["Pending", "In Progress"])},
		fields=["name", "task_type", "status", "priority", "assigned_to_user",
		        "due_by", "notes"],
		order_by="creation asc")
	names = _user_names(t.assigned_to_user for t in tasks)
	for t in tasks:
		t["assignee"] = names.get(t.assigned_to_user) or t.assigned_to_user
		t["due_by"] = str(t.due_by) if t.due_by else None
	return {
		"date": str(today),
		"room": {**r, "room_type_name": rt.get("room_type_name") or r.room_type},
		"room_type": {k: v for k, v in rt.items() if k != "image"},
		"photos": photos,
		"stay": stay,
		"next_arrival": nxt,
		"blocks": blocks,
		"tasks": tasks,
		"can": can,
	}


@frappe.whitelist()
@require_roles(*BOARD_ROLES)
def room_availability(room: str, start_date: str | None = None, days: int = 14):
	"""This room, night by night: booked (by whom), held out of service, or
	free. Same overlap rules as the tape chart and the block guard (the
	check-out night is free; a day-use stay holds its own date)."""
	r = _room_or_404(room)
	start = getdate(start_date or nowdate())
	days = max(1, min(cint(days) or 14, 31))
	end = add_days(start, days)
	res = frappe.db.sql(
		"""
		SELECT name, guest_name, status, check_in_date, check_out_date
		FROM `tabReservation`
		WHERE room = %(room)s AND status IN ('Confirmed', 'Checked In')
		  AND check_in_date < %(end)s
		  AND GREATEST(check_out_date, DATE_ADD(check_in_date, INTERVAL 1 DAY)) > %(start)s
		ORDER BY check_in_date
		""", {"room": room, "start": start, "end": end}, as_dict=True)
	blocks = frappe.get_all(
		"Room Block",
		filters={"room": room, "block_status": "Active",
		         "from_date": ("<", end), "to_date": (">", start)},
		fields=["name", "reason", "from_date", "to_date", "note"])
	cells = []
	for i in range(days):
		d = getdate(add_days(start, i))
		cell = {"date": str(d), "state": "free"}
		for b in res:
			last = max(getdate(b.check_out_date), getdate(add_days(b.check_in_date, 1)))
			if getdate(b.check_in_date) <= d < last:
				cell = {"date": str(d), "state": "booked", "reservation": b.name,
				        "guest_name": b.guest_name, "status": b.status,
				        "arrives": getdate(b.check_in_date) == d}
				break
		else:
			for k in blocks:
				if getdate(k.from_date) <= d < getdate(k.to_date):
					cell = {"date": str(d), "state": "blocked", "block": k.name,
					        "reason": k.reason, "note": k.note}
					break
		cells.append(cell)
	summary = {s: sum(1 for c in cells if c["state"] == s)
	           for s in ("free", "booked", "blocked")}
	return {"room": r.name, "room_number": r.room_number, "start": str(start),
	        "days": days, "cells": cells, "summary": summary}


# --- history -------------------------------------------------------------------

def _task_timeline(task_names: list) -> dict:
	"""Who started, finished and checked each housekeeping task, and when -
	read from the task's change log (Housekeeping Task tracks changes)."""
	if not task_names:
		return {}
	rows = frappe.db.sql(
		"""
		SELECT docname, owner, creation, data FROM `tabVersion`
		WHERE ref_doctype = 'Housekeeping Task' AND docname IN %(names)s
		ORDER BY creation ASC
		""", {"names": tuple(task_names)}, as_dict=True)
	out: dict = {}
	for v in rows:
		try:
			changed = (json.loads(v.data or "{}") or {}).get("changed") or []
		except (TypeError, ValueError):
			continue
		for row in changed:
			if not row or row[0] != "status" or len(row) < 3:
				continue
			new = row[2]
			t = out.setdefault(v.docname, {})
			key = {"In Progress": "started", "Done": "done", "Verified": "verified"}.get(new)
			if key and key not in t:
				t[key] = {"by": v.owner, "at": v.creation}
	return out


def _minutes(a, b) -> float | None:
	if not a or not b:
		return None
	mins = (get_datetime(b) - get_datetime(a)).total_seconds() / 60
	# under a minute is a tap-through, over the cap a task left open
	return round(mins, 1) if 1 <= mins <= _MAX_CLEAN_MINUTES else None


def _posted_room_revenue(reservations: list) -> dict:
	"""Room charges posted to folios, per reservation (pre-tax)."""
	if not reservations:
		return {}
	rows = frappe.db.sql(
		"""
		SELECT COALESCE(fc.reservation, f.reservation) AS res,
		       COALESCE(SUM(fc.amount), 0) AS amount
		FROM `tabFolio Charge` fc
		JOIN `tabFolio` f ON fc.parent = f.name
		WHERE fc.charge_type IN ('Room', 'Rate Adjustment')
		  AND COALESCE(fc.reservation, f.reservation) IN %(names)s
		GROUP BY res
		""", {"names": tuple(reservations)}, as_dict=True)
	return {r.res: float(r.amount or 0) for r in rows}


def _parse_move(rationale: str) -> tuple[str | None, str | None]:
	"""'<old> → <new> · ...' (move_reservation's log line) -> (old, new)."""
	head = (rationale or "").split(" · ")[0]
	if "→" not in head:
		return None, None
	old, new = (s.strip() for s in head.split("→", 1))
	return (old if old and old != "None" else None), (new or None)


@frappe.whitelist()
@require_roles(*BOARD_ROLES)
def room_history(room: str, limit: int = 15):
	"""Who stayed in this room lately (nights, room revenue), who cleaned
	and checked it and when, its service tickets, and the guests moved in
	or out of it."""
	r = _room_or_404(room)
	limit = max(1, min(cint(limit) or 15, 50))
	money = _can(_MONEY_ROLES)

	stays = frappe.get_all(
		"Reservation",
		filters={"room": room, "status": ("in", ["Checked In", "Checked Out"])},
		fields=["name", "guest", "guest_name", "status", "check_in_date",
		        "check_out_date", "nights", "adults", "children",
		        "amount_before_tax", "room_assigned_by", "room_assigned_at",
		        "checked_in_by"],
		order_by="check_in_date desc", limit=limit)
	posted = _posted_room_revenue([s.name for s in stays]) if money else {}
	for s in stays:
		s["check_in_date"] = str(s.check_in_date)
		s["check_out_date"] = str(s.check_out_date)
		if money:
			got = posted.get(s.name)
			# what the folio shows once nights are posted; the booked
			# room amount until then
			s["revenue"] = got if got else float(s.amount_before_tax or 0)
			s["revenue_source"] = "posted" if got else "booked"
		s.pop("amount_before_tax", None)

	tasks = frappe.get_all(
		"Housekeeping Task",
		filters={"room": room},
		fields=["name", "task_type", "status", "priority", "assigned_to_user",
		        "creation", "modified", "modified_by", "notes"],
		order_by="creation desc", limit=limit)
	timeline = _task_timeline([t.name for t in tasks])
	status_log = frappe.get_all(
		"Agent Action Log",
		filters={"action_type": "room_status", "reference_doctype": "Room",
		         "reference_name": room},
		fields=["actor", "creation", "rationale"],
		order_by="creation desc", limit=limit)
	tickets = frappe.get_all(
		"Service Ticket",
		filters={"room": room},
		fields=["name", "subject", "category", "priority", "status",
		        "assigned_to_user", "creation", "resolved_on", "resolution_note"],
		order_by="creation desc", limit=limit)
	move_rows = frappe.get_all(
		"Agent Action Log",
		filters={"action_type": "room_move", "property": r.property,
		         "rationale": ("like", f"%{room}%")},
		fields=["actor", "creation", "rationale", "reference_name"],
		order_by="creation desc", limit=limit * 3)
	moves = []
	for m in move_rows:
		old, new = _parse_move(m.rationale)
		if room not in (old, new) or old == new:
			continue
		moves.append({"reservation": m.reference_name, "by": m.actor,
		              "at": str(m.creation), "direction": "in" if new == room else "out",
		              "other_room": old if new == room else new,
		              "note": " · ".join(m.rationale.split(" · ")[1:]) or None})
		if len(moves) >= limit:
			break
	res_names = {m["reservation"] for m in moves}
	guests = {x.name: x.guest_name for x in frappe.get_all(
		"Reservation", filters={"name": ("in", list(res_names))},
		fields=["name", "guest_name"])} if res_names else {}
	other_rooms = {m["other_room"] for m in moves if m["other_room"]}
	numbers = {x.name: x.room_number for x in frappe.get_all(
		"Room", filters={"name": ("in", list(other_rooms))},
		fields=["name", "room_number"])} if other_rooms else {}
	for m in moves:
		m["guest_name"] = guests.get(m["reservation"])
		m["other_room_number"] = numbers.get(m["other_room"], m["other_room"])

	users = set()
	for s in stays:
		users |= {s.room_assigned_by, s.checked_in_by}
	for t in tasks:
		users.add(t.assigned_to_user)
		for ev in timeline.get(t.name, {}).values():
			users.add(ev["by"])
	users |= {x.actor for x in status_log} | {x.assigned_to_user for x in tickets}
	users |= {m["by"] for m in moves}
	names = _user_names(users)

	def who(u):
		return names.get(u) or u

	for s in stays:
		s["room_assigned_by_name"] = who(s.room_assigned_by)
		s["checked_in_by_name"] = who(s.checked_in_by)
		s["room_assigned_at"] = str(s.room_assigned_at) if s.room_assigned_at else None
	hk = []
	for t in tasks:
		tl = timeline.get(t.name, {})
		done = tl.get("done") or tl.get("verified")
		# no change log (an old task): the last person to touch a closed
		# task is the best record there is
		if not done and t.status in ("Done", "Verified"):
			done = {"by": t.modified_by, "at": t.modified}
		hk.append({
			"task": t.name, "type": t.task_type, "status": t.status,
			"priority": t.priority,
			"assigned_to": who(t.assigned_to_user),
			"created": str(t.creation),
			"started_by": who(tl["started"]["by"]) if tl.get("started") else None,
			"started_at": str(tl["started"]["at"]) if tl.get("started") else None,
			"cleaned_by": who(done["by"]) if done else None,
			"cleaned_at": str(done["at"]) if done else None,
			"inspected_by": who(tl["verified"]["by"]) if tl.get("verified") else None,
			"inspected_at": str(tl["verified"]["at"]) if tl.get("verified") else None,
			"minutes": _minutes(tl.get("started", {}).get("at"),
			                    (tl.get("done") or tl.get("verified") or {}).get("at")),
			"notes": t.notes,
		})
	return {
		"room": r.name,
		"room_number": r.room_number,
		"stays": stays,
		"housekeeping": hk,
		"status_changes": [{"by": who(x.actor), "at": str(x.creation),
		                    "change": x.rationale} for x in status_log],
		"tickets": [{**x, "assigned_to": who(x.assigned_to_user),
		             "creation": str(x.creation),
		             "resolved_on": str(x.resolved_on) if x.resolved_on else None}
		            for x in tickets],
		"moves": moves,
		"money": money,
	}


# --- insights ------------------------------------------------------------------

def _overlap(a_start, a_end, b_start, b_end) -> int:
	"""Nights two half-open date ranges share."""
	s = max(getdate(a_start), getdate(b_start))
	e = min(getdate(a_end), getdate(b_end))
	return max(0, date_diff(e, s))


@frappe.whitelist()
@require_roles(*BOARD_ROLES)
def room_insights(property: str, days: int = 30, refresh: int = 0,
                  from_date: str | None = None, to_date: str | None = None):
	"""Per-room numbers for the last `days` nights (7, 30, 90, 180 or 365,
	up to yesterday): room nights sold and occupancy, room revenue posted to
	folios, out-of-service nights, and how long cleans take. Cached for a
	few minutes (refresh=1 recomputes); one query per measure, never one
	per room."""
	assert_property_access(property)
	days = cint(days) or 30
	if days not in INSIGHT_WINDOWS:
		days = 30
	money = _can(_MONEY_ROLES)
	today = nowdate()
	if from_date:  # a picked range: nights from_date..to_date
		to_date = to_date or str(add_days(today, -1))
		days = date_diff(to_date, from_date) + 1
		if not 1 <= days <= max(INSIGHT_WINDOWS):
			frappe.throw(f"Pick a range of 1 to {max(INSIGHT_WINDOWS)} days.")
		today = str(add_days(to_date, 1))
	key = f"kamra_room_insights:{property}:{days}:{today}:{int(money)}"
	cached = None if cint(refresh) else frappe.cache().get_value(key)
	if cached:
		return cached
	# a picked range counts cleans up to its last day; presets include today's
	clean_to = to_date if from_date else nowdate()
	out = _compute_insights(property, days, getdate(today), money, clean_to)
	frappe.cache().set_value(key, out, expires_in_sec=INSIGHTS_CACHE_SECONDS)
	return out


def _compute_insights(property: str, days: int, today, money: bool,
                      clean_to: str | None = None) -> dict:
	start = getdate(add_days(today, -days))
	end = today  # nights up to last night
	rooms = frappe.get_all(
		"Room", filters={"property": property},
		fields=["name", "room_number", "room_type", "floor"],
		order_by="room_number asc")
	rt_names = {rt.name: rt.room_type_name for rt in frappe.get_all(
		"Room Type", filters={"property": property},
		fields=["name", "room_type_name"])}
	stats = {r.name: {
		"room": r.name, "room_number": r.room_number,
		"room_type_name": rt_names.get(r.room_type, r.room_type),
		"floor": r.floor, "nights": 0, "stays": 0, "revenue": 0.0,
		"out_of_service_nights": 0, "cleans": 0, "clean_minutes": [],
	} for r in rooms}

	# nights actually stayed (in-house or departed), whatever was posted
	for s in frappe.db.sql(
			"""
			SELECT room, check_in_date, check_out_date FROM `tabReservation`
			WHERE property = %(p)s AND room IS NOT NULL AND room != ''
			  AND status IN ('Checked In', 'Checked Out')
			  AND check_in_date < %(end)s AND check_out_date > %(start)s
			""", {"p": property, "start": start, "end": end}, as_dict=True):
		row = stats.get(s.room)
		if not row:
			continue
		n = _overlap(s.check_in_date, s.check_out_date, start, end)
		if n:
			row["nights"] += n
			row["stays"] += 1

	if money:
		for x in frappe.db.sql(
				"""
				SELECT r.room AS room, COALESCE(SUM(fc.amount), 0) AS amount
				FROM `tabFolio Charge` fc
				JOIN `tabFolio` f ON fc.parent = f.name
				JOIN `tabReservation` r ON r.name = COALESCE(fc.reservation, f.reservation)
				WHERE f.property = %(p)s
				  AND fc.charge_type IN ('Room', 'Rate Adjustment')
				  AND fc.posting_date >= %(start)s AND fc.posting_date < %(end)s
				GROUP BY r.room
				""", {"p": property, "start": start, "end": end}, as_dict=True):
			if x.room in stats:
				stats[x.room]["revenue"] = float(x.amount or 0)

	# held out of sale: active blocks, and released ones up to their release
	for b in frappe.get_all(
			"Room Block",
			filters={"property": property, "from_date": ("<", end),
			         "to_date": (">", start)},
			fields=["room", "from_date", "to_date", "block_status", "released_on"]):
		row = stats.get(b.room)
		if not row:
			continue
		stop = getdate(b.to_date)
		if b.block_status == "Released" and b.released_on:
			stop = min(stop, getdate(b.released_on))
		row["out_of_service_nights"] += _overlap(b.from_date, stop, start, end)

	# cleaning time: from In Progress to Done, out of the task change log
	tasks = frappe.get_all(
		"Housekeeping Task",
		filters={"property": property,
		         "creation": ("between", [str(start), f"{clean_to or today} 23:59:59"]),
		         "task_type": ("!=", "Inspection"),
		         "status": ("in", ["Done", "Verified"])},
		fields=["name", "room"])
	timeline = _task_timeline([t.name for t in tasks])
	for t in tasks:
		row = stats.get(t.room)
		if not row:
			continue
		row["cleans"] += 1
		tl = timeline.get(t.name, {})
		mins = _minutes((tl.get("started") or {}).get("at"),
		                (tl.get("done") or tl.get("verified") or {}).get("at"))
		if mins is not None:
			row["clean_minutes"].append(mins)

	all_minutes = []
	out_rooms = []
	for row in stats.values():
		sellable = max(0, days - row["out_of_service_nights"])
		row["sellable_nights"] = sellable
		row["occupancy_pct"] = round(100 * row["nights"] / sellable, 1) if sellable else 0.0
		mins = row.pop("clean_minutes")
		all_minutes += mins
		row["avg_clean_minutes"] = round(sum(mins) / len(mins), 1) if mins else None
		row["revenue"] = round(row["revenue"], 2) if money else None
		out_rooms.append(row)

	total_nights = sum(r["nights"] for r in out_rooms)
	sellable = sum(r["sellable_nights"] for r in out_rooms)
	by_use = sorted(out_rooms, key=lambda r: (-r["nights"], r["room_number"] or ""))
	least = sorted(out_rooms, key=lambda r: (r["occupancy_pct"], r["nights"],
	                                          r["room_number"] or ""))
	return {
		"property": property,
		"days": days,
		"from_date": str(start),
		"to_date": str(add_days(end, -1)),
		"money": money,
		"summary": {
			"rooms": len(out_rooms),
			"room_nights": total_nights,
			"occupancy_pct": round(100 * total_nights / sellable, 1) if sellable else 0.0,
			"revenue": round(sum(r["revenue"] or 0 for r in out_rooms), 2) if money else None,
			"out_of_service_nights": sum(r["out_of_service_nights"] for r in out_rooms),
			"avg_clean_minutes": round(sum(all_minutes) / len(all_minutes), 1)
			if all_minutes else None,
			"timed_cleans": len(all_minutes),
		},
		"most_used": by_use[:5],
		"least_used": least[:5],
		"rooms": out_rooms,
	}
