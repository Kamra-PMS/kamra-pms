"""Live updates: one tiny event says "something on this property changed".

Screens don't care what changed - they re-fetch their own view. Publishing
after commit means the re-fetch always sees the new state."""

import frappe

WATCHED = {"Reservation", "Folio", "Room", "Housekeeping Task",
           "Venue Booking", "Group Booking", "POS Order", "Service Ticket",
           "Laundry Order", "Agent Action Log"}


def notify(doc, method=None):
	if doc.doctype not in WATCHED:
		return
	try:
		frappe.publish_realtime(
			"kamra_changed",
			{"doctype": doc.doctype,
			 "property": doc.get("property")},
			after_commit=True,
		)
	except Exception:
		pass  # realtime must never break the write
