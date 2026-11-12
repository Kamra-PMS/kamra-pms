"""Reversing a check-in made by mistake, the same business day.

api.reverse_check_in (OPERA Cloud "Reverse Check In"): allowed on the
business date of the check-in when nothing was posted or paid. The stay
goes back to Confirmed (arrival), the room is released and marked Dirty
for housekeeping to inspect, and the reason goes on the action log. From
there the desk can check the guest in again or cancel the booking.
"""

from __future__ import annotations

import frappe

from kamra import api
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


class ReverseCheckInTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")
		frappe.db.set_value("Room", self.room, "housekeeping_status", "Clean")
		self.res = make_reservation(PROP_A, self.rt, TODAY, d(2),
		                            status="Checked In", room=self.room)
		# checked in today, on the property's business date
		frappe.db.set_value("Reservation", self.res.name, "checked_in_at",
		                    f"{TODAY} 10:00:00")

	def status(self):
		return frappe.db.get_value("Reservation", self.res.name, "status")

	def test_same_day_zero_balance_goes_back_to_arrival(self):
		out = api.reverse_check_in(self.res.name, "Wrong guest checked in")
		self.assertEqual(out["status"], "Confirmed")
		self.assertEqual(self.status(), "Confirmed")
		self.assertEqual(frappe.db.get_value("Reservation", self.res.name,
		                                     ["actual_check_in", "checked_in_at", "checked_in_by"]),
		                 (None, None, None))
		room = frappe.db.get_value("Room", self.room,
		                           ["occupancy_status", "housekeeping_status"])
		self.assertEqual(room, ("Vacant", "Dirty"))
		self.assertTrue(frappe.db.exists("Agent Action Log", {
			"action_type": "reverse_check_in", "reference_name": self.res.name}))
		# the desk can check the guest in again
		api.check_in(self.res.name)
		self.assertEqual(self.status(), "Checked In")

	def test_then_the_booking_can_be_cancelled(self):
		api.reverse_check_in(self.res.name, "Test booking")
		api.cancel_reservation(self.res.name, reason="Guest request", waive_fee=1)
		self.assertEqual(self.status(), "Cancelled")

	def test_refused_when_a_charge_is_on_the_bill(self):
		api.add_folio_charge(guest_folio(self.res.name), "Laundry", "UT laundry", 300)
		with self.assertRaisesRegex(frappe.ValidationError, "charge or payment is on the bill"):
			api.reverse_check_in(self.res.name, "Wrong guest")
		self.assertEqual(self.status(), "Checked In")

	def test_refused_when_a_payment_is_on_the_bill(self):
		api.add_folio_payment(guest_folio(self.res.name), "Cash", 500, kind="Advance")
		with self.assertRaisesRegex(frappe.ValidationError, "charge or payment is on the bill"):
			api.reverse_check_in(self.res.name, "Wrong guest")
		self.assertEqual(self.status(), "Checked In")

	def test_refused_after_the_night_audit(self):
		frappe.db.set_value("Property", PROP_A, "business_date", d(1))
		with self.assertRaisesRegex(frappe.ValidationError, "night audit has run"):
			api.reverse_check_in(self.res.name, "Too late")
		self.assertEqual(self.status(), "Checked In")

	def test_needs_a_reason_and_a_checked_in_stay(self):
		with self.assertRaisesRegex(frappe.ValidationError, "why"):
			api.reverse_check_in(self.res.name, " ")
		api.reverse_check_in(self.res.name, "Wrong room")
		with self.assertRaisesRegex(frappe.ValidationError, "checked-in"):
			api.reverse_check_in(self.res.name, "Again")

	def test_offered_only_when_allowed(self):
		actions = api.reservation_detail(self.res.name)["actions"]
		self.assertTrue(actions.get("can_reverse_check_in"))
		frappe.db.set_value("Property", PROP_A, "business_date", d(1))
		self.assertFalse(api.reservation_detail(self.res.name)["actions"]
		                 .get("can_reverse_check_in"))
