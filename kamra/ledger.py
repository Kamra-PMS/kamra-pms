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
	# extra beds in a let room - room revenue, so it lands in the Rooms group
	"Extra Guests": ("1320", "Extra Guests", "Rooms", "Extra Guests"),
	"Pet Charge": ("1330", "Pet Charge", "Rooms", "Pet Charge"),
	# collected for the municipality / city - a levy, not hotel revenue
	"Room Levy": ("1310", "Room Levy", "Levies", "Room Levy"),
	"Discount": ("9000", "Discount", "Adjustment", "Discount"),
	"Misc": ("8000", "Miscellaneous", "Other", "Misc"),
	"Allowance": ("9100", "Allowance", "Adjustment", "Allowance"),
	# a balance carried over from the previous PMS at go-live (kamra.golive):
	# not revenue of the day - the old system already counted it
	"Opening Balance": ("8900", "Opening Balance (go-live)", "Opening Balance",
	                    "Opening Balance"),
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
			"txn_type": "Adjustment" if charge_type in (
				"Discount", "Allowance", "Opening Balance")
			            else "Tax" if charge_type == "Room Levy" else "Revenue",
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
	business_date: str | None = None,
) -> str:
	"""The one Folio Ledger Entry writer. `business_date` defaults to the
	property's current business date; only a backfill passes its own
	(and needs backdate permission or allow_past_transaction)."""
	from kamra.business_date import assert_transaction_date
	bd = assert_transaction_date(property, business_date, label="Business date")
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


def record_charge_ledger(folio_doc, charge_row, session: str | None = None,
                         business_date: str | None = None):
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
		business_date=business_date,
	)


def unsaved_charges(folio_doc) -> list:
	"""Charge rows appended since the folio was loaded (no name yet). Take
	this before save; after save the same row objects carry their names."""
	return [c for c in folio_doc.charges if not c.name]


def ledger_charges(folio_doc, rows, session: str | None = None) -> None:
	"""Post saved charge rows to the Guest ledger through
	record_charge_ledger - the path for automatic postings (room nights,
	meal plans, levies, policy fees, cleaning fees, add-ons, POS). A row
	already on the ledger is skipped, so a caller can never double post.
	Like a manual charge, a ledger failure is logged, not raised: the
	folio line stands and the backfill patch can pick it up."""
	for row in rows:
		if not row.name:
			continue
		if frappe.db.exists("Folio Ledger Entry", {
				"source_doctype": "Folio Charge", "source_name": row.name,
				"folio": folio_doc.name}):
			continue
		try:
			record_charge_ledger(folio_doc, row.as_dict(), session=session)
		except Exception:
			frappe.log_error(title="ledger charge write failed")


def save_folio(folio_doc, session: str | None = None) -> None:
	"""Save (or insert) a folio and post any newly appended charge rows to
	the ledger."""
	new_rows = unsaved_charges(folio_doc)
	if folio_doc.is_new():
		folio_doc.insert(ignore_permissions=True)
	else:
		folio_doc.save(ignore_permissions=True)
	ledger_charges(folio_doc, new_rows, session=session)


def record_payment_ledger(folio_doc, payment_row, session: str | None = None,
                          ledger: str | None = None):
	"""ledger overrides where the row lands: a security-deposit refund is
	stored as a Refund row on the folio but releases the Deposit ledger
	(the liability), not the Guest ledger."""
	kind = payment_row.get("payment_kind") or "Payment"
	code_meta = PAYMENT_CODES.get(kind)
	code = code_meta[0] if code_meta else None
	if code and not frappe.db.exists("Transaction Code", code):
		ensure_default_transaction_codes()
	amt = float(payment_row.get("amount") or 0)
	ledger = ledger or ("Deposit" if kind in ("Advance", "Security Deposit")
	                    else "Guest")
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


ADVANCE_APPLIED = "Advance applied to the stay"


def _advance_held(folio: str, payment_row: str) -> float:
	"""What of one Advance payment still sits in the Deposit ledger."""
	return round(float(frappe.db.sql(
		"""SELECT COALESCE(SUM(credit - debit), 0) FROM `tabFolio Ledger Entry`
		   WHERE ledger = 'Deposit' AND source_doctype = 'Folio Payment'
		     AND source_name = %s AND folio = %s""",
		(payment_row, folio))[0][0] or 0), 2)


