"""Banquets - the function business, from first phone call to final bill.

The shape of the work, and the shape of this module:

  prospect   someone calls about a wedding. `create_enquiry` opens a
             function sheet with a follow-up date, and it sits in the
             pipeline until it converts or dies with a reason.
  build      `add_menu` / `add_service` pull from the property's own
             catalogue - menu packages priced per plate, and a service
             list (LED wall, DJ, podium, stage, decor, laptop, alcohol)
             priced per event / hour / day / pax / unit. Every line
             carries a chargeable flag: complimentary items still print
             on the event order and the pack list, they just don't reach
             the quote.
  negotiate  `negotiate` moves rates and the headline discount, and
             snapshots what the quote was worth before and after, so the
             fourth revision of a wedding quote isn't a mystery. What is
             still unsettled lives as open items with a price impact.
  commit     `generate_quote` stamps a version. `set_status` moves the
             function tentative -> confirmed, and a confirmed function
             owns the hall (tentative holds don't block - they're meant
             to be pushed off by real business).
  deliver    `generate_beo` prints the event order for the banquet,
             kitchen and AV teams; `banquet_document(kind="pack_list")`
             prints what physically has to be carried to the hall.
  settle     receipts against payment terms, then `post_to_folio` when
             the function rides a group's master bill.

Pricing lives in the Venue Booking controller, not here - so a line
posted by an agent, the Desk or this API is taxed and totalled the same
way. See kamra/kamra/doctype/venue_booking/venue_booking.py.
"""

from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import (
	add_days,
	add_to_date,
	getdate,
	now_datetime,
	nowdate,
)

from kamra.authz import require_roles

# who sells and runs functions
BANQUET_ROLES = ("Front Desk", "Revenue Manager", "Kamra Agent")
# who may change what things cost
CATALOGUE_ROLES = ("Front Desk", "Revenue Manager", "Finance")
# who may see a function without being able to touch it. Housekeeping is
# in here because the floor needs the setup, the pack list and the indent.
READ_ROLES = (*BANQUET_ROLES, "Finance", "Housekeeping")

# ...but commercial reporting is a narrower room. What the pipeline is
# worth, what converted, what every client spends and the cash book are
# not the floor's business.
REPORT_ROLES = (*BANQUET_ROLES, "Finance")

OPEN = ("Enquiry", "Tentative", "Confirmed")
DEAD = ("Cancelled", "Lost")

# enquiry -> tentative -> confirmed -> completed, and out at any point.
# Reopening a dead function is deliberate, not a slip, so it's allowed
# back to Enquiry only.
TRANSITIONS = {
	"Enquiry": ("Tentative", "Confirmed", "Cancelled", "Lost"),
	"Tentative": ("Confirmed", "Enquiry", "Cancelled", "Lost"),
	"Confirmed": ("Completed", "Tentative", "Cancelled"),
	"Completed": (),
	"Cancelled": ("Enquiry",),
	"Lost": ("Enquiry",),
}

# what a catalogue category becomes on the function sheet
_CATEGORY_TYPE = {
	"Audio Visual": "Audio Visual",
	"Decor": "Decor",
	"Entertainment": "Entertainment",
	"Furniture & Setup": "Furniture & Setup",
	"Staffing": "Staffing",
	"Beverage": "Food & Beverage",
	"Alcohol": "Alcohol",
	"Accommodation": "Accommodation",
	"Stationery": "Stationery",
	"Other": "Other",
}
_UOM_FROM_CATALOGUE = {
	"Per Event": "Lot", "Per Hour": "Hour", "Per Day": "Day",
	"Per Pax": "Pax", "Per Unit": "Unit",
}


def _fn(function: str):
	return frappe.get_doc("Venue Booking", function)


def _rows(value):
	"""A list of dicts, whether it arrived as JSON over the wire or as a
	real list from an in-process caller."""
	if isinstance(value, str):
		value = frappe.parse_json(value)
	return value or []


def _map(value) -> dict:
	"""Same, for the {row_name: value} shapes."""
	if isinstance(value, str):
		value = frappe.parse_json(value)
	return value or {}


# ══ the catalogue ════════════════════════════════════════════════════════

@frappe.whitelist()
@require_roles(*READ_ROLES)
def banquet_catalogue(property: str):
	"""What the property sells: the menu packages (with their courses) and
	the service list. This is the picker behind every line item."""
	menus = frappe.get_all(
		"Banquet Menu",
		filters={"property": property, "disabled": 0},
		fields=["name", "menu_name", "menu_code", "meal_period", "food_type",
		        "service_style", "cuisine", "rate_per_pax", "min_pax",
		        "gst_rate", "inclusions", "exclusions"],
		order_by="meal_period, rate_per_pax")
	for m in menus:
		m["courses"] = frappe.get_all(
			"Banquet Menu Course", filters={"parent": m.name},
			fields=["name", "course", "dishes", "choice_of", "is_live_counter"],
			order_by="idx")
	services = frappe.get_all(
		"Banquet Service Item",
		filters={"property": property, "disabled": 0},
		fields=["name", "item_name", "category", "uom", "rate", "gst_rate",
		        "chargeable", "is_alcohol", "on_pack_list", "description"],
		order_by="category, item_name")
	venues = frappe.get_all(
		"Venue", filters={"property": property, "disabled": 0},
		fields=["name", "venue_name", "venue_code", "venue_type", "capacity",
		        "min_capacity", "area_sqft", "base_price", "hourly_rate",
		        "min_hours", "gst_rate", "setup_styles", "amenities"],
		order_by="venue_name")
	return {"menus": menus, "services": services, "venues": venues}


@frappe.whitelist(methods=["POST"])
@require_roles(*CATALOGUE_ROLES)
def save_banquet_menu(property: str, menu_name: str, rate_per_pax: float,
                      courses=None, name: str | None = None, **kw):
	"""Add or edit one menu package. Courses replace wholesale - the grid
	the user is looking at is the truth."""
	if not (menu_name or "").strip():
		frappe.throw(_("The menu needs a name."))
	if float(rate_per_pax) < 0:
		frappe.throw(_("A plate price can't be negative."))
	doc = (frappe.get_doc("Banquet Menu", name) if name
	       else frappe.new_doc("Banquet Menu"))
	doc.update({
		"property": property,
		"menu_name": menu_name.strip()[:140],
		"rate_per_pax": float(rate_per_pax),
	})
	for field in ("menu_code", "meal_period", "food_type", "service_style",
	              "cuisine", "min_pax", "gst_rate", "inclusions", "exclusions",
	              "disabled"):
		if field in kw and kw[field] is not None:
			doc.set(field, kw[field])
	if courses is not None:
		doc.set("courses", [])
		for c in _rows(courses):
			if not (c.get("course") or "").strip():
				continue
			doc.append("courses", {
				"course": c["course"].strip()[:140],
				"dishes": (c.get("dishes") or "").strip(),
				"choice_of": int(c.get("choice_of") or 0),
				"is_live_counter": 1 if c.get("is_live_counter") else 0,
			})
	doc.save()
	return {"ok": True, "name": doc.name}


@frappe.whitelist(methods=["POST"])
@require_roles(*CATALOGUE_ROLES)
def delete_banquet_menu(name: str):
	frappe.delete_doc("Banquet Menu", name)
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
@require_roles(*CATALOGUE_ROLES)
def save_service_item(property: str, item_name: str, category: str,
                      rate: float = 0, uom: str = "Per Event",
                      name: str | None = None, **kw):
	"""Add or edit one service - a projector, an LED wall, a DJ, a podium,
	a stage, a decor package, bar service. `chargeable = 0` marks the ones
	the hotel throws in as standard; they still appear on the event order
	and the pack list."""
	if not (item_name or "").strip():
		frappe.throw(_("The service needs a name."))
	if category not in _CATEGORY_TYPE:
		frappe.throw(_("Unknown category: {0}").format(category))
	doc = (frappe.get_doc("Banquet Service Item", name) if name
	       else frappe.new_doc("Banquet Service Item"))
	doc.update({
		"property": property, "item_name": item_name.strip()[:140],
		"category": category, "rate": float(rate or 0), "uom": uom,
	})
	for field in ("gst_rate", "chargeable", "is_alcohol", "on_pack_list",
	              "description", "disabled"):
		if field in kw and kw[field] is not None:
			doc.set(field, kw[field])
	doc.save()
	return {"ok": True, "name": doc.name}


@frappe.whitelist(methods=["POST"])
@require_roles(*CATALOGUE_ROLES)
def delete_service_item(name: str):
	frappe.delete_doc("Banquet Service Item", name)
	return {"ok": True}


# ══ prospecting ══════════════════════════════════════════════════════════

@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES)
def create_enquiry(property: str, venue: str, event_date: str,
                   customer_name: str, event_type: str = "Wedding",
                   attendees: int = 0, customer_phone: str | None = None,
                   customer_email: str | None = None,
                   company: str | None = None, end_date: str | None = None,
                   start_time: str | None = None, end_time: str | None = None,
                   source: str = "Phone", requirements: str | None = None,
                   follow_up_days: int = 2, with_venue_line: int = 1,
                   sales_owner: str | None = None):
	"""Open a function sheet from an enquiry. The hall's rack rental goes on
	as the first line (that's the number the conversation starts from), and
	a follow-up lands in the diary so the enquiry doesn't go quiet."""
	if not (customer_name or "").strip():
		frappe.throw(_("Whose function is this? A customer name is required."))
	doc = frappe.get_doc({
		"doctype": "Venue Booking",
		"property": property, "venue": venue,
		"event_type": event_type or "Other",
		"status": "Enquiry",
		"enquiry_date": nowdate(),
		"follow_up_date": add_days(nowdate(), int(follow_up_days or 2)),
		"source": source or "Phone",
		"sales_owner": sales_owner or frappe.session.user,
		"event_date": event_date, "end_date": end_date or None,
		"start_time": start_time or None, "end_time": end_time or None,
		"customer_name": customer_name.strip()[:140],
		"customer_phone": customer_phone, "customer_email": customer_email,
		"company": company, "attendees": int(attendees or 0),
		"requirements": requirements,
	})
	if int(with_venue_line or 0):
		v = frappe.db.get_value(
			"Venue", venue, ["venue_name", "base_price", "hourly_rate",
			                 "gst_rate"], as_dict=True)
		if v and (v.base_price or v.hourly_rate):
			hourly = bool(start_time and end_time and v.hourly_rate
			              and not v.base_price)
			doc.append("items", {
				"item_type": "Venue Rental",
				"item_name": _("{0} rental").format(v.venue_name or venue),
				"uom": "Hour" if hourly else "Lot",
				"qty": 0,  # the controller fills hours / 1
				"list_rate": float(v.hourly_rate if hourly else v.base_price),
				"rate": float(v.hourly_rate if hourly else v.base_price),
				"chargeable": 1,
				"gst_rate": float(v.gst_rate or 18),
			})
	doc.insert()
	from kamra.savings import log_action
	log_action("banquet_enquiry", "Venue Booking", doc.name, property,
	           minutes_saved=6,
	           rationale=f"{event_type} enquiry for {customer_name} "
	                     f"({attendees or '?'} pax) on {event_date}")
	return {"ok": True, "function": doc.name, "status": doc.status,
	        "grand_total": doc.grand_total}


@frappe.whitelist()
@require_roles(*READ_ROLES)
def function_sheet(function: str):
	"""One function, everything about it - the sheet the banquet screen
	renders and Kamra Agent reads."""
	doc = _fn(function)
	venue = frappe.db.get_value(
		"Venue", doc.venue, ["venue_name", "venue_type", "capacity",
		                     "base_price", "hourly_rate", "setup_styles",
		                     "amenities"], as_dict=True) or {}
	out = doc.as_dict()
	out["venue_detail"] = venue
	out["billable_pax"] = doc.billable_pax
	out["received_total"] = float(doc.advance_received or 0)
	out["scheduled_total"] = sum(
		float(t.amount or 0) for t in doc.payment_terms
		if t.status in ("Pending", "Overdue"))
	out["open_item_impact"] = sum(
		float(o.price_impact or 0) for o in doc.open_items
		if o.status == "Open")
	out["group_detail"] = None
	if doc.group_booking:
		out["group_detail"] = frappe.db.get_value(
			"Group Booking", doc.group_booking,
			["name", "group_name", "check_in_date", "check_out_date",
			 "status"], as_dict=True)
	out["next_actions"] = _function_alerts(doc)
	return out


@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES)
def update_function(function: str, fields):
	"""Edit the sheet's own fields (not its tables - those have their own
	calls, because each one means something different)."""
	editable = {
		"venue", "event_type", "event_name", "event_date", "end_date",
		"start_time", "end_time", "setup_style", "setup_notes", "setup_from",
		"teardown_by", "customer_name", "customer_phone", "customer_email",
		"company", "travel_agent", "billing_name", "gstin", "billing_address",
		"place_of_supply", "attendees", "pax_guaranteed", "pax_actual",
		"rate_basis", "source", "sales_owner", "follow_up_date",
		"tentative_until", "quote_valid_till", "contract_signed_on",
		"requirements", "beo_notes", "internal_notes", "payment_terms_note",
		"discount_amount", "group_booking", "session",
		"service_charge_percent", "refundable_deposit",
		"hall_deal", "minimum_fnb_spend",
	}
	fields = _map(fields)
	unknown = set(fields) - editable
	if unknown:
		frappe.throw(_("Not editable here: {0}").format(", ".join(sorted(unknown))))
	doc = _fn(function)
	_guard_closed(doc)
	for k, v in fields.items():
		doc.set(k, v)
	doc.save()
	return {"ok": True, "grand_total": doc.grand_total,
	        "balance_due": doc.balance_due}


