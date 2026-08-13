"""Banquet management: the rules a function is priced, sold and settled by.

The eval harness proves the whole app hangs together; these are the unit
tests for this module alone - one behaviour per test, named for the rule
it defends, so a failure says what broke rather than that something did.
"""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from kamra import banquet as bq
from kamra.tests.fixtures import PROPERTY, build, enquiry


class BanquetTestCase(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.local.lang = frappe.local.lang or "en"
		self.f = build()

	def tearDown(self):
		frappe.set_user("Administrator")

	def sheet(self, fn):
		return frappe.get_doc("Venue Booking", fn)


# ══ selling the hall ═════════════════════════════════════════════════════

class TestEnquiry(BanquetTestCase):
	def test_enquiry_opens_with_the_halls_rack_rental_on_it(self):
		fn = enquiry(self.f)
		doc = self.sheet(fn)
		self.assertEqual(doc.status, "Enquiry")
		rental = next(r for r in doc.items if r.item_type == "Venue Rental")
		self.assertEqual(rental.rate, 50000)
		self.assertEqual(doc.venue_rental, 50000)

	def test_an_enquiry_is_diarised_so_it_cannot_go_quiet(self):
		fn = enquiry(self.f, follow_up_days=3)
		self.assertEqual(self.sheet(fn).follow_up_date,
		                 frappe.utils.getdate(add_days(nowdate(), 3)))

	def test_a_customer_needs_a_name(self):
		with self.assertRaises(frappe.ValidationError):
			enquiry(self.f, customer_name="  ")


class TestSessions(BanquetTestCase):
	def test_a_session_sets_the_clock(self):
		fn = enquiry(self.f)
		bq.update_function(fn, {"session": "Morning"})
		doc = self.sheet(fn)
		self.assertEqual(str(doc.start_time), "7:00:00")
		self.assertEqual(doc.billable_hours, 5)

	def test_explicit_hours_are_kept_as_custom_hours(self):
		# regression: a Select with no default silently took its FIRST
		# option, rewriting 19:00-23:00 into a morning function
		doc = self.sheet(enquiry(self.f))
		self.assertEqual(doc.session, "Custom Hours")
		self.assertEqual(str(doc.start_time), "19:00:00")

	def test_custom_hours_must_state_its_hours(self):
		doc = self.sheet(enquiry(self.f))
		doc.session = "Custom Hours"
		doc.start_time = doc.end_time = None
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)

	def test_a_reception_running_past_midnight_is_five_hours_not_minus_19(self):
		doc = self.sheet(enquiry(self.f, start_time="20:00", end_time="01:00"))
		self.assertEqual(doc.billable_hours, 5)


class TestHallConflicts(BanquetTestCase):
	def test_a_confirmed_function_owns_the_hall(self):
		day = add_days(nowdate(), 200)
		bq.set_status(enquiry(self.f, event_date=day), "Confirmed")
		clash = enquiry(self.f, event_date=day, customer_name="Second")
		with self.assertRaises(frappe.ValidationError):
			bq.set_status(clash, "Confirmed")

	def test_a_tentative_hold_can_be_sold_over(self):
		day = add_days(nowdate(), 201)
		bq.set_status(enquiry(self.f, event_date=day), "Tentative")
		other = enquiry(self.f, event_date=day, customer_name="Real business")
		bq.set_status(other, "Confirmed")
		self.assertEqual(self.sheet(other).status, "Confirmed")

	def test_a_hall_takes_a_morning_and_an_evening_function(self):
		day = add_days(nowdate(), 202)
		bq.set_status(enquiry(self.f, event_date=day), "Confirmed")
		morning = enquiry(self.f, event_date=day, customer_name="Conference",
		                  start_time="09:00", end_time="13:00")
		bq.set_status(morning, "Confirmed")
		self.assertEqual(self.sheet(morning).status, "Confirmed")

	def test_availability_reports_the_clash_it_refused(self):
		day = add_days(nowdate(), 203)
		bq.set_status(enquiry(self.f, event_date=day), "Confirmed")
		out = bq.venue_availability(PROPERTY, day, start_time="19:00",
		                            end_time="23:00")
		hall = next(v for v in out["venues"] if v["name"] == self.f["hall"])
		self.assertFalse(hall["available"])
		self.assertTrue(hall["conflicts"])


class TestPipeline(BanquetTestCase):
	def test_a_function_cannot_skip_the_work(self):
		fn = enquiry(self.f)
		with self.assertRaises(frappe.ValidationError):
			bq.set_status(fn, "Completed")

	def test_losing_business_requires_saying_why(self):
		fn = enquiry(self.f)
		with self.assertRaises(frappe.ValidationError):
			bq.set_status(fn, "Lost")
		bq.set_status(fn, "Lost", reason="Went elsewhere on price")
		self.assertTrue(self.sheet(fn).lost_reason)


# ══ what it costs the customer ═══════════════════════════════════════════

