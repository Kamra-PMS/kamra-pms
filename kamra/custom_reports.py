"""Custom report builder — save, run, export, and email.

Staff pick a whitelisted dataset, columns and filters in the SPA (or via
Agent/MCP). Definitions live on Kamra Custom Report. No Desk Query Reports,
no free SQL from the client.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Any, Callable

import frappe
from frappe import _
from frappe.utils import add_days, date_diff, getdate, now_datetime, nowdate

from kamra.authz import require_roles
from kamra.crs import assert_property_access

MAX_RANGE_DAYS = 92
MAX_ROWS = 5000

# Roles that may create / edit / schedule reports (plus the document owner
# for their own private reports).
EDIT_ROLES = ("Finance", "Hotel Admin", "System Manager", "Administrator")

# ---------------------------------------------------------------------------
# Dataset catalog
# ---------------------------------------------------------------------------

Column = dict[str, Any]
Dataset = dict[str, Any]


def _col(id: str, label: str, typ: str = "string") -> Column:
	return {"id": id, "label": label, "type": typ}


HK_ROLES = ("Housekeeping", "Housekeeping Supervisor", "Front Desk",
            "Hotel Admin", "Kamra Agent")

DATASETS: dict[str, Dataset] = {
	"arrivals": {
		"id": "arrivals",
		"label": "Arrivals",
		"description": "Confirmed and checked-in arrivals by check-in date.",
		"module": "front-desk",
		"roles": ("Front Desk", "Finance", "Hotel Admin", "Revenue Manager",
		          "Kamra Agent", "Night Auditor"),
		"date_field": "check_in_date",
		"needs_range": True,
		"columns": [
			_col("name", "Reservation"),
			_col("guest_name", "Guest"),
			_col("room_type", "Room type"),
			_col("room", "Room"),
			_col("status", "Status"),
			_col("source", "Source"),
			_col("channel", "Channel"),
			_col("check_in_date", "Check-in", "date"),
			_col("check_out_date", "Check-out", "date"),
			_col("nights", "Nights", "number"),
			_col("adults", "Adults", "number"),
			_col("children", "Children", "number"),
			_col("company", "Company"),
			_col("eta", "ETA"),
		],
	},
	"departures": {
		"id": "departures",
		"label": "Departures",
		"description": "Checked-in and checked-out departures by check-out date.",
		"module": "front-desk",
		"roles": ("Front Desk", "Finance", "Hotel Admin", "Revenue Manager",
		          "Kamra Agent", "Night Auditor"),
		"date_field": "check_out_date",
		"needs_range": True,
		"columns": [
			_col("name", "Reservation"),
			_col("guest_name", "Guest"),
			_col("room_type", "Room type"),
			_col("room", "Room"),
			_col("status", "Status"),
			_col("check_in_date", "Check-in", "date"),
			_col("check_out_date", "Check-out", "date"),
			_col("nights", "Nights", "number"),
			_col("company", "Company"),
		],
	},
	"in_house": {
		"id": "in_house",
		"label": "In-house guests",
		"description": "Guests currently checked in (as of to-date).",
		"module": "front-desk",
		"roles": ("Front Desk", "Finance", "Hotel Admin", "Revenue Manager",
		          "Kamra Agent", "Night Auditor"),
		"date_field": None,
		"needs_range": False,
		"columns": [
			_col("name", "Reservation"),
			_col("guest_name", "Guest"),
			_col("room_type", "Room type"),
			_col("room", "Room"),
			_col("check_in_date", "Check-in", "date"),
			_col("check_out_date", "Check-out", "date"),
			_col("nights", "Nights", "number"),
			_col("adults", "Adults", "number"),
			_col("children", "Children", "number"),
			_col("company", "Company"),
			_col("source", "Source"),
		],
	},
	"no_shows_cancels": {
		"id": "no_shows_cancels",
		"label": "No-shows & cancellations",
		"description": "No-shows and cancelled stays by check-in date.",
		"module": "front-desk",
		"roles": ("Front Desk", "Finance", "Hotel Admin", "Revenue Manager",
		          "Kamra Agent", "Night Auditor"),
		"date_field": "check_in_date",
		"needs_range": True,
		"columns": [
			_col("name", "Reservation"),
			_col("guest_name", "Guest"),
			_col("room_type", "Room type"),
			_col("status", "Status"),
			_col("source", "Source"),
			_col("check_in_date", "Check-in", "date"),
			_col("check_out_date", "Check-out", "date"),
			_col("company", "Company"),
		],
	},
	"occupancy_by_day": {
		"id": "occupancy_by_day",
		"label": "Occupancy & revenue by day",
		"description": "Rooms sold, occupancy, ADR, RevPAR and revenue per day.",
		"module": "finance",
		"roles": ("Finance", "Hotel Admin", "Revenue Manager", "Kamra Agent", "Front Desk", "Night Auditor"),
		"date_field": "date",
		"needs_range": True,
		"columns": [
			_col("date", "Date", "date"),
			_col("rooms_sold", "Rooms sold", "number"),
			_col("occupancy_pct", "Occ %", "number"),
			_col("adr", "ADR", "number"),
			_col("revpar", "RevPAR", "number"),
			_col("revpax", "RevPAX", "number"),
			_col("room_revenue", "Room revenue", "number"),
			_col("fnb_revenue", "F&B revenue", "number"),
			_col("other_revenue", "Other revenue", "number"),
			_col("total_revenue", "Total revenue", "number"),
			_col("pax", "Pax", "number"),
		],
	},
	"folio_charges": {
		"id": "folio_charges",
		"label": "Folio charges",
		"description": "Posted folio charge lines by posting date.",
		"module": "finance",
		"roles": ("Finance", "Hotel Admin", "Kamra Agent", "Night Auditor"),
		"date_field": "posting_date",
		"needs_range": True,
		"columns": [
			_col("posting_date", "Date", "date"),
			_col("folio", "Folio"),
			_col("reservation", "Reservation"),
			_col("guest_name", "Guest"),
			_col("charge_type", "Type"),
			_col("description", "Description"),
			_col("amount", "Amount", "number"),
		],
	},
	"payments": {
		"id": "payments",
		"label": "Payments",
		"description": "Folio payments by payment date.",
		"module": "finance",
		"roles": ("Finance", "Hotel Admin", "Kamra Agent", "Night Auditor"),
		"date_field": "posting_date",
		"needs_range": True,
		"columns": [
			_col("posting_date", "Date", "date"),
			_col("folio", "Folio"),
			_col("reservation", "Reservation"),
			_col("guest_name", "Guest"),
			_col("mode", "Mode"),
			_col("amount", "Amount", "number"),
			_col("reference", "Reference"),
		],
	},
	"voids": {
		"id": "voids",
		"label": "Voids & allowances",
		"description": "Voids, allowances and cancelled invoices.",
		"module": "finance",
		"roles": ("Finance", "Hotel Admin", "System Manager", "Administrator"),
		"date_field": "when",
		"needs_range": True,
		"columns": [
			_col("when", "When"),
			_col("actor", "Actor"),
			_col("action", "Action"),
			_col("folio", "Folio"),
			_col("pos_order", "POS order"),
			_col("approver", "Approver"),
			_col("detail", "Detail"),
		],
	},
	"contribution": {
		"id": "contribution",
		"label": "Contribution by source",
		"description": "Bookings, room nights and revenue by booking source.",
		"module": "revenue",
		"roles": ("Finance", "Revenue Manager", "Hotel Admin", "Kamra Agent"),
		"date_field": None,
		"needs_range": True,
		"columns": [
			_col("label", "Source"),
			_col("bookings", "Bookings", "number"),
			_col("room_nights", "Room nights", "number"),
			_col("revenue", "Revenue", "number"),
			_col("commission", "Commission", "number"),
			_col("share", "Share %", "number"),
		],
	},
	"hk_tasks": {
		"id": "hk_tasks",
		"label": "Housekeeping tasks",
		"description": "Housekeeping tasks created in the date range.",
		"module": "housekeeping",
		"roles": HK_ROLES,
		"date_field": "creation",
		"needs_range": True,
		"averages": ("clean_minutes",),
		"columns": [
			_col("name", "Task"),
			_col("room", "Room"),
			_col("task_type", "Type"),
			_col("priority", "Priority"),
			_col("status", "Status"),
			_col("assigned_to_user", "Assigned to"),
			_col("due_by", "Due by"),
			_col("breached", "Breached", "number"),
			_col("tasks", "Tasks", "number"),
			_col("clean_minutes", "Clean minutes", "number"),
			_col("creation", "Created"),
		],
	},
	"room_status": {
		"id": "room_status",
		"label": "Room status",
		"description": "Every room's housekeeping and occupancy status right now.",
		"module": "housekeeping",
		"roles": HK_ROLES,
		"needs_range": False,
		"columns": [
			_col("room", "Room"),
			_col("room_type", "Room type"),
			_col("floor", "Floor"),
			_col("housekeeping_status", "HK status"),
			_col("occupancy_status", "Occupancy"),
			_col("rooms", "Rooms", "number"),
		],
	},
	"lost_found": {
		"id": "lost_found",
		"label": "Lost and found",
		"description": "Items logged as found, missing or damaged, by date found.",
		"module": "housekeeping",
		"roles": HK_ROLES,
		"date_field": "found_on",
		"needs_range": True,
		"columns": [
			_col("name", "Item"),
			_col("found_on", "Found on", "date"),
			_col("item_description", "Description"),
			_col("condition", "Condition"),
			_col("found_in_room", "Room"),
			_col("found_by", "Found by"),
			_col("status", "Status"),
			_col("guest", "Guest"),
			_col("returned_on", "Returned on", "date"),
			_col("items", "Items", "number"),
		],
	},
	"pos_orders": {
		"id": "pos_orders",
		"label": "POS orders",
		"description": "Restaurant / outlet orders by creation date.",
		"module": "fnb",
		"roles": ("Finance", "Hotel Admin", "Kamra Agent", "Front Desk"),
		"date_field": "creation",
		"needs_range": True,
		"columns": [
			_col("name", "Order"),
			_col("outlet", "Outlet"),
			_col("posting_date", "Date", "date"),
			_col("status", "Status"),
			_col("guest_name", "Guest"),
			_col("room", "Room"),
			_col("covers", "Covers", "number"),
			_col("grand_total", "Total", "number"),
		],
	},
	"pos_items": {
		"id": "pos_items",
		"label": "POS items",
		"description": "Sold menu items by order date (voids excluded).",
		"module": "fnb",
		"roles": ("Finance", "Hotel Admin", "Kamra Agent", "Front Desk"),
		"date_field": "creation",
		"needs_range": True,
		"columns": [
			_col("item_name", "Item"),
			_col("outlet", "Outlet"),
			_col("posting_date", "Date", "date"),
			_col("qty", "Qty", "number"),
			_col("rate", "Rate", "number"),
			_col("amount", "Amount", "number"),
			_col("order", "Order"),
		],
	},
	"service_tickets": {
		"id": "service_tickets",
		"label": "Service tickets",
		"description": "Guest and maintenance tickets created in the date range.",
		"module": "operations",
		"roles": ("Front Desk", "Housekeeping", "Housekeeping Supervisor",
		          "Hotel Admin", "Kamra Agent", "Finance"),
		"date_field": "creation",
		"needs_range": True,
		"averages": ("resolution_minutes", "response_minutes"),
		"columns": [
			_col("name", "Ticket"),
			_col("subject", "Subject"),
			_col("category", "Category"),
			_col("priority", "Priority"),
			_col("status", "Status"),
			_col("source", "Source"),
			_col("room", "Room"),
			_col("guest_name", "Guest"),
			_col("assigned_to_user", "Assigned to"),
			_col("breached", "Breached", "number"),
			_col("tickets", "Tickets", "number"),
			_col("resolution_minutes", "Resolution minutes", "number"),
			_col("response_minutes", "Response minutes", "number"),
			_col("creation", "Created"),
			_col("due_by", "Due by"),
			_col("resolved_on", "Resolved on"),
		],
	},
	"laundry_orders": {
		"id": "laundry_orders",
		"label": "Laundry orders",
		"description": "Laundry line items by order date, with turnaround.",
		"module": "housekeeping",
		"roles": HK_ROLES,
		"date_field": "creation",
		"needs_range": True,
		"averages": ("turnaround_hours",),
		"columns": [
			_col("name", "Order"),
			_col("order_type", "Order type"),
			_col("room", "Room"),
			_col("status", "Status"),
			_col("express", "Express", "number"),
			_col("item_name", "Item"),
			_col("service_type", "Service"),
			_col("qty", "Qty", "number"),
			_col("returned_qty", "Returned", "number"),
			_col("amount", "Amount", "number"),
			_col("turnaround_hours", "Turnaround hours", "number"),
			_col("collected_at", "Collected at"),
			_col("delivered_at", "Delivered at"),
			_col("creation", "Created"),
		],
	},
	"shift_handover": {
		"id": "shift_handover",
		"label": "Shift handover",
		"description": "Cashier shift handovers by shift date.",
		"module": "front-desk",
		"roles": ("Front Desk", "Finance", "Hotel Admin", "Kamra Agent",
		          "Night Auditor"),
		"date_field": "shift_date",
		"needs_range": True,
		"columns": [
			_col("name", "Handover"),
			_col("shift_date", "Shift date", "date"),
			_col("shift", "Shift"),
			_col("status", "Status"),
			_col("handed_over_to", "Handed over to"),
			_col("opening_cash", "Opening cash", "number"),
			_col("cash_collected", "Cash collected", "number"),
			_col("payouts", "Payouts", "number"),
			_col("closing_cash", "Closing cash", "number"),
			_col("handover_notes", "Handover notes"),
		],
	},
	"early_departures": {
		"id": "early_departures",
		"label": "Early departures",
		"description": "Guests who checked out before their scheduled departure.",
		"module": "front-desk",
		"roles": ("Front Desk", "Finance", "Hotel Admin", "Revenue Manager",
		          "Kamra Agent", "Night Auditor"),
		"date_field": "actual_check_out",
		"needs_range": True,
		"columns": [
			_col("name", "Reservation"),
			_col("guest_name", "Guest"),
			_col("room_type", "Room type"),
			_col("room", "Room"),
			_col("check_in_date", "Check-in", "date"),
			_col("check_out_date", "Scheduled check-out", "date"),
			_col("actual_check_out", "Actual check-out"),
			_col("nights_short", "Nights short", "number"),
			_col("company", "Company"),
			_col("source", "Source"),
		],
	},
	"overdue_by_company": {
		"id": "overdue_by_company",
		"label": "Overdue by company",
		"description": "Companies with city ledger bills past their due date, aged by days overdue.",
		"module": "finance",
		"roles": ("Finance", "Hotel Admin", "Kamra Agent"),
		"needs_range": False,
		"columns": [
			_col("company", "Company"),
			_col("credit_days", "Terms (days)", "number"),
			_col("balance", "Balance", "number"),
			_col("not_due", "Not due", "number"),
			_col("d1_30", "1 to 30", "number"),
			_col("d31_60", "31 to 60", "number"),
			_col("d61_90", "61 to 90", "number"),
			_col("d90p", "90+", "number"),
			_col("overdue", "Overdue", "number"),
			_col("oldest_overdue_due_date", "Oldest due date", "date"),
		],
	},
	"dso": {
		"id": "dso",
		"label": "Days sales outstanding (DSO)",
		"description": "Per company: city ledger billed and paid in the period, the balance at its end, "
		               "and DSO = closing balance / billed x days. The last row is all companies.",
		"module": "finance",
		"roles": ("Finance", "Hotel Admin", "Kamra Agent"),
		"needs_range": True,
		"columns": [
			_col("company", "Company"),
			_col("billed", "Billed", "number"),
			_col("paid", "Paid", "number"),
			_col("closing_balance", "Closing balance", "number"),
			_col("dso", "DSO (days)", "number"),
		],
	},
}


# Department packs: several grouped datasets in one report, emailed weekly.
# A section the user's roles (or the property's modules) can't run is left
# out, so each person gets the part of the pack their access allows.
# Packs compare this period to the previous window of the same length (#346).
PACK_PREFIX = "pack:"
PACKS: dict[str, dict] = {
	"front_office": {
		"label": "Front Office pack",
		"description": "Occupancy by day, arrivals by source, in-house by room "
		               "type, no-shows, early departures and shift handovers.",
		"sections": [
			{"title": "Occupancy by day", "dataset": "occupancy_by_day",
			 "columns": ["date", "rooms_sold", "occupancy_pct", "adr", "revpar",
			             "room_revenue", "total_revenue"]},
			{"title": "Arrivals by source", "dataset": "arrivals",
			 "columns": ["source", "nights", "adults", "children"], "group_by": ["source"]},
			{"title": "In house by room type", "dataset": "in_house",
			 "columns": ["room_type", "nights", "adults", "children"],
			 "group_by": ["room_type"]},
			{"title": "No-shows and cancellations", "dataset": "no_shows_cancels"},
			{"title": "Early departures", "dataset": "early_departures"},
			{"title": "Shift handovers", "dataset": "shift_handover"},
		],
	},
	"housekeeping": {
		"label": "Housekeeping pack",
		"description": "Room status now, cleans by type and by attendant with "
		               "average minutes, and lost and found.",
		"sections": [
			{"title": "Room status", "dataset": "room_status",
			 "columns": ["housekeeping_status", "rooms"],
			 "group_by": ["housekeeping_status"]},
			{"title": "Tasks by type", "dataset": "hk_tasks",
			 "columns": ["task_type", "tasks", "breached", "clean_minutes"],
			 "group_by": ["task_type"]},
			{"title": "Tasks by attendant", "dataset": "hk_tasks",
			 "columns": ["assigned_to_user", "tasks", "breached", "clean_minutes"],
			 "group_by": ["assigned_to_user"]},
			{"title": "Lost and found", "dataset": "lost_found",
			 "columns": ["found_on", "item_description", "found_in_room",
			             "status", "returned_on"]},
		],
	},
	"fnb": {
		"label": "F&B pack",
		"description": "Sales and covers by outlet, orders by status, and "
		               "items sold by menu name.",
		"sections": [
			{"title": "Sales by outlet", "dataset": "pos_orders",
			 "columns": ["outlet", "covers", "grand_total"], "group_by": ["outlet"]},
			{"title": "Orders by status", "dataset": "pos_orders",
			 "columns": ["status", "covers", "grand_total"], "group_by": ["status"]},
			{"title": "Items by menu", "dataset": "pos_items",
			 "columns": ["item_name", "qty", "amount"], "group_by": ["item_name"]},
		],
	},
	"engineering": {
		"label": "Engineering pack",
		"description": "Tickets by category and priority, open work, SLA "
		               "breaches and average resolution time.",
		"sections": [
			{"title": "Tickets by category", "dataset": "service_tickets",
			 "columns": ["category", "tickets", "breached", "resolution_minutes"],
			 "group_by": ["category"]},
			{"title": "Tickets by priority", "dataset": "service_tickets",
			 "columns": ["priority", "tickets", "breached", "resolution_minutes"],
			 "group_by": ["priority"]},
			{"title": "Open tickets", "dataset": "service_tickets",
			 "columns": ["name", "subject", "category", "priority", "status",
			             "room", "due_by", "breached"],
			 "filters": [{"field": "status", "op": "=", "value": "Open"}]},
			{"title": "SLA breaches", "dataset": "service_tickets",
			 "columns": ["name", "subject", "category", "priority", "status",
			             "room", "due_by", "resolved_on"],
			 "filters": [{"field": "breached", "op": "=", "value": 1}]},
		],
	},
	"laundry": {
		"label": "Laundry pack",
		"description": "Volume by guest vs house, by item and status, with "
		               "turnaround hours.",
		"sections": [
			{"title": "Volume by guest vs house", "dataset": "laundry_orders",
			 "columns": ["order_type", "qty", "amount"], "group_by": ["order_type"]},
			{"title": "By item", "dataset": "laundry_orders",
			 "columns": ["item_name", "qty", "amount"], "group_by": ["item_name"]},
			{"title": "By status", "dataset": "laundry_orders",
			 "columns": ["status", "qty", "amount"], "group_by": ["status"]},
			{"title": "Turnaround", "dataset": "laundry_orders",
			 "columns": ["name", "order_type", "status", "turnaround_hours", "qty"],
			 "group_by": ["name"]},
		],
	},
	"hotel_manager": {
		"label": "Hotel Manager pack",
		"description": "Occupancy and revenue by day, revenue by source, "
		               "collections by mode, charges by type, voids.",
		"sections": [
			{"title": "Occupancy and revenue", "dataset": "occupancy_by_day"},
			{"title": "Revenue by source", "dataset": "contribution"},
			{"title": "Collections by mode", "dataset": "payments",
			 "columns": ["mode", "amount"], "group_by": ["mode"]},
			{"title": "Charges by type", "dataset": "folio_charges",
			 "columns": ["charge_type", "amount"], "group_by": ["charge_type"]},
			{"title": "Voids and allowances", "dataset": "voids"},
		],
	},
}


def _pack_sections(property: str, pack_id: str) -> list[dict]:
	"""The sections of a pack this user may run on this property."""
	return [s for s in PACKS[pack_id]["sections"]
	        if _dataset_allowed(DATASETS[s["dataset"]])
	        and _module_enabled(property, DATASETS[s["dataset"]].get("module"))]


def _pack_id(dataset: str | None) -> str | None:
	if dataset and dataset.startswith(PACK_PREFIX):
		pid = dataset[len(PACK_PREFIX):]
		if pid not in PACKS:
			frappe.throw(_("Unknown report pack: {0}").format(pid))
		return pid
	return None


def _user_roles() -> set[str]:
	return set(frappe.get_roles())


def _can_edit() -> bool:
	return bool(_user_roles() & set(EDIT_ROLES))


def _dataset_allowed(ds: Dataset) -> bool:
	roles = set(ds["roles"])
	if not (_user_roles() & roles):
		return False
	# module gate when the property has enabled_modules set
	return True


def _module_enabled(property: str, module: str | None) -> bool:
	from kamra.api import enabled_modules

	return not module or module in enabled_modules(property)


def _parse_json(raw: Any, default: Any):
	if raw is None or raw == "":
		return default
	if isinstance(raw, (list, dict)):
		return raw
	try:
		return json.loads(raw)
	except (TypeError, ValueError):
		return default


def _guard_range(from_date: str | None, to_date: str | None, needs_range: bool):
	if not needs_range:
		return from_date or nowdate(), to_date or nowdate()
	if not from_date or not to_date:
		frappe.throw(_("From date and to date are required."))
	f, t = getdate(from_date), getdate(to_date)
	if t < f:
		frappe.throw(_("To date must be on or after from date."))
	if (t - f).days > MAX_RANGE_DAYS:
		frappe.throw(_("Date range cannot exceed {0} days.").format(MAX_RANGE_DAYS))
	return str(f), str(t)


# ---------------------------------------------------------------------------
# Fetchers
# ---------------------------------------------------------------------------

def _fetch_reservations(property: str, from_date: str, to_date: str,
                        date_field: str, statuses: list[str]) -> list[dict]:
	fields = [
		"name", "guest_name", "room_type", "room", "status", "source",
		"channel", "check_in_date", "check_out_date", "nights", "adults",
		"children", "company", "eta",
	]
	return frappe.get_all(
		"Reservation",
		filters={
			"property": property,
			date_field: ["between", [from_date, to_date]],
			"status": ["in", statuses],
		},
		fields=fields,
		order_by=f"{date_field} asc, creation asc",
		limit_page_length=MAX_ROWS,
	)


def _fetch_arrivals(property: str, from_date: str, to_date: str, **_) -> list[dict]:
	return _fetch_reservations(
		property, from_date, to_date, "check_in_date",
		["Confirmed", "Checked In"])


def _fetch_departures(property: str, from_date: str, to_date: str, **_) -> list[dict]:
	return _fetch_reservations(
		property, from_date, to_date, "check_out_date",
		["Checked In", "Checked Out"])


def _fetch_in_house(property: str, from_date: str, to_date: str, **_) -> list[dict]:
	# as-of to_date: checked in on or before, checking out after
	fields = [
		"name", "guest_name", "room_type", "room", "status", "source",
		"check_in_date", "check_out_date", "nights", "adults", "children",
		"company",
	]
	return frappe.get_all(
		"Reservation",
		filters={
			"property": property,
			"status": "Checked In",
			"check_in_date": ["<=", to_date],
			"check_out_date": [">", to_date],
		},
		fields=fields,
		order_by="room asc",
		limit_page_length=MAX_ROWS,
	)


def _fetch_no_shows_cancels(property: str, from_date: str, to_date: str,
                            **_) -> list[dict]:
	return _fetch_reservations(
		property, from_date, to_date, "check_in_date",
		["No Show", "Cancelled"])


def _fetch_occupancy_by_day(property: str, from_date: str, to_date: str,
                            **_) -> list[dict]:
	from kamra.reports import _day_stats

	total_rooms = frappe.db.count("Room", {"property": property}) or 0
	rows = []
	d = getdate(from_date)
	end = getdate(to_date)
	while d <= end and len(rows) < MAX_ROWS:
		rows.append(_day_stats(property, str(d), total_rooms))
		d = getdate(add_days(d, 1))
	return rows


def _fetch_folio_charges(property: str, from_date: str, to_date: str,
                         **_) -> list[dict]:
	return frappe.db.sql(
		"""
		SELECT fc.posting_date, f.name AS folio,
		       COALESCE(fc.reservation, f.reservation) AS reservation,
		       f.guest_name, fc.charge_type, fc.description, fc.amount
		FROM `tabFolio Charge` fc
		JOIN `tabFolio` f ON fc.parent = f.name
		WHERE f.property = %(p)s
		  AND fc.posting_date BETWEEN %(f)s AND %(t)s
		ORDER BY fc.posting_date, f.name
		LIMIT %(lim)s
		""",
		{"p": property, "f": from_date, "t": to_date, "lim": MAX_ROWS},
		as_dict=True,
	)


def _fetch_payments(property: str, from_date: str, to_date: str,
                    **_) -> list[dict]:
	return frappe.db.sql(
		"""
		SELECT DATE(fp.posting_date) AS posting_date, f.name AS folio,
		       f.reservation, f.guest_name, fp.mode, fp.amount, fp.reference
		FROM `tabFolio Payment` fp
		JOIN `tabFolio` f ON fp.parent = f.name
		WHERE f.property = %(p)s
		  AND DATE(fp.posting_date) BETWEEN %(f)s AND %(t)s
		ORDER BY fp.posting_date, f.name
		LIMIT %(lim)s
		""",
		{"p": property, "f": from_date, "t": to_date, "lim": MAX_ROWS},
		as_dict=True,
	)


def _fetch_voids(property: str, from_date: str, to_date: str, **_) -> list[dict]:
	from kamra.reports import void_allowance_report

	return void_allowance_report(property, from_date, to_date)


def _fetch_contribution(property: str, from_date: str, to_date: str,
                        **_) -> list[dict]:
	from kamra.reports import contribution

	return contribution(property, from_date, to_date, by="source").get("rows") or []


def _fetch_hk_tasks(property: str, from_date: str, to_date: str,
                    **_) -> list[dict]:
	rows = frappe.get_all(
		"Housekeeping Task",
		filters={
			"property": property,
			"creation": ["between", [from_date, f"{to_date} 23:59:59"]],
		},
		fields=[
			"name", "room", "task_type", "priority", "status",
			"assigned_to_user", "due_by", "breached", "creation",
		],
		order_by="creation desc",
		limit_page_length=MAX_ROWS,
	)
	from kamra.rooms import _minutes, _task_timeline

	timeline = _task_timeline([r.name for r in rows if r.status in ("Done", "Verified")
	                           and r.task_type != "Inspection"])
	for r in rows:
		tl = timeline.get(r.name, {})
		r["clean_minutes"] = _minutes((tl.get("started") or {}).get("at"),
		                              (tl.get("done") or tl.get("verified") or {}).get("at"))
		r["tasks"] = 1
		r["creation"] = str(r.get("creation") or "")
		r["due_by"] = str(r.get("due_by") or "") if r.get("due_by") else ""
		r["breached"] = 1 if r.get("breached") else 0
	return rows


def _fetch_room_status(property: str, **_) -> list[dict]:
	rows = frappe.get_all(
		"Room", filters={"property": property},
		fields=["room_number", "room_type", "floor", "housekeeping_status",
		        "occupancy_status"],
		order_by="room_number asc", limit_page_length=MAX_ROWS)
	return [{**r, "room": r.pop("room_number"), "rooms": 1} for r in rows]


def _fetch_lost_found(property: str, from_date: str, to_date: str,
                      **_) -> list[dict]:
	rows = frappe.get_all(
		"Lost And Found Item",
		filters={"property": property, "found_on": ["between", [from_date, to_date]]},
		fields=["name", "found_on", "item_description", "condition",
		        "found_in_room", "found_by", "status", "guest", "returned_on"],
		order_by="found_on desc", limit_page_length=MAX_ROWS)
	return [{**r, "items": 1} for r in rows]


def _fetch_pos_orders(property: str, from_date: str, to_date: str,
                      **_) -> list[dict]:
	rows = frappe.get_all(
		"POS Order",
		filters={
			"property": property,
			"creation": ["between", [from_date, f"{to_date} 23:59:59"]],
		},
		fields=[
			"name", "outlet", "status", "room", "customer_name", "guest",
			"guests", "order_total", "creation",
		],
		order_by="creation desc",
		limit_page_length=MAX_ROWS,
	)
	out = []
	for r in rows:
		out.append({
			"name": r.name,
			"outlet": r.get("outlet"),
			"posting_date": str(r.get("creation") or "")[:10],
			"status": r.get("status"),
			"guest_name": r.get("customer_name") or r.get("guest") or "",
			"room": r.get("room"),
			"covers": int(r.get("guests") or 0),
			"grand_total": float(r.get("order_total") or 0),
		})
	return out


def _elapsed_minutes(start, end) -> float | None:
	if not start or not end:
		return None
	from frappe.utils import get_datetime

	try:
		a, b = get_datetime(start), get_datetime(end)
	except Exception:
		return None
	return round((b - a).total_seconds() / 60.0, 1)


def _fetch_pos_items(property: str, from_date: str, to_date: str,
                     **_) -> list[dict]:
	return frappe.db.sql(
		"""
		SELECT COALESCE(poi.item_name, poi.menu_item) AS item_name,
		       po.outlet, DATE(po.creation) AS posting_date,
		       poi.qty, poi.rate, poi.amount, po.name AS `order`
		FROM `tabPOS Order Item` poi
		JOIN `tabPOS Order` po ON poi.parent = po.name
		WHERE po.property = %(p)s
		  AND po.creation BETWEEN %(f)s AND %(t)s
		  AND IFNULL(poi.voided, 0) = 0
		ORDER BY po.creation DESC, poi.idx
		LIMIT %(lim)s
		""",
		{"p": property, "f": from_date, "t": f"{to_date} 23:59:59",
		 "lim": MAX_ROWS},
		as_dict=True,
	)


def _fetch_service_tickets(property: str, from_date: str, to_date: str,
                           **_) -> list[dict]:
	rows = frappe.get_all(
		"Service Ticket",
		filters={
			"property": property,
			"creation": ["between", [from_date, f"{to_date} 23:59:59"]],
		},
		fields=[
			"name", "subject", "category", "priority", "status", "source",
			"room", "guest_name", "assigned_to_user", "breached", "creation",
			"due_by", "resolved_on", "first_response_at",
		],
		order_by="creation desc",
		limit_page_length=MAX_ROWS,
	)
	out = []
	for r in rows:
		out.append({
			"name": r.name,
			"subject": r.get("subject") or "",
			"category": r.get("category"),
			"priority": r.get("priority"),
			"status": r.get("status"),
			"source": r.get("source"),
			"room": r.get("room"),
			"guest_name": r.get("guest_name") or "",
			"assigned_to_user": r.get("assigned_to_user") or "",
			"breached": 1 if r.get("breached") else 0,
			"tickets": 1,
			"resolution_minutes": _elapsed_minutes(r.get("creation"),
			                                       r.get("resolved_on")),
			"response_minutes": _elapsed_minutes(r.get("creation"),
			                                     r.get("first_response_at")),
			"creation": str(r.get("creation") or ""),
			"due_by": str(r.get("due_by") or "") if r.get("due_by") else "",
			"resolved_on": (str(r.get("resolved_on") or "")
			                if r.get("resolved_on") else ""),
		})
	return out


def _fetch_laundry_orders(property: str, from_date: str, to_date: str,
                          **_) -> list[dict]:
	rows = frappe.db.sql(
		"""
		SELECT lo.name, lo.order_type, lo.room, lo.status, lo.express,
		       lo.collected_at, lo.delivered_at, lo.creation,
		       li.item_name, li.service_type, li.qty, li.returned_qty, li.amount
		FROM `tabLaundry Order` lo
		LEFT JOIN `tabLaundry Order Item` li ON li.parent = lo.name
		WHERE lo.property = %(p)s
		  AND lo.creation BETWEEN %(f)s AND %(t)s
		ORDER BY lo.creation DESC, li.idx
		LIMIT %(lim)s
		""",
		{"p": property, "f": from_date, "t": f"{to_date} 23:59:59",
		 "lim": MAX_ROWS},
		as_dict=True,
	)
	out = []
	for r in rows:
		mins = _elapsed_minutes(r.get("collected_at") or r.get("creation"),
		                        r.get("delivered_at"))
		out.append({
			"name": r.name,
			"order_type": r.get("order_type") or "Guest",
			"room": r.get("room") or "",
			"status": r.get("status"),
			"express": 1 if r.get("express") else 0,
			"item_name": r.get("item_name") or "",
			"service_type": r.get("service_type") or "",
			"qty": int(r.get("qty") or 0),
			"returned_qty": int(r.get("returned_qty") or 0),
			"amount": float(r.get("amount") or 0),
			"turnaround_hours": (round(mins / 60.0, 1) if mins is not None
			                     else None),
			"collected_at": (str(r.get("collected_at") or "")
			                 if r.get("collected_at") else ""),
			"delivered_at": (str(r.get("delivered_at") or "")
			                 if r.get("delivered_at") else ""),
			"creation": str(r.get("creation") or ""),
		})
	return out


def _fetch_shift_handover(property: str, from_date: str, to_date: str,
                          **_) -> list[dict]:
	rows = frappe.get_all(
		"Shift Handover",
		filters={
			"property": property,
			"shift_date": ["between", [from_date, to_date]],
		},
		fields=[
			"name", "shift_date", "shift", "status", "handed_over_to",
			"opening_cash", "cash_collected", "payouts", "closing_cash",
			"handover_notes",
		],
		order_by="shift_date desc, shift asc",
		limit_page_length=MAX_ROWS,
	)
	out = []
	for r in rows:
		out.append({
			"name": r.name,
			"shift_date": str(r.get("shift_date") or ""),
			"shift": r.get("shift"),
			"status": r.get("status"),
			"handed_over_to": r.get("handed_over_to") or "",
			"opening_cash": float(r.get("opening_cash") or 0),
			"cash_collected": float(r.get("cash_collected") or 0),
			"payouts": float(r.get("payouts") or 0),
			"closing_cash": float(r.get("closing_cash") or 0),
			"handover_notes": r.get("handover_notes") or "",
		})
	return out


def _fetch_early_departures(property: str, from_date: str, to_date: str,
                            **_) -> list[dict]:
	rows = frappe.db.sql(
		"""
		SELECT name, guest_name, room_type, room, check_in_date,
		       check_out_date, actual_check_out, company, source
		FROM `tabReservation`
		WHERE property = %(p)s
		  AND status = 'Checked Out'
		  AND actual_check_out IS NOT NULL
		  AND DATE(actual_check_out) < check_out_date
		  AND DATE(actual_check_out) BETWEEN %(f)s AND %(t)s
		ORDER BY actual_check_out DESC
		LIMIT %(lim)s
		""",
		{"p": property, "f": from_date, "t": to_date, "lim": MAX_ROWS},
		as_dict=True,
	)
	out = []
	for r in rows:
		short = date_diff(r.check_out_date, getdate(r.actual_check_out))
		out.append({
			"name": r.name,
			"guest_name": r.get("guest_name") or "",
			"room_type": r.get("room_type"),
			"room": r.get("room"),
			"check_in_date": str(r.get("check_in_date") or ""),
			"check_out_date": str(r.get("check_out_date") or ""),
			"actual_check_out": str(r.get("actual_check_out") or ""),
			"nights_short": max(int(short or 0), 0),
			"company": r.get("company") or "",
			"source": r.get("source") or "",
		})
	return out


def _fetch_overdue_by_company(property: str, **_) -> list[dict]:
	from kamra.ledger import city_ledger_aging
	return [a for a in city_ledger_aging(property)["accounts"] if a["overdue"] > 0]


def _fetch_dso(property: str, from_date: str, to_date: str, **kw) -> list[dict]:
	"""DSO = closing AR / what was billed in the period x days in it. Billed
	is invoices less credit notes and adjustments; a company billed nothing
	has no DSO."""
	rows = frappe.db.sql(
		"""
		SELECT a.company,
		       SUM(CASE WHEN e.kind != 'Payment' AND e.posting_date BETWEEN %(f)s AND %(t)s
		                THEN e.debit - e.credit ELSE 0 END) AS billed,
		       SUM(CASE WHEN e.kind = 'Payment' AND e.posting_date BETWEEN %(f)s AND %(t)s
		                THEN e.credit - e.debit ELSE 0 END) AS paid,
		       SUM(CASE WHEN e.posting_date <= %(t)s THEN e.debit - e.credit ELSE 0 END)
		           AS closing_balance
		FROM `tabCity Ledger Entry` e
		JOIN `tabCity Ledger Account` a ON a.name = e.account
		WHERE a.property = %(p)s
		GROUP BY a.company ORDER BY a.company
		""", {"p": property, "f": from_date, "t": to_date}, as_dict=True)
	days = date_diff(to_date, from_date) + 1
	rows = [r for r in rows if r.billed or r.paid or r.closing_balance]
	rows.append({"company": _("All companies"),
	             **{k: sum(float(r[k] or 0) for r in rows)
	                for k in ("billed", "paid", "closing_balance")}})
	for r in rows:
		for k in ("billed", "paid", "closing_balance"):
			r[k] = round(float(r[k] or 0), 2)
		r["dso"] = round(r["closing_balance"] / r["billed"] * days, 1) if r["billed"] > 0 else None
	return rows


FETCHERS: dict[str, Callable[..., list[dict]]] = {
	"arrivals": _fetch_arrivals,
	"departures": _fetch_departures,
	"in_house": _fetch_in_house,
	"no_shows_cancels": _fetch_no_shows_cancels,
	"occupancy_by_day": _fetch_occupancy_by_day,
	"folio_charges": _fetch_folio_charges,
	"payments": _fetch_payments,
	"voids": _fetch_voids,
	"contribution": _fetch_contribution,
	"hk_tasks": _fetch_hk_tasks,
	"room_status": _fetch_room_status,
	"lost_found": _fetch_lost_found,
	"pos_orders": _fetch_pos_orders,
	"pos_items": _fetch_pos_items,
	"service_tickets": _fetch_service_tickets,
	"laundry_orders": _fetch_laundry_orders,
	"shift_handover": _fetch_shift_handover,
	"early_departures": _fetch_early_departures,
	"overdue_by_company": _fetch_overdue_by_company,
	"dso": _fetch_dso,
}


# ---------------------------------------------------------------------------
# Project / filter / sort / group in Python
# ---------------------------------------------------------------------------

OPS = {
	"=": lambda a, b: str(a) == str(b),
	"!=": lambda a, b: str(a) != str(b),
	"contains": lambda a, b: str(b).lower() in str(a or "").lower(),
	">": lambda a, b: _num(a) > _num(b),
	"<": lambda a, b: _num(a) < _num(b),
	">=": lambda a, b: _num(a) >= _num(b),
	"<=": lambda a, b: _num(a) <= _num(b),
}


def _num(v) -> float:
	try:
		return float(v or 0)
	except (TypeError, ValueError):
		return 0.0


def _apply_filters(rows: list[dict], filters: list[dict]) -> list[dict]:
	if not filters:
		return rows
	out = []
	for row in rows:
		ok = True
		for flt in filters:
			field = flt.get("field")
			op = flt.get("op", "=")
			val = flt.get("value")
			fn = OPS.get(op)
			if not field or not fn:
				continue
			if not fn(row.get(field), val):
				ok = False
				break
		if ok:
			out.append(row)
	return out


def _apply_sort(rows: list[dict], sort_spec: list[dict]) -> list[dict]:
	if not sort_spec:
		return rows
	# apply last key first so first key is primary
	result = list(rows)
	for spec in reversed(sort_spec):
		field = spec.get("field")
		if not field:
			continue
		rev = (spec.get("dir") or "asc").lower() == "desc"
		result.sort(
			key=lambda r, f=field: (r.get(f) is None, r.get(f) if not isinstance(r.get(f), (int, float)) else _num(r.get(f))),
			reverse=rev,
		)
	return result


def _apply_group(rows: list[dict], group_by: list[str],
                 columns: list[str], averages: tuple = ()) -> list[dict]:
	"""Group by fields; numeric columns are summed (or averaged over rows that
	have a value, for `averages`), others take first value."""
	if not group_by:
		return rows
	buckets: dict[tuple, dict] = {}
	seen: dict[tuple, dict] = {}  # key -> {avg column: [values]}
	for row in rows:
		vals = seen.setdefault(tuple(row.get(g) for g in group_by), {})
		for c in averages:
			if row.get(c) is not None:
				vals.setdefault(c, []).append(_num(row.get(c)))
		key = tuple(row.get(g) for g in group_by)
		if key not in buckets:
			buckets[key] = {c: row.get(c) for c in columns}
			for c in columns:
				if c not in group_by and isinstance(row.get(c), (int, float)):
					buckets[key][c] = _num(row.get(c))
			continue
		agg = buckets[key]
		for c in columns:
			if c in group_by:
				continue
			if isinstance(row.get(c), (int, float)) or isinstance(agg.get(c), (int, float)):
				agg[c] = _num(agg.get(c)) + _num(row.get(c))
	for key, agg in buckets.items():
		for c in averages:
			if c in agg and c not in group_by:
				v = seen[key].get(c)
				agg[c] = round(sum(v) / len(v), 1) if v else None
	return list(buckets.values())


def _project(rows: list[dict], columns: list[str]) -> list[dict]:
	return [{c: r.get(c) for c in columns} for r in rows]


def _resolve_columns(ds: Dataset, columns: list[str] | None) -> list[str]:
	allowed = {c["id"] for c in ds["columns"]}
	if not columns:
		return [c["id"] for c in ds["columns"]]
	picked = [c for c in columns if c in allowed]
	return picked or [c["id"] for c in ds["columns"]]


def _previous_range(from_date: str, to_date: str) -> tuple[str, str]:
	"""Same-length window ending the day before from_date."""
	f, t = getdate(from_date), getdate(to_date)
	span = (t - f).days
	prev_to = getdate(add_days(f, -1))
	prev_from = getdate(add_days(prev_to, -span))
	return str(prev_from), str(prev_to)


def _numeric_totals(payload: dict) -> dict[str, float]:
	totals: dict[str, float] = {}
	for c in payload.get("columns") or []:
		if c.get("type") != "number":
			continue
		cid = c["id"]
		# averages (occ %, ADR) use mean; counts/sums use sum
		if cid in ("occupancy_pct", "adr", "revpar", "revpax",
		           "clean_minutes", "resolution_minutes", "response_minutes",
		           "turnaround_hours"):
			vals = [_num(r.get(cid)) for r in payload["rows"]
			        if r.get(cid) is not None]
			totals[cid] = round(sum(vals) / len(vals), 2) if vals else 0.0
		else:
			totals[cid] = round(
				sum(_num(r.get(cid)) for r in payload["rows"]), 2)
	return totals


def _build_comparison(current: dict, previous: dict,
                      label_by_id: dict[str, str] | None = None) -> dict:
	"""Metric / this / previous / variance rows for numeric columns."""
	cur = _numeric_totals(current)
	prev = _numeric_totals(previous)
	labels = label_by_id or {
		c["id"]: c["label"] for c in (current.get("columns") or [])}
	rows = []
	for cid, this_v in cur.items():
		prev_v = prev.get(cid, 0.0)
		var = round(this_v - prev_v, 2)
		pct = (round(var / abs(prev_v) * 100, 1)
		       if prev_v else (100.0 if this_v else 0.0))
		rows.append({
			"metric": labels.get(cid, cid),
			"this_period": this_v,
			"previous_period": prev_v,
			"variance": var,
			"variance_pct": pct,
		})
	return {
		"from_date": current.get("from_date"),
		"to_date": current.get("to_date"),
		"previous_from_date": previous.get("from_date"),
		"previous_to_date": previous.get("to_date"),
		"rows": rows,
	}


def _truthy(v) -> bool:
	return str(v).lower() not in ("0", "false", "none", "")


def _run_dataset(
	property: str,
	dataset_id: str,
	from_date: str | None,
	to_date: str | None,
	columns: list[str] | None = None,
	filters: list[dict] | None = None,
	group_by: list[str] | None = None,
	sort: list[dict] | None = None,
	compare: bool = False,
) -> dict:
	ds = DATASETS.get(dataset_id)
	if not ds:
		frappe.throw(_("Unknown dataset: {0}").format(dataset_id))
	if not _dataset_allowed(ds):
		frappe.throw(_("Your role cannot run this dataset."), frappe.PermissionError)
	if not _module_enabled(property, ds.get("module")):
		frappe.throw(_("This dataset's module is disabled for the property."))

	from_date, to_date = _guard_range(from_date, to_date, ds["needs_range"])
	fetcher = FETCHERS[dataset_id]
	rows = fetcher(property=property, from_date=from_date, to_date=to_date)
	# stringify dates for JSON
	for r in rows:
		for k, v in list(r.items()):
			if hasattr(v, "isoformat"):
				r[k] = str(v)

	col_ids = _resolve_columns(ds, columns)
	allowed = {c["id"] for c in ds["columns"]}
	safe_filters = [f for f in (filters or []) if f.get("field") in allowed]
	safe_group = [g for g in (group_by or []) if g in allowed]
	safe_sort = [s for s in (sort or []) if s.get("field") in allowed]

	rows = _apply_filters(rows, safe_filters)
	if safe_group:
		rows = _apply_group(rows, safe_group, col_ids, ds.get("averages", ()))
	rows = _apply_sort(rows, safe_sort)
	rows = _project(rows, col_ids)
	if len(rows) > MAX_ROWS:
		rows = rows[:MAX_ROWS]

	col_meta = [c for c in ds["columns"] if c["id"] in col_ids]
	# preserve order of col_ids
	by_id = {c["id"]: c for c in col_meta}
	ordered = [by_id[c] for c in col_ids if c in by_id]

	payload = {
		"dataset": dataset_id,
		"title": ds["label"],
		"property": property,
		"from_date": from_date,
		"to_date": to_date,
		"columns": ordered,
		"rows": rows,
		"row_count": len(rows),
		"truncated": len(rows) >= MAX_ROWS,
	}
	if compare and ds.get("needs_range"):
		pf, pt = _previous_range(from_date, to_date)
		prev = _run_dataset(
			property, dataset_id, pf, pt, columns, filters, group_by, sort,
			compare=False)
		payload["comparison"] = _build_comparison(payload, prev)
	return payload


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def _to_csv(payload: dict) -> str:
	cols = [c["id"] for c in payload["columns"]]
	buf = io.StringIO()
	w = csv.writer(buf)
	w.writerow([_tr(c["label"], payload.get("lang")) for c in payload["columns"]])
	for row in payload["rows"]:
		w.writerow([row.get(c) for c in cols])
	return buf.getvalue()


def _tr(text: str, lang: str | None) -> str:
	"""Report wording in the reader's language, from kamra/translations."""
	return _(text, lang=lang) if lang and lang != "en" else text


