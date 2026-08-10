"""Kamra's pricing engine.

Deterministic by design: agents and humans both get quotes from this module;
no LLM ever computes money. Resolution order per night:
  season-adjusted occupancy rate -> rate-plan modifier -> meal plan
  -> voucher discount -> tax.
"""

from decimal import Decimal

import frappe
from frappe.utils import add_days, date_diff, getdate, nowdate


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


def season_adjust(property: str, date, base: Decimal) -> Decimal:
	"""Apply the highest-priority active season covering `date`."""
	seasons = frappe.get_all(
		"Season",
		filters={
			"property": property,
			"disabled": 0,
			"start_date": ("<=", date),
			"end_date": (">=", date),
		},
		fields=["adjustment_type", "adjustment_value", "days_of_week"],
		order_by="priority desc",
	)
	if not seasons:
		return base

	from frappe.utils import getdate
	dt = getdate(date)
	day_abbr = dt.strftime("%a").lower()

	for s in seasons:
		if s.days_of_week:
			days = [d.strip().lower() for d in s.days_of_week.split(",")]
			normalized_days = set()
			for d in days:
				if d in ("weekend", "weekends"):
					normalized_days.update(["sat", "sun"])
				elif d in ("weekday", "weekdays"):
					normalized_days.update(["mon", "tue", "wed", "thu", "fri"])
				else:
					normalized_days.add(d[:3])
			if day_abbr not in normalized_days:
				continue

		v = _dec(s.adjustment_value)
		if s.adjustment_type == "Percent":
			return base * (Decimal(1) + v / Decimal(100))
		if s.adjustment_type == "Amount":
			return base + v
		return v  # Absolute

	return base


def room_gst_rate(property: str, room_type_doc, nightly_rate: Decimal) -> Decimal:
	"""Room-night tax rate, resolved by the property's localization pack
	(India = GST slab/fixed; other countries = their own). Kept named
	room_gst_rate for its many callers; the logic lives in the pack."""
	from kamra.localization import pack_for
	return pack_for(property).calculate_room_tax(
		property, room_type_doc, nightly_rate)


def rates_include_tax(property: str) -> bool:
	return bool(frappe.get_cached_doc("Property", property).get("rates_include_tax"))


def validate_voucher(property: str, voucher_code: str, nights: int):
	"""Return the voucher doc if valid, else throw with a guest-readable reason."""
	name = frappe.db.get_value(
		"Discount Voucher",
		{"property": property, "voucher_code": voucher_code.strip().upper()},
	)
	if not name:
		frappe.throw(f"Voucher '{voucher_code}' does not exist.")
	v = frappe.get_doc("Discount Voucher", name)
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
			property, date, occupancy_rate(rt, adults, children)
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
		v = validate_voucher(property, voucher_code, max(nights, 1))
		voucher_name = v.name
		if v.discount_type == "Percent":
			discount = subtotal * _dec(v.value) / Decimal(100)
		else:
			discount = min(_dec(v.value), subtotal)

	taxable = subtotal - discount
	# discount reduces tax proportionally across the blended rate
	gross_tax = room_tax + meal_tax
	tax = gross_tax * (taxable / subtotal) if subtotal else Decimal(0)
	total = taxable + tax
	effective_pct = float(tax / taxable * 100) if taxable else 0

	return {
		"nights": nights,
		"day_use": day_use,
		"nightly": nightly,
		"room_total": float(room_total),
		"meal_total": float(meal_total),
		"discount": float(discount),
		"voucher": voucher_name,
		"amount_before_tax": float(taxable),
		"tax_percent": round(effective_pct, 2),
		"tax_amount": float(tax),
		"amount_after_tax": float(total),
	}
