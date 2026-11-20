"""Unit owners (#639).

A property manager links each owner to the units they own and to one or
more logins. Those logins get the Owner role and Frappe User Permissions
on just those rooms (and the property, so the property switcher works).
The portal they see is this module: occupancy, bookings and room revenue.
Guest name and phone stay off unless the admin turns Show guest contact
on. Identity documents are never returned.

Read only and Manage are stored per owner. Manage does not open the desk
and does not reveal a guest's documents; it is the hook for a later
"may block their own unit" grant. Both levels use the same portal today.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, getdate, nowdate

from kamra.authz import require_roles
from kamra.staff import ROLE_NAMES

OWNER_ROLE = "Owner"
# a login that also holds a desk role keeps the property permissions an
# admin already gave them; a dedicated owner login is scoped exactly
STAFF_ROLES = set(ROLE_NAMES) - {OWNER_ROLE}


def ensure_owner_role() -> None:
	if not frappe.db.exists("Role", OWNER_ROLE):
		frappe.get_doc({
			"doctype": "Role", "role_name": OWNER_ROLE, "desk_access": 0,
		}).insert(ignore_permissions=True)


def sync_user_access(user: str) -> None:
	"""Make this login's Owner role and room permissions match the Unit
	Owner records that list them. Called when an owner record is saved
	or deleted."""
	if not user or not frappe.db.exists("User", user):
		return
	ensure_owner_role()
	links = frappe.get_all("Unit Owner User", filters={"user": user}, pluck="parent")
	rooms: set[str] = set()
	properties: set[str] = set()
	for name in links:
		doc = frappe.get_doc("Unit Owner", name)
		properties.add(doc.property)
		for row in doc.units:
			if row.room:
				rooms.add(row.room)
	user_doc = frappe.get_doc("User", user)
	held = {r.role for r in user_doc.roles}
	user_doc.flags.ignore_permissions = True
	if links and OWNER_ROLE not in held:
		user_doc.add_roles(OWNER_ROLE)
		held.add(OWNER_ROLE)
	if not links and OWNER_ROLE in held:
		user_doc.remove_roles(OWNER_ROLE)
		held.discard(OWNER_ROLE)
	want = {("Room", room) for room in rooms} | {("Property", prop) for prop in properties}
	existing = frappe.get_all(
		"User Permission",
		filters={"user": user, "allow": ["in", ["Room", "Property"]]},
		fields=["name", "allow", "for_value"])
	have = {(row.allow, row.for_value): row.name for row in existing}
	# a dedicated owner login must not keep a room they were taken off
	if not (held & STAFF_ROLES):
		for key, name in have.items():
			if key not in want:
				frappe.delete_doc("User Permission", name, ignore_permissions=True)
	for allow, value in want:
		if (allow, value) not in have:
			frappe.get_doc({
				"doctype": "User Permission",
				"user": user,
				"allow": allow,
				"for_value": value,
			}).insert(ignore_permissions=True)
	frappe.clear_cache(user=user)


def _owner_docs(user: str, property: str) -> list:
	names = frappe.get_all("Unit Owner User", filters={"user": user}, pluck="parent")
	docs = []
	for name in names:
		doc = frappe.get_doc("Unit Owner", name)
		if doc.property == property:
			docs.append(doc)
	return docs


def _portal(docs: list, property: str, from_date: str, to_date: str) -> dict:
	rooms = []
	seen = set()
	show = False
	access = "Read only"
	names = []
	for doc in docs:
		names.append(doc.owner_name)
		show = show or bool(doc.show_guest_contact)
		if doc.access == "Manage":
			access = "Manage"
		for row in doc.units:
			if row.room and row.room not in seen:
				seen.add(row.room)
				rooms.append(row.room)
	meta = {
		r.name: r for r in frappe.get_all(
			"Room", filters={"name": ["in", rooms or ["-1"]]},
			fields=["name", "room_number", "occupancy_status"])
	}
	start, end = getdate(from_date), getdate(to_date)
	if end < start:
		start, end = end, start
	stays = frappe.get_all(
		"Reservation",
		filters={
			"property": property,
			"room": ["in", rooms or ["-1"]],
			"status": ["in", ["Confirmed", "Checked In", "Checked Out"]],
			"check_in_date": ["<=", str(end)],
			"check_out_date": [">", str(start)],
		},
		fields=["name", "room", "status", "check_in_date", "check_out_date",
		        "guest", "guest_name"],
		order_by="check_in_date asc",
		limit=200,
	)
	guests = {}
	if show:
		ids = list({s.guest for s in stays if s.guest})
		if ids:
			for g in frappe.get_all(
				"Guest", filters={"name": ["in", ids]},
				fields=["name", "first_name", "last_name", "phone"]):
				guests[g.name] = g
	span = date_diff(end, start) + 1
	sold = 0
	bookings = []
	for stay in stays:
		arrive = max(getdate(stay.check_in_date), start)
		leave = min(getdate(stay.check_out_date), add_days(end, 1))
		sold += max(0, date_diff(leave, arrive))
		guest = guests.get(stay.guest) if show else None
		full = ""
		phone = None
		if guest:
			full = " ".join(p for p in (guest.first_name, guest.last_name) if p)
			phone = guest.phone or None
		elif show and stay.guest_name:
			full = stay.guest_name
		bookings.append({
			"reservation": stay.name,
			"room": stay.room,
			"room_number": (meta.get(stay.room) or {}).get("room_number") or "",
			"status": stay.status,
			"check_in": str(stay.check_in_date),
			"check_out": str(stay.check_out_date),
			"guest": full or "Guest",
			"phone": phone if show else None,
		})
	revenue = 0.0
	if stays:
		for row in frappe.get_all(
			"Folio Charge",
			filters={
				"reservation": ["in", [s.name for s in stays]],
				"posting_date": ["between", [str(start), str(end)]],
				"charge_type": ["in", ["Room", "Extra Guests", "Cleaning Fee"]],
			},
			fields=["amount"]):
			revenue += float(row.amount or 0)
	units = [{
		"room": name,
		"room_number": (meta.get(name) or {}).get("room_number") or name,
		"occupancy_status": (meta.get(name) or {}).get("occupancy_status") or "",
	} for name in rooms]
	occupancy = round(100 * sold / (len(rooms) * span), 1) if rooms and span else 0
	return {
		"owner_name": ", ".join(names),
		"access": access,
		"show_guest_contact": bool(show),
		"from_date": str(start),
		"to_date": str(end),
		"units": units,
		"occupancy_pct": occupancy,
		"room_nights": sold,
		"revenue": round(revenue, 2),
		"bookings": bookings,
	}


@frappe.whitelist()
@require_roles("Hotel Admin")
def desk(property: str) -> dict:
	"""Owners and units for the admin screen."""
	owners = frappe.get_all(
		"Unit Owner", filters={"property": property},
		fields=["name", "owner_name", "access", "show_guest_contact"],
		order_by="owner_name asc")
	for row in owners:
		row["units"] = frappe.get_all(
			"Unit Owner Unit", filters={"parent": row.name}, pluck="room")
		row["users"] = frappe.get_all(
			"Unit Owner User", filters={"parent": row.name}, pluck="user")
	rooms = frappe.get_all(
		"Room", filters={"property": property},
		fields=["name", "room_number"], order_by="room_number asc")
	return {"owners": owners, "rooms": rooms}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin")
def save_owner(property: str, owner_name: str, rooms, users,
               access: str = "Read only", show_guest_contact: int = 0,
               name: str | None = None) -> dict:
	"""Create or update one owner and rescope their logins."""
	if isinstance(rooms, str):
		rooms = frappe.parse_json(rooms)
	if isinstance(users, str):
		users = frappe.parse_json(users)
	rooms = [r for r in (rooms or []) if r]
	users = [u for u in (users or []) if u]
	payload = {
		"owner_name": (owner_name or "").strip(),
		"property": property,
		"access": access if access in ("Read only", "Manage") else "Read only",
		"show_guest_contact": 1 if cint(show_guest_contact) else 0,
		"units": [{"room": r} for r in rooms],
		"users": [{"user": u} for u in users],
	}
	if name and frappe.db.exists("Unit Owner", name):
		doc = frappe.get_doc("Unit Owner", name)
		if doc.property != property:
			frappe.throw(_("That owner belongs to another property."), frappe.PermissionError)
		doc.update(payload)
		doc.save()
	else:
		doc = frappe.get_doc({"doctype": "Unit Owner", **payload})
		doc.insert()
	return {"name": doc.name}


@frappe.whitelist()
@require_roles(OWNER_ROLE)
def my_portal(property: str, from_date: str | None = None,
              to_date: str | None = None) -> dict:
	"""The signed-in owner's own units. Another owner's units are absent,
	not redacted."""
	docs = _owner_docs(frappe.session.user, property)
	if not docs:
		frappe.throw(_("You don't have units at this property."), frappe.PermissionError)
	start = from_date or nowdate()
	end = to_date or start
	return _portal(docs, property, start, end)
