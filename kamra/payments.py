"""Payment Links for folio settlement.

Lightweight by design: one REST call out, one webhook in. Which gateways a
property may use is its country pack's call (India: Razorpay, Cashfree);
this module decides what a link is for and posts the money, and never
speaks a gateway's API itself.
"""

import frappe
from frappe.utils import nowdate

from kamra.authz import require_roles


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
	from kamra import localization as loc

	folio = frappe.get_doc("Folio", folio_name)
	if folio.status == "Closed":
		frappe.throw("Folio is closed.")
	amount = float(amount) if amount else float(folio.balance or 0)
	if amount <= 0:
		frappe.throw("Nothing due on this folio.")
	pack = loc.pack_for(folio.property)
	if not loc.payment_gateways(pack):
		frappe.throw("Online payment links are not available for this property's country.")
	settings = _settings(folio.property)
	guest = frappe.get_doc("Guest", folio.guest)
	currency = frappe.get_cached_value("Property", folio.property,
	                                   "currency") or loc.default_currency(pack)

	if settings.test_mode:
		# local demo: fake link, settle via the webhook simulator
		link_id = f"plink_TEST{frappe.generate_hash(length=10)}"
		url = loc.test_gateway_link(pack, settings.gateway, link_id)
	else:
		link_id, url = loc.create_gateway_link(
			pack, settings,
			amount=amount,
			currency=currency.upper(),
			reference=folio.name,
			description=f"{purpose} {folio.name} · {folio.guest_name}",
			customer={"name": guest.full_name, "contact": guest.phone or "",
			          "email": guest.email or ""},
			notes={"folio": folio.name, "property": folio.property},
		)

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


def handle_webhook(gateway: str, payload: bytes, headers: dict) -> dict:
	"""Settle a gateway's "link paid" event. Idempotent: a retried event
	never posts the same payment twice. A bad signature raises."""
	from kamra import localization as loc

	paid = loc.parse_payment_webhook(gateway, payload, headers, _settings)
	if not paid:
		return {"ignored": True}
	posted = settle_payment_link(paid["folio"], paid["link_id"], paid["amount"])
	return {"ok": True, "folio": paid["folio"], "posted": posted}


def _webhook(gateway: str) -> dict:
	headers = {k.lower(): v for k, v in (frappe.request.headers or {}).items()}
	out = handle_webhook(gateway, frappe.request.get_data() or b"{}", headers)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional
	return out


@frappe.whitelist(allow_guest=True, methods=["POST"])
def razorpay_webhook():
	"""Razorpay calls this on payment_link.paid. Point the webhook at
	/api/method/kamra.payments.razorpay_webhook"""
	return _webhook("Razorpay")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def cashfree_webhook():
	"""Cashfree posts here for every link (set per link as notify_url)."""
	return _webhook("Cashfree")


@frappe.whitelist()
@require_roles("Hotel Admin", "Finance")
def gateway_info(property: str, gateway: str = "") -> dict:
	"""What the Payments settings card shows beside the keys: where the
	gateway reports payments, and where to open an account."""
	from kamra import localization as loc

	pack = loc.pack_for(property)
	if not gateway:
		gateway = frappe.db.get_value("Payment Gateway Settings",
		                              {"property": property}, "gateway") \
			or (loc.payment_gateways(pack) or [""])[0]
	return loc.gateway_info(pack, gateway)