def transfer_advances_to_guest(reservation: str,
                               business_date: str | None = None) -> float:
	"""An advance is a liability (Deposit ledger) only until the guest is in
	house. From check-in it pays the stay, so each Advance payment moves out
	of the Deposit ledger and credits the Guest ledger - the same two legs
	as a security deposit applied to the bill (deposit._transfer_to_guest).

	Idempotent per payment: only what is still held for that payment row
	moves, so calling it again (check-in, a later advance, check-out, the
	backfill patch) never moves money twice. Returns the amount moved."""
	code = PAYMENT_CODES["Advance"][0]
	if not frappe.db.exists("Transaction Code", code):
		ensure_default_transaction_codes()
	if not frappe.db.exists("Transaction Code", code):
		code = None
	moved = 0.0
	for folio in frappe.get_all("Folio", filters={"reservation": reservation},
	                            fields=["name", "property"]):
		for row in frappe.get_all(
				"Folio Payment",
				filters={"parent": folio.name, "parenttype": "Folio",
				         "payment_kind": "Advance"},
				pluck="name"):
			held = _advance_held(folio.name, row)
			if held <= 0.005:
				continue
			for ledger, debit, credit in (("Deposit", held, 0),
			                              ("Guest", 0, held)):
				write_ledger_entry(
					property=folio.property, folio=folio.name, ledger=ledger,
					debit=debit, credit=credit, description=ADVANCE_APPLIED,
					transaction_code=code, source_doctype="Folio Payment",
					source_name=row, business_date=business_date)
			moved += held
	return moved


def _charge_ledger_net(folio: str, charge_row_name: str) -> float:
	return float(frappe.db.sql(
		"""SELECT COALESCE(SUM(debit - credit), 0) FROM `tabFolio Ledger Entry`
		   WHERE source_doctype = 'Folio Charge' AND source_name = %s
		     AND folio = %s""", (charge_row_name, folio))[0][0] or 0)


def _original_charge_entry(folio: str, charge_row_name: str):
	return frappe.db.get_value(
		"Folio Ledger Entry",
		{"source_doctype": "Folio Charge", "source_name": charge_row_name,
		 "folio": folio, "reversal_of": ["in", ["", None]]},
		["name", "debit", "credit", "transaction_code", "description", "ledger"],
		as_dict=True,
	)


def reverse_ledger_for_charge(property: str, folio: str, charge_row_name: str,
                              reason: str = "", amount: float | None = None,
                              prefix: str = "VOID") -> str | None:
	"""Post a reversal against a charge's ledger entry. By default it
	reverses what is still on the ledger for the line (a line partly split
	away only reverses its remainder); `amount` reverses part of it (a
	split). Returns None when there is nothing left to reverse."""
	orig = _original_charge_entry(folio, charge_row_name)
	if not orig:
		# Soft fallback: no original entry (pre-ledger data)
		return None
	net = _charge_ledger_net(folio, charge_row_name)
	if amount is not None:
		# a part of a debit line (or of a credit line, sign kept)
		net = abs(float(amount)) if net >= 0 else -abs(float(amount))
	net = round(net, 2)
	if abs(net) < 0.005:
		return None  # already fully reversed
	return write_ledger_entry(
		property=property,
		folio=folio,
		ledger=orig.ledger or "Guest",
		debit=-net if net < 0 else 0,
		credit=net if net > 0 else 0,
		description=f"{prefix}: {reason or orig.description or ''}"[:140],
		transaction_code=orig.transaction_code,
		reversal_of=orig.name,
		source_doctype="Folio Charge",
		source_name=charge_row_name,
	)


@frappe.whitelist()
@require_roles("Finance", "Front Desk", "Hotel Admin", "Night Auditor", "Kamra Agent")
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
	# These four are subsidiary (control) ledgers, not a full double-entry
	# book: a charge debits Guest and its revenue side lives in the GL the
	# accounting export feeds, a payment credits Guest and the cash side is
	# the cashier's. So total debits exceed total credits by exactly what
	# guests owe - comparing the two flagged every hotel with an open bill.
	# The real test of these ledgers is that they agree with the bills they
	# summarise: each folio's Guest + Deposit postings net to its balance.
	recon = folio_reconciliation(property) if str(date) >= str(
		get_business_date(property)) else None
	return {
		"business_date": date,
		"ledgers": [ledgers[k] for k in ("Guest", "Deposit", "AR", "Package")],
		"total_debit": total_debit,
		"total_credit": total_credit,
		# true / false from the folio check; null for a past date, where
		# today's folio balances cannot be compared with the old ledger
		"in_balance": recon["in_balance"] if recon else None,
		"reconciliation": recon,
	}


