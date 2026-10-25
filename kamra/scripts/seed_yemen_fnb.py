"""Halal F&B for Yemen demo properties: two outlets, a full menu, recipes
and opening stock.

Idempotent. Re-running adds what's missing and never zeroes live stock.
Menu items stay available=1 with no expiry. Designed for demoyemen
(Demo Yemen) — that site is not a playground, so reset_demo will not wipe
it; this seed also re-creates the same outlets if a Yemen property is
ever rebuilt via seed_demo.

Run:
    bench --site demoyemen.kamrapms.com execute \\
        kamra.scripts.seed_yemen_fnb.execute
"""

from __future__ import annotations

import frappe

from kamra.localization import pack_for

DEFAULT_PROPERTY = "Demo Yemen"

# Two hotel F&B outlets — both Restaurant (no alcohol).
# (outlet_name, outlet_type, tables_layout,
#  [(item, category, price_yer, veg, station, course, allergens, description, img)])
POS = [
	("Al Rawdha Restaurant", "Restaurant", "\n".join([
		"[Main Hall]",
		"T1:2", "T2:4", "T3:4", "T4:2", "T5:4", "T6:6", "T7:4", "T8:8",
		"[Family]",
		"F1:6", "F2:8", "F3:10",
		"[Majlis]",
		"M1:8", "M2:12",
		"[Private Dining]",
		"PDR:14",
	]), [
		("Lentil Soup", "Soups", 1200, 1, "Kitchen", "Starter", None,
		 "Halal Yemeni shorbat adas with cumin and lemon.",
		 "https://images.unsplash.com/photo-1547592166-23ac45744acd?w=400"),
		("Shafout", "Starters", 1800, 1, "Kitchen", "Starter", "Dairy",
		 "Halal layered bread with yoghurt, hulba and sahawiq.",
		 "https://images.unsplash.com/photo-1601050690597-df0568f70950?w=400"),
		("Hummus with Olive Oil", "Starters", 1500, 1, "Kitchen", "Starter", "Sesame",
		 "Halal chickpea hummus, tahini and warm khubz.",
		 "https://images.unsplash.com/photo-1571997478779-2adcbbe9ab2f?w=400"),
		("Sambusa (meat)", "Starters", 1600, 0, "Kitchen", "Starter", "Gluten",
		 "Halal minced-lamb sambusa, three pieces.",
		 "https://images.unsplash.com/photo-1601050690117-e224a5132568?w=400"),
		("Chicken Mandi", "Mains", 5500, 0, "Kitchen", "Main", None,
		 "Halal charcoal mandi chicken on fragrant basmati.",
		 "https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=400"),
		("Lamb Haneeth", "Mains", 7200, 0, "Kitchen", "Main", None,
		 "Halal slow-oven haneeth with rice and broth.",
		 "https://images.unsplash.com/photo-1604908176997-125f25cc6f3d?w=400"),
		("Saltah", "Mains", 4200, 0, "Kitchen", "Main", "Dairy",
		 "Halal stone-bowl saltah with fenugreek froth and sahawiq.",
		 "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=400"),
		("Fahsa", "Mains", 4800, 0, "Kitchen", "Main", None,
		 "Halal lamb fahsa stew with hulba, served bubbling.",
		 "https://images.unsplash.com/photo-1574484284002-952d92456975?w=400"),
		("Zurbian", "Mains", 6500, 0, "Kitchen", "Main", "Dairy, Nuts",
		 "Halal layered rice with spiced lamb and raisins.",
		 "https://images.unsplash.com/photo-1589302168068-964664d93dc0?w=400"),
		("Grilled Hammour", "Mains", 6800, 0, "Kitchen", "Main", "Fish",
		 "Halal Gulf hammour, lemon and herb rice.",
		 "https://images.unsplash.com/photo-1519708227418-c8fd9a32b7a2?w=400"),
		("Chicken Kabsa", "Mains", 5200, 0, "Kitchen", "Main", None,
		 "Halal kabsa rice with roasted chicken and daqqous.",
		 "https://images.unsplash.com/photo-1599487488170-d11ec9c172f0?w=400"),
		("Vegetable Aseed", "Mains", 2800, 1, "Kitchen", "Main", None,
		 "Halal aseed porridge with vegetable broth (no meat).",
		 "https://images.unsplash.com/photo-1547592166-23ac45744acd?w=400"),
		("Mutabbaq (veg)", "Mains", 2200, 1, "Kitchen", "Main", "Gluten, Egg",
		 "Halal stuffed flatbread with egg, leek and cheese.",
		 "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=400"),
		("Fattoush", "Salads", 1800, 1, "Kitchen", "Starter", "Gluten",
		 "Halal Levantine salad with crisp khubz.",
		 "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=400"),
		("Bint al-Sahn", "Desserts", 2400, 1, "Kitchen", "Dessert", "Dairy, Gluten, Egg",
		 "Halal layered honey pastry with nigella.",
		 "https://images.unsplash.com/photo-1488477181946-6428a0291777?w=400"),
		("Kunafa", "Desserts", 2600, 1, "Kitchen", "Dessert", "Dairy, Gluten, Nuts",
		 "Halal cheese kunafa with pistachio.",
		 "https://images.unsplash.com/photo-1571877227200-a0d98ea607e9?w=400"),
		("Fresh Dates & Nuts", "Desserts", 1400, 1, "Kitchen", "Dessert", "Nuts",
		 "Halal Yemeni dates with mixed nuts.",
		 "https://images.unsplash.com/photo-1606313564200-e75d5e30476c?w=400"),
		("Qishr", "Beverages", 900, 1, "Bar", "Drink", None,
		 "Halal Yemeni coffee-husk tea with ginger.",
		 "https://images.unsplash.com/photo-1544787219-7f47ccb76574?w=400"),
		("Fresh Orange Juice", "Beverages", 1200, 1, "Bar", "Drink", None,
		 "Halal freshly pressed orange juice.",
		 "https://images.unsplash.com/photo-1621506289937-a8e4df240d0b?w=400"),
		("Laban", "Beverages", 800, 1, "Bar", "Drink", "Dairy",
		 "Halal salted yoghurt drink.",
		 "https://images.unsplash.com/photo-1571212515416-fef01fc43637?w=400"),
	]),
	("Bab al-Yemen Cafe", "Restaurant", "\n".join([
		"[Counter]",
		"C1:2", "C2:2", "C3:2", "C4:4",
		"[Lounge]",
		"L1:4", "L2:4", "L3:6", "L4:4", "L5:2",
		"[Terrace]",
		"TR1:2", "TR2:2", "TR3:4", "TR4:4",
	]), [
		("Yemeni Qahwa", "Coffee", 1000, 1, "Bar", "Drink", None,
		 "Halal lightly roasted Yemeni coffee with cardamom.",
		 "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=400"),
		("Qishr Spiced", "Coffee", 900, 1, "Bar", "Drink", None,
		 "Halal coffee-husk brew with cinnamon and ginger.",
		 "https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?w=400"),
		("Adeni Chai", "Tea", 700, 1, "Bar", "Drink", "Dairy",
		 "Halal milky Adeni tea with cardamom.",
		 "https://images.unsplash.com/photo-1571934811356-5cc061b6821f?w=400"),
		("Mint Tea", "Tea", 600, 1, "Bar", "Drink", None,
		 "Halal fresh mint tea.",
		 "https://images.unsplash.com/photo-1556679343-c7306c1976bc?w=400"),
		("Mango Juice", "Juices", 1300, 1, "Bar", "Drink", None,
		 "Halal fresh mango juice.",
		 "https://images.unsplash.com/photo-1546173159-315724a31696?w=400"),
		("Lemon Mint", "Juices", 1100, 1, "Bar", "Drink", None,
		 "Halal lemonade with mint.",
		 "https://images.unsplash.com/photo-1523371054106-bbf80586c33c?w=400"),
		("Ful Medames", "Breakfast", 1800, 1, "Kitchen", "Main", None,
		 "Halal slow-cooked fava beans with olive oil and egg optional.",
		 "https://images.unsplash.com/photo-1604329760661-e71dc83f8f26?w=400"),
		("Shakshuka", "Breakfast", 2200, 1, "Kitchen", "Main", "Egg",
		 "Halal eggs poached in tomato and pepper sauce.",
		 "https://images.unsplash.com/photo-1590412200988-a436970781fa?w=400"),
		("Cheese Mutabbaq", "Snacks", 2000, 1, "Kitchen", "Main", "Gluten, Dairy, Egg",
		 "Halal cheese-filled mutabbaq.",
		 "https://images.unsplash.com/photo-1509722747041-616f39b57569?w=400"),
		("Meat Sambusa Plate", "Snacks", 1900, 0, "Kitchen", "Starter", "Gluten",
		 "Halal lamb sambusa, four pieces with sahawiq.",
		 "https://images.unsplash.com/photo-1601050690597-df0568f70950?w=400"),
		("Chicken Shawarma Wrap", "Snacks", 2800, 0, "Kitchen", "Main", "Gluten, Dairy",
		 "Halal chicken shawarma in khubz with garlic sauce.",
		 "https://images.unsplash.com/photo-1529006557810-274b9b2fc783?w=400"),
		("Falafel Plate", "Snacks", 2000, 1, "Kitchen", "Main", "Sesame",
		 "Halal falafel, hummus, salad and pickles.",
		 "https://images.unsplash.com/photo-1593001874117-c99c800e3eb7?w=400"),
		("Zaatar Manakish", "Bakery", 1500, 1, "Kitchen", "Main", "Gluten",
		 "Halal zaatar flatbread from the tandoor.",
		 "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=400"),
		("Honey Cake Slice", "Sweets", 1400, 1, "Kitchen", "Dessert", "Dairy, Gluten, Egg, Nuts",
		 "Halal honey cake with pistachio.",
		 "https://images.unsplash.com/photo-1578985545062-69928b1d9587?w=400"),
		("Basbousa", "Sweets", 1200, 1, "Kitchen", "Dessert", "Dairy, Gluten, Nuts",
		 "Halal semolina cake soaked in syrup.",
		 "https://images.unsplash.com/photo-1614707267537-b85aaf00c0b7?w=400"),
		("Bottled Water", "Beverages", 400, 1, "Bar", "Drink", None,
		 "Still mineral water 500ml.",
		 "https://images.unsplash.com/photo-1548839140-29a749e1cf4d?w=400"),
	]),
]

