"""Ledger entries and credit notes are written only by Kamra's money code
(ignore_permissions). Sites that edited these doctypes in Role Permission
Manager carry Custom DocPerms that replace the JSON perms, so strip the
write grants there too. System Manager keeps full access."""

from __future__ import annotations

import frappe

DOCTYPES = ("Folio Ledger Entry", "City Ledger Entry", "Credit Note")
FLAGS = ("write", "create", "delete", "submit", "cancel", "amend")


def execute():
	frappe.db.sql(
		f"""UPDATE `tabCustom DocPerm`
		SET {", ".join(f"`{f}` = 0" for f in FLAGS)}
		WHERE parent IN %(doctypes)s AND role != 'System Manager'""",
		{"doctypes": DOCTYPES})
	for dt in DOCTYPES:
		frappe.clear_cache(doctype=dt)
