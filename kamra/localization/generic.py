"""Fallback pack for countries without a dedicated localization: a single
flat tax rate (Property.gst_rate_low reused as the VAT %), plain labels, no
government filings. Enough to run a hotel and print a clean invoice."""

from decimal import Decimal

import frappe


def calculate_room_tax(property, room_type_doc, nightly_rate) -> Decimal:
	prop = frappe.get_cached_doc("Property", property)
	return Decimal(str(prop.get("gst_rate_low") or 0))


def fnb_tax_rate(property) -> float:
	prop = frappe.get_cached_doc("Property", property)
	return float(prop.get("gst_rate_low") or 0)


def tax_rate_options(property) -> list:
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