INGREDIENTS = [
	("Basmati Rice", "kg", 800, "Dry Goods"),
	("Chicken (halal)", "kg", 2200, "Meat"),
	("Lamb (halal)", "kg", 4500, "Meat"),
	("Hammour Fillet", "kg", 5500, "Seafood"),
	("Onion", "kg", 350, "Produce"),
	("Tomato", "kg", 400, "Produce"),
	("Potato", "kg", 300, "Produce"),
	("Garlic", "kg", 900, "Produce"),
	("Fenugreek (hulba)", "kg", 1800, "Dry Goods"),
	("Sahawiq Mix", "kg", 1200, "Dry Goods"),
	("Yoghurt", "L", 700, "Dairy"),
	("Milk", "L", 600, "Dairy"),
	("Butter Ghee", "kg", 2800, "Dairy"),
	("Chickpeas", "kg", 650, "Dry Goods"),
	("Fava Beans", "kg", 550, "Dry Goods"),
	("Lentils", "kg", 500, "Dry Goods"),
	("Flatbread Flour", "kg", 400, "Dry Goods"),
	("Cooking Oil", "L", 900, "Dry Goods"),
	("Mixed Spices (hawaij)", "kg", 3200, "Dry Goods"),
	("Cardamom", "kg", 8000, "Dry Goods"),
	("Coffee Beans (Yemeni)", "kg", 6000, "Dry Goods"),
	("Coffee Husk (qishr)", "kg", 2500, "Dry Goods"),
	("Tea Leaves", "kg", 1800, "Dry Goods"),
	("Fresh Mint", "kg", 1200, "Produce"),
	("Dates", "kg", 1500, "Dry Goods"),
	("Pistachio", "kg", 9000, "Dry Goods"),
	("Honey", "kg", 3500, "Dry Goods"),
	("Orange", "pc", 150, "Produce"),
	("Mango", "pc", 400, "Produce"),
	("Lemon", "pc", 100, "Produce"),
	("Eggs", "pc", 80, "Dairy"),
	("Cheese (akkawi)", "kg", 2500, "Dairy"),
	("Konafeh Pastry", "kg", 2000, "Dry Goods"),
	("Bottled Water 500ml", "bottle", 80, "Dry Goods"),
	("Falafel Mix", "kg", 900, "Dry Goods"),
	("Shawarma Spice", "kg", 2800, "Dry Goods"),
]

