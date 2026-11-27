"""Refunds of bills paid at the outlet."""

from __future__ import annotations

import re
from unittest.mock import patch

import frappe

from kamra import cashier, inventory, pos, pos_refunds, settings
from kamra.tests.audit_fixtures import (
	PROP_A, PROP_B, TODAY, AuditTestCase, make_property)
from kamra.tests.test_rbac import _user

SUPERVISOR, PIN = "ut-refund-sup@example.com", "2468"


class RefundCase(AuditTestCase):
	"""A counter selling two lattes and a water with service 10% and tax 10%
	(the design's bill: 72,600 paid)."""

	def setUp(self):
		super().setUp()
		make_property(PROP_A, business_date=TODAY)
		frappe.cache().hdel(settings.CACHE_KEY, PROP_A)
		self.addCleanup(frappe.cache().hdel, settings.CACHE_KEY, PROP_A)
		self.addCleanup(frappe.set_user, "Administrator")
		self.outlet = frappe.get_doc({
			"doctype": "POS Outlet", "property": PROP_A, "outlet_name": "UT Counter",
			"outlet_type": "Restaurant", "gst_rate": 10, "levy_label": "Service",
			"levy_percent": 10, "levy_taxable": 1}).insert(ignore_permissions=True).name
		self.latte = self.dish("UT Latte", 25000)
		self.water = self.dish("UT Water", 10000)

	def dish(self, name, price, **extra):
		return frappe.get_doc({
			"doctype": "Menu Item", "property": PROP_A, "outlet": self.outlet,
			"item_name": name, "price": price, **extra}).insert(ignore_permissions=True).name

	def tills(self, on: int):
		settings.save_settings(PROP_A, "finance", {"use_cashier_tills": on})

	def open_till(self, user="Administrator"):
		frappe.set_user(user)  # nosemgrep: frappe-setuser -- test opens a till as this user
		try:
			return cashier.open_session(PROP_A, opening_float=0)["name"]
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- back to the test user

	def bill(self, *items, **extra):
		return pos.create_order(
			self.outlet,
			[{"menu_item": m, "qty": q} for m, q in items or ((self.latte, 2), (self.water, 1))],
			table_no="T1", **extra)["order"]

	def paid_bill(self, mode="Cash", *items):
		order = self.bill(*items)
		pos.pay_order(order, mode)
		return order

	def field(self, order, name):
		return frappe.db.get_value("POS Order", order, name)


