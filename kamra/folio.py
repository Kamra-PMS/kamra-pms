"""Folio lifecycle: open at check-in, post nightly charges, settle, close.

All amounts flow from the deterministic pricing engine. GST is carried
per line so a folio can mix rates (room 5/18%, F&B 5%) and still produce
a correct multi-rate invoice - the PRD's FR-60.
"""

import json
from decimal import Decimal

import frappe
from frappe.utils import add_days, getdate, now_datetime, nowdate

FNB_GST = 5.0  # F&B / meal-plan GST rate (India default; kept for imports)


def _fnb_gst(property):
	from kamra.localization import pack_for
	return pack_for(property).fnb_tax_rate(property)


def _recalculate(folio):
	charges = tax = Decimal(0)
	for c in folio.charges:
		amount = Decimal(str(c.amount or 0))
		rate = Decimal(str(c.gst_rate or 0))
		c.gst_amount = float(amount * rate / 100)
		c.total = float(amount + amount * rate / 100)
		charges += amount
		tax += amount * rate / 100
	paid = sum(Decimal(str(p.amount or 0)) for p in folio.payments)
	folio.charges_total = float(charges)
	folio.tax_total = float(tax)
	folio.grand_total = float(charges + tax)
	folio.payments_total = float(paid)
	folio.balance = float(charges + tax - paid)


def open_folio(reservation) -> str:
	"""Open (or return) the folio for a reservation. Called at check-in."""
	existing = frappe.db.get_value(
		"Folio", {"reservation": reservation.name, "folio_type": "Guest"}
	)
	if existing:
		_post_addons(reservation, existing)
		_post_pet_charge(reservation, existing)
		return existing
	folio = frappe.get_doc({
		"doctype": "Folio",
		"property": reservation.property,
		"reservation": reservation.name,
		"guest": reservation.guest,
		"status": "Open",
		"opened_on": now_datetime(),
	})
	if reservation.discount_amount:
		folio.append("charges", {
			"posting_date": nowdate(),
			"charge_type": "Discount",
			"description": "Booking discount (voucher)",
			"qty": 1,
			"rate": -float(reservation.discount_amount),
			"amount": -float(reservation.discount_amount),
			"gst_rate": _room_gst(reservation),
			"auto_posted": 1,
		})
	_recalculate(folio)
	from kamra.ledger import save_folio
	save_folio(folio)
	if reservation.flags.get("carried_forward"):
		# an in-house guest moved over at go-live: the old system billed
		# the one-time fees, and they arrive inside the opening balance
		return folio.name
	_post_addons(reservation, folio.name)
	_post_cleaning_fee(reservation, folio.name)
	_post_pet_charge(reservation, folio.name)
	return folio.name


def _post_cleaning_fee(reservation, folio_name: str):
	"""Post one-time cleaning fee from quote snapshot / property (ADR-008)."""
	fallback = float(
		frappe.db.get_value("Property", reservation.property, "cleaning_fee") or 0
	)
	_post_stay_fee(reservation, folio_name, "cleaning_fee", "Cleaning Fee",
	               "Cleaning fee", fallback)


def _post_pet_charge(reservation, folio_name: str):
	"""Post the pet charge once per stay, at what the guest was quoted."""
	pets = int(reservation.get("pets") or 0)
	if pets <= 0:
		return
	from frappe.utils import date_diff

	from kamra.pricing import pet_charge_amount
	prop = frappe.get_cached_doc("Property", reservation.property)
	# a property that has since stopped taking pets must not block check-in;
	# the quoted line in the snapshot still posts
	fallback = float(pet_charge_amount(
		prop, pets,
		date_diff(reservation.check_out_date, reservation.check_in_date),
	)) if prop.get("pets_allowed") else 0.0
	_post_stay_fee(reservation, folio_name, "pet_charge", "Pet Charge",
	               f"Pets × {pets}", fallback)


def _post_stay_fee(reservation, folio_name: str, component: str,
                   charge_type: str, description: str, fallback: float):
	"""Post a one-time stay fee at the amount and tax in the booking's quote
	snapshot, so a later price change never re-bills the guest. Without a
	snapshot line it posts `fallback` untaxed. Idempotent per folio."""
	import json
	amount = 0.0
	tax_rate = 0.0
	snap = getattr(reservation, "quote_snapshot", None)
	if snap:
		try:
			data = json.loads(snap) if isinstance(snap, str) else snap
			for li in data.get("line_items") or []:
				if li.get("component") == component:
					amount = float(li.get("amount") or 0)
					tax = float(li.get("tax_amount") or 0)
					tax_rate = (tax / amount * 100) if amount else 0
					break
		except Exception:
			pass  # snapshot unreadable; fall back to the property's current fee
	if amount <= 0:
		amount = fallback
	if amount <= 0:
		return
	if frappe.db.exists(
		"Folio Charge",
		{"parent": folio_name, "charge_type": charge_type, "auto_posted": 1},
	):
		return
	doc = frappe.get_doc("Folio", folio_name)
	if doc.status == "Closed":
		return
	doc.append(
		"charges",
		{
			"posting_date": nowdate(),
			"charge_type": charge_type,
			"description": description,
			"qty": 1,
			"rate": amount,
			"amount": amount,
			"gst_rate": tax_rate,
			"auto_posted": 1,
		},
	)
	_recalculate(doc)
	from kamra.ledger import save_folio
	save_folio(doc)


def _post_addons(reservation, folio_name: str):
	"""Post booking-time add-ons (experiences) that haven't hit the folio
	yet. Idempotent via the row's posted flag."""
	pending = [a for a in reservation.get("addons") or [] if not a.posted]
	if not pending:
		return
	doc = frappe.get_doc("Folio", folio_name)
	if doc.status == "Closed":
		return
	for a in pending:
		doc.append("charges", {
			"posting_date": nowdate(),
			"charge_type": "Misc",
			"reservation": reservation.name,
			"description": a.description or a.experience,
			"qty": a.qty or 1,
			"rate": a.rate,
			"amount": a.amount,
			"gst_rate": a.gst_rate,
			"auto_posted": 1,
		})
		frappe.db.set_value("Stay Addon", a.name, "posted", 1,
		                    update_modified=False)
		a.posted = 1
	_recalculate(doc)
	from kamra.ledger import save_folio
	save_folio(doc)


