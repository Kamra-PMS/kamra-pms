"""Recreation desk (#632), day one: a gym (or pool, spa, …) for in-house
guests and for members.

In-house access posts to the guest folio when it is paid, or is recorded
as complimentary. A membership covers an external customer for a day,
week, month or year, with an optional visit limit. Walk-in cash is
recorded on the visit. It is an operational receipt, not a tax invoice
and not a room folio - registering a recreation customer does not create
a stay.

Then: per-facility plans, renewals and expiry; QR passes for members
and in-house guests; spa treatments booked with a therapist and a room,
and pool or court sessions, never double-booked; walk-in and membership
cash through the till with a printable receipt; the reports and a
membership ledger per customer.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, time, timedelta

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, flt, get_datetime, getdate, now_datetime, nowdate, nowtime

from kamra.authz import require_roles

CATEGORIES = ("Gym", "Pool", "Spa", "Sauna", "Steam", "Yoga", "Court", "Other")
ACCESS = ("Complimentary", "Paid", "Both")
PERIODS = ("Day", "Week", "Month", "Year")
SPA_CHARGE = {"Spa", "Sauna", "Steam", "Yoga", "Pool"}
DESK = ("Front Desk", "Hotel Admin", "F&B Manager")


def _end(start, period: str):
	"""Last day the membership is valid, inclusive. A month bought on the
	15th runs through the 14th; when the anniversary day does not exist
	(31 Jan + a month) it runs through the last day of that month."""
	start = getdate(start)
	if period == "Day":
		return start
	if period == "Week":
		return add_days(start, 6)
	if period not in ("Month", "Year"):
		frappe.throw(_("Unknown membership period."))
	anniversary = getdate(add_months(start, 1 if period == "Month" else 12))
	return add_days(anniversary, -1) if anniversary.day == start.day else anniversary


def as_time(value) -> time | None:
	"""A Time field (timedelta from the database, time, or 'HH:MM[:SS]')."""
	if value in (None, ""):
		return None
	if isinstance(value, time):
		return value
	if isinstance(value, timedelta):
		secs = int(value.total_seconds()) % 86400
		return time(secs // 3600, (secs % 3600) // 60, secs % 60)
	parts = str(value).strip().split(":")
	try:
		return time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
	except (ValueError, IndexError):
		return None


def within_hours(now: time, opens: time | None, closes: time | None) -> bool:
	"""Blank or equal hours: always open. Closing before opening crosses
	midnight (22:00-02:00)."""
	if opens is None or closes is None or opens == closes:
		return True
	if opens < closes:
		return opens <= now <= closes
	return now >= opens or now <= closes


def _open_now(doc) -> bool:
	return doc.status == "Open" and within_hours(
		as_time(nowtime()), as_time(doc.opens), as_time(doc.closes))


def _inside(facility: str) -> int:
	return frappe.db.count("Recreation Visit", {"facility": facility, "status": "In"})


def _charge_type(category: str) -> str:
	return "Spa" if category in SPA_CHARGE else "Misc"


def plan_facilities(plan: str) -> list[str]:
	"""The facilities a plan opens; empty = every facility at the property."""
	one = frappe.db.get_value("Recreation Plan", plan, "facility")
	rows = frappe.get_all("Recreation Plan Facility", pluck="facility",
	                      filters={"parent": plan, "parenttype": "Recreation Plan"})
	return sorted({*rows, *([one] if one else [])})


def _covering(customer: str, facility, today: str):
	"""The membership this visit uses: a plan for this facility before an
	every-facility plan, then the one ending soonest (a day pass before a
	monthly). Exhausted visit limits don't cover."""
	rows = frappe.get_all(
		"Recreation Membership",
		filters={
			"customer": customer,
			"status": "Active",
			"starts_on": ["<=", today],
			"ends_on": [">=", today],
		},
		fields=["name", "plan", "visits_used", "ends_on"])
	best = []
	for row in rows:
		plan = frappe.db.get_value(
			"Recreation Plan", row.plan, ["visit_limit", "property"], as_dict=True)
		if not plan or plan.property != facility.property:
			continue
		opens = plan_facilities(row.plan)
		if opens and facility.name not in opens:
			continue
		limit = int(plan.visit_limit or 0)
		if limit and int(row.visits_used or 0) >= limit:
			continue
		best.append((0 if opens else 1, str(row.ends_on), row.name, row))
	return min(best)[3] if best else None