class TestPricing(BanquetTestCase):
	def test_menus_bill_the_guarantee_not_the_hope(self):
		fn = enquiry(self.f)
		bq.update_function(fn, {"pax_guaranteed": 180})
		bq.add_menu(fn, self.f["menu"])
		line = next(r for r in self.sheet(fn).items if r.item_type == "Menu")
		self.assertEqual(line.qty, 180)

	def test_more_people_than_guaranteed_are_billed_too(self):
		fn = enquiry(self.f)
		bq.update_function(fn, {"pax_guaranteed": 180, "pax_actual": 210})
		self.assertEqual(self.sheet(fn).billable_pax, 210)

	def test_a_package_floor_bills_its_minimum(self):
		fn = enquiry(self.f, attendees=40)
		bq.update_function(fn, {"pax_guaranteed": 40})
		bq.add_menu(fn, self.f["menu"])
		line = next(r for r in self.sheet(fn).items if r.item_type == "Menu")
		self.assertEqual(line.qty, 100)          # the menu's min_pax

	def test_a_complimentary_line_is_free_but_never_disappears(self):
		fn = enquiry(self.f)
		bq.add_service(fn, self.f["podium"])     # free by catalogue default
		doc = self.sheet(fn)
		line = next(r for r in doc.items if r.service_item == self.f["podium"])
		self.assertFalse(line.chargeable)
		self.assertEqual(line.amount, 0)
		self.assertEqual(doc.non_chargeable_value, 2000)
		pack = bq.banquet_document(fn, "pack_list")["pack"]
		names = [i["item_name"] for g in pack["groups"] for i in g["items"]]
		self.assertIn("Test Podium", names)

	def test_a_discount_spreads_pro_rata_and_each_line_keeps_its_own_tax(self):
		fn = enquiry(self.f)
		bq.update_function(fn, {"pax_guaranteed": 100})
		bq.add_menu(fn, self.f["menu"])          # 120,000 food @ 5%
		bq.add_service(fn, self.f["led"])        # 40,000 AV @ 18%
		doc = self.sheet(fn)                     # + 50,000 hall @ 18%
		self.assertEqual(doc.subtotal, 210000)

		bq.negotiate(fn, discount_amount=21000)  # 10% off the whole quote
		doc.reload()
		self.assertEqual(doc.taxable_amount, 189000)
		food = next(r for r in doc.items if r.item_type == "Menu")
		self.assertEqual(food.gst_rate, 5)
		self.assertAlmostEqual(food.net_amount, 108000, places=2)
		self.assertAlmostEqual(
			doc.tax_amount, 45000 * .18 + 108000 * .05 + 36000 * .18, places=2)

	def test_a_discount_bigger_than_the_quote_is_a_mistake(self):
		fn = enquiry(self.f)
		bq.add_menu(fn, self.f["menu"])
		with self.assertRaises(frappe.ValidationError):
			bq.negotiate(fn, discount_amount=9_000_000)

	def test_service_charge_rides_the_food_not_the_hall(self):
		fn = enquiry(self.f)
		bq.update_function(fn, {"pax_guaranteed": 100})
		bq.add_menu(fn, self.f["menu"])          # 120,000
		bq.add_service(fn, self.f["led"])        # 40,000 - not chargeable base
		bq.update_function(fn, {"service_charge_percent": 10})
		self.assertEqual(self.sheet(fn).service_charge, 12000)

	def test_every_price_move_is_recorded(self):
		fn = enquiry(self.f)
		bq.add_menu(fn, self.f["menu"])
		bq.generate_quote(fn)
		moved = bq.negotiate(fn, venue_rental=40000, note="Matched a rival")
		self.assertLess(moved["now"], moved["was"])
		doc = self.sheet(fn)
		self.assertEqual(doc.venue_rental, 40000)
		self.assertEqual(doc.venue_rental_list, 50000)
		self.assertTrue(doc.revisions)


# ══ what it costs the hotel ══════════════════════════════════════════════

class TestCostAndMargin(BanquetTestCase):
	def test_a_dish_costs_what_its_recipe_costs(self):
		out = bq.save_dish(PROPERTY, "Test Dal", course_type="Main Course",
		                   recipe=[{"ingredient": self.f["onion"], "qty": 0.5}])
		self.assertEqual(out["cost_per_portion"], 20)   # 0.5kg x 40

	def test_a_price_rise_re_costs_every_dish(self):
		frappe.db.set_value("Ingredient", self.f["onion"], "cost_per_unit", 60)
		bq.recost_dishes(PROPERTY)
		self.assertEqual(frappe.db.get_value(
			"Banquet Dish", self.f["veg"], "cost_per_portion"), 12)   # 0.2 x 60

	def test_a_service_carries_its_buy_price_onto_the_line(self):
		# regression: the sell price was copied and the cost forgotten, so
		# every hired LED wall read as 100% margin
		fn = enquiry(self.f)
		bq.add_service(fn, self.f["led"])
		line = next(r for r in self.sheet(fn).items
		            if r.service_item == self.f["led"])
		self.assertEqual(line.cost_rate, 25000)
		self.assertEqual(line.cost_amount, 25000)

	def test_a_menu_costs_its_default_dishes_before_anyone_chooses(self):
		fn = enquiry(self.f)
		bq.update_function(fn, {"pax_guaranteed": 100})
		bq.add_menu(fn, self.f["menu"])
		self.assertEqual(self.sheet(fn).food_cost, 800)   # 8/pax x 100

	def test_margin_is_revenue_less_what_it_actually_cost(self):
		fn = enquiry(self.f)
		bq.update_function(fn, {"pax_guaranteed": 100})
		bq.add_menu(fn, self.f["menu"])
		bq.add_service(fn, self.f["led"])
		doc = self.sheet(fn)
		self.assertEqual(doc.food_cost, 800)       # 8/pax x 100 pax
		# the LED wall's buy price, plus what opening the hall costs
		self.assertEqual(doc.service_cost, 30000)
		self.assertEqual(doc.total_cost, 30800)
		self.assertAlmostEqual(doc.gross_margin,
		                       doc.taxable_amount - doc.net_cost, places=2)

	def test_a_five_percent_supply_cannot_claim_the_input_credit(self):
		fn = enquiry(self.f)
		bq.update_function(fn, {"pax_guaranteed": 100})
		bq.add_menu(fn, self.f["menu"])          # billed at 5%
		doc = self.sheet(fn)
		self.assertFalse(doc.itc_eligible)
		self.assertEqual(doc.net_cost, doc.total_cost)

	def test_the_same_food_at_eighteen_percent_can(self):
		fn = enquiry(self.f)
		bq.update_function(fn, {"pax_guaranteed": 100})
		bq.add_menu(fn, self.f["menu"])
		doc = self.sheet(fn)
		for r in doc.items:
			if r.item_type == "Menu":
				r.gst_rate = 18
		doc.save(ignore_permissions=True)
		self.assertTrue(doc.itc_eligible)
		self.assertLess(doc.net_cost, doc.total_cost)


