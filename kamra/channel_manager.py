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

import hmac
import json
import re
from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import add_days, nowdate

from kamra.authz import require_perm
from kamra.channels import provider_for


# The sites a booking can arrive from. Channel managers spell them their own
# way ("BookingCom", "booking"); one name per site keeps reports and badges
# together whether the booking came in by API or was keyed from the email.
OTA_CHANNELS = ["Booking.com", "Agoda", "Airbnb", "Expedia", "MakeMyTrip",
                "Goibibo"]
_CHANNEL_ALIASES = {"booking": "Booking.com", "mmt": "MakeMyTrip"}


def canonical_channel(name: str | None) -> str | None:
	"""Booking.com for "BookingCom" / "booking.com" / "booking"; any other
	site is kept as typed."""
	name = (name or "").strip()
	if not name:
		return None
	key = re.sub(r"[^a-z0-9]", "", name.lower())
	known = {re.sub(r"[^a-z0-9]", "", c.lower()): c for c in OTA_CHANNELS}
	return known.get(key) or _CHANNEL_ALIASES.get(key) or name


def channel_commission_pcts() -> dict[str, float]:
	"""Each OTA's default commission %: its Travel Agent record of type OTA
	(Settings > Travel Agents), keyed by the site's one name."""
	return {canonical_channel(a.agent_name): float(a.commission_pct or 0)
	        for a in frappe.get_all(
	            "Travel Agent", filters={"agent_type": "OTA", "disabled": 0},
	            fields=["agent_name", "commission_pct"])}


def set_ota_commission(doc, pct) -> None:
	"""Record the OTA's commission on an inserted booking: `pct` of its
	pre-tax price (the base a travel agent's commission uses). A travel
	agent's own commission wins."""
	if doc.get("travel_agent") or not float(pct or 0):
		return
	base = (float(doc.amount_before_tax or 0)
	        or sum(float(n.rate or 0) for n in doc.night_rates))
	doc.db_set("commission_amount", round(base * float(pct) / 100, 2))


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
		fields=["room_type", "external_room_id", "external_rate_id", "rate_plan"])


def _sellable(property: str, room_type: str, check_in, check_out) -> int:
	"""Rooms of a type actually sellable for [check_in, check_out): physical
	rooms (not out of order) minus every overlapping confirmed/checked-in
	reservation of that type - ASSIGNED OR NOT - minus unpicked group holds,
	and nothing at all while the villa <-> room lockout applies.

	Counting unassigned reservations is the point: an OTA booking arrives
	without a room number, and it must still lower what we offer the OTAs, or
	the same room sells twice. (The front-desk availability query is a separate
	path and is unchanged.)"""
	from kamra.api import _block_hold
	from kamra.kamra.doctype.reservation.reservation import villa_lockout_conflict
	# the villa <-> room lockout: a booked whole villa leaves its member
	# rooms nothing to sell, and a booked member room leaves the villa none
	if villa_lockout_conflict(property, room_type, check_in, check_out):
		return 0
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