class TestPaymentFields(RefundCase):
	def test_paying_records_what_was_paid(self):
		order = self.paid_bill()
		self.assertEqual(
			(self.field(order, "paid_amount"), self.field(order, "paid_tax")), (72600, 6600))

	def test_a_save_cannot_mark_a_bill_paid(self):
		order = self.bill()
		doc = frappe.get_doc("POS Order", order)
		doc.update({"status": "Delivered", "paid": 1, "payment_mode": "Cash"})
		with self.assertRaisesRegex(frappe.ValidationError, "set by the till"):
			doc.save()

	def test_a_save_cannot_change_what_was_paid_or_refunded(self):
		order = self.paid_bill()
		for field, value in (("paid_amount", 999999), ("paid_tax", 0), ("refunded_amount", 1),
		                     ("payment_mode", "Card"), ("paid", 0)):
			doc = frappe.get_doc("POS Order", order)
			doc.set(field, value)
			with self.subTest(field=field), \
					self.assertRaisesRegex(frappe.ValidationError, "set by the till"):
				doc.save()

	def test_a_new_bill_cannot_arrive_paid(self):
		with self.assertRaisesRegex(frappe.ValidationError, "set by the till"):
			frappe.get_doc({
				"doctype": "POS Order", "property": PROP_A, "outlet": self.outlet,
				"status": "Placed", "paid": 1, "payment_mode": "Cash",
				"items": [{"menu_item": self.water, "item_name": "UT Water", "qty": 1, "rate": 10000}],
			}).insert()

	def test_other_edits_still_save(self):
		order = self.paid_bill()
		doc = frappe.get_doc("POS Order", order)
		doc.notes = "kept"
		doc.save()
		self.assertEqual(self.field(order, "notes"), "kept")

	def test_a_refund_record_cannot_be_written_by_hand(self):
		order = self.paid_bill()
		with self.assertRaisesRegex(frappe.ValidationError, "Refunds are made at the till"):
			frappe.get_doc({
				"doctype": "POS Refund", "property": PROP_A, "outlet": self.outlet,
				"pos_order": order, "amount": 100, "mode": "Cash",
				"idempotency_key": "by-hand"}).insert()

	def test_the_payment_mode_cannot_change_after_a_refund(self):
		order = self.paid_bill()
		refund = frappe.get_doc({
			"doctype": "POS Refund", "property": PROP_A, "outlet": self.outlet,
			"pos_order": order, "amount": 100, "mode": "Cash", "idempotency_key": "k1"})
		refund.flags.from_pos_refund = True
		refund.insert(ignore_permissions=True)
		with self.assertRaisesRegex(frappe.ValidationError, "has a refund"):
			pos.change_payment_mode(order, "Card")

	def test_a_new_refund_right_for_supervisors(self):
		from kamra.authz import perm_roles
		self.assertEqual(
			sorted(perm_roles("POS Order", "approve_refunds") - {"Administrator"}),
			["F&B Manager", "Finance", "Hotel Admin", "System Manager"])

	def test_the_pos_refund_reasons_exist(self):
		from kamra.ledger import ensure_default_reason_codes
		ensure_default_reason_codes()
		codes = frappe.get_all(
			"Reason Code", filters={"category": "POS Refund"}, pluck="name", order_by="name")
		self.assertEqual(codes, [
			"POS-REF-COMPL", "POS-REF-OTHER", "POS-REF-QUAL", "POS-REF-STAFF", "POS-REF-WRONG"])


class TestThePatch(RefundCase):
	def run_patch(self):
		from kamra.patches.v48.fill_paid_amounts import execute
		execute()

	def forget(self, order):
		frappe.db.set_value("POS Order", order, {"paid_amount": 0, "paid_tax": 0})

	def test_it_reads_the_till_rows(self):
		self.open_till()
		order = self.paid_bill()
		pos.change_payment_mode(order, "Card")
		self.forget(order)
		self.run_patch()
		self.assertEqual(
			(self.field(order, "paid_amount"), self.field(order, "paid_tax")), (72600, 6600))

	def test_without_a_record_it_needs_a_property_without_tills(self):
		order = self.paid_bill()
		self.forget(order)
		self.run_patch()
		self.assertEqual(self.field(order, "paid_amount"), 0)
		self.tills(0)
		self.run_patch()
		self.assertEqual(
			(self.field(order, "paid_amount"), self.field(order, "paid_tax")), (72600, 6600))


class Refunding(RefundCase):
	"""Refunds by a cashier (here Administrator) with a supervisor's PIN, on a
	property without tills unless the test turns them on."""

	def setUp(self):
		super().setUp()
		self.tills(0)
		_user(SUPERVISOR, "Hotel Admin")
		self.pin(SUPERVISOR, PIN)

	def pin(self, user, pin):
		frappe.db.delete("Cashier PIN", {"name": user})
		frappe.get_doc({"doctype": "Cashier PIN", "user": user, "pin": pin}).insert(
			ignore_permissions=True)
		frappe.cache.delete_value(f"kamra_supervisor_pin_fails:{user}")

	def row(self, order, dish):
		return next(i.name for i in frappe.get_doc("POS Order", order).items if i.menu_item == dish)

	def pick(self, order, dish, qty=1, back=0):
		return {"row": self.row(order, dish), "qty": qty, "back_to_stock": back}

	def refund(self, order, kind="whole", mode="Cash", reason="POS-REF-WRONG", **kw):
		kw.setdefault("supervisor", SUPERVISOR)
		kw.setdefault("supervisor_pin", PIN)
		kw.setdefault("idempotency_key", frappe.generate_hash(length=16))
		return pos_refunds.refund_bill(order, kind, mode, reason, **kw)

	def items(self, order, *picks):
		return self.refund(order, "items", lines=list(picks))

	def refunds(self, order):
		return frappe.get_all(
			"POS Refund", filters={"pos_order": order},
			fields=["*"], order_by="creation asc, name asc")


