"""Germany defaults and the localization seam; no database writes."""

from decimal import Decimal
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

import frappe

from kamra import hooks, localization
from kamra.localization import germany  # noqa: F401 — exercised via hooks


class TestGermanyPack(unittest.TestCase):
	def test_regional_defaults(self):
		self.assertEqual(germany.DEFAULT_CURRENCY, "EUR")
		self.assertEqual(germany.DEFAULT_TIMEZONE, "Europe/Berlin")
		self.assertEqual(ZoneInfo(germany.DEFAULT_TIMEZONE).key, "Europe/Berlin")
		self.assertEqual(germany.DEFAULT_NATIONALITY, "German")
		self.assertEqual(germany.HOME_COUNTRY_ISO3, "DEU")
		self.assertEqual(localization.payment_modes(germany), ["Cash", "Card", "Bank Transfer"])
		self.assertIn("Personalausweis", localization.id_types(germany))
		self.assertNotIn("Aadhaar", localization.id_types(germany))
		self.assertEqual(germany.ROOM_LEVY_LABEL, "City tax")
		self.assertEqual(germany.NOTICE_LANGUAGES, ["de", "en"])

	def test_room_reduced_rate_when_unset(self):
		for doc in (None, {}, {"tax_percent": None}, {"tax_percent": ""}):
			for tariff in (80, 120, 250):
				with self.subTest(doc=doc, tariff=tariff):
					self.assertEqual(germany.calculate_room_tax("P", doc, tariff), Decimal("7"))

	def test_explicit_room_percent_is_preserved(self):
		# same contract as UAE/Malaysia: a blank/zero Percent falls back to 7%
		for value in (7, 19, "7.00", Decimal("19")):
			self.assertEqual(
				germany.calculate_room_tax("P", {"tax_percent": value}, 100),
				Decimal(str(value)),
			)

	def test_fnb_and_services_use_standard_rate(self):
		self.assertEqual(germany.fnb_tax_rate("P"), 19.0)
		self.assertEqual(germany.services_tax_rate("P"), 19.0)
		self.assertEqual(localization.services_tax_rate(germany, "P"), 19.0)
		self.assertEqual(germany.tax_rate_options("P"), [0, 7, 19])

	def test_invoice_context(self):
		ctx = germany.invoice_context(frappe._dict(name=None))
		self.assertEqual(ctx["tax_label"], "MwSt (Umsatzsteuer)")
		self.assertEqual(ctx["tax_id_label"], "USt-IdNr.")
		self.assertIsNone(ctx["place_of_supply"])
		self.assertEqual(ctx["split"], [("mwst", Decimal("1"))])
		self.assertIn("Übernachtungssteuer", ctx["footer"])
		self.assertEqual(
			germany.invoice_context({"city": "Berlin", "state": "BE"})["place_of_supply"],
			"Berlin",
		)

	def test_locale_eur_defaults(self):
		loc = germany.locale({"currency": None})
		self.assertEqual(loc["currency"], "EUR")
		self.assertEqual(loc["currency_symbol"], "€")
		self.assertEqual(loc["locale"], "de-DE")
		self.assertEqual(loc["tax_label"], "MwSt")
		self.assertEqual(loc["tax_id_label"], "USt-IdNr.")
		# symbol stays the pack's € even if the property bills another code
		self.assertEqual(germany.locale({"currency": "USD"})["currency_symbol"], "€")
		self.assertEqual(germany.locale({"currency": "USD"})["currency"], "USD")

	def test_hook_resolves_germany(self):
		self.assertEqual(hooks.kamra_localization["Germany"], "kamra.localization.germany")
		mapping = {key: [value] for key, value in hooks.kamra_localization.items()}
		with patch.object(localization.frappe, "get_hooks", return_value=mapping):
			self.assertIs(localization.pack_for_country("Germany"), germany)
			self.assertEqual(localization.pack_for_country("India").__name__, "kamra.localization.india")
			countries = {row["country"]: row for row in localization.supported_countries()}
			self.assertEqual(countries["Germany"]["currency"], "EUR")
			self.assertEqual(countries["Germany"]["tax_id_label"], "USt-IdNr.")

	def test_no_automatic_city_tax_or_integrations(self):
		self.assertEqual(germany.ROOM_LEVY_LABEL, "City tax")
		self.assertEqual(localization.payment_gateways(germany), [])
		self.assertFalse(hasattr(germany, "tax_return_rows"))
		self.assertFalse(hasattr(germany, "on_invoice_issued"))