@frappe.whitelist()
@require_roles(*DESK)
def desk(property: str) -> dict:
	"""Facilities, who is inside, plans and customers for the desk."""
	facilities = frappe.get_all(
		"Recreation Facility", filters={"property": property},
		fields=["name", "facility_name", "category", "capacity", "access",
		        "price", "status", "opens", "closes", "slot_minutes"],
		order_by="facility_name asc")
	for row in facilities:
		row["inside"] = _inside(row.name)
		row["open_now"] = _open_now(row)
		row["opens"] = str(as_time(row.opens) or "") or None
		row["closes"] = str(as_time(row.closes) or "") or None
	visits = frappe.get_all(
		"Recreation Visit",
		filters={"property": property, "status": "In"},
		fields=["name", "facility", "facility_name", "who", "started_at",
		        "payment_mode", "amount"],
		order_by="started_at asc")
	plans = frappe.get_all(
		"Recreation Plan", filters={"property": property},
		fields=["name", "plan_name", "facility", "period", "price", "visit_limit"],
		order_by="plan_name asc")
	customers = frappe.get_all(
		"Recreation Customer", filters={"property": property},
		fields=["name", "full_name", "phone"],
		order_by="modified desc", limit=50)
	return {"facilities": facilities, "visits": visits, "plans": plans,
	        "customers": customers}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin", scope={"name": "Recreation Facility"})
def save_facility(property: str, facility_name: str, category: str = "Gym",
                  capacity: int = 1, access: str = "Both", price: float = 0,
                  status: str = "Open", opens: str | None = None,
                  closes: str | None = None, name: str | None = None) -> dict:
	payload = {
		"property": property,
		"facility_name": (facility_name or "").strip(),
		"category": category if category in CATEGORIES else "Gym",
		"capacity": max(1, cint(capacity)),
		"access": access if access in ACCESS else "Both",
		"price": max(0, flt(price)),
		"status": status if status in ("Open", "Maintenance") else "Open",
		"opens": opens or None,
		"closes": closes or None,
	}
	if name and frappe.db.exists("Recreation Facility", name):
		doc = frappe.get_doc("Recreation Facility", name)
		if doc.property != property:
			frappe.throw(_("That facility belongs to another property."), frappe.PermissionError)
		doc.update(payload)
		doc.save()
	else:
		doc = frappe.get_doc({"doctype": "Recreation Facility", **payload})
		doc.insert()
	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin", scope={"name": "Recreation Plan", "facility": "Recreation Facility"})
def save_plan(property: str, plan_name: str, period: str = "Month",
              price: float = 0, visit_limit: int = 0,
              facility: str | None = None, name: str | None = None,
              facilities=None) -> dict:
	"""`facilities` (a list) is the access the plan gives: those facilities
	only. Leave it and `facility` blank for every facility."""
	if period not in PERIODS:
		frappe.throw(_("Unknown membership period."))
	if isinstance(facilities, str):
		facilities = frappe.parse_json(facilities or "[]")
	picked = sorted({*(facilities or []), *([facility] if facility else [])})
	for f in picked:
		if frappe.db.get_value("Recreation Facility", f, "property") != property:
			frappe.throw(_("That facility belongs to another property."))
	payload = {
		"property": property,
		"plan_name": (plan_name or "").strip(),
		"period": period,
		"price": max(0, flt(price)),
		"visit_limit": max(0, cint(visit_limit)),
		"facility": None,
		"facilities": [{"facility": f} for f in picked],
	}
	if name and frappe.db.exists("Recreation Plan", name):
		doc = frappe.get_doc("Recreation Plan", name)
		if doc.property != property:
			frappe.throw(_("That plan belongs to another property."), frappe.PermissionError)
		doc.update(payload)
		doc.save()
	else:
		doc = frappe.get_doc({"doctype": "Recreation Plan", **payload})
		doc.insert()
	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
@require_roles(*DESK)
def register_customer(property: str, full_name: str, phone: str | None = None) -> dict:
	"""An external customer. This is not a hotel guest and not a stay."""
	name = (full_name or "").strip()
	if not name:
		frappe.throw(_("The customer's name is required."))
	doc = frappe.get_doc({
		"doctype": "Recreation Customer",
		"property": property,
		"full_name": name,
		"phone": (phone or "").strip() or None,
	}).insert()
	return {"name": doc.name, "full_name": doc.full_name}


def _take(property: str, amount: float, mode: str, reference: str) -> None:
	"""Money the desk takes goes in the cashier's till, like any other
	payment, where the property uses tills. It is an operational receipt
	(receipt()), not a room folio and not a tax invoice."""
	if flt(amount) <= 0:
		return
	from kamra.cashier import record_cashier_txn, tills_required
	if tills_required(property):
		record_cashier_txn(property, "Payment", mode or "Cash", flt(amount),
		                   reference=reference[:140])


