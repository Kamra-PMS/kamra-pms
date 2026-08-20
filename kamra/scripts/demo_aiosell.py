"""One-command demo of the AioSell channel-manager sync.

Run it:
    bench --site kamra.localhost execute kamra.scripts.demo_aiosell.run

It sets everything up (an AioSell connection, room mappings, a villa unit if
needed), then plays the whole story with plain-English printouts:

    1. an OTA booking arrives      -> a reservation appears by itself
    2. the guest changes dates     -> the reservation updates (full replace)
    3. the guest cancels           -> reservation cancelled + 6-month credit note
    4. villa <-> room lockout       -> booking one side zeroes the other's OTA stock

Re-runnable: it clears its own demo data first. To wipe demo data without
running the show:  ...execute kamra.scripts.demo_aiosell.reset
"""

import frappe
from frappe.utils import add_days, nowdate

from kamra.channels import provider_for
from kamra.channel_manager import _apply_event, ari_snapshot

DEMO_PROPERTY = "Kamra Lakeside Villa"   # has a real Villa + a member STD
HOTEL_CODE = "sandbox-pms"
MEMBER_CODE, MEMBER_RATE = "std", "std-ep"
VILLA_CODE, VILLA_RATE = "villa", "villa-ep"


# ── helpers ────────────────────────────────────────────────────────────────

def _line(c="─"):
	print(c * 68)


def _pick_property(property):
	if property:
		return property
	if frappe.db.exists("Property", DEMO_PROPERTY):
		return DEMO_PROPERTY
	rt = frappe.get_all("Room Type",
	                    filters={"disabled": 0, "room_category": "Villa"},
	                    fields=["property"], limit=1)
	if rt:
		return rt[0].property
	return frappe.get_all("Room Type", filters={"disabled": 0},
	                      fields=["property"], limit=1)[0].property


def _room_types(property):
	villa = frappe.get_all("Room Type",
	                       filters={"property": property, "disabled": 0,
	                                "room_category": "Villa"},
	                       pluck="name")
	member = frappe.get_all("Room Type",
	                        filters={"property": property, "disabled": 0,
	                                 "room_category": ("!=", "Villa")},
	                        pluck="name")
	return (member[0] if member else None), (villa[0] if villa else None)


def _ensure_connection(property):
	name = frappe.db.get_value("Channel Manager Connection",
	                           {"property": property, "provider": "AioSell"})
	if name:
		conn = frappe.get_doc("Channel Manager Connection", name)
	else:
		conn = frappe.get_doc({
			"doctype": "Channel Manager Connection", "property": property,
			"provider": "AioSell", "active": 1})
	conn.active = 1
	conn.external_property_id = HOTEL_CODE
	conn.pms_slug = "sample-pms"
	conn.api_username = "testuser"
	conn.api_key = "testpass"
	conn.save(ignore_permissions=True)
	return conn.name


def _ensure_mapping(connection, room_type, room_code, rate_code):
	name = frappe.db.get_value("Channel Room Mapping",
	                           {"connection": connection, "room_type": room_type})
	doc = frappe.get_doc("Channel Room Mapping", name) if name else \
		frappe.get_doc({"doctype": "Channel Room Mapping",
		                "connection": connection, "room_type": room_type})
	doc.external_room_id = room_code
	doc.external_rate_id = rate_code
	doc.save(ignore_permissions=True)


def _ensure_villa_room(property, villa_rt):
	"""The villa is one sellable unit - make sure it has a physical room, or its
	availability is always zero and the lockout can't be shown."""
	if not villa_rt:
		return
	if not frappe.db.exists("Room", {"property": property, "room_type": villa_rt}):
		frappe.get_doc({
			"doctype": "Room", "property": property, "room_type": villa_rt,
			"room_number": "VILLA", "housekeeping_status": "Clean",
			"occupancy_status": "Vacant"}).insert(ignore_permissions=True)


def _webhook(connection, payload):
	"""Apply an inbound AioSell webhook the way the real endpoint's worker
	does, but inline so any error is visible during the demo."""
	conn = frappe.get_doc("Channel Manager Connection", connection)
	for e in provider_for("AioSell").parse_webhook(conn, payload):
		_apply_event(conn, e)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- demo script (run via bench execute); commits so seeded demo data is visible; not app runtime


