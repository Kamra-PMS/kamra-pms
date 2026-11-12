"""Reports that used to take one day take a From/To range too."""

from __future__ import annotations

import frappe
from frappe.utils import add_days, nowdate

from kamra.business_date import report_range_end
from kamra.cashier import shift_report
from kamra.folio import post_room_night
from kamra.ledger import folio_history
from kamra.reports import manager_flash
from kamra.rooms import room_insights
from kamra.tests.audit_fixtures import (
	PROP_A,
	TODAY,
	AuditTestCase,
	d,
	make_property,
	make_reservation,
	make_room,
	make_room_type,
)


class ReportRangeTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		make_property(PROP_A)

	def test_range_guard(self):
		self.assertEqual(report_range_end("2026-10-01"), "2026-10-01")
		self.assertEqual(report_range_end("2026-10-01", "2026-10-05"), "2026-10-05")
		with self.assertRaises(frappe.ValidationError):
			report_range_end("2026-10-05", "2026-10-01")
		with self.assertRaises(frappe.ValidationError):
			report_range_end("2026-01-01", "2026-06-01")

	def test_flash_over_a_range_is_the_sum_of_its_days(self):
		end, start = nowdate(), add_days(nowdate(), -2)
		one = manager_flash(PROP_A, end)
		self.assertEqual(one["from_date"], end)
		rng = manager_flash(PROP_A, end, from_date=start)
		self.assertEqual([r["date"] for r in rng["trend"]],
		                 [str(add_days(start, i)) for i in range(3)])
		for k in ("rooms_sold", "room_revenue", "total_revenue"):
			self.assertEqual(rng["today"][k], sum(r[k] for r in rng["trend"]))

	def test_other_reports_take_a_range(self):
		start, end = str(add_days(nowdate(), -6)), nowdate()
		self.assertEqual(shift_report(PROP_A, start, end)["to_date"], end)
		ins = room_insights(PROP_A, from_date=start, to_date=end, refresh=1)
		self.assertEqual((ins["days"], ins["from_date"], ins["to_date"]), (7, start, end))
		self.assertIsInstance(folio_history(PROP_A, from_date=start, to_date=end)["folios"], list)


class FlashOccupancyTestCase(AuditTestCase):
	"""Occupancy on the flash, as OPERA's Manager's Report counts it: rooms
	occupied over rooms not out of order. On the open business date the
	rooms occupied are the rooms in house; once the night audit has closed
	a date, they are the room nights it posted. Room revenue, ADR and RevPAR
	stay posted only."""

	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.reports")
		make_property(PROP_A, business_date=TODAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.rooms = [make_room(PROP_A, self.rt, f"5{i:02d}") for i in range(1, 14)]
		frappe.db.set_value("Room", {"property": PROP_A},
		                    {"housekeeping_status": "Clean", "occupancy_status": "Vacant"})

	def check_in(self, room, check_in=None, check_out=None):
		return make_reservation(PROP_A, self.rt, check_in or d(-1),
		                        check_out or d(2), status="Checked In", room=room)

	def test_flash_occupancy_counts_in_house_before_audit(self):
		for room in self.rooms[:4]:
			self.check_in(room)
		today = manager_flash(PROP_A, TODAY)["today"]
		self.assertEqual(today["rooms_sold"], 0)  # nothing posted yet
		self.assertEqual(today["rooms_occupied"], 4)
		self.assertEqual(today["available_rooms"], 13)
		self.assertEqual(today["occupancy_basis"], "in_house")
		self.assertEqual(today["occupancy_pct"], 30.8)
		self.assertEqual((today["room_revenue"], today["adr"]), (0, 0))

	def test_flash_excludes_out_of_order(self):
		for room in self.rooms[:4]:
			self.check_in(room)
		frappe.db.set_value("Room", self.rooms[-1], "housekeeping_status", "Out of Order")
		flash = manager_flash(PROP_A, TODAY)
		self.assertEqual(flash["total_rooms"], 13)
		self.assertEqual(flash["available_rooms"], 12)
		self.assertEqual(flash["today"]["available_rooms"], 12)
		self.assertEqual(flash["today"]["occupancy_pct"], 33.3)

	def test_flash_keeps_posted_nights_for_an_audited_date(self):
		yesterday = d(-1)
		posted = self.check_in(self.rooms[0], check_in=d(-2))
		post_room_night(posted, yesterday)
		# checked in today: in house now, but not a room night of yesterday
		self.check_in(self.rooms[1], check_in=TODAY)
		# a maintenance block that covered yesterday takes that room out
		frappe.get_doc({"doctype": "Room Block", "property": PROP_A,
		                "room": self.rooms[-1], "reason": "Maintenance",
		                "from_date": d(-3), "to_date": TODAY,
		                "block_status": "Active"}).insert(ignore_permissions=True)
		day = manager_flash(PROP_A, yesterday)["today"]
		self.assertEqual(day["occupancy_basis"], "posted")
		self.assertEqual((day["rooms_occupied"], day["rooms_sold"]), (1, 1))
		self.assertEqual(day["available_rooms"], 12)
		self.assertEqual(day["occupancy_pct"], round(100 / 12, 1))

	def test_due_out_still_in_house_counts_as_occupied(self):
		self.check_in(self.rooms[0], check_in=d(-3), check_out=d(-1))
		today = manager_flash(PROP_A, TODAY)["today"]
		self.assertEqual(today["rooms_occupied"], 1)
		self.assertEqual(today["occupancy_pct"], round(100 / 13, 1))
