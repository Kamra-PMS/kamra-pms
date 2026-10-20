"""Go-live data - everything a hotel carries over from its old PMS on the
night it switches to Kamra, from Kamra's own CSV templates (vendor-neutral).

Three files, each previewed before anything is written:

- bookings  - kamra.migrate (future, in-house and history reservations)
- companies - corporate accounts with credit terms (credit allowed, limit,
              credit days)
- opening balances - one sheet, a `Type` column per row:
    In-house  what an in-house guest owed on the old folio (negative = in
              credit). One "Opening Balance" line on the guest folio.
    City ledger  an unpaid company invoice (negative = money the company
              paid ahead). Billed to the company's AR the way a checkout
              transfer is (ledger.transfer_to_city_ledger).
    Deposit   an advance a future booking has already paid. An Advance
              payment on its folio (Deposit ledger).

Every amount goes through the existing folio / ledger writers - no raw SQL
writes, no second path. Nothing touches today's till: the money moved in
the old system, before go-live. Each posting is labelled (charge type
"Opening Balance", transaction code 8900, references "opening-...") so an
audit can always tell carried-over money from Kamra's own, and each is
keyed so re-running the same file never posts twice.

`reconcile` compares the files with what is now in Kamra, category by
category; go-live is ready only when every count and total matches.
"""

from __future__ import annotations

import hashlib
import re

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, now_datetime

from kamra.authz import require_roles
from kamra.migrate import (
	_detect_dayfirst,
	_map_headers,
	_norm,
	_parse_csv,
	_parse_date,
)

OPENING_LABEL = "Opening balance b/f from previous system"
DEPOSIT_REF = "opening-deposit:"
AR_KEY = "opening-ar:"
CHANNEL = "Go-live opening balance"

# ── templates ────────────────────────────────────────────────────────────────

TEMPLATES = {
	"bookings": (
		"kamra-bookings.csv",
		["Reservation No", "Guest Name", "Phone", "Email", "Room Type", "Room",
		 "Check In", "Check Out", "Adults", "Children", "Total Amount",
		 "Status", "Source"]),
	"companies": (
		"kamra-companies.csv",
		["Company Name", "Tax ID", "Contact Name", "Contact Phone",
		 "Contact Email", "Credit Allowed", "Credit Limit", "Credit Days",
		 "Account No"]),
	"opening": (
		"kamra-opening-balances.csv",
		["Type", "Reservation No", "Guest Name", "Room", "Check In",
		 "Check Out", "Room Type", "Company", "Invoice No", "Invoice Date",
		 "Amount", "Mode"]),
}


@frappe.whitelist()
@require_roles("Finance")
def csv_template(kind: str):
	"""The header row of one of Kamra's go-live CSV templates."""
	if kind not in TEMPLATES:
		frappe.throw(_("Unknown template: {0}.").format(kind))
	filename, headers = TEMPLATES[kind]
	return {"filename": filename, "csv": ",".join(headers) + "\n",
	        "headers": headers}


# ── shared parsing ───────────────────────────────────────────────────────────

def _amount(v: str):
	"""'1,250.50' / '(1,250.50)' / '-1250' / 'SAR 300' -> float; None if blank."""
	v = (v or "").strip()
	if not v:
		return None
	neg = (v.startswith("(") and v.endswith(")")) or "-" in v
	digits = re.sub(r"[^0-9.]", "", v)
	if not digits or digits.count(".") > 1:
		raise ValueError(f"unreadable amount '{v}'")
	return -float(digits) if neg else float(digits)


def _yes(v: str, default: bool) -> bool:
	n = _norm(v)
	if not n:
		return default
	return n in ("y", "yes", "true", "1", "allowed", "credit", "on")


def _money(v) -> float:
	return round(flt(v), 2)


def _same(a, b) -> bool:
	return abs(flt(a) - flt(b)) < 0.005


def _business_date(property: str) -> str:
	from kamra.business_date import ensure_business_date, get_business_date
	ensure_business_date(property)
	return str(get_business_date(property))


def _lock(property: str):
	"""One go-live run per property at a time: a second click waits for the
	first to commit, then finds its rows already posted."""
	frappe.db.get_value("Property", property, "name", for_update=True)


# ── companies ────────────────────────────────────────────────────────────────

COMPANY_SYNONYMS = {
	"company_name": ["company name", "company", "corporate", "account name",
	                 "corporate name", "name", "organisation", "organization"],
	"tax_id": ["tax id", "gstin", "gst no", "gst number", "vat no",
	           "vat number", "trn", "tin", "tax number"],
	"contact_name": ["contact name", "contact person", "contact"],
	"contact_phone": ["contact phone", "phone", "mobile", "contact number"],
	"contact_email": ["contact email", "email", "e-mail"],
	"credit_allowed": ["credit allowed", "credit", "on credit", "bill to company",
	                   "city ledger"],
	"credit_limit": ["credit limit", "limit"],
	"credit_days": ["credit days", "payment terms", "credit period", "terms",
	                "payment days", "credit terms", "due days"],
	"account_number": ["account no", "account number", "ar account",
	                   "ledger account"],
}


