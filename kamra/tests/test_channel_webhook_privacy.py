"""#566: channel webhooks keep a summary + conversation ref, not raw guest text."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe
from frappe.utils import add_to_date, get_datetime

from kamra import agents_channels, privacy
from kamra.tests.audit_fixtures import PROP_A, TODAY, AuditTestCase, make_property


class ChannelWebhookRationaleTest(unittest.TestCase):
	def test_messaging_never_keeps_guest_words(self):
		secret = "Can I check in at 11am with passport X123?"
		out = agents_channels.messaging_log_rationale({
			"text": secret,
			"message_id": "prov-xyz789",
			"media_urls": ["https://example/a.jpg"],
		})
		self.assertNotIn(secret, out)
		self.assertNotIn("passport", out)
		self.assertIn("message_id=prov-xyz789", out)
		self.assertIn("text", out)
		self.assertIn("1 media", out)
		self.assertTrue(out.startswith("WhatsApp inbound"))

	def test_voice_never_keeps_transcript(self):
		transcript = "Guest said: room smells of smoke, please move us."
		out = agents_channels.voice_log_rationale({
			"summary": "Late checkout request",
			"call_id": "prov-abc123",
			"transcript": transcript,
		}, "call_ended")
		self.assertNotIn(transcript, out)
		self.assertNotIn("smells of smoke", out)
		self.assertIn("Late checkout request", out)
		self.assertIn("call_id=prov-abc123", out)
		self.assertIn("transcript held by provider", out)


class ChannelWebhookRetentionTest(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		make_property(PROP_A, message_retention_days=30)
		self._stack.enter_context(patch(
			"kamra.privacy.now_datetime",
			return_value=get_datetime(f"{TODAY} 03:40:00")))

	def _log(self, action_type, rationale, age_days):
		doc = frappe.get_doc({
			"doctype": "Agent Action Log",
			"property": PROP_A,
			"action_type": action_type,
			"rationale": rationale,
			"autonomy": "Full",
			"approval_status": "Executed",
			"action_channel": "WhatsApp" if action_type.startswith("whatsapp") else "Voice",
			"agent_name": "UT Concierge",
		}).insert(ignore_permissions=True)
		when = str(add_to_date(get_datetime(f"{TODAY} 03:40:00"), days=-age_days))
		frappe.db.sql(
			"UPDATE `tabAgent Action Log` SET creation = %s, modified = %s WHERE name = %s",
			(when, when, doc.name))
		return doc.name

	def test_retention_clears_old_channel_logs_only(self):
		old_wa = self._log("whatsapp.inbound",
		                   "WhatsApp inbound: please send the bill to my work email", 45)
		fresh_wa = self._log("whatsapp.inbound",
		                     "WhatsApp inbound · text · message_id=fresh", 5)
		old_voice = self._log("voice.call_ended",
		                      "Late checkout\n\nGuest asked to stay until 4pm", 45)
		other = self._log("folio_payment", "Payment ₹500 by Cash", 45)
		out = privacy.apply_message_retention()
		self.assertGreaterEqual(out["channel_logs"], 2)
		self.assertEqual(
			frappe.db.get_value("Agent Action Log", old_wa, "rationale"),
			privacy.CLEARED_CHANNEL_RATIONALE)
		self.assertEqual(
			frappe.db.get_value("Agent Action Log", old_voice, "rationale"),
			privacy.CLEARED_CHANNEL_RATIONALE)
		self.assertEqual(
			frappe.db.get_value("Agent Action Log", fresh_wa, "rationale"),
			"WhatsApp inbound · text · message_id=fresh")
		self.assertEqual(
			frappe.db.get_value("Agent Action Log", other, "rationale"),
			"Payment ₹500 by Cash")

	def test_trim_patch_rewrites_raw_rows(self):
		raw = self._log("whatsapp.inbound",
		                "WhatsApp inbound: Can I bring my dog?", 10)
		voice = self._log("voice.call_ended",
		                  "Room change\n\nPlease move us to a quiet floor", 10)
		already = self._log("whatsapp.inbound",
		                    "WhatsApp inbound · text · message_id=keep", 10)
		n = privacy.trim_channel_webhook_logs()
		self.assertGreaterEqual(n, 2)
		wa = frappe.db.get_value("Agent Action Log", raw, "rationale")
		self.assertNotIn("dog", wa)
		self.assertTrue(wa.startswith("WhatsApp inbound"))
		vo = frappe.db.get_value("Agent Action Log", voice, "rationale")
		self.assertNotIn("quiet floor", vo)
		self.assertIn("Room change", vo)
		self.assertEqual(
			frappe.db.get_value("Agent Action Log", already, "rationale"),
			"WhatsApp inbound · text · message_id=keep")