def open_group_folio(group_booking: str) -> str:
	"""Open (or return) the group's master folio - one consolidated bill
	for everything the company pays across all rooms of the group. It is
	anchored to the group's lead (first) reservation so invoicing and
	printing work unchanged."""
	existing = frappe.db.get_value(
		"Folio", {"group_booking": group_booking, "folio_type": "Group",
		          "status": "Open"})
	if existing:
		return existing
	lead = frappe.get_all(
		"Reservation",
		filters={"group_booking": group_booking,
		         "status": ("not in", ("Cancelled", "No Show"))},
		fields=["name", "property", "guest"],
		order_by="creation asc", limit=1)
	if not lead:
		frappe.throw(f"Group {group_booking} has no active reservations.")
	lead = lead[0]
	folio = frappe.get_doc({
		"doctype": "Folio",
		"property": lead.property,
		"reservation": lead.name,
		"guest": lead.guest,
		"folio_type": "Group",
		"group_booking": group_booking,
		"status": "Open",
		"opened_on": now_datetime(),
	})
	_recalculate(folio)
	folio.insert(ignore_permissions=True)
	return folio.name


def open_company_folio(reservation) -> str:
	"""Open (or return) the Company folio of a corporate stay."""
	existing = frappe.db.get_value(
		"Folio",
		{"reservation": reservation.name, "folio_type": "Company",
		 "status": "Open"},
	)
	if existing:
		return existing
	return split_folio(reservation.name, "Company")


# What a credit company pays when it has NO billing rules of its own - the
# property's `default_company_billing` setting. "Room" means the stay as sold:
# the room night, its meal plan, the levies on it, early/late fees, the
# cleaning fee, the extra beds agreed on it and any discount against it.
# Alcohol is filtered out before any of this (target_folio), so no option can
# bill liquor to a company.
_ROOM_CHARGES = frozenset({
	"Room", "Meal Plan", "Room Levy", "Early Check-in", "Late Checkout",
	"Cleaning Fee", "Extra Guests", "Discount",
})
COMPANY_BILLING_DEFAULTS = {
	"Room and F&B (liquor to guest)": _ROOM_CHARGES | {"Food & Beverage"},
	"Room only": _ROOM_CHARGES,
	"Everything except liquor": None,  # every charge type
	"Nothing (guest pays unless rules say so)": frozenset(),
}
DEFAULT_COMPANY_BILLING = "Room and F&B (liquor to guest)"


def default_company_billing(property: str | None) -> str:
	from kamra.settings import get_setting
	value = get_setting(property, "default_company_billing")
	return value if value in COMPANY_BILLING_DEFAULTS else DEFAULT_COMPANY_BILLING


def _company_pays(company: str, charge_type: str,
                  property: str | None = None) -> bool:
	"""Does the company pay this charge type? Its own billing rules decide
	when it has any. A credit company with none falls back to the
	property's default; a company without credit pays nothing by default."""
	rules = frappe.get_all(
		"Company Billing Rule",
		filters={"parent": company},
		fields=["charge_type", "pay_by"])
	if rules:
		return any(r.charge_type == charge_type and r.pay_by == "Company"
		           for r in rules)
	if not frappe.db.get_value("Corporate Account", company, "credit_allowed"):
		return False
	covered = COMPANY_BILLING_DEFAULTS[default_company_billing(property)]
	return covered is None or charge_type in covered


def target_folio(reservation, charge_type: str, is_alcohol: int = 0) -> str:
	"""Route a charge to the right folio of the stay.

	Group stays route company-payable charge types to the ONE group
	master folio (company pays the stay for every room, each guest pays
	their own extras). Individual corporate stays route to the stay's
	Company folio. The company's billing rules pick the charge types; a
	credit company with no rules uses the property's default
	(`default_company_billing`). Alcohol never bills to a company -
	Indian corporates won't settle it and most travel policies prohibit it.
	"""
	if not is_alcohol:
		group = reservation.get("group_booking")
		if group:
			company = frappe.db.get_value(
				"Group Booking", group, "company")
			if company and _company_pays(
					company, charge_type, reservation.get("property")):
				return open_group_folio(group)
		if reservation.get("company") and _company_pays(
				reservation.company, charge_type, reservation.get("property")):
			return open_company_folio(reservation)
	return open_folio(reservation)


def _charge_posted(reservation_name: str, charge_type: str, date: str) -> bool:
	"""Has this charge type already been posted for this date on ANY folio
	of the stay? Routing can land a member's room night on the GROUP
	master (anchored to the lead reservation), so we match on the line's
	own provenance first and fall back to the folio's reservation for
	lines predating the provenance field."""
	return bool(frappe.db.sql(
		"""
		SELECT 1 FROM `tabFolio Charge` fc
		JOIN `tabFolio` f ON fc.parent = f.name
		WHERE fc.charge_type = %(ct)s AND fc.posting_date = %(date)s
		  AND (fc.reservation = %(res)s
		       OR (IFNULL(fc.reservation, '') = '' AND f.reservation = %(res)s))
		LIMIT 1
		""",
		{"res": reservation_name, "ct": charge_type, "date": str(date)},
	))


def _room_gst(reservation) -> float:
	"""Effective GST for this reservation's first night (used for the
	discount line). Slab-aware."""
	from kamra.pricing import room_gst_rate

	locked = locked_night(reservation, reservation.check_in_date)
	if locked is not None:
		return float(locked.gst_rate or 0)

	rt = frappe.get_doc("Room Type", reservation.room_type)
	rate = Decimal(str(_nightly_room_rate(reservation, reservation.check_in_date)))
	return float(room_gst_rate(reservation.property, rt, rate))


def locked_night(reservation, date):
	"""The rate confirmed for this night at booking (Reservation Night
	Rate), or None for a stay booked before rates were locked."""
	key = str(getdate(date))
	for row in reservation.get("night_rates") or []:
		if str(row.stay_date) == key:
			return row
	return None


def _nightly_room_rate(reservation, date) -> float:
	"""Taxable nightly rate as the guest was quoted it.

	A booking carries its confirmed nightly rates (`night_rates`, locked
	from the quote that priced it - demand premium included), and the folio
	bills exactly those: a later season, rate change or a drop in occupancy
	never re-prices a confirmed stay. Stays booked before rates were locked
	fall back to pricing the night now: seasons applied, tax backed out when
	the property configures tax-inclusive pricing, and the booking's rate
	plan applied the way pricing.quote applies it."""
	locked = locked_night(reservation, date)
	if locked is not None:
		return float(locked.rate or 0)
	rate = _plan_free_night_rate(reservation, date)
	plan = reservation.get("rate_plan")
	if plan:
		rate *= _rate_plan_factor(reservation, plan)
	return float(rate)


