"""The Autonomy Gate - Kamra's per-action approval router.

Every mutating tool call routes through here to decide one of:

    Execute      → run now, log Executed. Fast path, most calls.
    Suggest      → do NOT run; log Suggested, return the draft only.
                   Used by "read-only proposals" (Revenue Bot showing
                   rate ideas that a human then hand-approves).
    Approve      → do NOT run; write a Pending Agent Action row, log
                   Pending, notify approver. The action replays exactly
                   when the human taps Approve.

The gate reads per-Agent autonomy_rules, so the decision is configuration,
not code. An unregistered caller (no matching Agent row) defaults to Full -
that preserves today's behaviour for existing endpoints during rollout.

Bypass:
    Set `frappe.flags.kamra_gate_bypass = True` to skip the gate for
    one call. The approve() replayer uses this - a Pending row that just
    got approved should NOT re-enter the gate and get parked again.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import frappe

from kamra import savings


# ---------------------------------------------------------------------------
# Decision types
# ---------------------------------------------------------------------------


@dataclass
class GateExecute:
	"""Proceed. Log row is Executed. Caller runs the action and may call
	finalize_after() to attach an after-snapshot."""

	log_name: str | None
	autonomy: str = "Full"

	kind: str = "execute"


@dataclass
class GateSuggest:
	"""Do NOT run. Return the draft to the user. Log row is Suggested."""

	log_name: str | None
	summary: str
	kind: str = "suggest"


@dataclass
class GatePending:
	"""Do NOT run. The action is parked in Pending Agent Action; the
	human approves in the Agents Inbox and it replays under their identity."""

	log_name: str | None
	pending_name: str
	summary: str
	kind: str = "pending"


GateDecision = GateExecute | GateSuggest | GatePending


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


def guard(
	action_type: str,
	*,
	endpoint: str,
	payload: dict[str, Any] | None = None,
	summary: str = "",
	agent_name: str | None = None,
	channel: str | None = None,
	reference_doctype: str | None = None,
	reference_name: str | None = None,
	property: str | None = None,
	before_snapshot: dict | list | str | None = None,
	minutes_saved: float = 0,
	rationale: str = "",
) -> GateDecision:
	"""The single entry point every mutating tool call flows through.

	Callers pattern:
	    decision = guard("cancel_reservation", endpoint="kamra.api.cancel_reservation",
	                     payload=locals_snapshot, summary="Cancel RES-… waive fee",
	                     reference_doctype="Reservation", reference_name=reservation,
	                     agent_name=agent, channel=_infer_channel())
	    if isinstance(decision, GateExecute):
	        # run the actual mutation
	        result = _do_the_thing()
	        finalize_after(decision.log_name, after_snapshot=_snapshot(...))
	        return result
	    if isinstance(decision, GateSuggest):
	        return {"gate": "suggest", "summary": decision.summary, "log": decision.log_name}
	    # GatePending
	    return {"gate": "pending", "pending": decision.pending_name, "log": decision.log_name,
	            "summary": decision.summary}
	"""
	payload = payload or {}

	# Bypass: replaying an approved Pending action skips the gate.
	if frappe.flags.get("kamra_gate_bypass"):
		log_name = savings.log_action(
			action_type=action_type,
			reference_doctype=reference_doctype,
			reference_name=reference_name,
			property=property,
			minutes_saved=minutes_saved,
			rationale=rationale or "Gate bypassed (approved replay).",
			agent_name=agent_name,
			autonomy="Approved",
			channel=channel or "Desk",
			approval_status="Approved",
			approver=frappe.session.user,
			before_snapshot=before_snapshot,
		)
		return GateExecute(log_name=log_name, autonomy="Approved")

	agent = _resolve_agent(agent_name, property)
	autonomy = agent.resolve_autonomy(action_type, payload) if agent else "Full"

	if autonomy == "Full":
		log_name = savings.log_action(
			action_type=action_type,
			reference_doctype=reference_doctype,
			reference_name=reference_name,
			property=property,
			minutes_saved=minutes_saved,
			rationale=rationale,
			agent_name=agent_name,
			autonomy="Full",
			channel=channel or _infer_channel(agent),
			approval_status="Executed",
			before_snapshot=before_snapshot,
		)
		return GateExecute(log_name=log_name, autonomy="Full")

	if autonomy == "Suggest":
		log_name = savings.log_action(
			action_type=action_type,
			reference_doctype=reference_doctype,
			reference_name=reference_name,
			property=property,
			minutes_saved=0,  # nothing happened, no time saved yet
			rationale=rationale or "Suggested by agent - awaiting human application.",
			agent_name=agent_name,
			autonomy="Suggest",
			channel=channel or _infer_channel(agent),
			approval_status="Suggested",
			before_snapshot=before_snapshot,
		)
		return GateSuggest(log_name=log_name, summary=summary or action_type)

	# Approve - park in Pending Agent Action + log Pending.
	approver = (agent.default_approver if agent else None) or _fallback_approver(property)
	pending = frappe.get_doc(
		{
			"doctype": "Pending Agent Action",
			"agent": agent.name if agent else None,
			"action_type": action_type,
			"summary": summary or action_type,
			"action_endpoint": endpoint,
			"payload": json.dumps(payload or {}, default=str, sort_keys=True),
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
			"property": property,
			"requested_by": agent_name or frappe.session.user,
			"status": "Pending",
		}
	).insert(ignore_permissions=True)

	log_name = savings.log_action(
		action_type=action_type,
		reference_doctype=reference_doctype,
		reference_name=reference_name,
		property=property,
		minutes_saved=0,
		rationale=rationale or "Awaiting human approval.",
		agent_name=agent_name,
		autonomy="Approved",
		channel=channel or _infer_channel(agent),
		approval_status="Pending",
		before_snapshot=before_snapshot,
	)

	# Back-link the log onto the pending row (idempotent even if log write failed).
	if log_name:
		frappe.db.set_value("Pending Agent Action", pending.name, "action_log", log_name)

	_notify_approver(approver, pending.name, summary or action_type)

	return GatePending(log_name=log_name, pending_name=pending.name, summary=summary or action_type)


def finalize_after(log_name: str | None, after_snapshot: dict | list | str | None) -> None:
	"""Attach an after-snapshot to a log row that just Executed.

	Callers pass the just-mutated doc's dict; the gate serialises + stores.
	No-ops if the log write earlier failed (log_name is None).
	"""
	if not log_name or after_snapshot is None:
		return
	try:
		frappe.db.set_value(
			"Agent Action Log",
			log_name,
			"after_snapshot",
			savings._serialise_snapshot(after_snapshot),
		)
	except Exception:
		frappe.log_error(title="Agent Action Log after_snapshot write failed")


# ---------------------------------------------------------------------------
# Approve / Reject
# ---------------------------------------------------------------------------


def approve_pending(pending_name: str, approver: str | None = None, note: str = "") -> dict:
	"""Replay the deferred call with gate bypass, mark everything Approved.

	Returns {'pending': name, 'log': log_name, 'result': <endpoint return>}.
	Raises if the pending row is not currently Pending, or if the endpoint
	can't be imported. On endpoint failure, the pending row stays Pending
	so the human can retry.
	"""
	approver = approver or frappe.session.user
	p = frappe.get_doc("Pending Agent Action", pending_name)
	_guard_pending_state(p)

	method: Callable = _resolve_endpoint(p.action_endpoint)
	payload = json.loads(p.payload or "{}") if p.payload else {}

	frappe.flags.kamra_gate_bypass = True
	try:
		result = method(**payload)
	finally:
		frappe.flags.kamra_gate_bypass = False

	# Flip everything to Approved after a successful replay.
	if p.action_log:
		savings.mark_approved(p.action_log, approver)
	frappe.db.set_value(
		"Pending Agent Action",
		p.name,
		{
			"status": "Approved",
			"approver": approver,
			"decision_note": note or None,
			"resolved_at": frappe.utils.now_datetime(),
		},
	)
	return {"pending": p.name, "log": p.action_log, "result": result}


def reject_pending(pending_name: str, approver: str | None = None, reason: str = "") -> dict:
	"""No replay, just flip to Rejected. The action never fires."""
	approver = approver or frappe.session.user
	p = frappe.get_doc("Pending Agent Action", pending_name)
	_guard_pending_state(p)

	if p.action_log:
		savings.mark_rejected(p.action_log, approver, reason)
	frappe.db.set_value(
		"Pending Agent Action",
		p.name,
		{
			"status": "Rejected",
			"approver": approver,
			"decision_note": reason or None,
			"resolved_at": frappe.utils.now_datetime(),
		},
	)
	return {"pending": p.name, "log": p.action_log, "status": "Rejected"}


def expire_stale_pending() -> int:
	"""Scheduler hook - flip anything past expires_at from Pending to Expired."""
	now = frappe.utils.now_datetime()
	stale = frappe.get_all(
		"Pending Agent Action",
		filters={"status": "Pending", "expires_at": ["<", now]},
		pluck="name",
	)
	for name in stale:
		p = frappe.get_doc("Pending Agent Action", name)
		if p.action_log:
			savings.mark_rejected(p.action_log, "Administrator", "Expired (TTL).")
		frappe.db.set_value(
			"Pending Agent Action",
			name,
			{"status": "Expired", "resolved_at": now},
		)
	if stale:
		frappe.db.commit()
	return len(stale)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _resolve_agent(agent_name: str | None, property: str | None):
	"""Look up the Agent row by (property, name-or-persona).

	Precedence:
	    1. Exact (property, agent_name) match.
	    2. Property-scoped active row with matching persona.
	    3. Chain-global (blank property) row with matching persona.
	None if no row is found - caller treats as Full autonomy.
	"""
	if not agent_name:
		return None
	filters_exact: dict[str, Any] = {"agent_name": agent_name, "active": 1}
	if property:
		filters_exact["property"] = property
	rows = frappe.get_all("Agent", filters=filters_exact, limit=1, pluck="name")
	if not rows and property:
		# Retry as a persona hint scoped to property.
		rows = frappe.get_all(
			"Agent",
			filters={"persona": agent_name, "property": property, "active": 1},
			limit=1,
			pluck="name",
		)
	if not rows:
		# Chain-global fallback.
		rows = frappe.get_all(
			"Agent",
			filters={"persona": agent_name, "property": "", "active": 1},
			limit=1,
			pluck="name",
		)
	if not rows:
		return None
	try:
		return frappe.get_doc("Agent", rows[0])
	except Exception:
		return None


def _infer_channel(agent) -> str:
	if agent and (agent.channel or "").strip():
		return agent.channel
	return "Desk"


def _fallback_approver(property: str | None) -> str | None:
	"""Property's Hotel Admin if we can find one, else Administrator."""
	if property:
		try:
			admin = frappe.get_all(
				"Has Role",
				filters={"role": "Hotel Admin", "parenttype": "User"},
				pluck="parent",
				limit=1,
			)
			if admin:
				return admin[0]
		except Exception:
			pass
	return "Administrator"


def _notify_approver(approver: str | None, pending_name: str, summary: str) -> None:
	if not approver:
		return
	try:
		frappe.publish_realtime(
			event="kamra_agent_pending",
			message={"pending": pending_name, "summary": summary},
			user=approver,
		)
	except Exception:
		frappe.log_error(title="Kamra gate notify failed")


def _guard_pending_state(pending) -> None:
	if pending.status != "Pending":
		frappe.throw(
			f"Pending Agent Action {pending.name} is already {pending.status.lower()}."
		)
	if pending.expires_at and frappe.utils.get_datetime(pending.expires_at) < frappe.utils.now_datetime():
		frappe.throw(f"Pending Agent Action {pending.name} has expired.")


def _resolve_endpoint(endpoint: str) -> Callable:
	"""Import the method by dotted path. Whitelisted at Frappe layer already -
	we're just calling the Python function directly."""
	if not endpoint:
		frappe.throw("Missing action_endpoint on Pending Agent Action.")
	try:
		return frappe.get_attr(endpoint)
	except (ImportError, AttributeError) as exc:
		frappe.throw(f"Cannot resolve endpoint '{endpoint}': {exc}")
