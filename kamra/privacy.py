"""Guest privacy by design (India DPDP Act 2023 and Rules 2025; GDPR-friendly).

The hotel is the Data Fiduciary for its guests. Kamra's job is to make the
right thing the default and the lawful thing one click:

  erase_guest        right to erasure (s.12): every identifying trace goes,
                     including photos, signatures, message logs and change
                     history; bills and stays stay for the tax books.
  export_guest_data  right to access (s.11): a summary of what is held.
  apply_retention    storage limitation (s.8(7)): guests with no stay for
                     Property.guest_retention_months are erased by the daily
                     scheduler. Guests on the blacklist are kept (security is
                     the stated purpose) until the flag is lifted.

What is deliberately kept after erasure: amounts, dates, rooms and invoice
numbers (GST law needs them), an ID masked to its last 4 digits in the stay
register, and one audit line saying the erasure happened (without the name).
"""

import json

import frappe
from frappe.utils import add_months, cint, getdate, nowdate

from kamra.authz import require_roles


def _mask(value: str | None) -> str | None:
	if not value or len(value) <= 4 or value.startswith("•"):
		return value
	return "•" * (len(value) - 4) + value[-4:]


def _delete_files(doctype: str, name: str, field: str | None = None, url: str | None = None) -> int:
	filters = {"attached_to_doctype": doctype, "attached_to_name": name}
	if field:
		filters["attached_to_field"] = field
	if url:
		filters["file_url"] = url
	gone = 0
	for f in frappe.get_all("File", filters=filters, pluck="name"):
		# delete_doc handles shared content hashes; delete_permanently leaves
		# no Deleted Document row holding the file name
		frappe.delete_doc("File", f, force=True, ignore_permissions=True, delete_permanently=True)
		gone += 1
	return gone


def _scrub_text(doctype: str, fields: tuple, secrets: list[str], alias: str, where: str = "", values=()):
	"""Replace each identifying string with the alias in free-text columns."""
	for field in fields:
		for s in secrets:
			frappe.db.sql(  # nosemgrep: frappe-sql-format-injection -- doctype/field are constants from this module; values parameterized
				f"UPDATE `tab{doctype}` SET `{field}` = REPLACE(`{field}`, %s, %s) "
				f"WHERE `{field}` LIKE %s {where}",
				(s, alias, f"%{s}%", *values))


def erase_guest(guest: str, reason: str = "request") -> dict:
	"""Irreversibly remove what identifies a guest. Financial records remain."""
	g = frappe.get_doc("Guest", guest)
	alias = f"Guest {frappe.generate_hash(length=6).upper()}"
	secrets = [s for s in {g.full_name, g.phone, g.email, g.id_number,
	                       f"{g.first_name or ''} {g.last_name or ''}".strip()} if s and len(s) >= 4]
	reservations = frappe.get_all("Reservation", filters={"guest": guest}, pluck="name")
	counts = {"files": 0, "messages": 0, "occupants": 0}

	# 1. the profile itself, photos included
	for field in ("id_file", "address_proof_file"):
		counts["files"] += _delete_files("Guest", guest, field)
	counts["files"] += _delete_files("Guest", guest)
	blank = {"first_name": alias, "last_name": "", "full_name": alias, "phone": "", "email": "",
	         "id_type": "", "id_number": "", "nationality": "", "address_line": "", "city": "",
	         "id_file": None, "address_proof_file": None, "date_of_birth": None, "gender": "",
	         "guest_notes": "Profile erased.", "vip": 0}
	frappe.db.set_value("Guest", guest, {k: v for k, v in blank.items() if g.meta.has_field(k)},
	                    update_modified=False)

	# 2. stays: names on the books become the alias; signatures, booker
	#    contact, occupant photos and phones go; IDs are masked
	for doctype in ("Reservation", "Folio"):
		frappe.db.sql(  # nosemgrep: frappe-sql-format-injection -- doctype is a constant from this loop
			f"UPDATE `tab{doctype}` SET guest_name = %s WHERE guest = %s", (alias, guest))
	for r in reservations:
		res = frappe.get_doc("Reservation", r)
		changes = {"booked_by_phone": "", "precheckin_signature": None}
		if res.get("booked_by_name") and res.booked_by_name in secrets:
			changes["booked_by_name"] = alias
		frappe.db.set_value("Reservation", r, {k: v for k, v in changes.items() if res.meta.has_field(k)},
		                    update_modified=False)
		for o in res.get("occupants") or []:
			oc = {"id_number": _mask(o.id_number), "phone": ""}
			if o.get("id_file"):
				counts["files"] += _delete_files("Reservation", r, url=o.id_file)
				oc["id_file"] = None
			if o.full_name in secrets:
				oc["full_name"] = alias
			frappe.db.set_value("Stay Occupant", o.name, oc, update_modified=False)
			counts["occupants"] += 1
		from kamra.id_documents import discard_id_document
		discard_id_document(r)
		for dt in ("Laundry Order", "Service Ticket"):
			frappe.db.sql(  # nosemgrep: frappe-sql-format-injection -- dt is a constant from this loop
				f"UPDATE `tab{dt}` SET guest_name = %s WHERE reservation = %s", (alias, r))

	# 3. conversations about the guest
	for m in frappe.get_all("WhatsApp Message", filters={"guest": guest}, pluck="name"):
		frappe.db.set_value("WhatsApp Message", m, {"content": "[erased]", "to_number": "",
		                                            "from_number": "", "guest": None},
		                    update_modified=False)
		counts["messages"] += 1
	_scrub_text("Copilot Conversation", ("messages", "title"), secrets, alias)
	_scrub_text("Communication", ("content", "subject", "recipients", "sender", "phone_no"), secrets, alias)

	# 4. audit and change history keep what happened, not who it was
	_scrub_text("Agent Action Log", ("rationale", "before_snapshot", "after_snapshot"), secrets, alias)
	frappe.db.delete("Version", {"ref_doctype": "Guest", "docname": guest})
	_scrub_text("Version", ("data",), secrets, alias,
	            "AND ref_doctype IN ('Reservation', 'Folio')", ())

	from kamra.savings import log_action
	log_action("erase_guest", "Guest", guest,
	           rationale=f"Personal data erased ({reason}); financial records kept for the books")
	return {"guest": guest, "alias": alias, "reservations": len(reservations), **counts}