def _table_html(payload: dict, lang: str = "en") -> str:
	esc = frappe.utils.escape_html
	cols = payload["columns"]
	ths = "".join(f"<th>{esc(_tr(c['label'], lang))}</th>" for c in cols)
	trs = "".join(
		"<tr>" + "".join(
			f"<td>{esc(str(row.get(c['id']) if row.get(c['id']) is not None else ''))}</td>"
			for c in cols) + "</tr>"
		for row in payload["rows"])
	return f"<table><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table>"


def _page_html(title: str, meta: str, body: str, lang: str = "en") -> str:
	rtl = lang == "ar"
	align = "right" if rtl else "left"
	esc = frappe.utils.escape_html
	return (
		f'<!DOCTYPE html>\n<html lang="{lang}" dir="{"rtl" if rtl else "ltr"}">\n'
		f'<head><meta charset="utf-8"><title>{esc(title)}</title>\n'
		"<style>\n"
		"body{font-family:system-ui,sans-serif;font-size:12px;color:#18181b;margin:24px}\n"
		"h1{font-size:18px;margin:0 0 4px}\n"
		"h2{font-size:14px;margin:24px 0 6px}\n"
		"h3{font-size:12px;margin:12px 0 4px;color:#52525b}\n"
		".meta{color:#71717a;margin-bottom:16px}\n"
		".kpis{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 20px}\n"
		".kpi{border:1px solid #e4e4e7;padding:10px 14px;min-width:110px}\n"
		".kpi .lbl{font-size:10px;text-transform:uppercase;letter-spacing:.04em;"
		"color:#71717a}\n"
		".kpi .val{font-size:18px;font-weight:600;margin-top:2px}\n"
		".kpi .delta{font-size:11px;margin-top:2px;color:#71717a}\n"
		".kpi .up{color:#15803d}.kpi .down{color:#b91c1c}\n"
		"table{border-collapse:collapse;width:100%}\n"
		f"th,td{{border:1px solid #e4e4e7;padding:6px 8px;text-align:{align}}}\n"
		"th{background:#f4f4f5;font-size:10px;text-transform:uppercase;letter-spacing:.04em}\n"
		"</style></head>\n<body>\n"
		f"<h1>{esc(title)}</h1>\n"
		f'<div class="meta">{esc(meta)}</div>\n'
		f"{body}\n</body></html>"
	)


