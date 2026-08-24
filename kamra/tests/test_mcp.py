"""Remote MCP OAuth + HTTP — needs a Frappe site (IntegrationTestCase)."""

from __future__ import annotations

import json

import frappe
from frappe.tests import IntegrationTestCase

from kamra import mcp_http, mcp_oauth
from kamra.mcp_tools import BY_NAME
from kamra.tests.fixtures import PROPERTY, build, ensure_roles_and_users


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
		self.assertFalse(mcp_oauth.is_public_https("http://hotel.example"))
		self.assertFalse(mcp_oauth.is_public_https("https://localhost"))
		self.assertTrue(mcp_oauth.is_public_https("https://pms.example.com"))


class TestRemoteMCP(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture sets admin before seeding MCP OAuth data
		ensure_roles_and_users()
		build()
		self.property = PROPERTY

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
