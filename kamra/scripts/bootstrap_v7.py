"""Schema v7 — self check-in (PRD FR-20 v0: pre-arrival details, no
external KYC vendor yet).

Run via bench console:
    from kamra.scripts.bootstrap_v7 import execute; execute()
"""

import frappe

from kamra.scripts.bootstrap_v5 import add_fields


def execute():
	add_fields("Reservation", [
		dict(fieldname="sb_precheckin", fieldtype="Section Break",
		     label="Pre-arrival Check-in", insert_after="special_requests"),
		dict(fieldname="precheckin_token", fieldtype="Data", hidden=1,
		     label="Pre-checkin Token", insert_after="sb_precheckin",
		     no_copy=1),
		dict(fieldname="precheckin_status", fieldtype="Select",
		     options="Not Started\nSubmitted\nVerified",
		     default="Not Started", label="Pre-checkin",
		     insert_after="precheckin_token", in_standard_filter=1),
		dict(fieldname="precheckin_on", fieldtype="Datetime", read_only=1,
		     label="Pre-checkin Submitted On",
		     insert_after="precheckin_status"),
		dict(fieldname="eta", fieldtype="Data", label="Guest ETA",
		     insert_after="precheckin_on",
		     description="Arrival time the guest told us, e.g. 14:30 or 'late night'"),
	])

	add_fields("Guest", [
		dict(fieldname="address_line", fieldtype="Data", label="Address",
		     insert_after="nationality"),
		dict(fieldname="city", fieldtype="Data", label="City",
		     insert_after="address_line"),
	])

	# backfill tokens for existing reservations
	for name in frappe.get_all(
		"Reservation", filters={"precheckin_token": ("in", ["", None])},
		pluck="name",
	):
		frappe.db.set_value(
			"Reservation", name, "precheckin_token",
			frappe.generate_hash(length=24), update_modified=False,
		)
	print("tokens backfilled")

	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- batch/seed/migration script runs outside the request cycle; explicit commit persists the staged writes
	print("Kamra v7 schema (self check-in) ready.")
