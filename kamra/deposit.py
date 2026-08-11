# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Security deposit liability lifecycle (ADR-009).

Deposits are stay-level liabilities — never accommodation revenue.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, nowdate


def ensure_deposit_for_reservation(reservation) -> str | None:
	"""Create a Required deposit row when Property policy asks for one."""
	if isinstance(reservation, str):
		reservation = frappe.get_doc("Reservation", reservation)
	if not frappe.db.exists("DocType", "Security Deposit"):
		return None
	existing = frappe.db.get_value(
		"Security Deposit", {"reservation": reservation.name}, "name"
	)
	if existing:
		return existing
	required = flt(
		frappe.db.get_value(
			"Property", reservation.property, "security_deposit_amount"
		)
		or 0
	)
	if required <= 0:
		return None
	doc = frappe.get_doc(
		{
			"doctype": "Security Deposit",
			"reservation": reservation.name,
			"property": reservation.property,
			"guest": reservation.guest,
			"status": "Required",
			"method": "payment",
			"required_amount": required,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def collect_deposit(
	reservation: str,
	amount: float,
	*,
	mode: str = "UPI",
	reference: str | None = None,
) -> dict:
	"""Collect deposit payment and post as Security Deposit on the folio."""
	dep_name = ensure_deposit_for_reservation(reservation)
	if not dep_name:
		frappe.throw(_("No security deposit is required for this stay."))
	dep = frappe.get_doc("Security Deposit", dep_name)
	if dep.status == "Waived":
		frappe.throw(_("Deposit was waived."))
	amt = flt(amount)
	if amt <= 0:
		frappe.throw(_("Collection amount must be positive."))

	res = frappe.get_doc("Reservation", reservation)
	from kamra.folio import _recalculate, open_folio

	folio = frappe.get_doc("Folio", open_folio(res))
	folio.append(
		"payments",
		{
			"posting_date": nowdate(),
			"mode": mode,
			"amount": amt,
			"payment_kind": "Security Deposit",
			"reference": reference or f"deposit:{reservation}",
		},
	)
	_recalculate(folio)
	folio.save(ignore_permissions=True)

	dep.collected_amount = flt(dep.collected_amount) + amt
	dep.method = "payment" if mode != "Cash" else "cash"
	if dep.collected_amount + 0.001 >= flt(dep.required_amount):
		dep.status = "Held" if res.status in ("Checked In",) else "Collected"
	else:
		dep.status = "Collected"
	dep.save(ignore_permissions=True)
	return {
		"deposit": dep.name,
		"status": dep.status,
		"collected_amount": dep.collected_amount,
		"balance": dep.balance,
		"folio": folio.name,
	}


def waive_deposit(reservation: str, reason: str) -> dict:
	dep_name = ensure_deposit_for_reservation(reservation)
	if not dep_name:
		frappe.throw(_("No deposit to waive."))
	dep = frappe.get_doc("Security Deposit", dep_name)
	dep.status = "Waived"
	dep.method = "waiver"
	dep.reason = reason
	dep.required_amount = 0
	dep.save(ignore_permissions=True)
	return {"deposit": dep.name, "status": dep.status}


def withhold_deposit(
	reservation: str,
	amount: float,
	reason: str,
	evidence: str | None = None,
) -> dict:
	dep = frappe.get_doc(
		"Security Deposit", {"reservation": reservation}
	)
	amt = flt(amount)
	if amt <= 0:
		frappe.throw(_("Withhold amount must be positive."))
	if not (reason or "").strip():
		frappe.throw(_("Withhold reason is required."))
	available = flt(dep.collected_amount) - flt(dep.withheld_amount) - flt(
		dep.refunded_amount
	)
	if amt > available + 0.01:
		frappe.throw(_("Cannot withhold more than the refundable balance."))
	dep.withheld_amount = flt(dep.withheld_amount) + amt
	dep.reason = reason
	if evidence:
		dep.evidence = evidence
	dep.status = "Withheld"
	dep.save(ignore_permissions=True)

	# Damage charge on folio (revenue), separate from deposit liability.
	res = frappe.get_doc("Reservation", reservation)
	from kamra.folio import _recalculate, open_folio

	folio = frappe.get_doc("Folio", open_folio(res))
	folio.append(
		"charges",
		{
			"posting_date": nowdate(),
			"charge_type": "Misc",
			"description": f"Damage / withhold: {reason}",
			"qty": 1,
			"rate": amt,
			"amount": amt,
			"gst_rate": 0,
			"auto_posted": 1,
		},
	)
	# Apply withheld deposit as payment against the damage charge.
	folio.append(
		"payments",
		{
			"posting_date": nowdate(),
			"mode": "Other",
			"amount": amt,
			"payment_kind": "Security Deposit",
			"reference": f"withhold:{dep.name}",
		},
	)
	_recalculate(folio)
	folio.save(ignore_permissions=True)
	return {
		"deposit": dep.name,
		"status": dep.status,
		"withheld_amount": dep.withheld_amount,
		"balance": dep.balance,
	}


def refund_deposit(
	reservation: str,
	amount: float | None = None,
	reference: str | None = None,
) -> dict:
	dep = frappe.get_doc(
		"Security Deposit", {"reservation": reservation}
	)
	bal = flt(dep.balance)
	amt = flt(amount if amount is not None else bal)
	if amt <= 0:
		frappe.throw(_("Nothing to refund."))
	if amt > bal + 0.01:
		frappe.throw(_("Refund exceeds refundable balance."))

	res = frappe.get_doc("Reservation", reservation)
	from kamra.folio import _recalculate, open_folio

	folio = frappe.get_doc("Folio", open_folio(res))
	folio.append(
		"payments",
		{
			"posting_date": nowdate(),
			"mode": "Other",
			"amount": -amt,
			"payment_kind": "Refund",
			"reference": reference or f"deposit-refund:{dep.name}",
		},
	)
	_recalculate(folio)
	folio.save(ignore_permissions=True)

	dep.refunded_amount = flt(dep.refunded_amount) + amt
	dep.refund_reference = reference or dep.refund_reference
	dep.status = "Refunded" if flt(dep.balance) <= 0.01 else dep.status
	if dep.status != "Refunded" and flt(dep.withheld_amount) > 0:
		dep.status = "Withheld"
	elif dep.status != "Refunded":
		dep.status = "Collected"
	dep.save(ignore_permissions=True)
	return {
		"deposit": dep.name,
		"status": dep.status,
		"refunded_amount": dep.refunded_amount,
		"balance": dep.balance,
		"folio": folio.name,
	}


def deposit_satisfied(reservation: str) -> bool:
	"""True when deposit policy is met (none required, waived, or collected)."""
	required = flt(
		frappe.db.get_value(
			"Property",
			frappe.db.get_value("Reservation", reservation, "property"),
			"security_deposit_amount",
		)
		or 0
	)
	if required <= 0:
		return True
	if not frappe.db.exists("DocType", "Security Deposit"):
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
