# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Kamra Enterprise desk API.

Community stays the default. These calls refuse until Settings -> Enterprise
is turned on for the property (or the site config kamra_edition is Enterprise).
Prices still come from kamra.pricing. Messages that need a vendor go through
the SMS and door-lock adapters; nothing here pretends a message was sent
when it was only logged.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import add_days, cint, date_diff, getdate, now_datetime, nowdate

from kamra.authz import require_roles
from kamra.edition import feature_on, is_enterprise, require_enterprise
from kamra.enterprise_logic import (
	arrival_sort_key,
	facilities_from_amenities,
	minutes_from_eta,
	peak_and_low,
	premium_for_occupancy,
	priority_for_arrival,
	recommend_for_guest,
	staffing_hint,
	valid_score,
	weekday_samples,
	deviation,
)


def _clear_pricing_cache() -> None:
	frappe.flags.enterprise_mode = None
	frappe.flags.enterprise_predict = None


# ── status ────────────────────────────────────────────────────────────────


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Revenue Manager", "Housekeeping", "Kamra Agent")
def enterprise_status(property: str) -> dict:
	"""Whether this property is on Enterprise, and which switches are on.

	Does not refuse Community: the desk uses it to explain how to turn the
	edition on.
	"""
	from kamra.settings import get_setting
	return {
		"enterprise": is_enterprise(property),
		"edition": "Enterprise" if is_enterprise(property) else "Community",
		"pricing_mode": get_setting(property, "ent_pricing_mode", "off"),
		"sms_provider": get_setting(property, "ent_sms_provider", "none"),
		"erp_mode": get_setting(property, "ent_erp_mode", "off"),
		"website": bool(get_setting(property, "ent_website")),
		"hk_priority": bool(get_setting(property, "ent_hk_priority")),
		"maintenance": bool(get_setting(property, "ent_maintenance")),
		"vip_welcome": bool(get_setting(property, "ent_vip_welcome")),
		"surveys": bool(get_setting(property, "ent_surveys")),
		"secrets": _secret_flags(property),
		"hotel_path": _hotel_path(property),
	}


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Revenue Manager", "Housekeeping", "Kamra Agent")
def enterprise_desk(property: str, days: int = 14) -> dict:
	"""Forecast, open alerts, maintenance plans and recent surveys."""
	require_enterprise(property)
	return {
		"status": enterprise_status(property),
		"forecast": _forecast(property, cint(days) or 14),
		"alerts": _alerts(property),
		"plans": _plans(property),
		"surveys": _surveys(property),
	}


def _secret_flags(property: str) -> dict:
	blank = {"sms": False, "erpnext": False, "door": False}
	if not frappe.db.exists("DocType", "Enterprise Secret"):
		return blank
	if not frappe.db.exists("Enterprise Secret", property):
		return blank
	doc = frappe.get_doc("Enterprise Secret", property)
	return {
		"sms": bool(doc.get_password("sms_auth", raise_exception=False)),
		"erpnext": bool(doc.get_password("erpnext_api_secret", raise_exception=False)),
		"door": bool(doc.get_password("door_http_secret", raise_exception=False)),
	}


def _hotel_path(property: str) -> str:
	from kamra.booking_slugs import slugify
	slug = frappe.db.get_value("Property", property, "page_slug") or slugify(
		frappe.db.get_value("Property", property, "property_name") or property)
	return f"/hotel/{slug}"


# ── forecast and pricing ──────────────────────────────────────────────────


@frappe.whitelist()
@require_roles("Front Desk", "Revenue Manager", "Hotel Admin", "Kamra Agent")
def occupancy_forecast(property: str, days: int = 0) -> dict:
	"""Predicted occupancy, peak and low days, and a housekeeping hint."""
	require_enterprise(property)
	from kamra.settings import get_setting
	horizon = cint(days) or cint(get_setting(property, "ent_forecast_days", 30)) or 30
	return _forecast(property, min(horizon, 90))


def _forecast(property: str, days: int) -> dict:
	from kamra.enterprise_pricing import preview_dates
	from kamra.pricing import forecast_occupancy
	_clear_pricing_cache()
	rows = preview_dates(property, days, lambda day: forecast_occupancy(property, day))
	for row in rows:
		row["premium_pct"] = premium_for_occupancy(row["predicted"])
	arrivals, departures, stayovers = _movement(property, nowdate())
	return {
		"days": rows,
		"extremes": peak_and_low(rows),
		"staffing": staffing_hint(arrivals, departures, stayovers),
		"note": "Predicted occupancy adds pace and the weekday history on top "
		        "of rooms already sold. Auto pricing uses it. Suggest mode "
		        "only shows it.",
	}