class TestMenuComposition(BanquetTestCase):
	def test_a_course_offers_its_dishes(self):
		fn = enquiry(self.f)
		bq.add_menu(fn, self.f["menu"])
		courses = bq.menu_choices(fn, self.f["menu"])["courses"]
		self.assertEqual(courses[0]["choice_of"], 1)
		self.assertEqual(len(courses[0]["options"]), 2)

	def test_choosing_re_costs_the_line_and_prices_the_upgrade(self):
		fn = enquiry(self.f)
		bq.update_function(fn, {"pax_guaranteed": 100})
		bq.add_menu(fn, self.f["menu"])
		out = bq.compose_menu(fn, self.f["menu"], [{
			"course": "Starters", "dish": self.f["nonveg"],
			"supplement_per_pax": 150, "note": "less spicy"}])
		self.assertEqual(out["cost_per_pax"], 30)
		self.assertEqual(out["supplement_per_pax"], 150)

		doc = self.sheet(fn)
		# an upgrade is a price change and belongs on the quote as one
		upgrade = next(r for r in doc.items
		               if (r.notes or "").startswith("supplement:"))
		self.assertEqual(upgrade.rate, 150)
		self.assertEqual(upgrade.qty, 100)

	def test_the_card_prints_what_they_chose_not_the_catalogue(self):
		fn = enquiry(self.f)
		bq.update_function(fn, {"pax_guaranteed": 100})
		bq.add_menu(fn, self.f["menu"])
		bq.compose_menu(fn, self.f["menu"],
		                [{"course": "Starters", "dish": self.f["nonveg"]}])
		served = bq.menu_card(fn)["menus"][0]
		self.assertTrue(served["chosen"])
		self.assertIn("Test Tikka", served["courses"][0]["dishes"])


class TestKitchen(BanquetTestCase):
	def test_the_indent_explodes_the_picks_into_ingredients(self):
		fn = enquiry(self.f)
		bq.update_function(fn, {"pax_guaranteed": 200})
		bq.add_menu(fn, self.f["menu"])
		bq.compose_menu(fn, self.f["menu"],
		                [{"course": "Starters", "dish": self.f["veg"]}])
		ind = bq.kitchen_indent(fn)
		onion = next(r for r in ind["ingredients"]
		             if r["ingredient"] == self.f["onion"])
		self.assertEqual(onion["required"], 40)   # 0.2kg x 1 portion x 200
		self.assertEqual(onion["cost"], 1600)

	def test_the_chefs_get_it_split_by_section(self):
		fn = enquiry(self.f)
		bq.update_function(fn, {"pax_guaranteed": 200})
		bq.add_menu(fn, self.f["menu"])
		bq.compose_menu(fn, self.f["menu"],
		                [{"course": "Starters", "dish": self.f["veg"]}])
		tandoor = next(k for k in bq.kitchen_indent(fn)["by_kitchen"]
		               if k["kitchen"] == "Tandoor")
		self.assertEqual(tandoor["dishes"][0]["portions"], 200)

	def test_no_menu_chosen_means_nothing_to_tell_the_kitchen(self):
		fn = enquiry(self.f)
		bq.update_function(fn, {"pax_guaranteed": 100})
		bq.add_menu(fn, self.f["menu"])
		with self.assertRaises(frappe.ValidationError):
			bq.kitchen_indent(fn)


# ══ the night, and the money ═════════════════════════════════════════════

