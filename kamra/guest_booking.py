"""AI guest booking (#228): an outside AI assistant books a stay for a guest.

The `guest.booking` service-account scope (kamra.service_accounts) opens
these five MCP tools and nothing else - no staff data, no other guest. They
run the booking engine's own code (kamra.public_api), so availability,
prices and the payment policy are the property's, never the model's:

- search: what is free for the dates, with real quoted totals per plan;
- hold: a Website booking. With nothing due now (pay at the hotel) the
  property's policy confirms it at once; with an advance due it is Pending
  Payment until hold_expires_on, after which the hold job releases it;
- payment link: the advance still due, through the property's gateway.
  Paid, the gateway webhook confirms the booking (payments.settle_payment_link);
- confirm: confirms only when the policy is met (paid, or nothing due);
- status: where the booking stands.

A key sees only the bookings it made itself (its hold is on the Agent
Action Log), and each key is throttled per hour.
"""

from __future__ import annotations

import frappe
from frappe import _

from kamra.authz import require_roles
from kamra.service_accounts import ROLE

HOLD_ACTION = "guest_ai_hold"
# calls per key per hour: generous for one assistant, a wall for a loop
LIMITS = {"search": 120, "hold": 20, "pay": 30, "read": 240}


def _throttle(kind: str) -> None:
	key = f"kamra:guest_booking:{kind}:{frappe.session.user}"
	n = frappe.cache.incrby(key, 1)
	if n == 1:
		frappe.cache.expire(key, 3600)
	if n > LIMITS[kind]:
		frappe.throw(_("Too many requests - try again within the hour."),
		             frappe.RateLimitExceededError)


def _own_booking(reservation: str):
	"""The reservation, if this key made it; else the same refusal as an
	unknown one, so a key can't probe other guests' bookings."""
	if not frappe.db.exists("Agent Action Log", {
			"action_type": HOLD_ACTION, "reference_doctype": "Reservation",
			"reference_name": reservation, "actor": frappe.session.user}):
		frappe.throw(_("No booking {0} made through this connection.").format(reservation),
		             frappe.DoesNotExistError)
	return frappe.get_doc("Reservation", reservation)


def _status(res) -> dict:
	"""Only the guest's own booking: dates, room type, money, state."""
	due = round(max(0.0, float(res.advance_due or 0) - float(res.advance_paid or 0)), 2)
	return {
		"reservation": res.name, "status": res.status,
		"confirmed": res.status == "Confirmed",
		"room_type": res.room_type, "check_in_date": str(res.check_in_date),
		"check_out_date": str(res.check_out_date),
		"amount_after_tax": float(res.amount_after_tax or 0),
		"advance_due": float(res.advance_due or 0),
		"advance_paid": float(res.advance_paid or 0), "still_due_now": due,
		"payment_policy": res.get("payment_policy"),
		"hold_expires_on": str(res.hold_expires_on) if res.hold_expires_on else None,
	}


@frappe.whitelist()
@require_roles(ROLE)
def search(property: str, check_in_date: str, check_out_date: str,
           adults: int = 2, children: int = 0, child_ages=None,
           voucher_code: str | None = None):
	"""Room types free for the stay, each with the real quoted total per
	meal plan and what is due now under the property's payment policy."""
	_throttle("search")
	from kamra.public_api import search_stay
	return search_stay(property, check_in_date, check_out_date, adults=adults,
	                   children=children, child_ages=child_ages,
	                   voucher_code=voucher_code)


@frappe.whitelist(methods=["POST"])
@require_roles(ROLE)
def hold(property: str, room_type: str, check_in_date: str, check_out_date: str,
         guest_name: str, phone: str, email: str = "", adults: int = 2,
         children: int = 0, child_ages=None, meal_plan: str = "",
         special_requests: str = "", voucher_code: str = "",
         idempotency_key: str = ""):
	"""Book the stay for the guest. Pay-at-hotel properties confirm it at
	once; with an advance due it is held (Pending Payment) until
	hold_expires_on - send the payment link before then."""
	_throttle("hold")
	from kamra.public_api import book
	# the booking engine's own writer, without its per-IP web limit (every
	# MCP call comes from one server): _throttle limits this key instead
	out = book.__wrapped__(
		property, room_type, check_in_date, check_out_date, guest_name, phone,
		email=email, adults=adults, children=children, child_ages=child_ages,
		meal_plan=meal_plan, special_requests=special_requests,
		voucher_code=voucher_code, idempotency_key=idempotency_key)
	from kamra.savings import log_action
	log_action(HOLD_ACTION, "Reservation", out["reservation"], property,
	           rationale=f"AI guest booking {out['status']}", channel="API",
	           agent_name="Guest assistant")
	res = frappe.get_doc("Reservation", out["reservation"])
	return {**_status(res), "needs_confirmation": out.get("needs_confirmation"),
	        "confirmation_reason": out.get("confirmation_reason"),
	        "idempotent_replay": out.get("idempotent_replay")}


@frappe.whitelist(methods=["POST"])
@require_roles(ROLE)
def payment_link(reservation: str):
	"""A payment link for the advance still due on this booking."""
	_throttle("pay")
	res = _own_booking(reservation)
	state = _status(res)
	if res.status not in ("Pending Payment", "Held", "Confirmed"):
		frappe.throw(_("This booking is {0}.").format(_(res.status).lower()))
	if state["still_due_now"] <= 0:
		frappe.throw(_("Nothing is due now - the rest is paid at the hotel."))
	from kamra.folio import open_folio
	from kamra.payments import create_payment_link
	link = create_payment_link(open_folio(res), amount=state["still_due_now"],
	                           purpose="Booking deposit")
	return {**state, "url": link["url"], "amount": link["amount"],
	        "currency": link["currency"]}


@frappe.whitelist(methods=["POST"])
@require_roles(ROLE)
def confirm(reservation: str):
	"""Confirm the booking - only once the property's policy is met: the
	advance is paid, or nothing was due now. Never on the model's say-so."""
	_throttle("read")
	res = _own_booking(reservation)
	if res.status == "Confirmed":
		return _status(res)
	if res.status not in ("Pending Payment", "Held"):
		frappe.throw(_("This booking is {0}.").format(_(res.status).lower()))
	if _status(res)["still_due_now"] > 0.005:
		frappe.throw(_("The advance isn't paid yet - send the payment link."))
	from kamra.api import _confirm_status
	_confirm_status(res)
	return _status(res)


@frappe.whitelist()
@require_roles(ROLE)
def status(reservation: str):
	"""Where a booking this connection made stands."""
	_throttle("read")
	return _status(_own_booking(reservation))

