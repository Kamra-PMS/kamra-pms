"""The desk sets the price of each night on a new booking (#634).

A Revenue Manager / Hotel Admin types a price for some nights; Kamra prices
the rest. The quote, the booking, its locked night rates and the folio's first
room night all carry the typed price, and anything else that would also set
the room price (a voucher, a rate plan, an OTA total) is refused."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from kamra.api import amend_stay, create_booking, create_group_booking, get_quote, walk_in


class NightPricesBookingTestCase(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		frappe.local.lang = "en"
		self.property = frappe.get_doc({"doctype": "Property",
			"property_name": "TEST NIGHTS " + frappe.generate_hash(length=8),
			"country": "Uganda", "currency": "UGX",
			"rates_include_tax": 1}).insert(ignore_permissions=True).name
		self.room_type = frappe.get_doc({"doctype": "Room Type", "property": self.property,
			"room_type_code": "STD", "room_type_name": "Standard", "base_price": 1000,
			"adults_capacity": 2}).insert(ignore_permissions=True).name
		for n in ("101", "102", "103", "104", "105"):
			frappe.get_doc({"doctype": "Room", "property": self.property,
				"room_type": self.room_type, "room_number": n}).insert(ignore_permissions=True)
		self.ci = str(add_days(nowdate(), 10))
		self.d2 = str(add_days(nowdate(), 11))
		self.d3 = str(add_days(nowdate(), 12))
		self.co = str(add_days(nowdate(), 13))

	def two_nights(self, **kw):
		return dict(property=self.property, room_type=self.room_type,
		            check_in_date=self.ci, check_out_date=self.d3, **kw)

	def book(self, nights, prices, **kw):
		return create_booking(
			self.property, self.room_type, self.ci, nights, "Night Guest",
			night_prices=prices, **kw)

	# -- the quote --------------------------------------------------------

	def test_one_typed_night_and_the_other_at_bar(self):
		q = get_quote(**self.two_nights(night_prices=[{"date": self.ci, "price": 1200}]))
		first, second = q["nightly"]
		self.assertTrue(first["hand_set"])
		self.assertEqual(first["demand_premium_pct"], 0)
		self.assertNotIn("hand_set", second)
		# the property's rates include tax: 1200 + the 1000 rate card, tax inside
		self.assertAlmostEqual(q["amount_after_tax"], 2200, places=2)
		self.assertAlmostEqual(q["totals"]["total"], 2200, places=2)
		rate_card = get_quote(**self.two_nights())
		self.assertAlmostEqual(rate_card["amount_after_tax"], 2000, places=2)
		self.assertAlmostEqual(second["rate"], rate_card["nightly"][1]["rate"], places=6)

	def test_a_typed_total_splits_exactly_over_the_nights(self):
		q = get_quote(**self.two_nights(night_prices=[
			{"date": self.ci, "price": 115}, {"date": self.d2, "price": 115}]))
		self.assertEqual(round(q["amount_after_tax"], 2), 230)
		q = get_quote(**self.two_nights(night_prices=[
			{"date": self.ci, "price": 120}, {"date": self.d2, "price": 110}]))
		self.assertEqual(round(q["amount_after_tax"], 2), 230)

	def test_prices_before_tax_when_the_property_quotes_before_tax(self):
		frappe.db.set_value("Property", self.property, "rates_include_tax", 0)
		frappe.clear_document_cache("Property", self.property)
		q = get_quote(**self.two_nights(night_prices=[{"date": self.ci, "price": 1200}]))
		self.assertEqual(q["nightly"][0]["rate"], 1200)
		self.assertGreater(q["amount_after_tax"], 2200)  # the tax comes on top

	def test_levy_and_totals_follow_the_typed_price(self):
		frappe.db.set_value("Property", self.property,
		                    {"room_levy_percent": 2, "room_levy_taxable": 0})
		frappe.clear_document_cache("Property", self.property)
		typed = get_quote(**self.two_nights(night_prices=[{"date": self.ci, "price": 1200}]))
		card = get_quote(**self.two_nights())
		self.assertGreater(typed["room_levy"], card["room_levy"])
		self.assertAlmostEqual(
			typed["room_levy"], typed["room_total"] * 0.02, places=6)

	# -- the booking ------------------------------------------------------

	def test_booking_locks_the_typed_night_and_prices_the_other(self):
		out = self.book(self.d3, [{"date": self.ci, "price": 1200}])
		res = frappe.get_doc("Reservation", out["reservation"])
		self.assertEqual(res.auto_price, 0)
		self.assertEqual([float(r.hand_price) for r in res.night_rates], [1200, 0])
		self.assertEqual(len(res.night_rates), 2)
		self.assertAlmostEqual(float(res.amount_after_tax), 2200, places=1)
		q = get_quote(**self.two_nights(night_prices=[{"date": self.ci, "price": 1200}]))
		self.assertEqual(
			[round(float(r.rate), 2) for r in res.night_rates],
			[round(n["rate"], 2) for n in q["nightly"]])
		self.assertEqual(
			[float(r.demand_premium_pct) for r in res.night_rates], [0, 0])
		# the trail: a comment, the action log
		comments = frappe.get_all("Comment", filters={
			"reference_doctype": "Reservation", "reference_name": res.name,
			"comment_type": "Comment"}, pluck="content")
		from kamra.localization import money_text
		self.assertTrue(any("Hand-set nightly prices" in c and self.ci in c
		                    and money_text(res.property, 1200) in c for c in comments), comments)
		self.assertTrue(frappe.db.exists("Agent Action Log", {
			"action_type": "set_night_prices", "reference_name": res.name}))

	def test_the_folio_bills_the_typed_night(self):
		from kamra.folio import open_folio, post_room_night
		res = frappe.get_doc("Reservation", self.book(
			self.d3, [{"date": self.ci, "price": 1200}])["reservation"])
		open_folio(res)
		post_room_night(res, self.ci)
		amounts = frappe.get_all("Folio Charge", filters={
			"reservation": res.name, "charge_type": "Room"}, pluck="amount")
		self.assertEqual([round(float(a), 2) for a in amounts],
		                 [round(float(res.night_rates[0].rate), 2)])

	def test_an_unrelated_save_keeps_the_typed_prices(self):
		res = frappe.get_doc("Reservation", self.book(
			self.d3, [{"date": self.ci, "price": 1200}])["reservation"])
		before = float(res.amount_after_tax)
		res.special_requests = "quiet room"
		res.save(ignore_permissions=True)
		res.reload()
		self.assertEqual(float(res.amount_after_tax), before)
		self.assertEqual([float(r.hand_price) for r in res.night_rates], [1200, 0])

	def test_walk_in_takes_the_typed_price(self):
		room = frappe.get_all("Room", filters={"property": self.property}, pluck="name")[0]
		today = nowdate()
		out = walk_in(self.property, self.room_type, room, str(add_days(today, 2)),
		              "Walk Typed", defer_check_in=1,
		              night_prices=[{"date": today, "price": 1300}])
		res = frappe.get_doc("Reservation", out["reservation"])
		self.assertEqual(res.auto_price, 0)
		self.assertEqual([float(r.hand_price) for r in res.night_rates], [1300, 0])
		self.assertAlmostEqual(float(res.amount_after_tax), 2300, places=1)

	def test_group_rooms_keep_their_own_prices(self):
		out = create_group_booking(
			self.property, "Two prices", self.ci, self.d3, [
				{"room_type": self.room_type, "count": 1, "guest_name": "One",
				 "night_prices": [{"date": self.ci, "price": 1200}]},
				{"room_type": self.room_type, "count": 1, "guest_name": "Two",
				 "night_prices": [{"date": self.d2, "price": 900}]},
				{"room_type": self.room_type, "count": 1, "guest_name": "Three"},
			], "Group Lead")
		self.assertEqual(len(out["created"]), 3)
		one, two, three = (frappe.get_doc("Reservation", n) for n in out["created"])
		self.assertEqual([float(r.hand_price) for r in one.night_rates], [1200, 0])
		self.assertEqual([float(r.hand_price) for r in two.night_rates], [0, 900])
		self.assertAlmostEqual(float(one.amount_after_tax), 2200, places=1)
		self.assertAlmostEqual(float(two.amount_after_tax), 1900, places=1)
		self.assertEqual(three.auto_price, 1)
		self.assertAlmostEqual(float(three.amount_after_tax), 2000, places=1)

	# -- refusals ---------------------------------------------------------

	def test_voucher_with_typed_nights_is_refused(self):
		frappe.get_doc({"doctype": "Discount Voucher", "property": self.property,
			"voucher_code": "NIGHT10", "discount_type": "Percent", "value": 10,
			}).insert(ignore_permissions=True)
		typed = [{"date": self.ci, "price": 1200}]
		with self.assertRaisesRegex(frappe.ValidationError, "voucher"):
			get_quote(**self.two_nights(voucher_code="NIGHT10", night_prices=typed))
		with self.assertRaisesRegex(frappe.ValidationError, "voucher"):
			self.book(self.d3, typed, voucher_code="NIGHT10")
		# nothing was booked and nothing was dropped
		self.assertFalse(frappe.db.exists("Reservation", {
			"property": self.property, "guest_name": "Night Guest"}))

	def test_rate_plan_with_typed_nights_is_refused(self):
		plan = frappe.get_doc({"doctype": "Rate Plan", "property": self.property,
			"rate_plan_name": "Corp", "code": "CORP", "modifier_type": "Percent",
			"modifier_value": -10}).insert(ignore_permissions=True).name
		typed = [{"date": self.ci, "price": 1200}]
		with self.assertRaisesRegex(frappe.ValidationError, "rate plan"):
			get_quote(**self.two_nights(rate_plan=plan, night_prices=typed))
		with self.assertRaisesRegex(frappe.ValidationError, "rate plan"):
			self.book(self.d3, typed, rate_plan=plan)

	def test_a_company_negotiated_plan_with_typed_nights_is_refused(self):
		plan = frappe.get_doc({"doctype": "Rate Plan", "property": self.property,
			"rate_plan_name": "Contract", "code": "CNTR", "modifier_type": "Percent",
			"modifier_value": -10}).insert(ignore_permissions=True).name
		company = frappe.get_doc({"doctype": "Corporate Account",
			"company_name": "Night Co " + frappe.generate_hash(length=6),
			"negotiated_rate_plan": plan}).insert(ignore_permissions=True).name
		typed = [{"date": self.ci, "price": 1200}]
		with self.assertRaisesRegex(frappe.ValidationError, "negotiated"):
			get_quote(**self.two_nights(company=company, night_prices=typed))
		with self.assertRaisesRegex(frappe.ValidationError, "negotiated"):
			self.book(self.d3, typed, company=company)

	def test_long_stay_discount_with_typed_nights_is_refused(self):
		frappe.get_doc({"doctype": "Long Stay Discount", "property": self.property,
			"min_nights": 2, "discount_percent": 10}).insert(ignore_permissions=True)
		with self.assertRaisesRegex(frappe.ValidationError, "long-stay"):
			get_quote(**self.two_nights(night_prices=[{"date": self.ci, "price": 1200}]))

	def test_an_ota_total_with_typed_nights_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "OTA"):
			self.book(self.d3, [{"date": self.ci, "price": 1200}],
			          booked_via="Booking.com", ota_total=2600)

	def test_group_with_typed_nights_and_a_rate_plan_refuses_before_the_group_exists(self):
		plan = frappe.get_doc({"doctype": "Rate Plan", "property": self.property,
			"rate_plan_name": "Grp", "code": "GRP", "modifier_type": "Percent",
			"modifier_value": -5}).insert(ignore_permissions=True).name
		with self.assertRaisesRegex(frappe.ValidationError, "rate plan"):
			create_group_booking(
				self.property, "Refused", self.ci, self.d3, [
					{"room_type": self.room_type, "count": 1,
					 "night_prices": [{"date": self.ci, "price": 1200}]}],
				"Group Lead", rate_plan=plan)
		self.assertFalse(frappe.db.exists("Group Booking", {
			"property": self.property, "group_name": "Refused"}))

	def test_only_a_rate_manager_can_type_a_night(self):
		typed = [{"date": self.ci, "price": 1200}]
		with patch("kamra.api._can_set_rate", return_value=False):
			with self.assertRaises(frappe.PermissionError):
				get_quote(**self.two_nights(night_prices=typed))
			with self.assertRaises(frappe.PermissionError):
				self.book(self.d3, typed)
			with self.assertRaises(frappe.PermissionError):
				create_group_booking(
					self.property, "No rights", self.ci, self.d3,
					[{"room_type": self.room_type, "count": 1, "night_prices": typed}],
					"Group Lead")
			# without typed nights nothing changes for the desk
			self.assertTrue(get_quote(**self.two_nights())["amount_after_tax"])

	def test_bad_payloads_are_refused_not_coerced(self):
		from kamra.pricing import MAX_NIGHT_PRICE
		bad = {
			"outside the stay": [{"date": self.d3, "price": 100}],
			"before the stay": [{"date": str(add_days(self.ci, -1)), "price": 100}],
			"zero": [{"date": self.ci, "price": 0}],
			"negative": [{"date": self.ci, "price": -5}],
			"not a number": [{"date": self.ci, "price": "abc"}],
			"nan": [{"date": self.ci, "price": "nan"}],
			"infinite": [{"date": self.ci, "price": float("inf")}],
			"boolean": [{"date": self.ci, "price": True}],
			"too many decimals": [{"date": self.ci, "price": 100.005}],
			"over the bound": [{"date": self.ci, "price": int(MAX_NIGHT_PRICE) + 1}],
			"twice": [{"date": self.ci, "price": 100}, {"date": self.ci, "price": 90}],
			"not a date": [{"date": "soon", "price": 100}],
			"extra key": [{"date": self.ci, "price": 100, "note": "x"}],
			"not a list": {"date": self.ci, "price": 100},
			"a bare number": [100],
		}
		for why, payload in bad.items():
			with self.subTest(why):
				with self.assertRaises(frappe.ValidationError):
					get_quote(**self.two_nights(night_prices=payload))
		with self.assertRaises(frappe.ValidationError):
			get_quote(**self.two_nights(night_prices="{not json"))
		# a JSON string of a good payload is fine
		q = get_quote(**self.two_nights(
			night_prices=frappe.as_json([{"date": self.ci, "price": 1200}])))
		self.assertTrue(q["nightly"][0]["hand_set"])

	def test_a_day_use_stay_has_no_nights_to_type(self):
		from kamra.pricing import quote
		with self.assertRaises(frappe.ValidationError):
			quote(self.property, self.room_type, self.ci, self.ci,
			      night_prices=[{"date": self.ci, "price": 1200}])

	# -- after a change ---------------------------------------------------

	def test_a_date_change_keeps_the_typed_nights_still_in_the_stay(self):
		out = self.book(self.co, [{"date": self.ci, "price": 1200},
		                          {"date": self.d3, "price": 800}])
		name = out["reservation"]
		res = frappe.get_doc("Reservation", name)
		self.assertAlmostEqual(float(res.amount_after_tax), 3000, places=1)  # 1200 + 1000 + 800
		# the last night goes: the first stays at 1200
		amend_stay(name, self.ci, self.d3, confirm_price=1)
		res.reload()
		self.assertEqual(res.auto_price, 0)
		self.assertEqual([float(r.hand_price) for r in res.night_rates], [1200, 0])
		self.assertAlmostEqual(float(res.amount_after_tax), 2200, places=1)
		# the first night goes too, and so does every typed night: back to auto pricing
		amend_stay(name, self.d2, self.d3, confirm_price=1)
		res.reload()
		self.assertEqual(res.auto_price, 1)
		self.assertEqual([float(r.hand_price) for r in res.night_rates], [0])
		self.assertAlmostEqual(float(res.amount_after_tax), 1000, places=1)

	def test_the_amend_preview_prices_around_the_typed_nights(self):
		from kamra.api import amend_stay_preview
		name = self.book(self.d3, [{"date": self.ci, "price": 1200}])["reservation"]
		pv = amend_stay_preview(name, self.ci, self.co)
		self.assertTrue(pv["reprices"])
		self.assertAlmostEqual(pv["new_amount"], 3200, places=1)  # 1200 + 1000 + 1000
		self.assertTrue(pv["needs_confirmation"])
