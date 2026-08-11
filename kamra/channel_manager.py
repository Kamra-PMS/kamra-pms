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


def ari_snapshot(property: str, connection: str, days: int = 90) -> list[dict]:
	"""Availability + rate per mapped room type per day, in the seam's
	normalized shape. Availability comes from the same engine the
	double-booking guard uses; the rate is the pricing engine's one-night
	sell rate (base occupancy, demand premiums and hurdle floors applied)."""
	from kamra.api import _available_rooms_raw, _block_hold
	from kamra.pricing import quote
	from kamra.siu.availability import capacity_by_night, has_active_sius

	out = []
	start = nowdate()
	end = add_days(start, days)
	for m in _mappings(connection):
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
				pass
			row["days"].append({"date": str(d), "available": avail,
			                    "rate": round(rate, 2)})
		out.append(row)
	return out


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


def push_all_ari():
	"""Hourly cron: keep every active connection fresh. Best-effort per
	connection - one provider being down never blocks the others."""
	for name in _connections():
		try:
			push_ari(name)
		except Exception:
			frappe.log_error(title=f"ARI push failed: {name}")


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


def _apply_event(conn, e: dict) -> dict:
	"""One normalized OTA event -> the same paths a human would take."""
	existing = frappe.db.get_value(
		"Reservation", {"property": conn.property, "ota_ref": e["ota_ref"]},
		["name", "status"], as_dict=True) if e.get("ota_ref") else None

	if e["event"] == "cancel":
		if not existing:
			return {"ota_ref": e.get("ota_ref"), "result": "cancel_unmatched"}
		doc = frappe.get_doc("Reservation", existing.name)
		if doc.status in ("Confirmed",):
			frappe.flags.kamra_cancelling = True
			try:
				doc.status = "Cancelled"
				doc.cancellation_reason = "Other"
				doc.cancellation_note = f"Cancelled by {e['channel']} " \
				                        f"({e['ota_ref']})"
				doc.save(ignore_permissions=True)
			finally:
				frappe.flags.kamra_cancelling = False
		return {"ota_ref": e["ota_ref"], "result": "cancelled",
		        "reservation": existing.name}

	room_type = _room_type_for(conn.name, e.get("room_type_external_id"))
	if not room_type:
		return {"ota_ref": e.get("ota_ref"), "result": "unmapped_room",
		        "external_room_id": e.get("room_type_external_id")}

	if e["event"] == "modify" and existing:
		doc = frappe.get_doc("Reservation", existing.name)
		doc.check_in_date = e["check_in"]
		doc.check_out_date = e["check_out"]
		doc.adults = e["adults"] or doc.adults
		doc.children = e["children"] or doc.children
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
	           rationale=f"{e['channel']} booking {e['ota_ref']} via "
	                     f"{conn.provider}",
	           channel="API")
	# sold a room - tighten availability on the channel side soon
	frappe.enqueue("kamra.channel_manager.push_all_ari", queue="long",
	               enqueue_after_commit=True)
	return {"ota_ref": e.get("ota_ref"), "result": "booked",
	        "reservation": doc.name}


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
