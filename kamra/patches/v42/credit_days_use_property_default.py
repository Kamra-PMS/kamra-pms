"""City Ledger Account.use_default_credit_days (#238): an account follows
the property's default payment terms unless it has its own.

Before this flag, credit_days 0 meant "property default" and any other
value was the account's own terms. Keep exactly that: accounts with
credit_days > 0 get the flag off, the rest keep it on. Runs before the
due-date backfill so that patch reads the right terms."""

import frappe


def execute():
	if not frappe.db.table_exists("City Ledger Account"):
		return
	if not frappe.db.has_column("City Ledger Account", "use_default_credit_days"):
		frappe.reload_doc("kamra", "doctype", "city_ledger_account")
	frappe.db.sql("""UPDATE `tabCity Ledger Account`
	                 SET use_default_credit_days = IF(IFNULL(credit_days, 0) > 0, 0, 1)""")
