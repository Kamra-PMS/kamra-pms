"""Which UI languages this site offers.

Hotel Admins switch them under Settings, Languages. The list is the whole
site (sign-in, the staff app, booking pages and self check-in), not one
property. A property's booking language only picks which enabled language
guests see first. See kamra.ui_languages for the catalog rules.
"""

from __future__ import annotations

import json

import frappe
from frappe import _

from kamra.authz import require_roles
from kamra.ui_languages import (
	UnknownLanguage,
	catalog_codes,
	clean_requested_disabled,
	enabled_list,
	language_label,
	load_catalog,
	parse_stored_disabled,
	resolve_language,
)

DISABLED_KEY = "kamra_disabled_ui_languages"

_catalog: list[dict] | None = None


def catalog() -> list[dict]:
	global _catalog
	if _catalog is None:
		_catalog = load_catalog()
	return _catalog


def known_codes() -> list[str]:
	return catalog_codes(catalog())


def disabled_codes() -> list[str]:
	"""Codes switched off. Missing or unreadable storage means none, so an
	upgrade leaves every current language on."""
	try:
		raw = frappe.db.get_default(DISABLED_KEY)
	except Exception:
		return []
	return parse_stored_disabled(raw, known_codes())


def enabled_codes() -> list[str]:
	return enabled_list(known_codes(), disabled_codes())


def language_enabled(code: str | None) -> bool:
	if not code:
		return False
	key = str(code).strip().lower()
	return any(c.lower() == key for c in enabled_codes())


def resolve_saved(saved: str | None, *fallbacks: str | None) -> str:
	"""A saved UI language that is still on, else a fallback, else English."""
	return resolve_language(saved, enabled_codes(), *fallbacks)


def public_booking_language(code: str | None) -> str | None:
	"""The property's booking language when guests may still be shown it.

	None means the guest's browser language (the page then keeps it only
	when that language is on).
	"""
	raw = (code or "").strip()
	if not raw or not language_enabled(raw):
		return None
	return resolve_language(raw, enabled_codes())


def assert_enabled_language(code: str) -> str:
	"""Refuse a booking language that is unknown or switched off.

	Empty is allowed (the guest's browser). Returns the catalogue code.
	"""
	raw = (code or "").strip()
	if not raw:
		return ""
	known = known_codes()
	match = next((c for c in known if c.lower() == raw.lower()), None)
	if not match:
		frappe.throw(_("{0} is not a Kamra language.").format(language_label(raw, catalog())))
	if match not in enabled_list(known, disabled_codes()):
		frappe.throw(_("{0} is switched off. Turn it on from Languages in Settings.").format(
			language_label(match, catalog())))
	return match


def _as_requested(disabled):
	try:
		return clean_requested_disabled(disabled, known_codes())
	except UnknownLanguage as exc:
		if not exc.code:
			frappe.throw(_("Send a list of language codes."))
		frappe.throw(_("{0} is not a Kamra language.").format(exc.code))
		raise


@frappe.whitelist(allow_guest=True)
def enabled_ui_languages() -> dict:
	"""Language codes sign-in, the staff app and guest pages may offer.

	English is always included. With nothing saved, every shipped language
	is included.
	"""
	return {"enabled": enabled_codes()}


@frappe.whitelist(methods=["POST"])
@require_roles()
def set_disabled_ui_languages(disabled=None) -> dict:
	"""Switch UI languages off for the whole site. Hotel Admin.

	`disabled` is a JSON list of language codes to hide. English is ignored.
	A shipped language left off this list stays on, including one added
	after the list was last saved.
	"""
	clean = _as_requested(disabled)
	before = disabled_codes()
	if clean != before:
		frappe.db.set_default(DISABLED_KEY, json.dumps(clean))
		from kamra.savings import log_action
		log_action(
			"ui_languages_changed",
			rationale="UI languages switched off: " + (", ".join(clean) if clean else "none"),
			before_snapshot={"disabled": before},
			after_snapshot={"disabled": clean},
		)
	return {"ok": True, "enabled": enabled_codes(), "disabled": clean}