@frappe.whitelist(methods=["POST"])
@require_roles(*DESK, scope={"customer": "Recreation Customer", "plan": "Recreation Plan"})
def sell_membership(customer: str, plan: str, starts_on: str | None = None,
                    paid: int = 1, mode: str = "Cash") -> dict:
	return _sell(customer, plan, starts_on, paid, mode)


@frappe.whitelist(methods=["POST"])
@require_roles(*DESK, scope={"membership": "Recreation Membership"})
def renew_membership(membership: str, paid: int = 1, mode: str = "Cash") -> dict:
	"""The same plan again, from the day after this one ends (or today,
	when it has already lapsed)."""
	old = frappe.get_doc("Recreation Membership", membership)
	if old.status == "Cancelled":
		frappe.throw(_("A cancelled membership can't be renewed. Sell a new one."))
	start = max(getdate(add_days(old.ends_on, 1)), getdate(nowdate()))
	return _sell(old.customer, old.plan, str(start), paid, mode, renewed_from=old.name)


def _sell(customer, plan, starts_on, paid, mode, renewed_from=None) -> dict:
	plan_doc = frappe.get_doc("Recreation Plan", plan)
	cust = frappe.get_doc("Recreation Customer", customer)
	if cust.property != plan_doc.property:
		frappe.throw(_("That customer is not at this property."))
	start = getdate(starts_on or nowdate())
	doc = frappe.get_doc({
		"doctype": "Recreation Membership",
		"property": plan_doc.property,
		"customer": customer,
		"customer_name": cust.full_name,
		"plan": plan,
		"plan_name": plan_doc.plan_name,
		"starts_on": start,
		"ends_on": _end(start, plan_doc.period),
		"status": "Active",
		"visits_used": 0,
		"amount": flt(plan_doc.price),
		"paid": 1 if cint(paid) else 0,
		"payment_mode": (mode or "Cash") if cint(paid) else None,
		"renewed_from": renewed_from,
	}).insert()
	if doc.paid:
		_take(doc.property, doc.amount, doc.payment_mode, f"Membership {doc.name}")
	return {"name": doc.name, "starts_on": str(doc.starts_on),
	        "ends_on": str(doc.ends_on), "amount": doc.amount, "receipt": doc.name}


def expire_memberships() -> int:
	"""Daily: memberships past their last day are Expired."""
	names = frappe.get_all("Recreation Membership", pluck="name",
	                       filters={"status": "Active", "ends_on": ["<", nowdate()]})
	for name in names:
		frappe.db.set_value("Recreation Membership", name, "status", "Expired",
		                    update_modified=False)
	return len(names)


@frappe.whitelist(methods=["POST"])
@require_roles(*DESK, scope={"facility": "Recreation Facility", "customer": "Recreation Customer"})
def check_in(facility: str, reservation: str | None = None,
             customer: str | None = None, complimentary: int = 0,
             mode: str = "Cash") -> dict:
	"""One person into a facility. In-house guests are a reservation that
	is checked in. External customers are a recreation customer, usually
	on a membership. Capacity and hours are enforced. A walk-in pays by
	`mode` (Cash by default) into the till."""
	return _enter(facility, reservation, customer, complimentary, mode)


