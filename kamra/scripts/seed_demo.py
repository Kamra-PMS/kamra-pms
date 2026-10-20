"""Seed a demo property so the local build shows a living hotel.

Run with:
    bench --site kamra.localhost execute kamra.scripts.seed_demo.execute

Idempotent: does nothing if the demo property already exists.
To wipe a public playground and rebuild from scratch, use
``kamra.scripts.reset_demo.execute`` instead.
"""

import random

import frappe
from frappe.utils import add_days, date_diff, nowdate

PROPERTY = "Kamra Demo Palace"

ROOM_TYPES = [
	("STD", "Standard", 2800, "City", ["101", "102", "103", "104", "105", "106"]),
	("DLX", "Deluxe", 4200, "Pool", ["201", "202", "203", "204", "205"]),
	("STE", "Suite", 7500, "Lake", ["301", "302", "303"]),
]

GUESTS = [
	("Aarav", "Sharma", "+91 98100 11001"),
	("Priya", "Nair", "+91 98100 11002"),
	("Rohan", "Mehta", "+91 98100 11003"),
	("Sneha", "Iyer", "+91 98100 11004"),
	("Vikram", "Rao", "+91 98100 11005"),
	("Ananya", "Das", "+91 98100 11006"),
	("Karan", "Kapoor", "+91 98100 11007"),
	("Meera", "Pillai", "+91 98100 11008"),
	("Arjun", "Singh", "+91 98100 11009"),
	("Divya", "Menon", "+91 98100 11010"),
]


def execute():
	# Document.insert skips doctype defaults while in_import is on (the
	# demo reset sets it for its wipe). Seed rows must get their defaults
	# - room status, folio type, check-in time, GST rates, booking engine.
	was_importing = frappe.flags.in_import
	frappe.flags.in_import = False
	try:
		return _execute()
	finally:
		frappe.flags.in_import = was_importing


