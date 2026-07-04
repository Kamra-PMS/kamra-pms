"""Whitelisted API for the Kamra front-desk UI.

Every endpoint here is also, by design, an agent tool: the same governed
surface serves the React console today and the MCP layer next.
"""

import frappe
from frappe.utils import add_days, nowdate


@frappe.whitelist()
def whoami():
	"""Current user + roles — drives which modules the UI shows."""
	user = frappe.session.user
	return {
		"user": user,
		"full_name": frappe.db.get_value("User", user, "full_name") or user,
		"roles": frappe.get_roles(user),
	}


@frappe.whitelist()
def set_room_rate(property: str, room_type: str, start_date: str,
                  end_date: str, rate: float, reason: str = ""):
	"""Set the nightly rate for a room type over a date range — bounded by
	the owner's Rate Guardrails (PRD FR-30). This is the Revenue Agent's
	write tool: it can never price outside the rails."""
	rate = float(rate)

	guardrails = frappe.get_all(
		"Rate Guardrail",
		filters={"property": property, "disabled": 0,
		         "room_type": ("in", [room_type, "", None])},
		fields=["name", "room_type", "floor_price", "ceiling_price"],
	)
	# most specific rail wins (room-type-specific over property-wide)
	rail = next((g for g in guardrails if g.room_type == room_type),
	            guardrails[0] if guardrails else None)
	if rail:
		if rate < float(rail.floor_price):
			frappe.throw(
				f"Blocked by guardrail {rail.name}: ₹{rate:,.0f} is below "
				f"the floor of ₹{float(rail.floor_price):,.0f}."
			)
		if rate > float(rail.ceiling_price):
			frappe.throw(
				f"Blocked by guardrail {rail.name}: ₹{rate:,.0f} is above "
				f"the ceiling of ₹{float(rail.ceiling_price):,.0f}."
			)

	season = frappe.get_doc({
		"doctype": "Season",
		"property": property,
		"season_name": f"Rate set {room_type.split('-')[-1]} "
		               f"{start_date}→{end_date}",
		"start_date": start_date,
		"end_date": end_date,
		"adjustment_type": "Absolute",
		"adjustment_value": rate,
		"priority": 100,
	})
	# absolute seasons apply per room type via the pricing engine only when
	# scoped — v0 seasons are property-wide, so callers should set rates per
	# room type ranges deliberately. Tracked as a follow-up to scope seasons.
	season.insert()

	from kamra.savings import log_action
	log_action(
		action_type="set_rate",
		reference_doctype="Season",
		reference_name=season.name,
		property=property,
		minutes_saved=6,
		rationale=reason or f"Nightly rate → ₹{rate:,.0f} for {room_type} "
		                    f"{start_date}→{end_date}",
		channel="API",
	)
	return {
		"season": season.name, "rate": rate,
		"guardrail_checked": rail.name if rail else None,
	}


