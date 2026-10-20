# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""External POS interface: in-house lookup, one posting per ticket, the
alcohol rule, property scope and roles."""

from __future__ import annotations

from unittest.mock import patch

import frappe

from kamra import api
from kamra import pos_interface as pi
from kamra.tests.audit_fixtures import (
	PROP_A,
	PROP_B,
	TODAY,
	AuditTestCase,
	d,
	ensure_user,
	make_guest,
	make_property,
	make_reservation,
	make_room,
	make_room_type,
)

POS_USER = "ut.pos.integrator@test.local"


def _corp(name: str) -> str:
	if not frappe.db.exists("Corporate Account", name):
		frappe.get_doc({"doctype": "Corporate Account", "company_name": name,
		                "credit_allowed": 1}).insert(ignore_permissions=True)
	return name


class POSInterfaceTestCase(AuditTestCase):
	properties = (PROP_A, PROP_B)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		# webhooks fire on these postings; keep them off the job queue
		self._stack.enter_context(patch("kamra.webhooks._enqueue"))
		make_property(PROP_A, business_date=TODAY)
		make_property(PROP_B, business_date=TODAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")
		self.res = make_reservation(PROP_A, self.rt, d(-1), d(2), room=self.room,
		                            status="Checked In",
		                            guest=make_guest("Asha", last_name="Rao"))
		rt_b = make_room_type(PROP_B, "STD", base_price=1000)
		self.room_b = make_room(PROP_B, rt_b, "201")
		self.res_b = make_reservation(PROP_B, rt_b, d(-1), d(2), room=self.room_b,
		                              status="Checked In")
		ensure_user(POS_USER, ["POS Integrator"])
		if not frappe.db.exists("User Permission", {"user": POS_USER, "allow": "Property"}):
			frappe.get_doc({"doctype": "User Permission", "user": POS_USER,
			                "allow": "Property", "for_value": PROP_A}).insert(
				ignore_permissions=True)
		frappe.clear_cache(user=POS_USER)

	def as_pos(self):
		frappe.set_user(POS_USER)  # nosemgrep: frappe-setuser -- the integrator persona under test

	def post(self, ticket="T-1", amount=450, **kw):
		return pi.pos_post_room_charge(PROP_A, ticket, amount,
		                               kw.pop("description", "Rooftop bar"),
		                               room=kw.pop("room", "101"), **kw)

	# -- lookup -------------------------------------------------------------

	def test_lookup_returns_in_house_minimal_fields(self):
		self.as_pos()
		rows = pi.pos_room_lookup(PROP_A, room="101")
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["reservation"], self.res.name)
		self.assertEqual(set(rows[0]), {"reservation", "room", "room_number",
		                                "guest_name", "check_out_date", "corporate"})
		self.assertEqual(pi.pos_room_lookup(PROP_A, room="999"), [])
		with self.assertRaisesRegex(frappe.ValidationError, "room number or"):
			pi.pos_room_lookup(PROP_A)

	def test_lookup_skips_guests_not_in_house(self):
		make_reservation(PROP_A, self.rt, d(3), d(4), room=self.room)
		self.as_pos()
		self.assertEqual([r["reservation"] for r in pi.pos_room_lookup(PROP_A, room="101")],
		                 [self.res.name])

	# -- posting ------------------------------------------------------------

	def test_post_goes_through_the_folio_and_is_idempotent(self):
		self.as_pos()
		first = self.post()
		self.assertFalse(first["duplicate"])
		self.assertEqual(first["folio_type"], "Guest")
		again = self.post()
		self.assertTrue(again["duplicate"])
		self.assertEqual(again["folio"], first["folio"])
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- back to the fixture user to inspect
		lines = frappe.get_all("Folio Charge", filters={
			"parent": first["folio"], "description": ("like", "%POS T-1%")},
			fields=["amount", "charge_type"])
		self.assertEqual(len(lines), 1)
		self.assertEqual(lines[0].charge_type, "Food & Beverage")
		self.assertEqual(frappe.db.count(pi.CHARGE, {"property": PROP_A}), 1)

	def test_reused_ticket_for_a_different_amount_refused(self):
		self.as_pos()
		self.post()
		with self.assertRaisesRegex(frappe.ValidationError, "different"):
			self.post(amount=999)

	def test_alcohol_never_bills_the_company(self):
		frappe.db.set_value("Reservation", self.res.name,
		                    {"company": _corp("UT POS Corp"), "booking_type": "Corporate"})
		self.as_pos()
		food = self.post("T-food", 500, description="Lunch")
		self.assertEqual(food["folio_type"], "Company")
		beer = self.post("T-beer", 300, description="Beer", is_alcohol=1)
		self.assertEqual(beer["folio_type"], "Guest")
		# and the posting helper itself refuses alcohol on a Company folio
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- direct helper check
		with self.assertRaisesRegex(frappe.ValidationError, "Alcohol cannot be billed"):
			api._post_folio_charge(food["folio"], "Food & Beverage", "Whisky", 800,
			                       is_alcohol=1)

	def test_other_property_refused(self):
		self.as_pos()
		with self.assertRaises(frappe.PermissionError):
			pi.pos_post_room_charge(PROP_B, "T-x", 100, "Bar", room="201")
		with self.assertRaises(frappe.PermissionError):
			pi.pos_room_lookup(PROP_B, room="201")
		# naming the other hotel's stay under my own property doesn't work either
		with self.assertRaises(frappe.PermissionError):
			pi.pos_post_room_charge(PROP_A, "T-y", 100, "Bar",
			                        reservation=self.res_b.name)

	def test_role_required(self):
		frappe.set_user(ensure_user("ut.pos.hk@test.local", ["Housekeeping"]))  # nosemgrep: frappe-setuser -- persona under test
		with self.assertRaises(frappe.PermissionError):
			self.post()

	def test_rules_enforced(self):
		self.as_pos()
		with self.assertRaisesRegex(frappe.ValidationError, "more than zero"):
			self.post("T-neg", -50)
		with self.assertRaisesRegex(frappe.ValidationError, "charge_type"):
			self.post("T-room", 100, charge_type="Room")
		with self.assertRaisesRegex(frappe.ValidationError, "ticket_id"):
			self.post("  ", 100)
		# nothing half-posted: the failed tickets left no record
		self.assertEqual(frappe.db.count(pi.CHARGE, {"property": PROP_A}), 0)

	def test_property_limit(self):
		with patch("kamra.settings.get_setting", return_value=1000):
			self.as_pos()
			with self.assertRaisesRegex(frappe.ValidationError, "limit"):
				self.post("T-big", 5000)
