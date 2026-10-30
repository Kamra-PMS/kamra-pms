"""Waiter and cashier on the restaurant bill, and the kitchen's Start and
Picked up times (SI list #411).

- served_by is the waiter typed on the bill, else the captain's full name;
  cashier is whoever closed the bill. Names, never emails.
- Start (accept_ticket) stamps started_at on every fired line not started
  yet, a later round included; auto KOT starts lines at fire.
- Picked up stamps picked_up_at on prepared lines; recall clears it.
  kot_status keeps New | Fired | Prepared, so nothing that reads it moves.
"""

from __future__ import annotations

import frappe

from kamra import custom_reports, pos
from kamra.tests.audit_fixtures import (
	PROP_A,
	TODAY,
	AuditTestCase,
	ensure_user,
	make_property,
)


class PosStaffKotTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		make_property(PROP_A, business_date=TODAY)
		name = frappe.db.get_value("POS Outlet", {"property": PROP_A,
		                                          "outlet_name": "UT KOT Cafe"})
		if not name:
			name = frappe.get_doc({
				"doctype": "POS Outlet", "property": PROP_A,
				"outlet_name": "UT KOT Cafe", "outlet_type": "Restaurant",
				"gst_rate": 5}).insert(ignore_permissions=True).name
		frappe.db.set_value("POS Outlet", name, "kot_mode", "Kitchen presses Start")
		self.outlet = name
		self.dosa = frappe.get_doc({
			"doctype": "Menu Item", "property": PROP_A, "outlet": name,
			"item_name": "UT KOT Dosa", "category": "Food", "price": 200,
			"is_veg": 1, "available": 1, "prep_station": "Kitchen",
		}).insert(ignore_permissions=True).name

	def send(self, **kw):
		return pos.send_order(self.outlet, [{"menu_item": self.dosa, "qty": 1}],
		                      property=PROP_A, table_no="T1", **kw)

	def lines(self, order):
		return pos.order_detail(order)["items"]

	def test_waiter_and_cashier_names_reach_the_bill_and_lists(self):
		captain = ensure_user("ut.kot.captain@example.com", ["Front Desk"])
		o = self.send(waiter="  Ravi  ")
		self.assertEqual(frappe.db.get_value("POS Order", o["order"], "waiter"), "Ravi")
		bill = pos.bill_data(o["order"])
		self.assertEqual(bill["served_by"], "Ravi")
		self.assertIsNone(bill["cashier"])

		# no waiter typed: the captain's display name, never the email
		pos.set_waiter(o["order"], "")
		frappe.db.set_value("POS Order", o["order"], "captain", captain)
		served = pos.bill_data(o["order"])["served_by"]
		self.assertEqual(served, frappe.utils.get_fullname(captain))
		self.assertNotIn("@", served)

		pos.set_waiter(o["order"], "Meena")
		frappe.set_user(captain)
		try:
			from kamra import cashier
			cashier.open_session(PROP_A, 0)
			pos.pay_order(o["order"], "Cash")
		finally:
			frappe.set_user("Administrator")
		name = frappe.utils.get_fullname(captain)
		self.assertEqual(frappe.db.get_value("POS Order", o["order"], "settled_by"), captain)
		bill = pos.bill_data(o["order"])
		self.assertEqual((bill["served_by"], bill["cashier"]), ("Meena", name))
		d = pos.order_detail(o["order"])
		self.assertEqual((d["served_by"], d["cashier"]), ("Meena", name))
		row = next(r for r in pos.orders_list(self.outlet)["rows"] if r["name"] == o["order"])
		self.assertEqual((row["served_by"], row["cashier"]), ("Meena", name))
		# the cashier is stamped once, on the close: a later change keeps it,
		# and a value sent by a client is put back
		doc = frappe.get_doc("POS Order", o["order"])
		doc.notes = "later edit"
		doc.settled_by = "Administrator"
		doc.save(ignore_permissions=True)
		self.assertEqual(frappe.db.get_value("POS Order", o["order"], "settled_by"), captain)
		# a closed bill keeps its waiter
		with self.assertRaisesRegex(frappe.ValidationError, "closed"):
			pos.set_waiter(o["order"], "Someone else")

	def test_no_cashier_for_administrator(self):
		o = self.send()
		pos.pay_order(o["order"], "Cash")
		self.assertIsNone(frappe.db.get_value("POS Order", o["order"], "settled_by"))

	def test_only_a_cooking_line_is_marked_ready(self):
		o = pos.create_order(self.outlet, [{"menu_item": self.dosa, "qty": 1}],
		                     property=PROP_A, table_no="T1")
		row = self.lines(o["order"])[0]["row"]
		with self.assertRaisesRegex(frappe.ValidationError, "cooking"):
			pos.mark_prepared(o["order"], row)  # still on the till
		self.assertFalse(self.lines(o["order"])[0]["prepared_at"])

	def test_start_and_pickup_times_and_turnaround_report(self):
		o = self.send()
		# manual outlet: fired, not started
		line = self.lines(o["order"])[0]
		self.assertTrue(line["fired_at"])
		self.assertFalse(line["started_at"])
		tick = next(t for t in pos.kitchen_queue(PROP_A, outlet=self.outlet)
		            if t["name"] == o["order"])
		self.assertIn("started_at", tick["items"][0])

		self.assertEqual(pos.accept_ticket(o["order"])["started"], 1)
		self.assertTrue(self.lines(o["order"])[0]["started_at"])

		# a second round on an accepted ticket waits for its own Start
		pos.send_round(o["order"], [{"menu_item": self.dosa, "qty": 2}])
		second = self.lines(o["order"])[1]
		self.assertFalse(second["started_at"])
		self.assertEqual(pos.accept_ticket(o["order"])["started"], 1)
		self.assertTrue(self.lines(o["order"])[1]["started_at"])

		# nothing at the pass yet
		with self.assertRaisesRegex(frappe.ValidationError, "Nothing is waiting"):
			pos.mark_picked_up(o["order"])
		pos.mark_prepared(o["order"])
		first_row = self.lines(o["order"])[0]["row"]
		self.assertEqual(pos.mark_picked_up(o["order"], first_row)["picked_up"], 1)
		self.assertEqual(pos.mark_picked_up(o["order"])["picked_up"], 1)
		for it in self.lines(o["order"]):
			self.assertEqual(it["kot_status"], "Prepared")  # status set untouched
			self.assertTrue(it["picked_up_at"])

		# a recall sends it back: plated and picked up are undone
		pos.recall_prepared(o["order"], first_row)
		it = self.lines(o["order"])[0]
		self.assertFalse(it["prepared_at"])
		self.assertFalse(it["picked_up_at"])

		rows = custom_reports._fetch_kitchen_times(
			PROP_A, frappe.utils.nowdate(), frappe.utils.nowdate())
		mine = [r for r in rows if r["order"] == o["order"]]
		self.assertEqual(len(mine), 2)
		done = next(r for r in mine if r["picked_up_at"])
		for k in ("wait_minutes", "cook_minutes", "pass_minutes", "total_minutes"):
			self.assertIsNotNone(done[k], k)
			self.assertGreaterEqual(done[k], 0)
		recalled = next(r for r in mine if not r["picked_up_at"])
		self.assertIsNone(recalled["pass_minutes"])

	def test_auto_kot_starts_lines_at_fire(self):
		frappe.db.set_value("POS Outlet", self.outlet, "kot_mode", "Auto-accept and print")
		o = self.send()
		line = self.lines(o["order"])[0]
		self.assertEqual(str(line["started_at"]), str(line["fired_at"]))
		self.assertEqual(pos.accept_ticket(o["order"])["started"], 0)

	def test_a_waiter_name_cannot_send_printer_commands(self):
		from kamra.printing import escpos
		out = escpos({"kind": "Bill", "served_by": "Ravi\x1bp\x00\x19\xfa", "items": []})
		self.assertIn(b"Served by: Ravip?", out)
		self.assertNotIn(b"\x1bp\x00", out)

	def test_outlet_waiter_list_comes_first_and_only_managers_edit_it(self):
		self.send(waiter="Typed Tom")
		r = pos.save_outlet_waiter(self.outlet, " Asha ")
		self.assertTrue(r["can_edit"])
		pos.save_outlet_waiter(self.outlet, "Bilal")
		pos.save_outlet_waiter(self.outlet, "asha")  # same name: never doubled
		self.assertEqual(pos.waiters(self.outlet)[:3], ["Asha", "Bilal", "Typed Tom"])

		pos.save_outlet_waiter(self.outlet, "Bilal", active=0)
		self.assertNotIn("Bilal", pos.waiters(self.outlet))
		listed = pos.outlet_waiters(self.outlet)["waiters"]
		self.assertEqual([(w["waiter_name"], w["active"]) for w in listed],
		                 [("Asha", 1), ("Bilal", 0)])

		# the till lists it; only Finance or an admin changes it
		desk = ensure_user("ut.kot.desk@example.com", ["Front Desk"])
		frappe.set_user(desk)
		try:
			self.assertFalse(pos.outlet_waiters(self.outlet)["can_edit"])
			self.assertIn("Asha", pos.waiters(self.outlet))
			with self.assertRaises(frappe.PermissionError):
				pos.save_outlet_waiter(self.outlet, "Sneaky")
		finally:
			frappe.set_user("Administrator")
