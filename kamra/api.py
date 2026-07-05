"""Whitelisted API for the Kamra front-desk UI.

Every endpoint here is also, by design, an agent tool: the same governed
surface serves the React console today and the MCP layer next.
"""

import json

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
def setup_property(payload):
	"""One-call property onboarding — the wizard's submit button and the
	migration agent's tool. payload = {property:{property_name, city,
	gstin?, phone?, ...}, room_types:[{code,name,base_price,adults?,
	extra_adult_price?,tax_percent?}], rooms:[{room_type_code,
	numbers:["101","102"]}], meal_plans:[{code,label?,price_per_adult}]}"""
	if isinstance(payload, str):
		payload = json.loads(payload)
	frappe.only_for(("System Manager", "Hotel Admin"))

	p = payload["property"]
	if frappe.db.exists("Property", p["property_name"]):
		frappe.throw(f"Property '{p['property_name']}' already exists.")

	prop = frappe.get_doc({"doctype": "Property", **p})
	prop.insert()

	rt_by_code = {}
	for rt in payload.get("room_types", []):
		doc = frappe.get_doc({
			"doctype": "Room Type",
			"property": prop.name,
			"room_type_code": rt["code"],
			"room_type_name": rt["name"],
			"base_price": rt["base_price"],
			"base_occupancy": rt.get("base_occupancy", 2),
			"extra_adult_price": rt.get("extra_adult_price", 0),
			"adults_capacity": rt.get("adults", 2),
			"children_capacity": rt.get("children", 1),
			"tax_percent": rt.get("tax_percent", 5),
		})
		doc.insert()
		rt_by_code[rt["code"]] = doc.name

	rooms_created = 0
	for spec in payload.get("rooms", []):
		rt_name = rt_by_code.get(spec["room_type_code"])
		if not rt_name:
			frappe.throw(f"Unknown room type code {spec['room_type_code']}")
		for num in spec["numbers"]:
			frappe.get_doc({
				"doctype": "Room", "property": prop.name,
				"room_number": str(num).strip(), "room_type": rt_name,
			}).insert()
			rooms_created += 1

	for mp in payload.get("meal_plans", []):
		frappe.get_doc({
			"doctype": "Meal Plan", "property": prop.name,
			"code": mp["code"], "label": mp.get("label"),
			"price_per_adult": mp.get("price_per_adult", 0),
			"price_per_child": mp.get("price_per_child", 0),
			"is_default": mp.get("is_default", 0),
		}).insert()

	from kamra.savings import log_action
	log_action("setup_property", "Property", prop.name, prop.name,
	           minutes_saved=45,
	           rationale=f"Onboarded {prop.name}: {len(rt_by_code)} room types, "
	                     f"{rooms_created} rooms",
	           channel="API")
	return {"property": prop.name, "room_types": len(rt_by_code),
	        "rooms": rooms_created,
	        "meal_plans": len(payload.get("meal_plans", []))}


@frappe.whitelist()
def import_bookings(property: str, bookings):
	"""Bulk booking import — the switch-over tool. Each row: {guest_name,
	phone?, room_type_code, check_in, check_out, adults?, children?,
	amount_after_tax?, channel?, status?}. Rows with a fixed amount keep
	it (auto_price off); others are priced by the engine."""
	if isinstance(bookings, str):
		bookings = json.loads(bookings)
	frappe.only_for(("System Manager", "Hotel Admin"))

	created, errors = [], []
	for i, row in enumerate(bookings):
		try:
			rt = frappe.db.get_value(
				"Room Type",
				{"property": property, "room_type_code": row["room_type_code"]},
			)
			if not rt:
				raise frappe.ValidationError(
					f"unknown room type code {row['room_type_code']}")
			guest = _find_or_create_guest(row["guest_name"], row.get("phone"))
			doc = frappe.get_doc({
				"doctype": "Reservation",
				"property": property,
				"guest": guest,
				"room_type": rt,
				"check_in_date": row["check_in"],
				"check_out_date": row["check_out"],
				"adults": row.get("adults", 2),
				"children": row.get("children", 0),
				"source": "PMS",
				"channel": row.get("channel"),
				"auto_price": 0 if row.get("amount_after_tax") else 1,
			})
			if row.get("amount_after_tax"):
				doc.amount_after_tax = row["amount_after_tax"]
			doc.insert()
			if row.get("status") in ("Checked In", "Cancelled"):
				doc.status = row["status"]
				doc.save()
			created.append(doc.name)
		except Exception as e:
			errors.append({"row": i + 1,
			               "guest": row.get("guest_name"),
			               "error": str(e)[:160]})

	from kamra.savings import log_action
	log_action("import_bookings", "Property", property, property,
	           minutes_saved=2 * len(created),
	           rationale=f"Imported {len(created)} bookings "
	                     f"({len(errors)} skipped)",
	           channel="API")
	return {"created": len(created), "reservations": created[:50],
	        "errors": errors}


