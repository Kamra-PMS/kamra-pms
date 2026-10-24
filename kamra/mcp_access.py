"""Who may use Kamra over MCP, and what an AI client may do for them.

Two roles open the MCP server, assigned per person by a hotel admin:

- MCP Read: the AI can look (arrivals, folios, reports) but not change.
- MCP Manage: the AI may also make changes.

They only open the door. What a tool can see or do is still limited by the
person's normal Kamra roles (`require_roles` on every endpoint), so nobody
can do more through Claude than they can in Kamra itself. Hotel Admin and
IT (authz.ADMIN) always have Manage.

Each property adds its own switches: AI access on or off, read-only for
everyone, and individual tools blocked. Roles and switches are read on
every request, so a change applies to the very next tool call.

The in-app Kamra Agent does not go through here: these rules are for
outside AI clients reaching /mcp."""

from __future__ import annotations

import json
from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.utils import add_to_date, now_datetime

from kamra.authz import ADMIN, IT_ADMIN, require_it_admin, require_roles, restricted_properties

MCP_READ = "MCP Read"
MCP_MANAGE = "MCP Manage"
MCP_ROLES = (MCP_READ, MCP_MANAGE)

NO_ACCESS = ("Your Kamra user has no MCP access. Ask your hotel admin for "
             "MCP Read or MCP Manage.")
READ_ONLY = ("Your MCP access is read-only (MCP Read), so the AI can't make "
             "changes. Ask your hotel admin for MCP Manage.")

# site-wide extra OAuth redirect URIs (self-hosted n8n and similar)
REDIRECTS_KEY = "kamra_mcp_extra_redirect_uris"
LAST_USED_EVERY_MINUTES = 5


def ensure_roles():
	"""Roles only; what they unlock is enforced here, never in DocPerms."""
	for role in MCP_ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({
				"doctype": "Role", "role_name": role, "desk_access": 0,
			}).insert(ignore_permissions=True)


# --- who and what --------------------------------------------------------------


def mcp_level(user: str | None = None) -> str | None:
	"""'manage', 'read' or None for this user."""
	user = user or frappe.session.user
	if user == "Administrator":
		return "manage"
	roles = set(frappe.get_roles(user))
	if roles & set(ADMIN) or MCP_MANAGE in roles:
		return "manage"
	if MCP_READ in roles:
		return "read"
	return None


def property_policy(property: str | None) -> frappe._dict:
	"""The property's AI switches. A property saved before these fields
	existed has AI access on, writes allowed and nothing blocked."""
	row = frappe.db.get_value(
		"Property", property,
		["property_name", "mcp_enabled", "mcp_read_only", "mcp_blocked_tools"],
		as_dict=True) if property else None
	if not row:
		return frappe._dict(name=property, property_name=property, enabled=False,
		                    read_only=False, blocked=set())
	return frappe._dict(
		name=property,
		property_name=row.property_name or property,
		enabled=row.mcp_enabled is None or bool(int(row.mcp_enabled)),
		read_only=bool(int(row.mcp_read_only or 0)),
		blocked=set(_tool_names(row.mcp_blocked_tools)),
	)


def access_refusal(user: str, property: str | None = None) -> str | None:
	"""Why this user can't use MCP (at this property), or None."""
	if not mcp_level(user):
		return NO_ACCESS
	if property:
		policy = property_policy(property)
		if not policy.enabled:
			return _("AI access over MCP is turned off for {0}. A hotel admin can "
			         "turn it on under Settings, AI access (MCP).").format(policy.property_name)
	return None


def tool_refusal(spec, level: str | None, policy) -> str | None:
	"""Why this tool can't run for this level at this property, or None."""
	if not level:
		return NO_ACCESS
	if spec.name in policy.blocked:
		return _("A hotel admin has blocked {0} for AI clients at {1}.").format(
			spec.name, policy.property_name)
	if spec.mutating:
		if level != "manage":
			return READ_ONLY
		if policy.read_only:
			return _("AI clients are read-only at {0}: a hotel admin has blocked "
			         "every tool that makes changes.").format(policy.property_name)
	return None


def permitted_tools(tools, level: str | None, policy) -> list:
	return [t for t in tools if tool_refusal(t, level, policy) is None]


def _tool_names(value) -> list[str]:
	if not value:
		return []
	if isinstance(value, (list, tuple)):
		items = value
	else:
		try:
			items = json.loads(value)
		except (TypeError, ValueError):
			items = str(value).replace("\n", ",").split(",")
		if not isinstance(items, list):
			items = [items]
	return sorted({str(v).strip() for v in items if str(v).strip()})


def touch_grant(grant) -> None:
	"""Record when a connection was last used, at most every few minutes so
	a busy client doesn't write on every call."""
	last = grant.get("last_used")
	if last and last > add_to_date(now_datetime(), minutes=-LAST_USED_EVERY_MINUTES):
		return
	frappe.db.set_value("MCP OAuth Grant", grant.name, "last_used", now_datetime(),
	                    update_modified=False)


