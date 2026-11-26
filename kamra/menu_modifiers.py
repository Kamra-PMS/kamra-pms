"""Choices on a dish: the groups the captain is asked about when a dish goes on
the bill - milk, size, extras, how it is cooked.

A GROUP (Menu Modifier Group) belongs to one outlet and is offered by the
dishes that list it. It says whether a choice is compulsory, whether more than
one may be picked and how many. Its CHOICES (Menu Modifier Option) each add a
price, and may take ingredients off the stock when the dish is fired, like a
recipe line does (see kamra.inventory).

Three decisions run through the rest of the POS, so they are written down here:

1. THE SERVER PRICES AND JUDGES THE CHOICES. The till sends only the ids it
   ticked. `resolve()` checks them against the groups the dish really offers,
   enforces required / one-or-several / the limit, and prices them from the
   database, exactly as `_load_items` already prices the dish itself.

2. A LINE KEEPS WHAT WAS SOLD. The choices go onto the POS Order Item as a JSON
   snapshot (group, choice, price at that moment) and the line's `rate` is the
   dish's price PLUS the choices. Renaming a choice, changing its price or
   deleting the group later never touches a bill that is already written, and
   everything that already reads qty x rate (bill, totals, voids, dashboard,
   room posting) stays right without knowing choices exist.

3. A GROUP WITH NO CHOICES IS NOT ASKED. A required group nobody can answer
   would stop the dish being sold, so it is left out of the till's menu and
   the checks until it has a choice.
"""

import json

import frappe
from frappe import _
from frappe.utils import flt

from kamra.authz import require_perm

MAX_OPTIONS = 60  # a sanity cap on one group's choices, not a business rule


# ------------------------------------------------------------------ reading

def groups_for_items(menu_items) -> dict:
	"""menu item -> the groups it offers, in till order (the group's Order,
	then its name), each with its choices. Groups without a choice are left
	out. One round of queries for the whole list: the till loads a whole menu
	through this."""
	ids = [m for m in dict.fromkeys(menu_items or []) if m]
	if not ids:
		return {}
	links = frappe.get_all(
		"Menu Item Modifier Group",
		filters={"parent": ["in", ids], "parenttype": "Menu Item"},
		fields=["parent", "modifier_group"], order_by="idx asc")
	if not links:
		return {}
	wanted = list({lk.modifier_group for lk in links})
	groups = {g.name: g for g in frappe.get_all(
		"Menu Modifier Group", filters={"name": ["in", wanted]},
		fields=["name", "group_name", "outlet", "required", "multi",
		        "max_choices", "sort_order"])}
	options: dict[str, list] = {}
	for o in frappe.get_all(
			"Menu Modifier Option", filters={"modifier_group": ["in", wanted]},
			fields=["name", "modifier_group", "option_name", "price"],
			order_by="sort_order asc, creation asc"):
		options.setdefault(o.modifier_group, []).append({
			"name": o.name, "option_name": o.option_name, "price": flt(o.price)})
	out: dict[str, list] = {}
	for lk in links:
		g = groups.get(lk.modifier_group)
		if not g or not options.get(g.name):
			continue
		out.setdefault(lk.parent, []).append({
			"name": g.name, "group_name": g.group_name, "outlet": g.outlet,
			"required": 1 if g.required else 0, "multi": 1 if g.multi else 0,
			"max_choices": int(g.max_choices or 0),
			"sort_order": int(g.sort_order or 0), "options": options[g.name]})
	for lst in out.values():
		lst.sort(key=lambda g: (g["sort_order"], g["group_name"].lower()))
	return out


def menu_payload(menu_items) -> tuple[list, dict]:
	"""What the till's menu needs: every group once, and which groups each dish
	offers (ids, in till order). Sent apart so a "Milk" shared by forty drinks
	travels once."""
	per_item = groups_for_items(menu_items)
	groups: dict[str, dict] = {}
	for lst in per_item.values():
		for g in lst:
			groups.setdefault(g["name"], {k: v for k, v in g.items() if k != "outlet"})
	return list(groups.values()), {
		item: [g["name"] for g in lst] for item, lst in per_item.items()}


