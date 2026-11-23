"""Gym desk and memberships (#632).

In-house complimentary access posts nothing. Paid access posts to the
guest folio. A membership covers an external customer until its visit
limit. Capacity and a property the desk isn't allowed into are refused.
"""

from __future__ import annotations

import frappe
from frappe.utils import get_datetime

from kamra import recreation
from kamra.tests.audit_fixtures import (
	PROP_A,
	PROP_B,
	TODAY,
	AuditTestCase,
	charges,
	d,
	ensure_user,
	make_guest,
	make_property,
	make_reservation,
	make_room,
	make_room_type,
)


class RecreationBase(AuditTestCase):
	properties = (PROP_A, PROP_B)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger",
		        "kamra.recreation")
		self._stack.enter_context(patch_now())
		make_property(PROP_A, business_date=TODAY)
		make_property(PROP_B, business_date=TODAY)
		rt = make_room_type(PROP_A)
		room = make_room(PROP_A, rt, "G1")
		self.stay = make_reservation(
			PROP_A, rt, TODAY, d(2), status="Checked In",
			room=room, guest=make_guest("Gym Guest"))
		self.gym = frappe.get_doc({
			"doctype": "Recreation Facility", "property": PROP_A,
			"facility_name": "UT Gym", "category": "Gym", "capacity": 1,
			"access": "Both", "price": 200, "status": "Open",
		}).insert(ignore_permissions=True)
		self.other = frappe.get_doc({
			"doctype": "Recreation Facility", "property": PROP_B,
			"facility_name": "UT Other Gym", "category": "Gym", "capacity": 5,
			"access": "Paid", "price": 100, "status": "Open",
		}).insert(ignore_permissions=True)



class RecreationTest(RecreationBase):

	def test_complimentary_posts_nothing_and_paid_posts_to_the_folio(self):
		free = recreation.check_in(self.gym.name, reservation=self.stay.name,
		                           complimentary=1)
		self.assertEqual(free["payment_mode"], "Complimentary")
		self.assertEqual(charges(self.stay.name, "Misc"), [])
		recreation.check_out(free["name"])
		paid = recreation.check_in(self.gym.name, reservation=self.stay.name)
		self.assertEqual(paid["payment_mode"], "Folio")
		posted = charges(self.stay.name, "Misc")
		self.assertEqual(len(posted), 1)
		self.assertEqual(float(posted[0].amount), 200)

	def test_capacity_and_closed_hours_are_refused(self):
		recreation.check_in(self.gym.name, reservation=self.stay.name, complimentary=1)
		with self.assertRaisesRegex(frappe.ValidationError, "capacity"):
			recreation.check_in(self.gym.name, reservation=self.stay.name, complimentary=1)
		self.gym.opens = "01:00:00"
		self.gym.closes = "02:00:00"
		self.gym.capacity = 5
		self.gym.save(ignore_permissions=True)
		with self.assertRaisesRegex(frappe.ValidationError, "not open"):
			recreation.check_in(self.gym.name, reservation=self.stay.name, complimentary=1)

	def test_a_membership_covers_visits_until_its_limit(self):
		customer = recreation.register_customer(PROP_A, "Walk In")["name"]
		plan = frappe.get_doc({
			"doctype": "Recreation Plan", "property": PROP_A,
			"plan_name": "UT Day", "period": "Day", "price": 500, "visit_limit": 1,
		}).insert(ignore_permissions=True)
		sold = recreation.sell_membership(customer, plan.name, starts_on=TODAY, paid=1)
		self.assertEqual(str(sold["ends_on"]), TODAY)
		first = recreation.check_in(self.gym.name, customer=customer)
		self.assertEqual(first["payment_mode"], "Membership")
		self.assertEqual(charges(self.stay.name, "Misc"), [])
		recreation.check_out(first["name"])
		second = recreation.check_in(self.gym.name, customer=customer)
		self.assertEqual(second["payment_mode"], "Cash")
		self.assertEqual(second["amount"], 200)
		day = recreation.revenue(PROP_A, TODAY)
		self.assertEqual(day["cash"], 200)
		self.assertEqual(day["membership"], 500)
		self.assertEqual(day["folio"], 0)

	def test_a_desk_limited_to_one_property_cannot_check_in_the_other(self):
		desk = ensure_user("ut.rec.desk@example.com", ["Front Desk"])
		frappe.get_doc({
			"doctype": "User Permission", "user": desk,
			"allow": "Property", "for_value": PROP_A,
		}).insert(ignore_permissions=True)
		frappe.clear_cache(user=desk)
		rt = make_room_type(PROP_B, code="GYM")
		room = make_room(PROP_B, rt, "G9")
		stay = make_reservation(
			PROP_B, rt, TODAY, d(2), status="Checked In",
			room=room, guest=make_guest("Other Gym"))
		frappe.set_user(desk)  # nosemgrep: frappe-setuser -- test fixture
		try:
			with self.assertRaises(frappe.PermissionError):
				recreation.check_in(self.other.name, reservation=stay.name)
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture



