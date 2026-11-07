"""Hourly and block day-use stays.

Nightly overnight pricing is unchanged. A Rate Plan with billing_basis
Hourly or Block prices a same-day stay from its planned (or actual) times,
and an in-house day-use past its planned ETD is due for checkout.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from decimal import Decimal

import frappe
from frappe.utils import flt, get_datetime, getdate, now_datetime

from kamra.notifications import record, room_no
from kamra.settings import get_setting

OVERSTAY_NEXT_HOUR = "Next hour"
OVERSTAY_NEXT_BLOCK = "Next block"
OVERSTAY_FULL_DAY = "Full day"
OVERSTAY_OPTIONS = (OVERSTAY_NEXT_HOUR, OVERSTAY_NEXT_BLOCK, OVERSTAY_FULL_DAY)


def overstay_rule(property: str) -> str:
	rule = get_setting(property, "day_use_overstay") or OVERSTAY_NEXT_HOUR
	return rule if rule in OVERSTAY_OPTIONS else OVERSTAY_NEXT_HOUR


def plan_billing(rate_plan: str | None) -> dict | None:
	"""Hourly/block fields from a Rate Plan, or None for nightly (default)."""
	if not rate_plan or not frappe.db.exists("Rate Plan", rate_plan):
		return None
	rp = frappe.get_cached_doc("Rate Plan", rate_plan)
	basis = (rp.get("billing_basis") or "Nightly").strip()
	if basis not in ("Hourly", "Block"):
		return None
	hourly = flt(rp.get("hourly_rate"))
	min_hours = flt(rp.get("min_hours") or 1) or 1.0
	block_hours = flt(rp.get("block_hours") or 3) or 3.0
	block_rate = flt(rp.get("block_rate"))
	if basis == "Block" and block_rate <= 0 and hourly > 0:
		block_rate = round(hourly * block_hours, 2)
	if basis == "Hourly" and hourly <= 0:
		frappe.throw(
			frappe._("Rate plan {0} is hourly but has no hourly rate.")
			.format(rp.rate_plan_name or rate_plan))
	if basis == "Block" and block_rate <= 0:
		frappe.throw(
			frappe._("Rate plan {0} is a block plan but has no block rate.")
			.format(rp.rate_plan_name or rate_plan))
	return {
		"billing_basis": basis,
		"hourly_rate": hourly,
		"min_hours": min_hours,
		"block_hours": block_hours,
		"block_rate": block_rate,
		"rate_plan": rate_plan,
	}


def hours_between(start, end) -> float:
	"""Elapsed hours between two datetimes or HH:MM strings on the same day."""
	if start is None or end is None:
		return 0.0
	if not isinstance(start, datetime):
		start = _as_dt(start)
	if not isinstance(end, datetime):
		end = _as_dt(end, ref=start)
	secs = (end - start).total_seconds()
	if secs < 0:
		frappe.throw(frappe._("Check-out time must be after check-in."))
	return round(secs / 3600.0, 4)


def _as_dt(value, ref: datetime | None = None) -> datetime:
	if isinstance(value, datetime):
		return value
	text = str(value).strip()
	if " " in text or "T" in text:
		return get_datetime(text)
	# HH:MM on the reference day (or today)
	base = (ref or now_datetime()).replace(
		hour=0, minute=0, second=0, microsecond=0)
	parts = text.split(":")
	h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
	return base + timedelta(hours=h, minutes=m)


def billable_units(elapsed_hours: float, plan: dict, *,
                   overstay: str = OVERSTAY_NEXT_HOUR,
                   planned_hours: float | None = None) -> dict:
	"""How many hours or blocks to bill for an elapsed stay.

	Returns `{units, hours, full_day, unit_rate, amount}` in the plan's
	gross (tax-inclusive or not is decided by the quote).
	"""
	basis = plan["billing_basis"]
	min_h = flt(plan["min_hours"]) or 1.0
	block_h = flt(plan["block_hours"]) or 3.0
	elapsed = max(flt(elapsed_hours), 0.0)
	planned = flt(planned_hours) if planned_hours is not None else elapsed

	# Past planned ETD under "Full day" → one nightly (caller substitutes).
	if (overstay == OVERSTAY_FULL_DAY and planned_hours is not None
			and elapsed > planned + 0.001):
		return {"units": 1.0, "hours": elapsed, "full_day": True,
		        "unit_rate": 0.0, "amount": 0.0}

	hours = max(elapsed, min_h)
	if basis == "Block":
		# Round up to the next whole block and bill block_rate × blocks.
		blocks = max(math.ceil(hours / block_h - 1e-9), math.ceil(min_h / block_h))
		blocks = max(int(blocks), 1)
		unit_rate = flt(plan["block_rate"])
		return {"units": float(blocks), "hours": blocks * block_h,
		        "full_day": False, "unit_rate": unit_rate,
		        "amount": round(blocks * unit_rate, 2)}

	# Hourly plan: round elapsed hours per the overstay rule.
	if overstay == OVERSTAY_NEXT_BLOCK:
		hours = max(math.ceil(hours / block_h - 1e-9) * block_h,
		            math.ceil(min_h / block_h) * block_h)
	else:
		# Next hour, or Full day while still inside the planned window.
		hours = max(math.ceil(hours - 1e-9), math.ceil(min_h - 1e-9))
	unit_rate = flt(plan["hourly_rate"])
	return {"units": float(hours), "hours": float(hours), "full_day": False,
	        "unit_rate": unit_rate, "amount": round(hours * unit_rate, 2)}


def quote_day_use_amount(property: str, rate_plan: str | None,
                         check_in_time, check_out_time,
                         nightly_fallback: Decimal) -> dict | None:
	"""Room amount for a day-use stay on an hourly/block plan, or None
	to keep the normal one-night quote."""
	plan = plan_billing(rate_plan)
	if not plan:
		return None
	if not check_in_time or not check_out_time:
		# No slot yet: bill the plan minimum.
		elapsed = flt(plan["min_hours"]) or 1.0
		planned = elapsed
	else:
		elapsed = hours_between(check_in_time, check_out_time)
		planned = elapsed
	units = billable_units(elapsed, plan, overstay=overstay_rule(property),
	                       planned_hours=planned)
	if units["full_day"]:
		amount = float(nightly_fallback)
		return {**plan, **units, "amount": amount,
		        "description": "Day use · full day"}
	label = ("Day use · {0:g} h".format(units["hours"]) if plan["billing_basis"] == "Hourly"
	         else "Day use · {0:g} × {1:g}h".format(units["units"], plan["block_hours"]))
	return {**plan, **units, "description": label}


def reservation_slot_hours(res) -> tuple[float, float]:
	"""(elapsed_or_planned hours so far, planned hours)."""
	date = getdate(res.check_in_date)
	start = res.get("planned_check_in_time") or "10:00"
	end = res.get("planned_check_out_time") or "18:00"
	start_dt = _as_dt(f"{date} {str(start)[:5]}")
	end_dt = _as_dt(f"{date} {str(end)[:5]}", ref=start_dt)
	planned = hours_between(start_dt, end_dt)
	# Actual elapsed: from planned start (or now if earlier) to now.
	now = now_datetime()
	elapsed = hours_between(start_dt, max(now, start_dt))
	return elapsed, planned


def is_due_out(res, now=None) -> bool:
	"""Whether an in-house stay should show as due for checkout.

	Overnight: checkout date has arrived (date-based, as before).
	Day-use with a planned ETD: only once that time has passed.
	Day-use with no ETD: due on the checkout date like overnight.
	"""
	if getattr(res, "status", None) and res.status != "Checked In":
		# Callers that already filtered Checked In may pass a bare row.
		pass
	now = now or now_datetime()
	today = getdate(now)
	co = getdate(res.check_out_date) if res.get("check_out_date") else None
	if not co:
		return False
	if co < today:
		return True
	if co > today:
		return False
	# Checkout date is today.
	if not cint_day_use(res):
		return True
	etd = res.get("planned_check_out_time")
	if not etd:
		return True
	deadline = _as_dt(f"{co} {str(etd)[:5]}")
	return now >= deadline


def cint_day_use(res) -> bool:
	v = res.get("is_day_use") if hasattr(res, "get") else getattr(res, "is_day_use", 0)
	try:
		return int(v or 0) == 1
	except (TypeError, ValueError):
		return bool(v)


def alert_overdue_day_use(property: str | None = None) -> list[str]:
	"""Notify front desk once when a day-use stay is past its planned ETD.

	Runs on the 15-minute scheduler. Idempotent: skips stays that already
	have an overdue-day-use notification.
	"""
	filters = {"status": "Checked In", "is_day_use": 1,
	           "planned_check_out_time": ("is", "set")}
	if property:
		filters["property"] = property
	now = now_datetime()
	alerted = []
	for res in frappe.get_all(
			"Reservation", filters=filters,
			fields=["name", "property", "guest_name", "room", "check_out_date",
			        "planned_check_out_time", "is_day_use", "status"]):
		if getdate(res.check_out_date) > getdate(now):
			continue
		if not is_due_out(res, now=now):
			continue
		if _already_alerted(res.name):
			continue
		etd = str(res.planned_check_out_time)[:5]
		subject = (f"Day-use past checkout ({etd}) - {res.guest_name}"
		           + (f" · Room {room_no(res.room)}" if res.room else ""))
		record(res.property, "front-desk", subject,
		       doctype="Reservation", name=res.name,
		       route=f"/reservations?open={res.name}")
		alerted.append(res.name)
	return alerted


def _already_alerted(reservation: str) -> bool:
	return bool(frappe.db.exists("Kamra Notification", {
		"reference_doctype": "Reservation",
		"reference_name": reservation,
		"subject": ("like", "Day-use past checkout%"),
	}))