def _guard_closed(doc):
	if doc.status == "Completed":
		frappe.throw(_("This function is closed. Reopen it before editing."))


@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES)
def set_status(function: str, status: str, reason: str | None = None,
               tentative_until: str | None = None):
	"""Move the function along its pipeline. Confirming takes the hall -
	the controller refuses a clash with another confirmed function."""
	doc = _fn(function)
	if status == doc.status:
		return {"ok": True, "status": status, "unchanged": True}
	allowed = TRANSITIONS.get(doc.status, ())
	if status not in allowed:
		frappe.throw(_("A {0} function can't go straight to {1}. From here: "
		              "{2}.").format(doc.status, status,
		                             ", ".join(allowed) or _("nowhere")))
	was = doc.status
	if status in DEAD:
		if not (reason or "").strip():
			frappe.throw(_("Say why - a cancelled or lost function needs a "
			              "reason so the pipeline stays honest."))
		doc.lost_reason = reason.strip()[:500]
	if status == "Tentative":
		doc.tentative_until = tentative_until or doc.tentative_until \
			or add_days(nowdate(), 7)
	if status == "Enquiry":
		doc.lost_reason = None
	doc.status = status
	doc.save()
	from kamra.savings import log_action
	log_action("banquet_status", "Venue Booking", doc.name, doc.property,
	           rationale=f"{doc.customer_name}: {was} → {status}"
	                     + (f" ({reason})" if reason else ""),
	           before_snapshot={"status": was},
	           after_snapshot={"status": status})
	return {"ok": True, "status": doc.status, "from": was,
	        "grand_total": doc.grand_total}


# ══ building the function ════════════════════════════════════════════════

@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES)
def add_menu(function: str, menu: str, qty=None, rate=None, chargeable: int = 1,
             notes: str | None = None):
	"""Put a menu package on the function. Left alone the quantity follows
	the pax rule (guaranteed, or actual if more turned up) and the price is
	the package's own plate price - pass `rate` when it's been negotiated."""
	doc = _fn(function)
	_guard_closed(doc)
	m = frappe.get_doc("Banquet Menu", menu)
	if m.property != doc.property:
		frappe.throw(_("That menu belongs to another property."))
	doc.append("items", {
		"item_type": "Menu",
		"item_name": f"{m.menu_name} ({m.meal_period})",
		"banquet_menu": m.name,
		"description": m.inclusions,
		"qty": float(qty) if qty else 0,
		"uom": "Pax",
		"list_rate": float(m.rate_per_pax or 0),
		"rate": float(rate) if rate is not None else float(m.rate_per_pax or 0),
		"cost_rate": _default_menu_cost(m),
		"chargeable": 1 if int(chargeable or 0) else 0,
		"gst_rate": float(m.gst_rate or 0),
		"notes": notes,
	})
	doc.save()
	return _line_result(doc)


@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES)
def add_service(function: str, service_item: str, qty=None, rate=None,
                chargeable=None, notes: str | None = None):
	"""Put a service on the function - projector, LED wall, DJ, podium,
	stage, decor, laptop, bar. The catalogue decides whether it's chargeable
	by default; pass `chargeable` to override for this function."""
	doc = _fn(function)
	_guard_closed(doc)
	s = frappe.get_doc("Banquet Service Item", service_item)
	if s.property != doc.property:
		frappe.throw(_("That service belongs to another property."))
	doc.append("items", {
		"item_type": _CATEGORY_TYPE.get(s.category, "Other"),
		"item_name": s.item_name,
		"service_item": s.name,
		"description": s.description,
		"qty": float(qty) if qty else 0,
		"uom": _UOM_FROM_CATALOGUE.get(s.uom, "Lot"),
		"list_rate": float(s.rate or 0),
		"rate": float(rate) if rate is not None else float(s.rate or 0),
		# the buy price rides along, or the margin on every hired LED wall
		# silently reads as 100%
		"cost_rate": float(s.cost_rate or 0),
		"chargeable": (1 if int(chargeable) else 0) if chargeable is not None
		              else (1 if s.chargeable else 0),
		"is_alcohol": 1 if s.is_alcohol else 0,
		"on_pack_list": 1 if s.on_pack_list else 0,
		"gst_rate": float(s.gst_rate or 0),
		"notes": notes,
	})
	doc.save()
	return _line_result(doc)


@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES)
def save_items(function: str, items):
	"""Replace the line grid wholesale - what the user is looking at is the
	truth. Rows keep their catalogue links so the event order can still
	print a menu's courses."""
	doc = _fn(function)
	_guard_closed(doc)
	doc.set("items", [])
	for r in _rows(items):
		if not (r.get("item_name") or "").strip():
			continue
		doc.append("items", {
			"item_type": r.get("item_type") or "Other",
			"item_name": r["item_name"].strip()[:140],
			"banquet_menu": r.get("banquet_menu") or None,
			"service_item": r.get("service_item") or None,
			"description": r.get("description"),
			"qty": float(r.get("qty") or 0),
			"uom": r.get("uom") or "Lot",
			"list_rate": float(r.get("list_rate") or 0),
			"rate": float(r.get("rate") or 0),
			"cost_rate": float(r.get("cost_rate") or 0),
			"actual_qty": float(r.get("actual_qty") or 0),
			"is_supplementary": 1 if r.get("is_supplementary") else 0,
			"chargeable": 1 if r.get("chargeable", 1) else 0,
			"is_alcohol": 1 if r.get("is_alcohol") else 0,
			"on_pack_list": 1 if r.get("on_pack_list") else 0,
			"tax_exempt": 1 if r.get("tax_exempt") else 0,
			"gst_rate": float(r.get("gst_rate") or 0),
			"notes": r.get("notes"),
		})
	doc.save()
	return _line_result(doc)


@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES)
def remove_item(function: str, row: str):
	doc = _fn(function)
	_guard_closed(doc)
	doc.set("items", [r for r in doc.items if r.name != row])
	doc.save()
	return _line_result(doc)


def _line_result(doc):
	return {
		"ok": True, "lines": len(doc.items),
		"subtotal": doc.subtotal, "tax_amount": doc.tax_amount,
		"grand_total": doc.grand_total, "balance_due": doc.balance_due,
		"non_chargeable_value": doc.non_chargeable_value,
	}


# ══ negotiation ══════════════════════════════════════════════════════════

@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES)
def negotiate(function: str, rows=None, discount_amount=None,
              note: str | None = None, venue_rental=None):
	"""The price moves. `rows` is {line_row_name: new_rate} - or pass
	`venue_rental` to move just the hall - and `discount_amount` is the
	headline reduction on the whole quote.

	Every move is snapshotted with what the quote was worth before and
	after, so the fourth revision of a wedding quote can be explained."""
	doc = _fn(function)
	_guard_closed(doc)
	before = float(doc.grand_total or 0)
	changes = []
	for row_name, new_rate in _map(rows).items():
		line = next((r for r in doc.items if r.name == row_name), None)
		if not line:
			frappe.throw(_("No such line on this function: {0}").format(row_name))
		if float(new_rate) < 0:
			frappe.throw(_("A rate can't be negative."))
		if float(line.rate or 0) != float(new_rate):
			changes.append(f"{line.item_name} {line.rate:,.0f}→{float(new_rate):,.0f}")
			line.rate = float(new_rate)
	if venue_rental is not None:
		line = next((r for r in doc.items if r.item_type == "Venue Rental"), None)
		if not line:
			frappe.throw(_("This function has no venue rental line to move."))
		if float(line.rate or 0) != float(venue_rental):
			changes.append(
				f"Hall {line.rate:,.0f}→{float(venue_rental):,.0f}")
			line.rate = float(venue_rental)
	if discount_amount is not None:
		if float(doc.discount_amount or 0) != float(discount_amount):
			changes.append(
				f"Discount {float(doc.discount_amount or 0):,.0f}"
				f"→{float(discount_amount):,.0f}")
		doc.discount_amount = float(discount_amount)
	doc.save()
	after = float(doc.grand_total or 0)
	_snapshot(doc, note or (", ".join(changes) if changes
	                        else _("Reviewed, no change")))
	from kamra.savings import log_action
	log_action("banquet_negotiate", "Venue Booking", doc.name, doc.property,
	           rationale=f"{doc.customer_name}: {before:,.0f} → {after:,.0f}"
	                     + (f" ({', '.join(changes)})" if changes else ""),
	           before_snapshot={"grand_total": before},
	           after_snapshot={"grand_total": after})
	return {"ok": True, "was": before, "now": after,
	        "moved_by": round(after - before, 2), "changes": changes,
	        "version": doc.quote_version}


def _snapshot(doc, note: str):
	"""Pin what the quote was worth at this moment. Called after the save
	that changed it, so the row records the price that resulted - which is
	what "the number we sent on the 3rd" means."""
	doc.append("revisions", {
		"version": int(doc.quote_version or 0),
		"revised_on": now_datetime(),
		"revised_by": frappe.session.user,
		"grand_total": float(doc.grand_total or 0),
		"pax": doc.billable_pax,
		"change_note": (note or "")[:500],
	})
	doc.save()


@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES)
def save_open_items(function: str, rows):
	"""What is still unsettled while the price is being agreed - the
	sangeet stage, whether the bar is on consumption, who pays for the
	extra generator. Each carries what agreeing it would do to the price."""
	doc = _fn(function)
	_guard_closed(doc)
	doc.set("open_items", [])
	for r in _rows(rows):
		if not (r.get("title") or "").strip():
			continue
		doc.append("open_items", {
			"title": r["title"].strip()[:140],
			"detail": r.get("detail"),
			"owner_side": r.get("owner_side") or "Hotel",
			"due_date": r.get("due_date") or None,
			"price_impact": float(r.get("price_impact") or 0),
			"status": r.get("status") or "Open",
		})
	doc.save()
	open_rows = [o for o in doc.open_items if o.status == "Open"]
	return {"ok": True, "open": len(open_rows),
	        "impact": sum(float(o.price_impact or 0) for o in open_rows)}


# ══ terms and money ══════════════════════════════════════════════════════

@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES, "Finance")
def set_payment_terms(function: str, terms, note: str | None = None):
	"""The schedule the customer signs up to. A term stated as a percentage
	follows the quote as it moves; one stated as an amount is a number both
	sides agreed and stays put."""
	doc = _fn(function)
	doc.set("payment_terms", [])
	for t in _rows(terms):
		if not (t.get("milestone") or "").strip():
			continue
		doc.append("payment_terms", {
			"milestone": t["milestone"].strip()[:140],
			"due_date": t.get("due_date") or None,
			"percent": float(t.get("percent") or 0),
			"amount": float(t.get("amount") or 0),
			"status": t.get("status") or "Pending",
			"received_on": t.get("received_on") or None,
			"reference": t.get("reference"),
		})
	if note is not None:
		doc.payment_terms_note = note
	doc.save()
	scheduled = sum(float(t.amount or 0) for t in doc.payment_terms)
	return {"ok": True, "terms": len(doc.payment_terms),
	        "scheduled": scheduled,
	        "unscheduled": round(float(doc.grand_total or 0) - scheduled, 2)}


@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES, "Finance")
def default_payment_terms(function: str, advance_percent: float = 25,
                          interim_percent: float = 50,
                          interim_days_before: int = 15):
	"""The usual three-milestone schedule, dated off this function: an
	advance to hold the hall, a second call before the date, the rest on
	completion. Editable afterwards like any other term."""
	doc = _fn(function)
	adv = float(advance_percent or 0)
	mid = float(interim_percent or 0)
	if adv + mid > 100:
		frappe.throw(_("The advance and interim add up to more than the bill."))
	terms = [
		{"milestone": _("Booking advance"), "percent": adv,
		 "due_date": nowdate()},
		{"milestone": _("Before the function"), "percent": mid,
		 "due_date": add_days(doc.event_date, -int(interim_days_before or 15))},
		{"milestone": _("On completion"), "percent": round(100 - adv - mid, 2),
		 "due_date": doc.end_date or doc.event_date},
	]
	return set_payment_terms(function, [t for t in terms if t["percent"] > 0])


