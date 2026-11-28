# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt
"""Giving money back on a bill paid at the outlet.

A POS Refund record is the money record: written only here, never edited or
deleted. Every refund is approved by someone holding the approve right (see
_approve) and has a reason, pays from the caller's own open till (where the
property uses tills), and is worked out under a lock on the bill, so money
never goes out twice. The bill itself stays as printed; reports subtract
refunds on the day money went back."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from kamra.authz import require_perm
from kamra.ledger import currency_digits, home_currency, round_to
from kamra.localization import money_text

APPROVE_REFUNDS = ("POS Order", "approve_refunds")
REASON_CATEGORY = "POS Refund"
OTHER_REASON = "POS-REF-OTHER"
# refund sums are kept to three decimals, the most any currency here has; two
# figures closer than SAME differ only by float noise
SAME = 0.0005


def lock_bill(order: str) -> None:
	"""Hold the bill until the request commits: one money change at a time."""
	frappe.db.get_value("POS Order", order, "name", for_update=True)


def refunds_of(order: str) -> list:
	"""The bill's refunds, read with a lock: a plain read can come from before
	a refund that committed while this request waited for the bill."""
	return frappe.db.sql(
		"""select name, amount, tax_amount, levy_amount from `tabPOS Refund`
		where pos_order = %s order by creation, name for update""", order, as_dict=True)


# ------------------------------------------------------------ the money rule

def line_amounts(paid: float, remaining: float, items: dict, picks: list,
                 digits: int = 2) -> list:
	"""Each picked line's part of a refund: its share, by line value, of what
	was actually paid (discount, levy and tax included).

	`items` is bill row -> (line amount, quantity sold, quantity already
	refunded) for the live lines; `picks` is [(row, quantity)]. A share is
	rounded to the currency's `digits`. The refund that takes the last priced
	units takes all that is left, so refunding every item gives back exactly
	what was paid (a rupiah bill can end in sen); no refund takes more."""
	subtotal = sum(amount for amount, _sold, _done in items.values())
	taken = {}
	for row, qty in picks:
		taken[row] = taken.get(row, 0) + qty
	shares = [
		round_to(paid * items[row][0] * qty / items[row][1] / subtotal, digits) if subtotal else 0.0
		for row, qty in picks]
	last = all(done + taken.get(row, 0) >= sold - 1e-9
	           for row, (amount, sold, done) in items.items() if amount > 0)
	total = remaining if last else min(round(sum(shares), 3), remaining)
	# put any difference (rounding, or the cap) on the last lines picked
	diff = round(total - sum(shares), 3)
	for i in range(len(shares) - 1, -1, -1):
		if not diff:
			break
		step = diff if diff > 0 else max(diff, -shares[i])
		shares[i] = round(shares[i] + step, 3)
		diff = round(diff - step, 3)
	return shares


def why_not(doc) -> str | None:
	"""Why this bill can't be refunded at the till, or None."""
	if doc.posted_to_folio:
		return _("Correct this on the room's bill at the desk.")
	if not doc.paid or doc.nc or doc.status != "Delivered":
		return _("Only a bill paid at the outlet can be refunded.")
	if flt(doc.paid_amount) <= 0:
		return _("This bill has no payment record, so it can't be refunded here.")
	return None


def refund_modes(doc) -> list:
	"""How money may go back: cash for cash, the card machine for a card;
	otherwise the same way by hand, cash or a bank transfer."""
	from kamra.localization import outlet_payment_modes, pack_for

	paid = doc.payment_mode
	if paid in ("Cash", "Card"):
		return [paid]
	allowed = outlet_payment_modes(pack_for(doc.property))
	return [m for m in dict.fromkeys([paid, "Cash", "Bank Transfer"])
	        if m == paid or m in allowed]


def _refunded_qty(order: str) -> dict:
	return dict(frappe.db.sql(
		"""select l.order_item, sum(l.qty) from `tabPOS Refund Line` l
		join `tabPOS Refund` r on r.name = l.parent
		where r.pos_order = %s group by l.order_item""", order))


def _live_lines(doc) -> dict:
	done = _refunded_qty(doc.name)
	return {it.name: (flt(it.amount), flt(it.qty), flt(done.get(it.name)))
	        for it in doc.items if not it.voided}


