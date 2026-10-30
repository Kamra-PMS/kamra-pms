"""Remote MCP OAuth + HTTP — needs a Frappe site (IntegrationTestCase)."""

from __future__ import annotations

import json
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch

import frappe
from frappe.tests import IntegrationTestCase

from kamra import mcp_access, mcp_http, mcp_oauth
from kamra.mcp_tools import BY_NAME
from kamra.tests.fixtures import PROPERTY, build, ensure_roles_and_users


class TestMCPFrameworkAuth(unittest.TestCase):
	"""Exercise Frappe's auth gate and final response processing without a database."""

	def setUp(self):
		self.stack = ExitStack()
		self.addCleanup(self.stack.close)
		self.context = SimpleNamespace(
			request=SimpleNamespace(path="/mcp", method="GET", headers={"Authorization": "Bearer test-token"}),
			response_headers={}, conf=frappe._dict(allow_cors=None),
		)
		self.framework = Mock()
		self.framework.local = self.context
		self.framework.conf = frappe._dict()
		self.framework.session = SimpleNamespace(user="Guest")
		self.framework.AuthenticationError = frappe.AuthenticationError
		self.framework.get_request_header.return_value = "Bearer test-token"
		self.framework.get_hooks.return_value = ["kamra.mcp_http.authenticate"]
		self.framework.get_attr.return_value = mcp_http.authenticate
		self.framework.db.get_value.return_value = 1
		self.framework.set_user.side_effect = lambda user: setattr(self.framework.session, "user", user)
		self.framework.monitor.get_trace_id.return_value = None
		self.framework._dev_server = False
		self.stack.enter_context(patch.object(mcp_http, "frappe", self.framework))
		self.stack.enter_context(patch.object(mcp_http, "protected_resource_url",
			return_value="https://hotel.example/mcp/.well-known/oauth-protected-resource"))

	def validate_auth(self):
		from frappe import auth

		with patch.object(auth, "frappe", self.framework), \
				patch.object(auth, "validate_oauth"), patch.object(auth, "validate_auth_via_api_keys"), \
				patch.object(auth, "validate_ip_address", create=True) as check_ip:
			auth.validate_auth()
			return check_ip

	def test_valid_kamra_token_passes_frappe_authentication_gate(self):
		with patch.object(mcp_http, "lookup_access_token", return_value=SimpleNamespace(user="staff@example.test")) as lookup:
			self.validate_auth()
		lookup.assert_called_once_with("test-token")
		self.assertEqual(self.framework.session.user, "staff@example.test")
		self.framework.db.get_value.assert_called_once_with("User", "staff@example.test", "enabled")

	def test_invalid_expired_or_revoked_token_is_rejected(self):
		with patch.object(mcp_http, "lookup_access_token", return_value=None):
			with self.assertRaises(frappe.AuthenticationError):
				self.validate_auth()
		self.framework.set_user.assert_not_called()

	def test_disabled_user_is_rejected(self):
		self.framework.db.get_value.return_value = 0
		with patch.object(mcp_http, "lookup_access_token", return_value=SimpleNamespace(user="disabled@example.test")):
			with self.assertRaises(frappe.AuthenticationError):
				self.validate_auth()
		self.framework.set_user.assert_not_called()

	def test_other_routes_and_disabled_mcp_do_not_authenticate_kamra_tokens(self):
		for path, disabled in (("/api/method/ping", False), ("/mcp/oauth/token", False),
		                       ("/mcp-other", False), ("/mcp", True)):
			with self.subTest(path=path, disabled=disabled):
				self.context.request.path = path
				self.framework.conf.kamra_mcp_disabled = disabled
				with patch.object(mcp_http, "lookup_access_token") as lookup:
					mcp_http.authenticate()
				lookup.assert_not_called()
		self.framework.set_user.assert_not_called()

	def test_mcp_challenge_survives_frappe_final_response_processing(self):
		from frappe import app
		from werkzeug.wrappers import Response

		for status in (401, 403):
			with self.subTest(status=status):
				self.context.response_headers.clear()
				response = Response(status=status)
				mcp_http.after_request(self.context.request, response)
				with patch.object(app, "frappe", self.framework), \
						patch.object(app, "is_oauth_metadata_enabled", return_value=True), \
						patch.object(app, "get_resource_url", return_value="https://hotel.example"):
					app.process_response(response)
				self.assertIn('/mcp/.well-known/oauth-protected-resource', response.headers['WWW-Authenticate'])
				self.assertIn('scope="kamra.mcp"', response.headers['WWW-Authenticate'])

	def test_other_responses_keep_frappe_oauth_metadata(self):
		from werkzeug.wrappers import Response

		for path, status, disabled in (("/api/method/ping", 401, False),
		                               ("/mcp/oauth/token", 403, False),
		                               ("/mcp", 200, False), ("/mcp", 404, False),
		                               ("/mcp", 401, True)):
			with self.subTest(path=path, status=status, disabled=disabled):
				self.context.request.path = path
				self.framework.conf.kamra_mcp_disabled = disabled
				response = Response(status=status)
				response.headers['WWW-Authenticate'] = 'Bearer realm="Frappe"'
				mcp_http.after_request(self.context.request, response)
				self.assertEqual(response.headers['WWW-Authenticate'], 'Bearer realm="Frappe"')
				self.assertEqual(self.context.response_headers, {})

	def test_standard_scoped_discovery_uses_kamra_instead_of_frappe(self):
		from werkzeug.wrappers import Response

		for path, function, document in (
			("/.well-known/oauth-authorization-server/mcp/oauth", "authorization_server_doc",
			 {"issuer": "https://hotel.example/mcp/oauth"}),
			("/.well-known/oauth-protected-resource/mcp", "protected_resource_doc",
			 {"resource": "https://hotel.example/mcp"}),
		):
			with self.subTest(path=path):
				self.context.request.path = path
				response = Response('{"issuer": "https://hotel.example"}', content_type="application/json")
				with patch.object(mcp_http, function, return_value=document):
					mcp_http.after_request(self.context.request, response)
				self.assertEqual(response.get_json(), document)
				self.assertEqual(response.status_code, 200)
				self.assertEqual(response.headers['Cache-Control'], 'no-store')

	def test_root_oauth_discovery_remains_frappe(self):
		from werkzeug.wrappers import Response

		for path in ("/.well-known/oauth-protected-resource", "/.well-known/oauth-authorization-server"):
			self.context.request.path = path
			response = Response('{"issuer": "https://hotel.example"}', content_type="application/json")
			mcp_http.after_request(self.context.request, response)
			self.assertEqual(response.get_json(), {"issuer": "https://hotel.example"})


