"""AioSell channel-manager adapter: the wire-format rules this integration
must not drift from. Pure-function tests - no site, no network - so they run
fast and pin the exact shapes from aiosell-api-context.md.

The consequence layer (booking creation, credit-note cancel, the write-time
villa guard) is covered by the reservation/eval suites; here we defend only
the adapter: webhook parsing, the push-side villa lockout, range collapsing,
and the credentials-pending gate.
"""

import unittest

import frappe

from kamra.channels import aiosell
from kamra.channel_manager import _apply_villa_lockout


def _book_payload(rooms, action="book"):
	return {
		"action": action, "hotelCode": "sandbox-pms", "channel": "Goibibo",
		"bookingId": "111222333", "cmBookingId": "AAABBBCCC",
		"checkin": "2026-08-10", "checkout": "2026-08-12",
		"specialRequests": "Airport Taxi Required", "pah": False,
		"amount": {"amountAfterTax": 1204, "amountBeforeTax": 1075,
		           "tax": 129, "currency": "INR", "commission": None},
		"guest": {"firstName": "Akshay", "lastName": "Kumar",
		          "email": "a@k.com", "phone": "9988776655"},
		"rooms": rooms,
	}


ONE_ROOM = [{"roomCode": "executive", "rateplanCode": "executive-s-ep",
             "guestName": "Akshay Kumar", "occupancy": {"adults": 1, "children": 0},
             "prices": [{"date": "2026-08-10", "sellRate": 537.5},
                        {"date": "2026-08-11", "sellRate": 537.5}]}]


class TestParseWebhook(unittest.TestCase):
	def setUp(self):
		self.conn = frappe._dict()  # parse_webhook is provider-pure

	def test_single_room_book_maps_every_field(self):
		e = aiosell.parse_webhook(self.conn, _book_payload(ONE_ROOM))
		self.assertEqual(len(e), 1)
		e = e[0]
		self.assertEqual(e["event"], "book")
		self.assertEqual(e["booking_id"], "111222333")
		self.assertEqual(e["ota_ref"], "111222333")  # single room -> bare id
		self.assertEqual(e["room_type_external_id"], "executive")
		self.assertEqual(e["external_rate_id"], "executive-s-ep")
		self.assertEqual(e["check_in"], "2026-08-10")
		self.assertEqual(e["check_out"], "2026-08-12")
		self.assertEqual(e["adults"], 1)
		self.assertEqual(e["total"], 1204)  # tax-inclusive booking total
		self.assertEqual(e["notes"], "Airport Taxi Required")

	def test_multi_room_book_splits_and_suffixes_ota_ref(self):
		two = ONE_ROOM + [{"roomCode": "suite", "rateplanCode": "suite-d-cp",
		                   "occupancy": {"adults": 2, "children": 1},
		                   "prices": [{"date": "2026-08-10", "sellRate": 900},
		                              {"date": "2026-08-11", "sellRate": 900}]}]
		e = aiosell.parse_webhook(self.conn, _book_payload(two))
		self.assertEqual([x["ota_ref"] for x in e], ["111222333-0", "111222333-1"])
		# multi-room: per-room total is the sum of its nightly sell rates
		self.assertEqual(e[1]["total"], 1800)
		self.assertEqual(e[1]["room_type_external_id"], "suite")

	def test_modify_is_flagged_modify(self):
		e = aiosell.parse_webhook(self.conn, _book_payload(ONE_ROOM, "modify"))
		self.assertEqual(e[0]["event"], "modify")

	def test_cancel_needs_only_booking_id(self):
		e = aiosell.parse_webhook(self.conn, {
			"action": "cancel", "hotelCode": "sandbox-pms",
			"channel": "Goibibo", "bookingId": "111222333"})
		self.assertEqual(len(e), 1)
		self.assertEqual(e[0]["event"], "cancel")
		self.assertEqual(e[0]["booking_id"], "111222333")
		self.assertEqual(e[0]["ota_ref"], "111222333")

	def test_missing_guest_never_crashes(self):
		p = _book_payload([{"roomCode": "executive", "rateplanCode": "x",
		                    "occupancy": {"adults": 2, "children": 0}}])
		p["guest"] = {}
		e = aiosell.parse_webhook(self.conn, p)[0]
		self.assertEqual(e["guest_name"], "OTA Guest")
		self.assertEqual(e["phone"], "")


