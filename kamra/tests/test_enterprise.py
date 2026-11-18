# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Kamra Enterprise: the edition gate and the brochure features.

Community stays the default. These tests turn Enterprise on for one
property and check the forecast-driven rate, SMS, surveys, housekeeping
priority, maintenance, ERPNext sync and the HTTP encoder.
"""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.utils import add_days

from kamra import enterprise
from kamra.door_lock import KeyRequest, get_adapter
from kamra.enterprise_books import sync_day
from kamra.pricing import quote
from kamra.settings import save_settings
from kamra.tests.audit_fixtures import (
	AuditTestCase, make_guest, make_property, make_reservation, make_room,
	make_room_type,
)

PROP = "UT Enterprise"


class EnterpriseTests(AuditTestCase):
	properties = (PROP,)

	def setUp(self):
		super().setUp()
		self.prop = make_property(
			PROP, booking_engine_enabled=1, page_slug="ut-enterprise",
			property_amenities="Pool: heated\nSpa", email="desk@ut-enterprise.test")

	def _enable(self, **changes):
		save_settings(self.prop, "enterprise", {"ent_edition": "Enterprise", **changes})

	def test_community_is_the_default_and_refuses_the_suite(self):
		status = enterprise.enterprise_status(self.prop)
		self.assertFalse(status["enterprise"])
		self.assertEqual(status["edition"], "Community")
		with self.assertRaises(frappe.ValidationError):
			enterprise.occupancy_forecast(self.prop)

	def test_auto_pricing_uses_the_forecast_and_community_does_not(self):
		room_type = make_room_type(self.prop, base_price=1000)
		room = make_room(self.prop, room_type, "101")
		make_reservation(self.prop, room_type, "2031-06-01", "2031-06-02", room=room)
		quiet = quote(self.prop, room_type, "2031-06-01", "2031-06-02")
		self.assertEqual(quiet["nightly"][0]["demand_premium_pct"], 0)
		self._enable(ent_pricing_mode="auto")
		priced = quote(self.prop, room_type, "2031-06-01", "2031-06-02")
		self.assertEqual(priced["nightly"][0]["demand_premium_pct"], 25)
		self.assertGreater(priced["nightly"][0]["rate"], quiet["nightly"][0]["rate"])
		# suggest mode shows a forecast and leaves the quote alone
		save_settings(self.prop, "enterprise", {"ent_pricing_mode": "suggest"})
		preview = enterprise.dynamic_pricing_preview(self.prop, days=3)
		self.assertTrue(preview["days"])
		again = quote(self.prop, room_type, "2031-06-01", "2031-06-02")
		self.assertEqual(again["nightly"][0]["demand_premium_pct"], 0)

	def test_guardrail_ceiling_holds_under_auto_mode(self):
		room_type = make_room_type(self.prop, base_price=1000)
		room = make_room(self.prop, room_type, "102")
		make_reservation(self.prop, room_type, "2031-06-01", "2031-06-02", room=room)
		frappe.get_doc({
			"doctype": "Rate Guardrail", "property": self.prop,
			"room_type": room_type, "floor_price": 800, "ceiling_price": 1100,
		}).insert(ignore_permissions=True)
		self._enable(ent_pricing_mode="auto")
		priced = quote(self.prop, room_type, "2031-06-01", "2031-06-02")
		self.assertLessEqual(priced["nightly"][0]["rate"], 1100)
		self.assertEqual(priced["nightly"][0]["demand_premium_pct"], 10)

	def test_forecast_and_guest_offers(self):
		self._enable()
		forecast = enterprise.occupancy_forecast(self.prop, days=7)
		self.assertEqual(len(forecast["days"]), 7)
		self.assertIn("attendants", forecast["staffing"])
		guest = make_guest("Nora", vip=1, dietary_notes="No nuts",
		                   special_occasions="Anniversary 14 Mar")
		make_room_type(self.prop, "STD", 1000)
		make_room_type(self.prop, "DLX", 2000)
		out = enterprise.guest_recommendations(self.prop, guest)
		codes = {row["code"] for row in out["offers"]}
		self.assertIn("dietary", codes)
		self.assertIn("vip_welcome", codes)
		self.assertIn("occasion", codes)

	def test_sms_log_is_not_a_send_and_http_is(self):
		self._enable(ent_sms_provider="log")
		guest = make_guest("Omar", phone="+967700000001")
		logged = enterprise.send_guest_sms(self.prop, guest, "Welcome")
		self.assertTrue(logged["logged"])
		self.assertFalse(logged["sent"])
		self.assertEqual(logged["status"], "Logged")
		save_settings(self.prop, "enterprise", {
			"ent_sms_provider": "http",
			"ent_sms_url": "https://sms.example.test/send",
		})
		with patch("kamra.enterprise_sms.request_json", return_value=(200, '{"id":"m1"}')):
			sent = enterprise.send_guest_sms(self.prop, guest, "Welcome again")
		self.assertTrue(sent["sent"])
		self.assertEqual(sent["status"], "Sent")
		self.assertEqual(sent["provider_id"], "m1")

	def test_survey_submit(self):
		self._enable(ent_surveys=1)
		guest = make_guest("Huda", phone="+967700000002", email="huda@example.test")
		res = make_reservation(self.prop, make_room_type(self.prop), "2031-03-10", "2031-03-11",
		                       guest=guest)
		frappe.db.set_value("Reservation", res.name, {
			"status": "Checked Out", "check_out_date": "2031-03-11",
		}, update_modified=False)
		with patch("kamra.enterprise.nowdate", return_value="2031-03-12"):
			out = enterprise.send_departure_surveys(self.prop)
		self.assertEqual(out["sent"], 1)
		token = frappe.db.get_value("Guest Survey", {"reservation": res.name}, "token")
		self.assertTrue(token)
		prompt = enterprise.survey_prompt(token)
		self.assertEqual(prompt["property_name"], PROP)
		done = enterprise.submit_survey(token, 5, "Lovely stay")
		self.assertTrue(done["ok"])
		self.assertEqual(frappe.db.get_value("Guest Survey", {"token": token}, "score"), 5)
		with self.assertRaises(frappe.ValidationError):
			enterprise.submit_survey(token, 9)

	def test_arrival_priority_and_maintenance(self):
		self._enable(ent_hk_priority=1, ent_maintenance=1)
		room_type = make_room_type(self.prop)
		room = make_room(self.prop, room_type, "201")
		guest = make_guest("VIP Layla", vip=1)
		make_reservation(self.prop, room_type, add_days(frappe.utils.nowdate(), 0),
		                 add_days(frappe.utils.nowdate(), 1), room=room, guest=guest, eta="09:00")
		task = frappe.get_doc({
			"doctype": "Housekeeping Task", "property": self.prop, "room": room,
			"task_type": "Checkout Clean", "priority": "Low", "status": "Pending",
		}).insert(ignore_permissions=True)
		ordered = enterprise.prioritize_arrival_cleans(self.prop)
		self.assertEqual(frappe.db.get_value("Housekeeping Task", task.name, "priority"), "Urgent")
		self.assertTrue(ordered["tasks"])
		plan = enterprise.save_maintenance_plan(
			self.prop, "Villa pump", interval_days=30, area="Villa", next_due="2031-03-01")
		with patch("kamra.enterprise.nowdate", return_value="2031-03-12"):
			ran = enterprise.run_due_maintenance(self.prop)
		self.assertEqual(ran["created"], 1)
		self.assertEqual(str(frappe.db.get_value("Maintenance Plan", plan["name"], "next_due")),
		                 "2031-04-11")
		with patch("kamra.enterprise.nowdate", return_value="2031-03-12"):
			again = enterprise.run_due_maintenance(self.prop)
		self.assertEqual(again["created"], 0)

	def test_anomaly_scan_opens_an_alert(self):
		self._enable(ent_anomaly_z=2, ent_anomaly_min_pct=20)
		series = {
			"room_revenue": [
				("2031-02-11", 100), ("2031-02-18", 100),
				("2031-02-25", 110), ("2031-03-04", 100),
				("2031-03-11", 400),
			],
		}
		with patch("kamra.enterprise._metric_series", return_value=series):
			out = enterprise.scan_anomalies(self.prop, "2031-03-11")
		self.assertEqual(out["created"], 1)
		alert = frappe.get_all("Enterprise Alert", filters={"property": self.prop},
		                       fields=["message", "status"])[0]
		self.assertEqual(alert.status, "Open")
		self.assertIn("above", alert.message)

	def test_erpnext_remote_posts_once_and_empty_day_does_not(self):
		self._enable(ent_erp_mode="remote", ent_erp_url="https://books.example.test",
		             ent_erp_key="key", ent_erp_company="Wadi Jarif",
		             ent_acct_debtors="Debtors - WJ", ent_acct_room="Rooms - WJ",
		             ent_acct_tax="VAT - WJ")
		enterprise.save_enterprise_secrets(self.prop, erpnext_api_secret="secret")
		empty = sync_day(self.prop, "2031-03-11")
		self.assertTrue(empty["ok"])
		self.assertFalse(empty["posted"])
		self.assertEqual(empty["reason"], "nothing_to_post")
		rows = {"rows": [{"lines": [{"description": "Room", "taxable": 100, "total_tax": 15}]}],
		        "totals": {}}
		calls = []

		def fake(url, payload=None, headers=None, method="POST", timeout=8):
			calls.append(method)
			if method == "GET":
				return 200, '{"data":[]}'
			return 200, '{"data":{"name":"ACC-JV-2031-00001"}}'

		with patch("kamra.accounting.export_invoices", return_value=rows), \
		     patch("kamra.enterprise_books.request_json", side_effect=fake):
			posted = sync_day(self.prop, "2031-03-11")
		self.assertTrue(posted["posted"])
		self.assertEqual(posted["external_id"], "ACC-JV-2031-00001")
		self.assertIn("POST", calls)
		flags = enterprise.enterprise_status(self.prop)["secrets"]
		self.assertTrue(flags["erpnext"])
		self.assertNotIn("secret", str(flags))

	def test_http_encoder_and_website(self):
		self._enable(ent_door_url="https://locks.example.test/keys", ent_website=1)
		save_settings(self.prop, "front-desk", {"door_lock_adapter": "http"})
		enterprise.save_enterprise_secrets(self.prop, door_http_secret="lock-secret")

		def fake(url, payload=None, headers=None, method="POST", timeout=8):
			self.assertEqual(payload["action"], "issue")
			self.assertEqual(headers["Authorization"], "Bearer lock-secret")
			return 200, '{"key_ids":["card-9"],"message":"Key encoded."}'

		with patch("kamra.enterprise_http.request_json", side_effect=fake):
			result = get_adapter(self.prop).issue_key(KeyRequest(
				property=self.prop, reservation="RES-1", room="ROOM-1",
				room_number="101", valid_from="2031-06-01 14:00:00",
				valid_to="2031-06-03 11:00:00", key_count=2, guest_name="A"))
		self.assertTrue(result.ok)
		self.assertEqual(result.key_ids, ["card-9"])
		site = enterprise.property_site("ut-enterprise")
		self.assertTrue(site["enabled"])
		self.assertEqual(site["facilities"][0]["area"], "Pool")
		save_settings(self.prop, "enterprise", {"ent_website": 0})
		closed = enterprise.property_site("ut-enterprise")
		self.assertFalse(closed["enabled"])
		self.assertIn("/stay/", closed["stay_path"])

	def test_http_encoder_refuses_on_community(self):
		save_settings(self.prop, "front-desk", {"door_lock_adapter": "http"})
		save_settings(self.prop, "enterprise", {"ent_door_url": "https://locks.example.test/keys"})
		result = get_adapter(self.prop).issue_key(KeyRequest(
			property=self.prop, reservation="RES-1", room="ROOM-1",
			room_number="101", valid_from="", valid_to="", key_count=1))
		self.assertFalse(result.ok)
		self.assertIn("Enterprise", result.message)
