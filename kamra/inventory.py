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

COST is one figure per ingredient (Ingredient.cost_per_unit), shared by every
outlet. A priced delivery either replaces it or averages it into the stock
held, as the property's "Ingredient cost" setting says: cost_after_receipt()
is the whole rule.

Permissions: consume_for_lines() runs under a captain's session, which cannot
write Ingredient Stock or Ingredient Ledger Entry by design - only Finance can move
stock deliberately. The writes in _apply_move() therefore use
ignore_permissions / db.set_value. That is intentional, not an oversight: the
authorization for consumption is the POS_ROLES gate on fire_kot, not doctype
perms on the ledger. authz.py's own docstring makes the same point.
"""

import math
import uuid
from functools import partial

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, nowdate

from kamra.authz import require_perm
from kamra.localization import money_text

# Who may look at stock, and who may move it. Chefs never appear here: they
# consume implicitly through fire_kot (already gated on POS_ROLES), because
# consumption is a byproduct of service, not an inventory action. Receiving
# and counting are money - a goods-in is an asset movement, a stock take is a
# P&L event - so they sit with Finance and the F&B Manager who runs the
# kitchen (require_roles widens that to admins).
INVENTORY_READ = ("Front Desk", "Finance", "F&B Manager", "Kamra Agent", "Hotel Admin")
INVENTORY_WRITE = ("Finance", "F&B Manager")

STATUS_OK, STATUS_LOW, STATUS_OUT, STATUS_NEGATIVE = "OK", "LOW", "OUT", "NEGATIVE"

AVERAGE_COST = "Average of purchases"


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


def check_outlet(property: str, outlet: str) -> None:
	"""Refuse an outlet of another property. require_perm only checks that the
	user can reach each record, so someone on two hotels could pair one's name
	with the other's outlet and leave a stock row labelled A under B."""
	if frappe.db.get_value("POS Outlet", outlet, "property") != property:
		frappe.throw(_("That outlet is not at this property."))


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
                batch_id: str | None = None, set_counted: bool = False,
                set_qty: float | None = None, cost: float | None = None,
                extra: dict | None = None, posted_at: str | None = None) -> float:
	"""THE only writer of qty_on_hand. One move = one locked row + one ledger
	entry, in one transaction. Never blocks: a move that takes the balance
	negative still lands, because a stale count must not stop service.

	The for_update lock is what stops a lost update - two chefs firing paneer
	in the same second both reading 10 and both writing 8, silently losing a
	deduction that only surfaces at the next stock take. One Frappe request is
	one transaction, so the lock spans the read and the write. This is not a
	novelty here: reservation.py locks a Room row the same way to stop a
	double booking. Do not "simplify" it away.

	`posted_at` dates the move in the past: it goes in at that moment and the
	later balances are worked again (_ripple). Without it the move happens now,
	stamped after the lock, so no row dated "now" can land before it. Never
	pass a time read before the lock. Answers with the stock on hand afterwards.
	"""
	name = _stock_row(property, outlet, ingredient, for_update=True)
	current = float(frappe.db.get_value("Ingredient Stock", name, "qty_on_hand",
	                                    for_update=True) or 0)
	back = posted_at is not None
	posted_at = posted_at or frappe.utils.now()
	# what the shelf held just before this move
	before = current - _moved_after(outlet, ingredient, posted_at) if back else current
	# A count reports what is on the shelf. Applying a delta taken before
	# the lock would miss a sale that landed while this count waited.
	counting = set_qty is not None
	if counting:
		after = float(set_qty)
		qty_change = after - before
	else:
		after = before + float(qty_change)
	effect = (_ripple(outlet, ingredient, float(qty_change), after=(posted_at,))
	          if back else float(qty_change))
	on_hand = current + effect
	# a delivery names the price paid; any other move snapshots today's cost
	if cost is None:
		cost = frappe.db.get_value("Ingredient", ingredient, "cost_per_unit")

	frappe.db.set_value("Ingredient Stock", name, "qty_on_hand", on_hand,
	                    update_modified=False)

	entry = frappe.get_doc({
		"doctype": "Ingredient Ledger Entry", "property": property, "outlet": outlet,
		"ingredient": ingredient, "qty_change": float(qty_change),
		"balance_after": after, "reason": reason, "posted_at": posted_at,
		"counted_qty": after if counting else 0,
		"reference_doctype": ref_dt, "reference_name": ref_dn, "note": note,
		"supplier": supplier, "invoice_no": invoice_no, "batch_id": batch_id,
		"cost_per_unit": cost, **(extra or {}),
	})
	entry.flags.stock_effect, entry.flags.on_hand = effect, on_hand
	entry.insert(ignore_permissions=True)
	if set_counted:
		_stamp_counted(name, outlet, ingredient)
	return on_hand


def _stamp_counted(stock_row: str, outlet: str, ingredient: str) -> None:
	"""The shelf says when it was last counted: the newest stock take still
	standing, which a back-dated one need not be."""
	last = frappe.get_all(
		"Ingredient Ledger Entry",
		filters={"outlet": outlet, "ingredient": ingredient, "reason": "Count",
		         "cancelled": 0},
		fields=["posted_at", "owner"], order_by="posted_at desc, creation desc", limit=1)
	frappe.db.set_value("Ingredient Stock", stock_row, {
		"last_counted_at": last[0].posted_at if last else None,
		"last_counted_by": last[0].owner if last else None,
	}, update_modified=False)


# A ledger row's place in its (ingredient, outlet) history is
# (posted_at, creation, name). "After" an insert is just a later posted_at:
# the new row is the newest typed at its own moment.
_PLACE = "(posted_at, creation, name)"


def _later_than(place: tuple) -> tuple:
	"""SQL condition and values for "comes after this place"."""
	if len(place) == 1:
		return "posted_at > %s", list(place)
	return f"{_PLACE} > (%s, %s, %s)", list(place)


def _moved_after(outlet: str, ingredient: str, posted_at: str) -> float:
	return float(frappe.db.sql(
		"""select coalesce(sum(qty_change), 0) from `tabIngredient Ledger Entry`
		where ingredient = %s and outlet = %s and posted_at > %s""",
		(ingredient, outlet, posted_at))[0][0])


def _later_count(outlet: str, ingredient: str, after: tuple):
	"""The first stock take still standing after this place, or None."""
	cond, values = _later_than(after)
	rows = frappe.db.sql(  # nosemgrep: frappe-sql-format-injection -- the condition is one of two constants; values are parameters
		f"""select name, posted_at, creation from `tabIngredient Ledger Entry`
		where ingredient = %s and outlet = %s and reason = 'Count' and cancelled = 0
		  and {cond}
		order by posted_at, creation, name limit 1""",
		[ingredient, outlet, *values], as_dict=True)
	return rows[0] if rows else None


def _ripple(outlet: str, ingredient: str, delta: float, *, after: tuple) -> float:
	"""A change of `delta` appears at a place in history: carry it forward.

	A stock take says what was on the shelf at its moment, so it absorbs the
	change - its own difference moves by -delta and nothing after it does.
	Answers with how much the stock on hand now changes. The caller holds the
	stock row's lock, so no other writer is adding rows meanwhile. Two set-based
	updates at most: a date far back must not hold the kitchen up row by row."""
	if not delta:
		return 0.0
	count = _later_count(outlet, ingredient, after)
	cond, values = _later_than(after)
	if count:
		cond += f" and {_PLACE} < (%s, %s, %s)"
		values += [count.posted_at, count.creation, count.name]
	frappe.db.sql(  # nosemgrep: frappe-sql-format-injection -- constant conditions; values are parameters
		f"""update `tabIngredient Ledger Entry` set balance_after = balance_after + %s
		where ingredient = %s and outlet = %s and {cond}""",
		[delta, ingredient, outlet, *values])
	if not count:
		return delta
	frappe.db.sql(
		"""update `tabIngredient Ledger Entry` set qty_change = qty_change - %s
		where name = %s""", (delta, count.name))
	return 0.0


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


