"""Recreation desk (#632), day one: a gym (or pool, spa, …) for in-house
guests and for members.

In-house access posts to the guest folio when it is paid, or is recorded
as complimentary. A membership covers an external customer for a day,
week, month or year, with an optional visit limit. Walk-in cash is
recorded on the visit. It is an operational receipt, not a tax invoice
and not a room folio — registering a recreation customer does not create
a stay.

Spa appointment scheduling, QR entry and a full membership ledger are
later phases.
"""

from __future__ import annotations

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
	start = getdate(start)
	if period == "Day":
		return start
	if period == "Week":
		return add_days(start, 6)
	if period == "Month":
		return add_days(add_months(start, 1), -1)
	if period == "Year":
		return add_days(add_months(start, 12), -1)
	frappe.throw(_("Unknown membership period."))


def _open_now(doc) -> bool:
	if doc.status != "Open":
		return False
	opens, closes = doc.opens, doc.closes
	if not opens or not closes:
		return True
	now = nowtime()
	opens, closes = str(opens)[:8], str(closes)[:8]
	if opens <= closes:
		return opens <= now <= closes
	return now >= opens or now <= closes


def _inside(facility: str) -> int:
	return frappe.db.count("Recreation Visit", {"facility": facility, "status": "In"})


def _charge_type(category: str) -> str:
	return "Spa" if category in SPA_CHARGE else "Misc"


def _covering(customer: str, facility, today: str):
	rows = frappe.get_all(
		"Recreation Membership",
		filters={
			"customer": customer,
			"status": "Active",
			"starts_on": ["<=", today],
			"ends_on": [">=", today],
		},
		fields=["name", "plan", "visits_used"])
	for row in rows:
		plan = frappe.db.get_value(
			"Recreation Plan", row.plan,
			["facility", "visit_limit", "property"], as_dict=True)
		if not plan or plan.property != facility.property:
			continue
		if plan.facility and plan.facility != facility.name:
			continue
		limit = int(plan.visit_limit or 0)
		if limit and int(row.visits_used or 0) >= limit:
			continue
		return row
	return None


@frappe.whitelist()
@require_roles(*DESK)
def desk(property: str) -> dict:
	"""Facilities, who is inside, plans and customers for the desk."""
	facilities = frappe.get_all(
		"Recreation Facility", filters={"property": property},
		fields=["name", "facility_name", "category", "capacity", "access",
		        "price", "status", "opens", "closes"],
		order_by="facility_name asc")
	for row in facilities:
		row["inside"] = _inside(row.name)
		row["open_now"] = row.status == "Open"
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
              facility: str | None = None, name: str | None = None) -> dict:
	if period not in PERIODS:
		frappe.throw(_("Unknown membership period."))
	if facility and frappe.db.get_value("Recreation Facility", facility, "property") != property:
		frappe.throw(_("That facility belongs to another property."))
	payload = {
		"property": property,
		"plan_name": (plan_name or "").strip(),
		"period": period,
		"price": max(0, flt(price)),
		"visit_limit": max(0, cint(visit_limit)),
		"facility": facility or None,
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


@frappe.whitelist(methods=["POST"])
@require_roles(*DESK, scope={"customer": "Recreation Customer", "plan": "Recreation Plan"})
def sell_membership(customer: str, plan: str, starts_on: str | None = None,
                    paid: int = 1) -> dict:
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
	}).insert()
	return {"name": doc.name, "ends_on": str(doc.ends_on), "amount": doc.amount}


@frappe.whitelist(methods=["POST"])
@require_roles(*DESK, scope={"facility": "Recreation Facility", "customer": "Recreation Customer"})
def check_in(facility: str, reservation: str | None = None,
             customer: str | None = None, complimentary: int = 0) -> dict:
	"""One person into a facility. In-house guests are a reservation that
	is checked in. External customers are a recreation customer, usually
	on a membership. Capacity and hours are enforced."""
	fac = frappe.get_doc("Recreation Facility", facility)
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
		covered = _covering(customer, fac, today)
	if covered:
		membership = covered.name
		mode = "Membership"
	elif reservation and fac.access == "Paid" and cint(complimentary):
		frappe.throw(_("{0} is paid access. Complimentary is not available.").format(fac.facility_name))
	elif fac.access == "Complimentary" or flt(fac.price) == 0 or (
		reservation and cint(complimentary) and fac.access == "Both"
	):
		mode = "Complimentary"
	elif reservation:
		mode = "Folio"
		amount = flt(fac.price)
	else:
		mode = "Cash"
		amount = flt(fac.price)
		if amount <= 0:
			mode = "Complimentary"
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
	}).insert()
	if mode == "Folio":
		from kamra.api import _post_folio_charge
		from kamra.folio import open_folio
		res_doc = frappe.get_doc("Reservation", reservation)
		folio = open_folio(res_doc)
		_post_folio_charge(
			folio, _charge_type(fac.category),
			f"{fac.facility_name} access", amount, reservation=res_doc.name)
	if membership:
		used = cint(frappe.db.get_value("Recreation Membership", membership, "visits_used"))
		frappe.db.set_value("Recreation Membership", membership, "visits_used", used + 1,
		                    update_modified=False)
	return {"name": visit.name, "payment_mode": mode, "amount": amount, "who": who}


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
