"""WhatsApp marketing consent (#89): promotional templates go only to guests
who opted in; STOP-style replies withdraw it; every change is logged.
Service messages (booking, check-in link, payment) are untouched."""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.utils import add_days, nowdate

from kamra import api, public_api, whatsapp
from kamra.privacy import set_marketing_consent, update_marketing_consent
from kamra.tests.audit_fixtures import PROP_A, AuditTestCase, make_guest, make_property, make_room, make_room_type

PHONE = "919800089089"


class MarketingConsentTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		frappe.local.lang = "en"  # booking writes a Version diff, which formats dates per language
		make_property(PROP_A)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		make_room(PROP_A, self.rt, "101")
		frappe.db.delete("Guest", {"phone": ("in", [PHONE, f"+{PHONE}"])})
		frappe.db.delete("Channel Provider Connection", {"external_account_id": "ut-89-phone"})
		frappe.get_doc({
			"doctype": "Channel Provider Connection", "property": PROP_A,
			"channel": "WhatsApp", "provider": "Meta Business", "active": 1,
			"phone_number": "+91 98450 00089", "external_account_id": "ut-89-phone",
			"credentials": "ut-token", "webhook_secret": "ut-verify", "meta_language": "en",
		}).insert(ignore_permissions=True)
		self.sent = []
		self._stack.enter_context(patch.object(
			whatsapp, "_post_graph",
			lambda conn, payload: self.sent.append(payload) or (True, f"wamid.ut{len(self.sent)}")))
		self.guest = make_guest("UT Consent", phone=PHONE)

	def consent(self):
		return frappe.db.get_value("Guest", self.guest, ["marketing_consent", "marketing_consent_date",
		                                                 "marketing_consent_source"], as_dict=True)

	def logs(self, action):
		return frappe.get_all("Agent Action Log", pluck="name",
		                      filters={"action_type": action, "reference_name": self.guest})

	def inbound(self, text):
		whatsapp._handle_inbound({
			"metadata": {"phone_number_id": "ut-89-phone"},
			"messages": [{"from": PHONE, "id": frappe.generate_hash(length=10),
			              "type": "text", "text": {"body": text}}],
		})

	def test_marketing_refused_without_consent(self):
		# no guest passed: the guest is found by phone
		out = whatsapp.send_template(PROP_A, PHONE, "ut_promo", ["x"], marketing=True)
		self.assertEqual(out["reason"], "no_marketing_consent")
		self.assertRaises(frappe.PermissionError, whatsapp.send_marketing, PROP_A, self.guest, "ut_promo")
		self.assertEqual(self.sent, [])

	def test_marketing_sent_with_consent(self):
		self.assertTrue(set_marketing_consent(self.guest, 1, "Desk"))
		out = whatsapp.send_marketing(PROP_A, self.guest, "ut_promo", '["Diwali"]')
		self.assertTrue(out["sent"])
		self.assertEqual(self.sent[-1]["template"]["name"], "ut_promo")
		self.assertTrue(whatsapp.send_template(PROP_A, PHONE, "ut_promo", [], marketing=True)["sent"])

	def test_service_template_unaffected(self):
		out = whatsapp.send_template(PROP_A, PHONE, "ut_booking_confirmation", ["a"], guest=self.guest)
		self.assertTrue(out["sent"])
		self.assertEqual(len(self.sent), 1)

	def test_stop_keywords_withdraw_and_confirm_once(self):
		words = [" STOP ", "stop", "Unsubscribe", "BAJA", "alto!", "إلغاء", "الغاء", "توقف", "PARAR", "Sair."]
		for word in words:
			set_marketing_consent(self.guest, 1, "Desk")
			before = len(self.sent)
			self.inbound(word)
			c = self.consent()
			self.assertEqual((c.marketing_consent, c.marketing_consent_source), (0, "WhatsApp Keyword"), word)
			self.assertEqual(len(self.sent), before + 1, word)
			self.assertEqual(self.sent[-1]["type"], "text")
		self.assertEqual(len(self.logs("marketing_consent_withdrawn")), len(words))
		# already withdrawn: no second confirmation, no new log row
		before = len(self.sent)
		self.inbound("STOP")
		self.assertEqual(len(self.sent), before)
		self.assertEqual(len(self.logs("marketing_consent_withdrawn")), len(words))
		# a keyword is not a service request; ordinary text is not a keyword
		self.inbound("please stop the room cleaning")
		self.assertEqual(self.consent().marketing_consent, 0)

	def test_start_regrants(self):
		self.inbound("Start")
		c = self.consent()
		self.assertEqual((c.marketing_consent, c.marketing_consent_source), (1, "WhatsApp Keyword"))
		self.assertEqual(len(self.sent), 1)
		self.assertEqual(len(self.logs("marketing_consent_granted")), 1)

	def test_booking_page_opt_in(self):
		book = getattr(public_api.book, "__wrapped__", public_api.book)
		def stay(day):
			return dict(property=PROP_A, room_type=self.rt, check_in_date=add_days(nowdate(), day),
			            check_out_date=add_days(nowdate(), day + 1), adults=1)
		book(guest_name="UT No Box", phone="919800089001", **stay(30))
		self.assertFalse(frappe.db.get_value("Guest", {"phone": "919800089001"}, "marketing_consent"))
		frappe.db.delete("Guest", {"phone": PHONE})
		out = book(guest_name="UT Box", phone=PHONE, marketing_consent=1, **stay(32))
		guest = frappe.db.get_value("Reservation", out["reservation"], "guest")
		c = frappe.db.get_value("Guest", guest, ["marketing_consent", "marketing_consent_date",
		                                         "marketing_consent_source"], as_dict=True)
		self.assertEqual((c.marketing_consent, c.marketing_consent_source), (1, "Booking Page"))
		self.assertTrue(c.marketing_consent_date)

	def test_desk_booking_and_toggle(self):
		api.create_booking(PROP_A, self.rt, add_days(nowdate(), 40), add_days(nowdate(), 41),
		                   "UT Consent", guest=self.guest, marketing_consent=1)
		self.assertEqual(self.consent().marketing_consent_source, "Desk")
		out = update_marketing_consent(self.guest, 0)
		self.assertEqual((out.marketing_consent, out.marketing_consent_source), (0, "Desk"))
		self.assertTrue(out.marketing_consent_date)
		self.assertEqual(len(self.logs("marketing_consent_granted")), 1)
		self.assertEqual(len(self.logs("marketing_consent_withdrawn")), 1)

	def test_plain_save_cannot_set_consent(self):
		doc = frappe.get_doc("Guest", self.guest)
		doc.marketing_consent = 1
		self.assertRaises(frappe.ValidationError, doc.save, ignore_permissions=True)
		self.assertRaises(frappe.ValidationError, make_guest, "UT Sneaky", marketing_consent=1)