def ari_snapshot(property: str, connection: str, days: int = 90, start=None,
                 with_rates: bool = True) -> list[dict]:
	"""Availability + rate per mapped room type per day, in the seam's
	normalized shape. Availability comes from the same engine the
	double-booking guard uses; the rate is the pricing engine's one-night
	sell rate (base occupancy, demand premiums and hurdle floors applied).

	`start` (default today) is the first day. with_rates=False leaves the
	rate out (None) and gives one row per room type and provider room id,
	however many rate plans are mapped to it: the outbox prices each mapped
	plan on its own (kamra.channel_ari)."""
	from kamra.api import _available_rooms_raw, _block_hold
	from kamra.kamra.doctype.reservation.reservation import villa_locked_nights
	from kamra.siu.availability import capacity_by_night, has_active_sius

	mappings = _mappings(connection)
	if not with_rates:
		seen = set()
		mappings = [m for m in mappings
		            if (m.room_type, m.external_room_id) not in seen
		            and not seen.add((m.room_type, m.external_room_id))]
	# room_category + physical room count per mapped room type - needed by the
	# villa lockout to know which rows are the whole-property bundle and when a
	# room type is fully free.
	meta = {m.room_type: {
		"category": frappe.db.get_value("Room Type", m.room_type,
		                                "room_category"),
		"total": frappe.db.count("Room", {"room_type": m.room_type}),
	} for m in mappings}

	out = []
	start = str(start or nowdate())
	end = add_days(start, days)

	def rate(room_type, d, d2):
		return _one_night_rate(property, room_type, d, d2) if with_rates else None

	for m in mappings:
		row = {"room_type": m.room_type,
		       "external_room_id": m.external_room_id,
		       "external_rate_id": m.external_rate_id, "days": []}
		use_siu = has_active_sius(property, m.room_type)
		siu_caps = (
			capacity_by_night(property, m.room_type, start, end)
			if use_siu else []
		)
		# nights the villa <-> room lockout takes this type off sale: a
		# booked villa zeroes its member rooms, a booked room the villa
		locked = villa_locked_nights(property, m.room_type, start, end)
		for i in range(days):
			d = add_days(start, i)
			d2 = add_days(d, 1)
			if str(d) in locked:
				row["days"].append({"date": str(d), "available": 0,
				                    "rate": rate(m.room_type, d, d2)})
				continue
			hold = _block_hold(property, m.room_type, d, d2)
			if use_siu:
				base = siu_caps[i] if i < len(siu_caps) else 0
				avail = max(0, base - (hold or 0))
			else:
				free = _available_rooms_raw(property, m.room_type, d, d2)
				avail = max(0, len(free) - (hold or 0))
			# Both paths must account for stays without a room number.
			if meta[m.room_type]["total"]:
				avail = min(avail, _sellable(property, m.room_type, d, d2))
			row["days"].append({"date": str(d), "available": avail,
			                    "rate": rate(m.room_type, d, d2)})
		out.append(row)
	_apply_villa_lockout(out, meta)
	return out


def _one_night_rate(property: str, room_type: str, d, d2) -> float:
	"""The pricing engine's one-night sell rate (2 adults), 0 when the
	night cannot be quoted - availability still goes out for that day."""
	from kamra.pricing import quote, rates_include_levy
	try:
		q = quote(property, room_type, str(d), str(d2), 2, 0, check_restrictions=False)
		night = q["nightly"][0]
		rate = float(night["rate"])
		if rates_include_levy(property):
			# The channel adds its own tax to whatever price it is given and
			# knows no levy, so a levy inside the displayed price is pushed
			# inside that price. An untaxed levy is sent with the tax taken
			# out, or the channel taxes it. The displayed price does not have
			# to include tax already: the channel adds tax either way. Room
			# 100, levy 10%, tax 10% bills 120 here; pushing 110 would show 121,
			# and the booking that comes back would lock a different room rate.
			levy = float(q.get("room_levy") or 0)
			if not _levy_is_taxed(property):
				levy /= 1 + float(night.get("gst_rate") or 0) / 100
			rate += levy
		return round(rate, 2)
	except Exception:
		return 0.0


