"""Front-office business date.

Opera advances the business date only after night audit, so a 01:00 charge
still posts to yesterday until the audit rolls the day. Every money and
revenue posting should use get_business_date(property), not nowdate()."""

from __future__ import annotations

import frappe
from frappe.utils import add_days, nowdate


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


MAX_REPORT_DAYS = 92


def report_range_end(start, end=None) -> str:
	"""The last day of a report's date range: `end`, or `start` for a
	one-day report. Refuses a backwards or longer-than-92-day range."""
	from frappe.utils import date_diff

	end = str(end or start)
	span = date_diff(end, start)
	if span < 0:
		frappe.throw("The end date is before the start date.")
	if span >= MAX_REPORT_DAYS:
		frappe.throw(f"Pick a range of {MAX_REPORT_DAYS} days or less.")
	return end
