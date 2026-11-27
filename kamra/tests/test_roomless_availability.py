"""A stay with no room number still takes a room off sale, and a whole villa
sells once.

Channel bookings arrive without a room, and a property can switch room
assignment off, so availability has to count stays by room type, as the
capacity guard does when a booking is saved."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from kamra import channel_manager as cm
from kamra.api import (
	amend_stay,
	availability_calendar,
	available_rooms,
	create_booking,
	create_group_with_rooming_list,
	group_amend_dates,
	promote_waitlist,
	waitlist_ready,
)
from kamra.booking_requests import booking_requests
from kamra.crs import crs_search, quote_itinerary
from kamra.public_api import book, search_stay
from kamra.siu import availability as siu_availability


class _Case(IntegrationTestCase):
	"""A property with a two-room type, and a two-night stay ten days out."""

	def setUp(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		frappe.local.lang = "en"
		self.property = frappe.get_doc({"doctype": "Property",
			"property_name": "TEST Roomless " + frappe.generate_hash(length=8),
			"booking_engine_enabled": 1}).insert(ignore_permissions=True).name
		self.room_type = self.make_type("STD", "Standard", ["101", "102"])
		self.guest = frappe.get_doc({"doctype": "Guest",
			"first_name": "Roomless Guest"}).insert(ignore_permissions=True).name
		self.ci = self.day(10)
		self.co = self.day(12)

	def day(self, n):
		return str(add_days(nowdate(), n))

	def make_type(self, code, name, numbers=(), category="Private"):
		room_type = frappe.get_doc({"doctype": "Room Type", "property": self.property,
			"room_type_code": code, "room_type_name": name, "room_category": category,
			"base_price": 1000, "adults_capacity": 2}).insert(ignore_permissions=True).name
		for number in numbers:
			frappe.get_doc({"doctype": "Room", "property": self.property,
				"room_type": room_type, "room_number": number}).insert(ignore_permissions=True)
		return room_type

	def stay(self, status="Confirmed", room_type=None, room=None, ci=None, co=None):
		"""Saved the way a channel booking is: no room unless one is named."""
		return frappe.get_doc({"doctype": "Reservation", "property": self.property,
			"room_type": room_type or self.room_type, "guest": self.guest, "room": room,
			"status": status, "check_in_date": ci or self.ci,
			"check_out_date": co or self.co, "adults": 2}).insert(ignore_permissions=True)

	def page(self, room_type=None, ci=None, co=None):
		"""(rooms_left, available) as the booking page is told."""
		rows = search_stay(self.property, ci or self.ci, co or self.co, 2, 0)
		row = next(r for r in rows if r["room_type"] == (room_type or self.room_type))
		return row["rooms_left"], row["available"]

	def calendar(self, room_type=None):
		out = availability_calendar(self.property, start_date=self.ci, days=2)
		row = next(r for r in out["room_types"]
		           if r["room_type"] == (room_type or self.room_type))
		return [c["available"] for c in row["cells"]]

	def channel(self, days=2):
		conn = frappe.get_doc({"doctype": "Channel Manager Connection",
			"property": self.property, "provider": "AioSell", "active": 1,
			"external_property_id": frappe.generate_hash(length=8)}).insert(ignore_permissions=True)
		frappe.get_doc({"doctype": "Channel Room Mapping", "connection": conn.name,
			"room_type": self.room_type, "external_room_id": "std",
			"external_rate_id": "std-rate"}).insert(ignore_permissions=True)
		snapshot = cm.ari_snapshot(self.property, conn.name, days=days, start=self.ci,
		                           with_rates=False)
		return [d["available"] for d in snapshot[0]["days"]]


class TestStaysWithoutARoom(_Case):
	def test_the_booking_page_has_nothing_left_when_they_fill_the_type(self):
		self.stay()
		self.stay()
		self.assertEqual(self.page(), (0, False))

	def test_they_come_off_on_top_of_stays_that_have_a_room(self):
		triple = self.make_type("TRP", "Triple", ["201", "202", "203"])
		room = frappe.db.get_value("Room", {"room_type": triple, "room_number": "201"})
		self.stay(room_type=triple, room=room)
		self.stay(room_type=triple)
		self.assertEqual(self.page(triple), (1, True))
		self.assertEqual(self.calendar(triple), [1, 1])

	def test_each_night_is_counted_on_its_own(self):
		"""Two stays on different nights leave one room for the whole stay."""
		self.stay(co=self.day(11))
		self.stay(ci=self.day(11))
		self.assertEqual(self.page(), (1, True))
		self.assertEqual(self.calendar(), [1, 1])

	def test_the_busiest_night_decides_a_longer_stay(self):
		self.stay(ci=self.day(11))
		self.assertEqual(self.page(), (1, True))
		self.assertEqual(self.calendar(), [2, 1])

	def test_a_departure_on_the_arrival_day_takes_nothing(self):
		self.stay(ci=self.day(8), co=self.ci)
		self.assertEqual(self.page(), (2, True))

	def test_stays_that_hold_no_room_take_nothing(self):
		self.stay(status="Requested")
		self.stay(status="Waitlist")
		self.assertEqual(self.page(), (2, True))
		self.assertEqual(self.calendar(), [2, 2])

	def test_unpaid_holds_come_off_the_page_the_calendar_and_the_channels(self):
		self.stay(status="Pending Payment")
		self.stay(status="Held")
		self.assertEqual(self.page(), (0, False))
		self.assertEqual(self.calendar(), [0, 0])
		self.assertEqual(self.channel(), [0, 0])

	def test_channels_count_them_on_top_of_a_blocked_room(self):
		room = frappe.db.get_value("Room", {"room_type": self.room_type, "room_number": "101"})
		frappe.get_doc({"doctype": "Room Block", "property": self.property, "room": room,
			"from_date": self.ci, "to_date": self.co, "block_status": "Active",
			"reason": "Maintenance"}).insert(ignore_permissions=True)
		self.stay()
		self.assertEqual(self.page(), (0, False))
		self.assertEqual(self.channel(), [0, 0])

	def test_the_channels_count_each_night_on_its_own(self):
		self.stay(co=self.day(11))
		self.stay(co=self.day(12))
		self.assertEqual(self.channel(days=3), [0, 1, 2])

	def test_the_channels_get_no_overbooking_allowance_around_a_blocked_room(self):
		"""Three rooms, one blocked, one stay: one room is physically free."""
		frappe.db.set_value("Room Type", self.room_type, "overbooking_pct", 50)
		frappe.get_doc({"doctype": "Room", "property": self.property,
			"room_type": self.room_type, "room_number": "103"}).insert(ignore_permissions=True)
		room = frappe.db.get_value("Room", {"room_type": self.room_type, "room_number": "101"})
		frappe.get_doc({"doctype": "Room Block", "property": self.property, "room": room,
			"from_date": self.ci, "to_date": self.co, "block_status": "Active",
			"reason": "Maintenance"}).insert(ignore_permissions=True)
		self.stay()
		self.assertEqual(self.channel(), [1, 1])

	def test_the_channel_push_counts_unsold_rooms_once_per_room_type(self):
		"""Once for the whole window, not once a day: the push covers 90 days."""
		with patch.object(siu_availability, "unsold_by_night",
		                  wraps=siu_availability.unsold_by_night) as counted, \
				patch.object(cm, "_sellable_by_night",
				             wraps=cm._sellable_by_night) as per_night:
			self.assertEqual(self.channel(days=6), [2] * 6)
		self.assertEqual((counted.call_count, per_night.call_count), (1, 1))

	def test_the_overbooking_allowance_is_still_offered(self):
		"""The page offers what saving the booking would accept."""
		frappe.db.set_value("Room Type", self.room_type, "overbooking_pct", 50)
		self.stay()
		self.stay()
		self.assertEqual(self.page(), (1, True))
		self.stay()
		self.assertEqual(self.page(), (0, False))

	def test_the_desk_can_still_give_such_a_stay_a_room(self):
		"""The room picker lists physical rooms: it is how these stays get one."""
		first = self.stay()
		self.stay()
		free = available_rooms(self.property, self.room_type, self.ci, self.co)
		self.assertEqual(len(free), 2)
		first.room = free[0]["name"]
		first.save()
		self.assertEqual(self.page(), (0, False))

	def test_multi_property_search_and_trip_quote_count_them(self):
		self.stay()
		self.stay()
		found = crs_search(self.ci, self.co)["properties"]
		self.assertNotIn(self.property, [r["property"] for r in found])
		quoted = quote_itinerary([{"property": self.property, "room_type": self.room_type,
			"check_in_date": self.ci, "check_out_date": self.co}])
		self.assertEqual(quoted["legs"][0]["available"], 0)

	def test_a_group_cannot_block_rooms_they_have_taken(self):
		self.stay()
		self.stay()
		with self.assertRaisesRegex(frappe.ValidationError, "Not enough rooms"):
			create_group_with_rooming_list(self.property, "Late Group", self.ci, self.co,
				[{"room_type": self.room_type, "rooms_blocked": 1}])

	def test_a_block_that_differs_by_night_is_held_to_each_night(self):
		self.stay(ci=self.day(11))
		self.stay(ci=self.day(11))
		with self.assertRaisesRegex(frappe.ValidationError, "Not enough rooms"):
			create_group_with_rooming_list(self.property, "Uneven Group", self.ci, self.co,
				[{"room_type": self.room_type,
				  "nightly_counts": {self.ci: 2, self.day(11): 1}}])

	def test_a_group_cannot_move_its_block_onto_them(self):
		group = create_group_with_rooming_list(
			self.property, "Moving Group", self.day(20), self.day(22),
			[{"room_type": self.room_type, "rooms_blocked": 1}])["group_booking"]
		self.stay()
		self.stay()
		with self.assertRaisesRegex(frappe.ValidationError, "not free on those dates"):
			group_amend_dates(group, self.ci, self.co)

	def test_the_waitlist_is_not_called_ready(self):
		self.stay()
		self.stay()
		waiting = create_booking(property=self.property, room_type=self.room_type,
			check_in_date=self.ci, check_out_date=self.co, guest_name="Wait Guest",
			phone="+91 90000 71001", waitlist=1)["reservation"]
		self.assertNotIn(waiting, [r["name"] for r in waitlist_ready(self.property)])

	def test_the_request_inbox_says_there_is_no_room(self):
		request = self.stay(status="Requested").name
		self.stay()
		self.stay()
		row = next(r for r in booking_requests(self.property)["requests"]
		           if r["name"] == request)
		self.assertEqual((row["rooms_free"], row["can_accept"]), (0, False))


class TestWholeVilla(_Case):
	"""An entire-place type with no rooms of its own takes the member rooms."""

	def setUp(self):
		super().setUp()
		self.villa = self.make_type("VILLA", "Entire Property", category="Villa")

	def villa_stay(self, **dates):
		return self.stay(room_type=self.villa, **dates)

	def live_villa_stays(self):
		return frappe.db.count("Reservation", {"room_type": self.villa,
			"status": ("in", ["Confirmed", "Checked In", "Held", "Pending Payment"])})

	def searched(self):
		"""How many of the villa the multi-property search offers (0: not listed)."""
		return next((row["available"]
			for found in crs_search(self.ci, self.co)["properties"]
			if found["property"] == self.property
			for row in found["room_types"] if row["room_type"] == self.villa), 0)

	def quoted(self):
		leg = {"property": self.property, "room_type": self.villa,
		       "check_in_date": self.ci, "check_out_date": self.co}
		return quote_itinerary([leg])["legs"][0]["available"]

	def waitlisted(self):
		return create_booking(property=self.property, room_type=self.villa,
			check_in_date=self.ci, check_out_date=self.co, guest_name="Wait Villa",
			phone="+91 90000 73001", waitlist=1)["reservation"]

	def ready(self):
		return [row["name"] for row in waitlist_ready(self.property)]

	def block_villa(self, ci=None, co=None, guests=None, **block):
		return create_group_with_rooming_list(
			self.property, "Villa Group", ci or self.ci, co or self.co,
			[{"room_type": self.villa, "rooms_blocked": 1, **block}], guests=guests)

	def test_a_free_villa_is_found_by_the_search_and_the_trip_quote(self):
		self.assertEqual((self.searched(), self.quoted()), (1, 1))

	def test_a_free_villa_waitlist_is_ready_and_can_be_confirmed(self):
		waiting = self.waitlisted()
		self.assertIn(waiting, self.ready())
		promote_waitlist(waiting)
		self.assertEqual(frappe.db.get_value("Reservation", waiting, "status"), "Confirmed")
		self.assertEqual(self.searched(), 0)

	def test_a_waitlisted_villa_cannot_be_confirmed_over_a_booked_one(self):
		waiting = self.waitlisted()
		self.villa_stay()
		with self.assertRaisesRegex(frappe.ValidationError, "sold out"):
			promote_waitlist(waiting)

	def test_a_group_can_block_the_free_villa_and_name_its_guest(self):
		out = self.block_villa(guests=[{"room_type": self.villa,
			"guest_name": "Villa Host", "phone": "+91 90000 73002"}])
		self.assertEqual((len(out["created"]), out["skipped"]), (1, []))

	def test_a_block_that_differs_by_night_can_take_the_free_villa(self):
		out = self.block_villa(nightly_counts={self.ci: 1, self.day(11): 0})
		self.assertEqual(out["status"], "Confirmed")

	def test_a_group_can_move_its_villa_block_to_free_dates(self):
		group = self.block_villa(ci=self.day(20), co=self.day(22))["group_booking"]
		group_amend_dates(group, self.ci, self.co)
		self.assertEqual(
			str(frappe.db.get_value("Group Booking", group, "check_in_date")), self.ci)

	def test_a_booked_villa_is_offered_nowhere(self):
		group = self.block_villa(ci=self.day(20), co=self.day(22))["group_booking"]
		self.villa_stay()
		self.assert_villa_off_sale(group)

	def test_a_booked_member_room_takes_the_villa_off_sale_there_too(self):
		group = self.block_villa(ci=self.day(20), co=self.day(22))["group_booking"]
		self.stay()
		self.assert_villa_off_sale(group)

	def assert_villa_off_sale(self, moving_group):
		self.assertEqual((self.searched(), self.quoted()), (0, 0))
		self.assertNotIn(self.waitlisted(), self.ready())
		with self.assertRaisesRegex(frappe.ValidationError, "Not enough rooms"):
			self.block_villa()
		with self.assertRaisesRegex(frappe.ValidationError, "not free on those dates"):
			group_amend_dates(moving_group, self.ci, self.co)

	def test_a_second_guest_cannot_book_it_for_the_same_dates(self):
		"""Through the booking page's own call, as two guests would."""
		def guest_books(number):
			# __wrapped__ skips the per-visitor rate limit; commit is held back
			# so the test's data rolls back
			with patch.object(frappe.db, "commit"):
				return book.__wrapped__(self.property, self.villa, self.ci, self.co,
					f"Villa Guest {number}", f"+91 90000 7200{number}")

		self.assertEqual(guest_books(1)["status"], "Confirmed")
		with self.assertRaisesRegex(frappe.ValidationError, "sold out"):
			guest_books(2)
		self.assertEqual(self.live_villa_stays(), 1)

	def test_an_overlap_of_one_night_is_refused(self):
		self.villa_stay()
		with self.assertRaisesRegex(frappe.ValidationError, "sold out"):
			self.villa_stay(ci=self.day(11), co=self.day(13))

	def test_back_to_back_stays_are_allowed(self):
		self.villa_stay()
		self.villa_stay(ci=self.co, co=self.day(14))
		self.assertEqual(self.live_villa_stays(), 2)

	def test_a_stay_cannot_be_moved_onto_booked_dates(self):
		self.villa_stay()
		other = self.villa_stay(ci=self.day(15), co=self.day(17))
		with self.assertRaisesRegex(frappe.ValidationError, "sold out"):
			amend_stay(other.name, self.ci, self.co, confirm_price=1)

	def test_stays_already_booked_twice_can_still_be_worked(self):
		"""Data saved before this check must not lock the desk out."""
		first = self.villa_stay(ci=self.day(0), co=self.day(2))
		second = self.villa_stay(ci=self.day(5), co=self.day(7))
		frappe.db.set_value("Reservation", second.name,
			{"check_in_date": self.day(0), "check_out_date": self.day(2)})
		first.reload()
		first.special_requests = "late arrival"
		first.save()
		first.status = "Checked In"
		first.save()
		second.reload()
		second.status = "Cancelled"
		second.cancellation_reason = "Other"
		frappe.flags.kamra_cancelling = True
		try:
			second.save()
		finally:
			frappe.flags.kamra_cancelling = False
		self.assertEqual(self.live_villa_stays(), 1)

	def test_the_request_inbox_knows_the_villa_is_taken(self):
		self.villa_stay()
		request = self.villa_stay(status="Requested").name
		row = next(r for r in booking_requests(self.property)["requests"]
		           if r["name"] == request)
		self.assertEqual((row["rooms_free"], row["can_accept"]), (0, False))

	def test_a_villa_with_its_own_room_shows_one_then_none(self):
		own = self.make_type("OWN", "Own-room Villa", ["V1"], category="Villa")
		self.assertEqual(self.page(own), (1, True))
		self.stay(room_type=own)
		self.assertEqual(self.page(own), (0, False))
		self.assertEqual(self.calendar(own), [0, 0])
