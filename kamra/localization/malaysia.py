"""Malaysia localization pack.

Malaysian accommodation is under SST (Service Tax), not GST (repealed
2018). Since 1 March 2024 accommodation is taxed at 8%, while food &
beverage stayed at 6% - the one country in the seam where rooms and
restaurants genuinely carry different rates:

  - the room rate comes from the Room Type's tax percent (default 8),
    so a future rate change is typed on the room type
  - hotel F&B is fixed at the statutory 6% F&B service tax rate
  - the Tourism Tax (TTx, RM10 per room per night, foreign guests
    only, operators under MyTTx) is a flat per-night levy, not a
    percentage - post it as a folio charge line for foreign-guest
    stays; automating it needs nationality-aware night audit, which a
    later pack version can add
  - invoices quote the SST registration number

MyTTx / SST-02 return filing is out of scope for the pack - a
connected service can wire it later without touching this seam.
"""

from decimal import Decimal

import frappe

DEFAULT_SST = Decimal("8")   # accommodation, since 2024-03-01
FNB_SST = Decimal("6")       # food & beverage kept the old rate


def calculate_room_tax(property, room_type_doc, nightly_rate) -> Decimal:
	"""Flat service tax - unset means the statutory 8%."""
	v = room_type_doc.get("tax_percent") if room_type_doc else None
	return Decimal(str(v)) if v else DEFAULT_SST


def fnb_tax_rate(property) -> float:
	"""F&B service tax stayed at 6% when accommodation moved to 8% -
	deliberately NOT the room rate."""
	return float(FNB_SST)


def tax_rate_options(property) -> list:
	return [0, 6, 8]


def invoice_context(prop_doc) -> dict:
	return {
		"tax_label": "Service Tax (SST)",
		"tax_id_label": "SST Registration No.",
		"service_code": None,
		"sac": None,
		"place_of_supply": prop_doc.get("city") or prop_doc.get("state"),
		# federal service tax, single line
		"split": [("sst", Decimal("1"))],
		"footer": "Tourism Tax (RM10/room/night, non-Malaysian guests) "
		          "is billed as a separate line where applicable. "
		          "This is a computer-generated invoice.",
	}


def locale(prop_doc) -> dict:
	return {
		"currency_symbol": "RM",
		"locale": "ms-MY",
		"currency": prop_doc.get("currency") or "MYR",
		"tax_label": "SST",
		"tax_id_label": "SST Reg. No.",
		"tax_rates": tax_rate_options(prop_doc.name),
	}
