"""Past transaction dates need Finance / Hotel Admin (or allow_past_transaction)."""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.utils import add_days, nowdate

from kamra.business_date import assert_transaction_date, can_backdate
from kamra.tests.audit_fixtures import AuditTestCase, make_property

PROP = "ut.past-date.prop"


class TestPastTransactionDate(AuditTestCase):
	def setUp(self):
		super().setUp()
		make_property(PROP, business_date=nowdate())
		frappe.flags.allow_past_transaction = None

	def tearDown(self):
		frappe.flags.allow_past_transaction = None
		super().tearDown()

	def test_defaults_to_business_date(self):
		self.assertEqual(assert_transaction_date(PROP), nowdate())

	def test_same_day_ok(self):
		self.assertEqual(assert_transaction_date(PROP, nowdate()), nowdate())

	def test_past_refused_without_permission(self):
		past = add_days(nowdate(), -1)
		with patch("kamra.business_date.can_backdate", return_value=False):
			with self.assertRaises(frappe.ValidationError):
				assert_transaction_date(PROP, past, label="Date")

	def test_past_ok_with_flag(self):
		past = add_days(nowdate(), -1)
		frappe.flags.allow_past_transaction = True
		self.assertTrue(can_backdate())
		self.assertEqual(assert_transaction_date(PROP, past), str(past))

	def test_shift_handover_refuses_past(self):
		past = add_days(nowdate(), -3)
		with patch("kamra.business_date.can_backdate", return_value=False):
			doc = frappe.get_doc({
				"doctype": "Shift Handover",
				"property": PROP,
				"shift": "Morning",
				"shift_date": past,
				"status": "Open",
			})
			with self.assertRaises(frappe.ValidationError):
				doc.insert()
