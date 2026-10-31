"""Kamra Agent - the in-app assistant. BYOK, optional, governed.

Talks to any OpenAI-compatible chat endpoint (OpenAI, OpenRouter, Groq,
Ollama, …) with the owner's own key. The model only ever acts through
the same whitelisted tool layer agents use: prices come from the pricing
engine, guardrails and policies apply, and every action lands in the
Agent Action Log. If the model is wrong, the tools refuse.
"""

import json

import frappe
import requests
from frappe.utils import cint, nowdate

from kamra.assistant_privacy import processor_disclosure, scrub_for_llm
from kamra.authz import require_roles
from kamra.llm_compat import chat_payload, retry_chat_payload
# one set of booking-reference parameter docs for MCP and the copilot
from kamra.mcp_tools import (MEAL_PLAN_PARAM,
                             RATE_PLAN_PARAM, ROOM_TYPE_PARAM, is_replay)

MAX_TOOL_ROUNDS = 6
TIMEOUT = 60
OUT_OF_CREDIT = ("Your AI key is out of credit. Top it up with your provider "
                 "or change the key in Settings > AI assistant.")


def _out_of_credit(resp) -> bool:
	"""The provider refused for money, not for the request: OpenAI's 429
	insufficient_quota, OpenRouter's 402, "credit balance is too low"."""
	if resp.status_code == 402:
		return True
	text = (resp.text or "").lower()
	return any(m in text for m in ("insufficient_quota", "billing", "credit"))


def _no_credit() -> dict:
	# the code lets the chat screen add a link to the AI settings
	return {"message": frappe._(OUT_OF_CREDIT), "code": "out_of_credit"}


def _sse(event, data):
	return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _provider_error(resp, limit: int = 300) -> str:
	if _out_of_credit(resp):
		return frappe._(OUT_OF_CREDIT)
	return f"AI provider error ({resp.status_code}): {(resp.text or '')[:limit]}"


SYSTEM = """You are Kamra Agent, the assistant for {property_name}, a hotel
running Kamra PMS. Today is {today}. You help staff work faster: look
things up, quote, book, check guests in and out, post charges, take
payments, preview and process cancellations.

Rules:
- Numbers come from tools, never from you. Always call `quote` with the requested dates and exact adult/child occupancy before quoting or booking. Never quote prices using the base_price from `booking_options` or `availability`, which only reflect base occupancy without extra guests or taxes.
  Always quote the total payable price (`amount_after_tax` or `totals.total`).
  This property's {tax_mode}. When rates include taxes, present the quote directly as the final total price (e.g. "{currency_label}360, taxes included").
  Do not break down or unbundle pre-tax base rates and tax amounts unless specifically requested by the guest or staff.
- NEVER claim you did something unless a tool call returned success for it.
  If you have no tool for a request, say so plainly and stop - do not
  pretend, and do not substitute an unrelated tool. (There is no way to
  "inform housekeeping" except raise_ticket; occupant/room tools are not it.)
- Do each action ONCE. Never call the same posting/charge/payment tool twice
  for a single request - one dinner bill is one post_charge, not two.
- Posting a charge: do NOT set gst_rate yourself - the system applies the
  right tax (food & beverage is taxed at the F&B rate, not 18%). For an
  itemised bill (e.g. a dinner), ask what was ordered / the total before
  posting if it isn't already clear.
- To remove or fix a wrong charge: get_folio to see the charge lines, then
  void_charge with that line's `name` on an open folio (use apply_allowance
  once a folio is invoiced). Do not "offset with a zero charge" or move it.
- A room number (e.g. 101) is NOT a reservation id (which looks like
  RES-YYYY-NNNNN). Never make one up: use only ids a tool returned.
- When you look up or act on a stay, write its reservation id in your reply.
  Later messages only see your replies, not earlier tool results.
  To act on a guest, first find the reservation with find_reservations (by
  guest name, room number, or status), then use its `name` as the reservation
  id for check_out / get_folio / stay_detail / cancel.
- "Who checked out / arrived / is in-house / is confirmed?" → find_reservations
  with the matching status (Checked Out, Checked In, Confirmed, Cancelled,
  No Show). front_desk_today is only *today's* board.
- Never say you can't find something before calling find_reservations.
- Once a stay is quoted and staff say book it / create it / go ahead, call
  create_booking. Do not quote again unless the dates, room type, rate or
  guests changed.
- "Deposit required" in a quote is the property's refundable security
  deposit, collected at check-in. It never blocks a booking. When staff say
  to skip or waive it, create the booking, then call waive_security_deposit
  on it with their words as the reason (e.g. "Waived for now on staff
  request"). Say the booking number and that the deposit is waived.
- Never record a payment or a security deposit unless staff say the money
  was received (how much and how). Booking a stay collects nothing.
- Checking out or collecting a balance: call checkout_context first. Its
  total owed includes nights check-out still posts, so it can be more than
  the stay's balance so far. Record the payment for that amount on the folio
  it names, then call check_out once.
- Before cancelling, run the cancellation preview and state the fee.
- Confirm irreversible actions (cancel, checkout with balance, voiding a
  charge) in one short question before calling the tool.
- Be brief and concrete - front desk answers, not essays.
- The property's currency is {currency}. Its display label is {currency_label}.
  Use that label for monetary amounts in the property's currency. It comes
  from Frappe's Currency.symbol, falling back to the ISO currency code when
  no symbol is configured. Preserve any different currency explicitly
  supplied by a tool; include its ISO code when needed to distinguish it.
  Never infer currency from the conversation language or earlier messages.
  Do not convert amounts or replace a tool result's explicit currency.
  If currency is unspecified, ask rather than guess.
{extra}"""

