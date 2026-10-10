# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""validate_voucher: limits apply to new use, not to re-pricing a saved booking."""

from unittest.mock import patch

import frappe
import unittest

from kamra.pricing import validate_voucher


def _voucher(**kw):
	base = dict(voucher_code="V1", disabled=0, valid_from=None, valid_to=None,
	            max_uses=0, times_used=0, min_nights=1)
	base.update(kw)
	return frappe._dict(base)


def _run(voucher, **kw):
	with patch("kamra.pricing.frappe.db.get_value", return_value="V1"), \
	     patch("kamra.pricing.frappe.get_doc", return_value=voucher):
		return validate_voucher("P", "v1", 2, **kw)


class TestVoucherLimits(unittest.TestCase):
	def test_expired_voucher_rejected(self):
		with self.assertRaisesRegex(frappe.ValidationError, "expired"):
			_run(_voucher(valid_to="2000-01-01"))

	def test_not_started_voucher_rejected(self):
		with self.assertRaisesRegex(frappe.ValidationError, "starts on"):
			_run(_voucher(valid_from="2999-01-01"))

	def test_used_up_voucher_rejected(self):
		with self.assertRaisesRegex(frappe.ValidationError, "fully redeemed"):
			_run(_voucher(max_uses=1, times_used=1))

	def test_saved_booking_keeps_used_up_voucher(self):
		self.assertTrue(_run(_voucher(max_uses=1, times_used=1), check_limits=False))

	def test_saved_booking_keeps_expired_voucher(self):
		self.assertTrue(
			_run(_voucher(valid_to="2000-01-01", disabled=1), check_limits=False))

	def test_min_nights_still_applies_without_limits(self):
		with self.assertRaisesRegex(frappe.ValidationError, "at least"):
			_run(_voucher(min_nights=5), check_limits=False)
