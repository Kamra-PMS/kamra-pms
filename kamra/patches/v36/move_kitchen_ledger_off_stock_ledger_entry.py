"""Kamra's kitchen ledger used to be a DocType named "Stock Ledger Entry",
the same name as ERPNext's core stock ledger. DocType names are global, so on
a site with ERPNext one definition overwrote the other and every Purchase
Invoice / Stock Entry demanded Property, Outlet and Ingredient (issue #131).

The ledger is now "Ingredient Ledger Entry". This copies the kitchen rows
across, then hands "Stock Ledger Entry" back to ERPNext - or drops it when
ERPNext is not installed. Rows without an ingredient are ERPNext's and are
never touched.
"""

import frappe

OLD = "Stock Ledger Entry"
NEW = "Ingredient Ledger Entry"


def execute():
	if not frappe.db.table_exists(OLD) or not frappe.db.has_column(OLD, "ingredient"):
		return

	frappe.reload_doc("kamra", "doctype", "ingredient_ledger_entry")
	cols = sorted(set(frappe.db.get_table_columns(OLD)) & set(frappe.db.get_table_columns(NEW)))
	col_sql = ", ".join(f"`{c}`" for c in cols)
	kitchen = "`ingredient` IS NOT NULL AND `ingredient` != ''"

	frappe.db.sql(
		f"INSERT IGNORE INTO `tab{NEW}` ({col_sql}) "  # nosemgrep: frappe-sql-format-injection -- column names come from the schema, not user input
		f"SELECT {col_sql} FROM `tab{OLD}` WHERE {kitchen}"
	)

	missing = frappe.db.sql(
		f"SELECT COUNT(*) FROM `tab{OLD}` o LEFT JOIN `tab{NEW}` n ON n.name = o.name "  # nosemgrep: frappe-sql-format-injection -- constant
		"WHERE o.ingredient IS NOT NULL AND o.ingredient != '' AND n.name IS NULL"
	)[0][0]
	if missing:
		frappe.throw(f"{missing} kitchen ledger row(s) did not copy to {NEW}; {OLD} left untouched.")

	if "erpnext" in frappe.get_installed_apps():
		frappe.db.sql(f"DELETE FROM `tab{OLD}` WHERE {kitchen}")  # nosemgrep: frappe-sql-format-injection -- constant
		frappe.reload_doc("stock", "doctype", "stock_ledger_entry", force=True)
	elif frappe.db.get_value("DocType", OLD, "module") == "Kamra":
		frappe.delete_doc("DocType", OLD, force=True, ignore_permissions=True, ignore_missing=True)
		frappe.db.sql_ddl(f"DROP TABLE IF EXISTS `tab{OLD}`")

	frappe.clear_cache(doctype=OLD)
	frappe.clear_cache(doctype=NEW)
