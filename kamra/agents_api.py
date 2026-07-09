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
	if property:
		conds.append("property = %(property)s")
		params["property"] = property
	if actor_kind == "agent":
		conds.append("COALESCE(agent_name, '') != ''")
	elif actor_kind == "human":
		conds.append("COALESCE(agent_name, '') = ''")
	if action_type:
		conds.append("action_type = %(action_type)s")
		params["action_type"] = action_type
	where = ("WHERE " + " AND ".join(conds)) if conds else ""
	return frappe.db.sql(f"""
		SELECT name, creation, actor, agent_name, action_type, action_channel,
		       approval_status, autonomy, approver, reference_doctype,
		       reference_name, rationale, minutes_saved, executed_at
		FROM `tabAgent Action Log`
		{where}
		ORDER BY creation DESC
		LIMIT %(limit)s OFFSET %(start)s
	""", params, as_dict=True)


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Revenue Manager", "Kamra Agent")
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
