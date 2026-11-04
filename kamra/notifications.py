"""The notification bell: one short line per thing a department should know.

Every notification belongs to a module (front desk, housekeeping, F&B...).
A person sees the modules their roles open - the same gates as the app
launcher (frontend/src/lib/apps.ts) - and only for modules the property
runs. Their own actions are left out: whoever made the booking doesn't need
telling. "Read" is one timestamp per person per property; anything newer
is unread. Rows older than KEEP_DAYS are deleted every night.

Writing a notification is best effort - it never breaks the booking, order
or ticket that caused it."""

from __future__ import annotations

import frappe
from frappe.utils import add_days, cint, get_datetime, now_datetime

from kamra.authz import ADMIN, assert_property_access, require_roles

KEEP_DAYS = 30

# who works in each module; admins see every module (mirrors apps.ts)
MODULE_ROLES = {
	"front-desk": {"Front Desk", "Night Auditor"},
	"housekeeping": {"Housekeeping", "Housekeeping Supervisor", "Front Desk"},
	"operations": {"Front Desk"},
	"fnb": {"Front Desk", "Finance", "F&B Manager"},
	"events": {"Front Desk", "Revenue Manager"},
	"finance": {"Finance", "Front Desk", "Night Auditor"},
	"revenue": {"Revenue Manager"},
}

STAFF = ("Front Desk", "Night Auditor", "Housekeeping", "Housekeeping Supervisor",
         "Finance", "F&B Manager", "Revenue Manager")


def record(property: str | None, module: str, subject: str, *,
           doctype: str | None = None, name: str | None = None,
           route: str | None = None) -> None:
	"""Add one line to the bell of everyone working in `module`."""
	if not property or module not in MODULE_ROLES:
		return
	try:
		# the reference is plain text, not a link: a notification must never
		# stop its booking or task from being deleted
		frappe.get_doc({
			"doctype": "Kamra Notification", "property": property,
			"module": module, "subject": subject[:240],
			"reference_doctype": doctype, "reference_name": name,
			"route": route,
		}).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(title=f"Notification not recorded: {subject[:80]}")


def room_no(room: str | None) -> str:
	"""The number staff know (204), not the record id (Naadi Stays-204)."""
	if not room:
		return ""
	return frappe.db.get_value("Room", room, "room_number") or room


def _room(doc) -> str:
	return f" - Room {room_no(doc.room)}" if doc.get("room") else ""


# --- what makes a notification ---------------------------------------------

# reservations that are only a question, not a booking yet
_NOT_BOOKED = {"Waitlist", "Inquiry", "Quoted"}


def on_reservation_insert(doc, method=None):
	if doc.status in _NOT_BOOKED:
		return
	record(doc.property, "front-desk",
	       f"New booking - {doc.guest_name}, {doc.check_in_date} to {doc.check_out_date}",
	       doctype=doc.doctype, name=doc.name, route=f"/reservations?open={doc.name}")


def on_reservation_update(doc, method=None):
	before = doc.get_doc_before_save()
	if not before or before.status == doc.status:
		return
	route = f"/reservations?open={doc.name}"
	if doc.status == "Cancelled":
		record(doc.property, "front-desk", f"Booking cancelled - {doc.guest_name}",
		       doctype=doc.doctype, name=doc.name, route=route)
	elif doc.status == "Checked In":
		record(doc.property, "front-desk", f"Checked in - {doc.guest_name}{_room(doc)}",
		       doctype=doc.doctype, name=doc.name, route=route)
	elif doc.status == "Checked Out":
		record(doc.property, "front-desk", f"Checked out - {doc.guest_name}{_room(doc)}",
		       doctype=doc.doctype, name=doc.name, route=route)
		if doc.get("room"):
			record(doc.property, "housekeeping",
			       f"Room {room_no(doc.room)} is empty - needs cleaning",
			       doctype="Room", name=doc.room, route="/room-board")


def on_housekeeping_task_insert(doc, method=None):
	record(doc.property, "housekeeping", f"New task: {doc.task_type}{_room(doc)}",
	       doctype=doc.doctype, name=doc.name, route="/housekeeping")


