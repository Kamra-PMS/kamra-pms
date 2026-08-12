# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Single source of truth for sellable inventory (ADR-003 / ADR-004).

All consumers — public search, desk calendar, CRS, MCP, ARI — should eventually
call ``availability()`` rather than re-implementing room/type SQL.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe
from frappe.utils import add_days, date_diff, getdate

# Single source: kamra.reservation_state (ADR-006).
from kamra.reservation_state import LIVE_STATUSES  # noqa: F401


def availability(
	property: str,
	*,
	siu: str | None = None,
	room_type: str | None = None,
	check_in_date: str,
	check_out_date: str,
	include_reasons: bool = False,
) -> list[dict[str, Any]]:
	"""Return sellable capacity for one SIU, all SIUs of a room type, or all
	active SIUs on the property for the date range.

	Each row:
	  {
	    "siu": name,
	    "unit_name": ...,
	    "unit_kind": ...,
	    "room_type": ...,
	    "competition_group": ...,
	    "sellable": 0|1,              # for the whole stay (all nights)
	    "sellable_per_night": [1,0,…],
	    "blocked": [{date, reason, reference}] if include_reasons
	  }
	"""
	_assert_dates(check_in_date, check_out_date)
	units = _load_units(property, siu=siu, room_type=room_type)
	if not units:
		return []

	nights = _nights(check_in_date, check_out_date)
	bookings = _load_bookings(property, check_in_date, check_out_date)
	blocks = _load_room_blocks(property, check_in_date, check_out_date)

	# Pre-index bookings / blocks by room and by room_type for competition.
	by_room = defaultdict(list)
	by_room_type = defaultdict(list)
	for b in bookings:
		if b.get("room"):
			by_room[b["room"]].append(b)
		if b.get("room_type"):
			by_room_type[b["room_type"]].append(b)

	# Competition state per night per group (ADR-004).
	group_state = _competition_state(units, bookings, nights)

	out = []
	for unit in units:
		row = _unit_availability(
			unit,
			nights,
			by_room=by_room,
			by_room_type=by_room_type,
			blocks=blocks,
			group_state=group_state,
			include_reasons=include_reasons,
		)
		out.append(row)
	return out


def sellable_count(
	property: str,
	room_type: str,
	check_in_date: str,
	check_out_date: str,
) -> int:
	"""How many SIUs of this room type are free for the whole stay.

	Used as a drop-in for ``len(_available_rooms_raw(...))`` style callers
	while migration to SIU is in progress.
	"""
	rows = availability(
		property,
		room_type=room_type,
		check_in_date=check_in_date,
		check_out_date=check_out_date,
	)
	return sum(1 for r in rows if r["sellable"])


def has_active_sius(property: str, room_type: str | None = None) -> bool:
	"""True when Sellable Unit inventory is wired for this property / type."""
	if not frappe.db.exists("DocType", "Sellable Unit"):
		return False
	filters: dict[str, Any] = {"property": property, "is_active": 1}
	if room_type:
		filters["room_type"] = room_type
	return bool(frappe.db.exists("Sellable Unit", filters))


def capacity_by_night(
	property: str,
	room_type: str,
	start_date: str,
	end_date: str,
) -> list[int]:
	"""Sellable SIU count per night in [start, end). Empty if no SIUs."""
	if not has_active_sius(property, room_type):
		return []
	rows = availability(
		property,
		room_type=room_type,
		check_in_date=start_date,
		check_out_date=end_date,
	)
	if not rows:
		return []
	nights = len(rows[0]["sellable_per_night"])
	return [
		sum(1 for r in rows if r["sellable_per_night"][i])
		for i in range(nights)
	]


def available_rooms_via_siu(
	property: str,
	room_type: str,
	check_in_date: str,
	check_out_date: str,
) -> list[dict]:
	"""Physical rooms behind free individual SIUs for this room type.

	Preserves the legacy ``available_rooms`` return shape so desk/public
	callers keep working during the migration.
	"""
	rows = availability(
		property,
		room_type=room_type,
		check_in_date=check_in_date,
		check_out_date=check_out_date,
	)
	rooms = []
	seen = set()
	for r in rows:
		if not r["sellable"] or r["unit_kind"] != "individual":
			continue
		for room in r.get("rooms") or []:
			if room["name"] in seen:
				continue
			seen.add(room["name"])
			# Match legacy SQL as_dict shape (attribute + key access).
			rooms.append(frappe._dict(room))
	return rooms


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _assert_dates(check_in_date: str, check_out_date: str):
	if date_diff(check_out_date, check_in_date) < 0:
		frappe.throw("Check-out cannot be before check-in.")


