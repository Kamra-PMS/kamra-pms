"""The room counts the booking screens show: what can still be sold of each
type, by the rules saving a booking applies."""

import frappe

from kamra import api
from kamra.tests.test_roomless_availability import _Case


class TestRoomsToSell(_Case):
	def left(self, room_type=None, ci=None, co=None, **kwargs):
		"""(free, without_room) for a type, as the screen is told."""
		rows = api.rooms_to_sell(self.property, ci or self.ci, co or self.co, **kwargs)
		row = rows[room_type or self.room_type]
		return row["free"], row["without_room"]

	def room(self, number):
		return frappe.db.get_value(
			"Room", {"property": self.property, "room_number": number})

	def desk_books(self):
		return api.create_booking(property=self.property, room_type=self.room_type,
			check_in_date=self.ci, check_out_date=self.co, guest_name="Desk Guest",
			phone="+91 90000 74001")

	def make_villa(self):
		return self.make_type("VILLA", "Entire Property", category="Villa")

	def test_a_free_type_counts_its_rooms(self):
		self.assertEqual(self.left(), (2, False))

	def test_stays_without_a_room_come_off(self):
		self.stay()
		self.assertEqual(self.left(), (1, False))

	def test_a_sold_type_is_sold_out_and_a_save_is_refused(self):
		self.stay()
		self.stay()
		self.assertEqual(self.left(), (0, False))
		with self.assertRaisesRegex(frappe.ValidationError, "sold out"):
			self.desk_books()

	def test_rooms_free_on_different_nights_take_a_booking_without_a_room(self):
		self.stay(room=self.room("101"), co=self.day(11))
		self.stay(room=self.room("102"), ci=self.day(11))
		self.assertEqual(self.left(), (0, True))
		saved = self.desk_books()["reservation"]
		self.assertFalse(frappe.db.get_value("Reservation", saved, "room"))

	def test_the_overbooking_allowance_is_offered_without_a_room(self):
		frappe.db.set_value("Room Type", self.room_type, "overbooking_pct", 50)
		self.stay(room=self.room("101"))
		self.stay(room=self.room("102"))
		self.assertEqual(self.left(), (0, True))
		self.assertTrue(self.desk_books()["reservation"])

	def test_a_booked_villa_sells_out_its_member_rooms(self):
		villa = self.make_villa()
		self.stay(room_type=villa)
		self.assertEqual(self.left(), (0, False))
		self.assertEqual(self.left(villa), (0, False))

	def test_a_free_villa_counts_one(self):
		self.assertEqual(self.left(self.make_villa()), (1, False))

	def test_a_walk_in_has_no_room_to_take_in_a_villa_without_rooms(self):
		"""A walk-in is given a room, and this villa has none of its own."""
		self.assertEqual(self.left(self.make_villa(), ready_now=1), (0, True))

	def test_a_walk_in_does_not_count_a_room_not_yet_left(self):
		"""The guest departs today and is still in the room."""
		leaving = self.stay(room=self.room("101"), ci=self.day(0), co=self.day(2))
		frappe.db.set_value("Reservation", leaving.name, {"status": "Checked In",
			"check_in_date": self.day(-1), "check_out_date": self.day(0)})
		tonight = {"ci": self.day(0), "co": self.day(1)}
		self.assertEqual(self.left(**tonight), (2, False))
		self.assertEqual(self.left(ready_now=1, **tonight), (1, False))

	def test_disabled_types_are_left_out(self):
		closed = self.make_type("OLD", "Closed", ["301"])
		frappe.db.set_value("Room Type", closed, "disabled", 1)
		self.assertEqual(
			list(api.rooms_to_sell(self.property, self.ci, self.co)), [self.room_type])

	def test_a_check_out_before_the_check_in_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Check-out"):
			api.rooms_to_sell(self.property, self.co, self.ci)