def _movement(property: str, day: str) -> tuple[int, int, int]:
	arrivals = frappe.db.count("Reservation", {
		"property": property, "status": "Confirmed", "check_in_date": day})
	departures = frappe.db.count("Reservation", {
		"property": property, "status": "Checked In", "check_out_date": day})
	# stayovers: in house, not leaving today
	in_house = frappe.db.count("Reservation", {
		"property": property, "status": "Checked In",
		"check_in_date": ("<=", day), "check_out_date": (">", day)})
	return int(arrivals or 0), int(departures or 0), int(in_house or 0)


@frappe.whitelist()
@require_roles("Revenue Manager", "Hotel Admin", "Kamra Agent")
def dynamic_pricing_preview(property: str, days: int = 14) -> dict:
	"""What auto mode would do. Does not change a rate."""
	require_enterprise(property)
	from kamra.settings import get_setting
	_clear_pricing_cache()
	forecast = _forecast(property, min(cint(days) or 14, 90))
	hurdles = frappe.db.count("Hurdle Rate", {"property": property, "disabled": 0})
	return {
		"mode": get_setting(property, "ent_pricing_mode", "off"),
		"hurdle_tiers": int(hurdles or 0),
		"days": forecast["days"],
		"how": "Auto mode passes predicted occupancy into hurdle tiers. "
		       "With no tier for that occupancy, the open band applies and "
		       "the rate guardrail still holds. Suggest mode does not change quotes.",
	}


# ── guest offers ──────────────────────────────────────────────────────────


@frappe.whitelist()
@require_roles("Front Desk", "Hotel Admin", "Kamra Agent")
def guest_recommendations(property: str, guest: str) -> dict:
	"""Offers from the guest profile and earlier stays. Nothing is posted."""
	require_enterprise(property)
	if not frappe.db.exists("Guest", guest):
		frappe.throw(_("Guest {0} was not found.").format(guest))
	doc = frappe.get_doc("Guest", guest)
	stays = frappe.get_all(
		"Reservation",
		filters={"guest": guest, "property": property,
		         "status": ("in", ["Confirmed", "Checked In", "Checked Out"])},
		fields=["room_type", "check_in_date", "check_out_date", "status"],
		order_by="check_in_date desc", limit=30,
	)
	for stay in stays:
		stay["nights"] = max(1, date_diff(stay.check_out_date, stay.check_in_date))
	folios = frappe.get_all("Folio", filters={"guest": guest, "property": property}, pluck="name")
	charges = []
	if folios:
		charges = frappe.get_all(
			"Folio Charge", filters={"parent": ("in", folios)},
			fields=["charge_type"], limit=200,
		)
	types = frappe.get_all(
		"Room Type", filters={"property": property, "disabled": 0},
		fields=["name", "room_type_name", "base_price"],
	)
	current = next((s.room_type for s in stays if s.status in ("Confirmed", "Checked In")), None)
	profile = {
		"vip": cint(doc.vip),
		"dietary_notes": doc.get("dietary_notes") or "",
		"special_occasions": doc.get("special_occasions") or "",
		"preferred_view": doc.get("preferred_view") or "",
		"preferred_room_type": doc.get("preferred_room_type") or "",
		"notes": doc.get("guest_notes") or "",
		"current_room_type": current,
		"room_types": types,
		"stays": stays,
		"charges": charges,
	}
	return {"guest": guest, "guest_name": doc.full_name, "offers": recommend_for_guest(profile)}


# ── anomalies ─────────────────────────────────────────────────────────────


@frappe.whitelist()
@require_roles("Finance", "Revenue Manager", "Hotel Admin", "Kamra Agent")
def list_anomaly_alerts(property: str, open_only: int = 1) -> dict:
	require_enterprise(property)
	return {"alerts": _alerts(property, open_only=cint(open_only))}