class TestTheMoney(Refunding):
	def test_items_share_what_was_paid_and_the_last_takes_the_rest(self):
		order = self.paid_bill()
		self.assertEqual(self.items(order, self.pick(order, self.latte))["amount"], 30250)
		self.assertEqual(self.items(order, self.pick(order, self.water))["amount"], 12100)
		last = self.items(order, self.pick(order, self.latte))
		self.assertEqual((last["amount"], last["remaining"]), (30250, 0))
		self.assertEqual(self.field(order, "refunded_amount"), 72600)
		self.assertEqual(
			[(r.tax_amount, r.levy_amount) for r in self.refunds(order)],
			[(2750, 2500), (1100, 1000), (2750, 2500)])

	def test_a_discount_is_shared_too(self):
		order = self.bill()
		pos.apply_discount(order, 6000, "regular")
		pos.pay_order(order, "Cash")
		self.assertEqual(self.field(order, "paid_amount"), 65340)
		self.assertEqual(self.items(order, self.pick(order, self.latte))["amount"], 27225)

	def test_three_equal_shares_of_100000(self):
		got, refunded = [], 0
		for done in range(3):
			amount = pos_refunds.line_amounts(
				100000, round(100000 - refunded, 2), {"a": (100000, 3, done)}, [("a", 1)])[0]
			got.append(amount)
			refunded += amount
		self.assertEqual(got, [33333.33, 33333.33, 33333.34])

	def test_an_amount_then_the_whole_bill(self):
		order = self.paid_bill()
		self.assertEqual(self.refund(order, "amount", amount=10000)["amount"], 10000)
		self.assertEqual(self.refund(order)["amount"], 62600)
		self.assertEqual(sum(r.tax_amount for r in self.refunds(order)), 6600)
		self.assertEqual(sum(r.levy_amount for r in self.refunds(order)), 6000)

	def test_after_an_amount_an_item_gets_at_most_what_is_left(self):
		order = self.paid_bill()
		self.refund(order, "amount", amount=50000)
		self.assertEqual(self.items(order, self.pick(order, self.latte, 2))["amount"], 22600)
		with self.assertRaisesRegex(frappe.ValidationError, "Nothing is left"):
			self.items(order, self.pick(order, self.water))

	def test_never_more_than_was_paid(self):
		order = self.paid_bill()
		with self.assertRaisesRegex(frappe.ValidationError, "up to"):
			self.refund(order, "amount", amount=72600.01)
		with self.assertRaisesRegex(frappe.ValidationError, "above zero"):
			self.refund(order, "amount", amount=0)
		with self.assertRaisesRegex(frappe.ValidationError, "left to refund"):
			self.items(order, self.pick(order, self.latte, 3))
		self.refund(order)
		with self.assertRaisesRegex(frappe.ValidationError, "Nothing is left"):
			self.refund(order)

	def test_a_replayed_attempt_pays_once(self):
		self.tills(1)
		self.open_till()
		order = self.paid_bill()
		first = self.refund(order, "amount", amount=100, idempotency_key="same-click")
		again = self.refund(order, "amount", amount=100, idempotency_key="same-click")
		self.assertEqual(again["refund"], first["refund"])
		self.assertEqual(len(self.refunds(order)), 1)
		self.assertEqual(frappe.db.count(
			"Cashier Transaction", {"pos_order": order, "kind": "Refund"}), 1)

	def test_a_quote_that_went_stale_pays_nothing(self):
		order = self.paid_bill()
		latte = self.pick(order, self.latte)
		quoted = pos_refunds.refund_quote(order, "items", lines=[latte])["amount"]
		self.assertEqual(quoted, 30250)
		self.refund(order, "amount", amount=60000)  # another till, meanwhile
		with self.assertRaisesRegex(frappe.ValidationError, "changed"):
			self.refund(order, "items", lines=[latte], expected_amount=quoted)
		self.assertEqual(len(self.refunds(order)), 1)
		got = self.refund(order, "items", lines=[latte], expected_amount="12600")
		self.assertEqual(got["amount"], 12600)

	def test_a_repeated_attempt_for_another_amount_says_what_was_paid(self):
		order = self.paid_bill()
		ask = {"idempotency_key": "one-window", "amount": 100, "expected_amount": 100}
		first = self.refund(order, "amount", **ask)
		self.assertEqual(self.refund(order, "amount", **ask)["refund"], first["refund"])
		with self.assertRaisesRegex(frappe.ValidationError, "already refunded"):
			self.refund(order, "amount", **{**ask, "amount": 200, "expected_amount": 200})
		self.assertEqual(len(self.refunds(order)), 1)

	def test_a_window_that_has_seen_its_refund_is_not_answered_with_it_again(self):
		order = self.paid_bill()
		self.refund(order, "amount", amount=100)  # before this window opened
		ask = {"lines": [self.pick(order, self.latte)], "idempotency_key": "one-window",
		       "expected_amount": 30250}
		first = self.refund(order, "items", seen_refunded="100", **ask)
		# the answer got lost and the same press is sent again
		again = self.refund(order, "items", seen_refunded="100", **ask)
		self.assertEqual(again["refund"], first["refund"])
		# the window has read the bill again, shows that refund, and asks for the
		# other latte: the same figure must not come back as done
		with self.assertRaisesRegex(frappe.ValidationError, "already refunded"):
			self.refund(order, "items", seen_refunded=30350, **ask)
		self.assertEqual(len(self.refunds(order)), 2)

	def test_a_quote_matches_what_the_refund_gives(self):
		order = self.paid_bill()
		quote = pos_refunds.refund_quote(order, "items", lines=[self.pick(order, self.latte)])
		self.assertEqual(
			(quote["amount"], [(x["qty"], x["amount"]) for x in quote["lines"]]),
			(30250, [(1, 30250)]))


