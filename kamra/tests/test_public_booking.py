"""/book quotes each meal plan and shows a real voucher discount."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, flt, nowdate

from kamra.public_api import search_stay, showcase


class PublicBookingTestCase(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		frappe.local.lang = "en"
		self.property = frappe.get_doc({"doctype": "Property",
			"property_name": "TEST BOOK " + frappe.generate_hash(length=8),
			"booking_engine_enabled": 1}).insert(ignore_permissions=True).name
		self.room_type = frappe.get_doc({"doctype": "Room Type", "property": self.property,
			"room_type_code": "STD", "room_type_name": "Standard", "base_price": 1000,
			"adults_capacity": 2}).insert(ignore_permissions=True).name
		frappe.get_doc({"doctype": "Room", "property": self.property,
			"room_type": self.room_type, "room_number": "101"}).insert(ignore_permissions=True)
		self.meal = frappe.get_doc({"doctype": "Meal Plan", "property": self.property,
			"code": "CP", "label": "Breakfast", "price_per_adult": 300}).insert(
			ignore_permissions=True).name
		frappe.get_doc({"doctype": "Discount Voucher", "property": self.property,
			"voucher_code": "TENOFF", "discount_type": "Percent", "value": 10,
			"min_nights": 1}).insert(ignore_permissions=True)
		self.ci, self.co = add_days(nowdate(), 5), add_days(nowdate(), 7)

	def row(self, **kw):
		return search_stay(self.property, self.ci, self.co, 2, 0, **kw)[0]

	def test_each_meal_plan_is_quoted(self):
		row = self.row()
		plans = {p["meal_plan"]: p for p in row["plans"]}
		self.assertEqual(set(plans), {"", self.meal})
		self.assertEqual(plans[""]["amount_after_tax"], row["quote"]["amount_after_tax"])
		self.assertGreater(plans[self.meal]["amount_after_tax"], plans[""]["amount_after_tax"])
		self.assertNotIn("list_amount", plans[""])
		self.assertIn("advance_due", plans[""])

	def test_showcase_payload_includes_max_total_occupants(self):
		data = showcase(self.property)
		rt = [r for r in data["room_types"] if r["name"] == self.room_type][0]
		self.assertIn("max_total_occupants", rt)
		self.assertEqual(rt["max_total_occupants"], 0)

		frappe.db.set_value("Room Type", self.room_type, "max_total_occupants", 4)
		data = showcase(self.property)
		rt = [r for r in data["room_types"] if r["name"] == self.room_type][0]
		self.assertEqual(rt["max_total_occupants"], 4)

	def test_free_meal_plan_is_the_room_only_rate(self):
		ep = frappe.get_doc({"doctype": "Meal Plan", "property": self.property,
			"code": "EP", "label": "Room only"}).insert(ignore_permissions=True).name
		self.assertEqual([p["meal_plan"] for p in self.row()["plans"]], [ep, self.meal])

	def test_voucher_discounts_and_keeps_list_price(self):
		plain = self.row()["plans"][0]["amount_after_tax"]
		plan = self.row(voucher_code="tenoff")["plans"][0]
		self.assertAlmostEqual(plan["list_amount"], plain, places=2)
		self.assertLess(plan["amount_after_tax"], plain)

	def test_unknown_voucher_is_ignored(self):
		plan = self.row(voucher_code="NOPE")["plans"][0]
		self.assertNotIn("list_amount", plan)

	def test_showcase_says_whether_tiers_apply(self):
		self.assertIs(showcase(self.property)["property"]["has_cancellation_tiers"], False)

	def test_link_previews_get_the_hotels_meta_and_staff_pages_stay_private(self):
		from kamra.www.kamra import _with_meta

		frappe.db.set_value("Property", self.property, {"meta_title": "Sea View Inn",
			"meta_description": "Rooms <b>by</b> the sea.", "og_image": "/files/sea.jpg",
			"booking_language": "es"})
		shell = '<html lang="en"><head><meta\n  name="description"\n  content="Kamra" />\n<title>Kamra PMS</title></head></html>'
		from kamra.booking_slugs import slugify
		frappe.form_dict.property = slugify(frappe.db.get_value("Property", self.property, "property_name"))
		try:
			page = _with_meta(shell, "/kamra/book")
		finally:
			frappe.form_dict.pop("property", None)
		self.assertIn("<title>Sea View Inn</title>", page)
		self.assertIn('property="og:image" content="http', page)
		self.assertIn("&lt;b&gt;by&lt;/b&gt;", page)  # escaped, never raw HTML
		self.assertNotIn('content="Kamra"', page)
		self.assertNotIn("noindex", page)
		self.assertIn('<html lang="es">', page)
		from kamra.public_api import _public_locale
		self.assertEqual(_public_locale(self.property)["default_language"], "es")
		self.assertIn("noindex", _with_meta(shell, "/kamra/folio/F-1"))
		self.assertIn("noindex", _with_meta(shell, "/kamra/checkin/abc"))

	def test_co_branding_uses_the_hotels_own_name_and_never_frappes_default(self):
		from kamra.public_api import site_info

		def brand(name):
			frappe.db.set_single_value("Website Settings", "app_name", name)
			frappe.clear_document_cache("Website Settings", "Website Settings")
			if hasattr(frappe.local, "website_settings"):
				del frappe.local.website_settings
			return site_info()["brand_name"]

		self.assertIsNone(brand("Frappe"))
		self.assertIsNone(brand(""))
		self.assertEqual(brand("Example Hotels"), "Example Hotels")
		self.assertEqual(site_info()["app"], "kamra")

	def test_search_stay_with_multiple_rooms(self):
		res = search_stay(self.property, self.ci, self.co, rooms=[
			{"adults": 2, "children": 0},
			{"adults": 1, "children": 0},
		])
		self.assertTrue(res.get("multi_room"))
		self.assertEqual(len(res["rooms"]), 2)
		self.assertIn(self.room_type, res["inventory"])

	def test_multi_room_booking_creates_linked_reservations(self):
		from kamra.public_api import book

		# Add a second room so inventory permits 2 rooms
		frappe.get_doc({
			"doctype": "Room", "property": self.property,
			"room_type": self.room_type, "room_number": "102",
		}).insert(ignore_permissions=True)

		res = book(
			property=self.property,
			check_in_date=self.ci,
			check_out_date=self.co,
			guest_name="Família Silva",
			phone="+5511988887777",
			email="silva@example.com",
			rooms=[
				{"room_type": self.room_type, "adults": 2, "children": 0},
				{"room_type": self.room_type, "adults": 1, "children": 0},
			],
		)
		self.assertIn("reservations", res)
		self.assertEqual(len(res["reservations"]), 2)
		r1, r2 = res["reservations"]
		doc1 = frappe.get_doc("Reservation", r1)
		doc2 = frappe.get_doc("Reservation", r2)
		self.assertEqual(doc1.guest_name, "Família Silva")
		self.assertEqual(doc2.guest_name, "Família Silva")
		self.assertTrue(doc1.group_booking)
		self.assertEqual(doc1.group_booking, doc2.group_booking)
		self.assertEqual(res["reservation"], r1)
		self.assertEqual(res["group_booking"], doc1.group_booking)
		gb = frappe.get_doc("Group Booking", doc1.group_booking)
		self.assertEqual(gb.master_reservation, r1)
		self.assertGreater(res["amount_after_tax"], 0)
		self.assertIn("cleaning_fee", res)
		self.assertIn("security_deposit_amount", res)

	def test_more_than_ten_rooms_rejected(self):
		from kamra.public_api import book
		with self.assertRaises(frappe.ValidationError):
			search_stay(self.property, self.ci, self.co, rooms=[{"adults": 1}] * 11)
		with self.assertRaises(frappe.ValidationError):
			book(
				property=self.property, check_in_date=self.ci, check_out_date=self.co,
				guest_name="Ten Plus", phone="+5511988887777",
				rooms=[{"room_type": self.room_type, "adults": 1}] * 11,
			)

	def test_malformed_rooms_payload_rejected(self):
		from kamra.public_api import book
		for bad in ["not-json", "{}", [123], [{"adults": 0}], [{"adults": 1, "children": -1}]]:
			with self.assertRaises(frappe.ValidationError):
				search_stay(self.property, self.ci, self.co, rooms=bad)
			with self.assertRaises(frappe.ValidationError):
				book(
					property=self.property, check_in_date=self.ci, check_out_date=self.co,
					guest_name="Bad Payload", phone="+5511988887777", rooms=bad,
				)

	def test_multi_room_atomic_rollback_on_partial_failure(self):
		from unittest.mock import patch
		import kamra.public_api
		from kamra.public_api import book

		for r_num in ["102", "103"]:
			if not frappe.db.exists("Room", {"property": self.property, "room_number": r_num}):
				frappe.get_doc({
					"doctype": "Room", "property": self.property,
					"room_type": self.room_type, "room_number": r_num,
				}).insert(ignore_permissions=True)

		before_res = frappe.db.count("Reservation", {"property": self.property})
		before_gb = frappe.db.count("Group Booking", {"property": self.property})

		real_book_single = kamra.public_api._book_single_stay
		calls = [0]
		inserted_in_flight = []

		def side_effect(*args, **kwargs):
			calls[0] += 1
			if calls[0] == 3:
				inserted_count = frappe.db.count("Reservation", {"property": self.property})
				inserted_in_flight.append(inserted_count)
				raise RuntimeError("Simulated failure while inserting room 3")
			return real_book_single(*args, **kwargs)

		with patch("kamra.public_api._book_single_stay", side_effect=side_effect):
			with self.assertRaises(RuntimeError):
				book(
					property=self.property, check_in_date=self.ci, check_out_date=self.co,
					guest_name="Fail Test", phone="+5511988887777",
					rooms=[
						{"room_type": self.room_type, "adults": 2, "children": 0},
						{"room_type": self.room_type, "adults": 2, "children": 0},
						{"room_type": self.room_type, "adults": 2, "children": 0},
					],
				)

		self.assertEqual(inserted_in_flight, [before_res + 2])
		self.assertEqual(frappe.db.count("Reservation", {"property": self.property}), before_res)
		self.assertEqual(frappe.db.count("Group Booking", {"property": self.property}), before_gb)

	def test_single_use_voucher_applied_once_across_rooms(self):
		from kamra.public_api import book

		if not frappe.db.exists("Room", {"property": self.property, "room_number": "102"}):
			frappe.get_doc({
				"doctype": "Room", "property": self.property,
				"room_type": self.room_type, "room_number": "102",
			}).insert(ignore_permissions=True)

		v = frappe.get_doc({
			"doctype": "Discount Voucher", "property": self.property,
			"voucher_code": "ONCEONLY", "discount_type": "Percent", "value": 10,
			"min_nights": 1, "max_uses": 1,
		}).insert(ignore_permissions=True)
		res = book(
			property=self.property, check_in_date=self.ci, check_out_date=self.co,
			guest_name="Voucher Guest", phone="+5511988887777", voucher_code="ONCEONLY",
			rooms=[
				{"room_type": self.room_type, "adults": 2, "children": 0},
				{"room_type": self.room_type, "adults": 2, "children": 0},
			],
		)
		self.assertEqual(len(res["reservations"]), 2)
		r1, r2 = res["reservations"]
		d1 = frappe.get_doc("Reservation", r1)
		d2 = frappe.get_doc("Reservation", r2)
		# voucher link kept on every room; use counted once under the lock
		self.assertEqual(d1.voucher, v.name)
		self.assertEqual(d2.voucher, v.name)
		self.assertGreater(flt(d1.discount_amount), 0)
		self.assertGreater(flt(d2.discount_amount), 0)
		self.assertAlmostEqual(
			flt(d1.amount_after_tax), flt(d2.amount_after_tax), places=2)
		self.assertEqual(frappe.db.get_value("Discount Voucher", v.name, "times_used"), 1)
		with self.assertRaises(Exception):
			book(
				property=self.property, check_in_date=self.ci, check_out_date=self.co,
				guest_name="Second Guest", phone="+5511988887777", voucher_code="ONCEONLY",
				room_type=self.room_type, adults=2, children=0,
			)

	def test_child_ages_per_room_and_combined_advance(self):
		from kamra.public_api import book
		frappe.db.set_value("Property", self.property, {
			"booking_payment_mode": "Advance percent",
			"advance_percent": 50,
		})
		frappe.clear_document_cache("Property", self.property)
		res = search_stay(self.property, self.ci, self.co, rooms=[
			{"adults": 2, "children": 1, "child_ages": [3]},
			{"adults": 2, "children": 1, "child_ages": [9]},
		])
		self.assertEqual(len(res["rooms"]), 2)
		r1_row = [r for r in res["rooms"][0] if r["room_type"] == self.room_type][0]
		r2_row = [r for r in res["rooms"][1] if r["room_type"] == self.room_type][0]
		self.assertEqual(r1_row["infants"], 1)
		self.assertEqual(r1_row["children"], 0)
		self.assertEqual(r2_row["infants"], 0)
		self.assertEqual(r2_row["children"], 1)

		out = book(
			property=self.property, check_in_date=self.ci, check_out_date=self.co,
			guest_name="Ages Guest", phone="+5511988887777",
			rooms=[
				{"room_type": self.room_type, "adults": 2, "children": 1, "child_ages": [3]},
				{"room_type": self.room_type, "adults": 2, "children": 1, "child_ages": [9]},
			],
		)
		self.assertEqual(out["advance_due"], round(out["amount_after_tax"] * 0.5, 2))
		self.assertEqual(out["balance_at_hotel"], round(out["amount_after_tax"] - out["advance_due"], 2))
		self.assertEqual(out["reservation"], out["reservations"][0])
		self.assertTrue(out["group_booking"].startswith("GRP-") or frappe.db.exists("Group Booking", out["group_booking"]))

	def test_multi_room_idempotent_replay(self):
		from kamra.public_api import book

		if not frappe.db.exists("Room", {"property": self.property, "room_number": "102"}):
			frappe.get_doc({
				"doctype": "Room", "property": self.property,
				"room_type": self.room_type, "room_number": "102",
			}).insert(ignore_permissions=True)

		before_gb = frappe.db.count("Group Booking", {"property": self.property})
		res1 = book(
			property=self.property, check_in_date=self.ci, check_out_date=self.co,
			guest_name="Idempotent Guest", phone="+5511988887777",
			idempotency_key="MULTI-IDEMP-TEST-123",
			rooms=[
				{"room_type": self.room_type, "adults": 2, "children": 0},
				{"room_type": self.room_type, "adults": 1, "children": 0},
			],
		)
		self.assertEqual(res1["idempotent_replay"], 0)
		self.assertEqual(frappe.db.count("Group Booking", {"property": self.property}), before_gb + 1)

		res2 = book(
			property=self.property, check_in_date=self.ci, check_out_date=self.co,
			guest_name="Idempotent Guest", phone="+5511988887777",
			idempotency_key="MULTI-IDEMP-TEST-123",
			rooms=[
				{"room_type": self.room_type, "adults": 2, "children": 0},
				{"room_type": self.room_type, "adults": 1, "children": 0},
			],
		)
		self.assertEqual(res2["idempotent_replay"], 1)
		self.assertEqual(res2["reservation"], res1["reservation"])
		self.assertEqual(res2["group_booking"], res1["group_booking"])
		self.assertEqual(res2["reservations"], res1["reservations"])
		self.assertEqual(res2["needs_confirmation"], res1["needs_confirmation"])
		self.assertEqual(res2["is_holiday"], res1["is_holiday"])
		self.assertEqual(res2.get("confirmation_reason"), res1.get("confirmation_reason"))
		self.assertEqual(frappe.db.count("Group Booking", {"property": self.property}), before_gb + 1)

	def test_multi_room_idempotent_replay_keeps_confirmation_and_holiday(self):
		from kamra.public_api import book

		frappe.db.set_value("Room Type", self.room_type, "max_extra_beds", 1)
		frappe.clear_document_cache("Room Type", self.room_type)
		frappe.get_doc({
			"doctype": "Season", "property": self.property,
			"season_name": "Holiday Test", "start_date": self.ci, "end_date": self.ci,
			"is_holiday": 1, "adjustment_type": "Percent", "adjustment_value": 0,
		}).insert(ignore_permissions=True)
		if not frappe.db.exists("Room", {"property": self.property, "room_number": "102"}):
			frappe.get_doc({
				"doctype": "Room", "property": self.property,
				"room_type": self.room_type, "room_number": "102",
			}).insert(ignore_permissions=True)

		key = "MULTI-IDEMP-CONFIRM-HOLIDAY"
		res1 = book(
			property=self.property, check_in_date=self.ci, check_out_date=self.co,
			guest_name="Confirm Guest", phone="+5511988887777",
			idempotency_key=key,
			rooms=[
				{"room_type": self.room_type, "adults": 3, "children": 0},
				{"room_type": self.room_type, "adults": 2, "children": 0},
			],
		)
		self.assertTrue(res1["needs_confirmation"])
		self.assertTrue(res1["is_holiday"])
		self.assertEqual(res1["idempotent_replay"], 0)

		res2 = book(
			property=self.property, check_in_date=self.ci, check_out_date=self.co,
			guest_name="Confirm Guest", phone="+5511988887777",
			idempotency_key=key,
			rooms=[
				{"room_type": self.room_type, "adults": 3, "children": 0},
				{"room_type": self.room_type, "adults": 2, "children": 0},
			],
		)
		self.assertEqual(res2["idempotent_replay"], 1)
		self.assertTrue(res2["needs_confirmation"])
		self.assertTrue(res2["is_holiday"])
		self.assertEqual(res2["confirmation_reason"], res1["confirmation_reason"])

	def test_per_room_validation_includes_room_index(self):
		with self.assertRaises(frappe.ValidationError) as ctx:
			search_stay(self.property, self.ci, self.co, rooms=[
				{"adults": 2, "children": 0},
				{"adults": 0, "children": 0},
			])
		self.assertIn("Room 2", str(ctx.exception))
		log = getattr(frappe.local, "message_log", None) or []
		self.assertTrue(log)
		entry = log[-1]
		data = frappe.parse_json(entry) if isinstance(entry, str) else entry
		self.assertEqual(data.get("room_index"), 1)

	def test_booking_room_abuse_rate_limit(self):
		from kamra.public_api import _check_booking_room_rate_limit
		ip = getattr(frappe.local, "request_ip", None) or "127.0.0.1"
		key = f"kamra:rate_limit:book_rooms:{ip}"
		cache = frappe.cache()
		cache.delete_value(key)

		_check_booking_room_rate_limit(6)
		_check_booking_room_rate_limit(4)  # 10 rooms allowed
		with self.assertRaises(frappe.TooManyRequestsError):
			_check_booking_room_rate_limit(1)  # 11 rooms blocked
		cache.delete_value(key)

