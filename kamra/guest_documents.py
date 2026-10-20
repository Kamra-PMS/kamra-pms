"""What a guest's profile knows about their identity documents.

One place answers "is there already an ID or address proof for this guest,
is it still valid, and has it been used before?", so the guest profile and
the check-in step say the same thing.

Three rules shape it:

1. It reads; it never blocks. A missing or expired ID is a warning for the
   desk (see the `warnings` note in api.reservation_detail): the guest is at
   the counter with the card in hand and no arrival is refused over paper.
2. The scan belongs to a stay, not to the profile (kamra.id_documents), so a
   scan is reported here only when a past stay still holds one. Under the
   property's "Verify & Discard" retention nothing is held after checkout,
   and the profile keeps only the type, the last four digits, the dates and
   the fact that the ID was verified.
3. Numbers are returned as stored. Verify & Discard has already masked them
   to the last four digits at checkout (api._scrub_stay_ids).
"""

from __future__ import annotations

import frappe
from frappe.utils import add_days, getdate, nowdate

# a document that ends within this many days is flagged as "expiring"
EXPIRING_DAYS = 30


def id_status(expiry, has_id: bool) -> str:
	"""none (no ID recorded), valid, expiring (ends within EXPIRING_DAYS) or
	expired. A document with no expiry date is valid: many ID types never
	expire (an Aadhaar card), and an empty date is not a lapsed one."""
	if not has_id:
		return "none"
	if not expiry:
		return "valid"
	today = getdate(nowdate())
	end = getdate(expiry)
	if end < today:
		return "expired"
	if end <= getdate(add_days(today, EXPIRING_DAYS)):
		return "expiring"
	return "valid"


def used_stays_count(guest: str) -> int:
	"""How many of this guest's stays captured an ID (scan held or since
	discarded). Check-in shows it: an ID verified on earlier stays is one the
	desk can recognise rather than collect again."""
	return frappe.db.count("Reservation", {"guest": guest, "id_document": ["is", "set"]}) \
		+ frappe.db.count("Reservation", {"guest": guest, "id_document": ["is", "not set"],
		                                  "id_document_discarded": 1})


def guest_documents(guest: str, scope=None) -> dict:
	"""The guest's ID and address proof as the profile shows them.

	`scope` is the restricted user's property filter (api._property_scope),
	so a person limited to one property counts only the stays there."""
	g = frappe.get_doc("Guest", guest)
	filters: dict = {"guest": guest}
	if scope:
		filters["property"] = scope
	stays = frappe.get_all(
		"Reservation", filters=filters,
		fields=["name", "property", "status", "check_in_date",
		        "id_document", "id_document_on", "id_document_discarded"],
		order_by="check_in_date desc")
	# a stay "used" the ID when it was captured there, whether or not the
	# scan is still held
	used = [r for r in stays if r.id_document or r.id_document_discarded]
	held = [r for r in used if r.id_document]
	last_used = max((r.id_document_on for r in used if r.id_document_on), default=None)
	if not last_used and used:
		last_used = used[0].check_in_date

	has_id = bool(g.get("id_number") or g.get("id_file") or held)
	retention = None
	if stays:
		retention = frappe.db.get_value("Property", stays[0].property, "id_retention")

	return {
		"id": {
			"type": g.get("id_type"),
			"number": g.get("id_number"),
			"place_of_issue": g.get("id_place_of_issue"),
			"issue_date": str(g.get("id_issue_date") or "") or None,
			"expiry_date": str(g.get("id_expiry_date") or "") or None,
			"status": id_status(g.get("id_expiry_date"), has_id),
			"on_file": has_id,
			# the latest stay still holding a scan; the picture itself is
			# fetched through api.id_document_image, which is role gated
			"scan_reservation": held[0].name if held else None,
			"scan_on": (str(held[0].id_document_on or "") or None) if held else None,
		},
		"address_proof": {"on_file": bool(g.get("address_proof_file"))},
		"used": {
			"count": len(used),
			"last_on": str(last_used) if last_used else None,
			"last_reservation": used[0].name if used else None,
		},
		"retention": retention,
	}
