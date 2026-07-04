"""Seed a second property (portfolio demo) + restrict the front-desk demo
user to the first property via Frappe User Permissions.

Run via bench console:
    from kamra.scripts.seed_property2 import execute; execute()
"""

import frappe

P2 = "Kamra Beach House"
P1 = "Kamra Demo Palace"


def execute():
	if not frappe.db.exists("Property", P2):
		frappe.get_doc({
			"doctype": "Property",
			"property_name": P2,
			"city": "Gokarna",
			"state": "Karnataka",
			"phone": "+91 83 4000 2000",
			"email": "beach@kamra.local",
			"gstin": "29ABCDE1234F2Z4",
			"star_category": "Homestay",
			"showcase_description": "Six rooms, one cliff, endless sea. "
			                        "Kamra Beach House is barefoot luxury on the Gokarna coast.",
			"hero_image": "https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?w=1600",
			"property_amenities": "Sea view, Cafe, Free WiFi, Hammocks",
		}).insert(ignore_permissions=True)
		print(f"created property: {P2}")

		for code, label, price, rooms in [
			("SEA", "Sea View", 5500, ["S1", "S2", "S3"]),
			("GDN", "Garden Cottage", 3200, ["G1", "G2", "G3"]),
		]:
			rt = frappe.get_doc({
				"doctype": "Room Type", "property": P2,
				"room_type_code": code, "room_type_name": label,
				"base_price": price, "base_occupancy": 2,
				"extra_adult_price": round(price * 0.2),
				"adults_capacity": 2, "children_capacity": 1,
				"bed_type": "Queen",
				"amenities": "WiFi, Fan, Hot water",
			}).insert(ignore_permissions=True)
			for num in rooms:
				frappe.get_doc({
					"doctype": "Room", "property": P2, "room_number": num,
					"room_type": rt.name, "floor": "G",
				}).insert(ignore_permissions=True)
		frappe.get_doc({
			"doctype": "Meal Plan", "property": P2, "code": "CP",
			"label": "Breakfast Included", "price_per_adult": 250,
			"is_default": 1,
		}).insert(ignore_permissions=True)
		print("room types, rooms, meal plan seeded")

	# Ravi (front desk) works only at the Palace
	if not frappe.db.exists(
		"User Permission",
		{"user": "frontdesk@kamra.local", "allow": "Property"},
	):
		frappe.get_doc({
			"doctype": "User Permission",
			"user": "frontdesk@kamra.local",
			"allow": "Property",
			"for_value": P1,
			"apply_to_all_doctypes": 1,
		}).insert(ignore_permissions=True)
		print("frontdesk@kamra.local restricted to Kamra Demo Palace")

	frappe.db.commit()
	print("Portfolio demo ready.")
