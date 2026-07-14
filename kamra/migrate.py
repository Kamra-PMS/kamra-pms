"""Migration importers - move a hotel off eZee / Cloudbeds / anything
with a CSV export, without hand-editing the file to match our columns.

The mapper recognises each vendor's header names (synonyms), detects the
date convention (eZee exports day-first, Cloudbeds month-first), resolves
room types by code or name, and maps their status vocabulary onto ours.
`preview_import` shows exactly what would happen - mapping, issues, row
counts - before `run_import` writes anything. History rows (checked-out /
cancelled / no-show) are stored as records, not re-run through live-
booking validation, so importing last year's register can't trip the
overbooking guard.
"""

import csv as csvmod
import io
import re

import frappe
from frappe import _

from kamra.authz import require_roles

# who a header column really is, whatever the vendor called it
SYNONYMS = {
	"guest_name": ["guest name", "guest", "name", "customer name",
	               "full name", "guest full name", "primary guest"],
	"phone": ["phone", "mobile", "mobile no", "mobile number",
	          "phone number", "contact", "contact no", "contact number"],
	"email": ["email", "e-mail", "email id", "guest email", "email address"],
	"room_type": ["room type", "room type code", "room category",
	              "accommodation type", "room type name", "category",
	              "rate type"],
	"check_in": ["check in", "check-in", "checkin", "check in date",
	             "checkin date", "arrival", "arrival date", "from date",
	             "start date"],
	"check_out": ["check out", "check-out", "checkout", "check out date",
	              "checkout date", "departure", "departure date", "to date",
	              "end date"],
	"adults": ["adults", "adult", "no of adults", "pax", "persons"],
	"children": ["children", "child", "kids", "no of children",
	             "no of child"],
	"amount_after_tax": ["grand total", "total amount", "total", "amount",
	                     "booking amount", "amount after tax", "net amount",
	                     "total charges", "total revenue"],
	"status": ["status", "reservation status", "booking status",
	           "res status"],
	"channel": ["channel", "source", "business source", "booking source",
	            "ota", "market source", "market segment"],
}
REQUIRED = ("guest_name", "room_type", "check_in", "check_out")

STATUS_MAP = {
	"confirmed": "Confirmed", "booked": "Confirmed", "reserved": "Confirmed",
	"guaranteed": "Confirmed", "new": "Confirmed",
	"checkedin": "Checked In", "inhouse": "Checked In",
	"arrived": "Checked In",
	"checkedout": "Checked Out", "departed": "Checked Out",
	"completed": "Checked Out", "checkout": "Checked Out",
	"cancelled": "Cancelled", "canceled": "Cancelled", "void": "Cancelled",
	"noshow": "No Show",
}
HISTORY = ("Checked Out", "Cancelled", "No Show")

MONTHS = {m: i + 1 for i, m in enumerate(
	["jan", "feb", "mar", "apr", "may", "jun",
	 "jul", "aug", "sep", "oct", "nov", "dec"])}


def _norm(s: str) -> str:
	return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _map_headers(headers):
	mapping, used = {}, set()
	for canon, alts in SYNONYMS.items():
		keys = {_norm(a) for a in alts}
		for h in headers:
			if h not in used and _norm(h) in keys:
				mapping[canon] = h
				used.add(h)
				break
	return mapping


def _parse_csv(text: str):
	text = (text or "").lstrip("﻿")
	try:
		dialect = csvmod.Sniffer().sniff(text[:2048], delimiters=",;\t")
	except Exception:
		dialect = csvmod.excel
	rows = [r for r in csvmod.reader(io.StringIO(text), dialect)
	        if any(c.strip() for c in r)]
	if len(rows) < 2:
		frappe.throw(_("The CSV needs a header row and at least one "
		              "data row."))
	headers = [c.strip() for c in rows[0]]
	return headers, [
		{headers[i]: (r[i].strip() if i < len(r) else "")
		 for i in range(len(headers))}
		for r in rows[1:]
	]


def _parse_date(v: str, dayfirst: bool):
	v = (v or "").strip().split(" ")[0].split("T")[0]
	if not v:
		return None
	m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", v)
	if m:
		y, mo, d = map(int, m.groups())
		return f"{y:04d}-{mo:02d}-{d:02d}"
	m = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})$", v)
	if m:
		a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
		y = y + 2000 if y < 100 else y
		if a > 12:
			d, mo = a, b
		elif b > 12:
			d, mo = b, a
		else:
			d, mo = (a, b) if dayfirst else (b, a)
		return f"{y:04d}-{mo:02d}-{d:02d}"
	m = re.match(r"^(\d{1,2})[ -]([A-Za-z]{3})[a-z]*[ -,]+(\d{2,4})$", v)
	if m and _norm(m.group(2))[:3] in MONTHS:
		d, mo, y = int(m.group(1)), MONTHS[_norm(m.group(2))[:3]], int(m.group(3))
		y = y + 2000 if y < 100 else y
		return f"{y:04d}-{mo:02d}-{d:02d}"
	return None


def _detect_dayfirst(values) -> bool:
	"""If any date's first number exceeds 12 it must be a day (eZee style);
	if any second number does, it's month-first (Cloudbeds). India default:
	day-first."""
	for v in values:
		m = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-]\d{2,4}", (v or "").strip())
		if not m:
			continue
		if int(m.group(1)) > 12:
			return True
		if int(m.group(2)) > 12:
			return False
	return True