def _levy_is_taxed(property: str) -> bool:
	taxable = frappe.get_cached_doc("Property", property).get("room_levy_taxable")
	return bool(1 if taxable is None else taxable)


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
@require_perm("Channel Manager Connection", "sync_channels")
def push_ari(connection: str, days: int | None = None):
	"""Push availability + rates for one connection, now. A connection whose
	adapter takes changes (Channex) queues a full sync on its outbox instead:
	one call per kind, through the same cap and retries (kamra.channel_ari)."""
	conn = frappe.get_doc("Channel Manager Connection", connection)
	if not conn.active:
		frappe.throw("This connection is not active.")
	from kamra import channel_ari
	if channel_ari.uses_outbox(connection):
		channel_ari.queue_full_sync(conn)
		return {"ok": True, "queued": True, "detail": "full sync queued"}
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
	the others. Pass `property` to scope the push to one property.

	Connections whose adapter takes changes are skipped: their outbox sends
	what changed, and a full sync only on demand (kamra.channel_ari)."""
	from kamra.channel_ari import uses_outbox
	for name in _connections(property):
		if uses_outbox(name):
			continue
		try:
			push_ari(name)
		except Exception:
			frappe.log_error(title=f"ARI push failed: {name}")


def enqueue_property_push(property: str | None, outbox: bool = True) -> None:
	"""Pipeline 1 trigger: after any availability or rate change, fan the new
	numbers out to this property's OTAs. After-commit so it runs on the
	saved state, and fully swallowed so a channel hiccup can never block or
	fail the booking / rate write that triggered it.

	Connections with an outbox get an availability change over the whole
	horizon (only what moved goes out); `outbox=False` leaves them to a
	caller that queued its own window."""
	from kamra import channel_ari
	try:
		if not property:
			return
		if outbox:
			channel_ari.enqueue_ari_change(property, kinds="availability",
			                               reason="enqueue_property_push")
		if not [n for n in _connections(property) if not channel_ari.uses_outbox(n)]:
			return
		frappe.enqueue("kamra.channel_manager.push_all_ari", queue="long",
		               enqueue_after_commit=True, property=property)
	except Exception:
		frappe.log_error(title="enqueue_property_push failed")


def on_reservation_change(doc, method=None):
	"""doc_event on Reservation: any insert/update/cancel moves availability,
	so refresh the channel side. The lockout + push run through the same
	ari_snapshot as everything else, so a direct front-desk villa/room
	booking tightens OTA inventory exactly like an OTA one does.

	A connection with an outbox gets the booking's own nights, before and
	after the change, for availability and price (occupancy moves price)."""
	from kamra import channel_ari
	window = channel_ari.reservation_window(doc, method)
	if window and getattr(doc, "property", None):
		channel_ari.enqueue_ari_change(doc.property, window[0], window[1], kinds="both",
		                               reason=f"Reservation {doc.name}")
	enqueue_property_push(getattr(doc, "property", None), outbox=False)


# ---------------------------------------------------------------------------
# Inbound bookings
# ---------------------------------------------------------------------------


@frappe.whitelist(allow_guest=True, methods=["POST"])
def webhook(connection: str | None = None, **kwargs):
	"""One URL per connection:
	/api/method/kamra.channel_manager.webhook?connection=CMC-00001
	Authenticated by the connection's webhook secret (X-Webhook-Secret
	header or `secret` in the payload)."""
	# A JSON body makes Frappe build the arguments from the body alone
	# (app.make_form_dict), so the ?connection= of that URL comes from here.
	connection = connection or (frappe.request.args.get("connection")
	                            if frappe.request else None)
	if not connection:
		frappe.throw("Missing connection.", frappe.ValidationError)
	conn = frappe.get_doc("Channel Manager Connection", connection)
	if not conn.active:
		return {"ok": False, "reason": "connection_inactive"}
	secret = conn.get_password("webhook_secret", raise_exception=False)
	sent = (frappe.get_request_header("X-Webhook-Secret")
	        if frappe.request else None) or kwargs.get("secret") or ""
	# no secret configured = nothing to authenticate against: refuse
	if not secret or not hmac.compare_digest(str(sent), secret):
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


def _storable_phone(phone: str | None) -> bool:
	"""Whether the Guest's Data/Phone field takes it: the check Frappe runs on
	insert (document.py, validate_phone_number(data, throw=True))."""
	return not phone or frappe.utils.validate_phone_number(phone)


def _storable_email(email: str | None) -> bool:
	"""Whether the Guest's Data/Email field takes it: every address Frappe
	splits out of it must be valid, as it checks on insert."""
	text = (email or "").strip()
	return not text or all(frappe.utils.validate_email_address(a)
	                       for a in frappe.utils.split_emails(text))


def _unstorable_contact(phone: str | None, email: str | None,
                        property: str | None) -> list[str]:
	"""The OTA contact the guest profile can't hold, exactly as it came (#468
	follow-up): a phone or an email Frappe would refuse on the Guest insert.
	It goes to the reservation's notes, so the booking is never lost over it."""
	from kamra import phone as phone_mod
	items = []
	typed = (phone or "").strip()
	if typed and not _storable_phone(phone_mod.for_property(typed, property)[0]):
		items.append(typed)
	mail = (email or "").strip()
	if not _storable_email(mail):
		items.append(mail)
	return items


