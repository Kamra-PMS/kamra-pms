"""The rate explained: BAR, season, demand, rate plan, voucher."""

from __future__ import annotations

from decimal import Decimal

import frappe
from frappe.utils import add_days, getdate

from kamra import pricing, rates
from kamra.tests.audit_fixtures import PROP_A, TODAY, AuditTestCase, make_property, make_room_type


class RatesTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY)
		make_property(PROP_A, business_date=TODAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.day = str(getdate(TODAY))
		self.next = str(add_days(self.day, 1))

	def season(self, **kw):
		return frappe.get_doc(dict({
			"doctype": "Season", "property": PROP_A, "season_name": "UT Peak", "room_type": self.rt,
			"start_date": self.day, "end_date": self.day, "adjustment_type": "Percent",
			"adjustment_value": 20, "priority": 10}, **kw)).insert(ignore_permissions=True)

	def test_bar_alone_is_the_base_price(self):
		n = rates.explain_night(PROP_A, frappe.get_doc("Room Type", self.rt), self.day)
		self.assertEqual((n["bar"], n["rate"]), (1000.0, 1000.0))
		self.assertIsNone(n["season"])
		self.assertIsNone(n["demand"])

	def test_season_is_named_and_moves_the_rate(self):
		self.season()
		n = rates.explain_night(PROP_A, frappe.get_doc("Room Type", self.rt), self.day)
		self.assertEqual(n["bar"], 1000.0)
		self.assertEqual(n["rate"], 1200.0)
		self.assertEqual(n["season"]["label"], "UT Peak")
		self.assertEqual(n["season"]["change"], "+20%")

	def test_what_is_explained_is_what_the_quote_charges(self):
		self.season()
		n = rates.explain_night(PROP_A, frappe.get_doc("Room Type", self.rt), self.day)
		q = pricing.quote(PROP_A, self.rt, self.day, self.next, 2, 0)
		self.assertAlmostEqual(q["nightly"][0]["rate"], n["rate"], places=2)

	def test_season_refactor_keeps_the_price(self):
		self.season(adjustment_type="Absolute", adjustment_value=1500)
		self.assertEqual(pricing.season_adjust(PROP_A, self.day, Decimal(1000), self.rt), Decimal(1500))
		self.assertEqual(pricing.season_adjust(PROP_A, self.next, Decimal(1000), self.rt), Decimal(1000))

	def test_rate_calendar_covers_every_room_type_and_date(self):
		self.season()
		cal = rates.rate_calendar(PROP_A, self.day, days=3)
		row = [r for r in cal["room_types"] if r["room_type"] == self.rt][0]
		self.assertEqual(len(row["nights"]), 3)
		self.assertEqual([n["rate"] for n in row["nights"]], [1200.0, 1000.0, 1000.0])

	def test_plans_and_voucher_are_real_quotes(self):
		frappe.get_doc({"doctype": "Rate Plan", "property": PROP_A, "rate_plan_name": "UT Corp",
		                "code": "UTC", "modifier_type": "Percent", "modifier_value": -10}
		               ).insert(ignore_permissions=True)
		frappe.get_doc({"doctype": "Discount Voucher", "property": PROP_A, "voucher_code": "UT10",
		                "discount_type": "Percent", "value": 10}).insert(ignore_permissions=True)
		out = rates.rate_options(PROP_A, self.rt, self.day, self.next, voucher_code="ut10")
		plan = out["plans"][0]
		self.assertEqual(plan["room_total"], 900.0)
		self.assertEqual(plan["vs_plain"], -100.0)
		self.assertTrue(out["voucher"]["valid"])
		self.assertGreater(out["voucher"]["discount"], 0)

	def test_a_bad_voucher_says_why(self):
		out = rates.rate_options(PROP_A, self.rt, self.day, self.next, voucher_code="NOPE")
		self.assertFalse(out["voucher"]["valid"])
		self.assertIn("does not exist", out["voucher"]["reason"])
