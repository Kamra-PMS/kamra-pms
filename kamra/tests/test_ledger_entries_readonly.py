"""Ledger entries are written only by Kamra's money code (it posts with
ignore_permissions). No business role may create, change or delete one
through Desk or /api/resource: that would let a balance be edited by hand."""

from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase


class LedgerEntriesReadOnlyTestCase(IntegrationTestCase):
	def test_business_roles_only_read_ledger_entries(self):
		for doctype in ("Folio Ledger Entry", "City Ledger Entry"):
			perms = frappe.get_meta(doctype).permissions
			for p in perms:
				if p.role == "System Manager":
					continue
				self.assertTrue(p.read, (doctype, p.role))
				self.assertFalse(p.write or p.create or p.delete, (doctype, p.role))
