"""Outbound webhooks - tell an integrator's system when something happens.

A hotel (Hotel Admin) subscribes an HTTPS endpoint, per property, to a list
of events. Kamra then POSTs a small signed JSON envelope for each event:

    {"id": "evt_...", "event": "reservation.created", "api_version": 1,
     "created_at": "2026-10-19T12:00:00", "property": "...", "data": {...}}

Delivery
    The event is written to the delivery log (Outbound Webhook Delivery)
    inside the same transaction as the change that caused it, and sent by a
    background job after commit - a rolled-back booking never notifies
    anyone, and a slow receiver never slows the desk. A non-2xx answer or a
    network error is retried with backoff (1m, 5m, 30m, 2h, 6h); the log
    keeps status, response code and attempts, and staff can resend.

Signature
    X-Kamra-Timestamp: unix seconds
    X-Kamra-Signature: sha256=HEX(HMAC_SHA256(secret, f"{timestamp}.{body}"))
    The receiver recomputes it over the raw body and rejects old timestamps.

Safety (see GHSA-5hcx for the history)
    - only HTTPS, never a private / loopback / link-local / internal
      address - checked when the URL is saved AND again before every send
      (DNS can change), redirects are not followed;
    - a payload carries only the record of the subscription's own property,
      and never guest contact details, ID documents or tokens;
    - the secret is stored encrypted, shown once, and never logged.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import secrets
import socket
import time
import uuid
from urllib.parse import urlsplit

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, now_datetime

from kamra.authz import require_roles

WEBHOOK = "Outbound Webhook"
DELIVERY = "Outbound Webhook Delivery"

API_VERSION = 1

EVENTS: dict[str, str] = {
	"reservation.created": "A booking was made (any source: desk, booking engine, OTA, agent).",
	"reservation.modified": "A booking's dates, room, room type, party, rate, plan or status changed.",
	"reservation.cancelled": "A booking was cancelled.",
	"guest.checked_in": "A stay was checked in.",
	"guest.checked_out": "A stay was checked out.",
	"folio.posted": "A charge was posted to a guest, company or group folio.",
	"night_audit.closed": "The night audit closed a business date.",
}
# a test event the settings screen sends to one endpoint; not subscribable
PING = "ping"

# seconds to wait before retry n (after attempt n failed)
BACKOFF = (60, 300, 1800, 7200, 21600)
MAX_ATTEMPTS = len(BACKOFF) + 1
TIMEOUT = 10  # seconds per attempt
SIGNATURE_PREFIX = "sha256="

# Reservation fields whose change is a reservation.modified
WATCHED = ("status", "check_in_date", "check_out_date", "room", "room_type",
           "sellable_unit", "adults", "children", "amount_after_tax",
           "meal_plan", "rate_plan", "guest_name", "company", "group_booking")


# ---------------------------------------------------------------------------
# signing and URL safety
# ---------------------------------------------------------------------------

def new_secret() -> str:
	return "whsec_" + secrets.token_urlsafe(32)


def sign(secret: str, timestamp: str | int, body: bytes | str) -> str:
	"""The X-Kamra-Signature value for a body sent at `timestamp`."""
	if isinstance(body, str):
		body = body.encode()
	msg = str(timestamp).encode() + b"." + body
	return SIGNATURE_PREFIX + hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def verify(secret: str, timestamp: str | int, body: bytes | str, signature: str,
           tolerance: int = 300, now: float | None = None) -> bool:
	"""Reference verifier - the same check a receiver should run."""
	try:
		age = abs((now if now is not None else time.time()) - int(timestamp))
	except (TypeError, ValueError):
		return False
	if age > tolerance:
		return False
	return hmac.compare_digest(sign(secret, timestamp, body), signature or "")


def _ip_blocked(addr: str) -> bool:
	"""Anything that isn't a plain public unicast address: private ranges,
	loopback, link-local (cloud metadata at 169.254.169.254), CGNAT,
	multicast, reserved, unspecified - and IPv4 hidden inside IPv6."""
	try:
		ip = ipaddress.ip_address(addr.split("%", 1)[0])
	except ValueError:
		return True
	if ip.version == 6 and ip.ipv4_mapped:
		ip = ip.ipv4_mapped
	return (not ip.is_global) or ip.is_multicast


def _allow_http() -> bool:
	return bool(frappe.conf.get("developer_mode")
	            or cint(frappe.conf.get("kamra_webhooks_allow_http")))


def _allow_private() -> bool:
	# local testing only (a receiver on the dev box); never set in production
	return bool(cint(frappe.conf.get("kamra_webhooks_allow_private")))


def validate_target_url(url: str | None) -> str:
	"""Refuse a URL that could be used to reach the server's own network
	(SSRF): non-HTTPS (except in developer mode), credentials in the URL,
	and any host that resolves to a non-public address. Returns the URL."""
	url = (url or "").strip()
	if not url:
		frappe.throw(_("Enter the endpoint URL."))
	if len(url) > 500:
		frappe.throw(_("The URL is too long."))
	try:
		parts = urlsplit(url)
		port = parts.port
	except ValueError:
		frappe.throw(_("That is not a valid URL."))
	scheme = (parts.scheme or "").lower()
	if scheme != "https" and not (scheme == "http" and _allow_http()):
		frappe.throw(_("Webhook URLs must use https://."))
	if parts.username or parts.password:
		frappe.throw(_("Don't put credentials in the URL - verify the signature instead."))
	host = (parts.hostname or "").strip(".").lower()
	if not host:
		frappe.throw(_("The URL has no host."))
	if _allow_private():
		return url
	if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
		frappe.throw(_("Webhooks can't be sent to internal hosts."))
	try:
		infos = socket.getaddrinfo(host, port or (443 if scheme == "https" else 80),
		                           proto=socket.IPPROTO_TCP)
	except (socket.gaierror, UnicodeError):
		frappe.throw(_("The host {0} can't be resolved.").format(host))
	addrs = {info[4][0] for info in infos}
	if not addrs or any(_ip_blocked(a) for a in addrs):
		frappe.throw(_("Webhooks can't be sent to private, loopback or internal addresses."))
	return url


def normalise_events(events) -> list[str]:
	"""A list (or newline / comma separated text) of known event names."""
	if isinstance(events, str):
		if events.strip().startswith("["):
			events = json.loads(events)
		else:
			events = events.replace(",", "\n").splitlines()
	out = []
	for e in events or []:
		e = str(e).strip()
		if not e:
			continue
		if e not in EVENTS:
			frappe.throw(_("Unknown event {0}. Use one of: {1}.").format(
				e, ", ".join(EVENTS)))
		if e not in out:
			out.append(e)
	if not out:
		frappe.throw(_("Pick at least one event."))
	return out


# ---------------------------------------------------------------------------
# emitting
# ---------------------------------------------------------------------------

def _muted() -> bool:
	f = frappe.flags
	return bool(f.in_install or f.in_migrate or f.in_patch or f.in_import
	            or f.kamra_mute_webhooks)


def _subscribers(property: str, event: str) -> list[str]:
	rows = frappe.get_all(WEBHOOK, filters={"property": property, "active": 1},
	                      fields=["name", "events"])
	return [r.name for r in rows
	        if event in (r.events or "").split("\n")]


def _queue(webhook: str, property: str, event: str, data: dict) -> str:
	envelope = {
		"id": "evt_" + uuid.uuid4().hex,
		"event": event,
		"api_version": API_VERSION,
		"created_at": now_datetime().isoformat(timespec="seconds"),
		"property": property,
		"data": data,
	}
	d = frappe.get_doc({
		"doctype": DELIVERY,
		"property": property,
		"webhook": webhook,
		"event": event,
		"event_id": envelope["id"],
		"status": "Pending",
		"attempts": 0,
		# stored exactly as sent, so every retry carries the same bytes
		"payload": json.dumps(envelope, default=str, separators=(",", ":")),
	})
	d.insert(ignore_permissions=True)
	_enqueue(d.name)
	return d.name


def _enqueue(delivery: str):
	frappe.enqueue("kamra.webhooks.deliver", queue="short", delivery=delivery,
	               enqueue_after_commit=True,
	               job_id=f"kamra-webhook-{delivery}", deduplicate=True)


def emit(event: str, property: str | None, data: dict) -> list[str]:
	"""Queue `event` for every active subscription of `property`. Never
	raises: a webhook problem must not undo a booking or a charge."""
	if event not in EVENTS or not property or _muted():
		return []
	try:
		return [_queue(name, property, event, data)
		        for name in _subscribers(property, event)]
	except Exception:
		frappe.log_error(title=f"Webhook emit failed: {event}")
		return []


# ---------------------------------------------------------------------------
# payloads - only the record itself, never contact details or IDs
# ---------------------------------------------------------------------------

def _s(v):
	return str(v) if v not in (None, "") else None


def reservation_payload(doc) -> dict:
	room_number = (frappe.db.get_value("Room", doc.room, "room_number")
	               if doc.get("room") else None)
	return {
		"reservation": doc.name,
		"status": doc.status,
		"source": doc.get("source"),
		"channel": doc.get("channel"),
		"ota_ref": doc.get("ota_ref"),
		"guest_name": doc.get("guest_name"),
		"room_type": doc.get("room_type"),
		"room": doc.get("room"),
		"room_number": room_number,
		"check_in_date": _s(doc.get("check_in_date")),
		"check_out_date": _s(doc.get("check_out_date")),
		"nights": cint(doc.get("nights")),
		"adults": cint(doc.get("adults")),
		"children": cint(doc.get("children")),
		"meal_plan": doc.get("meal_plan"),
		"rate_plan": doc.get("rate_plan"),
		"amount_after_tax": float(doc.get("amount_after_tax") or 0),
		"currency": frappe.db.get_value("Property", doc.property, "currency"),
		"company": doc.get("company"),
		"group_booking": doc.get("group_booking"),
		"actual_check_in": _s(doc.get("actual_check_in")),
		"actual_check_out": _s(doc.get("actual_check_out")),
		"cancellation_number": doc.get("cancellation_number"),
	}


def on_reservation_insert(doc, method=None):
	emit("reservation.created", doc.property, reservation_payload(doc))


def on_reservation_update(doc, method=None):
	prev = doc.get_doc_before_save()
	if not prev:  # an insert - after_insert already said "created"
		return
	changes = {f: [_s(prev.get(f)), _s(doc.get(f))] for f in WATCHED
	           if _s(prev.get(f)) != _s(doc.get(f))}
	if not changes:
		return
	event = "reservation.modified"
	if "status" in changes:
		event = {"Cancelled": "reservation.cancelled",
		         "Checked In": "guest.checked_in",
		         "Checked Out": "guest.checked_out"}.get(doc.status, event)
	data = reservation_payload(doc)
	data["changes"] = changes
	emit(event, doc.property, data)


def emit_folio_posted(folio, charge) -> list[str]:
	"""folio.posted for one charge line just saved on `folio`."""
	charge = charge if isinstance(charge, dict) else charge.as_dict()
	return emit("folio.posted", folio.property, {
		"folio": folio.name,
		"folio_type": folio.get("folio_type"),
		"reservation": charge.get("reservation") or folio.get("reservation"),
		"charge": {
			"row": charge.get("name"),
			"posting_date": _s(charge.get("posting_date")),
			"charge_type": charge.get("charge_type"),
			"description": charge.get("description"),
			"amount": float(charge.get("amount") or 0),
			"tax_rate": float(charge.get("gst_rate") or 0),
			"is_alcohol": cint(charge.get("is_alcohol")),
		},
		"balance": float(folio.get("balance") or 0),
	})


def emit_night_audit_closed(property: str, result: dict) -> list[str]:
	keys = ("audit", "status", "business_date", "next_business_date",
	        "room_charges_posted", "amount_posted", "no_shows_flagged",
	        "exceptions")
	return emit("night_audit.closed", property,
	            {k: _s(result.get(k)) if k.endswith("date") else result.get(k)
	             for k in keys})


# ---------------------------------------------------------------------------
# delivering
# ---------------------------------------------------------------------------

def _fail_or_retry(d, error: str | None, retry: bool):
	d.last_error = (error or "")[:500] or None
	if retry and cint(d.attempts) < MAX_ATTEMPTS:
		d.status = "Retrying"
		d.next_retry_at = add_to_date(now_datetime(),
		                              seconds=BACKOFF[cint(d.attempts) - 1])
	else:
		d.status = "Failed"
		d.next_retry_at = None


def deliver(delivery: str) -> dict:
	"""Send one delivery now (the background job). Updates the log row and
	the webhook's last status; schedules a retry on failure."""
	import requests

	d = frappe.get_doc(DELIVERY, delivery)
	if d.status == "Delivered":
		return {"status": d.status, "response_code": d.response_code}
	hook = frappe.db.get_value(WEBHOOK, d.webhook,
	                           ["name", "url", "active", "property"], as_dict=True)
	if not hook or not hook.active or hook.property != d.property:
		_fail_or_retry(d, "Webhook is inactive or was removed.", retry=False)
		d.save(ignore_permissions=True)
		return {"status": d.status, "response_code": None}

	from frappe.utils.password import get_decrypted_password
	secret = get_decrypted_password(WEBHOOK, hook.name, "secret",
	                                raise_exception=False)
	d.attempts = cint(d.attempts) + 1
	code = None
	error = None
	retry = True
	start = time.monotonic()
	try:
		url = validate_target_url(hook.url)  # again: DNS may have changed
		if not secret:
			raise frappe.ValidationError("Webhook has no signing secret - rotate it.")
		body = (d.payload or "{}").encode()
		ts = str(int(time.time()))
		resp = requests.post(url, data=body, timeout=TIMEOUT, allow_redirects=False,
		                     headers={
			"Content-Type": "application/json",
			"User-Agent": "Kamra-Webhooks/1",
			"X-Kamra-Event": d.event,
			"X-Kamra-Event-Id": d.event_id,
			"X-Kamra-Delivery": d.name,
			"X-Kamra-Timestamp": ts,
			"X-Kamra-Signature": sign(secret, ts, body),
		})
		code = resp.status_code
		if not 200 <= code < 300:
			error = f"HTTP {code}: {(resp.text or '')[:300]}"
	except frappe.ValidationError as e:
		error, retry = str(e), False  # a refused URL won't fix itself
	except requests.RequestException as e:
		error = f"{type(e).__name__}: {str(e)[:300]}"
	d.duration_ms = int((time.monotonic() - start) * 1000)
	d.response_code = code
	if error is None:
		d.status = "Delivered"
		d.delivered_at = now_datetime()
		d.next_retry_at = None
		d.last_error = None
	else:
		_fail_or_retry(d, error, retry)
	d.save(ignore_permissions=True)

	failures = 0 if d.status == "Delivered" else cint(
		frappe.db.get_value(WEBHOOK, hook.name, "consecutive_failures")) + 1
	frappe.db.set_value(WEBHOOK, hook.name, {
		"last_status": f"{d.status} ({code})" if code else d.status,
		"last_delivery_on": now_datetime(),
		"consecutive_failures": failures,
	}, update_modified=False)
	return {"status": d.status, "response_code": code, "attempts": d.attempts,
	        "error": d.last_error}


