"""The demo reset puts Kamra Agent back from site_config.json."""

import frappe

from kamra.scripts.reset_demo import restore_agent_from_site_config
from kamra.tests.audit_fixtures import PROP_A, AuditTestCase, make_property


class DemoAgentKeyTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		make_property(PROP_A)

	def test_agent_comes_back_from_site_config(self):
		frappe.conf.pop("kamra_agent_api_key", None)
		self.assertEqual(restore_agent_from_site_config(), 0)
		frappe.conf["kamra_agent_api_key"] = "sk-test-not-real"
		try:
			self.assertGreaterEqual(restore_agent_from_site_config(), 1)
			name = frappe.db.get_value("AI Assistant Settings", {"property": PROP_A})
			doc = frappe.get_doc("AI Assistant Settings", name)
			self.assertTrue(doc.enabled)
			self.assertEqual(doc.get_password("api_key"), "sk-test-not-real")
			restore_agent_from_site_config()  # idempotent: updates, no duplicate
			self.assertEqual(frappe.db.count("AI Assistant Settings", {"property": PROP_A}), 1)
		finally:
			frappe.conf.pop("kamra_agent_api_key", None)

	def test_reset_keeps_the_agent_settings(self):
		from kamra.scripts import reset_demo

		kept = {r.name for r in frappe.get_all(
			"DocType", filters={"module": "Kamra",
			                    "name": ("not in", list(reset_demo.KEEP_DOCTYPES))})}
		self.assertNotIn("AI Assistant Settings", kept)
		self.assertIn("Reservation", kept)