def _nights(check_in_date: str, check_out_date: str) -> list[str]:
	n = max(date_diff(check_out_date, check_in_date), 1)  # day-use = 1 night
	return [str(add_days(check_in_date, i)) for i in range(n)]


def _load_units(
	property: str,
	*,
	siu: str | None = None,
	room_type: str | None = None,
) -> list[dict]:
	filters: dict[str, Any] = {"property": property, "is_active": 1}
	if siu:
		filters["name"] = siu
	if room_type:
		filters["room_type"] = room_type
	units = frappe.get_all(
		"Sellable Unit",
		filters=filters,
		fields=[
			"name",
			"unit_name",
			"unit_kind",
			"room_type",
			"competition_group",
			"is_auto_assignable",
			"turnover_buffer_hours",
		],
		order_by="unit_name asc",
	)
	if not units:
		return []
	# Attach physical rooms
	room_rows = frappe.get_all(
		"Sellable Unit Room",
		filters={"parent": ("in", [u.name for u in units])},
		fields=["parent", "room"],
	)
	rooms_by_parent = defaultdict(list)
	room_names = [r.room for r in room_rows if r.room]
	room_meta = {}
	if room_names:
		for rm in frappe.get_all(
			"Room",
			filters={"name": ("in", room_names)},
			fields=["name", "room_number", "housekeeping_status"],
		):
			room_meta[rm.name] = rm
	for rr in room_rows:
		meta = room_meta.get(rr.room)
		if meta:
			rooms_by_parent[rr.parent].append(meta)
	for u in units:
		u["rooms"] = rooms_by_parent.get(u.name, [])
	return units


def _load_bookings(property: str, check_in_date: str, check_out_date: str) -> list[dict]:
	# Prefer sellable_unit when present; fall back to room / room_type so
	# pre-migration reservations still block inventory.
	fields = [
		"name",
		"room",
		"room_type",
		"check_in_date",
		"check_out_date",
		"status",
	]
	if frappe.db.has_column("Reservation", "sellable_unit"):
		fields.append("sellable_unit")
	return frappe.get_all(
		"Reservation",
		filters={
			"property": property,
			"status": ("in", list(LIVE_STATUSES)),
			"check_in_date": ("<", check_out_date),
			"check_out_date": (">", check_in_date),
		},
		fields=fields,
	)


def _load_room_blocks(
	property: str, check_in_date: str, check_out_date: str
) -> dict[str, list[dict]]:
	rows = frappe.get_all(
		"Room Block",
		filters={
			"property": property,
			"block_status": "Active",
			"from_date": ("<", check_out_date),
			"to_date": (">", check_in_date),
		},
		fields=["name", "room", "from_date", "to_date", "reason"],
	)
	by_room: dict[str, list[dict]] = defaultdict(list)
	for r in rows:
		if r.room:
			by_room[r.room].append(r)
	return by_room


def _covers(booking: dict, night: str) -> bool:
	"""A stay occupies [check_in, check_out). Day-use occupies check_in night."""
	ci = getdate(booking["check_in_date"])
	co = getdate(booking["check_out_date"])
	d = getdate(night)
	if co <= ci:
		return d == ci
	return ci <= d < co


