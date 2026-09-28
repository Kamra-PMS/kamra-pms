"""Saudi Arabia localization pack.

Hotel accommodation and hotel F&B are standard-rated VAT supplies - 15%
since July 2020. What sits beside VAT is not VAT:

  - the VAT rate comes from the Room Type's tax percent (default 15)
  - the municipality fee on accommodation (a percentage set by the
    municipality) is a levy on the guest, not tax on the operator's
    supply - post it as a normal folio charge line, like the UAE fees
  - tax invoices must quote the 15-digit VAT registration number;
    guest bills to individuals are "Simplified Tax Invoices" (ZATCA)

ZATCA (FATOORA) e-invoicing - QR codes, clearance and reporting - is out
of scope for the pack; a connected service can wire it later without
touching this seam.
"""

from decimal import Decimal

import frappe

DEFAULT_VAT = Decimal("15")

DEFAULT_CURRENCY = "SAR"
DEFAULT_TIMEZONE = "Asia/Riyadh"
DEFAULT_NATIONALITY = "Saudi"
# what the front desk records at check-in: citizens carry the National ID,
# residents the Iqama, GCC visitors their own national card
ID_TYPES = ["National ID", "Iqama", "Passport", "GCC ID", "Other"]
# mada is a card scheme - it books as Card so the till still balances
PAYMENT_MODES = ["Cash", "Card", "Bank Transfer"]


def calculate_room_tax(property, room_type_doc, nightly_rate) -> Decimal:
	"""Flat VAT - unset means the standard 15%."""
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
	return [0, 15]


def invoice_context(prop_doc) -> dict:
	return {
		"tax_label": "VAT",
		"tax_id_label": "VAT No.",
		"service_code": None,
		"sac": None,
		"place_of_supply": prop_doc.get("city") or prop_doc.get("state"),
		# national VAT, single line
		"split": [("vat", Decimal("1"))],
		"footer": "Simplified Tax Invoice - municipality fees appear as a "
		          "separate line where applicable. "
		          "This is a computer-generated invoice.",
	}


def locale(prop_doc) -> dict:
	return {
		# trailing space: "SAR 1,500" - the UI concatenates symbol+amount
		"currency_symbol": "SAR ",
		"locale": "en-SA",
		"currency": prop_doc.get("currency") or DEFAULT_CURRENCY,
		"tax_label": "VAT",
		"tax_id_label": "VAT No.",
		"tax_rates": tax_rate_options(prop_doc.name),
	}
