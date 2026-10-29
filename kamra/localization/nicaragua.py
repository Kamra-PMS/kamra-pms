"""Nicaragua: general-regime IVA, NIO and hotel invoice vocabulary.

The standard IVA rate is 15% (Ley 822, art. 109). A non-zero Room Type
tax_percent overrides the room rate, following the existing country-pack
contract: Frappe stores an empty Percent field as zero. Otherwise a
non-zero Property.gst_rate_low wins over 15%, so a Nicaragua property set
up under the generic pack keeps the rate it already charged. F&B and guest
services use that property rate or 15%, never a room-type override.

INTUR is a separate, operator-configured room levy, never a 17% IVA rate.
This pack supplies its label only; it does not enable the levy, decide
eligibility or thresholds, fetch exchange rates, or calculate exemptions.
Cuota fija, temporary tourism IVA exemptions, municipal taxes and DGI/INTUR
filing are outside this initial pack. It does not certify a fiscal invoice.

Sources (checked 2026-10-28):
- DGI, IVA and Ley 822 art. 109:
  https://www.dgi.gob.ni/FAQ/creacion__materia_imponible__h.htm
- BCN, currency symbol and domestic-price circular (2024-12-13):
  https://www.bcn.gob.ni/divulgacion-prensa/bcn-emite-circular-para-la-aplicacion-de-las-disposiciones-sobre-los-pagos-en-la
- INTUR, current tourism legislation and regulations:
  https://www.intur.gob.ni/leyes-de-turismo/
"""

from decimal import Decimal

import frappe

DEFAULT_VAT = Decimal("15")
DEFAULT_CURRENCY = "NIO"
DEFAULT_TIMEZONE = "America/Managua"
DEFAULT_NATIONALITY = "Nicaraguan"
ID_TYPES = ["National ID", "Passport", "Residence Card", "Driving License", "Other"]
PAYMENT_MODES = ["Cash", "Card", "Bank Transfer"]
ROOM_LEVY_LABEL = "INTUR"
NOTICE_LANGUAGES = ["es", "en"]


def _property_rate(property) -> Decimal:
	# the generic pack's flat rate, kept for properties created before this pack
	value = frappe.db.get_value("Property", property, "gst_rate_low") if property else None
	return Decimal(str(value)) if value else DEFAULT_VAT


def calculate_room_tax(property, room_type_doc, nightly_rate) -> Decimal:
	value = room_type_doc.get("tax_percent") if room_type_doc else None
	return Decimal(str(value)) if value else _property_rate(property)


def fnb_tax_rate(property) -> float:
	return float(_property_rate(property))


def services_tax_rate(property) -> float:
	return float(_property_rate(property))


def tax_rate_options(property) -> list:
	return [0, 15]


def invoice_context(prop_doc) -> dict:
	return {
		"tax_label": "IVA",
		"tax_id_label": "RUC",
		"service_code": None,
		"sac": None,
		"place_of_supply": prop_doc.get("city") or prop_doc.get("state"),
		"split": [("iva", Decimal("1"))],
		"footer": "Documento generado por Kamra. Los tributos y cargos "
		          "adicionales se detallan por separado.",
	}


def locale(prop_doc) -> dict:
	currency = prop_doc.get("currency") or DEFAULT_CURRENCY
	# Read the exact configured currency, so a USD property never inherits C$.
	symbol = (frappe.db.get_value("Currency", currency, "symbol") or "").strip()
	if not symbol:
		symbol = "C$" if currency == DEFAULT_CURRENCY else f"{currency} "
	return {
		"currency_symbol": symbol,
		"locale": "es-NI",
		"currency": currency,
		"tax_label": "IVA",
		"tax_id_label": "RUC",
		"tax_rates": tax_rate_options(prop_doc.get("name")),
	}
