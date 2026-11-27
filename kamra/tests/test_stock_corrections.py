"""Back-dated and cancelled stock entries: the balances stay true."""

from __future__ import annotations

import frappe
from frappe.utils import add_to_date, get_datetime, now_datetime

from kamra import inventory
from kamra.tests.audit_fixtures import PROP_A, PROP_B
from kamra.tests.test_rbac import _user
from kamra.tests.test_stock_cost import AVERAGE, StockCostTestCase


class LedgerCase(StockCostTestCase):
	def move(self, ing, qty, reason="Consumed", at=None, counted=None, outlet=None):
		return inventory._apply_move(
			PROP_A, outlet or self.cafe, ing, qty, reason, posted_at=at,
			set_counted=reason == "Count", set_qty=counted)

	def rows(self, ing, outlet=None, **filters):
		return frappe.get_all(
			"Ingredient Ledger Entry",
			filters={"ingredient": ing, "outlet": outlet or self.cafe, **filters},
			fields=["*"], order_by="posted_at asc, creation asc, name asc")

	def history(self, ing, outlet=None):
		"""(change, balance after) in date order."""
		return [(r.qty_change, r.balance_after) for r in self.rows(ing, outlet)]

	def on_hand(self, ing, outlet=None):
		return frappe.db.get_value(
			"Ingredient Stock", f"{outlet or self.cafe}::{ing}", "qty_on_hand")

	def assertStock(self, ing, qty, outlet=None):
		"""The shelf figure, and the history that has to explain it."""
		self.assertEqual(self.on_hand(ing, outlet), qty)
		self.assertAlmostEqual(sum(c for c, _after in self.history(ing, outlet)), qty, 6)

	def example(self):
		"""The design's starting table."""
		cups = self.ingredient("UT Cups", "pc")
		self.move(cups, 100, "Received", at="2026-11-01 09:00:00")
		self.move(cups, -30, at="2026-11-02 12:00:00")
		self.move(cups, 0, "Count", at="2026-11-03 22:00:00", counted=65)
		self.move(cups, -10, at="2026-11-04 12:00:00")
		return cups


