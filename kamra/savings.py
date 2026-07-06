"""The savings ledger — Kamra's core product primitive.

Every meaningful action (human or agent) can be recorded as an
Agent Action Log row. Automated actions carry an estimate of the staff
minutes they avoided; the dashboard aggregates these into the
hours-saved counter that anchors Kamra's value story.

As of v23 (autonomy gate), each row also carries an approval_status
(Executed / Suggested / Pending / Approved / Rejected) and optional
before/after JSON snapshots so the Agents Inbox can render a diff and
the timeline can support undo.
"""

import json

import frappe


def log_action(
	action_type: str,
	reference_doctype: str | None = None,
	reference_name: str | None = None,
	property: str | None = None,
	minutes_saved: float = 0,
	rationale: str = "",
	agent_name: str | None = None,
	autonomy: str = "Full",
	channel: str = "Desk",
	approval_status: str = "Executed",
	approver: str | None = None,
	before_snapshot: dict | list | str | None = None,
	after_snapshot: dict | list | str | None = None,
	executed_at=None,
) -> str | None:
	"""Write one row to the savings ledger. Never raises — logging must
	not break the business action it describes. Returns the log row name,
	or None if the write failed.

	Snapshots may be passed as dicts/lists (they're JSON-serialised here)
	or as pre-serialised strings. executed_at defaults to now() for
	terminal statuses (Executed / Approved / Rejected); it stays null for
	Suggested and Pending — the moment the action ran, not when it was
	proposed.
	"""
	try:
		if executed_at is None and approval_status in ("Executed", "Approved", "Rejected"):
			executed_at = frappe.utils.now_datetime()
		doc = frappe.get_doc(
			{
				"doctype": "Agent Action Log",
				"agent_name": agent_name or frappe.session.user,
				"action_type": action_type,
				"autonomy": autonomy,
				"approval_status": approval_status,
				"action_channel": channel,
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
				"property": property,
				"minutes_saved": minutes_saved,
				"rationale": rationale,
				"approver": approver,
				"before_snapshot": _serialise_snapshot(before_snapshot),
				"after_snapshot": _serialise_snapshot(after_snapshot),
				"executed_at": executed_at,
			}
		).insert(ignore_permissions=True)
		return doc.name
	except Exception:
		frappe.log_error(title="Agent Action Log write failed")
		return None


def mark_approved(log_name: str, approver: str) -> None:
	"""Flip a Pending row to Approved and stamp executed_at. The gate
	calls this immediately before it actually runs the deferred action."""
	try:
		frappe.db.set_value(
			"Agent Action Log",
			log_name,
			{
				"approval_status": "Approved",
				"approver": approver,
				"executed_at": frappe.utils.now_datetime(),
			},
		)
	except Exception:
		frappe.log_error(title="Agent Action Log approve failed")


def mark_rejected(log_name: str, approver: str, reason: str = "") -> None:
	"""Flip a Pending row to Rejected. No side effects — the deferred
	action never runs. If a reason is given it's appended to rationale."""
	try:
		updates = {
			"approval_status": "Rejected",
			"approver": approver,
			"executed_at": frappe.utils.now_datetime(),
		}
		if reason:
			existing = frappe.db.get_value("Agent Action Log", log_name, "rationale") or ""
			updates["rationale"] = (existing + "\n\nRejected: " + reason).strip()
		frappe.db.set_value("Agent Action Log", log_name, updates)
	except Exception:
		frappe.log_error(title="Agent Action Log reject failed")


def _serialise_snapshot(value) -> str | None:
	"""Coerce a snapshot to a JSON string. Accepts dict / list / str / None."""
	if value is None:
		return None
	if isinstance(value, str):
		return value
	try:
		return json.dumps(value, default=str, sort_keys=True)
	except Exception:
		return json.dumps({"_serialise_error": True, "repr": repr(value)[:1000]})
