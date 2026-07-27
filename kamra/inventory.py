"""Kitchen stock: what a dish consumes, and what the outlet has left.

Three ideas hold this module together. Each looks like a bug until you know
why it is there, so each is spelled out where it lives:

1. HEAT IS IRREVERSIBLE. Ingredients leave the shelf when the chef starts
   cooking (fire_kot), not when the bill is paid. Nothing downstream ever
   puts them back - not a void, not a cancel, not a recall. A line voided
   after firing was cooked and binned: that is wastage, not a reversal.
   See the reversal table in consume_for_lines().

2. A SHORT COUNT NEVER BLOCKS SERVICE. If the numbers say the paneer ran
   out, the chef still has paneer in their hand and the ticket still fires.
   The balance goes negative and says so loudly. Negative means "this count
   is stale, go recount" - it is the module admitting it does not know
   something, which is the most useful thing it can do. Do NOT clamp it.

3. THE RECIPE IS A LIE, BY 5-15%. A chef's hand is not a scale. Theoretical
   consumption always drifts from actual, which is exactly why adjust_stock()
   and last_counted_at exist. The honest claim is "here is what you SHOULD
   have; go count and tell me what you DO."

Permissions: consume_for_lines() runs under a captain's session, which cannot
write Ingredient Stock or Stock Ledger Entry by design - only Finance can move
stock deliberately. The writes in _apply_move() therefore use
ignore_permissions / db.set_value. That is intentional, not an oversight: the
authorization for consumption is the POS_ROLES gate on fire_kot, not doctype
perms on the ledger. authz.py's own docstring makes the same point.
"""

import uuid

import frappe
from frappe import _

from kamra.authz import require_roles

# Who may look at stock, and who may move it. Chefs never appear here: they
# consume implicitly through fire_kot (already gated on POS_ROLES), because
# consumption is a byproduct of service, not an inventory action. Receiving
# and counting are money - a goods-in is an asset movement, a stock take is a
# P&L event - so they sit with Finance (require_roles widens that to admins).
INVENTORY_READ = ("Front Desk", "Finance", "Kamra Agent", "Hotel Admin")
INVENTORY_WRITE = ("Finance",)

STATUS_OK, STATUS_LOW, STATUS_OUT, STATUS_NEGATIVE = "OK", "LOW", "OUT", "NEGATIVE"


def _status(qty: float, par: float) -> str:
	"""Derived on read, never stored: a stored status would need recomputing
	on every move AND every par edit, and would drift the first time someone
	forgot. It is four comparisons."""
	if qty < 0:
		return STATUS_NEGATIVE
	if qty == 0:
		return STATUS_OUT
	if par and qty <= par:
		return STATUS_LOW
	return STATUS_OK


def _stock_row(property: str, outlet: str, ingredient: str,
               for_update: bool = False) -> str:
	"""The (outlet, ingredient) balance row, created on first touch.

	The name is deterministic - "{outlet}::{ingredient}" - and that is
	load-bearing, not cosmetic. It makes the composite key the PRIMARY key,
	so MariaDB refuses a duplicate in the storage engine rather than in
	application code, where races live. An exists()-then-insert would be a
	textbook TOCTOU: two chefs firing the same new ingredient at once both
	see nothing, both insert, and you end up with two balance rows for one
	ingredient that no lock can ever reconcile. Do not replace this with a
	validate() uniqueness check.

	(POS Outlet and Ingredient names are short - "ING-00001" style - so the
	composite stays well inside Frappe's 140-char name limit. If outlet
	naming ever grows long, this needs a hash.)
	"""
	name = f"{outlet}::{ingredient}"
	if frappe.db.get_value("Ingredient Stock", name, "name",
	                       for_update=for_update):
		return name
	try:
		doc = frappe.get_doc({
			"doctype": "Ingredient Stock", "name": name,
			"property": property, "outlet": outlet, "ingredient": ingredient,
			"qty_on_hand": 0.0, "par_level": 0.0,
		})
		doc.flags.name_set = True  # honour our deterministic name
		doc.insert(ignore_permissions=True)
	except frappe.DuplicateEntryError:
		# Someone created it between our read and our insert. That is exactly
		# what the unique name is for - take the lock on the winner's row.
		frappe.db.get_value("Ingredient Stock", name, "name", for_update=True)
	return name


