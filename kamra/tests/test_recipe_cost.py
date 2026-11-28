"""Cost and margin per portion, from the recipe."""

from __future__ import annotations

from unittest.mock import patch

import frappe

from kamra import inventory
from kamra.tests.audit_fixtures import PROP_A
from kamra.tests.test_rbac import _grant, _user
from kamra.tests.test_stock_cost import StockCostTestCase


class TestRecipeCost(StockCostTestCase):
	def dish(self, name, price, *lines):
		return frappe.get_doc({
			"doctype": "Menu Item", "property": PROP_A, "outlet": self.cafe,
			"item_name": name, "price": price,
			"recipe": [{"ingredient": i, "qty": q} for i, q in lines],
		}).insert(ignore_permissions=True).name

	def row(self, dish):
		return next(d for d in inventory.recipe_overview(PROP_A) if d["name"] == dish)

	def assertCost(self, dish, cost, margin, pct, uncosted=()):
		d = self.row(dish)
		self.assertEqual(d["cost"], cost)
		self.assertEqual(d["margin"], margin)
		self.assertEqual(None if d["margin_pct"] is None else round(d["margin_pct"], 1), pct)
		self.assertEqual(d["uncosted"], list(uncosted))

	def test_the_worked_examples(self):
		milk = self.ingredient("UT Milk", "ml", 20)
		beans = self.ingredient("UT Beans", "g", 220)
		cup = self.ingredient("UT Cup", "pc", 2400)
		latte = self.dish("UT Latte", 25000, (milk, 150), (beans, 18), (cup, 1))
		self.assertCost(latte, 9360, 15640, 62.6)

		frappe.db.set_value("Ingredient", cup, "cost_per_unit", 0)
		self.assertCost(latte, None, None, None, ["UT Cup"])

		syrup = self.ingredient("UT Syrup", "ml", 6000)
		self.assertCost(self.dish("UT Dear", 10000, (syrup, 2)), 12000, -2000, -20.0)
		pack = self.ingredient("UT Pack", "pc", 3000)
		self.assertCost(self.dish("UT Free", 0, (pack, 1)), 3000, -3000, None)

	def test_a_dish_without_a_recipe_has_no_cost(self):
		self.assertCost(self.dish("UT Plain", 5000), None, None, None)

	def test_repeated_and_inactive_ingredients_are_counted(self):
		milk = self.ingredient("UT Milk", "ml", 20, is_active=0)
		dish = self.dish("UT Double", 5000, (milk, 100), (milk, 50))
		self.assertCost(dish, 3000, 2000, 40.0)

	def test_an_uncosted_ingredient_is_named_once(self):
		milk = self.ingredient("UT Milk", "ml", 20)
		water = self.ingredient("UT Water", "ml", 0)
		dish = self.dish("UT Thin", 5000, (milk, 100), (water, 5), (water, 5))
		self.assertCost(dish, None, None, None, ["UT Water"])

	def test_the_price_is_listed_beside_the_cost(self):
		milk = self.ingredient("UT Milk", "ml", 20)
		self.assertEqual(self.row(self.dish("UT Milk Cup", 5000, (milk, 100)))["price"], 5000)

	def test_more_dishes_do_not_mean_more_queries(self):
		milk = self.ingredient("UT Milk", "ml", 20)
		self.dish("UT One", 5000, (milk, 100))
		inventory.recipe_overview(PROP_A)  # warm the metadata caches

		def queries():
			with patch.object(frappe.db, "sql", wraps=frappe.db.sql) as spy:
				inventory.recipe_overview(PROP_A)
			return spy.call_count

		one = queries()
		for i in range(3):
			beans = self.ingredient(f"UT Beans {i}", "g", 200)
			self.dish(f"UT More {i}", 5000, (beans, 10))
		inventory.recipe_overview(PROP_A)
		self.assertEqual(queries(), one)

	def test_costs_need_view_stock(self):
		milk = self.ingredient("UT Milk", "ml", 20)
		dish = self.dish("UT Latte", 5000, (milk, 100))
		seen = inventory.menu_recipe(dish)
		self.assertEqual(seen["price"], 5000)
		self.assertEqual(seen["recipe"][0]["cost_per_unit"], 20)

		role = "UT Menu Reader"
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role,
			                "desk_access": 1}).insert(ignore_permissions=True)
		self.addCleanup(frappe.clear_cache, doctype="Menu Item")
		_grant("Menu Item", "view_recipes", role)
		reader = _user("ut-menu-reader@example.com", role)
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user(reader)  # nosemgrep: frappe-setuser -- test switches user
		hidden = inventory.menu_recipe(dish)
		self.assertNotIn("price", hidden)
		self.assertNotIn("cost_per_unit", hidden["recipe"][0])
		self.assertEqual(hidden["recipe"][0]["qty_on_hand"], None)
