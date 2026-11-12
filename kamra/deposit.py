# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Security deposit liability lifecycle (ADR-009).

A refundable damage deposit (villas, long stays) is a liability the hotel
holds for the guest - never accommodation revenue. Every rupee moves through
the folio writers that already exist; this module only decides what is
allowed and keeps the stay's Security Deposit record in step:

collect   add_folio_payment(kind="Security Deposit")
          folio: payment row          ledger: Deposit  credit (liability up)
waive     no money; a reason on the record
withhold  _post_folio_charge (a damage line, revenue)
          ledger: Guest debit (the charge) + transfer Deposit debit /
          Guest credit (the held money pays the charge)
refund    _refund_folio_payment (the refund writer: till, folio, ledger)
          ledger: Deposit debit (liability down) - not the Guest ledger

The deposit payment row already counts in the folio's payments, so the
guest's balance stays right without a second payment row: a withheld part
is absorbed by the damage charge, the rest leaves the folio as a refund.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

# a deposit can be taken on a booking that is still coming, or in-house
COLLECT_STATUSES = ("Confirmed", "Pending Payment", "Held", "Checked In")
REFUND_REASON = "Security deposit refund"
WITHHOLD_PREFIX = "Damage / security deposit withheld"


def _has_doctype() -> bool:
	return bool(frappe.db.exists("DocType", "Security Deposit"))


def _policy_amount(property: str) -> float:
	return flt(frappe.get_cached_value("Property", property,
	                                   "security_deposit_amount") or 0)


def ensure_deposit_for_reservation(reservation, amount: float = 0) -> str | None:
	"""The stay's Security Deposit row, created on first need. The amount
	comes from the property's policy; with no policy, a desk-agreed amount
	(the first collection) opens it - villas often set it per booking."""
	if isinstance(reservation, str):
		reservation = frappe.get_doc("Reservation", reservation)
	if not _has_doctype():
		return None
	existing = frappe.db.get_value(
		"Security Deposit", {"reservation": reservation.name}, "name")
	if existing:
		return existing
	required = _policy_amount(reservation.property) or flt(amount)
	if required <= 0:
		return None
	doc = frappe.get_doc({
		"doctype": "Security Deposit",
		"reservation": reservation.name,
		"property": reservation.property,
		"guest": reservation.guest,
		"status": "Required",
		"method": "payment",
		"required_amount": required,
	})
	doc.insert(ignore_permissions=True)
	return doc.name


def _get(reservation: str):
	name = frappe.db.get_value(
		"Security Deposit", {"reservation": reservation}, "name") \
		if _has_doctype() else None
	if not name:
		frappe.throw(_("No security deposit has been taken on this stay."))
	return frappe.get_doc("Security Deposit", name)


def _reservation(reservation: str):
	res = frappe.get_doc("Reservation", reservation)
	from kamra.crs import assert_property_access
	assert_property_access(res.property)
	return res


def _guest_folio(res, create: bool = False) -> str | None:
	name = frappe.db.get_value(
		"Folio", {"reservation": res.name, "folio_type": "Guest"}, "name")
	if name or not create:
		return name
	from kamra.folio import open_folio
	return open_folio(res)


def _held_status(res) -> str:
	return "Held" if res.status == "Checked In" else "Collected"


def _settle_status(dep, res) -> None:
	"""Status after a withhold or refund: open while money is still held."""
	if flt(dep.balance) > 0.009:
		dep.status = "Withheld" if flt(dep.withheld_amount) > 0 \
			else _held_status(res)
	elif flt(dep.refunded_amount) > 0:
		dep.status = "Refunded"
	else:
		dep.status = "Withheld"


def record_collected(reservation: str, amount: float, mode: str) -> None:
	"""Called by add_folio_payment after a Security Deposit payment lands on
	a guest folio - the only place collected_amount moves up."""
	if not _has_doctype():
		return
	res = frappe.get_doc("Reservation", reservation)
	name = ensure_deposit_for_reservation(res, amount)
	if not name:
		return
	dep = frappe.get_doc("Security Deposit", name)
	dep.collected_amount = flt(dep.collected_amount) + flt(amount)
	dep.method = "cash" if mode == "Cash" else "payment"
	dep.status = _held_status(res)
	dep.save(ignore_permissions=True)


