# What a channel manager last accepted for one provider id: sent_values is
# {"YYYY-MM-DD": {field: value}}. The outbox diffs against it, so nothing
# already sent goes again; a rejected value is never written here.

from frappe.model.document import Document


class ChannelARIState(Document):
	def autoname(self):
		self.name = f"{self.connection}|{self.kind}|{self.external_id}"