def folio_reconciliation(property: str, limit: int = 20) -> dict:
	"""Guest + Deposit ledger postings per folio against the folio's own
	balance (charges less payments). A folio whose ledger nets to something
	else - a posting that never reached the ledger, or one the folio lost -
	is a genuine break; the rest is money guests owe, not an imbalance."""
	rows = frappe.db.sql(
		"""
		SELECT f.name AS folio, f.folio_type, f.status,
		       COALESCE(f.balance, 0) AS balance,
		       COALESCE(e.net, 0) AS ledger
		FROM `tabFolio` f
		LEFT JOIN (
			SELECT folio, SUM(debit - credit) AS net
			FROM `tabFolio Ledger Entry`
			WHERE property = %(p)s AND ledger IN ('Guest', 'Deposit')
			GROUP BY folio
		) e ON e.folio = f.name
		WHERE f.property = %(p)s
		  AND ABS(COALESCE(f.balance, 0) - COALESCE(e.net, 0)) >= 0.02
		ORDER BY f.creation DESC
		""", {"p": property}, as_dict=True)
	ledger_net = float(frappe.db.sql(
		"""SELECT COALESCE(SUM(debit - credit), 0) FROM `tabFolio Ledger Entry`
		   WHERE property = %s AND ledger IN ('Guest', 'Deposit')""",
		property)[0][0] or 0)
	folios_net = float(frappe.db.sql(
		"""SELECT COALESCE(SUM(balance), 0) FROM `tabFolio`
		   WHERE property = %s""", property)[0][0] or 0)
	return {
		"in_balance": not rows,
		"ledger_net": round(ledger_net, 2),
		"folios_net": round(folios_net, 2),
		"difference": round(sum(float(r.balance) - float(r.ledger)
		                        for r in rows), 2),
		"folios_out": len(rows),
		"folios": [{"folio": r.folio, "folio_type": r.folio_type,
		            "status": r.status, "balance": round(float(r.balance), 2),
		            "ledger": round(float(r.ledger), 2),
		            "difference": round(float(r.balance) - float(r.ledger), 2)}
		           for r in rows[:limit]],
	}


@frappe.whitelist()
@require_roles("Finance", "Front Desk", "Hotel Admin", "Night Auditor", "Kamra Agent")
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


def company_payer_of(folio) -> str | None:
	"""The company that pays this folio on credit, or None when the guest
	pays it. Only a Company folio (the stay's company) or a group master
	(the group's company) is the company's bill; Guest and Extra folios -
	liquor, extras - are always the guest's."""
	kind = folio.get("folio_type") or "Guest"
	company = None
	if kind == "Company" and folio.get("reservation"):
		company = frappe.db.get_value(
			"Reservation", folio.get("reservation"), "company")
	elif kind == "Group" and folio.get("group_booking"):
		company = frappe.db.get_value(
			"Group Booking", folio.get("group_booking"), "company")
	if company and frappe.db.get_value(
			"Corporate Account", company, "credit_allowed"):
		return company
	return None


def effective_credit_days(account: str | None, property: str | None = None) -> int:
	"""The payment terms of a city ledger account. With "use property
	default" on (the default), the property's `default_credit_days`;
	otherwise its own credit_days as entered - 0 is due on the invoice date."""
	if account:
		row = frappe.db.get_value(
			"City Ledger Account", account,
			["credit_days", "use_default_credit_days", "property"], as_dict=True) or {}
		property = property or row.get("property")
		if row and not int(row.get("use_default_credit_days") or 0):
			return max(int(row.get("credit_days") or 0), 0)
	from kamra.settings import get_setting
	return max(int(get_setting(property, "default_credit_days") or 0), 0)


def due_date_for(account: str | None, invoice_date, property: str | None = None) -> str:
	"""Invoice date + the account's effective credit days."""
	from frappe.utils import add_days
	return str(add_days(invoice_date, effective_credit_days(account, property)))


def _transfer_company(folio, company: str | None = None) -> str | None:
	"""Who a city ledger transfer bills: the company asked for, else the
	stay's, else the group's."""
	if not company and folio.get("reservation"):
		company = frappe.db.get_value("Reservation", folio.reservation, "company")
	if not company and folio.get("group_booking"):
		company = frappe.db.get_value(
			"Group Booking", folio.group_booking, "company")
	return company