class TestWhoAndWhy(Refunding):
	def refused(self, order, words, **kw):
		with self.assertRaisesRegex((frappe.ValidationError, frappe.PermissionError), words):
			self.refund(order, **kw)
		self.assertEqual(self.refunds(order), [])

	def test_a_supervisors_pin_every_time(self):
		order = self.paid_bill()
		self.refused(order, "SUPERVISOR_REQUIRED", supervisor=None)
		self.refused(order, "SUPERVISOR_PIN_REQUIRED", supervisor_pin=None)
		self.refused(order, "Wrong|wrong", supervisor_pin="0000")
		desk = _user("ut-desk@example.com", "Front Desk")
		self.pin(desk, "1111")
		self.refused(order, "cannot approve", supervisor=desk, supervisor_pin="1111")

	def test_a_supervisor_refunding_still_types_their_pin(self):
		order = self.paid_bill()
		frappe.set_user(SUPERVISOR)  # nosemgrep: frappe-setuser -- test switches user
		self.refused(order, "SUPERVISOR_PIN_REQUIRED", supervisor_pin="")
		self.assertTrue(self.refund(order)["refund"])
		self.assertEqual(self.refunds(order)[0].approved_by, SUPERVISOR)
		self.assertEqual(self.refunds(order)[0].refunded_by, SUPERVISOR)

	def test_agents_never_refund(self):
		order = self.paid_bill()
		agent = _user("ut-agent@example.com", "Kamra Agent", "Hotel Admin")
		frappe.set_user(agent)  # nosemgrep: frappe-setuser -- test switches user
		self.refused(order, "AI agent")
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- back
		self.addCleanup(frappe.flags.pop, "kamra_agent_call", None)
		frappe.flags.kamra_agent_call = True
		self.refused(order, "AI agent")

	def test_a_reason_is_picked(self):
		order = self.paid_bill()
		self.refused(order, "Pick a refund reason", reason="REF-DEP")
		self.refused(order, "Pick a refund reason", reason="NOPE")
		self.refused(order, "in the note", reason="POS-REF-OTHER")
		self.refund(order, "amount", amount=1, reason="POS-REF-OTHER", note="split the cup")
		self.assertEqual(self.refunds(order)[0].note, "split the cup")

	def test_money_goes_back_the_ways_that_fit(self):
		cash = self.paid_bill("Cash")
		self.refused(cash, "Money goes back as", mode="Card")
		upi = self.paid_bill("UPI")
		self.assertEqual(pos_refunds.refund_options(upi)["modes"], ["UPI", "Cash", "Bank Transfer"])
		self.assertEqual(self.refund(upi, mode="Bank Transfer")["amount"], 72600)

	def test_only_bills_paid_at_the_till(self):
		open_bill = self.bill()
		self.refused(open_bill, "paid at the outlet")
		comped = self.bill()
		pos.mark_nc(comped, "Manager")
		pos.deliver_order(comped)
		self.refused(comped, "paid at the outlet")
		unrecorded = self.paid_bill()
		frappe.db.set_value("POS Order", unrecorded, "paid_amount", 0)
		self.refused(unrecorded, "no payment record")
		room_bill = self.paid_bill()
		frappe.db.set_value("POS Order", room_bill, {"paid": 0, "posted_to_folio": 1})
		self.refused(room_bill, "room's bill at the desk")
		self.assertEqual(
			pos_refunds.refund_options(room_bill)["why_not"],
			"Correct this on the room's bill at the desk.")


