"""A restaurant bill charged to the wrong room, moved to the right one.

pos.move_room_bill: same business day only, the charge and its ledger
leave the first guest's folio and land on the right guest's, liquor stays
off a company bill, and a paid or never-posted bill is refused.
"""

from __future__ import annotations

import frappe

from kamra import pos
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
from kamra.tests import test_folio_leaks as leaks


class MoveRoomBillTestCase(AuditTestCase):
	properties = (PROP_A,)
	outlet = leaks.FolioLeaksTestCase.outlet

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")
		self.room2 = make_room(PROP_A, self.rt, "102")
		self.wrong = make_reservation(PROP_A, self.rt, d(-1), d(1),
		                              status="Checked In", room=self.room)
		self.right = make_reservation(PROP_A, self.rt, d(-1), d(1),
		                              status="Checked In", room=self.room2)

	def bill(self, item):
		outlet = self.outlet_items[0]
		o = pos.create_order(outlet, [{"menu_item": item, "qty": 1}],
		                     room=self.room, order_type="Room Service")
		pos.deliver_order(o["order"])
		return o["order"]

	def lines(self, folio, order):
		return frappe.get_all("Folio Charge", filters={
			"parent": folio, "description": ["like", f"%({order})"]})

	def test_the_bill_moves_with_its_ledger(self):
		self.outlet_items = self.outlet()
		order = self.bill(self.outlet_items[1])
		src, dst = guest_folio(self.wrong.name), guest_folio(self.right.name)
		before_src, before_dst = leaks._balance(src), leaks._balance(dst)
		out = pos.move_room_bill(order, self.room2, "Guest gave room 101 by mistake")
		self.assertEqual(out["reservation"], self.right.name)
		self.assertFalse(self.lines(src, order))
		self.assertTrue(self.lines(dst, order))
		self.assertAlmostEqual(leaks._balance(src), before_src - 210, 2)
		self.assertAlmostEqual(leaks._balance(dst), before_dst + 210, 2)
		for f in (src, dst):  # each folio's guest ledger agrees with its balance
			self.assertAlmostEqual(leaks._net(f, "Guest"), leaks._balance(f), 2)
		self.assertEqual(frappe.db.get_value("POS Order", order, ["room", "reservation"]),
		                 (self.room2, self.right.name))
		with self.assertRaises(frappe.ValidationError):  # already there
			pos.move_room_bill(order, self.room2, "again")

	def test_a_split_bill_is_refused(self):
		from kamra import folio as folio_mod
		self.outlet_items = self.outlet()
		order = self.bill(self.outlet_items[1])
		src = guest_folio(self.wrong.name)
		line = self.lines(src, order)[0].name
		folio_mod.split_charge(src, line, folio_mod.split_folio(self.wrong.name), 50)
		with self.assertRaisesRegex(frappe.ValidationError, "split"):
			pos.move_room_bill(order, self.room2, "x")

	def test_only_the_same_business_day(self):
		self.outlet_items = self.outlet()
		order = self.bill(self.outlet_items[1])
		frappe.db.set_value("Property", PROP_A, "business_date", d(1))
		with self.assertRaisesRegex(frappe.ValidationError, "posted today"):
			pos.move_room_bill(order, self.room2, "late")

	def test_refusals(self):
		self.outlet_items = self.outlet()
		order = self.bill(self.outlet_items[1])
		with self.assertRaises(frappe.ValidationError):  # needs a reason
			pos.move_room_bill(order, self.room2, " ")
		with self.assertRaises(frappe.ValidationError):  # nobody in that room
			pos.move_room_bill(order, make_room(PROP_A, self.rt, "103"), "x")
		paid = pos.create_order(self.outlet_items[0],
		                        [{"menu_item": self.outlet_items[1], "qty": 1}],
		                        table_no="T9", order_type="Dine In")
		pos.pay_order(paid["order"], "Cash")
		with self.assertRaises(frappe.ValidationError):  # never on a room
			pos.move_room_bill(paid["order"], self.room2, "x")

	def test_liquor_lands_on_the_guest_not_the_company(self):
		COMPANY = leaks.COMPANY
		if not frappe.db.exists("Corporate Account", COMPANY):
			frappe.get_doc({"doctype": "Corporate Account", "company_name": COMPANY,
			                "credit_allowed": 1, "billing_rules": [
			                    {"charge_type": "Food & Beverage", "pay_by": "Company"}]}
			               ).insert(ignore_permissions=True)
		frappe.db.set_value("Reservation", self.right.name,
		                    {"company": COMPANY, "booking_type": "Corporate"})
		self.outlet_items = self.outlet()
		order = self.bill(self.outlet_items[2])  # gin
		out = pos.move_room_bill(order, self.room2, "wrong room")
		self.assertEqual(out["folio"], guest_folio(self.right.name))
