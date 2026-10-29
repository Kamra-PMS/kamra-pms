"""Undoing a checkout made by mistake, the same business day.

api.reinstate_checkout: the invoice is cancelled into the register, a
company bill leaves the company's account, the guest is in house in the
same room, and it is refused after the night audit, when the room is
taken, or when the company has paid.
"""

from __future__ import annotations

import frappe

from kamra import api, ledger
from kamra import folio as folio_mod
from kamra.tests import test_folio_leaks as leaks
from kamra.tests.audit_fixtures import (
	PROP_A,
	TODAY,
	AuditTestCase,
	d,
	guest_folio,
	make_property,
	make_reservation,
	make_room,
	make_room_type,
)


class ReinstateCheckoutTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")
		if not frappe.db.exists("Corporate Account", leaks.COMPANY):
			frappe.get_doc({"doctype": "Corporate Account",
			                "company_name": leaks.COMPANY}).insert(ignore_permissions=True)
		corp = frappe.get_doc("Corporate Account", leaks.COMPANY)
		corp.credit_allowed = 1
		corp.set("billing_rules", [{"charge_type": "Room", "pay_by": "Company"}])
		corp.save(ignore_permissions=True)
		self.company = corp.name

	def guest_stay_out(self):
		res = make_reservation(PROP_A, self.rt, d(-1), d(1), status="Checked In",
		                       room=self.room)
		folio_mod.post_remaining_nights(res)
		folio = guest_folio(res.name)
		api.add_folio_payment(folio, "Cash", leaks._balance(folio))
		api.check_out(res.name)
		number = folio_mod.close_folio(folio)
		return res, folio, number

	def test_guest_stay_comes_back_in_house(self):
		res, folio, number = self.guest_stay_out()
		self.assertEqual(frappe.db.get_value("Room", self.room, "occupancy_status"), "Vacant")
		out = api.reinstate_checkout(res.name, "Guest came back, checked out by mistake")
		self.assertEqual(out["cancelled_invoices"], [number])
		self.assertEqual(frappe.db.get_value("Reservation", res.name,
		                                     ["status", "actual_check_out"]),
		                 ("Checked In", None))
		self.assertEqual(frappe.db.get_value("Folio", folio, ["status", "invoice_number"]),
		                 ("Open", None))
		self.assertTrue(frappe.db.exists("Cancelled Invoice", {"invoice_number": number}))
		self.assertEqual(frappe.db.get_value("Room", self.room, "occupancy_status"), "Occupied")
		self.assertFalse(frappe.get_all("Housekeeping Task", filters={
			"reservation": res.name, "task_type": "Checkout Clean", "status": "Pending"}))
		# and the guest can check out again later, with a new invoice
		api.check_out(res.name)
		self.assertNotEqual(folio_mod.close_folio(folio), number)

	def test_company_bill_leaves_the_company_account(self):
		res = make_reservation(PROP_A, self.rt, d(-1), d(1), status="Checked In",
		                       room=self.room, booking_type="Corporate", company=self.company)
		folio_mod.post_remaining_nights(res)
		account_before = frappe.db.get_value("City Ledger Account",
		                                     {"company": self.company, "property": PROP_A},
		                                     "balance") or 0
		api.check_out(res.name)
		company = frappe.db.get_value("Folio", {"reservation": res.name,
		                                        "folio_type": "Company"})
		owed = frappe.db.get_value("Folio", company, "grand_total")
		folio_mod.close_folio(company)
		out = api.reinstate_checkout(res.name, "Wrong guest checked out")
		self.assertAlmostEqual(out["from_city_ledger"], float(owed), 2)
		account = frappe.db.get_value("City Ledger Account",
		                              {"company": self.company, "property": PROP_A},
		                              ["name", "balance"], as_dict=True)
		self.assertAlmostEqual(float(account.balance), float(account_before), 2)
		self.assertAlmostEqual(leaks._balance(company), float(owed), 2)
		self.assertAlmostEqual(leaks._net(company, "AR"), 0, 2)
		self.assertAlmostEqual(leaks._net(company, "Guest"), leaks._balance(company), 2)
		# checking out again bills the company once, not twice
		api.check_out(res.name)
		self.assertAlmostEqual(float(frappe.db.get_value(
			"City Ledger Account", account.name, "balance")),
			float(account_before) + float(owed), 2)
		# and a second mistake the same day can be undone too
		folio_mod.close_folio(company)
		api.reinstate_checkout(res.name, "Again")
		self.assertAlmostEqual(float(frappe.db.get_value(
			"City Ledger Account", account.name, "balance")), float(account_before), 2)

	def test_refused_after_the_night_audit(self):
		res, _folio, _n = self.guest_stay_out()
		frappe.db.set_value("Reservation", res.name, "actual_check_out", "2000-01-01 10:00:00")
		frappe.get_doc({"doctype": "Night Audit Run", "property": PROP_A,
		                "business_date": TODAY}).insert(ignore_permissions=True,
		                                                ignore_mandatory=True)
		with self.assertRaisesRegex(frappe.ValidationError, "night audit"):
			api.reinstate_checkout(res.name, "too late")

	def test_refused_when_the_room_is_taken(self):
		res, _folio, _n = self.guest_stay_out()
		make_reservation(PROP_A, self.rt, TODAY, d(2), status="Checked In", room=self.room)
		with self.assertRaises(frappe.ValidationError):
			api.reinstate_checkout(res.name, "room gone")
		self.assertEqual(frappe.db.get_value("Reservation", res.name, "status"), "Checked Out")

	def test_refused_when_the_company_has_paid(self):
		res = make_reservation(PROP_A, self.rt, d(-1), d(1), status="Checked In",
		                       room=self.room, booking_type="Corporate", company=self.company)
		folio_mod.post_remaining_nights(res)
		api.check_out(res.name)
		account = frappe.db.get_value("City Ledger Account",
		                              {"company": self.company, "property": PROP_A}, "name")
		ledger.city_ledger_settle(account, 100)
		with self.assertRaisesRegex(frappe.ValidationError, "already paid"):
			api.reinstate_checkout(res.name, "x")

	def test_needs_a_reason_and_a_checked_out_stay(self):
		res = make_reservation(PROP_A, self.rt, d(-1), d(1), status="Checked In",
		                       room=self.room)
		with self.assertRaises(frappe.ValidationError):
			api.reinstate_checkout(res.name, "x")
		with self.assertRaises(frappe.ValidationError):
			api.reinstate_checkout(res.name, " ")