def _digits(property: str) -> int:
	"""The decimals of the property's currency."""
	return currency_digits(home_currency(property))


def _work_out(doc, refunded: float, kind: str, lines, amount) -> tuple:
	"""(total, [{row, qty, amount, back_to_stock}]) for what was asked."""
	if isinstance(lines, str):
		lines = frappe.parse_json(lines)
	paid = flt(doc.paid_amount)
	remaining = round(paid - refunded, 3)
	if remaining <= 0:
		frappe.throw(_("Nothing is left to refund on this bill."))
	digits = _digits(doc.property)
	if kind == "amount":
		value = round_to(flt(amount), digits)
		# typing the figure the window shows as left asks for all of it
		if flt(amount) > 0 and value == round_to(remaining, digits):
			value = remaining
		if value <= 0:
			frappe.throw(_("The amount must be above zero."))
		if value > remaining:
			frappe.throw(_("You can refund up to {0}.").format(money_text(doc.property, remaining)))
		return value, []

	items = _live_lines(doc)
	rows = {it.name: it for it in doc.items if not it.voided}
	ticked = {x.get("row"): 1 for x in lines or [] if frappe.utils.cint(x.get("back_to_stock"))}
	if kind == "whole":
		picks = {row: round(sold - done, 6) for row, (_a, sold, done) in items.items()
		         if sold - done > 1e-9}
	elif kind == "items":
		picks = {}
		for x in lines or []:
			row, qty = x.get("row"), flt(x.get("qty"))
			if qty <= 0:
				continue
			if row not in rows:
				frappe.throw(_("That line is not on this bill."))
			picks[row] = picks.get(row, 0) + qty
		if not picks:
			frappe.throw(_("Pick at least one item."))
		for row, qty in picks.items():
			left = items[row][1] - items[row][2]
			if qty > left + 1e-9:
				frappe.throw(_("Only {0} of {1} left to refund.").format(
					f"{max(left, 0):g}", rows[row].item_name))
	else:
		frappe.throw(_("Refund the whole bill, chosen items, or an amount."))
	for row in ticked:
		if row in picks and not (rows[row].stock_item and rows[row].stock_posted):
			frappe.throw(_("{0} can't go back to stock.").format(rows[row].item_name))
	if not picks:
		return remaining, []
	order = list(picks.items())
	shares = line_amounts(paid, remaining, items, order, digits)
	total = round(sum(shares), 3)
	if total <= 0:
		frappe.throw(_("Nothing is left to refund on this bill."))
	return total, [
		{"row": row, "qty": qty, "amount": share, "back_to_stock": ticked.get(row, 0)}
		for (row, qty), share in zip(order, shares)]


# ------------------------------------------------------------ who and why

def _reason(code: str | None, note: str | None) -> str:
	"""The refund reason's wording. Checked here: a code from another list (a
	deposit refund, say) or one that doesn't exist is refused."""
	from kamra.ledger import ensure_default_reason_codes

	ensure_default_reason_codes()
	row = code and frappe.db.get_value(
		"Reason Code", code, ["category", "disabled", "description"], as_dict=True)
	if not row or row.category != REASON_CATEGORY or row.disabled:
		frappe.throw(_("Pick a refund reason."))
	if code == OTHER_REASON and not note:
		frappe.throw(_("Say why in the note."))
	return row.description


def _is_agent() -> bool:
	user = frappe.session.user
	return bool(frappe.flags.kamra_agent_call or frappe.flags.kamra_gate_bypass or (
		user != "Administrator" and "Kamra Agent" in frappe.get_roles(user)))


def _asks_pins(property: str) -> bool:
	"""The property's "Require cashier PIN on money actions" setting."""
	return bool(frappe.db.get_value("Property", property, "require_cashier_pin"))


def _approve(property: str, supervisor: str | None, pin) -> str:
	"""Who approved. The approve right is the protection, and the PIN follows
	the property's setting: someone who may approve refunds directly, typing
	their own PIN only where the property asks for PINs; anyone else needs an
	approver to pick their name and type their PIN, whatever the setting, as
	that is the only proof the approver was there. Never an AI agent."""
	if _is_agent():
		frappe.throw(_("An AI agent can never refund."), frappe.PermissionError)
	from kamra.authz import is_supervisor, verify_supervisor

	user = frappe.session.user
	if (supervisor or "").strip() in ("", user) and is_supervisor(user, APPROVE_REFUNDS):
		if not _asks_pins(property):
			return user
		supervisor = user
	return verify_supervisor(property, supervisor, pin, APPROVE_REFUNDS)


