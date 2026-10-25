"""Regressions for @lhertig's reports #341-#344, as suggested in them."""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.model.document import Document

from kamra import api
from kamra.pricing import capacity_overflow
from kamra.tests.audit_fixtures import (
	PROP_A, AuditTestCase, d, guest_folio, make_property, make_reservation, make_room_type,
)


class LhertigReportsTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		make_property(PROP_A)
		self.currency = frappe.db.get_value("Property", PROP_A, "currency")
		frappe.db.set_value("Property", PROP_A, "currency", "CHF")
		frappe.clear_document_cache("Property", PROP_A)
		self.rt = make_room_type(PROP_A, "LHG", adults_capacity=6, children_capacity=6,
		                         max_total_occupants=6, max_extra_beds=0)

	def tearDown(self):
		frappe.db.set_value("Property", PROP_A, "currency", self.currency)
		frappe.clear_document_cache("Property", PROP_A)
		super().tearDown()

	def advance(self, amount):
		res = make_reservation(PROP_A, self.rt, d(10), d(13))
		api.record_advance(res.name, amount, "Bank Transfer", reference="UT-ADV")
		return res.name, guest_folio(res.name)

	def deposit_net(self, folio):
		return float(frappe.db.sql(
			"SELECT COALESCE(SUM(credit - debit), 0) FROM `tabFolio Ledger Entry` "
			"WHERE folio = %s AND ledger = 'Deposit'", folio)[0][0])

	def test_341_payments_carry_the_property_currency(self):
		_, folio = self.advance(100)
		rows = frappe.get_all("Folio Payment", {"parent": folio}, ["currency", "amount"])
		self.assertEqual([(r.currency, r.amount) for r in rows], [("CHF", 100)])
		# any writer that leaves currency blank gets it from the folio's guard
		doc = frappe.get_doc("Folio", folio)
		doc.append("payments", {"posting_date": d(0), "payment_kind": "Payment",
		                        "mode": "Cash", "amount": 1})
		doc.save(ignore_permissions=True)
		self.assertEqual(doc.payments[-1].currency, "CHF")

	def test_342_total_occupants_caps_a_mixed_party(self):
		cap = frappe.db.get_value("Room Type", self.rt, [
			"adults_capacity", "children_capacity", "max_extra_beds",
			"max_total_occupants"], as_dict=True)
		self.assertEqual(capacity_overflow(cap, 6, 1), (1, 0))
		self.assertEqual(capacity_overflow(cap, 4, 2), (0, 0))
		with self.assertRaises(frappe.ValidationError):
			make_reservation(PROP_A, self.rt, d(20), d(22), adults=6, children=1)
		make_reservation(PROP_A, self.rt, d(20), d(22), adults=6, children=0)

	def test_343_refunding_an_advance_releases_the_deposit(self):
		res, folio = self.advance(100)
		self.assertAlmostEqual(self.deposit_net(folio), 100)
		api.refund_folio_payment(folio, 40, "Bank Transfer", reason="UT partial")
		self.assertAlmostEqual(self.deposit_net(folio), 60)
		self.assertAlmostEqual(frappe.db.get_value("Reservation", res, "advance_paid"), 60)
		api.refund_folio_payment(folio, 60, "Bank Transfer", reason="UT rest")
		self.assertAlmostEqual(self.deposit_net(folio), 0)
		self.assertAlmostEqual(frappe.db.get_value("Reservation", res, "advance_paid"), 0)

	def test_344_a_naming_race_is_retried_not_a_500(self):
		real_insert, raised = Document.insert, []

		def flaky(doc, *a, **k):
			if doc.doctype == "Reservation" and not raised:
				raised.append(1)
				raise frappe.QueryDeadlockError("Record has changed since last read in table 'tabSeries'")
			return real_insert(doc, *a, **k)

		# the real retry rolls the request back; keep this test's fixtures
		with patch.object(Document, "insert", flaky), \
		     patch.object(frappe.db, "rollback", lambda *a, **k: None):
			out = api.create_booking(PROP_A, self.rt, d(30), d(32), "UT Race",
			                         phone="+41790000001", assign_room=0)
		self.assertEqual(raised, [1])
		name = out.get("reservation") or out.get("name")
		self.assertTrue(frappe.db.exists("Reservation", name))