def transfer_to_city_ledger(folio: str, company: str | None = None,
                            invoice_date: str | None = None,
                            credit_check: bool = True,
                            credit_override_reason: str | None = None,
                            account: str | None = None) -> dict:
	"""Move an unpaid folio balance to company AR at checkout.
	`invoice_date` dates the AR invoice when it is older than today - an
	unpaid bill carried over from the old system at go-live, so aging
	counts from when the company was really billed. The bill is due
	`invoice date + credit days` (the account's, else the property's).

	`credit_check` runs the property's credit control (kamra.credit) first:
	warn lets it through with a warning, block refuses unless Finance or a
	Hotel Admin overrides with a reason. Go-live passes False - those bills
	were already on credit in the old system - and checkout passes False
	because it has checked every company of the stay at once.

	`account` bills that exact City Ledger Account (it must be the
	company's) instead of the company's first open one."""
	doc = frappe.get_doc("Folio", folio)
	balance = float(doc.balance or 0)
	if balance <= 0:
		frappe.throw("No balance to transfer to city ledger.")
	company = _transfer_company(doc, company)
	if not company:
		frappe.throw("A company is required for city ledger transfer.")
	if not frappe.db.get_value("Corporate Account", company, "credit_allowed"):
		frappe.throw(f"{company} is not allowed on city ledger (credit).")
	credit = None
	if credit_check:
		from kamra.credit import enforce_company_credit
		credit = enforce_company_credit(
			company, doc.property, balance,
			override_reason=credit_override_reason,
			context="city ledger transfer",
			reference_doctype="Folio", reference_name=doc.name,
			exclude_folios=[doc.name])
	if account and frappe.db.get_value(
			"City Ledger Account", account, ["property", "company"]) != (
			doc.property, company):
		frappe.throw(f"{account} is not {company}'s account at this property.")
	account = account or _ar_account(doc.property, company)
	bd = get_business_date(doc.property)
	inv_date = invoice_date or bd
	# Zero the guest folio with a Company Credit payment
	row = doc.append("payments", {
		"posting_date": bd,
		"payment_kind": "Payment",
		"mode": "Company Credit",
		"amount": balance,
		"reference": f"city-ledger:{account}",
	})
	from kamra.folio import _recalculate
	_recalculate(doc)
	doc.save(ignore_permissions=True)

	# Two legs, like any transfer: the Company Credit payment credits the
	# guest ledger (the folio is settled) and the same amount debits AR.
	# Without the guest credit the debt sat in both ledgers at once.
	record_payment_ledger(doc, row.as_dict())
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
		"posting_date": inv_date,
		"kind": "Invoice",
		"folio": doc.name,
		"invoice_number": doc.invoice_number,
		"due_date": due_date_for(account, inv_date, doc.property),
		"debit": balance,
		"credit": 0,
		"reference": doc.name,
	}).insert(ignore_permissions=True)
	acc = frappe.get_doc("City Ledger Account", account)
	acc.balance = float(acc.balance or 0) + balance
	acc.save(ignore_permissions=True)
	# money the company already paid ahead (an unapplied credit) settles
	# this new bill straight away
	applied = apply_unapplied_credit(account, only_folio=doc.name)
	out = {"account": account, "amount": balance, "balance": acc.balance,
	       "applied_from_credit": sum(r["amount"] for r in applied)}
	if credit and not credit.get("ok"):
		out["credit"] = credit
	return out


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Front Desk", "Kamra Agent")
def city_ledger_transfer(folio: str, company: str | None = None,
                         pin: str | None = None,
                         credit_override_reason: str | None = None):
	"""Move a folio's unpaid balance to the company's city ledger. Runs the
	property's credit control: over the credit limit or with overdue bills
	it warns, or refuses (CREDIT_BLOCKED) unless Finance or a Hotel Admin
	passes `credit_override_reason`. Agents can't override."""
	from kamra.authz import require_cashier_pin
	from kamra.receivables import assert_billable
	doc = frappe.get_doc("Folio", folio)
	require_cashier_pin(doc.property, pin)
	# the stay's company too, not only one passed in: a restricted account
	# takes no new bills either way
	company = _transfer_company(doc, company)
	if company:
		assert_billable(frappe.db.get_value(
			"City Ledger Account",
			{"property": doc.property, "company": company, "disabled": 0}, "name"))
	return transfer_to_city_ledger(
		folio, company, credit_override_reason=credit_override_reason)


# A company payment is one City Ledger Entry (kind Payment, no folio) that
# reduces the account. What it pays is recorded on the books: one AR credit
# per folio in Folio Ledger Entry, sourced to that City Ledger Entry. The
# part not applied to any folio stays on the account as unapplied credit
# (the AR ledger needs a folio, so it has no AR entry until it is applied).

def _payment_code() -> str | None:
	code = PAYMENT_CODES["Payment"][0]
	if not frappe.db.exists("Transaction Code", code):
		ensure_default_transaction_codes()
	return code if frappe.db.exists("Transaction Code", code) else None