def _find_or_create_guest(name: str, phone: str, email: str,
                          property: str | None = None) -> str:
	"""The OTA guest's profile. The phone is read with the property's
	country (#468); one that can't be read is kept as typed and flagged,
	never a reason to drop an already-acknowledged booking."""
	from kamra import phone as phone_mod
	typed = (phone or "").strip()
	phone, problem = phone_mod.for_property(typed, property)
	# #468 follow-up: what Frappe would refuse on the Guest insert stays off
	# the profile (blank) and on the reservation instead - see
	# _unstorable_contact. The phone is still flagged, without the number.
	if not _storable_phone(phone):
		phone, problem = "", phone_mod.INVALID
	if not _storable_email(email):
		email = ""
	for filt in ({"phone": phone_mod.matching(typed, property)} if phone else None,
	             {"email": email} if email else None):
		if filt:
			g = frappe.db.get_value("Guest", filt)
			if g:
				return g
	parts = (name or "OTA Guest").split(" ", 1)
	guest = frappe.get_doc({
		"doctype": "Guest", "first_name": parts[0],
		"last_name": parts[1] if len(parts) > 1 else "",
		"phone": phone or "", "email": email or "",
	}).insert(ignore_permissions=True).name
	phone_mod.flag(problem, "Guest", guest, property, "an OTA booking")
	return guest


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


def _locked_live_ota(property: str, ota_ref: str | None):
	"""The stay for this OTA reference, after the property inventory lock.

	A non-cancelled stay wins when a cancelled one shares the reference.
	The locking read sees a delivery that committed while this one waited.
	"""
	if not ota_ref:
		return None
	from kamra.kamra.doctype.reservation.reservation import lock_property_for_inventory
	lock_property_for_inventory(property)
	rows = frappe.db.sql(
		"""SELECT name, status FROM `tabReservation`
		   WHERE property = %s AND ota_ref = %s
		   ORDER BY CASE WHEN status = 'Cancelled' THEN 1 ELSE 0 END, creation
		   FOR UPDATE""",
		(property, ota_ref), as_dict=True)
	return rows[0] if rows else None


_CONTACT_LINE_EN = ("Contact from {0} could not be saved on the guest profile "
                    "and is kept here: {1}")


def _contact_line(channel: str | None, items: list[str]) -> str:
	"""The notes line that keeps an OTA contact the guest profile can't
	hold (#468 follow-up)."""
	return _("Contact from {0} could not be saved on the guest profile and is kept here: {1}"
	         ).format(channel, ", ".join(items))


def _kept_contact_line(notes: str | None) -> str | None:
	"""The contact line a reservation's notes already carry (#468 follow-up),
	in English or translated, so a modify without contact keeps it."""
	shapes = set()
	for template in (_CONTACT_LINE_EN.format("\0", "\1"), _contact_line("\0", ["\1"])):
		prefix, _sep, rest = template.partition("\0")
		shapes.add((prefix, rest.partition("\1")[0]))
	for line in (notes or "").splitlines():
		if any(line.startswith(prefix) and middle in line for prefix, middle in shapes):
			return line
	return None