def _rate_plan_factor(reservation, plan) -> Decimal:
	"""The stay's rate-plan factor, worked out once per loaded reservation:
	a plan that adds or fixes an amount works on the whole stay's total, so
	every night of the stay has to be priced to find one night's share."""
	from kamra.pricing import rate_plan_factor

	key = (plan, str(reservation.check_in_date), str(reservation.check_out_date),
	       reservation.adults, reservation.children, reservation.room_type,
	       reservation.get("over_capacity_charge"))
	flags = getattr(reservation, "flags", None)
	cache = flags.get("_kamra_plan_factor") if flags is not None else None
	if cache and cache[0] == key:
		return cache[1]
	start = getdate(reservation.check_in_date)
	nights = max((getdate(reservation.check_out_date) - start).days, 1)
	total = sum((_plan_free_night_rate(reservation, add_days(start, i))
	             for i in range(nights)), Decimal(0))
	factor = rate_plan_factor(plan, total)
	if flags is not None:
		flags["_kamra_plan_factor"] = (key, factor)
	return factor


def _plan_free_night_rate(reservation, date) -> Decimal:
	"""One night before the rate plan - the per-night step of pricing.quote."""
	from kamra.pricing import (
		occupancy_rate,
		rates_include_tax,
		room_gst_rate,
		season_adjust,
		small_group_allows_stay,
	)

	rt = frappe.get_doc("Room Type", reservation.room_type)
	base = occupancy_rate(
		rt, reservation.adults, reservation.children, date,
		allow_small_group=small_group_allows_stay(
			rt, reservation.check_in_date, reservation.check_out_date))
	rate = season_adjust(reservation.property, date, base,
	                     reservation.room_type)
	if rates_include_tax(reservation.property):
		gst = room_gst_rate(reservation.property, rt,
		                    rate + _over_cap_night(reservation))
		rate = rate / (Decimal(1) + gst / Decimal(100))
	return rate


def _over_cap_night(reservation) -> Decimal:
	"""The night's agreed extra-bed amount. It bills as its own line, but the
	slab reads the whole night's tariff, so it has to be in hand wherever the
	room's tax rate is worked out - matching pricing.quote."""
	return Decimal(str(reservation.get("over_capacity_charge") or 0))


def _nightly_gst(reservation, date) -> float:
	locked = locked_night(reservation, date)
	if locked is not None:
		return float(locked.gst_rate or 0)
	from kamra.pricing import (
		occupancy_rate,
		room_gst_rate,
		season_adjust,
		small_group_allows_stay,
	)

	rt = frappe.get_doc("Room Type", reservation.room_type)
	base = occupancy_rate(
		rt, reservation.adults, reservation.children, date,
		allow_small_group=small_group_allows_stay(
			rt, reservation.check_in_date, reservation.check_out_date))
	gross = season_adjust(reservation.property, date, base,
	                      reservation.room_type)
	return float(room_gst_rate(reservation.property, rt,
	                           gross + _over_cap_night(reservation)))


def _append_charge(folios, reservation, charge_type, line, is_alcohol=0):
	"""Append a line to the routed folio, reusing loaded docs so a multi-
	night posting run saves each folio once."""
	name = target_folio(reservation, charge_type, is_alcohol)
	if name not in folios:
		folios[name] = frappe.get_doc("Folio", name)
	folios[name].append("charges", line)


def post_room_night(reservation, date, folios=None) -> bool:
	"""Post one night's room (and meal plan) charge, routed by the
	company's billing rules. Skips dates already posted - safe to call
	from both audit and checkout. Pass `folios` (a dict) to batch saves
	across nights; when omitted the touched folios save immediately."""
	date = str(date)
	own_batch = folios is None
	if own_batch:
		folios = {}
	posted = False

	if not _charge_posted(reservation.name, "Room", date):
		room_no = (reservation.room or "").split("-")[-1]
		night_rate = _nightly_room_rate(reservation, date)
		_append_charge(folios, reservation, "Room", {
			"posting_date": date,
			"charge_type": "Room",
			"reservation": reservation.name,
			"description": f"Room {room_no} · {reservation.room_type.split('-')[-1]}"
			               + (" · day use" if getattr(reservation, "is_day_use", 0) else ""),
			"qty": 1,
			"rate": night_rate,
			"amount": night_rate,
			"gst_rate": _nightly_gst(reservation, date),
			"auto_posted": 1,
		})
		posted = True
		_post_room_levy(folios, reservation, date, night_rate)

	# Its own charge type, not the shared Misc bucket: dedupe is by type and
	# date, so a sundry the desk had already typed as Misc that day would
	# otherwise make the night's extra-bed charge look posted and skip it.
	over_cap = float(reservation.get("over_capacity_charge") or 0)
	if over_cap > 0 and not _charge_posted(
			reservation.name, "Extra Guests", date):
		guests = int(reservation.get("over_capacity_guests") or 0)
		_append_charge(folios, reservation, "Extra Guests", {
			"posting_date": date,
			"charge_type": "Extra Guests",
			"reservation": reservation.name,
			"description": (f"{guests} extra guests by arrangement"
			                if guests else "Extra guests by arrangement"),
			"qty": 1,
			"rate": over_cap,
			"amount": over_cap,
			"gst_rate": _nightly_gst(reservation, date),
			"auto_posted": 1,
		})
		posted = True

	if reservation.meal_plan and not _charge_posted(
			reservation.name, "Meal Plan", date):
		mp = frappe.get_doc("Meal Plan", reservation.meal_plan)
		locked = locked_night(reservation, date)
		if locked is not None:
			meal_amount = float(locked.meal_amount or 0)
		else:
			meal_amount = (
				(reservation.adults or 1) * float(mp.price_per_adult or 0)
				+ (reservation.children or 0) * float(mp.price_per_child or 0)
			)
		if meal_amount:
			_append_charge(folios, reservation, "Meal Plan", {
				"posting_date": date,
				"charge_type": "Meal Plan",
				"reservation": reservation.name,
				"description": f"{mp.label or mp.code} × {reservation.adults} adult(s)",
				"qty": 1,
				"rate": meal_amount,
				"amount": meal_amount,
				"gst_rate": _fnb_gst(reservation.property),
				"auto_posted": 1,
			})

	if own_batch:
		save_folios(folios)
	return posted


