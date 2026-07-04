# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_to_date, get_datetime, now_datetime

# priority -> minutes to resolve
SLA_MINUTES = {"Urgent": 15, "High": 30, "Medium": 60, "Low": 240}


class ServiceTicket(Document):
	def before_insert(self):
		self.due_by = add_to_date(
			now_datetime(), minutes=SLA_MINUTES.get(self.priority, 60)
		)

	def on_update(self):
		previous = self.get_doc_before_save()
		old_status = previous.status if previous else None
		if self.status == old_status:
			return

		if self.status == "Resolved":
			self.db_set("resolved_on", now_datetime(), update_modified=False)
			if self.due_by and now_datetime() > get_datetime(self.due_by):
				self.db_set("breached", 1, update_modified=False)
			from kamra.savings import log_action

			log_action(
				action_type="resolve_ticket",
				reference_doctype="Service Ticket",
				reference_name=self.name,
				property=self.property,
				minutes_saved=5 if self.source in ("AI Agent", "WhatsApp", "Voice") else 0,
				rationale=f"{self.category}: {self.subject}",
			)

		# a maintenance ticket puts a work item on the room's queue
		if (
			self.status == "In Progress"
			and self.category == "Maintenance"
			and self.room
			and not frappe.db.exists(
				"Housekeeping Task",
				{"room": self.room, "task_type": "Maintenance",
				 "status": ("in", ["Pending", "In Progress"])},
			)
		):
			frappe.get_doc({
				"doctype": "Housekeeping Task",
				"property": self.property,
				"room": self.room,
				"task_type": "Maintenance",
				"priority": self.priority,
				"status": "Pending",
				"notes": f"From ticket {self.name}: {self.subject}",
			}).insert(ignore_permissions=True)
