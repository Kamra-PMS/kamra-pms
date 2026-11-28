"""Meal plans when the property's rates include tax: the quote, the booking's
locked nights and the folio must read the meal price the same way, and bookings
locked with the price still carrying its tax are corrected once."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from kamra.api import create_booking, get_quote
from kamra.folio import post_room_night
from kamra.patches.v48 import take_tax_out_of_meal_nights as patch
from kamra.pricing import quote

# (country, currency, room price, meal price per adult): 0, 2 and 3 decimals
HOTELS = (
	("Indonesia", "IDR", 330000, 50000),
	("Japan", "JPY", 11000, 1100),
	("India", "INR", 3000, 500),
	("United Arab Emirates", "AED", 300, 45.5),
	("Kuwait", "KWD", 45.125, 3.125),
)


class TestMealPlanTax(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		frappe.local.lang = "en"
		self.ci = str(add_days(nowdate(), 10))
		self.co = str(add_days(nowdate(), 12))

	def hotel(self, country="Indonesia", currency="IDR", room=330000, meal=50000, inclusive=1):
		prop = frappe.get_doc({"doctype": "Property",
			"property_name": "TEST MEAL " + frappe.generate_hash(length=8),
			"country": country, "currency": currency,
			"rates_include_tax": inclusive}).insert(ignore_permissions=True).name
		rt = frappe.get_doc({"doctype": "Room Type", "property": prop, "room_type_code": "STD",
			"room_type_name": "Standard", "base_price": room,
			"adults_capacity": 2}).insert(ignore_permissions=True).name
		for n in ("101", "102"):
			frappe.get_doc({"doctype": "Room", "property": prop, "room_type": rt,
				"room_number": n}).insert(ignore_permissions=True)
		mp = frappe.db.get_value("Meal Plan", {"property": prop, "code": "CP"})
		if mp:
			frappe.db.set_value("Meal Plan", mp, {"price_per_adult": meal, "price_per_child": 0})
		else:
			mp = frappe.get_doc({"doctype": "Meal Plan", "property": prop, "code": "CP",
				"label": "Breakfast", "price_per_adult": meal,
				"price_per_child": 0}).insert(ignore_permissions=True).name
		return prop, rt, mp

	def book(self, prop, rt, mp):
		name = create_booking(prop, rt, self.ci, self.co, "Meal Guest", adults=2,
		                      meal_plan=mp)["reservation"]
		return frappe.get_doc("Reservation", name)

	def bill(self, res):
		for night in (self.ci, str(add_days(self.ci, 1))):
			post_room_night(frappe.get_doc("Reservation", res.name), night)
		lines = frappe.get_all("Folio Charge",
			filters={"reservation": res.name, "charge_type": ("in", ["Room", "Meal Plan"])},
			fields=["charge_type", "amount", "total"])
		return (sum(r.total for r in lines),
		        sum(r.total for r in lines if r.charge_type == "Meal Plan"))

	def old_booking(self, prop, rt, mp):
		"""A booking as earlier releases locked it: the meal price kept whole."""
		res = self.book(prop, rt, mp)
		raw = 2 * frappe.db.get_value("Meal Plan", mp, "price_per_adult")
		for row in res.night_rates:
			frappe.db.set_value("Reservation Night Rate", row.name, "meal_amount", raw)
		return res, raw

	def meals(self, res):
		return frappe.get_all("Reservation Night Rate", filters={"parent": res.name},
		                      order_by="stay_date", pluck="meal_amount")

	def test_the_bill_equals_the_quote(self):
		for country, currency, room, meal in HOTELS:
			for inclusive in (1, 0):
				with self.subTest(currency=currency, inclusive=inclusive):
					prop, rt, mp = self.hotel(country, currency, room, meal, inclusive)
					q = get_quote(prop, rt, self.ci, self.co, adults=2, meal_plan=mp)
					total, meals = self.bill(self.book(prop, rt, mp))
					self.assertAlmostEqual(total, q["amount_after_tax"], places=3)
					if inclusive:
						self.assertAlmostEqual(meals, meal * 4, places=3)

	def test_an_unknown_meal_plan_is_refused_not_quoted_free(self):
		prop, rt, _ = self.hotel()
		with self.assertRaises(frappe.DoesNotExistError):
			quote(prop, rt, self.ci, self.co, adults=2, meal_plan="No Such Plan")

	def test_a_stay_without_locked_nights_bills_the_shown_meal_price(self):
		prop, rt, mp = self.hotel()
		res = self.book(prop, rt, mp)
		frappe.db.delete("Reservation Night Rate", {"parent": res.name})
		_, meals = self.bill(res)
		self.assertAlmostEqual(meals, 200000, places=3)

	def test_patch_corrects_unbilled_nights_only_and_is_repeatable(self):
		for country, currency, room, meal in HOTELS:
			with self.subTest(currency=currency):
				prop, rt, mp = self.hotel(country, currency, room, meal)
				res, raw = self.old_booking(prop, rt, mp)
				post_room_night(frappe.get_doc("Reservation", res.name), self.ci)
				quoted = frappe.parse_json(res.quote_snapshot)["meal_total"] / 2
				patch.execute()
				first, second = self.meals(res)
				self.assertAlmostEqual(first, raw, places=6)  # already on the bill
				self.assertAlmostEqual(second, quoted, places=5)
				patch.execute()
				self.assertAlmostEqual(self.meals(res)[1], quoted, places=5)

	def test_patch_leaves_a_booking_quoted_before_tax(self):
		# booked while prices were before tax, the setting switched on afterwards
		prop, rt, mp = self.hotel(inclusive=0)
		res = self.book(prop, rt, mp)
		frappe.db.set_value("Property", prop, "rates_include_tax", 1)
		frappe.clear_document_cache("Property", prop)
		patch.execute()
		self.assertEqual(self.meals(res), [100000, 100000])

	def test_patch_corrects_after_the_setting_was_switched_off(self):
		prop, rt, mp = self.hotel()
		res, _ = self.old_booking(prop, rt, mp)
		frappe.db.set_value("Property", prop, "rates_include_tax", 0)
		frappe.clear_document_cache("Property", prop)
		patch.execute()
		quoted = frappe.parse_json(res.quote_snapshot)["meal_total"] / 2
		self.assertAlmostEqual(self.meals(res)[0], quoted, places=5)

	def test_patch_leaves_a_booking_without_a_saved_quote(self):
		prop, rt, mp = self.hotel()
		res, raw = self.old_booking(prop, rt, mp)
		frappe.db.set_value("Reservation", res.name, "quote_snapshot", None)
		patch.execute()
		self.assertEqual(self.meals(res), [raw, raw])
