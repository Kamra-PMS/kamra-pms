"""Reversing a check-in made by mistake, the same business day.

api.reverse_check_in (OPERA Cloud "Reverse Check In"): allowed on the
business date of the check-in when nothing was posted or paid. The stay
goes back to Confirmed (arrival), the room is released and marked Dirty
for housekeeping to inspect, and the reason goes on the action log. From
there the desk can check the guest in again or cancel the booking.
"""

from __future__ import annotations

from unittest.mock import patch

import frappe

from kamra import api
from kamra.door_lock import DoorLockAdapter, KeyResult
from kamra.tests.audit_fixtures import (
	PROP_A,
	PROP_B,
	TODAY,
	AuditTestCase,
	d,
	guest_folio,
	make_property,
	make_reservation,
	make_room,
	make_room_type,
)


class _Lock(DoorLockAdapter):
	"""A connected lock system that records what it was asked to do."""

	key = "ut-lock"
	label = "UT lock"

	def __init__(self):
		self.revoked = []

	def issue_key(self, request):
		return KeyResult(ok=True, adapter=self.key)

	def revoke_keys(self, property, reservation, room):
		self.revoked.append((property, reservation, room))
		return KeyResult(ok=True, adapter=self.key, message="UT keys cancelled")


class ReverseCheckInTestCase(AuditTestCase):
	properties = (PROP_A, PROP_B)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")
		frappe.db.set_value("Room", self.room, "housekeeping_status", "Clean")
		self.res = make_reservation(PROP_A, self.rt, TODAY, d(2),
		                            status="Checked In", room=self.room,
		                            occupants=[{"full_name": "UT Partner"}])
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

	def test_a_connected_lock_cancels_the_keys(self):
		lock = _Lock()
		with patch("kamra.door_lock.get_adapter", return_value=lock):
			out = api.reverse_check_in(self.res.name, "Wrong guest")
		self.assertEqual(lock.revoked, [(PROP_A, self.res.name, self.room)])
		self.assertTrue(out["key_result"]["ok"])

	def test_a_whole_villa_stay_cancels_the_keys_of_every_room(self):
		# a villa type with no rooms of its own takes the property's rooms
		make_property(PROP_B, business_date=TODAY)
		villa = make_room_type(PROP_B, "VIL", base_price=5000, room_category="Villa")
		bed = make_room_type(PROP_B, "BED", base_price=1000)
		rooms = [make_room(PROP_B, bed, n) for n in ("201", "202")]
		res = make_reservation(PROP_B, villa, TODAY, d(2), status="Checked In")
		frappe.db.set_value("Reservation", res.name, "checked_in_at", f"{TODAY} 10:00:00")
		lock = _Lock()
		with patch("kamra.door_lock.get_adapter", return_value=lock):
			out = api.reverse_check_in(res.name, "Wrong guest")
		self.assertEqual(sorted(lock.revoked), [(PROP_B, res.name, r) for r in sorted(rooms)])
		self.assertTrue(out["key_result"]["ok"])
		for r in rooms:
			self.assertEqual(frappe.db.get_value("Room", r, "occupancy_status"), "Vacant")

	def test_a_lock_lookup_failure_is_shown_not_raised(self):
		with patch("kamra.door_lock.get_adapter", side_effect=RuntimeError("UT no config")):
			out = api.reverse_check_in(self.res.name, "Wrong guest")
		self.assertEqual(out["status"], "Confirmed")
		self.assertFalse(out["key_result"]["ok"])
		self.assertIn("Cancel the keys at the encoder", out["key_result"]["message"])

	def test_manual_keys_are_left_to_the_desk(self):
		out = api.reverse_check_in(self.res.name, "Wrong guest")
		self.assertIsNone(out.get("key_result"))

	def test_the_next_check_in_stamps_arrival_afresh(self):
		occ = lambda: frappe.get_doc("Reservation", self.res.name).occupants[0]  # noqa: E731
		self.assertTrue(occ().arrived_at)
		api.reverse_check_in(self.res.name, "Wrong guest")
		self.assertIsNone(occ().arrived_at)
		api.check_in(self.res.name)
		self.assertEqual(occ().arrived_at, frappe.db.get_value(
			"Reservation", self.res.name, "checked_in_at"))

	def test_refused_while_a_security_deposit_is_held(self):
		frappe.get_doc({"doctype": "Security Deposit", "reservation": self.res.name,
		                "property": PROP_A, "status": "Held", "method": "authorization",
		                "required_amount": 5000}).insert(ignore_permissions=True)
		with self.assertRaisesRegex(frappe.ValidationError, "security deposit"):
			api.reverse_check_in(self.res.name, "Wrong guest")
		self.assertEqual(self.status(), "Checked In")
