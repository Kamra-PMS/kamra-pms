"""Housekeeping SLA escalation and completion alerts.

Every open task carries a due_by (set from its priority). This module runs
on a schedule: once a task is past due it escalates - first to the shift
supervisor, then, if it stays open, to the manager - and notifies over the
property's connected WhatsApp channel (falling back to the activity log when
no channel is wired). Completing a checkout clean for a room with an arrival
today pings the front desk that the room is ready.
"""

import frappe
from frappe.utils import get_datetime, now_datetime, time_diff_in_seconds

from kamra.kamra.doctype.housekeeping_task.housekeeping_task import HK_SLA_MINUTES

# escalation_level -> the role we notify at that level
_ESCALATION_ROLE = {1: "Front Desk", 2: "Hotel Admin"}


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
		sla = HK_SLA_MINUTES.get(t.priority, 90)
		# level 1 the moment it's overdue; level 2 once it's a full SLA late
		target = 2 if overdue_min >= sla else 1
		if target > (t.escalation_level or 0):
			_escalate(t, target, overdue_min)


def _escalate(task, level, overdue_min):
	frappe.db.set_value(
		"Housekeeping Task", task.name,
		{"escalation_level": level, "breached": 1}, update_modified=False)
	room = (task.room or "").split("-")[-1]
	who = "supervisor" if level == 1 else "manager"
	body = (f"Housekeeping overdue: {task.task_type} in room {room} "
	        f"({task.priority}) is {int(overdue_min)} min past due - "
	        f"escalated to the {who}.")
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
	mobile number). Graceful: send_outbound logs and no-ops without a
	connected channel, so this never raises into the caller."""
	from kamra.agents_channels import send_outbound
	users = frappe.get_all(
		"Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent")
	if not users:
		return
	phones = frappe.get_all(
		"User", filters={"name": ("in", users), "enabled": 1},
		fields=["mobile_no"])
	for p in phones:
		if p.mobile_no:
			try:
				send_outbound(property, "WhatsApp", p.mobile_no, body)
			except Exception:
				pass
