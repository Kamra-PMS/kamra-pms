"""Housekeeping SLA escalation and completion alerts.

Every open task carries a due_by (set from its priority). This module runs
on a schedule: once a task is past due it escalates - first to the front
desk (the duty desk that is staffed around the clock), then, once it is a
full SLA late, to the property's Hotel Admins - and notifies over the
property's connected WhatsApp channel (falling back to the activity log when
no channel is wired). Completing a checkout clean for a room with an arrival
today pings the front desk that the room is ready.
"""

import frappe
from frappe.utils import get_datetime, now_datetime, time_diff_in_seconds

from kamra.authz import assert_property_access, require_roles
from kamra.kamra.doctype.housekeeping_task.housekeeping_task import sla_minutes

HK_SUPERVISOR = "Housekeeping Supervisor"

# escalation_level -> the role we notify at that level, and how the alert
# names them (the text must say who was actually told)
_ESCALATION_ROLE = {1: "Front Desk", 2: "Hotel Admin"}
_ESCALATION_WHO = {1: "the front desk", 2: "the hotel admin"}


def escalate_overdue_tasks():
	"""Scheduled: bump overdue tasks up the escalation ladder and alert."""
	now = now_datetime()
	tasks = frappe.get_all(
		"Housekeeping Task",
		filters={"status": ("in", ["Pending", "In Progress"]),
		         "due_by": ("<", now)},
		fields=["name", "property", "room", "task_type", "priority",
		        "due_by", "escalation_level"],
	)
	for t in tasks:
		overdue_min = time_diff_in_seconds(now, get_datetime(t.due_by)) / 60
		sla = sla_minutes(t.property, t.priority)
		# level 1 the moment it's overdue; level 2 once it's a full SLA late
		target = 2 if overdue_min >= sla else 1
		if target > (t.escalation_level or 0):
			_escalate(t, target, overdue_min)


def _escalate(task, level, overdue_min):
	frappe.db.set_value(
		"Housekeeping Task", task.name,
		{"escalation_level": level, "breached": 1}, update_modified=False)
	room = (task.room or "").split("-")[-1]
	who = _ESCALATION_WHO.get(level, "the hotel admin")
	body = (f"Housekeeping overdue: {task.task_type} in room {room} "
	        f"({task.priority}) is {int(overdue_min)} min past due - "
	        f"escalated to {who}.")
	_notify_role(task.property, _ESCALATION_ROLE.get(level, "Hotel Admin"), body)
	from kamra.savings import log_action
	log_action("hk_escalation", "Housekeeping Task", task.name, task.property,
	           rationale=body)


def notify_room_ready(task):
	"""Completion alert - only for the time-critical case: a checkout clean
	finished for a room with a guest arriving today."""
	if task.task_type != "Checkout Clean":
		return
	from frappe.utils import nowdate
	arriving = frappe.db.exists(
		"Reservation",
		{"room": task.room, "status": "Confirmed", "check_in_date": nowdate()})
	if not arriving:
		return
	room = (task.room or "").split("-")[-1]
	_notify_role(task.property, "Front Desk",
	             f"Room {room} is ready for today's arrival.")


def _notify_role(property, role, body):
	"""WhatsApp everyone holding `role` at this property (by their User
	mobile number). Staff limited to other properties are left out. Graceful:
	send_outbound logs and no-ops without a connected channel, so this never
	raises into the caller."""
	from kamra.agents_channels import send_outbound
	from kamra.authz import restricted_properties
	users = frappe.get_all(
		"Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent")
	if not users:
		return
	phones = frappe.get_all(
		"User", filters={"name": ("in", users), "enabled": 1},
		fields=["name", "mobile_no"])
	for p in phones:
		allowed = restricted_properties(p.name)  # None: not limited to any
		if p.mobile_no and (allowed is None or property in allowed):
			try:
				send_outbound(property, "WhatsApp", p.mobile_no, body)
			except Exception:
				pass  # notify every recipient independently; one failure must not stop the rest


# ── #560: room status cases, inspection pass rate and turn time ─────────────
# Both sit in the Housekeeping module and behind its settings
# (hk_discrepancy_cases, hk_quality_report): off, the endpoints refuse and
# the board hides them.

def _feature_on(property: str, key: str) -> bool:
	from frappe.utils import cint

	from kamra.settings import _enabled_modules, get_setting
	return "housekeeping" in _enabled_modules(property) and bool(cint(get_setting(property, key)))


def _require(property: str, key: str) -> None:
	from frappe import _
	if not _feature_on(property, key):
		frappe.throw(_("This is switched off in Settings, Housekeeping."))


