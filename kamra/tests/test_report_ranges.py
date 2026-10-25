"""Reports that used to take one day take a From/To range too."""

from __future__ import annotations

import frappe
from frappe.utils import add_days, nowdate

from kamra.business_date import report_range_end
from kamra.cashier import shift_report
from kamra.ledger import folio_history
from kamra.reports import manager_flash
from kamra.rooms import room_insights
from kamra.tests.audit_fixtures import PROP_A, AuditTestCase, make_property


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
