"""Room.room_type keeps its individual Sellable Unit in step (#548)."""

from __future__ import annotations

import frappe

from kamra.api import available_rooms
from kamra.siu.units import ensure_individual_siu, sync_individual_siu_room_type
from kamra.tests.audit_fixtures import (
	PROP_A, TODAY, AuditTestCase, d, make_property, make_room, make_room_type,
)


class TestSiuRoomTypeSync(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		make_property(PROP_A, business_date=TODAY)
		self.rt_a = make_room_type(PROP_A, "SYA", base_price=900)
		self.rt_b = make_room_type(PROP_A, "SYB", base_price=1200)

	def test_changing_room_type_updates_individual_siu(self):
		room = make_room(PROP_A, self.rt_a, "SY101")
		unit = ensure_individual_siu(room)
		self.assertEqual(
			frappe.db.get_value("Sellable Unit", unit, "room_type"), self.rt_a)
		self.assertEqual(
			frappe.db.get_value("Sellable Unit", unit, "competition_group"),
			f"{PROP_A}::{self.rt_a}")

		doc = frappe.get_doc("Room", room)
		doc.room_type = self.rt_b
		doc.save(ignore_permissions=True)

		self.assertEqual(
			frappe.db.get_value("Sellable Unit", unit, "room_type"), self.rt_b)
		self.assertEqual(
			frappe.db.get_value("Sellable Unit", unit, "competition_group"),
			f"{PROP_A}::{self.rt_b}")

	def test_availability_follows_the_new_room_type(self):
		"""Walk-in listed the room under the old type and save failed (#548)."""
		room = make_room(PROP_A, self.rt_a, "SY111")
		ci, co = d(1), d(2)
		self.assertIn(room, [r["name"] for r in available_rooms(
			PROP_A, self.rt_a, ci, co)])

		doc = frappe.get_doc("Room", room)
		doc.room_type = self.rt_b
		doc.save(ignore_permissions=True)

		self.assertNotIn(room, [r["name"] for r in available_rooms(
			PROP_A, self.rt_a, ci, co)])
		self.assertIn(room, [r["name"] for r in available_rooms(
			PROP_A, self.rt_b, ci, co)])

	def test_villa_own_units_stay_off_estate_competition(self):
		"""A Villa type with its own Rooms must not join estate competition
		on create — otherwise the unassigned stay locks its own picker."""
		villa = make_room_type(PROP_A, "VIL", base_price=20000,
		                       room_category="Villa", room_type_name="UT Villa")
		from kamra.siu.units import ensure_whole_property_siu
		ensure_whole_property_siu(villa)
		room = make_room(PROP_A, villa, "VU1")
		unit = ensure_individual_siu(room)
		self.assertEqual(
			frappe.db.get_value("Sellable Unit", unit, "competition_group"),
			f"{PROP_A}::{villa}")
		ci, co = d(1), d(2)
		self.assertIn(room, [r["name"] for r in available_rooms(
			PROP_A, villa, ci, co)])

	def test_shared_unit_refuses_room_type_change(self):
		r1 = make_room(PROP_A, self.rt_a, "SY201")
		r2 = make_room(PROP_A, self.rt_a, "SY202")
		# drop auto individual units; put both rooms on one composite SIU
		for room in (r1, r2):
			for (parent,) in frappe.db.sql(
				"SELECT parent FROM `tabSellable Unit Room` WHERE room=%s", room):
				frappe.delete_doc("Sellable Unit", parent, ignore_permissions=True)
		frappe.get_doc({
			"doctype": "Sellable Unit",
			"property": PROP_A,
			"unit_name": "Connecting SY",
			"unit_kind": "composite",
			"is_active": 1,
			"room_type": self.rt_a,
			"physical_rooms": [{"room": r1}, {"room": r2}],
		}).insert(ignore_permissions=True)

		doc = frappe.get_doc("Room", r1)
		doc.room_type = self.rt_b
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)

	def test_sync_helper_creates_missing_unit(self):
		room = make_room(PROP_A, self.rt_a, "SY301")
		# strip the auto-created unit so sync must recreate
		parent = frappe.db.sql(
			"SELECT parent FROM `tabSellable Unit Room` WHERE room=%s", room)
		if parent:
			frappe.delete_doc("Sellable Unit", parent[0][0], ignore_permissions=True)
		name = sync_individual_siu_room_type(room)
		self.assertTrue(name)
		self.assertEqual(
			frappe.db.get_value("Sellable Unit", name, "room_type"), self.rt_a)
