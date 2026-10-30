"""Public SPA metadata follows native Website Settings, not a second brand."""

import unittest
from unittest.mock import patch

import frappe


class SiteBrandingTestCase(unittest.TestCase):
	def test_public_metadata_uses_native_website_branding(self):
		from kamra.public_api import site_info

		values = {"app_name": "Example Hotels", "app_logo": "/files/example.svg"}
		with patch.object(frappe, "get_website_settings", side_effect=values.get):
			info = site_info()
		self.assertEqual(info.get("app_name"), "Example Hotels")
		self.assertEqual(info.get("app_logo"), "/files/example.svg")
		self.assertEqual(info["app"], "kamra")

	def test_unset_branding_leaves_the_client_default_available(self):
		from kamra.public_api import site_info

		with patch.object(frappe, "get_website_settings", return_value=None):
			info = site_info()
		self.assertIsNone(info.get("app_name"))
		self.assertIsNone(info.get("app_logo"))
		self.assertIn("version", info)
