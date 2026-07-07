"""Whitelisted APIs backing the Agents screen (Team / Inbox / Timeline).

Every write here (approve / reject) routes through the Autonomy Gate so
the audit trail is honest - an approver's tap is itself an action, logged
under their identity, with the replayed endpoint's own log entry linked.
"""

from __future__ import annotations

import json

import frappe

from kamra import autonomy
from kamra.authz import require_roles


# ---------------------------------------------------------------------------
# Team tab
# ---------------------------------------------------------------------------


@frappe.whitelist()
@require_roles("Front Desk", "Hotel Admin", "Kamra Agent")
def agents_list(property: str | None = None, include_inactive: int = 0) -> list[dict]:
	"""Cards for the Team tab. Property-scoped by default; blank returns
	chain-global agents plus property-specific ones this user can see."""
	filters: dict = {}
	if property:
		filters["property"] = ("in", [property, ""])
	if not int(include_inactive or 0):
		filters["active"] = 1

	rows = frappe.get_all(
		"Agent",
		filters=filters,
		fields=[
			"name",
			"agent_name",
			"persona",
			"active",
			"property",
			"trigger_type",
			"schedule_cron",
			"channel",
			"model",
			"default_approver",
			"modified",
		],
		order_by="active desc, persona asc, agent_name asc",
	)

	for row in rows:
		row["tools"] = frappe.get_all(
			"Agent Tool",
			filters={"parent": row["name"]},
			pluck="tool_name",
			order_by="idx",
		)
		row["autonomy_rules"] = frappe.get_all(
			"Agent Autonomy Rule",
			filters={"parent": row["name"]},
			fields=[
				"action_type",
				"autonomy",
				"threshold_field",
				"threshold_operator",
				"threshold_value",
			],
			order_by="idx",
		)
		row["last_action_at"] = frappe.db.sql(
			"""
			SELECT MAX(creation) FROM `tabAgent Action Log`
			WHERE agent_name IN (%s, %s)
			""",
			(row["agent_name"], row["name"]),
		)[0][0]
		row["minutes_saved_week"] = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(minutes_saved), 0)
			FROM `tabAgent Action Log`
			WHERE agent_name IN (%s, %s)
			  AND creation >= DATE_SUB(NOW(), INTERVAL 7 DAY)
			""",
			(row["agent_name"], row["name"]),
		)[0][0] or 0
		row["pending_count"] = frappe.db.count(
			"Pending Agent Action",
			{"agent": row["name"], "status": "Pending"},
		)
	return rows


@frappe.whitelist()
@require_roles("Hotel Admin")
def toggle_agent(agent: str, active: int) -> dict:
	"""Pause or resume a named agent. Hotel Admin only - turning off Revenue
	Bot mid-day should be an intentional GM decision."""
	frappe.db.set_value("Agent", agent, "active", 1 if int(active) else 0)
	return {"agent": agent, "active": 1 if int(active) else 0}


# ---------------------------------------------------------------------------
# Inbox tab
# ---------------------------------------------------------------------------


@frappe.whitelist()
@require_roles("Front Desk", "Hotel Admin", "Kamra Agent")
def pending_actions(
	property: str | None = None,
	agent: str | None = None,
	include_resolved: int = 0,
	limit: int = 50,
) -> list[dict]:
	"""Inbox rows. Newest first. Resolved items are hidden by default."""
	filters: dict = {}
	if property:
		filters["property"] = property
	if agent:
		filters["agent"] = agent
	if not int(include_resolved or 0):
		filters["status"] = "Pending"

	rows = frappe.get_all(
		"Pending Agent Action",
		filters=filters,
		fields=[
			"name",
			"agent",
			"action_type",
			"status",
			"property",
			"summary",
			"action_endpoint",
			"reference_doctype",
			"reference_name",
			"requested_by",
			"action_log",
			"approver",
			"decision_note",
			"expires_at",
			"resolved_at",
			"creation",
		],
		order_by="creation desc",
		limit=int(limit),
	)

	# Hydrate before-snapshot for the diff preview - kept out of the list
	# call so a wide table stays cheap; here we're capped at `limit`.
	for row in rows:
		if row.get("action_log"):
			snap_before, snap_after = frappe.db.get_value(
				"Agent Action Log",
				row["action_log"],
				["before_snapshot", "after_snapshot"],
			) or (None, None)
			row["before_snapshot"] = _parse_json(snap_before)
			row["after_snapshot"] = _parse_json(snap_after)
	return rows


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin")
def approve_action(pending: str, note: str = "") -> dict:
	"""Replay the parked call. Hotel Admin bypasses any per-property approver
	restriction; Front Desk can approve their own department's items."""
	return autonomy.approve_pending(pending, approver=frappe.session.user, note=note)


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin")
def reject_action(pending: str, reason: str = "") -> dict:
	return autonomy.reject_pending(pending, approver=frappe.session.user, reason=reason)


