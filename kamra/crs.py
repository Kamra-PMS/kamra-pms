"""Central Reservation System - work across the whole chain.

`crs_search` looks for a room across every property the signed-in user may
access and returns what's available where, with live rates, so the front
desk can place a guest at whichever hotel has space. The booking itself
still goes through create_booking against the chosen property.

`permitted_properties` / `assert_property_access` are the chain's access
guard: endpoints that take a `property` argument can no longer be pointed
at a hotel the user isn't allowed to touch.

Itineraries: one trip across several properties (2 nights at A, then 3 at
B). Each leg is an ordinary Reservation at its own property - priced by
get_quote, booked by create_booking, guarded by the overlap and capacity
checks, billed on its own folio (tax and invoices stay per property) - and
points at one Itinerary record the guest can quote. Cancelling goes
through each leg's cancellation_preview / cancel_reservation, so every
leg's own policy and fee apply. Advances are taken per leg (record_advance
on that leg's booking), or once for the whole trip (record_trip_advance),
which splits the payment across the legs and books each share through
record_advance on that leg - the itinerary itself never holds money.
"""

import frappe
from frappe import _
from frappe.utils import cint, date_diff, getdate

from kamra.authz import require_roles


def permitted_properties() -> set[str]:
	"""The set of property names the current user may work with (native
	Frappe User Permissions decide this via my_properties)."""
	from kamra.api import my_properties
	return {p["name"] for p in my_properties()}


def assert_property_access(property: str):
	"""Guard: refuse an action aimed at a property the user isn't permitted
	for. A no-op for users with no property restriction (they see all)."""
	from kamra.authz import assert_property_access as _guard
	_guard(property)


@frappe.whitelist()
@require_roles("Front Desk", "Revenue Manager", "Hotel Admin", "Kamra Agent")
def crs_search(check_in_date: str, check_out_date: str,
               adults: int = 2, children: int = 0):
	"""Find a room across the chain: for every property the user can access,
	the room types with space for these dates and their all-in rate."""
	from kamra.api import available_rooms
	from kamra.pricing import quote

	nights = max(1, date_diff(check_out_date, check_in_date))
	results = []
	for prop in sorted(permitted_properties()):
		rts = frappe.get_all(
			"Room Type",
			filters={"property": prop, "disabled": 0},
			fields=["name", "room_type_name", "base_price",
			        "adults_capacity", "children_capacity"],
			order_by="base_price asc")
		room_types = []
		for rt in rts:
			# capacity gate: skip a type that can't sleep the party
			if rt.adults_capacity and int(adults) > rt.adults_capacity:
				continue
			free = available_rooms(prop, rt.name, check_in_date, check_out_date)
			if not free:
				continue
			try:
				q = quote(prop, rt.name, check_in_date, check_out_date,
				          int(adults), int(children))
			except Exception:
				continue
			total = q.get("amount_after_tax", 0)
			room_types.append({
				"room_type": rt.name,
				"room_type_name": rt.room_type_name,
				"available": len(free),
				"adults_capacity": rt.adults_capacity,
				"children_capacity": rt.children_capacity,
				"total": round(total, 0),
				"per_night": round(total / nights, 0) if nights else total,
			})
		if room_types:
			p = frappe.db.get_value(
				"Property", prop, ["property_name", "city"], as_dict=True)
			results.append({
				"property": prop,
				"property_name": p.property_name,
				"city": p.city,
				"available_rooms": sum(r["available"] for r in room_types),
				"from_rate": min(r["per_night"] for r in room_types),
				"room_types": room_types,
			})
	# cheapest-entry-point first
	results.sort(key=lambda r: r["from_rate"])
	return {
		"check_in_date": check_in_date,
		"check_out_date": check_out_date,
		"nights": nights,
		"adults": int(adults),
		"children": int(children),
		"properties": results,
	}


# ── itineraries ──────────────────────────────────────────────────────────

_LEG_KEYS = ("property", "room_type", "check_in_date", "check_out_date")