def _post_room_levy(folios, reservation, date, night_rate):
	"""The property's per-night levy on the room rate (municipality fee,
	city / tourism tax) - its own line so the invoice shows it and the
	ledger books it apart from room revenue."""
	prop = frappe.get_cached_doc("Property", reservation.property)
	pct = float(prop.get("room_levy_percent") or 0)
	if not pct or not night_rate or _charge_posted(
			reservation.name, "Room Levy", date):
		return
	levy = round(float(night_rate) * pct / 100, 2)
	_append_charge(folios, reservation, "Room Levy", {
		"posting_date": date,
		"charge_type": "Room Levy",
		"reservation": reservation.name,
		"description": f"{prop.get('room_levy_label') or 'Room levy'} {pct:g}%",
		"qty": 1,
		"rate": levy,
		"amount": levy,
		"gst_rate": _nightly_gst(reservation, date)
		            if int(prop.get("room_levy_taxable") if prop.get("room_levy_taxable") is not None else 1)
		            else 0,
		"auto_posted": 1,
	})


def save_folios(folios: dict):
	"""Save each touched folio and post its new lines to the ledger."""
	from kamra.ledger import save_folio
	for doc in folios.values():
		_recalculate(doc)
		save_folio(doc)


def carried_forward_until(reservation_name: str):
	"""For a stay that was in house at go-live: the business date its
	opening balance was posted. Nights before it were billed by the old
	system and are inside that balance. None for every other stay."""
	cutoff = frappe.db.sql(
		"""
		SELECT MAX(fc.posting_date) FROM `tabFolio Charge` fc
		JOIN `tabFolio` f ON fc.parent = f.name
		WHERE fc.charge_type = 'Opening Balance' AND f.folio_type = 'Guest'
		  AND (fc.reservation = %(res)s
		       OR (IFNULL(fc.reservation, '') = '' AND f.reservation = %(res)s))
		""", {"res": reservation_name})[0][0]
	return getdate(cutoff) if cutoff else None


def post_remaining_nights(reservation) -> int:
	"""At checkout: make sure every night of the stay is on its folio(s) -
	from go-live on, for a stay carried forward from the old system."""
	open_folio(reservation)  # guest folio always exists after checkout
	folios: dict = {}
	posted = 0
	date = getdate(reservation.check_in_date)
	cutoff = carried_forward_until(reservation.name)
	if cutoff and cutoff > date:
		date = cutoff
	end = getdate(reservation.check_out_date)
	if getattr(reservation, "is_day_use", 0) and end == date:
		end = getdate(add_days(date, 1))  # day-use bills its one date
	while date < end:
		if post_room_night(reservation, date, folios):
			posted += 1
		date = getdate(add_days(date, 1))
	save_folios(folios)
	return posted


def split_folio(reservation: str, folio_type: str = "Extra") -> str:
	"""Open an additional folio for a stay (Extra or Company) so charges
	can be routed/split - e.g. 70/30 corporate vs personal.

	If an empty folio of this type already exists, reuse it rather than
	piling up blank duplicates - you only ever need one unused split open."""
	res = frappe.get_doc("Reservation", reservation)
	for f in frappe.get_all(
		"Folio",
		filters={"reservation": reservation, "folio_type": folio_type,
		         "status": "Open"},
		fields=["name", "grand_total", "payments_total"],
	):
		if not f.grand_total and not f.payments_total:
			return f.name
	folio = frappe.get_doc({
		"doctype": "Folio",
		"property": res.property,
		"reservation": res.name,
		"guest": res.guest,
		"folio_type": folio_type,
		"status": "Open",
		"opened_on": now_datetime(),
	})
	_recalculate(folio)
	folio.insert(ignore_permissions=True)
	return folio.name


def transfer_charge(from_folio: str, charge_row: str, to_folio: str):
	"""Move one charge line between two open folios of the same stay."""
	transfer_charges(from_folio, [charge_row], to_folio)


def _folio_group(folio) -> str | None:
	return folio.get("group_booking") or frappe.db.get_value(
		"Reservation", folio.reservation, "group_booking")


def _assert_same_stay(src, dst):
	"""Charges may move within a stay, or within a group - company pays
	some rooms' charges on the master, guests settle the rest."""
	if src.reservation == dst.reservation:
		return
	sg, dg = _folio_group(src), _folio_group(dst)
	if sg and sg == dg:
		return
	frappe.throw("Folios belong to different stays.")


def transfer_charges(from_folio: str, charge_rows: list, to_folio: str):
	"""Move several charge lines at once - one save per folio, so a
	corporate re-bill of a whole stay is a single operation."""
	src = frappe.get_doc("Folio", from_folio)
	dst = frappe.get_doc("Folio", to_folio)
	_assert_same_stay(src, dst)
	if "Closed" in (src.status, dst.status):
		frappe.throw("Both folios must be open to transfer charges.")
	from kamra.ledger import ledger_charges, reverse_ledger_for_charge
	moved = []
	for charge_row in charge_rows:
		row = next((c for c in src.charges if c.name == charge_row), None)
		if not row:
			frappe.throw(f"Charge {charge_row} not found on {from_folio}.")
		if row.get("is_alcohol") and dst.folio_type in ("Company", "Group"):
			frappe.throw("Alcohol cannot be billed to a company folio.")
		dst.append("charges", {
			"posting_date": row.posting_date,
			"charge_type": row.charge_type,
			"reservation": row.get("reservation"),
			"description": row.description,
			"qty": row.qty,
			"rate": row.rate,
			"amount": row.amount,
			"gst_rate": row.gst_rate,
			"auto_posted": row.auto_posted,
			"is_alcohol": row.get("is_alcohol"),
		})
		moved.append(dst.charges[-1])
		src.charges.remove(row)
		# the line leaves this folio's ledger and joins the target's
		reverse_ledger_for_charge(src.property, src.name, row.name,
		                          f"to {dst.name}", prefix="TRANSFER")
	_recalculate(src)
	_recalculate(dst)
	src.save(ignore_permissions=True)
	dst.save(ignore_permissions=True)
	ledger_charges(dst, moved)