def _option_recipes_of(options) -> dict:
	"""choice -> [(ingredient, qty_per_dish), ...]. What a choice (Extra shot,
	Oat milk) takes off the shelf on top of the dish's own recipe: the same
	lines a recipe has, kept on the Menu Modifier Option."""
	ids = [o for o in options if o]
	if not ids:
		return {}
	out = {}
	for r in frappe.get_all(
		"Menu Item Ingredient",
		filters={"parent": ["in", ids], "parenttype": "Menu Modifier Option"},
		fields=["parent", "ingredient", "qty"], order_by="idx asc",
	):
		out.setdefault(r.parent, []).append((r.ingredient, float(r.qty or 0)))
	return out


def consume_for_lines(order, lines, note: str | None = None) -> list:
	"""Take lines' recipes off the outlet's stock. Called from fire_kot with
	the lines it just fired - never from a doc hook, see below - and, for lines
	never sent, from consume_unsent_lines when their bill closes.

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
	  deliver_order / pay_order nothing for a sent line (it left at fire); a
	                            line never sent leaves then, since it was handed
	                            over all the same (consume_unsent_lines)
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
	# a choice can take stock too (Extra shot: 18 g of beans): the dish's own
	# recipe and its choices are one movement per ingredient, summed
	extras = _option_recipes_of({o for it in todo for o in it.get("modifiers") or ()})
	need = {}
	for it in todo:
		qty = float(it.get("qty") or 1)
		for ing, per in recipes.get(it["menu_item"], ()):
			need[ing] = need.get(ing, 0.0) + per * qty
		for opt in it.get("modifiers") or ():
			for ing, per in extras.get(opt, ()):
				need[ing] = need.get(ing, 0.0) + per * qty
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
			note=note or f"KOT {order.kot_no or '-'}")
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
	# an item with its own stock remembers which stock item went: what a refund
	# puts back, whatever the menu says by then
	own = dict(frappe.get_all(
		"Menu Item",
		filters={"name": ["in", list({it["menu_item"] for it in todo})],
		         "stock_ingredient": ["is", "set"]},
		fields=["name", "stock_ingredient"], as_list=True))
	for it in todo:
		values = {"stock_posted": 1}
		if it["menu_item"] in own:
			values["stock_item"] = own[it["menu_item"]]
		frappe.db.set_value("POS Order Item", it["row"], values, update_modified=False)
	return alerts


def consume_unsent_lines(order) -> None:
	"""The bill is closing: paid, charged to a room, or comped. What was never
	sent to the kitchen was still handed over, so it leaves stock now (a sent
	line left when it was fired, a voided one was never served).

	Money first: a fault here is logged and the bill still closes. A database
	clash is not a stock fault - it ends the request, to be tried again."""
	todo = [it for it in order.items
	        if (it.kot_status or "New") == "New" and not it.voided and not it.stock_posted]
	if not todo:
		return
	from kamra.menu_modifiers import option_ids_of

	frappe.db.savepoint("stock_at_close")
	try:
		consume_for_lines(order, [
			{"row": it.name, "menu_item": it.menu_item, "qty": it.qty,
			 "stock_posted": it.stock_posted,
			 "modifiers": option_ids_of(it.modifiers)} for it in todo],
			note="Closed without a kitchen ticket")
	except (frappe.QueryDeadlockError, frappe.QueryTimeoutError):
		raise
	except Exception:
		frappe.db.rollback(save_point="stock_at_close")
		frappe.log_error(title=f"Stock not taken at close: {order.name}")
		return
	# keep the open document in step, should anything save it again
	for it in todo:
		it.stock_posted, it.stock_item = frappe.db.get_value(
			"POS Order Item", it.name, ["stock_posted", "stock_item"])


# ---------------------------------------------------------------- recipes

def portion_cost(parts: list) -> float | None:
	"""What one portion costs, from (quantity, cost per unit) pairs. None when
	there is nothing to add up, or when any part has no cost yet (0): a part
	total would read as a fine margin."""
	if not parts or any(float(cost or 0) <= 0 for _qty, cost in parts):
		return None
	return round(sum(float(qty or 0) * float(cost) for qty, cost in parts), 6)


def margin_of(price: float, cost: float | None) -> tuple:
	"""(price - cost, the same as a percent of the price); None where unknown."""
	if cost is None:
		return None, None
	price = float(price or 0)
	margin = round(price - cost, 6)
	return margin, (margin / price * 100 if price > 0 else None)


def _sees_costs() -> bool:
	"""Ingredient costs are for the people who can see stock."""
	return bool(frappe.has_permission("Ingredient", "view_stock",
	                                  ignore_share_permissions=True))

# ------------------------------------------------- ingredients made here
#
# A made ingredient ("syrup") carries the recipe of one batch. Its cost is
# stored like any other ingredient's, so everything that reads a cost needs no
# change; it is worked out again after whatever moved it has committed.

def _made_parts(made: list) -> dict:
	"""made ingredient -> the lines of its batch recipe."""
	out = {}
	for r in frappe.get_all(
		"Menu Item Ingredient",
		filters={"parent": ["in", made or [""]], "parenttype": "Ingredient"},
		fields=["parent", "ingredient", "qty"], order_by="idx asc",
	):
		out.setdefault(r.parent, []).append(r)
	return out


def _cost_gaps(names) -> dict:
	"""For the made ingredients among `names`: what in them has no cost yet."""
	parts = _made_parts(list(names))
	if not parts:
		return {}
	bare = dict(frappe.get_all(
		"Ingredient",
		filters={"name": ["in", [r.ingredient for rows in parts.values() for r in rows]],
		         "cost_per_unit": ["<=", 0]},
		fields=["name", "ingredient_name"], as_list=True))
	return {made: list(dict.fromkeys(bare[r.ingredient] for r in rows
	                                 if r.ingredient in bare))
	        for made, rows in parts.items()}


def _made_cost(parts: list, batch: float) -> float:
	"""One stock unit of a batch, from (quantity, cost per unit) pairs. 0, "no
	cost yet", when any part has none."""
	total = portion_cost(parts)
	if total is None or batch <= 0:
		return 0.0
	return round(total / batch, 6)


def schedule_recost(names) -> None:
	"""Work out made ingredients' costs again once the change in hand has
	committed; `names` are the ingredients whose cost or recipe just changed.
	Not before, and not inside a save: the saved row is still locked there (the
	wrong order to lock a batch's ingredients in), and the reads would not show
	what others have saved meanwhile."""
	if names:
		frappe.db.after_commit.add(partial(_recost, tuple(sorted(set(names)))))


def _recost(changed: tuple) -> None:
	"""Runs after the commit, as short transactions of its own. A database clash
	is tried again; a failure is logged and never fails what triggered it."""
	# whatever else waits for this commit runs now: a rollback below would drop it
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- after-commit work, nothing of the request is pending
	for attempt in range(3):
		try:
			made = sorted({
				*frappe.get_all("Ingredient", filters={"name": ["in", changed], "is_made": 1},
				                pluck="name"),
				*frappe.get_all("Menu Item Ingredient",
				                filters={"ingredient": ["in", changed],
				                         "parenttype": "Ingredient"}, pluck="parent")})
			if made:
				_write_made_costs(made)
			return
		except Exception:
			frappe.db.rollback()
			if attempt == 2:
				frappe.log_error(
					title="Cost of made ingredients not worked out",
					message=f"After a change to {', '.join(changed)}\n{frappe.get_traceback()}")
				frappe.db.commit()  # nosemgrep: frappe-manual-commit -- keep the error log