# ---------------------------------------------------------------------------
# Timeline tab
# ---------------------------------------------------------------------------


@frappe.whitelist()
@require_roles("Front Desk", "Hotel Admin", "Kamra Agent")
def agent_timeline(
	property: str | None = None,
	agent: str | None = None,
	channel: str | None = None,
	approval_status: str | None = None,
	days: int = 7,
	limit: int = 200,
) -> list[dict]:
	filters: dict = {}
	if property:
		filters["property"] = property
	if agent:
		filters["agent_name"] = agent
	if channel:
		filters["action_channel"] = channel
	if approval_status:
		filters["approval_status"] = approval_status
	if days:
		filters["creation"] = [">=", frappe.utils.add_days(frappe.utils.nowdate(), -int(days))]

	rows = frappe.get_all(
		"Agent Action Log",
		filters=filters,
		fields=[
			"name",
			"agent_name",
			"action_type",
			"autonomy",
			"approval_status",
			"action_channel",
			"reference_doctype",
			"reference_name",
			"property",
			"minutes_saved",
			"rationale",
			"approver",
			"executed_at",
			"creation",
		],
		order_by="creation desc",
		limit=int(limit),
	)
	return rows


@frappe.whitelist()
@require_roles("Front Desk", "Hotel Admin", "Kamra Agent")
def agents_savings_summary(property: str | None = None, days: int = 7) -> dict:
	"""Roll-up for the 'hours saved this week' card. Minutes across agents,
	broken down by channel - humans still get counted since human actions
	log too, but the interesting story is the agent split."""
	filters = "1=1"
	values: dict = {}
	if property:
		filters += " AND property = %(property)s"
		values["property"] = property
	filters += " AND creation >= DATE_SUB(NOW(), INTERVAL %(days)s DAY)"
	values["days"] = int(days)

	rows = frappe.db.sql(
		f"""
		SELECT COALESCE(action_channel, 'Unknown') AS channel,
		       COUNT(*) AS actions,
		       COALESCE(SUM(minutes_saved), 0) AS minutes
		FROM `tabAgent Action Log`
		WHERE {filters}
		GROUP BY channel
		ORDER BY minutes DESC
		""",
		values,
		as_dict=True,
	)
	total_minutes = sum(float(r["minutes"] or 0) for r in rows)
	return {
		"days": int(days),
		"channels": rows,
		"total_minutes": total_minutes,
		"total_hours": round(total_minutes / 60.0, 1),
	}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_json(raw):
	if not raw:
		return None
	if isinstance(raw, (dict, list)):
		return raw
	try:
		return json.loads(raw)
	except (ValueError, TypeError):
		return {"_raw": str(raw)[:2000]}


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Revenue Manager", "Kamra Agent")
def activity_feed(property: str | None = None, actor_kind: str | None = None,
                  action_type: str | None = None, limit: int = 50,
                  start: int = 0) -> list[dict]:
	"""The one ledger: every action anyone took - human or agent - newest
	first. actor_kind filters to "human" or "agent"."""
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
