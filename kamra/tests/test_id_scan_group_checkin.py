"""Reading an ID scanner's text, one card per guest at check-in, and
checking a whole group in.

kamra.id_scan (passport and ID card MRZ, the India pack's Aadhaar QR),
the ID step counting every adult on the booking, the occupant register
keeping a stored ID number when check-in sends the masked one, and
api.group_check_in.
"""

from __future__ import annotations

import gzip

import frappe

from kamra import api, checkin, id_scan
from kamra.localization.india import aadhaar_qr
from kamra.tests.audit_fixtures import (
	PROP_A,
	TODAY,
	AuditTestCase,
	d,
	make_property,
	make_reservation,
	make_room,
	make_room_type,
)

# ICAO 9303 specimen documents
TD3 = ("P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<\n"
       "L898902C36UTO7408122F1204159ZE184226B<<<<<10")
TD1 = ("I<UTOD231458907<<<<<<<<<<<<<<<\n"
       "7408122F1204159UTO<<<<<<<<<<<6\n"
       "ERIKSSON<<ANNA<MARIA<<<<<<<<<<")


def secure_qr(*fields: bytes) -> str:
	body = b"\xff".join(fields) + b"\xff" + b"JP2-PHOTO" + b"S" * 256
	return str(int.from_bytes(gzip.compress(body), "big"))


class IdScanTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.business_date")
		make_property(PROP_A, business_date=TODAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)

	# reading -------------------------------------------------------------

	def test_passport_strip_is_read_and_check_digits_hold(self):
		out = id_scan.parse_mrz(TD3)
		self.assertEqual((out["id_type"], out["id_number"], out["full_name"]),
		                 ("Passport", "L898902C3", "Anna Maria Eriksson"))
		self.assertEqual((out["date_of_birth"], out["id_expiry_date"], out["gender"]),
		                 ("1974-08-12", "2012-04-15", "Female"))
		# run together on one line, the way some readers send it
		self.assertEqual(id_scan.parse_mrz(TD3.replace("\n", ""))["id_number"], "L898902C3")
		with self.assertRaises(frappe.ValidationError):  # one wrong character
			id_scan.parse_mrz(TD3.replace("L898902C3", "L898902C4"))
		self.assertIsNone(id_scan.parse_mrz("hello"))

	def test_id_card_strip_is_read(self):
		out = id_scan.parse_mrz(TD1)
		self.assertEqual((out["id_type"], out["id_number"], out["nationality_code"]),
		                 ("Other", "D23145890", "UTO"))

	def test_aadhaar_secure_qr_keeps_only_the_last_four(self):
		text = secure_qr(b"V2", b"3", b"123420190101120000000", b"Asha Rao",
		                 b"01-02-1990", b"F", b"C/O Ravi", b"Bengaluru Urban", b"",
		                 b"12", b"Indiranagar", b"560038", b"HAL", b"Karnataka",
		                 b"100 Ft Rd", b"Bengaluru North", b"Bengaluru", b"5678")
		out = aadhaar_qr.read(text)
		self.assertEqual((out["id_type"], out["id_number"], out["full_name"]),
		                 ("Aadhaar", "XXXX XXXX 1234", "Asha Rao"))
		self.assertEqual((out["date_of_birth"], out["gender"], out["city"]),
		                 ("1990-02-01", "Female", "Bengaluru"))
		self.assertIn("560038", out["address"])
		self.assertNotIn("20190101", str(out))  # the rest of the reference id stays out

	def test_old_aadhaar_qr(self):
		out = aadhaar_qr.read('<?xml version="1.0"?><PrintLetterBarcodeData uid="987654321012" '
		                      'name="Ravi Kumar" gender="M" yob="1985" vtc="Mysuru" pc="570001"/>')
		self.assertEqual((out["id_number"], out["gender"], out["year_of_birth"]),
		                 ("XXXX XXXX 1012", "Male", "1985"))

	def test_the_endpoint_routes_through_the_property_pack(self):
		out = id_scan.read(PROP_A, TD3)
		self.assertEqual(out["nationality"], "UTO")
		self.assertIsInstance(out["age"], int)
		with self.assertRaises(frappe.ValidationError):
			id_scan.read(PROP_A, "not an id at all")

	# one card per guest ------------------------------------------------------

	def test_every_adult_on_the_booking_needs_an_id(self):
		res = make_reservation(PROP_A, self.rt, TODAY, d(2), adults=3)
		frappe.db.set_value("Guest", res.guest, "id_number", "P1234567")
		ids = checkin.checkin_flow(res.name)["ids"]
		self.assertFalse(ids["ok"])
		self.assertIn("2 more adults", ids["missing"])
		api.update_occupants(res.name, [
			{"full_name": "UT Second", "age": 30, "id_type": "Passport", "id_number": "X99"},
			{"full_name": "UT Third", "age": 31, "id_type": "Passport", "id_number": "X98"}])
		self.assertTrue(checkin.checkin_flow(res.name)["ids"]["ok"])

	def test_saving_cards_keeps_the_stored_id_behind_the_mask(self):
		res = make_reservation(PROP_A, self.rt, TODAY, d(2))
		row = api.update_occupants(res.name, [
			{"full_name": "UT Second", "age": 30, "phone": "999",
			 "id_type": "Passport", "id_number": "Z1234567"}])["rows"][0]
		shown = next(o for o in checkin.checkin_flow(res.name)["ids"]["occupants"])
		self.assertTrue(shown["id_number"].startswith("•"))
		# check-in sends back what it shows, without the phone, plus an edit
		saved = api.update_occupants(res.name, [
			{"row": row["row"], "full_name": "UT Second", "age": 31,
			 "id_number": shown["id_number"]}])["rows"][0]
		self.assertEqual((saved["id_number"], saved["phone"], saved["age"]),
		                 ("Z1234567", "999", 31))

	def test_scan_fills_the_main_guest(self):
		res = make_reservation(PROP_A, self.rt, TODAY, d(2))
		read = id_scan.read(PROP_A, TD3)
		checkin.save_guest_details(res.name, id_type=read["id_type"],
		                           id_number=read["id_number"],
		                           date_of_birth=read["date_of_birth"],
		                           gender=read["gender"],
		                           id_expiry_date=read["id_expiry_date"])
		g = frappe.db.get_value("Guest", res.guest,
		                        ["id_number", "gender", "date_of_birth"], as_dict=True)
		self.assertEqual((g.id_number, g.gender, str(g.date_of_birth)),
		                 ("L898902C3", "Female", "1974-08-12"))


class GroupCheckInTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.rooms = [make_room(PROP_A, self.rt, n) for n in ("201", "202", "203")]

	def test_the_whole_group_goes_in_and_rooms_are_given(self):
		gb = frappe.get_doc({
			"doctype": "Group Booking", "property": PROP_A,
			"group_name": "UT Offsite", "check_in_date": TODAY,
			"check_out_date": d(2), "status": "Confirmed"}).insert(ignore_permissions=True)
		given = make_reservation(PROP_A, self.rt, TODAY, d(2), room=self.rooms[0],
		                         group_booking=gb.name)
		bare = [make_reservation(PROP_A, self.rt, TODAY, d(2), group_booking=gb.name)
		        for _ in range(2)]
		later = make_reservation(PROP_A, self.rt, d(2), d(3), group_booking=gb.name)
		out = api.group_check_in(gb.name)
		self.assertEqual({x["reservation"] for x in out["checked_in"]},
		                 {given.name, *(b.name for b in bare)})
		self.assertEqual(out["skipped"], [])
		rooms = {frappe.db.get_value("Reservation", x["reservation"], "room")
		         for x in out["checked_in"]}
		self.assertEqual(rooms, set(self.rooms))
		self.assertEqual(frappe.db.get_value("Reservation", later.name, "status"), "Confirmed")
		# a second press changes nothing
		self.assertEqual(api.group_check_in(gb.name)["checked_in"], [])

	def test_no_room_left_skips_one_and_keeps_the_rest(self):
		gb = frappe.get_doc({
			"doctype": "Group Booking", "property": PROP_A,
			"group_name": "UT Big Party", "check_in_date": TODAY,
			"check_out_date": d(2), "status": "Confirmed"}).insert(ignore_permissions=True)
		stays = [make_reservation(PROP_A, self.rt, TODAY, d(2), group_booking=gb.name)
		         for _ in range(3)]
		frappe.db.set_value("Room", self.rooms[2], "housekeeping_status", "Out of Order")
		out = api.group_check_in(gb.name)
		self.assertEqual(len(out["checked_in"]), 2)
		self.assertEqual(len(out["skipped"]), 1)
		self.assertIn(out["skipped"][0]["reservation"], {s.name for s in stays})
