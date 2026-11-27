"""Units and buying units, the cost rule, and the purchase history."""

from __future__ import annotations

from unittest.mock import patch

import frappe

from kamra import inventory, settings
from kamra.tests.audit_fixtures import PROP_A, PROP_B, TODAY, AuditTestCase, make_property

AVERAGE = "Average of purchases"


class StockCostTestCase(AuditTestCase):
	def setUp(self):
		super().setUp()
		make_property(PROP_A, business_date=TODAY)
		make_property(PROP_B, business_date=TODAY)
		# settings are cached outside the transaction the test rolls back
		frappe.cache().hdel(settings.CACHE_KEY, PROP_A)
		self.addCleanup(frappe.cache().hdel, settings.CACHE_KEY, PROP_A)
		self.cafe, self.bar = self.outlet("UT Cafe"), self.outlet("UT Bar")

	def outlet(self, name):
		return frappe.get_doc({
			"doctype": "POS Outlet", "property": PROP_A, "outlet_name": name,
			"outlet_type": "Restaurant", "gst_rate": 5}).insert(ignore_permissions=True).name

	def ingredient(self, name="UT Beans", uom="g", cost=200, prop=PROP_A, **extra):
		return frappe.get_doc({
			"doctype": "Ingredient", "property": prop, "ingredient_name": name,
			"uom": uom, "cost_per_unit": cost, **extra}).insert(ignore_permissions=True).name

	def method(self, value):
		settings.save_settings(PROP_A, "fnb", {"stock_cost_method": value})

	def held(self, ing, qty, outlet=None):
		inventory.adjust_stock(PROP_A, outlet or self.cafe,
		                       [{"ingredient": ing, "counted_qty": qty}], note="opening")

	def receive(self, ing, qty, price=None, outlet=None, **row):
		if price is not None:
			row["cost_per_unit"] = price
		return inventory.receive_stock(PROP_A, outlet or self.cafe,
		                               [{"ingredient": ing, "qty": qty, **row}])

	def cost(self, ing):
		return frappe.db.get_value("Ingredient", ing, "cost_per_unit")


class TestUnits(StockCostTestCase):
	def refuses_new_unit(self, ing):
		doc = frappe.get_doc("Ingredient", ing)
		doc.uom = "kg"
		with self.assertRaises(frappe.ValidationError):
			doc.save()

	def test_any_word_is_a_stock_unit(self):
		self.assertEqual(
			frappe.db.get_value("Ingredient", self.ingredient(uom="shot"), "uom"), "shot")

	def test_a_buying_unit_needs_a_name_and_a_size_above_zero(self):
		for i, extra in enumerate(({"buy_uom": "box"}, {"buy_size": 24},
		                           {"buy_uom": "box", "buy_size": -1})):
			with self.subTest(extra=extra), self.assertRaises(frappe.ValidationError):
				self.ingredient(f"UT Bad {i}", uom="pc", **extra)

	def test_the_unit_locks_once_it_has_history(self):
		beans = self.ingredient()
		self.receive(beans, 5)
		self.refuses_new_unit(beans)

	def test_the_unit_locks_once_it_is_on_a_recipe(self):
		beans = self.ingredient()
		frappe.get_doc({
			"doctype": "Menu Item", "property": PROP_A, "outlet": self.cafe,
			"item_name": "UT Espresso", "price": 20,
			"recipe": [{"ingredient": beans, "qty": 18}]}).insert(ignore_permissions=True)
		self.refuses_new_unit(beans)

	def test_an_unused_ingredient_may_change_its_unit(self):
		beans = self.ingredient()
		inventory.save_ingredient(PROP_A, "UT Beans", "kg", name=beans)
		self.assertEqual(frappe.db.get_value("Ingredient", beans, "uom"), "kg")

	def test_saving_without_a_cost_keeps_cost_and_buying_unit(self):
		beans = self.ingredient(buy_uom="bag", buy_size=1000)
		inventory.save_ingredient(PROP_A, "UT Beans", "g", name=beans)
		self.assertEqual(
			frappe.db.get_value("Ingredient", beans, ["cost_per_unit", "buy_uom", "buy_size"]),
			(200, "bag", 1000))

	def test_a_new_ingredient_without_a_cost_starts_at_zero(self):
		new = inventory.save_ingredient(PROP_A, "UT New", "g")["name"]
		self.assertEqual(self.cost(new), 0)

	def test_a_never_stocked_ingredient_offers_its_buying_unit(self):
		cups = self.ingredient("UT Cups", uom="pc", buy_uom="box", buy_size=24)
		row = next(r for r in inventory.stock_list(PROP_A, self.cafe, include_unstocked=1)
		           if r["ingredient"] == cups)
		self.assertEqual((row["buy_uom"], row["buy_size"]), ("box", 24))


