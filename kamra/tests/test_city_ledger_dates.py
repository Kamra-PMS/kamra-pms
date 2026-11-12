"""Received date, disputed city-ledger bills, aging on the business date.

kamra.ledger.city_ledger_settle, set_city_ledger_dispute and _age_buckets,
plus the reminder skip in kamra.statements. A disputed bill stays in the
aging; it is not hidden.
"""

from __future__ import annotations

from unittest.mock import patch

import frappe

from kamra import credit, ledger, statements
from kamra.tests import test_credit_control as cc
from kamra.tests.audit_fixtures import PROP_A, TODAY, d

EMAIL = "ap@ut-ledger-dates.test"


def _payment(name: str):
	return frappe.db.get_value(
		"City Ledger Entry", name, ["posting_date", "received_on"], as_dict=True)


def _ar_date(payment: str):
	return frappe.db.get_value(
		"Folio Ledger Entry",
		{"source_doctype": "City Ledger Entry", "source_name": payment, "ledger": "AR"},
		"business_date")


class TestCityLedgerDates(cc.CreditControlTestCase):

	def test_payment_defaults_to_the_business_date(self):
		self.bill(500)
		out = ledger.city_ledger_settle(self.account, 200)
		row = _payment(out["payment"])
		self.assertEqual((str(row.posting_date), str(row.received_on), str(_ar_date(out["payment"]))),
		                 (TODAY, TODAY, TODAY))
		self.assertEqual(out["received_on"], TODAY)

	def test_received_on_dates_the_payment_and_refuses_a_future_or_unauthorised_past(self):
		self.bill(500)
		out = ledger.city_ledger_settle(self.account, 100, received_on=d(-3))
		row = _payment(out["payment"])
		self.assertEqual((str(row.posting_date), str(row.received_on), str(_ar_date(out["payment"]))),
		                 (d(-3), d(-3), d(-3)))
		with patch("kamra.business_date.can_backdate", return_value=False):
			with self.assertRaises(frappe.ValidationError):
				ledger.city_ledger_settle(self.account, 50, received_on=d(-2))
		with self.assertRaises(frappe.ValidationError):
			ledger.city_ledger_settle(self.account, 50, received_on=d(1))

	def test_disputed_bill_stays_on_the_aging_and_is_not_chased(self):
		self.terms(days=0)
		_moved, folio = self.bill(500)
		_other, sibling = self.bill(200, room=self.room2)
		with self.assertRaises(frappe.ValidationError):
			ledger.set_city_ledger_dispute(folio, 1, "  ")
		ledger.set_city_ledger_dispute(folio, 1, "Rate was wrong")

		# The calendar has moved on; night audit has not. Aging stays put.
		with patch("kamra.ledger.nowdate", return_value=d(40)):
			early = ledger.city_ledger_aging(PROP_A)["accounts"][0]
		self.assertEqual(early["overdue"], 0)

		frappe.db.set_value("Property", PROP_A, "business_date", d(40),
		                    update_modified=False)
		row = ledger.city_ledger_aging(PROP_A)["accounts"][0]
		self.assertAlmostEqual(row["overdue"], 700, places=2)
		self.assertAlmostEqual(row["disputed"], 500, places=2)
		self.assertIn(folio, [r["folio"] for r in ledger.city_ledger_account(
			self.account)["open_items"]])
		flagged = next(r for r in ledger.city_ledger_account(self.account)["open_items"]
		               if r["folio"] == folio)
		self.assertTrue(flagged["disputed"])
		self.assertEqual(flagged["dispute_note"], "Rate was wrong")

		with patch("kamra.ledger.nowdate", return_value=d(40)):
			res = credit.check_company_credit(self.company, PROP_A, 0)
		self.assertAlmostEqual(res["overdue_amount"], 200, places=2)

		frappe.db.set_value("Corporate Account", self.company, "contact_email", EMAIL)
		cc.set_setting(PROP_A, "credit_reminders", 1)
		with patch("kamra.statements.nowdate", return_value=d(40)), \
		     patch("kamra.ledger.nowdate", return_value=d(40)), \
		     patch("frappe.sendmail") as mail:
			sent = statements.send_property_reminders(PROP_A)["sent"]
		self.assertEqual([s["folio"] for s in sent], [sibling])
		self.assertEqual(mail.call_count, 1)
		html = statements.company_statement(self.account, format="html")["content"]
		self.assertIn("Disputed", html)
		self.assertIn("Rate was wrong", html)