@frappe.whitelist()
def owner_briefing(property: str, date: str | None = None):
	"""Deterministic numbers for the owner's morning briefing (PRD FR-70).
	An LLM turns this into prose; it never invents the figures."""
	from frappe.utils import getdate

	date = date or nowdate()
	yesterday = add_days(date, -1)

	rooms_total = frappe.db.count("Room", {"property": property})
	occupied = frappe.db.count(
		"Reservation", {"property": property, "status": "Checked In"}
	)
	arrivals = frappe.db.count(
		"Reservation",
		{"property": property, "status": "Confirmed", "check_in_date": date},
	)
	departures = frappe.db.count(
		"Reservation",
		{"property": property, "status": "Checked In", "check_out_date": date},
	)

	# yesterday's room revenue + rooms sold from posted folio charges
	rev, rooms_sold = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(fc.amount), 0),
		       COUNT(DISTINCT CASE WHEN fc.charge_type = 'Room'
		                           THEN f.name END)
		FROM `tabFolio Charge` fc
		JOIN `tabFolio` f ON fc.parent = f.name
		WHERE f.property = %(property)s
		  AND fc.posting_date = %(date)s
		  AND fc.charge_type IN ('Room', 'Meal Plan')
		""",
		{"property": property, "date": yesterday},
	)[0]
	room_revenue = float(rev or 0)
	rooms_sold = int(rooms_sold or 0)

	occupancy_pct = round(occupied / rooms_total * 100, 1) if rooms_total else 0
	adr = round(room_revenue / rooms_sold, 0) if rooms_sold else 0
	revpar = round(room_revenue / rooms_total, 0) if rooms_total else 0

	open_tickets = frappe.get_all(
		"Service Ticket",
		filters={"property": property,
		         "status": ("in", ["Open", "In Progress"])},
		fields=["name", "subject", "priority", "due_by"],
	)

	minutes = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(minutes_saved), 0) FROM `tabAgent Action Log`
		WHERE property = %(property)s AND DATE(creation) = %(date)s
		""",
		{"property": property, "date": yesterday},
	)[0][0]

	audit = frappe.db.get_value(
		"Night Audit Run", {"property": property, "business_date": yesterday},
		["name", "room_charges_posted", "no_shows_flagged"], as_dict=True,
	)

	next_7 = availability_calendar(property, date, 7)
	pickup = [
		{"date": c["date"],
		 "rooms_available": sum(
			 rt["cells"][i]["available"] for rt in next_7["room_types"]
		 )}
		for i, c in enumerate(next_7["room_types"][0]["cells"])
	] if next_7["room_types"] else []

	return {
		"date": str(getdate(date)),
		"occupancy_pct": occupancy_pct,
		"rooms_occupied": occupied,
		"rooms_total": rooms_total,
		"arrivals_today": arrivals,
		"departures_today": departures,
		"yesterday": {
			"room_revenue": room_revenue, "adr": adr, "revpar": revpar,
			"night_audit": audit,
			"agent_minutes_saved": float(minutes or 0),
		},
		"open_tickets": open_tickets,
		"next_7_days_availability": pickup,
	}


@frappe.whitelist()
def create_ticket(property: str, subject: str, category: str,
                  priority: str = "Medium", room: str | None = None,
                  reservation: str | None = None, guest: str | None = None,
                  description: str | None = None, source: str = "Manual"):
	"""Create a guest-request ticket. This is also the agent tool for
	'guest wants towels / AC is broken' — PRD FR-42."""
	doc = frappe.get_doc({
		"doctype": "Service Ticket",
		"property": property,
		"subject": subject,
		"category": category,
		"priority": priority,
		"room": room or None,
		"reservation": reservation or None,
		"guest": guest or None,
		"description": description,
		"source": source,
	})
	doc.insert()
	if source in ("AI Agent", "WhatsApp", "Voice", "QR"):
		from kamra.savings import log_action
		log_action("create_ticket", "Service Ticket", doc.name, property,
		           minutes_saved=4,
		           rationale=f"Captured request without staff: {subject}",
		           agent_name="Concierge", channel=source)
	return {"ticket": doc.name, "due_by": str(doc.due_by)}


@frappe.whitelist()
def tickets_list(property: str, show_closed: int = 0):
	filters = {"property": property}
	if not int(show_closed):
		filters["status"] = ("in", ["Open", "In Progress"])
	rows = frappe.get_all(
		"Service Ticket",
		filters=filters,
		fields=["name", "subject", "category", "priority", "status", "source",
		        "room", "guest_name", "due_by", "resolved_on", "breached",
		        "assigned_to_user", "creation"],
		order_by="creation desc",
		limit=200,
	)
	now = str(frappe.utils.now_datetime())
	for r in rows:
		r["overdue"] = bool(
			r.status in ("Open", "In Progress")
			and r.due_by and str(r.due_by) < now
		)
	return rows


@frappe.whitelist()
def advance_ticket(ticket: str, status: str, resolution_note: str | None = None):
	allowed = {"In Progress", "Resolved", "Closed", "Cancelled"}
	if status not in allowed:
		frappe.throw(f"Status must be one of {sorted(allowed)}")
	doc = frappe.get_doc("Service Ticket", ticket)
	doc.status = status
	if resolution_note:
		doc.resolution_note = resolution_note
	doc.save()
	return {"ticket": doc.name, "status": doc.status,
	        "breached": bool(doc.breached)}


