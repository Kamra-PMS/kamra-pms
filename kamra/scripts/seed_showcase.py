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
# (name, capacity, day rental, amenities, type, min pax, hourly, sq ft, layouts)
VENUES = [
	("Grand Ballroom", 400, 85000,
	 "Pillarless hall, stage, LED wall, in-house AV, green rooms.",
	 "Banquet Hall", 120, 14000, 6800,
	 "Theatre, Classroom, Round Table, Cluster, Floating"),
	("Garden Lawn", 600, 65000,
	 "Open-air lawn with fairy lights, marquee option, generator backup.",
	 "Lawn", 150, 11000, 12000, "Round Table, Floating, Custom"),
	("Riverside Deck", 120, 40000,
	 "Waterfront deck for cocktails and intimate ceremonies.",
	 "Poolside", 40, 7000, 2200, "Floating, Round Table"),
	("Boardroom", 20, 12000,
	 "Executive meeting room, video-conferencing, whiteboard, coffee service.",
	 "Board Room", 6, 2500, 480, "Boardroom, U-Shape"),
]

# The menu library, priced per plate the way a banquet sheet actually
# quotes. (name, code, meal, food type, style, cuisine, rate, min pax,
# courses[(course, dishes, pick, live)])
BANQUET_MENUS = [
	("Silver Veg Buffet", "SVB", "Dinner", "Veg", "Buffet", "North Indian",
	 1250, 100, [
		 ("Welcome drink", "Aam panna, Jal jeera", 1, 0),
		 ("Starters", "Paneer tikka, Hara bhara kebab, Corn seekh", 3, 0),
		 ("Main course", "Dal makhani, Paneer butter masala, Veg biryani, "
		                 "Mix veg", 0, 0),
		 ("Breads & rice", "Naan, Tandoori roti, Jeera rice", 0, 0),
		 ("Live counter", "Chaat counter", 0, 1),
		 ("Desserts", "Gulab jamun, Rasmalai, Ice cream", 2, 0),
	 ]),
	("Gold Non-Veg Buffet", "GNV", "Dinner", "Non-Veg", "Buffet",
	 "North Indian", 1850, 100, [
		 ("Starters (Veg)", "Paneer tikka, Mushroom galouti", 2, 0),
		 ("Starters (Non-veg)", "Murgh malai tikka, Fish amritsari, "
		                        "Mutton seekh", 3, 0),
		 ("Main course", "Butter chicken, Rogan josh, Dal makhani, "
		                 "Subz miloni", 0, 0),
		 ("Live counter", "Tandoor counter, Pasta counter", 0, 1),
		 ("Desserts", "Shahi tukda, Kesar phirni, Ice cream", 2, 0),
	 ]),
	("Corporate Working Lunch", "CWL", "Lunch", "Mixed", "Plated",
	 "Continental", 950, 25, [
		 ("Soup", "Cream of tomato, Sweetcorn", 1, 0),
		 ("Main", "Grilled chicken with herb rice, Penne arrabbiata", 1, 0),
		 ("Dessert", "Brownie with vanilla", 0, 0),
	 ]),
	("Hi-Tea Package", "HTP", "Hi-Tea", "Veg", "Buffet", "Indian", 550, 30, [
		 ("Savoury", "Samosa, Veg sandwich, Cocktail idli", 0, 0),
		 ("Sweet", "Mysore pak, Cookies", 0, 0),
		 ("Beverage", "Masala chai, Filter coffee", 0, 0),
	 ]),
	("Sangeet Cocktail Snacks", "SCS", "Snacks", "Mixed", "Cocktail",
	 "Global", 1450, 80, [
		 ("Passed canapes", "Chicken satay, Paneer bruschetta, "
		                    "Mini vada pav", 0, 0),
		 ("Live counter", "Kebab counter, Pani puri shots", 0, 1),
	 ]),
]