class TestRipple(LedgerCase):
	def test_the_worked_example_back_dated_wastage(self):
		cups = self.example()
		self.assertEqual(self.history(cups), [(100, 100), (-30, 70), (-5, 65), (-10, 55)])
		now = self.move(cups, -8, "Wastage", at="2026-11-02 18:00:00")
		self.assertEqual(
			self.history(cups), [(100, 100), (-30, 70), (-8, 62), (3, 65), (-10, 55)])
		self.assertStock(cups, 55)
		self.assertEqual(now, 55, "the move answers with the stock on hand")

	def test_a_back_dated_delivery_without_a_later_count_moves_stock(self):
		cups = self.ingredient("UT Cups", "pc")
		self.move(cups, 100, "Received", at="2026-11-01 09:00:00")
		self.move(cups, -30, at="2026-11-02 12:00:00")
		self.move(cups, 20, "Received", at="2026-11-01 12:00:00")
		self.assertEqual(self.history(cups), [(100, 100), (20, 120), (-30, 90)])
		self.assertStock(cups, 90)

	def test_a_back_dated_count_reworks_only_up_to_the_next_count(self):
		cups = self.ingredient("UT Cups", "pc")
		self.move(cups, 100, "Received", at="2026-11-01 09:00:00")
		self.move(cups, 0, "Count", at="2026-11-03 09:00:00", counted=80)
		self.move(cups, -5, at="2026-11-04 09:00:00")
		self.move(cups, 0, "Count", at="2026-11-05 09:00:00", counted=70)
		self.move(cups, -1, at="2026-11-06 09:00:00")
		self.move(cups, 0, "Count", at="2026-11-02 09:00:00", counted=50)
		self.assertEqual(self.history(cups), [
			(100, 100), (-50, 50), (30, 80), (-5, 75), (-5, 70), (-1, 69)])
		self.assertEqual([r.counted_qty for r in self.rows(cups, reason="Count")], [50, 80, 70])
		self.assertStock(cups, 69)

	def test_a_date_before_the_first_row(self):
		cups = self.ingredient("UT Cups", "pc")
		self.move(cups, 10, "Received", at="2026-11-05 09:00:00")
		self.move(cups, -3, at="2026-11-01 09:00:00")
		self.assertEqual(self.history(cups), [(-3, -3), (10, 7)])
		self.assertStock(cups, 7)

	def test_another_outlet_is_left_alone(self):
		cups = self.ingredient("UT Cups", "pc")
		self.move(cups, 10, "Received", at="2026-11-05 09:00:00", outlet=self.bar)
		self.move(cups, 4, "Received", at="2026-11-01 09:00:00")
		self.assertEqual(self.history(cups, self.bar), [(10, 10)])
		self.assertStock(cups, 4)

	def test_a_move_without_a_date_is_stamped_now(self):
		cups = self.ingredient("UT Cups", "pc")
		before = now_datetime()
		self.move(cups, 5, "Received")
		stamped = get_datetime(self.rows(cups)[0].posted_at)
		self.assertTrue(before <= stamped <= now_datetime(), stamped)

	def test_the_patch_dates_old_rows(self):
		from kamra.patches.v48.date_the_stock_ledger import execute

		cups = self.ingredient("UT Cups", "pc")
		self.move(cups, 100, "Received")
		self.move(cups, 0, "Count", counted=60)
		frappe.db.sql(
			"""update `tabIngredient Ledger Entry` set posted_at = null, counted_qty = 0
			where ingredient = %s""", cups)
		execute()
		for row in frappe.get_all(
				"Ingredient Ledger Entry", filters={"ingredient": cups},
				fields=["posted_at", "creation", "reason", "counted_qty", "balance_after"]):
			self.assertEqual(row.posted_at, row.creation)
			self.assertEqual(row.counted_qty, 60 if row.reason == "Count" else 0)


def ago(**shift):
	"""A moment in the past, as the screens send it."""
	return str(add_to_date(now_datetime(), **{k: -v for k, v in shift.items()}))[:19]


class WriterCase(LedgerCase):
	def deliver(self, ing, qty, price=None, at=None, outlet=None):
		row = {"ingredient": ing, "qty": qty}
		if price is not None:
			row["cost_per_unit"] = price
		return inventory.receive_stock(PROP_A, outlet or self.cafe, [row], posted_at=at)

	def count(self, ing, counted, at=None, outlet=None):
		return inventory.adjust_stock(
			PROP_A, outlet or self.cafe, [{"ingredient": ing, "counted_qty": counted}],
			note="counted", posted_at=at)

	def waste(self, ing, qty, at=None, outlet=None):
		return inventory.record_wastage(
			PROP_A, outlet or self.cafe, ing, qty, "spilt", posted_at=at)


