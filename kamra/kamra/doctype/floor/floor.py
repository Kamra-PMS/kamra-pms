# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class Floor(Document):
	def validate(self):
		self.floor_name = (self.floor_name or "").strip()
		if not self.floor_name:
			frappe.throw(_("Give the floor a name."))
		clash = frappe.db.exists("Floor", {
			"property": self.property, "floor_name": self.floor_name,
			"name": ("!=", self.name)})
		if clash:
			frappe.throw(_("{0} already has a floor called {1}.").format(
				self.property, self.floor_name))
		if self.disabled and self._room_count(self.get_doc_before_save()):
			frappe.throw(_("Floor {0} still has rooms. Move them to another floor before "
			               "disabling it.").format(self.floor_name))

	def _room_count(self, before=None) -> int:
		# rooms are keyed on the name as it was saved
		name = before.floor_name if before else self.floor_name
		return frappe.db.count("Room", {"property": self.property, "floor": name})

	def on_update(self):
		before = self.get_doc_before_save()
		if before and before.floor_name != self.floor_name:
			frappe.db.sql(
				"update `tabRoom` set floor=%s where property=%s and floor=%s",
				(self.floor_name, self.property, before.floor_name))

	def on_trash(self):
		if self._room_count():
			frappe.throw(_("Floor {0} still has rooms. Move them to another floor "
			               "before deleting it.").format(self.floor_name))
