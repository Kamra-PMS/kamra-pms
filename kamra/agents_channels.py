"""Voice + WhatsApp seam: provider-agnostic webhook contract.

HeyKoala is the first-party recommended provider (rock8v2 for voice,
HeyKoala Concierge for WhatsApp) but the same endpoints accept payloads
from Twilio, Retell, Vapi, or Meta Business directly. All the provider
needs to do is:

    1. POST to /api/method/kamra.agents_channels.voice_webhook or
       messaging_webhook with an HMAC-SHA256 signature of the raw body
       in the X-Kamra-Signature header (hex-encoded).
    2. Include phone_number of the property line in the payload so
       Kamra can route to the right Channel Provider Connection.
    3. Include guest_phone (E.164) so we can resolve the reservation.

The webhook does NOT run the agent's turn synchronously: it stamps an
Agent Action Log entry (a short summary and the conversation reference,
never the guest's words) and returns the routing hints the provider
needs. To answer the guest, the provider calls the guest concierge
endpoints below with a concierge.guest service account key, never staff
MCP tools. Every call is in the Agent Action Log under that account.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import frappe
from frappe import _

from kamra import savings
from kamra.authz import require_roles

# ---------------------------------------------------------------------------
# Inbound webhooks
# ---------------------------------------------------------------------------


@frappe.whitelist(allow_guest=True, methods=["POST"])
def voice_webhook(payload: str | dict | None = None) -> dict:
	"""HeyKoala / Twilio / etc. call this on call lifecycle events.

	Expected payload shape (provider-agnostic):
	    {
	        "event": "call_started" | "call_ended" | "tool_call",
	        "phone_number": "+919876543210",   # the property line
	        "guest_phone": "+919812345678",   # the caller
	        "call_id": "prov-abc123",
	        "transcript": "...",              # on call_ended
	        "summary": "..."                  # on call_ended
	    }
	"""
	body = _parse_payload(payload)
	connection = _authenticate("Voice", body)
	if not connection:
		return {"ok": False, "reason": "connection_not_found"}

	guest, reservation = _resolve_caller(body.get("guest_phone"), connection.property)
	event = (body.get("event") or "").strip() or "call_event"

	# a short summary and the call reference, never the transcript: the
	# log is kept far longer than a guest's words should be (#566)
	rationale = _summary_line(f"Voice {event}", body.get("summary"), body.get("call_id"))

	log_name = savings.log_action(
		action_type=f"voice.{event}",
		reference_doctype="Reservation" if reservation else ("Guest" if guest else None),
		reference_name=reservation or guest,
		property=connection.property,
		minutes_saved=_estimate_minutes(event, body),
		rationale=rationale,
		after_snapshot=_conversation_ref(body, "call_id"),
		agent_name=(connection.handles_agent or f"Voice Concierge ({connection.provider})"),
		autonomy="Full",
		channel="Voice",
		approval_status="Executed",
	)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional

	return {
		"ok": True,
		"log": log_name,
		"guest": guest,
		"reservation": reservation,
		"agent": connection.handles_agent,
		"routing": _routing_hint(connection.property, guest, reservation),
	}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def messaging_webhook(payload: str | dict | None = None) -> dict:
	"""HeyKoala / Meta Business / Twilio-WA call this per inbound message.

	Expected payload:
	    {
	        "phone_number": "+919876543210",  # the property WhatsApp line
	        "guest_phone": "+919812345678",   # the sender
	        "message_id": "prov-xyz789",
	        "text": "Can I check in at 11am?",
	        "media_urls": [ ... ]             # optional
	    }

	Returns routing hints. The provider answers through the guest
	concierge endpoints (concierge_context, stay_context, guest_request,
	channel_book). The log keeps the provider's optional "summary" and the
	message_id, not the text.
	"""
	body = _parse_payload(payload)
	connection = _authenticate("WhatsApp", body)
	if not connection:
		return {"ok": False, "reason": "connection_not_found"}

	guest, reservation = _resolve_caller(body.get("guest_phone"), connection.property)
	# the provider's summary (if it sends one) and the message reference,
	# never the guest's text (#566)
	rationale = _summary_line("WhatsApp inbound", body.get("summary"), body.get("message_id"))

	log_name = savings.log_action(
		action_type="whatsapp.inbound",
		reference_doctype="Reservation" if reservation else ("Guest" if guest else None),
		reference_name=reservation or guest,
		property=connection.property,
		minutes_saved=2,  # every triage-and-reply is ~2 clerical minutes
		rationale=rationale,
		after_snapshot=_conversation_ref(body, "message_id"),
		agent_name=(connection.handles_agent or f"WhatsApp Concierge ({connection.provider})"),
		autonomy="Full",
		channel="WhatsApp",
		approval_status="Executed",
	)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional

	return {
		"ok": True,
		"log": log_name,
		"guest": guest,
		"reservation": reservation,
		"agent": connection.handles_agent,
		"routing": _routing_hint(connection.property, guest, reservation),
	}


# ---------------------------------------------------------------------------
# Public API: list connections (for the Settings screen)
# ---------------------------------------------------------------------------


@frappe.whitelist()
@require_roles("Hotel Admin", "System Manager")
def channel_connections(property: str) -> list[dict]:
	rows = frappe.get_all(
		"Channel Provider Connection",
		filters={"property": property},
		fields=[
			"name",
			"channel",
			"provider",
			"active",
			"phone_number",
			"handles_agent",
			"external_account_id",
			"outbound_send_url",
			"service_account",
			"notes",
		],
		order_by="channel asc, provider asc",
	)
	# Never surface secrets — the presence flag is enough for the UI.
	for row in rows:
		row["has_webhook_secret"] = bool(
			frappe.db.get_value(
				"Channel Provider Connection",
				row["name"],
				"webhook_secret",
			)
		)
		row["has_credentials"] = bool(
			frappe.db.get_value(
				"Channel Provider Connection",
				row["name"],
				"credentials",
			)
		)
	return rows


# ---------------------------------------------------------------------------
# Outbound helper (used by scheduled agents like Owner Digest)
# ---------------------------------------------------------------------------


def send_outbound(
	property: str,
	channel: str,
	to: str,
	body: str,
	*,
	agent_name: str | None = None,
	log_as: str | None = None,
) -> dict:
	"""Push a message via the active provider for this (property, channel).

	Owner Digest calls this to deliver the Sunday summary; the WhatsApp
	Concierge uses it for outbound replies. Non-blocking failure: if no
	active connection exists, logs a 'no_channel' event and returns
	{'sent': False}. Real HTTP dispatch is provider-specific and stubbed
	here — HeyKoala's SDK / Meta's Graph API get wired in the provider
	adapters when we land each integration.
	"""
	import requests

	# what the log says instead of the body (a one-time code never goes in)
	logged = log_as if log_as is not None else body[:280]
	conn = frappe.get_all(
		"Channel Provider Connection",
		filters={"property": property, "channel": channel, "active": 1},
		fields=["name", "provider", "outbound_send_url"],
		limit=1,
	)
	if not conn:
		savings.log_action(
			action_type=f"{channel.lower()}.outbound",
			property=property,
			rationale=f"No active {channel} connection, outbound dropped: {logged[:200]}",
			agent_name=agent_name,
			autonomy="Full",
			channel=channel,
			approval_status="Executed",
		)
		return {"sent": False, "reason": "no_channel"}

	c = conn[0]
	if c["provider"] == "Meta Business" and channel == "WhatsApp":
		# native Cloud API send - no relay URL needed
		from kamra import whatsapp
		return whatsapp.send_text(property, to, body)
	url = c.get("outbound_send_url")
	if not url:
		return {"sent": False, "reason": "no_outbound_url"}

	# Provider-agnostic payload — the receiver adapter reshapes to its
	# native API. Kamra doesn't need to know the difference between Meta
	# WA templates and HeyKoala freeform messages at this layer.
	credentials = frappe.get_doc(
		"Channel Provider Connection", c["name"]
	).get_password("credentials", raise_exception=False)

	try:
		res = requests.post(
			url,
			json={
				"channel": channel,
				"provider": c["provider"],
				"to": to,
				"body": body,
			},
			headers=({"Authorization": f"Bearer {credentials}"} if credentials else {}),
			timeout=10,
		)
		ok = 200 <= res.status_code < 300
	except Exception as exc:  # pragma: no cover — network is best-effort
		savings.log_action(
			action_type=f"{channel.lower()}.outbound_error",
			property=property,
			rationale=f"Outbound failed via {c['provider']}: {exc}",
			agent_name=agent_name,
			autonomy="Full",
			channel=channel,
			approval_status="Executed",
		)
		return {"sent": False, "reason": "provider_error"}

	savings.log_action(
		action_type=f"{channel.lower()}.outbound",
		property=property,
		rationale=f"To {to} via {c['provider']}: {logged}",
		agent_name=agent_name,
		autonomy="Full",
		channel=channel,
		approval_status="Executed",
		minutes_saved=1,
	)
	return {"sent": ok, "provider": c["provider"]}


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _parse_payload(payload):
	if payload is None:
		# Frappe unpacks JSON bodies into request.form; grab the raw body if not.
		try:
			return frappe.request.get_json(force=True, silent=True) or {}
		except Exception:
			return {}
	if isinstance(payload, str):
		try:
			return json.loads(payload)
		except ValueError:
			return {}
	return payload or {}


def _authenticate(channel: str, body: dict):
	"""Verify HMAC signature and find the matching Channel Provider Connection.

	Returns the Connection doc or None if verification fails / no match. On
	failure, logs to Frappe's error log but never raises — the provider
	sees a benign 200 with ok=False to prevent enumeration.
	"""
	phone = (body.get("phone_number") or "").strip()
	if not phone:
		return None

	conn_rows = frappe.get_all(
		"Channel Provider Connection",
		filters={"channel": channel, "phone_number": phone, "active": 1},
		limit=1,
		pluck="name",
	)
	if not conn_rows:
		return None
	conn = frappe.get_doc("Channel Provider Connection", conn_rows[0])

	secret = conn.get_password("webhook_secret", raise_exception=False)
	if not secret or not _verify_signature(secret, body):
		frappe.log_error(
			title="Channel webhook signature mismatch",
			message=f"channel={channel} phone={phone} conn={conn.name}",
		)
		return None
	return conn


def _verify_signature(secret: str, body: dict) -> bool:
	sig_header = (
		frappe.get_request_header("X-Kamra-Signature")
		or frappe.get_request_header("X-Signature")
		or ""
	).strip()
	if not sig_header:
		return False
	raw = json.dumps(body, sort_keys=True, default=str).encode()
	expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
	return hmac.compare_digest(expected, sig_header.lower())


def _resolve_caller(guest_phone: str | None, property: str | None) -> tuple[str | None, str | None]:
	"""Best-effort: find a guest by E.164 phone, then their active reservation."""
	if not guest_phone:
		return None, None
	from kamra import phone as phone_mod
	guest = frappe.db.get_value("Guest", {"phone": phone_mod.matching(guest_phone, property)}, "name")
	if not guest:
		return None, None

	filters = {"guest": guest, "status": ("in", ["Confirmed", "Checked In"])}
	if property:
		filters["property"] = property
	res = frappe.get_all(
		"Reservation",
		filters=filters,
		pluck="name",
		order_by="check_in_date asc",
		limit=1,
	)
	return guest, (res[0] if res else None)


def _routing_hint(property: str, guest: str | None, reservation: str | None) -> dict:
	"""What the provider's agent runtime needs to pre-load a call/message."""
	hint = {"property": property}
	if guest:
		hint["guest"] = guest
	if reservation:
		hint["reservation"] = reservation
	return hint