def _comparison_html(comparison: dict, lang: str = "en") -> str:
	if not comparison or not comparison.get("rows"):
		return ""
	esc = frappe.utils.escape_html
	cols = [
		{"id": "metric", "label": "Metric"},
		{"id": "this_period", "label": "This period"},
		{"id": "previous_period", "label": "Previous period"},
		{"id": "variance", "label": "Variance"},
		{"id": "variance_pct", "label": "Variance %"},
	]
	payload = {"columns": cols, "rows": comparison["rows"]}
	heading = _tr("vs previous period", lang)
	return (f"<h3>{esc(heading)}</h3>\n{_table_html(payload, lang)}\n")


def _kpi_html(kpis: list[dict], lang: str = "en") -> str:
	if not kpis:
		return ""
	esc = frappe.utils.escape_html
	tiles = []
	for k in kpis:
		var = k.get("variance")
		cls = ""
		delta = ""
		if var is not None:
			cls = "up" if var > 0 else ("down" if var < 0 else "")
			sign = "+" if var > 0 else ""
			pct = k.get("variance_pct")
			delta = (f'<div class="delta {cls}">{esc(sign)}{esc(str(var))}'
			         + (f" ({sign}{esc(str(pct))}%)" if pct is not None else "")
			         + "</div>")
		tiles.append(
			f'<div class="kpi"><div class="lbl">{esc(_tr(k["label"], lang))}</div>'
			f'<div class="val">{esc(str(k["value"]))}</div>{delta}</div>')
	return f'<div class="kpis">{"".join(tiles)}</div>\n'


