"""Whitelisted API for the Kamra front-desk UI.

Every endpoint here is also, by design, an agent tool: the same governed
surface serves the React console today and the MCP layer next.
"""

import json
import math

import frappe
from frappe import _
from frappe.utils import add_days, cint, get_datetime, getdate, now_datetime, nowdate

from kamra.authz import act_as, require_it_admin, require_roles
from kamra.install import AGENT_EMAIL

# The apps a property actually runs. The launcher and the sidebar read
# this so a serviced-apartment operator never sees an empty restaurant.
ALL_MODULES = ("front-desk", "housekeeping", "operations", "fnb", "events",
               "revenue", "finance", "booking-engine", "admin")


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Revenue Manager", "Housekeeping",
               "Housekeeping Supervisor", "Kamra Agent", "Night Auditor")
def enabled_modules(property: str) -> list:
	"""Which parts of Kamra this property runs. Empty setting = all of
	them, so an existing property keeps working untouched."""
	raw = frappe.db.get_value("Property", property, "enabled_modules")
	picked = [m.strip() for m in (raw or "").split(",") if m.strip()]
	return picked or list(ALL_MODULES)


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin")
def set_enabled_modules(property: str, modules) -> dict:
	"""Turn parts of the product on or off for one property."""
	if isinstance(modules, str):
		modules = [m.strip() for m in modules.split(",")]
	unknown = [m for m in modules if m and m not in ALL_MODULES]
	if unknown:
		frappe.throw(_("Unknown module(s): {0}").format(", ".join(unknown)))
	# Front desk is the product. Admin holds Settings, Rooms and Room
	# Types - switch it off and you lose the only screen that could switch
	# it back on, and the ability to add a room at all. Neither is optional.
	picked = sorted({m for m in modules if m} | {"front-desk", "admin"})
	frappe.db.set_value("Property", property, "enabled_modules",
	                    ",".join(picked))
	return {"ok": True, "modules": picked}


@frappe.whitelist(allow_guest=True)
def whoami():
	"""Current user + roles - drives which modules the UI shows.

	allow_guest so the SPA's initial "am I logged in?" probe returns
	{user: "Guest"} cleanly instead of a 403 in the console.
	"""
	user = frappe.session.user
	return {
		"user": user,
		"full_name": frappe.db.get_value("User", user, "full_name") or user,
		"roles": frappe.get_roles(user),
	}


@frappe.whitelist()
@require_it_admin
def developer_info():
	"""REST base URL + whether the current user already has an API key.

	Drives the on-site Developers page. The secret itself is never returned
	here - Frappe stores it hashed; it's only shown once, at generation time.
	"""
	user = frappe.session.user
	return {
		"user": user,
		"has_key": bool(frappe.db.get_value("User", user, "api_key")),
		"base_url": frappe.utils.get_url(),
	}


@frappe.whitelist(methods=["POST"])
@require_it_admin
def generate_api_key():
	"""Generate (or rotate) the current user's REST API key + secret.

	Self-service: acts only on the signed-in user, so any authenticated staff
	member can mint a key scoped to their own roles. The secret is returned
	once here and stored hashed thereafter.
	"""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw("Sign in to generate an API key.")
	doc = frappe.get_doc("User", user)
	api_secret = frappe.generate_hash(length=15)
	if not doc.api_key:
		doc.api_key = frappe.generate_hash(length=15)
	doc.api_secret = api_secret
	doc.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional
	return {"api_key": doc.api_key, "api_secret": api_secret}


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent", "Hotel Admin", "System Manager")
def upload_room_image():
	"""Uploads an image file for room types / properties to public files."""
	req = getattr(frappe.local, "request", None)
	files = getattr(req, "files", {}) if req else {}
	if "file" not in files:
		frappe.throw("No file uploaded.")
	file = files["file"]
	filename = file.filename
	content = file.stream.read()

	from frappe.utils.file_manager import save_file
	saved = save_file(filename, content, None, None, is_private=0)
	return {"file_url": saved.file_url}


def _assert_within_guardrails(guardrails, room_type, rate: float,
                              start_date, end_date) -> list:
	"""Refuse a rate that breaks the owner's rails on any day in the range,
	and return the rails that were actually applied.

	Rails can be scoped to days of the week, so a property can hold a hard
	weekend floor while still allowing a midweek discount. The most specific
	rail wins for each day: room-type + days, then room-type, then
	property-wide + days, then property-wide.
	"""
	applied: list = []
	if not guardrails:
		return applied
	from frappe.utils import add_days, date_diff

	from kamra.pricing import days_cover

	def _rank(g, day_abbr):
		if not days_cover(g.days_of_week, day_abbr):
			return None
		return (1 if g.room_type == room_type else 0,
		        1 if g.days_of_week else 0)

	span = min(int(date_diff(end_date, start_date)) + 1, 92)
	checked: set = set()
	for i in range(span):
		day = add_days(start_date, i)
		day_abbr = getdate(day).strftime("%a").lower()
		if day_abbr in checked:
			continue  # the rails repeat weekly; one check per weekday is enough
		checked.add(day_abbr)
		ranked = [(r, g) for g in guardrails
		          if (r := _rank(g, day_abbr)) is not None]
		if not ranked:
			continue
		rail = max(ranked, key=lambda x: x[0])[1]
		if rail.name not in applied:
			applied.append(rail.name)
		scope = f" on {day_abbr.title()}" if rail.days_of_week else ""
		if rate < float(rail.floor_price):
			frappe.throw(
				f"Blocked by guardrail {rail.name}: \u20b9{rate:,.0f} is below "
				f"the floor of \u20b9{float(rail.floor_price):,.0f}{scope}."
			)
		if rate > float(rail.ceiling_price):
			frappe.throw(
				f"Blocked by guardrail {rail.name}: \u20b9{rate:,.0f} is above "
				f"the ceiling of \u20b9{float(rail.ceiling_price):,.0f}{scope}."
			)
	return applied


@frappe.whitelist()
@require_roles("Revenue Manager", "Kamra Agent")
def set_room_rate(property: str, room_type: str, start_date: str,
                  end_date: str, rate: float, reason: str = "",
                  agent: str | None = None, days_of_week: list | str | None = None):
	"""Set the nightly rate for a room type over a date range - bounded by
	the owner's Rate Guardrails (PRD FR-30). This is the Revenue Agent's
	write tool: it can never price outside the rails.

	Guardrails still clamp the rate; the change is recorded in the action log.
	"""
	from kamra.booking_refs import resolve_room_type
	room_type = resolve_room_type(property, room_type)
	rate = float(rate)

	guardrails = frappe.get_all(
		"Rate Guardrail",
		filters={"property": property, "disabled": 0,
		         "room_type": ("in", [room_type, "", None])},
		fields=["name", "room_type", "floor_price", "ceiling_price",
		        "days_of_week"],
	)
	rails_applied = _assert_within_guardrails(guardrails, room_type, rate,
	                                          start_date, end_date)

	# the hurdle is the DYNAMIC floor: when demand tiers are active for any
	# date in range, a manual rate can't undercut the minimum sell rate
	from frappe.utils import add_days, date_diff

	# Validate hurdle rates for each day in range
	from kamra.pricing import demand_tier
	for i in range(min(int(date_diff(end_date, start_date)) + 1, 92)):
		day = add_days(start_date, i)
		tier = demand_tier(property, room_type, day)
		if tier and tier["min_rate"] and rate < tier["min_rate"]:
			frappe.throw(
				f"Blocked by the hurdle rate: occupancy for {day} is "
				f"{tier['occupancy']:.0f}%, so the minimum sell rate is "
				f"₹{tier['min_rate']:,.0f} - ₹{rate:,.0f} undercuts it."
			)

	from frappe.utils import date_diff

	season_name_suffix = f" {days_of_week}" if days_of_week else ""
	days_str = ",".join(days_of_week) if isinstance(days_of_week, list) else days_of_week

	season = frappe.get_doc({
		"doctype": "Season",
		"property": property,
		"season_name": f"Rate set {room_type.split('-')[-1]} {start_date}→{end_date}{season_name_suffix}",
		# scope it to the room type the caller priced - a blank room_type
		# would set this rate for every room type in the house
		"room_type": room_type,
		"start_date": start_date,
		"end_date": end_date,
		"adjustment_type": "Absolute",
		"adjustment_value": rate,
		"priority": 100,
		"days_of_week": days_str
	})
	season.insert()
	from kamra.savings import log_action
	log_action("set_room_rate", "Season", season.name, property,
	           minutes_saved=6, rationale=reason or (
	               f"Set {room_type.split('-')[-1]} rate ₹{rate:,.0f} "
	               f"for {start_date}→{end_date}"))
	return {
		"season": season.name, "rate": rate,
		"guardrail_checked": rails_applied[0] if rails_applied else None,
		"guardrails_checked": rails_applied,
	}


@frappe.whitelist()
@require_roles()
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
		"Night Audit Run", {"property": property, "business_date": yesterday,
		                    "status": ("!=", "Draft")},
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


def _apply_country_defaults(p: dict):
	"""The country picks the pack; the pack knows the currency and clock.
	Explicit values from the caller always win."""
	country = (p.get("country") or "").strip()
	if not country:
		return
	p["country"] = country
	from kamra.localization import pack_for_country
	pack = pack_for_country(country)
	cur = p.get("currency") or getattr(pack, "DEFAULT_CURRENCY", None)
	if cur and frappe.db.exists("Currency", cur):
		p["currency"] = cur
		frappe.db.set_value("Currency", cur, "enabled", 1)
	elif p.get("currency"):
		frappe.throw(f"Unknown currency {p['currency']}.")
	if not p.get("timezone") and getattr(pack, "DEFAULT_TIMEZONE", None):
		p["timezone"] = pack.DEFAULT_TIMEZONE
	# the levy's name follows the country; its % is the operator's to set
	if not p.get("room_levy_label") and getattr(pack, "ROOM_LEVY_LABEL", None):
		p["room_levy_label"] = pack.ROOM_LEVY_LABEL


def default_floor(room_number: str) -> str:
	"""Best-guess floor for a room the wizard creates without one.

	Hotel numbering puts the floor before the last two digits (101 -> 1,
	1205 -> 12). Floor 0 and anything that isn't hotel numbering (1, G01,
	"Room 3", "Villa A") is a small place's ground floor.
	"""
	n = str(room_number or "").strip()
	if n.isdigit() and len(n) >= 3 and int(n[:-2]):
		return str(int(n[:-2]))
	return "Ground"


@frappe.whitelist()
def setup_property(payload):
	"""One-call property onboarding - the wizard's submit button and the
	migration agent's tool. payload = {property:{property_name, city,
	gstin?, phone?, ...}, room_types:[{code,name,base_price,adults?,
	extra_adult_price?,tax_percent?}], rooms:[{room_type_code,
	numbers:["101","102"]}], meal_plans:[{code,label?,price_per_adult}]}"""
	if isinstance(payload, str):
		payload = json.loads(payload)
	frappe.only_for(("System Manager", "Hotel Admin"))

	p = payload["property"]
	from kamra.property_presets import apply_kind_defaults, skip_meal_plans
	apply_kind_defaults(p)
	_apply_country_defaults(p)
	# Inventory topology: rooms (hotel / multi-unit) or whole_property (entire place).
	topology = (payload.get("inventory_topology") or "rooms").strip()
	if topology not in ("rooms", "whole_property"):
		frappe.throw(f"Unknown inventory_topology '{topology}'")

	if frappe.db.exists("Property", p["property_name"]):
		frappe.throw(f"Property '{p['property_name']}' already exists.")

	prop = frappe.get_doc({"doctype": "Property", **p})
	prop.insert()
	# property scope is enforced: a creator pinned to their first property
	# must not lose sight of the one they just added
	from kamra.authz import restricted_properties
	if restricted_properties() is not None:
		frappe.get_doc({
			"doctype": "User Permission", "user": frappe.session.user,
			"allow": "Property", "for_value": prop.name,
			"apply_to_all_doctypes": 1,
		}).insert(ignore_permissions=True)
	try:
		from kamra.property_presets import KIND_STR, normalize_kind
		from kamra.turnover import ensure_default_profile
		ensure_default_profile(
			prop.name,
			str_defaults=normalize_kind(prop.property_kind) == KIND_STR,
		)
	except Exception:
		frappe.log_error(title="Turnover Profile ensure after setup_property")

	# What the owner switched on (guided setup). Empty keeps the default:
	# every module, exactly as before.
	picked_modules = payload.get("modules")
	if picked_modules:
		unknown = [m for m in picked_modules if m not in ALL_MODULES]
		if unknown:
			frappe.throw(_("Unknown module(s): {0}").format(", ".join(unknown)))
		prop.db_set("enabled_modules", ",".join(
			sorted(set(picked_modules) | {"front-desk", "admin"})))
	wants = [w for w in (payload.get("wants") or []) if w in ("channel-manager", "whatsapp")]
	if wants:
		prop.db_set("setup_wants", ",".join(wants))
	pos_made = {}
	if payload.get("pos"):
		from kamra.onboarding import create_pos_setup
		pos_made = create_pos_setup(prop.name, payload["pos"])

	rt_by_code = {}
	weekends_created = 0
	for rt in payload.get("room_types", []):
		# Entire-place listings use Villa so the SIU backfill creates a
		# whole_property sellable unit (ADR-001 / ADR-002).
		category = rt.get("room_category", "Private")
		if topology == "whole_property":
			category = "Villa"
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
			"room_category": category,
			"air_conditioning": rt.get("air_conditioning", ""),
			"free_child_age": rt.get("free_child_age", 0),
			# unset = the country pack's standard rate, not an Indian slab
			"tax_percent": rt.get("tax_percent"),
		})
		doc.insert()
		rt_by_code[rt["code"]] = doc.name

		# Auto-create a Season for weekend (Fri+Sat) pricing if provided
		weekend_price = rt.get("weekend_price")
		if weekend_price and float(weekend_price) > 0:
			import datetime
			year_end = str(datetime.date.today().replace(year=datetime.date.today().year + 2))
			frappe.get_doc({
				"doctype": "Season",
				"property": prop.name,
				"season_name": f"{rt['name']} Weekend",
				"room_type": doc.name,
				"start_date": str(datetime.date.today()),
				"end_date": year_end,
				"adjustment_type": "Absolute",
				"adjustment_value": float(weekend_price),
				"days_of_week": "fri, sat",
				"priority": 100,
			}).insert()
			weekends_created += 1

	rooms_created = 0
	for spec in payload.get("rooms", []):
		rt_name = rt_by_code.get(spec["room_type_code"])
		if not rt_name:
			frappe.throw(f"Unknown room type code {spec['room_type_code']}")
		for num in spec["numbers"]:
			num = str(num).strip()
			frappe.get_doc({
				"doctype": "Room", "property": prop.name,
				"room_number": num, "room_type": rt_name,
				# the Today room board groups by floor - never leave it blank
				"floor": str(spec.get("floor") or "").strip() or default_floor(num),
			}).insert()
			rooms_created += 1

	# Entire-place with no physical rooms: still create a whole_property SIU
	# via Room Type Villa sync / backfill.
	meal_plans_created = 0
	if not skip_meal_plans(prop.property_kind):
		for mp in payload.get("meal_plans", []):
			frappe.get_doc({
				"doctype": "Meal Plan", "property": prop.name,
				"code": mp["code"], "label": mp.get("label"),
				"price_per_adult": mp.get("price_per_adult", 0),
				"price_per_child": mp.get("price_per_child", 0),
				"is_default": mp.get("is_default", 0),
			}).insert()
			meal_plans_created += 1

	from kamra.savings import log_action
	log_action("setup_property", "Property", prop.name, prop.name,
	           minutes_saved=45,
	           rationale=f"Onboarded {prop.name} ({prop.property_kind}): "
	                     f"{len(rt_by_code)} room types, {rooms_created} rooms",
	           channel="API")
	# Ensure Sellable Units exist for the new inventory (ADR-001).
	siu_stats = {}
	try:
		from kamra.siu.units import backfill_property
		siu_stats = backfill_property(prop.name)
	except Exception:
		frappe.log_error(title="Sellable Unit backfill after setup_property")
	return {"property": prop.name, "room_types": len(rt_by_code),
	        "rooms": rooms_created,
	        "meal_plans": meal_plans_created,
	        "property_kind": prop.property_kind,
	        "inventory_topology": topology,
	        "pos": pos_made,
	        "sellable_units": siu_stats}



@frappe.whitelist()
def import_bookings(property: str, bookings):
	"""Bulk booking import - the switch-over tool. Each row: {guest_name,
	phone?, room_type_code, check_in, check_out, adults?, children?,
	amount_after_tax?, channel?, status?}. Rows with a fixed amount keep
	it (auto_price off); others are priced by the engine."""
	if isinstance(bookings, str):
		bookings = json.loads(bookings)
	frappe.only_for(("System Manager", "Hotel Admin"))
	from kamra.authz import assert_property_access
	assert_property_access(property)

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


def _pack_tax_id_label(prop) -> str:
	from kamra.localization import pack_for
	return pack_for(prop.name).locale(prop).get("tax_id_label") or "Tax ID"


def _pack_tax_label(property: str) -> str:
	from kamra.localization import pack_for
	prop = frappe.get_cached_doc("Property", property)
	return pack_for(property).locale(prop).get("tax_label") or "Tax"


def _stay_money(res):
	"""The GRC's money line: what the stay owes and what's been taken -
	advances and held deposits called out separately."""
	folio = frappe.db.get_value(
		"Folio", {"reservation": res.name, "folio_type": "Guest"},
		["name", "grand_total", "payments_total", "balance"], as_dict=True)
	if not folio:
		return None
	rows = frappe.get_all(
		"Folio Payment", filters={"parent": folio.name},
		fields=["payment_kind", "amount"])
	def ksum(kind):
		return sum(float(r.amount or 0) for r in rows
		           if (r.payment_kind or "Payment") == kind)
	return {
		"folio": folio.name,
		"grand_total": float(folio.grand_total or 0),
		"paid_total": float(folio.payments_total or 0),
		"balance": float(folio.balance or 0),
		"advance": ksum("Advance"),
		"deposit_held": ksum("Security Deposit") + ksum("Refund"),
		"refunded": -ksum("Refund"),
	}


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
def registration_card(reservation: str):
	"""Everything the printed GRC (guest registration card) needs."""
	res = frappe.get_doc("Reservation", reservation)
	guest = frappe.get_doc("Guest", res.guest)
	prop = frappe.get_doc("Property", res.property)
	return {
		"property": {
			"property_name": prop.property_name,
			"logo_url": prop.get("logo_url"),
			"address": ", ".join(filter(None, [  # nosemgrep: frappe-no-functional-code -- filter(None, ...) drops empty address parts; equivalent to a comprehension
				prop.address_line, prop.city, prop.state, prop.pincode])),
			"gstin": prop.gstin, "phone": prop.phone, "email": prop.email,
			"tax_id_label": _pack_tax_id_label(prop),
			"checkin_time": str(prop.checkin_time or ""),
			"checkout_time": str(prop.checkout_time or ""),
		},
		"money": _stay_money(res),
		"readiness": {
			"id_on_file": bool(guest.get("id_file") or guest.get("id_number")),
			"address_on_file": bool(guest.get("address_proof_file")),
			"occupants": len(res.get("occupants") or []),
			"pax": int(res.adults or 0) + int(res.children or 0),
			"precheckin_status": res.get("precheckin_status") or "Not sent",
			"signed": bool(res.get("precheckin_signature")),
		},
		"signature": res.get("precheckin_signature") or None,
		"tax_label": _pack_tax_label(res.property),
		"reservation": {
			"room_id": res.room,
			"room_number": frappe.db.get_value("Room", res.room, "room_number")
			               if res.room else None,
			"room_type_name": frappe.db.get_value(
				"Room Type", res.room_type, "room_type_name")
			                  if res.room_type else None,
			"actual_check_in": str(res.actual_check_in) if res.get("actual_check_in") else None,
			"actual_check_out": str(res.actual_check_out) if res.get("actual_check_out") else None,
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
			"id_file": guest.get("id_file"),
			"address_proof_file": guest.get("address_proof_file"),
			"guest_id": guest.name,
			"address": ", ".join(filter(None, [  # nosemgrep: frappe-no-functional-code -- filter(None, ...) drops empty address parts; equivalent to a comprehension
				guest.get("address_line"), guest.get("city")])),
		},
		"occupants": [
			{"row": o.name, "full_name": o.full_name, "age": o.age,
			 "gender": o.gender, "nationality": o.nationality,
			 "id_type": o.id_type, "id_number": o.id_number,
			 "phone": o.phone, "id_file": o.get("id_file")}
			for o in (res.get("occupants") or [])
		],
	}


@frappe.whitelist()
@require_roles("Finance", "Front Desk", "Night Auditor", "Kamra Agent")
def cash_summary(property: str, date: str | None = None,
                 to_date: str | None = None):
	"""Cashier reconciliation: what the system says was collected today,
	per payment mode - the number the drawer must match at shift close.

	Prefers Cashier Transaction totals (FO + POS); falls back to folio
	payments for properties that have not opened a till yet."""
	from kamra.business_date import get_business_date
	date = date or get_business_date(property)
	try:
		from kamra.cashier import cash_summary_v2
		return cash_summary_v2(property, date, to_date)
	except frappe.ValidationError:
		raise
	except Exception:
		pass
	rows = frappe.db.sql(
		"""
		SELECT fp.mode, COUNT(*) AS txns, COALESCE(SUM(fp.amount), 0) AS total
		FROM `tabFolio Payment` fp
		JOIN `tabFolio` f ON fp.parent = f.name
		WHERE f.property = %(property)s AND fp.posting_date BETWEEN %(date)s AND %(to)s
		GROUP BY fp.mode ORDER BY total DESC
		""",
		{"property": property, "date": date, "to": to_date or date}, as_dict=True,
	)
	return {"date": date, "modes": rows,
	        "grand_total": float(sum(r.total for r in rows)),
	        "source": "folio"}


_DEPOSIT_STATUSES = ("Confirmed", "Pending Payment", "Held")


def _confirm_status(res):
	"""Held / Pending Payment → Confirmed: money has secured the booking."""
	if res.status not in ("Pending Payment", "Held"):
		return
	frappe.flags.kamra_status_transition = True
	try:
		res.status = "Confirmed"
		res.hold_expires_on = None
		res.save(ignore_permissions=True)
	finally:
		frappe.flags.kamra_status_transition = False
	res.reload()


def _deposit_state(res) -> dict:
	"""What the booking should have secured it with (the property's
	deposit %, the figure the quote promised), what has come in before
	arrival, and any link already out with the guest."""
	total = float(res.amount_after_tax or 0)
	pct = float(frappe.get_cached_value("Property", res.property,
	                                    "deposit_pct") or 0)
	expected = round(total * pct / 100, 2)
	paid = float(res.advance_paid or 0)
	link = frappe.db.get_value(
		"Folio", {"reservation": res.name, "folio_type": "Guest"},
		["payment_link_url", "payment_link_amount"], as_dict=True) or {}
	return {
		"pct": pct, "expected": expected, "paid": paid,
		"due": max(0.0, round(expected - paid, 2)),
		"link_url": link.get("payment_link_url"),
		"link_amount": float(link.get("payment_link_amount") or 0) or None,
		"can_take": res.status in _DEPOSIT_STATUSES,
	}


def _security_deposit_state(res) -> dict | None:
	try:
		from kamra.deposit import deposit_state
		return deposit_state(res)
	except Exception:
		frappe.log_error(title="security deposit state failed")
		return None


def _deposit_reservation(reservation: str):
	res = frappe.get_doc("Reservation", reservation)
	from kamra.crs import assert_property_access
	assert_property_access(res.property)
	if res.status not in _DEPOSIT_STATUSES:
		frappe.throw(_("A deposit is taken before arrival - this booking is "
		               "{0}. Take in-house payments on the folio.").format(
			res.status))
	return res


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance", "Kamra Agent")
def record_advance(reservation: str, amount: float, mode: str = "Cash",
                   reference: str | None = None, pin: str | None = None):
	"""Take a deposit / advance on a booking before arrival (#114). Opens
	the guest folio early so the money sits on the stay from day one and
	the balance at check-in is right; recorded through add_folio_payment,
	so the till, cashier PIN and ledger see it like any other payment.
	A Held / Pending Payment booking is confirmed by it."""
	res = _deposit_reservation(reservation)
	amount = float(amount or 0)
	if amount <= 0:
		frappe.throw(_("Enter the deposit amount."))
	from kamra.localization import pack_for, payment_modes
	modes = payment_modes(pack_for(res.property))
	if mode not in modes:
		frappe.throw(_("Pick a payment mode: {0}.").format(", ".join(modes)))
	# money guards before any write: a locked till refuses cleanly
	from kamra.authz import require_cashier_pin
	from kamra.cashier import require_open_session
	require_cashier_pin(res.property, pin)
	require_open_session(res.property)

	_confirm_status(res)
	from kamra.folio import open_folio
	folio = open_folio(res)
	add_folio_payment(folio, mode, amount,
	                  reference=reference or f"deposit:{res.name}", pin=pin,
	                  kind="Advance")
	frappe.db.set_value("Reservation", res.name, "advance_paid",
	                    float(res.advance_paid or 0) + amount)
	res.reload()
	from kamra.savings import log_action
	log_action("record_advance", "Folio", folio, res.property,
	           rationale=f"{mode} deposit {amount:,.0f} on {res.name}")
	return {"folio": folio, "status": res.status,
	        "deposit": _deposit_state(res)}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance", "Kamra Agent")
def deposit_payment_link(reservation: str, amount: float | None = None):
	"""A payment link for the booking deposit - the deposit still due by
	default, or any amount the desk agrees with the guest. Paid through the
	gateway, it posts to the folio as an Advance (settle_payment_link)."""
	res = _deposit_reservation(reservation)
	amount = float(amount or 0) or _deposit_state(res)["due"]
	if amount <= 0:
		frappe.throw(_("No deposit is due - enter the amount to request."))
	from kamra.folio import open_folio
	from kamra.payments import create_payment_link
	link = create_payment_link(open_folio(res), amount=amount,
	                           purpose="Booking deposit")
	prop = frappe.get_cached_value("Property", res.property, "property_name")
	link["message"] = _(
		"Hello {guest}, please pay the deposit of {cur} {amount} to secure "
		"your booking {ref} at {property} ({checkin} → {checkout}): {url}"
	).format(guest=res.guest_name, cur=link["currency"],
	         amount=f"{amount:,.2f}", ref=res.name, property=prop,
	         checkin=res.check_in_date, checkout=res.check_out_date,
	         url=link["url"])
	link["deposit"] = _deposit_state(res)
	return link


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance", "Hotel Admin")
def simulate_payment_link(reservation: str):
	"""Test mode only: act as the gateway and mark the outstanding link
	paid - for demos and training, never on a live gateway."""
	res = frappe.get_doc("Reservation", reservation)
	from kamra.crs import assert_property_access
	assert_property_access(res.property)
	from kamra.payments import _settings, settle_payment_link
	if not _settings(res.property).test_mode:
		frappe.throw(_("Only available while the payment gateway is in test mode."))
	f = frappe.db.get_value(
		"Folio", {"reservation": res.name, "folio_type": "Guest"},
		["name", "payment_link_id", "payment_link_amount"], as_dict=True)
	if not f or not f.payment_link_id:
		frappe.throw(_("No payment link has been sent for this booking."))
	posted = settle_payment_link(f.name, f.payment_link_id,
	                             float(f.payment_link_amount or 0))
	res.reload()
	return {"posted": posted, "status": res.status,
	        "deposit": _deposit_state(res)}


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Hotel Admin", "Kamra Agent")
def security_deposit(reservation: str):
	"""The stay's refundable security (damage) deposit: policy amount, what
	is held, withheld and refunded, its history and which actions are open."""
	from kamra.deposit import _reservation, deposit_state
	return deposit_state(_reservation(reservation))


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance", "Kamra Agent")
def collect_security_deposit(reservation: str, amount: float,
                             mode: str = "Cash", reference: str | None = None,
                             pin: str | None = None):
	"""Take a refundable security deposit (villas: the damage deposit). Lands
	on the guest folio as a Security Deposit payment and in the Deposit
	ledger - a liability held for the guest, never revenue. Cashier PIN and
	open till as for any payment."""
	from kamra.deposit import collect_deposit
	return collect_deposit(reservation, amount, mode=mode, reference=reference,
	                       pin=pin)


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Hotel Admin", "Kamra Agent")
def waive_security_deposit(reservation: str, reason: str):
	"""Waive the property's security deposit for this stay (reason required).
	Refused once money has been taken - refund it instead."""
	from kamra.deposit import waive_deposit
	return waive_deposit(reservation, reason)


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance", "Hotel Admin")
def withhold_security_deposit(reservation: str, amount: float, reason: str,
                              evidence: str | None = None,
                              pin: str | None = None):
	"""Keep all or part of the held deposit against damage (reason required).
	The withheld part posts as a damage charge on the guest folio and moves
	from the Deposit ledger to the Guest ledger to pay it."""
	from kamra.deposit import withhold_deposit
	return withhold_deposit(reservation, amount, reason, evidence, pin=pin)


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance", "Hotel Admin")
def refund_security_deposit(reservation: str, amount: float | None = None,
                            mode: str | None = None, note: str | None = None,
                            pin: str | None = None):
	"""Refund what is still held (all of it by default) through the folio
	refund path - till, folio and a Deposit-ledger debit. Cashier PIN."""
	from kamra.deposit import refund_deposit
	return refund_deposit(reservation, amount, mode=mode, note=note, pin=pin)


