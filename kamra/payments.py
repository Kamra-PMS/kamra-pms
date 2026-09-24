"""Payment Links for folio settlement and booking advances, on Razorpay or
Cashfree.

Lightweight by design: one REST call out, one webhook in. Each property
uses its OWN gateway account (Payment Gateway Settings), so a group with
several properties settles each into the right bank account. This module
is the only place that knows about payment gateways.

Two kinds of link, told apart by the link's notes:
  notes.folio        a bill at the desk (create_payment_link)
  notes.reservation  a website booking's advance (create_advance_link):
                     paying it confirms the booking via record_advance.
"""

import base64
import hashlib
import hmac
import json
import re
import time
from datetime import datetime, timedelta, timezone

import frappe
from frappe.utils import get_datetime, get_url, nowdate

RAZORPAY_API = "https://api.razorpay.com/v1/payment_links"

# Where a property without a gateway account is sent to open one. These
# are Kamra's partner referral links: they cost the hotel nothing and help
# fund the project. A site can point them elsewhere with site config
# kamra_razorpay_signup_url / kamra_cashfree_signup_url.
RAZORPAY_SIGNUP_URL = "https://dashboard.razorpay.com/signup"
CASHFREE_SIGNUP_URL = "https://merchant.cashfree.com/merchants/signup"

CASHFREE_API_VERSION = "2025-01-01"
_IST = timezone(timedelta(hours=5, minutes=30))

# Razorpay refuses a link that expires sooner than this.
_MIN_EXPIRY_SECONDS = 16 * 60


def _settings(property: str):
	name = frappe.db.get_value(
		"Payment Gateway Settings", {"property": property, "enabled": 1})
	if not name:
		frappe.throw(
			"No payment gateway configured for this property. "
			"Add API keys under Payment Gateway Settings."
		)
	return frappe.get_doc("Payment Gateway Settings", name)


def gateway_ready(property: str) -> bool:
	"""True when this property can take money online right now."""
	name = frappe.db.get_value(
		"Payment Gateway Settings", {"property": property, "enabled": 1},
		["name", "test_mode", "key_id"], as_dict=True)
	return bool(name and (name.test_mode or name.key_id))


def _currency(property: str) -> str:
	return (frappe.db.get_value("Property", property, "currency") or "INR").upper()


def _razorpay_link(settings, *, amount: float, currency: str, reference: str,
                   description: str, customer: dict, notes: dict,
                   callback_url: str | None = None,
                   expire_by: int | None = None) -> tuple[str, str]:
	"""Create a live Payment Link on the property's own account.
	Returns (link id, short url)."""
	import requests

	secret = settings.get_password("key_secret", raise_exception=False)
	if not settings.key_id or not secret:
		frappe.throw("Razorpay key ID and secret are required for live payment links.")

	body = {
		"amount": int(round(float(amount) * 100)),
		"currency": currency,
		"accept_partial": False,
		# unique per merchant account; a folio can be re-linked, so stamp it
		"reference_id": f"{reference}-{int(time.time())}"[:40],
		"description": description[:2048],
		"customer": {k: v for k, v in customer.items() if v},
		"notify": {"sms": bool(customer.get("contact")),
		           "email": bool(customer.get("email"))},
		"reminder_enable": True,
		"notes": notes,
	}
	if callback_url:
		body["callback_url"] = callback_url
		body["callback_method"] = "get"
	if expire_by:
		body["expire_by"] = int(expire_by)

	resp = requests.post(RAZORPAY_API, json=body,
	                     auth=(settings.key_id, secret), timeout=20)
	if resp.status_code >= 400:
		try:
			reason = resp.json().get("error", {}).get("description")
		except ValueError:
			reason = None
		frappe.throw(f"Razorpay refused the payment link: {reason or resp.status_code}")
	data = resp.json()
	return data["id"], data["short_url"]


