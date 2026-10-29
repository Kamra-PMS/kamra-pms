"""Dress the demo properties' public booking pages: hero, logo, gallery,
room photos, descriptions, amenities and policies.

Photos ship with the app under kamra/public/demo (see CREDITS.md there),
so the demo never hotlinks a third-party image.

Run with:
    bench --site <site> execute kamra.scripts.seed_booking_page.execute

Idempotent: every run writes the same content over the demo properties,
so a re-run after a content change updates an existing site. seed_demo
calls it, and the demo's daily reset (reset_demo) runs seed_demo.
"""

import frappe

IMG = "/assets/kamra/demo/"

PROPERTIES = {
	"Kamra Demo Palace": {
		"fields": {
			"star_category": "4 Star",
			"logo_url": IMG + "palace-logo.svg",
			"hero_image": IMG + "palace-hero.webp",
			"og_image": IMG + "palace-hero.webp",
			"showcase_description": (
				"A calm city hotel by Ulsoor Lake with a palm-lined pool, a sunset "
				"terrace and quiet rooms for work trips and long weekends. Ten "
				"minutes from MG Road, forty from the airport."),
			"property_amenities": (
				"Outdoor pool, Free WiFi, All-day restaurant, Spa, Fitness room, "
				"Airport transfer, Free parking, 24-hour front desk"),
			"address_line": "14 Lake View Road, Ulsoor",
			"pincode": "560008",
			"latitude": 12.9817,
			"longitude": 77.6195,
			"driving_directions": (
				"From the airport take NH 44 south to Hebbal, then the Outer Ring "
				"Road to Ulsoor. The hotel is on the east bank of the lake, with "
				"free parking at the gate."),
			"free_cancel_days": 2,
			"cancellation_fee": "First Night",
			"house_rules": (
				"Check-in from 2 pm, check-out by 11 am.\n"
				"Government photo ID for every adult at check-in.\n"
				"Quiet hours from 10 pm to 7 am."),
			"children_policy": (
				"Children under 5 stay free in their parents' room. An extra bed "
				"is available in Deluxe rooms and Suites."),
		},
		"gallery": [
			("palace-pool.webp", "Pool and garden"),
			("palace-terrace.webp", "Terrace at dusk"),
			("palace-cabanas.webp", "Poolside cabanas"),
			("palace-loungers.webp", "Sun deck"),
			("palace-view.webp", "Roof deck"),
		],
		"faqs": [
			("Is breakfast included?",
			 "Pick a rate with breakfast when you book, or add it at the front desk."),
			("Do you offer airport pickup?",
			 "Yes. Ask for a transfer in your special requests and we will confirm the price."),
			("Can I check in early?",
			 "Early check-in depends on the day's arrivals. Tell us your arrival time and we will do our best."),
		],
		"room_types": {
			"STD": ("A bright room on the city side with a queen bed, a work desk and "
			        "a rain shower. Good for one or two.",
			        "Free WiFi, Air conditioning, Smart TV, Tea and coffee, Work desk, Rain shower",
			        [("palace-std-1.webp", "Queen bed"), ("palace-std-2.webp", "Work corner")]),
			"DLX": ("More room to spread out, with a pool view, a reading chair and "
			        "a bathtub.",
			        "Free WiFi, Air conditioning, Smart TV, Minibar, Bathtub, Tea and coffee",
			        [("palace-dlx-1.webp", "Deluxe bedroom"), ("palace-dlx-2.webp", "Morning light")]),
			"STE": ("A corner suite over the lake with a separate lounge, a king bed "
			        "and floor-to-ceiling windows.",
			        "Separate lounge, King bed, Bathtub, Minibar, Free WiFi, Air conditioning, Smart TV",
			        [("palace-ste-1.webp", "Suite lounge"), ("palace-ste-2.webp", "Lake-facing bedroom"),
			         ("palace-ste-3.webp", "Bedroom")]),
		},
	},
	"Kamra Lakeside Villa": {
		"fields": {
			"star_category": "Boutique",
			"logo_url": IMG + "villa-logo.svg",
			"hero_image": IMG + "villa-hero.webp",
			"og_image": IMG + "villa-hero.webp",
			"showcase_description": (
				"A private villa on a quiet lake outside the city, with a garden, "
				"a plunge pool and a jetty for sunrise coffee. Book one room or "
				"the whole house."),
			"property_amenities": (
				"Private pool, Lake jetty, Garden, Full kitchen, Free WiFi, "
				"Free parking, Barbecue"),
			"free_cancel_days": 7,
			"cancellation_fee": "Full Stay",
			"house_rules": (
				"No parties or events.\n"
				"Pool hours 7 am to 8 pm.\n"
				"Quiet hours from 10 pm."),
		},
		"gallery": [
			("villa-lake.webp", "The lake at dawn"),
			("villa-pool.webp", "Plunge pool"),
			("villa-deck.webp", "Deck over the water"),
		],
		"faqs": [
			("Is there a cook?",
			 "A cook can be arranged for an extra charge. Ask when you book."),
		],
		"room_types": {
			"STD": ("A garden-facing bedroom with its own bathroom, in the main house.",
			        "Air conditioning, Free WiFi, Attached bathroom",
			        [("villa-room-1.webp", "Bedroom")]),
			"VILLA": ("All five bedrooms, the pool, the kitchen and the garden, just "
			          "for your group.",
			          "Private pool, Full kitchen, 5 bedrooms, Garden, Barbecue, Free WiFi, Free parking",
			          [("villa-house-1.webp", "The villa"), ("villa-house-2.webp", "Pool terrace"),
			           ("villa-house-3.webp", "Living room")]),
		},
	},
	"Kamra Beach Homestay": {
		"fields": {
			"star_category": "Homestay",
			"logo_url": IMG + "beach-logo.svg",
			"hero_image": IMG + "beach-hero.webp",
			"og_image": IMG + "beach-hero.webp",
			"showcase_description": (
				"A family-run homestay two minutes from the sand, with a sea-view "
				"deck, home-cooked breakfasts and hosts who know every beach shack "
				"worth the walk."),
			"property_amenities": (
				"Sea-view deck, Home-cooked breakfast, Free WiFi, Beach towels, "
				"Bicycle hire, Free parking"),
			"free_cancel_days": 3,
			"cancellation_fee": "First Night",
		},
		"gallery": [
			("beach-sunset.webp", "Sunset on the beach"),
			("beach-hut.webp", "Beach shack nearby"),
		],
		"faqs": [],
		"room_types": {
			"TFAC": ("The top floor to yourself: an air-conditioned room with a "
			         "lounge and a peek of the sea.",
			         "Air conditioning, Sea glimpse, Lounge, Free WiFi",
			         [("beach-tfac.webp", "Top floor")]),
			"UF2R": ("Two connected rooms on the upper floor, made for families.",
			         "Two rooms, Sofa lounge, Free WiFi, Ceiling fans",
			         [("beach-uf2r.webp", "Lounge")]),
			"GFNA": ("A cool ground-floor room a few steps from the garden.",
			         "Garden access, Ceiling fan, Free WiFi",
			         [("beach-gfna.webp", "Bedroom")]),
			"GFNB": ("A ground-floor twin room, quiet and shaded.",
			         "Twin beds, Ceiling fan, Free WiFi",
			         [("beach-gfnb.webp", "Twin beds")]),
		},
	},
}


def execute():
	for prop_name, spec in PROPERTIES.items():
		if not frappe.db.exists("Property", prop_name):
			continue
		prop = frappe.get_doc("Property", prop_name)
		prop.update(spec["fields"])
		prop.booking_engine_enabled = 1
		prop.set("gallery", [{"url": IMG + f, "caption": c} for f, c in spec["gallery"]])
		prop.set("faqs", [{"question": q, "answer": a} for q, a in spec["faqs"]])
		prop.save(ignore_permissions=True)
		for code, (description, amenities, media) in spec["room_types"].items():
			rt_name = frappe.db.get_value(
				"Room Type", {"property": prop_name, "room_type_code": code})
			if not rt_name:
				continue
			rt = frappe.get_doc("Room Type", rt_name)
			rt.description = description
			rt.amenities = amenities
			rt.image = IMG + media[0][0]
			rt.set("media", [{"media_type": "Image", "url": IMG + f, "caption": c}
			                 for f, c in media])
			rt.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- seed script runs outside the request cycle
