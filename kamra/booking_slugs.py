"""Public booking URL slugs — listing and site identifiers."""

from __future__ import annotations

import re

import frappe


def slugify(text: str) -> str:
	"""URL-safe slug from a display name."""
	s = (text or "").strip().lower()
	s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
	s = re.sub(r"[\s_]+", "-", s)
	s = re.sub(r"-+", "-", s).strip("-")
	return s or "listing"


def unique_listing_slug(property: str, base: str, exclude: str | None = None) -> str:
	"""Return *base* or base-2, base-3, … unique among room types on *property*."""
	slug = slugify(base)
	if not slug:
		slug = "listing"
	used = set(
		frappe.get_all(
			"Room Type",
			filters={"property": property, "name": ["!=", exclude]} if exclude else {"property": property},
			pluck="listing_slug",
		)
	)
	used.discard(None)
	used.discard("")
	if slug not in used:
		return slug
	for i in range(2, 200):
		candidate = f"{slug}-{i}"
		if candidate not in used:
			return candidate
	return f"{slug}-{frappe.generate_hash(length=6)}"


def ensure_room_type_slugs(room_type: str) -> None:
	"""Backfill listing_slug / location_slug on a Room Type if blank."""
	rt = frappe.get_doc("Room Type", room_type)
	changed = False
	if not (rt.get("listing_slug") or "").strip():
		rt.listing_slug = unique_listing_slug(rt.property, rt.room_type_name, exclude=rt.name)
		changed = True
	loc = (rt.get("location_name") or "").strip()
	if loc and not (rt.get("location_slug") or "").strip():
		rt.location_slug = slugify(loc)
		changed = True
	if changed:
		rt.db_set(
			{
				"listing_slug": rt.listing_slug,
				"location_slug": rt.get("location_slug"),
			},
			update_modified=False,
		)


def resolve_public_slug(slug: str) -> dict:
	"""Resolve a /stay/:slug path to property + listing or site scope."""
	slug = (slug or "").strip().lower()
	if not slug:
		frappe.throw("Listing not found.", frappe.DoesNotExistError)

	rt = frappe.db.get_value(
		"Room Type",
		{"listing_slug": slug, "disabled": 0},
		["name", "property", "room_type_name"],
		as_dict=True,
	)
	if rt:
		prop = frappe.db.get_value(
			"Property", rt.property, ["name", "booking_engine_enabled"], as_dict=True,
		)
		if not prop or not prop.booking_engine_enabled:
			frappe.throw("Listing not found.", frappe.DoesNotExistError)
		return {
			"kind": "listing",
			"property": rt.property,
			"listing_slug": slug,
			"room_type": rt.name,
			"room_type_name": rt.room_type_name,
		}

	site = frappe.db.sql(
		"""
		SELECT DISTINCT property, location_name
		FROM `tabRoom Type`
		WHERE disabled = 0 AND location_slug = %s
		LIMIT 1
		""",
		slug,
		as_dict=True,
	)
	if site:
		prop = frappe.db.get_value(
			"Property", site[0].property, ["name", "booking_engine_enabled"], as_dict=True,
		)
		if not prop or not prop.booking_engine_enabled:
			frappe.throw("Listing not found.", frappe.DoesNotExistError)
		return {
			"kind": "site",
			"property": site[0].property,
			"location_slug": slug,
			"location_name": site[0].location_name,
		}

	frappe.throw("Listing not found.", frappe.DoesNotExistError)
