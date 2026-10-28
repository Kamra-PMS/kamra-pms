"""Night audit checklist and the saved audit pack.

Before the night audit closes a business date the night auditor walks a
checklist: tills still open, restaurant bills not settled, guests due out who
are still in house, arrivals that will turn into no-shows, room nights posted
off the booked rate, outlet bills charged to rooms, folios owing a lot,
companies over their credit limit, and rooms whose board status disagrees with
the front office. `night_audit_precheck` answers that checklist, read-only.

Each check has a severity:

  block  open tills, open POS bills, departures still in house (each can be
         switched to a warning under Settings → Front Desk → Night audit
         checklist). A manual run refuses while a blocking check has open
         items, unless a supervisor acknowledges it with a reason.
  warn   listed, never stops the audit.
  info   for the auditor to eyeball (POS room postings), never stops it.

The scheduled run (night_audit_time, default 03:00) follows `na_auto_audit_with_blockers`: "Run and report
exceptions" (default - the date always rolls, the open items go in the pack)
or "Hold and alert" (the date is not rolled, Hotel Admin and Finance are
alerted).

Every Night Audit Run stores a JSON audit pack (`report_pack`): the manager's
flash, revenue by transaction code, ledger balances, occupancy / ADR / RevPAR,
the in-house list, departures, arrivals, no-shows with the policy outcome,
high balances, credit limits, POS room postings, rate variances, the cashier
sessions and the pre-check results with their acknowledgements.
`night_audit_pack` returns it; `rebuild_audit_pack` rebuilds a missing pack
so the desk can still print. `recover_stuck_business_date` advances the BD
when a Completed run exists for the current date but the roll did not stick
(restore / ops surgery) — money is never re-posted.

Money and the date roll still go only through `kamra.folio.run_night_audit`.
"""

from __future__ import annotations

import inspect
import json
import re

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime

from kamra.authz import require_roles

AUDIT_ROLES = ("Front Desk", "Finance", "Night Auditor", "Hotel Admin", "Kamra Agent")

RUN_AND_REPORT = "Run and report exceptions"
HOLD_AND_ALERT = "Hold and alert"

# check key -> the setting that makes it blocking (on by default)
BLOCKABLE = {
	"open_tills": "na_block_open_tills",
	"open_pos_bills": "na_block_open_pos",
	"departures_due": "na_block_departures",
}

ORDER = ("open_tills", "open_pos_bills", "departures_due", "arrivals_pending",
         "rate_variance", "zero_rate", "pos_room_postings", "high_balance",
         "departed_balances", "credit_limit", "overdue_ar", "room_status",
         "vacant_rooms")

# The End of Day wizard, in Opera's order: (key, title, the checks it shows)
STEPS = (
	("prepare", "Prepare End of Day", ()),
	("arrivals", "Arrivals not checked in", ("arrivals_pending",)),
	("departures", "Departures not checked out", ("departures_due",)),
	("folios", "Open folios and high balances",
	 ("high_balance", "departed_balances", "credit_limit", "overdue_ar")),
	("outlets", "Outlets and room postings", ("open_pos_bills", "pos_room_postings")),
	("rates", "Rate check", ("rate_variance", "zero_rate")),
	("rooms", "Room status", ("room_status", "vacant_rooms")),
	("cashiers", "Cashier closure", ("open_tills",)),
	("notes", "Notes", ()),
	("run", "Post room and tax and roll the business date", ()),
	("reports", "Print final reports", ()),
	("finalize", "Finalize", ()),
)
STEP_KEYS = tuple(k for k, _t, _c in STEPS)
RUN_STEP = STEP_KEYS.index("run") + 1  # 1-based

# rows kept per list in a check and in the pack - a busy hotel's in-house
# list fits; a runaway query does not bloat the run record
MAX_ITEMS = 500

OPEN_POS = ("Placed", "Confirmed", "Preparing")
_ORDER_REF = re.compile(r"\(([^()]+)\)\s*$")


# --- small helpers -------------------------------------------------------------

def _raw(fn):
	"""The function under @whitelist / @require_roles: the audit has already
	checked who may run it, and the scheduler has no session roles."""
	return inspect.unwrap(fn)


def _setting(property: str, key: str):
	from kamra.settings import get_setting
	return get_setting(property, key)


def _room_no(room: str | None) -> str | None:
	if not room:
		return None
	return frappe.db.get_value("Room", room, "room_number") or room.split("-")[-1]


def _guest_folio(reservation: str) -> dict:
	return frappe.db.get_value(
		"Folio", {"reservation": reservation, "folio_type": "Guest"},
		["name", "balance", "status"], as_dict=True) or {}


def _check(key: str, title: str, severity: str, items: list, action: str,
           resolve: str | None = None, **extra) -> dict:
	return {
		"key": key,
		"title": title,
		"severity": severity,
		"count": len(items),
		"items": items[:MAX_ITEMS],
		"truncated": len(items) > MAX_ITEMS,
		"action": action,
		"resolve": resolve,
		**extra,
	}


def _severity(property: str, key: str) -> str:
	return "block" if cint(_setting(property, BLOCKABLE[key])) else "warn"


def _iso(v) -> str | None:
	return str(v) if v not in (None, "") else None


def _stay_cols(res, bd: str | None = None) -> dict:
	"""The columns Opera's arrival / departure lists show for a stay."""
	from kamra.folio import locked_night
	rate = None
	night = locked_night(res, bd or res.check_in_date)
	if night is not None:
		rate = flt(night.rate)
	f = _guest_folio(res.name)
	nights = (getdate(res.check_out_date) - getdate(res.check_in_date)).days
	return {
		"reservation": res.name, "guest_name": res.guest_name,
		"check_in_date": _iso(res.check_in_date),
		"check_out_date": _iso(res.check_out_date),
		"nights": max(nights, 0),
		"room_type": (res.room_type or "").split("-")[-1],
		"rate_plan": (res.get("rate_plan") or "").split("-")[-1] or None,
		"rate": rate,
		"room": _room_no(res.room),
		"folio": f.get("name"), "balance": flt(f.get("balance"), 2),
		"adults": cint(res.adults), "children": cint(res.children),
		"source": res.get("channel") or res.get("source"),
		"company": res.get("company"),
	}


# --- the checks ------------------------------------------------------------------

def check_open_tills(property: str, bd: str) -> dict:
	rows = frappe.db.sql(
		"""
		SELECT s.name, s.user, s.cashier, s.business_date, s.opened_at,
		       s.opening_float, s.terminal,
		       (SELECT COUNT(*) FROM `tabCashier Transaction` t
		        WHERE t.session = s.name) AS txns,
		       (SELECT COALESCE(SUM(t.amount), 0) FROM `tabCashier Transaction` t
		        WHERE t.session = s.name AND t.mode = 'Cash'
		          AND t.kind IN ('Payment', 'Exchange', 'Refund')) AS cash_in
		FROM `tabCashier Session` s
		WHERE s.property = %(p)s AND s.status = 'Open'
		  AND (s.business_date <= %(d)s OR s.business_date IS NULL)
		ORDER BY s.opened_at
		""", {"p": property, "d": bd}, as_dict=True)
	items = [{
		"session": r.name,
		"user": r.user,
		"user_name": frappe.db.get_value("User", r.user, "full_name") or r.user,
		"cashier_id": frappe.db.get_value("Cashier", r.cashier, "cashier_id"),
		"business_date": _iso(r.business_date),
		"opened_at": _iso(r.opened_at),
		"terminal": r.terminal,
		"opening_float": flt(r.opening_float),
		"transactions": cint(r.txns),
		"cash_taken": flt(r.cash_in),
	} for r in rows]
	return _check(
		"open_tills", "Open cashier tills", _severity(property, "open_tills"),
		items, "Close each till under Finance → Cashier: count the cash and "
		       "record the variance.", "/cashier/sessions")