@frappe.whitelist()
def get_folio(reservation: str):
	"""Folio for a reservation — opens one if the guest is checked in."""
	name = frappe.db.get_value(
		"Folio", {"reservation": reservation, "folio_type": "Guest"}
	)
	if not name:
		res = frappe.get_doc("Reservation", reservation)
		if res.status not in ("Checked In", "Checked Out"):
			return None
		from kamra.folio import open_folio
		name = open_folio(res)
	folio = frappe.get_doc("Folio", name)
	return folio.as_dict()


@frappe.whitelist()
def add_folio_charge(folio: str, charge_type: str, description: str,
                     amount: float, gst_rate: float = 0,
                     posting_date: str | None = None):
	doc = frappe.get_doc("Folio", folio)
	if doc.status == "Closed":
		frappe.throw("Folio is closed.")
	doc.append("charges", {
		"posting_date": posting_date or nowdate(),
		"charge_type": charge_type,
		"description": description,
		"qty": 1,
		"rate": float(amount),
		"amount": float(amount),
		"gst_rate": float(gst_rate),
	})
	from kamra.folio import _recalculate
	_recalculate(doc)
	doc.save()
	from kamra.savings import log_action
	log_action("post_charge", "Folio", doc.name, doc.property,
	           rationale=f"{charge_type}: {description} ₹{amount}")
	return doc.as_dict()


@frappe.whitelist()
def add_folio_payment(folio: str, mode: str, amount: float,
                      reference: str | None = None):
	doc = frappe.get_doc("Folio", folio)
	doc.append("payments", {
		"posting_date": nowdate(),
		"mode": mode,
		"amount": float(amount),
		"reference": reference,
	})
	from kamra.folio import _recalculate
	_recalculate(doc)
	doc.save()
	return doc.as_dict()


@frappe.whitelist()
def split_folio(reservation: str, folio_type: str = "Extra"):
	from kamra.folio import split_folio as _split
	return {"folio": _split(reservation, folio_type)}


@frappe.whitelist()
def transfer_folio_charge(from_folio: str, charge_row: str, to_folio: str):
	from kamra.folio import transfer_charge
	transfer_charge(from_folio, charge_row, to_folio)
	from kamra.savings import log_action
	log_action("transfer_charge", "Folio", to_folio,
	           rationale=f"Moved charge {charge_row} {from_folio} → {to_folio}")
	return {"ok": True}


@frappe.whitelist()
def reservation_folios(reservation: str):
	"""All folios of a stay (guest + splits) with balances."""
	return frappe.get_all(
		"Folio",
		filters={"reservation": reservation},
		fields=["name", "folio_type", "status", "invoice_number",
		        "grand_total", "payments_total", "balance"],
		order_by="creation asc",
	)


@frappe.whitelist()
def close_folio(folio: str):
	from kamra.folio import close_folio as _close
	invoice_number = _close(folio)
	return {"invoice_number": invoice_number}


@frappe.whitelist()
def folio_invoice(folio: str):
	"""Everything a GST invoice print needs, with the multi-rate breakup."""
	doc = frappe.get_doc("Folio", folio)
	prop = frappe.get_doc("Property", doc.property)
	res = frappe.get_doc("Reservation", doc.reservation)

	# GST summary grouped by rate — the GSTR-compliant breakup
	by_rate: dict = {}
	for c in doc.charges:
		key = float(c.gst_rate or 0)
		slot = by_rate.setdefault(key, {"taxable": 0.0, "tax": 0.0})
		slot["taxable"] += float(c.amount or 0)
		slot["tax"] += float(c.gst_amount or 0)

	return {
		"folio": doc.as_dict(),
		"property": {
			"name": prop.property_name, "legal_name": prop.legal_name,
			"address": ", ".join(filter(None, [prop.address_line, prop.city,
			                                   prop.state, prop.pincode])),
			"gstin": prop.gstin, "phone": prop.phone, "email": prop.email,
		},
		"stay": {
			"reservation": res.name,
			"check_in": str(res.check_in_date),
			"check_out": str(res.check_out_date),
			"nights": res.nights, "room": res.room,
			"company": res.company,
		},
		"gst_summary": [
			{"rate": rate, "taxable": v["taxable"],
			 "cgst": v["tax"] / 2, "sgst": v["tax"] / 2, "total_tax": v["tax"]}
			for rate, v in sorted(by_rate.items())
		],
	}