def _wants(r: dict) -> tuple[str, str]:
	"""What each side says about the room, for a case's record."""
	return r["front_office"], f"{r['room_board']}, {r['housekeeping_status']}"


@frappe.whitelist()
@require_roles("Front Desk", "Housekeeping", HK_SUPERVISOR, "Hotel Admin", "Kamra Agent")
def room_discrepancies(property: str):
	"""Rooms where the front office and housekeeping disagree now (the night
	audit's room status check) that have no open case yet, and the open
	cases with their owner."""
	assert_property_access(property)
	if not _feature_on(property, "hk_discrepancy_cases"):
		return {"enabled": False, "detected": [], "cases": []}
	from kamra.night_audit import check_room_status
	cases = frappe.get_all(
		"Room Discrepancy", filters={"property": property, "status": "Open"},
		fields=["name", "room", "issue", "front_office", "housekeeping", "reservation",
		        "case_owner", "opened_by", "opened_on", "note"],
		order_by="opened_on asc")
	numbers = dict(frappe.get_all("Room", filters={"property": property},
	                              fields=["name", "room_number"], as_list=True))
	for c in cases:
		c["room_number"] = numbers.get(c.room, c.room)
	covered = {c.room for c in cases}
	detected = [r for r in check_room_status(property)["items"] if r["room_id"] not in covered]
	return {"enabled": True, "detected": detected, "cases": cases}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Housekeeping", HK_SUPERVISOR, "Hotel Admin")
def open_room_discrepancy(property: str, room: str, owner: str | None = None,
                          note: str = ""):
	"""Open a case for a room the front office and housekeeping disagree on,
	with an owner (default: whoever opens it). One open case per room."""
	from frappe import _
	from frappe.utils import now_datetime
	assert_property_access(property)
	_require(property, "hk_discrepancy_cases")
	if frappe.db.get_value("Room", room, "property") != property:
		frappe.throw(_("That room is not at this property."))
	if frappe.db.exists("Room Discrepancy", {"room": room, "status": "Open"}):
		frappe.throw(_("This room already has an open case."))
	from kamra.night_audit import check_room_status
	row = next((r for r in check_room_status(property)["items"] if r["room_id"] == room), None)
	if not row:
		frappe.throw(_("The front office and housekeeping agree on this room now."))
	fo, hk = _wants(row)
	doc = frappe.get_doc({
		"doctype": "Room Discrepancy", "property": property, "room": room,
		"issue": row["issue"], "front_office": fo, "housekeeping": hk,
		"reservation": row.get("reservation"), "status": "Open",
		"case_owner": owner or frappe.session.user, "opened_by": frappe.session.user,
		"opened_on": now_datetime(), "note": (note or "").strip()[:500] or None,
	})
	doc.flags.kamra_case = True
	doc.insert(ignore_permissions=True)
	from kamra.savings import log_action
	log_action("room_discrepancy_opened", "Room Discrepancy", doc.name, property,
	           rationale=f"Room {row['room']}: {row['issue']} (owner {doc.case_owner})")
	return {"case": doc.name, "owner": doc.case_owner}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Housekeeping", HK_SUPERVISOR, "Hotel Admin")
def close_room_discrepancy(case: str, reason: str):
	"""Close a room status case with what was found (the reason is required)."""
	from frappe import _
	from frappe.utils import now_datetime
	doc = frappe.get_doc("Room Discrepancy", case)
	assert_property_access(doc.property)
	if doc.status != "Open":
		frappe.throw(_("This case is already closed."))
	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("Say what was found - it closes the case on the record."))
	doc.update({"status": "Closed", "close_reason": reason[:500],
	            "closed_by": frappe.session.user, "closed_on": now_datetime()})
	doc.flags.kamra_case = True
	doc.save(ignore_permissions=True)
	from kamra.savings import log_action
	log_action("room_discrepancy_closed", "Room Discrepancy", doc.name, doc.property,
	           rationale=f"{doc.issue}: {reason}")
	return {"case": doc.name, "status": doc.status}


