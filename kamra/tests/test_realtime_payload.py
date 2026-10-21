"""The live-update ping says whether a document is new and who changed it
(as a hash), so a screen can alert for a new order and skip its own."""

from __future__ import annotations

from unittest.mock import patch

import frappe

from kamra.realtime import notify, who
from kamra.tests.audit_fixtures import AuditTestCase


class _Doc:
	doctype = "Service Ticket"
	name = "TKT-1"

	def get(self, key):
		return {"property": "P", "outlet": None}.get(key)


class RealtimePayloadTestCase(AuditTestCase):
	def sent(self, method):
		with patch.object(frappe, "publish_realtime") as pub:
			notify(_Doc(), method)
		self.assertTrue(pub.called)
		return pub.call_args.args[1]

	def test_a_new_document_is_flagged_new(self):
		self.assertTrue(self.sent("after_insert")["is_new"])

	def test_an_edit_is_not_new(self):
		self.assertFalse(self.sent("on_update")["is_new"])

	def test_who_changed_it_is_a_hash_never_the_user_name(self):
		payload = self.sent("after_insert")
		self.assertEqual(payload["by"], who(frappe.session.user))
		self.assertNotIn(frappe.session.user, str(payload))

	def test_who_matches_the_browser_hash(self):
		# the same value frontend/src/lib/notifications.ts computes for "a@b.c"
		self.assertEqual(who("a@b.c"), "a0e7ceb")
		self.assertEqual(who(""), "1505")