RECIPES = {
	"Chicken Mandi": [
		("Chicken (halal)", 0.35), ("Basmati Rice", 0.2), ("Onion", 0.05),
		("Mixed Spices (hawaij)", 0.01), ("Cooking Oil", 0.02),
	],
	"Lamb Haneeth": [
		("Lamb (halal)", 0.4), ("Basmati Rice", 0.2), ("Onion", 0.06),
		("Mixed Spices (hawaij)", 0.012), ("Garlic", 0.01),
	],
	"Saltah": [
		("Lamb (halal)", 0.15), ("Fenugreek (hulba)", 0.02), ("Yoghurt", 0.05),
		("Sahawiq Mix", 0.02), ("Onion", 0.04),
	],
	"Fahsa": [
		("Lamb (halal)", 0.3), ("Fenugreek (hulba)", 0.015), ("Onion", 0.05),
		("Sahawiq Mix", 0.02), ("Garlic", 0.01),
	],
	"Zurbian": [
		("Lamb (halal)", 0.35), ("Basmati Rice", 0.22), ("Yoghurt", 0.08),
		("Onion", 0.05), ("Mixed Spices (hawaij)", 0.01), ("Pistachio", 0.01),
	],
	"Grilled Hammour": [
		("Hammour Fillet", 0.3), ("Basmati Rice", 0.15), ("Lemon", 1),
		("Cooking Oil", 0.02), ("Garlic", 0.008),
	],
	"Chicken Kabsa": [
		("Chicken (halal)", 0.35), ("Basmati Rice", 0.2), ("Tomato", 0.08),
		("Onion", 0.05), ("Mixed Spices (hawaij)", 0.01),
	],
	"Lentil Soup": [("Lentils", 0.08), ("Onion", 0.03), ("Garlic", 0.005), ("Lemon", 0.5)],
	"Shafout": [
		("Flatbread Flour", 0.08), ("Yoghurt", 0.12), ("Fenugreek (hulba)", 0.01),
		("Sahawiq Mix", 0.015),
	],
	"Hummus with Olive Oil": [("Chickpeas", 0.12), ("Garlic", 0.005), ("Lemon", 0.5)],
	"Sambusa (meat)": [
		("Lamb (halal)", 0.08), ("Onion", 0.03), ("Flatbread Flour", 0.06),
		("Cooking Oil", 0.03),
	],
	"Mutabbaq (veg)": [
		("Flatbread Flour", 0.1), ("Eggs", 1), ("Onion", 0.04), ("Cheese (akkawi)", 0.05),
	],
	"Vegetable Aseed": [("Flatbread Flour", 0.15), ("Onion", 0.04), ("Tomato", 0.05)],
	"Fattoush": [
		("Tomato", 0.1), ("Onion", 0.03), ("Flatbread Flour", 0.04), ("Lemon", 1),
		("Fresh Mint", 0.02),
	],
	"Bint al-Sahn": [
		("Flatbread Flour", 0.1), ("Eggs", 1), ("Butter Ghee", 0.04), ("Honey", 0.05),
	],
	"Kunafa": [
		("Konafeh Pastry", 0.12), ("Cheese (akkawi)", 0.1), ("Pistachio", 0.02),
		("Butter Ghee", 0.03), ("Honey", 0.04),
	],
	"Fresh Dates & Nuts": [("Dates", 0.12), ("Pistachio", 0.03)],
	"Qishr": [("Coffee Husk (qishr)", 0.02), ("Cardamom", 0.002)],
	"Fresh Orange Juice": [("Orange", 3)],
	"Laban": [("Yoghurt", 0.25)],
	"Yemeni Qahwa": [("Coffee Beans (Yemeni)", 0.018), ("Cardamom", 0.003)],
	"Qishr Spiced": [("Coffee Husk (qishr)", 0.02), ("Cardamom", 0.002)],
	"Adeni Chai": [("Tea Leaves", 0.008), ("Milk", 0.15), ("Cardamom", 0.002)],
	"Mint Tea": [("Tea Leaves", 0.006), ("Fresh Mint", 0.02)],
	"Mango Juice": [("Mango", 1)],
	"Lemon Mint": [("Lemon", 2), ("Fresh Mint", 0.02)],
	"Ful Medames": [("Fava Beans", 0.15), ("Onion", 0.03), ("Garlic", 0.005), ("Cooking Oil", 0.02)],
	"Shakshuka": [("Eggs", 2), ("Tomato", 0.15), ("Onion", 0.04), ("Garlic", 0.008)],
	"Cheese Mutabbaq": [
		("Flatbread Flour", 0.1), ("Cheese (akkawi)", 0.08), ("Eggs", 1), ("Cooking Oil", 0.02),
	],
	"Meat Sambusa Plate": [
		("Lamb (halal)", 0.1), ("Onion", 0.04), ("Flatbread Flour", 0.08), ("Cooking Oil", 0.04),
	],
	"Chicken Shawarma Wrap": [
		("Chicken (halal)", 0.2), ("Flatbread Flour", 0.08), ("Shawarma Spice", 0.008),
		("Yoghurt", 0.04),
	],
	"Falafel Plate": [("Falafel Mix", 0.12), ("Chickpeas", 0.05), ("Cooking Oil", 0.04)],
	"Zaatar Manakish": [("Flatbread Flour", 0.1), ("Cooking Oil", 0.02)],
	"Honey Cake Slice": [
		("Flatbread Flour", 0.06), ("Honey", 0.04), ("Eggs", 1), ("Pistachio", 0.015),
		("Butter Ghee", 0.02),
	],
	"Basbousa": [
		("Flatbread Flour", 0.08), ("Honey", 0.05), ("Yoghurt", 0.04), ("Pistachio", 0.01),
	],
	"Bottled Water": [("Bottled Water 500ml", 1)],
}