def _normalize_companies(csv_text: str):
	headers, raw = _parse_csv(csv_text)
	mapping = _map_headers(headers, COMPANY_SYNONYMS)
	if "company_name" not in mapping:
		return headers, mapping, [], [{
			"row": 0, "name": "",
			"error": "Couldn't find a Company Name column. Use Kamra's "
			         "companies template."}]
	rows, issues, seen = [], [], set()
	for i, r in enumerate(raw, start=1):
		def get(f, r=r):
			return (r.get(mapping.get(f, ""), "") or "").strip()
		name = get("company_name")
		problems = []
		if not name:
			problems.append("no company name")
		elif _norm(name) in seen:
			problems.append("listed twice")
		try:
			limit = _amount(get("credit_limit"))
		except ValueError as e:
			problems.append(str(e))
			limit = None
		if limit is not None and limit < 0:
			problems.append("credit limit can't be negative")
		days = None
		raw_days = get("credit_days")
		if raw_days and _norm(raw_days) in ("immediate", "onreceipt",
		                                    "dueonreceipt", "cod"):
			days = 0
		elif raw_days:
			# "30", "30 days", "Net 30"; 0 = due on the invoice date
			digits = re.sub(r"[^0-9]", "", raw_days)
			if not digits or int(digits) > 365:
				problems.append(f"unreadable credit days '{raw_days}'")
			else:
				days = int(digits)
		if problems:
			issues.append({"row": i, "name": name, "error": "; ".join(problems)})
			continue
		seen.add(_norm(name))
		rows.append({
			"company_name": name,
			"tax_id": get("tax_id") or None,
			"contact_name": get("contact_name") or None,
			"contact_phone": get("contact_phone") or None,
			"contact_email": get("contact_email") or None,
			# a credit limit implies the company is on credit
			"credit_allowed": _yes(get("credit_allowed"), bool(limit)),
			"credit_limit": _money(limit or 0),
			# blank = the property's default payment terms
			"credit_days": days,
			"account_number": get("account_number") or None,
		})
	return headers, mapping, rows, issues


def _find_company(name: str) -> str | None:
	if not name:
		return None
	if frappe.db.exists("Corporate Account", name):
		return name
	key = _norm(name)
	for c in frappe.get_all("Corporate Account", pluck="name",
	                        limit_page_length=0):
		if _norm(c) == key:
			return c
	return None


def _account(property: str, company: str) -> str | None:
	return frappe.db.get_value(
		"City Ledger Account",
		{"property": property, "company": company, "disabled": 0}, "name")


@frappe.whitelist(methods=["POST"])
@require_roles("Finance")
def preview_companies(property: str, csv_text: str):
	"""Dry run of the companies file: column mapping, which companies are
	new and which already exist (they are updated, never duplicated)."""
	headers, mapping, rows, issues = _normalize_companies(csv_text)
	existing = sum(1 for r in rows if _find_company(r["company_name"]))
	return {
		"headers": headers, "mapping": mapping,
		"unmapped": [h for h in headers if h not in mapping.values()],
		"ok": len(rows), "skipped": len(issues),
		"new": len(rows) - existing, "existing": existing,
		"on_credit": sum(1 for r in rows if r["credit_allowed"]),
		"issues": issues[:25], "sample": rows[:10],
	}


@frappe.whitelist(methods=["POST"])
@require_roles("Finance")
def run_companies(property: str, csv_text: str):
	"""Create or update each company (an upsert, so a re-run changes
	nothing) and, for a company on credit, its city ledger account at this
	property with the credit limit."""
	from kamra.ledger import _ar_account
	_lock(property)
	_h, _m, rows, issues = _normalize_companies(csv_text)
	created = updated = 0
	errors = list(issues)
	for i, row in enumerate(rows, start=1):
		sp = f"golive_co_{i}"
		frappe.db.savepoint(sp)
		try:
			name = _find_company(row["company_name"])
			doc = frappe.get_doc("Corporate Account", name) if name else \
				frappe.new_doc("Corporate Account")
			if not name:
				doc.company_name = row["company_name"]
			for src, field in (("tax_id", "gstin"),
			                   ("contact_name", "contact_name"),
			                   ("contact_phone", "contact_phone"),
			                   ("contact_email", "contact_email")):
				if row[src]:
					doc.set(field, row[src])
			doc.credit_allowed = 1 if row["credit_allowed"] else 0
			if name:
				doc.save(ignore_permissions=True)
				updated += 1
			else:
				doc.insert(ignore_permissions=True)
				created += 1
			if row["credit_allowed"]:
				acc = frappe.get_doc("City Ledger Account",
				                     _ar_account(property, doc.name))
				acc.credit_limit = row["credit_limit"]
				if row["credit_days"] is not None:
					# an explicit value is the company's own terms (0 = due
					# on the invoice date); blank keeps the property default
					acc.credit_days = row["credit_days"]
					acc.use_default_credit_days = 0
				if row["account_number"]:
					acc.account_number = row["account_number"]
				acc.save(ignore_permissions=True)
		except Exception as e:
			frappe.db.rollback(save_point=sp)
			errors.append({"row": i, "name": row["company_name"],
			               "error": str(e)[:160]})
	from kamra.savings import log_action
	log_action("import_companies", "Property", property, property,
	           minutes_saved=len(rows),
	           rationale=f"Go-live: {created} companies created, "
	                     f"{updated} updated, {len(errors)} skipped",
	           channel="API")
	return {"created": created, "updated": updated, "errors": errors}


