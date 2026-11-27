"""Menu items with their own stock, and unsent items leaving stock at close."""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.utils import add_days

from kamra import inventory, pos
from kamra.tests.audit_fixtures import (
	PROP_A, PROP_B, TODAY, make_reservation, make_room, make_room_type)
from kamra.tests.test_rbac import _grant, _user
from kamra.tests.test_stock_cost import StockCostTestCase


class TrackCase(StockCostTestCase):
	def dish(self, name="UT Water", price=12000, recipe=(), outlet=None):
		return frappe.get_doc({
			"doctype": "Menu Item", "property": PROP_A, "outlet": outlet or self.cafe,
			"item_name": name, "price": price, "category": "Drinks",
			"recipe": [{"ingredient": i, "qty": q} for i, q in recipe],
		}).insert(ignore_permissions=True).name

	def recipe_of(self, dish):
		return [(r.ingredient, r.qty) for r in frappe.get_doc("Menu Item", dish).recipe]

	def link(self, dish):
		return frappe.db.get_value("Menu Item", dish, "stock_ingredient")


class TestTracking(TrackCase):
	def test_a_new_stock_item_is_made_for_it(self):
		water = self.dish()
		made = inventory.track_item_stock(
			water, uom="bottle", cost_per_unit=3000, buy_uom="box", buy_size=24)["ingredient"]
		ing = frappe.get_doc("Ingredient", made)
		self.assertEqual(
			(ing.ingredient_name, ing.uom, ing.cost_per_unit, ing.buy_uom, ing.buy_size,
			 ing.category, ing.property),
			("UT Water", "bottle", 3000, "box", 24, "Drinks", PROP_A))
		self.assertEqual(self.link(water), made)
		self.assertEqual(self.recipe_of(water), [(made, 1)])

	def test_the_same_bottle_can_serve_another_outlet(self):
		at_cafe, at_bar = self.dish(), self.dish(outlet=self.bar)
		made = inventory.track_item_stock(at_cafe, uom="bottle")["ingredient"]
		inventory.track_item_stock(at_bar, ingredient=made)
		self.assertEqual(self.recipe_of(at_bar), [(made, 1)])

	def test_a_one_to_one_recipe_is_adopted(self):
		bottle = self.ingredient("UT Bottle", "pc", 3000)
		water = self.dish(recipe=[(bottle, 1)])
		inventory.track_item_stock(water, ingredient=bottle)
		self.assertEqual(self.link(water), bottle)

	def test_a_dish_with_a_real_recipe_is_refused(self):
		beans = self.ingredient()
		coffee = self.dish("UT Coffee", recipe=[(beans, 18)])
		with self.assertRaisesRegex(frappe.ValidationError, "has a recipe"):
			inventory.track_item_stock(coffee, uom="pc")
		with self.assertRaisesRegex(frappe.ValidationError, "has a recipe"):
			inventory.track_item_stock(coffee, ingredient=beans)

	def test_a_second_stock_item_of_the_same_name_is_refused(self):
		self.ingredient("UT Water", "pc")
		with self.assertRaisesRegex(frappe.ValidationError, "already exists"):
			inventory.track_item_stock(self.dish(), uom="bottle")

	def test_tracking_twice_is_refused(self):
		water = self.dish()
		inventory.track_item_stock(water, uom="bottle")
		with self.assertRaisesRegex(frappe.ValidationError, "already tracks"):
			inventory.track_item_stock(water, uom="bottle")

	def test_stop_tracking_removes_the_recipe_and_keeps_the_stock_item(self):
		water = self.dish()
		made = inventory.track_item_stock(water, uom="bottle")["ingredient"]
		inventory.receive_stock(PROP_A, self.cafe, [{"ingredient": made, "qty": 5}])
		inventory.untrack_item_stock(water)
		self.assertIsNone(self.link(water))
		self.assertEqual(self.recipe_of(water), [])
		self.assertTrue(frappe.db.exists("Ingredient", made))

	def test_the_recipe_of_a_tracked_item_cannot_be_changed(self):
		water = self.dish()
		inventory.track_item_stock(water, uom="bottle")
		beans = self.ingredient()
		with self.assertRaisesRegex(frappe.ValidationError, "tracks its own stock"):
			inventory.save_recipe(water, [{"ingredient": beans, "qty": 1}])
		doc = frappe.get_doc("Menu Item", water)
		doc.recipe[0].qty = 2
		with self.assertRaisesRegex(frappe.ValidationError, "tracks its own stock"):
			doc.save()

	def test_another_propertys_stock_item_is_refused(self):
		theirs = self.ingredient("UT Theirs", "pc", prop=PROP_B)
		with self.assertRaisesRegex(frappe.ValidationError, "another property"):
			inventory.track_item_stock(self.dish(), ingredient=theirs)

	def test_the_screens_see_what_is_tracked(self):
		water = self.dish()
		made = inventory.track_item_stock(water, uom="bottle")["ingredient"]
		inventory.receive_stock(PROP_A, self.cafe, [{"ingredient": made, "qty": 48}])
		seen = inventory.menu_recipe(water)
		self.assertEqual(
			(seen["stock_ingredient"], seen["stock_name"], seen["stock_uom"], seen["stock_on_hand"]),
			(made, "UT Water", "bottle", 48))
		row = next(d for d in inventory.recipe_overview(PROP_A) if d["name"] == water)
		self.assertTrue(row["tracked"])

	def test_it_needs_menu_and_stock_rights(self):
		water = self.dish()
		bottle = self.ingredient("UT Bottle", "pc")
		role = "UT Menu Editor"
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)
		self.addCleanup(frappe.clear_cache, doctype="Menu Item")
		_grant("Menu Item", "edit_menu", role)
		_grant("Menu Item", "write", role)
		editor = _user("ut-menu-editor@example.com", role)
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user(editor)  # nosemgrep: frappe-setuser -- test switches user
		with self.assertRaises(frappe.PermissionError):
			inventory.track_item_stock(water, ingredient=bottle)
		doc = frappe.get_doc("Menu Item", water)
		doc.stock_ingredient = bottle
		doc.set("recipe", [{"ingredient": bottle, "qty": 1}])
		with self.assertRaises(frappe.PermissionError):
			doc.save()