def _execute():
	from kamra.scripts.seed_users import ensure_users

	# Mark this as a demo site so the login screen shows the demo accounts.
	frappe.db.set_default("kamra_demo_mode", "1")
	if frappe.db.exists("Property", PROPERTY):
		# first, while the defaults-skipped signature is still intact
		healed = heal_seed_defaults()
		ensure_users()
		from kamra.scripts.seed_showcase import execute as seed_showcase
		from kamra.scripts.seed_v1 import execute as seed_v1
		seed_showcase()
		seed_v1()
		seed_generic_properties()
		ensure_petty_cash_floats()
		frappe.db.commit()  # nosemgrep: frappe-manual-commit -- batch/seed/migration script runs outside the request cycle; explicit commit persists the staged writes
		print("Demo property already exists — ensured demo users + showcase + revenue samples."
		      + (f" Healed {healed} blank default(s)." if healed else ""))
		return

	random.seed(8)  # reproducible demo

	prop = frappe.get_doc(
		{
			"doctype": "Property",
			"property_name": PROPERTY,
			"city": "Bengaluru",
			"state": "Karnataka",
			"phone": "+91 80 4000 8000",
			"email": "demo@kamra.local",
			"gstin": "29ABCDE1234F1Z5",
			"petty_cash_float": 10000,
		}
	).insert(ignore_permissions=True)

	rooms_by_type = {}
	for code, label, price, view, room_numbers in ROOM_TYPES:
		rt = frappe.get_doc(
			{
				"doctype": "Room Type",
				"property": prop.name,
				"room_type_code": code,
				"room_type_name": label,
				"base_price": price,
				"base_occupancy": 2,
				"extra_adult_price": round(price * 0.25),
				"adults_capacity": 2 if code != "STE" else 3,
				"children_capacity": 1,
				"bed_type": "King" if code == "STE" else "Queen",
				"room_view": view,
				"tax_percent": 5 if price <= 7500 else 18,
				"amenities": "WiFi, AC, TV, Tea/Coffee",
			}
		).insert(ignore_permissions=True)
		rooms_by_type[rt.name] = []
		# spread the rooms across two floors so "high/low floor" preferences
		# have something to resolve against
		for idx, num in enumerate(room_numbers):
			floor = int(num[0]) + (1 if idx >= len(room_numbers) // 2 else 0)
			room = frappe.get_doc(
				{
					"doctype": "Room",
					"property": prop.name,
					"room_number": num,
					"room_type": rt.name,
					"floor": str(floor),
				}
			).insert(ignore_permissions=True)
			rooms_by_type[rt.name].append(room.name)

	frappe.get_doc(
		{
			"doctype": "Rate Plan",
			"property": prop.name,
			"rate_plan_name": "Best Available Rate",
			"code": "BAR",
			"modifier_type": "Percent",
			"modifier_value": 0,
			"is_default": 1,
		}
	).insert(ignore_permissions=True)

	guests = []
	for first, last, phone in GUESTS:
		guests.append(
			frappe.get_doc(
				{
					"doctype": "Guest",
					"first_name": first,
					"last_name": last,
					"phone": phone,
					"vip": 1 if first in ("Priya", "Vikram") else 0,
				}
			).insert(ignore_permissions=True)
		)

	today = nowdate()
	all_room_types = list(rooms_by_type.keys())
	used_rooms = set()

	def pick_room(rt):
		for r in rooms_by_type[rt]:
			if r not in used_rooms:
				used_rooms.add(r)
				return r
		return None

	def mk_res(guest, rt, ci, co, status, source, room=None):
		doc = frappe.get_doc(
			{
				"doctype": "Reservation",
				"property": prop.name,
				"guest": guest.name,
				"room_type": rt,
				"room": room,
				"check_in_date": ci,
				"check_out_date": co,
				"status": "Confirmed",
				"source": source,
				"adults": 2,
				"amount_before_tax": 0,
			}
		)
		# in-house and departing stays started before today: historical
		# seed rows, the case the past-check-in guard exempts by flag
		if date_diff(today, ci) > 0:
			doc.flags.allow_past_check_in = True
		doc.insert(ignore_permissions=True)
		if status != "Confirmed":
			doc.status = status
			doc.save(ignore_permissions=True)
		return doc

	# 3 in-house guests (checked in yesterday, leaving tomorrow/later)
	for i in range(3):
		rt = all_room_types[i % len(all_room_types)]
		room = pick_room(rt)
		mk_res(guests[i], rt, add_days(today, -1), add_days(today, 1 + i),
		       "Checked In", "OTA" if i == 0 else "Manual", room)

	# 2 of today's departures (checked in 2 days ago, leaving today)
	for i in range(3, 5):
		rt = all_room_types[i % len(all_room_types)]
		room = pick_room(rt)
		mk_res(guests[i], rt, add_days(today, -2), today,
		       "Checked In", "Phone", room)

	# 3 arrivals today (confirmed, not yet checked in; one by the AI agent)
	for i in range(5, 8):
		rt = all_room_types[i % len(all_room_types)]
		room = pick_room(rt)
		mk_res(guests[i], rt, today, add_days(today, 2),
		       "Confirmed", "AI Agent" if i == 5 else "Website", room)

	# 2 future bookings
	for i in range(8, 10):
		rt = all_room_types[i % len(all_room_types)]
		mk_res(guests[i], rt, add_days(today, 3), add_days(today, 5),
		       "Confirmed", "OTA")

	# A few savings-ledger rows so the counter is alive
	from kamra.savings import log_action

	for action, minutes, why in [
		("answer_guest_call", 6, "Answered rate inquiry on voice, quoted Deluxe"),
		("create_reservation", 8, "Booked 2-night Deluxe stay over WhatsApp"),
		("send_arrival_reminder", 4, "Confirmed ETA with tomorrow's arrival"),
		("night_audit_prep", 25, "Reconciled today's postings automatically"),
	]:
		log_action(
			action_type=action,
			property=prop.name,
			minutes_saved=minutes,
			rationale=why,
			agent_name="Kamra Agent",
			channel="Voice" if "call" in action else "WhatsApp",
		)

	# Demo login accounts (one per role) so the gated login buttons work.
	ensure_users()

	# showcase experiences + venues (safari, spa, romantic dinner, ballrooms)
	from kamra.scripts.seed_showcase import execute as seed_showcase
	seed_showcase()

	# seasons, guardrails, vouchers, meal plans, extra rate plans
	from kamra.scripts.seed_v1 import execute as seed_v1
	seed_v1()

	# Seed generic demo properties (lakeside villa with whole-property lock, and beach homestay with AC/non-AC rooms)
	seed_generic_properties()
	ensure_petty_cash_floats()

	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- batch/seed/migration script runs outside the request cycle; explicit commit persists the staged writes
	print(f"Seeded demo property '{PROPERTY}' with rooms, guests, reservations and login users.")


RENTALS = ("Kamra Lakeside Villa", "Kamra Beach Homestay")


def _insert_rental_property(fields: dict):
	"""A villa / homestay is a Short Term Rental with its booking page
	live - the same preset setup_property applies at creation."""
	from kamra.property_presets import KIND_STR, apply_kind_defaults
	from kamra.turnover import ensure_default_profile

	fields = apply_kind_defaults({
		**fields, "property_kind": KIND_STR, "booking_engine_enabled": 1,
	})
	prop = frappe.get_doc({"doctype": "Property", **fields}).insert(ignore_permissions=True)
	ensure_default_profile(prop.name, str_defaults=True)
	return prop


def _ensure_rental_kind():
	"""Heal demo sites seeded before the villa / homestay were rentals:
	switch the kind (Property.validate applies the STR preset to empty
	fields) and turn the booking engine on."""
	from kamra.property_presets import KIND_STR

	for name in RENTALS:
		if not frappe.db.exists("Property", name):
			continue
		doc = frappe.get_doc("Property", name)
		dirty = False
		if doc.property_kind != KIND_STR:
			doc.property_kind = KIND_STR
			dirty = True
		if not doc.booking_engine_enabled:
			doc.booking_engine_enabled = 1
			dirty = True
		mods = [m.strip() for m in (doc.enabled_modules or "").split(",") if m.strip()]
		if mods and "booking-engine" not in mods:
			doc.enabled_modules = ",".join(sorted(set(mods) | {"booking-engine"}))
			dirty = True
		if dirty:
			doc.save(ignore_permissions=True)



def ensure_petty_cash_floats():
	"""Each property keeps its own petty-cash imprest — never one shared box."""
	defaults = {
		"Kamra Demo Palace": 10000,
		"Kamra Beach House": 3000,
		"Kamra Lakeside Villa": 5000,
		"Kamra Beach Homestay": 2500,
	}
	for name, amount in defaults.items():
		if not frappe.db.exists("Property", name):
			continue
		cur = frappe.db.get_value("Property", name, "petty_cash_float")
		if cur in (None, "", 0, 0.0):
			frappe.db.set_value("Property", name, "petty_cash_float", amount,
			                    update_modified=False)


def seed_generic_properties():
	# 1. Seed Kamra Lakeside Villa (Generic Tatasth structure)
	p1 = "Kamra Lakeside Villa"
	if not frappe.db.exists("Property", p1):
		prop = _insert_rental_property({
			"property_name": p1,
			"city": "Bengaluru",
			"state": "Karnataka",
			"gstin": "29ABCDE1234F3Z3",
			"checkin_time": "14:00:00",
			"checkout_time": "11:00:00",
			"minimum_nights": 1,
			"booking_payment_mode": "Advance percent",
			"advance_percent": 100,
			"security_deposit_amount": 5000,
		})

		rt_std = frappe.get_doc({
			"doctype": "Room Type",
			"property": prop.name,
			"room_type_code": "STD",
			"room_type_name": "Standard Room",
			"room_category": "Private",
			"base_price": 7400,
			"base_occupancy": 2,
			"extra_adult_price": 2100,
			"child_price": 1000,
			"free_child_age": 6,
			"adults_capacity": 2,
			"children_capacity": 1,
			"max_total_occupants": 3,
		}).insert(ignore_permissions=True)

		rt_villa = frappe.get_doc({
			"doctype": "Room Type",
			"property": prop.name,
			"room_type_code": "VILLA",
			"room_type_name": "Entire Property",
			"room_category": "Villa",
			"base_price": 31500,
			"base_occupancy": 10,
			"extra_adult_price": 2100,
			"child_price": 1000,
			"free_child_age": 6,
			"adults_capacity": 10,
			"children_capacity": 5,
			"max_total_occupants": 15,
		}).insert(ignore_permissions=True)

		# Tatasth physical rooms (Ground Floor & First Floor)
		for i in range(1, 6):
			floor = "Ground Floor" if i <= 3 else "First Floor"
			frappe.get_doc({
				"doctype": "Room",
				"property": prop.name,
				"room_number": f"Room {i}",
				"room_type": rt_std.name,
				"floor": floor
			}).insert(ignore_permissions=True)

		from kamra.api import set_room_rate
		set_room_rate(prop.name, rt_std.name, "2026-08-01", "2027-08-01", 8600, reason="Weekend Rate", days_of_week=["Fri", "Sat"])
		set_room_rate(prop.name, rt_villa.name, "2026-08-01", "2027-08-01", 36800, reason="Weekend Rate", days_of_week=["Fri", "Sat"])
		print("Seeded generic Kamra Lakeside Villa.")

	# 2. Seed Kamra Beach Homestay (Generic Waterfront structure)
	p2 = "Kamra Beach Homestay"
	if not frappe.db.exists("Property", p2):
		prop = _insert_rental_property({
			"property_name": p2,
			"city": "Bengaluru",
			"state": "Karnataka",
			"gstin": "29ABCDE1234F4Z2",
			"checkin_time": "14:00:00",
			"checkout_time": "11:00:00",
			"minimum_nights": 1,
			"booking_payment_mode": "Advance percent",
			"advance_percent": 100,
			"security_deposit_amount": 5000,
		})

		rt_tfac = frappe.get_doc({
			"doctype": "Room Type", "property": prop.name,
			"room_type_code": "TFAC", "room_type_name": "Top Floor AC",
			"room_category": "Private", "base_price": 4000, "base_occupancy": 2,
			"adults_capacity": 2, "children_capacity": 1, "max_total_occupants": 3
		}).insert(ignore_permissions=True)

		rt_uf2r = frappe.get_doc({
			"doctype": "Room Type", "property": prop.name,
			"room_type_code": "UF2R", "room_type_name": "Upper Floor (2-room)",
			"room_category": "Private", "base_price": 6000, "base_occupancy": 4,
			"adults_capacity": 4, "children_capacity": 2, "max_total_occupants": 6
		}).insert(ignore_permissions=True)

		rt_gfna = frappe.get_doc({
			"doctype": "Room Type", "property": prop.name,
			"room_type_code": "GFNA", "room_type_name": "Ground Floor Non-AC – Room A",
			"room_category": "Private", "base_price": 2700, "base_occupancy": 2,
			"adults_capacity": 2, "children_capacity": 1, "max_total_occupants": 3
		}).insert(ignore_permissions=True)

		rt_gfnb = frappe.get_doc({
			"doctype": "Room Type", "property": prop.name,
			"room_type_code": "GFNB", "room_type_name": "Ground Floor Non-AC – Room B",
			"room_category": "Private", "base_price": 3100, "base_occupancy": 2,
			"adults_capacity": 2, "children_capacity": 1, "max_total_occupants": 3
		}).insert(ignore_permissions=True)

		# Physical Rooms (Top Floor, Upper Floor, Ground Floor)
		frappe.get_doc({"doctype": "Room", "property": prop.name, "room_number": "Room 1", "room_type": rt_tfac.name, "floor": "Top Floor"}).insert(ignore_permissions=True)
		frappe.get_doc({"doctype": "Room", "property": prop.name, "room_number": "Room 2", "room_type": rt_uf2r.name, "floor": "Upper Floor"}).insert(ignore_permissions=True)
		frappe.get_doc({"doctype": "Room", "property": prop.name, "room_number": "Room 3", "room_type": rt_uf2r.name, "floor": "Upper Floor"}).insert(ignore_permissions=True)
		frappe.get_doc({"doctype": "Room", "property": prop.name, "room_number": "Room 4", "room_type": rt_gfna.name, "floor": "Ground Floor"}).insert(ignore_permissions=True)
		frappe.get_doc({"doctype": "Room", "property": prop.name, "room_number": "Room 5", "room_type": rt_gfnb.name, "floor": "Ground Floor"}).insert(ignore_permissions=True)
		print("Seeded generic Kamra Beach Homestay.")

	_ensure_rental_kind()


# --- heal rows a defaults-skipped reset left blank ---------------------------

DEMO_PROPERTIES = (PROPERTY, *RENTALS)
_NUMERIC = {"Int", "Float", "Currency", "Percent", "Check", "Rating", "Duration"}
_TEMPORAL = {"Date", "Datetime", "Time"}
_SKIP_TYPES = {"Table", "Table MultiSelect", "Section Break", "Column Break",
               "Tab Break", "HTML", "Button", "Heading", "Fold"}


def _static_default(df):
	d = df.default
	if d in (None, ""):
		return None
	d = str(d)
	if d.startswith((":", "eval:", "__")) or d.lower() in ("today", "now") or "{" in d:
		return None
	if df.fieldtype in _NUMERIC:
		try:
			return float(d) if "." in d else int(d)
		except ValueError:
			return None
	return d


def _defaults_were_skipped(prop: str) -> bool:
	"""A Property inserted with in_import on carries no defaults: its hold
	window and GST slab are all zero. Settings can't save that (the hold
	window has a 5-minute floor), so a real property never matches."""
	row = frappe.db.get_value(
		"Property", prop,
		["hold_minutes", "gst_slab_threshold", "gst_rate_low", "gst_rate_high"],
		as_dict=True)
	return bool(row) and not any(row.values())


def heal_seed_defaults(properties=DEMO_PROPERTIES) -> int:
	"""Fill doctype defaults on demo rows that an earlier reset seeded
	without them (frappe.flags.in_import left on). Only touches demo
	properties that show the defaults-skipped signature, and only fields
	that are still blank / zero while their default is not, so values set
	since are kept. Child tables and doctypes without a property link
	(Guest, ...) are left alone.

	Bench: bench --site <demo> execute kamra.scripts.seed_demo.heal_seed_defaults
	"""
	targets = [p for p in properties
	           if frappe.db.exists("Property", p) and _defaults_were_skipped(p)]
	if not targets:
		return 0
	doctypes = ["Property"] + frappe.get_all(
		"DocType", filters={"module": "Kamra", "istable": 0, "issingle": 0,
		                    "name": ("!=", "Property")}, pluck="name")
	healed = 0
	for dt in doctypes:
		if not frappe.db.table_exists(dt):
			continue
		meta = frappe.get_meta(dt)
		if dt == "Property":
			key = "name"
		elif meta.has_field("property") and frappe.db.has_column(dt, "property"):
			key = "property"
		else:
			continue
		for df in meta.fields:
			if df.fieldtype in _SKIP_TYPES or df.fieldname == "naming_series":
				continue
			val = _static_default(df)
			if val is None or (df.fieldtype in _NUMERIC and not val):
				continue
			if not frappe.db.has_column(dt, df.fieldname):
				continue
			col = f"`{df.fieldname}`"
			if df.fieldtype in _NUMERIC:
				blank = f"ifnull({col}, 0) = 0"
			elif df.fieldtype in _TEMPORAL:
				blank = f"{col} is null"
			else:
				blank = f"ifnull({col}, '') = ''"
			for prop in targets:
				frappe.db.sql(  # nosemgrep: frappe-sql-format-injection -- doctype and fieldnames come from DocType meta, not user input; values are bound
					f"update `tab{dt}` set {col} = %s where `{key}` = %s and {blank}",
					(val, prop))
				healed += frappe.db._cursor.rowcount if getattr(frappe.db, "_cursor", None) else 0
	frappe.clear_cache()
	return healed
