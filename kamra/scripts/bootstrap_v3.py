"""Schema v3: Service Ticket (guest requests with SLA) — PRD FR-42.

Run via bench console:
    from kamra.scripts.bootstrap_v3 import execute; execute()

Idempotent.
"""

import frappe

from kamra.scripts.bootstrap_schema import _dt, f

CATEGORIES = (
	"Housekeeping\nRoom Service\nMaintenance\nFront Desk\n"
	"Concierge\nComplaint\nOther"
)


def execute():
	_dt("Service Ticket", [
		f("property", "Link", options="Property", reqd=1),
		f("subject", "Data", reqd=1, in_list_view=1),
		f("category", "Select", options=CATEGORIES, reqd=1, in_list_view=1,
		  in_standard_filter=1),
		f("column_break_a", "Column Break"),
		f("priority", "Select", options="Low\nMedium\nHigh\nUrgent",
		  default="Medium", in_list_view=1),
		f("status", "Select", in_list_view=1, in_standard_filter=1,
		  options="Open\nIn Progress\nResolved\nClosed\nCancelled",
		  default="Open"),
		f("source", "Select",
		  options="Manual\nAI Agent\nVoice\nWhatsApp\nQR", default="Manual"),
		f("sb_where", "Section Break", label="Where / Who"),
		f("room", "Link", options="Room"),
		f("reservation", "Link", options="Reservation"),
		f("column_break_b", "Column Break"),
		f("guest", "Link", options="Guest"),
		f("guest_name", "Data", fetch_from="guest.full_name", read_only=1),
		f("assigned_to_user", "Link", options="User", label="Assigned To"),
		f("sb_detail", "Section Break", label="Detail"),
		f("description", "Small Text"),
		f("sb_sla", "Section Break", label="SLA"),
		f("due_by", "Datetime", read_only=1,
		  description="Set from priority at creation"),
		f("resolved_on", "Datetime", read_only=1),
		f("column_break_c", "Column Break"),
		f("breached", "Check", read_only=1, label="SLA Breached"),
		f("resolution_note", "Small Text"),
	], naming_rule="Expression", autoname="format:TKT-{#####}",
	   title_field="subject")

	# permissions: front desk staff work tickets
	for role in ("Front Desk",):
		if not frappe.db.exists(
			"Custom DocPerm", {"parent": "Service Ticket", "role": role}
		):
			frappe.get_doc({
				"doctype": "Custom DocPerm",
				"parent": "Service Ticket",
				"parenttype": "DocType",
				"parentfield": "permissions",
				"role": role,
				"read": 1, "write": 1, "create": 1, "report": 1,
			}).insert(ignore_permissions=True)
			print(f"granted {role} perms on Service Ticket")

	frappe.db.commit()
	print("Kamra v3 schema (service tickets) ready.")
