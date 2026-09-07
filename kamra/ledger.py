"""Append-only folio ledger + city ledger + document helpers.

Folio Charge / Folio Payment remain the guest-facing projection; every
posting also writes a Folio Ledger Entry so voids become reversals and
the four Opera ledgers (Guest / Deposit / AR / Package) can be balanced."""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe.utils import now_datetime, nowdate

from kamra.authz import require_roles
from kamra.business_date import get_business_date


CHARGE_TYPE_TO_CODE = {
	"Room": ("1000", "Room Charge", "Rooms", "Room"),
	"Meal Plan": ("1100", "Meal Plan", "F&B", "Meal Plan"),
	"Food & Beverage": ("2000", "Food & Beverage", "F&B", "Food & Beverage"),
	"Minibar": ("2100", "Minibar", "F&B", "Minibar"),
	"Laundry": ("3000", "Laundry", "Other", "Laundry"),
	"Spa": ("3100", "Spa", "Other", "Spa"),
	"Early Check-in": ("1200", "Early Check-in", "Rooms", "Early Check-in"),
	"Late Checkout": ("1210", "Late Checkout", "Rooms", "Late Checkout"),
	"Cleaning Fee": ("1300", "Cleaning Fee", "Rooms", "Cleaning Fee"),
	"Discount": ("9000", "Discount", "Adjustment", "Discount"),
	"Misc": ("8000", "Miscellaneous", "Other", "Misc"),
	"Allowance": ("9100", "Allowance", "Adjustment", "Allowance"),
}

PAYMENT_CODES = {
	"Payment": ("9001", "Payment", "Payment"),
	"Advance": ("9002", "Advance / Deposit", "Payment"),
	"Security Deposit": ("9003", "Security Deposit", "Payment"),
	"Refund": ("9004", "Refund", "Payment"),
}


def ensure_default_transaction_codes(property: str | None = None) -> None:
	for charge_type, (code, desc, group, _) in CHARGE_TYPE_TO_CODE.items():
		if frappe.db.exists("Transaction Code", code):
			continue
		frappe.get_doc({
			"doctype": "Transaction Code",
			"code": code,
			"description": desc,
			"property": property,
			"txn_type": "Adjustment" if charge_type in ("Discount", "Allowance")
			            else "Revenue",
			"revenue_group": group,
			"subgroup": charge_type,
			"charge_type": charge_type,
			"is_alcohol": 0,
		}).insert(ignore_permissions=True)
	for kind, (code, desc, group) in PAYMENT_CODES.items():
		if frappe.db.exists("Transaction Code", code):
			continue
		frappe.get_doc({
			"doctype": "Transaction Code",
			"code": code,
			"description": desc,
			"txn_type": "Payment",
			"revenue_group": group,
			"subgroup": kind,
		}).insert(ignore_permissions=True)


def code_for_charge_type(charge_type: str) -> str | None:
	meta = CHARGE_TYPE_TO_CODE.get(charge_type)
	if not meta:
		return None
	code = meta[0]
	if not frappe.db.exists("Transaction Code", code):
		ensure_default_transaction_codes()
	return code if frappe.db.exists("Transaction Code", code) else None


def write_ledger_entry(
	*,
	property: str,
	folio: str,
	ledger: str,
	debit: float = 0,
	credit: float = 0,
	description: str | None = None,
	transaction_code: str | None = None,
	cashier: str | None = None,
	session: str | None = None,
	reversal_of: str | None = None,
	source_doctype: str | None = None,
	source_name: str | None = None,
) -> str:
	bd = get_business_date(property)
	doc = frappe.get_doc({
		"doctype": "Folio Ledger Entry",
		"property": property,
		"folio": folio,
		"ledger": ledger,
		"business_date": bd,
		"transaction_code": transaction_code,
		"description": (description or "")[:140] or None,
		"debit": float(debit or 0),
		"credit": float(credit or 0),
		"cashier": cashier,
		"session": session,
		"reversal_of": reversal_of,
		"source_doctype": source_doctype,
		"source_name": source_name,
		"posted_by": frappe.session.user,
		"posted_at": now_datetime(),
	})
	doc.insert(ignore_permissions=True)
	return doc.name