def retry_due():
	"""Scheduler (every minute): re-queue retries that are due, and any
	Pending row whose job was lost (a worker restart) for 10+ minutes."""
	now = now_datetime()
	due = frappe.get_all(DELIVERY, filters={"status": "Retrying",
	                                        "next_retry_at": ("<=", now)},
	                     pluck="name", limit=200, order_by="next_retry_at asc")
	stale = frappe.get_all(DELIVERY, filters={
		"status": "Pending", "attempts": 0,
		"creation": ("<", add_to_date(now, minutes=-10))},
		pluck="name", limit=200, order_by="creation asc")
	for name in due + stale:
		frappe.enqueue("kamra.webhooks.deliver", queue="short", delivery=name,
		               job_id=f"kamra-webhook-{name}", deduplicate=True)
	return len(due) + len(stale)


# ---------------------------------------------------------------------------
# managing subscriptions (Hotel Admin / System Manager)
# ---------------------------------------------------------------------------

_SCOPE = {"name": WEBHOOK, "webhook": WEBHOOK, "delivery": DELIVERY}


def _own(doctype: str, name: str, property: str | None = None):
	doc = frappe.get_doc(doctype, name)
	if property and doc.property != property:
		frappe.throw(_("That webhook belongs to another property."),
		             frappe.PermissionError)
	return doc


