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


def pet_charge_amount(prop, pets: int, nights: int) -> Decimal:
	"""What the property charges for this many pets over the stay, before
	tax. Per stay by default - most homestays charge once per pet, not per
	night - with Per night for the ones that price it like a room."""
	pets = max(0, cint(pets))
	if not pets:
		return Decimal(0)
	if not cint(prop.get("pets_allowed")):
		frappe.throw("This property does not accept pets.")
	amount = _dec(prop.get("pet_charge")) * pets
	if (prop.get("pet_charge_basis") or "Per stay") == "Per night":
		amount *= max(cint(nights), 1)
	return amount


def small_group_allows_stay(rt, check_in, check_out) -> bool:
	"""Does the small-group rate survive this particular stay?

	Properties that price small parties per head usually mean it midweek
	only, and treat a stay that touches a weekend as a weekend stay
	throughout - you cannot have two nights of a villa at the per-head rate
	because the first one happened to be a Thursday. `small_group_whole_stay`
	says so: every night has to fall on a small-group day, or the rate is off
	for the whole booking.

	Off (the default), each night is judged on its own, which is what a
	property wanting a simple midweek discount expects.
	"""
	if not rt.get("small_group_whole_stay"):
		return True
	days = rt.get("small_group_days")
	if not days:
		return True
	nights = max(1, int(date_diff(check_out, check_in) or 0))
	return all(
		days_cover(days, getdate(add_days(check_in, i)).strftime("%a").lower())
		for i in range(nights)
	)


def _small_group_rate(rt, adults: int, date=None) -> Decimal | None:
	"""Per-person rate for a party smaller than the room type's small-group
	threshold, or None when the rule does not apply.

	Whole-place lets (villas, homestays) often price a small midweek party
	per head rather than charging the full house rate - "under 5 guests, 4,000
	each". Kamra's standard model only ever ADDS for guests beyond base
	occupancy, so without this a party of three pays the eight-person rate.

	`small_group_days` scopes the rule to the days it applies on (blank = every
	day), which is what keeps a midweek-only rule from undercutting the weekend
	house rate. With no date in hand the rule is treated as day-agnostic.
	"""
	threshold = int(rt.get("small_group_max_adults") or 0)
	per_adult = _dec(rt.get("small_group_price_per_adult"))
	if not threshold or not per_adult or adults >= threshold:
		return None
	if date is not None and not days_cover(
			rt.get("small_group_days"), getdate(date).strftime("%a").lower()):
		return None
	return adults * per_adult


def _extra_adult_charge(rt, adults: int) -> Decimal:
	"""What guests beyond the base occupancy add, up to the room's capacity.

	The rate card only covers the room as sold - base occupancy plus the
	extra adults it can take. Anyone beyond the stated capacity is there by
	arrangement, on a mattress on the floor, and what they cost is agreed
	with the guest rather than read off a rate card. That amount lives on the
	booking (`over_capacity_charge`), so the engine stops at capacity and does
	not invent a price for people it was never asked about.
	"""
	base = int(rt.base_occupancy or 2)
	cap = int(rt.get("adults_capacity") or 0)
	billable = min(adults, cap) if cap else adults
	extra = max(0, billable - base)
	return extra * _dec(rt.extra_adult_price)


def occupancy_rate(rt, adults: int, children: int, date=None,
                   allow_small_group: bool = True) -> Decimal:
	"""Nightly room rate for a party, from Room Type occupancy pricing.

	`date` is optional and only used by the small-group rule, so every existing
	caller keeps its behaviour; pass the night being priced to honour
	`small_group_days`. `allow_small_group=False` switches that rate off for
	the whole stay - see small_group_allows_stay().
	"""
	adults = max(1, int(adults or 1))
	children = int(children or 0)

	small = _small_group_rate(rt, adults, date) if allow_small_group else None
	if small is not None:
		rate = small
	elif adults == 1 and rt.single_occupancy_price:
		rate = _dec(rt.single_occupancy_price)
	else:
		rate = _dec(rt.base_price)
		rate += _extra_adult_charge(rt, adults)

	# children between free_child_age and child_age_limit pay child_price;
	# the API treats older children as adults upstream.
	rate += _child_charge(rt, adults, children, priced_per_head=small is not None)
	return rate


