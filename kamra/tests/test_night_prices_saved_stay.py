"""A Revenue Manager / Hotel Admin re-prices the nights of a booking that
already exists (#634 follow-up).

A saved stay is re-priced around the nights the desk types: every other night
that is not on the bill yet keeps the rate it was booked at (not today's rate
card), a night already on the bill is closed, and a booking whose price is set
another way (a rate plan, an OTA total, a checked-out stay) says why. The same
people may do it as on a new booking: the front desk alone may not."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from kamra.api import (
	PriceConfirmationRequired,
	create_booking,
	get_quote,
	set_stay_prices,
	stay_prices_preview,
	stay_rates,
)

FRONT_DESK = "night.prices.desk@test.local"
DESK_AND_RATES = "night.prices.deskrates@test.local"
RATES_ONLY = "night.prices.rates@test.local"


class SavedStayPricesTestCase(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		frappe.local.lang = "en"
		self.property = frappe.get_doc({"doctype": "Property",
			"property_name": "TEST SAVED NIGHTS " + frappe.generate_hash(length=8),
			"country": "Uganda", "currency": "UGX",
			"rates_include_tax": 1}).insert(ignore_permissions=True).name
		self.room_type = frappe.get_doc({"doctype": "Room Type", "property": self.property,
			"room_type_code": "STD", "room_type_name": "Standard", "base_price": 1000,
			"adults_capacity": 2}).insert(ignore_permissions=True).name
		for n in ("101", "102", "103"):
			frappe.get_doc({"doctype": "Room", "property": self.property,
				"room_type": self.room_type, "room_number": n}).insert(ignore_permissions=True)
		self.ci = str(add_days(nowdate(), 10))
		self.d2 = str(add_days(nowdate(), 11))
		self.d3 = str(add_days(nowdate(), 12))
		self.co = str(add_days(nowdate(), 13))
		self.name = create_booking(
			self.property, self.room_type, self.ci, self.co, "Saved Stay Guest")["reservation"]
		self.desk = self._staff(FRONT_DESK, "Front Desk")
		self.desk_and_rates = self._staff(DESK_AND_RATES, "Front Desk", "Revenue Manager")
		self.rates_only = self._staff(RATES_ONLY, "Revenue Manager")

	def tearDown(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		frappe.db.rollback()
		for user in (FRONT_DESK, DESK_AND_RATES, RATES_ONLY):
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

	def shown(self):
		"""What the guest pays for each night, as the price box shows it. The
		property's rates include tax, so a night's locked rate is the net."""
		return [n["price"] for n in stay_rates(self.name)["nights"]]

	def hand(self):
		return [float(r.hand_price) for r in self.res().night_rates]

	def move_rate_card(self, base_price):
		frappe.db.set_value("Room Type", self.room_type, "base_price", base_price)
		frappe.clear_document_cache("Room Type", self.room_type)

	# -- who may do it ----------------------------------------------------

	def test_the_front_desk_alone_can_not_re_price_a_night(self):
		typed = [{"date": self.ci, "price": 1200}]
		frappe.set_user(self.desk)  # nosemgrep: frappe-setuser -- the role under test
		with self.assertRaises(frappe.PermissionError):
			stay_prices_preview(self.name, typed)
		with self.assertRaises(frappe.PermissionError):
			set_stay_prices(self.name, typed, confirm_price=1)
		# the reservation page still reads, and says this user may not edit
		self.assertFalse(stay_rates(self.name)["can_set"])
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- read back the result
		self.assertEqual(self.hand(), [0, 0, 0])

	def test_a_front_desk_user_who_also_holds_the_revenue_manager_role_can(self):
		frappe.set_user(self.desk_and_rates)  # nosemgrep: frappe-setuser -- the roles under test
		self.assertTrue(stay_rates(self.name)["can_set"])
		set_stay_prices(self.name, [{"date": self.ci, "price": 1200}], confirm_price=1)
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- read back the result
		self.assertEqual(self.hand(), [1200, 0, 0])
		self.assertEqual(self.shown(), [1200, 1000, 1000])

	def test_a_revenue_manager_alone_can_even_without_write_on_reservations(self):
		frappe.set_user(self.rates_only)  # nosemgrep: frappe-setuser -- the role under test
		pv = stay_prices_preview(self.name, [{"date": self.d2, "price": 1500}])
		self.assertAlmostEqual(pv["new_amount"], 3500, places=1)
		set_stay_prices(self.name, [{"date": self.d2, "price": 1500}], confirm_price=1)
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- read back the result
		self.assertEqual(self.hand(), [0, 1500, 0])

	# -- reading a stay ---------------------------------------------------

	def test_each_night_is_listed_as_the_guest_pays_it(self):
		out = stay_rates(self.name)
		self.assertTrue(out["editable"])
		self.assertIsNone(out["why_not"])
		self.assertTrue(out["tax_inclusive"])
		self.assertEqual([n["date"] for n in out["nights"]], [self.ci, self.d2, self.d3])
		# 1000 is the price the guest was quoted (tax inside); the locked rates are net of 5% tax
		self.assertEqual([n["price"] for n in out["nights"]], [1000, 1000, 1000])
		self.assertFalse(any(n["posted"] or n["hand_set"] for n in out["nights"]))

	# -- re-pricing ---------------------------------------------------------

	def test_a_night_is_re_priced_and_the_others_keep_the_rate_they_were_booked_at(self):
		before = float(self.res().amount_after_tax)
		self.assertAlmostEqual(before, 3000, places=1)
		# the rate card moves after the booking: the nights the desk leaves alone must not follow it
		self.move_rate_card(2000)
		out = set_stay_prices(self.name, [{"date": self.d2, "price": 1500}], confirm_price=1)
		res = self.res()
		self.assertEqual(res.auto_price, 0)
		self.assertEqual(self.hand(), [0, 1500, 0])
		self.assertEqual(self.shown(), [1000, 1500, 1000])
		self.assertAlmostEqual(float(res.amount_after_tax), 3500, places=1)
		self.assertAlmostEqual(out["previous_amount"], before, places=1)
		self.assertAlmostEqual(out["amount_after_tax"], 3500, places=1)

	def test_the_preview_writes_nothing_and_the_save_wants_the_new_price_confirmed(self):
		self.move_rate_card(2000)
		typed = [{"date": self.d2, "price": 1500}]
		pv = stay_prices_preview(self.name, typed)
		self.assertTrue(pv["needs_confirmation"])
		self.assertAlmostEqual(pv["current_amount"], 3000, places=1)
		self.assertAlmostEqual(pv["new_amount"], 3500, places=1)
		self.assertAlmostEqual(pv["difference"], 500, places=1)
		self.assertEqual([round(n["rate"] * 1.05, 2) for n in pv["nights"]], [1000, 1500, 1000])
		res = self.res()
		self.assertEqual(res.auto_price, 1)
		self.assertEqual(self.hand(), [0, 0, 0])
		self.assertAlmostEqual(float(res.amount_after_tax), 3000, places=1)
		with self.assertRaises(PriceConfirmationRequired):
			set_stay_prices(self.name, typed)
		self.assertEqual(self.res().auto_price, 1)

	def test_a_second_change_keeps_the_first(self):
		set_stay_prices(self.name, [{"date": self.d2, "price": 1500}], confirm_price=1)
		set_stay_prices(self.name, [{"date": self.ci, "price": 900}], confirm_price=1)
		self.assertEqual(self.hand(), [900, 1500, 0])
		self.assertEqual(self.shown(), [900, 1500, 1000])
		self.assertAlmostEqual(float(self.res().amount_after_tax), 3400, places=1)

	def test_the_change_is_commented_and_logged(self):
		set_stay_prices(self.name, [{"date": self.d2, "price": 1500}], confirm_price=1)
		comments = frappe.get_all("Comment", filters={
			"reference_doctype": "Reservation", "reference_name": self.name,
			"comment_type": "Comment"}, pluck="content")
		self.assertTrue(any("Nightly prices changed" in c and self.d2 in c
		                    and "1,000.00 → 1,500.00" in c for c in comments), comments)
		self.assertTrue(frappe.db.exists("Agent Action Log", {
			"action_type": "set_night_prices", "reference_name": self.name}))

	def test_the_folio_bills_the_new_price(self):
		from kamra.folio import open_folio, post_room_night
		set_stay_prices(self.name, [{"date": self.d2, "price": 1500}], confirm_price=1)
		res = self.res()
		open_folio(res)
		post_room_night(res, self.d2)
		amounts = frappe.get_all("Folio Charge", filters={
			"reservation": self.name, "charge_type": "Room"}, pluck="amount")
		self.assertEqual([round(float(a), 2) for a in amounts],
		                 [round(float(self.res().night_rates[1].rate), 2)])

	# -- nights on the bill ------------------------------------------------

	def test_a_night_on_the_bill_is_closed_and_keeps_its_charge(self):
		from kamra.folio import open_folio, post_room_night
		res = self.res()
		open_folio(res)
		post_room_night(res, self.ci)
		self.move_rate_card(2000)
		out = stay_rates(self.name)
		self.assertEqual([n["posted"] for n in out["nights"]], [True, False, False])
		with self.assertRaisesRegex(frappe.ValidationError, "already on the bill"):
			set_stay_prices(self.name, [{"date": self.ci, "price": 1200}], confirm_price=1)
		set_stay_prices(self.name, [{"date": self.d3, "price": 1100}], confirm_price=1)
		self.assertEqual(self.shown(), [1000, 1000, 1100])
		charged = frappe.get_all("Folio Charge", filters={
			"reservation": self.name, "charge_type": "Room"}, pluck="amount")
		self.assertEqual([round(float(a), 2) for a in charged], [round(1000 / 1.05, 2)])  # the night's net

	# -- a booking priced another way ------------------------------------------

	def test_a_booking_whose_price_is_set_another_way_says_why(self):
		plan = frappe.get_doc({"doctype": "Rate Plan", "property": self.property,
			"rate_plan_name": "Saved", "code": "SAV", "modifier_type": "Percent",
			"modifier_value": -5}).insert(ignore_permissions=True).name
		frappe.db.set_value("Reservation", self.name, "rate_plan", plan)
		out = stay_rates(self.name)
		self.assertFalse(out["editable"])
		self.assertIn("rate plan", out["why_not"])
		with self.assertRaisesRegex(frappe.ValidationError, "rate plan"):
			set_stay_prices(self.name, [{"date": self.ci, "price": 1200}], confirm_price=1)

	def test_a_stay_priced_as_a_whole_is_closed(self):
		other = create_booking(self.property, self.room_type, self.ci, self.d3, "Whole Total",
		                       booked_via="Booking.com", ota_total=2600)["reservation"]
		out = stay_rates(other)
		self.assertFalse(out["editable"])
		self.assertIn("priced as a whole", out["why_not"])
		with self.assertRaises(frappe.ValidationError):
			set_stay_prices(other, [{"date": self.ci, "price": 1200}], confirm_price=1)

	def test_a_checked_out_booking_is_closed(self):
		frappe.db.set_value("Reservation", self.name, "status", "Checked Out")
		self.assertFalse(stay_rates(self.name)["editable"])
		with self.assertRaises(frappe.ValidationError):
			set_stay_prices(self.name, [{"date": self.ci, "price": 1200}], confirm_price=1)

	def test_bad_requests_are_refused(self):
		for why, payload in {
			"nothing": [],
			"a night outside the stay": [{"date": self.co, "price": 1200}],
			"zero": [{"date": self.ci, "price": 0}],
			"three decimals": [{"date": self.ci, "price": 1200.005}],
		}.items():
			with self.subTest(why):
				with self.assertRaises(frappe.ValidationError):
					set_stay_prices(self.name, payload, confirm_price=1)
		self.assertEqual(self.res().auto_price, 1)
