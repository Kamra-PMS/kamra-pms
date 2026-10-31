"""A group with a main room that pays.

The main room (Group Booking.master_reservation) carries what `master_pays`
covers for every room on one group bill, with no company needed. A room can
opt out (pays_own_charges), liquor never routes, the main guest can leave
while the bill stays open, and settle_group_bill closes it. A company group
without a main room keeps its city-ledger behaviour.
"""

from __future__ import annotations

import frappe

from kamra import api
from kamra.checkout import settlement_position
from kamra.tests.audit_fixtures import (
	PROP_A,
	TODAY,
	AuditTestCase,
	d,
	make_property,
	make_reservation,
	make_room,
	make_room_type,
)

COMPANY = "UT Group Billing Corp"


class GroupBillingTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.rooms = [make_room(PROP_A, self.rt, n) for n in ("101", "102", "103")]

	def group(self, company=None, master=True, pays="Room only"):
		gb = frappe.get_doc({
			"doctype": "Group Booking", "property": PROP_A,
			"group_name": "UT Sharma Wedding", "company": company,
			"check_in_date": d(-1), "check_out_date": d(2),
			"status": "Confirmed"}).insert(ignore_permissions=True)
		stays = [make_reservation(PROP_A, self.rt, d(-1), TODAY if i == 0 else d(2),
		                          status="Checked In", room=room,
		                          group_booking=gb.name)
		         for i, room in enumerate(self.rooms)]
		if master:
			gb.db_set({"master_reservation": stays[0].name, "master_pays": pays})
		return gb, stays

	def post(self, res, charge_type, desc, amount=1000, alcohol=0):
		return api.post_stay_charge(res.name, charge_type, desc, amount,
		                            is_alcohol=alcohol)

	def test_main_room_pays_room_guest_pays_extras(self):
		r1, r2 = self.group()[1][:2]
		room = self.post(r2, "Room", "UT R2 night")
		self.assertEqual(room["folio_type"], "Group")
		self.assertEqual(frappe.db.get_value("Folio", room["folio"], "reservation"),
		                 r1.name)
		self.assertEqual(self.post(r2, "Minibar", "UT R2 minibar", 200)["folio_type"],
		                 "Guest")

	def test_room_that_pays_its_own_keeps_its_room_charge(self):
		r3 = self.group()[1][2]
		api.set_pays_own_charges(r3.name, 1)
		self.assertEqual(self.post(r3, "Room", "UT R3 night")["folio_type"], "Guest")

	def test_alcohol_never_routes(self):
		r2 = self.group(pays="Everything except liquor")[1][1]
		self.assertEqual(self.post(r2, "Food & Beverage", "UT lunch", 500)["folio_type"],
		                 "Group")
		self.assertEqual(self.post(r2, "Food & Beverage", "UT whisky", 800, 1)["folio_type"],
		                 "Guest")

	def test_main_guest_leaves_and_the_bill_stays_open(self):
		r1, r2 = self.group()[1][:2]
		bill = self.post(r2, "Room", "UT R2 night")["folio"]
		self.assertNotIn(bill, [f["name"] for f in settlement_position(r1.name)["folios"]])
		api.check_out(r1.name)
		self.assertEqual(frappe.db.get_value("Reservation", r1.name, "status"),
		                 "Checked Out")
		self.assertEqual(frappe.db.get_value("Folio", bill, "status"), "Open")
		self.assertEqual(self.post(r2, "Room", "UT R2 late night")["folio"], bill)

	def test_settle_group_bill_closes_it(self):
		gb, (_r1, r2, _r3) = self.group()
		bill = self.post(r2, "Room", "UT R2 night")["folio"]
		out = api.settle_group_bill(gb.name, mode="Cash")
		self.assertTrue(out["closed"])
		self.assertEqual(out["balance"], 0)
		self.assertEqual(frappe.db.get_value("Folio", bill, "status"), "Closed")
		self.assertTrue(out["invoice_number"])
		self.assertIn("still in house", out["warning"])

	def test_company_group_settles_to_the_city_ledger(self):
		gb, (_r1, r2, _r3) = self.group(company=_corp())
		bill = self.post(r2, "Room", "UT R2 night")["folio"]
		out = api.settle_group_bill(gb.name, to_city_ledger=1)
		self.assertTrue(out["closed"])
		self.assertTrue(frappe.db.exists("City Ledger Entry",
		                                 {"folio": bill, "kind": "Invoice"}))

	def test_set_group_master_reanchors_the_open_bill(self):
		gb, (_r1, r2, _r3) = self.group()
		bill = self.post(r2, "Room", "UT R2 night")["folio"]
		api.set_group_master(gb.name, r2.name)
		self.assertEqual(frappe.db.get_value("Folio", bill, "reservation"), r2.name)
		self.assertEqual(frappe.db.get_value("Group Booking", gb.name,
		                                     "master_reservation"), r2.name)

	def test_company_group_without_main_room_is_unchanged(self):
		r1, r2 = self.group(company=_corp(), master=False)[1][:2]
		bill = self.post(r2, "Room", "UT R2 night")["folio"]
		self.assertEqual(frappe.db.get_value("Folio", bill, "folio_type"), "Group")
		self.assertIn(bill, [f for f, _c, _b in
		                     settlement_position(r1.name)["to_city_ledger"]])

	def test_plain_group_without_main_room_routes_nothing(self):
		r2 = self.group(master=False)[1][1]
		self.assertEqual(self.post(r2, "Room", "UT R2 night")["folio_type"], "Guest")

	def test_create_group_booking_sets_the_main_room(self):
		out = api.create_group_booking(
			PROP_A, "UT Corporate Offsite", d(10), d(12),
			[{"room_type": self.rt, "count": 2, "guest_name": "UT Guest of group"}],
			guest_name="UT Lead", phone="+91 90000 55501",
			group_type="Wedding", master_index=1)
		self.assertEqual(len(out["created"]), 2, out["skipped"])
		self.assertEqual(out["master_reservation"], out["created"][1])
		gb = frappe.db.get_value("Group Booking", out["group_booking"],
		                         ["master_pays", "group_type"], as_dict=True)
		self.assertEqual((gb.master_pays, gb.group_type), ("Room only", "Wedding"))


def _corp():
	if frappe.db.exists("Corporate Account", COMPANY):
		doc = frappe.get_doc("Corporate Account", COMPANY)
	else:
		doc = frappe.get_doc({"doctype": "Corporate Account", "company_name": COMPANY})
	doc.credit_allowed = 1
	doc.set("billing_rules", [{"charge_type": "Room", "pay_by": "Company"}])
	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)
	return doc.name