def _child_charge(rt, adults: int, children: int,
                  priced_per_head: bool = False) -> Decimal:
	"""What the children in a party add to the nightly rate.

	By default every child is charged, which suits a room sold per person.
	A whole-place let is different: the rate buys the house up to its base
	occupancy, so a family of six adults and two children in a house that
	sleeps eight has already paid for all eight - charging the children again
	bills the same beds twice. `children_within_base_occupancy` switches to
	that reading, where children fill the base occupancy alongside adults and
	only the guests beyond it are charged.

	A small-group rate is already per head, so every child is charged there
	whichever way the flag is set.
	"""
	per_child = _dec(rt.child_price)
	if not children or not per_child:
		return Decimal(0)
	if priced_per_head or not rt.get("children_within_base_occupancy"):
		return children * per_child
	base = int(rt.base_occupancy or 2)
	# adults take the base occupancy first; children fill what is left
	free_seats = max(0, base - adults)
	return max(0, children - free_seats) * per_child


def forecast_occupancy(property: str, date,
                       exclude: str | None = None) -> float:
	"""Property occupancy for a future date: live reservations covering that
	night over sellable rooms. This is the demand signal hurdle tiers key on.

	`exclude` leaves one reservation out - re-quoting a saved booking must
	not count the booking itself, or an amendment would price against a
	house the original booking never saw."""
	total = frappe.db.count("Room", {"property": property})
	if not total:
		return 0.0
	sold = frappe.db.sql(
		"""SELECT COUNT(*) FROM `tabReservation`
		   WHERE property = %(p)s AND status IN ('Confirmed', 'Checked In')
		     AND name != %(x)s
		     AND check_in_date <= %(d)s
		     AND GREATEST(check_out_date,
		                  DATE_ADD(check_in_date, INTERVAL 1 DAY)) > %(d)s""",
		{"p": property, "d": str(date), "x": exclude or ""})[0][0]
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


def days_cover(days_of_week: str | None, day_abbr: str) -> bool:
	"""Does a comma-separated day list cover this weekday?

	A blank list runs every day; otherwise the weekday has to be listed, with
	the weekend/weekday shorthands expanded. Shared by seasons, rate
	guardrails and small-group pricing so all three read a day list the same
	way - note that "weekend" means Sat+Sun, so a property whose weekend is
	Fri+Sat spells the days out.
	"""
	if not days_of_week:
		return True
	normalized_days = set()
	for d in (x.strip().lower() for x in str(days_of_week).split(",")):
		if d in ("weekend", "weekends"):
			normalized_days.update(["sat", "sun"])
		elif d in ("weekday", "weekdays"):
			normalized_days.update(["mon", "tue", "wed", "thu", "fri"])
		else:
			normalized_days.add(d[:3])
	return day_abbr in normalized_days


def _season_covers_day(season, day_abbr: str) -> bool:
	return days_cover(season.days_of_week, day_abbr)


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


def stay_season_rules(property: str, check_in, check_out,
                      room_type: str | None = None) -> dict:
	"""The strictest season rules a stay runs into.

	Peak dates carry more than a price: New Year wants a two-night minimum,
	December wants no refunds. Those live on the Season that already prices
	the date, so one record covers the whole rule rather than a separate
	calendar nobody remembers to update.

	Returns the longest minimum stay any covered night asks for, and whether
	any of them is non-refundable.
	"""
	nights = max(1, int(date_diff(check_out, check_in) or 0))
	seasons = frappe.get_all(
		"Season",
		filters={"property": property, "disabled": 0,
		         "start_date": ("<=", add_days(check_in, nights - 1)),
		         "end_date": (">=", check_in),
		         "room_type": ("in", [room_type, "", None])},
		fields=["season_name", "start_date", "end_date", "days_of_week",
		        "minimum_nights", "non_refundable"])
	min_nights, non_refundable, named = 0, False, None
	for i in range(nights):
		date = add_days(check_in, i)
		day_abbr = getdate(date).strftime("%a").lower()
		for s in seasons:
			if not (getdate(s.start_date) <= getdate(date) <= getdate(s.end_date)):
				continue
			if not days_cover(s.days_of_week, day_abbr):
				continue
			if int(s.minimum_nights or 0) > min_nights:
				min_nights, named = int(s.minimum_nights), s.season_name
			if s.non_refundable:
				non_refundable = True
	return {"minimum_nights": min_nights, "non_refundable": non_refundable,
	        "season": named, "nights": nights}


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


