# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_to_date, get_datetime, now_datetime

# priority -> minutes to resolve. Defaults - each property sets its own in
# Settings -> Operations (ticket_sla_<priority>).
SLA_MINUTES = {"Urgent": 15, "High": 30, "Medium": 60, "Low": 240}


def sla_minutes(property: str | None, priority: str | None) -> int:
	from kamra.settings import get_setting
	p = priority if priority in SLA_MINUTES else "Medium"
	return int(get_setting(property, f"ticket_sla_{p.lower()}", SLA_MINUTES[p]))


class ServiceTicket(Document):
	def _track_changes(self, previous):
		"""Who did what, and when: the ticket's timeline."""
		from kamra.tickets import log_event
		now = now_datetime()
		user = frappe.session.user
		if (self.assigned_to_user or None) != (previous.assigned_to_user or None):
			log_event(self, "Assigned", previous.assigned_to_user, self.assigned_to_user)
			self.db_set({"assigned_by": user if self.assigned_to_user else None,
			             "assigned_at": now if self.assigned_to_user else None},
			            update_modified=False)
		if self.priority != previous.priority:
			log_event(self, "Priority", previous.priority, self.priority)
		if self.status != previous.status:
			reopened = previous.status in ("Resolved", "Closed", "Cancelled") \
				and self.status in ("Open", "In Progress")
			log_event(self, "Reopened" if reopened else "Status",
			          previous.status, self.status,
			          note=self.resolution_note if self.status in ("Resolved", "Closed") else None)
			if reopened:
				self.db_set({"reopened_count": int(self.reopened_count or 0) + 1,
				             "resolved_on": None, "resolved_by": None},
				            update_modified=False)
		if not self.first_response_at and (
				self.status != "Open" or self.assigned_to_user) and (
				self.status != previous.status or
				(self.assigned_to_user or None) != (previous.assigned_to_user or None)):
			self.db_set("first_response_at", now, update_modified=False)

	def before_insert(self):
		self.due_by = add_to_date(
			now_datetime(), minutes=sla_minutes(self.property, self.priority)
		)

	def after_insert(self):
		from kamra.tickets import log_event
		log_event(self, "Created", to_value=self.source or "Manual", note=self.subject)
		if self.assigned_to_user:
			log_event(self, "Assigned", to_value=self.assigned_to_user)

	def on_update(self):
		previous = self.get_doc_before_save()
		if not previous:
			return
		self._track_changes(previous)
		old_status = previous.status
		if self.status == old_status:
			return

		if self.status == "Resolved":
			self.db_set({"resolved_on": now_datetime(), "resolved_by": frappe.session.user},
			            update_modified=False)
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
