"""Catalog and fallback rules. No site: these do not import Frappe."""

from __future__ import annotations

import unittest

from kamra.ui_languages import (
	BASE,
	CATALOG_PATH,
	UnknownLanguage,
	clean_requested_disabled,
	enabled_list,
	language_label,
	load_catalog,
	parse_stored_disabled,
	resolve_language,
)


class UiLanguageLogicTest(unittest.TestCase):
	def test_shipped_catalog_starts_with_english_and_marks_arabic_rtl(self):
		rows = load_catalog()
		codes = [row["code"] for row in rows]
		self.assertEqual(codes[0], BASE)
		self.assertIn("es", codes)
		self.assertIn("pt", codes)
		self.assertIn("ar", codes)
		self.assertIn("de", codes)
		self.assertIn("id", codes)
		self.assertIn("fil", codes)
		self.assertIn("zh-CN", codes)
		self.assertTrue(CATALOG_PATH.is_file())
		arabic = next(row for row in rows if row["code"] == "ar")
		self.assertEqual(arabic["dir"], "rtl")
		self.assertEqual(language_label("es", rows), "Spanish")
		self.assertEqual(language_label("nope", rows), "nope")

	def test_missing_storage_enables_every_language_including_a_new_one(self):
		known = ["en", "es", "pt", "ar", "id"]
		self.assertEqual(parse_stored_disabled(None, known), [])
		self.assertEqual(parse_stored_disabled("", known), [])
		self.assertEqual(parse_stored_disabled("not-json", known), [])
		self.assertEqual(enabled_list(known, []), known)

	def test_stored_list_drops_english_unknown_and_removed_codes(self):
		known = ["en", "es", "pt", "ar"]
		self.assertEqual(
			parse_stored_disabled(["en", "es", "zz", "", "es"], known),
			["es"],
		)
		self.assertEqual(parse_stored_disabled('["pt", "fil"]', known), ["pt"])

	def test_a_new_language_stays_on_when_it_is_not_in_the_disabled_list(self):
		# id is registered after es was switched off: it is on, es stays off
		self.assertEqual(enabled_list(["en", "es", "pt", "ar", "id"], ["es"]),
		                 ["en", "pt", "ar", "id"])

	def test_save_refuses_an_unknown_code_and_cannot_disable_english(self):
		known = ["en", "es", "pt", "ar"]
		self.assertEqual(clean_requested_disabled(["en", "ar", "ar"], known), ["ar"])
		self.assertEqual(clean_requested_disabled("[]", known), [])
		with self.assertRaises(UnknownLanguage) as caught:
			clean_requested_disabled(["zz"], known)
		self.assertEqual(caught.exception.code, "zz")
		with self.assertRaises(UnknownLanguage):
			clean_requested_disabled({"es": False}, known)

	def test_resolve_falls_back_to_the_property_default_then_english(self):
		enabled = ["en", "pt"]
		self.assertEqual(resolve_language("es", enabled, "pt"), "pt")
		self.assertEqual(resolve_language("es", enabled, "ar"), "en")
		self.assertEqual(resolve_language("pt", enabled, "en"), "pt")
		self.assertEqual(resolve_language(None, enabled), "en")
		self.assertEqual(resolve_language("ES", ["en", "es"]), "es")


if __name__ == "__main__":
	unittest.main()
