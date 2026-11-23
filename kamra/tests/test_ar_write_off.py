"""#522: write a company bill off as bad debt, with the allowance approval
rules (threshold, manager PIN, pending request; agents only ask)."""

from __future__ import annotations

from unittest.mock import patch

import frappe

from kamra import api, ledger, receivables
from kamra.tests import test_credit_control as cc
from kamra.tests.audit_fixtures import PROP_A, ensure_user
from kamra.tests.test_billing_approvals_split import set_pin, set_setting

FINANCE = "ut.wo.finance@test.local"
GM = "ut.wo.gm@test.local"


def _bill(account, folio):
	return {r["folio"]: r for r in ledger.city_ledger_open_folios(account)}[folio]


def _ar_net(folio):
	return round(float(frappe.db.sql(
		"""SELECT COALESCE(SUM(debit - credit), 0) FROM `tabFolio Ledger Entry`
		   WHERE folio = %s AND ledger = 'AR'""", folio)[0][0]), 2)


class ARWriteOffTestCase(cc.CreditControlTestCase):

	def setUp(self):
		super().setUp()
		ensure_user(FINANCE, ["Finance"])
		ensure_user(GM, ["Hotel Admin"])
		set_setting(PROP_A, "allowance_approval", "Hotel Admin")
		set_setting(PROP_A, "allowance_approval_above", 100)

	def tearDown(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		super().tearDown()

	def test_small_write_off_posts_and_updates_bill_aging_and_books(self):
		_, folio = self.bill(500)
		ledger.city_ledger_settle(self.account, 300)
		frappe.set_user(FINANCE)  # nosemgrep: frappe-setuser -- test fixture
		out = receivables.write_off_ar_bill(self.account, folio, 80,
		                                    reason_code="ADJ-BADDEBT", reason="UT closed down")
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		self.assertNotIn("pending", out)
		item = _bill(self.account, folio)
		self.assertAlmostEqual(item["outstanding"], 120, 2)
		self.assertAlmostEqual(item["paid"], 300, 2)  # a write-off is not a payment
		self.assertAlmostEqual(_ar_net(folio), 120, 2)
		self.assertAlmostEqual(float(frappe.db.get_value(
			"City Ledger Account", self.account, "balance")), 120, 2)
		aging = ledger.city_ledger_account(self.account)
		self.assertAlmostEqual(aging["open_balance"], 120, 2)
		entry = frappe.get_doc("City Ledger Entry", out["entry"])
		self.assertEqual(entry.kind, "Write Off")
		self.assertIn("Bad debt", entry.notes)
		code = frappe.db.get_value("Folio Ledger Entry",
		                           {"folio": folio, "ledger": "AR", "credit": 80},
		                           "transaction_code")
		self.assertEqual(code, receivables.WRITE_OFF_CODE[0])
		history = ledger.city_ledger_history(self.account)["entries"]
		self.assertEqual(history[-1]["kind"], "Write Off")
		with self.assertRaises(frappe.ValidationError):  # more than it owes
			receivables.write_off_ar_bill(self.account, folio, 500, reason="UT")

	def test_above_threshold_waits_for_a_manager_then_posts(self):
		_, folio = self.bill(500)
		frappe.set_user(FINANCE)  # nosemgrep: frappe-setuser -- test fixture
		out = receivables.write_off_ar_bill(self.account, folio, 400, reason="UT gone")
		self.assertTrue(out["pending"])
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		self.assertAlmostEqual(_bill(self.account, folio)["outstanding"], 500, 2)
		listed = api.allowance_requests(PROP_A, city_ledger_account=self.account)["requests"]
		self.assertEqual([r["kind"] for r in listed], ["Write Off"])

		frappe.set_user(FINANCE)  # nosemgrep: frappe-setuser -- test fixture
		with self.assertRaises(frappe.PermissionError):  # not an approver here
			api.decide_allowance(out["request"], approve=1)
		set_pin(GM, "2468")
		frappe.set_user(GM)  # nosemgrep: frappe-setuser -- test fixture
		api.decide_allowance(out["request"], approve=1, pin="2468")
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		self.assertAlmostEqual(_bill(self.account, folio)["outstanding"], 100, 2)
		self.assertAlmostEqual(_ar_net(folio), 100, 2)
		req = frappe.get_doc("Allowance Request", out["request"])
		self.assertEqual((req.status, req.decided_by), ("Approved", GM))

	def test_approval_rechecks_what_the_bill_owes(self):
		_, folio = self.bill(500)
		frappe.set_user(FINANCE)  # nosemgrep: frappe-setuser -- test fixture
		out = receivables.write_off_ar_bill(self.account, folio, 400, reason="UT")
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		ledger.city_ledger_settle(self.account, 300)  # the company paid after all
		set_pin(GM, "2468")
		frappe.set_user(GM)  # nosemgrep: frappe-setuser -- test fixture
		with self.assertRaisesRegex(frappe.ValidationError, "can't be more"):
			api.decide_allowance(out["request"], approve=1, pin="2468")

	def test_manager_writes_off_at_once_with_their_pin(self):
		_, folio = self.bill(500)
		set_pin(GM, "2468")
		frappe.set_user(GM)  # nosemgrep: frappe-setuser -- test fixture
		out = receivables.write_off_ar_bill(self.account, folio, 500, reason="UT", pin="2468")
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		self.assertEqual(out["approved_by"], GM)
		self.assertAlmostEqual(_bill(self.account, folio)["outstanding"], 0, 2)

	def test_an_agent_only_asks_and_never_approves(self):
		_, folio = self.bill(500)
		with patch("kamra.credit._is_agent", return_value=True):
			out = receivables.write_off_ar_bill(self.account, folio, 10, reason="UT")
			self.assertTrue(out["pending"])  # even under the threshold
			with self.assertRaises(frappe.PermissionError):
				api.decide_allowance(out["request"], approve=1)
		self.assertAlmostEqual(_bill(self.account, folio)["outstanding"], 500, 2)

	def test_a_write_off_needs_a_reason(self):
		_, folio = self.bill(500)
		with self.assertRaises(frappe.ValidationError):
			receivables.write_off_ar_bill(self.account, folio, 50)

	def test_a_pending_write_off_cant_be_turned_into_something_else(self):
		_, folio = self.bill(500)
		frappe.set_user(FINANCE)  # nosemgrep: frappe-setuser -- test fixture
		out = receivables.write_off_ar_bill(self.account, folio, 400, reason="UT")
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		req = frappe.get_doc("Allowance Request", out["request"])
		req.kind = "Allowance"
		with self.assertRaisesRegex(frappe.ValidationError, "can't change"):
			req.save(ignore_permissions=True)
