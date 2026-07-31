"""India localization pack: GST (slab / fixed), SAC 996311, GSTIN, CGST/SGST,
GSTR-1. The single place the core's Indian tax behaviour lives - reference
implementation for every other country pack."""

from decimal import Decimal

import frappe

FNB_GST = 5.0  # F&B / meal-plan GST rate


def _dec(v):
	return Decimal(str(v or 0))


def calculate_room_tax(property, room_type_doc, nightly_rate) -> Decimal:
	"""GST rate for one room night. Slab mode: the nightly tariff picks the
	slab (<=threshold → low, else high). Fixed mode: the room type percent."""
	prop = frappe.get_cached_doc("Property", property)
	if (prop.get("gst_mode") or "Slab") == "Fixed":
		return _dec(room_type_doc.tax_percent)
	threshold = _dec(prop.get("gst_slab_threshold") or 7500)
	low = _dec(prop.get("gst_rate_low") or 5)
	high = _dec(prop.get("gst_rate_high") or 18)
	return low if _dec(nightly_rate) <= threshold else high


def fnb_tax_rate(property) -> float:
	return FNB_GST


def tax_rate_options(property) -> list:
	return [0, 5, 12, 18, 28]


def invoice_context(prop_doc) -> dict:
	"""Country block for the invoice print. Values chosen to be byte-identical
	to the pre-seam hardcoding in api.folio_invoice."""
	return {
		"tax_label": "GST",
		"tax_id_label": "GSTIN",
		"service_code": {"label": "SAC", "value": "996311"},
		"sac": "996311",
		"place_of_supply": prop_doc.state,
		# CGST/SGST 50/50 split for intra-state accommodation
		"split": [("cgst", Decimal("0.5")), ("sgst", Decimal("0.5"))],
		"footer": "This is a computer-generated tax invoice under the GST Act.",
	}


# What each kind of charge actually is, in the government's vocabulary. A
# bill that mixes a room night, a restaurant cover and a laundry bag has to
# carry three codes, not the accommodation one three times.
SAC_CODES = {
	"Room": "996311",              # room or unit accommodation
	"Early Check-in": "996311",
	"Late Checkout": "996311",
	"Meal Plan": "996311",         # bundled into the accommodation supply
	"Food & Beverage": "996331",   # restaurant / outdoor catering
	"Minibar": "996331",
	"Laundry": "999712",           # washing, cleaning and dyeing
	"Spa": "999722",               # physical well-being incl. health club
	"Misc": "999799",              # other services n.e.c.
	# banquet line types
	"Venue Rental": "997212",      # renting of non-residential property
	"Alcohol": "996331",
	"Audio Visual": "997329",      # leasing of other goods
	"Furniture & Setup": "997329",
	"Decor": "998596",             # events, exhibitions, conventions
	"Entertainment": "998553",
	"Staffing": "998519",
	"Stationery": "999799",
	"Accommodation": "996311",
}
DEFAULT_SAC = "999799"


def service_code_for(prop_doc, charge_type: str | None = None) -> dict | None:
	"""The SAC for one line. Discounts and allowances aren't a supply, so
	they carry no code at all."""
	if charge_type in ("Discount", "Allowance"):
		return None
	return {"label": "SAC",
	        "value": SAC_CODES.get(charge_type or "", DEFAULT_SAC)}


def tax_split(prop_doc, buyer_tax_id: str | None = None):
	"""Always CGST + SGST, and that is not an oversight.

	For hotel accommodation the place of supply is the location of the
	property (IGST Act s.12(3)(b)) - so a Delhi company staying in
	Bengaluru is still an intra-state supply and still pays CGST+SGST.
	Emitting IGST because the buyer's GSTIN is from another state is a
	common and expensive mistake; we don't make it.

	The buyer's state is still worth surfacing (see `interstate_buyer`) -
	it's the flag an accountant wants when the bill covers something that
	ISN'T accommodation, like outdoor catering at the client's own venue.
	"""
	return [("cgst", Decimal("0.5")), ("sgst", Decimal("0.5"))]


def state_code(gstin: str | None) -> str | None:
	"""The first two digits of a GSTIN are the state. Cheap way to know
	where a corporate buyer is registered without a second address field."""
	gstin = (gstin or "").strip()
	return gstin[:2] if len(gstin) >= 2 and gstin[:2].isdigit() else None


def amount_in_words(prop_doc, amount) -> str:
	from kamra.localization.words import amount_in_words as spell

	return spell(amount, prop_doc.get("currency") or "INR", indian=True)


def locale(prop_doc) -> dict:
	return {
		"currency_symbol": "₹",
		"locale": "en-IN",
		"currency": prop_doc.get("currency") or "INR",
		"tax_label": "GST",
		"tax_id_label": "GSTIN",
		"tax_rates": tax_rate_options(prop_doc.name),
	}
