"""Property scope for staff restricted to some hotels in a chain.

require_roles guards Kamra's own endpoints; these tests cover the paths
around it - Frappe's generic REST/Desk reads of Guest (which has no
property link for User Permissions to bite on), and upsert endpoints that
load a record by `name` before the caller's `property` is applied.
"""

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


def _stay(guest: str, prop: str) -> None:
	# validation (room types, rates) is beside the point here; the scope
	# rule only reads guest + property
	doc = frappe.get_doc({
		"doctype": "Reservation", "property": prop, "guest": guest,
		"room_type": "Scope Test", "status": "Confirmed",
		"check_in_date": nowdate(), "check_out_date": add_days(nowdate(), 1),
	})
	doc.set_new_name()
	doc.db_insert()


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
		_stay(self.mine, HOME)
		self.theirs = _guest("ScopeTheirs")
		_stay(self.theirs, OTHER)
		self.fresh = _guest("ScopeFresh")  # no stays anywhere yet

	def tearDown(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture teardown

	def as_desk(self):
		frappe.set_user(USER)  # nosemgrep: frappe-setuser -- acting as the restricted persona

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
		self.assertTrue({self.mine, self.theirs, self.fresh} <= names)

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