def on_laundry_order_insert(doc, method=None):
	who = doc.get("guest_name") or doc.get("house_label") or ""
	record(doc.property, "housekeeping",
	       f"Laundry to collect{_room(doc)}" + (f" ({who})" if who else ""),
	       doctype=doc.doctype, name=doc.name, route="/laundry")


def on_pos_order_insert(doc, method=None):
	# the till's own orders already chime on the kitchen screen; tell the
	# team about the ones that arrive from elsewhere (guest QR, agent, phone)
	# and every room service / delivery order
	if doc.get("source") in (None, "", "Manual") and \
			doc.get("order_type") not in ("Room Service", "Delivery"):
		return
	where = (f"Room {room_no(doc.room)}" if doc.get("room")
	         else f"Table {doc.table_no}" if doc.get("table_no")
	         else doc.get("order_type") or "")
	record(doc.property, "fnb", f"New {(doc.order_type or 'food').lower()} order"
	       + (f" - {where}" if where else ""),
	       doctype=doc.doctype, name=doc.name, route="/kitchen")


def on_venue_booking_insert(doc, method=None):
	what = doc.get("event_name") or doc.get("event_type") or "Event"
	record(doc.property, "events", f"New banquet {doc.status.lower()} - {what}, {doc.event_date}",
	       doctype=doc.doctype, name=doc.name, route=f"/banquet/{doc.name}")


def on_venue_booking_update(doc, method=None):
	before = doc.get_doc_before_save()
	if not before or before.status == doc.status or doc.status not in ("Confirmed", "Cancelled"):
		return
	what = doc.get("event_name") or doc.get("event_type") or "Event"
	record(doc.property, "events", f"Banquet {doc.status.lower()} - {what}, {doc.event_date}",
	       doctype=doc.doctype, name=doc.name, route=f"/banquet/{doc.name}")


def on_service_ticket_insert(doc, method=None):
	record(doc.property, "operations", f"New request: {doc.subject}{_room(doc)}",
	       doctype=doc.doctype, name=doc.name, route="/tickets")


def on_service_ticket_update(doc, method=None):
	before = doc.get_doc_before_save()
	if not before or before.status == doc.status or doc.status != "Resolved":
		return
	record(doc.property, "operations", f"Request resolved: {doc.subject}{_room(doc)}",
	       doctype=doc.doctype, name=doc.name, route="/tickets")


def on_housekeeping_task_update(doc, method=None):
	before = doc.get_doc_before_save()
	if not before or before.status == doc.status or doc.status not in ("Done", "Verified"):
		return
	done = "checked" if doc.status == "Verified" else "done"
	record(doc.property, "housekeeping", f"{doc.task_type} {done}{_room(doc)}",
	       doctype=doc.doctype, name=doc.name, route="/housekeeping")


def _money(amount) -> str:
	from frappe.utils import fmt_money
	return fmt_money(abs(amount or 0), precision=0)


def on_folio_update(doc, method=None):
	"""New payment, refund or hand-posted charge on a bill. The night audit's
	nightly room charges are left out (auto_posted), or the bell would list
	every room every night."""
	before = doc.get_doc_before_save()
	if not before:
		return
	route = f"/billing/{doc.name}"
	who = doc.get("guest_name") or doc.get("bill_to_name") or doc.name
	old_pay = {r.name for r in before.get("payments") or []}
	for p in doc.get("payments") or []:
		if p.name in old_pay:
			continue
		kind = p.get("payment_kind") or "Payment"
		mode = f" {p.mode}" if p.get("mode") else ""
		text = (f"Refund - {_money(p.amount)}{mode} - {who}" if kind == "Refund"
		        else f"{kind} received - {_money(p.amount)}{mode} - {who}")
		record(doc.property, "finance", text, doctype=doc.doctype, name=doc.name, route=route)
	old_charge = {r.name for r in before.get("charges") or []}
	for c in doc.get("charges") or []:
		if c.name in old_charge or c.get("auto_posted") or c.get("charge_type") == "Opening Balance":
			continue
		what = c.get("description") or c.get("charge_type") or "Charge"
		record(doc.property, "finance",
		       f"Charge posted - {what} {_money(c.get('total') or c.get('amount'))} - {who}",
		       doctype=doc.doctype, name=doc.name, route=route)


