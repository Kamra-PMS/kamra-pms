# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class MenuItem(Document):
	def validate(self):
		self.check_modifier_groups()

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
