"""Central Reservation System - work across the whole chain.

`crs_search` looks for a room across every property the signed-in user may
access and returns what's available where, with live rates, so the front
desk can place a guest at whichever hotel has space. The booking itself
still goes through create_booking against the chosen property.

`permitted_properties` / `assert_property_access` are the chain's access
guard: endpoints that take a `property` argument can no longer be pointed
at a hotel the user isn't allowed to touch.
"""

import frappe
from frappe.utils import date_diff

from kamra.authz import require_roles


def permitted_properties() -> set[str]:
	"""The set of property names the current user may work with (native
	Frappe User Permissions decide this via my_properties)."""
	from kamra.api import my_properties
	return {p["name"] for p in my_properties()}


def assert_property_access(property: str):
	"""Guard: refuse an action aimed at a property the user isn't permitted
	for. A no-op for users with no property restriction (they see all)."""
	from kamra.authz import assert_property_access as _guard
	_guard(property)


@frappe.whitelist()
@require_roles("Front Desk", "Revenue Manager", "Hotel Admin", "Kamra Agent")
def crs_search(check_in_date: str, check_out_date: str,
               adults: int = 2, children: int = 0):
	"""Find a room across the chain: for every property the user can access,
	the room types with space for these dates and their all-in rate."""
	from kamra.api import available_rooms
	from kamra.pricing import quote

	nights = max(1, date_diff(check_out_date, check_in_date))
	results = []
	for prop in sorted(permitted_properties()):
		rts = frappe.get_all(
			"Room Type",
			filters={"property": prop, "disabled": 0},
			fields=["name", "room_type_name", "base_price",
			        "adults_capacity", "children_capacity"],
			order_by="base_price asc")
		room_types = []
		for rt in rts:
			# capacity gate: skip a type that can't sleep the party
			if rt.adults_capacity and int(adults) > rt.adults_capacity:
				continue
			free = available_rooms(prop, rt.name, check_in_date, check_out_date)
			if not free:
				continue
			try:
				q = quote(prop, rt.name, check_in_date, check_out_date,
				          int(adults), int(children))
			except Exception:
				continue
			total = q.get("amount_after_tax", 0)
			room_types.append({
				"room_type": rt.name,
				"room_type_name": rt.room_type_name,
				"available": len(free),
				"adults_capacity": rt.adults_capacity,
				"children_capacity": rt.children_capacity,
				"total": round(total, 0),
				"per_night": round(total / nights, 0) if nights else total,
			})
		if room_types:
			p = frappe.db.get_value(
				"Property", prop, ["property_name", "city"], as_dict=True)
			results.append({
				"property": prop,
				"property_name": p.property_name,
				"city": p.city,
				"available_rooms": sum(r["available"] for r in room_types),
				"from_rate": min(r["per_night"] for r in room_types),
				"room_types": room_types,
			})
	# cheapest-entry-point first
	results.sort(key=lambda r: r["from_rate"])
	return {
		"check_in_date": check_in_date,
		"check_out_date": check_out_date,
		"nights": nights,
		"adults": int(adults),
		"children": int(children),
		"properties": results,
	}
