import frappe
from frappe.model.document import Document


class WhatsAppTemplate(Document):
	def validate(self):
		import re
		if not re.fullmatch(r"[a-z0-9_]+", self.template_name or ""):
			frappe.throw("Template name must be lowercase letters, numbers "
			             "and underscores only (Meta's requirement).")
		if self.meta_id and self.has_value_changed("body"):
			frappe.throw("Meta does not allow editing a submitted template - "
			             "duplicate it as a new template instead.")