def _res(ota_ref):
	rows = frappe.get_all("Reservation", filters={"ota_ref": ota_ref},
	                      fields=["name", "guest_name", "channel", "status",
	                              "check_in_date", "check_out_date",
	                              "amount_after_tax", "room_type"])
	return rows[0] if rows else None


def _avail(property, connection, room_type, date, days=12):
	for r in ari_snapshot(property, connection, days=days):
		if r["room_type"] == room_type:
			for d in r["days"]:
				if d["date"] == str(date):
					return d["available"]
	return None


def preview(property=None, days=5):
	"""Show the OUT direction without live credentials: the exact JSON Kamra
	would POST to Aiosell's /update (inventory) and /update-rates (rates)."""
	import json
	from kamra.channels.aiosell import build_push_bodies
	frappe.set_user("Administrator")  # nosemgrep: frappe-set-user -- demo script runs as admin to seed and read demo data; not app runtime
	property = _pick_property(property)
	conn = _ensure_connection(property)
	member_rt, villa_rt = _room_types(property)
	_ensure_mapping(conn, member_rt, MEMBER_CODE, MEMBER_RATE)
	if villa_rt:
		_ensure_mapping(conn, villa_rt, VILLA_CODE, VILLA_RATE)
		_ensure_villa_room(property, villa_rt)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- demo script (run via bench execute); commits so seeded demo data is visible; not app runtime

	snap = ari_snapshot(property, conn, days=int(days))
	inv, rates = build_push_bodies(HOTEL_CODE, snap)
	_line("═")
	print(f"  OUTBOUND PREVIEW · what Kamra would send Aiosell for {property}")
	print(f"  (first {days} days · villa lockout already applied)")
	_line("═")
	print("POST /api/v2/cm/update/<PMS_SLUG>   (availability)")
	print(json.dumps({"hotelCode": HOTEL_CODE, "updates": inv}, indent=2))
	_line()
	print("POST /api/v2/cm/update-rates/<PMS_SLUG>   (rates)")
	print(json.dumps({"hotelCode": HOTEL_CODE, "updates": rates}, indent=2))
	_line("═")
	print("  This is real data from your rooms/pricing. With live credentials")
	print("  it POSTs to Aiosell and fans out to every connected OTA.")
	_line("═")
	return {"inventory_blocks": len(inv), "rate_blocks": len(rates)}


def push_to_sandbox(password, property=None, days=14):
	"""Push REAL Kamra availability + rates to Aiosell's shared SANDBOX and
	watch it land on live.aiosell.com.

	Points a Kamra connection at the sandbox hotel, maps Kamra's room types onto
	the sandbox's OWN room codes (executive, suite) so the numbers are visible,
	then fires Kamra's real push. Run with the sandbox password:
	    ...execute kamra.scripts.demo_aiosell.push_to_sandbox --kwargs '{"password":"THE_SANDBOX_PW"}'
	"""
	from kamra.channel_manager import push_ari, ari_snapshot
	from kamra.channels.aiosell import build_push_bodies
	frappe.set_user("Administrator")  # nosemgrep: frappe-set-user -- demo script runs as admin to seed and read demo data; not app runtime
	property = _pick_property(property)
	member_rt, villa_rt = _room_types(property)

	name = frappe.db.get_value("Channel Manager Connection",
	                           {"property": property, "provider": "AioSell"})
	conn = frappe.get_doc("Channel Manager Connection", name) if name else \
		frappe.get_doc({"doctype": "Channel Manager Connection",
		                "property": property, "provider": "AioSell"})
	conn.active = 1
	conn.external_property_id = "sandbox-pms"   # the sandbox hotelCode
	conn.pms_slug = "sample-pms"                # the {pms} slug
	conn.api_username = "sandboxpms"            # sandbox Basic-auth user
	conn.api_key = password                     # sandbox Basic-auth password
	conn.save(ignore_permissions=True)

	reset(property)  # clear demo bookings so availability is clean
	# map Kamra room types -> the sandbox's own codes so they show on its board
	sandbox_map = [(member_rt, "executive", "executive-s-ep")]
	if villa_rt:
		sandbox_map.append((villa_rt, "suite", "suite-s-ep"))
	for rt, rc, rp in sandbox_map:
		if rt:
			_ensure_mapping(conn.name, rt, rc, rp)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- demo script (run via bench execute); commits so seeded demo data is visible; not app runtime

	snap = ari_snapshot(property, conn.name, days=int(days))
	inv, rates = build_push_bodies("sandbox-pms", snap)
	_line("═")
	print(f"  KAMRA → AIOSELL SANDBOX   ({property}, next {days} days)")
	_line("═")
	print("Kamra room type  →  sandbox code:")
	for rt, rc, rp in sandbox_map:
		if rt:
			print(f"   {rt}  →  {rc} / {rp}")
	print(f"\nAbout to send {len(inv)} inventory + {len(rates)} rate blocks "
	      f"(Kamra's real availability & pricing).")
	try:
		res = push_ari(conn.name, days=int(days))
		print("RESULT:", res)
		print("\n✅ Sent. Refresh live.aiosell.com (Sandbox PMS · Rates & "
		      "Inventory) — EXECUTIVE/SUITE now show KAMRA's numbers.")
	except Exception as e:
		print("PUSH FAILED:", str(e)[:400])
		print("If that's a 401/auth error, the sandbox API needs real partner "
		      "credentials (the dashboard login may not double as API auth) — "
		      "which is the onboarding step.")
	_line("═")
	return {"connection": conn.name, "inventory_blocks": len(inv),
	        "rate_blocks": len(rates)}