def _apply_event(conn, e: dict, requested_reason: str | None = None) -> dict:
	"""One normalized OTA event -> the same paths a human would take."""
	e["channel"] = canonical_channel(e.get("channel")) or "OTA"
	existing = _locked_live_ota(conn.property, e.get("ota_ref"))

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
			if r.status not in ("Confirmed", "Requested"):
				continue  # idempotent: already cancelled / checked out
			res = frappe.get_doc("Reservation", r.name)
			note = (f"Cancelled by {e.get('channel') or 'OTA'} "
			        f"({e.get('booking_id') or e.get('ota_ref')})")
			if r.status == "Requested":
				# a retained OTA sale holds no room and took no money
				_release(res, "Booked elsewhere", note)
				cancelled.append(r.name)
				continue
			out = _do_cancel(res, reason="Booked elsewhere", note=note,
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
	property_currency = frappe.db.get_value("Property", conn.property, "currency")
	if e.get("currency") and property_currency and e["currency"] != property_currency:
		requested_reason = (f"OTA currency mismatch — resolve: {e.get('total') or 0} "
		                    f"{e['currency']}; property currency {property_currency}")
		# Keep foreign money in the note, never in the property's ledger currency.
		e = dict(e, total=0)
	if requested_reason:
		e = dict(e, notes="\n".join(s for s in (e.get("notes"), requested_reason) if s))

	if e["event"] == "modify" and existing:
		# A modify payload is the full new state - overwrite the record, never
		# merge. Room type can change too (guest moved to a different category).
		doc = frappe.get_doc("Reservation", existing.name)
		doc.room_type = room_type
		doc.check_in_date = e["check_in"]
		doc.check_out_date = e["check_out"]
		doc.adults = e.get("adults") or 2
		doc.children = e.get("children") or 0
		# #468 follow-up: a modify carries the contact line too - the new one
		# when the channel sends a contact the profile can't hold, else the one
		# the reservation already had.
		unstorable = _unstorable_contact(e.get("phone"), e.get("email"), conn.property)
		contact = (_contact_line(e.get("channel"), unstorable) if unstorable
		           else _kept_contact_line(doc.special_requests))
		doc.special_requests = "\n".join(s for s in (e.get("notes"), contact) if s) or None
		doc.auto_price = 0 if requested_reason or e.get("total") else 1
		if e.get("total") or requested_reason:
			doc.amount_after_tax = e.get("total") or 0
		if not doc.auto_price:
			lock_channel_rates(doc, e.get("total"), e.get("nightly"))
		old_transition = frappe.flags.kamra_status_transition
		try:
			if requested_reason:
				doc.status = "Requested"
				frappe.flags.kamra_status_transition = True
			doc.save(ignore_permissions=True)
		finally:
			frappe.flags.kamra_status_transition = old_transition
		return {"ota_ref": e["ota_ref"], "result": "modified",
		        "reservation": existing.name}

	if existing:
		return {"ota_ref": e["ota_ref"], "result": "duplicate_ignored",
		        "reservation": existing.name}

	guest = _find_or_create_guest(e.get("guest_name"), e.get("phone"),
	                              e.get("email"), conn.property)
	notes = e.get("notes") or ""
	unstorable = _unstorable_contact(e.get("phone"), e.get("email"), conn.property)
	if unstorable:
		# #468 follow-up: what the profile refused stays on the reservation.
		notes = "\n".join(s for s in (notes, _contact_line(e.get("channel"), unstorable)) if s)
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
		"status": "Requested" if requested_reason else "Confirmed",
		"channel": e.get("channel"),
		"ota_ref": e.get("ota_ref"),
		"special_requests": notes or None,
		# the OTA already sold at its price - keep their number, don't reprice
		"auto_price": 0 if requested_reason or e.get("total") else 1,
	})
	if e.get("total"):
		doc.amount_after_tax = e["total"]
		lock_channel_rates(doc, e["total"], e.get("nightly"))
	try:
		doc.insert(ignore_permissions=True)
	except frappe.DuplicateEntryError:
		# The other delivery committed while this one waited on the property
		# lock. Hand back that stay instead of booking the guest twice.
		winner = _locked_live_ota(conn.property, e.get("ota_ref"))
		if winner:
			return {"ota_ref": e.get("ota_ref"), "result": "duplicate_ignored",
			        "reservation": winner.name}
		raise
	# the channel's own commission when it sends one, else the site's default
	if e.get("commission"):
		doc.db_set("commission_amount", float(e["commission"]))
	else:
		set_ota_commission(doc, channel_commission_pcts().get(e.get("channel")))
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


def lock_channel_rates(doc, total_after_tax, nightly=None) -> None:
	"""Lock an OTA booking's nightly rates from the channel's own prices.

	The OTA sold the stay at its price (`total_after_tax`, tax included), so
	the folio must bill that - not today's rack rate. The channel's per-night
	prices say how the total splits across the nights (an even split when it
	sends none); each night's share has the room tax backed out at the slab
	its own pre-tax rate falls in. A zero total (currency mismatch, retained
	for staff) locks nothing."""
	total = float(total_after_tax or 0)
	if total <= 0 or not doc.room_type:
		return
	from frappe.utils import date_diff, getdate

	from kamra.pricing import rates_include_levy, room_gst_rate, room_net_rate, room_rate_digits

	nights = max(date_diff(doc.check_out_date, doc.check_in_date), 1)
	dates = [str(add_days(doc.check_in_date, i)) for i in range(nights)]
	given = {str(getdate(n["date"])): float(n.get("amount") or 0)
	         for n in (nightly or []) if n.get("date")}
	weights = [given.get(d, 0.0) for d in dates]
	if not sum(weights):
		weights = [1.0] * nights
	rt = frappe.get_doc("Room Type", doc.room_type)
	rows, running = [], 0.0
	scale = total / sum(weights)
	# the room rate keeps the decimals the property's own bookings keep
	digits = room_rate_digits(doc.property)
	levy_inside = rates_include_levy(doc.property)
	for i, (d, w) in enumerate(zip(dates, weights, strict=True)):
		gross = round(total - running, 2) if i == nights - 1 else round(w * scale, 2)
		running += gross
		if levy_inside:
			# the OTA's total is the guest's price: the levy comes out of it too
			pre, gst = room_net_rate(doc.property, rt, gross, tax_included=True)
		else:
			gst = Decimal(str(room_gst_rate(doc.property, rt, Decimal(str(gross)))))
			pre = Decimal(str(gross)) / (1 + gst / 100)
			gst2 = Decimal(str(room_gst_rate(doc.property, rt, pre)))
			if gst2 != gst:  # the slab follows the pre-tax rate
				gst = gst2
				pre = Decimal(str(gross)) / (1 + gst / 100)
		rows.append({"stay_date": d, "rate": round(float(pre), digits),
		             "gst_rate": float(gst), "meal_amount": 0,
		             "demand_premium_pct": 0})
	doc.set("night_rates", rows)
	doc.rate_lock_key = None