class AtTheTill(TrackCase):
	"""Bills for a tracked bottle: how many leave the shelf, and when."""

	def setUp(self):
		super().setUp()
		self.water = self.dish()
		self.bottle = inventory.track_item_stock(self.water, uom="bottle")["ingredient"]
		inventory.receive_stock(PROP_A, self.cafe, [{"ingredient": self.bottle, "qty": 10}])

	def left(self, ing=None):
		return frappe.db.get_value(
			"Ingredient Stock", f"{self.cafe}::{ing or self.bottle}", "qty_on_hand")

	def hold(self, *items, **kw):
		return pos.create_order(
			self.cafe, [{"menu_item": m, "qty": q} for m, q in items or ((self.water, 1),)],
			table_no="T1", **kw)["order"]

	def pay(self, order):
		return pos.pay_order(order, "Cash")

	def line(self, order, menu_item=None):
		return next(i for i in frappe.get_doc("POS Order", order).items
		            if i.menu_item == (menu_item or self.water))

	def notes(self, order):
		return frappe.get_all("Ingredient Ledger Entry",
		                      filters={"reference_name": order}, pluck="note")


class TestWhenStockLeaves(AtTheTill):
	def test_held_then_paid(self):
		order = self.hold((self.water, 2))
		self.assertEqual(self.left(), 10)
		self.pay(order)
		self.assertEqual(self.left(), 8)
		line = self.line(order)
		self.assertEqual((line.kot_status, line.stock_posted, line.stock_item),
		                 ("New", 1, self.bottle))
		self.assertEqual(self.notes(order), ["Closed without a kitchen ticket"])

	def test_sent_then_paid_takes_once(self):
		order = self.hold()
		pos.fire_kot(order)
		self.assertEqual(self.left(), 9)
		self.pay(order)
		self.assertEqual(self.left(), 9)
		self.assertEqual(self.line(order).stock_item, self.bottle)

	def test_sent_then_voided_stays_used(self):
		order = self.hold((self.water, 1), (self.dish("UT Tea", 8000), 1))
		pos.fire_kot(order)
		pos.void_item(order, self.line(order).name, "changed mind")
		self.pay(order)
		self.assertEqual(self.left(), 9)

	def test_voided_before_sending_takes_nothing(self):
		order = self.hold((self.water, 1), (self.dish("UT Tea", 8000), 1))
		pos.void_item(order, self.line(order).name, "wrong item")
		self.pay(order)
		self.assertEqual(self.left(), 10)

	def test_only_a_line_added_after_the_ticket_leaves_at_payment(self):
		order = self.hold()
		pos.fire_kot(order)
		pos.add_items(order, [{"menu_item": self.water, "qty": 3}])
		self.pay(order)
		self.assertEqual(self.left(), 6)

	def test_split_after_sending_takes_nothing_twice(self):
		order = self.hold((self.water, 1), (self.water, 2))
		pos.fire_kot(order)
		first = frappe.get_doc("POS Order", order).items[0].name
		other = pos.split_order(order, [first])["new_order"]
		self.assertEqual(self.line(other).stock_item, self.bottle)
		self.pay(order)
		self.pay(other)
		self.assertEqual(self.left(), 7)

	def test_cancelled_before_sending_takes_nothing(self):
		order = self.hold()
		pos.cancel_order(order, "left")
		self.assertEqual(self.left(), 10)

	def test_a_comped_bill_never_sent_takes_stock(self):
		order = self.hold()
		pos.mark_nc(order, "Manager")
		pos.deliver_order(order)
		self.assertEqual(self.left(), 9)

	def test_charged_to_a_room_and_moved(self):
		kind = make_room_type(PROP_A)
		rooms = [make_room(PROP_A, kind, n) for n in ("ST1", "ST2")]
		for room in rooms:
			make_reservation(PROP_A, kind, add_days(TODAY, -1), add_days(TODAY, 1),
			                 status="Checked In", room=room)
		order = self.hold(room=rooms[0])
		pos.deliver_order(order)
		self.assertEqual(self.left(), 9)
		pos.move_room_bill(order, rooms[1], "wrong room")
		self.assertEqual(self.left(), 9)

	def test_closing_again_takes_nothing_more(self):
		order = self.hold()
		self.pay(order)
		pos.deliver_order(order)
		self.assertEqual(self.left(), 9)

	def test_a_rest_save_that_closes_the_bill_takes_it(self):
		order = self.hold()
		doc = frappe.get_doc("POS Order", order)
		doc.update({"status": "Delivered", "nc": 1, "nc_authorized_by": "Manager"})
		doc.save()
		self.assertEqual(self.left(), 9)

	def test_a_recipe_dish_never_sent_leaves_stock_too(self):
		beans = self.ingredient()
		inventory.receive_stock(PROP_A, self.cafe, [{"ingredient": beans, "qty": 100}])
		coffee = self.dish("UT Coffee", 20000, recipe=[(beans, 18)])
		self.pay(self.hold((coffee, 2)))
		self.assertEqual(self.left(beans), 64)
		self.assertIsNone(self.line(
			frappe.get_all("POS Order", pluck="name", order_by="creation desc", limit=1)[0],
			coffee).stock_item)

	def test_a_stock_fault_never_blocks_the_payment(self):
		order = self.hold()
		with patch("kamra.inventory.consume_for_lines", side_effect=ValueError("broken")):
			self.assertTrue(self.pay(order)["paid"])
		self.assertEqual(self.left(), 10)
		self.assertEqual(self.line(order).stock_posted, 0)
		self.assertTrue(frappe.db.exists(
			"Error Log", {"method": f"Stock not taken at close: {order}"}))

	def test_a_database_clash_is_not_swallowed(self):
		order = self.hold()
		with patch("kamra.inventory.consume_for_lines",
		           side_effect=frappe.QueryDeadlockError("1020")), \
				self.assertRaises(frappe.QueryDeadlockError):
			self.pay(order)

	def test_the_till_is_told_what_is_left(self):
		tea = self.dish("UT Tea", 8000)
		empty = self.dish("UT Soda", 9000)
		inventory.track_item_stock(empty, uom="can")
		menu = {i["name"]: i for c in pos.pos_menu(self.cafe)["categories"] for i in c["items"]}
		self.assertEqual(menu[self.water]["stock_left"], 10)
		self.assertEqual(menu[empty]["stock_left"], 0)
		self.assertNotIn("stock_left", menu[tea])


class TestMessages(TrackCase):
	MESSAGES = (
		"{0} tracks its own stock: its recipe is that one item. Stop tracking to change it.",
		"{0} has a recipe. Delete the recipe first.",
		"{0} already tracks its own stock.",
		"An ingredient called {0} already exists. Pick it instead.",
		"Tracking stock also needs the right to manage stock.",
	)

	def test_every_new_refusal_is_translated(self):
		from frappe.translate import clear_cache, get_all_translations
		clear_cache()
		for lang in ("ar", "es", "pt", "sw", "vi", "zh"):
			known = get_all_translations(lang)
			self.assertEqual([m for m in self.MESSAGES if m not in known], [], lang)
