"""Shared MCP tool registry — one list for stdio, remote HTTP, and docs.

Each tool wraps a governed Kamra API endpoint. Money and availability stay
in the PMS; the model only calls these tools. Role gates on the underlying
whitelist (`require_roles` / `_kamra_roles`) decide what a connected user
can see and call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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


def _p(typ: str, **extra: Any) -> dict[str, Any]:
	return {"type": typ, **extra}


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
		voucher, GST). Use before every booking.""",
		{
			"room_type": _p("string"),
			"check_in_date": _p("string"),
			"check_out_date": _p("string"),
			"adults": _p("integer"),
			"children": _p("integer"),
			"meal_plan": _p("string"),
			"voucher_code": _p("string"),
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
		free room, applies the voucher, prices via the engine.""",
		{
			"guest_name": _p("string"),
			"room_type": _p("string"),
			"check_in_date": _p("string"),
			"check_out_date": _p("string"),
			"phone": _p("string"),
			"adults": _p("integer"),
			"children": _p("integer"),
			"meal_plan": _p("string"),
			"voucher_code": _p("string"),
		},
		required=("guest_name", "room_type", "check_in_date", "check_out_date"),
		property=True,
		mutating=True,
		extra={"source": "AI Agent"},
	),
	_t(
		"add_to_waitlist",
		"api.create_booking",
		"""Park a stay on the waitlist (no room) — for dates that are sold out or
		restricted. Promote it later with promote_waitlist when a room frees.""",
		{
			"guest_name": _p("string"),
			"room_type": _p("string"),
			"check_in_date": _p("string"),
			"check_out_date": _p("string"),
			"phone": _p("string"),
			"adults": _p("integer"),
			"children": _p("integer"),
		},
		required=("guest_name", "room_type", "check_in_date", "check_out_date"),
		property=True,
		mutating=True,
		extra={"waitlist": 1, "source": "AI Agent"},
	),
	_t(
		"waitlist_ready",
		"api.waitlist_ready",
		"""Waitlisted stays that can NOW be booked — a room has freed up for their
		dates. Each item includes the guest name and phone, so you can proactively
		reach out. Poll this to catch openings the moment they appear — the wedge
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
		applies automatically — free outside the window, else the configured
		fee posts to the folio. Returns a cancellation number — always give
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
		"check_in",
		"api.check_in",
		"Check a guest in (opens their folio, marks the room occupied).",
		{"reservation": _p("string"), "room": _p("string")},
		required=("reservation",),
		mutating=True,
	),
	_t(
		"check_out",
		"api.check_out",
		"""Check a guest out (posts remaining nights to the folio, frees the
		room, queues housekeeping). Confirm with the user first.""",
		{"reservation": _p("string")},
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
		folio — corporate room/meals go to the Company folio, alcohol and
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
		master — company pays the stay, guests pay their extras.""",
		{"group_booking": _p("string")},
		required=("group_booking",),
		group="Groups",
	),
	_t(
		"split_folio_charge",
		"api.split_folio_charge",
		"""Split one charge line between two folios of the same stay — e.g.
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
		"update_occupants",
		"api.update_occupants",
		"""Record everyone staying in the room (the legal hotel register,
		printed on the GRC). occupants = [{full_name, age, gender,
		nationality, id_type, id_number, phone}] — replaces the list.""",
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
		the owner's rate guardrails — the PMS rejects rates outside the
		floor/ceiling. Always give a reason (it goes in the audit trail).""",
		{
			"room_type": _p("string"),
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
		agent hours saved. Turn this into a short, warm briefing — never
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
		as a crisp shift briefing — never change the figures.""",
		{"date": _p("string")},
		property=True,
		group="Briefings",
	),
	_t(
		"setup_property",
		"api.setup_property",
		"""Onboard a whole property in one call — the migration assistant's
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
		otherwise the pricing engine quotes. Returns per-row errors — report
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
		"run_night_audit",
		"api.run_night_audit",
		"""Run the end-of-day: post the night's room charges for in-house
		guests and flag no-shows. Idempotent per date.""",
		{"business_date": _p("string")},
		property=True,
		mutating=True,
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
		"""Name a guest into a group's room block — creates their reservation on
		the group's dates against the held inventory.""",
		{
			"group_booking": _p("string"),
			"room_type": _p("string"),
			"guest_name": _p("string"),
			"phone": _p("string"),
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
		sell over. Two functions can share a hall morning and evening — only a
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
		(with their courses), and the service list — LED wall, projector, DJ,
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
		quiet. Check banquet_availability first.""",
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
		package's own plate price. chargeable=0 gives it away — it still prints
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
		"""Put a service on a function — projector, LED wall, DJ, podium, stage,
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
		"""Move a function along: Enquiry → Tentative → Confirmed → Completed, or
		out as Cancelled / Lost. Cancelling or losing needs a reason. Confirming
		takes the hall and will refuse a clash with another confirmed function.""",
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
		"banquet_quote",
		"banquet.generate_quote",
		"""Stamp a quotation — bumps the version, dates it, and returns the whole
		document so it can be read back or emailed.""",
		{"function": _p("string"), "valid_days": _p("integer")},
		required=("function",),
		mutating=True,
		group="Banquets",
	),
	_t(
		"banquet_event_order",
		"banquet.generate_beo",
		"""Issue the banquet event order — the running sheet the banquet, kitchen
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
		"""Every hall and every session across a whole month — the grid that
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
		served, deducts any damage from the refundable deposit — a reason is
		required, and you can't deduct more than is held — and returns the rest
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
		— the sheet the customer signs off and the kitchen cooks from.""",
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
)

BY_NAME: dict[str, ToolSpec] = {t.name: t for t in TOOLS}
TOOL_COUNT = len(TOOLS)
INSTRUCTIONS = (
	"You are operating a hotel through Kamra PMS. Money and "
	"availability are computed by the PMS, never estimate them "
	"yourself — always quote before booking. Confirm irreversible "
	"actions (checkout, cancelling a stay, closing a folio) with the "
	"user first."
)

_JSON_TYPES = {
	"string": str,
	"integer": int,
	"number": float,
	"boolean": bool,
	"array": list,
	"object": dict,
}


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
	for key, schema in spec.parameters.items():
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


def allowed_tools(roles: set[str] | None = None) -> list[ToolSpec]:
	return [spec for spec in TOOLS if tool_allowed(spec, roles)]


def call_tool(spec: ToolSpec, arguments: dict[str, Any], property: str) -> Any:
	"""Run a tool as the current Frappe user. Mutating calls are logged."""
	import frappe

	from kamra.savings import log_action

	if not tool_allowed(spec):
		frappe.throw("Your role doesn't include this action.", frappe.PermissionError)
	fn = resolve_endpoint(spec.dotted)
	kwargs = prepare_arguments(spec, arguments or {}, property)
	frappe.flags.kamra_agent_call = True
	try:
		result = fn(**kwargs)
	finally:
		frappe.flags.kamra_agent_call = False
	if spec.mutating:
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
