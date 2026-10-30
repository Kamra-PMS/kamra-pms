"""Long-stay discount: "N+ nights: X% off" priced in the quote, locked on
the booking's nights, held at the rate guardrail floor."""

from __future__ import annotations

import frappe

from kamra import api
from kamra.tests.audit_fixtures import (PROP_A, AuditTestCase, d, make_property,
                                        make_room, make_room_type)


class LongStayTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		make_property(PROP_A)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		make_room(PROP_A, self.rt, "101")
		frappe.db.delete("Long Stay Discount", {"property": PROP_A})
		frappe.db.delete("Rate Guardrail", {"property": PROP_A})

	def rule(self, nights, pct, **kw):
		return frappe.get_doc({"doctype": "Long Stay Discount", "property": PROP_A,
		                       "min_nights": nights, "discount_percent": pct,
		                       **kw}).insert().name

	def quote(self, nights):
		return api.get_quote(property=PROP_A, room_type=self.rt,
		                     check_in_date=d(1), check_out_date=d(1 + nights))

	def test_no_rule_prices_as_before(self):
		q = self.quote(7)
		self.assertIsNone(q["long_stay"])
		self.assertAlmostEqual(q["room_total"], 7000)

	def test_highest_tier_reached_applies(self):
		self.rule(3, 10)
		self.rule(7, 20)
		self.assertIsNone(self.quote(2)["long_stay"])
		q3, q7 = self.quote(3), self.quote(7)
		self.assertAlmostEqual(q3["room_total"], 2700)
		self.assertAlmostEqual(q7["room_total"], 5600)
		self.assertEqual(q7["long_stay"]["percent"], 20)
		self.assertAlmostEqual(q7["long_stay"]["amount"], 1400)
		self.assertIn("20% off", q7["line_items"][0]["description"])
		# the nights the folio bills carry the discount
		b = api.create_booking(property=PROP_A, room_type=self.rt, check_in_date=d(1),
		                       check_out_date=d(8), guest_name="UT Long Stay")
		res = frappe.get_doc("Reservation", b["reservation"])
		self.assertAlmostEqual(sum(n.rate for n in res.night_rates), 5600)
		self.assertAlmostEqual(res.amount_after_tax, q7["amount_after_tax"])

	def test_guardrail_floor_holds(self):
		self.rule(3, 30)
		frappe.get_doc({"doctype": "Rate Guardrail", "property": PROP_A,
		                "floor_price": 800, "ceiling_price": 5000}).insert()
		q = self.quote(3)
		self.assertAlmostEqual(q["room_total"], 2400)
		self.assertAlmostEqual(q["long_stay"]["amount"], 600)

	def test_hurdle_minimum_holds(self):
		# a 10,000 room in a hurdle tier with an 8,000 minimum: 25% off would
		# be 7,500, but the tier's minimum is a floor too
		rt = make_room_type(PROP_A, "LUX", base_price=10000)
		frappe.db.delete("Hurdle Rate", {"property": PROP_A})
		frappe.get_doc({"doctype": "Hurdle Rate", "property": PROP_A, "room_type": rt,
		                "occupancy_from": 0, "premium_pct": 0,
		                "min_rate": 8000}).insert()
		self.rule(3, 25)
		q = api.get_quote(property=PROP_A, room_type=rt,
		                  check_in_date=d(1), check_out_date=d(4))
		self.assertAlmostEqual(q["room_total"], 24000)
		self.assertAlmostEqual(q["long_stay"]["amount"], 6000)

	def test_bad_rule_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self.rule(3, 100)
		with self.assertRaises(frappe.ValidationError):
			self.rule(0, 10)
