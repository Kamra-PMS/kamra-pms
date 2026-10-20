# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Go-live import (kamra.golive): the parts that need no database - amount
parsing, the companies file, the idempotency keys and the role gate. The
posting, idempotency and reconciliation paths run end to end in the eval
harness (t220-t224)."""

import unittest
from unittest.mock import patch

import frappe

from kamra import golive, migrate


class TestAmounts(unittest.TestCase):
	def test_formats(self):
		self.assertEqual(golive._amount("12,600.00"), 12600.0)
		self.assertEqual(golive._amount("(2,000)"), -2000.0)
		self.assertEqual(golive._amount("-450.5"), -450.5)
		self.assertEqual(golive._amount("SAR 300"), 300.0)
		self.assertEqual(golive._amount("0"), 0.0)
		self.assertIsNone(golive._amount("  "))

	def test_garbage_is_refused(self):
		with self.assertRaises(ValueError):
			golive._amount("n/a")
		with self.assertRaises(ValueError):
			golive._amount("1.2.3")


class TestCompaniesFile(unittest.TestCase):
	def test_credit_terms_and_issues(self):
		csv = ("Company,GSTIN,Credit Limit,Credit Allowed\n"
		       "Acme,29AAA,\"50,000\",\n"      # a limit implies credit
		       "Cash Co,,,No\n"
		       "acme,,,Yes\n"                  # listed twice
		       "Bad Co,,-5,\n")
		_h, mapping, rows, issues = golive._normalize_companies(csv)
		self.assertEqual(mapping["tax_id"], "GSTIN")
		self.assertEqual([r["company_name"] for r in rows], ["Acme", "Cash Co"])
		self.assertTrue(rows[0]["credit_allowed"])
		self.assertEqual(rows[0]["credit_limit"], 50000)
		self.assertFalse(rows[1]["credit_allowed"])
		self.assertEqual([i["row"] for i in issues], [3, 4])

	def test_credit_days_column(self):
		csv = ("Company Name,Credit Limit,Payment Terms\n"
		       "Acme,10000,Net 45\n"
		       "Beta,5000,\n"                   # blank = property default
		       "Gamma,5000,30 days\n"
		       "Cash Terms,5000,0\n"            # due on receipt
		       "COD Co,5000,On receipt\n"
		       "Delta,5000,forever\n")
		_h, mapping, rows, issues = golive._normalize_companies(csv)
		self.assertEqual(mapping["credit_days"], "Payment Terms")
		self.assertEqual([(r["company_name"], r["credit_days"]) for r in rows],
		                 [("Acme", 45), ("Beta", None), ("Gamma", 30),
		                  ("Cash Terms", 0), ("COD Co", 0)])
		self.assertEqual([i["row"] for i in issues], [6])
		self.assertIn("Credit Days", golive.TEMPLATES["companies"][1])

	def test_missing_name_column(self):
		_h, _m, rows, issues = golive._normalize_companies("Phone\n123\n")
		self.assertEqual(rows, [])
		self.assertIn("Company Name", issues[0]["error"])


class TestKeys(unittest.TestCase):
	def test_import_key_is_stable(self):
		row = {"guest_name": "A", "room_type": "P-DLX",
		       "check_in": "2026-10-01", "check_out": "2026-10-03"}
		self.assertEqual(migrate.import_key(row), migrate.import_key(dict(row)))
		self.assertTrue(migrate.import_key(row).startswith("import:auto:"))
		self.assertEqual(migrate.import_key({**row, "reservation_no": "R-9"}),
		                 "import:R-9")

	def test_ar_key_by_invoice(self):
		a = {"company": "Acme Ltd", "invoice_no": "INV-1", "amount": 10}
		b = {"company": "ACME LTD", "invoice_no": "INV-1", "amount": 99}
		c = {"company": "Acme Ltd", "invoice_no": "INV-2", "amount": 10}
		self.assertEqual(golive._ar_key(a), golive._ar_key(b))
		self.assertNotEqual(golive._ar_key(a), golive._ar_key(c))


class TestRoleGate(unittest.TestCase):
	def test_finance_only(self):
		for fn in (golive.run_opening, golive.preview_opening,
		           golive.run_companies, golive.preview_companies,
		           golive.reconcile, golive.csv_template):
			self.assertEqual(
				fn._kamra_roles,
				{"Finance", "Hotel Admin", "System Manager", "Administrator"},
				fn.__name__)

	def test_front_desk_refused(self):
		with patch("frappe.get_roles", return_value=["Front Desk"]):
			with self.assertRaises(frappe.PermissionError):
				golive.run_opening("P", "Type,Amount\nIn-house,1\n")