@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES, "Finance")
def record_receipt(function: str, amount: float, mode: str = "Bank Transfer",
                   kind: str = "Advance", reference: str | None = None,
                   receipt_date: str | None = None, settle_term: str | None = None):
	"""Money in against the function. Pass `settle_term` to tick off the
	payment-term row it pays, so the schedule and the ledger agree."""
	if float(amount) <= 0:
		frappe.throw(_("A receipt has to be a positive amount - use kind "
		              "'Refund' to give money back."))
	if kind not in ("Advance", "Payment", "Security Deposit", "Refund"):
		frappe.throw(_("Unknown receipt kind: {0}").format(kind))
	doc = _fn(function)
	doc.append("receipts", {
		"receipt_date": receipt_date or nowdate(),
		"kind": kind, "mode": mode, "amount": float(amount),
		"reference": reference, "received_by": frappe.session.user,
	})
	if settle_term:
		term = next((t for t in doc.payment_terms if t.name == settle_term), None)
		if not term:
			frappe.throw(_("No such payment term on this function."))
		term.status = "Received"
		term.received_on = receipt_date or nowdate()
		term.reference = reference or term.reference
	doc.save()
	from kamra.savings import log_action
	log_action("banquet_receipt", "Venue Booking", doc.name, doc.property,
	           rationale=f"{kind} ₹{float(amount):,.0f} ({mode}) for "
	                     f"{doc.customer_name} - balance ₹{doc.balance_due:,.0f}")
	return {"ok": True, "received": doc.advance_received,
	        "balance_due": doc.balance_due}


@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES)
def assign_green_room(function: str, room: str | None = None,
                      from_date: str | None = None, to_date: str | None = None,
                      complimentary: int = 1, rate: float = 0):
	"""Hold a changing room for the wedding party. The controller puts a
	Room Block on it so it genuinely leaves the sellable inventory; pass
	`complimentary=0` (with a rate) to bill it as an Accommodation line."""
	doc = _fn(function)
	_guard_closed(doc)
	doc.green_room = room or None
	if room:
		doc.green_room_from = from_date or doc.event_date
		doc.green_room_to = to_date or doc.end_date or doc.event_date
	else:
		doc.green_room_from = doc.green_room_to = None
	doc.green_room_complimentary = 1 if int(complimentary or 0) else 0
	# keep the billing line in step with the decision
	doc.set("items", [r for r in doc.items
	                  if not (r.item_type == "Accommodation"
	                          and r.notes == "green-room")])
	if room:
		room_no = frappe.db.get_value("Room", room, "room_number") or room
		doc.append("items", {
			"item_type": "Accommodation",
			"item_name": _("Green room ({0})").format(room_no),
			"qty": 1, "uom": "Day",
			"list_rate": float(rate or 0), "rate": float(rate or 0),
			"chargeable": 0 if int(complimentary or 0) else 1,
			"notes": "green-room",
		})
	doc.save()
	return {"ok": True, "green_room": doc.green_room,
	        "block": doc.green_room_block, "grand_total": doc.grand_total}


# ══ availability and the diary ═══════════════════════════════════════════

@frappe.whitelist()
@require_roles(*READ_ROLES)
def venue_availability(property: str, event_date: str,
                       end_date: str | None = None,
                       start_time: str | None = None,
                       end_time: str | None = None, pax: int = 0,
                       exclude: str | None = None):
	"""Which halls are free for these dates and hours. A confirmed function
	takes the hall; a tentative one is shown as a soft hold you can still
	sell over. Halls too small for the pax are flagged, not hidden."""
	from kamra.kamra.doctype.venue_booking.venue_booking import overlapping

	venues = frappe.get_all(
		"Venue", filters={"property": property, "disabled": 0},
		fields=["name", "venue_name", "venue_type", "capacity", "min_capacity",
		        "base_price", "hourly_rate", "min_hours", "setup_styles"],
		order_by="capacity")
	out = []
	for v in venues:
		hard = overlapping(property, v.name, event_date, end_date, start_time,
		                   end_time, exclude=exclude, statuses=("Confirmed",))
		soft = overlapping(property, v.name, event_date, end_date, start_time,
		                   end_time, exclude=exclude, statuses=("Tentative",))
		fits = not (pax and v.capacity and int(pax) > int(v.capacity))
		too_big = bool(pax and v.min_capacity and int(pax) < int(v.min_capacity))
		out.append({
			**v,
			"available": not hard,
			"fits": fits,
			"under_minimum": too_big,
			"conflicts": [dict(c, kind="confirmed") for c in hard]
			             + [dict(c, kind="tentative") for c in soft],
		})
	return {"date": event_date, "end_date": end_date,
	        "start_time": start_time, "end_time": end_time,
	        "pax": int(pax or 0), "venues": out}


@frappe.whitelist()
@require_roles(*READ_ROLES)
def banquet_calendar(property: str, start_date: str | None = None,
                     days: int = 31, status: str | None = None):
	"""The function diary - halls down the side, days across the top, every
	function in its cell with what it's worth and what's still owed.
	Multi-day functions appear on each of their days."""
	start = getdate(start_date or nowdate())
	days = max(1, min(int(days or 31), 62))
	last = add_days(start, days - 1)
	venues = frappe.get_all(
		"Venue", filters={"property": property, "disabled": 0},
		fields=["name", "venue_name", "venue_type", "capacity", "base_price"],
		order_by="venue_name")
	filters = {"property": property, "event_date": ("<=", str(last))}
	if status:
		filters["status"] = status
	rows = frappe.get_all(
		"Venue Booking", filters=filters,
		fields=["name", "venue", "event_type", "event_name", "status",
		        "event_date", "end_date", "start_time", "end_time",
		        "customer_name", "company", "attendees", "pax_guaranteed",
		        "pax_actual", "grand_total", "advance_received", "balance_due",
		        "setup_style", "sales_owner"],
		order_by="event_date, start_time")
	by_venue: dict[str, dict[str, list]] = {}
	for b in rows:
		first, final = getdate(b.event_date), getdate(b.end_date or b.event_date)
		if final < start:
			continue
		b["start_time"] = str(b.start_time or "")[:5]
		b["end_time"] = str(b.end_time or "")[:5]
		b["event_date"] = str(b.event_date)
		b["end_date"] = str(b.end_date) if b.end_date else None
		b["pax"] = b.pax_actual or b.pax_guaranteed or b.attendees or 0
		span = (final - first).days + 1
		for i in range(span):
			d = add_days(first, i)
			if start <= d <= last:
				cell = dict(b, day_index=i + 1, day_span=span)
				by_venue.setdefault(b.venue, {}).setdefault(
					str(d), []).append(cell)
	dates = [str(add_days(start, i)) for i in range(days)]
	for v in venues:
		cells = by_venue.get(v.name, {})
		v["bookings"] = [b for d in dates for b in cells.get(d, [])]
		v["by_date"] = cells
	return {"start": str(start), "days": days, "dates": dates,
	        "venues": venues}


# ══ month-wise tracking ══════════════════════════════════════════════════

@frappe.whitelist()
@require_roles(*REPORT_ROLES, "Hotel Admin")
def banquet_pipeline(property: str, from_date: str | None = None,
                     to_date: str | None = None, months: int = 6):
	"""The sales view: where the business is by month and by status, what
	converted, what died and why. Dated on the event, not the enquiry -
	a banquet team's month is the month the function happens."""
	start = getdate(from_date) if from_date else getdate(nowdate()).replace(day=1)
	end = getdate(to_date) if to_date else add_to_date(
		start, months=int(months or 6), days=-1)
	rows = frappe.get_all(
		"Venue Booking",
		filters={"property": property,
		         "event_date": ("between", [str(start), str(end)])},
		fields=["name", "venue", "event_type", "status", "event_date",
		        "customer_name", "company", "attendees", "pax_guaranteed",
		        "pax_actual", "grand_total", "advance_received", "balance_due",
		        "source", "sales_owner", "lost_reason", "enquiry_date"],
		order_by="event_date")

	def bucket():
		return {"count": 0, "value": 0.0, "pax": 0}

	by_month: dict[str, dict] = {}
	by_status, by_type, by_venue, by_source = {}, {}, {}, {}
	for r in rows:
		month = str(r.event_date)[:7]
		value = float(r.grand_total or 0)
		pax = int(r.pax_actual or r.pax_guaranteed or r.attendees or 0)
		m = by_month.setdefault(month, {
			"month": month, "statuses": {},
			"confirmed_value": 0.0, "pipeline_value": 0.0,
			"lost_value": 0.0, "count": 0, "pax": 0,
			"received": 0.0, "outstanding": 0.0})
		m["count"] += 1
		m["pax"] += pax
		s = m["statuses"].setdefault(r.status, bucket())
		s["count"] += 1
		s["value"] += value
		s["pax"] += pax
		if r.status in ("Confirmed", "Completed"):
			m["confirmed_value"] += value
			m["received"] += float(r.advance_received or 0)
			m["outstanding"] += float(r.balance_due or 0)
		elif r.status in ("Enquiry", "Tentative"):
			m["pipeline_value"] += value
		else:
			m["lost_value"] += value
		for store, key in ((by_status, r.status), (by_type, r.event_type),
		                   (by_venue, r.venue), (by_source, r.source)):
			b = store.setdefault(key or "Unknown", bucket())
			b["count"] += 1
			b["value"] += value
			b["pax"] += pax

	won = sum(1 for r in rows if r.status in ("Confirmed", "Completed"))
	dead = sum(1 for r in rows if r.status in DEAD)
	decided = won + dead
	lost_reasons: dict[str, int] = {}
	for r in rows:
		if r.status in DEAD and r.lost_reason:
			key = r.lost_reason.strip().split("\n")[0][:60]
			lost_reasons[key] = lost_reasons.get(key, 0) + 1

	def listed(store):
		return sorted(
			({"key": k, **v} for k, v in store.items()),
			key=lambda x: -x["value"])

	return {
		"from": str(start), "to": str(end),
		"months": [by_month[k] for k in sorted(by_month)],
		"by_status": listed(by_status),
		"by_event_type": listed(by_type),
		"by_venue": listed(by_venue),
		"by_source": listed(by_source),
		"totals": {
			"functions": len(rows),
			"confirmed_value": sum(
				float(r.grand_total or 0) for r in rows
				if r.status in ("Confirmed", "Completed")),
			"pipeline_value": sum(
				float(r.grand_total or 0) for r in rows
				if r.status in ("Enquiry", "Tentative")),
			"outstanding": sum(
				float(r.balance_due or 0) for r in rows
				if r.status in ("Confirmed", "Completed")),
			"conversion_rate": round(won / decided * 100, 1) if decided else None,
		},
		"lost_reasons": sorted(
			({"reason": k, "count": v} for k, v in lost_reasons.items()),
			key=lambda x: -x["count"]),
	}


# ══ reminders ════════════════════════════════════════════════════════════

def _function_alerts(doc):
	"""What this one function needs from somebody today."""
	today = getdate(nowdate())
	event = getdate(doc.event_date)
	days_out = (event - today).days
	out = []
	if doc.status in ("Enquiry", "Tentative") and doc.follow_up_date \
			and getdate(doc.follow_up_date) <= today:
		out.append({"kind": "follow_up", "urgency": "high",
		            "message": _("Follow-up was due {0}.").format(
			            doc.follow_up_date)})
	if doc.status == "Tentative" and doc.tentative_until \
			and getdate(doc.tentative_until) <= add_days(today, 3):
		out.append({"kind": "hold_expiring", "urgency": "high",
		            "message": _("The tentative hold on {0} runs out {1}.")
		            .format(doc.venue, doc.tentative_until)})
	for term in doc.payment_terms:
		if term.status in ("Pending", "Overdue") and term.due_date \
				and getdate(term.due_date) <= add_days(today, 3):
			out.append({"kind": "payment_due",
			            "urgency": "high" if term.status == "Overdue" else "normal",
			            "message": _("{0}: {1} due {2}.").format(
				            term.milestone,
				            frappe.format_value(float(term.amount or 0), "Currency"),
				            term.due_date)})
	if doc.status == "Confirmed":
		if 0 <= days_out <= 7 and not doc.beo_generated_on:
			out.append({"kind": "beo_missing", "urgency": "high",
			            "message": _("No event order yet and the function is "
			                        "in {0} days.").format(days_out)})
		if 0 <= days_out <= 3 and not doc.pax_guaranteed:
			out.append({"kind": "pax_missing", "urgency": "high",
			            "message": _("No guaranteed pax - the kitchen can't "
			                        "order.")})
		if 0 <= days_out <= 14 and not doc.contract_signed_on:
			out.append({"kind": "contract_unsigned", "urgency": "normal",
			            "message": _("The contract is still unsigned.")})
		if 0 <= days_out <= 14 and not float(doc.advance_received or 0):
			out.append({"kind": "no_advance", "urgency": "high",
			            "message": _("Nothing received yet against "
			                        "{0}.").format(frappe.format_value(
				            float(doc.grand_total or 0), "Currency"))})
		open_rows = [o for o in doc.open_items if o.status == "Open"]
		if open_rows and days_out <= 7:
			out.append({"kind": "open_items", "urgency": "normal",
			            "message": _("{0} open item(s) still unsettled.")
			            .format(len(open_rows))})
	if doc.status == "Confirmed" and days_out < 0:
		out.append({"kind": "close_it", "urgency": "normal",
		            "message": _("The function has passed - close it and "
		                        "settle the bill.")})
	return out