def _estimate_minutes(event: str, body: dict) -> float:
	"""Rough per-event minutes saved. Full call ≈ 5m; individual events ≈ 1m."""
	if event == "call_ended":
		# Some providers pass duration_seconds; longer calls saved more time.
		duration = float(body.get("duration_seconds") or 0)
		if duration >= 60:
			return round(duration / 60.0 + 2, 1)  # call time + triage overhead
		return 5.0
	return 1.0


def _summary_line(label: str, summary, ref) -> str:
	"""What a channel webhook keeps in the log: the event, the provider's
	own short summary (capped) and the conversation reference."""
	line = label
	summary = " ".join(str(summary or "").split())[:SUMMARY_CHARS]
	if summary:
		line += f": {summary}"
	if ref:
		line += f" [ref {str(ref)[:80]}]"
	return line


def _conversation_ref(body: dict, key: str) -> dict | None:
	ref = body.get(key) or body.get("conversation_id")
	return {"conversation_ref": str(ref)[:140]} if ref else None


SUMMARY_CHARS = 280


# ---------------------------------------------------------------------------
# Guest concierge: what a guest-facing channel agent may call
# ---------------------------------------------------------------------------
#
# A channel provider (WhatsApp, web chat, voice) talks to guests. It gets a
# service account with the guest concierge scope (kamra.service_accounts),
# linked from its Channel Provider Connection, and every request is also
# signed with that connection's webhook secret. The scope opens these four
# endpoints and nothing else: no staff MCP tool, no folio, no other guest.
#
# Every request body carries phone_number (the property line, picks the
# connection) and ts (unix seconds, within SIGNATURE_WINDOW), and is signed
# like the webhooks above: X-Kamra-Signature = hex HMAC-SHA256 of the JSON
# body with sorted keys.