def _to_html(payload: dict, lang: str = "en") -> str:
	meta = (f"{payload.get('property')} · {payload.get('from_date')} → "
	        f"{payload.get('to_date')} · "
	        + _tr("{0} rows", lang).format(payload.get("row_count", 0)))
	body = _table_html(payload, lang)
	if payload.get("comparison"):
		body += _comparison_html(payload["comparison"], lang)
	return _page_html(_tr(payload.get("title") or "Report", lang), meta,
	                  body, lang)


def _pack_kpis(sections: list[dict]) -> list[dict]:
	"""KPI tiles from an occupancy_by_day section when the pack has one."""
	occ = next((s for s in sections if s.get("dataset") == "occupancy_by_day"),
	           None)
	if not occ:
		return []
	label_of = {c["id"]: c["label"] for c in occ.get("columns") or []}
	cmp_by_label = {
		r["metric"]: r for r in (occ.get("comparison") or {}).get("rows", [])}
	wanted = ("rooms_sold", "occupancy_pct", "adr", "revpar",
	          "room_revenue", "total_revenue")
	totals = _numeric_totals(occ)
	out = []
	for cid in wanted:
		if cid not in totals:
			continue
		label = label_of.get(cid, cid)
		row = cmp_by_label.get(label)
		tile = {"label": label, "value": totals[cid]}
		if row:
			tile["variance"] = row.get("variance")
			tile["variance_pct"] = row.get("variance_pct")
		out.append(tile)
	return out