class FakeRequest:
	def __init__(self, method="GET", data=b"", headers=None, args=None, form=None):
		self.method = method
		self.headers = headers or {}
		self.args = args or {}
		self.form = form or {}
		self._data = data if isinstance(data, bytes) else data.encode("utf-8")

	def get_data(self):
		return self._data


class TestOAuthHelpers(IntegrationTestCase):
	def test_pkce_and_redirect_allowlist(self):
		verifier = "a" * 43
		challenge = mcp_oauth.pkce_s256(verifier)
		self.assertEqual(challenge, mcp_oauth.pkce_s256(verifier))
		self.assertNotEqual(challenge, verifier)
		self.assertTrue(mcp_oauth.redirect_uri_allowed(
			"https://claude.ai/api/mcp/auth_callback"))
		self.assertTrue(mcp_oauth.redirect_uri_allowed(
			"http://127.0.0.1:3118/callback"))
		self.assertTrue(mcp_oauth.redirect_uri_allowed(
			"http://localhost:9/callback"))
		self.assertFalse(mcp_oauth.redirect_uri_allowed(
			"https://evil.example/steal"))
		# ChatGPT: the stable callback and the per-connection form, nothing else
		self.assertTrue(mcp_oauth.redirect_uri_allowed(
			"https://chatgpt.com/connector_platform_oauth_redirect"))
		self.assertTrue(mcp_oauth.redirect_uri_allowed(
			"https://chatgpt.com/connector/oauth/abc_123-XYZ"))
		for bad in ("https://chatgpt.com/connector/oauth/a/b",
		            "https://chatgpt.com/connector/oauth/abc?x=1",
		            "https://chatgpt.com/other",
		            "http://chatgpt.com/connector_platform_oauth_redirect",
		            "https://evil.chatgpt.com.example/connector/oauth/abc"):
			self.assertFalse(mcp_oauth.redirect_uri_allowed(bad), bad)
		self.assertFalse(mcp_oauth.is_public_https("http://hotel.example"))
		self.assertFalse(mcp_oauth.is_public_https("https://localhost"))
		self.assertTrue(mcp_oauth.is_public_https("https://pms.example.com"))


