"""An outlet's levy (a service charge) on its restaurant bills.

The levy is a percentage of the bill after discount, added to the order total.
"Tax applies to the levy" says whether the outlet's tax is charged on it too.
On a room charge it posts as its own Food & Beverage line. A bill that is paid
or already on a room keeps the levy it was charged. NC bills get none. A
property whose country e-invoices every POS bill (Saudi Arabia) cannot set one.

Prices are from a real menu (Nasi Goreng 35.000, Es Teh 12.000).
"""

from __future__ import annotations

from unittest.mock import patch

import frappe

from kamra import pos
from kamra.tests.audit_fixtures import (
	PROP_A,
	TODAY,
	AuditTestCase,
	d,
	guest_folio,
	make_property,
	make_reservation,
	make_room,
	make_room_type,
)


class PosLevyTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY)
		self.outlet = self.make_outlet(levy_percent=10, levy_taxable=1)
		self.food = self.make_item("UT Levy Nasi Goreng", 35000)
		self.drink = self.make_item("UT Levy Es Teh", 12000)

	def make_outlet(self, **levy):
		name = frappe.db.get_value("POS Outlet", {"property": PROP_A,
		                                          "outlet_name": "UT Levy Warung"})
		fields = {"levy_label": "Service charge", "levy_percent": 0,
		          "levy_taxable": 1, **levy}
		if name:
			frappe.db.set_value("POS Outlet", name, fields)
			return name
		return frappe.get_doc({
			"doctype": "POS Outlet", "property": PROP_A,
			"outlet_name": "UT Levy Warung", "outlet_type": "Restaurant",
			"gst_rate": 5, **fields}).insert(ignore_permissions=True).name

	def make_item(self, label, price):
		return frappe.get_doc({
			"doctype": "Menu Item", "property": PROP_A, "outlet": self.outlet,
			"item_name": label, "category": "Food", "price": price,
			"is_veg": 1, "available": 1, "prep_station": "Kitchen",
		}).insert(ignore_permissions=True).name

	def order(self, **kw):
		lines = [{"menu_item": self.food, "qty": 1},
		         {"menu_item": self.drink, "qty": 2}]
		return pos.create_order(self.outlet, lines, table_no="T1",
		                        order_type="Dine In", **kw)["order"]

	def doc(self, order):
		return frappe.get_doc("POS Order", order)

	# the maths ---------------------------------------------------------

	def test_an_outlet_without_a_levy_bills_as_before(self):
		self.make_outlet(levy_percent=0)
		o = self.doc(self.order())
		self.assertEqual(o.subtotal, 59000)
		self.assertEqual(o.order_total, 59000)
		self.assertEqual(o.levy_amount, 0)
		bill = pos.bill_data(o.name)
		self.assertIsNone(bill["levy"])
		self.assertEqual(bill["taxable"], 59000)
		self.assertAlmostEqual(bill["grand_total"], 59000 * 1.05, 2)

	def test_the_levy_is_a_percentage_of_the_bill_after_discount(self):
		o = self.order()
		pos.apply_discount(o, 9000, "regular")
		doc = self.doc(o)
		self.assertEqual(doc.subtotal, 59000)
		self.assertEqual(doc.levy_amount, 5000)       # 10% of 50.000
		self.assertEqual(doc.order_total, 55000)      # items 50.000 + levy 5.000
		self.assertEqual((doc.levy_label, doc.levy_percent), ("Service charge", 10))

	def test_the_tax_is_charged_on_the_levy_when_the_outlet_says_so(self):
		o = self.order()
		pos.apply_discount(o, 9000, "regular")
		bill = pos.bill_data(o)
		self.assertEqual(bill["levy"], {"label": "Service charge", "percent": 10.0,
		                                "amount": 5000.0})
		self.assertEqual(bill["taxable"], 55000)          # 5% on items + levy
		self.assertAlmostEqual(bill["grand_total"], 55000 + 2750, 2)

	def test_the_tax_skips_the_levy_when_the_outlet_says_so(self):
		self.make_outlet(levy_percent=10, levy_taxable=0)
		o = self.order()
		pos.apply_discount(o, 9000, "regular")
		bill = pos.bill_data(o)
		self.assertEqual(bill["taxable"], 50000)          # 5% on the items only
		self.assertAlmostEqual(bill["grand_total"], 55000 + 2500, 2)
		self.assertEqual(self.doc(o).levy_taxable, 0)

	def test_an_nc_bill_carries_no_levy(self):
		o = self.order()
		pos.mark_nc(o, "Chef", "birthday")
		doc = self.doc(o)
		self.assertEqual((doc.order_total, doc.levy_amount), (0, 0))
		pos.mark_nc(o, "", undo=1)
		self.assertEqual(self.doc(o).order_total, 64900)  # 59.000 + 5.900 back

	def test_the_levy_follows_added_items(self):
		o = self.order()
		doc = self.doc(o)
		doc.append("items", {"menu_item": self.drink, "item_name": "UT Levy Es Teh",
		                     "qty": 1, "rate": 12000})
		doc.save()
		self.assertEqual(doc.subtotal, 71000)
		self.assertEqual(doc.levy_amount, 7100)
		self.assertEqual(doc.order_total, 78100)

	# once it is charged, it stays charged --------------------------------

	def test_a_paid_bill_keeps_the_levy_it_was_charged(self):
		o = self.order()
		pos.pay_order(o, "Cash")
		self.make_outlet(levy_percent=0)          # the owner turns the levy off later
		doc = self.doc(o)
		doc.save()
		self.assertEqual(doc.levy_amount, 5900)
		self.assertEqual(doc.order_total, 64900)

	def test_a_new_bill_after_the_change_uses_the_new_levy(self):
		first = self.order()
		self.make_outlet(levy_percent=5)
		second = self.order()
		self.assertEqual(self.doc(first).levy_amount, 5900)
		self.assertEqual(self.doc(second).levy_amount, 2950)

	# charged to a room -----------------------------------------------------

	def test_a_room_charge_posts_the_levy_as_its_own_line(self):
		rt = make_room_type(PROP_A, "STD", base_price=1000)
		room = make_room(PROP_A, rt, "101")
		make_reservation(PROP_A, rt, d(-1), d(1), status="Checked In", room=room)
		o = pos.create_order(
			self.outlet, [{"menu_item": self.food, "qty": 1},
			              {"menu_item": self.drink, "qty": 2}],
			room=room, order_type="Room Service")["order"]
		pos.deliver_order(o)
		lines = frappe.get_all(
			"Folio Charge", filters={"description": ["like", f"%({o})"]},
			fields=["description", "amount", "gst_rate", "charge_type"],
			order_by="idx")
		self.assertEqual(len(lines), 2, lines)
		items, levy = lines
		self.assertEqual(items.amount, 59000)
		self.assertEqual(levy.amount, 5900)
		self.assertIn("Service charge 10%", levy.description)
		self.assertEqual(levy.charge_type, "Food & Beverage")
		self.assertEqual(levy.gst_rate, 5)              # the levy is taxed here
		self.assertEqual(items.amount + levy.amount, self.doc(o).order_total)

	def test_an_untaxed_levy_posts_with_no_tax(self):
		self.make_outlet(levy_percent=10, levy_taxable=0)
		rt = make_room_type(PROP_A, "STD", base_price=1000)
		room = make_room(PROP_A, rt, "101")
		make_reservation(PROP_A, rt, d(-1), d(1), status="Checked In", room=room)
		o = pos.create_order(self.outlet, [{"menu_item": self.food, "qty": 1}],
		                     room=room, order_type="Room Service")["order"]
		pos.deliver_order(o)
		levy = frappe.get_all("Folio Charge", filters={
			"description": ["like", f"%Service charge 10%({o})"]},
			fields=["amount", "gst_rate"])
		self.assertEqual([(r.amount, r.gst_rate) for r in levy], [(3500, 0)])

	def test_a_moved_room_bill_takes_both_lines(self):
		rt = make_room_type(PROP_A, "STD", base_price=1000)
		wrong, right = make_room(PROP_A, rt, "101"), make_room(PROP_A, rt, "102")
		src = make_reservation(PROP_A, rt, d(-1), d(1), status="Checked In", room=wrong)
		dst = make_reservation(PROP_A, rt, d(-1), d(1), status="Checked In", room=right)
		o = pos.create_order(self.outlet, [{"menu_item": self.food, "qty": 1}],
		                     room=wrong, order_type="Room Service")["order"]
		pos.deliver_order(o)
		pos.move_room_bill(o, right, "Guest gave room 101 by mistake")
		on = lambda res: frappe.get_all("Folio Charge", filters={
			"parent": guest_folio(res.name), "description": ["like", f"%({o})"]})
		self.assertEqual(len(on(src)), 0)
		self.assertEqual(len(on(dst)), 2)

	# where it is not allowed ---------------------------------------------------

	def test_the_levy_must_be_between_zero_and_a_hundred(self):
		for bad in (-1, 101):
			doc = frappe.get_doc("POS Outlet", self.outlet)
			doc.levy_percent = bad
			with self.assertRaisesRegex(frappe.ValidationError, "between 0 and 100"):
				doc.save()

	def test_a_country_that_e_invoices_every_bill_cannot_set_a_levy(self):
		class EInvoicePack:
			def on_pos_bill_paid(self, doc):
				pass
		with patch("kamra.localization.pack_for", return_value=EInvoicePack()):
			doc = frappe.get_doc("POS Outlet", self.outlet)
			doc.levy_percent = 10
			with self.assertRaisesRegex(frappe.ValidationError, "e-invoicing"):
				doc.save()
			doc = frappe.get_doc("POS Outlet", self.outlet)   # a refused save leaves the copy stale
			doc.levy_percent = 0                      # no levy is always fine
			doc.save()
