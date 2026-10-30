"""Accounts receivable by hand: account setup, invoices raised on an account
(no stay), moving a bill between accounts, restricted accounts.

kamra.receivables over the city ledger, checked against the same numbers
the aging, statement and ledgers read. The company, account and bill
helpers come from the credit-control fixture.
"""

from __future__ import annotations

import frappe

from kamra import credit, ledger, receivables
from kamra.tests import test_credit_control as cc
from kamra.tests.audit_fixtures import PROP_A

OTHER = "UT AR Parent Co"


def _open(account):
	return {r["folio"]: r for r in ledger.city_ledger_open_folios(account)}


class ReceivablesTestCase(cc.CreditControlTestCase):

	def other_company(self):
		if not frappe.db.exists("Corporate Account", OTHER):
			frappe.get_doc({"doctype": "Corporate Account",
			                "company_name": OTHER}).insert(ignore_permissions=True)
		return OTHER

	def invoice(self, *lines, **kw):
		return receivables.create_ar_invoice(self.account, list(lines), **kw)

	# account setup ---------------------------------------------------------

	def test_opening_an_account_puts_the_company_on_credit(self):
		co = self.other_company()
		out = receivables.save_ar_account(PROP_A, co, account_number="UT-PARENT",
		                                  credit_limit=5000, use_default_credit_days=0,
		                                  credit_days=45, billing_address="1 Main St")
		acc = frappe.get_doc("City Ledger Account", out["account"])
		self.assertEqual((acc.account_number, acc.credit_days, acc.billing_address),
		                 ("UT-PARENT", 45, "1 Main St"))
		self.assertTrue(frappe.db.get_value("Corporate Account", co, "credit_allowed"))
		# checkout bills into the same account, not a second one
		self.assertEqual(ledger._ar_account(PROP_A, co), out["account"])
		with self.assertRaises(frappe.ValidationError):
			receivables.save_ar_account(PROP_A, co)
		with self.assertRaises(frappe.ValidationError):  # number taken
			receivables.save_ar_account(PROP_A, self.company, account_number="UT-PARENT",
			                            account=self.account)
		with self.assertRaises(frappe.ValidationError):  # restricted needs a why
			receivables.save_ar_account(PROP_A, co, account=out["account"], restricted=1)

	# invoices raised on the account -----------------------------------------

	def test_invoice_on_the_account_is_billed_taxed_and_numbered(self):
		out = self.invoice(
			{"charge_type": "Misc", "description": "Meeting room", "amount": 1000,
			 "qty": 2, "gst_rate": 18},
			{"charge_type": "Misc", "description": "Projector", "amount": 500,
			 "gst_rate": 0},
			reference="PO-778")
		self.assertAlmostEqual(out["total"], 2860, 2)       # 2000 + 360 tax + 500
		self.assertAlmostEqual(out["balance"], 2860, 2)
		folio = frappe.get_doc("Folio", out["folio"])
		self.assertEqual((folio.folio_type, folio.status, folio.reservation),
		                 ("Account", "Closed", None))
		self.assertEqual(folio.invoice_number, out["invoice_number"])
		item = _open(self.account)[out["folio"]]
		self.assertEqual(item["invoice_number"], out["invoice_number"])
		self.assertAlmostEqual(item["outstanding"], 2860, 2)
		# guest ledger nets to zero (charged, then billed on); AR carries it
		rows = frappe.db.sql(
			"""SELECT ledger, SUM(debit - credit) FROM `tabFolio Ledger Entry`
			   WHERE folio = %s GROUP BY ledger""", out["folio"])
		net = {k: round(float(v), 2) for k, v in rows}
		self.assertAlmostEqual(net.get("Guest", 0), 0, 2)
		self.assertAlmostEqual(net["AR"], 2860, 2)
		# a payment clears it like any company bill
		ledger.city_ledger_settle(self.account, 2860)
		self.assertNotIn(out["folio"], {f for f, r in _open(self.account).items()
		                                if r["outstanding"] > 0})
		# it lives on Receivables, not in the stay folio history
		hist = ledger.folio_history(PROP_A)["folios"]
		self.assertNotIn(out["folio"], [r.name for r in hist])

	def test_invoice_refuses_bad_lines(self):
		for line in ({"charge_type": "Misc", "description": "x", "amount": 0},
		             {"charge_type": "Misc", "description": "", "amount": 10},
		             {"charge_type": "Misc", "description": "x", "amount": 10, "gst_rate": 7},
		             {"charge_type": "Allowance", "description": "x", "amount": 10},
		             {"charge_type": "Misc", "description": "x", "amount": 10, "qty": 1.5}):
			with self.assertRaises(frappe.ValidationError, msg=str(line)):
				self.invoice(line)
		with self.assertRaises(frappe.ValidationError):
			self.invoice()

	def test_invoice_runs_credit_control(self):
		cc.set_setting(PROP_A, "credit_control", "Block")
		self.terms(limit=100)
		line = {"charge_type": "Misc", "description": "Hall", "amount": 500}
		with self.assertRaises(credit.CreditBlocked):
			self.invoice(line)
		out = self.invoice(line, credit_override_reason="MD approved")
		self.assertAlmostEqual(out["balance"], 500, 2)

	# restricted --------------------------------------------------------------

	def test_restricted_account_takes_no_new_bills_but_takes_payments(self):
		self.bill(400)
		frappe.db.set_value("City Ledger Account", self.account,
		                    {"restricted": 1, "restricted_reason": "Disputed"})
		with self.assertRaises(frappe.ValidationError):
			self.invoice({"charge_type": "Misc", "description": "x", "amount": 10})
		cc.set_setting(PROP_A, "credit_control", "Warn")
		chk = credit.check_company_credit(self.account, PROP_A, 10)
		self.assertFalse(chk["ok"])
		self.assertTrue(chk.get("restricted"))
		ledger.city_ledger_settle(self.account, 400)
		self.assertAlmostEqual(
			frappe.db.get_value("City Ledger Account", self.account, "balance"), 0, 2)

	# transfer between accounts -------------------------------------------------

	def test_transfer_moves_what_is_owed_and_keeps_the_bill_date(self):
		parent = receivables.save_ar_account(
			PROP_A, self.other_company(), account_number="UT-PARENT")["account"]
		_, folio = self.bill(500)
		ledger.city_ledger_settle(self.account, 200)
		before = _open(self.account)[folio]
		out = receivables.transfer_ar_invoice(self.account, folio, parent,
		                                      reason="Parent pays")
		self.assertAlmostEqual(out["amount"], 300, 2)
		self.assertAlmostEqual(_open(self.account)[folio]["outstanding"], 0, 2)
		moved = _open(parent)[folio]
		self.assertAlmostEqual(moved["outstanding"], 300, 2)
		self.assertEqual(moved["invoice_date"], before["invoice_date"])
		# each account's stored balance agrees with its ledger
		for acc in (self.account, parent):
			stored = frappe.db.get_value("City Ledger Account", acc, "balance")
			net = frappe.db.sql("""SELECT SUM(debit - credit) FROM `tabCity Ledger Entry`
			                       WHERE account = %s""", acc)[0][0]
			self.assertAlmostEqual(float(stored), float(net), 2)
		with self.assertRaises(frappe.ValidationError):  # nothing left to move
			receivables.transfer_ar_invoice(self.account, folio, parent)
		# the parent pays it off
		ledger.city_ledger_settle(parent, 300)
		self.assertAlmostEqual(_open(parent)[folio]["outstanding"], 0, 2)

	# review follow-ups ---------------------------------------------------------

	def test_credit_note_on_an_account_invoice_credits_the_account(self):
		out = self.invoice({"charge_type": "Misc", "description": "Hall",
		                    "amount": 1000})
		ledger.issue_credit_note(out["folio"], 300, "Half day only")
		stored = frappe.db.get_value("City Ledger Account", self.account, "balance")
		net = frappe.db.sql("""SELECT SUM(debit - credit) FROM `tabCity Ledger Entry`
		                       WHERE account = %s""", self.account)[0][0]
		self.assertAlmostEqual(float(stored), float(net), 2)
		self.assertAlmostEqual(_open(self.account)[out["folio"]]["outstanding"], 700, 2)

	def test_zatca_buyer_of_an_account_invoice_is_the_company(self):
		from kamra import zatca
		frappe.db.set_value("Corporate Account", self.company, "gstin", "300000000000003")
		out = self.invoice({"charge_type": "Misc", "description": "Hall",
		                    "amount": 100})
		kind, buyer = zatca._folio_buyer(frappe.get_doc("Folio", out["folio"]))
		self.assertEqual((kind, buyer["vat"]), ("Standard", "300000000000003"))

	def test_account_settings_only_change_through_receivables(self):
		# restricted / limit / balance can't be flipped over /api/resource
		for role in ("Front Desk", "Finance", "Hotel Admin", "Kamra Agent"):
			perms = frappe.get_all("DocPerm", filters={
				"parent": "City Ledger Account", "role": role},
				fields=["write", "create", "delete"])
			self.assertTrue(perms, role)
			self.assertFalse(any(p.write or p.create or p.delete for p in perms), role)

	# month-end bill ------------------------------------------------------------

	def test_checkout_bill_gets_its_invoice_number_on_the_account(self):
		from kamra import folio as folio_mod
		_, folio = self.bill(500)
		self.assertFalse(frappe.db.get_value("City Ledger Entry",
		                                     {"folio": folio, "kind": "Invoice"}, "invoice_number"))
		number = folio_mod.close_folio(folio)
		self.assertEqual(_open(self.account)[folio]["invoice_number"], number)

	def test_monthly_bill_rolls_up_the_month(self):
		from frappe.utils import getdate

		from kamra import statements
		out = self.invoice({"charge_type": "Misc", "description": "Hall", "amount": 1000,
		                    "gst_rate": 18})
		ledger.city_ledger_settle(self.account, 500)
		month = str(getdate(frappe.db.get_value(
			"City Ledger Entry", {"folio": out["folio"], "kind": "Invoice"},
			"creation")))[:7]
		mb = statements.monthly_bill(self.account, month)
		line = next(b for b in mb["bills"] if b["invoice"] == out["invoice_number"])
		self.assertEqual((line["taxable"], line["tax"], line["amount"]), (1000, 180, 1180))
		self.assertAlmostEqual(mb["paid"], 500, 2)
		self.assertAlmostEqual(mb["closing"], mb["opening"] + mb["billed"] - 500, 2)
		self.assertTrue(mb["number"].startswith("SOA-") and mb["number"].endswith(month.replace("-", "")))
		# an account invoice is corrected by credit note, never cancelled; a
		# cancelled stay bill's number leaves the account until it re-closes
		from kamra import folio as folio_mod
		with self.assertRaises(frappe.ValidationError):
			folio_mod.cancel_invoice(out["folio"], "UT wrong GSTIN")
		_, stay_folio = self.bill(300)
		folio_mod.close_folio(stay_folio)
		ledger.issue_credit_note(stay_folio, 50, "UT goodwill")
		folio_mod.cancel_invoice(stay_folio, "UT wrong GSTIN")
		self.assertIsNone(frappe.db.get_value("City Ledger Entry",
		                                      {"folio": stay_folio, "kind": "Invoice"},
		                                      "invoice_number"))
		# the credit note's CN- number doesn't stand in for the bill's
		self.assertIsNone(_open(self.account)[stay_folio]["invoice_number"])
		for bad in ("2026-13", "2026-1", "202610", "2026-10-05", ""):
			with self.assertRaises(frappe.ValidationError, msg=bad):
				statements.monthly_bill(self.account, bad)
		html = statements.monthly_bill_html(mb)
		self.assertIn(out["invoice_number"], html)
		self.assertIn("not a tax invoice", html)

	# second review ---------------------------------------------------------

	def test_account_invoice_prints_and_exports_as_a_tax_invoice(self):
		from kamra import accounting, api
		frappe.db.set_value("Corporate Account", self.company, "gstin", "29ABCDE1234F1Z5")
		out = self.invoice({"charge_type": "Misc", "description": "Hall",
		                    "amount": 1000, "gst_rate": 18})
		inv = api.folio_invoice(out["folio"])
		self.assertEqual(inv["bill_to"]["gstin"], "29ABCDE1234F1Z5")
		self.assertIsNone(inv["stay"]["reservation"])
		self.assertTrue(inv["document"]["is_final"])
		rows = accounting.export_invoices(PROP_A, "2000-01-01", "2100-12-31")["rows"]
		row = next(r for r in rows if r["invoice_number"] == out["invoice_number"])
		self.assertEqual(row["party_tax_id"], "29ABCDE1234F1Z5")
		self.assertAlmostEqual(row["grand_total"], 1180, 2)

	def test_account_invoice_cant_be_cancelled(self):
		from kamra import api
		out = self.invoice({"charge_type": "Misc", "description": "Hall",
		                    "amount": 100})
		with self.assertRaises(frappe.ValidationError):
			api.cancel_invoice(out["folio"], "wrong amount")
		self.assertEqual(frappe.db.get_value("Folio", out["folio"], "status"), "Closed")

	def test_transfer_to_the_stays_company_checks_a_restricted_account(self):
		res = cc.make_reservation(PROP_A, self.rt, cc.d(-1), cc.d(1),
		                          status="Checked In", room=self.room,
		                          company=self.company)
		folio = cc.guest_folio(res.name)
		cc.api.add_folio_charge(folio, "Misc", "UT bill", 200, gst_rate=0)
		frappe.db.set_value("City Ledger Account", self.account,
		                    {"restricted": 1, "restricted_reason": "Disputed"})
		with self.assertRaises(frappe.ValidationError):
			ledger.city_ledger_transfer(folio)  # no company passed

	def test_invoice_bills_the_account_it_was_raised_on(self):
		second = frappe.get_doc({"doctype": "City Ledger Account", "property": PROP_A,
		                         "company": self.company, "account_number": "UT-2ND",
		                         "balance": 0}).insert(ignore_permissions=True).name
		frappe.db.set_value("City Ledger Account", self.account, "credit_limit", 0)
		out = receivables.create_ar_invoice(
			second, [{"charge_type": "Misc", "description": "Hall", "amount": 100}])
		self.assertEqual(frappe.db.get_value(
			"City Ledger Entry", {"folio": out["folio"], "kind": "Invoice"}, "account"),
			second)

	def test_transfer_posts_today_and_ages_from_the_original_date(self):
		parent = receivables.save_ar_account(
			PROP_A, self.other_company(), account_number="UT-PARENT")["account"]
		res = cc.make_reservation(PROP_A, self.rt, cc.d(-1), cc.d(1),
		                          status="Checked In", room=self.room)
		folio = cc.guest_folio(res.name)
		cc.api.add_folio_charge(folio, "Misc", "UT bill", 300, gst_rate=0)
		ledger.transfer_to_city_ledger(folio, self.company, invoice_date=cc.d(-20),
		                               credit_check=False)
		receivables.transfer_ar_invoice(self.account, folio, parent)
		legs = frappe.get_all("City Ledger Entry", filters={"folio": folio},
		                      fields=["account", "kind", "posting_date", "invoice_date"],
		                      order_by="creation asc")
		moved = [r for r in legs if r.account == parent or r.kind == "Adjustment"]
		self.assertEqual({str(r.posting_date) for r in moved}, {str(cc.TODAY)})
		self.assertEqual(_open(parent)[folio]["invoice_date"], str(cc.d(-20)))

	def test_reminders_are_per_company(self):
		from kamra import statements
		from kamra.savings import log_action
		_, folio = self.bill(100)
		log_action(statements.LOG_PREFIX + "pre", "Folio", folio, PROP_A,
		           rationale=f"{self.company}: pre reminder")
		self.assertTrue(statements._reminded(folio, "pre", self.company))
		self.assertFalse(statements._reminded(folio, "pre", self.other_company()))
