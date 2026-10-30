"""Operational dashboards - one property, and the whole portfolio.

Property dashboard: the day at a glance for a single hotel, arranged by
department (front desk / housekeeping / finance) on top of the numbers the
manager flash already computes. Portfolio dashboard: the same headline
metrics rolled up across every property the signed-in user can access, with
a per-property table - the chain's central view.
"""

from decimal import ROUND_HALF_UP, Decimal

import frappe
from frappe.utils import add_days, add_years, getdate, nowdate

from kamra.authz import ADMIN, require_roles


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


# who sees the money on the dashboard; the front desk sees arrivals,
# departures, in house, rooms and occupancy (now and on the books), never
# revenue, ADR, RevPAR, collections or outstanding
FIGURE_ROLES = ("Finance", "Revenue Manager", "Night Auditor", "Kamra Agent", *ADMIN)
FIGURE_KEYS = ("occupancy_pct", "revenue_today", "revpar", "adr", "room_revenue_today",
               "collections_today", "statistics", "finance", "outlook", "comparison")
FORECAST_DAYS = 90


def _sellable(property: str) -> int:
	# out of order rooms are not for sale, as channel_manager._sellable counts
	return frappe.db.count("Room", {
		"property": property, "housekeeping_status": ("!=", "Out of Order")})


def occupancy_now(property: str, hk: dict) -> dict:
	"""Rooms occupied right now over sellable rooms."""
	sellable = _sellable(property)
	occupied = hk["occupied"]
	return {"occupied": occupied, "sellable": sellable,
	        "occupancy_pct": round(100 * occupied / sellable, 1) if sellable else 0}


def occupancy_forecast(property: str, date: str, days: int = FORECAST_DAYS) -> list[dict]:
	"""On the books for each night from date: live reservations covering the
	night (every live status, as group_blocks counts a pick up) over sellable rooms,
	plus group block rooms held but not yet picked up. Rooms only, no money."""
	sellable = _sellable(property)
	start = getdate(date)
	end = getdate(add_days(start, days))
	from kamra.reservation_state import LIVE_STATUSES
	stays = frappe.db.sql(
		"""SELECT check_in_date AS ci,
		          GREATEST(check_out_date, DATE_ADD(check_in_date, INTERVAL 1 DAY)) AS co
		   FROM `tabReservation`
		   WHERE property = %(p)s AND status IN %(live)s
		     AND check_in_date < %(e)s
		     AND GREATEST(check_out_date, DATE_ADD(check_in_date, INTERVAL 1 DAY)) > %(s)s""",
		{"p": property, "s": str(start), "e": str(end), "live": tuple(LIVE_STATUSES)},
		as_dict=True)
	held_by_night = _held_by_night(property, start, end)
	pct = lambda n: round(100 * n / sellable, 1) if sellable else 0  # noqa: E731
	out = []
	for i in range(days):
		d = getdate(add_days(start, i))
		# ponytail: days x stays scan; group by date in SQL if a house books thousands ahead
		booked = sum(1 for r in stays if getdate(r.ci) <= d < getdate(r.co))
		held = min(held_by_night.get(str(d), 0), max(0, sellable - booked))
		out.append({"date": str(d), "booked": booked, "held": held,
		            "available": max(0, sellable - booked - held),
		            "occupancy_pct": pct(booked), "occupancy_with_holds_pct": pct(booked + held)})
	return out


def _held_by_night(property: str, start, end) -> dict[str, int]:
	"""Group block rooms not yet picked up, per night, every room type: the
	same holds group_blocks keeps off sale (released and past-cutoff blocks
	no longer count)."""
	from kamra.group_blocks import _holding_groups, _unpicked
	out: dict[str, int] = {}
	for gb in _holding_groups(property, start, end):
		types = set(frappe.get_all("Group Room Block", filters={"parent": gb.name},
		                           pluck="room_type"))
		held = sum(_unpicked(gb.name, rt) for rt in types)
		if not held:
			continue
		d, co = max(getdate(gb.check_in_date), start), min(getdate(gb.check_out_date), end)
		while d < co:
			out[str(d)] = out.get(str(d), 0) + held
			d = getdate(add_days(d, 1))
	return out


COMPARE_METRICS = ("occupancy_pct", "rooms_sold", "room_revenue", "total_revenue", "adr", "revpar")


def _change(this, last):
	return round(100 * (this - last) / last, 1) if last else None


