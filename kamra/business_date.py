"""Front-office business date.

Opera advances the business date only after night audit, so a 01:00 charge
still posts to yesterday until the audit rolls the day. Every money and
revenue posting should use get_business_date(property), not nowdate().

Past dates (before the open business date) need an explicit backdate
permission — Finance / Hotel Admin / System Manager — or
frappe.flags.allow_past_transaction for night audit, go-live, and seeds."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, getdate, nowdate

# Who may post / save a transaction dated before the open business date.
BACKDATE_ROLES = (
	"Finance",
	"Hotel Admin",
	"System Manager",
	"Administrator",
)


def get_business_date(property: str) -> str:
	"""Current business date for a property; falls back to calendar today."""
	if not property:
		return nowdate()
	bd = frappe.db.get_value("Property", property, "business_date")
	return str(bd) if bd else nowdate()


def ensure_business_date(property: str) -> str:
	"""Seed business_date if blank, then return it."""
	bd = frappe.db.get_value("Property", property, "business_date")
	if not bd:
		bd = nowdate()
		frappe.db.set_value("Property", property, "business_date", bd,
		                    update_modified=False)
	return str(bd)


def advance_business_date(property: str, from_date: str | None = None) -> str:
	"""Roll the business date forward by one day after a successful night audit."""
	current = from_date or get_business_date(property)
	nxt = add_days(current, 1)
	frappe.db.set_value("Property", property, "business_date", nxt,
	                    update_modified=False)
	return str(nxt)


def can_backdate(user: str | None = None) -> bool:
	"""True when this user (or a system flag) may use a past business date."""
	if frappe.flags.get("allow_past_transaction"):
		return True
	roles = set(frappe.get_roles(user or frappe.session.user))
	return bool(roles & set(BACKDATE_ROLES))


def assert_transaction_date(
	property: str,
	date: str | None = None,
	*,
	label: str | None = None,
) -> str:
	"""Resolve a transaction date; refuse past business dates without permission.

	Returns the date to use (caller date, or the open business date when omitted).
	"""
	bd = get_business_date(property)
	resolved = str(getdate(date)) if date else bd
	if getdate(resolved) < getdate(bd) and not can_backdate():
		frappe.throw(
			_("{0} {1} is before the business date ({2}). "
			  "Only Finance or Hotel Admin can use a past date.")
			.format(_(label or "Date"), resolved, bd),
			title=_("Past date not allowed"),
		)
	return resolved
