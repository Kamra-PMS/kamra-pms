import frappe
from frappe import _
from frappe.model.document import Document


class UnitOwner(Document):
	def validate(self):
		if not self.units and not self.get("room_types"):
			frappe.throw(_("Add at least one unit or unit type."))
		if not self.users:
			frappe.throw(_("Add at least one login."))
		seen_rooms = []
		for row in self.units:
			room = frappe.db.get_value("Room", row.room, ["property", "room_number"], as_dict=True)
			if not room or room.property != self.property:
				frappe.throw(_("{0} is not a unit of this property.").format(row.room))
			if row.room in seen_rooms:
				frappe.throw(_("Each unit can only be listed once."))
			seen_rooms.append(row.room)
		types = []
		for row in self.get("room_types") or []:
			if frappe.db.get_value("Room Type", row.room_type, "property") != self.property:
				frappe.throw(_("{0} is not a unit type of this property.").format(row.room_type))
			if row.room_type in types:
				frappe.throw(_("Each unit type can only be listed once."))
			types.append(row.room_type)
		for row in self.units:
			if row.commission_percent and not 0 <= row.commission_percent <= 100:
				frappe.throw(_("Commission must be between 0 and 100."))
		for row in self.get("costs") or []:
			if row.room and frappe.db.get_value("Room", row.room, "property") != self.property:
				frappe.throw(_("{0} is not a unit of this property.").format(row.room))
		seen_users = []
		for row in self.users:
			if not frappe.db.exists("User", row.user):
				frappe.throw(_("No login named {0}.").format(row.user))
			if row.user in seen_users:
				frappe.throw(_("Each login can only be listed once."))
			seen_users.append(row.user)
		if self.access not in ("Read only", "Manage"):
			self.access = "Read only"

	def on_update(self):
		from kamra.owners import sync_user_access
		before = self.get_doc_before_save()
		previous = {r.user for r in before.users} if before else set()
		current = {r.user for r in self.users}
		for user in previous | current:
			sync_user_access(user)

	def on_trash(self):
		frappe.flags.kamra_owner_resync = [r.user for r in (self.users or [])]

	def after_delete(self):
		from kamra.owners import sync_user_access
		for user in frappe.flags.pop("kamra_owner_resync", None) or []:
			sync_user_access(user)
