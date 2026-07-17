"""Guest ID scans - the only place in Kamra that writes a private file.

Two callers, one gate: the guest's token-gated self check-in
(public_api.precheckin_upload_id) and the desk's authenticated counter
capture (api.upload_id_document). Both land in the same shape, so retention
only ever has to know about one shape.

Three things here are deliberate and will look wrong to someone skimming:

1. is_private=1 IS A LITERAL, never a parameter. Frappe's own upload_file
   takes is_private from the client form_dict - i.e. it trusts the browser to
   protect an Aadhaar scan. Nothing in this module can be talked into writing
   an ID where the public web can read it, because there is no argument that
   would do it.

2. THE FILE HANGS OFF THE RESERVATION, NOT THE GUEST. Guest is a shared
   profile keyed by phone, reused across stays. If the scan lived there,
   checkout of one stay would delete a document a repeat guest's OTHER live
   stay still needs. (_scrub_stay_ids already has that bug for the id_number
   TEXT - tolerable, the desk retypes it. For a file it is irreversible.)
   Attaching per-reservation makes cross-stay safety structural.

3. RE-ENCODING IS THE SECURITY BOUNDARY, not the format check. See _sanitise.

The image is deleted at checkout under the property's "Verify & Discard"
retention (see discard_id_document, called from api._scrub_stay_ids). Note
for anyone reading this before an audit: `bench backup --with-files` tars
private/files, so a scan survives in backups after that delete. No code here
fixes that; it is a backup-rotation decision. Do not let the guest-facing
copy over-promise.
"""

import base64
import io

import frappe
from frappe import _

# The client downscales to ~400KB before sending; this is the ceiling for a
# hostile caller, not a target. Capped BEFORE decode - a 500MB base64 string
# must not become 375MB of RAM on the way to being rejected.
MAX_BYTES = 4 * 1024 * 1024
MAX_EDGE = 2000
ALLOWED_FORMATS = {"JPEG", "PNG"}
DOC_FIELD = "id_document"
ACTIVE_STATUSES = ("Confirmed", "Checked In")


def _decode(data: str) -> bytes:
	"""data:image/jpeg;base64,... -> bytes."""
	if not data or not str(data).startswith("data:image/") or "," not in data:
		frappe.throw(_("Please upload a photo of your ID."))
	b64 = data.split(",", 1)[1]
	# 4/3 is base64's expansion; check the encoded length first so we never
	# allocate the decoded payload of something absurd.
	if len(b64) > (MAX_BYTES * 4 // 3) + 1024:
		frappe.throw(_("That photo is too large. Please retake it."))
	try:
		raw = base64.b64decode(b64, validate=True)
	except Exception:
		frappe.throw(_("That file didn't upload correctly. Please try again."))
	if not raw:
		frappe.throw(_("Please upload a photo of your ID."))
	if len(raw) > MAX_BYTES:
		frappe.throw(_("That photo is too large. Please retake it."))
	return raw


def _sanitise(raw: bytes) -> bytes:
	"""Return bytes we are certain are a plain JPEG, because we made them.

	Sniffing magic bytes only tells you the first few bytes look like an
	image; a JPEG with a webshell appended still starts with \\xff\\xd8.
	Re-encoding guarantees the OUTPUT is a JPEG this function wrote, so
	polyglots and appended payloads die on the way through rather than being
	detected. It also strips EXIF - which on a phone photo of an Aadhaar card
	carries the GPS coordinates of the guest's home.

	Never trust the filename or the Content-Type; Pillow's verdict is the
	only one that counts.
	"""
	from PIL import Image

	try:
		probe = Image.open(io.BytesIO(raw))
		probe.verify()  # structural check; leaves the object unusable
		fmt = probe.format
	except frappe.ValidationError:
		raise
	except Exception:
		frappe.throw(_("That doesn't look like a photo. Please retake it."))
	if fmt not in ALLOWED_FORMATS:
		frappe.throw(_("Please upload a JPG or PNG photo."))
	try:
		img = Image.open(io.BytesIO(raw))  # reopen: verify() consumed it
		img = img.convert("RGB")  # drops alpha/palette tricks
		img.thumbnail((MAX_EDGE, MAX_EDGE))
		out = io.BytesIO()
		img.save(out, format="JPEG", quality=82)  # no exif= -> stripped
		return out.getvalue()
	except Exception:
		frappe.throw(_("That photo couldn't be processed. Please retake it."))


def _existing(reservation: str) -> list:
	"""Files already attached to this booking's ID field. Queried by the
	attachment fields rather than by parsing Reservation.id_document, so a
	file orphaned by a half-failed replace is still found and cleaned up."""
	return frappe.get_all("File", filters={
		"attached_to_doctype": "Reservation",
		"attached_to_name": reservation,
		"attached_to_field": DOC_FIELD,
	}, pluck="name")


def store_id_document(res, data: str, source: str) -> str:
	"""Replace (never append) this booking's ID scan. Returns the file_url.

	`res` is a Reservation doc. This function does NOT check who is calling -
	the caller proves that: the guest endpoint by resolving a 96-bit token,
	the desk endpoint by @require_roles.
	"""
	if res.status not in ACTIVE_STATUSES:
		frappe.throw(_("This booking is no longer active."))

	clean = _sanitise(_decode(data))

	for old in _existing(res.name):  # one scan per booking, always
		try:
			frappe.delete_doc("File", old, ignore_permissions=True,
			                  delete_permanently=True)
		except Exception:
			frappe.log_error(title=f"ID document: stale file kept ({res.name})")

	from frappe.utils.file_manager import save_file
	f = save_file(
		fname=f"id-{res.name}.jpg",
		content=clean,
		dt="Reservation",
		dn=res.name,
		df=DOC_FIELD,
		is_private=1,
		folder="Home/Attachments",
	)
	frappe.db.set_value("Reservation", res.name, {
		DOC_FIELD: f.file_url,
		"id_document_source": source,
		"id_document_on": frappe.utils.now_datetime(),
		"id_document_discarded": 0,
	}, update_modified=False)
	return f.file_url


def discard_id_document(reservation: str) -> int:
	"""Verify & Discard: the scan leaves with the guest. Returns how many
	files went.

	Deliberately swallows its own errors. This runs inside checkout - a file
	Frappe cannot delete must never strand a guest at the desk with their
	luggage in the lobby. It logs and lets checkout finish; the leftover is a
	cleanup problem, not a service-stopping one.

	delete_doc, never os.unlink: File.on_trash -> delete_file_data_content
	handles the disk unlink AND the case where another File row shares the
	same content hash. Unlinking by hand would corrupt an unrelated
	attachment. delete_permanently=True because otherwise Frappe keeps a
	Deleted Document row holding the filename and trail - and "we deleted it"
	should mean it.
	"""
	gone = 0
	try:
		for name in _existing(reservation):
			frappe.delete_doc("File", name, ignore_permissions=True,
			                  delete_permanently=True)
			gone += 1
		frappe.db.set_value("Reservation", reservation, {
			DOC_FIELD: None,
			"id_document_discarded": 1,
		}, update_modified=False)
	except Exception:
		frappe.log_error(title=f"ID document discard failed: {reservation}")
	return gone
