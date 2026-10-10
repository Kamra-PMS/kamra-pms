"""Kamra's pricing engine.

Deterministic by design: agents and humans both get quotes from this module;
no LLM ever computes money. Resolution order per night:
  season-adjusted occupancy rate -> rate-plan modifier -> meal plan
  -> voucher discount -> tax.
"""

from decimal import Decimal

import frappe
from frappe.utils import add_days, cint, date_diff, getdate, nowdate


def _dec(v) -> Decimal:
	return Decimal(str(v or 0))


def occupancy_rate(rt, adults: int, children: int) -> Decimal:
	"""Nightly room rate for a party, from Room Type occupancy pricing."""
	adults = max(1, int(adults or 1))
	children = int(children or 0)

	if adults == 1 and rt.single_occupancy_price:
		rate = _dec(rt.single_occupancy_price)
	else:
		rate = _dec(rt.base_price)
		extra_adults = max(0, adults - int(rt.base_occupancy or 2))
		rate += extra_adults * _dec(rt.extra_adult_price)

	# children between free_child_age and child_age_limit pay child_price;
	# the API treats older children as adults upstream.
	rate += children * _dec(rt.child_price)
	return rate


def forecast_occupancy(property: str, date) -> float:
	"""Property occupancy for a future date: live reservations covering that
	night over sellable rooms. This is the demand signal hurdle tiers key on."""
	total = frappe.db.count("Room", {"property": property})
	if not total:
		return 0.0
	sold = frappe.db.sql(
		"""SELECT COUNT(*) FROM `tabReservation`
		   WHERE property = %(p)s AND status IN ('Confirmed', 'Checked In')
		     AND check_in_date <= %(d)s
		     AND GREATEST(check_out_date,
		                  DATE_ADD(check_in_date, INTERVAL 1 DAY)) > %(d)s""",
		{"p": property, "d": str(date)})[0][0]
	return round(sold / total * 100, 1)


def demand_tier(property: str, room_type: str, date,
                occupancy: float | None = None) -> dict | None:
	"""The active hurdle tier for a date: the highest occupancy threshold the
	forecast has crossed (room-type-specific rows beat property-wide ones).
	Returns {occupancy, occupancy_from, premium_pct, min_rate} or None."""
	occ = forecast_occupancy(property, date) if occupancy is None else occupancy
	rows = frappe.get_all(
		"Hurdle Rate",
		filters={"property": property, "disabled": 0,
		         "occupancy_from": ("<=", occ),
		         "room_type": ("in", [room_type, "", None])},
		fields=["room_type", "occupancy_from", "premium_pct", "min_rate"],
		order_by="occupancy_from desc")
	if not rows:
		return None
	specific = [r for r in rows if r.room_type == room_type]
	t = specific[0] if specific else rows[0]
	return {"occupancy": occ, "occupancy_from": float(t.occupancy_from),
	        "premium_pct": float(t.premium_pct or 0),
	        "min_rate": float(t.min_rate or 0)}


def demand_adjust(property: str, room_type: str, date, rate: Decimal,
                  occupancy: float | None = None) -> tuple[Decimal, dict | None]:
	"""Apply the active demand tier: premium % on top of the season rate,
	then the hurdle floor - the rate never sells below the tier's minimum."""
	tier = demand_tier(property, room_type, date, occupancy)
	if not tier:
		return rate, None
	rate = rate * (Decimal(1) + _dec(tier["premium_pct"]) / Decimal(100))
	if tier["min_rate"] and rate < _dec(tier["min_rate"]):
		rate = _dec(tier["min_rate"])
	return rate, tier


def _season_covers_day(season, day_abbr: str) -> bool:
	"""A blank days_of_week runs every day; otherwise the weekday has to be
	listed, with the weekend/weekday shorthands expanded."""
	if not season.days_of_week:
		return True
	normalized_days = set()
	for d in (x.strip().lower() for x in season.days_of_week.split(",")):
		if d in ("weekend", "weekends"):
			normalized_days.update(["sat", "sun"])
		elif d in ("weekday", "weekdays"):
			normalized_days.update(["mon", "tue", "wed", "thu", "fri"])
		else:
			normalized_days.add(d[:3])
	return day_abbr in normalized_days


def season_adjust(property: str, date, base: Decimal,
                  room_type: str | None = None) -> Decimal:
	"""Apply the active season covering `date` for this room type.

	A season that names a room type moves only that room type's rate; one
	with the field left blank is house-wide - "blank = all", as the Seasons
	form says. The room-type season wins over a house-wide one and priority
	breaks the tie inside each group, the same most-specific-wins rule the
	rate guardrails use. Called without a room_type only house-wide seasons
	apply, so one room type's rate can never be charged for another.
	"""
	seasons = frappe.get_all(
		"Season",
		filters={
			"property": property,
			"disabled": 0,
			"start_date": ("<=", date),
			"end_date": (">=", date),
			"room_type": ("in", [room_type, "", None]),
		},
		fields=["adjustment_type", "adjustment_value", "days_of_week",
		        "room_type", "priority"],
		order_by="priority desc",
	)
	if not seasons:
		return base

	from frappe.utils import getdate
	day_abbr = getdate(date).strftime("%a").lower()
	todays = [s for s in seasons if _season_covers_day(s, day_abbr)]
	if not todays:
		return base

	# most specific wins, then priority - `todays` is already priority desc,
	# so max() keeps the highest-priority season within each group
	s = max(todays, key=lambda x: (1 if x.room_type else 0,
	                               float(x.priority or 0)))

	v = _dec(s.adjustment_value)
	if s.adjustment_type == "Percent":
		return base * (Decimal(1) + v / Decimal(100))
	if s.adjustment_type == "Amount":
		return base + v
	return v  # Absolute


