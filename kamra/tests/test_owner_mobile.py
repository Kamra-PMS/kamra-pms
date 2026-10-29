"""The owner's phone view (kamra.dashboards.owner_snapshot): the hotel's
figures for Finance, Revenue, the night auditor and managers, never the
front desk, and only for the properties the user may see."""

from __future__ import annotations

import frappe

from kamra import dashboards
from kamra.tests.audit_fixtures import (
	PROP_A,
	PROP_B,
	TODAY,
	AuditTestCase,
	ensure_user,
	make_property,
	make_room,
	make_room_type,
)

DESK = "ut-owner-desk@kamra.local"
FIN = "ut-owner-fin@kamra.local"
REV = "ut-owner-rev@kamra.local"
SCOPED = "ut-owner-scoped@kamra.local"


class OwnerSnapshotTestCase(AuditTestCase):

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.business_date", "kamra.dashboards")
		for p in (PROP_A, PROP_B):
			make_property(p, business_date=TODAY)
		make_room(PROP_A, make_room_type(PROP_A, "STD", base_price=1000), "101")
		ensure_user(DESK, ["Front Desk"])
		ensure_user(FIN, ["Finance"])
		ensure_user(REV, ["Revenue Manager"])
		ensure_user(SCOPED, ["Finance"])
		frappe.get_doc({"doctype": "User Permission", "user": SCOPED,
		                "allow": "Property", "for_value": PROP_A}).insert(ignore_permissions=True)

	def as_user(self, user):
		frappe.set_user(user)  # nosemgrep: frappe-setuser -- the role under test

	def test_finance_gets_figures_and_audits(self):
		self.as_user(FIN)
		out = dashboards.owner_snapshot(PROP_A, TODAY)
		for key in ("today", "mtd", "movement", "collections", "outlook",
		            "guest_balances", "city_ledger", "city_ledger_overdue"):
			self.assertIn(key, out)
		self.assertEqual(out["total_rooms"], 1)
		self.assertEqual(len(out["outlook"]), 7)
		self.assertIsInstance(out["audits"], list)

	def test_month_to_date_range(self):
		self.as_user(FIN)
		start = TODAY[:8] + "01"
		out = dashboards.owner_snapshot(PROP_A, TODAY, start)
		self.assertEqual(out["from_date"], start)
		self.assertEqual(out["today"]["rooms_sold"], out["mtd"]["rooms_sold"])

	def test_revenue_manager_sees_figures_not_audit_packs(self):
		# the flash's collections and the ledger aging have their own, older
		# gates without Revenue Manager; the owner view must still answer
		self.as_user(REV)
		out = dashboards.owner_snapshot(PROP_A, TODAY)
		self.assertIn("collections", out)
		self.assertIsNone(out["audits"])

	def test_front_desk_is_refused(self):
		self.as_user(DESK)
		with self.assertRaises(frappe.PermissionError):
			dashboards.owner_snapshot(PROP_A, TODAY)

	def test_other_property_is_refused(self):
		self.as_user(SCOPED)
		dashboards.owner_snapshot(PROP_A, TODAY)
		with self.assertRaises(frappe.PermissionError):
			dashboards.owner_snapshot(PROP_B, TODAY)
