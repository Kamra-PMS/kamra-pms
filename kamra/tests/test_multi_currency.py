"""Billing in more than one currency (#411).

The books stay in the hotel's currency. A guest may pay in foreign cash or
by a foreign bank transfer: the server converts at the hotel's own buy rate
for the business date, posts the home amount to the ledger and keeps the
foreign amount and rate on the payment row. A folio can be SHOWN in another
currency; the tax invoice never changes.
"""

from __future__ import annotations

import frappe

from kamra import api, cashier, ledger
from kamra.tests.audit_fixtures import (
	PROP_A,
	TODAY,
	YESTERDAY,
	AuditTestCase,
	d,
	guest_folio,
	make_property,
	make_reservation,
	make_room,
	make_room_type,
)


class MultiCurrencyTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY, currency="INR")
		frappe.db.delete("Exchange Rate", {"property": PROP_A})
		rt = make_room_type(PROP_A, "STD", base_price=1000)
		res = make_reservation(PROP_A, rt, d(-1), d(1), status="Checked In",
		                       room=make_room(PROP_A, rt, "101"))
		self.folio = guest_folio(res.name)
		self.sess = cashier.open_session(PROP_A, 500)["name"]

	def rate(self, buy=83.105, sell=84.0, currency="USD"):
		return ledger.upsert_exchange_rate(PROP_A, currency, buy, sell)

	def test_rounding_rules(self):
		# half up to the cent on what is posted (float round() gives 2.34)
		self.assertEqual(ledger.fx_to_home(1, 2.345), 2.35)
		# the shown foreign figure rounds UP so paying it settles the bill
		self.assertEqual(ledger.home_to_fx(1000, 83.10), 12.04)
		self.assertGreaterEqual(ledger.fx_to_home(12.04, 83.10), 1000)

	def test_rate_entry_is_checked(self):
		for cur, buy in (("INR", 1), ("US", 83), ("USD", 0)):
			with self.assertRaises(frappe.ValidationError):
				ledger.upsert_exchange_rate(PROP_A, cur, buy, 84)
		row = self.rate(currency="usd")
		self.assertEqual((row["currency"], str(row["rate_date"])), ("USD", TODAY))
		self.rate(buy=83.2)  # same day: updated, not a second row
		self.assertEqual(frappe.db.count("Exchange Rate", {"property": PROP_A}), 1)

	def test_foreign_cash_posts_home_amount_and_keeps_snapshot(self):
		self.rate()
		before = frappe.get_doc("Folio", self.folio).balance
		api.add_folio_payment(self.folio, "Cash", 100, currency="usd")
		doc = frappe.get_doc("Folio", self.folio)
		pay = doc.payments[-1]
		self.assertEqual((pay.currency, pay.fx_amount, pay.exchange_rate, pay.amount),
		                 ("USD", 100, 83.105, 8310.50))
		self.assertAlmostEqual(doc.balance, before - 8310.50, places=2)
		# the ledger leg is the home amount, exactly as for any payment
		leg = frappe.get_all("Folio Ledger Entry",
		                     {"source_doctype": "Folio Payment", "source_name": pay.name},
		                     ["ledger", "credit", "debit"])
		self.assertEqual([(r.ledger, r.credit, r.debit) for r in leg],
		                 [("Guest", 8310.50, 0)])
		# foreign notes do not inflate the home-cash drawer count
		txn = frappe.get_all("Cashier Transaction", {"session": self.sess, "folio": self.folio},
		                     ["mode", "amount", "notes"])
		self.assertEqual(txn[0].mode, "Other")
		self.assertIn("USD 100.00 @ 83.105", txn[0].notes)
		self.assertEqual(cashier._recompute_session_totals(self.sess)["expected_cash"], 500)
		# a later rate change never rewrites history
		self.rate(buy=90)
		self.assertEqual(frappe.db.get_value("Folio Payment", pay.name, "amount"), 8310.50)

	def test_bank_transfer_keeps_its_mode(self):
		self.rate()
		api.add_folio_payment(self.folio, "Bank Transfer", 10, currency="USD")
		self.assertEqual(frappe.db.get_value(
			"Cashier Transaction", {"session": self.sess, "folio": self.folio}, "mode"),
			"Bank Transfer")

	def test_refused_without_todays_rate_or_on_card_or_deposit(self):
		frappe.get_doc({"doctype": "Exchange Rate", "property": PROP_A,
		                "currency": "USD", "rate_date": YESTERDAY,
		                "buy_rate": 80, "sell_rate": 81}).insert()
		with self.assertRaisesRegex(frappe.ValidationError, "No USD rate"):
			api.add_folio_payment(self.folio, "Cash", 100, currency="USD")
		self.rate()
		with self.assertRaises(frappe.ValidationError):
			api.add_folio_payment(self.folio, "Card", 100, currency="USD")
		with self.assertRaises(frappe.ValidationError):
			api.add_folio_payment(self.folio, "Cash", 100, currency="USD",
			                      kind="Security Deposit")
		# a foreign amount that rounds to nothing is not a payment
		with self.assertRaises(frappe.ValidationError):
			api.add_folio_payment(self.folio, "Cash", 0.004, currency="USD")
		self.assertFalse(frappe.db.exists("Folio Payment", {"parent": self.folio,
		                                                   "currency": "USD"}))

	def test_home_currency_payment_is_unchanged(self):
		api.add_folio_payment(self.folio, "Cash", 250, currency="INR")
		api.add_folio_payment(self.folio, "Cash", 250)
		for pay in frappe.get_doc("Folio", self.folio).payments:
			self.assertEqual((pay.currency, pay.amount, pay.exchange_rate,
			                  float(pay.fx_amount or 0)), ("INR", 250, 1, 0))
		self.assertEqual(cashier._recompute_session_totals(self.sess)["expected_cash"], 1000)

	def test_overpayment_change_is_refunded_in_home_currency(self):
		self.rate(buy=80)
		api._post_folio_charge(self.folio, "Misc", "Airport transfer", 1001)
		bal = frappe.get_doc("Folio", self.folio).balance
		shown = ledger.folio_in_currency(self.folio, "USD")
		self.assertEqual(shown["balance"], ledger.home_to_fx(bal, 80))
		self.assertEqual(shown["home_currency"], "INR")
		api.add_folio_payment(self.folio, "Cash", shown["balance"], currency="USD")
		change = -frappe.get_doc("Folio", self.folio).balance
		self.assertTrue(0 <= change < 80 * 0.01 + 0.001, change)
		if change:
			api.refund_folio_payment(self.folio, change, "Cash", "Change")
			self.assertAlmostEqual(frappe.get_doc("Folio", self.folio).balance, 0, places=2)

	def test_display_needs_todays_rate(self):
		with self.assertRaises(frappe.ValidationError):
			ledger.folio_in_currency(self.folio, "EUR")