# ----------------------------------------------------------------- the sale

def _ids(raw) -> list[str]:
	"""The ticked choice ids as the till or an agent sent them: a list, or the
	same list as JSON text. Repeats collapse - a choice is on or off."""
	if isinstance(raw, str):
		raw = frappe.parse_json(raw) if raw.strip().startswith("[") else \
			[p for p in (x.strip() for x in raw.split(",")) if p]
	return list(dict.fromkeys(str(x) for x in (raw or []) if x))


def resolve(item_name: str, offered: list, option_ids) -> tuple[list, float]:
	"""Judge the choices picked for one dish and price them. `offered` is the
	dish's groups from `groups_for_items`, which the caller looks up once for a
	whole order.

	Returns ([{"group", "option", "name", "price"}], what_they_add_to_one).
	Raises for a choice the dish does not offer, a compulsory group left
	unanswered, a second pick in a one-only group, or more than the limit. The
	words name the dish and the group, and the choices with their ids, so a
	person or an agent can see what to send instead."""
	chosen = _ids(option_ids)
	known = {o["name"] for g in offered for o in g["options"]}
	if [c for c in chosen if c not in known]:
		frappe.throw(_("{0} does not offer that choice.").format(item_name))
	snapshot, total = [], 0.0
	for g in offered:
		picked = [o for o in g["options"] if o["name"] in chosen]
		listing = ", ".join(f"{o['option_name']} ({o['name']})" for o in g["options"])
		if g["required"] and not picked:
			frappe.throw(_("{0}: choose {1}. Choices: {2}.")
			             .format(item_name, g["group_name"], listing))
		if not g["multi"] and len(picked) > 1:
			frappe.throw(_("{0}: {1} takes one choice only.")
			             .format(item_name, g["group_name"]))
		if g["multi"] and g["max_choices"] and len(picked) > g["max_choices"]:
			frappe.throw(_("{0}: {1} takes at most {2} choices.")
			             .format(item_name, g["group_name"], g["max_choices"]))
		for o in picked:
			snapshot.append({"group": g["group_name"], "option": o["name"],
			                 "name": o["option_name"], "price": o["price"]})
			total += o["price"]
	# prices count as they are stored: a currency may have 3 decimals, and a price
	# kept to 6 lets a tax added on top land on a round figure. So the sum is not
	# rounded to money, only cleared of float noise at the column's 9 places.
	return snapshot, flt(total, 9)


def dump(snapshot: list) -> str | None:
	return json.dumps(snapshot, separators=(",", ":")) if snapshot else None


def load(raw) -> list:
	"""A line's snapshot back as a list. Anything unreadable is no choices -
	a bill must always open."""
	if not raw:
		return []
	try:
		rows = json.loads(raw) if isinstance(raw, str) else raw
	except ValueError:
		return []
	return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def names_of(raw) -> list[str]:
	"""The choice names on a line, in the order they were picked: what the
	kitchen ticket and the bill print under the dish."""
	return [r.get("name") for r in load(raw) if r.get("name")]


def option_ids_of(raw) -> list[str]:
	return [r["option"] for r in load(raw) if r.get("option")]


# ------------------------------------------------------------------ editing

def _json(raw):
	return frappe.parse_json(raw) if isinstance(raw, str) else raw


