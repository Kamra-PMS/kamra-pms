"""Accounts payable: the hotel's suppliers and the bills it owes them.

A Vendor belongs to one property (the grocer, the linen contractor, the
power company). A Vendor Bill is one supplier invoice: amount before tax,
a tax rate, the due date (bill date + the vendor's terms unless the paper
says otherwise) and the payments made against it. The bill works out its
own tax, total, paid and still-owed figures (VendorBill.validate).

Who does what:
- Finance and Hotel Admin enter vendors and bills (an agent may enter a
  bill too, from a photo or an email). A new bill waits for approval.
- Hotel Admin approves a bill. Once approved, Finance or Hotel Admin
  records payments against it. Nothing is paid before it is approved.
  Payments stay here in accounts payable; nothing is posted to a general
  ledger.

Petty cash stays what it is: cash paid out of the till on the day, with a
voucher (kamra.cashier.post_petty_cash). A bill here is supplier credit,
paid later, usually from the bank. Paying a supplier from the drawer is a
petty cash voucher, not a bill, so the expense is never counted twice.

Aging is by due date, in the same buckets as the city ledger
(kamra.ledger.DUE_BUCKETS): not due, 1-30, 31-60, 61-90 and 90+ overdue.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, now_datetime, nowdate

from kamra.authz import require_perm
from kamra.ledger import DUE_BUCKETS, _due_bucket

EXPENSE_CATEGORIES = (
	"Food & Beverage Supplies", "Linen & Laundry", "Housekeeping Supplies",
	"Utilities", "Repairs & Maintenance", "Staff Costs", "Rent & Leases",
	"Commissions & Marketing", "Professional Fees", "Other",
)
OPEN = ("Awaiting Approval", "Approved", "Part Paid")
BILL = {"bill": "Vendor Bill"}


def _vendor(property: str, vendor: str) -> dict:
	"""A vendor at this property, by id or exact name."""
	row = frappe.db.get_value(
		"Vendor", {"name": vendor, "property": property},
		["name", "vendor_name", "payment_terms_days", "expense_category", "disabled"],
		as_dict=True) or frappe.db.get_value(
		"Vendor", {"vendor_name": vendor, "property": property},
		["name", "vendor_name", "payment_terms_days", "expense_category", "disabled"],
		as_dict=True)
	if not row:
		frappe.throw(_("Vendor {0} not found at this property.").format(vendor))
	return row


def _category(value: str | None, fallback: str = "Other") -> str:
	value = value or fallback
	if value not in EXPENSE_CATEGORIES:
		frappe.throw(_("Pick an expense category: {0}.").format(
			", ".join(EXPENSE_CATEGORIES)))
	return value


def _bill_row(b) -> dict:
	today = getdate(nowdate())
	late = (today - getdate(b.due_date)).days
	return {
		"name": b.name, "vendor": b.vendor, "vendor_name": b.vendor_name,
		"bill_number": b.bill_number, "bill_date": str(b.bill_date),
		"due_date": str(b.due_date), "expense_category": b.expense_category,
		"description": b.description, "amount": flt(b.amount),
		"tax_rate": flt(b.tax_rate), "tax_amount": flt(b.tax_amount),
		"total": flt(b.total), "paid": flt(b.paid),
		"outstanding": flt(b.outstanding), "status": b.status,
		"days_overdue": max(late, 0) if b.status in OPEN else 0,
		"entered_by": b.entered_by, "approved_by": b.approved_by,
	}


# ── vendors ─────────────────────────────────────────────────────────────────

@frappe.whitelist()
@require_perm("Vendor Bill", "view_payables")
def vendors(property: str, include_disabled: int = 0):
	"""Every vendor at the property with what the hotel still owes them,
	aged by due date - the payables list."""
	filters = {"property": property}
	if not int(include_disabled or 0):
		filters["disabled"] = 0
	rows = frappe.get_all(
		"Vendor", filters=filters,
		fields=["name", "vendor_name", "expense_category", "payment_terms_days",
		        "tax_id", "contact_name", "phone", "email", "notes", "disabled"],
		order_by="vendor_name asc", limit_page_length=0)
	aging = {a["vendor"]: a for a in payables_aging(property)["vendors"]}
	empty = dict.fromkeys(DUE_BUCKETS + ("overdue", "balance"), 0.0)
	for r in rows:
		a = aging.get(r.name) or {}
		r.update({k: a.get(k, v) for k, v in empty.items()})
		r["open_bills"] = a.get("open_bills", 0)
	return {"vendors": rows, "categories": EXPENSE_CATEGORIES}


@frappe.whitelist(methods=["POST"])
@require_perm("Vendor", "manage_vendors", scope={"vendor": "Vendor"})
def save_vendor(property: str, vendor_name: str, expense_category: str | None = None,
                payment_terms_days: int = 30, tax_id: str | None = None,
                contact_name: str | None = None, phone: str | None = None,
                email: str | None = None, notes: str | None = None,
                disabled: int = 0, vendor: str | None = None):
	"""Add a supplier at the property, or edit one (`vendor`). Names are
	unique per property, so a bill can name its vendor by name."""
	name = (vendor_name or "").strip()
	if not name:
		frappe.throw(_("Give the vendor a name."))
	if int(payment_terms_days or 0) < 0:
		frappe.throw(_("Payment terms can't be negative."))
	clash = frappe.db.get_value(
		"Vendor", {"property": property, "vendor_name": name,
		           "name": ("!=", vendor or "")}, "name")
	if clash:
		frappe.throw(_("There is already a vendor called {0} here.").format(name))
	values = {
		"vendor_name": name[:140],
		"expense_category": _category(expense_category),
		"payment_terms_days": int(payment_terms_days or 0),
		"tax_id": (tax_id or "").strip()[:40] or None,
		"contact_name": (contact_name or "").strip()[:140] or None,
		"phone": (phone or "").strip()[:40] or None,
		"email": (email or "").strip()[:140] or None,
		"notes": (notes or "").strip()[:1000] or None,
		"disabled": 1 if int(disabled or 0) else 0,
	}
	if vendor:
		doc = frappe.get_doc("Vendor", vendor)
		if doc.property != property:
			frappe.throw(_("That vendor belongs to another property."))
		doc.update(values)
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc({"doctype": "Vendor", "property": property, **values})
		doc.insert(ignore_permissions=True)
	return {"vendor": doc.name}


# ── bills ───────────────────────────────────────────────────────────────────

@frappe.whitelist(methods=["POST"])
@require_perm("Vendor Bill", "enter_bills")
def create_vendor_bill(property: str, vendor: str, bill_date: str, amount: float,
                       tax_rate: float = 0, expense_category: str | None = None,
                       bill_number: str | None = None, due_date: str | None = None,
                       description: str | None = None):
	"""Enter a supplier's bill. `amount` is before tax; the tax is
	amount x `tax_rate` %. The due date is the bill date plus the vendor's
	payment terms unless `due_date` is given. The bill then waits for a
	Hotel Admin to approve it."""
	v = _vendor(property, vendor)
	if v.disabled:
		frappe.throw(_("{0} is disabled. Turn it back on to enter a bill.").format(
			v.vendor_name))
	amount, rate = flt(amount, 2), flt(tax_rate)
	if amount <= 0:
		frappe.throw(_("The amount must be more than zero."))
	if not 0 <= rate <= 100:
		frappe.throw(_("The tax rate must be between 0 and 100."))
	bd = getdate(bill_date)
	if bd > getdate(nowdate()):
		frappe.throw(_("The bill date can't be in the future."))
	due = getdate(due_date) if due_date else getdate(
		add_days(bd, int(v.payment_terms_days or 0)))
	if due < bd:
		frappe.throw(_("The due date can't be before the bill date."))
	number = (bill_number or "").strip()[:80] or None
	if number and frappe.db.exists("Vendor Bill", {
			"vendor": v.name, "bill_number": number, "status": ("!=", "Cancelled")}):
		frappe.throw(_("Bill {0} from {1} is already entered.").format(
			number, v.vendor_name))
	doc = frappe.get_doc({
		"doctype": "Vendor Bill", "property": property, "vendor": v.name,
		"vendor_name": v.vendor_name, "bill_number": number,
		"bill_date": bd, "due_date": due,
		"expense_category": _category(expense_category, v.expense_category or "Other"),
		"description": (description or "").strip()[:1000] or None,
		"amount": amount, "tax_rate": rate,
		"status": "Awaiting Approval", "entered_by": frappe.session.user,
	}).insert(ignore_permissions=True)
	from kamra.savings import log_action
	log_action("vendor_bill_entered", "Vendor Bill", doc.name, property,
	           rationale=f"{v.vendor_name} {number or ''} {doc.total:,.2f} due {due}")
	return _bill_row(doc)


def _open_bill(bill: str):
	doc = frappe.get_doc("Vendor Bill", bill)
	if doc.status not in OPEN:
		frappe.throw(_("Bill {0} is {1}.").format(doc.name, _(doc.status).lower()))
	return doc


@frappe.whitelist(methods=["POST"])
@require_perm("Vendor Bill", "approve_bills", scope=BILL)
def approve_vendor_bill(bill: str):
	"""Approve a bill so it can be paid."""
	doc = _open_bill(bill)
	if doc.status != "Awaiting Approval":
		frappe.throw(_("Bill {0} is already approved.").format(doc.name))
	doc.status = "Approved"
	doc.approved_by = frappe.session.user
	doc.approved_on = now_datetime()
	doc.save(ignore_permissions=True)
	from kamra.savings import log_action
	log_action("vendor_bill_approved", "Vendor Bill", doc.name, doc.property,
	           rationale=f"{doc.vendor_name} {doc.total:,.2f}")
	return _bill_row(doc)


@frappe.whitelist(methods=["POST"])
@require_perm("Vendor Bill", "pay_bills", scope=BILL)
def pay_vendor_bill(bill: str, amount: float, mode: str = "Bank Transfer",
                    reference: str | None = None, payment_date: str | None = None):
	"""Record a payment against an approved bill: all of it or part. It
	can't be more than the bill still owes. This records the payment; it
	does not move money in a till (cash from the till is petty cash)."""
	doc = _open_bill(bill)
	if doc.status == "Awaiting Approval":
		frappe.throw(_("Approve bill {0} before paying it.").format(doc.name))
	amount = flt(amount, 2)
	if amount <= 0:
		frappe.throw(_("The amount must be more than zero."))
	if amount > flt(doc.outstanding) + 0.005:
		frappe.throw(_("Bill {0} only has {1} left to pay.").format(
			doc.name, f"{flt(doc.outstanding):,.2f}"))
	paid_on = getdate(payment_date or nowdate())
	if paid_on > getdate(nowdate()) or paid_on < getdate(doc.bill_date):
		frappe.throw(_("The payment date must be between the bill date and today."))
	mode = (mode or "").strip()[:40]
	if not mode:
		frappe.throw(_("Say how it was paid."))
	doc.append("payments", {
		"payment_date": paid_on, "amount": amount, "mode": mode,
		"reference": (reference or "").strip()[:140] or None,
		"paid_by": frappe.session.user,
	})
	doc.save(ignore_permissions=True)
	from kamra.savings import log_action
	log_action("vendor_bill_paid", "Vendor Bill", doc.name, doc.property,
	           rationale=f"{doc.vendor_name} paid {amount:,.2f} by {mode}")
	return _bill_row(doc)


@frappe.whitelist(methods=["POST"])
@require_perm("Vendor Bill", "pay_bills", scope=BILL)
def cancel_vendor_bill(bill: str, reason: str):
	"""Cancel a bill entered by mistake. A bill with payments on it can't
	be cancelled."""
	doc = _open_bill(bill)
	if not (reason or "").strip():
		frappe.throw(_("Say why the bill is cancelled."))
	if doc.payments:
		frappe.throw(_("Bill {0} has payments on it and can't be cancelled.").format(
			doc.name))
	doc.status = "Cancelled"
	doc.cancel_reason = reason.strip()[:500]
	doc.save(ignore_permissions=True)
	from kamra.savings import log_action
	log_action("vendor_bill_cancelled", "Vendor Bill", doc.name, doc.property,
	           rationale=doc.cancel_reason)
	return _bill_row(doc)


@frappe.whitelist()
@require_perm("Vendor Bill", "view_payables", scope=BILL)
def vendor_bill(bill: str):
	"""One bill with its payments."""
	doc = frappe.get_doc("Vendor Bill", bill)
	out = _bill_row(doc)
	out["cancel_reason"] = doc.cancel_reason
	out["approved_on"] = str(doc.approved_on) if doc.approved_on else None
	out["payments"] = [{"payment_date": str(p.payment_date), "amount": flt(p.amount),
	                    "mode": p.mode, "reference": p.reference, "paid_by": p.paid_by}
	                   for p in doc.payments]
	return out


@frappe.whitelist()
@require_perm("Vendor Bill", "view_payables", scope={"vendor": "Vendor"})
def vendor_bills(property: str, status: str = "open", vendor: str | None = None,
                 limit: int = 500):
	"""Bills at the property, most urgent first. `status` is "open"
	(not paid or cancelled, the default), "all", or one status."""
	filters = {"property": property}
	if status == "open":
		filters["status"] = ("in", OPEN)
	elif status and status != "all":
		filters["status"] = status
	if vendor:
		filters["vendor"] = vendor
	rows = frappe.get_all(
		"Vendor Bill", filters=filters,
		fields=["name", "vendor", "vendor_name", "bill_number", "bill_date",
		        "due_date", "expense_category", "description", "amount", "tax_rate",
		        "tax_amount", "total", "paid", "outstanding", "status",
		        "entered_by", "approved_by"],
		order_by="due_date asc, bill_date asc",
		limit_page_length=max(1, min(int(limit or 500), 2000)))
	return {"bills": [_bill_row(r) for r in rows]}


@frappe.whitelist()
@require_perm("Vendor Bill", "view_payables")
def payables_aging(property: str):
	"""What the hotel owes each vendor, aged by due date: not_due, d1_30,
	d31_60, d61_90, d90p and their sum `overdue`, plus totals."""
	rows = frappe.get_all(
		"Vendor Bill",
		filters={"property": property, "status": ("in", OPEN), "outstanding": (">", 0)},
		fields=["vendor", "vendor_name", "due_date", "outstanding"],
		limit_page_length=0)
	today = getdate(nowdate())
	by_vendor: dict[str, dict] = {}
	for r in rows:
		v = by_vendor.setdefault(r.vendor, {
			"vendor": r.vendor, "vendor_name": r.vendor_name, "open_bills": 0,
			**dict.fromkeys(DUE_BUCKETS, 0.0)})
		v["open_bills"] += 1
		v[_due_bucket((today - getdate(r.due_date)).days)] += flt(r.outstanding)
	out = []
	for v in by_vendor.values():
		for k in DUE_BUCKETS:
			v[k] = round(v[k], 2)
		v["overdue"] = round(sum(v[k] for k in DUE_BUCKETS[1:]), 2)
		v["balance"] = round(v["overdue"] + v["not_due"], 2)
		out.append(v)
	out.sort(key=lambda v: (-v["overdue"], -v["balance"], v["vendor_name"] or ""))
	totals = {k: round(sum(v[k] for v in out), 2)
	          for k in DUE_BUCKETS + ("overdue", "balance")}
	return {"vendors": out, "totals": totals}