def _reconcile_booking_rooms(conn, booking_id: str, keep: set) -> None:
	"""After a modify, a room line the payload no longer carries is a room the
	guest dropped. Release it (no credit note - a modify is not a cancel)."""
	for r in _reservations_for_booking(conn.property, booking_id):
		if r.ota_ref in keep or r.status not in ("Confirmed", "Requested"):
			continue
		_release(frappe.get_doc("Reservation", r.name), "Other",
		         f"Room removed on modify by {conn.provider}")


def _release(doc, reason: str, note: str) -> None:
	"""Cancel without a fee or credit note."""
	frappe.flags.kamra_cancelling = True
	try:
		doc.status = "Cancelled"
		doc.cancellation_reason = reason
		doc.cancellation_note = note
		doc.save(ignore_permissions=True)
	finally:
		frappe.flags.kamra_cancelling = False


def process_webhook_events(connection: str, payload: dict) -> None:
	"""Enqueued worker for an inbound OTA webhook (one delivery = one booking).

	Kept off the request path so the endpoint can answer Aiosell instantly.
	The whole booking is applied atomically. A capacity refusal rolls back
	all lines, then retains them as Requested for staff to resolve."""
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
	except Exception as exc:
		from kamra.kamra.doctype.reservation.reservation import InventoryRefused
		capacity_refused = isinstance(exc, InventoryRefused)
		frappe.db.rollback()
		if capacity_refused and action in ("book", "modify"):
			for e in events:
				_apply_event(conn, e, requested_reason="OTA overbooking — resolve")
			frappe.db.commit()  # nosemgrep: frappe-manual-commit -- background worker persists the non-inventory booking for resolution
			return
		frappe.log_error(
			title=f"OTA webhook apply failed: {conn.name} / {booking_id}")


def _norm(s: str) -> str:
	return (s or "").strip().lower().replace(" ", "").replace("_", "").replace("-", "")


@frappe.whitelist()
@require_perm("Channel Manager Connection", "sync_channels")
def import_room_mappings(connection: str, dry_run: int = 0):
	"""Property mapping, done once: pull the provider's room + rate-plan codes
	(via the adapter's fetch_property_details) and map them onto this
	property's room types.

	Auto-matches a provider room to a Kamra Room Type by code or name, then
	creates/updates a Channel Room Mapping (external_room_id = provider room id,
	external_rate_id = the room's first rate plan). Anything it can't place is
	returned under `unmatched` so you can map it by hand. Pass dry_run=1 to
	preview without writing.

	A provider that prices each rate plan (details["per_rate_plan"], Channex)
	gets one mapping per provider rate plan instead, matched to a Kamra Rate
	Plan by code or name; the one plan of a room left unmatched sells the
	room type's base price. `warnings` lists what to check by hand: currency,
	time zone, room counts, per-person plans and fixed-amount plans."""
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

	if details.get("per_rate_plan"):
		return _import_rate_plan_mappings(conn, details, index, int(dry_run or 0))

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
	        "created": created, "updated": updated, "unmatched": unmatched,
	        "warnings": []}


