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
		"max_cash_refund": 5000,
	})
	doc.insert(ignore_permissions=True)
	return doc.name


def require_open_session(property: str) -> str | None:
	"""Return open session name, or None when agents bypass. Throws otherwise."""
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
	user = frappe.session.user
	sess = frappe.db.get_value(
		"Cashier Session",
		{"property": property, "user": user, "status": "Open"},
		"name",
	)
	if not sess:
		frappe.throw(
			"NO_OPEN_SESSION: open your till under Finance → Cashier first.",
		)
	return sess


def _recompute_session_totals(session: str) -> dict[str, float]:
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
	sess.system_cash = cash
	sess.system_card = card
	sess.system_upi = upi
	sess.system_other = other
	sess.paid_outs = paid_outs
	sess.drops = drops
	sess.petty_cash = petty
	sess.expected_cash = expected
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
) -> str | None:
	"""Append a Cashier Transaction. Returns session name (or None)."""
	sess = session
	if not sess:
		try:
			sess = require_open_session(property)
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
		"reference": (reference or "")[:140] or None,
		"notes": notes,
		"posted_by": frappe.session.user,
		"posted_at": now_datetime(),
	}).insert(ignore_permissions=True)
	_recompute_session_totals(sess)
	return sess


def session_as_dict(name: str) -> dict[str, Any]:
	doc = frappe.get_doc("Cashier Session", name)
	totals = _recompute_session_totals(name)
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


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Kamra Agent")
def open_session(property: str, opening_float: float = 0,
                 terminal: str | None = None):
	"""Open the caller's till for the current business date."""
	ensure_business_date(property)
	user = frappe.session.user
	existing = frappe.db.get_value(
		"Cashier Session",
		{"property": property, "user": user, "status": "Open"},
		"name",
	)
	if existing:
		return session_as_dict(existing)
	cashier = ensure_cashier(property, user)
	bd = get_business_date(property)
	doc = frappe.get_doc({
		"doctype": "Cashier Session",
		"property": property,
		"cashier": cashier,
		"user": user,
		"business_date": bd,
		"terminal": terminal or "",
		"status": "Open",
		"opening_float": float(opening_float or 0),
		"opened_at": now_datetime(),
		"expected_cash": float(opening_float or 0),
	})
	doc.insert(ignore_permissions=True)
	return session_as_dict(doc.name)


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Kamra Agent")
def current_session(property: str):
	"""Caller's open session, or null."""
	user = frappe.session.user
	name = frappe.db.get_value(
		"Cashier Session",
		{"property": property, "user": user, "status": "Open"},
		"name",
	)
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
	return {"open": True, **session_as_dict(name)}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance", "Kamra Agent")
def close_session(session: str, counted_cash: float,
                  notes: str | None = None, pin: str | None = None):
	"""Count the drawer and close the till."""
	doc = frappe.get_doc("Cashier Session", session)
	if doc.status != "Open":
		frappe.throw("This session is already closed.")
	if doc.user != frappe.session.user and not (
			set(frappe.get_roles()) & {"Hotel Admin", "System Manager",
			                           "Administrator", "Finance"}):
		frappe.throw("Only the owning cashier (or Finance) can close this till.")
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
	name = f"SHIFT-{shift_date}-{slot}"
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
	sess = require_open_session(property)
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
              pin: str | None = None):
	"""Move cash from the till to a drop safe / general cashier."""
	if float(amount) <= 0:
		frappe.throw("Amount must be positive.")
	from kamra.authz import require_cashier_pin
	require_cashier_pin(property, pin)
	sess = require_open_session(property)
	record_cashier_txn(
		property, "Drop", "Cash", -abs(float(amount)),
		reference=(location or "safe")[:80],
		notes=f"Cash drop to {location or 'safe'}",
		session=sess,
	)
	return session_as_dict(sess) if sess else {"ok": True}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance", "Kamra Agent")
def post_petty_cash(property: str, amount: float, payee: str, category: str,
                    reason: str, pin: str | None = None):
	if float(amount) <= 0:
		frappe.throw("Amount must be positive.")
	if not (payee or "").strip() or not (reason or "").strip():
		frappe.throw("Payee and reason are required.")
	from kamra.authz import require_cashier_pin
	require_cashier_pin(property, pin)
	sess = require_open_session(property)
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
@require_roles("Front Desk", "Finance", "Hotel Admin", "Kamra Agent")
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
@require_roles("Front Desk", "Finance", "Hotel Admin", "Kamra Agent")
def session_report(session: str):
	return session_as_dict(session)


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Hotel Admin", "Kamra Agent")
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
@require_roles("Front Desk", "Finance", "Hotel Admin", "Kamra Agent")
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