def record_charge_ledger(folio_doc, charge_row, session: str | None = None):
	code = charge_row.get("transaction_code") or code_for_charge_type(
		charge_row.get("charge_type") or "Misc")
	amt = float(charge_row.get("total") or charge_row.get("amount") or 0)
	# Charges debit the guest ledger (guest owes more)
	write_ledger_entry(
		property=folio_doc.property,
		folio=folio_doc.name,
		ledger="Guest",
		debit=amt if amt >= 0 else 0,
		credit=abs(amt) if amt < 0 else 0,
		description=charge_row.get("description") or charge_row.get("charge_type"),
		transaction_code=code,
		session=session,
		source_doctype="Folio Charge",
		source_name=charge_row.get("name"),
	)


def record_payment_ledger(folio_doc, payment_row, session: str | None = None):
	kind = payment_row.get("payment_kind") or "Payment"
	code_meta = PAYMENT_CODES.get(kind)
	code = code_meta[0] if code_meta else None
	if code and not frappe.db.exists("Transaction Code", code):
		ensure_default_transaction_codes()
	amt = float(payment_row.get("amount") or 0)
	ledger = "Deposit" if kind in ("Advance", "Security Deposit") else "Guest"
	# Payments credit the ledger (reduce what guest owes / increase liability)
	write_ledger_entry(
		property=folio_doc.property,
		folio=folio_doc.name,
		ledger=ledger,
		debit=abs(amt) if amt < 0 else 0,
		credit=amt if amt >= 0 else 0,
		description=f"{kind} {payment_row.get('mode') or ''}".strip(),
		transaction_code=code,
		session=session,
		source_doctype="Folio Payment",
		source_name=payment_row.get("name"),
	)


def reverse_ledger_for_charge(property: str, folio: str, charge_row_name: str,
                              reason: str = "") -> str | None:
	"""Find the original ledger entry for a charge and post a reversal."""
	orig = frappe.db.get_value(
		"Folio Ledger Entry",
		{"source_doctype": "Folio Charge", "source_name": charge_row_name,
		 "folio": folio, "reversal_of": ["in", ["", None]]},
		["name", "debit", "credit", "transaction_code", "description", "ledger"],
		as_dict=True,
	)
	# Also skip if already reversed
	if orig and frappe.db.exists("Folio Ledger Entry", {"reversal_of": orig.name}):
		return None
	if not orig:
		# Soft fallback: no original entry (pre-ledger data)
		return None
	return write_ledger_entry(
		property=property,
		folio=folio,
		ledger=orig.ledger or "Guest",
		debit=float(orig.credit or 0),
		credit=float(orig.debit or 0),
		description=f"VOID: {reason or orig.description or ''}"[:140],
		transaction_code=orig.transaction_code,
		reversal_of=orig.name,
		source_doctype="Folio Charge",
		source_name=charge_row_name,
	)


@frappe.whitelist()
@require_roles("Finance", "Front Desk", "Hotel Admin", "Kamra Agent")
def ledger_balances(property: str, business_date: str | None = None):
	"""Four-ledger trial balance for a property (optionally as-of a date)."""
	date = business_date or get_business_date(property)
	rows = frappe.db.sql(
		"""
		SELECT ledger,
		       COALESCE(SUM(debit), 0) AS debit,
		       COALESCE(SUM(credit), 0) AS credit
		FROM `tabFolio Ledger Entry`
		WHERE property = %(property)s AND business_date <= %(date)s
		GROUP BY ledger
		""",
		{"property": property, "date": date}, as_dict=True,
	)
	ledgers = {r.ledger: {
		"ledger": r.ledger,
		"debit": float(r.debit),
		"credit": float(r.credit),
		"balance": float(r.debit) - float(r.credit),
	} for r in rows}
	for name in ("Guest", "Deposit", "AR", "Package"):
		ledgers.setdefault(name, {
			"ledger": name, "debit": 0.0, "credit": 0.0, "balance": 0.0,
		})
	total_debit = sum(v["debit"] for v in ledgers.values())
	total_credit = sum(v["credit"] for v in ledgers.values())
	return {
		"business_date": date,
		"ledgers": [ledgers[k] for k in ("Guest", "Deposit", "AR", "Package")],
		"total_debit": total_debit,
		"total_credit": total_credit,
		"in_balance": abs(total_debit - total_credit) < 0.02,
	}


