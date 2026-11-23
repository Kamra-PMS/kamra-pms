"""#228 ERPNext bridge: the day's journal balances and maps every leg, posts
once per business date, can be reversed and posted again, and stays off
(and harmless) without ERPNext. CI has no ERPNext, so the Journal Entry
insert/cancel are mocked; everything else runs on the real ledger."""

from __future__ import annotations

from unittest.mock import patch

import frappe

from kamra import api, erpnext_bridge as eb
from kamra.tests.audit_fixtures import (
	PROP_A, TODAY, AuditTestCase, d, guest_folio, make_property, make_reservation,
	make_room, make_room_type,
)
from kamra.tests.test_billing_approvals_split import set_setting

MAP = """# Kamra key = ERPNext account
Guest = Guest Ledger - UT
Deposit = Guest Deposits - UT
AR = City Ledger - UT
Tax = Output Tax - UT
1000 = Room Revenue - UT
3000 = Laundry Revenue - UT
9001 = Cash - UT
"""


def test_rows():
	rows = [
		# a room night of 112 incl. 12 tax, and a laundry charge with no tax
		{"ledger": "Guest", "transaction_code": "1000", "debit": 112, "credit": 0,
		 "gl_code": None, "charge_total": 112, "charge_tax": 12},
		{"ledger": "Guest", "transaction_code": "3000", "debit": 50, "credit": 0,
		 "gl_code": None, "charge_total": 50, "charge_tax": 0},
		# the guest pays 162 cash
		{"ledger": "Guest", "transaction_code": "9001", "debit": 0, "credit": 162,
		 "gl_code": None, "charge_total": None, "charge_tax": None},
	]
	return rows


class ERPNextBridgeTest(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY)
		set_setting(PROP_A, "erpnext_account_map", MAP)
		set_setting(PROP_A, "erpnext_company", "UT Hotels")
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")

	def test_lines_balance_split_tax_and_report_missing_keys(self):
		lines, missing = eb.journal_lines(test_rows(), eb.account_map(PROP_A))
		self.assertEqual(missing, [])
		by = {ln["account"]: ln for ln in lines}
		self.assertEqual(by["Room Revenue - UT"]["credit"], 100)
		self.assertEqual(by["Output Tax - UT"]["credit"], 12)
		self.assertEqual(by["Laundry Revenue - UT"]["credit"], 50)
		self.assertEqual(by["Cash - UT"]["debit"], 162)
		self.assertNotIn("Guest Ledger - UT", by)  # charged and paid the same day
		self.assertAlmostEqual(sum(ln["debit"] for ln in lines),
		                       sum(ln["credit"] for ln in lines), 2)
		_, missing = eb.journal_lines(test_rows(), {"Guest": "G"})
		self.assertEqual(missing, ["1000", "3000", "9001", "Tax"])

	def test_a_line_keeps_the_gl_code_it_was_posted_with(self):
		rows = [{"ledger": "Guest", "transaction_code": "1000", "debit": 10, "credit": 0,
		         "gl_code": "4000", "charge_total": None, "charge_tax": None}]
		lines, missing = eb.journal_lines(rows, {"Guest": "G", "4000": "Rooms 4000",
		                                         "1000": "Rooms by code"})
		self.assertEqual(missing, [])
		self.assertIn("Rooms 4000", [ln["account"] for ln in lines])

	def _day(self):
		res = make_reservation(PROP_A, self.rt, d(-1), d(1), status="Checked In",
		                       room=self.room)
		folio = guest_folio(res.name)
		api.add_folio_charge(folio, "Laundry", "UT laundry", 50, gst_rate=0)
		# night audit closed TODAY
		frappe.db.set_value("Property", PROP_A, "business_date", d(1))
		return folio

	def test_posts_once_reverses_and_posts_again(self):
		self._day()
		with patch.object(eb, "erpnext_installed", return_value=True), \
				patch.object(eb, "_submit_journal", side_effect=["JE-1", "JE-2"]) as submit, \
				patch.object(eb, "_cancel_journal") as cancel:
			first = eb.post_daily_journal(PROP_A, TODAY)
			self.assertEqual((first["status"], first["journal_entry"]), ("posted", "JE-1"))
			je = submit.call_args[0][0]
			self.assertEqual(je["company"], "UT Hotels")
			self.assertAlmostEqual(sum(a["debit_in_account_currency"] for a in je["accounts"]),
			                       sum(a["credit_in_account_currency"] for a in je["accounts"]), 2)
			again = eb.post_daily_journal(PROP_A, TODAY)
			self.assertEqual(again["status"], "already_posted")
			self.assertEqual(submit.call_count, 1)
			eb.reverse_daily_journal(PROP_A, TODAY, "UT correction")
			cancel.assert_called_once_with("JE-1")
			self.assertEqual(eb.post_daily_journal(PROP_A, TODAY)["journal_entry"], "JE-2")

	def test_refuses_an_open_date_or_an_unmapped_key(self):
		self._day()
		with patch.object(eb, "erpnext_installed", return_value=True), \
				patch.object(eb, "_submit_journal", return_value="JE-X") as submit:
			with self.assertRaisesRegex(frappe.ValidationError, "not closed"):
				eb.post_daily_journal(PROP_A, d(1))
			set_setting(PROP_A, "erpnext_account_map", "Guest = G")
			with self.assertRaisesRegex(frappe.ValidationError, "Map these"):
				eb.post_daily_journal(PROP_A, TODAY)
			submit.assert_not_called()

	def test_without_erpnext_nothing_posts_and_night_audit_is_untouched(self):
		set_setting(PROP_A, "erpnext_gl_posting", 1)
		self.assertFalse(eb.gl_posting_on(PROP_A))  # ERPNext is not on CI
		with self.assertRaisesRegex(frappe.ValidationError, "not installed"):
			eb.post_daily_journal(PROP_A, TODAY)
		eb.after_night_audit(PROP_A, TODAY)  # logs, never raises
		self.assertEqual(eb.preview_daily_journal(PROP_A, TODAY)["missing"], [])
