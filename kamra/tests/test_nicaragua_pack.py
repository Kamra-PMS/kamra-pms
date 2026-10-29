"""Nicaragua defaults and the localization seam; no database writes."""

from decimal import Decimal
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

import frappe

from kamra import hooks, localization
from kamra.localization import nicaragua


class TestNicaraguaPack(unittest.TestCase):
	def test_regional_defaults(self):
		self.assertEqual(nicaragua.DEFAULT_CURRENCY, "NIO")
		self.assertEqual(nicaragua.DEFAULT_TIMEZONE, "America/Managua")
		self.assertEqual(ZoneInfo(nicaragua.DEFAULT_TIMEZONE).key, "America/Managua")
		self.assertEqual(nicaragua.DEFAULT_NATIONALITY, "Nicaraguan")
		self.assertEqual(localization.payment_modes(nicaragua), ["Cash", "Card", "Bank Transfer"])
		self.assertIn("Residence Card", localization.id_types(nicaragua))
		self.assertNotIn("Aadhaar", localization.id_types(nicaragua))

	def test_room_standard_rate_for_empty_percent_and_any_tariff(self):
		# Frappe stores a blank Percent as zero, as in the other flat-tax packs.
		for doc in (None, {}, {"tax_percent": None}, {"tax_percent": ""}, {"tax_percent": 0}):
			for tariff in (500, 5000, 10000):
				with self.subTest(doc=doc, tariff=tariff):
					self.assertEqual(nicaragua.calculate_room_tax("P", doc, tariff), Decimal("15"))

	def test_existing_property_rate_is_kept(self):
		# a property set up under the generic pack keeps its gst_rate_low
		with patch.object(nicaragua, "frappe") as framework:
			framework.db.get_value.return_value = 10
			self.assertEqual(nicaragua.calculate_room_tax("P", {"tax_percent": 0}, 1000), Decimal("10"))
			self.assertEqual(nicaragua.fnb_tax_rate("P"), 10.0)
			self.assertEqual(nicaragua.calculate_room_tax("P", {"tax_percent": 12}, 1000), Decimal("12"))

	def test_explicit_nonzero_room_percent_is_preserved(self):
		for value in (10, 12.5, "15.00", Decimal("18")):
			self.assertEqual(nicaragua.calculate_room_tax("P", {"tax_percent": value}, 1000), Decimal(str(value)))

	def test_fnb_and_services_do_not_inherit_room_overrides(self):
		with patch.object(nicaragua, "frappe") as framework:
			framework.db.get_value.return_value = 0
			self.assertEqual(nicaragua.fnb_tax_rate("P"), 15.0)
			self.assertEqual(localization.services_tax_rate(nicaragua, "P"), 15.0)
			framework.get_all.assert_not_called()
		self.assertEqual(nicaragua.tax_rate_options("P"), [0, 15])

	def test_invoice_context_handles_empty_property_and_uses_single_iva(self):
		ctx = nicaragua.invoice_context(frappe._dict(name=None))
		self.assertEqual(ctx["tax_label"], "IVA")
		self.assertEqual(ctx["tax_id_label"], "RUC")
		self.assertIsNone(ctx["place_of_supply"])
		self.assertIsNone(ctx["service_code"])
		self.assertEqual(ctx["split"], [("iva", Decimal("1"))])
		self.assertEqual(nicaragua.invoice_context({"city": "Rivas", "state": "Rivas"})["place_of_supply"], "Rivas")
		self.assertEqual(nicaragua.invoice_context({"state": "Rivas"})["place_of_supply"], "Rivas")

	def test_currency_defaults_and_configured_symbols(self):
		for currency, symbol, expected in ((None, None, "C$"), ("NIO", "C$", "C$"),
		                                 ("NIO", "custom C$", "custom C$"),
		                                 ("NIO", " ", "C$"), ("USD", "$", "$"),
		                                 ("USD", None, "USD "), ("EUR", "€", "€")):
			with self.subTest(currency=currency, symbol=symbol), patch.object(nicaragua, "frappe") as framework:
				framework.db.get_value.return_value = symbol
				loc = nicaragua.locale({"currency": currency})
				self.assertEqual(loc["currency"], currency or "NIO")
				self.assertEqual(loc["currency_symbol"], expected)
				self.assertEqual(loc["locale"], "es-NI")
				framework.db.get_value.assert_called_once_with("Currency", currency or "NIO", "symbol")

	def test_hook_resolves_nicaragua_without_changing_other_countries(self):
		self.assertEqual(hooks.kamra_localization["Nicaragua"], "kamra.localization.nicaragua")
		mapping = {key: [value] for key, value in hooks.kamra_localization.items()}
		with patch.object(localization.frappe, "get_hooks", return_value=mapping):
			self.assertIs(localization.pack_for_country("Nicaragua"), nicaragua)
			self.assertEqual(localization.pack_for_country("India").__name__, "kamra.localization.india")
			self.assertEqual(localization.pack_for_country("Brazil").__name__, "kamra.localization.brazil")
			self.assertEqual(localization.pack_for_country("Unknown").__name__, "kamra.localization.generic")
			countries = {row["country"]: row for row in localization.supported_countries()}
			self.assertEqual(countries["Nicaragua"]["currency"], "NIO")
			self.assertEqual(countries["Nicaragua"]["tax_id_label"], "RUC")

	def test_no_automatic_levy_or_country_only_integrations(self):
		self.assertEqual(nicaragua.ROOM_LEVY_LABEL, "INTUR")
		self.assertNotIn(17, nicaragua.tax_rate_options("P"))
		self.assertEqual(localization.payment_gateways(nicaragua), [])
		self.assertFalse(hasattr(nicaragua, "tax_return_rows"))
		self.assertFalse(hasattr(nicaragua, "on_invoice_issued"))
