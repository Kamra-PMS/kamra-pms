import frappe

from kamra.siu.units import backfill_property


def execute():
	"""Create Sellable Units for every Room and Villa room type (ADR-001).

	Idempotent: safe to re-run. Existing Hotel behaviour is unchanged —
	availability still falls back to Room SQL when no SIUs exist.
	"""
	if not frappe.db.exists("DocType", "Sellable Unit"):
		return
	result = backfill_property()
	frappe.logger("kamra").info(f"v27 sellable unit backfill: {result}")
	frappe.clear_cache()
