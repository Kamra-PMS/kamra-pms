"""A foreign guest's visa (India: visa or OCI), recorded at check-in beside the ID."""

from __future__ import annotations

from unittest.mock import patch

import frappe

from kamra import api, checkin, guest_documents
from kamra.localization import (
	GENERIC_VISA_TYPES,
	generic,
	india,
	is_foreign_national,
	pack_for,
	visa_labels,
	visa_types,
)
from kamra.tests.audit_fixtures import (
	PROP_A,
	TODAY,
	AuditTestCase,
	d,
	make_property,
	make_reservation,
	make_room_type,
)


class GuestVisaTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.business_date")
		make_property(PROP_A, business_date=TODAY, country="India")
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)

	def test_foreign_means_not_the_home_nationality(self):
		pack = pack_for(PROP_A)  # the India pack: "Indian" / "IND"
		self.assertFalse(is_foreign_national(pack, "Indian"))
		self.assertFalse(is_foreign_national(pack, " ind "))
		self.assertFalse(is_foreign_national(pack, ""))
		self.assertTrue(is_foreign_national(pack, "British"))

	def test_generic_pack_does_not_treat_locals_as_foreign(self):
		# no home nationality → nobody is foreign (and no OCI wording)
		self.assertFalse(is_foreign_national(generic, "German"))
		self.assertFalse(is_foreign_national(generic, "Indian"))
		self.assertEqual(visa_types(generic), GENERIC_VISA_TYPES)
		self.assertNotIn("OCI Card", visa_types(generic))
		self.assertEqual(visa_labels(generic)["section"], "Visa")

	def test_empty_property_country_uses_generic_not_india(self):
		with patch.object(frappe, "get_cached_value", return_value=""):
			pack = pack_for(PROP_A)
		self.assertEqual(pack.__name__, "kamra.localization.generic")
		self.assertFalse(is_foreign_national(pack, "British"))

	def test_india_pack_lists_oci(self):
		self.assertEqual(visa_types(india), ["Visa", "e-Visa", "OCI Card"])
		self.assertEqual(visa_labels(india)["section"], "Visa / OCI")
		self.assertIn("OCI", visa_labels(india)["hint"])

	def test_desk_saves_the_visa_and_the_flow_masks_the_number(self):
		res = make_reservation(PROP_A, self.rt, TODAY, d(2))
		flow = checkin.save_guest_details(
			res.name, nationality="British", visa_type="e-Visa",
			visa_number=" EV1234567 ", visa_expiry_date="2032-01-31")
		g = frappe.db.get_value("Guest", res.guest,
		                        ["visa_type", "visa_number", "visa_expiry_date"], as_dict=True)
		self.assertEqual((g.visa_type, g.visa_number, str(g.visa_expiry_date)),
		                 ("e-Visa", "EV1234567", "2032-01-31"))
		self.assertTrue(flow["guest"]["foreign"])
		self.assertEqual(flow["guest"]["visa_type"], "e-Visa")
		# passport-grade PII: last four only, like id_number
		self.assertEqual(flow["guest"]["visa_number"], "•••••4567")
		self.assertIn("Indian", flow["guest"]["home_nationality"])
		self.assertIn("OCI Card", flow["vocabulary"]["visa_types"])
		self.assertEqual(flow["vocabulary"]["visa_section"], "Visa / OCI")

	def test_an_indian_guest_is_not_asked(self):
		res = make_reservation(PROP_A, self.rt, TODAY, d(2))
		flow = checkin.save_guest_details(res.name, nationality="Indian")
		self.assertFalse(flow["guest"]["foreign"])

	def test_unknown_visa_type_is_refused(self):
		res = make_reservation(PROP_A, self.rt, TODAY, d(2))
		with self.assertRaises(frappe.ValidationError):
			checkin.save_guest_details(res.name, visa_type="Tourist pass")

	def test_oci_refused_outside_india(self):
		res = make_reservation(PROP_A, self.rt, TODAY, d(2))
		with patch("kamra.localization.pack_for", return_value=generic):
			with self.assertRaises(frappe.ValidationError):
				checkin.save_guest_details(res.name, visa_type="OCI Card")

	def test_visa_photo_is_a_profile_document(self):
		self.assertEqual(guest_documents._field("visa"), "visa_file")

	def test_scrub_masks_visa_number_and_clears_visa_file(self):
		res = make_reservation(PROP_A, self.rt, TODAY, d(2))
		checkin.save_guest_details(
			res.name, nationality="British", visa_type="Visa",
			visa_number="AB9876543", visa_expiry_date="2030-06-01")
		# as if a desk Attach left a private file URL on the profile
		frappe.db.set_value("Guest", res.guest, "visa_file", "/private/files/visa-test.jpg")
		frappe.db.set_value("Property", PROP_A, "id_retention", "Verify & Discard")
		try:
			api._scrub_stay_ids(frappe.get_doc("Reservation", res.name))
			g = frappe.db.get_value("Guest", res.guest,
			                        ["visa_number", "visa_file"], as_dict=True)
			self.assertEqual(g.visa_number, "•••••6543")
			self.assertFalse(g.visa_file)
		finally:
			frappe.db.set_value("Property", PROP_A, "id_retention", "Store")
