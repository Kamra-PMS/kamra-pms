"""Kitchen inventory: what the stock screen can offer, and the low-stock level."""

from __future__ import annotations

import frappe

from kamra import inventory
from kamra.tests.audit_fixtures import (
	PROP_A, PROP_B, TODAY, AuditTestCase, ensure_user, make_property)

STOCK_LIST = "kamra.inventory.stock_list"


class KitchenStockTestCase(AuditTestCase):
	def setUp(self):
		super().setUp()
		make_property(PROP_A, business_date=TODAY)
		make_property(PROP_B, business_date=TODAY)
		self.outlet = frappe.get_doc({
			"doctype": "POS Outlet", "property": PROP_A,
			"outlet_name": "UT Stock Kitchen", "outlet_type": "Restaurant",
			"gst_rate": 5}).insert(ignore_permissions=True).name

	def ingredient(self, name: str, prop: str = PROP_A, active: int = 1) -> str:
		return frappe.get_doc({
			"doctype": "Ingredient", "property": prop, "ingredient_name": name,
			"uom": "L", "cost_per_unit": 20, "is_active": active,
		}).insert(ignore_permissions=True).name

	def listed(self, **kw) -> dict:
		# frappe.call, as the browser's request does: arguments by name
		rows = frappe.call(STOCK_LIST, property=PROP_A, outlet=self.outlet, **kw)
		return {r["ingredient"]: r for r in rows}


class TestAnIngredientThatHasNeverMoved(KitchenStockTestCase):
	def test_it_can_be_picked_for_a_receipt_or_a_count(self):
		milk = self.ingredient("UT Milk")

		row = self.listed(include_unstocked=1).get(milk)

		self.assertIsNotNone(row, "a new ingredient is not offered")
		self.assertEqual(
			(row["ingredient_name"], row["uom"], row["qty_on_hand"], row["stocked"]),
			("UT Milk", "L", 0, 0))

	def test_it_is_not_shown_as_something_the_outlet_holds(self):
		milk = self.ingredient("UT Milk")

		self.assertNotIn(milk, self.listed())

	def test_once_received_it_is_listed_once_as_stocked(self):
		milk = self.ingredient("UT Milk")
		inventory.receive_stock(PROP_A, self.outlet, [{"ingredient": milk, "qty": 2}])

		rows = frappe.call(STOCK_LIST, property=PROP_A, outlet=self.outlet,
		                   include_unstocked=1)

		mine = [(r["qty_on_hand"], r["stocked"]) for r in rows if r["ingredient"] == milk]
		self.assertEqual(mine, [(2, 1)])

	def test_a_retired_or_foreign_ingredient_is_not_offered(self):
		retired = self.ingredient("UT Retired", active=0)
		foreign = self.ingredient("UT Foreign", prop=PROP_B)

		rows = self.listed(include_unstocked=1)

		self.assertNotIn(retired, rows)
		self.assertNotIn(foreign, rows)


class TestLowStockLevel(KitchenStockTestCase):
	def test_a_negative_level_is_refused(self):
		milk = self.ingredient("UT Milk")
		inventory.set_par_level(PROP_A, self.outlet, milk, 5)

		with self.assertRaises(frappe.ValidationError):
			inventory.set_par_level(PROP_A, self.outlet, milk, -1)

		self.assertEqual(self.listed()[milk]["par_level"], 5)

	def test_a_level_that_is_not_a_finite_number_is_refused(self):
		milk = self.ingredient("UT Milk")
		inventory.set_par_level(PROP_A, self.outlet, milk, 5)

		for bad in ("nope", "", None, "nan", "NaN", "inf", "+inf", "-inf",
		            "Infinity", float("nan"), float("inf"), float("-inf")):
			with self.assertRaises(frappe.ValidationError) as caught:
				inventory.set_par_level(PROP_A, self.outlet, milk, bad)
			self.assertIn("Enter a number for the low-stock level.", str(caught.exception))

		inventory.set_par_level(PROP_A, self.outlet, milk, "6.5")
		self.assertEqual(self.listed()[milk]["par_level"], 6.5)


class TestWhoMaySetTheLevel(KitchenStockTestCase):
	def test_a_user_without_manage_stock_is_refused(self):
		milk = self.ingredient("UT Milk")
		# Front Desk may look at stock, not set the level
		frappe.set_user(ensure_user(  # nosemgrep: frappe-setuser -- the role under test
			"ut.stock.desk@test.local", ["Front Desk"]))

		with self.assertRaises(frappe.PermissionError):
			inventory.set_par_level(PROP_A, self.outlet, milk, 3)

		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		self.assertNotIn(milk, self.listed())

	def test_a_user_restricted_to_one_property_cannot_touch_another(self):
		mine = self.ingredient("UT Milk")
		foreign = self.ingredient("UT Foreign Milk", prop=PROP_B)
		outlet_b = frappe.get_doc({
			"doctype": "POS Outlet", "property": PROP_B,
			"outlet_name": "UT Other Kitchen", "outlet_type": "Restaurant",
			"gst_rate": 5}).insert(ignore_permissions=True).name
		user = ensure_user("ut.stock.scoped@test.local", ["F&B Manager"])
		frappe.db.delete("User Permission", {"user": user, "allow": "Property"})
		frappe.get_doc({
			"doctype": "User Permission", "user": user,
			"allow": "Property", "for_value": PROP_A,
		}).insert(ignore_permissions=True)
		frappe.clear_cache(user=user)
		frappe.set_user(user)  # nosemgrep: frappe-setuser -- the role under test

		rows = frappe.call(STOCK_LIST, property=PROP_A, outlet=self.outlet,
		                   include_unstocked=1)
		names = {r["ingredient"] for r in rows}
		self.assertIn(mine, names)
		self.assertNotIn(foreign, names)
		inventory.set_par_level(PROP_A, self.outlet, mine, 4)

		refused = (
			lambda: frappe.call(STOCK_LIST, property=PROP_B, outlet=outlet_b,
			                    include_unstocked=1),
			lambda: frappe.call(STOCK_LIST, property=PROP_B, outlet=self.outlet,
			                    include_unstocked=1),
			lambda: frappe.call(STOCK_LIST, property=PROP_A, outlet=outlet_b,
			                    include_unstocked=1),
			lambda: inventory.set_par_level(PROP_B, outlet_b, foreign, 9),
			lambda: inventory.set_par_level(PROP_A, outlet_b, mine, 9),
			lambda: inventory.set_par_level(PROP_A, self.outlet, foreign, 9),
		)
		for call in refused:
			with self.assertRaises(frappe.PermissionError):
				call()

		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		self.assertEqual(self.listed()[mine]["par_level"], 4)
		self.assertFalse(frappe.db.exists("Ingredient Stock", {"ingredient": foreign}))