def _apply_move(property: str, outlet: str, ingredient: str,
                qty_change: float, reason: str, *, ref_dt: str | None = None,
                ref_dn: str | None = None, note: str | None = None,
                supplier: str | None = None, invoice_no: str | None = None,
                batch_id: str | None = None, set_counted: bool = False) -> float:
	"""THE only writer of qty_on_hand. One move = one locked row + one ledger
	entry, in one transaction. Never blocks: a move that takes the balance
	negative still lands, because a stale count must not stop service.

	The for_update lock is what stops a lost update - two chefs firing paneer
	in the same second both reading 10 and both writing 8, silently losing a
	deduction that only surfaces at the next stock take. One Frappe request is
	one transaction, so the lock spans the read and the write. This is not a
	novelty here: reservation.py locks a Room row the same way to stop a
	double booking. Do not "simplify" it away.
	"""
	name = _stock_row(property, outlet, ingredient, for_update=True)
	current = float(frappe.db.get_value("Ingredient Stock", name, "qty_on_hand",
	                                    for_update=True) or 0)
	after = current + float(qty_change)
	cost = frappe.db.get_value("Ingredient", ingredient, "cost_per_unit")

	frappe.db.set_value("Ingredient Stock", name, "qty_on_hand", after,
	                    update_modified=False)
	if set_counted:
		frappe.db.set_value("Ingredient Stock", name, {
			"last_counted_at": frappe.utils.now(),
			"last_counted_by": frappe.session.user,
		}, update_modified=False)

	frappe.get_doc({
		"doctype": "Stock Ledger Entry", "property": property, "outlet": outlet,
		"ingredient": ingredient, "qty_change": float(qty_change),
		"balance_after": after, "reason": reason,
		"reference_doctype": ref_dt, "reference_name": ref_dn, "note": note,
		"supplier": supplier, "invoice_no": invoice_no, "batch_id": batch_id,
		"cost_per_unit": cost,
	}).insert(ignore_permissions=True)
	return after


def _recipes_of(menu_items) -> dict:
	"""menu_item -> [(ingredient, qty_per_unit), ...]. One query for the lot:
	fire_kot is on the hot path of every service."""
	ids = [m for m in menu_items if m]
	if not ids:
		return {}
	out = {}
	for r in frappe.get_all(
		"Menu Item Ingredient", filters={"parent": ["in", ids], "parenttype": "Menu Item"},
		fields=["parent", "ingredient", "qty"], order_by="idx asc",
	):
		out.setdefault(r.parent, []).append((r.ingredient, float(r.qty or 0)))
	return out