class TestDatedEntries(WriterCase):
	def test_the_future_is_refused(self):
		cups = self.ingredient("UT Cups", "pc")
		later = ago(hours=-1)
		for entry in (lambda: self.deliver(cups, 1, at=later),
		              lambda: self.count(cups, 1, at=later),
		              lambda: self.waste(cups, 1, at=later)):
			with self.assertRaisesRegex(frappe.ValidationError, "future"):
				entry()
		self.assertEqual(self.rows(cups), [])

	def test_a_call_without_a_date_happens_now(self):
		cups = self.ingredient("UT Cups", "pc")
		self.deliver(cups, 5)
		self.count(cups, 4)
		self.assertEqual(self.waste(cups, 1)["qty_on_hand"], 3)
		self.assertStock(cups, 3)
		self.assertEqual(self.history(cups), [(5, 5), (-1, 4), (-1, 3)])

	def test_a_stock_take_with_no_difference_is_recorded(self):
		cups = self.ingredient("UT Cups", "pc")
		self.deliver(cups, 10)
		self.assertEqual(self.count(cups, 10)["adjusted"], [])
		row = self.rows(cups, reason="Count")[0]
		self.assertEqual((row.qty_change, row.counted_qty), (0, 10))

	def test_a_back_dated_stock_take_compares_with_that_moment(self):
		cups = self.ingredient("UT Cups", "pc")
		self.deliver(cups, 10, at=ago(days=3))
		self.waste(cups, 4, at=ago(days=1))
		found = self.count(cups, 9, at=ago(days=2))["adjusted"][0]
		self.assertEqual((found["was"], found["now"], found["variance"]), (10, 9, -1))
		self.assertStock(cups, 5)

	def test_count_and_wastage_refuse_another_propertys_ingredient(self):
		other = self.ingredient("UT Other", "pc", prop=PROP_B)
		for entry in (lambda: self.count(other, 1), lambda: self.waste(other, 1)):
			with self.assertRaisesRegex(frappe.ValidationError, "another property"):
				entry()
		self.assertFalse(frappe.db.exists("Ingredient Stock", f"{self.cafe}::{other}"))

	def test_stock_never_lands_on_another_propertys_outlet(self):
		cups = self.ingredient("UT Cups", "pc")
		theirs = frappe.get_doc({
			"doctype": "POS Outlet", "property": PROP_B, "outlet_name": "UT Their",
			"outlet_type": "Restaurant"}).insert(ignore_permissions=True).name
		for entry in (lambda: self.deliver(cups, 1, outlet=theirs),
		              lambda: self.count(cups, 1, outlet=theirs),
		              lambda: self.waste(cups, 1, outlet=theirs),
		              lambda: inventory.set_par_level(PROP_A, theirs, cups, 2)):
			with self.assertRaisesRegex(frappe.ValidationError, "another property"):
				entry()
		self.assertFalse(frappe.db.exists("Ingredient Stock", f"{theirs}::{cups}"))

	def test_a_time_with_a_zone_or_nonsense_is_refused(self):
		cups = self.ingredient("UT Cups", "pc")
		for bad in ("2026-11-02T18:00:00Z", "2026-11-02 18:00:00+07:00", "last Tuesday-ish"):
			for call in (lambda: self.deliver(cups, 1, at=bad),
			             lambda: inventory.stock_at(PROP_A, self.cafe, bad)):
				with self.subTest(bad=bad), \
						self.assertRaisesRegex(frappe.ValidationError, "Pick a date and time"):
					call()
		self.assertEqual(self.rows(cups), [])

	def test_wastage_has_a_batch(self):
		cups = self.ingredient("UT Cups", "pc")
		self.waste(cups, 1)
		self.assertTrue(self.rows(cups)[0].batch_id)

	def test_average_counts_the_goods_a_later_stock_take_already_holds(self):
		self.method(AVERAGE)
		beans = self.ingredient(cost=200)
		self.count(beans, 3000)
		self.deliver(beans, 1000, 260, at=ago(days=1))
		self.assertStock(beans, 3000)
		self.assertEqual(self.cost(beans), 220)

	def test_last_price_keeps_a_newer_dated_price(self):
		beans = self.ingredient(cost=200)
		self.deliver(beans, 10, 260, at=ago(days=1))
		self.deliver(beans, 10, 100, at=ago(days=2), outlet=self.bar)
		self.assertEqual(self.cost(beans), 260)
		self.assertEqual(self.rows(beans, self.bar)[0].cost_after, 260)
		self.deliver(beans, 10, 300, at=ago(hours=1))
		self.assertEqual(self.cost(beans), 300)

	def test_one_ingredient_twice_in_a_back_dated_delivery(self):
		beans = self.ingredient(cost=200)
		self.deliver(beans, 1, 200)
		inventory.receive_stock(PROP_A, self.cafe, [
			{"ingredient": beans, "qty": 10, "cost_per_unit": 250},
			{"ingredient": beans, "qty": 20, "cost_per_unit": 270}], posted_at=ago(days=1))
		self.assertEqual(self.history(beans), [(10, 10), (20, 30), (1, 31)])
		self.assertStock(beans, 31)

	def test_last_counted_is_the_newest_stock_take(self):
		cups = self.ingredient("UT Cups", "pc")
		self.count(cups, 5, at=ago(days=1))
		newest = self.rows(cups)[0].posted_at
		self.count(cups, 7, at=ago(days=3))
		self.assertEqual(frappe.db.get_value(
			"Ingredient Stock", f"{self.cafe}::{cups}", "last_counted_at"), newest)