def _alerts(property: str, open_only: int = 1) -> list:
	filters = {"property": property}
	if open_only:
		filters["status"] = "Open"
	return frappe.get_all(
		"Enterprise Alert", filters=filters,
		fields=["name", "alert_date", "metric", "actual", "expected", "zscore",
		        "message", "status"],
		order_by="alert_date desc, creation desc", limit=50,
	)


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Revenue Manager", "Hotel Admin")
def acknowledge_alert(name: str) -> dict:
	doc = frappe.get_doc("Enterprise Alert", name)
	require_enterprise(doc.property)
	doc.status = "Acknowledged"
	doc.save(ignore_permissions=True)
	return {"ok": True, "name": doc.name}


def scan_anomalies(property: str, day: str | None = None) -> dict:
	"""Compare one day with earlier same-weekdays. Used by the scheduler."""
	if not is_enterprise(property):
		return {"created": 0}
	from kamra.settings import get_setting
	day = str(day or add_days(nowdate(), -1))[:10]
	z_threshold = float(get_setting(property, "ent_anomaly_z", 2) or 2)
	min_pct = float(get_setting(property, "ent_anomaly_min_pct", 20) or 20)
	start = str(add_days(day, -70))
	series = _metric_series(property, start, day)
	created = []
	labels = {
		"room_revenue": "Room revenue",
		"other_revenue": "Other revenue",
		"payments": "Payments",
		"expenses": "Expenses",
		"occupancy": "Occupancy",
	}
	for metric, points in series.items():
		actual = dict(points).get(day)
		if actual is None:
			continue
		history = weekday_samples(points, day)
		found = deviation(actual, history, z_threshold, min_pct)
		if not found:
			continue
		if frappe.db.exists("Enterprise Alert", {
			"property": property, "alert_date": day, "metric": metric}):
			continue
		message = (
			f"{labels.get(metric, metric)} {found['actual']} is {found['pct']}% "
			f"{found['direction']} the weekday average {found['mean']}."
		)
		doc = frappe.get_doc({
			"doctype": "Enterprise Alert",
			"property": property,
			"alert_date": day,
			"metric": metric,
			"actual": found["actual"],
			"expected": found["mean"],
			"zscore": found["z"],
			"message": message,
			"status": "Open",
		})
		doc.insert(ignore_permissions=True)
		created.append(doc.name)
	if created:
		_notify_anomaly(property, day, len(created))
	return {"created": len(created), "names": created}


def _metric_series(property: str, start: str, end: str) -> dict[str, list[tuple[str, float]]]:
	room_rows = frappe.db.sql(
		"""SELECT fc.posting_date,
		          SUM(CASE WHEN fc.charge_type IN
		              ('Room','Meal Plan','Extra Guests','Room Levy')
		              THEN fc.amount ELSE 0 END) AS room_revenue,
		          SUM(CASE WHEN fc.charge_type NOT IN
		              ('Room','Meal Plan','Extra Guests','Room Levy','Discount','Allowance')
		              THEN fc.amount ELSE 0 END) AS other_revenue
		   FROM `tabFolio Charge` fc
		   INNER JOIN `tabFolio` f ON f.name = fc.parent
		   WHERE f.property = %s AND fc.posting_date BETWEEN %s AND %s
		   GROUP BY fc.posting_date""",
		(property, start, end), as_dict=True,
	)
	pay_rows = frappe.db.sql(
		"""SELECT fp.posting_date, SUM(fp.amount) AS payments
		   FROM `tabFolio Payment` fp
		   INNER JOIN `tabFolio` f ON f.name = fp.parent
		   WHERE f.property = %s AND fp.posting_date BETWEEN %s AND %s
		   GROUP BY fp.posting_date""",
		(property, start, end), as_dict=True,
	)
	expense_rows = frappe.db.sql(
		"""SELECT bill_date, SUM(total) AS expenses
		   FROM `tabVendor Bill`
		   WHERE property = %s AND status != 'Cancelled'
		     AND bill_date BETWEEN %s AND %s
		   GROUP BY bill_date""",
		(property, start, end), as_dict=True,
	)
	out = {
		"room_revenue": [(str(r.posting_date), float(r.room_revenue or 0)) for r in room_rows],
		"other_revenue": [(str(r.posting_date), float(r.other_revenue or 0)) for r in room_rows],
		"payments": [(str(r.posting_date), float(r.payments or 0)) for r in pay_rows],
		"expenses": [(str(r.bill_date), float(r.expenses or 0)) for r in expense_rows],
		"occupancy": _occupancy_series(property, start, end),
	}
	return out


