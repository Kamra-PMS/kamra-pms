# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""What stands between a stay and its check-out.

`settlement_position` is the one place that decides what the guest owes,
what the guest is owed, and what moves to the city ledger. check_out's
guard (kamra.api._assert_settled) refuses on it; `checkout_context` shows
the desk the same numbers before anything is pressed, with a plan to clear
them through the existing writers only (add_folio_payment,
refund_security_deposit, refund_folio_payment, close_folio, the POS and
laundry endpoints, add_folio_charge for a late check-out fee).

checkout_context writes nothing. check_out posts any night not yet on the
folio before judging the balance, so the context does the same inside a
savepoint it always rolls back (as kamra.credit.checkout_credit_preview
does), and drops the after-commit work (realtime pushes, queued jobs) and
browser messages those rolled-back writes left, so opening the check-out
sheet is safe to repeat and leaves no trace.
"""

from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.utils import flt, getdate

EPS = 0.009
OPEN_POS_STATUSES = ("Placed", "Confirmed", "Preparing")
OPEN_LAUNDRY_STATUSES = ("Requested", "Collected", "In Process", "Ready")
POS_PAY_MODES = ("Cash", "Card", "UPI")  # what pos.pay_order accepts


def settlement_position(reservation: str) -> dict:
	"""Every folio of the stay, sorted into the guest's side and the
	company's. Only the stay's Company folio, or the group master when the
	group's company has credit, goes to the city ledger; anything else with
	money on it is the guest's to settle. Closed folios count too: a bill
	closed with money on it is still owed.

	owed            what the guest still has to pay
	refund_due      what the guest is owed back
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
	"""A server message without its HTML."""
	return re.sub(r"<[^>]+>", "", str(msg or "")).strip()


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
		self._had_rt = hasattr(frappe.local, "_realtime_log")
		self._rt = list(getattr(frappe.local, "_realtime_log", None) or [])
		self._msgs = len(getattr(frappe.local, "message_log", None) or [])
		db.savepoint(self.name)
		return self

	def __exit__(self, *exc):
		db = frappe.db
		lost = False
		try:
			db.rollback(save_point=self.name)
		except Exception:
			# the savepoint is gone: the database already rolled the whole
			# transaction back (a deadlock with another request). Nothing of
			# ours is left to undo, but what was read since is not the
			# snapshot we meant to show: start clean and say so.
			db.rollback()
			lost = True
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
		if lost:
			raise SnapshotLost(self.name)
		return False


class SnapshotLost(Exception):
	"""The database dropped the transaction under a _NoTrace block."""


def _modes(property: str) -> list[str]:
	from kamra.localization import pack_for, payment_modes
	return payment_modes(pack_for(property))


def _main_mode(payments, modes: list[str]) -> str | None:
	"""The mode most of the money came in by (what a refund goes back by).
	A security deposit goes back through its own refund, by its own mode."""
	by_mode: dict[str, float] = {}
	for p in payments:
		if flt(p.amount) > 0 and p.mode in modes and \
				p.payment_kind != "Security Deposit":
			by_mode[p.mode] = by_mode.get(p.mode, 0.0) + flt(p.amount)
	return max(by_mode, key=by_mode.get) if by_mode else None


def _fallback_mode(modes: list[str]) -> str:
	return "Cash" if "Cash" in modes else (modes[0] if modes else "Cash")


def _till(property: str) -> dict:
	"""The caller's till (kamra.cashier.till_state): open, or not needed at
	this property, or closed with whether this user may open it here."""
	from kamra.cashier import till_state
	return till_state(property)


# who check_out lets through (kamra.api.check_out), admins aside
CHECKOUT_ROLES = ("Front Desk", "Night Auditor", "Kamra Agent")


def _can_check_out() -> bool:
	from kamra.authz import ADMIN
	return frappe.session.user == "Administrator" or bool(
		(set(CHECKOUT_ROLES) | set(ADMIN)) & set(frappe.get_roles()))


def _companions(res) -> list[dict]:
	if not res.get("group_booking"):
		return []
	out = []
	for m in frappe.get_all(
			"Reservation",
			filters={"group_booking": res.group_booking, "status": "Checked In",
			         "name": ("!=", res.name)},
			fields=["name", "guest_name", "room", "check_out_date"],
			order_by="room asc"):
		out.append({
			"name": m.name, "guest_name": m.guest_name,
			"room_number": frappe.db.get_value("Room", m.room, "room_number")
			if m.room else None,
			"check_out_date": str(m.check_out_date)})
	return out


