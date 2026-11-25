"""A different person turns up for a booking made under someone else's name or
number: the desk moves the booking to them, before check-in.

The booking and its own paperwork name the new guest; the old profile, its
other stays, the money and the messages already sent to it stay as they were."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from kamra.api import change_booking_guest, create_booking

DESK = "change.guest.desk@test.local"
HOUSEKEEPER = "change.guest.hk@test.local"
ADMIN = "change.guest.admin@test.local"


class ChangeBookingGuestTestCase(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		frappe.local.lang = "en"
		self.property = frappe.get_doc({"doctype": "Property",
			"property_name": "TEST SWAP GUEST " + frappe.generate_hash(length=8),
			"country": "Uganda", "currency": "UGX"}).insert(ignore_permissions=True).name
		self.room_type = frappe.get_doc({"doctype": "Room Type", "property": self.property,
			"room_type_code": "STD", "room_type_name": "Standard", "base_price": 1000,
			"adults_capacity": 2}).insert(ignore_permissions=True).name
		for n in ("101", "102", "103"):
			frappe.get_doc({"doctype": "Room", "property": self.property,
				"room_type": self.room_type, "room_number": n}).insert(ignore_permissions=True)
		self.ci = str(add_days(nowdate(), 10))
		self.co = str(add_days(nowdate(), 12))
		# the booking was made under Alice's name and number ...
		out = create_booking(self.property, self.room_type, self.ci, self.co, "Alice Original",
		                     phone="+256 700 000 001")
		self.name = out["reservation"]
		self.alice = frappe.db.get_value("Reservation", self.name, "guest")
		self.desk = self._staff(DESK, "Front Desk")
		self.housekeeper = self._staff(HOUSEKEEPER, "Housekeeping")

	def tearDown(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		frappe.db.rollback()
		for user in (DESK, HOUSEKEEPER, ADMIN):
			frappe.clear_cache(user=user)

	def _staff(self, email: str, *roles: str) -> str:
		if not frappe.db.exists("User", email):
			frappe.get_doc({"doctype": "User", "email": email, "first_name": email.split("@")[0],
				"enabled": 1, "user_type": "System User", "send_welcome_email": 0,
				"roles": [{"role": r} for r in roles]}).insert(ignore_permissions=True)
		frappe.clear_cache(user=email)
		return email

	def res(self):
		return frappe.get_doc("Reservation", self.name)

	def swap(self, **kw):
		kw.setdefault("guest_name", "Bob Arrived")
		kw.setdefault("phone", "+256 700 000 002")
		return change_booking_guest(self.name, **kw)

	# -- the change -------------------------------------------------------

	def test_a_new_person_gets_a_new_profile_and_the_booking_names_them(self):
		out = self.swap()
		self.assertTrue(out["ok"])
		self.assertTrue(out["new_profile"])
		res = self.res()
		self.assertEqual(res.guest, out["guest"])
		self.assertNotEqual(res.guest, self.alice)
		self.assertEqual(res.guest_name, "Bob Arrived")
		self.assertEqual(frappe.db.get_value("Guest", res.guest, "phone"), "+256 700 000 002")

	def test_the_old_profile_and_its_other_stays_are_untouched(self):
		# Alice has another stay, which must not move
		other = create_booking(self.property, self.room_type, str(add_days(nowdate(), 20)),
		                       str(add_days(nowdate(), 22)), "Alice Original",
		                       phone="+256 700 000 001")["reservation"]
		self.assertEqual(frappe.db.get_value("Reservation", other, "guest"), self.alice)
		self.swap()
		self.assertEqual(frappe.db.get_value("Reservation", other, "guest"), self.alice)
		self.assertEqual(frappe.db.get_value("Guest", self.alice, "full_name"), "Alice Original")
		self.assertEqual(frappe.db.get_value("Guest", self.alice, "phone"), "+256 700 000 001")

	def test_the_same_name_and_phone_reuses_the_existing_profile(self):
		bob = create_booking(self.property, self.room_type, str(add_days(nowdate(), 30)),
		                     str(add_days(nowdate(), 31)), "Bob Arrived",
		                     phone="+256 700 000 002")
		bob_guest = frappe.db.get_value("Reservation", bob["reservation"], "guest")
		out = self.swap()
		self.assertEqual(out["guest"], bob_guest)
		self.assertFalse(out["new_profile"])

	def test_a_shared_phone_with_another_name_still_gets_its_own_profile(self):
		# Alice's number typed for a different person: not Alice
		out = self.swap(phone="+256 700 000 001")
		self.assertNotEqual(out["guest"], self.alice)
		self.assertTrue(out["new_profile"])

	def test_an_existing_guest_can_be_picked(self):
		carol = frappe.get_doc({"doctype": "Guest", "first_name": "Carol", "last_name": "Known",
			"phone": "+256700000003"}).insert(ignore_permissions=True).name
		out = change_booking_guest(self.name, guest=carol)
		self.assertEqual(out["guest"], carol)
		self.assertFalse(out["new_profile"])
		self.assertEqual(self.res().guest_name, "Carol Known")

	# -- what goes with the booking, and what does not -------------------------

	def test_the_bookings_folio_deposit_and_tickets_follow_the_new_guest(self):
		from kamra.folio import open_folio
		folio = open_folio(self.res())
		deposit = frappe.db.get_value("Security Deposit", {"reservation": self.name}) or frappe.get_doc({
			"doctype": "Security Deposit", "reservation": self.name, "guest": self.alice,
			"status": "Required", "required_amount": 500}).insert(ignore_permissions=True).name
		frappe.db.set_value("Security Deposit", deposit, "guest", self.alice)
		new = self.swap()["guest"]
		self.assertEqual(frappe.db.get_value("Folio", folio, "guest"), new)
		self.assertEqual(frappe.db.get_value("Folio", folio, "guest_name"), "Bob Arrived")
		self.assertEqual(frappe.db.get_value("Security Deposit", deposit, "guest"), new)

	def test_a_service_ticket_pos_order_and_recreation_visit_of_the_booking_follow_too(self):
		ticket = frappe.get_doc({"doctype": "Service Ticket", "property": self.property,
			"subject": "Extra pillows", "category": "Front Desk", "reservation": self.name,
			"guest": self.alice}).insert(ignore_permissions=True).name
		outlet = frappe.get_doc({"doctype": "POS Outlet", "property": self.property,
			"outlet_name": "Test Cafe " + frappe.generate_hash(length=5),
			"outlet_type": "Restaurant"}).insert(ignore_permissions=True).name
		order = frappe.get_doc({"doctype": "POS Order", "property": self.property, "outlet": outlet,
			"reservation": self.name, "guest": self.alice}).insert(ignore_permissions=True).name
		facility = frappe.get_doc({"doctype": "Recreation Facility", "property": self.property,
			"facility_name": "Test Gym"}).insert(ignore_permissions=True).name
		visit = frappe.get_doc({"doctype": "Recreation Visit", "property": self.property,
			"facility": facility, "who": "Alice Original", "status": "In",
			"started_at": frappe.utils.now_datetime(), "payment_mode": "Folio",
			"reservation": self.name, "guest": self.alice}).insert(ignore_permissions=True).name
		# a ticket from a DIFFERENT stay of Alice's must not move
		other_stay = create_booking(self.property, self.room_type, str(add_days(nowdate(), 30)),
		                            str(add_days(nowdate(), 31)), "Alice Original",
		                            phone="+256 700 000 001")["reservation"]
		other_ticket = frappe.get_doc({"doctype": "Service Ticket", "property": self.property,
			"subject": "Other stay", "category": "Front Desk", "reservation": other_stay,
			"guest": self.alice}).insert(ignore_permissions=True).name
		out = self.swap()
		new = out["guest"]
		for doctype, name in (("Service Ticket", ticket), ("POS Order", order),
		                      ("Recreation Visit", visit)):
			with self.subTest(doctype):
				self.assertEqual(frappe.db.get_value(doctype, name, "guest"), new)
		self.assertEqual(frappe.db.get_value("Service Ticket", other_ticket, "guest"), self.alice)
		self.assertEqual(out["moved"].get("Service Ticket"), 1)
		self.assertEqual(out["moved"].get("POS Order"), 1)
		self.assertEqual(out["moved"].get("Recreation Visit"), 1)

	def test_money_stays_where_it_was(self):
		from kamra.folio import open_folio
		folio = open_folio(self.res())
		fields = ["charges_total", "tax_total", "grand_total", "payments_total", "balance"]
		before = frappe.db.get_value("Folio", folio, fields, as_dict=True)
		price = float(self.res().amount_after_tax)
		self.swap()
		after = frappe.db.get_value("Folio", folio, fields, as_dict=True)
		self.assertEqual(before, after)
		self.assertEqual(float(self.res().amount_after_tax), price)

	def test_a_message_already_sent_stays_with_the_person_it_went_to(self):
		message = frappe.get_doc({"doctype": "WhatsApp Message", "property": self.property,
			"direction": "Outbound", "guest": self.alice, "reservation": self.name}).insert(
			ignore_permissions=True).name
		self.swap()
		self.assertEqual(frappe.db.get_value("WhatsApp Message", message, "guest"), self.alice)

	def test_a_pre_check_in_the_old_guest_did_is_cleared_and_their_link_stops_working(self):
		frappe.db.set_value("Reservation", self.name, {
			"precheckin_token": "oldtoken" + "x" * 24, "precheckin_status": "Submitted",
			"precheckin_consent": 1, "precheckin_signature": "data:image/png;base64,AAAA"})
		self.swap()
		res = self.res()
		self.assertNotEqual(res.precheckin_token, "oldtoken" + "x" * 24)
		self.assertEqual(res.precheckin_status, "Not Started")
		self.assertFalse(res.precheckin_signature)
		self.assertFalse(res.precheckin_consent)
		self.assertFalse(frappe.db.exists("Reservation", {"precheckin_token": "oldtoken" + "x" * 24}))

	def _store_id_scan(self):
		import base64
		import io

		from PIL import Image

		from kamra.id_documents import store_id_document
		buf = io.BytesIO()
		Image.new("RGB", (320, 200), "white").save(buf, format="PNG")
		url = store_id_document(
			self.res(), "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(), "Guest")
		return url

	def test_the_id_scan_the_old_guest_uploaded_is_deleted_with_its_fields(self):
		from kamra.id_documents import _existing
		url = self._store_id_scan()
		self.assertTrue(_existing(self.name))
		self.assertEqual(self.res().id_document, url)
		self.swap()
		res = self.res()
		self.assertFalse(res.id_document)
		self.assertFalse(res.id_document_source)
		self.assertFalse(res.id_document_on)
		# not "discarded after verification": the new guest has no scan yet, so the desk is asked for one
		self.assertEqual(res.id_document_discarded, 0)
		self.assertEqual(_existing(self.name), [])
		self.assertFalse(frappe.db.exists("File", {"file_url": url}))

	def test_if_the_scan_cannot_be_deleted_the_guest_is_not_changed(self):
		from unittest.mock import patch
		self._store_id_scan()
		frappe.db.savepoint("before_swap")
		# discard_id_document logs and carries on when Frappe cannot delete the file
		with patch("kamra.id_documents.discard_id_document", return_value=0):
			with self.assertRaisesRegex(frappe.ValidationError, "could not be removed"):
				self.swap()
		frappe.db.rollback(save_point="before_swap")  # what the request does with an error
		self.assertEqual(self.res().guest, self.alice)

	def test_the_change_is_commented_and_logged(self):
		self.swap(reason="Different Bob arrived")
		comments = frappe.get_all("Comment", filters={
			"reference_doctype": "Reservation", "reference_name": self.name,
			"comment_type": "Comment"}, pluck="content")
		self.assertTrue(any("Guest changed from Alice Original" in c and "Bob Arrived" in c
		                    and "Different Bob arrived" in c for c in comments), comments)
		self.assertTrue(frappe.db.exists("Agent Action Log", {
			"action_type": "change_booking_guest", "reference_name": self.name}))

	# -- when it is refused ------------------------------------------------

	def test_it_is_refused_once_the_guest_has_checked_in_or_the_booking_is_closed(self):
		for status in ("Checked In", "Checked Out", "Cancelled", "No Show"):
			with self.subTest(status):
				frappe.db.set_value("Reservation", self.name, "status", status)
				with self.assertRaisesRegex(frappe.ValidationError, "before check-in"):
					self.swap()
		self.assertEqual(self.res().guest, self.alice)

	def test_the_same_guest_or_nobody_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "already the guest"):
			change_booking_guest(self.name, guest=self.alice)
		with self.assertRaisesRegex(frappe.ValidationError, "new guest's name"):
			change_booking_guest(self.name)
		with self.assertRaises(frappe.ValidationError):
			change_booking_guest(self.name, guest="NO-SUCH-GUEST")

	def test_a_blacklisted_guest_is_refused_unless_a_hotel_admin_gives_a_reason(self):
		banned = frappe.get_doc({"doctype": "Guest", "first_name": "Barred", "last_name": "Person",
			"phone": "+256700000009", "blacklisted": 1,
			"blacklist_reason": "Damage"}).insert(ignore_permissions=True).name
		with self.assertRaisesRegex(frappe.ValidationError, "blacklisted"):
			change_booking_guest(self.name, guest=banned)
		# a typed number that belongs to the blacklisted profile meets it too
		with self.assertRaisesRegex(frappe.ValidationError, "blacklisted"):
			self.swap(guest_name="Somebody Else", phone="+256 700 000 009")
		self.assertEqual(self.res().guest, self.alice)
		change_booking_guest(self.name, guest=banned, blacklist_override_reason="Manager OK")
		self.assertEqual(self.res().guest, banned)

	def test_a_blacklist_override_needs_a_hotel_admin(self):
		banned = frappe.get_doc({"doctype": "Guest", "first_name": "Barred", "last_name": "Person",
			"phone": "+256700000009", "blacklisted": 1}).insert(ignore_permissions=True).name
		frappe.set_user(self.desk)  # nosemgrep: frappe-setuser -- the role under test
		with self.assertRaises(frappe.PermissionError):
			change_booking_guest(self.name, guest=banned, blacklist_override_reason="I say so")
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- read back the result
		self.assertEqual(self.res().guest, self.alice)

	# -- a desk limited to one hotel ---------------------------------------

	def _other_hotel_booking(self):
		other = frappe.get_doc({"doctype": "Property",
			"property_name": "TEST OTHER HOTEL " + frappe.generate_hash(length=8),
			"country": "Uganda", "currency": "UGX"}).insert(ignore_permissions=True).name
		rt = frappe.get_doc({"doctype": "Room Type", "property": other, "room_type_code": "STD",
			"room_type_name": "Standard", "base_price": 1000,
			"adults_capacity": 2}).insert(ignore_permissions=True).name
		frappe.get_doc({"doctype": "Room", "property": other, "room_type": rt,
			"room_number": "201"}).insert(ignore_permissions=True)
		name = create_booking(other, rt, self.ci, self.co, "Dora Elsewhere",
		                      phone="+256 700 000 007")["reservation"]
		return name, frappe.db.get_value("Reservation", name, "guest")

	def _limit_desk_to_this_hotel(self):
		frappe.get_doc({"doctype": "User Permission", "user": self.desk, "allow": "Property",
			"for_value": self.property}).insert(ignore_permissions=True)
		frappe.clear_cache(user=self.desk)

	def test_a_desk_limited_to_one_hotel_cannot_move_a_booking_to_a_guest_of_another(self):
		other_booking, dora = self._other_hotel_booking()
		self._limit_desk_to_this_hotel()
		frappe.set_user(self.desk)  # nosemgrep: frappe-setuser -- the user under test
		# Dora has only ever stayed at the other hotel
		with self.assertRaises(frappe.PermissionError):
			change_booking_guest(self.name, guest=dora)
		# and the other hotel's booking is not theirs to move
		with self.assertRaises(frappe.PermissionError):
			change_booking_guest(other_booking, guest=self.alice)
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- read back the result
		self.assertEqual(self.res().guest, self.alice)
		self.assertEqual(frappe.db.get_value("Reservation", other_booking, "guest"), dora)

	def test_the_same_desk_may_pick_a_guest_who_stayed_here_or_is_new_to_the_chain(self):
		self._limit_desk_to_this_hotel()
		local = create_booking(self.property, self.room_type, str(add_days(nowdate(), 30)),
		                       str(add_days(nowdate(), 31)), "Erin Local",
		                       phone="+256 700 000 004")["reservation"]
		erin = frappe.db.get_value("Reservation", local, "guest")
		unseen = frappe.get_doc({"doctype": "Guest", "first_name": "Frank", "last_name": "Unseen",
			"phone": "+256700000005"}).insert(ignore_permissions=True).name
		frappe.set_user(self.desk)  # nosemgrep: frappe-setuser -- the user under test
		change_booking_guest(self.name, guest=erin)
		change_booking_guest(self.name, guest=unseen)
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- read back the result
		self.assertEqual(self.res().guest, unseen)

	# -- who may ----------------------------------------------------------

	def test_the_front_desk_may_and_housekeeping_may_not(self):
		frappe.set_user(self.housekeeper)  # nosemgrep: frappe-setuser -- the role under test
		with self.assertRaises(frappe.PermissionError):
			self.swap()
		frappe.set_user(self.desk)  # nosemgrep: frappe-setuser -- the role under test
		self.swap()
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- read back the result
		self.assertEqual(self.res().guest_name, "Bob Arrived")
