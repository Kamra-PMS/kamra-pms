"""Endpoint authorization - Frappe checks doctype permissions on ORM
paths, but raw-SQL reads and db.set_value writes sail past them. Every
whitelisted Kamra endpoint therefore declares who may call it."""

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


def require_roles(*roles):
	"""Allow the listed roles (plus admins). Usage - below the
	whitelist decorator so the registered function is the guarded one:

	    @frappe.whitelist()
	    @require_roles("Front Desk", "Kamra Agent")
	    def check_in(...): ...
	"""
	allowed = set(roles) | set(ADMIN)

	def deco(fn):
		@wraps(fn)
		def guarded(*args, **kwargs):
			if not allowed & set(frappe.get_roles()):
				frappe.throw(
					f"Not permitted - needs one of: {', '.join(sorted(roles))}.",
					frappe.PermissionError)
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