@frappe.whitelist()
@require_roles("Finance", "Front Desk", "Hotel Admin", "Kamra Agent")
def journal_by_transaction_code(property: str, business_date: str | None = None):
	date = business_date or get_business_date(property)
	rows = frappe.db.sql(
		"""
		SELECT COALESCE(transaction_code, '—') AS transaction_code,
		       COALESCE(SUM(debit), 0) AS debit,
		       COALESCE(SUM(credit), 0) AS credit,
		       COUNT(*) AS entries
		FROM `tabFolio Ledger Entry`
		WHERE property = %(property)s AND business_date = %(date)s
		GROUP BY transaction_code
		ORDER BY transaction_code
		""",
		{"property": property, "date": date}, as_dict=True,
	)
	for r in rows:
		r["description"] = frappe.db.get_value(
			"Transaction Code", r.transaction_code, "description") or ""
	return {"business_date": date, "rows": rows}


@frappe.whitelist()
@require_roles("Finance", "Hotel Admin", "Kamra Agent")
def financial_activity(property: str, business_date: str | None = None,
                       user: str | None = None):
	date = business_date or get_business_date(property)
	filters: dict[str, Any] = {"property": property, "business_date": date}
	if user:
		filters["posted_by"] = user
	entries = frappe.get_all(
		"Folio Ledger Entry",
		filters=filters,
		fields=["name", "folio", "ledger", "transaction_code", "description",
		        "debit", "credit", "posted_by", "posted_at", "session"],
		order_by="posted_at desc",
		limit_page_length=500,
	)
	return {"business_date": date, "entries": entries}


# ── City ledger (AR) ─────────────────────────────────────────────────────────

def _ar_account(property: str, company: str) -> str:
	name = frappe.db.get_value(
		"City Ledger Account",
		{"property": property, "company": company, "disabled": 0},
		"name",
	)
	if name:
		return name
	doc = frappe.get_doc({
		"doctype": "City Ledger Account",
		"property": property,
		"company": company,
		"account_number": f"AR-{company[:20]}",
		"credit_limit": 0,
		"balance": 0,
	})
	doc.insert(ignore_permissions=True)
	return doc.name


def transfer_to_city_ledger(folio: str, company: str | None = None) -> dict:
	"""Move an unpaid folio balance to company AR at checkout."""
	doc = frappe.get_doc("Folio", folio)
	balance = float(doc.balance or 0)
	if balance <= 0:
		frappe.throw("No balance to transfer to city ledger.")
	if not company and doc.get("reservation"):
		company = frappe.db.get_value("Reservation", doc.reservation, "company")
	if not company and doc.get("group_booking"):
		company = frappe.db.get_value(
			"Group Booking", doc.group_booking, "company")
	if not company:
		frappe.throw("A company is required for city ledger transfer.")
	if not frappe.db.get_value("Company", company, "credit_allowed"):
		frappe.throw(f"{company} is not allowed on city ledger (credit).")
	account = _ar_account(doc.property, company)
	bd = get_business_date(doc.property)
	# Zero the guest folio with a Company Credit payment
	doc.append("payments", {
		"posting_date": bd,
		"payment_kind": "Payment",
		"mode": "Company Credit",
		"amount": balance,
		"reference": f"city-ledger:{account}",
	})
	from kamra.folio import _recalculate
	_recalculate(doc)
	doc.save(ignore_permissions=True)

	write_ledger_entry(
		property=doc.property,
		folio=doc.name,
		ledger="AR",
		debit=balance,
		description=f"Transfer to city ledger {company}",
		transaction_code=PAYMENT_CODES["Payment"][0]
		                 if frappe.db.exists("Transaction Code",
		                                     PAYMENT_CODES["Payment"][0])
		                 else None,
		source_doctype="Folio",
		source_name=doc.name,
	)
	frappe.get_doc({
		"doctype": "City Ledger Entry",
		"account": account,
		"property": doc.property,
		"posting_date": bd,
		"kind": "Invoice",
		"folio": doc.name,
		"invoice_number": doc.invoice_number,
		"debit": balance,
		"credit": 0,
		"reference": doc.name,
	}).insert(ignore_permissions=True)
	acc = frappe.get_doc("City Ledger Account", account)
	acc.balance = float(acc.balance or 0) + balance
	acc.save(ignore_permissions=True)
	return {"account": account, "amount": balance, "balance": acc.balance}


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Front Desk", "Kamra Agent")
def city_ledger_transfer(folio: str, company: str | None = None,
                         pin: str | None = None):
	from kamra.authz import require_cashier_pin
	prop = frappe.db.get_value("Folio", folio, "property")
	require_cashier_pin(prop, pin)
	return transfer_to_city_ledger(folio, company)


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Hotel Admin", "Kamra Agent")
def city_ledger_settle(account: str, amount: float, mode: str = "Bank Transfer",
                       reference: str | None = None):
	if float(amount) <= 0:
		frappe.throw("Amount must be positive.")
	acc = frappe.get_doc("City Ledger Account", account)
	bd = get_business_date(acc.property)
	frappe.get_doc({
		"doctype": "City Ledger Entry",
		"account": account,
		"property": acc.property,
		"posting_date": bd,
		"kind": "Payment",
		"debit": 0,
		"credit": float(amount),
		"reference": reference or mode,
	}).insert(ignore_permissions=True)
	acc.balance = float(acc.balance or 0) - float(amount)
	acc.save(ignore_permissions=True)
	return {"account": account, "balance": acc.balance}


