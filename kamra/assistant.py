"""Front-desk copilot — BYOK, optional, governed.

Talks to any OpenAI-compatible chat endpoint (OpenAI, OpenRouter, Groq,
Ollama, …) with the owner's own key. The model only ever acts through
the same whitelisted tool layer agents use: prices come from the pricing
engine, guardrails and policies apply, and every action lands in the
Agent Action Log. If the model is wrong, the tools refuse.
"""

import json

import frappe
import requests
from frappe.utils import nowdate

MAX_TOOL_ROUNDS = 6
TIMEOUT = 60

SYSTEM = """You are the front-desk copilot for {property_name}, a hotel
running Kamra PMS. Today is {today}. You help staff work faster: look
things up, quote, book, check guests in and out, post charges, take
payments, preview and process cancellations.

Rules:
- Numbers come from tools, never from you. Always quote before booking.
- Before cancelling, run the cancellation preview and state the fee.
- Confirm irreversible actions (cancel, checkout with balance) in one
  short question before calling the tool.
- Be brief and concrete — front desk answers, not essays. Amounts in ₹.
{extra}"""

# tool name → (kamra.api function, description, JSON-schema params,
# inject property?, mutating? — mutating calls are audit-logged)
EXTRA_TOOLS = {
	"amend_stay": (
		"amend_stay",
		"Change a stay's dates (extend/shorten). Re-prices and re-checks overlaps.",
		{"reservation": {"type": "string"}, "check_in_date": {"type": "string"},
		 "check_out_date": {"type": "string"}}, False, True),
	"move_room": (
		"move_reservation",
		"Move a stay to a different room.",
		{"reservation": {"type": "string"}, "new_room": {"type": "string"}},
		False, True),
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
	"set_room_rate": (
		"set_room_rate",
		"Set a nightly rate for a room type over dates. Owner guardrails apply — give a reason.",
		{"room_type": {"type": "string"}, "start_date": {"type": "string"},
		 "end_date": {"type": "string"}, "rate": {"type": "number"},
		 "reason": {"type": "string"}}, True, True),
	"owner_briefing": (
		"owner_briefing",
		"The manager's numbers: occupancy, revenue/ADR/RevPAR, arrivals, tickets.",
		{"date": {"type": "string"}}, True, False),
	"run_night_audit": (
		"run_night_audit",
		"Run end-of-day for a date: posts room nights, flags & charges no-shows.",
		{"business_date": {"type": "string"}}, True, True),
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
		"Price a stay (room type, dates, occupancy, optional meal plan / voucher).",
		{"room_type": {"type": "string"}, "check_in_date": {"type": "string"},
		 "check_out_date": {"type": "string"}, "adults": {"type": "integer"},
		 "children": {"type": "integer"}, "meal_plan": {"type": "string"},
		 "voucher_code": {"type": "string"}}, True, False),
	"booking_options": (
		"booking_options",
		"Room types, meal plans, companies, travel agents, experiences, sell message and policies.",
		{}, True, False),
	"create_booking": (
		"create_booking",
		"Book a stay. Quote first; confirm the total with staff before calling.",
		{"room_type": {"type": "string"}, "check_in_date": {"type": "string"},
		 "check_out_date": {"type": "string"}, "guest_name": {"type": "string"},
		 "phone": {"type": "string"}, "adults": {"type": "integer"},
		 "children": {"type": "integer"}, "meal_plan": {"type": "string"},
		 "company": {"type": "string"},
		 "booked_by_name": {"type": "string"},
		 "booked_by_phone": {"type": "string"}}, True, True),
	"guest_search": (
		"guest_search",
		"Find a guest profile by name or phone (returning guests, VIPs).",
		{"q": {"type": "string"}}, False, False),
	"check_in": (
		"check_in",
		"Check a reservation in (optionally into a specific room).",
		{"reservation": {"type": "string"}, "room": {"type": "string"}}, False, True),
	"check_out": (
		"check_out",
		"Check a reservation out. State the folio balance first if unpaid.",
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
		"Record a payment against a folio (mode: Cash, UPI, Card, Bank, Link).",
		{"folio": {"type": "string"}, "mode": {"type": "string"},
		 "amount": {"type": "number"}, "reference": {"type": "string"}}, False, True),
	"cancellation_preview": (
		"cancellation_preview",
		"What cancelling would cost right now. Always run before cancelling.",
		{"reservation": {"type": "string"}}, False, False),
	"cancel_booking": (
		"cancel_reservation",
		"Cancel a confirmed booking (policy applies; returns a cancellation number to read out).",
		{"reservation": {"type": "string"}, "reason": {"type": "string"},
		 "note": {"type": "string"}}, False, True),
}


