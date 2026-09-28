"""Endpoint authorization - Frappe checks doctype permissions on ORM
paths, but raw-SQL reads and db.set_value writes sail past them. Every
whitelisted Kamra endpoint therefore declares who may call it - and,
for staff restricted to some properties, which properties it may touch."""

import inspect
import json
from functools import wraps

import frappe
from frappe.utils import now_datetime, add_to_date

ADMIN = ("System Manager", "Administrator", "Hotel Admin")

# IT / site admins only - deliberately EXCLUDES the Hotel Admin business role.
# For user management, developer settings and API keys.
IT_ADMIN = ("System Manager", "Administrator")

PIN_MAX_ATTEMPTS = 5
PIN_LOCK_MINUTES = 15


def require_it_admin(fn):
	"""Stricter than require_roles: System / site administrators only, not the
	Hotel Admin (GM) business role. Place below @frappe.whitelist()."""

	@wraps(fn)
	def guarded(*args, **kwargs):
		if not set(IT_ADMIN) & set(frappe.get_roles()):
			frappe.throw(
				"Needs a System / site administrator (IT).", frappe.PermissionError)
		return fn(*args, **kwargs)

	return guarded


# Endpoint argument name -> the doctype(s) it names. Each carries a
# `property` link, so the guard can tell which hotel a call reaches into.
# Several candidates are tried in order (their naming series don't collide).
SCOPED_ARGS = {
	"reservation": ("Reservation", "POS Table Reservation"),
	"folio": ("Folio",), "from_folio": ("Folio",), "to_folio": ("Folio",),
	"folios": ("Folio",),
	"group_booking": ("Group Booking",), "group": ("Group Booking",),
	"order": ("POS Order", "Laundry Order"),
	"outlet": ("POS Outlet",),
	"room": ("Room",), "new_room": ("Room",),
	"task": ("Housekeeping Task", "Banquet Function Task"),
	"function": ("Venue Booking",),
	"venue": ("Venue",),
	"menu": ("Banquet Menu",),
	"menu_item": ("Menu Item",),
	"service_item": ("Banquet Service Item",),
	"ingredient": ("Ingredient",),
	"session": ("Cashier Session",),
	"ticket": ("Service Ticket",),
	"account": ("City Ledger Account",),
	"connection": ("Channel Manager Connection", "Channel Provider Connection"),
}


def restricted_properties() -> set[str] | None:
	"""The properties the current user is limited to by Frappe User
	Permissions, or None when they aren't restricted (they see them all)."""
	from frappe.core.doctype.user_permission.user_permission import (
		get_user_permissions)
	perms = get_user_permissions(frappe.session.user).get("Property")
	return {p.get("doc") for p in perms} if perms else None


def assert_property_access(property: str | None):
	"""Refuse a call aimed at a property the user isn't permitted for."""
	allowed = restricted_properties()
	if property and allowed is not None and property not in allowed:
		frappe.throw(f"You don't have access to {property}.",
		             frappe.PermissionError)


def assert_record_access(doctype: str, name: str | None):
	"""Same guard for a record: refuse it when it belongs to a property
	the user can't access."""
	if not name or restricted_properties() is None:
		return
	if frappe.get_meta(doctype).has_field("property"):
		assert_property_access(
			frappe.db.get_value(doctype, name, "property"))


def assert_guest_access(guest: str | None):
	"""Guest profiles are shared across the chain, so a guest has no single
	property. A restricted user may open one only if the guest has stayed
	(or is booked) at one of their properties, or has no stays yet."""
	allowed = restricted_properties()
	if not guest or allowed is None:
		return
	props = set(frappe.get_all("Reservation", filters={"guest": guest},
	                           pluck="property", distinct=True))
	if props and not props & allowed:
		frappe.throw("You don't have access to this guest.",
		             frappe.PermissionError)


def guest_scope_sql(alias: str = "g") -> tuple[str, dict]:
	"""SQL condition + params limiting a Guest query to the guests a
	restricted user may see (see assert_guest_access); ("1=1", {}) when
	the user isn't restricted."""
	allowed = restricted_properties()
	if allowed is None:
		return "1=1", {}
	return (
		f"(EXISTS (SELECT 1 FROM `tabReservation` gs WHERE gs.guest = {alias}.name"
		f" AND gs.property IN %(scope_properties)s)"
		f" OR NOT EXISTS (SELECT 1 FROM `tabReservation` gn"
		f" WHERE gn.guest = {alias}.name))",
		{"scope_properties": tuple(sorted(allowed)) or ("",)},
	)


def _values(value) -> list[str]:
	if isinstance(value, str) and value.startswith("["):
		try:
			value = json.loads(value)
		except ValueError:
			return [value]
	if isinstance(value, (list, tuple)):
		return [v for v in value if isinstance(v, str)]
	return [value] if isinstance(value, str) else []


def _enforce_property_scope(fn, args, kwargs, scope: dict):
	"""Check every argument that names a property-scoped record. A no-op
	for unrestricted users; unknown names are left for the endpoint's own
	not-found handling."""
	allowed = restricted_properties()
	if allowed is None:
		return
	try:
		bound = inspect.signature(fn).bind_partial(*args, **kwargs).arguments
	except TypeError:
		bound = kwargs
	for arg, value in bound.items():
		if arg == "property":
			assert_property_access(value if isinstance(value, str) else None)
			continue
		doctypes = scope.get(arg) or SCOPED_ARGS.get(arg)
		if not doctypes:
			continue
		if isinstance(doctypes, str):
			doctypes = (doctypes,)
		if doctypes == ("Guest",):
			for name in _values(value):
				assert_guest_access(name)
			continue
		for name in _values(value):
			for dt in doctypes:
				prop = frappe.db.get_value(dt, name, "property")
				if prop:
					assert_property_access(prop)
					break