def check_open_pos_bills(property: str, bd: str) -> dict:
	open_rows = frappe.get_all(
		"POS Order",
		filters={"property": property, "status": ("in", OPEN_POS)},
		fields=["name", "outlet", "status", "table_no", "room", "reservation",
		        "customer_name", "order_total", "kot_no", "kot_fired", "creation"],
		order_by="creation asc", limit_page_length=0)
	# served bills that were neither paid at the outlet, posted to a room nor
	# made complimentary - money nobody is holding
	served = frappe.db.sql(
		"""
		SELECT name, outlet, status, table_no, room, reservation, customer_name,
		       order_total, kot_no, creation
		FROM `tabPOS Order`
		WHERE property = %(p)s AND status = 'Delivered' AND IFNULL(paid, 0) = 0
		  AND IFNULL(posted_to_folio, 0) = 0 AND IFNULL(nc, 0) = 0
		  AND IFNULL(order_total, 0) > 0 AND DATE(creation) >= %(d)s
		ORDER BY creation
		""", {"p": property, "d": bd}, as_dict=True)
	items = []
	# an open bill nobody sent to the kitchen is named as such: it is cancelled
	# at the till with a reason, nothing to void
	for r, state in [(r, "open" if r.kot_fired else "open, not sent to kitchen")
	                 for r in open_rows] + \
			[(r, "served, not settled") for r in served]:
		items.append({
			"order": r.name,
			"bill_no": r.name,
			"kot_no": r.kot_no,
			"outlet": (r.outlet or "").split("-")[-1],
			"outlet_id": r.outlet,
			"table_no": r.table_no,
			"room": _room_no(r.room),
			"reservation": r.reservation,
			"guest_name": r.customer_name,
			"amount": flt(r.order_total),
			"status": r.status,
			"state": state,
			"opened_at": _iso(r.creation),
		})
	return _check(
		"open_pos_bills", "Open restaurant bills",
		_severity(property, "open_pos_bills"), items,
		"Settle each bill at its outlet: take payment, charge it to an "
		"in-house room, mark it NC or cancel it.", "/pos",
		amount=round(sum(i["amount"] for i in items), 2))


def check_departures_due(property: str, bd: str) -> dict:
	rows = frappe.get_all(
		"Reservation",
		filters={"property": property, "status": "Checked In",
		         "check_out_date": ("<=", bd)},
		fields=["name", "guest_name", "room", "check_in_date", "check_out_date"],
		order_by="check_out_date asc, name asc", limit_page_length=0)
	items = [_stay_cols(frappe.get_doc("Reservation", r.name)) for r in rows]
	return _check(
		"departures_due", "Departures still in house",
		_severity(property, "departures_due"), items,
		"Check the guest out, or extend the stay if they are staying on. "
		"The audit does not post a night for a stay past its departure date.",
		"/")


def check_arrivals_pending(property: str, bd: str, run_at=None) -> dict:
	from kamra import no_show
	from kamra.folio import audit_clock, policy_fee
	pol = no_show.policy(property)
	run_at = run_at or audit_clock(property)
	names = frappe.get_all(
		"Reservation",
		filters={"property": property, "status": "Confirmed",
		         "check_in_date": ("<=", bd)},
		order_by="check_in_date asc, name asc", pluck="name",
		limit_page_length=0)
	items = []
	counts = {"no_show": 0, "hold": 0, "defer": 0}
	for name in names:
		res = frappe.get_doc("Reservation", name)
		o = no_show.audit_outcome(res, pol, bd, run_at)
		counts[o.outcome] += 1
		fee = 0.0
		if o.outcome == "no_show":
			if o.fee == "charge":
				fee = flt(policy_fee(res, pol.charge), 2)
				label = f"No show - {pol.charge.lower()} fee"
			elif o.fee == "waived":
				label = f"No show - fee waived ({o.reason})"
			else:
				label = "No show - no fee"
		elif o.outcome == "hold":
			label = f"Held as a late arrival ({o.reason})"
		else:
			label = "Stays Due In until the next audit (one day later)"
		items.append({
			**_stay_cols(res),
			"eta": res.get("eta") or None,
			"outcome": o.outcome, "fee": o.fee, "fee_amount": fee,
			"policy": label,
		})
	return _check(
		"arrivals_pending", "Arrivals not checked in", "warn", items,
		"Check in guests who have arrived, flag Late arrival for those still "
		"coming, or cancel. Otherwise the no-show policy applies as shown.",
		"/", outcomes=counts)


def _expected_night(res, bd: str) -> tuple[float | None, str]:
	from kamra.folio import _nightly_room_rate, locked_night
	locked = locked_night(res, bd)
	if locked is not None:
		return flt(locked.rate), "locked nightly rate"
	try:
		return flt(_nightly_room_rate(res, bd)), "reservation rate"
	except Exception:
		return None, "no rate"


def check_rate_variance(property: str, bd: str) -> dict:
	tol = flt(_setting(property, "na_rate_variance_tolerance"))
	rows = frappe.db.sql(
		"""
		SELECT COALESCE(NULLIF(fc.reservation, ''), f.reservation) AS reservation,
		       MIN(fc.parent) AS folio, SUM(fc.amount) AS posted,
		       COUNT(*) AS n_lines, MIN(IFNULL(fc.auto_posted, 0)) AS all_auto
		FROM `tabFolio Charge` fc
		JOIN `tabFolio` f ON fc.parent = f.name
		WHERE f.property = %(p)s AND fc.posting_date = %(d)s
		  AND fc.charge_type = 'Room'
		GROUP BY COALESCE(NULLIF(fc.reservation, ''), f.reservation)
		""", {"p": property, "d": bd}, as_dict=True)
	items = []
	for r in rows:
		if not r.reservation or not frappe.db.exists("Reservation", r.reservation):
			continue
		res = frappe.get_doc("Reservation", r.reservation)
		expected, basis = _expected_night(res, bd)
		if expected is None:
			continue
		posted = flt(r.posted, 2)
		diff = round(posted - expected, 2)
		if abs(diff) <= tol:
			continue
		items.append({
			"reservation": res.name, "guest_name": res.guest_name,
			"room": _room_no(res.room), "folio": r.folio,
			"posted": posted, "expected": round(expected, 2),
			"difference": diff, "basis": basis, "lines": cint(r.n_lines),
			"manual": not cint(r.all_auto),
		})
	return _check(
		"rate_variance", "Room rate variances", "warn", items,
		"Compare with the booking: void and re-post a wrong room charge, or "
		"note why the rate was changed (a manual posting, a re-rate).",
		None, tolerance=tol)


def check_pos_room_postings(property: str, bd: str) -> dict:
	rows = frappe.db.sql(
		"""
		SELECT fc.name AS row_name, fc.parent AS folio, fc.description,
		       fc.amount, fc.total,
		       COALESCE(NULLIF(fc.reservation, ''), f.reservation) AS reservation,
		       f.guest_name
		FROM `tabFolio Charge` fc
		JOIN `tabFolio` f ON fc.parent = f.name
		WHERE f.property = %(p)s AND fc.posting_date = %(d)s
		  AND fc.charge_type = 'Food & Beverage' AND fc.description LIKE '%%(%%)'
		ORDER BY fc.creation
		""", {"p": property, "d": bd}, as_dict=True)
	refs = {}
	for r in rows:
		m = _ORDER_REF.search(r.description or "")
		if m:
			refs[r.row_name] = m.group(1)
	orders = {o.name: o for o in frappe.get_all(
		"POS Order", filters={"name": ("in", list(set(refs.values())) or [""])},
		fields=["name", "outlet", "room", "reservation", "kot_no", "table_no",
		        "order_total"])}
	items = []
	mismatches = 0
	for r in rows:
		o = orders.get(refs.get(r.row_name))
		if not o:
			continue
		res = frappe.db.get_value("Reservation", r.reservation,
		                          ["room", "guest_name"], as_dict=True) or {}
		wrong = bool(o.room and res.get("room") and o.room != res.get("room"))
		mismatches += wrong
		items.append({
			"bill_no": o.name, "order": o.name, "kot_no": o.kot_no,
			"outlet": (o.outlet or "").split("-")[-1], "outlet_id": o.outlet,
			"table_no": o.table_no,
			"room": _room_no(res.get("room")), "bill_room": _room_no(o.room),
			"reservation": r.reservation,
			"guest_name": res.get("guest_name") or r.guest_name,
			"folio": r.folio, "amount": flt(r.amount), "total": flt(r.total),
			"room_mismatch": wrong,
		})
	return _check(
		"pos_room_postings", "Outlet bills charged to rooms",
		"warn" if mismatches else "info", items,
		"Eyeball each bill against the room and guest. A bill on the wrong "
		"room is moved with a folio transfer, not re-posted.", "/pos-dashboard",
		mismatches=mismatches,
		amount=round(sum(i["total"] for i in items), 2))


def check_high_balance(property: str) -> dict:
	threshold = flt(_setting(property, "na_high_balance_threshold"))
	items = []
	if threshold > 0:
		rows = frappe.db.sql(
			"""
			SELECT f.name, f.folio_type, f.balance, f.reservation,
			       r.guest_name, r.room, r.check_out_date
			FROM `tabFolio` f
			JOIN `tabReservation` r ON r.name = f.reservation
			WHERE f.property = %(p)s AND f.status = 'Open'
			  AND r.status = 'Checked In' AND f.balance > %(t)s
			ORDER BY f.balance DESC
			""", {"p": property, "t": threshold}, as_dict=True)
		items = [{
			"folio": r.name, "folio_type": r.folio_type,
			"reservation": r.reservation, "guest_name": r.guest_name,
			"room": _room_no(r.room), "check_out_date": _iso(r.check_out_date),
			"balance": flt(r.balance, 2),
		} for r in rows]
	return _check(
		"high_balance", "High balances in house", "warn", items,
		"Take a payment or an authorisation, or ask the guest to settle "
		"part of the bill.", None, threshold=threshold,
		enabled=threshold > 0)


