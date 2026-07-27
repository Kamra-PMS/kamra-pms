"""Channex.io adapter - https://docs.channex.io

API-first channel-manager infrastructure: self-serve signup, sandbox at
staging.channex.io, per-property pricing, certified with Booking.com,
Agoda, Expedia, Airbnb and more. The hotel brings its own Channex
account; api_key is a Channex user API key, external_property_id the
Channex property id, and mappings carry Channex room_type/rate_plan ids.

Webhook: register a Channex webhook (event: booking) pointing at
/api/method/kamra.channel_manager.webhook?connection=<name>; put the
same secret on both sides.
"""

from __future__ import annotations

import frappe

DEFAULT_ENDPOINT = "https://app.channex.io/api/v1"


def _call(conn, method: str, path: str, payload=None):
	import requests

	key = conn.get_password("api_key", raise_exception=False)
	base = (conn.endpoint or DEFAULT_ENDPOINT).rstrip("/")
	res = requests.request(
		method, f"{base}/{path}",
		json=payload, headers={"user-api-key": key or ""}, timeout=20)
	ok = 200 <= res.status_code < 300
	try:
		body = res.json()
	except Exception:
		body = {"raw": res.text[:300]}
	return ok, body


def push_ari(conn, snapshot) -> tuple[bool, str]:
	"""Channex takes availability and rate values as bulk arrays."""
	availability, rates = [], []
	for rt in snapshot:
		for day in rt["days"]:
			availability.append({
				"property_id": conn.external_property_id,
				"room_type_id": rt["external_room_id"],
				"date": day["date"],
				"availability": day["available"],
			})
			if rt.get("external_rate_id"):
				rates.append({
					"property_id": conn.external_property_id,
					"rate_plan_id": rt["external_rate_id"],
					"date": day["date"],
					"rate": str(day["rate"]),
				})
	ok1, b1 = _call(conn, "POST", "availability",
	                {"values": availability})
	ok2, b2 = (True, {}) if not rates else _call(
		conn, "POST", "restrictions", {"values": rates})
	if ok1 and ok2:
		return True, f"{len(availability)} availability, {len(rates)} rate values"
	err = (b1 if not ok1 else b2)
	return False, str(err)[:280]


def parse_webhook(conn, payload) -> list[dict]:
	"""Channex booking webhook -> normalized events.

	Payload: {event: "booking", payload: {status, ota_reservation_code,
	ota_name, arrival_date, departure_date, customer{...}, rooms[...]}}
	"""
	body = payload.get("payload") or payload
	status = (body.get("status") or "new").lower()
	event = {"new": "book", "modified": "modify",
	         "cancelled": "cancel"}.get(status, "book")
	customer = body.get("customer") or {}
	out = []
	for room in body.get("rooms") or [{}]:
		days = room.get("days") or {}
		total = sum(float(v or 0) for v in days.values()) or \
			float(body.get("amount") or 0)
		occ = room.get("occupancy") or {}
		out.append({
			"event": event,
			"ota_ref": body.get("ota_reservation_code")
			           or body.get("unique_id") or "",
			"channel": body.get("ota_name") or "OTA",
			"room_type_external_id": room.get("room_type_id") or "",
			"check_in": room.get("checkin_date") or body.get("arrival_date"),
			"check_out": room.get("checkout_date") or body.get("departure_date"),
			"adults": int(occ.get("adults") or 2),
			"children": int(occ.get("children") or 0),
			"guest_name": " ".join(filter(None, [customer.get("name"),  # nosemgrep: frappe-no-functional-code -- filter(None, ...) drops empty parts; equivalent to a comprehension
			                                     customer.get("surname")]))
			              or "OTA Guest",
			"phone": customer.get("phone") or "",
			"email": customer.get("mail") or customer.get("email") or "",
			"total": total,
			"currency": body.get("currency") or "",
			"notes": body.get("notes") or "",
		})
	return out