SIGNATURE_WINDOW = 300
OTP_MINUTES = 10
OTP_TRIES = 5
CHANNEL_BOOK_LIMIT = 60  # per connection per hour; site config kamra_channel_book_limit

# what a guest may ask for: kind -> (stay instruction department, wording)
# or (None, ticket category)
REQUEST_KINDS = {
	"early_check_in": ("Front Desk", "Guest asks for early check-in"),
	"late_check_out": ("Front Desk", "Guest asks for late check-out"),
	"extra_bed": ("Housekeeping", "Guest asks for an extra bed"),
	"airport_transfer": ("Transport", "Guest asks for an airport transfer"),
	"special_occasion": ("Concierge", "Guest mentions a special occasion"),
	"housekeeping": (None, "Housekeeping"),
	"room_service": (None, "Room Service"),
	"maintenance": (None, "Maintenance"),
	"concierge": (None, "Concierge"),
	"other": (None, "Other"),
}
LIVE_STAY = ("Confirmed", "Checked In", "Pending Payment")


def _signed_connection(body: dict):
	"""The Channel Provider Connection this request comes from. Refuses
	unless the caller is a guest concierge service account, the connection
	is linked to that account, the signature matches its secret and the
	request is fresh."""
	from frappe.utils import cint

	from kamra.authz import assert_property_access
	from kamra.service_accounts import CONCIERGE, _parse, account_for

	denied = frappe.PermissionError
	account = account_for()
	if not account or not account.enabled or CONCIERGE not in _parse(account.scopes):
		frappe.throw(_("Needs a guest concierge service account key."), denied)
	phone = str(body.get("phone_number") or "").strip()
	name = frappe.db.get_value("Channel Provider Connection", {
		"phone_number": phone, "active": 1, "service_account": account.name}) if phone else None
	if not name:
		frappe.throw(_("No active channel connection for this key and line."), denied)
	conn = frappe.get_doc("Channel Provider Connection", name)
	secret = conn.get_password("webhook_secret", raise_exception=False)
	if not secret or not _verify_signature(secret, body):
		frappe.log_error(title="Concierge signature mismatch", message=f"conn={conn.name}")
		frappe.throw(_("Signature does not match."), denied)
	# unix seconds on both sides (now_datetime is in the site's time zone)
	if abs(time.time() - cint(body.get("ts"))) > SIGNATURE_WINDOW:
		frappe.throw(_("Request is too old (or ts is missing). Send the current unix time in ts."),
		             denied)
	if body.get("property") and body["property"] != conn.property:
		frappe.throw(_("This connection is for another property."), denied)
	assert_property_access(conn.property)
	return conn