class TestTheTill(Refunding):
	def setUp(self):
		super().setUp()
		self.tills(1)

	def till_rows(self, order):
		return frappe.get_all(
			"Cashier Transaction", filters={"pos_order": order, "kind": "Refund"},
			fields=["session", "mode", "amount"])

	def test_only_your_own_open_till(self):
		self.open_till(SUPERVISOR)
		order = self.paid_bill()
		with self.assertRaisesRegex(frappe.ValidationError, "NO_OPEN_SESSION"):
			self.refund(order)
		mine = self.open_till()
		self.refund(order, "amount", amount=500)
		self.assertEqual(self.till_rows(order), [{"session": mine, "mode": "Cash", "amount": -500}])

	def test_a_closed_original_till_pays_from_the_open_one(self):
		first = self.open_till()
		order = self.paid_bill()
		frappe.db.set_value("Cashier Session", first, "status", "Closed")
		second = self.open_till()
		self.refund(order)
		self.assertEqual(self.till_rows(order)[0].session, second)

	def test_without_tills_the_record_is_the_money_record(self):
		self.tills(0)
		order = self.paid_bill()
		out = self.refund(order)
		self.assertEqual(self.till_rows(order), [])
		self.assertIsNone(frappe.db.get_value("POS Refund", out["refund"], "cashier_session"))

	def test_the_refund_is_logged_with_its_approver(self):
		self.open_till()
		order = self.paid_bill()
		self.refund(order)
		log = frappe.get_all(
			"Agent Action Log", filters={"action_type": "pos_refund", "reference_name": order},
			fields=["approver", "rationale", "action_channel"])
		self.assertEqual((log[0].approver, log[0].action_channel), (SUPERVISOR, "Desk"))
		self.assertIn("Wrong order", log[0].rationale)