class TestTheNight(BanquetTestCase):
	def _sold(self):
		fn = enquiry(self.f)
		bq.update_function(fn, {"pax_guaranteed": 100})
		bq.add_menu(fn, self.f["menu"])
		bq.set_status(fn, "Confirmed")
		return fn

	def test_the_bill_follows_what_was_served(self):
		fn = self._sold()
		quoted = self.sheet(fn).grand_total
		line = next(r for r in self.sheet(fn).items if r.item_type == "Menu")
		bq.record_consumption(fn, {line.name: 118}, pax_actual=118)
		doc = self.sheet(fn)
		self.assertGreater(doc.grand_total, quoted)
		served = next(r for r in doc.items if r.name == line.name)
		self.assertEqual(served.amount, 118 * 1200)
		self.assertEqual(served.cost_amount, 118 * 8)

	def test_the_bar_running_on_bills_on_top(self):
		fn = self._sold()
		bq.add_supplementary(fn, "Extra bar round", qty=2, rate=6000,
		                     item_type="Alcohol", cost_rate=3500,
		                     is_alcohol=1)
		econ = bq.function_economics(fn)
		self.assertGreater(econ["revenue"]["supplementary"], 0)
		self.assertTrue(any(x["is_supplementary"] for x in econ["lines"]))

	def test_a_deposit_is_held_money_not_payment(self):
		fn = self._sold()
		total = self.sheet(fn).grand_total
		bq.record_receipt(fn, 25000, kind="Security Deposit", mode="Cash")
		doc = self.sheet(fn)
		self.assertEqual(doc.advance_received, 0)
		self.assertEqual(doc.deposit_held, 25000)
		self.assertEqual(doc.balance_due, total)

	def test_an_advance_does_pay_the_bill_down(self):
		fn = self._sold()
		total = self.sheet(fn).grand_total
		bq.record_receipt(fn, 50000, kind="Advance", mode="UPI")
		doc = self.sheet(fn)
		self.assertEqual(doc.advance_received, 50000)
		self.assertEqual(doc.balance_due, total - 50000)

	def test_terms_stated_as_a_percentage_follow_the_quote(self):
		fn = self._sold()
		bq.default_payment_terms(fn, advance_percent=25, interim_percent=50)
		doc = self.sheet(fn)
		self.assertEqual(len(doc.payment_terms), 3)
		self.assertAlmostEqual(doc.payment_terms[0].amount,
		                       doc.grand_total * .25, places=2)


class TestCloseOut(BanquetTestCase):
	def _held(self, deposit=20000):
		fn = enquiry(self.f)
		bq.update_function(fn, {"pax_guaranteed": 100})
		bq.add_menu(fn, self.f["menu"])
		bq.set_status(fn, "Confirmed")
		bq.record_receipt(fn, deposit, kind="Security Deposit", mode="Cash")
		return fn

	def test_a_deduction_needs_a_reason(self):
		with self.assertRaises(frappe.ValidationError):
			bq.close_out(self._held(), damage_amount=3000)

	def test_you_cannot_keep_more_than_you_hold(self):
		with self.assertRaises(frappe.ValidationError):
			bq.close_out(self._held(), damage_amount=99000,
			             damage_note="everything")

	def test_damage_comes_off_the_deposit_and_the_rest_goes_back(self):
		fn = self._held()
		out = bq.close_out(fn, damage_amount=3000, damage_note="Two chairs",
		                   pax_actual=118)
		self.assertEqual(out["refunded"], 17000)
		doc = self.sheet(fn)
		self.assertEqual(doc.status, "Completed")
		self.assertEqual(doc.deposit_held, 0)
		self.assertEqual(doc.pax_actual, 118)

	def test_the_damage_kept_becomes_revenue(self):
		fn = self._held()
		bq.close_out(fn, damage_amount=3000, damage_note="Two chairs")
		recovery = next(r for r in self.sheet(fn).items
		                if r.notes == "damage-recovery")
		self.assertEqual(recovery.rate, 3000)
		self.assertTrue(recovery.chargeable)

	def test_closing_out_twice_would_refund_twice(self):
		fn = self._held()
		bq.close_out(fn)
		with self.assertRaises(frappe.ValidationError):
			bq.close_out(fn)


class TestGreenRoom(BanquetTestCase):
	def _room(self):
		rt = frappe.db.get_value("Room Type", {"property": PROPERTY}) or \
			frappe.get_doc({
				"doctype": "Room Type", "property": PROPERTY,
				"room_type_code": "TST", "room_type_name": "Test Room",
				"base_price": 4000, "base_occupancy": 2,
				"adults_capacity": 3, "children_capacity": 2,
				"tax_percent": 5,
			}).insert(ignore_permissions=True).name
		return frappe.db.get_value("Room", {"property": PROPERTY}) or \
			frappe.get_doc({"doctype": "Room", "property": PROPERTY,
			                "room_number": "T101",
			                "room_type": rt}).insert(
				ignore_permissions=True).name

	def test_holding_a_green_room_takes_it_out_of_sale(self):
		fn = enquiry(self.f)
		bq.assign_green_room(fn, room=self._room(), complimentary=1)
		doc = self.sheet(fn)
		self.assertTrue(doc.green_room_block)
		block = frappe.get_doc("Room Block", doc.green_room_block)
		self.assertEqual(block.block_status, "Active")
		# and it's on the sheet without being on the bill
		line = next(r for r in doc.items if r.item_type == "Accommodation")
		self.assertFalse(line.chargeable)

	def test_losing_the_function_gives_the_room_back(self):
		fn = enquiry(self.f)
		bq.assign_green_room(fn, room=self._room(), complimentary=1)
		block = self.sheet(fn).green_room_block
		bq.set_status(fn, "Lost", reason="Date moved")
		self.assertEqual(frappe.db.get_value("Room Block", block,
		                                     "block_status"), "Released")


# ══ the paper ════════════════════════════════════════════════════════════

