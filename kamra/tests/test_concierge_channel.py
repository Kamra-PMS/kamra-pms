"""Guest concierge channel: a concierge credential reaches the four signed
concierge endpoints and nothing else (no staff MCP tool, no folio, no other
guest), nothing changes a stay without the stay token or a one-time code,
and channel webhooks keep a summary, not the guest's words."""

import hashlib
import hmac
import json
import time
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, now_datetime, nowdate

from kamra import agents_channels as ch
from kamra import service_accounts as sa
from kamra.mcp_access import mcp_level, property_policy, tool_refusal
from kamra.mcp_tools import TOOLS, resolve_endpoint, tool_allowed

HOME = "TEST Concierge Home"
OTHER = "TEST Concierge Other"
LINE = "+910000000564"
SECRET = "concierge-test-secret"
ENDPOINTS = ("concierge_context", "stay_context", "guest_request", "channel_book")


def _property(name: str) -> str:
	if not frappe.db.exists("Property", name):
		frappe.get_doc({"doctype": "Property", "property_name": name}).insert(
			ignore_permissions=True)
	return name


def _guest(first: str, phone: str) -> frappe._dict:
	doc = frappe.get_doc({"doctype": "Guest", "first_name": first, "phone": phone}).insert(
		ignore_permissions=True)
	return frappe._dict(name=doc.name, phone=doc.phone)


def _stay(guest: str, prop: str, status: str = "Confirmed", days: int = 0) -> str:
	doc = frappe.get_doc({
		"doctype": "Reservation", "property": prop, "guest": guest,
		"room_type": "Concierge Test", "status": status, "adults": 2,
		"check_in_date": add_days(nowdate(), days),
		"check_out_date": add_days(nowdate(), days + 2),
		"precheckin_token": frappe.generate_hash(length=32),
	})
	doc.set_new_name()
	doc.db_insert()
	return doc.name


def _signed(fn, body: dict, secret: str = SECRET, ts=None):
	body = {"phone_number": LINE, **body, "ts": int(ts if ts is not None else time.time())}
	sig = hmac.new(secret.encode(), json.dumps(body, sort_keys=True, default=str).encode(),
	               hashlib.sha256).hexdigest()
	with patch("frappe.get_request_header",
	           side_effect=lambda h, *a: sig if h == "X-Kamra-Signature" else None):
		return fn(**body)


