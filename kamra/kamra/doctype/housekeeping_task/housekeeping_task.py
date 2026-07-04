# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class HousekeepingTask(Document):
	def on_update(self):
		previous = self.get_doc_before_save()
		old_status = previous.status if previous else None
		if self.status == old_status:
			return
		# Completed cleans flow back into the room's live status so the
		# front desk (and any agent checking availability) sees readiness.
		if self.status == "Done":
			frappe.db.set_value("Room", self.room, "housekeeping_status", "Clean")
		elif self.status == "Verified":
			frappe.db.set_value("Room", self.room, "housekeeping_status", "Inspected")
