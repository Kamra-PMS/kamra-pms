import frappe
from frappe import _
from frappe.model.document import Document


class ChannelRoomMapping(Document):
	def validate(self):
		# a connection pushes one property's inventory: its mappings may only
		# name that property's room types
		if not (self.connection and self.room_type):
			return
		conn_prop = frappe.db.get_value(
			"Channel Manager Connection", self.connection, "property")
		rt_prop = frappe.db.get_value("Room Type", self.room_type, "property")
		if conn_prop and rt_prop and conn_prop != rt_prop:
			frappe.throw(_("Room type {0} belongs to {1}, not to this "
			               "connection's property {2}.").format(
				self.room_type, rt_prop, conn_prop))
		# a provider rate plan sells one Kamra plan: two mappings with the same
		# id would price it twice
		if self.external_rate_id and frappe.db.exists("Channel Room Mapping", {
				"connection": self.connection, "external_rate_id": self.external_rate_id,
				"name": ("!=", self.name or "")}):
			frappe.throw(_("Provider rate plan {0} is already mapped on this connection.").format(
				self.external_rate_id))
		if self.rate_plan and conn_prop:
			plan_prop = frappe.db.get_value("Rate Plan", self.rate_plan, "property")
			if plan_prop and plan_prop != conn_prop:
				frappe.throw(_("Rate plan {0} belongs to {1}, not to this connection's property {2}.").format(
					self.rate_plan, plan_prop, conn_prop))
