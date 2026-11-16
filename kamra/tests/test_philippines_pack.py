"""Philippines defaults and the localization seam; no database writes."""

import unittest
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

import frappe

from kamra import hooks, localization
from kamra.localization import philippines


class TestPhilippinesPack(unittest.TestCase):
	def test_regional_defaults(self):
		self.assertEqual(philippines.DEFAULT_CURRENCY, "PHP")
		self.assertEqual(philippines.DEFAULT_VAT, Decimal("12"))
		self.assertEqual(philippines.PERCENTAGE_TAX, Decimal("3"))
		self.assertEqual(philippines.DEFAULT_TIMEZONE, "Asia/Manila")
		self.assertEqual(ZoneInfo(philippines.DEFAULT_TIMEZONE).key, "Asia/Manila")
		self.assertEqual(philippines.DEFAULT_NATIONALITY, "Filipino")
		self.assertEqual(philippines.HOME_COUNTRY_ISO3, "PHL")
		self.assertEqual(philippines.FX_CURRENCIES, ["USD", "EUR", "JPY", "KRW", "CNY", "AUD", "SGD", "HKD"])
		self.assertNotIn("PHP", philippines.FX_CURRENCIES)
		self.assertIn("National Privacy Commission", philippines.PRIVACY_AUTHORITY)
		self.assertEqual(localization.payment_modes(philippines), ["Cash", "Card", "Bank Transfer"])
		self.assertEqual(localization.instant_payment_modes(philippines), [])
		# GCash and Maya settle like a card. They are not a till bucket.
		self.assertNotIn("GCash", localization.payment_modes(philippines))
		self.assertNotIn("Maya", localization.payment_modes(philippines))
		for id_type in (
			"PhilSys National ID",
			"Passport",
			"Driver's License",
			"UMID",
			"SSS",
			"PRC",
			"PhilHealth",
			"Postal ID",
			"Senior Citizen ID",
			"PWD ID",
			"ACR I-Card",
		):
			self.assertIn(id_type, localization.id_types(philippines))
		self.assertNotIn("Aadhaar", localization.id_types(philippines))
		hints = localization.front_desk_vocabulary(philippines)["id_type_hints"]
		self.assertIn("OSCA", hints["Senior Citizen ID"])
		self.assertIn("PWD", hints["PWD ID"])
		self.assertEqual(
			localization.cash_denominations(philippines), [1000, 500, 200, 100, 50, 20, 10, 5, 1, 0.25, 0.05]
		)
		self.assertEqual(localization.invoice_title(philippines), "Invoice")
		self.assertFalse(hasattr(philippines, "ROOM_LEVY_LABEL"))

	def test_room_rate_is_flat_twelve_percent_for_any_tariff(self):
		for doc in (None, {}, {"tax_percent": None}, {"tax_percent": ""}, {"tax_percent": 0}):
			for tariff in (500, 5000, 10000):
				with self.subTest(doc=doc, tariff=tariff):
					self.assertEqual(philippines.calculate_room_tax("P", doc, tariff), Decimal("12"))

	def test_explicit_room_percent_is_preserved(self):
		# 3 is the non-VAT percentage tax. Any other non-zero percent is kept.
		for value in (3, 12, "12.00", Decimal("5")):
			self.assertEqual(
				philippines.calculate_room_tax("P", {"tax_percent": value}, 1000), Decimal(str(value))
			)

	def test_fnb_and_services_follow_the_room_rate_or_twelve(self):
		self.assertEqual(philippines.fnb_tax_rate(None), 12.0)
		self.assertEqual(localization.services_tax_rate(philippines, None), 12.0)
		with patch.object(philippines, "frappe") as framework:
			framework.get_all.return_value = []
			self.assertEqual(philippines.fnb_tax_rate("P"), 12.0)
			framework.get_all.assert_called_once()
		with patch.object(philippines, "frappe") as framework:
			framework.get_all.return_value = [0, 3]
			self.assertEqual(philippines.fnb_tax_rate("P"), 3.0)
			self.assertEqual(localization.services_tax_rate(philippines, "P"), 3.0)
		self.assertEqual(philippines.tax_rate_options("P"), [0, 3, 12])
		self.assertNotIn(1, philippines.tax_rate_options("P"))

	def test_senior_and_pwd_discount_strips_vat_then_takes_twenty_percent(self):
		# RR 5-2017 worked example: 1,120 inclusive -> 800 due, VAT-exempt.
		sale = philippines.senior_pwd_amounts("1120")
		self.assertEqual(sale["vat_inclusive"], Decimal("1120.00"))
		self.assertEqual(sale["vat"], Decimal("120.00"))
		self.assertEqual(sale["vat_exclusive"], Decimal("1000.00"))
		self.assertEqual(sale["discount_percent"], Decimal("20"))
		self.assertEqual(sale["discount"], Decimal("200.00"))
		self.assertEqual(sale["amount_due"], Decimal("800.00"))
		self.assertEqual(sale["tax_rate"], Decimal("0"))
		# RMC 38-2012 drugstore example, the same formula for a hotel charge.
		medicines = philippines.senior_pwd_amounts(Decimal("844.75"))
		self.assertEqual(medicines["vat"], Decimal("90.51"))
		self.assertEqual(medicines["vat_exclusive"], Decimal("754.24"))
		self.assertEqual(medicines["discount"], Decimal("150.85"))
		self.assertEqual(medicines["amount_due"], Decimal("603.39"))

	def test_invoice_context_handles_an_empty_property(self):
		ctx = philippines.invoice_context(frappe._dict(name=None))
		self.assertEqual(ctx["tax_label"], "VAT")
		self.assertEqual(ctx["tax_id_label"], "TIN")
		self.assertIsNone(ctx["place_of_supply"])
		self.assertIsNone(ctx["service_code"])
		self.assertEqual(ctx["split"], [("vat", Decimal("1"))])
		self.assertIn("VAT-exempt", ctx["footer"])
		self.assertIn("zero-rated", ctx["footer"])
		self.assertIn("TIN", ctx["footer"])
		self.assertIn("RA 9994", ctx["footer"])
		self.assertIn("non-VAT seller must not", ctx["footer"])
		self.assertEqual(
			philippines.invoice_context({"city": "Cebu", "state": "Cebu"})["place_of_supply"], "Cebu"
		)
		self.assertEqual(philippines.invoice_context({"state": "Cebu"})["place_of_supply"], "Cebu")

	def test_locale_uses_the_peso_sign_only_for_php(self):
		loc = philippines.locale({})
		self.assertEqual(loc["currency"], "PHP")
		self.assertEqual(loc["currency_symbol"], "₱")
		self.assertEqual(loc["locale"], "en-PH")
		self.assertEqual(loc["tax_id_label"], "TIN")
		self.assertEqual(loc["tax_rates"], [0, 3, 12])
		usd = philippines.locale({"currency": "USD", "name": "P"})
		self.assertEqual(usd["currency_symbol"], "USD ")
		self.assertEqual(usd["locale"], "en-PH")

	def test_amount_in_words_uses_pesos_and_sentimo(self):
		prop = frappe._dict(currency="PHP")
		self.assertEqual(
			localization.amount_in_words(philippines, prop, 1120),
			"Pesos One Thousand One Hundred Twenty Only",
		)
		self.assertEqual(
			localization.amount_in_words(philippines, prop, Decimal("12.50")),
			"Pesos Twelve and Fifty Sentimo Only",
		)

	def test_hook_resolves_philippines_without_changing_other_countries(self):
		self.assertEqual(hooks.kamra_localization["Philippines"], "kamra.localization.philippines")
		mapping = {key: [value] for key, value in hooks.kamra_localization.items()}
		with patch.object(localization.frappe, "get_hooks", return_value=mapping):
			self.assertIs(localization.pack_for_country("Philippines"), philippines)
			self.assertEqual(localization.pack_for_country("India").__name__, "kamra.localization.india")
			self.assertEqual(
				localization.pack_for_country("Indonesia").__name__, "kamra.localization.indonesia"
			)
			self.assertEqual(localization.pack_for_country("Unknown").__name__, "kamra.localization.generic")
			countries = {row["country"]: row for row in localization.supported_countries()}
			self.assertEqual(countries["Philippines"]["currency"], "PHP")
			self.assertEqual(countries["Philippines"]["timezone"], "Asia/Manila")
			self.assertEqual(countries["Philippines"]["tax_label"], "VAT")
			self.assertEqual(countries["Philippines"]["tax_id_label"], "TIN")

	def test_no_country_only_integrations(self):
		self.assertEqual(localization.payment_gateways(philippines), [])
		self.assertFalse(hasattr(philippines, "tax_return_rows"))
		self.assertFalse(hasattr(philippines, "on_invoice_issued"))
		self.assertFalse(hasattr(philippines, "verify_tax_id"))