def _own_till(property: str, outlet: str) -> str | None:
	"""The caller's own open till, never anyone else's - not even for
	Administrator. None only where the property doesn't use tills."""
	from kamra.cashier import _open_session_names, _pick_session, tills_required

	session = _pick_session(_open_session_names(property, frappe.session.user), outlet)
	if not session and tills_required(property):
		frappe.throw("NO_OPEN_SESSION: open your till under Finance → Cashier first.")
	return session


# ------------------------------------------------------------ for the reports

def refunds_between(start, end, *, outlet: str | None = None,
                    property: str | None = None, by: str = "creation") -> list:
	"""Refunds made between two dates, for a report that subtracts them. Each
	report counts them on its own kind of date, as it counts sales: `creation`
	(the calendar day) or `business_date`."""
	filters = {"creation": ["between", [f"{start} 00:00:00", f"{end} 23:59:59.999999"]]} \
		if by == "creation" else {"business_date": ["between", [start, end]]}
	if outlet:
		filters["outlet"] = outlet
	if property:
		filters["property"] = property
	return frappe.get_all(
		"POS Refund", filters=filters,
		fields=["name", "property", "outlet", "pos_order", "business_date", "amount",
		        "tax_amount", "levy_amount", "mode", "reason_code", "approved_by",
		        "refunded_by", "creation"],
		order_by="creation asc, name asc", limit_page_length=0)


def before_tax(refund) -> float:
	"""A refund on the same footing as sales: its amount less its tax."""
	return flt(refund.amount) - flt(refund.tax_amount)


# ------------------------------------------------------------ endpoints

def history(order: str) -> list:
	rows = frappe.get_all(
		"POS Refund", filters={"pos_order": order},
		fields=["name", "amount", "tax_amount", "mode", "reason_code", "note",
		        "approved_by", "refunded_by", "business_date", "creation"],
		order_by="creation asc, name asc")
	if not rows:
		return rows
	reasons = dict(frappe.get_all(
		"Reason Code", filters={"name": ["in", [r.reason_code for r in rows]]},
		fields=["name", "description"], as_list=True))
	lines: dict = {}
	for x in frappe.get_all(
			"POS Refund Line", filters={"parent": ["in", [r.name for r in rows]],
			                            "parenttype": "POS Refund"},
			fields=["parent", "item_name", "qty", "amount", "back_to_stock"],
			order_by="idx asc"):
		lines.setdefault(x.pop("parent"), []).append(x)
	names = dict(frappe.get_all(
		"User", filters={"name": ["in", [u for r in rows for u in (r.approved_by, r.refunded_by)]]},
		fields=["name", "full_name"], as_list=True))
	for r in rows:
		r["reason"] = reasons.get(r.reason_code, r.reason_code)
		r["lines"] = lines.get(r.name, [])
		r["approved_by_name"] = names.get(r.approved_by) or r.approved_by
		r["refunded_by_name"] = names.get(r.refunded_by) or r.refunded_by
	return rows


