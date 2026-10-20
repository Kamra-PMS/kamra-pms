"""Seed revenue demo data: seasons, rate guardrails, vouchers, meal plans.

Sample rows include both Active and Disabled so a demo user can open the
lists, toggle Disabled (activate / deactivate), and see how pricing rails
and discount codes behave. CRUD stays available - these are starters.

Run with:
    bench --site kamra.localhost execute kamra.scripts.seed_v1.execute

Idempotent: keyed creates; re-running fills anything that is missing.
"""

from __future__ import annotations

import frappe
from frappe.utils import add_days, nowdate

PROPERTY = "Kamra Demo Palace"


def upsert(doctype: str, keys: dict, values: dict) -> str | None:
	name = frappe.db.exists(doctype, keys)
	if name:
		return name
	doc = frappe.get_doc({"doctype": doctype, **keys, **values})
	doc.insert(ignore_permissions=True)
	print(f"created {doctype}: {doc.name}")
	return doc.name


def room_type(code: str) -> str | None:
	return frappe.db.get_value(
		"Room Type", {"property": PROPERTY, "room_type_code": code}, "name"
	)


def execute():
	if not frappe.db.exists("Property", PROPERTY):
		print("Run seed_demo first.")
		return

	today = nowdate()
	std = room_type("STD")
	dlx = room_type("DLX")
	ste = room_type("STE")

	# ── Meal plans ────────────────────────────────────────────────────────
	upsert(
		"Meal Plan",
		{"property": PROPERTY, "code": "EP"},
		{"label": "Room Only", "price_per_adult": 0, "price_per_child": 0},
	)
	upsert(
		"Meal Plan",
		{"property": PROPERTY, "code": "CP"},
		{
			"label": "Breakfast Included",
			"price_per_adult": 350,
			"price_per_child": 200,
			"is_default": 1,
		},
	)
	upsert(
		"Meal Plan",
		{"property": PROPERTY, "code": "MAP"},
		{
			"label": "Breakfast + Dinner",
			"price_per_adult": 800,
			"price_per_child": 450,
		},
	)

	# ── Seasons (active + disabled samples) ───────────────────────────────
	# Active weekend uplift - fri/sat for the next two months
	upsert(
		"Season",
		{"property": PROPERTY, "season_name": "Weekend Uplift"},
		{
			"start_date": today,
			"end_date": add_days(today, 60),
			"adjustment_type": "Percent",
			"adjustment_value": 15,
			"days_of_week": "fri, sat",
			"priority": 5,
			"disabled": 0,
		},
	)
	# Active peak window with a minimum stay
	upsert(
		"Season",
		{"property": PROPERTY, "season_name": "Festival Peak"},
		{
			"start_date": add_days(today, 14),
			"end_date": add_days(today, 21),
			"adjustment_type": "Percent",
			"adjustment_value": 25,
			"priority": 20,
			"minimum_nights": 2,
			"non_refundable": 1,
			"disabled": 0,
		},
	)
	# Absolute suite rate for a short window (room-type scoped)
	if ste:
		upsert(
			"Season",
			{"property": PROPERTY, "season_name": "Suite Showcase Rate"},
			{
				"room_type": ste,
				"start_date": add_days(today, 7),
				"end_date": add_days(today, 10),
				"adjustment_type": "Absolute",
				"adjustment_value": 9999,
				"priority": 30,
				"disabled": 0,
			},
		)
	# Soft midweek discount (amount)
	upsert(
		"Season",
		{"property": PROPERTY, "season_name": "Midweek Soften"},
		{
			"start_date": today,
			"end_date": add_days(today, 45),
			"adjustment_type": "Amount",
			"adjustment_value": -200,
			"days_of_week": "tue, wed",
			"priority": 3,
			"disabled": 0,
		},
	)
	# Disabled - open the form and clear Disabled to activate
	upsert(
		"Season",
		{"property": PROPERTY, "season_name": "Monsoon (paused)"},
		{
			"start_date": add_days(today, 30),
			"end_date": add_days(today, 90),
			"adjustment_type": "Percent",
			"adjustment_value": -10,
			"priority": 8,
			"disabled": 1,
		},
	)

	# ── Rate guardrails ───────────────────────────────────────────────────
	upsert(
		"Rate Guardrail",
		{"property": PROPERTY, "floor_price": 2000, "ceiling_price": 12000},
		{"days_of_week": "", "disabled": 0},
	)
	if dlx:
		# Weekend floor sits above the midweek property rail
		upsert(
			"Rate Guardrail",
			{
				"property": PROPERTY,
				"room_type": dlx,
				"floor_price": 4500,
				"ceiling_price": 14000,
			},
			{"days_of_week": "fri, sat", "disabled": 0},
		)
	if std:
		upsert(
			"Rate Guardrail",
			{
				"property": PROPERTY,
				"room_type": std,
				"floor_price": 2200,
				"ceiling_price": 8000,
			},
			{"disabled": 0},
		)
	# Disabled experimental rail - toggle Disabled off to enforce it
	upsert(
		"Rate Guardrail",
		{"property": PROPERTY, "floor_price": 1500, "ceiling_price": 5000},
		{"days_of_week": "mon, tue, wed, thu", "disabled": 1},
	)

	# ── Discount vouchers ─────────────────────────────────────────────────
	upsert(
		"Discount Voucher",
		{"property": PROPERTY, "voucher_code": "WELCOME10"},
		{
			"discount_type": "Percent",
			"value": 10,
			"min_nights": 1,
			"max_uses": 100,
			"valid_from": today,
			"valid_to": add_days(today, 90),
			"disabled": 0,
		},
	)
	upsert(
		"Discount Voucher",
		{"property": PROPERTY, "voucher_code": "LONGSTAY500"},
		{
			"discount_type": "Amount",
			"value": 500,
			"min_nights": 3,
			"max_uses": 0,
			"valid_from": today,
			"valid_to": add_days(today, 180),
			"disabled": 0,
		},
	)
	upsert(
		"Discount Voucher",
		{"property": PROPERTY, "voucher_code": "FLASH25"},
		{
			"discount_type": "Percent",
			"value": 25,
			"min_nights": 1,
			"max_uses": 20,
			"valid_from": today,
			"valid_to": add_days(today, 14),
			"disabled": 0,
		},
	)
	# Nearly used up - shows times_used vs max_uses
	name = upsert(
		"Discount Voucher",
		{"property": PROPERTY, "voucher_code": "EARLYBIRD"},
		{
			"discount_type": "Percent",
			"value": 15,
			"min_nights": 2,
			"max_uses": 10,
			"valid_from": add_days(today, -30),
			"valid_to": add_days(today, 60),
			"disabled": 0,
		},
	)
	if name and not frappe.db.get_value("Discount Voucher", name, "times_used"):
		frappe.db.set_value("Discount Voucher", name, "times_used", 7)

	# Deactivated - clear Disabled to publish again
	upsert(
		"Discount Voucher",
		{"property": PROPERTY, "voucher_code": "STAFFCOMP"},
		{
			"discount_type": "Percent",
			"value": 50,
			"min_nights": 1,
			"max_uses": 5,
			"valid_from": today,
			"valid_to": add_days(today, 365),
			"disabled": 1,
		},
	)
	# Past validity - disabled so it stays out of the live quote path
	upsert(
		"Discount Voucher",
		{"property": PROPERTY, "voucher_code": "NY2025"},
		{
			"discount_type": "Percent",
			"value": 20,
			"min_nights": 1,
			"max_uses": 50,
			"valid_from": add_days(today, -120),
			"valid_to": add_days(today, -30),
			"disabled": 1,
		},
	)

	# ── Rate plans beyond BAR (if BAR already seeded by seed_demo) ───────
	upsert(
		"Rate Plan",
		{"property": PROPERTY, "code": "NRF"},
		{
			"rate_plan_name": "Non-refundable",
			"modifier_type": "Percent",
			"modifier_value": -10,
			"cancellation_policy": "Non-refundable",
			"is_default": 0,
			"disabled": 0,
		},
	)
	upsert(
		"Rate Plan",
		{"property": PROPERTY, "code": "CORP"},
		{
			"rate_plan_name": "Corporate negotiated",
			"modifier_type": "Percent",
			"modifier_value": -8,
			"is_default": 0,
			"disabled": 0,
		},
	)
	# Soft-closed plan - Disabled means it is not offered at booking
	upsert(
		"Rate Plan",
		{"property": PROPERTY, "code": "PKG"},
		{
			"rate_plan_name": "Package (unpublished)",
			"modifier_type": "Percent",
			"modifier_value": -5,
			"is_default": 0,
			"disabled": 1,
		},
	)

	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- batch/seed/migration script
	print("Revenue demo data ready (seasons, guardrails, vouchers, rate plans).")