def collect_deposit(reservation: str, amount: float, *, mode: str = "Cash",
                    reference: str | None = None,
                    pin: str | None = None,
                    idempotency_key: str | None = None) -> dict:
	"""Take the security deposit: a Security Deposit payment on the guest
	folio (opened early if the guest hasn't arrived), held as a liability.

	Pass idempotency_key (one per Collect press): a retry with the same key
	returns the first result instead of posting again."""
	key = (idempotency_key or "").strip() or None
	if key:
		from kamra.api import _paid_with_key
		folio = _paid_with_key(key, reservation=reservation)
		if folio:
			res = _reservation(reservation)
			state = deposit_state(res)
			state["idempotent_replay"] = 1
			return state
	res = _reservation(reservation)
	if res.status not in COLLECT_STATUSES:
		frappe.throw(_("A security deposit can't be taken on a {0} booking.")
		             .format(res.status))
	amt = flt(amount)
	if amt <= 0:
		frappe.throw(_("Enter the deposit amount."))
	if not _has_doctype():
		frappe.throw(_("Security deposits are not set up on this site."))
	existing = frappe.db.get_value(
		"Security Deposit", {"reservation": res.name}, ["status"], as_dict=True)
	if existing and existing.status == "Waived":
		frappe.throw(_("This deposit was waived."))
	if existing and existing.status == "Refunded":
		frappe.throw(_("This deposit has already been refunded."))
	from kamra.localization import pack_for, payment_modes
	modes = payment_modes(pack_for(res.property))
	if mode not in modes:
		frappe.throw(_("Pick a payment mode: {0}.").format(", ".join(modes)))

	folio = _guest_folio(res, create=True)
	from kamra.api import add_folio_payment
	# the one payment writer: cashier PIN, open till, ledger (Deposit) and
	# record_collected all happen in there
	add_folio_payment(folio, mode, amt,
	                  reference=reference or f"security-deposit:{res.name}",
	                  pin=pin, kind="Security Deposit", idempotency_key=key)
	from kamra.savings import log_action
	log_action("collect_security_deposit", "Reservation", res.name,
	           res.property,
	           rationale=f"{mode} security deposit {amt:,.2f} held for "
	                     f"{res.guest_name}")
	res.reload()
	return deposit_state(res)


def waive_deposit(reservation: str, reason: str) -> dict:
	res = _reservation(reservation)
	if not (reason or "").strip():
		frappe.throw(_("Waiving a deposit needs a reason."))
	name = ensure_deposit_for_reservation(res)
	if not name:
		frappe.throw(_("No security deposit is required for this stay."))
	dep = frappe.get_doc("Security Deposit", name)
	if flt(dep.collected_amount) > 0:
		frappe.throw(_("Money has already been taken - refund the deposit "
		               "instead of waiving it."))
	dep.status = "Waived"
	dep.method = "waiver"
	dep.reason = reason.strip()
	dep.save(ignore_permissions=True)
	from kamra.savings import log_action
	log_action("waive_security_deposit", "Reservation", res.name,
	           res.property, rationale=f"Deposit waived: {reason.strip()}")
	return deposit_state(res)


def withhold_deposit(reservation: str, amount: float, reason: str,
                     evidence: str | None = None,
                     pin: str | None = None) -> dict:
	"""Keep all or part of the held deposit against damage. The withheld
	part becomes a charge on the folio (revenue, Guest ledger) and the same
	amount moves out of the Deposit ledger to pay it."""
	res = _reservation(reservation)
	dep = _get(res.name)
	amt = flt(amount)
	if amt <= 0:
		frappe.throw(_("Enter the amount to withhold."))
	if not (reason or "").strip():
		frappe.throw(_("Withholding a deposit needs a reason."))
	if amt > flt(dep.balance) + 0.009:
		frappe.throw(_("Only {0:,.2f} of the deposit is still held.")
		             .format(flt(dep.balance)))
	folio = _guest_folio(res)
	if not folio or frappe.db.get_value("Folio", folio, "status") == "Closed":
		frappe.throw(_("The guest folio is closed - withhold before closing it."))
	from kamra.api import _pin_guard, _post_folio_charge
	_pin_guard(folio, pin)

	reason = reason.strip()
	_post_folio_charge(folio, "Misc", f"{WITHHOLD_PREFIX}: {reason}"[:140],
	                   amt, 0)
	# the held money pays that charge: liability released, guest credited
	_transfer_to_guest(res, folio, dep, amt,
	                   f"Deposit applied to damage: {reason}")

	dep.withheld_amount = flt(dep.withheld_amount) + amt
	dep.reason = reason
	if evidence:
		dep.evidence = evidence
	dep.status = "Withheld"
	dep.save(ignore_permissions=True)
	from kamra.savings import log_action
	log_action("withhold_security_deposit", "Reservation", res.name,
	           res.property, rationale=f"Withheld {amt:,.2f}: {reason}")
	return deposit_state(res)


