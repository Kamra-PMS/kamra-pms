"""Guided check-in - one screen per step, the property's SOP.

The steps and which of them are required come from the property's check-in
SOP (kamra.sop, "checkin"; Settings > Front desk > Check-in steps). This
module builds what each step needs, records who did each step and when, and
holds the one hard rule the server enforces: check_in refuses only while
there is no room (assign_room). Other steps the property marks required are
soft: the desk can check the guest in and finish them later (backfill).

Every step writes through the existing writer for its data: rooms through
move_reservation, deposits through the security deposit endpoints, payments
through the folio, requests through create_ticket. The step record itself
(Reservation.checkin_steps, JSON: step -> state, by, at, note) is the audit
trail, and each step also lands in the activity log under the operator who
did it.

Only the room step cannot be skipped. Soft-required steps can be skipped
with a reason, or left open and finished after check-in.
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from kamra.authz import require_roles
from kamra.guest_documents import id_status, used_stays_count

DESK = ("Front Desk", "Night Auditor", "Kamra Agent")
# confirmations only a person at the desk can give
STAFF = ("Front Desk", "Night Auditor")

PAYERS = ("OTA prepaid", "OTA, guest pays here", "Guest", "Company", "Group")

# quick requests at check-in -> a service ticket each (subject, category, priority)
REQUEST_PRESETS = {
	"extra_bed": ("Extra bed", "Housekeeping", "Medium"),
	"wake_up_call": ("Wake-up call", "Front Desk", "Medium"),
	"airport_drop": ("Airport drop", "Concierge", "Medium"),
	"dietary": ("Dietary needs", "Room Service", "Medium"),
	"special_occasion": ("Special occasion", "Concierge", "Medium"),
}

STAY_INFO_KEYS = ("guest_wifi_name", "guest_wifi_password", "breakfast_hours",
                  "emergency_number", "guest_info_note")


class CheckInStepsMissing(frappe.ValidationError):
	"""check_in refused: a required check-in step is not done yet."""


# ── the step list for a property ──────────────────────────────────────────

def checkin_steps(property: str) -> list[dict]:
	"""The property's check-in steps in order: its SOP template, with any
	built-in step it lacks added back at its default (a template saved
	before a step existed keeps working) and the room always required."""
	from kamra.sop import CHECKIN_ALWAYS_REQUIRED, checkin_default_steps
	# read-only: a property with no saved template uses the defaults (the
	# settings page saves one); never seed it from here, so two desks
	# opening check-ins at once don't race to insert the same template
	steps = []
	name = frappe.db.exists("DocType", "SOP Template") and frappe.db.get_value(
		"SOP Template", {"property": property, "key": "checkin", "active": 1}, "name")
	if name:
		steps = [{"step_key": s.step_key, "step_type": s.step_type, "title": s.title,
		          "instruction": s.instruction or "",
		          "prompt_to_guest": s.prompt_to_guest or "",
		          "is_blocking": 1 if s.is_blocking else 0,
		          "sequence": cint(s.sequence)}
		         for s in frappe.get_doc("SOP Template", name).steps or []]
	have = {s.get("step_key") for s in steps}
	steps = list(steps) + [s for s in checkin_default_steps(property)
	                       if s["step_key"] not in have]
	out = []
	for s in steps:
		s = dict(s)
		if s.get("step_key") in CHECKIN_ALWAYS_REQUIRED:
			s["is_blocking"] = 1
		out.append(s)
	out.sort(key=lambda s: int(s.get("sequence") or 0))
	return out


# ── per-stay record ───────────────────────────────────────────────────────

def _records(res) -> dict:
	raw = res.get("checkin_steps") if hasattr(res, "get") else None
	if not raw:
		return {}
	try:
		val = json.loads(raw)
		return val if isinstance(val, dict) else {}
	except (TypeError, ValueError):
		return {}


def record_step(res, key: str, state: str = "done", note: str | None = None,
                **extra) -> dict:
	"""Write one step's record (who, when) and the matching activity-log
	row. `extra` holds non-secret details for the record only."""
	recs = _records(res)
	rec = {"state": state, "by": frappe.session.user,
	       "at": str(now_datetime())}
	if note:
		rec["note"] = str(note)[:280]
	rec.update({k: v for k, v in extra.items() if v not in (None, "")})
	recs[key] = rec
	payload = json.dumps(recs, sort_keys=True, default=str)
	frappe.db.set_value("Reservation", res.name, "checkin_steps", payload,
	                    update_modified=False)
	res.checkin_steps = payload
	from kamra.savings import log_action
	what = "skipped" if state == "skipped" else "done"
	log_action(f"checkin_{key}", "Reservation", res.name, res.property,
	           rationale=f"Check-in step {key} {what} for {res.guest_name}"
	                     + (f": {str(note)[:140]}" if note else ""))
	return rec


# ── context ───────────────────────────────────────────────────────────────

def _symbol(property: str) -> str:
	from kamra.localization import pack_for
	prop = frappe.get_cached_doc("Property", property)
	return pack_for(property).locale(prop).get("currency_symbol", "")


def _ids(res, guest) -> dict:
	"""Whose ID is still missing, under the country's register rules: a
	minor is recorded by name and age only unless the pack keeps their ID."""
	from kamra.localization import is_minor, minor_id_kept, pack_for
	pack = pack_for(res.property)
	missing = []
	primary_ok = bool(guest and (guest.get("id_number") or guest.get("id_file"))
	                  or res.get("id_document"))
	if not primary_ok:
		missing.append(res.guest_name or _("the guest"))
	occupants, adults_named = [], 1
	for o in res.get("occupants") or []:
		minor = is_minor(pack, o.age)
		adults_named += 0 if minor else 1
		exempt = minor and not minor_id_kept(pack, o.nationality)
		has = bool(o.id_number or o.get("id_file"))
		if not exempt and not has:
			missing.append(o.full_name)
		occupants.append({
			"row": o.name, "full_name": o.full_name, "age": o.age,
			"gender": o.gender, "nationality": o.nationality, "id_type": o.id_type,
			"id_number": _mask(o.id_number), "has_id": has, "exempt": exempt,
			"has_photo": bool(o.get("photo")),
		})
	# every adult on the booking is in the register, by name and ID
	unnamed = max(0, cint(res.adults) - adults_named)
	if unnamed:
		missing.append(_("1 more adult") if unnamed == 1
		               else _("{0} more adults").format(unnamed))
	status = res.get("precheckin_status") or "Not Started"
	return {
		"ok": not missing,
		"missing": missing,
		"online": status in ("Submitted", "Verified"),
		"precheckin_status": status,
		"precheckin_on": str(res.precheckin_on) if res.get("precheckin_on") else None,
		"occupants": occupants,
	}


def _mask(value: str | None) -> str | None:
	if not value:
		return value
	v = str(value)
	return v if len(v) <= 4 else "•" * (len(v) - 4) + v[-4:]


def _billing(res) -> dict:
	"""Who pays, as the booking says it - the desk confirms or corrects."""
	company_name = rules = None
	if res.get("company"):
		company_name = frappe.db.get_value("Corporate Account", res.company,
		                                   "company_name") or res.company
		rules = [{"charge_type": r.charge_type, "pay_by": r.pay_by}
		         for r in frappe.get_doc("Corporate Account", res.company)
		         .get("billing_rules") or []]
	group_name = master = None
	if res.get("group_booking"):
		group_name = frappe.db.get_value("Group Booking", res.group_booking,
		                                 "group_name") or res.group_booking
		master = frappe.db.get_value(
			"Folio", {"group_booking": res.group_booking, "folio_type": "Group"},
			"name")
	is_ota = res.source == "OTA" or bool(res.get("ota_ref"))
	if master:
		payer = "Group"
	elif res.get("company"):
		payer = "Company"
	elif is_ota:
		payer = "OTA, guest pays here" if res.get("is_pay_at_hotel") else "OTA prepaid"
	else:
		payer = "Guest"
	total = flt(res.amount_after_tax)
	paid = flt(res.advance_paid)
	folio = frappe.db.get_value(
		"Folio", {"reservation": res.name, "folio_type": "Guest"},
		["name", "balance"], as_dict=True)
	if folio:
		balance = flt(folio.balance)
	elif payer == "OTA prepaid":
		balance = 0.0
	else:
		balance = max(0.0, round(total - paid, 2))
	labels = {
		"OTA prepaid": _("{0} has collected the room. Extras are paid by the guest.").format(
			res.get("channel") or _("The OTA")),
		"OTA, guest pays here": _("{0} booking. The guest pays the hotel.").format(
			res.get("channel") or _("OTA")),
		"Guest": _("The guest pays."),
		"Company": _("{0} pays as agreed; the rest is paid by the guest.").format(
			company_name or _("The company")),
		"Group": _("The group account {0} pays as agreed.").format(group_name or ""),
	}
	return {
		"payer": payer,
		"payer_label": labels[payer],
		"source": res.source, "channel": res.get("channel"),
		"ota_ref": res.get("ota_ref"),
		"pay_at_hotel": 1 if res.get("is_pay_at_hotel") else 0,
		"company": res.get("company"), "company_name": company_name,
		"billing_rules": rules or [],
		"group_booking": res.get("group_booking"), "group_name": group_name,
		"group_master_folio": master,
		"stay_total": total, "advance_paid": paid, "balance_due": balance,
		"options": list(PAYERS),
	}


def _room(res) -> dict:
	from kamra.kamra.doctype.reservation.reservation import (
		entire_place_rooms, uses_member_rooms)
	out = {"room": res.room, "room_number": None, "housekeeping_status": None,
	       "entire_place": None,
	       "room_type": res.room_type,
	       "room_type_name": frappe.db.get_value("Room Type", res.room_type,
	                                             "room_type_name"),
	       "assigned_by": res.get("room_assigned_by"),
	       "assigned_at": str(res.room_assigned_at) if res.get("room_assigned_at") else None}
	if res.room:
		r = frappe.db.get_value("Room", res.room,
		                        ["room_number", "housekeeping_status"], as_dict=True) or {}
		out["room_number"] = r.get("room_number") or res.room
		out["housekeeping_status"] = r.get("housekeeping_status")
	elif uses_member_rooms(res.property, res.room_type):
		out["entire_place"] = [r.room_number or r.name for r in
		                       entire_place_rooms(res.property, res.room_type)]
	return out


def _free_rooms(res) -> list[dict]:
	"""Rooms of the booked type the guest can go into now - clean first."""
	if res.status != "Confirmed":
		return []
	from kamra.api import available_rooms
	rank = {"Inspected": 0, "Clean": 1, "Dirty": 3}
	rows = [{"name": r["name"], "room_number": r["room_number"],
	         "housekeeping_status": r["housekeeping_status"]}
	        for r in available_rooms(res.property, res.room_type,
	                                 str(res.check_in_date), str(res.check_out_date),
	                                 group_booking=res.group_booking, ready_now=1)
	        if r["name"] != res.room]
	rows.sort(key=lambda r: (rank.get(r["housekeeping_status"] or "", 2),
	                         len(str(r["room_number"])), str(r["room_number"])))
	return rows


def _deposit(res) -> dict:
	from kamra.api import _deposit_state
	from kamra.deposit import deposit_satisfied, deposit_state
	sec = deposit_state(res)
	adv = _deposit_state(res)
	sec_applies = flt(sec.get("required")) > 0 and sec.get("status") != "None"
	adv_due = flt(adv.get("due")) if adv.get("can_take") else 0.0
	return {
		"applies": bool(sec_applies or adv_due > 0.009),
		"satisfied": deposit_satisfied(res.name),
		"security": sec,
		"advance": adv,
		"security_due": flt(sec.get("due")) if sec_applies else 0.0,
		"advance_due": adv_due,
	}


def stay_info(property: str) -> dict:
	from kamra.settings import get_setting
	vals = {k: get_setting(property, k) or "" for k in STAY_INFO_KEYS}
	vals["checkout_time"] = str(get_setting(property, "checkout_time") or "")[:5]
	vals["configured"] = any(vals[k] for k in STAY_INFO_KEYS)
	return vals


def _keys(res) -> dict:
	from kamra.door_lock import get_adapter
	adapter = get_adapter(res.property)
	return {
		"count": cint(res.get("key_count")),
		"cards": res.get("key_cards") or "",
		"issued_by": res.get("keys_issued_by"),
		"issued_at": str(res.keys_issued_at) if res.get("keys_issued_at") else None,
		"adapter": adapter.key, "adapter_label": adapter.label,
		"manual": adapter.key == "manual",
	}


def build_context(res, room_override: str | None = None) -> dict:
	guest = frappe.get_doc("Guest", res.guest) if res.guest else None
	billing = _billing(res)
	room = _room(res)
	if room_override and not room["room_number"]:
		room["room_number"] = frappe.db.get_value(
			"Room", room_override, "room_number") or room_override
	deposit = _deposit(res)
	records = _records(res)
	payer = (records.get("billing_check") or {}).get("payer") or billing["payer"]
	held = flt(deposit["security"].get("held"))
	return {
		"currency_symbol": _symbol(res.property),
		"records": records,
		"ids": _ids(res, guest),
		"billing": billing,
		"room": room,
		"deposit": deposit,
		"grc": {"signed": bool(res.get("precheckin_signature"))},
		"keys": _keys(res),
		"stay_info": stay_info(res.property),
		"special_requests": res.get("special_requests") or "",
		"room_charges": {
			"allowed": bool(cint(res.get("room_charges_allowed")
			                     if res.get("room_charges_allowed") is not None else 1)),
			"recommend_block": payer == "OTA prepaid" and held <= 0.009,
		},
		"_guest": guest,
	}


def evaluate(res, room_override: str | None = None) -> tuple[list[dict], dict]:
	from kamra.sop import evaluate_checkin_step
	ctx = build_context(res, room_override)
	steps = [evaluate_checkin_step(
		{"step_key": s.get("step_key") or "", "step_type": s.get("step_type") or "confirm",
		 "title": s.get("title") or "", "instruction": s.get("instruction") or "",
		 "prompt_to_guest": s.get("prompt_to_guest") or "",
		 "is_blocking": 1 if cint(s.get("is_blocking")) else 0,
		 "sequence": cint(s.get("sequence"))}, ctx)
		for s in checkin_steps(res.property)]
	return steps, ctx


def hard_missing(steps: list[dict]) -> list[dict]:
	"""Steps that refuse check_in: only the room (no room, no stay)."""
	from kamra.sop import CHECKIN_ALWAYS_REQUIRED
	return [s for s in steps
	        if s.get("step_key") in CHECKIN_ALWAYS_REQUIRED
	        and s.get("relevant") and s.get("state") != "done"]


def soft_pending(steps: list[dict]) -> list[dict]:
	"""Property-marked required steps still open — warn and backfill later;
	they do not refuse check_in."""
	from kamra.sop import CHECKIN_ALWAYS_REQUIRED
	return [s for s in steps
	        if s.get("is_blocking") and s.get("relevant") and s.get("state") != "done"
	        and s.get("step_key") not in CHECKIN_ALWAYS_REQUIRED]


def missing_required(steps: list[dict]) -> list[dict]:
	"""What still blocks check_in (room only). Kept name for callers."""
	return hard_missing(steps)


def assert_ready(res, room: str | None = None) -> None:
	"""check_in's hard gate: a room must be assigned. Other required steps
	are soft — check_in goes through and the desk finishes them later.
	Turned off only by server code (frappe.flags), never by a request."""
	if frappe.flags.kamra_checkin_steps_off:
		return
	steps, _ctx = evaluate(res, room_override=room)
	todo = hard_missing(steps)
	if todo:
		frappe.throw(
			_("Assign a room before check-in."),
			exc=CheckInStepsMissing, title=_("Check-in not finished"))


def after_check_in(res) -> dict | None:
	"""Called by check_in once the guest is in: a connected lock system
	makes the keys the desk recorded in the Keys step. The manual adapter
	needs nothing here (staff already encoded the cards)."""
	count = cint(res.get("key_count"))
	if not count or not res.room:
		return None
	from kamra.door_lock import get_adapter
	adapter = get_adapter(res.property)
	if adapter.key == "manual":
		return None
	return _call_adapter(adapter, res, count)


def _call_adapter(adapter, res, count: int) -> dict:
	from kamra.door_lock import KeyRequest
	from kamra.settings import get_setting
	out_time = str(get_setting(res.property, "checkout_time") or "11:00")[:5]
	req = KeyRequest(
		property=res.property, reservation=res.name, room=res.room,
		room_number=frappe.db.get_value("Room", res.room, "room_number") or res.room,
		valid_from=str(now_datetime().replace(microsecond=0)),
		valid_to=f"{res.check_out_date} {out_time}:00",
		key_count=count, guest_name=res.guest_name)
	try:
		result = adapter.issue_key(req)
	except Exception:
		# a connector must not break check-in; the desk sees the message
		frappe.log_error(title=f"Door lock {adapter.key} issue_key failed")
		return {"ok": False, "adapter": adapter.key, "manual": False,
		        "message": _("The lock system did not answer. Make the keys at the encoder.")}
	from kamra.savings import log_action
	log_action("issue_keys", "Reservation", res.name, res.property,
	           rationale=f"{count} key(s) via {adapter.key}: "
	                     f"{'ok' if result.ok else 'failed'}")
	return {"ok": bool(result.ok), "adapter": result.adapter,
	        "manual": bool(result.manual), "message": result.message,
	        "key_ids": list(result.key_ids or [])}


# ── endpoints ─────────────────────────────────────────────────────────────

def _res(reservation: str):
	res = frappe.get_doc("Reservation", reservation)
	from kamra.crs import assert_property_access
	assert_property_access(res.property)
	return res


def _open(res):
	if res.status not in ("Confirmed", "Checked In"):
		frappe.throw(_("Only a confirmed or in-house stay has check-in steps (this one is {0}).")
		             .format(_(res.status)))


def _step(res, key: str) -> dict:
	for s in checkin_steps(res.property):
		if s.get("step_key") == key:
			return s
	frappe.throw(_("{0} is not a check-in step at this property.").format(key))
	return {}  # unreachable: frappe.throw always raises


@frappe.whitelist()
@require_roles(*DESK)
def checkin_flow(reservation: str):
	"""Everything the guided check-in shows, in one round trip: the steps
	(required or optional, done, skipped or to do, and who did them), plus
	what each step screen needs."""
	res = _res(reservation)
	steps, ctx = evaluate(res)
	guest = ctx.pop("_guest")
	return _flow_payload(res, steps, ctx, guest)


def _till(property: str) -> dict:
	from kamra.cashier import till_state
	return till_state(property)


def _flow_payload(res, steps, ctx, guest) -> dict:
	from kamra.localization import front_desk_vocabulary, pack_for
	return {
		"reservation": {
			"name": res.name, "status": res.status,
			"guest": res.guest, "guest_name": res.guest_name,
			"room_type": res.room_type,
			"check_in_date": str(res.check_in_date),
			"check_out_date": str(res.check_out_date),
			"nights": res.nights, "adults": res.adults, "children": res.children,
			"vip": cint(guest.get("vip")) if guest else 0,
			"source": res.source, "special_requests": res.get("special_requests") or "",
			"checked_in_by": res.get("checked_in_by"),
			"checked_in_at": str(res.checked_in_at) if res.get("checked_in_at") else None,
		},
		"guest": {
			"name": guest.name if guest else None,
			"full_name": guest.full_name if guest else res.guest_name,
			"phone": guest.get("phone") if guest else None,
			"email": guest.get("email") if guest else None,
			"nationality": guest.get("nationality") if guest else None,
			"id_type": guest.get("id_type") if guest else None,
			"id_number": _mask(guest.get("id_number")) if guest else None,
			"id_on_file": bool(guest and (guest.get("id_number") or guest.get("id_file"))
			                   or res.get("id_document")),
			# what the profile already holds, so the desk can reuse it instead
			# of asking again; warnings only, never a reason to stop a check-in
			"id_expiry_date": str(guest.get("id_expiry_date") or "") or None if guest else None,
			"id_status": id_status(guest.get("id_expiry_date"), bool(
				guest.get("id_number") or guest.get("id_file") or res.get("id_document")))
			if guest else "none",
			"id_used_count": used_stays_count(guest.name) if guest else 0,
			"has_photo": bool(guest and guest.get("photo")),
			"gender": guest.get("gender") if guest else None,
			"date_of_birth": str(guest.get("date_of_birth") or "") or None if guest else None,
			"address": ", ".join(x for x in [guest.get("address_line"), guest.get("city")]
			                     if x) if guest else "",
		},
		"vocabulary": front_desk_vocabulary(pack_for(res.property)),
		"steps": steps,
		"missing_required": [s["step_key"] for s in hard_missing(steps)],
		"pending_backfill": [
			{"step": s["step_key"], "title": s["title"], "tip": s.get("tip") or ""}
			for s in soft_pending(steps)],
		"rooms": _free_rooms(res) if not res.room else [],
		"request_presets": [{"key": k, "label": v[0]} for k, v in REQUEST_PRESETS.items()],
		# the deposit step takes money: is the operator's till open, or can
		# they open it here (kamra.cashier.open_session)
		"till": _till(res.property),
		**{k: v for k, v in ctx.items() if k != "records"},
		"records": ctx["records"],
	}


@frappe.whitelist()
@require_roles("Front Desk", "Night Auditor", "Finance", "Hotel Admin", "Kamra Agent")
def check_in_readiness(reservation: str):
	"""Read-only: which check-in steps are done, whether check_in would go
	through now (room assigned), and which soft-required steps are still
	open to finish later. Agents read this; they cannot do the desk's
	steps for it."""
	res = _res(reservation)
	steps, _ctx = evaluate(res)
	hard = hard_missing(steps)
	soft = soft_pending(steps)
	return {
		"reservation": res.name, "status": res.status,
		"ready": res.status == "Confirmed" and not hard,
		"missing_required": [{"step": s["step_key"], "title": s["title"], "tip": s["tip"]}
		                     for s in hard],
		"pending_backfill": [{"step": s["step_key"], "title": s["title"], "tip": s["tip"]}
		                     for s in soft],
		"steps": [{"step": s["step_key"], "title": s["title"],
		           "required": s["is_blocking"], "applies": s["relevant"],
		           "state": s["state"], "done_by": s.get("done_by"),
		           "done_at": s.get("done_at")} for s in steps],
	}


@frappe.whitelist(methods=["POST"])
@require_roles(*STAFF)
def complete_checkin_step(reservation: str, step: str, note: str | None = None):
	"""The desk marks a step done (a confirm-only step, or the review of
	what the guest sent online). Refused while what the step stands for is
	not true yet - an ID still missing, a deposit not taken."""
	res = _res(reservation)
	_open(res)
	_step(res, step)
	steps, _ctx = evaluate(res)
	ev = next(s for s in steps if s["step_key"] == step)
	if not ev.get("facts_ok"):
		frappe.throw(ev.get("tip") or _("This step is not finished yet."))
	if step in ("billing_check", "room_charges", "keys", "guest_requests"):
		frappe.throw(_("Use the {0} screen for this step.").format(_(ev["title"])))
	record_step(res, step, "done", note=note)
	return checkin_flow(reservation)


@frappe.whitelist(methods=["POST"])
@require_roles(*STAFF)
def skip_checkin_step(reservation: str, step: str, reason: str | None = None):
	"""Skip a step to finish later. Only the room cannot be skipped."""
	from kamra.sop import CHECKIN_ALWAYS_REQUIRED
	res = _res(reservation)
	_open(res)
	s = _step(res, step)
	if (s.get("step_key") or step) in CHECKIN_ALWAYS_REQUIRED:
		frappe.throw(_("{0} cannot be skipped — assign a room first.")
		             .format(_(s.get("title") or step)))
	note = (reason or "").strip() or _("Backfill after check-in")
	record_step(res, step, "skipped", note=note)
	return checkin_flow(reservation)


@frappe.whitelist(methods=["POST"])
@require_roles(*STAFF)
def save_guest_details(reservation: str, phone: str | None = None,
                       email: str | None = None, id_type: str | None = None,
                       id_number: str | None = None,
                       nationality: str | None = None,
                       date_of_birth: str | None = None,
                       gender: str | None = None,
                       id_expiry_date: str | None = None,
                       address_line: str | None = None,
                       city: str | None = None):
	"""Correct the primary guest's contact and ID details at the desk, or
	keep what an ID scan read. Only what is passed changes; an ID type must
	be one the country recognises."""
	res = _res(reservation)
	_open(res)
	if not res.guest:
		frappe.throw(_("This booking has no guest profile."))
	from kamra.localization import validate_id_type
	changes = {}
	if phone is not None:
		changes["phone"] = phone.strip() or None
	if email is not None:
		changes["email"] = email.strip() or None
	if nationality is not None:
		changes["nationality"] = nationality.strip() or None
	from frappe.utils import getdate
	for field, value in (("date_of_birth", date_of_birth), ("id_expiry_date", id_expiry_date)):
		if value:
			changes[field] = str(getdate(value))
	# Data fields hold 140 characters; an Aadhaar address can run longer
	for field, value in (("address_line", address_line), ("city", city)):
		if value and value.strip():
			changes[field] = value.strip()[:140]
	if gender in ("Male", "Female", "Other"):
		changes["gender"] = gender
	if id_type:
		if id_type != frappe.db.get_value("Guest", res.guest, "id_type"):
			validate_id_type(res.property, id_type)
		changes["id_type"] = id_type
	if id_number is not None and id_number.strip():
		from kamra import localization as loc
		stored = loc.store_id_number(loc.pack_for(res.property),
		                           id_type or frappe.db.get_value("Guest", res.guest, "id_type"),
		                           id_number)
		if stored is not None:
			changes["id_number"] = stored
		elif "•" not in id_number:
			changes["id_number"] = id_number.strip()
	current = frappe.db.get_value("Guest", res.guest, list(changes), as_dict=True) \
		if changes else {}
	changes = {k: v for k, v in changes.items() if (current or {}).get(k) != v}
	if changes:
		# field names only: the activity log never holds the ID number itself
		changed = ", ".join(sorted(changes))
		frappe.db.set_value("Guest", res.guest, changes)
		from kamra.savings import log_action
		log_action("guest_details", "Reservation", res.name, res.property,
		           rationale=f"Desk updated {changed}")
	return checkin_flow(reservation)


@frappe.whitelist(methods=["POST"])
@require_roles(*STAFF)
def confirm_billing(reservation: str, payer: str, note: str | None = None):
	"""The desk confirms who pays (OTA, guest, company, group)."""
	res = _res(reservation)
	_open(res)
	if payer not in PAYERS:
		frappe.throw(_("Pick who pays: {0}.").format(", ".join(_(p) for p in PAYERS)))
	if payer == "Company" and not res.get("company"):
		frappe.throw(_("This booking has no company. Add the company to the booking first."))
	if payer == "Group" and not res.get("group_booking"):
		frappe.throw(_("This booking is not part of a group."))
	record_step(res, "billing_check", "done", note=note, payer=payer)
	return checkin_flow(reservation)


@frappe.whitelist(methods=["POST"])
@require_roles(*STAFF)
def assign_checkin_room(reservation: str, room: str | None = None):
	"""Keep the assigned room, or put the guest in another free room of
	the booked type. Upgrades and downgrades (a different type, maybe a
	new price) go through the room move screen (room_move_preview +
	move_reservation), which also records who assigned the room."""
	res = _res(reservation)
	_open(res)
	if res.status != "Confirmed":
		frappe.throw(_("The guest is already in house. Use Room move to change rooms."))
	if room and room != res.room:
		new_type = frappe.db.get_value("Room", room, "room_type")
		if new_type != res.room_type:
			frappe.throw(_("That room is another type. Use Upgrade or change type, so the price is shown first."))
		from kamra.api import move_reservation
		move_reservation(reservation, room, reason="Assigned at check-in")
		res.reload()
	if not res.room:
		ctx_room = _room(res)
		if not ctx_room.get("entire_place"):
			frappe.throw(_("Pick a room first."))
	number = frappe.db.get_value("Room", res.room, "room_number") if res.room else None
	record_step(res, "assign_room", "done",
	            note=_("Room {0}").format(number) if number else _("Whole place"),
	            room=res.room)
	return checkin_flow(reservation)


@frappe.whitelist(methods=["POST"])
@require_roles(*STAFF)
def sign_registration_card(reservation: str, signature: str | None = None,
                           on_paper: int = 0):
	"""The guest signs the registration card on screen (stored like the
	online signature) or on the printed card (on_paper=1)."""
	res = _res(reservation)
	_open(res)
	signed = bool(signature and str(signature).startswith("data:image"))
	if not signed and not cint(on_paper):
		frappe.throw(_("Have the guest sign on screen, or tick that they signed the printed card."))
	if signed:
		if len(signature) > 400_000:
			frappe.throw(_("That signature image is too large."))
		frappe.db.set_value("Reservation", res.name, {
			"precheckin_signature": signature, "precheckin_consent": 1,
		}, update_modified=False)
		res.precheckin_signature = signature
	record_step(res, "registration_card", "done",
	            note=_("Signed on screen") if signed else _("Signed on paper"),
	            method="screen" if signed else "paper")
	return checkin_flow(reservation)


@frappe.whitelist(methods=["POST"])
@require_roles(*STAFF)
def issue_keys(reservation: str, key_count: int = 1,
               key_cards: str | None = None):
	"""Record the keys handed to the guest, and who handed them. With a
	connected lock system the keys are made by it as soon as the guest is
	checked in (now, if already in house); with no lock system the desk
	encodes the cards at the encoder and notes the card numbers here."""
	res = _res(reservation)
	_open(res)
	count = cint(key_count)
	if count < 1 or count > 10:
		frappe.throw(_("Keys: between 1 and 10."))
	cards = (key_cards or "").strip()[:280] or None
	now = now_datetime()
	frappe.db.set_value("Reservation", res.name, {
		"key_count": count, "key_cards": cards,
		"keys_issued_by": frappe.session.user, "keys_issued_at": now,
	}, update_modified=False)
	res.key_count, res.key_cards = count, cards
	from kamra.door_lock import get_adapter
	adapter = get_adapter(res.property)
	result = None
	if adapter.key == "manual":
		number = frappe.db.get_value("Room", res.room, "room_number") if res.room else ""
		result = {"ok": True, "adapter": "manual", "manual": True,
		          "message": _("Encode {0} key card(s) for room {1} at the encoder.")
		          .format(count, number or "")}
	elif res.status == "Checked In" and res.room:
		result = _call_adapter(adapter, res, count)
	record_step(res, "keys", "done", note=_("{0} key(s)").format(count),
	            count=count, adapter=adapter.key)
	out = checkin_flow(reservation)
	out["key_result"] = result
	return out


@frappe.whitelist(methods=["POST"])
@require_roles(*STAFF)
def log_checkin_requests(reservation: str, requests=None, note: str | None = None):
	"""Quick requests at check-in become service tickets (one each); a free
	note is kept on the step and, if given alone, raised as one ticket."""
	res = _res(reservation)
	_open(res)
	if isinstance(requests, str):
		requests = frappe.parse_json(requests) if requests.strip() else []
	requests = [r for r in (requests or []) if r in REQUEST_PRESETS]
	note = (note or "").strip()[:500]
	from kamra.api import create_ticket
	tickets = []
	for key in requests:
		subject, category, priority = REQUEST_PRESETS[key]
		tickets.append(create_ticket(
			res.property, f"{subject} ({res.guest_name})", category,
			priority=priority, room=res.room, reservation=res.name,
			guest=res.guest, description=note or None)["ticket"])
	if note and not requests:
		tickets.append(create_ticket(
			res.property, f"Request at check-in ({res.guest_name})", "Front Desk",
			room=res.room, reservation=res.name, guest=res.guest,
			description=note)["ticket"])
	record_step(res, "guest_requests", "done",
	            note=", ".join(REQUEST_PRESETS[k][0] for k in requests) or note or _("Nothing needed"),
	            tickets=tickets)
	out = checkin_flow(reservation)
	out["tickets"] = tickets
	return out


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Night Auditor", "Finance", "Hotel Admin")
def set_room_charges(reservation: str, allowed: int = 1, reason: str | None = None):
	"""May the guest charge outlets, laundry and minibar to the room? POS,
	laundry and minibar postings check this flag. Changeable later in the
	stay by the desk or finance (logged)."""
	res = _res(reservation)
	if res.status not in ("Confirmed", "Checked In"):
		frappe.throw(_("Only a confirmed or in-house stay can change this."))
	allowed = 1 if cint(allowed) else 0
	frappe.db.set_value("Reservation", res.name, "room_charges_allowed", allowed,
	                    update_modified=False)
	res.room_charges_allowed = allowed
	record_step(res, "room_charges", "done",
	            note=(_("Room charges allowed") if allowed else _("Room charges blocked"))
	            + (f": {reason.strip()}" if (reason or "").strip() else ""),
	            allowed=allowed)
	return checkin_flow(reservation)
