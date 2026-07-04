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
		fields=["adjustment_type", "adjustment_value"],
		order_by="priority desc",
		limit=1,
	)
	if not seasons:
		return base
	s = seasons[0]
	v = _dec(s.adjustment_value)
	if s.adjustment_type == "Percent":
		return base * (Decimal(1) + v / Decimal(100))
	if s.adjustment_type == "Amount":
		return base + v
	return v  # Absolute


def room_gst_rate(property: str, room_type_doc, nightly_rate: Decimal) -> Decimal:
	"""GST rate for one room night. Slab mode (India default): the nightly
	tariff decides the slab. Fixed mode: the room type's tax_percent."""
	prop = frappe.get_cached_doc("Property", property)
	if (prop.get("gst_mode") or "Slab") == "Fixed":
		return _dec(room_type_doc.tax_percent)
	threshold = _dec(prop.get("gst_slab_threshold") or 7500)
	low = _dec(prop.get("gst_rate_low") or 5)
	high = _dec(prop.get("gst_rate_high") or 18)
	return low if nightly_rate <= threshold else high


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
	# a day-use stay bills one "night" on the check-in date
	for i in range(max(nights, 1)):
		date = add_days(check_in_date, i)
		rate = season_adjust(
			property, date, occupancy_rate(rt, adults, children)
		)
		gst = room_gst_rate(property, rt, rate)
		if inclusive:
			# configured price is gross — back out the taxable value
			rate = rate / (Decimal(1) + gst / Decimal(100))
		nightly.append({"date": str(date), "rate": float(rate),
		                "gst_rate": float(gst)})
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

	from kamra.folio import FNB_GST

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
