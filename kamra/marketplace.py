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
			"category": "Guest messaging (WhatsApp)",
			"blurb": "WhatsApp is the guest channel in India, Southeast Asia "
			         "and the Gulf. The Meta Cloud API integration is open "
			         "source and included - bring your own number. Managed "
			         "gateway and the AI concierge are connected services.",
			"cards": [
				_module("WhatsApp - Meta Cloud API",
				        "Booking confirmations, self check-in links, payment "
				        "requests and a desk-side guest thread on your own "
				        "WhatsApp Business number. Meta bills you directly "
				        "per conversation; Kamra adds nothing.",
				        detail="Included - bring your own number"),
				_bench("WhatsApp managed gateway",
				       "Same features, our number and Meta relationship - "
				       "for hotels that don't want Meta business "
				       "verification. Per conversation.", None,
				       status="planned"),
			],
		},
		{
			"category": "AI on your phone lines (HeyKoala)",
			"blurb": "Kamra is agent-ready. HeyKoala is the AI that answers your "
			         "phone and WhatsApp - it books, quotes and handles requests "
			         "24x7 using Kamra's governed tools, and every action is "
			         "logged. Connect a number to switch it on.",
			"cards": [
				_connector("HeyKoala Voice AI", "heykoala",
				           "A phone number HeyKoala's AI concierge answers - "
				           "books, quotes and answers, 24x7.",
				           action="heykoala", channel="Voice",
				           **_channel_status(property, "HeyKoala", "Voice")),
				_connector("HeyKoala WhatsApp", "heykoala",
				           "A WhatsApp number the AI answers - confirmations, "
				           "pre-arrival check-in and guest requests.",
				           action="heykoala", channel="WhatsApp",
				           **_channel_status(property, "HeyKoala", "WhatsApp")),
			],
		},
		{
			"category": "Distribution",
			"blurb": "Sync rates and availability across OTAs. Delivered as an "
			         "enterprise integration tailored to your channel mix.",
			"cards": [
				_module("Channex.io",
				        "Two-way OTA sync (Booking.com, Agoda, Expedia, "
				        "Airbnb) - bring your own Channex account, self-"
				        "serve. Map rooms, paste an API key, push.",
				        detail="Included - bring your own account"),
				_module("STAAH",
				        "Adapter ready; activates with STAAH connectivity-"
				        "partner credentials.", detail="Partner activation"),
				_module("AioSell",
				        "Adapter ready; activates with AioSell PMS-connect "
				        "credentials.", detail="Partner activation"),
				_enterprise("Other channel managers",
				            "SiteMinder, RateGain and friends - the provider "
				            "seam is open; scoped per property."),
			],
		},
		{
			"category": "Bring your own AI",
			"blurb": "Kamra ships the governed tools + MCP; you bring the "
			         "intelligence. Connect your own Claude (it acts as you, "
			         "scoped to your role), or power the in-app Copilot chat "
			         "with your OpenAI key.",
			"cards": [
				_connector("Connect Claude (MCP)", "claude",
				           "Point your Claude at this hotel over MCP - it can "
				           "use the tools your role allows, and nothing more.",
				           action="route", route="/assistant",
				           status="connected" if has_key else "available",
				           detail="Your connector" if has_key else None),
				_connector("OpenAI key", "openai",
				           "Power the in-app Copilot chat with your own key.",
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
				_module("Indonesia",
				        "PB1/PBJT regional hotel tax (flat, per-region rate), "
				        "NPWP on invoices, Rupiah. Community-contributed "
				        "(issue #4).",
				        detail="Included"),
				_module("Thailand",
				        "7% VAT, Thai tax invoice labels, Baht.",
				        detail="Included"),
				_module("Malaysia",
				        "SST 8% rooms / 6% F&B, SST registration no., "
				        "Ringgit. Tourism Tax as folio line.",
				        detail="Included"),
				_module("United Arab Emirates",
				        "5% VAT, TRN tax invoices, Dirham. Municipality "
				        "fee & Tourism Dirham as folio lines.",
				        detail="Included"),
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