def room_gst_rate(property: str, room_type_doc, nightly_rate: Decimal) -> Decimal:
	"""Room-night tax rate, resolved by the property's localization pack
	(India = GST slab/fixed; other countries = their own). Kept named
	room_gst_rate for its many callers; the logic lives in the pack."""
	from kamra.localization import pack_for
	return pack_for(property).calculate_room_tax(
		property, room_type_doc, nightly_rate)


def rates_include_tax(property: str) -> bool:
	return bool(frappe.get_cached_doc("Property", property).get("rates_include_tax"))


def validate_voucher(property: str, voucher_code: str, nights: int,
                     check_limits: bool = True):
	"""Return the voucher doc if valid, else throw with a guest-readable reason.

	check_limits=False skips the active flag, validity dates and use limit.
	Re-pricing a booking that already holds the voucher passes it: the
	booking was accepted when it was made, and its own use would otherwise
	count against the limit (or the voucher would have expired since)."""
	name = frappe.db.get_value(
		"Discount Voucher",
		{"property": property, "voucher_code": voucher_code.strip().upper()},
	)
	if not name:
		frappe.throw(f"Voucher '{voucher_code}' does not exist.")
	v = frappe.get_doc("Discount Voucher", name)
	if check_limits:
		today = getdate(nowdate())
		if v.disabled:
			frappe.throw(f"Voucher {v.voucher_code} is no longer active.")
		if v.valid_from and getdate(v.valid_from) > today:
			frappe.throw(f"Voucher {v.voucher_code} starts on {v.valid_from}.")
		if v.valid_to and getdate(v.valid_to) < today:
			frappe.throw(f"Voucher {v.voucher_code} expired on {v.valid_to}.")
		if v.max_uses and (v.times_used or 0) >= v.max_uses:
			frappe.throw(f"Voucher {v.voucher_code} has been fully redeemed.")
	if nights < (v.min_nights or 1):
		frappe.throw(
			f"Voucher {v.voucher_code} needs a stay of at least "
			f"{v.min_nights} nights."
		)
	return v