def _parse_legs(legs) -> list[dict]:
	"""The legs a caller asked for, checked and in date order: every leg
	names a property the user may access, stays at least one night, and no
	two legs overlap (the guest can't be in two hotels on one night; a leg
	may start the day the previous one ends)."""
	if isinstance(legs, str):
		legs = frappe.parse_json(legs)
	if not legs:
		frappe.throw(_("Add at least one stay to the itinerary."))
	out = []
	for leg in legs:
		missing = [k for k in _LEG_KEYS if not leg.get(k)]
		if missing:
			frappe.throw(_("Each stay needs {0}.").format(", ".join(missing)))
		assert_property_access(leg["property"])
		if date_diff(leg["check_out_date"], leg["check_in_date"]) < 1:
			frappe.throw(_("Each stay in an itinerary is at least one night."))
		out.append(dict(leg))
	out.sort(key=lambda leg: getdate(leg["check_in_date"]))
	_refuse_overlap(out)
	return out


def _refuse_overlap(legs: list[dict]):
	"""legs in check-in order; refuse the first pair that shares a night.
	A leg at a property the user can't access is never described: its
	dates would tell a restricted user about a stay at another hotel."""
	from kamra.authz import restricted_properties
	allowed = restricted_properties()
	for prev, nxt in zip(legs, legs[1:]):
		if getdate(nxt["check_in_date"]) < getdate(prev["check_out_date"]):
			if allowed is not None and any(
					leg.get("property") not in allowed for leg in (prev, nxt)):
				frappe.throw(_("These dates conflict with another stay on this "
				               "trip."), title=_("Itinerary dates overlap"))
			frappe.throw(_("Stays overlap: {0} to {1} and {2} to {3}. A guest "
			               "can't be in two places on one night.").format(
				prev["check_in_date"], prev["check_out_date"],
				nxt["check_in_date"], nxt["check_out_date"]),
				title=_("Itinerary dates overlap"))


def _live_legs(itinerary: str, exclude: str | None = None) -> list[dict]:
	from kamra.reservation_state import LIVE_STATUSES
	filters = {"itinerary": itinerary, "status": ("in", list(LIVE_STATUSES))}
	if exclude:
		filters["name"] = ("!=", exclude)
	return frappe.get_all("Reservation", filters=filters,
	                      fields=["name", "property", "check_in_date", "check_out_date"])


def assert_leg_fits(itinerary: str, check_in_date, check_out_date,
                    reservation: str | None = None, property: str | None = None):
	"""Reservation.validate: a live leg can't overlap another live leg of
	its itinerary (covers amend_stay on one leg)."""
	legs = _live_legs(itinerary, exclude=reservation) + [{
		"property": property,
		"check_in_date": check_in_date, "check_out_date": check_out_date}]
	legs.sort(key=lambda leg: getdate(leg["check_in_date"]))
	_refuse_overlap(legs)


def _leg_int(leg: dict, key: str, default) -> int:
	"""A leg's own adults / children, else the trip's. An explicit 0 on
	the leg (no children on this stay) is kept, not replaced."""
	v = leg.get(key)
	return cint(default if v in (None, "") else v)


def _locale(property: str) -> dict:
	from kamra.localization import pack_for
	loc = pack_for(property).locale(frappe.get_cached_doc("Property", property))
	return {"currency": loc.get("currency"),
	        "currency_symbol": loc.get("currency_symbol") or ""}


