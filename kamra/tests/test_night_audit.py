"""Night audit: kamra.folio.run_night_audit and everything it drives.

Covers the business-date rules (closes only the current date, never one
ahead of today, rolls exactly one day), the postings (one room night per
in-house guest at the engine's rate, missing folios opened, departed guests
left alone), no-shows and their policy fee, the waitlist purge, the Night
Audit Run record, the 03:00 scheduler entry and the role gate on the API.

The calendar is pinned with TODAY / YESTERDAY from audit_fixtures; see that
module for how commits inside the audit are kept out of the site.
"""

from __future__ import annotations

from typing import ClassVar
from unittest.mock import patch

import frappe
from frappe.utils import get_datetime

from kamra import business_date as bdm
from kamra import folio as folio_mod
from kamra import night_audit as na_mod
from kamra.tests.audit_fixtures import (
	PROP_A,
	PROP_B,
	TODAY,
	YESTERDAY,
	AuditTestCase,
	charges,
	d,
	ensure_user,
	guest_folio,
	make_property,
	make_reservation,
	make_room,
	make_room_type,
)


class NightAuditTestCase(AuditTestCase):
	def setUp(self):
		super().setUp()
		self.at(TODAY)
		make_property(PROP_A, business_date=YESTERDAY)
		make_property(PROP_B, business_date=YESTERDAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.rt_deluxe = make_room_type(PROP_A, "DLX", base_price=2500)
		self.rooms = [make_room(PROP_A, self.rt, f"10{i}") for i in range(1, 6)]
		self.deluxe_room = make_room(PROP_A, self.rt_deluxe, "201")
		self.rt_b = make_room_type(PROP_B, "STD", base_price=4000)
		self.room_b = make_room(PROP_B, self.rt_b, "101")
		make_room(PROP_B, self.rt_b, "102")

	# helpers -------------------------------------------------------------

	def in_house(self, room=None, check_in=None, check_out=None, prop=PROP_A,
	             room_type=None, **kw):
		return make_reservation(
			prop, room_type or self.rt, check_in or d(-3), check_out or d(2),
			status="Checked In", room=room or self.rooms[0], **kw)

	def arrival(self, check_in=None, check_out=None, **kw):
		return make_reservation(PROP_A, self.rt, check_in or d(-3),
		                        check_out or d(1), status="Confirmed", **kw)

	def bd(self, prop=PROP_A):
		return str(frappe.db.get_value("Property", prop, "business_date"))

	def set_bd(self, value, prop=PROP_A):
		frappe.db.set_value("Property", prop, "business_date", value)

	def set_policy(self, basis, prop=PROP_A):
		frappe.db.set_value("Property", prop, "no_show_charge", basis)

	def room_nights(self, res, date=None):
		rows = charges(res.name, "Room")
		if date:
			rows = [r for r in rows if str(r.posting_date) == str(date)]
		return rows

	# business date -------------------------------------------------------

	def test_closes_only_the_current_business_date(self):
		res = self.in_house()
		out = folio_mod.run_night_audit(PROP_A)
		self.assertEqual(str(out["business_date"]), YESTERDAY)
		self.assertTrue(frappe.db.exists("Night Audit Run",
		                                 f"AUDIT-{YESTERDAY}-{PROP_A}"))
		self.assertEqual(len(self.room_nights(res, YESTERDAY)), 1)
		# nothing was posted for any other night
		self.assertEqual(len(self.room_nights(res)), 1)

	def test_explicit_current_date_is_accepted(self):
		out = folio_mod.run_night_audit(PROP_A, YESTERDAY)
		self.assertEqual(str(out["business_date"]), YESTERDAY)

	def test_explicit_non_current_date_is_refused(self):
		res = self.in_house()
		for wrong in (d(-2), TODAY):
			with self.assertRaises(frappe.ValidationError):
				folio_mod.run_night_audit(PROP_A, wrong)
		self.assertEqual(self.bd(), YESTERDAY)
		self.assertFalse(self.room_nights(res))
		self.assertFalse(frappe.db.exists("Night Audit Run",
		                                  {"property": PROP_A}))

	def test_business_date_ahead_of_today_is_refused(self):
		self.set_bd(d(1))
		res = self.in_house()
		with self.assertRaises(frappe.ValidationError):
			folio_mod.run_night_audit(PROP_A)
		self.assertEqual(self.bd(), d(1))
		self.assertFalse(self.room_nights(res))
		self.assertFalse(frappe.db.exists("Night Audit Run",
		                                  {"property": PROP_A}))

	def test_blank_business_date_is_seeded_from_today(self):
		self.set_bd(None)
		out = folio_mod.run_night_audit(PROP_A)
		self.assertEqual(str(out["business_date"]), TODAY)
		self.assertEqual(self.bd(), d(1))

	def test_business_date_advances_exactly_one_day(self):
		out = folio_mod.run_night_audit(PROP_A)
		self.assertEqual(str(out["next_business_date"]), TODAY)
		self.assertEqual(self.bd(), TODAY)

	def test_business_date_rolls_over_a_month_end(self):
		self.at("2031-03-01")
		self.set_bd("2031-02-28")
		out = folio_mod.run_night_audit(PROP_A)
		self.assertEqual(str(out["next_business_date"]), "2031-03-01")

	# idempotency ---------------------------------------------------------

	def test_retry_after_success_returns_already_ran(self):
		res = self.in_house()
		first = folio_mod.run_night_audit(PROP_A)
		# the run finished but the date roll did not stick (a crash, a
		# restore): the same business date comes round again
		self.set_bd(YESTERDAY)
		again = folio_mod.run_night_audit(PROP_A)
		self.assertTrue(again.get("already_ran"))
		self.assertEqual(again["audit"], first["audit"])
		self.assertEqual(len(self.room_nights(res)), 1)
		self.assertEqual(frappe.db.count("Night Audit Run",
		                                 {"property": PROP_A}), 1)
		# and the business date was not rolled a second time
		self.assertEqual(self.bd(), YESTERDAY)

	def test_retry_with_the_closed_date_does_not_post_twice(self):
		res = self.in_house()
		first = folio_mod.run_night_audit(PROP_A)
		# a retry naming the closed date answers already_ran (#197)
		again = folio_mod.run_night_audit(PROP_A, YESTERDAY)
		self.assertTrue(again.get("already_ran"))
		self.assertEqual(again["audit"], first["audit"])
		self.assertEqual(len(self.room_nights(res)), 1)
		self.assertEqual(self.bd(), TODAY)

	def test_post_room_night_is_idempotent_per_date(self):
		res = self.in_house()
		self.assertTrue(folio_mod.post_room_night(res, YESTERDAY))
		self.assertFalse(folio_mod.post_room_night(res, YESTERDAY))
		self.assertEqual(len(self.room_nights(res, YESTERDAY)), 1)

	# postings ------------------------------------------------------------

	def test_one_room_night_per_in_house_guest_at_the_nightly_rate(self):
		std = self.in_house(room=self.rooms[0])
		std2 = self.in_house(room=self.rooms[1])
		dlx = self.in_house(room=self.deluxe_room, room_type=self.rt_deluxe)
		out = folio_mod.run_night_audit(PROP_A)
		self.assertEqual(out["room_charges_posted"], 3)
		for res, rate in ((std, 1000), (std2, 1000), (dlx, 2500)):
			rows = self.room_nights(res)
			self.assertEqual(len(rows), 1, res.name)
			self.assertEqual(str(rows[0].posting_date), YESTERDAY)
			self.assertAlmostEqual(float(rows[0].amount), rate, places=2)
			self.assertEqual(rows[0].parent, guest_folio(res.name))
		self.assertAlmostEqual(out["amount_posted"], 4500, places=2)

	def test_room_night_uses_the_season_rate_for_that_night(self):
		frappe.get_doc({
			"doctype": "Season", "property": PROP_A, "season_name": "UT Peak",
			"start_date": d(-1), "end_date": d(-1),
			"adjustment_type": "Percent", "adjustment_value": 20,
		}).insert(ignore_permissions=True)
		res = self.in_house()
		out = folio_mod.run_night_audit(PROP_A)
		self.assertAlmostEqual(float(self.room_nights(res)[0].amount), 1200,
		                       places=2)
		self.assertAlmostEqual(out["amount_posted"], 1200, places=2)

	def test_room_night_ignores_a_season_on_another_night(self):
		frappe.get_doc({
			"doctype": "Season", "property": PROP_A, "season_name": "UT Later",
			"start_date": d(0), "end_date": d(5),
			"adjustment_type": "Percent", "adjustment_value": 50,
		}).insert(ignore_permissions=True)
		res = self.in_house()
		folio_mod.run_night_audit(PROP_A)
		self.assertAlmostEqual(float(self.room_nights(res)[0].amount), 1000,
		                       places=2)

	# rate plans: the folio's room night is the night the guest was quoted.
	# folio._nightly_room_rate once ignored reservation.rate_plan, so the
	# audit and checkout billed the rack rate on a discounted booking.

	def plan(self, name, kind, value):
		return frappe.get_doc({
			"doctype": "Rate Plan", "property": PROP_A, "rate_plan_name": name,
			"code": name.upper().replace(" ", "-"),
			"modifier_type": kind, "modifier_value": value,
		}).insert(ignore_permissions=True).name

	def test_room_night_honours_the_bookings_rate_plan(self):
		plan = self.plan("UT Advance Purchase", "Percent", -10)
		res = self.in_house(rate_plan=plan)
		nightly_booked = float(res.amount_before_tax) / res.nights
		self.assertAlmostEqual(nightly_booked, 900, places=2)
		folio_mod.run_night_audit(PROP_A)
		self.assertAlmostEqual(float(self.room_nights(res)[0].amount), 900,
		                       places=2)

	def test_room_nights_equal_the_quote_night_by_night(self):
		"""Season on one night + a -10% plan: every posted night equals
		the quote's night under the same plan, and the stay sums to it."""
		from kamra.pricing import quote
		frappe.get_doc({
			"doctype": "Season", "property": PROP_A, "season_name": "UT Peak",
			"start_date": d(-2), "end_date": d(-2),
			"adjustment_type": "Percent", "adjustment_value": 20,
		}).insert(ignore_permissions=True)
		plan = self.plan("UT Member", "Percent", -10)
		res = self.in_house(check_in=d(-3), check_out=d(-1), rate_plan=plan)
		posted = folio_mod.post_remaining_nights(res)
		self.assertEqual(posted, 2)
		q = quote(PROP_A, self.rt, d(-3), d(-1), 2, 0, rate_plan=plan)
		rows = sorted(self.room_nights(res), key=lambda r: str(r.posting_date))
		# 1000 then 1200 (season), each 10% off
		self.assertEqual([round(float(r.amount), 2) for r in rows], [900, 1080])
		self.assertAlmostEqual(sum(float(r.amount) for r in rows),
		                       q["room_total"], places=2)
		self.assertAlmostEqual(q["room_total"], float(res.amount_before_tax),
		                       places=2)

	def test_amount_rate_plan_is_spread_over_the_stay(self):
		# the quote adds an Amount plan to the stay total once, so each night
		# carries its share and the nights sum to what was quoted
		plan = self.plan("UT Flat Off", "Amount", -400)
		res = self.in_house(check_in=d(-4), check_out=d(0), rate_plan=plan)
		self.assertAlmostEqual(float(res.amount_before_tax), 3600, places=2)
		folio_mod.post_remaining_nights(res)
		rows = self.room_nights(res)
		self.assertEqual(len(rows), 4)
		for r in rows:
			self.assertAlmostEqual(float(r.amount), 900, places=2)

	def test_rate_plan_applies_on_top_of_small_group_rate(self):
		rt = make_room_type(PROP_A, "SGV", base_price=8000,
		                    small_group_max_adults=4,
		                    small_group_price_per_adult=1500)
		room = make_room(PROP_A, rt, "301")
		plan = self.plan("UT SG Plan", "Percent", -10)
		res = self.in_house(room=room, room_type=rt, rate_plan=plan)
		folio_mod.run_night_audit(PROP_A)
		# 2 adults x 1500 per head, then 10% off
		self.assertAlmostEqual(float(self.room_nights(res)[0].amount), 2700,
		                       places=2)

	def test_no_plan_bills_the_plan_free_rate(self):
		res = self.in_house()
		self.assertAlmostEqual(folio_mod._nightly_room_rate(res, YESTERDAY),
		                       1000, places=2)

	def test_missing_guest_folio_is_opened(self):
		res = self.in_house()
		frappe.delete_doc("Folio", guest_folio(res.name), force=True,
		                  ignore_permissions=True)
		self.assertIsNone(guest_folio(res.name))
		out = folio_mod.run_night_audit(PROP_A)
		self.assertEqual(out["folios_opened"], 1)
		folio = guest_folio(res.name)
		self.assertTrue(folio)
		self.assertEqual(self.room_nights(res)[0].parent, folio)

	def test_existing_folio_is_not_reopened(self):
		self.in_house()
		out = folio_mod.run_night_audit(PROP_A)
		self.assertEqual(out["folios_opened"], 0)

	def test_guest_past_departure_is_not_charged(self):
		# still Checked In, but the stay ended on the date being closed
		gone = self.in_house(check_in=d(-4), check_out=YESTERDAY)
		long_gone = self.in_house(room=self.rooms[1], check_in=d(-5),
		                          check_out=d(-3))
		out = folio_mod.run_night_audit(PROP_A)
		self.assertEqual(out["room_charges_posted"], 0)
		self.assertFalse(self.room_nights(gone))
		self.assertFalse(self.room_nights(long_gone))

	def test_future_arrival_and_checked_out_stays_are_not_charged(self):
		future = make_reservation(PROP_A, self.rt, d(0), d(2),
		                          status="Confirmed", room=self.rooms[2])
		out = folio_mod.run_night_audit(PROP_A)
		self.assertEqual(out["room_charges_posted"], 0)
		self.assertFalse(self.room_nights(future))
		self.assertEqual(frappe.db.get_value("Reservation", future.name,
		                                     "status"), "Confirmed")

	def test_folio_totals_include_the_posted_night(self):
		res = self.in_house()
		folio_mod.run_night_audit(PROP_A)
		folio = frappe.get_doc("Folio", guest_folio(res.name))
		self.assertAlmostEqual(float(folio.charges_total), 1000, places=2)
		self.assertAlmostEqual(
			float(folio.grand_total),
			float(folio.charges_total) + float(folio.tax_total), places=2)

	# no-shows ------------------------------------------------------------

	def test_no_show_is_flagged_without_a_fee_when_policy_is_none(self):
		self.set_policy("None")
		res = self.arrival()
		out = folio_mod.run_night_audit(PROP_A)
		self.assertEqual(out["no_shows_flagged"], 1)
		self.assertEqual(frappe.db.get_value("Reservation", res.name, "status"),
		                 "No Show")
		self.assertFalse(charges(res.name))
		self.assertAlmostEqual(out["amount_posted"], 0, places=2)

	def test_no_show_first_night_fee(self):
		self.set_policy("First Night")
		res = self.arrival(check_in=d(-3), check_out=d(1))
		out = folio_mod.run_night_audit(PROP_A)
		self.assertEqual(frappe.db.get_value("Reservation", res.name, "status"),
		                 "No Show")
		fee = [c for c in charges(res.name)
		       if c.description == "No-show charge (First Night)"]
		self.assertEqual(len(fee), 1)
		self.assertAlmostEqual(float(fee[0].amount), 1000, places=2)
		self.assertAlmostEqual(out["amount_posted"], 1000, places=2)

	def test_no_show_full_stay_fee(self):
		self.set_policy("Full Stay")
		res = self.arrival(check_in=d(-3), check_out=d(1))  # 4 nights
		out = folio_mod.run_night_audit(PROP_A)
		fee = [c for c in charges(res.name)
		       if c.description == "No-show charge (Full Stay)"]
		self.assertEqual(len(fee), 1)
		self.assertAlmostEqual(float(fee[0].amount),
		                       float(res.amount_before_tax), places=2)
		self.assertAlmostEqual(float(fee[0].amount), 4000, places=2)
		self.assertAlmostEqual(out["amount_posted"], 4000, places=2)

	def test_policy_fee_basis_none_is_zero(self):
		res = self.arrival()
		self.assertEqual(folio_mod.policy_fee(res, "None"), 0.0)
		self.assertEqual(folio_mod.post_policy_fee(res, "None", "x"), 0.0)
		self.assertIsNone(guest_folio(res.name))

	def test_post_policy_fee_is_not_posted_twice(self):
		res = self.arrival()
		label = "No-show charge (First Night)"
		self.assertAlmostEqual(
			folio_mod.post_policy_fee(res, "First Night", label), 1000, places=2)
		self.assertEqual(folio_mod.post_policy_fee(res, "First Night", label), 0.0)
		self.assertEqual(len([c for c in charges(res.name)
		                      if c.description == label]), 1)

	def test_cancelled_and_in_house_stays_are_not_no_shows(self):
		self.set_policy("First Night")
		cancelled = self.arrival()
		frappe.db.set_value("Reservation", cancelled.name, "status", "Cancelled")
		in_house = self.in_house()
		out = folio_mod.run_night_audit(PROP_A)
		self.assertEqual(out["no_shows_flagged"], 0)
		self.assertEqual(frappe.db.get_value("Reservation", cancelled.name,
		                                     "status"), "Cancelled")
		self.assertEqual(frappe.db.get_value("Reservation", in_house.name,
		                                     "status"), "Checked In")

	# every money posting uses the business date, not the calendar: the
	# fee of a no-show flagged by the audit closing YESTERDAY is dated
	# YESTERDAY, like the room nights of the same run.
	def test_no_show_fee_is_dated_on_the_closed_business_date(self):
		self.set_policy("First Night")
		res = self.arrival()
		folio_mod.run_night_audit(PROP_A)
		fee = [c for c in charges(res.name) if c.description.startswith("No-show")]
		self.assertEqual(str(fee[0].posting_date), YESTERDAY)

	def test_cancellation_fee_is_dated_on_the_current_business_date(self):
		# outside the audit the fee belongs to the open business day, which
		# lags the calendar until the audit rolls it
		res = self.arrival(check_in=d(3), check_out=d(5))
		folio_mod.post_policy_fee(res, "First Night", "Cancellation fee (First Night)")
		fee = [c for c in charges(res.name) if c.description.startswith("Cancellation")]
		self.assertEqual(str(fee[0].posting_date), YESTERDAY)

	def test_arrival_due_on_the_closed_date_is_a_no_show(self):
		# end of day for D marks D's unarrived, guaranteed arrivals (Opera)
		self.set_policy("First Night")
		due = self.arrival(check_in=YESTERDAY, check_out=d(1))
		later = self.arrival(check_in=TODAY, check_out=d(2))
		out = folio_mod.run_night_audit(PROP_A)
		self.assertEqual(out["no_shows_flagged"], 1)
		self.assertEqual(frappe.db.get_value("Reservation", due.name, "status"),
		                 "No Show")
		self.assertEqual(frappe.db.get_value("Reservation", later.name,
		                                     "status"), "Confirmed")
		fee = [c for c in charges(due.name) if c.description.startswith("No-show")]
		self.assertEqual(str(fee[0].posting_date), YESTERDAY)

	# waitlist ------------------------------------------------------------

	def test_waitlist_purged_two_days_after_departure_but_not_one(self):
		two = make_reservation(PROP_A, self.rt, d(-6), d(-3), status="Waitlist")
		one = make_reservation(PROP_A, self.rt, d(-6), d(-2), status="Waitlist")
		future = make_reservation(PROP_A, self.rt, d(1), d(3), status="Waitlist")
		folio_mod.run_night_audit(PROP_A)  # closes d(-1): cut-off is d(-3)
		self.assertFalse(frappe.db.exists("Reservation", two.name))
		self.assertTrue(frappe.db.exists("Reservation", one.name))
		self.assertTrue(frappe.db.exists("Reservation", future.name))
		log = frappe.db.get_value("Night Audit Run",
		                          f"AUDIT-{YESTERDAY}-{PROP_A}", "log")
		self.assertIn("purged 1 stale waitlist entries", log)

	def test_waitlist_of_another_property_is_left_alone(self):
		other = make_reservation(PROP_B, self.rt_b, d(-9), d(-5),
		                         status="Waitlist")
		folio_mod.run_night_audit(PROP_A)
		self.assertTrue(frappe.db.exists("Reservation", other.name))

	# properties ----------------------------------------------------------

	def test_two_properties_are_audited_independently(self):
		a = self.in_house()
		b = self.in_house(prop=PROP_B, room=self.room_b, room_type=self.rt_b)
		b_noshow = make_reservation(PROP_B, self.rt_b, d(-3), d(1),
		                            status="Confirmed")
		out_a = folio_mod.run_night_audit(PROP_A)
		self.assertEqual(out_a["audit"], f"AUDIT-{YESTERDAY}-{PROP_A}")
		# A's run touched nothing of B's
		self.assertFalse(self.room_nights(b))
		self.assertEqual(self.bd(PROP_B), YESTERDAY)
		self.assertEqual(frappe.db.get_value("Reservation", b_noshow.name,
		                                     "status"), "Confirmed")
		# and B's own audit of the same date is not mistaken for A's
		out_b = folio_mod.run_night_audit(PROP_B)
		self.assertFalse(out_b.get("already_ran"))
		self.assertEqual(out_b["audit"], f"AUDIT-{YESTERDAY}-{PROP_B}")
		self.assertEqual(out_b["room_charges_posted"], 1)
		self.assertEqual(out_b["no_shows_flagged"], 1)
		self.assertAlmostEqual(float(self.room_nights(b)[0].amount), 4000,
		                       places=2)
		self.assertEqual(len(self.room_nights(a)), 1)

	# the record ----------------------------------------------------------

	def test_night_audit_run_record_counts(self):
		self.set_policy("First Night")
		self.in_house(room=self.rooms[0])
		missing = self.in_house(room=self.deluxe_room, room_type=self.rt_deluxe)
		frappe.delete_doc("Folio", guest_folio(missing.name), force=True,
		                  ignore_permissions=True)
		self.arrival()
		out = folio_mod.run_night_audit(PROP_A)
		run = frappe.get_doc("Night Audit Run", out["audit"])
		self.assertEqual(run.property, PROP_A)
		self.assertEqual(str(run.business_date), YESTERDAY)
		self.assertEqual(run.status, "Completed")
		self.assertEqual(run.room_charges_posted, 2)
		self.assertEqual(run.folios_opened, 1)
		self.assertEqual(run.no_shows_flagged, 1)
		# 1000 + 2500 room nights, 1000 first-night no-show fee
		self.assertAlmostEqual(float(run.amount_posted), 4500, places=2)
		self.assertAlmostEqual(out["amount_posted"], 4500, places=2)
		self.assertIn("flagged no-show", run.log)
		self.assertIn("opened folio", run.log)

	def test_empty_day_writes_a_nothing_to_do_record(self):
		out = folio_mod.run_night_audit(PROP_A)
		run = frappe.get_doc("Night Audit Run", out["audit"])
		self.assertEqual((run.room_charges_posted, run.folios_opened,
		                  run.no_shows_flagged), (0, 0, 0))
		self.assertEqual(float(run.amount_posted), 0)
		self.assertEqual(run.log, "Nothing to do.")

	def test_audit_is_logged_to_the_action_log(self):
		out = folio_mod.run_night_audit(PROP_A)
		self.assertTrue(frappe.db.exists("Agent Action Log", {
			"action_type": "night_audit", "reference_name": out["audit"]}))

	# context -------------------------------------------------------------

	def test_runs_without_frappe_local_lang(self):
		self.in_house()
		frappe.local.lang = None
		out = folio_mod.run_night_audit(PROP_A)
		self.assertEqual(out["room_charges_posted"], 1)
		self.assertEqual(frappe.local.lang, "en")

	def test_runs_when_lang_attribute_is_absent(self):
		if hasattr(frappe.local, "lang"):
			del frappe.local.lang
		out = folio_mod.run_night_audit(PROP_A)
		self.assertIn("audit", out)


class BusinessDateTestCase(AuditTestCase):
	def setUp(self):
		super().setUp()
		self.at(TODAY)
		make_property(PROP_A)

	def test_blank_business_date_falls_back_to_today(self):
		self.assertEqual(bdm.get_business_date(PROP_A), TODAY)
		self.assertEqual(bdm.get_business_date(""), TODAY)
		# reading does not seed
		self.assertIsNone(frappe.db.get_value("Property", PROP_A, "business_date"))

	def test_ensure_seeds_once(self):
		self.assertEqual(bdm.ensure_business_date(PROP_A), TODAY)
		frappe.db.set_value("Property", PROP_A, "business_date", d(-5))
		self.assertEqual(bdm.ensure_business_date(PROP_A), d(-5))

	def test_advance_rolls_one_day_from_the_given_date(self):
		self.assertEqual(bdm.advance_business_date(PROP_A, d(-5)), d(-4))
		self.assertEqual(bdm.get_business_date(PROP_A), d(-4))
		self.assertEqual(bdm.advance_business_date(PROP_A), d(-3))


class NightlySchedulerTestCase(AuditTestCase):
	"""kamra.folio.nightly_audit_all_properties - the 15 minute tick, here
	at 04:00 on TODAY (after the default 03:00 run time)."""

	def setUp(self):
		super().setUp()
		self.at(TODAY)
		self._stack.enter_context(patch.object(
			folio_mod, "audit_clock",
			return_value=get_datetime(f"{TODAY} 04:00:00")))
		make_property(PROP_A, business_date=YESTERDAY)
		make_property(PROP_B, business_date=YESTERDAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")
		self.rt_b = make_room_type(PROP_B, "STD", base_price=4000)
		self.room_b = make_room(PROP_B, self.rt_b, "101")
		self.calls: list[str] = []
		self.fail_first_ut = False
		real = folio_mod.run_night_audit

		def only_ours(prop, business_date=None, **kw):
			# the cron walks every property on the site; audit only ours so
			# the test never posts into a developer's seeded hotels
			self.calls.append(prop)
			if prop not in (PROP_A, PROP_B):
				return {"skipped": True}
			if self.fail_first_ut:
				self.fail_first_ut = False
				raise RuntimeError("boom")
			return real(prop, business_date, **kw)

		self._stack.enter_context(
			patch.object(folio_mod, "run_night_audit", side_effect=only_ours))
		self.log_error = self._stack.enter_context(
			patch.object(frappe, "log_error"))
		self.alert = self._stack.enter_context(
			patch.object(na_mod, "alert_staff"))

	def bd(self, prop):
		return str(frappe.db.get_value("Property", prop, "business_date"))

	def audits(self, prop):
		return frappe.get_all("Night Audit Run", filters={"property": prop},
		                      pluck="business_date")

	def test_runs_when_business_date_is_yesterday(self):
		res = make_reservation(PROP_A, self.rt, d(-2), d(2),
		                       status="Checked In", room=self.room)
		folio_mod.nightly_audit_all_properties()
		self.assertEqual([str(x) for x in self.audits(PROP_A)], [YESTERDAY])
		self.assertEqual(self.bd(PROP_A), TODAY)
		self.assertEqual(len(charges(res.name, "Room")), 1)
		self.log_error.assert_not_called()

	# the 03:00 cron only closes a day that has ended: with the business
	# date already TODAY (closed by hand before midnight, or a second
	# worker), it leaves the property alone (#197).
	def test_skips_when_business_date_is_today(self):
		res = make_reservation(PROP_A, self.rt, d(-2), d(2),
		                       status="Checked In", room=self.room)
		frappe.db.set_value("Property", PROP_A, "business_date", TODAY)
		folio_mod.nightly_audit_all_properties()
		self.assertNotIn(PROP_A, self.calls)  # skipped before the audit
		self.assertEqual(self.audits(PROP_A), [])
		self.assertEqual(self.bd(PROP_A), TODAY)
		self.assertFalse(charges(res.name, "Room"))
		# B, still on YESTERDAY, was closed as usual
		self.assertEqual(self.bd(PROP_B), TODAY)

	def test_does_not_close_a_business_date_ahead_of_today(self):
		frappe.db.set_value("Property", PROP_A, "business_date", d(1))
		folio_mod.nightly_audit_all_properties()
		self.assertEqual(self.audits(PROP_A), [])
		self.assertEqual(self.bd(PROP_A), d(1))
		# B is unaffected by A's refusal
		self.assertEqual(self.bd(PROP_B), TODAY)

	def test_skips_disabled_properties(self):
		frappe.db.set_value("Property", PROP_B, "disabled", 1)
		folio_mod.nightly_audit_all_properties()
		self.assertIn(PROP_A, self.calls)
		self.assertNotIn(PROP_B, self.calls)
		self.assertEqual(self.bd(PROP_B), YESTERDAY)
		self.assertEqual(self.bd(PROP_A), TODAY)

	def test_one_property_failing_does_not_stop_the_others(self):
		self.fail_first_ut = True
		folio_mod.nightly_audit_all_properties()
		ours = [p for p in self.calls if p in (PROP_A, PROP_B)]
		self.assertEqual(sorted(ours), [PROP_A, PROP_B])
		failed, survived = ours[0], ours[1]
		self.assertEqual(self.bd(failed), YESTERDAY)
		self.assertEqual(self.bd(survived), TODAY)
		titles = [c.kwargs.get("title") for c in self.log_error.call_args_list]
		self.assertIn(f"Night audit failed: {failed}", titles)
		self.assertNotIn(f"Night audit failed: {survived}", titles)

	def test_runs_without_frappe_local_lang(self):
		frappe.local.lang = None
		folio_mod.nightly_audit_all_properties()
		self.assertEqual(self.bd(PROP_A), TODAY)
		self.log_error.assert_not_called()

	# ewa, Sep 2026: a completed run for the open date whose roll did not
	# stick. Every night answered already_ran and the date never moved.
	def test_recovers_a_stuck_business_date_and_closes_the_next_day(self):
		res = make_reservation(PROP_A, self.rt, d(-4), d(2),
		                       status="Checked In", room=self.room)
		frappe.db.set_value("Property", PROP_A, "business_date", d(-2))
		folio_mod.run_night_audit(PROP_A, d(-2))
		frappe.db.set_value("Property", PROP_A, "business_date", d(-2))
		folio_mod.nightly_audit_all_properties()
		self.assertEqual(sorted(str(x) for x in self.audits(PROP_A)),
		                 [d(-2), YESTERDAY])
		self.assertEqual(self.bd(PROP_A), TODAY)
		# one night for the recovered day, one for yesterday; nothing twice
		self.assertEqual(len(charges(res.name, "Room")), 2)

	def test_catches_up_a_few_missed_days_in_order(self):
		res = make_reservation(PROP_A, self.rt, d(-5), d(2),
		                       status="Checked In", room=self.room)
		frappe.db.set_value("Property", PROP_A, "business_date", d(-3))
		# one business date per tick (#203)
		for _ in range(4):
			folio_mod.nightly_audit_all_properties()
		self.assertEqual(sorted(str(x) for x in self.audits(PROP_A)),
		                 [d(-3), d(-2), YESTERDAY])
		self.assertEqual(self.bd(PROP_A), TODAY)
		self.assertEqual(len(charges(res.name, "Room")), 3)

	def test_alerts_instead_of_posting_weeks_behind(self):
		res = make_reservation(PROP_A, self.rt, d(-30), d(2),
		                       status="Checked In", room=self.room)
		frappe.db.set_value("Property", PROP_A, "business_date", d(-20))
		folio_mod.nightly_audit_all_properties()
		self.assertEqual(self.audits(PROP_A), [])
		self.assertEqual(self.bd(PROP_A), d(-20))
		self.assertFalse(charges(res.name, "Room"))
		alerted = [c.args[0] for c in self.alert.call_args_list]
		self.assertIn(PROP_A, alerted)


class NightAuditPermissionTestCase(AuditTestCase):
	"""kamra.api.run_night_audit: who may close the day."""

	ALLOWED: ClassVar[dict] = {
		"ut.audit.desk@test.local": ["Front Desk"],
		"ut.audit.finance@test.local": ["Finance"],
		"ut.audit.agent@test.local": ["Kamra Agent"],
		"ut.audit.admin@test.local": ["Hotel Admin"],
	}
	REFUSED: ClassVar[dict] = {
		"ut.audit.hk@test.local": ["Housekeeping"],
		"ut.audit.revenue@test.local": ["Revenue Manager"],
		"ut.audit.nobody@test.local": [],
	}

	def setUp(self):
		super().setUp()
		make_property(PROP_A, business_date=YESTERDAY)
		for email, roles in {**self.ALLOWED, **self.REFUSED}.items():
			ensure_user(email, roles)
		self.stub = self._stack.enter_context(patch.object(
			folio_mod, "run_night_audit", return_value={"audit": "stub"}))

	def test_front_office_and_finance_roles_may_run_it(self):
		from kamra import api
		for email in self.ALLOWED:
			frappe.set_user(email)  # nosemgrep: frappe-setuser -- acting as the persona
			self.assertEqual(api.run_night_audit(PROP_A), {"audit": "stub"},
			                 email)
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- restore
		self.assertEqual(self.stub.call_count, len(self.ALLOWED))
		self.stub.assert_called_with(PROP_A, None, acknowledge=None, note=None,
		                             mode="manual")

	def test_other_roles_are_refused(self):
		from kamra import api
		for email in self.REFUSED:
			frappe.set_user(email)  # nosemgrep: frappe-setuser -- acting as the persona
			with self.assertRaises(frappe.PermissionError, msg=email):
				api.run_night_audit(PROP_A)
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- restore
		self.stub.assert_not_called()

	def test_gate_is_introspectable(self):
		from kamra import api
		self.assertLessEqual({"Front Desk", "Finance", "Kamra Agent"},
		                     set(api.run_night_audit._kamra_roles))
		self.assertNotIn("Housekeeping", api.run_night_audit._kamra_roles)


def at_time(day: str, hhmm: str):
	"""A datetime on `day` at HH:MM, for pinning the audit's clock."""
	from datetime import datetime
	return datetime.strptime(f"{day} {hhmm}", "%Y-%m-%d %H:%M")


class NoShowPolicyTestCase(AuditTestCase):
	"""The per-property no-show policy (kamra.no_show) as the night audit
	applies it: timing, late-arrival protection, the OTA fee waiver, and the
	release of non-guaranteed arrivals."""

	def setUp(self):
		super().setUp()
		self.at(TODAY)
		make_property(PROP_A, business_date=YESTERDAY,
		              no_show_charge="First Night")
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.rooms = [make_room(PROP_A, self.rt, f"10{i}") for i in range(1, 6)]
		# several unassigned arrivals share a night in some tests
		frappe.db.set_value("Room Type", self.rt, "overbooking_pct", 100)
		# the audit closing YESTERDAY, run by hand late that evening
		self.clock(YESTERDAY, "23:00")

	def clock(self, day, hhmm):
		if getattr(self, "_clock", None):
			self._clock.stop()
		self._clock = patch.object(folio_mod, "audit_clock",
		                           return_value=at_time(day, hhmm))
		self._clock.start()
		self.addCleanup(lambda c=self._clock: c.stop() if c else None)

	def policy(self, **values):
		frappe.db.set_value("Property", PROP_A, values)

	def due(self, check_in=YESTERDAY, check_out=None, **kw):
		return make_reservation(PROP_A, self.rt, check_in,
		                        check_out or d(1), status="Confirmed", **kw)

	def status(self, res):
		return frappe.db.get_value("Reservation", res.name, "status")

	def fees(self, res):
		return [c for c in charges(res.name) if c.description.startswith("No-show")]

	# timing --------------------------------------------------------------

	def test_default_timing_no_shows_on_the_arrival_dates_audit(self):
		res = self.due()
		folio_mod.run_night_audit(PROP_A)
		self.assertEqual(self.status(res), "No Show")

	def test_one_day_later_keeps_the_arrival_due_in_for_a_day(self):
		self.policy(no_show_timing="One day later")
		today_due = self.due()
		older = self.due(check_in=d(-2))
		out = folio_mod.run_night_audit(PROP_A)
		self.assertEqual(self.status(today_due), "Confirmed")
		self.assertEqual(self.status(older), "No Show")
		self.assertEqual(out["no_shows_flagged"], 1)
		# the next day's audit catches it, fee dated on that closed date
		self.clock(TODAY, "23:00")
		self.at(d(1))
		folio_mod.run_night_audit(PROP_A)
		self.assertEqual(self.status(today_due), "No Show")
		self.assertEqual([str(f.posting_date) for f in self.fees(today_due)], [TODAY])

	# late arrivals ---------------------------------------------------------

	def test_eta_after_a_manual_evening_audit_is_held(self):
		res = self.due(eta="01:00")  # lands at 01:00 the next morning
		out = folio_mod.run_night_audit(PROP_A)
		self.assertEqual(self.status(res), "Confirmed")
		self.assertEqual(out["no_shows_flagged"], 0)
		self.assertEqual(out["late_arrivals_held"], 1)
		self.assertEqual(out["held_late_arrivals"][0]["reservation"], res.name)
		self.assertFalse(self.fees(res))
		run = frappe.get_doc("Night Audit Run", out["audit"])
		self.assertEqual(run.late_arrivals_held, 1)
		self.assertIn(f"held late arrival: {res.name}", run.log)

	def test_scheduled_3am_run_after_a_1am_eta_no_shows(self):
		res = self.due(eta="01:00")
		self.clock(TODAY, "03:00")
		out = folio_mod.run_night_audit(PROP_A)
		self.assertEqual(self.status(res), "No Show")
		self.assertEqual(out["late_arrivals_held"], 0)
		self.assertEqual(len(self.fees(res)), 1)

	def test_evening_eta_before_and_after_the_run(self):
		later = self.due(eta="11:30 pm")
		earlier = self.due(eta="21:00")
		folio_mod.run_night_audit(PROP_A)  # runs at 23:00
		self.assertEqual(self.status(later), "Confirmed")
		self.assertEqual(self.status(earlier), "No Show")

	def test_planned_arrival_time_counts_as_an_eta(self):
		res = self.due(planned_check_in_time="23:45")
		folio_mod.run_night_audit(PROP_A)
		self.assertEqual(self.status(res), "Confirmed")

	def test_late_arrival_flag_holds_without_an_eta(self):
		res = self.due(late_arrival=1)
		self.clock(TODAY, "03:00")
		out = folio_mod.run_night_audit(PROP_A)
		self.assertEqual(self.status(res), "Confirmed")
		self.assertEqual(out["held_late_arrivals"][0]["reason"],
		                 "flagged late arrival")

	def test_held_arrival_is_no_showed_at_the_next_audit(self):
		res = self.due(late_arrival=1)
		folio_mod.run_night_audit(PROP_A)
		self.assertEqual(self.status(res), "Confirmed")
		self.clock(d(1), "03:00")
		self.at(d(1))
		out = folio_mod.run_night_audit(PROP_A)  # closes TODAY
		self.assertEqual(self.status(res), "No Show")
		self.assertEqual(out["late_arrivals_held"], 0)
		self.assertEqual([str(f.posting_date) for f in self.fees(res)], [TODAY])

	def test_protection_off_no_shows_a_late_eta(self):
		self.policy(protect_late_arrivals=0)
		res = self.due(eta="01:00", late_arrival=1)
		out = folio_mod.run_night_audit(PROP_A)
		self.assertEqual(self.status(res), "No Show")
		self.assertEqual(out["late_arrivals_held"], 0)

	def test_protection_covers_only_arrivals_due_on_the_closed_date(self):
		res = self.due(check_in=d(-3), late_arrival=1)
		folio_mod.run_night_audit(PROP_A)
		self.assertEqual(self.status(res), "No Show")

	def test_eta_parsing(self):
		from datetime import time

		from kamra.no_show import parse_eta
		self.assertEqual(parse_eta("14:30"), time(14, 30))
		self.assertEqual(parse_eta("1 am"), time(1, 0))
		self.assertEqual(parse_eta("9.45pm"), time(21, 45))
		self.assertEqual(parse_eta("12 am"), time(0, 0))
		self.assertEqual(parse_eta("midnight"), time(0, 0))
		self.assertEqual(parse_eta("late night"), "late")
		self.assertIsNone(parse_eta(""))
		self.assertIsNone(parse_eta("not sure"))

	# OTA fee waiver --------------------------------------------------------

	def test_ota_no_show_is_flagged_without_a_fee(self):
		res = self.due(check_in=d(-2), source="OTA", channel="Booking.com")
		direct = self.due(check_in=d(-2))
		out = folio_mod.run_night_audit(PROP_A)
		self.assertEqual(self.status(res), "No Show")
		self.assertFalse(self.fees(res))
		self.assertEqual(len(self.fees(direct)), 1)
		self.assertEqual(out["no_show_fees_waived"], 1)
		self.assertAlmostEqual(out["amount_posted"], 1000, places=2)
		run = frappe.get_doc("Night Audit Run", out["audit"])
		self.assertIn(f"no-show fee waived for {res.name}", run.log)
		self.assertEqual(run.no_show_fees_waived, 1)

	def test_a_channel_alone_marks_an_ota_booking(self):
		res = self.due(check_in=d(-2), channel="Agoda")
		folio_mod.run_night_audit(PROP_A)
		self.assertFalse(self.fees(res))

	def test_waiver_off_charges_the_ota_no_show(self):
		self.policy(waive_no_show_fee_for_ota=0)
		res = self.due(check_in=d(-2), source="OTA", channel="Booking.com")
		out = folio_mod.run_night_audit(PROP_A)
		self.assertEqual(len(self.fees(res)), 1)
		self.assertEqual(out["no_show_fees_waived"], 0)

	# release of non-guaranteed arrivals -----------------------------------

	def release(self, hhmm, day=TODAY):
		from kamra.no_show import release_for_property
		return release_for_property(PROP_A, now=at_time(day, hhmm))

	def test_release_time_blank_is_off(self):
		res = self.due(check_in=TODAY, check_out=d(2))
		self.assertEqual(self.release("23:59"), [])
		self.assertEqual(self.status(res), "Confirmed")

	def test_non_guaranteed_arrival_is_released_after_the_time(self):
		self.policy(non_guaranteed_release_time="18:00")
		res = self.due(check_in=TODAY, check_out=d(2))
		self.assertEqual(self.release("17:45"), [])
		self.assertEqual(self.status(res), "Confirmed")
		self.assertEqual(self.release("18:00"), [res.name])
		doc = frappe.get_doc("Reservation", res.name)
		self.assertEqual(doc.status, "Cancelled")
		self.assertEqual(float(doc.cancellation_fee or 0), 0)
		self.assertIn("Non-guaranteed", doc.cancellation_note)
		self.assertFalse(charges(res.name))
		self.assertTrue(frappe.db.exists("Agent Action Log", {
			"action_type": "non_guaranteed_release", "reference_name": res.name}))
		# idempotent: nothing left to release
		self.assertEqual(self.release("18:15"), [])

	def test_guaranteed_arrivals_are_kept(self):
		self.policy(non_guaranteed_release_time="18:00")
		paid = self.due(check_in=TODAY, check_out=d(2), advance_paid=500)
		ota = self.due(check_in=TODAY, check_out=d(2), source="OTA")
		corporate = self.due(check_in=TODAY, check_out=d(2),
		                     booking_type="Corporate")
		late = self.due(check_in=TODAY, check_out=d(2), late_arrival=1)
		deposit = self.due(check_in=TODAY, check_out=d(2))
		folio = frappe.get_doc("Folio", folio_mod.open_folio(deposit))
		folio.append("payments", {"amount": 300, "mode": "Cash",
		                          "posting_date": TODAY})
		folio.save(ignore_permissions=True)
		other_day = self.due(check_in=d(1), check_out=d(2))
		self.assertEqual(self.release("19:00"), [])
		for res in (paid, ota, corporate, late, deposit, other_day):
			self.assertEqual(self.status(res), "Confirmed", res.name)

	def test_booking_made_after_the_release_time_is_kept(self):
		self.policy(non_guaranteed_release_time="18:00")
		res = self.due(check_in=TODAY, check_out=d(2))
		frappe.db.set_value("Reservation", res.name, "creation",
		                    f"{TODAY} 18:30:00", update_modified=False)
		self.assertEqual(self.release("19:00"), [])
		self.assertEqual(self.status(res), "Confirmed")


class RateLockTestCase(AuditTestCase):
	"""A booking bills the nightly rates confirmed when it was made
	(Reservation Night Rate): later seasons, rate changes or a drop in
	demand never re-price it; an amendment re-quotes only once the new
	price is confirmed."""

	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY)
		make_property(PROP_A, business_date=YESTERDAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.rt_deluxe = make_room_type(PROP_A, "DLX", base_price=2500)
		self.rooms = [make_room(PROP_A, self.rt, f"10{i}") for i in range(1, 5)]
		self.deluxe_room = make_room(PROP_A, self.rt_deluxe, "201")

	def in_house(self, **kw):
		return make_reservation(PROP_A, self.rt, d(-3), d(2),
		                        status="Checked In", room=self.rooms[0], **kw)

	def season(self, start, end, pct):
		return frappe.get_doc({
			"doctype": "Season", "property": PROP_A,
			"season_name": f"UT {start} {pct}", "start_date": start,
			"end_date": end, "adjustment_type": "Percent",
			"adjustment_value": pct,
		}).insert(ignore_permissions=True)

	def night(self, res, date):
		rows = [r for r in charges(res.name, "Room") if str(r.posting_date) == str(date)]
		return float(rows[0].amount)

	def test_booking_locks_one_rate_per_night(self):
		res = self.in_house()
		self.assertEqual([str(r.stay_date) for r in res.night_rates],
		                 [d(-3), d(-2), d(-1), d(0), d(1)])
		self.assertTrue(all(float(r.rate) == 1000 for r in res.night_rates))
		self.assertTrue(res.rate_lock_key)

	def test_season_added_after_booking_does_not_change_the_bill(self):
		res = self.in_house()
		amount = float(res.amount_after_tax)
		self.season(d(-1), d(-1), 50)
		folio_mod.run_night_audit(PROP_A)
		self.assertAlmostEqual(self.night(res, YESTERDAY), 1000, places=2)
		# an unrelated save keeps the confirmed price too
		doc = frappe.get_doc("Reservation", res.name)
		doc.special_requests = "Extra pillows"
		doc.save(ignore_permissions=True)
		self.assertAlmostEqual(float(doc.amount_after_tax), amount, places=2)

	def test_demand_premium_is_billed_after_occupancy_drops(self):
		hurdle = frappe.get_doc({
			"doctype": "Hurdle Rate", "property": PROP_A, "room_type": self.rt,
			"occupancy_from": 0, "premium_pct": 20,
		}).insert(ignore_permissions=True)
		res = self.in_house()
		self.assertAlmostEqual(float(res.night_rates[0].rate), 1200, places=2)
		self.assertEqual(float(res.night_rates[0].demand_premium_pct), 20)
		frappe.db.set_value("Hurdle Rate", hurdle.name, "disabled", 1)
		folio_mod.run_night_audit(PROP_A)
		self.assertAlmostEqual(self.night(res, YESTERDAY), 1200, places=2)

	def test_stay_without_locked_rates_falls_back_to_pricing_now(self):
		res = self.in_house()
		frappe.db.delete("Reservation Night Rate", {"parent": res.name})
		self.season(d(-1), d(-1), 50)
		folio_mod.run_night_audit(PROP_A)
		self.assertAlmostEqual(self.night(res, YESTERDAY), 1500, places=2)

	def test_no_show_first_night_fee_uses_the_locked_rate(self):
		frappe.db.set_value("Property", PROP_A, "no_show_charge", "First Night")
		res = make_reservation(PROP_A, self.rt, d(-1), d(1))
		self.season(d(-1), d(-1), 50)
		folio_mod.run_night_audit(PROP_A)
		fee = [c for c in charges(res.name) if c.description.startswith("No-show")]
		self.assertAlmostEqual(float(fee[0].amount), 1000, places=2)

	def test_amend_stay_needs_the_new_price_confirmed(self):
		from kamra import api
		res = make_reservation(PROP_A, self.rt, d(5), d(7), room=self.rooms[1])
		self.season(d(7), d(7), 50)
		pv = api.amend_stay_preview(res.name, d(5), d(8))
		self.assertTrue(pv["needs_confirmation"])
		self.assertEqual([n["rate"] for n in pv["nights"]], [1000, 1000, 1500])
		with self.assertRaises(api.PriceConfirmationRequired):
			api.amend_stay(res.name, d(5), d(8))
		doc = frappe.get_doc("Reservation", res.name)
		self.assertEqual(str(doc.check_out_date), d(7))
		self.assertEqual(len(doc.night_rates), 2)
		out = api.amend_stay(res.name, d(5), d(8), confirm_price=1)
		self.assertAlmostEqual(float(out["amount_after_tax"]), pv["new_amount"], places=2)
		doc = frappe.get_doc("Reservation", res.name)
		self.assertEqual([float(r.rate) for r in doc.night_rates], [1000, 1000, 1500])

	def test_amend_with_an_unchanged_total_needs_no_confirmation(self):
		from kamra import api
		res = make_reservation(PROP_A, self.rt, d(5), d(7), room=self.rooms[1])
		out = api.amend_stay(res.name, d(6), d(8))
		self.assertAlmostEqual(float(out["amount_after_tax"]),
		                       float(res.amount_after_tax), places=2)

	def test_same_type_move_keeps_the_locked_rates(self):
		from kamra import api
		res = make_reservation(PROP_A, self.rt, d(5), d(7), room=self.rooms[1])
		self.season(d(5), d(6), 50)
		pv = api.room_move_preview(res.name, self.rooms[2])
		self.assertFalse(pv["needs_confirmation"])
		api.move_reservation(res.name, self.rooms[2])
		doc = frappe.get_doc("Reservation", res.name)
		self.assertEqual(doc.room, self.rooms[2])
		self.assertEqual([float(r.rate) for r in doc.night_rates], [1000, 1000])

	def test_upgrade_move_needs_the_new_price_confirmed(self):
		from kamra import api
		res = make_reservation(PROP_A, self.rt, d(5), d(7), room=self.rooms[1])
		pv = api.room_move_preview(res.name, self.deluxe_room)
		self.assertTrue(pv["needs_confirmation"])
		with self.assertRaises(api.PriceConfirmationRequired):
			api.move_reservation(res.name, self.deluxe_room)
		api.move_reservation(res.name, self.deluxe_room, confirm_price=1)
		doc = frappe.get_doc("Reservation", res.name)
		self.assertEqual(doc.room_type, self.rt_deluxe)
		self.assertEqual([float(r.rate) for r in doc.night_rates], [2500, 2500])
		self.assertAlmostEqual(float(doc.amount_after_tax), pv["new_amount"], places=2)

	def test_upgrade_move_can_keep_the_price_or_take_an_agreed_rate(self):
		from kamra import api
		res = make_reservation(PROP_A, self.rt, d(5), d(7), room=self.rooms[1])
		amount = float(res.amount_after_tax)
		# keep what the guest pays
		self.assertFalse(api.room_move_preview(
			res.name, self.deluxe_room, rate_mode="source")["needs_confirmation"])
		api.move_reservation(res.name, self.deluxe_room, rate_mode="source")
		doc = frappe.get_doc("Reservation", res.name)
		self.assertEqual(doc.room_type, self.rt_deluxe)
		self.assertEqual([float(r.rate) for r in doc.night_rates], [1000, 1000])
		self.assertAlmostEqual(float(doc.amount_after_tax), amount, places=2)
		# a rate the desk agreed, once confirmed
		api.move_reservation(res.name, self.rooms[2], confirm_price=1,
		                     rate_mode="custom", agreed_rate=1800)
		doc = frappe.get_doc("Reservation", res.name)
		self.assertEqual([float(r.rate) for r in doc.night_rates], [1800, 1800])
		# Front Desk alone may not set a rate
		ensure_user("ut.rate.desk@test.local", ["Front Desk"])
		frappe.set_user("ut.rate.desk@test.local")  # nosemgrep: frappe-setuser -- acting as the persona
		try:
			with self.assertRaises(frappe.PermissionError):
				api.room_move_preview(res.name, self.rooms[3],
				                      rate_mode="custom", agreed_rate=900)
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- restore

	def test_backfill_locks_old_bookings_once(self):
		from kamra.patches.v40 import lock_confirmed_night_rates as patch_mod
		hurdle = frappe.get_doc({
			"doctype": "Hurdle Rate", "property": PROP_A, "room_type": self.rt,
			"occupancy_from": 0, "premium_pct": 20,
		}).insert(ignore_permissions=True)
		quoted = make_reservation(PROP_A, self.rt, d(5), d(7), room=self.rooms[1])
		plain = make_reservation(PROP_A, self.rt, d(5), d(7), room=self.rooms[2])
		for res in (quoted, plain):
			frappe.db.delete("Reservation Night Rate", {"parent": res.name})
			frappe.db.set_value("Reservation", res.name, "rate_lock_key", None)
		# a booking from before quote snapshots: priced the way the folio
		# bills it today (no demand premium in that path)
		frappe.db.set_value("Reservation", plain.name, "quote_snapshot", None)
		frappe.db.set_value("Hurdle Rate", hurdle.name, "disabled", 1)
		patch_mod.lock(frappe.get_doc("Reservation", quoted.name))
		patch_mod.lock(frappe.get_doc("Reservation", plain.name))
		q = frappe.get_doc("Reservation", quoted.name)
		self.assertEqual([float(r.rate) for r in q.night_rates], [1200, 1200])
		self.assertTrue(q.rate_lock_key)
		p = frappe.get_doc("Reservation", plain.name)
		self.assertEqual([float(r.rate) for r in p.night_rates], [1000, 1000])
		# idempotent
		patch_mod.lock(frappe.get_doc("Reservation", quoted.name))
		self.assertEqual(frappe.db.count("Reservation Night Rate",
		                                 {"parent": quoted.name}), 2)
		# and the lock holds on the next save
		q.special_requests = "late"
		q.save(ignore_permissions=True)
		self.assertEqual([float(r.rate) for r in q.night_rates], [1200, 1200])

	def test_channel_booking_locks_the_channels_nightly_prices(self):
		from kamra.channel_manager import lock_channel_rates
		doc = frappe.get_doc({
			"doctype": "Reservation", "property": PROP_A, "room_type": self.rt,
			"guest": frappe.get_doc({"doctype": "Guest", "first_name": "UT OTA"})
			         .insert(ignore_permissions=True).name,
			"check_in_date": d(5), "check_out_date": d(7), "adults": 2,
			"source": "OTA", "channel": "Booking.com", "auto_price": 0,
			"amount_after_tax": 3000,
		})
		lock_channel_rates(doc, 3000, [{"date": d(5), "amount": 1000},
		                               {"date": d(6), "amount": 2000}])
		doc.insert(ignore_permissions=True)
		# Fixed tax mode on the test property: whatever its rate, the nights
		# carry the channel's 1:2 split and add back up to the OTA total
		gross = [float(r.rate) * (1 + float(r.gst_rate) / 100) for r in doc.night_rates]
		self.assertAlmostEqual(sum(gross), 3000, delta=0.05)
		self.assertAlmostEqual(gross[1] / gross[0], 2, places=2)


class NightAuditChecklistTestCase(AuditTestCase):
	"""kamra.night_audit: the pre-check checklist, blocker acknowledgement,
	the scheduled run's hold-or-report setting, the saved audit pack and
	the End of Day wizard."""

	def setUp(self):
		super().setUp()
		self.at(TODAY)
		make_property(PROP_A, business_date=YESTERDAY,
		              no_show_charge="First Night")
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.rooms = [make_room(PROP_A, self.rt, f"10{i}") for i in range(1, 6)]
		frappe.db.set_value("Room Type", self.rt, "overbooking_pct", 100)
		for r in self.rooms:
			frappe.db.set_value("Room", r, {"occupancy_status": "Vacant",
			                                "housekeeping_status": "Clean"})
		self._stack.enter_context(patch.object(
			folio_mod, "audit_clock", return_value=at_time(YESTERDAY, "23:00")))
		self.alerts = self._stack.enter_context(
			patch("kamra.night_audit.alert_staff"))
		from kamra import settings
		settings.clear_cache(PROP_A)
		self.addCleanup(settings.clear_cache, PROP_A)

	# helpers -------------------------------------------------------------

	def setting(self, key, value):
		import json as _json

		from kamra import settings
		name = frappe.db.get_value("Property Setting",
		                           {"property": PROP_A, "setting_key": key})
		if name:
			frappe.db.set_value("Property Setting", name, "value", _json.dumps(value))
		else:
			frappe.get_doc({"doctype": "Property Setting", "property": PROP_A,
			                "setting_key": key, "value": _json.dumps(value)}
			               ).insert(ignore_permissions=True)
		settings.clear_cache(PROP_A)

	def checks(self):
		from kamra import night_audit
		return {c["key"]: c for c in
		        night_audit.night_audit_precheck(PROP_A)["checks"]}

	def in_house(self, room=0, check_in=None, check_out=None, **kw):
		return make_reservation(PROP_A, self.rt, check_in or d(-3),
		                        check_out or d(2), status="Checked In",
		                        room=self.rooms[room], **kw)

	def open_till(self):
		from kamra import cashier
		return cashier.open_session(PROP_A, opening_float=500)["name"]

	def outlet(self):
		outlet = frappe.db.get_value("POS Outlet", {"property": PROP_A,
		                                            "outlet_name": "UT Bar"})
		if not outlet:
			outlet = frappe.get_doc({
				"doctype": "POS Outlet", "property": PROP_A,
				"outlet_name": "UT Bar", "outlet_type": "Restaurant",
				"gst_rate": 5}).insert(ignore_permissions=True).name
		item = frappe.get_doc({
			"doctype": "Menu Item", "property": PROP_A, "outlet": outlet,
			"item_name": "UT Soup", "price": 300, "available": 1,
		}).insert(ignore_permissions=True).name
		return outlet, item

	def pos_order(self, **kw):
		outlet, item = self.outlet()
		return frappe.get_doc({
			"doctype": "POS Order", "property": PROP_A, "outlet": outlet,
			"status": "Placed", "order_type": "Dine In", "table_no": "T1",
			"items": [{"menu_item": item, "item_name": "UT Soup", "qty": 1,
			           "rate": 300}], **kw,
		}).insert(ignore_permissions=True)

	def run_manual(self, **kw):
		from kamra import api
		return api.run_night_audit(PROP_A, **kw)

	# the checks ----------------------------------------------------------

	def test_a_quiet_day_has_no_blockers_and_runs(self):
		from kamra import night_audit
		out = night_audit.night_audit_precheck(PROP_A)
		self.assertEqual(out["business_date"], YESTERDAY)
		self.assertTrue(out["can_run"])
		self.assertEqual(out["blockers"], [])
		self.assertEqual([c["key"] for c in out["checks"]], list(night_audit.ORDER))
		for c in out["checks"]:
			self.assertIn(c["severity"], ("block", "warn", "info"))
			self.assertTrue(c["action"])
		run = self.run_manual()
		self.assertEqual(run["status"], "Completed")
		self.assertTrue(run["has_pack"])

	def test_open_till_blocks_until_acknowledged_with_a_reason(self):
		session = self.open_till()
		c = self.checks()["open_tills"]
		self.assertEqual((c["severity"], c["count"]), ("block", 1))
		self.assertEqual(c["items"][0]["session"], session)
		with self.assertRaises(frappe.ValidationError):
			self.run_manual()
		with self.assertRaises(frappe.ValidationError):
			self.run_manual(acknowledge=["open_tills"], note="")
		self.assertEqual(self.bd(), YESTERDAY)
		out = self.run_manual(acknowledge='["open_tills"]',
		                      note="Bar till counted by the duty manager")
		self.assertEqual(out["acknowledged"], ["open_tills"])
		self.assertEqual(out["status"], "Completed with Warnings")
		run = frappe.get_doc("Night Audit Run", out["audit"])
		import json as _json
		acks = _json.loads(run.acknowledgements)
		self.assertEqual(acks[0]["key"], "open_tills")
		self.assertEqual(acks[0]["by"], "Administrator")
		self.assertTrue(acks[0]["at"])
		self.assertEqual(acks[0]["note"], "Bar till counted by the duty manager")
		self.assertEqual(run.exceptions, 1)
		self.assertEqual(run.run_trigger, "Manual")
		self.assertEqual(self.bd(), TODAY)

	def bd(self):
		return str(frappe.db.get_value("Property", PROP_A, "business_date"))

	def test_closing_the_till_clears_the_blocker(self):
		from kamra import cashier
		session = self.open_till()
		cashier.close_session(session, counted_cash=500)
		self.assertEqual(self.checks()["open_tills"]["count"], 0)
		self.assertEqual(self.run_manual()["status"], "Completed")

	def test_a_blocking_check_can_be_made_a_warning(self):
		self.open_till()
		self.setting("na_block_open_tills", 0)
		c = self.checks()["open_tills"]
		self.assertEqual((c["severity"], c["count"]), ("warn", 1))
		self.assertEqual(self.run_manual()["status"], "Completed")

	def test_open_and_unsettled_pos_bills_block(self):
		order = self.pos_order()
		c = self.checks()["open_pos_bills"]
		self.assertEqual((c["severity"], c["count"]), ("block", 1))
		row = c["items"][0]
		self.assertEqual((row["bill_no"], row["outlet"], row["amount"]),
		                 (order.name, "UT Bar", 300))
		# nothing was sent to the kitchen: the captain can cancel it alone
		self.assertEqual(row["state"], "open, not sent to kitchen")
		with self.assertRaises(frappe.ValidationError):
			self.run_manual()

	def test_departure_still_in_house_blocks(self):
		res = self.in_house(check_in=d(-4), check_out=YESTERDAY)
		c = self.checks()["departures_due"]
		self.assertEqual((c["severity"], c["count"]), ("block", 1))
		self.assertEqual(c["items"][0]["reservation"], res.name)
		self.assertIn("nights", c["items"][0])
		self.setting("na_block_departures", 0)
		self.assertEqual(self.checks()["departures_due"]["severity"], "warn")

	def test_arrivals_show_what_the_no_show_policy_will_do(self):
		due = make_reservation(PROP_A, self.rt, YESTERDAY, d(1))
		ota = make_reservation(PROP_A, self.rt, YESTERDAY, d(1),
		                       source="OTA", channel="Booking.com")
		late = make_reservation(PROP_A, self.rt, YESTERDAY, d(1), late_arrival=1)
		c = self.checks()["arrivals_pending"]
		self.assertEqual(c["severity"], "warn")
		rows = {i["reservation"]: i for i in c["items"]}
		self.assertEqual((rows[due.name]["outcome"], rows[due.name]["fee"]),
		                 ("no_show", "charge"))
		self.assertGreater(rows[due.name]["fee_amount"], 0)
		self.assertEqual(rows[ota.name]["fee"], "waived")
		self.assertEqual(rows[late.name]["outcome"], "hold")
		frappe.db.set_value("Property", PROP_A, "no_show_timing", "One day later")
		rows = {i["reservation"]: i for i in self.checks()["arrivals_pending"]["items"]}
		self.assertEqual(rows[due.name]["outcome"], "defer")
		# the audit does what the checklist said
		frappe.db.set_value("Property", PROP_A, "no_show_timing",
		                    "At audit for arrival date")
		self.run_manual()
		self.assertEqual(frappe.db.get_value("Reservation", due.name, "status"), "No Show")
		self.assertEqual(frappe.db.get_value("Reservation", late.name, "status"), "Confirmed")

	def test_rate_variance_flags_a_room_night_off_the_booked_rate(self):
		from kamra.folio import post_room_night, save_folios
		res = self.in_house()
		post_room_night(res, YESTERDAY)
		self.assertEqual(self.checks()["rate_variance"]["count"], 0)
		other = self.in_house(room=1)
		folio = frappe.get_doc("Folio", guest_folio(other.name))
		folio.append("charges", {
			"posting_date": YESTERDAY, "charge_type": "Room",
			"reservation": other.name, "description": "Room manual", "qty": 1,
			"rate": 1600, "amount": 1600, "gst_rate": 0, "auto_posted": 0})
		save_folios({folio.name: folio})
		c = self.checks()["rate_variance"]
		self.assertEqual((c["severity"], c["count"]), ("warn", 1))
		row = c["items"][0]
		self.assertEqual(row["reservation"], other.name)
		self.assertTrue(row["manual"])
		self.assertAlmostEqual(row["difference"], row["posted"] - row["expected"])
		self.assertGreater(abs(row["difference"]), 1)

	def test_pos_bills_posted_to_rooms_are_listed_never_blocking(self):
		res = self.in_house()
		order = self.pos_order(room=res.room, reservation=res.name)
		order.status = "Delivered"
		order.save(ignore_permissions=True)
		c = self.checks()["pos_room_postings"]
		self.assertEqual((c["severity"], c["count"]), ("info", 1))
		row = c["items"][0]
		self.assertEqual((row["bill_no"], row["outlet"], row["room"],
		                  row["guest_name"]),
		                 (order.name, "UT Bar", "101", res.guest_name))
		self.assertFalse(row["room_mismatch"])
		self.assertEqual(self.checks()["open_pos_bills"]["count"], 0)

	def test_high_balance_threshold_and_off(self):
		from kamra.folio import post_room_night
		res = self.in_house()
		post_room_night(res, YESTERDAY)
		self.setting("na_high_balance_threshold", 500)
		c = self.checks()["high_balance"]
		self.assertEqual([i["reservation"] for i in c["items"]], [res.name])
		self.setting("na_high_balance_threshold", 0)
		c = self.checks()["high_balance"]
		self.assertEqual((c["count"], c["enabled"]), (0, False))

	def test_company_over_its_credit_limit(self):
		company = "UT Audit Corp"
		if not frappe.db.exists("Corporate Account", company):
			frappe.get_doc({"doctype": "Corporate Account", "company_name": company,
			                "credit_allowed": 1}).insert(ignore_permissions=True)
		acc = frappe.get_doc({"doctype": "City Ledger Account", "property": PROP_A,
		                      "company": company, "credit_limit": 100}
		                     ).insert(ignore_permissions=True)
		frappe.get_doc({"doctype": "City Ledger Entry", "account": acc.name,
		                "property": PROP_A, "posting_date": YESTERDAY,
		                "kind": "Invoice", "debit": 250}).insert(ignore_permissions=True)
		c = self.checks()["credit_limit"]
		self.assertEqual(c["count"], 1)
		row = c["items"][0]
		self.assertEqual((row["company"], row["exposure"], row["over_by"]),
		                 (company, 250, 150))

	def test_room_status_discrepancies_both_ways(self):
		res = self.in_house()
		frappe.db.set_value("Room", res.room, "occupancy_status", "Vacant")
		frappe.db.set_value("Room", self.rooms[3], "occupancy_status", "Occupied")
		c = self.checks()["room_status"]
		issues = {i["room"]: i["issue"] for i in c["items"]}
		self.assertIn("101", issues)
		self.assertIn("104", issues)
		self.assertIn("Vacant", issues["101"])
		self.assertIn("no guest", issues["104"])

	# scheduled run: hold or report ---------------------------------------

	def test_scheduled_run_reports_blockers_by_default(self):
		self.open_till()
		out = folio_mod.run_night_audit(PROP_A, mode="scheduled")
		self.assertEqual(out["status"], "Completed with Warnings")
		self.assertEqual(self.bd(), TODAY)
		run = frappe.get_doc("Night Audit Run", out["audit"])
		self.assertEqual(run.run_trigger, "Scheduled")
		self.assertIn("open_tills", run.acknowledgements)
		self.alerts.assert_not_called()

	def test_scheduled_run_holds_and_alerts_when_set(self):
		self.open_till()
		self.setting("na_auto_audit_with_blockers", "Hold and alert")
		out = folio_mod.run_night_audit(PROP_A, mode="scheduled")
		self.assertTrue(out["held"])
		self.assertEqual(self.bd(), YESTERDAY)
		self.assertFalse(frappe.db.exists("Night Audit Run", {"property": PROP_A}))
		self.assertTrue(frappe.db.exists("Agent Action Log", {
			"property": PROP_A, "action_type": "night_audit_held"}))
		# one in-app + email alert to Hotel Admin and Finance (no WhatsApp)
		self.alerts.assert_called_once()
		self.assertEqual(set(self.alerts.call_args.args[1]), {"Hotel Admin", "Finance"})
		from kamra import night_audit
		self.assertTrue(night_audit.night_audit_precheck(PROP_A)["held"])
		# nothing blocking: the scheduled run closes the day even on hold
		frappe.db.set_value("Cashier Session", {"property": PROP_A}, "status", "Closed")
		self.assertEqual(folio_mod.run_night_audit(PROP_A, mode="scheduled")["status"],
		                 "Completed")

	# the audit pack ------------------------------------------------------

	def test_the_pack_is_saved_with_every_section(self):
		from kamra import night_audit
		res = self.in_house()
		ns = make_reservation(PROP_A, self.rt, YESTERDAY, d(1))
		out = self.run_manual()
		pack = night_audit.night_audit_pack(out["audit"])
		self.assertTrue(pack["has_pack"])
		p = pack["pack"]
		for key in ("manager_flash", "revenue_by_transaction_code",
		            "ledger_balances", "statistics", "in_house", "departures",
		            "arrivals", "no_shows", "high_balance", "credit_limit",
		            "pos_room_postings", "rate_variance", "cashier_sessions",
		            "prechecks", "acknowledgements", "journal",
		            "deposit_ledger", "city_ledger", "cancellations", "reports"):
			self.assertIn(key, p, key)
		self.assertNotIn("errors", p)
		self.assertEqual(p["business_date"], YESTERDAY)
		self.assertEqual([r["reservation"] for r in p["in_house"]], [res.name])
		self.assertEqual(p["statistics"]["rooms_sold"], 1)
		self.assertEqual(p["no_shows"][0]["reservation"], ns.name)
		self.assertIn("fee posted", p["no_shows"][0]["outcome"])
		self.assertTrue(p["journal"]["lines"])
		self.assertEqual([c["key"] for c in p["prechecks"]],
		                 list(night_audit.ORDER))

	def test_a_run_without_a_pack_says_so(self):
		from kamra import night_audit
		frappe.get_doc({"doctype": "Night Audit Run", "property": PROP_A,
		                "business_date": d(-5), "status": "Completed"}
		               ).insert(ignore_permissions=True)
		name = f"AUDIT-{d(-5)}-{PROP_A}"
		out = night_audit.night_audit_pack(name)
		self.assertFalse(out["has_pack"])
		self.assertIsNone(out["pack"])
		self.assertTrue(out.get("can_rebuild"))
		self.assertIn("Rebuild", out["message"])
		rebuilt = night_audit.rebuild_audit_pack(name)
		self.assertTrue(rebuilt["has_pack"])
		self.assertIn("manager_flash", rebuilt["pack"])
		self.assertEqual(rebuilt["pack"].get("prechecks_source"), "live_rebuild")

	def test_stuck_business_date_surfaces_on_eod_and_recovers(self):
		from kamra import night_audit
		from kamra.business_date import get_business_date
		# Quiet day, run audit (rolls BD), then pin BD back to simulate a
		# restore / roll that did not stick.
		out = self.run_manual()
		closed = out["business_date"] if "business_date" in out else YESTERDAY
		frappe.db.set_value("Property", PROP_A, "business_date", closed)
		stuck = night_audit.stuck_business_date(PROP_A)
		self.assertIsNotNone(stuck)
		self.assertEqual(stuck["audit"], out["audit"])
		s = night_audit.eod_session(PROP_A)
		self.assertTrue(s["ran"])
		self.assertEqual(s["stuck_date"]["audit"], out["audit"])
		self.assertEqual(s["open_business_date"], closed)
		rows = {r["property"]: r for r in night_audit.eod_overview()}
		self.assertEqual(rows[PROP_A]["stuck_date"]["audit"], out["audit"])
		rec = night_audit.recover_stuck_business_date(PROP_A)
		self.assertEqual(rec["next_business_date"], TODAY)
		self.assertEqual(get_business_date(PROP_A), TODAY)
		self.assertIsNone(night_audit.stuck_business_date(PROP_A))
		cleared = night_audit.eod_session(PROP_A)
		self.assertIsNone(cleared.get("stuck_date"))

	# End of Day wizard ---------------------------------------------------

	def test_end_of_day_resumes_acknowledges_and_runs_from_the_draft(self):
		from kamra import night_audit
		self.open_till()
		s = night_audit.eod_session(PROP_A)
		self.assertEqual(s["status"], "Draft")
		self.assertEqual(s["current_step"], 1)
		steps = {x["key"]: x for x in s["steps"]}
		self.assertEqual(len(s["steps"]), 12)
		self.assertEqual(steps["cashiers"]["status"], "blocked")
		with self.assertRaises(frappe.ValidationError):
			night_audit.eod_progress(PROP_A, key="cashiers", status="done")
		night_audit.eod_progress(PROP_A, step=4, key="arrivals", status="done",
		                         notes="Heavy rain; lift 2 out of service")
		with self.assertRaises(frappe.ValidationError):
			night_audit.eod_acknowledge(PROP_A, "open_tills", "")
		with self.assertRaises(frappe.ValidationError):
			night_audit.eod_acknowledge(PROP_A, "departures_due", "nothing open")
		night_audit.eod_acknowledge(PROP_A, "open_tills", "Till 2 counted tomorrow")
		night_audit.eod_progress(PROP_A, key="cashiers", status="done")
		s = night_audit.eod_session(PROP_A)
		self.assertEqual(s["current_step"], 4)
		self.assertEqual(s["audit"], s["audit"])
		steps = {x["key"]: x["status"] for x in s["steps"]}
		self.assertEqual((steps["arrivals"], steps["cashiers"]), ("done", "done"))
		self.assertEqual(s["blockers"], [])
		draft = s["audit"]
		# the run takes the wizard's acknowledgement - no second reason
		out = self.run_manual()
		self.assertEqual(out["audit"], draft)
		run = frappe.get_doc("Night Audit Run", draft)
		self.assertEqual(run.status, "Completed with Warnings")
		self.assertEqual(run.auditor_notes, "Heavy rain; lift 2 out of service")
		pack = night_audit.night_audit_pack(draft)["pack"]
		self.assertEqual(pack["notes"], "Heavy rain; lift 2 out of service")
		self.assertEqual(pack["acknowledgements"][0]["note"], "Till 2 counted tomorrow")
		# the finished run reopens at its reports; history leaves drafts out
		done = night_audit.eod_session(PROP_A, audit=draft)
		self.assertTrue(done["ran"])
		self.assertGreaterEqual(done["current_step"], 11)
		names = [r["name"] for r in night_audit.night_audit_history(PROP_A)]
		self.assertEqual(names, [draft])

	def test_a_draft_is_not_a_closed_day(self):
		from kamra import night_audit
		night_audit.eod_session(PROP_A)
		self.assertFalse(night_audit.night_audit_precheck(PROP_A)["already_ran"])
		self.assertEqual(night_audit.night_audit_history(PROP_A), [])
		self.assertFalse(self.run_manual().get("already_ran"))

	def test_mark_no_show_applies_the_policy_now(self):
		from kamra import night_audit
		due = make_reservation(PROP_A, self.rt, YESTERDAY, d(1))
		ota = make_reservation(PROP_A, self.rt, YESTERDAY, d(1),
		                       source="OTA", channel="Agoda")
		out = night_audit.eod_mark_no_show(due.name)
		self.assertGreater(out["fee_amount"], 0)
		self.assertEqual(frappe.db.get_value("Reservation", due.name, "status"), "No Show")
		self.assertEqual(night_audit.eod_mark_no_show(ota.name)["fee"], "waived")
		future = make_reservation(PROP_A, self.rt, d(3), d(4))
		with self.assertRaises(frappe.ValidationError):
			night_audit.eod_mark_no_show(future.name)

	def test_overview_lists_the_property(self):
		from kamra import night_audit
		self.open_till()
		rows = {r["property"]: r for r in night_audit.eod_overview()}
		row = rows[PROP_A]
		self.assertEqual((row["business_date"], row["open_cashiers"], row["blockers"]),
		                 (YESTERDAY, 1, 1))

	def test_night_auditor_role_reaches_the_audit(self):
		from kamra import api, cashier, night_audit
		user = ensure_user("ut.audit.night@test.local", ["Night Auditor"])
		for fn in (api.run_night_audit, night_audit.night_audit_precheck,
		           night_audit.eod_session, night_audit.eod_acknowledge,
		           night_audit.night_audit_pack, night_audit.rebuild_audit_pack,
		           api.check_in, api.check_out, cashier.close_session,
		           api.get_folio):
			self.assertIn("Night Auditor", fn._kamra_roles, fn.__name__)
		# recover_stuck_business_date is Finance / Hotel Admin / Night Auditor
		self.assertIn("Night Auditor",
		              night_audit.recover_stuck_business_date._kamra_roles)
		frappe.set_user(user)  # nosemgrep: frappe-setuser -- acting as the persona
		out = night_audit.night_audit_precheck(PROP_A)
		self.assertEqual(out["business_date"], YESTERDAY)
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- restore