# --- extra redirect URIs ---------------------------------------------------------


def extra_redirect_uris() -> list[str]:
	raw = frappe.db.get_default(REDIRECTS_KEY)
	if not raw:
		return []
	try:
		items = json.loads(raw)
	except (TypeError, ValueError):
		return []
	return [str(u) for u in items if isinstance(u, str)]


def redirect_uri_problem(uri: str) -> str | None:
	"""Why an admin-entered redirect URI is refused, or None."""
	uri = (uri or "").strip()
	parsed = urlparse(uri)
	if parsed.scheme != "https" or not parsed.hostname:
		return _("{0}: use a full https:// address.").format(uri or _("(empty)"))
	if "*" in uri:
		return _("{0}: wildcards are not allowed; enter the exact address.").format(uri)
	if parsed.fragment or "#" in uri:
		return _("{0}: an address with # can't be a redirect.").format(uri)
	if parsed.username or parsed.password:
		return _("{0}: remove the user name and password.").format(uri)
	if len(uri) > 500:
		return _("That address is too long.")
	return None


# --- admin screen: Settings, AI access (MCP) ---------------------------------------


def _assert_admin():
	if not (set(ADMIN) & set(frappe.get_roles())):
		frappe.throw(_("Only a hotel admin can manage AI access."), frappe.PermissionError)


def _staff_for(property: str) -> list[dict]:
	from kamra.staff import list_staff

	return list_staff(property)


@frappe.whitelist()
@require_roles()
def access_overview(property: str) -> dict:
	"""Everything the AI access page shows: the property switches, who has
	which MCP role, the live connections and the recent AI actions."""
	_assert_admin()
	from kamra.mcp_tools import TOOLS

	policy = property_policy(property)
	staff = []
	for s in _staff_for(property):
		admin = bool(set(s["roles"]) & set(ADMIN)) or "System Manager" in s["roles"]
		staff.append({
			"user": s["user"], "full_name": s["full_name"], "email": s["email"],
			"enabled": s["enabled"], "roles": s["roles"], "is_self": s["is_self"],
			"level": "admin" if admin else (mcp_level(s["user"]) or "none"),
			"editable": s["editable"] and not admin,
		})

	grants = frappe.db.sql(
		"""
		SELECT g.name, g.user, g.creation, g.last_used, g.access_expires,
		       g.refresh_expires, c.client_name, u.full_name
		FROM `tabMCP OAuth Grant` g
		LEFT JOIN `tabMCP OAuth Client` c ON c.name = g.client
		LEFT JOIN `tabUser` u ON u.name = g.user
		WHERE g.property = %(p)s AND g.revoked = 0
		  AND IFNULL(g.access_token_hash, '') != ''
		  AND (g.refresh_expires IS NULL OR g.refresh_expires > NOW())
		ORDER BY COALESCE(g.last_used, g.creation) DESC
		LIMIT 200
		""", {"p": property}, as_dict=True)
	connections = [{
		"name": g.name, "user": g.user, "full_name": g.full_name or g.user,
		"client_name": g.client_name or _("MCP client"),
		"created": str(g.creation) if g.creation else None,
		"last_used": str(g.last_used) if g.last_used else None,
	} for g in grants]

	recent = frappe.get_all(
		"Agent Action Log",
		filters={"action_channel": "MCP", "property": property},
		fields=["name", "creation", "actor", "action_type"],
		order_by="creation desc", limit=10)

	return {
		"property": property,
		"property_name": policy.property_name,
		"site_disabled": bool(frappe.conf.get("kamra_mcp_disabled")),
		"enabled": policy.enabled,
		"read_only": policy.read_only,
		"blocked_tools": sorted(policy.blocked),
		"tools": [{"name": t.name, "group": t.group, "mutating": t.mutating}
		          for t in TOOLS],
		"staff": staff,
		"connections": connections,
		"recent": [{"name": r.name, "creation": str(r.creation), "actor": r.actor,
		            "action_type": r.action_type} for r in recent],
		"redirect_uris": extra_redirect_uris(),
		"can_edit_redirects": bool(set(IT_ADMIN) & set(frappe.get_roles())),
	}


