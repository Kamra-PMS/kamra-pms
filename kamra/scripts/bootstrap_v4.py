"""Schema v4: Rate Guardrail — the owner-set floor/ceiling that bounds
every rate move, human or agent (PRD FR-30).

Run via bench console:
    from kamra.scripts.bootstrap_v4 import execute; execute()
"""

import frappe

from kamra.scripts.bootstrap_schema import _dt, f
from kamra.scripts.fix_perms_fields import _grant


def execute():
	_dt("Rate Guardrail", [
		f("property", "Link", options="Property", reqd=1),
		f("room_type", "Link", options="Room Type",
		  description="Blank = applies to all room types of the property"),
		f("column_break_a", "Column Break"),
		f("floor_price", "Currency", reqd=1, in_list_view=1,
		  description="No rate may be set below this"),
		f("ceiling_price", "Currency", reqd=1, in_list_view=1,
		  description="No rate may be set above this"),
		f("disabled", "Check"),
	], naming_rule="Expression", autoname="format:GUARD-{####}")

	# custom perms replace built-ins — grant every relevant role explicitly
	for role, grants in {
		"System Manager": (1, 1, 1, 1),
		"Hotel Admin": (1, 1, 1, 1),
		"Revenue Manager": (1, 1, 1, 0),
		"Front Desk": (1, 0, 0, 0),
		"Kamra Agent": (1, 0, 0, 0),  # agents may READ guardrails, never edit
	}.items():
		r, w, c, d = grants
		_grant("Rate Guardrail", role, r, w, c, delete=d)
	print("Rate Guardrail perms granted")

	frappe.db.commit()
	print("Kamra v4 schema (rate guardrails) ready.")