class TestExtraRedirects(IntegrationTestCase):
	def tearDown(self):
		frappe.db.set_default(mcp_access.REDIRECTS_KEY, "[]")
		# handle_register commits, so the list must be cleared for real
		frappe.db.commit()  # nosemgrep: frappe-manual-commit -- undo the site-wide test value

	def setUp(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- IT changes the site-wide list
		frappe.db.set_default(mcp_access.REDIRECTS_KEY, "[]")

	def test_admin_added_redirect_is_exact_and_https_only(self):
		n8n = "https://n8n.hotel.example/rest/oauth2-credential/callback"
		self.assertFalse(mcp_oauth.redirect_uri_allowed(n8n))
		mcp_access.set_extra_redirect_uris([n8n])
		self.assertTrue(mcp_oauth.redirect_uri_allowed(n8n))
		self.assertFalse(mcp_oauth.redirect_uri_allowed(n8n + "/x"))
		self.assertFalse(mcp_oauth.redirect_uri_allowed(n8n.replace("n8n.", "n9n.")))
		for bad in ("http://n8n.hotel.example/cb", "https://*.hotel.example/cb",
		            "https://n8n.hotel.example/cb#x", "n8n.hotel.example/cb"):
			with self.assertRaises(frappe.ValidationError):
				mcp_access.set_extra_redirect_uris([bad])
		status, body = mcp_oauth.handle_register({"redirect_uris": [n8n]})
		self.assertEqual(status, 201, body)

	def test_only_it_can_change_redirects(self):
		frappe.set_user("banquet.sales@test.local")  # nosemgrep: frappe-setuser -- a non-IT user must be refused
		try:
			with self.assertRaises(frappe.PermissionError):
				mcp_access.set_extra_redirect_uris(["https://x.example/cb"])
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- restore admin

	def test_metadata_advertises_iss_and_no_cimd(self):
		doc = mcp_oauth.authorization_server_doc()
		self.assertTrue(doc["authorization_response_iss_parameter_supported"])
		self.assertFalse(doc["client_id_metadata_document_supported"])


class TestRemoteMCP(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture sets admin before seeding MCP OAuth data
		ensure_roles_and_users()
		build()
		self.property = PROPERTY
		# AI access on, nothing blocked: the switches persist across tests
		frappe.db.set_value("Property", PROPERTY, {
			"mcp_enabled": 1, "mcp_read_only": 0, "mcp_blocked_tools": ""})

	def tearDown(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture restores admin after MCP OAuth tests

	def _register(self, redirect="https://claude.ai/api/mcp/auth_callback"):
		status, body = mcp_oauth.handle_register({
			"client_name": "Claude",
			"redirect_uris": [redirect],
			"token_endpoint_auth_method": "none",
		})
		self.assertEqual(status, 201)
		return body["client_id"]

	def _grant_tokens(self, user, *, property=None):
		from frappe.utils import add_to_date, now_datetime

		client_id = self._register()
		verifier = "b" * 43
		grant = frappe.get_doc({
			"doctype": "MCP OAuth Grant",
			"user": user,
			"property": property or self.property,
			"client": client_id,
			"redirect_uri": "https://claude.ai/api/mcp/auth_callback",
			"scope": "kamra.mcp",
			"code_hash": mcp_oauth.hash_token("spent"),
			"code_challenge": mcp_oauth.pkce_s256(verifier),
			"code_expires": add_to_date(now_datetime(), minutes=5),
			"revoked": 0,
		}).insert(ignore_permissions=True)
		status, tokens = mcp_oauth._issue_tokens(grant)
		self.assertEqual(status, 200)
		self.assertTrue(tokens["access_token"])
		self.assertTrue(tokens["refresh_token"])
		return tokens

	def test_unauthenticated_mcp_is_401_with_resource_metadata(self):
		resp = mcp_http.dispatch("mcp", FakeRequest("POST", data=b"{}"))
		self.assertEqual(resp.status_code, 401)
		www = resp.headers.get("WWW-Authenticate") or ""
		self.assertIn("resource_metadata=", www)
		self.assertIn("/mcp/.well-known/oauth-protected-resource", www)

	def test_dcr_rejects_foreign_redirect(self):
		status, body = mcp_oauth.handle_register({
			"redirect_uris": ["https://evil.example/cb"],
		})
		self.assertEqual(status, 400)
		self.assertEqual(body["error"], "invalid_redirect_uri")

	def test_token_requires_pkce(self):
		client_id = self._register()
		code = mcp_oauth.new_token()
		frappe.get_doc({
			"doctype": "MCP OAuth Grant",
			"user": "Administrator",
			"property": self.property,
			"client": client_id,
			"redirect_uri": "https://claude.ai/api/mcp/auth_callback",
			"scope": "kamra.mcp",
			"code_hash": mcp_oauth.hash_token(code),
			"code_challenge": mcp_oauth.pkce_s256("c" * 43),
			"code_expires": frappe.utils.add_to_date(frappe.utils.now_datetime(), minutes=5),
			"revoked": 0,
		}).insert(ignore_permissions=True)
		status, body = mcp_oauth.handle_token({
			"grant_type": "authorization_code",
			"code": code,
			"redirect_uri": "https://claude.ai/api/mcp/auth_callback",
			"client_id": client_id,
			"code_verifier": "d" * 43,
		})
		self.assertEqual(status, 400)
		self.assertEqual(body["error"], "invalid_grant")

	def test_refresh_rotates(self):
		tokens = self._grant_tokens("Administrator")
		status, again = mcp_oauth.handle_token({
			"grant_type": "refresh_token",
			"refresh_token": tokens["refresh_token"],
		})
		self.assertEqual(status, 200)
		self.assertNotEqual(again["refresh_token"], tokens["refresh_token"])
		status, reused = mcp_oauth.handle_token({
			"grant_type": "refresh_token",
			"refresh_token": tokens["refresh_token"],
		})
		self.assertEqual(status, 400)
		self.assertEqual(reused["error"], "invalid_grant")

	def test_front_desk_does_not_see_set_room_rate(self):
		from kamra.mcp_tools import allowed_tools, tool_allowed

		frappe.set_user("banquet.sales@test.local")  # nosemgrep: frappe-setuser -- assert role-filtered MCP tool list for non-admin user
		self.assertFalse(tool_allowed(BY_NAME["set_room_rate"]))
		names = {t.name for t in allowed_tools()}
		self.assertNotIn("set_room_rate", names)
		self.assertIn("create_booking", names)
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- restore admin after role-filter test

	def test_housekeeping_does_not_see_city_ledger_aging(self):
		from kamra.mcp_tools import BY_NAME, allowed_tools, tool_allowed
		from kamra.tests.audit_fixtures import ensure_user

		email = "ut.mcp.hk.aging@test.local"
		ensure_user(email, ["Housekeeping"])
		frappe.set_user(email)  # nosemgrep: frappe-setuser -- Housekeeping must not see AR aging
		try:
			self.assertFalse(tool_allowed(BY_NAME["city_ledger_aging"]))
			self.assertNotIn("city_ledger_aging",
			                 {t.name for t in allowed_tools()})
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- restore

	def test_tools_call_logs_mcp_channel(self):
		tokens = self._grant_tokens("Administrator")
		req = FakeRequest(
			"POST",
			data=json.dumps({
				"jsonrpc": "2.0",
				"id": 1,
				"method": "tools/list",
			}),
			headers={"Authorization": f"Bearer {tokens['access_token']}"},
		)
		resp = mcp_http.dispatch("mcp", req)
		self.assertEqual(resp.status_code, 200)
		payload = json.loads(resp.get_data(as_text=True))
		names = {t["name"] for t in payload["result"]["tools"]}
		self.assertIn("quote", names)
		self.assertEqual(len(names), len(set(names)))

	def test_tools_call_structured_content_is_object(self):
		from types import SimpleNamespace
		from unittest.mock import patch

		grant = SimpleNamespace(user="Administrator", property=None)
		for result, has_structured in (([{"name": "R1"}], False), (None, False), ({"a": 1}, True)):
			with patch.object(mcp_http, "call_tool", return_value=result):
				out = mcp_http._tools_call({"name": "quote", "arguments": {}}, grant)
			self.assertFalse(out["isError"])
			self.assertEqual("structuredContent" in out, has_structured)
			if has_structured:
				self.assertIsInstance(out["structuredContent"], dict)

	def _key_user(self, email, *, restrict=True, enabled=1, mcp="MCP Manage"):
		"""A Front Desk user with an API key, limited to the test property,
		holding the given MCP role (None for no MCP access)."""
		mcp_access.ensure_roles()
		if not frappe.db.exists("User", email):
			frappe.get_doc({
				"doctype": "User", "email": email, "first_name": "MCP Agent",
				"send_welcome_email": 0, "roles": [{"role": "Front Desk"}],
			}).insert(ignore_permissions=True)
		user = frappe.get_doc("User", email)
		keep = [r.role for r in user.roles if r.role not in mcp_access.MCP_ROLES]
		user.set("roles", [{"role": r} for r in keep + ([mcp] if mcp else [])])
		user.enabled = enabled
		user.api_key = frappe.generate_hash(length=15)
		secret = frappe.generate_hash(length=15)
		user.api_secret = secret
		user.save(ignore_permissions=True)
		if restrict and not frappe.db.exists(
				"User Permission", {"user": email, "allow": "Property"}):
			frappe.get_doc({
				"doctype": "User Permission", "user": email, "allow": "Property",
				"for_value": self.property, "apply_to_all_doctypes": 1,
			}).insert(ignore_permissions=True)
		return f"token {user.api_key}:{secret}"

	def _call(self, auth, method="tools/list", params=None, **headers):
		return mcp_http.dispatch("mcp", FakeRequest(
			"POST",
			data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
			                 "params": params or {}}),
			headers={"Authorization": auth, **headers},
		))

	def _tools(self, auth):
		resp = self._call(auth)
		self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
		return {t["name"]: t for t in json.loads(resp.get_data(as_text=True))["result"]["tools"]}

	def test_no_mcp_role_is_403_with_a_clear_message(self):
		auth = self._key_user("mcp.none@test.local", mcp=None)
		resp = self._call(auth)
		self.assertEqual(resp.status_code, 403)
		self.assertIn("MCP Read or MCP Manage", resp.get_data(as_text=True))

	def test_mcp_read_lists_and_runs_only_reads(self):
		auth = self._key_user("mcp.read@test.local", mcp="MCP Read")
		tools = self._tools(auth)
		self.assertIn("quote", tools)
		self.assertNotIn("create_booking", tools)
		self.assertTrue(all(t["annotations"]["readOnlyHint"] for t in tools.values()))
		resp = self._call(auth, "tools/call", {"name": "create_booking", "arguments": {}})
		result = json.loads(resp.get_data(as_text=True))["result"]
		self.assertTrue(result["isError"])
		self.assertIn("read-only", result["content"][0]["text"])

	def test_role_change_applies_on_the_next_call(self):
		auth = self._key_user("mcp.promote@test.local", mcp="MCP Read")
		self.assertNotIn("create_booking", self._tools(auth))
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- the admin changes the role
		user = frappe.get_doc("User", "mcp.promote@test.local")
		user.append("roles", {"role": "MCP Manage"})
		user.save(ignore_permissions=True)
		self.assertIn("create_booking", self._tools(auth))

	def test_property_switches(self):
		auth = self._key_user("mcp.switch@test.local")
		# a call runs as the key's user, so switch back before each admin change
		mcp_access.set_mcp_policy(self.property, read_only=1, blocked_tools=["quote"])
		tools = self._tools(auth)
		self.assertNotIn("create_booking", tools)
		self.assertNotIn("quote", tools)
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- the admin changes the switch
		mcp_access.set_mcp_policy(self.property, enabled=0)
		self.assertEqual(self._call(auth).status_code, 403)

	def test_annotations(self):
		tools = self._tools(self._key_user("mcp.ann@test.local"))
		self.assertEqual(tools["quote"]["annotations"]["readOnlyHint"], True)
		cancel = tools["cancel_booking"]["annotations"]
		self.assertFalse(cancel["readOnlyHint"])
		self.assertTrue(cancel["destructiveHint"])
		self.assertTrue(tools["create_booking"]["annotations"]["idempotentHint"])
		self.assertEqual(tools["create_booking"]["title"], "Create booking")

	def test_consent_page_refuses_a_user_without_mcp_access(self):
		self._key_user("mcp.consent@test.local", mcp=None)
		client_id = self._register()
		frappe.set_user("mcp.consent@test.local")  # nosemgrep: frappe-setuser -- the consent page is rendered for the signed-in user
		try:
			status, _ctype, body = mcp_oauth.handle_authorize_get({
				"response_type": "code", "client_id": client_id,
				"redirect_uri": "https://claude.ai/api/mcp/auth_callback",
				"code_challenge": mcp_oauth.pkce_s256("e" * 43),
				"code_challenge_method": "S256", "state": "s",
			})
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- restore admin
		self.assertEqual(status, 403)
		self.assertIn("MCP Read or MCP Manage", body)

	def test_api_key_acts_as_its_user_for_its_one_property(self):
		auth = self._key_user("mcp.agent@test.local")
		resp = self._call(auth)
		self.assertEqual(resp.status_code, 200)
		names = {t["name"] for t in json.loads(resp.get_data(as_text=True))["result"]["tools"]}
		# the key carries the user's role, nothing more
		self.assertIn("create_booking", names)
		self.assertNotIn("set_room_rate", names)
		grant, refused = mcp_http._identity(FakeRequest(headers={"Authorization": auth}))
		self.assertIsNone(refused)
		self.assertEqual((grant.user, grant.property), ("mcp.agent@test.local", self.property))

	def test_api_key_wrong_secret_or_disabled_user_is_401(self):
		auth = self._key_user("mcp.agent2@test.local")
		self.assertEqual(self._call(auth[:-1] + "x").status_code, 401)
		auth = self._key_user("mcp.agent2@test.local", enabled=0)
		self.assertEqual(self._call(auth).status_code, 401)

	def test_api_key_cannot_reach_another_property(self):
		auth = self._key_user("mcp.agent3@test.local")
		resp = self._call(auth, **{"X-Kamra-Property": "Some Other Hotel"})
		self.assertEqual(resp.status_code, 403)

	def test_unrestricted_api_key_must_name_its_property(self):
		auth = self._key_user("mcp.agent4@test.local", restrict=False)
		self.assertEqual(self._call(auth).status_code, 403)
		resp = self._call(auth, **{"X-Kamra-Property": self.property})
		self.assertEqual(resp.status_code, 200)

	def test_revoke_kills_access(self):
		tokens = self._grant_tokens("Administrator")
		n = mcp_oauth.revoke_grants("Administrator", self.property)
		self.assertGreaterEqual(n, 1)
		req = FakeRequest(
			"POST",
			data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}),
			headers={"Authorization": f"Bearer {tokens['access_token']}"},
		)
		resp = mcp_http.dispatch("mcp", req)
		self.assertEqual(resp.status_code, 401)