# tool name → (kamra.api function, description, JSON-schema params,
# inject property?, mutating? - mutating calls are audit-logged)
EXTRA_TOOLS = {
	"amend_stay_preview": (
		"amend_stay_preview",
		"What new dates would do to a stay's bill (current vs new total, new "
		"nightly rates). Read-only - call before amend_stay.",
		{"reservation": {"type": "string"}, "check_in_date": {"type": "string"},
		 "check_out_date": {"type": "string"}}, False, False),
	"amend_stay": (
		"amend_stay",
		"Change a stay's dates (extend/shorten). Re-prices and re-checks "
		"overlaps. When the total changes it is refused unless confirm_price=1: "
		"run amend_stay_preview, tell the user the new price, and only pass "
		"confirm_price=1 once they agree.",
		{"reservation": {"type": "string"}, "check_in_date": {"type": "string"},
		 "check_out_date": {"type": "string"},
		 "confirm_price": {"type": "integer"}}, False, True),
	"move_room": (
		"move_reservation",
		"Move OR upgrade a stay to a different room - a same-type swap, or a "
		"different type (upgrade/downgrade, e.g. Standard -> Suite). The stay's "
		"room type follows the room it moves into. Call movable_rooms first to "
		"pick a room that is free for the dates. A different type re-prices: "
		"check room_move_preview and pass confirm_price=1 once the new price "
		"is agreed.",
		{"reservation": {"type": "string"}, "new_room": {"type": "string"},
		 "confirm_price": {"type": "integer"}},
		False, True),
	"room_move_preview": (
		"room_move_preview",
		"What moving a stay to a room would do to its bill. Read-only.",
		{"reservation": {"type": "string"}, "new_room": {"type": "string"}},
		False, False),
	"set_late_arrival": (
		"set_late_arrival",
		"Flag a confirmed arrival as arriving late (late_arrival=1, optional "
		"eta) so the night audit holds it instead of marking a no-show; 0 clears.",
		{"reservation": {"type": "string"}, "late_arrival": {"type": "integer"},
		 "eta": {"type": "string"}}, False, True),
	"movable_rooms": (
		"movable_rooms",
		"Rooms this stay could move into - across ALL room types - each flagged "
		"free or occupied for its dates, with the type name. Use this before "
		"move_room to choose a valid, available room (including upgrades).",
		{"reservation": {"type": "string"}, "check_in_date": {"type": "string"},
		 "check_out_date": {"type": "string"}}, False, False),
	"stay_folios": (
		"reservation_folios",
		"All folios of a stay (guest/extra/company/group) with balances.",
		{"reservation": {"type": "string"}}, False, False),
	"split_charge": (
		"split_folio_charge",
		"Split one charge line between two folios by percent OR amount (70/30 deals).",
		{"from_folio": {"type": "string"}, "charge_row": {"type": "string"},
		 "to_folio": {"type": "string"}, "percent": {"type": "number"},
		 "amount": {"type": "number"}}, False, True),
	"move_charges": (
		"transfer_folio_charges",
		"Move charge lines to another folio of the same stay or group.",
		{"from_folio": {"type": "string"},
		 "charge_rows": {"type": "array", "items": {"type": "string"}},
		 "to_folio": {"type": "string"}}, False, True),
	"group_billing": (
		"group_folios",
		"A group's billing picture: master folio + each member's folios.",
		{"group_booking": {"type": "string"}}, False, False),
	"update_occupants": (
		"update_occupants",
		"Record everyone staying in the room (legal register, prints on the GRC).",
		{"reservation": {"type": "string"},
		 "occupants": {"type": "array", "items": {"type": "object"}}},
		False, True),
	"void_charge": (
		"void_folio_charge",
		"Remove a WRONG charge line from an open folio (duplicate, wrong "
		"amount, wrong guest). Pass the folio and the charge line's id (the "
		"`name` field of the charge row from get_folio). For a settled/invoiced "
		"folio use apply_allowance instead.",
		{"folio": {"type": "string"}, "charge_row": {"type": "string"},
		 "reason": {"type": "string"}}, False, True),
	"apply_allowance": (
		"post_allowance",
		"Credit back part of a bill on an open folio without deleting the "
		"original line (service recovery, dispute, agreed discount). Needs a "
		"reason; it goes on the record.",
		{"folio": {"type": "string"}, "amount": {"type": "number"},
		 "reason": {"type": "string"}}, False, True),
	"raise_ticket": (
		"create_ticket",
		"Log a guest request or an operational issue as a ticket for the right "
		"team - e.g. a housekeeping issue (water spill, extra towels), "
		"maintenance, or a guest complaint. This is the ONLY way to notify "
		"housekeeping/maintenance; there is no other channel.",
		{"subject": {"type": "string"}, "category": {"type": "string"},
		 "priority": {"type": "string"}, "room": {"type": "string"},
		 "reservation": {"type": "string"}, "description": {"type": "string"}},
		True, True),
	"advance_ticket": (
		"advance_ticket",
		"Move a service ticket: In Progress, Resolved, Closed, or Cancelled. "
		"Pass resolution_note when resolving.",
		{"ticket": {"type": "string"}, "status": {"type": "string"},
		 "resolution_note": {"type": "string"}}, False, True),
	"hk_queue": (
		"hk_queue",
		"Housekeeping task queue and room board for this property.",
		{}, True, False),
	"hk_update_task": (
		"hk_update_task",
		"Start or complete a housekeeping task (In Progress, Done, Verified).",
		{"task": {"type": "string"}, "status": {"type": "string"}}, False, True),
	"set_room_hk_status": (
		"set_housekeeping_status",
		"Set a room's housekeeping status: Clean, Dirty, Inspected, Ready, Out of Order.",
		{"room": {"type": "string"}, "status": {"type": "string"}}, False, True),
	"security_deposit_status": (
		"security_deposit",
		"A stay's refundable security deposit: the policy amount, what is "
		"held, waived, withheld or refunded.",
		{"reservation": {"type": "string"}}, False, False),
	"collect_security_deposit": (
		"collect_security_deposit",
		"Record a refundable security deposit the guest has paid. mode: one "
		"of the property's payment modes. Confirm the amount with staff first.",
		{"reservation": {"type": "string"}, "amount": {"type": "number"},
		 "mode": {"type": "string"}, "reference": {"type": "string"}},
		False, True),
	"waive_security_deposit": (
		"waive_security_deposit",
		"Waive the security deposit for one stay (after it is booked). A "
		"reason is required: use the staff member's words. Refused once "
		"money was taken.",
		{"reservation": {"type": "string"}, "reason": {"type": "string"}},
		False, True),
	"close_folio": (
		"close_folio",
		"Close / settle an open folio and issue the invoice. Balance must be zero. Confirm first.",
		{"folio": {"type": "string"}}, False, True),
	"set_room_rate": (
		"set_room_rate",
		"Set a nightly rate for a room type over dates. Owner guardrails apply - give a reason.",
		{"room_type": ROOM_TYPE_PARAM, "start_date": {"type": "string"},
		 "end_date": {"type": "string"}, "rate": {"type": "number"},
		 "reason": {"type": "string"}}, True, True),
	"owner_briefing": (
		"owner_briefing",
		"The manager's numbers: occupancy, revenue/ADR/RevPAR, arrivals, tickets.",
		{"date": {"type": "string"}}, True, False),
	"position_briefing": (
		"position_briefing",
		"The hotel-position briefing for the GM/front desk: today's occupancy "
		"vs the overbooking ceiling, arrivals with ETAs, departures with ETDs "
		"and balances due, back-to-back room conflicts, the demand tier "
		"pricing is applying, and a 7-day outlook.",
		{"date": {"type": "string"}}, True, False),
	"night_audit_precheck": (
		"night_audit.night_audit_precheck",
		"The night audit checklist for the current business date (read-only): "
		"open tills, open restaurant bills, departures still in house, arrivals "
		"and what the no-show policy will do, rate variances, outlet bills on "
		"rooms, high balances, companies over credit limit, room status "
		"discrepancies. Each check has a severity (block | warn | info), a "
		"count, the rows and a suggested action. Run it before run_night_audit.",
		{}, True, False),
	"run_night_audit": (
		"run_night_audit",
		"Run end-of-day for the current business date: posts room nights, "
		"flags & charges no-shows, rolls the business date. Refused while a "
		"blocking pre-check has items: resolve them, or - only when staff "
		"confirm - pass acknowledge (the check keys) with note (the reason). "
		"business_date is optional and must equal the current business date.",
		{"business_date": {"type": "string"},
		 "acknowledge": {"type": "array", "items": {"type": "string"}},
		 "note": {"type": "string"}}, True, True),
	# Fixed reports. Each keeps its endpoint's role gate (_tool_allowed), so
	# the agent offers a user exactly the reports their roles can open.
	"manager_flash": (
		"reports.manager_flash",
		"The daily flash: yesterday's occupancy, ADR, RevPAR and revenue, month "
		"to date, today's movement, collections by mode and the 7-day outlook. "
		"Pass from_date for a range ending on date.",
		{"date": {"type": "string"}, "from_date": {"type": "string"}}, True, False),
	"cashier_shift_report": (
		"cashier.shift_report",
		"What each cashier took on a business date (or business_date to "
		"to_date), by payment mode.",
		{"business_date": {"type": "string"}, "to_date": {"type": "string"}},
		True, False),
	"voids_allowances_report": (
		"reports.void_allowance_report",
		"Every void and allowance in a date range, with who did it and why.",
		{"from_date": {"type": "string"}, "to_date": {"type": "string"}},
		True, False),
	"sla_report": (
		"reports.sla_report",
		"Guest request (ticket) SLA over a date range: resolution and breach "
		"rates by category and priority, and the overdue queue.",
		{"from_date": {"type": "string"}, "to_date": {"type": "string"}},
		True, False),
	"outlets": (
		"pos.outlets",
		"The property's restaurants, bars and other outlets. Call before "
		"outlet_dashboard or wastage_report to get an outlet id.",
		{}, True, False),
	"outlet_dashboard": (
		"pos.outlet_dashboard",
		"One outlet's day: sales, bills, covers, average bill, by order type "
		"and tender, open bills, NC / voids / cancellations, kitchen times. "
		"Pass to_date for a range starting on date.",
		{"outlet": {"type": "string"}, "date": {"type": "string"},
		 "to_date": {"type": "string"}},
		False, False),
	"wastage_report": (
		"inventory.wastage_report",
		"Food cooked and then voided over the last N days (default 30), with "
		"its cost; optionally for one outlet.",
		{"outlet": {"type": "string"}, "days": {"type": "integer"}},
		True, False),
	"list_report_datasets": (
		"custom_reports.list_report_datasets",
		"Whitelisted custom-report datasets and columns. Call before building "
		"or running a custom report.",
		{}, True, False),
	"list_report_packs": (
		"custom_reports.list_report_packs",
		"Department report packs (Front Office, Housekeeping, F&B, Hotel "
		"Manager) with the sections this user may see.",
		{}, True, False),
	"run_report_pack": (
		"custom_reports.run_report_pack",
		"Run a department pack (id from list_report_packs) for a date range; "
		"defaults to the last 7 days. format=json.",
		{"pack": {"type": "string"}, "from_date": {"type": "string"},
		 "to_date": {"type": "string"}, "format": {"type": "string"}},
		True, False),
	"list_custom_reports": (
		"custom_reports.list_custom_reports",
		"Saved custom reports for this property.",
		{}, True, False),
	"save_custom_report": (
		"custom_reports.save_custom_report",
		"Create or update a saved custom report (dataset + columns/filters). "
		"Only catalog field ids - never invent SQL. Pass name to update.",
		{"title": {"type": "string"}, "dataset": {"type": "string"},
		 "columns": {"type": "string"}, "filters": {"type": "string"},
		 "is_shared": {"type": "integer"},
		 "schedule_frequency": {"type": "string"},
		 "schedule_time": {"type": "string"},
		 "recipients": {"type": "string"}, "name": {"type": "string"}},
		True, True),
	"run_custom_report": (
		"custom_reports.run_custom_report",
		"Run a saved (name) or ad-hoc (dataset) custom report. Prefer "
		"format=json. from_date / to_date YYYY-MM-DD.",
		{"name": {"type": "string"}, "dataset": {"type": "string"},
		 "from_date": {"type": "string"}, "to_date": {"type": "string"},
		 "columns": {"type": "string"}, "filters": {"type": "string"},
		 "format": {"type": "string"}, "lang": {"type": "string"}},
		True, False),
	"email_custom_report": (
		"custom_reports.email_custom_report",
		"Email a custom report CSV to recipients (comma-separated).",
		{"recipients": {"type": "string"}, "name": {"type": "string"},
		 "dataset": {"type": "string"}, "from_date": {"type": "string"},
		 "to_date": {"type": "string"}}, True, True),
}

