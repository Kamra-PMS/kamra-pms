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
import traceback

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
	not break the business action it describes — but never fails silently
	either: an unknown channel is mapped to an allowed one, and a row that
	still fails is reported (server log + Error Log) and retried once with
	the minimal fields. Returns the log row name, or None if both failed.

	Snapshots may be passed as dicts/lists (they're JSON-serialised here)
	or as pre-serialised strings. executed_at defaults to now() for
	terminal statuses (Executed / Approved / Rejected); it stays null for
	Suggested and Pending — the moment the action ran, not when it was
	proposed.
	"""
	if executed_at is None and approval_status in ("Executed", "Approved", "Rejected"):
		executed_at = frappe.utils.now_datetime()
	channel, note = _normalise_channel(channel)
	row = {
		"doctype": "Agent Action Log",
		"actor": getattr(frappe.session, "user", None),
		# humans are the actor, not an "agent" — agent_name stays null
		"agent_name": agent_name,
		"action_type": action_type,
		"autonomy": autonomy,
		"approval_status": approval_status,
		"action_channel": channel,
		"reference_doctype": reference_doctype,
		"reference_name": reference_name,
		"property": property,
		"minutes_saved": minutes_saved,
		"rationale": str(rationale or "") + note,
		"approver": approver,
		"before_snapshot": _serialise_snapshot(before_snapshot),
		"after_snapshot": _serialise_snapshot(after_snapshot),
		"executed_at": executed_at,
	}
	try:
		return _insert(row)
	except Exception as exc:
		first = exc
	# The row didn't validate. Losing it silently is how agent actions went
	# missing from the activity log, so: record why, loudly, and retry once
	# with only the fields that can't fail validation.
	_report_failure(action_type, row, first)
	fallback = {k: row[k] for k in (
		"doctype", "actor", "action_type", "approval_status", "action_channel",
		"property", "minutes_saved", "executed_at")}
	fallback["agent_name"] = agent_name
	fallback["rationale"] = (
		f"{row['rationale']}\n\n[log fallback: full row failed — "
		f"{type(first).__name__}: {first}; channel={channel}, "
		f"ref={reference_doctype} {reference_name}]"
	).strip()[:5000]
	try:
		return _insert(fallback)
	except Exception as exc:
		_report_failure(action_type, fallback, exc, fallback=True)
		return None


# The Select only takes Desk / Voice / WhatsApp / API / Chat / MCP. The one
# off-list name a caller passes today is a channel provider's "SMS"; any
# other unknown name also lands on API rather than failing the row.
_CHANNEL_ALIASES = {"sms": "API"}


def _normalise_channel(channel: str | None) -> tuple[str | None, str]:
	"""(allowed channel, rationale note). Unknown channels map to an alias or
	"API", and the original name is kept in the rationale."""
	if not channel:
		return None, ""
	field = frappe.get_meta("Agent Action Log").get_field("action_channel")
	allowed = [o for o in (field.options or "").split("\n") if o]
	if channel in allowed:
		return channel, ""
	by_lower = {o.lower(): o for o in allowed}
	mapped = by_lower.get(channel.lower()) or _CHANNEL_ALIASES.get(channel.lower())
	if mapped not in allowed:
		mapped = "API" if "API" in allowed else None
	return mapped, f" [channel: {channel}]"


def _insert(row: dict) -> str:
	"""Insert under a savepoint so a failed row never poisons the caller's
	transaction (the business action it describes must still commit)."""
	sp = "aal_" + frappe.generate_hash(length=8)
	frappe.db.savepoint(sp)
	try:
		name = frappe.get_doc(dict(row)).insert(ignore_permissions=True).name
	except Exception:
		frappe.db.rollback(save_point=sp)
		raise
	frappe.db.release_savepoint(sp)
	return name


def _report_failure(action_type, row, exc, *, fallback=False) -> None:
	"""Make a failed log write visible: server log + Error Log row. Never
	raises - the business action it describes must still succeed."""
	what = "fallback write" if fallback else "write"
	title = f"Agent Action Log {what} failed: {action_type}"[:140]
	detail = {k: v for k, v in row.items()
	          if k not in ("before_snapshot", "after_snapshot")}
	try:
		frappe.logger("kamra.savings").error(
			f"{title}: {type(exc).__name__}: {exc} | {detail}")
		frappe.log_error(
			title=title,
			message="".join(traceback.format_exception(exc))
			+ f"\n\nRow: {frappe.as_json(detail)}",
			reference_doctype=row.get("reference_doctype") or None,
			reference_name=row.get("reference_name") or None,
		)
	except Exception:
		pass  # logging the failure must never break the caller


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
