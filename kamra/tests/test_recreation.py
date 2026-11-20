"""Gym desk and memberships (#632).

In-house complimentary access posts nothing. Paid access posts to the
guest folio. A membership covers an external customer until its visit
limit. Capacity and a property the desk isn't allowed into are refused.
"""

from __future__ import annotations

import frappe
from frappe.utils import get_datetime

from kamra import recreation
from kamra.tests.audit_fixtures import (
	PROP_A,
	PROP_B,
	TODAY,
	AuditTestCase,
	charges,
	d,
	ensure_user,
	make_guest,
	make_property,
	make_reservation,
	make_room,
	make_room_type,
)


class RecreationTest(AuditTestCase):
	properties = (PROP_A, PROP_B)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger",
		        "kamra.recreation")
		self._stack.enter_context(patch_now())
		make_property(PROP_A, business_date=TODAY)
		make_property(PROP_B, business_date=TODAY)
		rt = make_room_type(PROP_A)
		room = make_room(PROP_A, rt, "G1")
		self.stay = make_reservation(
			PROP_A, rt, TODAY, d(2), status="Checked In",
			room=room, guest=make_guest("Gym Guest"))
		self.gym = frappe.get_doc({
			"doctype": "Recreation Facility", "property": PROP_A,
			"facility_name": "UT Gym", "category": "Gym", "capacity": 1,
			"access": "Both", "price": 200, "status": "Open",
		}).insert(ignore_permissions=True)
		self.other = frappe.get_doc({
			"doctype": "Recreation Facility", "property": PROP_B,
			"facility_name": "UT Other Gym", "category": "Gym", "capacity": 5,
			"access": "Paid", "price": 100, "status": "Open",
		}).insert(ignore_permissions=True)

	def test_complimentary_posts_nothing_and_paid_posts_to_the_folio(self):
		free = recreation.check_in(self.gym.name, reservation=self.stay.name,
		                           complimentary=1)
		self.assertEqual(free["payment_mode"], "Complimentary")
		self.assertEqual(charges(self.stay.name, "Misc"), [])
		recreation.check_out(free["name"])
		paid = recreation.check_in(self.gym.name, reservation=self.stay.name)
		self.assertEqual(paid["payment_mode"], "Folio")
		posted = charges(self.stay.name, "Misc")
		self.assertEqual(len(posted), 1)
		self.assertEqual(float(posted[0].amount), 200)

	def test_capacity_and_closed_hours_are_refused(self):
		recreation.check_in(self.gym.name, reservation=self.stay.name, complimentary=1)
		with self.assertRaisesRegex(frappe.ValidationError, "capacity"):
			recreation.check_in(self.gym.name, reservation=self.stay.name, complimentary=1)
		self.gym.opens = "01:00:00"
		self.gym.closes = "02:00:00"
		self.gym.capacity = 5
		self.gym.save(ignore_permissions=True)
		with self.assertRaisesRegex(frappe.ValidationError, "not open"):
			recreation.check_in(self.gym.name, reservation=self.stay.name, complimentary=1)

	def test_a_membership_covers_visits_until_its_limit(self):
		customer = recreation.register_customer(PROP_A, "Walk In")["name"]
		plan = frappe.get_doc({
			"doctype": "Recreation Plan", "property": PROP_A,
			"plan_name": "UT Day", "period": "Day", "price": 500, "visit_limit": 1,
		}).insert(ignore_permissions=True)
		sold = recreation.sell_membership(customer, plan.name, starts_on=TODAY, paid=1)
		self.assertEqual(str(sold["ends_on"]), TODAY)
		first = recreation.check_in(self.gym.name, customer=customer)
		self.assertEqual(first["payment_mode"], "Membership")
		self.assertEqual(charges(self.stay.name, "Misc"), [])
		recreation.check_out(first["name"])
		second = recreation.check_in(self.gym.name, customer=customer)
		self.assertEqual(second["payment_mode"], "Cash")
		self.assertEqual(second["amount"], 200)
		day = recreation.revenue(PROP_A, TODAY)
		self.assertEqual(day["cash"], 200)
		self.assertEqual(day["membership"], 500)
		self.assertEqual(day["folio"], 0)

	def test_a_desk_limited_to_one_property_cannot_check_in_the_other(self):
		desk = ensure_user("ut.rec.desk@example.com", ["Front Desk"])
		frappe.get_doc({
			"doctype": "User Permission", "user": desk,
			"allow": "Property", "for_value": PROP_A,
		}).insert(ignore_permissions=True)
		frappe.clear_cache(user=desk)
		rt = make_room_type(PROP_B, code="GYM")
		room = make_room(PROP_B, rt, "G9")
		stay = make_reservation(
			PROP_B, rt, TODAY, d(2), status="Checked In",
			room=room, guest=make_guest("Other Gym"))
		frappe.set_user(desk)  # nosemgrep: frappe-setuser -- test fixture
		try:
			with self.assertRaises(frappe.PermissionError):
				recreation.check_in(self.other.name, reservation=stay.name)
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture


def patch_now():
	from unittest.mock import patch
	from contextlib import ExitStack
	stack = ExitStack()
	stack.enter_context(patch("kamra.recreation.now_datetime",
	                          return_value=get_datetime(f"{TODAY} 10:00:00")))
	stack.enter_context(patch("kamra.recreation.nowtime", return_value="10:00:00"))
	return stack
