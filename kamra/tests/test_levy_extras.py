"""The levy on extras: "Levy applies to room only" (on by default) keeps the
levy on room nights; switched off, extras carry it on lines of their own that
stay with their charge."""

from decimal import Decimal
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, flt, nowdate

from kamra.api import (_group_money, _post_folio_charge, add_folio_charge, booking_options,
                       change_stay_company, correct_folio_charge, create_booking, get_quote,
                       hk_post_consumable, post_stay_charge, void_folio_charge)
from kamra.checkin import log_checkin_requests
from kamra.folio import (_fnb_gst, charged_nights, open_folio, post_room_night, share_charges,
                         split_charge, split_folio, transfer_charge, transfer_charges)
from kamra.ledger import batch_post_charge
from kamra.localization import pack_for
from kamra.pricing import extra_net, extra_reading, levy_for_screen, levy_on_extras
from kamra.settings import SETTINGS, get_setting

NIGHTS = 2
# (country, currency, room, extra guest, meal per adult, a typed charge): 0, 2 and 3 decimals
HOTELS = (
	("Indonesia", "IDR", 389000, 150000, 50000, 100000),
	("Japan", "JPY", 11000, 2200, 1100, 900),
	("India", "INR", 3000, 700, 500, 450),
	("Kuwait", "KWD", 45.125, 12.375, 3.125, 7.875),
)
# (rates include tax, rates include the levy)
INCLUDES = ((1, 1), (1, 0), (0, 1), (0, 0))


def reading(extras=True, tax=True, levy=True):
	return {"levy_on_extras": extras, "tax_included": tax, "levy_included": levy}


