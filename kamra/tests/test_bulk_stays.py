"""Bulk check-in / cancel from Today (#534): each stay goes through the
single-stay call, and one that fails never stops the rest."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from kamra.api import bulk_stays, create_group_booking, group_assign_rooms


class BulkStaysTestCase(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		frappe.local.lang = "en"
		self.property = frappe.get_doc({"doctype": "Property",
			"property_name": "TEST BULK " + frappe.generate_hash(length=8),
			"country": "Uganda", "currency": "UGX"}).insert(ignore_permissions=True).name
		room_type = frappe.get_doc({"doctype": "Room Type", "property": self.property,
			"room_type_code": "DLX", "room_type_name": "Deluxe", "base_price": 1000,
			"adults_capacity": 2}).insert(ignore_permissions=True).name
		for n in ("301", "302", "303"):
			frappe.get_doc({"doctype": "Room", "property": self.property,
				"room_type": room_type, "room_number": n}).insert(ignore_permissions=True)
		out = create_group_booking(
			self.property, "Bulk", nowdate(), str(add_days(nowdate(), 2)),
			[{"room_type": room_type, "count": 3, "adults": 2}],
			"Lead Guest", phone="+256700000009")
		group_assign_rooms(out["group_booking"])
		self.stays = out["created"]

	def status(self, res):
		return frappe.db.get_value("Reservation", res, "status")

	def test_one_failure_never_stops_the_rest(self):
		r1, r2, r3 = self.stays
		# no room: check_in's own hard gate refuses this one
		frappe.db.set_value("Reservation", r3, "room", None)
		out = {x["reservation"]: x for x in bulk_stays("check_in", [r1, r2, r3])["results"]}
		self.assertTrue(out[r1].get("done") and out[r2].get("done"), out)
		self.assertTrue(out[r3].get("error"), out)
		self.assertEqual([self.status(r) for r in (r1, r2, r3)],
		                 ["Checked In", "Checked In", "Confirmed"])

		# cancel runs cancel_reservation's checks: a checked-in stay is refused
		out = {x["reservation"]: x for x in bulk_stays("cancel", [r1, r3])["results"]}
		self.assertTrue(out[r1].get("error"), out)
		self.assertTrue(out[r3].get("done"), out)
		self.assertEqual(self.status(r1), "Checked In")
		self.assertEqual(self.status(r3), "Cancelled")

	def test_refuses_unknown_action_and_empty_pick(self):
		with self.assertRaises(frappe.ValidationError):
			bulk_stays("delete", self.stays)
		with self.assertRaises(frappe.ValidationError):
			bulk_stays("check_in", [])
