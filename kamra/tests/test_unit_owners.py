"""Unit owners see their own units and nobody else's (#639).

Guest name and phone stay off unless the owner record says so. A login
that only has the Owner role is scoped to those rooms.
"""

from __future__ import annotations

import json

import frappe

from kamra import owners
from kamra.api import _post_folio_charge
from kamra.folio import open_folio
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


class UnitOwnerTest(AuditTestCase):
	properties = (PROP_A, PROP_B)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY)
		make_property(PROP_B, business_date=TODAY)
		rt = make_room_type(PROP_A)
		self.room_a = make_room(PROP_A, rt, "OA1")
		self.room_b = make_room(PROP_A, rt, "OB1")
		self.lina = make_guest("Lina", phone="999000111")
		self.omar = make_guest("Omar", phone="888000222")
		self.stay_a = make_reservation(
			PROP_A, rt, TODAY, d(2), status="Checked In",
			room=self.room_a, guest=self.lina)
		self.stay_b = make_reservation(
			PROP_A, rt, TODAY, d(2), status="Checked In",
			room=self.room_b, guest=self.omar)
		folio = open_folio(self.stay_a)
		_post_folio_charge(folio, "Room", "Night", 1000, reservation=self.stay_a.name)
		self.owner_a = ensure_user("ut.owner.a@example.com", ["Owner"])
		self.owner_b = ensure_user("ut.owner.b@example.com", ["Owner"])
		self.doc_a = frappe.get_doc({
			"doctype": "Unit Owner", "owner_name": "North wing",
			"property": PROP_A, "access": "Read only", "show_guest_contact": 0,
			"units": [{"room": self.room_a}],
			"users": [{"user": self.owner_a}],
		}).insert(ignore_permissions=True)
		self.doc_b = frappe.get_doc({
			"doctype": "Unit Owner", "owner_name": "South wing",
			"property": PROP_A, "access": "Manage", "show_guest_contact": 0,
			"units": [{"room": self.room_b}],
			"users": [{"user": self.owner_b}],
		}).insert(ignore_permissions=True)

	def test_an_owner_sees_only_their_unit_and_not_the_guest(self):
		frappe.set_user(self.owner_a)  # nosemgrep: frappe-setuser -- test fixture
		try:
			portal = owners.my_portal(PROP_A, TODAY, TODAY)
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		self.assertEqual([u["room"] for u in portal["units"]], [self.room_a])
		self.assertEqual(portal["bookings"][0]["guest"], "Guest")
		self.assertIsNone(portal["bookings"][0]["phone"])
		blob = json.dumps(portal)
		self.assertNotIn("Lina", blob)
		self.assertNotIn("Omar", blob)
		self.assertNotIn("999000111", blob)
		self.assertNotIn(self.stay_b.name, blob)
		posted = 0.0
		for kind in ("Room", "Extra Guests", "Cleaning Fee"):
			posted += sum(float(c.amount) for c in charges(self.stay_a.name, kind))
		self.assertGreater(posted, 0)
		self.assertEqual(portal["revenue"], round(posted, 2))
		self.assertEqual(portal["occupancy_pct"], 100)
		rooms = frappe.get_all(
			"User Permission",
			filters={"user": self.owner_a, "allow": "Room"}, pluck="for_value")
		self.assertIn(self.room_a, rooms)
		self.assertNotIn(self.room_b, rooms)

	def test_guest_contact_reveals_name_and_phone_only(self):
		self.doc_a.show_guest_contact = 1
		self.doc_a.save(ignore_permissions=True)
		frappe.set_user(self.owner_a)  # nosemgrep: frappe-setuser -- test fixture
		try:
			portal = owners.my_portal(PROP_A, TODAY, TODAY)
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		booking = portal["bookings"][0]
		self.assertIn("Lina", booking["guest"])
		self.assertEqual(booking["phone"], "999000111")
		self.assertNotIn("id_number", booking)
		self.assertNotIn("document", booking)

	def test_another_property_and_a_desk_login_are_refused(self):
		frappe.set_user(self.owner_a)  # nosemgrep: frappe-setuser -- test fixture
		try:
			with self.assertRaises(frappe.PermissionError):
				owners.my_portal(PROP_B, TODAY, TODAY)
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		desk = ensure_user("ut.owner.desk@example.com", ["Front Desk"])
		frappe.set_user(desk)  # nosemgrep: frappe-setuser -- test fixture
		try:
			with self.assertRaises(frappe.PermissionError):
				owners.my_portal(PROP_A, TODAY, TODAY)
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture

	def test_manage_can_hold_only_its_own_unit(self):
		frappe.set_user(self.owner_a)  # nosemgrep: frappe-setuser -- test fixture
		try:
			with self.assertRaises(frappe.PermissionError):
				owners.block_unit(PROP_A, self.room_a, d(3), d(5))
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		frappe.set_user(self.owner_b)  # nosemgrep: frappe-setuser -- test fixture
		try:
			with self.assertRaises(frappe.PermissionError):
				owners.block_unit(PROP_A, self.room_a, d(3), d(5))
			with self.assertRaisesRegex(frappe.ValidationError, "already booked") as caught:
				owners.block_unit(PROP_A, self.room_b, TODAY, d(2))
			self.assertNotIn("Omar", str(caught.exception))
			held = owners.block_unit(PROP_A, self.room_b, d(3), d(5))
			owners.release_block(held["name"])
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		self.assertEqual(
			frappe.db.get_value("Room Block", held["name"], "block_status"), "Released")

	def test_statement_is_revenue_minus_commission_and_names_nobody(self):
		self.doc_a.commission_percent = 10
		self.doc_a.save(ignore_permissions=True)
		frappe.set_user(self.owner_a)  # nosemgrep: frappe-setuser -- test fixture
		try:
			sheet = owners.my_statement(PROP_A, "2031-03")
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		self.assertGreater(sheet["revenue"], 0)
		self.assertEqual(sheet["commission"], round(sheet["revenue"] * 0.1, 2))
		self.assertEqual(sheet["payout"], round(sheet["revenue"] - sheet["commission"], 2))
		self.assertEqual(sheet["costs"], 0)
		blob = json.dumps(sheet)
		self.assertNotIn("Lina", blob)
		self.assertNotIn("Omar", blob)

	def test_one_overview_and_statement_across_an_owners_properties(self):
		"""#713: an owner with units at two properties sees both side by side,
		and another owner at one of them sees only their own."""
		rt_b = make_room_type(PROP_B)
		room_c = make_room(PROP_B, rt_b, "OC1")
		frappe.get_doc({
			"doctype": "Unit Owner", "owner_name": "Hill villa",
			"property": PROP_B, "access": "Read only", "commission_percent": 10,
			"units": [{"room": room_c}],
			"users": [{"user": self.owner_a}],
		}).insert(ignore_permissions=True)
		frappe.set_user(self.owner_a)  # nosemgrep: frappe-setuser -- test fixture
		try:
			both = owners.my_overview(TODAY, TODAY, TODAY[:7])
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		self.assertEqual(sorted(r["property"] for r in both["properties"]), sorted([PROP_A, PROP_B]))
		a = next(r for r in both["properties"] if r["property"] == PROP_A)
		self.assertGreater(a["revenue"], 0)
		self.assertEqual(both["totals"]["units"], 2)
		self.assertEqual(both["totals"]["room_nights"], 1)
		self.assertEqual(both["totals"]["occupancy_pct"], 50)
		self.assertEqual(both["totals"]["revenue"], round(sum(r["revenue"] for r in both["properties"]), 2))
		self.assertEqual(both["totals"]["statement"]["payout"],
		                 round(sum(r["statement"]["payout"] for r in both["properties"]), 2))
		blob = json.dumps(both)
		self.assertNotIn("Lina", blob)
		self.assertNotIn("Omar", blob)
		self.assertNotIn(self.room_b, blob)

		frappe.set_user(self.owner_b)  # nosemgrep: frappe-setuser -- test fixture
		try:
			one = owners.my_overview(TODAY, TODAY)
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		self.assertEqual([r["property"] for r in one["properties"]], [PROP_A])
		self.assertNotIn("statement", one["properties"][0])

		desk = ensure_user("ut.owner.desk2@example.com", ["Front Desk"])
		frappe.set_user(desk)  # nosemgrep: frappe-setuser -- test fixture
		try:
			with self.assertRaises(frappe.PermissionError):
				owners.my_overview(TODAY, TODAY)
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture

	def test_a_new_email_becomes_an_owner_login(self):
		owners.save_owner(
			PROP_A, "East wing", [self.room_a], ["ut.owner.new@example.com"])
		self.assertEqual(
			frappe.db.get_value("User", "ut.owner.new@example.com", "user_type"),
			"System User")
		self.assertIn(
			"Owner",
			[r.role for r in frappe.get_doc("User", "ut.owner.new@example.com").roles])