class LevyCase(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		frappe.local.lang = "en"
		self.dates = [str(add_days(nowdate(), 10 + i)) for i in range(NIGHTS + 1)]

	def hotel(self, country="Indonesia", currency="IDR", room=389000, meal=50000,
	          tax_in=1, levy_in=1, levy=10, levy_taxed=1, room_only=0):
		prop = frappe.get_doc({"doctype": "Property",
			"property_name": "TEST LEVY " + frappe.generate_hash(length=8),
			"country": country, "currency": currency,
			"rates_include_tax": tax_in, "rates_include_levy": levy_in,
			"room_levy_label": "Service charge", "room_levy_percent": levy,
			"room_levy_taxable": levy_taxed}).insert(ignore_permissions=True).name
		self.set_prop(prop, levy_room_only=room_only)
		rt = frappe.get_doc({"doctype": "Room Type", "property": prop, "room_type_code": "STD",
			"room_type_name": "Standard", "base_price": room, "tax_percent": 10,
			"adults_capacity": 2, "max_extra_beds": 1}).insert(ignore_permissions=True).name
		for number in ("101", "102"):
			frappe.get_doc({"doctype": "Room", "property": prop, "room_type": rt,
				"room_number": number}).insert(ignore_permissions=True)
		mp = frappe.db.get_value("Meal Plan", {"property": prop, "code": "CP"})
		if mp:
			frappe.db.set_value("Meal Plan", mp, {"price_per_adult": meal, "price_per_child": 0})
		else:
			mp = frappe.get_doc({"doctype": "Meal Plan", "property": prop, "code": "CP",
				"label": "Breakfast", "price_per_adult": meal,
				"price_per_child": 0}).insert(ignore_permissions=True).name
		return prop, rt, mp

	def set_prop(self, prop, **values):
		frappe.db.set_value("Property", prop, values)
		frappe.clear_document_cache("Property", prop)


class TestLevySetting(LevyCase):
	def test_new_property_is_room_only(self):
		prop = frappe.get_doc({"doctype": "Property",
			"property_name": "TEST LEVY " + frappe.generate_hash(length=8),
			"country": "Indonesia", "currency": "IDR",
			"room_levy_percent": 10}).insert(ignore_permissions=True).name
		self.assertEqual(frappe.db.get_value("Property", prop, "levy_room_only"), 1)
		self.assertEqual(int(get_setting(prop, "levy_room_only")), 1)
		self.assertFalse(levy_on_extras(prop))

	def test_switched_off_needs_a_levy(self):
		prop, _rt, _mp = self.hotel()
		self.assertTrue(levy_on_extras(prop))
		self.set_prop(prop, room_levy_percent=0)
		self.assertFalse(levy_on_extras(prop))

	def test_the_settings_say_levy(self):
		labels = {k: SETTINGS[k][1].label for k in
		          ("room_levy_label", "room_levy_percent", "levy_room_only")}
		self.assertEqual(labels, {"room_levy_label": "Levy name", "room_levy_percent": "Levy",
		                          "levy_room_only": "Levy applies to room only"})
		self.assertTrue(SETTINGS["levy_room_only"][1].hint.startswith("On: "))

	def test_the_reading_follows_the_settings(self):
		prop, _rt, _mp = self.hotel(tax_in=1, levy_in=0)
		self.assertEqual(extra_reading(prop), reading(levy=False))
		self.set_prop(prop, levy_room_only=1)
		self.assertEqual(extra_reading(prop), reading(extras=False, levy=False))

	def paid(self, prop, price, read, levy=True):
		"""(before tax, what the guest pays) at 10% tax and a taxed 10% levy."""
		net = extra_net(prop, price, 10, read, levy=levy)
		charge = net * Decimal("0.10") if read["levy_on_extras"] and levy else Decimal(0)
		return net, (net + charge) * Decimal("1.10")

	def test_extra_net_follows_both_include_settings(self):
		prop, _rt, _mp = self.hotel()
		for tax_in, levy_in, total in ((1, 1, 100000), (1, 0, 110000),
		                               (0, 1, 110000), (0, 0, 121000)):
			with self.subTest(tax_in=tax_in, levy_in=levy_in):
				_net, paid = self.paid(prop, 100000, reading(tax=bool(tax_in), levy=bool(levy_in)))
				self.assertAlmostEqual(float(paid), total, places=6)

	def test_extra_net_with_an_untaxed_levy_inside(self):
		prop, _rt, _mp = self.hotel(levy_taxed=0)
		net = extra_net(prop, 100000, 10, reading())
		self.assertAlmostEqual(float(net * Decimal("1.10") + net * Decimal("0.10")), 100000, places=6)

	def test_extra_net_without_the_levy(self):
		prop, _rt, _mp = self.hotel()
		# unticked: no levy, the tax still read by its setting
		self.assertAlmostEqual(float(self.paid(prop, 100000, reading(), levy=False)[1]), 100000, places=6)
		self.assertEqual(extra_net(prop, 100000, 10, reading(tax=False), levy=False), 100000)
		# room only: just the tax comes out when it is inside
		room_only = reading(extras=False)
		self.assertAlmostEqual(float(extra_net(prop, 110, 10, room_only)), 100, places=6)
		self.assertEqual(extra_net(prop, 110, 10, reading(extras=False, tax=False)), 110)


class TestLevyQuote(LevyCase):
	def quoted(self, prop, rt, mp, extra, pets=0):
		return get_quote(prop, rt, self.dates[0], self.dates[-1], adults=2, meal_plan=mp,
		                 over_capacity_charge=extra, pets=pets)

	def fees(self, prop, amount):
		"""A cleaning fee and a pet charge, both once per stay, priced `amount`."""
		self.set_prop(prop, cleaning_fee=amount, cleaning_fee_taxable=1, pets_allowed=1,
		              pet_charge=amount, pet_charge_basis="Per stay")

	def expected(self, prop, q, room, extra, meal, fee, tax_in, levy_in, extras_carry):
		"""What the guest pays at a taxed 10% levy: each price as shown, plus
		whichever of tax and levy it does not already hold."""
		def paid(price, gst, carries):
			tax = 1 if tax_in else 1 + gst / 100
			levy = 1.10 if carries and not levy_in else 1
			return price * tax * levy
		room_gst, fnb = q["nightly"][0]["gst_rate"], _fnb_gst(prop)
		return (NIGHTS * (paid(room, room_gst, True) + paid(extra, room_gst, extras_carry)
		                  + paid(2 * meal, fnb, extras_carry))
		        + 2 * paid(fee, room_gst, extras_carry))

	def test_extras_follow_the_switch_and_both_include_settings(self):
		for country, currency, room, extra, meal, fee in HOTELS:
			for tax_in, levy_in in INCLUDES:
				for room_only in (0, 1):
					with self.subTest(currency=currency, tax_in=tax_in, levy_in=levy_in,
					                  room_only=room_only):
						prop, rt, mp = self.hotel(country, currency, room, meal, tax_in,
						                          levy_in, room_only=room_only)
						self.fees(prop, fee)
						q = self.quoted(prop, rt, mp, extra, pets=1)
						want = self.expected(prop, q, room, extra, meal, fee, tax_in,
						                     levy_in, not room_only)
						self.assertAlmostEqual(q["amount_after_tax"], want, delta=want * 1e-9)
						self.assertEqual(q["levy_on_extras"], not room_only)
						self.assertEqual(q["extras_levy"] > 0, not room_only)

	def test_the_quote_shows_the_levy_on_extras_apart_from_the_room(self):
		prop, rt, mp = self.hotel()
		q = self.quoted(prop, rt, mp, 150000)
		parts = {li["component"]: li["amount"] for li in q["line_items"]}
		self.assertAlmostEqual(q["extras_levy"], (150000 + 100000) / 1.21 * 0.1 * NIGHTS, places=3)
		self.assertAlmostEqual(parts["extras_levy"], q["extras_levy"], places=6)
		self.assertAlmostEqual(q["room_levy"], 389000 / 1.21 * 0.1 * NIGHTS, places=3)

	def test_the_tax_slab_reads_an_extra_bed_without_its_levy(self):
		# 7,500 a night separates 5% from 18%; each stay is just under it
		for tax_in, levy_in, levy_taxed, room, extra in (
				(0, 1, 1, 7700, 520), (1, 1, 1, 8085, 160), (1, 1, 0, 7950, 180)):
			with self.subTest(tax_in=tax_in, levy_taxed=levy_taxed):
				prop, rt, _mp = self.hotel("India", "INR", room, 500, tax_in, levy_in,
				                           10, levy_taxed)
				frappe.db.set_value("Room Type", rt, "tax_percent", 0)
				frappe.clear_document_cache("Room Type", rt)
				q = get_quote(prop, rt, self.dates[0], self.dates[-1], adults=2,
				              over_capacity_charge=extra)
				rates = {li["component"]: li.get("tax_rate") for li in q["line_items"]}
				self.assertEqual((rates["accommodation"], rates["over_capacity"]), (5, 5))


class BillCase(LevyCase):
	def book(self, prop, rt, mp, extra, pets=0, addons=None):
		name = create_booking(prop, rt, self.dates[0], self.dates[-1], "Levy Guest",
		                      adults=2, meal_plan=mp, over_capacity_guests=1,
		                      over_capacity_charge=extra, pets=pets, addons=addons,
		                      over_capacity_reason="Agreed at the desk")["reservation"]
		return frappe.get_doc("Reservation", name)

	def post(self, res):
		"""Open the bill (fees and add-ons) and charge every night."""
		folio = open_folio(frappe.get_doc("Reservation", res.name))
		for night in self.dates[:-1]:
			post_room_night(frappe.get_doc("Reservation", res.name), night)
		return folio

	def lines(self, res, **filters):
		names = frappe.get_all("Folio", {"reservation": res.name}, pluck="name")
		return frappe.get_all("Folio Charge", filters={"parent": ("in", names), **filters},
		                      fields=["name", "parent", "charge_type", "description", "amount",
		                              "gst_rate", "total", "posting_date", "levy_link"],
		                      order_by="posting_date, creation, idx")

	def billed(self, res):
		return sum(flt(r.total) for r in self.lines(res))


class TestLevyOnQuotedExtras(BillCase):
	def test_the_bill_equals_the_quote(self):
		for country, currency, room, extra, meal, fee in HOTELS:
			for tax_in, levy_in in INCLUDES:
				for room_only in (0, 1):
					with self.subTest(currency=currency, tax_in=tax_in, levy_in=levy_in,
					                  room_only=room_only):
						prop, rt, mp = self.hotel(country, currency, room, meal, tax_in,
						                          levy_in, room_only=room_only)
						self.set_prop(prop, cleaning_fee=fee, pets_allowed=1, pet_charge=fee,
						              pet_charge_basis="Per stay")
						res = self.book(prop, rt, mp, extra, pets=1)
						self.post(res)
						# levies added on top are posted in whole cents, line by line
						self.assertAlmostEqual(self.billed(res), flt(res.amount_after_tax),
						                       delta=0.08)

	def test_each_extra_has_a_named_levy_line_sharing_its_key(self):
		prop, rt, mp = self.hotel()
		res = self.book(prop, rt, mp, 150000)
		self.post(res)
		linked = [r for r in self.lines(res) if r.levy_link]
		charges = [r for r in linked if r.charge_type != "Room Levy"]
		self.assertEqual(sorted(r.charge_type for r in charges),
		                 ["Extra Guests"] * NIGHTS + ["Meal Plan"] * NIGHTS)
		for charge in charges:
			levy = [r for r in linked if r.levy_link == charge.levy_link
			        and r.charge_type == "Room Levy"]
			self.assertEqual([r.description for r in levy],
			                 [f"Service charge 10% · {charge.description}"])
			self.assertAlmostEqual(flt(levy[0].amount), flt(charge.amount) * 0.1, places=5)
		self.assertFalse([r for r in self.lines(res, charge_type="Room") if r.levy_link])
		self.assertAlmostEqual(self.billed(res), (389000 + 150000 + 100000) * NIGHTS, places=3)

	def test_room_only_posts_no_levy_on_extras(self):
		prop, rt, mp = self.hotel(room_only=1)
		res = self.book(prop, rt, mp, 150000)
		self.post(res)
		self.assertFalse([r for r in self.lines(res) if r.levy_link])
		self.assertEqual(len(self.lines(res, charge_type="Room Levy")), NIGHTS)

	def test_a_levy_on_an_extra_does_not_stand_in_for_the_rooms(self):
		prop, rt, mp = self.hotel()
		res = self.book(prop, rt, mp, 150000)
		self.post(res)
		first = self.dates[0]
		for row in self.lines(res, posting_date=first):
			if row.charge_type in ("Room", "Room Levy") and not row.levy_link:
				void_folio_charge(row.parent, row.name, "Posted again")
		post_room_night(frappe.get_doc("Reservation", res.name), first)
		self.assertAlmostEqual(self.billed(res), (389000 + 150000 + 100000) * NIGHTS, places=3)

	def test_without_a_name_the_levy_on_extras_is_just_called_levy(self):
		for room_only, name in ((0, "Levy"), (1, "Room levy")):
			with self.subTest(room_only=room_only):
				prop, rt, mp = self.hotel(room_only=room_only)
				self.set_prop(prop, room_levy_label="")
				quoted = get_quote(prop, rt, self.dates[0], self.dates[-1], adults=2, meal_plan=mp)
				self.assertEqual(quoted["levy_label"], name)
				self.assertEqual([li["description"] for li in quoted["line_items"]
				                  if li["component"] == "extras_levy"],
				                 [] if room_only else ["Levy on extras"])
				self.assertEqual(levy_for_screen(prop), None if room_only else "Levy")
				res = self.book(prop, rt, mp, 150000)
				self.post(res)
				levies = self.lines(res, charge_type="Room Levy")
				# the room's own line reads as it always has
				self.assertEqual({r.description for r in levies if not r.levy_link},
				                 {"Room levy 10%"})
				self.assertEqual({r.description.split(" · ")[0] for r in levies if r.levy_link},
				                 set() if room_only else {"Levy 10%"})

	def test_posting_again_adds_nothing(self):
		prop, rt, mp = self.hotel()
		res = self.book(prop, rt, mp, 150000)
		self.post(res)
		before = len(self.lines(res))
		self.post(res)
		self.assertEqual(len(self.lines(res)), before)

	def test_changing_the_switch_after_booking_bills_the_quote(self):
		for booked, later in ((0, 1), (1, 0)):
			with self.subTest(booked=booked):
				prop, rt, mp = self.hotel(room_only=booked)
				res = self.book(prop, rt, mp, 150000)
				self.set_prop(prop, levy_room_only=later)
				self.post(res)
				self.assertAlmostEqual(self.billed(res), flt(res.amount_after_tax), delta=0.02)

	def test_a_quote_from_before_the_switch_bills_room_only(self):
		prop, rt, mp = self.hotel(room_only=1)
		res = self.book(prop, rt, mp, 150000)
		snapshot = frappe.parse_json(res.quote_snapshot)
		for key in ("levy_on_extras", "tax_included", "levy_included", "extras_levy"):
			snapshot.pop(key)
		frappe.db.set_value("Reservation", res.name, "quote_snapshot", frappe.as_json(snapshot))
		self.set_prop(prop, levy_room_only=0)
		self.post(res)
		self.assertFalse([r for r in self.lines(res) if r.levy_link])
		self.assertAlmostEqual(self.billed(res), flt(res.amount_after_tax), delta=0.02)

	def test_a_booking_with_no_quote_follows_the_settings(self):
		prop, rt, mp = self.hotel(room_only=1)
		res = self.book(prop, rt, mp, 150000)
		frappe.db.set_value("Reservation", res.name, "quote_snapshot", None)
		self.set_prop(prop, levy_room_only=0)
		self.post(res)
		self.assertTrue([r for r in self.lines(res, charge_type="Extra Guests") if r.levy_link])

	def experience(self, prop, price):
		return frappe.get_doc({"doctype": "Experience", "property": prop,
			"experience_name": "Dinner on the roof", "category": "Dining",
			"price": price, "gst_rate": 10}).insert(ignore_permissions=True).name

	def test_an_add_on_bills_what_the_booking_screen_showed(self):
		for tax_in, levy_in, shown in ((1, 1, 100000), (0, 0, 121000), (1, 0, 110000)):
			with self.subTest(tax_in=tax_in, levy_in=levy_in):
				prop, rt, mp = self.hotel(tax_in=tax_in, levy_in=levy_in)
				exp = self.experience(prop, 100000)
				offered = booking_options(prop)["experiences"]
				self.assertAlmostEqual(offered[0]["levy_gross"], shown, places=3)
				res = self.book(prop, rt, mp, 0, addons=[{"experience": exp, "qty": 1}])
				self.set_prop(prop, levy_room_only=1, rates_include_tax=1 - tax_in)
				folio = self.post(res)
				rows = [r for r in self.lines(res, parent=folio)
				        if "Dinner on the roof" in r.description]
				self.assertEqual(len(rows), 2)
				self.assertAlmostEqual(sum(flt(r.total) for r in rows), shown, delta=0.02)

	def test_an_add_on_with_the_switch_on_is_as_before(self):
		prop, rt, mp = self.hotel(room_only=1)
		exp = self.experience(prop, 100000)
		self.assertNotIn("levy_gross", booking_options(prop)["experiences"][0])
		res = self.book(prop, rt, mp, 0, addons=[{"experience": exp, "qty": 1}])
		self.post(res)
		rows = [r for r in self.lines(res) if "Dinner on the roof" in r.description]
		self.assertEqual([(flt(r.amount), flt(r.total)) for r in rows], [(100000, 110000)])


class StayCase(BillCase):
	def stay(self, country="Indonesia", currency="IDR", room=389000, **settings):
		"""A checked-in stay with an empty guest bill."""
		prop, rt, mp = self.hotel(country, currency, room, **settings)
		res = self.book(prop, rt, None, 0)
		frappe.db.set_value("Reservation", res.name, "status", "Checked In")
		res = frappe.get_doc("Reservation", res.name)
		return prop, res, open_folio(res)


class TestLevyOnPostedCharges(StayCase):
	def posted(self, res):
		return [(r.charge_type, r.description, flt(r.total)) for r in self.lines(res)]

	def test_a_typed_charge_follows_both_include_settings(self):
		for country, currency, room, _extra, _meal, price in HOTELS:
			for tax_in, levy_in in INCLUDES:
				with self.subTest(currency=currency, tax_in=tax_in, levy_in=levy_in):
					prop, res, folio = self.stay(country, currency, room,
					                            tax_in=tax_in, levy_in=levy_in)
					rates = [float(r) for r in pack_for(prop).tax_rate_options(prop)]
					tax = 10 if 10 in rates else next(r for r in rates if r)
					add_folio_charge(folio, "Misc", "Airport pickup", price, gst_rate=tax, levy=1)
					want = price * (1 if tax_in else 1 + tax / 100) * (1 if levy_in else 1.1)
					self.assertEqual(len(self.lines(res)), 2)
					self.assertAlmostEqual(self.billed(res), want, delta=0.02)

	def test_the_levy_line_names_the_charge_and_shares_its_key(self):
		_prop, res, folio = self.stay()
		add_folio_charge(folio, "Misc", "Airport pickup", 100000, gst_rate=10, levy=1)
		charge, levy = sorted(self.lines(res), key=lambda r: r.charge_type)
		self.assertEqual((charge.charge_type, levy.charge_type), ("Misc", "Room Levy"))
		self.assertEqual(levy.description, "Service charge 10% · Airport pickup")
		self.assertTrue(charge.levy_link)
		self.assertEqual(levy.levy_link, charge.levy_link)
		self.assertAlmostEqual(flt(charge.amount), 100000 / 1.21, places=5)

	def test_an_unticked_charge_carries_no_levy(self):
		_prop, res, folio = self.stay()
		add_folio_charge(folio, "Misc", "Lost key", 100000, gst_rate=0, levy=0)
		add_folio_charge(folio, "Misc", "Damaged towel", 110000, gst_rate=10, levy=0)
		self.assertEqual([(r.charge_type, round(flt(r.total), 3)) for r in self.lines(res)],
		                 [("Misc", 100000), ("Misc", 110000)])

	def test_room_only_posts_a_typed_charge_as_before(self):
		_prop, res, folio = self.stay(room_only=1)
		add_folio_charge(folio, "Misc", "Airport pickup", 100000, gst_rate=10, levy=1)
		post_stay_charge(res.name, "Laundry", "Two shirts", 50000, gst_rate=10, levy=1)
		self.assertEqual([(flt(r.amount), flt(r.total)) for r in self.lines(res)],
		                 [(100000, 110000), (50000, 55000)])

	def test_charges_posted_by_other_parts_of_kamra_carry_it(self):
		_prop, res, _folio = self.stay()
		post_stay_charge(res.name, "Laundry", "Two shirts", 50000, gst_rate=10, levy=1)
		self.assertEqual(sorted(r.charge_type for r in self.lines(res)),
		                 ["Laundry", "Room Levy"])
		self.assertAlmostEqual(self.billed(res), 50000, places=3)

	def test_a_stolen_or_damaged_item_never_carries_it(self):
		_prop, res, folio = self.stay()
		add_folio_charge(folio, "Stolen / Damaged Items", "Broken kettle", 110000,
		                 gst_rate=10, levy=1)
		self.assertEqual([(r.charge_type, round(flt(r.total), 3)) for r in self.lines(res)],
		                 [("Stolen / Damaged Items", 110000)])

	def test_charges_with_their_own_service_get_none(self):
		_prop, res, folio = self.stay()
		post_stay_charge(res.name, "Food & Beverage", "Rooftop bar (POS 7)", 50000,
		                 gst_rate=10, levy=None)  # an outside POS
		_post_folio_charge(folio, "Misc", "Banquet hall", 70000, 10)  # banquets, deposits
		self.assertEqual([(flt(r.amount), r.levy_link or "") for r in self.lines(res)],
		                 [(50000, ""), (70000, "")])

	def test_a_charge_posted_to_many_bills_carries_it(self):
		_prop, res, folio = self.stay()
		batch_post_charge([folio], "Misc", 100000, "Gala dinner", levy=1)
		self.assertEqual(sorted(r.charge_type for r in self.lines(res)), ["Misc", "Room Levy"])
		self.assertAlmostEqual(self.billed(res), 100000, places=3)
		self.assertAlmostEqual(
			flt(frappe.db.get_value("Folio", folio, "balance")), 100000, places=3)


class TestLevyPairs(StayCase):
	def pair(self, amount=100000, **settings):
		"""A bill holding one extra and its levy: (stay, bill, charge, levy)."""
		prop, res, folio = self.stay(**settings)
		add_folio_charge(folio, "Misc", "Airport pickup", amount, gst_rate=10, levy=1)
		charge, levy = sorted(self.lines(res), key=lambda r: r.charge_type)
		return res, folio, charge, levy

	def on(self, res, folio):
		"""What one bill of the stay comes to."""
		return sum(flt(r.total) for r in self.lines(res, parent=folio))

	def other_bill(self, res):
		return split_folio(res.name, "Extra")

	def assert_pairs_together(self, res, folio):
		linked = {}
		for row in self.lines(res, parent=folio):
			linked.setdefault(row.levy_link, 0)
			linked[row.levy_link] += flt(row.total) * (-1 if row.charge_type == "Room Levy" else 0.1)
		# on every bill each levy is a tenth of the charge it sits beside
		for link, off in linked.items():
			self.assertAlmostEqual(off, 0, delta=0.02, msg=link)

	def test_voiding_the_charge_voids_its_levy(self):
		res, folio, charge, _levy = self.pair()
		void_folio_charge(folio, charge.name, "Wrong room")
		self.assertAlmostEqual(self.billed(res), 0, places=3)
		self.assertAlmostEqual(flt(frappe.db.get_value("Folio", folio, "balance")), 0, places=3)

	def test_a_levy_can_be_waived_alone_and_stays_waived(self):
		res, folio, charge, levy = self.pair()
		void_folio_charge(folio, levy.name, "Waived")
		self.assertAlmostEqual(self.billed(res), flt(charge.total), places=3)
		correct_folio_charge(folio, charge.name, "Wording", description="Airport run")
		self.assertAlmostEqual(self.billed(res), flt(charge.total), places=3)
		repost = self.lines(res, charge_type="Misc", description="Airport run")[0]
		void_folio_charge(folio, repost.name, "Not taken")
		self.assertAlmostEqual(self.billed(res), 0, places=3)

	def test_correcting_the_amount_carries_to_the_levy(self):
		res, folio, charge, _levy = self.pair()
		correct_folio_charge(folio, charge.name, "Agreed less", amount=flt(charge.amount) / 2)
		self.assertAlmostEqual(self.billed(res), 50000, places=2)
		repost = [r for r in self.lines(res, charge_type="Misc") if r.amount > 0][-1]
		void_folio_charge(folio, repost.name, "Not taken")
		self.assertAlmostEqual(self.billed(res), 0, places=2)

	def test_correcting_the_tax_carries_to_the_levy(self):
		res, folio, charge, _levy = self.pair()
		correct_folio_charge(folio, charge.name, "Not taxed", gst_rate=0)
		self.assertAlmostEqual(self.billed(res), 100000 / 1.1, places=2)

	def test_rewording_a_charge_leaves_its_levy_alone(self):
		res, folio, charge, levy = self.pair()
		before = len(self.lines(res))
		correct_folio_charge(folio, charge.name, "Wording", description="Airport run")
		self.assertEqual(len(self.lines(res)), before + 2)  # the reversal and the repost only
		self.assertIn(levy.name, [r.name for r in self.lines(res, charge_type="Room Levy")])

	def test_moving_either_line_moves_both(self):
		for which in (0, 1):
			with self.subTest(moving=("charge", "levy")[which]):
				res, folio, charge, levy = self.pair()
				other = self.other_bill(res)
				transfer_charge(folio, (charge, levy)[which].name, other)
				self.assertAlmostEqual(self.on(res, other), 100000, places=3)
				self.assertAlmostEqual(self.on(res, folio), 0, places=3)
				moved = self.lines(res, parent=other, charge_type="Misc")[0]
				void_folio_charge(other, moved.name, "Not taken")
				self.assertAlmostEqual(self.billed(res), 0, places=3)

	def test_moving_both_ticked_lines_moves_each_once(self):
		res, folio, charge, levy = self.pair()
		other = self.other_bill(res)
		transfer_charges(folio, [charge.name, levy.name], other)
		self.assertEqual(len(self.lines(res, parent=other)), 2)

	def test_splitting_the_charge_splits_its_levy(self):
		res, folio, charge, _levy = self.pair()
		other = self.other_bill(res)
		split_charge(folio, charge.name, other, percent=30)
		self.assertAlmostEqual(self.on(res, other), 30000, delta=0.02)
		self.assertAlmostEqual(self.billed(res), 100000, places=3)
		self.assert_pairs_together(res, folio)
		self.assert_pairs_together(res, other)

	def test_a_levy_line_is_not_split_on_its_own(self):
		res, folio, _charge, levy = self.pair()
		other = self.other_bill(res)
		with self.assertRaises(frappe.ValidationError):
			split_charge(folio, levy.name, other, percent=30)
		self.assertAlmostEqual(self.on(res, folio), 100000, places=3)

	def test_voiding_one_share_leaves_the_other(self):
		res, folio, charge, _levy = self.pair()
		other = self.other_bill(res)
		split_charge(folio, charge.name, other, percent=30)
		theirs = self.lines(res, parent=other, charge_type="Misc")[0]
		transfer_charge(other, theirs.name, folio)  # back onto the first bill
		void_folio_charge(folio, charge.name, "One share not taken")
		self.assertAlmostEqual(self.billed(res), 30000, delta=0.02)
		self.assert_pairs_together(res, folio)

	def test_sharing_with_both_lines_ticked_cuts_each_once(self):
		res, folio, charge, levy = self.pair()
		other = self.other_bill(res)
		share_charges(folio, [charge.name, levy.name], [other], [30])
		self.assertAlmostEqual(self.on(res, other), 30000, delta=0.02)
		self.assertAlmostEqual(self.billed(res), 100000, places=3)
		self.assert_pairs_together(res, other)

	def test_a_company_change_keeps_the_pair_on_one_bill(self):
		company = frappe.get_doc({"doctype": "Corporate Account",
			"company_name": "TEST LEVY CO " + frappe.generate_hash(length=6),
			"credit_allowed": 1,
			"billing_rules": [{"charge_type": "Misc", "pay_by": "Company"}],
			}).insert(ignore_permissions=True).name
		res, folio, _charge, _levy = self.pair()
		change_stay_company(res.name, "Company will pay", company=company)
		target = frappe.db.get_value("Folio", {"reservation": res.name, "folio_type": "Company"})
		self.assertAlmostEqual(self.on(res, target), 100000, places=3)
		change_stay_company(res.name, "Guest pays after all", company=None)
		self.assertAlmostEqual(self.on(res, folio), 100000, places=3)

	def test_the_rooms_charged_levy_leaves_extras_out(self):
		prop, rt, mp = self.hotel()
		res = self.book(prop, rt, mp, 150000)
		self.post(res)
		night = charged_nights(res.name, 6)[self.dates[0]]
		self.assertAlmostEqual(night["levy_base"], 389000 / 1.21 * 0.1, places=4)


class TestLevyReviewCases(StayCase):
	def test_api_callers_keep_todays_posting_unless_they_ask(self):
		_prop, res, folio = self.stay()
		add_folio_charge(folio, "Misc", "From an integration", 100000, gst_rate=10)
		post_stay_charge(res.name, "Spa", "From an agent", 50000, gst_rate=10)
		batch_post_charge([folio], "Misc", 20000, "Posted in bulk")
		self.assertEqual([(flt(r.amount), r.levy_link or "") for r in self.lines(res)],
		                 [(100000, ""), (50000, ""), (20000, "")])

	def test_check_in_requests_and_consumables_carry_it(self):
		_prop, res, _folio = self.stay()
		frappe.db.set_value("Reservation", res.name, "room", f"{res.property}-101")
		log_checkin_requests(res.name, ["extra_bed"], prices={"extra_bed": 100000})
		hk_post_consumable(f"{res.property}-101", "Minibar", "Soft drinks", 50000)
		self.assertEqual(len(self.extras_levies(res)), 2)
		self.assertAlmostEqual(self.billed(res), 150000, places=3)

	def extras_levies(self, res):
		return [r for r in self.lines(res, charge_type="Room Levy") if r.levy_link]

	def test_integrations_and_the_guest_hear_of_the_whole_charge(self):
		_prop, res, folio = self.stay(tax_in=0, levy_in=0)
		posted, alerts = [], []
		with patch("kamra.webhooks.emit_folio_posted",
		           side_effect=lambda f, row: posted.append(flt(row.amount))), \
				patch("kamra.whatsapp.queue_room_charge_alert",
				      side_effect=lambda f, row: alerts.append(flt(row.get("total")))):
			add_folio_charge(folio, "Misc", "Airport pickup", 100000, gst_rate=10, levy=1)
			self.assertEqual(posted, [100000, 10000])
			self.assertEqual([round(a, 2) for a in alerts], [121000])
			charge = self.lines(res, charge_type="Misc")[0]
			del posted[:]
			correct_folio_charge(folio, charge.name, "Agreed less", amount=50000)
		self.assertIn(5000, posted)

	def test_one_void_by_the_desk_is_one_void_on_record(self):
		res, folio = self.stay()[1:]
		add_folio_charge(folio, "Misc", "Airport pickup", 100000, gst_rate=10, levy=1)
		count = lambda: frappe.db.count("Agent Action Log",
			{"property": res.property, "action_type": "void_charge"})
		before = count()
		charge = self.lines(res, charge_type="Misc")[0]
		void_folio_charge(folio, charge.name, "Wrong room")
		self.assertEqual(count() - before, 1)

	def test_a_replaced_line_never_takes_the_new_levy_with_it(self):
		res, folio = self.stay()[1:]
		add_folio_charge(folio, "Misc", "Airport pickup", 100000, gst_rate=10, levy=1)
		original = self.lines(res, charge_type="Misc")[0]
		correct_folio_charge(folio, original.name, "Agreed less", amount=41322.31405)
		other = split_folio(res.name, "Extra")
		transfer_charge(folio, original.name, other)
		self.assertFalse(self.lines(res, parent=other, charge_type="Room Levy"))

	def test_correcting_to_a_damaged_item_drops_the_levy(self):
		res, folio = self.stay()[1:]
		add_folio_charge(folio, "Misc", "Airport pickup", 100000, gst_rate=10, levy=1)
		charge = self.lines(res, charge_type="Misc")[0]
		correct_folio_charge(folio, charge.name, "It was a kettle",
		                     charge_type="Stolen / Damaged Items", amount=100000)
		self.assertAlmostEqual(self.billed(res), 110000, places=3)

	def test_a_negative_amount_gets_no_levy(self):
		res, folio = self.stay()[1:]
		batch_post_charge([folio], "Misc", -20000, "Goodwill", levy=1)
		self.assertEqual([(flt(r.amount), r.levy_link or "") for r in self.lines(res)],
		                 [(-20000, "")])

	def test_group_still_to_pay_counts_no_levy_on_a_typed_extra(self):
		res, folio = self.stay(tax_in=0, levy_in=0)[1:]
		add_folio_charge(folio, "Misc", "Airport pickup", 100000, gst_rate=10, levy=1)
		rooming = [frappe._dict(name=res.name, status="Checked In", amount_after_tax=2000000)]
		group = frappe._dict(name="TEST LEVY NO GROUP")
		money = _group_money(group, {"total": 2000000}, rooming)
		self.assertAlmostEqual(money["due"], 2121000, places=2)

	def test_a_re_quoted_stay_keeps_whether_its_extras_carry_the_levy(self):
		for booked in (0, 1):
			with self.subTest(room_only=booked):
				# with the levy added on top, a changed reading would change totals
				prop, rt, mp = self.hotel(room_only=booked, tax_in=0, levy_in=0)
				res = self.book(prop, rt, mp, 150000)
				self.post(res)
				self.set_prop(prop, levy_room_only=1 - booked)
				doc = frappe.get_doc("Reservation", res.name)
				doc.check_out_date = str(add_days(self.dates[-1], 1))
				doc.save(ignore_permissions=True)
				post_room_night(frappe.get_doc("Reservation", res.name), self.dates[-1])
				self.assertAlmostEqual(self.billed(res), flt(doc.amount_after_tax), delta=0.02)

	def test_an_unreadable_quote_does_not_stop_check_in(self):
		prop, rt, mp = self.hotel()
		res = self.book(prop, rt, mp, 150000)
		frappe.db.set_value("Reservation", res.name, "quote_snapshot", "{not json")
		self.assertTrue(open_folio(frappe.get_doc("Reservation", res.name)))