def _enter(facility, reservation=None, customer=None, complimentary=0,
           mode="Cash", booking=None) -> dict:
	fac = frappe.get_doc("Recreation Facility", facility)
	frappe.db.get_value("Recreation Facility", fac.name, "name", for_update=True)
	price = flt(booking.price) if booking else flt(fac.price)
	treatment = booking.treatment if booking else None
	pay_by = mode or "Cash"
	if not _open_now(fac):
		frappe.throw(_("{0} is not open.").format(fac.facility_name))
	if _inside(fac.name) >= int(fac.capacity or 1):
		frappe.throw(_("{0} is at capacity ({1}).").format(fac.facility_name, fac.capacity))
	if bool(reservation) == bool(customer):
		frappe.throw(_("Say who is coming in: a checked-in guest or an external customer."))
	today = nowdate()
	who = ""
	guest = None
	membership = None
	covered = None
	mode = "Complimentary"
	amount = 0.0
	if reservation:
		res = frappe.db.get_value(
			"Reservation", reservation,
			["status", "property", "guest", "guest_name"], as_dict=True)
		if not res or res.property != fac.property or res.status != "Checked In":
			frappe.throw(_("That guest is not checked in at this property."))
		guest = res.guest
		who = res.guest_name or _("Guest")
		covered = None
	else:
		cust = frappe.db.get_value(
			"Recreation Customer", customer, ["property", "full_name"], as_dict=True)
		if not cust or cust.property != fac.property:
			frappe.throw(_("That customer is not at this property."))
		who = cust.full_name
		# a membership opens the facility; a treatment is paid for
		covered = None if treatment else _covering(customer, fac, today)
	if covered:
		membership = covered.name
		mode = "Membership"
	elif reservation and fac.access == "Paid" and cint(complimentary):
		frappe.throw(_("{0} is paid access. Complimentary is not available.").format(fac.facility_name))
	elif (fac.access == "Complimentary" and not treatment) or price == 0 or (
		reservation and cint(complimentary) and fac.access == "Both"
	):
		mode = "Complimentary"
	elif reservation:
		mode = "Folio"
		amount = price
	else:
		mode = "Cash"
		amount = price
	visit = frappe.get_doc({
		"doctype": "Recreation Visit",
		"property": fac.property,
		"facility": fac.name,
		"facility_name": fac.facility_name,
		"reservation": reservation,
		"guest": guest,
		"customer": customer,
		"membership": membership,
		"who": who,
		"status": "In",
		"started_at": now_datetime(),
		"payment_mode": mode,
		"amount": amount,
		"booking": booking.name if booking else None,
	}).insert()
	if mode == "Cash":
		frappe.db.set_value("Recreation Visit", visit.name, "paid_by", pay_by)
		_take(fac.property, amount, pay_by, f"Recreation {visit.name}")
	if booking:
		frappe.db.set_value("Recreation Booking", booking.name,
		                    {"status": "Arrived", "visit": visit.name})
	if mode == "Folio":
		from kamra.api import _post_folio_charge
		from kamra.folio import open_folio
		res_doc = frappe.get_doc("Reservation", reservation)
		folio = open_folio(res_doc)
		label = (frappe.db.get_value("Recreation Treatment", treatment, "treatment_name")
		         if treatment else f"{fac.facility_name} access")
		_post_folio_charge(
			folio, _charge_type(fac.category), label, amount, reservation=res_doc.name)
	if membership:
		used = cint(frappe.db.get_value("Recreation Membership", membership, "visits_used"))
		frappe.db.set_value("Recreation Membership", membership, "visits_used", used + 1,
		                    update_modified=False)
	return {"name": visit.name, "payment_mode": mode, "amount": amount, "who": who,
	        "receipt": visit.name if mode == "Cash" else None}


@frappe.whitelist(methods=["POST"])
@require_roles(*DESK, scope={"visit": "Recreation Visit"})
def check_out(visit: str) -> dict:
	doc = frappe.get_doc("Recreation Visit", visit)
	if doc.status != "In":
		frappe.throw(_("That visit is already closed."))
	doc.status = "Out"
	doc.ended_at = now_datetime()
	doc.save()
	return {"name": doc.name, "status": doc.status}


@frappe.whitelist()
@require_roles(*DESK, "Finance")
def revenue(property: str, date: str | None = None) -> dict:
	"""What the desk took on one day: folio, cash and membership fees.
	Cash and membership fees are operational totals. Folio amounts are
	also on the guest bill."""
	day = str(getdate(date or nowdate()))
	start = get_datetime(f"{day} 00:00:00")
	end = get_datetime(f"{day} 23:59:59")
	visits = frappe.get_all(
		"Recreation Visit",
		filters={"property": property, "started_at": ["between", [start, end]]},
		fields=["payment_mode", "amount"])
	memberships = frappe.get_all(
		"Recreation Membership",
		filters={"property": property, "starts_on": day, "paid": 1},
		fields=["amount"])
	out = {"folio": 0.0, "cash": 0.0, "membership": 0.0, "visits": len(visits)}
	for row in visits:
		if row.payment_mode == "Folio":
			out["folio"] += float(row.amount or 0)
		elif row.payment_mode == "Cash":
			out["cash"] += float(row.amount or 0)
	out["membership"] = sum(float(m.amount or 0) for m in memberships)
	out["total"] = round(out["folio"] + out["cash"] + out["membership"], 2)
	return out


# ── Spa treatments and pool / court sessions ─────────────────────────────────
# One booking record for both: a facility for a time range, with a
# treatment and a therapist for the spa. A room or a pool never takes more
# overlapping bookings than its capacity (a treatment room is capacity 1),
# and a therapist never has two at once. On arrival the booking becomes a
# visit and is paid like any visit (folio, till, or complimentary).

def _dt(value) -> datetime:
	return get_datetime(value)


