"""The Today screen's room board shows a room held out of service, as the full board does."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from kamra.api import front_desk_snapshot


class TodayBoardBlocksTestCase(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		self.property = frappe.get_doc({"doctype": "Property",
			"property_name": "TEST OOS " + frappe.generate_hash(length=8)}).insert(ignore_permissions=True).name
		rt = frappe.get_doc({"doctype": "Room Type", "property": self.property,
			"room_type_code": "STD", "room_type_name": "Standard", "base_price": 1000,
			"adults_capacity": 2}).insert(ignore_permissions=True).name
		self.rooms = [frappe.get_doc({"doctype": "Room", "property": self.property,
			"room_type": rt, "room_number": n}).insert(ignore_permissions=True).name
			for n in ("101", "102")]

	def block(self, room, start, end, status="Active"):
		frappe.get_doc({"doctype": "Room Block", "property": self.property, "room": room,
			"from_date": start, "to_date": end, "block_status": status,
			"reason": "Maintenance"}).insert(ignore_permissions=True)

	def board(self):
		return {r.name: r for r in front_desk_snapshot(self.property)["rooms"]}

	def test_room_out_of_service_today_is_flagged(self):
		self.block(self.rooms[0], nowdate(), add_days(nowdate(), 3))
		board = self.board()
		self.assertEqual(board[self.rooms[0]]["block"]["reason"], "Maintenance")
		self.assertIsNone(board[self.rooms[1]]["block"])

	def test_block_ending_today_or_starting_later_is_not_flagged(self):
		self.block(self.rooms[0], add_days(nowdate(), -2), nowdate())
		self.block(self.rooms[1], add_days(nowdate(), 1), add_days(nowdate(), 2))
		board = self.board()
		self.assertIsNone(board[self.rooms[0]]["block"])
		self.assertIsNone(board[self.rooms[1]]["block"])
