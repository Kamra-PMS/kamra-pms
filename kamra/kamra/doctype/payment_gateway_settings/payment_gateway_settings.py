# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PaymentGatewaySettings(Document):
	def validate(self):
		# Payment confirmations are signature-checked; without the secret
		# every webhook is refused and folios never get marked paid.
		if self.enabled and not self.webhook_secret:
			frappe.msgprint(
				"Set the webhook secret (the same one entered on the gateway's "
				"webhook): payment confirmations are rejected until it is.",
				indicator="orange", alert=True)