class RecreationPhaseTwoTest(RecreationBase):
	"""Plans per facility, renewals, passes, spa and pool bookings,
	receipts, the report and the membership ledger."""

	def spa(self):
		room = frappe.get_doc({
			"doctype": "Recreation Facility", "property": PROP_A,
			"facility_name": "UT Spa Room", "category": "Spa", "capacity": 1,
			"access": "Paid", "price": 0, "status": "Open",
			"opens": "09:00:00", "closes": "21:00:00",
		}).insert(ignore_permissions=True)
		massage = recreation.save_treatment(PROP_A, "UT Massage", 60, 1500, room.name)["name"]
		ana = recreation.save_therapist(PROP_A, "UT Ana")["name"]
		return room, massage, ana

	def customer(self, name="UT Member"):
		return recreation.register_customer(PROP_A, name)["name"]

	def test_rules_for_time_fields_and_month_ends(self):
		from datetime import time, timedelta
		self.assertEqual(recreation.as_time(timedelta(hours=6)), time(6, 0))
		self.assertTrue(recreation.within_hours(time(10), time(6), time(22)))
		self.assertTrue(recreation.within_hours(time(1), time(22), time(2)))
		self.assertFalse(recreation.within_hours(time(5), time(6), time(22)))
		self.assertEqual(str(recreation._end("2026-01-31", "Month")), "2026-02-28")
		self.assertEqual(str(recreation._end("2026-01-15", "Month")), "2026-02-14")
		# a 06:00 opening read from the database as a timedelta is before 10:00
		self.gym.opens, self.gym.closes = "06:00:00", "22:00:00"
		self.gym.save(ignore_permissions=True)
		self.assertTrue(recreation._open_now(frappe.get_doc("Recreation Facility", self.gym.name)))

	def test_a_plan_opens_only_its_facilities_and_renews_from_its_end(self):
		pool = frappe.get_doc({
			"doctype": "Recreation Facility", "property": PROP_A,
			"facility_name": "UT Pool", "category": "Pool", "capacity": 5,
			"access": "Both", "price": 300, "status": "Open",
		}).insert(ignore_permissions=True)
		plan = recreation.save_plan(PROP_A, "UT Pool Month", "Month", 900,
		                            facilities=[pool.name])["name"]
		who = self.customer()
		sold = recreation.sell_membership(who, plan, starts_on=TODAY)
		gym = recreation.check_in(self.gym.name, customer=who)
		self.assertEqual(gym["payment_mode"], "Cash")  # the plan doesn't open the gym
		self.assertEqual(gym["receipt"], gym["name"])
		swim = recreation.check_in(pool.name, customer=who)
		self.assertEqual(swim["payment_mode"], "Membership")
		again = recreation.renew_membership(sold["name"])
		self.assertEqual(again["starts_on"], str(frappe.utils.add_days(sold["ends_on"], 1)))
		self.assertEqual(frappe.db.get_value("Recreation Membership", again["name"],
		                                     "renewed_from"), sold["name"])
		ledger = recreation.membership_ledger(who)
		self.assertEqual([e["kind"] for e in ledger["entries"]].count("Renewal"), 1)
		self.assertEqual(ledger["paid"], 900 + 900 + 200)

	def test_expiry_marks_lapsed_memberships(self):
		who = self.customer()
		plan = recreation.save_plan(PROP_A, "UT Day", "Day", 100)["name"]
		sold = recreation.sell_membership(who, plan, starts_on=d(-3))
		recreation.expire_memberships()
		self.assertEqual(frappe.db.get_value("Recreation Membership", sold["name"],
		                                     "status"), "Expired")

	def test_a_signed_pass_checks_in_and_a_forged_one_is_refused(self):
		who = self.customer()
		code = recreation.entry_pass(customer=who)["code"]
		self.assertTrue(recreation.entry_pass(reservation=self.stay.name)["qr"]
		                .startswith("data:image/svg+xml"))
		visit = recreation.check_in_by_pass(self.gym.name, code)
		self.assertEqual(visit["who"], "UT Member")
		recreation.check_out(visit["name"])
		forged = code[:-1] + ("0" if code[-1] != "0" else "1")
		with self.assertRaisesRegex(frappe.ValidationError, "not a recreation pass"):
			recreation.check_in_by_pass(self.gym.name, forged)
		guest = recreation.entry_pass(reservation=self.stay.name)["code"]
		self.assertEqual(recreation.check_in_by_pass(self.gym.name, guest, 1)["payment_mode"],
		                 "Complimentary")

	def test_spa_never_double_books_a_room_or_a_therapist(self):
		room, massage, ana = self.spa()
		at = f"{d(1)} 10:00:00"
		first = recreation.book(room.name, at, reservation=self.stay.name,
		                        treatment=massage, therapist=ana)
		self.assertEqual(first["ends_at"], f"{d(1)} 11:00:00")
		with self.assertRaisesRegex(frappe.ValidationError, "fully booked"):
			recreation.book(room.name, f"{d(1)} 10:30:00", customer=self.customer(),
			                treatment=massage)
		other = frappe.get_doc({
			"doctype": "Recreation Facility", "property": PROP_A,
			"facility_name": "UT Spa Room 2", "category": "Spa", "capacity": 1,
			"access": "Paid", "price": 0, "status": "Open",
		}).insert(ignore_permissions=True)
		with self.assertRaisesRegex(frappe.ValidationError, "therapist"):
			recreation.book(other.name, f"{d(1)} 10:30:00", customer=self.customer("UT B"),
			                treatment=massage, therapist=ana)
		with self.assertRaisesRegex(frappe.ValidationError, "closed"):
			recreation.book(room.name, f"{d(1)} 20:30:00", reservation=self.stay.name,
			                treatment=massage)
		# arrival posts the treatment to the guest folio
		arrived = recreation.arrive(first["name"])
		self.assertEqual(arrived["payment_mode"], "Folio")
		posted = charges(self.stay.name, "Spa")
		self.assertEqual([(p.description, float(p.amount)) for p in posted],
		                 [("UT Massage", 1500.0)])
		self.assertEqual(frappe.db.get_value("Recreation Booking", first["name"], "status"),
		                 "Arrived")

	def test_pool_sessions_fill_to_capacity(self):
		pool = frappe.get_doc({
			"doctype": "Recreation Facility", "property": PROP_A,
			"facility_name": "UT Lap Pool", "category": "Pool", "capacity": 2,
			"access": "Both", "price": 0, "status": "Open",
			"opens": "07:00:00", "closes": "09:00:00", "slot_minutes": 60,
		}).insert(ignore_permissions=True)
		sessions = recreation.slots(pool.name, d(1))
		self.assertEqual([s["starts_at"][11:16] for s in sessions], ["07:00", "08:00"])
		at = sessions[0]["starts_at"]
		recreation.book(pool.name, at, customer=self.customer("UT P1"))
		recreation.book(pool.name, at, customer=self.customer("UT P2"))
		with self.assertRaisesRegex(frappe.ValidationError, "fully booked"):
			recreation.book(pool.name, at, customer=self.customer("UT P3"))
		self.assertEqual(recreation.slots(pool.name, d(1))[0]["free"], 0)

	def test_receipts_and_the_report(self):
		who = self.customer()
		plan = recreation.save_plan(PROP_A, "UT Gym Month", "Month", 800,
		                            facilities=[self.gym.name])["name"]
		sold = recreation.sell_membership(who, plan, starts_on=TODAY, mode="Card")
		walk = recreation.check_in(self.gym.name, customer=self.customer("UT Walk"))
		recreation.check_out(walk["name"])
		guest = recreation.check_in(self.gym.name, reservation=self.stay.name)
		self.assertEqual(recreation.receipt(sold["name"])["paid_by"], "Card")
		self.assertEqual(recreation.receipt(walk["name"])["amount"], 200)
		with self.assertRaises(frappe.ValidationError):  # a folio charge has the bill
			recreation.receipt(guest["name"])
		out = recreation.report(PROP_A, TODAY, TODAY)
		self.assertEqual(out["use"], {"guest": 1, "external": 1})
		self.assertEqual(out["revenue"]["guest"], 200)
		self.assertEqual(out["revenue"]["membership"], 800)
		self.assertEqual(out["by_facility"]["UT Gym"]["visits"], 2)
		self.assertEqual(out["by_facility"]["UT Gym"]["revenue"], 200 + 200 + 800)
		self.assertEqual(out["memberships"]["active"], 1)

def patch_now():
	from unittest.mock import patch
	from contextlib import ExitStack
	stack = ExitStack()
	stack.enter_context(patch("kamra.recreation.now_datetime",
	                          return_value=get_datetime(f"{TODAY} 10:00:00")))
	stack.enter_context(patch("kamra.recreation.nowtime", return_value="10:00:00"))
	return stack