# Everything that isn't food. `chargeable=0` marks what the hotel throws
# in as standard - it still prints on the event order and the pack list.
# (name, category, uom, rate, gst, chargeable, alcohol, pack list, note).
# Cost is derived below as a share of the sell price - hire and
# sub-contract margins in this trade sit around 40-45%.
BANQUET_SERVICES = [
	("LED wall 12x8", "Audio Visual", "Per Event", 45000, 18, 1, 0, 1,
	 "Indoor P3 panel with processor and operator."),
	("Projector + 10ft screen", "Audio Visual", "Per Event", 8000, 18, 1, 0, 1,
	 "5000 lumen, HDMI and wireless."),
	("Extra cordless mic", "Audio Visual", "Per Unit", 1500, 18, 1, 0, 1, None),
	("House PA & 2 cordless mics", "Audio Visual", "Per Event", 6000, 18, 0, 0,
	 1, "Included with every hall booking."),
	("Laptop", "Audio Visual", "Per Day", 2500, 18, 1, 0, 1, None),
	("Podium with hotel branding", "Furniture & Setup", "Per Event", 2500, 18,
	 0, 0, 1, "Included on request."),
	("Stage 20x12 with carpet", "Furniture & Setup", "Per Event", 22000, 18, 1,
	 0, 1, "Includes skirting and steps."),
	("Dance floor 16x16", "Furniture & Setup", "Per Event", 18000, 18, 1, 0, 1,
	 None),
	("Registration desk & signage", "Furniture & Setup", "Per Event", 3500, 18,
	 0, 0, 1, "Standard for conferences."),
	("Floral stage decor", "Decor", "Per Event", 65000, 18, 1, 0, 1,
	 "Fresh flowers, backdrop and entrance arch."),
	("Entrance arch", "Decor", "Per Event", 15000, 18, 1, 0, 1, None),
	("Table centrepieces", "Decor", "Per Unit", 800, 18, 1, 0, 1, None),
	("DJ with light rig", "Entertainment", "Per Event", 35000, 18, 1, 0, 1,
	 "Till 23:00; local noise rules apply after."),
	("Live band (3 hrs)", "Entertainment", "Per Event", 55000, 18, 1, 0, 0,
	 None),
	("Butler service", "Staffing", "Per Pax", 120, 18, 1, 0, 0,
	 "One steward per ten covers."),
	("Valet parking", "Staffing", "Per Event", 12000, 18, 1, 0, 0, None),
	("Bar service (IMFL, on consumption)", "Alcohol", "Per Event", 0, 18, 1, 1,
	 0, "Billed on consumption; settles separately from a company bill."),
	("Corkage per bottle", "Alcohol", "Per Unit", 1200, 18, 1, 1, 0, None),
	("Unlimited soft beverages", "Beverage", "Per Pax", 250, 18, 1, 0, 0,
	 None),
	("Welcome drink on arrival", "Beverage", "Per Pax", 0, 5, 0, 0, 0,
	 "Included with every menu package."),
	("Printed menu cards", "Stationery", "Per Unit", 60, 18, 1, 0, 1, None),
	("Notepads & pens", "Stationery", "Per Pax", 0, 18, 0, 0, 1,
	 "Standard on every conference."),
]


