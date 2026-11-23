"""#521: a company pays a bill less tax it withholds; the withheld part
clears the bill and waits as Tax Withheld until its certificate."""

from __future__ import annotations

from unittest.mock import patch

import frappe

from kamra import ledger, receivables
from kamra.tests import test_credit_control as cc
from kamra.tests.audit_fixtures import PROP_A


def _bill(account, folio):
	return {r["folio"]: r for r in ledger.city_ledger_open_folios(account)}[folio]


def _ar_net(folio):
	return round(float(frappe.db.sql(
		"""SELECT COALESCE(SUM(debit - credit), 0) FROM `tabFolio Ledger Entry`
		   WHERE folio = %s AND ledger = 'AR'""", folio)[0][0]), 2)


def _balance(account):
	return round(float(frappe.db.get_value("City Ledger Account", account, "balance")), 2)


class ARWithholdingTestCase(cc.CreditControlTestCase):

	def tds(self, folio, amount, **kw):
		return [{"folio": folio, "amount": amount, "tax": "TDS-194C", "rate": 2, **kw}]

	def test_98_paid_plus_2_withheld_clears_a_100_bill(self):
		_, folio = self.bill(100)
		out = ledger.city_ledger_settle(self.account, 98, withholdings=self.tds(folio, 2))
		self.assertAlmostEqual(out["unapplied"], 0, 2)
		item = _bill(self.account, folio)
		self.assertAlmostEqual(item["outstanding"], 0, 2)
		self.assertAlmostEqual(item["paid"], 98, 2)  # the withheld part is not paid money
		self.assertAlmostEqual(_ar_net(folio), 0, 2)
		self.assertAlmostEqual(_balance(self.account), 0, 2)
		self.assertAlmostEqual(ledger.city_ledger_account(self.account)["overdue"], 0, 2)
		held = receivables.withheld_tax(PROP_A)
		self.assertEqual(len(held["rows"]), 1)
		row = held["rows"][0]
		self.assertEqual((row["tax_code"], row["amount"], row["status"]),
		                 ("TDS-194C", 2.0, "Awaiting Certificate"))
		self.assertEqual(held["totals"], {"TDS u/s 194C": 2.0})

	def test_oldest_first_leaves_room_for_what_was_withheld(self):
		_, a = self.bill(100)
		_, b = self.bill(100, room=self.room2)
		withheld = self.tds(a, 2) + self.tds(b, 2)
		ledger.city_ledger_settle(self.account, 196, withholdings=withheld)
		for f in (a, b):
			self.assertAlmostEqual(_bill(self.account, f)["outstanding"], 0, 2)

	def test_certificate_is_recorded_and_leaves_the_waiting_list(self):
		_, folio = self.bill(100)
		ledger.city_ledger_settle(self.account, 98, withholdings=self.tds(folio, 2))
		name = receivables.withheld_tax(PROP_A)["rows"][0]["name"]
		receivables.record_withholding_certificate(name, "16A-123", "Q3 FY2026-27")
		self.assertEqual(receivables.withheld_tax(PROP_A)["rows"], [])
		done = receivables.withheld_tax(PROP_A, status="Certificate Received")["rows"][0]
		self.assertEqual((done["certificate_number"], done["certificate_period"]),
		                 ("16A-123", "Q3 FY2026-27"))
		doc = frappe.get_doc("Tax Withheld", name)
		doc.amount = 5
		with self.assertRaisesRegex(frappe.ValidationError, "can't change"):
			doc.save(ignore_permissions=True)

	def test_reversing_the_payment_brings_the_withheld_part_back(self):
		_, folio = self.bill(100)
		out = ledger.city_ledger_settle(self.account, 98, withholdings=self.tds(folio, 2))
		ledger.reverse_city_ledger_payment(out["payment"], reason_code="REV-BOUNCE")
		self.assertAlmostEqual(_bill(self.account, folio)["outstanding"], 100, 2)
		self.assertAlmostEqual(_ar_net(folio), 100, 2)
		self.assertAlmostEqual(_balance(self.account), 100, 2)
		self.assertEqual(frappe.db.get_value("Tax Withheld", {"payment": out["payment"]},
		                                     "status"), "Reversed")

	def test_refuses_more_than_owed_and_unknown_taxes(self):
		_, folio = self.bill(100)
		with self.assertRaises(frappe.ValidationError):
			ledger.city_ledger_settle(self.account, 50, withholdings=self.tds(folio, 150))
		with self.assertRaises(frappe.ValidationError):
			ledger.city_ledger_settle(self.account, 98, withholdings=[
				{"folio": folio, "amount": 2, "tax": "NOPE"}])
		with self.assertRaises(frappe.ValidationError):  # 194C is 1% or 2%
			ledger.city_ledger_settle(self.account, 98, withholdings=self.tds(folio, 2, rate=7))
		self.assertAlmostEqual(_bill(self.account, folio)["outstanding"], 100, 2)

	def test_an_agents_payment_keeps_the_withholding_until_confirmed(self):
		_, folio = self.bill(100)
		with patch("kamra.credit._is_agent", return_value=True):
			out = ledger.city_ledger_settle(self.account, 98,
			                                withholdings=self.tds(folio, 2))
		self.assertTrue(out["pending"])
		self.assertAlmostEqual(_bill(self.account, folio)["outstanding"], 100, 2)
		self.assertFalse(frappe.db.exists("Tax Withheld", {"folio": folio}))

	def test_the_pack_names_the_taxes(self):
		from kamra.localization import generic, withholding_taxes
		from kamra.localization import india
		self.assertEqual([t["code"] for t in withholding_taxes(india)],
		                 ["TDS-194C", "TDS-194I"])
		self.assertEqual([t["code"] for t in withholding_taxes(generic)], ["WHT"])
