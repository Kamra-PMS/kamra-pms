"""Accounts receivable: set up a company's account, bill it directly, move
a bill between accounts.

The books underneath are the city ledger (kamra.ledger): a City Ledger
Account per company per property, a City Ledger Entry per bill, payment
and adjustment, and an AR leg in the Folio Ledger Entry for every bill.
Checkout fills it from stays; this module adds the three things a finance
team does by hand:

- `save_ar_account` opens or edits an account (number, terms, limit,
  billing address, restricted). Opening one puts the company on credit.
- `create_ar_invoice` bills the company for something that was not a stay
  (a meeting room, a contract fee). The lines go on an Account folio - a
  folio with no reservation - priced and taxed by the same rules as any
  folio charge, then billed to the account exactly the way checkout does
  (transfer_to_city_ledger, credit control included) and closed, which
  gives it its invoice number.
- `transfer_ar_invoice` moves what is still owed on one bill to another
  company's account (the parent company pays, the agency pays). AR as a
  whole doesn't change, so it is two City Ledger Entries and no ledger leg.
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import now_datetime

from kamra.authz import assert_property_access, require_roles
from kamra.business_date import get_business_date


def _account(account: str):
	acc = frappe.get_doc("City Ledger Account", account)
	assert_property_access(acc.property)
	return acc


def assert_billable(account: str) -> None:
	"""A restricted or disabled account takes no new bills - payments and
	statements still work, so the company can clear what it owes."""
	row = frappe.db.get_value(
		"City Ledger Account", account,
		["disabled", "restricted", "restricted_reason", "company"], as_dict=True)
	if not row:
		return
	if row.disabled:
		frappe.throw(_("The city ledger account of {0} is disabled.").format(
			row.company))
	if row.restricted:
		frappe.throw(_("The city ledger account of {0} is restricted{1}. "
		               "Lift the restriction to bill it.").format(
			row.company,
			f" ({row.restricted_reason})" if row.restricted_reason else ""))


@frappe.whitelist()
@require_roles("Finance", "Hotel Admin", "Front Desk", "Kamra Agent")
def ar_accounts(property: str):
	"""Every AR account at the property with its contact and position - the
	receivables list. Aging and balance come from city_ledger_aging so the
	two screens always agree."""
	assert_property_access(property)
	from kamra.ledger import city_ledger_aging
	rows = city_ledger_aging(property)["accounts"]
	extra = {r.name: r for r in frappe.get_all(
		"City Ledger Account", filters={"property": property, "disabled": 0},
		fields=["name", "restricted", "restricted_reason", "billing_address"])}
	contacts = {r.name: r for r in frappe.get_all(
		"Corporate Account",
		filters={"name": ("in", [r["company"] for r in rows] or [""])},
		fields=["name", "company_name", "contact_name", "contact_email",
		        "contact_phone", "gstin"])}
	for r in rows:
		e, c = extra.get(r["name"]) or {}, contacts.get(r["company"]) or {}
		r.update({
			"company_name": c.get("company_name") or r["company"],
			"contact_name": c.get("contact_name"),
			"contact_email": c.get("contact_email"),
			"contact_phone": c.get("contact_phone"),
			"tax_id": c.get("gstin"),
			"restricted": int(e.get("restricted") or 0),
			"restricted_reason": e.get("restricted_reason"),
			"billing_address": e.get("billing_address"),
		})
	rows.sort(key=lambda r: (-float(r.get("balance") or 0), r["company_name"]))
	return {"accounts": rows}


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Hotel Admin")
def save_ar_account(property: str, company: str, account_number: str | None = None,
                    credit_limit: float = 0, use_default_credit_days: int = 1,
                    credit_days: int = 0, billing_address: str | None = None,
                    restricted: int = 0, restricted_reason: str | None = None,
                    account: str | None = None):
	"""Open a company's AR account at a property, or edit it (`account`).
	One open account per company per property - checkout bills into it.
	The account number is the company's reference on statements and must
	be unique at the property. Opening an account puts the company on
	credit (Corporate Account.credit_allowed), since that is what it is for."""
	assert_property_access(property)
	if not frappe.db.exists("Corporate Account", company):
		frappe.throw(_("Company {0} not found.").format(company))
	number = (account_number or "").strip() or f"AR-{company[:20]}"
	if int(restricted or 0) and not (restricted_reason or "").strip():
		frappe.throw(_("Say why the account is restricted - it shows to "
		               "whoever tries to bill it."))
	if float(credit_limit or 0) < 0 or int(credit_days or 0) < 0:
		frappe.throw(_("Credit limit and credit days can't be negative."))
	clash = frappe.db.get_value(
		"City Ledger Account",
		{"property": property, "account_number": number,
		 "name": ("!=", account or "")}, "name")
	if clash:
		frappe.throw(_("Account number {0} is already used at this "
		               "property.").format(number))
	if account:
		doc = _account(account)
		if doc.property != property or doc.company != company:
			frappe.throw(_("An account's property and company can't change."))
	else:
		existing = frappe.db.get_value(
			"City Ledger Account",
			{"property": property, "company": company, "disabled": 0}, "name")
		if existing:
			frappe.throw(_("{0} already has an account here ({1}).").format(
				company, existing))
		doc = frappe.get_doc({"doctype": "City Ledger Account",
		                      "property": property, "company": company,
		                      "balance": 0})
	doc.update({
		"account_number": number,
		"credit_limit": float(credit_limit or 0),
		"use_default_credit_days": 1 if int(use_default_credit_days or 0) else 0,
		"credit_days": int(credit_days or 0),
		"billing_address": (billing_address or "").strip() or None,
		"restricted": 1 if int(restricted or 0) else 0,
		"restricted_reason": (restricted_reason or "").strip() or None,
	})
	doc.save(ignore_permissions=True)
	if not frappe.db.get_value("Corporate Account", company, "credit_allowed"):
		frappe.db.set_value("Corporate Account", company, "credit_allowed", 1)
	from kamra.savings import log_action
	log_action("save_ar_account", "City Ledger Account", doc.name, property,
	           rationale=f"{company} · {number} · limit {doc.credit_limit:,.2f}"
	                     + (f" · restricted: {doc.restricted_reason}"
	                        if doc.restricted else ""))
	return {"account": doc.name, "account_number": doc.account_number}


def _lines(lines) -> list[dict]:
	if isinstance(lines, str):
		lines = json.loads(lines or "[]")
	out = []
	for ln in lines or []:
		ln = ln or {}
		qty = float(ln.get("qty") or 1)
		if qty <= 0 or qty != int(qty):
			frappe.throw(_("Quantity must be a whole number above zero."))
		out.append({
			"charge_type": ln.get("charge_type") or "Misc",
			"description": (ln.get("description") or "").strip(),
			"rate": ln.get("amount"),
			"qty": int(qty),
			"gst_rate": float(ln.get("gst_rate") or 0),
		})
	if not out:
		frappe.throw(_("Add at least one line to the invoice."))
	return out


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Hotel Admin", "Kamra Agent")
def create_ar_invoice(account: str, lines, reference: str | None = None,
                      credit_override_reason: str | None = None):
	"""Bill a company directly, without a stay. `lines` is
	[{charge_type, description, amount, qty, gst_rate}]: amount is the unit
	price before tax, the tax rate must be one of the property's, and F&B or
	alcohol lines take the hotel's own rate whatever is sent. Credit control
	runs as at checkout. Returns the invoice number and the account's new
	balance."""
	from kamra.api import (_check_charge_amount_and_tax, _refuse_opening_balance,
	                       _resolve_charge_gst)
	from kamra.folio import _recalculate, close_folio
	from kamra.ledger import (CHARGE_TYPE_TO_CODE, code_for_charge_type,
	                          save_folio, transfer_to_city_ledger)

	acc = _account(account)
	assert_billable(account)
	rows = _lines(lines)
	bd = get_business_date(acc.property)
	company_name = frappe.db.get_value(
		"Corporate Account", acc.company, "company_name") or acc.company
	folio = frappe.get_doc({
		"doctype": "Folio",
		"property": acc.property,
		"guest_name": company_name,
		"folio_type": "Account",
		"status": "Open",
		"opened_on": now_datetime(),
	})
	for r in rows:
		if r["charge_type"] not in CHARGE_TYPE_TO_CODE \
				or r["charge_type"] in ("Discount", "Allowance"):
			frappe.throw(_("{0} can't be billed on an invoice.").format(
				r["charge_type"]))
		_refuse_opening_balance(r["charge_type"])
		if not r["description"]:
			frappe.throw(_("Every line needs a description."))
		_check_charge_amount_and_tax(acc.property, r["rate"], r["gst_rate"])
		rate = float(r["rate"])
		folio.append("charges", {
			"posting_date": bd,
			"charge_type": r["charge_type"],
			"transaction_code": code_for_charge_type(r["charge_type"]),
			"description": r["description"][:140],
			"qty": r["qty"],
			"rate": rate,
			"amount": round(rate * r["qty"], 2),
			"gst_rate": _resolve_charge_gst(acc.property, r["charge_type"],
			                                r["description"], 0, r["gst_rate"]),
		})
	_recalculate(folio)
	save_folio(folio)
	out = transfer_to_city_ledger(
		folio.name, acc.company, credit_override_reason=credit_override_reason,
		account=account)
	invoice = close_folio(folio.name)
	ref = (reference or "").strip()[:140] or None
	frappe.db.set_value(
		"City Ledger Entry", {"folio": folio.name, "kind": "Invoice"},
		"reference", ref or folio.name)
	from kamra.savings import log_action
	log_action("create_ar_invoice", "Folio", folio.name, acc.property,
	           rationale=f"{acc.company}: invoice {invoice} for "
	                     f"{folio.grand_total:,.2f}" + (f" · {ref}" if ref else ""))
	return {"account": account, "folio": folio.name, "invoice_number": invoice,
	        "total": folio.grand_total, "tax": folio.tax_total,
	        "balance": out["balance"], "credit": out.get("credit")}


@frappe.whitelist()
@require_roles("Finance", "Hotel Admin", "Front Desk", "Kamra Agent")
def ar_invoice(folio: str):
	"""One AR bill's lines and totals, whether it came from a stay or was
	raised on the account - what the invoice drawer shows and prints."""
	doc = frappe.get_doc("Folio", folio)
	assert_property_access(doc.property)
	return {
		"folio": doc.name,
		"folio_type": doc.folio_type,
		"reservation": doc.reservation,
		"guest_name": doc.guest_name,
		"invoice_number": doc.invoice_number,
		"status": doc.status,
		"closed_on": str(doc.closed_on or "") or None,
		"charges_total": doc.charges_total,
		"tax_total": doc.tax_total,
		"grand_total": doc.grand_total,
		"lines": [{"posting_date": str(c.posting_date), "charge_type": c.charge_type,
		           "transaction_code": c.transaction_code,
		           "description": c.description, "qty": c.qty, "rate": c.rate,
		           "amount": c.amount, "gst_rate": c.gst_rate,
		           "gst_amount": c.gst_amount, "total": c.total}
		          for c in doc.charges],
	}


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Hotel Admin")
def transfer_ar_invoice(account: str, folio: str, to_account: str,
                        reason: str | None = None):
	"""Move what is still owed on one bill to another company's account at
	the same property. What was already paid stays with the first account;
	the bill keeps its invoice number and invoice date, so it ages from when
	it was really raised. Credit control on the receiving company is not
	re-run - finance is choosing who pays."""
	from kamra.ledger import city_ledger_open_folios, due_date_for
	if account == to_account:
		frappe.throw(_("Pick a different account to transfer to."))
	# lock both accounts (fixed order) so two transfers of one bill can't
	# both read the same amount owed and move it twice
	for name in sorted((account, to_account)):
		frappe.db.get_value("City Ledger Account", name, "name", for_update=True)
	src, dst = _account(account), _account(to_account)
	if src.property != dst.property:
		frappe.throw(_("Both accounts must be at the same property."))
	assert_billable(to_account)
	item = next((r for r in city_ledger_open_folios(account)
	             if r["folio"] == folio), None)
	amount = round(float(item["outstanding"]) if item else 0, 2)
	if amount <= 0.005:
		frappe.throw(_("Nothing is owed on that bill on this account."))
	note = (reason or "").strip()[:140]
	bd = get_business_date(src.property)
	common = {"doctype": "City Ledger Entry", "property": src.property,
	          "folio": folio, "invoice_number": item["invoice_number"]}
	frappe.get_doc({**common, "account": account, "posting_date": bd,
	                "kind": "Adjustment", "debit": 0, "credit": amount,
	                "reference": f"Transferred to {dst.company}"[:140],
	                "notes": note or None}).insert(ignore_permissions=True)
	# both legs post today (the books see the move when it happened); the
	# bill ages from its original date, kept in invoice_date
	frappe.get_doc({**common, "account": to_account,
	                "posting_date": bd, "invoice_date": item["invoice_date"],
	                "kind": "Invoice",
	                "due_date": due_date_for(to_account, item["invoice_date"]),
	                "debit": amount, "credit": 0,
	                "reference": f"Transferred from {src.company}"[:140],
	                "notes": note or None}).insert(ignore_permissions=True)
	src.balance = float(src.balance or 0) - amount
	src.save(ignore_permissions=True)
	dst.balance = float(dst.balance or 0) + amount
	dst.save(ignore_permissions=True)
	from kamra.ledger import apply_unapplied_credit
	apply_unapplied_credit(to_account, only_folio=folio)
	from kamra.savings import log_action
	log_action("transfer_ar_invoice", "Folio", folio, src.property,
	           rationale=f"{amount:,.2f} of {item['invoice_number'] or folio} "
	                     f"from {src.company} to {dst.company}"
	                     + (f" · {note}" if note else ""))
	return {"folio": folio, "amount": amount,
	        "from_balance": src.balance, "to_balance": dst.balance}
