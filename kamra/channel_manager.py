"""Channel-manager core: what gets synced and how OTA bookings land.

Providers (kamra/channels/*) translate protocol; everything with
consequences lives here so an OTA booking obeys exactly the rules a
front-desk booking does - capacity, double-booking guard, pricing on
our side of the ledger, the audit log.

Sync model: availability + rates per (room type, day) pushed to the
provider on demand, on a schedule (hourly cron), and after any booking
lands. Bookings arrive on one webhook per connection; modifications
and cancellations match on the OTA's own reference (Reservation.ota_ref).
"""

from __future__ import annotations

import json

import frappe
from frappe.utils import add_days, nowdate

from kamra.authz import require_roles
from kamra.channels import provider_for


def _connections(property: str | None = None, only_active=True):
	filters = {}
	if property:
		filters["property"] = property
	if only_active:
		filters["active"] = 1
	return frappe.get_all("Channel Manager Connection", filters=filters,
	                      pluck="name")


def _mappings(connection: str) -> list[dict]:
	return frappe.get_all(
		"Channel Room Mapping", filters={"connection": connection},
		fields=["room_type", "external_room_id", "external_rate_id"])


def _sellable(property: str, room_type: str, check_in, check_out) -> int:
	"""Rooms of a type actually sellable for [check_in, check_out): physical
	rooms (not out of order) minus every overlapping confirmed/checked-in
	reservation of that type - ASSIGNED OR NOT - minus unpicked group holds.

	Counting unassigned reservations is the point: an OTA booking arrives
	without a room number, and it must still lower what we offer the OTAs, or
	the same room sells twice. (The front-desk availability query is a separate
	path and is unchanged.)"""
	from kamra.api import _block_hold
	total = frappe.db.count("Room", {
		"property": property, "room_type": room_type,
		"housekeeping_status": ("!=", "Out of Order")})
	booked = frappe.db.sql(
		"""SELECT COUNT(*) FROM `tabReservation`
		   WHERE property = %(p)s AND room_type = %(rt)s
		     AND status IN ('Confirmed', 'Checked In')
		     AND check_in_date < GREATEST(%(co)s,
		                                  DATE_ADD(%(ci)s, INTERVAL 1 DAY))
		     AND GREATEST(check_out_date,
		                  DATE_ADD(check_in_date, INTERVAL 1 DAY)) > %(ci)s""",
		{"p": property, "rt": room_type, "ci": check_in, "co": check_out},
	)[0][0]
	hold = _block_hold(property, room_type, check_in, check_out) or 0
	return max(0, int(total) - int(booked) - int(hold))


def ari_snapshot(property: str, connection: str, days: int = 90) -> list[dict]:
	"""Availability + rate per mapped room type per day, in the seam's
	normalized shape. Availability comes from the same engine the
	double-booking guard uses; the rate is the pricing engine's one-night
	sell rate (base occupancy, demand premiums and hurdle floors applied)."""
	from kamra.api import _available_rooms_raw, _block_hold
	from kamra.pricing import quote
	from kamra.siu.availability import capacity_by_night, has_active_sius

	mappings = _mappings(connection)
	# room_category + physical room count per mapped room type - needed by the
	# villa lockout to know which rows are the whole-property bundle and when a
	# room type is fully free.
	meta = {m.room_type: {
		"category": frappe.db.get_value("Room Type", m.room_type,
		                                "room_category"),
		"total": frappe.db.count("Room", {"room_type": m.room_type}),
	} for m in mappings}

	out = []
	start = nowdate()
	end = add_days(start, days)
	for m in mappings:
		row = {"room_type": m.room_type,
		       "external_room_id": m.external_room_id,
		       "external_rate_id": m.external_rate_id, "days": []}
		use_siu = has_active_sius(property, m.room_type)
		siu_caps = (
			capacity_by_night(property, m.room_type, start, end)
			if use_siu else []
		)
		for i in range(days):
			d = add_days(start, i)
			d2 = add_days(d, 1)
			hold = _block_hold(property, m.room_type, d, d2)
			if use_siu:
				base = siu_caps[i] if i < len(siu_caps) else 0
				avail = max(0, base - (hold or 0))
			else:
				free = _available_rooms_raw(property, m.room_type, d, d2)
				avail = max(0, len(free) - (hold or 0))
			rate = 0.0
			try:
				q = quote(property, m.room_type, str(d), str(d2), 2, 0)
				rate = float(q["nightly"][0]["rate"])
			except Exception:
				pass  # keep availability for the day even when the rate cannot be quoted
			row["days"].append({"date": str(d), "available": avail,
			                    "rate": round(rate, 2)})
		out.append(row)
	_apply_villa_lockout(out, meta)
	return out