@frappe.whitelist(methods=["POST"])
@require_roles()
def export_guest_data(guest: str) -> dict:
	"""Right to access: everything Kamra holds about one guest, readable."""
	g = frappe.get_doc("Guest", guest)
	profile = {f.fieldname: g.get(f.fieldname) for f in g.meta.fields
	           if f.fieldtype not in ("Section Break", "Column Break", "Tab Break") and g.get(f.fieldname)}
	stays = frappe.get_all("Reservation", filters={"guest": guest},
	                       fields=["name", "property", "check_in_date", "check_out_date", "status",
	                               "adults", "children", "source"], order_by="check_in_date desc")
	folios = frappe.get_all("Folio", filters={"guest": guest},
	                        fields=["name", "reservation", "status", "grand_total", "balance"])
	messages = frappe.get_all("WhatsApp Message", filters={"guest": guest},
	                          fields=["creation", "direction", "status", "template_name"],
	                          order_by="creation desc", limit=200)
	from kamra.savings import log_action
	log_action("export_guest_data", "Guest", guest, rationale="Data access request answered")
	return {"generated_on": str(frappe.utils.now_datetime()), "guest": guest, "profile": profile,
	        "stays": stays, "bills": folios, "messages": messages,
	        "note": "Bills and stay dates are kept as tax records even after erasure."}


def _last_activity(guest: str):
	row = frappe.db.sql("""select max(greatest(coalesce(check_out_date, '1970-01-01'),
		date(modified))) from `tabReservation` where guest=%s""", guest)
	last = row[0][0] if row and row[0][0] else None
	return getdate(last) if last else getdate(frappe.db.get_value("Guest", guest, "modified"))


def apply_retention(limit: int = 500) -> dict:
	"""Daily: erase guests idle past their property's retention period.
	A guest's period is the longest among the properties they stayed at;
	any property with retention off (0) keeps them."""
	months = {p.name: cint(p.guest_retention_months)
	          for p in frappe.get_all("Property", fields=["name", "guest_retention_months"])}
	if not any(months.values()):
		return {"erased": 0}
	erased = 0
	candidates = frappe.db.sql("""select g.name from `tabGuest` g
		where coalesce(g.blacklisted, 0) = 0 and g.full_name not like 'Guest %%'
		and not exists (select 1 from `tabReservation` r where r.guest = g.name
		                and r.status in ('Tentative', 'Pending Payment', 'Held', 'Confirmed', 'Checked In'))
		order by g.modified limit %s""", limit, pluck=True)
	for guest in candidates:
		props = set(frappe.get_all("Reservation", filters={"guest": guest}, pluck="property"))
		keep = [months.get(p, 0) for p in props] or [0]
		if 0 in keep:
			continue
		if _last_activity(guest) < getdate(add_months(nowdate(), -max(keep))):
			erase_guest(guest, reason="retention period ended")
			erased += 1
			frappe.db.commit()  # nosemgrep: frappe-manual-commit -- scheduler: one guest's erasure must not roll back another's
	return {"erased": erased}