_OVERLAP = {
	"facility": """SELECT name FROM `tabRecreation Booking`
		WHERE facility = %(value)s AND status IN ('Booked', 'Arrived')
		  AND starts_at < %(ends)s AND ends_at > %(starts)s""",
	"therapist": """SELECT name FROM `tabRecreation Booking`
		WHERE therapist = %(value)s AND status IN ('Booked', 'Arrived')
		  AND starts_at < %(ends)s AND ends_at > %(starts)s""",
}


def _overlapping(field: str, value: str, starts, ends, lock: bool = True) -> int:
	"""Bookings of this facility (or therapist) that overlap the range,
	read with a lock when booking so two desks can't both take the last
	place."""
	sql = _OVERLAP[field] + (" FOR UPDATE" if lock else "")
	return len(frappe.db.sql(sql, {"value": value, "starts": starts, "ends": ends}))


def slots(facility: str, day: str | None = None) -> list[dict]:
	"""The sessions of a facility with session minutes, opening to closing
	on one day, with how many places each still has."""
	fac = frappe.get_doc("Recreation Facility", facility)
	step = cint(fac.get("slot_minutes"))
	if step <= 0:
		return []
	day = getdate(day or nowdate())
	opens = as_time(fac.opens) or time(0, 0)
	closes = as_time(fac.closes) or time(23, 59, 59)
	start = datetime.combine(day, opens)
	end = datetime.combine(day if closes > opens else add_days(day, 1), closes)
	out = []
	while start + timedelta(minutes=step) <= end:
		stop = start + timedelta(minutes=step)
		taken = _overlapping("facility", fac.name, start, stop, lock=False)
		out.append({"starts_at": str(start), "ends_at": str(stop),
		            "free": max(int(fac.capacity or 1) - taken, 0)})
		start = stop
	return out


@frappe.whitelist()
@require_roles(*DESK, scope={"facility": "Recreation Facility"})
def facility_slots(facility: str, day: str | None = None) -> list[dict]:
	return slots(facility, day)


@frappe.whitelist(methods=["POST"])
@require_roles(*DESK, scope={"facility": "Recreation Facility",
                             "customer": "Recreation Customer"})
def book(facility: str, starts_at: str, reservation: str | None = None,
         customer: str | None = None, treatment: str | None = None,
         therapist: str | None = None, ends_at: str | None = None) -> dict:
	"""Book a treatment (with a therapist, in a treatment room) or a pool /
	court session. The end comes from the treatment's minutes or the
	facility's session minutes unless given."""
	fac = frappe.get_doc("Recreation Facility", facility)
	# one booking at a time per room and per therapist: the overlap counts
	# below run under these locks
	frappe.db.get_value("Recreation Facility", fac.name, "name", for_update=True)
	if bool(reservation) == bool(customer):
		frappe.throw(_("Say who the booking is for: a checked-in guest or an external customer."))
	if fac.status != "Open":
		frappe.throw(_("{0} is not open.").format(fac.facility_name))
	tr = None
	if treatment:
		tr = frappe.db.get_value("Recreation Treatment", treatment,
		                         ["property", "duration", "price", "treatment_name", "disabled"],
		                         as_dict=True)
		if not tr or tr.property != fac.property or tr.disabled:
			frappe.throw(_("That treatment is not offered here."))
	if therapist:
		th = frappe.db.get_value("Recreation Therapist", therapist,
		                         ["property", "disabled"], as_dict=True, for_update=True)
		if not th or th.property != fac.property or th.disabled:
			frappe.throw(_("That therapist is not at this property."))
	starts = _dt(starts_at)
	minutes = cint(tr.duration) if tr else cint(fac.get("slot_minutes"))
	ends = _dt(ends_at) if ends_at else (starts + timedelta(minutes=minutes) if minutes else None)
	if not ends or ends <= starts:
		frappe.throw(_("Give the booking an end time."))
	if not (within_hours(starts.time(), as_time(fac.opens), as_time(fac.closes))
	        and within_hours(ends.time(), as_time(fac.opens), as_time(fac.closes))):
		frappe.throw(_("{0} is closed at that time.").format(fac.facility_name))
	if _overlapping("facility", fac.name, starts, ends) >= int(fac.capacity or 1):
		frappe.throw(_("{0} is fully booked then.").format(fac.facility_name))
	if therapist and _overlapping("therapist", therapist, starts, ends):
		frappe.throw(_("That therapist already has a booking then."))
	if reservation:
		res = frappe.db.get_value("Reservation", reservation,
		                          ["property", "status", "guest_name"], as_dict=True)
		if not res or res.property != fac.property or res.status not in (
				"Confirmed", "Checked In"):
			frappe.throw(_("That stay is not booked at this property."))
		who = res.guest_name
	else:
		cust = frappe.db.get_value("Recreation Customer", customer,
		                           ["property", "full_name"], as_dict=True)
		if not cust or cust.property != fac.property:
			frappe.throw(_("That customer is not at this property."))
		who = cust.full_name
	doc = frappe.get_doc({
		"doctype": "Recreation Booking", "property": fac.property,
		"facility": fac.name, "facility_name": fac.facility_name,
		"treatment": treatment or None, "therapist": therapist or None,
		"starts_at": starts, "ends_at": ends, "reservation": reservation,
		"customer": customer, "who": who, "status": "Booked",
		"price": flt(tr.price) if tr else flt(fac.price),
	}).insert()
	return {"name": doc.name, "starts_at": str(doc.starts_at),
	        "ends_at": str(doc.ends_at), "price": doc.price}


