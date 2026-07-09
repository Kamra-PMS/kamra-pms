# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_to_date, get_datetime, now_datetime

# priority -> minutes allowed before the clean is overdue
HK_SLA_MINUTES = {"Urgent": 20, "High": 45, "Medium": 90, "Low": 180}


class HousekeepingTask(Document):
	def before_insert(self):
		if not self.due_by:
			self.due_by = add_to_date(
				now_datetime(),
				minutes=HK_SLA_MINUTES.get(self.priority, 90),
			)

	def on_update(self):
		previous = self.get_doc_before_save()
		old_status = previous.status if previous else None
		if self.status == old_status:
			return
		# Completed cleans flow back into the room's live status so the
		# front desk (and any agent checking availability) sees readiness.
		if self.status == "Done":
			frappe.db.set_value("Room", self.room, "housekeeping_status", "Clean")
			if self.due_by and now_datetime() > get_datetime(self.due_by):
				self.db_set("breached", 1, update_modified=False)
			from kamra.housekeeping import notify_room_ready
			notify_room_ready(self)
		elif self.status == "Verified":
			frappe.db.set_value("Room", self.room, "housekeeping_status", "Inspected")