def _sum(rows: list[dict], key: str):
	"""A combined figure only when every leg is in one currency - two
	currencies don't add up to one number."""
	if len({r["currency"] for r in rows}) > 1:
		return None
	return round(sum(float(r.get(key) or 0) for r in rows), 2)


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
def quote_itinerary(legs, adults: int = 2, children: int = 0,
                    company: str | None = None):
	"""Price a multi-property trip before booking it: each leg priced by
	get_quote (the same engine create_booking uses), rooms free per leg,
	and the combined total. legs: [{property, room_type, check_in_date,
	check_out_date, adults?, children?, meal_plan?, rate_plan?}]."""
	from kamra.api import available_rooms, get_quote
	from kamra.booking_refs import resolve_room_type

	out = []
	for leg in _parse_legs(legs):
		prop = leg["property"]
		q = get_quote(property=prop, room_type=leg["room_type"],
		              check_in_date=leg["check_in_date"],
		              check_out_date=leg["check_out_date"],
		              adults=_leg_int(leg, "adults", adults),
		              children=_leg_int(leg, "children", children),
		              meal_plan=leg.get("meal_plan"),
		              rate_plan=leg.get("rate_plan"), company=company)
		rt = resolve_room_type(prop, leg["room_type"])
		out.append({
			**leg, **_locale(prop),
			"room_type": rt,
			"property_name": frappe.db.get_value(
				"Property", prop, "property_name"),
			"room_type_name": frappe.db.get_value(
				"Room Type", rt, "room_type_name"),
			"nights": date_diff(leg["check_out_date"], leg["check_in_date"]),
			"available": len(available_rooms(
				prop, rt, leg["check_in_date"], leg["check_out_date"])),
			"amount_after_tax": q.get("amount_after_tax"),
			# the advance this leg's dates ask for at its property
			"advance_percent": q["advance"]["percent"],
			"advance_due": q["advance"]["amount"],
			"cancellation": q.get("cancellation"),
		})
	return {"legs": out, "total": _sum(out, "amount_after_tax"),
	        "advance_due": _sum(out, "advance_due")}


def _book_legs(itn, legs: list[dict], adults, children, phone,
               idempotency_key: str | None):
	"""Book each leg through create_booking (pricing, room, overlap and
	credit guards all apply) and tie it to the itinerary."""
	from kamra.api import create_booking

	for i, leg in enumerate(legs):
		r = create_booking(
			property=leg["property"], room_type=leg["room_type"],
			check_in_date=leg["check_in_date"],
			check_out_date=leg["check_out_date"],
			guest_name=itn.guest_name, phone=phone, guest=itn.guest,
			adults=_leg_int(leg, "adults", adults),
			children=_leg_int(leg, "children", children),
			meal_plan=leg.get("meal_plan"), rate_plan=leg.get("rate_plan"),
			company=itn.company, travel_agent=itn.travel_agent,
			booking_type="Corporate" if itn.company else "Individual",
			booked_by_name=itn.booked_by_name,
			booked_by_phone=itn.booked_by_phone,
			idempotency_key=f"{idempotency_key}:{i}" if idempotency_key else None)
		if not frappe.db.exists("Itinerary", itn.name):
			# create_booking's deadlock retry rolled the whole transaction
			# back (the itinerary and the legs before this one with it):
			# refuse rather than leave this leg booked on its own
			frappe.throw(_("The booking system was busy. Nothing was booked; "
			               "please try again."), title=_("Try again"))
		other = frappe.db.get_value("Reservation", r["reservation"], "itinerary")
		if other and other != itn.name:
			# create_booking handed back a booking that already belongs to
			# another trip (an agent retry): never move it between trips
			# (named neither: the other trip may be at a hotel the user
			# can't see)
			frappe.throw(_("This booking already belongs to another trip."),
			             title=_("Already booked"))
		frappe.db.set_value("Reservation", r["reservation"], "itinerary",
		                    itn.name)


