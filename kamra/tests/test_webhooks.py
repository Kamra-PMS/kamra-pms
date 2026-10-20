# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Outbound webhooks: signature, SSRF guard, retries and the delivery log,
property scope, and the events the booking lifecycle fires."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import socket
from types import SimpleNamespace
from unittest.mock import patch

import frappe
import requests
from frappe.utils import add_to_date, now_datetime

from kamra import webhooks as wh
from kamra.tests.audit_fixtures import (
	PROP_A,
	PROP_B,
	TODAY,
	AuditTestCase,
	d,
	ensure_user,
	make_property,
	make_reservation,
	make_room,
	make_room_type,
)

PUBLIC_IP = "93.184.216.34"
URL = "https://hooks.example.com/kamra"


def _resolve_to(*ips):
	def fake(host, port, *a, **kw):
		try:  # an IP literal resolves to itself, as the real resolver does
			ipaddress.ip_address(host)
			found = (host,)
		except ValueError:
			found = ips
		return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in found]
	return patch("kamra.webhooks.socket.getaddrinfo", side_effect=fake)


def _resp(code: int, text: str = ""):
	return SimpleNamespace(status_code=code, text=text)


class SignatureTestCase(AuditTestCase):
	properties = ()

	def test_signature_is_hmac_sha256_over_timestamp_dot_body(self):
		body = b'{"id":"evt_1","event":"ping"}'
		expected = hmac.new(b"whsec_x", b"1700000000." + body, hashlib.sha256).hexdigest()
		self.assertEqual(wh.sign("whsec_x", 1700000000, body), "sha256=" + expected)
		self.assertEqual(wh.sign("whsec_x", "1700000000", body.decode()),
		                 "sha256=" + expected)

	def test_verify_accepts_only_fresh_untampered_bodies(self):
		body = b'{"a":1}'
		sig = wh.sign("s3cret", 1000, body)
		self.assertTrue(wh.verify("s3cret", 1000, body, sig, now=1100))
		self.assertFalse(wh.verify("s3cret", 1000, b'{"a":2}', sig, now=1100))
		self.assertFalse(wh.verify("other", 1000, body, sig, now=1100))
		self.assertFalse(wh.verify("s3cret", 1000, body, sig, now=1000 + 301))
		self.assertFalse(wh.verify("s3cret", "nope", body, sig, now=1100))


class SSRFTestCase(AuditTestCase):
	properties = ()

	def setUp(self):
		super().setUp()
		self._stack.enter_context(patch.dict(frappe.conf, {
			"developer_mode": 0, "kamra_webhooks_allow_http": 0,
			"kamra_webhooks_allow_private": 0}))

	def refused(self, url, msg):
		with self.assertRaisesRegex(frappe.ValidationError, msg):
			wh.validate_target_url(url)

	def test_https_only_and_no_credentials(self):
		self.refused("http://hooks.example.com/x", "https")
		self.refused("ftp://hooks.example.com/x", "https")
		self.refused("https://user:pw@hooks.example.com/x", "credentials")
		self.refused("", "Enter the endpoint")

	def test_internal_addresses_refused(self):
		for url in ("https://127.0.0.1/x", "https://10.0.0.5/x",
		            "https://192.168.1.10/x", "https://172.16.0.1/x",
		            "https://169.254.169.254/latest/meta-data",
		            "https://100.64.0.1/x", "https://[::1]/x",
		            "https://[::ffff:127.0.0.1]/x", "https://0.0.0.0/x",
		            "https://224.0.0.1/x"):
			self.refused(url, "private, loopback or internal")
		self.refused("https://localhost/x", "internal hosts")
		self.refused("https://redis-queue.internal/x", "internal hosts")

	def test_hostname_resolving_to_private_ip_refused(self):
		with _resolve_to(PUBLIC_IP, "10.1.2.3"):
			self.refused(URL, "private, loopback or internal")

	def test_public_https_allowed(self):
		with _resolve_to(PUBLIC_IP):
			self.assertEqual(wh.validate_target_url(URL), URL)

	def test_unresolvable_host_refused(self):
		with patch("kamra.webhooks.socket.getaddrinfo",
		           side_effect=socket.gaierror("nope")):
			self.refused(URL, "can't be resolved")