TOOLS = {
	**EXTRA_TOOLS,
	"front_desk_today": (
		"front_desk_snapshot",
		"Today's arrivals, departures, in-house guests (with paid/due) and room board.",
		{}, True, False),
	"availability": (
		"availability_calendar",
		"Rooms available and nightly rate per room type per date.",
		{"start_date": {"type": "string"}, "days": {"type": "integer"}}, True, False),
	"quote": (
		"get_quote",
		"Price a stay (room type, dates, occupancy, optional meal plan / rate "
		"plan / voucher). Room type, meal plan and rate plan take the id, code "
		"or exact name; an unknown or ambiguous one is refused with the valid "
		"options - pick from those, never guess.",
		{"room_type": ROOM_TYPE_PARAM, "check_in_date": {"type": "string"},
		 "check_out_date": {"type": "string"}, "adults": {"type": "integer"},
		 "children": {"type": "integer"}, "meal_plan": MEAL_PLAN_PARAM,
		 "rate_plan": RATE_PLAN_PARAM,
		 "voucher_code": {"type": "string"}}, True, False),
	"booking_options": (
		"booking_options",
		"Room types catalog, meal plans, companies, travel agents, experiences, sell message and policies. Do not use its base_price to quote stays; call `quote` for actual pricing with occupancy and taxes.",
		{}, True, False),
	"create_booking": (
		"create_booking",
		"Book a stay. Quote first; confirm the total with staff before calling. "
		"Room type / meal plan / rate plan take the id, code or exact name. "
		"Call it once per room: a repeat returns the existing booking "
		"(idempotent_replay) instead of booking twice. For several identical "
		"rooms, call it once per room in the same reply.",
		{"room_type": ROOM_TYPE_PARAM, "check_in_date": {"type": "string"},
		 "check_out_date": {"type": "string"}, "guest_name": {"type": "string"},
		 "phone": {"type": "string"}, "adults": {"type": "integer"},
		 "children": {"type": "integer"}, "meal_plan": MEAL_PLAN_PARAM,
		 "rate_plan": RATE_PLAN_PARAM,
		 "company": {"type": "string"},
		 "booked_by_name": {"type": "string"},
		 "booked_by_phone": {"type": "string"}}, True, True),
	"find_reservations": (
		"find_reservations",
		"Find reservations by guest name, room number, or reference - optionally "
		"filtered by status (Confirmed, Checked In, Checked Out, Cancelled, No "
		"Show). Use this to resolve a room number or a name to a reservation "
		"before acting, or to list stays by status (e.g. who checked out).",
		{"query": {"type": "string"}, "status": {"type": "string"},
		 "limit": {"type": "integer"}}, True, False),
	"stay_detail": (
		"reservation_detail",
		"Full detail for one reservation: dates, room, guest + stay history, "
		"folio balance so far (paid/due), booker, and which actions are "
		"available. Not the check-out amount: use checkout_context for that.",
		{"reservation": {"type": "string"}}, False, False),
	"waitlist_ready": (
		"waitlist_ready",
		"Waitlisted stays that can now be booked - a room freed for their "
		"dates - with the guest's phone, so you can proactively reach out.",
		{}, True, False),
	"promote_waitlist": (
		"promote_waitlist",
		"Promote a waitlisted reservation into a free room (Confirmed).",
		{"reservation": {"type": "string"}}, False, True),
	"create_group_block": (
		"create_group_block",
		"Draft a MICE piece of business in one go: a group booking with a "
		"room block (list of {room_type, rooms_blocked, block_rate}) and "
		"optionally its banquet event (venue, event_type, event_date, "
		"attendees). Starts as Open (a proposal) - confirm it to hold rooms.",
		{"group_name": {"type": "string"},
		 "check_in_date": {"type": "string"},
		 "check_out_date": {"type": "string"},
		 "blocks": {"type": "array", "items": {"type": "object"}},
		 "company": {"type": "string"},
		 "cutoff_date": {"type": "string"},
		 "venue": {"type": "string"},
		 "event_type": {"type": "string"},
		 "event_date": {"type": "string"},
		 "attendees": {"type": "integer"}}, True, True),
	"group_pickup_status": (
		"group_detail",
		"Group Rooms Control for a group booking: the block, per-room-type "
		"pickup (blocked/picked/remaining), rooming list, event, the main "
		"room and the group bill balance.",
		{"group_booking": {"type": "string"}}, False, False),
	"create_group_booking": (
		"create_group_booking",
		"Book a group (corporate, wedding) in one go: rooms = [{room_type, "
		"count, room?, guest_name?}]. master_index picks the main room whose "
		"guest pays master_pays (default \"Room only\" = room + tax) for every "
		"room on one group bill.",
		{"group_name": {"type": "string"},
		 "check_in_date": {"type": "string"},
		 "check_out_date": {"type": "string"},
		 "rooms": {"type": "array", "items": {"type": "object"}},
		 "guest_name": {"type": "string"}, "phone": {"type": "string"},
		 "company": {"type": "string"}, "group_type": {"type": "string"},
		 "master_index": {"type": "integer"},
		 "master_pays": {"type": "string"}}, True, True),
	"settle_group_bill": (
		"settle_group_bill",
		"Settle a group's bill: a payment by mode (amount defaults to the "
		"balance) or to_city_ledger=1 for a company with credit. Closes it at 0.",
		{"group_booking": {"type": "string"}, "mode": {"type": "string"},
		 "amount": {"type": "number"}, "to_city_ledger": {"type": "integer"},
		 "reference": {"type": "string"}}, False, True),
	"pickup_group_room": (
		"pickup_group_room",
		"Name a guest into a group's room block (creates their reservation "
		"on the group dates).",
		{"group_booking": {"type": "string"},
		 "room_type": ROOM_TYPE_PARAM,
		 "guest_name": {"type": "string"},
		 "phone": {"type": "string"}, "adults": {"type": "integer"},
		 "children": {"type": "integer"},
		 "idempotency_key": {
			 "type": "string",
			 "description": "Optional unique key for this pickup; a retry with "
			 "the same key returns the first reservation."}}, False, True),
	"guest_search": (
		"guest_search",
		"Find a guest profile by name or phone (returning guests, VIPs).",
		{"q": {"type": "string"}}, False, False),
	"check_in": (
		"check_in",
		"Check a reservation in (optionally into a specific room).",
		{"reservation": {"type": "string"}, "room": {"type": "string"}}, False, True),
	"checkout_context": (
		"checkout_context",
		"Read-only: what check-out will ask for. Balances per folio after the "
		"nights check-out still posts, the total the guest owes, a held "
		"security deposit, open restaurant bills and every blocker. Call it "
		"before collecting a balance or checking out.",
		{"reservation": {"type": "string"}}, False, False),
	"check_out": (
		"check_out",
		"Check a reservation out. Call checkout_context first and settle what "
		"it says is owed.",
		{"reservation": {"type": "string"}}, False, True),
	"get_folio": (
		"get_folio",
		"The stay's bill: charges, payments, GST, balance.",
		{"reservation": {"type": "string"}}, False, False),
	"post_charge": (
		"post_stay_charge",
		"Post a charge to a stay; billing rules pick the folio. Alcohol never bills to a company.",
		{"reservation": {"type": "string"}, "charge_type": {"type": "string"},
		 "description": {"type": "string"}, "amount": {"type": "number"},
		 "gst_rate": {"type": "number"}, "is_alcohol": {"type": "integer"}},
		False, True),
	"record_payment": (
		"add_folio_payment",
		"Record a payment staff say was received, against a folio (mode: "
		"Cash, Card, Bank Transfer, Payment Link or the country's own modes "
		"from the property locale). folio is "
		"the folio id from checkout_context folios[].folio or get_folio. If you "
		"only have the booking, pass reservation instead and leave folio out: "
		"the stay's open guest folio is used.",
		{"folio": {"type": "string"}, "reservation": {"type": "string"},
		 "mode": {"type": "string"},
		 "amount": {"type": "number"}, "reference": {"type": "string"}}, False, True),
	"cancellation_preview": (
		"cancellation_preview",
		"What cancelling would cost right now. Always run before cancelling.",
		{"reservation": {"type": "string"}}, False, False),
	"cancel_booking": (
		"cancel_reservation",
		"Cancel a confirmed booking (policy applies; returns a cancellation number to read out). "
		"Only after cancellation_preview AND staff answered yes to the fee in a later "
		"message. Never in the same turn as the preview.",
		{"reservation": {"type": "string"}, "reason": {"type": "string"},
		 "note": {"type": "string"}}, False, True),

	# ── banquets ────────────────────────────────────────────────────────
	# The whole reason a banquet enquiry is worth answering in seconds: by
	# the time the caller has finished describing the wedding, the hall is
	# checked, the sheet exists and the menu is priced.
	"banquet_availability": (
		"banquet.venue_availability",
		"Which halls are free for a date (and hours, and pax). A confirmed "
		"function takes the hall; a tentative hold shows as a soft hold you "
		"can still sell over. Always run this before opening an enquiry.",
		{"event_date": {"type": "string"}, "end_date": {"type": "string"},
		 "start_time": {"type": "string"}, "end_time": {"type": "string"},
		 "pax": {"type": "integer"}}, True, False),
	"banquet_catalogue": (
		"banquet.banquet_catalogue",
		"What the property sells at a function: menu packages (per plate, "
		"with their courses) and services (LED wall, projector, DJ, podium, "
		"stage, decor, bar). Read this before quoting anything.",
		{}, True, False),
	"banquet_enquiry": (
		"banquet.create_enquiry",
		"Open a function sheet from an enquiry. The hall's rack rental goes "
		"on as the first line and a follow-up is diarised. Check "
		"banquet_availability first.",
		{"venue": {"type": "string"}, "event_date": {"type": "string"},
		 "customer_name": {"type": "string"}, "event_type": {"type": "string"},
		 "attendees": {"type": "integer"}, "customer_phone": {"type": "string"},
		 "customer_email": {"type": "string"}, "company": {"type": "string"},
		 "end_date": {"type": "string"}, "start_time": {"type": "string"},
		 "end_time": {"type": "string"}, "source": {"type": "string"},
		 "requirements": {"type": "string"}}, True, True),
	"banquet_sheet": (
		"banquet.function_sheet",
		"One function in full: dates, pax, every line item, the negotiation "
		"history, payment terms, what's been received and what it still "
		"needs from somebody.",
		{"function": {"type": "string"}}, False, False),
	"banquet_add_menu": (
		"banquet.add_menu",
		"Put a menu package on a function. The quantity follows the "
		"guaranteed pax on its own. Pass chargeable=0 to give it away - it "
		"still prints on the event order, it just leaves the quote.",
		{"function": {"type": "string"}, "menu": {"type": "string"},
		 "qty": {"type": "number"}, "rate": {"type": "number"},
		 "chargeable": {"type": "integer"}}, False, True),
	"banquet_add_service": (
		"banquet.add_service",
		"Put a service on a function - projector, LED wall, DJ, podium, "
		"stage, decor, laptop, bar. chargeable=0 makes it complimentary.",
		{"function": {"type": "string"}, "service_item": {"type": "string"},
		 "qty": {"type": "number"}, "rate": {"type": "number"},
		 "chargeable": {"type": "integer"}}, False, True),
	"banquet_negotiate": (
		"banquet.negotiate",
		"Move the price: a headline discount, or the hall rate. Every move "
		"is snapshotted, so 'what did we send on the 3rd' stays answerable. "
		"Confirm the new total with staff before calling.",
		{"function": {"type": "string"}, "discount_amount": {"type": "number"},
		 "venue_rental": {"type": "number"}, "note": {"type": "string"}},
		False, True),
	"banquet_status": (
		"banquet.set_status",
		"Move a function along: Enquiry → Tentative → Confirmed → Completed, "
		"or out as Cancelled / Lost (a reason is required). Confirming takes "
		"the hall and will refuse a clash.",
		{"function": {"type": "string"}, "status": {"type": "string"},
		 "reason": {"type": "string"}}, False, True),
	"banquet_quote": (
		"banquet.generate_quote",
		"Stamp a quotation - bumps the version, dates it, and returns the "
		"whole document to read back to the customer.",
		{"function": {"type": "string"}, "valid_days": {"type": "integer"}},
		False, True),
	"banquet_pipeline": (
		"banquet.banquet_pipeline",
		"The banquet sales picture by month and by status: what's confirmed, "
		"what's still in play, what's outstanding, conversion, and why "
		"business went away.",
		{"from_date": {"type": "string"}, "to_date": {"type": "string"},
		 "months": {"type": "integer"}}, True, False),
	"banquet_month": (
		"banquet.month_availability",
		"Every hall and every session across a whole month - the grid that "
		"answers 'do you have the 14th of December?' in one look. Sessions "
		"are Morning / Afternoon / Evening, which is how halls are sold.",
		{"month": {"type": "string"}}, True, False),
	"banquet_close_out": (
		"banquet.close_out",
		"Hand the hall back after the function: record the covers actually "
		"served, deduct any damage from the refundable deposit (a reason is "
		"required) and return the rest. Closes the function.",
		{"function": {"type": "string"}, "damage_amount": {"type": "number"},
		 "damage_note": {"type": "string"}, "pax_actual": {"type": "integer"},
		 "refund_deposit": {"type": "integer"}}, False, True),
	"banquet_register": (
		"banquet.banquet_register",
		"The banquet office's books for a period: functions, quotations, "
		"enquiries, receipts (the cash book) or sales - a rollup by hall, "
		"event type and session.",
		{"register": {"type": "string"}, "from_date": {"type": "string"},
		 "to_date": {"type": "string"}}, True, False),
	"banquet_menu_card": (
		"banquet.menu_card",
		"What will actually be served, course by course, with no prices on "
		"it - the sheet the customer signs off and the kitchen cooks from.",
		{"function": {"type": "string"}}, False, False),
	"banquet_reminders": (
		"banquet.banquet_reminders",
		"Everything across the property that needs chasing today: follow-ups "
		"gone quiet, tentative holds about to lapse, payments due, event "
		"orders missing before the date.",
		{"days": {"type": "integer"}}, True, False),
}