class TestCancel(WriterCase):
	def entry(self, ing, reason, n=0, **filters):
		return self.rows(ing, reason=reason, **filters)[n].name

	def cancel(self, row, why="entered twice"):
		return inventory.cancel_stock_entry(PROP_A, row, why)

	def test_the_worked_example_cancels(self):
		cups = self.example()
		self.waste(cups, 8, at="2026-11-02 18:00:00")
		self.cancel(self.entry(cups, "Count"))
		self.assertEqual(
			self.history(cups), [(100, 100), (-30, 70), (-8, 62), (0, 62), (-10, 52)])
		self.assertStock(cups, 52)
		self.deliver(cups, 24, at="2026-11-04 18:00:00")
		self.assertStock(cups, 76)
		self.cancel(self.entry(cups, "Wastage"))
		self.assertEqual(self.history(cups), [
			(100, 100), (-30, 70), (0, 70), (0, 70), (-10, 60), (24, 84)])
		self.assertStock(cups, 84)

	def test_a_cancelled_line_says_what_it_was_and_who_took_it_back(self):
		cups = self.ingredient("UT Cups", "pc")
		self.waste(cups, 8)
		self.cancel(self.entry(cups, "Wastage"), "  wrong outlet  ")
		row = self.rows(cups)[0]
		self.assertEqual(
			(row.cancelled, row.qty_change, row.original_qty_change, row.cancel_reason),
			(1, 0, -8, "wrong outlet"))
		self.assertEqual(row.cancelled_by, frappe.session.user)
		self.assertTrue(row.cancelled_at)

	def test_a_whole_delivery_is_cancelled_from_any_of_its_lines(self):
		cups = self.ingredient("UT Cups", "pc")
		lids = self.ingredient("UT Lids", "pc")
		inventory.receive_stock(PROP_A, self.cafe, [
			{"ingredient": cups, "qty": 5}, {"ingredient": lids, "qty": 7}])
		self.assertEqual(self.cancel(self.entry(lids, "Received"))["cancelled"], 2)
		self.assertStock(cups, 0)
		self.assertStock(lids, 0)

	def test_cancelling_a_stock_take_moves_last_counted_back(self):
		cups = self.ingredient("UT Cups", "pc")
		self.count(cups, 5, at=ago(days=3))
		older = self.rows(cups)[0].posted_at
		self.count(cups, 7, at=ago(days=1))
		self.cancel(self.entry(cups, "Count", n=1))
		self.assertEqual(frappe.db.get_value(
			"Ingredient Stock", f"{self.cafe}::{cups}", "last_counted_at"), older)
		self.assertStock(cups, 5)

	def test_refusals(self):
		cups = self.ingredient("UT Cups", "pc")
		self.waste(cups, 1)
		wasted = self.entry(cups, "Wastage")
		with self.assertRaisesRegex(frappe.ValidationError, "reason"):
			self.cancel(wasted, "  ")
		self.cancel(wasted)
		with self.assertRaisesRegex(frappe.ValidationError, "already cancelled"):
			self.cancel(wasted)
		self.move(cups, -1)
		with self.assertRaisesRegex(frappe.ValidationError, "Only deliveries"):
			self.cancel(self.entry(cups, "Consumed"))
		theirs = self.ingredient("UT Other", "pc", prop=PROP_B)
		outlet = frappe.get_doc({
			"doctype": "POS Outlet", "property": PROP_B, "outlet_name": "UT Their Bar",
			"outlet_type": "Restaurant"}).insert(ignore_permissions=True).name
		inventory.record_wastage(PROP_B, outlet, theirs, 1, "spilt")
		row = frappe.db.get_value("Ingredient Ledger Entry", {"ingredient": theirs})
		with self.assertRaisesRegex(frappe.ValidationError, "not found"):
			self.cancel(row)

	def test_every_ledger_reason_is_listed_as_cancellable_or_not(self):
		options = frappe.get_meta("Ingredient Ledger Entry").get_field("reason").options
		listed = inventory.CANCELLABLE + inventory.NOT_CANCELLABLE
		self.assertEqual(sorted(listed), sorted(options.split("\n")))

	def test_only_hotel_admins_cancel_by_default(self):
		cups = self.ingredient("UT Cups", "pc")
		self.waste(cups, 1)
		row = self.entry(cups, "Wastage")
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user(_user("ut-fnb@example.com", "F&B Manager"))  # nosemgrep: frappe-setuser -- test switches user
		with self.assertRaises(frappe.PermissionError):
			self.cancel(row)
		frappe.set_user(_user("ut-admin@example.com", "Hotel Admin"))  # nosemgrep: frappe-setuser -- test switches user
		self.assertEqual(self.cancel(row)["cancelled"], 1)


