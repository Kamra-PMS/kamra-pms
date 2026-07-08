"""The Kamra Marketplace: what's in your plan, and what you can plug in.

Three kinds of card, three install models - never conflated:

  module     a Kamra app that ships in this codebase, open and included
             (no install, no lock).
  connector  a live integration backed by a config row (a channel, a payment
             gateway, an AI key) - the card connects/configures it here.
  bench_app  a separate Frappe app you install on the bench (country packs,
             the ERPNext accounting bridge) - the card shows honest
             `bench get-app` instructions, never a fake button.
"""

import frappe

from kamra.authz import require_roles


def _channel_status(property: str, provider: str, channel: str):
	row = frappe.db.get_value(
		"Channel Provider Connection",
		{"property": property, "provider": provider, "channel": channel,
		 "active": 1},
		["name", "phone_number"], as_dict=True)
	if row:
		return {"status": "connected", "detail": row.phone_number,
		        "connection": row.name}
	return {"status": "available"}


@frappe.whitelist()
@require_roles("Hotel Admin", "System Manager")
def registry(property: str):
	"""Everything on offer, grouped, with this property's live status."""
	ai = frappe.db.get_value(
		"AI Assistant Settings", {"property": property}, "enabled")
	pay = frappe.db.get_value(
		"Payment Gateway Settings", {"property": property}, "enabled")
	me = frappe.session.user
	has_key = bool(frappe.db.get_value("User", me, "api_key"))

	return [
		{
			"category": "Kamra apps",
			"blurb": "The rooms of your PMS - every app is open and included.",
			"cards": [
				_module("Front Desk", "Reservations, arrivals, the desk."),
				_module("Housekeeping", "Room board and the phone app."),
				_module("Operations", "Guest requests and shifts."),
				_module("Finance", "Folios, invoices, night audit."),
				_module("Copilot", "Chat with your PMS using your own AI key."),
				_module("Events & Groups", "Banquets, blocks and pickup."),
				_module("Revenue", "Rates, seasons, offers, partners."),
				_module("POS", "Restaurant & outlet billing.", planned=True),
			],
		},
		{
			"category": "Channels",
			"blurb": "Let guests reach you on voice and WhatsApp - answered by "
			         "your AI, logged like any staff action.",
			"cards": [
				_connector("HeyKoala Voice AI", "heykoala",
				           "A phone number your AI concierge answers - books, "
				           "quotes, answers, 24x7.",
				           action="heykoala", channel="Voice",
				           **_channel_status(property, "HeyKoala", "Voice")),
				_connector("HeyKoala WhatsApp", "heykoala",
				           "A WhatsApp concierge for confirmations, pre-arrival "
				           "check-in and requests.",
				           action="heykoala", channel="WhatsApp",
				           **_channel_status(property, "HeyKoala", "WhatsApp")),
				_connector("Twilio / Meta Business", "twilio",
				           "Bring your own telephony or WhatsApp Business.",
				           status="planned"),
			],
		},
		{
			"category": "Distribution",
			"blurb": "Sync rates and availability across OTAs. Delivered as an "
			         "enterprise integration tailored to your channel mix.",
			"cards": [
				_enterprise("Channel Manager",
				            "Two-way OTA sync (Booking.com, MakeMyTrip, Agoda "
				            "and more) via a channel-manager partner - scoped "
				            "and connected for your property."),
			],
		},
		{
			"category": "AI",
			"blurb": "Bring your own model, or your own Claude.",
			"cards": [
				_connector("Claude Desktop", "claude",
				           "Connect Claude to this hotel with your own access - "
				           "it acts as you.",
				           action="route", route="/assistant",
				           status="connected" if has_key else "available",
				           detail="Your connector" if has_key else None),
				_connector("OpenAI key", "openai",
				           "Power NOVA with your own OpenAI key.",
				           action="route", route="/settings",
				           status="connected" if ai else "configure"),
			],
		},
		{
			"category": "Payments",
			"blurb": "Take deposits and settle bills online.",
			"cards": [
				_connector("Razorpay", "razorpay",
				           "Payment links for balances and advances.",
				           action="route", route="/settings",
				           status="connected" if pay else "configure"),
			],
		},
		{
			"category": "Accounting",
			"blurb": "Push closed folios to your books - Kamra keeps the "
			         "front office, your ledger keeps compliance.",
			"cards": [
				_connector("Accounting export", "export",
				           "Download closed invoices as Tally, Zoho or ERPNext "
				           "import files - your books, your ledger.",
				           action="route", route="/accounting-export",
				           status="available"),
				_bench("ERPNext + India Compliance",
				       "Post invoices to ERPNext; e-invoice (IRN), e-way bill "
				       "and GSTR filing via the India Compliance app.",
				       "bench get-app india_compliance"),
			],
		},
		{
			"category": "Country packs",
			"blurb": "Tax, invoicing and government filing for where you "
			         "operate. Install the pack for your country.",
			"cards": [
				_module("India", "GST slabs, SAC, GSTIN, GSTR-1, e-invoice.",
				        detail="Included"),
				_bench("United Arab Emirates", "UAE VAT, FTA reports.", None,
				       status="planned"),
				_bench("Saudi Arabia", "ZATCA Phase 2, QR, e-invoice.", None,
				       status="planned"),
				_bench("United Kingdom", "VAT, Making Tax Digital.", None,
				       status="planned"),
				_bench("Germany", "MwSt, DATEV, TSE.", None, status="planned"),
				_bench("France", "TVA, NF525, FEC.", None, status="planned"),
			],
		},
	]


