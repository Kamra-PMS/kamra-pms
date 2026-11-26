"""Settings → Languages: who may switch a UI language off, and what a
disabled booking language does to guests and the property record."""

from __future__ import annotations

import json

import frappe
from frappe.tests import IntegrationTestCase

from kamra import languages
from kamra.tests.audit_fixtures import ensure_user
from kamra.ui_languages import BASE


class UiLanguagesTest(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		frappe.local.lang = "en"
		self._prior = frappe.db.get_default(languages.DISABLED_KEY)
		frappe.db.set_default(languages.DISABLED_KEY, "[]")
		self.admin = ensure_user("ut.langs.admin@example.com", ["Hotel Admin"])
		self.desk = ensure_user("ut.langs.desk@example.com", ["Front Desk"])
		self.property = frappe.get_doc({
			"doctype": "Property",
			"property_name": "UT Lang " + frappe.generate_hash(length=6),
			"booking_engine_enabled": 1,
			"booking_language": "es",
		}).insert(ignore_permissions=True).name

	def tearDown(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- restore the test user
		super().tearDown()
		# set_default is cached in-process; the rollback put the row back,
		# so drop the cache or the next test still sees this list.
		frappe.clear_cache()
		if hasattr(frappe.local, "defaults"):
			del frappe.local.defaults

	def test_default_offers_every_shipped_language_and_english_stays_on(self):
		frappe.set_user("Guest")  # nosemgrep: frappe-setuser -- the login screen reads this as a guest
		offered = languages.enabled_ui_languages()["enabled"]
		self.assertEqual(offered[0], BASE)
		self.assertEqual(offered, languages.known_codes())
		for code in ("en", "es", "pt", "ar", "de", "id", "fil", "vi", "sw", "hi", "ta", "zh-CN"):
			self.assertIn(code, offered)

		frappe.set_user(self.admin)  # nosemgrep: frappe-setuser -- Hotel Admin may change the list
		saved = languages.set_disabled_ui_languages(["en", "ar", "ar"])
		self.assertIn("en", saved["enabled"])
		self.assertNotIn("ar", saved["enabled"])
		self.assertEqual(saved["disabled"], ["ar"])
		self.assertEqual(json.loads(frappe.db.get_default(languages.DISABLED_KEY)), ["ar"])

	def test_front_desk_cannot_change_the_list_and_unknown_codes_are_refused(self):
		frappe.set_user(self.desk)  # nosemgrep: frappe-setuser -- a desk user must not pass the admin gate
		with self.assertRaises(frappe.PermissionError):
			languages.set_disabled_ui_languages(["es"])
		self.assertEqual(json.loads(frappe.db.get_default(languages.DISABLED_KEY) or "[]"), [])

		frappe.set_user(self.admin)  # nosemgrep: frappe-setuser -- Hotel Admin may change the list
		with self.assertRaises(frappe.ValidationError):
			languages.set_disabled_ui_languages(["zz"])
		with self.assertRaises(frappe.ValidationError):
			languages.set_disabled_ui_languages("nope")

	def test_saving_a_disabled_booking_language_is_refused_and_an_old_value_still_saves(self):
		frappe.set_user(self.admin)  # nosemgrep: frappe-setuser -- Hotel Admin may change the list
		languages.set_disabled_ui_languages(["es"])

		doc = frappe.get_doc("Property", self.property)
		doc.meta_title = "Still open"
		doc.save(ignore_permissions=True)
		self.assertEqual(doc.booking_language, "es")
		self.assertEqual(doc.meta_title, "Still open")

		doc.booking_language = "es"
		doc.save(ignore_permissions=True)

		doc.booking_language = "pt"
		doc.save(ignore_permissions=True)
		self.assertEqual(doc.booking_language, "pt")

		doc.booking_language = "es"
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)
		doc.booking_language = "zz"
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)

		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc({
				"doctype": "Property",
				"property_name": "UT Lang Off " + frappe.generate_hash(length=4),
				"booking_language": "es",
			}).insert(ignore_permissions=True)

		languages.set_disabled_ui_languages([])
		doc.reload()
		doc.booking_language = "ES"
		doc.save(ignore_permissions=True)
		self.assertEqual(doc.booking_language, "es")

	def test_guests_are_not_shown_a_disabled_booking_language(self):
		from kamra.apps import property_profile
		from kamra.booking_slugs import slugify
		from kamra.public_api import _public_locale
		from kamra.www.kamra import _guest_meta

		frappe.db.set_value("Property", self.property, "booking_language", "es")
		frappe.set_user(self.admin)  # nosemgrep: frappe-setuser -- Hotel Admin may change the list
		languages.set_disabled_ui_languages(["es"])

		locale = _public_locale(self.property)
		self.assertIsNone(locale["default_language"])
		self.assertIn("en", locale["enabled_languages"])
		self.assertNotIn("es", locale["enabled_languages"])
		self.assertEqual(languages.resolve_saved("es", "pt"), "pt")
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- read the profile as the site admin

		slug = slugify(frappe.db.get_value("Property", self.property, "property_name"))
		frappe.form_dict.property = slug
		try:
			meta = _guest_meta(None)
		finally:
			frappe.form_dict.pop("property", None)
		self.assertTrue(meta)
		self.assertFalse(meta.get("lang"))

		self.assertEqual(property_profile(self.property)["language"], "en")
