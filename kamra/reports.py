"""MIS reporting — the manager's flash and the trend behind it.

Everything is computed from folios (posted money) and reservations
(occupancy), never estimated: the same numbers the GST invoice and the
cash drawer reconcile to.
"""

import frappe
from frappe.utils import add_days, getdate, nowdate

from kamra.authz import require_roles


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
		        'Food & Beverage', 'Meal Plan', 'Minibar', 'Discount',
		        'Opening Balance')
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
@require_roles("Finance", "Hotel Admin")
def void_allowance_report(
	property: str,
	from_date: str | None = None,
	to_date: str | None = None,
):
	"""Audit trail of every void, allowance and invoice cancellation on a
	property: who reversed what, when, and why. The compliance answer to
	"show me every write-off" - read straight from the action log, so it
	cannot drift from what actually happened."""
	from kamra.crs import assert_property_access

	assert_property_access(property)
	filters = [
		["property", "=", property],
		[
			"action_type",
			"in",
			["void_charge", "post_allowance", "cancel_invoice",
			 "pos_void_item", "pos_cancel_order"],
		],
	]
	if from_date:
		filters.append(["creation", ">=", from_date])
	if to_date:
		filters.append(["creation", "<=", f"{to_date} 23:59:59"])
	rows = frappe.get_all(
		"Agent Action Log",
		filters=filters,
		fields=["creation", "actor", "action_type", "reference_doctype",
		        "reference_name", "rationale", "approver"],
		order_by="creation desc",
		limit_page_length=0,
	)
	label = {
		"void_charge": "Void",
		"post_allowance": "Allowance",
		"cancel_invoice": "Invoice cancelled",
		# restaurant bills: a voided line, or a whole bill cancelled
		"pos_void_item": "POS void",
		"pos_cancel_order": "POS bill cancelled",
	}
	pos = {"pos_void_item", "pos_cancel_order"}
	return [
		{
			"when": str(r.creation),
			"actor": r.actor,
			"action": label.get(r.action_type, r.action_type),
			# a folio, or the POS bill for the restaurant rows
			"folio": None if r.action_type in pos else r.reference_name,
			"pos_order": r.reference_name if r.action_type in pos else None,
			"approver": r.approver,
			"detail": r.rationale,
		}
		for r in rows
	]


@frappe.whitelist()
@require_roles("Finance", "Front Desk", "Night Auditor", "Kamra Agent")
def manager_flash(property: str, date: str | None = None,
                  from_date: str | None = None):
	"""The daily flash: yesterday's performance, month to date, today's
	movement, collections by mode, and the 7-day outlook. With from_date,
	the day figures, trend, movement and collections cover from_date..date."""
	from kamra.business_date import report_range_end

	date = date or nowdate()
	start = from_date or date
	report_range_end(start, date)
	total_rooms = frappe.db.count("Room", {"property": property}) or 0

	month = _days(property, getdate(date).replace(day=1), getdate(date), total_rooms)
	days = _days(property, getdate(start), getdate(date), total_rooms)

	def count(field, statuses):
		return frappe.db.count("Reservation", {
			"property": property, field: ("between", [start, date]),
			"status": ("in", statuses)})

	movement = {
		"arrivals": count("check_in_date", ["Confirmed", "Checked In"]),
		"departures": count("check_out_date", ["Checked In", "Checked Out"]),
		"in_house": frappe.db.count("Reservation", {
			"property": property, "status": "Checked In"}),
		"no_shows": count("check_in_date", ["No Show"]),
	}

	from kamra.api import cash_summary
	collections = cash_summary(property, start, date)

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
		"date": str(date), "from_date": str(start), "total_rooms": total_rooms,
		"today": days[-1] if len(days) == 1 else _sum_days(days, total_rooms),
		"mtd": _sum_days(month, total_rooms), "movement": movement,
		"collections": collections,
		"trend": days if len(days) > 1 else month[-14:],
		"outlook": outlook,
	}


def _days(property: str, d, end, total_rooms: int) -> list[dict]:
	out = []
	while d <= end:
		out.append(_day_stats(property, str(d), total_rooms))
		d = getdate(add_days(d, 1))
	return out


def _sum_days(days: list[dict], total_rooms: int) -> dict:
	"""Several days' stats as one: totals, with rates over the whole span."""
	tot = {k: sum(d[k] for d in days) for k in
	       ("rooms_sold", "pax", "room_revenue", "fnb_revenue", "other_revenue",
	        "total_revenue")}
	n = total_rooms * len(days)
	return {**tot,
	        "occupancy_pct": round(100 * tot["rooms_sold"] / n, 1) if n else 0,
	        "adr": round(tot["room_revenue"] / tot["rooms_sold"], 0) if tot["rooms_sold"] else 0,
	        "revpar": round(tot["room_revenue"] / n, 0) if n else 0,
	        "revpax": round(tot["total_revenue"] / tot["pax"], 0) if tot["pax"] else 0}


