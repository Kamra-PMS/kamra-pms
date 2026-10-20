"""Auto KOT moved from a per-outlet checkbox (`auto_kot`) to an F&B setting
that each outlet can override (`kot_mode`). An outlet that had the box
ticked keeps auto KOT by being set to "Auto-accept and print"; the rest
follow the F&B setting, which defaults to off - so nothing changes on the
floor after the upgrade.

Idempotent: only outlets still on the default are touched."""

import frappe


def execute():
	if not frappe.db.has_column("POS Outlet", "auto_kot"):
		return
	frappe.db.sql(
		"""update `tabPOS Outlet` set kot_mode = 'Auto-accept and print'
		   where auto_kot = 1
		     and ifnull(kot_mode, '') in ('', 'Use F&B setting')""")
	frappe.db.sql(
		"""update `tabPOS Outlet` set kot_mode = 'Use F&B setting'
		   where ifnull(kot_mode, '') = ''""")
