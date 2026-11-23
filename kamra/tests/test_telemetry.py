"""Install heartbeat and opt-in registration (kamra.telemetry, #657).

kamrapms.com is never contacted: requests is patched."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import frappe

from kamra import telemetry as tm
from kamra.tests.audit_fixtures import AuditTestCase, ensure_user

ALLOWED = {"install_id", "kamra_version", "frappe_version", "rooms", "country",
           "deployment", "checkins_last_7_days"}


def ok(status=200):
	return MagicMock(status_code=status)


class TestTelemetry(AuditTestCase):
	def setUp(self):
		super().setUp()
		frappe.db.set_default(tm.OFF_KEY, "0")
		frappe.db.set_default(tm.REG_KEY, "")
		self._conf = frappe.conf.pop("kamra_telemetry", None)
		self._env = patch.dict(os.environ, {"KAMRA_TELEMETRY": "", "DO_NOT_TRACK": ""})
		self._env.start()

	def tearDown(self):
		self._env.stop()
		if self._conf is not None:
			frappe.conf["kamra_telemetry"] = self._conf
		super().tearDown()

	# heartbeat --------------------------------------------------------------

	def test_payload_is_exactly_the_documented_fields(self):
		p = tm.payload()
		self.assertEqual(set(p), ALLOWED)
		self.assertIn(p["deployment"], ("docker", "bench"))
		self.assertIn(p["rooms"], ("0", "1-10", "11-50", "51-200", "200+"))
		self.assertIsInstance(p["checkins_last_7_days"], bool)
		# nothing that names the hotel, the site or a person
		text = frappe.as_json(p).lower()
		self.assertNotIn(frappe.local.site.lower(), text)
		self.assertNotIn("@", text)

	def test_install_id_is_random_and_stable(self):
		first = tm.install_id()
		self.assertEqual(len(first), 36)
		self.assertNotIn(frappe.local.site, first)
		self.assertEqual(tm.install_id(), first)

	def test_room_buckets(self):
		self.assertEqual([tm._rooms_bucket(n) for n in (0, 1, 10, 11, 50, 51, 200, 201)],
		                 ["0", "1-10", "1-10", "11-50", "11-50", "51-200", "51-200", "200+"])

	def test_heartbeat_sends_the_payload(self):
		with patch("requests.post", return_value=ok()) as post:
			self.assertTrue(tm.send_heartbeat())
		self.assertEqual(set(post.call_args.kwargs["json"]), ALLOWED)
		self.assertEqual(post.call_args.kwargs["timeout"], tm.TIMEOUT)

	def test_heartbeat_fails_silently(self):
		with patch("requests.post", side_effect=OSError("offline")):
			self.assertFalse(tm.send_heartbeat())

	def test_settings_switch_turns_it_off(self):
		tm.set_telemetry(0)
		with patch("requests.post") as post:
			self.assertFalse(tm.send_heartbeat())
		post.assert_not_called()
		tm.set_telemetry(1)
		self.assertTrue(tm.enabled())

	def test_env_and_site_config_turn_it_off(self):
		for env in ({"KAMRA_TELEMETRY": "0"}, {"DO_NOT_TRACK": "1"}):
			with patch.dict(os.environ, env), patch("requests.post") as post:
				self.assertTrue(tm.disabled_by_config())
				self.assertFalse(tm.send_heartbeat())
				post.assert_not_called()
		frappe.conf["kamra_telemetry"] = 0
		try:
			self.assertFalse(tm.enabled())
			self.assertTrue(tm.telemetry_status()["disabled_by_config"])
		finally:
			frappe.conf.pop("kamra_telemetry", None)
		self.assertTrue(tm.enabled())

	# registration -----------------------------------------------------------

	def test_register_edit_remove(self):
		with patch("requests.request", return_value=ok()) as req:
			out = tm.save_registration("Sea View", "gm@seaview.test", city="Goa",
			                           country="India", room_count=24, list_publicly=1)
			self.assertTrue(out["sent"])
			method, url = req.call_args.args
			self.assertEqual((method, url.rsplit("/", 1)[1]), ("POST", "register"))
			self.assertEqual(req.call_args.kwargs["json"]["install_id"], tm.install_id())
			self.assertTrue(tm.telemetry_status()["registration"]["list_publicly"])

			tm.save_registration("Sea View", "gm@seaview.test", list_publicly=0)
			self.assertFalse(tm.telemetry_status()["registration"]["list_publicly"])

			self.assertIsNone(tm.remove_registration()["registration"])
			self.assertEqual(req.call_args.args[0], "DELETE")
		self.assertIsNone(tm.telemetry_status()["registration"])

	def test_failed_removal_keeps_the_registration(self):
		with patch("requests.request", return_value=ok()):
			tm.save_registration("Sea View", "gm@seaview.test")
		with patch("requests.request", side_effect=OSError("offline")):
			out = tm.remove_registration()
		self.assertFalse(out["sent"])
		self.assertEqual(out["registration"]["property_name"], "Sea View")

	def test_registration_needs_name_and_email(self):
		with patch("requests.request") as req:
			with self.assertRaises(frappe.ValidationError):
				tm.save_registration("", "gm@seaview.test")
			with self.assertRaises(frappe.ValidationError):
				tm.save_registration("Sea View", "not-an-email")
		req.assert_not_called()

	def test_only_admins(self):
		ensure_user("ut.tm.desk@test.local", ["Front Desk"])
		frappe.set_user("ut.tm.desk@test.local")  # nosemgrep: frappe-setuser -- persona
		try:
			for fn in (tm.telemetry_status, lambda: tm.set_telemetry(0),
			           tm.remove_registration):
				with self.assertRaises(frappe.PermissionError):
					fn()
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- restore