def _cashfree_link(settings, *, amount: float, currency: str, reference: str,
                   description: str, customer: dict, notes: dict,
                   callback_url: str | None = None,
                   expire_by: int | None = None) -> tuple[str, str]:
	"""Create a live Cashfree Payment Link on the property's own account.
	Cashfree posts the result to notify_url, so the hotel sets up no
	webhook. Test App IDs (TEST...) go to Cashfree's sandbox."""
	import requests

	secret = settings.get_password("key_secret", raise_exception=False)
	if not settings.key_id or not secret:
		frappe.throw("Cashfree App ID and secret key are required for live payment links.")
	phone = re.sub(r"\D", "", customer.get("contact") or "")
	if len(phone) < 10:
		frappe.throw("Cashfree needs the guest's mobile number to send a payment link. "
		             "Add it to the guest profile.")
	link_id = re.sub(r"[^A-Za-z0-9_-]", "-", f"{reference}-{int(time.time())}")[-50:]
	body = {
		"link_id": link_id,
		"link_amount": round(float(amount), 2),
		"link_currency": currency,
		"link_purpose": description[:500],
		"customer_details": {k: v for k, v in {
			"customer_name": customer.get("name"), "customer_email": customer.get("email"),
			"customer_phone": phone[-10:]}.items() if v},
		"link_notify": {"send_sms": True, "send_email": bool(customer.get("email"))},
		"link_auto_reminders": True,
		"link_notes": {k: str(v) for k, v in notes.items()},
		"link_meta": {"notify_url": get_url("/api/method/kamra.payments.cashfree_webhook")},
	}
	if callback_url:
		body["link_meta"]["return_url"] = callback_url
	if expire_by:
		body["link_expiry_time"] = datetime.fromtimestamp(int(expire_by), _IST).isoformat()
	base = ("https://sandbox.cashfree.com/pg" if settings.key_id.upper().startswith("TEST")
	        else "https://api.cashfree.com/pg")
	resp = requests.post(f"{base}/links", json=body, timeout=20, headers={
		"x-client-id": settings.key_id, "x-client-secret": secret,
		"x-api-version": CASHFREE_API_VERSION, "x-idempotency-key": link_id})
	if resp.status_code >= 400:
		try:
			reason = resp.json().get("message")
		except ValueError:
			reason = None
		frappe.throw(f"Cashfree refused the payment link: {reason or resp.status_code}")
	return link_id, resp.json()["link_url"]


def _gateway(settings) -> str:
	return "Cashfree" if (settings.gateway or "") == "Cashfree" else "Razorpay"


def _link(settings, **kw) -> tuple[str, str]:
	"""(link id, url) on whichever gateway this property uses."""
	if settings.test_mode:
		# local demo: fake link, settle via the webhook simulator
		link_id = f"plink_TEST{frappe.generate_hash(length=10)}"
		host = "payments.cashfree.com/links" if _gateway(settings) == "Cashfree" else "rzp.io"
		return link_id, f"https://{host}/test/{link_id}"
	make = _cashfree_link if _gateway(settings) == "Cashfree" else _razorpay_link
	return make(settings, **kw)


def create_payment_link(folio_name: str) -> dict:
	folio = frappe.get_doc("Folio", folio_name)
	if folio.status == "Closed":
		frappe.throw("Folio is closed.")
	if (folio.balance or 0) <= 0:
		frappe.throw("Nothing due on this folio.")
	settings = _settings(folio.property)
	guest = frappe.get_doc("Guest", folio.guest)

	link_id, url = _link(
		settings,
		amount=float(folio.balance),
		currency=_currency(folio.property),
		reference=folio.name,
		description=f"Stay bill {folio.name} · {folio.guest_name}",
		customer={"name": guest.full_name, "contact": guest.phone or "",
		          "email": guest.email or ""},
		notes={"folio": folio.name, "property": folio.property},
	)

	folio.db_set("payment_link_id", link_id, update_modified=False)
	folio.db_set("payment_link_url", url, update_modified=False)

	from kamra.savings import log_action
	log_action("send_payment_link", "Folio", folio.name, folio.property,
	           minutes_saved=4,
	           rationale=f"Payment link ₹{folio.balance:,.0f} for {guest.full_name}",
	           channel="API")
	return {"url": url, "link_id": link_id, "amount": float(folio.balance),
	        "test_mode": bool(settings.test_mode)}


