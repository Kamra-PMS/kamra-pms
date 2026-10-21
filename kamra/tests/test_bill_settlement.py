"""Two money gaps closed together.

1. A credit company with no billing rules got nothing billed after the
   check-out fix (#215): only the Company folio moves to the city ledger,
   and only billing rules put charges there. The property's
   `default_company_billing` now decides what such a company pays. Its own
   rules always win, and liquor never bills to a company.
2. An unpaid dine-in or takeaway bill could be marked Delivered (closed).
   A POS bill closes only paid, posted to a checked-in room, or NC with an
   authorization. The kitchen marking food served does not settle it.
"""

from __future__ import annotations

import frappe

from kamra import api, pos
from kamra import folio as folio_mod
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

DEFAULT = "Room and F&B (liquor to guest)"
NOTHING = "Nothing (guest pays unless rules say so)"


def _folio_type_of(reservation: str, description: str) -> str:
	rows = frappe.db.sql(
		"""SELECT f.folio_type FROM `tabFolio Charge` fc
		   JOIN `tabFolio` f ON fc.parent = f.name
		   WHERE f.reservation = %s AND fc.description = %s""",
		(reservation, description), pluck=True)
	assert len(rows) == 1, (description, rows)
	return rows[0]


def _room_folio_types(reservation: str) -> list:
	return frappe.db.sql(
		"""SELECT f.folio_type FROM `tabFolio Charge` fc
		   JOIN `tabFolio` f ON fc.parent = f.name
		   WHERE f.reservation = %s AND fc.charge_type = 'Room'""",
		reservation, pluck=True)


def _corp(name: str, credit: int = 1, rules=()) -> str:
	if frappe.db.exists("Corporate Account", name):
		doc = frappe.get_doc("Corporate Account", name)
	else:
		doc = frappe.get_doc({"doctype": "Corporate Account", "company_name": name})
	doc.credit_allowed = credit
	doc.set("billing_rules", [{"charge_type": t, "pay_by": "Company"} for t in rules])
	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)
	return doc.name


class CompanyDefaultBillingTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")

	def stay(self, company: str):
		return make_reservation(PROP_A, self.rt, d(-1), TODAY,
		                        status="Checked In", room=self.room,
		                        booking_type="Corporate", company=company)

	def post(self, res, charge_type, desc, amount, alcohol=0):
		api.post_stay_charge(res.name, charge_type, desc, amount, is_alcohol=alcohol)
		return _folio_type_of(res.name, desc)

	def test_no_rules_credit_company_pays_room_and_food_not_liquor_or_laundry(self):
		res = self.stay(_corp("UT Default Corp"))
		folio_mod.post_remaining_nights(res)
		self.assertEqual(_room_folio_types(res.name), ["Company"])
		self.assertEqual(self.post(res, "Food & Beverage", "UT lunch", 500), "Company")
		self.assertEqual(self.post(res, "Food & Beverage", "UT whisky", 800, 1), "Guest")
		self.assertEqual(self.post(res, "Laundry", "UT laundry", 300), "Guest")
		self.assertEqual(self.post(res, "Minibar", "UT minibar", 200), "Guest")
		self.assertEqual(self.post(res, "Misc", "UT paid-out", 100), "Guest")
		shown = api.company_billing_default("UT Default Corp", PROP_A)
		self.assertTrue(shown["applies"])
		self.assertEqual(shown["default"], DEFAULT)
		self.assertIn("Food & Beverage", shown["charge_types"])

	def test_explicit_rules_override_the_default(self):
		make_property(PROP_A, default_company_billing="Everything except liquor")
		res = self.stay(_corp("UT Rules Corp", rules=("Laundry",)))
		folio_mod.post_remaining_nights(res)
		self.assertEqual(_room_folio_types(res.name), ["Guest"])
		self.assertEqual(self.post(res, "Food & Beverage", "UT lunch", 500), "Guest")
		self.assertEqual(self.post(res, "Laundry", "UT laundry", 300), "Company")
		self.assertFalse(api.company_billing_default("UT Rules Corp", PROP_A)["applies"])

	def test_room_only_and_everything_except_liquor(self):
		make_property(PROP_A, default_company_billing="Room only")
		res = self.stay(_corp("UT Room Only Corp"))
		folio_mod.post_remaining_nights(res)
		self.assertEqual(_room_folio_types(res.name), ["Company"])
		self.assertEqual(self.post(res, "Food & Beverage", "UT lunch", 500), "Guest")
		make_property(PROP_A, default_company_billing="Everything except liquor")
		self.assertEqual(self.post(res, "Laundry", "UT laundry", 300), "Company")
		self.assertEqual(self.post(res, "Minibar", "UT beer", 300, 1), "Guest")

	def test_nothing_reproduces_strict_routing(self):
		make_property(PROP_A, default_company_billing=NOTHING)
		res = self.stay(_corp("UT Strict Corp"))
		folio_mod.post_remaining_nights(res)
		self.assertEqual(_room_folio_types(res.name), ["Guest"])
		self.assertEqual(self.post(res, "Food & Beverage", "UT lunch", 500), "Guest")
		self.assertFalse(frappe.db.get_value(
			"Folio", {"reservation": res.name, "folio_type": "Company"}))

	def test_company_without_credit_gets_no_default(self):
		res = self.stay(_corp("UT Cash Corp", credit=0))
		folio_mod.post_remaining_nights(res)
		self.assertEqual(_room_folio_types(res.name), ["Guest"])
		self.assertTrue(guest_folio(res.name))


class BillSettlementTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")
		self.outlet = frappe.db.get_value(
			"POS Outlet", {"property": PROP_A, "outlet_name": "UT Settle Cafe"})
		if not self.outlet:
			self.outlet = frappe.get_doc({
				"doctype": "POS Outlet", "property": PROP_A,
				"outlet_name": "UT Settle Cafe", "outlet_type": "Restaurant",
				"gst_rate": 5}).insert(ignore_permissions=True).name
		self.dish = frappe.db.get_value(
			"Menu Item", {"outlet": self.outlet, "item_name": "UT Thali"})
		if not self.dish:
			self.dish = frappe.get_doc({
				"doctype": "Menu Item", "property": PROP_A, "outlet": self.outlet,
				"item_name": "UT Thali", "category": "Food", "price": 300,
				"is_veg": 1, "available": 1, "prep_station": "Kitchen",
			}).insert(ignore_permissions=True).name

	def order(self, order_type="Dine In", **kw):
		return pos.create_order(self.outlet, [{"menu_item": self.dish, "qty": 1}],
		                        order_type=order_type, **kw)["order"]

	def status(self, order):
		return frappe.db.get_value("POS Order", order, "status")

	def test_unpaid_dine_in_cannot_close(self):
		o = self.order(table_no="T1")
		with self.assertRaisesRegex(frappe.ValidationError, "not settled"):
			pos.deliver_order(o)
		self.assertNotEqual(self.status(o), "Delivered")

	def test_unpaid_takeaway_cannot_close_on_a_direct_save(self):
		o = self.order("Takeaway")
		doc = frappe.get_doc("POS Order", o)
		doc.status = "Delivered"
		with self.assertRaisesRegex(frappe.ValidationError, "not settled"):
			doc.save()

	def test_serving_does_not_settle_the_bill(self):
		o = self.order(table_no="T2")
		pos.fire_kot(o)
		self.assertTrue(pos.mark_prepared(o)["all_prepared"])
		self.assertEqual(self.status(o), "Preparing")
		with self.assertRaisesRegex(frappe.ValidationError, "not settled"):
			pos.deliver_order(o)

	def test_paid_bill_closes(self):
		o = self.order(table_no="T3")
		self.assertTrue(pos.pay_order(o, "Cash")["paid"])
		self.assertEqual(self.status(o), "Delivered")

	def test_wrong_payment_mode_can_be_corrected_while_the_till_is_open(self):
		from kamra import cashier
		cashier.open_session(PROP_A, 0)
		o = self.order(table_no="T3b")
		pos.pay_order(o, "Card")
		out = pos.change_payment_mode(o, "Cash", "pressed Card by mistake")
		self.assertEqual(out["was"], "Card")
		self.assertEqual(frappe.db.get_value("POS Order", o, "payment_mode"), "Cash")
		by_mode = {m: a for m, a in frappe.db.sql(
			"""SELECT mode, SUM(amount) FROM `tabCashier Transaction`
			   WHERE pos_order = %s AND kind = 'Payment' GROUP BY mode""", o)}
		self.assertEqual(float(by_mode.get("Card") or 0), 0.0)
		self.assertGreater(float(by_mode.get("Cash") or 0), 0)
		with self.assertRaisesRegex(frappe.ValidationError, "already marked"):
			pos.change_payment_mode(o, "Cash")

	def test_order_history_exports_with_payment_mode(self):
		import csv
		import io

		from frappe.utils import nowdate
		o = self.order(table_no="T3d")
		pos.pay_order(o, "UPI")
		out = pos.orders_export(self.outlet, nowdate())
		rows = list(csv.DictReader(io.StringIO(out["csv"].lstrip("\ufeff"))))
		mine = [r for r in rows if r["Bill"] == o]
		self.assertEqual(len(mine), 1)
		self.assertEqual((mine[0]["Payment mode"], mine[0]["State"]), ("UPI", "paid"))
		only_cash = pos.orders_export(self.outlet, nowdate(), mode="Cash")
		self.assertNotIn(o, only_cash["csv"])

	def test_order_history_reaches_back_a_year_and_filters(self):
		from frappe.utils import add_days, nowdate
		a = self.order(table_no="H1")
		pos.pay_order(a, "UPI")
		b = self.order("Takeaway")
		pos.pay_order(b, "Cash")
		old = self.order(table_no="H3")
		pos.pay_order(old, "Cash")
		frappe.db.set_value("POS Order", old, "creation", f"{add_days(nowdate(), -90)} 12:00:00")
		wide = pos.orders_list(self.outlet, add_days(nowdate(), -120), nowdate())
		names = {r["name"] for r in wide["rows"]}
		self.assertTrue({a, b, old} <= names, "a 90 day old bill must be reachable")
		# today alone does not include it
		self.assertNotIn(old, {r["name"] for r in pos.orders_list(self.outlet, nowdate())["rows"]})
		# one kind of order, one way of paying
		self.assertEqual({r["order_type"] for r in pos.orders_list(
			self.outlet, add_days(nowdate(), -120), nowdate(), order_type="Takeaway")["rows"]}, {"Takeaway"})
		cash = pos.orders_list(self.outlet, add_days(nowdate(), -120), nowdate(), mode="Cash")
		self.assertTrue({b, old} <= {r["name"] for r in cash["rows"]})
		self.assertNotIn(a, {r["name"] for r in cash["rows"]})
		self.assertEqual(set(cash["totals"]["by_mode"]), {"Cash"})
		# a year is the most that can be asked for
		with self.assertRaisesRegex(frappe.ValidationError, "one year"):
			pos.orders_list(self.outlet, add_days(nowdate(), -400), nowdate())

	def test_order_history_pages_without_changing_the_totals(self):
		from frappe.utils import nowdate
		for i in range(3):
			pos.pay_order(self.order(table_no=f"P{i}"), "Card")
		full = pos.orders_list(self.outlet, nowdate(), mode="Card")
		first = pos.orders_list(self.outlet, nowdate(), mode="Card", limit=2)
		rest = pos.orders_list(self.outlet, nowdate(), mode="Card", limit=2, offset=2)
		self.assertEqual(len(first["rows"]), 2)
		self.assertTrue(first["has_more"])
		self.assertEqual(first["total"], full["total"])
		self.assertEqual(first["totals"], full["totals"])
		self.assertEqual(len(first["rows"]) + len(rest["rows"]), full["total"])
		self.assertFalse(set(r["name"] for r in first["rows"]) & set(r["name"] for r in rest["rows"]))
		self.assertAlmostEqual(first["totals"]["sales"],
		                       sum(r["amount"] for r in full["rows"] if r["state"] == "paid"), 2)

	def test_payment_mode_stays_once_the_till_is_closed(self):
		from kamra import cashier
		cashier.open_session(PROP_A, 0)
		o = self.order(table_no="T3c")
		pos.pay_order(o, "Card")
		sess = frappe.db.get_value("Cashier Transaction", {"pos_order": o}, "session")
		frappe.db.set_value("Cashier Session", sess, "status", "Closed")
		with self.assertRaisesRegex(frappe.ValidationError, "closed"):
			pos.change_payment_mode(o, "Cash")

	def test_paid_flag_without_a_payment_mode_is_refused(self):
		doc = frappe.get_doc("POS Order", self.order("Takeaway"))
		doc.paid, doc.status = 1, "Delivered"
		with self.assertRaisesRegex(frappe.ValidationError, "payment mode"):
			doc.save()

	def test_nc_closes_only_with_an_authorization(self):
		o = self.order(table_no="T4")
		frappe.db.set_value("POS Order", o, "nc", 1)
		with self.assertRaisesRegex(frappe.ValidationError, "authorized"):
			pos.deliver_order(o)
		frappe.db.set_value("POS Order", o, "nc", 0)
		pos.mark_nc(o, "GM", "birthday")
		self.assertEqual(pos.deliver_order(o)["status"], "Delivered")

	def test_room_posting_closes_the_bill(self):
		res = make_reservation(PROP_A, self.rt, d(-1), TODAY,
		                       status="Checked In", room=self.room)
		o = self.order(table_no="T5")
		pos.charge_to_room(o, self.room)
		self.assertTrue(pos.deliver_order(o)["posted_to_folio"])
		self.assertTrue(frappe.get_all("Folio Charge", filters={
			"parent": guest_folio(res.name), "description": ["like", f"%{o}%"]}))

	def test_fully_voided_bill_closes(self):
		o = self.order(table_no="T6")
		row = frappe.get_doc("POS Order", o).items[0].name
		pos.void_item(o, row, "walked out before cooking")
		self.assertEqual(pos.deliver_order(o)["status"], "Delivered")