def _savepoint(fn):
	"""All legs or none: a leg that fails rolls back the ones before it."""
	sp = f"itn_{frappe.generate_hash(length=8)}"
	frappe.db.savepoint(sp)
	try:
		return fn()
	except Exception:
		try:
			frappe.db.rollback(save_point=sp)
		except Exception:
			# the savepoint went with a full rollback inside (create_booking's
			# deadlock retry): drop what was written after it as well
			frappe.db.rollback()
		raise


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Kamra Agent")
def create_itinerary(legs, guest_name: str | None = None,
                     phone: str | None = None, guest: str | None = None,
                     adults: int = 2, children: int = 0,
                     company: str | None = None,
                     travel_agent: str | None = None,
                     booked_by_name: str | None = None,
                     booked_by_phone: str | None = None,
                     notes: str | None = None,
                     idempotency_key: str | None = None):
	"""Book a trip across properties in one go: one reservation per leg
	(each a normal booking at its own property, with its own folio) under
	one itinerary reference. All legs book or none do. Quote first with
	quote_itinerary. Take one advance for the trip with record_trip_advance,
	or per leg with record_advance."""
	from kamra.api import _find_or_create_guest

	legs = _parse_legs(legs)
	key = (idempotency_key or "").strip() or None
	if key:
		existing = frappe.db.get_value("Itinerary", {"idempotency_key": key})
		if existing:
			return {**get_itinerary(existing), "idempotent_replay": 1}
	if guest:
		if not frappe.db.exists("Guest", guest):
			frappe.throw(_("Guest profile {0} not found.").format(guest))
	elif (guest_name or "").strip():
		guest = _find_or_create_guest(guest_name, phone, legs[0]["property"])
	else:
		frappe.throw(_("Enter the guest's name."))

	def book():
		itn = frappe.get_doc({
			"doctype": "Itinerary", "guest": guest, "company": company or None,
			"travel_agent": travel_agent or None,
			"booked_by_name": booked_by_name or None,
			"booked_by_phone": booked_by_phone or None,
			"notes": notes or None, "idempotency_key": key,
		}).insert(ignore_permissions=True)  # gated above; the doctype is read only
		_book_legs(itn, legs, adults, children, phone, key)
		return itn.name

	name = _savepoint(book)
	from kamra.savings import log_action
	log_action("create_itinerary", "Itinerary", name, legs[0]["property"],
	           rationale=f"Trip of {len(legs)} stays for {guest_name or guest}: "
	           + ", ".join(f"{leg['property']} {leg['check_in_date']} to "
	                       f"{leg['check_out_date']}" for leg in legs))
	return get_itinerary(name)


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Kamra Agent")
def add_itinerary_leg(itinerary: str, property: str, room_type: str,
                      check_in_date: str, check_out_date: str,
                      adults: int = 2, children: int = 0,
                      meal_plan: str | None = None,
                      rate_plan: str | None = None):
	"""Add one more stay to an existing trip. It can't overlap a live leg."""
	itn = _itinerary(itinerary)
	# two adds at once: the second waits here and then sees the first's leg
	frappe.db.get_value("Itinerary", itn.name, "name", for_update=True)
	leg = _parse_legs([{
		"property": property, "room_type": room_type,
		"check_in_date": check_in_date, "check_out_date": check_out_date,
		"meal_plan": meal_plan, "rate_plan": rate_plan}])[0]
	assert_leg_fits(itn.name, check_in_date, check_out_date, property=property)
	phone = frappe.db.get_value("Guest", itn.guest, "phone")
	_savepoint(lambda: _book_legs(itn, [leg], adults, children, phone, None))
	return get_itinerary(itn.name)


def _itinerary(itinerary: str):
	"""The itinerary, if the user may access every property it touches -
	a trip is worked as a whole, so a partial view is refused. The refusal
	is the same as for a trip that doesn't exist: it never names (or
	confirms) a hotel the user can't see. A trip with no legs yet is shown
	only to users with no property restriction (authz.itinerary_has_permission)."""
	from kamra.authz import restricted_properties
	exists = frappe.db.exists("Itinerary", itinerary)
	allowed = restricted_properties()
	if exists and allowed is not None:
		props = set(frappe.get_all("Reservation", filters={"itinerary": itinerary},
		                           pluck="property", distinct=True))
		exists = bool(props) and props <= allowed
	if not exists:
		frappe.throw(_("Itinerary not found."), frappe.DoesNotExistError)
	return frappe.get_doc("Itinerary", itinerary)


def _status(legs: list[dict]) -> str:
	statuses = {leg["status"] for leg in legs}
	if not statuses or statuses == {"Cancelled"}:
		return "Cancelled"
	if "Checked In" in statuses:
		return "In stay"
	if statuses & {"Confirmed", "Held", "Pending Payment"}:
		return "Booked"
	return "Completed"


_LEG_FIELDS = ["name", "property", "room_type", "room", "check_in_date",
               "check_out_date", "nights", "adults", "children", "status",
               "amount_after_tax", "advance_paid", "cancellation_number",
               "cancellation_fee"]