def _occupancy_series(property: str, start: str, end: str) -> list[tuple[str, float]]:
	sellable = frappe.db.count("Room", {"property": property}) or 0
	if not sellable:
		return []
	rows = frappe.get_all(
		"Reservation",
		filters={
			"property": property,
			"status": ("in", ["Confirmed", "Checked In", "Checked Out"]),
			"check_out_date": (">", start),
			"check_in_date": ("<=", end),
		},
		fields=["check_in_date", "check_out_date"],
		limit=5000,
	)
	counts: dict[str, int] = {}
	day = getdate(start)
	last = getdate(end)
	while day <= last:
		counts[str(day)] = 0
		day = getdate(add_days(day, 1))
	for row in rows:
		cursor = getdate(row.check_in_date)
		depart = getdate(row.check_out_date)
		while cursor < depart:
			stamp = str(cursor)
			if stamp in counts:
				counts[stamp] += 1
			cursor = getdate(add_days(cursor, 1))
	return [(stamp, round(sold / sellable * 100, 1)) for stamp, sold in sorted(counts.items())]


def _notify_anomaly(property: str, day: str, count: int) -> None:
	email = frappe.db.get_value("Property", property, "email")
	if not email:
		return
	try:
		frappe.sendmail(
			recipients=[email],
			subject=f"Kamra: {count} figure(s) to look at for {day}",
			message=f"{count} revenue or expense figure(s) for {property} on {day} "
			        f"sit outside the usual weekday range. Open Enterprise on the desk.",
			now=False,
		)
	except Exception:
		pass


# ── messaging: SMS, VIP welcome, surveys ──────────────────────────────────


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Hotel Admin", "Kamra Agent")
def send_guest_sms(property: str, guest: str, body: str, reservation: str | None = None) -> dict:
	"""Send one SMS through the configured provider. A log provider does not send."""
	require_enterprise(property)
	if not (body or "").strip():
		frappe.throw(_("Write the message first."))
	phone = frappe.db.get_value("Guest", guest, "phone")
	if not phone:
		frappe.throw(_("This guest has no phone number."))
	from kamra.enterprise_sms import send_sms
	return send_sms(property, phone, body.strip(), purpose="manual",
	                guest=guest, reservation=reservation)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=30, seconds=3600)
def submit_survey(token: str, score: int, comment: str = "") -> dict:
	"""A guest scores the stay from 1 to 5. The token is the only credential."""
	number = valid_score(score)
	if number is None:
		frappe.throw(_("Choose a score from 1 to 5."))
	name = frappe.db.get_value("Guest Survey", {"token": token}, "name")
	if not name:
		frappe.throw(_("This survey link is not valid."))
	doc = frappe.get_doc("Guest Survey", name)
	if doc.status == "Submitted":
		return {"ok": True, "already": True}
	doc.score = number
	doc.comment = (comment or "")[:2000]
	doc.status = "Submitted"
	doc.submitted_on = now_datetime()
	doc.save(ignore_permissions=True)
	return {"ok": True, "score": number}


@frappe.whitelist(allow_guest=True)
def survey_prompt(token: str) -> dict:
	"""The property name for the public survey page. No guest details."""
	name = frappe.db.get_value("Guest Survey", {"token": token}, "name")
	if not name:
		frappe.throw(_("This survey link is not valid."))
	doc = frappe.get_doc("Guest Survey", name)
	prop = frappe.db.get_value("Property", doc.property, "property_name")
	return {"property_name": prop or doc.property, "submitted": doc.status == "Submitted"}


def send_vip_welcomes(property: str) -> dict:
	if not feature_on(property, "ent_vip_welcome"):
		return {"sent": 0}
	today = getdate(nowdate())
	horizon = getdate(add_days(today, 2))
	rows = frappe.get_all(
		"Reservation",
		filters={
			"property": property, "status": "Confirmed",
			"check_in_date": ("between", [str(today), str(horizon)]),
		},
		fields=["name", "guest", "guest_name", "check_in_date"],
		limit=200,
	)
	sent = 0
	prop_name = frappe.db.get_value("Property", property, "property_name") or property
	for row in rows:
		if not row.guest or not cint(frappe.db.get_value("Guest", row.guest, "vip")):
			continue
		if frappe.db.exists("SMS Message", {
			"reservation": row.name, "purpose": "vip_welcome"}):
			continue
		# Also skip when a welcome email was already logged on the survey-less path
		# by a previous SMS log. The exists check above is the idempotency key
		# even when the provider is not SMS: we write a log row either way.
		body = (
			f"Welcome to {prop_name}, {row.guest_name or 'guest'}. "
			f"We are preparing your arrival on {row.check_in_date}.\n"
			f"أهلاً بك في {prop_name}. نجهّز وصولك في {row.check_in_date}."
		)
		_welcome_channels(property, row, body)
		sent += 1
	return {"sent": sent}


