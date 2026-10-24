"""Property onboarding: what guided setup creates for the restaurant side,
and the 'finish setting up' list for everything left to do.

Quick setup makes a property with its region's currency, clock and tax and
nothing else; this list is how the owner comes back to it."""

from __future__ import annotations

import frappe
from frappe import _

from kamra.authz import assert_property_access, require_roles

STATIONS = ("Kitchen", "Tandoor", "Grill", "Fryer", "Bar")
OUTLET_TYPES = ("Restaurant", "Room Service", "Bar", "Spa", "Other")
TILL_KINDS = ("Front Desk", "Restaurant", "Bar", "Spa", "Cash Office", "Other")
MAX_OUTLETS, MAX_TILLS = 20, 30


def create_pos_setup(property: str, pos: dict) -> dict:
	"""Outlets, the stations that print their kitchen tickets, and tills.

	pos = {outlets:[{name,type}], stations:["Kitchen","Bar"],
	       tills:[{name,kind,outlet?}], cash_office: bool}
	Each station gets one print-station printer routed for every outlet, so
	KOTs print by station from day one; bills are set per till later."""
	outlets: list[str] = []
	for o in (pos.get("outlets") or [])[:MAX_OUTLETS]:
		name = (o.get("name") or "").strip()
		if not name:
			continue
		typ = o.get("type") if o.get("type") in OUTLET_TYPES else "Restaurant"
		doc = frappe.get_doc({"doctype": "POS Outlet", "property": property,
		                      "outlet_name": name, "outlet_type": typ}).insert()
		outlets.append(doc.name)
	by_label = {frappe.db.get_value("POS Outlet", n, "outlet_name"): n for n in outlets}

	stations = [s for s in (pos.get("stations") or []) if s in STATIONS]
	printers = 0
	if outlets and stations:
		for st in dict.fromkeys(stations):
			frappe.get_doc({
				"doctype": "Kitchen Printer", "property": property,
				"printer_name": f"{st} printer", "connection": "Print station",
				"prints_kots": 1, "prints_bills": 0,
				"routes": [{"outlet": o, "prep_station": st} for o in outlets],
			}).insert()
			printers += 1

	tills = 0
	if frappe.db.exists("DocType", "Cashier Terminal"):
		specs = list((pos.get("tills") or [])[:MAX_TILLS])
		if pos.get("cash_office"):
			specs.append({"name": "Cash office", "kind": "Cash Office"})
		for t in specs:
			name = (t.get("name") or "").strip()
			if not name:
				continue
			kind = t.get("kind") if t.get("kind") in TILL_KINDS else "Front Desk"
			frappe.get_doc({
				"doctype": "Cashier Terminal", "property": property,
				"terminal_name": name, "kind": kind,
				"outlet": by_label.get(t.get("outlet")) or None,
			}).insert()
			tills += 1
	return {"outlets": len(outlets), "stations": printers, "tills": tills}


def _modules(property: str) -> set[str]:
	from kamra.api import enabled_modules
	return set(enabled_modules(property))


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Hotel Admin", "Kamra Agent")
def setup_checklist(property: str) -> dict:
	"""What is set up and what is still to do, for the Finish setup screen.
	Only items that matter for the modules this property runs."""
	assert_property_access(property)
	prop = frappe.db.get_value(
		"Property", property,
		["country", "currency", "gstin", "property_kind", "booking_engine_enabled", "setup_wants"],
		as_dict=True)
	mods = _modules(property)
	wants = set((prop.setup_wants or "").split(","))
	n = lambda dt, **f: frappe.db.count(dt, {"property": property, **f})  # noqa: E731
	is_str = prop.property_kind == "Short Term Rental"
	items = []

	def add(key, label, done, detail, to, doc=None):
		items.append({"key": key, "label": label, "done": bool(done), "detail": detail,
		              "to": to, "doc": doc})

	add("region", _("Region, currency and tax"), prop.country and prop.currency,
	    _("Set from the country you chose."), "/settings/general", "country-setup")
	if prop.country:
		add("taxid", _("Tax registration number"), bool(prop.gstin),
		    _("Printed on invoices. Add it when you have it."), "/settings/general", "country-setup")
	add("room_types", _("Room types and rates"), n("Room Type") > 0,
	    _("What you sell and the base rate (BAR) for each."), "/room-types", "revenue")
	if not is_str:
		add("rooms", _("Rooms"), n("Room") > 0, _("The numbered rooms the front desk assigns."),
		    "/rooms", "front-desk")
	if "booking-engine" in mods:
		add("booking_engine", _("Online booking page"), bool(prop.booking_engine_enabled),
		    _("Turn it on, add photos and policies."), "/booking-settings/profile", "booking-engine")
	if "channel-manager" in wants or frappe.db.exists("Channel Manager Connection", {"property": property}):
		add("channel", _("Channel manager"),
		    frappe.db.exists("Channel Manager Connection", {"property": property, "active": 1}),
		    _("Connect your channel manager so OTA bookings arrive and rates and availability go out."),
		    "/channel-manager", "channel-manager")
	if "fnb" in mods:
		add("outlets", _("Restaurant outlets"), n("POS Outlet") > 0,
		    _("Each place that sells food or drink."), "/outlets", "fnb")
		add("menu", _("Menu"), n("Menu Item") > 0, _("Dishes and prices per outlet."), "/menu-items", "fnb")
		add("printers", _("Kitchen printers"), n("Kitchen Printer") > 0,
		    _("Which station prints which tickets, and where bills print."), "/printers", "fnb")
	if "finance" in mods or "fnb" in mods:
		if frappe.db.exists("DocType", "Cashier Terminal"):
			add("tills", _("Tills"), n("Cashier Terminal") > 0,
			    _("Name each till, tie it to an outlet. Without any, everyone uses the Default till."),
			    "/cashier/board", "billing")
	users = frappe.db.sql(
		"""SELECT COUNT(DISTINCT parent) FROM `tabHas Role`
		   WHERE parenttype='User' AND role IN ('Front Desk','Housekeeping','Finance','Hotel Admin')""")[0][0]
	add("staff", _("Your team"), users > 1, _("Invite staff and give each the right role."),
	    "/settings/staff", "settings")
	done = sum(1 for i in items if i["done"])
	return {"items": items, "done": done, "total": len(items),
	        "percent": round(100 * done / len(items)) if items else 100}