def _settings(property: str):
	name = frappe.db.get_value(
		"AI Assistant Settings", {"property": property})
	return frappe.get_doc("AI Assistant Settings", name) if name else None


@frappe.whitelist()
def assistant_status(property: str):
	s = _settings(property)
	return {"enabled": bool(s and s.enabled and s.get_password(
		"api_key", raise_exception=False))}


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
	} for name, (_, desc, params, _inject, _mut) in TOOLS.items()]


def _run_tool(name: str, args: dict, property: str):
	from kamra import api
	fn_name, _desc, params, inject, mutating = TOOLS[name]
	fn = getattr(api, fn_name)
	clean = {k: v for k, v in args.items()
	         if k in params and v not in (None, "")}
	if inject:
		clean["property"] = property
	result = fn(**clean)
	if mutating:
		# a guaranteed audit line for every state-changing chat action,
		# on top of whatever the API itself logs
		from kamra.savings import log_action
		log_action("copilot_" + name, "Property", property, property,
		           rationale=frappe.as_json(clean)[:400],
		           agent_name="Front Desk Copilot", channel="Chat")
	return json.loads(frappe.as_json(result))


@frappe.whitelist()
def ask(property: str, messages):
	"""One copilot turn: history in, answer out. The model may call
	governed tools along the way; every call is returned so the UI can
	show what actually happened."""
	s = _settings(property)
	if not (s and s.enabled):
		frappe.throw("The AI assistant is not enabled for this property — "
		             "an admin can switch it on under Settings.")
	api_key = s.get_password("api_key", raise_exception=False)
	if not api_key:
		frappe.throw("No API key configured. Add your provider's key under "
		             "Settings → AI assistant.")
	if isinstance(messages, str):
		messages = frappe.parse_json(messages)

	prop_name = frappe.db.get_value("Property", property, "property_name")
	system = SYSTEM.format(
		property_name=prop_name or property, today=nowdate(),
		extra=("\n" + s.extra_instructions) if s.extra_instructions else "")
	convo = [{"role": "system", "content": system}] + list(messages)

	actions = []
	for _ in range(MAX_TOOL_ROUNDS):
		resp = requests.post(
			f"{(s.base_url or 'https://api.openai.com/v1').rstrip('/')}/chat/completions",
			headers={"Authorization": f"Bearer {api_key}",
			         "Content-Type": "application/json"},
			json={"model": s.model or "gpt-4o-mini", "messages": convo,
			      "tools": _tool_defs(), "temperature": 0.2},
			timeout=TIMEOUT,
		)
		if resp.status_code != 200:
			frappe.throw(f"AI provider error ({resp.status_code}): "
			             f"{resp.text[:300]}")
		msg = resp.json()["choices"][0]["message"]
		convo.append(msg)

		calls = msg.get("tool_calls") or []
		if not calls:
			return {"reply": msg.get("content") or "", "actions": actions}

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
			              "content": frappe.as_json(result)})

	return {"reply": "I hit my tool-call limit for one question — "
	                 "try breaking it into smaller steps.",
	        "actions": actions}