class ConciergeChannelTestCase(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture setup
		self._commit, frappe.db.commit = frappe.db.commit, lambda *a, **k: None
		from kamra.install import ensure_agent_identity

		ensure_agent_identity()
		_property(HOME)
		_property(OTHER)
		self.acct = sa.create_service_account("TEST concierge", [sa.CONCIERGE], [HOME])
		self.conn = frappe.get_doc({
			"doctype": "Channel Provider Connection", "property": HOME,
			"channel": "WhatsApp", "provider": "Custom", "active": 1,
			"phone_number": LINE, "webhook_secret": SECRET,
			"service_account": self.acct["name"],
		}).insert(ignore_permissions=True)
		self.me = _guest("Asha", "+919800000561")
		self.stranger = _guest("Bina", "+919800000562")
		self.past = _guest("Chitra", "+919800000563")
		self.my_stay = _stay(self.me.name, HOME)
		self.their_stay = _stay(self.stranger.name, OTHER)
		_stay(self.past.name, HOME, status="Checked Out", days=-10)

	def tearDown(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture teardown
		frappe.db.commit = self._commit
		frappe.local.cache.pop("kamra_service_accounts", None)
		frappe.db.rollback()

	def _as_concierge(self):
		frappe.local.cache.pop("kamra_service_accounts", None)
		frappe.set_user(self.acct["user"])  # nosemgrep: frappe-setuser -- acting as the concierge service account under test
		return sa.account_for()

	def test_concierge_credential_never_reaches_staff_tools(self):
		account = self._as_concierge()
		user = self.acct["user"]
		# no staff role at all, so even a call past the gate fails require_roles
		roles = set(frappe.get_all("Has Role", filters={"parent": user, "parenttype": "User"},
		                           pluck="role"))
		self.assertEqual(roles, {sa.ROLE})
		self.assertIsNone(mcp_level(user))
		self.assertTrue(sa.refusal(account, "/mcp"))
		policy = property_policy(HOME)
		for spec in TOOLS:
			self.assertTrue(sa.refusal(account, f"/api/method/kamra.{spec.dotted}"), spec.name)
			self.assertTrue(tool_refusal(spec, "manage", policy), spec.name)
			if getattr(resolve_endpoint(spec.dotted), "_kamra_roles", None):
				self.assertFalse(tool_allowed(spec, roles), spec.name)
		for path in ("/api/resource/Folio", "/api/resource/Guest", "/api/resource/Reservation",
		             "/api/v2/document/Folio", "/api/method/kamra.api.get_folio",
		             "/api/method/kamra.api.guests_with_stats",
		             "/api/method/kamra.assistant.chat", "/app/folio"):
			self.assertTrue(sa.refusal(account, path), path)
		for name in ENDPOINTS:
			self.assertIsNone(sa.refusal(account, f"/api/method/kamra.agents_channels.{name}"))

	def test_staff_endpoints_refuse_the_concierge_user_in_process(self):
		from kamra import api

		self._as_concierge()
		with self.assertRaises(frappe.PermissionError):
			api.get_folio(self.my_stay)
		with self.assertRaises(frappe.PermissionError):
			api.guests_with_stats()

	def test_signature_freshness_and_account_link(self):
		self._as_concierge()
		with self.assertRaises(frappe.PermissionError):
			_signed(ch.concierge_context, {}, secret="wrong")
		with self.assertRaises(frappe.PermissionError):
			_signed(ch.concierge_context, {}, ts=time.time() - 3600)
		with self.assertRaises(frappe.PermissionError):
			_signed(ch.concierge_context, {"property": OTHER})
		facts = _signed(ch.concierge_context, {})
		self.assertEqual(facts["property"], HOME)

		# a staff service account, and a concierge key not linked to this line
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- creating the other accounts
		staff = sa.create_service_account("TEST staff", ["reports.read"], [HOME])
		other = sa.create_service_account("TEST other concierge", [sa.CONCIERGE], [HOME])
		for acct in (staff, other):
			frappe.local.cache.pop("kamra_service_accounts", None)
			frappe.set_user(acct["user"])  # nosemgrep: frappe-setuser -- acting as the account under test
			with self.assertRaises(frappe.PermissionError):
				_signed(ch.stay_context, {"guest_phone": self.me.phone})

	def test_stay_context_is_minimal_and_own_stay_only(self):
		self._as_concierge()
		mine = _signed(ch.stay_context, {"guest_phone": self.me.phone})
		self.assertTrue(mine["found"])
		self.assertEqual(mine["reservation"], self.my_stay)
		self.assertEqual(set(mine), {
			"found", "reservation", "status", "check_in_date", "check_out_date", "room_type",
			"adults", "children", "first_name", "vip", "category", "stays_count", "last_stay"})
		# a guest whose stay is at another property, a past guest, a stranger
		for phone in (self.stranger.phone, self.past.phone, "+919800000569", ""):
			self.assertEqual(_signed(ch.stay_context, {"guest_phone": phone}), {"found": False})

	def test_guest_request_needs_token_or_otp(self):
		self._as_concierge()
		sent = []
		with patch.object(ch, "send_outbound",
		                  side_effect=lambda *a, **k: sent.append((a, k)) or {"sent": True}):
			ask = _signed(ch.guest_request, {"reservation": self.my_stay, "kind": "housekeeping",
			                                 "note": "Two more towels please"})
		self.assertTrue(ask["otp_required"])
		self.assertEqual(sent[0][1]["log_as"], "one-time code to the guest")
		code = sent[0][0][3][:6]
		self.assertNotIn(code, sent[0][1]["log_as"])
		with self.assertRaises(frappe.PermissionError):
			_signed(ch.guest_request, {"reservation": self.my_stay, "kind": "housekeeping",
			                           "otp": "000000" if code != "000000" else "111111"})
		done = _signed(ch.guest_request, {"reservation": self.my_stay, "kind": "housekeeping",
		                                  "note": "Two more towels please", "otp": code})
		ticket = frappe.db.get_value("Service Ticket", done["ticket"],
		                             ["reservation", "source", "category"], as_dict=True)
		self.assertEqual((ticket.reservation, ticket.source, ticket.category),
		                 (self.my_stay, "WhatsApp", "Housekeeping"))

		token = frappe.db.get_value("Reservation", self.my_stay, "precheckin_token")
		with self.assertRaises(frappe.PermissionError):
			_signed(ch.guest_request, {"reservation": self.my_stay, "kind": "late_check_out",
			                           "stay_token": "x" * 32})
		late = _signed(ch.guest_request, {"reservation": self.my_stay, "kind": "late_check_out",
		                                  "stay_token": token})
		self.assertEqual(late["stay_instruction"], "Front Desk")
		# another property's stay, even with its token
		other_token = frappe.db.get_value("Reservation", self.their_stay, "precheckin_token")
		with self.assertRaises(frappe.PermissionError):
			_signed(ch.guest_request, {"reservation": self.their_stay, "kind": "extra_bed",
			                           "stay_token": other_token})

	def test_webhooks_keep_a_summary_not_guest_text(self):
		frappe.set_user("Guest")  # nosemgrep: frappe-setuser -- webhooks are called by the provider without a session
		words = "my card number is 4111 and I am in room 12"
		body = {"phone_number": LINE, "guest_phone": self.me.phone, "message_id": "wamid.T566",
		        "text": words}
		sig = hmac.new(SECRET.encode(), json.dumps(body, sort_keys=True).encode(),
		               hashlib.sha256).hexdigest()
		with patch("frappe.get_request_header", return_value=sig):
			res = ch.messaging_webhook(body)
		self.assertTrue(res["ok"])
		row = frappe.db.get_value("Agent Action Log", res["log"],
		                          ["rationale", "after_snapshot"], as_dict=True)
		self.assertNotIn("4111", row.rationale)
		self.assertIn("wamid.T566", row.after_snapshot)

		# voice: the transcript never lands, the summary is capped
		voice = frappe.get_doc({
			"doctype": "Channel Provider Connection", "property": HOME, "channel": "Voice",
			"provider": "Custom", "active": 1, "phone_number": LINE, "webhook_secret": SECRET,
		}).insert(ignore_permissions=True)
		self.assertTrue(voice.name)
		body = {"phone_number": LINE, "guest_phone": self.me.phone, "call_id": "call-566",
		        "event": "call_ended", "summary": "Asked about breakfast. " * 40,
		        "transcript": words}
		sig = hmac.new(SECRET.encode(), json.dumps(body, sort_keys=True).encode(),
		               hashlib.sha256).hexdigest()
		with patch("frappe.get_request_header", return_value=sig):
			res = ch.voice_webhook(body)
		rationale = frappe.db.get_value("Agent Action Log", res["log"], "rationale")
		self.assertNotIn("4111", rationale)
		self.assertLess(len(rationale), 400)
		self.assertIn("call-566", rationale)

	def test_retention_clears_old_channel_rows(self):
		from kamra.privacy import CLEARED_CHANNEL_LOG, clear_channel_logs
		from kamra.savings import log_action

		name = log_action("whatsapp.outbound", property=HOME, rationale="To +91 via Custom: hi",
		                  channel="WhatsApp")
		frappe.db.sql("UPDATE `tabAgent Action Log` SET creation = %s WHERE name = %s",
		              (add_days(now_datetime(), -40), name))
		self.assertGreaterEqual(clear_channel_logs(HOME, add_days(now_datetime(), -30)), 1)
		self.assertEqual(frappe.db.get_value("Agent Action Log", name, "rationale"),
		                 CLEARED_CHANNEL_LOG)

	def test_patch_trims_existing_rows(self):
		from kamra.patches.v48 import trim_channel_webhook_logs
		from kamra.savings import log_action

		wa = log_action("whatsapp.inbound", property=HOME,
		                rationale="WhatsApp inbound: my passport is X123", channel="WhatsApp")
		vo = log_action("voice.call_ended", property=HOME,
		                rationale="Booked a spa slot\n\nfull transcript with X123", channel="Voice")
		trim_channel_webhook_logs.execute()
		self.assertNotIn("X123", frappe.db.get_value("Agent Action Log", wa, "rationale"))
		self.assertEqual(frappe.db.get_value("Agent Action Log", vo, "rationale"),
		                 "Booked a spa slot")