def _apply_villa_lockout(rows: list[dict], meta: dict) -> None:
	"""Push-side Villa<->Room lockout (mutates `rows` in place).

	An Entire-Property (Villa-category) unit and its member rooms cannot both
	sell the same night, so per day:
	  - a member room is booked  -> the villa pushes 0 available
	  - the villa is booked       -> every member room pushes 0 available

	This complements - it does NOT replace - the write-time guard in
	Reservation.validate_villa_lockout; that one stops Kamra accepting a
	conflicting booking, this one stops OTAs ever showing it. A property with
	no Villa-category room type mapped is a no-op (unchanged behavior)."""
	villa_rts = [rt for rt, mm in meta.items() if mm["category"] == "Villa"]
	member_rts = [rt for rt, mm in meta.items() if mm["category"] != "Villa"]
	if not villa_rts or not member_rts:
		return
	by_rt = {r["room_type"]: r for r in rows}
	ndays = len(rows[0]["days"]) if rows else 0
	for i in range(ndays):
		villa_sold = any(
			by_rt[rt]["days"][i]["available"] < (meta[rt]["total"] or 0)
			for rt in villa_rts if rt in by_rt)
		members_all_free = all(
			by_rt[rt]["days"][i]["available"] >= (meta[rt]["total"] or 0)
			for rt in member_rts if rt in by_rt)
		if not members_all_free:
			for rt in villa_rts:
				if rt in by_rt:
					by_rt[rt]["days"][i]["available"] = 0
		if villa_sold:
			for rt in member_rts:
				if rt in by_rt:
					by_rt[rt]["days"][i]["available"] = 0


@frappe.whitelist()
@require_roles("Revenue Manager", "Hotel Admin", "Kamra Agent")
def push_ari(connection: str, days: int | None = None):
	"""Push availability + rates for one connection, now."""
	conn = frappe.get_doc("Channel Manager Connection", connection)
	if not conn.active:
		frappe.throw("This connection is not active.")
	snapshot = ari_snapshot(conn.property, connection,
	                        int(days or conn.sync_days or 90))
	if not snapshot:
		frappe.throw("No room mappings yet - map your room types to the "
		             "provider's room/rate ids first.")
	ok, detail = provider_for(conn.provider).push_ari(conn, snapshot)
	frappe.db.set_value("Channel Manager Connection", connection, {
		"last_push": frappe.utils.now_datetime(),
		"last_push_status": ("OK: " if ok else "FAILED: ") + detail[:130],
	}, update_modified=False)
	from kamra.savings import log_action
	log_action("channel.ari_push", "Channel Manager Connection", connection,
	           conn.property,
	           rationale=f"{conn.provider}: {'pushed' if ok else 'failed'} "
	                     f"- {detail[:160]}",
	           channel="API")
	if not ok:
		frappe.throw(f"{conn.provider} rejected the push: {detail}")
	return {"ok": True, "detail": detail}


def push_all_ari(property: str | None = None):
	"""Hourly cron (and the post-change trigger): keep active connections
	fresh. Best-effort per connection - one provider being down never blocks
	the others. Pass `property` to scope the push to one property."""
	for name in _connections(property):
		try:
			push_ari(name)
		except Exception:
			frappe.log_error(title=f"ARI push failed: {name}")


def enqueue_property_push(property: str | None) -> None:
	"""Pipeline 1 trigger: after any availability or rate change, fan the new
	numbers out to this property's OTAs. After-commit so it runs on the
	saved state, and fully swallowed so a channel hiccup can never block or
	fail the booking / rate write that triggered it."""
	try:
		if not property or not _connections(property):
			return
		frappe.enqueue("kamra.channel_manager.push_all_ari", queue="long",
		               enqueue_after_commit=True, property=property)
	except Exception:
		frappe.log_error(title="enqueue_property_push failed")


