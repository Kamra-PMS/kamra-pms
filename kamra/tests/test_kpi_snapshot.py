"""Business date and daily KPI snapshot endpoints (#542).

The night audit writes one Daily KPI Snapshot for the date it closes; a
second write for that date keeps the first; its figures are the manager
flash's for that date; kpi_snapshots reads a capped date range.
"""

from __future__ import annotations

from unittest.mock import patch

import frappe

from kamra import folio as folio_mod
from kamra.reports import (
	business_date,
	kpi_snapshots,
	manager_flash,
	write_kpi_snapshot,
)
from kamra.tests.audit_fixtures import (
	PROP_A,
	TODAY,
	YESTERDAY,
	AuditTestCase,
	d,
	make_property,
	make_reservation,
	make_room,
	make_room_type,
)

FIGURES = ("rooms_sold", "rooms_occupied", "available_rooms", "occupancy_pct",
           "adr", "revpar", "revpax", "room_revenue", "fnb_revenue",
           "other_revenue", "allowances", "total_revenue")


class KPISnapshotTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY)
		make_property(PROP_A, business_date=YESTERDAY)
		rt = make_room_type(PROP_A, "STD", base_price=1000)
		rooms = [make_room(PROP_A, rt, f"10{i}") for i in range(1, 4)]
		self.res = make_reservation(PROP_A, rt, d(-3), d(2),
		                            status="Checked In", room=rooms[0])

	def snaps(self):
		return kpi_snapshots(PROP_A, YESTERDAY)["snapshots"]

	def test_business_date(self):
		self.assertEqual(business_date(PROP_A)["business_date"], YESTERDAY)

	def test_audit_writes_one_snapshot_equal_to_the_flash(self):
		folio_mod.run_night_audit(PROP_A)
		snaps = self.snaps()
		self.assertEqual(len(snaps), 1)
		snap, flash = snaps[0], manager_flash(PROP_A, YESTERDAY)
		self.assertGreater(snap["room_revenue"], 0)
		for k in FIGURES:
			self.assertEqual(snap[k], flash["today"][k], k)
		self.assertEqual(snap["collections"]["grand_total"],
		                 flash["collections"]["grand_total"])
		self.assertEqual(snap["revenue_by_group"]["rooms"], flash["today"]["room_revenue"])
		self.assertIn("ar_balance", snap)

	def test_snapshot_is_written_once(self):
		folio_mod.run_night_audit(PROP_A)
		first = self.snaps()[0]
		# a second write keeps the first: it does not even recompute
		with patch("kamra.reports.kpi_figures", side_effect=AssertionError):
			write_kpi_snapshot(PROP_A, YESTERDAY)
		self.assertEqual(self.snaps(), [first])
		self.assertEqual(frappe.db.count("Daily KPI Snapshot",
		                                 {"property": PROP_A}), 1)
		# a second audit of the same date answers already_ran, still one
		self.assertTrue(folio_mod.run_night_audit(PROP_A, YESTERDAY).get("already_ran"))
		self.assertEqual(frappe.db.count("Daily KPI Snapshot",
		                                 {"property": PROP_A}), 1)

	def test_open_date_has_no_snapshot(self):
		self.assertEqual(self.snaps(), [])

	def test_range_is_capped_and_ordered(self):
		with self.assertRaises(frappe.ValidationError):
			kpi_snapshots(PROP_A, d(-400), TODAY)
		with self.assertRaises(frappe.ValidationError):
			kpi_snapshots(PROP_A, TODAY, YESTERDAY)
		self.assertEqual(kpi_snapshots(PROP_A, d(-365), TODAY)["snapshots"], [])