def _welcome_channels(property, row, body: str) -> None:
	guest = frappe.db.get_value("Guest", row.guest, ["phone", "email"], as_dict=True) or {}
	from kamra.enterprise_sms import send_sms
	logged = False
	if guest.get("phone"):
		result = send_sms(property, guest.phone, body, purpose="vip_welcome",
		                  guest=row.guest, reservation=row.name)
		logged = bool(result.get("name"))
	if not logged:
		# Mark the stay even when SMS is off, so the welcome email is not sent again tomorrow.
		frappe.get_doc({
			"doctype": "SMS Message", "property": property,
			"recipient": guest.get("phone") or "",
			"body": body[:1000], "purpose": "vip_welcome", "status": "Logged",
			"adapter": "none", "guest": row.guest, "reservation": row.name,
		}).insert(ignore_permissions=True)
	if guest.get("email"):
		try:
			frappe.sendmail(recipients=[guest.email],
			                subject=f"Welcome to {property}",
			                message=body.replace("\n", "<br>"), now=False)
		except Exception:
			pass
	try:
		from kamra.whatsapp import send_text
		if guest.get("phone"):
			send_text(property, guest.phone, body, guest=row.guest, reservation=row.name)
	except Exception:
		pass


def send_departure_surveys(property: str) -> dict:
	if not feature_on(property, "ent_surveys"):
		return {"sent": 0}
	day = str(add_days(nowdate(), -1))
	rows = frappe.get_all(
		"Reservation",
		filters={"property": property, "status": "Checked Out", "check_out_date": day},
		fields=["name", "guest", "guest_name"], limit=300,
	)
	sent = 0
	prop_name = frappe.db.get_value("Property", property, "property_name") or property
	for row in rows:
		if frappe.db.exists("Guest Survey", {"reservation": row.name}):
			continue
		token = frappe.generate_hash(length=24)
		doc = frappe.get_doc({
			"doctype": "Guest Survey",
			"property": property,
			"reservation": row.name,
			"guest": row.guest,
			"token": token,
			"status": "Sent",
			"sent_on": now_datetime(),
		})
		doc.insert(ignore_permissions=True)
		link = f"{frappe.utils.get_url()}/kamra/survey/{token}"
		body = (
			f"Thank you for staying at {prop_name}. "
			f"How was your stay? 1 to 5: {link}\n"
			f"شكراً لإقامتكم في {prop_name}. كيف كانت الإقامة؟ من 1 إلى 5: {link}"
		)
		guest = {}
		if row.guest:
			guest = frappe.db.get_value("Guest", row.guest, ["phone", "email"], as_dict=True) or {}
		from kamra.enterprise_sms import send_sms
		if guest.get("phone"):
			send_sms(property, guest.phone, body, purpose="survey",
			         guest=row.guest, reservation=row.name)
		if guest.get("email"):
			try:
				frappe.sendmail(recipients=[guest.email],
				                subject=f"How was your stay at {prop_name}?",
				                message=body.replace("\n", "<br>"), now=False)
			except Exception:
				pass
		try:
			from kamra.whatsapp import send_text
			if guest.get("phone"):
				send_text(property, guest.phone, body, guest=row.guest, reservation=row.name)
		except Exception:
			pass
		sent += 1
	return {"sent": sent}


def _surveys(property: str) -> list:
	return frappe.get_all(
		"Guest Survey", filters={"property": property},
		fields=["name", "reservation", "guest", "score", "status", "sent_on", "comment"],
		order_by="creation desc", limit=15,
	)


# ── housekeeping and maintenance ──────────────────────────────────────────


@frappe.whitelist(methods=["POST"])
@require_roles("Housekeeping", "Front Desk", "Hotel Admin")
def prioritize_arrival_cleans(property: str, day: str | None = None) -> dict:
	"""Set departure-clean priority from today's arrivals. VIP and early ETA first."""
	require_enterprise(property)
	if not feature_on(property, "ent_hk_priority"):
		frappe.throw(_("Turn on arrival-priority housekeeping under Settings, Enterprise."))
	return _prioritize(property, day or nowdate())