def _import_rate_plan_mappings(conn, details: dict, index: dict, dry_run: int) -> dict:
	"""import_room_mappings for a provider that prices each rate plan: one
	Channel Room Mapping per provider rate plan, found again by
	(connection, external_rate_id)."""
	from frappe.utils import get_system_timezone
	plans = {}
	for p in frappe.get_all("Rate Plan", filters={"property": conn.property, "disabled": 0},
	                        fields=["name", "code", "rate_plan_name", "modifier_type"]):
		for key in (p.code, p.rate_plan_name):
			if key:
				plans.setdefault(_norm(key), p)
	prop = frappe.db.get_value("Property", conn.property, ["currency", "timezone"], as_dict=True) or {}
	warnings, warned = [], set()

	def warn(code: str, key, message: str) -> None:
		if (code, key) not in warned:
			warned.add((code, key))
			warnings.append({"code": code, "message": message})

	if details.get("currency") and prop.get("currency") and details["currency"] != prop["currency"]:
		warn("currency", None, _("The channel manager sells in {0}; this property is in {1}.").format(
			details["currency"], prop["currency"]))
	timezone = prop.get("timezone") or get_system_timezone()
	if details.get("timezone") and details["timezone"] != timezone:
		warn("timezone", None, _("The channel manager's property time zone is {0}; this property's is {1}.").format(
			details["timezone"], timezone))

	created, updated, unmatched = [], [], []
	for r in details.get("rooms") or []:
		room_id = str(r.get("room_id") or "")
		rateplans = r.get("rateplans") or []
		match = index.get(_norm(r.get("room_id"))) or index.get(_norm(r.get("room_name")))
		if not match:
			unmatched.append({"room_id": room_id, "room_name": r.get("room_name"),
			                  "rateplans": [rp.get("rateplan_id") for rp in rateplans],
			                  "reason": _("No room type matches it.")})
			continue
		rooms = frappe.db.count("Room", {"room_type": match})
		if r.get("count_of_rooms") is not None and int(r["count_of_rooms"]) != rooms:
			warn("count_of_rooms", room_id, _("The channel manager has {0} rooms of {1}; Kamra has {2}.").format(
				r["count_of_rooms"], r.get("room_name") or room_id, rooms))
		paired, loose = [], []
		for rp in rateplans:
			plan = plans.get(_norm(rp.get("rateplan_name"))) or plans.get(_norm(rp.get("rateplan_id")))
			(paired if plan else loose).append((rp, plan))
		if len(loose) == 1:  # the room's own price: no Kamra plan, the base price
			paired.append((loose[0][0], None))
			loose = []
		for rp, _plan in loose:
			unmatched.append({"room_id": room_id, "room_name": r.get("room_name"),
			                  "rateplan_id": str(rp.get("rateplan_id") or ""), "rateplan_name": rp.get("rateplan_name"),
			                  "reason": _("Several rate plans of this room match no Kamra rate plan: map them by hand.")})
		for rp, plan in paired:
			rate_id = str(rp.get("rateplan_id") or "")
			if rp.get("sell_mode") == "per_person":
				warn("per_person", rate_id, _("Rate plan {0} is priced per person; Kamra sends one price per room.").format(
					rp.get("rateplan_name") or rate_id))
			if plan and plan.modifier_type in ("Amount", "Absolute"):
				warn("fixed_amount", plan.name, _("Rate plan {0} adds a fixed amount: on the channels it applies every "
				                                  "night, on direct bookings once per stay.").format(plan.rate_plan_name))
			row = {"room_type": match, "external_room_id": room_id, "external_rate_id": rate_id,
			       "rate_plan": plan.name if plan else None}
			existing = frappe.db.get_value("Channel Room Mapping",
			                               {"connection": conn.name, "external_rate_id": rate_id}, "name")
			if dry_run:
				(updated if existing else created).append(row)
				continue
			if existing:
				doc = frappe.get_doc("Channel Room Mapping", existing)
				doc.update(row)
				doc.save(ignore_permissions=True)
				updated.append({**row, "name": existing})
			else:
				doc = frappe.get_doc({"doctype": "Channel Room Mapping", "connection": conn.name,
				                      **row}).insert(ignore_permissions=True)
				created.append({**row, "name": doc.name})
	return {"hotel_id": details.get("hotel_id"), "hotel_name": details.get("hotel_name"),
	        "created": created, "updated": updated, "unmatched": unmatched, "warnings": warnings}


@frappe.whitelist()
@require_perm("Channel Manager Connection", "view_channels")
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
