"""MIS reporting — the manager's flash and the trend behind it.

Everything is computed from folios (posted money) and reservations
(occupancy), never estimated: the same numbers the GST invoice and the
cash drawer reconcile to.
"""

import frappe
from kamra.authz import require_roles
from frappe.utils import add_days, getdate, nowdate


def _day_stats(property: str, date: str, total_rooms: int) -> dict:
	row = frappe.db.sql(
		"""
		SELECT
		  COUNT(DISTINCT CASE WHEN fc.charge_type = 'Room'
		        THEN COALESCE(fc.reservation, f.reservation) END) AS rooms_sold,
		  COALESCE(SUM(CASE WHEN fc.charge_type = 'Room'
		        THEN fc.amount ELSE 0 END), 0) AS room_revenue,
		  COALESCE(SUM(CASE WHEN fc.charge_type IN ('Food & Beverage',
		        'Meal Plan', 'Minibar') THEN fc.amount ELSE 0 END), 0)
		        AS fnb_revenue,
		  COALESCE(SUM(CASE WHEN fc.charge_type NOT IN ('Room',
		        'Food & Beverage', 'Meal Plan', 'Minibar', 'Discount')
		        THEN fc.amount ELSE 0 END), 0) AS other_revenue
		FROM `tabFolio Charge` fc
		JOIN `tabFolio` f ON fc.parent = f.name
		WHERE f.property = %(p)s AND fc.posting_date = %(d)s
		""",
		{"p": property, "d": date}, as_dict=True)[0]
	sold = int(row.rooms_sold or 0)
	rev = float(row.room_revenue or 0)
	fnb = float(row.fnb_revenue or 0)
	other = float(row.other_revenue or 0)
	total_rev = rev + fnb + other
	# guests (pax) in-house that night — the denominator for RevPAX
	pax = int(frappe.db.sql(
		"""
		SELECT COALESCE(SUM(adults + IFNULL(children, 0)), 0)
		FROM `tabReservation`
		WHERE property = %(p)s AND status IN ('Checked In', 'Checked Out')
		  AND check_in_date <= %(d)s AND check_out_date > %(d)s
		""",
		{"p": property, "d": date})[0][0] or 0)
	return {
		"date": str(date),
		"rooms_sold": sold,
		"pax": pax,
		"occupancy_pct": round(100 * sold / total_rooms, 1) if total_rooms else 0,
		"room_revenue": rev,
		"fnb_revenue": fnb,
		"other_revenue": other,
		"total_revenue": total_rev,
		"adr": round(rev / sold, 0) if sold else 0,
		"revpar": round(rev / total_rooms, 0) if total_rooms else 0,
		# RevPAX — total guest spend (room + all ancillary) per in-house guest.
		# Captures the F&B / experiences / upgrades revenue that RevPAR misses.
		"revpax": round(total_rev / pax, 0) if pax else 0,
	}


@frappe.whitelist()
@require_roles("Finance", "Front Desk", "Kamra Agent")
def manager_flash(property: str, date: str | None = None):
	"""The daily flash: yesterday's performance, month to date, today's
	movement, collections by mode, and the 7-day outlook."""
	date = date or nowdate()
	total_rooms = frappe.db.count("Room", {"property": property}) or 0

	# month-to-date across day stats
	mtd = {"rooms_sold": 0, "room_revenue": 0.0, "fnb_revenue": 0.0,
	       "other_revenue": 0.0}
	d = getdate(date).replace(day=1)
	end = getdate(date)
	days = 0
	trend = []
	while d <= end:
		s = _day_stats(property, str(d), total_rooms)
		for k in mtd:
			mtd[k] += s[k]
		trend.append(s)
		days += 1
		d = getdate(add_days(d, 1))
	mtd["occupancy_pct"] = round(
		100 * mtd["rooms_sold"] / (total_rooms * days), 1) if total_rooms and days else 0
	mtd["adr"] = round(mtd["room_revenue"] / mtd["rooms_sold"], 0) \
		if mtd["rooms_sold"] else 0
	mtd["revpar"] = round(mtd["room_revenue"] / (total_rooms * days), 0) \
		if total_rooms and days else 0

	movement = {
		"arrivals": frappe.db.count("Reservation", {
			"property": property, "check_in_date": date,
			"status": ("in", ["Confirmed", "Checked In"])}),
		"departures": frappe.db.count("Reservation", {
			"property": property, "check_out_date": date,
			"status": ("in", ["Checked In", "Checked Out"])}),
		"in_house": frappe.db.count("Reservation", {
			"property": property, "status": "Checked In"}),
		"no_shows": frappe.db.count("Reservation", {
			"property": property, "check_in_date": date,
			"status": "No Show"}),
	}

	from kamra.api import cash_summary
	collections = cash_summary(property, date)

	outlook = []
	for i in range(1, 8):
		od = str(add_days(date, i))
		booked = frappe.db.sql(
			"""
			SELECT COUNT(*) FROM `tabReservation`
			WHERE property = %(p)s AND status IN ('Confirmed', 'Checked In')
			  AND check_in_date <= %(d)s AND check_out_date > %(d)s
			""", {"p": property, "d": od})[0][0]
		outlook.append({
			"date": od, "booked": int(booked),
			"occupancy_pct": round(100 * booked / total_rooms, 1)
			if total_rooms else 0,
		})

	return {
		"date": str(date), "total_rooms": total_rooms,
		"today": trend[-1] if trend else None,
		"mtd": mtd, "movement": movement,
		"collections": collections,
		"trend": trend[-14:],
		"outlook": outlook,
	}


