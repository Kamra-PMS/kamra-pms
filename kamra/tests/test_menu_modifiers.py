"""Choices on a dish: milk, ice, extras (Menu Modifier Group / Option).

A real café menu: Es Kopi Susu 24.000, with Ice (must pick one: Normal, Less,
No ice), Milk (optional, one: Oat +8.000, Soy +6.000) and Extras (pick up to
two: Extra shot +6.000, Caramel +5.000, Whipped cream +4.000).

What these pin: the server prices and judges the choices (the till sends ids
only); the line's rate is the dish plus its choices and keeps its own copy of
what was sold; the kitchen ticket, the bill and the split carry them; a
choice's stock lines are taken at the fire, with the dish's recipe, once.
"""

from __future__ import annotations

from unittest.mock import patch

import frappe

from kamra import inventory, menu_modifiers, pos
from kamra.tests.audit_fixtures import PROP_A, TODAY, AuditTestCase, make_property


class MenuModifiersTest(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		make_property(PROP_A, business_date=TODAY)
		self.outlet = self.outlet_named("UT Choices Cafe")
		self.kopi = self.dish("UT Es Kopi Susu", 24000)
		self.nasi = self.dish("UT Nasi Goreng Choices", 35000)
		self.ice = self.group("Ice", [("Normal", 0), ("Less ice", 0), ("No ice", 0)],
		                      required=1, order=1)
		self.milk = self.group("Milk", [("Oat milk", 8000), ("Soy milk", 6000)], order=2)
		self.extras = self.group("Extras", [("Extra shot", 6000), ("Caramel", 5000),
		                                    ("Whipped cream", 4000)],
		                         multi=1, most=2, order=3)
		for g in (self.ice, self.milk, self.extras):
			self.offer(g, self.kopi)

	# fixtures -----------------------------------------------------------

	def outlet_named(self, label):
		name = frappe.db.get_value("POS Outlet", {"property": PROP_A, "outlet_name": label})
		if name:
			return name
		return frappe.get_doc({
			"doctype": "POS Outlet", "property": PROP_A, "outlet_name": label,
			"outlet_type": "Restaurant", "gst_rate": 5}).insert(ignore_permissions=True).name

	def dish(self, label, price, outlet=None):
		return frappe.get_doc({
			"doctype": "Menu Item", "property": PROP_A, "outlet": outlet or self.outlet,
			"item_name": label, "category": "Drinks", "price": price,
			"is_veg": 1, "available": 1, "prep_station": "Kitchen",
		}).insert(ignore_permissions=True).name

	def group(self, label, options, required=0, multi=0, most=0, order=0, outlet=None):
		out = menu_modifiers.save_modifier_group(
			outlet or self.outlet, label,
			[{"option_name": n, "price": p} for n, p in options],
			required=required, multi=multi, max_choices=most, sort_order=order)
		return out["name"]

	def offer(self, group, dish):
		doc = frappe.get_doc("Menu Item", dish)
		doc.append("modifier_groups", {"modifier_group": group})
		doc.save(ignore_permissions=True)

	def option(self, group, label):
		return frappe.db.get_value("Menu Modifier Option",
		                           {"modifier_group": group, "option_name": label}, "name")

	def order(self, dish, picks, qty=1, **kw):
		line = {"menu_item": dish, "qty": qty,
		        "modifiers": [self.option(g, n) for g, n in picks]}
		return pos.create_order(self.outlet, [line], table_no="T1",
		                        order_type="Dine In", **kw)["order"]

	def doc(self, order):
		return frappe.get_doc("POS Order", order)

	# pricing and the snapshot ----------------------------------------------

	def test_the_server_prices_the_choices_and_the_line_keeps_them(self):
		o = self.order(self.kopi, [(self.ice, "Less ice"), (self.milk, "Oat milk"),
		                           (self.extras, "Extra shot"), (self.extras, "Caramel")],
		               qty=2)
		line = self.doc(o).items[0]
		self.assertEqual(line.modifier_total, 19000)        # 8.000 + 6.000 + 5.000
		self.assertEqual(line.rate, 43000)                  # 24.000 + 19.000
		self.assertEqual(line.amount, 86000)
		self.assertEqual(self.doc(o).order_total, 86000)
		kept = menu_modifiers.load(line.modifiers)
		self.assertEqual([c["name"] for c in kept],
		                 ["Less ice", "Oat milk", "Extra shot", "Caramel"])
		self.assertEqual([c["group"] for c in kept], ["Ice", "Milk", "Extras", "Extras"])

	def test_a_price_finer_than_two_decimals_is_kept_whole(self):
		# 0.125 is a real price in a 3-decimal currency (KWD, BHD, OMR); 4545.454545
		# is 5000 with a 10% tax on top, kept to 6 places so the guest pays a round figure
		kopi = self.dish("UT Fine Kopi", 25454.545455)
		fine = self.group("Fine", [("Fils", 0.125), ("Shot", 4545.454545)], multi=1)
		self.offer(fine, kopi)
		o = self.order(kopi, [(fine, "Fils"), (fine, "Shot")])
		line = self.doc(o).items[0]
		sold = sum(c["price"] for c in menu_modifiers.load(line.modifiers))
		self.assertAlmostEqual(line.modifier_total, 4545.579545, places=6)
		self.assertAlmostEqual(line.modifier_total, sold, places=6)      # the line's own copy agrees
		self.assertAlmostEqual(line.rate, 30000.125, places=6)
		self.assertAlmostEqual(line.rate - line.modifier_total, 25454.545455, places=6)

	def test_a_bill_looks_the_groups_up_once_however_many_lines(self):
		pick = [self.option(self.ice, "Normal")]
		lines = [{"menu_item": self.kopi, "qty": 1, "modifiers": pick},
		         {"menu_item": self.nasi, "qty": 1},
		         {"menu_item": self.kopi, "qty": 2, "modifiers": pick}]
		with patch.object(menu_modifiers, "groups_for_items",
		                  wraps=menu_modifiers.groups_for_items) as looked_up:
			o = pos.create_order(self.outlet, lines, table_no="T1",
			                     order_type="Dine In")["order"]
		self.assertEqual(looked_up.call_count, 1)
		self.assertEqual(self.doc(o).order_total, 24000 + 35000 + 48000)

	def test_a_dish_without_choices_bills_exactly_as_before(self):
		o = pos.create_order(self.outlet, [{"menu_item": self.nasi, "qty": 2}],
		                     table_no="T2", order_type="Dine In")["order"]
		line = self.doc(o).items[0]
		self.assertEqual((line.rate, line.modifier_total, line.modifiers), (35000, 0, None))
		self.assertEqual(self.doc(o).order_total, 70000)

	def test_the_price_a_till_sends_is_never_used(self):
		line = {"menu_item": self.kopi, "qty": 1, "rate": 1, "modifier_total": 99999,
		        "modifiers": [self.option(self.ice, "Normal")]}
		o = pos.create_order(self.outlet, [line], table_no="T1",
		                     order_type="Dine In")["order"]
		self.assertEqual(self.doc(o).items[0].rate, 24000)

	def test_a_menu_price_change_does_not_re_price_a_bill_that_is_open(self):
		o = self.order(self.kopi, [(self.ice, "Normal"), (self.milk, "Oat milk")])
		frappe.db.set_value("Menu Item", self.kopi, "price", 99000)
		frappe.db.set_value("Menu Modifier Option", self.option(self.milk, "Oat milk"),
		                    "price", 50000)
		pos.add_items(o, [{"menu_item": self.nasi, "qty": 1}])   # any later save of the bill
		first, second = self.doc(o).items
		self.assertEqual((first.rate, second.rate), (32000, 35000))
		self.assertEqual(self.doc(o).order_total, 67000)

	def test_the_same_dish_with_different_choices_is_two_lines(self):
		lines = [
			{"menu_item": self.kopi, "qty": 1, "modifiers": [self.option(self.ice, "Normal")]},
			{"menu_item": self.kopi, "qty": 1, "modifiers": [
				self.option(self.ice, "No ice"), self.option(self.milk, "Soy milk")]},
		]
		o = pos.create_order(self.outlet, lines, table_no="T1",
		                     order_type="Dine In")["order"]
		self.assertEqual([i.rate for i in self.doc(o).items], [24000, 30000])
		self.assertEqual(self.doc(o).order_total, 54000)

	def test_a_round_added_later_prices_its_choices_too(self):
		o = self.order(self.kopi, [(self.ice, "Normal")])
		pos.add_items(o, [{"menu_item": self.kopi, "qty": 1, "modifiers": [
			self.option(self.ice, "Normal"), self.option(self.milk, "Oat milk")]}])
		self.assertEqual(self.doc(o).order_total, 24000 + 32000)

	# the rules ------------------------------------------------------------

	def test_a_compulsory_group_must_be_answered(self):
		with self.assertRaisesRegex(frappe.ValidationError, r"choose Ice.*Normal \(MMO-"):
			pos.create_order(self.outlet, [{"menu_item": self.kopi, "qty": 1}],
			                 table_no="T1", order_type="Dine In")

	def test_a_one_only_group_takes_one(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Milk takes one choice only"):
			self.order(self.kopi, [(self.ice, "Normal"), (self.milk, "Oat milk"),
			                       (self.milk, "Soy milk")])

	def test_several_choices_stop_at_the_limit(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Extras takes at most 2"):
			self.order(self.kopi, [(self.ice, "Normal"), (self.extras, "Extra shot"),
			                       (self.extras, "Caramel"), (self.extras, "Whipped cream")])

	def test_no_limit_means_every_choice_may_be_ticked(self):
		frappe.db.set_value("Menu Modifier Group", self.extras, "max_choices", 0)
		o = self.order(self.kopi, [(self.ice, "Normal"), (self.extras, "Extra shot"),
		                           (self.extras, "Caramel"), (self.extras, "Whipped cream")])
		self.assertEqual(self.doc(o).items[0].modifier_total, 15000)

	def test_a_choice_the_dish_does_not_offer_is_refused(self):
		other = self.group("Spice", [("Mild", 0), ("Hot", 0)])
		with self.assertRaisesRegex(frappe.ValidationError, "does not offer that choice"):
			pos.create_order(self.outlet, [{"menu_item": self.nasi, "qty": 1,
			                                "modifiers": [self.option(other, "Hot")]}],
			                 table_no="T1", order_type="Dine In")

	def test_a_group_nobody_can_answer_does_not_block_the_dish(self):
		frappe.get_doc({"doctype": "Menu Modifier Group", "property": PROP_A,
		                "outlet": self.outlet, "group_name": "UT Empty", "required": 1}
		               ).insert(ignore_permissions=True)
		empty = frappe.db.get_value("Menu Modifier Group", {"group_name": "UT Empty"})
		self.offer(empty, self.nasi)
		o = pos.create_order(self.outlet, [{"menu_item": self.nasi, "qty": 1}],
		                     table_no="T1", order_type="Dine In")["order"]
		self.assertEqual(self.doc(o).order_total, 35000)

	# the till's menu ---------------------------------------------------------

	def test_the_menu_sends_each_group_once_and_the_ids_per_dish(self):
		menu = pos.pos_menu(self.outlet)
		groups = {g["group_name"]: g for g in menu["modifier_groups"]}
		self.assertEqual(sorted(groups), ["Extras", "Ice", "Milk"])
		self.assertEqual(groups["Extras"]["max_choices"], 2)
		self.assertEqual([o["option_name"] for o in groups["Ice"]["options"]],
		                 ["Normal", "Less ice", "No ice"])
		items = {i["item_name"]: i for c in menu["categories"] for i in c["items"]}
		self.assertEqual(items["UT Es Kopi Susu"]["group_ids"],
		                 [self.ice, self.milk, self.extras])    # the group's Order
		self.assertNotIn("group_ids", items["UT Nasi Goreng Choices"])

	# a bill keeps what was sold --------------------------------------------------

	def test_editing_or_deleting_a_group_never_changes_a_bill_already_written(self):
		o = self.order(self.kopi, [(self.ice, "Normal"), (self.milk, "Oat milk")])
		menu_modifiers.save_modifier_group(
			self.outlet, "Milk", [{"name": self.option(self.milk, "Oat milk"),
			                       "option_name": "Barista oat", "price": 12000}],
			name=self.milk)
		menu_modifiers.delete_modifier_group(self.ice)
		line = pos.order_detail(o)["items"][0]
		self.assertEqual([c["name"] for c in line["modifiers"]], ["Normal", "Oat milk"])
		self.assertEqual((line["rate"], line["amount"]), (32000, 32000))

	def test_split_carries_the_choices(self):
		lines = [{"menu_item": self.kopi, "qty": 1, "modifiers": [
			self.option(self.ice, "Normal"), self.option(self.milk, "Oat milk")]},
			{"menu_item": self.nasi, "qty": 1}]
		o = pos.create_order(self.outlet, lines, table_no="T1",
		                     order_type="Dine In")["order"]
		coffee = [i for i in self.doc(o).items if i.menu_item == self.kopi][0].name
		new = pos.split_order(o, [coffee])["new_order"]
		moved = self.doc(new).items[0]
		self.assertEqual((moved.rate, moved.modifier_total), (32000, 8000))
		self.assertEqual([c["name"] for c in menu_modifiers.load(moved.modifiers)],
		                 ["Normal", "Oat milk"])
		self.assertEqual(self.doc(new).order_total + self.doc(o).order_total, 67000)

	# the kitchen, the till's ticket and the bill -------------------------------------

	def test_the_kot_the_kitchen_screen_and_the_bill_show_the_choices(self):
		out = pos.send_order(self.outlet, [{"menu_item": self.kopi, "qty": 1, "modifiers": [
			self.option(self.ice, "Less ice"), self.option(self.extras, "Extra shot")]}],
			property=PROP_A, table_no="T1")
		self.assertEqual(out["fired_items"][0]["modifiers"], ["Less ice", "Extra shot"])
		self.assertEqual(out["ticket"]["items"][0]["modifiers"], ["Less ice", "Extra shot"])
		queue = [q for q in pos.kitchen_queue(PROP_A, self.outlet) if q["name"] == out["order"]]
		self.assertEqual(queue[0]["items"][0]["modifiers"], ["Less ice", "Extra shot"])
		bill = pos.bill_data(out["order"])
		self.assertEqual(bill["items"][0]["modifiers"], ["Less ice", "Extra shot"])
		self.assertEqual(bill["items"][0]["rate"], 30000)
		self.assertEqual(bill["items"][0]["amount"], bill["items"][0]["qty"] * bill["items"][0]["rate"])

	# stock ---------------------------------------------------------------------------

	def ingredient(self, label, uom):
		return frappe.get_doc({"doctype": "Ingredient", "property": PROP_A,
		                       "ingredient_name": label, "uom": uom}
		                      ).insert(ignore_permissions=True).name

	def on_hand(self, ing):
		return frappe.db.get_value("Ingredient Stock", f"{self.outlet}::{ing}", "qty_on_hand")

	def test_a_choice_takes_its_ingredients_with_the_recipe_once(self):
		beans = self.ingredient("UT Coffee Beans", "g")
		oat = self.ingredient("UT Oat Drink", "ml")
		for ing in (beans, oat):
			inventory.receive_stock(PROP_A, self.outlet, [{"ingredient": ing, "qty": 1000}])
		dish = frappe.get_doc("Menu Item", self.kopi)
		dish.set("recipe", [{"ingredient": beans, "qty": 18}])
		dish.save(ignore_permissions=True)
		shot = self.option(self.extras, "Extra shot")
		oat_milk = self.option(self.milk, "Oat milk")
		menu_modifiers.save_modifier_group(
			self.outlet, "Extras", [
				{"name": shot, "option_name": "Extra shot", "price": 6000,
				 "ingredients": [{"ingredient": beans, "qty": 18}]},
				{"name": self.option(self.extras, "Caramel"), "option_name": "Caramel", "price": 5000},
				{"name": self.option(self.extras, "Whipped cream"), "option_name": "Whipped cream", "price": 4000}],
			multi=1, max_choices=2, sort_order=3, name=self.extras)
		menu_modifiers.save_modifier_group(
			self.outlet, "Milk", [
				{"name": oat_milk, "option_name": "Oat milk", "price": 8000,
				 "ingredients": [{"ingredient": oat, "qty": 150}]},
				{"name": self.option(self.milk, "Soy milk"), "option_name": "Soy milk", "price": 6000}],
			sort_order=2, name=self.milk)
		out = pos.send_order(self.outlet, [{"menu_item": self.kopi, "qty": 2, "modifiers": [
			self.option(self.ice, "Normal"), oat_milk, shot]}],
			property=PROP_A, table_no="T1")
		# beans: 2 x (18 recipe + 18 extra shot); oat: 2 x 150
		self.assertEqual(self.on_hand(beans), 1000 - 72)
		self.assertEqual(self.on_hand(oat), 1000 - 300)
		pos.fire_kot(out["order"])                          # nothing new to fire: no second take
		self.assertEqual(self.on_hand(beans), 1000 - 72)

	def test_a_choice_with_no_ingredients_leaves_the_stock_alone(self):
		beans = self.ingredient("UT Quiet Beans", "g")
		inventory.receive_stock(PROP_A, self.outlet, [{"ingredient": beans, "qty": 500}])
		pos.send_order(self.outlet, [{"menu_item": self.kopi, "qty": 1, "modifiers": [
			self.option(self.ice, "Normal"), self.option(self.milk, "Soy milk")]}],
			property=PROP_A, table_no="T1")
		self.assertEqual(self.on_hand(beans), 500)

	def test_a_voided_line_wastes_its_choices_ingredients_too(self):
		beans = self.ingredient("UT Waste Beans", "g")
		frappe.db.set_value("Ingredient", beans, "cost_per_unit", 200)
		inventory.receive_stock(PROP_A, self.outlet, [{"ingredient": beans, "qty": 1000}])
		dish = frappe.get_doc("Menu Item", self.kopi)
		dish.set("recipe", [{"ingredient": beans, "qty": 18}])
		dish.save(ignore_permissions=True)
		shot = self.option(self.extras, "Extra shot")
		menu_modifiers.save_modifier_group(
			self.outlet, "Extras", [{"name": shot, "option_name": "Extra shot", "price": 6000,
			                         "ingredients": [{"ingredient": beans, "qty": 18}]}],
			multi=1, max_choices=2, sort_order=3, name=self.extras)
		out = pos.send_order(self.outlet, [{"menu_item": self.kopi, "qty": 2, "modifiers": [
			self.option(self.ice, "Normal"), shot]}], property=PROP_A, table_no="T1")
		line = self.doc(out["order"]).items[0].name
		pos.void_item(out["order"], line, reason="spilled")
		report = inventory.wastage_report(PROP_A, self.outlet)
		mine = [r for r in report["lines"] if r["order_name"] == out["order"]]
		# 2 dishes x (18 g of the recipe + 18 g of the extra shot) x 200
		self.assertEqual(mine[0]["value"], 14400)
		self.assertEqual(report["total_value"], 14400)
		self.assertEqual(report["by_reason"], [{"reason": "spilled", "value": 14400}])
		self.assertNotIn("modifiers", mine[0])          # the report's rows keep their shape

	# the editor ---------------------------------------------------------------------------

	def test_saving_a_group_sets_its_choices_and_the_dishes_that_offer_it(self):
		out = menu_modifiers.save_modifier_group(
			self.outlet, "Spice", [{"option_name": "Mild"}, {"option_name": "Hot", "price": 0}],
			items=[self.nasi], required=1)
		self.assertEqual((out["options"], out["dishes"]), (2, 1))
		meta = menu_modifiers.groups_for_items([self.nasi])[self.nasi][0]
		self.assertEqual((meta["group_name"], meta["required"]), ("Spice", 1))
		# a second save with fewer dishes takes the group off the others
		menu_modifiers.save_modifier_group(
			self.outlet, "Spice", [{"name": self.option(out["name"], "Mild"),
			                        "option_name": "Mild"}],
			items=[], name=out["name"], required=1)
		self.assertFalse(menu_modifiers.groups_for_items([self.nasi]))
		self.assertEqual(frappe.db.count("Menu Modifier Option", {"modifier_group": out["name"]}), 1)

	def test_a_choice_keeps_its_identity_when_renamed_in_the_editor(self):
		oat = self.option(self.milk, "Oat milk")
		menu_modifiers.save_modifier_group(
			self.outlet, "Milk", [{"name": oat, "option_name": "Oat drink", "price": 9000},
			                      {"option_name": "Almond", "price": 7000}], name=self.milk)
		self.assertEqual(frappe.db.get_value("Menu Modifier Option", oat, "option_name"), "Oat drink")
		self.assertIsNone(self.option(self.milk, "Soy milk"))   # not sent: removed
		self.assertEqual(frappe.db.count("Menu Modifier Option", {"modifier_group": self.milk}), 2)

	def test_deleting_a_group_takes_it_off_every_dish(self):
		out = menu_modifiers.delete_modifier_group(self.milk)
		self.assertEqual(out["dishes"], 1)
		self.assertFalse(frappe.db.exists("Menu Modifier Group", self.milk))
		self.assertEqual(frappe.db.count("Menu Modifier Option", {"modifier_group": self.milk}), 0)
		self.assertNotIn(self.milk, [g["name"] for g in
		                             menu_modifiers.groups_for_items([self.kopi])[self.kopi]])

	def test_the_editor_refuses_what_would_break_the_till(self):
		for options, why in (
			([], "at least one choice"),
			([{"option_name": ""}], "needs a name"),
			([{"option_name": "A"}, {"option_name": "a"}], "twice"),
			([{"option_name": "Cheap", "price": -1}], "take money off"),
		):
			with self.assertRaisesRegex(frappe.ValidationError, why):
				menu_modifiers.save_modifier_group(self.outlet, "Bad", options)
		with self.assertRaisesRegex(frappe.ValidationError, "not a dish of this outlet"):
			other = self.outlet_named("UT Choices Bar")
			menu_modifiers.save_modifier_group(
				self.outlet, "Bad", [{"option_name": "A"}],
				items=[self.dish("UT Bar Beer", 40000, outlet=other)])

	def test_a_dish_cannot_offer_another_outlets_group(self):
		other = self.outlet_named("UT Choices Bar 2")
		foreign = self.group("Foreign", [("A", 0)], outlet=other)
		with self.assertRaisesRegex(frappe.ValidationError, "belongs to another outlet"):
			self.offer(foreign, self.nasi)

	# the dish's own form (REST PUT: update the document with its rows, save) -----------------

	def put(self, dish, **data):
		"""What the Menu screen's save does to a dish: load it, update it with what the form sent, save."""
		doc = frappe.get_doc("Menu Item", dish)
		doc.update(data)
		doc.save(ignore_permissions=True)
		return doc

	def groups_of(self, dish):
		return [g["name"] for g in menu_modifiers.groups_for_items([dish]).get(dish, [])]

	def test_ticking_a_group_on_the_dish_form_is_the_same_as_ticking_the_dish_in_the_group(self):
		rows = [{"modifier_group": self.ice}, {"modifier_group": self.milk}]
		self.put(self.nasi, modifier_groups=rows)
		self.assertEqual(self.groups_of(self.nasi), [self.ice, self.milk])       # the till's menu
		over = {g["name"]: g for g in menu_modifiers.modifier_overview(PROP_A)["groups"]}
		self.assertIn(self.nasi, over[self.ice]["items"])                          # the Choices editor
		self.assertIn(self.nasi, over[self.milk]["items"])
		self.put(self.nasi, modifier_groups=[{"modifier_group": self.milk}])      # untick Ice on the form
		self.assertEqual(self.groups_of(self.nasi), [self.milk])
		self.put(self.nasi, modifier_groups=[])
		self.assertFalse(self.groups_of(self.nasi))

	def test_saving_the_form_with_the_groups_it_loaded_changes_nothing(self):
		doc = frappe.get_doc("Menu Item", self.kopi)
		before = [(r.name, r.modifier_group) for r in doc.modifier_groups]
		sent = [r.as_dict() for r in doc.modifier_groups]            # what the form got and sends back
		versions = frappe.db.count("Version", {"ref_doctype": "Menu Item", "docname": self.kopi})
		self.put(self.kopi, price=24000, modifier_groups=sent)
		after = [(r.name, r.modifier_group) for r in frappe.get_doc("Menu Item", self.kopi).modifier_groups]
		self.assertEqual(after, before)                              # the same rows, not rewritten
		self.assertEqual(frappe.db.count("Version", {"ref_doctype": "Menu Item", "docname": self.kopi}), versions)

	def test_a_dish_saved_without_the_groups_key_keeps_its_groups(self):
		self.put(self.kopi, price=25000)                              # an older form, an import, the API
		self.assertEqual(sorted(self.groups_of(self.kopi)), sorted([self.ice, self.milk, self.extras]))

	def test_the_dish_form_cannot_take_another_outlets_group(self):
		other = self.outlet_named("UT Choices Bar 3")
		foreign = self.group("Foreign form", [("A", 0)], outlet=other)
		with self.assertRaisesRegex(frappe.ValidationError, "belongs to another outlet"):
			self.put(self.nasi, modifier_groups=[{"modifier_group": foreign}])

	def test_the_endpoints_ask_for_the_menu_permission(self):
		for fn in (menu_modifiers.modifier_overview, menu_modifiers.save_modifier_group,
		           menu_modifiers.delete_modifier_group):
			self.assertEqual(fn._kamra_perm, ("Menu Item", "edit_menu"))
		over = menu_modifiers.modifier_overview(PROP_A)
		mine = [g for g in over["groups"] if g["name"] == self.extras][0]
		self.assertEqual(mine["items"], [self.kopi])
		self.assertEqual([o["option_name"] for o in mine["options"]],
		                 ["Extra shot", "Caramel", "Whipped cream"])