@frappe.whitelist(methods=["POST"])
@require_roles(*DESK, scope={"booking": "Recreation Booking"})
def arrive(booking: str, complimentary: int = 0, mode: str = "Cash") -> dict:
	"""The booked guest or customer is here: it becomes a visit, paid like
	one (the treatment's price, else the facility's)."""
	doc = frappe.get_doc("Recreation Booking", booking, for_update=True)
	if doc.status != "Booked":
		frappe.throw(_("That booking is already {0}.").format(_(doc.status).lower()))
	return _enter(doc.facility, doc.reservation, doc.customer, complimentary, mode,
	              booking=doc)


@frappe.whitelist(methods=["POST"])
@require_roles(*DESK, scope={"booking": "Recreation Booking"})
def cancel_booking(booking: str, no_show: int = 0) -> dict:
	doc = frappe.get_doc("Recreation Booking", booking)
	if doc.status != "Booked":
		frappe.throw(_("That booking is already {0}.").format(_(doc.status).lower()))
	doc.status = "No Show" if cint(no_show) else "Cancelled"
	doc.save()
	return {"name": doc.name, "status": doc.status}


@frappe.whitelist()
@require_roles(*DESK)
def bookings(property: str, day: str | None = None) -> list[dict]:
	day = str(getdate(day or nowdate()))
	return frappe.get_all(
		"Recreation Booking",
		filters={"property": property,
		         "starts_at": ["between", [f"{day} 00:00:00", f"{day} 23:59:59"]]},
		fields=["name", "facility", "facility_name", "treatment", "therapist",
		        "starts_at", "ends_at", "who", "status", "price", "visit"],
		order_by="starts_at asc")


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin")
def save_treatment(property: str, treatment_name: str, duration: int = 60,
                   price: float = 0, facility: str | None = None,
                   name: str | None = None, disabled: int = 0) -> dict:
	return _save("Recreation Treatment", name, property, {
		"treatment_name": (treatment_name or "").strip(),
		"duration": max(5, cint(duration)), "price": max(0, flt(price)),
		"facility": facility or None, "disabled": cint(disabled)})


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin")
def save_therapist(property: str, therapist_name: str, name: str | None = None,
                   disabled: int = 0) -> dict:
	return _save("Recreation Therapist", name, property, {
		"therapist_name": (therapist_name or "").strip(), "disabled": cint(disabled)})


def _save(doctype: str, name, property: str, payload: dict) -> dict:
	from kamra.authz import assert_property_access
	assert_property_access(property)
	if payload.get("facility") and frappe.db.get_value(
			"Recreation Facility", payload["facility"], "property") != property:
		frappe.throw(_("That facility belongs to another property."))
	if name and frappe.db.exists(doctype, name):
		doc = frappe.get_doc(doctype, name)
		if doc.property != property:
			frappe.throw(_("That belongs to another property."), frappe.PermissionError)
		doc.update(payload)
		doc.save()
	else:
		doc = frappe.get_doc({"doctype": doctype, "property": property, **payload}).insert()
	return {"name": doc.name}


@frappe.whitelist()
@require_roles(*DESK)
def spa_setup(property: str) -> dict:
	return {
		"treatments": frappe.get_all(
			"Recreation Treatment", filters={"property": property, "disabled": 0},
			fields=["name", "treatment_name", "duration", "price", "facility"],
			order_by="treatment_name asc"),
		"therapists": frappe.get_all(
			"Recreation Therapist", filters={"property": property, "disabled": 0},
			fields=["name", "therapist_name"], order_by="therapist_name asc"),
	}


# ── QR passes ────────────────────────────────────────────────────────────────
# A pass is "KRP-C-<customer>-<sig>" or "KRP-R-<reservation>-<sig>", signed
# with the site's secret so it can't be made up from a name. The desk scans
# it (a scanner types into the box) instead of picking the person.

