"""Localization seam. The core PMS never knows about GST, VAT or fiscal
printers - it asks the country pack. Packs are resolved through the
`kamra_localization` hook (ERPNext regional_overrides style), so a future
`kamra_uae` app claims its country just by declaring the hook. Countries
without a pack fall back to a plain flat-tax `generic` pack.

Interface every pack implements (see india.py):
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
# A pack that predates these keeps working: each accessor falls back to
# something correct-but-plain, so adding a country never means editing the
# invoice printer.


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
	}


def privacy_terms(pack) -> dict:
	"""Who a guest complains to, and the statutory guest report (if any)
	the hotel files - for the privacy notice where data is collected."""
	return {
		"privacy_authority": getattr(pack, "PRIVACY_AUTHORITY", None)
		                     or "your local data protection authority",
		"guest_report": getattr(pack, "GUEST_REPORT", None),
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
