# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class OutboundWebhook(Document):
	def validate(self):
		# the same checks however the record is saved (settings screen,
		# Desk, data import): known events only, and a URL that is not a
		# way into the hotel's own network
		from kamra.webhooks import normalise_events, validate_target_url
		self.events = "\n".join(normalise_events(self.events))
		self.url = validate_target_url(self.url)
