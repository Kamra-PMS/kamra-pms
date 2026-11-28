# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class IngredientLedgerEntry(Document):
	pass


def on_doctype_update():
	# history, balances at a moment and the back-dating ripple all read in this order
	frappe.db.add_index("Ingredient Ledger Entry", ["ingredient", "outlet", "posted_at"])
