# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt


class Ingredient(Document):
	def validate(self):
		self.uom = (self.uom or "").strip()
		self.buy_uom = (self.buy_uom or "").strip() or None
		self._check_buying_unit()
		self._check_made_here()
		self._keep_stock_unit()

	def on_update(self):
		# what something made here costs follows its recipe, its batch and the
		# cost of what goes into it
		if cint(self.is_made) or (self.get_doc_before_save()
		                          and self.has_value_changed("cost_per_unit")):
			from kamra.inventory import schedule_recost

			schedule_recost([self.name])

	def _check_buying_unit(self):
		size = flt(self.buy_size)
		if size < 0:
			frappe.throw(_("A buying unit must hold more than zero {0}.").format(self.uom))
		if bool(self.buy_uom) != bool(size):
			frappe.throw(_("Give a buying unit both a name and how many {0} it holds.")
			             .format(self.uom))

	def _check_made_here(self):
		"""Made here: a batch of this is made from bought ingredients (one level
		only), and what it costs is worked out from them, never typed. Checked
		here because the ingredient screen saves through the REST API."""
		before = None if self.is_new() else self.get_doc_before_save()
		made = cint(self.is_made)
		if before and made != cint(before.is_made) \
				and frappe.db.exists("Ingredient Ledger Entry", {"ingredient": self.name}):
			frappe.throw(_("{0} already has stock history, so \"Made here\" stays as it is.")
			             .format(self.ingredient_name))
		if not made:
			self.batch_qty = 0
			self.set("recipe", [])
			return
		# a line added on the screen and left blank says nothing
		filled = [line for line in self.recipe if line.ingredient or flt(line.qty)]
		if len(filled) != len(self.recipe):
			self.set("recipe", filled)
		if not flt(self.batch_qty) > 0:
			frappe.throw(_("Say how much one batch makes, above zero."))
		if not self.recipe:
			frappe.throw(_("Something made here needs at least one ingredient in its recipe."))
		for line in self.recipe:
			self._check_part(line)
		used_in = frappe.db.get_value(
			"Menu Item Ingredient",
			{"ingredient": self.name, "parenttype": "Ingredient"}, "parent")
		if used_in:
			frappe.throw(_("{0} is used to make {1}, so it cannot be made here itself.").format(
				self.ingredient_name,
				frappe.db.get_value("Ingredient", used_in, "ingredient_name")))
		self.cost_per_unit = flt(before.cost_per_unit) if before else 0

	def _check_part(self, line):
		if not flt(line.qty) > 0:
			frappe.throw(_("Every recipe line needs a quantity above zero."))
		if line.ingredient == self.name:
			frappe.throw(_("{0} cannot be made from itself.").format(self.ingredient_name))
		part = frappe.db.get_value(
			"Ingredient", line.ingredient,
			["ingredient_name", "property", "is_made"], as_dict=True)
		if not part or part.property != self.property:
			frappe.throw(_("{0} belongs to another property.").format(line.ingredient))
		if part.is_made:
			frappe.throw(_("{0} is made here too. Use only bought ingredients.")
			             .format(part.ingredient_name))

	def _keep_stock_unit(self):
		"""Stock figures and recipe quantities are plain numbers in this unit,
		so changing it would turn 18 g into 18 kg."""
		if self.is_new() or not self.has_value_changed("uom"):
			return
		if frappe.db.exists("Ingredient Ledger Entry", {"ingredient": self.name}) \
				or frappe.db.exists("Menu Item Ingredient", {"ingredient": self.name}) \
				or frappe.db.exists("Menu Item Ingredient",
				                    {"parent": self.name, "parenttype": "Ingredient"}):
			frappe.throw(_("{0} already has stock history or is on a recipe, so its unit stays {1}.")
			             .format(self.ingredient_name, self.get_doc_before_save().uom))