# ── opening balances ─────────────────────────────────────────────────────────

OPENING_SYNONYMS = {
	"type": ["type", "balance type", "category", "kind", "ledger"],
	"reservation_no": ["reservation no", "reservation number", "res no",
	                   "reservation id", "booking id", "booking no",
	                   "booking number", "confirmation no",
	                   "confirmation number"],
	"guest_name": ["guest name", "guest", "name", "primary guest"],
	"room": ["room", "room no", "room number"],
	"check_in": ["check in", "check-in", "checkin", "arrival",
	             "arrival date", "check in date"],
	"check_out": ["check out", "check-out", "checkout", "departure",
	              "departure date", "check out date"],
	"room_type": ["room type", "room category"],
	"company": ["company", "company name", "corporate", "account",
	            "account name", "bill to"],
	"invoice_no": ["invoice no", "invoice number", "invoice", "bill no",
	               "bill number"],
	"invoice_date": ["invoice date", "bill date", "date"],
	"amount": ["amount", "balance", "outstanding", "closing balance",
	           "amount due", "deposit", "deposit amount", "advance"],
	"mode": ["mode", "payment mode", "paid by", "payment method"],
}

TYPES = {
	"inhouse": "in_house", "inhouseguest": "in_house", "guest": "in_house",
	"guestledger": "in_house", "folio": "in_house", "guestfolio": "in_house",
	"cityledger": "ar", "ar": "ar", "company": "ar", "receivable": "ar",
	"accountsreceivable": "ar", "debtor": "ar", "invoice": "ar",
	"deposit": "deposit", "advance": "deposit", "advancedeposit": "deposit",
	"depositledger": "deposit",
}
LABELS = {"in_house": "In-house guest balances",
          "ar": "City ledger (AR) by company",
          "deposit": "Advance deposits"}
DEPOSIT_STATUSES = ("Confirmed", "Pending Payment", "Held")


def _find_reservation(property: str, row: dict, statuses) -> tuple:
	"""The Kamra stay a row means: by the old reservation number the
	bookings import kept, else guest + arrival, else (in house) the room.
	Returns (name, error)."""
	from kamra.migrate import import_key
	base = {"property": property, "status": ("in", statuses)}
	if row.get("reservation_no"):
		name = frappe.db.get_value("Reservation", {
			**base, "idempotency_key": import_key(
				{"reservation_no": row["reservation_no"]})})
		if name:
			return name, None
	hits = []
	if row.get("guest_name") and row.get("check_in"):
		hits = frappe.get_all("Reservation", filters={
			**base, "guest_name": row["guest_name"],
			"check_in_date": row["check_in"]}, pluck="name")
	if not hits and row.get("room") and "Checked In" in statuses:
		hits = frappe.get_all("Reservation", filters={
			**base, "room": row["room"]}, pluck="name")
	if len(hits) == 1:
		return hits[0], None
	if len(hits) > 1:
		return None, "matches more than one stay - add the Reservation No"
	what = "in-house stay" if "Checked In" in statuses else "upcoming booking"
	return None, (f"no {what} found - import the bookings first "
	              "(same Reservation No, or guest name + check-in)")


def _ar_key(row: dict) -> str:
	ident = row.get("invoice_no") or "|".join(
		str(row.get(k) or "") for k in ("invoice_date", "amount", "guest_name"))
	digest = hashlib.sha1(f"{_norm(row['company'])}|{ident}".encode()).hexdigest()
	return f"{AR_KEY}{digest[:20]}"


