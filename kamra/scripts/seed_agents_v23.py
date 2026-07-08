"""Seed the three default agents per property (v23 slice).

Idempotent — safe to re-run. Get-or-creates by (property, persona) so
existing rows are not overwritten; the hotel is free to rename them,
tighten tools, or change models afterwards.

Run:
    from kamra.scripts.seed_agents_v23 import execute; execute()
Or targeted:
    from kamra.scripts.seed_agents_v23 import execute; execute("Kamra Demo Palace")
"""

import frappe


# The read-heavy set almost every persona wants for context.
READ_TOOLS = [
	"front_desk_snapshot",
	"availability_calendar",
	"booking_options",
	"guest_search",
	"guests_with_stats",
	"guest_journey",
	"find_reservations",
	"reservation_detail",
	"tape_chart",
	"hk_queue",
	"tickets_list",
	"get_folio",
	"cash_summary",
	"cancellation_preview",
	"cancellation_letter",
	"my_properties",
]


FRONT_DESK_WRITE_TOOLS = [
	"get_quote",
	"create_booking",
	"amend_stay",
	"move_reservation",
	"check_in",
	"check_out",
	"add_folio_charge",
	"add_folio_payment",
	"record_advance",
	"send_payment_link",
	"create_ticket",
	"advance_ticket",
	"hk_update_task",
	"set_housekeeping_status",
	"post_stay_charge",
	"update_occupants",
	"cancel_reservation",
	"split_folio_charge",
	"transfer_folio_charge",
	"transfer_folio_charges",
	"merge_guests",
]


NIGHT_AUDIT_TOOLS = [
	"run_night_audit",
	"front_desk_snapshot",
	"owner_briefing",
	"cash_summary",
]


OWNER_DIGEST_TOOLS = [
	"owner_briefing",
	"front_desk_snapshot",
	"cash_summary",
	"gstr1_rows",
]


FRONT_DESK_PROMPT = (
	"You are the Front Desk Copilot. You help the staff get their job done fast. "
	"Never guess at money or availability — always call the quote/availability tools "
	"before proposing a booking. Confirm before you charge, waive, refund, or cancel. "
	"When something needs approval, say so and describe the pending action clearly."
)

NIGHT_AUDIT_PROMPT = (
	"You are the Night Auditor. You run once at 3am. Close out the day: post room+meal "
	"nights, flag no-shows, reconcile cash, and produce a variance report. If variance "
	"exceeds the tolerance, park the reconciliation as Pending for the owner instead of "
	"forcing it through."
)

OWNER_DIGEST_PROMPT = (
	"You are the Owner Digest agent. Every Sunday 8am you produce a short WhatsApp-ready "
	"summary of the past week: occupancy vs forecast, RevPAR, top pending decisions, and "
	"anything unusual in the Agent Action Log. Be concise, use numbers, no fluff."
)


def _get_or_create(property_name: str | None, persona: str, defaults: dict) -> str:
	"""Idempotent by (property, persona)."""
	existing = frappe.get_all(
		"Agent",
		filters={"property": property_name or "", "persona": persona},
		limit=1,
	)
	if existing:
		return existing[0].name
	doc = frappe.get_doc({
		"doctype": "Agent",
		"property": property_name,
		"persona": persona,
		**defaults,
	})
	doc.insert(ignore_permissions=True)
	return doc.name


def _wire_front_desk(property_name: str | None) -> str:
	name = _get_or_create(
		property_name,
		"Front Desk Copilot",
		{
			"agent_name": "NOVA",
			"active": 1,
			"trigger_type": "Event",
			"channel": "Desk",
			"model": "claude-sonnet-4-7",
			"system_prompt": FRONT_DESK_PROMPT,
		},
	)
	doc = frappe.get_doc("Agent", name)
	_replace_tools(doc, READ_TOOLS + FRONT_DESK_WRITE_TOOLS)
	_replace_autonomy(doc, [
		# Money out — always ask.
		("cancel_reservation", "Approve", None, None, 0, "Cancellations touch policy fees."),
		("merge_guests", "Approve", None, None, 0, "Merges are hard to undo — human confirms."),
		("split_folio_charge", "Approve", None, None, 0, "Money movement between folios."),
		("transfer_folio_charge", "Approve", None, None, 0, "Money movement between folios."),
		("transfer_folio_charges", "Approve", None, None, 0, "Bulk money movement."),
		# Charges above ₹500 in absolute value — ask.
		("add_folio_charge", "Approve", "amount", ">=", 500, "High-value line items go through GM."),
		("post_stay_charge", "Approve", "amount", ">=", 500, "High-value line items go through GM."),
		# Rate overrides — always ask; guardrails already clamp but human sees delta.
		("set_room_rate", "Approve", None, None, 0, "Rate changes always route to Revenue Manager."),
	])
	doc.save(ignore_permissions=True)
	return name


