"""Floor master: the patch, auto-create on save, rename, delete, the board
payloads and the bulk Add rooms endpoint."""

from __future__ import annotations

import frappe

from kamra import floors, rooms
from kamra.patches.v47 import create_floors_from_rooms
from kamra.tests.audit_fixtures import (
	PROP_A, PROP_B, AuditTestCase, ensure_user, make_property, make_room_type,
)


def _room(prop, rt, number, floor=None):
	return frappe.get_doc({"doctype": "Room", "property": prop, "room_type": rt,
	                       "room_number": number, "floor": floor}).insert(ignore_permissions=True)


def _names(prop):
	return {f.floor_name: f.sort_order for f in frappe.get_all(
		"Floor", filters={"property": prop}, fields=["floor_name", "sort_order"])}


class TestFloors(AuditTestCase):
	def setUp(self):
		super().setUp()
		make_property(PROP_A)
		make_property(PROP_B)
		self.rt = make_room_type(PROP_A, "FLR")
		self.rtb = make_room_type(PROP_B, "FLR")

	def test_save_creates_floor_once(self):
		_room(PROP_A, self.rt, "F101", " 1 ")
		_room(PROP_A, self.rt, "F102", "1")
		self.assertEqual(_names(PROP_A), {"1": 10})
		self.assertEqual(frappe.db.get_value("Room", f"{PROP_A}-F101", "floor"), "1")

	def test_blank_floor_makes_none(self):
		_room(PROP_A, self.rt, "F103", "")
		self.assertEqual(_names(PROP_A), {})

	def test_same_name_in_two_properties(self):
		_room(PROP_A, self.rt, "F104", "2")
		_room(PROP_B, self.rtb, "F104", "2")
		self.assertEqual(_names(PROP_A), {"2": 20})
		self.assertEqual(_names(PROP_B), {"2": 20})

	def test_unique_per_property(self):
		_room(PROP_A, self.rt, "F105", "3")
		with self.assertRaises((frappe.ValidationError, frappe.DuplicateEntryError)):
			frappe.get_doc({"doctype": "Floor", "property": PROP_A, "floor_name": "3"}).insert()
		other = frappe.get_doc({"doctype": "Floor", "property": PROP_A,
		                        "floor_name": "33"}).insert()
		other.floor_name = "3"
		with self.assertRaises(frappe.ValidationError):
			other.save()

	def test_rename_moves_rooms(self):
		_room(PROP_A, self.rt, "F106", "4")
		_room(PROP_B, self.rtb, "F106", "4")
		f = frappe.get_doc("Floor", f"{PROP_A}-4")
		f.floor_name = "Fourth"
		f.save()
		self.assertEqual(frappe.db.get_value("Room", f"{PROP_A}-F106", "floor"), "Fourth")
		self.assertEqual(frappe.db.get_value("Room", f"{PROP_B}-F106", "floor"), "4")

	def test_delete_and_disable_refused_with_rooms(self):
		_room(PROP_A, self.rt, "F107", "5")
		f = frappe.get_doc("Floor", f"{PROP_A}-5")
		with self.assertRaises(frappe.ValidationError):
			f.delete()
		f.disabled = 1
		with self.assertRaises(frappe.ValidationError):
			f.save()
		frappe.db.delete("Room", {"name": f"{PROP_A}-F107"})
		frappe.get_doc("Floor", f"{PROP_A}-5").delete()
		self.assertFalse(frappe.db.exists("Floor", f"{PROP_A}-5"))

	def test_disabled_floor_reenabled_when_used(self):
		f = frappe.get_doc({"doctype": "Floor", "property": PROP_A, "floor_name": "6",
		                    "disabled": 1}).insert()
		_room(PROP_A, self.rt, "F108", "6")
		self.assertEqual(frappe.db.get_value("Floor", f.name, "disabled"), 0)

	def test_patch_natural_order_idempotent_per_property(self):
		for n, fl in (("P1", "10"), ("P2", "2"), ("P3", "Floor 3"), ("P4", "Roof"),
		              ("P5", "Annex")):
			_room(PROP_A, self.rt, n, fl)
		_room(PROP_B, self.rtb, "P1", "2")
		frappe.db.delete("Floor", {"property": ("in", [PROP_A, PROP_B])})
		create_floors_from_rooms.execute()
		create_floors_from_rooms.execute()
		a = _names(PROP_A)
		self.assertEqual(sorted(a, key=a.get), ["2", "Floor 3", "10", "Annex", "Roof"])
		self.assertEqual(frappe.db.count("Floor", {"property": PROP_A}), 5)
		self.assertEqual(_names(PROP_B), {"2": 20})

	def test_board_payloads(self):
		_room(PROP_A, self.rt, "B1", "10")
		_room(PROP_A, self.rt, "B2", "2")
		out = rooms.rooms_board(PROP_A)
		self.assertEqual({r["room_number"]: r["floor"] for r in out["rooms"]},
		                 {"B1": "10", "B2": "2"})
		self.assertEqual([f["name"] for f in out["floors"]], ["2", "10"])
		self.assertEqual(set(out["floors"][0]), {"name", "sort_order"})
		self.assertEqual([f["name"] for f in floors.floors_for(PROP_B)], [])
		from kamra.api import room_board
		hk = room_board(PROP_A)
		self.assertEqual([f["name"] for f in hk["floors"]], ["2", "10"])
		self.assertEqual({r["floor"] for r in hk["rooms"]}, {"10", "2"})
		self.assertTrue(any(t["name"] == self.rt for t in hk["room_types"]))

	def test_add_rooms_range_duplicates_and_preview(self):
		_room(PROP_A, self.rt, "203", "2")
		pv = floors.add_rooms(PROP_A, "2", self.rt, 201, 205, preview=1)
		self.assertEqual(pv["create"], ["201", "202", "204", "205"])
		self.assertEqual(pv["skipped"], ["203"])
		self.assertFalse(frappe.db.exists("Room", f"{PROP_A}-201"))
		done = floors.add_rooms(PROP_A, "2", self.rt, 201, 205)
		self.assertEqual(done["created"], 4)
		self.assertEqual(frappe.db.get_value("Room", f"{PROP_A}-201", "floor"), "2")
		self.assertEqual(floors.add_rooms(PROP_A, "2", self.rt, 201, 205)["created"], 0)
		p = floors.add_rooms(PROP_A, "G", self.rt, 1, 2, prefix="V", preview=1)
		self.assertEqual(p["create"], ["V1", "V2"])

	def test_add_rooms_bad_input(self):
		with self.assertRaises(frappe.ValidationError):
			floors.add_rooms(PROP_A, "2", self.rt, 210, 201)
		with self.assertRaises(frappe.ValidationError):
			floors.add_rooms(PROP_A, "2", self.rt, "a", 3)
		with self.assertRaises(frappe.ValidationError):
			floors.add_rooms(PROP_A, "2", self.rtb, 1, 2)  # other property's type

	def test_add_rooms_scope_and_role(self):
		email = ensure_user("floors-admin@example.com", ["Hotel Admin"])
		frappe.get_doc({"doctype": "User Permission", "user": email, "allow": "Property",
		                "for_value": PROP_B}).insert(ignore_permissions=True)
		frappe.clear_cache(user=email)
		frappe.set_user(email)  # nosemgrep: frappe-setuser -- test fixture
		with self.assertRaises(frappe.PermissionError):
			floors.add_rooms(PROP_A, "2", self.rt, 1, 2)
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		desk = ensure_user("floors-hk@example.com", ["Housekeeping"])
		frappe.set_user(desk)  # nosemgrep: frappe-setuser -- test fixture
		with self.assertRaises(frappe.PermissionError):
			floors.add_rooms(PROP_A, "2", self.rt, 1, 2)