class TestVillaLockout(unittest.TestCase):
	def _rows(self, villa_av, std_av):
		return [
			{"room_type": "VILLA", "days": [{"date": "d1", "available": villa_av, "rate": 0}]},
			{"room_type": "STD", "days": [{"date": "d1", "available": std_av, "rate": 0}]},
		]

	META = {"VILLA": {"category": "Villa", "total": 1},
	        "STD": {"category": "Private", "total": 3}}

	def test_all_free_is_untouched(self):
		rows = self._rows(1, 3)
		_apply_villa_lockout(rows, self.META)
		self.assertEqual(rows[0]["days"][0]["available"], 1)
		self.assertEqual(rows[1]["days"][0]["available"], 3)

	def test_a_booked_member_room_zeroes_the_villa(self):
		rows = self._rows(1, 2)  # one std room sold
		_apply_villa_lockout(rows, self.META)
		self.assertEqual(rows[0]["days"][0]["available"], 0)  # villa locked
		self.assertEqual(rows[1]["days"][0]["available"], 2)  # std unchanged

	def test_a_booked_villa_zeroes_every_member(self):
		rows = self._rows(0, 3)  # villa sold
		_apply_villa_lockout(rows, self.META)
		self.assertEqual(rows[0]["days"][0]["available"], 0)
		self.assertEqual(rows[1]["days"][0]["available"], 0)  # std locked

	def test_no_villa_mapped_is_a_noop(self):
		rows = self._rows(1, 2)
		meta = {"VILLA": {"category": "Private", "total": 1},
		        "STD": {"category": "Private", "total": 3}}
		_apply_villa_lockout(rows, meta)
		self.assertEqual(rows[0]["days"][0]["available"], 1)
		self.assertEqual(rows[1]["days"][0]["available"], 2)


class TestRangeCollapse(unittest.TestCase):
	def test_consecutive_equal_values_collapse_to_ranges(self):
		runs = aiosell._runs([{"date": "d1", "value": 5},
		                      {"date": "d2", "value": 5},
		                      {"date": "d3", "value": 3}])
		self.assertEqual(runs, [["d1", "d2", 5], ["d3", "d3", 3]])


class _StubConn:
	def __init__(self, live):
		self.endpoint = None
		if live:
			self.api_username, self._pw = "realuser", "realpw"
			self.pms_slug, self.external_property_id = "sample-pms", "sandbox-pms"
		else:
			self.api_username, self._pw = "<USERNAME>", "<PASSWORD>"
			self.pms_slug, self.external_property_id = "<PMS_SLUG>", "sandbox-pms"

	def get_password(self, *a, **k):
		return self._pw


class TestPush(unittest.TestCase):
	def test_placeholder_credentials_report_pending_not_a_fake_sync(self):
		ok, detail = aiosell.push_ari(_StubConn(live=False), [])
		self.assertFalse(ok)
		self.assertIn("pending", detail.lower())

	def test_push_bodies_match_the_spec_shapes(self):
		captured = []

		def fake_post(conn, path, payload, user, pwd):
			captured.append((path, payload))
			return True, {"success": True, "message": "ok"}

		orig = aiosell._post
		aiosell._post = fake_post
		try:
			snapshot = [{"room_type": "STD", "external_room_id": "executive",
			             "external_rate_id": "executive-s-ep",
			             "days": [{"date": "2026-08-10", "available": 5, "rate": 1749},
			                      {"date": "2026-08-11", "available": 5, "rate": 1749}]}]
			ok, _ = aiosell.push_ari(_StubConn(live=True), snapshot)
		finally:
			aiosell._post = orig

		self.assertTrue(ok)
		paths = {p for p, _ in captured}
		self.assertEqual(paths, {"update/sample-pms", "update-rates/sample-pms"})
		bodies = dict(captured)
		inv = bodies["update/sample-pms"]
		self.assertEqual(inv["hotelCode"], "sandbox-pms")
		room = inv["updates"][0]["rooms"][0]
		self.assertEqual(room, {"roomCode": "executive", "available": 5})
		# two equal days collapsed into one inclusive range
		self.assertEqual(inv["updates"][0]["startDate"], "2026-08-10")
		self.assertEqual(inv["updates"][0]["endDate"], "2026-08-11")
		rate = bodies["update-rates/sample-pms"]["updates"][0]["rates"][0]
		self.assertEqual(rate, {"roomCode": "executive",
		                        "rateplanCode": "executive-s-ep", "rate": 1749})


if __name__ == "__main__":
	unittest.main()