def check_credit_limit(property: str) -> dict:
	from kamra.ledger import company_payer_of
	accounts = frappe.get_all(
		"City Ledger Account",
		filters={"property": property, "disabled": 0, "credit_limit": (">", 0)},
		fields=["name", "company", "account_number", "credit_limit"])
	items = []
	if accounts:
		folios = frappe.db.sql(
			"""
			SELECT f.name, f.folio_type, f.reservation, f.group_booking,
			       f.balance, r.guest_name, r.room
			FROM `tabFolio` f
			JOIN `tabReservation` r ON r.name = f.reservation
			WHERE f.property = %(p)s AND f.status = 'Open'
			  AND f.folio_type IN ('Company', 'Group')
			  AND r.status = 'Checked In'
			""", {"p": property}, as_dict=True)
		by_company: dict[str, list] = {}
		for f in folios:
			company = company_payer_of(f)
			if company:
				by_company.setdefault(company, []).append(f)
		for a in accounts:
			ar = flt(frappe.db.sql(
				"""SELECT COALESCE(SUM(debit - credit), 0)
				   FROM `tabCity Ledger Entry` WHERE account = %s""", a.name)[0][0], 2)
			mine = by_company.get(a.company) or []
			in_house = round(sum(max(flt(f.balance), 0) for f in mine), 2)
			exposure = round(ar + in_house, 2)
			if exposure <= flt(a.credit_limit):
				continue
			items.append({
				"account": a.name, "company": a.company,
				"account_number": a.account_number,
				"credit_limit": flt(a.credit_limit), "ar_balance": ar,
				"in_house": in_house, "exposure": exposure,
				"over_by": round(exposure - flt(a.credit_limit), 2),
				"folios": [{"folio": f.name, "reservation": f.reservation,
				            "guest_name": f.guest_name, "room": _room_no(f.room),
				            "balance": flt(f.balance, 2)} for f in mine],
			})
	return _check(
		"credit_limit", "Companies over their credit limit", "warn", items,
		"Ask the company for a payment, or have Finance raise the limit "
		"before more is billed to them.", "/ledgers")


def check_overdue_ar(property: str) -> dict:
	"""Companies with city ledger bills past their due date (invoice date +
	credit days), by company - what to chase before billing them more."""
	from kamra.ledger import _account_position
	items = []
	for a in frappe.get_all(
			"City Ledger Account",
			filters={"property": property, "disabled": 0},
			fields=["name", "company", "account_number", "credit_limit"],
			limit_page_length=0):
		pos = _account_position(a.name)
		if pos["overdue"] <= 0.005:
			continue
		items.append({
			"account": a.name, "company": a.company,
			"account_number": a.account_number,
			"credit_days": pos["credit_days"],
			"overdue": pos["overdue"], "d1_30": pos["d1_30"],
			"d31_60": pos["d31_60"], "d61_90": pos["d61_90"],
			"d90p": pos["d90p"],
			"oldest_due_date": pos["oldest_overdue_due_date"],
			"balance": round(pos["open_balance"] - pos["unapplied_credit"], 2),
		})
	items.sort(key=lambda r: -r["overdue"])
	return _check(
		"overdue_ar", "Companies with overdue bills", "warn", items,
		"Chase the company for payment. Credit control (Settings, Finance) can "
		"warn or block more billing to a company with overdue bills.", "/ledgers",
		total=round(sum(r["overdue"] for r in items), 2))


def check_room_status(property: str) -> dict:
	rooms = frappe.get_all(
		"Room", filters={"property": property},
		fields=["name", "room_number", "housekeeping_status", "occupancy_status"],
		limit_page_length=0)
	in_house: dict[str, dict] = {}
	for r in frappe.get_all(
			"Reservation",
			filters={"property": property, "status": "Checked In",
			         "room": ("is", "set")},
			fields=["name", "room", "guest_name"], limit_page_length=0):
		in_house.setdefault(r.room, r)
	items = []
	for room in rooms:
		guest = in_house.get(room.name)
		issue = None
		if guest and room.occupancy_status != "Occupied":
			issue = "Guest in house, room board shows Vacant"
		elif not guest and room.occupancy_status == "Occupied":
			issue = "Room board shows Occupied, no guest in house"
		elif guest and room.housekeeping_status == "Out of Order":
			issue = "Out of order room has an in-house guest"
		if not issue:
			continue
		items.append({
			"room": room.room_number, "room_id": room.name,
			"front_office": "Occupied" if guest else "Vacant",
			"room_board": room.occupancy_status or "Vacant",
			"housekeeping_status": room.housekeeping_status,
			"reservation": guest.name if guest else None,
			"guest_name": guest.guest_name if guest else None,
			"issue": issue,
		})
	items.sort(key=lambda i: (len(str(i["room"])), str(i["room"])))
	return _check(
		"room_status", "Room status discrepancies", "warn", items,
		"Walk the room: release a room left Occupied after check-out, or "
		"correct the board for a room that is in use.", "/housekeeping-board")


def check_departed_balances(property: str) -> dict:
	rows = frappe.db.sql(
		"""
		SELECT f.name, f.folio_type, f.balance, f.reservation,
		       r.guest_name, r.room, r.check_out_date
		FROM `tabFolio` f
		JOIN `tabReservation` r ON r.name = f.reservation
		WHERE f.property = %(p)s AND f.status = 'Open'
		  AND r.status = 'Checked Out' AND ABS(f.balance) > 0.009
		ORDER BY r.check_out_date DESC
		""", {"p": property}, as_dict=True)
	items = [{
		"folio": r.name, "folio_type": r.folio_type,
		"reservation": r.reservation, "guest_name": r.guest_name,
		"room": _room_no(r.room), "check_out_date": _iso(r.check_out_date),
		"balance": flt(r.balance, 2),
	} for r in rows]
	return _check(
		"departed_balances", "Balances on departed stays", "warn", items,
		"Collect, refund, move to the city ledger or write off with an "
		"allowance, then close the folio.", None)


def _in_house_names(property: str, bd: str) -> list[str]:
	return frappe.get_all(
		"Reservation",
		filters={"property": property, "status": "Checked In",
		         "check_in_date": ("<=", bd), "check_out_date": (">", bd)},
		order_by="room asc", pluck="name", limit_page_length=0)


def check_zero_rate(property: str, bd: str) -> dict:
	items = []
	for name in _in_house_names(property, bd):
		res = frappe.get_doc("Reservation", name)
		expected, basis = _expected_night(res, bd)
		if expected is None or expected > 0.009:
			continue
		items.append({**_stay_cols(res, bd), "rate": 0.0, "basis": basis})
	return _check(
		"zero_rate", "Zero-rate and complimentary rooms", "warn", items,
		"Confirm each complimentary stay was approved; otherwise correct "
		"the rate before the audit posts the night.", None)


def check_vacant_rooms(property: str) -> dict:
	occupied = set(frappe.get_all(
		"Reservation", filters={"property": property, "status": "Checked In",
		                        "room": ("is", "set")}, pluck="room",
		limit_page_length=0))
	rooms = frappe.get_all(
		"Room", filters={"property": property},
		fields=["name", "room_number", "room_type", "housekeeping_status",
		        "occupancy_status"], limit_page_length=0)
	items = [{
		"room": r.room_number, "room_id": r.name,
		"room_type": (r.room_type or "").split("-")[-1],
		"housekeeping_status": r.housekeeping_status,
		"room_board": r.occupancy_status or "Vacant",
	} for r in rooms if r.name not in occupied]
	items.sort(key=lambda i: (len(str(i["room"])), str(i["room"])))
	return _check(
		"vacant_rooms", "Vacant rooms", "info", items,
		"Vacant rooms that are Dirty are cleaned before the next arrivals.",
		"/housekeeping-board")


def run_checks(property: str, business_date: str | None = None,
               run_at=None) -> list[dict]:
	"""Every pre-check for the business date, in checklist order."""
	from kamra.business_date import ensure_business_date
	bd = str(getdate(business_date or ensure_business_date(property)))
	return [
		check_open_tills(property, bd),
		check_open_pos_bills(property, bd),
		check_departures_due(property, bd),
		check_arrivals_pending(property, bd, run_at),
		check_rate_variance(property, bd),
		check_zero_rate(property, bd),
		check_pos_room_postings(property, bd),
		check_high_balance(property),
		check_departed_balances(property),
		check_credit_limit(property),
		check_overdue_ar(property),
		check_room_status(property),
		check_vacant_rooms(property),
	]


def open_blockers(checks: list[dict]) -> list[dict]:
	return [c for c in checks if c["severity"] == "block" and c["count"]]