def _pack_html(pack: dict, lang: str = "en") -> str:
	esc = frappe.utils.escape_html
	body = _kpi_html(pack.get("kpis") or [], lang)
	for s in pack["sections"]:
		body += f"<h2>{esc(_tr(s['title'], lang))}</h2>\n{_table_html(s, lang)}\n"
		if s.get("comparison"):
			body += _comparison_html(s["comparison"], lang)
	meta = f"{pack['property']} · {pack['from_date']} → {pack['to_date']}"
	if pack.get("previous_from_date"):
		meta += (f" · {_tr('vs previous period', lang)} "
		         f"{pack['previous_from_date']} → {pack['previous_to_date']}")
	return _page_html(_tr(pack["title"], lang), meta, body, lang)


# ---------------------------------------------------------------------------
# Whitelist API
# ---------------------------------------------------------------------------

@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Hotel Admin", "Revenue Manager",
               "Housekeeping", "Kamra Agent", "Night Auditor")
def list_report_datasets(property: str):
	"""Whitelisted datasets the current user may run on this property."""
	assert_property_access(property)
	out = []
	for ds in DATASETS.values():
		if not _dataset_allowed(ds):
			continue
		if not _module_enabled(property, ds.get("module")):
			continue
		out.append({
			"id": ds["id"],
			"label": ds["label"],
			"description": ds["description"],
			"module": ds.get("module"),
			"needs_range": ds["needs_range"],
			"columns": ds["columns"],
			"filter_ops": list(OPS.keys()),
		})
	return out


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Hotel Admin", "Revenue Manager",
               "Housekeeping", "Kamra Agent", "Night Auditor")
