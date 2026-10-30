"""Group bookings: rooms booked by count, the rooming list named in one go,
and check-in / cancel / date changes for the whole group or picked rooms."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from kamra.api import (create_group_booking, group_amend_dates, group_assign_rooms,
                       group_cancel, group_check_in, group_detail, set_rooming_names)


class GroupActionsTestCase(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		frappe.local.lang = "en"
		self.property = frappe.get_doc({"doctype": "Property",
			"property_name": "TEST GRP " + frappe.generate_hash(length=8),
			"country": "Uganda", "currency": "UGX"}).insert(ignore_permissions=True).name
		self.room_type = frappe.get_doc({"doctype": "Room Type", "property": self.property,
			"room_type_code": "DLX", "room_type_name": "Deluxe", "base_price": 1000,
			"adults_capacity": 2}).insert(ignore_permissions=True).name
		self.rooms = [frappe.get_doc({"doctype": "Room", "property": self.property,
			"room_type": self.room_type, "room_number": n}).insert(ignore_permissions=True).name
			for n in ("201", "202", "203", "204")]

	def group(self, count=3):
		out = create_group_booking(
			self.property, "Offsite", nowdate(), str(add_days(nowdate(), 2)),
			[{"room_type": self.room_type, "count": count, "adults": 2}],
			"Lead Guest", phone="+256700000001")
		self.assertEqual(out["skipped"], [])
		return out["group_booking"], out["created"]

	def status(self, res):
		return frappe.db.get_value("Reservation", res, "status")

	def test_count_books_that_many_rooms(self):
		gb, created = self.group(count=3)
		self.assertEqual(len(created), 3)
		self.assertEqual(len(group_detail(gb)["rooming_list"]), 3)

	def test_rooming_names_give_each_room_its_own_guest(self):
		gb, (r1, r2, r3) = self.group()
		lead = frappe.db.get_value("Reservation", r1, "guest")
		out = set_rooming_names(gb, [
			{"reservation": r2, "guest_name": "Priya Sharma", "phone": ""},
			{"reservation": r3, "guest_name": "Rahul Mehta", "phone": "+256700000002"},
			{"reservation": r1, "guest_name": "Lead Guest", "phone": ""},
		])["results"]
		self.assertFalse([x for x in out if x.get("error")], out)
		self.assertTrue(next(x for x in out if x["reservation"] == r1).get("unchanged"))
		self.assertEqual(frappe.db.get_value("Reservation", r2, "guest_name"), "Priya Sharma")
		g2, g3 = (frappe.db.get_value("Reservation", r, "guest") for r in (r2, r3))
		self.assertNotIn(lead, (g2, g3))
		self.assertNotEqual(g2, g3)
		self.assertEqual(frappe.db.get_value("Guest", g3, "phone"), "+256700000002")
		# the room's own guest folio follows the new name
		for folio in frappe.get_all("Folio", filters={"reservation": r2,
				"folio_type": "Guest", "status": "Open"}, pluck="name"):
			self.assertEqual(frappe.db.get_value("Folio", folio, "guest"), g2)

	def test_rooming_names_refuse_another_groups_room(self):
		gb, _ = self.group(count=1)
		_, (other,) = self.group(count=1)
		out = set_rooming_names(gb, [{"reservation": other, "guest_name": "Intruder"}])
		self.assertEqual(out["results"], [])
		self.assertNotEqual(frappe.db.get_value("Reservation", other, "guest_name"), "Intruder")

	def test_check_in_gives_a_room_to_rooms_without_a_number(self):
		gb, (r1, r2, _r3) = self.group()
		for r in (r1, r2, _r3):
			frappe.db.set_value("Reservation", r, "room", None)
		doc = frappe.get_doc("Reservation", r1)
		doc.room = self.rooms[0]
		doc.save()
		out = {x["reservation"]: x for x in group_check_in(gb, [r1, r2])["results"]}
		self.assertEqual(set(out), {r1, r2})
		self.assertEqual([self.status(r) for r in (r1, r2)], ["Checked In", "Checked In"])
		r2_room = frappe.db.get_value("Reservation", r2, "room")
		self.assertTrue(r2_room)
		self.assertNotEqual(r2_room, self.rooms[0])

	def test_assign_rooms_gives_each_room_its_own_number(self):
		gb, created = self.group()
		for r in created:
			frappe.db.set_value("Reservation", r, "room", None)
		out = group_assign_rooms(gb)["results"]
		self.assertEqual([x.get("assigned") for x in out], [1, 1, 1], out)
		rooms = [frappe.db.get_value("Reservation", r, "room") for r in created]
		self.assertEqual(len(set(rooms)), 3)

	def test_a_group_where_no_room_books_leaves_nothing_behind(self):
		before = frappe.db.count("Group Booking", {"property": self.property})
		with self.assertRaises(frappe.ValidationError):
			create_group_booking(
				self.property, "Too big", nowdate(), str(add_days(nowdate(), 2)),
				[{"room_type": "No Such Type", "count": 2}], "Lead Guest")
		self.assertEqual(frappe.db.count("Group Booking", {"property": self.property}), before)

	def test_cancel_picked_rooms_keeps_the_group(self):
		gb, (r1, r2, r3) = self.group()
		group_cancel(gb, [r1], waive_fee=1)
		self.assertEqual([self.status(r) for r in (r1, r2, r3)],
		                 ["Cancelled", "Confirmed", "Confirmed"])
		self.assertEqual(frappe.db.get_value("Group Booking", gb, "status"), "Confirmed")

	def test_cancel_all_cancels_the_group(self):
		gb, created = self.group()
		out = group_cancel(gb, waive_fee=1)["results"]
		self.assertFalse([x for x in out if x.get("error")], out)
		self.assertEqual({self.status(r) for r in created}, {"Cancelled"})
		self.assertEqual(frappe.db.get_value("Group Booking", gb, "status"), "Cancelled")

	def test_amend_all_moves_rooms_and_group(self):
		gb, created = self.group(count=2)
		ci, co = str(add_days(nowdate(), 1)), str(add_days(nowdate(), 4))
		out = group_amend_dates(gb, ci, co, confirm_price=1)["results"]
		self.assertFalse([x for x in out if x.get("error")], out)
		for r in created:
			d = frappe.db.get_value("Reservation", r,
			                        ["check_in_date", "check_out_date"], as_dict=True)
			self.assertEqual((str(d.check_in_date), str(d.check_out_date)), (ci, co))
		g = frappe.db.get_value("Group Booking", gb,
		                        ["check_in_date", "check_out_date"], as_dict=True)
		self.assertEqual((str(g.check_in_date), str(g.check_out_date)), (ci, co))
