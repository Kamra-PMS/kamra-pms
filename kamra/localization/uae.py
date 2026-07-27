"""United Arab Emirates localization pack.

UAE hotel stays and hotel F&B are standard-rated VAT supplies - 5%
since 2018. The emirate-level levies are NOT VAT and are not
percentages of the same base:

  - the VAT rate comes from the Room Type's tax percent (default 5)
  - the municipality fee (e.g. 7% in Dubai), the customary 10%
    service charge, and the per-night Tourism Dirham (AED 7-20 by
    hotel class in Dubai; other emirates differ) are posted as normal
    folio charge lines - they vary by emirate and are levies on the
    guest, not tax on the operator's supply
  - tax invoices must quote the 15-digit TRN and be titled
    "Tax Invoice" (FTA requirement)

FTA e-invoicing (planned phase-in) is out of scope for the pack - a
connected service can wire it later without touching this seam.
"""

from decimal import Decimal

import frappe

DEFAULT_VAT = Decimal("5")


def calculate_room_tax(property, room_type_doc, nightly_rate) -> Decimal:
	"""Flat VAT - unset means the standard 5%."""
	v = room_type_doc.get("tax_percent") if room_type_doc else None
	return Decimal(str(v)) if v else DEFAULT_VAT


def fnb_tax_rate(property) -> float:
	"""Hotel restaurants are the same standard-rated VAT supply."""
	rates = frappe.get_all(
		"Room Type", filters={"property": property, "disabled": 0},
		pluck="tax_percent", limit=5)
	first = next((r for r in rates if r), None)
	return float(first) if first else float(DEFAULT_VAT)


def tax_rate_options(property) -> list:
	return [0, 5]


def invoice_context(prop_doc) -> dict:
	return {
		"tax_label": "VAT",
		"tax_id_label": "TRN",
		"service_code": None,
		"sac": None,
		"place_of_supply": prop_doc.get("city") or prop_doc.get("state"),
		# federal VAT, single line
		"split": [("vat", Decimal("1"))],
		"footer": "Tax Invoice - municipality fees and Tourism Dirham "
		          "appear as separate lines where applicable. "
		          "This is a computer-generated invoice.",
	}


def locale(prop_doc) -> dict:
	return {
		# trailing space: "AED 1,500" - the UI concatenates symbol+amount
		"currency_symbol": "AED ",
		"locale": "en-AE",
		"currency": prop_doc.get("currency") or "AED",
		"tax_label": "VAT",
		"tax_id_label": "TRN",
		"tax_rates": tax_rate_options(prop_doc.name),
	}
