"""The night audit report: day, month to date and year to date; food and
beverage apart; each outlet; banquets; balances brought and carried forward.
"""

from __future__ import annotations

import frappe

from kamra import audit_report, pos
from kamra import folio as folio_mod
from kamra.tests import test_folio_leaks as leaks
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


class AuditReportTestCase(AuditTestCase):
	properties = (PROP_A,)
	outlet = leaks.FolioLeaksTestCase.outlet

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")
		make_room(PROP_A, self.rt, "102")

	def test_the_day_split_by_source(self):
		outlet, dosa, gin = self.outlet()
		res = make_reservation(PROP_A, self.rt, TODAY, d(2), status="Checked In",
		                       room=self.room)
		folio_mod.post_remaining_nights(res)
		# a mixed bill paid at the outlet, and liquor charged to the room
		mixed = pos.create_order(outlet, [{"menu_item": dosa, "qty": 2},
		                                  {"menu_item": gin, "qty": 1}],
		                         table_no="T1", order_type="Dine In")
		pos.pay_order(mixed["order"], "Cash")
		room_bill = pos.create_order(outlet, [{"menu_item": gin, "qty": 1}],
		                             room=self.room, order_type="Room Service")
		pos.deliver_order(room_bill["order"])
		vb = frappe.get_doc({"doctype": "Venue Booking", "property": PROP_A,
		                     "status": "Confirmed", "event_date": TODAY}
		                    ).insert(ignore_permissions=True, ignore_mandatory=True)
		# a function's totals as its quote left them
		vb.db_set({"fnb_spend": 5000, "venue_rental": 2000, "taxable_amount": 7500})
		r = audit_report.build(PROP_A, TODAY)
		day, mtd, ytd = r["periods"]
		self.assertEqual((day["food"], day["beverage"]), (400, 1000))
		self.assertEqual(day["banquets"], 7500)
		self.assertEqual(day["banquet"]["fnb"], 5000)
		bar = next(o for o in day["outlets"] if o["outlet"] == outlet)
		self.assertEqual((bar["bills"], bar["to_rooms"]), (2, 500))
		self.assertGreaterEqual(day["rooms_sold"], 1)
		self.assertGreater(day["room_revenue"], 0)
		# the room-charged gin is on the folio too, but counted once
		self.assertAlmostEqual(day["total_revenue"],
		                       day["room_revenue"] + 1400 + 7500
		                       + day["meal_plan_minibar"] + day["other"], 2)
		for per in (mtd, ytd):
			self.assertGreaterEqual(per["total_revenue"], day["total_revenue"])

	def test_year_starts_in_april_for_india(self):
		from datetime import date
		self.assertEqual(audit_report.year_start(PROP_A, "2027-02-10"), date(2026, 4, 1))
		self.assertEqual(audit_report.year_start(PROP_A, "2026-05-10"), date(2026, 4, 1))

	def test_balances_carry_forward(self):
		res = make_reservation(PROP_A, self.rt, TODAY, d(2), status="Checked In",
		                       room=self.room)
		folio_mod.post_remaining_nights(res)
		guest = next(b for b in audit_report.build(PROP_A, TODAY)["balances"]
		             if b["ledger"] == "Guest")
		self.assertAlmostEqual(guest["carried_forward"],
		                       guest["brought_forward"] + guest["debit"] - guest["credit"], 2)
		self.assertGreater(guest["debit"], 0)

	def test_desk_and_banquet_folio_lines_count_once(self):
		from kamra import api
		from kamra.tests.audit_fixtures import ensure_user, guest_folio
		res = make_reservation(PROP_A, self.rt, TODAY, d(2), status="Checked In",
		                       room=self.room)
		folio = guest_folio(res.name)
		# F&B typed at the desk (no restaurant bill) counts; a function's line
		# posted to the folio is already in the banquet figures
		api.add_folio_charge(folio, "Food & Beverage", "UT room-service sandwich", 300,
		                     gst_rate=0)
		api.add_folio_charge(folio, "Misc", "EVT-2026-9999 · UT stage", 900, gst_rate=0)
		day = audit_report.build(PROP_A, TODAY)["periods"][0]
		self.assertEqual(day["food"], 300)
		self.assertEqual(day["other"], 0)
		# a Revenue Manager can read it (the ledger step has a narrower gate)
		ensure_user("ut-rm-audit@kamra.local", ["Revenue Manager"])
		frappe.set_user("ut-rm-audit@kamra.local")  # nosemgrep: frappe-setuser -- the role
		try:
			self.assertTrue(audit_report.night_audit_report(PROP_A, TODAY)["balances"])
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- restore
