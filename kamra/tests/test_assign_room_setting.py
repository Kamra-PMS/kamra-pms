"""The "Allow assigning room while making the reservation" setting (#593).

On (the default): create_booking hands out a free room, as it always did.
Off: the reservation holds a room type only and the room is chosen at
check-in. A room the caller names (a walk-in) is still kept, and the stay
still counts against the room type so the hotel cannot oversell.
"""

from __future__ import annotations

import json

import frappe

from kamra import api
from kamra.settings import SETTINGS, clear_cache, get_setting
from kamra.tests.audit_fixtures import (
	PROP_A,
	TODAY,
	AuditTestCase,
	d,
	make_property,
	make_room,
	make_room_type,
)

KEY = "assign_room_on_booking"


def set_setting(prop: str, key: str, value) -> None:
	name = frappe.db.get_value("Property Setting", {"property": prop, "setting_key": key})
	if name:
		frappe.db.set_value("Property Setting", name, "value", json.dumps(value))
	else:
		frappe.get_doc({"doctype": "Property Setting", "property": prop,
		                "setting_key": key, "value": json.dumps(value)}
		               ).insert(ignore_permissions=True)
	clear_cache(prop)


class TestAssignRoomSetting(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date")
		make_property(PROP_A, business_date=TODAY)
		frappe.db.delete("Property Setting", {"property": PROP_A})
		clear_cache(PROP_A)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")
		self.room2 = make_room(PROP_A, self.rt, "102")

	def book(self, n: int = 1, **extra):
		return api.create_booking(
			property=PROP_A, room_type=self.rt, check_in_date=d(3), check_out_date=d(5),
			guest_name=f"UT Assign Guest {n}", phone=f"+91 90000 5{n:04d}", **extra)

	def test_the_setting_is_in_the_front_desk_page_and_on_by_default(self):
		self.assertEqual(SETTINGS[KEY][0].id, "front-desk")
		self.assertEqual(get_setting(PROP_A, KEY), 1)

	def test_on_assigns_a_room(self):
		out = self.book()
		self.assertIn(out["room"], (self.room, self.room2))

	def test_off_leaves_the_room_unassigned(self):
		set_setting(PROP_A, KEY, 0)
		out = self.book()
		self.assertFalse(out["room"])
		self.assertFalse(frappe.db.get_value("Reservation", out["reservation"], "room"))

	def test_off_still_counts_the_stay_against_the_room_type(self):
		set_setting(PROP_A, KEY, 0)
		self.book(1)
		self.book(2)
		with self.assertRaises(frappe.ValidationError):
			self.book(3)

	def test_off_keeps_a_room_the_caller_names(self):
		set_setting(PROP_A, KEY, 0)
		out = self.book(room=self.room2)
		self.assertEqual(out["room"], self.room2)

	def test_turning_it_back_on_assigns_again(self):
		set_setting(PROP_A, KEY, 0)
		self.assertFalse(self.book(1)["room"])
		set_setting(PROP_A, KEY, 1)
		self.assertTrue(self.book(2)["room"])
