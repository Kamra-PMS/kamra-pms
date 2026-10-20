"""Shared MCP tool registry - one list for stdio, remote HTTP, and docs.

Each tool wraps a governed Kamra API endpoint. Money and availability stay
in the PMS; the model only calls these tools. Visibility is the intersection
of (1) the signed-in user's Frappe roles via `require_roles` / `_kamra_roles`
and (2) the property's `enabled_modules` (tool `module` must be on).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kamra.reservation_state import AGENT_DUPLICATE_WINDOW_MINUTES

# Tool group → Property.enabled_modules slug. None = always offered when
# role-allowed (briefings / onboarding stay available).
GROUP_MODULE: dict[str, str | None] = {
	"Front desk": "front-desk",
	"Ops": "operations",
	"Billing": "finance",
	"Revenue": "revenue",
	"Briefings": "front-desk",
	"Onboarding": "admin",
	"Night audit": "finance",
	"Groups": "front-desk",
	"Banquets": "events",
	"Housekeeping": "housekeeping",
	"F&B": "fnb",
	"Laundry": "fnb",
	"Channels": "booking-engine",
}


@dataclass(frozen=True)
class ToolSpec:
	name: str
	dotted: str
	description: str
	parameters: dict[str, dict[str, Any]]
	required: tuple[str, ...] = ()
	inject_property: bool = False
	mutating: bool = False
	extra: dict[str, Any] = field(default_factory=dict)
	bool_as_int: tuple[str, ...] = ()
	group: str = "Front desk"
	module: str | None = None


def _p(typ: str, **extra: Any) -> dict[str, Any]:
	return {"type": typ, **extra}


# Booking references: the PMS resolves these to this property's IDs
# (kamra/booking_refs.py) and refuses unknown or ambiguous values with the
# list of valid options - it never guesses.
ROOM_TYPE_PARAM = _p(
	"string",
	description="Room type: its id (e.g. 'Kamra Demo Palace-DLX'), its code "
	"('DLX') or its exact name ('Deluxe'). See booking_options.",
)
MEAL_PLAN_PARAM = _p(
	"string",
	description="Optional meal plan: id, code ('CP') or exact label "
	"('Breakfast Included'). See booking_options.",
)
RATE_PLAN_PARAM = _p(
	"string",
	description="Optional rate plan: id, code ('BAR') or exact name. "
	"See booking_options.",
)
COMPANY_PARAM = _p(
	"string",
	description="Optional Corporate Account id (see booking_options). With no "
	"rate_plan, the company's negotiated rate plan prices the stay.",
)
IDEMPOTENCY_KEY_PARAM = _p(
	"string",
	description="Optional unique key for this booking (e.g. a UUID). Retrying "
	"with the same key returns the first booking instead of a duplicate. "
	"Reusing a key for a different booking is refused. Without a key, an "
	"identical booking (same guest, room type, dates, meal plan, rate plan "
	f"and party size) made in the last {AGENT_DUPLICATE_WINDOW_MINUTES} "
	"minutes is returned instead of booking twice; pass a new key to book a "
	"second identical room on purpose.",
)


def _t(
	name: str,
	dotted: str,
	description: str,
	parameters: dict[str, dict[str, Any]],
	*,
	required: tuple[str, ...] = (),
	property: bool = False,
	mutating: bool = False,
	extra: dict[str, Any] | None = None,
	bools: tuple[str, ...] = (),
	group: str = "Front desk",
	module: str | None = None,
) -> ToolSpec:
	return ToolSpec(
		name=name,
		dotted=dotted,
		description="\n".join(
			line.strip() for line in description.strip().splitlines()
		),
		parameters=parameters,
		required=required,
		inject_property=property,
		mutating=mutating,
		extra=extra or {},
		bool_as_int=bools,
		group=group,
		module=module if module is not None else GROUP_MODULE.get(group),
	)


TOOLS: tuple[ToolSpec, ...] = (
	_t(
		"front_desk_today",
		"api.front_desk_snapshot",
		"""Today's snapshot: arrivals, departures, in-house guests, room board
		and the hours-saved counter.""",
		{},
		property=True,
	),
	_t(
		"availability",
		"api.availability_calendar",
		"""Room availability and nightly rates per room type for the next N
		days. start_date YYYY-MM-DD (default today).""",
		{"start_date": _p("string"), "days": _p("integer")},
		property=True,
	),
	_t(
		"quote",
		"api.get_quote",
		"""Price a stay (deterministic: occupancy pricing, seasons, meal plan,
		voucher, GST). Use before every booking. Room type, meal plan and rate
		plan accept the id, code or exact name; an unknown or ambiguous value
		is refused with the valid options.""",
		{
			"room_type": ROOM_TYPE_PARAM,
			"check_in_date": _p("string"),
			"check_out_date": _p("string"),
			"adults": _p("integer"),
			"children": _p("integer"),
			"meal_plan": MEAL_PLAN_PARAM,
			"rate_plan": RATE_PLAN_PARAM,
			"voucher_code": _p("string"),
			"company": COMPANY_PARAM,
		},
		required=("room_type", "check_in_date", "check_out_date"),
		property=True,
	),
	_t(
		"booking_options",
		"api.booking_options",
		"""Room types, meal plans, rate plans and corporate accounts available
		for booking at this property.""",
		{},
		property=True,
	),
	_t(
		"create_booking",
		"api.create_booking",
		"""Create a reservation. Dedupes the guest by phone, auto-assigns a
		free room, applies the voucher, prices via the engine. Room type,
		meal plan and rate plan accept the id, code or exact name. Safe to
		retry: a repeated call returns the existing booking (see
		idempotency_key) - check idempotent_replay in the result.""",
		{
			"guest_name": _p("string"),
			"room_type": ROOM_TYPE_PARAM,
			"check_in_date": _p("string"),
			"check_out_date": _p("string"),
			"phone": _p("string"),
			"adults": _p("integer"),
			"children": _p("integer"),
			"meal_plan": MEAL_PLAN_PARAM,
			"rate_plan": RATE_PLAN_PARAM,
			"voucher_code": _p("string"),
			"company": COMPANY_PARAM,
			"idempotency_key": IDEMPOTENCY_KEY_PARAM,
		},
		required=("guest_name", "room_type", "check_in_date", "check_out_date"),
		property=True,
		mutating=True,
		extra={"source": "AI Agent"},
	),
	_t(
		"add_to_waitlist",
		"api.create_booking",
		"""Park a stay on the waitlist (no room) - for dates that are sold out or
		restricted. Promote it later with promote_waitlist when a room frees.""",
		{
			"guest_name": _p("string"),
			"room_type": ROOM_TYPE_PARAM,
			"check_in_date": _p("string"),
			"check_out_date": _p("string"),
			"phone": _p("string"),
			"adults": _p("integer"),
			"children": _p("integer"),
			"idempotency_key": IDEMPOTENCY_KEY_PARAM,
		},
		required=("guest_name", "room_type", "check_in_date", "check_out_date"),
		property=True,
		mutating=True,
		extra={"waitlist": 1, "source": "AI Agent"},
	),
	_t(
		"waitlist_ready",
		"api.waitlist_ready",
		"""Waitlisted stays that can NOW be booked - a room has freed up for their
		dates. Each item includes the guest name and phone, so you can proactively
		reach out. Poll this to catch openings the moment they appear - the wedge
		for turning a sold-out 'no' into a booking.""",
		{},
		property=True,
	),
	_t(
		"promote_waitlist",
		"api.promote_waitlist",
		"""Promote a waitlisted stay into a free room (Confirmed). Fails if no room
		is free for its dates.""",
		{"reservation": _p("string")},
		required=("reservation",),
		mutating=True,
	),
	_t(
		"cancellation_preview",
		"api.cancellation_preview",
		"""What cancelling would cost right now (policy window, fee basis,
		estimated fee). ALWAYS read this to the guest before cancelling.""",
		{"reservation": _p("string")},
		required=("reservation",),
	),
	_t(
		"cancel_booking",
		"api.cancel_reservation",
		"""Cancel a confirmed booking. The property's cancellation policy
		applies automatically - free outside the window, else the configured
		fee posts to the folio. Returns a cancellation number - always give
		it to the guest. Reasons: Guest request, Change of plans, Duplicate
		booking, Payment failed, Weather / travel disruption, Booked
		elsewhere, Other. Only waive the fee when a manager authorizes it;
		the waiver is logged.""",
		{
			"reservation": _p("string"),
			"reason": _p("string"),
			"note": _p("string"),
			"waive_fee": _p("boolean"),
		},
		required=("reservation",),
		mutating=True,
		bools=("waive_fee",),
	),
	_t(
		"booking_requests",
		"booking_requests.booking_requests",
		"""Pending Request-to-Book stays (status Requested) waiting for the
		host, with whether each can be accepted right now (rooms_free,
		blocker). A request holds NO room until it is accepted.""",
		{},
		property=True,
	),
	_t(
		"accept_booking_request",
		"booking_requests.accept_booking_request",
		"""Accept a Request-to-Book stay: confirms it and takes a room of its
		type (or the room given). Refused when the dates sold out meanwhile,
		the villa/room lockout applies or a group block holds the rooms -
		then decline it or offer other dates.""",
		{"reservation": _p("string"), "room": _p("string")},
		required=("reservation",),
		mutating=True,
	),
	_t(
		"decline_booking_request",
		"booking_requests.decline_booking_request",
		"""Decline a Request-to-Book stay. A reason is required and is sent
		to the guest (WhatsApp / email when the property has them set up).
		No cancellation fee - the stay was never confirmed.""",
		{"reservation": _p("string"), "reason": _p("string")},
		required=("reservation", "reason"),
		mutating=True,
	),
	_t(
		"check_in_readiness",
		"checkin.check_in_readiness",
		"""Read-only: the property's check-in steps for a stay (ID, who
		pays, room, deposit, registration card, keys...), which are done
		and by whom, and which REQUIRED steps are still open. check_in is
		refused until those are done by the front desk in the guided
		check-in; an agent cannot do or skip them.""",
		{"reservation": _p("string")},
		required=("reservation",),
	),
	_t(
		"check_in",
		"api.check_in",
		"""Check a guest in (opens their folio, marks the room occupied).
		Refused while a required check-in step is open; call
		check_in_readiness first and tell the desk what is missing.""",
		{"reservation": _p("string"), "room": _p("string")},
		required=("reservation",),
		mutating=True,
	),
	_t(
		"check_out",
		"api.check_out",
		"""Check a guest out (posts remaining nights to the folio, frees the
		room, queues housekeeping). Refused while any folio has a balance:
		collect payment or refund first. A corporate stay with credit moves
		to the city ledger automatically, after the property's credit
		control: over the credit limit or with overdue bills it either warns
		(credit_warnings in the result) or is refused with CREDIT_BLOCKED and
		the reason. An agent can never override a credit block - tell the
		user; Finance or a Hotel Admin can override it at the desk. Confirm
		with the user first.""",
		{"reservation": _p("string")},
		required=("reservation",),
		mutating=True,
	),
	_t(
		"checkout_context",
		"api.checkout_context",
		"""Read-only: what stands between a stay and check-out, without
		changing anything. Balances per folio after the nights check-out would
		still post, totals owed by the guest and owed back to the guest, a
		held security deposit, what moves to the city ledger and its credit
		check, open restaurant orders, each folio's invoice, and `blockers`
		(every reason check_out would refuse). Use it before check_out to tell
		the user what to settle; collecting or refunding money is done at the
		desk.""",
		{"reservation": _p("string")},
		required=("reservation",),
	),
	_t(
		"find_reservations",
		"api.find_reservations",
		"""Find reservations by guest name, room number, or reference  - 
		optionally filtered by status (Confirmed, Checked In, Checked Out,
		Cancelled, No Show, Waitlisted). Resolve a room or name to a
		reservation before acting.""",
		{
			"query": _p("string"),
			"status": _p("string"),
			"limit": _p("integer"),
		},
		property=True,
	),
	_t(
		"stay_detail",
		"api.reservation_detail",
		"""Full detail for one reservation: dates, room, guest + stay history,
		folio balance (paid/due), booker, and which actions are available.""",
		{"reservation": _p("string")},
		required=("reservation",),
	),
	_t(
		"amend_stay_preview",
		"api.amend_stay_preview",
		"""What new dates would do to a stay's bill before anything changes:
		current and new totals, the difference and the new nightly rates,
		priced by the engine. Read-only. Call before amend_stay and tell the
		guest / staff the new price.""",
		{
			"reservation": _p("string"),
			"check_in_date": _p("string"),
			"check_out_date": _p("string"),
		},
		required=("reservation", "check_in_date", "check_out_date"),
	),
	_t(
		"amend_stay",
		"api.amend_stay",
		"""Change a stay's dates (extend/shorten). An auto-priced stay is
		re-quoted and its nightly rates re-locked; when the total changes the
		call is refused unless confirm_price=1, so run amend_stay_preview
		first and confirm the new price with staff. Re-checks room overlaps.""",
		{
			"reservation": _p("string"),
			"check_in_date": _p("string"),
			"check_out_date": _p("string"),
			"confirm_price": _p("integer", description="1 = the new price from amend_stay_preview was confirmed."),
		},
		required=("reservation", "check_in_date", "check_out_date"),
		mutating=True,
	),
	_t(
		"move_room",
		"api.move_reservation",
		"""Move a stay to a different room (pre-arrival or mid-stay). Overlap
		guard re-runs; on a checked-in move the old room goes Dirty. A move to
		another room type re-prices an auto-priced stay: check
		room_move_preview and pass confirm_price=1 once the new price is
		agreed. A same-type move keeps the confirmed rates.""",
		{"reservation": _p("string"), "new_room": _p("string"),
		 "confirm_price": _p("integer", description="1 = the re-priced total was confirmed.")},
		required=("reservation", "new_room"),
		mutating=True,
	),
	_t(
		"room_move_preview",
		"api.room_move_preview",
		"""What moving a stay to a room would do to the bill: same type keeps
		the price; another type is re-quoted. Read-only.""",
		{"reservation": _p("string"), "new_room": _p("string")},
		required=("reservation", "new_room"),
	),
	_t(
		"set_late_arrival",
		"api.set_late_arrival",
		"""Flag a confirmed arrival as arriving late (late_arrival=1), with the
		guest's ETA if known, or clear the flag (late_arrival=0). With the
		property's late-arrival protection on, the night audit holds it as
		Due In instead of marking a no-show.""",
		{"reservation": _p("string"),
		 "late_arrival": _p("integer", description="1 = flag late, 0 = clear."),
		 "eta": _p("string", description="Optional ETA as the guest said it, e.g. 01:30.")},
		required=("reservation",),
		mutating=True,
	),
	_t(
		"guest_lookup",
		"api.guests_with_stats",
		"Find guests by name or phone, with stay stats and lifetime value.",
		{"search": _p("string")},
		required=("search",),
	),
	_t(
		"guest_journey",
		"api.guest_journey",
		"""A guest's full history: profile, stats, chronological timeline.
		Load this before talking to a returning guest.""",
		{"guest": _p("string")},
		required=("guest",),
	),
	_t(
		"create_ticket",
		"api.create_ticket",
		"""Log a guest request / issue as a tracked ticket. Categories:
		Housekeeping, Room Service, Maintenance, Front Desk, Concierge,
		Complaint, Other. Priority sets the SLA.""",
		{
			"subject": _p("string"),
			"category": _p("string"),
			"priority": _p("string"),
			"room": _p("string"),
			"description": _p("string"),
		},
		required=("subject", "category"),
		property=True,
		mutating=True,
		extra={"source": "AI Agent"},
		group="Ops",
	),
	_t(
		"list_tickets",
		"api.tickets_list",
		"Open service tickets with SLA/overdue status.",
		{"show_closed": _p("boolean")},
		property=True,
		bools=("show_closed",),
		group="Ops",
	),
	_t(
		"advance_ticket",
		"api.advance_ticket",
		"""Move a service ticket along: In Progress, Resolved, Closed, or
		Cancelled. Pass a resolution_note when resolving.""",
		{
			"ticket": _p("string"),
			"status": _p("string"),
			"resolution_note": _p("string"),
		},
		required=("ticket", "status"),
		mutating=True,
		group="Ops",
	),
	_t(
		"hk_queue",
		"api.hk_queue",
		"""Housekeeping phone view: prioritized task queue and room board.
		Checkout cleans for rooms with an arrival today jump the queue.""",
		{},
		property=True,
		group="Housekeeping",
	),
	_t(
		"hk_update_task",
		"api.hk_update_task",
		"""Start or complete a housekeeping task. Status: In Progress, Done,
		or Verified.""",
		{"task": _p("string"), "status": _p("string")},
		required=("task", "status"),
		mutating=True,
		group="Housekeeping",
	),
	_t(
		"hk_assign_task",
		"api.hk_assign_task",
		"Supervisor hands a task to a specific housekeeper (awaits accept).",
		{"task": _p("string"), "user": _p("string")},
		required=("task", "user"),
		mutating=True,
		group="Housekeeping",
	),
	_t(
		"hk_claim_task",
		"api.hk_claim_task",
		"Housekeeper takes an unassigned task from the pool for themselves.",
		{"task": _p("string")},
		required=("task",),
		mutating=True,
		group="Housekeeping",
	),
	_t(
		"set_room_hk_status",
		"api.set_housekeeping_status",
		"""Set a room's housekeeping status: Clean, Dirty, Inspected, Ready,
		or Out of Order.""",
		{"room": _p("string"), "status": _p("string")},
		required=("room", "status"),
		mutating=True,
		group="Housekeeping",
	),
	_t(
		"hk_post_consumable",
		"api.hk_post_consumable",
		"""Housekeeping posts Minibar or Laundry found in a room onto the
		in-house guest's folio. Other charge types are refused.""",
		{
			"room": _p("string"),
			"charge_type": _p("string"),
			"description": _p("string"),
			"amount": _p("number"),
		},
		required=("room", "charge_type", "description", "amount"),
		mutating=True,
		group="Housekeeping",
	),
	_t(
		"get_folio",
		"api.get_folio",
		"The guest's bill: charge lines, payments, GST, balance.",
		{"reservation": _p("string")},
		required=("reservation",),
		group="Billing",
	),
	_t(
		"add_folio_charge",
		"api.add_folio_charge",
		"""Post a charge to an open folio (F&B, minibar, laundry, late
		checkout…). Amount is pre-tax.""",
		{
			"folio": _p("string"),
			"charge_type": _p("string"),
			"description": _p("string"),
			"amount": _p("number"),
			"gst_rate": _p("number"),
		},
		required=("folio", "charge_type", "description", "amount"),
		mutating=True,
		group="Billing",
	),
	_t(
		"post_stay_charge",
		"api.post_stay_charge",
		"""Post a charge to a stay and let the company billing rules pick the
		folio - corporate room/meals go to the Company folio, alcohol and
		unruled charges to the guest. Prefer this over add_folio_charge when
		you don't know which folio should carry the line.""",
		{
			"reservation": _p("string"),
			"charge_type": _p("string"),
			"description": _p("string"),
			"amount": _p("number"),
			"gst_rate": _p("number"),
			"is_alcohol": _p("boolean"),
		},
		required=("reservation", "charge_type", "description", "amount"),
		mutating=True,
		bools=("is_alcohol",),
		group="Billing",
	),
	_t(
		"group_billing",
		"api.group_folios",
		"""A group's whole billing picture: the consolidated company (master)
		folio plus each member reservation's own folios with balances. Use
		split_folio_charge to move value between a member's bill and the
		master - company pays the stay, guests pay their extras.""",
		{"group_booking": _p("string")},
		required=("group_booking",),
		group="Groups",
	),
	_t(
		"split_folio_charge",
		"api.split_folio_charge",
		"""Split one charge line between two folios of the same stay - e.g.
		a 70/30 corporate deal or a shared room. Give percent OR amount (the
		part that moves to to_folio). Use get_folio first to find folio and
		charge row names.""",
		{
			"from_folio": _p("string"),
			"charge_row": _p("string"),
			"to_folio": _p("string"),
			"percent": _p("number"),
			"amount": _p("number"),
		},
		required=("from_folio", "charge_row", "to_folio"),
		mutating=True,
		group="Billing",
	),
	_t(
		"stay_folios",
		"api.reservation_folios",
		"""All folios of a stay (guest / extra / company / group) with
		balances - plus the group master when the stay is on a block.""",
		{"reservation": _p("string")},
		required=("reservation",),
		group="Billing",
	),
	_t(
		"record_payment",
		"api.add_folio_payment",
		"""Record money received on a folio. mode: Cash, UPI, Card, Bank,
		Link. kind: Payment (default), Advance, or Security Deposit.
		Confirm the amount with staff before calling.""",
		{
			"folio": _p("string"),
			"mode": _p("string"),
			"amount": _p("number"),
			"reference": _p("string"),
			"kind": _p("string"),
		},
		required=("folio", "mode", "amount"),
		mutating=True,
		group="Billing",
	),
	_t(
		"void_charge",
		"api.void_folio_charge",
		"""Remove a WRONG charge line from an open folio (duplicate, wrong
		amount, wrong guest). Pass the folio and the charge line's id (`name`
		from get_folio). For settled/invoiced bills use apply_allowance.""",
		{
			"folio": _p("string"),
			"charge_row": _p("string"),
			"reason": _p("string"),
		},
		required=("folio", "charge_row"),
		mutating=True,
		group="Billing",
	),
	_t(
		"apply_allowance",
		"api.post_allowance",
		"""Credit back part of a bill on an open folio without deleting the
		original line (service recovery, dispute, agreed discount). Needs a
		reason; it goes on the record.""",
		{
			"folio": _p("string"),
			"amount": _p("number"),
			"reason": _p("string"),
			"gst_rate": _p("number"),
		},
		required=("folio", "amount", "reason"),
		mutating=True,
		group="Billing",
	),
	_t(
		"move_charges",
		"api.transfer_folio_charges",
		"""Move charge lines to another folio of the same stay or group.
		charge_rows is a list of charge line names from get_folio.""",
		{
			"from_folio": _p("string"),
			"charge_rows": _p("array", items=_p("string")),
			"to_folio": _p("string"),
		},
		required=("from_folio", "charge_rows", "to_folio"),
		mutating=True,
		group="Billing",
	),
	_t(
		"close_folio",
		"api.close_folio",
		"""Close / settle an open folio and issue the invoice number. Balance
		must be zero (or use part-settle elsewhere). Confirm with staff  - 
		irreversible.""",
		{"folio": _p("string")},
		required=("folio",),
		mutating=True,
		group="Billing",
	),
	_t(
		"update_occupants",
		"api.update_occupants",
		"""Record everyone staying in the room (the legal hotel register,
		printed on the GRC). occupants = [{full_name, age, gender,
		nationality, id_type, id_number, phone}] - replaces the list.""",
		{
			"reservation": _p("string"),
			"occupants": _p("array", items=_p("object")),
		},
		required=("reservation", "occupants"),
		mutating=True,
	),
	_t(
		"set_room_rate",
		"api.set_room_rate",
		"""Set the nightly rate for a room type over a date range. Bounded by
		the owner's rate guardrails - the PMS rejects rates outside the
		floor/ceiling. Always give a reason (it goes in the audit trail).""",
		{
			"room_type": ROOM_TYPE_PARAM,
			"start_date": _p("string"),
			"end_date": _p("string"),
			"rate": _p("number"),
			"reason": _p("string"),
		},
		required=("room_type", "start_date", "end_date", "rate"),
		property=True,
		mutating=True,
		group="Revenue",
	),
	_t(
		"owner_briefing",
		"api.owner_briefing",
		"""The owner's morning numbers: occupancy, yesterday's revenue/ADR/
		RevPAR, arrivals/departures, open tickets, next-7-day availability,
		agent hours saved. Turn this into a short, warm briefing - never
		change the figures.""",
		{"date": _p("string")},
		property=True,
		group="Briefings",
	),
	_t(
		"position_briefing",
		"api.position_briefing",
		"""The hotel-position briefing for the GM and front desk: today's
		occupancy against the overbooking ceiling, arrivals sorted by ETA,
		departures with ETDs and balances due, back-to-back room conflicts
		(incoming guest lands before the outgoing one leaves), the demand
		tier pricing is applying, and a 7-day occupancy outlook. Read it out
		as a crisp shift briefing - never change the figures.""",
		{"date": _p("string")},
		property=True,
		group="Briefings",
	),
	_t(
		"setup_property",
		"api.setup_property",
		"""Onboard a whole property in one call - the migration assistant's
		tool. Ask the hotel for their room list/rate card (any format), map
		it into: {property:{property_name, city, gstin?, phone?},
		room_types:[{code,name,base_price,adults?}], rooms:[{room_type_code,
		numbers:[..]}], meal_plans:[{code,price_per_adult}]}. Confirm the
		mapping with the user before calling.""",
		{"payload": _p("object")},
		required=("payload",),
		mutating=True,
		group="Onboarding",
	),
	_t(
		"import_bookings",
		"api.import_bookings",
		"""Migrate existing reservations from another PMS/spreadsheet. Each:
		{guest_name, phone?, room_type_code, check_in, check_out, adults?,
		amount_after_tax?, channel?, status?}. Fixed amounts are preserved;
		otherwise the pricing engine quotes. Returns per-row errors - report
		them to the user rather than silently dropping rows.""",
		{
			"bookings": _p("array", items=_p("object")),
			"property": _p("string"),
		},
		required=("bookings",),
		property=True,
		mutating=True,
		group="Onboarding",
	),
	_t(
		"send_payment_link",
		"api.folio_payment_link",
		"""Create a Razorpay payment link for a folio's outstanding balance
		(SMS/email to the guest when contact details exist).""",
		{"folio": _p("string")},
		required=("folio",),
		mutating=True,
		group="Billing",
	),
	_t(
		"send_deposit_link",
		"api.deposit_payment_link",
		"""Create a payment link for a booking's deposit before arrival - the
		deposit still due (the property's deposit %) unless an amount is
		given. When the guest pays, it posts to the folio as an Advance and
		confirms a held booking. Returns the link and a ready-to-send message.""",
		{"reservation": _p("string"), "amount": _p("number")},
		required=("reservation",),
		mutating=True,
		group="Billing",
	),
	_t(
		"company_credit_status",
		"credit.company_credit_status",
		"""A company's credit position before billing it more: its credit
		limit (0 = none), what it owes on the city ledger and on stays in
		house, bills overdue past the grace period, and whether billing
		`amount` more would be warned or blocked by the property's credit
		control. Read-only. Bookings on company billing and check-outs run
		the same check; an agent can't override a block.""",
		{"company": _p("string"), "amount": _p("number")},
		required=("company",),
		property=True,
		group="Billing",
	),
	_t(
		"security_deposit_status",
		"api.security_deposit",
		"""The stay's refundable security (damage) deposit: the property's
		policy amount, what is held, withheld and refunded, and whether it is
		still holding up check-out. Withholding and refunding are done by
		staff at the desk (cashier PIN) - not by an agent.""",
		{"reservation": _p("string")},
		required=("reservation",),
		group="Billing",
	),
	_t(
		"collect_security_deposit",
		"api.collect_security_deposit",
		"""Record a refundable security deposit the guest has paid (villas:
		the damage deposit). It is held on the guest folio as a liability,
		not revenue, and refunded or withheld at check-out. mode: one of the
		property's payment modes. Confirm the amount with staff first.""",
		{
			"reservation": _p("string"),
			"amount": _p("number"),
			"mode": _p("string"),
			"reference": _p("string"),
		},
		required=("reservation", "amount", "mode"),
		mutating=True,
		group="Billing",
	),
	_t(
		"waive_security_deposit",
		"api.waive_security_deposit",
		"""Waive the property's security deposit for one stay. A reason is
		required and goes on the record; refused once money was taken.""",
		{"reservation": _p("string"), "reason": _p("string")},
		required=("reservation", "reason"),
		mutating=True,
		group="Billing",
	),
	_t(
		"run_night_audit",
		"api.run_night_audit",
		"""Run the end-of-day for the property's current business date: post
		the night's room charges for in-house guests at their confirmed
		nightly rates, flag no-shows per the property's no-show policy, then
		roll the business date forward. Call night_audit_precheck first: the
		run is refused while a blocking check (open tills, open restaurant
		bills, departures still in house) has items. Resolve them, or - only
		when a staff member confirms and gives the reason - pass acknowledge
		(the blocking check keys) and note (the reason); who acknowledged it
		is recorded on the run. Late arrivals due on the closed date may be
		held as Due In (held_late_arrivals); OTA no-shows may carry no fee
		(no_show_fees_waived). Each run saves an audit pack (has_pack).
		business_date is optional; if given it must equal the current
		business date. A day that already closed returns already_ran.""",
		{
			"business_date": _p("string", description="Optional. Must equal the current business date."),
			"acknowledge": _p("array", items=_p("string"),
			                  description="Blocking check keys to acknowledge, e.g. open_tills."),
			"note": _p("string", description="Reason for acknowledging the blocking checks."),
		},
		property=True,
		mutating=True,
		group="Night audit",
	),
	_t(
		"night_audit_precheck",
		"night_audit.night_audit_precheck",
		"""The night audit checklist for the current business date, read-only.
		Checks: open_tills, open_pos_bills, departures_due (blocking by
		default), arrivals_pending (with what the no-show policy will do),
		rate_variance, pos_room_postings, high_balance, credit_limit and
		room_status. Each has severity (block | warn | info), count, items
		(reservation, folio, room, guest, amount, outlet / bill no) and a
		suggested action. blockers lists the checks stopping a manual run;
		can_run is true when there are none.""",
		{},
		property=True,
		group="Night audit",
	),
	_t(
		"create_group_block",
		"api.create_group_block",
		"""Draft a MICE piece of business in one call: a group booking with a room
		block (list of {room_type, rooms_blocked, block_rate}) and optionally its
		banquet event. The agent wedge: turn "30 rooms + a 200-pax wedding on
		Dec 12" into a live proposal. Starts Open; confirming it holds the rooms
		out of general sale until the cutoff date.""",
		{
			"group_name": _p("string"),
			"check_in_date": _p("string"),
			"check_out_date": _p("string"),
			"blocks": _p("array", items=_p("object")),
			"company": _p("string"),
			"cutoff_date": _p("string"),
			"venue": _p("string"),
			"event_type": _p("string"),
			"event_date": _p("string"),
			"attendees": _p("integer"),
			"customer_phone": _p("string"),
		},
		required=("group_name", "check_in_date", "check_out_date", "blocks"),
		property=True,
		mutating=True,
		group="Groups",
	),
	_t(
		"group_pickup_status",
		"api.group_detail",
		"""Group Rooms Control: the block, per-room-type pickup (blocked / picked
		up / remaining), rooming list, tied event and master folio.""",
		{"group_booking": _p("string")},
		required=("group_booking",),
		group="Groups",
	),
	_t(
		"pickup_group_room",
		"api.pickup_group_room",
		"""Name a guest into a group's room block - creates their reservation on
		the group's dates against the held inventory.""",
		{
			"group_booking": _p("string"),
			"room_type": ROOM_TYPE_PARAM,
			"guest_name": _p("string"),
			"phone": _p("string"),
			"adults": _p("integer"),
			"children": _p("integer"),
			"idempotency_key": _p(
				"string",
				description="Optional unique key for this pickup (e.g. a "
				"UUID). Retrying with the same key returns the first "
				"reservation; every call without a key books another room.",
			),
		},
		required=("group_booking", "room_type", "guest_name"),
		mutating=True,
		group="Groups",
	),
	# Banquets
	_t(
		"banquet_availability",
		"banquet.venue_availability",
		"""Which halls are free for a date, hours and pax. A confirmed function
		takes the hall; a tentative hold is shown as a soft hold you can still
		sell over. Two functions can share a hall morning and evening - only a
		real overlap in hours counts as taken. Run this before every enquiry.""",
		{
			"event_date": _p("string"),
			"end_date": _p("string"),
			"start_time": _p("string"),
			"end_time": _p("string"),
			"pax": _p("integer"),
		},
		required=("event_date",),
		property=True,
		group="Banquets",
	),
	_t(
		"banquet_catalogue",
		"banquet.banquet_catalogue",
		"""What the property sells at a function: menu packages priced per plate
		(with their courses), and the service list - LED wall, projector, DJ,
		podium, stage, decor, laptop, bar. Read this before quoting anything;
		never invent a price.""",
		{},
		property=True,
		group="Banquets",
	),
	_t(
		"banquet_enquiry",
		"banquet.create_enquiry",
		"""Open a function sheet from an enquiry. The hall's rack rental goes on
		as the first line and a follow-up is diarised, so the enquiry can't go
		quiet. Halls sell by session: pass session (Morning / Afternoon /
		Evening / Full Day) and the hours follow it, or session "Custom Hours"
		with start_time and end_time. Check banquet_availability first.""",
		{
			"venue": _p("string"),
			"event_date": _p("string"),
			"customer_name": _p("string"),
			"event_type": _p("string"),
			"attendees": _p("integer"),
			"customer_phone": _p("string"),
			"customer_email": _p("string"),
			"company": _p("string"),
			"end_date": _p("string"),
			"session": _p("string"),
			"start_time": _p("string"),
			"end_time": _p("string"),
			"source": _p("string"),
			"requirements": _p("string"),
		},
		required=("venue", "event_date", "customer_name"),
		property=True,
		mutating=True,
		group="Banquets",
	),
	_t(
		"banquet_sheet",
		"banquet.function_sheet",
		"""One function in full: dates, pax (expected / guaranteed / actual),
		every line item with its chargeable flag, the negotiation history,
		payment terms, receipts, and what it still needs from somebody.""",
		{"function": _p("string")},
		required=("function",),
		group="Banquets",
	),
	_t(
		"banquet_add_menu",
		"banquet.add_menu",
		"""Put a menu package on a function. Left alone the quantity follows the
		pax rule (guaranteed, or actual if more turned up) and the price is the
		package's own plate price. chargeable=0 gives it away - it still prints
		on the event order, it just leaves the quote.""",
		{
			"function": _p("string"),
			"menu": _p("string"),
			"qty": _p("number"),
			"rate": _p("number"),
			"chargeable": _p("integer"),
		},
		required=("function", "menu"),
		mutating=True,
		group="Banquets",
	),
	_t(
		"banquet_add_service",
		"banquet.add_service",
		"""Put a service on a function - projector, LED wall, DJ, podium, stage,
		decor, laptop, bar. The catalogue decides chargeable by default; pass
		chargeable=0 to throw it in for this function.""",
		{
			"function": _p("string"),
			"service_item": _p("string"),
			"qty": _p("number"),
			"rate": _p("number"),
			"chargeable": _p("integer"),
		},
		required=("function", "service_item"),
		mutating=True,
		group="Banquets",
	),
	_t(
		"banquet_negotiate",
		"banquet.negotiate",
		"""Move the price: a headline discount on the whole quote, or the hall
		rate on its own. Every move is snapshotted with what the quote was worth
		before and after, so the fourth revision stays explainable. Confirm the
		new total with the user before calling.""",
		{
			"function": _p("string"),
			"discount_amount": _p("number"),
			"venue_rental": _p("number"),
			"note": _p("string"),
		},
		required=("function",),
		mutating=True,
		group="Banquets",
	),
	_t(
		"banquet_payment_terms",
		"banquet.set_payment_terms",
		"""Set the payment schedule: [{milestone, due_date, percent | amount}].
		A term stated as a percentage follows the quote as it moves; one stated
		as an amount is a number both sides agreed and stays put.""",
		{
			"function": _p("string"),
			"terms": _p("array", items=_p("object")),
			"note": _p("string"),
		},
		required=("function",),
		mutating=True,
		group="Banquets",
	),
	_t(
		"banquet_record_receipt",
		"banquet.record_receipt",
		"""Record money in against a function (Advance / Payment / Security
		Deposit / Refund).""",
		{
			"function": _p("string"),
			"amount": _p("number"),
			"mode": _p("string"),
			"kind": _p("string"),
			"reference": _p("string"),
		},
		required=("function", "amount"),
		mutating=True,
		group="Banquets",
	),
	_t(
		"banquet_status",
		"banquet.set_status",
		"""Move a function along: Enquiry → Tentative → Confirmed, or out as
		Cancelled / Lost. Cancelling or losing needs a reason. Confirming takes
		the hall and will refuse a clash with another confirmed function. A
		confirmed function is completed with banquet_close_out, not here.""",
		{
			"function": _p("string"),
			"status": _p("string"),
			"reason": _p("string"),
		},
		required=("function", "status"),
		mutating=True,
		group="Banquets",
	),
	_t(
		"banquet_link_group",
		"banquet.link_group",
		"""Tie a function to a group booking at the same property so its bill
		rides the group's master folio when it is posted to the bill, or untie
		it by leaving group_booking empty. Refused once the function is billed.""",
		{
			"function": _p("string"),
			"group_booking": _p("string"),
		},
		required=("function",),
		mutating=True,
		group="Banquets",
	),
	_t(
		"banquet_quote",
		"banquet.generate_quote",
		"""Stamp a quotation - bumps the version, dates it, and returns the whole
		document so it can be read back or emailed.""",
		{"function": _p("string"), "valid_days": _p("integer")},
		required=("function",),
		mutating=True,
		group="Banquets",
	),
	_t(
		"banquet_event_order",
		"banquet.generate_beo",
		"""Issue the banquet event order - the running sheet the banquet, kitchen
		and AV teams work the day from, with the menus expanded into courses.
		Only a confirmed function gets one.""",
		{"function": _p("string")},
		required=("function",),
		mutating=True,
		group="Banquets",
	),
	_t(
		"banquet_document",
		"banquet.banquet_document",
		"""Fetch a function's paper without re-issuing it. kind: quote, contract,
		beo, pack_list, invoice. The pack list is what physically has to reach
		the hall, complimentary items included.""",
		{"function": _p("string"), "kind": _p("string")},
		required=("function",),
		group="Banquets",
	),
	_t(
		"banquet_pipeline",
		"banquet.banquet_pipeline",
		"""The banquet sales picture, month by month and by status: what's
		confirmed, what's still in play, what's outstanding, the conversion
		rate, and why business went away. Dated on the event, not the enquiry.""",
		{
			"from_date": _p("string"),
			"to_date": _p("string"),
			"months": _p("integer"),
		},
		property=True,
		group="Banquets",
	),
	_t(
		"banquet_reminders",
		"banquet.banquet_reminders",
		"""Everything that needs chasing: follow-ups gone quiet, tentative holds
		about to lapse, payments due, event orders missing before the date,
		functions confirmed with nothing received.""",
		{"days": _p("integer")},
		property=True,
		group="Banquets",
	),
	_t(
		"banquet_month",
		"banquet.month_availability",
		"""Every hall and every session across a whole month - the grid that
		answers "do you have the 14th of December?" in one look. Halls are sold
		by session (Morning / Afternoon / Evening), not by the hour, so a hall
		can take a morning conference and an evening wedding on the same day.
		month is YYYY-MM; omit for the current one.""",
		{"month": _p("string")},
		property=True,
		group="Banquets",
	),
	_t(
		"banquet_close_out",
		"banquet.close_out",
		"""Hand the hall back after the function. Records the covers actually
		served, deducts any damage from the refundable deposit - a reason is
		required, and you can't deduct more than is held - and returns the rest
		as a real refund line. Closes the function.""",
		{
			"function": _p("string"),
			"damage_amount": _p("number"),
			"damage_note": _p("string"),
			"pax_actual": _p("integer"),
			"refund_deposit": _p("integer"),
		},
		required=("function",),
		mutating=True,
		group="Banquets",
	),
	_t(
		"banquet_register",
		"banquet.banquet_register",
		"""The banquet office's books for a period. register is one of:
		functions (everything booked), quotations (what was quoted and whether
		it landed), enquiries (what came in), receipts (the cash book, by
		mode), sales (revenue rolled up by hall, event type, session and
		source).""",
		{
			"register": _p("string"),
			"from_date": _p("string"),
			"to_date": _p("string"),
		},
		property=True,
		group="Banquets",
	),
	_t(
		"banquet_menu_card",
		"banquet.menu_card",
		"""What will actually be served, course by course, with no prices on it
		 -  the sheet the customer signs off and the kitchen cooks from.""",
		{"function": _p("string")},
		required=("function",),
		group="Banquets",
	),
	_t(
		"banquet_receipt_document",
		"banquet.receipt_document",
		"""One receipt as a document the customer can keep, with the amount in
		words and the running balance on the function.""",
		{"function": _p("string"), "receipt": _p("string")},
		required=("function", "receipt"),
		group="Banquets",
	),
	# ── F&B / POS ────────────────────────────────────────────────────────
	_t(
		"pos_outlets",
		"pos.outlets",
		"List F&B outlets (restaurant, bar, room service) for this property.",
		{},
		property=True,
		group="F&B",
	),
	_t(
		"pos_menu",
		"pos.pos_menu",
		"Menu items for an outlet (with courses, prices, allergens).",
		{"outlet": _p("string")},
		required=("outlet",),
		group="F&B",
	),
	_t(
		"pos_table_map",
		"pos.table_map",
		"Floor plan: tables with occupancy, open checks, and reservations.",
		{"outlet": _p("string")},
		required=("outlet",),
		group="F&B",
	),
	_t(
		"pos_open_orders",
		"pos.open_orders",
		"Open POS checks at an outlet.",
		{"outlet": _p("string")},
		required=("outlet",),
		group="F&B",
	),
	_t(
		"pos_order_detail",
		"pos.order_detail",
		"One POS order: items, KOTs, totals, payment state.",
		{"order": _p("string")},
		required=("order",),
		group="F&B",
	),
	_t(
		"pos_create_order",
		"pos.create_order",
		"""Open a POS check. items = [{item, qty, notes?}]. Optionally bind
		table_no and/or a room/reservation for room charge.""",
		{
			"outlet": _p("string"),
			"items": _p("array", items=_p("object")),
			"table_no": _p("string"),
			"room": _p("string"),
			"reservation": _p("string"),
			"guests": _p("integer"),
			"customer_name": _p("string"),
			"customer_phone": _p("string"),
			"order_type": _p("string"),
			"notes": _p("string"),
		},
		required=("outlet", "items"),
		property=True,
		mutating=True,
		group="F&B",
	),
	_t(
		"pos_add_items",
		"pos.add_items",
		"Add items to an open POS order. items = [{item, qty, notes?}].",
		{
			"order": _p("string"),
			"items": _p("array", items=_p("object")),
		},
		required=("order", "items"),
		mutating=True,
		group="F&B",
	),
	_t(
		"pos_confirm_order",
		"pos.confirm_order",
		"Confirm a draft order so it can be fired to the kitchen.",
		{"order": _p("string")},
		required=("order",),
		mutating=True,
		group="F&B",
	),
	_t(
		"pos_fire_kot",
		"pos.fire_kot",
		"Fire a kitchen order ticket (whole check or one course).",
		{"order": _p("string"), "course": _p("string")},
		required=("order",),
		mutating=True,
		group="F&B",
	),
	_t(
		"pos_send_order",
		"pos.send_order",
		"""Open a new POS check and send it straight to the kitchen in one
		step (create, confirm and fire the KOT). Use this for a normal order;
		pos_create_order is for a check you will fire later. items = [{item,
		qty, notes?}]. Optionally bind table_no and/or a room/reservation.""",
		{
			"outlet": _p("string"),
			"items": _p("array", items=_p("object")),
			"table_no": _p("string"),
			"room": _p("string"),
			"reservation": _p("string"),
			"guests": _p("integer"),
			"order_type": _p("string"),
			"customer_name": _p("string"),
			"customer_phone": _p("string"),
			"delivery_address": _p("string"),
			"allergy_note": _p("string"),
			"notes": _p("string"),
		},
		required=("outlet", "items"),
		property=True,
		mutating=True,
		group="F&B",
	),
	_t(
		"pos_send_round",
		"pos.send_round",
		"Add another round to an open POS check and fire it to the kitchen in one step. items = [{item, qty, notes?}].",
		{
			"order": _p("string"),
			"items": _p("array", items=_p("object")),
		},
		required=("order", "items"),
		mutating=True,
		group="F&B",
	),
	_t(
		"pos_kitchen_queue",
		"pos.kitchen_queue",
		"KDS view: tickets waiting / cooking for the property (optional outlet).",
		{"outlet": _p("string")},
		property=True,
		group="F&B",
	),
	_t(
		"pos_pay_order",
		"pos.pay_order",
		"""Settle a POS check. mode: Cash, UPI, Card, Room Charge, etc.
		Confirm the total with staff before calling.""",
		{"order": _p("string"), "mode": _p("string")},
		required=("order", "mode"),
		mutating=True,
		group="F&B",
	),
	_t(
		"pos_orders",
		"pos.orders_list",
		"""Bills at an outlet for a day (default today) or a date range of up
		to 31 days, newest first, each with its state: open (not sent to the
		kitchen), sent, paid, room (posted to a room folio), nc, closed or
		cancelled. Viewing today also lists bills still open from earlier
		days. q searches bill/KOT number, table, room and customer.""",
		{
			"outlet": _p("string"),
			"date": _p("string", description="YYYY-MM-DD; default today"),
			"to_date": _p("string", description="YYYY-MM-DD, end of a range"),
			"q": _p("string"),
			"state": _p("string", enum=["open", "sent", "paid", "room", "nc",
			                            "closed", "cancelled"]),
		},
		required=("outlet",),
		group="F&B",
	),
	_t(
		"pos_cancel_order",
		"pos.cancel_order",
		"""Cancel an open POS bill that has nothing sent to the kitchen yet,
		with a reason (kept on the bill and in the activity log; the table is
		freed). Refused once any item was fired: food the kitchen started is
		voided by a supervisor at the till, never by an agent. Check with
		pos_order_detail first (kitchen_lines must be 0).""",
		{"order": _p("string"), "reason": _p("string")},
		required=("order", "reason"),
		mutating=True,
		group="F&B",
	),
	_t(
		"pos_remove_item",
		"pos.remove_item",
		"""Remove one line that has not been sent to the kitchen from an open
		POS bill (row id from pos_order_detail). Lines the kitchen already has
		are refused, and so is the last line (cancel the bill instead).""",
		{"order": _p("string"), "item_row": _p("string")},
		required=("order", "item_row"),
		mutating=True,
		group="F&B",
	),
	# ── External POS (third-party till posting to a room) ────────────────
	_t(
		"pos_room_lookup",
		"pos_interface.pos_room_lookup",
		"""Find an in-house guest to charge: by room number and/or last name
		(2+ letters). Only checked-in stays at this property; returns room,
		guest name, reservation and departure date.""",
		{"room": _p("string"), "last_name": _p("string")},
		property=True,
		group="F&B",
	),
	_t(
		"pos_post_room_charge",
		"pos_interface.pos_post_room_charge",
		"""Post an outlet ticket (bar, spa, restaurant on another POS) to an
		in-house guest's bill. ticket_id is the POS check number and makes the
		call safe to retry: the same ticket is never posted twice. The billing
		rules pick the folio; alcohol (is_alcohol=true) always goes to the
		guest's own folio. Confirm the amount with staff before calling.""",
		{"ticket_id": _p("string"), "amount": _p("number"),
		 "description": _p("string"), "room": _p("string"),
		 "reservation": _p("string"),
		 "charge_type": _p("string", enum=["Food & Beverage", "Minibar",
		                                   "Laundry", "Spa", "Misc"]),
		 "is_alcohol": _p("boolean"), "outlet_name": _p("string")},
		required=("ticket_id", "amount", "description"),
		property=True,
		mutating=True,
		bools=("is_alcohol",),
		group="F&B",
	),
	# ── Laundry ──────────────────────────────────────────────────────────
	_t(
		"laundry_board",
		"laundry.laundry_board",
		"Laundry ops board: pickups, in-plant, ready, deliveries outstanding.",
		{},
		property=True,
		group="Laundry",
	),
	_t(
		"laundry_rates",
		"laundry.laundry_rates",
		"Rate card for laundry items and service types at this property.",
		{},
		property=True,
		group="Laundry",
	),
	_t(
		"laundry_collect",
		"laundry.collect_laundry",
		"""Collect guest laundry. items = [{item_name, service_type, qty}].
		Bills from the rate card; express=true for rush. Pass order to fill
		a prior pickup request.""",
		{
			"room": _p("string"),
			"items": _p("array", items=_p("object")),
			"express": _p("boolean"),
			"order": _p("string"),
			"notes": _p("string"),
		},
		required=("items",),
		property=True,
		mutating=True,
		bools=("express",),
		group="Laundry",
	),
	_t(
		"laundry_status",
		"laundry.laundry_status",
		"""Advance a laundry bag: Collected → In Process → Ready (one step
		at a time). Use laundry_deliver to finish.""",
		{"order": _p("string"), "status": _p("string")},
		required=("order", "status"),
		mutating=True,
		group="Laundry",
	),
	_t(
		"laundry_deliver",
		"laundry.deliver_laundry",
		"Mark laundry delivered to the guest/room; posts any final charges.",
		{"order": _p("string"), "shortage_note": _p("string")},
		required=("order",),
		mutating=True,
		group="Laundry",
	),
	_t(
		"rooms_board",
		"rooms.rooms_board",
		"""Every room today: housekeeping status, occupancy, the in-house
		guest, who arrives or leaves today, whether the room is held out of
		service, and its open housekeeping task. Read-only.""",
		{},
		property=True,
	),
	_t(
		"room_detail",
		"rooms.room_detail",
		"""One room right now: its type and features, housekeeping status,
		the guest in it (with balance), the next arrival, active out-of-service
		holds and open housekeeping tasks. room is the room id (see
		rooms_board). Read-only.""",
		{"room": _p("string")},
		required=("room",),
	),
	_t(
		"room_availability",
		"rooms.room_availability",
		"""One room night by night (up to 31 days): booked (by whom), held out
		of service, or free. Read-only.""",
		{"room": _p("string"), "start_date": _p("string", format="date"),
		 "days": _p("integer")},
		required=("room",),
	),
	_t(
		"room_history",
		"rooms.room_history",
		"""Who stayed in a room lately (nights, room revenue), who cleaned and
		inspected it and when, its service tickets, and guests moved in or out
		of it. Read-only.""",
		{"room": _p("string"), "limit": _p("integer")},
		required=("room",),
	),
	_t(
		"room_insights",
		"rooms.room_insights",
		"""Per-room numbers for the last 7, 30, 90, 180 or 365 nights: room
		nights and occupancy, posted room revenue, out-of-service nights and
		average cleaning time, with the most and least used rooms. Read-only.""",
		{"days": _p("integer")},
		property=True,
	),
)