def _legs_of(names: list[str]) -> dict[str, list[dict]]:
	rows = frappe.get_all("Reservation", filters={"itinerary": ("in", names)},
	                      fields=["itinerary", *_LEG_FIELDS],
	                      order_by="check_in_date asc, creation asc")
	out: dict[str, list[dict]] = {}
	for r in rows:
		out.setdefault(r.pop("itinerary"), []).append(r)
	return out


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Kamra Agent")
def get_itinerary(itinerary: str):
	"""A trip with its legs in date order: each leg's property, dates,
	status, price, advance paid and deposit still due, plus the combined
	total (live legs) - what the combined confirmation prints."""
	from kamra.api import _deposit_state
	from kamra.reservation_state import LIVE_STATUSES

	itn = _itinerary(itinerary)
	legs = _legs_of([itn.name]).get(itn.name, [])
	for leg in legs:
		leg.update(_locale(leg["property"]))
		leg["reservation"] = leg.pop("name")
		leg["property_name"], leg["city"], leg["property_phone"] = \
			frappe.db.get_value("Property", leg["property"],
			                    ["property_name", "city", "phone"])
		leg["room_type_name"] = frappe.db.get_value(
			"Room Type", leg["room_type"], "room_type_name")
		dep = _deposit_state(frappe._dict(
			name=leg["reservation"], property=leg["property"],
			amount_after_tax=leg["amount_after_tax"],
			advance_paid=leg["advance_paid"], status=leg["status"]))
		leg["advance_percent"] = dep["pct"]
		leg["advance_required"] = dep["expected"] if dep["can_take"] else 0.0
		leg["deposit_due"] = dep["due"] if dep["can_take"] else 0.0
	live = [leg for leg in legs if leg["status"] in LIVE_STATUSES]
	guest = frappe.db.get_value("Guest", itn.guest,
	                            ["full_name", "phone", "email"], as_dict=True)
	return {
		"name": itn.name, "guest": itn.guest,
		"guest_name": guest.full_name if guest else itn.guest_name,
		"phone": guest.phone if guest else None,
		"email": guest.email if guest else None,
		"company": itn.company, "travel_agent": itn.travel_agent,
		"booked_by_name": itn.booked_by_name, "notes": itn.notes,
		"created": str(itn.creation),
		"status": _status(legs),
		"check_in_date": str(live[0]["check_in_date"]) if live else None,
		"check_out_date": str(live[-1]["check_out_date"]) if live else None,
		"legs": legs,
		"total": _sum(live, "amount_after_tax"),
		"advance_paid": _sum(live, "advance_paid"),
		"advance_required": _sum(live, "advance_required"),
		"advance_due": _sum(live, "deposit_due"),
		# advances taken on legs since cancelled and not refunded: still on
		# those folios (the fee kept, or a refund to make). Not in advance_paid,
		# which is the live stays' only
		"advance_held_cancelled": _sum(
			[leg for leg in legs if leg["status"] == "Cancelled"], "advance_paid"),
		"cancellation_fees": _sum(legs, "cancellation_fee"),
	}


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Kamra Agent")
def list_itineraries(search: str | None = None, limit: int = 50):
	"""Recent trips the user can work with (every leg at a property they
	may access), newest first, with their legs and status."""
	# get_list, not get_all: kamra.authz.itinerary_query_conditions drops
	# trips with a leg the user can't access in SQL, before the limit
	ref = (search or "").strip()
	or_filters = {"guest_name": ("like", f"%{ref}%"), "name": ref} if ref else None
	rows = frappe.get_list("Itinerary", or_filters=or_filters,
	                       fields=["name", "guest_name"],
	                       order_by="creation desc",
	                       limit=min(cint(limit) or 50, 200))
	legs = _legs_of([r.name for r in rows]) if rows else {}
	out = []
	for row in rows:
		ls = legs.get(row.name, [])
		out.append({
			"name": row.name, "guest_name": row.guest_name, "status": _status(ls),
			"legs": [{"reservation": leg["name"], "property": leg["property"],
			          "check_in_date": str(leg["check_in_date"]),
			          "check_out_date": str(leg["check_out_date"]),
			          "status": leg["status"]} for leg in ls],
		})
	return out


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
def cancel_itinerary_preview(itinerary: str):
	"""What cancelling the whole trip would cost now: each leg's own
	cancellation_preview (its property's policy) and the total fee. Legs
	already checked in or finished can't be cancelled and are listed apart."""
	from kamra.api import cancellation_preview

	itn = _itinerary(itinerary)
	rows, skipped = [], []
	for leg in _legs_of([itn.name]).get(itn.name, []):
		if leg["status"] != "Confirmed":
			skipped.append({"reservation": leg["name"], "status": leg["status"]})
			continue
		terms = cancellation_preview(reservation=leg["name"])
		rows.append({"reservation": leg["name"], "property": leg["property"],
		             **_locale(leg["property"]), **terms})
	return {"legs": rows, "not_cancellable": skipped,
	        "total_fee": _sum(rows, "estimated_fee")}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Kamra Agent")
