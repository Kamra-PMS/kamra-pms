"""Scoped service accounts for connected apps.

A connected app (a BI tool pulling reports, an approvals bot, a guest
channel) gets its own API identity instead of borrowing a person's key.
Each account is a Frappe user with:

- named scopes: the exact endpoints and MCP tools it may call, nothing
  else. Frappe's own REST (/api/resource), Desk pages and every Kamra
  endpoint outside the scopes are refused before they run;
- chosen properties, as User Permissions, so `require_roles` keeps it to
  those hotels like any restricted staff member;
- an API key that IT can rotate, and revoke with immediate effect;
- a row in the Agent Action Log for every call, allowed or refused.

The roles on the account's user are only what its scoped endpoints ask
for. The scope gate, not the roles, decides what it can reach.

Use the key on REST (`Authorization: token <key>:<secret>`) or on remote
MCP at /mcp (the same header, plus X-Kamra-Property when the account has
more than one property)."""

from __future__ import annotations

import json
import re

import frappe
from frappe import _
from frappe.utils import add_to_date, now_datetime

from kamra.authz import require_it_admin, restricted_properties

ROLE = "Kamra Service Account"
# every service account user lives on this domain, so telling one apart
# costs no query on other users' requests
DOMAIN = "@service.kamra.local"
LAST_USED_EVERY_MINUTES = 5

# Who a scoped endpoint is satisfied by, in order of preference. Never an
# admin role: an endpoint only admins may call can't be put in a scope.
_ROLE_PREFERENCE = ("Finance", "Front Desk", "Revenue Manager", "Night Auditor",
                    "Housekeeping", "Kamra Agent")

# scope -> label, MCP tool names (their endpoints are callable over REST too)
# and REST-only endpoints (dotted, without the "kamra." prefix)
SCOPES: dict[str, dict] = {
	"frontdesk.read": {
		"label": "Read front desk: today, availability, quotes, bookings",
		"tools": ("front_desk_today", "availability", "quote", "booking_options",
		          "find_reservations", "stay_detail"),
		"rest": (),
	},
	"reports.read": {
		"label": "Read reports: manager flash, night audit, report packs, books",
		"tools": ("manager_flash", "night_audit_report", "voids_allowances_report",
		          "sla_report", "list_report_packs", "run_report_pack",
		          "list_report_datasets", "list_custom_reports", "run_custom_report",
		          "profit_and_loss", "balance_sheet", "cash_forecast"),
		"rest": (),
	},
	"cashier.read": {
		"label": "Read cashier: shifts, folios, city ledger",
		"tools": ("cashier_shift_report", "get_folio", "stay_folios",
		          "city_ledger_aging", "ar_accounts", "ar_account_detail"),
		"rest": ("cashier.list_sessions",),
	},
	"approvals.write": {
		"label": "Approve: allowances, till variances, booking requests",
		"tools": ("allowance_requests", "booking_requests", "accept_booking_request",
		          "decline_booking_request"),
		"rest": ("api.decide_allowance", "cashier.approve_variance"),
	},
}

# harmless calls any key may make (a client checking its key works)
ALWAYS = frozenset({"frappe.auth.get_logged_user"})

_METHOD_PATH = re.compile(r"^/api/(?:v\d+/)?method/([\w.]+)/?$")


# --- what a scope opens --------------------------------------------------------


def _parse(value) -> list[str]:
	if not value:
		return []
	if isinstance(value, (list, tuple, set)):
		items = value
	else:
		try:
			items = json.loads(value)
		except (TypeError, ValueError):
			items = str(value).replace("\n", ",").split(",")
	return sorted({str(v).strip() for v in items if str(v).strip()})


def scope_tools(scopes) -> set[str]:
	return {t for s in _parse(scopes) for t in SCOPES.get(s, {}).get("tools", ())}


def scope_methods(scopes) -> set[str]:
	"""Dotted whitelisted methods (kamra.x.y) the scopes open."""
	from kamra.mcp_tools import BY_NAME

	out = {f"kamra.{BY_NAME[t].dotted}" for t in scope_tools(scopes)}
	for s in _parse(scopes):
		out |= {f"kamra.{m}" for m in SCOPES.get(s, {}).get("rest", ())}
	return out


def _endpoint(dotted: str):
	import importlib

	module, _, attr = dotted.rpartition(".")
	return getattr(importlib.import_module(module), attr)


def scope_roles(scopes) -> set[str]:
	"""The roles the account's user needs for its scoped endpoints to pass
	their own require_roles check. Throws for an endpoint only an admin may
	call: no scope may carry admin reach."""
	from kamra.mcp_tools import BY_NAME

	roles = {ROLE}
	for method in sorted(scope_methods(scopes)):
		allowed = getattr(_endpoint(method), "_kamra_roles", None)
		if not allowed:
			continue  # no role gate on this endpoint
		pick = next((r for r in _ROLE_PREFERENCE if r in allowed), None)
		if not pick:
			frappe.throw(_("{0} needs an admin and can't be in a scope.").format(method))
		roles.add(pick)
	tools = scope_tools(scopes)
	if tools:
		roles.add("MCP Manage" if any(BY_NAME[t].mutating for t in tools) else "MCP Read")
	return roles