@frappe.whitelist()
@require_perm("Menu Item", "edit_menu")
def modifier_overview(property: str):
	"""Everything the Choices editor shows: each group with its choices (and
	the ingredients each takes), the dishes that offer it, and the property's
	dishes and outlets to pick from."""
	outlets = frappe.get_all(
		"POS Outlet", filters={"property": property, "disabled": 0},
		fields=["name", "outlet_name"], order_by="outlet_name")
	dishes = frappe.get_all(
		"Menu Item", filters={"property": property},
		fields=["name", "item_name", "outlet", "category"],
		order_by="outlet asc, category asc, item_name asc")
	groups = frappe.get_all(
		"Menu Modifier Group", filters={"property": property},
		fields=["name", "group_name", "outlet", "required", "multi",
		        "max_choices", "sort_order"],
		order_by="outlet asc, sort_order asc, group_name asc")
	if not groups:
		return {"groups": [], "dishes": dishes, "outlets": outlets}
	names = [g.name for g in groups]
	options = frappe.get_all(
		"Menu Modifier Option", filters={"modifier_group": ["in", names]},
		fields=["name", "modifier_group", "option_name", "price"],
		order_by="sort_order asc, creation asc")
	lines: dict[str, list] = {}
	if options:
		for r in frappe.get_all(
				"Menu Item Ingredient",
				filters={"parent": ["in", [o.name for o in options]],
				         "parenttype": "Menu Modifier Option"},
				fields=["parent", "ingredient", "qty"], order_by="idx asc"):
			meta = frappe.db.get_value("Ingredient", r.ingredient,
			                           ["ingredient_name", "uom"], as_dict=True) or {}
			lines.setdefault(r.parent, []).append({
				"ingredient": r.ingredient, "qty": r.qty,
				"ingredient_name": meta.get("ingredient_name"),
				"uom": meta.get("uom")})
	by_group: dict[str, list] = {}
	for o in options:
		by_group.setdefault(o.modifier_group, []).append({
			"name": o.name, "option_name": o.option_name, "price": flt(o.price),
			"ingredients": lines.get(o.name, [])})
	on_dishes: dict[str, list] = {}
	for lk in frappe.get_all(
			"Menu Item Modifier Group",
			filters={"modifier_group": ["in", names], "parenttype": "Menu Item"},
			fields=["parent", "modifier_group"]):
		on_dishes.setdefault(lk.modifier_group, []).append(lk.parent)
	outlet_name = {o.name: o.outlet_name for o in outlets}
	for g in groups:
		g["outlet_name"] = outlet_name.get(g.outlet)
		g["options"] = by_group.get(g.name, [])
		g["items"] = on_dishes.get(g.name, [])
	return {"groups": groups, "dishes": dishes, "outlets": outlets}


def _clean_options(options, property: str) -> list[dict]:
	"""The editor's choices, judged before anything is written."""
	rows = _json(options) or []
	if not isinstance(rows, list) or not rows:
		frappe.throw(_("Add at least one choice."))
	if len(rows) > MAX_OPTIONS:
		frappe.throw(_("A group takes {0} choices at most.").format(MAX_OPTIONS))
	seen, clean = set(), []
	for r in rows:
		label = (r.get("option_name") or "").strip()
		if not label:
			frappe.throw(_("Every choice needs a name."))
		if label.lower() in seen:
			frappe.throw(_("{0} is in this group twice.").format(label))
		seen.add(label.lower())
		price = flt(r.get("price"))
		if price < 0:
			frappe.throw(_("{0}: a choice cannot take money off the price.").format(label))
		used, taken = [], set()
		for line in r.get("ingredients") or []:
			ing = line.get("ingredient")
			if not ing:
				continue
			qty = flt(line.get("qty"))
			if qty <= 0:
				frappe.throw(_("{0}: every ingredient needs a quantity above zero.").format(label))
			if ing in taken:
				frappe.throw(_("{0}: {1} is listed twice.").format(label, ing))
			taken.add(ing)
			if frappe.db.get_value("Ingredient", ing, "property") != property:
				frappe.throw(_("{0} belongs to another property.").format(ing))
			used.append({"ingredient": ing, "qty": qty})
		clean.append({"name": r.get("name") or None, "option_name": label,
		              "price": price, "ingredients": used})
	return clean


