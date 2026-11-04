"""Frappe's setup wizard stays shut on a Kamra site."""

import json

import frappe
from frappe.tests import IntegrationTestCase

from kamra.setup_guard import close_frappe_setup_wizard

WIZARD = "frappe.desk.page.setup_wizard.setup_wizard."


def _user(email, role):
	if not frappe.db.exists("User", email):
		frappe.get_doc({"doctype": "User", "email": email, "first_name": "Guard",
		                "send_welcome_email": 0, "roles": [{"role": role}]}).insert(ignore_permissions=True)
	return email


class SetupGuardTestCase(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		close_frappe_setup_wizard()

	def test_install_and_migrate_mark_the_wizard_done(self):
		frappe.db.set_value("Installed Application", {"app_name": "frappe"}, "is_setup_complete", 0)
		frappe.db.set_single_value("System Settings", "setup_complete", 0)
		self.assertFalse(frappe.is_setup_complete())
		close_frappe_setup_wizard()
		close_frappe_setup_wizard()  # a second run changes nothing
		self.assertTrue(frappe.is_setup_complete())
		self.assertEqual(frappe.db.get_single_value("System Settings", "setup_complete"), 1)

	def test_staff_cannot_call_the_wizard_writes(self):
		from kamra import setup_guard
		desk = _user("guard.desk@test.local", "Front Desk")
		frappe.set_user(desk)  # nosemgrep: frappe-setuser -- the role under test
		with self.assertRaises(frappe.PermissionError):
			setup_guard.setup_complete(json.dumps({}))
		with self.assertRaises(frappe.PermissionError):
			setup_guard.initialize_system_settings_and_user(json.dumps({}), json.dumps({}))

	def test_a_system_manager_on_a_finished_site_changes_nothing(self):
		from kamra import setup_guard
		close_frappe_setup_wizard()
		before = frappe.db.get_value("User", "Administrator", "modified")
		self.assertEqual(setup_guard.setup_complete(json.dumps({})), {"status": "ok"})
		setup_guard.initialize_system_settings_and_user(
			json.dumps({}), json.dumps({"email": "Administrator", "password": "not-applied-9!"}))
		self.assertEqual(frappe.db.get_value("User", "Administrator", "modified"), before)

	def test_the_overrides_are_registered(self):
		hooks = frappe.get_hooks("override_whitelisted_methods")
		self.assertIn("kamra.setup_guard.setup_complete", hooks.get(WIZARD + "setup_complete"))
		self.assertIn("kamra.setup_guard.initialize_system_settings_and_user",
		              hooks.get(WIZARD + "initialize_system_settings_and_user"))
