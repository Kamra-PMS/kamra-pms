"""Seed showcase experiences and venues onto an existing demo property so
the booking engine and events diary look like a living resort.

Run with:
    bench --site <site> execute kamra.scripts.seed_showcase.execute

Idempotent: each experience/venue is keyed by (property, name); re-running
adds only what's missing, never duplicates.
"""

import frappe

PROPERTY = "Kamra Demo Palace"

# (name, category, price, duration, gst%, description, image)
EXPERIENCES = [
	("Sunrise Safari", "Tour", 3500, "3 hours", 5,
	 "Open-jeep wildlife safari with a naturalist guide, tea and binoculars.",
	 "https://images.unsplash.com/photo-1516426122078-c23e76319801?w=400"),
	("Candlelight Romantic Dinner", "Dining", 4500, "2 hours", 5,
	 "Private poolside table, five-course chef's menu, live acoustic music.",
	 "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=400"),
	("Ayurvedic Spa Ritual", "Spa", 2800, "90 min", 18,
	 "Warm-oil abhyanga massage followed by a herbal steam and tea.",
	 "https://images.unsplash.com/photo-1544161515-4ab6ce6db874?w=400"),
	("Couple's Spa Retreat", "Spa", 5200, "2 hours", 18,
	 "Side-by-side massage suite, aroma soak and a fruit platter for two.",
	 "https://images.unsplash.com/photo-1600334129128-685c5582fd35?w=400"),
	("Heritage City Walk", "Tour", 1200, "2.5 hours", 5,
	 "Guided old-town walk through bazaars, temples and hidden courtyards.",
	 "https://images.unsplash.com/photo-1524492412937-b28074a5d7da?w=400"),
	("Cooking Class with the Chef", "Activity", 2200, "2 hours", 5,
	 "Hands-on regional-thali class, spice-market tour and a sit-down lunch.",
	 "https://images.unsplash.com/photo-1556910103-1c02745aae4d?w=400"),
	("Sunset Lake Cruise", "Activity", 1800, "75 min", 5,
	 "Slow boat across the lake at golden hour with canapes and sparkling wine.",
	 "https://images.unsplash.com/photo-1514890547357-a9ee288728e0?w=400"),
	("Airport Transfer (Sedan)", "Transport", 1500, "one way", 5,
	 "Private air-conditioned sedan, meet-and-greet, bottled water.",
	 "https://images.unsplash.com/photo-1449965408869-eaa3f722e40d?w=400"),
	("Yoga at Dawn", "Activity", 800, "60 min", 5,
	 "Guided hatha-yoga session on the lawn as the sun comes up.",
	 "https://images.unsplash.com/photo-1506126613408-eca07ce68773?w=400"),
	("In-Room Floral Turndown", "Other", 2500, "on arrival", 18,
	 "Rose-petal bed, balloons and a cake — set up before you reach the room.",
	 "https://images.unsplash.com/photo-1522673607200-164d1b6ce486?w=400"),
]

# (name, capacity, base_price, amenities)
VENUES = [
	("Grand Ballroom", 400, 85000,
	 "Pillarless hall, stage, LED wall, in-house AV, green rooms."),
	("Garden Lawn", 600, 65000,
	 "Open-air lawn with fairy lights, marquee option, generator backup."),
	("Riverside Deck", 120, 40000,
	 "Waterfront deck for cocktails and intimate ceremonies."),
	("Boardroom", 20, 12000,
	 "Executive meeting room, video-conferencing, whiteboard, coffee service."),
]


# POS: (outlet_name, outlet_type, gst%, [ (item, category, price, veg, station, img) ])
POS = [
	("The Terrace Restaurant", "Restaurant", 5, [
		("Masala Dosa", "South Indian", 220, 1, "Kitchen",
		 "https://images.unsplash.com/photo-1630383249896-424e482df921?w=400"),
		("Butter Chicken", "North Indian", 480, 0, "Kitchen",
		 "https://images.unsplash.com/photo-1603894584373-5ac82b2ae398?w=400"),
		("Paneer Tikka", "Starters", 360, 1, "Kitchen",
		 "https://images.unsplash.com/photo-1599487488170-d11ec9c172f0?w=400"),
		("Veg Biryani", "Rice", 340, 1, "Kitchen",
		 "https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=400"),
		("Gulab Jamun", "Desserts", 160, 1, "Kitchen",
		 "https://images.unsplash.com/photo-1666190092159-3171cf0fbb12?w=400"),
	]),
	("Poolside Bar", "Bar", 18, [
		("Cold Coffee", "Beverages", 180, 1, "Bar",
		 "https://images.unsplash.com/photo-1461023058943-07fcbe16d735?w=400"),
		("Fresh Lime Soda", "Beverages", 120, 1, "Bar",
		 "https://images.unsplash.com/photo-1523371054106-bbf80586c33c?w=400"),
		("Kingfisher Beer", "Alcohol", 350, 1, "Bar",
		 "https://images.unsplash.com/photo-1608270586620-248524c67de9?w=400"),
	]),
]


