"""Kamra Agent and MCP offer each user the reports their roles can open - the
same gates as the report screens, never more."""

from __future__ import annotations

import frappe

from kamra import assistant, mcp_tools
from kamra.custom_reports import list_report_datasets, list_report_packs, run_report_pack
from kamra.tests.audit_fixtures import PROP_A, AuditTestCase, ensure_user, make_property

REPORT_TOOLS = {
	"manager_flash", "cashier_shift_report", "voids_allowances_report",
	"sla_report", "outlets", "outlet_dashboard", "wastage_report",
	"banquet_register", "list_report_datasets", "run_custom_report",
	"list_report_packs", "run_report_pack",
}
BUILDER = {"list_report_datasets", "run_custom_report", "list_report_packs",
           "run_report_pack"}
FRONT_DESK = {"arrivals", "departures", "in_house", "no_shows_cancels",
              "occupancy_by_day"}
HK = {"hk_tasks", "room_status", "lost_found"}

# role -> (report tools, custom-report datasets, packs) it must get, exactly
EXPECTED = {
	"Front Desk": (
		{"manager_flash", "cashier_shift_report", "sla_report", "outlets",
		 "outlet_dashboard", "wastage_report", "banquet_register", *BUILDER},
		FRONT_DESK | HK | {"pos_orders"},
		{"front_office", "housekeeping", "fnb", "hotel_manager"}),
	"Night Auditor": (
		{"manager_flash", "cashier_shift_report", *BUILDER},
		FRONT_DESK | {"folio_charges", "payments"},
		{"front_office", "hotel_manager"}),
	"Finance": (
		{"manager_flash", "cashier_shift_report", "voids_allowances_report",
		 "outlets", "outlet_dashboard", "wastage_report", "banquet_register",
		 *BUILDER},
		FRONT_DESK | {"folio_charges", "payments", "voids", "contribution",
		              "pos_orders"},
		{"front_office", "fnb", "hotel_manager"}),
	"Housekeeping": (BUILDER, HK, {"housekeeping"}),
}


class AgentReportAccessTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		make_property(PROP_A)

	def test_each_role_gets_exactly_its_reports(self):
		for role, (tools, datasets, packs) in EXPECTED.items():
			email = f"ut.reports.{role.lower().replace(' ', '')}@test.local"
			ensure_user(email, [role])
			frappe.set_user(email)  # nosemgrep: frappe-setuser -- acting as the persona
			try:
				offered = {d["function"]["name"] for d in assistant._tool_defs()}
				self.assertEqual(offered & REPORT_TOOLS, tools, role)
				mcp = {s.name for s in mcp_tools.allowed_tools(property=PROP_A)}
				self.assertEqual(mcp & REPORT_TOOLS, tools, f"MCP {role}")
				self.assertEqual({d["id"] for d in list_report_datasets(PROP_A)},
				                 datasets, role)
				self.assertEqual({p["id"][len("pack:"):] for p in list_report_packs(PROP_A)},
				                 packs, role)
			finally:
				frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- restore

	def test_a_pack_holds_only_the_sections_the_role_may_run(self):
		email = "ut.reports.nightauditor@test.local"
		ensure_user(email, ["Night Auditor"])
		frappe.set_user(email)  # nosemgrep: frappe-setuser -- acting as the persona
		try:
			pack = run_report_pack(PROP_A, "hotel_manager")
			self.assertEqual([s["dataset"] for s in pack["sections"]],
			                 ["occupancy_by_day", "payments", "folio_charges"])
			html = run_report_pack(PROP_A, "hotel_manager", format="html")["content"]
			self.assertIn("Collections by mode", html)
			self.assertNotIn("Voids and allowances", html)
			with self.assertRaises(frappe.PermissionError):
				run_report_pack(PROP_A, "housekeeping")
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- restore

	def test_housekeeping_pack_runs_every_section(self):
		email = "ut.reports.housekeeping@test.local"
		ensure_user(email, ["Housekeeping"])
		frappe.set_user(email)  # nosemgrep: frappe-setuser -- acting as the persona
		try:
			pack = run_report_pack(PROP_A, "housekeeping")
			self.assertEqual([s["dataset"] for s in pack["sections"]],
			                 ["room_status", "hk_tasks", "hk_tasks", "lost_found"])
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- restore

	def test_grouped_clean_minutes_are_averaged_over_timed_cleans(self):
		from kamra.custom_reports import _apply_group

		rows = [{"t": "A", "tasks": 1, "m": 20.0}, {"t": "A", "tasks": 1, "m": 40.0},
		        {"t": "A", "tasks": 1, "m": None}]
		self.assertEqual(_apply_group(rows, ["t"], ["t", "tasks", "m"], ("m",)),
		                 [{"t": "A", "tasks": 3.0, "m": 30.0}])
