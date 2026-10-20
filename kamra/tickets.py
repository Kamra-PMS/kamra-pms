"""Service tickets: who has it, who solved it, and the whole story.

A ticket carries an assignee (assigned_to_user), who assigned it and when,
when someone first picked it up, and who resolved it. Every change leaves a
Ticket Event, so a ticket opened months ago can still be read end to end:
created, assigned to whom, what was done, who closed it, and whether it
came back. The SLA clock itself (due_by, breached) is unchanged.

Tickets from before this existed have no events and no resolver: the
detail shows what the ticket itself still knows (created, resolved on) and
leaves the person blank rather than guess."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime, time_diff_in_seconds

from kamra.authz import assert_property_access, require_roles

OPS_ROLES = ("Front Desk", "Housekeeping", "Housekeeping Supervisor",
             "Hotel Admin", "Kamra Agent")
# who can be handed a ticket
ASSIGNABLE_ROLES = ("Front Desk", "Housekeeping", "Housekeeping Supervisor",
                    "Hotel Admin")
OPEN_STATES = ("Open", "In Progress")
DONE_STATES = ("Resolved", "Closed", "Cancelled")


def log_event(ticket, kind: str, from_value=None, to_value=None, note=None):
	"""Append a line to the ticket's timeline."""
	frappe.get_doc({
		"doctype": "Ticket Event", "ticket": ticket.name,
		"property": ticket.property, "kind": kind, "by": frappe.session.user,
		"at": now_datetime(), "from_value": (str(from_value) if from_value else None),
		"to_value": (str(to_value) if to_value else None),
		"note": (note or "")[:500] or None,
	}).insert(ignore_permissions=True)


def _names(users) -> dict[str, str]:
	users = [u for u in set(users) if u]
	if not users:
		return {}
	return {u.name: u.full_name or u.name for u in frappe.get_all(
		"User", filters={"name": ["in", users]}, fields=["name", "full_name"])}


