"""Backfill listing_slug and location_slug on Room Types for public /stay URLs."""

import frappe

from kamra.booking_slugs import slugify, unique_listing_slug


def execute():
	if not frappe.db.has_column("Room Type", "listing_slug"):
		return

	for name in frappe.get_all("Room Type", pluck="name"):
		rt = frappe.get_doc("Room Type", name)
		updates = {}
		if not (rt.get("listing_slug") or "").strip():
			updates["listing_slug"] = unique_listing_slug(
				rt.property, rt.room_type_name, exclude=rt.name,
			)
		loc = (rt.get("location_name") or "").strip()
		if loc and not (rt.get("location_slug") or "").strip():
			updates["location_slug"] = slugify(loc)
		if updates:
			frappe.db.set_value("Room Type", name, updates, update_modified=False)

	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- migration patch runs outside the request cycle; explicit commit persists the backfill
