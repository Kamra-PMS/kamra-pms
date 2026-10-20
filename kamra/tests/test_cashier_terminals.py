"""Many tills per property: terminals, who holds which, the cash office,
and which station prints bills as against KOTs.

Everything here is additive. A property that never adds a terminal behaves
as before: one Default till per user. The first test class pins that."""

from __future__ import annotations

from unittest.mock import patch

import frappe

from kamra import cashier, printing
from kamra.tests.audit_fixtures import (
	PROP_A,
	PROP_B,
	TODAY,
	AuditTestCase,
	ensure_user,
	make_property,
)


class TillTestCase(AuditTestCase):
	properties = (PROP_A, PROP_B)
	ONE = "ut.terminals.one@test.local"
	TWO = "ut.terminals.two@test.local"
	FIN = "ut.terminals.fin@test.local"

	def setUp(self):
		super().setUp()
		self.at(TODAY)
		make_property(PROP_A, business_date=TODAY)
		make_property(PROP_B, business_date=TODAY)
		for u, roles in ((self.ONE, ["Front Desk"]), (self.TWO, ["Front Desk"]),
		                 (self.FIN, ["Finance"])):
			ensure_user(u, roles)
		self.outlet = frappe.db.get_value(
			"POS Outlet", {"property": PROP_A, "outlet_name": "UT Till Bar"}) or \
			frappe.get_doc({"doctype": "POS Outlet", "property": PROP_A,
			                "outlet_name": "UT Till Bar", "outlet_type": "Bar",
			                "gst_rate": 5}).insert(ignore_permissions=True).name

	def terminal(self, name, kind="Front Desk", **kw):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- fixture
		return cashier.save_terminal(PROP_A, name, kind=kind, **kw)["name"]

	def as_user(self, user):
		frappe.set_user(user)  # nosemgrep: frappe-setuser -- the cashier persona


class DefaultTillUnchangedTestCase(TillTestCase):
	"""No terminals configured: nothing new is required or changes."""

	def test_open_without_a_terminal_is_the_default_till(self):
		self.as_user(self.ONE)
		sess = cashier.open_session(PROP_A, 500)
		self.assertFalse(sess.get("cashier_terminal"))
		self.assertEqual(cashier.open_session(PROP_A, 500)["name"], sess["name"])
		self.assertEqual(cashier.require_open_session(PROP_A), sess["name"])

	def test_each_user_has_their_own_default_till(self):
		self.as_user(self.ONE)
		a = cashier.open_session(PROP_A, 100)["name"]
		self.as_user(self.TWO)
		b = cashier.open_session(PROP_A, 100)["name"]
		self.assertNotEqual(a, b)

	def test_board_lists_default_even_with_no_terminals(self):
		self.as_user(self.ONE)
		cashier.open_session(PROP_A, 100)
		board = cashier.tills_board(PROP_A)
		self.assertEqual([t["terminal_name"] for t in board["tills"]], ["Default"])
		self.assertEqual(len(board["tills"][0]["sessions"]), 1)


