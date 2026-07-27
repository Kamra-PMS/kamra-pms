"""Thailand localization pack.

Thai hotel rooms and hotel F&B are standard-rated VAT supplies - 7%
(the reduced rate, extended year after year; the statutory 10% has not
applied since 1999). So this is a flat-rate pack:

  - the rate comes from the Room Type's tax percent (default 7), so if
    the statutory rate ever changes the operator types the new number
    on the room type
  - the customary 10% service charge is NOT VAT - it is itself a
    VATable part of the bill; post it as a normal folio charge line
  - tax invoices quote the 13-digit Tax ID (TIN) and should say
    "ใบกำกับภาษี" (tax invoice)

No per-night tourism levy exists today (the proposed 300-baht entry
fee was never implemented). e-Tax Invoice (ETDA) filing is out of
scope for the pack - a connected service can wire it later without
touching this seam.
"""

from decimal import Decimal

import frappe

DEFAULT_VAT = Decimal("7")


def calculate_room_tax(property, room_type_doc, nightly_rate) -> Decimal:
	"""Flat VAT - no slabs, no per-tariff switching. Unset means the
	standard 7%."""
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
	return [0, 7]


def invoice_context(prop_doc) -> dict:
	return {
		"tax_label": "VAT (ภาษีมูลค่าเพิ่ม)",
		"tax_id_label": "Tax ID",
		"service_code": None,
		"sac": None,
		"place_of_supply": prop_doc.get("city") or prop_doc.get("state"),
		# national VAT, single line - no centre/state split
		"split": [("vat", Decimal("1"))],
		"footer": "ใบกำกับภาษี / Tax Invoice - "
		          "This is a computer-generated invoice.",
	}


def locale(prop_doc) -> dict:
	return {
		"currency_symbol": "฿",
		"locale": "th-TH",
		"currency": prop_doc.get("currency") or "THB",
		"tax_label": "VAT",
		"tax_id_label": "Tax ID",
		"tax_rates": tax_rate_options(prop_doc.name),
	}
