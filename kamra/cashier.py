"""Opera-style cashier till: open/close sessions, float, paid-outs, drops,
and a unified cash trail for front-office + POS.

Money actions elsewhere call record_cashier_txn(...) after resolving the
caller's open session. Agents bypass the session gate (same rule as PIN)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import now_datetime

from kamra.authz import require_roles
from kamra.business_date import ensure_business_date, get_business_date
from kamra.settings import get_setting

CASH_MODES = ("Cash",)
CARD_MODES = ("Card",)
UPI_MODES = ("UPI",)


def _agent_bypass() -> bool:
	if getattr(frappe.flags, "kamra_agent_call", False) or \
	   getattr(frappe.flags, "kamra_gate_bypass", False):
		return True
	if "Kamra Agent" in frappe.get_roles():
		return True
	if frappe.session.user == "Administrator":
		return True
	return False


def _cashier_for_user(property: str, user: str | None = None) -> str | None:
	user = user or frappe.session.user
	name = frappe.db.get_value(
		"Cashier",
		{"property": property, "user": user, "disabled": 0},
		"name",
	)
	return name


def ensure_cashier(property: str, user: str | None = None) -> str:
	"""Auto-provision a Cashier ID for the user on first till open."""
	user = user or frappe.session.user
	existing = _cashier_for_user(property, user)
	if existing:
		return existing
	# Stable short id from username
	base = (user.split("@")[0] or "csh")[:12].upper().replace(".", "")
	cid = f"{base}-{property[:8]}".upper()
	n = 1
	while frappe.db.exists("Cashier", {"cashier_id": cid}):
		n += 1
		cid = f"{base}{n}-{property[:8]}".upper()
	doc = frappe.get_doc({
		"doctype": "Cashier",
		"cashier_id": cid,
		"user": user,
		"property": property,
		"is_floating": 0,
		"max_cash_refund": get_setting(property, "max_cash_refund"),
	})
	doc.insert(ignore_permissions=True)
	return doc.name


def _open_session_names(property: str, user: str) -> list[str]:
	"""The user's open tills here, newest first. Usually one; a person
	covering two stations holds one per terminal."""
	return frappe.get_all(
		"Cashier Session",
		filters={"property": property, "user": user, "status": "Open"},
		pluck="name", order_by="opened_at desc, creation desc")


def _pick_session(names: list[str], outlet: str | None = None) -> str | None:
	"""Of several open tills, the one serving `outlet` (a POS bill goes to the
	till of its outlet), else the one opened last."""
	if outlet and len(names) > 1:
		for n in names:
			if frappe.db.get_value("Cashier Session", n, "outlet") == outlet:
				return n
	return names[0] if names else None


# who may open their own till (open_session); admins always may
TILL_OPENERS = ("Front Desk", "Finance", "Kamra Agent")


def tills_required(property: str | None) -> bool:
	"""Does this property take money through cashier tills? On by default.
	A small place with no cash drawer turns it off (Settings > Finance):
	payments are then recorded without a till, and the till screens
	(paid-outs, drops, petty cash, exchange) still need one."""
	return bool(get_setting(property, "use_cashier_tills"))


def can_open_till() -> bool:
	from kamra.authz import ADMIN
	return bool((set(TILL_OPENERS) | set(ADMIN)) & set(frappe.get_roles()))


def till_state(property: str) -> dict[str, Any]:
	"""What a money screen needs to know about the caller's till: is one
	needed, is it open, and can this user open it here (open_session)."""
	required = tills_required(property)
	session = None if _agent_bypass() else _pick_session(
		_open_session_names(property, frappe.session.user))
	return {
		"property": property,
		"required": required,
		"open": bool(session) or _agent_bypass() or not required,
		"session": session,
		"can_open": can_open_till(),
		"who_can_open": ["Front Desk", "Finance", "Hotel Admin"],
		"business_date": str(get_business_date(property) or ""),
	}


def require_open_session(property: str, outlet: str | None = None,
                         till_only: bool = False) -> str | None:
	"""Return open session name, or None when agents bypass. Throws otherwise.

	`outlet`: which till to take when the user holds several.
	A property that does not use tills (use_cashier_tills off) records
	payments without one: None comes back instead of a refusal, unless
	`till_only` (a paid-out, drop, petty cash or exchange, which only make
	sense against a till)."""
	if _agent_bypass():
		# Prefer an open session if one exists; else None (txn still recorded
		# without session when agents act).
		sess = frappe.db.get_value(
			"Cashier Session",
			{"property": property, "status": "Open"},
			"name",
			order_by="opened_at desc",
		)
		return sess
	sess = _pick_session(_open_session_names(property, frappe.session.user), outlet)
	if not sess:
		if not till_only and not tills_required(property):
			return None
		frappe.throw(
			"NO_OPEN_SESSION: open your till under Finance → Cashier first.",
		)
	return sess


_TOTAL_FIELDS = ("system_cash", "system_card", "system_upi", "system_other",
                 "paid_outs", "drops", "petty_cash", "expected_cash")


def _recompute_session_totals(session: str, persist: bool = True) -> dict[str, float]:
	"""Re-add the session's transactions into its stored totals. The row is
	written only when a total actually moved: a screen that merely reads the
	till (current_session, on every load) must not write, or two loads at
	once race on the same row (MariaDB 1020 "Record has changed")."""
	rows = frappe.db.sql(
		"""
		SELECT kind, mode, COALESCE(SUM(amount), 0) AS total
		FROM `tabCashier Transaction`
		WHERE session = %s
		GROUP BY kind, mode
		""",
		session, as_dict=True,
	)
	cash = card = upi = other = paid_outs = drops = petty = 0.0
	for r in rows:
		amt = float(r.total or 0)
		kind = r.kind
		mode = r.mode or "Other"
		if kind == "Paid Out":
			paid_outs += abs(amt)
		elif kind == "Drop":
			drops += abs(amt)
		elif kind == "Petty Cash":
			petty += abs(amt)
		elif kind in ("Payment", "Exchange"):
			if mode in CASH_MODES:
				cash += amt
			elif mode in CARD_MODES:
				card += amt
			elif mode in UPI_MODES:
				upi += amt
			else:
				other += amt
		elif kind == "Refund":
			# refunds reduce the mode bucket (amount stored negative)
			if mode in CASH_MODES:
				cash += amt
			elif mode in CARD_MODES:
				card += amt
			elif mode in UPI_MODES:
				upi += amt
			else:
				other += amt

	sess = frappe.get_doc("Cashier Session", session)
	opening = float(sess.opening_float or 0)
	expected = opening + cash - paid_outs - drops - petty
	fresh = dict(zip(_TOTAL_FIELDS, (cash, card, upi, other, paid_outs, drops,
	                                 petty, expected)))
	if persist and any(abs(float(sess.get(k) or 0) - v) > 0.004
	                   for k, v in fresh.items()):
		sess.update(fresh)
		sess.save(ignore_permissions=True)
	return {
		"cash": cash, "card": card, "upi": upi, "other": other,
		"paid_outs": paid_outs, "drops": drops, "petty_cash": petty,
		"opening_float": opening, "expected_cash": expected,
	}


def record_cashier_txn(
	property: str,
	kind: str,
	mode: str,
	amount: float,
	*,
	folio: str | None = None,
	pos_order: str | None = None,
	reference: str | None = None,
	notes: str | None = None,
	session: str | None = None,
	outlet: str | None = None,
) -> str | None:
	"""Append a Cashier Transaction. Returns session name (or None)."""
	sess = session
	if not outlet and pos_order:
		outlet = frappe.db.get_value("POS Order", pos_order, "outlet")
	if not sess:
		try:
			sess = require_open_session(property, outlet)
		except Exception:
			if _agent_bypass():
				sess = None
			else:
				raise
	if not sess:
		return None
	bd = get_business_date(property)
	frappe.get_doc({
		"doctype": "Cashier Transaction",
		"session": sess,
		"property": property,
		"kind": kind,
		"mode": mode or "Cash",
		"amount": float(amount),
		"business_date": bd,
		"folio": folio,
		"pos_order": pos_order,
		"outlet": outlet or frappe.db.get_value("Cashier Session", sess, "outlet"),
		"reference": (reference or "")[:140] or None,
		"notes": notes,
		"posted_by": frappe.session.user,
		"posted_at": now_datetime(),
	}).insert(ignore_permissions=True)
	_recompute_session_totals(sess)
	return sess


def session_as_dict(name: str, persist: bool = True) -> dict[str, Any]:
	totals = _recompute_session_totals(name, persist=persist)
	doc = frappe.get_doc("Cashier Session", name)
	txns = frappe.get_all(
		"Cashier Transaction",
		filters={"session": name},
		fields=["name", "kind", "mode", "amount", "folio", "pos_order",
		        "reference", "posted_by", "posted_at", "notes"],
		order_by="posted_at desc",
		limit_page_length=200,
	)
	d = doc.as_dict()
	d["totals"] = totals
	d["transactions"] = txns
	d["cashier_id"] = frappe.db.get_value("Cashier", doc.cashier, "cashier_id")
	return d


def _session_view(name: str) -> dict[str, Any]:
	"""session_as_dict for a read-only endpoint. Should a concurrent request
	refresh the same session's totals first (MariaDB snapshot isolation
	raises 1020 on the second write), nothing of ours was written yet: start
	a fresh transaction and answer from it without writing."""
	try:
		return session_as_dict(name)
	except frappe.QueryDeadlockError:
		frappe.db.rollback()
		return session_as_dict(name, persist=False)


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Kamra Agent")
def open_session(property: str, opening_float: float | None = None,
                 terminal: str | None = None, cashier_terminal: str | None = None):
	"""Open the caller's till for the current business date.

	`cashier_terminal` picks a configured till. Without it the session is the
	property's Default till, one per user, exactly as before terminals existed.
	A configured terminal has one open session at a time; one user may hold
	several, one per terminal."""
	ensure_business_date(property)
	user = frappe.session.user
	term = None
	if cashier_terminal:
		term = frappe.db.get_value(
			"Cashier Terminal", cashier_terminal,
			["name", "property", "disabled", "outlet", "default_float", "terminal_name"],
			as_dict=True)
		if not term or term.property != property:
			frappe.throw("That terminal is not at this property.")
		if term.disabled:
			frappe.throw("That terminal is switched off.")
		taken = frappe.db.get_value(
			"Cashier Session", {"cashier_terminal": term.name, "status": "Open"},
			["name", "user"], as_dict=True)
		if taken:
			if taken.user == user:
				return session_as_dict(taken.name)
			frappe.throw(f"{term.terminal_name} is already open under {taken.user}. "
			             "Ask them (or a manager) to close it first.")
	else:
		existing = frappe.db.get_value(
			"Cashier Session",
			{"property": property, "user": user, "status": "Open",
			 "cashier_terminal": ["is", "not set"]},
			"name",
		)
		if existing:
			return session_as_dict(existing)
	cashier = ensure_cashier(property, user)
	bd = get_business_date(property)
	opening = float(opening_float) if opening_float not in (None, "") else \
		float(term.default_float or 0) if term else 0.0
	doc = frappe.get_doc({
		"doctype": "Cashier Session",
		"property": property,
		"cashier": cashier,
		"user": user,
		"business_date": bd,
		"terminal": (term.terminal_name if term else terminal) or "",
		"cashier_terminal": term.name if term else None,
		"outlet": term.outlet if term else None,
		"status": "Open",
		"opening_float": opening,
		"opened_at": now_datetime(),
		"expected_cash": opening,
	})
	doc.insert(ignore_permissions=True)
	return session_as_dict(doc.name)


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Night Auditor", "Kamra Agent")
def current_session(property: str, cashier_terminal: str | None = None):
	"""Caller's open session, or null. With several open, the newest unless
	`cashier_terminal` names one."""
	user = frappe.session.user
	names = _open_session_names(property, user)
	if cashier_terminal:
		names = [n for n in names
		         if frappe.db.get_value("Cashier Session", n, "cashier_terminal") == cashier_terminal]
	name = names[0] if names else None
	if not name and _agent_bypass():
		name = frappe.db.get_value(
			"Cashier Session",
			{"property": property, "status": "Open"},
			"name",
			order_by="opened_at desc",
		)
	if not name:
		return {
			"open": False,
			"business_date": get_business_date(property),
			"cashier": _cashier_for_user(property),
		}
	mine = _open_session_names(property, user)
	return {"open": True, "open_sessions": mine,
	        "open_tills": [{"name": n, "cashier_terminal": t, "terminal": lbl or "Default"}
	                       for n, t, lbl in (
	                           (n, *frappe.db.get_value("Cashier Session", n,
	                                                    ["cashier_terminal", "terminal"]))
	                           for n in mine)],
	        **_session_view(name)}


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Night Auditor", "Kamra Agent")
def my_till(property: str):
	"""Read-only: does taking money here need a till, is the caller's open,
	and may the caller open one (open_session). The check-in, walk-in and
	check-out sheets read it to offer "Open my till" in place."""
	return till_state(property)


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance", "Night Auditor", "Kamra Agent")
def close_session(session: str, counted_cash: float,
                  notes: str | None = None, pin: str | None = None):
	"""Count the drawer and close the till."""
	doc = frappe.get_doc("Cashier Session", session)
	if doc.status != "Open":
		frappe.throw("This session is already closed.")
	if doc.user != frappe.session.user and not (
			set(frappe.get_roles()) & {"Hotel Admin", "System Manager",
			                           "Administrator", "Finance",
			                           "Night Auditor"}):
		frappe.throw("Only the owning cashier (or Finance / the night auditor) can close this till.")
	from kamra.authz import require_cashier_pin
	require_cashier_pin(doc.property, pin)
	totals = _recompute_session_totals(session)
	doc.reload()
	doc.counted_cash = float(counted_cash)
	doc.variance = float(counted_cash) - float(totals["expected_cash"])
	doc.status = "Closed"
	doc.closed_at = now_datetime()
	doc.closed_by = frappe.session.user
	doc.close_notes = (notes or "").strip()[:500] or None
	tol = float(get_setting(doc.property, "till_variance_tolerance") or 0)
	if tol > 0 and abs(doc.variance) > tol:
		# never block a cash count; flag it for a manager instead
		doc.variance_status = "Needs Review"
	doc.save(ignore_permissions=True)

	# Derive a Shift Handover row so ops history stays consistent.
	try:
		_sync_shift_handover(doc)
	except Exception:
		frappe.log_error(title="shift handover sync failed")

	return session_as_dict(doc.name)


def _sync_shift_handover(sess) -> None:
	from frappe.utils import getdate
	shift_date = getdate(sess.business_date)
	# Map time-of-day roughly: Morning / Evening / Night by hour
	hour = (sess.closed_at or now_datetime()).hour
	slot = "Morning" if hour < 14 else ("Evening" if hour < 22 else "Night")
	# Prefer property-scoped uniqueness via filters if autoname collides
	existing = frappe.db.get_value(
		"Shift Handover",
		{"property": sess.property, "shift_date": shift_date, "shift": slot},
		"name",
	)
	payload = {
		"opening_cash": float(sess.opening_float or 0),
		"cash_collected": float(sess.system_cash or 0),
		"payouts": float(sess.paid_outs or 0) + float(sess.petty_cash or 0),
		"closing_cash": float(sess.counted_cash or 0),
		"status": "Closed",
		"handed_over_to": sess.user,
		"handover_notes": (
			f"Auto from cashier session {sess.name}; variance "
			f"{float(sess.variance or 0):,.2f}"
			+ (f"; {sess.close_notes}" if sess.close_notes else "")
		)[:500],
	}
	if existing:
		doc = frappe.get_doc("Shift Handover", existing)
		doc.update(payload)
		doc.save(ignore_permissions=True)
	else:
		frappe.get_doc({
			"doctype": "Shift Handover",
			"property": sess.property,
			"shift": slot,
			"shift_date": shift_date,
			**payload,
		}).insert(ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance", "Kamra Agent")
def post_paid_out(property: str, amount: float, reason: str,
                  payee: str | None = None, pin: str | None = None):
	"""Cash leaving the drawer (vendor / guest paid-out)."""
	if float(amount) <= 0:
		frappe.throw("Amount must be positive.")
	if not (reason or "").strip():
		frappe.throw("A reason is required.")
	from kamra.authz import require_cashier_pin
	require_cashier_pin(property, pin)
	sess = require_open_session(property, till_only=True)
	record_cashier_txn(
		property, "Paid Out", "Cash", -abs(float(amount)),
		reference=(payee or "")[:80] or None,
		notes=reason.strip()[:200],
		session=sess,
	)
	return session_as_dict(sess) if sess else {"ok": True}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance", "Kamra Agent")
def cash_drop(property: str, amount: float, location: str | None = None,
              pin: str | None = None, to_terminal: str | None = None):
	"""Move cash from the till to a drop safe / general cashier.

	`to_terminal` names a Cash Office terminal: the drop is then a pending
	transfer the cash office confirms when the money arrives. Without it the
	drop is just recorded against `location`, as before."""
	if float(amount) <= 0:
		frappe.throw("Amount must be positive.")
	from kamra.authz import require_cashier_pin
	require_cashier_pin(property, pin)
	office = None
	if to_terminal:
		office = frappe.db.get_value("Cashier Terminal", to_terminal,
		                             ["name", "property", "kind", "terminal_name", "disabled"],
		                             as_dict=True)
		if not office or office.property != property or office.disabled:
			frappe.throw("That cash office is not available at this property.")
		if office.kind != "Cash Office":
			frappe.throw(f"{office.terminal_name} is not a cash office.")
	sess = require_open_session(property, till_only=True)
	where = office.terminal_name if office else (location or "safe")
	record_cashier_txn(
		property, "Drop", "Cash", -abs(float(amount)),
		reference=where[:80],
		notes=f"Cash drop to {where}",
		session=sess,
	)
	if office:
		frappe.get_doc({
			"doctype": "Cash Transfer", "property": property, "kind": "Drop",
			"status": "Pending", "amount": abs(float(amount)),
			"business_date": get_business_date(property),
			"from_session": sess,
			"from_terminal": frappe.db.get_value("Cashier Session", sess, "cashier_terminal") if sess else None,
			"to_terminal": office.name, "requested_by": frappe.session.user,
			"requested_at": now_datetime(),
		}).insert(ignore_permissions=True)
	return session_as_dict(sess) if sess else {"ok": True}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance", "Kamra Agent")
def post_petty_cash(property: str, amount: float, payee: str, category: str,
                    reason: str, pin: str | None = None):
	if float(amount) <= 0:
		frappe.throw("Amount must be positive.")
	if not (payee or "").strip() or not (reason or "").strip():
		frappe.throw("Payee and reason are required.")
	from kamra.authz import assert_property_access, require_cashier_pin
	assert_property_access(property)
	require_cashier_pin(property, pin)
	sess = require_open_session(property, till_only=True)
	bd = get_business_date(property)
	voucher = frappe.get_doc({
		"doctype": "Petty Cash Voucher",
		"property": property,
		"session": sess,
		"voucher_date": bd,
		"payee": payee.strip()[:120],
		"category": category or "Miscellaneous",
		"amount": float(amount),
		"reason": reason.strip()[:500],
		"approver": frappe.session.user,
		"status": "Posted",
	})
	voucher.insert(ignore_permissions=True)
	record_cashier_txn(
		property, "Petty Cash", "Cash", -abs(float(amount)),
		reference=voucher.name,
		notes=f"{payee}: {reason.strip()[:120]}",
		session=sess,
	)
	return {"voucher": voucher.name, "session": session_as_dict(sess) if sess else None}


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Hotel Admin", "Night Auditor", "Kamra Agent")
def petty_cash_report(property: str, limit: int = 50):
	"""Vouchers and totals for one property only — never mixed across hotels."""
	from kamra.authz import assert_property_access
	assert_property_access(property)
	from frappe.utils import getdate, get_first_day
	bd = get_business_date(property)
	today = getdate(bd)
	month_start = get_first_day(today)
	prop_name = frappe.db.get_value("Property", property, "property_name") or property
	imprest = float(frappe.db.get_value("Property", property, "petty_cash_float") or 0)
	vouchers = frappe.get_all(
		"Petty Cash Voucher",
		filters={"property": property, "status": "Posted"},
		fields=["name", "voucher_date", "payee", "category", "amount",
		        "reason", "status", "session"],
		order_by="voucher_date desc, creation desc",
		limit_page_length=int(limit or 50),
	)
	agg = frappe.db.sql(
		"""
		SELECT
			COALESCE(SUM(CASE WHEN voucher_date = %(today)s THEN amount ELSE 0 END), 0) AS today,
			COALESCE(SUM(CASE WHEN voucher_date >= %(month_start)s THEN amount ELSE 0 END), 0) AS month,
			COALESCE(SUM(amount), 0) AS all_time,
			COUNT(*) AS voucher_count
		FROM `tabPetty Cash Voucher`
		WHERE property = %(property)s AND status = 'Posted'
		""",
		{"property": property, "today": today, "month_start": month_start},
		as_dict=True,
	)[0]
	return {
		"property": property,
		"property_name": prop_name,
		"imprest": imprest,
		"business_date": str(bd),
		"spent_today": float(agg.today or 0),
		"spent_month": float(agg.month or 0),
		"spent_all_time": float(agg.all_time or 0),
		"voucher_count": int(agg.voucher_count or 0),
		"vouchers": vouchers,
	}


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Hotel Admin", "Kamra Agent")
def set_petty_cash_float(property: str, amount: float):
	"""Set this property's standing petty-cash imprest (per hotel, not shared)."""
	from kamra.authz import assert_property_access
	assert_property_access(property)
	if float(amount) < 0:
		frappe.throw("Imprest cannot be negative.")
	if not frappe.db.exists("Property", property):
		frappe.throw(f"Unknown property: {property}")
	frappe.db.set_value("Property", property, "petty_cash_float", float(amount))
	return {"property": property, "imprest": float(amount)}


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Hotel Admin", "Night Auditor", "Kamra Agent")
def list_sessions(property: str, business_date: str | None = None,
                  status: str | None = None):
	filters: dict[str, Any] = {"property": property}
	if business_date:
		filters["business_date"] = business_date
	if status:
		filters["status"] = status
	rows = frappe.get_all(
		"Cashier Session",
		filters=filters,
		fields=["name", "cashier", "user", "business_date", "status",
		        "opening_float", "system_cash", "expected_cash", "counted_cash",
		        "variance", "opened_at", "closed_at", "terminal"],
		order_by="opened_at desc",
		limit_page_length=100,
	)
	for r in rows:
		r["cashier_id"] = frappe.db.get_value("Cashier", r.cashier, "cashier_id")
	return {"sessions": rows, "business_date": get_business_date(property)}


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Hotel Admin", "Night Auditor", "Kamra Agent")
def session_report(session: str):
	return _session_view(session)


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Hotel Admin", "Night Auditor", "Kamra Agent")
def cash_summary_v2(property: str, date: str | None = None):
	"""Unified FO + POS cash for a business date (replaces folio-only summary)."""
	date = date or get_business_date(property)
	# Prefer cashier transactions when sessions exist for the day
	rows = frappe.db.sql(
		"""
		SELECT mode, kind, COUNT(*) AS txns, COALESCE(SUM(amount), 0) AS total
		FROM `tabCashier Transaction`
		WHERE property = %(property)s AND business_date = %(date)s
		GROUP BY mode, kind
		ORDER BY total DESC
		""",
		{"property": property, "date": date}, as_dict=True,
	)
	if rows:
		by_mode: dict[str, dict] = {}
		for r in rows:
			if r.kind in ("Paid Out", "Drop", "Petty Cash"):
				continue
			m = r.mode or "Other"
			slot = by_mode.setdefault(m, {"mode": m, "txns": 0, "total": 0.0})
			slot["txns"] += int(r.txns or 0)
			slot["total"] += float(r.total or 0)
		modes = sorted(by_mode.values(), key=lambda x: -x["total"])
		return {
			"date": date,
			"modes": modes,
			"grand_total": float(sum(m["total"] for m in modes)),
			"source": "cashier",
		}
	# Fallback: folio payments (legacy) — inline to avoid circular import
	folio_rows = frappe.db.sql(
		"""
		SELECT fp.mode, COUNT(*) AS txns, COALESCE(SUM(fp.amount), 0) AS total
		FROM `tabFolio Payment` fp
		JOIN `tabFolio` f ON fp.parent = f.name
		WHERE f.property = %(property)s AND fp.posting_date = %(date)s
		GROUP BY fp.mode ORDER BY total DESC
		""",
		{"property": property, "date": date}, as_dict=True,
	)
	return {
		"date": date,
		"modes": folio_rows,
		"grand_total": float(sum(r.total for r in folio_rows)),
		"source": "folio",
	}


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Hotel Admin", "Night Auditor", "Kamra Agent")
def shift_report(property: str, business_date: str | None = None):
	"""Per-cashier totals for a business date."""
	date = business_date or get_business_date(property)
	sessions = frappe.get_all(
		"Cashier Session",
		filters={"property": property, "business_date": date},
		fields=["name", "cashier", "user", "status", "opening_float",
		        "system_cash", "system_card", "system_upi", "system_other",
		        "paid_outs", "drops", "petty_cash", "expected_cash",
		        "counted_cash", "variance", "opened_at", "closed_at"],
		order_by="opened_at asc",
	)
	for s in sessions:
		s["cashier_id"] = frappe.db.get_value("Cashier", s.cashier, "cashier_id")
	journal = frappe.db.sql(
		"""
		SELECT ct.kind, ct.mode, COUNT(*) AS txns,
		       COALESCE(SUM(ct.amount), 0) AS total
		FROM `tabCashier Transaction` ct
		WHERE ct.property = %(property)s AND ct.business_date = %(date)s
		GROUP BY ct.kind, ct.mode
		ORDER BY ct.kind, ct.mode
		""",
		{"property": property, "date": date}, as_dict=True,
	)
	return {"business_date": date, "sessions": sessions, "journal": journal}


