"""Hotel SI list #411: occupant arrival times, the early check-out flow and
the WhatsApp room-charge alert."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.utils import get_datetime, now_datetime

from kamra import api, whatsapp
from kamra import folio as folio_mod
from kamra.settings import clear_cache, write_kv
from kamra.tests.audit_fixtures import (
	PROP_A,
	TODAY,
	AuditTestCase,
	charges,
	d,
	ensure_user,
	guest_folio,
	make_guest,
	make_property,
	make_reservation,
	make_room,
	make_room_type,
)


class _Base(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")
		self.addCleanup(clear_cache, PROP_A)

	def setting(self, key, val):
		write_kv(PROP_A, key, val)
		clear_cache(PROP_A)

	def stay(self, check_in=None, check_out=None, **kw):
		return make_reservation(PROP_A, self.rt, check_in or d(-1),
		                        check_out or d(3), status="Checked In",
		                        room=self.room, **kw)


class OccupantTimesTestCase(_Base):
	def test_check_in_stamps_the_register_and_later_guests_arrive_now(self):
		res = make_reservation(PROP_A, self.rt, TODAY, d(2), room=self.room,
		                       occupants=[{"full_name": "First Friend", "age": 30}])
		res.status = "Checked In"
		res.save(ignore_permissions=True)
		res.reload()
		first = res.occupants[0]
		self.assertEqual(get_datetime(first.arrived_at), get_datetime(res.actual_check_in))

		later = now_datetime()
		out = api.update_occupants(res.name, [
			{"row": first.name, "full_name": "First Friend", "age": 30},
			{"full_name": "Late Friend", "age": 28},
		])
		rows = {r["full_name"]: r for r in out["rows"]}
		self.assertEqual(get_datetime(rows["First Friend"]["arrived_at"]),
		                 get_datetime(str(first.arrived_at)[:19]))
		self.assertGreaterEqual(get_datetime(rows["Late Friend"]["arrived_at"]),
		                        get_datetime(str(later)[:19]))

		# an agent replacing the list without row ids keeps each guest's time
		out = api.update_occupants(res.name, [
			{"full_name": "late friend", "age": 28,
			 "left_at": str(now_datetime())[:19]},
			{"full_name": "First Friend", "age": 30}])
		rows = {r["full_name"].lower(): r for r in out["rows"]}
		self.assertEqual(rows["first friend"]["arrived_at"],
		                 str(first.arrived_at)[:19])
		self.assertTrue(rows["late friend"]["left_at"])

		with self.assertRaises(frappe.ValidationError):
			api.update_occupants(res.name, [
				{"full_name": "Late Friend", "arrived_at": f"{TODAY} 12:00:00",
				 "left_at": f"{TODAY} 10:00:00"}])

	def test_register_before_check_in_has_no_arrival(self):
		res = make_reservation(PROP_A, self.rt, d(1), d(2), room=self.room)
		out = api.update_occupants(res.name, [{"full_name": "Early Bird"}])
		self.assertIsNone(out["rows"][0]["arrived_at"])


class EarlyCheckoutTestCase(_Base):
	def setUp(self):
		super().setUp()
		frappe.flags.allow_unsettled_checkout = True
		self.addCleanup(setattr, frappe.flags, "allow_unsettled_checkout", False)

	def nights(self, res):
		return sorted(str(c.posting_date) for c in charges(res.name, "Room"))

	def test_default_policy_bills_every_booked_night_as_before(self):
		res = self.stay()
		from kamra.checkout import early_departure_plan
		plan = early_departure_plan(res)
		self.assertEqual(plan["policy"], "All Nights")
		self.assertEqual(plan["unused_nights"], 3)
		self.assertEqual(plan["new_check_out"], TODAY)
		api.check_out(res.name)
		self.assertEqual(self.nights(res), [d(-1), TODAY, d(1), d(2)])

	def test_no_charge_policy_shortens_and_bills_only_nights_stayed(self):
		self.setting("early_departure_fee", "None")
		res = self.stay()
		with self.assertRaises(frappe.ValidationError):
			api.check_out(res.name)  # unused nights are never billed by accident
		api.check_out(res.name, early_reason="Family emergency")
		res.reload()
		self.assertEqual(res.status, "Checked Out")
		self.assertEqual(str(res.check_out_date), TODAY)
		self.assertEqual(str(res.booked_check_out_date), d(3))
		self.assertEqual(res.early_departure_reason, "Family emergency")
		self.assertEqual(self.nights(res), [d(-1)])
		self.assertFalse([c for c in charges(res.name, "Misc")
		                  if "Early departure" in (c.description or "")])
		from kamra.custom_reports import _fetch_early_departures
		real = str(res.actual_check_out)[:10]  # stamped by the wall clock
		rows = _fetch_early_departures(PROP_A, real, real)
		row = next(r for r in rows if r["name"] == res.name)
		self.assertEqual(row["check_out_date"], d(3))
		self.assertEqual(row["reason"], "Family emergency")

	def test_one_night_policy_and_who_may_change_it(self):
		self.setting("early_departure_fee", "One Night")
		res = self.stay()
		desk = ensure_user("ut-early-desk@example.com", ["Front Desk"])
		frappe.set_user(desk)
		with self.assertRaises(frappe.PermissionError):
			api.early_departure(res.name, "Flight moved", fee="None")
		out = api.early_departure(res.name, "Flight moved")
		frappe.set_user("Administrator")
		self.assertEqual(out["unused_nights"], 3)
		self.assertEqual(out["amount"], 1000)
		fee = [c for c in charges(res.name, "Misc") if "Early departure" in c.description]
		self.assertEqual([c.amount for c in fee], [1000])
		self.assertEqual(fee[0].parent, guest_folio(res.name))
		folio_mod.post_remaining_nights(frappe.get_doc("Reservation", res.name))
		self.assertEqual(self.nights(res), [d(-1)])

	def test_company_that_pays_the_room_pays_the_charge(self):
		self.setting("early_departure_fee", "One Night")
		name = "UT Early Corp"
		if not frappe.db.exists("Corporate Account", name):
			frappe.get_doc({"doctype": "Corporate Account", "company_name": name,
			                "credit_allowed": 1,
			                "billing_rules": [{"charge_type": "Room", "pay_by": "Company"}]}
			               ).insert(ignore_permissions=True)
		res = self.stay(company=name, booking_type="Corporate")
		api.early_departure(res.name, "Meeting ended early")
		fee = [c for c in charges(res.name, "Misc") if "Early departure" in c.description]
		self.assertEqual(frappe.db.get_value("Folio", fee[0].parent, "folio_type"), "Company")

	def test_finance_can_waive_the_charge(self):
		self.setting("early_departure_fee", "All Nights")
		res = self.stay()
		fin = ensure_user("ut-early-fin@example.com", ["Finance"])
		frappe.set_user(fin)
		out = api.early_departure(res.name, "Complaint, GM waived", fee="None")
		frappe.set_user("Administrator")
		self.assertEqual(out["amount"], 0)

	def test_not_early_is_refused_and_context_shows_the_plan(self):
		self.setting("early_departure_fee", "None")
		res = self.stay(check_out=TODAY)
		with self.assertRaises(frappe.ValidationError):
			api.early_departure(res.name, "x")
		early = make_reservation(PROP_A, self.rt, d(-1), d(2), status="Checked In",
		                         room=make_room(PROP_A, self.rt, "102"))
		from kamra.checkout import _checkout_context
		ctx = _checkout_context(early.name)
		self.assertEqual(ctx["early_departure"]["unused_nights"], 2)
		self.assertIn("early_departure", [b["code"] for b in ctx["blockers"]])


class RoomChargeAlertTestCase(_Base):
	def setUp(self):
		super().setUp()
		self.conn = SimpleNamespace(tpl_room_charge="kamra_room_charge",
		                            get=lambda k, d=None: getattr(self.conn, k, d))
		self._stack.enter_context(patch.object(whatsapp, "_conn", return_value=self.conn))
		self.enq = self._stack.enter_context(patch("frappe.enqueue"))
		self.guest = make_guest("UT Alert", phone="+919800000001")
		self.res = self.stay(guest=self.guest)
		self.folio = guest_folio(self.res.name)
		self.addCleanup(self._unthrottle)
		self._unthrottle()

	def _unthrottle(self):
		c = frappe.cache()
		c.delete(c.make_key(f"kamra_wa_room_charge:{self.folio}"))

	def post(self, amount=250, charge_type="Minibar"):
		api.post_stay_charge(self.res.name, charge_type, "Minibar: 2 sodas", amount)

	def test_off_by_default(self):
		self.post()
		self.enq.assert_not_called()

	def test_one_alert_per_window_with_the_charge(self):
		self.setting("room_charge_whatsapp", 1)
		self.post()
		self.post()
		self.assertEqual(self.enq.call_count, 1)
		kw = self.enq.call_args.kwargs
		self.assertEqual(kw["folio"], self.folio)
		self.assertTrue(kw["enqueue_after_commit"])
		self.assertGreaterEqual(kw["amount"], 250)

		with patch.object(whatsapp, "send_template", return_value={"sent": True}) as st:
			whatsapp.send_room_charge_alert(**{k: kw[k] for k in
			                                   ("folio", "reservation", "amount", "description")})
		args = st.call_args.args
		self.assertEqual(args[1], "+919800000001")
		self.assertEqual(args[2], "kamra_room_charge")
		self.assertEqual(args[3][2], "Minibar: 2 sodas")

	def test_room_nights_negative_lines_and_company_bills_never_alert(self):
		self.setting("room_charge_whatsapp", 1)
		folio_mod.post_remaining_nights(self.res)  # the audit's writer
		folio = frappe.get_doc("Folio", self.folio)
		self.assertFalse(whatsapp.queue_room_charge_alert(
			folio, {"charge_type": "Minibar", "amount": -50}))
		folio.folio_type = "Company"
		self.assertFalse(whatsapp.queue_room_charge_alert(
			folio, {"charge_type": "Minibar", "amount": 100}))
		self.enq.assert_not_called()

	def test_no_template_no_alert(self):
		self.setting("room_charge_whatsapp", 1)
		self.conn.tpl_room_charge = None
		self.post()
		self.enq.assert_not_called()