def comparison(property: str, date: str, total_rooms: int, forecast: list[dict]) -> dict:
	"""Today, month to date, year to date and the next 90 days on the books,
	each against the same dates one year back. Year to date starts at the
	country pack's financial year (April in India). The 90 days are the
	forecast's nights from tonight, over sellable rooms like the forecast."""
	from kamra.localization import financial_year_start, pack_for
	from kamra.reports import range_stats
	d = getdate(date)
	ly = lambda x: getdate(add_years(x, -1))  # noqa: E731 - 29 Feb -> 28 Feb
	fy = financial_year_start(pack_for(property), d)
	periods = []
	for pid, start, end in (("today", d, d), ("mtd", d.replace(day=1), d), ("ytd", fy, d)):
		this = range_stats(property, start, end, total_rooms)
		last = range_stats(property, ly(start), ly(end), total_rooms)
		periods.append({"id": pid, "from_date": str(start), "to_date": str(end),
		                "ly_from_date": str(ly(start)), "ly_to_date": str(ly(end)),
		                "this_year": this, "last_year": last,
		                "change_pct": {k: _change(this[k], last[k]) for k in COMPARE_METRICS}})
	# the future: rooms on the books against what last year actually sold
	if forecast:
		start, end = getdate(forecast[0]["date"]), getdate(forecast[-1]["date"])
		sellable = _sellable(property)
		sold = sum(x["booked"] for x in forecast)
		n = sellable * len(forecast)
		this = {"rooms_sold": sold, "occupancy_pct": round(100 * sold / n, 1) if n else 0}
		last = range_stats(property, ly(start), ly(end), sellable)
		periods.append({"id": "on_the_books", "rooms_basis": "sellable",
		                "from_date": str(start), "to_date": str(end),
		                "ly_from_date": str(ly(start)), "ly_to_date": str(ly(end)),
		                "this_year": this, "last_year": last,
		                "change_pct": {k: _change(this[k], last[k]) for k in this}})
	return {"financial_year_start": str(fy), "periods": periods}


def sees_figures() -> bool:
	return bool(set(FIGURE_ROLES) & set(frappe.get_roles()))


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Revenue Manager", "Night Auditor", "Hotel Admin",
               "Kamra Agent")
def property_dashboard(property: str, date: str | None = None, with_comparison: int = 0):
	"""Everything one hotel's dashboard needs, by department. The year on
	year comparison is heavy, so only the Dashboard screen asks for it."""
	from kamra.crs import assert_property_access
	assert_property_access(property)
	date = date or nowdate()
	hk = _housekeeping_slice(property)
	forecast = occupancy_forecast(property, date)
	if not sees_figures():
		from kamra.reports import movement_counts
		move = movement_counts(property, date, date)
		return {
			"property": property,
			"property_name": frappe.db.get_value("Property", property, "property_name"),
			"date": date,
			"figures_hidden": True,
			**move,
			"front_desk": move,
			"housekeeping": hk,
			"occupancy_now": occupancy_now(property, hk),
			"forecast": forecast,
		}
	from kamra.reports import manager_flash
	flash = manager_flash(property, date)
	today = flash.get("today") or {}
	mtd = flash.get("mtd") or {}
	move = flash.get("movement") or {}
	finance = _finance_slice(property, date)

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
		# Room revenue ÷ rooms available today — same day as revenue_today.
		# (MTD RevPAR lives under statistics.revpar for the flash report.)
		"revpar": today.get("revpar", 0),
		"adr": today.get("adr", 0),
		"room_revenue_today": today.get("room_revenue", 0),
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
		"occupancy_now": occupancy_now(property, hk),
		"forecast": forecast,
		**({"comparison": comparison(property, date, flash.get("total_rooms", 0), forecast)}
		   if int(with_comparison or 0) else {}),
	}


def _whole(amount) -> float:
	"""Round money to whole units, half up - the way the portfolio shows it.
	Python's round() is half-to-even (11792.5 -> 11792) while the browser
	rounds half up (11,793), so a total rounded by one and a row by the other
	disagreed by a unit. Rows are rounded here once; totals add the rounded
	rows, so the tile is always the sum of the table."""
	return float(Decimal(str(amount or 0)).quantize(Decimal("1"), ROUND_HALF_UP))


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
		"revenue_today": _whole(s.get("room_revenue", 0) + s.get("fnb_revenue", 0)
		                        + s.get("other_revenue", 0)),
		"collections_today": _whole(finance["collections_today"]),
		"outstanding": _whole(finance["outstanding"]),
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
		# sums of the already-rounded rows: the tile equals the table
		"revenue_today": sum(r["revenue_today"] for r in rows),
		"collections_today": sum(r["collections_today"] for r in rows),
		"outstanding": sum(r["outstanding"] for r in rows),
	}
	rows.sort(key=lambda r: r["revenue_today"], reverse=True)
	return {"date": date, "totals": totals, "properties": rows}
