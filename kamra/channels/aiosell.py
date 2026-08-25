"""AioSell adapter - https://apidocs.aiosell.com/

Indian channel manager (+ revenue management) popular with budget and
mid-market properties. This adapter is transport only: it speaks AioSell's
`/api/v2/cm` wire format on both sides and hands Kamra's normalized shapes to
kamra.channel_manager, where every consequence (booking creation, availability,
pricing, the credit-note cancellation policy, the audit log) lives.

Wire format is fixed by aiosell-api-context.md:
  - Base URL   https://live.aiosell.com/api/v2/cm
  - Auth       HTTP Basic (username + password issued at partner onboarding)
  - Rate push  POST /update-rates/{pms}   {hotelCode, updates:[{startDate,
               endDate, rates:[{roomCode, rateplanCode, rate}]}]}
  - Inv push   POST /update/{pms}         {hotelCode, updates:[{startDate,
               endDate, rooms:[{roomCode, available}]}]}
  - Mapping    GET  /property_details/{hotelCode}?partnerId={pms}
  - Webhook    Aiosell POSTs book/modify/cancel to a URL WE host; we validate
               the inbound Basic-auth header, resolve the property by hotelCode.

Credentials and the {pms} slug are issued only after partner onboarding. Until
then the connection holds the `<USERNAME>` / `<PASSWORD>` / `<PMS_SLUG>`
placeholders and push_ari reports the connection as pending rather than
pretending to sync. Never hard-code or guess real values.
"""

from __future__ import annotations

import base64
import hmac
import json

import frappe

DEFAULT_BASE = "https://live.aiosell.com/api/v2/cm"
# unresolved placeholders - a connection still carrying these is not live
PLACEHOLDERS = {"", None, "<USERNAME>", "<PASSWORD>", "<PMS_SLUG>"}


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------

def _creds(conn):
	"""(username, password, pms_slug, hotel_code) for a connection, or a
	reason string if any is still a placeholder."""
	user = conn.api_username
	pwd = conn.get_password("api_key", raise_exception=False)
	pms = conn.pms_slug
	hotel = conn.external_property_id
	missing = [n for n, v in (("username", user), ("password", pwd),
	                          ("pms slug", pms), ("hotelCode", hotel))
	           if v in PLACEHOLDERS]
	if missing:
		return None, ("AioSell partner credentials pending - set the "
		              f"{', '.join(missing)} on this connection once AioSell "
		              "onboards you as a PMS partner.")
	return (user, pwd, pms, hotel), None


def _base(conn) -> str:
	return (conn.endpoint or DEFAULT_BASE).rstrip("/")


def _post(conn, path: str, payload, user: str, pwd: str):
	"""POST JSON with Basic auth. Returns (ok, body). ok is true only when
	both the HTTP status and AioSell's own `success` flag are good."""
	import requests
	from requests.auth import HTTPBasicAuth

	res = requests.post(f"{_base(conn)}/{path}", json=payload,
	                    auth=HTTPBasicAuth(user, pwd),
	                    headers={"Content-Type": "application/json"},
	                    timeout=20)
	try:
		body = res.json()
	except Exception:
		body = {"raw": res.text[:300]}
	ok = (200 <= res.status_code < 300) and bool(
		body.get("success") or body.get("status"))
	return ok, body


def _runs(days: list[dict]):
	"""Collapse a consecutive per-day series into inclusive [start, end] runs
	of equal value - AioSell pushes are upserts over a date range, so this
	turns 90 daily values into a handful of range blocks."""
	runs = []
	for d in days:
		if runs and runs[-1][2] == d["value"]:
			runs[-1][1] = d["date"]
		else:
			runs.append([d["date"], d["date"], d["value"]])
	return runs


# ---------------------------------------------------------------------------
# Push: Kamra -> AioSell
# ---------------------------------------------------------------------------

