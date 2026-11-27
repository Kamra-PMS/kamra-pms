"""Ingredients made here: their rules, their worked-out cost, and production."""

from __future__ import annotations

from functools import partial
from unittest.mock import patch

import frappe

from kamra import banquet, inventory, pos
from kamra.tests.audit_fixtures import PROP_A, PROP_B
from kamra.tests.test_rbac import _user
from kamra.tests.test_stock_corrections import WriterCase, ago


class MadeCase(WriterCase):
	def made(self, name="UT Syrup", parts=(), batch=1000, uom="ml", **extra):
		return frappe.get_doc({
			"doctype": "Ingredient", "property": PROP_A, "ingredient_name": name,
			"uom": uom, "is_made": 1, "batch_qty": batch,
			"recipe": [{"ingredient": i, "qty": q} for i, q in parts], **extra,
		}).insert(ignore_permissions=True).name

	def syrup(self, **extra):
		"""The design's example: sugar 18 per g, water 1 per ml, and a batch of
		1,000 ml from 500 g and 600 ml."""
		self.sugar = self.ingredient("UT Sugar", "g", cost=18)
		self.water = self.ingredient("UT Water", "ml", cost=1)
		return self.made(parts=[(self.sugar, 500), (self.water, 600)], **extra)

	def change(self, ing, **values):
		doc = frappe.get_doc("Ingredient", ing)
		doc.update(values)
		doc.save()
		return doc

	def settle(self):
		"""Run the cost work queued for after the commit (commits are off here,
		so nothing else runs it). Other queued callbacks are left alone."""
		queue = frappe.db.after_commit._functions
		mine = [f for f in queue
		        if isinstance(f, partial) and f.func is inventory._recost]
		for f in mine:
			queue.remove(f)
			f()


class TestMadeRules(MadeCase):
	def refuses(self, words, **kw):
		with self.assertRaisesRegex(frappe.ValidationError, words):
			self.made(**kw)

	def refuses_change(self, words, ing, **values):
		with self.assertRaisesRegex(frappe.ValidationError, words):
			self.change(ing, **values)

	def test_it_saves_with_its_recipe(self):
		doc = frappe.get_doc("Ingredient", self.syrup())
		self.assertEqual(
			(doc.is_made, doc.batch_qty, [(r.ingredient, r.qty) for r in doc.recipe]),
			(1, 1000, [(self.sugar, 500), (self.water, 600)]))

	def test_a_batch_a_line_and_quantities_are_needed(self):
		sugar = self.ingredient("UT Sugar", "g")
		for batch in (0, -1):
			with self.subTest(batch=batch):
				self.refuses("one batch", parts=[(sugar, 5)], batch=batch)
		self.refuses("at least one ingredient", parts=[])
		for qty in (0, -5):
			with self.subTest(qty=qty):
				self.refuses("above zero", parts=[(sugar, qty)])

	def test_a_blank_line_is_dropped(self):
		sugar = self.ingredient("UT Sugar", "g")
		made = self.made(parts=[(sugar, 5), ("", ""), (None, 0)])
		self.assertEqual(len(frappe.get_doc("Ingredient", made).recipe), 1)

	def test_only_bought_ingredients_of_this_property_go_into_it(self):
		syrup = self.syrup()
		self.refuses("is made here", name="UT Sauce", parts=[(syrup, 10)])
		theirs = self.ingredient("UT Theirs", "g", prop=PROP_B)
		self.refuses("another property", name="UT Sauce", parts=[(theirs, 10)])
		self.refuses_change(
			"itself", syrup, recipe=[{"ingredient": syrup, "qty": 1}])

	def test_one_that_a_made_one_uses_cannot_become_made(self):
		self.syrup()
		self.refuses_change(
			"used to make UT Syrup", self.sugar, is_made=1, batch_qty=10,
			recipe=[{"ingredient": self.water, "qty": 1}])

	def test_the_typed_cost_is_ignored(self):
		syrup = self.syrup(cost_per_unit=999)
		self.assertEqual(self.cost(syrup), 0, "until it is worked out")
		frappe.db.set_value("Ingredient", syrup, "cost_per_unit", 9.6)
		self.change(syrup, cost_per_unit=999)
		self.assertEqual(self.cost(syrup), 9.6)

	def test_made_here_locks_once_there_is_stock_history(self):
		syrup = self.syrup()
		self.count(syrup, 5)
		self.refuses_change("stock history", syrup, is_made=0)
		honey = self.ingredient("UT Honey", "g")
		self.deliver(honey, 5)
		self.refuses_change(
			"stock history", honey, is_made=1, batch_qty=10,
			recipe=[{"ingredient": self.sugar, "qty": 1}])
		# a number sent as text is not a change
		self.change(syrup, is_made="1")

	def test_the_unit_locks_while_it_has_its_own_recipe(self):
		self.refuses_change("unit stays ml", self.syrup(), uom="L")

	def test_switching_it_off_clears_the_recipe(self):
		syrup = self.syrup()
		doc = self.change(syrup, is_made=0)
		self.assertEqual((doc.batch_qty, len(doc.recipe)), (0, 0))
		self.assertFalse(frappe.db.exists("Menu Item Ingredient", {"parent": syrup}))
		self.change(syrup, uom="L")

	def test_a_part_cannot_be_deleted(self):
		self.syrup()
		with self.assertRaisesRegex(frappe.ValidationError, "1 recipe"):
			inventory.delete_ingredient(self.sugar)


