"""Folio discounts, refunds, room setup and night audit options.

- A refund goes out only when the guest is in credit, up to that credit.
- A discount on the folio: a percent, or an amount for the stay or per
  night, or a promo code; it posts as an allowance on the room nights.
- A room type's ID follows its code.
- Rooms import from a spreadsheet.
- Night audit can extend unchecked-out departures one night.
- A dry property hides alcohol (property_locale.sells_alcohol).
"""

from __future__ import annotations

import frappe

from kamra import api, golive
from kamra import folio as folio_mod
from kamra import night_audit as na
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
from kamra.tests.test_billing_approvals_split import bal, set_setting


class DeskFeedbackTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY)
		frappe.db.delete("Property Setting", {"property": PROP_A})
		set_setting(PROP_A, "use_cashier_tills", 0)
		set_setting(PROP_A, "allowance_approval", "Off")
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")

	def stay(self, nights: int = 3):
		res = make_reservation(PROP_A, self.rt, d(-nights), TODAY,
		                       status="Checked In", room=self.room)
		folio_mod.post_remaining_nights(res)
		return res, guest_folio(res.name)

	def room_total(self, folio: str) -> float:
		return round(sum(c.amount for c in frappe.get_doc("Folio", folio).charges
		                 if c.charge_type == "Room"), 2)

	def allowances(self, folio: str) -> list:
		return [c for c in frappe.get_doc("Folio", folio).charges
		        if c.charge_type == "Allowance"]

	# refunds -----------------------------------------------------------------

	def test_refund_only_when_the_guest_is_in_credit(self):
		_res, folio = self.stay()
		owed = bal(folio)
		self.assertGreater(owed, 100)
		api.add_folio_payment(folio, "Cash", 100)  # paid some, still owes
		with self.assertRaisesRegex(frappe.ValidationError, "nothing is due back"):
			api.refund_folio_payment(folio, 10, "Cash", reason="UT owes")
		api.add_folio_payment(folio, "Cash", owed)  # now 100 over
		with self.assertRaisesRegex(frappe.ValidationError, "is due back"):
			api.refund_folio_payment(folio, 150, "Cash", reason="UT too much")
		api.refund_folio_payment(folio, 100, "Cash", reason="UT change")
		self.assertEqual(bal(folio), 0)

	# discounts ---------------------------------------------------------------

	def test_percent_discount_comes_off_the_room_nights(self):
		_res, folio = self.stay()
		total = self.room_total(folio)
		p = api.post_discount(folio, value=10, kind="Percent", preview=1)
		self.assertAlmostEqual(p["total"], round(total * 0.1, 2), places=2)
		self.assertFalse(self.allowances(folio))  # a preview posts nothing
		before = bal(folio)
		api.post_discount(folio, value=10, kind="Percent", reason="UT loyal guest")
		lines = self.allowances(folio)
		self.assertAlmostEqual(-sum(c.amount for c in lines), p["total"], places=2)
		self.assertIn("Discount 10%", lines[0].description)
		self.assertLess(bal(folio), before)

	def test_amount_per_night_or_for_the_stay(self):
		_res, folio = self.stay(nights=3)
		night = api.post_discount(folio, value=100, kind="Amount", basis="Night",
		                          preview=1)
		self.assertAlmostEqual(night["total"], 300, places=2)
		stay = api.post_discount(folio, value=250, kind="Amount", basis="Stay",
		                         preview=1)
		self.assertAlmostEqual(stay["total"], 250, places=2)

	def test_discount_limits_and_reason(self):
		_res, folio = self.stay()
		with self.assertRaisesRegex(frappe.ValidationError, "more than the room nights"):
			api.post_discount(folio, value=10 ** 7, kind="Amount", reason="UT")
		with self.assertRaisesRegex(frappe.ValidationError, "100%"):
			api.post_discount(folio, value=101, kind="Percent", reason="UT")
		with self.assertRaisesRegex(frappe.ValidationError, "needs a reason"):
			api.post_discount(folio, value=5, kind="Percent")

	def test_discount_refused_when_folio_balance_is_zero(self):
		_res, folio = self.stay()
		api.add_folio_payment(folio, "Cash", bal(folio))
		self.assertAlmostEqual(bal(folio), 0, places=2)
		with self.assertRaisesRegex(frappe.ValidationError, "no open balance"):
			api.post_discount(folio, value=10, kind="Percent", reason="UT")
		with self.assertRaisesRegex(frappe.ValidationError, "no open balance"):
			api.post_discount(folio, value=10, kind="Percent", preview=1)

	def test_discount_capped_to_open_balance(self):
		_res, folio = self.stay()
		owed = bal(folio)
		# Leave a small open balance that a 50% room discount would overshoot.
		leave = round(owed * 0.05, 2)
		api.add_folio_payment(folio, "Cash", round(owed - leave, 2))
		open_bal = bal(folio)
		self.assertGreater(open_bal, 0)
		self.assertLess(open_bal, owed * 0.2)
		preview = api.post_discount(folio, value=50, kind="Percent", preview=1)
		impact = api._discount_tax_inclusive(preview["lines"])
		self.assertLessEqual(impact, open_bal + 0.005)
		api.post_discount(folio, value=50, kind="Percent", reason="UT partial")
		self.assertGreaterEqual(bal(folio), -0.005)

	def test_no_room_nights_yet(self):
		res = make_reservation(PROP_A, self.rt, TODAY, d(2), status="Checked In",
		                       room=self.room)
		with self.assertRaisesRegex(frappe.ValidationError, "no room nights"):
			api.post_discount(guest_folio(res.name), value=10, reason="UT")

	def test_promo_code_on_an_open_folio_once(self):
		_res, folio = self.stay()
		code = "UTDESKPROMO"
		frappe.db.delete("Discount Voucher", {"voucher_code": code})
		v = frappe.get_doc({"doctype": "Discount Voucher", "property": PROP_A,
		                    "voucher_code": code, "discount_type": "Percent",
		                    "value": 20, "max_uses": 0}).insert(ignore_permissions=True)
		api.post_discount(folio, voucher_code=code.lower())
		self.assertEqual(frappe.db.get_value("Discount Voucher", v.name, "times_used"), 1)
		self.assertIn(code, self.allowances(folio)[0].description)
		with self.assertRaisesRegex(frappe.ValidationError, "already on this stay"):
			api.post_discount(folio, voucher_code=code)

	# setup -------------------------------------------------------------------

	def test_room_type_id_follows_its_code(self):
		rt = make_room_type(PROP_A, "UTX")
		room = make_room(PROP_A, rt, "901")
		doc = frappe.get_doc("Room Type", rt)
		doc.room_type_code = "UTY"
		doc.save(ignore_permissions=True)
		self.assertEqual(doc.name, f"{PROP_A}-UTY")
		self.assertFalse(frappe.db.exists("Room Type", rt))
		self.assertEqual(frappe.db.get_value("Room", room, "room_type"), doc.name)

	def test_rooms_import_creates_updates_and_skips(self):
		csv = ("Room Number,Room Type,Floor,Notes\n"
		       "801,STD,8,Sea view\n"
		       "101,UT STD,1,\n"
		       "802,NOPE,8,\n")
		p = golive.preview_rooms(PROP_A, csv)
		self.assertEqual((p["ok"], p["new"], p["existing"], p["skipped"]), (2, 1, 1, 1))
		r = golive.run_rooms(PROP_A, csv)
		self.assertEqual((r["created"], r["updated"], r["skipped"]), (1, 1, 1))
		self.assertEqual(frappe.db.get_value(
			"Room", {"property": PROP_A, "room_number": "801"}, "floor"), "8")
		self.assertEqual(frappe.db.get_value("Room", self.room, "floor"), "1")

	# night audit -------------------------------------------------------------

	def test_auto_extend_departures(self):
		res = make_reservation(PROP_A, self.rt, d(-1), TODAY, status="Checked In",
		                       room=self.room)
		self.assertEqual(na.auto_extend_departures(PROP_A, TODAY), [])  # off
		self.assertEqual(na.check_departures_due(PROP_A, TODAY)["severity"], "block")
		set_setting(PROP_A, "na_auto_extend", 1)
		self.assertEqual(na.check_departures_due(PROP_A, TODAY)["severity"], "warn")
		out = na.auto_extend_departures(PROP_A, TODAY)
		self.assertEqual([x["extended"] for x in out], [True])
		self.assertEqual(str(frappe.db.get_value("Reservation", res.name,
		                                         "check_out_date")), d(1))

	# alcohol -----------------------------------------------------------------

	def test_dry_property_hides_alcohol(self):
		self.assertTrue(api.property_locale(PROP_A)["sells_alcohol"])
		set_setting(PROP_A, "sells_alcohol", 0)
		self.assertFalse(api.property_locale(PROP_A)["sells_alcohol"])

	# invoice title -------------------------------------------------------

	def test_invoice_title_follows_the_tax_law(self):
		from kamra import localization as loc
		self.assertEqual(loc.invoice_title(loc.pack_for_country("India")), "Tax Invoice")
		self.assertEqual(loc.invoice_title(loc.pack_for_country("United Arab Emirates")),
		                 "Tax Invoice")
		from kamra.localization import generic
		self.assertEqual(loc.invoice_title(generic), "Invoice")

	def test_bill_shows_a_discount_not_an_allowance(self):
		_res, folio = self.stay()
		api.post_discount(folio, value=10, kind="Percent", reason="UT")
		heads = {h["head"] for h in api.folio_invoice(folio)["summary_by_head"]}
		self.assertIn("Discount", heads)
		self.assertNotIn("Allowance", heads)
