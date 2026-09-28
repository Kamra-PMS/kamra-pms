"""Razorpay Payment Links for folio settlement.

Lightweight by design: one REST call out, one webhook in. For multi-
gateway needs later, swap in the frappe/payments app — this module is
the only place that knows about Razorpay.
"""

import hashlib
import hmac
import json

import frappe
from frappe.utils import nowdate

RAZORPAY_API = "https://api.razorpay.com/v1/payment_links"


def _settings(property: str):
	name = frappe.db.get_value(
		"Payment Gateway Settings", {"property": property, "enabled": 1})
	if not name:
		frappe.throw(
			"No payment gateway configured for this property. "
			"Add API keys under Payment Gateway Settings."
		)
	return frappe.get_doc("Payment Gateway Settings", name)


def create_payment_link(folio_name: str, amount: float | None = None,
                        purpose: str = "Stay bill") -> dict:
	"""A link for the folio's balance - or, before arrival, for an explicit
	amount (a booking deposit), when the folio has no charges yet."""
	folio = frappe.get_doc("Folio", folio_name)
	if folio.status == "Closed":
		frappe.throw("Folio is closed.")
	amount = float(amount) if amount else float(folio.balance or 0)
	if amount <= 0:
		frappe.throw("Nothing due on this folio.")
	settings = _settings(folio.property)
	guest = frappe.get_doc("Guest", folio.guest)
	currency = frappe.get_cached_value("Property", folio.property,
	                                   "currency") or "INR"

	if settings.test_mode:
		# local demo: fake link, settle via the webhook simulator
		link_id = f"plink_TEST{frappe.generate_hash(length=10)}"
		url = f"https://rzp.io/test/{link_id}"
	else:
		# production: route through the frappe/payments app — supports
		# Razorpay today; Stripe/PayPal/Paytm/Braintree by configuring
		# their Settings and switching `gateway` here.
		from payments.utils import get_payment_gateway_controller

		controller = get_payment_gateway_controller(settings.gateway)
		url = controller.get_payment_url(**{
			"amount": amount,
			"currency": currency,
			"title": f"{purpose} {folio.name}",
			"description": f"{folio.guest_name} · {folio.reservation}",
			"reference_doctype": "Folio",
			"reference_docname": folio.name,
			"payer_name": guest.full_name,
			"payer_email": guest.email or "",
			"order_id": folio.name,
		})
		link_id = folio.name

	folio.db_set("payment_link_id", link_id, update_modified=False)
	folio.db_set("payment_link_url", url, update_modified=False)
	folio.db_set("payment_link_amount", amount, update_modified=False)

	from kamra.savings import log_action
	log_action("send_payment_link", "Folio", folio.name, folio.property,
	           minutes_saved=4,
	           rationale=f"{purpose} link {currency} {amount:,.0f} for {guest.full_name}",
	           channel="API")
	return {"url": url, "link_id": link_id, "amount": amount,
	        "currency": currency, "test_mode": bool(settings.test_mode)}


def settle_payment_link(folio_name: str, link_id: str, amount: float) -> bool:
	"""Post money received through a link, once per link payment. Money that
	arrives before the guest does is an Advance on the booking: it counts
	toward the deposit and confirms a held booking."""
	folio = frappe.get_doc("Folio", folio_name)
	if amount <= 0 or any(p.reference == link_id for p in folio.payments):
		return False
	res = frappe.get_doc("Reservation", folio.reservation) \
		if folio.reservation else None
	pre_arrival = bool(res and res.status in (
		"Confirmed", "Pending Payment", "Held"))
	folio.append("payments", {
		"posting_date": nowdate(),
		"payment_kind": "Advance" if pre_arrival else "Payment",
		"mode": "Payment Link",
		"amount": amount,
		"reference": link_id,
	})
	from kamra.folio import _recalculate
	_recalculate(folio)
	folio.save(ignore_permissions=True)
	try:
		from kamra.ledger import record_payment_ledger
		record_payment_ledger(folio, folio.payments[-1].as_dict())
	except Exception:
		frappe.log_error(title="ledger payment-link write failed")
	if pre_arrival:
		frappe.db.set_value("Reservation", res.name, "advance_paid",
		                    float(res.advance_paid or 0) + amount)
		if res.status in ("Pending Payment", "Held"):
			from kamra.api import _confirm_status
			_confirm_status(res)
	from kamra.savings import log_action
	log_action("payment_received", "Folio", folio.name, folio.property,
	           minutes_saved=3,
	           rationale=f"{amount:,.0f} {'deposit ' if pre_arrival else ''}"
	                     f"auto-posted from payment link",
	           agent_name="Payments", channel="API")
	return True


@frappe.whitelist(allow_guest=True, methods=["POST"])
def razorpay_webhook():
	"""Razorpay calls this on payment_link.paid. Point the webhook at
	/api/method/kamra.payments.razorpay_webhook"""
	payload = frappe.request.get_data() or b"{}"
	event = json.loads(payload)

	entity = (event.get("payload", {}).get("payment_link", {})
	          .get("entity", {}))
	folio_name = (entity.get("notes") or {}).get("folio")
	if event.get("event") != "payment_link.paid" or not folio_name:
		return {"ignored": True}

	property = frappe.db.get_value("Folio", folio_name, "property")
	if not property:
		return {"ignored": True}
	settings = _settings(property)

	# Always verify - test mode too (Razorpay signs test webhooks). With no
	# webhook secret configured there is nothing to verify against, so the
	# call is refused rather than trusted.
	secret = settings.get_password("webhook_secret", raise_exception=False)
	given = frappe.get_request_header("X-Razorpay-Signature") or ""
	expected = hmac.new((secret or "").encode(), payload,
	                    hashlib.sha256).hexdigest()
	if not secret or not hmac.compare_digest(given, expected):
		frappe.throw("Invalid webhook signature", frappe.PermissionError)

	folio = frappe.get_doc("Folio", folio_name)

	amount = float(entity.get("amount_paid") or entity.get("amount") or 0) / 100
	posted = settle_payment_link(folio.name, entity.get("id"), amount)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional
	return {"ok": True, "folio": folio.name, "posted": posted}
