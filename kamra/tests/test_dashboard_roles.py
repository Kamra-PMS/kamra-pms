"""The dashboard keeps the hotel's numbers from the front desk.

A receptionist sees arrivals, departures, in house and rooms; revenue,
ADR, RevPAR, collections, outstanding and occupancy are for Finance,
Revenue, the night auditor and managers. The server leaves them out, so
the numbers are not just hidden on screen.
"""

from __future__ import annotations

import frappe

from kamra import dashboards, reports
from kamra.tests.audit_fixtures import (
	PROP_A,
	TODAY,
	AuditTestCase,
	ensure_user,
	make_property,
	make_room,
	make_room_type,
)

DESK = "ut-desk-figures@kamra.local"
FIN = "ut-fin-figures@kamra.local"


class DashboardRolesTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.business_date")
		make_property(PROP_A, business_date=TODAY)
		make_room(PROP_A, make_room_type(PROP_A, "STD", base_price=1000), "101")
		ensure_user(DESK, ["Front Desk"])
		ensure_user(FIN, ["Finance"])

	def tearDown(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- restore
		super().tearDown()

	def test_front_desk_gets_movement_but_no_figures(self):
		frappe.set_user(DESK)  # nosemgrep: frappe-setuser -- the receptionist
		out = dashboards.property_dashboard(PROP_A, TODAY)
		self.assertTrue(out["figures_hidden"])
		for key in dashboards.FIGURE_KEYS:
			self.assertNotIn(key, out)
		self.assertIn("arrivals", out)
		self.assertIn("in_house", out["front_desk"])
		self.assertIn("room_status", out["housekeeping"])
		with self.assertRaises(frappe.PermissionError):
			reports.manager_flash(PROP_A, TODAY)

	def test_finance_gets_the_figures(self):
		frappe.set_user(FIN)  # nosemgrep: frappe-setuser -- finance
		out = dashboards.property_dashboard(PROP_A, TODAY)
		self.assertNotIn("figures_hidden", out)
		for key in ("revenue_today", "adr", "revpar", "occupancy_pct", "finance", "statistics"):
			self.assertIn(key, out)
