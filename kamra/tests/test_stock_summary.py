"""The stock summary: what a period started with, what moved, what is left."""

from __future__ import annotations

import frappe
from frappe.utils import nowdate

from kamra import inventory
from kamra.tests.audit_fixtures import PROP_A, PROP_B
from kamra.tests.test_stock_corrections import WriterCase


class SummaryCase(WriterCase):
	def summary(self, start, end, **kw):
		return inventory.stock_summary(PROP_A, start, end, **kw)["rows"]

	def row(self, ing, start, end, **kw):
		found = [r for r in self.summary(start, end, **kw) if r["ingredient"] == ing]
		self.assertEqual(len(found), 1, (ing, start, end, found))
		return found[0]

	def figures(self, r):
		return tuple(r[k] for k in ("beginning", "purchases", "used", "wastage", "adjustment", "ending"))


class TestTheFigures(SummaryCase):
	def test_the_worked_examples(self):
		cups = self.example()
		for start, end, want in (
				("2026-11-01", "2026-11-04", (0, 100, -40, 0, -5, 55)),
				("2026-11-02", "2026-11-03", (100, 0, -30, 0, -5, 65)),
				("2026-11-04", "2026-11-04", (65, 0, -10, 0, 0, 55)),
				("2026-11-05", "2026-11-05", (55, 0, 0, 0, 0, 55))):
			with self.subTest(start=start, end=end):
				self.assertEqual(self.figures(self.row(cups, start, end, outlet=self.cafe)), want)

	def test_wastage_has_its_own_column_and_a_return_counts_as_used(self):
		cups = self.ingredient("UT Cups", "pc")
		self.deliver(cups, 10, at="2026-11-01 09:00:00")
		self.waste(cups, 2, at="2026-11-01 10:00:00")
		self.move(cups, -3, at="2026-11-01 11:00:00")
		self.move(cups, 1, "Return", at="2026-11-01 12:00:00")
		self.assertEqual(
			self.figures(self.row(cups, "2026-11-01", "2026-11-01", outlet=self.cafe)),
			(0, 10, -2, -2, 0, 6))

	def test_every_ledger_reason_has_a_column(self):
		options = frappe.get_meta("Ingredient Ledger Entry").get_field("reason").options
		self.assertEqual(sorted(inventory.SUMMARY_BUCKETS), sorted(options.split("\n")))

	def test_ending_today_is_what_the_stock_screen_shows(self):
		cups = self.ingredient("UT Cups", "pc")
		self.deliver(cups, 10)
		self.waste(cups, 3)
		self.count(cups, 5, at="2026-11-01 09:00:00")
		shelf = {r["ingredient"]: r["qty_on_hand"]
		         for r in inventory.stock_list(PROP_A, self.cafe)}
		for r in self.summary("2026-11-01", nowdate(), outlet=self.cafe):
			self.assertEqual(r["ending"], shelf[r["ingredient"]], r["ingredient_name"])

	def test_a_cancelled_only_ingredient_is_left_out(self):
		cups = self.ingredient("UT Cups", "pc")
		self.deliver(cups, 10)
		inventory.cancel_stock_entry(
			PROP_A, self.rows(cups)[0].name, "never came")
		self.assertEqual(
			[r for r in self.summary(nowdate(), nowdate()) if r["ingredient"] == cups], [])


class TestFilters(SummaryCase):
	def setUp(self):
		super().setUp()
		self.cups = self.ingredient("UT Cups", "pc", category="Packaging")
		self.milk = self.ingredient("UT Milk", "ml")
		self.deliver(self.cups, 10)
		self.deliver(self.cups, 4, outlet=self.bar)
		self.deliver(self.milk, 500)
		inventory.set_par_level(PROP_A, self.bar, self.cups, 5)

	def names(self, **kw):
		return [(r["ingredient_name"], r["outlet_name"]) for r in
		        self.summary(nowdate(), nowdate(), **kw)]

	def test_all_outlets_is_one_row_per_outlet(self):
		self.assertEqual(self.names(), [
			("UT Cups", "UT Bar"), ("UT Cups", "UT Cafe"), ("UT Milk", "UT Cafe")])
		row = self.summary(nowdate(), nowdate())[1]
		self.assertEqual((row["category"], row["uom"]), ("Packaging", "pc"))

	def test_one_outlet_search_and_low_only(self):
		self.assertEqual(self.names(outlet=self.bar), [("UT Cups", "UT Bar")])
		self.assertEqual(self.names(search="mil"), [("UT Milk", "UT Cafe")])
		self.assertEqual(self.names(low_only=1), [("UT Cups", "UT Bar")])

	def test_another_propertys_outlet_gives_nothing(self):
		outlet = frappe.get_doc({
			"doctype": "POS Outlet", "property": PROP_B, "outlet_name": "UT Their",
			"outlet_type": "Restaurant"}).insert(ignore_permissions=True).name
		theirs = self.ingredient("UT Theirs", "pc", prop=PROP_B)
		inventory.receive_stock(PROP_B, outlet, [{"ingredient": theirs, "qty": 1}])
		self.assertEqual(self.names(outlet=outlet), [])

	def test_the_history_of_one_period(self):
		cups = self.ingredient("UT Lids", "pc")
		self.deliver(cups, 10, at="2026-11-01 09:00:00")
		self.waste(cups, 1, at="2026-11-02 23:59:00")
		self.waste(cups, 2, at="2026-11-03 00:00:00")
		rows = inventory.ingredient_ledger(
			PROP_A, self.cafe, cups, from_date="2026-11-02", to_date="2026-11-02")
		self.assertEqual([r.qty_change for r in rows], [-1])
