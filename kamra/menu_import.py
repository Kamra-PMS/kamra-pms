"""Bulk menu upload - move a restaurant's price list in from a spreadsheet
instead of typing every dish by hand.

Mirrors the booking importer (kamra/migrate.py): the mapper recognises the
header names people actually use (item/dish/product, price/rate/mrp,
veg/non-veg...), `preview_menu_import` shows exactly what would happen -
mapping, issues, counts - before `run_menu_import` writes anything, and the
run upserts by (property, outlet, item_name) so re-importing a corrected
file updates prices instead of duplicating the menu.

Outlet comes from an `outlet` column when the file has one (multi-outlet
exports), otherwise from the outlet picked in the UI.
"""

import re

import frappe
from frappe import _

from kamra.authz import require_roles
from kamra.migrate import _norm, _parse_csv

# Menu Item is written by Finance / Hotel Admin / System Manager (Front Desk
# is read-only on the doctype) - the importer matches that.
MENU_ROLES = ("Finance",)

# who a header column really is, whatever the spreadsheet called it
SYNONYMS = {
	"item_name": ["item", "item name", "name", "dish", "product", "menu item",
	              "item_name", "particulars", "food item"],
	"category": ["category", "section", "group", "course", "menu category",
	             "sub category", "subcategory"],
	"price": ["price", "rate", "amount", "mrp", "selling price", "cost",
	          "price inr", "price (inr)", "unit price"],
	"is_veg": ["veg", "is veg", "veg/non-veg", "veg non veg", "food type",
	           "veg or non veg", "dietary", "type"],
	"is_alcohol": ["alcohol", "is alcohol", "liquor", "bar item", "alcoholic"],
	"available": ["available", "is available", "active", "in stock",
	              "enabled", "status"],
	"prep_station": ["station", "prep station", "kitchen/bar", "prepared at",
	                 "prep"],
	"description": ["description", "notes", "details", "about"],
	"outlet": ["outlet", "restaurant", "outlet name", "venue"],
}

REQUIRED = ("item_name", "price")

TRUE = {"1", "y", "yes", "true", "t", "available", "active", "in stock",
        "enabled", "on"}
FALSE = {"0", "n", "no", "false", "f", "unavailable", "inactive",
         "out of stock", "disabled", "off"}
VEG_TRUE = {"veg", "vegetarian", "v", "pure veg", "green"}
VEG_FALSE = {"non veg", "nonveg", "non-veg", "nv", "chicken", "mutton",
             "egg", "fish", "meat", "eggetarian"}

TEMPLATE_HEADERS = ["item_name", "category", "price", "veg", "alcohol",
                    "available", "station", "description"]


def _map_headers(headers):
	mapping, used = {}, set()
	for canon, alts in SYNONYMS.items():
		keys = {_norm(a) for a in alts}
		for h in headers:
			if h not in used and _norm(h) in keys:
				mapping[canon] = h
				used.add(h)
				break
	return mapping


def _in(val, bag):
	return _norm(val) in {_norm(x) for x in bag}


def _flag(val, default=None):
	if not _norm(val):
		return default
	if _in(val, TRUE):
		return 1
	if _in(val, FALSE):
		return 0
	return default


def _veg(val, default=0):
	if not _norm(val):
		return default
	if _in(val, VEG_TRUE):
		return 1
	if _in(val, VEG_FALSE):
		return 0
	return _flag(val, default)


def _price(val):
	"""₹1,299.00 / 1299 / '1 299' -> 1299.0; anything unusable -> None."""
	s = re.sub(r"[^\d.]", "", str(val or ""))
	if not s or s.count(".") > 1:
		return None
	try:
		p = float(s)
	except ValueError:
		return None
	return p if p > 0 else None


def _outlet_resolver(property: str):
	rows = frappe.get_all(
		"POS Outlet", filters={"property": property, "disabled": 0},
		fields=["name", "outlet_name"])

	def resolve(val):
		key = _norm(val)
		if not key:
			return None
		for o in rows:
			if key in (_norm(o.outlet_name), _norm(o.name)):
				return o.name
		return None

	return resolve, [{"name": o.name, "outlet_name": o.outlet_name}
	                 for o in rows]