def parse_keys(value) -> list[str]:
	"""acknowledge=[keys] as a list, a JSON list or a comma string."""
	if not value:
		return []
	if isinstance(value, str):
		value = value.strip()
		if value.startswith("["):
			try:
				value = json.loads(value)
			except ValueError:
				frappe.throw(_("acknowledge must be a list of check keys."))
		else:
			value = value.split(",")
	return [str(v).strip() for v in value if str(v).strip()]


def acknowledgement_rows(blockers: list[dict], keys: list[str], note: str,
                         by: str | None = None, auto: bool = False) -> list[dict]:
	at = str(now_datetime())
	by = by or frappe.session.user
	return [{
		"key": c["key"], "title": c["title"], "count": c["count"],
		"note": note, "by": by,
		"by_name": frappe.db.get_value("User", by, "full_name") or by,
		"at": at, "auto": 1 if auto else 0,
	} for c in blockers if c["key"] in keys]


def _loads(raw, default):
	if not raw:
		return default
	try:
		return json.loads(raw)
	except ValueError:
		return default


def draft_acknowledgements(draft: str | None) -> list[dict]:
	"""Blocking checks acknowledged in the End of Day wizard for the draft."""
	if not draft:
		return []
	return _loads(frappe.db.get_value("Night Audit Run", draft,
	                                  "acknowledgements"), [])


# --- endpoints -----------------------------------------------------------------

def _last_hold(property: str) -> dict | None:
	"""The latest scheduled run that held the audit, if no audit ran since."""
	row = frappe.get_all(
		"Agent Action Log",
		filters={"property": property, "action_type": "night_audit_held"},
		fields=["creation", "rationale"], order_by="creation desc", limit=1)
	if not row:
		return None
	last_run = frappe.db.get_value(
		"Night Audit Run", {"property": property, "status": ("!=", "Draft")},
		"creation", order_by="creation desc")
	if last_run and last_run > row[0].creation:
		return None
	return {"at": str(row[0].creation), "detail": row[0].rationale}


@frappe.whitelist()
@require_roles(*AUDIT_ROLES)
def night_audit_precheck(property: str):
	"""The night audit checklist for the property's current business date.
	Read-only. Each check: key, title, severity (block | warn | info),
	count, items (with reservation / folio / room / guest / amount /
	outlet and bill no where they apply) and a suggested action. A manual
	audit refuses while a blocking check has items, unless each one is
	acknowledged with a reason (run_night_audit acknowledge=[keys], note)."""
	from kamra.business_date import get_business_date
	from kamra.crs import assert_property_access
	assert_property_access(property)
	if not frappe.db.exists("Property", property):
		frappe.throw(_("Unknown property."))
	bd = get_business_date(property)
	checks = run_checks(property, bd)
	blockers = [c["key"] for c in open_blockers(checks)]
	return {
		"property": property,
		"business_date": bd,
		"generated_at": str(now_datetime()),
		"checks": checks,
		"blockers": blockers,
		"can_run": not blockers,
		"already_ran": bool(frappe.db.exists(
			"Night Audit Run", {"property": property, "business_date": bd,
			                    "status": ("!=", "Draft")})),
		"auto_audit_with_blockers": _setting(property, "na_auto_audit_with_blockers"),
		"held": _last_hold(property),
	}


@frappe.whitelist()
@require_roles(*AUDIT_ROLES, scope={"audit": "Night Audit Run"})
def night_audit_pack(audit: str):
	"""The saved audit pack of one Night Audit Run. Missing packs answer
	has_pack: false with a message; rebuild_audit_pack can recreate them."""
	if not frappe.db.exists("Night Audit Run", audit):
		frappe.throw(_("Night audit run {0} not found.").format(audit),
		             frappe.DoesNotExistError)
	run = frappe.db.get_value(
		"Night Audit Run", audit,
		["name", "property", "business_date", "status", "room_charges_posted",
		 "amount_posted", "no_shows_flagged", "late_arrivals_held",
		 "no_show_fees_waived", "folios_opened", "run_trigger", "run_by",
		 "exceptions", "auditor_notes", "report_pack", "creation"], as_dict=True)
	from kamra.crs import assert_property_access
	assert_property_access(run.property)
	raw = run.pop("report_pack", None)
	run["business_date"] = _iso(run.business_date)
	run["creation"] = _iso(run.creation)
	pack = None
	if raw:
		try:
			pack = json.loads(raw)
		except ValueError:
			pack = None
	if not pack:
		return {"audit": audit, "run": run, "has_pack": False, "pack": None,
		        "can_rebuild": run.status != "Draft",
		        "message": _("No audit pack was saved for this run. Rebuild it "
		                     "to print the night's reports.")}
	return {"audit": audit, "run": run, "has_pack": True, "pack": pack,
	        "can_rebuild": True}


def _pack_summary_from_run(run) -> dict:
	return {
		"audit": run.name,
		"status": run.status,
		"room_charges_posted": cint(run.room_charges_posted),
		"amount_posted": flt(run.amount_posted),
		"no_shows_flagged": cint(run.no_shows_flagged),
		"late_arrivals_held": cint(run.late_arrivals_held),
		"no_show_fees_waived": cint(run.no_show_fees_waived),
		"folios_opened": cint(run.folios_opened),
		"trigger": run.run_trigger,
		"run_by": run.run_by,
		"exceptions": cint(run.exceptions),
		"notes": run.auditor_notes,
	}


def _no_shows_for_pack(property: str, bd: str) -> list[dict]:
	rows = frappe.get_all(
		"Reservation",
		filters={"property": property, "status": "No Show", "check_in_date": bd},
		fields=["name", "guest_name", "room", "room_type", "source", "channel"],
		order_by="name asc", limit_page_length=MAX_ITEMS)
	return [{
		"reservation": r.name, "guest_name": r.guest_name,
		"room": _room_no(r.room), "room_type": (r.room_type or "").split("-")[-1],
		"source": r.channel or r.source, "outcome": "no_show",
	} for r in rows]


@frappe.whitelist(methods=["POST"])
@require_roles(*AUDIT_ROLES, scope={"audit": "Night Audit Run"})
def rebuild_audit_pack(audit: str):
	"""Rebuild and save the printable audit pack for a completed run.
	Use when the automatic night left has_pack false, or to refresh the
	pack. Does not re-post charges or roll the business date."""
	if not frappe.db.exists("Night Audit Run", audit):
		frappe.throw(_("Night audit run {0} not found.").format(audit),
		             frappe.DoesNotExistError)
	run = frappe.get_doc("Night Audit Run", audit)
	from kamra.crs import assert_property_access
	assert_property_access(run.property)
	if run.status == "Draft":
		frappe.throw(_("Finish End of Day before printing the audit pack."))
	bd = _iso(run.business_date)
	acks = []
	if run.acknowledgements:
		try:
			acks = json.loads(run.acknowledgements)
		except ValueError:
			acks = []
	# Prefer the original pack's prechecks / held_late when a partial JSON
	# still exists (failed save mid-write). Otherwise rebuild live sections
	# and mark prechecks as rebuilt so printers know they are not the night's
	# snapshot. Held late arrivals cannot be reconstructed after the fact.
	prior = None
	if run.report_pack:
		try:
			prior = json.loads(run.report_pack)
		except ValueError:
			prior = None
	checks = (prior or {}).get("prechecks") or run_checks(run.property, bd)
	held_late = list((prior or {}).get("held_late_arrivals") or [])
	if not held_late and cint(run.late_arrivals_held):
		held_late = [{
			"reservation": None,
			"guest_name": None,
			"eta": None,
			"reason": _("({n} late arrival(s) held that night — list not "
			            "saved on the original pack)").format(
				n=cint(run.late_arrivals_held)),
		}]
	summary = _pack_summary_from_run(run)
	pack = build_pack(
		run.property, bd, checks=checks, acknowledgements=acks,
		summary=summary, no_shows=_no_shows_for_pack(run.property, bd),
		held_late=held_late)
	pack["rebuilt_at"] = str(now_datetime())
	pack["rebuilt_by"] = frappe.session.user
	pack["prechecks_source"] = (
		"original" if (prior or {}).get("prechecks") else "live_rebuild")
	run.report_pack = json.dumps(pack, default=str)
	run.save(ignore_permissions=True)
	from kamra.savings import log_action
	log_action(
		"rebuild_audit_pack", "Night Audit Run", run.name, run.property,
		rationale=f"Rebuilt audit pack for {bd}",
		channel="MCP" if frappe.flags.get("kamra_agent_call") else "Desk")
	return night_audit_pack(audit)