def _write_made_costs(made: list) -> None:
	names = {*made, *(r.ingredient for rows in _made_parts(made).values() for r in rows)}
	# the locks must open the transaction: the reads after them are then current
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- after-commit work, nothing written yet
	_lock_ingredients(sorted(names))
	parts = _made_parts(made)
	costs = dict(frappe.get_all(
		"Ingredient",
		filters={"name": ["in", [r.ingredient for rows in parts.values() for r in rows] or [""]]},
		fields=["name", "cost_per_unit"], as_list=True))
	for name, rows in parts.items():
		batch = flt(frappe.db.get_value("Ingredient", name, "batch_qty"))
		frappe.db.set_value(
			"Ingredient", name, "cost_per_unit",
			_made_cost([(r.qty, costs.get(r.ingredient)) for r in rows], batch))
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- release the locks


@frappe.whitelist()
@require_perm("Ingredient", "view_stock")
def ingredients(property: str, active_only: int = 1):
	"""The ingredient master - the picker behind the recipe editor. A made one
	without a cost also names what in it still needs one (`missing`)."""
	filters = {"property": property}
	if int(active_only or 0):
		filters["is_active"] = 1
	rows = frappe.get_all(
		"Ingredient", filters=filters,
		fields=["name", "ingredient_name", "uom", "category", "cost_per_unit",
		        "is_active", "is_made"],
		order_by="ingredient_name asc")
	gaps = _cost_gaps([r.name for r in rows if r.is_made and flt(r.cost_per_unit) <= 0])
	for r in rows:
		if r.name in gaps:
			r["missing"] = gaps[r.name]
	return rows


@frappe.whitelist()
@require_perm("Menu Item", "view_recipes")
def menu_recipe(menu_item: str):
	"""One dish's recipe, with each line's unit and what the dish's own outlet
	has on hand right now - so the editor can say "you have 0.4 kg left". The
	menu price and each ingredient's cost come with it only for people who can
	see stock."""
	mi = frappe.db.get_value(
		"Menu Item", menu_item,
		["item_name", "property", "outlet", "price", "stock_ingredient"], as_dict=True)
	if not mi:
		frappe.throw(_("Menu item not found."))
	rows = frappe.get_all(
		"Menu Item Ingredient", filters={"parent": menu_item, "parenttype": "Menu Item"},
		fields=["name", "ingredient", "qty", "note"], order_by="idx asc")
	costs = _sees_costs()
	gaps = _cost_gaps([r.ingredient for r in rows]) if costs else {}
	for r in rows:
		meta = frappe.db.get_value(
			"Ingredient", r.ingredient,
			["ingredient_name", "uom", "cost_per_unit"], as_dict=True) or {}
		r["ingredient_name"] = meta.get("ingredient_name")
		r["uom"] = meta.get("uom")
		if costs:
			r["cost_per_unit"] = meta.get("cost_per_unit")
			if r.ingredient in gaps and flt(r["cost_per_unit"]) <= 0:
				r["missing"] = gaps[r.ingredient]
		r["qty_on_hand"] = frappe.db.get_value(
			"Ingredient Stock", f"{mi.outlet}::{r.ingredient}", "qty_on_hand")
	out = {"menu_item": menu_item, "item_name": mi.item_name,
	       "outlet": mi.outlet, "property": mi.property, "recipe": rows,
	       "stock_ingredient": mi.stock_ingredient}
	if mi.stock_ingredient:
		own = frappe.db.get_value("Ingredient", mi.stock_ingredient,
		                          ["ingredient_name", "uom"], as_dict=True) or {}
		out.update({
			"stock_name": own.get("ingredient_name"), "stock_uom": own.get("uom"),
			"stock_on_hand": float(frappe.db.get_value(
				"Ingredient Stock", f"{mi.outlet}::{mi.stock_ingredient}", "qty_on_hand") or 0),
		})
	if costs:
		out["price"] = mi.price
	return out


@frappe.whitelist()
@require_perm("Ingredient", "view_stock")
def recipe_overview(property: str):
	"""Every dish and whether it has a recipe yet. Dishes without one are not
	a problem to be nagged about - most menus will only ever cost their big
	movers - but you cannot decide that without seeing the list.

	A dish with a recipe also says what one portion costs today and what is
	left of its price; `uncosted` names the ingredients that stop that."""
	dishes = frappe.get_all(
		"Menu Item", filters={"property": property},
		fields=["name", "item_name", "outlet", "category", "available", "price",
		        "stock_ingredient"],
		order_by="outlet asc, category asc, item_name asc")
	if not dishes:
		return []
	lines = {}
	for r in frappe.get_all(
		"Menu Item Ingredient",
		filters={"parent": ["in", [d.name for d in dishes]], "parenttype": "Menu Item"},
		fields=["parent", "ingredient", "qty"], order_by="idx asc",
	):
		lines.setdefault(r.parent, []).append(r)
	used = {r.ingredient for rows in lines.values() for r in rows}
	ings = {
		i.name: i for i in frappe.get_all(
			"Ingredient", filters={"name": ["in", list(used) or [""]]},
			fields=["name", "ingredient_name", "cost_per_unit"])
	}
	outlets = {
		o.name: o.outlet_name for o in frappe.get_all(
			"POS Outlet", filters={"name": ["in", list({d.outlet for d in dishes})]},
			fields=["name", "outlet_name"])
	}
	bare = [n for n, i in ings.items() if float(i.cost_per_unit or 0) <= 0]
	gaps = _cost_gaps(bare)

	def needs_cost(name):
		"""What to give a cost, so that this ingredient has one."""
		own = ings[name].ingredient_name
		return [_("{0} (in {1})").format(part, own) for part in gaps.get(name) or []] or [own]

	for d in dishes:
		rows = lines.get(d.name, [])
		d["lines"] = len(rows)
		d["tracked"] = bool(d.pop("stock_ingredient"))
		d["outlet_name"] = outlets.get(d.outlet)
		d["cost"] = portion_cost(
			[(r.qty, ings[r.ingredient].cost_per_unit) for r in rows])
		d["margin"], d["margin_pct"] = margin_of(d.price, d["cost"])
		d["uncosted"] = list(dict.fromkeys(
			label for r in rows if r.ingredient in bare for label in needs_cost(r.ingredient)))
	return dishes


@frappe.whitelist(methods=["POST"])
@require_perm("Menu Item", "edit_menu")
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


# ------------------------------------------------------ items' own stock

def require_stock_rights() -> None:
	"""Giving a menu item its own stock, or taking it away, is stock work too."""
	if not frappe.has_permission("Ingredient", "manage_stock",
	                             ignore_share_permissions=True):
		frappe.throw(_("Tracking stock also needs the right to manage stock."),
		             frappe.PermissionError)