def _row(doc) -> dict:
	return {
		"name": doc.name, "property": doc.property, "label": doc.label,
		"url": doc.url, "active": cint(doc.active),
		"events": [e for e in (doc.events or "").split("\n") if e],
		"has_secret": bool(doc.get("secret")),
		"last_status": doc.get("last_status"),
		"last_delivery_on": _s(doc.get("last_delivery_on")),
		"consecutive_failures": cint(doc.get("consecutive_failures")),
	}


def _log(action: str, name: str, property: str, rationale: str):
	from kamra.savings import log_action
	log_action(action, WEBHOOK, name, property, rationale=rationale)


@frappe.whitelist()
@require_roles("Hotel Admin")
def webhook_events() -> list:
	"""The events a webhook can subscribe to."""
	return [{"event": k, "description": v} for k, v in EVENTS.items()]


@frappe.whitelist()
@require_roles("Hotel Admin")
def list_webhooks(property: str) -> list:
	"""This property's webhook subscriptions (never the secrets)."""
	return [_row(frappe.get_doc(WEBHOOK, n)) for n in frappe.get_all(
		WEBHOOK, filters={"property": property}, pluck="name",
		order_by="creation asc")]


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin", scope=_SCOPE)
def save_webhook(property: str, url: str, events, label: str | None = None,
                 active: int = 1, name: str | None = None) -> dict:
	"""Create or update a subscription. A new one gets a signing secret,
	returned once in `secret` - store it on the receiving side now."""
	secret = None
	if name:
		doc = _own(WEBHOOK, name, property)
	else:
		doc = frappe.new_doc(WEBHOOK)
		doc.property = property
		secret = new_secret()
		doc.secret = secret
	doc.url = url
	doc.events = "\n".join(normalise_events(events))
	doc.label = (label or "").strip()[:140] or None
	doc.active = 1 if cint(active) else 0
	doc.save(ignore_permissions=True)  # role + property checked above
	_log("webhook_saved", doc.name, property,
	     f"{'Created' if secret else 'Updated'} webhook {doc.label or ''} "
	     f"-> {doc.url} ({', '.join(doc.events.split(chr(10)))})")
	return {**_row(doc), "secret": secret}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin", scope=_SCOPE)
