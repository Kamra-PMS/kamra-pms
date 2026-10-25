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
from frappe.utils import add_days, getdate, now_datetime, nowdate

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
			_col("share", "Share %", "number"),
		],
	},
	"hk_tasks": {
		"id": "hk_tasks",
		"label": "Housekeeping tasks",
		"description": "Housekeeping tasks created in the date range.",
		"module": "housekeeping",
		"roles": ("Housekeeping", "Front Desk", "Hotel Admin", "Kamra Agent"),
		"date_field": "creation",
		"needs_range": True,
		"columns": [
			_col("name", "Task"),
			_col("room", "Room"),
			_col("task_type", "Type"),
			_col("priority", "Priority"),
			_col("status", "Status"),
			_col("assigned_to_user", "Assigned to"),
			_col("due_by", "Due by"),
			_col("breached", "Breached", "number"),
			_col("creation", "Created"),
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
}


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
	if not module:
		return True
	enabled = frappe.db.get_value("Property", property, "enabled_modules")
	if not enabled:
		return True
	try:
		mods = json.loads(enabled) if isinstance(enabled, str) else enabled
	except (TypeError, ValueError):
		return True
	if not mods:
		return True
	return module in mods


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
	for r in rows:
		r["creation"] = str(r.get("creation") or "")
		r["due_by"] = str(r.get("due_by") or "") if r.get("due_by") else ""
		r["breached"] = 1 if r.get("breached") else 0
	return rows


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
	"pos_orders": _fetch_pos_orders,
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
                 columns: list[str]) -> list[dict]:
	"""Group by fields; numeric columns are summed, others take first value."""
	if not group_by:
		return rows
	buckets: dict[tuple, dict] = {}
	for row in rows:
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
	return list(buckets.values())


def _project(rows: list[dict], columns: list[str]) -> list[dict]:
	return [{c: r.get(c) for c in columns} for r in rows]


def _resolve_columns(ds: Dataset, columns: list[str] | None) -> list[str]:
	allowed = {c["id"] for c in ds["columns"]}
	if not columns:
		return [c["id"] for c in ds["columns"]]
	picked = [c for c in columns if c in allowed]
	return picked or [c["id"] for c in ds["columns"]]


def _run_dataset(
	property: str,
	dataset_id: str,
	from_date: str | None,
	to_date: str | None,
	columns: list[str] | None = None,
	filters: list[dict] | None = None,
	group_by: list[str] | None = None,
	sort: list[dict] | None = None,
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
		rows = _apply_group(rows, safe_group, col_ids)
	rows = _apply_sort(rows, safe_sort)
	rows = _project(rows, col_ids)
	if len(rows) > MAX_ROWS:
		rows = rows[:MAX_ROWS]

	col_meta = [c for c in ds["columns"] if c["id"] in col_ids]
	# preserve order of col_ids
	by_id = {c["id"]: c for c in col_meta}
	ordered = [by_id[c] for c in col_ids if c in by_id]

	return {
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


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def _to_csv(payload: dict) -> str:
	cols = [c["id"] for c in payload["columns"]]
	buf = io.StringIO()
	w = csv.writer(buf)
	w.writerow([c["label"] for c in payload["columns"]])
	for row in payload["rows"]:
		w.writerow([row.get(c) for c in cols])
	return buf.getvalue()


def _to_html(payload: dict, lang: str = "en") -> str:
	rtl = lang == "ar"
	direction = "rtl" if rtl else "ltr"
	cols = payload["columns"]
	ths = "".join(f"<th>{frappe.utils.escape_html(c['label'])}</th>" for c in cols)
	trs = []
	for row in payload["rows"]:
		tds = "".join(
			f"<td>{frappe.utils.escape_html(str(row.get(c['id']) if row.get(c['id']) is not None else ''))}</td>"
			for c in cols
		)
		trs.append(f"<tr>{tds}</tr>")
	title = frappe.utils.escape_html(payload.get("title") or "Report")
	meta = frappe.utils.escape_html(
		f"{payload.get('property')} · {payload.get('from_date')} → {payload.get('to_date')}"
	)
	align = "right" if rtl else "left"
	row_count = payload.get("row_count", 0)
	body_rows = "".join(trs)
	return (
		f'<!DOCTYPE html>\n<html lang="{lang}" dir="{direction}">\n'
		f'<head><meta charset="utf-8"><title>{title}</title>\n'
		"<style>\n"
		"body{font-family:system-ui,sans-serif;font-size:12px;color:#18181b;margin:24px}\n"
		"h1{font-size:18px;margin:0 0 4px}\n"
		".meta{color:#71717a;margin-bottom:16px}\n"
		"table{border-collapse:collapse;width:100%}\n"
		f"th,td{{border:1px solid #e4e4e7;padding:6px 8px;text-align:{align}}}\n"
		"th{background:#f4f4f5;font-size:10px;text-transform:uppercase;letter-spacing:.04em}\n"
		"</style></head>\n<body>\n"
		f"<h1>{title}</h1>\n"
		f'<div class="meta">{meta} · {row_count} rows</div>\n'
		f"<table><thead><tr>{ths}</tr></thead><tbody>{body_rows}</tbody></table>\n"
		"</body></html>"
	)


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
):
	"""Create or update a saved custom report definition."""
	assert_property_access(property)
	ds = DATASETS.get(dataset)
	if not ds:
		frappe.throw(_("Unknown dataset: {0}").format(dataset))
	if not _dataset_allowed(ds):
		frappe.throw(_("Your role cannot save this dataset."), frappe.PermissionError)

	cols = _resolve_columns(ds, _parse_json(columns, []))
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
):
	"""Run a saved report or an ad-hoc definition. format=json|csv|html."""
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

	payload = _run_dataset(
		property, ds_id, from_date, to_date, cols, flts, grp, srt)
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
	if fmt == "html":
		content = _to_html(meta, lang or "en")
		fname = _filename(meta, "html")
	else:
		content = _to_csv(meta)
		fname = _filename(meta, "csv")
		fmt = "csv"

	title = meta.get("title") or "Kamra report"

	frappe.sendmail(
		recipients=emails,
		subject=f"{title} · {meta.get('from_date')} - {meta.get('to_date')}",
		message=(
			f"<p>{frappe.utils.escape_html(title)}</p>"
			f"<p>{frappe.utils.escape_html(str(meta.get('property')))} · "
			f"{frappe.utils.escape_html(str(meta.get('from_date')))} → "
			f"{frappe.utils.escape_html(str(meta.get('to_date')))} · "
			f"{meta.get('row_count', 0)} rows</p>"
			"<p>The report is attached.</p>"
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
			"columns_json", "filters_json", "group_by_json", "sort_json",
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
				)
		except Exception:
			frappe.log_error(
				title=f"Custom report schedule failed: {r.name}",
				message=frappe.get_traceback(),
			)