@frappe.whitelist(methods=["POST"])
@require_perm("Menu Item", "edit_menu", scope={"menu_item": "Menu Item"})
def track_item_stock(menu_item: str, ingredient: str | None = None,
                     ingredient_name: str | None = None, uom: str | None = None,
                     cost_per_unit: float | None = None, buy_uom: str | None = None,
                     buy_size: float | None = None):
	"""Give a menu item its own stock: a stock item (a new one, or one that
	exists, such as the same bottle sold at another outlet) behind a fixed
	recipe of one. Receiving, counting, cost and reports then work on it as on
	any ingredient. A dish already made of 1 x an ingredient can adopt it."""
	require_stock_rights()
	doc = frappe.get_doc("Menu Item", menu_item)
	if doc.stock_ingredient:
		frappe.throw(_("{0} already tracks its own stock.").format(doc.item_name))
	lines = [(r.ingredient, float(r.qty or 0)) for r in doc.recipe]
	if lines and lines != [(ingredient, 1.0)]:
		frappe.throw(_("{0} has a recipe. Delete the recipe first.").format(doc.item_name))
	if not ingredient:
		name = (ingredient_name or doc.item_name or "").strip()
		if frappe.db.exists("Ingredient",
		                    {"property": doc.property, "ingredient_name": name}):
			frappe.throw(_("An ingredient called {0} already exists. Pick it instead.")
			             .format(name))
		new = frappe.get_doc({
			"doctype": "Ingredient", "property": doc.property, "ingredient_name": name,
			"uom": (uom or "").strip() or "pc", "category": doc.category,
			"cost_per_unit": float(cost_per_unit or 0),
			"buy_uom": (buy_uom or "").strip() or None, "buy_size": float(buy_size or 0),
		})
		new.insert()
		ingredient = new.name
	doc.stock_ingredient = ingredient
	doc.set("recipe", [{"ingredient": ingredient, "qty": 1}])
	doc.save()
	return {"ok": True, "ingredient": ingredient}


@frappe.whitelist(methods=["POST"])
@require_perm("Menu Item", "edit_menu", scope={"menu_item": "Menu Item"})
def untrack_item_stock(menu_item: str):
	"""Stop tracking: selling the item takes no stock from now on. The stock
	item and its history stay."""
	require_stock_rights()
	doc = frappe.get_doc("Menu Item", menu_item)
	if doc.stock_ingredient:
		doc.stock_ingredient = None
		doc.set("recipe", [])
		doc.save()
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
@require_perm("Ingredient", "manage_stock", scope={"name": "Ingredient"})
def save_ingredient(property: str, ingredient_name: str, uom: str,
                    category: str | None = None, cost_per_unit: float | None = None,
                    gst_rate: float | None = None, is_active: int = 1,
                    name: str | None = None, buy_uom: str | None = None,
                    buy_size: float | None = None):
	"""Create or update one ingredient. A cost or buying unit that isn't sent is
	left as it is: the cost follows deliveries, and editing something else must
	not put an old figure back."""
	if not (ingredient_name or "").strip():
		frappe.throw(_("An ingredient needs a name."))
	doc = frappe.get_doc("Ingredient", name) if name else frappe.new_doc("Ingredient")
	doc.update({
		"property": property, "ingredient_name": ingredient_name.strip(),
		"uom": uom, "category": (category or "").strip() or None,
		"is_active": int(is_active or 0),
	})
	if cost_per_unit not in (None, ""):
		doc.cost_per_unit = float(cost_per_unit)
	if buy_uom is not None:
		doc.buy_uom = buy_uom
	if buy_size is not None:
		doc.buy_size = float(buy_size or 0)
	if gst_rate is not None:
		doc.gst_rate = float(gst_rate)
	doc.save()
	return {"ok": True, "name": doc.name}


@frappe.whitelist(methods=["POST"])
@require_perm("Ingredient", "manage_stock", scope={"name": "Ingredient"})
def delete_ingredient(name: str):
	"""Refuse if it is on a recipe or has history - deleting it would orphan a
	recipe or punch a hole in the ledger. Deactivate instead."""
	used = len(set(frappe.get_all(
		"Menu Item Ingredient", filters={"ingredient": name},
		fields=["parenttype", "parent"], as_list=True)))
	if used:
		frappe.throw(_("{0} recipe(s) use this ingredient. Deactivate it instead.")
		             .format(used))
	if frappe.db.count("Ingredient Ledger Entry", {"ingredient": name}):
		frappe.throw(_("This ingredient has stock history. Deactivate it instead."))
	frappe.delete_doc("Ingredient", name)
	return {"ok": True}


# ------------------------------------------------------------ stock moves

def cost_after_receipt(method: str, on_hand: float, cost: float, qty: float,
                       price: float | None) -> float:
	"""What an ingredient costs after `qty` stock units arrive at `price` each
	(None: no price given). on_hand is the stock before, across every outlet."""
	if price is None:
		return cost
	if method != AVERAGE_COST:
		return round(price, 6)
	if on_hand > 0 and cost > 0:
		return round((on_hand * cost + qty * price) / (on_hand + qty), 6)
	# no priced stock to average with: free goods must not turn a cost into 0
	return round(price, 6) if price > 0 else cost


def _lock_ingredients(names: list) -> None:
	"""Hold these ingredients until the request commits, so two deliveries of
	one ingredient are costed one after the other. Sorted: one lock order."""
	for name in sorted(names):
		frappe.db.get_value("Ingredient", name, "name", for_update=True)


def _lock_stock(names: list) -> None:
	"""Then their balance rows at every outlet, so the stock a delivery is
	averaged into holds still. Ingredient first, as consume_for_lines locks."""
	frappe.db.sql(
		"""select name from `tabIngredient Stock` where ingredient in %(names)s
		order by ingredient, name for update""", {"names": tuple(names)})


def _number(value) -> float:
	"""A finite number, or NaN, which fails every "above zero" check."""
	try:
		out = float(value)
	except (TypeError, ValueError):
		return math.nan
	return out if math.isfinite(out) else math.nan


def _delivery_line(row: dict, ing: dict) -> dict:
	"""One received row in stock units, plus what was bought as typed. Refuses
	the row before anything moves."""
	if cint(ing.get("is_made")):
		frappe.throw(_("{0} is made here. Record it with Produce, not as a delivery.")
		             .format(ing["ingredient_name"]))
	qty = _number(row.get("qty") or 0)
	if not qty > 0:
		frappe.throw(_("Received quantity must be above zero."))
	price = None
	if row.get("cost_per_unit") not in (None, ""):
		price = _number(row["cost_per_unit"])
		if not price >= 0:
			frappe.throw(_("A price cannot be below zero."))
	# the screen says which stock unit it showed: a changed one is not guessed at
	if row.get("uom") and str(row["uom"]).strip() != ing["uom"]:
		frappe.throw(_("The unit of {0} changed. Close the window and open it again.")
		             .format(ing["ingredient_name"]))
	unit, size = ing["uom"], 1.0
	if cint(row.get("in_buying_unit")):
		unit = ing["buy_uom"]
		if not unit:
			frappe.throw(_("{0} has no buying unit.").format(ing["ingredient_name"]))
		if row.get("buy_uom") and row["buy_uom"].strip() != unit:
			frappe.throw(_("The buying unit of {0} changed. Close the window and open it again.")
			             .format(ing["ingredient_name"]))
		typed = row.get("buy_size")
		size = _number(ing["buy_size"] if typed in (None, "") else typed)
		if not size > 0:
			frappe.throw(_("A buying unit must hold more than zero {0}.").format(ing["uom"]))
	return {
		"ingredient": ing["name"], "note": row.get("note"),
		"qty": qty * size, "price": None if price is None else price / size,
		"purchase_qty": qty, "purchase_uom": unit, "purchase_size": size,
		"purchase_price": price or 0,
	}