def _body(kwargs: dict) -> dict:
	body = dict(kwargs)
	body.pop("cmd", None)
	return body


@frappe.whitelist(methods=["POST"])
def concierge_context(**kwargs) -> dict:
	"""Hotel facts the hotel entered, for a guest conversation: FAQs, house
	rules, policies, amenities, published experiences, outlets, directions,
	check-in and check-out times. Nothing about any guest."""
	conn = _signed_connection(_body(kwargs))
	from kamra.public_api import _property_payload

	prop = _property_payload(frappe.get_cached_doc("Property", conn.property))
	keep = ("property_name", "description", "address_line", "city", "state", "pincode",
	        "country", "phone", "email", "website", "amenities", "checkin_time",
	        "checkout_time", "driving_directions", "latitude", "longitude", "faqs",
	        "house_rules", "pets_policy", "children_policy", "extra_bed_policy",
	        "pets_allowed", "minimum_nights", "free_cancel_days", "booking_mode",
	        "property_kind")
	out = {k: prop.get(k) for k in keep}
	out["property"] = conn.property
	out["experiences"] = frappe.get_all(
		"Experience",
		filters={"property": conn.property, "disabled": 0, "show_on_booking_page": 1},
		fields=["name", "experience_name", "category", "price", "duration", "description"],
		order_by="experience_name asc")
	out["outlets"] = frappe.get_all(
		"POS Outlet", filters={"property": conn.property, "disabled": 0},
		fields=["outlet_name", "outlet_type"], order_by="outlet_name asc")
	return out