class TerminalSessionsTestCase(TillTestCase):

	def test_a_terminal_has_one_open_session(self):
		bar = self.terminal("Bar 1", "Bar", outlet=self.outlet, default_float=300)
		self.as_user(self.ONE)
		sess = cashier.open_session(PROP_A, cashier_terminal=bar)
		self.assertEqual(sess["opening_float"], 300)  # the terminal's default float
		self.assertEqual(sess["outlet"], self.outlet)
		self.as_user(self.TWO)
		with self.assertRaises(frappe.ValidationError):
			cashier.open_session(PROP_A, cashier_terminal=bar)
		# the holder opening it again just gets it back
		self.as_user(self.ONE)
		self.assertEqual(cashier.open_session(PROP_A, cashier_terminal=bar)["name"], sess["name"])

	def test_one_user_can_hold_two_terminals_and_the_default(self):
		a, b = self.terminal("Lobby"), self.terminal("Pool Bar", "Bar", outlet=self.outlet)
		self.as_user(self.ONE)
		s1 = cashier.open_session(PROP_A, 0, cashier_terminal=a)["name"]
		s2 = cashier.open_session(PROP_A, 0, cashier_terminal=b)["name"]
		s0 = cashier.open_session(PROP_A, 0)["name"]
		self.assertEqual(len({s0, s1, s2}), 3)
		cur = cashier.current_session(PROP_A)
		self.assertEqual(cur["name"], s0)  # newest
		self.assertCountEqual(cur["open_sessions"], [s0, s1, s2])
		self.assertEqual(cashier.current_session(PROP_A, cashier_terminal=a)["name"], s1)

	def test_money_follows_the_till_of_the_outlet(self):
		lobby = self.terminal("Lobby")
		bar = self.terminal("Bar", "Bar", outlet=self.outlet)
		self.as_user(self.ONE)
		s_bar = cashier.open_session(PROP_A, 0, cashier_terminal=bar)["name"]
		s_lobby = cashier.open_session(PROP_A, 0, cashier_terminal=lobby)["name"]  # newest
		# a bar bill lands on the bar till although the lobby one was opened last
		self.assertEqual(cashier.require_open_session(PROP_A, self.outlet), s_bar)
		self.assertEqual(cashier.require_open_session(PROP_A), s_lobby)
		cashier.record_cashier_txn(PROP_A, "Payment", "Cash", 250, outlet=self.outlet)
		self.assertEqual(frappe.db.get_value(
			"Cashier Transaction", {"session": s_bar}, "outlet"), self.outlet)

	def test_validation(self):
		other = frappe.get_doc({"doctype": "Cashier Terminal", "property": PROP_B,
		                        "terminal_name": "Elsewhere"}).insert(ignore_permissions=True).name
		self.as_user(self.ONE)
		with self.assertRaises(frappe.ValidationError):
			cashier.open_session(PROP_A, cashier_terminal=other)
		off = self.terminal("Old")
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- fixture
		cashier.save_terminal(PROP_A, "Old", disabled=1, name=off)
		self.as_user(self.ONE)
		with self.assertRaises(frappe.ValidationError):
			cashier.open_session(PROP_A, cashier_terminal=off)

	def test_front_desk_cannot_add_tills(self):
		self.as_user(self.ONE)
		with self.assertRaises(frappe.PermissionError):
			cashier.save_terminal(PROP_A, "Mine")


class CashOfficeTestCase(TillTestCase):

	def test_drop_is_received_and_banked(self):
		office = self.terminal("Safe", "Cash Office")
		lobby = self.terminal("Lobby")
		self.as_user(self.ONE)
		sess = cashier.open_session(PROP_A, 1000, cashier_terminal=lobby)["name"]
		cashier.cash_drop(PROP_A, 400, to_terminal=office)
		pending = cashier.tills_board(PROP_A)["pending_transfers"]
		self.assertEqual(len(pending), 1)
		self.assertEqual(frappe.db.get_value("Cashier Session", sess, "drops"), 400)
		board_safe = [t for t in cashier.tills_board(PROP_A)["tills"] if t["name"] == office][0]["safe"]
		self.assertEqual((board_safe["balance"], board_safe["in_transit"]), (0, 400))
		# the dropper cannot also receive it
		with self.assertRaises(frappe.ValidationError):
			cashier.receive_transfer(pending[0]["name"])
		self.as_user(self.FIN)
		self.assertEqual(cashier.receive_transfer(pending[0]["name"])["safe"]["balance"], 400)
		with self.assertRaises(frappe.ValidationError):
			cashier.receive_transfer(pending[0]["name"])  # already received
		with self.assertRaises(frappe.ValidationError):
			cashier.bank_deposit(office, 500)  # more than the safe holds
		self.assertEqual(cashier.bank_deposit(office, 150)["safe"]["balance"], 250)

	def test_drop_to_a_till_that_is_not_a_cash_office_is_refused(self):
		lobby = self.terminal("Lobby")
		self.as_user(self.ONE)
		cashier.open_session(PROP_A, 100)
		with self.assertRaises(frappe.ValidationError):
			cashier.cash_drop(PROP_A, 10, to_terminal=lobby)

	def test_plain_drop_still_works_without_a_cash_office(self):
		self.as_user(self.ONE)
		cashier.open_session(PROP_A, 100)
		cashier.cash_drop(PROP_A, 30, "safe")
		self.assertEqual(frappe.db.count("Cash Transfer", {"property": PROP_A}), 0)