def _all_prepared(order) -> bool:
	live = [i for i in order.get("items") or [] if not i.get("voided")]
	return bool(live) and all(i.get("kot_status") == "Prepared" for i in live)


def on_pos_order_update(doc, method=None):
	"""The kitchen has finished every dish on the order: tell the floor."""
	before = doc.get_doc_before_save()
	if not before or _all_prepared(before) or not _all_prepared(doc):
		return
	where = (f"Room {room_no(doc.room)}" if doc.get("room")
	         else f"Table {doc.table_no}" if doc.get("table_no")
	         else doc.get("customer_name") or doc.get("order_type") or "")
	kot = f" (KOT {doc.kot_no})" if doc.get("kot_no") else ""
	record(doc.property, "fnb", f"Order ready{kot}" + (f" - {where}" if where else ""),
	       doctype=doc.doctype, name=doc.name, route="/pos")


def on_ingredient_ledger_insert(doc, method=None):
	"""Stock just fell to or below its minimum (par level). Only the move that
	crosses the line tells; the sales after it stay quiet."""
	if (doc.get("qty_change") or 0) >= 0 or not doc.get("outlet"):
		return
	par = frappe.db.get_value("Ingredient Stock", f"{doc.outlet}::{doc.ingredient}", "par_level")
	if not par:
		return
	after = doc.balance_after or 0
	if after > par or after - doc.qty_change <= par:
		return
	name, uom = frappe.db.get_value("Ingredient", doc.ingredient,
	                                ["ingredient_name", "uom"]) or (doc.ingredient, "")
	left = f"{after:g} {uom or ''}".strip()
	record(doc.property, "fnb",
	       f"Low stock - {name or doc.ingredient}: {left} left (minimum {par:g})",
	       doctype="Ingredient", name=doc.ingredient, route="/inventory")


# rates: a revenue manager should hear when a price moves
_ROOM_TYPE_PRICES = ("base_price", "single_occupancy_price", "extra_adult_price",
                     "extra_bed_price", "child_price")


def on_room_type_update(doc, method=None):
	before = doc.get_doc_before_save()
	if not before:
		return
	label = doc.get("room_type_name") or doc.name
	for f in _ROOM_TYPE_PRICES:
		old, new = before.get(f) or 0, doc.get(f) or 0
		if old != new:
			field = doc.meta.get_label(f) or f
			record(doc.property, "revenue",
			       f"Price changed - {label} {field}: {_money(old)} to {_money(new)}",
			       doctype=doc.doctype, name=doc.name, route="/room-types")


def on_season_change(doc, method=None):
	"""A date-range rate added or edited (also the agent's set_room_rate)."""
	if method == "on_update" and doc.get_doc_before_save() is None:
		return  # the insert already told
	if method == "on_update":
		before = doc.get_doc_before_save()
		keys = ("adjustment_type", "adjustment_value", "start_date", "end_date",
		        "room_type", "disabled")
		if all(before.get(k) == doc.get(k) for k in keys):
			return
	verb = "added" if method == "after_insert" else "changed"
	rt = (" " + (frappe.db.get_value("Room Type", doc.room_type, "room_type_name") or doc.room_type)
	      if doc.get("room_type") else "")
	record(doc.property, "revenue",
	       f"Rate {verb}{rt} - {doc.start_date} to {doc.end_date}",
	       doctype=doc.doctype, name=doc.name, route="/rate-calendar")


def on_rate_plan_update(doc, method=None):
	before = doc.get_doc_before_save()
	if not before or (before.get("modifier_type") == doc.get("modifier_type")
	                  and before.get("modifier_value") == doc.get("modifier_value")):
		return
	record(doc.property, "revenue",
	       f"Rate plan changed - {doc.get('rate_plan_name') or doc.name}",
	       doctype=doc.doctype, name=doc.name, route="/rate-plans")


