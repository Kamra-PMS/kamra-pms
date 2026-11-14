"""A void keeps the line on the folio and adds a signed reversal line.

folio.void_charge used to delete the line, so the bill, get_folio and the
printed folio lost every trace of it. Now the original stays, a line of the
opposite sign follows it (same charge type and transaction code, the reason
and the user on it), each line carries its own ledger entry and the pair
nets to zero. A voided pair is not a room sold, does not stop the night
being posted again, and cannot be voided, moved or split.
"""

from __future__ import annotations

import frappe

from kamra import api, ledger
from kamra import folio as folio_mod
from kamra.reports import _day_stats
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


class VoidKeepsLineTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")
		self.res = make_reservation(PROP_A, self.rt, TODAY, d(2),
		                            status="Checked In", room=self.room)
		self.folio = guest_folio(self.res.name)

	def charge(self, amount=13000, charge_type="Food & Beverage"):
		doc = api.add_folio_charge(self.folio, charge_type, f"UT {charge_type}",
		                           amount)
		return doc["charges"][-1]["name"]

	def lines(self):
		return frappe.get_doc("Folio", self.folio).charges

	def balance(self):
		return float(frappe.db.get_value("Folio", self.folio, "balance") or 0)

	def test_void_keeps_the_line_and_adds_a_signed_reversal(self):
		before = self.balance()
		row = self.charge()
		orig = next(c for c in self.lines() if c.name == row)
		api.void_folio_charge(self.folio, row, reason="UT posted to the wrong room")
		lines = self.lines()
		self.assertIn(row, [c.name for c in lines], "the voided line left the folio")
		rev = [c for c in lines if c.get("reversal_of") == row]
		self.assertEqual(len(rev), 1, "no reversal line on the folio")
		rev = rev[0]
		self.assertEqual(rev.charge_type, orig.charge_type)
		self.assertEqual(float(rev.amount), -float(orig.amount))
		self.assertEqual(float(rev.total), -float(orig.total))
		self.assertEqual(rev.void_reason, "UT posted to the wrong room")
		self.assertEqual(rev.voided_by, frappe.session.user)
		self.assertAlmostEqual(self.balance(), before, places=2)
		# each line has its own ledger entry and the folio equals its ledger
		self.assertTrue(frappe.db.exists("Folio Ledger Entry", {
			"source_doctype": "Folio Charge", "source_name": rev.name}))
		self.assertTrue(ledger.folio_reconciliation(PROP_A)["in_balance"])
		# the bill screen reads both lines
		names = [c["name"] for c in api.get_folio(self.res.name)["charges"]]
		self.assertIn(row, names)
		self.assertIn(rev.name, names)

	def test_a_voided_line_and_its_reversal_cannot_be_voided_again(self):
		row = self.charge()
		api.void_folio_charge(self.folio, row, reason="UT duplicate")
		rev = next(c.name for c in self.lines() if c.get("reversal_of") == row)
		with self.assertRaisesRegex(frappe.ValidationError, "already voided"):
			api.void_folio_charge(self.folio, row, reason="UT again")
		with self.assertRaisesRegex(frappe.ValidationError, "reverses a void"):
			api.void_folio_charge(self.folio, rev, reason="UT undo")

	def test_a_voided_pair_cannot_be_moved_or_split(self):
		row = self.charge()
		api.void_folio_charge(self.folio, row, reason="UT duplicate")
		extra = api.split_folio(self.res.name, "Extra")["folio"]
		with self.assertRaisesRegex(frappe.ValidationError, "voided"):
			folio_mod.transfer_charges(self.folio, [row], extra)
		with self.assertRaisesRegex(frappe.ValidationError, "voided"):
			folio_mod.split_charge(self.folio, row, extra, percent=50)

	def test_a_voided_room_night_is_not_sold_and_posts_again(self):
		folio_mod.post_room_night(self.res, TODAY)
		night = next(c.name for c in self.lines() if c.charge_type == "Room")
		self.assertEqual(_day_stats(PROP_A, TODAY, 1)["rooms_sold"], 1)
		api.void_folio_charge(self.folio, night, reason="UT wrong rate")
		self.assertIn(night, [c.name for c in self.lines()])
		self.assertEqual(_day_stats(PROP_A, TODAY, 1)["rooms_sold"], 0)
		self.assertNotIn(TODAY, folio_mod.charged_nights(self.res.name))
		# a discount does not come off the voided night
		with self.assertRaisesRegex(frappe.ValidationError, "no room nights"):
			api.post_discount(self.folio, value=10, kind="Percent", preview=1)
		# advance billing (and the night audit) post the night again
		ledger.force_advance_bill(self.res.name, "tonight")
		self.assertEqual(_day_stats(PROP_A, TODAY, 1)["rooms_sold"], 1)
		self.assertFalse(folio_mod.post_room_night(self.res, TODAY))
