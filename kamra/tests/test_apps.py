"""Connected apps: signed manifest, one-time pairing code, scope limits,
disconnect and property_profile."""

import base64
import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime

from kamra import apps
from kamra import service_accounts as sa
from kamra.mcp_access import extra_redirect_uris

HOME = "TEST APP Home"
OTHER = "TEST APP Other"
URL = "https://reports.example.test"
REDIRECT = URL + "/oauth/callback"


def _property(name: str) -> str:
	if not frappe.db.exists("Property", name):
		frappe.get_doc({"doctype": "Property", "property_name": name}).insert(
			ignore_permissions=True)
	return name


def _manifest(**over) -> dict:
	m = {"id": "test-reports", "name": "Test Reports", "url": URL,
	     "icon": URL + "/icon.png", "redirect_uri": REDIRECT,
	     "scopes": ["reports.read", "finance.read"], "roles": ["Finance"]}
	m.update(over)
	return m


class AppPairingTestCase(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture setup
		_property(HOME)
		_property(OTHER)
		self.defaults = {k: frappe.db.get_default(k)
		                 for k in (apps.KEYS_KEY, apps.UNSIGNED_KEY)}
		frappe.db.set_default(apps.UNSIGNED_KEY, "1")
		self.manifest = _manifest()

	def tearDown(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture teardown
		frappe.local.cache.pop("kamra_service_accounts", None)
		frappe.db.rollback()
		for key, value in self.defaults.items():
			frappe.db.set_default(key, value or "")
		frappe.db.commit()  # nosemgrep: frappe-manual-commit -- restore the site-wide trust defaults

	def _download(self, url):
		self.assertEqual(url, URL + "/kamra-app.json")
		return json.dumps(self.manifest).encode()

	def _connect(self, scopes=("reports.read",), properties=(HOME,)):
		with patch.object(apps, "_download", self._download):
			return apps.connect(URL, list(scopes), list(properties))

	def _pair(self, code, app_id="test-reports"):
		frappe.set_user("Guest")  # nosemgrep: frappe-setuser -- pair is the unauthenticated endpoint
		try:
			return apps.pair(code, app_id)
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- back to the test user

	def _as(self, user):
		frappe.local.cache.pop("kamra_service_accounts", None)
		frappe.set_user(user)  # nosemgrep: frappe-setuser -- acting as the paired app
		return sa.account_for()

	def test_signature(self):
		from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
		from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

		key = Ed25519PrivateKey.generate()
		pub = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
		apps.set_trust(unsigned=0, keys=[base64.b64encode(pub).decode()])
		m = _manifest()
		m["signature"] = base64.b64encode(key.sign(apps.canonical(m))).decode()
		self.assertTrue(apps.signed_by_trusted_key(m))
		self.manifest = m
		with patch.object(apps, "_download", self._download):
			self.assertTrue(apps.preview(URL)["signed"])
			# a changed scope list breaks the signature
			self.manifest = {**m, "scopes": ["approvals.write"]}
			self.assertRaises(frappe.ValidationError, apps.preview, URL)
			# unsigned is refused unless IT allows it
			self.manifest = _manifest()
			self.assertRaises(frappe.ValidationError, apps.preview, URL)
			apps.set_trust(unsigned=1)
			self.assertFalse(apps.preview(URL)["signed"])

	def test_manifest_must_stay_on_its_host(self):
		self.manifest = _manifest(redirect_uri="https://elsewhere.test/cb")
		with patch.object(apps, "_download", self._download):
			self.assertRaises(frappe.ValidationError, apps.preview, URL)
		self.assertRaises(frappe.ValidationError, apps.manifest_url, "http://reports.example.test")

	def test_code_works_once(self):
		reply = self._connect()
		self.assertIn(REDIRECT, extra_redirect_uris())
		got = self._pair(reply["code"].lower().replace("-", " "))
		self.assertEqual(got["scopes"], ["reports.read"])
		self.assertEqual([p["property"] for p in got["properties"]], [HOME])
		self.assertTrue(got["api_key"] and got["api_secret"])
		self.assertEqual(frappe.db.get_value("Kamra App", "test-reports", "status"), "Paired")
		self.assertEqual(self._pair(reply["code"])["error"], "invalid_code")
		logged = frappe.get_all("Agent Action Log", filters={
			"action_type": "app.pair_attempt", "rationale": ["like", "test-reports from%"],
			"creation": [">=", add_to_date(now_datetime(), minutes=-1)]},
			fields=["approval_status"])
		self.assertEqual(sorted(r.approval_status for r in logged), ["Executed", "Rejected"])

	def test_code_expires_and_names_its_app(self):
		reply = self._connect()
		self.assertEqual(self._pair(reply["code"], "another-app")["error"], "invalid_code")
		frappe.db.set_value("Kamra App", "test-reports", "code_expires",
		                    add_to_date(now_datetime(), minutes=-1))
		self.assertEqual(self._pair(reply["code"])["error"], "invalid_code")
		fresh = apps.new_pairing_code("test-reports")
		self.assertIn("api_secret", self._pair(fresh["code"]))

	def test_scope_limits(self):
		with patch.object(apps, "_download", self._download):
			# only what the app asked for
			self.assertRaises(frappe.ValidationError, apps.connect, URL,
			                  ["approvals.write"], [HOME])
		reply = self._connect(scopes=("finance.read",))
		self._pair(reply["code"])
		user = frappe.db.get_value("Kamra Service Account", frappe.db.get_value(
			"Kamra App", "test-reports", "service_account"), "user")
		me = self._as(user)
		for ok in ("kamra.api.folio_invoice", "kamra.cashier.session_report",
		           "kamra.apps.property_profile", "kamra.receivables.ar_invoice"):
			self.assertIsNone(sa.refusal(me, f"/api/method/{ok}"), ok)
		for no in ("kamra.reports.manager_flash", "kamra.api.add_folio_payment",
		           "kamra.apps.my_apps", "kamra.apps.disconnect"):
			self.assertTrue(sa.refusal(me, f"/api/method/{no}"), no)
		self.assertEqual(apps.property_profile(HOME)["name"], HOME)
		self.assertRaises(frappe.PermissionError, apps.property_profile, OTHER)

	def test_disconnect_stops_access(self):
		reply = self._connect()
		self._pair(reply["code"])
		self.assertIn("test-reports", [a["app_id"] for a in apps.my_apps()])
		account = frappe.db.get_value("Kamra App", "test-reports", "service_account")
		user = frappe.db.get_value("Kamra Service Account", account, "user")
		apps.disconnect("test-reports")
		self.assertNotIn(REDIRECT, extra_redirect_uris())
		self.assertNotIn("test-reports", [a["app_id"] for a in apps.my_apps()])
		frappe.local.cache.pop("kamra_service_accounts", None)
		self.assertTrue(sa.refusal(sa.account_for(user),
		                           "/api/method/kamra.reports.manager_flash"))
		# reconnecting makes a new account
		again = self._connect()
		self.assertNotEqual(frappe.db.get_value("Kamra App", "test-reports",
		                                        "service_account"), account)
		self.assertTrue(again["code"])

	def test_tile_follows_roles(self):
		self._pair(self._connect()["code"])
		user = "test-app-hk@example.test"
		if not frappe.db.exists("User", user):
			frappe.get_doc({"doctype": "User", "email": user, "first_name": "HK",
			                "send_welcome_email": 0,
			                "roles": [{"role": "Housekeeping"}]}).insert(ignore_permissions=True)
		frappe.set_user(user)  # nosemgrep: frappe-setuser -- a staff member without the app's role
		self.assertNotIn("test-reports", [a["app_id"] for a in apps.my_apps()])

	def test_manifest_can_stay_out_of_the_switcher(self):
		self.manifest = _manifest(switcher=False)
		self._pair(self._connect()["code"])
		self.assertEqual(frappe.db.get_value("Kamra App", "test-reports", "show_in_switcher"), 0)
		# not even admins get a tile; the app is still paired and reachable from Marketplace
		self.assertNotIn("test-reports", [a["app_id"] for a in apps.my_apps()])
		self.assertEqual(frappe.db.get_value("Kamra App", "test-reports", "status"), "Paired")

	def test_property_profile(self):
		frappe.db.set_value("Property", HOME, {"gstin": "TAX-123", "logo_url": "/files/logo.png",
		                                       "timezone": "Asia/Dubai"})
		frappe.clear_document_cache("Property", HOME)
		p = apps.property_profile(HOME)
		self.assertEqual(p["tax_id"], "TAX-123")
		self.assertTrue(p["logo_url"].endswith("/files/logo.png"))
		self.assertEqual(p["timezone"], "Asia/Dubai")
		for key in ("currency", "language", "checkin_time", "checkout_time", "address"):
			self.assertIn(key, p)