# --- terminals: many tills, one place to see them ------------------------------

TERMINAL_EDITORS = ("Finance", "Hotel Admin")
TERMINAL_KINDS = ("Front Desk", "Restaurant", "Bar", "Spa", "Cash Office", "Other")


def _terminal_row(t: dict) -> dict:
	sess = frappe.db.get_value(
		"Cashier Session", {"cashier_terminal": t["name"], "status": "Open"},
		["name", "user", "opened_at", "expected_cash", "opening_float"], as_dict=True)
	t["open_session"] = sess
	return t


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Hotel Admin", "Night Auditor", "Kamra Agent")
def terminals(property: str, include_disabled: int = 0):
	"""A property's configured tills. Sessions opened without a terminal are
	the Default till and are not listed here."""
	filters: dict[str, Any] = {"property": property}
	if not int(include_disabled or 0):
		filters["disabled"] = 0
	rows = frappe.get_all(
		"Cashier Terminal", filters=filters,
		fields=["name", "terminal_name", "kind", "outlet", "bill_printer",
		        "default_float", "disabled"],
		order_by="terminal_name")
	return [_terminal_row(r) for r in rows]


@frappe.whitelist(methods=["POST"])
@require_roles(*TERMINAL_EDITORS)
def save_terminal(property: str, terminal_name: str, kind: str = "Front Desk",
                  outlet: str | None = None, bill_printer: str | None = None,
                  default_float: float = 0, disabled: int = 0,
                  name: str | None = None):
	"""Add or change a till."""
	from kamra.authz import assert_property_access
	assert_property_access(property)
	terminal_name = (terminal_name or "").strip()
	if not terminal_name:
		frappe.throw("Give the till a name.")
	if kind not in TERMINAL_KINDS:
		frappe.throw("Unknown kind of till.")
	if outlet and frappe.db.get_value("POS Outlet", outlet, "property") != property:
		frappe.throw("That outlet is not at this property.")
	if bill_printer:
		bp = frappe.db.get_value("Kitchen Printer", bill_printer,
		                         ["property", "prints_bills"], as_dict=True)
		if not bp or bp.property != property:
			frappe.throw("That printer is not at this property.")
		if not bp.prints_bills:
			frappe.throw("That printer is set to print KOTs only. Turn on "
			             "'Prints Bills' on it first.")
	taken = frappe.db.get_value("Cashier Terminal",
	                            {"property": property, "terminal_name": terminal_name})
	if taken and taken != name:
		frappe.throw(f"There's already a till called {terminal_name}.")
	fields = {"terminal_name": terminal_name, "kind": kind, "outlet": outlet or None,
	          "bill_printer": bill_printer or None,
	          "default_float": float(default_float or 0), "disabled": 1 if int(disabled or 0) else 0}
	if name:
		doc = frappe.get_doc("Cashier Terminal", name)
		if doc.property != property:
			frappe.throw("That till is not at this property.")
		if fields["disabled"] and frappe.db.exists(
				"Cashier Session", {"cashier_terminal": name, "status": "Open"}):
			frappe.throw("Close the open session on this till before switching it off.")
		doc.update(fields)
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc(dict(fields, doctype="Cashier Terminal",
		                          property=property)).insert(ignore_permissions=True)
	return {"ok": True, "name": doc.name}