def on_reservation_change(doc, method=None):
	"""doc_event on Reservation: any insert/update/cancel moves availability,
	so refresh the channel side. The lockout + push run through the same
	ari_snapshot as everything else, so a direct front-desk villa/room
	booking tightens OTA inventory exactly like an OTA one does."""
	enqueue_property_push(getattr(doc, "property", None))


# ---------------------------------------------------------------------------
# Inbound bookings
# ---------------------------------------------------------------------------


@frappe.whitelist(allow_guest=True, methods=["POST"])
def webhook(connection: str, **kwargs):
	"""One URL per connection:
	/api/method/kamra.channel_manager.webhook?connection=CMC-00001
	Authenticated by the connection's webhook secret (X-Webhook-Secret
	header or `secret` in the payload)."""
	conn = frappe.get_doc("Channel Manager Connection", connection)
	if not conn.active:
		return {"ok": False, "reason": "connection_inactive"}
	secret = conn.get_password("webhook_secret", raise_exception=False)
	sent = (frappe.get_request_header("X-Webhook-Secret")
	        if frappe.request else None) or kwargs.get("secret")
	if secret and sent != secret:
		frappe.throw("Webhook secret mismatch.", frappe.PermissionError)

	try:
		payload = json.loads(frappe.request.data or b"{}") \
			if frappe.request else dict(kwargs)
	except Exception:
		payload = dict(kwargs)

	events = provider_for(conn.provider).parse_webhook(conn, payload)
	results = [_apply_event(conn, e) for e in events]
	return {"ok": True, "results": results}


def _room_type_for(connection: str, external_id: str) -> str | None:
	return frappe.db.get_value(
		"Channel Room Mapping",
		{"connection": connection, "external_room_id": external_id},
		"room_type")


def _find_or_create_guest(name: str, phone: str, email: str) -> str:
	for filt in ({"phone": phone} if phone else None,
	             {"email": email} if email else None):
		if filt:
			g = frappe.db.get_value("Guest", filt)
			if g:
				return g
	parts = (name or "OTA Guest").split(" ", 1)
	return frappe.get_doc({
		"doctype": "Guest", "first_name": parts[0],
		"last_name": parts[1] if len(parts) > 1 else "",
		"phone": phone or "", "email": email or "",
	}).insert(ignore_permissions=True).name


def _reservations_for_booking(property: str, booking_id: str) -> list[dict]:
	"""Every Kamra reservation for one OTA booking: the single-room case
	(ota_ref == bookingId) and each line of a multi-room booking
	(ota_ref == "bookingId-<n>"). A cancel payload carries only the base
	bookingId, so it must reach all of them."""
	if not booking_id:
		return []
	return frappe.db.sql(
		"""SELECT name, status, ota_ref FROM `tabReservation`
		   WHERE property = %(p)s
		     AND (ota_ref = %(b)s OR ota_ref LIKE %(bl)s)""",
		{"p": property, "b": booking_id, "bl": booking_id + "-%"},
		as_dict=True)