def cancel_itinerary(itinerary: str, reason: str = "Guest request",
                     note: str | None = None, waive_fee: int = 0):
	"""Cancel every confirmed leg of a trip, each through cancel_reservation
	so its own property's policy and fee apply (waive_fee=1 waives them all,
	logged per leg). All legs cancel or none do. To cancel one leg, call
	cancel_reservation on it."""
	from kamra.api import cancel_reservation

	itn = _itinerary(itinerary)
	legs = [leg["name"] for leg in _legs_of([itn.name]).get(itn.name, [])
	        if leg["status"] == "Confirmed"]
	if not legs:
		frappe.throw(_("Nothing to cancel: no leg of this itinerary is "
		               "confirmed."))
	results = _savepoint(lambda: [
		cancel_reservation(reservation=r, reason=reason, note=note,
		                   waive_fee=waive_fee) for r in legs])
	return {"itinerary": itn.name, "cancelled": results,
	        **get_itinerary(itn.name)}


# ── one advance for the whole trip ───────────────────────────────────────

def allocate_trip_advance(rows: list[dict], amount: float) -> list[float]:
	"""Split one trip payment across its legs (rows in date order, each
	{due, open}: advance still due, and the bill not yet paid).

	First every leg gets up to its own advance still due, earliest stay
	first, so each hotel is secured to its own policy before any money
	runs ahead. What is left goes to the earliest leg, up to that leg's
	unpaid bill, then the next: one leg is never paid more than it costs,
	so no hotel ends the stay holding money it has to refund. A payment
	larger than the whole trip's unpaid total is refused by the caller."""
	shares = [0.0] * len(rows)
	left = round(float(amount), 2)
	for key in ("due", "open"):
		for i, r in enumerate(rows):
			room = round(float(r[key]) - shares[i], 2)
			take = min(left, max(room, 0.0))
			shares[i] = round(shares[i] + take, 2)
			left = round(left - take, 2)
	return shares


