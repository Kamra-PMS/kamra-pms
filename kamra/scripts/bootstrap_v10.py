"""Schema v10 — POS-lite (outlets, menu, orders→folio) + Experiences.

Run via bench console:
    from kamra.scripts.bootstrap_v10 import execute; execute()
"""

import frappe

from kamra.scripts.bootstrap_schema import f
from kamra.scripts.bootstrap_v2 import _dt
from kamra.scripts.fix_perms_fields import _grant

ROLES_RW = ("System Manager", "Hotel Admin", "Front Desk", "Kamra Agent")


def execute():
	_dt("POS Outlet", [
		f("property", "Link", options="Property", reqd=1),
		f("outlet_name", "Data", reqd=1, in_list_view=1),
		f("outlet_type", "Select", in_list_view=1,
		  options="Restaurant\nRoom Service\nBar\nSpa\nOther",
		  default="Restaurant"),
		f("column_break_a", "Column Break"),
		f("gst_rate", "Percent", label="GST %", default="5"),
		f("disabled", "Check"),
	], autoname="format:{property}-{outlet_name}", naming_rule="Expression",
	   title_field="outlet_name")

	_dt("Menu Item", [
		f("property", "Link", options="Property", reqd=1),
		f("outlet", "Link", options="POS Outlet", reqd=1, in_list_view=1),
		f("item_name", "Data", reqd=1, in_list_view=1),
		f("column_break_a", "Column Break"),
		f("category", "Data", in_list_view=1),
		f("price", "Currency", reqd=1, in_list_view=1),
		f("is_veg", "Check", label="Veg"),
		f("available", "Check", default="1", in_list_view=1),
	], naming_rule="Expression", autoname="format:MI-{#####}",
	   title_field="item_name")

	_dt("POS Order Item", [
		f("menu_item", "Link", options="Menu Item", reqd=1, in_list_view=1),
		f("item_name", "Data", fetch_from="menu_item.item_name",
		  in_list_view=1),
		f("qty", "Float", default="1", in_list_view=1),
		f("rate", "Currency", fetch_from="menu_item.price", in_list_view=1),
		f("amount", "Currency", read_only=1, in_list_view=1),
	], istable=1)

	_dt("POS Order", [
		f("property", "Link", options="Property", reqd=1),
		f("outlet", "Link", options="POS Outlet", reqd=1, in_list_view=1),
		f("column_break_a", "Column Break"),
		f("status", "Select", in_list_view=1, in_standard_filter=1,
		  options="Placed\nPreparing\nDelivered\nCancelled",
		  default="Placed"),
		f("source", "Select", options="Manual\nAI Agent\nQR\nPhone",
		  default="Manual"),
		f("sb_who", "Section Break", label="Guest / Room"),
		f("room", "Link", options="Room", in_list_view=1),
		f("reservation", "Link", options="Reservation",
		  description="Set to post the order to the guest folio on delivery"),
		f("sb_items", "Section Break", label="Items"),
		f("items", "Table", options="POS Order Item"),
		f("sb_totals", "Section Break", label="Totals"),
		f("order_total", "Currency", read_only=1, in_list_view=1),
		f("column_break_b", "Column Break"),
		f("posted_to_folio", "Check", read_only=1),
		f("notes", "Small Text"),
	], naming_rule="Expression", autoname="format:ORD-{YYYY}-{#####}")

	_dt("Experience", [
		f("property", "Link", options="Property", reqd=1),
		f("experience_name", "Data", reqd=1, in_list_view=1),
		f("category", "Select", in_list_view=1,
		  options="Spa\nTour\nDining\nActivity\nTransport\nOther"),
		f("column_break_a", "Column Break"),
		f("price", "Currency", in_list_view=1,
		  description="Per person; 0 = price on request"),
		f("duration", "Data", description="e.g. 90 min, half day"),
		f("gst_rate", "Percent", label="GST %", default="18"),
		f("sb_public", "Section Break", label="Showcase"),
		f("description", "Small Text"),
		f("image_url", "Data"),
		f("show_on_booking_page", "Check", default="1"),
		f("disabled", "Check"),
	], autoname="format:{property}-{experience_name}",
	   naming_rule="Expression", title_field="experience_name")

	for doctype in ("POS Outlet", "Menu Item", "POS Order", "Experience"):
		for role in ROLES_RW:
			write = 0 if (role == "Kamra Agent" and doctype != "POS Order") else 1
			_grant(doctype, role, 1, write, write,
			       delete=1 if role in ("System Manager", "Hotel Admin") else 0)
		_grant(doctype, "Revenue Manager", 1, 1, 1)
		_grant(doctype, "Housekeeping", 1, 0, 0)

	frappe.db.commit()
	print("Kamra v10 schema (POS + experiences) ready.")