def list_report_packs(property: str):
	"""Department packs with the sections this user may run here."""
	assert_property_access(property)
	out = []
	for pid, pack in PACKS.items():
		sections = _pack_sections(property, pid)
		if sections:
			out.append({"id": PACK_PREFIX + pid, "label": pack["label"],
			            "description": pack["description"],
			            "sections": [s["title"] for s in sections]})
	return out


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Hotel Admin", "Revenue Manager",
               "Housekeeping", "Kamra Agent", "Night Auditor")
def run_report_pack(property: str, pack: str, from_date: str | None = None,
                    to_date: str | None = None, format: str | None = "json",
                    lang: str | None = "en", compare: int | str | None = 1):
	"""Run a department pack (id from list_report_packs) for a date range.
	format=json (sections of rows) or html (one printable page).
	compare=1 (default) adds this-vs-previous totals on each section."""
	assert_property_access(property)
	pid = _pack_id(pack if pack.startswith(PACK_PREFIX) else PACK_PREFIX + pack)
	sections = _pack_sections(property, pid)
	if not sections:
		frappe.throw(_("Your role cannot run any part of this pack."),
		             frappe.PermissionError)
	to_date = to_date or add_days(nowdate(), -1)
	from_date = from_date or add_days(to_date, -6)
	do_compare = _truthy(1 if compare is None else compare)
	out = {"pack": PACK_PREFIX + pid, "title": PACKS[pid]["label"],
	       "property": property, "from_date": from_date, "to_date": to_date,
	       "sections": []}
	if do_compare:
		pf, pt = _previous_range(from_date, to_date)
		out["previous_from_date"] = pf
		out["previous_to_date"] = pt
	for s in sections:
		res = _run_dataset(property, s["dataset"], from_date, to_date,
		                   s.get("columns"), s.get("filters"), s.get("group_by"),
		                   compare=do_compare and DATASETS[s["dataset"]].get(
			                   "needs_range", False))
		res["title"] = s["title"]
		out["sections"].append(res)
	out["row_count"] = sum(s["row_count"] for s in out["sections"])
	out["kpis"] = _pack_kpis(out["sections"])
	if (format or "json").lower() == "html":
		return {"format": "html", "title": out["title"],
		        "filename": _filename(out, "html"),
		        "content": _pack_html(out, lang or "en")}
	return out


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Hotel Admin", "Revenue Manager",
               "Housekeeping", "Kamra Agent", "Night Auditor")
