"""Banquet enterprise (issue #67): send quote (with its PDF), desk guest
confirm, department checklists on Confirm (Sales, Finance, Housekeeping,
F&B, Engineering, HR), quote no-response reminders, food tastings, a
payment link per milestone with guest balance reminders, deposit rules on
Confirm and the equipment calendar.

Guest portal is out of scope — sales records confirmation on the sheet.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, getdate, now_datetime, nowdate

from kamra.authz import require_roles

BANQUET_ROLES = ("Front Desk", "Revenue Manager", "Kamra Agent")
READ_ROLES = BANQUET_ROLES + ("Finance", "Housekeeping")

# Department → Frappe role for confirm fan-out notifications.
# F&B has no dedicated role yet; Front Desk covers banquet F&B ops.
DEPT_ROLE = {
	"Sales": "Front Desk",
	"Finance": "Finance",
	"Housekeeping": "Housekeeping",
	"F&B": "Front Desk",
	# no engineering or HR role in Kamra: their managers hear it
	"Engineering": "Hotel Admin",
	"HR": "Hotel Admin",
}

DEFAULT_TEMPLATES = {
	"Sales": [
		("Finalise BEO and pack list", 7),
		("Confirm guaranteed pax with guest", 5),
		("Issue / collect signed contract", 7),
	],
	"Finance": [
		("Verify advance received against terms", 14),
		("Confirm payment schedule and tax ID", 10),
	],
	"Housekeeping": [
		("Pre-function clean of hall and green room", 1),
		("Post-function reset scheduled", 0),
	],
	"F&B": [
		("Kitchen indent reviewed", 3),
		("Setup style and bar placement confirmed", 2),
	],
	"Engineering": [
		("AC set point agreed for the hall", 1),
		("Projector, HDMI and microphones tested", 1),
		("WiFi network ready, speed tested, guest coupons printed", 1),
	],
	"HR": [
		("Extra staff (male / female) rostered", 3),
		("Bar setup crew booked", 2),
	],
}


def _fn(name: str):
	return frappe.get_doc("Venue Booking", name)


def ensure_default_templates(property: str) -> int:
	"""Seed Sales/Finance/HK/F&B templates for a property if none exist."""
	created = 0
	for department, tasks in DEFAULT_TEMPLATES.items():
		existing = frappe.get_all(
			"Banquet Checklist Template",
			filters={"property": property, "department": department},
			fields=["name", "event_type"],
			limit=5,
		)
		# a blank event_type template already covers "all types"
		if any(not (r.event_type or "").strip() for r in existing):
			continue
		doc = frappe.get_doc({
			"doctype": "Banquet Checklist Template",
			"property": property,
			"department": department,
			"enabled": 1,
			"tasks": [
				{"title": title, "due_offset_days": days, "sort_order": i}
				for i, (title, days) in enumerate(tasks)
			],
		})
		doc.insert(ignore_permissions=True)
		created += 1
	return created


def instantiate_checklists(doc) -> list[str]:
	"""Clone enabled templates onto the function. Idempotent per title+dept."""
	ensure_default_templates(doc.property)
	created: list[str] = []
	templates = frappe.get_all(
		"Banquet Checklist Template",
		filters={"property": doc.property, "enabled": 1},
		pluck="name",
	)
	event = getdate(doc.event_date)
	for tname in templates:
		tmpl = frappe.get_doc("Banquet Checklist Template", tname)
		if tmpl.event_type and tmpl.event_type != (doc.event_type or ""):
			continue
		for row in tmpl.tasks:
			title = (row.title or "").strip()
			if not title:
				continue
			if frappe.db.exists(
				"Banquet Function Task",
				{
					"venue_booking": doc.name,
					"department": tmpl.department,
					"title": title,
				},
			):
				continue
			offset = int(row.due_offset_days or 0)
			due = add_days(event, -offset)
			task = frappe.get_doc({
				"doctype": "Banquet Function Task",
				"venue_booking": doc.name,
				"property": doc.property,
				"department": tmpl.department,
				"title": title,
				"due_date": due,
				"status": "Open",
				"template": tmpl.name,
			})
			task.insert(ignore_permissions=True)
			created.append(task.name)
	return created


def notify_departments_on_confirm(doc) -> None:
	"""Fan-out to Finance, HK, F&B (Front Desk), and sales_owner."""
	from kamra.housekeeping import _notify_role
	from kamra.savings import log_action

	body = _(
		"Banquet confirmed: {customer} · {venue} on {date} · {total}"
	).format(
		customer=doc.customer_name,
		venue=doc.venue,
		date=doc.event_date,
		total=frappe.format_value(float(doc.grand_total or 0), "Currency"),
	)
	roles_notified = set()
	for role in DEPT_ROLE.values():
		if role in roles_notified:
			continue
		_notify_role(doc.property, role, body)
		roles_notified.add(role)
	if doc.sales_owner:
		mobile = frappe.db.get_value("User", doc.sales_owner, "mobile_no")
		if mobile:
			try:
				from kamra.agents_channels import send_outbound
				send_outbound(doc.property, "WhatsApp", mobile, body)
			except Exception:
				# the notification is best-effort - but a silent failure means
				# nobody knows the team was never told
				frappe.log_error(title="Banquet: WhatsApp alert to staff failed")
	log_action(
		"banquet_confirm_notify",
		"Venue Booking",
		doc.name,
		doc.property,
		minutes_saved=5,
		rationale=body,
	)


def apply_deposit_rules(doc) -> dict:
	"""The property's deposit rules, on a function confirmed without its own:
	the default payment milestones (Settings -> Banquets & Groups) when it
	has none, and the refundable deposit when it holds none."""
	from kamra.banquet import default_payment_terms
	from kamra.settings import get_setting
	out = {"terms": False, "deposit": 0.0}
	if not doc.payment_terms and float(get_setting(doc.property, "banquet_advance_pct") or 0) \
			+ float(get_setting(doc.property, "banquet_interim_pct") or 0) > 0:
		default_payment_terms(doc.name)
		out["terms"] = True
	deposit = float(get_setting(doc.property, "banquet_refundable_deposit") or 0)
	if deposit > 0 and not float(frappe.db.get_value(
			"Venue Booking", doc.name, "refundable_deposit") or 0):
		fresh = frappe.get_doc("Venue Booking", doc.name)
		fresh.refundable_deposit = deposit
		fresh.save(ignore_permissions=True)
		out["deposit"] = deposit
	return out


def on_function_confirmed(doc) -> dict:
	"""Called when status first becomes Confirmed."""
	tasks = instantiate_checklists(doc)
	notify_departments_on_confirm(doc)
	rules = apply_deposit_rules(doc)
	return {"tasks_created": len(tasks), "task_names": tasks, "deposit_rules": rules}


def _quote_html(doc, payload: dict) -> str:
	"""Simple HTML body for the quotation email."""
	prop = payload.get("property") or {}
	lines = payload.get("lines") or payload.get("items") or []
	rows = ""
	for ln in lines:
		name = ln.get("item_name") or ln.get("description") or ""
		qty = ln.get("qty") or 1
		amount = ln.get("amount") or ln.get("line_total") or 0
		rows += (
			f"<tr><td>{frappe.utils.escape_html(str(name))}</td>"
			f"<td style='text-align:right'>{qty}</td>"
			f"<td style='text-align:right'>"
			f"{frappe.format_value(float(amount or 0), 'Currency')}</td></tr>"
		)
	hotel = prop.get("property_name") or prop.get("legal_name") or doc.property
	return f"""
	<div style="font-family:sans-serif;font-size:14px;color:#18181b">
	  <p>{frappe.utils.escape_html(str(hotel))}</p>
	  <h2>Quotation {frappe.utils.escape_html(str(doc.quote_number or ''))}
	      v{int(doc.quote_version or 0)}</h2>
	  <p>Dear {frappe.utils.escape_html(doc.customer_name or 'Guest')},</p>
	  <p>Please find our quotation for
	     <strong>{frappe.utils.escape_html(doc.event_name or doc.event_type or 'your event')}</strong>
	     on <strong>{doc.event_date}</strong> at
	     <strong>{frappe.utils.escape_html(str(doc.venue))}</strong>.</p>
	  <table style="border-collapse:collapse;width:100%;max-width:560px"
	         cellpadding="6">
	    <thead><tr style="background:#f4f4f5;text-align:left">
	      <th>Item</th><th style="text-align:right">Qty</th>
	      <th style="text-align:right">Amount</th>
	    </tr></thead>
	    <tbody>{rows}</tbody>
	  </table>
	  <p><strong>Total:
	     {frappe.format_value(float(doc.grand_total or 0), 'Currency')}</strong>
	     {" · valid till " + str(doc.quote_valid_till) if doc.quote_valid_till else ""}</p>
	  <p>Please reply to this email, call us, or message on WhatsApp to confirm
	     or request changes. Our sales desk will record your response.</p>
	  <p>Thank you,<br/>{frappe.utils.escape_html(str(hotel))}</p>
	</div>
	"""


def _quote_pdf(doc, html: str) -> dict | None:
	"""The quotation as a PDF attachment. None when the server can't render
	PDFs (no wkhtmltopdf): the email still goes, with the quote in its body."""
	try:
		from frappe.utils.pdf import get_pdf
		name = f"{doc.quote_number or doc.name}-v{int(doc.quote_version or 0)}.pdf"
		return {"fname": name.replace("/", "-"), "fcontent": get_pdf(html)}
	except Exception:
		frappe.log_error(title="Banquet: quotation PDF not rendered")
		return None


@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES)
def send_quotation(function: str, channels: str | list | None = None):
	"""Email (and optional WhatsApp) the stamped quotation to the guest.

	Does not open a guest portal — desk stays in the loop for confirmation.
	"""
	from kamra.banquet import _fn as fn_load
	from kamra.banquet import banquet_document
	from kamra.savings import log_action

	doc = fn_load(function)
	if not doc.quote_number and not int(doc.quote_version or 0):
		frappe.throw(_("Stamp a quotation first (Issue → Stamp quote)."))
	if not (doc.customer_email or "").strip() and not (doc.customer_phone or "").strip():
		frappe.throw(_("Add a customer email or phone before sending."))

	if isinstance(channels, str):
		import json
		try:
			channels = json.loads(channels)
		except Exception:
			channels = [c.strip() for c in channels.split(",") if c.strip()]
	channels = channels or ["email"]
	if not isinstance(channels, (list, tuple)):
		channels = ["email"]

	payload = banquet_document(function, "quote")
	html = _quote_html(doc, payload)
	pdf = _quote_pdf(doc, html)
	sent = []

	if "email" in channels:
		email = (doc.customer_email or "").strip()
		if not email:
			frappe.throw(_("Customer email is required to send by email."))
		subject = _("Quotation {0} — {1}").format(
			doc.quote_number or doc.name,
			doc.event_name or doc.customer_name,
		)
		frappe.sendmail(
			recipients=[email],
			subject=subject,
			message=html,
			reference_doctype="Venue Booking",
			reference_name=doc.name,
			attachments=[pdf] if pdf else None,
			now=True,
		)
		sent.append("email")

	if "whatsapp" in channels:
		phone = (doc.customer_phone or "").strip()
		if phone:
			try:
				from kamra.agents_channels import send_outbound
				text = _(
					"Quotation {num} for {event} on {date}: total {total}. "
					"Please reply to confirm or request changes."
				).format(
					num=doc.quote_number or doc.name,
					event=doc.event_name or doc.event_type or "your event",
					date=doc.event_date,
					total=frappe.format_value(float(doc.grand_total or 0), "Currency"),
				)
				send_outbound(doc.property, "WhatsApp", phone, text)
				sent.append("whatsapp")
			except Exception:
				frappe.log_error(title="banquet send_quotation whatsapp")

	if not sent:
		frappe.throw(_("Nothing was sent — check channels and guest contact."))

	doc.quote_emailed_on = now_datetime()
	doc.save(ignore_permissions=True)
	log_action(
		"banquet_quote_sent",
		"Venue Booking",
		doc.name,
		doc.property,
		minutes_saved=10,
		rationale=f"Quote v{doc.quote_version} sent via {', '.join(sent)} "
		          f"to {doc.customer_email or doc.customer_phone}",
	)
	return {
		"ok": True,
		"sent": sent,
		"quote_emailed_on": str(doc.quote_emailed_on),
		"quote_version": doc.quote_version,
	}


@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES)
def record_guest_response(
	function: str,
	outcome: str,
	channel: str | None = None,
	notes: str | None = None,
	confirm_status: int = 0,
):
	"""Desk records how the guest responded (phone / email / WhatsApp).

	outcome: Confirmed | Changes Requested | Declined
	If confirm_status and outcome is Confirmed, also moves Tentative/Enquiry → Confirmed.
	"""
	from kamra.banquet import _fn as fn_load
	from kamra.banquet import set_status
	from kamra.savings import log_action

	outcome = (outcome or "").strip()
	if outcome not in ("Confirmed", "Changes Requested", "Declined"):
		frappe.throw(_("Unknown guest response: {0}").format(outcome))
	channel = (channel or "Phone").strip()
	if channel not in ("Phone", "Email", "WhatsApp"):
		frappe.throw(_("Unknown channel: {0}").format(channel))

	doc = fn_load(function)
	doc.customer_confirmed_on = nowdate()
	doc.customer_confirm_channel = channel
	doc.customer_confirm_outcome = outcome
	doc.customer_confirm_notes = (notes or "").strip()[:500] or None
	doc.save(ignore_permissions=True)

	log_action(
		"banquet_guest_response",
		"Venue Booking",
		doc.name,
		doc.property,
		minutes_saved=5,
		rationale=f"Guest {outcome} via {channel}"
		          + (f": {notes}" if notes else ""),
	)

	status_result = None
	if int(confirm_status or 0) and outcome == "Confirmed" \
			and doc.status in ("Enquiry", "Tentative"):
		status_result = set_status(function, "Confirmed")

	return {
		"ok": True,
		"customer_confirmed_on": str(doc.customer_confirmed_on),
		"customer_confirm_outcome": doc.customer_confirm_outcome,
		"customer_confirm_channel": doc.customer_confirm_channel,
		"status": status_result,
	}


@frappe.whitelist()
@require_roles(*READ_ROLES)
def function_tasks(function: str):
	"""Checklist tasks for one function, grouped by department."""
	rows = frappe.get_all(
		"Banquet Function Task",
		filters={"venue_booking": function},
		fields=["name", "department", "title", "due_date", "status",
		        "completed_on", "completed_by"],
		order_by="department, due_date, creation",
	)
	open_n = sum(1 for r in rows if r.status == "Open")
	done_n = sum(1 for r in rows if r.status == "Done")
	by_dept: dict[str, list] = {}
	for r in rows:
		by_dept.setdefault(r.department, []).append(r)
	return {
		"function": function,
		"open": open_n,
		"done": done_n,
		"total": len(rows),
		"departments": [
			{"department": k, "tasks": v} for k, v in by_dept.items()
		],
	}


@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES, "Finance", "Housekeeping")
def complete_function_task(task: str, done: int = 1):
	"""Mark a department checklist task done (or reopen)."""
	doc = frappe.get_doc("Banquet Function Task", task)
	if int(done or 0):
		doc.status = "Done"
		doc.completed_on = now_datetime()
		doc.completed_by = frappe.session.user
	else:
		doc.status = "Open"
		doc.completed_on = None
		doc.completed_by = None
	doc.save(ignore_permissions=True)
	return {"ok": True, "name": doc.name, "status": doc.status}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin", "System Manager", "Administrator")
def seed_banquet_checklist_templates(property: str):
	"""Ensure default department templates exist for this property."""
	n = ensure_default_templates(property)
	return {"ok": True, "created": n}


def quote_no_response_alert(doc) -> dict | None:
	"""Quote emailed (or issued) ≥3 days ago, still open, no guest response."""
	if doc.status not in ("Enquiry", "Tentative"):
		return None
	if doc.customer_confirm_outcome:
		return None
	sent = doc.quote_emailed_on or doc.quote_sent_on
	if not sent:
		return None
	sent_day = getdate(sent)
	if (getdate(nowdate()) - sent_day).days < 3:
		return None
	via = _("emailed") if doc.quote_emailed_on else _("issued")
	return {
		"kind": "quote_no_response",
		"urgency": "high",
		"message": _(
			"Quote {0} was {1} on {2} with no guest response yet."
		).format(doc.quote_number or f"v{doc.quote_version}", via, sent_day),
	}


def maybe_email_guest_quote_chase(doc, alert: dict) -> None:
	"""Best-effort guest email when quote_no_response fires."""
	email = (doc.customer_email or "").strip()
	if not email:
		return
	try:
		frappe.sendmail(
			recipients=[email],
			subject=_("Following up: quotation {0}").format(
				doc.quote_number or doc.name),
			message=_(
				"<p>Dear {name},</p>"
				"<p>We sent a quotation for your event on {date} and have not "
				"heard back. Please reply to this email, call us, or message "
				"on WhatsApp so we can hold the hall for you.</p>"
				"<p>Thank you.</p>"
			).format(name=frappe.utils.escape_html(doc.customer_name or "Guest"),
			         date=doc.event_date),
			reference_doctype="Venue Booking",
			reference_name=doc.name,
			now=True,
		)
	except Exception:
		frappe.log_error(title="banquet quote chase email")


# ══ food tasting (Phase 2) ═══════════════════════════════════════════════

def _staff_alert(property: str, users, body: str) -> None:
	"""WhatsApp each staff user who has a mobile; best-effort."""
	from kamra.agents_channels import send_outbound
	for user in {u for u in users if u}:
		mobile = frappe.db.get_value("User", user, "mobile_no")
		if not mobile:
			continue
		try:
			send_outbound(property, "WhatsApp", mobile, body)
		except Exception:
			frappe.log_error(title="Banquet: staff alert failed")


def _ics(doc, start, minutes: int = 60) -> bytes:
	"""A one-event calendar invite for the tasting (RFC 5545, floating time)."""
	from frappe.utils import add_to_date, get_datetime
	fmt = "%Y%m%dT%H%M%S"
	begin = get_datetime(start)
	end = add_to_date(begin, minutes=minutes)
	hotel = frappe.db.get_value("Property", doc.property, "property_name") or doc.property
	lines = [
		"BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Kamra PMS//Banquet//EN",
		"METHOD:PUBLISH", "BEGIN:VEVENT",
		f"UID:tasting-{doc.name}@kamra",
		f"DTSTAMP:{now_datetime().strftime(fmt)}",
		f"DTSTART:{begin.strftime(fmt)}", f"DTEND:{end.strftime(fmt)}",
		f"SUMMARY:Food tasting - {doc.event_name or doc.event_type or doc.name}",
		f"LOCATION:{hotel}", "END:VEVENT", "END:VCALENDAR", "",
	]
	return "\r\n".join(lines).encode()


def _menu_lines(doc) -> list[str]:
	return [r.item_name for r in doc.items if r.item_type == "Menu" and r.item_name]


@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES)
def schedule_tasting(function: str, tasting_on: str, pax: int | None = None,
                     chef: str | None = None, notes: str | None = None,
                     email_guest: int = 1):
	"""Book the food tasting: the guest gets an email with the menu and a
	calendar invite, the chef and the sales owner a WhatsApp alert."""
	from kamra.banquet import _fn as fn_load
	from kamra.savings import log_action
	from kamra.settings import get_setting
	doc = fn_load(function)
	if not int(get_setting(doc.property, "banquet_tasting_allowed") or 0):
		frappe.throw(_("Food tastings are switched off for this property "
		               "(Settings -> Banquets & Groups)."))
	if doc.status not in ("Enquiry", "Tentative", "Confirmed"):
		frappe.throw(_("A {0} function doesn't get a tasting.").format(doc.status))
	if not tasting_on:
		frappe.throw(_("Pick when the tasting is."))
	doc.tasting_status = "Scheduled"
	doc.tasting_on = tasting_on
	doc.tasting_pax = int(pax or doc.tasting_pax
	                      or get_setting(doc.property, "banquet_tasting_pax") or 4)
	doc.tasting_chef = chef or doc.tasting_chef
	if notes is not None:
		doc.tasting_notes = (notes or "").strip()[:1000] or None
	emailed = False
	email = (doc.customer_email or "").strip()
	if int(email_guest or 0) and email:
		menu = _menu_lines(doc)
		frappe.sendmail(
			recipients=[email],
			subject=_("Your food tasting for {0}").format(
				doc.event_name or doc.event_type or doc.name),
			message=_(
				"<p>Dear {name},</p><p>Your food tasting is booked for "
				"<strong>{when}</strong> for {pax} people.</p>{menu}"
				"<p>The calendar invite is attached. Reply to this email if "
				"you need another time.</p>"
			).format(name=frappe.utils.escape_html(doc.customer_name or "Guest"),
			         when=doc.tasting_on, pax=doc.tasting_pax,
			         menu=("<p>" + _("We will serve:") + "</p><ul>"
			               + "".join(f"<li>{frappe.utils.escape_html(m)}</li>" for m in menu)
			               + "</ul>") if menu else ""),
			attachments=[{"fname": "tasting.ics", "fcontent": _ics(doc, doc.tasting_on)}],
			reference_doctype="Venue Booking", reference_name=doc.name, now=True)
		doc.tasting_invited_on = now_datetime()
		emailed = True
	doc.save(ignore_permissions=True)
	body = _("Food tasting: {customer} on {when}, {pax} pax ({event} {date}).").format(
		customer=doc.customer_name, when=doc.tasting_on, pax=doc.tasting_pax,
		event=doc.event_type or "", date=doc.event_date)
	_staff_alert(doc.property, [doc.tasting_chef, doc.sales_owner], body)
	if not doc.tasting_chef:
		from kamra.housekeeping import _notify_role
		_notify_role(doc.property, "F&B Manager", body)
	log_action("banquet_tasting", "Venue Booking", doc.name, doc.property,
	           minutes_saved=10, rationale=body)
	return {"ok": True, "tasting_status": doc.tasting_status,
	        "tasting_on": str(doc.tasting_on), "emailed": emailed}


@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES)
def record_tasting(function: str, outcome: str = "Done", notes: str | None = None):
	"""After the tasting (or when the guest skips it): what they thought goes
	on the function for the menu, and the sales owner hears."""
	from kamra.banquet import _fn as fn_load
	from kamra.savings import log_action
	if outcome not in ("Done", "Waived"):
		frappe.throw(_("A tasting is Done or Waived."))
	doc = fn_load(function)
	doc.tasting_status = outcome
	if (notes or "").strip():
		doc.tasting_notes = notes.strip()[:1000]
	doc.save(ignore_permissions=True)
	body = _("Tasting {0} for {1}: {2}").format(
		_(outcome).lower(), doc.customer_name, doc.tasting_notes or "-")
	_staff_alert(doc.property, [doc.sales_owner], body)
	log_action("banquet_tasting_done", "Venue Booking", doc.name, doc.property,
	           rationale=body)
	return {"ok": True, "tasting_status": doc.tasting_status}


def tasting_alert(doc) -> dict | None:
	"""A tasting asked for but not booked, within three weeks of the date."""
	if doc.tasting_status != "Requested" or doc.status not in ("Tentative", "Confirmed"):
		return None
	if (getdate(doc.event_date) - getdate(nowdate())).days > 21:
		return None
	return {"kind": "tasting_unscheduled", "urgency": "normal",
	        "message": _("The guest asked for a food tasting - book it.")}


# ══ payment links and guest balance reminders (Phase 2) ══════════════════
# A one-off gateway link per payment milestone (no guest portal). The
# gateway's webhook comes back through kamra.payments.handle_webhook, which
# routes a banquet link here by the "VB:" reference in its notes.

LINK_PREFIX = "VB:"


def _term(doc, term: str):
	row = next((t for t in doc.payment_terms if t.name == term), None)
	if not row:
		frappe.throw(_("No such payment term on this function."))
	return row


def create_term_link(doc, row) -> dict:
	"""A gateway link for what one milestone still asks for."""
	from kamra import localization as loc
	from kamra.payments import _settings
	if row.status == "Received":
		frappe.throw(_("{0} is already received.").format(row.milestone))
	amount = round(float(row.amount or 0), 2)
	if amount <= 0:
		frappe.throw(_("{0} has no amount to pay.").format(row.milestone))
	pack = loc.pack_for(doc.property)
	if not loc.payment_gateways(pack):
		frappe.throw(_("Online payment links are not available for this property's country."))
	settings = _settings(doc.property)
	currency = (frappe.get_cached_value("Property", doc.property, "currency")
	            or loc.default_currency(pack)).upper()
	ref = f"{LINK_PREFIX}{doc.name}:{row.name}"
	if settings.test_mode:
		link_id = f"plink_TEST{frappe.generate_hash(length=10)}"
		url = loc.test_gateway_link(pack, settings.gateway, link_id)
	else:
		link_id, url = loc.create_gateway_link(
			pack, settings, amount=amount, currency=currency, reference=doc.name,
			description=f"{row.milestone} · {doc.event_name or doc.event_type} {doc.event_date}",
			customer={"name": doc.customer_name or "", "contact": doc.customer_phone or "",
			          "email": doc.customer_email or ""},
			notes={"folio": ref, "property": doc.property})
	frappe.db.set_value("Banquet Payment Term", row.name,
	                    {"payment_link_id": link_id, "payment_link_url": url},
	                    update_modified=False)
	row.payment_link_id, row.payment_link_url = link_id, url
	return {"url": url, "link_id": link_id, "amount": amount, "currency": currency,
	        "test_mode": bool(settings.test_mode)}


def _email_term(doc, row, url: str | None, reminder: bool) -> bool:
	email = (doc.customer_email or "").strip()
	if not email:
		return False
	amount = frappe.format_value(float(row.amount or 0), "Currency")
	pay = (f'<p><a href="{frappe.utils.escape_html(url)}">' + _("Pay {0} online").format(amount)
	       + "</a></p>") if url else ""
	frappe.sendmail(
		recipients=[email],
		subject=(_("Reminder: {0} due for your event on {1}") if reminder
		         else _("{0} for your event on {1}")).format(row.milestone, doc.event_date),
		message=_(
			"<p>Dear {name},</p><p>{milestone}: <strong>{amount}</strong> is due "
			"{due} for {event} on {date}.</p>{pay}<p>If you have already paid, "
			"thank you - please ignore this note.</p>"
		).format(name=frappe.utils.escape_html(doc.customer_name or "Guest"),
		         milestone=frappe.utils.escape_html(row.milestone), amount=amount,
		         due=row.due_date or "", event=frappe.utils.escape_html(
			         doc.event_name or doc.event_type or ""),
		         date=doc.event_date, pay=pay),
		reference_doctype="Venue Booking", reference_name=doc.name, now=True)
	return True


@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES, "Finance")
def send_payment_link(function: str, term: str, channels: str | list | None = None):
	"""Send the guest a one-off payment link for one milestone, by email
	and/or WhatsApp. Paying it records the receipt and ticks the milestone."""
	import json
	from kamra.banquet import _fn as fn_load
	from kamra.savings import log_action
	doc = fn_load(function)
	row = _term(doc, term)
	if isinstance(channels, str):
		try:
			channels = json.loads(channels)
		except ValueError:
			channels = [c.strip() for c in channels.split(",") if c.strip()]
	channels = channels or ["email"]
	link = create_term_link(doc, row)
	sent = []
	if "email" in channels and _email_term(doc, row, link["url"], reminder=False):
		sent.append("email")
	if "whatsapp" in channels and (doc.customer_phone or "").strip():
		try:
			from kamra.agents_channels import send_outbound
			send_outbound(doc.property, "WhatsApp", doc.customer_phone.strip(), _(
				"{0} for your event on {1}: {2}. Pay here: {3}").format(
				row.milestone, doc.event_date,
				frappe.format_value(float(row.amount or 0), "Currency"), link["url"]))
			sent.append("whatsapp")
		except Exception:
			frappe.log_error(title="Banquet: payment link WhatsApp failed")
	log_action("banquet_payment_link", "Venue Booking", doc.name, doc.property,
	           minutes_saved=4, rationale=f"{row.milestone} link {link['currency']} "
	                                       f"{link['amount']:,.2f} sent via {', '.join(sent) or 'none'}")
	return {**link, "sent": sent}


def settle_term_link(ref: str, link_id: str, amount: float) -> bool:
	"""A banquet link was paid: the receipt goes on the function against its
	milestone, once per link payment."""
	from kamra.business_date import get_business_date
	from kamra.savings import log_action
	function, _sep, term = ref[len(LINK_PREFIX):].partition(":")
	if amount <= 0 or not frappe.db.exists("Venue Booking", function):
		return False
	doc = frappe.get_doc("Venue Booking", function)
	if any(r.reference == link_id for r in doc.receipts):
		return False
	row = next((t for t in doc.payment_terms if t.name == term), None)
	rd = get_business_date(doc.property)
	doc.append("receipts", {
		"receipt_date": rd, "kind": "Payment" if doc.status == "Completed" else "Advance",
		"mode": "Payment Link", "amount": float(amount), "reference": link_id,
		"received_by": frappe.session.user})
	if row and row.status != "Received":
		row.status, row.received_on, row.reference = "Received", rd, link_id
	doc.save(ignore_permissions=True)
	log_action("banquet_receipt", "Venue Booking", doc.name, doc.property,
	           agent_name="Payments", channel="API",
	           rationale=f"{amount:,.2f} received by payment link for {doc.customer_name}")
	return True


def remind_guest_balance(doc, today=None) -> list[str]:
	"""Guest-facing reminder for each milestone due within three days or
	overdue, with a payment link when the property takes online payments.
	At most one per milestone every three days."""
	today = getdate(today or nowdate())
	sent = []
	if doc.status not in ("Tentative", "Confirmed", "Completed"):
		return sent
	for row in doc.payment_terms:
		if row.status not in ("Pending", "Overdue") or not row.due_date \
				or getdate(row.due_date) > add_days(today, 3) or float(row.amount or 0) <= 0:
			continue
		if row.guest_reminded_on and (today - getdate(row.guest_reminded_on)).days < 3:
			continue
		url = row.payment_link_url
		if not url:
			try:
				url = create_term_link(doc, row)["url"]
			except frappe.ValidationError:
				url = None  # no gateway here: the reminder still goes
				frappe.clear_messages()
		if _email_term(doc, row, url, reminder=True):
			frappe.db.set_value("Banquet Payment Term", row.name, "guest_reminded_on",
			                    today, update_modified=False)
			sent.append(row.name)
	return sent


# ══ equipment calendar (Phase 3) ═════════════════════════════════════════

def _days(start, end):
	d = getdate(start)
	while d <= getdate(end):
		yield d
		d = add_days(d, 1)


def equipment_bookings(property: str, start, end, statuses=("Tentative", "Confirmed"),
                       exclude: str | None = None) -> list[dict]:
	"""Tracked equipment (a service item with units owned) on each function
	running between start and end: [{function, service_item, qty, ...}]."""
	rows = frappe.db.sql(
		"""SELECT vb.name AS function, vb.customer_name, vb.status, vb.event_date,
		          COALESCE(vb.end_date, vb.event_date) AS end_date,
		          vb.start_time, vb.end_time, vb.venue,
		          i.service_item, s.item_name, s.stock_qty,
		          SUM(CASE WHEN i.uom = 'Hour' THEN 1 ELSE i.qty END) AS qty
		   FROM `tabVenue Booking` vb
		   JOIN `tabBanquet Function Item` i ON i.parent = vb.name
		        AND i.parenttype = 'Venue Booking'
		   JOIN `tabBanquet Service Item` s ON s.name = i.service_item
		   WHERE vb.property = %(p)s AND vb.status IN %(st)s
		     AND vb.event_date <= %(e)s AND COALESCE(vb.end_date, vb.event_date) >= %(s)s
		     AND IFNULL(s.stock_qty, 0) > 0 AND vb.name != %(x)s
		   GROUP BY vb.name, i.service_item""",
		{"p": property, "st": tuple(statuses), "s": str(start), "e": str(end),
		 "x": exclude or ""}, as_dict=True)
	return rows


def equipment_overbooked(doc) -> str | None:
	"""Whether this function, with the other confirmed ones at the same
	time, needs more of a tracked item than the hotel owns."""
	from kamra.kamra.doctype.venue_booking.venue_booking import _times_overlap
	want: dict[str, float] = {}
	for r in doc.items:
		if r.service_item:
			# an hourly line's qty is hours, not units: it is one unit
			units = 1.0 if r.uom == "Hour" else float(r.qty or 0)
			want[r.service_item] = want.get(r.service_item, 0.0) + units
	if not want:
		return None
	stock = dict(frappe.get_all("Banquet Service Item", filters={
		"name": ("in", list(want)), "stock_qty": (">", 0)},
		fields=["name", "stock_qty"], as_list=True))
	if not stock:
		return None
	end = doc.end_date or doc.event_date
	others = [o for o in equipment_bookings(doc.property, doc.event_date, end,
	                                       statuses=("Confirmed",), exclude=doc.name)
	          if o.service_item in stock]
	for item, qty in want.items():
		if item not in stock:
			continue
		for day in _days(doc.event_date, end):
			used = qty
			for o in others:
				if o.service_item != item or not (getdate(o.event_date) <= day <= getdate(o.end_date)):
					continue
				if doc.start_time and doc.end_time and o.start_time and o.end_time \
						and not _times_overlap(doc.event_date, doc.start_time, doc.end_date,
						                       doc.end_time, o.event_date, o.start_time,
						                       o.end_date, o.end_time):
					continue
				used += float(o.qty or 0)
			if used > float(stock[item]):
				name = frappe.db.get_value("Banquet Service Item", item, "item_name")
				return _("Only {0} {1} - {2} are needed on {3} with the other "
				         "confirmed functions.").format(int(stock[item]), name,
				                                        int(used), day)
	return None


@frappe.whitelist()
@require_roles(*READ_ROLES)
def equipment_calendar(property: str, start_date: str | None = None, days: int = 30):
	"""Each tracked item, each day: units owned, units booked (confirmed and
	tentative) and by which functions."""
	start = getdate(start_date or nowdate())
	days = min(max(int(days or 30), 1), 92)
	end = add_days(start, days - 1)
	items = frappe.get_all("Banquet Service Item",
	                       filters={"property": property, "stock_qty": (">", 0), "disabled": 0},
	                       fields=["name", "item_name", "category", "stock_qty"],
	                       order_by="category, item_name")
	bookings = equipment_bookings(property, start, end)
	out = []
	for it in items:
		row = {"item": it.name, "item_name": it.item_name, "category": it.category,
		       "stock_qty": int(it.stock_qty), "days": []}
		for day in _days(start, end):
			on = [b for b in bookings if b.service_item == it.name
			      and getdate(b.event_date) <= day <= getdate(b.end_date)]
			confirmed = sum(float(b.qty or 0) for b in on if b.status == "Confirmed")
			row["days"].append({
				"date": str(day), "confirmed": confirmed,
				"tentative": sum(float(b.qty or 0) for b in on if b.status == "Tentative"),
				"over": confirmed > it.stock_qty,
				"functions": [{"function": b.function, "customer_name": b.customer_name,
				               "status": b.status, "qty": float(b.qty or 0)} for b in on]})
		out.append(row)
	return {"start": str(start), "end": str(end), "items": out}
