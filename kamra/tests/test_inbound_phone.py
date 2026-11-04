"""Phones that come in from outside the desk are read with the property's
country and never cost a booking (#468)."""

from __future__ import annotations

import frappe

from kamra import api, channel_manager
from kamra import phone as phone_mod
from kamra.tests.audit_fixtures import AuditTestCase, make_property

PROP = "UT Phone UG"


class InboundPhoneTestCase(AuditTestCase):
	properties = (PROP,)

	def setUp(self):
		super().setUp()
		make_property(PROP, country="Uganda")
		frappe.db.delete("Guest", {"phone": ("in", ["+256772123456", "0772123456",
		                                            "+256 772 123456",
		                                            "+442079460958", "12345"])})

	def test_normalise(self):
		n = phone_mod.normalise
		self.assertEqual(n("0772123456", "UG"), ("+256772123456", None))
		self.assertEqual(n("772123456", "UG"), ("+256772123456", None))
		self.assertEqual(n("+442079460958", "UG"), ("+442079460958", None))
		self.assertEqual(n("00442079460958", "UG"), ("+442079460958", None))
		self.assertEqual(n("0772123456", None), ("0772123456", phone_mod.NO_COUNTRY))
		self.assertEqual(n("12345", "UG"), ("12345", phone_mod.INVALID))
		self.assertEqual(n("  ", "UG"), ("", None))
		# a valid international number is kept as written, not compacted
		self.assertEqual(n("+256 772 123456", "UG"), ("+256 772 123456", None))
		self.assertEqual(phone_mod.canonical("+256 772 123456", "UG"), "+256772123456")

	def test_region_from_the_property(self):
		self.assertEqual(phone_mod.region_for(PROP), "UG")

	def test_local_and_international_find_the_same_guest(self):
		g = api._find_or_create_guest("UT Phone One", "0772123456", PROP)
		self.assertEqual(frappe.db.get_value("Guest", g, "phone"), "+256772123456")
		self.assertEqual(api._find_or_create_guest("UT Phone One", "+256 772 123456", PROP), g)

	def test_spaced_international_is_kept_and_found_again(self):
		g = api._find_or_create_guest("UT Phone Spaced", "+256 772 123456", PROP)
		self.assertEqual(frappe.db.get_value("Guest", g, "phone"), "+256 772 123456")
		self.assertEqual(
			api._find_or_create_guest("UT Phone Spaced", "+256 772 123456", PROP), g)

	def test_foreign_number_stays_foreign(self):
		g = api._find_or_create_guest("UT Phone Two", "+442079460958", PROP)
		self.assertEqual(frappe.db.get_value("Guest", g, "phone"), "+442079460958")

	def test_unreadable_number_is_kept_and_flagged_without_the_number(self):
		g = api._find_or_create_guest("UT Phone Three", "12345", PROP)
		self.assertEqual(frappe.db.get_value("Guest", g, "phone"), "12345")
		log = frappe.get_all("Agent Action Log", filters={
			"action_type": "phone_needs_review", "reference_name": g},
			fields=["rationale"])
		self.assertTrue(log)
		self.assertNotIn("12345", log[0].rationale)

	def test_ota_guest_with_a_bad_phone_is_still_created(self):
		g = channel_manager._find_or_create_guest("UT Phone Ota", "12345", "", PROP)
		self.assertTrue(frappe.db.exists("Guest", g))
		g2 = channel_manager._find_or_create_guest("UT Phone Ota", "0772123456", "", PROP)
		self.assertEqual(frappe.db.get_value("Guest", g2, "phone"), "+256772123456")

	def test_property_phone_is_read_with_its_country(self):
		doc = frappe.get_doc("Property", PROP)
		doc.phone = "0772123456"
		doc.save(ignore_permissions=True)
		self.assertEqual(doc.phone, "+256772123456")
