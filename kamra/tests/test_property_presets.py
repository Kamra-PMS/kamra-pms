# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Unit tests for property_kind presets (ADR-005)."""

from kamra.property_presets import (
	KIND_HOTEL,
	KIND_STR,
	STR_MODULES,
	apply_kind_defaults,
	normalize_kind,
	skip_meal_plans,
)


def test_normalize_blank_is_hotel():
	assert normalize_kind(None) == KIND_HOTEL
	assert normalize_kind("") == KIND_HOTEL
	assert normalize_kind("Homestay") == KIND_HOTEL


def test_str_defaults_overbooking_and_modules():
	out = apply_kind_defaults({"property_name": "Sunset Villas", "property_kind": KIND_STR})
	assert out["property_kind"] == KIND_STR
	assert out["overbooking_pct"] == 0
	assert out["enabled_modules"] == ",".join(STR_MODULES)


def test_str_preserves_operator_overrides():
	out = apply_kind_defaults({
		"property_kind": KIND_STR,
		"overbooking_pct": 5,
		"enabled_modules": "front-desk,admin,fnb",
	})
	assert out["overbooking_pct"] == 5
	assert out["enabled_modules"] == "front-desk,admin,fnb"


def test_hotel_leaves_modules_empty():
	out = apply_kind_defaults({"property_kind": KIND_HOTEL})
	assert out["property_kind"] == KIND_HOTEL
	assert "enabled_modules" not in out or not out.get("enabled_modules")


def test_skip_meal_plans_only_for_str():
	assert skip_meal_plans(KIND_STR) is True
	assert skip_meal_plans(KIND_HOTEL) is False