class TestBackToStock(Refunding):
	def setUp(self):
		super().setUp()
		self.bottle = inventory.track_item_stock(self.water, uom="bottle")["ingredient"]
		inventory.receive_stock(PROP_A, self.outlet, [{"ingredient": self.bottle, "qty": 10}])

	def left(self):
		return frappe.db.get_value(
			"Ingredient Stock", f"{self.outlet}::{self.bottle}", "qty_on_hand")

	def test_the_bottle_returns_even_if_tracking_changed(self):
		order = self.paid_bill()
		self.assertEqual(self.left(), 9)
		inventory.untrack_item_stock(self.water)
		self.items(order, self.pick(order, self.water, 1, back=1))
		self.assertEqual(self.left(), 10)
		entry = frappe.get_all(
			"Ingredient Ledger Entry", filters={"reason": "Return", "ingredient": self.bottle},
			fields=["qty_change", "reference_doctype", "reference_name"])[0]
		self.assertEqual(
			(entry.qty_change, entry.reference_doctype, entry.reference_name),
			(1, "POS Refund", self.refunds(order)[0].name))
		line = frappe.get_all("POS Refund Line", filters={"parent": self.refunds(order)[0].name},
		                      fields=["back_to_stock", "stock_item"])[0]
		self.assertEqual((line.back_to_stock, line.stock_item), (1, self.bottle))
		with self.assertRaisesRegex(frappe.ValidationError, "left to refund"):
			self.items(order, self.pick(order, self.water, 1, back=1))

	def test_returns_take_stock_rows_in_the_one_lock_order(self):
		can = inventory.track_item_stock(self.latte, uom="can")["ingredient"]
		self.assertGreater(can, self.bottle, "the lines below are picked the other way round")
		order = self.paid_bill()
		moved, real = [], inventory._apply_move

		def note(prop, outlet, ingredient, *args, **kwargs):
			moved.append(ingredient)
			return real(prop, outlet, ingredient, *args, **kwargs)

		with patch.object(inventory, "_apply_move", side_effect=note):
			self.items(order, self.pick(order, self.latte, 1, back=1),
			           self.pick(order, self.water, 1, back=1))
		self.assertEqual(moved, [self.bottle, can])

	def test_not_ticked_stays_sold(self):
		order = self.paid_bill()
		self.items(order, self.pick(order, self.water))
		self.assertEqual(self.left(), 9)

	def test_a_recipe_dish_cannot_go_back(self):
		order = self.paid_bill()
		with self.assertRaisesRegex(frappe.ValidationError, "back to stock"):
			self.items(order, self.pick(order, self.latte, 1, back=1))
		options = pos_refunds.refund_options(order)
		self.assertEqual(
			{x["item_name"]: x["can_restock"] for x in options["lines"]},
			{"UT Latte": False, "UT Water": True})


