"""Allocation agent (ORION): give every unassigned arrival the right room.

This is agent-native, not a rules engine bolted on: ORION reads each guest's
free-text wishes (special requests + guest profile notes) and the concrete
attributes of the free rooms, then proposes the best fit - VIPs to the best
room, "lake view" to a lake-view room, "high floor" to the top, a group kept
together. Proposals flow through the autonomy gate, so a manager can let ORION
assign the obvious ones and approve the judgement calls. A human clicking
"Auto-assign" on the tape chart runs the same logic with their own authority.

The scorer is deterministic and testable; when an OpenAI key is configured it
can be layered on top, but the hotel is never blocked on a model being up."""

import frappe

from kamra.authz import require_roles

# free-text preference cues -> how they score a candidate room
_VIEW_WORDS = ("view", "lake", "sea", "ocean", "pool", "garden", "city",
               "mountain", "hill", "beach", "river")
_HIGH_WORDS = ("high floor", "higher floor", "top floor", "upper floor",
               "upper", "highest")
_LOW_WORDS = ("ground floor", "low floor", "lower floor", "ground-floor",
              "no stairs", "accessible")
_BED_WORDS = ("king", "queen", "twin", "double", "single")
_QUIET_WORDS = ("quiet", "corner", "away from", "peaceful", "no noise")


def _room_pool(property: str):
	"""Every room with the attributes allocation cares about, keyed by name."""
	rooms = frappe.db.sql(
		"""
		SELECT r.name, r.room_number, r.floor, r.room_type,
		       rt.room_type_name, rt.room_view, rt.bed_type
		FROM `tabRoom` r
		LEFT JOIN `tabRoom Type` rt ON rt.name = r.room_type
		WHERE r.property = %(p)s
		""", {"p": property}, as_dict=True)
	floors = [int(r.floor) for r in rooms if _as_int(r.floor) is not None]
	return rooms, (max(floors) if floors else None), (min(floors) if floors else None)


def _as_int(v):
	try:
		return int(str(v).strip())
	except (ValueError, TypeError, AttributeError):
		return None


def _score(prefs: str, vip: bool, room: dict, max_floor, min_floor):
	"""Score how well a free room fits the guest's wishes; return (score, why)."""
	p = (prefs or "").lower()
	score = 0.0
	why = []

	view = (room.get("room_view") or "").lower()
	if any(w in p for w in _VIEW_WORDS):
		if view and view != "standard" and (view in p or "view" in p):
			score += 3
			why.append(f"{room['room_view']} view")

	fl = _as_int(room.get("floor"))
	if any(w in p for w in _HIGH_WORDS) and fl is not None and fl == max_floor:
		score += 2
		why.append("top floor")
	if any(w in p for w in _LOW_WORDS) and fl is not None and fl == min_floor:
		score += 2
		why.append("ground floor")

	bed = (room.get("bed_type") or "").lower()
	for w in _BED_WORDS:
		if w in p and w in bed:
			score += 2
			why.append(f"{room['bed_type']} bed")
			break

	if any(w in p for w in _QUIET_WORDS):
		# quieter rooms tend to sit at the far end of the corridor
		score += 0.5
		why.append("quieter end")

	if vip:
		# nudge VIPs toward the higher room numbers (usually the better rooms)
		score += (_as_int(room.get("room_number")) or 0) / 100000.0
		why.append("VIP - best available")

	return score, why