def _normalize_menu(property: str, csv_text: str, outlet: str | None = None):
	headers, raw = _parse_csv(csv_text)
	mapping = _map_headers(headers)
	missing = [f for f in REQUIRED if f not in mapping]
	resolve_outlet, outlets = _outlet_resolver(property)
	default_outlet = resolve_outlet(outlet) if outlet else None

	if missing:
		return headers, mapping, [], [{
			"row": 0, "item": "",
			"error": "Couldn't find column(s) for: " + ", ".join(missing)
			         + ". Rename the headers or use the template.",
		}], outlets

	rows, issues = [], []
	for i, r in enumerate(raw, start=1):
		def get(f):
			return r.get(mapping.get(f, ""), "")

		item = (get("item_name") or "").strip()
		price = _price(get("price"))
		row_outlet = (resolve_outlet(get("outlet")) if "outlet" in mapping
		              else None) or default_outlet

		problems = []
		if not item:
			problems.append("no item name")
		if price is None:
			problems.append("missing or invalid price")
		if not row_outlet:
			problems.append("no outlet - pick one above, or add an "
			                "'outlet' column")
		if problems:
			issues.append({"row": i, "item": item or "(blank)",
			               "error": ", ".join(problems)})
			continue

		alcohol = _flag(get("is_alcohol"), 0)
		station = get("prep_station")
		if _norm(station) in ("bar",):
			prep = "Bar"
		elif _norm(station) in ("kitchen",):
			prep = "Kitchen"
		else:
			prep = "Bar" if alcohol else "Kitchen"

		rows.append({
			"row": i,
			"item_name": item[:140],
			"outlet": row_outlet,
			"category": (get("category") or "").strip()[:140] or None,
			"price": price,
			"is_veg": _veg(get("is_veg"), 0),
			"is_alcohol": alcohol,
			"available": _flag(get("available"), 1),
			"prep_station": prep,
			"description": (get("description") or "").strip()[:500] or None,
			"existing": frappe.db.get_value("Menu Item", {
				"property": property, "outlet": row_outlet,
				"item_name": item[:140]}, "name"),
		})
	return headers, mapping, rows, issues, outlets


@frappe.whitelist(methods=["POST"])
@require_roles(*MENU_ROLES)
def preview_menu_import(property: str, csv_text: str,
                        outlet: str | None = None):
	"""Dry run: how the columns map, what would be created vs updated, and
	every row that would be skipped. Nothing is written."""
	headers, mapping, rows, issues, outlets = _normalize_menu(
		property, csv_text, outlet)
	return {
		"headers": headers,
		"mapping": mapping,
		"unmapped": [h for h in headers if h not in mapping.values()],
		"ok": len(rows),
		"skipped": len(issues),
		"new_count": sum(1 for r in rows if not r["existing"]),
		"update_count": sum(1 for r in rows if r["existing"]),
		"issues": issues[:25],
		"sample": rows[:10],
		"outlets": outlets,
	}


@frappe.whitelist(methods=["POST"])
@require_roles(*MENU_ROLES)
def run_menu_import(property: str, csv_text: str, outlet: str | None = None,
                    update_existing: int = 1):
	"""Import the file. Upserts by (property, outlet, item_name): a dish
	already on that outlet's menu is updated (price/flags), never duplicated.
	One bad row never aborts the batch."""
	_headers, _mapping, rows, issues, _outlets = _normalize_menu(
		property, csv_text, outlet)

	created, updated, skipped = 0, 0, 0
	errors = list(issues)
	for r in rows:
		payload = {
			"category": r["category"], "price": r["price"],
			"is_veg": r["is_veg"], "is_alcohol": r["is_alcohol"],
			"available": r["available"], "prep_station": r["prep_station"],
		}
		if r["description"]:
			payload["description"] = r["description"]
		try:
			if r["existing"]:
				if not int(update_existing or 0):
					skipped += 1
					continue
				doc = frappe.get_doc("Menu Item", r["existing"])
				doc.update(payload)
				doc.save()
				updated += 1
			else:
				frappe.get_doc({
					"doctype": "Menu Item", "property": property,
					"outlet": r["outlet"], "item_name": r["item_name"],
					**payload,
				}).insert()
				created += 1
		except Exception as e:
			errors.append({"row": r["row"], "item": r["item_name"],
			               "error": str(e)[:160]})
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional

	from kamra.savings import log_action
	log_action(
		action_type="menu_import",
		reference_doctype="POS Outlet",
		reference_name=outlet,
		property=property,
		minutes_saved=max(1, (created + updated) * 0.5),
		rationale=f"Bulk menu upload: {created} new, {updated} updated",
		agent_name="Menu Import",
		channel="API",
	)
	return {"created": created, "updated": updated, "skipped": skipped,
	        "errors": errors[:25]}


@frappe.whitelist()
@require_roles(*MENU_ROLES)
def menu_template():
	"""The CSV headers + one sample row, so the file starts out right."""
	return {
		"headers": TEMPLATE_HEADERS,
		"sample": [
			["Paneer Tikka", "Starters", "320", "veg", "no", "yes",
			 "Kitchen", "Char-grilled cottage cheese"],
			["Chicken Biryani", "Mains", "380", "non-veg", "no", "yes",
			 "Kitchen", ""],
			["Kingfisher Draught", "Beverages", "250", "", "yes", "yes",
			 "Bar", ""],
		],
	}
