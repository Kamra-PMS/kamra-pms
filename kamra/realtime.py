"""Live updates: one tiny event says "something on this property changed".

Screens re-fetch their own view. The event carries the doctype and, for
outlet documents, the outlet, so a till or kitchen display can ignore the
front desk's and housekeeping's traffic. `is_new` is true when the document
was just created, so a screen can sound an alert for a new order or booking
and stay quiet for every edit after it, and `by` is a short hash of who made
the change (never the user name), so a screen can skip the alert for its own
person's action. The browser computes the same hash for its own user. Publishing after commit means the
re-fetch always sees the new state."""

import frappe

WATCHED = {"Reservation", "Folio", "Room", "Housekeeping Task",
           "Venue Booking", "Group Booking", "POS Order", "Service Ticket",
           "Laundry Order", "Agent Action Log"}


def who(user: str | None) -> str:
	"""A 32 bit djb2 hash of the user id, in hex. It only has to let a browser
	recognise its own user's changes; it is not a secret and not an identity,
	so staff addresses never travel in the broadcast. The same function is in
	frontend/src/lib/notifications.ts and the two must stay identical."""
	h = 5381
	for ch in user or "":
		h = ((h * 33) ^ ord(ch)) & 0xFFFFFFFF
	return format(h, "x")


def notify(doc, method=None):
	if doc.doctype not in WATCHED:
		return
	try:
		frappe.publish_realtime(  # nosemgrep: frappe-realtime-pick-room -- intentional lightweight property-wide change ping; clients filter by property and re-fetch
			"kamra_changed",
			{"doctype": doc.doctype, "name": doc.name,
			 "property": doc.get("property"), "outlet": doc.get("outlet"),
			 "is_new": method == "after_insert", "by": who(frappe.session.user)},
			after_commit=True,
		)
	except Exception:
		pass  # realtime must never break the write