def _transfer_to_guest(res, folio: str, dep, amt: float, why: str) -> None:
	"""Held money leaves the Deposit ledger (liability) and credits the Guest
	ledger - it is paying something on the bill."""
	from kamra.ledger import PAYMENT_CODES, write_ledger_entry
	code = PAYMENT_CODES["Security Deposit"][0]
	if not frappe.db.exists("Transaction Code", code):
		code = None
	for ledger, debit, credit in (("Deposit", amt, 0), ("Guest", 0, amt)):
		write_ledger_entry(
			property=res.property, folio=folio, ledger=ledger,
			debit=debit, credit=credit, description=why[:140],
			transaction_code=code,
			source_doctype="Security Deposit", source_name=dep.name)


def apply_held_to_bill(res) -> float:
	"""At check-out, once the folio is settled: whatever deposit is still
	held was used to pay the bill (the desk let it cover the balance rather
	than refunding it and taking a payment). Record that, so the Deposit
	ledger does not carry a liability for a guest who has left."""
	if not _has_doctype():
		return 0.0
	name = frappe.db.get_value(
		"Security Deposit", {"reservation": res.name}, "name")
	if not name:
		return 0.0
	dep = frappe.get_doc("Security Deposit", name)
	amt = flt(dep.balance)
	if amt <= 0.009:
		return 0.0
	folio = _guest_folio(res)
	if not folio:
		return 0.0
	_transfer_to_guest(res, folio, dep, amt, "Deposit applied to the bill")
	dep.withheld_amount = flt(dep.withheld_amount) + amt
	dep.reason = "\n".join(filter(None, [  # nosemgrep: frappe-no-functional-code -- drops an empty previous reason
		dep.reason, _("Applied to the bill at check-out")]))
	dep.status = "Withheld"
	dep.save(ignore_permissions=True)
	from kamra.savings import log_action
	log_action("apply_security_deposit", "Reservation", res.name,
	           res.property,
	           rationale=f"Held deposit {amt:,.2f} applied to the bill at check-out")
	return amt


def refund_deposit(reservation: str, amount: float | None = None,
                   mode: str | None = None, note: str | None = None,
                   pin: str | None = None) -> dict:
	"""Give back what is still held, through the folio's refund writer."""
	res = _reservation(reservation)
	dep = _get(res.name)
	bal = flt(dep.balance)
	amt = flt(amount) if amount not in (None, "", 0, "0") else bal
	if amt <= 0:
		frappe.throw(_("Nothing is held to refund."))
	if amt > bal + 0.009:
		frappe.throw(_("Only {0:,.2f} of the deposit is still held.")
		             .format(bal))
	folio = _guest_folio(res)
	if not folio:
		frappe.throw(_("No guest folio for this stay."))
	# the deposit can only come back out of the guest's credit - if the
	# folio still owes money, settle or withhold first (also stops a deposit
	# that went back through the folio's own refund form going back twice)
	credit = -flt(frappe.db.get_value("Folio", folio, "balance"))
	if amt > credit + 0.009:
		frappe.throw(_(
			"The guest folio only has {0:,.2f} in credit. Settle the bill "
			"or withhold against it before refunding the deposit.")
			.format(max(credit, 0)))
	mode = mode or _last_mode(folio) or "Cash"
	from kamra.localization import pack_for, payment_modes
	modes = payment_modes(pack_for(res.property))
	if mode not in modes:
		frappe.throw(_("Pick a payment mode: {0}.").format(", ".join(modes)))
	text = f"{REFUND_REASON} {dep.name}"
	if (note or "").strip():
		text += f": {note.strip()}"
	from kamra.api import _refund_folio_payment
	_refund_folio_payment(folio, amt, mode, text[:140], pin=pin,
	                      ledger="Deposit")

	dep.refunded_amount = flt(dep.refunded_amount) + amt
	dep.refund_reference = text[:140]
	dep.balance = max(0.0, flt(dep.collected_amount) - flt(dep.withheld_amount)
	                  - flt(dep.refunded_amount))
	_settle_status(dep, res)
	dep.save(ignore_permissions=True)
	from kamra.savings import log_action
	log_action("refund_security_deposit", "Reservation", res.name,
	           res.property, rationale=f"{mode} deposit refund {amt:,.2f}")
	return deposit_state(res)


