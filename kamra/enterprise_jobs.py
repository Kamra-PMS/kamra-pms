# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Scheduled Enterprise work. Community properties are skipped."""

from __future__ import annotations

import frappe


def _properties() -> list[str]:
	return frappe.get_all("Property", filters={"disabled": 0}, pluck="name")


def morning():
	"""06:00: welcomes, surveys, arrival-priority cleans, maintenance."""
	from kamra.enterprise import run_morning
	for prop in _properties():
		try:
			run_morning(prop)
		except Exception:
			frappe.log_error(title=f"Enterprise morning {prop}")


def after_audit():
	"""04:30: anomaly scan and ERPNext sync for yesterday."""
	from kamra.enterprise import run_after_audit
	for prop in _properties():
		try:
			run_after_audit(prop)
		except Exception:
			frappe.log_error(title=f"Enterprise after audit {prop}")
