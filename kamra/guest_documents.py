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

import base64
import mimetypes

import frappe
from frappe import _
from frappe.utils import add_days, getdate, nowdate

from kamra.authz import require_roles

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
	retention = _retention(guest, stays)

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
			# an image kept on the profile itself (fetched through guest_file)
			"file": bool(g.get("id_file")),
		},
		"address_proof": {"on_file": bool(g.get("address_proof_file"))},
		"photo": bool(g.get("photo")),
		"used": {
			"count": len(used),
			"last_on": str(last_used) if last_used else None,
			"last_reservation": used[0].name if used else None,
		},
		"retention": retention,
	}


# ── images kept on the profile: photo, ID, address proof ──────────────────
#
# The same pipeline as the stay's ID scan (kamra.id_documents): the browser
# sends a data URL, it is re-encoded (JPEG or PNG only, metadata stripped,
# size capped), saved as a private file, and read back through a role gated
# endpoint rather than a /private/files link. All three are optional.

GUEST_FILES = {"photo": "photo", "id": "id_file", "address": "address_proof_file"}


def _retention(guest: str, stays=None) -> str | None:
	"""The ID policy that governs this guest: the latest stay's property, or
	the only property on a single-property site."""
	if stays is None:
		stays = frappe.get_all("Reservation", filters={"guest": guest},
		                       fields=["property"], order_by="check_in_date desc", limit=1)
	if stays:
		return frappe.db.get_value("Property", stays[0].property, "id_retention")
	props = frappe.get_all("Property", pluck="id_retention", limit=2)
	return props[0] if len(props) == 1 else None


def _drop(guest: str, field: str) -> None:
	"""Delete the field's files, including older uploads that recorded only
	their URL and not the field."""
	from kamra.privacy import _delete_files

	_delete_files("Guest", guest, field)
	url = frappe.db.get_value("Guest", guest, field)
	if url:
		_delete_files("Guest", guest, url=url)


def _field(kind: str) -> str:
	if kind not in GUEST_FILES:
		frappe.throw(_("Unknown document."))
	return GUEST_FILES[kind]


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Kamra Agent", scope={"guest": "Guest"})
def save_guest_file(guest: str, kind: str, data: str) -> dict:
	"""Keep a photo, ID image or address proof on the profile, replacing the
	previous one. A property on Verify & Discard keeps no ID images, so only
	the photo is accepted there (the check-in ID step verifies and discards)."""
	from frappe.utils.file_manager import save_file

	from kamra.id_documents import _decode, _sanitise

	field = _field(kind)
	if kind != "photo" and _retention(guest) == "Verify & Discard":
		frappe.throw(_("This property does not keep ID images. Verify the ID at check-in instead."))
	clean = _sanitise(_decode(data))
	_drop(guest, field)
	f = save_file(fname=f"{kind}-{guest}.jpg", content=clean, dt="Guest", dn=guest,
	              df=field, is_private=1, folder="Home/Attachments")
	frappe.db.set_value("Guest", guest, field, f.file_url)
	return {"ok": True}


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent", scope={"guest": "Guest"})
def guest_file(guest: str, kind: str) -> dict:
	"""One of the profile's images as a data URL."""
	field = _field(kind)
	url = frappe.db.get_value("Guest", guest, field)
	if not url:
		frappe.throw(_("Nothing on file."))
	name = frappe.db.get_value("File", {"attached_to_doctype": "Guest", "attached_to_name": guest,
	                                    "file_url": url})
	if not name:
		frappe.throw(_("That file is no longer stored."))
	doc = frappe.get_doc("File", name)
	mime = mimetypes.guess_type(doc.file_name or url)[0] or "image/jpeg"
	return {"data": f"data:{mime};base64," + base64.b64encode(doc.get_content()).decode(),
	        "is_image": mime.startswith("image/")}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Kamra Agent", scope={"guest": "Guest"})
def remove_guest_file(guest: str, kind: str) -> dict:
	_drop(guest, _field(kind))
	frappe.db.set_value("Guest", guest, _field(kind), None)
	return {"ok": True}
