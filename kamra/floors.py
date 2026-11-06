"""Floors - the master behind Room.floor, and bulk room creation.

Room.floor stays the floor's NAME as text (a soft link), so every payload
and import that reads or writes it is unchanged. A Floor record gives the
name an order and a place to rename or retire it; Room.validate creates the
record the first time a name is used.
"""

import re

import frappe
from frappe import _

from kamra.authz import assert_property_access, require_roles

_NUM = re.compile(r"-?\d+")
_OTHERS_BASE = 10000


def floor_number(name: str):
	"""The number in a floor name ("3", "Floor 3", "3rd"), or None."""
	m = _NUM.search(name or "")
	return int(m.group()) if m else None


def natural_key(name: str):
	"""Numbers by value, then everything else alphabetically."""
	n = floor_number(name)
	return (0, n, (name or "").lower()) if n is not None else (1, 0, (name or "").lower())


def default_sort_order(property: str, floor_name: str) -> int:
	"""Numbered floors sit at 10 x the number; others after the last of them,
	in the order they appear. The owner reorders from Admin > Floors."""
	n = floor_number(floor_name)
	if n is not None:
		return n * 10
	top = frappe.db.sql(
		"select max(sort_order) from `tabFloor` where property=%s", property)[0][0]
	return max(_OTHERS_BASE, (top or 0) + 10)


def ensure_floor(property: str, floor_name: str) -> str | None:
	"""Create the Floor for a name used on a room (and re-enable a disabled
	one). Returns the Floor's name, or None for a blank floor."""
	floor_name = (floor_name or "").strip()
	if not floor_name:
		return None
	name = frappe.db.get_value(
		"Floor", {"property": property, "floor_name": floor_name}, ["name", "disabled"],
		as_dict=True)
	if name:
		if name.disabled:
			frappe.db.set_value("Floor", name.name, "disabled", 0)
		return name.name
	doc = frappe.get_doc({
		"doctype": "Floor", "property": property, "floor_name": floor_name,
		"sort_order": default_sort_order(property, floor_name)})
	doc.insert(ignore_permissions=True)
	return doc.name


def floors_for(property: str) -> list:
	"""[{name, sort_order}] in board order, for the room boards' `floors`."""
	rows = frappe.get_all(
		"Floor", filters={"property": property, "disabled": 0},
		fields=["floor_name", "sort_order"])
	rows.sort(key=lambda r: (r.sort_order or 0, natural_key(r.floor_name)))
	return [{"name": r.floor_name, "sort_order": r.sort_order or 0} for r in rows]


def parse_range(start, end, prefix: str = "") -> list:
	"""Room numbers start..end (inclusive), each with the optional prefix."""
	try:
		a, b = int(start), int(end)
	except (TypeError, ValueError):
		frappe.throw(_("Enter the first and last room number as whole numbers."))
	if b < a:
		frappe.throw(_("The last room number must not be below the first."))
	if b - a >= 500:
		frappe.throw(_("Add at most 500 rooms at a time."))
	prefix = (prefix or "").strip()
	return [f"{prefix}{n}" for n in range(a, b + 1)]


@frappe.whitelist()
@require_roles("Hotel Admin")
def add_rooms(property: str, floor: str, room_type: str, start, end,
              prefix: str = "", preview=0):
	"""Create rooms start..end on a floor (numbers that already exist are
	skipped). preview=1 only reports what would happen. Admin > Rooms >
	Add rooms."""
	assert_property_access(property)
	numbers = parse_range(start, end, prefix)
	if frappe.db.get_value("Room Type", room_type, "property") != property:
		frappe.throw(_("Room type {0} does not belong to this property.").format(room_type))
	have = set(frappe.get_all(
		"Room", filters={"property": property, "room_number": ("in", numbers)},
		pluck="room_number"))
	new = [n for n in numbers if n not in have]
	skipped = [n for n in numbers if n in have]
	if not int(preview):
		for n in new:
			frappe.get_doc({
				"doctype": "Room", "property": property, "room_number": n,
				"room_type": room_type, "floor": (floor or "").strip()}).insert()
	return {"create": new, "skipped": skipped, "created": 0 if int(preview) else len(new)}
