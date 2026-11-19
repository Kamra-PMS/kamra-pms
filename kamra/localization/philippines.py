"""Philippines localization pack.

VAT-registered hotels, motels, inns, resorts and hotel restaurants charge
12% VAT on the VAT-exclusive price (NIRC Section 108(A), as amended by
RA 12023). This is a flat-rate pack:

  - the room rate comes from the Room Type's tax percent (default 12),
    so a later change is typed on the room type
  - hotel F&B and guest services use that same rate
  - a service charge is not VAT. Post it as a normal folio line. It is
    part of gross sales, so it is itself VATable. RA 11360 distributes
    the charge to covered employees; it does not take it out of the tax
  - invoices quote the seller's TIN

Non-VAT sellers, generally those under the Section 109(CC) threshold
(PHP 3,000,000 until BIR applies the three-year CPI adjustment) who have
not registered for VAT voluntarily, pay 3% percentage tax under Section
116 instead of charging 12% VAT. CREATE (RA 11534) cut that rate to 1%
only from 1 July 2020 to 30 June 2023. tax_rate_options includes 0, 3
and 12. The default stays 12. A non-VAT house that shows the percentage
tax types 3 on the room type. A blank percent is stored as 0 and means
"use 12%", the same contract as the other flat-rate packs, so 0% on the
room type is not how a house absorbs the tax. A 0% line is still offered
when a charge is posted by hand (VAT-exempt, zero-rated, or a tax the
house does not pass on). The printed tax label stays VAT, because the
seam has one label. A non-VAT seller must not present this print as a
VAT invoice: RR 7-2024 makes that seller liable for 12% VAT, without
input tax, plus a 50% surcharge.

Local business tax (Local Government Code, RA 7160, Section 143) is paid
by the hotel to the city. It is not a guest-facing percentage, and the
schedules differ by ordinance, so this pack does not hardcode one.
Amusement tax (Section 140) is on admission fees, not on room charges.
A city fee that really is charged to the guest has no national default:
set the room levy name and percent (they start blank and at zero), or
post a flat environmental fee as its own charge.

Senior citizens (RA 9994, RR 7-2010) and persons with disability
(RA 10754, RR 5-2017) get a 20% discount and a VAT exemption on their
own hotel and restaurant consumption. senior_pwd_amounts() applies the
BIR formula: remove 12% VAT, then take 20% off the VAT-exclusive price.
The folio writer does not call it. Staff still post the discount and a
0% tax line by hand, and the OSCA or PWD ID number still has to be
written on the invoice. The ID types below are what the desk can record.

BIR invoicing (RA 11976, the Ease of Paying Taxes Act, and RR 7-2024)
replaced the official receipt with an invoice as the principal document.
A VAT invoice shows that the seller is VAT-registered, the seller's TIN,
VAT as its own amount, and the split of VATable, VAT-exempt and
zero-rated sales. The printer already shows tax on each line and groups
lines by rate. It cannot print those three buckets as separate totals:
exempt and zero-rated are both a 0% line. Post them as their own lines.
This pack does not make the print a BIR-accredited invoice (CAS, POS
or EIS).

GCash and Maya settle like a card through the acquirer, or like a bank
transfer. Book them as Card or Bank Transfer, the same way Indonesia
books QRIS. They are not a separate till bucket.

Sources (checked 2026-11-16):
- RA 12023, NIRC Section 108(A), 12% on hotel and restaurant services:
  https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/2/97876
- BIR Revenue Regulations No. 3-2024, 12% of gross sales excluding VAT,
  and the Section 109(CC) threshold:
  https://www.ntrc.gov.ph/images/BIR/RR/2024/RR%20No.3-%202024.pdf
- NIRC Section 116, 3% percentage tax. The 1% CREATE rate applied only
  from 1 July 2020 to 30 June 2023
- BIR Revenue Regulations No. 7-2024, invoicing under RA 11976:
  https://taxacctgcenter.ph/revenue-regulations-no-7-2024/
- BIR Revenue Regulations No. 7-2010 (RA 9994) and No. 5-2017 (RA 10754):
  https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/10/55830
  https://ncda.gov.ph/disability-laws/implementing-rules-and-regulations-irr/revenue-regulations-no-5-2017-rules-and-regulations-implementing-republic-act-no-10754/
- RA 7160, Local Government Code, Sections 140 and 143
- Bangko Sentral ng Pilipinas, coins and notes in circulation:
  https://www.bsp.gov.ph/SitePages/CoinsAndNotes/CoinsAndNotes.aspx

Assumptions: a Filipino hotel operator should confirm the labels, whether
the house is VAT-registered, and any city guest fee. The CPI adjustment
of the VAT threshold is not encoded. EIS filing, a Filipino privacy
notice, and posting the senior citizen or PWD discount from the folio
are out of scope.
"""

from decimal import ROUND_HALF_UP, Decimal

import frappe

DEFAULT_VAT = Decimal("12")
# NIRC Section 116, for a non-VAT seller. Not the rate a new property uses.
PERCENTAGE_TAX = Decimal("3")
# RA 9994 / RA 10754. Applied by senior_pwd_amounts, not by the folio writer.
SENIOR_PWD_DISCOUNT = Decimal("20")