def city_ledger_open_folios(account: str) -> list[dict]:
	"""Every folio billed to this account, oldest bill first: what was
	billed (transfers less credit notes), what company payments have
	cleared, and what is still owed."""
	billed = frappe.db.sql(
		"""
		SELECT folio,
		       MIN(CASE WHEN kind = 'Invoice'
		                 THEN COALESCE(invoice_date, posting_date) END) AS invoice_date,
		       MIN(CASE WHEN kind = 'Invoice' THEN due_date END) AS due_date,
		       MIN(posting_date) AS first_date,
		       MAX(invoice_number) AS invoice_number,
		       COALESCE(SUM(debit - credit), 0) AS billed
		FROM `tabCity Ledger Entry`
		WHERE account = %s AND IFNULL(folio, '') != '' AND kind != 'Payment'
		GROUP BY folio
		""",
		account, as_dict=True,
	)
	paid = dict(frappe.db.sql(
		"""
		SELECT e.folio, COALESCE(SUM(e.credit - e.debit), 0)
		FROM `tabFolio Ledger Entry` e
		JOIN `tabCity Ledger Entry` c ON c.name = e.source_name
		WHERE e.source_doctype = 'City Ledger Entry' AND c.account = %s
		GROUP BY e.folio
		""",
		account,
	))
	out = []
	days = None
	for r in billed:
		p = float(paid.get(r.folio) or 0)
		inv = str(r.invoice_date or r.first_date)
		due = r.due_date
		if not due:
			# a bill raised before due dates were recorded: invoice date +
			# the account's terms today (the backfill patch stores it)
			if days is None:
				days = effective_credit_days(account)
			from frappe.utils import add_days
			due = add_days(inv, days)
		out.append({
			"folio": r.folio,
			"invoice_number": r.invoice_number,
			"invoice_date": inv,
			"due_date": str(due),
			"billed": round(float(r.billed), 2),
			"paid": round(p, 2),
			"outstanding": round(float(r.billed) - p, 2),
		})
	out.sort(key=lambda r: (r["invoice_date"], r["folio"]))
	return out


def _unapplied_payments(account: str) -> list[dict]:
	"""Company payments on this account with money not yet applied to a
	folio, oldest first."""
	rows = frappe.db.sql(
		"""
		SELECT c.name, c.posting_date, c.reference, c.credit - c.debit AS amount,
		       COALESCE((SELECT SUM(e.credit - e.debit) FROM `tabFolio Ledger Entry` e
		                 WHERE e.source_doctype = 'City Ledger Entry'
		                   AND e.source_name = c.name), 0) AS applied
		FROM `tabCity Ledger Entry` c
		WHERE c.account = %s AND c.kind = 'Payment' AND IFNULL(c.folio, '') = ''
		ORDER BY c.posting_date ASC, c.creation ASC
		""",
		account, as_dict=True,
	)
	out = []
	for r in rows:
		remaining = round(float(r.amount or 0) - float(r.applied or 0), 2)
		if remaining > 0.005:
			out.append({"name": r.name, "posting_date": str(r.posting_date),
			            "reference": r.reference, "remaining": remaining})
	return out


def _post_ar_credit(acc, payment: str, folio: str, amount: float,
                    reference: str | None = None,
                    business_date: str | None = None) -> str:
	return write_ledger_entry(
		property=acc.property,
		folio=folio,
		ledger="AR",
		credit=round(float(amount), 2),
		description=f"City ledger payment {acc.company}"
		            + (f" · {reference}" if reference else ""),
		transaction_code=_payment_code(),
		source_doctype="City Ledger Entry",
		source_name=payment,
		business_date=business_date,
	)


def _allocation_plan(account: str, amount: float, allocations=None) -> list[dict]:
	"""[{folio, amount}] for a payment: oldest bill first by default, or
	the caller's explicit folios (each within what that folio still owes,
	all within the payment). Whatever is left stays unapplied."""
	open_items = {r["folio"]: r for r in city_ledger_open_folios(account)
	              if r["outstanding"] > 0.005}
	if allocations in (None, "", []):
		plan, left = [], round(float(amount), 2)
		for r in open_items.values():
			if left <= 0.005:
				break
			take = round(min(left, r["outstanding"]), 2)
			plan.append({"folio": r["folio"], "amount": take})
			left = round(left - take, 2)
		return plan
	if isinstance(allocations, str):
		allocations = json.loads(allocations)
	plan, seen, total = [], set(), 0.0
	for a in allocations or []:
		folio = (a or {}).get("folio")
		amt = round(float((a or {}).get("amount") or 0), 2)
		if not amt:
			continue
		if folio in seen:
			frappe.throw(f"{folio} is listed twice.")
		seen.add(folio)
		item = open_items.get(folio)
		if not item:
			frappe.throw(f"{folio} has nothing open on this city ledger account.")
		if amt < 0:
			frappe.throw("Allocation amounts must be positive.")
		if amt > item["outstanding"] + 0.005:
			frappe.throw(f"{folio} owes {item['outstanding']:,.2f} - "
			             f"can't apply {amt:,.2f} to it.")
		total += amt
		plan.append({"folio": folio, "amount": amt})
	if total > float(amount) + 0.005:
		frappe.throw(f"Allocations ({total:,.2f}) are more than the payment "
		             f"({float(amount):,.2f}).")
	return plan