def _safe_balance(terminal: str) -> dict[str, float]:
	got = frappe.db.sql(
		"""SELECT COALESCE(SUM(amount), 0) FROM `tabCash Transfer`
		   WHERE to_terminal = %s AND kind = 'Drop' AND status = 'Received'""",
		terminal)[0][0]
	banked = frappe.db.sql(
		"""SELECT COALESCE(SUM(amount), 0) FROM `tabCash Transfer`
		   WHERE from_terminal = %s AND kind = 'Bank Deposit' AND status = 'Received'""",
		terminal)[0][0]
	pending = frappe.db.sql(
		"""SELECT COALESCE(SUM(amount), 0) FROM `tabCash Transfer`
		   WHERE to_terminal = %s AND kind = 'Drop' AND status = 'Pending'""",
		terminal)[0][0]
	return {"received": float(got), "banked": float(banked),
	        "in_transit": float(pending), "balance": float(got) - float(banked)}


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Hotel Admin", "Night Auditor", "Kamra Agent")
def tills_board(property: str):
	"""Every till right now: who holds it, what should be in it, what is on
	its way to the cash office. The Default till (sessions opened without a
	terminal, i.e. everything from before terminals) is its own row."""
	bd = get_business_date(property)
	open_rows = frappe.get_all(
		"Cashier Session",
		filters={"property": property, "status": "Open"},
		fields=["name", "user", "cashier", "cashier_terminal", "terminal", "outlet",
		        "opened_at", "opening_float", "expected_cash", "business_date"],
		order_by="opened_at asc")
	by_term: dict[str | None, list] = {}
	for r in open_rows:
		r["cashier_id"] = frappe.db.get_value("Cashier", r.cashier, "cashier_id")
		by_term.setdefault(r.cashier_terminal or None, []).append(r)
	board = []
	for t in frappe.get_all("Cashier Terminal", filters={"property": property, "disabled": 0},
	                        fields=["name", "terminal_name", "kind", "outlet", "bill_printer"],
	                        order_by="terminal_name"):
		row = dict(t, sessions=by_term.get(t.name, []), is_default=False)
		if t.kind == "Cash Office":
			row["safe"] = _safe_balance(t.name)
		board.append(row)
	board.insert(0, {"name": None, "terminal_name": "Default", "kind": "Front Desk",
	                 "outlet": None, "bill_printer": None, "is_default": True,
	                 "sessions": by_term.get(None, [])})
	pending = frappe.get_all(
		"Cash Transfer", filters={"property": property, "status": "Pending"},
		fields=["name", "kind", "amount", "from_session", "from_terminal", "to_terminal",
		        "requested_by", "requested_at"], order_by="requested_at asc")
	review = frappe.get_all(
		"Cashier Session",
		filters={"property": property, "variance_status": "Needs Review"},
		fields=["name", "user", "cashier_terminal", "business_date", "variance", "closed_at"],
		order_by="closed_at desc", limit_page_length=20)
	return {"business_date": str(bd), "tills": board, "pending_transfers": pending,
	        "variance_review": review}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance", "Hotel Admin", "Kamra Agent")