def _apply_event(conn, e: dict) -> dict:
	"""One normalized OTA event -> the same paths a human would take."""
	existing = frappe.db.get_value(
		"Reservation", {"property": conn.property, "ota_ref": e["ota_ref"]},
		["name", "status"], as_dict=True) if e.get("ota_ref") else None

	if e["event"] == "cancel":
		# A cancel frees the room(s) and - per the property's cancellation
		# policy, which carries no OTA exception - issues a 6-month credit
		# note instead of a cash refund. Reuse the exact front-desk path.
		from kamra.api import _do_cancel
		rows = _reservations_for_booking(
			conn.property, e.get("booking_id") or e.get("ota_ref"))
		if not rows:
			return {"ota_ref": e.get("ota_ref"), "result": "cancel_unmatched"}
		cancelled, vouchers = [], []
		for r in rows:
			if r.status != "Confirmed":
				continue  # idempotent: already cancelled / checked out
			res = frappe.get_doc("Reservation", r.name)
			out = _do_cancel(
				res, reason="Booked elsewhere",
				note=f"Cancelled by {e.get('channel') or 'OTA'} "
				     f"({e.get('booking_id') or e.get('ota_ref')})",
				issue_credit_note=1)
			cancelled.append(r.name)
			if out.get("credit_note_voucher"):
				vouchers.append(out["credit_note_voucher"])
		return {"ota_ref": e.get("ota_ref"),
		        "result": "cancelled" if cancelled else "already_cancelled",
		        "reservations": cancelled, "credit_notes": vouchers}

	room_type = _room_type_for(conn.name, e.get("room_type_external_id"))
	if not room_type:
		return {"ota_ref": e.get("ota_ref"), "result": "unmapped_room",
		        "external_room_id": e.get("room_type_external_id")}

	if e["event"] == "modify" and existing:
		# A modify payload is the full new state - overwrite the record, never
		# merge. Room type can change too (guest moved to a different category).
		doc = frappe.get_doc("Reservation", existing.name)
		doc.room_type = room_type
		doc.check_in_date = e["check_in"]
		doc.check_out_date = e["check_out"]
		doc.adults = e.get("adults") or 2
		doc.children = e.get("children") or 0
		doc.special_requests = e.get("notes") or None
		doc.auto_price = 0 if e.get("total") else 1
		if e.get("total"):
			doc.amount_after_tax = e["total"]
		doc.save(ignore_permissions=True)
		return {"ota_ref": e["ota_ref"], "result": "modified",
		        "reservation": existing.name}

	if existing:
		return {"ota_ref": e["ota_ref"], "result": "duplicate_ignored",
		        "reservation": existing.name}

	guest = _find_or_create_guest(e.get("guest_name"), e.get("phone"),
	                              e.get("email"))
	doc = frappe.get_doc({
		"doctype": "Reservation",
		"property": conn.property,
		"guest": guest,
		"room_type": room_type,
		"check_in_date": e["check_in"],
		"check_out_date": e["check_out"],
		"adults": e.get("adults") or 2,
		"children": e.get("children") or 0,
		"source": "OTA",
		"channel": e.get("channel"),
		"ota_ref": e.get("ota_ref"),
		"special_requests": e.get("notes") or None,
		# the OTA already sold at its price - keep their number, don't reprice
		"auto_price": 0 if e.get("total") else 1,
	})
	if e.get("total"):
		doc.amount_after_tax = e["total"]
	doc.insert(ignore_permissions=True)
	from kamra.savings import log_action
	log_action("channel.booking", "Reservation", doc.name, conn.property,
	           minutes_saved=4,
	           rationale=f"{e.get('channel') or 'OTA'} booking "
	                     f"{e.get('ota_ref')} via {conn.provider}",
	           channel="API")
	# the availability push back to the channel is triggered by the
	# on_reservation_change doc_event this insert fires - no ad-hoc enqueue.
	return {"ota_ref": e.get("ota_ref"), "result": "booked",
	        "reservation": doc.name}


def _reconcile_booking_rooms(conn, booking_id: str, keep: set) -> None:
	"""After a modify, a room line the payload no longer carries is a room the
	guest dropped. Release it (no credit note - a modify is not a cancel)."""
	for r in _reservations_for_booking(conn.property, booking_id):
		if r.ota_ref in keep or r.status != "Confirmed":
			continue
		doc = frappe.get_doc("Reservation", r.name)
		frappe.flags.kamra_cancelling = True
		try:
			doc.status = "Cancelled"
			doc.cancellation_reason = "Other"
			doc.cancellation_note = f"Room removed on modify by {conn.provider}"
			doc.save(ignore_permissions=True)
		finally:
			frappe.flags.kamra_cancelling = False