def create_advance_link(reservation: str) -> dict | None:
	"""Payment link for what a website booking owes now (advance_due less
	anything already paid). Expires with the booking's hold, so an unpaid
	link can never confirm a room the hold has already released.
	Returns None when nothing is due or the property takes no online money."""
	res = frappe.get_doc("Reservation", reservation)
	due = round(float(res.advance_due or 0) - float(res.advance_paid or 0), 2)
	if due <= 0 or res.status not in ("Pending Payment", "Held") \
			or not gateway_ready(res.property):
		return None
	settings = _settings(res.property)
	guest = frappe.get_doc("Guest", res.guest)

	expire_by = None
	if res.hold_expires_on:
		expire_by = int(get_datetime(res.hold_expires_on).timestamp())
		# a hold that ends within the gateway's minimum still gets a link;
		# a payment that lands after release is caught by the webhook
		expire_by = max(expire_by, int(time.time()) + _MIN_EXPIRY_SECONDS)
	link_id, url = _link(
		settings,
		amount=due,
		currency=_currency(res.property),
		reference=res.name,
		description=f"Advance for booking {res.name}",
		customer={"name": guest.full_name, "contact": guest.phone or "",
		          "email": guest.email or ""},
		notes={"reservation": res.name, "property": res.property},
		callback_url=get_url(f"/book?reservation={res.name}&payment=done"),
		expire_by=expire_by,
	)

	from kamra.savings import log_action
	log_action("send_advance_link", "Reservation", res.name, res.property,
	           rationale=f"Online advance ₹{due:,.0f} for {guest.full_name}",
	           agent_name="Payments", channel="API")
	return {"url": url, "link_id": link_id, "amount": due,
	        "test_mode": bool(settings.test_mode)}


def _verify_signature(settings, payload: bytes, given: str):
	"""Live money needs a signed webhook. Test mode skips the check so the
	demo can settle links with a simulated call."""
	if settings.test_mode:
		return
	secret = settings.get_password("webhook_secret", raise_exception=False)
	if not secret:
		frappe.throw("Webhook secret is not configured for this property.",
		             frappe.PermissionError)
	given = given or ""
	expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
	if not hmac.compare_digest(given, expected):
		frappe.throw("Invalid webhook signature", frappe.PermissionError)


def _settle_advance(reservation: str, amount: float, link_id: str) -> dict:
	res = frappe.get_doc("Reservation", reservation)
	from kamra.savings import log_action

	already = frappe.db.exists("Folio Payment", {
		"parenttype": "Folio", "reference": link_id,
		"parent": ["in", frappe.get_all(
			"Folio", {"reservation": reservation}, pluck="name") or [""]],
	})
	if already:
		return {"ok": True, "reservation": reservation, "posted": False}

	if res.status not in ("Confirmed", "Checked In", "Pending Payment", "Held"):
		# the hold lapsed before the guest paid: the money is real but the
		# room may be gone, so a person decides (rebook or refund)
		log_action("late_advance_payment", "Reservation", reservation, res.property,
		           rationale=(f"₹{amount:,.0f} paid online after the booking was "
		                      f"{res.status.lower()}; rebook or refund "
		                      f"(payment link {link_id})"),
		           agent_name="Payments", channel="API")
		return {"ok": True, "reservation": reservation, "posted": False,
		        "needs_attention": True}

	from kamra.api import record_advance
	frappe.set_user("agent@kamra.local")  # governed writer, as public_api.book  # nosemgrep: frappe-setuser -- controlled user context switch for a signature-verified gateway callback
	try:
		out = record_advance(reservation, amount, mode="Payment Link",
		                     reference=link_id)
	finally:
		frappe.set_user("Guest")  # nosemgrep: frappe-setuser -- restore the anonymous webhook context
	return {"ok": True, "reservation": reservation, "posted": True,
	        "folio": out["folio"], "status": out["status"]}


def _settle_folio(folio_name: str, amount: float, link_id: str) -> dict:
	folio = frappe.get_doc("Folio", folio_name)
	already = any(p.reference == link_id for p in folio.payments)
	if not already and amount > 0:
		folio.append("payments", {
			"posting_date": nowdate(),
			"mode": "Payment Link",
			"amount": amount,
			"reference": link_id,
		})
		from kamra.folio import _recalculate
		_recalculate(folio)
		folio.save(ignore_permissions=True)
		from kamra.savings import log_action
		log_action("payment_received", "Folio", folio.name, folio.property,
		           minutes_saved=3,
		           rationale=f"₹{amount:,.0f} auto-posted from payment link",
		           agent_name="Payments", channel="API")
	return {"ok": True, "folio": folio.name, "posted": not already}