def _has_role(roles) -> bool:
	from kamra.authz import ADMIN
	return frappe.session.user == "Administrator" or bool(
		(set(roles) | set(ADMIN)) & set(frappe.get_roles()))


def _pending_bills(res, modes: list[str]) -> list[dict]:
	"""Bills for this stay that are not on its folio yet: restaurant and
	room-service orders still open, laundry not delivered. Each says what
	the desk can do about it, through the bill's own endpoints:

	  POS order   post to the room (pos.deliver_order) or pay at the outlet
	              (pos.pay_order)
	  laundry     a bag still at the laundry moves on to Ready
	              (laundry.laundry_status), then is handed back and billed
	              (laundry.return_items + deliver_laundry); a pickup that
	              was only requested has nothing to bill yet

	None of them stops the check-out: a bill left open is billed to the
	departed stay when it is posted later, which the sheet says plainly."""
	from kamra.laundry import LAUNDRY_ROLES
	from kamra.pos import POS_ROLES
	out = []
	if frappe.db.exists("DocType", "POS Order"):
		can_pos = _has_role(POS_ROLES)
		for o in frappe.get_all(
				"POS Order",
				filters={"reservation": res.name,
				         "status": ("in", OPEN_POS_STATUSES),
				         "posted_to_folio": 0, "paid": 0},
				fields=["name", "outlet", "status", "order_total", "nc"],
				order_by="creation asc"):
			out.append({
				"kind": "pos", "name": o.name,
				"label": (frappe.db.get_value("POS Outlet", o.outlet, "outlet_name")
				          if o.outlet else None) or _("Restaurant"),
				"status": o.status, "amount": round(flt(o.order_total), 2),
				"complimentary": bool(o.nc),
				"can_act": can_pos,
				"can_post_to_room": can_pos,
				"can_mark_ready": False,
				"billable": not o.nc,
				"pay_modes": [] if (o.nc or not can_pos)
				else [m for m in modes if m in POS_PAY_MODES],
				"hint": _("Not on the bill yet. Post it to the room, or the guest pays "
				          "for it at the outlet."),
				"act_roles": list(POS_ROLES[:2])})
	if frappe.db.exists("DocType", "Laundry Order"):
		can_laundry = _has_role(LAUNDRY_ROLES)
		for o in frappe.get_all(
				"Laundry Order",
				filters={"reservation": res.name, "order_type": "Guest",
				         "status": ("in", OPEN_LAUNDRY_STATUSES)},
				fields=["name", "status", "total", "complimentary"],
				order_by="creation asc"):
			items = frappe.get_all(
				"Laundry Order Item", filters={"parent": o.name},
				fields=["name", "item_name", "qty", "returned_qty"],
				order_by="idx asc") if o.status != "Requested" else []
			missing = sum(max(int(flt(i.qty)) - int(flt(i.returned_qty)), 0)
			              for i in items)
			if o.status == "Requested":
				hint = _("Pickup requested, nothing collected yet: there is nothing "
				         "to bill.")
			elif o.status == "Ready":
				hint = _("Back from the laundry. Hand it to the guest and post it "
				         "to the room.")
			else:
				hint = _("Still at the laundry ({0}). It can be billed once it is "
				         "back: when the bag is at the desk, mark it ready, then "
				         "post it to the room.").format(_(o.status))
			out.append({
				"kind": "laundry", "name": o.name, "label": _("Laundry"),
				"status": o.status, "amount": round(flt(o.total), 2),
				"complimentary": bool(o.complimentary),
				"can_act": can_laundry,
				# delivery bills the stay; a bag still being washed can't go
				"can_post_to_room": can_laundry and o.status == "Ready",
				"can_mark_ready": can_laundry and o.status in ("Collected", "In Process"),
				"billable": o.status != "Requested" and not o.complimentary
				and flt(o.total) > 0,
				"pieces_missing": missing,
				"items": [{"row": i.name, "item_name": i.item_name,
				           "qty": int(flt(i.qty))} for i in items],
				"pay_modes": [],
				"hint": hint,
				"act_roles": ["Front Desk", "Housekeeping"]})
	return out


