# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class MenuModifierGroup(Document):
	def validate(self):
		self.group_name = (self.group_name or "").strip()
		if not self.group_name:
			frappe.throw(_("A group needs a name."))
		if frappe.db.get_value("POS Outlet", self.outlet, "property") != self.property:
			frappe.throw(_("{0} belongs to another property.").format(self.outlet))
		clash = frappe.db.sql(
			"""select name from `tabMenu Modifier Group`
			   where outlet=%s and name!=%s and lower(group_name)=%s""",
			(self.outlet, self.name or "", self.group_name.lower()))
		if clash:
			frappe.throw(_("This outlet already has a group called {0}.")
			             .format(self.group_name))
		# "Most choices" only means something when several may be picked
		self.max_choices = max(0, int(self.max_choices or 0)) if self.multi else 0

	def on_trash(self):
		"""A group takes its choices with it and comes off every dish that
		offered it. What was sold keeps its own copy of the choice (see
		kamra.menu_modifiers), so past bills read the same."""
		for opt in frappe.get_all("Menu Modifier Option",
		                          filters={"modifier_group": self.name}):
			frappe.delete_doc("Menu Modifier Option", opt.name,
			                  ignore_permissions=True, force=True)
		for row in frappe.get_all(
				"Menu Item Modifier Group",
				filters={"modifier_group": self.name, "parenttype": "Menu Item"},
				fields=["name"]):
			frappe.delete_doc("Menu Item Modifier Group", row.name,
			                  ignore_permissions=True, force=True)