class TestTheCostRule(StockCostTestCase):
	# stock before, cost before, delivered, price per stock unit, cost after
	CASES = ((2000, 200, 1000, 260, 220), (-200, 200, 1000, 260, 260),
	         (2000, 200, 1000, None, 200), (2000, 200, 1000, 0, 133.333333),
	         (0, 200, 1000, 0, 200), (-200, 200, 1000, 0, 200), (500, 0, 1000, 0, 0))

	def test_each_row_of_the_design_in_average_mode(self):
		self.method(AVERAGE)
		for i, (stock, cost, qty, price, after) in enumerate(self.CASES):
			with self.subTest(case=self.CASES[i]):
				ing = self.ingredient(f"UT {i}", cost=cost)
				if stock:
					self.held(ing, stock)
				self.receive(ing, qty, price)
				self.assertAlmostEqual(self.cost(ing), after, places=6)

	def test_free_goods_on_an_empty_shelf_then_a_priced_delivery(self):
		self.method(AVERAGE)
		beans = self.ingredient()
		self.receive(beans, 1000, 0)
		self.receive(beans, 1000, 260)
		self.assertAlmostEqual(self.cost(beans), 230, places=6)

	def test_the_stock_of_every_outlet_counts(self):
		self.method(AVERAGE)
		beans = self.ingredient()
		self.held(beans, 500)
		self.held(beans, 1500, outlet=self.bar)
		self.receive(beans, 1000, 260)
		self.assertAlmostEqual(self.cost(beans), 220, places=6)

	def test_boxes_and_bags(self):
		self.method(AVERAGE)
		cups = self.ingredient("UT Cups", "pc", 2000, buy_uom="box", buy_size=24)
		self.held(cups, 12)
		self.receive(cups, 2, 60000, in_buying_unit=1, buy_uom="box", buy_size=24)
		self.assertAlmostEqual(self.cost(cups), 2400, places=6)
		self.assertEqual(frappe.db.get_value("Ingredient Stock", f"{self.cafe}::{cups}", "qty_on_hand"), 60)
		beans = self.ingredient(buy_uom="bag", buy_size=1000)
		self.held(beans, 2000)
		self.receive(beans, 3, 260000, in_buying_unit=1)
		self.assertAlmostEqual(self.cost(beans), 236, places=6)

	def test_last_price_is_the_default_and_behaves_as_before(self):
		beans = self.ingredient()
		self.held(beans, 2000)
		for price, after in ((260, 260), (None, 260), (0, 0)):
			self.receive(beans, 1000, price)
			self.assertEqual(self.cost(beans), after)


