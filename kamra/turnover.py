# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Turnover readiness helpers (ADR-010 / Phase 2B)."""

from __future__ import annotations

import frappe
from frappe.utils import add_to_date, now_datetime


def get_turnover_profile(property: str) -> dict | None:
	if not frappe.db.exists("DocType", "Turnover Profile"):
		return None
	name = frappe.db.get_value(
		"Turnover Profile",
		{"property": property, "is_default": 1},
		"name",
	)
	if not name:
		name = frappe.db.get_value(
			"Turnover Profile", {"property": property}, "name"
		)
	if not name:
		return None
	return frappe.get_cached_doc("Turnover Profile", name).as_dict()


def ensure_default_profile(property: str, *, str_defaults: bool = False) -> str | None:
	"""Create a default Turnover Profile for a property if missing."""
	if not frappe.db.exists("DocType", "Turnover Profile"):
		return None
	existing = frappe.db.get_value(
		"Turnover Profile", {"property": property, "is_default": 1}, "name"
	)
	if existing:
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "Turnover Profile",
			"property": property,
			"profile_name": "Default",
			"is_default": 1,
			"clean_duration_minutes": 120,
			"inspect_duration_minutes": 30,
			"buffer_after_ready_minutes": 0,
			"same_day_turn_allowed": 0 if str_defaults else 1,
			"requires_inspection": 1 if str_defaults else 0,
			"ready_marked_by": "Housekeeping",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def on_checkout_clean_done(task) -> None:
	"""After Checkout Clean Done: spawn Inspection when profile requires it."""
	if not task.room or task.task_type != "Checkout Clean":
		return
	profile = get_turnover_profile(task.property) or {}
	if not profile.get("requires_inspection"):
		return
	# Avoid duplicate open inspections for the same reservation/room.
	open_insp = frappe.db.exists(
		"Housekeeping Task",
		{
			"room": task.room,
			"task_type": "Inspection",
			"status": ("in", ["Pending", "In Progress"]),
			"reservation": task.reservation,
		},
	)
	if open_insp:
		return
	mins = int(profile.get("inspect_duration_minutes") or 30)
	frappe.get_doc(
		{
			"doctype": "Housekeeping Task",
			"property": task.property,
			"room": task.room,
			"task_type": "Inspection",
			"priority": "High",
			"status": "Pending",
			"reservation": task.reservation,
			"due_by": add_to_date(now_datetime(), minutes=mins),
		}
	).insert(ignore_permissions=True)


def mark_room_ready(room: str) -> None:
	frappe.db.set_value("Room", room, "housekeeping_status", "Ready")


def room_is_ready(room: str) -> bool:
	status = frappe.db.get_value("Room", room, "housekeeping_status")
	return status in ("Ready", "Clean", "Inspected")
