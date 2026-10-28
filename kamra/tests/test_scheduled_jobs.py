"""The other scheduled / audit-style routines.

- every scheduler_events entry in hooks.py resolves to a callable;
- the cashier till: open, cash movements, close, variance, shift handover;
- privacy retention: kamra.privacy.apply_retention and
  apply_message_retention (03:30 / 03:40);
- the hourly channel-manager ARI push (kamra.channel_manager.push_all_ari);
- the 15-minute jobs: reservation_state.expire_holds and
  housekeeping.escalate_overdue_tasks.

The night audit has its own module (test_night_audit) and the ledger reports
theirs (test_ledger_audit). Each routine here gets a happy path, an
empty-data run, a failure mode and its invariant.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import frappe
from frappe.utils import add_to_date, get_datetime, now_datetime

from kamra import cashier, privacy
from kamra import channel_manager as cm
from kamra.tests.audit_fixtures import (
	PROP_A,
	PROP_B,
	TODAY,
	AuditTestCase,
	d,
	ensure_user,
	make_guest,
	make_property,
	make_reservation,
	make_room,
	make_room_type,
)


def _backdate(doctype: str, name: str, when: str, field: str = "modified"):
	frappe.db.sql(  # nosemgrep: frappe-sql-format-injection -- test helper, constant doctypes/fields
		f"UPDATE `tab{doctype}` SET `{field}` = %s WHERE name = %s", (when, name))


class SchedulerHooksTestCase(AuditTestCase):
	properties = ()

	def test_every_scheduled_job_resolves(self):
		from kamra import hooks
		jobs = [m for methods in hooks.scheduler_events["cron"].values()
		        for m in methods]
		self.assertIn("kamra.folio.nightly_audit_all_properties", jobs)
		for path in jobs:
			self.assertTrue(callable(frappe.get_attr(path)), path)

	def test_night_audit_ticks_every_15_minutes(self):
		from kamra import hooks
		cron = hooks.scheduler_events["cron"]
		# per-property run time on the property clock (#203)
		self.assertIn("kamra.folio.nightly_audit_all_properties", cron["*/15 * * * *"])
		self.assertNotIn("0 3 * * *", cron)
		self.assertIn("kamra.privacy.apply_retention", cron["30 3 * * *"])
		self.assertIn("kamra.channel_manager.push_all_ari", cron["0 * * * *"])


# ── cashier till ────────────────────────────────────────────────────────────

class CashierCloseTestCase(AuditTestCase):
	DESK = "ut.till.desk@test.local"
	DESK2 = "ut.till.desk2@test.local"
	FIN = "ut.till.finance@test.local"

	def setUp(self):
		super().setUp()
		self.at(TODAY)
		make_property(PROP_A, business_date=TODAY)
		ensure_user(self.DESK, ["Front Desk"])
		ensure_user(self.DESK2, ["Front Desk"])
		ensure_user(self.FIN, ["Finance"])
		frappe.set_user(self.DESK)  # nosemgrep: frappe-setuser -- the cashier persona

	def open(self, opening=1000):
		return cashier.open_session(PROP_A, opening)["name"]

	def test_full_shift_closes_with_the_right_variance(self):
		sess = self.open(1000)
		cashier.record_cashier_txn(PROP_A, "Payment", "Cash", 500)
		cashier.record_cashier_txn(PROP_A, "Payment", "Card", 900)
		cashier.record_cashier_txn(PROP_A, "Payment", "UPI", 300)
		cashier.record_cashier_txn(PROP_A, "Refund", "Cash", -50)
		cashier.post_paid_out(PROP_A, 100, "UT courier")
		cashier.cash_drop(PROP_A, 200, "safe")
		out = cashier.close_session(sess, counted_cash=1100, notes="UT close")
		# 1000 float + 500 cash - 50 refund - 100 paid out - 200 dropped
		self.assertAlmostEqual(out["expected_cash"], 1150, places=2)
		self.assertAlmostEqual(out["variance"], -50, places=2)
		self.assertEqual(out["status"], "Closed")
		self.assertEqual(out["closed_by"], self.DESK)
		t = out["totals"]
		self.assertAlmostEqual(t["card"], 900, places=2)
		self.assertAlmostEqual(t["upi"], 300, places=2)
		# non-cash takings never change what should be in the drawer
		self.assertAlmostEqual(
			t["expected_cash"],
			t["opening_float"] + t["cash"] - t["paid_outs"] - t["drops"]
			- t["petty_cash"], places=2)
		handover = frappe.get_all("Shift Handover", filters={
			"property": PROP_A, "shift_date": TODAY},
			fields=["closing_cash", "opening_cash", "cash_collected", "status"])
		self.assertEqual(len(handover), 1)
		self.assertAlmostEqual(float(handover[0].closing_cash), 1100, places=2)
		self.assertAlmostEqual(float(handover[0].cash_collected), 450, places=2)

	def test_empty_shift_closes_level(self):
		sess = self.open(750)
		out = cashier.close_session(sess, counted_cash=750)
		self.assertAlmostEqual(out["expected_cash"], 750, places=2)
		self.assertAlmostEqual(out["variance"], 0, places=2)
		self.assertEqual(out["transactions"], [])

	def test_session_is_stamped_with_the_business_date(self):
		frappe.db.set_value("Property", PROP_A, "business_date", d(-1))
		sess = self.open()
		self.assertEqual(str(frappe.db.get_value("Cashier Session", sess,
		                                         "business_date")), d(-1))

	def test_reopening_returns_the_open_session(self):
		self.assertEqual(self.open(), self.open(500))

	def test_closing_twice_is_refused(self):
		sess = self.open()
		cashier.close_session(sess, counted_cash=1000)
		with self.assertRaises(frappe.ValidationError):
			cashier.close_session(sess, counted_cash=1000)

	def test_another_cashier_cannot_close_but_finance_can(self):
		sess = self.open()
		frappe.set_user(self.DESK2)  # nosemgrep: frappe-setuser -- persona
		with self.assertRaises(frappe.ValidationError):
			cashier.close_session(sess, counted_cash=1000)
		frappe.set_user(self.FIN)  # nosemgrep: frappe-setuser -- persona
		self.assertEqual(cashier.close_session(sess, 1000)["status"], "Closed")

	def test_cash_movements_need_an_open_till(self):
		with self.assertRaisesRegex(frappe.ValidationError, "NO_OPEN_SESSION"):
			cashier.post_paid_out(PROP_A, 100, "UT courier")
		with self.assertRaises(frappe.ValidationError):
			cashier.cash_drop(PROP_A, 0)

	def test_housekeeping_cannot_touch_the_till(self):
		ensure_user("ut.till.hk@test.local", ["Housekeeping"])
		frappe.set_user("ut.till.hk@test.local")  # nosemgrep: frappe-setuser -- persona
		with self.assertRaises(frappe.PermissionError):
			cashier.open_session(PROP_A, 100)


# ── privacy retention ───────────────────────────────────────────────────────

class RetentionTestCase(AuditTestCase):
	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.privacy")
		make_property(PROP_A, guest_retention_months=12,
		              message_retention_days=30)
		make_property(PROP_B, guest_retention_months=0,
		              message_retention_days=0)
		self.rt = make_room_type(PROP_A, "STD")
		self.rt_b = make_room_type(PROP_B, "STD")
		# file deletes are outside the transaction; keep them out of tests
		self._stack.enter_context(
			patch("kamra.privacy._delete_files", return_value=0))
		# the job walks every guest on the site; erase only ours for real
		real = privacy.erase_guest
		self.ours: set[str] = set()
		self.selected: list[str] = []

		def erase_ours(guest, reason="request"):
			self.selected.append(guest)
			if guest in self.ours:
				return real(guest, reason)
			return {}

		self._stack.enter_context(
			patch("kamra.privacy.erase_guest", side_effect=erase_ours))

	def past_guest(self, first, check_out, prop=PROP_A, **guest_fields):
		guest = make_guest(first, **guest_fields)
		self.ours.add(guest)
		res = make_reservation(prop, self.rt if prop == PROP_A else self.rt_b,
		                       str(frappe.utils.add_days(check_out, -2)),
		                       str(check_out), status="Checked Out",
		                       guest=guest)
		_backdate("Reservation", res.name, f"{check_out} 12:00:00")
		_backdate("Guest", guest, "2000-01-01 00:00:00")
		return guest, res

	def name_of(self, guest):
		return frappe.db.get_value("Guest", guest, "full_name")

	def test_guest_idle_past_retention_is_erased(self):
		old, res = self.past_guest("UT Oldstay", d(-400), phone="9990001111")
		recent, _ = self.past_guest("UT Recent", d(-30))
		out = privacy.apply_retention(limit=100000)
		self.assertGreaterEqual(out["erased"], 1)
		self.assertTrue(self.name_of(old).startswith("Guest "))
		self.assertEqual(frappe.db.get_value("Guest", old, "phone"), "")
		self.assertEqual(self.name_of(recent), "UT Recent")
		self.assertNotIn(recent, self.selected)
		# the stay itself stays on the books, under the alias
		self.assertTrue(frappe.db.exists("Reservation", res.name))
		self.assertEqual(frappe.db.get_value("Reservation", res.name, "guest_name"),
		                 self.name_of(old))

	def test_blacklisted_guest_is_kept(self):
		g, _ = self.past_guest("UT Banned", d(-400))
		# flagged after the stay (a flagged guest cannot book at all)
		frappe.db.set_value("Guest", g, {"blacklisted": 1,
		                                 "blacklist_reason": "UT"},
		                    update_modified=False)
		privacy.apply_retention(limit=100000)
		self.assertNotIn(g, self.selected)
		self.assertEqual(self.name_of(g), "UT Banned")

	def test_property_with_retention_off_keeps_its_guests(self):
		g, _ = self.past_guest("UT Both", d(-400))
		# the same guest also stayed at B, which keeps guests forever
		make_reservation(PROP_B, self.rt_b, d(-402), d(-400),
		                 status="Checked Out", guest=g)
		frappe.db.sql("UPDATE `tabReservation` SET modified = %s WHERE guest = %s",
		              (f"{d(-400)} 12:00:00", g))
		only_b, _ = self.past_guest("UT OnlyB", d(-400), prop=PROP_B)
		privacy.apply_retention(limit=100000)
		self.assertNotIn(g, self.selected)
		self.assertNotIn(only_b, self.selected)

	def test_live_booking_keeps_the_guest(self):
		g, _ = self.past_guest("UT Returning", d(-400))
		make_reservation(PROP_A, self.rt, d(10), d(12), guest=g)
		privacy.apply_retention(limit=100000)
		self.assertNotIn(g, self.selected)

	def test_already_erased_guest_is_not_picked_again(self):
		g, _ = self.past_guest("UT Twice", d(-400))
		privacy.apply_retention(limit=100000)
		self.assertIn(g, self.selected)
		self.selected.clear()
		privacy.apply_retention(limit=100000)
		self.assertNotIn(g, self.selected)

	def test_no_retention_anywhere_is_a_no_op(self):
		with patch.object(frappe, "get_all", return_value=[]):
			self.assertEqual(privacy.apply_retention(), {"erased": 0})
			self.assertEqual(privacy.apply_message_retention(),
			                 {"messages": 0, "chats": 0})

	# messages ---------------------------------------------------------------

	def message(self, prop, content, age_days):
		doc = frappe.get_doc({"doctype": "WhatsApp Message", "property": prop,
		                      "direction": "Inbound", "status": "Received",
		                      "content": content}).insert(ignore_permissions=True)
		_backdate("WhatsApp Message", doc.name, self.ago(age_days), "creation")
		return doc.name

	def chat(self, prop, age_days):
		doc = frappe.get_doc({"doctype": "Copilot Conversation", "property": prop,
		                      "title": "UT chat about a guest",
		                      "messages": '[{"role": "user", "content": "hi"}]'}
		                     ).insert(ignore_permissions=True)
		_backdate("Copilot Conversation", doc.name, self.ago(age_days))
		return doc.name

	def ago(self, days):
		return str(add_to_date(get_datetime(f"{TODAY} 03:40:00"), days=-days))

	def test_message_retention_clears_old_text_only(self):
		self._stack.enter_context(patch(
			"kamra.privacy.now_datetime",
			return_value=get_datetime(f"{TODAY} 03:40:00")))
		old = self.message(PROP_A, "UT my passport is X123", 45)
		fresh = self.message(PROP_A, "UT see you soon", 5)
		kept_b = self.message(PROP_B, "UT B keeps this", 400)
		old_chat = self.chat(PROP_A, 45)
		fresh_chat = self.chat(PROP_A, 5)
		orphan = self.chat(None, 45)  # follows the shortest period (30)
		out = privacy.apply_message_retention()
		self.assertGreaterEqual(out["messages"], 1)
		self.assertGreaterEqual(out["chats"], 2)
		self.assertEqual(frappe.db.get_value("WhatsApp Message", old, "content"), "")
		# the row stays for audit: direction and status survive
		self.assertEqual(frappe.db.get_value("WhatsApp Message", old, "status"),
		                 "Received")
		self.assertEqual(frappe.db.get_value("WhatsApp Message", fresh, "content"),
		                 "UT see you soon")
		self.assertEqual(frappe.db.get_value("WhatsApp Message", kept_b, "content"),
		                 "UT B keeps this")
		for name in (old_chat, orphan):
			row = frappe.db.get_value("Copilot Conversation", name,
			                          ["messages", "title"], as_dict=True)
			self.assertEqual(row.messages, "[]")
			self.assertEqual(row.title, privacy.CLEARED_CHAT_TITLE)
		self.assertNotEqual(frappe.db.get_value("Copilot Conversation",
		                                        fresh_chat, "messages"), "[]")
		# idempotent: a second night finds nothing of ours left to clear
		again = privacy.apply_message_retention()
		self.assertEqual(frappe.db.get_value("WhatsApp Message", old, "content"), "")
		self.assertLessEqual(again["messages"], out["messages"])


# ── channel manager ARI push ───────────────────────────────────────────────

class AriPushTestCase(AuditTestCase):
	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date",
		        "kamra.channel_manager")
		make_property(PROP_A)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.rooms = [make_room(PROP_A, self.rt, n) for n in ("101", "102")]
		self.conn = self.connection()
		self.provider = MagicMock()
		self.provider.push_ari.return_value = (True, "accepted")
		self._stack.enter_context(
			patch("kamra.channel_manager.provider_for", return_value=self.provider))

	def connection(self, active=1, mapped=True):
		conn = frappe.get_doc({
			"doctype": "Channel Manager Connection", "property": PROP_A,
			"provider": "Custom", "active": active, "sync_days": 3,
			"external_property_id": "ut"}).insert(ignore_permissions=True)
		if mapped:
			frappe.get_doc({"doctype": "Channel Room Mapping",
			                "connection": conn.name, "room_type": self.rt,
			                "external_room_id": "ut-std",
			                "external_rate_id": "ut-bar"}
			               ).insert(ignore_permissions=True)
		return conn.name

	def pushed(self):
		return self.provider.push_ari.call_args.args[1]

	def test_push_sends_availability_and_rate_per_day(self):
		make_reservation(PROP_A, self.rt, d(0), d(1), room=self.rooms[0])
		cm.push_all_ari(PROP_A)
		snap = self.pushed()
		self.assertEqual(len(snap), 1)
		days = snap[0]["days"]
		self.assertEqual([x["date"] for x in days], [d(0), d(1), d(2)])
		# two rooms, one sold tonight
		self.assertEqual([x["available"] for x in days], [1, 2, 2])
		self.assertTrue(all(x["rate"] == 1000 for x in days))
		status = frappe.db.get_value("Channel Manager Connection", self.conn,
		                             "last_push_status")
		self.assertEqual(status, "OK: accepted")

	def test_unassigned_booking_still_lowers_availability(self):
		make_reservation(PROP_A, self.rt, d(0), d(1))
		make_reservation(PROP_A, self.rt, d(0), d(1))
		cm.push_all_ari(PROP_A)
		self.assertEqual(self.pushed()[0]["days"][0]["available"], 0)

	def test_inactive_connection_is_not_pushed(self):
		frappe.db.set_value("Channel Manager Connection", self.conn, "active", 0)
		cm.push_all_ari(PROP_A)
		self.provider.push_ari.assert_not_called()

	def test_provider_failure_is_logged_and_others_still_push(self):
		second = self.connection()
		self.provider.push_ari.side_effect = [(False, "down"), (True, "ok")]
		with patch.object(frappe, "log_error") as log:
			cm.push_all_ari(PROP_A)
		self.assertEqual(self.provider.push_ari.call_count, 2)
		self.assertEqual(log.call_count, 1)
		self.assertTrue(log.call_args.kwargs["title"].startswith("ARI push failed"))
		statuses = {n: frappe.db.get_value("Channel Manager Connection", n,
		                                   "last_push_status")
		            for n in (self.conn, second)}
		self.assertEqual(sorted(statuses.values()), ["FAILED: down", "OK: ok"])

	def test_unmapped_connection_is_logged_not_raised(self):
		frappe.db.delete("Channel Room Mapping", {"connection": self.conn})
		with patch.object(frappe, "log_error") as log:
			cm.push_all_ari(PROP_A)
		self.provider.push_ari.assert_not_called()
		log.assert_called_once()

	def test_hourly_cron_walks_every_active_connection(self):
		inactive = self.connection(active=0)
		with patch.object(cm, "push_ari") as push:
			cm.push_all_ari()  # the cron passes no property
		names = [c.args[0] for c in push.call_args_list]
		self.assertIn(self.conn, names)
		self.assertNotIn(inactive, names)


# ── 15-minute jobs ───────────────────────────────────────────────────────────

class HoldExpiryTestCase(AuditTestCase):
	def setUp(self):
		super().setUp()
		make_property(PROP_A)
		self.rt = make_room_type(PROP_A, "STD")
		for n in ("101", "102", "103"):
			make_room(PROP_A, self.rt, n)

	def hold(self, minutes, status="Held"):
		res = make_reservation(PROP_A, self.rt, d(5), d(7), status=status)
		frappe.db.set_value("Reservation", res.name, "hold_expires_on",
		                    add_to_date(now_datetime(), minutes=minutes))
		return res.name

	def status(self, name):
		return frappe.db.get_value("Reservation", name, "status")

	# expire_holds once set cancellation_reason to a value that is not one
	# of the field's Select options, so every save failed validation and no
	# hold was ever released. The reason is now an allowed option ("Other")
	# with the cause in cancellation_note.
	def test_expired_holds_are_released(self):
		from kamra.reservation_state import expire_holds
		lapsed = self.hold(-10)
		pending = self.hold(-1, status="Pending Payment")
		live = self.hold(30)
		out = expire_holds()
		self.assertGreaterEqual(out["expired"], 2)
		self.assertEqual(self.status(lapsed), "Cancelled")
		self.assertEqual(self.status(pending), "Cancelled")
		self.assertEqual(self.status(live), "Held")
		self.assertIsNone(frappe.db.get_value("Reservation", lapsed,
		                                      "hold_expires_on"))
		reason, note = frappe.db.get_value(
			"Reservation", lapsed, ["cancellation_reason", "cancellation_note"])
		self.assertEqual(reason, "Other")
		self.assertEqual(note, "Hold / payment window expired")
		options = frappe.get_meta("Reservation").get_field(
			"cancellation_reason").options.split("\n")
		self.assertIn(reason, options)

	def test_confirmed_stay_is_never_expired(self):
		from kamra.reservation_state import expire_holds
		conf = self.hold(-10, status="Confirmed")
		expire_holds()
		self.assertEqual(self.status(conf), "Confirmed")

	def test_a_failing_hold_is_logged_and_the_job_carries_on(self):
		from kamra.reservation_state import expire_holds
		bad, other = self.hold(-20), self.hold(-10)
		real = frappe.get_doc
		seen = []

		def flaky(*args, **kw):
			if args[:1] == ("Reservation",) and len(args) > 1:
				seen.append(args[1])
				if args[1] == bad:
					raise RuntimeError("locked")
			return real(*args, **kw)

		with patch.object(frappe, "get_doc", side_effect=flaky), \
		     patch.object(frappe, "log_error") as log:
			expire_holds()  # never raises into the scheduler
		self.assertEqual(self.status(bad), "Held")
		self.assertIn(other, seen)  # the job moved on past the failure
		self.assertIn(f"Hold expiry failed for {bad}",
		              [c.kwargs.get("title") for c in log.call_args_list])
		self.assertFalse(frappe.flags.kamra_status_transition)
		self.assertFalse(frappe.flags.kamra_cancelling)

	def test_nothing_to_expire(self):
		from kamra.reservation_state import expire_holds
		with patch.object(frappe, "get_all", return_value=[]):
			self.assertEqual(expire_holds(), {"expired": 0})


class HousekeepingEscalationTestCase(AuditTestCase):
	def setUp(self):
		super().setUp()
		make_property(PROP_A)
		self.rt = make_room_type(PROP_A, "STD")
		self.room = make_room(PROP_A, self.rt, "101")
		self.notify = self._stack.enter_context(
			patch("kamra.housekeeping._notify_role"))

	def task(self, overdue_min, status="Pending", priority="High"):
		t = frappe.get_doc({"doctype": "Housekeeping Task", "property": PROP_A,
		                    "room": self.room, "task_type": "Checkout Clean",
		                    "priority": priority, "status": "Pending"}
		                   ).insert(ignore_permissions=True)
		frappe.db.set_value("Housekeeping Task", t.name, {
			"due_by": add_to_date(now_datetime(), minutes=-overdue_min),
			"status": status})
		return t.name

	def level(self, name):
		return frappe.db.get_value("Housekeeping Task", name,
		                           ["escalation_level", "breached"])

	def test_escalation_ladder(self):
		from kamra.housekeeping import escalate_overdue_tasks
		from kamra.kamra.doctype.housekeeping_task.housekeeping_task import (
			sla_minutes,
		)
		sla = sla_minutes(PROP_A, "High")
		late = self.task(5)
		very_late = self.task(sla + 5)
		on_time = self.task(-30)
		done = self.task(sla + 5, status="Done")
		escalate_overdue_tasks()
		self.assertEqual(self.level(late), (1, 1))
		self.assertEqual(self.level(very_late), (2, 1))
		self.assertEqual(self.level(on_time)[0] or 0, 0)
		self.assertEqual(self.level(done)[0] or 0, 0)
		roles = {c.args[1] for c in self.notify.call_args_list
		         if c.args[0] == PROP_A}
		self.assertEqual(roles, {"Front Desk", "Hotel Admin"})

	def test_escalation_is_not_repeated(self):
		from kamra.housekeeping import escalate_overdue_tasks
		self.task(5)
		escalate_overdue_tasks()
		first = len([c for c in self.notify.call_args_list if c.args[0] == PROP_A])
		escalate_overdue_tasks()
		second = len([c for c in self.notify.call_args_list if c.args[0] == PROP_A])
		self.assertEqual(first, 1)
		self.assertEqual(second, 1)