def stuck_business_date(property: str) -> dict | None:
	"""A Completed (or Warnings) run exists for the *current* business date —
	the roll did not stick after a successful audit. Returns the run, or None."""
	from kamra.business_date import get_business_date
	bd = get_business_date(property)
	row = frappe.db.get_value(
		"Night Audit Run",
		{"property": property, "business_date": bd, "status": ("!=", "Draft")},
		["name", "status", "business_date", "run_trigger"], as_dict=True)
	if not row:
		return None
	return {
		"audit": row.name, "status": row.status,
		"business_date": _iso(row.business_date),
		"run_trigger": row.run_trigger,
	}


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Hotel Admin", "Night Auditor", "Kamra Agent")
def recover_stuck_business_date(property: str):
	"""Advance the business date when a completed audit exists for the
	current date but the roll did not stick. Never re-posts room nights."""
	from kamra.crs import assert_property_access
	from kamra.business_date import advance_business_date, get_business_date
	assert_property_access(property)
	stuck = stuck_business_date(property)
	if not stuck:
		frappe.throw(_("The business date is not stuck — no completed audit "
		               "for today's open date."))
	bd = get_business_date(property)
	new_bd = advance_business_date(property, bd)
	from kamra.savings import log_action
	log_action(
		"night_audit_recover_bd", "Night Audit Run", stuck["audit"], property,
		rationale=f"Recovered stuck business date {bd} → {new_bd} "
		          f"(audit {stuck['audit']} already completed)",
		channel="MCP" if frappe.flags.get("kamra_agent_call") else "Desk",
		after_snapshot={"from": bd, "to": new_bd, "audit": stuck["audit"]})
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists recovery before returning
	return {"ok": True, "audit": stuck["audit"], "business_date": bd,
	        "next_business_date": new_bd}


@frappe.whitelist()
@require_roles(*AUDIT_ROLES)
def night_audit_history(property: str, limit: int = 20):
	"""Recent Night Audit Runs of a property, newest first, with whether
	each has a saved audit pack."""
	from kamra.crs import assert_property_access
	assert_property_access(property)
	limit = max(1, min(cint(limit) or 20, 100))
	rows = frappe.db.sql(
		"""
		SELECT name, business_date, status, room_charges_posted, amount_posted,
		       no_shows_flagged, late_arrivals_held, folios_opened, run_trigger,
		       run_by, exceptions, creation,
		       (IFNULL(report_pack, '') != '') AS has_pack
		FROM `tabNight Audit Run`
		WHERE property = %(p)s AND status != 'Draft'
		ORDER BY business_date DESC, creation DESC
		LIMIT %(n)s
		""", {"p": property, "n": limit}, as_dict=True)
	for r in rows:
		r["business_date"] = _iso(r.business_date)
		r["creation"] = _iso(r.creation)
		r["has_pack"] = bool(cint(r.has_pack))
	return rows


# --- run log (scheduled and manual) -------------------------------------------

def record_run(property: str, trigger: str, fn):
	"""Run one night audit attempt (`fn`) and write a Night Audit Log row:
	Closed, Held, Skipped or Failed, with when, who and why. `fn` returning
	None means there was nothing to do, and nothing is logged. A failure is
	rolled back, logged, alerted to Hotel Admin (scheduled runs) and raised."""
	from kamra.business_date import get_business_date
	started = now_datetime()
	frappe.db.savepoint("kamra_na_run")
	try:
		out = fn()
	except Exception as e:
		frappe.db.rollback(save_point="kamra_na_run")
		refused = trigger == "Manual" and isinstance(e, frappe.ValidationError)
		msg = frappe.utils.strip_html(str(e))[:1000] or type(e).__name__
		_write_log(property, trigger, get_business_date(property),
		           "Skipped" if refused else "Failed", msg, started)
		if not refused and trigger == "Scheduled":
			name = frappe.db.get_value("Property", property, "property_name") or property
			alert_staff(property, ("Hotel Admin",), f"Night audit failed - {name}",
			            f"{name}: the scheduled night audit failed: {msg}")
		frappe.db.commit()  # nosemgrep: frappe-manual-commit -- the failure log must survive the caller's rollback
		raise
	if out is None:
		return None
	if out.get("held"):
		status, msg = "Held", out.get("message")
	elif out.get("already_ran"):
		status, msg = "Skipped", f"Already closed (audit {out.get('audit')})"
	elif out.get("skipped"):
		status, msg = "Skipped", out.get("message")
	else:
		status = "Closed"
		msg = (f"Posted {out.get('room_charges_posted', 0)} room nights, flagged "
		       f"{out.get('no_shows_flagged', 0)} no-shows; business date is now "
		       f"{out.get('next_business_date')}")
	_write_log(property, trigger, out.get("business_date") or get_business_date(property),
	           status, msg, started, out.get("audit"))
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the run log with the run
	return out


def _write_log(property, trigger, business_date, status, message, started, audit=None):
	frappe.get_doc({
		"doctype": "Night Audit Log", "property": property,
		"business_date": business_date, "status": status, "run_trigger": trigger,
		"user": frappe.session.user, "started_at": started,
		"finished_at": now_datetime(), "message": message,
		"audit": audit if audit and frappe.db.exists("Night Audit Run", audit) else None,
	}).insert(ignore_permissions=True)


@frappe.whitelist()
@require_roles("Finance", "Hotel Admin", "Night Auditor")
def night_audit_schedule(property: str):
	"""The automatic night audit at a glance: on or off, the next run on the
	property clock (None = manual only), the business date and the last 30
	runs, scheduled and manual, from the Night Audit Log."""
	from kamra.business_date import get_business_date
	from kamra.crs import assert_property_access
	from kamra.folio import audit_clock
	assert_property_access(property)
	bd = get_business_date(property)
	now = audit_clock(property)
	runs = frappe.get_all(
		"Night Audit Log", filters={"property": property},
		fields=["business_date", "status", "run_trigger", "user", "started_at",
		        "finished_at", "message", "audit"],
		order_by="creation desc", limit=30)
	for r in runs:
		for k in ("business_date", "started_at", "finished_at"):
			r[k] = _iso(r[k])
	return {
		"auto": _setting(property, "night_audit_auto"),
		"time": _setting(property, "night_audit_time"),
		"grace_minutes": _setting(property, "night_audit_grace_minutes"),
		"timezone": frappe.db.get_value("Property", property, "timezone")
		            or frappe.utils.get_system_timezone(),
		"business_date": bd, "now": str(now.replace(microsecond=0)),
		"next_run": next_auto_run(property, bd, now), "runs": runs,
	}


def next_auto_run(property: str, bd, now) -> str | None:
	"""When the scheduler will next try to close the day, on the property
	clock `now`; None when the automatic audit is off (manual only)."""
	from datetime import timedelta

	from kamra.folio import audit_due_at, scheduled_attempt_made
	if not _setting(property, "night_audit_auto"):
		return None
	due = audit_due_at(property, now.date())
	if now >= due:
		if getdate(bd) >= now.date() or scheduled_attempt_made(property, bd, now, due):
			due += timedelta(days=1)
		else:  # due now: the next 15 minute tick
			due = (now + timedelta(minutes=15 - now.minute % 15)).replace(second=0, microsecond=0)
	return str(due)


# --- scheduled hold ------------------------------------------------------------

def alert_staff(property: str, roles: tuple[str, ...], subject: str, body: str) -> int:
	"""In-app notification (the bell) plus email to every enabled user holding
	one of `roles`. WhatsApp is deliberately not used here. Best effort: one
	recipient failing never stops the rest. Returns the recipient count."""
	users = set(frappe.get_all("Has Role", filters={
		"role": ("in", list(roles)), "parenttype": "User"}, pluck="parent"))
	users = frappe.get_all("User", filters={
		"name": ("in", list(users) or [""]), "enabled": 1,
		"user_type": "System User"}, fields=["name", "email"])
	for u in users:
		try:
			frappe.get_doc({"doctype": "Notification Log", "for_user": u.name,
			                "type": "Alert", "subject": subject,
			                "email_content": body,
			                "document_type": "Property", "document_name": property,
			                }).insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(title=f"Night audit alert (in-app) failed: {u.name}")
		if u.email:
			try:
				frappe.sendmail(recipients=[u.email], subject=subject,
				                message=body, delayed=True)
			except Exception:
				frappe.log_error(title=f"Night audit alert (email) failed: {u.name}")
	return len(users)


def hold_and_alert(property: str, bd: str, blockers: list[dict]) -> dict:
	"""Scheduled run on "Hold and alert": leave the business date, write an
	Activity log row and message Hotel Admin and Finance."""
	from kamra.savings import log_action
	summary = "; ".join(f"{c['title']}: {c['count']}" for c in blockers)
	msg = (f"Night audit for {bd} was held - {summary}. The business date was "
	       f"not rolled. Resolve or acknowledge the checks and run the audit "
	       f"from End of Day.")
	log_action("night_audit_held", "Property", property, property,
	           rationale=msg, agent_name="Night Audit", autonomy="Full",
	           channel="API",
	           after_snapshot={"business_date": bd,
	                           "blockers": [{"key": c["key"], "count": c["count"]}
	                                        for c in blockers]})
	try:
		name = frappe.db.get_value("Property", property, "property_name") or property
		alert_staff(property, ("Hotel Admin", "Finance"),
		            f"Night audit held - {name}", f"{name}: {msg}")
	except Exception:
		frappe.log_error(title=f"Night audit hold alert failed: {property}")
	return {"held": True, "business_date": bd,
	        "blockers": [{"key": c["key"], "title": c["title"],
	                      "count": c["count"]} for c in blockers],
	        "message": msg}