@frappe.whitelist()
@require_perm("POS Order", "take_orders", scope={"order": "POS Order"})
def refund_options(order: str):
	"""Everything the refund window needs: whether the bill can be refunded,
	what is left, its lines, the ways money may go back, the reasons, who may
	approve (and whether the caller can, and needs their own PIN to), and the
	refunds so far."""
	from kamra.authz import is_supervisor, supervisors_for
	from kamra.ledger import ensure_default_reason_codes
	from kamra.menu_modifiers import names_of

	doc = frappe.get_doc("POS Order", order)
	problem = why_not(doc)
	made = history(order)
	refunded = round(sum(flt(r.amount) for r in made), 3)
	done = _refunded_qty(order)
	ensure_default_reason_codes()
	return {
		"order": order, "eligible": not problem, "why_not": problem,
		"paid": flt(doc.paid_amount), "paid_by": doc.payment_mode,
		"refunded": refunded,
		"remaining": round(max(flt(doc.paid_amount) - refunded, 0), 3),
		"lines": [
			{"row": it.name, "item_name": it.item_name, "qty": flt(it.qty),
			 # tells two lines of one dish apart (oat milk and plain)
			 "choices": names_of(it.modifiers),
			 "refunded_qty": flt(done.get(it.name)),
			 "can_restock": bool(it.stock_item and it.stock_posted)}
			for it in doc.items if not it.voided],
		"modes": [] if problem else refund_modes(doc),
		"reasons": [
			{"code": r.name, "label": r.description} for r in frappe.get_all(
				"Reason Code", filters={"category": REASON_CATEGORY, "disabled": 0},
				fields=["name", "description"], order_by="creation asc, name asc")],
		"approvers": supervisors_for(doc.property, APPROVE_REFUNDS),
		"can_approve": not _is_agent() and is_supervisor(perm=APPROVE_REFUNDS),
		"pin_required": _asks_pins(doc.property),
		"has_pin": bool(frappe.db.exists(
			"Cashier PIN", {"name": frappe.session.user, "must_reset": 0})),
		"refunds": made,
	}


@frappe.whitelist(methods=["POST"])
@require_perm("POS Order", "take_orders", scope={"order": "POS Order"})
def refund_quote(order: str, kind: str, lines=None, amount: float | None = None):
	"""What a refund would give back, line by line, before anyone approves it."""
	doc = frappe.get_doc("POS Order", order)
	problem = why_not(doc)
	if problem:
		frappe.throw(problem)
	refunded = sum(flt(r.amount) for r in history(order))
	total, picks = _work_out(doc, refunded, kind, lines, amount)
	return {"amount": total,
	        "lines": [{k: p[k] for k in ("row", "qty", "amount")} for p in picks]}


def _not_as_shown(expected, amount: float) -> bool:
	"""True when the screen showed another amount (none sent: nothing to compare)."""
	return expected not in (None, "") and abs(flt(expected) - amount) >= SAME


def _has_seen(seen, name: str, refunds: list) -> bool:
	"""True when a window showing `seen` as already refunded had this refund in
	that figure: it is then asking for more, not repeating a lost request.
	`refunds` are the bill's, oldest first."""
	if seen in (None, ""):
		return False
	before = 0.0
	for r in refunds:
		if r.name == name:
			break
		before += flt(r.amount)
	return flt(seen) - before >= SAME


def _answer(name: str, order: str) -> dict:
	paid, refunded = frappe.db.get_value("POS Order", order, ["paid_amount", "refunded_amount"])
	return {"refund": name, "amount": flt(frappe.db.get_value("POS Refund", name, "amount")),
	        "refunded": flt(refunded), "remaining": round(flt(paid) - flt(refunded), 3)}


