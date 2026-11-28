"""A guest can be charged for room items taken or broken, on its own line."""

from __future__ import annotations

import frappe

from kamra import api
from kamra.ledger import CHARGE_TYPE_TO_CODE
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

STOLEN = "Stolen / Damaged Items"


class StolenChargeTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY)
		frappe.db.delete("Property Setting", {"property": PROP_A})
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")

	def test_both_doctypes_can_store_it(self):
		for doctype in ("Folio Charge", "Transaction Code"):
			options = frappe.get_meta(doctype).get_field("charge_type").options.split("\n")
			self.assertIn(STOLEN, options, doctype)

	def test_posts_on_its_own_line_with_its_own_code(self):
		res = make_reservation(PROP_A, self.rt, d(-1), d(1),
		                       status="Checked In", room=self.room)
		folio = guest_folio(res.name)
		api.add_folio_charge(folio, STOLEN, "Bath towel x2", 800, gst_rate=18)

		line = next(c for c in frappe.get_doc("Folio", folio).charges
		            if c.charge_type == STOLEN)
		self.assertEqual(line.amount, 800)
		self.assertEqual(line.gst_rate, 18)
		code = CHARGE_TYPE_TO_CODE[STOLEN][0]
		self.assertEqual(line.transaction_code, code)
		txn = frappe.get_doc("Transaction Code", code)
		self.assertEqual(txn.charge_type, STOLEN)
		self.assertEqual(txn.revenue_group, "Other")