class TestCancelledDeliveryCost(WriterCase):
	def delivery(self, ing, price, qty=1000):
		self.deliver(ing, qty, price)
		return self.rows(ing, reason="Received")[-1].name

	def cancel(self, row):
		return inventory.cancel_stock_entry(PROP_A, row, "wrong price")["cost_unchanged"]

	def average(self):
		self.method(AVERAGE)
		beans = self.ingredient(cost=200)
		self.count(beans, 2000)
		return beans

	def test_the_old_cost_comes_back(self):
		beans = self.average()
		first = self.delivery(beans, 260)
		self.assertEqual(self.cost(beans), 220)
		self.assertEqual(self.cancel(first), [])
		self.assertEqual(self.cost(beans), 200)

	def test_a_later_delivery_keeps_the_cost_until_it_goes_too(self):
		beans = self.average()
		first = self.delivery(beans, 260)
		second = self.delivery(beans, 300)
		moved = self.cost(beans)
		self.assertEqual(self.cancel(first), ["UT Beans"])
		self.assertEqual(self.cost(beans), moved)
		self.assertEqual(self.cancel(second), [])
		self.assertEqual(self.cost(beans), 200, "as if neither had been typed")

	def test_two_lines_of_one_delivery_are_undone_newest_first(self):
		beans = self.average()
		inventory.receive_stock(PROP_A, self.cafe, [
			{"ingredient": beans, "qty": 100, "cost_per_unit": 260},
			{"ingredient": beans, "qty": 100, "cost_per_unit": 300}])
		self.assertEqual(self.cancel(self.rows(beans, reason="Received")[0].name), [])
		self.assertEqual(self.cost(beans), 200)

	def test_a_typed_cost_since_is_left_alone(self):
		beans = self.average()
		first = self.delivery(beans, 260)
		frappe.db.set_value("Ingredient", beans, "cost_per_unit", 500)
		self.assertEqual(self.cancel(first), ["UT Beans"])
		self.assertEqual(self.cost(beans), 500)

	def test_a_delivery_from_before_prices_were_kept_never_moves_the_cost(self):
		beans = self.average()
		first = self.delivery(beans, 260)
		frappe.db.set_value("Ingredient Ledger Entry", first, "price_entry", "")
		self.assertEqual(self.cancel(first), ["UT Beans"])
		self.assertEqual(self.cost(beans), 220)

	def test_a_delivery_without_a_price_changed_nothing_to_put_back(self):
		beans = self.average()
		free = self.delivery(beans, None)
		frappe.db.set_value("Ingredient", beans, "cost_per_unit", 500)
		self.assertEqual(self.cancel(free), [])
		self.assertEqual(self.cost(beans), 500)

	def test_last_price_falls_back_to_the_newest_delivery_standing(self):
		beans = self.ingredient(cost=200)
		first = self.delivery(beans, 80)
		second = self.delivery(beans, 90)
		third = self.delivery(beans, 90)
		self.assertEqual(self.cancel(second), [])
		self.assertEqual(self.cost(beans), 90)
		self.assertEqual(self.cancel(third), [])
		self.assertEqual(self.cost(beans), 80)
		self.assertEqual(self.cancel(first), [])
		self.assertEqual(self.cost(beans), 200)