def apply_unapplied_credit(account: str, only_folio: str | None = None,
                           backdate: bool = False) -> list[dict]:
	"""Apply money the company paid but that is not yet on any folio -
	oldest payment to oldest open bill. `only_folio` limits it to one bill
	(a fresh transfer); `backdate` dates each AR credit to the later of the
	payment and the bill (used by the backfill patch)."""
	acc = frappe.get_doc("City Ledger Account", account)
	items = [r for r in city_ledger_open_folios(account)
	         if r["outstanding"] > 0.005
	         and (not only_folio or r["folio"] == only_folio)]
	applied = []
	for p in _unapplied_payments(account):
		left = p["remaining"]
		for r in items:
			if left <= 0.005:
				break
			if r["outstanding"] <= 0.005:
				continue
			take = round(min(left, r["outstanding"]), 2)
			bd = max(p["posting_date"], r["invoice_date"]) if backdate else None
			_post_ar_credit(acc, p["name"], r["folio"], take,
			                reference=p["reference"], business_date=bd)
			r["outstanding"] = round(r["outstanding"] - take, 2)
			left = round(left - take, 2)
			applied.append({"payment": p["name"], "folio": r["folio"],
			                "amount": take})
	return applied


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Hotel Admin", "Kamra Agent")
def city_ledger_settle(account: str, amount: float, mode: str = "Bank Transfer",
                       reference: str | None = None, allocations=None):
	"""Record a company's payment against its city ledger account and clear
	the AR it pays. By default it pays the oldest open bills first;
	`allocations` ([{folio, amount}]) names the folios instead. Any excess
	stays on the account as unapplied credit and settles the company's next
	bill."""
	amount = round(float(amount or 0), 2)
	if amount <= 0:
		frappe.throw("Amount must be positive.")
	acc = frappe.get_doc("City Ledger Account", account)
	if acc.disabled:
		frappe.throw("This city ledger account is disabled.")
	plan = _allocation_plan(account, amount, allocations)
	bd = get_business_date(acc.property)
	ref = (reference or "").strip() or mode
	payment = frappe.get_doc({
		"doctype": "City Ledger Entry",
		"account": account,
		"property": acc.property,
		"posting_date": bd,
		"kind": "Payment",
		"debit": 0,
		"credit": amount,
		"reference": ref[:140],
		"notes": f"{mode}" + (f" · {reference}" if reference else ""),
	}).insert(ignore_permissions=True)
	for a in plan:
		_post_ar_credit(acc, payment.name, a["folio"], a["amount"], reference=ref)
	acc.balance = float(acc.balance or 0) - amount
	acc.save(ignore_permissions=True)
	applied_total = round(sum(a["amount"] for a in plan), 2)
	from kamra.savings import log_action
	log_action("city_ledger_settle", "City Ledger Account", account,
	           acc.property,
	           rationale=f"{acc.company} paid {amount:,.2f} by {mode}"
	                     f"; applied {applied_total:,.2f} to {len(plan)} folio(s)")
	return {
		"account": account,
		"payment": payment.name,
		"balance": acc.balance,
		"applied": plan,
		"unapplied": round(amount - applied_total, 2),
	}


# Aging is by DUE date: a bill is "not due" until invoice date + the
# company's credit days, then 1-30 / 31-60 / 61-90 / 90+ days overdue.
# The older invoice-age keys (current / b30 / b60 / b90 / b90p, 30-day steps
# from the invoice date) are still returned for callers that read them.
DUE_BUCKETS = ("not_due", "d1_30", "d31_60", "d61_90", "d90p")
INVOICE_AGE_BUCKETS = ("current", "b30", "b60", "b90", "b90p")


def _netted(open_items: list[dict], unapplied: float) -> list[tuple[dict, float]]:
	"""(bill, what it still counts for) oldest first, with money the company
	paid ahead (unapplied credit) netted off the oldest bills - so the
	buckets add up to the account balance."""
	credit = max(float(unapplied), 0.0)
	out = []
	for r in open_items:
		amt = float(r["outstanding"])
		if amt <= 0:
			continue
		if credit > 0:
			take = min(credit, amt)
			amt -= take
			credit -= take
		if amt <= 0.005:
			continue
		out.append((r, amt))
	return out


def days_overdue(item: dict, today=None) -> int:
	from frappe.utils import date_diff, getdate
	return date_diff(getdate(today or nowdate()), item["due_date"])


