"""Kamra Agent offers each user the reports their roles can open - the same
gates as the report screens, never more."""

from __future__ import annotations

import frappe

from kamra import assistant
from kamra.custom_reports import list_report_datasets
from kamra.tests.audit_fixtures import PROP_A, AuditTestCase, ensure_user, make_property

REPORT_TOOLS = {
	"manager_flash", "cashier_shift_report", "voids_allowances_report",
	"sla_report", "outlets", "outlet_dashboard", "wastage_report",
	"banquet_register", "list_report_datasets", "run_custom_report",
}

# role -> (agent report tools, custom-report datasets) it must get, exactly
EXPECTED = {
	"Front Desk": (
		{"manager_flash", "cashier_shift_report", "sla_report", "outlets",
		 "outlet_dashboard", "wastage_report", "banquet_register",
		 "list_report_datasets", "run_custom_report"},
		{"arrivals", "departures", "in_house", "no_shows_cancels",
		 "occupancy_by_day", "hk_tasks", "pos_orders"}),
	"Night Auditor": (
		{"manager_flash", "cashier_shift_report", "list_report_datasets",
		 "run_custom_report"},
		{"arrivals", "departures", "in_house", "no_shows_cancels",
		 "occupancy_by_day", "folio_charges", "payments"}),
	"Finance": (
		{"manager_flash", "cashier_shift_report", "voids_allowances_report",
		 "outlets", "outlet_dashboard", "wastage_report", "banquet_register",
		 "list_report_datasets", "run_custom_report"},
		{"arrivals", "departures", "in_house", "no_shows_cancels",
		 "occupancy_by_day", "folio_charges", "payments", "voids",
		 "contribution", "pos_orders"}),
	"Housekeeping": (
		{"list_report_datasets", "run_custom_report"},
		{"hk_tasks"}),
}


class AgentReportAccessTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		make_property(PROP_A)

	def test_each_role_gets_exactly_its_reports(self):
		for role, (tools, datasets) in EXPECTED.items():
			email = f"ut.reports.{role.lower().replace(' ', '')}@test.local"
			ensure_user(email, [role])
			frappe.set_user(email)  # nosemgrep: frappe-setuser -- acting as the persona
			try:
				offered = {d["function"]["name"] for d in assistant._tool_defs()}
				self.assertEqual(offered & REPORT_TOOLS, tools, role)
				self.assertEqual({d["id"] for d in list_report_datasets(PROP_A)},
				                 datasets, role)
			finally:
				frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- restore
