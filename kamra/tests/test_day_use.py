"""Hourly / block day-use pricing, due-out by time, and overstay rules (#497)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import frappe

from kamra import api, day_use, folio as folio_mod
from kamra.pricing import quote
from kamra.tests.audit_fixtures import (
	PROP_A,
	TODAY,
	AuditTestCase,
	guest_folio,
	make_property,
	make_reservation,
	make_room,
	make_room_type,
)
from kamra.tests.test_billing_approvals_split import set_setting


class DayUsePricingTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY)
		frappe.db.delete("Property Setting", {"property": PROP_A})
		set_setting(PROP_A, "day_use_overstay", "Next hour")
		self.rt = make_room_type(PROP_A, "STD", base_price=2400)
		self.room = make_room(PROP_A, self.rt, "201")
		frappe.db.delete("Rate Plan", {"property": PROP_A, "code": ("in", ["HRLY", "BLK"])})
		self.hourly = frappe.get_doc({
			"doctype": "Rate Plan", "property": PROP_A,
			"rate_plan_name": "Hourly Day Use", "code": "HRLY",
			"modifier_type": "Percent", "modifier_value": 0,
			"billing_basis": "Hourly", "hourly_rate": 200, "min_hours": 2,
		}).insert(ignore_permissions=True)
		self.block = frappe.get_doc({
			"doctype": "Rate Plan", "property": PROP_A,
			"rate_plan_name": "Block Day Use", "code": "BLK",
			"modifier_type": "Percent", "modifier_value": 0,
			"billing_basis": "Block", "hourly_rate": 200,
			"min_hours": 3, "block_hours": 3, "block_rate": 500,
		}).insert(ignore_permissions=True)

	def test_hourly_quote_uses_elapsed_hours_not_full_night(self):
		nightly = quote(PROP_A, self.rt, TODAY, TODAY, 2, 0)
		hourly = quote(PROP_A, self.rt, TODAY, TODAY, 2, 0,
		               rate_plan=self.hourly.name,
		               check_in_time="10:00", check_out_time="14:00")
		self.assertTrue(hourly["day_use"])
		self.assertEqual(hourly["day_use_billing"]["billing_basis"], "Hourly")
		self.assertEqual(hourly["day_use_billing"]["hours"], 4)
		# 4h × 200 = 800 vs one full night (~2400) — must be the hour total.
		self.assertAlmostEqual(hourly["room_total"], 800, places=0)
		self.assertLess(hourly["amount_after_tax"], nightly["amount_after_tax"])

	def test_block_quote_rounds_up_to_blocks(self):
		# 4 hours → 2 × 3h blocks at 500 = 1000
		q = quote(PROP_A, self.rt, TODAY, TODAY, 2, 0,
		          rate_plan=self.block.name,
		          check_in_time="09:00", check_out_time="13:00")
		self.assertEqual(q["day_use_billing"]["billing_basis"], "Block")
		self.assertEqual(q["day_use_billing"]["units"], 2)
		self.assertAlmostEqual(q["room_total"], 1000, places=0)

	def test_overnight_quote_unchanged_with_hourly_plan(self):
		from frappe.utils import add_days
		q = quote(PROP_A, self.rt, TODAY, add_days(TODAY, 2), 2, 0,
		          rate_plan=self.hourly.name,
		          check_in_time="14:00", check_out_time="11:00")
		self.assertFalse(q["day_use"])
		self.assertNotIn("day_use_billing", q)
		self.assertAlmostEqual(q["room_total"], 4800, places=0)

	def test_due_out_only_after_planned_etd(self):
		res = make_reservation(PROP_A, self.rt, TODAY, TODAY,
		                       status="Checked In", room=self.room)
		res.db_set("is_day_use", 1)
		res.db_set("planned_check_out_time", "13:00:00")
		row = frappe.get_doc("Reservation", res.name)
		before = datetime.strptime(f"{TODAY} 12:00:00", "%Y-%m-%d %H:%M:%S")
		after = datetime.strptime(f"{TODAY} 13:00:00", "%Y-%m-%d %H:%M:%S")
		self.assertFalse(day_use.is_due_out(row, now=before))
		self.assertTrue(day_use.is_due_out(row, now=after))

	def test_room_board_due_out_respects_etd(self):
		res = make_reservation(PROP_A, self.rt, TODAY, TODAY,
		                       status="Checked In", room=self.room)
		res.db_set("is_day_use", 1)
		res.db_set("planned_check_out_time", "23:30:00")
		with patch("kamra.day_use.now_datetime",
		           return_value=datetime.strptime(
			           f"{TODAY} 12:00:00", "%Y-%m-%d %H:%M:%S")):
			# is_due_out reads now from day_use; room_board calls it without now
			with patch("kamra.api.nowdate", return_value=TODAY):
				board = api.room_board(PROP_A)
		tile = next(x for x in board["rooms"] if x.name == self.room)
		# 12:00 < 23:30 → not due yet
		self.assertTrue(tile["day_use"])
		self.assertEqual(tile["etd"], "23:30")
		self.assertFalse(tile["due_out"])

	def test_overstay_full_day_and_folio_post(self):
		set_setting(PROP_A, "day_use_overstay", "Full day")
		res = make_reservation(
			PROP_A, self.rt, TODAY, TODAY, status="Checked In", room=self.room,
			rate_plan=self.hourly.name, is_day_use=1, auto_price=1,
			planned_check_in_time="10:00:00", planned_check_out_time="12:00:00")
		# Past ETD → full day card rate when posting.
		past = datetime.strptime(f"{TODAY} 15:00:00", "%Y-%m-%d %H:%M:%S")
		with patch("kamra.day_use.now_datetime", return_value=past):
			folio_mod.post_remaining_nights(frappe.get_doc("Reservation", res.name))
		folio = frappe.get_doc("Folio", guest_folio(res.name))
		room = [c for c in folio.charges if c.charge_type == "Room"]
		self.assertEqual(len(room), 1)
		self.assertIn("full day", room[0].description)
		# Full day ≈ base 2400 (tax handling may back out); must exceed 2h×200.
		self.assertGreater(float(room[0].amount), 400)

	def test_alert_overdue_day_use_once(self):
		res = make_reservation(PROP_A, self.rt, TODAY, TODAY,
		                       status="Checked In", room=self.room)
		res.db_set("is_day_use", 1)
		res.db_set("planned_check_out_time", "08:00:00")
		past = datetime.strptime(f"{TODAY} 10:00:00", "%Y-%m-%d %H:%M:%S")
		with patch("kamra.day_use.now_datetime", return_value=past):
			first = day_use.alert_overdue_day_use(PROP_A)
			second = day_use.alert_overdue_day_use(PROP_A)
		self.assertIn(res.name, first)
		self.assertEqual(second, [])


class DayUseUnitsTestCase(AuditTestCase):
	"""Pure unit maths — no property fixtures beyond AuditTestCase."""

	properties = ()

	def test_billable_units_rounding(self):
		plan = {"billing_basis": "Hourly", "hourly_rate": 100, "min_hours": 2,
		        "block_hours": 3, "block_rate": 250}
		u = day_use.billable_units(1.2, plan, overstay="Next hour")
		self.assertEqual(u["hours"], 2)  # min hours
		u = day_use.billable_units(2.1, plan, overstay="Next hour")
		self.assertEqual(u["hours"], 3)
		u = day_use.billable_units(4, plan, overstay="Next block")
		self.assertEqual(u["hours"], 6)
		block = {**plan, "billing_basis": "Block"}
		u = day_use.billable_units(4, block, overstay="Next hour")
		self.assertEqual(u["units"], 2)
		self.assertEqual(u["amount"], 500)
		u = day_use.billable_units(5, plan, overstay="Full day", planned_hours=3)
		self.assertTrue(u["full_day"])
