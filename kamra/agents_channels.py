"""Voice + WhatsApp seam — provider-agnostic webhook contract.

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

The webhook does NOT run the agent's turn synchronously — it stamps an
Agent Action Log entry, snapshots useful context (linked reservation,
guest journey), and returns the routing hints the provider needs. The
provider then invokes the same MCP tools directly under its own auth
context (with agent_name in the tool payload), just like external Claude
would. That keeps the tool audit trail identical across humans, agents,
and voice/text guests — one Autonomy Gate → one Action Log.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import frappe

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

	summary = body.get("summary") or f"Voice · {event}"
	rationale = summary
	if body.get("transcript"):
		rationale = (rationale + "\n\n" + (body["transcript"] or ""))[:2000]

	log_name = savings.log_action(
		action_type=f"voice.{event}",
		reference_doctype="Reservation" if reservation else ("Guest" if guest else None),
		reference_name=reservation or guest,
		property=connection.property,
		minutes_saved=_estimate_minutes(event, body),
		rationale=rationale,
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

	Returns routing hints. The provider then either calls MCP tools
	directly or POSTs to a follow-up endpoint to receive Kamra's reply.
	"""
	body = _parse_payload(payload)
	connection = _authenticate("WhatsApp", body)
	if not connection:
		return {"ok": False, "reason": "connection_not_found"}

	guest, reservation = _resolve_caller(body.get("guest_phone"), connection.property)
	text = (body.get("text") or "").strip()
	rationale = f"WhatsApp inbound: {text[:1500]}" if text else "WhatsApp inbound"

	log_name = savings.log_action(
		action_type="whatsapp.inbound",
		reference_doctype="Reservation" if reservation else ("Guest" if guest else None),
		reference_name=reservation or guest,
		property=connection.property,
		minutes_saved=2,  # every triage-and-reply is ~2 clerical minutes
		rationale=rationale,
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
			rationale=f"No active {channel} connection — outbound dropped: {body[:200]}",
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
		rationale=f"To {to} via {c['provider']}: {body[:280]}",
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
	if secret and not _verify_signature(secret, body):
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
	guest = frappe.db.get_value("Guest", {"phone": guest_phone}, "name")
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