@frappe.whitelist()
@require_roles(*READ_ROLES)
def banquet_reminders(property: str, days: int = 30):
	"""Everything across the property that needs chasing - the banquet
	team's morning list."""
	horizon = add_days(nowdate(), int(days or 30))
	filters = {"property": property, "status": ("in", list(OPEN)),
	           "event_date": ("<=", horizon)}
	total_open = frappe.db.count("Venue Booking", filters)
	# each function is opened in full (its terms and open items decide what
	# it needs), so the window is capped rather than left unbounded
	names = frappe.get_all("Venue Booking", filters=filters, pluck="name",
	                       order_by="event_date", limit=250)
	out = []
	for name in names:
		doc = frappe.get_doc("Venue Booking", name)
		alerts = _function_alerts(doc)
		if alerts:
			out.append({
				"function": doc.name, "customer_name": doc.customer_name,
				"venue": doc.venue, "event_date": str(doc.event_date),
				"status": doc.status, "grand_total": doc.grand_total,
				"balance_due": doc.balance_due,
				"sales_owner": doc.sales_owner, "alerts": alerts,
			})
	out.sort(key=lambda x: (
		0 if any(a["urgency"] == "high" for a in x["alerts"]) else 1,
		x["event_date"]))
	return {"property": property, "count": len(out), "functions": out,
	        "scanned": len(names), "open_functions": total_open,
	        "truncated": total_open > len(names)}


def run_banquet_reminders():
	"""Scheduled: nudge whoever owns each function about what it needs.
	Follows the housekeeping escalation path - WhatsApp where a channel is
	wired, the activity log either way."""
	from kamra.housekeeping import _notify_role
	from kamra.savings import log_action

	for prop in frappe.get_all("Property", pluck="name"):
		try:
			board = banquet_reminders(prop, days=45)
		except Exception:
			frappe.log_error(title="banquet reminders", message=frappe.get_traceback())
			continue
		urgent = [f for f in board["functions"]
		          if any(a["urgency"] == "high" for a in f["alerts"])]
		if not urgent:
			continue
		for f in urgent[:20]:
			body = _("Banquet: {0} at {1} on {2} - {3}").format(
				f["customer_name"], f["venue"], f["event_date"],
				"; ".join(a["message"] for a in f["alerts"]
				          if a["urgency"] == "high"))
			sent = False
			if f["sales_owner"]:
				mobile = frappe.db.get_value("User", f["sales_owner"], "mobile_no")
				if mobile:
					try:
						from kamra.agents_channels import send_outbound
						send_outbound(prop, "WhatsApp", mobile, body)
						sent = True
					except Exception:
						pass  # fall through to role notify when WhatsApp is unavailable
			if not sent:
				_notify_role(prop, "Front Desk", body)
			log_action("banquet_reminder", "Venue Booking", f["function"], prop,
			           minutes_saved=3, rationale=body)


# ══ documents ════════════════════════════════════════════════════════════

_DOC_KINDS = ("quote", "contract", "beo", "pack_list", "invoice")


@frappe.whitelist()
@require_roles(*READ_ROLES)
def banquet_document(function: str, kind: str = "quote"):
	"""The paper. One shape for every document so the front end can print
	them all the same way:

	  quote      what it costs, line by line, with the terms
	  contract   the quote plus the terms, the policy and signature blocks
	  beo        the banquet event order - the running sheet for the day
	  pack_list  what physically has to reach the hall, and by when
	  invoice    the bill, against what's already been received
	"""
	if kind not in _DOC_KINDS:
		frappe.throw(_("Unknown document: {0}").format(kind))
	doc = _fn(function)
	prop = frappe.db.get_value(
		"Property", doc.property,
		["property_name", "legal_name", "address_line", "city", "state",
		 "pincode", "country", "phone", "email", "website", "gstin",
		 "logo_url"], as_dict=True) or {}
	prop["address"] = ", ".join(filter(None, [  # nosemgrep: frappe-no-functional-code -- drops empty address parts
		prop.get("address_line"), prop.get("city"), prop.get("state"),
		prop.get("pincode")]))
	venue = frappe.db.get_value(
		"Venue", doc.venue, ["venue_name", "venue_type", "capacity"],
		as_dict=True) or {}

	from kamra import localization as loc

	pack = loc.pack_for(doc.property)
	ctx = pack.invoice_context(frappe.get_cached_doc("Property", doc.property))
	prop_doc = frappe.get_cached_doc("Property", doc.property)

	# the number a customer quotes back at you - each document has its own
	number = {
		"quote": doc.quote_number, "contract": doc.quote_number,
		"invoice": doc.invoice_number, "beo": doc.beo_number,
	}.get(kind) or doc.name
	issued = {
		"quote": doc.quote_sent_on, "contract": doc.contract_signed_on,
		"invoice": doc.invoice_date,
		"beo": str(doc.beo_generated_on or "")[:10] or None,
	}.get(kind)

	header = {
		"kind": kind,
		"title": {"quote": _("Quotation"), "contract": _("Function Contract"),
		          "beo": _("Banquet Event Order"), "pack_list": _("Pack List"),
		          "invoice": _("Tax Invoice")}[kind],
		"number": number,
		"is_final": bool(number != doc.name),
		"function": doc.name,
		"reference": doc.name,
		"issued_on": str(issued) if issued else None,
		"version": int(doc.quote_version or 0),
		"printed_on": str(now_datetime()),
		"valid_till": str(doc.quote_valid_till) if doc.quote_valid_till else None,
		"beo_number": doc.beo_number,
		"amount_in_words": loc.amount_in_words(pack, prop_doc, doc.grand_total),
		"service_code_label": (ctx.get("service_code") or {}).get("label", "SAC"),
		"footer": ctx.get("footer"),
		"place_of_supply": ctx.get("place_of_supply"),
		"tax_label": ctx.get("tax_label"),
		"tax_id_label": ctx.get("tax_id_label"),
	}
	customer = {
		"name": doc.billing_name or doc.customer_name,
		"contact": doc.customer_name,
		"phone": doc.customer_phone, "email": doc.customer_email,
		"company": doc.company, "gstin": doc.gstin,
		"address": doc.billing_address,
		"place_of_supply": doc.place_of_supply,
	}
	event = {
		"event_name": doc.event_name, "event_type": doc.event_type,
		"venue": venue.get("venue_name") or doc.venue,
		"venue_type": venue.get("venue_type"),
		"event_date": str(doc.event_date),
		"end_date": str(doc.end_date) if doc.end_date else None,
		"start_time": str(doc.start_time or "")[:5],
		"end_time": str(doc.end_time or "")[:5],
		"hours": doc.billable_hours,
		"setup_style": doc.setup_style, "setup_notes": doc.setup_notes,
		"setup_from": str(doc.setup_from) if doc.setup_from else None,
		"teardown_by": str(doc.teardown_by) if doc.teardown_by else None,
		"pax_expected": doc.attendees, "pax_guaranteed": doc.pax_guaranteed,
		"pax_actual": doc.pax_actual, "billable_pax": doc.billable_pax,
		"rate_basis": doc.rate_basis,
		"green_room": doc.green_room,
		"green_room_complimentary": bool(doc.green_room_complimentary),
	}

	def line(r):
		code = loc.service_code_for(pack, prop_doc, r.item_type)
		return {
			"row": r.name, "item_type": r.item_type, "item_name": r.item_name,
			"service_code": (code or {}).get("value"),
			"description": r.description, "qty": r.qty, "uom": r.uom,
			"list_rate": r.list_rate, "rate": r.rate,
			"chargeable": bool(r.chargeable), "is_alcohol": bool(r.is_alcohol),
			"on_pack_list": bool(r.on_pack_list),
			"amount": r.amount, "net_amount": r.net_amount,
			"gst_rate": r.gst_rate, "gst_amount": r.gst_amount,
			"total": r.total, "notes": r.notes,
			"banquet_menu": r.banquet_menu,
		}

	chargeable = [line(r) for r in doc.items if r.chargeable]
	complimentary = [line(r) for r in doc.items if not r.chargeable]
	totals = {
		"subtotal": doc.subtotal, "discount": doc.discount_amount,
		"taxable": doc.taxable_amount, "tax": doc.tax_amount,
		"grand_total": doc.grand_total,
		"complimentary_value": doc.non_chargeable_value,
		"received": doc.advance_received, "balance_due": doc.balance_due,
		"tax_summary": _tax_summary(doc),
	}
	body = {
		"header": header, "property": prop, "customer": customer,
		"event": event, "totals": totals,
		"tax_breakup": _tax_breakup(doc, loc.tax_split(pack, prop_doc, doc.gstin)),
		"lines": chargeable, "complimentary": complimentary,
		"terms": [{"milestone": t.milestone,
		           "due_date": str(t.due_date) if t.due_date else None,
		           "percent": t.percent, "amount": t.amount,
		           "status": t.status, "reference": t.reference}
		          for t in doc.payment_terms],
		"terms_note": doc.payment_terms_note,
		"open_items": [{"title": o.title, "detail": o.detail,
		                "owner_side": o.owner_side, "status": o.status,
		                "due_date": str(o.due_date) if o.due_date else None,
		                "price_impact": o.price_impact}
		               for o in doc.open_items],
		"requirements": doc.requirements,
	}

	if kind in ("beo", "pack_list"):
		body["menus"] = _menu_detail(doc)
		body["notes"] = doc.beo_notes
	if kind == "pack_list":
		body["pack"] = _pack_list(doc)
	if kind == "contract":
		body["signatures"] = [
			{"for": prop.get("property_name") or doc.property,
			 "role": _("Authorised signatory")},
			{"for": customer["name"], "role": _("Client")},
		]
		body["signed_on"] = str(doc.contract_signed_on) \
			if doc.contract_signed_on else None
	if kind == "invoice":
		body["receipts"] = [
			{"date": str(r.receipt_date), "kind": r.kind, "mode": r.mode,
			 "amount": r.amount, "reference": r.reference}
			for r in doc.receipts]
	return body


def _tax_summary(doc):
	"""GST grouped by rate - what the invoice has to show line by rate."""
	buckets: dict[float, dict] = {}
	for r in doc.items:
		if not r.chargeable:
			continue
		rate = float(r.gst_rate or 0)
		b = buckets.setdefault(rate, {"gst_rate": rate, "taxable": 0.0,
		                              "tax": 0.0})
		b["taxable"] += float(r.net_amount or 0)
		b["tax"] += float(r.gst_amount or 0)
	return [buckets[k] for k in sorted(buckets)]


def _tax_breakup(doc, split):
	"""Tax by rate, split into the parts the invoice has to name - CGST and
	SGST here, a single VAT line elsewhere. The country pack decides."""
	buckets: dict = {}
	for r in doc.items:
		if not r.chargeable:
			continue
		rate = float(r.gst_rate or 0)
		b = buckets.setdefault(rate, {"rate": rate, "taxable": 0.0, "tax": 0.0})
		b["taxable"] += float(r.net_amount or 0)
		b["tax"] += float(r.gst_amount or 0)
	return [{
		"rate": k, "taxable": v["taxable"], "total_tax": v["tax"],
		"parts": [{"label": label.upper(),
		           "rate": round(k * float(share), 4),
		           "amount": v["tax"] * float(share)}
		          for label, share in split],
	} for k, v in sorted(buckets.items())]


def _menu_detail(doc):
	"""The courses behind every menu line - what the kitchen actually cooks.

	Once the customer has chosen, their picks are the truth: the card that
	prints is the food they'll be served, not everything the package could
	have offered. Until then it falls back to the catalogue, so a menu is
	printable the day it's quoted."""
	chosen: dict = {}
	for s in doc.selections:
		chosen.setdefault(s.banquet_menu, {}).setdefault(
			s.course or "", []).append(s)

	out = []
	seen = set()
	for r in doc.items:
		if not r.banquet_menu or r.banquet_menu in seen:
			continue
		seen.add(r.banquet_menu)
		m = frappe.get_doc("Banquet Menu", r.banquet_menu)
		picks = chosen.get(m.name)
		if picks:
			courses = [{
				"course": course or _("Chosen"),
				"dishes": ", ".join(x.dish_name for x in rows),
				"choice_of": 0, "is_live_counter": False,
				"kitchen": rows[0].kitchen,
				"notes": "; ".join(x.note for x in rows if x.note) or None,
			} for course, rows in picks.items()]
		else:
			courses = [{"course": c.course, "dishes": c.dishes,
			            "choice_of": c.choice_of,
			            "is_live_counter": bool(c.is_live_counter),
			            "kitchen": None, "notes": None}
			           for c in m.courses]
		out.append({
			"row": r.name, "menu": m.name, "menu_name": m.menu_name,
			"menu_code": m.menu_code, "meal_period": m.meal_period,
			"food_type": m.food_type, "service_style": m.service_style,
			"cuisine": m.cuisine, "pax": r.actual_qty or r.qty,
			"chargeable": bool(r.chargeable),
			"chosen": bool(picks),
			"inclusions": m.inclusions, "exclusions": m.exclusions,
			"courses": courses,
		})
	return out


def _pack_list(doc):
	"""What has to be carried to the hall, grouped the way it gets loaded.
	Complimentary items are on it too - the podium still needs moving."""
	groups: dict[str, list] = {}
	for r in doc.items:
		if not r.on_pack_list:
			continue
		groups.setdefault(r.item_type, []).append({
			"item_name": r.item_name, "qty": r.qty, "uom": r.uom,
			"chargeable": bool(r.chargeable), "notes": r.notes,
			"description": r.description,
		})
	return {
		"deliver_by": str(doc.setup_from) if doc.setup_from
		              else f"{doc.event_date} {str(doc.start_time or '')[:5]}",
		"collect_after": str(doc.teardown_by) if doc.teardown_by else None,
		"venue": doc.venue,
		"groups": [{"group": k, "items": v} for k, v in sorted(groups.items())],
		"total_items": sum(len(v) for v in groups.values()),
	}


