"""Core is country-neutral: currency fallbacks and money in server text come
from the property's pack, so a non-India property never sees INR or a rupee
sign, and an India property reads exactly as before."""

import unittest
from unittest.mock import patch

import frappe

from kamra import localization
from kamra.kamra.doctype.folio.folio import Folio
from kamra.localization import generic, india


def _prop(currency):
	return frappe._dict(name="P", currency=currency)


class TestCountryNeutralCore(unittest.TestCase):
	def test_default_currency_comes_from_the_pack(self):
		self.assertEqual(localization.default_currency(india), "INR")
		self.assertEqual(localization.default_currency(generic), "USD")

	def test_money_text_uses_the_property_currency(self):
		with patch.object(frappe, "get_cached_doc", return_value=_prop("AED")), \
				patch.object(frappe.db, "get_value", return_value="AED "), \
				patch.object(localization, "pack_for", return_value=generic):
			text = localization.money_text("P", 1500)
		self.assertEqual(text, "AED 1,500")
		with patch.object(frappe, "get_cached_doc", return_value=_prop("INR")), \
				patch.object(localization, "pack_for", return_value=india):
			self.assertEqual(localization.money_text("P", 1500), "₹1,500")

	def test_payment_row_currency_falls_back_to_the_pack(self):
		for pack, expected in ((generic, "USD"), (india, "INR")):
			row = frappe._dict(currency=None)
			fake = frappe._dict(property="P", payments=[row])
			with self.subTest(pack=pack.__name__), \
					patch.object(frappe, "get_cached_value", return_value=None), \
					patch.object(localization, "pack_for", return_value=pack):
				Folio.stamp_payment_currency(fake)
			self.assertEqual(row.currency, expected)

	def test_voucher_note_has_no_rupee_outside_india(self):
		from kamra import public_api
		v = frappe._dict(value=500, discount_type="Amount", voucher_code="SUMMER")
		with patch("kamra.pricing.validate_voucher", return_value=v), \
				patch.object(localization, "money_text", return_value="AED 500"):
			out = public_api.check_voucher("P", "SUMMER")
		self.assertIn("AED 500 off", out["message"])
		self.assertNotIn("₹", out["message"])

	def test_india_specifics_live_in_the_india_pack(self):
		self.assertIn("Aadhaar", localization.front_desk_vocabulary(india)["id_type_hints"])
		self.assertEqual(localization.front_desk_vocabulary(generic)["id_type_hints"], {})
		self.assertIn("GST", localization.invoice_tax_note(india))
		self.assertEqual(localization.invoice_tax_note(generic), "")

	def test_instant_modes_come_from_the_pack(self):
		from kamra.localization import saudi, thailand
		self.assertIn("UPI", localization.payment_modes(india))
		self.assertEqual(localization.outlet_payment_modes(india), ["Cash", "Card", "UPI"])
		for pack in (saudi, thailand, generic):
			with self.subTest(pack=pack.__name__):
				self.assertNotIn("UPI", localization.payment_modes(pack))
				self.assertEqual(localization.instant_payment_modes(pack), [])
				self.assertEqual(localization.outlet_payment_modes(pack), ["Cash", "Card"])
		from kamra import zatca
		self.assertNotIn("UPI", zatca.PAYMENT_MEANS)

	def test_a_country_mode_is_refused_where_the_pack_has_none(self):
		from kamra import cashier, pos
		from kamra.localization import thailand
		with patch.object(localization, "pack_for", return_value=thailand):
			for mode in ("Cash", "Card", "Payment Link", "OTA Prepaid", None):
				localization.assert_payment_mode("P", mode)
			with self.assertRaises(frappe.ValidationError):
				localization.assert_payment_mode("P", "UPI")
			# the shared writers: the till (every folio, POS and refund
			# payment lands there) and the outlet's settle check
			with self.assertRaises(frappe.ValidationError):
				cashier.record_cashier_txn("P", "Payment", "UPI", 100)
			with self.assertRaises(frappe.ValidationError):
				pos._assert_outlet_mode("P", "UPI")
		with patch.object(localization, "pack_for", return_value=india):
			localization.assert_payment_mode("P", "UPI")
			pos._assert_outlet_mode("P", "UPI")