def handle_webhook(payload: bytes, signature: str = "") -> dict:
	"""Settle a Razorpay payment_link.paid event. Idempotent: a retried
	event never posts the same payment twice."""
	event = json.loads(payload or b"{}")

	entity = (event.get("payload", {}).get("payment_link", {})
	          .get("entity", {}))
	notes = entity.get("notes") or {}
	folio_name = notes.get("folio")
	reservation = notes.get("reservation")
	if event.get("event") != "payment_link.paid" or not (folio_name or reservation):
		return {"ignored": True}

	if reservation:
		if not frappe.db.exists("Reservation", reservation):
			return {"ignored": True}
		property = frappe.db.get_value("Reservation", reservation, "property")
	else:
		if not frappe.db.exists("Folio", folio_name):
			return {"ignored": True}
		property = frappe.db.get_value("Folio", folio_name, "property")

	_verify_signature(_settings(property), payload, signature)

	amount = float(entity.get("amount_paid") or entity.get("amount") or 0) / 100
	return _settle(folio_name, reservation, amount, entity.get("id") or "")


def _settle(folio_name: str | None, reservation: str | None, amount: float, link_id: str) -> dict:
	if reservation:
		return _settle_advance(reservation, amount, link_id) if amount > 0 \
			else {"ok": True, "posted": False}
	return _settle_folio(folio_name, amount, link_id)


def _link_owner(notes: dict) -> tuple[str | None, str | None, str | None]:
	"""(folio, reservation, property) named in a link's notes, if they exist."""
	folio_name, reservation = notes.get("folio"), notes.get("reservation")
	if reservation and frappe.db.exists("Reservation", reservation):
		return None, reservation, frappe.db.get_value("Reservation", reservation, "property")
	if folio_name and frappe.db.exists("Folio", folio_name):
		return folio_name, None, frappe.db.get_value("Folio", folio_name, "property")
	return None, None, None


def handle_cashfree_webhook(payload: bytes, signature: str = "", timestamp: str = "") -> dict:
	"""Settle a Cashfree PAYMENT_LINK_EVENT that says PAID. Signed with the
	property's own secret key: base64(HMAC-SHA256(timestamp + raw body)).
	Idempotent on the link id, like the Razorpay path."""
	event = json.loads(payload or b"{}")
	data = event.get("data") or {}
	if event.get("type") != "PAYMENT_LINK_EVENT" or data.get("link_status") != "PAID":
		return {"ignored": True}
	folio_name, reservation, property = _link_owner(data.get("link_notes") or {})
	if not property:
		return {"ignored": True}

	settings = _settings(property)
	if not settings.test_mode:
		secret = settings.get_password("key_secret", raise_exception=False)
		if not secret:
			frappe.throw("Cashfree secret key is not configured for this property.",
			             frappe.PermissionError)
		expected = base64.b64encode(hmac.new(
			secret.encode(), (timestamp or "").encode() + (payload or b""),
			hashlib.sha256).digest()).decode()
		if not hmac.compare_digest(signature or "", expected):
			frappe.throw("Invalid webhook signature", frappe.PermissionError)

	amount = float(data.get("link_amount_paid") or data.get("link_amount") or 0)
	return _settle(folio_name, reservation, amount, data.get("link_id") or "")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def razorpay_webhook():
	"""Razorpay calls this on payment_link.paid. Point the webhook at
	/api/method/kamra.payments.razorpay_webhook"""
	out = handle_webhook(frappe.request.get_data() or b"{}",
	                     frappe.get_request_header("X-Razorpay-Signature") or "")
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional
	return out


@frappe.whitelist(allow_guest=True, methods=["POST"])
def cashfree_webhook():
	"""Cashfree posts here for every link (set per link as notify_url)."""
	out = handle_cashfree_webhook(frappe.request.get_data() or b"{}",
	                              frappe.get_request_header("x-webhook-signature") or "",
	                              frappe.get_request_header("x-webhook-timestamp") or "")
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional
	return out


@frappe.whitelist()
def gateway_info(property: str, gateway: str = "") -> dict:
	"""What the Payments settings card needs beyond the doc itself."""
	if not gateway:
		gateway = frappe.db.get_value("Payment Gateway Settings", {"property": property},
		                              "gateway") or "Razorpay"
	if gateway == "Cashfree":
		return {
			"gateway": "Cashfree",
			"webhook_url": get_url("/api/method/kamra.payments.cashfree_webhook"),
			"signup_url": frappe.conf.get("kamra_cashfree_signup_url") or CASHFREE_SIGNUP_URL,
			"needs_webhook": False,
			"ready": gateway_ready(property),
		}
	return {
		"gateway": "Razorpay",
		"webhook_url": get_url("/api/method/kamra.payments.razorpay_webhook"),
		"signup_url": frappe.conf.get("kamra_razorpay_signup_url") or RAZORPAY_SIGNUP_URL,
		"needs_webhook": True,
		"ready": gateway_ready(property),
	}
