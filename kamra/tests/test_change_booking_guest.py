"""A different person turns up for a booking made under someone else's name or
number: the desk moves the booking to them, before check-in.

The booking and its own paperwork name the new guest; the old profile, its
other stays, the money and the messages already sent to it stay as they were."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from kamra.api import (
	add_occupant_names,
	change_booking_guest,
	create_booking,
	guest_alert,
	update_occupants,
	upload_occupant_id,
)

DESK = "change.guest.desk@test.local"
HOUSEKEEPER = "change.guest.hk@test.local"
ADMIN = "change.guest.admin@test.local"


def _png_data_url() -> str:
	import base64
	import io

	from PIL import Image
	buf = io.BytesIO()
	Image.new("RGB", (320, 200), "white").save(buf, format="PNG")
	return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


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
		frappe.flags.kamra_blacklist_override = None
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

	def test_a_blacklisted_phone_at_another_hotel_hides_name_and_reason(self):
		# Dora only stayed at the other hotel and is blacklisted there
		_other, dora = self._other_hotel_booking()
		frappe.db.set_value("Guest", dora, {
			"blacklisted": 1, "blacklist_reason": "Secret other-hotel reason"})
		dora_phone = frappe.db.get_value("Guest", dora, "phone")
		self._limit_desk_to_this_hotel()
		frappe.set_user(self.desk)  # nosemgrep: frappe-setuser -- the user under test
		with self.assertRaises(frappe.ValidationError) as ctx:
			change_booking_guest(self.name, guest_name="Typed Local Name", phone=dora_phone)
		msg = str(ctx.exception)
		self.assertIn("blacklisted", msg.lower())
		self.assertNotIn("Secret other-hotel reason", msg)
		self.assertNotIn(frappe.db.get_value("Guest", dora, "full_name"), msg)
		# Hotel Admin override keeps the typed name, not Dora's profile
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- admin override
		change_booking_guest(self.name, guest_name="Typed Local Name", phone=dora_phone,
		                     blacklist_override_reason="GM approved at this hotel")
		res = self.res()
		self.assertNotEqual(res.guest, dora)
		self.assertEqual(res.guest_name, "Typed Local Name")
		# Front Desk can read this hotel's activity feed — the other hotel's
		# standing reason must not appear in the override log.
		log = frappe.get_all(
			"Agent Action Log",
			filters={"action_type": "blacklist_override", "reference_name": dora},
			fields=["rationale"], order_by="creation desc", limit=1)
		self.assertTrue(log, "override was not logged")
		self.assertNotIn("Secret other-hotel reason", log[0].rationale)
		self.assertIn("GM approved at this hotel", log[0].rationale)

	def test_the_desk_cannot_override_a_number_listed_at_another_hotel(self):
		# not seeing who is listed is no reason to let them through
		_booking, dora = self._other_hotel_booking()
		frappe.db.set_value("Guest", dora, {"blacklisted": 1, "blacklist_reason": "Broke a door"})
		self._limit_desk_to_this_hotel()
		frappe.set_user(self.desk)  # nosemgrep: frappe-setuser -- the user under test
		number = "+256 700 000 007"
		for what, call in (
			("change guest", lambda: self.swap(guest_name="Somebody Else", phone=number,
			                                   blacklist_override_reason="I say so")),
			("change guest, under their name", lambda: self.swap(
				guest_name="Dora Elsewhere", phone=number, blacklist_override_reason="I say so")),
			("new booking", lambda: self._book_with("Somebody Else", number,
			                                        blacklist_override_reason="I say so")),
		):
			with self.subTest(what):
				frappe.local.message_log = []
				with self.assertRaises(frappe.PermissionError) as refused:
					call()
				told = f"{refused.exception} {frappe.local.message_log}"
				self.assertNotIn("Broke a door", told)
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- read back the result
		self.assertEqual(self.res().guest, self.alice)
		self.assertFalse(frappe.db.exists("Agent Action Log", {
			"action_type": "blacklist_override", "reference_name": dora}))

	# -- people listed in online check-in -------------------------------------

	def _online_check_in(self, rows):
		"""The people the old guest listed on the online check-in page."""
		from kamra.public_api import _merge_precheckin_occupants
		_merge_precheckin_occupants(self.res(), rows)
		frappe.db.set_value("Reservation", self.name, "precheckin_status", "Submitted")

	def _people(self) -> list[str]:
		return sorted(o.full_name for o in self.res().occupants)

	def _row(self, full_name: str) -> str:
		return next(o.name for o in self.res().occupants if o.full_name == full_name)

	def test_people_the_old_guest_listed_online_leave_with_them(self):
		add_occupant_names(self.name, ["Desk Added"])
		# the guest's list repeats the desk's name and adds two of their own
		self._online_check_in([{"full_name": "Desk Added"},
		                       {"full_name": "Friend Online", "id_type": "Passport", "id_number": "X1234567"},
		                       {"full_name": "Child Online", "age": 5}])
		self.assertEqual(self._people(), ["Child Online", "Desk Added", "Friend Online"])
		out = self.swap()
		# the desk's own row stays, even though the old guest sent its name back
		self.assertEqual(self._people(), ["Desk Added"])
		self.assertEqual(out["removed_occupants"], 2)
		self.assertFalse(frappe.db.exists("Stay Occupant", {"id_number": "X1234567"}))
		comments = frappe.get_all("Comment", filters={
			"reference_doctype": "Reservation", "reference_name": self.name,
			"comment_type": "Comment"}, pluck="content")
		self.assertTrue(any("People listed in online check-in and removed: 2" in c for c in comments),
		                comments)

	def test_a_listed_person_the_desk_confirmed_stays_and_the_price_does_not_move(self):
		self._online_check_in([{"full_name": "Child Online", "age": 5},
		                       {"full_name": "Photographed Online"},
		                       {"full_name": "Never Seen Online"}])
		# at the counter the desk confirms the child's age and photographs another
		update_occupants(self.name, [
			{"row": self._row("Child Online"), "full_name": "Child Online", "age": 5},
			{"row": self._row("Photographed Online"), "full_name": "Photographed Online"},
			{"row": self._row("Never Seen Online"), "full_name": "Never Seen Online"}])
		upload_occupant_id(self.name, self._row("Photographed Online"), _png_data_url(), kind="photo")
		price = float(self.res().amount_after_tax)
		out = self.swap()
		self.assertEqual(self._people(), ["Child Online", "Photographed Online"])
		self.assertEqual(out["removed_occupants"], 1)
		self.assertEqual(float(self.res().amount_after_tax), price)
		self.assertTrue(next(o for o in self.res().occupants if o.full_name == "Photographed Online").photo)

	def test_a_listed_person_with_a_scanned_id_stays(self):
		self._online_check_in([{"full_name": "Scanned Online"}])
		upload_occupant_id(self.name, self._row("Scanned Online"), _png_data_url(), kind="id")
		self.assertEqual(self.swap()["removed_occupants"], 0)
		self.assertEqual(self._people(), ["Scanned Online"])

	def test_the_mark_survives_a_desk_save_without_row_ids(self):
		self._online_check_in([{"full_name": "Friend Online"}])
		update_occupants(self.name, [{"full_name": "Friend Online"}, {"full_name": "Desk Added"}])
		self.assertEqual(self.swap()["removed_occupants"], 1)
		self.assertEqual(self._people(), ["Desk Added"])

	def test_the_desks_own_list_is_left_alone(self):
		add_occupant_names(self.name, ["Desk One", "Desk Two"])
		out = self.swap()
		self.assertEqual(out["removed_occupants"], 0)
		self.assertEqual(self._people(), ["Desk One", "Desk Two"])
		comments = frappe.get_all("Comment", filters={
			"reference_doctype": "Reservation", "reference_name": self.name,
			"comment_type": "Comment"}, pluck="content")
		self.assertFalse(any("online check-in" in c for c in comments), comments)

	# -- a number on the blacklist ------------------------------------------

	def _listed(self, phone="+256700000009"):
		"""A blacklisted guest who has never stayed anywhere: every desk may see them."""
		return frappe.get_doc({"doctype": "Guest", "first_name": "Barred", "last_name": "Person",
			"phone": phone, "blacklisted": 1,
			"blacklist_reason": "Damage"}).insert(ignore_permissions=True).name

	def _book_with(self, guest_name, phone, **kw):
		return create_booking(self.property, self.room_type, str(add_days(nowdate(), 40)),
		                      str(add_days(nowdate(), 41)), guest_name, phone=phone, **kw)

	def _refusal(self, call) -> str:
		"""Everything the screen would be told: the error and the queued messages."""
		frappe.local.message_log = []
		with self.assertRaises(frappe.ValidationError) as refused:
			call()
		return f"{refused.exception} {frappe.local.message_log}"

	def test_a_number_listed_at_another_hotel_is_refused_without_saying_who_or_why(self):
		_booking, dora = self._other_hotel_booking()
		frappe.db.set_value("Guest", dora, {"blacklisted": 1, "blacklist_reason": "Broke a door"})
		self._limit_desk_to_this_hotel()
		frappe.set_user(self.desk)  # nosemgrep: frappe-setuser -- the user under test
		number = "+256 700 000 007"
		for what, call in (
			("change guest", lambda: self.swap(guest_name="Somebody Else", phone=number)),
			("change guest, under their name", lambda: self.swap(guest_name="Dora Elsewhere", phone=number)),
			("new booking", lambda: self._book_with("Somebody Else", number)),
		):
			with self.subTest(what):
				told = self._refusal(call)
				self.assertIn("blacklisted", told)
				self.assertNotIn("Dora", told)
				self.assertNotIn("Broke a door", told)
		alert = guest_alert(phone=number)
		self.assertTrue(alert["blacklisted"])
		self.assertIsNone(alert["guest"])
		self.assertIsNone(alert["full_name"])
		self.assertIsNone(alert["blacklist_reason"])
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- read back the result
		self.assertEqual(self.res().guest, self.alice)

	def test_a_number_the_desk_may_see_is_refused_saying_who_and_why(self):
		self._listed()
		frappe.set_user(self.desk)  # nosemgrep: frappe-setuser -- the user under test
		for what, call in (
			("change guest", lambda: self.swap(guest_name="Somebody Else", phone="+256 700 000 009")),
			("new booking", lambda: self._book_with("Somebody Else", "+256 700 000 009")),
		):
			with self.subTest(what):
				told = self._refusal(call)
				self.assertIn("Barred Person", told)
				self.assertIn("Damage", told)

	def test_the_warning_is_about_the_blacklisted_profile_when_a_number_is_shared(self):
		banned = self._listed()
		# a newer, clean profile on the same number: a plain lookup would find this one
		frappe.get_doc({"doctype": "Guest", "first_name": "Honest", "last_name": "Sharer",
			"phone": "+256700000009"}).insert(ignore_permissions=True)
		alert = guest_alert(phone="+256700000009")
		self.assertTrue(alert["blacklisted"])
		self.assertEqual(alert["guest"], banned)

	def test_a_hotel_admins_override_books_the_name_typed_not_the_listed_profile(self):
		banned = self._listed()
		out = self.swap(guest_name="Somebody Else", phone="+256 700 000 009",
		                blacklist_override_reason="Shared family phone")
		self.assertNotEqual(out["guest"], banned)
		self.assertTrue(out["new_profile"])
		self.assertEqual(self.res().guest_name, "Somebody Else")
		self.assertEqual(frappe.db.get_value("Guest", banned, "full_name"), "Barred Person")
		self.assertTrue(frappe.db.exists("Agent Action Log", {
			"action_type": "blacklist_override", "reference_name": banned}))

	def test_a_new_booking_override_books_the_name_typed_too(self):
		banned = self._listed()
		out = self._book_with("Somebody Else", "+256 700 000 009",
		                      blacklist_override_reason="Shared family phone")
		booked = frappe.db.get_value("Reservation", out["reservation"], ["guest", "guest_name"],
		                             as_dict=True)
		self.assertNotEqual(booked.guest, banned)
		self.assertEqual(booked.guest_name, "Somebody Else")

	def test_an_override_under_the_listed_name_books_that_profile(self):
		banned = self._listed()
		out = self.swap(guest_name="barred person", phone="+256 700 000 009",
		                blacklist_override_reason="Manager OK")
		self.assertEqual(out["guest"], banned)

	def test_the_desk_cannot_override_a_listed_number(self):
		self._listed()
		frappe.set_user(self.desk)  # nosemgrep: frappe-setuser -- the user under test
		for call in (
			lambda: self.swap(guest_name="Somebody Else", phone="+256 700 000 009",
			                  blacklist_override_reason="I say so"),
			lambda: self._book_with("Somebody Else", "+256 700 000 009",
			                        blacklist_override_reason="I say so"),
		):
			with self.assertRaises(frappe.PermissionError):
				call()
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- read back the result
		self.assertEqual(self.res().guest, self.alice)

	# -- who may ----------------------------------------------------------

	def test_the_front_desk_may_and_housekeeping_may_not(self):
		frappe.set_user(self.housekeeper)  # nosemgrep: frappe-setuser -- the role under test
		with self.assertRaises(frappe.PermissionError):
			self.swap()
		frappe.set_user(self.desk)  # nosemgrep: frappe-setuser -- the role under test
		self.swap()
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- read back the result
		self.assertEqual(self.res().guest_name, "Bob Arrived")
