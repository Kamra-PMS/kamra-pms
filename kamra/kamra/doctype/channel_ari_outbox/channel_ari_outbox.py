# One row per change waiting to go to a channel manager: the connection, the
# window of dates it can move and what to send (availability, restrictions or
# both). The worker (kamra.channel_ari.flush_outbox) joins the due rows and
# sends only what differs from Channel ARI State. Dates and ids only.

from frappe.model.document import Document


class ChannelARIOutbox(Document):
	pass