def _live_stay(guest_phone, property: str):
	"""(guest, reservation) for this phone's current or next stay here."""
	from frappe.utils import nowdate

	from kamra import phone as phone_mod

	if not str(guest_phone or "").strip():
		return None, None
	guests = frappe.get_all("Guest", filters={
		"phone": phone_mod.matching(str(guest_phone), property)}, pluck="name")
	if not guests:
		return None, None
	res = frappe.get_all(
		"Reservation",
		filters={"guest": ("in", guests), "property": property,
		         "status": ("in", LIVE_STAY), "check_out_date": (">=", nowdate())},
		fields=["name", "guest"], order_by="check_in_date asc", limit=1)
	return (res[0].guest, res[0].name) if res else (None, None)


@frappe.whitelist(methods=["POST"])
def stay_context(**kwargs) -> dict:
	"""Minimal facts for the caller's own current or next stay here: dates,
	room type, party, stays count, last stay, VIP and category. No folio,
	no other guests. {"found": false} when this phone has no current or
	upcoming stay at the property."""
	body = _body(kwargs)
	conn = _signed_connection(body)
	guest, reservation = _live_stay(body.get("guest_phone"), conn.property)
	if not reservation:
		return {"found": False}
	res = frappe.db.get_value(
		"Reservation", reservation,
		["name", "status", "check_in_date", "check_out_date", "room_type", "adults",
		 "children"], as_dict=True)
	g = frappe.db.get_value("Guest", guest, ["first_name", "vip", "guest_category"],
	                        as_dict=True)
	past = frappe.get_all("Reservation", filters={
		"guest": guest, "property": conn.property, "status": "Checked Out"},
		pluck="check_out_date", order_by="check_out_date desc")
	return {
		"found": True,
		"reservation": res.name,
		"status": res.status,
		"check_in_date": str(res.check_in_date),
		"check_out_date": str(res.check_out_date),
		"room_type": frappe.db.get_value("Room Type", res.room_type, "room_type_name")
		or res.room_type,
		"adults": res.adults,
		"children": res.children,
		"first_name": g.first_name,
		"vip": bool(g.vip),
		"category": g.guest_category or "Standard",
		"stays_count": len(past),
		"last_stay": str(past[0]) if past else None,
	}


