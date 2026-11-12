"""Housekeeping WhatsApp alerts reach only staff who work at that property."""

from __future__ import annotations

from unittest.mock import patch

import frappe

from kamra.housekeeping import _notify_role
from kamra.tests.audit_fixtures import PROP_A, PROP_B, AuditTestCase, ensure_user, make_property

AT_A = ("ut-hk-at-a@example.com", "+919800000011")
AT_B = ("ut-hk-at-b@example.com", "+919800000012")
ANYWHERE = ("ut-hk-anywhere@example.com", "+919800000013")


class TestHousekeepingAlertRecipients(AuditTestCase):
	def setUp(self):
		super().setUp()
		make_property(PROP_A)
		make_property(PROP_B)
		for (user, mobile), props in ((AT_A, [PROP_A]), (AT_B, [PROP_B]), (ANYWHERE, [])):
			ensure_user(user, ["Front Desk"])
			frappe.db.set_value("User", user, "mobile_no", mobile)
			frappe.db.delete("User Permission", {"user": user, "allow": "Property"})
			for p in props:
				frappe.get_doc({"doctype": "User Permission", "user": user,
				                "allow": "Property", "for_value": p}).insert(ignore_permissions=True)
		frappe.clear_cache()

	def _sent_to(self, property):
		with patch("kamra.agents_channels.send_outbound") as send:
			_notify_role(property, "Front Desk", "Room 101 is ready for today's arrival.")
		return {c.args[2] for c in send.call_args_list}

	def test_staff_of_another_property_are_left_out(self):
		sent = self._sent_to(PROP_A)
		self.assertIn(AT_A[1], sent)
		self.assertNotIn(AT_B[1], sent)

	def test_staff_not_limited_to_a_property_still_hear(self):
		self.assertIn(ANYWHERE[1], self._sent_to(PROP_A))
		self.assertIn(ANYWHERE[1], self._sent_to(PROP_B))

	def test_the_other_property_gets_its_own_staff(self):
		sent = self._sent_to(PROP_B)
		self.assertIn(AT_B[1], sent)
		self.assertNotIn(AT_A[1], sent)