def execute():
	if not frappe.db.exists("Property", PROPERTY):
		print(f"Property '{PROPERTY}' not found — run seed_demo first.")
		return

	added_exp = 0
	for name, cat, price, dur, gst, desc, img in EXPERIENCES:
		if frappe.db.exists("Experience", {"property": PROPERTY,
		                                    "experience_name": name}):
			continue
		frappe.get_doc({
			"doctype": "Experience",
			"property": PROPERTY,
			"experience_name": name,
			"category": cat,
			"price": price,
			"duration": dur,
			"gst_rate": gst,
			"description": desc,
			"image_url": img,
			"show_on_booking_page": 1,
		}).insert(ignore_permissions=True)
		added_exp += 1

	added_venue = 0
	for name, cap, price, amenities in VENUES:
		if frappe.db.exists("Venue", {"property": PROPERTY, "venue_name": name}):
			continue
		frappe.get_doc({
			"doctype": "Venue",
			"property": PROPERTY,
			"venue_name": name,
			"capacity": cap,
			"base_price": price,
			"amenities": amenities,
		}).insert(ignore_permissions=True)
		added_venue += 1

	# area-wise table layouts ("[Area]" headers, "name:seats" lines) so the
	# POS table map shows areas, seats and a realistic floor
	RESTAURANT_TABLES = "\n".join([
		"[Main Hall]",
		"T1:2", "T2:4", "T3:4", "T4:2", "T5:4", "T6:6", "T7:2", "T8:4",
		"[Family]",
		"F1:6", "F2:6", "F3:8",
		"[Patio]",
		"P1:2", "P2:2", "P3:4", "P4:4",
		"[Private Dining]",
		"PDR:10",
	])
	BAR_TABLES = "\n".join([
		"[Counter]",
		"C1:1", "C2:1", "C3:1", "C4:1", "C5:1", "C6:1",
		"[Lounge]",
		"L1:4", "L2:4", "L3:6", "L4:2",
		"[Poolside]",
		"S1:2", "S2:2", "S3:4",
	])
	added_outlet = added_item = 0
	for oname, otype, gst, items in POS:
		tables = (RESTAURANT_TABLES if otype == "Restaurant"
		          else BAR_TABLES if otype == "Bar" else None)
		outlet = frappe.db.get_value(
			"POS Outlet", {"property": PROPERTY, "outlet_name": oname})
		if not outlet:
			outlet = frappe.get_doc({
				"doctype": "POS Outlet", "property": PROPERTY,
				"outlet_name": oname, "outlet_type": otype, "gst_rate": gst,
				"tables": tables,
			}).insert(ignore_permissions=True).name
			added_outlet += 1
		elif tables:
			current = frappe.db.get_value("POS Outlet", outlet, "tables") or ""
			if "[" not in current:  # upgrade layouts that predate areas
				frappe.db.set_value("POS Outlet", outlet, "tables", tables)
		for item, cat, price, veg, station, img in items:
			if frappe.db.exists("Menu Item", {"outlet": outlet, "item_name": item}):
				continue
			frappe.get_doc({
				"doctype": "Menu Item", "property": PROPERTY, "outlet": outlet,
				"item_name": item, "category": cat, "price": price,
				"is_veg": veg, "available": 1, "prep_station": station,
				"is_alcohol": 1 if cat == "Alcohol" else 0, "image": img,
			}).insert(ignore_permissions=True)
			added_item += 1

	# laundry rate card - the price list the attendant quotes from
	LAUNDRY = [
		("Shirt", [("Wash & Iron", 60), ("Dry Clean", 120), ("Iron Only", 25)]),
		("T-Shirt", [("Wash & Iron", 50), ("Iron Only", 20)]),
		("Trousers", [("Wash & Iron", 70), ("Dry Clean", 140), ("Iron Only", 30)]),
		("Jeans", [("Wash & Iron", 80), ("Iron Only", 35)]),
		("Kurta", [("Wash & Iron", 60), ("Dry Clean", 130), ("Iron Only", 25)]),
		("Saree", [("Dry Clean", 220), ("Iron Only", 80)]),
		("Suit (2 pc)", [("Dry Clean", 380)]),
		("Blazer", [("Dry Clean", 260)]),
		("Dress", [("Wash & Iron", 110), ("Dry Clean", 200)]),
		("Undergarments", [("Wash & Iron", 25)]),
		("Socks (pair)", [("Wash & Iron", 20)]),
		("Nightwear", [("Wash & Iron", 55)]),
	]
	added_rate = 0
	for item, services in LAUNDRY:
		for service, rate in services:
			if frappe.db.exists("Laundry Rate", {
					"property": PROPERTY, "item_name": item,
					"service_type": service}):
				continue
			frappe.get_doc({
				"doctype": "Laundry Rate", "property": PROPERTY,
				"item_name": item, "service_type": service, "rate": rate,
			}).insert(ignore_permissions=True)
			added_rate += 1

	# operations: guest requests / tickets across teams and states, so the
	# Operations screens, SLA report and dashboards have a story to tell
	TICKETS = [
		("Extra towels for 204", "Housekeeping", "Medium", "Open", "WhatsApp"),
		("AC not cooling in 310", "Maintenance", "Urgent", "In Progress", "Manual"),
		("Airport cab at 6 AM", "Concierge", "High", "Open", "Voice"),
		("Late checkout request — 112", "Front Desk", "Medium", "Resolved", "Manual"),
		("Crib for the baby, room 218", "Housekeeping", "High", "Resolved", "AI Agent"),
		("Wi-Fi drops on 3rd floor", "Maintenance", "High", "Open", "QR"),
		("Birthday cake for table F2 tonight", "Room Service", "Medium", "In Progress", "Manual"),
		("Noise complaint — corridor, 2nd floor", "Complaint", "Urgent", "Resolved", "Manual"),
		("Iron & board to 415", "Housekeeping", "Low", "Closed", "WhatsApp"),
		("Spare adapter (Type G) needed", "Concierge", "Low", "Open", "Manual"),
	]
	added_ticket = 0
	rooms = frappe.get_all("Room", filters={"property": PROPERTY},
	                       fields=["name"], limit=12)
	for i, (subject, cat, prio, status, source) in enumerate(TICKETS):
		if frappe.db.exists("Service Ticket",
		                    {"property": PROPERTY, "subject": subject}):
			continue
		t = frappe.get_doc({
			"doctype": "Service Ticket", "property": PROPERTY,
			"subject": subject, "category": cat, "priority": prio,
			"source": source,
			"room": rooms[i % len(rooms)].name if rooms else None,
		})
		t.insert(ignore_permissions=True)
		if status != "Open":
			t.status = status
			t.save(ignore_permissions=True)
		added_ticket += 1

	# a shift-handover trail: yesterday's closed shifts + today's open one
	from frappe.utils import add_days, nowdate
	added_ho = 0
	HANDOVERS = [
		(add_days(nowdate(), -1), "Morning", "Closed", 5000, 42350, 1200,
		 "Two early check-ins done. 310 AC ticket open for maintenance."),
		(add_days(nowdate(), -1), "Evening", "Closed", 8000, 61200, 800,
		 "Full house tonight. Cab booked for 6 AM airport drop (ticket)."),
		(nowdate(), "Morning", "Open", 6000, 18500, 0,
		 "Waiting on laundry return for 204. F2 birthday setup at 7 PM."),
	]
	for date, shift, status, opening, collected, payouts, notes in HANDOVERS:
		if frappe.db.exists("Shift Handover", {
				"property": PROPERTY, "shift_date": date, "shift": shift}):
			continue
		frappe.get_doc({
			"doctype": "Shift Handover", "property": PROPERTY,
			"shift_date": date, "shift": shift, "status": status,
			"opening_cash": opening, "cash_collected": collected,
			"payouts": payouts,
			"closing_cash": opening + collected - payouts,
			"handover_notes": notes,
		}).insert(ignore_permissions=True)
		added_ho += 1

	# a live laundry story for the HK app: one bag in process, one ready
	added_lnd = 0
	inhouse = frappe.get_all(
		"Reservation", filters={"property": PROPERTY, "status": "Checked In"},
		fields=["name", "room"], limit=2)
	if (inhouse and frappe.db.exists("Laundry Rate", {"property": PROPERTY})
			and not frappe.db.count("Laundry Order", {"property": PROPERTY})):
		from kamra.laundry import collect_laundry, laundry_status
		for i, res in enumerate(inhouse):
			order = collect_laundry(PROPERTY, res.room, [
				{"item_name": "Shirt", "service_type": "Wash & Iron", "qty": 2},
				{"item_name": "Trousers", "service_type": "Wash & Iron", "qty": 1},
			] if i == 0 else [
				{"item_name": "Saree", "service_type": "Dry Clean", "qty": 1},
				{"item_name": "Kurta", "service_type": "Wash & Iron", "qty": 2},
			])["order"]
			laundry_status(order, "In Process")
			if i == 1:
				laundry_status(order, "Ready")
			added_lnd += 1

	extra = seed_sample_content()

	frappe.db.commit()
	print(f"Showcase seed: +{added_exp} experiences, +{added_venue} venues, "
	      f"+{added_outlet} outlets, +{added_item} menu items, "
	      f"+{added_rate} laundry rates, +{added_ticket} tickets, "
	      f"+{added_ho} handovers, +{added_lnd} laundry orders, {extra} "
	      f"on '{PROPERTY}'.")