DEFAULT_CURRENCY = "PHP"
# foreign money guests bring most; Settings, Finance, Exchange rates can change it
FX_CURRENCIES = ["USD", "EUR", "JPY", "KRW", "CNY", "AUD", "SGD", "HKD"]
DEFAULT_TIMEZONE = "Asia/Manila"
DEFAULT_NATIONALITY = "Filipino"
# a passport or ID card MRZ names the country by this code
HOME_COUNTRY_ISO3 = "PHL"
# named in the guest privacy notice (Data Privacy Act of 2012, RA 10173)
PRIVACY_AUTHORITY = "the National Privacy Commission"
ID_TYPES = [
	"PhilSys National ID",
	"Passport",
	"Driver's License",
	"UMID",
	"SSS",
	"PRC",
	"PhilHealth",
	"Postal ID",
	"Senior Citizen ID",
	"PWD ID",
	"ACR I-Card",
	"Other",
]
ID_TYPE_HINTS = {
	"PhilSys National ID": "PhilID. A printed or digital copy is fine.",
	"Senior Citizen ID": "OSCA ID number. The 20% discount and VAT exemption are posted by hand.",
	"PWD ID": "PWD ID number. The 20% discount and VAT exemption are posted by hand.",
	"ACR I-Card": "For a foreign resident.",
}
# GCash and Maya settle like a card (or a bank transfer). Book Card or
# Bank Transfer; they are not their own till bucket.
PAYMENT_MODES = ["Cash", "Card", "Bank Transfer"]
# NGC notes still in circulation, including the 200-piso and 20-piso notes
# BSP no longer prints, plus NGC coins a till actually counts. The 1-sentimo
# and the older 10-sentimo remain legal tender and are not listed.
CASH_DENOMINATIONS = (1000, 500, 200, 100, 50, 20, 10, 5, 1, 0.25, 0.05)


def _money(value) -> Decimal:
	return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_room_tax(property, room_type_doc, nightly_rate) -> Decimal:
	"""Flat VAT. No slabs. An unset percent (Frappe stores a blank as 0)
	means the statutory 12%. A non-VAT house that shows percentage tax
	types 3."""
	v = room_type_doc.get("tax_percent") if room_type_doc else None
	return Decimal(str(v)) if v else DEFAULT_VAT


def fnb_tax_rate(property) -> float:
	"""Hotel restaurants take the same rate as the rooms. A house that set
	a room type (a non-VAT 3%, for example) carries that rate into F&B."""
	if property:
		rates = frappe.get_all(
			"Room Type", filters={"property": property, "disabled": 0}, pluck="tax_percent", limit=5
		)
		first = next((r for r in rates if r), None)
		if first:
			return float(first)
	return float(DEFAULT_VAT)


def tax_rate_options(property) -> list:
	# 0: VAT-exempt or zero-rated (the printer cannot tell those apart)
	# 3: Section 116 percentage tax, only for a non-VAT seller
	# 12: standard VAT
	return [0, int(PERCENTAGE_TAX), int(DEFAULT_VAT)]


def senior_pwd_amounts(vat_inclusive) -> dict:
	"""BIR senior citizen / PWD computation for a VAT-registered seller.

	`vat_inclusive` is the VAT-inclusive price of that guest's own
	consumption (RR 7-2010, RR 5-2017; the worked example in RMC 38-2012).
	Remove 12% VAT, then take 20% off the VAT-exclusive amount. The sale
	is VAT-exempt: tax_rate is 0, and vat_exclusive is the VAT-exempt sale
	to show before the discount. The guest pays amount_due.

	Nothing in core calls this. Post the discount and a 0% line by hand.
	Split a shared bill down to the eligible portion first. A non-VAT
	seller does not strip VAT: the 20% is on the price charged, and
	percentage tax is still the seller's. This function does not do that
	case.
	"""
	gross = _money(vat_inclusive)
	exclusive = _money(gross / (1 + DEFAULT_VAT / Decimal("100")))
	discount = _money(exclusive * SENIOR_PWD_DISCOUNT / Decimal("100"))
	return {
		"vat_inclusive": gross,
		"vat": _money(gross - exclusive),
		"vat_exclusive": exclusive,
		"discount_percent": SENIOR_PWD_DISCOUNT,
		"discount": discount,
		"amount_due": _money(exclusive - discount),
		"tax_rate": Decimal("0"),
	}


def invoice_context(prop_doc) -> dict:
	return {
		"tax_label": "VAT",
		"tax_id_label": "TIN",
		"service_code": None,
		"sac": None,
		"place_of_supply": prop_doc.get("city") or prop_doc.get("state"),
		# national VAT, one line. Exempt and zero-rated stay 0% lines.
		"split": [("vat", Decimal("1"))],
		"footer": "TIN is the seller's tax ID. VAT is printed apart from "
		"the VAT-exclusive price; keep VATable, VAT-exempt and "
		"zero-rated sales on separate lines. Senior citizen and "
		"PWD consumption is VAT-exempt, with 20% off the "
		"VAT-exclusive price (RA 9994, RA 10754). A non-VAT seller "
		"must not present this print as a VAT invoice. Valid for "
		"input VAT only if this property's invoicing is BIR-accredited.",
	}


def locale(prop_doc) -> dict:
	currency = prop_doc.get("currency") or DEFAULT_CURRENCY
	# a property that bills in another currency must not inherit the peso sign
	symbol = "₱" if currency == DEFAULT_CURRENCY else f"{currency} "
	return {
		"currency_symbol": symbol,
		"locale": "en-PH",
		"currency": currency,
		"tax_label": "VAT",
		"tax_id_label": "TIN",
		"tax_rates": tax_rate_options(prop_doc.get("name")),
	}
