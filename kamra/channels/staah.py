"""STAAH adapter - https://www.staah.com (SU/connectivity API)

The name Indian and SEA mid-market hotels already know. STAAH's PMS
connectivity runs through their partner program (XML-based SU API for
rates/inventory, reservation delivery by push or pull); credentials and
the exact DTD arrive with partner onboarding. As with AioSell, the
transport lives in one function and both sides of it speak Kamra's
normalized shapes - activating this adapter is a mapping exercise
against the partner doc.
"""

from __future__ import annotations


DEFAULT_ENDPOINT = "https://sua.staah.net/PMSService"


def push_ari(conn, snapshot) -> tuple[bool, str]:
	if not (conn.endpoint or conn.get_password("api_key",
	                                           raise_exception=False)):
		return False, ("STAAH partner credentials pending - join their "
		               "connectivity partner program, then set the API key "
		               "and endpoint on this connection.")
	import requests

	# SU API: one XML document per room/rate with date-range updates
	key = conn.get_password("api_key", raise_exception=False)
	parts = []
	for rt in snapshot:
		for d in rt["days"]:
			parts.append(
				f'<AvailRateUpdate><HotelCode>{conn.external_property_id}'
				f"</HotelCode><RoomCode>{rt['external_room_id']}</RoomCode>"
				f"<RateCode>{rt.get('external_rate_id') or ''}</RateCode>"
				f"<Date>{d['date']}</Date><Avail>{d['available']}</Avail>"
				f"<Rate>{d['rate']}</Rate></AvailRateUpdate>")
	xml = ("<?xml version=\"1.0\"?><AvailRateUpdateRQ>"
	       + "".join(parts) + "</AvailRateUpdateRQ>")
	try:
		res = requests.post(
			conn.endpoint or DEFAULT_ENDPOINT, data=xml,
			headers={"Content-Type": "application/xml",
			         "Authorization": f"Bearer {key or ''}"}, timeout=25)
		if 200 <= res.status_code < 300:
			return True, f"{len(parts)} day-values"
		return False, f"HTTP {res.status_code}: {res.text[:200]}"
	except Exception as exc:
		return False, str(exc)[:280]


def parse_webhook(conn, payload) -> list[dict]:
	"""STAAH reservation push (JSON form) -> normalized events."""
	status = (payload.get("status") or "confirmed").lower()
	event = "cancel" if "cancel" in status else (
		"modify" if "modif" in status else "book")
	out = []
	for room in payload.get("rooms") or [payload]:
		out.append({
			"event": event,
			"ota_ref": str(payload.get("reservationId")
			               or payload.get("booking_ref") or ""),
			"channel": payload.get("channelName") or "OTA",
			"room_type_external_id": str(room.get("roomCode") or ""),
			"check_in": room.get("checkIn") or payload.get("checkIn"),
			"check_out": room.get("checkOut") or payload.get("checkOut"),
			"adults": int(room.get("adults") or 2),
			"children": int(room.get("children") or 0),
			"guest_name": payload.get("guestName") or "OTA Guest",
			"phone": payload.get("guestPhone") or "",
			"email": payload.get("guestEmail") or "",
			"total": float(payload.get("totalAmount") or 0),
			"currency": payload.get("currency") or "",
			"notes": payload.get("remarks") or "",
		})
	return out
