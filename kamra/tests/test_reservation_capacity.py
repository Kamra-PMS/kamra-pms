"""Room-type capacity checks serialize before they count inventory."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate


class ReservationCapacityTestCase(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		self.property = frappe.get_doc({"doctype": "Property",
			"property_name": "TEST Capacity " + frappe.generate_hash(length=8)}).insert(ignore_permissions=True).name
		self.room_type = frappe.get_doc({"doctype": "Room Type", "property": self.property,
			"room_type_code": "STD", "room_type_name": "Standard",
			"base_price": 1000}).insert(ignore_permissions=True).name
		frappe.get_doc({"doctype": "Room", "property": self.property,
			"room_type": self.room_type, "room_number": "101"}).insert(ignore_permissions=True)
		self.guest = frappe.get_doc({"doctype": "Guest", "first_name": "Capacity Guest"}).insert(ignore_permissions=True).name

	def reservation(self, status="Confirmed"):
		return frappe.get_doc({"doctype": "Reservation", "property": self.property,
			"room_type": self.room_type, "guest": self.guest, "status": status,
			"check_in_date": nowdate(), "check_out_date": add_days(nowdate(), 1), "adults": 2})

	def test_room_type_row_is_locked_before_inventory_counts(self):
		doc = self.reservation()
		with patch.object(frappe.db, "sql", wraps=frappe.db.sql) as queries:
			doc.validate_type_capacity()
		sql = [str(call.args[0]).upper() for call in queries.call_args_list]
		locks = [i for i, q in enumerate(sql) if "TABROOM TYPE" in q and "FOR UPDATE" in q]
		counts = [i for i, q in enumerate(sql)
		          if "TABRESERVATION" in q and "FOR UPDATE" in q]
		self.assertTrue(locks, "Room Type was not locked before checking capacity")
		self.assertTrue(counts, "Capacity was not re-read with FOR UPDATE")
		self.assertLess(locks[0], min(counts))

	def test_requested_stay_does_not_lock_or_consume_capacity(self):
		doc = self.reservation(status="Requested")
		with patch.object(frappe.db, "sql", wraps=frappe.db.sql) as queries:
			doc.validate_type_capacity()
		self.assertEqual(queries.call_count, 0)

	def test_sold_out_type_still_refuses_an_unassigned_stay(self):
		self.reservation().insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			self.reservation().validate_type_capacity()

	def test_a_booking_that_lands_while_this_one_waits_is_seen(self):
		"""The stay inserted by the request that held the room-type lock is
		visible to the one that was waiting. A count taken before the lock
		would still see an empty house and sell the only room twice."""
		state = {"done": False}
		real = frappe.db.get_value

		def values(*args, **kwargs):
			out = real(*args, **kwargs)
			if (not state["done"] and args and args[0] == "Room Type"
			        and kwargs.get("for_update")):
				state["done"] = True
				self.reservation().insert(ignore_permissions=True)
			return out

		with patch.object(frappe.db, "get_value", side_effect=values):
			with self.assertRaises(frappe.ValidationError):
				self.reservation().insert(ignore_permissions=True)
		self.assertEqual(frappe.db.count(
			"Reservation", {"property": self.property, "status": "Confirmed"}), 1)

	def test_villa_and_a_member_room_cannot_both_be_sold(self):
		villa = frappe.get_doc({
			"doctype": "Room Type", "property": self.property,
			"room_type_code": "VILLA", "room_type_name": "Whole villa",
			"room_category": "Villa", "base_price": 5000,
		}).insert(ignore_permissions=True).name
		self.reservation().insert(ignore_permissions=True)
		stay = self.reservation()
		stay.room_type = villa
		with self.assertRaises(frappe.ValidationError):
			stay.insert(ignore_permissions=True)

	def test_a_room_booked_while_the_villa_waits_is_seen(self):
		villa = frappe.get_doc({
			"doctype": "Room Type", "property": self.property,
			"room_type_code": "VILLA2", "room_type_name": "Whole villa 2",
			"room_category": "Villa", "base_price": 5000,
		}).insert(ignore_permissions=True).name
		state = {"done": False}
		real = frappe.db.get_value

		def values(*args, **kwargs):
			out = real(*args, **kwargs)
			if (not state["done"] and args and args[0] == "Property"
			        and kwargs.get("for_update")):
				state["done"] = True
				self.reservation().insert(ignore_permissions=True)
			return out

		stay = self.reservation()
		stay.room_type = villa
		with patch.object(frappe.db, "get_value", side_effect=values):
			with self.assertRaises(frappe.ValidationError):
				stay.insert(ignore_permissions=True)
		self.assertEqual(frappe.db.count(
			"Reservation", {"property": self.property, "status": "Confirmed"}), 1)

	def test_ota_reference_is_unique_for_a_live_stay(self):
		first = self.reservation()
		first.ota_ref = "OTA-ONCE"
		first.insert(ignore_permissions=True)
		self.assertEqual(first.ota_live_key, f"{self.property}::OTA-ONCE")
		second = self.reservation()
		second.ota_ref = "OTA-ONCE"
		with self.assertRaises(frappe.DuplicateEntryError):
			second.insert(ignore_permissions=True)
		frappe.flags.kamra_cancelling = True
		try:
			first.reload()
			first.status = "Cancelled"
			first.save(ignore_permissions=True)
		finally:
			frappe.flags.kamra_cancelling = False
		self.assertFalse(first.ota_live_key)
		second.insert(ignore_permissions=True)
		self.assertEqual(second.ota_live_key, f"{self.property}::OTA-ONCE")

	def test_duplicate_ota_refs_are_reported_and_not_deleted(self):
		from kamra.patches.v47.report_duplicate_ota_refs import execute
		kept = self.reservation()
		kept.ota_ref = "OTA-DUP"
		kept.insert(ignore_permissions=True)
		extra = self.reservation()
		extra.ota_ref = "OTA-OTHER"
		extra.insert(ignore_permissions=True)
		frappe.db.set_value("Reservation", extra.name, {
			"ota_ref": "OTA-DUP", "ota_live_key": None,
		}, update_modified=False)
		execute()
		self.assertTrue(frappe.db.exists("Reservation", extra.name))
		self.assertEqual(frappe.db.get_value("Reservation", kept.name, "ota_live_key"),
		                 f"{self.property}::OTA-DUP")
		self.assertFalse(frappe.db.get_value("Reservation", extra.name, "ota_live_key"))
		execute()
		self.assertFalse(frappe.db.get_value("Reservation", extra.name, "ota_live_key"))
