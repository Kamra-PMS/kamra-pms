# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class SOPTemplate(Document):
	def validate(self):
		self.key = (self.key or "").strip().lower()
		seen = set()
		for s in self.steps or []:
			s.step_key = (s.step_key or "").strip()
			if s.step_key in seen:
				frappe.throw(_("Step {0} is listed twice.").format(s.step_key))
			seen.add(s.step_key)
		if self.key == "checkin":
			# a stay cannot be checked in without a room: that step is
			# required whatever the template says
			for s in self.steps or []:
				if s.step_key == "assign_room":
					s.is_blocking = 1