def _trip_advance(itinerary: str, amount=None) -> dict:
	from kamra.api import _DEPOSIT_STATUSES

	trip = get_itinerary(itinerary)
	legs = [leg for leg in trip["legs"] if leg["status"] in _DEPOSIT_STATUSES]
	if not legs:
		frappe.throw(_("No stay on this trip is waiting for an advance. "
		               "Take in-house payments on the leg's folio."))
	if len({leg["currency"] for leg in legs}) > 1:
		frappe.throw(_("The stays on this trip are in different currencies. "
		               "Take the advance on each stay instead."))
	rows = [{"due": float(leg["deposit_due"] or 0),
	         "open": max(0.0, round(float(leg["amount_after_tax"] or 0)
	                                - float(leg["advance_paid"] or 0), 2))}
	        for leg in legs]
	due = round(sum(r["due"] for r in rows), 2)
	unpaid = round(sum(r["open"] for r in rows), 2)
	amount = round(float(amount), 2) if amount not in (None, "") else due
	if amount <= 0:
		frappe.throw(_("Enter the advance amount."))
	if amount > unpaid + 0.005:
		frappe.throw(_("{0} is more than the trip still owes ({1}).").format(
			f"{amount:,.2f}", f"{unpaid:,.2f}"))
	shares = allocate_trip_advance(rows, amount)
	return {
		"itinerary": trip["name"], "amount": amount,
		"currency": legs[0]["currency"],
		"currency_symbol": legs[0]["currency_symbol"],
		"advance_required": trip["advance_required"],
		"advance_paid": trip["advance_paid"],
		"advance_due": due, "unpaid": unpaid,
		"legs": [{"reservation": leg["reservation"],
		          "property": leg["property"],
		          "property_name": leg["property_name"],
		          "check_in_date": str(leg["check_in_date"]),
		          "check_out_date": str(leg["check_out_date"]),
		          "advance_percent": leg["advance_percent"],
		          "advance_required": leg["advance_required"],
		          "advance_paid": float(leg["advance_paid"] or 0),
		          "advance_due": r["due"], "share": share}
		         for leg, r, share in zip(legs, rows, shares)],
	}


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Kamra Agent")
def trip_advance_preview(itinerary: str, amount: float | None = None):
	"""How one advance for the whole trip would be split across its legs,
	before taking it: each leg's advance % and amount still due, and its
	share. Without an amount, the trip's advance still due. Show this to
	the guest or staff, then call record_trip_advance with the same amount."""
	return _trip_advance(itinerary, amount)


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance", "Kamra Agent")
def record_trip_advance(itinerary: str, amount: float, mode: str = "Cash",
                        reference: str | None = None, pin: str | None = None,
                        idempotency_key: str | None = None):
	"""Take one advance for the whole trip. The payment is split as
	trip_advance_preview shows and each share is recorded through
	record_advance on its leg, so every hotel's folio, till and books get
	their own part (refunds and cancellation then follow that leg's own
	policy). All shares post or none do. A retry with the same
	idempotency_key returns the trip without posting again."""
	from kamra.api import _paid_with_key, record_advance
	from kamra.authz import require_cashier_pin
	from kamra.cashier import require_open_session
	from kamra.localization import pack_for, payment_modes

	itn = _itinerary(itinerary)
	# one trip advance at a time: lock the trip, then its legs (name order,
	# as a per-leg record_advance locks them), so what is still owed is
	# read after any advance a double submit just posted
	frappe.db.get_value("Itinerary", itn.name, "name", for_update=True)
	legs = frappe.db.sql(
		"SELECT name FROM `tabReservation` WHERE itinerary = %s "
		"ORDER BY name FOR UPDATE", (itn.name,), pluck=True)
	key = (idempotency_key or "").strip() or None
	if key and any(_paid_with_key(key, reservation=r) for r in legs):
		return {"idempotent_replay": 1, **get_itinerary(itn.name)}
	plan = _trip_advance(itn.name, amount)
	paying = [leg for leg in plan["legs"] if leg["share"] > 0]
	# every money guard of every hotel before the first write
	for prop in dict.fromkeys(leg["property"] for leg in paying):
		modes = payment_modes(pack_for(prop))
		if mode not in modes:
			frappe.throw(_("Pick a payment mode: {0}.").format(", ".join(modes)))
		require_cashier_pin(prop, pin)
		require_open_session(prop)
	ref = reference or f"trip:{plan['itinerary']}"
	_savepoint(lambda: [
		record_advance(reservation=leg["reservation"], amount=leg["share"],
		               mode=mode, reference=ref, pin=pin, idempotency_key=key)
		for leg in paying])
	from kamra.savings import log_action
	log_action("record_trip_advance", "Itinerary", plan["itinerary"],
	           paying[0]["property"],
	           rationale=f"{mode} trip advance {plan['amount']:,.2f}: " + ", ".join(
	               f"{leg['reservation']} {leg['share']:,.2f}" for leg in paying))
	return {"allocation": plan["legs"], "amount": plan["amount"],
	        **get_itinerary(plan["itinerary"])}