def apply_rate_plan(rate_plan: str | None, room_total: Decimal) -> Decimal:
	"""The stay's room total after its rate plan's modifier.

	The plan works on the whole stay's (season- and occupancy-priced) room
	total: Percent scales it, Amount adds to it, Absolute replaces it. The
	quote calls this, and so does the folio when it posts a night, so a
	booking and its room nights can never disagree about the plan.
	"""
	room_total = _dec(room_total)
	if not rate_plan:
		return room_total
	rp = frappe.get_doc("Rate Plan", rate_plan)
	v = _dec(rp.modifier_value)
	if rp.modifier_type == "Percent":
		return room_total * (Decimal(1) + v / Decimal(100))
	if rp.modifier_type == "Amount":
		return room_total + v
	if rp.modifier_type == "Absolute":
		return v
	return room_total


def rate_plan_factor(rate_plan: str | None, room_total: Decimal) -> Decimal:
	"""What each night of a stay is multiplied by under its rate plan.

	The quote applies the plan to the stay total and scales the room tax by
	the same ratio, which spreads the plan over the nights in proportion to
	their rates. A night's share of the planned total is therefore its rate
	times this factor - the folio uses it so each posted room night is
	exactly the night the guest was quoted."""
	room_total = _dec(room_total)
	if not rate_plan or not room_total:
		return Decimal(1)
	return apply_rate_plan(rate_plan, room_total) / room_total