def split_charge(from_folio: str, charge_row: str, to_folio: str,
                 percent: float | None = None,
                 amount: float | None = None) -> dict:
	"""Split one charge line between two open folios of the same stay -
	the 70/30 corporate deal, the shared room, the disputed minibar.
	Give either a percent (of the line) or an absolute amount to move.
	Conservation is exact: source keeps base − part, target gets part."""
	src = frappe.get_doc("Folio", from_folio)
	dst = frappe.get_doc("Folio", to_folio)
	if from_folio == to_folio:
		frappe.throw("Pick a different folio to split into.")
	_assert_same_stay(src, dst)
	if "Closed" in (src.status, dst.status):
		frappe.throw("Both folios must be open to split charges.")
	row = next((c for c in src.charges if c.name == charge_row), None)
	if not row:
		frappe.throw(f"Charge {charge_row} not found on {from_folio}.")
	base = Decimal(str(row.amount or 0))
	if base <= 0:
		frappe.throw("Only positive charge lines can be split.")
	if percent:
		part = (base * Decimal(str(percent)) / 100).quantize(Decimal("0.01"))
	elif amount:
		part = Decimal(str(amount)).quantize(Decimal("0.01"))
	else:
		frappe.throw("Give a percent or an amount to split off.")
	if part <= 0 or part >= base:
		frappe.throw(f"Split must be between 0 and ₹{base} (exclusive).")
	if row.get("is_alcohol") and dst.folio_type in ("Company", "Group"):
		frappe.throw("Alcohol cannot be billed to a company folio.")

	remainder = base - part
	row.amount = float(remainder)
	row.rate = float(remainder)
	row.qty = 1
	dst.append("charges", {
		"posting_date": row.posting_date,
		"charge_type": row.charge_type,
		"reservation": row.get("reservation"),
		"description": f"{row.description} · split",
		"qty": 1,
		"rate": float(part),
		"amount": float(part),
		"gst_rate": row.gst_rate,
		"auto_posted": row.auto_posted,
		"is_alcohol": row.get("is_alcohol"),
	})
	part_row = dst.charges[-1]
	_recalculate(src)
	_recalculate(dst)
	src.save(ignore_permissions=True)
	dst.save(ignore_permissions=True)
	# the split-off part (with its tax) leaves the source line's ledger and
	# is posted on the target's
	from kamra.ledger import ledger_charges, reverse_ledger_for_charge
	reverse_ledger_for_charge(src.property, src.name, row.name,
	                          f"to {dst.name}", amount=float(part_row.total or 0),
	                          prefix="SPLIT")
	ledger_charges(dst, [part_row])
	return {"kept": float(remainder), "moved": float(part)}


def percent_fee(reservation, pct: float) -> float:
	"""₹ for a cancellation band expressed as a percentage of the stay.

	A tiered policy says "half back between three and seven days", which is
	neither one night nor the whole stay, so it cannot be said with a fee
	basis. Pre-tax; GST rides on the folio line.
	"""
	return round(float(reservation.amount_before_tax or 0)
	             * float(pct) / 100.0, 2)


def policy_fee(reservation, basis: str, pct: float | None = None) -> float:
	"""₹ for a cancellation/no-show fee basis: 'First Night' or
	'Full Stay' (pre-tax; GST rides on the folio line).

	`pct` defers to percent_fee(), so a caller holding a tiered band can use
	the one entry point the posting path already calls.
	"""
	if pct is not None:
		return percent_fee(reservation, pct)
	if basis == "First Night":
		return float(_nightly_room_rate(reservation,
		                                reservation.check_in_date))
	if basis == "Full Stay":
		return float(reservation.amount_before_tax or 0)
	return 0.0


def post_policy_fee(reservation, basis: str, label: str,
                    pct: float | None = None,
                    posting_date: str | None = None) -> float:
	"""Open the guest folio and post a policy fee (no-show / late
	cancellation). Returns the pre-tax amount posted.

	`pct` posts that percentage of the stay, for a tiered policy.
	`posting_date` is the business day the fee belongs to: the night audit
	passes the date it is closing; left out (a cancellation at the desk) it
	is the property's current business date - never the calendar, which
	runs a day ahead between midnight and the audit."""
	amount = policy_fee(reservation, basis, pct=pct)
	if amount <= 0:
		return 0.0
	folio = frappe.get_doc("Folio", open_folio(reservation))
	if folio.status == "Closed":
		return 0.0
	already = any(c.description == label for c in folio.charges)
	if already:
		return 0.0
	if not posting_date:
		from kamra.business_date import get_business_date
		posting_date = get_business_date(reservation.property)
	folio.append("charges", {
		"posting_date": str(posting_date),
		"charge_type": "Misc",
		"reservation": reservation.name,
		"description": label,
		"qty": 1,
		"rate": amount,
		"amount": amount,
		"gst_rate": _room_gst(reservation),
		"auto_posted": 1,
	})
	_recalculate(folio)
	from kamra.ledger import save_folio
	save_folio(folio)
	return amount


def close_folio(folio_name: str) -> str:
	"""Close the folio and assign the GST invoice number.

	A folio closes only when it is settled: what the guest owes is paid, what
	the company owes has moved to the city ledger (transfer_to_city_ledger
	zeroes it with a Company Credit payment), and nothing is owed back.
	Closing with money on it was how a guest left owing."""
	folio = frappe.get_doc("Folio", folio_name)
	if folio.status == "Closed":
		return folio.invoice_number
	_recalculate(folio)
	balance = float(folio.balance or 0)
	if abs(balance) > 0.01:
		from kamra.localization import pack_for
		symbol = pack_for(folio.property).locale(
			frappe.get_cached_doc("Property", folio.property)).get(
			"currency_symbol", "")
		if balance > 0:
			frappe.throw(frappe._(
				"Cannot close the folio: {0}{1:,.2f} is still owed. Collect "
				"payment, or move the company's share to the city ledger, "
				"first.").format(symbol, balance))
		frappe.throw(frappe._(
			"Cannot close the folio: {0}{1:,.2f} is owed back to the guest. "
			"Issue the refund first.").format(symbol, -balance))
	from frappe.model.naming import make_autoname

	folio.status = "Closed"
	folio.closed_on = now_datetime()
	# one series per property: each GSTIN must have its own unique
	# invoice series, and GST caps invoice numbers at 16 chars - a short
	# initials code keeps INV-KDP-26-00001 inside the limit
	code = "".join(w[0] for w in folio.property.split())[:3].upper()
	folio.invoice_number = make_autoname(f"INV-{code}-.YY.-.#####")
	_recalculate(folio)
	folio.save(ignore_permissions=True)
	# statutory e-invoicing (ZATCA in Saudi Arabia) - the pack decides
	from kamra import localization as loc
	loc.on_invoice_issued(loc.pack_for(folio.property), folio.name)
	return folio.invoice_number


