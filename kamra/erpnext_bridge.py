"""ERPNext bridge (#228, P3): opt-in, and only when ERPNext is on the site.

- Night audit posts one submitted Journal Entry per business date to the
  ERPNext ledger. Every Folio Ledger Entry is one leg (its ledger: Guest,
  Deposit, AR, Package); the other leg is its transaction code's account
  (the GL code the line was posted with), with a charge's tax split out to
  the Tax account. So the entry balances by construction and the day's
  revenue ties to the GL with no manual export.
- An approved supplier bill posts to the ERPNext supplier's account
  (Dr expense and purchase tax, Cr Creditors) and each payment clears it.
- Frappe HR: a Kamra staff login is linked to its Employee record through
  the Employee's own user_id.

Accounts come from the property's account map (Settings -> Finance ->
ERPNext books). An ERPNext Sync Log row per business date, bill or
payment keeps every post to once; a reversal cancels the entry (ERPNext
writes the reversing GL) and lets the date post again.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate

from kamra.authz import assert_property_access, require_roles

LEDGERS = ("Guest", "Deposit", "AR", "Package")


def erpnext_installed() -> bool:
	return "erpnext" in frappe.get_installed_apps()


def hrms_installed() -> bool:
	return "hrms" in frappe.get_installed_apps()


def _setting(prop: str, key: str):
	from kamra.settings import get_setting
	return get_setting(prop, key)


def account_map(prop: str) -> dict[str, str]:
	"""The Settings text, one `key = account` per line (`:` works too)."""
	out = {}
	for line in (_setting(prop, "erpnext_account_map") or "").splitlines():
		sep = "=" if "=" in line else ":" if ":" in line else None
		if not sep or line.lstrip().startswith("#"):
			continue
		key, account = (p.strip() for p in line.split(sep, 1))
		if key and account:
			out[key] = account
	return out


# ── the day's journal ────────────────────────────────────────────────────────

def _day_rows(prop: str, date: str) -> list[dict]:
	return frappe.db.sql(
		"""
		SELECT e.ledger, e.transaction_code, e.debit, e.credit,
		       COALESCE(NULLIF(fc.gl_code, ''), NULLIF(fp.gl_code, ''),
		                NULLIF(tc.gl_code, '')) AS gl_code,
		       fc.total AS charge_total, fc.gst_amount AS charge_tax
		FROM `tabFolio Ledger Entry` e
		LEFT JOIN `tabFolio Charge` fc
		       ON e.source_doctype = 'Folio Charge' AND fc.name = e.source_name
		LEFT JOIN `tabFolio Payment` fp
		       ON e.source_doctype = 'Folio Payment' AND fp.name = e.source_name
		LEFT JOIN `tabTransaction Code` tc ON tc.name = e.transaction_code
		WHERE e.property = %s AND e.business_date = %s
		""", (prop, date), as_dict=True)


def journal_lines(rows: list[dict], accounts: dict[str, str]) -> tuple[list[dict], list[str]]:
	"""Net debit (+) / credit (-) per ERPNext account for the day's ledger
	rows, and the keys the account map is missing."""
	net: dict[str, float] = {}
	missing: set[str] = set()

	def book(key: str | None, amount: float):
		account = accounts.get(key or "")
		if not account:
			missing.add(key or "(no transaction code)")
			return
		net[account] = net.get(account, 0.0) + amount

	for r in rows:
		amount = flt(r["debit"]) - flt(r["credit"])
		if abs(amount) < 0.005:
			continue
		book(r["ledger"], amount)
		tax = 0.0
		if flt(r.get("charge_total")) and flt(r.get("charge_tax")):
			tax = flt(amount * flt(r["charge_tax"]) / flt(r["charge_total"]), 2)
		gl, code = r.get("gl_code"), r.get("transaction_code")
		# the GL code the line was posted with, else its transaction code
		key = gl if (gl in accounts or (gl and code not in accounts)) else code
		book(key, -(amount - tax))
		if tax:
			book("Tax", -tax)
	lines = [{"account": a, "debit": flt(v, 2) if v > 0 else 0, "credit": flt(-v, 2) if v < 0 else 0}
	         for a, v in sorted(net.items()) if abs(v) >= 0.005]
	return lines, sorted(missing)


def _log_name(kind: str, ref: str) -> str:
	return f"{kind}:{ref}"[:140]


def _post_journal(prop: str, kind: str, ref: str, posting_date, lines: list[dict],
                  remark: str, party: tuple | None = None) -> dict:
	"""Insert and submit one Journal Entry, once per (kind, ref)."""
	name = _log_name(kind, ref)
	log = frappe.db.get_value("ERPNext Sync Log", name, ["status", "journal_entry"],
	                          as_dict=True, for_update=True)
	if log and log.status == "Posted":
		return {"status": "already_posted", "journal_entry": log.journal_entry}
	company = (_setting(prop, "erpnext_company") or "").strip()
	if not company:
		frappe.throw(_("Set the ERPNext company in Settings, Finance, ERPNext books."))
	cost_center = (_setting(prop, "erpnext_cost_center") or "").strip() or None
	rows = []
	for ln in lines:
		row = {"account": ln["account"], "cost_center": cost_center,
		       "debit_in_account_currency": ln["debit"],
		       "credit_in_account_currency": ln["credit"]}
		if party and ln["account"] == party[2]:
			row.update(party_type=party[0], party=party[1])
		rows.append(row)
	je = _submit_journal({"doctype": "Journal Entry", "voucher_type": "Journal Entry",
	                      "company": company, "posting_date": str(posting_date),
	                      "user_remark": remark[:500], "accounts": rows})
	total = flt(sum(ln["debit"] for ln in lines), 2)
	if log:
		frappe.db.set_value("ERPNext Sync Log", name, {
			"status": "Posted", "journal_entry": je, "total": total})
	else:
		frappe.get_doc({"doctype": "ERPNext Sync Log", "name": name, "property": prop,
		                "kind": kind, "reference": ref, "journal_entry": je,
		                "status": "Posted", "total": total}).insert(ignore_permissions=True)
	return {"status": "posted", "journal_entry": je, "total": total}


def _submit_journal(doc: dict) -> str:
	je = frappe.get_doc(doc)
	je.insert(ignore_permissions=True)
	je.submit()
	return je.name


def _cancel_journal(name: str) -> None:
	je = frappe.get_doc("Journal Entry", name)
	je.flags.ignore_permissions = True
	je.cancel()


def _closed_date(prop: str, business_date: str) -> str:
	from kamra.business_date import get_business_date
	date = str(getdate(business_date))
	if getdate(date) >= getdate(get_business_date(prop)):
		frappe.throw(_("{0} is not closed yet. It posts after its night audit.").format(date))
	return date


@frappe.whitelist()
@require_roles("Finance", "Hotel Admin")
def preview_daily_journal(property: str, business_date: str):
	"""The journal entry a closed business date would post, and the account
	map keys it still needs. Works without ERPNext."""
	assert_property_access(property)
	lines, missing = journal_lines(_day_rows(property, str(getdate(business_date))),
	                               account_map(property))
	return {"business_date": str(getdate(business_date)), "lines": lines, "missing": missing,
	        "debit": flt(sum(ln["debit"] for ln in lines), 2),
	        "credit": flt(sum(ln["credit"] for ln in lines), 2)}


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Hotel Admin")
def post_daily_journal(property: str, business_date: str):
	"""Post a closed business date to ERPNext (night audit does it on its
	own when the setting is on). Refuses while any key is unmapped, so a
	day never posts in part."""
	assert_property_access(property)
	return _post_day(property, business_date)


def _post_day(property: str, business_date: str) -> dict:
	if not erpnext_installed():
		frappe.throw(_("ERPNext is not installed on this site."))
	date = _closed_date(property, business_date)
	lines, missing = journal_lines(_day_rows(property, date), account_map(property))
	if missing:
		frappe.throw(_("Map these in Settings, Finance, ERPNext books first: {0}").format(
			", ".join(missing)))
	if not lines:
		return {"status": "nothing_to_post", "business_date": date}
	out = _post_journal(property, "Business Date", f"{property} {date}", date, lines,
	                    f"Kamra night audit {property} {date}")
	if out["status"] == "posted":
		from kamra.savings import log_action
		log_action("erpnext_gl_posted", "Property", property, property,
		           rationale=f"{date} → ERPNext {out['journal_entry']} ({out['total']:,.2f})")
	return {**out, "business_date": date}


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Hotel Admin")
def reverse_daily_journal(property: str, business_date: str, reason: str):
	"""Cancel a business date's journal entry in ERPNext (it writes the
	reversing GL), so the date can post again after a correction."""
	assert_property_access(property)
	if not (reason or "").strip():
		frappe.throw(_("Say why the posting is reversed."))
	date = str(getdate(business_date))
	name = _log_name("Business Date", f"{property} {date}")
	log = frappe.db.get_value("ERPNext Sync Log", name, ["status", "journal_entry"],
	                          as_dict=True, for_update=True)
	if not log or log.status != "Posted":
		frappe.throw(_("{0} is not posted to ERPNext.").format(date))
	_cancel_journal(log.journal_entry)
	frappe.db.set_value("ERPNext Sync Log", name, {"status": "Reversed",
	                                                "note": reason.strip()[:500]})
	from kamra.savings import log_action
	log_action("erpnext_gl_reversed", "Property", property, property,
	           rationale=f"{date}: {log.journal_entry} cancelled - {reason.strip()}")
	return {"status": "reversed", "journal_entry": log.journal_entry}


def after_night_audit(property: str, business_date: str) -> None:
	"""Background job enqueued by night audit. Never raises: a failure is
	logged and the date can be posted from Settings later."""
	try:
		_post_day(property, business_date)
	except Exception:
		frappe.log_error(title=f"ERPNext posting failed for {property} {business_date}")


def gl_posting_on(prop: str) -> bool:
	return bool(int(_setting(prop, "erpnext_gl_posting") or 0)) and erpnext_installed()


# ── supplier bills ───────────────────────────────────────────────────────────

def _supplier(prop: str, name: str) -> str:
	if frappe.db.exists("Supplier", name):
		return name
	return frappe.get_doc({
		"doctype": "Supplier", "supplier_name": name,
		"supplier_group": _setting(prop, "erpnext_supplier_group") or "All Supplier Groups",
	}).insert(ignore_permissions=True).name


def _need(accounts: dict, *keys: str) -> list[str]:
	return [k for k in keys if k not in accounts]


def sync_vendor_bill(bill: str) -> list[dict]:
	"""Post an approved supplier bill and its payments that are not in
	ERPNext yet. Safe to call again: each posts once."""
	doc = frappe.get_doc("Vendor Bill", bill)
	prop = doc.property
	if not (int(_setting(prop, "erpnext_purchase_sync") or 0) and erpnext_installed()):
		return []
	if doc.status in ("Awaiting Approval", "Cancelled"):
		return []
	accounts = account_map(prop)
	expense = doc.expense_category if doc.expense_category in accounts else "Expense"
	missing = _need(accounts, expense, "Creditors",
	                *(["Purchase Tax"] if flt(doc.tax_amount) else []))
	if missing:
		frappe.throw(_("Map these in Settings, Finance, ERPNext books first: {0}").format(
			", ".join(missing)))
	supplier = _supplier(prop, doc.vendor_name)
	creditors = accounts["Creditors"]
	party = ("Supplier", supplier, creditors)
	out = []
	lines = [{"account": accounts[expense], "debit": flt(doc.amount, 2), "credit": 0},
	         {"account": creditors, "debit": 0, "credit": flt(doc.total, 2)}]
	if flt(doc.tax_amount):
		lines.insert(1, {"account": accounts["Purchase Tax"],
		                 "debit": flt(doc.tax_amount, 2), "credit": 0})
	out.append(_post_journal(prop, "Supplier Bill", doc.name, doc.bill_date, lines,
	                         f"Kamra supplier bill {doc.name} {doc.bill_number or ''}".strip(),
	                         party))
	for p in doc.payments:
		bank_key = f"Pay:{p.mode}" if f"Pay:{p.mode}" in accounts else "Bank"
		if bank_key not in accounts:
			frappe.throw(_("Map these in Settings, Finance, ERPNext books first: {0}").format(
				f"Pay:{p.mode} or Bank"))
		out.append(_post_journal(
			prop, "Supplier Payment", p.name, p.payment_date,
			[{"account": creditors, "debit": flt(p.amount, 2), "credit": 0},
			 {"account": accounts[bank_key], "debit": 0, "credit": flt(p.amount, 2)}],
			f"Kamra payment on {doc.name} by {p.mode} {p.reference or ''}".strip(), party))
	return out


def after_vendor_bill_change(bill: str) -> None:
	"""Called by kamra.payables after an approval or a payment. A failure
	never blocks the bill; Sync supplier bills posts it later."""
	try:
		sync_vendor_bill(bill)
	except Exception:
		frappe.log_error(title=f"ERPNext supplier bill sync failed for {bill}")


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Hotel Admin")
def sync_vendor_bills(property: str):
	"""Post every approved supplier bill and payment not in ERPNext yet."""
	assert_property_access(property)
	if not erpnext_installed():
		frappe.throw(_("ERPNext is not installed on this site."))
	posted = 0
	for name in frappe.get_all("Vendor Bill", pluck="name", filters={
			"property": property, "status": ("not in", ("Awaiting Approval", "Cancelled"))}):
		posted += sum(1 for r in sync_vendor_bill(name) if r["status"] == "posted")
	return {"posted": posted}


# ── Frappe HR ────────────────────────────────────────────────────────────────

@frappe.whitelist()
@require_roles("Hotel Admin")
def staff_employees(property: str):
	"""Kamra staff at this property with the HR Employee each is linked to
	(Employee.user_id), and the Employees not linked to anyone yet."""
	assert_property_access(property)
	if not hrms_installed():
		frappe.throw(_("Frappe HR is not installed on this site."))
	from kamra.staff import list_staff
	staff = list_staff(property)
	emp = {e.user_id: e for e in frappe.get_all(
		"Employee", filters={"user_id": ("in", [s["user"] for s in staff] or [""])},
		fields=["name", "employee_name", "user_id"])}
	unlinked = frappe.get_all("Employee", filters={"user_id": ("is", "not set"),
	                                               "status": "Active"},
	                          fields=["name", "employee_name"], order_by="employee_name",
	                          limit_page_length=500)
	return {"staff": [{"user": s["user"], "full_name": s["full_name"],
	                   "employee": (emp.get(s["user"]) or {}).get("name"),
	                   "employee_name": (emp.get(s["user"]) or {}).get("employee_name")}
	                  for s in staff],
	        "unlinked_employees": unlinked}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin")
def link_employee(user: str, employee: str | None = None):
	"""Link a staff login to its HR Employee (or unlink with no employee).
	The link is the Employee's own user_id, so HR and Kamra agree."""
	if not hrms_installed():
		frappe.throw(_("Frappe HR is not installed on this site."))
	for name in frappe.get_all("Employee", filters={"user_id": user}, pluck="name"):
		if name != employee:
			frappe.db.set_value("Employee", name, "user_id", None)
	if employee:
		doc = frappe.get_doc("Employee", employee)
		doc.user_id = user
		doc.save(ignore_permissions=True)
	return {"user": user, "employee": employee}
