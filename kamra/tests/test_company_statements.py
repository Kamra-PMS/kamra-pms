"""Company statements, due-date reminders and the AR reports (#238 phase 2).

kamra.statements (statement, reminders) and the overdue_by_company / dso
datasets in kamra.custom_reports, fed by real city ledger bills and
payments. The company and its bills come from the phase 1 fixture.
"""

from __future__ import annotations

from unittest.mock import patch

import frappe

from kamra import ledger, statements
from kamra.custom_reports import _run_dataset
from kamra.tests import test_credit_control as cc
from kamra.tests.audit_fixtures import PROP_A, TODAY, d, ensure_user

FINANCE = "ut.stmt.finance@test.local"
DESK = "ut.stmt.desk@test.local"
EMAIL = "ap@utcredit.test"


class CompanyStatementTestCase(cc.CreditControlTestCase):
	"""Reuses the phase 1 company, account and bill helpers, not its tests."""

	def contact(self, email):
		frappe.db.set_value("Corporate Account", self.company, "contact_email", email)

	def on(self, day):
		"""Pin today for the ledger and the statements."""
		stack = patch("kamra.ledger.nowdate", return_value=day)
		stack2 = patch("kamra.statements.nowdate", return_value=day)
		stack.start(), stack2.start()
		self.addCleanup(stack.stop)
		self.addCleanup(stack2.stop)

	def remind(self, day):
		with patch("kamra.ledger.nowdate", return_value=day), \
		     patch("kamra.statements.nowdate", return_value=day), \
		     patch("frappe.sendmail") as mail, \
		     patch("kamra.night_audit.alert_staff") as alert:
			out = statements.send_property_reminders(PROP_A)
		return out, mail, alert

	# statement -------------------------------------------------------------

	def test_statement_totals_and_aging_match_the_ledger(self):
		self.terms(days=30)
		self.bill(500)
		self.bill(300, room=self.room2)
		ledger.city_ledger_settle(self.account, 600, reference="UT-1")
		self.on(d(45))
		st = statements.company_statement(self.account)
		row = ledger.city_ledger_aging(PROP_A)["accounts"][0]
		for k in ("balance", "not_due", "d1_30", "d31_60", "overdue", "unapplied_credit"):
			self.assertAlmostEqual(st[k], row[k], 2, k)
		self.assertAlmostEqual(st["balance"], 200, 2)
		self.assertAlmostEqual(st["d1_30"], 200, 2)
		self.assertAlmostEqual(st["open_balance"],
		                       sum(r["outstanding"] for r in st["open_items"]), 2)
		self.assertEqual([r["days_overdue"] for r in st["open_items"]], [15])
		html = statements.company_statement(self.account, format="html")["content"]
		self.assertIn("Statement of account", html)
		self.assertIn(cc.COMPANY, html)
		self.assertIn("200.00", html)
		self.assertIn("UT-1", html)

	def test_unapplied_credit_shows_on_the_statement(self):
		self.terms(days=30)
		self.bill(500)
		ledger.city_ledger_settle(self.account, 700)
		st = statements.company_statement(self.account)
		self.assertAlmostEqual(st["unapplied_credit"], 200, 2)
		self.assertAlmostEqual(st["balance"], -200, 2)

	def test_email_statement_defaults_to_the_billing_contact(self):
		self.bill(500)
		self.contact(None)
		with patch("frappe.sendmail") as mail:
			with self.assertRaises(frappe.ValidationError):
				statements.email_company_statement(self.account)
			mail.assert_not_called()
			self.contact(EMAIL)
			out = statements.email_company_statement(self.account)
		self.assertEqual(out["sent_to"], [EMAIL])
		kw = mail.call_args.kwargs
		self.assertEqual(kw["recipients"], [EMAIL])
		self.assertTrue(kw["attachments"][0]["fname"].endswith(".html"))

	# reminders -------------------------------------------------------------

	def test_reminder_stage(self):
		for late, stage in ((-4, None), (-3, "pre"), (-1, "pre"), (0, "due"),
		                    (14, "due"), (15, "late"), (120, "late")):
			self.assertEqual(statements.reminder_stage(late), stage, late)

	def test_each_stage_is_sent_once_per_bill(self):
		self.terms(days=10)
		self.contact(EMAIL)
		_, folio = self.bill(500)
		sent = []
		for day in (d(6), d(7), d(7), d(9), d(10), d(10), d(24), d(25), d(26)):
			out, mail, _alert = self.remind(day)
			stages = [s["stage"] for s in out["sent"]]
			sent.append((day, stages))
			self.assertEqual(mail.call_count, 1 if stages else 0, day)
		self.assertEqual([s for _, s in sent], [[], ["pre"], [], [], ["due"], [], [],
		                                        ["late"], []])
		self.assertEqual(frappe.db.count("Agent Action Log", {
			"reference_doctype": "Folio", "reference_name": folio,
			"action_type": ("like", "credit_reminder_%")}), 3)

	def test_missed_days_send_only_the_stage_reached(self):
		self.terms(days=10)
		self.contact(EMAIL)
		self.bill(500)
		out, mail, _alert = self.remind(d(40))
		self.assertEqual([s["stage"] for s in out["sent"]], ["late"])
		self.assertIn("is 30 days overdue", " ".join(
			str(a) for a in mail.call_args.kwargs.values()))

	def test_paid_bills_and_no_email_send_nothing(self):
		self.terms(days=10)
		self.contact(None)
		self.bill(500)
		out, mail, alert = self.remind(d(10))
		mail.assert_not_called()
		self.assertEqual(out["no_email"], [cc.COMPANY])
		alert.assert_called_once()
		self.contact(EMAIL)
		ledger.city_ledger_settle(self.account, 500)
		out, mail, alert = self.remind(d(10))
		self.assertEqual(out, {"sent": [], "no_email": []})
		mail.assert_not_called()
		alert.assert_not_called()

	def test_setting_off_sends_nothing(self):
		self.assertFalse(frappe.db.get_value(
			"Property Setting", {"property": PROP_A, "setting_key": "credit_reminders"}))
		with patch("kamra.statements.send_property_reminders") as send, \
		     patch("frappe.db.commit"):
			statements.run_payment_reminders()
			self.assertNotIn(PROP_A, [c.args[0] for c in send.call_args_list])
			cc.set_setting(PROP_A, "credit_reminders", 1)
			statements.run_payment_reminders()
			self.assertIn(PROP_A, [c.args[0] for c in send.call_args_list])

	# reports ---------------------------------------------------------------

	def test_dso_on_a_known_fixture(self):
		self.terms(days=30)
		self.bill(1000)
		ledger.city_ledger_settle(self.account, 400)
		rows = _run_dataset(PROP_A, "dso", d(-29), TODAY)["rows"]
		row = next(r for r in rows if r["company"] == cc.COMPANY)
		self.assertEqual((row["billed"], row["paid"], row["closing_balance"], row["dso"]),
		                 (1000, 400, 600, 18.0))
		self.assertEqual(rows[-1]["company"], "All companies")

	def test_overdue_by_company(self):
		self.terms(days=0)
		self.bill(500)
		self.assertNotIn(cc.COMPANY, [r["company"] for r in
		                              _run_dataset(PROP_A, "overdue_by_company", None, None)["rows"]])
		self.on(d(40))
		row = next(r for r in _run_dataset(PROP_A, "overdue_by_company", None, None)["rows"]
		           if r["company"] == cc.COMPANY)
		self.assertEqual((row["d31_60"], row["overdue"]), (500, 500))

	# role gate -------------------------------------------------------------

	def test_role_gate(self):
		self.contact(EMAIL)
		self.bill(500)
		ensure_user(DESK, ["Front Desk"])
		ensure_user(FINANCE, ["Finance"])
		frappe.set_user(DESK)  # nosemgrep: frappe-setuser -- acting as the persona
		try:
			for fn in (lambda: statements.company_statement(self.account),
			           lambda: statements.email_company_statement(self.account),
			           lambda: _run_dataset(PROP_A, "dso", d(-29), TODAY),
			           lambda: _run_dataset(PROP_A, "overdue_by_company", None, None)):
				with self.assertRaises(frappe.PermissionError):
					fn()
			frappe.set_user(FINANCE)  # nosemgrep: frappe-setuser -- acting as the persona
			self.assertEqual(statements.company_statement(self.account)["company"],
			                 cc.COMPANY)
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- restore


# the inherited phase 1 tests run in their own module
for _name in dir(cc.CreditControlTestCase):
	if _name.startswith("test_"):
		setattr(CompanyStatementTestCase, _name, None)