# --- who is calling ------------------------------------------------------------


def account_for(user: str | None = None) -> frappe._dict | None:
	"""The service account behind this user, or None for anyone else. A
	service account user with no live account comes back as a revoked
	account, so it can reach nothing."""
	user = user or frappe.session.user
	if not user or not user.endswith(DOMAIN):
		return None
	# per request (frappe.local.cache is reset by frappe.init): tools/list
	# asks once per tool
	cache = frappe.local.cache.setdefault("kamra_service_accounts", {})
	if user not in cache:
		row = frappe.db.get_value(
			"Kamra Service Account", {"user": user},
			["name", "account_name", "scopes", "enabled", "last_used"], as_dict=True)
		cache[user] = row or frappe._dict(name=None, account_name=user, scopes="",
		                                  enabled=0, last_used=None)
		cache[user].user = user
	return cache[user]


def refusal(account, path: str) -> str | None:
	"""Why this account may not make this request, or None."""
	if not account.enabled or not account.name:
		return _("This service account has been revoked.")
	if not restricted_properties(account.user):
		# a service account always names its properties; without them it
		# would reach every hotel
		return _("This service account has no properties.")
	if path == "/mcp":
		if scope_tools(account.scopes):
			return None
		return _("This service account's scope has no MCP tools.")
	match = _METHOD_PATH.match(path or "")
	if match and (match.group(1) in ALWAYS or match.group(1) in scope_methods(account.scopes)):
		return None
	return _("Outside this service account's scope: {0}").format(
		match.group(1) if match else path)


def enforce_scope():
	"""auth_hooks: runs after Frappe has resolved the API key to its user,
	before the endpoint. Refuses anything outside the account's scope."""
	request = getattr(frappe.local, "request", None)
	if not request:
		return
	account = account_for()
	if not account:
		return
	why = refusal(account, request.path)
	if why:
		frappe.local.flags.kamra_service_refusal = why
		raise frappe.PermissionError(why)


def tool_refusal(spec) -> str | None:
	"""For mcp_access: a service account sees only its scoped tools."""
	account = account_for()
	if account and spec.name not in scope_tools(account.scopes):
		return _("{0} is outside this service account's scope.").format(spec.name)
	return None


def after_request(request, response):
	"""Log every service account call in the Agent Action Log."""
	try:
		account = account_for()
	except Exception:
		return
	if not account:
		return
	path = request.path or ""
	status = getattr(response, "status_code", None) or 500
	what = path
	match = _METHOD_PATH.match(path)
	if match:
		what = match.group(1)
	elif path == "/mcp":
		what = " ".join(["mcp", *_mcp_calls(request)])
	refused = getattr(frappe.local.flags, "kamra_service_refusal", None)
	prop = (request.headers.get("X-Kamra-Property") or frappe.form_dict.get("property")
	        or None)
	allowed = restricted_properties(account.user) or set()
	if not isinstance(prop, str) or prop not in allowed:
		prop = next(iter(allowed)) if len(allowed) == 1 else None

	from kamra.savings import log_action
	log_action(
		"service_account.call",
		"Kamra Service Account" if account.name else None, account.name,
		property=prop,
		rationale=(f"{request.method} {what} -> {status}"
		           + (f" (refused: {refused})" if refused else ""))[:1000],
		agent_name=account.account_name,
		channel="MCP" if path == "/mcp" else "API",
		approval_status="Rejected" if refused or status >= 400 else "Executed",
	)
	last = account.get("last_used")
	if account.name and (not last or last < add_to_date(
			now_datetime(), minutes=-LAST_USED_EVERY_MINUTES)):
		frappe.db.set_value("Kamra Service Account", account.name, "last_used",
		                    now_datetime(), update_modified=False)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- after_request runs after Frappe's own commit or rollback; the audit row must persist for refused calls too


def _mcp_calls(request) -> list[str]:
	try:
		body = json.loads(request.get_data() or b"null")
	except (TypeError, ValueError):
		return []
	items = body if isinstance(body, list) else [body]
	out = []
	for msg in items:
		if not isinstance(msg, dict):
			continue
		if msg.get("method") == "tools/call":
			out.append(str((msg.get("params") or {}).get("name") or "?")[:80])
		elif msg.get("method"):
			out.append(str(msg["method"])[:40])
	return out[:20]


# --- IT: create, rotate, revoke ------------------------------------------------


def _ensure_role():
	if not frappe.db.exists("Role", ROLE):
		frappe.get_doc({"doctype": "Role", "role_name": ROLE, "desk_access": 0}).insert(
			ignore_permissions=True)