@frappe.whitelist()
@require_roles("Finance", "Hotel Admin", "Front Desk", "Kamra Agent")
def city_ledger_aging(property: str):
	accounts = frappe.get_all(
		"City Ledger Account",
		filters={"property": property, "disabled": 0},
		fields=["name", "company", "account_number", "balance", "credit_limit"],
	)
	# Simple aging: open debit entries by age buckets
	out = []
	for a in accounts:
		entries = frappe.get_all(
			"City Ledger Entry",
			filters={"account": a.name, "kind": "Invoice"},
			fields=["posting_date", "debit", "credit", "folio", "invoice_number"],
			order_by="posting_date asc",
		)
		# payments reduce oldest first (FIFO) for display only
		paid = frappe.db.sql(
			"""SELECT COALESCE(SUM(credit - debit), 0) FROM `tabCity Ledger Entry`
			   WHERE account=%s AND kind='Payment'""",
			a.name,
		)[0][0] or 0
		remaining_pay = float(paid)
		buckets = {"current": 0.0, "b30": 0.0, "b60": 0.0, "b90": 0.0, "b90p": 0.0}
		from frappe.utils import date_diff, getdate
		today = getdate(nowdate())
		for e in entries:
			amt = float(e.debit or 0) - float(e.credit or 0)
			if remaining_pay > 0:
				take = min(remaining_pay, amt)
				amt -= take
				remaining_pay -= take
			if amt <= 0:
				continue
			age = date_diff(today, e.posting_date)
			if age <= 30:
				buckets["current"] += amt
			elif age <= 60:
				buckets["b30"] += amt
			elif age <= 90:
				buckets["b60"] += amt
			elif age <= 120:
				buckets["b90"] += amt
			else:
				buckets["b90p"] += amt
		out.append({**a, **buckets})
	return {"accounts": out}


# ── Advance / Force bill ─────────────────────────────────────────────────────

@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance", "Kamra Agent")
def force_advance_bill(reservation: str, nights: str = "entire",
                       pin: str | None = None):
	"""Post future room (+ meal) charges ahead of night audit.

	nights: 'tonight' | 'entire' | integer string of nights.
	"""
	from kamra.folio import (open_folio, post_room_night, _nightly_room_rate,
	                         _recalculate)
	from kamra.authz import require_cashier_pin
	from frappe.utils import add_days, getdate, date_diff

	res = frappe.get_doc("Reservation", reservation)
	require_cashier_pin(res.property, pin)
	if res.status not in ("Confirmed", "Checked In", "Held", "Pending Payment"):
		frappe.throw("Advance bill only for active reservations.")
	folio_name = open_folio(res)
	folio = frappe.get_doc("Folio", folio_name)
	ci = getdate(res.check_in_date)
	co = getdate(res.check_out_date)
	stay = max(date_diff(co, ci), 1)
	if str(nights).lower() in ("tonight", "1"):
		n = 1
	elif str(nights).lower() in ("entire", "all", ""):
		n = stay
	else:
		n = max(1, min(int(nights), stay))

	posted = []
	start = ci if res.status != "Checked In" else getdate(
		get_business_date(res.property))
	for i in range(n):
		day = add_days(start, i)
		if getdate(day) >= co:
			break
		# Skip if already auto-posted for this date
		exists = any(
			c.charge_type == "Room" and str(c.posting_date) == str(day)
			and c.auto_posted
			for c in folio.charges
		)
		if exists:
			continue
		ok = post_room_night(res, str(day))
		if ok:
			posted.append(str(day))
	folio.reload()
	_recalculate(folio)
	folio.save(ignore_permissions=True)
	amount = sum(
		float(c.total or 0) for c in folio.charges
		if str(c.posting_date) in posted
	)
	return {
		"folio": folio.name,
		"nights_posted": posted,
		"amount": amount,
		"balance": folio.balance,
	}


