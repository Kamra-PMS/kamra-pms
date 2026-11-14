"""The Kamra Marketplace: what's in your plan, and what you can plug in.

Card kinds, each with its own install model - never conflated:

  module     a Kamra app that ships in this codebase, open and included
             (no install, no lock).
  connector  a live integration backed by a config row (a channel, a payment
             gateway, an AI key) - the card connects/configures it here.
  bench_app  a separate Frappe app you install on the bench (country packs,
             the ERPNext accounting bridge) - the card shows honest
             `bench get-app` instructions, never a fake button.
  custom     built for a hotel on request; the card files an enquiry.
  link       points at docs or issues (the "Your country" pack card).
  enterprise the one Kamra Enterprise card: a quote enquiry, and Connect
             through the Connected apps pairing flow.
"""

import frappe

from kamra.authz import require_roles

DOCS_COUNTRY_PACK = "https://kamrapms.com/docs/write-a-country-pack"
COUNTRY_PACK_ISSUES = ("https://github.com/Kamra-PMS/kamra-pms/issues"
                       "?q=is%3Aopen+label%3Acountry-pack")


@frappe.whitelist()
@require_roles("Hotel Admin", "System Manager")
def registry(property: str):
	"""Everything on offer, grouped, with this property's live status."""
	ai = frappe.db.get_value(
		"AI Assistant Settings", {"property": property}, "enabled")
	from kamra import localization as loc

	pay = frappe.db.get_value(
		"Payment Gateway Settings", {"property": property},
		["enabled", "gateway"], as_dict=True) or {}
	gateways = loc.payment_gateways(loc.pack_for(property))
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
				_module("Kamra Agent",
				        "The in-app agent, with your own AI key "
				        "(OpenAI, Gemini, Groq, OpenRouter…)."),
				_module("Events & Groups", "Banquets, blocks and pickup."),
				_module("Revenue", "Rates, seasons, offers, partners."),
				_module("POS",
				        "Table map, running bills, thermal KOT, kitchen display."),
			],
		},
		{
			"category": "Guest messaging (WhatsApp)",
			"blurb": "WhatsApp is the guest channel in India, Southeast Asia "
			         "and the Gulf. The Meta Cloud API integration is open "
			         "source and included - bring your own number.",
			"cards": [
				_module("WhatsApp - Meta Cloud API",
				        "Booking confirmations, self check-in links, payment "
				        "requests and a desk-side guest thread on your own "
				        "WhatsApp Business number. Meta bills you directly "
				        "per conversation; Kamra adds nothing.",
				        detail="Included - bring your own number"),
			],
		},
		{
			"category": "Distribution",
			"blurb": "Sync rates and availability across OTAs through the "
			         "channel manager you already use.",
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
				_custom("Other channel managers",
				        "SiteMinder, RateGain and others plug into the same "
				        "open provider seam. We build it as a custom "
				        "integration on request, scoped per property."),
			],
		},
		{
			"category": "Bring your own AI",
			"blurb": "Kamra ships the governed tools + MCP; you bring the "
			         "intelligence. Connect Claude Desktop over MCP, or power "
			         "the in-app Agent with any OpenAI-compatible key "
			         "(OpenAI, Gemini, Groq, OpenRouter, Ollama…).",
			"cards": [
				_connector("Connect Claude (MCP)", "claude",
				           "Claude the app acts as you over hosted MCP, "
				           "not an Anthropic API key in Settings. Role limits "
				           "and the Activity Log still apply.",
				           action="route", route="/assistant",
				           status="connected" if has_key else "available",
				           detail="Your connector" if has_key else None),
				_connector("Bring your own model", "openai",
				           "In-app Kamra Agent: pick OpenAI, Gemini, Groq, "
				           "OpenRouter or Ollama, paste a key, Test connection.",
				           action="route", route="/settings",
				           status="connected" if ai else "configure"),
			],
		},
		{
			"category": "Payments",
			"blurb": "Take deposits and settle bills online. The gateways on "
			         "offer come with your country pack.",
			"cards": [
				_connector(g, g.lower(),
				           f"Payment links for balances and advances, paid "
				           f"into your own {g} account.",
				           action="route", route="/settings",
				           status="connected" if pay.get("enabled")
				           and pay.get("gateway") == g else "configure")
				for g in gateways
			] or [
				_module("Online payment links",
				        "No gateway in your country pack yet - take "
				        "payments at the desk.", planned=True),
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
				_module("India", "GST slabs, SAC, GSTIN, GSTR-1. "
				        "Razorpay and Cashfree payment links.",
				        detail="Included"),
				_module("Indonesia",
				        "PB1/PBJT regional hotel tax (flat, per-region rate), "
				        "NPWP on invoices, Rupiah. Community-contributed.",
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
				_module("Saudi Arabia",
				        "15% VAT, ZATCA Phase 1 e-invoices with QR, "
				        "Riyal. Municipality fee as a folio line.",
				        detail="Included"),
				_module("Brazil",
				        "Municipal ISS on rooms and F&B (5% default, set "
				        "per room type), CNPJ or CPF on invoices, Real.",
				        detail="Included"),
				_module("Nicaragua",
				        "15% IVA, Córdoba, hotel invoice wording in "
				        "Spanish and English. INTUR levy as a folio line.",
				        detail="Included"),
				_link("Your country",
				      "Not listed yet? A country pack is one Python file. "
				      "Follow the guide, or pick up an open country pack "
				      "issue.",
				      [("Country pack guide", DOCS_COUNTRY_PACK),
				       ("Open country pack issues", COUNTRY_PACK_ISSUES)]),
			],
		},
		{
			"category": "Kamra Enterprise",
			"blurb": "A separate paid program that connects to your Kamra "
			         "over the public API. Community stays free and "
			         "complete for running a hotel.",
			"cards": [
				{"kind": "enterprise", "name": "Kamra Enterprise",
				 "blurb": "Owner and MD reporting, audit statements, Pro "
				          "Agent, guest concierge and offers through "
				          "HeyKoala on voice and WhatsApp, and tools for "
				          "chains. Contact us for a quote.",
				 "status": "on_request", "action": "pair"},
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


def _custom(name, blurb):
	"""Built for a hotel on request; the card files an enquiry."""
	return {"kind": "custom", "name": name, "blurb": blurb,
	        "status": "on_request"}


def _link(name, blurb, links):
	return {"kind": "link", "name": name, "blurb": blurb, "status": "help_wanted",
	        "links": [{"label": lbl, "href": href} for lbl, href in links]}


def _bench(name, blurb, command, status="planned"):
	return {"kind": "bench_app", "name": name, "blurb": blurb,
	        "command": command, "status": status}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin", "System Manager")
def connect_heykoala(property: str, channel: str, phone_number: str):
	"""Wire a HeyKoala Voice/WhatsApp channel to this property. Creates (or
	revives) the Channel Provider Connection, mints an inbound webhook secret,
	and returns the URLs + secret ONCE so they can be pasted into HeyKoala.

	Guest-facing AI now belongs to Kamra Enterprise, which drives this over
	the public API; the Marketplace no longer shows a wizard for it. Kept
	unchanged as a public API contract."""
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
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional

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
	"""Switch off a Channel Provider Connection. Kamra Enterprise drives guest
	AI channels now; kept unchanged as a public API contract."""
	frappe.db.set_value("Channel Provider Connection", connection, "active", 0)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin", "System Manager")
def enterprise_enquiry(property: str, item: str, note: str = "",
                       contact: str = ""):
	"""Register interest in Kamra Enterprise or a custom integration. The
	method name is kept for API compatibility. Lands in the
	Activity log for the team to follow up - no obligation, no auto-provision."""
	from kamra.savings import log_action
	log_action("enterprise_enquiry", "Property", property, property,
	           rationale=f"{item} - {note or 'requested'} "
	                     f"({contact or frappe.session.user})")
	return {"ok": True}
