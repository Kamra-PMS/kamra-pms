"""F&B Manager: runs the restaurant floor (outlets, menu, waiter list, tables,
kitchen display, F&B reports) and approves POS voids, but never reaches
folios, the cashier till, finance, the front desk or revenue."""

from __future__ import annotations

import importlib
import inspect

import frappe

from kamra import pos, settings, staff
from kamra.install import STAFF_ROLES, ensure_staff_roles
from kamra.tests.audit_fixtures import (
	PROP_A,
	TODAY,
	AuditTestCase,
	ensure_user,
	make_property,
)

ROLE = "F&B Manager"
FNB_USER = "ut.fnbmgr@example.com"


class FnbManagerTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		make_property(PROP_A, business_date=TODAY)
		name = frappe.db.get_value("POS Outlet", {"property": PROP_A,
		                                          "outlet_name": "UT FnB Grill"})
		if not name:
			name = frappe.get_doc({
				"doctype": "POS Outlet", "property": PROP_A,
				"outlet_name": "UT FnB Grill", "outlet_type": "Restaurant",
				"gst_rate": 5}).insert(ignore_permissions=True).name
		self.outlet = name
		self.dish = frappe.get_doc({
			"doctype": "Menu Item", "property": PROP_A, "outlet": name,
			"item_name": "UT FnB Kebab", "category": "Food", "price": 300,
			"is_veg": 0, "available": 1, "prep_station": "Kitchen",
		}).insert(ignore_permissions=True).name
		self.fnb = ensure_user(FNB_USER, [ROLE])
		if not frappe.db.exists("Cashier PIN", self.fnb):
			frappe.get_doc({"doctype": "Cashier PIN", "user": self.fnb,
			                "pin": "4321", "must_reset": 0}).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- restore
		super().tearDown()

	def as_(self, user):
		frappe.set_user(user)  # nosemgrep: frappe-setuser -- acting as the persona

	def test_role_is_seeded_and_assignable(self):
		self.assertIn(ROLE, STAFF_ROLES)
		ensure_staff_roles()
		self.assertTrue(frappe.db.exists("Role", ROLE))
		self.assertIn(ROLE, [r["role"] for r in staff.staff_roles()])

	def test_edits_waiters_menu_outlet_and_fnb_settings(self):
		self.as_(self.fnb)
		self.assertTrue(pos.outlet_waiters(self.outlet)["can_edit"])
		r = pos.save_outlet_waiter(self.outlet, "Farah")
		self.assertIn("Farah", [w["waiter_name"] for w in r["waiters"]])
		# menu and outlet (table map lives on the outlet) through the doctype
		item = frappe.get_doc("Menu Item", self.dish)
		item.price = 320
		item.save()
		frappe.get_doc({"doctype": "Menu Item", "property": PROP_A,
		                "outlet": self.outlet, "item_name": "UT FnB Tikka",
		                "category": "Food", "price": 250}).insert()
		outlet = frappe.get_doc("POS Outlet", self.outlet)
		outlet.tables = "T1\nT2\nT3"
		outlet.save()
		from kamra.inventory import set_menu_availability
		self.assertEqual(set_menu_availability(self.dish, 0)["available"], 0)
		mods = [m["id"] for m in settings.settings_schema(PROP_A)["modules"]]
		self.assertEqual(mods, ["fnb"])

	def test_approves_a_kitchen_void_for_a_captain(self):
		captain = ensure_user("ut.fnb.captain@example.com", ["Front Desk"])
		self.as_(captain)
		o = pos.send_order(self.outlet, [{"menu_item": self.dish, "qty": 1}],
		                   property=PROP_A, table_no="T1")
		self.assertIn(self.fnb, [a["user"] for a in pos.void_approvers(self.outlet)])
		with self.assertRaises(frappe.PermissionError):
			pos.cancel_order(o["order"], reason="guest left")
		r = pos.cancel_order(o["order"], reason="guest left",
		                     supervisor=self.fnb, supervisor_pin="4321")
		self.assertEqual(r["approved_by"], self.fnb)
		# and at their own till, with their own PIN
		o2 = pos.send_order(self.outlet, [{"menu_item": self.dish, "qty": 1}],
		                    property=PROP_A, table_no="T2")
		self.as_(self.fnb)
		self.assertEqual(pos.cancel_order(o2["order"], reason="wrong table",
		                                  supervisor_pin="4321")["approved_by"], self.fnb)

	def test_no_folio_cashier_finance_front_desk_or_revenue(self):
		for mod in ("kamra.cashier", "kamra.folio", "kamra.ledger", "kamra.night_audit",
		            "kamra.checkin", "kamra.checkout", "kamra.rates", "kamra.credit",
		            "kamra.deposit", "kamra.accounting"):
			for name, fn in inspect.getmembers(importlib.import_module(mod), callable):
				gate = getattr(fn, "_kamra_roles", None)
				if gate is not None and getattr(fn, "__module__", mod) == mod \
						and name != "list_reason_codes":  # the POS void dialog's reasons
					self.assertNotIn(ROLE, gate, f"{mod}.{name}")
		from kamra import api, cashier
		self.as_(self.fnb)
		for call in (lambda: api.get_folio("RES-NONE"),
		             lambda: cashier.open_session(PROP_A)):
			with self.assertRaises(frappe.PermissionError):
				call()
		from kamra import mcp_tools
		tools = {s.name for s in mcp_tools.allowed_tools(property=PROP_A)}
		self.assertTrue({"pos_create_order", "pos_kitchen_queue", "pos_table_map"} <= tools)
		self.assertFalse({"get_folio", "check_in", "record_payment", "set_room_rate"} & tools)
