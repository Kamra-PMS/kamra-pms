"""Phone numbers that arrive from outside the desk (OTAs, the public booking
API, imports, the CRS, setup) in one shape: E.164, read with the property's
country (#468).

The desk's own phone picker already sends E.164. Everything else can carry
a local number ("0772123456"), a bare national one, or a number from
another country. normalise() keeps a valid international number as it is,
reads a local one with the property's country, and never refuses: a number
it can't read is kept exactly as typed and the caller is told why, so a
booking is never lost over a phone number.
"""

from __future__ import annotations

import frappe

import phonenumbers

# what a caller gets back when a number is kept as typed
NO_COUNTRY = "no_country"  # a local number, and no country to read it with
INVALID = "invalid"  # not a phone number for that country


def region_for(property: str | None) -> str | None:
	"""The property's country as an ISO region ("UG", "IN"), or None."""
	if not property:
		return None
	country = frappe.get_cached_value("Property", property, "country")
	if not country:
		return None
	code = frappe.get_cached_value("Country", country, "code")
	return code.upper() if code else None


def normalise(raw: str | None, region: str | None) -> tuple[str, str | None]:
	"""(value to store, problem). Blank stays blank. A number that parses
	and is valid comes back as E.164; anything else comes back as typed
	(trimmed) with NO_COUNTRY or INVALID."""
	text = (raw or "").strip()
	if not text:
		return "", None
	dialled = "+" + text[2:].lstrip() if text.startswith("00") else text
	international = dialled.startswith("+")
	if not international and not region:
		return text, NO_COUNTRY
	try:
		number = phonenumbers.parse(dialled, None if international else region)
	except phonenumbers.NumberParseException:
		return text, INVALID
	if not phonenumbers.is_valid_number(number):
		return text, INVALID
	return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164), None


def for_property(raw: str | None, property: str | None) -> tuple[str, str | None]:
	"""normalise() with the property's country."""
	return normalise(raw, region_for(property))


def matching(raw: str | None, property: str | None = None) -> tuple:
	"""A Guest filter value that finds a profile by phone whether it was
	saved normalised or (before #468) as typed: ("in", {typed, E.164})."""
	typed = (raw or "").strip()
	return ("in", {typed, for_property(typed, property)[0]})


def flag(problem: str | None, doctype: str, name: str, property: str | None,
         where: str) -> None:
	"""Leave a reviewable note when a number was kept as typed. The note
	never carries the number itself (contact details stay out of logs)."""
	if not problem:
		return
	why = ("the property has no country to read a local number with"
	       if problem == NO_COUNTRY else "it isn't a valid number for that country")
	from kamra.savings import log_action
	log_action("phone_needs_review", doctype, name, property,
	           rationale=f"Phone from {where} kept as typed: {why}. "
	                     "Check it on the guest profile.")