def _last_mode(folio: str) -> str | None:
	return frappe.db.get_value(
		"Folio Payment",
		{"parent": folio, "payment_kind": "Security Deposit"},
		"mode", order_by="idx desc")


def deposit_state(res) -> dict:
	"""What the deposit panel shows: the policy, what is held, what came
	out, and which actions are open right now."""
	if isinstance(res, str):
		res = frappe.get_doc("Reservation", res)
	policy = _policy_amount(res.property)
	row = frappe.db.get_value(
		"Security Deposit", {"reservation": res.name},
		["name", "status", "required_amount", "collected_amount",
		 "withheld_amount", "refunded_amount", "balance", "reason",
		 "refund_reference"], as_dict=True) if _has_doctype() else None
	folio = frappe.db.get_value(
		"Folio", {"reservation": res.name, "folio_type": "Guest"},
		["name", "status", "balance"], as_dict=True)
	status = row.status if row else ("Required" if policy > 0 else "None")
	held = flt(row.balance) if row else 0.0
	collected = flt(row.collected_amount) if row else 0.0
	required = flt(row.required_amount) if row else policy
	folio_open = bool(folio and folio.status != "Closed")
	in_play = res.status in COLLECT_STATUSES
	history = []
	if folio:
		for p in frappe.get_all(
				"Folio Payment",
				filters={"parent": folio.name, "parenttype": "Folio"},
				fields=["posting_date", "payment_kind", "mode", "amount",
				        "reference"], order_by="idx asc"):
			if p.payment_kind == "Security Deposit":
				history.append({"kind": "Collected", "date": str(p.posting_date),
				                "mode": p.mode, "amount": flt(p.amount)})
			elif p.payment_kind == "Refund" and \
					(p.reference or "").startswith(REFUND_REASON):
				history.append({"kind": "Refunded", "date": str(p.posting_date),
				                "mode": p.mode, "amount": -flt(p.amount)})
		for c in frappe.get_all(
				"Folio Charge",
				filters={"parent": folio.name, "parenttype": "Folio",
				         "description": ("like", f"{WITHHOLD_PREFIX}%")},
				fields=["posting_date", "description", "amount"],
				order_by="idx asc"):
			history.append({"kind": "Withheld", "date": str(c.posting_date),
			                "amount": flt(c.amount),
			                "note": c.description.split(":", 1)[-1].strip()})
	return {
		"name": row.name if row else None,
		"status": status,
		"policy_amount": policy,
		"required": required,
		"collected": collected,
		"withheld": flt(row.withheld_amount) if row else 0.0,
		"refunded": flt(row.refunded_amount) if row else 0.0,
		"held": held,
		"due": max(0.0, round(required - collected, 2))
			if status not in ("Waived", "Refunded") else 0.0,
		"reason": row.reason if row else None,
		"folio": folio.name if folio else None,
		"folio_credit": max(0.0, -flt(folio.balance)) if folio else 0.0,
		"history": history,
		"can_collect": in_play and status not in ("Waived", "Refunded"),
		"can_waive": in_play and collected <= 0 and status != "Waived"
			and required > 0,
		"can_withhold": held > 0 and folio_open,
		"can_refund": held > 0 and folio_open,
		# check-out refuses while the guest is owed money: a held deposit
		# has to be withheld or refunded first
		"blocks_checkout": res.status == "Checked In" and held > 0.009
			and folio_open and -flt(folio.balance) > 0.009,
	}


def deposit_satisfied(reservation: str) -> bool:
	"""True when deposit policy is met (none required, waived, or collected)."""
	required = _policy_amount(
		frappe.db.get_value("Reservation", reservation, "property"))
	if required <= 0:
		return True
	if not _has_doctype():
		return True
	row = frappe.db.get_value(
		"Security Deposit",
		{"reservation": reservation},
		["status", "collected_amount", "required_amount"],
		as_dict=True,
	)
	if not row:
		return False
	if row.status == "Waived":
		return True
	return flt(row.collected_amount) + 0.01 >= flt(row.required_amount)