class TestReceiving(StockCostTestCase):
	FIELDS = ["qty_change", "purchase_qty", "purchase_uom", "purchase_size", "purchase_price",
	          "cost_per_unit", "price_entry", "cost_before", "cost_after"]

	def setUp(self):
		super().setUp()
		self.method(AVERAGE)
		self.cups = self.ingredient("UT Cups", "pc", 2000, buy_uom="box", buy_size=24)
		self.held(self.cups, 12)

	def line(self):
		rows = frappe.get_all("Ingredient Ledger Entry", fields=self.FIELDS,
		                      filters={"ingredient": self.cups, "reason": "Received"})
		self.assertEqual(len(rows), 1)
		return tuple(rows[0][f] for f in self.FIELDS)

	def test_the_line_keeps_what_was_bought(self):
		self.receive(self.cups, 2, 60000, in_buying_unit=1)
		self.assertEqual(self.line(), (48, 2, "box", 24, 60000, 2500, "Entered", 2000, 2400))

	def test_no_price_says_so(self):
		self.receive(self.cups, 10)
		self.assertEqual(self.line(), (10, 10, "pc", 1, 0, 2000, "Not entered", 2000, 2000))

	def test_an_old_style_call_is_in_the_stock_unit(self):
		self.receive(self.cups, 12, 3000)
		self.assertEqual(self.line(), (12, 12, "pc", 1, 3000, 3000, "Entered", 2000, 2500))

	def test_a_pack_size_changed_for_one_delivery(self):
		self.receive(self.cups, 2, in_buying_unit=1, buy_size=20)
		self.assertEqual(self.line()[:4], (40, 2, "box", 20))
		self.assertEqual(frappe.db.get_value("Ingredient", self.cups, "buy_size"), 24)

	def test_what_is_refused(self):
		loose = self.ingredient("UT Loose")
		foreign = self.ingredient("UT Foreign", prop=PROP_B)
		for ing, price, row in (
			(loose, None, {"in_buying_unit": 1}),
			(self.cups, None, {"in_buying_unit": 1, "buy_uom": "sack"}),
			(self.cups, None, {"in_buying_unit": 1, "buy_size": 0}),
			(self.cups, -1, {}),
			(foreign, None, {}),
		):
			with self.subTest(row=row, price=price), self.assertRaises(frappe.ValidationError):
				self.receive(ing, 1, price, **row)

	def test_a_stock_unit_changed_since_the_screen_showed_it_is_refused(self):
		beans = self.ingredient()
		with self.assertRaises(frappe.ValidationError):
			self.receive(beans, 5, 12000, uom="kg")
		self.receive(beans, 5, 12000, uom="g")
		self.assertEqual(frappe.db.get_value(
			"Ingredient Stock", f"{self.cafe}::{beans}", "qty_on_hand"), 5)

	def test_one_bad_row_moves_nothing(self):
		with self.assertRaises(frappe.ValidationError):
			inventory.receive_stock(PROP_A, self.cafe, [
				{"ingredient": self.cups, "qty": 5, "cost_per_unit": 9000},
				{"ingredient": self.cups, "qty": 0}])
		self.assertEqual(self.cost(self.cups), 2000)
		self.assertEqual(frappe.db.get_value(
			"Ingredient Stock", f"{self.cafe}::{self.cups}", "qty_on_hand"), 12)

	def test_the_same_ingredient_twice_is_two_deliveries(self):
		beans = self.ingredient()
		self.held(beans, 2000)
		inventory.receive_stock(PROP_A, self.cafe, [
			{"ingredient": beans, "qty": 1000, "cost_per_unit": 260},
			{"ingredient": beans, "qty": 1000, "cost_per_unit": 300}])
		self.assertAlmostEqual(self.cost(beans), 240, places=6)

	def test_a_delivery_that_lands_while_this_one_waits_is_counted(self):
		# played in order, as a second connection can't see this test's rows
		beans = self.ingredient()
		self.held(beans, 2000)
		real, state = inventory._lock_ingredients, {"done": False}

		def other_lands_first(names):
			real(names)
			if not state["done"]:
				state["done"] = True
				self.receive(beans, 1000, 260, outlet=self.bar)

		with patch.object(inventory, "_lock_ingredients", other_lands_first):
			self.receive(beans, 1000, 300)
		self.assertAlmostEqual(self.cost(beans), 240, places=6)


class TestPurchaseHistory(StockCostTestCase):
	def test_deliveries_of_every_outlet_newest_first(self):
		beans = self.ingredient()
		self.receive(beans, 1000, 260)
		self.receive(beans, 500, 300, outlet=self.bar)
		self.held(beans, 10)
		rows = inventory.ingredient_ledger(PROP_A, self.cafe, beans, purchases_only=1)
		self.assertEqual([(r["outlet_name"], r["qty_change"], r["purchase_price"]) for r in rows],
		                 [("UT Bar", 500, 300), ("UT Cafe", 1000, 260)])

	def test_a_delivery_is_not_pushed_off_by_other_movements(self):
		beans = self.ingredient()
		self.receive(beans, 1000, 260)
		for qty in range(1, 61):
			self.held(beans, qty)
		self.assertEqual(len(inventory.ingredient_ledger(PROP_A, self.cafe, beans, purchases_only=1)), 1)

	def test_all_movements_stays_per_outlet_and_carries_the_price(self):
		beans = self.ingredient()
		self.receive(beans, 1000, 260)
		self.receive(beans, 500, 300, outlet=self.bar)
		rows = inventory.ingredient_ledger(PROP_A, self.cafe, beans)
		self.assertEqual([(r["outlet"], r["price_entry"], r["cost_per_unit"]) for r in rows],
		                 [(self.cafe, "Entered", 260)])


class TestWhatTheDeskReads(StockCostTestCase):
	MESSAGES = (
		"A price cannot be below zero.",
		"{0} has no buying unit.",
		"A buying unit must hold more than zero {0}.",
		"The buying unit of {0} changed. Close the window and open it again.",
		"The unit of {0} changed. Close the window and open it again.",
		"Give a buying unit both a name and how many {0} it holds.",
		"{0} already has stock history or is on a recipe, so its unit stays {1}.",
	)

	def test_every_new_refusal_is_translated(self):
		from frappe.translate import clear_cache, get_all_translations
		clear_cache()
		for lang in ("ar", "es", "pt", "sw", "vi", "zh"):
			known = get_all_translations(lang)
			self.assertEqual([m for m in self.MESSAGES if m not in known], [], lang)