def process_webhook_events(connection: str, payload: dict) -> None:
	"""Enqueued worker for an inbound OTA webhook (one delivery = one booking).

	Kept off the request path so the endpoint can answer Aiosell instantly.
	The whole booking is applied atomically: if one room line is rejected
	(e.g. the write-time villa guard blocks a conflicting OTA booking), the
	whole booking rolls back and is logged, rather than half-applied."""
	conn = frappe.get_doc("Channel Manager Connection", connection)
	if not conn.active:
		return
	events = provider_for(conn.provider).parse_webhook(conn, payload)
	if not events:
		return
	action = events[0].get("event")
	booking_id = events[0].get("booking_id") or events[0].get("ota_ref")
	try:
		for e in events:
			_apply_event(conn, e)
		if action == "modify":
			_reconcile_booking_rooms(
				conn, booking_id, keep={e.get("ota_ref") for e in events})
		frappe.db.commit()  # nosemgrep: frappe-manual-commit -- background webhook worker persists the completed booking before returning; reviewed as intentional
	except Exception:
		frappe.db.rollback()
		frappe.log_error(
			title=f"OTA webhook apply failed: {conn.name} / {booking_id}")


def _norm(s: str) -> str:
	return (s or "").strip().lower().replace(" ", "").replace("_", "").replace("-", "")


@frappe.whitelist()
@require_roles("Revenue Manager", "Hotel Admin", "Kamra Agent")
def import_room_mappings(connection: str, dry_run: int = 0):
	"""Property mapping, done once: pull the provider's room + rate-plan codes
	(via the adapter's fetch_property_details) and map them onto this
	property's room types.

	Auto-matches a provider room to a Kamra Room Type by code or name, then
	creates/updates a Channel Room Mapping (external_room_id = provider room id,
	external_rate_id = the room's first rate plan). Anything it can't place is
	returned under `unmatched` so you can map it by hand. Pass dry_run=1 to
	preview without writing."""
	conn = frappe.get_doc("Channel Manager Connection", connection)
	provider = provider_for(conn.provider)
	if not hasattr(provider, "fetch_property_details"):
		frappe.throw(f"{conn.provider} does not support mapping import.")
	details = provider.fetch_property_details(conn)

	rts = frappe.get_all("Room Type",
	                     filters={"property": conn.property, "disabled": 0},
	                     fields=["name", "room_type_code", "room_type_name"])
	index = {}
	for rt in rts:
		for key in (rt.room_type_code, rt.room_type_name,
		            rt.name.split("-")[-1]):
			index.setdefault(_norm(key), rt.name)

	created, updated, unmatched = [], [], []
	for r in details.get("rooms") or []:
		room_id = str(r.get("room_id") or "")
		rateplans = r.get("rateplans") or []
		rate_id = str(rateplans[0].get("rateplan_id")) if rateplans else None
		match = index.get(_norm(r.get("room_id"))) \
			or index.get(_norm(r.get("room_name")))
		if not match:
			unmatched.append({
				"room_id": room_id, "room_name": r.get("room_name"),
				"rateplans": [rp.get("rateplan_id") for rp in rateplans]})
			continue
		existing = frappe.db.get_value(
			"Channel Room Mapping",
			{"connection": connection, "room_type": match}, "name")
		row = {"room_type": match, "external_room_id": room_id,
		       "external_rate_id": rate_id}
		if int(dry_run or 0):
			(updated if existing else created).append(row)
			continue
		if existing:
			frappe.db.set_value("Channel Room Mapping", existing, {
				"external_room_id": room_id, "external_rate_id": rate_id})
			updated.append({**row, "name": existing})
		else:
			doc = frappe.get_doc({
				"doctype": "Channel Room Mapping", "connection": connection,
				**row}).insert(ignore_permissions=True)
			created.append({**row, "name": doc.name})
	return {"hotel_id": details.get("hotel_id"),
	        "hotel_name": details.get("hotel_name"),
	        "created": created, "updated": updated, "unmatched": unmatched}


@frappe.whitelist()
@require_roles("Revenue Manager", "Hotel Admin", "Front Desk", "Kamra Agent")
def connection_status(property: str):
	"""The sync-health card: connections, mappings, last push."""
	out = []
	for name in _connections(property, only_active=False):
		c = frappe.get_doc("Channel Manager Connection", name)
		out.append({
			"name": c.name, "provider": c.provider, "active": c.active,
			"external_property_id": c.external_property_id,
			"mappings": len(_mappings(name)),
			"last_push": str(c.last_push or ""),
			"last_push_status": c.last_push_status,
			"webhook_url": f"/api/method/kamra.channel_manager.webhook"
			               f"?connection={c.name}",
		})
	return out