def _normalize_opening(property: str, csv_text: str):
	"""Parse and match every row. Returns (headers, mapping, items, issues,
	dayfirst). In-house and deposit rows are summed per stay - two lines
	for one guest are one balance."""
	headers, raw = _parse_csv(csv_text)
	mapping = _map_headers(headers, OPENING_SYNONYMS)
	missing = [f for f in ("type", "amount") if f not in mapping]
	if missing:
		return headers, mapping, [], [{
			"row": 0, "type": "", "who": "",
			"error": "Couldn't find column(s) for: " + ", ".join(missing)
			         + ". Use Kamra's opening-balance template."}], True
	dayfirst = _detect_dayfirst(
		[r.get(mapping.get(f, ""), "") for r in raw
		 for f in ("check_in", "invoice_date")])
	from kamra.localization import pack_for, payment_modes
	modes = payment_modes(pack_for(property))
	rooms = {_norm(r.room_number): r.name for r in frappe.get_all(
		"Room", filters={"property": property},
		fields=["name", "room_number"])}

	stays: dict = {}  # (category, reservation) -> item
	items, issues = [], []
	for i, r in enumerate(raw, start=1):
		def get(f, r=r):
			return (r.get(mapping.get(f, ""), "") or "").strip()
		cat = TYPES.get(_norm(get("type")))
		row = {
			"reservation_no": get("reservation_no") or None,
			"guest_name": get("guest_name") or None,
			"room": rooms.get(_norm(get("room"))) if get("room") else None,
			"check_in": _parse_date(get("check_in"), dayfirst),
			"check_out": _parse_date(get("check_out"), dayfirst),
			"room_type": get("room_type") or None,
			"company": get("company") or None,
			"invoice_no": get("invoice_no") or None,
			"invoice_date": _parse_date(get("invoice_date"), dayfirst),
		}
		who = row["guest_name"] or row["company"] or row["reservation_no"] or ""
		problems = []
		if not cat:
			problems.append(f"unknown type '{get('type')}' (use In-house, "
			                "City ledger or Deposit)")
		try:
			amount = _amount(get("amount"))
		except ValueError as e:
			problems.append(str(e))
			amount = None
		if amount is None and not problems:
			problems.append("no amount")
		if get("room") and not row["room"]:
			problems.append(f"unknown room '{get('room')}'")
		if get("check_in") and not row["check_in"]:
			problems.append("unreadable check-in date")
		if get("invoice_date") and not row["invoice_date"]:
			problems.append("unreadable invoice date")

		if not problems and cat in ("in_house", "deposit"):
			statuses = ("Checked In",) if cat == "in_house" else DEPOSIT_STATUSES
			res, err = _find_reservation(property, row, statuses)
			if err:
				problems.append(err)
			if cat == "deposit":
				if amount is not None and amount <= 0:
					problems.append("a deposit must be positive")
				mode = get("mode") or "Bank Transfer"
				match = next((m for m in modes if _norm(m) == _norm(mode)), None)
				if not match:
					problems.append(f"unknown payment mode '{mode}' "
					                f"(use: {', '.join(modes)})")
				row["mode"] = match
			if not problems:
				key = (cat, res)
				if key in stays:
					stays[key]["amount"] = _money(stays[key]["amount"] + amount)
					stays[key]["rows"].append(i)
				else:
					stays[key] = {
						"category": cat, "reservation": res,
						"guest_name": frappe.db.get_value(
							"Reservation", res, "guest_name"),
						"amount": _money(amount), "mode": row.get("mode"),
						"rows": [i]}
					items.append(stays[key])
		elif not problems and cat == "ar":
			company = _find_company(row["company"])
			if not row["company"]:
				problems.append("no company")
			elif not company:
				problems.append(f"unknown company '{row['company']}' - "
				                "import the companies file first")
			elif not frappe.db.get_value(
					"Corporate Account", company, "credit_allowed"):
				problems.append(f"{company} is not on credit (Credit "
				                "Allowed) - it can't carry a city ledger balance")
			if amount == 0:
				problems.append("a city ledger line needs an amount")
			if not problems:
				row.update({"company": company, "amount": _money(amount)})
				items.append({
					"category": "ar", "company": company,
					"guest_name": row["guest_name"],
					"invoice_no": row["invoice_no"],
					"invoice_date": row["invoice_date"],
					"check_in": row["check_in"], "check_out": row["check_out"],
					"room_type": row["room_type"], "amount": _money(amount),
					"key": _ar_key(row), "rows": [i]})
		if problems:
			issues.append({"row": i, "type": get("type"), "who": who,
			               "error": "; ".join(problems)})
	for it in items:
		it["posted"] = _posted(property, it)
	return headers, mapping, items, issues, dayfirst


def _posted(property: str, item: dict) -> bool:
	"""Is this item in Kamra already? The idempotency check."""
	if item["category"] == "in_house":
		return bool(_opening_lines(item["reservation"]))
	if item["category"] == "deposit":
		return bool(frappe.db.exists("Folio Payment", {
			"reference": DEPOSIT_REF + item["reservation"],
			"parenttype": "Folio"}))
	if item["amount"] > 0:
		return bool(frappe.db.exists("Reservation", {
			"property": property, "idempotency_key": item["key"]}))
	return bool(frappe.db.exists("City Ledger Entry", {
		"property": property, "reference": item["key"]}))


