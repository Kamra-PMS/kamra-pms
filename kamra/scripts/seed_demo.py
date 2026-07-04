"""Seed a demo property so the local build shows a living hotel.

Run with:
    bench --site kamra.localhost execute kamra.scripts.seed_demo.execute

Idempotent: does nothing if the demo property already exists.
"""

import random

import frappe
from frappe.utils import add_days, nowdate

PROPERTY = "Kamra Demo Palace"

ROOM_TYPES = [
	("STD", "Standard", 2800, ["101", "102", "103", "104", "105", "106"]),
	("DLX", "Deluxe", 4200, ["201", "202", "203", "204", "205"]),
	("STE", "Suite", 7500, ["301", "302", "303"]),
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
	if frappe.db.exists("Property", PROPERTY):
		print("Demo property already exists — skipping.")
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
		}
	).insert(ignore_permissions=True)

	rooms_by_type = {}
	for code, label, price, room_numbers in ROOM_TYPES:
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
				"tax_percent": 5 if price <= 7500 else 18,
				"amenities": "WiFi, AC, TV, Tea/Coffee",
			}
		).insert(ignore_permissions=True)
		rooms_by_type[rt.name] = []
		for num in room_numbers:
			room = frappe.get_doc(
				{
					"doctype": "Room",
					"property": prop.name,
					"room_number": num,
					"room_type": rt.name,
					"floor": num[0],
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

	frappe.db.commit()
	print(f"Seeded demo property '{PROPERTY}' with rooms, guests and reservations.")