def _due_bucket(overdue: int) -> str:
	return ("not_due" if overdue <= 0 else "d1_30" if overdue <= 30 else
	        "d31_60" if overdue <= 60 else "d61_90" if overdue <= 90 else "d90p")


def _age_buckets(open_items: list[dict], unapplied: float) -> dict:
	from frappe.utils import date_diff, getdate
	buckets = dict.fromkeys(DUE_BUCKETS + INVOICE_AGE_BUCKETS, 0.0)
	today = getdate(nowdate())
	oldest_due = None
	for r, amt in _netted(open_items, unapplied):
		late = days_overdue(r, today)
		buckets[_due_bucket(late)] += amt
		if late > 0 and (oldest_due is None or r["due_date"] < oldest_due):
			oldest_due = r["due_date"]
		age = date_diff(today, r["invoice_date"])
		key = ("current" if age <= 30 else "b30" if age <= 60 else
		       "b60" if age <= 90 else "b90" if age <= 120 else "b90p")
		buckets[key] += amt
	out = {k: round(v, 2) for k, v in buckets.items()}
	out["overdue"] = round(sum(out[k] for k in DUE_BUCKETS[1:]), 2)
	out["oldest_overdue_due_date"] = oldest_due
	return out


def overdue_past_grace(open_items: list[dict], unapplied: float,
                       grace_days: int = 0) -> tuple[float, str | None]:
	"""What the company owes on bills more than `grace_days` past their due
	date, and the oldest such due date."""
	total, oldest = 0.0, None
	today = nowdate()
	for r, amt in _netted(open_items, unapplied):
		if days_overdue(r, today) > int(grace_days or 0):
			total += amt
			if oldest is None or r["due_date"] < oldest:
				oldest = r["due_date"]
	return round(total, 2), oldest


def _account_position(account: str) -> dict:
	open_items = city_ledger_open_folios(account)
	balance = float(frappe.db.sql(
		"""SELECT COALESCE(SUM(debit - credit), 0) FROM `tabCity Ledger Entry`
		   WHERE account = %s""", account)[0][0] or 0)
	outstanding = round(sum(max(r["outstanding"], 0) for r in open_items), 2)
	unapplied = round(max(outstanding - balance, 0.0), 2)
	return {
		"open_items": open_items,
		"open_balance": outstanding,
		"unapplied_credit": unapplied,
		"credit_days": effective_credit_days(account),
		**_age_buckets(open_items, unapplied),
	}


@frappe.whitelist()
@require_roles("Finance", "Hotel Admin", "Front Desk", "Night Auditor", "Kamra Agent")
def city_ledger_aging(property: str):
	"""Every company's AR at the property, aged by due date (not_due,
	d1_30, d31_60, d61_90, d90p and their sum `overdue`). The invoice-age
	keys (current, b30, b60, b90, b90p) are kept for older callers."""
	accounts = frappe.get_all(
		"City Ledger Account",
		filters={"property": property, "disabled": 0},
		fields=["name", "company", "account_number", "balance", "credit_limit"],
	)
	out = []
	for a in accounts:
		pos = _account_position(a.name)
		pos.pop("open_items")
		out.append({**a, **pos})
	totals = {k: round(sum(a[k] for a in out), 2)
	          for k in DUE_BUCKETS + ("overdue",)}
	return {"accounts": out, "totals": totals}


@frappe.whitelist()
@require_roles("Finance", "Hotel Admin", "Front Desk", "Kamra Agent")
def city_ledger_account(account: str):
	"""One company's city ledger: balance, aging, each open bill (oldest
	first) and recent payments - what the payment screen needs."""
	acc = frappe.get_doc("City Ledger Account", account)
	pos = _account_position(account)
	open_items = [r for r in pos.pop("open_items") if r["outstanding"] > 0.005]
	for r in open_items:
		f = frappe.db.get_value("Folio", r["folio"],
		                        ["guest_name", "reservation", "folio_type"],
		                        as_dict=True) or {}
		r.update({"guest_name": f.get("guest_name"),
		          "reservation": f.get("reservation"),
		          "folio_type": f.get("folio_type")})
	payments = frappe.get_all(
		"City Ledger Entry",
		filters={"account": account, "kind": "Payment"},
		fields=["name", "posting_date", "credit", "reference", "notes"],
		order_by="posting_date desc, creation desc",
		limit_page_length=10,
	)
	today = nowdate()
	for r in open_items:
		r["days_overdue"] = max(days_overdue(r, today), 0)
	# rolling credit: what is owed and what in-house stays will owe use the
	# limit up, payments free it again (kamra.credit counts the same way)
	from kamra.credit import in_house_exposure
	in_house = in_house_exposure(acc.company, acc.property)
	limit = float(acc.credit_limit or 0)
	return {
		"in_house": in_house,
		"available_credit": round(limit - float(acc.balance or 0) - in_house, 2)
		                    if limit > 0 else None,
		"account": acc.name,
		"company": acc.company,
		"account_number": acc.account_number,
		"credit_limit": acc.credit_limit,
		"account_credit_days": int(acc.get("credit_days") or 0),
		"use_default_credit_days": bool(acc.get("use_default_credit_days")),
		"billing_address": acc.get("billing_address"),
		"restricted": bool(acc.get("restricted")),
		"restricted_reason": acc.get("restricted_reason"),
		"balance": float(acc.balance or 0),
		**pos,
		"open_items": open_items,
		"payments": payments,
	}