OPENING = {
	"Al Rawdha Restaurant": [
		("Basmati Rice", 40, 15), ("Chicken (halal)", 25, 10), ("Lamb (halal)", 18, 8),
		("Hammour Fillet", 8, 3), ("Onion", 30, 10), ("Tomato", 25, 8),
		("Potato", 20, 8), ("Garlic", 5, 2), ("Fenugreek (hulba)", 3, 1),
		("Sahawiq Mix", 4, 1.5), ("Yoghurt", 20, 8), ("Milk", 15, 6),
		("Butter Ghee", 8, 3), ("Chickpeas", 12, 4), ("Lentils", 10, 4),
		("Flatbread Flour", 30, 10), ("Cooking Oil", 25, 8),
		("Mixed Spices (hawaij)", 3, 1), ("Cardamom", 1, 0.3),
		("Coffee Husk (qishr)", 2, 0.8), ("Dates", 10, 3), ("Pistachio", 2, 0.5),
		("Honey", 5, 2), ("Orange", 80, 30), ("Lemon", 60, 20),
		("Eggs", 120, 40), ("Cheese (akkawi)", 6, 2), ("Konafeh Pastry", 4, 1.5),
	],
	"Bab al-Yemen Cafe": [
		("Coffee Beans (Yemeni)", 5, 2), ("Coffee Husk (qishr)", 3, 1),
		("Tea Leaves", 3, 1), ("Fresh Mint", 4, 1.5), ("Milk", 20, 8),
		("Yoghurt", 12, 5), ("Cardamom", 1, 0.3), ("Fava Beans", 10, 4),
		("Tomato", 15, 5), ("Onion", 12, 4), ("Garlic", 3, 1),
		("Eggs", 100, 30), ("Flatbread Flour", 20, 8), ("Cheese (akkawi)", 5, 2),
		("Chickpeas", 8, 3), ("Falafel Mix", 6, 2), ("Shawarma Spice", 2, 0.5),
		("Chicken (halal)", 12, 5), ("Lamb (halal)", 6, 2), ("Cooking Oil", 15, 5),
		("Honey", 4, 1.5), ("Pistachio", 1.5, 0.5), ("Mango", 40, 15),
		("Lemon", 50, 20), ("Bottled Water 500ml", 120, 48),
	],
}