def consume_for_lines(order, lines) -> list:
	"""Take a fired order's recipes off the outlet's stock. Called from
	fire_kot with the lines it just fired - never from a doc hook, see below.

	Idempotent per line via stock_posted, so a re-fired later course, a
	recall, a split or a retried request can never double-deduct.

	WHY AN EXPLICIT CALL, NOT A CONTROLLER HOOK: POS Order.on_update +
	posted_to_folio is the right template for folio posting, and the wrong one
	for stock. split_order() inserts a NEW POS Order whose lines are copied
	with kot_status intact - brand-new child rows that are already "Fired"
	with stock_posted defaulting to 0. A hook keyed on "fired and not posted"
	would silently deduct twice for every split bill. Splitting a table is
	routine, so the data would be poisoned within a week and be near
	impossible to trace back. (split_order copies stock_posted across too,
	which closes the same hole from the other side.)

	WHAT DOES *NOT* MOVE STOCK, and why - the whole reversal table:
	  create_order / add_items  nothing left the shelf; a tab may sit an hour
	  void on a New line        never deducted
	  void on a Fired line      the chef may be cooking it RIGHT NOW. It is
	                            cooked and binned: wastage, not a reversal.
	  acknowledge_void          display only, no physical meaning
	  recall_prepared           Prepared -> Fired, never -> New. A mis-tap on
	                            a greasy screen must not move stock.
	  mark_prepared             ingredients left at fire, not here
	  cancel_order              fired half was cooked; unfired half never moved
	  deliver_order / pay_order money-time, far too late
	  mark_nc                   a comped dish consumed real paneer - that is
	                            the entire point of costing an NC
	  a recipe edited later     the ledger snapshotted qty at fire; history is
	                            never rewritten
	The genuinely-not-cooked case (a captain voids five seconds after firing,
	before the chef looked up) is NOT solved with a heuristic on void_seen or
	elapsed time - that guesses at the physical world and is wrong in both
	directions. It is solved by adjust_stock: a human puts it back, with a
	required note, leaving a Count row. A discrepancy is an explicit decision,
	never silence - the same shape as laundry's shortage guard.
	"""
	todo = [it for it in lines if not it.get("stock_posted")]
	if not todo:
		return []

	recipes = _recipes_of({it["menu_item"] for it in todo})
	need = {}
	for it in todo:
		for ing, per in recipes.get(it["menu_item"], ()):
			need[ing] = need.get(ing, 0.0) + per * float(it.get("qty") or 1)
	if not need:
		return []  # nothing fired here has a recipe. Silence is correct.

	alerts = []
	# SORTED IS A DEADLOCK GUARD, NOT TIDINESS. Butter Chicken needs
	# {chicken, cream}; Paneer Tikka needs {cream, paneer}. Two tickets firing
	# at once, unordered: A holds chicken and wants cream while B holds cream
	# and wants chicken. MariaDB kills one - and a chef's KOT dies mid-service
	# with an opaque error, which is the one thing this module must never do.
	# A global lock order makes that structurally impossible: B simply waits.
	# Invisible in single-user dev; catastrophic on a Saturday night.
	for ing in sorted(need):
		after = _apply_move(
			order.property, order.outlet, ing, -need[ing], "Consumed",
			ref_dt="POS Order", ref_dn=order.name,
			note=f"KOT {order.kot_no or '-'}")
		if after <= 0:
			alerts.append({
				"ingredient": ing,
				"ingredient_name": frappe.db.get_value("Ingredient", ing, "ingredient_name"),
				"qty_on_hand": after,
				"level": STATUS_NEGATIVE.lower() if after < 0 else STATUS_OUT.lower(),
			})

	# Stamp only after every move landed. Same transaction, so a failure rolls
	# the deduction and the stamp back together. db.set_value rather than
	# touching the child docs: fire_kot has already saved, and a second save
	# would re-run validate(), re-fire on_update (a duplicate realtime notify)
	# and re-enter the folio branch.
	for it in todo:
		frappe.db.set_value("POS Order Item", it["row"], "stock_posted", 1,
		                    update_modified=False)
	return alerts


# ---------------------------------------------------------------- recipes

@frappe.whitelist()
@require_roles(*INVENTORY_READ)
def ingredients(property: str, active_only: int = 1):
	"""The ingredient master - the picker behind the recipe editor."""
	filters = {"property": property}
	if int(active_only or 0):
		filters["is_active"] = 1
	return frappe.get_all(
		"Ingredient", filters=filters,
		fields=["name", "ingredient_name", "uom", "category", "cost_per_unit",
		        "is_active"],
		order_by="ingredient_name asc")


@frappe.whitelist()
@require_roles(*INVENTORY_READ)
def menu_recipe(menu_item: str):
	"""One dish's recipe, with each line's unit and what the dish's own outlet
	has on hand right now - so the editor can say "you have 0.4 kg left"."""
	mi = frappe.db.get_value("Menu Item", menu_item,
	                         ["item_name", "property", "outlet"], as_dict=True)
	if not mi:
		frappe.throw(_("Menu item not found."))
	rows = frappe.get_all(
		"Menu Item Ingredient", filters={"parent": menu_item, "parenttype": "Menu Item"},
		fields=["name", "ingredient", "qty", "note"], order_by="idx asc")
	for r in rows:
		meta = frappe.db.get_value("Ingredient", r.ingredient,
		                           ["ingredient_name", "uom"], as_dict=True) or {}
		r["ingredient_name"] = meta.get("ingredient_name")
		r["uom"] = meta.get("uom")
		r["qty_on_hand"] = frappe.db.get_value(
			"Ingredient Stock", f"{mi.outlet}::{r.ingredient}", "qty_on_hand")
	return {"menu_item": menu_item, "item_name": mi.item_name,
	        "outlet": mi.outlet, "property": mi.property, "recipe": rows}