def _otp_key(reservation: str) -> str:
	return f"kamra_concierge_otp:{reservation}"


def _proof(res, body: dict, conn) -> dict | None:
	"""Nothing changes a stay on a phone match alone. The stay token (the
	pre-check-in link) or a one-time code sent to the phone on the booking
	proves it is the guest. Returns None when proven, else what to send
	back (a code was sent)."""
	from frappe.utils import cint

	token = str(body.get("stay_token") or "")
	if token:
		stored = res.get("precheckin_token") or ""
		if stored and hmac.compare_digest(stored, token):
			return None
		frappe.throw(_("That stay token does not match this booking."), frappe.PermissionError)
	key = _otp_key(res.name)
	otp = str(body.get("otp") or "").strip()
	if otp:
		state = frappe.cache.get_value(key) or {}
		if not state or cint(state.get("tries")) >= OTP_TRIES:
			frappe.cache.delete_value(key)
			frappe.throw(_("The code has expired. Ask for a new one."), frappe.PermissionError)
		if hmac.compare_digest(state.get("hash") or "", _otp_hash(res.name, otp)):
			frappe.cache.delete_value(key)
			return None
		state["tries"] = cint(state.get("tries")) + 1
		frappe.cache.set_value(key, state, expires_in_sec=OTP_MINUTES * 60)
		frappe.throw(_("That code is not right."), frappe.PermissionError)

	import secrets

	code = f"{secrets.randbelow(10**6):06d}"
	frappe.cache.set_value(key, {"hash": _otp_hash(res.name, code), "tries": 0},
	                       expires_in_sec=OTP_MINUTES * 60)
	phone = frappe.db.get_value("Guest", res.guest, "phone")
	prop = frappe.get_cached_value("Property", res.property, "property_name")
	# to the phone on the booking, never to a number the caller names
	sent = send_outbound(
		res.property, "SMS" if conn.channel == "Voice" else conn.channel, phone,
		f"{code} is your {prop} code to confirm your request. It expires in "
		f"{OTP_MINUTES} minutes.", log_as="one-time code to the guest") if phone else {}
	return {"ok": False, "otp_required": True, "otp_sent": bool(sent.get("sent")),
	        "message": "Send the code the guest received as otp, or the stay_token."}


def _otp_hash(reservation: str, code: str) -> str:
	return hashlib.sha256(f"{reservation}:{code}".encode()).hexdigest()