def _settings(property: str):
	name = frappe.db.get_value(
		"AI Assistant Settings", {"property": property})
	return frappe.get_doc("AI Assistant Settings", name) if name else None


def _system_prompt(property: str, settings) -> str:
	"""Use the property's currency and Frappe symbol in both chat paths."""
	prop = frappe.get_cached_doc("Property", property)
	currency = prop.get("currency")
	if not currency:
		from kamra.localization import pack_for

		currency = pack_for(property).locale(prop).get("currency")
	symbol = (frappe.db.get_value("Currency", currency, "symbol") or "").strip() if currency else ""
	inclusive = bool(prop.get("rates_include_tax"))
	tax_mode = "rates include taxes" if inclusive else "rates exclude taxes"
	return SYSTEM.format(
		property_name=prop.property_name or property, today=nowdate(),
		currency=currency or "unspecified",
		currency_label=symbol or currency or "unspecified",
		tax_mode=tax_mode,
		extra=("\n" + settings.extra_instructions) if settings.extra_instructions else "")


@frappe.whitelist()
def assistant_status(property: str):
	from kamra.authz import assert_property_access
	assert_property_access(property)
	s = _settings(property)
	key = s.get_password("api_key", raise_exception=False) if s else None
	# Never return the key - only a masked tail so admins can confirm one is set.
	key_hint = ("••••" + key[-4:]) if key and len(key) >= 4 else None
	base = (s.base_url if s else None) or "https://api.openai.com/v1"
	return {
		"enabled": bool(s and s.enabled and key),
		"model": (s.model if s else None) or "gpt-4o-mini",
		"base_url": base,
		"key_hint": key_hint,
		"processor_disclosure": processor_disclosure(base),
		"redact_guest_contact_details": bool(
			cint(s.redact_guest_contact_details) if s else 1),
	}