@frappe.whitelist()
@require_roles(*INVENTORY_READ)
def recipe_overview(property: str):
	"""Every dish and whether it has a recipe yet. Dishes without one are not
	a problem to be nagged about - most menus will only ever cost their big
	movers - but you cannot decide that without seeing the list."""
	dishes = frappe.get_all(
		"Menu Item", filters={"property": property},
		fields=["name", "item_name", "outlet", "category", "available"],
		order_by="outlet asc, category asc, item_name asc")
	if not dishes:
		return []
	counts = {}
	for r in frappe.get_all(
		"Menu Item Ingredient",
		filters={"parent": ["in", [d.name for d in dishes]], "parenttype": "Menu Item"},
		fields=["parent"],
	):
		counts[r.parent] = counts.get(r.parent, 0) + 1
	outlets = {
		o.name: o.outlet_name for o in frappe.get_all(
			"POS Outlet", filters={"name": ["in", list({d.outlet for d in dishes})]},
			fields=["name", "outlet_name"])
	}
	for d in dishes:
		d["lines"] = counts.get(d.name, 0)
		d["outlet_name"] = outlets.get(d.outlet)
	return dishes


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Hotel Admin")
def save_recipe(menu_item: str, rows):
	"""Replace a dish's recipe wholesale. An empty list is valid and means
	"this dish never touches inventory" - the optional in the requirement."""
	if isinstance(rows, str):
		rows = frappe.parse_json(rows)
	doc = frappe.get_doc("Menu Item", menu_item)
	clean = []
	for r in rows or []:
		ing = r.get("ingredient")
		qty = float(r.get("qty") or 0)
		if not ing:
			continue
		if qty <= 0:
			frappe.throw(_("Every recipe line needs a quantity above zero."))
		ing_property = frappe.db.get_value("Ingredient", ing, "property")
		if ing_property != doc.property:
			frappe.throw(_("{0} belongs to another property.").format(ing))
		clean.append({"ingredient": ing, "qty": qty, "note": r.get("note") or None})
	doc.set("recipe", clean)
	doc.save()
	return {"ok": True, "lines": len(clean)}


@frappe.whitelist(methods=["POST"])
@require_roles(*INVENTORY_WRITE)
def save_ingredient(property: str, ingredient_name: str, uom: str,
                    category: str | None = None, cost_per_unit: float = 0,
                    is_active: int = 1, name: str | None = None):
	"""Create or update one ingredient."""
	if not (ingredient_name or "").strip():
		frappe.throw(_("An ingredient needs a name."))
	doc = frappe.get_doc("Ingredient", name) if name else frappe.new_doc("Ingredient")
	doc.update({
		"property": property, "ingredient_name": ingredient_name.strip(),
		"uom": uom, "category": (category or "").strip() or None,
		"cost_per_unit": float(cost_per_unit or 0), "is_active": int(is_active or 0),
	})
	doc.save()
	return {"ok": True, "name": doc.name}


@frappe.whitelist(methods=["POST"])
@require_roles(*INVENTORY_WRITE)
def delete_ingredient(name: str):
	"""Refuse if it is on a recipe or has history - deleting it would orphan a
	recipe or punch a hole in the ledger. Deactivate instead."""
	used = frappe.db.count("Menu Item Ingredient", {"ingredient": name})
	if used:
		frappe.throw(_("{0} dish(es) use this ingredient. Deactivate it instead.")
		             .format(used))
	if frappe.db.count("Stock Ledger Entry", {"ingredient": name}):
		frappe.throw(_("This ingredient has stock history. Deactivate it instead."))
	frappe.delete_doc("Ingredient", name)
	return {"ok": True}


