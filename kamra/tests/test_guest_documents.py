"""The guest profile's identity documents: what is on file, whether it is
still valid, and whether it has been used on earlier stays. Warnings only:
nothing here may stop an arrival."""

from __future__ import annotations

import frappe

from kamra import api, checkin
from kamra.guest_documents import EXPIRING_DAYS, guest_documents, id_status
from kamra.tests.audit_fixtures import (
	PROP_A,
	TODAY,
	AuditTestCase,
	d,
	make_guest,
	make_property,
	make_reservation,
	make_room,
	make_room_type,
)


class GuestDocumentsTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.guest_documents")
		make_property(PROP_A, business_date=TODAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")

	def stay(self, guest, **kw):
		return make_reservation(PROP_A, self.rt, d(-30), d(-28), "Checked Out",
		                        guest=guest, **kw)

	def test_status_none_valid_expiring_expired(self):
		self.assertEqual(id_status(None, False), "none")
		# many IDs never expire: no date is valid, not lapsed
		self.assertEqual(id_status(None, True), "valid")
		self.assertEqual(id_status(d(-1), True), "expired")
		self.assertEqual(id_status(d(0), True), "expiring")
		self.assertEqual(id_status(d(EXPIRING_DAYS), True), "expiring")
		self.assertEqual(id_status(d(EXPIRING_DAYS + 1), True), "valid")

	def test_a_guest_with_no_papers_has_nothing_on_file(self):
		docs = guest_documents(make_guest("UT Bare"))
		self.assertFalse(docs["id"]["on_file"])
		self.assertEqual(docs["id"]["status"], "none")
		self.assertFalse(docs["address_proof"]["on_file"])
		self.assertEqual(docs["used"]["count"], 0)

	def test_typed_id_with_dates_is_on_file_and_expired_is_flagged(self):
		g = make_guest("UT Passport", id_type="Passport", id_number="P243869",
		               id_place_of_issue="Bangalore", id_issue_date=d(-4000),
		               id_expiry_date=d(-3))
		docs = guest_documents(g)
		self.assertTrue(docs["id"]["on_file"])
		self.assertEqual(docs["id"]["place_of_issue"], "Bangalore")
		self.assertEqual(docs["id"]["status"], "expired")

	def test_an_id_cannot_expire_before_it_was_issued(self):
		with self.assertRaisesRegex(frappe.ValidationError, "expire before"):
			make_guest("UT Typo", id_type="Passport", id_number="P1",
			           id_issue_date=d(0), id_expiry_date=d(-10))

	def test_used_on_earlier_stays_counts_scans_held_and_discarded(self):
		g = make_guest("UT Repeat", id_type="Passport", id_number="P777")
		held = self.stay(g)
		frappe.db.set_value("Reservation", held.name, {
			"id_document": "/private/files/x.jpg", "id_document_on": f"{d(-30)} 10:00:00"})
		gone = self.stay(g)
		frappe.db.set_value("Reservation", gone.name, "id_document_discarded", 1)
		self.stay(g)  # never captured
		docs = guest_documents(g)
		self.assertEqual(docs["used"]["count"], 2)
		self.assertEqual(docs["id"]["scan_reservation"], held.name)
		# only a stay that still holds a scan offers one
		frappe.db.set_value("Reservation", held.name, "id_document", None)
		self.assertIsNone(guest_documents(g)["id"]["scan_reservation"])

	def test_guest_journey_carries_the_documents_and_dates(self):
		g = make_guest("UT Journey", id_type="Aadhaar", id_number="XXXX1234",
		               id_expiry_date=d(400))
		self.stay(g)
		out = api.guest_journey(g)
		self.assertEqual(out["guest"]["id_expiry_date"], d(400))
		self.assertEqual(out["documents"]["id"]["status"], "valid")

	def test_check_in_sees_the_id_on_file_and_an_expired_one_does_not_block(self):
		g = make_guest("UT Arrive", id_type="Passport", id_number="P999",
		               id_expiry_date=d(-1))
		res = make_reservation(PROP_A, self.rt, d(0), d(2), "Confirmed", guest=g,
		                       room=self.room)
		flow = checkin.checkin_flow(res.name)
		ctx = flow["guest"]
		self.assertTrue(ctx["id_on_file"])
		self.assertEqual(ctx["id_status"], "expired")
		self.assertEqual(ctx["id_expiry_date"], d(-1))
		# a warning for the desk, never a reason to refuse the arrival: the
		# expired ID still counts as an ID that was collected
		self.assertTrue(flow["ids"]["ok"])
		self.assertEqual(flow["ids"]["missing"], [])
