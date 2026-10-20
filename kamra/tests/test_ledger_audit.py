"""Ledger audit reports: the four-ledger trial balance and the daily journals.

kamra.ledger.ledger_balances, journal_by_transaction_code,
financial_activity and city_ledger_aging, fed by the real posting paths
(add_folio_charge, add_folio_payment, void_folio_charge,
refund_folio_payment, transfer_to_city_ledger, city_ledger_settle).

The invariant checked throughout: for every folio, what the Guest and
Deposit ledgers say the guest owes equals the folio's own balance, and the
trial balance is level (debits == credits) whenever nothing is owed.
"""

from __future__ import annotations

from unittest.mock import patch

import frappe

from kamra import api, ledger
from kamra import folio as folio_mod
from kamra.tests.audit_fixtures import (
	PROP_A,
	PROP_B,
	TODAY,
	YESTERDAY,
	AuditTestCase,
	d,
	ensure_user,
	guest_folio,
	make_property,
	make_reservation,
	make_room,
	make_room_type,
)

COMPANY = "UT Audit Corp"


class LedgerAuditTestCase(AuditTestCase):
	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY)
		make_property(PROP_B, business_date=TODAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")
		self.room2 = make_room(PROP_A, self.rt, "102")
		self.res = make_reservation(PROP_A, self.rt, d(-1), d(2),
		                            status="Checked In", room=self.room)
		self.folio = guest_folio(self.res.name)
		if frappe.db.exists("Corporate Account", COMPANY):
			frappe.db.set_value("Corporate Account", COMPANY, "credit_allowed", 1)
		else:
			frappe.get_doc({"doctype": "Corporate Account",
			                "company_name": COMPANY,
			                "credit_allowed": 1}).insert(ignore_permissions=True)

	# helpers -------------------------------------------------------------

	def charge(self, amount, charge_type="Laundry", gst=18, folio=None):
		doc = api.add_folio_charge(folio or self.folio, charge_type,
		                           f"UT {charge_type}", amount, gst_rate=gst)
		return doc["charges"][-1]["name"]

	def pay(self, amount, kind="Payment", folio=None):
		api.add_folio_payment(folio or self.folio, "Cash", amount, kind=kind)

	def balances(self, prop=PROP_A, date=None):
		out = ledger.ledger_balances(prop, date)
		return out, {r["ledger"]: r for r in out["ledgers"]}

	def folio_ledger_net(self, folio=None):
		"""What the Guest + Deposit ledgers say this folio owes."""
		return float(frappe.db.sql(
			"""SELECT COALESCE(SUM(debit - credit), 0) FROM `tabFolio Ledger Entry`
			   WHERE folio = %s AND ledger IN ('Guest', 'Deposit')""",
			folio or self.folio)[0][0])

	def assert_ledger_matches_folio(self, folio=None):
		bal = float(frappe.db.get_value("Folio", folio or self.folio, "balance"))
		self.assertAlmostEqual(self.folio_ledger_net(folio), bal, places=2)

	def set_bd(self, value, prop=PROP_A):
		frappe.db.set_value("Property", prop, "business_date", value)

	# empty data ----------------------------------------------------------

	def test_empty_property_trial_balance_is_level_and_zero(self):
		out, _ = self.balances()
		self.assertEqual(str(out["business_date"]), TODAY)
		self.assertEqual([r["ledger"] for r in out["ledgers"]],
		                 ["Guest", "Deposit", "AR", "Package"])
		for row in out["ledgers"]:
			self.assertEqual((row["debit"], row["credit"], row["balance"]),
			                 (0.0, 0.0, 0.0))
		self.assertEqual((out["total_debit"], out["total_credit"]), (0, 0))
		self.assertTrue(out["in_balance"])

	def test_empty_journals(self):
		self.assertEqual(ledger.journal_by_transaction_code(PROP_A)["rows"], [])
		self.assertEqual(ledger.financial_activity(PROP_A)["entries"], [])
		self.assertEqual(ledger.city_ledger_aging(PROP_A)["accounts"], [])

	# postings and the invariant -------------------------------------------

	def test_charge_debits_the_guest_ledger(self):
		self.charge(500)  # 500 + 18% = 590
		out, by = self.balances()
		self.assertAlmostEqual(by["Guest"]["debit"], 590, places=2)
		self.assertAlmostEqual(by["Guest"]["balance"], 590, places=2)
		# the guest owes 590: debits exceed credits, which is not an error -
		# the ledgers agree with the folio, so the trial balance is in balance
		self.assertGreater(out["total_debit"], out["total_credit"])
		self.assertTrue(out["in_balance"])
		self.assert_ledger_matches_folio()

	def test_charge_then_full_payment_is_level(self):
		self.charge(500)
		self.pay(590)
		out, by = self.balances()
		self.assertTrue(out["in_balance"])
		self.assertAlmostEqual(out["total_debit"], out["total_credit"], places=2)
		self.assertAlmostEqual(by["Guest"]["balance"], 0, places=2)
		self.assert_ledger_matches_folio()

	def test_void_reverses_the_charge(self):
		row = self.charge(500)
		api.void_folio_charge(self.folio, row, reason="UT posted in error")
		out, by = self.balances()
		self.assertTrue(out["in_balance"])
		self.assertAlmostEqual(by["Guest"]["debit"], 590, places=2)
		self.assertAlmostEqual(by["Guest"]["credit"], 590, places=2)
		self.assert_ledger_matches_folio()
		# a second reversal of the same line is refused
		self.assertIsNone(ledger.reverse_ledger_for_charge(
			PROP_A, self.folio, row, "again"))

	def test_refund_of_an_over_collected_advance(self):
		self.charge(500)
		self.pay(1000, kind="Advance")
		api.refund_folio_payment(self.folio, 410, "Cash", reason="UT over-collected")
		out, by = self.balances()
		# the stay is in house, so the advance pays it: it leaves the
		# Deposit ledger and credits the Guest ledger straight away
		self.assertAlmostEqual(by["Deposit"]["credit"], 1000, places=2)
		self.assertAlmostEqual(by["Deposit"]["debit"], 1000, places=2)
		self.assertAlmostEqual(by["Guest"]["debit"], 590 + 410, places=2)
		self.assertAlmostEqual(by["Guest"]["credit"], 1000, places=2)
		self.assertTrue(out["in_balance"])
		self.assert_ledger_matches_folio()

	def test_city_ledger_transfer_moves_the_debt_to_ar(self):
		self.charge(500)
		self.pay(90)
		moved = ledger.transfer_to_city_ledger(self.folio, COMPANY)
		self.assertAlmostEqual(moved["amount"], 500, places=2)
		out, by = self.balances()
		self.assertAlmostEqual(by["Guest"]["balance"], 0, places=2)
		self.assertAlmostEqual(by["AR"]["balance"], 500, places=2)
		self.assertAlmostEqual(out["total_debit"] - out["total_credit"], 500,
		                       places=2)
		self.assertAlmostEqual(float(frappe.db.get_value(
			"City Ledger Account", moved["account"], "balance")), 500, places=2)
		self.assert_ledger_matches_folio()

	def test_full_sequence_keeps_every_folio_in_step(self):
		keep = self.charge(1000)
		wrong = self.charge(200)
		api.void_folio_charge(self.folio, wrong, reason="UT wrong outlet")
		self.pay(500, kind="Advance")
		self.pay(300)
		api.refund_folio_payment(self.folio, 100, "Cash", reason="UT goodwill")
		self.assert_ledger_matches_folio()
		ledger.transfer_to_city_ledger(self.folio, COMPANY)
		self.assert_ledger_matches_folio()
		self.assertAlmostEqual(
			float(frappe.db.get_value("Folio", self.folio, "balance")), 0,
			places=2)
		self.assertTrue(keep)

	# BUG: city_ledger_settle books the company's payment only on the City
	# Ledger Account / City Ledger Entry. Nothing credits the AR ledger in
	# Folio Ledger Entry, so once the company has paid, ledger_balances
	# still shows the receivable and the trial balance never levels; the
	# AR ledger and the city ledger disagree forever.
	def test_settled_city_ledger_clears_the_ar_ledger(self):
		self.charge(500)
		moved = ledger.transfer_to_city_ledger(self.folio, COMPANY)
		ledger.city_ledger_settle(moved["account"], moved["amount"])
		out, by = self.balances()
		self.assertAlmostEqual(by["AR"]["balance"], float(frappe.db.get_value(
			"City Ledger Account", moved["account"], "balance")), places=2)
		self.assertTrue(out["in_balance"])

	# BUG: the night audit's room nights (folio.post_room_night) - and the
	# no-show fee, cleaning fee and add-ons - are appended straight to the
	# folio and never written to Folio Ledger Entry. The four-ledger trial
	# balance therefore omits all room revenue: after the audit and the
	# guest paying the bill, the Guest ledger shows a credit balance while
	# the folio says the guest owes nothing.
	def test_night_audit_room_nights_reach_the_guest_ledger(self):
		self.set_bd(YESTERDAY)
		folio_mod.run_night_audit(PROP_A)
		self.assertTrue(frappe.get_all("Folio Charge", filters={
			"parent": self.folio, "charge_type": "Room"}))
		self.assert_ledger_matches_folio()

	def test_ledger_write_failure_is_logged_not_raised(self):
		with patch("kamra.ledger.record_charge_ledger",
		           side_effect=RuntimeError("ledger down")), \
		     patch.object(frappe, "log_error") as log:
			self.charge(500)
		self.assertTrue(frappe.get_all("Folio Charge", filters={
			"parent": self.folio, "charge_type": "Laundry"}))
		log.assert_called_once()
		self.assertEqual(log.call_args.kwargs.get("title"),
		                 "ledger charge write failed")
		self.assertEqual(self.balances()[1]["Guest"]["debit"], 0.0)

	# per business date -----------------------------------------------------

	def test_entries_carry_the_business_date_not_the_calendar(self):
		self.set_bd(d(-3))
		self.charge(100)
		row = frappe.get_all("Folio Ledger Entry", filters={"folio": self.folio},
		                     pluck="business_date")
		self.assertEqual([str(x) for x in row], [d(-3)])

	def test_trial_balance_as_of_a_date_and_daily_journal(self):
		self.set_bd(d(-2))
		self.charge(100, gst=0)
		self.set_bd(d(-1))
		self.charge(200, gst=0)
		self.pay(50)
		_, early = self.balances(date=d(-2))
		self.assertAlmostEqual(early["Guest"]["debit"], 100, places=2)
		_, late = self.balances(date=d(-1))
		self.assertAlmostEqual(late["Guest"]["debit"], 300, places=2)
		self.assertAlmostEqual(late["Guest"]["credit"], 50, places=2)
		# the journal is the one day only, grouped by transaction code
		rows = {r["transaction_code"]: r for r in
		        ledger.journal_by_transaction_code(PROP_A, d(-1))["rows"]}
		self.assertEqual(set(rows), {"3000", "9001"})
		self.assertAlmostEqual(float(rows["3000"]["debit"]), 200, places=2)
		self.assertEqual(rows["3000"]["entries"], 1)
		self.assertEqual(rows["3000"]["description"], "Laundry")
		self.assertAlmostEqual(float(rows["9001"]["credit"]), 50, places=2)
		# default date is the property's business date
		self.assertEqual(ledger.journal_by_transaction_code(PROP_A)["business_date"],
		                 d(-1))

	def test_financial_activity_lists_the_days_postings_by_user(self):
		self.charge(100)
		self.pay(118)
		entries = ledger.financial_activity(PROP_A)["entries"]
		self.assertEqual(len(entries), 2)
		self.assertEqual({e.posted_by for e in entries}, {"Administrator"})
		self.assertEqual(ledger.financial_activity(
			PROP_A, user="nobody@test.local")["entries"], [])
		self.assertEqual(ledger.financial_activity(PROP_A, d(-5))["entries"], [])

	def test_properties_do_not_share_a_ledger(self):
		self.charge(500)
		out, _ = self.balances(PROP_B)
		self.assertEqual(out["total_debit"], 0)
		self.assertTrue(out["in_balance"])

	# city ledger ------------------------------------------------------------

	def test_city_ledger_aging_buckets_and_fifo_payments(self):
		self.charge(500, gst=0)
		moved = ledger.transfer_to_city_ledger(self.folio, COMPANY)
		# 45 days later the invoice sits in the 31-60 bucket
		with patch("kamra.ledger.nowdate", return_value=d(45)):
			acc = ledger.city_ledger_aging(PROP_A)["accounts"]
		self.assertEqual(len(acc), 1)
		self.assertEqual(acc[0]["company"], COMPANY)
		self.assertAlmostEqual(acc[0]["b30"], 500, places=2)
		self.assertEqual(acc[0]["current"], 0)
		# a part payment reduces the oldest invoice first
		ledger.city_ledger_settle(moved["account"], 200)
		with patch("kamra.ledger.nowdate", return_value=d(130)):
			acc = ledger.city_ledger_aging(PROP_A)["accounts"][0]
		self.assertAlmostEqual(acc["b90p"], 300, places=2)
		self.assertAlmostEqual(float(acc["balance"]), 300, places=2)

	def test_city_ledger_aging_current_bucket(self):
		self.charge(500, gst=0)
		ledger.transfer_to_city_ledger(self.folio, COMPANY)
		acc = ledger.city_ledger_aging(PROP_A)["accounts"][0]
		self.assertAlmostEqual(acc["current"], 500, places=2)
		for b in ("b30", "b60", "b90", "b90p"):
			self.assertEqual(acc[b], 0)

	def test_city_ledger_transfer_refusals(self):
		with self.assertRaises(frappe.ValidationError):  # nothing owed
			ledger.transfer_to_city_ledger(self.folio, COMPANY)
		self.charge(100)
		with self.assertRaises(frappe.ValidationError):  # no company
			ledger.transfer_to_city_ledger(self.folio)
		frappe.db.set_value("Corporate Account", COMPANY, "credit_allowed", 0)
		with self.assertRaises(frappe.ValidationError):  # no credit line
			ledger.transfer_to_city_ledger(self.folio, COMPANY)
		self.assertEqual(self.balances()[1]["AR"]["debit"], 0.0)

	def test_city_ledger_settle_refuses_non_positive(self):
		self.charge(100)
		moved = ledger.transfer_to_city_ledger(self.folio, COMPANY)
		for bad in (0, -5):
			with self.assertRaises(frappe.ValidationError):
				ledger.city_ledger_settle(moved["account"], bad)

	# access ----------------------------------------------------------------

	def test_report_role_gates(self):
		ensure_user("ut.ledger.hk@test.local", ["Housekeeping"])
		ensure_user("ut.ledger.desk@test.local", ["Front Desk"])
		frappe.set_user("ut.ledger.hk@test.local")  # nosemgrep: frappe-setuser -- persona
		for fn in (ledger.ledger_balances, ledger.journal_by_transaction_code,
		           ledger.financial_activity, ledger.city_ledger_aging):
			with self.assertRaises(frappe.PermissionError, msg=fn.__name__):
				fn(PROP_A)
		frappe.set_user("ut.ledger.desk@test.local")  # nosemgrep: frappe-setuser -- persona
		self.assertTrue(ledger.ledger_balances(PROP_A)["in_balance"])
		# financial activity (who posted what) is Finance-only
		with self.assertRaises(frappe.PermissionError):
			ledger.financial_activity(PROP_A)