class TestDocuments(BanquetTestCase):
	def _sold(self):
		fn = enquiry(self.f)
		bq.update_function(fn, {"pax_guaranteed": 150})
		bq.add_menu(fn, self.f["menu"])
		bq.add_service(fn, self.f["led"])
		bq.set_status(fn, "Confirmed")
		return fn

	def test_every_document_renders(self):
		fn = self._sold()
		for kind in ("quote", "contract", "beo", "pack_list", "invoice"):
			with self.subTest(kind=kind):
				doc = bq.banquet_document(fn, kind)
				self.assertTrue(doc["header"]["title"])
				self.assertTrue(doc["property"])
		self.assertTrue(bq.menu_card(fn)["header"]["title"])

	def test_an_unsold_function_gets_no_event_order(self):
		fn = enquiry(self.f)
		bq.add_menu(fn, self.f["menu"])
		with self.assertRaises(frappe.ValidationError):
			bq.generate_beo(fn)

	def test_the_event_order_numbers_itself_and_prints_the_menu(self):
		beo = bq.generate_beo(self._sold())
		self.assertTrue(beo["header"]["beo_number"])
		self.assertTrue(beo["menus"])
		self.assertEqual(beo["event"]["billable_pax"], 150)

	def test_a_quote_is_versioned(self):
		fn = self._sold()
		self.assertEqual(bq.generate_quote(fn)["header"]["version"], 1)
		self.assertEqual(bq.generate_quote(fn)["header"]["version"], 2)

	def test_a_receipt_prints_with_the_amount_in_words(self):
		fn = self._sold()
		bq.record_receipt(fn, 25000, kind="Advance", mode="UPI")
		row = self.sheet(fn).receipts[0]
		doc = bq.receipt_document(fn, row.name)
		self.assertEqual(doc["receipt"]["amount"], 25000)
		self.assertIn("Twenty Five Thousand", doc["header"]["amount_in_words"])


# ══ the customer, and the books ══════════════════════════════════════════

class TestCustomer(BanquetTestCase):
	def test_the_same_number_is_the_same_client(self):
		a = enquiry(self.f, customer_phone="+91 90000 55555")
		b = enquiry(self.f, customer_phone="+91 90000 55555",
		            day_offset=90)
		bq.link_customer(a)
		bq.link_customer(b)
		self.assertEqual(self.sheet(a).customer, self.sheet(b).customer)

	def test_a_profile_carries_the_history(self):
		fn = enquiry(self.f, customer_phone="+91 90000 66666")
		bq.link_customer(fn)
		bq.update_function(fn, {"pax_guaranteed": 100})
		bq.add_menu(fn, self.f["menu"])
		bq.set_status(fn, "Confirmed")
		p = bq.customer_profile(PROPERTY, phone="+91 90000 66666")
		self.assertTrue(p["found"])
		self.assertGreaterEqual(p["stats"]["won"], 1)
		self.assertGreater(p["stats"]["lifetime_value"], 0)

	def test_an_unknown_number_is_not_a_crash(self):
		self.assertFalse(
			bq.customer_profile(PROPERTY, phone="+91 00000 00000")["found"])


class TestRegisters(BanquetTestCase):
	def setUp(self):
		super().setUp()
		self.fn = enquiry(self.f)
		bq.update_function(self.fn, {"pax_guaranteed": 100})
		bq.add_menu(self.fn, self.f["menu"])
		bq.set_status(self.fn, "Confirmed")
		bq.record_receipt(self.fn, 50000, kind="Advance", mode="UPI")
		self.window = (add_days(nowdate(), -1), add_days(nowdate(), 400))

	def test_the_function_register_totals_its_own_rows(self):
		reg = bq.banquet_register(PROPERTY, "functions", *self.window)
		self.assertEqual(reg["totals"]["value"],
		                 sum(float(r["grand_total"] or 0) for r in reg["rows"]))

	def test_the_cash_book_reads_by_payment_and_by_mode(self):
		cash = bq.banquet_register(PROPERTY, "receipts", *self.window)
		self.assertTrue(cash["rows"])
		self.assertAlmostEqual(cash["totals"]["value"],
		                       sum(x["amount"] for x in cash["by_mode"]),
		                       places=2)

	def test_lost_business_is_not_sales(self):
		bq.set_status(enquiry(self.f, day_offset=95), "Lost", reason="Price")
		sales = bq.banquet_register(PROPERTY, "sales", *self.window)
		self.assertTrue(all(r["status"] not in ("Cancelled", "Lost")
		                    for r in sales["rows"]))

	def test_an_unknown_register_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			bq.banquet_register(PROPERTY, "nonsense")


class TestMonthGrid(BanquetTestCase):
	def test_a_morning_function_does_not_block_the_evening(self):
		day = add_days(nowdate(), 210)
		fn = enquiry(self.f, event_date=day)
		bq.update_function(fn, {"session": "Morning"})
		bq.set_status(fn, "Confirmed")
		grid = bq.month_availability(PROPERTY, str(day)[:7])
		rows = {r["session"]: r for r in grid["rows"]
		        if r["venue"] == self.f["hall"]}
		self.assertIn(str(day), rows["Morning"]["by_date"])
		self.assertNotIn(str(day), rows["Evening"]["by_date"])


# ══ who may do what ══════════════════════════════════════════════════════

