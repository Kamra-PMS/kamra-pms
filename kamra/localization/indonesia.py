"""Indonesia localization pack — requested and guided by the community
(github.com/Kamra-PMS/kamra-pms/issues/4, @augustinussent).

Indonesian hotel stays are NOT under PPN (national VAT): accommodation and
hotel F&B carry the REGIONAL hotel tax — PB1, now formally PBJT under
UU HKPD 1/2022 — levied by the city/regency, standard 10% almost
everywhere (regions may set less). So this pack is a flat-rate pack:

  - the rate comes from the Room Type's tax percent (default 10) so a
    region with a different PBJT just types its number on the room type -
    the India-labelled GST slab fields are deliberately NOT reused (they
    default to Indian values on every new property)
  - the customary 5-10% service charge is NOT a tax - post it as a
    normal folio charge line if the house levies it
  - businesses still quote their NPWP on invoices

PPN (11%/12%) appears in tax_rate_options for the odd non-hotel supply
an operator may bill. e-Faktur integration is out of scope for the pack
(it applies to PPN-registered supplies, not PB1) - a connected service
can wire it later without touching this seam.
"""

from decimal import Decimal

import frappe

DEFAULT_PBJT = Decimal("10")


def calculate_room_tax(property, room_type_doc, nightly_rate) -> Decimal:
	"""PBJT is flat - no slabs, no per-tariff switching. The room type's
	tax percent IS the region's PBJT; unset means the standard 10%."""
	v = room_type_doc.get("tax_percent") if room_type_doc else None
	return Decimal(str(v)) if v else DEFAULT_PBJT


def fnb_tax_rate(property) -> float:
	"""Hotel restaurants fall under the same regional PBJT. Use the
	property's most common room-type rate; standard 10% when unset."""
	rates = frappe.get_all(
		"Room Type", filters={"property": property, "disabled": 0},
		pluck="tax_percent", limit=5)
	first = next((r for r in rates if r), None)
	return float(first) if first else float(DEFAULT_PBJT)


def tax_rate_options(property) -> list:
	return [0, 10, 11, 12]


def invoice_context(prop_doc) -> dict:
	return {
		"tax_label": "PB1 (Pajak Hotel)",
		"tax_id_label": "NPWP",
		"service_code": None,
		"sac": None,
		"place_of_supply": prop_doc.get("city") or prop_doc.get("state"),
		# regional tax, single line - no centre/state split
		"split": [("pb1", Decimal("1"))],
		"footer": "Faktur ini dibuat secara elektronik. / "
		          "This is a computer-generated invoice.",
	}


def locale(prop_doc) -> dict:
	return {
		"currency_symbol": "Rp",
		"locale": "id-ID",
		"currency": prop_doc.get("currency") or "IDR",
		"tax_label": "PB1",
		"tax_id_label": "NPWP",
		"tax_rates": tax_rate_options(prop_doc.name),
	}