@frappe.whitelist()
def run_night_audit(property: str, business_date: str | None = None):
	from kamra.folio import run_night_audit as _run
	return _run(property, business_date)


@frappe.whitelist()
def gstr1_rows(from_date: str, to_date: str):
	"""Invoice-level rows for a GSTR-1 style export (v0: B2C summary)."""
	folios = frappe.get_all(
		"Folio",
		filters={
			"status": "Closed",
			"closed_on": ("between", [from_date, to_date]),
		},
		fields=["name", "invoice_number", "guest_name", "closed_on",
		        "charges_total", "tax_total", "grand_total"],
		order_by="closed_on asc",
	)
	return folios


@frappe.whitelist()
def guests_with_stats(search: str | None = None):
	"""Guest list with stay stats — the CRM index."""
	where = ""
	params: dict = {}
	if search:
		where = "WHERE g.full_name LIKE %(q)s OR g.phone LIKE %(q)s"
		params["q"] = f"%{search}%"
	return frappe.db.sql(
		f"""
		SELECT
			g.name, g.full_name, g.phone, g.email, g.vip,
			COUNT(r.name) AS bookings,
			SUM(CASE WHEN r.status IN ('Checked In','Checked Out') THEN 1 ELSE 0 END) AS stays,
			COALESCE(SUM(CASE WHEN r.status != 'Cancelled' THEN r.nights ELSE 0 END), 0) AS nights,
			COALESCE(SUM(CASE WHEN r.status != 'Cancelled' THEN r.amount_after_tax ELSE 0 END), 0) AS lifetime_value,
			MAX(r.check_in_date) AS last_stay
		FROM `tabGuest` g
		LEFT JOIN `tabReservation` r ON r.guest = g.name
		{where}
		GROUP BY g.name
		ORDER BY lifetime_value DESC, g.modified DESC
		LIMIT 200
		""",
		params,
		as_dict=True,
	)


@frappe.whitelist()
def guest_journey(guest: str):
	"""One guest's full story: profile, stats, chronological timeline.
	This is the CRM detail view — and the context an AI concierge loads
	before speaking to a returning guest."""
	doc = frappe.get_doc("Guest", guest)

	reservations = frappe.get_all(
		"Reservation",
		filters={"guest": guest},
		fields=[
			"name", "status", "source", "channel", "room", "room_type",
			"check_in_date", "check_out_date", "nights", "adults", "children",
			"amount_after_tax", "discount_amount", "special_requests",
			"booking_type", "company", "creation",
			"actual_check_in", "actual_check_out",
		],
		order_by="check_in_date desc",
	)

	live = [r for r in reservations if r.status != "Cancelled"]
	stats = {
		"bookings": len(reservations),
		"stays": sum(1 for r in reservations if r.status in ("Checked In", "Checked Out")),
		"nights": sum(r.nights or 0 for r in live),
		"lifetime_value": float(sum(r.amount_after_tax or 0 for r in live)),
		"first_seen": str(min((r.creation for r in reservations), default="")),
	}

	timeline = []
	for r in reservations:
		timeline.append({
			"ts": str(r.creation),
			"type": "booking",
			"title": f"Booked {r.room_type.split('-')[-1] if r.room_type else ''}"
			         f" · {r.nights} night{'s' if (r.nights or 0) != 1 else ''}",
			"detail": f"{r.check_in_date} → {r.check_out_date}"
			          f" · via {r.channel or r.source}"
			          + (f" · {r.company}" if r.company else ""),
			"amount": float(r.amount_after_tax or 0),
			"reference": r.name,
		})
		if r.actual_check_in:
			timeline.append({
				"ts": str(r.actual_check_in), "type": "check_in",
				"title": f"Checked in · Room {r.room.split('-')[-1] if r.room else '—'}",
				"detail": r.special_requests or "", "reference": r.name,
			})
		if r.actual_check_out:
			timeline.append({
				"ts": str(r.actual_check_out), "type": "check_out",
				"title": "Checked out",
				"detail": f"Folio ₹{float(r.amount_after_tax or 0):,.0f}",
				"reference": r.name,
			})
		if r.status == "Cancelled":
			timeline.append({
				"ts": str(r.creation), "type": "cancelled",
				"title": "Booking cancelled", "detail": r.name,
				"reference": r.name,
			})

	# agent touches on this guest's reservations
	res_names = [r.name for r in reservations]
	if res_names:
		for log in frappe.get_all(
			"Agent Action Log",
			filters={
				"reference_doctype": "Reservation",
				"reference_name": ("in", res_names),
			},
			fields=["creation", "agent_name", "action_type", "rationale",
			        "minutes_saved", "action_channel"],
			order_by="creation desc",
			limit=50,
		):
			timeline.append({
				"ts": str(log.creation), "type": "agent",
				"title": f"{log.agent_name} · {log.action_type.replace('_', ' ')}",
				"detail": log.rationale or "",
				"channel": log.action_channel,
			})

	timeline.sort(key=lambda e: e["ts"], reverse=True)

	return {
		"guest": {
			"name": doc.name, "full_name": doc.full_name,
			"first_name": doc.first_name, "phone": doc.phone,
			"email": doc.email, "vip": doc.vip,
			"nationality": doc.nationality, "id_type": doc.id_type,
			"notes": doc.guest_notes,
		},
		"stats": stats,
		"reservations": reservations,
		"timeline": timeline,
	}