def quote(
	property: str,
	room_type: str,
	check_in_date: str,
	check_out_date: str,
	adults: int = 2,
	children: int = 0,
	meal_plan: str | None = None,
	rate_plan: str | None = None,
	voucher_code: str | None = None,
	check_voucher_limits: bool = True,
) -> dict:
	nights = date_diff(check_out_date, check_in_date)
	day_use = nights == 0
	if nights < 0:
		frappe.throw("Check-out cannot be before check-in.")

	rt = frappe.get_doc("Room Type", room_type)
	inclusive = rates_include_tax(property)

	nightly = []
	room_total = Decimal(0)
	room_tax = Decimal(0)
	occ_cache: dict = {}
	# a day-use stay bills one "night" on the check-in date
	for i in range(max(nights, 1)):
		date = add_days(check_in_date, i)
		rate = season_adjust(
			property, date, occupancy_rate(rt, adults, children), room_type
		)
		# demand pricing: when the house fills past a hurdle tier, the
		# premium applies and the tier's floor holds - decided here, in
		# code, never by the caller
		if str(date) not in occ_cache:
			occ_cache[str(date)] = forecast_occupancy(property, date)
		rate, tier = demand_adjust(property, room_type, date, rate,
		                           occupancy=occ_cache[str(date)])
		gst = room_gst_rate(property, rt, rate)
		if inclusive:
			# configured price is gross — back out the taxable value
			rate = rate / (Decimal(1) + gst / Decimal(100))
		nightly.append({"date": str(date), "rate": float(rate),
		                "gst_rate": float(gst),
		                "demand_premium_pct": tier["premium_pct"] if tier else 0,
		                "occupancy": occ_cache[str(date)]})
		room_total += rate
		room_tax += rate * gst / Decimal(100)

	if rate_plan:
		rp = frappe.get_doc("Rate Plan", rate_plan)
		v = _dec(rp.modifier_value)
		old_room_total = room_total
		if rp.modifier_type == "Percent":
			room_total *= Decimal(1) + v / Decimal(100)
		elif rp.modifier_type == "Amount":
			room_total += v
		elif rp.modifier_type == "Absolute":
			room_total = v
		if old_room_total:
			room_tax *= room_total / old_room_total

	from kamra.folio import _fnb_gst
	FNB_GST = _fnb_gst(property)

	billable_nights = max(nights, 1)
	meal_total = Decimal(0)
	if meal_plan:
		mp = frappe.get_doc("Meal Plan", meal_plan)
		meal_total = billable_nights * (
			adults * _dec(mp.price_per_adult)
			+ children * _dec(mp.price_per_child)
		)
		if inclusive:
			meal_total /= Decimal(1) + _dec(FNB_GST) / Decimal(100)
	meal_tax = meal_total * _dec(FNB_GST) / Decimal(100)

	subtotal = room_total + meal_total

	discount = Decimal(0)
	voucher_name = None
	if voucher_code:
		v = validate_voucher(property, voucher_code, max(nights, 1),
		                     check_limits=check_voucher_limits)
		voucher_name = v.name
		if v.discount_type == "Percent":
			discount = subtotal * _dec(v.value) / Decimal(100)
		else:
			discount = min(_dec(v.value), subtotal)

	taxable = subtotal - discount
	# discount reduces tax proportionally across the blended rate
	gross_tax = room_tax + meal_tax
	tax = gross_tax * (taxable / subtotal) if subtotal else Decimal(0)

	# Cleaning fee (ADR-008): separate line; taxable at room GST when enabled.
	prop = frappe.get_cached_doc("Property", property)
	cleaning = _dec(prop.get("cleaning_fee") or 0)
	cleaning_tax = Decimal(0)
	if cleaning > 0:
		# Use the stay's average room GST as the cleaning tax rate.
		avg_gst = (room_tax / room_total * Decimal(100)) if room_total else Decimal(0)
		if cint(prop.get("cleaning_fee_taxable") if prop.get("cleaning_fee_taxable") is not None else 1):
			if inclusive:
				cleaning = cleaning / (Decimal(1) + avg_gst / Decimal(100))
			cleaning_tax = cleaning * avg_gst / Decimal(100)
		tax += cleaning_tax
		total_base = taxable + cleaning
	else:
		total_base = taxable

	# Room levy (municipality fee, city / tourism tax): a % of the room rate
	# net of discount, posted per night as its own folio line
	levy_pct = _dec(prop.get("room_levy_percent") or 0)
	levy = levy_tax = Decimal(0)
	if levy_pct > 0 and room_total:
		room_net = room_total * (taxable / subtotal) if subtotal else room_total
		levy = room_net * levy_pct / Decimal(100)
		if cint(prop.get("room_levy_taxable") if prop.get("room_levy_taxable") is not None else 1):
			avg_gst = room_tax / room_total * Decimal(100)
			levy_tax = levy * avg_gst / Decimal(100)
		tax += levy_tax
		total_base += levy

	total = total_base + tax
	effective_pct = float(tax / total_base * 100) if total_base else 0

	deposit_required = float(prop.get("security_deposit_amount") or 0)

	line_items = [
		{
			"component": "accommodation",
			"description": "Room nights",
			"amount": float(room_total),
			"tax_amount": float(room_tax * (taxable / subtotal) if subtotal else 0),
			"tax_rate": float(room_tax / room_total * 100) if room_total else 0,
			"is_tax_inclusive": bool(inclusive),
			"nights_applied": billable_nights,
		},
	]
	if meal_total:
		line_items.append({
			"component": "meal_plan",
			"description": "Meal plan",
			"amount": float(meal_total),
			"tax_amount": float(meal_tax * (taxable / subtotal) if subtotal else 0),
			"nights_applied": billable_nights,
		})
	if cleaning > 0:
		line_items.append({
			"component": "cleaning_fee",
			"description": "Cleaning fee",
			"amount": float(cleaning),
			"tax_amount": float(cleaning_tax),
			"nights_applied": 0,
		})
	if levy:
		line_items.append({
			"component": "room_levy",
			"description": prop.get("room_levy_label") or "Room levy",
			"amount": float(levy),
			"tax_amount": float(levy_tax),
			"nights_applied": billable_nights,
		})
	if discount:
		line_items.append({
			"component": "promotion",
			"description": "Discount",
			"amount": -float(discount),
			"tax_amount": 0.0,
			"nights_applied": billable_nights,
		})

	from frappe.utils import now_datetime
	return {
		"nights": nights,
		"day_use": day_use,
		"nightly": nightly,
		"room_total": float(room_total),
		"meal_total": float(meal_total),
		"cleaning_fee": float(cleaning),
		"room_levy": float(levy),
		"discount": float(discount),
		"voucher": voucher_name,
		"amount_before_tax": float(total_base),
		"tax_percent": round(effective_pct, 2),
		"tax_amount": float(tax),
		"amount_after_tax": float(total),
		"line_items": line_items,
		"totals": {
			"subtotal": float(subtotal + cleaning + levy),
			"discount": float(discount),
			"tax": float(tax),
			"total": float(total),
			"deposit_required": deposit_required,
		},
		"currency": prop.get("currency") or "INR",
		"quote_version": 1,
		"quoted_at": str(now_datetime()),
	}
