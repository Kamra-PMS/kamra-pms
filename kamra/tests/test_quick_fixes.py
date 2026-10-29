"""Small fixes from the SI call list (#411): the Taxi charge, the market
segment, reservation numbers by financial year, priced check-in requests,
and the payment link in the WhatsApp payment message."""

from __future__ import annotations

from unittest.mock import patch

import frappe

from kamra import api, checkin, ledger
from kamra.localization import financial_year, pack_for
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


class QuickFixesTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")

	def test_taxi_is_a_charge_with_its_own_code(self):
		res = make_reservation(PROP_A, self.rt, TODAY, d(2), status="Checked In",
		                       room=self.room)
		api.post_stay_charge(res.name, "Taxi", "UT airport run", 800)
		line = frappe.get_all("Folio Charge", filters={"parent": guest_folio(res.name),
		                                               "charge_type": "Taxi"})
		self.assertTrue(line)
		self.assertEqual(ledger.CHARGE_TYPE_TO_CODE["Taxi"][0], "3200")

	def test_market_segment_on_a_booking(self):
		out = api.create_booking(PROP_A, self.rt, d(3), d(4), "UT Segment Guest",
		                         phone="+91 90000 77001", market_segment="Leisure")
		self.assertEqual(frappe.db.get_value("Reservation", out["reservation"],
		                                     "market_segment"), "Leisure")

	def test_numbers_restart_with_the_financial_year(self):
		pack = pack_for(PROP_A)
		self.assertEqual(financial_year(pack, "2027-02-10"), 2026)
		self.assertEqual(financial_year(pack, "2027-04-01"), 2027)
		res = make_reservation(PROP_A, self.rt, d(5), d(6))
		self.assertTrue(res.name.startswith(f"RES-{financial_year(pack, frappe.utils.today())}-"))

	def test_a_priced_request_goes_on_the_bill(self):
		res = make_reservation(PROP_A, self.rt, TODAY, d(2), status="Checked In",
		                       room=self.room)
		checkin.log_checkin_requests(res.name, ["extra_bed", "wake_up_call"],
		                             prices={"extra_bed": 700, "wake_up_call": 50})
		lines = frappe.get_all("Folio Charge", filters={"parent": guest_folio(res.name),
		                                                "description": "Extra bed"},
		                       fields=["charge_type", "amount"])
		self.assertEqual([(r.charge_type, r.amount) for r in lines], [("Extra Guests", 700)])
		# a wake-up call is never charged
		self.assertFalse(frappe.get_all("Folio Charge", filters={
			"parent": guest_folio(res.name), "description": "Wake-up call"}))

	def test_a_lost_counter_restarts_after_the_highest_number(self):
		first = make_reservation(PROP_A, self.rt, d(5), d(6))
		prefix = first.name.rsplit("-", 1)[0] + "-"
		frappe.db.sql("DELETE FROM `tabSeries` WHERE name = %s", prefix)
		second = make_reservation(PROP_A, self.rt, d(7), d(8))
		self.assertGreater(int(second.name.rsplit("-", 1)[1]), int(first.name.rsplit("-", 1)[1]))

	def test_saving_the_requests_step_again_does_not_bill_twice(self):
		res = make_reservation(PROP_A, self.rt, TODAY, d(2), status="Checked In",
		                       room=self.room)
		for _ in range(2):
			checkin.log_checkin_requests(res.name, ["extra_bed"], prices={"extra_bed": 700})
		self.assertEqual(len(frappe.get_all("Folio Charge", filters={
			"parent": guest_folio(res.name), "description": "Extra bed"})), 1)

	def test_whatsapp_payment_message_carries_the_link(self):
		from kamra import whatsapp
		res = make_reservation(PROP_A, self.rt, TODAY, d(2), status="Checked In",
		                       room=self.room)
		frappe.db.set_value("Guest", res.guest, "phone", "+91 90000 77002")
		sent = {}
		with patch.object(whatsapp, "_conn", return_value=frappe._dict(tpl_payment_request="pay")), \
				patch("kamra.payments.create_payment_link",
				      return_value={"url": "https://pay.example/abc"}), \
				patch.object(whatsapp, "send_template",
				             side_effect=lambda *a, **k: sent.update(args=a[3]) or {"ok": True}):
			out = whatsapp.send_payment_request(res.name, 500)
		self.assertEqual(sent["args"][2], "https://pay.example/abc")
		self.assertEqual(out["payment_link"], "https://pay.example/abc")