def _sig(kind: str, name: str) -> str:
	from frappe.utils.password import get_encryption_key
	key = get_encryption_key().encode()
	return hmac.new(key, f"{kind}:{name}".encode(), hashlib.sha256).hexdigest()[:16]


def pass_code(kind: str, name: str) -> str:
	return f"KRP-{kind}-{name}-{_sig(kind, name)}"


def read_pass(code: str) -> tuple[str, str]:
	"""('R', reservation) or ('C', customer); refuses anything not signed here."""
	code = (code or "").strip()
	try:
		head, kind, rest = code.split("-", 2)
		name, sig = rest.rsplit("-", 1)
	except ValueError:
		frappe.throw(_("That is not a recreation pass."))
	if head != "KRP" or kind not in ("R", "C") or not hmac.compare_digest(sig, _sig(kind, name)):
		frappe.throw(_("That is not a recreation pass."))
	return kind, name


@frappe.whitelist()
@require_roles(*DESK, scope={"customer": "Recreation Customer", "reservation": "Reservation"})
def entry_pass(customer: str | None = None, reservation: str | None = None) -> dict:
	"""A member's or an in-house guest's pass: the code and its QR (data URI)."""
	if bool(customer) == bool(reservation):
		frappe.throw(_("Pick a customer or a stay."))
	code = pass_code("C", customer) if customer else pass_code("R", reservation)
	from kamra.zatca import qr_svg_data_uri
	return {"code": code, "qr": qr_svg_data_uri(code)}


@frappe.whitelist(methods=["POST"])
@require_roles(*DESK, scope={"facility": "Recreation Facility"})
def check_in_by_pass(facility: str, code: str, complimentary: int = 0) -> dict:
	kind, name = read_pass(code)
	if kind == "R":
		return _enter(facility, reservation=name, complimentary=complimentary)
	return _enter(facility, customer=name, complimentary=complimentary)


# ── Receipts, reports and the membership ledger ──────────────────────────────

@frappe.whitelist()
@require_roles(*DESK, "Finance")
def receipt(name: str) -> dict:
	"""A walk-in's or a membership's receipt: the record's number is the
	receipt number. An operational receipt, not a tax invoice."""
	from kamra.authz import assert_property_access
	doctype = "Recreation Membership" if frappe.db.exists("Recreation Membership", name) \
		else "Recreation Visit"
	doc = frappe.get_doc(doctype, name)
	assert_property_access(doc.property)
	if doctype == "Recreation Visit":
		if doc.payment_mode != "Cash":
			frappe.throw(_("Only a walk-in payment has a receipt here; folio charges are on the guest bill."))
		item = doc.facility_name
		if doc.booking:
			tr = frappe.db.get_value("Recreation Booking", doc.booking, "treatment")
			item = frappe.db.get_value("Recreation Treatment", tr, "treatment_name") if tr else item
		row = {"who": doc.who, "item": item, "date": str(doc.started_at)[:16],
		       "amount": flt(doc.amount), "paid_by": doc.get("paid_by") or "Cash"}
	else:
		if not doc.paid:
			frappe.throw(_("This membership is not paid yet."))
		row = {"who": doc.customer_name,
		       "item": f"{doc.plan_name} ({doc.starts_on} - {doc.ends_on})",
		       "date": str(doc.creation)[:16], "amount": flt(doc.amount),
		       "paid_by": doc.get("payment_mode") or "Cash"}
	prop = frappe.db.get_value("Property", doc.property,
	                           ["property_name", "address_line", "city"], as_dict=True) or {}
	# receipt UI wants `address`; Property stores it as address_line
	return {"number": doc.name,
	        "property": {
	        	"property_name": prop.get("property_name"),
	        	"address": prop.get("address_line"),
	        	"city": prop.get("city"),
	        },
	        **row, "note": _("Receipt. Not a tax invoice.")}