def _month_bounds(period: str):
	"""'2026-07' -> (first day, first day of next month, days in month)."""
	from frappe.utils import get_first_day, get_last_day, date_diff, add_days
	from datetime import datetime

	start = get_first_day(datetime.strptime(period + "-01", "%Y-%m-%d"))
	last = get_last_day(start)
	nxt = add_days(last, 1)
	return str(start), str(nxt), date_diff(nxt, start)


@frappe.whitelist()
@require_roles("Finance", "Revenue Manager", "Kamra Agent")
def budget_vs_actual(property: str, period: str | None = None):
	"""Monthly target vs actual: room revenue, occupancy %, ADR, RevPAR - with
	variance. period is 'YYYY-MM' (defaults to the current month)."""
	from frappe.utils import nowdate

	period = period or nowdate()[:7]
	start, nxt, days = _month_bounds(period)
	total_rooms = frappe.db.count("Room", {"property": property}) or 0
	room_nights = total_rooms * days

	agg = frappe.db.sql(
		"""
		SELECT
		  COUNT(DISTINCT CASE WHEN fc.charge_type='Room'
		        THEN CONCAT(COALESCE(fc.reservation,f.reservation),'|',fc.posting_date) END) AS rooms_sold,
		  COALESCE(SUM(CASE WHEN fc.charge_type='Room' THEN fc.amount ELSE 0 END),0) AS room_revenue
		FROM `tabFolio Charge` fc JOIN `tabFolio` f ON fc.parent=f.name
		WHERE f.property=%(p)s AND fc.posting_date>=%(s)s AND fc.posting_date<%(n)s
		""",
		{"p": property, "s": start, "n": nxt}, as_dict=True)[0]
	sold = int(agg.rooms_sold or 0)
	room_rev = float(agg.room_revenue or 0)

	actual = {
		"room_revenue": round(room_rev, 0),
		"occupancy_pct": round(100 * sold / room_nights, 1) if room_nights else 0,
		"adr": round(room_rev / sold, 0) if sold else 0,
		"revpar": round(room_rev / room_nights, 0) if room_nights else 0,
	}
	b = frappe.db.get_value(
		"Revenue Budget", {"property": property, "period": period},
		["name", "room_revenue_target", "occupancy_target", "adr_target",
		 "revpar_target"], as_dict=True) or {}
	target = {
		"room_revenue": float(b.get("room_revenue_target") or 0),
		"occupancy_pct": float(b.get("occupancy_target") or 0),
		"adr": float(b.get("adr_target") or 0),
		"revpar": float(b.get("revpar_target") or 0),
	}
	rows = []
	for key, label in [("room_revenue", "Room Revenue"),
	                   ("occupancy_pct", "Occupancy %"),
	                   ("adr", "ADR / ARR"), ("revpar", "RevPAR")]:
		a, t = actual[key], target[key]
		rows.append({
			"metric": label, "key": key, "actual": a, "target": t,
			"variance": round(a - t, 1),
			"attainment": round(100 * a / t, 0) if t else None,
		})
	return {"period": period, "days_elapsed": min(
		days, max(0, __import__("frappe").utils.date_diff(nowdate(), start) + 1)),
		"total_days": days, "rows": rows, "has_budget": bool(b)}


@frappe.whitelist(methods=["POST"])
@require_roles("Revenue Manager", "Hotel Admin", "Finance")
def save_budget(property: str, period: str, room_revenue_target: float = 0,
                occupancy_target: float = 0, adr_target: float = 0,
                revpar_target: float = 0):
	name = frappe.db.get_value(
		"Revenue Budget", {"property": property, "period": period})
	doc = frappe.get_doc("Revenue Budget", name) if name \
		else frappe.new_doc("Revenue Budget")
	doc.update({
		"property": property, "period": period,
		"room_revenue_target": room_revenue_target,
		"occupancy_target": occupancy_target,
		"adr_target": adr_target, "revpar_target": revpar_target,
	})
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"ok": True}


