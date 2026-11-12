# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""The keys kamra/contract_keys.py documents are really there (#580): call
each documented method and fire each documented webhook event."""

from __future__ import annotations

import json
import socket
from unittest.mock import patch

import frappe

from kamra import api, cashier, reports
from kamra import webhooks as wh
from kamra.contract_keys import RESPONSE_KEYS, WEBHOOK_ENVELOPE_KEYS, WEBHOOK_PAYLOAD_KEYS
from kamra.tests.audit_fixtures import (
	PROP_A,
	TODAY,
	AuditTestCase,
	d,
	make_property,
	make_reservation,
	make_room,
	make_room_type,
)


class ContractKeysTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")

	def assertKeys(self, what: str, out: dict, keys):
		missing = sorted(set(keys) - set(out))
		self.assertFalse(missing, f"{what} does not return documented keys {missing}")

	def test_documented_response_keys_are_returned(self):
		res = make_reservation(PROP_A, self.rt, d(-1), d(1), room=self.room,
		                       status="Checked In")
		folio = api.get_folio(res.name)
		sess = cashier.open_session(PROP_A, 500)["name"]
		calls = {
			"api.get_folio": folio,
			"api.folio_invoice": api.folio_invoice(folio["name"]),
			"api.property_locale": api.property_locale(PROP_A),
			"cashier.list_sessions": cashier.list_sessions(PROP_A),
			"cashier.session_report": cashier.session_report(sess),
			"reports.manager_flash": reports.manager_flash(PROP_A, TODAY),
		}
		self.assertEqual(set(calls), set(RESPONSE_KEYS), "a documented method is untested")
		for dotted, out in calls.items():
			self.assertKeys(dotted, out, RESPONSE_KEYS[dotted])

	def test_documented_webhook_payload_keys_are_sent(self):
		sent: dict[str, dict] = {}
		real_emit = wh.emit

		def capture(event, property, data):
			sent.setdefault(event, data)
			return real_emit(event, property, data)

		with patch("kamra.webhooks.emit", side_effect=capture):
			res = make_reservation(PROP_A, self.rt, d(-1), d(1), room=self.room,
			                       status="Checked In")
			api.post_stay_charge(res.name, "Food & Beverage", "UT lunch", 500)
			res.reload()
			res.adults = 1
			res.save(ignore_permissions=True)
			leaving = make_reservation(PROP_A, self.rt, d(-1), TODAY, status="Checked In",
			                           room=make_room(PROP_A, self.rt, "102"))
			frappe.flags.allow_unsettled_checkout = True  # the bill is not under test
			try:
				api.check_out(leaving.name)
			finally:
				frappe.flags.allow_unsettled_checkout = False
			other = make_reservation(PROP_A, self.rt, d(5), d(6))
			api.cancel_reservation(other.name, waive_fee=1)
			wh.emit_night_audit_closed(PROP_A, {"audit": "NA-1", "business_date": TODAY})
		for event, keys in WEBHOOK_PAYLOAD_KEYS.items():
			self.assertIn(event, sent, f"{event} was not fired")
			self.assertKeys(event, sent[event], keys)

	def test_envelope_keys(self):
		public = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
		self._stack.enter_context(patch("kamra.webhooks.socket.getaddrinfo", return_value=public))
		self._stack.enter_context(patch("kamra.webhooks._enqueue"))
		self._stack.enter_context(patch.dict(frappe.conf, {"developer_mode": 0}))
		wh.save_webhook(PROP_A, "https://hooks.example.com/kamra", ["folio.posted"])
		names = wh.emit("folio.posted", PROP_A, {"folio": "F-1"})
		env = json.loads(frappe.db.get_value(wh.DELIVERY, names[0], "payload"))
		self.assertKeys("webhook envelope", env, WEBHOOK_ENVELOPE_KEYS)