def _wire_night_auditor(property_name: str | None) -> str:
	name = _get_or_create(
		property_name,
		"Night Auditor",
		{
			"agent_name": "IRA",
			"active": 1,
			"trigger_type": "Cron",
			"schedule_cron": "0 3 * * *",
			"channel": "API",
			"model": "claude-haiku-4-5",
			"system_prompt": NIGHT_AUDIT_PROMPT,
		},
	)
	doc = frappe.get_doc("Agent", name)
	_replace_tools(doc, NIGHT_AUDIT_TOOLS)
	# Variance handling is enforced inside the run_night_audit implementation, not the
	# gate — variance thresholds live on Property, not Agent. Full is fine here.
	_replace_autonomy(doc, [])
	doc.save(ignore_permissions=True)
	return name


def _wire_owner_digest(property_name: str | None) -> str:
	name = _get_or_create(
		property_name,
		"Owner Digest",
		{
			"agent_name": "TARA",
			"active": 1,
			"trigger_type": "Cron",
			"schedule_cron": "0 8 * * 0",
			"channel": "WhatsApp",
			"model": "claude-haiku-4-5",
			"system_prompt": OWNER_DIGEST_PROMPT,
		},
	)
	doc = frappe.get_doc("Agent", name)
	_replace_tools(doc, OWNER_DIGEST_TOOLS)
	# Read-only — no autonomy rules needed.
	_replace_autonomy(doc, [])
	doc.save(ignore_permissions=True)
	return name


ALLOCATION_PROMPT = (
	"You are ORION, the Allocation agent. Each night you give tomorrow's "
	"arrivals the right room - matching room type, honouring guest preferences "
	"(a lake view, a high floor, a quiet corner), giving VIPs the best available "
	"room, and keeping groups together. Assign the obvious ones yourself; when "
	"there is a real choice, a VIP, or a preference to weigh, propose it and let "
	"the front desk approve. Never move a guest who is already placed."
)


def _wire_allocation(property_name: str | None) -> str:
	name = _get_or_create(
		property_name,
		"Allocation",
		{
			"agent_name": "ORION",
			"active": 1,
			"trigger_type": "Cron",
			"schedule_cron": "30 3 * * *",
			"channel": "API",
			"model": "claude-haiku-4-5",
			"system_prompt": ALLOCATION_PROMPT,
		},
	)
	doc = frappe.get_doc("Agent", name)
	_replace_tools(doc, READ_TOOLS + [
		"kamra.allocation.suggest_allocation",
		"kamra.allocation.apply_allocation",
	])
	_replace_autonomy(doc, [
		# Assign freely when it's the only sensible room; when the proposal
		# needed a judgement call (choice / VIP / preference), route to approval.
		("allocate_room", "Approve", "needs_review", ">=", 1,
		 "Preference, VIP or a real choice - the desk confirms."),
	])
	doc.save(ignore_permissions=True)
	return name


def _replace_tools(doc, tool_names: list[str]) -> None:
	doc.set("tool_allowlist", [])
	for t in sorted(set(tool_names)):
		doc.append("tool_allowlist", {"tool_name": t})


def _replace_autonomy(doc, rules: list[tuple]) -> None:
	doc.set("autonomy_rules", [])
	for action_type, autonomy, field, op, value, note in rules:
		doc.append("autonomy_rules", {
			"action_type": action_type,
			"autonomy": autonomy,
			"threshold_field": field,
			"threshold_operator": op,
			"threshold_value": value,
			"note": note,
		})


def execute(property_name: str | None = None) -> dict:
	"""Seed the three defaults for every enabled property (or one, if named)."""
	if property_name:
		properties: list[str | None] = [property_name]
	else:
		rows = frappe.get_all("Property", filters={"disabled": 0}, pluck="name") or []
		properties = list(rows) or [None]

	created = []
	for prop in properties:
		created.append(_wire_front_desk(prop))
		created.append(_wire_night_auditor(prop))
		created.append(_wire_owner_digest(prop))
		created.append(_wire_allocation(prop))
	frappe.db.commit()
	return {"seeded": len(created), "agents": created}