@frappe.whitelist()
@require_roles(*DESK, "Finance")
def report(property: str, from_date: str | None = None, to_date: str | None = None) -> dict:
	"""Attendance, memberships, revenue by facility and by customer type,
	and hotel-guest against outside use, for a date range (default: this
	month so far)."""
	from kamra.authz import assert_property_access
	assert_property_access(property)
	end = getdate(to_date or nowdate())
	start = getdate(from_date or end.replace(day=1))
	if (end - start).days > 366:
		frappe.throw(_("Pick a year or less."))
	visits = frappe.get_all(
		"Recreation Visit",
		filters={"property": property,
		         "started_at": ["between", [f"{start} 00:00:00", f"{end} 23:59:59"]]},
		fields=["facility", "facility_name", "reservation", "customer",
		        "payment_mode", "amount", "started_at"])
	sold = frappe.get_all(
		"Recreation Membership",
		filters={"property": property, "paid": 1, "starts_on": ["between", [start, end]]},
		fields=["plan", "amount"])
	by_facility: dict[str, dict] = {}
	by_day: dict[str, int] = {}
	use = {"guest": 0, "external": 0}
	revenue = {"guest": 0.0, "external": 0.0, "membership": 0.0}
	for v in visits:
		f = by_facility.setdefault(v.facility_name, {"visits": 0, "revenue": 0.0})
		f["visits"] += 1
		f["revenue"] += flt(v.amount)
		day = str(v.started_at)[:10]
		by_day[day] = by_day.get(day, 0) + 1
		kind = "guest" if v.reservation else "external"
		use[kind] += 1
		revenue[kind] += flt(v.amount)
	names = {f.name: f.facility_name for f in frappe.get_all(
		"Recreation Facility", filters={"property": property}, fields=["name", "facility_name"])}
	for m in sold:
		revenue["membership"] += flt(m.amount)
		opens = plan_facilities(m.plan)
		label = names.get(opens[0]) if len(opens) == 1 else _("Memberships (several facilities)")
		f = by_facility.setdefault(label, {"visits": 0, "revenue": 0.0})
		f["revenue"] += flt(m.amount)
	today = nowdate()
	active = frappe.db.count("Recreation Membership", {
		"property": property, "status": "Active", "ends_on": [">=", today]})
	expired = frappe.db.count("Recreation Membership", {
		"property": property, "status": ["in", ["Active", "Expired"]], "ends_on": ["<", today]})
	expiring = frappe.get_all(
		"Recreation Membership",
		filters={"property": property, "status": "Active",
		         "ends_on": ["between", [today, add_days(today, 7)]]},
		fields=["name", "customer", "customer_name", "plan_name", "ends_on"],
		order_by="ends_on asc")
	for f in by_facility.values():
		f["revenue"] = round(f["revenue"], 2)
	return {
		"from_date": str(start), "to_date": str(end),
		"attendance": {"total": len(visits), "by_day": dict(sorted(by_day.items()))},
		"by_facility": by_facility,
		"use": use,
		"revenue": {**{k: round(v, 2) for k, v in revenue.items()},
		            "external_total": round(revenue["external"] + revenue["membership"], 2)},
		"memberships": {"active": active, "expired": expired, "expiring_soon": expiring},
	}


@frappe.whitelist()
@require_roles(*DESK, "Finance", scope={"customer": "Recreation Customer"})
def membership_ledger(customer: str) -> dict:
	"""Everything one customer bought and used, oldest first: each
	membership (and renewal) with its fee, each visit against it with the
	visits left, and what they paid at the desk."""
	cust = frappe.get_doc("Recreation Customer", customer)
	rows = []
	limits = {}
	for m in frappe.get_all(
			"Recreation Membership", filters={"customer": customer},
			fields=["name", "plan", "plan_name", "starts_on", "ends_on", "status",
			        "amount", "paid", "payment_mode", "renewed_from", "creation"]):
		limits[m.name] = cint(frappe.db.get_value("Recreation Plan", m.plan, "visit_limit"))
		rows.append({"at": str(m.starts_on), "kind": "Renewal" if m.renewed_from else "Membership",
		             "ref": m.name, "detail": f"{m.plan_name} {m.starts_on} - {m.ends_on}",
		             "status": m.status, "charged": flt(m.amount),
		             "paid": flt(m.amount) if m.paid else 0.0})
	used: dict[str, int] = {}
	for v in frappe.get_all(
			"Recreation Visit", filters={"customer": customer},
			fields=["name", "facility_name", "membership", "payment_mode", "amount",
			        "started_at"], order_by="started_at asc"):
		row = {"at": str(v.started_at), "kind": "Visit", "ref": v.name,
		       "detail": v.facility_name, "charged": flt(v.amount),
		       "paid": flt(v.amount) if v.payment_mode == "Cash" else 0.0}
		if v.membership:
			used[v.membership] = used.get(v.membership, 0) + 1
			row["membership"] = v.membership
			if limits.get(v.membership):
				row["visits_left"] = max(limits[v.membership] - used[v.membership], 0)
		rows.append(row)
	rows.sort(key=lambda r: r["at"])
	charged = round(sum(r["charged"] for r in rows), 2)
	paid = round(sum(r["paid"] for r in rows), 2)
	return {"customer": cust.name, "full_name": cust.full_name, "entries": rows,
	        "charged": charged, "paid": paid, "owed": round(charged - paid, 2)}