def _new_secret(user: str) -> dict:
	doc = frappe.get_doc("User", user)
	if not doc.api_key:
		doc.api_key = frappe.generate_hash(length=15)
	secret = frappe.generate_hash(length=32)
	doc.api_secret = secret
	doc.flags.ignore_permissions = True
	doc.save()
	return {"api_key": doc.api_key, "api_secret": secret}


def _check(scopes, properties) -> tuple[list[str], list[str]]:
	scopes = _parse(scopes)
	properties = _parse(properties)
	if not scopes:
		frappe.throw(_("Pick at least one scope."))
	unknown = [s for s in scopes if s not in SCOPES]
	if unknown:
		frappe.throw(_("Unknown scope: {0}").format(", ".join(unknown)))
	if not properties:
		frappe.throw(_("Pick at least one property."))
	missing = [p for p in properties if not frappe.db.exists("Property", p)]
	if missing:
		frappe.throw(_("Unknown property: {0}").format(", ".join(missing)))
	return scopes, properties


@frappe.whitelist()
@require_it_admin
def list_scopes() -> list[dict]:
	return [{"scope": k, "label": v["label"], "tools": list(v["tools"])}
	        for k, v in SCOPES.items()]


@frappe.whitelist()
@require_it_admin
def list_service_accounts() -> list[dict]:
	rows = frappe.get_all(
		"Kamra Service Account",
		fields=["name", "account_name", "user", "enabled", "scopes", "properties",
		        "last_used", "revoked_on", "creation"],
		order_by="creation desc")
	for r in rows:
		r["scopes"] = _parse(r["scopes"])
		r["properties"] = _parse(r["properties"])
	return rows


@frappe.whitelist(methods=["POST"])
@require_it_admin
def create_service_account(account_name: str, scopes: str | list, properties: str | list) -> dict:
	"""A new service account. The secret is shown once, here."""
	account_name = (account_name or "").strip()
	if not account_name:
		frappe.throw(_("Name the connected app."))
	scopes, properties = _check(scopes, properties)
	roles = scope_roles(scopes)
	_ensure_role()

	email = f"svc-{frappe.generate_hash(length=10)}{DOMAIN}"
	user = frappe.get_doc({
		"doctype": "User", "email": email, "first_name": account_name[:60],
		"last_name": "(service account)", "enabled": 1, "send_welcome_email": 0,
		"roles": [{"role": r} for r in sorted(roles)],
	})
	user.flags.no_welcome_mail = True
	user.insert(ignore_permissions=True)
	for p in properties:
		frappe.get_doc({"doctype": "User Permission", "user": email, "allow": "Property",
		                "for_value": p, "apply_to_all_doctypes": 1}).insert(
			ignore_permissions=True)
	doc = frappe.get_doc({
		"doctype": "Kamra Service Account", "account_name": account_name,
		"user": email, "enabled": 1, "scopes": json.dumps(scopes),
		"properties": json.dumps(properties),
	}).insert(ignore_permissions=True)
	keys = _new_secret(email)

	from kamra.savings import log_action
	log_action("service_account.created", "Kamra Service Account", doc.name,
	           property=properties[0] if len(properties) == 1 else None,
	           rationale=f"{account_name}: {', '.join(scopes)} at {', '.join(properties)}",
	           channel="API")
	return {"name": doc.name, "user": email, "scopes": scopes,
	        "properties": properties, **keys}


@frappe.whitelist(methods=["POST"])
@require_it_admin
def rotate_service_account_key(account: str) -> dict:
	"""A new secret; the old one stops working now. Shown once."""
	doc = frappe.get_doc("Kamra Service Account", account)
	if not doc.enabled:
		frappe.throw(_("This service account is revoked. Create a new one."))
	keys = _new_secret(doc.user)
	from kamra.savings import log_action
	log_action("service_account.rotated", "Kamra Service Account", doc.name,
	           rationale=f"New key for {doc.account_name}", channel="API")
	return {"name": doc.name, **keys}


@frappe.whitelist(methods=["POST"])
@require_it_admin
def revoke_service_account(account: str) -> dict:
	"""Stop the account at once: its user is disabled and its secret
	replaced, so the next call with the old key fails to sign in."""
	doc = frappe.get_doc("Kamra Service Account", account)
	if doc.enabled:
		_new_secret(doc.user)  # the old secret no longer matches
		frappe.db.set_value("User", doc.user, "enabled", 0)
		doc.db_set({"enabled": 0, "revoked_on": now_datetime(),
		            "revoked_by": frappe.session.user})
		from frappe.sessions import clear_sessions
		clear_sessions(doc.user, force=True)
		frappe.local.cache.get("kamra_service_accounts", {}).pop(doc.user, None)
		from kamra.savings import log_action
		log_action("service_account.revoked", "Kamra Service Account", doc.name,
		           rationale=f"Revoked {doc.account_name}", channel="API")
	return {"ok": True, "name": doc.name, "enabled": 0}