def build_push_bodies(hotel_code: str, snapshot) -> tuple[list, list]:
	"""The exact (inventory, rates) update blocks we POST to /update and
	/update-rates for `snapshot`. Split out from push_ari so it can be
	previewed without credentials - handy for showing what a sync sends."""
	inv_updates, rate_updates = [], []
	for rt in snapshot:
		room_code = rt["external_room_id"]
		rate_code = rt.get("external_rate_id")
		# availability -> /update
		for start, end, avail in _runs(
				[{"date": d["date"], "value": int(d["available"])}
				 for d in rt["days"]]):
			inv_updates.append({"startDate": start, "endDate": end,
			                    "rooms": [{"roomCode": room_code,
			                               "available": avail}]})
		# rates -> /update-rates (needs a rate plan; skip rows without one)
		if rate_code:
			for start, end, rate in _runs(
					[{"date": d["date"], "value": round(float(d["rate"]), 2)}
					 for d in rt["days"]]):
				rate_updates.append({"startDate": start, "endDate": end,
				                     "rates": [{"roomCode": room_code,
				                                "rateplanCode": rate_code,
				                                "rate": rate}]})
	return inv_updates, rate_updates


def push_ari(conn, snapshot) -> tuple[bool, str]:
	"""Push availability (/update) and rates (/update-rates) for the mapped
	room types. `snapshot` is kamra.channel_manager.ari_snapshot's shape, with
	the Villa lockout already applied to the `available` numbers."""
	creds, reason = _creds(conn)
	if not creds:
		return False, reason
	user, pwd, pms, hotel = creds

	inv_updates, rate_updates = build_push_bodies(hotel, snapshot)

	results, ok_all = [], True
	if inv_updates:
		ok, body = _post(conn, f"update/{pms}",
		                 {"hotelCode": hotel, "updates": inv_updates}, user, pwd)
		ok_all = ok_all and ok
		results.append("inv " + ("ok" if ok else str(body.get("message") or body)[:120]))
	if rate_updates:
		ok, body = _post(conn, f"update-rates/{pms}",
		                 {"hotelCode": hotel, "updates": rate_updates}, user, pwd)
		ok_all = ok_all and ok
		results.append("rates " + ("ok" if ok else str(body.get("message") or body)[:120]))
	if not results:
		return False, "No room mappings to push."
	detail = (f"{len(inv_updates)} inv + {len(rate_updates)} rate blocks; "
	          + "; ".join(results))
	return ok_all, detail[:280]


def fetch_property_details(conn) -> dict:
	"""GET /property_details - the hotel_id, room_id and rateplan_id codes to
	map Kamra's room types onto. Call this first, once per property."""
	import requests
	from requests.auth import HTTPBasicAuth

	creds, reason = _creds(conn)
	if not creds:
		frappe.throw(reason)
	user, pwd, pms, hotel = creds
	res = requests.get(f"{_base(conn)}/property_details/{hotel}",
	                   params={"partnerId": pms},
	                   auth=HTTPBasicAuth(user, pwd), timeout=20)
	res.raise_for_status()
	return res.json()


# ---------------------------------------------------------------------------
# Webhook: AioSell -> Kamra
# ---------------------------------------------------------------------------

def parse_webhook(conn, payload) -> list[dict]:
	"""AioSell reservation webhook -> Kamra's normalized events.

	book/modify carry the full booking state (rooms[]); cancel carries only
	bookingId. One event per room line; ota_ref is the bookingId for a
	single-room booking, "bookingId-<n>" for each line of a multi-room one, so
	each line is its own idempotent reservation and cancel can still reach the
	whole set via booking_id."""
	action = (payload.get("action") or "book").lower()
	event = "cancel" if "cancel" in action else (
		"modify" if "modif" in action else "book")
	booking_id = str(payload.get("bookingId") or "")
	channel = payload.get("channel") or "OTA"

	if event == "cancel":
		return [{"event": "cancel", "booking_id": booking_id,
		         "ota_ref": booking_id, "channel": channel}]

	guest = payload.get("guest") or {}
	gname = " ".join(p for p in (guest.get("firstName"),
	                             guest.get("lastName")) if p).strip()
	amount = payload.get("amount") or {}
	rooms = payload.get("rooms") or []
	multi = len(rooms) > 1

	out = []
	for i, room in enumerate(rooms):
		occ = room.get("occupancy") or {}
		prices = room.get("prices") or []
		# single-room: use the booking's tax-inclusive total; multi-room: best
		# per-room signal is the sum of its nightly sell rates.
		if multi:
			total = sum(float(p.get("sellRate") or 0) for p in prices)
		else:
			total = float(amount.get("amountAfterTax") or 0)
		out.append({
			"event": event,
			"booking_id": booking_id,
			"ota_ref": f"{booking_id}-{i}" if multi else booking_id,
			"channel": channel,
			"room_type_external_id": str(room.get("roomCode") or ""),
			"external_rate_id": room.get("rateplanCode"),
			"check_in": payload.get("checkin"),
			"check_out": payload.get("checkout"),
			"adults": int(occ.get("adults") or 2),
			"children": int(occ.get("children") or 0),
			"guest_name": room.get("guestName") or gname or "OTA Guest",
			"phone": guest.get("phone") or "",
			"email": guest.get("email") or "",
			"total": total,
			"currency": amount.get("currency") or "INR",
			"notes": payload.get("specialRequests") or "",
		})
	return out


