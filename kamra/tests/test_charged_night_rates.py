"""A rate change on a stay in house never re-prices a night already on the
folio (settings: charged_night_rate_change). Each policy is driven by an
extension into a long-stay tier, and the booking total must equal what the
folios bill once every night is posted."""

from __future__ import annotations

import frappe

from kamra import api, settings
from kamra import folio as folio_mod
from kamra.tests.audit_fixtures import (
	PROP_A,
	TODAY,
	AuditTestCase,
	d,
	ensure_user,
	make_property,
	make_reservation,
	make_room,
	make_room_type,
)

FIN = "ut-charged-fin@kamra.local"
DESK = "ut-charged-desk@kamra.local"


class ChargedNightRatesTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")
		frappe.db.delete("Long Stay Discount", {"property": PROP_A})
		frappe.db.delete("Rate Guardrail", {"property": PROP_A})
		frappe.db.delete("Property Setting", {"property": PROP_A,
		                                      "setting_key": "charged_night_rate_change"})
		settings.clear_cache(PROP_A)
		# 5+ nights: 20% off every night
		frappe.get_doc({"doctype": "Long Stay Discount", "property": PROP_A,
		                "min_nights": 5, "discount_percent": 20}).insert()
		# 4 nights, two of them already charged at 1000
		self.res = make_reservation(PROP_A, self.rt, d(-2), d(2),
		                            status="Checked In", room=self.room,
		                            auto_price=1)
		for day in (d(-2), d(-1)):
			folio_mod.post_room_night(self.res, day)

	def tearDown(self):
		settings.clear_cache(PROP_A)
		super().tearDown()

	def policy(self, value):
		settings.write_kv(PROP_A, "charged_night_rate_change", value)
		settings.clear_cache(PROP_A)

	def extend(self, nights_to=3):
		pv = api.amend_stay_preview(self.res.name, d(-2), d(nights_to))
		api.amend_stay(self.res.name, d(-2), d(nights_to), confirm_price=1)
		return pv, frappe.get_doc("Reservation", self.res.name)

	def rates(self, res):
		return {str(n.stay_date): n.rate for n in res.night_rates}

	def adjustments(self):
		return frappe.get_all(
			"Folio Charge",
			filters={"reservation": self.res.name, "charge_type": "Rate Adjustment"},
			fields=["posting_date", "stay_date", "amount", "gst_rate", "description"],
			order_by="stay_date asc, amount asc")

	def assert_booking_matches_folio(self, res):
		folio_mod.post_remaining_nights(res)
		billed = sum(frappe.get_all("Folio", filters={"reservation": res.name},
		                            pluck="grand_total"))
		self.assertAlmostEqual(float(res.amount_after_tax), billed, places=2)

	def test_default_keeps_charged_nights(self):
		pv, res = self.extend()
		self.assertEqual(self.rates(res), {d(-2): 1000, d(-1): 1000, d(0): 800,
		                                   d(1): 800, d(2): 800})
		self.assertFalse(self.adjustments())
		cn = pv["charged_nights"]
		self.assertEqual(cn["policy"], "Keep charged nights")
		self.assertEqual([n["action"] for n in cn["nights"]], ["kept", "kept"])
		gst = res.night_rates[0].gst_rate
		self.assertAlmostEqual(cn["kept_difference"], 400 * (1 + gst / 100), places=2)
		self.assertAlmostEqual(pv["new_amount"], float(res.amount_after_tax), places=2)
		self.assert_booking_matches_folio(res)

	def test_credit_the_difference(self):
		self.policy("Credit the difference")
		pv, res = self.extend()
		self.assertEqual(set(self.rates(res).values()), {800})
		adj = self.adjustments()
		gst = frappe.db.get_value("Folio Charge", {"reservation": res.name,
		                                           "charge_type": "Room"}, "gst_rate")
		self.assertEqual([(str(a.stay_date), a.amount) for a in adj],
		                 [(d(-2), -200), (d(-1), -200)])
		for a in adj:
			self.assertEqual(str(a.posting_date), TODAY)
			self.assertEqual(a.gst_rate, gst)
			self.assertIn("Rate change: night of", a.description)
		self.assertAlmostEqual(pv["charged_nights"]["credit_total"],
		                       -400 * (1 + gst / 100), places=2)
		self.assertAlmostEqual(pv["new_amount"], float(res.amount_after_tax), places=2)
		# a later re-price does not credit the same nights again
		api.amend_stay(self.res.name, d(-2), d(4), confirm_price=1)
		self.assertEqual(len(self.adjustments()), 2)
		self.assert_booking_matches_folio(frappe.get_doc("Reservation", res.name))

	def test_credit_lowers_room_revenue_not_rooms_sold(self):
		from kamra.reports import _day_stats
		self.policy("Credit the difference")
		folio_mod.post_room_night(self.res, TODAY)
		before = _day_stats(PROP_A, TODAY, 1)
		self.assertEqual((before["rooms_sold"], before["room_revenue"]), (1, 1000))
		self.extend()  # three charged nights credited 200 each, dated today
		after = _day_stats(PROP_A, TODAY, 1)
		self.assertEqual(after["rooms_sold"], 1)
		self.assertAlmostEqual(after["room_revenue"], 400)
		self.assertEqual(after["adr"], 400)
		self.assertAlmostEqual(after["other_revenue"], before["other_revenue"])

	def test_credit_never_raises_a_charged_night(self):
		self.policy("Credit the difference")
		frappe.db.delete("Long Stay Discount", {"property": PROP_A})
		frappe.db.set_value("Room Type", self.rt, "base_price", 1500)
		frappe.clear_document_cache("Room Type", self.rt)
		_, res = self.extend()
		self.assertEqual(self.rates(res)[d(-2)], 1000)
		self.assertEqual(self.rates(res)[d(0)], 1500)
		self.assertFalse(self.adjustments())
		self.assert_booking_matches_folio(res)

	def test_correct_back_dated_rates(self):
		self.policy("Correct back-dated rates")
		_, res = self.extend()
		# the amend itself keeps the charged nights
		self.assertEqual(self.rates(res)[d(-2)], 1000)
		self.assertFalse(self.adjustments())
		dry = api.correct_charged_nights(res.name, dry_run=1)
		self.assertEqual([n["date"] for n in dry["nights"]], [d(-2), d(-1)])

		ensure_user(DESK, ["Front Desk"])
		ensure_user(FIN, ["Finance"])
		frappe.set_user(DESK)  # nosemgrep: frappe-setuser -- test persona
		with self.assertRaises(frappe.PermissionError):
			api.correct_charged_nights(res.name, reason="Wrong tariff")
		frappe.set_user(FIN)  # nosemgrep: frappe-setuser -- test persona
		with self.assertRaises(frappe.ValidationError):  # no reason
			api.correct_charged_nights(res.name, pin="1234")
		with self.assertRaisesRegex(frappe.ValidationError, "PIN_NOT_SET"):
			api.correct_charged_nights(res.name, reason="Wrong tariff")
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- fixture setup
		frappe.get_doc({"doctype": "Cashier PIN", "user": FIN, "pin": "1234",
		                "must_reset": 0}).insert(ignore_permissions=True)
		frappe.set_user(FIN)  # nosemgrep: frappe-setuser -- test persona
		with self.assertRaisesRegex(frappe.ValidationError, "SUPERVISOR_PIN_REQUIRED"):
			api.correct_charged_nights(res.name, reason="Wrong tariff")
		self.assertFalse(self.adjustments())
		out = api.correct_charged_nights(res.name, reason="Wrong tariff", pin="1234")
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- fixture cleanup
		self.assertTrue(out["ok"])
		adj = self.adjustments()
		self.assertEqual([(str(a.stay_date), a.amount) for a in adj],
		                 [(d(-2), -1000), (d(-2), 800), (d(-1), -1000), (d(-1), 800)])
		self.assertTrue(all(str(a.posting_date) == TODAY for a in adj))
		res = frappe.get_doc("Reservation", res.name)
		self.assertEqual(set(self.rates(res).values()), {800})
		# the posted night lines are untouched
		self.assertEqual(sorted(frappe.get_all(
			"Folio Charge", filters={"reservation": res.name, "charge_type": "Room"},
			pluck="amount")), [1000, 1000])
		self.assert_booking_matches_folio(res)

	def test_correction_is_off_by_default(self):
		with self.assertRaisesRegex(frappe.ValidationError, "is off"):
			api.correct_charged_nights(self.res.name, reason="x", pin="1")

	def test_rate_adjustment_cannot_be_hand_posted(self):
		folio = frappe.db.get_value("Folio", {"reservation": self.res.name})
		with self.assertRaises(frappe.ValidationError):
			api.add_folio_charge(folio, "Rate Adjustment", "x", -100)