@frappe.whitelist()
def registration_card(reservation: str):
	"""Everything the printed GRC (guest registration card) needs."""
	res = frappe.get_doc("Reservation", reservation)
	guest = frappe.get_doc("Guest", res.guest)
	prop = frappe.get_doc("Property", res.property)
	return {
		"property": {
			"property_name": prop.property_name,
			"logo_url": prop.get("logo_url"),
			"address": ", ".join(filter(None, [
				prop.address_line, prop.city, prop.state, prop.pincode])),
			"gstin": prop.gstin, "phone": prop.phone, "email": prop.email,
			"checkin_time": str(prop.checkin_time or ""),
			"checkout_time": str(prop.checkout_time or ""),
		},
		"reservation": {
			"name": res.name, "status": res.status,
			"room": (res.room or "").split("-")[-1],
			"room_type": res.room_type.split("-")[-1],
			"check_in_date": str(res.check_in_date),
			"check_out_date": str(res.check_out_date),
			"nights": res.nights, "adults": res.adults,
			"children": res.children, "is_day_use": res.get("is_day_use"),
			"rate_total": float(res.amount_after_tax or 0),
			"advance_paid": float(res.advance_paid or 0),
			"company": res.get("company"),
			"booked_by_name": res.get("booked_by_name"),
			"source": res.source, "eta": res.get("eta"),
			"special_requests": res.special_requests,
			"precheckin_status": res.get("precheckin_status"),
		},
		"guest": {
			"full_name": guest.full_name, "phone": guest.phone,
			"email": guest.email, "nationality": guest.nationality,
			"id_type": guest.id_type, "id_number": guest.id_number,
			"address": ", ".join(filter(None, [
				guest.get("address_line"), guest.get("city")])),
		},
		"occupants": [
			{"full_name": o.full_name, "age": o.age, "gender": o.gender,
			 "nationality": o.nationality, "id_type": o.id_type,
			 "id_number": o.id_number, "phone": o.phone}
			for o in (res.get("occupants") or [])
		],
	}


@frappe.whitelist()
def cash_summary(property: str, date: str | None = None):
	"""Cashier reconciliation: what the system says was collected today,
	per payment mode — the number the drawer must match at shift close."""
	date = date or nowdate()
	rows = frappe.db.sql(
		"""
		SELECT fp.mode, COUNT(*) AS txns, COALESCE(SUM(fp.amount), 0) AS total
		FROM `tabFolio Payment` fp
		JOIN `tabFolio` f ON fp.parent = f.name
		WHERE f.property = %(property)s AND fp.posting_date = %(date)s
		GROUP BY fp.mode ORDER BY total DESC
		""",
		{"property": property, "date": date}, as_dict=True,
	)
	return {"date": date, "modes": rows,
	        "grand_total": float(sum(r.total for r in rows))}


@frappe.whitelist()
def record_advance(reservation: str, amount: float, mode: str = "UPI",
                   reference: str | None = None):
	"""Advance/deposit against a Confirmed booking — opens the folio early
	so the money sits on the stay from day one (GM gap: deposits arrive at
	booking, not at check-in)."""
	res = frappe.get_doc("Reservation", reservation)
	if res.status not in ("Confirmed", "Checked In"):
		frappe.throw("Advances only apply to active reservations.")
	from kamra.folio import _recalculate, open_folio

	folio = frappe.get_doc("Folio", open_folio(res))
	folio.append("payments", {
		"posting_date": nowdate(),
		"mode": mode,
		"amount": float(amount),
		"reference": reference or f"advance:{reservation}",
	})
	_recalculate(folio)
	folio.save(ignore_permissions=True)
	frappe.db.set_value("Reservation", reservation, "advance_paid",
	                    float(res.advance_paid or 0) + float(amount))
	from kamra.savings import log_action
	log_action("record_advance", "Folio", folio.name, res.property,
	           rationale=f"₹{float(amount):,.0f} advance on {reservation}")
	return {"folio": folio.name, "balance": folio.balance}


@frappe.whitelist()
def folio_payment_link(folio: str):
	from kamra.payments import create_payment_link
	return create_payment_link(folio)


