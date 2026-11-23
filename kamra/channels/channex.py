"""Channex.io adapter - https://docs.channex.io

API-first channel-manager infrastructure: self-serve signup, sandbox at
staging.channex.io, per-property pricing, certified with Booking.com,
Agoda, Expedia, Airbnb and more. The hotel brings its own Channex
account; api_key is a Channex user API key, external_property_id the
Channex property id, and mappings carry Channex room_type/rate_plan ids.

Webhook: register a Channex webhook (event: booking) pointing at
/api/method/kamra.channel_manager.webhook?connection=<name>; put the
same secret on both sides.

Availability and rates go out through the ARI outbox (kamra.channel_ari):
only what changed, as date ranges, one call per endpoint, under Channex's
rate limit.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

DEFAULT_ENDPOINT = "https://app.channex.io/api/v1"


class ChannexError(Exception):
	"""A non-2xx answer from Channex. detail is short (<= 300 characters) and
	never the whole body."""

	def __init__(self, status: int, detail: str):
		self.status = status
		self.detail = str(detail or "")[:300]
		super().__init__(f"Channex {status}: {self.detail}")


class ChannexRateLimited(ChannexError):
	"""429: wait retry_after seconds (Retry-After; 60 when missing)."""

	def __init__(self, status: int, detail: str, retry_after: int = 60):
		super().__init__(status, detail)
		self.retry_after = retry_after


def _retry_after(value) -> int:
	try:
		seconds = int(str(value).strip())
	except (TypeError, ValueError):
		return 60
	return seconds if seconds > 0 else 60


def _send(conn, method: str, path: str, *, params: dict | None = None,
          payload=None) -> tuple[dict, dict]:
	"""One call to the Channex API: (the JSON of a 2xx, its headers with
	lower-case names). ChannexRateLimited on a 429, ChannexError on anything
	else; a timeout or a dropped connection is ChannexError(0, ...)."""
	import requests

	key = conn.get_password("api_key", raise_exception=False)
	base = (conn.endpoint or DEFAULT_ENDPOINT).rstrip("/")
	try:
		res = requests.request(
			method, f"{base}/{path}", params=params, json=payload,
			headers={"user-api-key": key or ""}, timeout=20)
	except (requests.Timeout, requests.ConnectionError) as exc:
		raise ChannexError(0, f"{type(exc).__name__}: {exc}") from None
	headers = {str(k).lower(): v for k, v in (res.headers or {}).items()}
	if 200 <= res.status_code < 300:
		try:
			return res.json(), headers
		except ValueError:
			return {}, headers
	try:
		body = res.json()
		detail = str(body.get("errors") or body) if isinstance(body, dict) else str(body)
	except ValueError:
		detail = res.text or ""
	if res.status_code == 429:
		raise ChannexRateLimited(429, detail, _retry_after(headers.get("retry-after")))
	raise ChannexError(res.status_code, detail)


def _request(conn, method: str, path: str, *, params: dict | None = None,
             payload=None) -> dict:
	"""One call to the Channex API: the JSON of a 2xx, ChannexRateLimited on a
	429, ChannexError on anything else."""
	return _send(conn, method, path, params=params, payload=payload)[0]


def rate_limit_wait(headers: dict) -> int:
	"""Seconds to hold back according to the `RateLimit` header
	("<name>";r=<remaining>;t=<seconds>, ...): the longest t among the
	entries with nothing remaining, 0 when every one has some left. Names
	change, so it is read generically; a header that does not parse is 0."""
	wait = 0
	for entry in str((headers or {}).get("ratelimit") or "").split(","):
		fields = {}
		for part in entry.split(";")[1:]:
			key, _, value = part.strip().partition("=")
			fields[key] = value
		try:
			remaining, seconds = int(fields["r"]), int(fields["t"])
		except (KeyError, ValueError):
			continue
		if remaining <= 0:
			wait = max(wait, seconds)
	return wait


def _attributes(item: dict) -> dict:
	return dict(item.get("attributes") or {}, id=item.get("id"))


_ARI_ID_FIELD = {"availability": "room_type_id", "restrictions": "rate_plan_id"}


def _ari_value(field: str, value):
	if field == "rate":
		# a decimal string: Channex refuses a bare float with decimals
		return str(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
	if field == "availability":
		return int(value)
	return value


def _change_key(id_field: str, obj: dict) -> tuple:
	return (str(obj.get(id_field)), obj.get("date"), obj.get("date_from"), obj.get("date_to"))


def push_ari_changes(conn, kind: str, changes: list[dict]) -> dict:
	"""Send ARI changes, in the order given, in ONE call: kind is
	"availability" or "restrictions", changes the output of
	channel_ari.compress ({external_id, date | date_from + date_to, values}).
	Returns {"task_ids", "rejected": [change + "reasons": {field: [why]}],
	"wait": seconds the RateLimit header asks to hold back}. A rejected value
	does not fail the call: Channex applies the others and lists it under
	meta.warnings. ChannexRateLimited on a 429, ChannexError otherwise."""
	id_field = _ARI_ID_FIELD[kind]
	values, by_key = [], {}
	for change in changes:
		obj = {"property_id": conn.external_property_id, id_field: change["external_id"]}
		if change.get("date"):
			obj["date"] = change["date"]
		else:
			obj["date_from"], obj["date_to"] = change["date_from"], change["date_to"]
		for field, value in (change.get("values") or {}).items():
			obj[field] = _ari_value(field, value)
		values.append(obj)
		by_key.setdefault(_change_key(id_field, obj), change)
	body, headers = _send(conn, "POST", kind, payload={"values": values})
	rejected = []
	for warning in (body.get("meta") or {}).get("warnings") or []:
		change = by_key.get(_change_key(id_field, warning)) or {
			"external_id": warning.get(id_field), "date": warning.get("date"),
			"date_from": warning.get("date_from"), "date_to": warning.get("date_to"), "values": {}}
		rejected.append(dict(change, reasons=warning.get("warning") or {}))
	return {"task_ids": [d.get("id") for d in body.get("data") or [] if d.get("id")],
	        "rejected": rejected, "wait": rate_limit_wait(headers)}


def _all_pages(conn, path: str, params: dict) -> list[dict]:
	items, page = [], 1
	while True:
		body = _request(conn, "GET", path, params=dict(
			params, **{"pagination[page]": page, "pagination[limit]": 100}))
		data = body.get("data") or []
		items += data
		total = (body.get("meta") or {}).get("total")
		if len(data) < 100 or (total is not None and len(items) >= int(total)):
			return items
		page += 1


def fetch_property_details(conn) -> dict:
	"""The property, its room types and their rate plans, for the mapping
	import: {hotel_id, hotel_name, currency, timezone, per_rate_plan: True,
	rooms: [{room_id, room_name, count_of_rooms, rateplans: [{rateplan_id,
	rateplan_name, sell_mode, currency}]}]}. Channex prices each rate plan, so
	the import maps one Kamra plan to each."""
	pid = conn.external_property_id
	prop = _attributes(_request(conn, "GET", f"properties/{pid}").get("data") or {})
	scope = {"filter[property_id]": pid}
	rooms, by_id = [], {}
	for item in _all_pages(conn, "room_types", scope):
		attrs = item.get("attributes") or {}
		room = {"room_id": str(item.get("id")), "room_name": attrs.get("title"),
		        "count_of_rooms": attrs.get("count_of_rooms"), "rateplans": []}
		rooms.append(room)
		by_id[room["room_id"]] = room
	for item in _all_pages(conn, "rate_plans", scope):
		attrs = item.get("attributes") or {}
		room_id = (((item.get("relationships") or {}).get("room_type") or {}).get("data") or {}).get("id")
		room = by_id.get(str(room_id))
		if room is None:
			continue
		room["rateplans"].append({"rateplan_id": str(item.get("id")), "rateplan_name": attrs.get("title"),
		                          "sell_mode": attrs.get("sell_mode"), "currency": attrs.get("currency")})
	return {"hotel_id": prop.get("id") or pid, "hotel_name": prop.get("title"),
	        "currency": prop.get("currency"), "timezone": prop.get("timezone"),
	        "per_rate_plan": True, "rooms": rooms}


def push_ari(conn, snapshot) -> tuple[bool, str]:
	"""The seam's whole-snapshot push, as ranges, in two calls at most (one
	availability, one restrictions). Channex connections normally go through
	the outbox (kamra.channel_ari), which sends only what changed."""
	from kamra.channel_ari import compress
	availability, rates = {}, {}
	for rt in snapshot:
		room = availability.setdefault(rt["external_room_id"], {})
		for d in rt["days"]:
			room[d["date"]] = {"availability": d["available"]}
			if rt.get("external_rate_id") and float(d.get("rate") or 0) > 0:
				rates.setdefault(rt["external_rate_id"], {})[d["date"]] = {"rate": d["rate"]}
	sent = {}
	try:
		for kind, cells in (("availability", availability), ("restrictions", rates)):
			changes = compress(cells)
			if changes:
				push_ari_changes(conn, kind, changes)
				sent[kind] = sum(len(c) for c in cells.values())
	except ChannexError as exc:
		return False, exc.detail[:280] or str(exc)[:280]
	return True, f"{sent.get('availability', 0)} availability, {sent.get('restrictions', 0)} rate values"


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
			"nightly": [{"date": k, "amount": float(v or 0)} for k, v in sorted(days.items())],
			"currency": body.get("currency") or "",
			"notes": body.get("notes") or "",
		})
	return out
