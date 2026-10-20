"""The activity ledger API - every action anyone took, human or AI.

Kamra has no native agents; this reads the shared audit log (Agent Action Log)
that records human actions and any connected AI's actions alike."""

from __future__ import annotations

import frappe

from kamra.authz import require_roles


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Revenue Manager", "Kamra Agent")
def activity_feed(property: str | None = None, actor_kind: str | None = None,
                  action_type: str | None = None, limit: int = 50,
                  start: int = 0) -> list[dict]:
	"""The one ledger: every action anyone took - human or AI - newest first.
	actor_kind filters to "human" or "agent"."""
	conds, params = [], {"limit": min(int(limit), 200), "start": int(start)}
	from kamra.authz import restricted_properties
	allowed = restricted_properties()
	if property:
		conds.append("property = %(property)s")
		params["property"] = property
	elif allowed is not None:
		conds.append("property IN %(allowed)s")
		params["allowed"] = tuple(sorted(allowed)) or ("",)
	if actor_kind == "agent":
		conds.append("COALESCE(agent_name, '') != ''")
	elif actor_kind == "human":
		conds.append("COALESCE(agent_name, '') = ''")
	if action_type:
		conds.append("action_type = %(action_type)s")
		params["action_type"] = action_type
	where = ("WHERE " + " AND ".join(conds)) if conds else ""
	return frappe.db.sql(f"""  # nosemgrep: frappe-sql-format-injection -- values are parameterized; interpolated text is a constant or whitelisted identifier, not user input
		SELECT name, creation, actor, agent_name, action_type, action_channel,
		       approval_status, autonomy, approver, reference_doctype,
		       reference_name, rationale, minutes_saved, executed_at
		FROM `tabAgent Action Log`
		{where}
		ORDER BY creation DESC
		LIMIT %(limit)s OFFSET %(start)s
	""", params, as_dict=True)


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Revenue Manager", "Kamra Agent", scope={"name": "Agent Action Log"})
def activity_detail(name: str) -> dict:
	"""Everything one ledger row knows — including the before/after
	snapshots that are too heavy for the feed."""
	doc = frappe.get_doc("Agent Action Log", name)

	def _json(v):
		if not v:
			return None
		try:
			return frappe.parse_json(v)
		except Exception:
			return v

	return {
		"name": doc.name,
		"creation": doc.creation,
		"executed_at": doc.executed_at,
		"property": doc.property,
		"actor": doc.actor,
		"agent_name": doc.agent_name,
		"action_type": doc.action_type,
		"action_channel": doc.action_channel,
		"autonomy": doc.autonomy,
		"approval_status": doc.approval_status,
		"approver": doc.approver,
		"reference_doctype": doc.reference_doctype,
		"reference_name": doc.reference_name,
		"rationale": doc.rationale,
		"minutes_saved": doc.minutes_saved,
		"before_snapshot": _json(doc.before_snapshot),
		"after_snapshot": _json(doc.after_snapshot),
	}


def _property_staff(property: str) -> list[str]:
	"""Users with a Kamra role who can reach this property (unrestricted,
	or given it as a User Permission) - the people on its staff list."""
	from kamra.staff import NEVER_LISTED, ROLE_NAMES
	users = set(frappe.get_all(
		"Has Role", filters={"role": ("in", ROLE_NAMES), "parenttype": "User"},
		pluck="parent")) - set(NEVER_LISTED)
	if not users:
		return []
	perms: dict[str, set] = {}
	for p in frappe.get_all("User Permission",
	                        filters={"user": ("in", list(users)), "allow": "Property"},
	                        fields=["user", "for_value"]):
		perms.setdefault(p.user, set()).add(p.for_value)
	return sorted(u for u in users if u not in perms or property in perms[u])


@frappe.whitelist()
@require_roles("Hotel Admin", "Finance", "System Manager")
def staff_sign_ins(property: str, limit: int = 50, start: int = 0,
                   user: str | None = None) -> list[dict]:
	"""Who signed in to and out of Kamra, newest first: Frappe's own Login /
	Logout records (Activity Log), limited to this property's staff. Only
	what Frappe already stores is shown - who, when, in or out, and whether
	the attempt worked. IP addresses are left out."""
	from kamra.authz import assert_property_access
	assert_property_access(property)
	staff = _property_staff(property)
	if user:
		staff = [u for u in staff if u == user]
	if not staff:
		return []
	rows = frappe.get_all(
		"Activity Log",
		filters={"operation": ("in", ("Login", "Logout")), "user": ("in", staff)},
		fields=["name", "creation", "user", "full_name", "operation", "status"],
		order_by="creation desc",
		limit_start=int(start), limit_page_length=min(int(limit), 200),
		ignore_permissions=True,
	)
	return [{
		"name": r.name, "creation": str(r.creation), "user": r.user,
		"full_name": r.full_name or r.user, "operation": r.operation,
		"status": r.status or "Success",
	} for r in rows]