class TestAccess(BanquetTestCase):
	"""Every endpoint is gated. These assert the gate is where we think it
	is - a read-only role must not be able to move a price, and a role that
	should read must not be locked out."""

	def test_sales_can_run_the_whole_flow(self):
		frappe.set_user("banquet.sales@test.local")
		fn = enquiry(self.f)
		bq.add_menu(fn, self.f["menu"])
		bq.negotiate(fn, discount_amount=1000)
		bq.set_status(fn, "Tentative")
		self.assertEqual(self.sheet(fn).status, "Tentative")

	def test_finance_may_read_but_not_re_price(self):
		fn = enquiry(self.f)
		frappe.set_user("banquet.finance@test.local")
		bq.function_sheet(fn)                    # allowed
		bq.banquet_register(PROPERTY, "receipts")
		with self.assertRaises(frappe.PermissionError):
			bq.negotiate(fn, discount_amount=1000)

	def test_housekeeping_sees_the_indent_but_not_the_pipeline(self):
		fn = enquiry(self.f)
		bq.update_function(fn, {"pax_guaranteed": 100})
		bq.add_menu(fn, self.f["menu"])
		bq.compose_menu(fn, self.f["menu"],
		                [{"course": "Starters", "dish": self.f["veg"]}])
		frappe.set_user("banquet.hk@test.local")
		# the floor needs what to pull and what to carry...
		self.assertTrue(bq.kitchen_indent(fn)["ingredients"])
		self.assertTrue(bq.banquet_document(fn, "pack_list"))
		# ...but the funnel, the conversion rate and the cash book are not
		# the floor's business
		with self.assertRaises(frappe.PermissionError):
			bq.banquet_pipeline(PROPERTY)
		with self.assertRaises(frappe.PermissionError):
			bq.banquet_register(PROPERTY, "receipts")

	def test_only_the_catalogue_roles_change_what_things_cost(self):
		frappe.set_user("banquet.hk@test.local")
		with self.assertRaises(frappe.PermissionError):
			bq.save_dish(PROPERTY, "Sneaky dish")
		frappe.set_user("banquet.revenue@test.local")
		self.assertTrue(bq.save_dish(PROPERTY, "Allowed dish")["name"])


# ══ the hall itself ══════════════════════════════════════════════════════

class TestFloorPlan(BanquetTestCase):
	"""A ballroom that splits into A and B is three sellable spaces sharing
	two physical pieces. Selling half must take the whole room off the
	market - without this a hall gets sold twice and nobody finds out
	until the trucks arrive."""

	def test_selling_a_half_takes_the_whole_room(self):
		day = add_days(nowdate(), 300)
		bq.set_status(enquiry(self.f, venue=self.f["hall_a"],
		                      event_date=day), "Confirmed")
		whole = enquiry(self.f, venue=self.f["hall_ab"], event_date=day,
		                customer_name="Big wedding")
		with self.assertRaises(frappe.ValidationError):
			bq.set_status(whole, "Confirmed")

	def test_selling_the_whole_room_takes_both_halves(self):
		day = add_days(nowdate(), 301)
		bq.set_status(enquiry(self.f, venue=self.f["hall_ab"],
		                      event_date=day), "Confirmed")
		half = enquiry(self.f, venue=self.f["hall_b"], event_date=day,
		               customer_name="Small party")
		with self.assertRaises(frappe.ValidationError):
			bq.set_status(half, "Confirmed")

	def test_the_two_halves_sell_independently(self):
		day = add_days(nowdate(), 302)
		bq.set_status(enquiry(self.f, venue=self.f["hall_a"],
		                      event_date=day), "Confirmed")
		other = enquiry(self.f, venue=self.f["hall_b"], event_date=day,
		                customer_name="Other half")
		bq.set_status(other, "Confirmed")
		self.assertEqual(self.sheet(other).status, "Confirmed")

	def test_a_hall_with_no_sections_only_clashes_with_itself(self):
		day = add_days(nowdate(), 303)
		bq.set_status(enquiry(self.f, event_date=day), "Confirmed")
		elsewhere = enquiry(self.f, venue=self.f["small"], event_date=day,
		                    customer_name="Boardroom")
		bq.set_status(elsewhere, "Confirmed")
		self.assertEqual(self.sheet(elsewhere).status, "Confirmed")

	def test_the_hall_reports_what_it_shares_a_floor_with(self):
		out = bq.venue_detail(self.f["hall_ab"])
		self.assertCountEqual(out["shares_floor_with"],
		                      [self.f["hall_a"], self.f["hall_b"]])
		self.assertEqual(len(out["sections"]), 2)