@frappe.whitelist(methods=["POST"])
@require_perm("POS Order", "take_orders", scope={"order": "POS Order"})
def refund_bill(order: str, kind: str, mode: str, reason_code: str,
                supervisor: str | None = None, supervisor_pin: str | None = None,
                idempotency_key: str | None = None, lines=None,
                amount: float | None = None, note: str | None = None,
                expected_amount: float | None = None,
                seen_refunded: float | None = None):
	"""Give money back on a paid bill: the whole of what is left ("whole"),
	chosen items ("items", lines = [{row, qty, back_to_stock}]), or an amount
	("amount"). The screen sends one idempotency_key per attempt, so a retried
	request answers with the refund already made and pays nothing twice. It also
	sends expected_amount, the figure it showed: if what would be recorded
	differs (another refund came in between), nothing is paid. seen_refunded is
	what the window showed as already given back: once that includes the refund
	made for this key, pressing again is refused rather than answered with it."""
	key = (idempotency_key or "").strip()[:140]
	if not key:
		frappe.throw(_("Try again from the refund window."))
	note = (note or "").strip()[:500] or None
	prop = frappe.db.get_value("POS Order", order, "property")
	why = _reason(reason_code, note)
	approver = _approve(prop, supervisor, supervisor_pin)

	# one money change at a time on a bill, read after the lock: end the
	# transaction the checks above read in
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- only reason-code seeds and PIN counters written so far; the reads after the lock need a fresh snapshot
	lock_bill(order)
	prior = refunds_of(order)
	again = frappe.db.get_value(
		"POS Refund", {"idempotency_key": key}, ["name", "pos_order"], as_dict=True)
	if again:
		if again.pos_order != order:
			frappe.throw(_("Try again from the refund window."))
		made = _answer(again.name, order)
		if _not_as_shown(expected_amount, made["amount"]) \
				or _has_seen(seen_refunded, again.name, prior):
			frappe.throw(_("This attempt already refunded {0}. Close the window to see it.")
			             .format(money_text(prop, made["amount"])))
		return made
	doc = frappe.get_doc("POS Order", order)
	problem = why_not(doc)
	if problem:
		frappe.throw(problem)
	modes = refund_modes(doc)
	if mode not in modes:
		frappe.throw(_("Money goes back as {0}.").format(", ".join(modes)))
	refunded = round(sum(flt(r.amount) for r in prior), 3)
	total, picks = _work_out(doc, refunded, kind, lines, amount)
	# the cashier counts out what the screen said: never record another figure
	if _not_as_shown(expected_amount, total):
		frappe.throw(_("The amount to give back has changed: it is now {0}. Check it and refund again.")
		             .format(money_text(prop, total)))
	session = _own_till(doc.property, doc.outlet)

	paid = flt(doc.paid_amount)
	last = abs(paid - refunded - total) < SAME
	digits = _digits(doc.property)

	def part(whole, field):
		left = round(flt(whole) - sum(flt(r.get(field)) for r in prior), 3)
		if last:
			return left
		# whole-unit parts can add up to more than there is: never below zero
		return min(round_to(flt(whole) * total / paid, digits), left)

	rows = {it.name: it for it in doc.items}
	menu = [rows[p["row"]].menu_item for p in picks]
	drinks = set(frappe.get_all(
		"Menu Item", filters={"name": ["in", menu or [""]], "is_alcohol": 1}, pluck="name"))
	card = (doc.card_network, doc.card_last4) if mode == "Card" else (None, None)
	refund = frappe.get_doc({
		"doctype": "POS Refund", "property": doc.property, "outlet": doc.outlet,
		"pos_order": doc.name, "business_date": _business_date(doc.property),
		"amount": total, "tax_amount": part(doc.paid_tax, "tax_amount"),
		"levy_amount": part(doc.levy_amount, "levy_amount"), "mode": mode,
		"card_network": card[0], "card_last4": card[1], "reason_code": reason_code,
		"note": note, "approved_by": approver, "refunded_by": frappe.session.user,
		"cashier_session": session, "idempotency_key": key,
		"lines": [{
			"order_item": p["row"], "item_name": rows[p["row"]].item_name, "qty": p["qty"],
			"amount": p["amount"], "back_to_stock": p["back_to_stock"],
			"is_beverage": 1 if rows[p["row"]].menu_item in drinks else 0,
			"stock_item": rows[p["row"]].stock_item if p["back_to_stock"] else None,
		} for p in picks],
	})
	refund.flags.from_pos_refund = True
	refund.insert(ignore_permissions=True)

	if session:
		from kamra.cashier import record_cashier_txn
		record_cashier_txn(
			doc.property, "Refund", mode, -total, pos_order=doc.name,
			reference=f"POS refund {doc.name}", notes=f"{why}: {note}" if note else why,
			session=session, card_network=card[0], card_last4=card[1])
	# stock rows are taken in ingredient order, as the kitchen takes them
	for line in sorted((x for x in refund.lines if x.back_to_stock), key=lambda x: x.stock_item):
		from kamra.inventory import _apply_move
		_apply_move(doc.property, doc.outlet, line.stock_item, line.qty, "Return",
		            ref_dt="POS Refund", ref_dn=refund.name, note=f"Refunded {doc.name}")
	frappe.db.set_value("POS Order", doc.name, "refunded_amount", round(refunded + total, 3))

	from kamra.savings import log_action
	log_action("pos_refund", "POS Order", doc.name, doc.property,
	           rationale=f"{money_text(doc.property, total)} refunded ({mode}) - {why}; "
	                     f"approved by {approver}",
	           approver=approver, channel="Desk")
	from kamra import localization as loc
	loc.on_pos_refund(loc.pack_for(doc.property), refund.name)
	return _answer(refund.name, doc.name)


def _business_date(property: str):
	from kamra.business_date import get_business_date

	return get_business_date(property)
