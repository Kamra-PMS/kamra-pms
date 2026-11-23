"""A dish saved at price 0 is refused on the way to the kitchen until the
captain confirms it is free (#640)."""

from __future__ import annotations

import frappe

from kamra import pos
from kamra.tests.audit_fixtures import PROP_A, TODAY, AuditTestCase, make_property


class ZeroPriceOrderTest(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		make_property(PROP_A, business_date=TODAY)
		name = frappe.db.get_value("POS Outlet", {"property": PROP_A,
		                                          "outlet_name": "UT Free Cafe"})
		if not name:
			name = frappe.get_doc({
				"doctype": "POS Outlet", "property": PROP_A,
				"outlet_name": "UT Free Cafe", "outlet_type": "Restaurant",
				"gst_rate": 5,
			}).insert(ignore_permissions=True).name
		self.outlet = name
		self.water = frappe.get_doc({
			"doctype": "Menu Item", "property": PROP_A, "outlet": name,
			"item_name": "UT Free Water", "category": "Beverage", "price": 0,
			"is_veg": 1, "available": 1,
		}).insert(ignore_permissions=True).name

	def test_zero_is_refused_until_the_captain_confirms(self):
		items = [{"menu_item": self.water, "qty": 1}]
		with self.assertRaisesRegex(frappe.ValidationError, "no price"):
			pos.send_order(self.outlet, items, property=PROP_A, table_no="T1")
		out = pos.send_order(self.outlet, items, property=PROP_A, table_no="T1",
		                     allow_zero=1)
		self.assertTrue(out["order"])
		self.assertEqual(out["order_total"], 0)

	def test_a_priced_dish_does_not_ask(self):
		dosa = frappe.get_doc({
			"doctype": "Menu Item", "property": PROP_A, "outlet": self.outlet,
			"item_name": "UT Priced Dosa", "category": "Food", "price": 80,
			"is_veg": 1, "available": 1,
		}).insert(ignore_permissions=True).name
		out = pos.send_order(self.outlet, [{"menu_item": dosa, "qty": 1}],
		                     property=PROP_A, table_no="T2")
		self.assertGreater(out["order_total"], 0)