@frappe.whitelist()
@require_roles("Front Desk", "Revenue Manager", "Kamra Agent")
def suggest_allocation(property: str, date: str | None = None):
	"""Propose a room for every unassigned arrival on `date`. No mutation."""
	from frappe.utils import nowdate
	from kamra.api import available_rooms

	d = date or nowdate()
	arrivals = frappe.get_all(
		"Reservation",
		filters={"property": property, "status": "Confirmed",
		         "check_in_date": d, "room": ("in", ["", None])},
		fields=["name", "guest", "guest_name", "room_type", "check_in_date",
		        "check_out_date", "special_requests", "group_booking",
		        "is_day_use"],
		order_by="booking_type desc, creation asc")

	# batch the guest lookups (vip + notes)
	gnames = [a.guest for a in arrivals if a.guest]
	gmeta = {g.name: g for g in frappe.get_all(
		"Guest", filters={"name": ("in", gnames or [""])},
		fields=["name", "vip", "guest_notes"])} if gnames else {}

	pool, max_floor, min_floor = _room_pool(property)
	by_name = {r.name: r for r in pool}

	# rooms already handed out in this pass, so two arrivals never collide
	taken: set[str] = set()
	proposals, unfittable = [], []

	for a in arrivals:
		free = available_rooms(property, a.room_type, a.check_in_date,
		                       a.check_out_date, group_booking=a.group_booking)
		cands = [by_name[r["name"]] for r in free
		         if r["name"] in by_name and r["name"] not in taken]
		if not cands:
			unfittable.append({"reservation": a.name, "guest_name": a.guest_name,
			                   "room_type": a.room_type,
			                   "reason": "No free room of this type"})
			continue

		g = gmeta.get(a.guest)
		vip = bool(g and g.vip)
		prefs = " ".join(filter(None, [a.special_requests,
		                               g.guest_notes if g else None]))
		# high/low floor is relative to the rooms actually on offer for this type
		cfloors = [_as_int(r.get("floor")) for r in cands
		           if _as_int(r.get("floor")) is not None]
		cmax = max(cfloors) if cfloors else None
		cmin = min(cfloors) if cfloors else None
		scored = sorted(
			((_score(prefs, vip, r, cmax, cmin), r) for r in cands),
			key=lambda x: (x[0][0], -(_as_int(x[1].get("room_number")) or 0)),
			reverse=True)
		(best_score, why), room = scored[0]
		taken.add(room.name)

		# a real choice (>1 candidate) or a preference/VIP match => needs a look
		needs_review = vip or best_score > 0 or len(cands) > 1
		proposals.append({
			"reservation": a.name,
			"guest_name": a.guest_name,
			"vip": 1 if vip else 0,
			"room_type_name": room.get("room_type_name") or a.room_type,
			"suggested_room": room.name,
			"room_number": room.get("room_number"),
			"why": ", ".join(why) if why else "First free room of the type",
			"alternatives": len(cands) - 1,
			"needs_review": 1 if needs_review else 0,
			"prefs": prefs.strip(),
		})

	return {"date": str(d), "proposals": proposals, "unfittable": unfittable}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Revenue Manager", "Kamra Agent")
def apply_allocation(property: str, assignments, agent: str | None = None):
	"""Assign the proposed rooms. Each assignment flows through the autonomy
	gate: a human runs on their own authority (executes); an agent runs under
	its rules (obvious ones execute, judgement calls park in Approvals)."""
	from kamra.autonomy import guard, finalize_after, GateExecute, GateSuggest

	if isinstance(assignments, str):
		assignments = frappe.parse_json(assignments)

	executed, pending = [], []
	for a in assignments:
		res, room = a.get("reservation"), a.get("room") or a.get("suggested_room")
		if not (res and room):
			continue
		doc = frappe.db.get_value("Reservation", res,
		                          ["guest_name", "room", "status"], as_dict=True)
		if not doc or doc.status not in ("Confirmed", "Checked In"):
			continue
		summary = (f"Assign {doc.guest_name} to "
		           f"room {frappe.db.get_value('Room', room, 'room_number')}")
		decision = guard(
			"allocate_room", endpoint="kamra.allocation.apply_allocation",
			payload={"property": property, "assignments": [a],
			         "needs_review": a.get("needs_review", 1)},
			summary=summary, agent_name=agent, property=property,
			reference_doctype="Reservation", reference_name=res,
			before_snapshot={"room": doc.room}, minutes_saved=2,
			rationale=a.get("why") or "")
		if isinstance(decision, GateExecute):
			frappe.db.set_value("Reservation", res, "room", room)
			from kamra.savings import log_action
			log_action("allocate_room", "Reservation", res, property,
			           rationale=f"→ room {room}. {a.get('why') or ''}".strip(),
			           agent_name=agent)
			finalize_after(decision.log_name, after_snapshot={"room": room})
			executed.append({"reservation": res, "room": room})
		elif isinstance(decision, GateSuggest):
			pending.append({"reservation": res, "gate": "suggest",
			                "summary": decision.summary})
		else:  # GatePending
			pending.append({"reservation": res, "gate": "pending",
			                "summary": summary})

	frappe.db.commit()
	return {"executed": executed, "pending": pending}


def run_nightly_allocation():
	"""ORION's scheduled pass: pre-assign tomorrow's arrivals for every active
	property. Obvious placements execute; anything ORION should not decide alone
	(a real choice, a VIP, a preference match) parks in Approvals for the desk.
	Wired to the scheduler, so the board is already sorted before the team
	arrives."""
	from frappe.utils import add_days, nowdate

	tomorrow = add_days(nowdate(), 1)
	for prop in frappe.get_all("Property", filters={"disabled": 0}, pluck="name"):
		try:
			sug = suggest_allocation(prop, tomorrow)
			if sug["proposals"]:
				apply_allocation(prop, sug["proposals"], agent="ORION")
		except Exception:
			frappe.log_error(f"ORION allocation failed for {prop}",
			                 "Allocation agent")
