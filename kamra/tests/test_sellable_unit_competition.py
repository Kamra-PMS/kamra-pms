# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Unit-level tests for Sellable Unit competition math (ADR-004).

These do not require a running Frappe site — they document the algorithm
used by kamra.siu.availability so regressions are caught early.
"""

from __future__ import annotations


def competition_sellable(
	*,
	unit_kind: str,
	individual_booked: int,
	whole_booked: int,
	individual_total: int,
) -> int:
	"""Mirror of ADR-004 night rules for one SIU."""
	if unit_kind == "whole_property":
		return 1 if individual_booked == 0 and whole_booked == 0 else 0
	if unit_kind == "individual":
		return 0 if whole_booked else 1  # per-unit booking handled separately
	return 0


def test_whole_property_free_when_nothing_booked():
	assert competition_sellable(
		unit_kind="whole_property",
		individual_booked=0,
		whole_booked=0,
		individual_total=5,
	) == 1


def test_whole_property_blocked_by_any_individual():
	assert competition_sellable(
		unit_kind="whole_property",
		individual_booked=1,
		whole_booked=0,
		individual_total=5,
	) == 0


def test_whole_property_blocked_by_itself():
	assert competition_sellable(
		unit_kind="whole_property",
		individual_booked=0,
		whole_booked=1,
		individual_total=5,
	) == 0


def test_individual_blocked_when_estate_booked():
	assert competition_sellable(
		unit_kind="individual",
		individual_booked=0,
		whole_booked=1,
		individual_total=5,
	) == 0


def test_individual_free_when_estate_free():
	assert competition_sellable(
		unit_kind="individual",
		individual_booked=0,
		whole_booked=0,
		individual_total=5,
	) == 1