# Presets for Settings → AI assistant. All speak OpenAI Chat Completions.
# Claude Desktop is a different path (MCP) — not an Anthropic key here.
AI_PROVIDER_PRESETS = (
	{
		"id": "openai",
		"label": "OpenAI",
		"base_url": "https://api.openai.com/v1",
		"model": "gpt-4o-mini",
		"hint": "Paste an sk-… key from platform.openai.com",
	},
	{
		"id": "gemini",
		"label": "Google Gemini",
		"base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
		"model": "gemini-2.0-flash",
		"hint": "Paste a Google AI Studio key — uses Gemini's OpenAI-compatible URL",
	},
	{
		"id": "groq",
		"label": "Groq",
		"base_url": "https://api.groq.com/openai/v1",
		"model": "llama-3.3-70b-versatile",
		"hint": "Fast open models — key from console.groq.com",
	},
	{
		"id": "openrouter",
		"label": "OpenRouter",
		"base_url": "https://openrouter.ai/api/v1",
		"model": "openai/gpt-4o-mini",
		"hint": "One key for many models (including Claude-as-model). Not Claude Desktop MCP.",
	},
	{
		"id": "ollama",
		"label": "Ollama (local)",
		"base_url": "http://host.docker.internal:11434/v1",
		"model": "llama3.2",
		"hint": "Local models. From Docker use host.docker.internal; on bare metal use http://127.0.0.1:11434/v1",
	},
	{
		"id": "azure",
		"label": "Azure OpenAI",
		"base_url": "",
		"model": "gpt-4o-mini",
		"hint": "Paste your Azure resource Chat Completions URL ending in /v1 (or /openai/v1)",
	},
	{
		"id": "custom",
		"label": "Custom (OpenAI-compatible)",
		"base_url": "",
		"model": "gpt-4o-mini",
		"hint": "Any host that implements POST /v1/chat/completions",
	},
)


@frappe.whitelist()
@require_roles("Hotel Admin", "System Manager", "Front Desk")
def provider_presets():
	"""Dropdown options for Settings — kill 'paste Claude key into OpenAI' tickets."""
	out = []
	for row in AI_PROVIDER_PRESETS:
		p = dict(row)
		p["processor_note"] = processor_disclosure(p.get("base_url"))
		out.append(p)
	return {"presets": out}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin", "System Manager")
def test_connection(property: str, base_url: str | None = None,
                    model: str | None = None, api_key: str | None = None):
	"""One cheap Chat Completions call with no tools. Returns the provider
	error text when it fails so Setup is diagnosable."""
	import time

	s = _settings(property)
	key = (api_key or "").strip() or (
		s.get_password("api_key", raise_exception=False) if s else None)
	if not key:
		frappe.throw("No API key — paste one, or save Settings first.")
	if key.lower().startswith("sk-ant-"):
		frappe.throw(
			"That looks like an Anthropic / Claude API key. This chat uses "
			"OpenAI-compatible Chat Completions only. Use Connect Claude "
			"(MCP) on Kamra Agent, or put Claude behind OpenRouter.")

	base = (base_url or (s.base_url if s else None)
	        or "https://api.openai.com/v1").rstrip("/")
	mdl = model or (s.model if s else None) or "gpt-4o-mini"
	headers = {"Authorization": f"Bearer {key}",
	           "Content-Type": "application/json"}
	body = chat_payload(
		mdl,
		[{"role": "user", "content": "Reply with exactly: ok"}],
		temperature=0,
	)
	# No tools — simplest possible probe.
	t0 = time.monotonic()
	try:
		resp = requests.post(f"{base}/chat/completions", headers=headers,
		                     json=body, timeout=30)
	except requests.RequestException as e:
		return {"ok": False, "error": f"Could not reach {base}: {e}",
		        "base_url": base, "model": mdl}
	ms = int((time.monotonic() - t0) * 1000)
	if resp.status_code != 200:
		return {
			"ok": False,
			"status": resp.status_code,
			"error": (frappe._(OUT_OF_CREDIT) if _out_of_credit(resp)
			          else (resp.text or "")[:400]),
			"base_url": base,
			"model": mdl,
			"latency_ms": ms,
		}
	try:
		text = (resp.json()["choices"][0]["message"].get("content") or "")
	except (KeyError, IndexError, ValueError, TypeError):
		text = (resp.text or "")[:200]
	return {
		"ok": True,
		"reply": text[:200],
		"base_url": base,
		"model": mdl,
		"latency_ms": ms,
	}