def _late_checkout(res, prop, folio_rows) -> dict | None:
	"""Is the guest leaving after the property's check-out time? The fee is
	the desk's to enter (Kamra has no late-fee tariff): the dialog offers a
	Late Checkout charge line and never suggests an amount."""
	if res.status != "Checked In" or res.get("is_day_use"):
		return None
	cutoff = prop.get("checkout_time")
	if not cutoff:
		return None
	from kamra.no_show import property_now
	now = property_now(res.property)
	due_date = getdate(res.check_out_date)
	cutoff_s = str(cutoff)[:5]
	late = now.date() > due_date or (
		now.date() == due_date and now.strftime("%H:%M") > cutoff_s)
	if not late and not res.get("late_checkout"):
		return None
	names = [f["folio"] for f in folio_rows]
	charged = bool(names) and bool(frappe.db.exists(
		"Folio Charge", {"parent": ("in", names), "charge_type": "Late Checkout"}))
	room_rate = frappe.get_all(
		"Folio Charge",
		filters={"parent": ("in", names), "charge_type": "Room"} if names
		else {"name": ""},
		fields=["gst_rate"], order_by="posting_date desc", limit=1)
	guest = next((f["folio"] for f in folio_rows
	              if f["folio_type"] == "Guest" and f["status"] == "Open"), None)
	return {"checkout_time": cutoff_s, "now": now.strftime("%H:%M"),
	        "late": late, "requested": bool(res.get("late_checkout")),
	        "already_charged": charged, "folio": guest,
	        "tax_rate": flt(room_rate[0].gst_rate) if room_rate else 0.0}


def checkout_context(reservation: str) -> dict:
	"""checkout_context below, tried a second time when another request
	deadlocked it (the database then drops the whole transaction, savepoint
	included); the desk sees the bill, not a server error."""
	for attempt in (1, 2):
		try:
			return _checkout_context(reservation)
		except (SnapshotLost, frappe.QueryDeadlockError):
			frappe.db.rollback()
			if attempt == 2:
				raise
	return {}


