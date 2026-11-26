# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class Ingredient(Document):
	def validate(self):
		self.uom = (self.uom or "").strip()
		self.buy_uom = (self.buy_uom or "").strip() or None
		self._check_buying_unit()
		self._keep_stock_unit()

	def _check_buying_unit(self):
		size = flt(self.buy_size)
		if size < 0:
			frappe.throw(_("A buying unit must hold more than zero {0}.").format(self.uom))
		if bool(self.buy_uom) != bool(size):
			frappe.throw(_("Give a buying unit both a name and how many {0} it holds.")
			             .format(self.uom))

	def _keep_stock_unit(self):
		"""Stock figures and recipe quantities are plain numbers in this unit,
		so changing it would turn 18 g into 18 kg."""
		if self.is_new() or not self.has_value_changed("uom"):
			return
		if frappe.db.exists("Ingredient Ledger Entry", {"ingredient": self.name}) \
				or frappe.db.exists("Menu Item Ingredient", {"ingredient": self.name}):
			frappe.throw(_("{0} already has stock history or is on a recipe, so its unit stays {1}.")
			             .format(self.ingredient_name, self.get_doc_before_save().uom))