def _opening_lines(reservation: str) -> list:
	return frappe.db.sql(
		"""SELECT fc.name, fc.amount FROM `tabFolio Charge` fc
		   JOIN `tabFolio` f ON fc.parent = f.name
		   WHERE fc.charge_type = 'Opening Balance' AND f.folio_type = 'Guest'
		     AND f.reservation = %s""", reservation, as_dict=True)


def _summary(items: list, issues: list) -> list[dict]:
	out = []
	for cat, label in LABELS.items():
		mine = [i for i in items if i["category"] == cat]
		out.append({
			"category": cat, "label": label, "count": len(mine),
			"total": _money(sum(i["amount"] for i in mine)),
			"already_posted": sum(1 for i in mine if i["posted"]),
		})
	return out


@frappe.whitelist(methods=["POST"])
@require_roles("Finance")
def preview_opening(property: str, csv_text: str):
	"""Dry run of the opening-balance file: what each row matched, totals
	per category, what is already posted (a re-run skips it) and every row
	that can't be posted. Nothing is written."""
	headers, mapping, items, issues, dayfirst = _normalize_opening(
		property, csv_text)
	return {
		"headers": headers, "mapping": mapping,
		"unmapped": [h for h in headers if h not in mapping.values()],
		"date_format": "day-first (DD/MM)" if dayfirst else "month-first (MM/DD)",
		"business_date": _business_date(property),
		"ok": len(items), "skipped": len(issues),
		"categories": _summary(items, issues),
		"issues": issues[:50],
		"sample": [{k: v for k, v in i.items() if k != "key"}
		           for i in items[:15]],
	}


def _post_in_house(property: str, item: dict, bd: str):
	"""One Opening Balance line on the in-house guest's folio - posted even
	at zero, because it also marks the stay as carried forward: checkout
	bills nights from this date on (folio.post_remaining_nights)."""
	from kamra.folio import _recalculate, open_folio
	from kamra.ledger import code_for_charge_type, save_folio
	res = frappe.get_doc("Reservation", item["reservation"])
	res.flags.carried_forward = True  # no one-time fees on this folio
	doc = frappe.get_doc("Folio", open_folio(res))
	if doc.status == "Closed":
		frappe.throw(_("The guest folio is already closed."))
	doc.append("charges", {
		"posting_date": bd,
		"charge_type": "Opening Balance",
		"transaction_code": code_for_charge_type("Opening Balance"),
		"reservation": res.name,
		"description": OPENING_LABEL,
		"qty": 1, "rate": item["amount"], "amount": item["amount"],
		"gst_rate": 0, "auto_posted": 1,
	})
	_recalculate(doc)
	save_folio(doc)  # posts the line to the Guest ledger


def _post_deposit(property: str, item: dict, bd: str):
	"""An Advance payment on the booking's folio, held in the Deposit ledger
	until check-in - like record_advance, but not through today's till: the
	money was taken by the old system."""
	from kamra.api import _confirm_status
	from kamra.folio import _recalculate, open_folio
	from kamra.ledger import record_payment_ledger
	res = frappe.get_doc("Reservation", item["reservation"])
	doc = frappe.get_doc("Folio", open_folio(res))
	row = doc.append("payments", {
		"posting_date": bd,
		"payment_kind": "Advance",
		"mode": item["mode"],
		"amount": item["amount"],
		"reference": DEPOSIT_REF + res.name,
	})
	_recalculate(doc)
	doc.save(ignore_permissions=True)
	record_payment_ledger(doc, row.as_dict())
	_confirm_status(res)  # a Held / Pending Payment booking is now secured
	frappe.db.set_value("Reservation", res.name, "advance_paid",
	                    flt(res.advance_paid) + item["amount"],
	                    update_modified=False)


def _ar_room_type(property: str, wanted: str | None) -> str:
	from kamra.migrate import _room_type_resolver
	resolve, _names = _room_type_resolver(property)
	rt = resolve(wanted) if wanted else None
	rt = rt or frappe.db.get_value("Room Type", {"property": property}, "name")
	if not rt:
		frappe.throw(_("Set up at least one room type first."))
	return rt


