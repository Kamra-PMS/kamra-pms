"""An open tab refreshes a CSRF token that went stale after a sign-in in
another tab (#467): kamra.api.csrf_token hands out the session's current
token, and nothing to a guest."""

import frappe
from frappe.tests import IntegrationTestCase

from kamra import api


class CsrfRefreshTestCase(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture teardown

	def test_signed_in_user_gets_the_session_token(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		self.assertEqual(api.csrf_token(), frappe.sessions.get_csrf_token())

	def test_guest_gets_none(self):
		frappe.set_user("Guest")  # nosemgrep: frappe-setuser -- test fixture
		self.assertIsNone(api.csrf_token())
