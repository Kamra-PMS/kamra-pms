"""The demo history replay: its clock, its mutes, and the rebuild guard."""

import datetime
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from kamra import demo_guard
from kamra.scripts import reset_demo, seed_history


class SimulatedPastTestCase(IntegrationTestCase):
	def test_clock_moves_every_reader_and_comes_back(self):
		import kamra.cashier as cashier
		real = cashier.now_datetime
		past = add_days(nowdate(), -30)
		with seed_history.simulated_past():
			seed_history.at(past, 10)
			# frappe's own helpers and a kamra module that imported
			# now_datetime directly both read the simulated day
			self.assertEqual(frappe.utils.nowdate(), past)
			self.assertEqual(str(cashier.now_datetime().date()), past)
		self.assertIs(cashier.now_datetime, real)
		self.assertEqual(frappe.utils.nowdate(), nowdate())

	def test_side_effects_are_muted_and_restored(self):
		enqueue, publish = frappe.enqueue, frappe.publish_realtime
		with seed_history.simulated_past():
			self.assertIsNone(frappe.enqueue("kamra.webhooks.deliver", delivery="x"))
			self.assertIsNone(frappe.publish_realtime("kamra_print", {}, user="Administrator"))
			self.assertTrue(frappe.flags.mute_emails)
			self.assertTrue(frappe.flags.kamra_mute_webhooks)
		self.assertIs(frappe.enqueue, enqueue)
		self.assertIs(frappe.publish_realtime, publish)

	def test_minutes_roll_into_the_hour(self):
		with seed_history.simulated_past():
			seed_history.at("2026-01-05", 11, 75)
			self.assertEqual(seed_history._state["at"], datetime.datetime(2026, 1, 5, 12, 15))

	def test_short_history_ties_out(self):
		# three days through the real write paths; only on a site where the
		# demo hotel exists and has no history yet (a fresh dev/CI site)
		if not frappe.db.exists("Property", seed_history.PROPERTY) or frappe.db.exists(
				"Night Audit Run", {"property": seed_history.PROPERTY}):
			self.skipTest("needs the demo property without any history")
		stats = seed_history.execute(days=3)
		self.assertEqual(stats.get("night_audits"), 3)
		self.assertEqual(
			str(frappe.db.get_value("Property", seed_history.PROPERTY, "business_date")),
			nowdate())
		self.assertFalse(frappe.db.count("Error Log", {"method": ("like", "seed_history%")}))

	def test_past_room_charges_name_the_past_stay(self):
		# today's demo guests are already checked in while the past replays,
		# so a POS bill or laundry bag sent by room alone landed on their folio
		from types import SimpleNamespace

		h = seed_history.History.__new__(seed_history.History)
		h.rng, h.stats = seed_history.random.Random(1), {}
		h.outlets, h.menu = ["Restaurant"], {"Restaurant": ["Dal", "Rice"]}
		day = add_days(nowdate(), -5)
		past = {"in": True, "arrive": add_days(day, -1), "depart": add_days(day, 2),
		        "room": "R-101", "res": "RES-PAST"}
		h.plan = [past]
		orders = []
		order = SimpleNamespace(items=[], name="POS-1")
		with patch("kamra.pos.create_order",
		           side_effect=lambda *a, **k: orders.append(k) or {"name": "POS-1"}), \
				patch("kamra.pos.confirm_order"), patch("kamra.pos.deliver_order"), \
				patch("kamra.pos.pay_order"), patch.object(seed_history.frappe, "get_doc",
				                                           return_value=order), \
				patch.object(h, "as_user"), patch.object(h.rng, "random", return_value=0.1):
			h._pos(day, "dinner")
		to_rooms = [k for k in orders if k.get("room")]
		self.assertTrue(to_rooms)
		self.assertEqual({k["reservation"] for k in to_rooms}, {"RES-PAST"})


class RebuildGuardTestCase(IntegrationTestCase):
	def tearDown(self):
		frappe.db.set_default(demo_guard.FLAG, "")

	def test_fresh_flag_blocks_and_expires(self):
		frappe.db.set_default(demo_guard.FLAG, str(frappe.utils.now_datetime()))
		self.assertTrue(demo_guard.rebuilding())
		old = frappe.utils.now_datetime() - datetime.timedelta(
			minutes=demo_guard.REBUILD_MINUTES + 1)
		frappe.db.set_default(demo_guard.FLAG, str(old))
		# a reset that died long ago never keeps the demo shut
		self.assertFalse(demo_guard.rebuilding())
		frappe.db.set_default(demo_guard.FLAG, "")
		self.assertFalse(demo_guard.rebuilding())

	def test_reset_hands_history_on_and_reopens(self):
		stubs = (
			patch.object(reset_demo, "_wipe_kamra_doctypes", return_value=0),
			patch.object(reset_demo, "_wipe_core", return_value=0),
			patch.object(reset_demo, "_wipe_extra_users", return_value=0),
			patch.object(reset_demo, "_reset_demo_passwords"),
			patch("kamra.scripts.seed_demo.execute"),
			patch.object(reset_demo.frappe.db, "commit"),
		)
		for s in stubs:
			s.start()
			self.addCleanup(s.stop)
		with patch.object(seed_history, "execute", return_value={"night_audits": 0}) as replay:
			out = reset_demo.reset(history="inline")
		replay.assert_called_once()
		self.assertEqual(out["history"], {"night_audits": 0})
		self.assertFalse(demo_guard.rebuilding())
		with patch.object(reset_demo.frappe, "enqueue") as enqueue:
			reset_demo.reset(history="queue")
		self.assertEqual(enqueue.call_args.args[0], "kamra.scripts.seed_history.after_reset")
		# the queued job reopens the demo when it ends; until then it is shut
		self.assertTrue(demo_guard.rebuilding())