class _WebhookCase(AuditTestCase):
	properties = (PROP_A, PROP_B)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		self._stack.enter_context(patch.dict(frappe.conf, {"developer_mode": 0}))
		self._stack.enter_context(_resolve_to(PUBLIC_IP))
		self.enqueued = []
		self._stack.enter_context(patch("kamra.webhooks._enqueue",
		                                side_effect=self.enqueued.append))
		make_property(PROP_A, business_date=TODAY)
		make_property(PROP_B, business_date=TODAY)

	def subscribe(self, prop=PROP_A, events=tuple(wh.EVENTS)):
		return wh.save_webhook(prop, URL, list(events), label="UT receiver")

	def deliveries(self, prop=PROP_A, event=None):
		f = {"property": prop}
		if event:
			f["event"] = event
		return frappe.get_all(wh.DELIVERY, filters=f, pluck="name",
		                      order_by="creation asc")


class SubscriptionTestCase(_WebhookCase):
	def test_secret_returned_once_and_never_listed(self):
		out = self.subscribe()
		self.assertTrue(out["secret"].startswith("whsec_"))
		listed = wh.list_webhooks(PROP_A)
		self.assertEqual(len(listed), 1)
		self.assertNotIn("secret", listed[0])
		self.assertTrue(listed[0]["has_secret"])
		again = wh.save_webhook(PROP_A, URL, ["folio.posted"],
		                        name=out["name"])
		self.assertIsNone(again["secret"])
		self.assertEqual(again["events"], ["folio.posted"])

	def test_unknown_event_and_private_url_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Unknown event"):
			wh.save_webhook(PROP_A, URL, ["reservation.deleted"])
		with self.assertRaisesRegex(frappe.ValidationError, "private"):
			wh.save_webhook(PROP_A, "https://127.0.0.1/hook", ["folio.posted"])