# ------------------------------------------------------------ stock moves

@frappe.whitelist(methods=["POST"])
@require_roles(*INVENTORY_WRITE)
def receive_stock(property: str, outlet: str, rows, supplier: str | None = None,
                  invoice_no: str | None = None):
	"""Goods in. rows = [{ingredient, qty, cost_per_unit?}]. One batch_id ties
	the delivery together, which is why this needs no Stock Receipt doctype:
	a receipt is just its ledger rows plus a supplier and an invoice number."""
	if isinstance(rows, str):
		rows = frappe.parse_json(rows)
	if not rows:
		frappe.throw(_("Nothing to receive."))
	batch = uuid.uuid4().hex[:12]
	out = []
	for r in rows:
		qty = float(r.get("qty") or 0)
		if qty <= 0:
			frappe.throw(_("Received quantity must be above zero."))
		ing = r["ingredient"]
		if r.get("cost_per_unit") not in (None, ""):
			# the price we actually paid becomes the price we value waste at
			frappe.db.set_value("Ingredient", ing, "cost_per_unit",
			                    float(r["cost_per_unit"]))
		after = _apply_move(property, outlet, ing, qty, "Received",
		                    supplier=supplier, invoice_no=invoice_no,
		                    batch_id=batch, note=r.get("note"))
		out.append({"ingredient": ing, "qty_on_hand": after})

	from kamra.savings import log_action
	log_action("stock_receive", "POS Outlet", outlet, property,
	           rationale=f"{len(out)} ingredient(s) received"
	                     + (f" from {supplier}" if supplier else ""),
	           channel="API")
	return {"ok": True, "batch_id": batch, "rows": out}


@frappe.whitelist(methods=["POST"])
@require_roles(*INVENTORY_WRITE)
def adjust_stock(property: str, outlet: str, rows, note: str):
	"""The stock take, and the escape hatch for everything this module cannot
	know. rows = [{ingredient, counted_qty}] - COUNTS, not deltas, exactly
	like laundry's return_items: a human reports what is physically on the
	shelf and the system works out its own error.

	The note is required on purpose. A write-off with no reason is precisely
	the silence this module exists to remove - the same call laundry's
	shortage guard makes when it refuses to deliver a short bag unexplained.
	"""
	if isinstance(rows, str):
		rows = frappe.parse_json(rows)
	if not (note or "").strip():
		frappe.throw(_("A stock take needs a note - what did you count, and why "
		               "does it differ?"))
	if not rows:
		frappe.throw(_("Nothing counted."))
	batch = uuid.uuid4().hex[:12]
	out = []
	for r in rows:
		ing = r["ingredient"]
		counted = float(r.get("counted_qty") or 0)
		name = _stock_row(property, outlet, ing)
		current = float(frappe.db.get_value("Ingredient Stock", name, "qty_on_hand") or 0)
		delta = counted - current
		if abs(delta) < 1e-9:
			continue  # counted exactly what we thought: nothing to record
		after = _apply_move(property, outlet, ing, delta, "Count",
		                    note=note.strip()[:500], batch_id=batch,
		                    set_counted=True)
		out.append({"ingredient": ing, "was": current, "now": after,
		            "variance": delta})

	if out:
		from kamra.savings import log_action
		value = sum(abs(r["variance"])
		            * float(frappe.db.get_value("Ingredient", r["ingredient"],
		                                        "cost_per_unit") or 0)
		            for r in out)
		log_action("stock_count", "POS Outlet", outlet, property,
		           rationale=f"{len(out)} variance(s), ~₹{value:,.0f} adjusted - "
		                     f"{note.strip()[:80]}",
		           channel="API")
	return {"ok": True, "batch_id": batch, "adjusted": out}