def _resolve(fn_name: str):
	"""A tool's target. Bare names live in kamra.api (where most of the
	front-desk surface is); a dotted name reaches a sibling module, so a
	whole domain like banquets can be wired in without re-exporting every
	endpoint through api.py."""
	import importlib

	if "." in fn_name:
		module, attr = fn_name.rsplit(".", 1)
		return getattr(importlib.import_module(f"kamra.{module}"), attr, None)
	from kamra import api
	return getattr(api, fn_name, None)


def _tool_allowed(name: str) -> bool:
	"""RBAC for Kamra Agent: a tool is only visible/callable when the
	signed-in user's roles pass the SAME gate as the underlying API
	endpoint. The model never even sees tools this user couldn't use."""
	fn = _resolve(TOOLS[name][0])
	allowed = getattr(fn, "_kamra_roles", None)
	if not allowed:
		return True
	return bool(set(frappe.get_roles()) & set(allowed))


def _tool_defs():
	return [{
		"type": "function",
		"function": {
			"name": name,
			"description": desc,
			"parameters": {
				"type": "object",
				"properties": params,
				"required": [],
			},
		},
	} for name, (_, desc, params, _inject, _mut) in TOOLS.items()
	  if _tool_allowed(name)]


def _post_chat(base: str, headers: dict, body: dict, *, stream: bool = False):
	"""POST /chat/completions, retrying once if the model rejects the payload.

	GPT-5.6 luna/terra/sol refuse function tools on Chat Completions unless
	``reasoning_effort`` is ``none`` (#23). Compatible hosts that already
	accept the first body are unchanged.
	"""
	url = f"{base}/chat/completions"
	resp = requests.post(url, headers=headers, json=body,
	                     timeout=TIMEOUT, stream=stream)
	if resp.status_code != 400:
		return resp
	retry = retry_chat_payload(body, resp.text or "")
	if not retry:
		return resp
	return requests.post(url, headers=headers, json=retry,
	                     timeout=TIMEOUT, stream=stream)


# a ticket the copilot raises is an agent's ticket - the same source the MCP
# create_ticket tool stamps, so reports tell it apart from staff-typed ones
_FIXED_ARGS = {"raise_ticket": {"source": "AI Agent"}}


def _payment_folio(args: dict) -> dict:
	"""record_payment takes a folio id, but models often have only the
	booking (or pass it as the folio): use that stay's open guest folio."""
	args = dict(args)
	res = args.pop("reservation", None)
	folio = args.get("folio")
	if folio and frappe.db.exists("Folio", folio):
		return args
	if not res and folio and frappe.db.exists("Reservation", folio):
		res = folio
	if res:
		found = frappe.db.get_value(
			"Folio", {"reservation": res, "folio_type": "Guest", "status": "Open"},
			"name", order_by="creation desc")
		if found:
			args["folio"] = found
	return args


# the documents a chat tool may name, and the field that ties each to a property
_SCOPED_ARGS = {"reservation": "Reservation", "folio": "Folio",
                "outlet": "POS Outlet"}


def _assert_this_property(args: dict, property: str) -> None:
	"""Kamra Agent works for the property it was opened on. A reservation or
	folio from another property (a guessed or remembered id) is refused even
	when the user may see that property elsewhere."""
	for key, doctype in _SCOPED_ARGS.items():
		value = args.get(key)
		if not value or not frappe.db.exists(doctype, value):
			continue
		owner = frappe.db.get_value(doctype, value, "property")
		if owner and owner != property:
			frappe.throw(f"{value} belongs to another property, not this one. "
			             "Look the stay up again with find_reservations.")


def _recent_same_stays(args: dict, property: str) -> int:
	"""Live stays for this guest name and dates made in the duplicate window."""
	from frappe.utils import add_to_date, now_datetime

	from kamra.reservation_state import AGENT_DUPLICATE_WINDOW_MINUTES, LIVE_STATUSES
	if not (args.get("guest_name") and args.get("check_in_date")
	        and args.get("check_out_date")):
		return 0
	return frappe.db.count("Reservation", {
		"property": property, "guest_name": args["guest_name"].strip(),
		"check_in_date": args["check_in_date"],
		"check_out_date": args["check_out_date"],
		"status": ("in", list(LIVE_STATUSES)),
		"creation": (">=", add_to_date(
			now_datetime(), minutes=-AGENT_DUPLICATE_WINDOW_MINUTES)),
	})


def _note_refs(args: dict, result) -> None:
	"""Remember the stays this turn touched; see _missing_refs."""
	refs = getattr(frappe.local, "kamra_chat_refs", None)
	if refs is None:
		return
	found = [args.get("reservation")]
	if isinstance(result, dict):
		found += [result.get("reservation"), result.get("name")]
	for ref in found:
		if isinstance(ref, str) and ref.startswith("RES-") and ref not in refs:
			refs.append(ref)


def _note_quote(args: dict, result) -> None:
	"""Keep the turn's last quote, so the chat can show it as a card."""
	if not isinstance(result, dict) or "amount_after_tax" not in result:
		return
	frappe.local.kamra_chat_quote = {
		"type": "quote",
		"room_type": args.get("room_type"),
		"check_in_date": args.get("check_in_date"),
		"check_out_date": args.get("check_out_date"),
		"adults": args.get("adults"),
		"children": args.get("children"),
		"nights": result.get("nights"),
		"total": result.get("amount_after_tax"),
		"deposit": (result.get("totals") or {}).get("deposit_required") or 0,
		"currency": result.get("currency"),
	}


def _turn_cards() -> list[dict]:
	"""What the chat draws under a reply: the stays the turn touched (the
	screen loads each through reservation_detail, with the user's own
	permissions) and the last quote, unless the turn went on to book it."""
	refs = list(getattr(frappe.local, "kamra_chat_refs", None) or [])
	cards: list[dict] = []
	quote = getattr(frappe.local, "kamra_chat_quote", None)
	if quote and not refs:
		cards.append(quote)
	cards += [{"type": "stay", "reservation": r} for r in refs[:3]]
	return cards


def _missing_refs(text: str) -> str:
	"""Later turns only see the replies, not tool results: a reply about a
	stay that never names its reservation id leaves the next turn guessing
	one. Returns a "Ref:" line for the ids the reply left out."""
	refs = getattr(frappe.local, "kamra_chat_refs", None) or []
	missing = [r for r in refs if r not in (text or "")][:3]
	return f"\n\nRef: {', '.join(missing)}" if missing else ""