class DeliveryTestCase(_WebhookCase):
	def test_emit_signs_and_delivers(self):
		sub = self.subscribe(events=("folio.posted",))
		names = wh.emit("folio.posted", PROP_A, {"folio": "F-1", "balance": 10})
		self.assertEqual(len(names), 1)
		self.assertEqual(self.enqueued, names)
		with patch("requests.post", return_value=_resp(200)) as post:
			out = wh.deliver(names[0])
		self.assertEqual(out["status"], "Delivered")
		args, kw = post.call_args
		self.assertEqual(args[0], URL)
		self.assertFalse(kw["allow_redirects"])
		h = kw["headers"]
		body = kw["data"]
		self.assertTrue(wh.verify(sub["secret"], h["X-Kamra-Timestamp"], body,
		                          h["X-Kamra-Signature"]))
		env = json.loads(body)
		self.assertEqual(env["event"], "folio.posted")
		self.assertEqual(env["property"], PROP_A)
		self.assertEqual(h["X-Kamra-Event-Id"], env["id"])
		row = frappe.get_doc(wh.DELIVERY, names[0])
		self.assertEqual((row.status, row.attempts, row.response_code),
		                 ("Delivered", 1, 200))
		# the secret is never written into the log
		self.assertNotIn(sub["secret"], json.dumps(row.as_dict(), default=str))

	def test_failures_retry_with_backoff_then_fail(self):
		self.subscribe(events=("folio.posted",))
		name = wh.emit("folio.posted", PROP_A, {"folio": "F-1"})[0]
		with patch("requests.post", return_value=_resp(500, "boom")):
			out = wh.deliver(name)
		self.assertEqual(out["status"], "Retrying")
		row = frappe.get_doc(wh.DELIVERY, name)
		self.assertEqual(row.attempts, 1)
		self.assertEqual(row.response_code, 500)
		self.assertIn("HTTP 500", row.last_error)
		gap = (row.next_retry_at - row.modified).total_seconds()
		self.assertAlmostEqual(gap, wh.BACKOFF[0], delta=5)
		# a due retry is picked up by the scheduler
		frappe.db.set_value(wh.DELIVERY, name, "next_retry_at",
		                    add_to_date(now_datetime(), minutes=-1))
		with patch("frappe.enqueue") as enq:
			self.assertGreaterEqual(wh.retry_due(), 1)
		self.assertIn(name, [c.kwargs["delivery"] for c in enq.call_args_list])
		with patch("requests.post", side_effect=requests.ConnectionError("down")):
			for _ in range(wh.MAX_ATTEMPTS - 1):
				out = wh.deliver(name)
		self.assertEqual(out["status"], "Failed")
		self.assertEqual(frappe.db.get_value(wh.DELIVERY, name, "attempts"),
		                 wh.MAX_ATTEMPTS)
		hook = frappe.get_all(wh.WEBHOOK, filters={"property": PROP_A},
		                      fields=["consecutive_failures", "last_status"])[0]
		self.assertEqual(hook.consecutive_failures, wh.MAX_ATTEMPTS)

		# manual resend: same event id, delivered this time
		event_id = frappe.db.get_value(wh.DELIVERY, name, "event_id")
		self.assertEqual(wh.resend_delivery(name)["status"], "Pending")
		with patch("requests.post", return_value=_resp(204)) as post:
			self.assertEqual(wh.deliver(name)["status"], "Delivered")
		self.assertEqual(post.call_args.kwargs["headers"]["X-Kamra-Event-Id"], event_id)

	def test_failed_test_ping_is_failed_on_the_hook_too(self):
		sub = self.subscribe(events=("folio.posted",))
		with patch("requests.post", return_value=_resp(405, "nope")):
			out = wh.send_test_event(sub["name"], PROP_A)
		self.assertEqual(out["status"], "Failed")
		self.assertEqual(frappe.db.get_value(wh.DELIVERY, out["delivery"], "status"), "Failed")
		# the endpoint card must not claim a retry is coming
		self.assertEqual(frappe.db.get_value(wh.WEBHOOK, sub["name"], "last_status"),
		                 "Failed (405)")

	def test_dns_rebinding_to_private_ip_fails_without_retry(self):
		self.subscribe(events=("folio.posted",))
		name = wh.emit("folio.posted", PROP_A, {"folio": "F-1"})[0]
		with _resolve_to("127.0.0.1"), patch("requests.post") as post:
			out = wh.deliver(name)
		post.assert_not_called()
		self.assertEqual(out["status"], "Failed")

	def test_redirect_is_not_followed_and_counts_as_failure(self):
		self.subscribe(events=("folio.posted",))
		name = wh.emit("folio.posted", PROP_A, {"folio": "F-1"})[0]
		with patch("requests.post", return_value=_resp(302)):
			self.assertEqual(wh.deliver(name)["status"], "Retrying")

	def test_inactive_webhook_gets_nothing(self):
		sub = self.subscribe(events=("folio.posted",))
		wh.save_webhook(PROP_A, URL, ["folio.posted"], active=0, name=sub["name"])
		self.assertEqual(wh.emit("folio.posted", PROP_A, {}), [])