@frappe.whitelist(methods=["POST"])
@require_roles()
def set_mcp_level(property: str, user: str, level: str) -> dict:
	"""Give a person no MCP access, MCP Read or MCP Manage. Their other
	roles are left alone; admins already have full access."""
	_assert_admin()
	if level not in ("none", "read", "manage"):
		frappe.throw(_("Pick none, read or manage."))
	row = next((s for s in _staff_for(property) if s["user"] == user), None)
	if not row:
		frappe.throw(_("That person isn't on the staff list for this property."),
		             frappe.PermissionError)
	if row["is_self"]:
		frappe.throw(_("You can't change your own AI access."), frappe.PermissionError)
	if not row["editable"]:
		frappe.throw(_("Only IT can change this person's access."), frappe.PermissionError)
	if set(row["roles"]) & set(ADMIN):
		frappe.throw(_("Hotel admins and IT always have full AI access."))

	before = mcp_level(user) or "none"
	doc = frappe.get_doc("User", user)
	keep = [r.role for r in doc.roles if r.role not in MCP_ROLES]
	doc.set("roles", [])
	for r in keep:
		doc.append("roles", {"role": r})
	if level == "read":
		doc.append("roles", {"role": MCP_READ})
	elif level == "manage":
		doc.append("roles", {"role": MCP_MANAGE})
	doc.flags.ignore_permissions = True
	doc.save()

	from kamra.savings import log_action
	log_action("mcp_access_changed", "User", user, property=property,
	           rationale=f"AI access for {user}: {before} to {level}",
	           before_snapshot={"level": before}, after_snapshot={"level": level})
	return {"ok": True, "user": user, "level": level}


@frappe.whitelist(methods=["POST"])
@require_roles()
def set_mcp_policy(property: str, enabled=None, read_only=None, blocked_tools=None) -> dict:
	"""Change this property's AI switches. Pass only what changes."""
	_assert_admin()
	from kamra.mcp_tools import BY_NAME

	before = property_policy(property)
	changes: dict = {}
	if enabled is not None:
		changes["mcp_enabled"] = 1 if str(enabled).lower() in ("1", "true") else 0
	if read_only is not None:
		changes["mcp_read_only"] = 1 if str(read_only).lower() in ("1", "true") else 0
	if blocked_tools is not None:
		names = _tool_names(blocked_tools)
		unknown = [n for n in names if n not in BY_NAME]
		if unknown:
			frappe.throw(_("Unknown tool: {0}").format(", ".join(unknown)))
		changes["mcp_blocked_tools"] = json.dumps(names) if names else ""
	if not changes:
		return {"ok": True}
	frappe.db.set_value("Property", property, changes)

	from kamra.savings import log_action
	after = property_policy(property)
	log_action("mcp_policy_changed", "Property", property, property=property,
	           rationale="AI access switches changed",
	           before_snapshot={"enabled": before.enabled, "read_only": before.read_only,
	                            "blocked": sorted(before.blocked)},
	           after_snapshot={"enabled": after.enabled, "read_only": after.read_only,
	                           "blocked": sorted(after.blocked)})
	return {"ok": True, "enabled": after.enabled, "read_only": after.read_only,
	        "blocked_tools": sorted(after.blocked)}


@frappe.whitelist(methods=["POST"])
@require_roles()
def revoke_connection(property: str, grant: str) -> dict:
	"""Disconnect one AI client. It has to sign in again to come back."""
	_assert_admin()
	row = frappe.db.get_value("MCP OAuth Grant", grant, ["property", "user", "revoked"],
	                          as_dict=True)
	if not row or row.property != property:
		frappe.throw(_("That connection isn't at this property."), frappe.PermissionError)
	if not int(row.revoked or 0):
		frappe.db.set_value("MCP OAuth Grant", grant, "revoked", 1)
		from kamra.savings import log_action
		log_action("mcp_connection_revoked", "Property", property, property=property,
		           rationale=f"Disconnected an AI client of {row.user}")
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
@require_it_admin
def set_extra_redirect_uris(uris) -> dict:
	"""Extra OAuth redirect addresses for clients Kamra doesn't know by name,
	such as a self-hosted n8n. https only, exact match, no wildcards. IT only:
	it applies to every property on the site."""
	if isinstance(uris, str):
		try:
			uris = json.loads(uris)
		except ValueError:
			uris = uris.split("\n")
	clean = []
	for u in uris or []:
		u = str(u).strip()
		if not u:
			continue
		problem = redirect_uri_problem(u)
		if problem:
			frappe.throw(problem)
		if u not in clean:
			clean.append(u)
	if len(clean) > 20:
		frappe.throw(_("At most 20 extra addresses."))
	frappe.db.set_default(REDIRECTS_KEY, json.dumps(clean))

	from kamra.savings import log_action
	log_action("mcp_redirects_changed", "User", frappe.session.user,
	           rationale=f"{len(clean)} extra MCP redirect address(es)")
	return {"ok": True, "redirect_uris": clean}


def visible_properties(user: str) -> list[dict]:
	"""Properties this user may connect an AI client to: within their scope
	and with AI access on."""
	allowed = restricted_properties(user)
	rows = frappe.get_all("Property", fields=["name", "property_name"],
	                      order_by="property_name asc")
	return [r for r in rows
	        if (allowed is None or r.name in allowed) and property_policy(r.name).enabled]