def list_custom_reports(property: str):
	"""Saved reports visible to this user on the property."""
	assert_property_access(property)
	user = frappe.session.user
	rows = frappe.get_all(
		"Kamra Custom Report",
		filters={"property": property},
		fields=[
			"name", "title", "dataset", "is_shared", "owner",
			"schedule_frequency", "schedule_time", "schedule_weekday",
			"recipients", "last_sent_on", "modified",
		],
		order_by="modified desc",
		limit_page_length=200,
	)
	visible = []
	for r in rows:
		ds = DATASETS.get(r.dataset)
		if ds and not _dataset_allowed(ds):
			continue
		pid = r.dataset[len(PACK_PREFIX):] if r.dataset.startswith(PACK_PREFIX) else None
		if pid and (pid not in PACKS or not _pack_sections(property, pid)):
			continue
		if pid:
			ds = {"label": PACKS[pid]["label"]}
		if r.is_shared or r.owner == user or _can_edit():
			visible.append({
				**r,
				"is_shared": bool(r.is_shared),
				"can_edit": r.owner == user or _can_edit(),
				"dataset_label": (ds or {}).get("label") or r.dataset,
			})
	return visible


def _load_report(name: str, property: str | None = None) -> "frappe.model.document.Document":
	doc = frappe.get_doc("Kamra Custom Report", name)
	if property and doc.property != property:
		frappe.throw(_("Report does not belong to this property."), frappe.PermissionError)
	assert_property_access(doc.property)
	return doc


def _assert_can_edit_doc(doc):
	if doc.owner == frappe.session.user or _can_edit():
		return
	frappe.throw(_("You cannot edit this report."), frappe.PermissionError)


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Hotel Admin", "Revenue Manager",
               "Housekeeping", "Kamra Agent", "Night Auditor")
def get_custom_report(name: str, property: str | None = None):
	"""Full saved definition for the builder."""
	doc = _load_report(name, property)
	ds = DATASETS.get(doc.dataset)
	if ds and not _dataset_allowed(ds):
		frappe.throw(_("Your role cannot open this report."), frappe.PermissionError)
	if not (doc.is_shared or doc.owner == frappe.session.user or _can_edit()):
		frappe.throw(_("This report is private."), frappe.PermissionError)
	return {
		"name": doc.name,
		"property": doc.property,
		"title": doc.title,
		"dataset": doc.dataset,
		"is_shared": bool(doc.is_shared),
		"columns": _parse_json(doc.columns_json, []),
		"filters": _parse_json(doc.filters_json, []),
		"group_by": _parse_json(doc.group_by_json, []),
		"sort": _parse_json(doc.sort_json, []),
		"schedule_frequency": doc.schedule_frequency or "Off",
		"schedule_time": doc.schedule_time or "07:00",
		"schedule_weekday": doc.schedule_weekday or "Mon",
		"recipients": doc.recipients or "",
		"lang": doc.lang or "en",
		"last_sent_on": str(doc.last_sent_on) if doc.last_sent_on else None,
		"owner": doc.owner,
		"can_edit": doc.owner == frappe.session.user or _can_edit(),
	}


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Hotel Admin", "System Manager", "Front Desk",
               "Revenue Manager", "Housekeeping", "Kamra Agent", "Night Auditor")