def _post_ar_invoice(property: str, item: dict, bd: str):
	"""An unpaid company bill from the old system. It is kept the way Kamra
	keeps any company bill: a past stay (a history record, like the
	bookings import's) whose Company folio carries the amount as an
	Opening Balance line and is then billed to the company's AR by
	transfer_to_city_ledger - the checkout path - dated to the original
	invoice so aging stays true."""
	from kamra.api import _find_or_create_guest
	from kamra.folio import _recalculate
	from kamra.ledger import code_for_charge_type, save_folio, transfer_to_city_ledger
	company = item["company"]
	inv_date = item.get("invoice_date") or str(add_days(bd, -1))
	ci = item.get("check_in") or inv_date
	co = item.get("check_out") or str(add_days(ci, 1))
	if getdate(co) <= getdate(ci):
		co = str(add_days(ci, 1))
	guest = _find_or_create_guest(item.get("guest_name") or company, None,
	                              property)
	res = frappe.get_doc({
		"doctype": "Reservation",
		"property": property,
		"guest": guest,
		"room_type": _ar_room_type(property, item.get("room_type")),
		"check_in_date": ci, "check_out_date": co,
		"adults": 1,
		"source": "PMS",
		"channel": CHANNEL,
		# inserted quietly (no confirmation message), stamped below
		"status": "Inquiry",
		"booking_type": "Corporate",
		"company": company,
		"idempotency_key": item["key"],
		"auto_price": 0,
		"amount_after_tax": item["amount"],
		"special_requests": f"{OPENING_LABEL}: unpaid invoice "
		                    f"{item.get('invoice_no') or ''}".strip(),
	})
	# a past stay is a record (as in the bookings import): no live checks,
	# no folio of its own, no housekeeping task
	res.flags.ignore_validate = True
	res.insert(ignore_permissions=True)
	res.db_set("status", "Checked Out", update_modified=False)

	folio = frappe.get_doc({
		"doctype": "Folio",
		"property": property,
		"reservation": res.name,
		"guest": guest,
		"folio_type": "Company",
		"status": "Open",
		"opened_on": now_datetime(),
		# the company's AP knows the bill by the old number
		"invoice_number": item.get("invoice_no"),
	})
	folio.append("charges", {
		"posting_date": bd,
		"charge_type": "Opening Balance",
		"transaction_code": code_for_charge_type("Opening Balance"),
		"reservation": res.name,
		"description": f"{OPENING_LABEL}"
		               + (f" · invoice {item['invoice_no']}" if item.get("invoice_no") else ""),
		"qty": 1, "rate": item["amount"], "amount": item["amount"],
		"gst_rate": 0, "auto_posted": 1,
	})
	_recalculate(folio)
	save_folio(folio)
	transfer_to_city_ledger(folio.name, company, invoice_date=inv_date,
	                        credit_check=False)
	# billed in full to the company: the folio is done
	frappe.db.set_value("Folio", folio.name, {
		"status": "Closed", "closed_on": now_datetime()})


def _post_ar_credit(property: str, item: dict):
	"""Money a company paid ahead in the old system: a city ledger payment
	(city_ledger_settle), which clears its oldest open bills and keeps the
	rest as unapplied credit for the next one."""
	from kamra.ledger import _ar_account, city_ledger_settle
	city_ledger_settle(_ar_account(property, item["company"]),
	                   abs(item["amount"]), mode=CHANNEL,
	                   reference=item["key"])


@frappe.whitelist(methods=["POST"])
@require_roles("Finance")
def run_opening(property: str, csv_text: str):
	"""Post the opening balances. Each item is posted once: a re-run of the
	same file finds it in Kamra and skips it (and says so). Company bills
	go in before company credits, so a credit settles the oldest bill."""
	_lock(property)
	bd = _business_date(property)
	_h, _m, items, issues, _d = _normalize_opening(property, csv_text)
	posted = {c: 0 for c in LABELS}
	totals = {c: 0.0 for c in LABELS}
	already, errors = 0, list(issues)
	order = sorted(items, key=lambda i: (
		{"in_house": 0, "deposit": 1, "ar": 2}[i["category"]],
		i["amount"] < 0))
	# carried-forward balances are bookkeeping, not new business: the
	# placeholder stays and opening lines must not reach outbound webhook
	# subscribers as reservation.created / folio.posted events
	was_muted = frappe.flags.kamra_mute_webhooks
	frappe.flags.kamra_mute_webhooks = True
	try:
		for n, it in enumerate(order, start=1):
			if it["posted"]:
				already += 1
				continue
			sp = f"golive_ob_{n}"
			frappe.db.savepoint(sp)
			try:
				if it["category"] == "in_house":
					_post_in_house(property, it, bd)
				elif it["category"] == "deposit":
					_post_deposit(property, it, bd)
				elif it["amount"] > 0:
					_post_ar_invoice(property, it, bd)
				else:
					_post_ar_credit(property, it)
				posted[it["category"]] += 1
				totals[it["category"]] += it["amount"]
			except Exception as e:
				frappe.db.rollback(save_point=sp)
				errors.append({"row": it["rows"][0], "type": LABELS[it["category"]],
				               "who": it.get("guest_name") or it.get("company") or "",
				               "error": str(e)[:200]})
	finally:
		frappe.flags.kamra_mute_webhooks = was_muted
	from kamra.savings import log_action
	log_action("import_opening_balances", "Property", property, property,
	           minutes_saved=sum(posted.values()),
	           rationale="Go-live opening balances: " + ", ".join(
	               f"{posted[c]} {LABELS[c].lower()} ({totals[c]:,.2f})"
	               for c in LABELS) + f"; {already} already posted",
	           channel="API")
	return {"business_date": bd, "posted": posted,
	        "totals": {c: _money(v) for c, v in totals.items()},
	        "already_posted": already, "errors": errors}