@frappe.whitelist()
@require_roles("Finance", "Revenue Manager", "Kamra Agent")
def contribution(property: str, from_date: str, to_date: str,
                 by: str = "source"):
	"""Who brings the business: revenue + room nights + share, grouped by
	booking source, company or travel agent. by = source | company | travel_agent."""
	col = {"source": "r.source", "company": "r.company",
	       "travel_agent": "r.travel_agent"}.get(by, "r.source")
	rows = frappe.db.sql(
		f"""
		SELECT COALESCE({col}, 'Direct') AS label,
		       COUNT(*) AS bookings,
		       COALESCE(SUM(r.nights),0) AS room_nights,
		       COALESCE(SUM(r.amount_after_tax),0) AS revenue
		FROM `tabReservation` r
		WHERE r.property=%(p)s
		  AND r.status IN ('Confirmed','Checked In','Checked Out')
		  AND r.check_in_date>=%(f)s AND r.check_in_date<=%(t)s
		GROUP BY label
		ORDER BY revenue DESC
		""",
		{"p": property, "f": from_date, "t": to_date}, as_dict=True)
	total = sum(float(x.revenue or 0) for x in rows) or 1
	for x in rows:
		x["revenue"] = round(float(x.revenue or 0), 0)
		x["share"] = round(100 * x["revenue"] / total, 1)
	return {"by": by, "total": round(total, 0), "rows": rows}


@frappe.whitelist()
@require_roles("Front Desk", "Hotel Admin", "Kamra Agent")
def sla_report(property: str, from_date: str, to_date: str):
	"""Operations SLA health from Service Tickets over a window: overall
	resolution and breach rates, a breakdown by category and by priority,
	and the currently-overdue queue aged by how long it's past its due time.

	Time-to-resolve is measured creation -> resolved_on; a ticket counts as
	breached if it was resolved after due_by, or is still open past due_by."""
	tickets = frappe.db.sql(
		"""
		SELECT name, category, priority, status, breached,
		       creation, due_by, resolved_on
		FROM `tabService Ticket`
		WHERE property=%(p)s AND DATE(creation)>=%(f)s AND DATE(creation)<=%(t)s
		""",
		{"p": property, "f": from_date, "t": to_date}, as_dict=True)

	from frappe.utils import get_datetime, now_datetime, time_diff_in_seconds
	now = now_datetime()

	def resolve_mins(tk):
		if tk.resolved_on:
			return time_diff_in_seconds(get_datetime(tk.resolved_on),
			                            get_datetime(tk.creation)) / 60
		return None

	def is_breached(tk):
		if tk.breached:
			return True
		if not tk.due_by:
			return False
		end = get_datetime(tk.resolved_on) if tk.resolved_on else now
		return end > get_datetime(tk.due_by)

	total = len(tickets)
	resolved = [t for t in tickets if t.status in ("Resolved", "Closed")]
	breached = [t for t in tickets if is_breached(t)]
	res_mins = [m for m in (resolve_mins(t) for t in resolved) if m is not None]

	def group_by(key):
		g: dict[str, dict] = {}
		for t in tickets:
			k = t.get(key) or "Other"
			row = g.setdefault(k, {"label": k, "count": 0, "breached": 0,
			                       "resolved": 0, "mins": []})
			row["count"] += 1
			if is_breached(t):
				row["breached"] += 1
			m = resolve_mins(t)
			if m is not None:
				row["resolved"] += 1
				row["mins"].append(m)
		out = []
		for row in g.values():
			mins = row.pop("mins")
			row["avg_resolve_mins"] = round(sum(mins) / len(mins)) if mins else None
			row["breach_pct"] = round(100 * row["breached"] / row["count"], 1) \
				if row["count"] else 0
			out.append(row)
		return sorted(out, key=lambda r: r["count"], reverse=True)

	# overdue queue: still open, past due, aged
	overdue = []
	for t in tickets:
		if t.status in ("Resolved", "Closed", "Cancelled") or not t.due_by:
			continue
		over_min = time_diff_in_seconds(now, get_datetime(t.due_by)) / 60
		if over_min <= 0:
			continue
		overdue.append({
			"name": t.name, "category": t.category, "priority": t.priority,
			"overdue_hours": round(over_min / 60, 1),
		})
	overdue.sort(key=lambda r: r["overdue_hours"], reverse=True)

	return {
		"from": from_date, "to": to_date,
		"total": total,
		"resolved": len(resolved),
		"open": total - len(resolved),
		"breached": len(breached),
		"breach_pct": round(100 * len(breached) / total, 1) if total else 0,
		"avg_resolve_mins": round(sum(res_mins) / len(res_mins)) if res_mins else None,
		"by_category": group_by("category"),
		"by_priority": group_by("priority"),
		"overdue": overdue,
	}
