"""Hourly / block day-use pricing, due-out by time, and overstay rules (#497)."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from unittest.mock import patch

import frappe

from kamra import api, day_use, folio as folio_mod
from kamra.pricing import quote
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
from kamra.tests.test_billing_approvals_split import set_setting


class DayUsePricingTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY)
		frappe.db.delete("Property Setting", {"property": PROP_A})
		set_setting(PROP_A, "day_use_overstay", "Next hour")
		self.rt = make_room_type(PROP_A, "STD", base_price=2400)
		self.room = make_room(PROP_A, self.rt, "201")
		frappe.db.delete("Rate Plan", {"property": PROP_A, "code": ("in", ["HRLY", "BLK"])})
		self.hourly = frappe.get_doc({
			"doctype": "Rate Plan", "property": PROP_A,
			"rate_plan_name": "Hourly Day Use", "code": "HRLY",
			"modifier_type": "Percent", "modifier_value": 0,
			"billing_basis": "Hourly", "hourly_rate": 200, "min_hours": 2,
		}).insert(ignore_permissions=True)
		self.block = frappe.get_doc({
			"doctype": "Rate Plan", "property": PROP_A,
			"rate_plan_name": "Block Day Use", "code": "BLK",
			"modifier_type": "Percent", "modifier_value": 0,
			"billing_basis": "Block", "hourly_rate": 200,
			"min_hours": 3, "block_hours": 3, "block_rate": 500,
		}).insert(ignore_permissions=True)

	def test_hourly_quote_uses_elapsed_hours_not_full_night(self):
		nightly = quote(PROP_A, self.rt, TODAY, TODAY, 2, 0)
		hourly = quote(PROP_A, self.rt, TODAY, TODAY, 2, 0,
		               rate_plan=self.hourly.name,
		               check_in_time="10:00", check_out_time="14:00")
		self.assertTrue(hourly["day_use"])
		self.assertEqual(hourly["day_use_billing"]["billing_basis"], "Hourly")
		self.assertEqual(hourly["day_use_billing"]["hours"], 4)
		# 4h × 200 = 800 vs one full night (~2400) — must be the hour total.
		self.assertAlmostEqual(hourly["room_total"], 800, places=0)
		self.assertLess(hourly["amount_after_tax"], nightly["amount_after_tax"])

	def test_block_quote_rounds_up_to_blocks(self):
		# 4 hours → 2 × 3h blocks at 500 = 1000
		q = quote(PROP_A, self.rt, TODAY, TODAY, 2, 0,
		          rate_plan=self.block.name,
		          check_in_time="09:00", check_out_time="13:00")
		self.assertEqual(q["day_use_billing"]["billing_basis"], "Block")
		self.assertEqual(q["day_use_billing"]["units"], 2)
		self.assertAlmostEqual(q["room_total"], 1000, places=0)

	def test_overnight_quote_unchanged_with_hourly_plan(self):
		from frappe.utils import add_days
		q = quote(PROP_A, self.rt, TODAY, add_days(TODAY, 2), 2, 0,
		          rate_plan=self.hourly.name,
		          check_in_time="14:00", check_out_time="11:00")
		self.assertFalse(q["day_use"])
		self.assertNotIn("day_use_billing", q)
		self.assertAlmostEqual(q["room_total"], 4800, places=0)

	def test_due_out_only_after_planned_etd(self):
		# a day use from the start: validate_dates refuses a same-day stay otherwise
		res = make_reservation(PROP_A, self.rt, TODAY, TODAY,
		                       status="Checked In", room=self.room, is_day_use=1)
		res.db_set("planned_check_out_time", "13:00:00")
		row = frappe.get_doc("Reservation", res.name)
		before = datetime.strptime(f"{TODAY} 12:00:00", "%Y-%m-%d %H:%M:%S")
		after = datetime.strptime(f"{TODAY} 13:00:00", "%Y-%m-%d %H:%M:%S")
		self.assertFalse(day_use.is_due_out(row, now=before))
		self.assertTrue(day_use.is_due_out(row, now=after))

	def test_room_board_due_out_respects_etd(self):
		# a day use from the start: validate_dates refuses a same-day stay otherwise
		res = make_reservation(PROP_A, self.rt, TODAY, TODAY,
		                       status="Checked In", room=self.room, is_day_use=1)
		res.db_set("planned_check_out_time", "23:30:00")
		with patch("kamra.day_use.now_datetime",
		           return_value=datetime.strptime(
			           f"{TODAY} 12:00:00", "%Y-%m-%d %H:%M:%S")):
			# is_due_out reads now from day_use; room_board calls it without now
			with patch("kamra.api.nowdate", return_value=TODAY):
				board = api.room_board(PROP_A)
		tile = next(x for x in board["rooms"] if x.name == self.room)
		# 12:00 < 23:30 → not due yet
		self.assertTrue(tile["day_use"])
		self.assertEqual(tile["etd"], "23:30")
		self.assertFalse(tile["due_out"])

	def test_room_board_shows_a_morning_etd_as_hh_mm(self):
		"""An 08:00 ETD is "08:00" on the board, not "8:00:" - which did not
		parse, so on the checkout day the whole board raised."""
		make_reservation(PROP_A, self.rt, TODAY, TODAY, status="Checked In",
		                 room=self.room, is_day_use=1, planned_check_out_time="08:00:00")
		for clock, due in (("07:00", False), ("09:00", True)):
			with self.subTest(clock=clock):
				with patch("kamra.day_use.now_datetime",
				           return_value=datetime.strptime(f"{TODAY} {clock}", "%Y-%m-%d %H:%M")), \
				     patch("kamra.api.nowdate", return_value=TODAY):
					board = api.room_board(PROP_A)
				tile = next(x for x in board["rooms"] if x.name == self.room)
				self.assertEqual((tile["etd"], tile["due_out"]), ("08:00", due))

	def test_a_morning_hourly_day_use_bills_its_hours(self):
		"""An 08:00-11:00 hourly stay. Read back from the database its start
		is a timedelta, and "8:00:" did not parse, so posting the stay (what
		check-out does) raised."""
		res = make_reservation(
			PROP_A, self.rt, TODAY, TODAY, status="Checked In", room=self.room,
			rate_plan=self.hourly.name, is_day_use=1, auto_price=1,
			planned_check_in_time="08:00:00", planned_check_out_time="11:00:00")
		row = frappe.get_doc("Reservation", res.name)
		at_etd = datetime.strptime(f"{TODAY} 11:00:00", "%Y-%m-%d %H:%M:%S")
		with patch("kamra.day_use.now_datetime", return_value=at_etd):
			self.assertEqual(day_use.reservation_slot_hours(row), (3.0, 3.0))
			folio_mod.post_remaining_nights(row)
		folio = frappe.get_doc("Folio", guest_folio(res.name))
		room = [c for c in folio.charges if c.charge_type == "Room"]
		self.assertEqual(len(room), 1)
		self.assertIn("day use · 3 h", room[0].description)

	def test_a_morning_block_day_use_bills_its_block(self):
		"""Same parser as the hourly stay: an 08:00 block start is a
		timedelta, and posting it (check-out) used to raise."""
		res = make_reservation(
			PROP_A, self.rt, TODAY, TODAY, status="Checked In", room=self.room,
			rate_plan=self.block.name, is_day_use=1, auto_price=1,
			planned_check_in_time="08:00:00", planned_check_out_time="11:00:00")
		row = frappe.get_doc("Reservation", res.name)
		at_etd = datetime.strptime(f"{TODAY} 11:00:00", "%Y-%m-%d %H:%M:%S")
		with patch("kamra.day_use.now_datetime", return_value=at_etd):
			self.assertEqual(day_use.reservation_slot_hours(row), (3.0, 3.0))
			folio_mod.post_remaining_nights(row)
		folio = frappe.get_doc("Folio", guest_folio(res.name))
		room = [c for c in folio.charges if c.charge_type == "Room"]
		self.assertEqual(len(room), 1)
		self.assertIn("day use · 1 × 3h", room[0].description)

	def _morning_changeover(self):
		"""The guest in the room leaves today at 10:00; the next one arrives at 08:00."""
		make_reservation(PROP_A, self.rt, d(-1), TODAY, status="Checked In", room=self.room,
		                 planned_check_out_time="10:00:00")
		make_reservation(PROP_A, self.rt, TODAY, d(1), room=self.room,
		                 planned_check_in_time="08:00:00")

	def test_tape_chart_flags_a_morning_arrival_before_the_departure(self):
		"""An 08:00 arrival in a room whose guest leaves at 10:00 is a
		changeover conflict: compared as text, "8:00:00" sorted after
		"10:00:00" and it went unflagged."""
		self._morning_changeover()
		chart = api.tape_chart(PROP_A, start_date=d(-1), days=3)
		conflict = next(c for c in chart["conflicts"] if c["room"] == self.room)
		self.assertEqual((conflict["eta"], conflict["etd"]), ("08:00", "10:00"))
		# the bars themselves used to keep the raw timedelta, and the screen
		# cuts that text to five characters ("8:00:")
		bars = next(r for r in chart["rooms"] if r.name == self.room).bookings
		incoming = next(b for b in bars if str(b.check_in_date) == TODAY)
		outgoing = next(b for b in bars
		                if str(b.check_out_date) == TODAY and b.name != incoming.name)
		self.assertEqual(incoming.planned_check_in_time, "08:00")
		self.assertEqual(outgoing.planned_check_out_time, "10:00")

	def test_position_briefing_flags_a_morning_arrival_before_the_departure(self):
		"""The briefing compares the same two times: "8:00:" sorted after "10:00"."""
		self._morning_changeover()
		briefing = api.position_briefing(PROP_A, TODAY)
		self.assertIn({"room_no": "201", "eta": "08:00", "etd": "10:00"},
		              [{k: c[k] for k in ("room_no", "eta", "etd")} for c in briefing["changeover_conflicts"]])
		arrival = next(a for a in briefing["arrivals"] if a.eta == "08:00")
		departure = next(x for x in briefing["departures"] if x.etd == "10:00")
		self.assertEqual(arrival.planned_check_in_time, "08:00")
		self.assertEqual(departure.planned_check_out_time, "10:00")

	def test_a_morning_day_use_keeps_its_rate_lock_key_when_read_back(self):
		"""The booking is priced from the times the desk sent ("08:00:00");
		read back from the database they are timedeltas, and "8:00:" made
		another lock key, so a save that changed nothing re-priced it."""
		res = make_reservation(PROP_A, self.rt, TODAY, TODAY, room=self.room, is_day_use=1,
		                       rate_plan=self.hourly.name, auto_price=1,
		                       planned_check_in_time="08:00:00", planned_check_out_time="11:00:00")
		self.assertTrue(res.rate_lock_key)
		row = frappe.get_doc("Reservation", res.name)
		self.assertIsInstance(row.planned_check_in_time, timedelta)
		self.assertEqual(row.rate_lock_key_for(row.quote_inputs()), res.rate_lock_key)

	def test_overstay_full_day_and_folio_post(self):
		set_setting(PROP_A, "day_use_overstay", "Full day")
		res = make_reservation(
			PROP_A, self.rt, TODAY, TODAY, status="Checked In", room=self.room,
			rate_plan=self.hourly.name, is_day_use=1, auto_price=1,
			planned_check_in_time="10:00:00", planned_check_out_time="12:00:00")
		# Past ETD → full day card rate when posting.
		past = datetime.strptime(f"{TODAY} 15:00:00", "%Y-%m-%d %H:%M:%S")
		with patch("kamra.day_use.now_datetime", return_value=past):
			folio_mod.post_remaining_nights(frappe.get_doc("Reservation", res.name))
		folio = frappe.get_doc("Folio", guest_folio(res.name))
		room = [c for c in folio.charges if c.charge_type == "Room"]
		self.assertEqual(len(room), 1)
		self.assertIn("full day", room[0].description)
		# Full day ≈ base 2400 (tax handling may back out); must exceed 2h×200.
		self.assertGreater(float(room[0].amount), 400)

	def test_alert_overdue_day_use_once(self):
		# a day use from the start: validate_dates refuses a same-day stay otherwise
		res = make_reservation(PROP_A, self.rt, TODAY, TODAY,
		                       status="Checked In", room=self.room, is_day_use=1)
		res.db_set("planned_check_out_time", "08:00:00")
		past = datetime.strptime(f"{TODAY} 10:00:00", "%Y-%m-%d %H:%M:%S")
		with patch("kamra.day_use.now_datetime", return_value=past):
			first = day_use.alert_overdue_day_use(PROP_A)
			second = day_use.alert_overdue_day_use(PROP_A)
		self.assertIn(res.name, first)
		self.assertEqual(second, [])


class DayUseUnitsTestCase(AuditTestCase):
	"""Pure unit maths — no property fixtures beyond AuditTestCase."""

	properties = ()

	def test_a_time_field_reads_as_hh_mm(self):
		"""The database gives a Time field as a timedelta: 08:00 is "8:00:00",
		whose first five characters were "8:00:"."""
		for value, text in ((timedelta(hours=8), "08:00"), (timedelta(hours=23, minutes=30), "23:30"),
		                    ("08:00:00", "08:00"), ("8:05", "08:05"), ("13:00", "13:00"),
		                    ("8:00:", "08:00"), (time(7, 45), "07:45"),
		                    (datetime(2031, 3, 12, 8, 5), "08:05"),
		                    (None, None), ("", None), ("   ", None),
		                    ("nope", None), ("99:99", None), ("24:00", None)):
			with self.subTest(value=value):
				self.assertEqual(day_use.hhmm(value), text)

	def test_an_unreadable_time_does_not_raise(self):
		"""A bad string must not take down due-out or the hourly bill."""
		res = frappe._dict(check_out_date=TODAY, is_day_use=1, status="Checked In",
		                   planned_check_out_time="nope")
		now = datetime.strptime(f"{TODAY} 12:00", "%Y-%m-%d %H:%M")
		self.assertTrue(day_use.is_due_out(res, now=now))
		slot = frappe._dict(check_in_date=TODAY, planned_check_in_time="nope",
		                    planned_check_out_time="also")
		at = datetime.strptime(f"{TODAY} 12:00", "%Y-%m-%d %H:%M")
		with patch("kamra.day_use.now_datetime", return_value=at):
			self.assertEqual(day_use.reservation_slot_hours(slot), (2.0, 8.0))

	def test_billable_units_rounding(self):
		plan = {"billing_basis": "Hourly", "hourly_rate": 100, "min_hours": 2,
		        "block_hours": 3, "block_rate": 250}
		u = day_use.billable_units(1.2, plan, overstay="Next hour")
		self.assertEqual(u["hours"], 2)  # min hours
		u = day_use.billable_units(2.1, plan, overstay="Next hour")
		self.assertEqual(u["hours"], 3)
		u = day_use.billable_units(4, plan, overstay="Next block")
		self.assertEqual(u["hours"], 6)
		block = {**plan, "billing_basis": "Block"}
		u = day_use.billable_units(4, block, overstay="Next hour")
		self.assertEqual(u["units"], 2)
		self.assertEqual(u["amount"], 500)
		u = day_use.billable_units(5, plan, overstay="Full day", planned_hours=3)
		self.assertTrue(u["full_day"])