def save_custom_report(
	property: str,
	title: str,
	dataset: str,
	columns: str | list | None = None,
	filters: str | list | None = None,
	group_by: str | list | None = None,
	sort: str | list | None = None,
	is_shared: int | str | None = 0,
	schedule_frequency: str | None = "Off",
	schedule_time: str | None = "07:00",
	schedule_weekday: str | None = "Mon",
	recipients: str | None = "",
	name: str | None = None,
	lang: str | None = None,
):
	"""Create or update a saved custom report definition. lang (en, es, ar)
	is the language its scheduled emails go out in."""
	assert_property_access(property)
	pid = _pack_id(dataset)
	ds = {"label": PACKS[pid]["label"], "columns": []} if pid else DATASETS.get(dataset)
	if not ds:
		frappe.throw(_("Unknown dataset: {0}").format(dataset))
	if pid and not _pack_sections(property, pid):
		frappe.throw(_("Your role cannot run any part of this pack."),
		             frappe.PermissionError)
	if not pid and not _dataset_allowed(ds):
		frappe.throw(_("Your role cannot save this dataset."), frappe.PermissionError)

	cols = [] if pid else _resolve_columns(ds, _parse_json(columns, []))
	flts = _parse_json(filters, [])
	grp = _parse_json(group_by, [])
	srt = _parse_json(sort, [])

	freq = schedule_frequency or "Off"
	if freq not in ("Off", "Daily", "Weekly"):
		frappe.throw(_("Invalid schedule frequency."))

	if name:
		doc = _load_report(name, property)
		_assert_can_edit_doc(doc)
	else:
		if not _can_edit() and frappe.session.user not in ("Administrator",):
			# Front Desk etc. may still save private reports they own
			pass
		doc = frappe.new_doc("Kamra Custom Report")
		doc.property = property

	doc.title = (title or "").strip() or ds["label"]
	doc.dataset = dataset
	doc.is_shared = 1 if str(is_shared) in ("1", "True", "true") else 0
	if doc.is_shared and not _can_edit():
		frappe.throw(_("Only Finance or Hotel Admin can share a report."),
		             frappe.PermissionError)
	doc.columns_json = json.dumps(cols)
	doc.filters_json = json.dumps(flts)
	doc.group_by_json = json.dumps(grp)
	doc.sort_json = json.dumps(srt)
	doc.schedule_frequency = freq
	doc.schedule_time = (schedule_time or "07:00").strip()[:5]
	doc.schedule_weekday = schedule_weekday or "Mon"
	doc.recipients = (recipients or "").strip()
	if lang:
		doc.lang = lang
	if freq != "Off" and not doc.recipients:
		frappe.throw(_("Add at least one recipient email for a scheduled report."))
	if freq != "Off" and not _can_edit():
		frappe.throw(_("Only Finance or Hotel Admin can schedule email."),
		             frappe.PermissionError)

	doc.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists saved report before returning to SPA/MCP; reviewed as intentional
	return get_custom_report(doc.name, property)


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Hotel Admin", "System Manager", "Front Desk",
               "Revenue Manager", "Housekeeping", "Kamra Agent", "Night Auditor")
def delete_custom_report(name: str, property: str | None = None):
	"""Delete a saved report the user can edit."""
	doc = _load_report(name, property)
	_assert_can_edit_doc(doc)
	frappe.delete_doc("Kamra Custom Report", doc.name, ignore_permissions=True)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists delete before returning; reviewed as intentional
	return {"ok": True}


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Hotel Admin", "Revenue Manager",
               "Housekeeping", "Kamra Agent", "Night Auditor")
def run_custom_report(
	property: str,
	dataset: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
	columns: str | list | None = None,
	filters: str | list | None = None,
	group_by: str | list | None = None,
	sort: str | list | None = None,
	name: str | None = None,
	format: str | None = "json",
	lang: str | None = "en",
	compare: int | str | None = 0,
):
	"""Run a saved report or an ad-hoc definition. format=json|csv|html.
	compare=1 adds this-vs-previous totals for number columns."""
	assert_property_access(property)
	if name:
		doc = _load_report(name, property)
		ds_id = doc.dataset
		cols = _parse_json(doc.columns_json, [])
		flts = _parse_json(doc.filters_json, [])
		grp = _parse_json(doc.group_by_json, [])
		srt = _parse_json(doc.sort_json, [])
		title = doc.title
	else:
		if not dataset:
			frappe.throw(_("dataset or name is required."))
		ds_id = dataset
		cols = _parse_json(columns, [])
		flts = _parse_json(filters, [])
		grp = _parse_json(group_by, [])
		srt = _parse_json(sort, [])
		title = None

	if _pack_id(ds_id):
		res = run_report_pack(property, ds_id, from_date, to_date, format, lang,
		                      compare=compare if compare is not None else 1)
		if title and isinstance(res, dict):
			res["title"] = title
		return res

	payload = _run_dataset(
		property, ds_id, from_date, to_date, cols, flts, grp, srt,
		compare=_truthy(compare))
	if title:
		payload["title"] = title
	payload["lang"] = lang or "en"

	fmt = (format or "json").lower()
	if fmt == "csv":
		return {"format": "csv", "filename": _filename(payload, "csv"),
		        "content": _to_csv(payload), **{k: payload[k] for k in
		        ("title", "from_date", "to_date", "row_count", "dataset")}}
	if fmt == "html":
		return {"format": "html", "filename": _filename(payload, "html"),
		        "content": _to_html(payload, lang or "en"),
		        "title": payload["title"], "row_count": payload["row_count"]}
	return payload


def _filename(payload: dict, ext: str) -> str:
	safe = "".join(
		c if c.isalnum() or c in "-_" else "_"
		for c in (payload.get("title") or payload.get("dataset") or "report")
	)[:40]
	return f"{safe}_{payload.get('from_date')}_{payload.get('to_date')}.{ext}"


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Hotel Admin", "System Manager", "Front Desk",
               "Revenue Manager", "Housekeeping", "Kamra Agent", "Night Auditor")
def email_custom_report(
	property: str,
	recipients: str,
	name: str | None = None,
	dataset: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
	columns: str | list | None = None,
	filters: str | list | None = None,
	group_by: str | list | None = None,
	sort: str | list | None = None,
	lang: str | None = "en",
	attach_format: str | None = "csv",
):
	"""Run a report and email it (CSV or HTML attachment)."""
	assert_property_access(property)
	emails = [e.strip() for e in (recipients or "").split(",") if e.strip()]
	if not emails:
		frappe.throw(_("Add at least one recipient email."))

	# default date window for scheduled-style sends without dates: yesterday
	if not from_date and not to_date:
		to_date = add_days(nowdate(), -1)
		from_date = to_date

	meta = run_custom_report(
		property=property, dataset=dataset, from_date=from_date,
		to_date=to_date, columns=columns, filters=filters,
		group_by=group_by, sort=sort, name=name, format="json",
		lang=lang or "en",
	)
	fmt = (attach_format or "csv").lower()
	if "sections" in meta:  # a department pack is one HTML page
		content = _pack_html(meta, lang or "en")
		fname = _filename(meta, "html")
	elif fmt == "html":
		content = _to_html(meta, lang or "en")
		fname = _filename(meta, "html")
	else:
		content = _to_csv(meta)
		fname = _filename(meta, "csv")

	title = _tr(meta.get("title") or "Kamra report", lang)
	esc = frappe.utils.escape_html
	frappe.sendmail(
		recipients=emails,
		subject=f"{title} · {meta.get('from_date')} - {meta.get('to_date')}",
		message=(
			f'<div dir="{"rtl" if lang == "ar" else "ltr"}">'
			f"<p>{esc(title)}</p>"
			f"<p>{esc(str(meta.get('property')))} · "
			f"{esc(str(meta.get('from_date')))} → {esc(str(meta.get('to_date')))} · "
			+ esc(_tr("{0} rows", lang).format(meta.get("row_count", 0))) + "</p>"
			f"<p>{esc(_tr('The report is attached.', lang))}</p></div>"
		),
		attachments=[{
			"fname": fname,
			"fcontent": content.encode("utf-8") if isinstance(content, str) else content,
		}],
	)

	if name:
		frappe.db.set_value("Kamra Custom Report", name, "last_sent_on",
		                    now_datetime())
		frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persist last_sent_on after mail; reviewed as intentional

	return {"ok": True, "sent_to": emails, "row_count": meta.get("row_count", 0)}


def _weekday_code(dt: datetime) -> str:
	return ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")[dt.weekday()]


def run_scheduled_custom_reports():
	"""Hourly: send daily/weekly reports whose schedule_time matches now."""
	now = now_datetime()
	hhmm = now.strftime("%H:%M")
	# match within the current hour (scheduler fires hourly)
	hour_prefix = now.strftime("%H:")
	rows = frappe.get_all(
		"Kamra Custom Report",
		filters={"schedule_frequency": ["in", ["Daily", "Weekly"]]},
		fields=[
			"name", "property", "title", "dataset", "schedule_frequency",
			"schedule_time", "schedule_weekday", "recipients", "last_sent_on",
			"columns_json", "filters_json", "group_by_json", "sort_json", "lang",
		],
	)
	for r in rows:
		st = (r.schedule_time or "07:00").strip()[:5]
		if not st.startswith(hour_prefix) and st != hhmm:
			# only fire in the scheduled hour
			if len(st) >= 2 and st[:2] != now.strftime("%H"):
				continue
		if r.schedule_frequency == "Weekly":
			if _weekday_code(now) != (r.schedule_weekday or "Mon"):
				continue
		# skip if already sent today
		if r.last_sent_on and getdate(r.last_sent_on) == getdate(now):
			continue
		if not r.recipients:
			continue
		try:
			to_date = add_days(nowdate(), -1)
			from_date = to_date
			if r.schedule_frequency == "Weekly":
				from_date = add_days(to_date, -6)
			from kamra.authz import act_as

			# Scheduler has no session roles; run as Administrator for the
			# property-scoped send (same pattern as other nightly jobs).
			with act_as("Administrator"):
				email_custom_report(
					property=r.property,
					recipients=r.recipients,
					name=r.name,
					from_date=from_date,
					to_date=to_date,
					attach_format="csv",
					lang=r.lang or "en",
				)
		except Exception:
			frappe.log_error(
				title=f"Custom report schedule failed: {r.name}",
				message=frappe.get_traceback(),
			)
