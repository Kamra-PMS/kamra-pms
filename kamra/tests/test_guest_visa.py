"""A foreign guest's visa or OCI card, recorded at check-in beside the ID."""

from __future__ import annotations

import frappe

from kamra import checkin, guest_documents
from kamra.localization import is_foreign_national, pack_for
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
		make_property(PROP_A, business_date=TODAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)

	def test_foreign_means_not_the_home_nationality(self):
		pack = pack_for(PROP_A)  # the India pack: "Indian" / "IND"
		self.assertFalse(is_foreign_national(pack, "Indian"))
		self.assertFalse(is_foreign_national(pack, " ind "))
		self.assertFalse(is_foreign_national(pack, ""))
		self.assertTrue(is_foreign_national(pack, "British"))

	def test_desk_saves_the_visa_and_the_flow_shows_it(self):
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
		self.assertIn("Indian", flow["guest"]["home_nationality"])

	def test_an_indian_guest_is_not_asked(self):
		res = make_reservation(PROP_A, self.rt, TODAY, d(2))
		flow = checkin.save_guest_details(res.name, nationality="Indian")
		self.assertFalse(flow["guest"]["foreign"])

	def test_unknown_visa_type_is_refused(self):
		res = make_reservation(PROP_A, self.rt, TODAY, d(2))
		with self.assertRaises(frappe.ValidationError):
			checkin.save_guest_details(res.name, visa_type="Tourist pass")

	def test_visa_photo_is_a_profile_document(self):
		self.assertEqual(guest_documents._field("visa"), "visa_file")