BY_NAME: dict[str, ToolSpec] = {t.name: t for t in TOOLS}
TOOL_COUNT = len(TOOLS)
INSTRUCTIONS = (
	"You are operating a hotel through Kamra PMS. Money and "
	"availability are computed by the PMS, never estimate them "
	"yourself - always quote before booking. Confirm irreversible "
	"actions (checkout, cancelling a stay, closing a folio) with the "
	"user first."
)

def input_schema(spec: ToolSpec) -> dict[str, Any]:
	schema: dict[str, Any] = {"type": "object", "properties": spec.parameters}
	if spec.required:
		schema["required"] = list(spec.required)
	return schema


def mcp_tool_list(allowed: list[ToolSpec] | None = None) -> list[dict[str, Any]]:
	out = []
	for spec in allowed if allowed is not None else TOOLS:
		out.append(
			{
				"name": spec.name,
				"description": spec.description,
				"inputSchema": input_schema(spec),
			}
		)
	return out


def prepare_arguments(spec: ToolSpec, arguments: dict[str, Any], property: str) -> dict[str, Any]:
	"""Map MCP arguments onto the Kamra API kwargs."""
	clean: dict[str, Any] = dict(spec.extra)
	for key in spec.parameters:
		if key not in arguments:
			continue
		value = arguments[key]
		if value in ("", None):
			continue
		if key in spec.bool_as_int:
			value = 1 if value in (True, 1, "1", "true", "True") else 0
		clean[key] = value
	if spec.inject_property and "property" not in clean:
		clean["property"] = property
	elif spec.inject_property and not clean.get("property"):
		clean["property"] = property
	return clean


