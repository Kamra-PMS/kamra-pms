"""#560: room status discrepancy cases, inspection pass rate and turn time,
booking links with a source tag. Each behind its module setting."""

from __future__ import annotations

import frappe

from kamra import housekeeping as hk
from kamra import public_api, reports
from kamra.tests.audit_fixtures import (
	PROP_A,
	TODAY,
	AuditTestCase,
	d,
	ensure_user,
	make_property,
	make_reservation,
	make_room,
	make_room_type,
)
from kamra.tests.test_billing_approvals_split import set_setting

MAID = "ut.hk560.maid@test.local"


def _task(room, task_type, status="Pending", **kw):
	doc = frappe.get_doc({"doctype": "Housekeeping Task", "property": PROP_A,
	                      "room": room, "task_type": task_type, "priority": "Medium",
	                      "status": "Pending", **kw}).insert(ignore_permissions=True)
	if status != "Pending":
		doc.status = status
		doc.save(ignore_permissions=True)
	return doc


class HkCasesAndLinksTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		make_property(PROP_A, business_date=TODAY)
		frappe.db.delete("Property Setting", {"property": PROP_A})
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")
		ensure_user(MAID, ["Housekeeping"])

	# room status cases -----------------------------------------------------

	def test_a_disagreement_becomes_a_case_with_an_owner_and_closes_with_a_reason(self):
		frappe.db.set_value("Room", self.room, "occupancy_status", "Occupied")  # no guest in house
		found = hk.room_discrepancies(PROP_A)
		self.assertEqual([r["room_id"] for r in found["detected"]], [self.room])
		out = hk.open_room_discrepancy(PROP_A, self.room, owner=MAID)
		self.assertEqual(out["owner"], MAID)
		found = hk.room_discrepancies(PROP_A)
		self.assertEqual(found["detected"], [])  # covered by the open case
		self.assertEqual([c["case_owner"] for c in found["cases"]], [MAID])
		with self.assertRaises(frappe.ValidationError):  # one open case per room
			hk.open_room_discrepancy(PROP_A, self.room)
		with self.assertRaises(frappe.ValidationError):  # a reason is required
			hk.close_room_discrepancy(out["case"], "")
		hk.close_room_discrepancy(out["case"], "Guest left early, board not released")
		doc = frappe.get_doc("Room Discrepancy", out["case"])
		self.assertEqual((doc.status, doc.close_reason),
		                 ("Closed", "Guest left early, board not released"))
		doc.status = "Open"  # can't be reopened from Desk / REST
		with self.assertRaises(frappe.PermissionError):
			doc.save(ignore_permissions=True)

	def test_a_room_both_sides_agree_on_gets_no_case(self):
		with self.assertRaises(frappe.ValidationError):
			hk.open_room_discrepancy(PROP_A, self.room)

	def test_cases_are_off_with_their_setting(self):
		set_setting(PROP_A, "hk_discrepancy_cases", 0)
		frappe.db.set_value("Room", self.room, "occupancy_status", "Occupied")
		self.assertFalse(hk.room_discrepancies(PROP_A)["enabled"])
		with self.assertRaises(frappe.ValidationError):
			hk.open_room_discrepancy(PROP_A, self.room)

	# pass rate and turn time -----------------------------------------------

	def test_pass_rate_counts_for_the_attendant_whose_clean_was_inspected(self):
		clean = _task(self.room, "Checkout Clean", "Done", assigned_to_user=MAID)
		self.assertTrue(frappe.db.get_value("Housekeeping Task", clean.name, "completed_on"))
		first = _task(self.room, "Inspection")
		self.assertEqual(first.clean_task, clean.name)
		out = hk.hk_fail_inspection(first.name, "Hair in the shower")
		self.assertEqual(frappe.db.get_value("Room", self.room, "housekeeping_status"), "Dirty")
		reclean = frappe.get_doc("Housekeeping Task", out["reclean"])
		self.assertEqual((reclean.assigned_to_user, reclean.task_type), (MAID, "Checkout Clean"))
		reclean.status = "Done"
		reclean.save(ignore_permissions=True)
		second = _task(self.room, "Inspection")
		self.assertEqual(second.clean_task, reclean.name)
		second.status = "Verified"
		second.save(ignore_permissions=True)
		self.assertEqual(frappe.db.get_value("Housekeeping Task", second.name,
		                                     "inspection_result"), "Passed")
		q = hk.hk_quality(PROP_A)
		maid = next(r for r in q["attendant"] if r["key"] == MAID)
		self.assertEqual((maid["inspected"], maid["passed"], maid["pass_rate"], maid["cleans"]),
		                 (2, 1, 50.0, 2))
		self.assertIsNotNone(maid["avg_turn_minutes"])
		std = next(r for r in q["room_type"] if r["key"] == self.rt)
		self.assertEqual(std["pass_rate"], 50.0)
		with self.assertRaises(frappe.ValidationError):  # a closed inspection can't fail
			hk.hk_fail_inspection(second.name, "late")

	def test_quality_is_off_with_its_setting(self):
		set_setting(PROP_A, "hk_quality_report", 0)
		self.assertFalse(hk.hk_quality(PROP_A)["enabled"])

	# booking links ---------------------------------------------------------

	def test_a_link_tag_is_cleaned_and_kept_only_when_links_are_on(self):
		self.assertEqual(public_api.clean_source_tag(PROP_A, " Insta bio/Nov! "), "Insta-bio-Nov")
		self.assertIsNone(public_api.clean_source_tag(PROP_A, ""))
		self.assertEqual(len(public_api.clean_source_tag(PROP_A, "x" * 200)), 60)
		set_setting(PROP_A, "booking_links", 0)
		self.assertIsNone(public_api.clean_source_tag(PROP_A, "newsletter"))

	def test_bookings_are_counted_per_source_tag(self):
		res = make_reservation(PROP_A, self.rt, d(1), d(3), status="Confirmed")
		frappe.db.set_value("Reservation", res.name, "source_tag", "newsletter")
		out = reports.booking_link_sources(PROP_A)
		self.assertTrue(out["enabled"])
		row = next(r for r in out["rows"] if r["tag"] == "newsletter")
		self.assertEqual((row["bookings"], row["room_nights"]), (1, 2))