class TestTheWorkedOutCost(MadeCase):
	def test_saving_the_recipe_works_it_out(self):
		syrup = self.syrup()
		self.settle()
		self.assertEqual(self.cost(syrup), 9.6)

	def test_a_dearer_delivery_changes_it_and_cancelling_puts_it_back(self):
		syrup = self.syrup()
		self.settle()
		self.deliver(self.sugar, 1000, price=20)
		self.assertEqual(self.cost(syrup), 9.6, "not before the delivery is saved")
		self.settle()
		self.assertEqual(self.cost(syrup), 10.6)
		inventory.cancel_stock_entry(PROP_A, self.rows(self.sugar)[0].name, "wrong price")
		self.settle()
		self.assertEqual((self.cost(self.sugar), self.cost(syrup)), (18, 9.6))

	def test_a_typed_cost_and_the_ingredient_screen_change_it(self):
		syrup = self.syrup()
		self.settle()
		self.change(self.sugar, cost_per_unit=20)
		self.settle()
		self.assertEqual(self.cost(syrup), 10.6)

	def test_the_recipe_and_the_batch_change_it(self):
		syrup = self.syrup()
		self.settle()
		self.change(syrup, batch_qty=2000)
		self.settle()
		self.assertEqual(self.cost(syrup), 4.8)
		self.change(syrup, recipe=[{"ingredient": self.sugar, "qty": 1000}])
		self.settle()
		self.assertEqual(self.cost(syrup), 9)

	def test_one_part_without_a_cost_means_no_cost_yet(self):
		syrup = self.syrup()
		self.settle()
		self.change(self.water, cost_per_unit=0)
		self.settle()
		self.assertEqual(self.cost(syrup), 0)
		latte = frappe.get_doc({
			"doctype": "Menu Item", "property": PROP_A, "outlet": self.cafe,
			"item_name": "UT Latte", "price": 25000,
			"recipe": [{"ingredient": syrup, "qty": 20}]}).insert(ignore_permissions=True).name
		dish = [d for d in inventory.recipe_overview(PROP_A) if d.name == latte][0]
		self.assertEqual((dish["cost"], dish["uncosted"]), (None, ["UT Water (in UT Syrup)"]))
		listed = {i.name: i for i in inventory.ingredients(PROP_A)}
		self.assertEqual((listed[syrup].is_made, listed[syrup].missing), (1, ["UT Water"]))
		self.assertNotIn("missing", listed[self.water])
		self.assertEqual(inventory.menu_recipe(latte)["recipe"][0]["missing"], ["UT Water"])

	def test_six_decimals(self):
		sugar = self.ingredient("UT Sugar", "g", cost=1)
		third = self.made(parts=[(sugar, 1)], batch=3)
		self.settle()
		self.assertEqual(self.cost(third), 0.333333)

	def test_an_ingredient_nobody_makes_from_costs_nothing_extra(self):
		beans = self.ingredient()
		self.settle()
		self.deliver(beans, 5, price=3)
		self.settle()
		self.assertEqual(self.cost(beans), 3)

	def test_a_failure_is_logged_and_keeps_what_else_was_queued(self):
		syrup = self.syrup()
		done = []
		frappe.db.after_commit.add(lambda: done.append("other"))
		with patch.object(inventory, "_made_cost", side_effect=RuntimeError("boom")), \
				patch.object(frappe.db, "rollback") as rolled_back, \
				patch.object(frappe, "log_error") as logged, \
				patch.object(frappe.db, "commit",
				             side_effect=lambda: frappe.db.after_commit.run()):
			self.settle()
		self.assertEqual(done, ["other"], "what was queued runs before any rollback")
		self.assertEqual(rolled_back.call_count, 3, "tried three times")
		self.assertIn(syrup, str(logged.call_args))
		self.assertEqual(self.cost(syrup), 0)


