"""One Floor per distinct typed Room.floor of each property, in natural
order (numbers by value, then the rest alphabetically). Safe to rerun."""

import frappe


def execute():
	frappe.reload_doc("kamra", "doctype", "floor")
	frappe.reload_doc("kamra", "doctype", "room")
	from kamra.floors import floor_number, natural_key

	seen = frappe.db.sql(
		"select distinct property, floor from `tabRoom` "
		"where ifnull(floor, '') != '' and ifnull(property, '') != ''")
	by_prop = {}
	for prop, floor in seen:
		by_prop.setdefault(prop, set()).add(floor.strip())
	for prop, names in by_prop.items():
		have = set(frappe.get_all("Floor", filters={"property": prop}, pluck="floor_name"))
		others = 0
		for name in sorted(names, key=natural_key):
			n = floor_number(name)
			if n is None:
				others += 1
			if name in have or not name:
				continue
			frappe.get_doc({
				"doctype": "Floor", "property": prop, "floor_name": name,
				"sort_order": n * 10 if n is not None else 10000 + others * 10,
			}).insert(ignore_permissions=True)
