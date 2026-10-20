"""City ledger bills raised before payment terms existed have no due date.

Give each Invoice entry one: its invoice (posting) date + the account's
effective credit days today (the account's own, else the property's
`default_credit_days`). Aging by due date and credit control read it.

Idempotent: only entries with no due date are touched, so a re-run changes
nothing."""

import frappe


def execute():
	if not frappe.db.table_exists("City Ledger Entry"):
		return
	if not frappe.db.has_column("City Ledger Entry", "due_date"):
		frappe.reload_doc("kamra", "doctype", "city_ledger_entry")
	if not frappe.db.has_column("City Ledger Account", "credit_days"):
		frappe.reload_doc("kamra", "doctype", "city_ledger_account")
	from frappe.utils import add_days

	from kamra.ledger import effective_credit_days

	rows = frappe.db.sql(
		"""SELECT name, account, property, posting_date
		   FROM `tabCity Ledger Entry`
		   WHERE kind = 'Invoice' AND due_date IS NULL""",
		as_dict=True)
	days: dict[str, int] = {}
	for r in rows:
		if r.account not in days:
			days[r.account] = effective_credit_days(r.account, r.property)
		frappe.db.set_value(
			"City Ledger Entry", r.name, "due_date",
			str(add_days(r.posting_date, days[r.account])),
			update_modified=False)
