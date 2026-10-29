"""Management books: the next few days of cash, a management P&L and a
balance sheet of what Kamra can see.

None of this is statutory accounts. Kamra is the front office, not a
general ledger: it knows guest bills, company (city ledger) bills, advance
deposits, supplier bills (kamra.payables) and petty cash. It does not know
the bank balance, payroll run outside Kamra, fixed assets, loans or equity.
The accounting export (kamra.accounting) hands the invoices to the real
books.

Revenue is counted once, the way the night audit report does it:
- folio charges by department (kamra.ledger.CHARGE_TYPE_TO_CODE groups),
  leaving out restaurant bills charged to a room (their line ends
  "(ORD-...)") and banquet lines (they start "EVT-"), plus the room levy
  and go-live opening balances, which are not revenue
- restaurant bills (POS Order) from the bill itself, paid at the outlet
  or charged to a room
- banquets from the function (Venue Booking) on its event date
All figures are before tax.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, date_diff, flt, get_first_day, getdate, nowdate

from kamra.authz import require_roles

FOLIO_SKIP = ("Opening Balance", "Room Levy")
NOT_FOLIO = """IFNULL(fc.description, '') NOT LIKE '%%(ORD-%%'
	  AND IFNULL(fc.description, '') NOT LIKE 'EVT-%%'"""


def _r(x) -> float:
	return round(flt(x), 2)


def till_cash(property: str) -> float:
	"""Cash in the property's open tills right now (opening float + cash
	taken - paid outs, drops and petty cash)."""
	from kamra.cashier import _recompute_session_totals
	names = frappe.get_all("Cashier Session",
	                       filters={"property": property, "status": "Open"}, pluck="name")
	return _r(sum(_recompute_session_totals(n, persist=False)["expected_cash"]
	              for n in names))


# ── next days of cash ───────────────────────────────────────────────────────

def _company_credit(company: str | None) -> bool:
	return bool(company and frappe.db.get_value(
		"Corporate Account", company, "credit_allowed"))


@frappe.whitelist()
@require_roles("Finance", "Hotel Admin", "Kamra Agent")
def cash_forecast(property: str, days: int = 5, opening: float | None = None):
	"""Money expected in and out over the next `days` days (5, 15 or 30;
	default 5), day by day from today, with a running position and
	subtotals by week.

	In: company (city ledger) bills falling due, what departing guests
	still owe, advance deposits due from arrivals. Out: supplier bills
	falling due, drafts awaiting approval included and flagged `draft`.
	Anything already overdue is counted today. `opening` is
	the cash and bank to start from; without it, the cash in open tills.
	Read-only."""
	from kamra.api import _DEPOSIT_STATUSES, _deposit_state, _stay_balances
	from kamra.ledger import _account_position, _netted

	days = int(days or 5)
	if days not in (5, 15, 30):
		frappe.throw(_("Choose 5, 15 or 30 days."))
	today = getdate(nowdate())
	end = add_days(today, days - 1)
	items: list[dict] = []

	def add(kind, when, label, amount, ref=None, draft=False):
		if flt(amount) > 0.005:
			items.append({"kind": kind, "date": str(max(getdate(when), today)),
			              "label": label, "amount": _r(amount), "reference": ref,
			              "overdue": getdate(when) < today, "draft": draft})

	# company bills, money paid ahead netted off the oldest
	for acc in frappe.get_all("City Ledger Account",
	                          filters={"property": property, "disabled": 0},
	                          fields=["name", "company"]):
		pos = _account_position(acc.name)
		for it, amt in _netted(pos["open_items"], pos["unapplied_credit"]):
			if getdate(it["due_date"]) <= getdate(end):
				add("company_bills", it["due_date"],
				    f"{acc.company} {it.get('invoice_number') or it['folio']}",
				    amt, it["folio"])

	# advance deposits due from guests arriving in the window
	deposits: dict[str, float] = {}
	for res in frappe.get_all(
			"Reservation",
			filters={"property": property, "status": ("in", _DEPOSIT_STATUSES),
			         "check_in_date": ("between", [today, end])},
			fields=["name", "property", "status", "guest_name", "check_in_date",
			        "amount_after_tax", "advance_paid"]):
		due = flt(_deposit_state(res)["due"])
		deposits[res.name] = due
		add("deposits", res.check_in_date, f"{res.guest_name} {res.name}", due, res.name)

	# what departing guests still owe. A stay a company pays on credit is
	# left out: its bill reaches the city ledger and falls due later.
	deps = frappe.get_all(
		"Reservation",
		filters={"property": property,
		         "status": ("in", ("Checked In",) + tuple(_DEPOSIT_STATUSES)),
		         "check_out_date": ("<=", end)},
		fields=["name", "status", "guest_name", "check_out_date", "company",
		        "group_booking", "pays_own_charges", "amount_after_tax"])
	group_co = dict(frappe.get_all(
		"Group Booking", filters={"name": ("in", [r.group_booking for r in deps
		                                           if r.group_booking] or [""])},
		fields=["name", "company"], as_list=True))
	deps = [r for r in deps
	        if (r.status == "Checked In" or getdate(r.check_out_date) >= today)
	        and (r.pays_own_charges or not _company_credit(
	            r.company or group_co.get(r.group_booking)))]
	money = _stay_balances([r.name for r in deps])
	for r in deps:
		m = money.get(r.name) or {}
		due = flt(m.get("due"))
		if r.status == "Checked In" and getdate(r.check_out_date) > today:
			# ponytail: nights not yet posted are taken from the booking
			# total; extras still to come are not forecast
			due = max(due, flt(r.amount_after_tax) - flt(m.get("paid")))
		# a deposit forecast above is part of the same bill
		add("departures", r.check_out_date, f"{r.guest_name} {r.name}",
		    due - deposits.get(r.name, 0), r.name)

	for b in frappe.get_all(
			"Vendor Bill",
			filters={"property": property,
			         "status": ("in", ("Awaiting Approval", "Approved", "Part Paid")),
			         "outstanding": (">", 0), "due_date": ("<=", end)},
			fields=["name", "vendor_name", "bill_number", "due_date", "outstanding",
			        "status"]):
		add("vendor_bills", b.due_date,
		    f"{b.vendor_name} {b.bill_number or b.name}", b.outstanding, b.name,
		    draft=b.status == "Awaiting Approval")

	source = "tills" if opening in (None, "") else "entered"
	position = till_cash(property) if source == "tills" else _r(opening)
	start = position
	IN = ("company_bills", "departures", "deposits")
	out_days = []
	for i in range(days):
		d = str(add_days(today, i))
		todays = sorted((x for x in items if x["date"] == d), key=lambda x: -x["amount"])
		sums = {k: _r(sum(x["amount"] for x in todays if x["kind"] == k))
		        for k in IN + ("vendor_bills",)}
		money_in = _r(sum(sums[k] for k in IN))
		money_out = sums["vendor_bills"]
		position = _r(position + money_in - money_out)
		out_days.append({"date": d, **sums, "money_in": money_in,
		                 "money_out": money_out, "net": _r(money_in - money_out),
		                 "closing": position, "items": todays})
	weeks = []
	for i in range(0, days, 7):
		wk = out_days[i:i + 7]
		money_in = _r(sum(d["money_in"] for d in wk))
		money_out = _r(sum(d["money_out"] for d in wk))
		weeks.append({"from_date": wk[0]["date"], "to_date": wk[-1]["date"],
		              "money_in": money_in, "money_out": money_out,
		              "net": _r(money_in - money_out), "closing": wk[-1]["closing"]})
	return {
		"from_date": str(today), "to_date": str(end),
		"opening": start, "opening_source": source,
		"days": out_days, "weeks": weeks,
		"money_in": _r(sum(d["money_in"] for d in out_days)),
		"money_out": _r(sum(d["money_out"] for d in out_days)),
		"closing": position,
		"overdue_in": _r(sum(x["amount"] for x in items
		                     if x["overdue"] and x["kind"] in IN)),
		"overdue_out": _r(sum(x["amount"] for x in items
		                      if x["overdue"] and x["kind"] == "vendor_bills")),
		"draft_out": _r(sum(x["amount"] for x in items if x["draft"])),
	}


# ── management P&L ──────────────────────────────────────────────────────────

def _revenue(property: str, start, end) -> dict:
	from kamra.ledger import CHARGE_TYPE_TO_CODE
	rows = frappe.db.sql(
		f"""
		SELECT fc.charge_type, COALESCE(SUM(fc.amount), 0) AS amount
		FROM `tabFolio Charge` fc JOIN `tabFolio` f ON fc.parent = f.name
		WHERE f.property = %(p)s AND fc.posting_date BETWEEN %(s)s AND %(e)s
		  AND fc.charge_type NOT IN %(skip)s AND {NOT_FOLIO}
		GROUP BY fc.charge_type
		""", {"p": property, "s": start, "e": end, "skip": FOLIO_SKIP}, as_dict=True)
	rev = {"rooms": 0.0, "fnb": 0.0, "banquets": 0.0, "other": 0.0, "allowances": 0.0}
	for r in rows:
		group = (CHARGE_TYPE_TO_CODE.get(r.charge_type) or ("", "", "Other"))[2]
		key = ("rooms" if group == "Rooms" or r.charge_type == "Discount" else
		       "fnb" if group == "F&B" else
		       "allowances" if r.charge_type == "Allowance" else "other")
		rev[key] += flt(r.amount)
	rev["fnb"] += flt(frappe.db.sql(
		"""SELECT COALESCE(SUM(order_total), 0) FROM `tabPOS Order`
		   WHERE property = %(p)s AND status = 'Delivered' AND IFNULL(nc, 0) = 0
		     AND DATE(creation) BETWEEN %(s)s AND %(e)s""",
		{"p": property, "s": start, "e": end})[0][0])
	# a confirmed function counts once it has been held
	rev["banquets"] += flt(frappe.db.sql(
		"""SELECT COALESCE(SUM(taxable_amount), 0) FROM `tabVenue Booking`
		   WHERE property = %(p)s AND event_date BETWEEN %(s)s AND %(e)s
		     AND (status = 'Completed' OR (status = 'Confirmed' AND event_date <= %(t)s))""",
		{"p": property, "s": start, "e": end, "t": nowdate()})[0][0])
	return {k: _r(v) for k, v in rev.items()}


def tax_collected(property: str, start, end) -> float:
	"""Tax on guest bills (folio charges) plus banquets billed outside a
	folio. Tax on restaurant bills paid at the outlet is not split out."""
	folio = frappe.db.sql(
		"""SELECT COALESCE(SUM(fc.gst_amount), 0)
		   FROM `tabFolio Charge` fc JOIN `tabFolio` f ON fc.parent = f.name
		   WHERE f.property = %(p)s AND fc.posting_date BETWEEN %(s)s AND %(e)s
		     AND fc.charge_type NOT IN ('Opening Balance')""",
		{"p": property, "s": start, "e": end})[0][0]
	banquet = frappe.db.sql(
		"""SELECT COALESCE(SUM(tax_amount), 0) FROM `tabVenue Booking`
		   WHERE property = %(p)s AND event_date BETWEEN %(s)s AND %(e)s
		     AND status IN ('Confirmed', 'Completed') AND IFNULL(posted_to_folio, 0) = 0""",
		{"p": property, "s": start, "e": end})[0][0]
	return _r(flt(folio) + flt(banquet))


def _bills_in(property: str, start, end):
	return frappe.db.sql(
		"""SELECT expense_category AS category, COALESCE(SUM(amount), 0) AS amount,
		          COALESCE(SUM(tax_amount), 0) AS tax, COUNT(*) AS bills
		   FROM `tabVendor Bill`
		   WHERE property = %(p)s AND status != 'Cancelled'
		     AND bill_date BETWEEN %(s)s AND %(e)s
		   GROUP BY expense_category ORDER BY amount DESC""",
		{"p": property, "s": start, "e": end}, as_dict=True)


def _dates(from_date, to_date):
	start, end = getdate(from_date), getdate(to_date)
	if end < start:
		frappe.throw(_("The end date is before the start date."))
	if date_diff(end, start) > 366:
		frappe.throw(_("Pick a period of a year or less."))
	return start, end


@frappe.whitelist()
@require_roles("Finance", "Hotel Admin", "Kamra Agent")
def profit_and_loss(property: str, from_date: str, to_date: str):
	"""A management P&L for the period, before tax: revenue by department
	(rooms, food and beverage, banquets, other, less allowances) and
	expenses (supplier bills by category on their bill date, petty cash by
	category). Not statutory accounts: payroll, depreciation and anything
	paid outside Kamra are not in it."""
	start, end = _dates(from_date, to_date)
	rev = _revenue(property, start, end)
	bills = _bills_in(property, start, end)
	petty = frappe.db.sql(
		"""SELECT category, COALESCE(SUM(amount), 0) AS amount, COUNT(*) AS vouchers
		   FROM `tabPetty Cash Voucher`
		   WHERE property = %(p)s AND status = 'Posted'
		     AND voucher_date BETWEEN %(s)s AND %(e)s
		   GROUP BY category ORDER BY amount DESC""",
		{"p": property, "s": start, "e": end}, as_dict=True)
	revenue = [{"key": k, "amount": rev[k]}
	           for k in ("rooms", "fnb", "banquets", "other", "allowances")]
	revenue_total = _r(sum(rev.values()))
	expense_total = _r(sum(flt(b.amount) for b in bills) + sum(flt(p.amount) for p in petty))
	return {
		"from_date": str(start), "to_date": str(end),
		"revenue": revenue, "revenue_total": revenue_total,
		"supplier_bills": [{"category": b.category, "amount": _r(b.amount),
		                    "count": int(b.bills)} for b in bills],
		"petty_cash": [{"category": p.category, "amount": _r(p.amount),
		                "count": int(p.vouchers)} for p in petty],
		"expense_total": expense_total,
		"net": _r(revenue_total - expense_total),
		"tax_collected": tax_collected(property, start, end),
		"tax_on_bills": _r(sum(flt(b.tax) for b in bills)),
	}


# ── balance sheet ───────────────────────────────────────────────────────────

def _ledger(property: str, ledger: str, as_of) -> float:
	return _r(frappe.db.sql(
		"""SELECT COALESCE(SUM(debit - credit), 0) FROM `tabFolio Ledger Entry`
		   WHERE property = %s AND ledger = %s AND business_date <= %s""",
		(property, ledger, as_of))[0][0])


def payables_at(property: str, as_of) -> float:
	"""Supplier bills dated on or before `as_of` less what was paid on
	them by then."""
	billed = frappe.db.sql(
		"""SELECT COALESCE(SUM(total), 0) FROM `tabVendor Bill`
		   WHERE property = %s AND status != 'Cancelled' AND bill_date <= %s""",
		(property, as_of))[0][0]
	paid = frappe.db.sql(
		"""SELECT COALESCE(SUM(p.amount), 0) FROM `tabVendor Bill Payment` p
		   JOIN `tabVendor Bill` b ON b.name = p.parent
		   WHERE b.property = %s AND b.status != 'Cancelled'
		     AND b.bill_date <= %s AND p.payment_date <= %s""",
		(property, as_of, as_of))[0][0]
	return _r(flt(billed) - flt(paid))


@frappe.whitelist()
@require_roles("Finance", "Hotel Admin", "Kamra Agent")
def balance_sheet(property: str, as_of: str | None = None):
	"""What is owed to the hotel and what it owes, as of a date (default
	today): guest ledger and city ledger against advance deposits and
	supplier bills, plus cash in open tills when the date is today. Tax
	collected this month is shown for reference, not in the totals: Kamra
	does not record tax paid to the government. Not a full balance sheet:
	the bank, fixed assets, loans and equity are not in Kamra."""
	today = getdate(nowdate())
	d = getdate(as_of) if as_of else today
	if d > today:
		frappe.throw(_("Pick today or a date in the past."))
	cash = till_cash(property) if d == today else None
	city = _r(frappe.db.sql(
		"""SELECT COALESCE(SUM(debit - credit), 0) FROM `tabCity Ledger Entry`
		   WHERE property = %s AND posting_date <= %s""", (property, d))[0][0])
	assets = [
		{"key": "cash_in_tills", "amount": cash},
		{"key": "guest_ledger", "amount": _ledger(property, "Guest", d)},
		{"key": "city_ledger", "amount": city},
	]
	liabilities = [
		{"key": "advance_deposits", "amount": _r(-_ledger(property, "Deposit", d))},
		{"key": "payables", "amount": payables_at(property, d)},
	]
	month = get_first_day(d)
	assets_total = _r(sum(flt(a["amount"]) for a in assets))
	liabilities_total = _r(sum(flt(x["amount"]) for x in liabilities))
	return {
		"as_of": str(d),
		"assets": assets, "assets_total": assets_total,
		"liabilities": liabilities, "liabilities_total": liabilities_total,
		"net": _r(assets_total - liabilities_total),
		"tax_month_from": str(month),
		"tax_collected_month": tax_collected(property, month, d),
		"tax_on_bills_month": _r(sum(flt(b.tax) for b in _bills_in(property, month, d))),
	}
