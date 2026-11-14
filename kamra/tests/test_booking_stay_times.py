"""Booking dialog: the property's standard times and an overnight stay's
planned arrival and departure time (#599).

The dialog reads the standard times from booking_options and sends the times
it shows to create_booking, which keeps them on the reservation. For an
overnight stay they are display only: the price and status do not change.
"""

from __future__ import annotations

import frappe

from kamra import api
from kamra.tests.audit_fixtures import (
	PROP_A,
	TODAY,
	AuditTestCase,
	d,
	make_property,
	make_room,
	make_room_type,
)


class TestBookingStayTimes(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date")
		make_property(PROP_A, business_date=TODAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		make_room(PROP_A, self.rt, "101")
		make_room(PROP_A, self.rt, "102")

	def book(self, n: int = 1, **extra):
		return api.create_booking(
			property=PROP_A, room_type=self.rt, check_in_date=d(3), check_out_date=d(6),
			guest_name=f"UT Times Guest {n}", phone=f"+91 90000 6{n:04d}", **extra)

	def stay(self, out: dict) -> frappe._dict:
		return frappe.db.get_value(
			"Reservation", out["reservation"],
			["planned_check_in_time", "planned_check_out_time", "is_day_use",
			 "amount_after_tax", "status", "check_in_date", "check_out_date"], as_dict=True)

	def test_options_carry_the_property_standard_times(self):
		frappe.db.set_value("Property", PROP_A, {"checkin_time": "15:30:00", "checkout_time": "12:00:00"})
		prop = api.booking_options(PROP_A)["property"]
		self.assertEqual(prop["checkin_time"], "15:30")
		self.assertEqual(prop["checkout_time"], "12:00")

	def test_options_fall_back_to_14_00_and_11_00_when_the_property_has_none(self):
		frappe.db.set_value("Property", PROP_A, {"checkin_time": None, "checkout_time": None})
		prop = api.booking_options(PROP_A)["property"]
		self.assertEqual(prop["checkin_time"], "14:00")
		self.assertEqual(prop["checkout_time"], "11:00")

	def test_an_overnight_booking_keeps_the_times_it_was_given(self):
		out = self.book(check_in_time="14:00", check_out_time="12:00")
		stay = self.stay(out)
		self.assertEqual(str(stay.planned_check_in_time)[:5], "14:00")
		self.assertEqual(str(stay.planned_check_out_time)[:5], "12:00")
		self.assertFalse(stay.is_day_use)

	def test_a_late_departure_is_not_refused_on_an_overnight_stay(self):
		# departure 11:00 is "earlier" than arrival 14:00 on the clock, and must be fine
		out = self.book(check_in_time="14:00", check_out_time="11:00")
		self.assertEqual(str(self.stay(out).planned_check_out_time)[:5], "11:00")

	def test_the_times_do_not_change_the_price(self):
		plain = self.stay(self.book(1))
		timed = self.stay(self.book(2, check_in_time="09:00", check_out_time="18:00"))
		self.assertEqual(float(plain.amount_after_tax), float(timed.amount_after_tax))
		self.assertEqual(plain.status, timed.status)

	def test_a_booking_without_times_still_works(self):
		stay = self.stay(self.book())
		self.assertFalse(stay.planned_check_in_time)
		self.assertFalse(stay.planned_check_out_time)

	def test_nights_follow_the_check_out_date(self):
		out = self.book(check_in_time="14:00", check_out_time="12:00")
		stay = self.stay(out)
		self.assertEqual(str(stay.check_out_date), d(6))
		self.assertEqual((frappe.utils.getdate(stay.check_out_date) - frappe.utils.getdate(stay.check_in_date)).days, 3)

	def test_a_malformed_time_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "HH:MM"):
			self.book(check_in_time="25:99", check_out_time="12:00")

	def test_the_registration_card_carries_the_booking_times(self):
		out = self.book(check_in_time="15:30", check_out_time="12:00")
		card = api.registration_card(out["reservation"])
		self.assertEqual(card["reservation"]["planned_check_in_time"], "15:30")
		self.assertEqual(card["reservation"]["planned_check_out_time"], "12:00")
		self.assertIn("checkin_time", card["property"])  # the fallback

	def test_the_registration_card_has_no_booking_times_when_none_were_set(self):
		card = api.registration_card(self.book(2)["reservation"])
		self.assertIsNone(card["reservation"]["planned_check_in_time"])
		self.assertIsNone(card["reservation"]["planned_check_out_time"])
