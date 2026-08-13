"""AioSell adapter - https://aiosell.com/connect-to-aiosell/

Indian channel manager (+ revenue management) popular with budget and
mid-market properties; offers a whitelabel/connect API for PMSs: the PMS
pushes rates + inventory as JSON, bookings arrive on a webhook. Exact
endpoint paths and payload field names are issued when AioSell enables a
PMS partner account, so this adapter keeps the transport in one place
(_push) with Kamra's normalized shapes on either side - finishing it is
a field-name exercise against their partner doc, not a redesign.

Until partner credentials exist, push_ari reports the connection as
pending rather than pretending to sync.
"""

from __future__ import annotations


DEFAULT_ENDPOINT = "https://live.aiosell.com/api/v1/pms"


def _push(conn, path: str, payload):
	import requests

	key = conn.get_password("api_key", raise_exception=False)
	base = (conn.endpoint or DEFAULT_ENDPOINT).rstrip("/")
	res = requests.post(f"{base}/{path}", json=payload,
	                    headers={"Authorization": f"Bearer {key or ''}"},
	                    timeout=20)
	ok = 200 <= res.status_code < 300
	try:
		body = res.json()
	except Exception:
		body = {"raw": res.text[:300]}
	return ok, body


def push_ari(conn, snapshot) -> tuple[bool, str]:
	if not (conn.endpoint or conn.get_password("api_key",
	                                           raise_exception=False)):
		return False, ("AioSell partner credentials pending - ask AioSell "
		               "for PMS connect access, then set the API key and "
		               "endpoint on this connection.")
	updates = []
	for rt in snapshot:
		updates.append({
			"hotelCode": conn.external_property_id,
			"roomCode": rt["external_room_id"],
			"rateplanCode": rt.get("external_rate_id") or None,
			"updates": [{"date": d["date"], "available": d["available"],
			             "rate": d["rate"]} for d in rt["days"]],
		})
	ok, body = _push(conn, "update-inventory", {"updates": updates})
	return (True, f"{sum(len(u['updates']) for u in updates)} day-values") \
		if ok else (False, str(body)[:280])


def parse_webhook(conn, payload) -> list[dict]:
	"""AioSell booking push -> normalized events. Field names follow their
	reservation JSON (hotelCode/bookingId/rooms[]); tolerant of case."""
	action = (payload.get("action") or payload.get("status") or "book").lower()
	event = "cancel" if "cancel" in action else (
		"modify" if "modif" in action else "book")
	guest = payload.get("guest") or {}
	out = []
	for room in payload.get("rooms") or [payload]:
		out.append({
			"event": event,
			"ota_ref": str(payload.get("bookingId")
			               or payload.get("booking_id") or ""),
			"channel": payload.get("channel") or payload.get("source")
			           or "OTA",
			"room_type_external_id": str(room.get("roomCode")
			                             or room.get("room_code") or ""),
			"check_in": room.get("checkin") or payload.get("checkin"),
			"check_out": room.get("checkout") or payload.get("checkout"),
			"adults": int(room.get("adults") or 2),
			"children": int(room.get("children") or 0),
			"guest_name": guest.get("name") or payload.get("guestName")
			              or "OTA Guest",
			"phone": guest.get("phone") or "",
			"email": guest.get("email") or "",
			"total": float(payload.get("amount")
			               or payload.get("totalAmount") or 0),
			"currency": payload.get("currency") or "INR",
			"notes": payload.get("specialRequests") or "",
		})
	return out