# --- the audit pack ------------------------------------------------------------

def _section(pack: dict, key: str, fn):
	try:
		pack[key] = fn()
	except Exception as e:
		pack.setdefault("errors", {})[key] = str(e)[:300]
		frappe.log_error(title=f"Night audit pack section failed: {key}")


def _in_house(property: str, bd: str) -> list[dict]:
	from kamra.folio import locked_night
	rows = frappe.get_all(
		"Reservation",
		filters={"property": property, "status": "Checked In",
		         "check_in_date": ("<=", bd), "check_out_date": (">", bd)},
		fields=["name"], order_by="room asc", limit_page_length=0)
	out = []
	for r in rows[:MAX_ITEMS]:
		res = frappe.get_doc("Reservation", r.name)
		locked = locked_night(res, bd)
		f = _guest_folio(res.name)
		out.append({
			"reservation": res.name, "guest_name": res.guest_name,
			"room": _room_no(res.room),
			"room_type": (res.room_type or "").split("-")[-1],
			"check_in_date": _iso(res.check_in_date),
			"check_out_date": _iso(res.check_out_date),
			"adults": cint(res.adults), "children": cint(res.children),
			"rate": flt(locked.rate) if locked is not None else None,
			"company": res.company, "folio": f.get("name"),
			"balance": flt(f.get("balance"), 2),
		})
	return out


def _movement(property: str, field: str, bd: str) -> list[dict]:
	rows = frappe.get_all(
		"Reservation",
		filters={"property": property, field: bd,
		         "status": ("not in", ("Waitlist", "Inquiry", "Quoted"))},
		fields=["name", "guest_name", "room", "room_type", "status",
		        "check_in_date", "check_out_date", "source", "channel"],
		order_by="name asc", limit_page_length=MAX_ITEMS)
	return [{
		"reservation": r.name, "guest_name": r.guest_name,
		"room": _room_no(r.room), "room_type": (r.room_type or "").split("-")[-1],
		"status": r.status, "check_in_date": _iso(r.check_in_date),
		"check_out_date": _iso(r.check_out_date),
		"source": r.channel or r.source,
	} for r in rows]


def _cashier_sessions(property: str, bd: str) -> list[dict]:
	rows = frappe.db.sql(
		"""
		SELECT name, user, cashier, business_date, status, terminal,
		       opening_float, system_cash, system_card, system_upi, system_other,
		       paid_outs, drops, petty_cash, expected_cash, counted_cash,
		       variance, opened_at, closed_at, closed_by
		FROM `tabCashier Session`
		WHERE property = %(p)s
		  AND (business_date = %(d)s
		       OR (status = 'Open' AND (business_date <= %(d)s
		                                OR business_date IS NULL)))
		ORDER BY opened_at
		""", {"p": property, "d": bd}, as_dict=True)
	out = []
	for r in rows:
		closed = r.status == "Closed"
		out.append({
			"session": r.name, "user": r.user,
			"user_name": frappe.db.get_value("User", r.user, "full_name") or r.user,
			"cashier_id": frappe.db.get_value("Cashier", r.cashier, "cashier_id"),
			"business_date": _iso(r.business_date), "status": r.status,
			"terminal": r.terminal, "opening_float": flt(r.opening_float),
			"cash": flt(r.system_cash), "card": flt(r.system_card),
			"upi": flt(r.system_upi), "other": flt(r.system_other),
			"paid_outs": flt(r.paid_outs), "drops": flt(r.drops),
			"petty_cash": flt(r.petty_cash),
			"expected_cash": flt(r.expected_cash),
			"counted_cash": flt(r.counted_cash) if closed else None,
			"variance": flt(r.variance) if closed else None,
			"opened_at": _iso(r.opened_at), "closed_at": _iso(r.closed_at),
		})
	return out


def build_pack(property: str, bd: str, *, checks: list[dict],
               acknowledgements: list[dict], summary: dict,
               no_shows: list[dict], held_late: list[dict]) -> dict:
	"""The audit pack saved on the Night Audit Run: what the night auditor
	prints. Built after the night's postings, before the date rolls. A
	section that fails is left out and named under `errors`; the audit
	itself never fails because of the pack."""
	from kamra import ledger, reports
	prop = frappe.db.get_value(
		"Property", property, ["property_name", "currency", "legal_name",
		                       "city"], as_dict=True) or {}
	acked = {a["key"]: a for a in acknowledgements}
	prechecks = []
	for c in checks:
		row = dict(c)
		row["acknowledgement"] = acked.get(c["key"])
		row["exception"] = c["severity"] == "block" and bool(c["count"])
		prechecks.append(row)
	pack: dict = {
		"version": 1,
		"property": property,
		"property_name": prop.get("property_name") or property,
		"legal_name": prop.get("legal_name"),
		"city": prop.get("city"),
		"currency": prop.get("currency"),
		"business_date": bd,
		"generated_at": str(now_datetime()),
		"generated_by": frappe.session.user,
		"run": summary,
		"prechecks": prechecks,
		"acknowledgements": acknowledgements,
		"no_shows": no_shows,
		"held_late_arrivals": held_late,
	}
	total_rooms = frappe.db.count("Room", {"property": property}) or 0
	_section(pack, "statistics",
	         lambda: {**reports._day_stats(property, bd, total_rooms),
	                  "total_rooms": total_rooms})
	_section(pack, "manager_flash",
	         lambda: _raw(reports.manager_flash)(property, bd))
	_section(pack, "revenue_by_transaction_code",
	         lambda: _raw(ledger.journal_by_transaction_code)(property, bd))
	_section(pack, "ledger_balances",
	         lambda: _raw(ledger.ledger_balances)(property, bd))
	_section(pack, "in_house", lambda: _in_house(property, bd))
	_section(pack, "departures", lambda: _movement(property, "check_out_date", bd))
	_section(pack, "arrivals", lambda: _movement(property, "check_in_date", bd))
	_section(pack, "high_balance", lambda: check_high_balance(property))
	_section(pack, "credit_limit", lambda: check_credit_limit(property))
	_section(pack, "overdue_ar", lambda: check_overdue_ar(property))
	_section(pack, "pos_room_postings", lambda: check_pos_room_postings(property, bd))
	_section(pack, "rate_variance", lambda: check_rate_variance(property, bd))
	_section(pack, "cashier_sessions", lambda: _cashier_sessions(property, bd))
	_section(pack, "journal", lambda: journal_by_cashier(property, bd))
	_section(pack, "deposit_ledger", lambda: _deposit_ledger(property, bd))
	_section(pack, "city_ledger",
	         lambda: _raw(ledger.city_ledger_aging)(property))
	_section(pack, "cancellations", lambda: _cancellations(property, bd))
	pack["notes"] = summary.get("notes")
	pack["reports"] = [{"key": k, "title": t} for k, t in REPORTS]
	return pack


# The final reports the End of Day prints, in order. Each reads its section
# of the saved pack, so history shows exactly what was printed.
REPORTS = (
	("manager_flash", "Manager's flash"),
	("journal", "Journal by cashier and transaction code"),
	("cashier_summary", "Cashier summary"),
	("guest_ledger", "Guest ledger detail"),
	("city_ledger", "City ledger / AR summary"),
	("deposit_ledger", "Deposit ledger balance"),
	("trial_balance", "Trial balance"),
	("occupancy", "Occupancy & revenue"),
	("no_shows", "No-shows and cancellations"),
	("rate_variance", "Rate variance"),
	("exceptions", "Pre-checks and exceptions"),
)