@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES)
def generate_quote(function: str, valid_days: int = 15,
                   note: str | None = None):
	"""Stamp a quotation. Bumps the version, dates it, and snapshots what
	it was worth - so 'the price we sent on the 3rd' is answerable."""
	doc = _fn(function)
	if not doc.items:
		frappe.throw(_("There's nothing to quote yet - put some lines on it."))
	doc.quote_version = int(doc.quote_version or 0) + 1
	if not doc.quote_number:
		from frappe.model.naming import make_autoname
		doc.quote_number = make_autoname(f"QTN-{str(doc.event_date)[:4]}-.#####")
	doc.quote_sent_on = nowdate()
	doc.quote_valid_till = add_days(nowdate(), int(valid_days or 15))
	doc.save()
	_snapshot(doc, note or _("Quote v{0} issued").format(doc.quote_version))
	from kamra.savings import log_action
	log_action("banquet_quote", "Venue Booking", doc.name, doc.property,
	           minutes_saved=20,
	           rationale=f"Quote v{doc.quote_version} for {doc.customer_name}: "
	                     f"₹{doc.grand_total:,.0f} ({len(doc.items)} lines)")
	return banquet_document(function, "quote")


@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES)
def generate_beo(function: str):
	"""Issue the banquet event order - the sheet the banquet, kitchen and
	AV teams run the day from. Only a confirmed function gets one; the
	teams shouldn't be preparing for business that isn't sold."""
	doc = _fn(function)
	if doc.status not in ("Confirmed", "Completed"):
		frappe.throw(_("Only a confirmed function gets an event order - this "
		              "one is {0}.").format(doc.status))
	if not doc.beo_number:
		doc.beo_number = f"BEO-{str(doc.event_date)[:4]}-{doc.name.split('-')[-1]}"
	doc.beo_generated_on = now_datetime()
	doc.save()
	from kamra.savings import log_action
	log_action("banquet_beo", "Venue Booking", doc.name, doc.property,
	           minutes_saved=25,
	           rationale=f"Event order {doc.beo_number} for {doc.customer_name} "
	                     f"({doc.billable_pax} pax on {doc.event_date})")
	return banquet_document(function, "beo")


@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES, "Finance")
def generate_invoice(function: str):
	"""Raise the tax invoice for a function.

	The number is assigned once and never moves - re-printing an invoice
	must give the same document, because the customer's books and ours
	have to agree on what it was called."""
	doc = _fn(function)
	if doc.status not in ("Confirmed", "Completed"):
		frappe.throw(_("Invoice a confirmed function, not a {0} one.")
		             .format(doc.status))
	if not doc.items:
		frappe.throw(_("There's nothing to invoice."))
	if not doc.invoice_number:
		from frappe.model.naming import make_autoname
		doc.invoice_number = make_autoname(
			f"BINV-{str(doc.event_date)[:4]}-.#####")
		doc.invoice_date = nowdate()
		doc.save()
		from kamra.savings import log_action
		log_action("banquet_invoice", "Venue Booking", doc.name, doc.property,
		           minutes_saved=10,
		           rationale=f"Invoice {doc.invoice_number} for "
		                     f"{doc.customer_name}: ₹{doc.grand_total:,.0f}")
	return banquet_document(function, "invoice")


# ══ settlement ═══════════════════════════════════════════════════════════

_FOLIO_CHARGE_TYPE = {
	"Menu": "Food & Beverage",
	"Food & Beverage": "Food & Beverage",
	"Alcohol": "Food & Beverage",
	"Accommodation": "Room",
}


@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES, "Finance")
def post_to_folio(function: str, folio: str | None = None):
	"""Push the chargeable lines onto a bill. A function tied to a group
	rides the group's master folio; otherwise pass one explicitly.

	Alcohol is reported back rather than posted when the bill is a company
	or group folio - the same rule the folio itself enforces - so it can be
	settled separately instead of failing the whole post."""
	from kamra.api import add_folio_charge

	doc = _fn(function)
	if doc.posted_to_folio:
		frappe.throw(_("This function has already been billed to {0}.")
		             .format(doc.folio))
	if doc.status not in ("Confirmed", "Completed"):
		frappe.throw(_("Bill a confirmed function, not a {0} one.")
		             .format(doc.status))
	target = folio or doc.folio
	if not target and doc.group_booking:
		target = frappe.db.get_value(
			"Folio", {"group_booking": doc.group_booking, "folio_type": "Group",
			          "status": "Open"}, "name")
		if not target:
			from kamra.folio import open_group_folio
			target = open_group_folio(doc.group_booking)
	if not target:
		frappe.throw(_("There's no bill to post to. Tie the function to a "
		              "group booking, or pass a folio."))

	folio_type = frappe.db.get_value("Folio", target, "folio_type")
	posted, deferred = [], []
	for r in doc.items:
		if not r.chargeable or not float(r.net_amount or 0):
			continue
		if r.is_alcohol and folio_type in ("Company", "Group"):
			deferred.append({"item_name": r.item_name,
			                 "amount": float(r.total or 0)})
			continue
		add_folio_charge(
			target,
			_FOLIO_CHARGE_TYPE.get(r.item_type, "Misc"),
			f"{doc.name} · {r.item_name}"
			+ (f" ({r.qty:g} {r.uom})" if r.qty else ""),
			float(r.net_amount),
			gst_rate=float(r.gst_rate or 0),
			is_alcohol=1 if r.is_alcohol else 0)
		posted.append({"item_name": r.item_name, "amount": float(r.net_amount)})

	doc.folio = target
	# the flag is the double-post guard, so it goes up the moment anything
	# reached the bill - alcohol lines that couldn't ride a company folio
	# are reported back, not silently left for a second run to duplicate
	doc.posted_to_folio = 1 if posted else 0
	if deferred:
		note = _("Settle separately (alcohol can't ride a company bill): "
		         "{0}").format(", ".join(d["item_name"] for d in deferred))
		doc.internal_notes = ((doc.internal_notes + "\n")
		                      if doc.internal_notes else "") + note
	doc.save()
	from kamra.savings import log_action
	log_action("banquet_billed", "Venue Booking", doc.name, doc.property,
	           minutes_saved=15,
	           rationale=f"{len(posted)} line(s) of {doc.customer_name}'s "
	                     f"function posted to {target}"
	                     + (f"; {len(deferred)} to settle separately"
	                        if deferred else ""))
	return {"ok": True, "folio": target, "posted": posted,
	        "settle_separately": deferred,
	        "note": _("Alcohol can't ride a company bill - settle those lines "
	                  "separately.") if deferred else None}


# ══ the close-out ════════════════════════════════════════════════════════

@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES, "Finance")
def close_out(function: str, damage_amount: float = 0,
              damage_note: str | None = None, refund_deposit: int = 1,
              refund_mode: str = "Bank Transfer",
              pax_actual: int | None = None):
	"""Hand the hall back. The last ritual of a function, and the one that
	usually happens on a WhatsApp message and a scrap of paper: walk the
	room, count the actual covers, note what got broken, take that off the
	deposit and give the rest back.

	Doing it here means the deduction has a reason attached, the refund is
	a real ledger line, and the function closes in one motion instead of
	three people remembering to do three things.
	"""
	doc = _fn(function)
	if doc.status not in ("Confirmed", "Completed"):
		frappe.throw(_("Only a confirmed function can be closed out - this "
		              "one is {0}.").format(doc.status))
	if doc.closed_out_on:
		frappe.throw(_("This function was already closed out on {0}.")
		             .format(doc.closed_out_on))
	damage = float(damage_amount or 0)
	if damage < 0:
		frappe.throw(_("Damages can't be negative."))
	if damage and not (damage_note or "").strip():
		frappe.throw(_("Say what was damaged - a deduction the customer "
		              "can't see the reason for is a dispute waiting."))
	held = float(doc.deposit_held or 0)
	if damage > held and held:
		frappe.throw(_("Damages of {0} exceed the {1} held. Bill the "
		              "difference as a charge instead of over-deducting.")
		             .format(frappe.format_value(damage, "Currency"),
		                     frappe.format_value(held, "Currency")))
	if pax_actual is not None:
		doc.pax_actual = int(pax_actual)

	refund = 0.0
	if int(refund_deposit or 0) and held:
		refund = round(held - damage, 2)
		if refund > 0:
			doc.append("receipts", {
				"receipt_date": nowdate(), "kind": "Refund",
				"mode": refund_mode, "amount": refund,
				"reference": _("Deposit returned")
				             + (f" (less {damage:,.0f} damages)" if damage else ""),
				"received_by": frappe.session.user,
			})
	doc.damage_amount = damage
	doc.damage_note = (damage_note or "").strip()[:500] or None
	doc.deposit_refunded = float(doc.deposit_refunded or 0) + refund
	doc.closed_out_on = now_datetime()
	doc.closed_out_by = frappe.session.user
	if damage:
		# the hotel keeps the damage money: it's revenue, not a deposit
		doc.append("items", {
			"item_type": "Other", "item_name": _("Damage recovery"),
			"description": doc.damage_note, "qty": 1, "uom": "Lot",
			"rate": damage, "list_rate": damage, "chargeable": 1,
			"notes": "damage-recovery",
		})
	doc.status = "Completed"
	doc.save()
	from kamra.savings import log_action
	log_action("banquet_close_out", "Venue Booking", doc.name, doc.property,
	           minutes_saved=10,
	           rationale=f"{doc.customer_name} closed out - "
	                     f"{doc.billable_pax} actual pax, "
	                     f"₹{damage:,.0f} damages, ₹{refund:,.0f} returned")
	return {"ok": True, "status": doc.status, "damage": damage,
	        "refunded": refund, "deposit_held": doc.deposit_held,
	        "balance_due": doc.balance_due, "grand_total": doc.grand_total}


@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES, "Finance")
def receipt_document(function: str, receipt: str):
	"""One receipt, as a document the customer can keep. Every advance a
	banquet office takes needs a piece of paper against it - this is that
	piece of paper."""
	doc = _fn(function)
	row = next((r for r in doc.receipts if r.name == receipt), None)
	if not row:
		frappe.throw(_("No such receipt on this function."))
	prop = frappe.db.get_value(
		"Property", doc.property,
		["property_name", "legal_name", "address_line", "city", "state",
		 "pincode", "phone", "email", "gstin", "logo_url"], as_dict=True) or {}
	from kamra import localization as loc

	pack = loc.pack_for(doc.property)
	prop_doc = frappe.get_cached_doc("Property", doc.property)
	return {
		"header": {
			"kind": "receipt", "title": _("Receipt"),
			"reference": f"{doc.name}/{row.idx}",
			"receipt_no": row.name,
			"date": str(row.receipt_date),
			"printed_on": str(now_datetime()),
			"amount_in_words": loc.amount_in_words(pack, prop_doc, row.amount),
		},
		"property": prop,
		"customer": {
			"name": doc.billing_name or doc.customer_name,
			"contact": doc.customer_name, "phone": doc.customer_phone,
			"email": doc.customer_email, "company": doc.company,
			"gstin": doc.gstin, "address": doc.billing_address,
		},
		"event": {
			"function": doc.name, "event_type": doc.event_type,
			"event_name": doc.event_name, "venue": doc.venue,
			"session": doc.session, "event_date": str(doc.event_date),
			"pax": doc.billable_pax,
		},
		"receipt": {
			"kind": row.kind, "mode": row.mode, "amount": row.amount,
			"reference": row.reference, "received_by": row.received_by,
		},
		"running": {
			"grand_total": doc.grand_total,
			"received": doc.advance_received,
			"deposit_held": doc.deposit_held,
			"balance_due": doc.balance_due,
		},
	}


@frappe.whitelist()
@require_roles(*READ_ROLES)
def menu_card(function: str):
	"""The menu the customer signs off - what will actually be served,
	course by course, with nothing about money on it. The kitchen and the
	customer read the same sheet, which is the whole point."""
	doc = _fn(function)
	prop = frappe.db.get_value(
		"Property", doc.property,
		["property_name", "legal_name", "address_line", "city", "phone",
		 "logo_url"], as_dict=True) or {}
	return {
		"header": {"kind": "menu_card", "title": _("Selected Menu"),
		           "reference": doc.name,
		           "printed_on": str(now_datetime())},
		"property": prop,
		"event": {
			"customer": doc.customer_name, "phone": doc.customer_phone,
			"company": doc.company,
			"event_name": doc.event_name, "event_type": doc.event_type,
			"venue": doc.venue, "session": doc.session,
			"event_date": str(doc.event_date),
			"end_date": str(doc.end_date) if doc.end_date else None,
			"pax": doc.billable_pax,
			"setup_style": doc.setup_style,
		},
		"menus": _menu_detail(doc),
		# what's being served that isn't on a menu package: the bar, the
		# live counters bought as services, the cake
		"extras": [
			{"item_name": r.item_name, "description": r.description,
			 "qty": r.qty, "uom": r.uom, "chargeable": bool(r.chargeable)}
			for r in doc.items
			if r.item_type in ("Food & Beverage", "Alcohol") and not r.banquet_menu
		],
		"notes": doc.beo_notes,
		"signatures": [
			{"for": doc.customer_name, "role": _("Customer")},
			{"for": prop.get("property_name") or doc.property,
			 "role": _("Banquet manager")},
		],
	}