def rotate_webhook_secret(name: str, property: str | None = None) -> dict:
	"""Issue a new signing secret (returned once); the old one stops working."""
	doc = _own(WEBHOOK, name, property)
	secret = new_secret()
	doc.secret = secret
	doc.save(ignore_permissions=True)
	_log("webhook_secret_rotated", doc.name, doc.property,
	     f"Signing secret rotated for {doc.url}")
	return {"name": doc.name, "secret": secret}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin", scope=_SCOPE)
def delete_webhook(name: str, property: str | None = None) -> dict:
	"""Remove a subscription and its delivery log."""
	doc = _own(WEBHOOK, name, property)
	frappe.db.delete(DELIVERY, {"webhook": doc.name})
	frappe.delete_doc(WEBHOOK, doc.name, ignore_permissions=True)
	_log("webhook_deleted", doc.name, doc.property, f"Webhook to {doc.url} removed")
	return {"ok": True}


@frappe.whitelist()
@require_roles("Hotel Admin", scope=_SCOPE)
def webhook_deliveries(property: str, webhook: str | None = None,
                       status: str | None = None, limit: int = 50) -> list:
	"""The delivery log, newest first."""
	filters = {"property": property}
	if webhook:
		filters["webhook"] = webhook
	if status:
		filters["status"] = status
	return frappe.get_all(DELIVERY, filters=filters, fields=[
		"name", "webhook", "event", "event_id", "status", "attempts",
		"response_code", "duration_ms", "last_error", "next_retry_at",
		"delivered_at", "creation"],
		order_by="creation desc", limit=max(1, min(cint(limit) or 50, 200)))


