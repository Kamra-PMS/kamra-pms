"""Fixtures for the banquet tests.

Each test runs in its own transaction and is rolled back, so everything is
built get-or-create and rebuilt per test. That costs a little speed and buys
complete isolation: no test can be broken by another test's leftovers, and
the suite gives the same answer on a fresh CI site as on a developer's
seeded one.
"""

import frappe

PROPERTY = "TEST Banquet Hotel"
ROLES = ("Front Desk", "Housekeeping", "Finance", "Revenue Manager",
         "Kamra Agent", "Hotel Admin")

# (login, first name, roles) - the personas the access tests act as
USERS = {
	"banquet.sales@test.local": ("Sales", ["Front Desk"]),
	"banquet.finance@test.local": ("Fin", ["Finance"]),
	"banquet.hk@test.local": ("Floor", ["Housekeeping"]),
	"banquet.revenue@test.local": ("Rev", ["Revenue Manager"]),
}


def _upsert(doctype: str, filters: dict, payload: dict) -> str:
	"""Create it, or put an existing one back to these exact values.

	Restoring matters more than creating: a test that raises an ingredient
	price must not change what the next test costs. Frappe's rollback is
	not something to lean on for that - the fixtures own their own state.
	"""
	existing = frappe.db.get_value(doctype, filters)
	if not existing:
		doc = frappe.get_doc({"doctype": doctype, **payload})
		doc.insert(ignore_permissions=True)
		return doc.name
	doc = frappe.get_doc(doctype, existing)
	doc.update(payload)
	doc.save(ignore_permissions=True)
	return doc.name


def ensure_roles_and_users():
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role,
			                "desk_access": 0}).insert(ignore_permissions=True)
	for email, (first, roles) in USERS.items():
		if frappe.db.exists("User", email):
			continue
		frappe.get_doc({
			"doctype": "User", "email": email, "first_name": first,
			"enabled": 1, "user_type": "System User",
			"send_welcome_email": 0,
			"roles": [{"role": r} for r in roles],
		}).insert(ignore_permissions=True)


def build() -> dict:
	"""A property with a hall, an ingredient shelf, a costed dish library and
	a menu whose starter course offers a choice. Everything the banquet
	tests need and nothing they don't."""
	ensure_roles_and_users()
	f = {"property": PROPERTY}

	_upsert("Property", {"property_name": PROPERTY}, {
		"property_name": PROPERTY, "city": "Testville", "state": "Karnataka",
		"gst_mode": "Slab", "gst_slab_threshold": 7500,
		"gst_rate_low": 5, "gst_rate_high": 18, "gstin": "29AABCU9603R1ZM",
	})

	f["hall"] = _upsert("Venue", {"property": PROPERTY,
	                                     "venue_name": "Test Hall"}, {
		"property": PROPERTY, "venue_name": "Test Hall",
		"venue_type": "Banquet Hall", "capacity": 300, "min_capacity": 50,
		"base_price": 50000, "hourly_rate": 8000, "min_hours": 4,
		"gst_rate": 18,
	})
	f["small"] = _upsert("Venue", {"property": PROPERTY,
	                                      "venue_name": "Test Boardroom"}, {
		"property": PROPERTY, "venue_name": "Test Boardroom",
		"venue_type": "Board Room", "capacity": 20, "base_price": 8000,
	})

	# the shelf: a cheap vegetable and an expensive protein
	f["onion"] = _upsert("Ingredient", {"property": PROPERTY,
	                                           "ingredient_name": "Test Onion"}, {
		"property": PROPERTY, "ingredient_name": "Test Onion", "uom": "kg",
		"cost_per_unit": 40, "gst_rate": 5, "is_active": 1,
	})
	f["chicken"] = _upsert("Ingredient", {"property": PROPERTY,
	                                             "ingredient_name": "Test Chicken"}, {
		"property": PROPERTY, "ingredient_name": "Test Chicken", "uom": "kg",
		"cost_per_unit": 300, "gst_rate": 5, "is_active": 1,
	})

	# two starters: the standard one and a chargeable upgrade
	f["veg"] = _upsert("Banquet Dish", {"property": PROPERTY,
	                                           "dish_name": "Test Paneer"}, {
		"property": PROPERTY, "dish_name": "Test Paneer",
		"course_type": "Starters", "food_type": "Veg", "kitchen": "Tandoor",
		"portion_per_pax": 1, "cost_per_portion": 8,
		"recipe": [{"ingredient": f["onion"], "qty": 0.2}],
	})
	f["nonveg"] = _upsert("Banquet Dish", {"property": PROPERTY,
	                                              "dish_name": "Test Tikka"}, {
		"property": PROPERTY, "dish_name": "Test Tikka",
		"course_type": "Starters", "food_type": "Non-Veg",
		"kitchen": "Tandoor", "portion_per_pax": 1, "cost_per_portion": 30,
		"recipe": [{"ingredient": f["chicken"], "qty": 0.1}],
	})

	f["menu"] = _upsert("Banquet Menu", {"property": PROPERTY,
	                                            "menu_name": "Test Buffet"}, {
		"property": PROPERTY, "menu_name": "Test Buffet",
		"meal_period": "Dinner", "food_type": "Veg", "rate_per_pax": 1200,
		"min_pax": 100, "gst_rate": 5,
		"courses": [{"course": "Starters", "dishes": "Paneer, Tikka",
		             "choice_of": 1}],
		"dish_options": [
			{"course": "Starters", "dish": f["veg"], "is_default": 1},
			{"course": "Starters", "dish": f["nonveg"],
			 "supplement_per_pax": 150},
		],
	})

	f["led"] = _upsert("Banquet Service Item", {
		"property": PROPERTY, "item_name": "Test LED wall"}, {
		"property": PROPERTY, "item_name": "Test LED wall",
		"category": "Audio Visual", "uom": "Per Event", "rate": 40000,
		"gst_rate": 18, "cost_rate": 25000, "cost_gst_rate": 18,
		"chargeable": 1, "on_pack_list": 1,
	})
	f["podium"] = _upsert("Banquet Service Item", {
		"property": PROPERTY, "item_name": "Test Podium"}, {
		"property": PROPERTY, "item_name": "Test Podium",
		"category": "Furniture & Setup", "uom": "Per Event", "rate": 2000,
		"gst_rate": 18, "chargeable": 0, "on_pack_list": 1,
	})
	f["starter_course"] = "Starters"
	return f


_DAY = [60]


def next_day_offset() -> int:
	"""A fresh date for every function the suite creates.

	A confirmed function owns its hall - which is the rule under test - so
	two tests sharing a date would fail each other for the wrong reason.
	Walking the calendar forward keeps every test independent of the order
	they run in.
	"""
	_DAY[0] += 1
	return _DAY[0]


def enquiry(f: dict, **kw) -> str:
	"""A function on the test hall, evening, 19:00-23:00, on a day no other
	test is using."""
	from kamra import banquet as bq
	from frappe.utils import add_days, nowdate

	args = {
		"property": PROPERTY, "venue": f["hall"],
		"event_date": add_days(nowdate(),
		                       kw.pop("day_offset", None) or next_day_offset()),
		"customer_name": "Test Customer", "attendees": 200,
		"start_time": "19:00", "end_time": "23:00",
	}
	args.update(kw)
	return bq.create_enquiry(**args)["function"]