# ══ the month at a glance ════════════════════════════════════════════════

@frappe.whitelist()
@require_roles(*READ_ROLES)
def month_availability(property: str, month: str | None = None):
	"""Every hall × every session, across a whole month.

	The question a banquet office is actually asked - "do you have the
	14th of December?" - is about a hall and a session, not a range of
	hours. This is the grid that answers it in one look: halls down the
	side split by session, days across the top, and what's in each cell.
	"""
	from frappe.utils import get_first_day, get_last_day

	anchor = getdate(f"{month}-01") if month else getdate(nowdate())
	start, end = get_first_day(anchor), get_last_day(anchor)
	venues = frappe.get_all(
		"Venue", filters={"property": property, "disabled": 0},
		fields=["name", "venue_name", "venue_type", "capacity", "base_price"],
		order_by="venue_name")
	rows = frappe.get_all(
		"Venue Booking",
		filters={"property": property,
		         "event_date": ("<=", str(end)),
		         "status": ("in", list(OPEN) + ["Completed"])},
		fields=["name", "venue", "session", "status", "event_date", "end_date",
		        "customer_name", "event_type", "event_name", "grand_total",
		        "attendees", "pax_guaranteed", "pax_actual", "balance_due"])

	days = (end - start).days + 1
	dates = [str(add_days(start, i)) for i in range(days)]
	# venue -> session -> date -> [functions]
	cells: dict = {}
	for b in rows:
		first = getdate(b.event_date)
		last = getdate(b.end_date or b.event_date)
		if last < start:
			continue
		b["event_date"] = str(b.event_date)
		b["pax"] = b.pax_actual or b.pax_guaranteed or b.attendees or 0
		sessions = (["Morning", "Afternoon", "Evening"]
		            if b.session in ("Full Day", None, "")
		            else [b.session if b.session != "Custom Hours" else "Evening"])
		for i in range((last - first).days + 1):
			d = add_days(first, i)
			if not (start <= d <= end):
				continue
			for s in sessions:
				(cells.setdefault(b.venue, {}).setdefault(s, {})
				 .setdefault(str(d), []).append(dict(b, spans_day=(last > first))))

	out = []
	for v in venues:
		for s in ("Morning", "Afternoon", "Evening"):
			booked = cells.get(v.name, {}).get(s, {})
			out.append({
				"venue": v.name, "venue_name": v.venue_name,
				"venue_type": v.venue_type, "capacity": v.capacity,
				"base_price": v.base_price, "session": s,
				"by_date": booked,
				"sold_days": len(booked),
			})
	return {
		"month": str(start)[:7], "start": str(start), "end": str(end),
		"dates": dates, "rows": out, "venues": venues,
		"utilisation": round(
			sum(r["sold_days"] for r in out) / (len(out) * days) * 100, 1)
		if out and days else 0,
	}


# ══ the registers ════════════════════════════════════════════════════════

_REGISTERS = ("functions", "quotations", "enquiries", "receipts", "sales")


@frappe.whitelist()
@require_roles(*REPORT_ROLES, "Hotel Admin")
def banquet_register(property: str, register: str = "functions",
                     from_date: str | None = None, to_date: str | None = None):
	"""The listings a banquet office runs the week on - the same five books
	every hall has kept on paper forever, dated and totalled:

	  functions   every booking in the window, with pax, rate and value
	  quotations  what was quoted, and whether it converted
	  enquiries   what came in, and what happened to it
	  receipts    the cash book: every payment, by mode
	  sales       revenue by hall, event type and month
	"""
	if register not in _REGISTERS:
		frappe.throw(_("Unknown register: {0}").format(register))
	start = getdate(from_date) if from_date else getdate(nowdate()).replace(day=1)
	end = getdate(to_date) if to_date else add_to_date(start, months=1, days=-1)

	base = {"property": property,
	        "event_date": ("between", [str(start), str(end)])}
	fields = ["name", "event_date", "end_date", "session", "status",
	          "customer_name", "company", "customer_phone", "venue",
	          "event_type", "event_name", "attendees", "pax_guaranteed",
	          "pax_actual", "subtotal", "discount_amount", "service_charge",
	          "tax_amount", "grand_total", "advance_received", "balance_due",
	          "quote_version", "quote_sent_on", "enquiry_date", "source",
	          "sales_owner", "lost_reason", "creation"]

	if register == "enquiries":
		filters = {"property": property,
		           "enquiry_date": ("between", [str(start), str(end)])}
	elif register == "quotations":
		filters = dict(base, quote_version=(">", 0))
	else:
		filters = base

	rows = frappe.get_all("Venue Booking", filters=filters, fields=fields,
	                      order_by="event_date, venue", limit=2000)
	for r in rows:
		r["pax"] = r.pax_actual or r.pax_guaranteed or r.attendees or 0
		r["rate_per_pax"] = round(
			float(r.grand_total or 0) / r["pax"], 2) if r["pax"] else 0
		r["event_date"] = str(r.event_date)
		r["end_date"] = str(r.end_date) if r.end_date else None

	title = {
		"functions": _("Function register"),
		"quotations": _("Quotations issued"),
		"enquiries": _("Enquiries received"),
		"receipts": _("Receipts"),
		"sales": _("Sales summary"),
	}[register]
	out = {"register": register, "title": title, "property": property,
	       "from": str(start), "to": str(end), "rows": rows,
	       "totals": {
		       "count": len(rows),
		       "pax": sum(r["pax"] for r in rows),
		       "value": sum(float(r.grand_total or 0) for r in rows),
		       "received": sum(float(r.advance_received or 0) for r in rows),
		       "outstanding": sum(float(r.balance_due or 0) for r in rows),
	       }}

	if register == "receipts":
		# the cash book reads by payment, not by function
		names = [r["name"] for r in rows] or [""]
		lines = frappe.get_all(
			"Banquet Receipt",
			filters={"parent": ("in", names),
			         "receipt_date": ("between", [str(start), str(end)])},
			fields=["name", "parent", "receipt_date", "kind", "mode", "amount",
			        "reference", "received_by"],
			order_by="receipt_date, creation", limit=5000)
		by_function = {r["name"]: r for r in rows}
		by_mode: dict = {}
		for line in lines:
			fn = by_function.get(line.parent, {})
			line["customer_name"] = fn.get("customer_name")
			line["venue"] = fn.get("venue")
			line["event_date"] = fn.get("event_date")
			signed = -float(line.amount or 0) if line.kind == "Refund" \
				else float(line.amount or 0)
			line["signed_amount"] = signed
			by_mode[line.mode] = by_mode.get(line.mode, 0.0) + signed
		out["rows"] = lines
		out["by_mode"] = sorted(
			({"mode": k, "amount": v} for k, v in by_mode.items()),
			key=lambda x: -x["amount"])
		out["totals"] = {"count": len(lines),
		                 "value": sum(x["signed_amount"] for x in lines)}

	if register == "sales":
		def roll(key):
			acc: dict = {}
			for r in rows:
				if r.status in DEAD:
					continue
				k = r.get(key) or "Unknown"
				slot = acc.setdefault(k, {"key": k, "count": 0, "pax": 0,
				                          "value": 0.0, "received": 0.0})
				slot["count"] += 1
				slot["pax"] += r["pax"]
				slot["value"] += float(r.grand_total or 0)
				slot["received"] += float(r.advance_received or 0)
			return sorted(acc.values(), key=lambda x: -x["value"])

		out["by_venue"] = roll("venue")
		out["by_event_type"] = roll("event_type")
		out["by_session"] = roll("session")
		out["by_source"] = roll("source")
		out["rows"] = [r for r in rows if r.status not in DEAD]
		out["totals"]["value"] = sum(
			float(r.grand_total or 0) for r in out["rows"])
	return out


# ══ the dish library and what a menu costs ═══════════════════════════════
# The sell side was always modelled; this is the buy side. A banquet dish
# carries a recipe against the SAME Ingredient master the restaurant uses,
# so one cost feed serves both kitchens and a function can finally answer
# "what did we make on it?".

def _dish_cost(doc) -> float:
	"""One portion, from the recipe."""
	total = 0.0
	for r in doc.recipe:
		cost = frappe.db.get_value("Ingredient", r.ingredient, "cost_per_unit")
		total += float(r.qty or 0) * float(cost or 0)
	return round(total, 4)


@frappe.whitelist()
@require_roles(*READ_ROLES)
def dish_library(property: str, course_type: str | None = None):
	"""Every dish the banquet kitchen can produce, with what it costs to
	make. This is the picker behind menu building and the spine of margin."""
	filters = {"property": property, "disabled": 0}
	if course_type:
		filters["course_type"] = course_type
	dishes = frappe.get_all(
		"Banquet Dish", filters=filters,
		fields=["name", "dish_name", "course_type", "food_type", "kitchen",
		        "portion_per_pax", "cost_per_portion", "allergens",
		        "description"],
		order_by="course_type, dish_name")
	for d in dishes:
		d["recipe"] = frappe.get_all(
			"Menu Item Ingredient",
			filters={"parent": d.name, "parenttype": "Banquet Dish"},
			fields=["name", "ingredient", "qty", "note"], order_by="idx")
	return dishes


@frappe.whitelist(methods=["POST"])
@require_roles(*CATALOGUE_ROLES)
def save_dish(property: str, dish_name: str, recipe=None,
              name: str | None = None, **kw):
	"""Add or edit a dish. The recipe is what makes it cost something -
	without one the dish is free, and so is the margin it reports."""
	if not (dish_name or "").strip():
		frappe.throw(_("The dish needs a name."))
	doc = (frappe.get_doc("Banquet Dish", name) if name
	       else frappe.new_doc("Banquet Dish"))
	doc.update({"property": property, "dish_name": dish_name.strip()[:140]})
	for field in ("course_type", "food_type", "kitchen", "portion_per_pax",
	              "allergens", "description", "disabled"):
		if field in kw and kw[field] is not None:
			doc.set(field, kw[field])
	if recipe is not None:
		doc.set("recipe", [])
		for r in _rows(recipe):
			if not r.get("ingredient") or float(r.get("qty") or 0) <= 0:
				continue
			doc.append("recipe", {"ingredient": r["ingredient"],
			                      "qty": float(r["qty"]),
			                      "note": r.get("note")})
	doc.cost_per_portion = _dish_cost(doc)
	doc.save()
	return {"ok": True, "name": doc.name,
	        "cost_per_portion": doc.cost_per_portion}


@frappe.whitelist(methods=["POST"])
@require_roles(*CATALOGUE_ROLES)
def delete_dish(name: str):
	frappe.delete_doc("Banquet Dish", name)
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
@require_roles(*CATALOGUE_ROLES)
def recost_dishes(property: str):
	"""Ingredient prices moved - re-cost every dish. Run it after a delivery
	or a price revision, so quotes stop being priced off last season's
	onions."""
	changed = []
	for name in frappe.get_all("Banquet Dish", filters={"property": property},
	                           pluck="name"):
		doc = frappe.get_doc("Banquet Dish", name)
		was = float(doc.cost_per_portion or 0)
		now = _dish_cost(doc)
		if abs(now - was) > 0.001:
			doc.cost_per_portion = now
			doc.save()
			changed.append({"dish": doc.dish_name, "was": was, "now": now})
	return {"ok": True, "recosted": len(changed), "changes": changed[:50]}


def _default_menu_cost(menu_doc) -> float:
	"""What the package costs before anyone has chosen - its default dishes.
	Without this a fresh quote reads as pure margin until the menu is
	composed, which is the most flattering possible lie."""
	by_course = _dish_options(menu_doc)
	total = 0.0
	for c in menu_doc.courses:
		offered = by_course.get(c.course, [])
		picks = [d for d in offered if d.is_default] or offered
		if c.choice_of:
			picks = picks[: int(c.choice_of)]
		for d in picks:
			dish = frappe.db.get_value(
				"Banquet Dish", d.dish,
				["cost_per_portion", "portion_per_pax"], as_dict=True) or {}
			total += float(dish.get("cost_per_portion") or 0) * float(
				dish.get("portion_per_pax") or 1)
	return round(total, 4)


def _dish_options(menu_doc) -> dict:
	"""Course name -> the dishes it offers.

	They live on the MENU rather than inside each course row because Frappe
	has no nested child tables - a Table field on a child doctype never
	materialises. Each row names its course instead."""
	out: dict = {}
	for d in menu_doc.get("dish_options") or []:
		out.setdefault(d.course, []).append(d)
	return out