class TestHallDeal(BanquetTestCase):
	def test_hall_and_food_bills_both(self):
		fn = enquiry(self.f)
		bq.update_function(fn, {"pax_guaranteed": 100})
		bq.add_menu(fn, self.f["menu"])
		doc = self.sheet(fn)
		self.assertFalse(doc.hall_waived)
		rental = next(r for r in doc.items if r.item_type == "Venue Rental")
		self.assertTrue(rental.chargeable)

	def test_the_hall_is_free_once_the_food_bill_clears_the_number(self):
		fn = enquiry(self.f)
		bq.update_function(fn, {
			"pax_guaranteed": 100,
			"hall_deal": "Hall free over a minimum spend",
			"minimum_fnb_spend": 100000})
		bq.add_menu(fn, self.f["menu"])          # 100 x 1200 = 120,000
		doc = self.sheet(fn)
		self.assertEqual(doc.fnb_spend, 120000)
		self.assertTrue(doc.hall_waived)
		rental = next(r for r in doc.items if r.item_type == "Venue Rental")
		self.assertFalse(rental.chargeable)
		self.assertEqual(rental.amount, 0)

	def test_the_rental_comes_back_when_the_food_bill_drops(self):
		fn = enquiry(self.f)
		bq.update_function(fn, {
			"pax_guaranteed": 100,
			"hall_deal": "Hall free over a minimum spend",
			"minimum_fnb_spend": 100000})
		bq.add_menu(fn, self.f["menu"])
		self.assertTrue(self.sheet(fn).hall_waived)
		# the guest count falls and the deal no longer holds
		bq.update_function(fn, {"minimum_fnb_spend": 500000})
		doc = self.sheet(fn)
		self.assertFalse(doc.hall_waived)
		rental = next(r for r in doc.items if r.item_type == "Venue Rental")
		self.assertTrue(rental.chargeable)

	def test_a_waived_hall_still_costs_the_hotel_to_open(self):
		fn = enquiry(self.f, venue=self.f["hall_ab"])
		bq.update_function(fn, {"pax_guaranteed": 100,
		                        "hall_deal": "Food only"})
		doc = self.sheet(fn)
		self.assertTrue(doc.hall_waived)
		rental = next(r for r in doc.items if r.item_type == "Venue Rental")
		self.assertEqual(rental.cost_rate, 6000)   # the venue's running cost


class TestAmenities(BanquetTestCase):
	def test_included_amenities_are_not_billed(self):
		out = bq.venue_detail(self.f["hall_ab"])
		included = [a["amenity"] for a in out["amenities"] if a["included"]]
		self.assertIn("Air conditioning", included)
		self.assertIn("Generator backup", included)

	def test_chargeable_extras_can_be_priced_onto_the_quote(self):
		fn = enquiry(self.f, venue=self.f["hall_ab"])
		out = bq.offer_amenities(fn)
		self.assertEqual(out["added"], 1)          # only the valet parking
		line = next(r for r in self.sheet(fn).items
		            if r.notes == "hall-amenity")
		self.assertEqual(line.rate, 12000)

	def test_or_parked_as_open_items_while_it_is_undecided(self):
		fn = enquiry(self.f, venue=self.f["hall_ab"])
		bq.offer_amenities(fn, as_open_items=1)
		doc = self.sheet(fn)
		self.assertTrue(any(o.title == "Valet parking" for o in doc.open_items))
		self.assertFalse(any(r.notes == "hall-amenity" for r in doc.items))


class TestQuoteAdvisor(BanquetTestCase):
	"""Margin after the event is an autopsy. This is the number that
	changes a decision, while the discount is still being typed."""

	def _priced(self):
		fn = enquiry(self.f)
		bq.update_function(fn, {"pax_guaranteed": 100})
		bq.add_menu(fn, self.f["menu"])          # 120,000 sell / 800 cost
		bq.add_service(fn, self.f["led"])        # 40,000 sell / 25,000 cost
		return fn

	def test_it_says_what_is_left_at_the_current_price(self):
		out = bq.quote_advisor(self._priced())
		self.assertEqual(out["revenue"], 210000)
		# 800 food + 25,000 LED wall + 5,000 to open the hall
		self.assertEqual(out["cost"], 30800)
		self.assertEqual(out["margin"], 179200)
		self.assertEqual(out["verdict"], "good")

	def test_it_prices_a_what_if_without_touching_the_quote(self):
		fn = self._priced()
		before = self.sheet(fn).discount_amount
		out = bq.quote_advisor(fn, at_discount=100000)
		self.assertEqual(out["revenue"], 110000)
		self.assertLess(out["margin_percent"], 80)
		self.assertEqual(self.sheet(fn).discount_amount, before)

	def test_it_says_how_much_more_can_be_given_away(self):
		out = bq.quote_advisor(self._priced())
		self.assertAlmostEqual(out["max_discount"]["to_break_even"],
		                       210000 - 30800, places=2)
		self.assertLess(out["max_discount"]["to_target"],
		                out["max_discount"]["to_break_even"])

	def test_it_refuses_to_pretend_when_nothing_is_costed(self):
		# the boardroom carries no running cost, so nothing on this quote
		# has a buy price at all
		fn = enquiry(self.f, venue=self.f["small"])
		doc = self.sheet(fn)
		for r in doc.items:
			r.cost_rate = 0
		doc.save(ignore_permissions=True)
		out = bq.quote_advisor(fn)
		self.assertEqual(out["verdict"], "unknown")
		self.assertIn("imaginary", out["advice"])

	def test_it_calls_a_loss_a_loss(self):
		fn = self._priced()
		out = bq.quote_advisor(fn, at_discount=200000)
		self.assertEqual(out["verdict"], "loss")
		self.assertLess(out["margin"], 0)

	def test_it_says_how_much_more_food_would_free_the_hall(self):
		fn = enquiry(self.f)
		bq.update_function(fn, {
			"pax_guaranteed": 100,
			"hall_deal": "Hall free over a minimum spend",
			"minimum_fnb_spend": 200000})
		bq.add_menu(fn, self.f["menu"])          # 120,000 of 200,000
		hall = bq.quote_advisor(fn)["hall"]
		self.assertFalse(hall["waived"])
		self.assertEqual(hall["short_by"], 80000)