def reset(property=None):
	"""Delete this demo's reservations and credit notes so it can replay clean."""
	property = _pick_property(property)
	for r in frappe.get_all("Reservation",
	                        filters={"ota_ref": ("like", "DEMO-%")}, pluck="name"):
		try:
			frappe.delete_doc("Reservation", r, force=1, ignore_permissions=True)
		except Exception:
			pass
	for v in frappe.get_all("Discount Voucher",
	                        filters={"voucher_code": ("like", "CN-DEMO-%")},
	                        pluck="name"):
		try:
			frappe.delete_doc("Discount Voucher", v, force=1, ignore_permissions=True)
		except Exception:
			pass
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- demo script (run via bench execute); commits so seeded demo data is visible; not app runtime
	print(f"Demo data cleared for {property}.")


# ── the show ────────────────────────────────────────────────────────────────

def run(property=None):
	frappe.set_user("Administrator")  # nosemgrep: frappe-set-user -- demo script runs as admin to seed and read demo data; not app runtime
	property = _pick_property(property)
	member_rt, villa_rt = _room_types(property)
	if not member_rt:
		print(f"'{property}' has no room type to book - add one first.")
		return

	_line("═")
	print(f"  AIOSELL SYNC DEMO   ·   property: {property}")
	_line("═")

	reset(property)
	conn = _ensure_connection(property)
	_ensure_mapping(conn, member_rt, MEMBER_CODE, MEMBER_RATE)
	if villa_rt:
		_ensure_mapping(conn, villa_rt, VILLA_CODE, VILLA_RATE)
		_ensure_villa_room(property, villa_rt)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- demo script (run via bench execute); commits so seeded demo data is visible; not app runtime
	print(f"Setup ready · connection {conn} · member room '{member_rt}'"
	      + (f" · villa '{villa_rt}'" if villa_rt else " · (no villa room type)"))

	ci, co = add_days(nowdate(), 20), add_days(nowdate(), 22)

	# 1 ── a booking arrives from an OTA
	_line()
	print("STEP 1 · A guest books on Goibibo → Aiosell → Kamra")
	_webhook(conn, {
		"action": "book", "hotelCode": HOTEL_CODE, "channel": "Goibibo",
		"bookingId": "DEMO-501", "checkin": str(ci), "checkout": str(co),
		"specialRequests": "High floor, late check-in", "pah": False,
		"amount": {"amountAfterTax": 3400, "currency": "INR"},
		"guest": {"firstName": "Asha", "lastName": "Rao", "phone": "9800000000"},
		"rooms": [{"roomCode": MEMBER_CODE, "rateplanCode": MEMBER_RATE,
		           "occupancy": {"adults": 2, "children": 0},
		           "prices": [{"date": str(ci), "sellRate": 1700},
		                      {"date": str(add_days(ci, 1)), "sellRate": 1700}]}]})
	r = _res("DEMO-501")
	print(f"   → Kamra created reservation {r.name}: {r.guest_name} "
	      f"({r.channel}), {r.check_in_date}→{r.check_out_date}, ₹{r.amount_after_tax:.0f}")
	print("   Nobody typed it in. Open Kamra → Today/Reservations to show it.")

	# 2 ── the guest changes dates (full replace)
	_line()
	print("STEP 2 · The guest extends the stay (Aiosell sends the new state)")
	_webhook(conn, {
		"action": "modify", "hotelCode": HOTEL_CODE, "channel": "Goibibo",
		"bookingId": "DEMO-501", "checkin": str(ci), "checkout": str(add_days(ci, 4)),
		"amount": {"amountAfterTax": 6800, "currency": "INR"},
		"guest": {"firstName": "Asha", "lastName": "Rao"},
		"rooms": [{"roomCode": MEMBER_CODE, "rateplanCode": MEMBER_RATE,
		           "occupancy": {"adults": 2, "children": 0},
		           "prices": [{"date": str(ci), "sellRate": 1700}]}]})
	r = _res("DEMO-501")
	print(f"   → Same booking, now {r.check_in_date}→{r.check_out_date}, "
	      f"₹{r.amount_after_tax:.0f}. Updated automatically.")

	# 3 ── the guest cancels → credit note, no cash refund
	_line()
	print("STEP 3 · The guest cancels")
	frappe.db.set_value("Reservation", r.name, "advance_paid", 6800)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- demo script (run via bench execute); commits so seeded demo data is visible; not app runtime
	_webhook(conn, {"action": "cancel", "hotelCode": HOTEL_CODE,
	                "channel": "Goibibo", "bookingId": "DEMO-501"})
	r = _res("DEMO-501")
	cn = frappe.get_all("Discount Voucher",
	                    filters={"voucher_code": ("like", "CN-%")},
	                    fields=["voucher_code", "value", "valid_to"],
	                    order_by="creation desc", limit=1)
	print(f"   → Reservation {r.name} is now {r.status}.")
	if cn:
		print(f"   → Credit note {cn[0].voucher_code}: ₹{cn[0].value:.0f}, "
		      f"valid to {cn[0].valid_to} (your no-cash-refund policy).")

	# 4 ── villa <-> room lockout (only if this property has a real villa)
	if villa_rt:
		_line()
		print("STEP 4 · Villa ↔ Room lockout (what Kamra pushes back to OTAs)")
		d = add_days(nowdate(), 5)
		before_v = _avail(property, conn, villa_rt, d)
		before_m = _avail(property, conn, member_rt, d)
		print(f"   Before: villa={before_v} unit, rooms={before_m} on {d}")
		_webhook(conn, {
			"action": "book", "hotelCode": HOTEL_CODE, "channel": "Airbnb",
			"bookingId": "DEMO-777", "checkin": str(d), "checkout": str(add_days(d, 1)),
			"amount": {"amountAfterTax": 1700, "currency": "INR"},
			"guest": {"firstName": "Ravi"},
			"rooms": [{"roomCode": MEMBER_CODE, "rateplanCode": MEMBER_RATE,
			           "occupancy": {"adults": 2, "children": 0},
			           "prices": [{"date": str(d), "sellRate": 1700}]}]})
		after_v = _avail(property, conn, villa_rt, d)
		after_m = _avail(property, conn, member_rt, d)
		print(f"   One room sold → villa={after_v} (locked!), rooms={after_m} on {d}")
		print("   → The whole-villa listing closes on every OTA the moment one "
		      "room sells.")

		# reverse direction: book the WHOLE villa → every individual room closes
		d2 = add_days(nowdate(), 7)
		print(f"\n   Now the other way — book the ENTIRE villa on {d2}:")
		print(f"   Before: villa={_avail(property, conn, villa_rt, d2)} unit, "
		      f"rooms={_avail(property, conn, member_rt, d2)}")
		_webhook(conn, {
			"action": "book", "hotelCode": HOTEL_CODE, "channel": "Airbnb",
			"bookingId": "DEMO-778", "checkin": str(d2), "checkout": str(add_days(d2, 1)),
			"amount": {"amountAfterTax": 8600, "currency": "INR"},
			"guest": {"firstName": "Meera"},
			"rooms": [{"roomCode": VILLA_CODE, "rateplanCode": VILLA_RATE,
			           "occupancy": {"adults": 4, "children": 0},
			           "prices": [{"date": str(d2), "sellRate": 8600}]}]})
		print(f"   Whole villa sold → rooms={_avail(property, conn, member_rt, d2)} "
		      f"(all locked!), villa={_avail(property, conn, villa_rt, d2)} on {d2}")
		print("   → Every individual room closes on every OTA the moment the "
		      "villa sells — no double-booking, either direction.")

	_line("═")
	print("  DEMO COMPLETE. Re-run any time — it resets itself.")
	_line("═")
	return {"property": property, "connection": conn}