def _module(name, blurb, planned=False, detail=None):
	return {"kind": "module", "name": name, "blurb": blurb,
	        "status": "planned" if planned else "included", "detail": detail}


def _connector(name, key, blurb, action=None, route=None, channel=None,
               status="available", detail=None, connection=None):
	return {"kind": "connector", "name": name, "key": key, "blurb": blurb,
	        "action": action, "route": route, "channel": channel,
	        "status": status, "detail": detail, "connection": connection}


def _enterprise(name, blurb):
	return {"kind": "enterprise", "name": name, "blurb": blurb,
	        "status": "enterprise"}


def _bench(name, blurb, command, status="planned"):
	return {"kind": "bench_app", "name": name, "blurb": blurb,
	        "command": command, "status": status}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin", "System Manager")
def connect_heykoala(property: str, channel: str, phone_number: str):
	"""Wire a HeyKoala Voice/WhatsApp channel to this property. Creates (or
	revives) the Channel Provider Connection, mints an inbound webhook secret,
	and returns the URLs + secret ONCE so they can be pasted into HeyKoala."""
	if channel not in ("Voice", "WhatsApp"):
		frappe.throw("Channel must be Voice or WhatsApp.")
	if not (phone_number or "").strip():
		frappe.throw("A phone number is required.")
	secret = frappe.generate_hash(length=32)
	existing = frappe.db.get_value(
		"Channel Provider Connection",
		{"property": property, "provider": "HeyKoala", "channel": channel})
	doc = frappe.get_doc("Channel Provider Connection", existing) if existing \
		else frappe.new_doc("Channel Provider Connection")
	doc.property = property
	doc.provider = "HeyKoala"
	doc.channel = channel
	doc.phone_number = phone_number.strip()
	doc.active = 1
	doc.webhook_secret = secret
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	from kamra.savings import log_action
	log_action("channel_connected", "Channel Provider Connection", doc.name,
	           property, rationale=f"HeyKoala {channel} on {phone_number}")

	base = frappe.utils.get_url()
	method = ("voice_webhook" if channel == "Voice" else "messaging_webhook")
	return {
		"connection": doc.name,
		"channel": channel,
		"phone_number": doc.phone_number,
		"webhook_url": f"{base}/api/method/kamra.agents_channels.{method}",
		"webhook_secret": secret,
		"signature_header": "X-Kamra-Signature",
		"signature_note": "HMAC-SHA256 of the JSON body (keys sorted), hex, "
		                  "sent in the X-Kamra-Signature header.",
	}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin", "System Manager")
def disconnect_channel(connection: str):
	frappe.db.set_value("Channel Provider Connection", connection, "active", 0)
	frappe.db.commit()
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin", "System Manager")
def enterprise_enquiry(property: str, item: str, note: str = "",
                       contact: str = ""):
	"""Register interest in an enterprise / custom integration. Lands in the
	Activity log for the team to follow up - no obligation, no auto-provision."""
	from kamra.savings import log_action
	log_action("enterprise_enquiry", "Property", property, property,
	           rationale=f"{item} - {note or 'requested'} "
	                     f"({contact or frappe.session.user})")
	return {"ok": True}