@frappe.whitelist(methods=["POST"])
def guest_request(**kwargs) -> dict:
	"""Raise a guest's request on their own stay: a stay instruction (early
	check-in, late check-out, extra bed, airport transfer, special
	occasion) or a service ticket (housekeeping, room service, maintenance,
	concierge, other). Needs stay_token or otp; without either, a code is
	sent to the phone on the booking and otp_required comes back."""
	body = _body(kwargs)
	conn = _signed_connection(body)
	kind = str(body.get("kind") or "")
	if kind not in REQUEST_KINDS:
		frappe.throw(_("kind must be one of: {0}.").format(", ".join(REQUEST_KINDS)))
	name = str(body.get("reservation") or "")
	res = frappe.get_doc("Reservation", name) if name and frappe.db.exists(
		"Reservation", name) else None
	if not res or res.property != conn.property or res.status not in LIVE_STAY:
		frappe.throw(_("No current or upcoming stay with that reference here."),
		             frappe.PermissionError)
	pending = _proof(res, body, conn)
	if pending:
		return pending

	from kamra import api
	from kamra.authz import act_as
	from kamra.public_api import GUEST_AGENT

	note = " ".join(str(body.get("note") or "").split())[:500]
	department, wording = REQUEST_KINDS[kind]
	source = conn.channel if conn.channel in ("WhatsApp", "Voice") else "AI Agent"
	with act_as(GUEST_AGENT):
		if department:
			api.add_stay_instruction(res.name, department,
			                         f"{wording} (via {conn.channel})" + (f": {note}" if note else ""))
			out = {"ok": True, "kind": kind, "stay_instruction": department}
		else:
			room = res.get("room")
			ticket = api.create_ticket(
				conn.property, (note or wording)[:140], wording, room=room or None,
				reservation=res.name, guest=res.guest, description=note or None,
				source=source)
			out = {"ok": True, "kind": kind, "ticket": ticket["ticket"],
			       "due_by": ticket["due_by"]}
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the request before replying to the channel provider
	return out


@frappe.whitelist(methods=["POST"])
def channel_book(**kwargs) -> dict:
	"""Book for a guest in the conversation. The same booking as the public
	booking page (public_api), priced by the pricing engine, with the AI
	Agent source and this channel on the booking. idempotency_key is
	required, so a retry returns the same booking. A payment link comes
	back when an advance is due and the property has a gateway. Limited per
	connection (site config kamra_channel_book_limit, per hour), not per
	IP: the booking page's own limit is unchanged."""
	from frappe.utils import cint

	body = _body(kwargs)
	conn = _signed_connection(body)
	key = str(body.get("idempotency_key") or "").strip()
	if not key:
		frappe.throw(_("idempotency_key is required."))
	limit = cint(frappe.conf.get("kamra_channel_book_limit") or CHANNEL_BOOK_LIMIT)
	counter = frappe.cache.make_key(f"kamra_channel_book:{conn.name}")
	# same counter as frappe.rate_limiter; make_key keeps it per site
	if not frappe.cache.get(counter):  # nosemgrep: frappe-cache-breaks-multitenancy -- key made with make_key, so it is per site
		frappe.cache.setex(counter, 3600, 0)  # nosemgrep: frappe-cache-breaks-multitenancy -- key made with make_key, so it is per site
	if frappe.cache.incrby(counter, 1) > limit:
		frappe.throw(_("Too many bookings from this channel in the last hour."),
		             frappe.RateLimitExceededError)

	from kamra.public_api import _book

	guest_phone = str(body.get("phone") or body.get("guest_phone") or "")
	out = _book(
		conn.property, body.get("room_type"), body.get("check_in_date"),
		body.get("check_out_date"), str(body.get("guest_name") or ""), guest_phone,
		email=body.get("email") or "", adults=cint(body.get("adults") or 2),
		children=cint(body.get("children") or 0), meal_plan=body.get("meal_plan") or "",
		special_requests=" ".join(str(body.get("special_requests") or "").split())[:500],
		addons=body.get("addons"), voucher_code=body.get("voucher_code") or "",
		idempotency_key=key, child_ages=body.get("child_ages"),
		source="AI Agent", channel=conn.channel)
	out["payment_link"] = _deposit_link(out) if out.get("advance_due") else None
	return out


def _deposit_link(booking: dict) -> str | None:
	"""A pay-online link for the advance, or None where the property has no
	live gateway (the guest pays as the booking's payment policy says)."""
	from kamra import api
	from kamra.authz import act_as
	from kamra.public_api import GUEST_AGENT

	try:
		with act_as(GUEST_AGENT):
			return (api.deposit_payment_link(booking["reservation"],
			                                 booking["advance_due"]) or {}).get("url")
	except frappe.ValidationError:
		frappe.clear_messages()
		return None
