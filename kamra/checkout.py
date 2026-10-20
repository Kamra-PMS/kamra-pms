# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""What stands between a stay and its check-out.

`settlement_position` is the one place that decides what the guest owes,
what the guest is owed, and what moves to the city ledger. check_out's
guard (kamra.api._assert_settled) refuses on it; `settlement_preview`
shows the desk the same numbers before anything is pressed, plus a plan
to clear them through the existing writers (add_folio_payment,
refund_security_deposit, refund_folio_payment, close_folio).

The preview writes nothing. check_out posts any night not yet on the
folio before judging the balance, so the preview does the same inside a
savepoint it always rolls back (as kamra.credit.checkout_credit_preview
does), and drops the after-commit work (realtime pushes, queued jobs)
that those rolled-back saves had queued, so no phantom event leaves.
"""

from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.utils import flt

EPS = 0.009
OPEN_POS_STATUSES = ("Placed", "Confirmed", "Preparing")


def settlement_position(reservation: str) -> dict:
	"""Every folio of the stay, sorted into the guest's side and the
	company's. Only the stay's Company folio, or the group master when the
	group's company has credit, goes to the city ledger; anything else with
	money on it is the guest's to settle. Closed folios count too: a bill
	closed with money on it is still owed.

	owed        what the guest still has to pay
	refund_due  what the guest is owed back
	to_city_ledger  [(folio, company, balance)] check-out will move
	"""
	from kamra.ledger import company_payer_of

	owed = refund = 0.0
	to_city_ledger: list[tuple[str, str, float]] = []
	folios = []
	for f in frappe.get_all(
			"Folio", filters={"reservation": reservation},
			fields=["name", "balance", "folio_type", "group_booking",
			        "reservation", "status", "invoice_number",
			        "grand_total", "payments_total"],
			order_by="creation asc"):
		balance = round(flt(f.balance), 2)
		payer = company_payer_of(f) if balance > EPS else None
		if payer:
			to_city_ledger.append((f.name, payer, balance))
		elif balance > EPS:
			owed += balance
		elif balance < -EPS:
			refund -= balance
		folios.append({**f, "balance": balance, "city_ledger_company": payer})
	return {"owed": round(owed, 2), "refund_due": round(refund, 2),
	        "to_city_ledger": to_city_ledger, "folios": folios}


def _plain(msg) -> str:
	"""A server message without its HTML and machine prefix."""
	text = re.sub(r"<[^>]+>", "", str(msg or "")).strip()
	return text


class _NoTrace:
	"""Roll back to a savepoint and forget what the rolled-back writes
	queued: after-commit callbacks (realtime, enqueue_after_commit), the
	realtime log and any message a caught refusal left for the browser."""

	def __init__(self, name: str):
		self.name = name

	def __enter__(self):
		db = frappe.db
		self._after = list(db.after_commit._functions)
		self._before = list(db.before_commit._functions)
		self._rt = list(getattr(frappe.local, "_realtime_log", None) or [])
		self._had_rt = hasattr(frappe.local, "_realtime_log")
		self._msgs = len(getattr(frappe.local, "message_log", None) or [])
		db.savepoint(self.name)
		return self

	def __exit__(self, *exc):
		db = frappe.db
		db.rollback(save_point=self.name)
		db.after_commit._functions.clear()
		db.after_commit._functions.extend(self._after)
		db.before_commit._functions.clear()
		db.before_commit._functions.extend(self._before)
		if self._had_rt:
			frappe.local._realtime_log = self._rt
		elif hasattr(frappe.local, "_realtime_log"):
			del frappe.local._realtime_log
		log = getattr(frappe.local, "message_log", None)
		if log is not None:
			del log[self._msgs:]
		return False


def _modes(property: str) -> list[str]:
	from kamra.localization import pack_for, payment_modes
	return payment_modes(pack_for(property))


def _payments(folio: str) -> list:
	return frappe.get_all(
		"Folio Payment", filters={"parent": folio, "parenttype": "Folio"},
		fields=["payment_kind", "mode", "amount"], order_by="idx asc")


def _main_mode(payments, modes: list[str]) -> str | None:
	"""The mode most of the money came in by (what a refund goes back by)."""
	by_mode: dict[str, float] = {}
	for p in payments:
		# a security deposit goes back through its own refund, by its own mode
		if flt(p.amount) > 0 and p.mode in modes and \
				p.payment_kind != "Security Deposit":
			by_mode[p.mode] = by_mode.get(p.mode, 0.0) + flt(p.amount)
	return max(by_mode, key=by_mode.get) if by_mode else None


def _till_open(property: str) -> bool:
	from kamra.cashier import _agent_bypass
	if _agent_bypass():
		return True
	return bool(frappe.db.exists(
		"Cashier Session", {"property": property, "user": frappe.session.user,
		                    "status": "Open"}))


def _group(res) -> dict | None:
	if not res.get("group_booking"):
		return None
	g = frappe.db.get_value("Group Booking", res.group_booking,
	                        ["name", "group_name", "company"], as_dict=True)
	if not g:
		return None
	others = frappe.db.count("Reservation", {
		"group_booking": res.group_booking, "status": "Checked In",
		"name": ("!=", res.name)})
	return {"name": g.name, "group_name": g.group_name or g.name,
	        "company": g.company, "others_in_house": others}


def _open_pos(res) -> list[dict]:
	if not frappe.db.exists("DocType", "POS Order"):
		return []
	return frappe.get_all(
		"POS Order",
		filters={"reservation": res.name, "status": ("in", OPEN_POS_STATUSES),
		         "posted_to_folio": 0, "paid": 0},
		fields=["name", "outlet", "status", "order_total"],
		order_by="creation asc")


def settlement_preview(reservation: str) -> dict:
	"""Everything the check-out dialog needs, computed without changing
	anything: balances after the remaining nights are posted, the money
	steps that clear them, the invoice state of each folio, the company
	credit check and every refusal check-out would give."""
	from kamra.authz import assert_property_access
	from kamra.localization import pack_for

	res = frappe.get_doc("Reservation", reservation)
	assert_property_access(res.property)
	prop = frappe.get_cached_doc("Property", res.property)
	symbol = pack_for(res.property).locale(prop).get("currency_symbol", "")
	modes = _modes(res.property)
	in_house = res.status == "Checked In"
	blockers: list[dict] = []
	notices: list[dict] = []

	with _NoTrace("kamra_settle_preview"):
		nights_error = None
		if in_house:
			from kamra.folio import post_remaining_nights
			frappe.db.savepoint("kamra_settle_nights")
			try:
				post_remaining_nights(res)
			except Exception as e:
				frappe.db.rollback(save_point="kamra_settle_nights")
				nights_error = _plain(e) or _("The remaining nights could not be posted.")
		pos = settlement_position(res.name)
		folio_rows = []
		for f in pos["folios"]:
			payments = _payments(f["name"])
			received = sum(flt(p.amount) for p in payments if flt(p.amount) > 0)
			refunded = -sum(flt(p.amount) for p in payments if flt(p.amount) < 0)
			folio_rows.append({
				"folio": f["name"],
				"folio_type": f.get("folio_type") or "Guest",
				"status": f.get("status") or "Open",
				"invoice_number": f.get("invoice_number"),
				"balance": f["balance"],
				"grand_total": round(flt(f.get("grand_total")), 2),
				"paid": round(flt(f.get("payments_total")), 2),
				"refundable": round(max(received - refunded, 0.0), 2),
				"city_ledger_company": f.get("city_ledger_company"),
				"side": "company" if f.get("city_ledger_company") else "guest",
				"has_charges": flt(f.get("grand_total")) != 0,
				"main_mode": _main_mode(payments, modes),
			})
		from kamra.deposit import deposit_state
		deposit = deposit_state(res)
		credit = None
		if in_house and not nights_error and pos["to_city_ledger"]:
			from kamra.credit import (_for_ui, can_override,
			                          checkout_credit_checks, credit_policy)
			checks = [_for_ui(c) for c in checkout_credit_checks(res.name)]
			credit = {"policy": credit_policy(res.property), "checks": checks,
			          "ok": all(c["ok"] for c in checks),
			          "blocked": any(c["blocked"] for c in checks),
			          "can_override": can_override()}

	if not in_house:
		blockers.append({
			"code": "not_in_house", "step": "review",
			"message": _("This stay is {0}, so there is nothing to check out.")
			.format(_(res.status))})
	if nights_error:
		guest_closed = [f for f in folio_rows if f["status"] == "Closed"
		                and f["side"] == "guest"]
		blockers.append({
			"code": "nights_not_posted", "step": "review",
			"folio": guest_closed[0]["folio"] if guest_closed else None,
			"message": (_("Check-out posts the remaining nights first, and "
			              "that failed: {0}").format(nights_error)
			            + (" " + _("The folio was invoiced before every night "
			                       "was posted. Open it and cancel the invoice, "
			                       "then check out.") if guest_closed else ""))})

	# --- the money plan --------------------------------------------------
	collect: list[dict] = []
	refunds: list[dict] = []
	held = flt(deposit.get("held"))
	dep_folio = deposit.get("folio")
	for f in folio_rows:
		if f["side"] != "guest":
			continue
		if f["balance"] > EPS:
			collect.append({"folio": f["folio"], "folio_type": f["folio_type"],
			                "amount": f["balance"],
			                "invoiced": f["status"] == "Closed"})
		elif f["balance"] < -EPS:
			due = -f["balance"]
			if f["status"] == "Closed":
				blockers.append({
					"code": "refund_on_invoiced_folio", "step": "settle",
					"folio": f["folio"],
					"message": _("{0}{1:,.2f} is owed back on folio {2}, which is "
					             "already invoiced ({3}). A refund needs the invoice "
					             "cancelled first: open the folio.").format(
						symbol, due, f["folio"], f["invoice_number"] or "")})
				continue
			from_deposit = 0.0
			if f["folio"] == dep_folio and held > EPS:
				from_deposit = round(min(held, due), 2)
				refunds.append({
					"kind": "deposit", "folio": f["folio"],
					"folio_type": f["folio_type"], "amount": from_deposit,
					"source": "security_deposit",
					"mode": _deposit_mode(f["folio"], modes) or f["main_mode"]
					or _fallback_mode(modes)})
			rest = round(due - from_deposit, 2)
			if rest > EPS:
				avail = round(f["refundable"] - from_deposit, 2)
				amount = round(min(rest, max(avail, 0.0)), 2)
				if amount > EPS:
					refunds.append({
						"kind": "folio", "folio": f["folio"],
						"folio_type": f["folio_type"], "amount": amount,
						"source": "overpayment",
						"mode": f["main_mode"] or _fallback_mode(modes)})
				if rest - amount > EPS:
					blockers.append({
						"code": "refund_exceeds_collected", "step": "settle",
						"folio": f["folio"],
						"message": _("Folio {0} shows {1}{2:,.2f} in the guest's "
						             "favour but only {1}{3:,.2f} was collected on it, "
						             "so it can't all be refunded. Open the folio and "
						             "correct it (move a charge or a payment).").format(
							f["folio"], symbol, rest, max(avail, 0.0))})

	if held > EPS and not any(r["kind"] == "deposit" for r in refunds) and in_house:
		notices.append({
			"code": "deposit_applied",
			"message": _("The security deposit of {0}{1:,.2f} still held counts "
			             "toward the bill; check-out records it as applied.")
			.format(symbol, held)})

	open_pos = _open_pos(res) if in_house else []
	if open_pos:
		notices.append({
			"code": "open_pos_orders",
			"message": _("{0} restaurant or room-service order(s) for this stay "
			             "are not on the folio yet. They post to the folio when "
			             "delivered: deliver or settle them before check-out so "
			             "the guest pays for them.").format(len(open_pos))})
	group = _group(res)
	if group:
		notices.append({
			"code": "group",
			"message": _("Part of group {0}. This checks out this room only; "
			             "{1} other room(s) of the group stay in house.")
			.format(group["group_name"], group["others_in_house"])})

	needs_pin = bool(prop.get("require_cashier_pin"))
	till_open = _till_open(res.property)
	money_due = bool(collect or refunds)
	if money_due and not till_open:
		blockers.append({
			"code": "till_closed", "step": "settle",
			"message": _("Open your till (Finance, Cashier) to take or give "
			             "back money, then come back to check out.")})
	if credit and credit["blocked"]:
		blockers.append({
			"code": "credit_blocked", "step": "confirm",
			"message": _("Company credit is blocked."),
			"can_override": credit["can_override"]})

	owed, refund_due = pos["owed"], pos["refund_due"]
	settled = owed <= EPS and refund_due <= EPS
	hard = [b for b in blockers if b["code"] not in ("credit_blocked",)]
	return {
		"reservation": res.name,
		"guest_name": res.guest_name,
		"room": (res.room or "").split("-")[-1] or None,
		"status": res.status,
		"check_in_date": str(res.check_in_date),
		"check_out_date": str(res.check_out_date),
		"currency_symbol": symbol,
		"payment_modes": modes,
		"pin_required": needs_pin,
		"till_open": till_open,
		"totals": {"owed": owed, "refund_due": refund_due,
		           "to_city_ledger": round(sum(b for _f, _c, b in
		                                        pos["to_city_ledger"]), 2)},
		"folios": folio_rows,
		"city_ledger": [{"folio": f, "company": c, "amount": b}
		                for f, c, b in pos["to_city_ledger"]],
		"deposit": {"name": deposit.get("name"), "status": deposit.get("status"),
		            "held": held, "folio": dep_folio},
		"collect": collect,
		"refunds": refunds,
		"credit": credit,
		"open_pos_orders": open_pos,
		"group": group,
		"blockers": blockers,
		"notices": notices,
		"steps": {"settle": money_due or any(b["step"] == "settle" for b in blockers),
		          "confirm": in_house},
		"settled": settled,
		"can_check_out": in_house and settled and not hard
		                 and not (credit and credit["blocked"]
		                          and not credit["can_override"]),
	}


def _deposit_mode(folio: str, modes: list[str]) -> str | None:
	from kamra.deposit import _last_mode
	mode = _last_mode(folio)
	return mode if mode in modes else None


def _fallback_mode(modes: list[str]) -> str:
	return "Cash" if "Cash" in modes else (modes[0] if modes else "Cash")