def _month_bounds(period: str):
	"""'2026-07' -> (first day, first day of next month, days in month)."""
	from datetime import datetime

	from frappe.utils import add_days, date_diff, get_first_day, get_last_day

	start = get_first_day(datetime.strptime(period + "-01", "%Y-%m-%d"))
	last = get_last_day(start)
	nxt = add_days(last, 1)
	return str(start), str(nxt), date_diff(nxt, start)


@frappe.whitelist()
@require_roles("Finance", "Revenue Manager", "Kamra Agent")
def budget_vs_actual(property: str, period: str | None = None):
	"""Monthly target vs actual: room revenue, occupancy %, ADR, RevPAR - with
	variance. period is 'YYYY-MM' (defaults to the current month).

	"Actual" is posted money: Room charges on folios, dated inside the month.
	A room night reaches a folio when End of Day (night audit) posts it, so a
	stay in-house tonight counts once its night is audited - not before.
	Occupancy and RevPAR divide by the room nights elapsed so far (to the
	business date), not the whole month, so a month-to-date figure compares
	with a monthly occupancy target. `on_books_nights` / `unposted_nights`
	say how many sold nights in the same window are still waiting for End
	of Day, so a zero is explained rather than mysterious."""
	from frappe.utils import date_diff, nowdate

	period = period or nowdate()[:7]
	start, nxt, days = _month_bounds(period)
	total_rooms = frappe.db.count("Room", {"property": property}) or 0

	# the nights that have happened: up to the business date (the night
	# being audited next), else through today
	business = frappe.db.get_value("Property", property, "business_date") \
		if frappe.db.has_column("Property", "business_date") else None
	upto = str(getdate(business)) if business else str(add_days(nowdate(), 1))
	window_end = min(max(upto, start), nxt)
	elapsed = date_diff(window_end, start)
	room_nights = total_rooms * elapsed

	agg = frappe.db.sql(
		"""
		SELECT
		  COUNT(DISTINCT CASE WHEN fc.charge_type='Room'
		        THEN CONCAT(COALESCE(fc.reservation,f.reservation),'|',fc.posting_date) END) AS rooms_sold,
		  COALESCE(SUM(CASE WHEN fc.charge_type='Room' THEN fc.amount ELSE 0 END),0) AS room_revenue,
		  MAX(CASE WHEN fc.charge_type='Room' THEN fc.posting_date END) AS posted_through
		FROM `tabFolio Charge` fc JOIN `tabFolio` f ON fc.parent=f.name
		WHERE f.property=%(p)s AND fc.posting_date>=%(s)s AND fc.posting_date<%(n)s
		""",
		{"p": property, "s": start, "n": nxt}, as_dict=True)[0]
	sold = int(agg.rooms_sold or 0)
	room_rev = float(agg.room_revenue or 0)
	# sold nights in the same elapsed window, whether posted yet or not -
	# and, stay by stay, how many of them End of Day hasn't posted. Per stay,
	# not house totals: a no-show or cancellation fee posts a Room charge for
	# a stay that isn't on the books, and must not hide another stay's gap.
	stays = frappe.db.sql(
		"""
		SELECT name, DATEDIFF(LEAST(check_out_date, %(e)s),
		                      GREATEST(check_in_date, %(s)s)) AS nights
		FROM `tabReservation`
		WHERE property=%(p)s
		  AND status IN ('Confirmed', 'Checked In', 'Checked Out')
		  AND check_in_date < %(e)s AND check_out_date > %(s)s
		""",
		{"p": property, "s": start, "e": window_end}, as_dict=True)
	on_books = sum(int(r.nights or 0) for r in stays)
	posted_by_stay = dict(frappe.db.sql(
		"""
		SELECT COALESCE(fc.reservation, f.reservation) AS res,
		       COUNT(DISTINCT fc.posting_date)
		FROM `tabFolio Charge` fc JOIN `tabFolio` f ON fc.parent=f.name
		WHERE f.property=%(p)s AND fc.charge_type='Room'
		  AND fc.posting_date>=%(s)s AND fc.posting_date<%(e)s
		GROUP BY res
		""",
		{"p": property, "s": start, "e": window_end})) if stays else {}
	unposted = sum(max(0, int(r.nights or 0) - int(posted_by_stay.get(r.name) or 0))
	               for r in stays)

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
	return {"period": period, "days_elapsed": elapsed,
	        "total_days": days, "rows": rows, "has_budget": bool(b),
	        "basis": "posted",
	        "posted_nights": sold,
	        "posted_through": str(agg.posted_through) if agg.posted_through else None,
	        "on_books_nights": on_books,
	        "unposted_nights": unposted,
	        "elapsed_room_nights": room_nights}


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
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional
	return {"ok": True}


