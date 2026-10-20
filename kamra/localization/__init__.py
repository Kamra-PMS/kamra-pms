"""Localization seam. The core PMS never knows about GST, VAT or fiscal
printers - it asks the country pack. Packs are resolved through the
`kamra_localization` hook (ERPNext regional_overrides style), so a future
`kamra_uae` app claims its country just by declaring the hook. Countries
without a pack fall back to a plain flat-tax `generic` pack.

Interface every pack implements (see india/):
  calculate_room_tax(property, room_type_doc, nightly_rate) -> Decimal
  fnb_tax_rate(property) -> float
  tax_rate_options(property) -> list[float]
  invoice_context(prop_doc) -> dict   (labels, service code, place of supply)
  locale(prop_doc) -> dict            (currency_symbol, locale, tax_label...)

Optional, for invoice printing - a pack that doesn't implement these gets
a sensible default from the accessors at the bottom of this file, so an
existing pack keeps working untouched:
  service_code_for(prop_doc, charge_type) -> dict | None   (per-LINE SAC/HSN)
  tax_split(prop_doc, buyer_tax_id) -> list[(label, share)]
  amount_in_words(prop_doc, amount) -> str

Optional country integrations - absent means "not offered in this country",
and the accessors refuse rather than fall back to another country's:
  PAYMENT_GATEWAYS = [...]; payment_provider(gateway) -> module
  tax_return_rows(property, from_date, to_date) -> list[dict]
  verify_tax_id(property, tax_id, business_name) -> dict
  verify_guest_id(property, guest, id_type, consent) -> dict
"""

import importlib

import frappe


def pack_for(property: str | None = None):
	country = None
	if property:
		country = frappe.get_cached_value("Property", property, "country")
	return pack_for_country(country or "India")


def pack_for_country(country: str):
	mapping = frappe.get_hooks("kamra_localization") or {}
	target = mapping.get(country)
	if target:
		path = target[-1] if isinstance(target, (list, tuple)) else target
		try:
			return importlib.import_module(path)
		except ModuleNotFoundError:
			pass
	from kamra.localization import generic
	return generic


# ── optional pack behaviour, with defaults ───────────────────────────────
#
#   services_tax_rate(property) -> float   (laundry & other guest services)
# A pack that predates these keeps working: each accessor falls back to
# something correct-but-plain, so adding a country never means editing the
# invoice printer.


def services_tax_rate(pack, property: str | None) -> float:
	"""The tax rate on a guest service such as laundry. A pack can say so
	(India: 18% GST on services); otherwise the pack's standard rate - the
	one its F&B rate already resolves to in every flat-VAT country."""
	fn = getattr(pack, "services_tax_rate", None)
	if fn:
		return float(fn(property))
	return float(pack.fnb_tax_rate(property))


def money_text(property: str | None, amount) -> str:
	"""An amount in the property's currency for server-written text (the
	activity log, alerts) - never a hardcoded rupee sign."""
	symbol = ""
	try:
		if property:
			prop = frappe.get_cached_doc("Property", property)
			symbol = pack_for(property).locale(prop).get("currency_symbol") or ""
	except Exception:
		symbol = ""
	try:
		value = float(amount or 0)
	except (TypeError, ValueError):
		return f"{symbol}{amount}"
	text = f"{value:,.2f}"
	if text.endswith(".00"):
		text = text[:-3]
	return f"{symbol}{text}"


def service_code_for(pack, prop_doc, charge_type: str | None = None):
	"""The tax service code for ONE line. A bill that mixes a room night,
	a restaurant cover and a laundry bag carries three different codes -
	printing the accommodation code against all of them is wrong."""
	fn = getattr(pack, "service_code_for", None)
	if fn:
		return fn(prop_doc, charge_type)
	return pack.invoice_context(prop_doc).get("service_code")


def tax_split(pack, prop_doc, buyer_tax_id: str | None = None):
	"""How the tax on this bill is named and divided - [(label, share)].
	Passed the buyer's tax id because in some countries who they are (and
	where) changes the answer."""
	fn = getattr(pack, "tax_split", None)
	if fn:
		return fn(prop_doc, buyer_tax_id)
	return pack.invoice_context(prop_doc)["split"]


def amount_in_words(pack, prop_doc, amount) -> str:
	fn = getattr(pack, "amount_in_words", None)
	if fn:
		return fn(prop_doc, amount)
	from kamra.localization.words import amount_in_words as spell

	loc = pack.locale(prop_doc)
	return spell(amount, loc.get("currency") or "", indian=False)


# ── front-desk vocabulary: IDs and ways to pay ───────────────────────────
# A pack declares ID_TYPES / PAYMENT_MODES / DEFAULT_* as module constants.
# Payment modes are always drawn from the canonical Folio Payment modes, so
# a pack chooses what the desk is offered - never invents a mode the till,
# ledger and night audit do not know.

