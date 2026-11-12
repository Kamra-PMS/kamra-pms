"""Folio payment and security-deposit collects are idempotent (#550)."""

from __future__ import annotations

import frappe

from kamra import api, cashier
from kamra.tests.audit_fixtures import (
	PROP_A, TODAY, AuditTestCase, d, guest_folio, make_property, make_reservation,
	make_room, make_room_type,
)


class TestPaymentIdempotency(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY, security_deposit_amount=500,
		              require_cashier_pin=0)
		self.rt = make_room_type(PROP_A, "PID", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "PID101")
		self.res = make_reservation(
			PROP_A, self.rt, d(-1), d(2), status="Checked In", room=self.room)
		self.folio = guest_folio(self.res.name)
		cashier.open_session(PROP_A, 500)

	def _payment_count(self, folio: str) -> int:
		return len(frappe.get_doc("Folio", folio).payments)

	def test_add_folio_payment_key_replays(self):
		first = api.add_folio_payment(
			self.folio, "Cash", 100, kind="Payment",
			idempotency_key="ut-pay-k1")
		again = api.add_folio_payment(
			self.folio, "Cash", 100, kind="Payment",
			idempotency_key="ut-pay-k1")
		self.assertEqual(again.get("idempotent_replay"), 1)
		self.assertEqual(self._payment_count(self.folio), 1)
		self.assertAlmostEqual(
			float(frappe.db.get_value("Folio", self.folio, "balance")),
			float(first["balance"]), places=2)
		# a new key posts a second payment
		api.add_folio_payment(
			self.folio, "Cash", 50, kind="Payment",
			idempotency_key="ut-pay-k2")
		self.assertEqual(self._payment_count(self.folio), 2)

	def test_collect_security_deposit_key_replays(self):
		if not frappe.db.exists("DocType", "Security Deposit"):
			self.skipTest("Security Deposit doctype not installed")
		one = api.collect_security_deposit(
			self.res.name, 200, mode="Cash",
			idempotency_key="ut-dep-k1")
		two = api.collect_security_deposit(
			self.res.name, 200, mode="Cash",
			idempotency_key="ut-dep-k1")
		self.assertEqual(two.get("idempotent_replay"), 1)
		self.assertAlmostEqual(float(one["collected"]), float(two["collected"]))
		# only one Security Deposit payment on the folio
		kinds = [p.payment_kind for p in frappe.get_doc("Folio", self.folio).payments]
		self.assertEqual(kinds.count("Security Deposit"), 1)
		# a new press posts again
		api.collect_security_deposit(
			self.res.name, 100, mode="Cash",
			idempotency_key="ut-dep-k2")
		kinds = [p.payment_kind for p in frappe.get_doc("Folio", self.folio).payments]
		self.assertEqual(kinds.count("Security Deposit"), 2)
