# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Property kind presets (ADR-005).

``property_kind`` is a setup / presentation preset only. It must not fork
pricing, availability, deposits, or channel sync. Those stay on explicit
SIU / policy fields.
"""

from __future__ import annotations

# Values stored on Property.property_kind
KIND_HOTEL = "Hotel"
KIND_STR = "Short Term Rental"
KINDS = (KIND_HOTEL, KIND_STR)

# Module catalogs match kamra.api.ALL_MODULES.
HOTEL_MODULES = (
	"front-desk",
	"housekeeping",
	"operations",
	"fnb",
	"events",
	"revenue",
	"finance",
	"booking-engine",
	"admin",
)

STR_MODULES = (
	"front-desk",
	"housekeeping",
	"revenue",
	"finance",
	"booking-engine",
	"admin",
)


def normalize_kind(kind: str | None) -> str:
	k = (kind or "").strip()
	if k in KINDS:
		return k
	return KIND_HOTEL


def apply_kind_defaults(property_fields: dict) -> dict:
	"""Mutate (and return) the property payload with kind-aware defaults.

	Only fills keys that are missing / empty so operator overrides win.
	"""
	kind = normalize_kind(property_fields.get("property_kind"))
	property_fields["property_kind"] = kind

	if kind == KIND_STR:
		property_fields.setdefault("overbooking_pct", 0)
		if property_fields.get("overbooking_pct") in (None, ""):
			property_fields["overbooking_pct"] = 0
		# Empty enabled_modules means "all" for hotels; STR must set an
		# explicit list so F&B / events / operations stay off by default.
		if not (property_fields.get("enabled_modules") or "").strip():
			property_fields["enabled_modules"] = ",".join(STR_MODULES)
		# Day-use calendar windows off by default for vacation rentals.
		if not property_fields.get("hourly_view_start"):
			property_fields["hourly_view_start"] = ""
		if not property_fields.get("hourly_view_end"):
			property_fields["hourly_view_end"] = ""
	else:
		# Hotel: leave modules empty (= all) unless the caller set them.
		property_fields.setdefault("property_kind", KIND_HOTEL)

	return property_fields


def skip_meal_plans(kind: str | None) -> bool:
	return normalize_kind(kind) == KIND_STR