def require_roles(*roles, scope: dict | None = None):
	"""Allow the listed roles (plus admins). Usage - below the
	whitelist decorator so the registered function is the guarded one:

	    @frappe.whitelist()
	    @require_roles("Front Desk", "Kamra Agent")
	    def check_in(...): ...

	It also enforces property scope: a user restricted to some properties
	can't pass a `property`, or a record id (see SCOPED_ARGS), that belongs
	to another one. `scope` adds endpoint-specific arguments, e.g.
	scope={"name": "Hurdle Rate"}. A "Guest" scope checks guest visibility
	(assert_guest_access) instead, since guests belong to the whole chain.
	"""
	allowed = set(roles) | set(ADMIN)
	scope = scope or {}

	def deco(fn):
		@wraps(fn)
		def guarded(*args, **kwargs):
			if not allowed & set(frappe.get_roles()):
				frappe.throw(
					f"Not permitted - needs one of: {', '.join(sorted(roles))}.",
					frappe.PermissionError)
			_enforce_property_scope(fn, args, kwargs, scope)
			return fn(*args, **kwargs)
		# introspectable RBAC: Kamra Agent filters its tool list by this
		guarded._kamra_roles = allowed
		return guarded
	return deco


def _pin_locked(doc) -> bool:
	if not doc.get("locked_until"):
		return False
	return now_datetime() < doc.locked_until


def require_cashier_pin(property: str, pin=None):
	"""The walk-up-to-an-unlocked-terminal guard: money actions re-confirm
	WHO is acting with a personal PIN, even inside a valid session.

	Skipped for agents (Kamra Agent role, the copilot's in-process tool calls,
	and gated replays) - their identity and accountability come from the
	autonomy gate + action log, not a keypad. Off unless the property enables
	require_cashier_pin.

	Supports a short unlock window via frappe.cache (set by verify_cashier_pin).
	"""
	if not property or not frappe.db.get_value(
			"Property", property, "require_cashier_pin"):
		return
	if getattr(frappe.flags, "kamra_agent_call", False) or \
	   getattr(frappe.flags, "kamra_gate_bypass", False):
		return
	if "Kamra Agent" in frappe.get_roles():
		return
	user = frappe.session.user
	if user == "Administrator":
		return

	# Sliding unlock window (set after a successful PinPad entry)
	cache_key = f"kamra_cashier_unlock:{user}"
	if frappe.cache.get_value(cache_key):
		# refresh sliding window
		frappe.cache.set_value(cache_key, 1, expires_in_sec=PIN_LOCK_MINUTES * 60)
		return

	if not frappe.db.exists("Cashier PIN", user):
		frappe.throw("PIN_NOT_SET: set your cashier PIN first (ask for it on "
		             "this screen), then retry.")
	doc = frappe.get_doc("Cashier PIN", user)
	if doc.get("must_reset"):
		frappe.throw("PIN_MUST_RESET: your PIN was reset by an admin - "
		             "enroll a new PIN first.")
	if _pin_locked(doc):
		frappe.throw("PIN_LOCKED: too many wrong attempts - try again later.")
	if not pin:
		frappe.throw("PIN_REQUIRED: this action needs your cashier PIN.")
	from frappe.utils.password import get_decrypted_password
	stored = get_decrypted_password("Cashier PIN", user, "pin",
	                                raise_exception=False)
	if not stored or str(pin).strip() != str(stored):
		attempts = int(doc.pin_attempts or 0) + 1
		doc.pin_attempts = attempts
		if attempts >= PIN_MAX_ATTEMPTS:
			doc.locked_until = add_to_date(now_datetime(),
			                               minutes=PIN_LOCK_MINUTES)
			doc.pin_attempts = 0
			doc.save(ignore_permissions=True)
			frappe.throw("PIN_LOCKED: too many wrong attempts - locked for "
			             f"{PIN_LOCK_MINUTES} minutes.")
		doc.save(ignore_permissions=True)
		frappe.throw("Wrong cashier PIN.")
	# success
	if doc.pin_attempts or doc.locked_until:
		doc.pin_attempts = 0
		doc.locked_until = None
		doc.save(ignore_permissions=True)
	frappe.cache.set_value(cache_key, 1, expires_in_sec=PIN_LOCK_MINUTES * 60)


def unlock_cashier_session(property: str, pin: str) -> dict:
	"""Explicit PinPad verify: validates PIN and opens the unlock window."""
	# Clear any existing unlock so we always re-validate
	frappe.cache.delete_value(f"kamra_cashier_unlock:{frappe.session.user}")
	require_cashier_pin(property, pin)
	return {"ok": True, "unlocked_minutes": PIN_LOCK_MINUTES}


def cashier_unlock_status(property: str) -> dict:
	required = bool(property and frappe.db.get_value(
		"Property", property, "require_cashier_pin"))
	user = frappe.session.user
	has_pin = bool(frappe.db.exists("Cashier PIN", user))
	must_reset = False
	locked = False
	if has_pin:
		doc = frappe.get_doc("Cashier PIN", user)
		must_reset = bool(doc.get("must_reset"))
		locked = _pin_locked(doc)
	unlocked = bool(frappe.cache.get_value(f"kamra_cashier_unlock:{user}"))
	return {
		"required": required,
		"has_pin": has_pin,
		"must_reset": must_reset,
		"locked": locked,
		"unlocked": unlocked or not required or user == "Administrator",
	}
