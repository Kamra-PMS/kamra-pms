"""Company credit control (#238 phase 1): payment terms, due-date aging and
the credit check at check-out and booking.

kamra.ledger (effective_credit_days, transfer_to_city_ledger, aging) and
kamra.credit (check_company_credit, enforce_company_credit), fed by the
real paths: api.check_out, ledger.city_ledger_transfer, city_ledger_settle,
api.create_booking and the backfill patch.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import frappe

from kamra import api, credit, ledger
from kamra import folio as folio_mod
from kamra.settings import clear_cache
from kamra.tests.audit_fixtures import (
	PROP_A,
	TODAY,
	AuditTestCase,
	d,
	ensure_user,
	guest_folio,
	make_property,
	make_reservation,
	make_room,
	make_room_type,
)

COMPANY = "UT Credit Corp"
FINANCE = "ut.credit.finance@test.local"
DESK = "ut.credit.desk@test.local"
AGENT = "ut.credit.agent@test.local"


def set_setting(prop: str, key: str, value) -> None:
	name = frappe.db.get_value("Property Setting",
	                           {"property": prop, "setting_key": key})
	if name:
		frappe.db.set_value("Property Setting", name, "value", json.dumps(value))
	else:
		frappe.get_doc({"doctype": "Property Setting", "property": prop,
		                "setting_key": key, "value": json.dumps(value)}
		               ).insert(ignore_permissions=True)
	clear_cache(prop)


def _balance(folio: str) -> float:
	return round(float(frappe.db.get_value("Folio", folio, "balance") or 0), 2)


class CreditControlTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY)
		frappe.db.delete("Property Setting", {"property": PROP_A})
		clear_cache(PROP_A)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")
		self.room2 = make_room(PROP_A, self.rt, "102")
		if frappe.db.exists("Corporate Account", COMPANY):
			corp = frappe.get_doc("Corporate Account", COMPANY)
		else:
			corp = frappe.get_doc({"doctype": "Corporate Account",
			                       "company_name": COMPANY})
		corp.credit_allowed = 1
		corp.set("billing_rules", [{"charge_type": "Room", "pay_by": "Company"}])
		if corp.is_new():
			corp.insert(ignore_permissions=True)
		else:
			corp.save(ignore_permissions=True)
		self.company = corp.name
		self.account = ledger._ar_account(PROP_A, self.company)
		self.terms(limit=0)
		frappe.db.set_value("City Ledger Account", self.account,
		                    {"credit_days": 0, "use_default_credit_days": 1})

	def tearDown(self):
		super().tearDown()
		clear_cache(PROP_A)

	# helpers -------------------------------------------------------------

	def terms(self, limit=None, days=None, use_default=None):
		"""`days` sets the account's own terms (use property default off)."""
		values = {}
		if limit is not None:
			values["credit_limit"] = limit
		if days is not None:
			values["credit_days"] = days
			values["use_default_credit_days"] = 0
		if use_default is not None:
			values["use_default_credit_days"] = use_default
		frappe.db.set_value("City Ledger Account", self.account, values)

	def bill(self, amount, room=None):
		"""A guest folio of `amount` moved to the company's city ledger."""
		res = make_reservation(PROP_A, self.rt, d(-1), d(1),
		                       status="Checked In", room=room or self.room)
		folio = guest_folio(res.name)
		api.add_folio_charge(folio, "Misc", "UT bill", amount, gst_rate=0)
		return ledger.transfer_to_city_ledger(folio, self.company,
		                                      credit_check=False), folio

	def corporate_stay(self, room=None):
		res = make_reservation(PROP_A, self.rt, d(-1), TODAY,
		                       status="Checked In", room=room or self.room,
		                       booking_type="Corporate", company=self.company)
		folio_mod.post_remaining_nights(res)
		company_folio = frappe.db.get_value(
			"Folio", {"reservation": res.name, "folio_type": "Company"})
		self.assertTrue(company_folio)
		return res, company_folio

	def aging(self, on=None):
		if on:
			with patch("kamra.ledger.nowdate", return_value=on):
				return ledger.city_ledger_aging(PROP_A)["accounts"][0]
		return ledger.city_ledger_aging(PROP_A)["accounts"][0]

	def logs(self, action):
		return frappe.get_all("Agent Action Log",
		                      filters={"action_type": action, "property": PROP_A},
		                      fields=["rationale", "approver", "after_snapshot",
		                              "reference_name"])

	# payment terms + due dates -----------------------------------------

	def test_due_date_uses_the_account_credit_days(self):
		self.terms(days=45)
		self.bill(500)
		due = frappe.db.get_value("City Ledger Entry",
		                          {"account": self.account, "kind": "Invoice"},
		                          "due_date")
		self.assertEqual(str(due), d(45))

	def test_due_date_falls_back_to_the_property_default(self):
		self.assertEqual(ledger.effective_credit_days(self.account), 30)
		set_setting(PROP_A, "default_credit_days", 10)
		self.assertEqual(ledger.effective_credit_days(self.account), 10)
		self.bill(500)
		due = frappe.db.get_value("City Ledger Entry",
		                          {"account": self.account, "kind": "Invoice"},
		                          "due_date")
		self.assertEqual(str(due), d(10))

	def test_due_on_receipt_without_touching_the_property_default(self):
		self.terms(days=0)
		self.assertEqual(ledger.effective_credit_days(self.account), 0)
		self.bill(500)
		due = frappe.db.get_value("City Ledger Entry",
		                          {"account": self.account, "kind": "Invoice"},
		                          "due_date")
		self.assertEqual(str(due), TODAY)
		self.assertEqual(credit.company_credit_terms(self.company, PROP_A)
		                 ["default_credit_days"], 30)
		row = self.aging(d(1))
		self.assertAlmostEqual(row["d1_30"], 500, places=2)
		# back on the default: 30 days again
		self.terms(use_default=1)
		self.assertEqual(ledger.effective_credit_days(self.account), 30)

	def test_use_default_patch_keeps_old_behaviour(self):
		from kamra.patches.v42 import credit_days_use_property_default as patch_mod
		other = frappe.get_doc({"doctype": "Corporate Account",
		                        "company_name": "UT Credit Own Terms",
		                        "credit_allowed": 1}).insert(ignore_permissions=True)
		own = ledger._ar_account(PROP_A, other.name)
		# a fresh account follows the property default
		self.assertEqual(frappe.db.get_value("City Ledger Account", own,
		                                     "use_default_credit_days"), 1)
		# as left by the old code: 0 = default, anything else = own terms
		frappe.db.set_value("City Ledger Account", own,
		                    {"credit_days": 21, "use_default_credit_days": 1})
		patch_mod.execute()
		self.assertEqual(frappe.db.get_value("City Ledger Account", own,
		                                     "use_default_credit_days"), 0)
		self.assertEqual(frappe.db.get_value("City Ledger Account", self.account,
		                                     "use_default_credit_days"), 1)
		self.assertEqual(ledger.effective_credit_days(own), 21)
		self.assertEqual(ledger.effective_credit_days(self.account), 30)

	def test_45_day_company_is_not_due_at_day_35(self):
		self.terms(days=45)
		self.bill(500)
		row = self.aging(d(35))
		self.assertAlmostEqual(row["not_due"], 500, places=2)
		self.assertEqual(row["overdue"], 0)
		# the old invoice-age view called it 31-60 days old
		self.assertAlmostEqual(row["b30"], 500, places=2)
		row = self.aging(d(50))
		self.assertAlmostEqual(row["d1_30"], 500, places=2)
		self.assertAlmostEqual(row["overdue"], 500, places=2)
		self.assertEqual(row["oldest_overdue_due_date"], d(45))
		row = self.aging(d(45 + 95))
		self.assertAlmostEqual(row["d90p"], 500, places=2)

	def test_aging_buckets_sum_to_the_balance_with_unapplied_credit(self):
		self.terms(days=30)
		first, f1 = self.bill(500)
		_second, f2 = self.bill(400, room=self.room2)
		# pays the first bill and 100 more that is kept as credit
		ledger.city_ledger_settle(self.account, 600,
		                          allocations=[{"folio": f1, "amount": 500}])
		row = self.aging(d(40))
		self.assertAlmostEqual(row["unapplied_credit"], 100, places=2)
		self.assertAlmostEqual(float(row["balance"]), 300, places=2)
		buckets = sum(row[k] for k in ledger.DUE_BUCKETS)
		self.assertAlmostEqual(buckets, 300, places=2)
		self.assertAlmostEqual(row["overdue"], 300, places=2)
		legacy = sum(row[k] for k in ledger.INVOICE_AGE_BUCKETS)
		self.assertAlmostEqual(legacy, 300, places=2)
		view = ledger.city_ledger_account(self.account)
		self.assertEqual([r["folio"] for r in view["open_items"]], [f2])
		self.assertEqual(view["open_items"][0]["due_date"], d(30))

	def test_backfill_patch_sets_due_dates_and_is_idempotent(self):
		from kamra.patches.v42 import backfill_city_ledger_due_dates as patch_mod
		self.terms(days=20)
		self.bill(500)
		entry = frappe.db.get_value("City Ledger Entry",
		                            {"account": self.account, "kind": "Invoice"})
		frappe.db.set_value("City Ledger Entry", entry,
		                    {"due_date": None, "posting_date": d(-60)})
		# without a stored due date the aging still dates it from the terms
		self.assertEqual(ledger.city_ledger_open_folios(self.account)[0]["due_date"],
		                 d(-40))
		patch_mod.execute()
		self.assertEqual(str(frappe.db.get_value("City Ledger Entry", entry,
		                                         "due_date")), d(-40))
		# a re-run changes nothing, even after the terms change
		self.terms(days=90)
		patch_mod.execute()
		self.assertEqual(str(frappe.db.get_value("City Ledger Entry", entry,
		                                         "due_date")), d(-40))

	# the check -------------------------------------------------------------

	def test_check_reports_limit_and_overdue(self):
		self.terms(limit=1000, days=30)
		self.bill(800)
		res = credit.check_company_credit(self.company, PROP_A, 300)
		self.assertFalse(res["ok"])
		self.assertAlmostEqual(res["over_limit_by"], 100, places=2)
		self.assertEqual(res["overdue_amount"], 0)
		self.assertEqual(len(res["reasons"]), 1)
		# the account name works as well as the company
		self.assertTrue(credit.check_company_credit(self.account, PROP_A, 200)["ok"])
		with patch("kamra.ledger.nowdate", return_value=d(31)):
			res = credit.check_company_credit(self.company, PROP_A, 0)
		self.assertAlmostEqual(res["overdue_amount"], 800, places=2)
		self.assertFalse(res["ok"])

	def test_zero_limit_means_no_limit(self):
		self.terms(limit=0)
		self.bill(500000)
		self.assertTrue(credit.check_company_credit(self.company, PROP_A, 10 ** 7)["ok"])

	def test_grace_days(self):
		self.terms(days=30)
		self.bill(500)
		set_setting(PROP_A, "credit_overdue_grace_days", 10)
		with patch("kamra.ledger.nowdate", return_value=d(38)):
			self.assertTrue(credit.check_company_credit(self.company, PROP_A)["ok"])
		with patch("kamra.ledger.nowdate", return_value=d(41)):
			res = credit.check_company_credit(self.company, PROP_A)
		self.assertFalse(res["ok"])
		self.assertAlmostEqual(res["overdue_amount"], 500, places=2)

	def test_policy_off_checks_nothing(self):
		self.terms(limit=100)
		self.bill(500)
		set_setting(PROP_A, "credit_control", "Off")
		res = credit.check_company_credit(self.company, PROP_A, 500)
		self.assertTrue(res["ok"])
		self.assertEqual(res["policy"], "off")

	# enforcement at check-out ------------------------------------------------

	def test_over_limit_checkout_warns_under_warn(self):
		self.terms(limit=100)
		res, company_folio = self.corporate_stay()
		out = api.check_out(res.name)
		self.assertEqual(frappe.db.get_value("Reservation", res.name, "status"),
		                 "Checked Out")
		self.assertEqual(out["credit_warnings"][0]["company"], self.company)
		self.assertIn("credit limit", out["credit_warnings"][0]["reasons"][0])
		self.assertTrue(frappe.db.exists("City Ledger Entry",
		                                 {"folio": company_folio, "kind": "Invoice"}))
		self.assertTrue(self.logs("credit_warning"))

	def test_over_limit_checkout_is_blocked_under_block(self):
		self.terms(limit=100)
		set_setting(PROP_A, "credit_control", "Block")
		res, company_folio = self.corporate_stay()
		owed = _balance(company_folio)
		with self.assertRaises(credit.CreditBlocked) as ctx:
			api.check_out(res.name)
		self.assertIn("CREDIT_BLOCKED", str(ctx.exception))
		# nothing moved
		self.assertEqual(frappe.db.get_value("Reservation", res.name, "status"),
		                 "Checked In")
		self.assertAlmostEqual(_balance(company_folio), owed, places=2)
		self.assertFalse(frappe.db.exists("City Ledger Entry",
		                                  {"folio": company_folio}))

	def test_finance_override_is_logged_with_reason(self):
		ensure_user(FINANCE, ["Finance", "Front Desk"])
		self.terms(limit=100)
		set_setting(PROP_A, "credit_control", "Block")
		res, company_folio = self.corporate_stay()
		owed = _balance(company_folio)
		frappe.set_user(FINANCE)  # nosemgrep: frappe-setuser -- persona: Finance overrides the block
		with self.assertRaises(credit.CreditBlocked):
			api.check_out(res.name, credit_override_reason="   ")
		out = api.check_out(res.name, credit_override_reason="GM approved, PO 4411")
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- back to the fixture user
		self.assertTrue(out["credit_warnings"][0]["overridden"])
		logs = self.logs("credit_override")
		self.assertEqual(len(logs), 1)
		self.assertEqual(logs[0].approver, FINANCE)
		self.assertEqual(logs[0].reference_name, res.name)
		self.assertIn("GM approved, PO 4411", logs[0].rationale)
		snap = json.loads(logs[0].after_snapshot)
		self.assertAlmostEqual(snap["amount"], owed, places=2)
		self.assertEqual(snap["by"], FINANCE)

	def test_front_desk_cannot_override(self):
		ensure_user(DESK, ["Front Desk"])
		self.terms(limit=100)
		set_setting(PROP_A, "credit_control", "Block")
		res, _company_folio = self.corporate_stay()
		frappe.set_user(DESK)  # nosemgrep: frappe-setuser -- persona: Front Desk may not override
		with self.assertRaises(frappe.PermissionError):
			api.check_out(res.name, credit_override_reason="guest is a VIP")
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- back to the fixture user
		self.assertFalse(self.logs("credit_override"))

	def test_an_agent_can_never_override(self):
		self.terms(limit=100)
		set_setting(PROP_A, "credit_control", "Block")
		res, _company_folio = self.corporate_stay()
		frappe.flags.kamra_agent_call = "MCP"
		try:
			# even as Administrator: an agent call gets the reason, not a pass
			with self.assertRaises(frappe.PermissionError) as ctx:
				api.check_out(res.name, credit_override_reason="agent says ok")
			self.assertIn("agent", str(ctx.exception))
			with self.assertRaises(credit.CreditBlocked):
				api.check_out(res.name)
		finally:
			frappe.flags.kamra_agent_call = None
		self.assertFalse(self.logs("credit_override"))

	def test_city_ledger_transfer_endpoint_is_checked(self):
		self.terms(limit=100)
		set_setting(PROP_A, "credit_control", "Block")
		res = make_reservation(PROP_A, self.rt, d(-1), d(1),
		                       status="Checked In", room=self.room)
		folio = guest_folio(res.name)
		api.add_folio_charge(folio, "Misc", "UT bill", 500, gst_rate=0)
		with self.assertRaises(credit.CreditBlocked):
			ledger.city_ledger_transfer(folio, self.company)
		out = ledger.city_ledger_transfer(folio, self.company,
		                                  credit_override_reason="UT approved")
		self.assertTrue(out["credit"]["overridden"])
		self.assertEqual(len(self.logs("credit_override")), 1)

	def test_checkout_preview_matches_the_checkout(self):
		self.terms(limit=100)
		set_setting(PROP_A, "credit_control", "Block")
		res, company_folio = self.corporate_stay()
		prev = credit.checkout_credit_preview(res.name)
		self.assertTrue(prev["blocked"])
		self.assertEqual(prev["checks"][0]["folios"], [company_folio])
		self.assertAlmostEqual(prev["checks"][0]["amount"], _balance(company_folio),
		                       places=2)
		self.assertTrue(prev["can_override"])  # Administrator

	# enforcement at booking ---------------------------------------------------

	def test_booking_on_company_billing_is_checked(self):
		self.terms(limit=100)
		set_setting(PROP_A, "credit_control", "Block")
		args = dict(property=PROP_A, room_type=self.rt, check_in_date=d(5),
		            check_out_date=d(7), guest_name="UT Credit Guest",
		            phone="+91 90000 23801", company=self.company,
		            booking_type="Corporate")
		before = frappe.db.count("Reservation", {"property": PROP_A})
		with self.assertRaises(credit.CreditBlocked):
			api.create_booking(**args)
		# the refused booking is rolled back - no room held
		self.assertEqual(frappe.db.count("Reservation", {"property": PROP_A}), before)
		out = api.create_booking(**args, credit_override_reason="UT approved")
		self.assertTrue(out["credit_warning"]["overridden"])
		set_setting(PROP_A, "credit_control", "Warn")
		out = api.create_booking(**{**args, "phone": "+91 90000 23802",
		                            "guest_name": "UT Credit Guest 2"})
		self.assertFalse(out["credit_warning"]["overridden"])

	def test_settings_registry_has_the_credit_policy(self):
		from kamra.settings import SETTINGS, get_setting
		self.assertEqual(SETTINGS["credit_control"][0].id, "finance")
		self.assertEqual(get_setting(PROP_A, "credit_control"), "Warn")
		self.assertEqual(get_setting(PROP_A, "default_credit_days"), 30)
		self.assertEqual(get_setting(PROP_A, "credit_overdue_grace_days"), 0)

	def test_credit_terms_endpoint_role_gate(self):
		ensure_user(DESK, ["Front Desk"])
		frappe.set_user(DESK)  # nosemgrep: frappe-setuser -- persona: Front Desk can't change terms
		with self.assertRaises(frappe.PermissionError):
			credit.set_company_credit_terms(self.company, PROP_A, 5000, 45)
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- back to the fixture user
		out = credit.set_company_credit_terms(self.company, PROP_A, 5000, 45, 0)
		self.assertEqual((out["credit_limit"], out["credit_days"],
		                  out["use_default_credit_days"], out["effective_credit_days"]),
		                 (5000, 45, False, 45))
		out = credit.set_company_credit_terms(self.company, PROP_A, 5000, 0, 0)
		self.assertEqual(out["effective_credit_days"], 0)  # due on receipt
		out = credit.set_company_credit_terms(self.company, PROP_A,
		                                      use_default_credit_days=1)
		self.assertEqual(out["effective_credit_days"], 30)
		self.assertTrue(self.logs("credit_terms_changed"))