@frappe.whitelist(methods=["POST"])
@require_roles(*INVENTORY_WRITE)
def record_wastage(property: str, outlet: str, ingredient: str, qty: float,
                   reason_note: str):
	"""Stock destroyed OUTSIDE a sale: a crate of tomatoes rots, a bottle
	breaks. No POS line exists, so only a real ledger row can say it happened.

	Note what this is NOT for: food that was cooked and then voided. That
	already left the shelf at fire and already has its Consumed row - writing
	a Wastage row too would deduct it twice. Use wastage_report() for those.
	"""
	qty = float(qty or 0)
	if qty <= 0:
		frappe.throw(_("Wasted quantity must be above zero."))
	if not (reason_note or "").strip():
		frappe.throw(_("Wastage needs a reason."))
	after = _apply_move(property, outlet, ingredient, -qty, "Wastage",
	                    note=reason_note.strip()[:500])
	from kamra.savings import log_action
	cost = float(frappe.db.get_value("Ingredient", ingredient, "cost_per_unit") or 0)
	log_action("stock_wastage", "Ingredient", ingredient, property,
	           rationale=f"{qty} wasted (~₹{qty * cost:,.0f}) - "
	                     f"{reason_note.strip()[:80]}",
	           channel="API")
	return {"ok": True, "qty_on_hand": after}


# ----------------------------------------------------------------- reads

@frappe.whitelist()
@require_roles(*INVENTORY_READ)
def stock_list(property: str, outlet: str, status: str | None = None):
	"""Everything this outlet holds. Stock is per outlet, so there is no such
	thing as a merged total across outlets and this never offers one."""
	rows = frappe.get_all(
		"Ingredient Stock", filters={"property": property, "outlet": outlet},
		fields=["name", "ingredient", "qty_on_hand", "par_level",
		        "last_counted_at", "last_counted_by"])
	out = []
	for r in rows:
		meta = frappe.db.get_value(
			"Ingredient", r.ingredient,
			["ingredient_name", "uom", "category", "cost_per_unit", "is_active"],
			as_dict=True) or {}
		r.update(meta)
		r["status"] = _status(float(r.qty_on_hand or 0), float(r.par_level or 0))
		if status and r["status"] != status:
			continue
		out.append(r)
	out.sort(key=lambda r: (
		{STATUS_NEGATIVE: 0, STATUS_OUT: 1, STATUS_LOW: 2, STATUS_OK: 3}[r["status"]],
		(r.get("ingredient_name") or "")))
	return out


@frappe.whitelist()
@require_roles(*INVENTORY_READ)
def ingredient_ledger(property: str, outlet: str, ingredient: str,
                      limit: int = 50):
	"""Where did my paneer go? Newest first, each row carrying the balance it
	produced, so the history explains the number on the shelf."""
	rows = frappe.get_all(
		"Stock Ledger Entry",
		filters={"property": property, "outlet": outlet, "ingredient": ingredient},
		fields=["name", "creation", "qty_change", "balance_after", "reason",
		        "reference_doctype", "reference_name", "note", "supplier",
		        "invoice_no", "cost_per_unit", "owner"],
		order_by="creation desc", limit=int(limit or 50))
	return rows


@frappe.whitelist()
@require_roles(*INVENTORY_READ)
def low_stock(property: str, outlet: str | None = None):
	"""Everything at or under par, out, or negative - and, for each, the
	dishes that use it. That last part is what makes the flag actionable:
	"Paneer is out" means nothing until you know it takes Paneer Tikka with
	it. We flag and offer; a human decides. Nothing is ever auto-86'd."""
	filters = {"property": property}
	if outlet:
		filters["outlet"] = outlet
	rows = frappe.get_all(
		"Ingredient Stock", filters=filters,
		fields=["outlet", "ingredient", "qty_on_hand", "par_level",
		        "last_counted_at"])
	out = []
	for r in rows:
		st = _status(float(r.qty_on_hand or 0), float(r.par_level or 0))
		if st == STATUS_OK:
			continue
		meta = frappe.db.get_value("Ingredient", r.ingredient,
		                           ["ingredient_name", "uom"], as_dict=True) or {}
		r.update(meta)
		r["status"] = st
		# the dishes this takes down with it - a flag nobody can act on is
		# just noise, and "Paneer is out" only means something once you know
		# it means no Paneer Tikka
		uses = frappe.get_all(
			"Menu Item Ingredient",
			filters={"ingredient": r.ingredient, "parenttype": "Menu Item"},
			pluck="parent")
		r["dishes"] = frappe.get_all(
			"Menu Item", filters={"name": ["in", uses], "outlet": r.outlet},
			fields=["name", "item_name", "available"]) if uses else []
		out.append(r)
	out.sort(key=lambda r: {STATUS_NEGATIVE: 0, STATUS_OUT: 1, STATUS_LOW: 2}[r["status"]])
	return out