def receive_transfer(transfer: str, pin: str | None = None):
	"""The cash office confirms a drop arrived."""
	t = frappe.get_doc("Cash Transfer", transfer)
	from kamra.authz import assert_property_access, require_cashier_pin
	assert_property_access(t.property)
	if t.kind != "Drop" or t.status != "Pending":
		frappe.throw("This transfer is not waiting to be received.")
	require_cashier_pin(t.property, pin)
	if t.requested_by == frappe.session.user and not (
			set(frappe.get_roles()) & {"Hotel Admin", "System Manager", "Finance"}):
		frappe.throw("Someone other than the person who dropped the cash must receive it.")
	t.status = "Received"
	t.received_by = frappe.session.user
	t.received_at = now_datetime()
	t.save(ignore_permissions=True)
	return {"ok": True, "safe": _safe_balance(t.to_terminal)}


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Hotel Admin")
def bank_deposit(cash_office: str, amount: float, notes: str | None = None,
                 pin: str | None = None):
	"""Cash leaves the safe for the bank."""
	office = frappe.db.get_value("Cashier Terminal", cash_office,
	                             ["name", "property", "kind"], as_dict=True)
	if not office or office.kind != "Cash Office":
		frappe.throw("That is not a cash office.")
	from kamra.authz import assert_property_access, require_cashier_pin
	assert_property_access(office.property)
	require_cashier_pin(office.property, pin)
	amt = float(amount)
	if amt <= 0:
		frappe.throw("Amount must be positive.")
	if amt > _safe_balance(office.name)["balance"] + 0.004:
		frappe.throw("That is more than the safe holds.")
	now = now_datetime()
	doc = frappe.get_doc({
		"doctype": "Cash Transfer", "property": office.property, "kind": "Bank Deposit",
		"status": "Received", "amount": amt, "business_date": get_business_date(office.property),
		"from_terminal": office.name, "requested_by": frappe.session.user, "requested_at": now,
		"received_by": frappe.session.user, "received_at": now,
		"notes": (notes or "")[:500] or None,
	}).insert(ignore_permissions=True)
	return {"ok": True, "transfer": doc.name, "safe": _safe_balance(office.name)}


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Hotel Admin")
def approve_variance(session: str, note: str | None = None):
	"""A manager signs off a till that closed over or short."""
	doc = frappe.get_doc("Cashier Session", session)
	from kamra.authz import assert_property_access
	assert_property_access(doc.property)
	if doc.variance_status != "Needs Review":
		frappe.throw("This till has nothing waiting for review.")
	if doc.user == frappe.session.user and "Hotel Admin" not in frappe.get_roles() \
	   and frappe.session.user != "Administrator":
		frappe.throw("Someone other than the cashier has to approve the variance.")
	doc.variance_status = "Approved"
	doc.variance_approved_by = frappe.session.user
	if note:
		doc.close_notes = ((doc.close_notes or "") + f" | Review: {note.strip()}")[:500]
	doc.save(ignore_permissions=True)
	return {"ok": True}
