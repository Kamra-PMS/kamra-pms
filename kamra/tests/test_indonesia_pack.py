"""Indonesia's ways to pay, and the doctypes that have to store them; no
database writes.

QRIS is Indonesia's instant mode (as UPI is India's): the desk records it, the
POS settles with it and the till counts it in the instant column. Bank
Transfer is taken at the restaurant as well as the front desk."""

import importlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from kamra import hooks, localization
from kamra.localization import india, indonesia, thailand

DOCTYPES = Path(hooks.__file__).parent / "kamra" / "doctype"


def _options(doctype: str, fieldname: str) -> list[str]:
	"""A Select field's options, read from the doctype's JSON."""
	folder = frappe.scrub(doctype)
	fields = json.loads((DOCTYPES / folder / f"{folder}.json").read_text())["fields"]
	field = next(f for f in fields if f["fieldname"] == fieldname)
	return [o for o in field["options"].split("\n") if o]


def _packs():
	return [importlib.import_module(path)
	        for path in sorted(set(hooks.kamra_localization.values()))]


class TestIndonesiaPaymentModes(unittest.TestCase):
	def test_qris_is_the_instant_mode(self):
		self.assertEqual(localization.payment_modes(indonesia),
		                 ["Cash", "Card", "QRIS", "Bank Transfer"])
		self.assertEqual(localization.instant_payment_modes(indonesia), ["QRIS"])

	def test_the_restaurant_takes_every_way_to_pay(self):
		self.assertEqual(localization.outlet_payment_modes(indonesia),
		                 ["Cash", "Card", "QRIS", "Bank Transfer"])

	def test_bank_transfer_is_offered_at_the_outlet_in_every_pack(self):
		for pack in _packs():
			with self.subTest(pack=pack.__name__):
				self.assertIn("Bank Transfer", localization.outlet_payment_modes(pack))

	def test_qris_belongs_to_indonesia_alone(self):
		for pack in _packs():
			if pack is indonesia:
				continue
			with self.subTest(pack=pack.__name__):
				self.assertNotIn("QRIS", localization.payment_modes(pack))
				self.assertNotIn("QRIS", localization.outlet_payment_modes(pack))

	def test_qris_is_refused_where_the_pack_has_none(self):
		from kamra import cashier, pos
		for pack in (india, thailand):
			with self.subTest(pack=pack.__name__), \
					patch.object(localization, "pack_for", return_value=pack):
				with self.assertRaises(frappe.ValidationError):
					localization.assert_payment_mode("P", "QRIS")
				with self.assertRaises(frappe.ValidationError):
					cashier.record_cashier_txn("P", "Payment", "QRIS", 100)
				with self.assertRaises(frappe.ValidationError):
					pos._assert_outlet_mode("P", "QRIS")
		with patch.object(localization, "pack_for", return_value=indonesia):
			localization.assert_payment_mode("P", "QRIS")
			pos._assert_outlet_mode("P", "QRIS")

	def test_bank_transfer_settles_a_bill_at_the_outlet(self):
		from kamra import pos
		with patch.object(localization, "pack_for", return_value=thailand):
			pos._assert_outlet_mode("P", "Bank Transfer")


class TestModesFitTheirDoctypes(unittest.TestCase):
	"""A mode a pack offers has to be an option on the field that stores it,
	or saving the payment fails. The POS list was once held to Cash, Card and
	UPI for that reason."""

	def test_what_the_desk_and_the_till_record(self):
		for pack in _packs():
			for doctype in ("Folio Payment", "Cashier Transaction"):
				with self.subTest(pack=pack.__name__, doctype=doctype):
					options = _options(doctype, "mode")
					for mode in localization.payment_modes(pack):
						self.assertIn(mode, options)

	def test_what_a_banquet_receipt_records(self):
		for pack in _packs():
			with self.subTest(pack=pack.__name__):
				options = _options("Banquet Receipt", "mode")
				for mode in (*localization.payment_modes(pack),
				             *localization.instant_payment_modes(pack)):
					self.assertIn(mode, options)

	def test_what_a_settled_outlet_bill_records(self):
		for pack in _packs():
			with self.subTest(pack=pack.__name__):
				options = _options("POS Order", "payment_mode")
				for mode in localization.outlet_payment_modes(pack):
					self.assertIn(mode, options)