# ── Proforma + Credit Note ───────────────────────────────────────────────────

@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance", "Kamra Agent")
def generate_proforma(folio: str, notes: str | None = None):
	from kamra.api import folio_invoice
	inv = folio_invoice(folio)
	f = inv["folio"]
	doc = frappe.get_doc({
		"doctype": "Proforma Folio",
		"property": f.get("property"),
		"folio": folio,
		"reservation": f.get("reservation"),
		"generated_on": now_datetime(),
		"generated_by": frappe.session.user,
		"grand_total": f.get("grand_total"),
		"balance": f.get("balance"),
		"payload": json.dumps(inv, default=str),
		"notes": notes,
	})
	doc.insert(ignore_permissions=True)
	return {"proforma": doc.name, "invoice": inv}


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Hotel Admin", "Kamra Agent")
def issue_credit_note(folio: str, amount: float, reason: str,
                      pin: str | None = None):
	from kamra.authz import require_cashier_pin
	doc = frappe.get_doc("Folio", folio)
	require_cashier_pin(doc.property, pin)
	if not doc.invoice_number:
		frappe.throw("Credit notes need a closed invoice as the original.")
	if float(amount) <= 0:
		frappe.throw("Amount must be positive.")
	if not (reason or "").strip():
		frappe.throw("A reason is required.")
	bd = get_business_date(doc.property)
	# Sequential CN number
	count = frappe.db.count("Credit Note", {"property": doc.property}) + 1
	cn_number = f"CN-{doc.property[:6]}-{bd.replace('-', '')}-{count:04d}"
	cn = frappe.get_doc({
		"doctype": "Credit Note",
		"property": doc.property,
		"folio": folio,
		"original_invoice": doc.invoice_number,
		"credit_note_number": cn_number,
		"issue_date": bd,
		"amount": float(amount),
		"tax_amount": 0,
		"reason": reason.strip()[:500],
		"status": "Issued",
		"issued_by": frappe.session.user,
	})
	cn.insert(ignore_permissions=True)
	# Allowance on folio if still open; else AR credit
	if doc.status == "Open":
		doc.append("charges", {
			"posting_date": bd,
			"charge_type": "Allowance",
			"description": f"Credit note {cn_number}: {reason.strip()[:80]}",
			"qty": 1,
			"rate": -float(amount),
			"amount": -float(amount),
			"gst_rate": 0,
		})
		from kamra.folio import _recalculate
		_recalculate(doc)
		doc.save(ignore_permissions=True)
	else:
		# Post AR credit if company linked on the reservation
		company = None
		if doc.get("reservation"):
			company = frappe.db.get_value(
				"Reservation", doc.reservation, "company")
		if company:
			account = _ar_account(doc.property, company)
			frappe.get_doc({
				"doctype": "City Ledger Entry",
				"account": account,
				"property": doc.property,
				"posting_date": bd,
				"kind": "Credit Note",
				"folio": folio,
				"invoice_number": cn_number,
				"debit": 0,
				"credit": float(amount),
				"reference": doc.invoice_number,
				"notes": reason.strip()[:200],
			}).insert(ignore_permissions=True)
			acc = frappe.get_doc("City Ledger Account", account)
			acc.balance = float(acc.balance or 0) - float(amount)
			acc.save(ignore_permissions=True)
	write_ledger_entry(
		property=doc.property,
		folio=folio,
		ledger="Guest" if doc.status == "Open" else "AR",
		credit=float(amount),
		description=f"Credit note {cn_number}",
		source_doctype="Credit Note",
		source_name=cn.name,
	)
	return {"credit_note": cn.name, "number": cn_number}


# ── Folio history / reprints / batch ─────────────────────────────────────────