@frappe.whitelist()
@require_roles(*READ_ROLES)
def menu_cost(menu: str, pax: int = 0):
	"""What one plate of this menu costs to make, and what it earns.

	Costs the DEFAULT selection - one dish per choice where the course
	offers a choice, everything where it doesn't - so a menu can be judged
	before anyone has booked it."""
	m = frappe.get_doc("Banquet Menu", menu)
	courses, cost = [], 0.0
	by_course = _dish_options(m)
	for c in m.courses:
		offered = by_course.get(c.course, [])
		picks = [d for d in offered if d.is_default] or list(offered)
		if c.choice_of:
			picks = picks[: int(c.choice_of)]
		line = 0.0
		for d in picks:
			dish = frappe.db.get_value(
				"Banquet Dish", d.dish,
				["cost_per_portion", "portion_per_pax"], as_dict=True) or {}
			line += float(dish.get("cost_per_portion") or 0) * float(
				dish.get("portion_per_pax") or 1)
		cost += line
		courses.append({"course": c.course, "dishes": len(picks),
		                "cost_per_pax": round(line, 2),
		                "costed": bool(offered)})
	sell = float(m.rate_per_pax or 0)
	pax = int(pax or m.min_pax or 0)
	return {
		"menu": m.name, "menu_name": m.menu_name,
		"rate_per_pax": sell, "cost_per_pax": round(cost, 2),
		"margin_per_pax": round(sell - cost, 2),
		"margin_percent": round((sell - cost) / sell * 100, 2) if sell else 0,
		"courses": courses,
		"uncosted_courses": [c["course"] for c in courses if not c["costed"]],
		"at_pax": {"pax": pax, "revenue": round(sell * pax, 2),
		           "cost": round(cost * pax, 2)} if pax else None,
	}


# ══ what the customer chose ══════════════════════════════════════════════

@frappe.whitelist()
@require_roles(*READ_ROLES)
def menu_choices(function: str, menu: str):
	"""The course-by-course picker for one menu on one function: what the
	course offers, how many the guest may take, and what's chosen so far."""
	doc = _fn(function)
	m = frappe.get_doc("Banquet Menu", menu)
	chosen = {(s.course, s.dish_name) for s in doc.selections
	          if s.banquet_menu == menu}
	by_course = _dish_options(m)
	out = []
	for c in m.courses:
		options = []
		for d in by_course.get(c.course, []):
			dish = frappe.db.get_value(
				"Banquet Dish", d.dish,
				["dish_name", "food_type", "kitchen", "cost_per_portion",
				 "portion_per_pax", "allergens"], as_dict=True) or {}
			options.append({
				"dish": d.dish, "dish_name": dish.get("dish_name"),
				"food_type": dish.get("food_type"),
				"kitchen": dish.get("kitchen"),
				"allergens": dish.get("allergens"),
				"cost_per_portion": dish.get("cost_per_portion"),
				"portion_per_pax": dish.get("portion_per_pax") or 1,
				"supplement_per_pax": d.supplement_per_pax,
				"is_default": bool(d.is_default),
				"chosen": (c.course, dish.get("dish_name")) in chosen,
			})
		out.append({
			"course": c.course, "choice_of": c.choice_of,
			"is_live_counter": bool(c.is_live_counter),
			"free_text": c.dishes, "options": options,
			"chosen_count": sum(1 for o in options if o["chosen"]),
		})
	return {"menu": m.name, "menu_name": m.menu_name,
	        "meal_period": m.meal_period, "courses": out}


@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES)
def compose_menu(function: str, menu: str, picks):
	"""Record what the customer actually chose - "one soup of these two, the
	paneer not the mushroom".

	The dish NAME is stored alongside the link on purpose: renaming a dish
	next season must not rewrite a menu card the customer already signed.
	Any supplement the choice carries goes on as its own line, because an
	upgrade is a price change and should be visible as one."""
	doc = _fn(function)
	_guard_closed(doc)
	if not frappe.db.exists("Banquet Menu", menu):
		frappe.throw(_("No such menu."))

	# the picks for THIS menu are replaced; other menus on the function stay
	doc.set("selections", [s for s in doc.selections if s.banquet_menu != menu])
	supplement = 0.0
	for r in _rows(picks):
		dish = frappe.db.get_value(
			"Banquet Dish", r.get("dish"),
			["dish_name", "food_type", "kitchen", "cost_per_portion",
			 "portion_per_pax"], as_dict=True) if r.get("dish") else None
		name = (dish or {}).get("dish_name") or r.get("dish_name")
		if not name:
			continue
		supplement += float(r.get("supplement_per_pax") or 0)
		doc.append("selections", {
			"banquet_menu": menu, "course": r.get("course"),
			"dish": r.get("dish") or None, "dish_name": name,
			"food_type": (dish or {}).get("food_type"),
			"kitchen": (dish or {}).get("kitchen"),
			"cost_per_portion": (dish or {}).get("cost_per_portion") or 0,
			"portion_per_pax": (dish or {}).get("portion_per_pax") or 1,
			"supplement_per_pax": float(r.get("supplement_per_pax") or 0),
			"note": r.get("note"),
		})

	# the menu line now costs what these dishes cost, per head
	per_pax = sum(float(s.cost_per_portion or 0) * float(s.portion_per_pax or 1)
	              for s in doc.selections if s.banquet_menu == menu)
	for row in doc.items:
		if row.banquet_menu == menu:
			row.cost_rate = round(per_pax, 4)

	_sync_supplement(doc, menu, supplement)
	doc.save()
	return {"ok": True,
	        "chosen": len([s for s in doc.selections if s.banquet_menu == menu]),
	        "cost_per_pax": round(per_pax, 2),
	        "supplement_per_pax": round(supplement, 2),
	        "grand_total": doc.grand_total,
	        "margin_percent": doc.margin_percent}


def _sync_supplement(doc, menu: str, per_pax: float):
	"""An upgraded dish is a price change; it belongs on the quote as its
	own line, not buried in the package rate."""
	tag = f"supplement:{menu}"
	doc.set("items", [r for r in doc.items if r.notes != tag])
	if per_pax <= 0:
		return
	menu_name = frappe.db.get_value("Banquet Menu", menu, "menu_name") or menu
	doc.append("items", {
		"item_type": "Menu", "banquet_menu": menu,
		"item_name": _("{0} - upgrades").format(menu_name),
		"qty": 0, "uom": "Pax", "list_rate": per_pax, "rate": per_pax,
		"chargeable": 1, "notes": tag,
	})


# ══ the kitchen ══════════════════════════════════════════════════════════

@frappe.whitelist()
@require_roles(*READ_ROLES, "Housekeeping")
def kitchen_indent(function: str):
	"""What the kitchen has to buy and pull for this function.

	The artifact that has always sat between the event order and the store
	room, written by hand: chosen dishes x portions x guaranteed pax,
	exploded through the recipes into ingredient quantities, checked against
	what's actually on the shelf.
	"""
	doc = _fn(function)
	pax = doc.billable_pax
	if not pax:
		frappe.throw(_("Set the guaranteed pax first - an indent without a "
		              "headcount is a guess."))

	dishes = [s for s in doc.selections if s.dish]
	if not dishes:
		frappe.throw(_("Nothing chosen yet. Compose the menu, then the "
		              "kitchen can be told what to pull."))

	recipes: dict = {}
	for r in frappe.get_all(
		"Menu Item Ingredient",
		filters={"parent": ("in", [s.dish for s in dishes]),
		         "parenttype": "Banquet Dish"},
		fields=["parent", "ingredient", "qty"], order_by="idx"):
		recipes.setdefault(r.parent, []).append((r.ingredient, float(r.qty or 0)))

	need: dict = {}
	uncosted = []
	for s in dishes:
		lines = recipes.get(s.dish)
		if not lines:
			uncosted.append(s.dish_name)
			continue
		portions = float(s.portion_per_pax or 1) * pax
		for ingredient, qty in lines:
			slot = need.setdefault(ingredient, {"ingredient": ingredient,
			                                    "qty": 0.0, "dishes": []})
			slot["qty"] += qty * portions
			if s.dish_name not in slot["dishes"]:
				slot["dishes"].append(s.dish_name)

	rows = []
	for ingredient, slot in need.items():
		meta = frappe.db.get_value(
			"Ingredient", ingredient,
			["ingredient_name", "uom", "cost_per_unit", "category"],
			as_dict=True) or {}
		on_hand = sum(float(x or 0) for x in frappe.get_all(
			"Ingredient Stock", filters={"ingredient": ingredient},
			pluck="qty_on_hand"))
		qty = round(slot["qty"], 3)
		rows.append({
			"ingredient": ingredient,
			"ingredient_name": meta.get("ingredient_name"),
			"category": meta.get("category"), "uom": meta.get("uom"),
			"required": qty, "on_hand": round(on_hand, 3),
			"short_by": round(max(0.0, qty - on_hand), 3),
			"cost": round(qty * float(meta.get("cost_per_unit") or 0), 2),
			"for_dishes": slot["dishes"],
		})
	rows.sort(key=lambda r: (-r["short_by"], r["ingredient_name"] or ""))

	by_kitchen: dict = {}
	for s in dishes:
		by_kitchen.setdefault(s.kitchen or "Main Kitchen", []).append({
			"dish": s.dish_name, "course": s.course,
			"food_type": s.food_type,
			"portions": round(float(s.portion_per_pax or 1) * pax, 1),
			"note": s.note,
		})

	return {
		"function": doc.name, "customer_name": doc.customer_name,
		"event_date": str(doc.event_date), "session": doc.session,
		"venue": doc.venue, "pax": pax,
		"ingredients": rows,
		"total_cost": round(sum(r["cost"] for r in rows), 2),
		"shortfall_lines": sum(1 for r in rows if r["short_by"] > 0),
		"by_kitchen": [{"kitchen": k, "dishes": v}
		               for k, v in sorted(by_kitchen.items())],
		"uncosted": uncosted,
	}


@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES, "Housekeeping")
def issue_indent(function: str, outlet: str, rows=None):
	"""Pull the indent off the shelf. Writes real stock movements through
	the same single writer the restaurant uses, so the store room reflects
	a banquet the way it reflects a table."""
	from kamra.inventory import _apply_move

	doc = _fn(function)
	if doc.status not in ("Confirmed", "Completed"):
		frappe.throw(_("Issue against a confirmed function, not a {0} one.")
		             .format(doc.status))
	wanted = _rows(rows) if rows else kitchen_indent(function)["ingredients"]
	moved = []
	for r in wanted:
		qty = float(r.get("required") or r.get("qty") or 0)
		if qty <= 0:
			continue
		after = _apply_move(
			doc.property, outlet, r["ingredient"], -qty, "Consumption",
			ref_dt="Venue Booking", ref_dn=doc.name,
			note=_("Banquet indent for {0}").format(doc.customer_name))
		moved.append({"ingredient": r["ingredient"], "qty": qty,
		              "balance_after": after})
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional
	from kamra.savings import log_action
	log_action("banquet_indent", "Venue Booking", doc.name, doc.property,
	           minutes_saved=20,
	           rationale=f"{len(moved)} ingredient line(s) issued for "
	                     f"{doc.customer_name} ({doc.billable_pax} pax)")
	return {"ok": True, "issued": len(moved), "lines": moved}


# ══ during the event ═════════════════════════════════════════════════════

@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES)
def record_consumption(function: str, rows=None, pax_actual: int | None = None):
	"""What was actually served, against what was quoted.

	The quote said 300 plates; 318 people ate and the bar went through
	another two cases. Until this is recorded the bill is a forecast -
	rows = {line_row_name: actual_qty}."""
	doc = _fn(function)
	_guard_closed(doc)
	if pax_actual is not None:
		doc.pax_actual = int(pax_actual)
	changes = []
	for row_name, qty in _map(rows).items():
		line = next((r for r in doc.items if r.name == row_name), None)
		if not line:
			frappe.throw(_("No such line on this function: {0}").format(row_name))
		if float(qty) < 0:
			frappe.throw(_("A served quantity can't be negative."))
		if float(line.qty or 0) != float(qty):
			changes.append(f"{line.item_name} {line.qty:g}→{float(qty):g}")
		line.actual_qty = float(qty)
	doc.save()
	from kamra.savings import log_action
	if changes:
		log_action("banquet_consumption", "Venue Booking", doc.name,
		           doc.property,
		           rationale=f"{doc.customer_name}: " + ", ".join(changes[:6]))
	return {"ok": True, "grand_total": doc.grand_total,
	        "balance_due": doc.balance_due, "changes": changes,
	        "margin_percent": doc.margin_percent}


@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES)
def add_supplementary(function: str, item_name: str, qty: float, rate: float,
                      item_type: str = "Food & Beverage",
                      uom: str = "Unit", cost_rate: float = 0,
                      is_alcohol: int = 0, notes: str | None = None):
	"""Something ordered on the night that wasn't on the quote - another
	round at the bar, twenty extra plates, a second cake. It bills on top
	and is marked so the final bill can show it apart from what was
	agreed."""
	doc = _fn(function)
	_guard_closed(doc)
	if float(qty) <= 0 or float(rate) < 0:
		frappe.throw(_("A supplementary needs a positive quantity."))
	doc.append("items", {
		"item_type": item_type, "item_name": (item_name or "").strip()[:140],
		"qty": float(qty), "uom": uom, "rate": float(rate),
		"list_rate": float(rate), "cost_rate": float(cost_rate or 0),
		"chargeable": 1, "is_supplementary": 1,
		"is_alcohol": 1 if int(is_alcohol or 0) else 0, "notes": notes,
	})
	doc.save()
	return {"ok": True, "grand_total": doc.grand_total,
	        "supplementary_total": sum(
		        float(r.total or 0) for r in doc.items if r.is_supplementary)}