def _moment(value):
	"""A date and time as the screens send it (the site's own time, no zone
	named), or a refusal."""
	try:
		when = frappe.utils.get_datetime(value)
	except (ValueError, TypeError, OverflowError):
		when = None
	if not when or when.tzinfo:
		frappe.throw(_("Pick a date and time."))
	return when


def _when(posted_at) -> str | None:
	"""The moment a manual stock entry is dated, or None for "now"."""
	if posted_at in (None, ""):
		return None
	when = _moment(posted_at)
	if when > frappe.utils.now_datetime():
		frappe.throw(_("A stock entry cannot be dated in the future."))
	return str(when)


def _lock_for_writing(property: str, names: list) -> dict:
	"""Start a manual stock entry: hold these ingredients and their stock rows,
	then read them. One manual entry at a time per ingredient, with stock, cost
	and history read after the lock - so the transaction this request has been
	reading in ends first (nothing is written yet): its snapshot would not show
	an entry that committed while this one waited."""
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- nothing written yet; the reads after the lock need a fresh snapshot
	_lock_ingredients(names)
	_lock_stock(names)
	held = {}
	for name in names:
		ing = frappe.db.get_value(
			"Ingredient", name,
			["name", "property", "ingredient_name", "uom", "buy_uom", "buy_size", "is_made"],
			as_dict=True)
		if not ing or ing.property != property:
			frappe.throw(_("{0} belongs to another property.").format(name))
		held[name] = ing
	return held


def _priced_after(ingredient: str, posted_at: str) -> bool:
	"""A delivery with a price, still standing, dated after this moment - at
	any outlet, since an ingredient has one cost."""
	return bool(frappe.db.exists("Ingredient Ledger Entry", {
		"ingredient": ingredient, "reason": "Received", "price_entry": "Entered",
		"cancelled": 0, "posted_at": [">", posted_at]}))


@frappe.whitelist(methods=["POST"])
@require_perm("Ingredient", "manage_stock")
def receive_stock(property: str, outlet: str, rows, supplier: str | None = None,
                  invoice_no: str | None = None, posted_at: str | None = None):
	"""Goods in. rows = [{ingredient, qty, cost_per_unit?, note?, uom?,
	in_buying_unit?, buy_uom?, buy_size?}]. qty and cost_per_unit are in the
	unit chosen: the stock unit, or the buying unit with in_buying_unit
	(buy_size changes the pack size for this delivery only; uom and buy_uom are
	the units the screen showed, and a row is refused if either has changed
	since). One batch_id ties the delivery together, which is why
	this needs no Stock Receipt doctype: a receipt is just its ledger rows plus
	a supplier and an invoice number. posted_at dates a delivery that happened
	earlier; it is costed with the stock and cost as they are now."""
	from kamra.settings import get_setting

	if isinstance(rows, str):
		rows = frappe.parse_json(rows)
	if not rows:
		frappe.throw(_("Nothing to receive."))
	check_outlet(property, outlet)
	posted_at = _when(posted_at)
	held = _lock_for_writing(property, sorted({r["ingredient"] for r in rows}))
	# every row is checked before any of them moves
	lines = [_delivery_line(r, held[r["ingredient"]]) for r in rows]

	method = get_setting(property, "stock_cost_method")
	batch = uuid.uuid4().hex[:12]
	out, repriced = [], []
	for line in lines:
		ing, price = line["ingredient"], line["price"]
		on_hand = sum(float(q or 0) for q in frappe.get_all(
			"Ingredient Stock", filters={"ingredient": ing}, pluck="qty_on_hand"))
		cost = float(frappe.db.get_value("Ingredient", ing, "cost_per_unit") or 0)
		# the stock these goods join: today's total, unless a later stock take at
		# this outlet already holds them - then it is the total less them
		if posted_at and _later_count(outlet, ing, (posted_at,)):
			on_hand -= line["qty"]
		if posted_at and method != AVERAGE_COST and _priced_after(ing, posted_at):
			new_cost = cost  # a newer-dated delivery names the last price paid
		else:
			new_cost = cost_after_receipt(method, on_hand, cost, line["qty"], price)
		if new_cost != cost:
			frappe.db.set_value("Ingredient", ing, "cost_per_unit", new_cost)
			repriced.append(ing)
		after = _apply_move(
			property, outlet, ing, line["qty"], "Received",
			supplier=supplier, invoice_no=invoice_no, batch_id=batch,
			note=line["note"], cost=cost if price is None else round(price, 6),
			posted_at=posted_at,
			extra={
				**{k: line[k] for k in ("purchase_qty", "purchase_uom",
				                        "purchase_size", "purchase_price")},
				"price_entry": "Not entered" if price is None else "Entered",
				"cost_before": cost, "cost_after": new_cost,
			})
		out.append({"ingredient": ing, "qty_on_hand": after})

	from kamra.savings import log_action
	log_action("stock_receive", "POS Outlet", outlet, property,
	           rationale=f"{len(out)} ingredient(s) received"
	                     + (f" from {supplier}" if supplier else ""),
	           channel="API")
	schedule_recost(repriced)
	return {"ok": True, "batch_id": batch, "rows": out}


@frappe.whitelist(methods=["POST"])
@require_perm("Ingredient", "manage_stock")
def adjust_stock(property: str, outlet: str, rows, note: str,
                 posted_at: str | None = None):
	"""The stock take, and the escape hatch for everything this module cannot
	know. rows = [{ingredient, counted_qty}] - COUNTS, not deltas, exactly
	like laundry's return_items: a human reports what is physically on the
	shelf and the system works out its own error.

	The note is required on purpose. A write-off with no reason is precisely
	the silence this module exists to remove - the same call laundry's
	shortage guard makes when it refuses to deliver a short bag unexplained.

	Every count is recorded, a count with no difference too: it fixes what was
	on the shelf at that moment against anything dated earlier. posted_at says
	when the shelf was counted; the difference is against that moment.
	"""
	if isinstance(rows, str):
		rows = frappe.parse_json(rows)
	if not (note or "").strip():
		frappe.throw(_("A stock take needs a note - what did you count, and why "
		               "does it differ?"))
	if not rows:
		frappe.throw(_("Nothing counted."))
	check_outlet(property, outlet)
	posted_at = _when(posted_at)
	_lock_for_writing(property, sorted({r["ingredient"] for r in rows}))
	batch = uuid.uuid4().hex[:12]
	out = []
	for r in rows:
		ing = r["ingredient"]
		counted = float(r.get("counted_qty") or 0)
		name = _stock_row(property, outlet, ing, for_update=True)
		expected = float(frappe.db.get_value("Ingredient Stock", name, "qty_on_hand",
		                                     for_update=True) or 0)
		if posted_at:
			expected -= _moved_after(outlet, ing, posted_at)
		_apply_move(property, outlet, ing, 0, "Count",
		            note=note.strip()[:500], batch_id=batch,
		            set_counted=True, set_qty=counted, posted_at=posted_at)
		if abs(counted - expected) >= 1e-9:
			out.append({"ingredient": ing, "was": expected, "now": counted,
			            "variance": counted - expected})

	if out:
		from kamra.savings import log_action
		value = sum(abs(r["variance"])
		            * float(frappe.db.get_value("Ingredient", r["ingredient"],
		                                        "cost_per_unit") or 0)
		            for r in out)
		log_action("stock_count", "POS Outlet", outlet, property,
		           rationale=f"{len(out)} variance(s), ~{money_text(property, round(value))} adjusted - "
		                     f"{note.strip()[:80]}",
		           channel="API")
	return {"ok": True, "batch_id": batch, "adjusted": out}