@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance", "Kamra Agent")
def record_folio_reprint(folio: str, document: str = "Guest Folio",
                         reason: str | None = None):
	prop, inv = frappe.db.get_value(
		"Folio", folio, ["property", "invoice_number"])
	prev = frappe.db.count("Folio Reprint", {"folio": folio}) + 1
	doc = frappe.get_doc({
		"doctype": "Folio Reprint",
		"property": prop,
		"folio": folio,
		"invoice_number": inv,
		"reprint_of": document,
		"printed_on": now_datetime(),
		"printed_by": frappe.session.user,
		"reason": reason,
		"revision": prev,
	})
	doc.insert(ignore_permissions=True)
	return {"reprint": doc.name, "revision": prev}


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Hotel Admin", "Kamra Agent")
def folio_history(property: str, query: str | None = None,
                  status: str | None = None):
	filters: list = [["property", "=", property]]
	if status:
		filters.append(["status", "=", status])
	rows = frappe.get_all(
		"Folio",
		filters=filters,
		fields=["name", "guest_name", "reservation", "status", "invoice_number",
		        "grand_total", "payments_total", "balance", "closed_on",
		        "modified"],
		order_by="modified desc",
		limit_page_length=200,
	)
	if query:
		q = query.lower()
		rows = [r for r in rows if q in (r.guest_name or "").lower()
		        or q in (r.invoice_number or "").lower()
		        or q in (r.name or "").lower()
		        or q in (r.reservation or "").lower()]
	# Attach reprint counts
	for r in rows:
		r["reprints"] = frappe.db.count("Folio Reprint", {"folio": r.name})
	return {"folios": rows}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance", "Kamra Agent")
def batch_post_charge(folios: str | list, charge_type: str, amount: float,
                      description: str | None = None, pin: str | None = None):
	"""Post the same charge to many folios (group / event)."""
	import json as _json
	if isinstance(folios, str):
		folios = _json.loads(folios)
	if not folios:
		frappe.throw("Pick at least one folio.")
	from kamra.authz import require_cashier_pin
	prop = frappe.db.get_value("Folio", folios[0], "property")
	require_cashier_pin(prop, pin)
	bd = get_business_date(prop)
	code = code_for_charge_type(charge_type)
	posted = []
	for fn in folios:
		doc = frappe.get_doc("Folio", fn)
		if doc.status != "Open":
			continue
		row = {
			"posting_date": bd,
			"charge_type": charge_type,
			"transaction_code": code,
			"description": description or charge_type,
			"qty": 1,
			"rate": float(amount),
			"amount": float(amount),
			"gst_rate": 0,
		}
		doc.append("charges", row)
		from kamra.folio import _recalculate
		_recalculate(doc)
		doc.save(ignore_permissions=True)
		# last charge row
		charge = doc.charges[-1]
		try:
			from kamra.cashier import require_open_session
			sess = require_open_session(prop)
		except Exception:
			sess = None
		record_charge_ledger(doc, charge.as_dict(), session=sess)
		posted.append(fn)
	return {"posted": posted, "count": len(posted)}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance", "Kamra Agent")
def batch_print_folios(folios: str | list):
	import json as _json
	if isinstance(folios, str):
		folios = _json.loads(folios)
	out = []
	for fn in folios:
		out.append(record_folio_reprint(fn, "Guest Folio", "batch print"))
	return {"reprints": out}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Kamra Agent")
def quick_checkout(reservation: str, pin: str | None = None):
	"""Settle + close folio + check out in one step when balance is zero
	or fully covered by company credit."""
	from kamra.api import close_folio, check_out
	res = frappe.get_doc("Reservation", reservation)
	folio_name = frappe.db.get_value(
		"Folio", {"reservation": reservation, "folio_type": "Guest",
		          "status": "Open"}, "name")
	if not folio_name:
		frappe.throw("No open guest folio.")
	folio = frappe.get_doc("Folio", folio_name)
	if float(folio.balance or 0) > 0.009:
		company = frappe.db.get_value(
			"Reservation", reservation, "company")
		if company and frappe.db.get_value(
				"Company", company, "credit_allowed"):
			transfer_to_city_ledger(folio_name, company)
		else:
			frappe.throw(
				f"Balance ₹{float(folio.balance):,.2f} remains - collect payment "
				"or transfer to city ledger first.")
	close_folio(folio_name, pin=pin)
	return check_out(reservation)


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Kamra Agent")
def group_checkout(group: str, pin: str | None = None):
	"""Quick-checkout every Checked In reservation on a group."""
	res_names = frappe.get_all(
		"Reservation",
		filters={"revenue_group": group, "status": "Checked In"},
		pluck="name",
	)
	results = []
	for r in res_names:
		try:
			results.append({"reservation": r, **quick_checkout(r, pin=pin)})
		except Exception as e:
			results.append({"reservation": r, "error": str(e)})
	return {"results": results}