@frappe.whitelist()
@require_roles("Front Desk", "Hotel Admin", "Kamra Agent")
def release_access_instructions(reservation: str, force: int = 0):
	from kamra.access import release_access
	return release_access(reservation, force=int(force or 0))


@frappe.whitelist()
@require_roles("Front Desk", "Hotel Admin", "Kamra Agent")
def confirm_pending_reservation(reservation: str):
	"""Mark Held / Pending Payment / Requested as Confirmed (host or payment)."""
	res = frappe.get_doc("Reservation", reservation)
	if res.status not in ("Held", "Pending Payment", "Requested", "Waitlist"):
		frappe.throw(f"Cannot confirm from status {res.status}.")
	frappe.flags.kamra_status_transition = True
	try:
		res.status = "Confirmed"
		res.hold_expires_on = None
		res.save(ignore_permissions=True)
	finally:
		frappe.flags.kamra_status_transition = False
	try:
		from kamra.deposit import ensure_deposit_for_reservation
		ensure_deposit_for_reservation(res)
	except Exception:
		frappe.log_error(title="Security deposit ensure on confirm failed")
	return {"reservation": res.name, "status": res.status}


@frappe.whitelist()
@require_roles("Finance", "Front Desk", "Kamra Agent")
def folio_payment_link(folio: str):
	from kamra.payments import create_payment_link
	return create_payment_link(folio)


@frappe.whitelist()
@require_roles("Housekeeping", "Front Desk", "Kamra Agent")
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
		        "assigned_to_user", "assignment_status", "due_by", "creation"],
		order_by="creation asc",
	)
	me = frappe.session.user
	now_dt = now_datetime()
	prio_rank = {"Urgent": 0, "High": 1, "Medium": 2, "Low": 3}
	for t in tasks:
		t["arrival_today"] = t.room in arriving_rooms
		t["room_number"] = (t.room or "").split("-")[-1]
		t["mine"] = bool(t.assigned_to_user) and t.assigned_to_user == me
		t["claimable"] = not t.assigned_to_user
		t["overdue"] = bool(t.due_by and get_datetime(t.due_by) < now_dt)
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

	# guest context the housekeeper needs on the floor: who's in the room or
	# arriving, whether they're a VIP, their requests and arrival timing
	ctx = {}
	stays = frappe.get_all(
		"Reservation",
		filters={"property": property, "room": ("is", "set"),
		         "status": ("in", ["Confirmed", "Checked In"]),
		         "check_in_date": ("<=", today), "check_out_date": (">=", today)},
		fields=["room", "guest", "guest_name", "status", "special_requests",
		        "eta", "check_in_date", "check_out_date"],
	) + frappe.get_all(
		"Reservation",
		filters={"property": property, "room": ("is", "set"),
		         "status": "Confirmed", "check_in_date": today},
		fields=["room", "guest", "guest_name", "status", "special_requests",
		        "eta", "check_in_date", "check_out_date"],
	)
	vips = set(frappe.get_all(
		"Guest", filters={"name": ("in", [s.guest for s in stays if s.guest]), "vip": 1},
		pluck="name")) if stays else set()
	for s in stays:
		c = ctx.setdefault(s.room, {})
		if s.guest in vips:
			c["vip"] = 1
		if s.special_requests:
			c["special_requests"] = s.special_requests
		if str(s.check_in_date) == today:
			c["arrival_today"] = 1
			c["eta"] = str(s.eta or "")
			c["arriving_guest"] = s.guest_name
		if str(s.check_out_date) == today:
			c["departure_today"] = 1
		if s.status == "Checked In":
			c["in_house_guest"] = s.guest_name

	for r in rooms:
		r["arrival_today"] = r.name in arriving_rooms
		r.update(ctx.get(r.name, {}))
	# tasks carry the same context so a card can show the VIP star inline
	for t in tasks:
		c = ctx.get(t.room, {})
		t["vip"] = c.get("vip", 0)
		t["special_requests"] = t.get("special_requests") or c.get("special_requests")
		t["eta"] = c.get("eta")

	# completion media (proof-of-clean photos/videos) attached to each task
	task_names = [t.name for t in tasks]
	media = {}
	if task_names:
		for f in frappe.get_all(
			"File",
			filters={"attached_to_doctype": "Housekeeping Task",
			         "attached_to_name": ("in", task_names)},
			fields=["attached_to_name", "file_url"], order_by="creation asc"):
			media.setdefault(f.attached_to_name, []).append(f.file_url)
	for t in tasks:
		t["media"] = media.get(t.name, [])

	return {"date": today, "tasks": tasks, "rooms": rooms}


@frappe.whitelist()
@require_roles("Housekeeping", "Front Desk", "Kamra Agent")
def hk_update_task(task: str, status: str):
	"""Start or complete a housekeeping task from the phone.

	An Inspection is completed by passing it: Done on an inspection is taken
	as Verified, which moves the room to Ready (inspection required by the
	turnover profile) or Inspected - never back to plain Clean. Verifying -
	an inspection or anyone's clean - is a supervisor's call, the same rule
	set_housekeeping_status applies to Inspected / Ready."""
	if status not in ("In Progress", "Done", "Verified"):
		frappe.throw("Status must be In Progress, Done or Verified.")
	doc = frappe.get_doc("Housekeeping Task", task)
	if doc.task_type == "Inspection" and status == "Done":
		status = "Verified"
	if status == "Verified" and not _is_room_supervisor():
		frappe.throw(_("Only a housekeeping supervisor can pass an inspection "
		               "or verify a clean."), frappe.PermissionError)
	doc.status = status
	doc.save()
	if status in ("Done", "Verified"):
		from kamra.savings import log_action
		log_action("housekeeping_done", "Housekeeping Task", doc.name,
		           doc.property, minutes_saved=3,
		           rationale=f"{doc.task_type} for {doc.room} closed from mobile",
		           channel="API")
	return {"ok": True, "task": doc.name, "status": doc.status}


@frappe.whitelist(methods=["POST"])
@require_roles("Housekeeping", "Front Desk", "Kamra Agent")
def hk_upload_media(task: str):
	"""Attach a completion photo/video (proof of clean) to a housekeeping task.

	Uploaded from the housekeeper's phone while the room is being serviced. Stored
	public and attached to the task, so it stays with the record after the task
	closes and drops out of the live queue."""
	if not frappe.db.exists("Housekeeping Task", task):
		frappe.throw("Task not found.")
	req = getattr(frappe.local, "request", None)
	files = getattr(req, "files", {}) if req else {}
	if "file" not in files:
		frappe.throw("No file uploaded.")
	f = files["file"]
	content = f.stream.read()
	if len(content) > 25 * 1024 * 1024:
		frappe.throw("File is too large - keep photos/videos under 25 MB.")
	# endpoint-gated (Kamra authorizes on the route, not the doctype), so the
	# File is created ignore_permissions and attached to the task.
	saved = frappe.get_doc({
		"doctype": "File",
		"file_name": f.filename,
		"content": content,
		"attached_to_doctype": "Housekeeping Task",
		"attached_to_name": task,
		"is_private": 0,
	}).insert(ignore_permissions=True)
	from kamra.savings import log_action
	log_action("hk_media_upload", "Housekeeping Task", task,
	           frappe.db.get_value("Housekeeping Task", task, "property"),
	           rationale=f"Completion media added to {task}", channel="API")
	return {"file_url": saved.file_url, "file_name": saved.file_name}


@frappe.whitelist(methods=["POST"])
@require_roles("Housekeeping", "Front Desk", "Kamra Agent")
def hk_delete_media(task: str, file_url: str):
	"""Remove a completion photo/video from a housekeeping task."""
	name = frappe.db.get_value("File", {
		"attached_to_doctype": "Housekeeping Task",
		"attached_to_name": task,
		"file_url": file_url,
	})
	if not name:
		frappe.throw("That file is not attached to this task.")
	frappe.delete_doc("File", name, ignore_permissions=True)
	return {"ok": True}


@frappe.whitelist()
@require_roles("Housekeeping", "Front Desk", "Hotel Admin", "Kamra Agent")
def hk_task_media(task: str):
	"""Completion photos/videos attached to one housekeeping task (newest first)."""
	return frappe.get_all(
		"File",
		filters={"attached_to_doctype": "Housekeeping Task",
		         "attached_to_name": task},
		fields=["file_url"], order_by="creation desc", pluck="file_url")


@frappe.whitelist()
@require_roles("Housekeeping", "Front Desk", "Hotel Admin", "Kamra Agent")
def hk_room_media(room: str):
	"""Photos/videos from the room's LATEST cleaning only - so the front desk
	sees just the most recent clean, not older cycles. Lets reception confirm a
	room is genuinely guest-ready."""
	tasks = frappe.get_all("Housekeeping Task", filters={"room": room}, pluck="name")
	if not tasks:
		return []
	# the newest attached file marks the most recent cleaning that has media
	latest = frappe.get_all(
		"File",
		filters={"attached_to_doctype": "Housekeeping Task",
		         "attached_to_name": ("in", tasks)},
		fields=["attached_to_name"], order_by="creation desc", limit=1)
	if not latest:
		return []
	return frappe.get_all(
		"File",
		filters={"attached_to_doctype": "Housekeeping Task",
		         "attached_to_name": latest[0].attached_to_name},
		fields=["file_url"], order_by="creation asc", pluck="file_url")


def _hk_staff(property: str) -> list[dict]:
	"""Enabled staff who can work housekeeping tasks at this property: a
	Housekeeping or Housekeeping Supervisor role, and no property
	restriction that leaves this one out."""
	holders = set(frappe.get_all(
		"Has Role",
		filters={"role": ("in", ["Housekeeping", "Housekeeping Supervisor"]),
		         "parenttype": "User",
		         "parent": ("not in", ["Administrator", "Guest"])},
		pluck="parent"))
	if not holders:
		return []
	restricted: dict[str, set] = {}
	for p in frappe.get_all("User Permission",
	                        filters={"user": ("in", list(holders)), "allow": "Property"},
	                        fields=["user", "for_value"]):
		restricted.setdefault(p.user, set()).add(p.for_value)
	users = frappe.get_all(
		"User", filters={"name": ("in", list(holders)), "enabled": 1},
		fields=["name", "full_name"], order_by="full_name asc")
	return [{"user": u.name, "full_name": u.full_name or u.name}
	        for u in users
	        if u.name not in restricted or property in restricted[u.name]]


@frappe.whitelist()
@require_roles("Housekeeping Supervisor", "Front Desk", "Kamra Agent")
def hk_staff(property: str):
	"""Who a supervisor can hand a housekeeping task to at this property."""
	from kamra.crs import assert_property_access
	assert_property_access(property)
	return _hk_staff(property)


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Housekeeping", "Kamra Agent")
def hk_assign_task(task: str, user: str):
	"""A supervisor hands a task to a specific housekeeper (awaits accept).
	Attendants take work from the pool with hk_claim_task; handing a task to
	someone else is the supervisor's (or desk's) call, and only to a
	housekeeper who can work this property."""
	if not _is_room_supervisor():
		frappe.throw(_("Only a housekeeping supervisor can assign tasks."),
		             frappe.PermissionError)
	doc = frappe.get_doc("Housekeeping Task", task)
	if doc.status not in ("Pending", "In Progress"):
		frappe.throw(_("Task {0} is already {1}.").format(doc.name, doc.status))
	if user not in {s["user"] for s in _hk_staff(doc.property)}:
		frappe.throw(_("{0} is not housekeeping staff at this property.").format(user))
	doc.assigned_to_user = user
	doc.assignment_status = "Assigned"
	doc.save()
	from kamra.savings import log_action
	log_action("hk_assign", "Housekeeping Task", doc.name, doc.property,
	           rationale=f"{doc.task_type} {doc.room} → {user}")
	return {"ok": True, "assignment_status": "Assigned", "assigned_to_user": user}


@frappe.whitelist(methods=["POST"])
@require_roles("Housekeeping", "Front Desk", "Kamra Agent")
def hk_claim_task(task: str):
	"""A housekeeper takes an unassigned task from the pool for themselves."""
	doc = frappe.get_doc("Housekeeping Task", task)
	if doc.assigned_to_user and doc.assigned_to_user != frappe.session.user:
		frappe.throw(f"Already taken by {doc.assigned_to_user}.")
	doc.assigned_to_user = frappe.session.user
	doc.assignment_status = "Accepted"
	doc.save()
	return {"ok": True, "assignment_status": "Accepted"}


@frappe.whitelist(methods=["POST"])
@require_roles("Housekeeping", "Front Desk", "Kamra Agent")
def hk_accept_task(task: str):
	"""The assigned housekeeper accepts the task handed to them."""
	doc = frappe.get_doc("Housekeeping Task", task)
	doc.assignment_status = "Accepted"
	if not doc.assigned_to_user:
		doc.assigned_to_user = frappe.session.user
	doc.save()
	return {"ok": True, "assignment_status": "Accepted"}


@frappe.whitelist(methods=["POST"])
@require_roles("Housekeeping", "Front Desk", "Kamra Agent")
def hk_reject_task(task: str, reason: str = ""):
	"""Decline a task - it drops back into the pool for someone else,
	keeping the reason on record."""
	doc = frappe.get_doc("Housekeeping Task", task)
	who = doc.assigned_to_user or frappe.session.user
	doc.assigned_to_user = None
	doc.assignment_status = "Unassigned"
	doc.reject_reason = f"{who}: {reason}" if reason else who
	doc.save()
	from kamra.savings import log_action
	log_action("hk_reject", "Housekeeping Task", doc.name, doc.property,
	           rationale=f"{who} declined {doc.task_type} {doc.room}: {reason}")
	return {"ok": True, "assignment_status": "Unassigned"}


@frappe.whitelist(methods=["POST"])
@require_roles("Housekeeping", "Front Desk", "Kamra Agent")
def hk_log_item(property: str, item_description: str, condition: str = "Found",
                room: str | None = None):
	"""A floor housekeeper logs a lost/found/missing/damaged item from the
	phone. Lands in the Lost & Found register for the desk to reconcile."""
	doc = frappe.get_doc({
		"doctype": "Lost And Found Item",
		"property": property,
		"item_description": item_description,
		"condition": condition,
		"found_in_room": room or None,
		"found_on": nowdate(),
		"found_by": frappe.session.user,
		"status": "In Storage",
	}).insert()
	from kamra.savings import log_action
	log_action("lost_found_logged", "Lost And Found Item", doc.name, property,
	           rationale=f"{condition}: {item_description}"
	                     + (f" in {room}" if room else ""))
	return {"ok": True, "name": doc.name}


@frappe.whitelist(methods=["POST"])
@require_roles("Housekeeping", "Front Desk", "Kamra Agent")
def hk_post_consumable(room: str, charge_type: str, description: str,
                       amount: float):
	"""Housekeeping posts what they find in the room - minibar consumption or
	laundry - onto the in-house guest's folio. Scoped to those two types so
	the floor can't touch discounts, allowances or room charges."""
	if charge_type not in ("Minibar", "Laundry"):
		frappe.throw("Housekeeping can only post Minibar or Laundry.")
	if float(amount) <= 0:
		frappe.throw("Amount must be positive.")
	res = frappe.db.get_value(
		"Reservation",
		{"room": room, "status": "Checked In"},
		["name", "property"], as_dict=True)
	if not res:
		frappe.throw("No checked-in guest in that room to bill.")
	from kamra.pos import assert_room_charges_allowed
	assert_room_charges_allowed(res.name)
	# post through the governed agent user (same pattern as public bookings):
	# the housekeeper is authorized above and scoped to two charge types, and
	# GST is still resolved server-side. Attribution is stamped below.
	# laundry is a taxable service at the country pack's services rate (the
	# same rate a Laundry Order bills at); minibar resolves to the F&B rate
	# inside post_stay_charge
	gst_rate = 0
	if charge_type == "Laundry":
		from kamra.localization import pack_for, services_tax_rate
		gst_rate = services_tax_rate(pack_for(res.property), res.property)
	with act_as(AGENT_EMAIL):
		out = post_stay_charge(res.name, charge_type, description, float(amount),
		                       gst_rate=gst_rate)
	from kamra.savings import log_action
	from kamra.localization import money_text
	log_action("hk_charge", "Folio", out.get("folio"), res.property,
	           rationale=f"{charge_type} {money_text(res.property, amount)} "
	                     f"to {room} ({description})")
	return {"ok": True, "folio": out.get("folio"), "balance": out.get("balance")}


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
def create_ticket(property: str, subject: str, category: str,
                  priority: str = "Medium", room: str | None = None,
                  reservation: str | None = None, guest: str | None = None,
                  description: str | None = None, source: str = "Manual"):
	"""Create a guest-request ticket. This is also the agent tool for
	'guest wants towels / AC is broken' - PRD FR-42."""
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
		           agent_name="Concierge",
		           # the ticket source names who raised it; the log channel
		           # names how it reached Kamra (an AI agent is API)
		           channel=({"AI Agent": agent_channel() or "API", "QR": "API"}
		                    .get(source, source)))
	return {"ticket": doc.name, "due_by": str(doc.due_by)}


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
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
@require_roles("Front Desk", "Kamra Agent")
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
@require_roles("Finance", "Front Desk", "Night Auditor", "Kamra Agent")
def get_folio(reservation: str):
	"""Folio for a reservation - opens one if the guest is checked in."""
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
@require_roles("Finance", "Front Desk", "Kamra Agent")
def add_folio_charge(folio: str, charge_type: str, description: str,
                     amount: float, gst_rate: float = 0,
                     posting_date: str | None = None, is_alcohol: int = 0,
                     reservation: str | None = None):
	_refuse_opening_balance(charge_type)
	# check what the caller sent, before the hotel's own rules pick a rate
	_check_charge_amount_and_tax(
		frappe.db.get_value("Folio", folio, "property"), amount, gst_rate)
	return _post_folio_charge(folio, charge_type, description, amount,
	                          gst_rate, posting_date, is_alcohol, reservation)


def _refuse_opening_balance(charge_type: str):
	"""An opening balance is carried over by the go-live import only - a
	hand-posted one would look like an old-system balance to the audit."""
	if charge_type == "Opening Balance":
		frappe.throw("Opening balances are posted by the go-live import "
		             "only (Go-live import screen).")


