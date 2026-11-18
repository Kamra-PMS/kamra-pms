"""Germany localization pack — requested by the community
(github.com/Kamra-PMS/kamra-pms/issues/623, @andreasnewuser).

German hotel accommodation is a reduced-rate VAT supply (7% MwSt /
Umsatzsteuer) under §12 Abs. 2 Nr. 11 UStG. Breakfast, minibar, spa and
most other guest services stay at the standard 19%. So this pack splits
rates the same way Malaysia splits SST:

  - the room rate comes from the Room Type's tax percent (default 7)
  - hotel F&B and guest services use the statutory 19%
  - city / overnight taxes (Übernachtungssteuer, Beherbergungssteuer,
    Kurtaxe) are municipal levies on the guest, not VAT - post them as
    folio charge lines; the pack only supplies the label
  - invoices quote the USt-IdNr. (or Steuernummer) and use MwSt wording

Kleinunternehmer (§19 UStG), DATEV chart codes, and the full set of
mandatory German invoice fields (laufende Rechnungsnummer beyond Kamra's
own series, Leistungsdatum rules) are out of scope for this first pack -
a follow-up can wire them without changing the seam.

Sources (checked 2026-11-18):
- §12 Abs. 2 Nr. 11 UStG (reduced rate for short-term lodging)
- §12 Abs. 1 UStG (standard 19%)
"""

from decimal import Decimal

DEFAULT_VAT = Decimal("7")    # short-term lodging
STANDARD_VAT = Decimal("19")  # F&B, spa, laundry, most other services

DEFAULT_CURRENCY = "EUR"
# foreign money guests bring most; Settings, Finance, Exchange rates can change it
FX_CURRENCIES = ["USD", "GBP", "CHF", "PLN", "CZK", "DKK", "SEK", "NOK"]
DEFAULT_TIMEZONE = "Europe/Berlin"
DEFAULT_NATIONALITY = "German"
# a passport or ID card MRZ names the country by this code
HOME_COUNTRY_ISO3 = "DEU"
# named in the guest privacy notice
PRIVACY_AUTHORITY = "the Federal Commissioner for Data Protection and Freedom of Information (BfDI)"
ID_TYPES = ["Personalausweis", "Passport", "Residence Permit", "Driving License", "Other"]
PAYMENT_MODES = ["Cash", "Card", "Bank Transfer"]
# notes and coins the till counts at close, largest first
CASH_DENOMINATIONS = (500, 200, 100, 50, 20, 10, 5, 2, 1, 0.5, 0.2, 0.1, 0.05, 0.02, 0.01)
# municipal overnight / visitor levy - operator configures amount per property
ROOM_LEVY_LABEL = "City tax"
NOTICE_LANGUAGES = ["de", "en"]
INVOICE_TITLE = "Rechnung"


def calculate_room_tax(property, room_type_doc, nightly_rate) -> Decimal:
	"""Reduced MwSt on lodging - unset means the statutory 7%."""
	v = room_type_doc.get("tax_percent") if room_type_doc else None
	return Decimal(str(v)) if v else DEFAULT_VAT


def fnb_tax_rate(property) -> float:
	"""Breakfast and restaurant supplies stay at the standard 19% -
	deliberately NOT the room rate."""
	return float(STANDARD_VAT)


def services_tax_rate(property) -> float:
	"""Laundry, spa and other guest services: standard 19%."""
	return float(STANDARD_VAT)


def tax_rate_options(property) -> list:
	return [0, 7, 19]


def invoice_context(prop_doc) -> dict:
	return {
		"tax_label": "MwSt (Umsatzsteuer)",
		"tax_id_label": "USt-IdNr.",
		"service_code": None,
		"sac": None,
		"place_of_supply": prop_doc.get("city") or prop_doc.get("state"),
		# federal VAT, single line (7% nights and 19% extras appear as
		# separate charge lines with their own rates on the folio)
		"split": [("mwst", Decimal("1"))],
		"footer": "City tax / Übernachtungssteuer appears as a separate "
		          "line where the municipality levies it. "
		          "This is a computer-generated invoice. / "
		          "Dies ist eine computererstellte Rechnung.",
	}


def locale(prop_doc) -> dict:
	# € is the pack's desk symbol (same pattern as RM / ฿ / AED ); a property
	# that bills in another currency still keeps that currency code on the doc.
	return {
		"currency_symbol": "€",
		"locale": "de-DE",
		"currency": prop_doc.get("currency") or DEFAULT_CURRENCY,
		"tax_label": "MwSt",
		"tax_id_label": "USt-IdNr.",
		"tax_rates": tax_rate_options(prop_doc.get("name")),
	}
