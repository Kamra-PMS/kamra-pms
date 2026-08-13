# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Helpers to create / maintain Sellable Units from Rooms and Room Types."""

from __future__ import annotations

import frappe


def ensure_individual_siu(room_name: str) -> str | None:
	"""Create (or return) the individual SIU backing a physical Room."""
	room = frappe.db.get_value(
		"Room",
		room_name,
		["name", "property", "room_number", "room_type"],
		as_dict=True,
	)
	if not room:
		return None

	existing = frappe.db.sql(
		"""
		SELECT parent FROM `tabSellable Unit Room`
		WHERE room = %s
		LIMIT 1
		""",
		room.name,
	)
	if existing:
		return existing[0][0]

	unit_name = f"Room {room.room_number}"
	doc = frappe.get_doc(
		{
			"doctype": "Sellable Unit",
			"property": room.property,
			"unit_name": unit_name,
			"unit_kind": "individual",
			"is_active": 1,
			"room_type": room.room_type,
			"competition_group": f"{room.property}::{room.room_type}",
			"is_auto_assignable": 1,
			"physical_rooms": [{"room": room.name}],
		}
	)
	# Avoid name collisions when room numbers repeat across types.
	if frappe.db.exists("Sellable Unit", f"{room.property}-{unit_name}"):
		doc.unit_name = f"{room.room_type.split('-')[-1]} {room.room_number}"
	doc.insert(ignore_permissions=True)
	return doc.name


def ensure_whole_property_siu(room_type_name: str) -> str | None:
	"""Create (or return) a whole_property SIU for a Villa room type."""
	rt = frappe.db.get_value(
		"Room Type",
		room_type_name,
		["name", "property", "room_type_name", "room_type_code", "room_category",
		 "base_occupancy", "max_total_occupants", "adults_capacity"],
		as_dict=True,
	)
	if not rt or rt.room_category != "Villa":
		return None

	existing = frappe.db.get_value(
		"Sellable Unit",
		{
			"property": rt.property,
			"room_type": rt.name,
			"unit_kind": "whole_property",
		},
		"name",
	)
	if existing:
		return existing

	unit_name = rt.room_type_name or rt.room_type_code or "Entire Property"
	doc = frappe.get_doc(
		{
			"doctype": "Sellable Unit",
			"property": rt.property,
			"unit_name": unit_name,
			"unit_kind": "whole_property",
			"is_active": 1,
			"room_type": rt.name,
			"competition_group": f"{rt.property}::estate",
			"is_auto_assignable": 0,
			"base_occupancy": rt.base_occupancy or rt.adults_capacity or 2,
			"max_occupants": rt.max_total_occupants or rt.adults_capacity or 0,
		}
	)
	# Link any rooms already under this type (sentinel inventory).
	rooms = frappe.get_all(
		"Room", filters={"room_type": rt.name}, fields=["name"]
	)
	for r in rooms:
		doc.append("physical_rooms", {"room": r.name})
	doc.insert(ignore_permissions=True)

	# Put sibling individual SIUs for the same property into the estate
	# competition group so hybrid lockout works after backfill.
	_align_estate_competition(rt.property)
	return doc.name


def _align_estate_competition(property: str):
	"""If a whole_property SIU exists, pull all individual SIUs on the property
	into the same competition group so hybrid bookings compete."""
	estate = f"{property}::estate"
	has_whole = frappe.db.exists(
		"Sellable Unit",
		{"property": property, "unit_kind": "whole_property", "is_active": 1},
	)
	if not has_whole:
		return
	frappe.db.sql(
		"""
		UPDATE `tabSellable Unit`
		SET competition_group = %s
		WHERE property = %s AND unit_kind = 'individual' AND is_active = 1
		""",
		(estate, property),
	)


def backfill_property(property: str | None = None) -> dict:
	"""Create SIUs for Rooms and Villa room types. Idempotent."""
	room_filters = {"property": property} if property else {}
	rooms = frappe.get_all("Room", filters=room_filters, pluck="name")
	created_rooms = 0
	for name in rooms:
		before = frappe.db.sql(
			"SELECT parent FROM `tabSellable Unit Room` WHERE room=%s LIMIT 1",
			name,
		)
		ensure_individual_siu(name)
		after = frappe.db.sql(
			"SELECT parent FROM `tabSellable Unit Room` WHERE room=%s LIMIT 1",
			name,
		)
		if not before and after:
			created_rooms += 1

	rt_filters = {"room_category": "Villa"}
	if property:
		rt_filters["property"] = property
	villas = frappe.get_all("Room Type", filters=rt_filters, pluck="name")
	created_villas = 0
	for name in villas:
		before = frappe.db.get_value(
			"Sellable Unit",
			{"room_type": name, "unit_kind": "whole_property"},
			"name",
		)
		ensure_whole_property_siu(name)
		after = frappe.db.get_value(
			"Sellable Unit",
			{"room_type": name, "unit_kind": "whole_property"},
			"name",
		)
		if not before and after:
			created_villas += 1

	# Align competition groups for any property that has a whole_property SIU.
	props = (
		[property]
		if property
		else frappe.get_all("Property", pluck="name")
	)
	for p in props:
		_align_estate_competition(p)

	return {
		"individual_sius_created": created_rooms,
		"whole_property_sius_created": created_villas,
	}