# ── FX desk ──────────────────────────────────────────────────────────────────

@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Kamra Agent")
def list_exchange_rates(property: str):
	from frappe.utils import getdate
	today = get_business_date(property)
	rows = frappe.get_all(
		"Exchange Rate",
		filters={"property": property, "disabled": 0},
		fields=["name", "currency", "rate_date", "buy_rate", "sell_rate",
		        "service_tax_pct", "max_exchange"],
		order_by="currency asc, rate_date desc",
	)
	# Keep latest per currency
	seen = set()
	latest = []
	for r in rows:
		if r.currency in seen:
			continue
		seen.add(r.currency)
		latest.append(r)
	return {"business_date": today, "rates": latest}


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Hotel Admin", "Kamra Agent")
def upsert_exchange_rate(property: str, currency: str, buy_rate: float,
                         sell_rate: float, service_tax_pct: float = 0,
                         max_exchange: float | None = None):
	bd = get_business_date(property)
	existing = frappe.db.get_value(
		"Exchange Rate",
		{"property": property, "currency": currency, "rate_date": bd},
		"name",
	)
	if existing:
		doc = frappe.get_doc("Exchange Rate", existing)
		doc.buy_rate = float(buy_rate)
		doc.sell_rate = float(sell_rate)
		doc.service_tax_pct = float(service_tax_pct or 0)
		doc.max_exchange = max_exchange
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc({
			"doctype": "Exchange Rate",
			"property": property,
			"currency": currency.upper(),
			"rate_date": bd,
			"buy_rate": float(buy_rate),
			"sell_rate": float(sell_rate),
			"service_tax_pct": float(service_tax_pct or 0),
			"max_exchange": max_exchange,
		})
		doc.insert(ignore_permissions=True)
	return doc.as_dict()


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Kamra Agent")
def currency_calculator(property: str, currency: str, fx_amount: float,
                        direction: str = "Buy"):
	rate_row = frappe.get_all(
		"Exchange Rate",
		filters={"property": property, "currency": currency, "disabled": 0},
		fields=["buy_rate", "sell_rate", "service_tax_pct", "max_exchange"],
		order_by="rate_date desc",
		limit_page_length=1,
	)
	rate_row = rate_row[0] if rate_row else None
	if not rate_row:
		frappe.throw(f"No exchange rate for {currency}.")
	rate = float(rate_row.buy_rate if direction == "Buy" else rate_row.sell_rate)
	local = float(fx_amount) * rate
	tax = local * float(rate_row.service_tax_pct or 0) / 100.0
	return {
		"currency": currency,
		"direction": direction,
		"fx_amount": float(fx_amount),
		"exchange_rate": rate,
		"local_amount": round(local, 2),
		"service_tax": round(tax, 2),
		"total": round(local + (tax if direction == "Buy" else 0), 2),
		"max_exchange": rate_row.max_exchange,
	}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance", "Kamra Agent")
def post_exchange(property: str, currency: str, fx_amount: float,
                  direction: str = "Buy", folio: str | None = None,
                  guest: str | None = None, pin: str | None = None):
	from kamra.authz import require_cashier_pin
	from kamra.cashier import require_open_session, record_cashier_txn
	require_cashier_pin(property, pin)
	calc = currency_calculator(property, currency, fx_amount, direction)
	if calc.get("max_exchange") and float(fx_amount) > float(calc["max_exchange"]):
		frappe.throw("Exceeds per-transaction FX limit.")
	sess = require_open_session(property)
	bd = get_business_date(property)
	txn = frappe.get_doc({
		"doctype": "Exchange Transaction",
		"property": property,
		"session": sess,
		"guest": guest,
		"folio": folio,
		"direction": direction,
		"currency": currency.upper(),
		"fx_amount": float(fx_amount),
		"exchange_rate": calc["exchange_rate"],
		"local_amount": calc["local_amount"],
		"service_tax": calc["service_tax"],
		"business_date": bd,
		"posted_by": frappe.session.user,
		"posted_at": now_datetime(),
	})
	txn.insert(ignore_permissions=True)
	# Buy foreign = hotel pays local cash out; Sell = hotel receives local cash
	amt = -calc["total"] if direction == "Buy" else calc["local_amount"]
	record_cashier_txn(
		property, "Exchange", "Cash", amt,
		folio=folio, reference=txn.name,
		notes=f"{direction} {fx_amount} {currency} @ {calc['exchange_rate']}",
		session=sess,
	)
	if folio and direction == "Sell":
		# Optionally record as folio payment in foreign currency
		fdoc = frappe.get_doc("Folio", folio)
		fdoc.append("payments", {
			"posting_date": bd,
			"payment_kind": "Payment",
			"mode": "Cash",
			"amount": calc["local_amount"],
			"currency": currency.upper(),
			"fx_amount": float(fx_amount),
			"exchange_rate": calc["exchange_rate"],
			"reference": f"fx:{txn.name}",
		})
		from kamra.folio import _recalculate
		_recalculate(fdoc)
		fdoc.save(ignore_permissions=True)
	return {"transaction": txn.name, **calc}


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Hotel Admin", "Kamra Agent")
def exchange_history(property: str, business_date: str | None = None):
	date = business_date or get_business_date(property)
	rows = frappe.get_all(
		"Exchange Transaction",
		filters={"property": property, "business_date": date},
		fields=["name", "direction", "currency", "fx_amount", "exchange_rate",
		        "local_amount", "service_tax", "folio", "guest", "posted_by",
		        "posted_at"],
		order_by="posted_at desc",
	)
	return {"business_date": date, "transactions": rows}