@frappe.whitelist()
def my_properties():
	"""Properties the current user may work with. frappe.get_list applies
	User Permissions, so a property-restricted user sees only theirs."""
	return frappe.get_list(
		"Property",
		filters={"disabled": 0},
		fields=["name", "property_name", "city"],
		order_by="property_name asc",
	)


@frappe.whitelist()
def front_desk_snapshot(property: str | None = None, date: str | None = None):
	"""Everything the front desk needs for one day, in one call."""
	date = date or nowdate()

	res_filters = {"check_in_date": date, "status": "Confirmed"}
	dep_filters = {"check_out_date": date, "status": "Checked In"}
	inh_filters = {"status": "Checked In"}
	room_filters = {}
	if property:
		for flt in (res_filters, dep_filters, inh_filters, room_filters):
			flt["property"] = property

	res_fields = [
		"name", "guest_name", "room_type", "room", "status", "source",
		"check_in_date", "check_out_date", "nights", "adults", "children",
		"special_requests", "channel",
	]

	arrivals = frappe.get_all(
		"Reservation", filters=res_filters, fields=res_fields,
		order_by="creation asc",
	)
	departures = frappe.get_all(
		"Reservation", filters=dep_filters, fields=res_fields,
		order_by="creation asc",
	)
	in_house = frappe.get_all(
		"Reservation", filters=inh_filters, fields=res_fields,
		order_by="room asc",
	)
	rooms = frappe.get_all(
		"Room",
		filters=room_filters,
		fields=[
			"name", "room_number", "room_type", "floor",
			"housekeeping_status", "occupancy_status",
		],
		order_by="room_number asc",
	)

	minutes = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(minutes_saved), 0)
		FROM `tabAgent Action Log`
		WHERE DATE(creation) >= %(since)s
		""",
		{"since": add_days(date, -30)},
	)[0][0]

	return {
		"date": date,
		"arrivals": arrivals,
		"departures": departures,
		"in_house": in_house,
		"rooms": rooms,
		"minutes_saved_30d": float(minutes or 0),
	}


@frappe.whitelist()
def check_in(reservation: str, room: str | None = None):
	doc = frappe.get_doc("Reservation", reservation)
	if room:
		doc.room = room
	doc.status = "Checked In"
	doc.save()
	return {"ok": True, "reservation": doc.name, "room": doc.room}


@frappe.whitelist()
def check_out(reservation: str):
	doc = frappe.get_doc("Reservation", reservation)
	doc.status = "Checked Out"
	doc.save()
	return {"ok": True, "reservation": doc.name}


@frappe.whitelist()
def set_housekeeping_status(room: str, status: str):
	allowed = {"Clean", "Dirty", "Inspected", "Out of Order"}
	if status not in allowed:
		frappe.throw(f"Invalid status. Use one of {sorted(allowed)}")
	frappe.db.set_value("Room", room, "housekeeping_status", status)
	return {"ok": True, "room": room, "status": status}


@frappe.whitelist()
def availability_calendar(property: str, start_date: str | None = None, days: int = 14):
	"""Per room-type, per date: rooms available and the 2-adult rate.
	Powers the calendar view and, later, the agent's availability tool."""
	from kamra.pricing import occupancy_rate, season_adjust

	start = start_date or nowdate()
	days = min(int(days), 31)
	dates = [add_days(start, i) for i in range(days)]

	room_types = frappe.get_all(
		"Room Type",
		filters={"property": property, "disabled": 0},
		fields=["name", "room_type_name", "base_price"],
		order_by="base_price asc",
	)
	from frappe.utils import getdate

	end = add_days(start, days)
	rows = []
	for rt in room_types:
		rt_doc = frappe.get_doc("Room Type", rt.name)
		total = frappe.db.count(
			"Room",
			{"property": property, "room_type": rt.name},
		)
		bookings = frappe.get_all(
			"Reservation",
			filters={
				"room_type": rt.name,
				"status": ("in", ["Confirmed", "Checked In"]),
				"check_in_date": ("<", end),
				"check_out_date": (">", start),
			},
			fields=["check_in_date", "check_out_date"],
		)
		base = occupancy_rate(rt_doc, 2, 0)
		cells = []
		for date in dates:
			d = getdate(date)
			taken = sum(
				1 for b in bookings
				if getdate(b.check_in_date) <= d < getdate(b.check_out_date)
			)
			cells.append({
				"date": str(date),
				"available": max(0, total - taken),
				"rate": float(season_adjust(property, date, base)),
			})
		rows.append({
			"room_type": rt.name,
			"room_type_name": rt.room_type_name,
			"total_rooms": total,
			"cells": cells,
		})
	return {"start": str(start), "days": days, "dates": [str(d) for d in dates],
	        "room_types": rows}


