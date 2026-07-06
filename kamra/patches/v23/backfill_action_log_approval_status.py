"""Backfill approval_status on pre-v23 Agent Action Log rows.

Before the autonomy gate landed, every logged action was a fait accompli —
the row was written after the tool ran. In the new model, approval_status
distinguishes: Executed (ran under Full autonomy), Suggested (draft only),
Pending / Approved / Rejected (gated actions). All historical rows are
retroactively 'Executed' — that's what the old log_action() actually recorded.

executed_at is backfilled from `creation` since the two were the same event
before the gate existed.
"""

import frappe


def execute():
	frappe.db.sql(
		"""
		UPDATE `tabAgent Action Log`
		SET approval_status = 'Executed',
		    executed_at = creation
		WHERE approval_status IS NULL OR approval_status = ''
		"""
	)
	frappe.db.commit()
