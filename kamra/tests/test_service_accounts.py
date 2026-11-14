"""Scoped service accounts: a key reaches only its scope and properties,
revoking stops it at once, and every call is in the Agent Action Log."""

from types import SimpleNamespace

import frappe
from frappe.tests import IntegrationTestCase

from kamra import service_accounts as sa
from kamra.mcp_access import property_policy, tool_refusal
from kamra.mcp_tools import BY_NAME

HOME = "TEST SA Home"
OTHER = "TEST SA Other"


def _property(name: str) -> str:
	if not frappe.db.exists("Property", name):
		frappe.get_doc({"doctype": "Property", "property_name": name}).insert(
			ignore_permissions=True)
	return name


def _request(path: str, method: str = "GET", body: bytes = b"", headers=None):
	return SimpleNamespace(path=path, method=method, headers=headers or {},
	                       get_data=lambda: body)


class ServiceAccountTestCase(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture setup
		_property(HOME)
		_property(OTHER)
		self.acct = sa.create_service_account("TEST reports app", ["reports.read"], [HOME])

	def tearDown(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture teardown
		frappe.local.cache.pop("kamra_service_accounts", None)
		frappe.db.rollback()

	def _as_account(self):
		frappe.local.cache.pop("kamra_service_accounts", None)
		frappe.set_user(self.acct["user"])  # nosemgrep: frappe-setuser -- acting as the service account under test
		return sa.account_for()

	def test_every_scope_is_grantable(self):
		for name, scope in sa.SCOPES.items():
			for tool in scope["tools"]:
				self.assertIn(tool, BY_NAME, f"{name}: unknown tool {tool}")
			roles = sa.scope_roles([name])
			self.assertFalse(roles & {"Hotel Admin", "System Manager", "Administrator"}, name)

	def test_scope_gate_on_rest_and_mcp(self):
		account = self._as_account()
		self.assertIsNotNone(account)
		self.assertIsNone(sa.refusal(account, "/api/method/kamra.reports.manager_flash"))
		self.assertIsNone(sa.refusal(account, "/api/v2/method/kamra.books.balance_sheet"))
		self.assertIsNone(sa.refusal(account, "/mcp"))
		for path in ("/api/method/kamra.api.get_folio", "/api/method/kamra.api.check_in",
		             "/api/resource/Guest", "/api/v2/document/Folio", "/app/folio",
		             "/api/method/kamra.assistant.chat", "/"):
			self.assertTrue(sa.refusal(account, path), path)

		policy = property_policy(HOME)
		self.assertIsNone(tool_refusal(BY_NAME["manager_flash"], "read", policy))
		self.assertTrue(tool_refusal(BY_NAME["get_folio"], "read", policy))
		self.assertTrue(tool_refusal(BY_NAME["create_booking"], "manage", policy))

	def test_enforce_scope_raises_before_the_endpoint(self):
		self._as_account()
		frappe.local.request = _request("/api/method/kamra.api.get_folio")
		try:
			with self.assertRaises(frappe.PermissionError):
				sa.enforce_scope()
			frappe.local.request = _request("/api/method/kamra.reports.manager_flash")
			sa.enforce_scope()
		finally:
			frappe.local.request = None
			frappe.local.flags.kamra_service_refusal = None

	def test_limited_to_its_properties(self):
		from kamra.authz import assert_property_access, restricted_properties

		self.assertEqual(restricted_properties(self.acct["user"]), {HOME})
		self._as_account()
		with self.assertRaises(frappe.PermissionError):
			assert_property_access(OTHER)

	def test_revoke_stops_access_at_once(self):
		from kamra.mcp_http import _key_user

		key, secret = self.acct["api_key"], self.acct["api_secret"]
		self.assertEqual(_key_user(key, secret), self.acct["user"])
		sa.revoke_service_account(self.acct["name"])
		self.assertIsNone(_key_user(key, secret))
		self.assertFalse(frappe.db.get_value("User", self.acct["user"], "enabled"))
		account = self._as_account()
		self.assertTrue(sa.refusal(account, "/api/method/kamra.reports.manager_flash"))

	def test_rotate_replaces_the_secret(self):
		from kamra.mcp_http import _key_user

		new = sa.rotate_service_account_key(self.acct["name"])
		self.assertIsNone(_key_user(self.acct["api_key"], self.acct["api_secret"]))
		self.assertEqual(_key_user(new["api_key"], new["api_secret"]), self.acct["user"])

	def test_every_call_is_logged(self):
		self._as_account()
		frappe.local.flags.kamra_service_refusal = None
		real_commit, frappe.db.commit = frappe.db.commit, lambda *a, **k: None
		try:
			sa.after_request(_request("/api/method/kamra.reports.manager_flash"),
			                 SimpleNamespace(status_code=200))
			frappe.local.flags.kamra_service_refusal = "Outside this service account's scope"
			sa.after_request(_request("/api/method/kamra.api.get_folio"),
			                 SimpleNamespace(status_code=403))
			sa.after_request(
				_request("/mcp", "POST",
				         b'{"jsonrpc":"2.0","id":1,"method":"tools/call",'
				         b'"params":{"name":"manager_flash"}}'),
				SimpleNamespace(status_code=200))
		finally:
			frappe.db.commit = real_commit
			frappe.local.flags.kamra_service_refusal = None
		rows = frappe.get_all(
			"Agent Action Log",
			filters={"action_type": "service_account.call", "actor": self.acct["user"]},
			fields=["rationale", "approval_status", "action_channel", "property"],
			order_by="creation asc")
		self.assertEqual(len(rows), 3)
		self.assertEqual(rows[0].approval_status, "Executed")
		self.assertEqual(rows[0].property, HOME)
		self.assertEqual(rows[1].approval_status, "Rejected")
		self.assertIn("kamra.api.get_folio", rows[1].rationale)
		self.assertEqual(rows[2].action_channel, "MCP")
		self.assertIn("manager_flash", rows[2].rationale)

	def test_only_it_manages_accounts(self):
		self._as_account()
		with self.assertRaises(frappe.PermissionError):
			sa.create_service_account("x", ["reports.read"], [HOME])
