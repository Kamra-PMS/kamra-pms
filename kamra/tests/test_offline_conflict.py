"""#228: a room or task status changed offline is sent with the status the
user saw; the server refuses it if someone changed it meanwhile."""

from __future__ import annotations

from unittest.mock import patch

import frappe

from kamra import api
from kamra.tests.audit_fixtures import PROP_A, TODAY, AuditTestCase, make_property, make_room, make_room_type


class OfflineConflictTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		make_property(PROP_A, business_date=TODAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")
		frappe.db.set_value("Room", self.room, "housekeeping_status", "Dirty")
		self._stack.enter_context(patch("kamra.housekeeping._notify_role"))

	def status(self):
		return frappe.db.get_value("Room", self.room, "housekeeping_status")

	def test_room_change_from_the_status_seen_applies(self):
		api.set_housekeeping_status(self.room, "Clean", expected="Dirty")
		self.assertEqual(self.status(), "Clean")

	def test_room_changed_meanwhile_is_refused(self):
		frappe.db.set_value("Room", self.room, "housekeeping_status", "Out of Order")
		with self.assertRaisesRegex(frappe.ValidationError, "not applied"):
			api.set_housekeeping_status(self.room, "Clean", expected="Dirty")
		self.assertEqual(self.status(), "Out of Order")
		# someone already made the same change: nothing to refuse
		api.set_housekeeping_status(self.room, "Out of Order", expected="Dirty")
		# a change made online (no expected) is not checked
		api.set_housekeeping_status(self.room, "Clean")
		self.assertEqual(self.status(), "Clean")

	def test_task_changed_meanwhile_is_refused(self):
		task = frappe.get_doc({"doctype": "Housekeeping Task", "property": PROP_A,
		                       "room": self.room, "task_type": "Checkout Clean",
		                       "priority": "High", "status": "Pending"}
		                      ).insert(ignore_permissions=True).name
		frappe.db.set_value("Housekeeping Task", task, "status", "In Progress")
		with self.assertRaisesRegex(frappe.ValidationError, "not applied"):
			api.hk_update_task(task, "Done", expected="Pending")
		api.hk_update_task(task, "Done", expected="In Progress")
		self.assertEqual(frappe.db.get_value("Housekeeping Task", task, "status"), "Done")