def resolve_endpoint(dotted: str):
	import importlib

	module, attr = dotted.split(".", 1)
	return getattr(importlib.import_module(f"kamra.{module}"), attr)


def tool_allowed(spec: ToolSpec, roles: set[str] | None = None) -> bool:
	fn = resolve_endpoint(spec.dotted)
	allowed = getattr(fn, "_kamra_roles", None)
	if not allowed:
		return True
	if roles is None:
		import frappe

		roles = set(frappe.get_roles())
	return bool(set(roles) & set(allowed))


def module_allowed(spec: ToolSpec, modules: set[str] | None = None,
                   property: str | None = None) -> bool:
	"""Property.enabled_modules gate. Tools with module=None always pass."""
	if not spec.module:
		return True
	if modules is None:
		if not property:
			return True
		from kamra.api import enabled_modules

		modules = set(enabled_modules(property))
	return spec.module in modules


def allowed_tools(
	roles: set[str] | None = None,
	property: str | None = None,
	modules: set[str] | None = None,
) -> list[ToolSpec]:
	"""Tools visible to this identity: role ∩ property modules."""
	if modules is None and property:
		from kamra.api import enabled_modules

		modules = set(enabled_modules(property))
	return [
		spec
		for spec in TOOLS
		if tool_allowed(spec, roles) and module_allowed(spec, modules)
	]


