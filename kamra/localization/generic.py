"""Fallback pack for countries without a dedicated localization: a single
flat tax rate (Property.gst_rate_low reused as the VAT %), plain labels, no
government filings. Enough to run a hotel and print a clean invoice."""

from decimal import Decimal

import frappe

# foreign currencies a property takes until Settings, Finance, Exchange rates
# says otherwise; a pack lists its own (kamra.settings.fx_currencies_default)
FX_CURRENCIES = ["USD", "EUR", "GBP", "AED", "SAR", "SGD", "AUD", "JPY"]


def calculate_room_tax(property, room_type_doc, nightly_rate) -> Decimal:
	prop = frappe.get_cached_doc("Property", property)
	return Decimal(str(prop.get("gst_rate_low") or 0))


def fnb_tax_rate(property) -> float:
	prop = frappe.get_cached_doc("Property", property)
	return float(prop.get("gst_rate_low") or 0)


def tax_rate_options(property) -> list:
	# a property that charges no tax (its rates are 0) offers only 0%, so a
	# charge added by hand can't pick up a tax by mistake
	if property:
		prop = frappe.get_cached_doc("Property", property)
		if not float(prop.get("gst_rate_low") or 0) and not float(prop.get("gst_rate_high") or 0):
			return [0]
	return [0, 5, 10, 12, 15, 20]


def invoice_context(prop_doc) -> dict:
	return {
		"tax_label": "Tax",
		"tax_id_label": "Tax ID",
		"service_code": None,
		"sac": None,
		"place_of_supply": prop_doc.get("state"),
		"split": [("tax", Decimal("1"))],
		"footer": "This is a computer-generated invoice.",
	}


def locale(prop_doc) -> dict:
	currency = prop_doc.get("currency") or "USD"
	# the Currency master knows the symbol ($, £, €, S$, ...); on a bare
	# site with no currency records the code itself becomes the symbol -
	# "USD 1,500" beats a bare unlabelled number
	symbol = frappe.db.get_value("Currency", currency, "symbol")
	return {
		"currency_symbol": symbol or f"{currency} ",
		"locale": "en-US",
		"currency": currency,
		"tax_label": "Tax",
		"tax_id_label": "Tax ID",
		"tax_rates": tax_rate_options(prop_doc.name),
	}
