"""Banquet enterprise (issue #67 Phase 1): send quote, desk guest confirm,
department checklists on Confirm, quote no-response reminders.

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
}

DEFAULT_TEMPLATES = {
	"Sales": [
		("Finalise BEO and pack list", 7),
		("Confirm guaranteed pax with guest", 5),
		("Issue / collect signed contract", 7),
	],
	"Finance": [
		("Verify advance received against terms", 14),
		("Confirm payment schedule and GSTIN", 10),
	],
	"Housekeeping": [
		("Pre-function clean of hall and green room", 1),
		("Post-function reset scheduled", 0),
	],
	"F&B": [
		("Kitchen indent reviewed", 3),
		("Setup style and bar placement confirmed", 2),
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
	for department, role in DEPT_ROLE.items():
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
				pass
	log_action(
		"banquet_confirm_notify",
		"Venue Booking",
		doc.name,
		doc.property,
		minutes_saved=5,
		rationale=body,
	)


def on_function_confirmed(doc) -> dict:
	"""Called when status first becomes Confirmed."""
	tasks = instantiate_checklists(doc)
	notify_departments_on_confirm(doc)
	return {"tasks_created": len(tasks), "task_names": tasks}


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
	    <tbody>{rows or '<tr><td colspan="3">See attached details</td></tr>'}</tbody>
	  </table>
	  <p><strong>Total:
	     {frappe.format_value(float(doc.grand_total or 0), 'Currency')}</strong>
	     {" · valid till " + str(doc.quote_valid_till) if doc.quote_valid_till else ""}</p>
	  <p>Please reply to this email, call us, or message on WhatsApp to confirm
	     or request changes. Our sales desk will record your response.</p>
	  <p>Thank you,<br/>{frappe.utils.escape_html(str(hotel))}</p>
	</div>
	"""


@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES)
def send_quotation(function: str, channels: str | list | None = None):
	"""Email (and optional WhatsApp) the stamped quotation to the guest.

	Does not open a guest portal — desk stays in the loop for confirmation.
	"""
	from kamra.banquet import banquet_document, _fn as fn_load
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
	from kamra.banquet import set_status, _fn as fn_load
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