def _minutes_left(due_by) -> int | None:
	if not due_by:
		return None
	return int(time_diff_in_seconds(get_datetime(due_by), now_datetime()) // 60)


@frappe.whitelist()
@require_roles(*OPS_ROLES)
def tickets_search(property: str, view: str = "open", category: str | None = None,
                   priority: str | None = None, q: str | None = None,
                   assignee: str | None = None, older_than_days: int = 0,
                   limit: int = 200):
	"""Tickets for a property with the filters a supervisor needs.

	view: open (default), mine, unassigned, overdue, resolved, all. Old
	tickets are never hidden: 'all' and 'resolved' go back as far as the
	data does, and older_than_days narrows to the ones still open past that."""
	assert_property_access(property)
	me = frappe.session.user
	now = str(now_datetime())
	where = ["t.property = %(p)s"]
	args: dict = {"p": property, "me": me, "now": now, "lim": min(int(limit or 200), 500)}
	if view == "open":
		where.append("t.status IN ('Open','In Progress')")
	elif view == "mine":
		where.append("t.status IN ('Open','In Progress') AND t.assigned_to_user = %(me)s")
	elif view == "unassigned":
		where.append("t.status IN ('Open','In Progress') AND (t.assigned_to_user IS NULL OR t.assigned_to_user = '')")
	elif view == "overdue":
		where.append("t.status IN ('Open','In Progress') AND t.due_by < %(now)s")
	elif view == "resolved":
		where.append("t.status IN ('Resolved','Closed')")
	if category:
		where.append("t.category = %(cat)s")
		args["cat"] = category
	if priority:
		where.append("t.priority = %(pri)s")
		args["pri"] = priority
	if assignee:
		where.append("t.assigned_to_user = %(asg)s")
		args["asg"] = assignee
	if int(older_than_days or 0) > 0:
		where.append("t.status IN ('Open','In Progress') AND t.creation < DATE_SUB(%(now)s, INTERVAL %(days)s DAY)")
		args["days"] = int(older_than_days)
	if q and q.strip():
		where.append("(t.subject LIKE %(q)s OR t.name LIKE %(q)s OR t.room LIKE %(q)s "
		             "OR t.guest_name LIKE %(q)s OR t.description LIKE %(q)s)")
		args["q"] = f"%{q.strip()}%"
	rows = frappe.db.sql(
		f"""SELECT t.name, t.subject, t.category, t.priority, t.status, t.source, t.room,
		           t.guest_name, t.due_by, t.resolved_on, t.breached, t.assigned_to_user,
		           t.resolved_by, t.first_response_at, t.reopened_count, t.creation
		    FROM `tabService Ticket` t WHERE {' AND '.join(where)}
		    ORDER BY (t.status IN ('Open','In Progress')) DESC, t.due_by ASC, t.creation DESC
		    LIMIT %(lim)s""", args, as_dict=True)  # nosemgrep: frappe-sql-format-injection -- fixed clauses, values bound
	names = _names([r.assigned_to_user for r in rows] + [r.resolved_by for r in rows])
	for r in rows:
		is_open = r.status in OPEN_STATES
		r["assigned_to_name"] = names.get(r.assigned_to_user)
		r["resolved_by_name"] = names.get(r.resolved_by)
		r["age_hours"] = round(time_diff_in_seconds(now_datetime(), get_datetime(r.creation)) / 3600, 1)
		r["minutes_left"] = _minutes_left(r.due_by) if is_open else None
		r["overdue"] = bool(is_open and r.minutes_left is not None and r.minutes_left < 0)
	cnt = frappe.db.sql(
		"""SELECT
		     SUM(status IN ('Open','In Progress')) AS open_n,
		     SUM(status IN ('Open','In Progress') AND assigned_to_user = %(me)s) AS mine,
		     SUM(status IN ('Open','In Progress') AND (assigned_to_user IS NULL OR assigned_to_user = '')) AS unassigned,
		     SUM(status IN ('Open','In Progress') AND due_by < %(now)s) AS overdue,
		     SUM(status IN ('Resolved','Closed')) AS resolved,
		     COUNT(*) AS total
		   FROM `tabService Ticket` WHERE property = %(p)s""", args, as_dict=True)[0]
	return {"tickets": rows,
	        "counts": {"open": int(cnt.open_n or 0), "mine": int(cnt.mine or 0),
	                   "unassigned": int(cnt.unassigned or 0), "overdue": int(cnt.overdue or 0),
	                   "resolved": int(cnt.resolved or 0), "all": int(cnt.total or 0)}}


@frappe.whitelist()
@require_roles(*OPS_ROLES)
def ticket_detail(ticket: str):
	"""One ticket in full: its fields, SLA, and the timeline."""
	doc = frappe.get_doc("Service Ticket", ticket)
	assert_property_access(doc.property)
	events = frappe.get_all(
		"Ticket Event", filters={"ticket": ticket},
		fields=["kind", "by", "at", "from_value", "to_value", "note"], order_by="at asc, creation asc")
	people = [e.by for e in events] + [doc.assigned_to_user, doc.assigned_by, doc.resolved_by,
	                                   *[e.from_value for e in events if e.kind == "Assigned"],
	                                   *[e.to_value for e in events if e.kind == "Assigned"]]
	names = _names(people)
	for e in events:
		e["by_name"] = names.get(e.by) or e.by
		if e.kind == "Assigned":
			e["from_name"] = names.get(e.from_value) if e.from_value else None
			e["to_name"] = names.get(e.to_value) if e.to_value else None
	if not events:
		# a ticket from before the timeline: show what it still knows
		events = [{"kind": "Created", "by": doc.owner, "by_name": names.get(doc.owner) or doc.owner,
		           "at": doc.creation, "to_value": doc.source, "note": doc.subject,
		           "from_value": None}]
		if doc.resolved_on:
			events.append({"kind": "Status", "by": doc.resolved_by, "by_name": names.get(doc.resolved_by),
			               "at": doc.resolved_on, "from_value": None, "to_value": "Resolved",
			               "note": doc.resolution_note})
	is_open = doc.status in OPEN_STATES
	end = get_datetime(doc.resolved_on) if doc.resolved_on else now_datetime()
	d = doc.as_dict()
	d.update({
		"assigned_to_name": names.get(doc.assigned_to_user),
		"assigned_by_name": names.get(doc.assigned_by),
		"resolved_by_name": names.get(doc.resolved_by),
		"events": events,
		"age_hours": round(time_diff_in_seconds(now_datetime(), get_datetime(doc.creation)) / 3600, 1),
		"minutes_left": _minutes_left(doc.due_by) if is_open else None,
		"overdue": bool(is_open and doc.due_by and now_datetime() > get_datetime(doc.due_by)),
		"resolve_minutes": round(time_diff_in_seconds(end, get_datetime(doc.creation)) / 60)
		                   if not is_open and doc.resolved_on else None,
		"response_minutes": round(time_diff_in_seconds(get_datetime(doc.first_response_at),
		                                               get_datetime(doc.creation)) / 60)
		                    if doc.first_response_at else None,
	})
	return d


@frappe.whitelist()
@require_roles(*OPS_ROLES)
def ticket_assignees(property: str):
	"""Staff a ticket can be handed to."""
	assert_property_access(property)
	users = frappe.db.sql(
		"""SELECT DISTINCT u.name, u.full_name FROM `tabUser` u
		   JOIN `tabHas Role` r ON r.parent = u.name AND r.parenttype = 'User'
		   WHERE u.enabled = 1 AND u.user_type = 'System User'
		     AND r.role IN %(roles)s AND u.name NOT IN ('Administrator', 'Guest')
		   ORDER BY u.full_name""", {"roles": ASSIGNABLE_ROLES}, as_dict=True)
	from kamra.authz import restricted_properties
	out = []
	for u in users:
		limited = restricted_properties(u.name)
		if limited is not None and property not in limited:
			continue
		out.append({"user": u.name, "name": u.full_name or u.name})
	return out


@frappe.whitelist(methods=["POST"])
@require_roles(*OPS_ROLES)
def assign_ticket(ticket: str, user: str | None = None, note: str | None = None):
	"""Hand a ticket to someone, or clear the assignee (user empty)."""
	doc = frappe.get_doc("Service Ticket", ticket)
	assert_property_access(doc.property)
	if doc.status in DONE_STATES:
		frappe.throw(_("This ticket is {0}. Reopen it before assigning it.").format(_(doc.status)))
	if user:
		if not frappe.db.get_value("User", user, "enabled"):
			frappe.throw(_("{0} is not an active user.").format(user))
		if not set(frappe.get_roles(user)) & set(ASSIGNABLE_ROLES):
			frappe.throw(_("{0} cannot be assigned tickets (needs a front desk or housekeeping role).").format(user))
	doc.assigned_to_user = user or None
	doc.save()
	if note and note.strip():
		log_event(doc, "Note", note=note.strip())
	return ticket_detail(ticket)


@frappe.whitelist(methods=["POST"])
@require_roles(*OPS_ROLES)
def claim_ticket(ticket: str):
	"""Take a ticket yourself."""
	return assign_ticket(ticket, frappe.session.user)


@frappe.whitelist(methods=["POST"])
@require_roles(*OPS_ROLES)
def start_ticket(ticket: str):
	"""Begin work: moves it to In Progress and, if nobody has it, gives it to you."""
	doc = frappe.get_doc("Service Ticket", ticket)
	assert_property_access(doc.property)
	if doc.status != "Open":
		frappe.throw(_("Only an open ticket can be started."))
	if not doc.assigned_to_user:
		doc.assigned_to_user = frappe.session.user
	doc.status = "In Progress"
	doc.save()
	return ticket_detail(ticket)


@frappe.whitelist(methods=["POST"])
@require_roles(*OPS_ROLES)
def add_ticket_note(ticket: str, note: str):
	"""A comment on the timeline (what was tried, who was called)."""
	if not (note or "").strip():
		frappe.throw(_("Write the note first."))
	doc = frappe.get_doc("Service Ticket", ticket)
	assert_property_access(doc.property)
	log_event(doc, "Note", note=note.strip())
	return ticket_detail(ticket)


@frappe.whitelist(methods=["POST"])
@require_roles(*OPS_ROLES)
def resolve_ticket(ticket: str, resolution_note: str | None = None, close: int = 0):
	"""Mark a ticket solved, recording who did it and what was done."""
	doc = frappe.get_doc("Service Ticket", ticket)
	assert_property_access(doc.property)
	if doc.status in DONE_STATES:
		frappe.throw(_("This ticket is already {0}.").format(_(doc.status)))
	doc.resolution_note = (resolution_note or "").strip()[:500] or doc.resolution_note
	doc.status = "Closed" if int(close or 0) else "Resolved"
	if not doc.resolved_on and doc.status == "Closed":
		doc.resolved_on = now_datetime()
		doc.resolved_by = frappe.session.user
	doc.save()
	return ticket_detail(ticket)


@frappe.whitelist(methods=["POST"])
@require_roles(*OPS_ROLES)
def reopen_ticket(ticket: str, reason: str):
	"""A solved ticket that came back. Needs a reason; it is kept in the timeline."""
	if len((reason or "").strip()) < 3:
		frappe.throw(_("Say why it is being reopened."))
	doc = frappe.get_doc("Service Ticket", ticket)
	assert_property_access(doc.property)
	if doc.status not in DONE_STATES:
		frappe.throw(_("This ticket is already open."))
	doc.status = "Open"
	doc.resolution_note = None
	doc.save()
	log_event(doc, "Note", note=f"Reopened: {reason.strip()}")
	return ticket_detail(ticket)