# called from code that writes with set_value, where no hook runs

def room_out_of_order(property: str, room: str) -> None:
	record(property, "housekeeping", f"Room {room_no(room)} marked out of order",
	       doctype="Room", name=room, route="/room-board")


def no_show(res) -> None:
	record(res.property, "front-desk", f"No-show - {res.guest_name}",
	       doctype="Reservation", name=res.name, route=f"/reservations?open={res.name}")


# --- the bell ----------------------------------------------------------------

def _seen_key(property: str) -> str:
	return f"kamra_bell_seen:{property}"


def visible_modules(property: str, user: str | None = None) -> list[str]:
	"""The modules whose notifications this person sees on this property."""
	from kamra.api import ALL_MODULES

	roles = set(frappe.get_roles(user))
	raw = frappe.db.get_value("Property", property, "enabled_modules")
	running = [m.strip() for m in (raw or "").split(",") if m.strip()] or list(ALL_MODULES)
	admin = bool(roles & set(ADMIN))
	return [m for m in MODULE_ROLES
	        if m in running and (admin or roles & MODULE_ROLES[m])]


@frappe.whitelist()
@require_roles(*STAFF)
def bell(property: str, limit: int = 40) -> dict:
	"""What this person hasn't opened yet, newest first, and how many. An
	opened notification leaves the list (open_one); "Mark all read" clears
	everything up to now (mark_read)."""
	assert_property_access(property)
	user = frappe.session.user
	modules = visible_modules(property, user)
	if not modules:
		return {"modules": [], "unread": 0, "items": []}
	filters = [["property", "=", property], ["module", "in", modules]]
	if user != "Administrator":
		filters.append(["owner", "!=", user])  # not your own actions
	seen = frappe.defaults.get_user_default(_seen_key(property))
	if seen:
		filters.append(["creation", ">", get_datetime(seen)])
	opened = frappe.get_all("Kamra Notification Read",
	                        filters={"user": user, "property": property},
	                        pluck="notification")
	if opened:
		filters.append(["name", "not in", opened])
	rows = frappe.get_all(
		"Kamra Notification", filters=filters,
		fields=["name", "module", "subject", "route", "creation"],
		order_by="creation desc", limit_page_length=min(cint(limit) or 40, 100))
	unread = frappe.db.count("Kamra Notification", filters)
	now = now_datetime()
	for r in rows:
		# seconds ago, so the browser's clock and time zone don't matter
		r["age"] = max(int((now - get_datetime(r.pop("creation"))).total_seconds()), 0)
	return {"modules": modules, "unread": unread, "items": rows}


@frappe.whitelist(methods=["POST"])
@require_roles(*STAFF)
def open_one(property: str, notification: str) -> dict:
	"""This person opened one notification: it leaves their list only."""
	assert_property_access(property)
	user = frappe.session.user
	if frappe.db.exists("Kamra Notification", {"name": notification, "property": property}) \
			and not frappe.db.exists("Kamra Notification Read",
			                         {"notification": notification, "user": user}):
		frappe.get_doc({"doctype": "Kamra Notification Read", "notification": notification,
		                "user": user, "property": property}).insert(ignore_permissions=True)
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
@require_roles(*STAFF)
def mark_read(property: str) -> dict:
	"""Everything up to now counts as read for this person."""
	assert_property_access(property)
	frappe.defaults.set_user_default(_seen_key(property), str(now_datetime()))
	# the per-notification marks before now are no longer needed
	frappe.db.delete("Kamra Notification Read",
	                 {"user": frappe.session.user, "property": property})
	return {"ok": True}


def purge_old() -> None:
	"""Nightly: drop notifications older than KEEP_DAYS, and who opened them."""
	cutoff = add_days(now_datetime(), -KEEP_DAYS)
	frappe.db.delete("Kamra Notification", {"creation": ("<", cutoff)})
	frappe.db.delete("Kamra Notification Read", {"creation": ("<", cutoff)})
