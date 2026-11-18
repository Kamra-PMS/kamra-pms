"""Nightly prices typed on New booking (#634): validation only, no DB writes."""

import unittest
from decimal import Decimal
from unittest.mock import patch

import frappe

from kamra.pricing import MAX_NIGHT_PRICE, normalize_night_prices, refuse_with_night_prices


class TestNightPrices(unittest.TestCase):
	def test_empty_payload_is_no_override(self):
		for raw in (None, "", [], {}):
			self.assertEqual(normalize_night_prices(raw, "2030-02-01", "2030-02-03"), {})

	def test_one_typed_night_kept_other_at_bar(self):
		out = normalize_night_prices(
			[{"date": "2030-02-01", "price": 120}],
			"2030-02-01", "2030-02-03")
		self.assertEqual(out, {"2030-02-01": Decimal("120")})

	def test_json_string_payload(self):
		with patch.object(frappe, "parse_json", return_value=[{"date": "2030-02-01", "price": "99.50"}]):
			out = normalize_night_prices('[{"date":"2030-02-01","price":"99.50"}]',
			                            "2030-02-01", "2030-02-02")
		self.assertEqual(out, {"2030-02-01": Decimal("99.50")})

	def test_date_outside_stay_refused(self):
		with self.assertRaises(frappe.ValidationError):
			normalize_night_prices(
				[{"date": "2030-02-05", "price": 100}],
				"2030-02-01", "2030-02-03")

	def test_checkout_night_refused(self):
		# last night of the stay is the night before check-out
		with self.assertRaises(frappe.ValidationError):
			normalize_night_prices(
				[{"date": "2030-02-03", "price": 100}],
				"2030-02-01", "2030-02-03")

	def test_duplicate_date_refused(self):
		with self.assertRaises(frappe.ValidationError):
			normalize_night_prices(
				[{"date": "2030-02-01", "price": 100},
				 {"date": "2030-02-01", "price": 110}],
				"2030-02-01", "2030-02-03")

	def test_zero_negative_and_extra_decimals_refused(self):
		for price in (0, -5, "0", "120.505", True):
			with self.subTest(price=price), self.assertRaises(frappe.ValidationError):
				normalize_night_prices(
					[{"date": "2030-02-01", "price": price}],
					"2030-02-01", "2030-02-02")

	def test_above_ceiling_refused(self):
		with self.assertRaises(frappe.ValidationError):
			normalize_night_prices(
				[{"date": "2030-02-01", "price": MAX_NIGHT_PRICE + 1}],
				"2030-02-01", "2030-02-02")

	def test_day_use_refused(self):
		with self.assertRaises(frappe.ValidationError):
			normalize_night_prices(
				[{"date": "2030-02-01", "price": 100}],
				"2030-02-01", "2030-02-01")

	def test_extra_keys_refused(self):
		with self.assertRaises(frappe.ValidationError):
			normalize_night_prices(
				[{"date": "2030-02-01", "price": 100, "note": "x"}],
				"2030-02-01", "2030-02-02")

	def test_refuse_with_night_prices_names_the_conflict(self):
		with self.assertRaises(frappe.ValidationError) as ctx:
			refuse_with_night_prices("a voucher")
		self.assertIn("voucher", str(ctx.exception).lower())
