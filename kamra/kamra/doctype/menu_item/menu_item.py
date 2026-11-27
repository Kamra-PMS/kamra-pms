# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class MenuItem(Document):
	def validate(self):
		self.check_modifier_groups()
		self.keep_own_stock()

	def check_modifier_groups(self):
		"""A dish offers its own outlet's groups, each once. A group from
		another outlet would put choices on the till that the outlet's own
		kitchen and stock never set up."""
		seen = set()
		for row in self.get("modifier_groups") or []:
			if row.modifier_group in seen:
				frappe.throw(_("{0}: {1} is listed twice.")
				             .format(self.item_name, row.modifier_group))
			seen.add(row.modifier_group)
			outlet = frappe.db.get_value(
				"Menu Modifier Group", row.modifier_group, "outlet")
			if outlet != self.outlet:
				frappe.throw(_("{0}: {1} belongs to another outlet.")
				             .format(self.item_name, row.modifier_group))

	def keep_own_stock(self):
		"""An item that tracks its own stock is one stock item behind a fixed
		one-line recipe, never edited apart. Here and not only in the API,
		because the menu form saves through REST."""
		before = self.get_doc_before_save()
		was = before.stock_ingredient if before else None
		if (self.stock_ingredient or None) != (was or None) \
				and not self.flags.ignore_permissions:
			from kamra.inventory import require_stock_rights
			require_stock_rights()
		if not self.stock_ingredient:
			return
		if frappe.db.get_value("Ingredient", self.stock_ingredient, "property") != self.property:
			frappe.throw(_("{0} belongs to another property.").format(self.stock_ingredient))
		if [(r.ingredient, flt(r.qty)) for r in self.recipe] != [(self.stock_ingredient, 1.0)]:
			frappe.throw(_(
				"{0} tracks its own stock: its recipe is that one item. Stop tracking to change it."
			).format(self.item_name))
