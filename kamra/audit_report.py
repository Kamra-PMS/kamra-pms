"""The night audit report: the day, month to date and year to date, side
by side.

Where each number comes from, so nothing is counted twice:
- rooms, meal plans, minibar and other charges: posted folio charges
- food and beverage: the restaurant bills themselves (POS Order), paid at
  the outlet or charged to a room, split per item by Menu Item.is_alcohol,
  for each outlet. A bill charged to a room is also on the guest's folio
  (its line ends "(ORD-...)"), so those folio lines are left out; other
  F&B on folios (an outside POS, a desk posting) is counted as is.
- banquets: the functions held (Venue Booking, Confirmed or Completed) by
  event date: food and beverage spend, hall rent, the rest. A function's
  lines posted to a folio start with its "EVT-..." name and are left out
  of the folio figures, so they count once.
- discounts on the room come off room revenue; the room levy is a tax
  collected for someone else, not revenue
- brought forward / carried forward: the Guest, Advance deposit and City
  ledger (AR) balances before and after the day, with the day's movement

The year starts where the country pack says (India: 1 April, the
financial year); everywhere else on 1 January.
"""

from __future__ import annotations

import frappe
from frappe.utils import add_days, date_diff, flt, getdate

from kamra.authz import require_roles

FOLIO_SKIP = ("Opening Balance", "Room Levy")
FNB_TYPES = ("Food & Beverage",)
LEDGERS = (("Guest", "Guest ledger"), ("Deposit", "Advance deposits"), ("AR", "City ledger"))


def _folio(property: str, start, end) -> dict:
	row = frappe.db.sql(
		"""
		SELECT
		  COUNT(DISTINCT CASE WHEN fc.charge_type = 'Room' THEN
		        CONCAT(COALESCE(fc.reservation, f.reservation), fc.posting_date) END)
		        AS room_nights,
		  COALESCE(SUM(CASE WHEN fc.charge_type IN ('Room', 'Discount')
		        THEN fc.amount END), 0) AS rooms,
		  COALESCE(SUM(CASE WHEN fc.charge_type IN ('Meal Plan', 'Minibar')
		        THEN fc.amount END), 0) AS meal_plan_minibar,
		  COALESCE(SUM(CASE WHEN fc.charge_type IN %(fnb)s AND fc.is_alcohol = 0
		        THEN fc.amount END), 0) AS food,
		  COALESCE(SUM(CASE WHEN fc.charge_type IN %(fnb)s AND fc.is_alcohol = 1
		        THEN fc.amount END), 0) AS beverage,
		  COALESCE(SUM(CASE WHEN fc.charge_type NOT IN ('Room', 'Discount', 'Meal Plan', 'Minibar')
		        AND fc.charge_type NOT IN %(fnb)s AND fc.charge_type NOT IN %(skip)s
		        THEN fc.amount END), 0) AS other
		FROM `tabFolio Charge` fc JOIN `tabFolio` f ON fc.parent = f.name
		WHERE f.property = %(p)s AND fc.posting_date BETWEEN %(s)s AND %(e)s
		  AND IFNULL(fc.description, '') NOT LIKE '%%(ORD-%%'
		  AND IFNULL(fc.description, '') NOT LIKE 'EVT-%%'
		""", {"p": property, "s": start, "e": end, "skip": FOLIO_SKIP, "fnb": FNB_TYPES},
		as_dict=True)[0]
	return {k: flt(v) for k, v in row.items()}


def _outlets(property: str, start, end) -> list[dict]:
	"""Each outlet's food and beverage sales (before tax, after discount)."""
	rows = frappe.db.sql(
		"""
		SELECT o.outlet, o.name AS bill, o.subtotal, o.discount_amount, o.paid,
		       COALESCE(SUM(CASE WHEN mi.is_alcohol = 1 THEN i.amount END), 0) AS bev,
		       COALESCE(SUM(CASE WHEN IFNULL(mi.is_alcohol, 0) = 0 THEN i.amount END), 0) AS food
		FROM `tabPOS Order` o
		JOIN `tabPOS Order Item` i ON i.parent = o.name AND i.voided = 0
		LEFT JOIN `tabMenu Item` mi ON mi.name = i.menu_item
		WHERE o.property = %(p)s AND o.status = 'Delivered' AND o.nc = 0
		  AND COALESCE(o.business_date, DATE(o.creation)) BETWEEN %(s)s AND %(e)s
		GROUP BY o.name
		""", {"p": property, "s": start, "e": end}, as_dict=True)
	out: dict[str, dict] = {}
	for r in rows:
		gross = flt(r.food) + flt(r.bev)
		keep = 1 - (flt(r.discount_amount) / gross) if gross else 0
		o = out.setdefault(r.outlet, {"outlet": r.outlet, "bills": 0, "food": 0.0,
		                              "beverage": 0.0, "to_rooms": 0.0})
		o["bills"] += 1
		o["food"] += flt(r.food) * keep
		o["beverage"] += flt(r.bev) * keep
		if not r.paid:
			o["to_rooms"] += gross * keep
	names = dict(frappe.get_all("POS Outlet", filters={"name": ("in", list(out) or [""])},
	                            fields=["name", "outlet_name"], as_list=True))
	for o in out.values():
		o["name"] = names.get(o["outlet"]) or o["outlet"]
		o["total"] = o["food"] + o["beverage"]
		for k in ("food", "beverage", "to_rooms", "total"):
			o[k] = round(o[k], 2)
	return sorted(out.values(), key=lambda o: o["name"])