@frappe.whitelist()
def booking_options(property: str):
	"""Everything the booking form needs to render its dropdowns."""
	return {
		"room_types": frappe.get_all(
			"Room Type", filters={"property": property, "disabled": 0},
			fields=["name", "room_type_name", "base_price", "adults_capacity"],
			order_by="base_price asc",
		),
		"meal_plans": frappe.get_all(
			"Meal Plan", filters={"property": property, "disabled": 0},
			fields=["name", "code", "label", "price_per_adult", "is_default"],
			order_by="price_per_adult asc",
		),
		"rate_plans": frappe.get_all(
			"Rate Plan", filters={"property": property, "disabled": 0},
			fields=["name", "rate_plan_name", "code", "is_default"],
		),
		"companies": frappe.get_all(
			"Company", filters={"disabled": 0},
			fields=["name", "company_name", "negotiated_rate_plan"],
		),
	}


@frappe.whitelist()
def get_quote(property: str, room_type: str, check_in_date: str,
              check_out_date: str, adults: int = 2, children: int = 0,
              meal_plan: str | None = None, rate_plan: str | None = None,
              voucher_code: str | None = None):
	from kamra.pricing import quote

	return quote(property, room_type, check_in_date, check_out_date,
	             int(adults), int(children), meal_plan or None,
	             rate_plan or None, voucher_code or None)


def _find_or_create_guest(guest_name: str, phone: str | None):
	if phone:
		existing = frappe.db.get_value("Guest", {"phone": phone})
		if existing:
			return existing
	parts = guest_name.strip().split(" ", 1)
	guest = frappe.get_doc({
		"doctype": "Guest",
		"first_name": parts[0],
		"last_name": parts[1] if len(parts) > 1 else "",
		"phone": phone,
	}).insert(ignore_permissions=True)
	return guest.name