def journal_by_cashier(property: str, bd: str) -> dict:
	"""Every folio ledger posting of the business date - the night
	auditor's key report: time, room, guest, transaction code,
	description, debit, credit and the cashier who posted it, grouped by
	cashier and transaction code with subtotals."""
	rows = frappe.db.sql(
		"""
		SELECT fle.name, fle.business_date, fle.posted_at, fle.folio,
		       fle.ledger, fle.transaction_code, fle.description,
		       fle.debit, fle.credit, fle.cashier, fle.posted_by,
		       f.guest_name, r.room, tc.description AS code_description,
		       c.cashier_id
		FROM `tabFolio Ledger Entry` fle
		LEFT JOIN `tabFolio` f ON f.name = fle.folio
		LEFT JOIN `tabReservation` r ON r.name = f.reservation
		LEFT JOIN `tabTransaction Code` tc ON tc.name = fle.transaction_code
		LEFT JOIN `tabCashier` c ON c.name = fle.cashier
		WHERE fle.property = %(p)s AND fle.business_date = %(d)s
		ORDER BY COALESCE(c.cashier_id, fle.posted_by), fle.transaction_code,
		         fle.posted_at
		""", {"p": property, "d": bd}, as_dict=True)
	lines = []
	groups: dict = {}
	for r in rows[:MAX_ITEMS * 4]:
		cashier = r.cashier_id or r.posted_by or "-"
		line = {
			"date": _iso(r.business_date),
			"time": str(r.posted_at)[11:16] if r.posted_at else None,
			"room": _room_no(r.room), "guest_name": r.guest_name,
			"folio": r.folio, "ledger": r.ledger,
			"transaction_code": r.transaction_code,
			"code_description": r.code_description,
			"description": r.description,
			"debit": flt(r.debit, 2), "credit": flt(r.credit, 2),
			"cashier": cashier,
		}
		lines.append(line)
		g = groups.setdefault((cashier, r.transaction_code or "-"), {
			"cashier": cashier, "transaction_code": r.transaction_code or "-",
			"description": r.code_description or "", "entries": 0,
			"debit": 0.0, "credit": 0.0})
		g["entries"] += 1
		g["debit"] = round(g["debit"] + line["debit"], 2)
		g["credit"] = round(g["credit"] + line["credit"], 2)
	return {
		"business_date": bd, "lines": lines,
		"subtotals": list(groups.values()),
		"total_debit": round(sum(x["debit"] for x in lines), 2),
		"total_credit": round(sum(x["credit"] for x in lines), 2),
	}


def _deposit_ledger(property: str, bd: str) -> dict:
	rows = frappe.db.sql(
		"""
		SELECT fle.folio, SUM(fle.debit) AS debit, SUM(fle.credit) AS credit,
		       f.guest_name, f.reservation, r.room, r.status, r.check_in_date
		FROM `tabFolio Ledger Entry` fle
		LEFT JOIN `tabFolio` f ON f.name = fle.folio
		LEFT JOIN `tabReservation` r ON r.name = f.reservation
		WHERE fle.property = %(p)s AND fle.ledger = 'Deposit'
		  AND fle.business_date <= %(d)s
		GROUP BY fle.folio
		HAVING ABS(SUM(fle.debit) - SUM(fle.credit)) > 0.009
		""", {"p": property, "d": bd}, as_dict=True)
	items = [{
		"folio": r.folio, "reservation": r.reservation,
		"guest_name": r.guest_name, "room": _room_no(r.room),
		"status": r.status, "check_in_date": _iso(r.check_in_date),
		"balance": round(flt(r.debit) - flt(r.credit), 2),
	} for r in rows]
	return {"items": items,
	        "total": round(sum(i["balance"] for i in items), 2)}


def _cancellations(property: str, bd: str) -> list[dict]:
	rows = frappe.db.sql(
		"""
		SELECT name, guest_name, room_type, check_in_date, check_out_date,
		       cancellation_number, cancellation_fee, cancellation_reason,
		       cancelled_on, source, channel
		FROM `tabReservation`
		WHERE property = %(p)s AND status = 'Cancelled'
		  AND DATE(cancelled_on) = %(d)s
		ORDER BY cancelled_on
		""", {"p": property, "d": bd}, as_dict=True)
	return [{
		"reservation": r.name, "guest_name": r.guest_name,
		"room_type": (r.room_type or "").split("-")[-1],
		"check_in_date": _iso(r.check_in_date),
		"check_out_date": _iso(r.check_out_date),
		"cancellation_number": r.cancellation_number,
		"fee": flt(r.cancellation_fee), "reason": r.cancellation_reason,
		"source": r.channel or r.source, "cancelled_on": _iso(r.cancelled_on),
	} for r in rows]


# --- End of Day wizard ---------------------------------------------------------

def _lost_create_race(e: Exception) -> bool:
	"""True when an insert failed because a concurrent request created the
	same row first: a duplicate key, or MariaDB's snapshot-isolation error
	1020 (raised by Frappe as QueryDeadlockError)."""
	return isinstance(e, (frappe.DuplicateEntryError, frappe.QueryDeadlockError)) \
		or bool(getattr(frappe.db, "is_duplicate_entry", None)
		        and frappe.db.is_duplicate_entry(e))


def _draft(property: str, bd: str, create: bool = False) -> str | None:
	name = frappe.db.get_value(
		"Night Audit Run",
		{"property": property, "business_date": bd, "status": "Draft"}, "name")
	if name or not create:
		return name
	doc = frappe.get_doc({
		"doctype": "Night Audit Run", "property": property,
		"business_date": bd, "status": "Draft", "eod_step": 1,
		"run_trigger": "Manual", "run_by": frappe.session.user,
		"log": "End of Day started.",
	})
	try:
		doc.insert(ignore_permissions=True)
	except Exception as e:
		# The run's name is AUDIT-<date>-<property>: two first loads of the
		# wizard at once (a double render, two tabs) both try to create it.
		# The loser fails on the key - MariaDB's snapshot isolation reports
		# that as 1020 "Record has changed since last read" - and the draft
		# it wanted now exists. Nothing was written before this point, so
		# drop the transaction (a fresh one sees the winner's row) and use
		# the row the other request made.
		if not _lost_create_race(e):
			raise
		frappe.db.rollback()
		name = frappe.db.get_value(
			"Night Audit Run",
			{"property": property, "business_date": bd, "status": "Draft"},
			"name")
		if not name:
			raise
		return name
	return doc.name


def _step_rows(checks: list[dict], state: dict, acks: list[dict],
               ran: bool) -> list[dict]:
	by_key = {c["key"]: c for c in checks}
	acked = {a["key"] for a in acks}
	out = []
	for i, (key, title, keys) in enumerate(STEPS, start=1):
		mine = [by_key[k] for k in keys if k in by_key]
		blocking = [c for c in mine if c["severity"] == "block" and c["count"]
		            and c["key"] not in acked]
		if ran and i <= RUN_STEP:
			status = "done"
		elif blocking:
			status = "blocked"
		else:
			status = state.get(key) or "pending"
		out.append({
			"index": i, "key": key, "title": title, "checks": list(keys),
			"status": status,
			"count": sum(c["count"] for c in mine if c["severity"] != "info"),
			"blocking": [c["key"] for c in blocking],
		})
	return out


def _eod_state(property: str, audit: str | None = None) -> dict:
	from kamra.business_date import get_business_date
	from kamra.no_show import property_now
	prop = frappe.db.get_value(
		"Property", property,
		["property_name", "currency", "require_cashier_pin", "timezone"],
		as_dict=True) or {}
	# stuck_date: a completed audit exists for the *current* open BD — the
	# roll did not stick. Surface it so the wizard never looks "fully closed"
	# while the property is still on yesterday.
	stuck = stuck_business_date(property)
	base = {
		"property": property,
		"property_name": prop.get("property_name") or property,
		"currency": prop.get("currency"),
		"server_date": str(getdate()),
		"server_time": str(now_datetime())[:16],
		"property_now": str(property_now(property))[:16],
		"require_cashier_pin": cint(prop.get("require_cashier_pin")),
		# hook: a property that turns on blind cashier counts hides the
		# expected cash from whoever counts the drawer
		"blind_count": 0,
		"high_balance_threshold": flt(_setting(property, "na_high_balance_threshold")),
		"auto_audit_with_blockers": _setting(property, "na_auto_audit_with_blockers"),
		"reports": [{"key": k, "title": t} for k, t in REPORTS],
		"stuck_date": stuck,
		"open_business_date": get_business_date(property),
	}
	if audit:
		# a finished run: the wizard resumes at its reports
		run = frappe.db.get_value(
			"Night Audit Run", audit,
			["name", "property", "business_date", "status", "eod_step",
			 "eod_state", "auditor_notes", "acknowledgements", "report_pack"],
			as_dict=True)
		if not run or run.property != property:
			frappe.throw(_("Night audit run {0} not found.").format(audit),
			             frappe.DoesNotExistError)
		if run.status != "Draft":
			pack = _loads(run.report_pack, {})
			state = _loads(run.eod_state, {})
			acks = _loads(run.acknowledgements, [])
			checks = pack.get("prechecks") or []
			return {**base, "business_date": _iso(run.business_date),
			        "audit": run.name, "ran": True, "status": run.status,
			        "current_step": max(cint(run.eod_step), RUN_STEP + 1),
			        "notes": run.auditor_notes, "acknowledgements": acks,
			        "checks": checks, "has_pack": bool(pack),
			        "steps": _step_rows(checks, state, acks, True),
			        "sessions": pack.get("cashier_sessions") or []}
	bd = get_business_date(property)
	done = frappe.db.get_value(
		"Night Audit Run", {"property": property, "business_date": bd,
		                    "status": ("!=", "Draft")}, "name")
	if done:
		return _eod_state(property, done)
	draft = _draft(property, bd, create=True)
	run = frappe.db.get_value(
		"Night Audit Run", draft,
		["eod_step", "eod_state", "auditor_notes", "acknowledgements"],
		as_dict=True)
	checks = run_checks(property, bd)
	state = _loads(run.eod_state, {})
	acks = _loads(run.acknowledgements, [])
	return {**base, "business_date": bd, "audit": draft, "ran": False,
	        "status": "Draft", "current_step": cint(run.eod_step) or 1,
	        "notes": run.auditor_notes, "acknowledgements": acks,
	        "checks": checks,
	        "blockers": [c["key"] for c in open_blockers(checks)
	                     if c["key"] not in {a["key"] for a in acks}],
	        "steps": _step_rows(checks, state, acks, False),
	        "sessions": _cashier_sessions(property, bd)}