def _banquets(property: str, start, end) -> dict:
	row = frappe.db.sql(
		"""
		SELECT COUNT(*) AS functions, COALESCE(SUM(fnb_spend), 0) AS fnb,
		       COALESCE(SUM(venue_rental), 0) AS hall,
		       COALESCE(SUM(taxable_amount), 0) AS total
		FROM `tabVenue Booking`
		WHERE property = %(p)s AND status IN ('Confirmed', 'Completed')
		  AND event_date BETWEEN %(s)s AND %(e)s
		""", {"p": property, "s": start, "e": end}, as_dict=True)[0]
	fnb, hall, total = flt(row.fnb), flt(row.hall), flt(row.total)
	return {"functions": int(row.functions or 0), "fnb": fnb, "hall": hall,
	        "other": max(0.0, total - fnb - hall), "total": total}


def _period(property: str, label: str, start, end, total_rooms: int) -> dict:
	f = _folio(property, start, end)
	outlets = _outlets(property, start, end)
	banq = _banquets(property, start, end)
	# the restaurants' bills, plus F&B posted on folios some other way
	food = sum(o["food"] for o in outlets) + f["food"]
	bev = sum(o["beverage"] for o in outlets) + f["beverage"]
	nights = int(f["room_nights"])
	available = total_rooms * (date_diff(end, start) + 1)
	total = f["rooms"] + food + bev + banq["total"] + f["meal_plan_minibar"] + f["other"]
	return {
		"label": label, "from_date": str(start), "to_date": str(end),
		"rooms_sold": nights,
		"occupancy_pct": round(100 * nights / available, 1) if available else 0,
		"room_revenue": f["rooms"],
		"adr": round(f["rooms"] / nights, 0) if nights else 0,
		"revpar": round(f["rooms"] / available, 0) if available else 0,
		"food": round(food, 2), "beverage": round(bev, 2),
		"banquets": banq["total"], "meal_plan_minibar": f["meal_plan_minibar"],
		"other": f["other"], "total_revenue": round(total, 2),
		"outlets": outlets, "banquet": banq,
	}


def _balances(property: str, d) -> list[dict]:
	from kamra.ledger import ledger_balances as guarded
	from kamra.night_audit import _raw
	# the report's own role check has run; the ledger endpoint's is narrower
	ledger_balances = _raw(guarded)
	before = {r["ledger"]: r for r in ledger_balances(property, str(add_days(d, -1)))["ledgers"]}
	after = {r["ledger"]: r for r in ledger_balances(property, str(d))["ledgers"]}
	# the city ledger is what companies owe: City Ledger Entry, as the
	# Receivables screen and the credit limit check read it, so a company
	# payment not yet applied to a folio counts too
	before["AR"], after["AR"] = _city_ledger(property, add_days(d, -1)), _city_ledger(property, d)
	return [{
		"ledger": key, "label": label,
		"brought_forward": round(before[key]["balance"], 2),
		"debit": round(after[key]["debit"] - before[key]["debit"], 2),
		"credit": round(after[key]["credit"] - before[key]["credit"], 2),
		"carried_forward": round(after[key]["balance"], 2),
	} for key, label in LEDGERS]


def _city_ledger(property: str, d) -> dict:
	debit, credit = frappe.db.sql(
		"""SELECT COALESCE(SUM(debit), 0), COALESCE(SUM(credit), 0)
		   FROM `tabCity Ledger Entry` WHERE property = %s AND posting_date <= %s""",
		(property, str(d)))[0]
	return {"debit": flt(debit), "credit": flt(credit), "balance": flt(debit) - flt(credit)}


def build(property: str, d) -> dict:
	from kamra.localization import financial_year_start, pack_for
	d = getdate(d)
	total_rooms = frappe.db.count("Room", {"property": property}) or 0
	return {
		"business_date": str(d),
		"total_rooms": total_rooms,
		"periods": [
			_period(property, "Day", d, d, total_rooms),
			_period(property, "Month to date", d.replace(day=1), d, total_rooms),
			_period(property, "Year to date", financial_year_start(pack_for(property), d), d,
			        total_rooms),
		],
		"balances": _balances(property, d),
	}


@frappe.whitelist()
@require_roles("Finance", "Revenue Manager", "Night Auditor", "Kamra Agent")
def night_audit_report(property: str, date: str | None = None):
	"""The night audit report for a business date (default: the last one
	closed): rooms, food and beverage separately, each outlet, banquets,
	meal plans and minibar, other income, for the day, month to date and
	year to date, plus each ledger's balance brought and carried forward."""
	from kamra.business_date import get_business_date
	from kamra.authz import assert_property_access
	assert_property_access(property)
	return build(property, date or add_days(get_business_date(property), -1))