# The banquet dish library, with real recipes against the same ingredient
# master the restaurant uses. Without these a quote reads as 100% margin,
# which is the most flattering possible lie.
# (dish, course, food type, kitchen, portions/pax, [(ingredient, qty/portion)])
BANQUET_DISHES = [
	("Paneer Tikka", "Starters", "Veg", "Tandoor", 1,
	 [("Paneer", 0.08), ("Onion", 0.03), ("Cooking Oil", 0.01)]),
	("Hara Bhara Kebab", "Starters", "Veg", "Tandoor", 1,
	 [("Mixed Vegetables", 0.07), ("Potato", 0.04), ("Cooking Oil", 0.01)]),
	("Murgh Malai Tikka", "Starters", "Non-Veg", "Tandoor", 1,
	 [("Chicken", 0.09), ("Cream", 0.02)]),
	("Fish Amritsari", "Starters", "Non-Veg", "Tandoor", 1,
	 [("Chicken", 0.08), ("Cooking Oil", 0.02)]),
	("Cream of Tomato Soup", "Soup", "Veg", "Continental", 1,
	 [("Tomato", 0.12), ("Cream", 0.03)]),
	("Sweetcorn Soup", "Soup", "Veg", "Chinese", 1,
	 [("Mixed Vegetables", 0.08), ("Milk", 0.05)]),
	("Dal Makhani", "Main Course", "Veg", "Main Kitchen", 1,
	 [("Butter", 0.02), ("Cream", 0.03), ("Tomato", 0.05)]),
	("Paneer Butter Masala", "Main Course", "Veg", "Main Kitchen", 1,
	 [("Paneer", 0.07), ("Butter", 0.02), ("Tomato", 0.06)]),
	("Butter Chicken", "Main Course", "Non-Veg", "Main Kitchen", 1,
	 [("Chicken", 0.11), ("Butter", 0.02), ("Tomato", 0.06), ("Cream", 0.02)]),
	("Subz Miloni", "Main Course", "Veg", "Main Kitchen", 1,
	 [("Mixed Vegetables", 0.11), ("Cooking Oil", 0.01)]),
	("Veg Biryani", "Rice", "Veg", "Main Kitchen", 1,
	 [("Basmati Rice", 0.12), ("Mixed Vegetables", 0.05), ("Cooking Oil", 0.01)]),
	("Jeera Rice", "Rice", "Veg", "Main Kitchen", 1,
	 [("Basmati Rice", 0.1), ("Cooking Oil", 0.01)]),
	("Gulab Jamun", "Dessert", "Veg", "Bakery", 1,
	 [("Gulab Jamun Mix", 0.05), ("Sugar", 0.04)]),
	("Rasmalai", "Dessert", "Veg", "Bakery", 1,
	 [("Milk", 0.1), ("Sugar", 0.03), ("Paneer", 0.02)]),
	("Chaat Counter", "Live Counter", "Veg", "Live Counter", 1,
	 [("Potato", 0.06), ("Onion", 0.03), ("Cooking Oil", 0.01)]),
	("Welcome Drink - Aam Panna", "Welcome Drink", "Veg", "Cold Kitchen", 1,
	 [("Lime", 0.5), ("Sugar", 0.02)]),
]

# Which dishes each menu course offers, and how many the guest may take.
# (menu, course, choose N, [(dish, is_default, supplement/pax)])
MENU_DISH_OPTIONS = [
	("Silver Veg Buffet", "Starters", 2, [
		("Paneer Tikka", 1, 0), ("Hara Bhara Kebab", 1, 0),
		("Chaat Counter", 0, 120)]),
	("Silver Veg Buffet", "Main course", 3, [
		("Dal Makhani", 1, 0), ("Paneer Butter Masala", 1, 0),
		("Subz Miloni", 1, 0), ("Veg Biryani", 0, 0)]),
	("Silver Veg Buffet", "Desserts", 1, [
		("Gulab Jamun", 1, 0), ("Rasmalai", 0, 60)]),
	("Gold Non-Veg Buffet", "Starters (Non-veg)", 2, [
		("Murgh Malai Tikka", 1, 0), ("Fish Amritsari", 1, 0)]),
	("Gold Non-Veg Buffet", "Main course", 3, [
		("Butter Chicken", 1, 0), ("Dal Makhani", 1, 0),
		("Subz Miloni", 1, 0)]),
	("Corporate Working Lunch", "Soup", 1, [
		("Cream of Tomato Soup", 1, 0), ("Sweetcorn Soup", 0, 0)]),
]


# Kitchen stock: (ingredient, uom, cost_per_unit, category)
INGREDIENTS = [
	("Paneer", "kg", 400, "Dairy"),
	("Chicken", "kg", 320, "Meat"),
	("Butter", "kg", 520, "Dairy"),
	("Cream", "L", 260, "Dairy"),
	("Tomato", "kg", 40, "Produce"),
	("Onion", "kg", 35, "Produce"),
	("Basmati Rice", "kg", 120, "Dry Goods"),
	("Mixed Vegetables", "kg", 60, "Produce"),
	("Dosa Batter", "L", 80, "Dry Goods"),
	("Potato", "kg", 30, "Produce"),
	("Gulab Jamun Mix", "kg", 180, "Dry Goods"),
	("Sugar", "kg", 45, "Dry Goods"),
	("Milk", "L", 60, "Dairy"),
	("Coffee Powder", "kg", 900, "Dry Goods"),
	("Lime", "pc", 4, "Bar"),
	("Soda", "bottle", 25, "Bar"),
	("Kingfisher Bottle", "bottle", 130, "Bar"),
	("Cooking Oil", "L", 140, "Dry Goods"),
	("Garam Masala", "kg", 700, "Dry Goods"),
]

