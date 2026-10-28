# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class Guest(Document):
	def before_save(self):
		parts = [self.first_name or "", self.last_name or ""]
		self.full_name = " ".join(p.strip() for p in parts if p.strip())

	def validate(self):
		# consent changes only through kamra.privacy.set_marketing_consent,
		# which records the source and logs the change
		if self.has_value_changed("marketing_consent") \
				and (self.marketing_consent or not self.is_new()):
			frappe.throw(_("Marketing consent is changed from the guest profile, "
			               "the booking page or a STOP / START reply."))
		# a document cannot expire before it was issued; a typo here would
		# otherwise show every check-in a false "expired" warning
		if self.id_issue_date and self.id_expiry_date \
				and getdate(self.id_expiry_date) < getdate(self.id_issue_date):
			frappe.throw(_("The ID cannot expire before the day it was issued."))