@frappe.whitelist(methods=["POST"])
@require_roles(*AUDIT_ROLES)
def eod_session(property: str, audit: str | None = None):
	"""Open (or resume) End of Day for the property's current business date:
	the draft run that keeps the wizard's progress, every pre-check and
	the step list with each step's status (pending, done, blocked). With
	`audit`, a finished run is shown at its final reports."""
	from kamra.crs import assert_property_access
	assert_property_access(property)
	if not frappe.db.exists("Property", property):
		frappe.throw(_("Unknown property."))
	return _eod_state(property, audit)


@frappe.whitelist(methods=["POST"])
@require_roles(*AUDIT_ROLES)
def eod_progress(property: str, step: int | None = None,
                 status: str | None = None, key: str | None = None,
                 notes: str | None = None):
	"""Save the wizard's place: the current step (1-based), a step's status
	(`key` + `status`: done | skipped | pending) and the manager notes.
	A blocked step cannot be marked done - acknowledge it first."""
	from kamra.business_date import get_business_date
	from kamra.crs import assert_property_access
	assert_property_access(property)
	draft = _draft(property, get_business_date(property), create=True)
	doc = frappe.get_doc("Night Audit Run", draft)
	state = _loads(doc.eod_state, {})
	if key:
		if key not in STEP_KEYS:
			frappe.throw(_("Unknown End of Day step: {0}").format(key))
		if status not in ("done", "skipped", "pending"):
			frappe.throw(_("Step status must be done, skipped or pending."))
		if status in ("done", "skipped"):
			checks = dict((k, c) for k, _t, c in STEPS)[key]
			acked = {a["key"] for a in _loads(doc.acknowledgements, [])}
			bd = get_business_date(property)
			live = {c["key"]: c for c in run_checks(property, bd)} if checks else {}
			blocking = [live[k] for k in checks if k in live
			            and live[k]["severity"] == "block" and live[k]["count"]
			            and k not in acked]
			if blocking:
				frappe.throw(_("{0} still has open items - resolve them or "
				               "acknowledge with a reason.").format(
					blocking[0]["title"]))
		state[key] = status
		doc.eod_state = json.dumps(state)
	if step is not None:
		doc.eod_step = max(1, min(cint(step), RUN_STEP))
	if notes is not None:
		doc.auditor_notes = (notes or "").strip()[:5000] or None
	doc.save(ignore_permissions=True)
	return {"audit": doc.name, "current_step": doc.eod_step, "state": state,
	        "notes": doc.auditor_notes}


@frappe.whitelist(methods=["POST"])
@require_roles(*AUDIT_ROLES)
def eod_acknowledge(property: str, key: str, reason: str):
	"""Acknowledge a blocking check with a reason so End of Day can go on.
	Who and when are recorded on the run and in the Activity log."""
	from kamra.business_date import get_business_date
	from kamra.crs import assert_property_access
	from kamra.savings import log_action
	assert_property_access(property)
	reason = (reason or "").strip()
	if len(reason) < 3:
		frappe.throw(_("Give a reason for acknowledging this check."))
	bd = get_business_date(property)
	check = next((c for c in run_checks(property, bd) if c["key"] == key), None)
	if not check:
		frappe.throw(_("Unknown check: {0}").format(key))
	if check["severity"] != "block" or not check["count"]:
		frappe.throw(_("{0} is not blocking the audit - nothing to "
		               "acknowledge.").format(check["title"]))
	draft = _draft(property, bd, create=True)
	doc = frappe.get_doc("Night Audit Run", draft)
	acks = [a for a in _loads(doc.acknowledgements, []) if a["key"] != key]
	row = acknowledgement_rows([check], [key], reason)[0]
	acks.append(row)
	doc.acknowledgements = json.dumps(acks)
	doc.save(ignore_permissions=True)
	log_action("night_audit_acknowledged", "Night Audit Run", doc.name, property,
	           rationale=f"{check['title']} ({check['count']}) acknowledged "
	                     f"for {bd}: {reason}",
	           channel="MCP" if frappe.flags.get("kamra_agent_call") else "Desk",
	           after_snapshot=row)
	return {"audit": doc.name, "acknowledgement": row, "acknowledgements": acks}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Night Auditor", "Hotel Admin", "Kamra Agent")
def eod_mark_no_show(reservation: str, reason: str | None = None):
	"""End of Day: mark an arrival that did not come a No Show now, with the
	property's no-show fee policy applied exactly as the audit applies it
	(fee posted on the business date, or waived for an OTA booking)."""
	from kamra import no_show
	from kamra.business_date import get_business_date
	from kamra.folio import apply_no_show
	from kamra.savings import log_action
	res = frappe.get_doc("Reservation", reservation)
	bd = get_business_date(res.property)
	if res.status != "Confirmed":
		frappe.throw(_("Only a Confirmed arrival can be marked no-show "
		               "(this one is {0}).").format(res.status))
	if getdate(res.check_in_date) > getdate(bd):
		frappe.throw(_("This arrival is due on {0}, after the business date "
		               "{1}.").format(res.check_in_date, bd))
	pol = no_show.policy(res.property)
	ns = apply_no_show(res, pol, no_show.fee_decision(res, pol), bd)
	log_action("no_show", "Reservation", res.name, res.property,
	           rationale=f"{res.name} ({res.guest_name}) marked no-show at End "
	                     f"of Day: {ns['outcome']}"
	                     + (f" - {reason.strip()}" if (reason or "").strip() else ""),
	           channel="MCP" if frappe.flags.get("kamra_agent_call") else "Desk",
	           after_snapshot=ns)
	return ns


@frappe.whitelist()
@require_roles(*AUDIT_ROLES)
def eod_overview():
	"""Manage End of Day: one row per property the user can access - the
	business date, the property's local time, arrivals and departures
	pending, open cashiers and POS bills, and the number of blockers."""
	from kamra.authz import restricted_properties
	from kamra.business_date import get_business_date
	from kamra.no_show import property_now
	allowed = restricted_properties()
	props = frappe.get_all("Property", filters={"disabled": 0},
	                       fields=["name", "property_name"], order_by="property_name")
	out = []
	for p in props:
		if allowed is not None and p.name not in allowed:
			continue
		bd = get_business_date(p.name)
		now = property_now(p.name)
		tills = check_open_tills(p.name, bd)
		pos = check_open_pos_bills(p.name, bd)
		deps = check_departures_due(p.name, bd)
		arrivals = frappe.db.count("Reservation", {
			"property": p.name, "status": "Confirmed",
			"check_in_date": ("<=", bd)})
		blockers = open_blockers([tills, pos, deps])
		draft = frappe.db.get_value(
			"Night Audit Run", {"property": p.name, "business_date": bd,
			                    "status": "Draft"}, ["name", "eod_step"],
			as_dict=True)
		last = frappe.db.get_value(
			"Night Audit Run", {"property": p.name, "status": ("!=", "Draft")},
			["name", "business_date", "status", "report_pack", "run_trigger"],
			as_dict=True, order_by="business_date desc")
		stuck = stuck_business_date(p.name)
		held = _last_hold(p.name)
		out.append({
			"property": p.name, "property_name": p.property_name or p.name,
			"business_date": bd, "property_now": str(now)[:16],
			"next_auto_run": next_auto_run(p.name, bd, now),
			"arrivals_pending": arrivals,
			"departures_pending": deps["count"],
			"open_cashiers": tills["count"],
			"open_pos_bills": pos["count"],
			"blockers": len(blockers),
			"blocker_keys": [c["key"] for c in blockers],
			"draft_step": cint(draft.eod_step) if draft else None,
			"held": held,
			"stuck_date": stuck,
			"last_run": {"audit": last.name,
			             "business_date": _iso(last.business_date),
			             "status": last.status,
			             "run_trigger": last.run_trigger,
			             "has_pack": bool(last.report_pack)} if last else None,
		})
	return out
