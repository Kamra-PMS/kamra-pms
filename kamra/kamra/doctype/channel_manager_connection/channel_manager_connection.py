import frappe
from frappe.model.document import Document


class ChannelManagerConnection(Document):
	def validate(self):
		# Inbound webhooks are refused until the connection can authenticate
		# them - say so up front instead of letting bookings silently bounce.
		if not self.active:
			return
		if self.provider == "AioSell":
			missing = not (self.api_username and self.api_key)
			what = "API username and API key"
		else:
			missing = not self.webhook_secret
			what = "webhook secret"
		if missing:
			frappe.msgprint(
				f"Set the {what}: inbound bookings from {self.provider} are "
				"rejected until it is configured.",
				indicator="orange", alert=True)
