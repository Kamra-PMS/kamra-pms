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
# charged per night on the room rate; the rate is set per property
ROOM_LEVY_LABEL = "Municipality fee"
DEFAULT_NATIONALITY = "Saudi"
# named in the guest privacy notice (PDPL; hotels register guests in Shomoos)
PRIVACY_AUTHORITY = "the Saudi Data & AI Authority (SDAIA)"
GUEST_REPORT = "guest registration with the Shomoos security system"
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


# ── ZATCA e-invoicing ────────────────────────────────────────────────────

def on_invoice_issued(folio_name: str):
	from kamra import zatca
	return zatca.issue_for_folio(folio_name)


def on_invoice_cancelled(folio_name: str, invoice_number: str, reason: str):
	from kamra import zatca
	return zatca.credit_note_for_folio(folio_name, invoice_number, reason)


def on_pos_bill_paid(order_name: str, tax_rate: float):
	from kamra import zatca
	return zatca.issue_for_pos_order(order_name, tax_rate)


def invoice_print_block(source_doctype: str, source_name: str,
                        number: str | None = None):
	from kamra import zatca
	return zatca.print_block(source_doctype, source_name, number)