class TestDocumentCompliance(BanquetTestCase):
	"""A quotation and a tax invoice are documents a customer files and an
	auditor reads. They need the hotel's identity on them, a number of
	their own that never moves, and the tax stated the way the law states
	it."""

	def _sold(self):
		fn = enquiry(self.f)
		bq.update_function(fn, {"pax_guaranteed": 100})
		bq.add_menu(fn, self.f["menu"])          # food at 5%
		bq.add_service(fn, self.f["led"])        # AV at 18%
		bq.set_status(fn, "Confirmed")
		return fn

	def test_the_hotels_identity_is_on_the_paper(self):
		doc = bq.banquet_document(self._sold(), "quote")
		p = doc["property"]
		self.assertTrue(p["property_name"])
		self.assertTrue(p["address"])
		self.assertTrue(p["gstin"])
		self.assertIn("logo_url", p)

	def test_a_quotation_gets_a_number_that_survives_revisions(self):
		fn = self._sold()
		first = bq.generate_quote(fn)["header"]
		self.assertTrue(first["number"].startswith("QTN-"))
		self.assertEqual(first["version"], 1)
		second = bq.generate_quote(fn)["header"]
		self.assertEqual(second["number"], first["number"])
		self.assertEqual(second["version"], 2)

	def test_an_invoice_number_is_assigned_once_and_never_moves(self):
		fn = self._sold()
		first = bq.generate_invoice(fn)["header"]
		self.assertTrue(first["number"].startswith("BINV-"))
		self.assertEqual(bq.generate_invoice(fn)["header"]["number"],
		                 first["number"])
		# and re-printing gives the same document
		self.assertEqual(bq.banquet_document(fn, "invoice")["header"]["number"],
		                 first["number"])

	def test_an_unissued_document_says_it_is_a_draft(self):
		fn = self._sold()
		self.assertFalse(bq.banquet_document(fn, "quote")["header"]["is_final"])
		bq.generate_quote(fn)
		self.assertTrue(bq.banquet_document(fn, "quote")["header"]["is_final"])

	def test_every_line_carries_its_service_code(self):
		doc = bq.banquet_document(self._sold(), "invoice")
		codes = {l["item_name"]: l["service_code"] for l in doc["lines"]}
		# a hall, a menu and a hired LED wall are three different supplies
		self.assertEqual(len(set(codes.values())), 3)
		self.assertTrue(all(codes.values()))

	def test_the_tax_is_broken_out_by_rate_and_named(self):
		doc = bq.banquet_document(self._sold(), "invoice")
		rates = {r["rate"] for r in doc["tax_breakup"]}
		self.assertEqual(rates, {5.0, 18.0})       # food and services
		parts = doc["tax_breakup"][0]["parts"]
		self.assertEqual([p["label"] for p in parts], ["CGST", "SGST"])
		# each half is half the rate, and they add back to the whole
		self.assertAlmostEqual(sum(p["amount"] for p in parts),
		                       doc["tax_breakup"][0]["total_tax"], places=2)

	def test_the_total_is_written_out_in_words(self):
		doc = bq.banquet_document(self._sold(), "invoice")
		self.assertTrue(doc["header"]["amount_in_words"].startswith("Rupees"))
		self.assertTrue(doc["header"]["amount_in_words"].endswith("Only"))

	def test_it_carries_the_compliance_footer_and_place_of_supply(self):
		h = bq.banquet_document(self._sold(), "invoice")["header"]
		self.assertIn("computer-generated", h["footer"])
		self.assertEqual(h["place_of_supply"], "Karnataka")
		self.assertEqual(h["tax_id_label"], "GSTIN")

	def test_an_unsold_function_cannot_be_invoiced(self):
		fn = enquiry(self.f)
		bq.add_menu(fn, self.f["menu"])
		with self.assertRaises(frappe.ValidationError):
			bq.generate_invoice(fn)


class TestModuleGate(BanquetTestCase):
	"""A property runs only the parts of Kamra it bought - but two of them
	can't be given up, or the site becomes unadministrable."""

	def test_a_property_runs_only_what_it_switched_on(self):
		from kamra.api import enabled_modules, set_enabled_modules

		set_enabled_modules(PROPERTY, "front-desk,housekeeping,finance")
		on = enabled_modules(PROPERTY)
		self.assertIn("housekeeping", on)
		self.assertNotIn("fnb", on)
		self.assertNotIn("events", on)

	def test_admin_and_the_front_desk_cannot_be_switched_off(self):
		from kamra.api import enabled_modules, set_enabled_modules

		# without admin there is no Settings screen to turn anything back
		# on with, and no way to add a room
		set_enabled_modules(PROPERTY, "finance")
		on = enabled_modules(PROPERTY)
		self.assertIn("admin", on)
		self.assertIn("front-desk", on)

	def test_an_empty_setting_means_everything(self):
		from kamra.api import ALL_MODULES, enabled_modules

		frappe.db.set_value("Property", PROPERTY, "enabled_modules", "")
		self.assertCountEqual(enabled_modules(PROPERTY), list(ALL_MODULES))

	def test_a_module_that_does_not_exist_is_refused(self):
		from kamra.api import set_enabled_modules

		with self.assertRaises(frappe.ValidationError):
			set_enabled_modules(PROPERTY, "front-desk,spa-and-wellness")