GENERIC_ID_TYPES = ["Passport", "National ID", "Driving License", "Other"]
GENERIC_PAYMENT_MODES = ["Cash", "Card", "Bank Transfer"]
CANONICAL_PAYMENT_MODES = ("Cash", "Card", "UPI", "Bank Transfer")


def id_types(pack) -> list[str]:
	return list(getattr(pack, "ID_TYPES", None) or GENERIC_ID_TYPES)


def payment_modes(pack) -> list[str]:
	modes = getattr(pack, "PAYMENT_MODES", None) or GENERIC_PAYMENT_MODES
	return [m for m in modes if m in CANONICAL_PAYMENT_MODES]


def front_desk_vocabulary(pack) -> dict:
	return {
		"id_types": id_types(pack),
		"payment_modes": payment_modes(pack),
		"default_nationality": getattr(pack, "DEFAULT_NATIONALITY", "") or "",
		"adult_age": adult_age(pack),
		"minor_ids": minor_ids(pack),
	}


# ── children on the stay register (India DPDP s.9 and alike) ─────────────
# A minor is recorded with name and age only. ID details are kept only where
# registration law asks for them: by default for foreign nationals (Form C,
# TM30 and the like); a pack whose register covers every guest sets
# MINOR_IDS = "all".

def adult_age(pack) -> int:
	return int(getattr(pack, "ADULT_AGE", 18))


def minor_ids(pack) -> str:
	return getattr(pack, "MINOR_IDS", "foreign")


def is_minor(pack, age) -> bool:
	try:
		return age not in (None, "") and int(age) < adult_age(pack)
	except (TypeError, ValueError):
		return False


def minor_id_kept(pack, nationality: str | None) -> bool:
	"""May ID details be recorded for a minor of this nationality?"""
	if minor_ids(pack) == "all":
		return True
	home = (getattr(pack, "DEFAULT_NATIONALITY", "") or "").strip().casefold()
	nat = (nationality or "").strip().casefold()
	return bool(nat) and nat != home


def privacy_terms(pack) -> dict:
	"""Who a guest complains to, and the statutory guest report (if any)
	the hotel files - for the privacy notice where data is collected."""
	return {
		"privacy_authority": getattr(pack, "PRIVACY_AUTHORITY", None)
		                     or "your local data protection authority",
		"guest_report": getattr(pack, "GUEST_REPORT", None),
		"adult_age": adult_age(pack),
		# languages a guest may read the notice in besides the page's own
		"notice_languages": list(getattr(pack, "NOTICE_LANGUAGES", None) or []),
	}


def validate_id_type(property: str | None, id_type: str | None):
	"""An ID type must be one this property's country recognises. Values
	already on file are never re-checked - only new writes."""
	if not id_type:
		return
	allowed = id_types(pack_for(property))
	if id_type not in allowed:
		frappe.throw(
			frappe._("Unknown ID type {0}. Use one of: {1}.").format(
				id_type, ", ".join(allowed)))


# ── country integrations: payment gateways, tax returns, verification ────
# The core keeps the entry points (create a link, settle it, export a
# return, check an ID); the pack decides whether the country has the
# integration at all and which provider runs it.


def _not_offered(what: str):
	frappe.throw(frappe._("{0} is not available for this property's country.")
	             .format(what))


def payment_gateways(pack) -> list[str]:
	"""Online gateways the desk may configure in this country."""
	if not getattr(pack, "payment_provider", None):
		return []
	return list(getattr(pack, "PAYMENT_GATEWAYS", None) or [])


def _provider(pack, gateway: str | None):
	if not gateway or gateway not in payment_gateways(pack):
		_not_offered(frappe._("The {0} payment gateway").format(gateway or "online"))
	return pack.payment_provider(gateway)


def create_gateway_link(pack, settings, **link) -> tuple[str, str]:
	"""A live payment link on the property's own gateway account.
	Returns (link id, url)."""
	return _provider(pack, settings.gateway).create_link(settings, **link)


def test_gateway_link(pack, gateway: str | None, link_id: str) -> str:
	"""Where a test-mode link points - nothing is charged."""
	return _provider(pack, gateway).test_link(link_id)


def gateway_info(pack, gateway: str | None) -> dict:
	"""What Settings shows beside the keys: webhook URL, signup link."""
	return _provider(pack, gateway).info()


def _gateway_provider_any(gateway: str):
	"""The provider for a gateway name, from whichever pack offers it. A
	webhook names its gateway before it names a property."""
	mapping = frappe.get_hooks("kamra_localization") or {}
	for target in mapping.values():
		path = target[-1] if isinstance(target, (list, tuple)) else target
		try:
			pack = importlib.import_module(path)
		except ModuleNotFoundError:
			continue
		if gateway in payment_gateways(pack):
			return pack.payment_provider(gateway)
	return None