@frappe.whitelist(methods=["POST"])
@require_perm("Menu Item", "edit_menu")
def save_modifier_group(outlet: str, group_name: str, options, items=None,
                        required=0, multi=0, max_choices=0, sort_order=0,
                        name: str | None = None):
	"""Create or change one group: its rules, its choices and the dishes that
	offer it, in one go. `options` replaces the choices (a choice sent with its
	`name` keeps its identity and its stock lines; one no longer sent is
	removed). `items` replaces the dishes that offer the group; leave it out to
	keep them as they are."""
	property = frappe.db.get_value("POS Outlet", outlet, "property")
	if not property:
		frappe.throw(_("Outlet not found."))
	clean = _clean_options(options, property)
	if name:
		group = frappe.get_doc("Menu Modifier Group", name)
		if group.outlet != outlet:
			frappe.throw(_("A group cannot move to another outlet."))
	else:
		group = frappe.new_doc("Menu Modifier Group")
		group.update({"property": property, "outlet": outlet})
	group.update({
		"group_name": group_name, "required": 1 if int(required or 0) else 0,
		"multi": 1 if int(multi or 0) else 0,
		"max_choices": int(max_choices or 0), "sort_order": int(sort_order or 0)})
	dishes = None
	if items is not None:
		dishes = list(dict.fromkeys(_json(items) or []))
		for it in dishes:
			if frappe.db.get_value("Menu Item", it, "outlet") != outlet:
				frappe.throw(_("{0} is not a dish of this outlet.").format(it))
	group.save(ignore_permissions=True)

	existing = {o.name: o for o in frappe.get_all(
		"Menu Modifier Option", filters={"modifier_group": group.name},
		fields=["name"])}
	kept = set()
	for i, row in enumerate(clean):
		if row["name"] in existing:
			opt = frappe.get_doc("Menu Modifier Option", row["name"])
		else:
			opt = frappe.new_doc("Menu Modifier Option")
			opt.update({"property": property, "modifier_group": group.name})
		opt.update({"option_name": row["option_name"], "price": row["price"],
		            "sort_order": i})
		opt.set("ingredients", row["ingredients"])
		opt.save(ignore_permissions=True)
		kept.add(opt.name)
	for gone in set(existing) - kept:
		frappe.delete_doc("Menu Modifier Option", gone,
		                  ignore_permissions=True, force=True)

	if dishes is not None:
		_set_dishes(group.name, dishes)
	return {"ok": True, "name": group.name, "options": len(clean),
	        "dishes": len(dishes) if dishes is not None else None}


def _set_dishes(group: str, dishes: list) -> None:
	"""Make exactly these dishes offer the group. Each changed dish is saved as
	a whole, so its history and the caches that read it stay right."""
	have = {r.parent for r in frappe.get_all(
		"Menu Item Modifier Group",
		filters={"modifier_group": group, "parenttype": "Menu Item"},
		fields=["parent"])}
	for it in set(dishes) - have:
		doc = frappe.get_doc("Menu Item", it)
		doc.append("modifier_groups", {"modifier_group": group})
		doc.save(ignore_permissions=True)
	for it in have - set(dishes):
		_drop_from(it, group)


def _drop_from(menu_item: str, group: str) -> None:
	doc = frappe.get_doc("Menu Item", menu_item)
	doc.set("modifier_groups", [r for r in doc.modifier_groups
	                            if r.modifier_group != group])
	doc.save(ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
@require_perm("Menu Item", "edit_menu", scope={"name": "Menu Modifier Group"})
def delete_modifier_group(name: str):
	"""Remove a group, its choices, and its place on every dish. Bills already
	written keep the choices they sold (they hold their own copy)."""
	if not frappe.db.exists("Menu Modifier Group", name):
		frappe.throw(_("Group not found."))
	dishes = [r.parent for r in frappe.get_all(
		"Menu Item Modifier Group",
		filters={"modifier_group": name, "parenttype": "Menu Item"},
		fields=["parent"])]
	for it in dishes:
		_drop_from(it, name)
	frappe.delete_doc("Menu Modifier Group", name, ignore_permissions=True)
	return {"ok": True, "dishes": len(dishes)}
