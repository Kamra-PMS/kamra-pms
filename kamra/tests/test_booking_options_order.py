"""booking_options room-type order is stable and cheapest-first (#549)."""

from __future__ import annotations

import frappe

from kamra.api import available_rooms, booking_options
from kamra.tests.audit_fixtures import (
	PROP_A, TODAY, AuditTestCase, d, make_property, make_room, make_room_type,
)


class TestBookingOptionsOrder(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		make_property(PROP_A, business_date=TODAY)
		# same price → name must break the tie; Alpha before Zulu
		self.rt_z = make_room_type(PROP_A, "ZUL", base_price=1000,
		                           room_type_name="Zulu")
		self.rt_a = make_room_type(PROP_A, "ALP", base_price=1000,
		                           room_type_name="Alpha")
		self.rt_dear = make_room_type(PROP_A, "DLX", base_price=2500,
		                              room_type_name="Deluxe")
		# only the dear type has inventory
		make_room(PROP_A, self.rt_dear, "BO101")

	def test_room_types_sorted_by_price_then_name(self):
		names = [rt["name"] for rt in booking_options(PROP_A)["room_types"]]
		# Alpha and Zulu share base_price; Alpha comes first by name
		self.assertEqual(names[:2], [self.rt_a, self.rt_z])
		self.assertEqual(names[-1], self.rt_dear)

	def test_empty_types_have_no_available_rooms(self):
		ci, co = d(1), d(2)
		self.assertEqual(available_rooms(PROP_A, self.rt_a, ci, co), [])
		self.assertEqual(available_rooms(PROP_A, self.rt_z, ci, co), [])
		self.assertEqual(
			[r["name"] for r in available_rooms(PROP_A, self.rt_dear, ci, co)],
			[f"{PROP_A}-BO101"])