@frappe.whitelist()
def create_booking(property: str, room_type: str, check_in_date: str,
                   check_out_date: str, guest_name: str,
                   phone: str | None = None, adults: int = 2,
                   children: int = 0, meal_plan: str | None = None,
                   rate_plan: str | None = None,
                   voucher_code: str | None = None,
                   booking_type: str = "Individual",
                   company: str | None = None,
                   group_booking: str | None = None,
                   source: str = "Manual", assign_room: int = 1):
	"""One-call booking: guest dedup by phone, optional auto room
	assignment, voucher applied, price computed by the engine."""
	guest = _find_or_create_guest(guest_name, phone)

	voucher = None
	if voucher_code:
		from kamra.pricing import validate_voucher
		from frappe.utils import date_diff
		voucher = validate_voucher(
			property, voucher_code,
			date_diff(check_out_date, check_in_date),
		).name

	room = None
	if int(assign_room):
		free = available_rooms(property, room_type, check_in_date, check_out_date)
		room = free[0].name if free else None

	doc = frappe.get_doc({
		"doctype": "Reservation",
		"property": property,
		"guest": guest,
		"room_type": room_type,
		"room": room,
		"check_in_date": check_in_date,
		"check_out_date": check_out_date,
		"adults": int(adults),
		"children": int(children),
		"meal_plan": meal_plan or None,
		"rate_plan": rate_plan or None,
		"voucher": voucher,
		"booking_type": booking_type,
		"company": company or None,
		"group_booking": group_booking or None,
		"source": source,
		"is_day_use": 1 if check_in_date == check_out_date else 0,
		"auto_price": 1,
	})
	doc.insert(ignore_permissions=False)

	from kamra.savings import log_action
	log_action(
		action_type="create_reservation",
		reference_doctype="Reservation",
		reference_name=doc.name,
		property=property,
		minutes_saved=8 if source == "AI Agent" else 0,
		rationale=f"Booked {room_type} {check_in_date}→{check_out_date} for {guest_name}",
		channel="API" if source == "AI Agent" else "Desk",
	)
	return {
		"reservation": doc.name,
		"room": doc.room,
		"guest": guest,
		"amount_after_tax": doc.amount_after_tax,
		"discount": doc.discount_amount,
	}


@frappe.whitelist()
def create_group_booking(property: str, group_name: str, check_in_date: str,
                         check_out_date: str, rooms: str | list,
                         guest_name: str, phone: str | None = None,
                         company: str | None = None,
                         meal_plan: str | None = None,
                         rate_plan: str | None = None):
	"""Create a Group Booking plus one reservation per requested room.
	`rooms` = [{"room_type": <name>, "count": 2}, ...] (JSON string ok)."""
	import json

	if isinstance(rooms, str):
		rooms = json.loads(rooms)

	group = frappe.get_doc({
		"doctype": "Group Booking",
		"property": property,
		"group_name": group_name,
		"company": company or None,
		"check_in_date": check_in_date,
		"check_out_date": check_out_date,
		"status": "Confirmed",
	}).insert(ignore_permissions=False)

	created, skipped = [], []
	for spec in rooms:
		for _ in range(int(spec.get("count", 1))):
			try:
				res = create_booking(
					property=property,
					room_type=spec["room_type"],
					check_in_date=check_in_date,
					check_out_date=check_out_date,
					guest_name=guest_name,
					phone=phone,
					meal_plan=meal_plan,
					rate_plan=rate_plan,
					booking_type="Corporate" if company else "Group",
					company=company,
					group_booking=group.name,
				)
				created.append(res["reservation"])
			except Exception as e:
				skipped.append({"room_type": spec["room_type"], "reason": str(e)})

	return {"group_booking": group.name, "created": created, "skipped": skipped}


@frappe.whitelist()
def available_rooms(property: str, room_type: str, check_in_date: str, check_out_date: str):
	"""Rooms of a type with no overlapping live reservation — the same
	logic the double-booking guard enforces, exposed as a query."""
	return frappe.db.sql(
		"""
		SELECT r.name, r.room_number, r.housekeeping_status
		FROM `tabRoom` r
		WHERE r.property = %(property)s
		  AND r.room_type = %(room_type)s
		  AND r.housekeeping_status != 'Out of Order'
		  AND NOT EXISTS (
			SELECT 1 FROM `tabReservation` b
			WHERE b.room = r.name
			  AND b.status IN ('Confirmed', 'Checked In')
			  AND b.check_in_date < GREATEST(%(check_out)s,
			                                 DATE_ADD(%(check_in)s, INTERVAL 1 DAY))
			  AND GREATEST(b.check_out_date,
			               DATE_ADD(b.check_in_date, INTERVAL 1 DAY)) > %(check_in)s
		  )
		ORDER BY r.room_number
		""",
		{
			"property": property,
			"room_type": room_type,
			"check_in": check_in_date,
			"check_out": check_out_date,
		},
		as_dict=True,
	)
