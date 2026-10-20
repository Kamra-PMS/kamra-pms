"""Property scope for staff restricted to some hotels in a chain.

require_roles guards Kamra's own endpoints; these tests cover the paths
around it - Frappe's generic REST/Desk reads of Guest (which has no
property link for User Permissions to bite on), and upsert endpoints that
load a record by `name` before the caller's `property` is applied.
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from kamra import authz

HOME = "TEST Scope Home"
OTHER = "TEST Scope Other"
USER = "scope.desk@test.local"


def _property(name: str) -> str:
	if not frappe.db.exists("Property", name):
		frappe.get_doc({"doctype": "Property", "property_name": name}).insert(
			ignore_permissions=True)
	return name


def _guest(first: str) -> str:
	return frappe.get_doc({"doctype": "Guest", "first_name": first}).insert(
		ignore_permissions=True).name


def _stay(guest: str, prop: str) -> str:
	# validation (room types, rates) is beside the point here; the scope
	# rule only reads guest + property
	doc = frappe.get_doc({
		"doctype": "Reservation", "property": prop, "guest": guest,
		"room_type": "Scope Test", "status": "Confirmed",
		"check_in_date": nowdate(), "check_out_date": add_days(nowdate(), 1),
	})
	doc.set_new_name()
	doc.db_insert()
	return doc.name


def _record(doctype: str, prop: str) -> str:
	# a bare row is enough: the scope rule only reads the property link
	doc = frappe.get_doc({"doctype": doctype, "property": prop})
	doc.name = "TEST-SCOPE-" + frappe.generate_hash(length=10)
	doc.db_insert()
	return doc.name


class PropertyScopeTestCase(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture setup
		_property(HOME)
		_property(OTHER)
		if not frappe.db.exists("User", USER):
			frappe.get_doc({
				"doctype": "User", "email": USER, "first_name": "Scope",
				"enabled": 1, "user_type": "System User", "send_welcome_email": 0,
				"roles": [{"role": "Front Desk"}],
			}).insert(ignore_permissions=True)
		if not frappe.db.exists("User Permission", {"user": USER, "allow": "Property"}):
			frappe.get_doc({
				"doctype": "User Permission", "user": USER,
				"allow": "Property", "for_value": HOME,
			}).insert(ignore_permissions=True)
		frappe.clear_cache(user=USER)

		self.mine = _guest("ScopeMine")
		self.my_stay = _stay(self.mine, HOME)
		self.theirs = _guest("ScopeTheirs")
		self.their_stay = _stay(self.theirs, OTHER)
		self.fresh = _guest("ScopeFresh")  # no stays anywhere yet

	def tearDown(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture teardown

	def as_desk(self):
		frappe.set_user(USER)  # nosemgrep: frappe-setuser -- acting as the restricted persona

	def unscoped_desk(self):
		frappe.db.delete("User Permission", {"user": USER, "allow": "Property"})
		frappe.clear_cache(user=USER)
		self.as_desk()

	def test_strict_scope_refuses_staff_without_property_permissions(self):
		self.unscoped_desk()
		with patch.dict(frappe.conf, {"kamra_strict_property_scope": True}):
			with self.assertRaises(frappe.PermissionError):
				authz.assert_property_access(OTHER)
			self.assertEqual(authz.restricted_properties(), set())

	def test_legacy_scope_keeps_unscoped_staff_chain_wide(self):
		self.unscoped_desk()
		for strict in (None, False):
			with patch.dict(frappe.conf, {"kamra_strict_property_scope": strict}):
				self.assertIsNone(authz.restricted_properties())
				authz.assert_property_access(OTHER)

	def test_strict_scope_keeps_explicit_property_permissions(self):
		self.as_desk()
		with patch.dict(frappe.conf, {"kamra_strict_property_scope": True}):
			authz.assert_property_access(HOME)
			with self.assertRaises(frappe.PermissionError):
				authz.assert_property_access(OTHER)

	def test_strict_scope_keeps_administrator_chain_wide(self):
		with patch.dict(frappe.conf, {"kamra_strict_property_scope": True}):
			self.assertIsNone(authz.restricted_properties())
			authz.assert_property_access(OTHER)

	def test_strict_scope_keeps_system_manager_chain_wide(self):
		user = frappe.get_doc("User", USER)
		user.add_roles("System Manager")
		try:
			self.unscoped_desk()
			with patch.dict(frappe.conf, {"kamra_strict_property_scope": True}):
				self.assertIsNone(authz.restricted_properties())
				authz.assert_property_access(OTHER)
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- fixture cleanup
			user.remove_roles("System Manager")

	def test_strict_scope_does_not_exempt_kamra_agent(self):
		user = frappe.get_doc("User", USER)
		user.add_roles("Kamra Agent")
		try:
			self.unscoped_desk()
			with patch.dict(frappe.conf, {"kamra_strict_property_scope": True}):
				self.assertEqual(authz.restricted_properties(), set())
				with self.assertRaises(frappe.PermissionError):
					authz.assert_property_access(OTHER)
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- fixture cleanup
			user.remove_roles("Kamra Agent")

	def test_strict_scope_reads_site_config_as_integer(self):
		self.unscoped_desk()
		with patch.dict(frappe.conf, {"kamra_strict_property_scope": "0"}):
			self.assertIsNone(authz.restricted_properties())
		with patch.dict(frappe.conf, {"kamra_strict_property_scope": "1"}):
			self.assertEqual(authz.restricted_properties(), set())

	# ── strict scope on Frappe's own list / document reads ─────────────

	def listed_properties(self, doctype="Reservation"):
		return set(frappe.get_list(doctype, filters={"property": ["in", [HOME, OTHER]]},
		                           pluck="property", limit_page_length=0))

	def test_legacy_scope_lists_every_property_to_unscoped_staff(self):
		self.unscoped_desk()
		self.assertEqual(self.listed_properties(), {HOME, OTHER})
		self.assertTrue(frappe.has_permission("Reservation", "read", self.their_stay))

	def test_strict_scope_lists_nothing_to_unscoped_staff(self):
		self.unscoped_desk()
		with patch.dict(frappe.conf, {"kamra_strict_property_scope": 1}):
			self.assertEqual(self.listed_properties(), set())
			self.assertFalse(frappe.has_permission("Reservation", "read", self.their_stay))
			with self.assertRaises(frappe.PermissionError):
				frappe.client.get("Reservation", self.their_stay)

	def test_strict_scope_lists_only_permitted_property(self):
		self.as_desk()
		with patch.dict(frappe.conf, {"kamra_strict_property_scope": 1}):
			self.assertEqual(self.listed_properties(), {HOME})
			self.assertTrue(frappe.has_permission("Reservation", "read", self.my_stay))
			self.assertFalse(frappe.has_permission("Reservation", "read", self.their_stay))

	def test_strict_scope_covers_property_linked_doctypes(self):
		names = {dt: _record(dt, OTHER) for dt in ("Folio", "Room", "Housekeeping Task")}
		user = frappe.get_doc("User", USER)
		user.add_roles("Hotel Admin")
		try:
			self.unscoped_desk()
			with patch.dict(frappe.conf, {"kamra_strict_property_scope": 1}):
				for doctype, name in names.items():
					self.assertEqual(self.listed_properties(doctype), set(), doctype)
					self.assertFalse(frappe.has_permission(doctype, "read", name), doctype)
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- fixture cleanup
			user.remove_roles("Hotel Admin")

	def test_strict_scope_keeps_system_manager_lists_chain_wide(self):
		user = frappe.get_doc("User", USER)
		user.add_roles("System Manager")
		try:
			self.unscoped_desk()
			with patch.dict(frappe.conf, {"kamra_strict_property_scope": 1}):
				self.assertEqual(self.listed_properties(), {HOME, OTHER})
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- fixture cleanup
			user.remove_roles("System Manager")

	def test_every_property_linked_doctype_is_scoped(self):
		linked = {
			row.parent for row in frappe.get_all(
				"DocField", filters={"fieldname": "property", "fieldtype": "Link",
				                     "options": "Property", "parenttype": "DocType"},
				fields=["parent"])
			if frappe.db.get_value("DocType", row.parent, "module") == "Kamra"
			and not frappe.get_meta(row.parent).istable
			and not frappe.get_meta(row.parent).issingle
		}
		self.assertLessEqual({"Reservation", "Folio", "Room", "Housekeeping Task"}, linked)
		queries = frappe.get_hooks("permission_query_conditions")
		checks = frappe.get_hooks("has_permission")
		for doctype in sorted(linked):
			self.assertIn("kamra.authz.property_query_conditions", queries.get(doctype, []), doctype)
			self.assertIn("kamra.authz.property_has_permission", checks.get(doctype, []), doctype)

	def test_strict_scope_does_not_exempt_hotel_admin(self):
		user = frappe.get_doc("User", USER)
		user.add_roles("Hotel Admin")
		try:
			self.unscoped_desk()
			with patch.dict(frappe.conf, {"kamra_strict_property_scope": True}):
				with self.assertRaises(frappe.PermissionError):
					authz.assert_property_access(OTHER)
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- fixture cleanup
			user.remove_roles("Hotel Admin")

	# ── Frappe's own REST / Desk paths ─────────────────────────────────

	def test_guest_list_hides_other_properties_guests(self):
		self.as_desk()
		names = set(frappe.get_list("Guest", pluck="name", limit_page_length=0))
		self.assertIn(self.mine, names)
		self.assertIn(self.fresh, names)
		self.assertNotIn(self.theirs, names)

	def test_guest_doc_read_refused_for_other_property(self):
		self.as_desk()
		self.assertTrue(frappe.has_permission("Guest", "read", self.mine))
		self.assertFalse(frappe.has_permission("Guest", "read", self.theirs))
		with self.assertRaises(frappe.PermissionError):
			frappe.client.get("Guest", self.theirs)

	def test_unrestricted_staff_still_see_every_guest(self):
		self.assertEqual(authz.guest_query_conditions("Administrator"), "")
		names = set(frappe.get_list("Guest", pluck="name", limit_page_length=0))
		self.assertLessEqual({self.mine, self.theirs, self.fresh}, names)

	# ── Kamra endpoints ────────────────────────────────────────────────

	def test_guest_argument_is_scoped_by_default(self):
		from kamra.api import create_ticket
		self.as_desk()
		with self.assertRaises(frappe.PermissionError):
			create_ticket(HOME, "Towels", "Housekeeping", guest=self.theirs)

	def test_upsert_cannot_take_over_other_property_record(self):
		from kamra.api import save_hurdle_rate
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- fixture
		theirs = frappe.get_doc({"doctype": "Hurdle Rate", "property": OTHER,
		                         "occupancy_from": 80}).insert(ignore_permissions=True)
		self.as_desk()
		with self.assertRaises(frappe.PermissionError):
			save_hurdle_rate(HOME, 10, name=theirs.name)
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- verify
		self.assertEqual(frappe.db.get_value("Hurdle Rate", theirs.name, "property"), OTHER)