def _run_tool(name: str, args: dict, property: str):
	if not _tool_allowed(name):
		frappe.throw("Your role doesn't include this action.",
		             frappe.PermissionError)
	fn_name, _desc, params, inject, mutating = TOOLS[name]
	fn = _resolve(fn_name)
	clean = {k: v for k, v in args.items()
	         if k in params and v not in (None, "")}
	if inject:
		clean["property"] = property
	_assert_this_property(clean, property)
	if name == "record_payment":
		clean = _payment_folio(clean)
	if name == "create_booking":
		# A model-made key reads as "a second identical room on purpose" and
		# switches the duplicate guard off, so the chat never passes one. The
		# same booking twice in ONE turn is deliberate ("book two rooms"); in a
		# later turn it is a retry, and the duplicate guard returns the first.
		# Asked for N identical rooms, it books only while fewer than N
		# matching stays were made recently (earlier turns count too).
		import uuid
		sig = frappe.as_json(sorted(clean.items()))
		seen = getattr(frappe.local, "kamra_chat_bookings", None)
		if seen is not None:
			seen[sig] = seen.get(sig, 0) + 1
			if seen[sig] > 1 and _recent_same_stays(clean, property) < seen[sig]:
				clean["idempotency_key"] = f"chat-{uuid.uuid4().hex}"
	# arguments the tool always carries, whatever the model sent
	clean.update(_FIXED_ARGS.get(name, {}))
	# Kamra Agent tool calls are agent actions: accountability comes from
	# action log, not the cashier PIN (which guards humans at a terminal)
	# the channel doubles as the "agent call" flag the cashier PIN and the
	# booking duplicate guard read; create_booking stamps source AI Agent
	prev, frappe.flags.kamra_agent_call = frappe.flags.kamra_agent_call, "Chat"
	try:
		result = fn(**clean)
	finally:
		frappe.flags.kamra_agent_call = prev
	if mutating and not is_replay(result):
		# a guaranteed audit line for every state-changing chat action,
		# on top of whatever the API itself logs
		from kamra.savings import log_action
		log_action("copilot_" + name, "Property", property, property,
		           rationale=frappe.as_json(clean)[:400],
		           agent_name="Front Desk Copilot", channel="Chat")
	_note_refs(clean, result)
	if name == "quote":
		_note_quote(clean, result)
	return json.loads(frappe.as_json(result))


def _tool_json_for_provider(result, settings):
	"""Mask guest phone / ID in tool payloads before they leave for the LLM."""
	if isinstance(result, dict) and set(result.keys()) == {"error"}:
		return frappe.as_json(result)
	strict = bool(cint(getattr(settings, "redact_guest_contact_details", 1)))
	return frappe.as_json(scrub_for_llm(result, strict=strict))


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Revenue Manager")
def ask(property: str, messages):
	"""One Kamra Agent turn: history in, answer out. The model may call
	governed tools along the way; every call is returned so the UI can
	show what actually happened."""
	s = _settings(property)
	if not (s and s.enabled):
		frappe.throw("The AI assistant is not enabled for this property - "
		             "an admin can switch it on under Settings.")
	api_key = s.get_password("api_key", raise_exception=False)
	if not api_key:
		frappe.throw("No API key configured. Add your provider's key under "
		             "Settings → AI assistant.")
	if isinstance(messages, str):
		messages = frappe.parse_json(messages)

	system = _system_prompt(property, s)
	convo = [{"role": "system", "content": system}] + list(messages)

	base = (s.base_url or "https://api.openai.com/v1").rstrip("/")
	model = s.model or "gpt-4o-mini"
	headers = {"Authorization": f"Bearer {api_key}",
	           "Content-Type": "application/json"}
	actions = []
	frappe.local.kamra_chat_bookings = {}
	frappe.local.kamra_chat_refs = []
	frappe.local.kamra_chat_quote = None
	for _ in range(MAX_TOOL_ROUNDS):
		resp = _post_chat(base, headers, chat_payload(
			model, convo, tools=_tool_defs(), temperature=0.2))
		if resp.status_code != 200:
			frappe.throw(_provider_error(resp))
		msg = resp.json()["choices"][0]["message"]
		convo.append(msg)

		calls = msg.get("tool_calls") or []
		if not calls:
			reply = msg.get("content") or ""
			return {"reply": reply + _missing_refs(reply), "actions": actions,
			        "cards": _turn_cards()}

		for call in calls:
			name = call["function"]["name"]
			try:
				args = json.loads(call["function"]["arguments"] or "{}")
			except ValueError:
				args = {}
			try:
				result = _run_tool(name, args, property)
				actions.append({"tool": name, "ok": True})
			except Exception as e:
				result = {"error": str(e)}
				actions.append({"tool": name, "ok": False, "error": str(e)})
			convo.append({"role": "tool",
			              "tool_call_id": call["id"],
			              "content": _tool_json_for_provider(result, s)})

	return {"reply": "I hit my tool-call limit for one question - "
	                 "try breaking it into smaller steps.",
	        "actions": actions}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance", "Revenue Manager")
def ask_stream(property: str, messages):
	"""Streaming Kamra Agent turn (Server-Sent Events). Governed tools run FIRST
	(they need the DB, which the request context still holds), emitting an
	`action` event each; then the final answer is streamed token-by-token as
	`token` events. The generator itself touches no DB - only the OpenAI stream
	- so it's safe to iterate after the request handler returns.

	Events: action {tool, ok} · token {text} · card {type, ...} · error
	{message} · done {}
	"""
	from werkzeug.wrappers import Response

	s = _settings(property)
	if not (s and s.enabled):
		frappe.throw("The AI assistant is not enabled for this property.")
	api_key = s.get_password("api_key", raise_exception=False)
	if not api_key:
		frappe.throw("No API key configured - Settings → AI assistant.")
	if isinstance(messages, str):
		messages = frappe.parse_json(messages)

	base = (s.base_url or "https://api.openai.com/v1").rstrip("/")
	model = s.model or "gpt-4o-mini"
	headers = {"Authorization": f"Bearer {api_key}",
	           "Content-Type": "application/json"}
	system = _system_prompt(property, s)
	convo = [{"role": "system", "content": system}] + list(messages)

	# --- resolve tools synchronously (DB access happens here, before streaming)
	actions = []
	frappe.local.kamra_chat_bookings = {}
	frappe.local.kamra_chat_refs = []
	frappe.local.kamra_chat_quote = None
	for _ in range(MAX_TOOL_ROUNDS):
		resp = _post_chat(base, headers, chat_payload(
			model, convo, tools=_tool_defs(), temperature=0.2))
		if resp.status_code != 200:
			if _out_of_credit(resp):
				return Response(_sse("error", _no_credit()) + _sse("done", {}),
				                mimetype="text/event-stream")
			frappe.throw(f"AI provider error ({resp.status_code}): {resp.text[:200]}")
		msg = resp.json()["choices"][0]["message"]
		calls = msg.get("tool_calls") or []
		if not calls:
			break  # data gathered; regenerate the answer streamed (no tools)
		convo.append(msg)
		for call in calls:
			try:
				args = json.loads(call["function"]["arguments"] or "{}")
			except ValueError:
				args = {}
			try:
				result = _run_tool(call["function"]["name"], args, property)
				actions.append({"tool": call["function"]["name"], "ok": True})
			except Exception as e:
				result = {"error": str(e)}
				actions.append({"tool": call["function"]["name"], "ok": False})
			convo.append({"role": "tool", "tool_call_id": call["id"],
			              "content": _tool_json_for_provider(result, s)})

	sse = _sse
	# read now: the generator runs after the request context is gone
	no_credit = _no_credit()
	refs = list(getattr(frappe.local, "kamra_chat_refs", None) or [])
	cards = _turn_cards()

	def gen():
		streamed = []
		for a in actions:
			yield sse("action", a)
		try:
			# final answer streamed WITHOUT tools → the model must produce text
			r = _post_chat(base, headers, chat_payload(
				model, convo, stream=True, temperature=0.2), stream=True)
			if r.status_code != 200:
				yield sse("error", no_credit if _out_of_credit(r)
				          else {"message": f"AI provider error ({r.status_code})"})
			else:
				for raw in r.iter_lines():
					if not raw:
						continue
					line = raw.decode("utf-8")
					if not line.startswith("data: "):
						continue
					chunk = line[6:]
					if chunk == "[DONE]":
						break
					try:
						delta = json.loads(chunk)["choices"][0].get("delta", {})
					except (ValueError, KeyError, IndexError):
						continue
					if delta.get("content"):
						streamed.append(delta["content"])
						yield sse("token", {"text": delta["content"]})
				text = "".join(streamed)
				missing = [r for r in refs if r not in text][:3]
				if missing:
					yield sse("token", {"text": f"\n\nRef: {', '.join(missing)}"})
				for card in cards:
					yield sse("card", card)
		except Exception as e:
			yield sse("error", {"message": str(e)[:150]})
		yield sse("done", {})

	return Response(gen(), mimetype="text/event-stream", headers={
		"Cache-Control": "no-cache",
		"X-Accel-Buffering": "no",  # tell nginx not to buffer this response
	})


