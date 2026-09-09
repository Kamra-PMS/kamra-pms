"""Seed default Transaction Codes + Reason Codes; backfill Folio Charge.transaction_code."""

import frappe


def execute():
	from kamra.ledger import (
		ensure_default_reason_codes,
		ensure_default_transaction_codes,
		CHARGE_TYPE_TO_CODE,
	)
	ensure_default_transaction_codes()
	ensure_default_reason_codes()
	# Backfill transaction_code on existing Folio Charge rows via parent folios
	# (child table - update by SQL for speed)
	for charge_type, (code, *_rest) in CHARGE_TYPE_TO_CODE.items():
		if not frappe.db.exists("Transaction Code", code):
			continue
		frappe.db.sql(
			"""
			UPDATE `tabFolio Charge`
			SET transaction_code = %s
			WHERE charge_type = %s
			  AND (transaction_code IS NULL OR transaction_code = '')
			""",
			(code, charge_type),
		)
	# Seed business_date on properties
	from frappe.utils import nowdate
	for name in frappe.get_all("Property", pluck="name"):
		if not frappe.db.get_value("Property", name, "business_date"):
			frappe.db.set_value("Property", name, "business_date", nowdate(),
			                    update_modified=False)
