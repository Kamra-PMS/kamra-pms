"""Unit and integration tests for Holiday Packages (closed packages with tiered occupancy pricing)."""

from __future__ import annotations

from decimal import Decimal

import frappe
from frappe.utils import add_days, getdate

from kamra import pricing, rates
from kamra.kamra.doctype.holiday_package.holiday_package import HolidayPackage
from kamra.tests.audit_fixtures import PROP_A, TODAY, AuditTestCase, make_property, make_room_type


class HolidayPackageTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY)
		make_property(PROP_A, business_date=TODAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=200, extra_adult_price=70, adults_capacity=4)
		self.day0 = str(getdate(TODAY))
		self.day1 = str(add_days(self.day0, 1))
		self.day2 = str(add_days(self.day0, 2))
		self.day3 = str(add_days(self.day0, 3))
		self.day4 = str(add_days(self.day0, 4))
		self.day5 = str(add_days(self.day0, 5))

	def make_package(self, **kw):
		data = {
			"doctype": "Holiday Package",
			"property": PROP_A,
			"package_name": "Pacote Feriado 3 Noites",
			"room_type": self.rt,
			"start_date": self.day0,
			"end_date": self.day2,  # 3 nights: day0, day1, day2; check_out on day3
			"package_nights": 3,
			"extra_night_price": 500,
			"price_1_pax": 1600,
			"price_2_pax": 1850,
			"price_3_pax": 2500,
			"price_4_pax": 3000,
			"price_5_pax": 3600,
			"extra_adult_price": 500,
			"child_price": 200,
			"ota_strategy": "Markup",
			"ota_daily_rate": 1300,
			"flyer_image": "/files/carnaval_2026.png",
			"advance_percent": 50,
			"non_refundable": 1,
			"inclusions": "Café da manhã incluso e passeio no rio",
			"priority": 20,
			"disabled": 0,
		}
		data.update(kw)
		return frappe.get_doc(data).insert(ignore_permissions=True)

	def test_holiday_package_validations(self):
		"""Validation edge cases: end_date before start_date, non-positive package_nights/price."""
		# start_date > end_date throws
		doc_bad_dates = frappe.get_doc({
			"doctype": "Holiday Package",
			"property": PROP_A,
			"package_name": "Bad Dates",
			"start_date": self.day2,
			"end_date": self.day0,
			"package_nights": 3,
			"price_2_pax": 1850,
		})
		self.assertRaises(frappe.ValidationError, doc_bad_dates.insert)

		# package_nights < 1 throws
		doc_bad_min = frappe.get_doc({
			"doctype": "Holiday Package",
			"property": PROP_A,
			"package_name": "Bad Min",
			"start_date": self.day0,
			"end_date": self.day2,
			"package_nights": 0,
			"price_2_pax": 1850,
		})
		self.assertRaises(frappe.ValidationError, doc_bad_min.insert)

		# price_2_pax <= 0 throws
		doc_bad_price = frappe.get_doc({
			"doctype": "Holiday Package",
			"property": PROP_A,
			"package_name": "Bad Price",
			"start_date": self.day0,
			"end_date": self.day2,
			"package_nights": 3,
			"price_2_pax": 0,
		})
		self.assertRaises(frappe.ValidationError, doc_bad_price.insert)

		# extra_night_price < 0 throws
		doc_bad_extra_night = frappe.get_doc({
			"doctype": "Holiday Package",
			"property": PROP_A,
			"package_name": "Bad Extra Night",
			"start_date": self.day0,
			"end_date": self.day2,
			"package_nights": 3,
			"price_2_pax": 1850,
			"extra_night_price": -50,
		})
		self.assertRaises(frappe.ValidationError, doc_bad_extra_night.insert)

		# advance_percent > 100 throws
		doc_bad_adv = frappe.get_doc({
			"doctype": "Holiday Package",
			"property": PROP_A,
			"package_name": "Bad Advance",
			"start_date": self.day0,
			"end_date": self.day2,
			"package_nights": 3,
			"price_2_pax": 1850,
			"advance_percent": 150,
		})
		self.assertRaises(frappe.ValidationError, doc_bad_adv.insert)

		# ota_daily_rate negative throws
		doc_bad_ota = frappe.get_doc({
			"doctype": "Holiday Package",
			"property": PROP_A,
			"package_name": "Bad OTA",
			"start_date": self.day0,
			"end_date": self.day2,
			"package_nights": 3,
			"price_2_pax": 1850,
			"ota_strategy": "Markup",
			"ota_daily_rate": -100,
		})
		self.assertRaises(frappe.ValidationError, doc_bad_ota.insert)

	def test_package_price_calculation_occupancy_tiers(self):
		"""Package rate calculates exact stepped tiers: 1p, 2p, 3p, 4p, 5p, extra pax, and children."""
		pkg = self.make_package()

		# 1 pax: custom single rate (1600)
		self.assertEqual(pkg.package_price_for(1), Decimal(1600))

		# 2 pax: base rate (1850)
		self.assertEqual(pkg.package_price_for(2), Decimal(1850))

		# 3 pax: stepped rate (2500)
		self.assertEqual(pkg.package_price_for(3), Decimal(2500))

		# 4 pax: stepped rate (3000)
		self.assertEqual(pkg.package_price_for(4), Decimal(3000))

		# 5 pax: stepped rate (3600)
		self.assertEqual(pkg.package_price_for(5), Decimal(3600))

		# 6 pax: 5 pax (3600) + 1 extra adult @ 500 = 4100
		self.assertEqual(pkg.package_price_for(6), Decimal(4100))

		# 2 pax + 2 children @ 200 = 1850 + 400 = 2250
		self.assertEqual(pkg.package_price_for(2, children=2), Decimal(2250))

	def test_package_fallback_when_higher_tiers_empty(self):
		"""When price_3_pax or price_4_pax is not explicitly given, falls back to extra_adult_price."""
		pkg = self.make_package(price_3_pax=0, price_4_pax=0, price_5_pax=0, extra_adult_price=400)
		# 2 pax: 1850
		self.assertEqual(pkg.package_price_for(2), Decimal(1850))
		# 3 pax: 1850 + 400 = 2250
		self.assertEqual(pkg.package_price_for(3), Decimal(2250))
		# 4 pax: 2250 + 400 = 2650
		self.assertEqual(pkg.package_price_for(4), Decimal(2650))

	def test_package_extra_night_pricing(self):
		"""Package duration with additional nights billed at extra_night_price."""
		pkg = self.make_package(package_nights=3, extra_night_price=600)

		# 3 nights (2 pax): base package rate (1850)
		self.assertEqual(pkg.package_price_for(2, nights=3), Decimal(1850))

		# 4 nights (2 pax): 1850 + 1 * 600 = 2450
		self.assertEqual(pkg.package_price_for(2, nights=4), Decimal(2450))

		# 5 nights (2 pax): 1850 + 2 * 600 = 3050
		self.assertEqual(pkg.package_price_for(2, nights=5), Decimal(3050))

	def test_active_holiday_package_resolution_and_priority(self):
		"""Package discovery respects date coverage, room type specificity and priority."""
		pkg_general = self.make_package(package_name="General House Package", room_type="", priority=10)
		pkg_specific = self.make_package(package_name="Room Specific Package", room_type=self.rt, priority=10)

		# Specific room type package wins over general
		found = pricing.active_holiday_package(PROP_A, self.day0, self.day3, self.rt)
		self.assertIsNotNone(found)
		self.assertEqual(found.package_name, "Room Specific Package")

		# Disabled package does not match
		pkg_specific.disabled = 1
		pkg_specific.save(ignore_permissions=True)
		found_fallback = pricing.active_holiday_package(PROP_A, self.day0, self.day3, self.rt)
		self.assertEqual(found_fallback.package_name, "General House Package")

	def test_quote_exact_package_rates_for_2_3_4_adults(self):
		"""Crucial Delta Park scenario: 3 nights package produces exact 1850, 2500, 3000 without rounding leak."""
		self.make_package()

		# 2 adults for 3 nights: exact 1850.00
		q2 = pricing.quote(PROP_A, self.rt, self.day0, self.day3, adults=2, children=0)
		self.assertEqual(q2["room_total"], 1850.0)
		self.assertEqual(len(q2["nightly"]), 3)
		self.assertAlmostEqual(sum(n["rate"] for n in q2["nightly"]), 1850.0, places=2)
		self.assertEqual(q2["package"]["package_name"], "Pacote Feriado 3 Noites")
		self.assertEqual(q2["package"]["package_nights"], 3)
		self.assertEqual(q2["package"]["extra_night_price"], 500.0)
		self.assertEqual(q2["package"]["flyer_image"], "/files/carnaval_2026.png")
		self.assertEqual(q2["package"]["ota_daily_rate"], 1300.0)
		self.assertEqual(q2["advance"]["percent"], 50.0)

		# 3 adults for 3 nights: exact 2500.00
		q3 = pricing.quote(PROP_A, self.rt, self.day0, self.day3, adults=3, children=0)
		self.assertEqual(q3["room_total"], 2500.0)
		self.assertEqual(len(q3["nightly"]), 3)
		self.assertAlmostEqual(sum(n["rate"] for n in q3["nightly"]), 2500.0, places=2)

		# 4 adults for 3 nights: exact 3000.00
		q4 = pricing.quote(PROP_A, self.rt, self.day0, self.day3, adults=4, children=0)
		self.assertEqual(q4["room_total"], 3000.0)
		self.assertEqual(len(q4["nightly"]), 3)
		self.assertAlmostEqual(sum(n["rate"] for n in q4["nightly"]), 3000.0, places=2)

	def test_quote_with_extra_nights_beyond_package_duration(self):
		"""A 4-night stay on a 3-night package charges package rate + 1 extra night @ extra_night_price."""
		self.make_package(package_nights=3, extra_night_price=500)

		# 2 adults for 4 nights: 1850 (package) + 500 (extra night) = 2350.00
		q_4n = pricing.quote(PROP_A, self.rt, self.day0, self.day4, adults=2, children=0)
		self.assertEqual(q_4n["room_total"], 2350.0)
		self.assertEqual(len(q_4n["nightly"]), 4)
		self.assertAlmostEqual(sum(n["rate"] for n in q_4n["nightly"]), 2350.0, places=2)
		self.assertIn("Diária Adicional", q_4n["nightly"][-1]["package"])
		self.assertEqual(q_4n["nightly"][-1]["rate"], 500.0)

	def test_reveillon_flyer_scenarios_touching_peak_date(self):
		"""Real-world Réveillon flyer test:
		Package window is day4..day6 (3 nights, e.g. 31/12, 01/01, 02/01).
		1. Guest staying day2..day5 (3 nights: day2, day3, day4; touches day4) -> Charged full 3-night package (1850.00).
		2. Guest staying day0..day7 (7 nights; touches day4..day6) -> 3 nights package (1850) + 4 extra nights @ 400 = 3450.00.
		"""
		d0 = self.day0
		d2 = str(add_days(d0, 2))
		d4 = str(add_days(d0, 4))
		d5 = str(add_days(d0, 5))
		d6 = str(add_days(d0, 6))
		d7 = str(add_days(d0, 7))

		self.make_package(
			package_name="Pacote Réveillon Costa do Mar",
			start_date=d4,
			end_date=d6,
			package_nights=3,
			price_2_pax=1850,
			extra_night_price=400,
			priority=50,
		)

		# Case 1: 3 nights (d2..d5) that touch the 31st (d4)
		q_shifted = pricing.quote(PROP_A, self.rt, d2, d5, adults=2)
		self.assertEqual(q_shifted["room_total"], 1850.0)
		self.assertEqual(len(q_shifted["nightly"]), 3)
		self.assertEqual(q_shifted["package"]["package_name"], "Pacote Réveillon Costa do Mar")

		# Case 2: 7 nights (d0..d7) enclosing the package: 3 package nights + 4 extra nights @ 400
		q_extended = pricing.quote(PROP_A, self.rt, d0, d7, adults=2)
		self.assertEqual(q_extended["room_total"], 3450.0)
		self.assertEqual(len(q_extended["nightly"]), 7)
		pkg_nights = [n for n in q_extended["nightly"] if n["package"] == "Pacote Réveillon Costa do Mar"]
		extra_nights = [n for n in q_extended["nightly"] if "Diária Adicional" in n["package"]]
		self.assertEqual(len(pkg_nights), 3)
		self.assertEqual(len(extra_nights), 4)
		self.assertEqual(extra_nights[0]["rate"], 400.0)

	def test_agreed_rate_bypasses_package(self):
		"""When staff specifies an agreed rate at front desk, it overrides the package rate."""
		self.make_package()
		q_agreed = pricing.quote(PROP_A, self.rt, self.day0, self.day3, adults=2, agreed_rate=500)
		# 3 nights @ 500 = 1500
		self.assertEqual(q_agreed["room_total"], 1500.0)
		self.assertIsNone(q_agreed["package"])

	def test_stay_season_rules_and_rates_explain_night(self):
		"""Stay rules and explain_night expose package attributes, package_nights, and OTA rate."""
		pkg = self.make_package()

		rules = pricing.stay_season_rules(PROP_A, self.day0, self.day3, self.rt)
		self.assertEqual(rules["minimum_nights"], 3)
		self.assertTrue(rules["non_refundable"])
		self.assertEqual(rules["holiday"], "Pacote Feriado 3 Noites")
		self.assertEqual(rules["advance_percent"], 50.0)

		# Explain night returns package details
		rt_doc = frappe.get_doc("Room Type", self.rt)
		n = rates.explain_night(PROP_A, rt_doc, self.day0)
		self.assertIsNotNone(n.get("package"))
		self.assertEqual(n["package"]["label"], "Pacote Feriado 3 Noites")
		self.assertEqual(n["package"]["flyer_image"], "/files/carnaval_2026.png")
		self.assertEqual(n["package"]["ota_rate"], 1300.0)
		self.assertEqual(n["package"]["package_nights"], 3)
		self.assertEqual(n["package"]["extra_night_price"], 500.0)
