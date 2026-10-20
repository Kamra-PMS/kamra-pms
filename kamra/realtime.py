"""Live updates: one tiny event says "something on this property changed".

Screens re-fetch their own view. The event carries the doctype and, for
outlet documents, the outlet, so a till or kitchen display can ignore the
front desk's and housekeeping's traffic. Publishing after commit means the
re-fetch always sees the new state."""

import frappe

WATCHED = {"Reservation", "Folio", "Room", "Housekeeping Task",
           "Venue Booking", "Group Booking", "POS Order", "Service Ticket",
           "Laundry Order", "Agent Action Log"}


def notify(doc, method=None):
	if doc.doctype not in WATCHED:
		return
	try:
		frappe.publish_realtime(  # nosemgrep: frappe-realtime-pick-room -- intentional lightweight property-wide change ping; clients filter by property and re-fetch
			"kamra_changed",
			{"doctype": doc.doctype, "name": doc.name,
			 "property": doc.get("property"), "outlet": doc.get("outlet")},
			after_commit=True,
		)
	except Exception:
		pass  # realtime must never break the write