@frappe.whitelist(methods=["POST"])
@require_perm("Ingredient", "manage_stock")
def record_wastage(property: str, outlet: str, ingredient: str, qty: float,
                   reason_note: str, posted_at: str | None = None):
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
	check_outlet(property, outlet)
	posted_at = _when(posted_at)
	_lock_for_writing(property, [ingredient])
	after = _apply_move(property, outlet, ingredient, -qty, "Wastage",
	                    note=reason_note.strip()[:500], batch_id=uuid.uuid4().hex[:12],
	                    posted_at=posted_at)
	from kamra.savings import log_action
	cost = float(frappe.db.get_value("Ingredient", ingredient, "cost_per_unit") or 0)
	log_action("stock_wastage", "Ingredient", ingredient, property,
	           rationale=f"{qty} wasted (~{money_text(property, round(qty * cost))}) - "
	                     f"{reason_note.strip()[:80]}",
	           channel="API")
	return {"ok": True, "qty_on_hand": after}


# ------------------------------------------------------------- production

@frappe.whitelist(methods=["POST"])
@require_perm("Ingredient", "manage_stock")
def produce(property: str, outlet: str, ingredient: str, qty: float,
            posted_at: str | None = None, note: str | None = None):
	"""Record a batch made at an outlet: the made ingredient goes into stock and,
	in the recipe's proportion, what it is made from comes out (3 decimals). Too
	little of something goes below zero, as everywhere. The new stock's row is
	costed at what this batch used, each other row at that ingredient's cost now.
	One batch_id, so a cancel takes back the whole batch."""
	made_qty = _number(qty or 0)
	if not made_qty > 0:
		frappe.throw(_("Say how much was made, above zero."))
	posted_at = _when(posted_at)
	note = (note or "").strip()[:500] or None
	check_outlet(property, outlet)
	# read the recipe to know what to lock, then read it again under the locks
	parts = {r.ingredient for r in _made_parts([ingredient]).get(ingredient, [])}
	held = _lock_for_writing(property, sorted({ingredient, *parts}))
	name = held[ingredient].ingredient_name
	lines = _made_parts([ingredient]).get(ingredient, [])
	if not cint(held[ingredient].is_made) or not lines:
		frappe.throw(_("{0} is not made here.").format(name))
	if {r.ingredient for r in lines} - set(held):
		frappe.throw(_("The recipe of {0} just changed. Try again.").format(name))
	per_batch = {}
	for r in lines:
		per_batch[r.ingredient] = per_batch.get(r.ingredient, 0.0) + flt(r.qty)
	batch_qty = flt(frappe.db.get_value("Ingredient", ingredient, "batch_qty"))
	if batch_qty <= 0:
		frappe.throw(_("Say how much one batch makes, above zero."))
	costs = {}
	for part in per_batch:
		if cint(held[part].is_made):
			frappe.throw(_("{0} is made here itself. Take it out of the recipe of {1}.")
			             .format(held[part].ingredient_name, name))
		costs[part] = flt(frappe.db.get_value("Ingredient", part, "cost_per_unit"))
	use = {part: round(per * made_qty / batch_qty, 3) for part, per in per_batch.items()}
	use = {part: amount for part, amount in use.items() if amount > 0}
	if not use:
		frappe.throw(_("That is too little to take anything from stock."))
	batch_cost = _made_cost([(amount, costs[part]) for part, amount in use.items()], made_qty)

	batch = uuid.uuid4().hex[:12]
	after = {}
	for part in sorted({ingredient, *use}):
		made_row = part == ingredient
		after[part] = _apply_move(
			property, outlet, part, made_qty if made_row else -use[part], "Production",
			note=note if made_row else
			     (f"For {name}: {note}" if note else f"For {name}")[:500],
			batch_id=batch, posted_at=posted_at,
			cost=batch_cost if made_row else costs[part])

	from kamra.savings import log_action
	log_action("stock_produce", "Ingredient", ingredient, property,
	           rationale=f"{made_qty:g} {held[ingredient].uom} of {name} made at {outlet}",
	           channel="API")
	return {
		"ok": True, "batch_id": batch, "qty_on_hand": after[ingredient],
		"used": [{"ingredient": part, "ingredient_name": held[part].ingredient_name,
		          "uom": held[part].uom, "qty": use[part], "qty_on_hand": after[part]}
		         for part in per_batch if part in use],
	}


# ----------------------------------------------------------------- cancel

# Every ledger reason is on one of these two lists. Only what someone typed by
# hand can be taken back; the rest (kitchen and banquet usage, the demo's
# opening rows, anything added later) is put right with a stock take.
CANCELLABLE = ("Received", "Count", "Wastage", "Production")
NOT_CANCELLABLE = ("Opening", "Consumed", "Return")


@frappe.whitelist(methods=["POST"])
@require_perm("Ingredient", "cancel_stock", scope={"entry": "Ingredient Ledger Entry"})
def cancel_stock_entry(property: str, entry: str, reason: str):
	"""Take back a delivery, a stock take or a wastage entry. `entry` is any
	line of it: a delivery or a stock take goes as a whole. The lines stay in
	history, marked cancelled, moving nothing on their date, and later
	balances and stock takes are worked again. A cancelled delivery's price is
	taken out of the cost only while that is safe; `cost_unchanged` names the
	ingredients to check by hand."""
	from kamra.settings import get_setting

	if not (reason or "").strip():
		frappe.throw(_("A reason is required to cancel."))
	first = frappe.db.get_value(
		"Ingredient Ledger Entry", entry, ["property", "batch_id"], as_dict=True)
	if not first or first.property != property:
		frappe.throw(_("Stock entry not found."))
	filters = ({"batch_id": first.batch_id, "property": property}
	           if first.batch_id else {"name": entry})
	picked = frappe.get_all(
		"Ingredient Ledger Entry", filters=filters, fields=["name", "ingredient"])
	_lock_for_writing(property, sorted({r.ingredient for r in picked}))
	# read again after the lock: someone may have cancelled it while we waited.
	# Newest first, so two lines of one ingredient are undone in turn.
	rows = frappe.get_all(
		"Ingredient Ledger Entry", filters={"name": ["in", [r.name for r in picked]]},
		fields=["name", "reason", "cancelled"], order_by="creation desc, name desc")
	if any(r.cancelled for r in rows):
		frappe.throw(_("This entry is already cancelled."))
	if any(r.reason not in CANCELLABLE for r in rows):
		frappe.throw(_("Only deliveries, stock takes, wastage and production batches can be cancelled."))
	method = get_setting(property, "stock_cost_method")
	why = reason.strip()[:500]
	unchanged, repriced = [], []
	for r in rows:
		row = _cancel_row(r.name, why)
		if row.reason != "Received":
			continue
		repriced.append(row.ingredient)
		if not _restore_cost(row, method):
			unchanged.append(
				frappe.db.get_value("Ingredient", row.ingredient, "ingredient_name"))
	schedule_recost(repriced)
	from kamra.savings import log_action
	log_action("stock_cancel", "Ingredient Ledger Entry", entry, property,
	           rationale=f"{len(rows)} stock line(s) cancelled - {why[:80]}",
	           channel="API")
	return {"ok": True, "cancelled": len(rows),
	        "cost_unchanged": list(dict.fromkeys(unchanged))}


