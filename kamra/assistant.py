"""Front-desk copilot — BYOK, optional, governed.

Talks to any OpenAI-compatible chat endpoint (OpenAI, OpenRouter, Groq,
Ollama, …) with the owner's own key. The model only ever acts through
the same whitelisted tool layer agents use: prices come from the pricing
engine, guardrails and policies apply, and every action lands in the
Agent Action Log. If the model is wrong, the tools refuse.
"""

import json

import frappe
from kamra.authz import require_roles
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
- A room number (e.g. 101) is NOT a reservation id (e.g. RES-2026-00021).
  To act on a guest, first find the reservation with find_reservations (by
  guest name, room number, or status), then use its `name` as the reservation
  id for check_out / get_folio / stay_detail / cancel.
- "Who checked out / arrived / is in-house / is confirmed?" → find_reservations
  with the matching status (Checked Out, Checked In, Confirmed, Cancelled,
  No Show). front_desk_today is only *today's* board.
- Never say you can't find something before calling find_reservations.
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
	"find_reservations": (
		"find_reservations",
		"Find reservations by guest name, room number, or reference — optionally "
		"filtered by status (Confirmed, Checked In, Checked Out, Cancelled, No "
		"Show). Use this to resolve a room number or a name to a reservation "
		"before acting, or to list stays by status (e.g. who checked out).",
		{"query": {"type": "string"}, "status": {"type": "string"},
		 "limit": {"type": "integer"}}, True, False),
	"stay_detail": (
		"reservation_detail",
		"Full detail for one reservation: dates, room, guest + stay history, "
		"folio balance (paid/due), booker, and which actions are available.",
		{"reservation": {"type": "string"}}, False, False),
	"waitlist_ready": (
		"waitlist_ready",
		"Waitlisted stays that can now be booked — a room freed for their "
		"dates — with the guest's phone, so you can proactively reach out.",
		{}, True, False),
	"promote_waitlist": (
		"promote_waitlist",
		"Promote a waitlisted reservation into a free room (Confirmed).",
		{"reservation": {"type": "string"}}, False, True),
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
	key = s.get_password("api_key", raise_exception=False) if s else None
	# Never return the key — only a masked tail so admins can confirm one is set.
	key_hint = ("••••" + key[-4:]) if key and len(key) >= 4 else None
	return {
		"enabled": bool(s and s.enabled and key),
		"model": (s.model if s else None) or "gpt-4o-mini",
		"key_hint": key_hint,
	}


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
	# copilot tool calls are agent actions: accountability comes from the
	# action log, not the cashier PIN (which guards humans at a terminal)
	frappe.flags.kamra_agent_call = True
	try:
		result = fn(**clean)
	finally:
		frappe.flags.kamra_agent_call = False
	if mutating:
		# a guaranteed audit line for every state-changing chat action,
		# on top of whatever the API itself logs
		from kamra.savings import log_action
		log_action("copilot_" + name, "Property", property, property,
		           rationale=frappe.as_json(clean)[:400],
		           agent_name="Front Desk Copilot", channel="Chat")
	return json.loads(frappe.as_json(result))


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Revenue Manager")
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


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance", "Revenue Manager")
def ask_stream(property: str, messages):
	"""Streaming copilot turn (Server-Sent Events). Governed tools run FIRST
	(they need the DB, which the request context still holds), emitting an
	`action` event each; then the final answer is streamed token-by-token as
	`token` events. The generator itself touches no DB — only the OpenAI stream
	— so it's safe to iterate after the request handler returns.

	Events: action {tool, ok} · token {text} · error {message} · done {}
	"""
	from werkzeug.wrappers import Response

	s = _settings(property)
	if not (s and s.enabled):
		frappe.throw("The AI assistant is not enabled for this property.")
	api_key = s.get_password("api_key", raise_exception=False)
	if not api_key:
		frappe.throw("No API key configured — Settings → AI assistant.")
	if isinstance(messages, str):
		messages = frappe.parse_json(messages)

	base = (s.base_url or "https://api.openai.com/v1").rstrip("/")
	model = s.model or "gpt-4o-mini"
	headers = {"Authorization": f"Bearer {api_key}",
	           "Content-Type": "application/json"}
	prop_name = frappe.db.get_value("Property", property, "property_name")
	system = SYSTEM.format(
		property_name=prop_name or property, today=nowdate(),
		extra=("\n" + s.extra_instructions) if s.extra_instructions else "")
	convo = [{"role": "system", "content": system}] + list(messages)

	# --- resolve tools synchronously (DB access happens here, before streaming)
	actions = []
	for _ in range(MAX_TOOL_ROUNDS):
		resp = requests.post(f"{base}/chat/completions", headers=headers,
			json={"model": model, "messages": convo, "tools": _tool_defs(),
			      "temperature": 0.2}, timeout=TIMEOUT)
		if resp.status_code != 200:
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
			              "content": frappe.as_json(result)})

	def sse(event, data):
		return f"event: {event}\ndata: {json.dumps(data)}\n\n"

	def gen():
		for a in actions:
			yield sse("action", a)
		try:
			# final answer streamed WITHOUT tools → the model must produce text
			r = requests.post(f"{base}/chat/completions", headers=headers,
				json={"model": model, "messages": convo, "temperature": 0.2,
				      "stream": True}, stream=True, timeout=TIMEOUT)
			if r.status_code != 200:
				yield sse("error", {"message": f"AI provider error ({r.status_code})"})
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
		"Cache-Control": "no-cache",
		"X-Accel-Buffering": "no",  # tell nginx not to buffer this response
	})