def post_allowance(folio_name: str, amount: float, reason: str,
                   gst_rate: float = 0) -> str:
	"""A negative adjustment against a specific folio - the hotel writes off
	part of a charge (service recovery, dispute) WITHOUT touching the original
	line, so the trail stays honest. GST reverses at the same rate as the
	charge being adjusted."""
	folio = frappe.get_doc("Folio", folio_name)
	if folio.status == "Closed":
		frappe.throw("This folio is settled - pass the allowance on the "
		             "guest's open folio, or cancel the invoice first.")
	amount = abs(float(amount))
	if not amount:
		frappe.throw("Allowance amount is required.")
	if not (reason or "").strip():
		frappe.throw("An allowance needs a reason - it goes on the record.")
	folio.append("charges", {
		"posting_date": frappe.utils.nowdate(),
		"charge_type": "Allowance",
		"description": reason.strip(),
		"qty": 1,
		"rate": -amount,
		"amount": -amount,
		"gst_rate": float(gst_rate or 0),
	})
	_recalculate(folio)
	from kamra.ledger import save_folio
	save_folio(folio)
	from kamra.savings import log_action
	log_action("post_allowance", "Folio", folio.name, folio.property,
	           rationale=f"Allowance ₹{amount:.0f} - {reason.strip()}")
	return folio.name


def void_charge(folio_name: str, charge_row: str, reason: str = "") -> dict:
	"""Remove a wrong charge line from an OPEN folio - the correction path for
	a mis-posted bill (wrong amount, duplicate, wrong guest). The folio must
	still be open; once it is invoiced, use an allowance instead so the ledger
	stays honest. Every void is logged with who and why."""
	folio = frappe.get_doc("Folio", folio_name)
	if folio.status == "Closed":
		frappe.throw("This folio is settled - post an allowance to reverse a "
		             "charge, or cancel the invoice first.")
	if not (reason or "").strip():
		frappe.throw("A void needs a reason - it goes on the record.")
	row = next((c for c in folio.charges if c.name == charge_row), None)
	if not row:
		frappe.throw("That charge line is not on this folio.")
	removed = {"charge_type": row.charge_type, "description": row.description,
	           "amount": row.amount}
	# no-op when the caller (api.void_folio_charge) already reversed it
	from kamra.ledger import reverse_ledger_for_charge
	try:
		reverse_ledger_for_charge(folio.property, folio.name, row.name,
		                          reason or "")
	except Exception:
		frappe.log_error(title="ledger void reversal failed")
	folio.remove(row)
	_recalculate(folio)
	folio.save(ignore_permissions=True)
	from kamra.savings import log_action
	log_action("void_charge", "Folio", folio.name, folio.property,
	           rationale=f"Removed {removed['charge_type']} "
	                     f"{removed['description']} ₹{removed['amount']}"
	                     + (f" - {reason}" if reason else ""))
	return {"folio": folio.name, "removed": removed, "balance": folio.balance}


def part_settle(folio_name: str) -> dict:
	"""Interim invoice mid-stay: freeze the fully-paid folio with a real
	invoice number and open a fresh one so the stay keeps running - the
	long-stay pattern (guests settling every N days without checking out).
	The room stays occupied; only the bill closes."""
	folio = frappe.get_doc("Folio", folio_name)
	if folio.status == "Closed":
		frappe.throw("This folio is already settled.")
	_recalculate(folio)
	if round(folio.balance or 0, 2) != 0:
		frappe.throw("Settle the balance first - an interim invoice needs "
		             "the folio fully paid.")
	if not folio.charges:
		frappe.throw("Nothing to invoice on this folio.")
	invoice = close_folio(folio.name)
	fresh = frappe.get_doc({
		"doctype": "Folio",
		"property": folio.property,
		"reservation": folio.reservation,
		"guest": folio.guest,
		"folio_type": folio.folio_type,
		"status": "Open",
		"opened_on": now_datetime(),
		"group_booking": folio.get("group_booking"),
	})
	_recalculate(fresh)
	fresh.insert(ignore_permissions=True)
	return {"invoice_number": invoice, "closed_folio": folio.name,
	        "new_folio": fresh.name}


def cancel_invoice(folio_name: str, reason: str) -> dict:
	"""Void a generated invoice the auditable way: the number goes to the
	Cancelled Invoice register (finance never loses a bill in the sequence,
	and the old bill stays printable), then the folio reopens so it can be
	corrected and re-closed under a fresh number."""
	folio = frappe.get_doc("Folio", folio_name)
	if folio.status != "Closed" or not folio.invoice_number:
		frappe.throw("Only a settled folio with an invoice can be cancelled.")
	if not (reason or "").strip():
		frappe.throw("A cancellation needs a reason - it goes on the record.")
	frappe.get_doc({
		"doctype": "Cancelled Invoice",
		"property": folio.property,
		"folio": folio.name,
		"invoice_number": folio.invoice_number,
		"grand_total": folio.grand_total,
		"cancelled_on": now_datetime(),
		"reason": reason.strip(),
	}).insert(ignore_permissions=True)
	old = folio.invoice_number
	folio.invoice_number = None
	folio.status = "Open"
	folio.closed_on = None
	frappe.flags.kamra_invoice_cancel = True
	try:
		folio.save(ignore_permissions=True)
	finally:
		frappe.flags.kamra_invoice_cancel = False
	# where the authority forbids cancelling (ZATCA), this issues the
	# credit note that reverses the invoice
	from kamra import localization as loc
	loc.on_invoice_cancelled(loc.pack_for(folio.property), folio.name, old,
	                         reason.strip())
	return {"cancelled": old, "folio": folio.name}


def apply_no_show(res, pol, decision, business_date) -> dict:
	"""Mark one stay No Show and apply the property's no-show fee policy
	(`decision` from kamra.no_show.audit_outcome): the fee is posted on
	the business date being closed, or waived for an OTA booking. Used by
	the night audit and by the End of Day "Mark no-show" action, so both
	charge the same way. Returns the audit pack's no-show row."""
	before = res.status
	frappe.db.set_value("Reservation", res.name, "status", "No Show")
	# a direct status write skips the Reservation doc events, so tell the
	# webhook subscribers here
	from kamra.webhooks import emit, reservation_payload
	emit("reservation.modified", res.property,
	     {**reservation_payload(res), "status": "No Show",
	      "changes": {"status": [before, "No Show"]}})
	ns = {"reservation": res.name, "guest_name": res.guest_name,
	      "room_type": (res.room_type or "").split("-")[-1],
	      "check_in_date": str(res.check_in_date),
	      "source": res.get("channel") or res.get("source"),
	      "fee": decision.fee, "fee_amount": 0.0,
	      "outcome": "No show - no fee"}
	if decision.fee == "waived":
		ns["outcome"] = f"No show - fee waived ({decision.reason})"
	elif decision.fee == "charge":
		fee = post_policy_fee(res, pol.charge,
		                      f"No-show charge ({pol.charge})",
		                      posting_date=business_date)
		ns["fee_amount"] = float(fee or 0)
		ns["outcome"] = f"No show - {pol.charge.lower()} fee posted"
	return ns


