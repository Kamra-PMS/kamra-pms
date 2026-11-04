"""The notification bell: each department sees its own lines, never its own
actions, and "read" is a per-person timestamp."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import frappe

from kamra import notifications
from kamra.tests.audit_fixtures import PROP_A, AuditTestCase, ensure_user, make_property

HK = "ut-bell-hk@example.com"
DESK = "ut-bell-desk@example.com"


class _Doc(SimpleNamespace):
	"""Just enough of a document for the hook functions."""

	def get(self, key, default=None):
		return getattr(self, key, default)

	def get_doc_before_save(self):
		return getattr(self, "before", None)


def _lines(module=None):
	filters = {"property": PROP_A}
	if module:
		filters["module"] = module
	return frappe.get_all("Kamra Notification", filters=filters, pluck="subject")


class TestNotificationBell(AuditTestCase):
	def setUp(self):
		super().setUp()
		make_property(PROP_A, enabled_modules="")
		ensure_user(HK, ["Housekeeping"])
		ensure_user(DESK, ["Front Desk"])
		frappe.db.delete("Kamra Notification", {"property": PROP_A})
		frappe.db.delete("Kamra Notification Read", {"property": PROP_A})
		for user in (HK, DESK, "Administrator"):
			frappe.defaults.clear_user_default(notifications._seen_key(PROP_A), user)

	def test_each_person_sees_only_the_modules_they_work_in(self):
		self.assertEqual(notifications.visible_modules(PROP_A, HK), ["housekeeping"])
		self.assertIn("front-desk", notifications.visible_modules(PROP_A, DESK))
		self.assertNotIn("events", notifications.visible_modules(PROP_A, HK))
		self.assertEqual(notifications.visible_modules(PROP_A, "Administrator"),
		                 list(notifications.MODULE_ROLES))

	def test_a_module_the_property_doesnt_run_stays_quiet(self):
		make_property(PROP_A, enabled_modules="front-desk,admin")
		self.assertEqual(notifications.visible_modules(PROP_A, HK), [])

	def test_housekeeping_does_not_see_front_desk_lines(self):
		notifications.record(PROP_A, "front-desk", "New booking - Asha")
		notifications.record(PROP_A, "housekeeping", "Room 101 is empty - needs cleaning")
		frappe.set_user(HK)  # nosemgrep: frappe-setuser -- test fixture
		got = notifications.bell(PROP_A)
		self.assertEqual([i["subject"] for i in got["items"]],
		                 ["Room 101 is empty - needs cleaning"])
		self.assertEqual(got["unread"], 1)

	def test_your_own_actions_are_left_out(self):
		frappe.set_user(DESK)  # nosemgrep: frappe-setuser -- test fixture
		notifications.record(PROP_A, "front-desk", "New booking - Asha")
		self.assertEqual(notifications.bell(PROP_A)["items"], [])

	def test_mark_read_clears_the_count(self):
		notifications.record(PROP_A, "housekeeping", "New task: Deep Clean")
		frappe.set_user(HK)  # nosemgrep: frappe-setuser -- test fixture
		self.assertEqual(notifications.bell(PROP_A)["unread"], 1)
		notifications.mark_read(PROP_A)
		got = notifications.bell(PROP_A)
		self.assertEqual(got["unread"], 0)
		self.assertEqual(got["items"], [])

	def test_an_opened_notification_leaves_only_that_persons_list(self):
		notifications.record(PROP_A, "housekeeping", "New task: Deep Clean")
		notifications.record(PROP_A, "housekeeping", "Laundry to collect")
		frappe.set_user(HK)  # nosemgrep: frappe-setuser -- test fixture
		first = notifications.bell(PROP_A)["items"][0]
		notifications.open_one(PROP_A, first["name"])
		got = notifications.bell(PROP_A)
		self.assertEqual(got["unread"], 1)
		self.assertNotIn(first["name"], [i["name"] for i in got["items"]])
		frappe.set_user(DESK)  # nosemgrep: frappe-setuser -- test fixture
		self.assertEqual(notifications.bell(PROP_A)["unread"], 2)  # still there for others

	def test_check_out_tells_the_desk_and_housekeeping(self):
		doc = _Doc(doctype="Reservation", name="RES-UT-1", property=PROP_A,
		           guest_name="Asha", room="101", status="Checked Out",
		           before=SimpleNamespace(status="Checked In"))
		notifications.on_reservation_update(doc)
		self.assertEqual(_lines("front-desk"), ["Checked out - Asha - Room 101"])
		self.assertEqual(_lines("housekeeping"), ["Room 101 is empty - needs cleaning"])
		# the booking page opens a stay with ?open=, there is no /reservations/<id> page
		self.assertEqual(frappe.db.get_value("Kamra Notification", {"property": PROP_A, "module": "front-desk"}, "route"),
		                 "/reservations?open=RES-UT-1")

	def test_a_save_without_a_status_change_is_quiet(self):
		doc = _Doc(doctype="Reservation", name="RES-UT-1", property=PROP_A,
		           guest_name="Asha", room="101", status="Checked In",
		           before=SimpleNamespace(status="Checked In"))
		notifications.on_reservation_update(doc)
		self.assertEqual(_lines(), [])

	def test_an_enquiry_is_not_a_new_booking(self):
		notifications.on_reservation_insert(_Doc(
			doctype="Reservation", name="RES-UT-2", property=PROP_A, guest_name="Ravi",
			status="Inquiry", check_in_date="2026-11-12", check_out_date="2026-11-14"))
		self.assertEqual(_lines(), [])

	def test_the_tills_own_dine_in_order_is_left_to_the_kitchen_screen(self):
		order = dict(doctype="POS Order", name="POS-UT-1", property=PROP_A,
		             room=None, table_no="3", order_type="Dine In")
		notifications.on_pos_order_insert(_Doc(source="Manual", **order))
		self.assertEqual(_lines("fnb"), [])
		notifications.on_pos_order_insert(_Doc(source="QR", **order))
		self.assertEqual(_lines("fnb"), ["New dine in order - Table 3"])

	def test_old_lines_are_dropped(self):
		notifications.record(PROP_A, "finance", "Night audit held")
		name = frappe.get_all("Kamra Notification", filters={"property": PROP_A}, pluck="name")[0]
		frappe.db.set_value("Kamra Notification", name, "creation",
		                    frappe.utils.add_days(frappe.utils.now_datetime(), -31))
		notifications.purge_old()
		self.assertEqual(_lines(), [])


class _Meta:
	@staticmethod
	def get_label(field):
		return {"base_price": "Base Price"}.get(field, field)


class TestMoreNotifications(AuditTestCase):
	def setUp(self):
		super().setUp()
		make_property(PROP_A, enabled_modules="")
		frappe.db.delete("Kamra Notification", {"property": PROP_A})

	def test_a_payment_a_refund_and_a_desk_charge_tell_finance(self):
		old = _Doc(name="P0", payment_kind="Payment", mode="Cash", amount=100)
		before = _Doc(payments=[old], charges=[])
		doc = _Doc(doctype="Folio", name="FOL-UT-1", property=PROP_A, guest_name="Asha",
		           before=before,
		           payments=[old,
		                     _Doc(name="P1", payment_kind="Payment", mode="UPI", amount=5000),
		                     _Doc(name="P2", payment_kind="Refund", mode="Cash", amount=-500)],
		           charges=[_Doc(name="C1", description="Minibar", total=300, auto_posted=0),
		                    _Doc(name="C2", description="Room", total=4000, auto_posted=1)])
		notifications.on_folio_update(doc)
		got = sorted(_lines("finance"))
		self.assertEqual(len(got), 3)  # the old payment and the audit's room charge stay quiet
		self.assertTrue(any(s.startswith("Payment received - ") and "UPI - Asha" in s for s in got))
		self.assertTrue(any(s.startswith("Refund - ") and "Cash - Asha" in s for s in got))
		self.assertTrue(any(s.startswith("Charge posted - Minibar") for s in got))

	def test_the_kitchen_finishing_an_order_tells_the_floor_once(self):
		fired = [_Doc(kot_status="Fired"), _Doc(kot_status="Prepared")]
		ready = [_Doc(kot_status="Prepared"), _Doc(kot_status="Prepared"),
		         _Doc(kot_status="Fired", voided=1)]
		order = dict(doctype="POS Order", name="POS-UT-2", property=PROP_A,
		             room=None, table_no="5", kot_no="12")
		notifications.on_pos_order_update(_Doc(items=ready, before=_Doc(items=fired), **order))
		self.assertEqual(_lines("fnb"), ["Order ready (KOT 12) - Table 5"])
		notifications.on_pos_order_update(_Doc(items=ready, before=_Doc(items=ready), **order))
		self.assertEqual(len(_lines("fnb")), 1)

	def test_low_stock_tells_only_when_it_crosses_the_minimum(self):
		def value(doctype, name, field=None, *a, **k):
			if doctype == "Ingredient Stock":
				return 5
			if doctype == "Ingredient":
				return ("Tomato", "kg")
			return frappe.db.__class__.get_value(frappe.db, doctype, name, field, *a, **k)

		entry = dict(property=PROP_A, outlet="OUT-1", ingredient="ING-1")
		with patch.object(frappe.db, "get_value", side_effect=value):
			notifications.on_ingredient_ledger_insert(_Doc(qty_change=-3, balance_after=4, **entry))
			notifications.on_ingredient_ledger_insert(_Doc(qty_change=-1, balance_after=3, **entry))
			notifications.on_ingredient_ledger_insert(_Doc(qty_change=10, balance_after=13, **entry))
		self.assertEqual(_lines("fnb"), ["Low stock - Tomato: 4 kg left (minimum 5)"])

	def test_resolved_request_and_finished_task(self):
		notifications.on_service_ticket_update(_Doc(
			doctype="Service Ticket", name="TKT-UT", property=PROP_A, subject="AC not working",
			room="204", status="Resolved", before=SimpleNamespace(status="In Progress")))
		notifications.on_housekeeping_task_update(_Doc(
			doctype="Housekeeping Task", name="HK-UT", property=PROP_A, task_type="Checkout Clean",
			room="204", status="Done", before=SimpleNamespace(status="In Progress")))
		self.assertEqual(_lines("operations"), ["Request resolved: AC not working - Room 204"])
		self.assertEqual(_lines("housekeeping"), ["Checkout Clean done - Room 204"])

	def test_a_price_change_reaches_revenue_only(self):
		doc = _Doc(doctype="Room Type", name="UT-DLX", property=PROP_A, room_type_name="Deluxe",
		           meta=_Meta(), base_price=4500, before=_Doc(base_price=4000))
		notifications.on_room_type_update(doc)
		self.assertEqual(len(_lines("revenue")), 1)
		self.assertIn("Deluxe Base Price", _lines("revenue")[0])
		ensure_user(HK, ["Housekeeping"])
		self.assertNotIn("revenue", notifications.visible_modules(PROP_A, HK))
		ensure_user("ut-bell-rev@example.com", ["Revenue Manager"])
		rev = notifications.visible_modules(PROP_A, "ut-bell-rev@example.com")
		self.assertIn("revenue", rev)
		self.assertNotIn("front-desk", rev)

	def test_saving_a_season_without_changing_the_rate_is_quiet(self):
		same = dict(adjustment_type="Absolute", adjustment_value=5000, start_date="2026-12-24",
		            end_date="2026-12-26", room_type=None, disabled=0)
		doc = _Doc(doctype="Season", name="SEA-UT", property=PROP_A, before=_Doc(**same), **same)
		notifications.on_season_change(doc, "on_update")
		self.assertEqual(_lines(), [])
		notifications.on_season_change(_Doc(doctype="Season", name="SEA-UT", property=PROP_A,
		                                    **same), "after_insert")
		self.assertEqual(_lines("revenue"), ["Rate added - 2026-12-24 to 2026-12-26"])