@frappe.whitelist()
def hk_queue(property: str):
	"""The housekeeper's phone view: prioritized task queue + room board.
	Checkout cleans for rooms with an arrival today jump the queue."""
	today = nowdate()
	arriving_rooms = set(frappe.get_all(
		"Reservation",
		filters={"property": property, "status": "Confirmed",
		         "check_in_date": today, "room": ("is", "set")},
		pluck="room",
	))

	tasks = frappe.get_all(
		"Housekeeping Task",
		filters={"property": property,
		         "status": ("in", ["Pending", "In Progress"])},
		fields=["name", "room", "task_type", "priority", "status", "notes",
		        "creation"],
		order_by="creation asc",
	)
	prio_rank = {"Urgent": 0, "High": 1, "Medium": 2, "Low": 3}
	for t in tasks:
		t["arrival_today"] = t.room in arriving_rooms
		t["room_number"] = (t.room or "").split("-")[-1]
	tasks.sort(key=lambda t: (
		not t["arrival_today"],
		0 if t.task_type == "Checkout Clean" else 1,
		prio_rank.get(t.priority, 9),
		str(t.creation),
	))

	rooms = frappe.get_all(
		"Room",
		filters={"property": property},
		fields=["name", "room_number", "housekeeping_status",
		        "occupancy_status"],
		order_by="room_number asc",
	)
	for r in rooms:
		r["arrival_today"] = r.name in arriving_rooms

	return {"date": today, "tasks": tasks, "rooms": rooms}


