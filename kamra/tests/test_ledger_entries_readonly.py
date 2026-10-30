"""Ledger entries are written only by Kamra's money code (it posts with
ignore_permissions). No business role may create, change or delete one
through Desk or /api/resource: that would let a balance be edited by hand."""

from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase


class LedgerEntriesReadOnlyTestCase(IntegrationTestCase):
	def test_business_roles_only_read_ledger_entries(self):
		for doctype in ("Folio Ledger Entry", "City Ledger Entry", "Credit Note"):
			perms = frappe.get_meta(doctype).permissions
			for p in perms:
				if p.role == "System Manager":
					continue
				self.assertTrue(p.read, (doctype, p.role))
				self.assertFalse(p.write or p.create or p.delete, (doctype, p.role))

	def test_patch_strips_custom_docperm_writes(self):
		"""A Role Permission Manager edit leaves Custom DocPerms that
		override the JSON; the patch drops their write grants."""
		from kamra.patches.v46.ledger_custom_perms_readonly import execute

		rows = []
		for role in ("Front Desk", "System Manager"):
			rows.append(frappe.get_doc({
				"doctype": "Custom DocPerm", "parent": "Credit Note",
				"parenttype": "DocType", "parentfield": "permissions",
				"role": role, "permlevel": 0, "read": 1, "write": 1,
				"create": 1, "delete": 1}).insert(ignore_permissions=True))
		try:
			execute()
			fd = frappe.db.get_value("Custom DocPerm", rows[0].name,
			                         ["read", "write", "create", "delete"], as_dict=True)
			self.assertEqual((fd.read, fd.write, fd.create, fd.delete), (1, 0, 0, 0))
			self.assertEqual(frappe.db.get_value("Custom DocPerm", rows[1].name, "write"), 1)
		finally:
			for r in rows:
				frappe.db.delete("Custom DocPerm", r.name)
			frappe.clear_cache(doctype="Credit Note")