# ── reconciliation ───────────────────────────────────────────────────────────

def _kamra_in_house(property: str) -> dict:
	rows = frappe.db.sql(
		"""SELECT f.reservation, SUM(fc.amount) AS amount
		   FROM `tabFolio Charge` fc JOIN `tabFolio` f ON fc.parent = f.name
		   WHERE f.property = %s AND f.folio_type = 'Guest'
		     AND fc.charge_type = 'Opening Balance'
		   GROUP BY f.reservation""", property, as_dict=True)
	return {r.reservation: _money(r.amount) for r in rows}


def _kamra_deposits(property: str) -> dict:
	rows = frappe.db.sql(
		"""SELECT f.reservation, SUM(fp.amount) AS amount
		   FROM `tabFolio Payment` fp JOIN `tabFolio` f ON fp.parent = f.name
		   WHERE f.property = %s AND fp.reference LIKE %s
		   GROUP BY f.reservation""",
		(property, DEPOSIT_REF + "%"), as_dict=True)
	return {r.reservation: _money(r.amount) for r in rows}


def _kamra_ar(property: str) -> dict:
	"""key -> (company, signed amount) for every carried-over AR item."""
	out = {}
	for r in frappe.db.sql(
			"""SELECT r.idempotency_key AS k, r.company, SUM(c.debit) AS amount
			   FROM `tabReservation` r
			   JOIN `tabFolio` f ON f.reservation = r.name
			   JOIN `tabCity Ledger Entry` c ON c.folio = f.name AND c.kind = 'Invoice'
			   WHERE r.property = %s AND r.idempotency_key LIKE %s
			   GROUP BY r.idempotency_key, r.company""",
			(property, AR_KEY + "%"), as_dict=True):
		out[r.k] = (r.company, _money(r.amount))
	for r in frappe.db.sql(
			"""SELECT c.reference AS k, a.company, SUM(c.credit) AS amount
			   FROM `tabCity Ledger Entry` c
			   JOIN `tabCity Ledger Account` a ON a.name = c.account
			   WHERE c.property = %s AND c.kind = 'Payment' AND c.reference LIKE %s
			   GROUP BY c.reference, a.company""",
			(property, AR_KEY + "%"), as_dict=True):
		out[r.k] = (r.company, -_money(r.amount))
	return out


def _compare(cat: str, label: str, file_map: dict, kamra_map: dict,
             name_of) -> dict:
	"""file_map / kamra_map: key -> amount."""
	problems = []
	for k, amt in file_map.items():
		if k not in kamra_map:
			problems.append(f"{name_of(k)}: {amt:,.2f} in the file, not in Kamra")
		elif not _same(kamra_map[k], amt):
			problems.append(f"{name_of(k)}: file {amt:,.2f}, "
			                f"Kamra {kamra_map[k]:,.2f}")
	for k, amt in kamra_map.items():
		if k not in file_map:
			problems.append(f"{name_of(k)}: {amt:,.2f} in Kamra, not in the file")
	ft, kt = _money(sum(file_map.values())), _money(sum(kamra_map.values()))
	return {
		"category": cat, "label": label,
		"file_count": len(file_map), "file_total": ft,
		"kamra_count": len(kamra_map), "kamra_total": kt,
		"matched": not problems and len(file_map) == len(kamra_map)
		           and _same(ft, kt),
		"problems": problems[:50],
	}


def _guest(res: str) -> str:
	g = frappe.db.get_value("Reservation", res, "guest_name") or ""
	return f"{g} ({res})" if g else res


