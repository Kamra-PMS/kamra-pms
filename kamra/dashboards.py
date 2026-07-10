"""Operational dashboards - one property, and the whole portfolio.

Property dashboard: the day at a glance for a single hotel, arranged by
department (front desk / housekeeping / finance) on top of the numbers the
manager flash already computes. Portfolio dashboard: the same headline
metrics rolled up across every property the signed-in user can access, with
a per-property table - the chain's central view.
"""

import frappe
from frappe.utils import nowdate

from kamra.authz import require_roles


def _housekeeping_slice(property: str):
	"""Room-status breakdown + task load for the housekeeping department."""
	rooms = frappe.get_all(
		"Room", filters={"property": property},
		fields=["housekeeping_status", "occupancy_status"])
	status = {"Clean": 0, "Dirty": 0, "Inspected": 0, "Out of Order": 0}
	occupied = 0
	for r in rooms:
		status[r.housekeeping_status] = status.get(r.housekeeping_status, 0) + 1
		if r.occupancy_status == "Occupied":
			occupied += 1
	from frappe.utils import now_datetime
	open_tasks = frappe.get_all(
		"Housekeeping Task",
		filters={"property": property, "status": ("in", ["Pending", "In Progress"])},
		fields=["due_by"])
	now = now_datetime()
	overdue = sum(
		1 for t in open_tasks
		if t.due_by and frappe.utils.get_datetime(t.due_by) < now)
	return {
		"room_status": status,
		"occupied": occupied,
		"vacant": len(rooms) - occupied,
		"open_tasks": len(open_tasks),
		"overdue_tasks": overdue,
	}


def _finance_slice(property: str, date: str):
	"""Collections today (by mode), and money still owed on open folios."""
	from kamra.api import cash_summary
	collections = cash_summary(property, date)
	outstanding = frappe.db.sql(
		"""SELECT COALESCE(SUM(balance), 0) FROM `tabFolio`
		   WHERE property = %(p)s AND status = 'Open'""",
		{"p": property})[0][0]
	open_folios = frappe.db.count(
		"Folio", {"property": property, "status": "Open"})
	return {
		"collections_today": collections.get("grand_total", 0),
		"collections_by_mode": collections.get("modes", []),
		"outstanding": float(outstanding or 0),
		"open_folios": open_folios,
	}


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Revenue Manager", "Hotel Admin", "Kamra Agent")
def property_dashboard(property: str, date: str | None = None):
	"""Everything one hotel's dashboard needs, by department."""
	date = date or nowdate()
	from kamra.reports import manager_flash
	flash = manager_flash(property, date)
	today = flash.get("today") or {}
	mtd = flash.get("mtd") or {}
	move = flash.get("movement") or {}
	finance = _finance_slice(property, date)
	hk = _housekeeping_slice(property)

	return {
		"property": property,
		"property_name": frappe.db.get_value("Property", property, "property_name"),
		"date": date,
		"total_rooms": flash.get("total_rooms", 0),
		# headline metrics
		"occupancy_pct": today.get("occupancy_pct", 0),
		"arrivals": move.get("arrivals", 0),
		"departures": move.get("departures", 0),
		"in_house": move.get("in_house", 0),
		"no_shows": move.get("no_shows", 0),
		"revenue_today": round(
			today.get("room_revenue", 0) + today.get("fnb_revenue", 0)
			+ today.get("other_revenue", 0), 0),
		"collections_today": finance["collections_today"],
		# statistics (month to date)
		"statistics": {
			"mtd_occupancy_pct": mtd.get("occupancy_pct", 0),
			"mtd_revenue": round(mtd.get("room_revenue", 0)
			                     + mtd.get("fnb_revenue", 0)
			                     + mtd.get("other_revenue", 0), 0),
			"adr": mtd.get("adr", 0),
			"revpar": mtd.get("revpar", 0),
			"rooms_sold_mtd": mtd.get("rooms_sold", 0),
		},
		# department dashboards
		"front_desk": {
			"arrivals": move.get("arrivals", 0),
			"departures": move.get("departures", 0),
			"in_house": move.get("in_house", 0),
			"no_shows": move.get("no_shows", 0),
		},
		"housekeeping": hk,
		"finance": finance,
		"outlook": flash.get("outlook", []),
	}


def _property_summary(property: str, date: str):
	"""Compact headline numbers for one property in the portfolio table."""
	total_rooms = frappe.db.count("Room", {"property": property}) or 0
	from kamra.reports import _day_stats
	s = _day_stats(property, date, total_rooms)
	finance = _finance_slice(property, date)
	return {
		"property": property,
		"property_name": frappe.db.get_value("Property", property, "property_name"),
		"total_rooms": total_rooms,
		"occupancy_pct": s.get("occupancy_pct", 0),
		"rooms_sold": s.get("rooms_sold", 0),
		"arrivals": frappe.db.count("Reservation", {
			"property": property, "check_in_date": date,
			"status": ("in", ["Confirmed", "Checked In"])}),
		"departures": frappe.db.count("Reservation", {
			"property": property, "check_out_date": date,
			"status": ("in", ["Checked In", "Checked Out"])}),
		"in_house": frappe.db.count("Reservation", {
			"property": property, "status": "Checked In"}),
		"revenue_today": round(s.get("room_revenue", 0) + s.get("fnb_revenue", 0)
		                       + s.get("other_revenue", 0), 0),
		"collections_today": finance["collections_today"],
		"outstanding": finance["outstanding"],
	}


@frappe.whitelist()
@require_roles("Finance", "Revenue Manager", "Hotel Admin", "Kamra Agent")
def portfolio_dashboard(date: str | None = None):
	"""The chain's central view: headline metrics rolled up across every
	property the signed-in user may access, plus a per-property table."""
	date = date or nowdate()
	from kamra.api import my_properties
	props = [p["name"] for p in my_properties()]
	rows = [_property_summary(p, date) for p in props]

	rooms = sum(r["total_rooms"] for r in rows)
	sold = sum(r["rooms_sold"] for r in rows)
	totals = {
		"properties": len(rows),
		"total_rooms": rooms,
		"occupancy_pct": round(100 * sold / rooms, 1) if rooms else 0,
		"arrivals": sum(r["arrivals"] for r in rows),
		"departures": sum(r["departures"] for r in rows),
		"in_house": sum(r["in_house"] for r in rows),
		"revenue_today": round(sum(r["revenue_today"] for r in rows), 0),
		"collections_today": round(sum(r["collections_today"] for r in rows), 0),
		"outstanding": round(sum(r["outstanding"] for r in rows), 0),
	}
	rows.sort(key=lambda r: r["revenue_today"], reverse=True)
	return {"date": date, "totals": totals, "properties": rows}