def _room_type_resolver(property: str):
	rts = frappe.get_all(
		"Room Type", filters={"property": property},
		fields=["name", "room_type_code", "room_type_name"])
	cache: dict = {}

	def resolve(val: str):
		key = _norm(val)
		if not key:
			return None
		if key in cache:
			return cache[key]
		found = None
		for rt in rts:
			if key in (_norm(rt.room_type_code), _norm(rt.room_type_name),
			           _norm(rt.name)):
				found = rt.name
				break
		if not found:  # "Deluxe Room" should still hit "Deluxe"
			for rt in rts:
				n = _norm(rt.room_type_name)
				if n and (n in key or key in n):
					found = rt.name
					break
		cache[key] = found
		return found

	return resolve, [rt.room_type_name for rt in rts]


def _normalize(property: str, csv_text: str, preset: str):
	headers, raw = _parse_csv(csv_text)
	mapping = _map_headers(headers)
	missing = [f for f in REQUIRED if f not in mapping]
	dayfirst = (True if preset == "ezee"
	            else False if preset == "cloudbeds"
	            else _detect_dayfirst(
		[r.get(mapping.get("check_in", ""), "") for r in raw]))
	resolve, available = _room_type_resolver(property)

	rows, issues = [], []
	if missing:
		return headers, mapping, rows, [{
			"row": 0, "guest": "",
			"error": "Couldn't find column(s) for: "
			         + ", ".join(missing)
			         + ". Rename the headers or use the generic template.",
		}], dayfirst

	for i, r in enumerate(raw, start=1):
		get = lambda f: r.get(mapping.get(f, ""), "")  # noqa: E731
		guest = get("guest_name")
		problems = []
		if not guest.strip():
			problems.append("no guest name")
		rt = resolve(get("room_type"))
		if not rt:
			problems.append(
				f"unknown room type '{get('room_type')}' "
				f"(have: {', '.join(available) or 'none yet'})")
		ci = _parse_date(get("check_in"), dayfirst)
		co = _parse_date(get("check_out"), dayfirst)
		if not ci or not co:
			problems.append("unreadable date(s)")
		elif co < ci:
			problems.append("check-out before check-in")
		status_raw = _norm(get("status"))
		status = STATUS_MAP.get(status_raw, "Confirmed") if status_raw else "Confirmed"
		if problems:
			issues.append({"row": i, "guest": guest,
			               "error": "; ".join(problems)})
			continue
		amount = re.sub(r"[^0-9.]", "", get("amount_after_tax") or "")
		rows.append({
			"guest_name": guest.strip(),
			"phone": get("phone").strip() or None,
			"email": get("email").strip() or None,
			"room_type": rt,
			"check_in": ci, "check_out": co,
			"adults": int(re.sub(r"\D", "", get("adults") or "") or 2) or 2,
			"children": int(re.sub(r"\D", "", get("children") or "") or 0),
			"amount_after_tax": float(amount) if amount else None,
			"status": status,
			"channel": get("channel").strip() or None,
		})
	return headers, mapping, rows, issues, dayfirst


@frappe.whitelist(methods=["POST"])
@require_roles()
def preview_import(property: str, csv_text: str, preset: str = "auto"):
	"""Dry run: how the file's columns map, which date convention was
	detected, and every row that would be skipped - nothing is written."""
	headers, mapping, rows, issues, dayfirst = _normalize(
		property, csv_text, preset)
	return {
		"headers": headers,
		"mapping": mapping,
		"unmapped": [h for h in headers if h not in mapping.values()],
		"date_format": "day-first (DD/MM)" if dayfirst else "month-first (MM/DD)",
		"ok": len(rows),
		"skipped": len(issues),
		"issues": issues[:25],
		"sample": rows[:10],
	}


@frappe.whitelist(methods=["POST"])
@require_roles()
def run_import(property: str, csv_text: str, preset: str = "auto"):
	"""Import the file. Live rows (confirmed / in-house) go through the
	full booking validation; history rows (checked-out / cancelled /
	no-show) are stored as records with their status stamped directly, so
	guest history survives the migration."""
	from kamra.api import _find_or_create_guest
	_headers, _mapping, rows, issues, _dayfirst = _normalize(
		property, csv_text, preset)

	created, history, errors = [], 0, list(issues)
	for i, row in enumerate(rows, start=1):
		try:
			guest = _find_or_create_guest(row["guest_name"], row["phone"])
			if row["email"] and not frappe.db.get_value("Guest", guest, "email"):
				frappe.db.set_value("Guest", guest, "email", row["email"],
				                    update_modified=False)
			doc = frappe.get_doc({
				"doctype": "Reservation",
				"property": property,
				"guest": guest,
				"room_type": row["room_type"],
				"check_in_date": row["check_in"],
				"check_out_date": row["check_out"],
				"adults": row["adults"],
				"children": row["children"],
				"source": "PMS",
				"channel": row["channel"],
				"auto_price": 0 if row["amount_after_tax"] else 1,
			})
			if row["amount_after_tax"]:
				doc.amount_after_tax = row["amount_after_tax"]
			if row["status"] in HISTORY:
				# a past stay is a record, not a live booking: skip live
				# validation (overbooking guard, blacklist) and stamp the
				# final status without side effects (no folio, no HK task)
				doc.flags.ignore_validate = True
				doc.insert()
				doc.db_set("status", row["status"], update_modified=False)
				history += 1
			else:
				doc.insert()
				if row["status"] == "Checked In":
					doc.status = "Checked In"
					doc.save()
			created.append(doc.name)
		except Exception as e:
			errors.append({"row": i, "guest": row["guest_name"],
			               "error": str(e)[:160]})

	from kamra.savings import log_action
	log_action("import_bookings", "Property", property, property,
	           minutes_saved=2 * len(created),
	           rationale=f"Imported {len(created)} bookings "
	                     f"({history} history, {len(errors)} skipped)",
	           channel="API")
	return {"created": len(created), "history": history,
	        "reservations": created[:50], "errors": errors}