class ScopeTestCase(_WebhookCase):
	def test_events_stay_within_their_property(self):
		self.subscribe(PROP_A, events=("folio.posted",))
		self.assertEqual(wh.emit("folio.posted", PROP_B, {"folio": "F-B"}), [])
		self.assertEqual(self.deliveries(PROP_A), [])

	def test_restricted_admin_cannot_reach_another_property(self):
		other = self.subscribe(PROP_B, events=("folio.posted",))
		delivery = wh.emit("folio.posted", PROP_B, {"folio": "F-B"})[0]
		user = ensure_user("ut.wh.admin@test.local", ["Hotel Admin"])
		if not frappe.db.exists("User Permission", {"user": user, "allow": "Property"}):
			frappe.get_doc({"doctype": "User Permission", "user": user,
			                "allow": "Property", "for_value": PROP_A}).insert(
				ignore_permissions=True)
		frappe.clear_cache(user=user)
		frappe.set_user(user)  # nosemgrep: frappe-setuser -- acting as the restricted persona under test
		self.assertEqual(wh.list_webhooks(PROP_A), [])
		for call in (lambda: wh.list_webhooks(PROP_B),
		             lambda: wh.webhook_deliveries(PROP_B),
		             lambda: wh.resend_delivery(delivery),
		             lambda: wh.delivery_detail(delivery),
		             lambda: wh.rotate_webhook_secret(other["name"]),
		             lambda: wh.delete_webhook(other["name"]),
		             lambda: wh.save_webhook(PROP_A, URL, ["folio.posted"],
		                                     name=other["name"])):
			with self.assertRaises(frappe.PermissionError):
				call()

	def test_front_desk_cannot_manage_webhooks(self):
		frappe.set_user(ensure_user("ut.wh.desk@test.local", ["Front Desk"]))  # nosemgrep: frappe-setuser -- persona under test
		with self.assertRaises(frappe.PermissionError):
			wh.save_webhook(PROP_A, URL, ["folio.posted"])
		with self.assertRaises(frappe.PermissionError):
			wh.list_webhooks(PROP_A)


class LifecycleEventsTestCase(_WebhookCase):
	def setUp(self):
		super().setUp()
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")
		self.subscribe()

	def events(self):
		return frappe.get_all(wh.DELIVERY, filters={"property": PROP_A},
		                      pluck="event", order_by="creation asc")

	def test_booking_lifecycle_fires_events_without_guest_contact(self):
		res = make_reservation(PROP_A, self.rt, d(-1), d(1), room=self.room,
		                       status="Checked In")
		self.assertEqual(self.events()[:2], ["reservation.created", "guest.checked_in"])
		from kamra import api
		api.post_stay_charge(res.name, "Food & Beverage", "UT lunch", 500)
		self.assertIn("folio.posted", self.events())
		res.reload()
		res.adults = 1
		res.save(ignore_permissions=True)
		self.assertEqual(self.events()[-1], "reservation.modified")
		payload = json.loads(frappe.get_all(
			wh.DELIVERY, filters={"property": PROP_A, "event": "reservation.modified"},
			pluck="payload")[0])
		self.assertEqual(payload["data"]["changes"]["adults"], ["2", "1"])
		self.assertEqual(payload["data"]["room_number"], "101")
		for row in frappe.get_all(wh.DELIVERY, filters={"property": PROP_A},
		                          pluck="payload"):
			data = json.loads(row)["data"]
			for leaked in ("phone", "email", "guest", "id_document",
			               "precheckin_token", "booked_by_phone"):
				self.assertNotIn(leaked, data)

	def test_cancel_fires_cancelled(self):
		res = make_reservation(PROP_A, self.rt, d(5), d(6))
		from kamra import api
		api.cancel_reservation(res.name, waive_fee=1)
		self.assertEqual(self.events()[-1], "reservation.cancelled")

	def test_muted_during_imports(self):
		frappe.flags.in_import = True
		try:
			make_reservation(PROP_A, self.rt, d(7), d(8))
		finally:
			frappe.flags.in_import = False
		self.assertEqual(self.events(), [])

	def test_night_audit_closed_payload(self):
		names = wh.emit_night_audit_closed(PROP_A, {
			"audit": "NA-1", "status": "Completed", "business_date": TODAY,
			"next_business_date": d(1), "room_charges_posted": 3,
			"amount_posted": 3000.0, "no_shows_flagged": 0, "exceptions": 0})
		env = json.loads(frappe.db.get_value(wh.DELIVERY, names[0], "payload"))
		self.assertEqual(env["event"], "night_audit.closed")
		self.assertEqual(env["data"]["business_date"], TODAY)
		self.assertEqual(env["data"]["room_charges_posted"], 3)
