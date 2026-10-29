"""/book quotes each meal plan and shows a real voucher discount."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from kamra.public_api import search_stay, showcase


class PublicBookingTestCase(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		frappe.local.lang = "en"
		self.property = frappe.get_doc({"doctype": "Property",
			"property_name": "TEST BOOK " + frappe.generate_hash(length=8),
			"booking_engine_enabled": 1}).insert(ignore_permissions=True).name
		self.room_type = frappe.get_doc({"doctype": "Room Type", "property": self.property,
			"room_type_code": "STD", "room_type_name": "Standard", "base_price": 1000,
			"adults_capacity": 2}).insert(ignore_permissions=True).name
		frappe.get_doc({"doctype": "Room", "property": self.property,
			"room_type": self.room_type, "room_number": "101"}).insert(ignore_permissions=True)
		self.meal = frappe.get_doc({"doctype": "Meal Plan", "property": self.property,
			"code": "CP", "label": "Breakfast", "price_per_adult": 300}).insert(
			ignore_permissions=True).name
		frappe.get_doc({"doctype": "Discount Voucher", "property": self.property,
			"voucher_code": "TENOFF", "discount_type": "Percent", "value": 10,
			"min_nights": 1}).insert(ignore_permissions=True)
		self.ci, self.co = add_days(nowdate(), 5), add_days(nowdate(), 7)

	def row(self, **kw):
		return search_stay(self.property, self.ci, self.co, 2, 0, **kw)[0]

	def test_each_meal_plan_is_quoted(self):
		row = self.row()
		plans = {p["meal_plan"]: p for p in row["plans"]}
		self.assertEqual(set(plans), {"", self.meal})
		self.assertEqual(plans[""]["amount_after_tax"], row["quote"]["amount_after_tax"])
		self.assertGreater(plans[self.meal]["amount_after_tax"], plans[""]["amount_after_tax"])
		self.assertNotIn("list_amount", plans[""])
		self.assertIn("advance_due", plans[""])

	def test_free_meal_plan_is_the_room_only_rate(self):
		ep = frappe.get_doc({"doctype": "Meal Plan", "property": self.property,
			"code": "EP", "label": "Room only"}).insert(ignore_permissions=True).name
		self.assertEqual([p["meal_plan"] for p in self.row()["plans"]], [ep, self.meal])

	def test_voucher_discounts_and_keeps_list_price(self):
		plain = self.row()["plans"][0]["amount_after_tax"]
		plan = self.row(voucher_code="tenoff")["plans"][0]
		self.assertAlmostEqual(plan["list_amount"], plain, places=2)
		self.assertLess(plan["amount_after_tax"], plain)

	def test_unknown_voucher_is_ignored(self):
		plan = self.row(voucher_code="NOPE")["plans"][0]
		self.assertNotIn("list_amount", plan)

	def test_showcase_says_whether_tiers_apply(self):
		self.assertIs(showcase(self.property)["property"]["has_cancellation_tiers"], False)