class VarianceTestCase(TillTestCase):

	def close(self, counted, tolerance):
		self.as_user(self.ONE)
		sess = cashier.open_session(PROP_A, 1000)["name"]
		with patch("kamra.cashier.get_setting", return_value=tolerance):
			return cashier.close_session(sess, counted_cash=counted)

	def test_within_tolerance_is_not_flagged(self):
		self.assertFalse(self.close(995, 10).get("variance_status"))

	def test_over_tolerance_is_flagged_but_still_closes(self):
		out = self.close(900, 10)
		self.assertEqual(out["status"], "Closed")
		self.assertEqual(out["variance_status"], "Needs Review")
		self.assertEqual(len(cashier.tills_board(PROP_A)["variance_review"]), 1)

	def test_tolerance_zero_means_off(self):
		self.assertFalse(self.close(100, 0).get("variance_status"))

	def test_manager_approves_not_the_cashier(self):
		out = self.close(900, 10)
		with self.assertRaises((frappe.ValidationError, frappe.PermissionError)):
			cashier.approve_variance(out["name"])
		self.as_user(self.FIN)
		cashier.approve_variance(out["name"], "recounted, till was short")
		self.assertEqual(frappe.db.get_value("Cashier Session", out["name"], "variance_status"),
		                 "Approved")


class PrinterRolesTestCase(TillTestCase):
	"""Printing a bill and printing a KOT are different jobs on different
	stations."""

	def printer(self, name, **kw):
		return frappe.get_doc(dict({
			"doctype": "Kitchen Printer", "property": PROP_A, "printer_name": name,
			"connection": "Print station",
		}, **kw)).insert(ignore_permissions=True).name

	def test_an_existing_printer_is_kot_only(self):
		p = self.printer("UT Old Kitchen",
		                 routes=[{"outlet": self.outlet, "prep_station": ""}])
		rows = {r["name"]: r for r in printing._printers(PROP_A)}
		self.assertEqual((rows[p]["prints_kots"], rows[p]["prints_bills"]), (1, 0))
		self.assertIsNone(printing._bill_printer(PROP_A, self.outlet, None))

	def test_bill_goes_to_the_till_printer_not_a_kot_printer(self):
		kot = self.printer("UT Pass", routes=[{"outlet": self.outlet, "prep_station": ""}])
		bill = self.printer("UT Receipt", prints_kots=0, prints_bills=1)
		term = self.terminal("Bar", "Bar", outlet=self.outlet, bill_printer=bill)
		self.assertEqual(printing._bill_printer(PROP_A, self.outlet, term)["name"], bill)
		self.assertNotEqual(printing._bill_printer(PROP_A, self.outlet, term)["name"], kot)

	def test_a_bill_only_printer_never_takes_a_kot(self):
		bill = self.printer("UT Receipt2", prints_kots=0, prints_bills=1,
		                    routes=[{"outlet": self.outlet, "prep_station": ""}])
		self.assertNotIn(bill, [p["name"] for p in printing._printers(PROP_A) if p["prints_kots"]])

	def test_bill_printer_falls_back_to_the_one_routed_to_the_outlet(self):
		bill = self.printer("UT Receipt3", prints_kots=0, prints_bills=1,
		                    routes=[{"outlet": self.outlet, "prep_station": ""}])
		self.assertEqual(printing._bill_printer(PROP_A, self.outlet, None)["name"], bill)

	def test_terminal_refuses_a_kot_only_printer_as_its_bill_printer(self):
		kot = self.printer("UT Pass2")
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- fixture
		with self.assertRaises(frappe.ValidationError):
			cashier.save_terminal(PROP_A, "Bar", bill_printer=kot)

	def test_bill_escpos_renders(self):
		data = printing.escpos({"kind": "Bill", "property_name": "UT", "outlet_name": "Bar",
		                        "items": [{"item_name": "Beer", "qty": 2, "amount": 400}],
		                        "subtotal": 400, "grand_total": 420,
		                        "tax_parts": [{"label": "GST", "rate": 5, "amount": 20}]})
		self.assertIn(b"BILL", data)
		self.assertIn(b"TOTAL", data)
		self.assertIn(b"420.00", data)


class SiteInfoVersionTestCase(TillTestCase):
	"""The login screen and the nav footer quote what site_info says."""

	def test_site_info_carries_the_running_version(self):
		from kamra import __version__
		from kamra.public_api import site_info
		info = site_info()
		self.assertEqual(info["version"], __version__)
		self.assertIsNone(info["channel"])

	def test_channel_and_build_come_from_site_config(self):
		from kamra.public_api import site_info
		with patch.dict(frappe.conf, {"kamra_channel": "nightly", "kamra_build": "8f32098abcdef0"}):
			info = site_info()
		self.assertEqual((info["channel"], info["build"]), ("nightly", "8f32098abcde"))