def _cancel_row(name: str, why: str):
	"""Zero one ledger line and carry that forward. Answers with the line as it
	was. The caller holds the ingredient's locks."""
	row = frappe.db.get_value(
		"Ingredient Ledger Entry", name,
		["name", "property", "outlet", "ingredient", "reason", "qty_change",
		 "balance_after", "posted_at", "creation", "price_entry", "cost_before", "cost_after"],
		as_dict=True, for_update=True)
	delta = -float(row.qty_change or 0)
	frappe.db.set_value("Ingredient Ledger Entry", name, {
		"cancelled": 1, "cancelled_by": frappe.session.user,
		"cancelled_at": frappe.utils.now(), "cancel_reason": why,
		"original_qty_change": row.qty_change, "qty_change": 0,
		"balance_after": float(row.balance_after or 0) + delta,
	}, update_modified=False)
	stock = _stock_row(row.property, row.outlet, row.ingredient, for_update=True)
	current = float(frappe.db.get_value("Ingredient Stock", stock, "qty_on_hand",
	                                    for_update=True) or 0)
	effect = _ripple(row.outlet, row.ingredient, delta,
	                 after=(row.posted_at, row.creation, row.name))
	frappe.db.set_value("Ingredient Stock", stock, "qty_on_hand", current + effect,
	                    update_modified=False)
	if row.reason == "Count":
		_stamp_counted(stock, row.outlet, row.ingredient)
	from kamra.notifications import low_stock_crossed
	low_stock_crossed(row.property, row.outlet, row.ingredient, effect, current + effect)
	return row


def _restore_cost(row, method: str) -> bool:
	"""After a delivery line is cancelled, take its price out of the cost. False
	when the cost can no longer be worked back and someone should look at it.

	Only the cost this very line set is touched. With an average, the old cost
	returns unless a later-typed delivery was averaged on top of it - walking
	back through earlier ones already cancelled. With "last price paid", the
	newest-dated delivery still standing names the price."""
	if row.price_entry == "Not entered":
		return True  # it never touched the cost
	if row.price_entry != "Entered":
		return False  # from before prices were kept this way

	def same(a, b):
		return abs(float(a or 0) - float(b or 0)) < 1e-6

	cost = frappe.db.get_value("Ingredient", row.ingredient, "cost_per_unit")
	if not same(cost, row.cost_after):
		return False
	priced = {"ingredient": row.ingredient, "reason": "Received",
	          "price_entry": "Entered", "name": ["!=", row.name]}
	if method == AVERAGE_COST:
		if frappe.db.exists("Ingredient Ledger Entry",
		                    {**priced, "cancelled": 0, "creation": [">", row.creation]}):
			return False
		target = row.cost_before
		for earlier in frappe.get_all(
				"Ingredient Ledger Entry",
				filters={**priced, "creation": ["<", row.creation]},
				fields=["cancelled", "cost_before", "cost_after"],
				order_by="creation desc, name desc"):
			if not earlier.cancelled or not same(earlier.cost_after, target):
				break
			target = earlier.cost_before
	else:
		newest = frappe.get_all(
			"Ingredient Ledger Entry", filters={**priced, "cancelled": 0},
			fields=["cost_per_unit"], order_by="posted_at desc, creation desc", limit=1)
		target = newest[0].cost_per_unit if newest else row.cost_before
	frappe.db.set_value("Ingredient", row.ingredient, "cost_per_unit", float(target or 0))
	return True


# ----------------------------------------------------------------- reads