@frappe.whitelist()
def hk_update_task(task: str, status: str):
	"""Start or complete a housekeeping task from the phone."""
	if status not in ("In Progress", "Done", "Verified"):
		frappe.throw("Status must be In Progress, Done or Verified.")
	doc = frappe.get_doc("Housekeeping Task", task)
	doc.status = status
	doc.save()
	if status in ("Done", "Verified"):
		from kamra.savings import log_action
		log_action("housekeeping_done", "Housekeeping Task", doc.name,
		           doc.property, minutes_saved=3,
		           rationale=f"{doc.task_type} for {doc.room} closed from mobile",
		           channel="API")
	return {"ok": True, "task": doc.name, "status": doc.status}


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
                     posting_date: str | None = None, is_alcohol: int = 0,
                     reservation: str | None = None):
	doc = frappe.get_doc("Folio", folio)
	if doc.status == "Closed":
		frappe.throw("Folio is closed.")
	if int(is_alcohol or 0) and doc.folio_type in ("Company", "Group"):
		frappe.throw("Alcohol cannot be billed to a company folio — "
		             "post it to the guest folio.")
	doc.append("charges", {
		"posting_date": posting_date or nowdate(),
		"charge_type": charge_type,
		"reservation": reservation or doc.reservation,
		"description": description,
		"qty": 1,
		"rate": float(amount),
		"amount": float(amount),
		"gst_rate": float(gst_rate),
		"is_alcohol": 1 if int(is_alcohol or 0) else 0,
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
def post_stay_charge(reservation: str, charge_type: str, description: str,
                     amount: float, gst_rate: float = 0, is_alcohol: int = 0):
	"""Post a charge to a stay letting the billing rules pick the folio —
	corporate room/meals land on the Company folio, alcohol and anything
	unruled lands on the guest. The agent-facing way to post charges."""
	res = frappe.get_doc("Reservation", reservation)
	if res.status not in ("Confirmed", "Checked In", "Checked Out"):
		frappe.throw("Reservation is not active.")
	from kamra.folio import target_folio
	is_alcohol = 1 if int(is_alcohol or 0) else 0
	folio_name = target_folio(res, charge_type, is_alcohol)
	out = add_folio_charge(folio_name, charge_type, description, amount,
	                       gst_rate, is_alcohol=is_alcohol,
	                       reservation=res.name)
	return {"folio": folio_name, "folio_type": out.get("folio_type"),
	        "balance": out.get("balance")}


@frappe.whitelist()
def set_billing_rules(company: str, rules):
	"""Replace a company's billing rules. rules = [{charge_type, pay_by}]."""
	if isinstance(rules, str):
		rules = frappe.parse_json(rules)
	doc = frappe.get_doc("Company", company)
	doc.set("billing_rules", [])
	for r in rules or []:
		doc.append("billing_rules", {
			"charge_type": r.get("charge_type"),
			"pay_by": r.get("pay_by") or "Company",
		})
	doc.save()
	return {"company": company, "rules": len(doc.billing_rules)}


@frappe.whitelist()
def get_billing_rules(company: str):
	doc = frappe.get_doc("Company", company)
	return [{"charge_type": r.charge_type, "pay_by": r.pay_by}
	        for r in (doc.get("billing_rules") or [])]


@frappe.whitelist()
def update_occupants(reservation: str, occupants):
	"""Replace the stay's occupant register.
	occupants = [{full_name, age, gender, nationality, id_type, id_number, phone}]"""
	if isinstance(occupants, str):
		occupants = frappe.parse_json(occupants)
	doc = frappe.get_doc("Reservation", reservation)
	doc.set("occupants", [])
	for o in occupants or []:
		if not (o.get("full_name") or "").strip():
			continue
		doc.append("occupants", {
			"full_name": o["full_name"].strip(),
			"age": o.get("age") or None,
			"gender": o.get("gender") or "",
			"nationality": o.get("nationality") or "Indian",
			"id_type": o.get("id_type") or "",
			"id_number": (o.get("id_number") or "").strip(),
			"phone": o.get("phone") or "",
		})
	doc.save()
	return {"reservation": reservation, "occupants": len(doc.occupants)}


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
def transfer_folio_charges(from_folio: str, charge_rows, to_folio: str):
	"""Bulk move: several charge lines to another folio of the stay."""
	if isinstance(charge_rows, str):
		charge_rows = frappe.parse_json(charge_rows)
	from kamra.folio import transfer_charges
	transfer_charges(from_folio, charge_rows, to_folio)
	from kamra.savings import log_action
	log_action("transfer_charges", "Folio", to_folio,
	           rationale=f"Moved {len(charge_rows)} charges "
	                     f"{from_folio} → {to_folio}")
	return {"ok": True, "moved": len(charge_rows)}


@frappe.whitelist()
def split_folio_charge(from_folio: str, charge_row: str, to_folio: str,
                       percent: float | None = None,
                       amount: float | None = None):
	"""Split one charge line between two folios — by percent or amount."""
	from kamra.folio import split_charge
	out = split_charge(from_folio, charge_row, to_folio,
	                   percent=float(percent) if percent else None,
	                   amount=float(amount) if amount else None)
	from kamra.savings import log_action
	log_action("split_charge", "Folio", to_folio,
	           rationale=f"Split ₹{out['moved']:,.2f} of {charge_row} "
	                     f"{from_folio} → {to_folio}")
	return out


_FOLIO_LIST_FIELDS = ["name", "folio_type", "status", "invoice_number",
                      "grand_total", "payments_total", "balance"]


@frappe.whitelist()
def reservation_folios(reservation: str):
	"""All folios of a stay (guest + splits) with balances — plus the
	group master folio when the stay belongs to a group, so charges can
	be moved between a guest's bill and the company's consolidated one."""
	rows = frappe.get_all(
		"Folio",
		filters={"reservation": reservation},
		fields=_FOLIO_LIST_FIELDS,
		order_by="creation asc",
	)
	group = frappe.db.get_value("Reservation", reservation, "group_booking")
	if group:
		seen = {r.name for r in rows}
		rows += [m for m in frappe.get_all(
			"Folio",
			filters={"group_booking": group, "folio_type": "Group"},
			fields=_FOLIO_LIST_FIELDS,
		) if m.name not in seen]
	return rows


@frappe.whitelist()
def group_master_folio(group_booking: str):
	"""Get-or-create the group's consolidated company folio."""
	from kamra.folio import open_group_folio
	return {"folio": open_group_folio(group_booking)}


@frappe.whitelist()
def group_folios(group_booking: str):
	"""The whole group's billing picture: the master folio plus every
	member reservation's folios, with balances."""
	master = frappe.get_all(
		"Folio", filters={"group_booking": group_booking,
		                  "folio_type": "Group"},
		fields=_FOLIO_LIST_FIELDS)
	members = frappe.get_all(
		"Reservation",
		filters={"group_booking": group_booking},
		fields=["name", "guest_name", "room", "status"],
		order_by="creation asc")
	for m in members:
		m["folios"] = [f for f in frappe.get_all(
			"Folio", filters={"reservation": m.name},
			fields=_FOLIO_LIST_FIELDS) if f.folio_type != "Group"]
	return {"master": master[0] if master else None, "members": members}


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

	# B2B: corporate bookings carry the buyer's GSTIN on the invoice.
	# A group master folio bills to the GROUP's company.
	bill_to = None
	bill_company = res.company
	if doc.folio_type == "Group" and doc.get("group_booking"):
		bill_company = frappe.db.get_value(
			"Group Booking", doc.group_booking, "company") or bill_company
	if bill_company:
		company = frappe.db.get_value(
			"Company", bill_company, ["company_name", "gstin"], as_dict=True)
		if company:
			bill_to = {"name": company.company_name, "gstin": company.gstin}

	return {
		"folio": doc.as_dict(),
		"bill_to": bill_to,
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
			"group_booking": res.get("group_booking"),
			"booked_by_name": res.get("booked_by_name"),
			"booked_by_phone": res.get("booked_by_phone"),
			"contact_preference": res.get("contact_preference"),
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
def guest_search(q: str):
	"""Typeahead for attaching a booking to an existing profile."""
	q = (q or "").strip()
	if len(q) < 2:
		return []
	return frappe.db.sql(
		"""
		SELECT g.name, g.full_name, g.phone, g.email, g.vip, g.blacklisted,
		       COUNT(r.name) AS stays, MAX(r.check_in_date) AS last_stay
		FROM `tabGuest` g
		LEFT JOIN `tabReservation` r
		       ON r.guest = g.name AND r.status IN ('Checked In', 'Checked Out')
		WHERE g.full_name LIKE %(q)s OR g.phone LIKE %(q)s
		GROUP BY g.name
		ORDER BY stays DESC, g.modified DESC
		LIMIT 8
		""",
		{"q": f"%{q}%"}, as_dict=True,
	)


_GUEST_LINKS = [  # every doctype that points at a Guest
	("Reservation", "guest"), ("Folio", "guest"),
	("Service Ticket", "guest"), ("Lost And Found Item", "guest"),
]


@frappe.whitelist()
def merge_guests(source: str, target: str):
	"""Merge a duplicate profile into the surviving one: every linked
	document is repointed, missing contact fields are copied over, and
	the duplicate is deleted. Money is untouched — folios keep their
	lines and totals."""
	if source == target:
		frappe.throw("Pick two different profiles to merge.")
	src = frappe.get_doc("Guest", source)
	dst = frappe.get_doc("Guest", target)

	moved = {}
	for doctype, field in _GUEST_LINKS:
		rows = frappe.get_all(doctype, filters={field: source}, pluck="name")
		for name in rows:
			frappe.db.set_value(doctype, name, field, target,
			                    update_modified=False)
		if rows:
			moved[doctype] = len(rows)
	# denormalized guest_name on stays and bills follows the survivor
	for doctype in ("Reservation", "Folio"):
		frappe.db.sql(
			f"UPDATE `tab{doctype}` SET guest_name = %s WHERE guest = %s",
			(dst.full_name, target))

	# fill the survivor's blanks from the duplicate; strictest flags win
	for field in ("phone", "email", "id_type", "id_number", "nationality",
	              "address_line", "city", "guest_notes"):
		if not dst.get(field) and src.get(field):
			dst.set(field, src.get(field))
	if src.vip:
		dst.vip = 1
	if src.blacklisted:
		dst.blacklisted = 1
		dst.blacklist_reason = dst.blacklist_reason or src.blacklist_reason
	dst.save(ignore_permissions=True)
	frappe.delete_doc("Guest", source, ignore_permissions=True)

	from kamra.savings import log_action
	log_action("merge_guests", "Guest", target,
	           rationale=f"Merged {source} into {target}: "
	                     + ", ".join(f"{k}×{v}" for k, v in moved.items()))
	return {"target": target, "moved": moved}


@frappe.whitelist()
def anonymize_guest(guest: str):
	"""Right-to-erasure: strip everything that identifies the person while
	keeping stays and bills intact for the books. Irreversible."""
	doc = frappe.get_doc("Guest", guest)
	alias = f"Guest {frappe.generate_hash(length=6).upper()}"
	doc.update({
		"first_name": alias, "last_name": "", "full_name": alias,
		"phone": "", "email": "", "id_type": "", "id_number": "",
		"nationality": "", "address_line": "", "city": "",
		"guest_notes": "Profile anonymized on request.", "vip": 0,
	})
	doc.save(ignore_permissions=True)
	for doctype in ("Reservation", "Folio"):
		frappe.db.sql(
			f"UPDATE `tab{doctype}` SET guest_name = %s WHERE guest = %s",
			(alias, guest))
	# the stay register keeps masked IDs only
	for r in frappe.get_all("Reservation", filters={"guest": guest},
	                        pluck="name"):
		res = frappe.get_doc("Reservation", r)
		for o in res.get("occupants") or []:
			if o.id_number:
				frappe.db.set_value("Stay Occupant", o.name, "id_number",
				                    _mask_id(o.id_number),
				                    update_modified=False)
		if res.get("booked_by_phone"):
			frappe.db.set_value("Reservation", r, "booked_by_phone", "",
			                    update_modified=False)

	from kamra.savings import log_action
	log_action("anonymize_guest", "Guest", guest,
	           rationale="PII erased; financial records preserved")
	return {"guest": guest, "alias": alias}


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
			"id_number": doc.id_number,
			"blacklisted": doc.get("blacklisted"),
			"blacklist_reason": doc.get("blacklist_reason"),
			"address": ", ".join(filter(None, [
				doc.get("address_line"), doc.get("city")])),
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
		"special_requests", "channel", "precheckin_status", "eta",
		"precheckin_token", "booked_by_name", "booked_by_phone",
		"booker_relation", "contact_preference", "company",
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

	# payment state per stay, straight off the folios (the group master is
	# the company's bill, not this guest's — excluded from the chip)
	all_rows = arrivals + departures + in_house
	names = list({r.name for r in all_rows})
	paid_map = {}
	if names:
		for row in frappe.db.sql(
			"""
			SELECT reservation,
			       COALESCE(SUM(payments_total), 0) AS paid,
			       COALESCE(SUM(balance), 0) AS due
			FROM `tabFolio`
			WHERE reservation IN %(names)s AND folio_type != 'Group'
			GROUP BY reservation
			""",
			{"names": names}, as_dict=True,
		):
			paid_map[row.reservation] = row
	amounts = {r.name: r for r in frappe.get_all(
		"Reservation", filters={"name": ("in", names or [""])},
		fields=["name", "amount_after_tax", "advance_paid"])}
	for r in all_rows:
		hit = paid_map.get(r.name)
		amt = amounts.get(r.name)
		if hit:
			r["paid_total"] = float(hit.paid)
			r["balance_due"] = float(hit.due)
		else:
			# no folio yet — the booking-time advance is all we know
			adv = float(amt.advance_paid or 0) if amt else 0
			total = float(amt.amount_after_tax or 0) if amt else 0
			r["paid_total"] = adv
			r["balance_due"] = max(0.0, total - adv)
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


def _mask_id(value: str | None) -> str | None:
	"""'987654321012' → '••••••••1012' — enough for the register audit
	trail without holding the full number."""
	if not value or len(value) <= 4 or value.startswith("•"):
		return value
	return "•" * (len(value) - 4) + value[-4:]


def _scrub_stay_ids(res):
	"""Verify & Discard retention: after checkout, keep only the last 4
	digits of every ID collected for the stay."""
	if frappe.db.get_value("Property", res.property, "id_retention") \
			!= "Verify & Discard":
		return
	for o in res.get("occupants") or []:
		if o.id_number:
			frappe.db.set_value("Stay Occupant", o.name, "id_number",
			                    _mask_id(o.id_number), update_modified=False)
	guest_id = frappe.db.get_value("Guest", res.guest, "id_number")
	if guest_id:
		frappe.db.set_value("Guest", res.guest, "id_number",
		                    _mask_id(guest_id), update_modified=False)


def _cancellation_terms(res):
	"""Policy + fee estimate for a reservation, before anyone commits."""
	from frappe.utils import date_diff
	from kamra.folio import policy_fee

	policy = frappe.db.get_value(
		"Property", res.property,
		["free_cancel_days", "cancellation_fee"], as_dict=True)
	days_before = date_diff(res.check_in_date, nowdate())
	inside_window = days_before < int(policy.free_cancel_days or 0)
	basis = policy.cancellation_fee or "None"
	fee = policy_fee(res, basis) if inside_window and basis != "None" else 0.0
	return {
		"days_before_arrival": days_before,
		"free_cancel_days": int(policy.free_cancel_days or 0),
		"inside_window": inside_window,
		"fee_basis": basis,
		"estimated_fee": fee,
	}


@frappe.whitelist()
def cancellation_preview(reservation: str):
	"""What cancelling right now would cost — shown before confirming."""
	res = frappe.get_doc("Reservation", reservation)
	return _cancellation_terms(res)


CANCEL_REASONS = ["Guest request", "Change of plans", "Duplicate booking",
                  "Payment failed", "Weather / travel disruption",
                  "Booked elsewhere", "Other"]


@frappe.whitelist()
def cancel_reservation(reservation: str, reason: str = "Guest request",
                       note: str | None = None, waive_fee: int = 0):
	"""Cancel a booking, applying the property's cancellation policy:
	free outside the window, else the configured fee lands on the folio.
	Issues a cancellation number the guest can hold on to. Pass
	waive_fee=1 to cancel graciously (logged)."""
	from frappe.model.naming import make_autoname

	res = frappe.get_doc("Reservation", reservation)
	if res.status != "Confirmed":
		frappe.throw("Only confirmed bookings can be cancelled — "
		             "checked-in stays check out.")
	if reason not in CANCEL_REASONS:
		reason = "Other"
	terms = _cancellation_terms(res)

	fee = 0.0
	if terms["inside_window"] and not int(waive_fee or 0) \
			and terms["fee_basis"] != "None":
		from kamra.folio import post_policy_fee
		fee = post_policy_fee(
			res, terms["fee_basis"],
			f"Cancellation fee ({terms['fee_basis']})")

	res.status = "Cancelled"
	res.cancellation_reason = reason
	res.cancellation_note = note or ""
	res.cancellation_number = make_autoname("CXL-.YYYY.-.#####")
	res.cancellation_fee = fee
	res.cancelled_on = frappe.utils.now_datetime()
	frappe.flags.kamra_cancelling = True
	try:
		res.save()
	finally:
		frappe.flags.kamra_cancelling = False

	from kamra.savings import log_action
	log_action("cancel_reservation", "Reservation", res.name, res.property,
	           rationale=f"{res.cancellation_number} · {reason} · "
	                     f"{terms['days_before_arrival']}d before arrival — "
	                     + (f"fee ₹{fee:,.0f}" if fee else
	                        ("fee waived" if int(waive_fee or 0)
	                         else "no fee (outside window)")))
	return {"reservation": res.name,
	        "cancellation_number": res.cancellation_number,
	        "fee": fee, "waived": bool(int(waive_fee or 0))}


@frappe.whitelist()
def cancellation_letter(reservation: str):
	"""Everything the printable cancellation confirmation needs."""
	res = frappe.get_doc("Reservation", reservation)
	if res.status != "Cancelled":
		frappe.throw("This reservation is not cancelled.")
	prop = frappe.get_doc("Property", res.property)
	guest = frappe.get_doc("Guest", res.guest)
	return {
		"property": {
			"property_name": prop.property_name,
			"logo_url": prop.get("logo_url"),
			"address": ", ".join(filter(None, [
				prop.address_line, prop.city, prop.state, prop.pincode])),
			"phone": prop.phone, "email": prop.email,
		},
		"guest": {"full_name": guest.full_name, "phone": guest.phone,
		          "email": guest.email},
		"reservation": {
			"name": res.name,
			"room_type": (res.room_type or "").split("-")[-1],
			"check_in_date": str(res.check_in_date),
			"check_out_date": str(res.check_out_date),
			"nights": res.nights,
			"amount_after_tax": float(res.amount_after_tax or 0),
			"cancellation_number": res.cancellation_number,
			"cancellation_reason": res.cancellation_reason,
			"cancellation_fee": float(res.cancellation_fee or 0),
			"cancelled_on": str(res.cancelled_on or ""),
			"advance_paid": float(res.advance_paid or 0),
		},
	}


@frappe.whitelist()
def check_out(reservation: str):
	doc = frappe.get_doc("Reservation", reservation)
	doc.status = "Checked Out"
	doc.save()
	_scrub_stay_ids(doc)
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
def tape_chart(property: str, start_date: str | None = None, days: int = 14):
	"""Rooms × dates grid with reservation bars — the front desk's home."""
	from frappe.utils import getdate

	start = getdate(start_date or nowdate())
	days = min(int(days), 31)
	end = add_days(start, days)

	rooms = frappe.get_all(
		"Room", filters={"property": property},
		fields=["name", "room_number", "room_type", "housekeeping_status",
		        "occupancy_status"],
		order_by="room_type asc, room_number asc",
	)
	bookings = frappe.get_all(
		"Reservation",
		filters={
			"property": property, "room": ("is", "set"),
			"status": ("in", ["Confirmed", "Checked In"]),
			"check_in_date": ("<", end), "check_out_date": (">", start),
		},
		fields=["name", "room", "guest_name", "status", "check_in_date",
		        "check_out_date", "is_day_use", "adults",
		        "precheckin_status", "source"],
	)
	by_room = {}
	for b in bookings:
		by_room.setdefault(b.room, []).append(b)
	for r in rooms:
		r["bookings"] = by_room.get(r.name, [])
	return {
		"start": str(start), "days": days,
		"dates": [str(add_days(start, i)) for i in range(days)],
		"rooms": rooms,
	}


@frappe.whitelist()
def move_reservation(reservation: str, new_room: str):
	"""Room move — mid-stay or before arrival. Overlap guard re-runs."""
	doc = frappe.get_doc("Reservation", reservation)
	if doc.status not in ("Confirmed", "Checked In"):
		frappe.throw("Only active reservations can be moved.")
	old_room = doc.room
	doc.room = new_room
	doc.save()
	if doc.status == "Checked In" and old_room and old_room != new_room:
		frappe.db.set_value("Room", old_room,
		                    {"occupancy_status": "Vacant",
		                     "housekeeping_status": "Dirty"})
		frappe.db.set_value("Room", new_room, "occupancy_status", "Occupied")
	from kamra.savings import log_action
	log_action("room_move", "Reservation", doc.name, doc.property,
	           rationale=f"{old_room} → {new_room}")
	return {"ok": True, "room": doc.room}


@frappe.whitelist()
def amend_stay(reservation: str, check_in_date: str, check_out_date: str):
	"""Extend / shorten a stay. Re-prices when auto_price is on; the
	overlap guard validates the new window."""
	doc = frappe.get_doc("Reservation", reservation)
	if doc.status not in ("Confirmed", "Checked In"):
		frappe.throw("Only active reservations can be amended.")
	old = f"{doc.check_in_date}→{doc.check_out_date}"
	doc.check_in_date = check_in_date
	doc.check_out_date = check_out_date
	doc.save()
	from kamra.savings import log_action
	log_action("amend_stay", "Reservation", doc.name, doc.property,
	           rationale=f"{old} → {check_in_date}→{check_out_date}; "
	                     f"new total ₹{doc.amount_after_tax or 0:,.0f}")
	return {"ok": True, "nights": doc.nights,
	        "amount_after_tax": doc.amount_after_tax}


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
		"travel_agents": frappe.get_all(
			"Travel Agent", filters={"disabled": 0},
			fields=["name", "agent_name", "commission_pct"],
			order_by="agent_name asc",
		),
		"experiences": frappe.get_all(
			"Experience", filters={"property": property, "disabled": 0},
			fields=["name", "experience_name", "category", "price",
			        "gst_rate"],
			order_by="price asc",
		),
		"property": frappe.db.get_value(
			"Property", property,
			["sell_message", "free_cancel_days", "cancellation_fee",
			 "no_show_charge", "deposit_pct"],
			as_dict=True,
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
                   source: str = "Manual", assign_room: int = 1,
                   travel_agent: str | None = None,
                   booked_by_name: str | None = None,
                   booked_by_phone: str | None = None,
                   booker_relation: str | None = None,
                   contact_preference: str | None = None,
                   guest: str | None = None,
                   addons=None):
	"""One-call booking: attach to an existing guest profile when given,
	else dedup by phone / create one. Optional auto room assignment,
	voucher applied, price computed by the engine."""
	if guest:
		if not frappe.db.exists("Guest", guest):
			frappe.throw(f"Guest profile {guest} not found.")
	else:
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
		"travel_agent": travel_agent or None,
		"booked_by_name": booked_by_name or None,
		"booked_by_phone": booked_by_phone or None,
		"booker_relation": booker_relation or None,
		"contact_preference": contact_preference
			or ("Booker" if booked_by_name else "Guest"),
		"auto_price": 1,
	})

	# extras chosen at booking — priced from the Experience, posted to the
	# folio the moment it opens
	if isinstance(addons, str):
		addons = frappe.parse_json(addons)
	for a in addons or []:
		exp = frappe.db.get_value(
			"Experience", a.get("experience"),
			["experience_name", "price", "gst_rate"], as_dict=True)
		if not exp:
			continue
		qty = float(a.get("qty") or 1)
		doc.append("addons", {
			"experience": a["experience"],
			"description": exp.experience_name,
			"qty": qty,
			"rate": float(exp.price or 0),
			"amount": qty * float(exp.price or 0),
			"gst_rate": float(exp.gst_rate or 0),
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
					guest_name=spec.get("guest_name") or guest_name,
					phone=spec.get("phone") or phone,
					adults=int(spec.get("adults", 2)),
					children=int(spec.get("children", 0)),
					meal_plan=spec.get("meal_plan") or meal_plan,
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
