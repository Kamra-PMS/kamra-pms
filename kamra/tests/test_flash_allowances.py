"""An allowance is a credit to the guest, not a revenue stream.

reports._day_stats (the manager flash, MTD, the portfolio row, the owner
view, the audit pack and the manager_flash MCP tool) must keep an
Allowance line out of "other revenue" and report it as its own figure, so
total revenue stays net of it.
"""

from __future__ import annotations

from unittest.mock import patch

from kamra import folio as folio_mod
from kamra.reports import _day_stats, manager_flash
from kamra.tests.audit_fixtures import (
	PROP_A,
	TODAY,
	AuditTestCase,
	d,
	guest_folio,
	make_property,
	make_reservation,
	make_room,
	make_room_type,
)


class FlashAllowancesTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=100000)
		self.room = make_room(PROP_A, self.rt, "101")
		self.res = make_reservation(PROP_A, self.rt, TODAY, d(2),
		                            status="Checked In", room=self.room)
		folio_mod.post_room_night(self.res, TODAY)
		self.room_revenue = _day_stats(PROP_A, TODAY, 1)["room_revenue"]
		self.assertGreater(self.room_revenue, 0)
		# post_allowance dates the line with frappe.utils.nowdate()
		with patch("frappe.utils.nowdate", return_value=TODAY):
			folio_mod.post_allowance(guest_folio(self.res.name), 20000, "UT goodwill")

	def test_allowance_is_not_other_revenue(self):
		day = _day_stats(PROP_A, TODAY, 1)
		self.assertEqual(day["room_revenue"], self.room_revenue)
		self.assertEqual(day["other_revenue"], 0)
		self.assertEqual(day.get("allowances"), -20000)
		# total revenue stays net of the allowance
		self.assertEqual(day["total_revenue"], self.room_revenue - 20000)

	def test_flash_and_month_to_date_carry_allowances(self):
		flash = manager_flash(PROP_A, TODAY)
		for span in (flash["today"], flash["mtd"]):
			self.assertEqual(span["other_revenue"], 0)
			self.assertEqual(span.get("allowances"), -20000)
			self.assertEqual(span["total_revenue"], self.room_revenue - 20000)

	def test_dashboard_revenue_today_stays_net(self):
		from kamra.dashboards import _property_summary, property_dashboard
		dash = property_dashboard(PROP_A, TODAY)
		# the split, not just the net: room revenue stays gross and the
		# allowance is its own figure, so revenue = room + allowances here
		self.assertEqual(dash["room_revenue_today"], self.room_revenue)
		self.assertEqual(dash.get("allowances_today"), -20000)
		self.assertEqual(dash["revenue_today"],
		                 dash["room_revenue_today"] + dash["allowances_today"])
		self.assertEqual(dash["revenue_today"], self.room_revenue - 20000)
		self.assertEqual(dash["statistics"]["mtd_revenue"], self.room_revenue - 20000)
		self.assertEqual(_property_summary(PROP_A, TODAY)["revenue_today"],
		                 self.room_revenue - 20000)
