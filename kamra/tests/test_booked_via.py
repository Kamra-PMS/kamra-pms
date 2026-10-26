"""A booking keyed in from an OTA email is tagged like a channel booking."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from kamra.api import booking_options, create_booking
from kamra.channel_manager import canonical_channel


class BookedViaTestCase(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		frappe.local.lang = "en"
		self.property = frappe.get_doc({"doctype": "Property",
			"property_name": "TEST VIA " + frappe.generate_hash(length=8),
			"country": "Uganda", "currency": "UGX"}).insert(ignore_permissions=True).name
		self.room_type = frappe.get_doc({"doctype": "Room Type", "property": self.property,
			"room_type_code": "STD", "room_type_name": "Standard", "base_price": 1000,
			"adults_capacity": 2}).insert(ignore_permissions=True).name
		for n in ("101", "102"):
			frappe.get_doc({"doctype": "Room", "property": self.property,
				"room_type": self.room_type, "room_number": n}).insert(ignore_permissions=True)

	def book(self, **kw):
		return create_booking(self.property, self.room_type, nowdate(),
		                      str(add_days(nowdate(), 2)), "Via Guest", **kw)

	def test_names_are_one_per_site(self):
		for raw in ("BookingCom", "booking.com", "booking", "Booking.com"):
			self.assertEqual(canonical_channel(raw), "Booking.com")
		self.assertEqual(canonical_channel("makemytrip"), "MakeMyTrip")
		self.assertEqual(canonical_channel("Cleartrip"), "Cleartrip")
		self.assertIsNone(canonical_channel("  "))

	def test_ota_booking_keeps_site_ref_and_sold_price(self):
		ref = "BDC-" + frappe.generate_hash(length=6)
		r = frappe.get_doc("Reservation", self.book(
			booked_via="booking.com", ota_ref=ref, ota_total=2600)["reservation"])
		self.assertEqual((r.source, r.channel, r.ota_ref), ("OTA", "Booking.com", ref))
		self.assertEqual(r.auto_price, 0)
		self.assertAlmostEqual(float(r.amount_after_tax), 2600, places=0)
		self.assertEqual(len(r.night_rates), 2)
		# the same email cannot be keyed twice
		self.assertRaises(frappe.ValidationError, self.book,
		                  booked_via="Booking.com", ota_ref=ref)
		self.assertIn("Booking.com", booking_options(self.property)["ota_channels"])

	def test_other_site_without_price_uses_rate_card(self):
		r = frappe.get_doc("Reservation", self.book(booked_via="Cleartrip")["reservation"])
		self.assertEqual((r.source, r.channel, r.auto_price), ("OTA", "Cleartrip", 1))
		self.assertIn("Cleartrip", booking_options(self.property)["ota_channels"])

	def test_direct_booking_unchanged(self):
		r = frappe.get_doc("Reservation", self.book()["reservation"])
		self.assertEqual(r.source, "Manual")
		self.assertFalse(r.channel)
