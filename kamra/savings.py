"""The savings ledger — Kamra's core product primitive.

Every meaningful action (human or agent) can be recorded as an
Agent Action Log row. Automated actions carry an estimate of the staff
minutes they avoided; the dashboard aggregates these into the
hours-saved counter that anchors Kamra's value story.
"""

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
):
	"""Write one row to the savings ledger. Never raises — logging must
	not break the business action it describes."""
	try:
		frappe.get_doc(
			{
				"doctype": "Agent Action Log",
				"agent_name": agent_name or frappe.session.user,
				"action_type": action_type,
				"autonomy": autonomy,
				"action_channel": channel,
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
				"property": property,
				"minutes_saved": minutes_saved,
				"rationale": rationale,
			}
		).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(title="Agent Action Log write failed")