# What one portion consumes: menu item -> [(ingredient, qty)]
RECIPES = {
	"Paneer Tikka": [("Paneer", 0.2), ("Onion", 0.05), ("Cream", 0.03),
	                 ("Garam Masala", 0.005)],
	"Butter Chicken": [("Chicken", 0.25), ("Butter", 0.04), ("Cream", 0.05),
	                   ("Tomato", 0.15), ("Garam Masala", 0.008)],
	"Masala Dosa": [("Dosa Batter", 0.15), ("Potato", 0.1), ("Onion", 0.03),
	                ("Cooking Oil", 0.02)],
	"Veg Biryani": [("Basmati Rice", 0.15), ("Mixed Vegetables", 0.12),
	                ("Onion", 0.04), ("Garam Masala", 0.006)],
	"Gulab Jamun": [("Gulab Jamun Mix", 0.06), ("Sugar", 0.05), ("Milk", 0.02)],
	"Cold Coffee": [("Milk", 0.2), ("Coffee Powder", 0.01), ("Sugar", 0.02)],
	"Fresh Lime Soda": [("Lime", 1), ("Soda", 1), ("Sugar", 0.015)],
	# the 1:1 case - a bar is inventory's easiest win, and it proves the model
	# handles stock that is never cooked at all
	"Kingfisher Beer": [("Kingfisher Bottle", 1)],
}

# Opening stock per outlet: (ingredient, qty, par_level). Paneer opens BELOW
# par on purpose, so the demo lands on a live amber flag with an 86 candidate
# to click rather than a screen of green.
OPENING = {
	"The Terrace Restaurant": [
		("Paneer", 0.4, 2), ("Chicken", 14, 5), ("Butter", 6, 2),
		("Cream", 8, 3), ("Tomato", 12, 4), ("Onion", 20, 6),
		("Basmati Rice", 25, 8), ("Mixed Vegetables", 9, 4),
		("Dosa Batter", 10, 4), ("Potato", 15, 5),
		("Gulab Jamun Mix", 3, 1), ("Sugar", 12, 4), ("Milk", 18, 6),
		("Cooking Oil", 20, 5), ("Garam Masala", 2, 0.5),
	],
	"Poolside Bar": [
		("Lime", 60, 20), ("Soda", 48, 12), ("Kingfisher Bottle", 72, 24),
		("Milk", 10, 4), ("Coffee Powder", 2, 0.5), ("Sugar", 5, 2),
	],
}