def seed_sample_content():
	"""Fill the long tail of demo fields so every screen has a story:
	property profile & policies, revenue controls, a rolling 'today' with
	arrivals/departures and ETAs, table reservations, a room block, lost &
	found. Idempotent - only fills what's empty."""
	from frappe.utils import add_days, add_to_date, now_datetime, nowdate

	# ── property profile: fill only blank fields ────────────────────────
	PROFILE = {
		"website": "https://demo.kamrapms.com",
		"driving_directions": (
			"From Kempegowda International Airport take NH-44 south "
			"(45 min). We're 500 m past the Lalbagh West Gate - look for "
			"the green porte-cochère."),
		"latitude": 12.9507, "longitude": 77.5848,
		"house_rules": (
			"Check-in 14:00, check-out 11:00. Government ID required for "
			"all adult guests. Quiet hours 22:00-07:00. Smoking only on "
			"the terrace."),
		"pets_policy": ("Small pets (under 10 kg) welcome in Garden rooms "
		                "at ₹750/night - please tell us in advance."),
		"children_policy": ("Children under 6 stay free in the parents' "
		                    "room; 6-11 at the child rate. Cribs on "
		                    "request, free."),
		"extra_bed_policy": "Rollaway bed ₹900/night, subject to room size.",
		"meta_title": "Kamra Demo Palace, Bengaluru - boutique stays near Lalbagh",
		"meta_description": (
			"38 rooms of quiet luxury by Lalbagh Botanical Garden. Direct "
			"rates, pay at hotel, instant confirmation."),
		"page_slug": "kamra-demo-palace",
		"overbooking_pct": 10,
	}
	prop = frappe.get_doc("Property", PROPERTY)
	filled = 0
	for k, v in PROFILE.items():
		if not (prop.get(k) or ""):
			prop.set(k, v)
			filled += 1
	if filled:
		prop.flags.ignore_validate = True
		prop.save(ignore_permissions=True)

	# ── demand pricing tiers (Settings → Demand pricing) ────────────────
	tiers = 0
	for occ, prem, floor in ((70, 10, 0), (85, 20, 6500)):
		if not frappe.db.exists("Hurdle Rate",
		                        {"property": PROPERTY, "occupancy_from": occ}):
			frappe.get_doc({
				"doctype": "Hurdle Rate", "property": PROPERTY,
				"occupancy_from": occ, "premium_pct": prem, "min_rate": floor,
			}).insert(ignore_permissions=True)
			tiers += 1

	# ── a rolling 'today': arrivals with ETAs, departures with ETDs ─────
	def _mk_guest(name, phone):
		g = frappe.db.get_value("Guest", {"phone": phone})
		if g:
			return g
		first, _, last = name.partition(" ")
		return frappe.get_doc({
			"doctype": "Guest", "first_name": first, "last_name": last,
			"phone": phone,
		}).insert(ignore_permissions=True).name

	def _free_room(ci, co):
		for r in frappe.get_all("Room", filters={"property": PROPERTY},
		                        pluck="name"):
			clash = frappe.db.sql(
				"""select name from tabReservation where room=%s
				   and status in ('Confirmed','Checked In')
				   and check_in_date < %s and check_out_date > %s limit 1""",
				(r, co, ci))
			if not clash and not frappe.db.exists("Room Block", {
					"room": r, "block_status": "Active",
					"from_date": ("<", co), "to_date": (">", ci)}):
				return r
		return None

	today, added_story = nowdate(), 0
	story = [
		# (guest, phone, ci offset, co offset, eta, etd, checkin?)
		("Ananya Iyer", "+91 98860 11001", 0, 2, "11:30", None, 0),
		("Rohan Kapoor", "+91 98860 11002", 0, 1, "14:00", None, 0),
		("Meera & Arjun Shah", "+91 98860 11003", 0, 3, "18:45", None, 0),
		("David Chen", "+91 98860 11004", -1, 0, None, "10:30", 1),
		("Fatima Khan", "+91 98860 11005", -2, 0, None, "11:00", 1),
		("Karthik Rao", "+91 98860 11006", -1, 1, None, None, 1),
	]
	arrivals_today = frappe.db.count("Reservation", {
		"property": PROPERTY, "check_in_date": today, "status": "Confirmed"})
	if arrivals_today < 2:
		rt = frappe.get_all("Room Type", filters={"property": PROPERTY},
		                    pluck="name", limit=1)[0]
		for name, phone, ci_off, co_off, eta, etd, check_in in story:
			ci, co = add_days(today, ci_off), add_days(today, co_off)
			guest = _mk_guest(name, phone)
			if frappe.db.exists("Reservation", {
					"guest": guest, "check_in_date": ci,
					"status": ("in", ["Confirmed", "Checked In"])}):
				continue
			room = _free_room(ci, co)
			try:
				res = frappe.get_doc({
					"doctype": "Reservation", "property": PROPERTY,
					"guest": guest, "room_type": rt, "room": room,
					"check_in_date": ci, "check_out_date": co,
					"adults": 2, "auto_price": 1, "source": "Website",
					"planned_check_in_time": eta,
					"planned_check_out_time": etd,
				}).insert(ignore_permissions=True)
				if check_in:
					res.status = "Checked In"
					res.save(ignore_permissions=True)
				added_story += 1
			except Exception:
				continue  # full house is fine - the demo stays consistent

	# ── tonight's table reservations ────────────────────────────────────
	added_tres = 0
	outlet = frappe.db.get_value(
		"POS Outlet", {"property": PROPERTY, "outlet_type": "Restaurant"})
	if outlet and not frappe.db.count("POS Table Reservation", {
			"outlet": outlet, "status": "Booked"}):
		tonight = now_datetime().replace(minute=0, second=0, microsecond=0)
		for tbl, guest, phone, party, hrs in (
				("F2", "Nisha Reddy", "+91 98860 11007", 6, 3),
				("T6", "Imran Sheikh", "+91 98860 11008", 4, 4)):
			frappe.get_doc({
				"doctype": "POS Table Reservation", "outlet": outlet,
				"table_no": tbl, "guest_name": guest, "phone": phone,
				"party_size": party,
				"reserved_at": add_to_date(tonight, hours=hrs),
				"notes": "Birthday cake at the table" if tbl == "F2" else None,
			}).insert(ignore_permissions=True)
			added_tres += 1

	# ── a maintenance hold on the tape chart ────────────────────────────
	added_block = 0
	if not frappe.db.count("Room Block", {
			"property": PROPERTY, "block_status": "Active"}):
		room = _free_room(add_days(today, 5), add_days(today, 8))
		if room:
			frappe.get_doc({
				"doctype": "Room Block", "property": PROPERTY, "room": room,
				"from_date": add_days(today, 5), "to_date": add_days(today, 8),
				"reason": "Maintenance",
				"note": "AC compressor replacement - vendor booked",
			}).insert(ignore_permissions=True)
			added_block = 1

	# ── lost & found shelf ──────────────────────────────────────────────
	added_lf = 0
	rooms = frappe.get_all("Room", filters={"property": PROPERTY},
	                       pluck="name", limit=4)
	for desc, cond, i in (("Black leather wallet", "Found", 0),
	                      ("Kids' blue water bottle", "Found", 1),
	                      ("Silver bracelet", "Missing", 2)):
		if frappe.db.exists("Lost And Found Item", {
				"property": PROPERTY, "item_description": desc}):
			continue
		frappe.get_doc({
			"doctype": "Lost And Found Item", "property": PROPERTY,
			"item_description": desc, "condition": cond,
			"found_in_room": rooms[i % len(rooms)] if rooms else None,
			"found_on": today,
		}).insert(ignore_permissions=True)
		added_lf += 1

	return (f"+{filled} profile fields, +{tiers} demand tiers, "
	        f"+{added_story} today-stays, +{added_tres} table res, "
	        f"+{added_block} blocks, +{added_lf} lost&found")