def _yemen_properties() -> list[str]:
	return frappe.get_all(
		"Property", filters={"country": "Yemen"}, pluck="name",
	) or ([DEFAULT_PROPERTY] if frappe.db.exists("Property", DEFAULT_PROPERTY) else [])


def _fnb_gst(property: str) -> float:
	try:
		return float(pack_for(property).fnb_tax_rate(property) or 5)
	except Exception:
		return 5.0


def seed_property(property: str) -> dict:
	"""Seed both outlets + menu + inventory for one Yemen property."""
	if not frappe.db.exists("Property", property):
		return {"property": property, "error": "missing"}

	gst = _fnb_gst(property)
	added = {"outlets": 0, "items": 0, "ingredients": 0, "stock": 0}

	# Drop the empty provision-time shell outlet (trailing space, no menu)
	shell = frappe.db.get_value(
		"POS Outlet",
		{"property": property, "outlet_name": "Main Restaurant "},
	)
	if shell and not frappe.db.exists("Menu Item", {"outlet": shell}):
		frappe.delete_doc("POS Outlet", shell, ignore_permissions=True, force=True)

	for oname, otype, tables, items in POS:
		outlet = frappe.db.get_value(
			"POS Outlet", {"property": property, "outlet_name": oname})
		if not outlet:
			outlet = frappe.get_doc({
				"doctype": "POS Outlet",
				"property": property,
				"outlet_name": oname,
				"outlet_type": otype,
				"gst_rate": gst,
				"tables": tables,
			}).insert(ignore_permissions=True).name
			added["outlets"] += 1
		else:
			frappe.db.set_value("POS Outlet", outlet, {
				"gst_rate": gst, "tables": tables, "outlet_type": otype,
			})

		for (item, cat, price, veg, station, course, allergens,
		     desc, img) in items:
			existing = frappe.db.exists(
				"Menu Item", {"outlet": outlet, "item_name": item})
			payload = {
				"category": cat,
				"price": price,
				"is_veg": veg,
				"available": 1,
				"prep_station": station,
				"course": course,
				"allergens": allergens,
				"description": desc,
				"is_alcohol": 0,
				"image": img,
			}
			if existing:
				frappe.db.set_value("Menu Item", existing, payload)
				continue
			frappe.get_doc({
				"doctype": "Menu Item",
				"property": property,
				"outlet": outlet,
				"item_name": item,
				**payload,
			}).insert(ignore_permissions=True)
			added["items"] += 1

	from kamra import inventory

	ing_id: dict[str, str] = {}
	for name, uom, cost, cat in INGREDIENTS:
		existing = frappe.db.exists(
			"Ingredient", {"property": property, "ingredient_name": name})
		if existing:
			frappe.db.set_value("Ingredient", existing, {
				"uom": uom, "cost_per_unit": cost, "category": cat, "is_active": 1,
			})
			ing_id[name] = existing
			continue
		ing_id[name] = frappe.get_doc({
			"doctype": "Ingredient",
			"property": property,
			"ingredient_name": name,
			"uom": uom,
			"cost_per_unit": cost,
			"category": cat,
			"is_active": 1,
		}).insert(ignore_permissions=True).name
		added["ingredients"] += 1

	for item_name, lines in RECIPES.items():
		mi = frappe.db.exists(
			"Menu Item", {"property": property, "item_name": item_name})
		if not mi:
			continue
		doc = frappe.get_doc("Menu Item", mi)
		doc.set("recipe", [
			{"ingredient": ing_id[i], "qty": q}
			for i, q in lines if i in ing_id
		])
		doc.save(ignore_permissions=True)

	for outlet_name, opening in OPENING.items():
		outlet = frappe.db.exists(
			"POS Outlet", {"property": property, "outlet_name": outlet_name})
		if not outlet:
			continue
		for name, qty, par in opening:
			if name not in ing_id:
				continue
			row = f"{outlet}::{ing_id[name]}"
			if frappe.db.exists("Ingredient Stock", row):
				# keep live counts; only refresh par
				frappe.db.set_value(
					"Ingredient Stock", row, "par_level", par,
					update_modified=False)
				continue
			inventory._apply_move(
				property, outlet, ing_id[name], qty, "Opening",
				note="Opening stock (Yemen F&B seed)")
			frappe.db.set_value(
				"Ingredient Stock", row, "par_level", par,
				update_modified=False)
			added["stock"] += 1

	frappe.db.commit()
	return {"property": property, **added}


def execute(property: str | None = None):
	"""Seed every Yemen property on the site, or one named property."""
	targets = [property] if property else _yemen_properties()
	if not targets:
		print("No Yemen property found — create Demo Yemen first.")
		return {"seeded": []}
	out = []
	for prop in targets:
		result = seed_property(prop)
		out.append(result)
		print(
			f"Yemen F&B on {prop}: "
			f"+{result.get('outlets', 0)} outlets, "
			f"+{result.get('items', 0)} dishes, "
			f"+{result.get('ingredients', 0)} ingredients, "
			f"+{result.get('stock', 0)} opening stock rows"
		)
	return {"seeded": out}
