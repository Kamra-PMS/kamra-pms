"""Seed showcase content: property description, review links, room media.

Run via bench console:
    from kamra.scripts.seed_v6 import execute; execute()
"""

import frappe

PROPERTY = "Kamra Demo Palace"

U = "https://images.unsplash.com"
MEDIA = {
	"STD": [
		(f"{U}/photo-1631049307264-da0ec9d70304?w=1200", "Standard room"),
		(f"{U}/photo-1584132967334-10e028bd69f7?w=1200", "Work desk & bath"),
	],
	"DLX": [
		(f"{U}/photo-1590490360182-c33d57733427?w=1200", "Deluxe king room"),
		(f"{U}/photo-1582719478250-c89cae4dc85b?w=1200", "Balcony seating"),
	],
	"STE": [
		(f"{U}/photo-1578683010236-d716f9a3f461?w=1200", "Suite living area"),
		(f"{U}/photo-1591088398332-8a7791972843?w=1200", "Suite bedroom"),
	],
}


def execute():
	prop = frappe.get_doc("Property", PROPERTY)
	prop.showcase_description = (
		"A calm 14-room boutique stay in the heart of Bengaluru — "
		"complimentary breakfast plans, workspaces in every room, and a "
		"front desk that answers in seconds, any hour."
	)
	prop.hero_image = f"{U}/photo-1566073771259-6a8506099945?w=1600"
	prop.star_category = "Boutique"
	prop.google_reviews_url = "https://www.google.com/maps/search/Kamra+Demo+Palace+reviews"
	prop.tripadvisor_url = "https://www.tripadvisor.in/Search?q=Kamra%20Demo%20Palace"
	prop.property_amenities = "Free WiFi, Breakfast, Airport pickup, Parking, Laundry, 24x7 desk"
	prop.booking_engine_enabled = 1
	prop.save(ignore_permissions=True)
	print("property showcase updated")

	for code, items in MEDIA.items():
		rt = frappe.get_doc("Room Type", f"{PROPERTY}-{code}")
		if rt.get("media"):
			continue
		for url, caption in items:
			rt.append("media", {"media_type": "Image", "url": url,
			                    "caption": caption})
		rt.save(ignore_permissions=True)
		print(f"media added: {code}")

	frappe.db.commit()
	print("v6 showcase seed done.")
