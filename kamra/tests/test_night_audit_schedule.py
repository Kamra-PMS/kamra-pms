"""The per-property night audit schedule (#203): night_audit_auto,
night_audit_time and grace on the property clock, a 15 minute tick that
closes one business date at a time, and the Night Audit Log.

The site clock is pinned per tick (now_datetime) and the calendar with
TODAY from audit_fixtures, so the tests never depend on the wall clock."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import frappe
from frappe.utils import get_datetime, get_system_timezone

from kamra import folio as folio_mod
from kamra import night_audit as na_mod
from kamra import settings
from kamra.tests.audit_fixtures import (
	PROP_A,
	PROP_B,
	TODAY,
	YESTERDAY,
	AuditTestCase,
	charges,
	d,
	make_property,
	make_reservation,
	make_room,
	make_room_type,
)


class NightAuditScheduleTestCase(AuditTestCase):
	def setUp(self):
		super().setUp()
		frappe.local.lang = "en"  # restored by AuditTestCase.tearDown
		self.at(TODAY)
		make_property(PROP_A, business_date=YESTERDAY)
		make_property(PROP_B, business_date=YESTERDAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")
		self.addCleanup(settings.clear_cache)
		self.calls: list[str] = []
		self.result: dict | None = None  # a canned run_night_audit result
		self.boom = False
		real = folio_mod.run_night_audit
		real_get_all = frappe.get_all

		def our_properties(doctype, *a, **kw):
			# the tick walks every property on the site; keep it to ours so
			# it never locks or audits a developer's seeded hotels
			rows = real_get_all(doctype, *a, **kw)
			if doctype == "Property" and kw.get("pluck") == "name":
				return [p for p in rows if p in (PROP_A, PROP_B)]
			return rows

		def only_ours(prop, business_date=None, **kw):
			self.calls.append(prop)
			if self.boom:
				raise RuntimeError("boom")
			if self.result is not None:
				return self.result
			return real(prop, business_date, **kw)

		self._stack.enter_context(
			patch.object(folio_mod, "run_night_audit", side_effect=only_ours))
		self._stack.enter_context(
			patch.object(frappe, "get_all", side_effect=our_properties))
		self.log_error = self._stack.enter_context(patch.object(frappe, "log_error"))
		self.alert = self._stack.enter_context(patch.object(na_mod, "alert_staff"))

	# helpers -------------------------------------------------------------

	def setting(self, key, value, prop=PROP_A):
		settings.write_kv(prop, key, value)
		settings.clear_cache(prop)

	def site_clock(self, hhmm: str):
		t = get_datetime(f"{TODAY} {hhmm}:00")
		stack = self._stack
		for target in ("frappe.utils.now_datetime", "kamra.folio.now_datetime",
		               "kamra.night_audit.now_datetime"):
			stack.enter_context(patch(target, return_value=t))

	def tick(self, hhmm: str):
		"""One scheduler tick at this site time."""
		t = get_datetime(f"{TODAY} {hhmm}:00")
		with patch("frappe.utils.now_datetime", return_value=t), \
		     patch.object(folio_mod, "now_datetime", return_value=t), \
		     patch.object(na_mod, "now_datetime", return_value=t):
			folio_mod.nightly_audit_all_properties()

	def bd(self, prop=PROP_A):
		return str(frappe.db.get_value("Property", prop, "business_date"))

	def closed(self, prop=PROP_A):
		return sorted(str(x) for x in frappe.get_all(
			"Night Audit Run", filters={"property": prop}, pluck="business_date"))

	def logs(self, prop=PROP_A):
		return frappe.get_all("Night Audit Log", filters={"property": prop},
		                      fields=["status", "run_trigger", "business_date",
		                              "message", "audit"],
		                      order_by="creation asc")

	# 10 - no settings rows: today's 03:00 behaviour
	def test_defaults_reproduce_the_0300_run(self):
		self.assertEqual(settings.get_setting(PROP_A, "night_audit_auto"), 1)
		self.assertEqual(settings.get_setting(PROP_A, "night_audit_time"), "03:00")
		self.assertEqual(settings.get_setting(PROP_A, "night_audit_grace_minutes"), 0)

	# 1 - closes once after 03:00 local and not before
	def test_default_closes_once_after_0300(self):
		res = make_reservation(PROP_A, self.rt, d(-2), d(2),
		                       status="Checked In", room=self.room)
		self.tick("02:45")
		self.assertEqual(self.closed(), [])
		self.assertEqual(self.logs(), [])
		self.tick("03:00")
		self.assertEqual(self.closed(), [YESTERDAY])
		self.assertEqual(self.bd(), TODAY)
		self.tick("03:15")
		self.tick("09:00")
		self.assertEqual(self.closed(), [YESTERDAY])
		self.assertEqual(len(charges(res.name, "Room")), 1)
		logs = self.logs()
		self.assertEqual([(r.status, r.run_trigger) for r in logs],
		                 [("Closed", "Scheduled")])
		self.assertEqual(str(logs[0].business_date), YESTERDAY)
		self.assertTrue(logs[0].audit)

	# 2 - auto off: the scheduler never closes it
	def test_auto_off_is_never_closed_by_the_scheduler(self):
		self.setting("night_audit_auto", 0)
		for t in ("03:00", "06:00", "23:45"):
			self.tick(t)
		self.assertNotIn(PROP_A, self.calls)
		self.assertEqual(self.bd(), YESTERDAY)
		# B, on the defaults, closed as usual
		self.assertEqual(self.bd(PROP_B), TODAY)

	# 3 - a custom time, and the grace delay
	def test_custom_time_and_grace(self):
		self.setting("night_audit_time", "05:30")
		self.setting("night_audit_grace_minutes", 30, PROP_B)
		for t in ("03:00", "03:15"):
			self.tick(t)
		self.assertEqual(self.bd(), YESTERDAY)
		self.assertEqual(self.bd(PROP_B), YESTERDAY)
		self.tick("03:30")
		self.tick("05:15")
		self.assertEqual(self.bd(), YESTERDAY)
		self.tick("05:30")
		self.assertEqual(self.bd(), TODAY)
		# B: the default 03:00 plus 30 minutes grace
		self.assertEqual(self.bd(PROP_B), TODAY)
		self.assertEqual(frappe.db.get_value("Night Audit Log", {"property": PROP_B},
		                                     "started_at"), get_datetime(f"{TODAY} 03:30:00"))

	# 4 - a second tick (or worker) never closes the day again; a held date
	# is tried once a day, not every 15 minutes
	def test_second_tick_does_not_close_again_or_re_alert(self):
		self.tick("03:00")
		self.tick("03:00")
		self.assertEqual(self.closed(), [YESTERDAY])
		self.assertEqual(self.calls.count(PROP_A), 1)
		# the lock: the row is taken FOR UPDATE before the run
		with patch.object(frappe.db, "sql", wraps=frappe.db.sql) as sql:
			frappe.db.set_value("Property", PROP_A, "business_date", YESTERDAY)
			frappe.db.delete("Night Audit Run", {"property": PROP_A})
			self.tick("03:15")
		self.assertTrue(any("FOR UPDATE" in str(c.args[0]) for c in sql.call_args_list))

	def test_held_date_is_tried_once_a_day(self):
		self.result = {"held": True, "business_date": YESTERDAY, "message": "held: open tills"}
		self.tick("03:00")
		self.tick("03:15")
		self.tick("08:00")
		self.assertEqual(self.calls.count(PROP_A), 1)
		self.assertEqual([r.status for r in self.logs()], ["Held"])
		self.assertEqual(self.logs()[0].message, "held: open tills")

	# 5 - three days behind: one day per tick, never past today
	def test_catch_up_one_day_per_tick(self):
		res = make_reservation(PROP_A, self.rt, d(-5), d(2),
		                       status="Checked In", room=self.room)
		frappe.db.set_value("Property", PROP_A, "business_date", d(-3))
		self.tick("03:00")
		self.assertEqual(self.bd(), d(-2))
		self.tick("03:15")
		self.assertEqual(self.bd(), d(-1))
		self.tick("03:30")
		self.assertEqual(self.bd(), TODAY)
		self.tick("03:45")
		self.tick("23:45")
		self.assertEqual(self.bd(), TODAY)
		self.assertEqual(self.closed(), [d(-3), d(-2), YESTERDAY])
		self.assertEqual(len(charges(res.name, "Room")), 3)
		self.assertEqual([r.status for r in self.logs()], ["Closed"] * 3)

	def test_never_closes_today_or_later(self):
		frappe.db.set_value("Property", PROP_A, "business_date", TODAY)
		self.tick("23:45")
		frappe.db.set_value("Property", PROP_A, "business_date", d(1))
		self.tick("23:45")
		self.assertNotIn(PROP_A, self.calls)
		self.assertEqual(self.closed(), [])

	# 7 - manual run with auto off, same guards, logged
	def test_manual_run_with_auto_off(self):
		from kamra import api
		self.setting("night_audit_auto", 0)
		self.site_clock("10:00")
		out = api.run_night_audit(PROP_A)
		self.assertEqual(out["business_date"], YESTERDAY)
		self.assertEqual(self.bd(), TODAY)
		# today may be closed by hand (before midnight); tomorrow may not
		api.run_night_audit(PROP_A)
		self.assertEqual(self.bd(), d(1))
		with self.assertRaises(frappe.ValidationError):
			api.run_night_audit(PROP_A)
		self.assertEqual(self.bd(), d(1))
		self.assertEqual([(r.status, r.run_trigger) for r in self.logs()],
		                 [("Closed", "Manual"), ("Closed", "Manual"),
		                  ("Skipped", "Manual")])
		self.assertIn("ahead of today", self.logs()[-1].message)

	# 8 - every run is logged; a failure alerts Hotel Admin, is not retried
	# every tick, and does not stop the other property
	def test_failure_is_logged_and_alerted(self):
		self.boom = True
		self.tick("03:00")
		self.tick("03:15")
		self.assertEqual(self.calls.count(PROP_A), 1)
		self.assertEqual(self.bd(), YESTERDAY)
		log = self.logs()
		self.assertEqual([r.status for r in log], ["Failed"])
		self.assertIn("boom", log[0].message)
		alerted = [c.args for c in self.alert.call_args_list if c.args[0] == PROP_A]
		self.assertEqual(len(alerted), 1)
		self.assertEqual(alerted[0][1], ("Hotel Admin",))
		titles = [c.kwargs.get("title") for c in self.log_error.call_args_list]
		self.assertIn(f"Night audit failed: {PROP_A}", titles)

	# 9 - two properties on different clocks close at their own 03:00
	def test_properties_close_on_their_own_clock(self):
		site = get_system_timezone()
		day = datetime.fromisoformat(f"{TODAY} 02:00")
		ahead = None
		for tz in ("Asia/Tokyo", "Asia/Kolkata", "Asia/Dubai", "Europe/Berlin",
		           "Europe/London", "America/Sao_Paulo", "America/New_York",
		           "America/Los_Angeles", "Pacific/Honolulu"):
			diff = (day.replace(tzinfo=ZoneInfo(site)).astimezone(ZoneInfo(tz))
			        .replace(tzinfo=None) - day)
			if timedelta(hours=1) <= diff <= timedelta(hours=6):
				ahead = tz
				break
		self.assertTrue(ahead, f"no test zone 1-6 h ahead of {site}")
		frappe.db.set_value("Property", PROP_B, "timezone", ahead)
		self.tick("02:00")  # B is past 03:00 on its clock, A is not
		self.assertEqual(self.bd(PROP_B), TODAY)
		self.assertEqual(self.bd(PROP_A), YESTERDAY)
		self.tick("03:00")
		self.assertEqual(self.bd(PROP_A), TODAY)

	# the settings page view
	def test_schedule_view(self):
		self.site_clock("01:00")
		out = na_mod.night_audit_schedule(PROP_A)
		self.assertEqual(out["next_run"], f"{TODAY} 03:00:00")
		self.assertEqual(out["business_date"], YESTERDAY)
		self.setting("night_audit_auto", 0)
		self.assertIsNone(na_mod.night_audit_schedule(PROP_A)["next_run"])
