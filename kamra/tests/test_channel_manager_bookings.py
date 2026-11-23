"""Rejected OTA sales remain visible to staff without consuming inventory."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from kamra import channel_manager as cm
from kamra.channels import aiosell


class ChannelManagerBookingTestCase(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		frappe.local.lang = "en"
		self.property = frappe.get_doc({"doctype": "Property",
			"property_name": "TEST OTA " + frappe.generate_hash(length=8),
			"country": "Uganda", "currency": "UGX"}).insert(ignore_permissions=True).name
		self.room_type = frappe.get_doc({"doctype": "Room Type", "property": self.property,
			"room_type_code": "STD", "room_type_name": "Standard", "base_price": 1000,
			"adults_capacity": 2}).insert(ignore_permissions=True).name
		frappe.get_doc({"doctype": "Room", "property": self.property,
			"room_type": self.room_type, "room_number": "101"}).insert(ignore_permissions=True)
		self.guest = frappe.get_doc({"doctype": "Guest", "first_name": "OTA Guest"}).insert(ignore_permissions=True).name
		self.conn = frappe.get_doc({"doctype": "Channel Manager Connection", "property": self.property,
			"provider": "AioSell", "active": 1, "external_property_id": "demo"}).insert(ignore_permissions=True)
		frappe.get_doc({"doctype": "Channel Room Mapping", "connection": self.conn.name,
			"room_type": self.room_type, "external_room_id": "std"}).insert(ignore_permissions=True)
		self.ref = "TEST-" + frappe.generate_hash(length=8)

	def payload(self, currency="UGX", rooms=1):
		return {"action": "book", "hotelCode": "demo", "channel": "Booking.com",
			"bookingId": self.ref, "checkin": nowdate(), "checkout": str(add_days(nowdate(), 1)),
			"guest": {"firstName": "OTA", "lastName": "Arrival"},
			"amount": {"amountAfterTax": 1500, "currency": currency},
			"specialRequests": "Late arrival",
			"rooms": [{"roomCode": "std", "occupancy": {"adults": 2, "children": 0},
			           "prices": [{"date": nowdate(), "sellRate": 1500}]} for _ in range(rooms)]}

	def sold_out(self):
		return frappe.get_doc({"doctype": "Reservation", "property": self.property,
			"room_type": self.room_type, "guest": self.guest, "status": "Confirmed",
			"check_in_date": nowdate(), "check_out_date": add_days(nowdate(), 1),
			"adults": 2}).insert(ignore_permissions=True)

	def deliver(self, payload):
		# Real rollback, bounded to the worker's transaction; keep test fixtures.
		sp = "ota_test_" + frappe.generate_hash(length=8)
		frappe.db.savepoint(sp)
		rollback = frappe.db.rollback
		def worker_rollback(*args, **kwargs):
			return rollback(*args, **kwargs) if args or kwargs else rollback(save_point=sp)
		with patch.object(frappe.db, "commit", return_value=None), \
		     patch.object(frappe.db, "rollback", side_effect=worker_rollback):
			cm.process_webhook_events(self.conn.name, payload)

	def received(self, ref=None):
		name = frappe.db.get_value("Reservation", {"property": self.property, "ota_ref": ref or self.ref})
		self.assertTrue(name, "OTA booking was dropped instead of retained for resolution")
		return frappe.get_doc("Reservation", name)

	def test_sold_out_booking_is_requested_with_resolution_note(self):
		original = self.sold_out()
		self.deliver(self.payload())
		doc = self.received()
		self.assertEqual(doc.status, "Requested")
		self.assertIn("OTA overbooking — resolve", doc.special_requests)
		self.assertIn("Late arrival", doc.special_requests)
		self.assertEqual(float(doc.amount_after_tax), 1500)
		self.assertEqual(cm._sellable(self.property, self.room_type, nowdate(), add_days(nowdate(), 1)), 0)
		self.assertEqual(frappe.db.get_value("Reservation", original.name, "status"), "Confirmed")

	def test_multi_room_refusal_keeps_all_lines_requested(self):
		self.deliver(self.payload(rooms=2))
		for i in range(2):
			self.assertEqual(self.received(f"{self.ref}-{i}").status, "Requested")

	def test_requested_replay_does_not_duplicate_the_booking(self):
		self.sold_out()
		payload = self.payload()
		self.deliver(payload)
		self.deliver(payload)
		self.assertEqual(self.received().status, "Requested")
		self.assertEqual(frappe.db.count("Reservation", {"property": self.property, "ota_ref": self.ref}), 1)

	def test_a_second_delivery_returns_the_original_stay(self):
		payload = self.payload()
		self.deliver(payload)
		original = self.received()
		self.assertEqual(original.status, "Confirmed")
		self.deliver(payload)
		self.assertEqual(frappe.db.get_value(
			"Reservation", {"property": self.property, "ota_ref": self.ref}, "name"),
			original.name)
		self.assertEqual(frappe.db.count(
			"Reservation", {"property": self.property, "ota_ref": self.ref}), 1)

	def test_missing_currency_defaults_to_property_currency(self):
		payload = self.payload()
		payload["amount"].pop("currency")
		self.assertEqual(aiosell.parse_webhook(self.conn, payload)[0]["currency"], "UGX")

	def test_foreign_currency_is_requested_without_mislabelled_money(self):
		self.deliver(self.payload(currency="USD"))
		doc = self.received()
		self.assertEqual(doc.status, "Requested")
		self.assertIn("USD", doc.special_requests)
		self.assertIn("UGX", doc.special_requests)
		self.assertIn("1500", doc.special_requests)
		self.assertEqual(float(doc.amount_after_tax or 0), 0)
		self.assertEqual(cm._sellable(self.property, self.room_type, nowdate(), add_days(nowdate(), 1)), 1)

	def test_matching_currency_keeps_confirmed_booking_and_original_price(self):
		self.deliver(self.payload())
		doc = self.received()
		self.assertEqual(doc.status, "Confirmed")
		self.assertEqual(float(doc.amount_after_tax), 1500)

	def test_currency_mismatch_on_modify_is_requested(self):
		self.deliver(self.payload())
		payload = self.payload(currency="USD")
		payload["action"] = "modify"
		self.deliver(payload)
		self.assertEqual(self.received().status, "Requested")
		self.assertIn("USD", self.received().special_requests)
		self.assertFalse(frappe.flags.kamra_status_transition)

	def test_capacity_refusal_on_modify_keeps_new_dates_for_resolution(self):
		payload = self.payload()
		payload["checkin"] = str(add_days(nowdate(), 2))
		payload["checkout"] = str(add_days(nowdate(), 3))
		self.deliver(payload)
		self.sold_out()
		payload = self.payload()
		payload["action"] = "modify"
		self.deliver(payload)
		doc = self.received()
		self.assertEqual(doc.status, "Requested")
		self.assertEqual(str(doc.check_in_date), nowdate())
		self.assertIn("OTA overbooking — resolve", doc.special_requests)
		self.assertFalse(frappe.flags.kamra_status_transition)

	def test_invalid_occupancy_is_not_treated_as_overbooking(self):
		payload = self.payload()
		payload["rooms"][0]["occupancy"]["adults"] = 3
		self.deliver(payload)
		self.assertFalse(frappe.db.exists("Reservation", {"property": self.property, "ota_ref": self.ref}))

	def test_ota_cancel_cancels_retained_requested_booking(self):
		self.sold_out()
		self.deliver(self.payload())
		self.assertEqual(self.received().status, "Requested")
		self.deliver({"action": "cancel", "hotelCode": "demo", "channel": "Booking.com",
			"bookingId": self.ref})
		doc = self.received()
		self.assertEqual(doc.status, "Cancelled")
		self.assertIn(self.ref, doc.cancellation_note or "")

	def test_modify_dropping_a_retained_room_cancels_it(self):
		self.deliver(self.payload(rooms=3))
		for i in range(3):
			self.assertEqual(self.received(f"{self.ref}-{i}").status, "Requested")
		payload = self.payload(rooms=2)
		payload["action"] = "modify"
		self.deliver(payload)
		self.assertEqual(self.received(f"{self.ref}-0").status, "Requested")
		self.assertEqual(self.received(f"{self.ref}-1").status, "Requested")
		self.assertEqual(self.received(f"{self.ref}-2").status, "Cancelled")

	def test_physical_room_double_booking_is_retained_as_requested(self):
		"""The room-overlap refusal ("Double booking blocked") is an inventory
		refusal too, whatever its message title says."""
		frappe.get_doc({"doctype": "Room", "property": self.property,
			"room_type": self.room_type, "room_number": "102"}).insert(ignore_permissions=True)
		taken = frappe.db.get_value("Room", {"property": self.property, "room_number": "101"})
		holder = self.sold_out()
		frappe.db.set_value("Reservation", holder.name, "room", taken)
		original = cm._apply_event

		def assign_taken_room(conn, e, requested_reason=None):
			out = original(conn, e, requested_reason=requested_reason)
			if not requested_reason and out.get("reservation"):
				doc = frappe.get_doc("Reservation", out["reservation"])
				doc.room = taken
				doc.save(ignore_permissions=True)
			return out

		with patch.object(cm, "_apply_event", side_effect=assign_taken_room):
			self.deliver(self.payload())
		doc = self.received()
		self.assertEqual(doc.status, "Requested")
		self.assertIn("OTA overbooking — resolve", doc.special_requests)
		self.assertFalse(doc.room)


class ChannelContactNeverDropsBookingTestCase(IntegrationTestCase):
	"""A phone or an email Frappe would refuse on the Guest insert never costs
	an OTA booking (follow-up to #468): the profile keeps it blank, the
	reservation's notes keep it as it came, and the phone is flagged."""

	def setUp(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		frappe.local.lang = "en"
		self.property = frappe.get_doc({"doctype": "Property",
			"property_name": "TEST OTA CONTACT " + frappe.generate_hash(length=8),
			"country": "Uganda", "currency": "UGX"}).insert(ignore_permissions=True).name
		self.room_type = frappe.get_doc({"doctype": "Room Type", "property": self.property,
			"room_type_code": "STD", "room_type_name": "Standard", "base_price": 1000,
			"adults_capacity": 2}).insert(ignore_permissions=True).name
		frappe.get_doc({"doctype": "Room", "property": self.property,
			"room_type": self.room_type, "room_number": "101"}).insert(ignore_permissions=True)
		self.conn = frappe.get_doc({"doctype": "Channel Manager Connection", "property": self.property,
			"provider": "Channex", "active": 1, "external_property_id": "demo-contact"}).insert(ignore_permissions=True)
		frappe.get_doc({"doctype": "Channel Room Mapping", "connection": self.conn.name,
			"room_type": self.room_type, "external_room_id": "contact-std"}).insert(ignore_permissions=True)
		frappe.db.delete("Guest", {"phone": ("in", ["+256772987654", "+256 772 987 654", "0772 987 654"])})

	def ev(self, **kw):
		tag = frappe.generate_hash(length=8)
		e = {"event": "book", "ota_ref": "TEST-CONTACT-" + tag, "channel": "Booking.com",
			"room_type_external_id": "contact-std", "check_in": nowdate(),
			"check_out": str(add_days(nowdate(), 1)), "adults": 2, "children": 0,
			"guest_name": "Contact Test", "phone": "", "email": f"contact-{tag}@example.test",
			"total": 0, "nightly": [], "currency": "", "notes": ""}
		e.update(kw)
		return e

	def booked(self, e):
		out = cm._apply_event(self.conn, e)
		self.assertEqual(out["result"], "booked", out)
		return frappe.get_doc("Reservation", out["reservation"])

	def test_local_number_is_read_with_the_property_country(self):
		from kamra import phone as phone_mod
		self.assertEqual(phone_mod.for_property("0772 987 654", self.property), ("+256772987654", None))

	def test_phone_frappe_refuses_keeps_the_booking_and_the_number(self):
		res = self.booked(self.ev(phone="abc-123"))
		self.assertEqual(frappe.db.get_value("Guest", res.guest, "phone") or "", "")
		self.assertIn("abc-123", res.special_requests)
		rationale = frappe.db.get_value("Agent Action Log",
			{"action_type": "phone_needs_review", "reference_doctype": "Guest",
			 "reference_name": res.guest}, "rationale")
		self.assertTrue(rationale, "the unreadable phone was not flagged for review")
		self.assertNotIn("abc-123", rationale)

	def test_email_frappe_refuses_keeps_the_booking_and_the_address(self):
		res = self.booked(self.ev(email="not-an-email"))
		self.assertEqual(frappe.db.get_value("Guest", res.guest, "email") or "", "")
		self.assertIn("not-an-email", res.special_requests)

	def test_two_writings_of_one_number_are_one_guest(self):
		first = self.booked(self.ev(phone="0772 987 654"))
		second = self.booked(self.ev(phone="+256 772 987 654",
			check_in=str(add_days(nowdate(), 2)), check_out=str(add_days(nowdate(), 3))))
		self.assertEqual(first.guest, second.guest)

	def test_channel_notes_come_first_and_the_contact_line_after(self):
		res = self.booked(self.ev(phone="abc-123", notes="Late arrival"))
		notes = res.special_requests
		self.assertIn("Late arrival", notes)
		self.assertLess(notes.index("Late arrival"), notes.index("abc-123"))
		self.assertIn("Contact from Booking.com could not be saved on the guest profile", notes)

	def test_unstorable_contact_lists_what_came_as_it_came(self):
		self.assertEqual(cm._unstorable_contact("abc-123", "", self.property), ["abc-123"])
		self.assertEqual(cm._unstorable_contact("", "not-an-email", self.property), ["not-an-email"])
		self.assertEqual(cm._unstorable_contact("0772 987 654", "a@example.test", self.property), [])
		self.assertEqual(cm._unstorable_contact("", "", self.property), [])

	def post_webhook(self, body: dict, secret: str) -> dict:
		"""What Frappe does with Channex's POST: a JSON body, the connection in
		the URL we hand out (connection_status), the secret in a header. The
		arguments come from Frappe's own make_form_dict, and the call is the one
		handler.execute_cmd makes, as Guest."""
		from frappe.app import make_form_dict
		from werkzeug.test import EnvironBuilder
		request = EnvironBuilder(method="POST", path="/api/method/kamra.channel_manager.webhook",
			query_string={"connection": self.conn.name}, json=body,
			headers={"X-Webhook-Secret": secret}).get_request()
		before = getattr(frappe.local, "request", None), frappe.local.form_dict
		frappe.local.request = request
		make_form_dict(request)
		frappe.set_user("Guest")  # nosemgrep: frappe-setuser -- test fixture: the endpoint's real caller
		try:
			return frappe.call("kamra.channel_manager.webhook", **frappe.form_dict)
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
			frappe.local.request, frappe.local.form_dict = before

	def test_channex_webhook_keeps_the_booking_with_a_refused_phone(self):
		# The real path: Channex POSTs JSON to the allow_guest endpoint at the
		# URL with ?connection=, so it runs as Guest, through parse_webhook.
		self.conn.webhook_secret = "ut-secret"
		self.conn.save(ignore_permissions=True)
		ref = "TEST-CONTACT-WH-" + frappe.generate_hash(length=8)
		payload = {"status": "new", "ota_reservation_code": ref, "ota_name": "Booking.com",
			"arrival_date": nowdate(), "departure_date": str(add_days(nowdate(), 1)),
			"customer": {"name": "Webhook", "surname": "Test", "phone": "abc-123",
			             "mail": "contact-wh@example.test"},
			"rooms": [{"room_type_id": "contact-std", "occupancy": {"adults": 2}}]}
		out = self.post_webhook({"event": "booking", "payload": payload}, "ut-secret")
		self.assertEqual(out["results"][0]["result"], "booked", out)
		res = frappe.get_doc("Reservation", {"property": self.property, "ota_ref": ref})
		self.assertEqual(frappe.db.get_value("Guest", res.guest, "phone") or "", "")
		self.assertIn("abc-123", res.special_requests)

	def test_a_modify_keeps_the_contact_line_with_the_new_notes(self):
		e = self.ev(phone="abc-123", notes="Late arrival")
		res = self.booked(e)
		out = cm._apply_event(self.conn, dict(e, event="modify", notes="Early check-in"))
		self.assertEqual(out["result"], "modified", out)
		notes = frappe.db.get_value("Reservation", res.name, "special_requests")
		self.assertIn("Early check-in", notes)
		self.assertNotIn("Late arrival", notes)
		self.assertIn("abc-123", notes)
		self.assertLess(notes.index("Early check-in"), notes.index("abc-123"))
		self.assertEqual(notes.count("could not be saved on the guest profile"), 1)

	def test_a_modify_without_contact_keeps_the_line_it_had(self):
		e = self.ev(phone="abc-123", notes="Late arrival")
		res = self.booked(e)
		cm._apply_event(self.conn, dict(e, event="modify", phone="", notes="Baby cot"))
		notes = frappe.db.get_value("Reservation", res.name, "special_requests")
		self.assertIn("Baby cot", notes)
		self.assertIn("abc-123", notes)
		self.assertEqual(notes.count("could not be saved on the guest profile"), 1)
		cm._apply_event(self.conn, dict(e, event="modify", phone="", notes=""))
		self.assertIn("abc-123", frappe.db.get_value("Reservation", res.name, "special_requests"))