def negotiated_rate_plan(property: str, company: str | None) -> str | None:
	"""The rate plan a company negotiated, as it applies at *property*.

	Corporate Accounts are chain-wide but rate plans belong to a property:
	the company's plan applies when it is this property's (and enabled);
	at a sister property the plan with the same code stands in for it.
	None when the company has no plan, or none fits here."""
	if not company:
		return None
	plan = frappe.db.get_value("Corporate Account", company,
	                           "negotiated_rate_plan")
	if not plan:
		return None
	rp = frappe.db.get_value("Rate Plan", plan,
	                         ["name", "property", "code", "disabled"],
	                         as_dict=True)
	if not rp:
		return None
	if rp.property == property:
		return None if rp.disabled else rp.name
	if rp.code:
		return frappe.db.get_value(
			"Rate Plan", {"property": property, "code": rp.code, "disabled": 0},
			"name")
	return None


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
	over_capacity_charge: float = 0,
	exclude_reservation: str | None = None,
	pets: int = 0,
	company: str | None = None,
) -> dict:
	# a stay for a company is priced on the plan the company negotiated,
	# unless the caller named a plan of its own
	if not rate_plan and company:
		rate_plan = negotiated_rate_plan(property, company)
	nights = date_diff(check_out_date, check_in_date)
	day_use = nights == 0
	if nights < 0:
		frappe.throw("Check-out cannot be before check-in.")

	rt = frappe.get_doc("Room Type", room_type)
	inclusive = rates_include_tax(property)
	small_ok = small_group_allows_stay(rt, check_in_date, check_out_date)

	nightly = []
	room_total = Decimal(0)
	room_tax = Decimal(0)
	# Guests above the room's capacity, at the price agreed on this booking:
	# gathered per night so each night is taxed at its own rate.
	night_over_cap = _dec(over_capacity_charge)
	over_cap = Decimal(0)
	over_cap_tax = Decimal(0)
	occ_cache: dict = {}
	# a day-use stay bills one "night" on the check-in date
	for i in range(max(nights, 1)):
		date = add_days(check_in_date, i)
		rate = season_adjust(
			property, date,
			occupancy_rate(rt, adults, children, date,
			               allow_small_group=small_ok),
			room_type
		)
		# demand pricing: when the house fills past a hurdle tier, the
		# premium applies and the tier's floor holds - decided here, in
		# code, never by the caller
		if str(date) not in occ_cache:
			occ_cache[str(date)] = forecast_occupancy(
				property, date, exclude=exclude_reservation)
		rate, tier = demand_adjust(property, room_type, date, rate,
		                           occupancy=occ_cache[str(date)])
		# The agreed amount for extra beds counts toward the slab even though
		# it bills as its own line: GST reads what the unit fetches for the
		# day, not the occupancy its rate card started from. A room at 7,000
		# with 2,000 of extra beds is a 9,000 night, so 18%, not 5%.
		gst = room_gst_rate(property, rt, rate + night_over_cap)
		if inclusive:
			# configured price is gross — back out the taxable value
			rate = rate / (Decimal(1) + gst / Decimal(100))
		if night_over_cap:
			net = (night_over_cap / (Decimal(1) + gst / Decimal(100))
			       if inclusive else night_over_cap)
			over_cap += net
			over_cap_tax += net * gst / Decimal(100)
		nightly.append({"date": str(date), "rate": float(rate),
		                "gst_rate": float(gst),
		                "demand_premium_pct": tier["premium_pct"] if tier else 0,
		                "occupancy": occ_cache[str(date)]})
		room_total += rate
		room_tax += rate * gst / Decimal(100)

	if rate_plan:
		old_room_total = room_total
		room_total = apply_rate_plan(rate_plan, room_total)
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

	# The extra beds bill as their own line rather than buried in the room
	# rate: the guest is told what the house costs and what the extra beds
	# cost, and the desk agreed the second number separately. A rate plan or
	# a discount does not touch it - it is a figure a person agreed.
	if over_cap > 0:
		tax += over_cap_tax
		total_base += over_cap

	# Pets: their own line, taxed at the stay's room GST like the cleaning
	# fee. A voucher discounts the stay, not the pet charge.
	pets = max(0, cint(pets))
	pet_fee = pet_charge_amount(prop, pets, billable_nights)
	pet_tax = Decimal(0)
	if pet_fee > 0:
		avg_gst = (room_tax / room_total * Decimal(100)) if room_total else Decimal(0)
		if inclusive:
			pet_fee = pet_fee / (Decimal(1) + avg_gst / Decimal(100))
		pet_tax = pet_fee * avg_gst / Decimal(100)
		tax += pet_tax
		total_base += pet_fee

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
	if over_cap > 0:
		line_items.append({
			"component": "over_capacity",
			"description": "Extra guests by arrangement",
			"amount": float(over_cap),
			"tax_amount": float(over_cap_tax),
			"tax_rate": float(over_cap_tax / over_cap * 100) if over_cap else 0,
			"is_tax_inclusive": bool(inclusive),
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
	if pet_fee > 0:
		line_items.append({
			"component": "pet_charge",
			"description": f"Pets × {pets}",
			"amount": float(pet_fee),
			"tax_amount": float(pet_tax),
			"nights_applied": billable_nights
				if prop.get("pet_charge_basis") == "Per night" else 0,
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
		"over_capacity_total": float(over_cap),
		"pets": pets,
		"pet_charge": float(pet_fee),
		"room_levy": float(levy),
		"discount": float(discount),
		"voucher": voucher_name,
		"rate_plan": rate_plan or None,
		"amount_before_tax": float(total_base),
		"tax_percent": round(effective_pct, 2),
		"tax_amount": float(tax),
		"amount_after_tax": float(total),
		"line_items": line_items,
		"totals": {
			"subtotal": float(subtotal + cleaning + pet_fee + levy),
			"discount": float(discount),
			"tax": float(tax),
			"total": float(total),
			"deposit_required": deposit_required,
		},
		"currency": prop.get("currency") or "INR",
		"quote_version": 1,
		"quoted_at": str(now_datetime()),
	}
