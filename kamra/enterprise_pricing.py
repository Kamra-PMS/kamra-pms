# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Forecast signal that the pricing engine reads when Enterprise auto mode is on.

Community quotes never reach the forecast. Auto mode feeds predicted
occupancy into the existing hurdle tiers. When no tier matches, the open
band in enterprise_logic applies, still inside the rate guardrail.
"""

from __future__ import annotations

from datetime import timedelta

import frappe
from frappe.utils import date_diff, getdate, nowdate

from kamra.enterprise_logic import predict_occupancy_pct


def pricing_occupancy(property: str, day: str, on_books: float) -> tuple[float, bool]:
	"""(occupancy percent for demand tiers, whether the open band may run).

	A forecast error falls back to rooms already sold. Quotes keep working.
	"""
	try:
		if _mode(property) != "auto":
			return float(on_books or 0), False
		return _predicted(property, str(day)[:10], float(on_books or 0)), True
	except Exception:
		frappe.log_error(title="Enterprise pricing signal")
		return float(on_books or 0), False


def preview_dates(property: str, days: int, on_books_for) -> list[dict]:
	"""Predicted occupancy for the next `days` dates.

	`on_books_for(date) -> float` is the live occupancy percent. Kept as a
	callback so this module does not import the pricing engine while the
	pricing engine is calling us.
	"""
	start = getdate(nowdate())
	out = []
	for offset in range(max(1, int(days))):
		day = start + timedelta(days=offset)
		stamp = str(day)
		on_books = float(on_books_for(stamp) or 0)
		predicted = _predicted(property, stamp, on_books) if _mode(property) != "off" else on_books
		# Suggest and auto both show the forecast. Only auto changes quotes,
		# and that decision stays in pricing_occupancy.
		if _mode(property) == "off":
			predicted = on_books
		out.append({
			"date": stamp,
			"on_books": round(on_books, 1),
			"predicted": round(predicted, 1),
			"lead_days": date_diff(stamp, start),
		})
	return out


def _mode(property: str) -> str:
	cache = getattr(frappe.flags, "enterprise_mode", None)
	if cache and cache.get("property") == property:
		return cache["mode"]
	from kamra.edition import is_enterprise
	from kamra.settings import get_setting
	mode = "off"
	if is_enterprise(property):
		mode = get_setting(property, "ent_pricing_mode", "off") or "off"
		if mode not in ("off", "suggest", "auto"):
			mode = "off"
	frappe.flags.enterprise_mode = {"property": property, "mode": mode}
	return mode


def _context(property: str) -> dict:
	cache = getattr(frappe.flags, "enterprise_predict", None)
	if cache and cache.get("property") == property:
		return cache
	sellable = frappe.db.count("Room", {"property": property}) or 0
	today = getdate(nowdate())
	start = today - timedelta(days=84)
	rows = frappe.get_all(
		"Reservation",
		filters={
			"property": property,
			"status": ("in", ["Confirmed", "Checked In", "Checked Out"]),
			"check_out_date": (">", str(start)),
		},
		fields=["check_in_date", "check_out_date", "creation", "status"],
		limit=5000,
	)
	# Final occupancy by past date, for the weekday average.
	finals: dict[str, int] = {}
	for row in rows:
		if str(row.status) not in ("Checked In", "Checked Out", "Confirmed"):
			continue
		arrival = getdate(row.check_in_date)
		depart = getdate(row.check_out_date)
		if depart <= arrival:
			depart = arrival + timedelta(days=1)
		day = max(arrival, start)
		last = min(depart, today)
		while day < last:
			if day < today:
				stamp = str(day)
				finals[stamp] = finals.get(stamp, 0) + 1
			day += timedelta(days=1)
	weekday_avg: dict[int, float] = {}
	buckets: dict[int, list[float]] = {}
	for stamp, sold in finals.items():
		pct = (sold / sellable * 100.0) if sellable else 0.0
		buckets.setdefault(getdate(stamp).weekday(), []).append(pct)
	for weekday, values in buckets.items():
		weekday_avg[weekday] = sum(values) / len(values)
	cache = {
		"property": property,
		"sellable": sellable,
		"rows": rows,
		"weekday_avg": weekday_avg,
		"today": today,
		"memo": {},
	}
	frappe.flags.enterprise_predict = cache
	return cache


def _predicted(property: str, day: str, on_books: float) -> float:
	ctx = _context(property)
	memo = ctx["memo"]
	if day in memo:
		return memo[day]
	target = getdate(day)
	lead = date_diff(target, ctx["today"])
	last_7_start = ctx["today"] - timedelta(days=7)
	prior_start = ctx["today"] - timedelta(days=14)
	pickup_last = 0
	pickup_prior = 0
	for row in ctx["rows"]:
		arrival = getdate(row.check_in_date)
		depart = getdate(row.check_out_date)
		if not (arrival <= target < depart or (depart <= arrival and arrival == target)):
			continue
		created = getdate(str(row.creation)[:10])
		if last_7_start <= created < ctx["today"]:
			pickup_last += 1
		elif prior_start <= created < last_7_start:
			pickup_prior += 1
	weekday_final = ctx["weekday_avg"].get(target.weekday())
	predicted = predict_occupancy_pct(
		on_books, ctx["sellable"], pickup_last, pickup_prior, weekday_final, lead)
	memo[day] = predicted
	return predicted