def _connection_for(hotel_code: str):
	name = frappe.db.get_value(
		"Channel Manager Connection",
		{"provider": "AioSell", "external_property_id": hotel_code, "active": 1},
		"name")
	return frappe.get_doc("Channel Manager Connection", name) if name else None


WEBHOOK_PATH = "/api/method/kamra.channels.aiosell.reservation_webhook"


def preserve_webhook_auth():
	"""`before_request` hook (runs BEFORE Frappe's own auth check).

	Frappe reserves the `Authorization: Basic` header for its own api-key login
	and rejects anything that isn't a valid Frappe key - before allow_guest
	endpoints run. AioSell authenticates its webhook with Basic auth (the
	partner username/password we set), which is NOT a Frappe api key, so Frappe
	would 401 the call before our webhook ever sees it.

	For our webhook path only, stash the header and strip it from the request so
	Frappe treats the call as guest; reservation_webhook then validates the
	stashed credentials itself against the Channel Manager Connection."""
	req = getattr(frappe.local, "request", None)
	if not req or getattr(req, "path", None) != WEBHOOK_PATH:
		return
	auth = req.headers.get("Authorization")
	if auth and auth.startswith("Basic "):
		frappe.local.flags.aiosell_webhook_auth = auth
		# request.headers is read-only; drop it from the WSGI environ so
		# frappe.get_request_header("Authorization") returns None downstream.
		req.environ.pop("HTTP_AUTHORIZATION", None)


def _auth_ok(conn) -> bool:
	"""Constant-time-validate the inbound Basic-auth header against the
	connection's stored credentials. Reads the header preserved by
	preserve_webhook_auth (Frappe strips it during its own auth), falling back
	to the live header for direct calls / tests."""
	header = getattr(frappe.local.flags, "aiosell_webhook_auth", None) \
		or (frappe.get_request_header("Authorization") if frappe.request else None)
	if not header or not header.startswith("Basic "):
		return False
	try:
		user, _, pwd = base64.b64decode(header[6:]).decode("utf-8").partition(":")
	except Exception:
		return False
	exp_user = conn.api_username or ""
	exp_pwd = conn.get_password("api_key", raise_exception=False) or ""
	return (hmac.compare_digest(user, exp_user)
	        and hmac.compare_digest(pwd, exp_pwd))


@frappe.whitelist(allow_guest=True, methods=["POST"])
def reservation_webhook(**kwargs):
	"""The single URL we host and hand to AioSell at onboarding:
	/api/method/kamra.channels.aiosell.reservation_webhook

	One endpoint for book / modify / cancel, differentiated by `action` and
	routed to a property by `hotelCode`. Validates Basic auth, answers
	instantly, and does the real work off the request path so AioSell never
	times out and retries."""
	try:
		payload = json.loads(frappe.request.data or b"{}") \
			if frappe.request and frappe.request.data else dict(kwargs)
	except Exception:
		payload = dict(kwargs)

	conn = _connection_for(payload.get("hotelCode"))
	if not conn or not _auth_ok(conn):
		# same answer for unknown hotel and bad credentials - don't leak which
		frappe.throw("Unauthorized", frappe.AuthenticationError)

	frappe.logger("aiosell", allow_site=True).info({
		"connection": conn.name, "action": payload.get("action"),
		"bookingId": payload.get("bookingId"), "hotelCode": payload.get("hotelCode"),
	})
	frappe.enqueue("kamra.channel_manager.process_webhook_events",
	               queue="short", enqueue_after_commit=True,
	               connection=conn.name, payload=payload)
	return {"success": True, "message": "Reservation received"}
