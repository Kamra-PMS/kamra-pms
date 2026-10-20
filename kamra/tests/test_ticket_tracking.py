"""Tickets: who has it, who solved it, the timeline, the old backlog."""

from __future__ import annotations

import frappe
from frappe.utils import add_to_date, now_datetime

from kamra import reports, tickets
from kamra.tests.audit_fixtures import PROP_A, TODAY, AuditTestCase, ensure_user, make_property


REAL_TODAY = str(now_datetime().date())  # tickets are stamped with the real clock


class TicketTrackingTestCase(AuditTestCase):
	properties = (PROP_A,)
	DESK = "ut.tkt.desk@test.local"
	HK = "ut.tkt.hk@test.local"
	LAW = "ut.tkt.nobody@test.local"

	def setUp(self):
		super().setUp()
		self.at(TODAY)
		make_property(PROP_A, business_date=TODAY)
		ensure_user(self.DESK, ["Front Desk"])
		ensure_user(self.HK, ["Housekeeping"])
		ensure_user(self.LAW, ["Accounts User"])

	def ticket(self, **kw):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- fixture
		doc = frappe.get_doc(dict({
			"doctype": "Service Ticket", "property": PROP_A, "subject": "UT towels",
			"category": "Housekeeping", "priority": "Medium"}, **kw)).insert(ignore_permissions=True)
		return doc.name

	def as_user(self, u):
		frappe.set_user(u)  # nosemgrep: frappe-setuser -- the staff persona

	def test_creation_is_on_the_timeline(self):
		t = self.ticket()
		self.as_user(self.DESK)
		d = tickets.ticket_detail(t)
		self.assertEqual([e["kind"] for e in d["events"]], ["Created"])

	def test_assign_records_who_and_when(self):
		t = self.ticket()
		self.as_user(self.DESK)
		d = tickets.assign_ticket(t, self.HK)
		self.assertEqual(d["assigned_to_user"], self.HK)
		self.assertEqual(d["assigned_by"], self.DESK)
		self.assertTrue(d["assigned_at"])
		self.assertTrue(d["first_response_at"])
		ev = [e for e in d["events"] if e["kind"] == "Assigned"][0]
		self.assertEqual((ev["by"], ev["to_value"]), (self.DESK, self.HK))

	def test_cannot_assign_to_someone_without_a_ticket_role(self):
		t = self.ticket()
		self.as_user(self.DESK)
		with self.assertRaises(frappe.ValidationError):
			tickets.assign_ticket(t, self.LAW)

	def test_resolver_is_recorded_and_shows_in_the_sla_report(self):
		t = self.ticket()
		self.as_user(self.HK)
		tickets.claim_ticket(t)
		d = tickets.resolve_ticket(t, "Delivered two towels")
		self.assertEqual(d["status"], "Resolved")
		self.assertEqual(d["resolved_by"], self.HK)
		self.assertEqual(d["resolution_note"], "Delivered two towels")
		self.assertIsNotNone(d["resolve_minutes"])
		self.as_user("Administrator")
		rep = reports.sla_report(PROP_A, REAL_TODAY, REAL_TODAY)
		self.assertIn(self.HK, [r["user"] for r in rep["by_resolver"]])

	def test_reopen_needs_a_reason_and_is_counted(self):
		t = self.ticket()
		self.as_user(self.DESK)
		tickets.resolve_ticket(t, "fixed")
		with self.assertRaises(frappe.ValidationError):
			tickets.reopen_ticket(t, "")
		d = tickets.reopen_ticket(t, "still dripping")
		self.assertEqual(d["status"], "Open")
		self.assertEqual(d["reopened_count"], 1)
		self.assertIsNone(d["resolved_by"])
		self.assertIn("Reopened", [e["kind"] for e in d["events"]])

	def test_start_takes_an_unassigned_ticket(self):
		t = self.ticket()
		self.as_user(self.HK)
		d = tickets.start_ticket(t)
		self.assertEqual((d["status"], d["assigned_to_user"]), ("In Progress", self.HK))

	def test_cannot_assign_a_finished_ticket(self):
		t = self.ticket()
		self.as_user(self.DESK)
		tickets.resolve_ticket(t, "done")
		with self.assertRaises(frappe.ValidationError):
			tickets.assign_ticket(t, self.HK)

	def test_search_views_and_counts(self):
		a = self.ticket(subject="UT leak")
		b = self.ticket(subject="UT wifi")
		self.as_user(self.DESK)
		tickets.claim_ticket(a)
		self.assertEqual(tickets.tickets_search(PROP_A, "mine")["tickets"][0]["name"], a)
		un = [r["name"] for r in tickets.tickets_search(PROP_A, "unassigned")["tickets"]]
		self.assertIn(b, un)
		self.assertNotIn(a, un)
		self.assertEqual([r["name"] for r in tickets.tickets_search(PROP_A, "all", q="wifi")["tickets"]], [b])
		tickets.resolve_ticket(a, "done")
		out = tickets.tickets_search(PROP_A, "resolved")
		self.assertEqual([r["name"] for r in out["tickets"]], [a])
		self.assertEqual(out["tickets"][0]["resolved_by"], self.DESK)
		self.assertGreaterEqual(out["counts"]["resolved"], 1)

	def test_old_open_tickets_stay_visible(self):
		t = self.ticket(subject="UT ancient")
		frappe.db.set_value("Service Ticket", t, "creation", add_to_date(now_datetime(), days=-20),
		                    update_modified=False)
		self.as_user(self.DESK)
		old = tickets.tickets_search(PROP_A, "open", older_than_days=7)["tickets"]
		self.assertIn(t, [r["name"] for r in old])
		self.assertGreaterEqual(old[0]["age_hours"], 24 * 19)
		self.as_user("Administrator")
		rep = reports.sla_report(PROP_A, REAL_TODAY, REAL_TODAY)
		self.assertIn(t, [r["name"] for r in rep["oldest_open"]])
		self.assertGreaterEqual(dict((a["label"], a["count"]) for a in rep["aging"])["Over 7 days"], 1)

	def test_legacy_ticket_without_events_still_has_a_detail(self):
		t = self.ticket()
		frappe.db.delete("Ticket Event", {"ticket": t})
		self.as_user(self.DESK)
		d = tickets.ticket_detail(t)
		self.assertEqual(d["events"][0]["kind"], "Created")

	def test_assignees_are_ticket_staff_only(self):
		self.as_user(self.DESK)
		users = {u["user"] for u in tickets.ticket_assignees(PROP_A)}
		self.assertIn(self.HK, users)
		self.assertNotIn(self.LAW, users)