def _prioritize(property: str, day: str) -> dict:
	arrivals = frappe.get_all(
		"Reservation",
		filters={"property": property, "status": "Confirmed", "check_in_date": day,
		         "room": ("is", "set")},
		fields=["room", "guest", "eta", "guest_name"],
		limit=500,
	)
	by_room = {}
	for row in arrivals:
		vip = bool(row.guest and cint(frappe.db.get_value("Guest", row.guest, "vip")))
		minutes = minutes_from_eta(row.eta)
		current = by_room.get(row.room)
		candidate = {"room": row.room, "vip": vip, "minutes": minutes,
		             "guest_name": row.guest_name}
		if current is None or arrival_sort_key(True, vip, minutes, row.room) < arrival_sort_key(
			True, current["vip"], current["minutes"], row.room):
			by_room[row.room] = candidate
	tasks = frappe.get_all(
		"Housekeeping Task",
		filters={"property": property, "status": "Pending",
		         "task_type": ("in", ["Checkout Clean", "Stayover Clean"])},
		fields=["name", "room", "task_type", "priority"],
		limit=500,
	)
	updated = []
	for task in tasks:
		info = by_room.get(task.room)
		same_day = bool(info) and task.task_type == "Checkout Clean"
		priority = priority_for_arrival(
			same_day, bool(info and info["vip"]), info["minutes"] if info else None)
		if priority != task.priority:
			frappe.db.set_value("Housekeeping Task", task.name, "priority", priority,
			                    update_modified=False)
		updated.append({
			"task": task.name, "room": task.room, "priority": priority,
			"guest_name": info["guest_name"] if info else None,
			"vip": bool(info and info["vip"]),
		})
	updated.sort(key=lambda row: arrival_sort_key(
		row["priority"] != "Medium", row["vip"],
		by_room.get(row["room"], {}).get("minutes"), row["room"] or ""))
	return {"tasks": updated, "arrivals": len(by_room)}


@frappe.whitelist()
@require_roles("Housekeeping", "Hotel Admin")
def maintenance_plans(property: str) -> dict:
	require_enterprise(property)
	return {"plans": _plans(property)}


def _plans(property: str) -> list:
	return frappe.get_all(
		"Maintenance Plan", filters={"property": property},
		fields=["name", "title", "area", "room", "interval_days",
		        "last_completed", "next_due", "disabled"],
		order_by="next_due asc", limit=100,
	)


@frappe.whitelist(methods=["POST"])
@require_roles("Housekeeping", "Hotel Admin")
def save_maintenance_plan(property: str, title: str, interval_days: int = 30,
                          area: str = "", room: str | None = None,
                          next_due: str | None = None, name: str | None = None,
                          notes: str = "") -> dict:
	require_enterprise(property)
	if not (title or "").strip():
		frappe.throw(_("Give the plan a name."))
	interval = cint(interval_days)
	if interval < 1:
		frappe.throw(_("The interval has to be at least one day."))
	if name:
		doc = frappe.get_doc("Maintenance Plan", name)
		if doc.property != property:
			frappe.throw(_("That plan belongs to another property."))
	else:
		doc = frappe.new_doc("Maintenance Plan")
		doc.property = property
	doc.title = title.strip()[:140]
	doc.area = (area or "")[:140]
	doc.room = room or None
	doc.interval_days = interval
	doc.notes = notes or ""
	doc.next_due = next_due or nowdate()
	doc.disabled = 0
	doc.save(ignore_permissions=True)
	return {"ok": True, "name": doc.name, "next_due": str(doc.next_due)}


@frappe.whitelist(methods=["POST"])
@require_roles("Housekeeping", "Hotel Admin")
def disable_maintenance_plan(name: str) -> dict:
	doc = frappe.get_doc("Maintenance Plan", name)
	require_enterprise(doc.property)
	doc.disabled = 1
	doc.save(ignore_permissions=True)
	return {"ok": True}