# ── Advance / Force bill ─────────────────────────────────────────────────────

@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance", "Kamra Agent")
def force_advance_bill(reservation: str, nights: str = "entire",
                       pin: str | None = None):
	"""Post future room (+ meal) charges ahead of night audit.

	nights: 'tonight' | 'entire' | integer string of nights.
	"""
	from frappe.utils import add_days, date_diff, getdate

	from kamra.authz import require_cashier_pin
	from kamra.folio import _recalculate, open_folio, post_room_night

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
		# the allowance line carries the Guest-ledger credit itself
		save_folio(doc)
	else:
		# AR credit on the account the bill was last invoiced to (an Account
		# folio has no stay; a transferred bill lives on the new account),
		# else the stay's company
		account = frappe.db.get_value(
			"City Ledger Entry", {"folio": folio, "kind": "Invoice"}, "account",
			order_by="creation desc")
		if not account and doc.get("reservation"):
			company = frappe.db.get_value(
				"Reservation", doc.reservation, "company")
			account = _ar_account(doc.property, company) if company else None
		if account:
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
			ledger="AR",
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
@require_roles("Front Desk", "Finance", "Hotel Admin", "Night Auditor", "Kamra Agent")
def folio_history(property: str, query: str | None = None,
                  status: str | None = None, from_date: str | None = None,
                  to_date: str | None = None):
	# account invoices have no stay to show - they live on Receivables
	filters: list = [["property", "=", property],
	                 ["folio_type", "!=", "Account"]]
	if status:
		filters.append(["status", "=", status])
	if from_date:  # by the day the bill was closed
		from kamra.business_date import report_range_end

		to = report_range_end(from_date, to_date)
		filters.append(["closed_on", "between", [from_date, f"{to} 23:59:59"]])
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
	from kamra.api import _refuse_opening_balance
	_refuse_opening_balance(charge_type)
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
@require_roles("Front Desk", "Night Auditor", "Kamra Agent")
def quick_checkout(reservation: str, pin: str | None = None):
	"""Check out and close the guest folio in one step. check_out settles the
	stay the one way: the company's folio (Company, or the group master)
	moves to the city ledger when the company has credit, and the guest's
	own folio must already be paid - liquor and extras are never billed to
	the company."""
	from kamra.api import check_out, close_folio
	folio_name = frappe.db.get_value(
		"Folio", {"reservation": reservation, "folio_type": "Guest",
		          "status": "Open"}, "name")
	if not folio_name:
		frappe.throw("No open guest folio.")
	out = check_out(reservation)
	close_folio(folio_name, pin=pin)
	return out


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Kamra Agent")
def group_checkout(group: str, pin: str | None = None):
	"""Quick-checkout every Checked In reservation on a group."""
	res_names = frappe.get_all(
		"Reservation",
		filters={"group_booking": group, "status": "Checked In"},
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
	from kamra.cashier import record_cashier_txn, require_open_session
	require_cashier_pin(property, pin)
	calc = currency_calculator(property, currency, fx_amount, direction)
	if calc.get("max_exchange") and float(fx_amount) > float(calc["max_exchange"]):
		frappe.throw("Exceeds per-transaction FX limit.")
	sess = require_open_session(property, till_only=True)
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
		try:
			record_payment_ledger(fdoc, fdoc.payments[-1].as_dict(), session=sess)
		except Exception:
			frappe.log_error(title="ledger payment write failed")
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
			roles = set(frappe.get_roles())
			if not (roles & {"Hotel Admin", "Finance", "System Manager",
			                 "Administrator"}):
				frappe.throw("Supervisor role required for this reason.", frappe.PermissionError)
			pin_required = not property or bool(frappe.db.get_value(
				"Property", property, "require_cashier_pin"))
			if pin_required:
				if not supervisor_pin:
					frappe.throw("SUPERVISOR_PIN_REQUIRED: this reason needs approval.")
				from kamra.authz import require_cashier_pin
				if property:
					require_cashier_pin(property, supervisor_pin)
	return reason_code or free_text.strip()[:140]
