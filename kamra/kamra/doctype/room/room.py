# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class Room(Document):
	def validate(self):
		# Room.floor stays the floor's name; make sure the Floor master has it
		from kamra.floors import ensure_floor
		self.floor = (self.floor or "").strip() or None
		if self.floor and (self.is_new() or self.has_value_changed("floor")):
			ensure_floor(self.property, self.floor)
		self.validate_connecting_room()

	def validate_connecting_room(self):
		"""A connecting room is another room at the same property (#536)."""
		if not self.connects_to:
			return
		if self.connects_to == self.name:
			frappe.throw(_("A room can't connect to itself."))
		if frappe.db.get_value("Room", self.connects_to, "property") != self.property:
			frappe.throw(_("The connecting room must be at the same property."))

	def after_insert(self):
		# Keep Sellable Units in sync with physical inventory (ADR-001).
		try:
			from kamra.siu.units import ensure_individual_siu
			ensure_individual_siu(self.name)
		except Exception:
			frappe.log_error(title="Sellable Unit sync on Room insert")

	def on_update(self):
		self.sync_connecting_room()
		# Room.room_type drives the individual Sellable Unit's type (#548).
		if not self.has_value_changed("room_type"):
			return
		from kamra.siu.units import sync_individual_siu_room_type
		sync_individual_siu_room_type(self.name)

	def sync_connecting_room(self):
		"""The connecting door goes both ways: link the partner back, and
		unlink the old partner when the link changes."""
		if not self.has_value_changed("connects_to"):
			return
		old = self.get_doc_before_save()
		before = old.connects_to if old else None
		if before and before != self.connects_to and \
				frappe.db.get_value("Room", before, "connects_to") == self.name:
			frappe.db.set_value("Room", before, "connects_to", None)
		if self.connects_to:
			partner_was = frappe.db.get_value("Room", self.connects_to, "connects_to")
			if partner_was and partner_was != self.name and \
					frappe.db.get_value("Room", partner_was, "connects_to") == self.connects_to:
				# the partner's own old partner loses its link to it
				frappe.db.set_value("Room", partner_was, "connects_to", None)
			frappe.db.set_value("Room", self.connects_to, "connects_to", self.name)