def _post_folio_charge(folio: str, charge_type: str, description: str,
                       amount: float, gst_rate: float = 0,
                       posting_date: str | None = None, is_alcohol: int = 0,
                       reservation: str | None = None):
	"""Put one charge on a bill. Not whitelisted and does no amount or rate
	check: a caller that takes an amount or rate from outside calls
	_check_charge_amount_and_tax on it first. Code that posts rates the
	hotel itself decided (the agent's post_stay_charge, banquet billing)
	calls this directly."""
	_refuse_opening_balance(charge_type)
	doc = frappe.get_doc("Folio", folio)
	if doc.status == "Closed":
		frappe.throw("Folio is closed.")
	if int(is_alcohol or 0) and doc.folio_type in ("Company", "Group"):
		frappe.throw("Alcohol cannot be billed to a company folio - "
		             "post it to the guest folio.")
	# tax is the hotel's rule, not the caller's guess - without this an
	# F&B/minibar charge posted without a rate lands on the bill untaxed
	gst_rate = _resolve_charge_gst(doc.property, charge_type, description,
	                               int(is_alcohol or 0), float(gst_rate or 0))
	from kamra.business_date import assert_transaction_date
	from kamra.ledger import code_for_charge_type, record_charge_ledger
	bd = assert_transaction_date(doc.property, posting_date, label="Posting date")
	code = code_for_charge_type(charge_type)
	doc.append("charges", {
		"posting_date": bd,
		"charge_type": charge_type,
		"transaction_code": code,
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
	charge = doc.charges[-1]
	try:
		record_charge_ledger(doc, charge.as_dict())
	except Exception:
		frappe.log_error(title="ledger charge write failed")
	from kamra.savings import log_action
	log_action("post_charge", "Folio", doc.name, doc.property,
	           rationale=f"{charge_type}: {description} ₹{amount}")
	from kamra.webhooks import emit_folio_posted
	emit_folio_posted(doc, charge)
	return doc.as_dict()




def _pin_guard(folio: str, pin=None):
	from kamra.authz import require_cashier_pin
	require_cashier_pin(frappe.db.get_value("Folio", folio, "property"), pin)

@frappe.whitelist()
@require_roles("Finance", "Front Desk", "Kamra Agent")
def add_folio_payment(folio: str, mode: str, amount: float,
                      reference: str | None = None, pin: str | None = None,
                      kind: str = "Payment"):
	"""Record money received on the stay ledger. kind labels WHY it came
	in - Payment (against the bill), Advance (collected before/at
	check-in) or Security Deposit (held, refundable). Refunds go through
	refund_folio_payment so they can never be entered by accident."""
	if kind not in ("Payment", "Advance", "Security Deposit"):
		frappe.throw("kind must be Payment, Advance or Security Deposit.")
	if float(amount) <= 0:
		frappe.throw("Amount must be positive.")
	_pin_guard(folio, pin)
	doc = frappe.get_doc("Folio", folio)
	from kamra.business_date import get_business_date
	from kamra.cashier import record_cashier_txn, require_open_session
	bd = get_business_date(doc.property)
	# Property currency — never leave Folio Payment on the INR schema default (#341)
	currency = (frappe.get_cached_value("Property", doc.property, "currency")
	            or "INR")
	sess = None
	try:
		sess = require_open_session(doc.property)
	except Exception:
		if "Kamra Agent" not in frappe.get_roles() and \
		   frappe.session.user != "Administrator":
			raise
	doc.append("payments", {
		"posting_date": bd,
		"payment_kind": kind,
		"mode": mode,
		"amount": float(amount),
		"reference": reference,
		"currency": currency,
	})
	from kamra.folio import _recalculate
	_recalculate(doc)
	doc.save()
	pay = doc.payments[-1]
	record_cashier_txn(
		doc.property, "Payment", mode, float(amount),
		folio=doc.name, reference=reference, session=sess)
	try:
		from kamra.ledger import record_payment_ledger
		record_payment_ledger(doc, pay.as_dict(), session=sess)
	except Exception:
		frappe.log_error(title="ledger payment write failed")
	if kind == "Advance" and doc.reservation and frappe.db.get_value(
			"Reservation", doc.reservation, "status") == "Checked In":
		# an advance taken from a guest already in house pays the stay
		from kamra.ledger import transfer_advances_to_guest
		transfer_advances_to_guest(doc.reservation)
	if kind == "Security Deposit" and doc.reservation and \
	   (doc.folio_type or "Guest") == "Guest":
		# keep the stay's Security Deposit record in step, whichever screen
		# took the money (the deposit panel or the folio's own payment form)
		from kamra.deposit import record_collected
		record_collected(doc.reservation, float(amount), mode)
	elif kind != "Security Deposit":
		# who took which money, for the activity log (a deposit logs its own)
		from kamra.localization import money_text
		from kamra.savings import log_action
		log_action("folio_payment", "Folio", doc.name, doc.property,
		           rationale=f"{kind} {money_text(doc.property, amount)} by {mode}"
		                     + (f" ({reference})" if reference else ""))
	return doc.as_dict()


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Front Desk", "Kamra Agent")
def refund_folio_payment(folio: str, amount: float, mode: str,
                         reason: str, pin: str | None = None,
                         reason_code: str | None = None,
                         supervisor_pin: str | None = None):
	"""Give money back on an open folio - a held security deposit at
	checkout, or an over-collected advance. Stored as a negative ledger
	row so every balance still sums exactly; a reason is mandatory."""
	return _refund_folio_payment(folio, amount, mode, reason, pin=pin,
	                             reason_code=reason_code,
	                             supervisor_pin=supervisor_pin)


def _refund_folio_payment(folio: str, amount: float, mode: str, reason: str,
                          pin: str | None = None,
                          reason_code: str | None = None,
                          supervisor_pin: str | None = None,
                          ledger: str | None = None):
	"""The one refund writer (folio row, till, ledger). Not whitelisted:
	ledger lets a security-deposit refund release the Deposit ledger -
	callers that pass it have already checked the deposit's balance.

	A pre-arrival Advance still sitting in Deposit is refunded there too
	(#343), not onto Guest, and Reservation.advance_paid is reduced."""
	if float(amount) <= 0:
		frappe.throw("Refund amount must be positive.")
	if not (reason or "").strip() and not reason_code:
		frappe.throw("A refund reason is required.")
	_pin_guard(folio, pin)
	doc = frappe.get_doc("Folio", folio)
	if doc.status == "Closed":
		frappe.throw("This folio is closed - refunds need a credit note "
		             "via allowance on a new folio.")
	from kamra.ledger import require_reason
	reason_text = require_reason(
		"Refund", reason_code, reason or "",
		supervisor_pin=supervisor_pin, property=doc.property)
	received = sum(float(p.amount or 0) for p in doc.payments
	               if float(p.amount or 0) > 0)
	refunded = -sum(float(p.amount or 0) for p in doc.payments
	                if float(p.amount or 0) < 0)
	if float(amount) > received - refunded:
		frappe.throw(f"Only ₹{received - refunded:,.2f} was collected on "
		             "this folio - can't refund more than that.")
	# Pre-arrival advance: release Deposit liability, not Guest (#343)
	release_advance = False
	if not ledger:
		ledger = _prearrival_advance_refund_ledger(doc)
		release_advance = ledger == "Deposit"
	from kamra.business_date import get_business_date
	from kamra.cashier import record_cashier_txn, require_open_session
	bd = get_business_date(doc.property)
	currency = (frappe.get_cached_value("Property", doc.property, "currency")
	            or "INR")
	sess = None
	try:
		sess = require_open_session(doc.property)
	except Exception:
		if "Kamra Agent" not in frappe.get_roles() and \
		   frappe.session.user != "Administrator":
			raise
	doc.append("payments", {
		"posting_date": bd,
		"payment_kind": "Refund",
		"mode": mode,
		"amount": -float(amount),
		"reference": str(reason_text)[:140],
		"currency": currency,
	})
	from kamra.folio import _recalculate
	_recalculate(doc)
	doc.save()
	pay = doc.payments[-1]
	record_cashier_txn(
		doc.property, "Refund", mode, -float(amount),
		folio=doc.name, reference=str(reason_text)[:140], session=sess)
	try:
		from kamra.ledger import record_payment_ledger
		record_payment_ledger(doc, pay.as_dict(), session=sess, ledger=ledger)
	except Exception:
		frappe.log_error(title="ledger refund write failed")
	if release_advance and doc.reservation:
		paid = float(frappe.db.get_value(
			"Reservation", doc.reservation, "advance_paid") or 0)
		frappe.db.set_value(
			"Reservation", doc.reservation, "advance_paid",
			max(0.0, round(paid - float(amount), 2)))
	if ledger != "Deposit":  # a deposit refund logs itself (kamra.deposit)
		from kamra.localization import money_text
		from kamra.savings import log_action
		log_action("folio_refund", "Folio", doc.name, doc.property,
		           rationale=f"Refund {money_text(doc.property, amount)} by {mode}: "
		                     f"{str(reason_text)[:100]}")
	elif release_advance:
		from kamra.localization import money_text
		from kamra.savings import log_action
		log_action("folio_refund", "Folio", doc.name, doc.property,
		           rationale=f"Advance refund {money_text(doc.property, amount)} "
		                     f"by {mode}: {str(reason_text)[:100]}")
	return {"ok": True, "balance": doc.balance}


def _prearrival_advance_refund_ledger(doc) -> str | None:
	"""Deposit when a pre-arrival Advance is still held there; else None
	(record_payment_ledger defaults Refund → Guest)."""
	if not doc.reservation:
		return None
	status = frappe.db.get_value("Reservation", doc.reservation, "status")
	if status not in ("Confirmed", "Held", "Pending Payment", "Waitlist"):
		return None
	held = float(frappe.db.sql(
		"""SELECT COALESCE(SUM(credit - debit), 0)
		   FROM `tabFolio Ledger Entry`
		   WHERE folio = %s AND ledger = 'Deposit'""",
		(doc.name,))[0][0] or 0)
	return "Deposit" if held > 0 else None


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Kamra Agent")
def set_actual_times(reservation: str, actual_check_in: str | None = None,
                     actual_check_out: str | None = None):
	"""Correct the recorded arrival/departure moments - early check-ins
	and late checkouts should show what actually happened, not just when
	the button was pressed. Early/late charges stay explicit folio lines."""
	from frappe.utils import get_datetime
	updates = {}
	if actual_check_in:
		updates["actual_check_in"] = get_datetime(actual_check_in)
	if actual_check_out:
		updates["actual_check_out"] = get_datetime(actual_check_out)
	if not updates:
		frappe.throw("Nothing to update.")
	frappe.db.set_value("Reservation", reservation, updates)
	from kamra.savings import log_action
	res = frappe.db.get_value("Reservation", reservation,
	                          ["property", "guest_name"], as_dict=True)
	log_action("set_actual_times", "Reservation", reservation, res.property,
	           rationale=f"Actual times corrected for {res.guest_name}: "
	                     + ", ".join(f"{k}={v}" for k, v in updates.items()))
	return {"ok": True, **{k: str(v) for k, v in updates.items()}}


_FNB_WORDS = ("food", "dinner", "lunch", "breakfast", "meal", "restaurant",
              "f&b", "fnb", "beverage", "snack", "room service", "cafe",
              "kitchen", "buffet", "minibar", "mini bar")


def _check_charge_amount_and_tax(property: str, amount, gst_rate):
	"""A posted charge is a positive amount taxed at one of the country
	pack's rates. Reductions go through allowances and voids, not through a
	minus charge, and an unknown rate would put made-up tax on the bill."""
	try:
		amount = float(amount)
	except (TypeError, ValueError):
		frappe.throw("Charge amount must be a number.")
	if not math.isfinite(amount):
		frappe.throw("Charge amount must be a number.")
	if not amount > 0:
		frappe.throw("Charge amount must be more than zero. To reduce a "
		             "bill, post an allowance or void the charge.")
	from kamra.localization import pack_for
	allowed = [float(r) for r in pack_for(property).tax_rate_options(property)]
	if float(gst_rate or 0) not in allowed:
		frappe.throw("Tax rate {0}% is not allowed. Use one of: {1}.".format(
			f"{float(gst_rate or 0):g}",
			", ".join(f"{r:g}" for r in allowed)))


def _resolve_charge_gst(property: str, charge_type: str, description: str,
                        is_alcohol: int, provided: float) -> float:
	"""The tax rate a charge actually carries, decided server-side so a caller
	(human or agent) cannot mis-tax it. Food & beverage uses the F&B rate from
	the localization pack; alcohol its own rate; otherwise the given rate."""
	text = f"{charge_type} {description}".lower()
	if is_alcohol:
		return float(provided) if provided else 18.0
	if any(w in text for w in _FNB_WORDS):
		from kamra.folio import _fnb_gst
		return float(_fnb_gst(property))
	return float(provided or 0)


@frappe.whitelist()
@require_roles("Finance", "Front Desk", "Kamra Agent")
def void_folio_charge(folio: str, charge_row: str, reason: str = "",
                      pin: str | None = None,
                      reason_code: str | None = None,
                      supervisor_pin: str | None = None):
	"""Remove a wrong charge line from an open folio (the bill-correction
	path). PIN-guarded like other money actions for humans; agents are
	accountable through the action log. Posts a ledger reversal."""
	_pin_guard(folio, pin)
	prop = frappe.db.get_value("Folio", folio, "property")
	from kamra.ledger import require_reason, reverse_ledger_for_charge
	reason_text = require_reason(
		"Void", reason_code, reason or "",
		supervisor_pin=supervisor_pin, property=prop)
	try:
		reverse_ledger_for_charge(prop, folio, charge_row, str(reason_text))
	except Exception:
		frappe.log_error(title="ledger void reversal failed")
	from kamra.folio import void_charge
	return void_charge(folio, charge_row, str(reason_text))


@frappe.whitelist()
@require_roles("Finance", "Front Desk", "Kamra Agent")
def post_stay_charge(reservation: str, charge_type: str, description: str,
                     amount: float, gst_rate: float = 0, is_alcohol: int = 0):
	"""Post a charge to a stay letting the billing rules pick the folio -
	corporate room/meals land on the Company folio, alcohol and anything
	unruled lands on the guest. The agent-facing way to post charges."""
	res = frappe.get_doc("Reservation", reservation)
	if res.status not in ("Confirmed", "Checked In", "Checked Out"):
		frappe.throw("Reservation is not active.")
	from kamra.folio import target_folio
	is_alcohol = 1 if int(is_alcohol or 0) else 0
	# check what the caller sent, not the rate the hotel picks below
	_check_charge_amount_and_tax(res.property, amount, gst_rate)
	# GST is decided by the hotel's tax rules, not by the caller's guess:
	# food & beverage carries the F&B rate (5% in India), not 12/18.
	gst_rate = _resolve_charge_gst(res.property, charge_type, description,
	                               is_alcohol, gst_rate)
	folio_name = target_folio(res, charge_type, is_alcohol)
	out = _post_folio_charge(folio_name, charge_type, description, amount,
	                         gst_rate, is_alcohol=is_alcohol,
	                         reservation=res.name)
	return {"folio": folio_name, "folio_type": out.get("folio_type"),
	        "balance": out.get("balance")}


@frappe.whitelist()
@require_roles("Finance", "Front Desk", "Kamra Agent")
def set_billing_rules(company: str, rules):
	"""Replace a company's billing rules. rules = [{charge_type, pay_by}]."""
	if isinstance(rules, str):
		rules = frappe.parse_json(rules)
	doc = frappe.get_doc("Corporate Account", company)
	doc.set("billing_rules", [])
	for r in rules or []:
		doc.append("billing_rules", {
			"charge_type": r.get("charge_type"),
			"pay_by": r.get("pay_by") or "Company",
		})
	doc.save()
	return {"company": company, "rules": len(doc.billing_rules)}


@frappe.whitelist()
@require_roles("Finance", "Front Desk", "Kamra Agent")
def get_billing_rules(company: str):
	doc = frappe.get_doc("Corporate Account", company)
	return [{"charge_type": r.charge_type, "pay_by": r.pay_by}
	        for r in (doc.get("billing_rules") or [])]


@frappe.whitelist()
@require_roles("Finance", "Front Desk", "Kamra Agent")
def company_billing_default(company: str, property: str | None = None):
	"""What this company pays when it has no billing rules: the property's
	`default_company_billing` for a credit company, nothing otherwise.
	`charge_types` is None when every charge type (except liquor) is covered."""
	from kamra.folio import COMPANY_BILLING_DEFAULTS, default_company_billing
	if property:
		from kamra.crs import assert_property_access
		assert_property_access(property)
	doc = frappe.get_doc("Corporate Account", company)
	has_rules = bool(doc.get("billing_rules"))
	label = default_company_billing(property)
	covered = COMPANY_BILLING_DEFAULTS[label]
	return {
		"company": company,
		"credit_allowed": bool(doc.credit_allowed),
		"has_rules": has_rules,
		"default": label,
		"charge_types": None if covered is None else sorted(covered),
		"applies": bool(doc.credit_allowed) and not has_rules,
	}


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
def update_occupants(reservation: str, occupants):
	"""Replace the stay's occupant register.
	occupants = [{full_name, age, gender, nationality, id_type, id_number, phone}]
	A child keeps name and age only: no phone, and ID details only where the
	country's register needs them (see localization.minor_id_kept)."""
	if isinstance(occupants, str):
		occupants = frappe.parse_json(occupants)
	doc = frappe.get_doc("Reservation", reservation)
	from kamra.localization import is_minor, minor_id_kept, pack_for, validate_id_type
	pack = pack_for(doc.property)
	default_nat = getattr(pack, "DEFAULT_NATIONALITY", "")
	# scans survive edits even when the client sends stale rows: carry the
	# stored id_file for any row that comes back without one
	existing_scans = {o.name: o.get("id_file")
	                  for o in (doc.get("occupants") or [])}
	existing_types = {o.name: o.get("id_type")
	                  for o in (doc.get("occupants") or [])}
	doc.set("occupants", [])
	stale_scans, minors_trimmed = [], 0
	for o in occupants or []:
		if not (o.get("full_name") or "").strip():
			continue
		nationality = o.get("nationality") or default_nat
		row = {
			"full_name": o["full_name"].strip(),
			"age": o.get("age") or None,
			"gender": o.get("gender") or "",
			"nationality": nationality,
			"id_type": o.get("id_type") or "",
			"id_number": (o.get("id_number") or "").strip(),
			"phone": o.get("phone") or "",
			# an uploaded ID survives a register edit
			"id_file": o.get("id_file")
			           or existing_scans.get(o.get("row")) or None,
		}
		if is_minor(pack, row["age"]):
			# a child's phone is never needed; ID only where the register asks
			trim = {"phone": ""} if minor_id_kept(pack, nationality) else \
			       {"phone": "", "id_type": "", "id_number": "", "id_file": None}
			if any(row[k] for k in trim):
				minors_trimmed += 1
				if row["id_file"] and "id_file" in trim:
					stale_scans.append(row["id_file"])
			row.update(trim)
		if row["id_type"] and row["id_type"] != existing_types.get(o.get("row")):
			validate_id_type(doc.property, row["id_type"])
		doc.append("occupants", row)
	doc.save()
	if stale_scans:
		from kamra.privacy import _delete_files
		for url in stale_scans:
			_delete_files("Reservation", reservation, url=url)
	return {"reservation": reservation, "occupants": len(doc.occupants),
	        "minors_trimmed": minors_trimmed,
	        "rows": [
	            {"row": o.name, "full_name": o.full_name, "age": o.age,
	             "gender": o.gender, "nationality": o.nationality,
	             "id_type": o.id_type, "id_number": o.id_number,
	             "phone": o.phone, "id_file": o.get("id_file")}
	            for o in doc.occupants]}


@frappe.whitelist()
@require_roles("Finance", "Front Desk", "Kamra Agent")
def split_folio(reservation: str, folio_type: str = "Extra"):
	from kamra.folio import split_folio as _split
	return {"folio": _split(reservation, folio_type)}


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Front Desk", "Kamra Agent")
def delete_folio(folio: str):
	"""Remove an empty split/extra folio created by mistake.

	Guards: never the primary Guest folio, and only when it carries no
	charges and no payments - money is never dropped this way.
	"""
	doc = frappe.get_doc("Folio", folio)
	if doc.folio_type == "Guest":
		frappe.throw("The primary guest folio can't be deleted.")
	if doc.get("charges") or doc.get("payments"):
		frappe.throw(
			"This folio has charges or payments - move them to another folio first."
		)
	if doc.docstatus == 1:
		doc.cancel()
	frappe.delete_doc("Folio", folio, ignore_permissions=True, force=True)
	return {"deleted": folio}


@frappe.whitelist()
@require_roles("Finance", "Front Desk", "Kamra Agent")
def transfer_folio_charge(from_folio: str, charge_row: str, to_folio: str):
	from kamra.folio import transfer_charge
	transfer_charge(from_folio, charge_row, to_folio)
	from kamra.savings import log_action
	log_action("transfer_charge", "Folio", to_folio,
	           rationale=f"Moved charge {charge_row} {from_folio} → {to_folio}")
	return {"ok": True}


@frappe.whitelist()
@require_roles("Finance", "Front Desk", "Kamra Agent")
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
@require_roles("Finance", "Front Desk", "Kamra Agent")
def split_folio_charge(from_folio: str, charge_row: str, to_folio: str,
                       percent: float | None = None,
                       amount: float | None = None):
	"""Split one charge line between two folios - by percent or amount."""
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
@require_roles("Finance", "Front Desk", "Kamra Agent")
def reservation_folios(reservation: str):
	"""All folios of a stay (guest + splits) with balances - plus the
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
@require_roles("Finance", "Front Desk", "Kamra Agent")
def group_master_folio(group_booking: str):
	"""Get-or-create the group's consolidated company folio."""
	from kamra.folio import open_group_folio
	return {"folio": open_group_folio(group_booking)}


@frappe.whitelist()
@require_roles("Finance", "Front Desk", "Kamra Agent")
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
@require_roles("Finance", "Front Desk", "Kamra Agent")
def close_folio(folio: str, pin: str | None = None):
	_pin_guard(folio, pin)
	prop = frappe.db.get_value("Folio", folio, "property")
	try:
		from kamra.cashier import require_open_session
		require_open_session(prop)
	except Exception:
		if "Kamra Agent" not in frappe.get_roles() and \
		   frappe.session.user != "Administrator":
			raise
	from kamra.folio import close_folio as _close
	was_open = frappe.db.get_value("Folio", folio, "status") != "Closed"
	invoice_number = _close(folio)
	if was_open:
		from kamra.savings import log_action
		log_action("close_folio", "Folio", folio, prop,
		           rationale=f"Folio closed, invoice {invoice_number}")
	return {"invoice_number": invoice_number}


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Front Desk", "Kamra Agent")
def post_allowance(folio: str, amount: float, reason: str,
                   gst_rate: float = 0, pin: str | None = None):
	"""Write off part of a bill against a specific folio, with a reason."""
	_pin_guard(folio, pin)
	from kamra.folio import post_allowance as _allow
	_allow(folio, float(amount), reason, float(gst_rate or 0))
	from kamra.savings import log_action
	log_action("allowance", "Folio", folio,
	           rationale=f"Allowance ₹{abs(float(amount)):,.2f}: {reason}")
	return {"ok": True, "folio": folio}


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Front Desk", "Kamra Agent")
def part_settle_folio(folio: str, pin: str | None = None):
	"""Interim invoice mid-stay: freeze the paid folio, open a fresh one."""
	_pin_guard(folio, pin)
	from kamra.folio import part_settle as _settle
	return _settle(folio)


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Front Desk", "Kamra Agent")
def cancel_invoice(folio: str, reason: str, pin: str | None = None):
	"""Void an invoice into the register and reopen the folio for correction."""
	_pin_guard(folio, pin)
	from kamra.folio import cancel_invoice as _cancel
	out = _cancel(folio, reason)
	from kamra.savings import log_action
	log_action("cancel_invoice", "Folio", folio,
	           rationale=f"Invoice {out['cancelled']} cancelled: {reason}")
	return out


@frappe.whitelist()
@require_roles("Finance", "Front Desk", "Kamra Agent")
def folio_invoice(folio: str):
	"""Everything the bill needs to print itself.

	A tax invoice is a legal document, not a screenshot of a table: the
	service code belongs on each LINE (a room night, a restaurant cover
	and a laundry bag are three different supplies), the tax has to be
	named the way the country names it, the total has to appear in words,
	and the guest wants a summary by what they bought before they read
	forty lines. All of that is assembled here so every surface that
	prints a bill - the folio screen, a PDF, an email - agrees.
	"""
	from kamra import localization as loc

	doc = frappe.get_doc("Folio", folio)
	prop = frappe.get_doc("Property", doc.property)
	res = frappe.get_doc("Reservation", doc.reservation)
	pack = loc.pack_for(doc.property)
	_loc_ctx = pack.invoice_context(prop)

	# B2B: corporate bookings carry the buyer's GSTIN on the invoice.
	# A group master folio bills to the GROUP's company.
	bill_to = None
	bill_company = res.company
	if doc.folio_type == "Group" and doc.get("group_booking"):
		bill_company = frappe.db.get_value(
			"Group Booking", doc.group_booking, "company") or bill_company
	if bill_company:
		company = frappe.db.get_value(
			"Corporate Account", bill_company, ["company_name", "gstin"], as_dict=True)
		if company:
			bill_to = {"name": company.company_name, "gstin": company.gstin}

	buyer_tax_id = (bill_to or {}).get("gstin")
	split = loc.tax_split(pack, prop, buyer_tax_id)

	# per-line service codes + a summary of what was actually bought
	lines, by_rate, by_head = [], {}, {}
	for c in doc.charges:
		code = loc.service_code_for(pack, prop, c.charge_type)
		lines.append({
			"row": c.name, "posting_date": str(c.posting_date),
			"charge_type": c.charge_type, "description": c.description,
			"qty": c.qty, "rate": c.rate, "amount": c.amount,
			"gst_rate": c.gst_rate, "gst_amount": c.gst_amount,
			"total": c.total, "is_alcohol": c.is_alcohol,
			"auto_posted": c.auto_posted,
			"service_code": (code or {}).get("value"),
		})
		key = float(c.gst_rate or 0)
		slot = by_rate.setdefault(key, {"taxable": 0.0, "tax": 0.0})
		slot["taxable"] += float(c.amount or 0)
		slot["tax"] += float(c.gst_amount or 0)
		head = by_head.setdefault(
			c.charge_type or "Other",
			{"head": c.charge_type or "Other", "amount": 0.0, "tax": 0.0,
			 "total": 0.0, "lines": 0, "service_code": (code or {}).get("value")})
		head["amount"] += float(c.amount or 0)
		head["tax"] += float(c.gst_amount or 0)
		head["total"] += float(c.total or 0)
		head["lines"] += 1

	settled = bool(doc.invoice_number)
	# what the tax authority requires ON the bill (ZATCA: QR + Arabic title)
	statutory = loc.invoice_print_block(
		pack, "Folio", doc.name, doc.invoice_number) if settled else None
	return {
		"folio": doc.as_dict(),
		"lines": lines,
		"bill_to": bill_to,
		"statutory": statutory,
		"document": {
			# a bill before settlement is provisional and must say so - the
			# invoice number only exists once the folio closes
			"title": (statutory or {}).get("title") or (
				_("Tax Invoice") if settled else _("Provisional Bill")),
			"title_local": (statutory or {}).get("title_ar"),
			"is_final": settled,
			"number": doc.invoice_number or doc.name,
			"date": str(doc.closed_on or "")[:10] or nowdate(),
			"amount_in_words": loc.amount_in_words(pack, prop, doc.grand_total),
			"footer": _loc_ctx.get("footer"),
			"service_code_label": (_loc_ctx.get("service_code") or {}).get(
				"label", "SAC"),
		},
		"property": {
			"name": prop.property_name, "legal_name": prop.legal_name,
			"logo_url": prop.get("logo_url"),
			"address_line": prop.address_line, "city": prop.city,
			"state": prop.state, "pincode": prop.pincode,
			"address": ", ".join(filter(None, [prop.address_line, prop.city,  # nosemgrep: frappe-no-functional-code -- filter(None, ...) drops empty address parts; equivalent to a comprehension
			                                   prop.state, prop.pincode])),
			"gstin": prop.gstin, "phone": prop.phone, "email": prop.email,
			"website": prop.get("website"),
			# country pack owns the service code + place-of-supply rule
			"sac": _loc_ctx["sac"],
			"place_of_supply": _loc_ctx["place_of_supply"],
			"tax_label": _loc_ctx["tax_label"],
			"tax_id_label": _loc_ctx["tax_id_label"],
		},
		"guest": _invoice_guest(res),
		"stay": {
			"reservation": res.name,
			"check_in": str(res.check_in_date),
			"check_out": str(res.check_out_date),
			"arrival": str(res.get("actual_check_in") or "") or None,
			"departure": str(res.get("actual_check_out") or "") or None,
			"nights": res.nights, "room": res.room,
			"room_type": res.room_type,
			"adults": res.adults, "children": res.children,
			"pax": int(res.adults or 0) + int(res.children or 0),
			"meal_plan": res.get("meal_plan"),
			"company": res.company,
			"group_booking": res.get("group_booking"),
			"booked_by_name": res.get("booked_by_name"),
			"booked_by_phone": res.get("booked_by_phone"),
			"contact_preference": res.get("contact_preference"),
		},
		"summary_by_head": sorted(by_head.values(), key=lambda h: -h["total"]),
		"tax_summary": [
			{"rate": rate, "taxable": v["taxable"], "total_tax": v["tax"],
			 "parts": [{"label": label.upper(),
			            "rate": round(rate * float(share), 4),
			            "amount": v["tax"] * float(share)}
			           for label, share in split]}
			for rate, v in sorted(by_rate.items())
		],
		# kept for callers written against the pre-v2 shape
		"gst_summary": [
			{"rate": rate, "taxable": v["taxable"],
			 "cgst": v["tax"] * float(split[0][1]),
			 "sgst": v["tax"] * float(split[-1][1]),
			 "total_tax": v["tax"]}
			for rate, v in sorted(by_rate.items())
		],
	}


def _invoice_guest(res) -> dict:
	"""Who the bill is addressed to, as the guest register knows them -
	nationality included, because a foreign guest's invoice needs it and
	so does the police report."""
	g = frappe.db.get_value(
		"Guest", res.guest,
		["full_name", "phone", "email", "nationality", "address_line",
		 "city", "id_type", "id_number"], as_dict=True) or {}
	return {
		"guest_id": res.guest,
		"name": g.get("full_name") or res.guest_name,
		"phone": g.get("phone"), "email": g.get("email"),
		"nationality": g.get("nationality"),
		"address": ", ".join(filter(None, [g.get("address_line"), g.get("city")])),  # nosemgrep: frappe-no-functional-code -- drops empty address parts
		"id_type": g.get("id_type"),
	}


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Night Auditor", "Kamra Agent")
def run_night_audit(property: str, business_date: str | None = None,
                    acknowledge=None, note: str | None = None):
	"""Close the current business date. Refused while a blocking pre-check
	(kamra.night_audit.night_audit_precheck) has items, unless each is
	listed in `acknowledge` (check keys) with a `note` giving the reason."""
	# Night audit is a front-desk / night-auditor ritual, not admin-only.
	from kamra.folio import run_night_audit as _run
	from kamra.night_audit import record_run
	return record_run(property, "Manual", lambda: _run(
		property, business_date, acknowledge=acknowledge, note=note, mode="manual"))


@frappe.whitelist()
@require_roles()
def gstr1_rows(from_date: str, to_date: str, property: str | None = None):
	"""Invoice-level rows for a GSTR-1 style export (v0: B2C summary).
	Filter by property - each GSTIN files its own return. The return is the
	India pack's: a property elsewhere is refused, and without a property
	only the user's India properties are included."""
	from kamra import localization as loc
	if property:
		return loc.tax_return_rows(loc.pack_for(property), property,
		                           from_date, to_date)
	scope = _property_scope()
	names = scope[1] if scope else frappe.get_all("Property", pluck="name")
	india = loc.pack_for_country("India")
	return loc.tax_return_rows(india, [p for p in names if loc.pack_for(p) is india],
	                           from_date, to_date)


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
def guests_with_stats(search: str | None = None):
	"""Guest list with stay stats - the CRM index."""
	from kamra.authz import guest_scope_sql
	scope_sql, params = guest_scope_sql("g")
	where = f"WHERE {scope_sql}"
	join_scope = (" AND r.property IN %(scope_properties)s"
	              if "scope_properties" in params else "")
	if search:
		where += " AND (g.full_name LIKE %(q)s OR g.phone LIKE %(q)s)"
		params["q"] = f"%{search}%"
	return frappe.db.sql(  # nosemgrep: frappe-sql-format-injection -- values are parameterized; interpolated text is a constant or whitelisted identifier, not user input
		f"""
		SELECT
			g.name, g.full_name, g.phone, g.email, g.vip,
			COUNT(r.name) AS bookings,
			SUM(CASE WHEN r.status IN ('Checked In','Checked Out') THEN 1 ELSE 0 END) AS stays,
			COALESCE(SUM(CASE WHEN r.status != 'Cancelled' THEN r.nights ELSE 0 END), 0) AS nights,
			COALESCE(SUM(CASE WHEN r.status != 'Cancelled' THEN r.amount_after_tax ELSE 0 END), 0) AS lifetime_value,
			MAX(r.check_in_date) AS last_stay
		FROM `tabGuest` g
		LEFT JOIN `tabReservation` r ON r.guest = g.name{join_scope}
		{where}
		GROUP BY g.name
		ORDER BY lifetime_value DESC, g.modified DESC
		LIMIT 200
		""",
		params,
		as_dict=True,
	)


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
def guest_search(q: str):
	"""Typeahead for attaching a booking to an existing profile."""
	q = (q or "").strip()
	if len(q) < 2:
		return []
	from kamra.authz import guest_scope_sql
	scope_sql, params = guest_scope_sql("g")
	params["q"] = f"%{q}%"
	return frappe.db.sql(  # nosemgrep: frappe-sql-format-injection -- values are parameterized; the interpolated scope clause is a constant from authz
		f"""
		SELECT g.name, g.full_name, g.phone, g.email, g.vip, g.blacklisted,
		       g.blacklist_reason,
		       COUNT(r.name) AS stays, MAX(r.check_in_date) AS last_stay
		FROM `tabGuest` g
		LEFT JOIN `tabReservation` r
		       ON r.guest = g.name AND r.status IN ('Checked In', 'Checked Out')
		WHERE (g.full_name LIKE %(q)s OR g.phone LIKE %(q)s) AND {scope_sql}
		GROUP BY g.name
		ORDER BY stays DESC, g.modified DESC
		LIMIT 8
		""",
		params, as_dict=True,
	)


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
def guest_alert(guest: str | None = None, phone: str | None = None):
	"""Is the guest a booking would attach to blacklisted? The desk asks
	before booking so the warning shows up front, not as a refusal at the
	end. Resolves exactly like create_booking: the chosen profile, else the
	profile with this phone number."""
	name = guest or (frappe.db.get_value("Guest", {"phone": phone}) if phone else None)
	if not name:
		return {"guest": None, "blacklisted": 0, "blacklist_reason": None}
	g = frappe.db.get_value(
		"Guest", name, ["name", "full_name", "blacklisted", "blacklist_reason"],
		as_dict=True)
	if not g:
		return {"guest": None, "blacklisted": 0, "blacklist_reason": None}
	from kamra.authz import assert_guest_access
	try:
		assert_guest_access(g.name)
		visible = True
	except frappe.PermissionError:
		visible = False
	return {
		"guest": g.name if visible else None,
		"full_name": g.full_name if visible else None,
		"blacklisted": 1 if g.blacklisted else 0,
		"blacklist_reason": g.blacklist_reason if visible else None,
		"can_override": 1 if _is_admin() else 0,
	}


def _is_admin() -> bool:
	from kamra.authz import ADMIN
	return bool(set(ADMIN) & set(frappe.get_roles()))


@frappe.whitelist(methods=["POST"])
@require_roles(scope={"guest": "Guest"})
def set_guest_blacklist(guest: str, blacklisted: int, reason: str):
	"""Blacklist a guest, or lift it. Hotel Admin only; a reason is required
	either way and lands in the activity log with the before/after."""
	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("A reason is required."))
	flag = 1 if cint(blacklisted) else 0
	before = frappe.db.get_value(
		"Guest", guest, ["blacklisted", "blacklist_reason"], as_dict=True)
	if before is None:
		frappe.throw(_("Guest profile {0} not found.").format(guest))
	frappe.db.set_value("Guest", guest, {
		"blacklisted": flag,
		# the standing reason is the one that put them on the list
		"blacklist_reason": reason[:500] if flag else None,
	})
	last_property = frappe.db.get_value(
		"Reservation", {"guest": guest}, "property", order_by="creation desc")
	from kamra.savings import log_action
	log_action(
		action_type="guest_blacklisted" if flag else "guest_blacklist_removed",
		reference_doctype="Guest",
		reference_name=guest,
		property=last_property,
		rationale=reason,
		before_snapshot={"blacklisted": cint(before.blacklisted),
		                 "blacklist_reason": before.blacklist_reason},
		after_snapshot={"blacklisted": flag,
		                "blacklist_reason": reason if flag else None},
	)
	return {"guest": guest, "blacklisted": flag,
	        "blacklist_reason": reason if flag else None}


_GUEST_LINKS = [  # every doctype that points at a Guest
	("Reservation", "guest"), ("Folio", "guest"),
	("Service Ticket", "guest"), ("Lost And Found Item", "guest"),
	("Security Deposit", "guest"),
	("Venue Booking", "customer"),  # banquet uses customer, not guest
	("WhatsApp Message", "guest"),
]


@frappe.whitelist()
@require_roles(scope={"source": "Guest", "target": "Guest"})
def merge_guests(source: str, target: str):
	"""Merge a duplicate profile into the surviving one: every linked
	document is repointed, missing contact fields are copied over, and
	the duplicate is deleted. Money is untouched - folios keep their
	lines and totals."""
	if source == target:
		frappe.throw("Pick two different profiles to merge.")
	src = frappe.get_doc("Guest", source)
	dst = frappe.get_doc("Guest", target)

	moved = {}
	for doctype, field in _GUEST_LINKS:
		if not frappe.db.exists("DocType", doctype):
			continue
		if not frappe.get_meta(doctype).has_field(field):
			continue
		rows = frappe.get_all(doctype, filters={field: source}, pluck="name")
		for name in rows:
			frappe.db.set_value(doctype, name, field, target,
			                    update_modified=False)
		if rows:
			moved[doctype] = len(rows)
	# denormalized guest_name on stays and bills follows the survivor
	for doctype in ("Reservation", "Folio"):
		frappe.db.sql(  # nosemgrep: frappe-sql-format-injection -- values are parameterized; interpolated text is a constant or whitelisted identifier, not user input
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
@require_roles(scope={"guest": "Guest"})
def anonymize_guest(guest: str):
	"""Right to erasure (DPDP s.12): see kamra.privacy.erase_guest. Stays
	and bills stay for the books. Irreversible."""
	from kamra.privacy import erase_guest

	return erase_guest(guest, reason="request")


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent", scope={"guest": "Guest"})
def guest_journey(guest: str):
	"""One guest's full story: profile, stats, chronological timeline.
	This is the CRM detail view - and the context an AI concierge loads
	before speaking to a returning guest."""
	from kamra.guest_documents import guest_documents

	doc = frappe.get_doc("Guest", guest)

	filters = {"guest": guest}
	scope = _property_scope()
	if scope:  # a restricted user sees only the stays at their properties
		filters["property"] = scope
	reservations = frappe.get_all(
		"Reservation",
		filters=filters,
		fields=[
			"name", "status", "source", "channel", "room", "room_type",
			"check_in_date", "check_out_date", "nights", "adults", "children",
			"amount_after_tax", "discount_amount", "special_requests",
			"booking_type", "company", "creation",
			"actual_check_in", "actual_check_out", "property",
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
				"title": f"Checked in · Room {r.room.split('-')[-1] if r.room else '-'}",
				"detail": r.special_requests or "", "reference": r.name,
			})
		if r.actual_check_out:
			timeline.append({
				"ts": str(r.actual_check_out), "type": "check_out",
				"title": "Checked out",
				"detail": f"Folio {_currency_symbol(r.property)}"
				          f"{float(r.amount_after_tax or 0):,.0f}",
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
			fields=["creation", "agent_name", "actor", "action_type",
			        "rationale", "minutes_saved", "action_channel"],
			order_by="creation desc",
			limit=50,
		):
			# a person at the desk is the actor and leaves agent_name empty
			who = log.agent_name or (
				frappe.utils.get_fullname(log.actor) if log.actor else "") \
				or "Staff"
			what = (log.action_type or "").replace("_", " ")
			timeline.append({
				"ts": str(log.creation), "type": "agent",
				"title": f"{who} · {what[:1].upper()}{what[1:]}",
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
			"id_place_of_issue": doc.get("id_place_of_issue"),
			"id_issue_date": str(doc.get("id_issue_date") or "") or None,
			"id_expiry_date": str(doc.get("id_expiry_date") or "") or None,
			"blacklisted": doc.get("blacklisted"),
			"blacklist_reason": doc.get("blacklist_reason"),
			"marketing_consent": doc.get("marketing_consent") or 0,
			"marketing_consent_date": doc.get("marketing_consent_date"),
			"marketing_consent_source": doc.get("marketing_consent_source"),
			"address": ", ".join(filter(None, [  # nosemgrep: frappe-no-functional-code -- filter(None, ...) drops empty address parts; equivalent to a comprehension
				doc.get("address_line"), doc.get("city")])),
			"notes": doc.guest_notes,
		},
		"stats": stats,
		"documents": guest_documents(guest, scope),
		"reservations": reservations,
		"timeline": timeline,
	}


def _currency_symbol(property: str | None) -> str:
	"""The property's currency symbol from its country pack."""
	if not property:
		return ""
	from kamra.localization import pack_for
	return pack_for(property).locale(
		frappe.get_cached_doc("Property", property)).get("currency_symbol", "")


def _property_scope():
	"""Filter value for a call that left `property` out: the user's own
	properties when they're restricted, else None (no filter)."""
	from kamra.authz import restricted_properties
	allowed = restricted_properties()
	return ("in", sorted(allowed)) if allowed is not None else None


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


def _stay_balances(names: list) -> dict:
	"""What each stay costs, has paid and still owes - one rule set shared
	by the Today board and the reservation drawer so they never disagree.

	Only the Guest folio counts (summed, so a part-settled stay with a fresh
	folio still adds up). The group master is the company's bill and Extra /
	Company folios are routed elsewhere, so neither is this guest's balance.

	- Checked In / Checked Out / No Show / Cancelled with a Guest folio: the
	  folio is the bill.
	- No Show / Cancelled with no folio: nothing is owed; any advance taken
	  is a refund due.
	- Confirmed with an early deposit folio: the booking total is the bill,
	  the folio holds what was paid.
	- Confirmed with no folio: the booking-time advance is all we know."""
	names = list({n for n in names if n})
	if not names:
		return {}
	resv = {r.name: r for r in frappe.get_all(
		"Reservation", filters={"name": ("in", names)},
		fields=["name", "status", "amount_after_tax", "advance_paid",
		        "check_out_date"])}
	folios = _guest_folio_sums(names)
	# A guest due out has nights the night audit has not posted yet;
	# check-out posts them before it counts what is owed, so the board does
	# the same (and throws the postings away) rather than show a balance
	# that check-out then refuses.
	today = getdate(nowdate())
	due_out = [n for n, r in resv.items() if r.status == "Checked In"
	           and r.check_out_date and getdate(r.check_out_date) <= today]
	if due_out:
		folios.update(_checkout_projection(due_out))
	out = {}
	for name, res in resv.items():
		folio = folios.get(name)
		total_booked = float(res.amount_after_tax or 0)
		adv = float(res.advance_paid or 0)
		ended = res.status in ("No Show", "Cancelled")
		if folio and (ended or res.status in ("Checked In", "Checked Out")):
			m = {"total": float(folio.total), "paid": float(folio.paid),
			     "due": float(folio.due), "has_folio": True, "source": "folio"}
		elif ended:
			m = {"total": 0.0, "paid": adv, "due": 0.0, "has_folio": False,
			     "source": "none"}
			if adv > 0:
				m["refund_due"] = adv
		elif folio:
			paid = float(folio.paid)
			m = {"total": total_booked, "paid": paid,
			     "due": max(0.0, round(total_booked - paid, 2)),
			     "has_folio": True, "source": "booking"}
		else:
			m = {"total": total_booked, "paid": adv,
			     "due": max(0.0, round(total_booked - adv, 2)),
			     "has_folio": False, "source": "booking"}
		out[name] = m
	return out


def _guest_folio_sums(names: list) -> dict:
	"""Guest-folio total / paid / balance per reservation."""
	if not names:
		return {}
	return {row.reservation: row for row in frappe.db.sql(
		"""
		SELECT reservation,
		       COALESCE(SUM(grand_total), 0) AS total,
		       COALESCE(SUM(payments_total), 0) AS paid,
		       COALESCE(SUM(balance), 0) AS due
		FROM `tabFolio`
		WHERE reservation IN %(names)s AND folio_type = 'Guest'
		GROUP BY reservation
		""",
		{"names": list(names)}, as_dict=True,
	)}


def _checkout_projection(names: list) -> dict:
	"""Guest-folio sums as they will stand at check-out: every remaining
	night posted by the same writer check-out uses (post_remaining_nights),
	inside a savepoint that is rolled back. Nothing is kept - not the
	charges, the ledger lines, nor the realtime pings their saves queue -
	so this is a read. Falls back to the posted figures on any error."""
	from kamra.folio import post_remaining_nights

	db = frappe.db
	queues = (db.before_commit, db.after_commit, db.after_rollback)
	saved = [list(q._functions) for q in queues]
	had_log = hasattr(frappe.local, "_realtime_log")
	saved_log = list(getattr(frappe.local, "_realtime_log", None) or [])
	sp = "kamra_checkout_projection"
	db.savepoint(sp)
	try:
		for name in names:
			post_remaining_nights(frappe.get_doc("Reservation", name))
		return _guest_folio_sums(names)
	except Exception:
		frappe.log_error(title="Kamra: check-out balance projection")
		return {}
	finally:
		db.rollback(save_point=sp)
		for q, fns in zip(queues, saved):
			q._functions.clear()
			q._functions.extend(fns)
		if had_log:
			frappe.local._realtime_log = saved_log
		elif hasattr(frappe.local, "_realtime_log"):
			del frappe.local._realtime_log


def _stay_balance(reservation: str) -> dict:
	"""_stay_balances for one booking."""
	return _stay_balances([reservation]).get(reservation) or {
		"total": 0.0, "paid": 0.0, "due": 0.0, "has_folio": False,
		"source": "none"}


@frappe.whitelist()
@require_roles("Front Desk", "Night Auditor", "Kamra Agent", "Finance", "Revenue Manager")
def front_desk_snapshot(property: str | None = None, date: str | None = None):
	"""Everything the front desk needs for one day, in one call."""
	date = date or nowdate()

	res_filters = {"check_in_date": date, "status": "Confirmed"}
	dep_filters = {"check_out_date": date, "status": "Checked In"}
	inh_filters = {"status": "Checked In"}
	room_filters = {}
	scope = property or _property_scope()
	if scope:
		for flt in (res_filters, dep_filters, inh_filters, room_filters):
			flt["property"] = scope

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

	# payment state per stay - the same rules as the reservation drawer
	all_rows = arrivals + departures + in_house
	money = _stay_balances([r.name for r in all_rows])
	for r in all_rows:
		m = money.get(r.name) or {}
		r["paid_total"] = m.get("paid", 0.0)
		r["balance_due"] = m.get("due", 0.0)
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
@require_roles("Front Desk", "Kamra Agent", "Finance", "Revenue Manager")
def find_reservations(property: str, query: str | None = None,
                      status: str | None = None, limit: int = 20):
	"""Search reservations by guest name, room number, or reference - optionally
	filtered by status. The way to resolve a room number or a name to an actual
	reservation before acting on it."""
	filters = {"property": property}
	if status:
		filters["status"] = status
	or_filters = None
	if query and query.strip():
		q = f"%{query.strip()}%"
		or_filters = [
			["name", "like", q],
			["guest_name", "like", q],
			["room", "like", q],
		]
	return frappe.get_all(
		"Reservation",
		filters=filters,
		or_filters=or_filters,
		fields=[
			"name", "guest", "guest_name", "room", "room_type", "status",
			"check_in_date", "check_out_date", "nights", "adults", "children",
			"amount_after_tax", "advance_paid",
		],
		order_by="check_in_date desc",
		limit=int(limit or 20),
	)


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Revenue Manager", "Kamra Agent")
def find_invoices(property: str, query: str | None = None, limit: int = 8):
	"""Resolve an invoice number (or partial) to its folio and stay, so the
	command palette can jump straight from 'INV-KDP-26-00042' to the bill."""
	q = (query or "").strip()
	if not q:
		return []
	rows = frappe.get_all(
		"Folio",
		filters={"property": property, "invoice_number": ["like", f"%{q}%"]},
		fields=["name", "invoice_number", "reservation", "guest",
		        "guest_name", "grand_total", "status", "folio_type"],
		order_by="modified desc",
		limit=int(limit or 8),
	)
	return rows


STAY_INSTRUCTION_FOR = ("Front Desk", "Housekeeping", "F&B", "Concierge",
                         "Transport", "Maintenance", "Security")


def _stay_instruction_rows(reservation: str) -> list:
	return frappe.get_all(
		"Stay Instruction",
		filters={"parent": reservation, "parenttype": "Reservation",
		         "parentfield": "instructions"},
		fields=["name", "department", "instruction", "status", "done_by",
		        "done_on", "owner", "creation"],
		order_by="idx asc")


@frappe.whitelist()
@require_roles("Front Desk", "Housekeeping", "Kamra Agent")
def stay_instructions(reservation: str):
	"""The special instructions on a stay (a VIP amenity, a 6am wake-up, a
	no-feather pillow) - each for one department, Open until someone marks
	it Done."""
	if not frappe.db.exists("Reservation", reservation):
		frappe.throw(_("Reservation {0} not found.").format(reservation),
		             frappe.DoesNotExistError)
	return _stay_instruction_rows(reservation)


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Kamra Agent")
def add_stay_instruction(reservation: str, department: str, instruction: str):
	"""Add an instruction to a stay for one department. Written as its own
	child row so it never re-saves (and re-validates) the whole booking."""
	instruction = (instruction or "").strip()
	if not instruction:
		frappe.throw(_("Write the instruction."))
	if department not in STAY_INSTRUCTION_FOR:
		frappe.throw(_("Instruction must be for one of: {0}.").format(
			", ".join(STAY_INSTRUCTION_FOR)))
	res = frappe.db.get_value("Reservation", reservation,
	                          ["name", "property", "status"], as_dict=True)
	if not res:
		frappe.throw(_("Reservation {0} not found.").format(reservation),
		             frappe.DoesNotExistError)
	if res.status in ("Cancelled", "Checked Out", "No Show"):
		frappe.throw(_("This stay is {0} - no new instructions.").format(res.status))
	idx = (frappe.db.sql(
		"""SELECT MAX(idx) FROM `tabStay Instruction`
		WHERE parent=%s AND parenttype='Reservation' AND parentfield='instructions'""",
		reservation)[0][0] or 0) + 1
	row = frappe.get_doc({
		"doctype": "Stay Instruction", "parent": reservation,
		"parenttype": "Reservation", "parentfield": "instructions",
		"idx": idx, "department": department,
		"instruction": instruction[:1000], "status": "Open",
	})
	row.db_insert()
	from kamra.savings import log_action
	log_action("stay_instruction", "Reservation", reservation, res.property,
	           rationale=f"{department}: {instruction[:120]}")
	return _stay_instruction_rows(reservation)


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Housekeeping", "Kamra Agent")
def set_stay_instruction_status(reservation: str, row: str, status: str):
	"""Mark one instruction Done (stamping who and when), or reopen it."""
	if status not in ("Open", "Done"):
		frappe.throw(_("Status must be Open or Done."))
	if not frappe.db.exists("Stay Instruction", {
			"name": row, "parent": reservation, "parenttype": "Reservation"}):
		frappe.throw(_("That instruction is not on this stay."))
	done = status == "Done"
	text = frappe.db.get_value("Stay Instruction", row, "instruction") or ""
	frappe.db.set_value("Stay Instruction", row, {
		"status": status,
		"done_by": frappe.session.user if done else None,
		"done_on": now_datetime() if done else None,
	})
	from kamra.savings import log_action
	log_action("stay_instruction", "Reservation", reservation,
	           frappe.db.get_value("Reservation", reservation, "property"),
	           rationale=f"{status}: {text[:120]}")
	return _stay_instruction_rows(reservation)


def _checkin_backfill(res) -> list[dict]:
	"""Soft-required check-in steps still open (Checked In or Confirmed).
	Empty when nothing applies or everything is done / skipped."""
	if res.status not in ("Confirmed", "Checked In"):
		return []
	from kamra.checkin import evaluate, soft_pending
	steps, _ctx = evaluate(res)
	return [{"step": s["step_key"], "title": s["title"], "tip": s.get("tip") or ""}
	        for s in soft_pending(steps)]


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent", "Finance", "Revenue Manager")
def reservation_detail(reservation: str):
	"""Everything about one booking in a single call - stay, money, guest,
	booker and the actions currently available. Powers the reservation drawer."""
	from kamra.kamra.doctype.reservation.reservation import uses_member_rooms
	res = frappe.get_doc("Reservation", reservation)

	# guest identity + stay history
	guest = None
	if res.guest:
		g = frappe.db.get_value(
			"Guest", res.guest,
			["name", "full_name", "phone", "email", "vip", "blacklisted"],
			as_dict=True,
		)
		if g:
			g["stays"] = frappe.db.count("Reservation", {
				"guest": res.guest, "status": ("in", ["Checked In", "Checked Out"])})
			g["last_stay"] = frappe.db.get_value(
				"Reservation", {"guest": res.guest, "status": "Checked Out",
				                "name": ("!=", res.name)},
				"check_out_date", order_by="check_out_date desc")
			guest = g

	money = _stay_balance(res.name)
	# the drawer's "Open folio" link - the newest guest folio (a
	# part-settled stay has several; the fresh one is the open one)
	folio = frappe.db.get_value(
		"Folio", {"reservation": reservation, "folio_type": "Guest"},
		["name"], as_dict=True, order_by="creation desc")

	booker = None
	if res.booked_by_name:
		booker = {
			"name": res.booked_by_name, "phone": res.booked_by_phone,
			"relation": res.booker_relation,
			"contact_preference": res.contact_preference,
		}

	cancellation = None
	if res.get("cancellation_number") or res.status == "Cancelled":
		cancellation = {
			"reason": res.get("cancellation_reason"),
			"note": res.get("cancellation_note"),
			"number": res.get("cancellation_number"),
			"fee": float(res.get("cancellation_fee") or 0),
			"cancelled_on": res.get("cancelled_on"),
		}

	return {
		"name": res.name,
		"status": res.status,
		"source": res.source,
		"channel": res.channel,
		"booking_type": res.booking_type,
		"property": res.property,
		"check_in_date": res.check_in_date,
		"check_out_date": res.check_out_date,
		"nights": res.nights,
		"adults": res.adults,
		"children": res.children,
		"room": res.room,
		"room_number": frappe.db.get_value("Room", res.room, "room_number") if res.room else None,
		"room_type": res.room_type,
		"room_type_name": frappe.db.get_value(
			"Room Type", res.room_type, "room_type_name") if res.room_type else None,
		# the plan's label ("Breakfast"), not its internal ID
		"meal_plan_name": (frappe.db.get_value(
			"Meal Plan", res.meal_plan, "label") or res.meal_plan)
			if res.meal_plan else None,
		"meal_plan": res.meal_plan,
		"rate_plan": res.rate_plan,
		"special_requests": res.special_requests,
		"eta": res.eta,
		"late_arrival": int(res.get("late_arrival") or 0),
		# the nightly rates confirmed at booking - what the folio bills
		"night_rates": [
			{"date": str(n.stay_date), "rate": float(n.rate or 0),
			 "demand_premium_pct": float(n.demand_premium_pct or 0)}
			for n in (res.get("night_rates") or [])],
		"precheckin_status": res.precheckin_status,
		"precheckin_token": res.get("precheckin_token"),
		# the scan itself is never in this payload - id_document is only the
		# private path, fetched separately through id_document_image so one
		# role gate governs who ever sees the picture
		"id_document": res.get("id_document"),
		"id_document_source": res.get("id_document_source"),
		"id_document_on": str(res.get("id_document_on") or "") or None,
		"id_document_discarded": res.get("id_document_discarded") or 0,
		"precheckin_verified_by": res.get("precheckin_verified_by"),
		"precheckin_verified_on": str(res.get("precheckin_verified_on") or "") or None,
		"amount_after_tax": float(res.amount_after_tax or 0),
		"advance_paid": float(res.advance_paid or 0),
		"company": res.company,
		"travel_agent": res.travel_agent,
		"folio_name": folio.name if folio else None,
		"money": money,
		"deposit": _deposit_state(res),
		"security_deposit": _security_deposit_state(res),
		"guest": guest,
		"booker": booker,
		"cancellation": cancellation,
		"actions": {
			"can_check_in": res.status == "Confirmed" and (
				bool(res.room) or uses_member_rooms(res.property, res.room_type)),
			"can_check_out": res.status == "Checked In",
			"can_cancel": res.status in ("Confirmed", "Checked In"),
			"can_amend": res.status in ("Confirmed", "Checked In"),
		},
		# Warnings are NOT capabilities, and they live apart on purpose. A
		# missing ID must never appear in `actions` - the guest is standing
		# at the desk with a physical card, and no arrival gets blocked over
		# an upload that didn't happen. The desk sees it and decides.
		"warnings": {
			"id_document_missing": not res.get("id_document")
			and not res.get("id_document_discarded"),
			"id_unverified": res.precheckin_status == "Submitted",
		},
		"checkin_backfill": _checkin_backfill(res),
	}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Kamra Agent")
def upload_id_document(reservation: str, data: str):
	"""Capture the guest's ID at the counter, when they never uploaded one.

	Same storage as the guest path, different gate: there the token proves
	ownership, here @require_roles does. This exists so that "never block
	check-in" has somewhere to go - the desk flags a missing document, then
	fixes it in the same breath instead of turning the guest away."""
	from kamra.id_documents import store_id_document

	res = frappe.get_doc("Reservation", reservation)
	store_id_document(res, data, source="Desk")
	from kamra.savings import log_action
	log_action("id_document_capture", "Reservation", res.name, res.property,
	           minutes_saved=1,
	           rationale=f"ID captured at the desk for {res.guest_name}")
	return {"ok": True}


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
def id_document_image(reservation: str):
	"""The ID scan as a data URL, for the desk to eyeball.

	Why not just point an <img> at the /private/files/ URL: Frappe would
	authorise that through File.has_permission -> the Reservation's own
	doctype permissions. On a site whose Custom DocPerm rows omit Front Desk
	(as ours do - any custom perm on a doctype REPLACES all its standard
	perms), that check says no, and the desk gets a broken image while a
	Hotel Admin sees it. Kamra's authorization has always lived on the
	endpoint rather than the doctype (see authz.py), so the image is served
	the same way as everything else here: one gate, one rule, works for
	every role the app actually grants.
	"""
	import base64

	url = frappe.db.get_value("Reservation", reservation, "id_document")
	if not url:
		frappe.throw("No ID document on this booking.")
	name = frappe.db.get_value("File", {
		"attached_to_doctype": "Reservation", "attached_to_name": reservation,
		"attached_to_field": "id_document",
	})
	if not name:
		frappe.throw("That ID document is no longer stored.")
	content = frappe.get_doc("File", name).get_content()
	return {
		"data": "data:image/jpeg;base64," + base64.b64encode(content).decode(),
		"captured_on": str(frappe.db.get_value("Reservation", reservation,
		                                       "id_document_on") or ""),
	}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Kamra Agent")
def verify_precheckin(reservation: str):
	"""The desk has held the document against the human and agrees.

	This is the write that finally makes precheckin_status="Verified" real -
	the enum has existed since pre-arrival check-in shipped and no code path
	ever set it. precheckin_submit already refuses to touch a Verified
	booking, so the guest is locked out of rewriting a checked card the
	moment this lands; that guard was clearly written for this."""
	res = frappe.get_doc("Reservation", reservation)
	if res.precheckin_status != "Submitted":
		frappe.throw("Only a submitted pre-check-in can be verified.")
	frappe.db.set_value("Reservation", res.name, {
		"precheckin_status": "Verified",
		"precheckin_verified_by": frappe.session.user,
		"precheckin_verified_on": frappe.utils.now_datetime(),
	})
	from kamra.savings import log_action
	log_action("verify_precheckin", "Reservation", res.name, res.property,
	           minutes_saved=2,
	           rationale=f"Desk verified {res.guest_name}'s ID against the document")
	return {"ok": True, "status": "Verified"}


@frappe.whitelist()
@require_roles("Front Desk", "Night Auditor", "Kamra Agent")
def checkin_context(reservation: str):
	"""Everything the check-in flow needs in one round trip: how complete
	the guest's registration is, the assigned room - or the allocator's
	suggestion plus every room the desk may hand over instead."""
	res = frappe.get_doc("Reservation", reservation)
	guest = frappe.get_doc("Guest", res.guest) if res.guest else None

	room_assigned = None
	if res.room:
		room_assigned = frappe.db.get_value(
			"Room", res.room,
			["name", "room_number", "housekeeping_status"], as_dict=True)

	# a whole villa with no Room of its own takes the property's member
	# rooms at check-in, so the desk checks it in as one unit. A villa type
	# with its own rooms gets the normal picker (one unit per stay).
	from kamra.kamra.doctype.reservation.reservation import (
		entire_place_rooms, uses_member_rooms)
	entire_place = None
	if not res.room and uses_member_rooms(res.property, res.room_type):
		entire_place = {"rooms": [
			r.room_number or r.name
			for r in entire_place_rooms(res.property, res.room_type)]}

	suggestion = None
	rooms = []
	if not res.room and not entire_place and res.status == "Confirmed":
		rooms = [
			{"name": r["name"], "room_number": r["room_number"],
			 "housekeeping_status": r["housekeeping_status"]}
			for r in available_rooms(res.property, res.room_type,
			                         res.check_in_date, res.check_out_date,
			                         group_booking=res.group_booking,
			                         ready_now=1)]
		from kamra.allocation import suggest_allocation
		for p_ in suggest_allocation(
				res.property, str(res.check_in_date))["proposals"]:
			if p_["reservation"] == res.name:
				suggestion = {
					"room": p_["suggested_room"],
					"room_number": p_["room_number"],
					"why": p_["why"],
					"needs_review": p_["needs_review"],
				}
				break

	return {
		"reservation": {
			"name": res.name, "status": res.status,
			"guest": res.guest, "guest_name": res.guest_name,
			"room_type": res.room_type,
			"room_type_name": frappe.db.get_value(
				"Room Type", res.room_type, "room_type_name"),
			"check_in_date": str(res.check_in_date),
			"check_out_date": str(res.check_out_date),
			"adults": res.adults, "children": res.children,
			"planned_check_in_time": str(res.get("planned_check_in_time") or ""),
			"vip": frappe.db.get_value("Guest", res.guest, "vip")
			       if res.guest else 0,
		},
		"readiness": {
			"phone": bool(guest and guest.get("phone")),
			"email": bool(guest and guest.get("email")),
			"id_on_file": bool(guest and guest.get("id_file")),
			"address_on_file": bool(guest and guest.get("address_proof_file")),
			"precheckin_status": res.get("precheckin_status") or "Not sent",
			"link_sent": bool(res.get("precheckin_link_sent")),
		},
		"room_assigned": room_assigned,
		"entire_place": entire_place,
		"suggestion": suggestion,
		"rooms": rooms,
	}


@frappe.whitelist()
@require_roles("Front Desk", "Night Auditor", "Kamra Agent")
def check_in(reservation: str, room: str | None = None):
	"""Check the guest in: the last step of the guided check-in.

	Hard gate: a room must be assigned (or passed here). Soft-required
	steps (ID, deposit, registration card, …) may still be open — the desk
	is warned and finishes them later. kamra.checkin.check_in_readiness
	lists hard blockers and pending backfill. Records who checked the guest
	in and when; a connected door-lock system then makes the keys recorded
	in the Keys step."""
	doc = frappe.get_doc("Reservation", reservation)
	from kamra.checkin import after_check_in, assert_ready, evaluate, soft_pending
	if doc.status == "Confirmed":
		assert_ready(doc, room=room)
	if room:
		doc.room = room
	doc.status = "Checked In"
	doc.save()
	from kamra.savings import log_action
	if doc.room:
		where = frappe.db.get_value("Room", doc.room, "room_number") or doc.room
	else:
		where = "the whole villa"
	log_action("check_in", "Reservation", doc.name, doc.property,
	           rationale=f"{doc.guest_name} into {where}")
	out = {"ok": True, "reservation": doc.name, "room": doc.room,
	       "checked_in_by": frappe.session.user}
	steps, _ctx = evaluate(doc)
	pending = soft_pending(steps)
	if pending:
		out["pending_backfill"] = [
			{"step": s["step_key"], "title": s["title"]} for s in pending]
	keys = after_check_in(doc)
	if keys:
		out["keys"] = keys
	return out


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Kamra Agent")
def walk_in(property: str, room_type: str, room: str, check_out_date: str,
            guest_name: str, phone: str | None = None,
            guest: str | None = None, adults: int = 2, children: int = 0,
            meal_plan: str | None = None, voucher_code: str | None = None,
            company: str | None = None, id_type: str | None = None,
            rate_plan: str | None = None,
            id_number: str | None = None, nationality: str | None = None,
            payment_mode: str | None = None, payment_amount: float = 0,
            payment_reference: str | None = None, pin: str | None = None,
            idempotency_key: str | None = None,
            check_in_time: str | None = None,
            check_out_time: str | None = None,
            blacklist_override_reason: str | None = None,
            credit_override_reason: str | None = None,
            defer_check_in: int = 0,
            booked_via: str | None = None,
            ota_ref: str | None = None,
            ota_total: float = 0,
            ota_commission_pct: float | None = None):
	"""Walk-in in one step: book, register the ID, check into the chosen
	room and take the money - the counter flow that used to be four screens.

	defer_check_in=1 books, assigns the room and takes the money (as an
	advance) but leaves the stay Confirmed, so the desk finishes it in the
	guided check-in. Without it, check_in runs now (room is enough; other
	soft-required steps stay as backfill). The walk-in records the steps it
	does itself (room, who pays, the ID when given).

	It is the same writers chained (create_booking → check_in →
	add_folio_payment), inside one request, so it is all-or-nothing: a
	refused PIN or a room that just sold rolls the booking back too.
	Arrival is always today (calendar, like every new booking - a lagging
	night audit must not turn walk-ins away); a future stay is a normal
	booking, not a walk-in.

	An OTA guest who books and arrives the same day is a walk-in booked
	via that site: booked_via / ota_ref / ota_total / ota_commission_pct
	work as in create_booking (the stay's source is then OTA)."""
	from kamra.crs import assert_property_access
	from kamra.localization import pack_for, payment_modes, validate_id_type
	assert_property_access(property)

	amount = float(payment_amount or 0)
	if amount < 0:
		frappe.throw(_("Payment amount cannot be negative."))
	modes = payment_modes(pack_for(property))
	if amount and payment_mode not in modes:
		frappe.throw(_("Pick a payment mode: {0}.").format(", ".join(modes)))
	validate_id_type(property, id_type)

	check_in_date = nowdate()
	# a same-day check-out is a day-use walk-in (hourly), never the past
	if str(check_out_date) < check_in_date:
		frappe.throw(_("Check-out must be today (day use) or later ({0}).")
		             .format(check_in_date))

	r = frappe.db.get_value("Room", room, ["property", "room_type"],
	                        as_dict=True)
	if not r or r.property != property or r.room_type != room_type:
		frappe.throw(_("Room {0} is not a {1} room here.").format(
			room, room_type))

	# Money guards first, so a locked till refuses before anything is booked
	# rather than after the guest already holds a key.
	if amount:
		from kamra.authz import require_cashier_pin
		from kamra.cashier import require_open_session
		require_cashier_pin(property, pin)
		require_open_session(property)

	booked = create_booking(
		property=property, room_type=room_type,
		check_in_date=check_in_date, check_out_date=check_out_date,
		guest_name=guest_name, phone=phone, guest=guest,
		adults=adults, children=children, meal_plan=meal_plan,
		rate_plan=rate_plan,
		voucher_code=voucher_code, company=company,
		booking_type="Corporate" if company else "Individual",
		source="Walk-in", room=room, assign_room=0,
		idempotency_key=idempotency_key,
		check_in_time=check_in_time, check_out_time=check_out_time,
		blacklist_override_reason=blacklist_override_reason,
		credit_override_reason=credit_override_reason,
		booked_via=booked_via, ota_ref=ota_ref, ota_total=ota_total,
		ota_commission_pct=ota_commission_pct)
	reservation = booked["reservation"]
	folio_filter = {"reservation": reservation, "folio_type": "Guest"}

	if booked.get("idempotent_replay"):
		# a double-tap on the button: report what the first tap did
		return {
			"reservation": reservation, "room": booked["room"],
			"room_number": frappe.db.get_value(
				"Room", booked["room"], "room_number"),
			"folio": frappe.db.get_value("Folio", folio_filter),
			"idempotent_replay": 1,
		}

	id_fields = {k: v for k, v in (("id_type", id_type),
	                               ("id_number", (id_number or "").strip()),
	                               ("nationality", nationality)) if v}
	if id_fields:
		frappe.db.set_value("Guest", booked["guest"], id_fields)

	# what the walk-in counter did itself, recorded under this operator
	from kamra.checkin import record_step
	res_doc = frappe.get_doc("Reservation", reservation)
	record_step(res_doc, "billing_check", "done", note="Walk-in",
	            payer="Company" if company else "Guest")
	if id_fields.get("id_number"):
		record_step(res_doc, "guest_ids", "done", note="Walk-in ID")

	if cint(defer_check_in):
		folio = None
		if amount:
			folio = record_advance(reservation, amount, mode=payment_mode,
			                       reference=payment_reference, pin=pin)["folio"]
		return {
			"reservation": reservation, "room": room,
			"room_number": frappe.db.get_value("Room", room, "room_number"),
			"folio": folio or frappe.db.get_value("Folio", folio_filter),
			"checked_in": 0,
			"amount_after_tax": booked.get("amount_after_tax"),
			"paid": amount,
			**({"credit_warning": booked["credit_warning"]}
			   if booked.get("credit_warning") else {}),
		}

	check_in(reservation, room)
	folio = frappe.db.get_value("Folio", folio_filter)

	if amount:
		add_folio_payment(folio, payment_mode, amount,
		                  reference=payment_reference, pin=pin,
		                  kind="Advance")

	return {
		"reservation": reservation,
		"room": room,
		"room_number": frappe.db.get_value("Room", room, "room_number"),
		"folio": folio,
		"amount_after_tax": booked.get("amount_after_tax"),
		"paid": amount,
		**({"credit_warning": booked["credit_warning"]}
		   if booked.get("credit_warning") else {}),
	}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Kamra Agent")
def upload_occupant_id(reservation: str, row: str, image: str):
	"""ID document for one occupant on the stay register. Same security
	pipeline as every ID image: decoded, re-encoded through PIL (the
	sanitisation boundary), stored private, attached to the reservation
	so checkout retention rules find it."""
	from kamra.id_documents import _decode, _sanitise

	res = frappe.get_doc("Reservation", reservation)
	match = [o for o in (res.get("occupants") or []) if o.name == row]
	if not match:
		frappe.throw("No such occupant row on this stay.")
	occ = match[0]
	from kamra.localization import adult_age, is_minor, minor_id_kept, pack_for
	pack = pack_for(res.property)
	if is_minor(pack, occ.age) and not minor_id_kept(pack, occ.nationality):
		frappe.throw(f"Registration law needs only the name and age of a guest under "
		             f"{adult_age(pack)}; their ID is not kept.")
	content = _sanitise(_decode(image))
	fdoc = frappe.get_doc({
		"doctype": "File",
		"file_name": f"occupant-id-{res.name}-{occ.idx}.jpg",
		"attached_to_doctype": "Reservation",
		"attached_to_name": res.name,
		"is_private": 1,
		"content": content,
	}).insert(ignore_permissions=True)
	frappe.db.set_value("Stay Occupant", occ.name, "id_file", fdoc.file_url,
	                    update_modified=False)
	from kamra.savings import log_action
	log_action("occupant_id_capture", "Reservation", res.name, res.property,
	           rationale=f"ID captured for occupant {occ.full_name}")
	return {"ok": True, "file": fdoc.file_url, "row": occ.name}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Kamra Agent", scope={"guest": "Guest"})
def upload_guest_document(guest: str, kind: str, image: str):
	"""The desk captures or replaces a guest's document while preparing
	the GRC - walk-ins, or a newer copy over last visit's. kind is 'id'
	or 'address'; stored privately, one current copy per slot."""
	if kind not in ("id", "address"):
		frappe.throw("kind must be 'id' or 'address'.")
	if not frappe.db.exists("Guest", guest):
		frappe.throw("Guest not found.")
	field = "id_file" if kind == "id" else "address_proof_file"
	from kamra.public_api import _save_id_image
	url = _save_id_image(guest, image, field)
	frappe.db.set_value("Guest", guest, field, url, update_modified=False)
	return {"ok": True, "file": url}


def _mask_id(value: str | None) -> str | None:
	"""'987654321012' → '••••••••1012' - enough for the register audit
	trail without holding the full number."""
	if not value or len(value) <= 4 or value.startswith("•"):
		return value
	return "•" * (len(value) - 4) + value[-4:]


def _scrub_stay_ids(res):
	"""Verify & Discard retention: after checkout, keep only the last 4
	digits of every ID collected for the stay - and the ID scan itself leaves
	with the guest.

	The scan has to go with the number. Masking the digits while a full
	photograph of the same Aadhaar sits on disk would make the whole setting
	a lie."""
	if frappe.db.get_value("Property", res.property, "id_retention") \
			!= "Verify & Discard":
		return
	for o in res.get("occupants") or []:
		if o.id_number:
			frappe.db.set_value("Stay Occupant", o.name, "id_number",
			                    _mask_id(o.id_number), update_modified=False)
		if o.get("id_file"):
			# occupant scans leave with the party, like every other ID
			for f in frappe.get_all("File", filters={
					"attached_to_doctype": "Reservation",
					"attached_to_name": res.name,
					"file_url": o.id_file}, pluck="name"):
				frappe.delete_doc("File", f, force=True,
				                  ignore_permissions=True)
			frappe.db.set_value("Stay Occupant", o.name, "id_file", None,
			                    update_modified=False)
	guest_id = frappe.db.get_value("Guest", res.guest, "id_number")
	if guest_id:
		frappe.db.set_value("Guest", res.guest, "id_number",
		                    _mask_id(guest_id), update_modified=False)
	from kamra.id_documents import discard_id_document
	discard_id_document(res.name)  # logs and moves on; never breaks checkout
	# the document photos are part of the same promise: verified, discarded
	for field in ("id_file", "address_proof_file"):
		if frappe.db.get_value("Guest", res.guest, field):
			for f in frappe.get_all("File", filters={
					"attached_to_doctype": "Guest",
					"attached_to_name": res.guest,
					"attached_to_field": field}, pluck="name"):
				frappe.delete_doc("File", f, force=True,
				                  ignore_permissions=True)
			frappe.db.set_value("Guest", res.guest, field, None,
			                    update_modified=False)


def cancellation_tier_for(property: str, days_before: int) -> dict | None:
	"""The tier covering a cancellation this many days before arrival.

	Tiers are bands keyed by the days remaining: 7/0%, 3/50%, 0/100% reads
	as free beyond a week, half between three and seven days, nothing back
	inside three. The band with the highest `days_before` at or below the
	days remaining wins. A property with no tiers keeps the single-window
	policy, so nothing changes for anyone who has not set them up.
	"""
	rows = frappe.get_all(
		"Cancellation Tier",
		# a child table is addressed by all three: parent alone would pick up
		# rows from any other doctype that grows a Cancellation Tier table,
		# and quietly change what a guest is charged
		filters={"parenttype": "Property", "parentfield": "cancellation_tiers",
		         "parent": property},
		fields=["days_before", "charge_pct", "label"],
		order_by="days_before desc")
	if not rows:
		return None
	for t in rows:
		if int(days_before) >= int(t.days_before or 0):
			return {"days_before": int(t.days_before or 0),
			        "charge_pct": float(t.charge_pct or 0),
			        "label": t.label}
	# earlier than every band (a late cancellation on a policy whose lowest
	# band is above zero): the strictest one applies
	last = rows[-1]
	return {"days_before": int(last.days_before or 0),
	        "charge_pct": float(last.charge_pct or 0), "label": last.label}


def _cancellation_terms(res):
	"""Policy + fee estimate for a reservation, before anyone commits."""
	from frappe.utils import date_diff

	from kamra.folio import percent_fee, policy_fee

	policy = frappe.db.get_value(
		"Property", res.property,
		["free_cancel_days", "cancellation_fee"], as_dict=True)
	days_before = date_diff(res.check_in_date, nowdate())

	from kamra.pricing import stay_season_rules

	rules = stay_season_rules(res.property, res.check_in_date,
	                          res.check_out_date, res.room_type)
	if rules["non_refundable"]:
		# Peak dates are sold on the understanding that they are not given
		# back; no band of the policy applies.
		return {
			"days_before_arrival": days_before,
			"free_cancel_days": int(policy.free_cancel_days or 0),
			"inside_window": True,
			"fee_basis": "100% of stay",
			"tier": {"days_before": days_before, "charge_pct": 100.0,
			         "label": rules["season"] or "Non-refundable dates"},
			"non_refundable_season": rules["season"],
			"estimated_fee": percent_fee(res, 100),
		}

	tier = cancellation_tier_for(res.property, days_before)
	if tier:
		pct = tier["charge_pct"]
		return {
			"days_before_arrival": days_before,
			"free_cancel_days": int(policy.free_cancel_days or 0),
			"inside_window": pct > 0,
			"fee_basis": f"{pct:g}% of stay",
			"tier": tier,
			"estimated_fee": percent_fee(res, pct) if pct else 0.0,
		}

	inside_window = days_before < int(policy.free_cancel_days or 0)
	basis = policy.cancellation_fee or "None"
	fee = policy_fee(res, basis) if inside_window and basis != "None" else 0.0
	return {
		"days_before_arrival": days_before,
		"free_cancel_days": int(policy.free_cancel_days or 0),
		"inside_window": inside_window,
		"fee_basis": basis,
		"tier": None,
		"estimated_fee": fee,
	}


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
def cancellation_preview(reservation: str):
	"""What cancelling right now would cost - shown before confirming."""
	res = frappe.get_doc("Reservation", reservation)
	return _cancellation_terms(res)


CANCEL_REASONS = ["Guest request", "Change of plans", "Duplicate booking",
                  "Payment failed", "Weather / travel disruption",
                  "Booked elsewhere", "Other"]


def _do_cancel(res, reason: str = "Guest request", note: str | None = None,
               waive_fee: int = 0, issue_credit_note: int = 0) -> dict:
	"""Shared cancel path for desk API and OTA channel manager."""
	from frappe.model.naming import make_autoname

	if reason not in CANCEL_REASONS:
		reason = "Other"
	terms = _cancellation_terms(res)

	summary = (f"Cancel {res.name} · {reason}"
	           + (" · fee waived" if int(waive_fee or 0) else ""))

	fee = 0.0
	if terms["inside_window"] and not int(waive_fee or 0) \
			and terms["fee_basis"] != "None":
		from kamra.folio import post_policy_fee
		tier = terms.get("tier")
		fee = post_policy_fee(
			res, terms["fee_basis"],
			f"Cancellation fee ({terms['fee_basis']})",
			pct=tier["charge_pct"] if tier else None)

	res.status = "Cancelled"
	res.cancellation_reason = reason
	res.cancellation_note = note or ""
	res.cancellation_number = make_autoname("CXL-.YYYY.-.#####")
	res.cancellation_fee = fee
	res.cancelled_on = frappe.utils.now_datetime()
	frappe.flags.kamra_cancelling = True
	try:
		# ignore_permissions: both callers are pre-authorized — the desk wrapper
		# via @require_roles, the OTA webhook worker as a trusted internal caller
		# (it runs as Guest). Validation (villa lockout etc.) still runs.
		res.save(ignore_permissions=True)
	finally:
		frappe.flags.kamra_cancelling = False

	voucher_code = None
	if int(issue_credit_note or 0) == 1:
		credit_amount = max(0.0, float(res.advance_paid or 0) - fee)
		if credit_amount > 0:
			import random
			import string
			code_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
			voucher_code = f"CN-{res.name.split('-')[-1]}-{code_suffix}"

			from frappe.utils import add_days, today
			voucher = frappe.get_doc({
				"doctype": "Discount Voucher",
				"property": res.property,
				"voucher_code": voucher_code,
				"discount_type": "Amount",
				"value": credit_amount,
				"valid_from": today(),
				"valid_to": add_days(today(), 180),
				"max_uses": 1,
				"disabled": 0
			})
			voucher.insert(ignore_permissions=True)

	from kamra.savings import log_action
	log_action("cancel_reservation", "Reservation", res.name, res.property,
	           minutes_saved=8, rationale=summary)

	return {"reservation": res.name,
	        "cancellation_number": res.cancellation_number,
	        "fee": fee, "waived": bool(int(waive_fee or 0)),
	        "credit_note_voucher": voucher_code}


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
def cancel_reservation(reservation: str, reason: str = "Guest request",
                       note: str | None = None, waive_fee: int = 0,
                       agent: str | None = None, issue_credit_note: int = 0):
	"""Cancel a booking, applying the property's cancellation policy:
	free outside the window, else the configured fee lands on the folio.
	Issues a cancellation number the guest can hold on to. Pass
	waive_fee=1 to cancel graciously (logged).

	The cancellation is recorded in the action log.
	"""
	res = frappe.get_doc("Reservation", reservation)
	if res.status != "Confirmed":
		frappe.throw("Only confirmed bookings can be cancelled - "
		             "checked-in stays check out.")
	return _do_cancel(res, reason=reason, note=note, waive_fee=waive_fee,
	                  issue_credit_note=issue_credit_note)


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
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
			"address": ", ".join(filter(None, [  # nosemgrep: frappe-no-functional-code -- filter(None, ...) drops empty address parts; equivalent to a comprehension
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


def _assert_settled(doc, credit_override_reason: str | None = None) -> list[dict]:
	"""A guest never departs owing money, or owed it (issue #132).

	Every night is posted first, because night audit may not have run for the
	last one. Only what the company pays moves to the city ledger: the stay's
	Company folio, or the group master when the group's company has credit.
	The guest's own folios (Guest, Extra) - liquor, extras, anything the
	billing rules left on the guest - are the guest's to settle, so a balance
	there refuses the check-out. Closed folios count too: a bill closed with
	money still on it is still owed. frappe.flags.allow_unsettled_checkout is
	for seed and test scripts only - no endpoint sets it.

	Before anything moves, the property's credit control (kamra.credit)
	checks each company once for everything the stay bills to it. Returns
	the checks that warned or were overridden, for the desk to show.
	"""
	if frappe.flags.allow_unsettled_checkout:
		return []
	from kamra.checkout import settlement_position
	from kamra.folio import post_remaining_nights
	from kamra.localization import pack_for

	post_remaining_nights(doc)
	symbol = pack_for(doc.property).locale(
		frappe.get_cached_doc("Property", doc.property)).get("currency_symbol", "")
	# the one judgement of what is owed either way, shared with the desk's
	# check-out sheet (checkout_context)
	position = settlement_position(doc.name)
	owed, refund = position["owed"], position["refund_due"]
	to_city_ledger = [(f, c) for f, c, _b in position["to_city_ledger"]]
	if owed:
		frappe.throw(_("Cannot check out: {0}{1:,.2f} is still owed. Collect payment "
		               "or transfer it to the city ledger before departure.").format(symbol, owed),
		             title=_("Settle before check-out"))
	if refund:
		frappe.throw(_("Cannot check out: the guest is owed {0}{1:,.2f}. Issue the "
		               "refund before departure.").format(symbol, refund),
		             title=_("Settle before check-out"))
	# nothing moves until the guest's side is settled - and the company's
	# credit is checked once for everything the stay bills to it
	from kamra.credit import enforce_company_credit
	by_company: dict[str, list[str]] = {}
	for folio, company in to_city_ledger:
		by_company.setdefault(company, []).append(folio)
	credit = []
	for company, folios in by_company.items():
		amount = sum(float(frappe.db.get_value("Folio", f, "balance") or 0)
		             for f in folios)
		res = enforce_company_credit(
			company, doc.property, amount,
			override_reason=credit_override_reason,
			context="check-out", reference_doctype="Reservation",
			reference_name=doc.name, exclude_folios=folios)
		if not res["ok"]:
			credit.append(res)
	from kamra.ledger import transfer_to_city_ledger
	for folio, company in to_city_ledger:
		transfer_to_city_ledger(folio, company, credit_check=False)
	return credit



@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Night Auditor", "Kamra Agent")
def checkout_context(reservation: str):
	"""Everything the guided check-out needs in one round trip, without
	changing anything: each folio with its lines and invoice, as it will
	stand once check-out posts the remaining nights (worked out inside a
	savepoint that is always rolled back), bills not on the folio yet (open
	restaurant orders, laundry), a late check-out, what the guest owes
	(`collect`) or is owed (`refunds`: a held security deposit first, through
	its own refund path), what moves to the city ledger and its credit
	check, whether a cashier PIN and an open till are needed, every refusal
	check-out would give (`blockers`, each tied to its step) and the
	property's check-out SOP. check_out judges the balances with the same
	helper (kamra.checkout.settlement_position), so the two never disagree.
	Safe to call again and again: opening the sheet writes nothing."""
	from kamra.checkout import checkout_context as _context
	from kamra.sop import _template_steps, evaluate_sop_steps, next_tip

	ctx = _context(reservation)
	prop = frappe.db.get_value("Reservation", reservation, "property")
	meta, steps = _template_steps(prop, "checkout")
	evaluated = evaluate_sop_steps("checkout", steps, ctx) if meta else []
	ctx["sop"] = {
		"name": meta.get("name") if meta else None,
		"key": "checkout",
		"title": (meta or {}).get("title") or "Checkout",
		"steps": evaluated,
		"next_tip": next_tip(evaluated),
	}
	return ctx


@frappe.whitelist()
@require_roles("Front Desk", "Night Auditor", "Kamra Agent")
def check_out(reservation: str, credit_override_reason: str | None = None):
	"""Check a guest out. What the company pays moves to the city ledger,
	after the property's credit control: a warning comes back in
	`credit_warnings`; a block refuses (CREDIT_BLOCKED) unless Finance or a
	Hotel Admin passes `credit_override_reason` (logged). Agents can't
	override."""
	doc = frappe.get_doc("Reservation", reservation)
	credit = _assert_settled(doc, credit_override_reason)
	# a held security deposit that the settled bill used up is recorded as
	# applied, so the Deposit ledger doesn't keep a departed guest's money
	from kamra.deposit import apply_held_to_bill
	apply_held_to_bill(doc)
	doc.status = "Checked Out"
	doc.save()
	_scrub_stay_ids(doc)
	from kamra.savings import log_action
	log_action("check_out", "Reservation", doc.name, doc.property,
	           rationale=f"{doc.guest_name} departed")
	out = {"ok": True, "reservation": doc.name}
	if credit:
		out["credit_warnings"] = [
			{"company": c["company"], "reasons": c["reasons"],
			 "overridden": bool(c.get("overridden"))} for c in credit]
	return out


HK_SUPERVISOR = "Housekeeping Supervisor"
# who oversees rooms: the supervisor, the desk, and the property's admins
_ROOM_SUPERVISORS = {HK_SUPERVISOR, "Front Desk", "Hotel Admin",
                     "System Manager", "Kamra Agent"}
# what an attendant may set by hand; passing a room (Inspected / Ready) or
# taking it out of order is a supervisor's call
_ATTENDANT_STATUSES = {"Clean", "Dirty"}


def _is_room_supervisor() -> bool:
	return frappe.session.user == "Administrator" or \
		bool(_ROOM_SUPERVISORS & set(frappe.get_roles()))


@frappe.whitelist(methods=["POST"])
@require_roles("Housekeeping", HK_SUPERVISOR, "Front Desk", "Kamra Agent")
def set_housekeeping_status(room: str, status: str):
	"""Change a room's housekeeping status - role, property and DocPerm
	checked (#99): an attendant can mark Clean / Dirty, only a supervisor
	can pass a room or take it out of order, nobody can touch a room of a
	property they aren't assigned to, and removing Write on Room in the
	role permissions actually removes the ability."""
	allowed = {"Clean", "Dirty", "Inspected", "Ready", "Out of Order"}
	if status not in allowed:
		frappe.throw(f"Invalid status. Use one of {sorted(allowed)}")
	r = frappe.db.get_value("Room", room, ["property", "housekeeping_status"],
	                        as_dict=True)
	if not r:
		frappe.throw(_("Room {0} not found.").format(room), frappe.DoesNotExistError)
	from kamra.crs import assert_property_access
	assert_property_access(r.property)
	frappe.has_permission("Room", "write", doc=room, throw=True)
	if status not in _ATTENDANT_STATUSES and not _is_room_supervisor():
		frappe.throw(
			_("Only a housekeeping supervisor can set a room to {0}.").format(status),
			frappe.PermissionError)
	if status == r.housekeeping_status:
		return {"ok": True, "room": room, "status": status}
	frappe.db.set_value("Room", room, "housekeeping_status", status)
	from kamra.savings import log_action
	log_action("room_status", "Room", room, r.property,
	           rationale=f"{r.housekeeping_status or '-'} → {status}")
	return {"ok": True, "room": room, "status": status}


@frappe.whitelist()
@require_roles(HK_SUPERVISOR, "Front Desk", "Kamra Agent")
def room_board(property: str):
	"""Every room at a glance for the housekeeping supervisor: status,
	occupancy, who is in it, and its open task - the board the desk has,
	inside the Housekeeping module (#99)."""
	from kamra.crs import assert_property_access
	assert_property_access(property)
	rooms = frappe.get_all(
		"Room", filters={"property": property},
		fields=["name", "room_number", "room_type", "floor",
		        "housekeeping_status", "occupancy_status"],
		order_by="room_number asc",
	)
	in_house = {
		r.room: r for r in frappe.get_all(
			"Reservation",
			filters={"property": property, "status": "Checked In",
			         "room": ("is", "set")},
			fields=["room", "guest_name", "check_out_date", "is_day_use",
			        "planned_check_out_time"])}
	due_out = str(nowdate())
	tasks = {}
	for t in frappe.get_all(
			"Housekeeping Task",
			filters={"property": property,
			         "status": ("in", ["Pending", "In Progress"])},
			fields=["name", "room", "task_type", "status", "priority",
			        "assigned_to_user", "due_by"],
			order_by="creation asc"):
		tasks.setdefault(t.room, t)
	names = {u.name: u.full_name for u in frappe.get_all(
		"User", filters={"name": ("in", list({t.assigned_to_user for t in
		                                      tasks.values() if t.assigned_to_user}))},
		fields=["name", "full_name"])} if tasks else {}
	for r in rooms:
		stay = in_house.get(r.name)
		r["guest_name"] = stay.guest_name if stay else None
		r["due_out"] = bool(stay and str(stay.check_out_date) <= due_out)
		# a day-use room turns the same day: housekeeping plans on its slot
		r["day_use"] = bool(stay and stay.is_day_use)
		r["etd"] = str(stay.planned_check_out_time)[:5] \
			if stay and stay.planned_check_out_time else None
		t = tasks.get(r.name)
		r["task"] = {
			"name": t.name, "type": t.task_type, "status": t.status,
			"priority": t.priority,
			"assignee": names.get(t.assigned_to_user) or t.assigned_to_user,
		} if t else None
	return {"rooms": rooms, "can_supervise": _is_room_supervisor()}


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
def availability_calendar(property: str, start_date: str | None = None, days: int = 14):
	"""Per room-type, per date: rooms available and the 2-adult rate.
	Powers the calendar view and, later, the agent's availability tool."""
	from kamra.group_blocks import block_hold_by_night
	from kamra.kamra.doctype.reservation.reservation import villa_locked_nights
	from kamra.pricing import occupancy_rate, season_adjust
	from kamra.siu.availability import capacity_by_night, has_active_sius

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

		def _display_rate(date, rt_doc=rt_doc, rt_name=rt.name):
			"""The 2-adult shelf rate for one night. Priced per night rather
			than once for the range, so a day-scoped rule (small-group
			pricing, a weekend season) shows on the right columns."""
			return float(season_adjust(
				property, date, occupancy_rate(rt_doc, 2, 0, date), rt_name))

		# nights the villa <-> room lockout or a group block takes off sale
		locked = villa_locked_nights(property, rt.name, start, end)
		held = block_hold_by_night(property, rt.name, dates)
		if has_active_sius(property, rt.name):
			caps = capacity_by_night(property, rt.name, start, end)
			total = max(caps) if caps else 0
			cells = []
			for i, date in enumerate(dates):
				cap = caps[i] if i < len(caps) else 0
				cells.append({
					"date": str(date),
					"available": 0 if str(date) in locked
					else max(0, cap - held.get(str(date), 0)),
					"rate": _display_rate(date),
				})
		else:
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
			cells = []
			for date in dates:
				d = getdate(date)
				taken = sum(
					1 for b in bookings
					if getdate(b.check_in_date) <= d < getdate(b.check_out_date)
				)
				cells.append({
					"date": str(date),
					"available": 0 if str(date) in locked
					else max(0, total - taken - held.get(str(date), 0)),
					"rate": _display_rate(date),
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
@require_roles("Front Desk", "Kamra Agent")
def tape_chart(property: str, start_date: str | None = None, days: int = 14):
	"""Rooms × dates grid with reservation bars - the front desk's home."""
	from frappe.utils import getdate

	start = getdate(start_date or nowdate())
	days = min(int(days), 31)
	end = add_days(start, days)

	rooms = frappe.get_all(
		"Room", filters={"property": property},
		fields=["name", "room_number", "room_type", "housekeeping_status",
		        "occupancy_status", "floor"],
		order_by="room_type asc, room_number asc",
	)
	# room-type labels (accordion headers show the name, not the Link id)
	rt_names = {
		rt.name: rt.room_type_name for rt in frappe.get_all(
			"Room Type", filters={"property": property},
			fields=["name", "room_type_name"])}
	for r in rooms:
		r["room_type_name"] = rt_names.get(r.room_type, r.room_type)
	bookings = frappe.get_all(
		"Reservation",
		filters={
			"property": property, "room": ("is", "set"),
			"status": ("in", ["Confirmed", "Checked In"]),
			"check_in_date": ("<", end), "check_out_date": (">", start),
		},
		fields=["name", "room", "guest", "guest_name", "status",
		        "check_in_date", "check_out_date", "is_day_use", "adults",
		        "planned_check_in_time", "planned_check_out_time",
		        "precheckin_status", "source", "booking_type", "company",
		        "travel_agent", "group_booking"],
	)
	# VIP flag rides in from the guest profile (one lookup per distinct guest)
	guests = {b.guest for b in bookings if b.guest}
	vip = set(frappe.get_all(
		"Guest", filters={"name": ("in", list(guests)), "vip": 1},
		pluck="name")) if guests else set()
	by_room = {}
	for b in bookings:
		b["vip"] = 1 if b.guest in vip else 0
		by_room.setdefault(b.room, []).append(b)
	# rooms held out of sale (house use, VIP, maintenance) draw as bands too
	blocks = frappe.get_all(
		"Room Block",
		filters={
			"property": property, "block_status": "Active",
			"from_date": ("<", end), "to_date": (">", start),
		},
		fields=["name", "room", "reason", "from_date", "to_date", "note"],
	)
	blocks_by_room = {}
	for k in blocks:
		blocks_by_room.setdefault(k.room, []).append(k)
	for r in rooms:
		r["bookings"] = by_room.get(r.name, [])
		r["blocks"] = blocks_by_room.get(r.name, [])

	# changeover conflicts: same room turns over today and the incoming
	# guest lands before (or within the hk buffer of) the outgoing one
	conflicts = []
	for r in rooms:
		by_date_out = {str(b.check_out_date): b for b in r["bookings"]
		               if b.planned_check_out_time}
		for b in r["bookings"]:
			out = by_date_out.get(str(b.check_in_date))
			if not out or out.name == b.name or not b.planned_check_in_time:
				continue
			if str(b.planned_check_in_time) <= str(out.planned_check_out_time):
				conflicts.append({
					"room": r.name, "room_number": r.room_number,
					"date": str(b.check_in_date),
					"out_res": out.name, "out_guest": out.guest_name,
					"etd": str(out.planned_check_out_time)[:5],
					"in_res": b.name, "in_guest": b.guest_name,
					"eta": str(b.planned_check_in_time)[:5],
				})

	# the day-by-day house position: sold vs capacity vs the overbooking
	# ceiling, plus the demand tier the pricing engine is applying
	from kamra.pricing import demand_tier, forecast_occupancy
	prop_ob = float(frappe.get_cached_doc("Property", property)
	                .get("overbooking_pct") or 0)
	capacity = len(rooms)
	position = []
	for i in range(days):
		d = str(add_days(start, i))
		occ = forecast_occupancy(property, d)
		sold = round(occ * capacity / 100) if capacity else 0
		tier = demand_tier(property, "", d, occupancy=occ)
		position.append({
			"date": d, "sold": sold, "capacity": capacity,
			"occupancy": occ,
			"limit": int(capacity * (1 + prop_ob / 100)),
			"overbooked": sold > capacity,
			"premium_pct": tier["premium_pct"] if tier else 0,
			"min_rate": tier["min_rate"] if tier else 0,
		})

	return {
		"start": str(start), "days": days,
		"dates": [str(add_days(start, i)) for i in range(days)],
		"rooms": rooms,
		"position": position,
		"conflicts": conflicts,
	}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Kamra Agent")
def send_precheckin_link(reservation: str, channel: str = "WhatsApp"):
	"""Send the guest their self check-in link (mints a token if needed). Sends
	over a connected channel when there is one; otherwise returns the link for
	the desk to share. Marks when it went out so the arrivals board can show it."""
	res = frappe.db.get_value(
		"Reservation", reservation,
		["name", "property", "guest", "guest_name", "precheckin_token"],
		as_dict=True)
	if not res:
		frappe.throw("Reservation not found.")
	if not res.precheckin_token:
		res.precheckin_token = frappe.generate_hash(length=32)
		frappe.db.set_value("Reservation", reservation, "precheckin_token",
		                    res.precheckin_token)

	link = f"{frappe.utils.get_url()}/kamra/checkin/{res.precheckin_token}"
	phone = frappe.db.get_value("Guest", res.guest, "phone") if res.guest else None
	sent = False
	if phone:
		try:
			from kamra.agents_channels import send_outbound
			send_outbound(res.property, channel, phone,
			              f"Hi {res.guest_name}, check in early and skip the "
			              f"front-desk queue for your stay: {link}")
			sent = True
		except Exception:
			sent = False  # no live channel; fall back to returning the link

	frappe.db.set_value("Reservation", reservation, "precheckin_link_sent",
	                    frappe.utils.now_datetime())
	from kamra.savings import log_action
	log_action("send_precheckin_link", "Reservation", reservation, res.property,
	           minutes_saved=2,
	           rationale=f"Self check-in link {'sent via ' + channel if sent else 'generated'}")
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional
	return {"ok": True, "link": link, "sent": sent,
	        "channel": channel if sent else None}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Kamra Agent")
def set_stay_times(reservation: str, eta: str | None = None,
                   etd: str | None = None):
	"""Set the planned arrival (ETA) and departure (ETD) times for any stay.
	These drive the hotel-position view on the tape chart: back-to-back
	rooms conflict when the incoming guest lands before the outgoing one
	leaves, and the day's arrival flow is planned around them."""
	frappe.db.set_value("Reservation", reservation, {
		"planned_check_in_time": eta or None,
		"planned_check_out_time": etd or None,
	})
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Kamra Agent")
def set_day_use_times(reservation: str, from_time: str, to_time: str):
	"""Set planned check-in/out times for a day-use booking (drives the hourly
	tape view)."""
	return set_stay_times(reservation, from_time, to_time)


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Kamra Agent")
def position_briefing(property: str, date: str | None = None):
	"""The GM / front-desk position briefing - what Kamra Agent reads out
	at the morning meeting: today's occupancy against the overbooking
	ceiling, arrivals with ETAs, departures with ETDs and balances,
	back-to-back conflicts, the demand tier pricing is applying, and a
	7-day outlook."""
	from frappe.utils import getdate

	from kamra.pricing import demand_tier, forecast_occupancy

	d = str(getdate(date or nowdate()))
	prop = frappe.get_cached_doc("Property", property)
	capacity = frappe.db.count("Room", {"property": property})
	ob_pct = float(prop.get("overbooking_pct") or 0)

	arrivals = frappe.get_all(
		"Reservation",
		filters={"property": property, "check_in_date": d,
		         "status": "Confirmed"},
		fields=["name", "guest_name", "room", "room_type",
		        "planned_check_in_time", "adults", "children",
		        "precheckin_status", "company", "group_booking"],
		order_by="planned_check_in_time asc")
	departures = frappe.get_all(
		"Reservation",
		filters={"property": property, "check_out_date": d,
		         "status": "Checked In"},
		fields=["name", "guest_name", "room",
		        "planned_check_out_time"],
		order_by="planned_check_out_time asc")
	for a in arrivals:
		a["eta"] = str(a.planned_check_in_time)[:5] if a.planned_check_in_time else None
		a["room_no"] = (a.room or "").split("-")[-1] or None
	for dep in departures:
		dep["etd"] = str(dep.planned_check_out_time)[:5] if dep.planned_check_out_time else None
		dep["room_no"] = (dep.room or "").split("-")[-1]
	# what check-out will ask for, unposted nights included
	dep_money = _stay_balances([dep.name for dep in departures])
	for dep in departures:
		dep["balance_due"] = (dep_money.get(dep.name) or {}).get("due", 0.0)

	# back-to-back: departure and arrival share a room today and the times cross
	conflicts = []
	dep_by_room = {x.room: x for x in departures if x.room and x.etd}
	for a in arrivals:
		out = dep_by_room.get(a.room)
		if out and a["eta"] and a["eta"] <= out["etd"]:
			conflicts.append({
				"room_no": out["room_no"], "out_guest": out.guest_name,
				"etd": out["etd"], "in_guest": a.guest_name, "eta": a["eta"]})

	outlook = []
	for i in range(7):
		day = str(add_days(d, i))
		occ = forecast_occupancy(property, day)
		tier = demand_tier(property, "", day, occupancy=occ)
		outlook.append({"date": day, "occupancy": occ,
		                "premium_pct": tier["premium_pct"] if tier else 0,
		                "min_rate": tier["min_rate"] if tier else 0})

	occ_today = outlook[0]["occupancy"]
	return {
		"date": d,
		"occupancy": occ_today,
		"sold": round(occ_today * capacity / 100) if capacity else 0,
		"capacity": capacity,
		"overbooking_pct": ob_pct,
		"overbooking_limit": int(capacity * (1 + ob_pct / 100)),
		"arrivals": arrivals,
		"departures": departures,
		"changeover_conflicts": conflicts,
		"demand_tier": ({"premium_pct": outlook[0]["premium_pct"],
		                 "min_rate": outlook[0]["min_rate"]}
		                if outlook[0]["premium_pct"] or outlook[0]["min_rate"]
		                else None),
		"outlook": outlook,
	}


# Demand tiers are a revenue control: the revenue manager sets them (the
# Settings -> Revenue card), the desk and finance keep the access they had.
HURDLE_ROLES = ("Front Desk", "Finance", "Revenue Manager", "Kamra Agent")


@frappe.whitelist()
@require_roles(*HURDLE_ROLES)
def hurdle_rates(property: str):
	"""The demand tiers: at each occupancy threshold, the premium applied
	and the minimum sell rate enforced. A row with a room type applies to
	that type only and beats the property-wide row at the same threshold."""
	rows = frappe.get_all(
		"Hurdle Rate", filters={"property": property, "disabled": 0},
		fields=["name", "room_type", "occupancy_from", "premium_pct",
		        "min_rate"],
		order_by="occupancy_from asc")
	names = {r.room_type for r in rows if r.room_type}
	labels = dict(frappe.get_all(
		"Room Type", filters={"name": ("in", list(names))},
		fields=["name", "room_type_name"], as_list=True)) if names else {}
	for r in rows:
		r["room_type_name"] = labels.get(r.room_type) if r.room_type else None
	return rows


@frappe.whitelist(methods=["POST"])
@require_roles(*HURDLE_ROLES, scope={"name": "Hurdle Rate"})
def save_hurdle_rate(property: str, occupancy_from: float,
                     premium_pct: float = 0, min_rate: float = 0,
                     room_type: str | None = None, name: str | None = None):
	if not (0 <= float(occupancy_from) <= 100):
		frappe.throw("Occupancy threshold must be between 0 and 100.")
	if float(premium_pct or 0) < 0 or float(min_rate or 0) < 0:
		frappe.throw("Premium and hurdle must not be negative.")
	if room_type:
		from kamra.booking_refs import resolve_room_type
		room_type = resolve_room_type(property, room_type)
	doc = (frappe.get_doc("Hurdle Rate", name) if name
	       else frappe.new_doc("Hurdle Rate"))
	doc.update({
		"property": property, "room_type": room_type or None,
		"occupancy_from": float(occupancy_from),
		"premium_pct": float(premium_pct or 0),
		"min_rate": float(min_rate or 0),
	})
	# the role gate above is the permission; Revenue Manager has no DocPerm
	doc.save(ignore_permissions=True)
	return {"ok": True, "name": doc.name}


@frappe.whitelist(methods=["POST"])
@require_roles(*HURDLE_ROLES, scope={"name": "Hurdle Rate"})
def delete_hurdle_rate(name: str):
	frappe.delete_doc("Hurdle Rate", name, ignore_permissions=True)
	return {"ok": True}


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
def tape_chart_hourly(property: str, date: str | None = None):
	"""Single-day, rooms x hours. Day-use bookings sit at their planned times;
	an overnight stay covering this day shows as a full-width occupied band."""
	from frappe.utils import getdate

	d = getdate(date or nowdate())
	prop = frappe.get_cached_doc("Property", property)

	def _hour(v, default):
		try:
			return int(str(v).split(":")[0])
		except (ValueError, AttributeError):
			return default

	start_h = _hour(prop.get("hourly_view_start"), 6)
	end_h = _hour(prop.get("hourly_view_end"), 23) or 23
	if end_h <= start_h:
		start_h, end_h = 6, 23

	rooms = frappe.get_all(
		"Room", filters={"property": property},
		fields=["name", "room_number", "room_type", "housekeeping_status"],
		order_by="room_type asc, room_number asc")
	rt_names = {rt.name: rt.room_type_name for rt in frappe.get_all(
		"Room Type", filters={"property": property},
		fields=["name", "room_type_name"])}
	for r in rooms:
		r["room_type_name"] = rt_names.get(r.room_type, r.room_type)

	rows = frappe.get_all(
		"Reservation",
		filters={"property": property, "room": ("is", "set"),
		         "status": ("in", ["Confirmed", "Checked In"]),
		         "check_in_date": ("<=", str(d)),
		         "check_out_date": (">=", str(d))},
		fields=["name", "room", "guest", "guest_name", "status", "is_day_use",
		        "check_in_date", "check_out_date", "planned_check_in_time",
		        "planned_check_out_time", "source", "booking_type", "company",
		        "group_booking", "travel_agent"])
	vipset = set(frappe.get_all(
		"Guest", filters={"name": ("in", [r.guest for r in rows if r.guest] or [""]),
		                  "vip": 1}, pluck="name"))
	by_room = {}
	for b in rows:
		b["vip"] = 1 if b.guest in vipset else 0
		# overnight (multi-day) stay that includes today -> full band, no times
		b["overnight"] = 0 if b.is_day_use else 1
		if b.is_day_use:
			def _hhmm(t, fallback):
				if not t:
					return fallback
				parts = str(t).split(":")
				return f"{int(parts[0]):02d}:{parts[1] if len(parts) > 1 else '00'}"
			b["from_hour"] = _hhmm(b.planned_check_in_time, "10:00")
			b["to_hour"] = _hhmm(b.planned_check_out_time, "18:00")
		by_room.setdefault(b.room, []).append(b)
	for r in rooms:
		r["bookings"] = by_room.get(r.name, [])
	return {"date": str(d), "start_hour": start_h, "end_hour": end_h,
	        "rooms": rooms}


@frappe.whitelist()
@require_roles("Front Desk", "Revenue Manager", "Kamra Agent")
def venue_calendar(property: str, start_date: str | None = None, days: int = 14):
	"""Venues × dates with their bookings - the banquet/function diary. Shows
	each venue's schedule so you can see availability and spot conflicts."""
	from frappe.utils import getdate

	start = getdate(start_date or nowdate())
	days = min(int(days), 31)
	end = add_days(start, days)
	venues = frappe.get_all(
		"Venue", filters={"property": property, "disabled": 0},
		fields=["name", "venue_name", "capacity", "base_price"],
		order_by="venue_name asc")
	bookings = frappe.get_all(
		"Venue Booking",
		filters={"property": property,
		         "event_date": ("between", [str(start), str(add_days(end, -1))])},
		fields=["name", "venue", "event_type", "status", "event_date",
		        "start_time", "end_time", "customer_name", "attendees",
		        "quoted_amount", "advance_received"],
		order_by="event_date asc, start_time asc")
	by_venue = {}
	for b in bookings:
		b["start_time"] = str(b.start_time or "")[:5]
		b["end_time"] = str(b.end_time or "")[:5]
		b["event_date"] = str(b.event_date)
		by_venue.setdefault(b.venue, []).append(b)
	for v in venues:
		v["bookings"] = by_venue.get(v.name, [])
	return {
		"start": str(start), "days": days,
		"dates": [str(add_days(start, i)) for i in range(days)],
		"venues": venues,
	}


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
def move_reservation(reservation: str, new_room: str,
                     reason: str | None = None, confirm_price: int = 0,
                     rate_mode: str = "destination",
                     agreed_rate: float | None = None):
	"""Room move / upgrade - mid-stay or before arrival. Overlap guard re-runs.
	One writer for the tape chart, the reservation drawer and the GRC (#113).

	The new room may be a DIFFERENT room type (e.g. Standard -> Suite): the
	reservation's room type follows the room it moves into, so upgrades and
	downgrades are allowed. If the booking auto-prices, the new type's rate
	is quoted and locked - shown first by room_move_preview, and refused
	unless confirm_price=1 when it changes the bill. A same-type move keeps
	the locked nightly rates; a manually-priced booking keeps its amount.

	rate_mode: "destination" (the new type's rate, above), "source" (keep
	what the guest pays now) or "custom" (agreed_rate per night; Revenue
	Manager / admins only)."""
	doc = frappe.get_doc("Reservation", reservation)
	from kamra.crs import assert_property_access
	assert_property_access(doc.property)
	if doc.status not in ("Confirmed", "Checked In"):
		frappe.throw("Only active reservations can be moved.")
	if frappe.db.get_value("Room", new_room, "property") != doc.property:
		frappe.throw(_("Room {0} is not in this property.").format(new_room))
	old_room = doc.room
	old_type = doc.room_type
	old_amount = float(doc.amount_after_tax or 0)
	new_type = frappe.db.get_value("Room", new_room, "room_type")
	_require_price_confirmation(
		_move_price(doc, new_type, rate_mode, agreed_rate), confirm_price)
	doc.room = new_room
	if rate_mode == "source":
		# keep what the guest pays: re-key the lock so the save keeps the rates
		doc.rate_lock_key = doc.rate_lock_key_for(doc.quote_inputs())
	doc.save()
	if doc.status == "Checked In" and old_room and old_room != new_room:
		frappe.db.set_value("Room", old_room,
		                    {"occupancy_status": "Vacant",
		                     "housekeeping_status": "Dirty"})
		frappe.db.set_value("Room", new_room, "occupancy_status", "Occupied")
	from kamra.savings import log_action
	note = f"{old_room} → {new_room}"
	if new_type and new_type != old_type:
		note += f" · {old_type} → {new_type}"
	if abs(float(doc.amount_after_tax or 0) - old_amount) >= 0.01:
		note += (f" · re-priced {old_amount:,.2f} → "
		         f"{float(doc.amount_after_tax or 0):,.2f} (confirmed)")
	if rate_mode != "destination":
		note += f" · rate: {rate_mode}"
	if (reason or "").strip():
		note += f" · {reason.strip()[:140]}"
	log_action("room_move", "Reservation", doc.name, doc.property, rationale=note)
	return {"ok": True, "room": doc.room, "room_type": doc.room_type,
	        "amount_after_tax": float(doc.amount_after_tax or 0)}


def _can_set_rate() -> bool:
	# the same people who may set room rates (set_room_rate)
	return _is_admin() or "Revenue Manager" in frappe.get_roles()


def _move_price(res, new_type: str | None, rate_mode: str,
                agreed_rate: float | None) -> dict:
	"""Price preview for a room move. Leaves res holding the move's price
	inputs (room type, agreed rate) for the save that follows."""
	if rate_mode not in ("destination", "source", "custom"):
		frappe.throw(_("Unknown rate option: {0}").format(rate_mode))
	changes = {} if not new_type or new_type == res.room_type else {"room_type": new_type}
	if rate_mode == "source":
		pv = _reprice_preview(res, **changes)
		pv.update(new_amount=pv["current_amount"], difference=0.0,
		          needs_confirmation=False, reprices=False)
		return pv
	if rate_mode == "custom":
		if not _can_set_rate():
			frappe.throw(_("Only a Revenue Manager or Hotel Admin can enter a new rate."),
			             frappe.PermissionError)
		if float(agreed_rate or 0) <= 0:
			frappe.throw(_("Enter the new nightly rate."))
		if not res.get("auto_price"):
			frappe.throw(_("This booking is priced by hand; change its amount instead."))
		changes["agreed_rate"] = float(agreed_rate)
	else:
		changes["agreed_rate"] = 0  # the destination's own rate card
	return _reprice_preview(res, **changes)


class PriceConfirmationRequired(frappe.ValidationError):
	"""An amendment would change what the guest pays; the caller has to see
	the new price (the *_preview endpoint) and pass confirm_price=1."""


def _reprice_preview(res, **changes) -> dict:
	"""What saving these changes would do to the bill - priced by the same
	code the save runs (Reservation.requote), the booking itself left out of
	the house's occupancy. Nothing is written.

	A booking with manual pricing (auto_price off) keeps its amount; one
	whose price inputs do not change keeps its locked nightly rates."""
	current = float(res.amount_after_tax or 0)
	old_key = res.get("rate_lock_key")
	for k, v in changes.items():
		res.set(k, v)
	out = {"current_amount": current, "new_amount": current,
	       "difference": 0.0, "auto_price": bool(res.get("auto_price")),
	       "reprices": False, "needs_confirmation": False, "nights": []}
	if not res.get("auto_price") or not res.room_type:
		return out
	inputs = res.quote_inputs()
	if res.get("night_rates") and old_key == res.rate_lock_key_for(inputs):
		return out  # same stay, same locked rates
	q = res.requote()
	plan_free = sum(float(n["rate"]) for n in q["nightly"]) or 1.0
	factor = float(q["room_total"]) / plan_free
	new = round(float(q["amount_after_tax"]), 2)
	out.update({
		"new_amount": new,
		"difference": round(new - current, 2),
		"reprices": True,
		"needs_confirmation": abs(new - current) >= 0.01,
		"nights": [{"date": n["date"], "rate": round(float(n["rate"]) * factor, 2),
		            "demand_premium_pct": n.get("demand_premium_pct") or 0}
		           for n in q["nightly"]],
	})
	return out


def _require_price_confirmation(preview: dict, confirm_price) -> None:
	if preview["needs_confirmation"] and not cint(confirm_price):
		frappe.throw(
			_("This change re-prices the stay from {0} to {1}. Show the guest "
			  "the new price, then confirm it (confirm_price=1).").format(
				f"{preview['current_amount']:,.2f}",
				f"{preview['new_amount']:,.2f}"),
			exc=PriceConfirmationRequired, title=_("Confirm the new price"))


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
def room_move_preview(reservation: str, new_room: str,
                      rate_mode: str = "destination",
                      agreed_rate: float | None = None):
	"""What a move would do to the bill before the desk confirms it: a
	same-type swap keeps the price (and the locked nightly rates); an
	upgrade / downgrade on an auto-priced booking is re-quoted at the new
	type's rate by the pricing engine, and move_reservation then needs
	confirm_price=1."""
	res = frappe.get_doc("Reservation", reservation)
	from kamra.crs import assert_property_access
	assert_property_access(res.property)
	new_type = frappe.db.get_value("Room", new_room, "room_type")
	same_type = new_type == res.room_type
	pv = _move_price(res, new_type, rate_mode, agreed_rate)
	return {
		"same_type": same_type,
		"new_room_type": new_type,
		"new_room_type_name": frappe.db.get_value(
			"Room Type", new_type, "room_type_name") if new_type else None,
		"current_amount": pv["current_amount"],
		"new_amount": pv["new_amount"],
		"difference": pv["difference"],
		"needs_confirmation": pv["needs_confirmation"],
		"nights": pv["nights"],
		"auto_price": pv["auto_price"],
		"in_house": res.status == "Checked In",
		"can_set_rate": _can_set_rate(),
	}


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
def movable_rooms(reservation: str, check_in_date: str | None = None,
                  check_out_date: str | None = None):
	"""Every room the booking could move into - across ALL room types, so the
	front desk can upgrade (Standard -> Suite) as well as swap same-type. Each
	room is flagged free/occupied for the dates and carries its type name; the
	booking's current type is listed first."""
	res = frappe.get_doc("Reservation", reservation)
	ci = check_in_date or res.check_in_date
	co = check_out_date or res.check_out_date
	from kamra.crs import assert_property_access
	assert_property_access(res.property)
	rooms = frappe.get_all(
		"Room", filters={"property": res.property},
		fields=["name", "room_number", "room_type", "floor",
		        "housekeeping_status"], order_by="room_number")
	# availability is computed per type; union the free rooms across every type
	types = {r.room_type for r in rooms}
	free = set()
	for rt in types:
		free |= {r.name for r in _available_rooms_raw(res.property, rt, ci, co)}
	type_name = {
		t: (frappe.db.get_value("Room Type", t, "room_type_name") or t)
		for t in types
	}
	out = [
		{"name": r.name, "room_number": r.room_number,
		 "room_type": r.room_type, "floor": r.floor,
		 "housekeeping_status": r.housekeeping_status,
		 "current": r.name == res.room,
		 "room_type_name": type_name.get(r.room_type, r.room_type),
		 # the guest's own current room counts as available to them
		 "free": r.name in free or r.name == res.room,
		 "same_type": r.room_type == res.room_type}
		for r in rooms
	]
	# current type first, then the rest - so a same-type swap is the default and
	# upgrades/downgrades follow
	out.sort(key=lambda r: (not r["same_type"], r["room_type_name"], r["room_number"]))
	return out


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
def amend_stay_preview(reservation: str, check_in_date: str, check_out_date: str):
	"""What new dates would do to the bill, before anything changes: the
	current and new totals and the new nightly rates, priced by the engine
	from today's rules. amend_stay needs confirm_price=1 when the total
	changes."""
	doc = frappe.get_doc("Reservation", reservation)
	from kamra.crs import assert_property_access
	assert_property_access(doc.property)
	return _reprice_preview(doc, check_in_date=check_in_date,
	                        check_out_date=check_out_date)


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
def amend_stay(reservation: str, check_in_date: str, check_out_date: str,
               confirm_price: int = 0):
	"""Extend / shorten a stay; the overlap guard validates the new window.

	An auto-priced stay is re-quoted for its new dates and its nightly
	rates re-locked. That changes what the guest pays, so call
	amend_stay_preview first, show the new price, and pass confirm_price=1;
	without it a change in the total is refused. A manually-priced stay
	keeps its amount."""
	doc = frappe.get_doc("Reservation", reservation)
	from kamra.crs import assert_property_access
	assert_property_access(doc.property)
	if doc.status not in ("Confirmed", "Checked In"):
		frappe.throw("Only active reservations can be amended.")
	old = f"{doc.check_in_date}→{doc.check_out_date}"
	old_amount = float(doc.amount_after_tax or 0)
	_require_price_confirmation(
		_reprice_preview(doc, check_in_date=check_in_date,
		                 check_out_date=check_out_date), confirm_price)
	doc.save()
	from kamra.savings import log_action
	log_action("amend_stay", "Reservation", doc.name, doc.property,
	           rationale=f"{old} → {check_in_date}→{check_out_date}; "
	                     f"total {old_amount:,.2f} → "
	                     f"{float(doc.amount_after_tax or 0):,.2f}"
	                     + (" (new price confirmed)" if cint(confirm_price) else ""))
	return {"ok": True, "nights": doc.nights,
	        "previous_amount": old_amount,
	        "amount_after_tax": doc.amount_after_tax}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Kamra Agent")
def set_late_arrival(reservation: str, late_arrival: int = 1,
                     eta: str | None = None):
	"""Flag (or unflag) a confirmed arrival as arriving late, optionally with
	the ETA the guest gave. With the property's late-arrival protection on,
	the night audit holds a flagged arrival as Due In instead of marking it
	a no-show; the next audit decides."""
	doc = frappe.get_doc("Reservation", reservation)
	from kamra.crs import assert_property_access
	assert_property_access(doc.property)
	if doc.status != "Confirmed":
		frappe.throw(_("Only an arrival that has not checked in can be flagged late."))
	values = {"late_arrival": 1 if cint(late_arrival) else 0}
	if eta is not None:
		values["eta"] = (eta or "").strip()[:60] or None
	frappe.db.set_value("Reservation", doc.name, values)
	from kamra.savings import log_action
	log_action("late_arrival", "Reservation", doc.name, doc.property,
	           rationale=(f"{doc.name} flagged late arrival"
	                      if values["late_arrival"] else
	                      f"{doc.name} late-arrival flag cleared")
	                     + (f" · ETA {values['eta']}" if values.get("eta") else ""))
	return {"ok": True, **values}


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
def booking_options(property: str):
	"""Everything the booking form needs to render its dropdowns."""
	from kamra.channel_manager import channel_commission_pcts
	return {
		"room_types": frappe.get_all(
			"Room Type", filters={"property": property, "disabled": 0},
			fields=["name", "room_type_code", "room_type_name", "base_price",
			        "adults_capacity", "children_capacity", "room_category",
			        "max_extra_beds"],
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
			"Corporate Account", filters={"disabled": 0},
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
		"property": _booking_property_policy(property),
		"ota_channels": _ota_channels(property),
		"ota_commission": channel_commission_pcts(),
	}


def _refuse_taken_ota_ref(property: str, ota_ref: str | None,
                          group_booking: str | None = None) -> None:
	"""One OTA reference books once. The rooms of one multi-room booking
	share it (same group booking); any other booking with it is refused."""
	if not ota_ref:
		return
	for r in frappe.get_all("Reservation", filters={
			"property": property, "ota_ref": ota_ref,
			"status": ["!=", "Cancelled"]}, fields=["name", "group_booking"]):
		if not group_booking or r.group_booking != group_booking:
			frappe.throw(_("OTA booking {0} is already reservation {1}.").format(
				ota_ref, r.name))


def _ota_channels(property: str) -> list[str]:
	"""The common OTAs, then any other site this property has booked through."""
	from kamra.channel_manager import OTA_CHANNELS
	used = frappe.get_all("Reservation", filters={
		"property": property, "source": "OTA", "channel": ["is", "set"]},
		pluck="channel", distinct=True, limit=50)
	return OTA_CHANNELS + sorted({c for c in used if c not in OTA_CHANNELS})


def _booking_property_policy(property: str) -> dict:
	"""Property policy fields for the booking dialog — never null strings."""
	prop = frappe.db.get_value(
		"Property", property,
		["sell_message", "free_cancel_days", "cancellation_fee",
		 "no_show_charge", "deposit_pct", "country", "pets_allowed",
		 "pet_charge", "pet_charge_basis"],
		as_dict=True,
	) or {}
	prop["pets_allowed"] = int(prop.get("pets_allowed") or 0)
	prop["pet_charge"] = float(prop.get("pet_charge") or 0)
	prop["pet_charge_basis"] = prop.get("pet_charge_basis") or "Per stay"
	prop["cancellation_fee"] = prop.get("cancellation_fee") or "None"
	prop["no_show_charge"] = prop.get("no_show_charge") or "None"
	prop["free_cancel_days"] = int(prop.get("free_cancel_days") or 0)
	prop["deposit_pct"] = float(prop.get("deposit_pct") or 0)
	prop["sell_message"] = prop.get("sell_message") or ""
	# drives the dial-code prefix on guest phone inputs
	prop["country"] = prop.get("country") or "India"
	return prop


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
def get_quote(property: str, room_type: str, check_in_date: str,
              check_out_date: str, adults: int = 2, children: int = 0,
              meal_plan: str | None = None, rate_plan: str | None = None,
              voucher_code: str | None = None,
              over_capacity_charge: float = 0, pets: int = 0,
              company: str | None = None):
	"""Price a stay. With a company and no rate plan, the company's
	negotiated plan applies - the same plan create_booking stores."""
	from kamra.booking_refs import (resolve_meal_plan, resolve_rate_plan,
	                                resolve_room_type)
	from kamra.pricing import quote

	# agents name things the way staff do ("Deluxe", "breakfast"); resolve
	# to IDs at this property or refuse with the valid options
	room_type = resolve_room_type(property, room_type)
	meal_plan = resolve_meal_plan(property, meal_plan)
	rate_plan = resolve_rate_plan(property, rate_plan)
	q = quote(property, room_type, check_in_date, check_out_date,
	          int(adults), int(children), meal_plan or None,
	          rate_plan or None, voucher_code or None,
	          over_capacity_charge=float(over_capacity_charge or 0),
	          pets=int(pets or 0), company=company or None)
	if isinstance(q, dict):
		q["cancellation"] = cancellation_outlook(
			property, room_type, check_in_date, check_out_date)
	return q


def _fee_label(basis: str) -> str:
	"""'First Night' -> 'the first night'; '50% of stay' -> '50% of the stay'."""
	if "%" in basis:
		return basis.replace("of stay", "of the stay")
	return f"the {basis.lower()}"


def cancellation_outlook(property: str, room_type: str, check_in_date: str,
                         check_out_date: str) -> dict:
	"""The cancellation terms a quote can promise, decided by the same rules
	cancellation_preview applies when someone actually cancels (season,
	tiers, then the single free window) - evaluated from today, so a window
	that has already closed is never offered as a future date.

	free_now: cancelling today costs nothing. free_until: the last date that
	is still free (None while free_now means free right up to arrival)."""
	from frappe.utils import add_days, date_diff

	from kamra.pricing import stay_season_rules

	days_now = date_diff(check_in_date, nowdate())
	rules = stay_season_rules(property, check_in_date, check_out_date,
	                          room_type)
	if rules["non_refundable"]:
		return {"free_now": False, "free_until": None,
		        "fee_basis": "100% of stay",
		        "fee_label": _fee_label("100% of stay"),
		        "non_refundable_season": rules["season"]
		        or "Non-refundable dates"}

	def charge(d: int) -> tuple[bool, str]:
		"""(charged?, basis) for a cancellation d days before arrival -
		the branch _cancellation_terms takes."""
		tier = cancellation_tier_for(property, d)
		if tier:
			return tier["charge_pct"] > 0, f"{tier['charge_pct']:g}% of stay"
		policy = frappe.db.get_value(
			"Property", property, ["free_cancel_days", "cancellation_fee"],
			as_dict=True)
		basis = policy.cancellation_fee or "None"
		inside = d < int(policy.free_cancel_days or 0)
		return inside and basis != "None", basis

	charged_now, basis_now = charge(days_now)
	if charged_now:
		return {"free_now": False, "free_until": None,
		        "fee_basis": basis_now, "fee_label": _fee_label(basis_now),
		        "non_refundable_season": None}

	# free today: walk towards arrival to the first day that costs. Charges
	# only change where a tier band starts or where the free window ends,
	# so those are the only days worth asking about.
	free_days = int(frappe.db.get_value(
		"Property", property, "free_cancel_days") or 0)
	tiers = frappe.get_all(
		"Cancellation Tier",
		filters={"parenttype": "Property", "parentfield": "cancellation_tiers",
		         "parent": property},
		pluck="days_before")
	edges = {int(t or 0) - 1 for t in tiers} | {free_days - 1, -1}
	for d in sorted((e for e in edges if e < days_now), reverse=True):
		charged, basis = charge(d)
		if charged:
			last_free = add_days(check_in_date, -(d + 1))
			return {"free_now": True, "free_until": str(last_free),
			        "fee_basis": basis, "fee_label": _fee_label(basis),
			        "non_refundable_season": None}
	return {"free_now": True, "free_until": None, "fee_basis": "None",
	        "fee_label": "", "non_refundable_season": None}


def _find_or_create_guest(guest_name: str, phone: str | None,
                          property: str | None = None):
	if phone:
		existing = frappe.db.get_value("Guest", {"phone": phone})
		if existing:
			return existing
	parts = guest_name.strip().split(" ", 1)
	# the likely nationality follows the property's country, not India's
	from kamra.localization import pack_for
	nationality = getattr(pack_for(property), "DEFAULT_NATIONALITY", None) \
		if property else None
	guest = frappe.get_doc({
		"doctype": "Guest",
		"first_name": parts[0],
		"last_name": parts[1] if len(parts) > 1 else "",
		"phone": phone,
		"nationality": nationality or None,
	}).insert(ignore_permissions=True)
	return guest.name


def _blacklist_gate(guest: str, property: str, override_reason: str | None):
	"""A blacklisted guest is refused unless a Hotel Admin confirms with a
	reason. The override is scoped to this guest for this request only and
	is logged; Reservation.validate_blacklist still refuses everyone else."""
	flagged, reason = frappe.db.get_value(
		"Guest", guest, ["blacklisted", "blacklist_reason"]) or (0, None)
	if not flagged:
		return
	override_reason = (override_reason or "").strip()
	if not override_reason:
		return  # validate_blacklist refuses with the standing reason
	if not _is_admin():
		frappe.throw(_("Only a Hotel Admin can book a blacklisted guest."),
		             frappe.PermissionError)
	frappe.flags.kamra_blacklist_override = guest
	from kamra.savings import log_action
	log_action(
		action_type="blacklist_override",
		reference_doctype="Guest",
		reference_name=guest,
		property=property,
		rationale=f"Booked despite blacklist ({reason or 'no reason'}): {override_reason}",
	)


# How long an identical agent booking counts as a retry of the first one.
from kamra.reservation_state import AGENT_DUPLICATE_WINDOW_MINUTES  # noqa: E402


def agent_channel() -> str | None:
	"""The channel of the agent tool call running now ("MCP" from the MCP
	registry, "Chat" from the in-app copilot), or None for a human caller.

	frappe.flags.kamra_agent_call holds the channel name; a bare True (an
	older caller) still counts as an agent call, logged as "API"."""
	flag = getattr(frappe.flags, "kamra_agent_call", None)
	if not flag:
		return None
	return flag if isinstance(flag, str) else "API"


def _booking_result(doc) -> dict:
	"""create_booking's response for a reservation document."""
	return {
		"reservation": doc.name,
		"room": doc.room,
		"guest": doc.guest,
		"amount_after_tax": doc.amount_after_tax,
		"discount": doc.discount_amount,
		"status": doc.status,
	}


def _booking_replay(reservation: str) -> dict:
	"""create_booking's response for a booking that already exists."""
	out = _booking_result(frappe.get_doc("Reservation", reservation))
	out["idempotent_replay"] = 1
	return out


def _collapse(value) -> str:
	"""Trimmed, inner whitespace collapsed - how two spellings of one name
	are compared."""
	return " ".join(str(value or "").split())


def _assert_key_matches(reservation: str, key: str, room_type: str,
                        check_in_date: str, check_out_date: str, *,
                        guest: str | None, guest_name: str | None,
                        phone: str | None) -> None:
	"""An idempotency_key replays only the booking it was first used for.
	The same key on a different stay or guest is a caller bug: refuse it
	rather than hand back someone else's reservation as a success."""
	r = frappe.db.get_value(
		"Reservation", reservation,
		["room_type", "check_in_date", "check_out_date", "guest", "guest_name"],
		as_dict=True)
	same_stay = (r.room_type == room_type
	             and getdate(r.check_in_date) == getdate(check_in_date)
	             and getdate(r.check_out_date) == getdate(check_out_date))
	if guest:
		same_guest = r.guest == guest
	else:
		# the stored name comes from the guest profile; a phone match covers
		# a profile found by phone under a different spelling
		same_guest = (
			_collapse(r.guest_name).casefold() == _collapse(guest_name).casefold()
			or bool(phone and str(phone).strip() and _collapse(
				frappe.db.get_value("Guest", r.guest, "phone")) == _collapse(phone)))
	if not (same_stay and same_guest):
		frappe.throw(
			_("This idempotency_key ({0}) was already used for a different "
			  "booking ({1}: {2}, {3} to {4}, {5}). Use a new key for a new "
			  "booking.").format(key, reservation, r.room_type,
			                     r.check_in_date, r.check_out_date,
			                     r.guest_name or r.guest),
			title=_("Idempotency key already used"))


def _recent_agent_duplicate(property: str, room_type: str, check_in_date: str,
                            check_out_date: str, *, guest: str | None,
                            guest_name: str | None, phone: str | None,
                            meal_plan: str | None, rate_plan: str | None,
                            adults: int, children: int,
                            waitlist: int = 0) -> str | None:
	"""A reservation identical to this one (same guest, property, room type,
	dates, meal plan, rate plan and party size) created within the duplicate
	window - or None. Only live stays count (a waitlist call matches only
	Waitlist stays): an Inquiry or a cancelled booking is not a retry.

	The guest is matched by profile when given, else by phone, else by the
	name (trimmed, whitespace collapsed; the column collation ignores case):
	without a phone every call creates a new guest profile, so the profile
	alone can't catch a retry."""
	from frappe.utils import add_to_date

	from kamra.reservation_state import LIVE_STATUSES

	since = add_to_date(now_datetime(), minutes=-AGENT_DUPLICATE_WINDOW_MINUTES)
	conds = ["r.property = %(property)s", "r.room_type = %(room_type)s",
	         "r.check_in_date = %(ci)s", "r.check_out_date = %(co)s",
	         "r.creation >= %(since)s",
	         "IFNULL(r.meal_plan, '') = %(meal_plan)s",
	         "IFNULL(r.rate_plan, '') = %(rate_plan)s",
	         "r.adults = %(adults)s", "r.children = %(children)s"]
	values = {"property": property, "room_type": room_type,
	          "ci": getdate(check_in_date), "co": getdate(check_out_date),
	          "since": since, "meal_plan": meal_plan or "",
	          "rate_plan": rate_plan or "", "adults": int(adults or 0),
	          "children": int(children or 0)}
	if waitlist:
		conds.append("r.status = 'Waitlist'")
	else:
		conds.append("r.status IN %(live)s")
		values["live"] = LIVE_STATUSES
	if guest:
		conds.append("r.guest = %(guest)s")
		values["guest"] = guest
	elif phone and str(phone).strip():
		conds.append("g.phone = %(phone)s")
		values["phone"] = str(phone).strip()
	elif _collapse(guest_name):
		conds.append(
			"REGEXP_REPLACE(TRIM(r.guest_name), '[[:space:]]+', ' ') = %(gname)s")
		values["gname"] = _collapse(guest_name)
	else:
		return None
	rows = frappe.db.sql(  # nosemgrep: frappe-sql-format-injection -- conds holds only fixed SQL fragments written above; every value is bound through `values`
		f"""SELECT r.name FROM `tabReservation` r
		JOIN `tabGuest` g ON g.name = r.guest
		WHERE {' AND '.join(conds)}
		ORDER BY r.creation DESC LIMIT 1""",
		values,
	)
	return rows[0][0] if rows else None


def _stay_slot(check_in_date, check_out_date, t_in=None, t_out=None):
	"""Normalise a booking's planned times to HH:MM:SS (or None). A day-use
	slot must end after it starts - the room is only the guest's for those
	hours."""
	def norm(v):
		if not v:
			return None
		parts = str(v).strip().split(":")
		try:
			h, m = int(parts[0]), int(parts[1] if len(parts) > 1 else 0)
		except ValueError:
			frappe.throw(_("Times are HH:MM, e.g. 10:00."))
		if not (0 <= h <= 23 and 0 <= m <= 59):
			frappe.throw(_("Times are HH:MM, e.g. 10:00."))
		return f"{h:02d}:{m:02d}:00"
	t_in, t_out = norm(t_in), norm(t_out)
	if str(check_in_date) == str(check_out_date) and t_in and t_out \
			and t_out <= t_in:
		frappe.throw(_("A day-use slot must end after it starts."))
	return t_in, t_out


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
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
                   waitlist: int = 0,
                   addons=None,
                   guest_category: str | None = None,
                   stay_details=None,
                   instructions=None,
                   room: str | None = None,
                   status: str | None = None,
                   idempotency_key: str | None = None,
                   hold_expires_on: str | None = None,
                   over_capacity_reason: str | None = None,
                   over_capacity_guests: int = 0,
                   over_capacity_charge: float = 0,
                   check_in_time: str | None = None,
                   check_out_time: str | None = None,
                   blacklist_override_reason: str | None = None,
                   pets: int = 0,
                   credit_override_reason: str | None = None,
                   booked_via: str | None = None,
                   ota_ref: str | None = None,
                   ota_total: float = 0,
                   ota_commission_pct: float | None = None,
                   marketing_consent: int = 0):
	"""One-call booking: attach to an existing guest profile when given,
	else dedup by phone / create one. Optional auto room assignment,
	voucher applied, price computed by the engine.

	waitlist=1 parks the stay with no room and status Waitlist - for dates
	that are sold out or restricted; promote it later when a room frees.

	status / idempotency_key / hold_expires_on support Instant public booking
	(ADR-006 / ADR-007). Desk callers leave them unset → Confirmed.

	Day use: check_out_date == check_in_date books a same-day stay, priced
	by the quote engine (one billable date). check_in_time / check_out_time
	(HH:MM) are its slot - they place it on the hourly tape and tell
	housekeeping when the room turns; on an overnight stay they are the
	ETA / ETD.

	A stay billed to a company on credit runs the property's credit control
	(kamra.credit) for its amount: a warning comes back as `credit_warning`;
	a block refuses (CREDIT_BLOCKED) unless Finance or a Hotel Admin passes
	`credit_override_reason`, which is logged. Agents can't override."""
	from kamra.crs import assert_property_access
	from kamra.reservation_state import find_by_idempotency, lock_sius_for_booking
	assert_property_access(property)
	check_in_time, check_out_time = _stay_slot(
		check_in_date, check_out_date, check_in_time, check_out_time)

	# names ("Deluxe", "Breakfast") or codes resolve to this property's IDs;
	# unknown / ambiguous values are refused with the valid options
	from kamra.booking_refs import (resolve_meal_plan, resolve_rate_plan,
	                                resolve_room_type)
	room_type = resolve_room_type(property, room_type)
	meal_plan = resolve_meal_plan(property, meal_plan)
	rate_plan = resolve_rate_plan(property, rate_plan)

	# "MCP" / "Chat" while an agent tool call runs; its bookings are AI Agent
	# bookings whichever agent surface made them
	channel = agent_channel()
	if channel and source == "Manual":
		source = "AI Agent"

	# Booked via an OTA and keyed in from its email: tag the site and its
	# reference, and keep the price the OTA charged (as a channel manager
	# booking does). One reference books once. The OTA's commission is its
	# default % (its Travel Agent record of type OTA) unless the desk says.
	from kamra.channel_manager import (canonical_channel,
	                                   channel_commission_pcts,
	                                   lock_channel_rates, set_ota_commission)
	via = canonical_channel(booked_via)
	ota_ref = (ota_ref or "").strip() or None
	if via:
		source = "OTA"
		if ota_commission_pct in (None, ""):
			ota_commission_pct = channel_commission_pcts().get(via)
	_refuse_taken_ota_ref(property, ota_ref, group_booking)

	key = (idempotency_key or "").strip() or None
	if key:
		existing = find_by_idempotency(property, key)
		if existing:
			_assert_key_matches(existing, key, room_type, check_in_date,
			                    check_out_date, guest=guest,
			                    guest_name=guest_name, phone=phone)
			return _booking_replay(existing)

	# An agent that retries a tool call (timeout, lost response, a model
	# that repeats itself) must not book the guest twice. Without a key,
	# an identical agent booking made moments ago is returned instead of a
	# second one. Desk bookings (several identical rooms for one party) are
	# never subject to this guard, nor are group pickups: several identical
	# rooms for one party is what a block is, and the block bounds it.
	if not key and not group_booking and (channel or source == "AI Agent"):
		recent = _recent_agent_duplicate(
			property, room_type, check_in_date, check_out_date,
			guest=guest, guest_name=guest_name, phone=phone,
			meal_plan=meal_plan, rate_plan=rate_plan,
			adults=int(adults or 0), children=int(children or 0),
			waitlist=int(waitlist or 0))
		if recent:
			from kamra.savings import log_action
			log_action(
				"agent_duplicate_booking_blocked", "Reservation", recent,
				property,
				rationale=(f"Identical booking for {guest_name} ({room_type} "
				           f"{check_in_date}→{check_out_date}) was already made "
				           f"in the last {AGENT_DUPLICATE_WINDOW_MINUTES} minutes; "
				           f"returned {recent} instead of booking again"),
				channel=channel or "API")
			out = _booking_replay(recent)
			out["duplicate_of_recent"] = 1
			out["note"] = (
				f"An identical booking ({recent}) was made in the last "
				f"{AGENT_DUPLICATE_WINDOW_MINUTES} minutes, so no new "
				"reservation was created. To book another identical room on "
				"purpose, call again with a new idempotency_key.")
			return out

	if guest:
		if not frappe.db.exists("Guest", guest):
			frappe.throw(f"Guest profile {guest} not found.")
	else:
		guest = _find_or_create_guest(guest_name, phone, property)
	_blacklist_gate(guest, property, blacklist_override_reason)
	if guest_category:
		frappe.db.set_value("Guest", guest, "guest_category", guest_category)
		if guest_category == "VIP":
			frappe.db.set_value("Guest", guest, "vip", 1)

	voucher = None
	if voucher_code:
		from frappe.utils import date_diff

		from kamra.pricing import validate_voucher
		voucher = validate_voucher(
			property, voucher_code,
			date_diff(check_out_date, check_in_date),
		).name

	if not room and int(assign_room) and not int(waitlist or 0):
		# Serialize hybrid / SIU capacity before reading free rooms (ADR-007).
		lock_sius_for_booking(property, room_type)
		# a group pickup books against its own block, not general inventory
		free = available_rooms(property, room_type, check_in_date,
		                       check_out_date, group_booking=group_booking)
		if free and getdate(check_in_date) <= getdate(nowdate()):
			# arriving today: hand out a room nobody is still checked in to
			# before one whose guest departs today but has not left yet
			occupied = in_house_rooms(property)
			free = sorted(free, key=lambda r: r["name"] in occupied)
		# SIU path returns plain dicts; legacy SQL returns frappe._dict.
		room = free[0]["name"] if free else None
	elif not int(waitlist or 0):
		lock_sius_for_booking(property, room_type)

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
		"pets": max(0, int(pets or 0)),
		"meal_plan": meal_plan or None,
		"rate_plan": rate_plan or None,
		"voucher": voucher,
		"booking_type": booking_type,
		"company": company or None,
		"group_booking": group_booking or None,
		"source": source,
		"is_day_use": 1 if check_in_date == check_out_date else 0,
		"planned_check_in_time": check_in_time,
		"planned_check_out_time": check_out_time,
		"travel_agent": travel_agent or None,
		"booked_by_name": booked_by_name or None,
		"booked_by_phone": booked_by_phone or None,
		"booker_relation": booker_relation or None,
		"contact_preference": contact_preference
			or ("Booker" if booked_by_name else "Guest"),
		"auto_price": 1,
		"idempotency_key": key,
		"hold_expires_on": hold_expires_on or None,
	})
	if int(waitlist or 0):
		doc.status = "Waitlist"
	elif status:
		doc.status = status
	if via:
		doc.channel, doc.ota_ref = via, ota_ref
		if float(ota_total or 0) > 0:
			doc.auto_price = 0
			doc.amount_after_tax = float(ota_total)
			lock_channel_rates(doc, float(ota_total))

	# Booking a party above the room's capacity is a decision someone makes
	# by arrangement; the reason is what records who agreed it, and the
	# reservation refuses without one.
	if (over_capacity_reason or "").strip():
		doc.over_capacity_reason = over_capacity_reason.strip()
	if over_capacity_guests:
		doc.over_capacity_guests = int(over_capacity_guests)
	if over_capacity_charge:
		doc.over_capacity_charge = float(over_capacity_charge)

	# extras chosen at booking - priced from the Experience, posted to the
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

	# Arrival, transport, purpose and service flags - the details a real
	# front desk collects. Whitelisted so a caller can't set arbitrary fields.
	_STAY_KEYS = {
		"arrival_mode", "arrival_ref", "arrival_datetime", "pickup_required",
		"pickup_note", "departure_mode", "departure_ref", "departure_datetime",
		"drop_required", "drop_note", "purpose", "extra_beds", "infants",
		"valet_parking", "early_checkin", "late_checkout",
	}
	if isinstance(stay_details, str):
		stay_details = frappe.parse_json(stay_details)
	for k, v in (stay_details or {}).items():
		if k in _STAY_KEYS and v not in (None, ""):
			doc.set(k, v)

	# Special instructions, each routed to the team that acts on it.
	if isinstance(instructions, str):
		instructions = frappe.parse_json(instructions)
	for ins in instructions or []:
		if ins.get("instruction"):
			doc.append("instructions", {
				"department": ins.get("department") or "Front Desk",
				"instruction": ins["instruction"],
			})
	# One-tap service flags become instructions for the right department, so
	# a pickup or a valet request reaches the people who fulfil it.
	for flag, dept, text in (
		("pickup_required", "Transport", "Airport / station pickup"),
		("drop_required", "Transport", "Airport / station drop"),
		("valet_parking", "Concierge", "Valet parking"),
		("early_checkin", "Front Desk", "Early check-in requested"),
		("late_checkout", "Front Desk", "Late check-out requested"),
	):
		if doc.get(flag):
			note = text
			if flag == "pickup_required" and doc.get("arrival_ref"):
				note = f"{text} · {doc.arrival_ref}"
			doc.append("instructions", {
				"department": dept, "instruction": note, "status": "Open",
			})

	# A company on credit: check its credit for this stay. The booking is
	# priced on insert, so it is checked straight after, inside a savepoint
	# that a refusal rolls back (a group loop that catches the error must
	# not keep the room).
	from kamra.credit import credit_applies, credit_policy
	gate_credit = (credit_applies(company) and doc.status != "Waitlist"
	               and credit_policy(property) != "off")
	# Concurrent bookings race on tabSeries (RES-YYYY-#####); retry instead
	# of returning HTTP 500 QueryDeadlockError (#344).
	credit = None
	for attempt in (1, 2, 3):
		try:
			if gate_credit:
				frappe.db.savepoint("kamra_credit_gate")
			doc.insert(ignore_permissions=False)
			if gate_credit:
				from kamra.credit import enforce_company_credit
				try:
					credit = enforce_company_credit(
						company, property, float(doc.amount_after_tax or 0),
						override_reason=credit_override_reason,
						context="booking", reference_doctype="Reservation",
						reference_name=doc.name)
				except Exception:
					frappe.db.rollback(save_point="kamra_credit_gate")
					raise
			break
		except frappe.QueryDeadlockError:
			frappe.db.rollback()
			if attempt == 3:
				raise
			# Guest may have been created in the rolled-back transaction
			if not frappe.db.exists("Guest", guest):
				guest = _find_or_create_guest(guest_name, phone, property)
			payload = doc.as_dict()
			payload.pop("name", None)
			payload["guest"] = guest
			doc = frappe.get_doc(payload)
	if via:
		set_ota_commission(doc, ota_commission_pct)

	from kamra.savings import log_action
	log_action(
		action_type="create_reservation",
		reference_doctype="Reservation",
		reference_name=doc.name,
		property=property,
		minutes_saved=8 if source == "AI Agent" else 0,
		rationale=f"Booked {room_type} {check_in_date}→{check_out_date} for {guest_name}",
		channel=channel or ("API" if source == "AI Agent" else "Desk"),
	)
	if cint(marketing_consent):
		from kamra.privacy import set_marketing_consent
		set_marketing_consent(doc.guest, 1, "Desk", property)
	out = _booking_result(doc)
	if credit and not credit["ok"]:
		out["credit_warning"] = {
			"company": company, "reasons": credit["reasons"],
			"overridden": bool(credit.get("overridden"))}
	return out


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent", "Revenue Manager")
def waitlist(property: str):
	"""All waitlisted stays for the property, by arrival date."""
	return frappe.get_all(
		"Reservation",
		filters={"property": property, "status": "Waitlist"},
		fields=["name", "guest_name", "room_type", "check_in_date",
		        "check_out_date", "nights", "adults", "children",
		        "amount_after_tax"],
		order_by="check_in_date asc")


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
def promote_waitlist(reservation: str):
	"""Promote a waitlisted stay to Confirmed when a room is free for its
	dates. Assigns the first free room; the overlap guard validates it."""
	doc = frappe.get_doc("Reservation", reservation)
	if doc.status != "Waitlist":
		frappe.throw("Only waitlisted reservations can be promoted.")
	free = available_rooms(doc.property, doc.room_type,
	                       doc.check_in_date, doc.check_out_date)
	if not free:
		frappe.throw("Still no room free for those dates.")
	doc.room = free[0]["name"]
	doc.status = "Confirmed"
	doc.save()
	from kamra.savings import log_action
	log_action("waitlist_promote", "Reservation", doc.name, doc.property,
	           rationale=f"Promoted from waitlist into {doc.room}")
	return {"ok": True, "reservation": doc.name, "room": doc.room}


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
def waitlist_ready(property: str):
	"""Waitlisted stays that CAN now be accommodated - a room is free for
	their dates. This is the signal the voice/WhatsApp agent watches so it
	can proactively reach the guest the moment a room opens."""
	ready = []
	for r in frappe.get_all(
			"Reservation",
			filters={"property": property, "status": "Waitlist"},
			fields=["name", "guest", "guest_name", "room_type",
			        "check_in_date", "check_out_date", "nights",
			        "adults", "children", "amount_after_tax"]):
		free = available_rooms(property, r.room_type,
		                       r.check_in_date, r.check_out_date)
		if free:
			r["rooms_free"] = len(free)
			r["phone"] = frappe.db.get_value(
				"Guest", r.guest, "phone") if r.guest else None
			ready.append(r)
	return ready


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
def create_group_booking(property: str, group_name: str, check_in_date: str,
                         check_out_date: str, rooms: str | list,
                         guest_name: str, phone: str | None = None,
                         company: str | None = None,
                         meal_plan: str | None = None,
                         rate_plan: str | None = None,
                         booked_via: str | None = None,
                         ota_ref: str | None = None,
                         ota_total: float = 0,
                         ota_commission_pct: float | None = None):
	"""Create a Group Booking plus one reservation per requested room.
	`rooms` = [{"room_type": <name>, "count": 2}, ...] (JSON string ok).

	Booked via an OTA (see create_booking): every room carries the site and
	the one OTA reference, and the sold total (`ota_total`, tax included) is
	split across the rooms in proportion to their rate-card prices, each
	room locked to its share."""
	if isinstance(rooms, str):
		rooms = json.loads(rooms)
	lines = [spec for spec in rooms for _n in range(int(spec.get("count", 1)))]

	ota_ref = (ota_ref or "").strip() or None
	_refuse_taken_ota_ref(property, ota_ref)  # before the group is made
	shares = [0.0] * len(lines)
	total = float(ota_total or 0) if booked_via else 0
	if total > 0 and lines:
		weights = [float(get_quote(
			property, spec["room_type"], check_in_date, check_out_date,
			adults=int(spec.get("adults", 2)),
			children=int(spec.get("children", 0)),
			meal_plan=spec.get("meal_plan") or meal_plan, rate_plan=rate_plan,
			company=company).get("amount_after_tax") or 0) for spec in lines]
		if not sum(weights):
			weights = [1.0] * len(lines)
		for i, w in enumerate(weights):
			shares[i] = round(total * w / sum(weights), 2)
		shares[-1] = round(total - sum(shares[:-1]), 2)  # rounding

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
	for spec, share in zip(lines, shares, strict=True):
		try:
			res = create_booking(
				property=property,
				room_type=spec["room_type"],
				room=spec.get("room"),
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
				booked_via=booked_via,
				ota_ref=ota_ref,
				ota_total=share,
				ota_commission_pct=ota_commission_pct,
			)
			created.append(res["reservation"])
		except Exception as e:
			skipped.append({"room_type": spec["room_type"], "reason": str(e)})

	return {"group_booking": group.name, "created": created, "skipped": skipped}


def _block_hold(property: str, room_type: str, check_in_date: str,
                check_out_date: str, for_group: str | None = None) -> int:
	"""Rooms held by confirmed group blocks overlapping the window that
	haven't been picked up yet (kamra.group_blocks). A block stops holding
	once its cutoff passes; the scheduler then writes the release record.
	The group's own pickups see their held rooms, not a shortage."""
	from kamra.group_blocks import block_hold
	return block_hold(property, room_type, check_in_date, check_out_date,
	                  for_group=for_group)


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent", "Revenue Manager", "Hotel Admin")
def inventory_availability(property: str, check_in_date: str, check_out_date: str,
                           room_type: str | None = None, siu: str | None = None,
                           include_reasons: int = 0):
	"""Sellable Unit availability (ADR-003). Prefer this over ad-hoc room SQL."""
	from kamra.siu.availability import availability as avail
	return avail(
		property,
		siu=siu or None,
		room_type=room_type or None,
		check_in_date=check_in_date,
		check_out_date=check_out_date,
		include_reasons=bool(int(include_reasons or 0)),
	)


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
def available_rooms(property: str, room_type: str, check_in_date: str,
                    check_out_date: str, group_booking: str | None = None,
                    ready_now: int = 0):
	"""Rooms of a type with no overlapping live reservation - the same
	logic the double-booking guard enforces, exposed as a query. Confirmed
	group blocks hold their unsold rooms out of general sale; pass the
	group to book against its own block.

	A stay may start on another's departure date, so a room whose guest
	departs today is "free" for a booking. Pass ready_now=1 when the guest
	is being put in the room now (check-in, walk-in, allocation for today):
	a room whose occupant is still Checked In is then left out until they
	check out - the same rule Reservation.validate_room_vacant enforces."""
	# Prefer Sellable Unit availability when SIUs exist for this type
	# (ADR-003). Fall back to legacy Room SQL during migration.
	rooms = None
	from kamra.siu.availability import has_active_sius
	if has_active_sius(property, room_type):
		from kamra.siu.availability import available_rooms_via_siu
		rooms = available_rooms_via_siu(
			property, room_type, check_in_date, check_out_date
		)
	if rooms is None:
		rooms = _available_rooms_raw(property, room_type, check_in_date,
		                             check_out_date)
	if int(ready_now or 0) and getdate(check_in_date) <= getdate(nowdate()):
		occupied = in_house_rooms(property)
		rooms = [r for r in (rooms or []) if r["name"] not in occupied]
	hold = _block_hold(property, room_type, check_in_date, check_out_date,
	                   for_group=group_booking)
	if hold:
		rooms = rooms[:max(0, len(rooms) - hold)]
	# Always frappe._dict so callers can use row["name"] or row.name.
	return [frappe._dict(r) for r in (rooms or [])]


def in_house_rooms(property: str) -> set[str]:
	"""Rooms a guest is checked in to right now, whatever their departure
	date says - they stay occupied until the guest checks out."""
	return set(frappe.get_all(
		"Reservation",
		filters={"property": property, "status": "Checked In",
		         "room": ("is", "set"),
		         "check_in_date": ("<=", nowdate())},
		pluck="room"))


def _available_rooms_raw(property: str, room_type: str, check_in_date: str,
                         check_out_date: str):
	# villa <-> room lockout: a booked whole villa takes its member rooms off
	# sale and any booked member room takes the villa off sale - the same
	# query validate_villa_lockout refuses a booking on
	from kamra.kamra.doctype.reservation.reservation import villa_lockout_conflict
	if villa_lockout_conflict(property, room_type, check_in_date, check_out_date):
		return []
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
		  AND NOT EXISTS (
			SELECT 1 FROM `tabRoom Block` k
			WHERE k.room = r.name
			  AND k.block_status = 'Active'
			  AND k.from_date < %(check_out)s
			  AND k.to_date > %(check_in)s
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


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
def room_blocks(property: str, active_only: int = 1):
	"""Rooms held out of sale (house use, VIP, maintenance)."""
	filters = {"property": property}
	if int(active_only or 0):
		filters["block_status"] = "Active"
	rows = frappe.get_all(
		"Room Block", filters=filters,
		fields=["name", "room", "reason", "from_date", "to_date",
		        "block_status", "note", "released_by", "released_on"],
		order_by="from_date asc",
	)
	nums = {r.name: r.room_number for r in frappe.get_all(
		"Room", filters={"property": property},
		fields=["name", "room_number"])}
	for r in rows:
		r["room_number"] = nums.get(r.room, r.room)
	return rows


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Kamra Agent")
def create_room_block(property: str, room: str, from_date: str,
                      to_date: str, reason: str = "House Use",
                      note: str | None = None):
	"""Hold a room out of sale for a date range. Refused if the room is
	already booked in that window (move the guest first)."""
	doc = frappe.get_doc({
		"doctype": "Room Block",
		"property": property,
		"room": room,
		"from_date": from_date,
		"to_date": to_date,
		"reason": reason,
		"note": note or None,
		"block_status": "Active",
	})
	doc.insert()
	from kamra.savings import log_action
	log_action("room_block", "Room Block", doc.name, property,
	           rationale=f"{reason}: {room} {from_date}→{to_date}")
	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Kamra Agent", scope={"name": "Room Block"})
def release_room_block(name: str):
	"""Free a held room before its end date (the room returns to sale)."""
	doc = frappe.get_doc("Room Block", name)
	doc.block_status = "Released"
	doc.released_by = frappe.session.user
	doc.released_on = frappe.utils.now_datetime()
	doc.save()
	from kamra.savings import log_action
	log_action("room_unblock", "Room Block", doc.name, doc.property,
	           rationale=f"released {doc.room}")
	return {"name": doc.name, "block_status": "Released"}


@frappe.whitelist()
@require_roles("Finance", "Front Desk", "Revenue Manager", "Housekeeping")
def cashier_pin_status(property: str):
	"""Does this property demand a PIN on money actions, and does the
	signed-in user have one set yet? Includes unlock / lockout state."""
	from kamra.authz import cashier_unlock_status
	return cashier_unlock_status(property)


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Front Desk", "Revenue Manager", "Housekeeping")
def set_cashier_pin(pin: str, current_pin: str | None = None):
	"""Set or change your own cashier PIN (4-8 digits). Changing an existing
	PIN needs the current one — unless must_reset was set by an admin."""
	pin = str(pin or "").strip()
	if not pin.isdigit() or not (4 <= len(pin) <= 8):
		frappe.throw("The PIN must be 4 to 8 digits.")
	user = frappe.session.user
	if frappe.db.exists("Cashier PIN", user):
		doc = frappe.get_doc("Cashier PIN", user)
		if not doc.get("must_reset"):
			from frappe.utils.password import get_decrypted_password
			stored = get_decrypted_password("Cashier PIN", user, "pin",
			                                raise_exception=False)
			if not current_pin or str(current_pin).strip() != str(stored):
				frappe.throw("Your current PIN is needed to change it.")
		doc.pin = pin
		doc.must_reset = 0
		doc.pin_attempts = 0
		doc.locked_until = None
		doc.save(ignore_permissions=True)
	else:
		frappe.get_doc({"doctype": "Cashier PIN", "user": user,
		                "pin": pin, "must_reset": 0}).insert(
			ignore_permissions=True)
	frappe.cache.delete_value(f"kamra_cashier_unlock:{user}")
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin")
def reset_cashier_pin(user: str):
	"""Admin reset: wipe the user's PIN and force re-enrollment."""
	if not user:
		frappe.throw("user is required.")
	if frappe.db.exists("Cashier PIN", user):
		frappe.delete_doc("Cashier PIN", user, ignore_permissions=True,
		                  force=True)
	# Leave a must_reset stub so status can surface the flag, OR just
	# rely on PIN_NOT_SET. Create a stub with must_reset for clarity.
	frappe.get_doc({
		"doctype": "Cashier PIN",
		"user": user,
		"pin": "0000",  # replaced on enroll; blocked by must_reset
		"must_reset": 1,
		"pin_attempts": 0,
	}).insert(ignore_permissions=True)
	frappe.cache.delete_value(f"kamra_cashier_unlock:{user}")
	try:
		from kamra.savings import log_action
		log_action("reset_cashier_pin", "Cashier PIN", user, None,
		           rationale=f"PIN reset for {user} by {frappe.session.user}")
	except Exception:
		# the reset itself succeeded; losing its audit line must be visible
		frappe.log_error(title="Cashier PIN reset: action log write failed")
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional
	return {"ok": True, "user": user, "must_reset": True}


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Front Desk", "Revenue Manager", "Housekeeping")
def verify_cashier_pin(property: str, pin: str):
	"""PinPad unlock: validate PIN and open a 15-minute sliding window."""
	from kamra.authz import unlock_cashier_session
	return unlock_cashier_session(property, pin)


# ---------------------------------------------------------------------------
# MICE: group room blocks + pickup (Group Rooms Control)
# ---------------------------------------------------------------------------

@frappe.whitelist()
@require_roles("Front Desk", "Revenue Manager", "Kamra Agent")
def group_detail(group_booking: str):
	"""Everything Group Rooms Control needs: the block, per-type pickup,
	the rooming list, the tied event and the master folio."""
	from kamra.group_blocks import effective_cutoff
	gb = frappe.get_doc("Group Booking", group_booking)
	released_on = frappe.db.get_value("Group Booking", gb.name, "released_on") \
		if frappe.db.has_column("Group Booking", "released_on") else None
	pickup = []
	for b in gb.blocks:
		picked = frappe.db.count("Reservation", {
			"group_booking": gb.name, "room_type": b.room_type,
			"status": ("in", ["Confirmed", "Checked In"])})
		pickup.append({
			"room_type": b.room_type,
			"rooms_blocked": b.rooms_blocked,
			"block_rate": b.block_rate,
			"picked_up": picked,
			"remaining": max(0, int(b.rooms_blocked) - picked),
			"rooms_released": int(frappe.db.get_value(
				"Group Room Block", b.name, "rooms_released") or 0)
			if released_on else 0,
		})
	rooming = frappe.get_all(
		"Reservation",
		filters={"group_booking": gb.name},
		fields=["name", "guest_name", "room_type", "room", "status",
		        "check_in_date", "check_out_date"],
		order_by="creation asc")
	event = None
	if gb.get("event"):
		event = frappe.db.get_value(
			"Venue Booking", gb.event,
			["name", "venue", "event_type", "event_date", "status",
			 "attendees", "quoted_amount"], as_dict=True)
	master = frappe.db.get_value(
		"Folio", {"group_booking": gb.name, "folio_type": "Group"}, "name")
	return {
		"group": {
			"name": gb.name, "group_name": gb.group_name,
			"company": gb.company, "status": gb.status,
			"check_in_date": str(gb.check_in_date),
			"check_out_date": str(gb.check_out_date),
			"cutoff_date": str(gb.cutoff_date) if gb.cutoff_date else None,
			"released_on": str(released_on) if released_on else None,
			"holds_inventory": gb.status == "Confirmed" and not released_on
			and effective_cutoff(gb.cutoff_date, gb.check_in_date)
			>= getdate(nowdate()),
			"notes": gb.notes,
		},
		"pickup": pickup,
		"rooming_list": rooming,
		"event": event,
		"master_folio": master,
	}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Revenue Manager", "Kamra Agent")
def save_group_blocks(group_booking: str, blocks, cutoff_date: str | None = None,
                      status: str | None = None):
	"""Set the room block (list of {room_type, rooms_blocked, block_rate})
	and optionally the cutoff/status. Confirmed blocks hold inventory."""
	if isinstance(blocks, str):
		blocks = frappe.parse_json(blocks)
	gb = frappe.get_doc("Group Booking", group_booking)
	gb.blocks = []
	for b in blocks or []:
		if not b.get("room_type") or not int(b.get("rooms_blocked") or 0):
			continue
		gb.append("blocks", {
			"room_type": b["room_type"],
			"rooms_blocked": int(b["rooms_blocked"]),
			"block_rate": float(b.get("block_rate") or 0),
		})
	if cutoff_date is not None:
		gb.cutoff_date = cutoff_date or None
		# a cutoff pushed back into the future re-opens a released block:
		# its unpicked rooms are held again until the new date
		from kamra.group_blocks import effective_cutoff
		if gb.get("released_on") and effective_cutoff(
				gb.cutoff_date, gb.check_in_date) >= getdate(nowdate()):
			gb.released_on = None
			frappe.db.set_value("Group Booking", gb.name, "released_on", None,
			                    update_modified=False)
	if status:
		gb.status = status
	gb.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional
	return {"ok": True, "blocks": len(gb.blocks)}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Kamra Agent")
def pickup_group_room(group_booking: str, room_type: str, guest_name: str,
                      phone: str | None = None, adults: int = 2,
                      children: int = 0, idempotency_key: str | None = None):
	"""Name a guest into the block: creates a reservation on the group's
	dates against its held inventory. Every call books a room (a block is
	several identical rooms for one party); pass idempotency_key to make a
	retry safe."""
	gb = frappe.get_doc("Group Booking", group_booking)
	out = create_booking(
		property=gb.property, room_type=room_type,
		check_in_date=str(gb.check_in_date),
		check_out_date=str(gb.check_out_date),
		guest_name=guest_name, phone=phone,
		adults=int(adults), children=int(children),
		booking_type="Group", company=gb.company,
		group_booking=gb.name, source="Manual",
		idempotency_key=idempotency_key)
	if not out.get("idempotent_replay"):
		from kamra.savings import log_action
		log_action("group_pickup", "Group Booking", gb.name, gb.property,
		           rationale=f"{guest_name} picked up a {room_type.split('-')[-1]}"
		                     f" from block {gb.group_name}",
		           channel=agent_channel() or "Desk")
	return out


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Revenue Manager", "Kamra Agent")
def create_group_block(property: str, group_name: str, check_in_date: str,
                       check_out_date: str, blocks,
                       company: str | None = None,
                       cutoff_date: str | None = None,
                       venue: str | None = None,
                       event_type: str | None = None,
                       event_date: str | None = None,
                       attendees: int = 0,
                       customer_phone: str | None = None,
                       notes: str | None = None):
	"""One call drafts the whole piece of MICE business: the group, its room
	block, and (optionally) the banquet event - the agent wedge: an inquiry
	agent turns "30 rooms + a 200-pax wedding on Dec 12" into a proposal."""
	if isinstance(blocks, str):
		blocks = frappe.parse_json(blocks)
	gb = frappe.get_doc({
		"doctype": "Group Booking",
		"property": property,
		"group_name": group_name,
		"company": company,
		"check_in_date": check_in_date,
		"check_out_date": check_out_date,
		"cutoff_date": cutoff_date,
		"status": "Open",
		"notes": notes,
	})
	from kamra.booking_refs import resolve_room_type
	for b in blocks or []:
		gb.append("blocks", {
			# agents name room types the way staff do ("Deluxe", "DLX")
			"room_type": resolve_room_type(property, b.get("room_type")),
			"rooms_blocked": int(b.get("rooms_blocked") or 0),
			"block_rate": float(b.get("block_rate") or 0),
		})
	gb.insert(ignore_permissions=True)
	event = None
	if venue:
		ev = frappe.get_doc({
			"doctype": "Venue Booking",
			"property": property,
			"venue": venue,
			"event_type": event_type or "Other",
			"status": "Enquiry",
			"event_date": event_date or check_in_date,
			"customer_name": group_name,
			"customer_phone": customer_phone,
			"company": company,
			"attendees": int(attendees or 0),
			"group_booking": gb.name,
		})
		ev.insert(ignore_permissions=True)
		gb.event = ev.name
		gb.save(ignore_permissions=True)
		event = ev.name
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional
	from kamra.savings import log_action
	log_action("group_block_drafted", "Group Booking", gb.name, property,
	           minutes_saved=15,
	           rationale=f"Drafted block '{group_name}' "
	                     f"({sum(int(b.get('rooms_blocked') or 0) for b in blocks or [])} rooms"
	                     f"{' + event' if event else ''})")
	return {"group_booking": gb.name, "event": event, "status": gb.status}



@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance", "Revenue Manager", "Housekeeping")
def my_connector_credentials(property: str):
	"""Personal MCP credentials for connecting Claude (or any MCP client)
	AS YOURSELF. The key acts with exactly your roles - Frappe enforces the
	same gates as the UI, so a front-desk connection can do front-desk
	things and nothing more. Regenerating invalidates the old secret.

	Platform-wide / service keys stay on the Developers page (IT admin)."""
	user = frappe.session.user
	api_key = frappe.db.get_value("User", user, "api_key")
	if not api_key:
		api_key = frappe.generate_hash(length=15)
	api_secret = frappe.generate_hash(length=15)
	u = frappe.get_doc("User", user)
	u.api_key = api_key
	u.api_secret = api_secret
	u.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional
	from kamra.savings import log_action
	log_action("connector_key_issued", "User", user,
	           rationale="Personal MCP connector credentials (re)generated")
	return {"api_key": api_key, "api_secret": api_secret,
	        "base_url": frappe.utils.get_url(), "property": property,
	        "user": user}


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Revenue Manager", "Housekeeping")
def linked_records(doctype: str, name: str):
	"""The connective tissue: for any record, everything it's attached to -
	guest, reservation(s), folio(s), company, group, event - so every screen
	can offer one-tap paths to billing and editing. One endpoint, all types."""
	from kamra.authz import assert_record_access
	if frappe.db.exists("DocType", doctype):
		assert_record_access(doctype, name)
	out = {"guest": None, "guest_name": None, "reservations": [],
	       "folios": [], "company": None, "group_booking": None,
	       "group_name": None, "event": None, "event_type": None}

	def folios_for(filters):
		return frappe.get_all("Folio", filters=filters,
			fields=["name", "folio_type", "status", "balance",
			        "invoice_number"], order_by="creation asc")

	if doctype == "Reservation":
		r = frappe.db.get_value("Reservation", name,
			["guest", "guest_name", "company", "group_booking"], as_dict=True)
		if not r:
			frappe.throw("Reservation not found.")
		out.update(guest=r.guest, guest_name=r.guest_name, company=r.company,
		           group_booking=r.group_booking)
		out["folios"] = folios_for({"reservation": name})
	elif doctype == "Venue Booking":
		v = frappe.db.get_value("Venue Booking", name,
			["company", "group_booking", "customer_name", "event_type"],
			as_dict=True)
		if not v:
			frappe.throw("Event not found.")
		out.update(company=v.company, group_booking=v.group_booking,
		           guest_name=v.customer_name, event=name,
		           event_type=v.event_type)
		if v.group_booking:
			out["folios"] = folios_for(
				{"group_booking": v.group_booking, "folio_type": "Group"})
	elif doctype == "Group Booking":
		g = frappe.db.get_value("Group Booking", name,
			["company", "event", "group_name"], as_dict=True)
		if not g:
			frappe.throw("Group not found.")
		out.update(company=g.company, event=g.event, group_booking=name,
		           group_name=g.group_name)
		if g.event:
			out["event_type"] = frappe.db.get_value(
				"Venue Booking", g.event, "event_type")
		out["folios"] = folios_for(
			{"group_booking": name, "folio_type": "Group"})
	elif doctype == "Guest":
		out["guest"] = name
		out["guest_name"] = frappe.db.get_value("Guest", name, "full_name")
		out["reservations"] = frappe.get_all("Reservation",
			filters={"guest": name},
			fields=["name", "status", "check_in_date"],
			order_by="check_in_date desc", limit=5)
		out["folios"] = folios_for({"guest": name})[-5:]
	if out["group_booking"] and not out.get("group_name"):
		out["group_name"] = frappe.db.get_value(
			"Group Booking", out["group_booking"], "group_name")
	return out


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Revenue Manager", "Housekeeping", "Kamra Agent")
def property_locale(property: str):
	"""Currency, number locale and tax vocabulary for this property, from its
	localization pack. Drives the frontend's money formatting and tax dropdowns
	so no screen hardcodes ₹ or GST %. `integrations` says which country
	integrations (gateways, tax return, ID checks) this property has."""
	from kamra.localization import front_desk_vocabulary, integrations, pack_for
	prop = frappe.get_cached_doc("Property", property)
	pack = pack_for(property)
	return {**pack.locale(prop), **front_desk_vocabulary(pack),
	        "integrations": integrations(pack),
	        # the rate the server puts on any food & beverage charge, whatever
	        # rate the caller picked (_resolve_charge_gst) - so the folio's
	        # charge form shows the rate that will apply instead of a choice
	        # that is ignored
	        "fnb_tax_rate": float(pack.fnb_tax_rate(property)),
	        "fnb_charge_words": list(_FNB_WORDS)}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance")
def verify_tax_id(property: str, tax_id: str, business_name: str = ""):
	"""Check a buyer's tax ID before the invoice goes out, where the
	property's country pack offers it."""
	from kamra import localization as loc
	return loc.verify_tax_id(loc.pack_for(property), property, tax_id,
	                         business_name)


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", scope={"guest": "Guest"})
def verify_guest_id(property: str, guest: str, id_type: str, consent: int = 0):
	"""Read the guest's ID document on file into the profile, where the
	property's country pack offers it. consent: the desk confirms the guest
	was told."""
	from kamra import localization as loc
	return loc.verify_guest_id(loc.pack_for(property), property, guest,
	                           id_type, consent)


@frappe.whitelist()
@require_roles("Finance")
def zatca_settings(property: str):
	"""The property's ZATCA (Saudi e-invoicing) settings, created from the
	property on first use, plus what is still missing for a valid invoice
	and where the invoice chain stands."""
	from kamra import zatca
	from kamra.crs import assert_property_access
	assert_property_access(property)
	s = zatca.settings_for(property)
	return {
		"name": s.name,
		"missing": zatca.readiness(s),
		"issued": frappe.db.count(zatca.RECORD, {"property": property}),
		"last_icv": s.last_icv,
		"onboarding_status": s.onboarding_status,
		"environment": s.environment,
	}


@frappe.whitelist()
@require_roles("Finance")
def zatca_invoice_xml(invoice_number: str, property: str,
                      document_type: str = "Invoice"):
	"""The UBL XML behind an issued invoice or credit note - for the
	accountant, an auditor or a ZATCA query."""
	from kamra.crs import assert_property_access
	assert_property_access(property)
	rec = frappe.db.get_value(
		"ZATCA Invoice", {"property": property, "invoice_number": invoice_number,
		                  "document_type": document_type},
		["xml", "uuid", "icv", "invoice_hash", "status"], as_dict=True)
	if not rec:
		frappe.throw(_("No ZATCA record for {0}.").format(invoice_number))
	return rec


@frappe.whitelist()
def localization_countries():
	"""Countries with a dedicated tax & invoicing pack, with the currency,
	time zone and tax vocabulary picking one sets up. Read-only reference
	data for the setup wizard and Settings."""
	from kamra.localization import supported_countries
	return supported_countries()


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent")
def pending_deposit_refunds(property: str):
	"""Returns a list of checked-out reservations with pending security deposit refunds
	for NEFT processing (e.g. Tuesday/Saturday payout batches).
	"""
	reservations = frappe.get_all(
		"Reservation",
		filters={"property": property, "status": "Checked Out"},
		fields=["name", "guest_name", "check_in_date", "check_out_date"]
	)

	pending = []
	for res in reservations:
		folio_name = frappe.db.get_value("Folio", {"reservation": res.name}, "name")
		if not folio_name:
			continue

		payments = frappe.get_all(
			"Folio Payment",
			filters={"parent": folio_name, "parenttype": "Folio"},
			fields=["payment_kind", "amount"]
		)

		deposits_sum = sum(p.amount for p in payments if p.payment_kind == "Security Deposit")
		refunds_sum = sum(p.amount for p in payments if p.payment_kind == "Refund")

		if deposits_sum > refunds_sum:
			pending.append({
				"reservation": res.name,
				"guest_name": res.guest_name,
				"check_out_date": res.check_out_date,
				"deposit_amount": float(deposits_sum),
				"refunded_amount": float(refunds_sum),
				"pending_refund": float(deposits_sum - refunds_sum)
			})

	return pending
