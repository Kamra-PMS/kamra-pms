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


def create_payment_link(folio_name: str) -> dict:
	folio = frappe.get_doc("Folio", folio_name)
	if folio.status == "Closed":
		frappe.throw("Folio is closed.")
	if (folio.balance or 0) <= 0:
		frappe.throw("Nothing due on this folio.")
	settings = _settings(folio.property)
	guest = frappe.get_doc("Guest", folio.guest)
	amount_paise = int(round(float(folio.balance) * 100))

	if settings.test_mode:
		link_id = f"plink_TEST{frappe.generate_hash(length=10)}"
		url = f"https://rzp.io/test/{link_id}"
	else:
		import requests

		resp = requests.post(
			RAZORPAY_API,
			auth=(settings.key_id,
			      settings.get_password("key_secret")),
			json={
				"amount": amount_paise,
				"currency": "INR",
				"description": f"Stay bill {folio.name}",
				"customer": {
					"name": guest.full_name,
					"contact": guest.phone or "",
					"email": guest.email or "",
				},
				"notify": {"sms": bool(guest.phone), "email": bool(guest.email)},
				"notes": {"folio": folio.name, "property": folio.property},
			},
			timeout=20,
		)
		if not resp.ok:
			frappe.throw(f"Razorpay error: {resp.text[:300]}")
		data = resp.json()
		link_id, url = data["id"], data["short_url"]

	folio.db_set("payment_link_id", link_id, update_modified=False)
	folio.db_set("payment_link_url", url, update_modified=False)

	from kamra.savings import log_action
	log_action("send_payment_link", "Folio", folio.name, folio.property,
	           minutes_saved=4,
	           rationale=f"Payment link ₹{folio.balance:,.0f} for {guest.full_name}",
	           channel="API")
	return {"url": url, "link_id": link_id, "amount": float(folio.balance),
	        "test_mode": bool(settings.test_mode)}


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

	folio = frappe.get_doc("Folio", folio_name)
	settings = _settings(folio.property)

	# verify signature when a webhook secret is configured (skip in test mode)
	secret = settings.get_password("webhook_secret", raise_exception=False)
	if secret and not settings.test_mode:
		given = frappe.get_request_header("X-Razorpay-Signature") or ""
		expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
		if not hmac.compare_digest(given, expected):
			frappe.throw("Invalid webhook signature", frappe.PermissionError)

	amount = float(entity.get("amount_paid") or entity.get("amount") or 0) / 100
	already = any(p.reference == entity.get("id") for p in folio.payments)
	if not already and amount > 0:
		folio.append("payments", {
			"posting_date": nowdate(),
			"mode": "Payment Link",
			"amount": amount,
			"reference": entity.get("id"),
		})
		from kamra.folio import _recalculate
		_recalculate(folio)
		folio.save(ignore_permissions=True)
		from kamra.savings import log_action
		log_action("payment_received", "Folio", folio.name, folio.property,
		           minutes_saved=3,
		           rationale=f"₹{amount:,.0f} auto-posted from payment link",
		           agent_name="Payments", channel="API")
	frappe.db.commit()
	return {"ok": True, "folio": folio.name, "posted": not already}
