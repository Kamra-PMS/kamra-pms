"""Kitchen stock entries gain the moment they happened. Everything typed so
far happened when it was typed, and every stock take counted the balance it
left."""

import frappe


def execute():
	frappe.db.sql(
		"""update `tabIngredient Ledger Entry` set posted_at = creation
		where posted_at is null""")
	frappe.db.sql(
		"""update `tabIngredient Ledger Entry` set counted_qty = balance_after
		where reason = 'Count' and ifnull(cancelled, 0) = 0""")