@frappe.whitelist(methods=["POST"])
@require_roles(HK_SUPERVISOR, "Hotel Admin")
def hk_fail_inspection(task: str, reason: str):
	"""A supervisor fails an inspection: the room goes back to Dirty and a
	re-clean is handed to the attendant whose clean failed. The reason is
	kept; it counts against that attendant's pass rate."""
	from frappe import _
	doc = frappe.get_doc("Housekeeping Task", task)
	assert_property_access(doc.property)
	if doc.task_type != "Inspection" or doc.status in ("Done", "Verified"):
		frappe.throw(_("Only an open inspection can be failed."))
	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("Say what failed - the attendant sees it on the re-clean."))
	doc.inspection_result = "Failed"
	doc.fail_reason = reason[:500]
	doc.status = "Done"  # closes the inspection; the room stays out of Ready
	doc.save(ignore_permissions=True)
	frappe.db.set_value("Room", doc.room, "housekeeping_status", "Dirty")
	attendant = (frappe.db.get_value("Housekeeping Task", doc.clean_task, "assigned_to_user")
	             if doc.clean_task else None)
	reclean = frappe.get_doc({
		"doctype": "Housekeeping Task", "property": doc.property, "room": doc.room,
		"task_type": "Checkout Clean", "priority": "High", "status": "Pending",
		"reservation": doc.reservation, "assigned_to_user": attendant,
		"assignment_status": "Assigned" if attendant else "Unassigned",
		"notes": _("Re-clean: inspection failed - {0}").format(reason)[:500],
	}).insert(ignore_permissions=True)
	from kamra.savings import log_action
	log_action("hk_inspection_failed", "Housekeeping Task", doc.name, doc.property,
	           rationale=f"{doc.room}: {reason}")
	return {"ok": True, "task": doc.name, "reclean": reclean.name}


def _minutes(a, b) -> float:
	return round(time_diff_in_seconds(get_datetime(b), get_datetime(a)) / 60, 1)


@frappe.whitelist()
@require_roles(HK_SUPERVISOR, "Hotel Admin", "Kamra Agent")
def hk_quality(property: str, from_date: str | None = None, to_date: str | None = None):
	"""Inspection pass rate and checkout-clean turn time (task made to task
	done, in minutes) by attendant and by room type, over inspections and
	cleans completed between the dates (default: the last 30 days)."""
	from frappe.utils import add_days, getdate, nowdate
	assert_property_access(property)
	if not _feature_on(property, "hk_quality_report"):
		return {"enabled": False}
	to_date = str(getdate(to_date or nowdate()))
	from_date = str(getdate(from_date or add_days(to_date, -30)))
	if (getdate(to_date) - getdate(from_date)).days > 366:
		frappe.throw("Pick at most a year.")
	window = ("between", (f"{from_date} 00:00:00", f"{to_date} 23:59:59"))
	room_types = dict(frappe.get_all("Room", filters={"property": property},
	                                 fields=["name", "room_type"], as_list=True))
	cleans = {t.name: t for t in frappe.get_all(
		"Housekeeping Task",
		filters={"property": property, "task_type": ("!=", "Inspection"),
		         "status": ("in", ("Done", "Verified"))},
		fields=["name", "room", "task_type", "assigned_to_user", "creation", "completed_on"],
		limit_page_length=0)}
	inspections = frappe.get_all(
		"Housekeeping Task",
		filters={"property": property, "task_type": "Inspection",
		         "inspection_result": ("in", ("Passed", "Failed")), "completed_on": window},
		fields=["room", "clean_task", "inspection_result"], limit_page_length=0)
	rows: dict[tuple, dict] = {}

	def row(kind, key):
		return rows.setdefault((kind, key), {"inspected": 0, "passed": 0, "turns": []})

	for i in inspections:
		clean = cleans.get(i.clean_task) or {}
		for kind, key in (("attendant", clean.get("assigned_to_user") or ""),
		                  ("room_type", room_types.get(i.room) or "")):
			r = row(kind, key)
			r["inspected"] += 1
			r["passed"] += i.inspection_result == "Passed"
	for c in cleans.values():
		if c.task_type != "Checkout Clean" or not c.completed_on \
				or not (from_date <= str(getdate(c.completed_on)) <= to_date):
			continue
		turn = _minutes(c.creation, c.completed_on)
		for kind, key in (("attendant", c.assigned_to_user or ""),
		                  ("room_type", room_types.get(c.room) or "")):
			row(kind, key)["turns"].append(turn)
	names = dict(frappe.get_all("User", filters={"name": ("in", [k for (kind, k) in rows
	                                                              if kind == "attendant" and k] or [""])},
	                            fields=["name", "full_name"], as_list=True))
	out = {"attendant": [], "room_type": []}
	for (kind, key), r in sorted(rows.items(), key=lambda x: (x[0][0], x[0][1])):
		turns = r["turns"]
		out[kind].append({
			"key": key or None,
			"label": (names.get(key) or key) if kind == "attendant" else key,
			"inspected": r["inspected"], "passed": r["passed"],
			"pass_rate": round(100 * r["passed"] / r["inspected"], 1) if r["inspected"] else None,
			"cleans": len(turns),
			"avg_turn_minutes": round(sum(turns) / len(turns), 1) if turns else None,
		})
	return {"enabled": True, "from_date": from_date, "to_date": to_date, **out}