def run_due_maintenance(property: str) -> dict:
	if not feature_on(property, "ent_maintenance"):
		return {"created": 0}
	today = nowdate()
	plans = frappe.get_all(
		"Maintenance Plan",
		filters={"property": property, "disabled": 0,
		         "next_due": ("<=", today)},
		fields=["name", "title", "area", "room", "interval_days", "notes"],
		limit=200,
	)
	created = []
	for plan in plans:
		subject = f"Preventive maintenance: {plan.title}"[:140]
		open_ticket = frappe.db.exists("Service Ticket", {
			"property": property, "subject": subject,
			"status": ("in", ["Open", "In Progress"]),
		})
		if open_ticket:
			continue
		ticket = frappe.get_doc({
			"doctype": "Service Ticket",
			"property": property,
			"subject": subject,
			"category": "Maintenance",
			"priority": "Medium",
			"room": plan.room,
			"description": plan.notes or plan.area or "Scheduled preventive maintenance.",
			"source": "Manual",
		})
		ticket.insert(ignore_permissions=True)
		frappe.db.set_value("Maintenance Plan", plan.name, {
			"last_completed": today,
			"next_due": add_days(today, cint(plan.interval_days) or 30),
		}, update_modified=False)
		created.append(ticket.name)
	return {"created": len(created), "tickets": created}


# ── accounting ────────────────────────────────────────────────────────────


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Hotel Admin")
def sync_erpnext(property: str, business_date: str | None = None) -> dict:
	"""Post one day's closed invoices to ERPNext. Refuses to invent a success."""
	require_enterprise(property)
	from kamra.enterprise_books import sync_day
	day = str(business_date or add_days(nowdate(), -1))[:10]
	return sync_day(property, day)


# ── secrets ───────────────────────────────────────────────────────────────


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin")
def save_enterprise_secrets(property: str, sms_auth: str | None = None,
                            erpnext_api_secret: str | None = None,
                            door_http_secret: str | None = None) -> dict:
	"""Store provider secrets. Omit a field to leave it. Pass an empty string to clear it.

	Values are not written to the activity log.
	"""
	require_enterprise(property)
	if frappe.db.exists("Enterprise Secret", property):
		doc = frappe.get_doc("Enterprise Secret", property)
	else:
		doc = frappe.new_doc("Enterprise Secret")
		doc.property = property
	for field, value in (
		("sms_auth", sms_auth),
		("erpnext_api_secret", erpnext_api_secret),
		("door_http_secret", door_http_secret),
	):
		if value is None:
			continue
		doc.set(field, value)
	doc.save(ignore_permissions=True)
	from kamra.savings import log_action
	log_action("enterprise_secrets", "Enterprise Secret", doc.name, property,
	           rationale="Enterprise provider secrets updated")
	return {"ok": True, "secrets": _secret_flags(property)}


# ── property website ──────────────────────────────────────────────────────


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=60, seconds=3600)
def property_site(slug: str) -> dict:
	"""The multi-section property website. Community properties keep /stay and /book."""
	from kamra.booking_slugs import resolve_public_slug
	from kamra.public_api import showcase
	from kamra.settings import get_setting
	resolved = resolve_public_slug(slug)
	property = resolved["property"]
	if not (is_enterprise(property) and get_setting(property, "ent_website")):
		return {
			"enabled": False,
			"property": property,
			"stay_path": f"/stay/{slug}",
		}
	data = showcase(
		property,
		listing_slug=resolved.get("listing_slug"),
		location_slug=resolved.get("location_slug"),
	)
	amenities = (data.get("property") or {}).get("amenities") or []
	data["enabled"] = True
	data["facilities"] = facilities_from_amenities(amenities)
	data["languages"] = ["en", "ar"]
	return data


def run_morning(property: str) -> None:
	"""VIP welcomes, departure surveys, housekeeping order, maintenance."""
	if not is_enterprise(property):
		return
	send_vip_welcomes(property)
	send_departure_surveys(property)
	if feature_on(property, "ent_hk_priority"):
		_prioritize(property, nowdate())
	run_due_maintenance(property)


def run_after_audit(property: str) -> None:
	if not is_enterprise(property):
		return
	day = str(add_days(nowdate(), -1))
	try:
		scan_anomalies(property, day)
	except Exception:
		frappe.log_error(title=f"Enterprise anomalies {property}")
	from kamra.settings import get_setting
	if (get_setting(property, "ent_erp_mode", "off") or "off") in ("same_site", "remote"):
		try:
			from kamra.enterprise_books import sync_day
			sync_day(property, day)
		except Exception:
			frappe.log_error(title=f"Enterprise ERPNext sync {property}")
