"""Reports show sales after refunds: sales stay on the sale's day, refunds
count on the day the money went back, under the way it went back."""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.utils import add_days, nowdate

from kamra import audit_report, books, custom_reports, night_audit, pos, reports
from kamra.tests.audit_fixtures import PROP_A, TODAY
from kamra.tests.test_pos_refunds import SUPERVISOR, Refunding

PHONE = "+62 812 0000 111"


class AfterOneRefund(Refunding):
	"""The design's bill (items 60,000, levy 6,000, tax 6,600), one latte
	refunded in cash: 30,250 = items 25,000 + levy 2,500 + tax 2,750."""

	def setUp(self):
		super().setUp()
		self.order = self.paid_bill()
		frappe.db.set_value("POS Order", self.order, "customer_phone", PHONE)
		self.items(self.order, self.pick(self.order, self.latte))

	def history(self, **kw):
		return pos.orders_list(self.outlet, **kw)


class TestBillHistory(AfterOneRefund):
	def test_totals_show_sales_refunds_and_net(self):
		out = self.history()
		t = out["totals"]
		self.assertEqual((t["sales"], t["refunds"], t["net"], t["by_mode"]),
		                 (66000, 27500, 38500, {"Cash": 38500}))
		self.assertEqual((out["rows"][0]["refunded"], out["rows"][0]["paid_amount"]), (30250, 72600))

	def test_a_search_or_state_filter_hides_the_refund_figures(self):
		for filters in ({"q": "T1"}, {"state": "paid"}):
			t = self.history(**filters)["totals"]
			self.assertEqual((t["refunds"], t["net"], t["by_mode"]), (None, None, {"Cash": 66000}))

	def test_refunds_follow_the_way_money_went_back(self):
		self.assertEqual(self.history(mode="Card")["totals"]["refunds"], 0)
		self.assertEqual(self.history(mode="Cash")["totals"]["refunds"], 27500)

	def test_the_csv_has_a_row_per_refund(self):
		csv = pos.orders_export(self.outlet)["csv"]
		row = [line for line in csv.splitlines() if ",refund," in line]
		self.assertEqual(len(row), 1)
		cells = row[0].split(",")
		self.assertEqual((cells[0], cells[11], float(cells[14])), (self.order, "Cash", -27500))

	def test_the_bill_view_lists_its_refunds(self):
		frappe.db.set_value("User", SUPERVISOR, "full_name", "UT Budi")
		d = pos.order_detail(self.order)
		self.assertEqual(d["refunds"][0]["approved_by_name"], "UT Budi")
		self.assertTrue(d["refunds"][0]["refunded_by_name"])
		self.assertEqual((d["refunded_amount"], d["paid_amount"], len(d["refunds"])), (30250, 72600, 1))


class TestDashboards(AfterOneRefund):
	def test_the_fnb_dashboard(self):
		d = pos.outlet_dashboard(self.outlet)
		self.assertEqual((d["gross_sales"], d["refunds"], d["net_sales"]),
		                 (66000, {"count": 1, "amount": 27500}, 38500))
		self.assertEqual([(x["label"], x["total"]) for x in d["by_tender"]], [("Cash", 38500)])
		self.assertEqual([x["total"] for x in d["by_order_type"]], [38500])
		latte = next(x for x in d["top_items"] if x["item_name"] == "UT Latte")
		self.assertEqual((latte["qty"], latte["amount"]), (1, 25000))

	def test_a_guests_spend_is_net(self):
		got = pos._outlet_history(self.outlet, None, frappe._dict(name="UT-nobody", phone=PHONE), None)
		self.assertEqual(got["spend"], 38500)


class TestBackOffice(AfterOneRefund):
	def outlet_figures(self, day):
		return next((o for o in audit_report._outlets(PROP_A, day, day)
		             if o["outlet"] == self.outlet), None)

	def test_the_night_audit_outlet_figures_lose_items_not_levy_or_tax(self):
		o = self.outlet_figures(TODAY)
		self.assertEqual((o["food"], o["beverage"], o["total"]), (35000, 0, 35000))

	def test_a_refund_on_a_later_day_counts_that_day(self):
		later = add_days(TODAY, 1)
		frappe.db.set_value("Property", PROP_A, "business_date", later)
		self.refund(self.order, "amount", amount=7260)  # a tenth of what was paid
		self.assertEqual(self.outlet_figures(TODAY)["food"], 35000)
		self.assertEqual(self.outlet_figures(later)["food"], -6000)

	def test_an_amount_refund_splits_like_the_bill(self):
		beer = self.dish("UT Beer", 25000, is_alcohol=1)
		order = self.paid_bill("Cash", (beer, 1), (self.latte, 1))
		before = self.outlet_figures(TODAY)
		self.refund(order, "amount", amount=frappe.db.get_value("POS Order", order, "paid_amount"))
		after = self.outlet_figures(TODAY)
		self.assertEqual((before["food"] - after["food"], before["beverage"] - after["beverage"]),
		                 (25000, 25000))

	def test_the_profit_and_loss_loses_the_refund_without_tax(self):
		span = (min(str(nowdate()), TODAY), max(str(nowdate()), TODAY))
		with patch("kamra.pos_refunds.refunds_between", return_value=[]):
			without = books._revenue(PROP_A, *span)["fnb"]
		self.assertEqual(without - books._revenue(PROP_A, *span)["fnb"], 27500)

	def test_custom_reports(self):
		today = str(nowdate())
		bill = next(r for r in custom_reports._fetch_pos_orders(PROP_A, today, today)
		            if r["name"] == self.order)
		# without tax, like the total beside it
		self.assertEqual((bill["grand_total"], bill["refunded"]), (66000, 27500))
		refund = custom_reports._fetch_pos_refunds(PROP_A, today, today)[0]
		self.assertEqual(
			(refund["order"], refund["amount"], refund["tax"], refund["mode"], refund["reason"],
			 refund["approved_by"]),
			(self.order, 30250, 2750, "Cash", "Wrong order", SUPERVISOR))
		self.assertIn("pos_refunds", custom_reports.DATASETS)
		self.assertIn("pos_refunds", custom_reports.FETCHERS)

	def test_voids_and_allowances_list_it(self):
		row = next(r for r in reports.void_allowance_report(PROP_A)
		           if r["action"] == "POS refund")
		self.assertEqual((row["pos_order"], row["approver"]), (self.order, SUPERVISOR))

	def test_the_unusual_activity_check_counts_it(self):
		seen = []
		with patch.object(night_audit, "_count_spikes",
		                  side_effect=lambda kind, words, rows, bd: seen.append(rows) or []):
			night_audit._void_and_allowance_spikes(PROP_A, str(nowdate()))
		self.assertIn(self.order, [r[3] for r in seen[0]])