# POS: (outlet_name, outlet_type, gst%,
#       [ (item, category, price, veg, station, course, allergens, img) ])
POS = [
	("The Terrace Restaurant", "Restaurant", 5, [
		("Masala Dosa", "South Indian", 220, 1, "Kitchen", "Main", "Gluten",
		 "https://images.unsplash.com/photo-1630383249896-424e482df921?w=400"),
		("Butter Chicken", "North Indian", 480, 0, "Tandoor", "Main", "Nuts, Dairy",
		 "https://images.unsplash.com/photo-1603894584373-5ac82b2ae398?w=400"),
		("Paneer Tikka", "Starters", 360, 1, "Tandoor", "Starter", "Dairy",
		 "https://images.unsplash.com/photo-1599487488170-d11ec9c172f0?w=400"),
		("Veg Biryani", "Rice", 340, 1, "Kitchen", "Main", None,
		 "https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=400"),
		("Gulab Jamun", "Desserts", 160, 1, "Kitchen", "Dessert", "Nuts, Dairy",
		 "https://images.unsplash.com/photo-1666190092159-3171cf0fbb12?w=400"),
	]),
	("Poolside Bar", "Bar", 18, [
		("Cold Coffee", "Beverages", 180, 1, "Bar", "Drink", "Dairy",
		 "https://images.unsplash.com/photo-1461023058943-07fcbe16d735?w=400"),
		("Fresh Lime Soda", "Beverages", 120, 1, "Bar", "Drink", None,
		 "https://images.unsplash.com/photo-1523371054106-bbf80586c33c?w=400"),
		("Kingfisher Beer", "Alcohol", 350, 1, "Bar", "Drink", "Gluten",
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
	for (name, cap, price, amenities, vtype, min_cap, hourly, sqft,
	     layouts) in VENUES:
		if frappe.db.exists("Venue", {"property": PROPERTY, "venue_name": name}):
			continue
		frappe.get_doc({
			"doctype": "Venue",
			"property": PROPERTY,
			"venue_name": name,
			"venue_type": vtype,
			"capacity": cap,
			"min_capacity": min_cap,
			"area_sqft": sqft,
			"base_price": price,
			"hourly_rate": hourly,
			"min_hours": 4,
			"gst_rate": 18,
			"setup_styles": layouts,
			"amenities": amenities,
		}).insert(ignore_permissions=True)
		added_venue += 1

	added_bq = seed_banquets()

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
		for item, cat, price, veg, station, course, allergens, img in items:
			existing = frappe.db.exists("Menu Item", {"outlet": outlet, "item_name": item})
			if existing:  # upgrade menus that predate coursing and allergens
				frappe.db.set_value("Menu Item", existing, {
					"course": course, "allergens": allergens, "prep_station": station})
				continue
			frappe.get_doc({
				"doctype": "Menu Item", "property": PROPERTY, "outlet": outlet,
				"item_name": item, "category": cat, "price": price,
				"is_veg": veg, "available": 1, "prep_station": station,
				"course": course, "allergens": allergens,
				"is_alcohol": 1 if cat == "Alcohol" else 0, "image": img,
			}).insert(ignore_permissions=True)
			added_item += 1

	# kitchen stock: the ingredient master, then a recipe per dish, then what
	# each outlet opens with
	from kamra import inventory

	ing_id = {}
	for name, uom, cost, cat in INGREDIENTS:
		existing = frappe.db.exists("Ingredient", {"property": PROPERTY,
		                                           "ingredient_name": name})
		if existing:  # keep costs and units current on a re-run
			frappe.db.set_value("Ingredient", existing,
			                    {"uom": uom, "cost_per_unit": cost, "category": cat})
			ing_id[name] = existing
			continue
		ing_id[name] = frappe.get_doc({
			"doctype": "Ingredient", "property": PROPERTY, "ingredient_name": name,
			"uom": uom, "cost_per_unit": cost, "category": cat, "is_active": 1,
		}).insert(ignore_permissions=True).name

	for item_name, lines in RECIPES.items():
		mi = frappe.db.exists("Menu Item", {"property": PROPERTY,
		                                    "item_name": item_name})
		if not mi:
			continue
		doc = frappe.get_doc("Menu Item", mi)
		doc.set("recipe", [{"ingredient": ing_id[i], "qty": q} for i, q in lines])
		doc.save(ignore_permissions=True)

	for outlet_name, opening in OPENING.items():
		outlet = frappe.db.exists("POS Outlet", {"property": PROPERTY,
		                                         "outlet_name": outlet_name})
		if not outlet:
			continue
		for name, qty, par in opening:
			row = f"{outlet}::{ing_id[name]}"
			if frappe.db.exists("Ingredient Stock", row):
				continue  # already opened - never re-stock a live count
			# through _apply_move, not a raw write, so the demo's ledger is
			# real and the opening balance can be explained like any other move
			inventory._apply_move(PROPERTY, outlet, ing_id[name], qty, "Opening",
			                      note="Opening stock (demo seed)")
			frappe.db.set_value("Ingredient Stock", row, "par_level", par,
			                    update_modified=False)

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

	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- batch/seed/migration script runs outside the request cycle; explicit commit persists the staged writes
	print(f"Showcase seed: +{added_exp} experiences, +{added_venue} venues, "
	      f"+{added_outlet} outlets, +{added_item} menu items, "
	      f"+{added_rate} laundry rates, +{added_ticket} tickets, "
	      f"+{added_ho} handovers, +{added_lnd} laundry orders, {added_bq} "
	      f"{extra} on '{PROPERTY}'.")


def seed_banquets():
	"""The banquet catalogue and a pipeline that looks like a real month:
	an enquiry still being chased, a tentative hold on a Saturday, a
	confirmed wedding with an advance in and an event order to print, and
	one that went to a competitor - so the funnel and the conversion rate
	aren't hypothetical."""
	from frappe.utils import add_days, nowdate

	added_menu = 0
	for name, code, meal, food, style, cuisine, rate, min_pax, courses in \
			BANQUET_MENUS:
		if frappe.db.exists("Banquet Menu",
		                    {"property": PROPERTY, "menu_name": name}):
			continue
		frappe.get_doc({
			"doctype": "Banquet Menu", "property": PROPERTY,
			"menu_name": name, "menu_code": code, "meal_period": meal,
			"food_type": food, "service_style": style, "cuisine": cuisine,
			"rate_per_pax": rate, "min_pax": min_pax, "gst_rate": 5,
			"inclusions": "Crockery, cutlery, service staff and "
			              "unlimited water.",
			"exclusions": "Alcohol, live counters beyond those listed, "
			              "and taxes.",
			"courses": [{"course": c, "dishes": d, "choice_of": pick,
			             "is_live_counter": live}
			            for c, d, pick, live in courses],
		}).insert(ignore_permissions=True)
		added_menu += 1

	added_svc = 0
	for (name, cat, uom, rate, gst, chargeable, alcohol, pack,
	     note) in BANQUET_SERVICES:
		if frappe.db.exists("Banquet Service Item",
		                    {"property": PROPERTY, "item_name": name}):
			continue
		frappe.get_doc({
			"doctype": "Banquet Service Item", "property": PROPERTY,
			"item_name": name, "category": cat, "uom": uom, "rate": rate,
			"gst_rate": gst, "chargeable": chargeable, "is_alcohol": alcohol,
			"on_pack_list": pack, "description": note,
			"cost_rate": round(rate * 0.58, 2), "cost_gst_rate": 18,
		}).insert(ignore_permissions=True)
		added_svc += 1

	added_dish = 0
	for name, course, food, kitchen, portions, recipe in BANQUET_DISHES:
		if frappe.db.exists("Banquet Dish", {"property": PROPERTY,
		                                     "dish_name": name}):
			continue
		rows, cost = [], 0.0
		for ing_name, qty in recipe:
			ing = frappe.db.get_value(
				"Ingredient", {"property": PROPERTY, "ingredient_name": ing_name})
			if not ing:
				continue
			rows.append({"ingredient": ing, "qty": qty})
			cost += qty * float(frappe.db.get_value(
				"Ingredient", ing, "cost_per_unit") or 0)
		frappe.get_doc({
			"doctype": "Banquet Dish", "property": PROPERTY, "dish_name": name,
			"course_type": course, "food_type": food, "kitchen": kitchen,
			"portion_per_pax": portions, "recipe": rows,
			"cost_per_portion": round(cost, 4),
		}).insert(ignore_permissions=True)
		added_dish += 1

	# hang the dishes off each menu's courses so a customer can choose
	for menu_name, course, choose, options in MENU_DISH_OPTIONS:
		menu = frappe.db.get_value(
			"Banquet Menu", {"property": PROPERTY, "menu_name": menu_name})
		if not menu:
			continue
		doc = frappe.get_doc("Banquet Menu", menu)
		row = next((c for c in doc.courses
		            if c.course.lower().startswith(course.lower()[:8])), None)
		if not row:
			continue
		row.choice_of = choose
		for dish_name, default, supplement in options:
			dish = frappe.db.get_value(
				"Banquet Dish", {"property": PROPERTY, "dish_name": dish_name})
			if not dish or any(d.dish == dish and d.course == row.course
			                   for d in doc.dish_options):
				continue
			doc.append("dish_options", {
				"course": row.course, "dish": dish, "is_default": default,
				"supplement_per_pax": supplement})
		doc.save(ignore_permissions=True)

	if frappe.db.exists("Venue Booking", {"property": PROPERTY,
	                                      "event_name": "Sharma-Verma Reception"}):
		return (f"+{added_menu} banquet menus, +{added_svc} banquet services, "
		        f"+{added_dish} dishes")

	from kamra import banquet as bq

	def venue(name):
		return frappe.db.get_value(
			"Venue", {"property": PROPERTY, "venue_name": name})

	def menu(name):
		return frappe.db.get_value(
			"Banquet Menu", {"property": PROPERTY, "menu_name": name})

	def service(name):
		return frappe.db.get_value(
			"Banquet Service Item", {"property": PROPERTY, "item_name": name})

	# ── the wedding that's sold: advance in, event order due ────────────
	wedding = bq.create_enquiry(
		PROPERTY, venue("Grand Ballroom"), add_days(nowdate(), 21),
		"Anita Sharma", event_type="Reception", attendees=320,
		customer_phone="+91 98450 11223", start_time="19:00",
		end_time="23:30", source="Referral",
		requirements="320 pax reception, gold non-veg buffet, floral stage, "
		             "DJ till 11, green room for the bride.")["function"]
	bq.update_function(wedding, {
		"event_name": "Sharma-Verma Reception", "pax_guaranteed": 300,
		"setup_style": "Round Table", "billing_name": "Anita Sharma",
		"setup_notes": "Stage at the north end, dance floor centre, "
		               "buffet along the east wall.",
	})
	bq.add_menu(wedding, menu("Gold Non-Veg Buffet"))
	for item in ("Floral stage decor", "DJ with light rig",
	             "Stage 20x12 with carpet", "Dance floor 16x16",
	             "LED wall 12x8", "Valet parking"):
		bq.add_service(wedding, service(item))
	for freebie in ("House PA & 2 cordless mics", "Podium with hotel branding",
	                "Welcome drink on arrival"):
		bq.add_service(wedding, service(freebie), chargeable=0)
	# choose the dishes, so the demo's margin is a number and not a guess
	gold = menu("Gold Non-Veg Buffet")
	try:
		picks = []
		for c in bq.menu_choices(wedding, gold)["courses"]:
			for o in c["options"][: (c["choice_of"] or len(c["options"]))]:
				picks.append({"course": c["course"], "dish": o["dish"],
				              "supplement_per_pax": o["supplement_per_pax"]})
		if picks:
			bq.compose_menu(wedding, gold, picks)
	except Exception:
		pass  # a demo seed must never block on the trimmings

	bq.negotiate(wedding, venue_rental=72000,
	             note="Matched the competitor on the hall")
	bq.negotiate(wedding, discount_amount=40000,
	             note="Owner approved 40k off to close it")
	bq.generate_quote(wedding, valid_days=10)
	bq.set_status(wedding, "Confirmed")
	bq.default_payment_terms(wedding)
	terms = frappe.get_doc("Venue Booking", wedding).payment_terms
	if terms:
		bq.record_receipt(wedding, terms[0].amount, mode="Bank Transfer",
		                  kind="Advance", reference="UTR9911002233",
		                  settle_term=terms[0].name)

	# ── the conference still being negotiated ───────────────────────────
	conf = bq.create_enquiry(
		PROPERTY, venue("Boardroom"), add_days(nowdate(), 9),
		"Priya Menon", event_type="Training", attendees=18,
		customer_phone="+91 99001 44556", customer_email="priya@acme.example",
		start_time="09:30", end_time="17:30", source="Email",
		requirements="Two-day leadership offsite, U-shape, working lunch, "
		             "projector.")["function"]
	bq.update_function(conf, {
		"event_name": "Acme Leadership Offsite", "setup_style": "U-Shape",
		"end_date": add_days(nowdate(), 10), "pax_guaranteed": 18,
		"gstin": "29AABCU9603R1ZM", "place_of_supply": "Karnataka",
	})
	bq.add_menu(conf, menu("Corporate Working Lunch"))
	bq.add_menu(conf, menu("Hi-Tea Package"))
	bq.add_service(conf, service("Projector + 10ft screen"))
	bq.add_service(conf, service("Notepads & pens"), chargeable=0)
	bq.add_service(conf, service("Registration desk & signage"), chargeable=0)
	bq.save_open_items(conf, [
		{"title": "Second day's lunch - veg only or mixed?",
		 "owner_side": "Client", "due_date": add_days(nowdate(), 3),
		 "price_impact": 0, "status": "Open"},
		{"title": "Airport transfers for six delegates",
		 "detail": "They've asked; we haven't priced it yet.",
		 "owner_side": "Hotel", "due_date": add_days(nowdate(), 2),
		 "price_impact": 9000, "status": "Open"},
	])
	bq.generate_quote(conf, valid_days=7)
	bq.set_status(conf, "Tentative",
	              tentative_until=add_days(nowdate(), 4))

	# ── the enquiry that's gone quiet ───────────────────────────────────
	quiet = bq.create_enquiry(
		PROPERTY, venue("Garden Lawn"), add_days(nowdate(), 45),
		"Rakesh Iyer", event_type="Sangeet", attendees=250,
		customer_phone="+91 98860 77889", start_time="18:00",
		end_time="23:00", source="Website", follow_up_days=-3,
		requirements="Sangeet on the lawn, cocktail snacks, DJ.")["function"]
	bq.add_menu(quiet, menu("Sangeet Cocktail Snacks"))
	bq.add_service(quiet, service("DJ with light rig"))

	# ── the one that got away ───────────────────────────────────────────
	lost = bq.create_enquiry(
		PROPERTY, venue("Riverside Deck"), add_days(nowdate(), 30),
		"Fatima Qureshi", event_type="Engagement", attendees=90,
		customer_phone="+91 90080 33221", source="Walk-in")["function"]
	bq.set_status(lost, "Lost",
	              reason="Went to a competitor on price")

	return (f"+{added_menu} banquet menus, +{added_svc} banquet services, "
	        f"+4 functions")


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

	# ── WhatsApp: connection staged in admin + a sample guest thread ────
	added_wa = 0
	if not frappe.db.exists("Channel Provider Connection", {
			"property": PROPERTY, "channel": "WhatsApp",
			"provider": "Meta Business"}):
		frappe.get_doc({
			"doctype": "Channel Provider Connection", "property": PROPERTY,
			"channel": "WhatsApp", "provider": "Meta Business",
			"active": 0,  # flip on after entering your own Meta credentials
			"phone_number": "+91 98450 00000",
			"external_account_id": "demo-phone-number-id",
			"meta_language": "en",
			"tpl_booking_confirmation": "kamra_booking_confirmation",
			"tpl_precheckin": "kamra_precheckin_link",
			"tpl_payment_request": "kamra_payment_request",
			"notes": "Demo connection - enter your Meta Cloud API phone "
			         "number ID and token, then tick Active.",
		}).insert(ignore_permissions=True)
		added_wa += 1
	if not frappe.db.exists("WhatsApp Message", {"property": PROPERTY}):
		demo_guest = frappe.get_all(
			"Guest", filters={"phone": ("!=", "")},
			fields=["name", "first_name", "phone"], limit=1)
		g = demo_guest[0] if demo_guest else None
		thread = [
			("Outbound", "Template", "kamra_booking_confirmation", "Sent",
			 "Rohan · Kamra Demo Palace · 2026-07-24 · 2026-07-26"),
			("Outbound", "Template", "kamra_precheckin_link", "Sent",
			 "Rohan · https://demo.kamrapms.com/kamra/checkin/…"),
			("Inbound", "Text", None, "Received",
			 "Hi! Could we get a late checkout on Sunday?"),
			("Outbound", "Text", None, "Sent",
			 "Of course - late checkout till 2 PM is confirmed for you."),
		]
		for direction, mtype, tpl, status, content in thread:
			frappe.get_doc({
				"doctype": "WhatsApp Message", "property": PROPERTY,
				"direction": direction, "message_type": mtype,
				"template_name": tpl, "status": status,
				"content": content,
				"to_number": (g["phone"] if g and direction == "Outbound"
				              else "+91 98450 00000"),
				"from_number": ("+91 98450 00000" if direction == "Outbound"
				                else (g["phone"] if g else "+91 98000 11223")),
				"guest": g["name"] if g else None,
			}).insert(ignore_permissions=True)
			added_wa += 1

	return (f"+{filled} profile fields, +{tiers} demand tiers, "
	        f"+{added_story} today-stays, +{added_tres} table res, "
	        f"+{added_block} blocks, +{added_lf} lost&found, "
	        f"+{added_wa} whatsapp")
