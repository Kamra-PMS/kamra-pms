# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class MenuModifierOption(Document):
	def validate(self):
		self.option_name = (self.option_name or "").strip()
		if not self.option_name:
			frappe.throw(_("A choice needs a name."))
		if float(self.price or 0) < 0:
			frappe.throw(_("{0}: a choice cannot take money off the price.")
			             .format(self.option_name))
		group_property = frappe.db.get_value(
			"Menu Modifier Group", self.modifier_group, "property")
		if group_property != self.property:
			frappe.throw(_("{0} belongs to another property.")
			             .format(self.modifier_group))