class ProduceCase(MadeCase):
	def setUp(self):
		super().setUp()
		self.syr = self.syrup()
		self.settle()
		self.held(self.sugar, 800)
		self.held(self.water, 5000)
		self.addCleanup(frappe.set_user, "Administrator")

	def produce(self, qty=2000, **kw):
		return inventory.produce(PROP_A, self.cafe, self.syr, qty, **kw)

	def made_rows(self, ing):
		return self.rows(ing, reason="Production")


class TestProducing(ProduceCase):
	def test_the_worked_example(self):
		got = self.produce()
		self.assertEqual(
			[(u["ingredient_name"], u["uom"], u["qty"], u["qty_on_hand"]) for u in got["used"]],
			[("UT Sugar", "g", 1000, -200), ("UT Water", "ml", 1200, 3800)])
		self.assertEqual(got["qty_on_hand"], 2000)
		self.assertStock(self.sugar, -200)
		self.assertStock(self.water, 3800)
		self.assertStock(self.syr, 2000)
		rows = [self.made_rows(i)[0] for i in (self.sugar, self.water, self.syr)]
		self.assertEqual([r.qty_change for r in rows], [-1000, -1200, 2000])
		self.assertEqual([r.cost_per_unit for r in rows], [18, 1, 9.6])
		self.assertEqual({r.batch_id for r in rows}, {got["batch_id"]})
		self.assertEqual(rows[0].note, "For UT Syrup")
		self.assertEqual(self.cost(self.syr), 9.6, "producing sets no cost")

	def test_a_sale_takes_the_syrup_and_not_what_is_in_it(self):
		self.produce()
		latte = frappe.get_doc({
			"doctype": "Menu Item", "property": PROP_A, "outlet": self.cafe,
			"item_name": "UT Latte", "price": 25000,
			"recipe": [{"ingredient": self.syr, "qty": 20}]}).insert(ignore_permissions=True).name
		order = pos.create_order(self.cafe, [{"menu_item": latte, "qty": 1}], table_no="T1")["order"]
		pos.fire_kot(order)
		self.assertStock(self.syr, 1980)
		self.assertStock(self.sugar, -200)
		self.assertStock(self.water, 3800)

	def test_cancelling_the_batch_takes_all_of_it_back(self):
		self.produce()
		self.waste(self.syr, 20)
		got = inventory.cancel_stock_entry(
			PROP_A, self.made_rows(self.water)[0].name, "spoilt count")
		self.assertEqual(got["cancelled"], 3)
		self.assertStock(self.sugar, 800)
		self.assertStock(self.water, 5000)
		self.assertStock(self.syr, -20)

	def test_the_cancel_refusal_names_batches_too(self):
		self.move(self.sugar, -1)  # kitchen usage cannot be cancelled
		used = self.rows(self.sugar, reason="Consumed")[0].name
		with self.assertRaisesRegex(frappe.ValidationError, "production batches"):
			inventory.cancel_stock_entry(PROP_A, used, "mistake")

	def test_part_of_a_batch_and_a_note(self):
		got = self.produce(333, note="half jar")
		self.assertEqual([u["qty"] for u in got["used"]], [166.5, 199.8])
		self.assertEqual(self.made_rows(self.sugar)[0].note, "For UT Syrup: half jar")
		self.assertEqual(self.made_rows(self.syr)[0].note, "half jar")

	def test_the_same_part_on_two_lines_is_one_move(self):
		self.change(self.syr, recipe=[{"ingredient": self.sugar, "qty": 1},
		                              {"ingredient": self.sugar, "qty": 2}], batch_qty=3)
		self.produce(10)
		self.assertEqual([r.qty_change for r in self.made_rows(self.sugar)], [-10])

	def test_a_batch_dated_earlier_goes_in_before_a_later_count(self):
		self.held(self.syr, 50)
		self.produce(1000, posted_at=ago(hours=2))
		self.assertStock(self.syr, 50)
		self.assertStock(self.sugar, 800)
		self.assertEqual(self.made_rows(self.syr)[0].qty_change, 1000)

	def test_a_part_without_a_cost_leaves_the_batch_without_one(self):
		self.change(self.water, cost_per_unit=0)
		self.produce(100)
		self.assertEqual(self.made_rows(self.syr)[0].cost_per_unit, 0)
		self.assertEqual(self.made_rows(self.sugar)[0].cost_per_unit, 18)

	def test_refusals(self):
		def refused(words, **kw):
			args = {"property": PROP_A, "outlet": self.cafe, "ingredient": self.syr, "qty": 10, **kw}
			with self.assertRaisesRegex(frappe.ValidationError, words):
				inventory.produce(**args)

		# text that is no number never gets this far: the framework refuses it
		for qty in (0, -1, "nan", "inf"):
			with self.subTest(qty=qty):
				refused("above zero", qty=qty)
		refused("future", posted_at=ago(hours=-1))
		refused("not made here", ingredient=self.sugar)
		theirs = self.ingredient("UT Theirs", "g", prop=PROP_B)
		refused("another property", ingredient=theirs)
		other = frappe.get_doc({
			"doctype": "POS Outlet", "property": PROP_B, "outlet_name": "UT Their",
			"outlet_type": "Restaurant"}).insert(ignore_permissions=True).name
		refused("another property", outlet=other)
		# a recipe that slipped past the one-level rule
		frappe.db.set_value("Ingredient", self.sugar, "is_made", 1)
		refused("is made here itself")
		self.assertEqual(self.made_rows(self.syr), [])

	def test_only_stock_managers_produce(self):
		desk = _user("ut-desk-produce@example.com", "Front Desk")
		frappe.set_user(desk)  # nosemgrep: frappe-setuser -- test acts as this user
		with self.assertRaises(frappe.PermissionError):
			self.produce()
		chef = _user("ut-fnb-produce@example.com", "F&B Manager")
		frappe.set_user(chef)  # nosemgrep: frappe-setuser -- test acts as this user
		self.assertEqual(self.produce(10)["qty_on_hand"], 10)

	def test_it_cannot_be_received(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Record it with Produce"):
			self.deliver(self.syr, 5)
		self.assertEqual(self.rows(self.syr), [])


class TestAroundProduction(ProduceCase):
	def test_the_summary_has_a_production_column(self):
		self.produce()
		today = frappe.utils.nowdate()
		rows = {r["ingredient"]: r for r in inventory.stock_summary(
			PROP_A, today, today, outlet=self.cafe)["rows"]}
		self.assertEqual(
			[(rows[i]["production"], rows[i]["ending"]) for i in (self.sugar, self.water, self.syr)],
			[(-1000, -200), (-1200, 3800), (2000, 2000)])

	def test_the_stock_list_marks_what_is_made_here(self):
		shelf = {r["ingredient"]: r for r in inventory.stock_list(
			PROP_A, self.cafe, include_unstocked=1)}
		self.assertEqual((shelf[self.syr].is_made, shelf[self.sugar].is_made), (1, 0))

	def test_a_low_ingredient_says_what_it_makes(self):
		inventory.set_par_level(PROP_A, self.cafe, self.sugar, 900)
		low = [r for r in inventory.low_stock(PROP_A, self.cafe) if r["ingredient"] == self.sugar]
		self.assertEqual((low[0]["makes"], low[0]["dishes"]), (["UT Syrup"], []))

	def test_a_banquet_dish_costs_the_syrup_itself(self):
		dish = banquet.save_dish(
			PROP_A, "UT Syrup Cake", recipe=[{"ingredient": self.syr, "qty": 10}])
		self.assertEqual(dish["cost_per_portion"], 96)


class TestMessages(MadeCase):
	MESSAGES = (
		"{0} already has stock history, so \"Made here\" stays as it is.",
		"Say how much one batch makes, above zero.",
		"Something made here needs at least one ingredient in its recipe.",
		"{0} is used to make {1}, so it cannot be made here itself.",
		"Every recipe line needs a quantity above zero.",
		"{0} cannot be made from itself.",
		"{0} belongs to another property.",
		"{0} is made here too. Use only bought ingredients.",
		"{0} recipe(s) use this ingredient. Deactivate it instead.",
		"{0} (in {1})",
		"{0} is made here. Record it with Produce, not as a delivery.",
		"Say how much was made, above zero.",
		"{0} is not made here.",
		"The recipe of {0} just changed. Try again.",
		"{0} is made here itself. Take it out of the recipe of {1}.",
		"That is too little to take anything from stock.",
	)

	def test_every_new_refusal_is_translated(self):
		from frappe.translate import clear_cache, get_all_translations
		clear_cache()
		for lang in ("ar", "es", "pt", "sw", "vi", "zh"):
			known = get_all_translations(lang)
			self.assertEqual([m for m in self.MESSAGES if m not in known], [], lang)
