"""Kamra Verify for Indian properties: a corporate buyer's GSTIN, and a
guest's Aadhaar / Passport / Driving Licence / Voter ID read into the
profile. The checks run on the Kamra Connect hub (Cashfree SecureID behind
it) and are charged per check to the install's Connect wallet.

Privacy (DPDP): the hotel is the Data Fiduciary, Kamra a Data Processor.
An ID is read only after the desk confirms the guest was told; Aadhaar
numbers arrive from the hub already masked to the last 4 digits.
"""

import frappe
from frappe.utils import cint, getdate, now_datetime

# Guest.id_type -> the hub reads these; the rest of ID_TYPES are typed in
SCANNABLE_IDS = ("Aadhaar", "Passport", "Driving License", "Voter ID")

_GENDERS = {"m": "Male", "male": "Male", "f": "Female", "female": "Female",
            "t": "Other", "transgender": "Other", "other": "Other"}


def verify_gstin(property: str, gstin: str, business_name: str = "") -> dict:
	"""A corporate guest's GSTIN: is it active, and whose is it."""
	from kamra.connect.client import call

	out = call("verify_gstin", json_body={"gstin": gstin, "business_name": business_name})
	from kamra.savings import log_action
	log_action("verify_gstin", "Property", property, property, minutes_saved=5,
	           rationale=f"GSTIN {out.get('gstin')} {'valid' if out.get('valid') else 'NOT valid'}"
	                     f" · {out.get('legal_name') or '-'}", channel="API")
	return out


def _id_image(url: str) -> tuple[bytes, str]:
	name = frappe.db.get_value("File", {"file_url": url})
	if not name:
		frappe.throw("The ID image is not on file. Capture it first.")
	f = frappe.get_doc("File", name)
	return f.get_content(), f.file_name or "id.jpg"


def _as_date(value: str):
	for v in (value, (value or "").replace("/", "-")):
		try:
			d = getdate(v)
			if d and 1900 < d.year <= now_datetime().year:
				return d
		except Exception:
			pass  # not a date in this spelling; try the next one
	return None


def scan_guest_id(property: str, guest: str, id_type: str, consent: int = 0) -> dict:
	"""Read the guest's ID document on file and fill the profile: ID type
	and number, date of birth, gender; nationality, name and address only
	where the profile has none."""
	if not cint(consent):
		frappe.throw("Tell the guest their ID will be read by Kamra's verification partner, "
		             "then tick the confirmation.")
	if id_type not in SCANNABLE_IDS:
		frappe.throw(f"Reading supports: {', '.join(SCANNABLE_IDS)}.")
	if not frappe.db.exists("Guest", guest):
		frappe.throw("Guest not found.")
	g = frappe.get_doc("Guest", guest)
	if not g.id_file:
		frappe.throw("Capture the ID document first, then read it.")
	image, filename = _id_image(g.id_file)

	from kamra.connect.client import call
	out = call("scan_id", params={"id_type": id_type, "filename": filename, "consent": 1},
	           data=image)

	filled = {}

	def put(field, value, only_if_empty=False):
		if value and (not only_if_empty or not g.get(field)) and g.get(field) != value:
			g.set(field, value)
			filled[field] = value

	put("id_type", id_type)
	put("id_number", out.get("id_number"))
	put("date_of_birth", _as_date(out.get("date_of_birth") or ""))
	put("gender", _GENDERS.get((out.get("gender") or "").strip().lower()))
	put("nationality", out.get("nationality"), only_if_empty=True)
	put("address_line", (out.get("address") or "")[:140], only_if_empty=True)
	if out.get("name") and not (g.first_name or "").strip():
		first, _, last = out["name"].strip().partition(" ")
		put("first_name", first)
		put("last_name", last)
	if filled:
		g.save(ignore_permissions=True)
	from kamra.savings import log_action
	log_action("scan_guest_id", "Guest", g.name, property, minutes_saved=3,
	           rationale=f"{id_type} read by Kamra Verify; filled {', '.join(filled) or 'nothing new'}",
	           channel="API")
	return {"filled": {k: str(v) for k, v in filled.items()},
	        "charged": out.get("charged")}