HELP_SYSTEM = """You are the Kamra PMS help assistant. You explain HOW to use
Kamra - an open-source, AI-native hotel PMS - to hotel staff. You do NOT act on
hotel data (Kamra Agent does that); you give short, concrete how-to
answers and point to where things live in the app.

What Kamra does and where to find it:
- Front desk: "Today" (arrivals, departures, in-house, room board, check in /
  out), Tape Chart (rooms × dates; move rooms, amend stays), Calendar
  (availability).
- New booking: the "New booking" button opens a side drawer - pick the guest
  (returning guests autocomplete), room type, dates, meal plan and add-ons, with
  a live quote. "Add to waitlist" parks a stay when the dates are sold out or
  restricted; promote it later from the reservation when a room frees.
- Reservations: a searchable, filterable, paginated list; click a booking for
  the 360 panel - live billing, editable dates, guest journey, check in/out,
  cancel, registration card.
- Guests: profiles with stay history, VIP/blacklist, merge and anonymize.
- Billing: folios, post charges, take payments, payment links. Closing a folio
  assigns a tax invoice number (logo, tax ID and the tax details the
  property's country requires).
- Reports: one Reports hub - manager flash, shift report, F&B dashboard,
  banquet registers, SLA, voids, department packs (Front Office,
  Housekeeping, F&B, Hotel Manager) and custom reports (build, save, group
  and drill down, email daily or weekly). Which reports a user sees follows their
  role.
- Housekeeping: room board + a phone app at /kamra/hk.
- Revenue: rate plans, seasons, vouchers, rate guardrails.
- Events: Venue Bookings and a Venue Calendar (banquet/function diary);
  Experiences cover spa/tours as booking add-ons.
- Inventory: Rooms; Room Types - open a room type to add photos (image URLs),
  amenities (one per line) and a description shown on the public booking engine.
- Settings: property & GST, booking page (hero image, amenities, description),
  cancellation/deposit policy, payment gateway, and the AI assistant (your own
  key). Admins also have Developers (API keys), New Property and the Frappe Desk.
- Public booking engine at /book; pre-arrival self check-in via the guest link.
- Roles: a System Admin (IT - users, API keys, Frappe Desk) versus a Hotel
  Admin / GM (runs the property, no IT access). Manage staff from
  Admin → Manage Users.
- Kamra Agent (the sparkle button) can act - quote, book, check in,
  post charges, cancel, and watch the waitlist. This help assistant only
  explains how to do things yourself.

Be brief and practical. Use short steps. If you're unsure, say so and point to
the docs (github.com/Kamra-PMS/kamra-pms/tree/main/docs)."""


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance", "Revenue Manager", "Housekeeping")
def help_ask(property: str, messages):
	"""Streaming how-to help (SSE). No tools, no data access - just explains
	how to use Kamra, grounded in the app's features. Reuses the property's
	AI key. Events: token {text} · error {message} · done {}."""
	from werkzeug.wrappers import Response

	s = _settings(property)
	if not (s and s.enabled):
		frappe.throw("The AI assistant is not enabled for this property.")
	api_key = s.get_password("api_key", raise_exception=False)
	if not api_key:
		frappe.throw("No API key configured - Settings → AI assistant.")
	if isinstance(messages, str):
		messages = frappe.parse_json(messages)
	base = (s.base_url or "https://api.openai.com/v1").rstrip("/")
	model = s.model or "gpt-4o-mini"
	headers = {"Authorization": f"Bearer {api_key}",
	           "Content-Type": "application/json"}
	convo = [{"role": "system", "content": HELP_SYSTEM}] + list(messages)
	sse = _sse
	no_credit = _no_credit()  # translated now, before the request context goes

	def gen():
		try:
			r = _post_chat(base, headers, chat_payload(
				model, convo, stream=True, temperature=0.3), stream=True)
			if r.status_code != 200:
				yield sse("error", no_credit if _out_of_credit(r)
				          else {"message": f"AI provider error ({r.status_code})"})
			else:
				for raw in r.iter_lines():
					if not raw:
						continue
					line = raw.decode("utf-8")
					if not line.startswith("data: "):
						continue
					chunk = line[6:]
					if chunk == "[DONE]":
						break
					try:
						delta = json.loads(chunk)["choices"][0].get("delta", {})
					except (ValueError, KeyError, IndexError):
						continue
					if delta.get("content"):
						yield sse("token", {"text": delta["content"]})
		except Exception as e:
			yield sse("error", {"message": str(e)[:150]})
		yield sse("done", {})

	return Response(gen(), mimetype="text/event-stream", headers={
		"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
	})


# ---------------------------------------------------------------------------
# Persistent conversations for the full-page assistant module. Each row is one
# chat, owned by the user who created it and scoped to a property. Messages are
# the display history [{role, content, actions?}] - the agent re-runs its tools
# each turn, so it only needs the text history for context.
# ---------------------------------------------------------------------------

CONVO_ROLES = ("Front Desk", "Finance", "Revenue Manager", "Hotel Admin",
               "Kamra Agent")


def _own_convo(name):
	owner = frappe.db.get_value("Copilot Conversation", name, "owner")
	if owner is None:
		frappe.throw("Conversation not found.")
	if owner != frappe.session.user and "System Manager" not in frappe.get_roles():
		frappe.throw("That conversation isn't yours.", frappe.PermissionError)


@frappe.whitelist()
@require_roles(*CONVO_ROLES)
def list_conversations(property: str):
	"""The signed-in user's chats for this property, most recent first."""
	return frappe.get_all(
		"Copilot Conversation",
		filters={"owner": frappe.session.user, "property": property},
		fields=["name", "title", "modified"],
		order_by="modified desc", limit=100)


@frappe.whitelist()
@require_roles(*CONVO_ROLES)
def get_conversation(name: str):
	_own_convo(name)
	doc = frappe.get_doc("Copilot Conversation", name)
	return {
		"name": doc.name, "title": doc.title,
		"messages": frappe.parse_json(doc.messages) if doc.messages else [],
	}


@frappe.whitelist(methods=["POST"])
@require_roles(*CONVO_ROLES)
def create_conversation(property: str, title: str = "New chat"):
	doc = frappe.new_doc("Copilot Conversation")
	doc.property = property
	doc.title = title or "New chat"
	doc.messages = "[]"
	doc.insert(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional
	return {"name": doc.name, "title": doc.title}


@frappe.whitelist(methods=["POST"])
@require_roles(*CONVO_ROLES)
def save_conversation(name: str, messages, title: str | None = None):
	_own_convo(name)
	if isinstance(messages, str):
		messages = frappe.parse_json(messages)
	updates = {"messages": frappe.as_json(messages)}
	if title:
		updates["title"] = title[:140]
	frappe.db.set_value("Copilot Conversation", name, updates)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
@require_roles(*CONVO_ROLES)
def rename_conversation(name: str, title: str):
	_own_convo(name)
	frappe.db.set_value("Copilot Conversation", name, "title",
	                    (title or "Untitled")[:140])
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
@require_roles(*CONVO_ROLES)
def delete_conversation(name: str):
	_own_convo(name)
	frappe.delete_doc("Copilot Conversation", name, ignore_permissions=True)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional
	return {"ok": True}