def _checkout_context(reservation: str) -> dict:
	"""Everything the guided check-out needs, computed without changing
	anything (see the module docstring): folios with their lines and
	invoices, pending bills, a late check-out, the money plan (collect /
	refund, a held deposit through its own path), the city-ledger moves and
	their credit check, and every refusal check-out would give (`blockers`,
	each tied to the step it belongs to)."""
	from kamra.authz import assert_property_access
	from kamra.localization import pack_for
	from kamra.sop import group_for_charge

	res = frappe.get_doc("Reservation", reservation)
	assert_property_access(res.property)
	prop = frappe.get_cached_doc("Property", res.property)
	symbol = pack_for(res.property).locale(prop).get("currency_symbol", "")
	modes = _modes(res.property)
	in_house = res.status == "Checked In"
	blockers: list[dict] = []
	notices: list[dict] = []
	groups: dict[str, dict] = {}

	with _NoTrace("kamra_checkout_ctx"):
		nights_error = None
		if in_house:
			from kamra.folio import post_remaining_nights
			frappe.db.savepoint("kamra_checkout_nights")
			try:
				post_remaining_nights(res)
			except frappe.QueryDeadlockError:
				raise  # not the folio's fault: try the whole context again
			except Exception as e:
				frappe.db.rollback(save_point="kamra_checkout_nights")
				nights_error = _plain(e) or _("The remaining nights could not be posted.")
		pos = settlement_position(res.name)
		folio_rows = []
		display = list(pos["folios"])
		if res.get("group_booking"):
			# the group's master bill, shown for reference: it belongs to the
			# group and is settled with the group, not by this stay
			seen = {f["name"] for f in display}
			for m in frappe.get_all(
					"Folio", filters={"group_booking": res.group_booking,
					                  "folio_type": "Group"},
					fields=["name", "balance", "folio_type", "status",
					        "invoice_number", "grand_total", "payments_total",
					        "reservation", "group_booking"]):
				if m.name not in seen:
					display.append({**m, "balance": round(flt(m.balance), 2),
					                "city_ledger_company": None, "_group_only": True})
		for f in display:
			doc = frappe.get_doc("Folio", f["name"])
			received = sum(flt(p.amount) for p in doc.payments if flt(p.amount) > 0)
			refunded = -sum(flt(p.amount) for p in doc.payments if flt(p.amount) < 0)
			lines = []
			for c in doc.charges or []:
				grp = group_for_charge(c.charge_type, c.description or "")
				line = {"name": c.name, "charge_type": c.charge_type,
				        "description": c.description,
				        "posting_date": str(c.posting_date or ""),
				        "amount": flt(c.amount), "gst_amount": flt(c.gst_amount),
				        "is_alcohol": 1 if c.get("is_alcohol") else 0,
				        "group": grp, "folio": doc.name,
				        "folio_type": doc.folio_type or "Guest"}
				lines.append(line)
				if not f.get("_group_only"):
					g = groups.setdefault(grp, {"group": grp, "amount": 0.0,
					                            "count": 0, "lines": []})
					g["amount"] = round(g["amount"] + line["amount"] + line["gst_amount"], 2)
					g["count"] += 1
					g["lines"].append(line)
			company = f.get("city_ledger_company")
			folio_rows.append({
				"folio": doc.name, "name": doc.name,
				"folio_type": doc.folio_type or "Guest",
				"status": doc.status or "Open",
				"invoice_number": doc.invoice_number,
				"balance": f["balance"],
				"grand_total": round(flt(doc.grand_total), 2),
				"paid_total": round(flt(doc.payments_total), 2),
				"refundable": round(max(received - refunded, 0.0), 2),
				"city_ledger_company": company,
				"can_city_ledger": bool(company),
				"side": "group" if f.get("_group_only")
				else ("company" if company else "guest"),
				"has_charges": bool(doc.charges),
				"main_mode": _main_mode(doc.payments, modes),
				"charges": lines,
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
		late = _late_checkout(res, prop, folio_rows) if not nights_error else None

	pending = _pending_bills(res, modes) if in_house else []
	own = [f for f in folio_rows if f["side"] != "group"]

	if not in_house:
		blockers.append({
			"code": "not_in_house", "step": "review",
			"message": _("This stay is {0}, so there is nothing to check out.")
			.format(_(res.status))})
	if nights_error:
		closed = [f for f in own if f["status"] == "Closed" and f["side"] == "guest"]
		msg = _("Check-out posts the remaining nights first, and that failed: {0}"
		        ).format(nights_error)
		if closed:
			msg += " " + _("The folio was invoiced before every night was posted. "
			               "Open it and cancel the invoice, then check out.")
		blockers.append({"code": "nights_not_posted", "step": "review",
		                 "folio": closed[0]["folio"] if closed else None,
		                 "message": msg})

	# --- the money plan: guest side only, through the existing writers ------
	collect: list[dict] = []
	refunds: list[dict] = []
	held = flt(deposit.get("held"))
	dep_folio = deposit.get("folio")
	for f in own:
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

	if held > EPS and in_house and not any(r["kind"] == "deposit" for r in refunds):
		notices.append({
			"code": "deposit_applied",
			"message": _("The security deposit of {0}{1:,.2f} still held counts "
			             "toward the bill; check-out records it as applied.")
			.format(symbol, held)})
	companions = _companions(res)
	if res.get("group_booking"):
		notices.append({
			"code": "group",
			"message": _("Part of a group. This checks out this room only; {0} "
			             "other room(s) of the group are still in house.")
			.format(len(companions))})

	needs_pin = bool(prop.get("require_cashier_pin"))
	till = _till(res.property)
	till_open = till["open"]
	money_due = bool(collect or refunds)
	if money_due and not till_open:
		blockers.append({
			"code": "till_closed", "step": "settle",
			"message": _("Your till is closed. Open it here to take or give back "
			             "money.") if till["can_open"] else
			_("Taking or giving back money needs an open till, and your role can't "
			  "open one. Ask {0} to settle the bill.").format(
				", ".join(_(r) for r in till["who_can_open"]))})
	can_check_out = _can_check_out()
	if in_house and not can_check_out:
		blockers.append({
			"code": "role_cannot_check_out", "step": "confirm",
			"message": _("Your role can settle the bill but not check the guest out. "
			             "Ask Front Desk or a Hotel Admin to press Check out.")})
	if credit and credit["blocked"]:
		blockers.append({
			"code": "credit_blocked", "step": "company",
			"message": _("Company credit is blocked: {0}").format(
				"; ".join(r for c in credit["checks"] if c["blocked"]
				          for r in c["reasons"])),
			"can_override": credit["can_override"]})
	open_bills = [b for b in pending if b["billable"]]
	if open_bills:
		notices.append({
			"code": "pending_bills",
			"message": _("{0} bill(s) for this stay are not on the folio yet. Post "
			             "them to the room or settle them below. They do not stop "
			             "the check-out, but anything still open is not on the "
			             "guest's bill.").format(len(open_bills))})

	owed, refund_due = pos["owed"], pos["refund_due"]
	settled = owed <= EPS and refund_due <= EPS
	hard = [b for b in blockers if b["code"] != "credit_blocked"]
	credit_stuck = bool(credit and credit["blocked"] and not credit["can_override"])
	city_total = round(sum(b for _f, _c, b in pos["to_city_ledger"]), 2)
	company_name = frappe.db.get_value(
		"Corporate Account", res.company, "company_name") if res.get("company") else None
	billing_rules = [
		{"charge_type": r.charge_type, "pay_by": r.pay_by}
		for r in frappe.get_all("Company Billing Rule",
		                        filters={"parent": res.company},
		                        fields=["charge_type", "pay_by"])
	] if res.get("company") else []
	room = frappe.db.get_value(
		"Room", res.room, ["name", "room_number", "housekeeping_status"],
		as_dict=True) if res.room else None
	for b in blockers:
		b.setdefault("amount", 0)
	if owed > EPS:
		blockers.append({"code": "owed", "step": "settle", "amount": owed,
		                 "message": _("Collect {0}{1:,.2f} before departure.")
		                 .format(symbol, owed)})
	if refund_due > EPS:
		blockers.append({"code": "refund", "step": "settle", "amount": refund_due,
		                 "message": _("Refund {0}{1:,.2f} before departure.")
		                 .format(symbol, refund_due)})

	return {
		"reservation": {
			"name": res.name, "status": res.status, "guest": res.guest,
			"guest_name": res.guest_name, "company": res.company,
			"company_name": company_name,
			"group_booking": res.get("group_booking"),
			"room": res.room, "room_number": room.room_number if room else None,
			"room_type": res.room_type,
			"room_type_name": frappe.db.get_value(
				"Room Type", res.room_type, "room_type_name"),
			"check_in_date": str(res.check_in_date),
			"check_out_date": str(res.check_out_date),
			"adults": res.adults, "children": res.children,
			"vip": frappe.db.get_value("Guest", res.guest, "vip") if res.guest else 0,
		},
		"room": room,
		"currency_symbol": symbol,
		"payment_modes": modes,
		"pin_required": needs_pin,
		"till_open": till_open,
		"till": till,
		"folios": folio_rows,
		"groups": groups,
		"totals": {
			"charges": round(sum(f["grand_total"] for f in own), 2),
			"paid": round(sum(f["paid_total"] for f in own), 2),
			"balance": round(sum(f["balance"] for f in own), 2),
			"owed": owed, "refund_due": refund_due,
			"city_ledger_eligible": city_total,
			"to_city_ledger": city_total,
		},
		"billing": {"company": res.company, "company_name": company_name,
		            "credit_allowed": bool(pos["to_city_ledger"]),
		            "rules": billing_rules},
		"city_ledger": [{"folio": f, "company": c, "amount": b,
		                 "company_name": frappe.db.get_value(
			                 "Corporate Account", c, "company_name") or c}
		                for f, c, b in pos["to_city_ledger"]],
		"credit": credit,
		"deposit": {
			"name": deposit.get("name"), "status": deposit.get("status"),
			"held": held, "folio": dep_folio,
			"collected_amount": flt(deposit.get("collected")),
			"withheld_amount": flt(deposit.get("withheld")),
			"refunded_amount": flt(deposit.get("refunded")),
			"balance": held,
		} if deposit.get("name") else None,
		"collect": collect,
		"refunds": refunds,
		"pending_bills": pending,
		"late_checkout": late,
		"companions": companions,
		"blockers": blockers,
		"notices": notices,
		"settled": settled,
		"actions": {
			"can_checkout": in_house and settled and not hard and not credit_stuck,
			"can_check_out_role": can_check_out,
			"can_collect": bool(collect),
			"can_refund": bool(refunds),
			"can_city_ledger": bool(pos["to_city_ledger"]),
			"can_refund_deposit": held > EPS and bool(dep_folio),
			"can_withhold_deposit": held > EPS and in_house,
		},
	}


def _deposit_mode(folio: str, modes: list[str]) -> str | None:
	from kamra.deposit import _last_mode
	mode = _last_mode(folio)
	return mode if mode in modes else None
