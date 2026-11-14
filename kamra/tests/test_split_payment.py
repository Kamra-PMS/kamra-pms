"""Split payment at check-out (#597): one request records several payments.

api.add_folio_payments posts each line the way add_folio_payment does, and
keeps all of them or none.
"""

from __future__ import annotations

import frappe

from kamra import api, cashier
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


def _payments(folio: str) -> list:
	return frappe.get_all("Folio Payment", filters={"parent": folio},
	                      fields=["mode", "amount", "reference", "payment_kind"],
	                      order_by="idx")


class TestSplitPayment(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date")
		make_property(PROP_A, business_date=TODAY)
		rt = make_room_type(PROP_A, "STD", base_price=1000)
		room = make_room(PROP_A, rt, "101")
		res = make_reservation(PROP_A, rt, d(-1), d(1), status="Checked In", room=room)
		self.folio = guest_folio(res.name)
		cashier.open_session(PROP_A, 0)

	def line(self, mode: str, amount: float, reference: str | None = None, **extra) -> dict:
		return {"folio": self.folio, "mode": mode, "amount": amount,
		        "reference": reference, **extra}

	def test_each_line_becomes_one_payment_with_its_mode_and_reference(self):
		out = api.add_folio_payments([
			self.line("Cash", 1000),
			self.line("Card", 1500, "CARD-7781"),
			self.line("UPI", 500.5, "UPI-42"),
		])
		self.assertEqual(out["posted"], 3)
		self.assertEqual(out["folios"], [self.folio])
		rows = _payments(self.folio)
		self.assertEqual([r.mode for r in rows], ["Cash", "Card", "UPI"])
		self.assertEqual([float(r.amount) for r in rows], [1000.0, 1500.0, 500.5])
		self.assertEqual([r.reference for r in rows], [None, "CARD-7781", "UPI-42"])
		self.assertEqual(float(frappe.db.get_value("Folio", self.folio, "payments_total") or 0), 3000.5)

	def test_each_mode_reaches_the_till_separately(self):
		api.add_folio_payments([self.line("Cash", 400), self.line("Card", 600, "C-1")])
		by_mode = dict(frappe.db.sql(
			"""SELECT mode, SUM(amount) FROM `tabCashier Transaction`
			   WHERE folio = %s AND kind = 'Payment' GROUP BY mode""", self.folio))
		self.assertEqual(float(by_mode["Cash"]), 400.0)
		self.assertEqual(float(by_mode["Card"]), 600.0)

	def test_a_refused_line_keeps_none_of_the_lines(self):
		with self.assertRaises(frappe.ValidationError):
			api.add_folio_payments([
				self.line("Cash", 1000),
				self.line("Not A Real Mode", 500),
			])
		self.assertEqual(_payments(self.folio), [])
		self.assertEqual(frappe.db.count("Cashier Transaction", {"folio": self.folio}), 0)

	def test_nothing_to_post_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "at least one"):
			api.add_folio_payments([])

	def test_a_zero_or_negative_amount_is_refused_before_anything_posts(self):
		for amount in (0, -50):
			with self.assertRaisesRegex(frappe.ValidationError, "positive"):
				api.add_folio_payments([self.line("Cash", 100), self.line("Card", amount)])
		self.assertEqual(_payments(self.folio), [])

	def test_json_text_is_accepted_as_the_http_call_sends_it(self):
		import json
		out = api.add_folio_payments(json.dumps([self.line("Cash", 100), self.line("UPI", 200, "U-1")]))
		self.assertEqual(out["posted"], 2)

	def test_too_many_lines_are_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "At most"):
			api.add_folio_payments([self.line("Cash", 1)] * (api.MAX_SPLIT_LINES + 1))

	def test_a_retry_with_the_same_keys_does_not_pay_twice(self):
		lines = [self.line("Cash", 300, idempotency_key="k-1"),
		         self.line("Card", 700, "C-9", idempotency_key="k-2")]
		api.add_folio_payments(lines)
		api.add_folio_payments(lines)
		self.assertEqual(len(_payments(self.folio)), 2)