class TestSaudiCreditNotes(Refunding):
	def setUp(self):
		super().setUp()
		make_property(PROP_B, business_date=TODAY, country="Saudi Arabia", currency="SAR")
		frappe.cache().hdel(settings.CACHE_KEY, PROP_B)
		self.addCleanup(frappe.cache().hdel, settings.CACHE_KEY, PROP_B)
		settings.save_settings(PROP_B, "finance", {"use_cashier_tills": 0})
		# Kamra refuses a levy while e-invoicing is on, so none here
		self.outlet = frappe.get_doc({
			"doctype": "POS Outlet", "property": PROP_B, "outlet_name": "UT Riyadh",
			"outlet_type": "Restaurant", "gst_rate": 15}).insert(ignore_permissions=True).name
		self.latte, self.water = (
			frappe.get_doc({"doctype": "Menu Item", "property": PROP_B, "outlet": self.outlet,
			                "item_name": n, "price": p}).insert(ignore_permissions=True).name
			for n, p in (("UT SA Latte", 25), ("UT SA Water", 10)))

	def documents(self, order):
		return frappe.get_all(
			"ZATCA Invoice", filters={"source_name": ["like", f"%"], "property": PROP_B},
			fields=["invoice_number", "document_type", "billing_reference", "tax_exclusive"],
			order_by="icv asc")

	def test_each_refund_gets_its_own_note_never_above_the_invoice(self):
		order = self.paid_bill()
		self.refund(order, "amount", amount=20)
		self.items(order, self.pick(order, self.latte))
		self.refund(order)
		docs = self.documents(order)
		self.assertEqual(
			[(d.invoice_number, d.document_type, d.billing_reference) for d in docs],
			[(order, "Invoice", None),
			 (f"{order}-R1", "Credit Note", order),
			 (f"{order}-R2", "Credit Note", order),
			 (f"{order}-R3", "Credit Note", order)])
		invoice, notes = docs[0].tax_exclusive, sum(d.tax_exclusive for d in docs[1:])
		self.assertLessEqual(round(notes, 2), round(invoice, 2))
		self.assertGreater(notes, invoice - 0.05)

	def test_a_small_bills_note_states_the_invoices_rate(self):
		# 6.50 of coffee carries 0.98 VAT, which is not 15.00% of 6.50
		coffee = frappe.get_doc({
			"doctype": "Menu Item", "property": PROP_B, "outlet": self.outlet,
			"item_name": "UT SA Coffee", "price": 6.5}).insert(ignore_permissions=True).name
		order = self.paid_bill("Cash", (coffee, 1))
		# the outlet's rate moves afterwards: the note keeps the invoice's
		frappe.db.set_value("POS Outlet", self.outlet, "gst_rate", 20)
		self.refund(order)
		docs = frappe.get_all(
			"ZATCA Invoice", filters={"property": PROP_B},
			fields=["document_type", "vat_total", "xml"], order_by="icv asc")
		self.assertEqual(
			[(d.document_type, d.vat_total, set(re.findall(r"<cbc:Percent>([^<]+)<", d.xml)))
			 for d in docs],
			[("Invoice", 0.98, {"15.00"}), ("Credit Note", 0.98, {"15.00"})])

	def test_a_bill_without_an_invoice_gets_no_credit_note(self):
		order = self.paid_bill()
		frappe.db.delete("ZATCA Invoice", {"source_name": order})  # paid before e-invoicing
		self.refund(order)
		self.assertEqual(self.documents(order), [])


class TestMessages(RefundCase):
	MESSAGES = (
		"Payment details are set by the till, not by editing the bill.",
		"Refunds are made at the till, and are never edited or deleted.",
		"This bill has a refund, so its payment mode can't change.",
		"Correct this on the room's bill at the desk.",
		"Only a bill paid at the outlet can be refunded.",
		"This bill has no payment record, so it can't be refunded here.",
		"Nothing is left to refund on this bill.",
		"The amount must be above zero.",
		"You can refund up to {0}.",
		"That line is not on this bill.",
		"Pick at least one item.",
		"Only {0} of {1} left to refund.",
		"Refund the whole bill, chosen items, or an amount.",
		"{0} can't go back to stock.",
		"Pick a refund reason.",
		"Say why in the note.",
		"An AI agent can never refund.",
		"Try again from the refund window.",
		"Money goes back as {0}.",
		"The amount to give back has changed: it is now {0}. Check it and refund again.",
		"This attempt already refunded {0}. Close the window to see it.",
	)

	def test_every_new_refusal_is_translated(self):
		from frappe.translate import clear_cache, get_all_translations
		clear_cache()
		for lang in ("ar", "es", "pt", "sw", "vi", "zh"):
			known = get_all_translations(lang)
			self.assertEqual([m for m in self.MESSAGES if m not in known], [], lang)