def parse_payment_webhook(gateway: str, payload: bytes, headers: dict,
                          settings_for) -> dict | None:
	"""A gateway's "paid" callback, verified against the property's own
	keys. Returns {folio, property, link_id, amount}, or None when the
	event is not a payment we act on. A bad signature raises."""
	provider = _gateway_provider_any(gateway)
	if not provider:
		return None
	folio = provider.webhook_folio(payload)
	if not folio or not frappe.db.exists("Folio", folio):
		return None
	property = frappe.db.get_value("Folio", folio, "property")
	if gateway not in payment_gateways(pack_for(property)):
		return None
	settings = settings_for(property)
	if settings.gateway != gateway:
		frappe.throw(frappe._("This property does not take payments through {0}.")
		             .format(gateway), frappe.PermissionError)
	paid = provider.verify_webhook(settings, payload, headers)
	if not paid:
		return None
	return {"folio": folio, "property": property, **paid}


def tax_return_rows(pack, property: str | None, from_date: str, to_date: str):
	fn = getattr(pack, "tax_return_rows", None)
	if not fn:
		_not_offered(frappe._("The tax return export"))
	return fn(property, from_date, to_date)


def verify_tax_id(pack, property: str, tax_id: str, business_name: str = ""):
	if not verify_released():
		frappe.throw(frappe._("Kamra Verify isn't available yet."))
	fn = getattr(pack, "verify_tax_id", None)
	if not fn:
		_not_offered(frappe._("Tax ID verification"))
	return fn(property, tax_id, business_name)


def verify_guest_id(pack, property: str, guest: str, id_type: str,
                    consent: int = 0):
	if not verify_released():
		frappe.throw(frappe._("Kamra Verify isn't available yet."))
	fn = getattr(pack, "verify_guest_id", None)
	if not fn:
		_not_offered(frappe._("Guest ID verification"))
	return fn(property, guest, id_type, consent)


def verify_released() -> bool:
	"""Kamra Verify isn't released yet: its hub service isn't live. Until it
	is, every Verify button, the Settings page and the endpoints stay off
	unless a site opts in with `kamra_verify_enabled: 1` in site config."""
	return bool(frappe.conf.get("kamra_verify_enabled"))


def integrations(pack) -> dict:
	"""Which country integrations this property has - so the desk shows a
	Verify button or a gateway picker only where they exist."""
	verify = verify_released()
	return {
		"payment_gateways": payment_gateways(pack),
		"tax_return": bool(getattr(pack, "tax_return_rows", None)),
		"verify_tax_id": verify and bool(getattr(pack, "verify_tax_id", None)),
		"verify_guest_id": verify and bool(getattr(pack, "verify_guest_id", None)),
	}


def supported_countries() -> list[dict]:
	"""Countries with a dedicated pack, and what picking one sets up - the
	setup wizard and Settings offer these. Anything else runs on the
	generic pack with the currency the operator chooses."""
	mapping = frappe.get_hooks("kamra_localization") or {}
	out = []
	for country, target in mapping.items():
		path = target[-1] if isinstance(target, (list, tuple)) else target
		try:
			pack = importlib.import_module(path)
		except ModuleNotFoundError:
			continue
		ctx = pack.invoice_context(frappe._dict(name=None))
		out.append({
			"country": country,
			"currency": getattr(pack, "DEFAULT_CURRENCY", None),
			"timezone": getattr(pack, "DEFAULT_TIMEZONE", None),
			"tax_label": ctx.get("tax_label"),
			"tax_id_label": ctx.get("tax_id_label"),
		})
	return sorted(out, key=lambda c: c["country"])


# ── statutory e-invoicing hooks ──────────────────────────────────────────
# A pack that must report invoices to its tax authority (Saudi ZATCA, and
# tomorrow others) implements on_invoice_issued / on_invoice_cancelled /
# on_pos_bill_paid. The core calls these after the bill is final; a
# failure is logged loudly but never stops the desk closing a bill - the
# record can be regenerated, a guest kept waiting at checkout cannot.


def _hook(pack, name, *args):
	fn = getattr(pack, name, None)
	if not fn:
		return None
	# all-or-nothing: a half-written record would fork the invoice chain
	sp = f"einv_{name}"
	frappe.db.savepoint(sp)
	try:
		return fn(*args)
	except Exception:
		frappe.db.rollback(save_point=sp)
		frappe.log_error(title=f"e-invoicing: {name} failed")
		return None


def on_invoice_issued(pack, folio_name: str):
	return _hook(pack, "on_invoice_issued", folio_name)


def on_invoice_cancelled(pack, folio_name: str, invoice_number: str,
                         reason: str):
	return _hook(pack, "on_invoice_cancelled", folio_name, invoice_number,
	             reason)


def on_pos_bill_paid(pack, order_name: str, tax_rate: float):
	return _hook(pack, "on_pos_bill_paid", order_name, tax_rate)


def invoice_print_block(pack, source_doctype: str, source_name: str,
                        number: str | None = None):
	"""Whatever the authority requires ON the printed bill (ZATCA's QR and
	bilingual title) - None where nothing is required."""
	return _hook(pack, "invoice_print_block", source_doctype, source_name,
	             number)