@frappe.whitelist()
@require_roles("Finance", "Revenue Manager", "Kamra Agent")
def contribution(property: str, from_date: str, to_date: str,
                 by: str = "source"):
	"""Who brings the business: revenue + room nights + share + the
	commission paid for it (travel agent or OTA), grouped by booking source,
	company, travel agent or OTA channel.
	by = source | company | travel_agent | channel."""
	col = {"source": "r.source", "company": "r.company",
	       "travel_agent": "r.travel_agent",
	       "channel": "r.channel"}.get(by, "r.source")
	rows = frappe.db.sql(  # nosemgrep: frappe-sql-format-injection -- values are parameterized; interpolated text is a constant or whitelisted identifier, not user input
		f"""
		SELECT COALESCE({col}, 'Direct') AS label,
		       COUNT(*) AS bookings,
		       COALESCE(SUM(r.nights),0) AS room_nights,
		       COALESCE(SUM(r.amount_after_tax),0) AS revenue,
		       COALESCE(SUM(r.commission_amount),0) AS commission
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
		x["commission"] = round(float(x.commission or 0), 0)
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
		SELECT name, subject, category, priority, status, breached,
		       creation, due_by, resolved_on, resolved_by, assigned_to_user
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

	# a ticket is resolved when it is Resolved or Closed - one rule for the
	# headline and every breakdown. A ticket closed without passing through
	# Resolved has no resolved_on, so it counts as resolved but adds no
	# time to the averages.
	done = ("Resolved", "Closed")
	total = len(tickets)
	resolved = [t for t in tickets if t.status in done]
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
			if t.status in done:
				row["resolved"] += 1
				m = resolve_mins(t)
				if m is not None:
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
			"subject": t.subject, "assigned_to_user": t.assigned_to_user,
			"overdue_hours": round(over_min / 60, 1),
		})
	overdue.sort(key=lambda r: r["overdue_hours"], reverse=True)

	# who solved them, and the whole open backlog - not only this window's
	solver: dict[str, dict] = {}
	for t in resolved:
		who = t.resolved_by or ""
		row = solver.setdefault(who, {"user": who or None, "resolved": 0, "breached": 0, "mins": []})
		row["resolved"] += 1
		if is_breached(t):
			row["breached"] += 1
		m = resolve_mins(t)
		if m is not None:
			row["mins"].append(m)
	people = {u.name: u.full_name for u in frappe.get_all(
		"User", filters={"name": ["in", [k for k in solver if k]]}, fields=["name", "full_name"])} if solver else {}
	by_resolver = []
	for row in solver.values():
		mins = row.pop("mins")
		row["name"] = people.get(row["user"]) or row["user"] or "Not recorded"
		row["avg_resolve_mins"] = round(sum(mins) / len(mins)) if mins else None
		by_resolver.append(row)
	by_resolver.sort(key=lambda x: x["resolved"], reverse=True)

	open_all = frappe.db.sql(
		"""SELECT name, subject, category, priority, status, creation, due_by, assigned_to_user
		   FROM `tabService Ticket` WHERE property=%s AND status IN ('Open','In Progress')
		   ORDER BY creation ASC""", property, as_dict=True)
	buckets = [("Under 1 day", 0, 1), ("1 to 3 days", 1, 3), ("3 to 7 days", 3, 7), ("Over 7 days", 7, 10**6)]
	aging = []
	for label, lo, hi in buckets:
		n = sum(1 for t in open_all
		        if lo <= time_diff_in_seconds(now, get_datetime(t.creation)) / 86400 < hi)
		aging.append({"label": label, "count": n})
	asg = {u.name: u.full_name for u in frappe.get_all(
		"User", filters={"name": ["in", [t.assigned_to_user for t in open_all if t.assigned_to_user] or [""]]},
		fields=["name", "full_name"])}
	oldest_open = [{
		"name": t.name, "subject": t.subject, "category": t.category, "priority": t.priority,
		"status": t.status, "age_days": round(time_diff_in_seconds(now, get_datetime(t.creation)) / 86400, 1),
		"assigned_to_user": t.assigned_to_user, "assigned_to_name": asg.get(t.assigned_to_user),
	} for t in open_all[:15]]

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
		"by_resolver": by_resolver,
		"aging": aging,
		"oldest_open": oldest_open,
		"open_total": len(open_all),
		"unassigned_open": sum(1 for t in open_all if not t.assigned_to_user),
	}