@frappe.whitelist()
@require_perm("Ingredient", "view_stock")
def stock_list(property: str, outlet: str, status: str | None = None,
               include_unstocked: int = 0):
	"""Everything this outlet holds. Stock is per outlet, so there is no such
	thing as a merged total across outlets and this never offers one.

	include_unstocked adds the active ingredients this outlet has never moved,
	at zero and marked stocked = 0, for the receipt, count and wastage pickers:
	a balance row only appears with the first movement, so without them a new
	ingredient could never get one."""
	rows = frappe.get_all(
		"Ingredient Stock", filters={"property": property, "outlet": outlet},
		fields=["name", "ingredient", "qty_on_hand", "par_level",
		        "last_counted_at", "last_counted_by"])
	for r in rows:
		r["stocked"] = 1
	if int(include_unstocked or 0):
		held = {r.ingredient for r in rows}
		rows += [
			frappe._dict(name=None, ingredient=name, qty_on_hand=0.0, par_level=0.0,
			             last_counted_at=None, last_counted_by=None, stocked=0)
			for name in frappe.get_all(
				"Ingredient", filters={"property": property, "is_active": 1},
				pluck="name")
			if name not in held
		]
	out = []
	for r in rows:
		meta = frappe.db.get_value(
			"Ingredient", r.ingredient,
			["ingredient_name", "uom", "buy_uom", "buy_size", "category",
			 "cost_per_unit", "is_active", "is_made"],
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
@require_perm("Ingredient", "view_stock")
def ingredient_ledger(property: str, outlet: str, ingredient: str,
                      limit: int = 50, purchases_only: int = 0,
                      from_date: str | None = None, to_date: str | None = None):
	"""Where did my paneer go? Newest first by when it happened, each row
	carrying the balance it produced, so the history explains the number on the
	shelf. Cancelled lines stay, saying who took them back and why;
	batch_ingredients names everything in the line's entry.

	purchases_only lists the deliveries alone, from every outlet of the
	property (an ingredient has one cost), with their own limit: kitchen usage
	would otherwise push them off the end."""
	purchases = cint(purchases_only)
	filters = {"property": property, "ingredient": ingredient}
	if purchases:
		filters["reason"] = "Received"
	else:
		filters["outlet"] = outlet
	if from_date or to_date:
		filters["posted_at"] = ["between", [
			f"{getdate(from_date or '1900-01-01')} 00:00:00",
			f"{getdate(to_date or nowdate())} 23:59:59.999999"]]
	rows = frappe.get_all(
		"Ingredient Ledger Entry", filters=filters,
		fields=["name", "creation", "outlet", "qty_change", "balance_after", "reason",
		        "reference_doctype", "reference_name", "note", "supplier",
		        "invoice_no", "cost_per_unit", "purchase_qty", "purchase_uom",
		        "purchase_size", "purchase_price", "price_entry", "cost_after",
		        "owner", "posted_at", "batch_id", "cancelled", "cancelled_by",
		        "cancelled_at", "cancel_reason", "original_qty_change"],
		order_by="posted_at desc, creation desc", limit=int(limit or 50))
	_name_the_entries(rows)
	if purchases and rows:
		names = {o.name: o.outlet_name for o in frappe.get_all(
			"POS Outlet", filters={"name": ["in", list({r.outlet for r in rows})]},
			fields=["name", "outlet_name"])}
		for r in rows:
			r["outlet_name"] = names.get(r.outlet)
	return rows


def _name_the_entries(rows: list) -> None:
	"""Give each line the names of every ingredient in its entry (a delivery
	or a stock take covers several): what a cancel would take back."""
	batches = {r.batch_id for r in rows if r.batch_id}
	lines = frappe.get_all(
		"Ingredient Ledger Entry",
		filters={"batch_id": ["in", list(batches) or [""]]},
		fields=["batch_id", "ingredient"], order_by="creation asc") if rows else []
	names = {i.name: i.ingredient_name for i in frappe.get_all(
		"Ingredient", filters={"name": ["in", [x.ingredient for x in lines] or [""]]},
		fields=["name", "ingredient_name"])}
	held = {}
	for x in lines:
		held.setdefault(x.batch_id, {})[names.get(x.ingredient, x.ingredient)] = 1
	for r in rows:
		r["batch_ingredients"] = list(held.get(r.batch_id, {}))


# which column of the summary each ledger reason counts in (a test keeps every
# reason listed)
SUMMARY_BUCKETS = {
	"Received": "purchases", "Consumed": "used", "Return": "used",
	"Wastage": "wastage", "Count": "adjustment", "Opening": "adjustment",
	"Production": "production",
}


@frappe.whitelist()
@require_perm("Ingredient", "view_stock")
def stock_summary(property: str, from_date: str, to_date: str,
                  outlet: str | None = None, search: str | None = None,
                  low_only: int = 0):
	"""For a period: what each ingredient started with, what came in and went
	out by kind, and what was left - per outlet, never a merged total. Days are
	the calendar days entries are dated, so a back-dated entry changes its past
	period. A row shows with stock at the start or a standing movement in the
	period; cancelled lines move nothing. low_only keeps what is at or below
	its low-stock level now."""
	start, end = getdate(from_date), getdate(to_date)
	if end < start:
		start, end = end, start
	columns = list(dict.fromkeys(SUMMARY_BUCKETS.values()))
	params = {"property": property, "outlet": outlet,
	          "start": f"{start} 00:00:00", "after": f"{add_days(end, 1)} 00:00:00"}
	sums = []
	for column in columns:
		params[column] = tuple(r for r, c in SUMMARY_BUCKETS.items() if c == column)
		sums.append(f"""sum(case when posted_at >= %(start)s and reason in %({column})s
			then qty_change else 0 end) as {column}""")
	moved = frappe.db.sql(  # nosemgrep: frappe-sql-format-injection -- the interpolated column names are the constants above; values are parameters
		f"""select outlet, ingredient,
			sum(case when posted_at < %(start)s then qty_change else 0 end) as beginning,
			sum(case when posted_at >= %(start)s and ifnull(cancelled, 0) = 0
				then 1 else 0 end) as moves,
			{", ".join(sums)}
		from `tabIngredient Ledger Entry`
		where property = %(property)s and posted_at < %(after)s
			{"and outlet = %(outlet)s" if outlet else ""}
		group by outlet, ingredient""", params, as_dict=True)
	moved = [m for m in moved if m.moves or round(float(m.beginning or 0), 6)]
	if not moved:
		return {"from": str(start), "to": str(end), "rows": []}
	ings = {i.name: i for i in frappe.get_all(
		"Ingredient", filters={"name": ["in", [m.ingredient for m in moved]]},
		fields=["name", "ingredient_name", "category", "uom"])}
	outlets = dict(frappe.get_all(
		"POS Outlet", filters={"name": ["in", [m.outlet for m in moved]]},
		fields=["name", "outlet_name"], as_list=True))
	shelf = {(s.outlet, s.ingredient): s for s in frappe.get_all(
		"Ingredient Stock", filters={"property": property,
		                             "ingredient": ["in", [m.ingredient for m in moved]]},
		fields=["outlet", "ingredient", "qty_on_hand", "par_level"])}
	wanted = (search or "").strip().lower()
	rows = []
	for m in moved:
		ing = ings.get(m.ingredient) or frappe._dict(ingredient_name=m.ingredient)
		now = shelf.get((m.outlet, m.ingredient))
		low = bool(now and float(now.par_level or 0) > 0
		           and float(now.qty_on_hand or 0) <= float(now.par_level))
		if (wanted and wanted not in (ing.ingredient_name or "").lower()) \
				or (cint(low_only) and not low):
			continue
		row = {
			"ingredient": m.ingredient, "ingredient_name": ing.ingredient_name,
			"category": ing.category, "uom": ing.uom, "outlet": m.outlet,
			"outlet_name": outlets.get(m.outlet, m.outlet),
			"beginning": round(float(m.beginning or 0), 6),
			**{c: round(float(m.get(c) or 0), 6) for c in columns},
			"low": low,
		}
		row["ending"] = round(row["beginning"] + sum(row[c] for c in columns), 6)
		rows.append(row)
	rows.sort(key=lambda r: ((r["ingredient_name"] or "").lower(), r["outlet_name"]))
	return {"from": str(start), "to": str(end), "rows": rows}


@frappe.whitelist()
@require_perm("Ingredient", "view_stock")
def stock_at(property: str, outlet: str, at: str):
	"""What the outlet's shelf held at a moment, per ingredient: today's figure
	less everything dated after it. The stock take screen compares against
	this when the count is dated in the past."""
	moment = str(_moment(at))
	held = {r.ingredient: float(r.qty_on_hand or 0) for r in frappe.get_all(
		"Ingredient Stock", filters={"property": property, "outlet": outlet},
		fields=["ingredient", "qty_on_hand"])}
	for ingredient, later in frappe.db.sql(
			"""select ingredient, sum(qty_change) from `tabIngredient Ledger Entry`
			where property = %s and outlet = %s and posted_at > %s
			group by ingredient""", (property, outlet, moment)):
		if ingredient in held:
			held[ingredient] -= float(later or 0)
	return held


@frappe.whitelist()
@require_perm("Ingredient", "view_stock")
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
		makes = frappe.get_all(
			"Menu Item Ingredient",
			filters={"ingredient": r.ingredient, "parenttype": "Ingredient"}, pluck="parent")
		r["makes"] = frappe.get_all(
			"Ingredient", filters={"name": ["in", makes], "is_active": 1},
			pluck="ingredient_name", order_by="ingredient_name asc") if makes else []
		out.append(r)
	out.sort(key=lambda r: {STATUS_NEGATIVE: 0, STATUS_OUT: 1, STATUS_LOW: 2}[r["status"]])
	return out


@frappe.whitelist()
@require_perm("Ingredient", "view_stock")
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
		select i.item_name, i.menu_item, i.qty, i.modifiers, i.void_reason, p.outlet,
		       p.name as order_name, p.creation
		  from `tabPOS Order Item` i
		  join `tabPOS Order` p on p.name = i.parent
		 where {' and '.join(conds)}
		 order by p.creation desc""", params, as_dict=True)
	if not lines:
		return {"lines": [], "by_reason": [], "total_value": 0.0}

	from kamra.menu_modifiers import option_ids_of
	recipes = _recipes_of({r.menu_item for r in lines})
	# what a line's choices took off the shelf (an extra shot's beans) was binned too
	chosen = [option_ids_of(r.pop("modifiers")) for r in lines]
	extras = _option_recipes_of({o for ids in chosen for o in ids})
	costs = {}
	total = 0.0
	by_reason = {}
	for r, ids in zip(lines, chosen):
		value = 0.0
		used = list(recipes.get(r.menu_item, ()))
		for opt in ids:
			used += extras.get(opt, ())
		for ing, per in used:
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
@require_perm("Menu Item", "edit_menu")
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
@require_perm("Ingredient", "manage_stock")
def set_par_level(property: str, outlet: str, ingredient: str, par_level: float):
	"""Where LOW starts for this ingredient at this outlet. Zero = no par."""
	try:
		par = float(par_level)
	except (TypeError, ValueError):
		frappe.throw(_("Enter a number for the low-stock level."))
	# nan and inf compare in surprising ways (nan < 0 is false) and must not
	# land in the column as a level nobody can read
	if not math.isfinite(par):
		frappe.throw(_("Enter a number for the low-stock level."))
	if par < 0:
		frappe.throw(_("A low-stock level cannot be below zero."))
	check_outlet(property, outlet)
	name = _stock_row(property, outlet, ingredient)
	frappe.db.set_value("Ingredient Stock", name, "par_level", par,
	                    update_modified=False)
	return {"ok": True}