def audit_clock(property: str):
	"""When the audit is running, on the property's clock - what a late
	arrival's ETA is compared with. Its own function so tests can pin it."""
	from kamra.no_show import property_now
	return property_now(property)


def run_night_audit(property: str, business_date: str | None = None,
                    acknowledge=None, note: str | None = None,
                    mode: str | None = None) -> dict:
	"""Automated end-of-day: open missing folios, post the night's room
	charges for every in-house guest, flag no-shows. Closes only the
	property's current business date; a retry for a date that already
	closed returns ``already_ran`` instead of posting twice.

	The night audit checklist (kamra.night_audit) runs first:

	mode "manual" (Billing, REST, MCP): refused while a blocking check has
	  items, unless every one is listed in ``acknowledge`` with a ``note``
	  (the reason) - who acknowledged it and when is stored on the run.
	mode "scheduled" (03:00): follows the property's
	  na_auto_audit_with_blockers - "Run and report exceptions" closes the
	  day and records the blockers as exceptions; "Hold and alert" leaves
	  the business date and alerts Hotel Admin and Finance.
	mode None (an internal call): never gated; open blockers are recorded
	  as exceptions.

	Every run saves its audit pack (night_audit.build_pack) on the record."""
	# In non-request contexts (the 3 AM scheduler, bench console) frappe.local.lang
	# is unset, which makes Frappe's number/currency formatting raise
	# UnboundLocalError. Default it so the audit runs everywhere.
	if not getattr(frappe.local, "lang", None):
		frappe.local.lang = "en"
	from kamra.business_date import ensure_business_date, get_business_date
	ensure_business_date(property)
	current = get_business_date(property)
	business_date = str(getdate(business_date or current))
	# per property AND date - a global AUDIT-<date> name would make the
	# second property's audit silently no-op every night. Checked before
	# the date guards so a retry after success answers already_ran.
	audit_name = f"AUDIT-{business_date}-{property}"
	# an End of Day draft (status Draft) is the wizard's progress for the
	# date, not a closed day
	done = frappe.db.get_value(
		"Night Audit Run",
		{"property": property, "business_date": business_date,
		 "status": ("!=", "Draft")}, "name")
	if done:
		return {"already_ran": True, "audit": done}
	draft_name = frappe.db.get_value(
		"Night Audit Run",
		{"property": property, "business_date": business_date,
		 "status": "Draft"}, "name")
	# The audit only ever closes the property's current business date. A
	# different date would post into a closed day or skip days, and then
	# set the business date to that date + 1.
	if getdate(business_date) != getdate(current):
		frappe.throw(frappe._("Night audit can only close the current business date "
		               "({0}).").format(current))
	# A day can't be closed before it has happened. Without this, repeated
	# clicks rolled the business date into the future and charged in-house
	# guests a room night (and no-shows a fee) per click.
	if getdate(business_date) > getdate(nowdate()):
		frappe.throw(frappe._("Business date {0} is already ahead of today ({1}). "
		               "Night audit for it can run once that day has "
		               "started.").format(business_date, nowdate()))

	# the checklist, as it stands before anything is posted
	from kamra import night_audit as na
	run_at = audit_clock(property)
	checks = na.run_checks(property, business_date, run_at)
	blockers = na.open_blockers(checks)
	acks: list[dict] = []
	if mode == "manual":
		# acknowledged in the End of Day wizard (each with its own reason)
		drafted = {a["key"]: a for a in na.draft_acknowledgements(draft_name)}
		keys = na.parse_keys(acknowledge)
		missing = [c for c in blockers
		           if c["key"] not in keys and c["key"] not in drafted]
		if missing:
			frappe.throw(
				frappe._("Night audit is blocked: {0}. Resolve them, or acknowledge "
				         "each with a reason to run anyway.").format(
					"; ".join(f"{c['title']} ({c['count']})" for c in missing)),
				title=frappe._("Night audit pre-checks"))
		fresh = [c for c in blockers if c["key"] not in drafted]
		if fresh and len((note or "").strip()) < 3:
			frappe.throw(frappe._("Give a reason for acknowledging the blocking "
			                      "checks."))
		acks = [drafted[c["key"]] for c in blockers if c["key"] in drafted] + \
			na.acknowledgement_rows(fresh, keys, (note or "").strip())
	elif mode == "scheduled" and blockers:
		from kamra.settings import get_setting
		if get_setting(property, "na_auto_audit_with_blockers") == na.HOLD_AND_ALERT:
			out = na.hold_and_alert(property, business_date, blockers)
			frappe.db.commit()  # nosemgrep: frappe-manual-commit -- scheduler job persists the hold alert per property; reviewed as intentional
			return out
		acks = na.acknowledgement_rows(
			blockers, [c["key"] for c in blockers],
			"Scheduled audit: run and reported as exceptions", by="Administrator",
			auto=True)

	log_lines = []
	folios_opened = charges_posted = no_shows = 0
	amount_posted = Decimal(0)
	no_show_rows: list[dict] = []

	in_house = frappe.get_all(
		"Reservation",
		filters={
			"property": property,
			"status": "Checked In",
			"check_in_date": ("<=", business_date),
			"check_out_date": (">", business_date),
		},
		fields=["name"],
	)
	for row in in_house:
		res = frappe.get_doc("Reservation", row.name)
		if not frappe.db.get_value(
				"Folio", {"reservation": res.name, "folio_type": "Guest"}):
			folio_name = open_folio(res)
			folios_opened += 1
			log_lines.append(f"opened folio {folio_name} for {res.name}")
		if post_room_night(res, business_date):
			charges_posted += 1
			amount_posted += Decimal(str(_nightly_room_rate(res, business_date)))
			log_lines.append(f"posted room night {business_date} for {res.name}")

	# no-shows: closing day D ends D's arrivals too (Opera end of day), so
	# a confirmed stay due on or before the closed date that never checked
	# in is flagged AND charged per the property's policy - on the closed
	# date, like the room nights of the same run. The property's no-show
	# policy (kamra.no_show) can push that a day later, hold late arrivals
	# due on the closed date until the next audit, and waive the fee on OTA
	# bookings (the OTA collects under its own policy).
	from kamra import no_show
	pol = no_show.policy(property)
	cutoff = business_date if pol.timing != no_show.ONE_DAY_LATER \
		else str(add_days(business_date, -1))
	held_late: list[dict] = []
	fees_waived = 0
	stale = frappe.get_all(
		"Reservation",
		filters={
			"property": property,
			"status": "Confirmed",
			"check_in_date": ("<=", cutoff),
		},
		fields=["name"],
		order_by="check_in_date asc, name asc",
	)
	for row in stale:
		res = frappe.get_doc("Reservation", row.name)
		decision = no_show.audit_outcome(res, pol, business_date, run_at)
		if decision.outcome == "defer":
			continue
		if decision.outcome == "hold":
			held_late.append({"reservation": res.name,
			                  "guest_name": res.guest_name,
			                  "eta": res.get("eta") or None,
			                  "reason": decision.reason})
			log_lines.append(f"held late arrival: {res.name} ({decision.reason})")
			continue
		ns = apply_no_show(res, pol, decision, business_date)
		no_shows += 1
		no_show_rows.append(ns)
		log_lines.append(f"flagged no-show: {row.name}")
		if decision.fee == "waived":
			fees_waived += 1
			log_lines.append(
				f"no-show fee waived for {row.name}: {decision.reason}")
		if ns["fee_amount"]:
			amount_posted += Decimal(str(ns["fee_amount"]))
			log_lines.append(
				f"posted no-show charge {ns['fee_amount']:,.2f} for {row.name}")

	# purge stale waitlist entries - two days after their requested departure
	from frappe.utils import add_days as _add_days
	purged = 0
	for wl in frappe.get_all("Reservation", filters={
			"property": property, "status": "Waitlist",
			"check_out_date": ("<=", _add_days(business_date, -2))}, pluck="name"):
		frappe.delete_doc("Reservation", wl, ignore_permissions=True, force=True)
		purged += 1
	if purged:
		log_lines.append(f"purged {purged} stale waitlist entries")

	for a in acks:
		log_lines.append(f"acknowledged {a['key']} ({a['count']}) by {a['by']}: "
		                 f"{a['note']}")
	unacked = [c for c in blockers if c["key"] not in {a["key"] for a in acks}]
	for c in unacked:
		log_lines.append(f"exception: {c['title']} ({c['count']})")
	trigger = {"manual": "Manual", "scheduled": "Scheduled"}.get(mode or "", "System")
	summary = {
		"room_charges_posted": charges_posted,
		"amount_posted": float(amount_posted),
		"no_shows_flagged": no_shows,
		"late_arrivals_held": len(held_late),
		"no_show_fees_waived": fees_waived,
		"folios_opened": folios_opened,
		"trigger": trigger,
		"run_by": frappe.session.user,
		"exceptions": len(blockers),
		"notes": (frappe.db.get_value("Night Audit Run", draft_name,
		                              "auditor_notes") if draft_name else None),
	}
	try:
		pack = na.build_pack(property, business_date, checks=checks,
		                     acknowledgements=acks, summary=summary,
		                     no_shows=no_show_rows, held_late=held_late)
		report_pack = json.dumps(pack, default=str)
	except Exception:
		frappe.log_error(title=f"Night audit pack failed: {property}")
		report_pack = None

	values = {
		"status": "Completed with Warnings" if blockers else "Completed",
		"room_charges_posted": charges_posted,
		"amount_posted": float(amount_posted),
		"no_shows_flagged": no_shows,
		"late_arrivals_held": len(held_late),
		"no_show_fees_waived": fees_waived,
		"folios_opened": folios_opened,
		"run_trigger": trigger,
		"run_by": frappe.session.user,
		"exceptions": len(blockers),
		"acknowledgements": json.dumps(acks) if acks else None,
		"report_pack": report_pack,
		"log": "\n".join(log_lines) or "Nothing to do.",
		"eod_step": 11,
	}
	if draft_name:
		# the wizard's draft becomes the run: its notes and progress stay
		audit = frappe.get_doc("Night Audit Run", draft_name)
		audit.update(values)
		audit.save(ignore_permissions=True)
	else:
		audit = frappe.get_doc({"doctype": "Night Audit Run",
		                        "property": property,
		                        "business_date": business_date, **values})
		audit.insert(ignore_permissions=True)

	# Advance the front-office business date (Opera End of Day roll).
	from kamra.business_date import advance_business_date, ensure_business_date
	ensure_business_date(property)
	new_bd = advance_business_date(property, business_date)

	from kamra.savings import log_action
	log_action(
		action_type="night_audit",
		reference_doctype="Night Audit Run",
		reference_name=audit.name,
		property=property,
		minutes_saved=90,
		rationale=f"Posted {charges_posted} room nights, flagged {no_shows} "
		          f"no-shows, held {len(held_late)} late arrivals for "
		          f"{business_date}; business date → {new_bd}",
		agent_name="Night Audit",
		autonomy="Full",
		channel="API",
	)
	if acks and mode == "manual":
		log_action(
			action_type="night_audit_acknowledged",
			reference_doctype="Night Audit Run",
			reference_name=audit.name,
			property=property,
			rationale="Blocking checks acknowledged: "
			          + "; ".join(f"{a['title']} ({a['count']})" for a in acks)
			          + f" - {acks[0]['note']}",
			channel="MCP" if frappe.flags.get("kamra_agent_call") else "Desk",
			after_snapshot=acks,
		)
	from kamra.webhooks import emit_night_audit_closed
	emit_night_audit_closed(property, {
		"audit": audit.name, "status": audit.status,
		"business_date": business_date, "next_business_date": new_bd,
		"room_charges_posted": charges_posted,
		"amount_posted": float(amount_posted), "no_shows_flagged": no_shows,
		"exceptions": len(blockers)})
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional
	return {
		"audit": audit.name,
		"status": audit.status,
		"exceptions": len(blockers),
		"acknowledged": [a["key"] for a in acks],
		"has_pack": bool(report_pack),
		"room_charges_posted": charges_posted,
		"amount_posted": float(amount_posted),
		"no_shows_flagged": no_shows,
		"late_arrivals_held": len(held_late),
		"held_late_arrivals": held_late,
		"no_show_fees_waived": fees_waived,
		"folios_opened": folios_opened,
		"business_date": business_date,
		"next_business_date": new_bd,
	}


def nightly_audit_all_properties():
	"""Scheduler entry point - runs the audit for every active property.

	The cron fires at 03:00, so it only closes a business date that is
	strictly before today. If staff already closed yesterday by hand, the
	business date is today and that day has only just started - leave it."""
	today = getdate(nowdate())
	for p in frappe.get_all("Property", filters={"disabled": 0}):
		try:
			from kamra.business_date import ensure_business_date
			bd = getdate(ensure_business_date(p.name))
			if bd >= today:
				frappe.logger("kamra").info(
					f"Night audit skipped for {p.name}: business date {bd} "
					f"is not before today ({today})")
				continue
			run_night_audit(p.name, mode="scheduled")
		except Exception:
			frappe.log_error(title=f"Night audit failed: {p.name}")