HELP_SYSTEM = """You are the Kamra PMS help assistant. You explain HOW to use
Kamra — an open-source, AI-native hotel PMS — to hotel staff. You do NOT act on
hotel data (the front-desk copilot does that); you give short, concrete how-to
answers and point to where things live in the app.

What Kamra does and where to find it:
- Front desk: "Today" (arrivals, departures, in-house, room board, check in /
  out), Tape Chart (rooms × dates; move rooms, amend stays), Calendar
  (availability).
- New booking: the "New booking" button opens a side drawer — pick the guest
  (returning guests autocomplete), room type, dates, meal plan and add-ons, with
  a live quote. "Add to waitlist" parks a stay when the dates are sold out or
  restricted; promote it later from the reservation when a room frees.
- Reservations: a searchable, filterable, paginated list; click a booking for
  the 360 panel — live billing, editable dates, guest journey, check in/out,
  cancel, registration card.
- Guests: profiles with stay history, VIP/blacklist, merge and anonymize.
- Billing: folios, post charges, take payments, payment links. Closing a folio
  assigns a GST tax invoice (logo, GSTIN, place of supply, SAC 996311).
- Reports: occupancy, ADR, RevPAR, RevPAX, MTD, collections, 14-day trend.
- Housekeeping: room board + a phone app at /kamra/hk.
- Revenue: rate plans, seasons, vouchers, rate guardrails.
- Events: Venue Bookings and a Venue Calendar (banquet/function diary);
  Experiences cover spa/tours as booking add-ons.
- Inventory: Rooms; Room Types — open a room type to add photos (image URLs),
  amenities (one per line) and a description shown on the public booking engine.
- Settings: property & GST, booking page (hero image, amenities, description),
  cancellation/deposit policy, payment gateway, and the AI assistant (your own
  key). Admins also have Developers (API keys), New Property and the Frappe Desk.
- Public booking engine at /book; pre-arrival self check-in via the guest link.
- Roles: a System Admin (IT — users, API keys, Frappe Desk) versus a Hotel
  Admin / GM (runs the property, no IT access). Manage staff from
  Admin → Manage Users.
- The front-desk copilot (the sparkle button) can act — quote, book, check in,
  post charges, cancel, and watch the waitlist. This help assistant only
  explains how to do things yourself.

Be brief and practical. Use short steps. If you're unsure, say so and point to
the docs (github.com/Kamra-PMS/kamra-pms/tree/main/docs)."""


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance", "Revenue Manager", "Housekeeping")
def help_ask(property: str, messages):
	"""Streaming how-to help (SSE). No tools, no data access — just explains
	how to use Kamra, grounded in the app's features. Reuses the property's
	AI key. Events: token {text} · error {message} · done {}."""
	from werkzeug.wrappers import Response

	s = _settings(property)
	if not (s and s.enabled):
		frappe.throw("The AI assistant is not enabled for this property.")
	api_key = s.get_password("api_key", raise_exception=False)
	if not api_key:
		frappe.throw("No API key configured — Settings → AI assistant.")
	if isinstance(messages, str):
		messages = frappe.parse_json(messages)
	base = (s.base_url or "https://api.openai.com/v1").rstrip("/")
	model = s.model or "gpt-4o-mini"
	headers = {"Authorization": f"Bearer {api_key}",
	           "Content-Type": "application/json"}
	convo = [{"role": "system", "content": HELP_SYSTEM}] + list(messages)

	def sse(event, data):
		return f"event: {event}\ndata: {json.dumps(data)}\n\n"

	def gen():
		try:
			r = requests.post(f"{base}/chat/completions", headers=headers,
				json={"model": model, "messages": convo, "temperature": 0.3,
				      "stream": True}, stream=True, timeout=TIMEOUT)
			if r.status_code != 200:
				yield sse("error", {"message": f"AI provider error ({r.status_code})"})
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
# the display history [{role, content, actions?}] — the agent re-runs its tools
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
	frappe.db.commit()
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
	frappe.db.commit()
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
@require_roles(*CONVO_ROLES)
def rename_conversation(name: str, title: str):
	_own_convo(name)
	frappe.db.set_value("Copilot Conversation", name, "title",
	                    (title or "Untitled")[:140])
	frappe.db.commit()
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
@require_roles(*CONVO_ROLES)
def delete_conversation(name: str):
	_own_convo(name)
	frappe.delete_doc("Copilot Conversation", name, ignore_permissions=True)
	frappe.db.commit()
	return {"ok": True}
