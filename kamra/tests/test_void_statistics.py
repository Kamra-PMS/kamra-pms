"""Statistics after a void, the same day and after the night audit.

A void keeps the line and posts a reversal dated the business date
(folio.void_charge). The day's statistics count a room night on its own
posting date unless it was voided that same day. A void on a later
business date is an adjustment on that date: OPERA dates the adjustment of
a past revenue date on the current business date, so the closed day is not
restated. The reversal is never a room sold, never a posted night and never
a rate variance. A line that never reached the ledger takes no ledger
reversal either, so the folio still equals its ledger.
"""

from __future__ import annotations

import frappe

from kamra import api, audit_report, ledger, night_audit, pos
from kamra import folio as folio_mod
from kamra.reports import _day_stats, budget_vs_actual, range_stats
from kamra.tests import test_folio_leaks as leaks
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


class VoidStatisticsTestCase(AuditTestCase):
	properties = (PROP_A,)
	outlet = leaks.FolioLeaksTestCase.outlet

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")
		self.room2 = make_room(PROP_A, self.rt, "102")
		self.res = make_reservation(PROP_A, self.rt, TODAY, d(2),
		                            status="Checked In", room=self.room)
		self.folio = guest_folio(self.res.name)

	def night(self, res=None, day=TODAY):
		res = res or self.res
		folio_mod.post_room_night(res, day)
		folio = guest_folio(res.name)
		doc = frappe.get_doc("Folio", folio)
		voided = folio_mod.voided_rows(doc)
		row = next(c for c in doc.charges
		           if c.charge_type == "Room" and str(c.posting_date) == day
		           and not c.get("reversal_of") and c.name not in voided)
		return folio, row.name, float(row.amount)

	def audit_to(self, day):
		frappe.db.set_value("Property", PROP_A, "business_date", day)
		frappe.clear_document_cache("Property", PROP_A)

	def test_a_void_after_the_audit_keeps_the_closed_night_sold(self):
		folio, row, amount = self.night()
		self.audit_to(d(1))
		api.void_folio_charge(folio, row, reason="UT wrong rate")
		closed, today = _day_stats(PROP_A, TODAY, 2), _day_stats(PROP_A, d(1), 2)
		# the closed night keeps its room sold and its revenue
		self.assertEqual((closed["rooms_sold"], closed["room_revenue"]), (1, amount))
		# the reversal is an adjustment on the void date, not a room unsold
		self.assertEqual((today["rooms_sold"], today["room_revenue"]), (0, -amount))
		span = range_stats(PROP_A, TODAY, d(1), 2)
		self.assertEqual((span["rooms_sold"], span["room_revenue"]), (1, 0))
		self.assertEqual(audit_report.build(PROP_A, TODAY)["periods"][0]["rooms_sold"], 1)
		self.assertEqual(audit_report.build(PROP_A, d(1))["periods"][0]["rooms_sold"], 0)

	def test_budget_counts_the_closed_night_once_and_the_void_date_as_unposted(self):
		folio, row, _amount = self.night()
		self.audit_to(d(1))
		api.void_folio_charge(folio, row, reason="UT wrong rate")
		self.audit_to(d(2))
		out = budget_vs_actual(PROP_A, TODAY[:7])
		# night 1 is posted (and stays so); night 2 was never posted - the
		# reversal dated d(1) is not a posted night
		self.assertEqual(out["posted_nights"], 1)
		self.assertEqual(out["posted_through"], TODAY)
		self.assertEqual(out["unposted_nights"], 1)

	def test_a_same_day_void_is_no_room_sold_anywhere(self):
		folio, row, _amount = self.night()
		api.void_folio_charge(folio, row, reason="UT wrong guest")
		self.assertEqual(_day_stats(PROP_A, TODAY, 2)["rooms_sold"], 0)
		self.assertEqual(range_stats(PROP_A, TODAY, TODAY, 2)["rooms_sold"], 0)
		self.audit_to(d(1))
		self.assertEqual(budget_vs_actual(PROP_A, TODAY[:7])["posted_nights"], 0)

	def test_owner_briefing_does_not_count_a_voided_room(self):
		other = make_reservation(PROP_A, self.rt, TODAY, d(2),
		                         status="Checked In", room=self.room2)
		folio, row, _amount = self.night()
		_f2, _r2, amount2 = self.night(other)
		api.void_folio_charge(folio, row, reason="UT wrong guest")
		y = api.owner_briefing(PROP_A, d(1))["yesterday"]
		self.assertEqual(y["room_revenue"], amount2)
		# one room sold yesterday, not two
		self.assertEqual(y["adr"], round(amount2, 0))

	def test_a_promo_code_minimum_ignores_a_voided_night(self):
		folio, row, _amount = self.night()
		api.void_folio_charge(folio, row, reason="UT wrong rate")
		folio_mod.post_room_night(self.res, TODAY)  # the night again, right
		code = "UTVOIDMIN"
		frappe.db.delete("Discount Voucher", {"voucher_code": code})
		frappe.get_doc({"doctype": "Discount Voucher", "property": PROP_A,
		                "voucher_code": code, "discount_type": "Percent",
		                "value": 10, "min_nights": 2, "max_uses": 0}
		               ).insert(ignore_permissions=True)
		# one room night stands on the bill: the voided pair is not two more
		with self.assertRaisesRegex(frappe.ValidationError, "at least 2 nights"):
			api.post_discount(folio, voucher_code=code, preview=1)

	def test_rate_variance_ignores_a_voided_pair_and_a_later_reversal(self):
		_folio, row, _amount = self.night()
		api.void_folio_charge(self.folio, row, reason="UT wrong rate")
		self.assertEqual(night_audit.check_rate_variance(PROP_A, TODAY)["items"], [])
		# a night voided after the audit: its reversal on the void date is
		# not a room night posted off the rate
		_folio, row, _amount = self.night()
		self.audit_to(d(1))
		api.void_folio_charge(self.folio, row, reason="UT wrong rate")
		self.assertEqual(night_audit.check_rate_variance(PROP_A, d(1))["items"], [])

	def test_outlet_bills_on_rooms_ignore_a_voided_bill(self):
		outlet, dosa, _gin = self.outlet()
		order = pos.create_order(outlet, [{"menu_item": dosa, "qty": 1}],
		                         room=self.room, order_type="Room Service")["order"]
		pos.deliver_order(order)
		row = next(c.name for c in frappe.get_doc("Folio", self.folio).charges
		           if f"({order})" in (c.description or ""))
		listed = night_audit.check_pos_room_postings(PROP_A, TODAY)["items"]
		self.assertEqual([i["order"] for i in listed], [order])
		api.void_folio_charge(self.folio, row, reason="UT not ours")
		self.assertEqual(night_audit.check_pos_room_postings(PROP_A, TODAY)["items"], [])

	def test_a_line_with_no_ledger_entry_takes_no_ledger_reversal(self):
		# an outlet transfer posted before the ledger existed: on the folio,
		# with no Guest ledger row
		doc = frappe.get_doc("Folio", self.folio)
		doc.append("charges", {
			"posting_date": TODAY, "charge_type": "Food & Beverage",
			"reservation": self.res.name, "description": "UT outlet transfer (legacy)",
			"qty": 1, "rate": 700, "amount": 700, "gst_rate": 0})
		folio_mod._recalculate(doc)
		doc.save(ignore_permissions=True)
		row = doc.charges[-1].name
		self.assertFalse(frappe.db.exists("Folio Ledger Entry", {
			"source_doctype": "Folio Charge", "source_name": row}))
		out = api.void_folio_charge(self.folio, row, reason="UT posted twice")
		# no ledger credit for a debit the ledger never had
		self.assertFalse(frappe.db.exists("Folio Ledger Entry", {
			"source_doctype": "Folio Charge", "source_name": out["reversal"]}))
		rec = ledger.folio_reconciliation(PROP_A, limit=500)
		self.assertNotIn(self.folio, [f["folio"] for f in rec["folios"]])
