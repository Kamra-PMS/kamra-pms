"""The self check-in link is only marked sent when a message really went out."""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.utils import add_days, nowdate

from kamra.api import send_precheckin_link
from kamra.prearrival import run_prearrival_outreach
from kamra.tests.audit_fixtures import (PROP_A, AuditTestCase, make_guest,
                                        make_property, make_reservation, make_room_type)


class TestPrecheckinLink(AuditTestCase):
	def setUp(self):
		super().setUp()
		make_property(PROP_A, auto_send_checkin_links=1)
		frappe.db.delete("Channel Provider Connection", {"property": PROP_A})
		rt = make_room_type(PROP_A)
		# arriving tomorrow: the daily run looks ahead from today
		tomorrow = add_days(nowdate(), 1)
		self.res = make_reservation(PROP_A, rt, tomorrow, add_days(tomorrow, 1),
		                            guest=make_guest(phone="+919800000001")).name

	def _marked(self):
		return frappe.db.get_value("Reservation", self.res, "precheckin_link_sent")

	def test_no_channel_gives_the_link_but_does_not_mark_it_sent(self):
		out = send_precheckin_link(self.res)
		self.assertFalse(out["sent"])
		self.assertIsNone(out["channel"])
		self.assertIn("/kamra/checkin/", out["link"])
		self.assertIsNone(self._marked())

	def test_a_dropped_message_is_not_marked_sent(self):
		with patch("kamra.agents_channels.send_outbound",
		           return_value={"sent": False, "reason": "provider_error"}):
			self.assertFalse(send_precheckin_link(self.res)["sent"])
		self.assertIsNone(self._marked())

	def test_a_delivered_message_is_marked_sent(self):
		with patch("kamra.agents_channels.send_outbound",
		           return_value={"sent": True, "provider": "Meta Business"}):
			out = send_precheckin_link(self.res)
		self.assertTrue(out["sent"])
		self.assertEqual(out["channel"], "WhatsApp")
		self.assertIsNotNone(self._marked())

	def test_the_daily_run_skips_a_hotel_with_no_whatsapp_line(self):
		with patch("kamra.api.send_precheckin_link") as send:
			run_prearrival_outreach(horizon_days=2)
		self.assertNotIn(self.res, [c.args[0] for c in send.call_args_list])

	def test_the_daily_run_sends_and_marks_once_a_line_is_connected(self):
		frappe.get_doc({"doctype": "Channel Provider Connection", "property": PROP_A,
		                "channel": "WhatsApp", "provider": "Custom",
		                "active": 1}).insert(ignore_permissions=True)
		with patch("kamra.agents_channels.send_outbound",
		           return_value={"sent": True, "provider": "Custom"}):
			run_prearrival_outreach(horizon_days=2)
		self.assertIsNotNone(self._marked())
