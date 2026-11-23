"""#639 beyond the portal: owners scoped by unit type, a monthly statement
with per-unit commission and costs, and Manage owners booking and pricing
their own units through the desk's own checks."""

from __future__ import annotations

import frappe

from kamra import owners
from kamra.install import AGENT_EMAIL
from kamra.tests.audit_fixtures import PROP_A, TODAY, d, ensure_user, make_room, make_room_type
from kamra.tests.test_unit_owners import UnitOwnerTest


def _as(user, fn, *args, **kwargs):
	frappe.set_user(user)  # nosemgrep: frappe-setuser -- test fixture
	try:
		return fn(*args, **kwargs)
	finally:
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture


class OwnerAccountsTest(UnitOwnerTest):

	def setUp(self):
		super().setUp()
		ensure_user(AGENT_EMAIL, ["Kamra Agent"])
		# a unit type the south-wing owner holds outright
		self.villa = make_room_type(PROP_A, "VIL", base_price=3000)
		self.villa_1 = make_room(PROP_A, self.villa, "OV1")
		self.doc_b.append("room_types", {"room_type": self.villa})
		self.doc_b.save(ignore_permissions=True)

	def _perms(self, user):
		return set(frappe.get_all("User Permission", pluck="for_value",
		                          filters={"user": user, "allow": "Room"}))

	def test_a_unit_type_covers_every_unit_including_new_ones(self):
		self.assertEqual(owners.owned_rooms(self.doc_b), [self.room_b, self.villa_1])
		self.assertIn(self.villa_1, self._perms(self.owner_b))
		villa_2 = make_room(PROP_A, self.villa, "OV2")
		self.assertIn(villa_2, self._perms(self.owner_b))
		self.assertNotIn(villa_2, self._perms(self.owner_a))
		portal = _as(self.owner_b, owners.my_portal, PROP_A, TODAY, TODAY)
		self.assertEqual({u["room"] for u in portal["units"]},
		                 {self.room_b, self.villa_1, villa_2})

	def test_statement_takes_unit_commission_and_costs_off_the_payout(self):
		self.doc_a.commission_percent = 20
		self.doc_a.units[0].commission_percent = 10
		self.doc_a.save(ignore_permissions=True)
		owners.add_owner_cost(self.doc_a.name, TODAY, "Deep clean", 50, room=self.room_a)
		with self.assertRaises(frappe.ValidationError):  # not their unit
			owners.add_owner_cost(self.doc_a.name, TODAY, "Paint", 10, room=self.room_b)
		out = _as(self.owner_a, owners.my_statement, PROP_A, TODAY[:7])
		line = out["lines"][0]
		self.assertEqual((line["room"], line["commission_percent"]), (self.room_a, 10))
		self.assertAlmostEqual(out["commission"], round(out["revenue"] * 0.10, 2), 2)
		self.assertEqual(out["costs"], 50)
		self.assertAlmostEqual(out["payout"], out["revenue"] - out["commission"] - 50, 2)
		self.assertGreater(out["revenue"], 0)

	def test_manage_books_its_own_unit_through_the_desk(self):
		with self.assertRaises(frappe.PermissionError):  # read only
			_as(self.owner_a, owners.book_unit, PROP_A, self.room_a, d(3), d(5), "Guest A")
		with self.assertRaises(frappe.PermissionError):  # not theirs
			_as(self.owner_b, owners.book_unit, PROP_A, self.room_a, d(3), d(5), "Guest A")
		out = _as(self.owner_b, owners.book_unit, PROP_A, self.room_b, d(3), d(5), "Guest B")
		res = frappe.get_doc("Reservation", out["reservation"])
		self.assertEqual((res.room, res.booked_by_name), (self.room_b, self.owner_b))
		with self.assertRaises(frappe.ValidationError):  # the desk's clash check
			_as(self.owner_b, owners.book_unit, PROP_A, self.room_b, d(4), d(6), "Guest C")

	def test_manage_prices_only_a_unit_type_it_owns_outright(self):
		with self.assertRaises(frappe.PermissionError):  # STD has the north wing's unit too
			_as(self.owner_b, owners.set_unit_rate, PROP_A,
			    frappe.db.get_value("Room", self.room_b, "room_type"), d(3), d(5), 1500)
		out = _as(self.owner_b, owners.set_unit_rate, PROP_A, self.villa, d(3), d(5), 3500)
		season = frappe.get_doc("Season", out["season"])
		self.assertEqual((season.room_type, float(season.adjustment_value)), (self.villa, 3500))
		with self.assertRaises(frappe.PermissionError):  # read only
			_as(self.owner_a, owners.set_unit_rate, PROP_A, self.villa, d(3), d(5), 3500)