@frappe.whitelist()
@require_roles(*READ_ROLES)
def function_economics(function: str):
	"""The P&L of one function: what it sold, what it cost, what the input
	credit is worth, and what's left - plus where the quote and the night
	disagreed."""
	doc = _fn(function)
	lines = []
	for r in doc.items:
		quoted = float(r.qty or 0)
		served = float(r.actual_qty or 0)
		lines.append({
			"row": r.name, "item_name": r.item_name, "item_type": r.item_type,
			"uom": r.uom, "quoted_qty": quoted,
			"actual_qty": served or None,
			"variance": round(served - quoted, 2) if served else 0,
			"rate": r.rate, "amount": r.amount, "net_amount": r.net_amount,
			"cost_rate": r.cost_rate, "cost_amount": r.cost_amount,
			"input_tax": r.input_tax,
			"margin": round(float(r.net_amount or 0) - float(r.cost_amount or 0), 2),
			"chargeable": bool(r.chargeable),
			"is_supplementary": bool(r.is_supplementary),
		})
	supplementary = [x for x in lines if x["is_supplementary"]]
	return {
		"function": doc.name, "customer_name": doc.customer_name,
		"pax": doc.billable_pax,
		"revenue": {
			"subtotal": doc.subtotal, "discount": doc.discount_amount,
			"service_charge": doc.service_charge,
			"taxable": doc.taxable_amount, "tax": doc.tax_amount,
			"grand_total": doc.grand_total,
			"complimentary": doc.non_chargeable_value,
			"supplementary": round(sum(x["net_amount"] or 0
			                           for x in supplementary), 2),
		},
		"cost": {
			"food": doc.food_cost, "service": doc.service_cost,
			"total": doc.total_cost, "input_tax": doc.input_tax_credit,
			"itc_eligible": bool(doc.itc_eligible), "net": doc.net_cost,
		},
		"margin": {
			"gross": doc.gross_margin, "percent": doc.margin_percent,
			"per_pax": round(float(doc.gross_margin or 0) / doc.billable_pax, 2)
			if doc.billable_pax else 0,
		},
		"lines": lines,
		"uncosted_lines": [x["item_name"] for x in lines
		                   if x["chargeable"] and not x["cost_rate"]],
	}


# ══ the customer ═════════════════════════════════════════════════════════

@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES)
def link_customer(function: str, guest: str | None = None):
	"""Tie the function to a real guest record instead of a name in a box.

	Without this a banquet customer is a string: no history, no notes, no
	'they complained about the AC last time'. With it, the banquet office
	sees the same person the front desk does."""
	doc = _fn(function)
	if guest:
		if not frappe.db.exists("Guest", guest):
			frappe.throw(_("No such guest."))
		doc.customer = guest
		doc.customer_name = frappe.db.get_value("Guest", guest, "full_name") \
			or doc.customer_name
	else:
		doc.customer = _find_or_create_guest(doc)
	doc.save()
	return {"ok": True, "customer": doc.customer,
	        "customer_name": doc.customer_name}


def _find_or_create_guest(doc):
	"""Dedupe on the phone number, the way the front desk does."""
	phone = (doc.customer_phone or "").strip()
	if phone:
		existing = frappe.db.get_value("Guest", {"phone": phone})
		if existing:
			return existing
	parts = (doc.customer_name or "Guest").strip().split(" ", 1)
	g = frappe.get_doc({
		"doctype": "Guest", "first_name": parts[0][:60],
		"last_name": (parts[1][:60] if len(parts) > 1 else None),
		"phone": phone or None, "email": doc.customer_email or None,
	})
	g.insert(ignore_permissions=True)
	return g.name


@frappe.whitelist()
@require_roles(*REPORT_ROLES)
def customer_profile(property: str, guest: str | None = None,
                     phone: str | None = None):
	"""Everything the banquet office should know before picking up the
	phone: what this client has run with us, what they spent, what they
	usually book, and what's still owed."""
	if not guest and phone:
		guest = frappe.db.get_value("Guest", {"phone": phone.strip()})
	if not guest:
		return {"found": False}
	g = frappe.db.get_value(
		"Guest", guest,
		["name", "full_name", "phone", "email", "vip", "guest_notes",
		 "guest_category", "city", "blacklisted", "blacklist_reason"],
		as_dict=True)
	if not g:
		return {"found": False}

	functions = frappe.get_all(
		"Venue Booking",
		filters={"property": property, "customer": guest},
		fields=["name", "event_date", "event_type", "event_name", "venue",
		        "session", "status", "grand_total", "balance_due",
		        "pax_actual", "pax_guaranteed", "attendees", "company"],
		order_by="event_date desc", limit=50)
	won = [f for f in functions if f.status in ("Confirmed", "Completed")]
	spend = sum(float(f.grand_total or 0) for f in won)
	pax = [int(f.pax_actual or f.pax_guaranteed or f.attendees or 0) for f in won]

	def commonest(key):
		counts: dict = {}
		for f in won:
			counts[f.get(key)] = counts.get(f.get(key), 0) + 1
		return max(counts, key=counts.get) if counts else None

	stays = frappe.db.count("Reservation", {"guest": guest})
	return {
		"found": True, "guest": g,
		"functions": [dict(f, event_date=str(f.event_date)) for f in functions],
		"stats": {
			"functions": len(functions), "won": len(won),
			"lifetime_value": round(spend, 2),
			"average_value": round(spend / len(won), 2) if won else 0,
			"average_pax": round(sum(pax) / len(pax)) if pax else 0,
			"outstanding": round(sum(float(f.balance_due or 0) for f in won), 2),
			"usual_venue": commonest("venue"),
			"usual_event": commonest("event_type"),
			"room_stays": stays,
			"last_event": str(won[0].event_date) if won else None,
		},
	}


# ══ before you send the price ════════════════════════════════════════════

# What a banquet is expected to hold. Below the floor a function is worth
# arguing about; below break-even it is worth refusing.
TARGET_MARGIN = 40.0
FLOOR_MARGIN = 25.0


@frappe.whitelist()
@require_roles(*BANQUET_ROLES, "Finance")
def quote_advisor(function: str, at_discount: float | None = None):
	"""Would this function make money at the price we're about to send?

	Margin after the event is an autopsy. The number that changes a
	decision is the one on screen while the discount is still being typed
	- so this answers, for the price as it stands: what's left, how much
	more could be given away before it stops being worth doing, and where
	the cost actually sits.

	`at_discount` prices a what-if without touching the quote.
	"""
	doc = _fn(function)
	discount = (Decimal(str(at_discount)) if at_discount is not None
	            else Decimal(str(doc.discount_amount or 0)))

	subtotal = Decimal(str(doc.subtotal or 0))
	if discount > subtotal:
		frappe.throw(_("That discount is more than the quote itself."))
	cost = Decimal(str(doc.net_cost or 0))
	revenue = subtotal - discount
	margin = revenue - cost
	pct = float(round(margin / revenue * 100, 2)) if revenue else 0.0

	# the most that can be given away and still clear each bar
	def headroom(target: float) -> float:
		if not cost:
			return float(subtotal)          # nothing costed: no honest answer
		keep = cost / (1 - Decimal(str(target)) / 100) if target < 100 else cost
		return float(max(Decimal(0), subtotal - keep))

	uncosted = [r.item_name for r in doc.items
	            if r.chargeable and not float(r.cost_rate or 0)]
	drivers = sorted(
		({"item_name": r.item_name, "cost": float(r.cost_amount or 0),
		  "share": round(float(r.cost_amount or 0) / float(cost) * 100, 1)
		  if cost else 0}
		 for r in doc.items if float(r.cost_amount or 0)),
		key=lambda x: -x["cost"])[:5]

	verdict, advice = _verdict(pct, bool(uncosted), cost)
	return {
		"function": doc.name, "pax": doc.billable_pax,
		"subtotal": float(subtotal), "discount": float(discount),
		"revenue": float(revenue), "cost": float(cost),
		"margin": float(margin), "margin_percent": pct,
		"per_pax": {
			"revenue": round(float(revenue) / doc.billable_pax, 2)
			if doc.billable_pax else 0,
			"cost": round(float(cost) / doc.billable_pax, 2)
			if doc.billable_pax else 0,
			"margin": round(float(margin) / doc.billable_pax, 2)
			if doc.billable_pax else 0,
		},
		"break_even_price": float(cost),
		"max_discount": {
			"to_break_even": headroom(0),
			"to_floor": headroom(FLOOR_MARGIN),
			"to_target": headroom(TARGET_MARGIN),
		},
		"target_margin": TARGET_MARGIN, "floor_margin": FLOOR_MARGIN,
		"verdict": verdict, "advice": advice,
		"cost_drivers": drivers,
		"uncosted_lines": uncosted,
		"hall": {
			"deal": doc.hall_deal, "waived": bool(doc.hall_waived),
			"fnb_spend": doc.fnb_spend,
			"minimum": doc.minimum_fnb_spend,
			"short_by": max(0.0, float(doc.minimum_fnb_spend or 0)
			                - float(doc.fnb_spend or 0))
			if doc.hall_deal == "Hall free over a minimum spend" else 0,
		},
	}


def _verdict(pct: float, uncosted: bool, cost) -> tuple:
	if not cost:
		return "unknown", _(
			"Nothing on this quote carries a cost yet, so any margin shown "
			"is imaginary. Choose the menu's dishes and put cost rates on "
			"the services before trusting the number.")
	if pct < 0:
		return "loss", _(
			"This loses money at the current price.") + (
			_(" And some lines still cost nothing, so it loses more.")
			if uncosted else "")
	if uncosted:
		return "partial", _(
			"Some lines still cost nothing, so the real margin is lower "
			"than this. Treat it as a ceiling, not an answer.")
	if pct < FLOOR_MARGIN:
		return "thin", _(
			"Below the {0}% floor. Worth taking only for the rooms it "
			"brings, or a date that would otherwise sit empty.").format(
				FLOOR_MARGIN)
	if pct < TARGET_MARGIN:
		return "ok", _("Workable, though under the {0}% a banquet "
		              "normally holds.").format(TARGET_MARGIN)
	return "good", _("Comfortably profitable at this price.")


@frappe.whitelist(methods=["POST"])
@require_roles(*BANQUET_ROLES)
def offer_amenities(function: str, amenities=None, as_open_items: int = 0):
	"""Put the hall's chargeable extras on the function.

	A hall's air-conditioning and generator come with it; its extra mics,
	its valet parking and its second generator do not. Those live on the
	venue, and this is how they reach a quote - either priced onto it, or
	parked as open items when the customer hasn't decided yet, which is
	where most of them actually sit while a wedding is being agreed.
	"""
	doc = _fn(function)
	_guard_closed(doc)
	wanted = set(_rows(amenities) or [])
	rows = frappe.get_all(
		"Venue Amenity",
		filters={"parent": doc.venue, "parenttype": "Venue", "included": 0},
		fields=["name", "amenity", "category", "rate", "uom", "note"])
	picked = [r for r in rows if not wanted or r.amenity in wanted]
	if not picked:
		return {"ok": True, "added": 0,
		        "note": _("This hall has no chargeable extras on it.")}

	for a in picked:
		if int(as_open_items or 0):
			doc.append("open_items", {
				"title": a.amenity,
				"detail": _("{0} on {1} - not yet agreed.").format(
					a.category, doc.venue),
				"owner_side": "Client", "status": "Open",
				"price_impact": float(a.rate or 0),
			})
		else:
			doc.append("items", {
				"item_type": _AMENITY_TYPE.get(a.category, "Other"),
				"item_name": a.amenity, "description": a.note,
				"qty": 0, "uom": _UOM_FROM_CATALOGUE.get(a.uom, "Lot"),
				"list_rate": float(a.rate or 0), "rate": float(a.rate or 0),
				"chargeable": 1, "notes": "hall-amenity",
			})
	doc.save()
	return {"ok": True, "added": len(picked),
	        "as_open_items": bool(int(as_open_items or 0)),
	        "grand_total": doc.grand_total}


_AMENITY_TYPE = {
	"Audio Visual": "Audio Visual", "Climate": "Furniture & Setup",
	"Power": "Furniture & Setup", "Parking": "Staffing",
	"Service": "Staffing", "Access": "Other", "Kitchen": "Food & Beverage",
	"Safety": "Other", "Other": "Other",
}


@frappe.whitelist()
@require_roles(*READ_ROLES)
def venue_detail(venue: str):
	"""One hall in full: what it holds, what it comes with, what it costs
	to open, and which other spaces it shares its floor with."""
	from kamra.kamra.doctype.venue_booking.venue_booking import clashing_venues

	v = frappe.get_doc("Venue", venue)
	shares = [x for x in clashing_venues(v.property, venue) if x != venue]
	return {
		"venue": v.as_dict(),
		"amenities": [
			{"amenity": a.amenity, "category": a.category,
			 "included": bool(a.included), "rate": a.rate, "uom": a.uom,
			 "note": a.note}
			for a in v.get("amenities_list") or []],
		"sections": [{"section": s.section, "area_sqft": s.area_sqft,
		              "seats": s.seats} for s in v.get("sections") or []],
		"shares_floor_with": shares,
		"floor_plan": v.floor_plan,
	}