@frappe.whitelist(methods=["POST"])
@require_roles("Finance")
def reconcile(property: str, opening_csv: str | None = None,
              companies_csv: str | None = None,
              bookings_csv: str | None = None):
	"""Counts and totals in each go-live file against what is now in Kamra,
	per category. `ready` is true only when every category matches and no
	row of any file was left out - the gate before the hotel goes live."""
	categories, blockers = [], []

	if bookings_csv and bookings_csv.strip():
		from kamra.migrate import _normalize, import_key
		_h, _m, rows, issues, _d = _normalize(property, bookings_csv, "auto")
		keys = {import_key(r): r for r in rows}
		found = set(frappe.get_all("Reservation", filters={
			"property": property,
			"idempotency_key": ("in", list(keys) or [""])},
			pluck="idempotency_key"))
		problems = [f"{r['guest_name']} {r['check_in']}: not in Kamra"
		            for k, r in keys.items() if k not in found]
		if len(keys) < len(rows):
			problems.append(f"{len(rows) - len(keys)} row(s) repeat another "
			                "row - only one of each is imported")
		problems += [f"Row {i['row']} ({i['guest']}): {i['error']}"
		             for i in issues]
		categories.append({
			"category": "bookings", "label": "Bookings",
			"file_count": len(keys) + len(issues), "file_total": None,
			"kamra_count": len(found), "kamra_total": None,
			"matched": not problems, "problems": problems[:50]})

	if companies_csv and companies_csv.strip():
		_h, _m, rows, issues = _normalize_companies(companies_csv)
		problems, found = [], 0
		for r in rows:
			name = _find_company(r["company_name"])
			if not name:
				problems.append(f"{r['company_name']}: not in Kamra")
				continue
			found += 1
			credit = frappe.db.get_value("Corporate Account", name,
			                             "credit_allowed")
			if bool(credit) != r["credit_allowed"]:
				problems.append(f"{name}: credit allowed differs")
			if r["credit_allowed"]:
				acc = _account(property, name)
				limit = frappe.db.get_value("City Ledger Account", acc,
				                            "credit_limit") if acc else None
				if acc is None or not _same(limit, r["credit_limit"]):
					problems.append(f"{name}: credit limit "
					                f"{r['credit_limit']:,.2f} not set")
				terms = frappe.db.get_value(
					"City Ledger Account", acc,
					["credit_days", "use_default_credit_days"],
					as_dict=True) if acc else None
				if r["credit_days"] is not None and (
						terms is None or terms.use_default_credit_days
						or int(terms.credit_days or 0) != r["credit_days"]):
					problems.append(f"{name}: credit days "
					                f"{r['credit_days']} not set")
		problems += [f"Row {i['row']} ({i['name']}): {i['error']}"
		             for i in issues]
		categories.append({
			"category": "companies", "label": "Companies",
			"file_count": len(rows) + len(issues),
			"file_total": _money(sum(r["credit_limit"] for r in rows)),
			"kamra_count": found, "kamra_total": None,
			"matched": not problems, "problems": problems[:50]})

	if opening_csv and opening_csv.strip():
		_h, _m, items, issues, _d = _normalize_opening(property, opening_csv)
		def by(cat):
			return {i["reservation"]: i["amount"] for i in items
			        if i["category"] == cat}
		categories.append(_compare("in_house", LABELS["in_house"],
		                           by("in_house"), _kamra_in_house(property),
		                           _guest))
		categories.append(_compare("deposit", LABELS["deposit"],
		                           by("deposit"), _kamra_deposits(property),
		                           _guest))
		ar_file = {i["key"]: i for i in items if i["category"] == "ar"}
		kamra_ar = _kamra_ar(property)
		names = {**{k: v[0] for k, v in kamra_ar.items()},
		         **{k: i["company"] + (f" {i['invoice_no']}" if i["invoice_no"] else "")
		            for k, i in ar_file.items()}}
		ar = _compare("ar", LABELS["ar"],
		              {k: i["amount"] for k, i in ar_file.items()},
		              {k: v[1] for k, v in kamra_ar.items()},
		              lambda k: names.get(k, k))
		# the per-company view a finance team ties to the old AR report
		companies: dict = {}
		for i in ar_file.values():
			companies.setdefault(i["company"], {"company": i["company"],
			                                    "file": 0.0, "kamra": 0.0})
			companies[i["company"]]["file"] += i["amount"]
		for company, amt in kamra_ar.values():
			companies.setdefault(company, {"company": company,
			                               "file": 0.0, "kamra": 0.0})
			companies[company]["kamra"] += amt
		ar["by_company"] = [{
			**c, "file": _money(c["file"]), "kamra": _money(c["kamra"]),
			"balance": _money(frappe.db.sql(
				"""SELECT COALESCE(SUM(debit - credit), 0)
				   FROM `tabCity Ledger Entry` WHERE account = %s""",
				_account(property, c["company"]) or "")[0][0]),
			"matched": _same(c["file"], c["kamra"]),
		} for c in sorted(companies.values(), key=lambda c: c["company"])]
		categories.append(ar)
		if issues:
			blockers += [f"Opening balances row {i['row']} ({i['who']}): "
			             f"{i['error']}" for i in issues]

	# every in-house stay brought over by the bookings import needs its
	# opening balance (zero if settled) - without it checkout would bill
	# the nights the old system already billed
	have = _kamra_in_house(property)
	for r in frappe.get_all("Reservation", filters={
			"property": property, "status": "Checked In",
			"idempotency_key": ("like", "import:%")},
			fields=["name", "guest_name"]):
		if r.name not in have:
			blockers.append(f"{r.guest_name} ({r.name}) is in house but "
			                "has no opening balance row - add it, even at 0")

	for c in categories:
		if not c["matched"]:
			blockers.append(f"{c['label']} don't match yet")
	return {
		"business_date": _business_date(property),
		"categories": categories,
		"blockers": blockers[:100],
		"ready": bool(categories) and not blockers,
	}