# ── Reason codes ─────────────────────────────────────────────────────────────

DEFAULT_REASONS = [
	("VOID-GUEST", "Guest declined / changed mind", "Void", 0),
	("VOID-ERR", "Posting error", "Void", 0),
	("VOID-DUP", "Duplicate charge", "Void", 0),
	("ADJ-COMP", "Complimentary adjustment", "Adjust", 1),
	("ADJ-RATE", "Rate correction", "Adjust", 0),
	("RATE-PROMO", "Promotional rate change", "Rate Change", 0),
	("RATE-MGR", "Manager rate override", "Rate Change", 1),
	("REF-DEP", "Security deposit refund", "Refund", 0),
	("REF-OVER", "Overpayment refund", "Refund", 0),
	("PO-VENDOR", "Vendor paid-out", "Paid Out", 0),
	("NC-MGMT", "Management NC", "NC", 1),
]


def ensure_default_reason_codes() -> None:
	for code, desc, cat, sup in DEFAULT_REASONS:
		if frappe.db.exists("Reason Code", code):
			continue
		frappe.get_doc({
			"doctype": "Reason Code",
			"code": code,
			"description": desc,
			"category": cat,
			"requires_supervisor": sup,
		}).insert(ignore_permissions=True)


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Kamra Agent")
def list_reason_codes(category: str | None = None):
	ensure_default_reason_codes()
	filters: dict[str, Any] = {"disabled": 0}
	if category:
		filters["category"] = category
	return frappe.get_all(
		"Reason Code", filters=filters,
		fields=["name", "code", "description", "category", "requires_supervisor"],
		order_by="category asc, code asc",
	)


def require_reason(category: str, reason_code: str | None, free_text: str = "",
                   supervisor_pin: str | None = None, property: str | None = None):
	"""Validate a reason code; if it requires supervisor, check supervisor PIN."""
	ensure_default_reason_codes()
	if not reason_code and not (free_text or "").strip():
		frappe.throw("A reason code or reason text is required.")
	if reason_code and frappe.db.exists("Reason Code", reason_code):
		row = frappe.db.get_value(
			"Reason Code", reason_code,
			["category", "requires_supervisor", "disabled"], as_dict=True)
		if row.disabled:
			frappe.throw("That reason code is disabled.")
		if row.category != category:
			frappe.throw(f"Reason code is for {row.category}, not {category}.")
		if row.requires_supervisor:
			# Supervisor = Hotel Admin PIN or a second user's PIN via pin check
			if not supervisor_pin:
				frappe.throw("SUPERVISOR_PIN_REQUIRED: this reason needs approval.")
			# Accept any valid cashier PIN from a Finance/Admin user by
			# temporarily validating against the current user's PIN is wrong;
			# instead require the property's require_cashier_pin path with a
			# flag. Practical approach: Hotel Admin / Finance role + their PIN.
			roles = set(frappe.get_roles())
			if not (roles & {"Hotel Admin", "Finance", "System Manager",
			                 "Administrator"}):
				frappe.throw("Supervisor role required for this reason.")
			from kamra.authz import require_cashier_pin
			if property:
				require_cashier_pin(property, supervisor_pin)
	return reason_code or free_text.strip()[:140]
