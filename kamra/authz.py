"""Endpoint authorization - Frappe checks doctype permissions on ORM
paths, but raw-SQL reads and db.set_value writes sail past them. Every
whitelisted Kamra endpoint therefore declares who may call it."""

from functools import wraps

import frappe

ADMIN = ("System Manager", "Administrator", "Hotel Admin")

# IT / site admins only - deliberately EXCLUDES the Hotel Admin business role.
# For user management, developer settings and API keys.
IT_ADMIN = ("System Manager", "Administrator")


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
		# introspectable RBAC: the copilot filters its tool list by this
		guarded._kamra_roles = allowed
		return guarded
	return deco


def require_cashier_pin(property: str, pin=None):
	"""The walk-up-to-an-unlocked-terminal guard: money actions re-confirm
	WHO is acting with a personal PIN, even inside a valid session.

	Skipped for agents (Kamra Agent role, the copilot's in-process tool calls,
	and gated replays) - their identity and accountability come from the
	autonomy gate + action log, not a keypad. Off unless the property enables
	require_cashier_pin."""
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
	if not frappe.db.exists("Cashier PIN", user):
		frappe.throw("PIN_NOT_SET: set your cashier PIN first (ask for it on "
		             "this screen), then retry.")
	if not pin:
		frappe.throw("PIN_REQUIRED: this action needs your cashier PIN.")
	from frappe.utils.password import get_decrypted_password
	stored = get_decrypted_password("Cashier PIN", user, "pin",
	                                raise_exception=False)
	if not stored or str(pin).strip() != str(stored):
		frappe.throw("Wrong cashier PIN.")