@frappe.whitelist()
@require_roles("Hotel Admin", scope=_SCOPE)
def delivery_detail(delivery: str) -> dict:
	"""One delivery with the exact payload that was (or will be) sent."""
	d = frappe.get_doc(DELIVERY, delivery)
	return {k: _s(d.get(k)) if k in ("next_retry_at", "delivered_at", "creation") else d.get(k)
	        for k in ("name", "webhook", "event", "event_id", "status",
	                  "attempts", "response_code", "duration_ms", "last_error",
	                  "next_retry_at", "delivered_at", "creation", "payload")}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin", scope=_SCOPE)
def resend_delivery(delivery: str) -> dict:
	"""Send a delivery again now - same event id, so the receiver can tell
	it is the same event."""
	d = frappe.get_doc(DELIVERY, delivery)
	d.status = "Pending"
	d.next_retry_at = None
	d.save(ignore_permissions=True)
	_log("webhook_resent", d.webhook, d.property, f"Resent {d.event} ({d.event_id})")
	_enqueue(d.name)
	return {"name": d.name, "status": d.status}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin", scope=_SCOPE)
def send_test_event(name: str, property: str | None = None) -> dict:
	"""Send a signed `ping` to one endpoint right now and report the result."""
	doc = _own(WEBHOOK, name, property)
	if not doc.active:
		frappe.throw(_("Switch the webhook on first."))
	envelope_data = {"message": "Test event from Kamra - your endpoint is reachable.",
	                 "webhook": doc.name}
	d = frappe.get_doc({
		"doctype": DELIVERY, "property": doc.property, "webhook": doc.name,
		"event": PING, "event_id": "evt_" + uuid.uuid4().hex, "status": "Pending",
		"attempts": 0,
	})
	d.payload = json.dumps({"id": d.event_id, "event": PING, "api_version": API_VERSION,
	                        "created_at": now_datetime().isoformat(timespec="seconds"),
	                        "property": doc.property, "data": envelope_data},
	                       separators=(",", ":"))
	d.insert(ignore_permissions=True)
	out = deliver(d.name)
	if out["status"] == "Retrying":  # a test is one shot - don't keep retrying it
		frappe.db.set_value(DELIVERY, d.name, {"status": "Failed", "next_retry_at": None})
		out["status"] = "Failed"
		code = out.get("response_code")
		frappe.db.set_value(WEBHOOK, doc.name, "last_status",
		                    f"Failed ({code})" if code else "Failed",
		                    update_modified=False)
	return {"delivery": d.name, **out}