def is_replay(result: Any) -> bool:
	"""True when a write returned an existing record instead of making one
	(idempotency-key replay or a caught duplicate): nothing was executed, so
	no "Executed" audit row is written for it."""
	return isinstance(result, dict) and bool(
		result.get("idempotent_replay") or result.get("duplicate_of_recent"))


def call_tool(spec: ToolSpec, arguments: dict[str, Any], property: str) -> Any:
	"""Run a tool as the current Frappe user. Mutating calls are logged."""
	import frappe

	from kamra.savings import log_action

	if not tool_allowed(spec):
		frappe.throw("Your role doesn't include this action.", frappe.PermissionError)
	if not module_allowed(spec, property=property):
		frappe.throw(
			f"This property does not have the '{spec.module}' module enabled.",
			frappe.PermissionError,
		)
	fn = resolve_endpoint(spec.dotted)
	kwargs = prepare_arguments(spec, arguments or {}, property)
	# the channel doubles as the "agent call" flag the cashier PIN and the
	# booking duplicate guard read
	prev, frappe.flags.kamra_agent_call = frappe.flags.kamra_agent_call, "MCP"
	try:
		result = fn(**kwargs)
	finally:
		frappe.flags.kamra_agent_call = prev
	if spec.mutating and not is_replay(result):
		log_action(
			"mcp_" + spec.name,
			"Property",
			property,
			property,
			rationale=frappe.as_json(kwargs)[:400],
			agent_name="Claude (MCP)",
			channel="MCP",
		)
	return result