@frappe.whitelist()
@require_roles(*INVENTORY_READ)
def wastage_report(property: str, outlet: str | None = None, days: int = 30):
	"""Food that was cooked and then binned: lines voided after they fired.

	Derived, deliberately. The stock already left at the fire and the Consumed
	row is the truth - a second Wastage row would deduct it twice, and a
	compensating pair would churn the ledger without changing a balance. This
	only asks which of those consumptions turned out to be waste, and what
	they cost. reason="Wastage" in the ledger stays reserved for stock
	destroyed outside a sale, so SUM(qty_change) always equals reality.
	"""
	conds = ["p.property = %(property)s", "i.voided = 1", "i.stock_posted = 1",
	         "p.creation >= DATE_SUB(NOW(), INTERVAL %(days)s DAY)"]
	params = {"property": property, "days": int(days or 30)}
	if outlet:
		conds.append("p.outlet = %(outlet)s")
		params["outlet"] = outlet
	lines = frappe.db.sql(f"""  # nosemgrep: frappe-sql-format-injection -- values are parameterized; interpolated text is a constant or whitelisted identifier, not user input
		select i.item_name, i.menu_item, i.qty, i.void_reason, p.outlet,
		       p.name as order_name, p.creation
		  from `tabPOS Order Item` i
		  join `tabPOS Order` p on p.name = i.parent
		 where {' and '.join(conds)}
		 order by p.creation desc""", params, as_dict=True)
	if not lines:
		return {"lines": [], "by_reason": [], "total_value": 0.0}

	recipes = _recipes_of({r.menu_item for r in lines})
	costs = {}
	total = 0.0
	by_reason = {}
	for r in lines:
		value = 0.0
		for ing, per in recipes.get(r.menu_item, ()):
			if ing not in costs:
				costs[ing] = float(frappe.db.get_value(
					"Ingredient", ing, "cost_per_unit") or 0)
			value += per * float(r.qty or 0) * costs[ing]
		r["value"] = round(value, 2)
		total += value
		key = (r.void_reason or "no reason given").strip()
		by_reason[key] = by_reason.get(key, 0.0) + value
	return {
		"lines": lines,
		"by_reason": sorted(({"reason": k, "value": round(v, 2)}
		                     for k, v in by_reason.items()),
		                    key=lambda x: -x["value"]),
		"total_value": round(total, 2),
	}


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Hotel Admin")
def set_menu_availability(menu_item: str, available: int):
	"""86 a dish, or put it back. This is the ONLY thing that ever pulls an
	item off the menu for stock reasons, and a human has to press it.

	Nothing auto-86s on a zero balance, deliberately: the count is the least
	trustworthy number in the building (see this module's docstring), and a
	stale one would silently hide a dish the kitchen can actually cook. The
	screen flags what is out and offers the button; the decision stays with
	someone who can walk over and look at the shelf.
	"""
	doc = frappe.get_doc("Menu Item", menu_item)
	doc.available = 1 if int(available or 0) else 0
	doc.save()
	return {"ok": True, "available": doc.available}


@frappe.whitelist(methods=["POST"])
@require_roles(*INVENTORY_WRITE)
def set_par_level(property: str, outlet: str, ingredient: str, par_level: float):
	"""Where LOW starts for this ingredient at this outlet. Zero = no par."""
	name = _stock_row(property, outlet, ingredient)
	frappe.db.set_value("Ingredient Stock", name, "par_level",
	                    float(par_level or 0), update_modified=False)
	return {"ok": True}