class TestReads(WriterCase):
	def alerts(self):
		return frappe.get_all(
			"Kamra Notification", filters={"property": PROP_A, "module": "fnb"}, pluck="subject")

	def cups_with_a_minimum(self):
		cups = self.ingredient("UT Cups", "pc")
		self.deliver(cups, 10, at=ago(days=3))
		inventory.set_par_level(PROP_A, self.cafe, cups, 5)
		return cups

	def test_history_follows_the_date_of_the_entry(self):
		cups = self.ingredient("UT Cups", "pc")
		self.deliver(cups, 1, at=ago(days=1))
		self.deliver(cups, 2, at=ago(days=3))
		rows = inventory.ingredient_ledger(PROP_A, self.cafe, cups)
		self.assertEqual([r.qty_change for r in rows], [1, 2])
		self.assertTrue(rows[0].posted_at > rows[1].posted_at)

	def test_each_line_names_everything_in_its_entry(self):
		cups = self.ingredient("UT Cups", "pc")
		lids = self.ingredient("UT Lids", "pc")
		inventory.receive_stock(PROP_A, self.cafe, [
			{"ingredient": cups, "qty": 5}, {"ingredient": lids, "qty": 7}])
		self.waste(cups, 1)
		wasted, delivered = inventory.ingredient_ledger(PROP_A, self.cafe, cups)
		self.assertEqual(delivered.batch_ingredients, ["UT Cups", "UT Lids"])
		self.assertEqual(wasted.batch_ingredients, ["UT Cups"])
		self.assertEqual((wasted.cancelled, wasted.cancel_reason), (0, None))

	def test_stock_at_a_moment(self):
		cups = self.ingredient("UT Cups", "pc")
		self.deliver(cups, 10, at=ago(days=3))
		self.waste(cups, 4, at=ago(days=1))
		for moment, held in ((ago(days=4), 0), (ago(days=2), 10), (ago(minutes=0), 6)):
			self.assertEqual(
				inventory.stock_at(PROP_A, self.cafe, moment)[cups], held, moment)

	def test_a_back_dated_entry_that_crosses_the_minimum_today_says_so(self):
		cups = self.cups_with_a_minimum()
		self.waste(cups, 6, at=ago(days=1))
		self.assertEqual(self.alerts(), ["Low stock - UT Cups: 4 pc left (minimum 5)"])

	def test_one_a_later_stock_take_absorbs_stays_quiet(self):
		cups = self.cups_with_a_minimum()
		self.count(cups, 10)
		self.waste(cups, 6, at=ago(days=1))
		self.assertEqual(self.alerts(), [])

	def test_cancelling_a_delivery_that_empties_the_shelf_says_so(self):
		cups = self.cups_with_a_minimum()
		inventory.cancel_stock_entry(
			PROP_A, self.rows(cups, reason="Received")[0].name, "never came")
		self.assertEqual(self.alerts(), ["Low stock - UT Cups: 0 pc left (minimum 5)"])


class TestMessages(WriterCase):
	MESSAGES = (
		"Pick a date and time.",
		"A stock entry cannot be dated in the future.",
		"A reason is required to cancel.",
		"Stock entry not found.",
		"This entry is already cancelled.",
		"Only deliveries, stock takes, wastage and production batches can be cancelled.",
	)

	def test_every_new_refusal_is_translated(self):
		from frappe.translate import clear_cache, get_all_translations
		clear_cache()
		for lang in ("ar", "es", "pt", "sw", "vi", "zh"):
			known = get_all_translations(lang)
			self.assertEqual([m for m in self.MESSAGES if m not in known], [], lang)
