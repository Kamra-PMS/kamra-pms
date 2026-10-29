"""Accounts payable (kamra.payables) and the management books
(kamra.books): bill lifecycle, who may do what, property scope, aging,
the five-day cash view, the P&L and the balance sheet."""

from __future__ import annotations

import frappe

from kamra import books, payables
from kamra.tests.audit_fixtures import (
	TODAY, AuditTestCase, d, ensure_user, make_property,
)

# own properties: other suites lock the shared "UT Audit" rows
PROP_A, PROP_B = "UT Books A", "UT Books B"

FIN = "ut-books-fin@example.com"
FD = "ut-books-fd@example.com"
ADMIN = "ut-books-admin@example.com"


class TestFinanceBooks(AuditTestCase):
	properties = (PROP_A, PROP_B)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.payables", "kamra.books", "kamra.business_date")
		make_property(PROP_A)
		make_property(PROP_B)
		for dt in ("Vendor Bill", "Vendor", "Petty Cash Voucher"):
			frappe.db.delete(dt, {"property": ("in", (PROP_A, PROP_B))})
		self.vendor = payables.save_vendor(
			PROP_A, "UT Grocer", expense_category="Food & Beverage Supplies",
			payment_terms_days=15)["vendor"]

	def bill(self, amount=1000, **kw):
		kw.setdefault("bill_date", d(-1))
		return payables.create_vendor_bill(PROP_A, self.vendor, amount=amount, **kw)

	def test_bill_lifecycle(self):
		b = self.bill(1000, tax_rate=18, bill_number="G-1")
		self.assertEqual((b["tax_amount"], b["total"]), (180, 1180))
		self.assertEqual(b["due_date"], d(14))
		self.assertEqual(b["expense_category"], "Food & Beverage Supplies")
		self.assertEqual(b["status"], "Awaiting Approval")
		with self.assertRaises(frappe.ValidationError):
			self.bill(5, bill_number="G-1")  # same supplier bill twice
		with self.assertRaises(frappe.ValidationError):
			payables.pay_vendor_bill(b["name"], 100)  # not approved yet
		payables.approve_vendor_bill(b["name"])
		r = payables.pay_vendor_bill(b["name"], 500, reference="NEFT 1")
		self.assertEqual((r["status"], r["outstanding"]), ("Part Paid", 680))
		with self.assertRaises(frappe.ValidationError):
			payables.pay_vendor_bill(b["name"], 681)
		with self.assertRaises(frappe.ValidationError):
			payables.cancel_vendor_bill(b["name"], "typo")
		r = payables.pay_vendor_bill(b["name"], 680)
		self.assertEqual((r["status"], r["outstanding"]), ("Paid", 0))
		# a bill by vendor name works, a clean one cancels
		c = payables.create_vendor_bill(PROP_A, "UT Grocer", d(0), 50)
		self.assertEqual(payables.cancel_vendor_bill(c["name"], "typo")["status"],
		                 "Cancelled")

	def test_roles_and_property_scope(self):
		b = self.bill()
		ensure_user(FIN, ["Finance"])
		ensure_user(FD, ["Front Desk"])
		ensure_user(ADMIN, ["Hotel Admin"])
		# the money and the approval only move through kamra.payables: Desk
		# and /api/resource can't approve, pay, re-price or delete a bill
		for user in (FIN, ADMIN):
			for ptype in ("write", "create", "delete"):
				self.assertFalse(frappe.has_permission("Vendor Bill", ptype, user=user),
				                 (user, ptype))
		frappe.set_user(FD)
		with self.assertRaises(frappe.PermissionError):
			self.bill()
		frappe.set_user(FIN)
		self.bill(10)  # Finance enters
		with self.assertRaises(frappe.PermissionError):
			payables.approve_vendor_bill(b["name"])
		frappe.set_user("Administrator")
		frappe.db.delete("User Permission", {"user": ADMIN})
		frappe.get_doc({"doctype": "User Permission", "user": ADMIN,
		                "allow": "Property", "for_value": PROP_B}).insert(
			ignore_permissions=True)
		frappe.clear_cache(user=ADMIN)
		frappe.set_user(ADMIN)
		with self.assertRaises(frappe.PermissionError):
			payables.approve_vendor_bill(b["name"])  # PROP_A's bill
		with self.assertRaises(frappe.PermissionError):
			books.profit_and_loss(PROP_A, d(-30), d(0))

	def test_aging(self):
		for days_late in (-3, 5, 45, 100):
			b = self.bill(100, bill_date=d(-120), due_date=d(-days_late))
			payables.approve_vendor_bill(b["name"])
		t = payables.payables_aging(PROP_A)["totals"]
		self.assertEqual((t["not_due"], t["d1_30"], t["d31_60"], t["d61_90"], t["d90p"]),
		                 (100, 100, 100, 0, 100))
		self.assertEqual((t["overdue"], t["balance"]), (300, 400))
		v = payables.vendors(PROP_A)["vendors"][0]
		self.assertEqual((v["balance"], v["open_bills"]), (400, 4))

	def test_cash_forecast(self):
		self.bill(300, bill_date=d(-30), due_date=d(-2))  # overdue: counted today
		self.bill(200, due_date=d(2))
		self.bill(999, due_date=d(9))  # outside five days
		acc = frappe.get_doc({"doctype": "City Ledger Account", "property": PROP_A,
		                      "company": None, "account_number": "UT-BOOKS"})
		acc.flags.ignore_mandatory = True
		acc.insert(ignore_permissions=True)
		e = frappe.get_doc({"doctype": "City Ledger Entry", "account": acc.name,
		                    "property": PROP_A, "posting_date": d(-20), "kind": "Invoice",
		                    "folio": "UT-FOLIO-BOOKS", "due_date": d(1), "debit": 700})
		e.flags.ignore_links = True
		e.insert(ignore_permissions=True)
		f = books.cash_forecast(PROP_A, opening=1000)
		self.assertEqual([x["date"] for x in f["days"]], [d(i) for i in range(5)])
		self.assertEqual([x["money_out"] for x in f["days"]], [300, 0, 200, 0, 0])
		self.assertEqual(f["days"][1]["company_bills"], 700)
		self.assertEqual((f["opening_source"], f["closing"]), ("entered", 1200))
		self.assertEqual(f["overdue_out"], 300)

	def test_pnl_and_balance_sheet(self):
		folio = frappe.get_doc({
			"doctype": "Folio", "property": PROP_A, "status": "Open",
			"folio_type": "Guest", "charges": [
				{"posting_date": d(0), "charge_type": "Room", "description": "Night",
				 "qty": 1, "rate": 4000, "amount": 4000, "gst_rate": 12},
				{"posting_date": d(0), "charge_type": "Discount", "description": "Promo",
				 "qty": 1, "rate": -400, "amount": -400},
				{"posting_date": d(0), "charge_type": "Laundry", "description": "Bag",
				 "qty": 1, "rate": 300, "amount": 300},
				{"posting_date": d(0), "charge_type": "Allowance", "description": "Sorry",
				 "qty": 1, "rate": -100, "amount": -100},
				# a restaurant bill charged to the room: its POS Order counts it
				{"posting_date": d(0), "charge_type": "Food & Beverage",
				 "description": "Cafe: Tea x1 (ORD-2031-00001)", "qty": 1,
				 "rate": 250, "amount": 250},
				{"posting_date": d(0), "charge_type": "Room Levy", "description": "Levy",
				 "qty": 1, "rate": 50, "amount": 50},
			]})
		folio.flags.ignore_links = True
		folio.insert(ignore_permissions=True)
		b = self.bill(1000, tax_rate=10, bill_date=d(0))
		payables.approve_vendor_bill(b["name"])
		payables.pay_vendor_bill(b["name"], 400)
		pc = frappe.get_doc({"doctype": "Petty Cash Voucher", "property": PROP_A,
		                     "session": "UT-SESSION", "voucher_date": d(0),
		                     "payee": "Plumber", "category": "Maintenance",
		                     "amount": 150, "reason": "Tap", "status": "Posted"})
		pc.flags.ignore_links = True
		pc.insert(ignore_permissions=True)

		p = books.profit_and_loss(PROP_A, d(0), d(0))
		rev = {r["key"]: r["amount"] for r in p["revenue"]}
		self.assertEqual(rev, {"rooms": 3600, "fnb": 0, "banquets": 0,
		                       "other": 300, "allowances": -100})
		self.assertEqual(p["revenue_total"], 3800)
		self.assertEqual(p["expense_total"], 1150)
		self.assertEqual(p["net"], 2650)
		self.assertEqual(p["tax_on_bills"], 100)

		bs = books.balance_sheet(PROP_A)
		pay = {x["key"]: x["amount"] for x in bs["liabilities"]}["payables"]
		self.assertEqual(pay, 700)
		self.assertEqual(books.payables_at(PROP_A, d(-1)), 0)
		with self.assertRaises(frappe.ValidationError):
			books.balance_sheet(PROP_A, d(1))

	def test_forecast_deposit_and_departure_count_once(self):
		from kamra.tests.audit_fixtures import make_reservation, make_room_type
		frappe.db.set_value("Property", PROP_A, "deposit_pct", 30)
		frappe.clear_document_cache("Property", PROP_A)
		rt = make_room_type(PROP_A)
		res = make_reservation(PROP_A, rt, d(1), d(3))
		frappe.db.set_value("Reservation", res.name,
		                    {"amount_after_tax": 3000, "advance_paid": 0})
		f = books.cash_forecast(PROP_A, opening=0)
		self.assertEqual(f["days"][1]["deposits"], 900)
		self.assertEqual(f["days"][3]["departures"], 2100)
		self.assertEqual(f["closing"], 3000)
