"""A Revenue Manager / Hotel Admin re-prices the nights of a booking that
already exists (#634 follow-up).

A saved stay is re-priced around the nights the desk types: every other night
that is not on the bill yet keeps the rate it was booked at (not today's rate
card), a night already on the bill is closed, and a booking whose price is set
another way (a rate plan, an OTA total, a checked-out stay) says why. The same
people may do it as on a new booking: the front desk alone may not."""

from unittest import mock

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
SCOPED = "night.prices.scoped@test.local"


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
		for user in (FRONT_DESK, DESK_AND_RATES, RATES_ONLY, SCOPED):
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

	def save(self, typed):
		"""What the page does: look at the new total, then save with that total."""
		shown = stay_prices_preview(self.name, typed)["new_amount"]
		return set_stay_prices(self.name, typed, expected_total=shown)

	def shown(self):
		"""What the guest pays for each night, as the price box shows it. The
		property's rates include tax, so a night's locked rate is the net."""
		return [n["price"] for n in stay_rates(self.name)["nights"]]

	def hand(self):
		return [float(r.hand_price) for r in self.res().night_rates]

	def assert_reads_in_property_currency(self, error, *amounts):
		"""money_text, as the comment and the action log: UGX has no decimals."""
		from kamra.localization import money_text
		for amount in amounts:
			self.assertIn(money_text(self.property, amount), str(error))
		self.assertNotIn(".00", str(error))

	def trail(self):
		"""The reservation's comments and logged price changes."""
		comments = frappe.get_all("Comment", filters={
			"reference_doctype": "Reservation", "reference_name": self.name,
			"comment_type": "Comment"}, pluck="content")
		logged = frappe.db.count("Agent Action Log", {
			"action_type": "set_night_prices", "reference_name": self.name})
		return [c for c in comments if "ightly prices" in c], logged

	def check_in_with_a_folio(self, extra: float, paid: float) -> str:
		"""In house: the first night on the bill, a sundry of `extra`, `paid` received."""
		from kamra.folio import open_folio, post_room_night, save_folios
		frappe.db.set_value("Reservation", self.name, "status", "Checked In")
		res = self.res()
		folio = open_folio(res)
		post_room_night(res, self.ci)
		doc = frappe.get_doc("Folio", folio)
		doc.append("charges", {"posting_date": self.ci, "charge_type": "Misc", "reservation": self.name,
			"description": "Minibar", "qty": 1, "rate": extra, "amount": extra, "gst_rate": 0})
		doc.append("payments", {"posting_date": nowdate(), "mode": "Cash", "amount": paid,
			"payment_kind": "Payment"})
		save_folios({folio: doc})  # totals and balance, as the app saves a folio
		return folio

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
			set_stay_prices(self.name, typed, expected_total=3200)
		# the reservation page still reads, and says this user may not edit
		self.assertFalse(stay_rates(self.name)["can_set"])
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- read back the result
		self.assertEqual(self.hand(), [0, 0, 0])

	def test_a_front_desk_user_who_also_holds_the_revenue_manager_role_can(self):
		frappe.set_user(self.desk_and_rates)  # nosemgrep: frappe-setuser -- the roles under test
		self.assertTrue(stay_rates(self.name)["can_set"])
		self.save([{"date": self.ci, "price": 1200}])
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- read back the result
		self.assertEqual(self.hand(), [1200, 0, 0])
		self.assertEqual(self.shown(), [1200, 1000, 1000])

	def test_a_revenue_manager_alone_can_even_without_write_on_reservations(self):
		frappe.set_user(self.rates_only)  # nosemgrep: frappe-setuser -- the role under test
		pv = stay_prices_preview(self.name, [{"date": self.d2, "price": 1500}])
		self.assertAlmostEqual(pv["new_amount"], 3500, places=1)
		self.save([{"date": self.d2, "price": 1500}])
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
		out = self.save([{"date": self.d2, "price": 1500}])
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
		self.save([{"date": self.d2, "price": 1500}])
		self.save([{"date": self.ci, "price": 900}])
		self.assertEqual(self.hand(), [900, 1500, 0])
		self.assertEqual(self.shown(), [900, 1500, 1000])
		self.assertAlmostEqual(float(self.res().amount_after_tax), 3400, places=1)

	def test_a_night_sent_at_the_price_it_has_is_not_a_change(self):
		same = [{"date": self.d2, "price": 1000}]
		pv = stay_prices_preview(self.name, same)
		self.assertFalse(pv["needs_confirmation"])
		self.assertAlmostEqual(pv["new_amount"], 3000, places=1)
		self.assertEqual(pv["difference"], 0)
		out = set_stay_prices(self.name, same)
		self.assertAlmostEqual(out["amount_after_tax"], 3000, places=1)
		self.assertEqual(self.hand(), [0, 0, 0])
		self.assertEqual(self.res().auto_price, 1)  # the booking was not touched
		self.assertEqual(self.trail(), ([], 0))
		# sent along with a real change, only the real change is recorded
		self.save([{"date": self.ci, "price": 1000}, {"date": self.d2, "price": 1500}])
		self.assertEqual(self.hand(), [0, 1500, 0])
		comments, logged = self.trail()
		self.assertEqual((len(comments), logged), (1, 1))
		self.assertIn(self.d2, comments[0])
		self.assertNotIn(self.ci, comments[0])
		# and the same figure again changes nothing
		self.save([{"date": self.d2, "price": 1500}])
		self.assertEqual((len(self.trail()[0]), self.trail()[1]), (1, 1))

	def test_a_night_on_the_bill_sent_unchanged_is_skipped(self):
		from kamra.folio import open_folio, post_room_night
		res = self.res()
		open_folio(res)
		post_room_night(res, self.ci)
		self.save([{"date": self.ci, "price": 1000}, {"date": self.d3, "price": 1100}])
		self.assertEqual(self.hand(), [0, 0, 1100])

	def test_the_change_is_commented_and_logged(self):
		self.save([{"date": self.d2, "price": 1500}])
		comments = frappe.get_all("Comment", filters={
			"reference_doctype": "Reservation", "reference_name": self.name,
			"comment_type": "Comment"}, pluck="content")
		from kamra.localization import money_text
		change = f"{money_text(self.property, 1000)} → {money_text(self.property, 1500)}"
		self.assertTrue(any("Nightly prices changed" in c and self.d2 in c and change in c
		                    for c in comments), comments)
		self.assertTrue(frappe.db.exists("Agent Action Log", {
			"action_type": "set_night_prices", "reference_name": self.name}))

	def test_the_folio_bills_the_new_price(self):
		from kamra.folio import open_folio, post_room_night
		self.save([{"date": self.d2, "price": 1500}])
		res = self.res()
		open_folio(res)
		post_room_night(res, self.d2)
		amounts = frappe.get_all("Folio Charge", filters={
			"reservation": self.name, "charge_type": "Room"}, pluck="amount")
		self.assertEqual([round(float(a), 2) for a in amounts],
		                 [round(float(self.res().night_rates[1].rate), 2)])

	def test_a_save_whose_total_is_not_the_one_shown_is_refused(self):
		typed = [{"date": self.d2, "price": 1500}]
		shown = stay_prices_preview(self.name, typed)["new_amount"]
		self.assertAlmostEqual(shown, 3500, places=1)
		# someone else changes another night before this save arrives
		self.save([{"date": self.d3, "price": 1100}])
		with self.assertRaisesRegex(PriceConfirmationRequired, "not the") as refused:
			set_stay_prices(self.name, typed, expected_total=shown)
		self.assert_reads_in_property_currency(refused.exception, 3600, 3500)
		self.assertEqual(self.hand(), [0, 0, 1100])
		# the total the desk now sees is the one that saves
		self.save(typed)
		self.assertEqual(self.hand(), [0, 1500, 1100])

	def test_a_change_in_the_total_is_not_saved_without_the_total_that_was_shown(self):
		with self.assertRaises(PriceConfirmationRequired) as refused:
			set_stay_prices(self.name, [{"date": self.d2, "price": 1500}])
		self.assert_reads_in_property_currency(refused.exception, 3000, 3500)
		self.assertEqual(self.hand(), [0, 0, 0])
		self.assertEqual(self.res().auto_price, 1)

	def test_the_preview_shows_what_the_guest_has_paid_and_what_is_left(self):
		typed = [{"date": self.d2, "price": 1500}]
		pv = stay_prices_preview(self.name, typed)
		self.assertEqual(pv["paid"], 0)
		self.assertAlmostEqual(pv["new_balance"], 3500, places=1)
		# an advance taken with the booking
		frappe.db.set_value("Reservation", self.name, "advance_paid", 1000)
		pv = stay_prices_preview(self.name, typed)
		self.assertEqual(pv["paid"], 1000)
		self.assertAlmostEqual(pv["new_balance"], 2500, places=1)
		# the guest folio's payments count once there is a folio
		from kamra.folio import open_folio
		folio = open_folio(self.res())
		frappe.db.set_value("Folio", folio.name if hasattr(folio, "name") else folio,
		                    "payments_total", 800)
		pv = stay_prices_preview(self.name, typed)
		self.assertEqual(pv["paid"], 800)
		self.assertAlmostEqual(pv["new_balance"], 2700, places=1)
		# a price cut below what was paid leaves the guest in credit
		cut = [{"date": d, "price": 100} for d in (self.ci, self.d2, self.d3)]
		pv = stay_prices_preview(self.name, cut)
		self.assertAlmostEqual(pv["new_amount"], 300, places=1)
		self.assertAlmostEqual(pv["new_balance"], -500, places=1)
		self.assertEqual(self.hand(), [0, 0, 0])  # a preview writes nothing

	def test_an_in_house_guest_owes_what_the_folio_will_show_at_check_out(self):
		from kamra.folio import post_remaining_nights
		folio = self.check_in_with_a_folio(extra=200, paid=800)
		self.move_rate_card(2000)  # the nights to come keep their booked or typed price
		charges = frappe.db.count("Folio Charge", {"parent": folio})
		typed = [{"date": self.d2, "price": 1500}]
		pv = stay_prices_preview(self.name, typed)
		self.assertEqual(pv["paid"], 800)
		# 1000 billed + 1500 and 1000 still to bill + 200 of minibar - 800 paid
		self.assertAlmostEqual(pv["new_balance"], 2900, places=1)
		self.assertAlmostEqual(
			stay_prices_preview(self.name, [{"date": self.d2, "price": 1000}])["new_balance"], 2400, places=1)
		# the preview leaves the bill and the booking as they were
		self.assertEqual(frappe.db.count("Folio Charge", {"parent": folio}), charges)
		self.assertEqual(self.hand(), [0, 0, 0])
		# the figure shown is the one check-out bills after the save
		set_stay_prices(self.name, typed, expected_total=pv["new_amount"])
		post_remaining_nights(self.res())
		self.assertAlmostEqual(float(frappe.db.get_value("Folio", folio, "balance")),
		                       pv["new_balance"], places=1)

	def test_the_balance_counts_the_credit_the_save_posts_for_a_billed_night(self):
		from kamra.folio import post_remaining_nights
		from kamra.settings import write_kv
		write_kv(self.property, "charged_night_rate_change", "Credit the difference")
		folio = self.check_in_with_a_folio(extra=200, paid=800)
		self.move_rate_card(500)  # lower now: the billed night is credited the difference on save
		typed = [{"date": self.d2, "price": 1500}]
		pv = stay_prices_preview(self.name, typed)
		# 500 for the billed night after its credit + 1500 and 1000 to come + 200 - 800
		self.assertAlmostEqual(pv["new_balance"], 2400, places=1)
		set_stay_prices(self.name, typed, expected_total=pv["new_amount"])
		post_remaining_nights(self.res())
		self.assertAlmostEqual(float(frappe.db.get_value("Folio", folio, "balance")),
		                       pv["new_balance"], places=1)

	def test_nights_billed_to_the_company_are_not_the_guests_to_pay(self):
		corp = frappe.get_doc({"doctype": "Corporate Account",
			"company_name": "TEST NIGHTS CO " + frappe.generate_hash(length=8), "credit_allowed": 1,
			"billing_rules": [{"charge_type": "Room", "pay_by": "Company"}]}).insert(ignore_permissions=True)
		frappe.db.set_value("Reservation", self.name, "company", corp.name)
		self.check_in_with_a_folio(extra=200, paid=50)
		pv = stay_prices_preview(self.name, [{"date": self.d2, "price": 1500}])
		self.assertAlmostEqual(pv["new_balance"], 150, places=1)  # the minibar less what was paid

	# -- the nights are recorded in the property's currency -------------------

	def test_the_comment_reads_in_the_property_currency(self):
		self.save([{"date": self.d2, "price": 1500}])
		from kamra.localization import money_text
		comments = frappe.get_all("Comment", filters={
			"reference_doctype": "Reservation", "reference_name": self.name,
			"comment_type": "Comment"}, pluck="content")
		# UGX has no decimals: "1,500", never "1,500.00"
		self.assertTrue(any(money_text(self.property, 1500) in c and "1,500.00" not in c
		                    for c in comments), comments)

	# -- who may look, and where ----------------------------------------------

	def test_the_rate_card_is_quoted_only_for_someone_who_can_set_prices(self):
		import kamra.rates
		with mock.patch.object(kamra.rates, "rate_options", wraps=kamra.rates.rate_options) as quote:
			frappe.set_user(self.desk)  # nosemgrep: frappe-setuser -- the role under test
			out = stay_rates(self.name)
			self.assertEqual((out["can_set"], out["nights"]), (False, []))
			quote.assert_not_called()
			frappe.set_user(self.rates_only)  # nosemgrep: frappe-setuser -- the role under test
			self.assertEqual(len(stay_rates(self.name)["nights"]), 3)
			quote.assert_called_once()

	def test_a_user_scoped_to_another_property_is_refused(self):
		other = frappe.get_doc({"doctype": "Property",
			"property_name": "TEST OTHER NIGHTS " + frappe.generate_hash(length=8),
			"country": "Uganda", "currency": "UGX",
			"rates_include_tax": 1}).insert(ignore_permissions=True).name
		other_type = frappe.get_doc({"doctype": "Room Type", "property": other,
			"room_type_code": "STD", "room_type_name": "Standard", "base_price": 1000,
			"adults_capacity": 2}).insert(ignore_permissions=True).name
		frappe.get_doc({"doctype": "Room", "property": other, "room_type": other_type,
			"room_number": "201"}).insert(ignore_permissions=True)
		theirs = create_booking(other, other_type, self.ci, self.co, "Other Property Guest")["reservation"]
		scoped = self._staff(SCOPED, "Revenue Manager")
		frappe.get_doc({"doctype": "User Permission", "user": scoped, "allow": "Property",
			"for_value": other}).insert(ignore_permissions=True)
		frappe.clear_cache(user=scoped)
		typed = [{"date": self.ci, "price": 1200}]
		frappe.set_user(scoped)  # nosemgrep: frappe-setuser -- the scoped user under test
		# the same person works on the property they are scoped to ...
		self.assertTrue(stay_rates(theirs)["can_set"])
		self.assertTrue(stay_prices_preview(theirs, typed)["needs_confirmation"])
		# ... and is refused on this one, on all three endpoints
		with self.assertRaises(frappe.PermissionError):
			stay_rates(self.name)
		with self.assertRaises(frappe.PermissionError):
			stay_prices_preview(self.name, typed)
		with self.assertRaises(frappe.PermissionError):
			set_stay_prices(self.name, typed, expected_total=3200)
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- read back the result
		self.assertEqual(self.hand(), [0, 0, 0])

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
			set_stay_prices(self.name, [{"date": self.ci, "price": 1200}], expected_total=1)
		self.save([{"date": self.d3, "price": 1100}])
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
			set_stay_prices(self.name, [{"date": self.ci, "price": 1200}], expected_total=1)

	def test_a_stay_priced_as_a_whole_is_closed(self):
		other = create_booking(self.property, self.room_type, self.ci, self.d3, "Whole Total",
		                       booked_via="Booking.com", ota_total=2600)["reservation"]
		out = stay_rates(other)
		self.assertFalse(out["editable"])
		self.assertIn("priced as a whole", out["why_not"])
		with self.assertRaises(frappe.ValidationError):
			set_stay_prices(other, [{"date": self.ci, "price": 1200}], expected_total=1)

	def test_a_checked_out_booking_is_closed(self):
		frappe.db.set_value("Reservation", self.name, "status", "Checked Out")
		self.assertFalse(stay_rates(self.name)["editable"])
		with self.assertRaises(frappe.ValidationError):
			set_stay_prices(self.name, [{"date": self.ci, "price": 1200}], expected_total=1)

	def test_bad_requests_are_refused(self):
		for why, payload in {
			"nothing": [],
			"a night outside the stay": [{"date": self.co, "price": 1200}],
			"zero": [{"date": self.ci, "price": 0}],
			"three decimals": [{"date": self.ci, "price": 1200.005}],
		}.items():
			with self.subTest(why):
				with self.assertRaises(frappe.ValidationError):
					set_stay_prices(self.name, payload, expected_total=1)
		self.assertEqual(self.res().auto_price, 1)