def _competition_state(
	units: list[dict], bookings: list[dict], nights: list[str]
) -> dict[str, dict[str, dict[str, int]]]:
	"""group → night → {individual_booked, whole_booked, individual_total}."""
	units_by_group: dict[str, list[dict]] = defaultdict(list)
	for u in units:
		units_by_group[u["competition_group"]].append(u)

	# Also need full group membership for competition math even if the caller
	# filtered to one room_type — load siblings by competition_group.
	groups = list(units_by_group.keys())
	if groups:
		siblings = frappe.get_all(
			"Sellable Unit",
			filters={
				"competition_group": ("in", groups),
				"is_active": 1,
			},
			fields=["name", "unit_kind", "competition_group", "room_type"],
		)
		for s in siblings:
			units_by_group[s.competition_group].append(s)

	# Deduplicate siblings
	for g, lst in list(units_by_group.items()):
		seen = set()
		deduped = []
		for u in lst:
			if u["name"] in seen:
				continue
			seen.add(u["name"])
			deduped.append(u)
		units_by_group[g] = deduped

	siu_names = {u["name"] for lst in units_by_group.values() for u in lst}
	bookings_by_siu = defaultdict(list)
	for b in bookings:
		su = b.get("sellable_unit")
		if su and su in siu_names:
			bookings_by_siu[su].append(b)

	# Room → SIU map for pre-migration reservations that only set `room`.
	room_to_siu = {}
	room_links = frappe.get_all(
		"Sellable Unit Room",
		filters={"parent": ("in", list(siu_names))} if siu_names else {"parent": ""},
		fields=["parent", "room"],
	)
	for link in room_links:
		if link.room:
			room_to_siu[link.room] = link.parent

	for b in bookings:
		if b.get("sellable_unit"):
			continue
		# Assigned room → individual / composite SIU.
		if b.get("room") and b["room"] in room_to_siu:
			bookings_by_siu[room_to_siu[b["room"]]].append(b)
			continue
		# Unassigned Villa-category stay → whole_property SIU of that type.
		rt = b.get("room_type")
		if not rt:
			continue
		category = frappe.db.get_value("Room Type", rt, "room_category")
		if category == "Villa":
			for g, lst in units_by_group.items():
				for u in lst:
					if u["unit_kind"] == "whole_property" and u["room_type"] == rt:
						bookings_by_siu[u["name"]].append(b)
						break

	state: dict[str, dict[str, dict[str, int]]] = {}
	for g, lst in units_by_group.items():
		individuals = [u for u in lst if u["unit_kind"] == "individual"]
		wholes = [u for u in lst if u["unit_kind"] == "whole_property"]
		state[g] = {}
		for night in nights:
			i_booked = 0
			for u in individuals:
				if any(_covers(b, night) for b in bookings_by_siu.get(u["name"], [])):
					i_booked += 1
			w_booked = 0
			for u in wholes:
				if any(_covers(b, night) for b in bookings_by_siu.get(u["name"], [])):
					w_booked = 1
					break
			state[g][night] = {
				"individual_booked": i_booked,
				"whole_booked": w_booked,
				"individual_total": len(individuals),
			}
	return state


def _unit_availability(
	unit: dict,
	nights: list[str],
	*,
	by_room: dict,
	by_room_type: dict,
	blocks: dict,
	group_state: dict,
	include_reasons: bool,
) -> dict:
	sellable_per_night = []
	blocked: list[dict] = []
	rooms = unit.get("rooms") or []

	for night in nights:
		reasons = []
		free = 1

		# Room-level reservation / block for individual & composite units.
		if unit["unit_kind"] in ("individual", "composite"):
			if not rooms:
				free = 0
				reasons.append(
					{"date": night, "reason": "no_physical_room", "reference": unit["name"]}
				)
			else:
				for rm in rooms:
					if rm.housekeeping_status == "Out of Order":
						free = 0
						reasons.append(
							{
								"date": night,
								"reason": "out_of_order",
								"reference": rm.name,
							}
						)
					for b in by_room.get(rm.name, []):
						if _covers(b, night):
							free = 0
							reasons.append(
								{
									"date": night,
									"reason": "reservation",
									"reference": b["name"],
								}
							)
					for blk in blocks.get(rm.name, []):
						bf, bt = getdate(blk.from_date), getdate(blk.to_date)
						d = getdate(night)
						if bf <= d < bt:
							free = 0
							reasons.append(
								{
									"date": night,
									"reason": "owner_block"
									if (blk.reason or "").lower().startswith("owner")
									else "room_block",
									"reference": blk.name,
								}
							)

		# Competition group (ADR-004).
		gs = group_state.get(unit["competition_group"], {}).get(night)
		if gs:
			if unit["unit_kind"] == "whole_property":
				if gs["whole_booked"] or gs["individual_booked"] > 0:
					free = 0
					reasons.append(
						{
							"date": night,
							"reason": "competition",
							"reference": unit["competition_group"],
						}
					)
			elif unit["unit_kind"] == "individual":
				if gs["whole_booked"]:
					free = 0
					reasons.append(
						{
							"date": night,
							"reason": "competition",
							"reference": unit["competition_group"],
						}
					)

		sellable_per_night.append(free)
		if include_reasons:
			blocked.extend(reasons)

	sellable = 1 if sellable_per_night and all(sellable_per_night) else 0
	result = {
		"siu": unit["name"],
		"unit_name": unit["unit_name"],
		"unit_kind": unit["unit_kind"],
		"room_type": unit["room_type"],
		"competition_group": unit["competition_group"],
		"sellable": sellable,
		"sellable_per_night": sellable_per_night,
		"rooms": [
			{
				"name": r.name,
				"room_number": r.room_number,
				"housekeeping_status": r.housekeeping_status,
			}
			for r in rooms
		],
	}
	if include_reasons:
		result["blocked"] = blocked
	return result
