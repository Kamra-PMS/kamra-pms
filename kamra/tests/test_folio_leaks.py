"""Five ways money left a stay unbilled, and the fixes that close them.

1. Check-out on a corporate stay moved EVERY open folio to the city ledger,
   the guest's own one (liquor, extras) included. Only the company's folio
   moves now; the guest settles the rest.
2. A room-service order for a room with no checked-in stay was delivered
   with nothing posted and nothing paid.
3. A folio could be closed with money still owed, and check-out only looked
   at Open folios, so the guest left owing.
4. A dine-in guest could not sign the bill to their room (charge_to_room).
5. An advance sat in the Deposit ledger forever; from check-in it now pays
   the stay through the Guest ledger.
"""

from __future__ import annotations

import frappe

from kamra import api, ledger, pos
from kamra import folio as folio_mod
from kamra.tests.audit_fixtures import (
	PROP_A,
	TODAY,
	AuditTestCase,
	d,
	guest_folio,
	make_guest,
	make_property,
	make_reservation,
	make_room,
	make_room_type,
)

COMPANY = "UT Leak Corp"


def _net(folio: str, ledger_name: str) -> float:
	return round(float(frappe.db.sql(
		"""SELECT COALESCE(SUM(debit - credit), 0) FROM `tabFolio Ledger Entry`
		   WHERE folio = %s AND ledger = %s""", (folio, ledger_name))[0][0]), 2)


def _balance(folio: str) -> float:
	return round(float(frappe.db.get_value("Folio", folio, "balance") or 0), 2)


class FolioLeaksTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")
		self.room2 = make_room(PROP_A, self.rt, "102")
		if frappe.db.exists("Corporate Account", COMPANY):
			corp = frappe.get_doc("Corporate Account", COMPANY)
		else:
			corp = frappe.get_doc({"doctype": "Corporate Account",
			                       "company_name": COMPANY})
		corp.credit_allowed = 1
		corp.set("billing_rules", [
			{"charge_type": "Room", "pay_by": "Company"},
			{"charge_type": "Food & Beverage", "pay_by": "Company"},
		])
		if corp.is_new():
			corp.insert(ignore_permissions=True)
		else:
			corp.save(ignore_permissions=True)
		self.company = corp.name

	def corporate_stay(self, room=None):
		return make_reservation(PROP_A, self.rt, d(-1), TODAY,
		                        status="Checked In", room=room or self.room,
		                        booking_type="Corporate", company=self.company)

	# 1. liquor billed to the company at check-out -------------------------

	def test_checkout_leaves_liquor_on_the_guest(self):
		res = self.corporate_stay()
		folio_mod.post_remaining_nights(res)
		company = frappe.db.get_value(
			"Folio", {"reservation": res.name, "folio_type": "Company"})
		self.assertTrue(company, "room night was not routed to the company")
		owed_by_company = _balance(company)
		self.assertGreater(owed_by_company, 0)
		guest = guest_folio(res.name)
		api.add_folio_charge(guest, "Food & Beverage", "UT Whisky", 1000,
		                     gst_rate=0, is_alcohol=1)
		liquor = _balance(guest)  # with whatever tax the hotel's rule adds
		self.assertGreaterEqual(liquor, 1000)

		with self.assertRaisesRegex(frappe.ValidationError, "still owed"):
			api.check_out(res.name)
		# the refusal moved nothing: no AR, the liquor still on the guest
		self.assertAlmostEqual(_balance(guest), liquor, places=2)
		self.assertAlmostEqual(_balance(company), owed_by_company, places=2)
		self.assertFalse(frappe.get_all("City Ledger Entry",
		                                filters={"folio": ["in", [guest, company]]}))

		api.add_folio_payment(guest, "Cash", liquor)
		api.check_out(res.name)
		self.assertEqual(frappe.db.get_value("Reservation", res.name, "status"),
		                 "Checked Out")
		# only the company's folio reached the city ledger
		cle = frappe.get_all("City Ledger Entry", filters={"folio": ["in", [guest, company]]},
		                     fields=["folio", "debit"])
		self.assertEqual([(r.folio, round(r.debit, 2)) for r in cle],
		                 [(company, owed_by_company)])
		self.assertFalse([p for p in frappe.get_doc("Folio", guest).payments
		                  if p.mode == "Company Credit"])
		self.assertAlmostEqual(_balance(company), 0, places=2)

	def test_guest_folio_of_a_credit_company_is_not_moved(self):
		# no billing rule for laundry: it stays on the guest folio, and a
		# company with credit still doesn't pick it up at check-out
		res = self.corporate_stay()
		guest = guest_folio(res.name)
		api.add_folio_charge(guest, "Laundry", "UT Laundry", 300, gst_rate=0)
		with self.assertRaisesRegex(frappe.ValidationError, "still owed"):
			api.check_out(res.name)
		self.assertAlmostEqual(ledger.company_payer_of(
			frappe.get_doc("Folio", guest)) or 0, 0)

	def test_quick_checkout_does_not_move_the_guest_folio(self):
		res = self.corporate_stay()
		guest = guest_folio(res.name)
		api.add_folio_charge(guest, "Minibar", "UT Beer", 400, gst_rate=0,
		                     is_alcohol=1)
		with self.assertRaisesRegex(frappe.ValidationError, "still owed"):
			ledger.quick_checkout(res.name)
		api.add_folio_payment(guest, "Cash", _balance(guest))
		ledger.quick_checkout(res.name)
		self.assertEqual(frappe.db.get_value("Folio", guest, "status"), "Closed")
		self.assertEqual(frappe.db.get_value("Reservation", res.name, "status"),
		                 "Checked Out")

	# 2 + 4. POS room posting ----------------------------------------------

	def outlet(self):
		name = frappe.db.get_value("POS Outlet", {"property": PROP_A,
		                                          "outlet_name": "UT Leak Bar"})
		if not name:
			name = frappe.get_doc({
				"doctype": "POS Outlet", "property": PROP_A,
				"outlet_name": "UT Leak Bar", "outlet_type": "Restaurant",
				"gst_rate": 5}).insert(ignore_permissions=True).name

		def item(label, price, alcohol=0):
			return frappe.get_doc({
				"doctype": "Menu Item", "property": PROP_A, "outlet": name,
				"item_name": label, "category": "Food", "price": price,
				"is_veg": 1, "available": 1, "prep_station": "Kitchen",
				"is_alcohol": alcohol}).insert(ignore_permissions=True).name
		return name, item("UT Dosa", 200), item("UT Gin", 500, alcohol=1)

	def test_room_service_to_an_empty_room_is_refused(self):
		outlet, dosa, _gin = self.outlet()
		with self.assertRaisesRegex(frappe.ValidationError, "no checked-in guest"):
			pos.create_order(outlet, [{"menu_item": dosa, "qty": 1}],
			                 room=self.room2, order_type="Room Service")

	def test_room_order_cannot_close_unbilled_after_the_guest_leaves(self):
		outlet, dosa, _gin = self.outlet()
		res = make_reservation(PROP_A, self.rt, d(-1), TODAY,
		                       status="Checked In", room=self.room)
		o = pos.create_order(outlet, [{"menu_item": dosa, "qty": 1}],
		                     room=self.room)
		self.assertEqual(frappe.db.get_value("POS Order", o["order"],
		                                     "reservation"), res.name)
		frappe.db.set_value("Reservation", res.name, "status", "Checked Out")
		with self.assertRaisesRegex(frappe.ValidationError, "no checked-in guest"):
			pos.deliver_order(o["order"])
		self.assertNotEqual(frappe.db.get_value("POS Order", o["order"], "status"),
		                    "Delivered")
		# paying at the outlet still closes it
		out = pos.pay_order(o["order"], "Cash")
		self.assertTrue(out["paid"])

	def test_room_order_without_a_stay_link_is_refused_at_delivery(self):
		# an order that reached the database with a room but no stay (older
		# data, or a stay that has since gone) never closes unbilled
		outlet, dosa, _gin = self.outlet()
		doc = frappe.get_doc({
			"doctype": "POS Order", "property": PROP_A, "outlet": outlet,
			"status": "Placed", "order_type": "Room Service", "room": self.room2,
			"items": [{"menu_item": dosa, "item_name": "UT Dosa", "qty": 1,
			           "rate": 200}]}).insert(ignore_permissions=True)
		with self.assertRaisesRegex(frappe.ValidationError, "no checked-in guest"):
			pos.deliver_order(doc.name)

	def test_in_house_rooms_lists_only_occupied_rooms(self):
		guest = make_guest("UT Asha")
		make_reservation(PROP_A, self.rt, d(-1), d(1), status="Checked In",
		                 room=self.room, guest=guest)
		rows = pos.in_house_rooms(PROP_A)
		self.assertEqual([(r["room"], r["room_number"]) for r in rows],
		                 [(self.room, "101")])
		self.assertIn("UT Asha", rows[0]["guest_name"])

	def test_dine_in_bill_charged_to_room_keeps_billing_and_alcohol_rules(self):
		outlet, dosa, gin = self.outlet()
		res = self.corporate_stay()
		guest = guest_folio(res.name)
		# food only: the company pays F&B, so it lands on the company folio
		food = pos.create_order(outlet, [{"menu_item": dosa, "qty": 1}],
		                        table_no="T1", order_type="Dine In")
		pos.charge_to_room(food["order"], self.room)
		self.assertTrue(pos.deliver_order(food["order"])["posted_to_folio"])
		company = frappe.db.get_value(
			"Folio", {"reservation": res.name, "folio_type": "Company"})
		self.assertTrue(frappe.get_all("Folio Charge", filters={
			"parent": company, "description": ["like", f"%{food['order']}%"]}))
		# with alcohol the whole bill goes to the guest
		drinks = pos.create_order(outlet, [{"menu_item": gin, "qty": 1}],
		                          table_no="T1", order_type="Dine In",
		                          room=self.room)
		self.assertEqual(frappe.db.get_value("POS Order", drinks["order"],
		                                     "order_type"), "Dine In")
		pos.deliver_order(drinks["order"])
		line = frappe.get_all("Folio Charge", filters={
			"description": ["like", f"%{drinks['order']}%"]},
			fields=["parent", "is_alcohol", "posting_date"])
		self.assertEqual([(r.parent, r.is_alcohol) for r in line], [(guest, 1)])
		self.assertEqual(str(line[0].posting_date), TODAY)

	def test_charge_to_room_refuses_an_empty_room(self):
		outlet, dosa, _gin = self.outlet()
		o = pos.create_order(outlet, [{"menu_item": dosa, "qty": 1}],
		                     table_no="T2", order_type="Dine In")
		with self.assertRaisesRegex(frappe.ValidationError, "no checked-in guest"):
			pos.charge_to_room(o["order"], self.room2)

	# 3. folio closed with a balance ---------------------------------------

	def test_close_folio_needs_a_settled_bill(self):
		res = make_reservation(PROP_A, self.rt, d(-1), d(1),
		                       status="Checked In", room=self.room)
		folio = guest_folio(res.name)
		api.add_folio_charge(folio, "Laundry", "UT Laundry", 500, gst_rate=0)
		with self.assertRaisesRegex(frappe.ValidationError, "still owed"):
			folio_mod.close_folio(folio)
		api.add_folio_payment(folio, "Cash", 600)
		with self.assertRaisesRegex(frappe.ValidationError, "owed back"):
			folio_mod.close_folio(folio)
		api.refund_folio_payment(folio, 100, "Cash", reason="UT change")
		self.assertTrue(folio_mod.close_folio(folio).startswith("INV-"))

	def test_city_ledger_transfer_then_close(self):
		res = self.corporate_stay()
		folio_mod.post_remaining_nights(res)
		company = frappe.db.get_value(
			"Folio", {"reservation": res.name, "folio_type": "Company"})
		ledger.transfer_to_city_ledger(company, self.company)
		self.assertTrue(folio_mod.close_folio(company).startswith("INV-"))

	def test_checkout_counts_a_closed_folio_with_a_balance(self):
		res = make_reservation(PROP_A, self.rt, d(-1), TODAY,
		                       status="Checked In", room=self.room)
		folio_mod.post_remaining_nights(res)
		folio = guest_folio(res.name)
		owed = _balance(folio)
		self.assertGreater(owed, 0)
		# a folio closed with money on it before this fix
		frappe.db.set_value("Folio", folio, {"status": "Closed",
		                                     "invoice_number": "INV-UT-LEGACY"})
		with self.assertRaisesRegex(frappe.ValidationError, "still owed"):
			api.check_out(res.name)

	# 5. advances leave the Deposit ledger ---------------------------------

	def advance_stay(self, amount=1500, room=None):
		res = make_reservation(PROP_A, self.rt, d(-1), TODAY,
		                       status="Confirmed", room=room or self.room)
		folio = folio_mod.open_folio(res)
		api.add_folio_payment(folio, "UPI", amount, kind="Advance")
		self.assertAlmostEqual(_net(folio, "Deposit"), -amount, places=2)
		return res, folio

	def test_check_in_moves_the_advance_to_the_guest_ledger(self):
		res, folio = self.advance_stay()
		res.reload()
		res.status = "Checked In"
		res.save(ignore_permissions=True)
		self.assertAlmostEqual(_net(folio, "Deposit"), 0, places=2)
		self.assertAlmostEqual(_net(folio, "Guest"), _balance(folio), places=2)
		# idempotent: running it again moves nothing
		self.assertEqual(ledger.transfer_advances_to_guest(res.name), 0)

		# after check-out with the bill paid, both ledgers are flat
		folio_mod.post_remaining_nights(res)
		owed = _balance(folio)
		if owed > 0:
			api.add_folio_payment(folio, "Cash", owed)
		elif owed < 0:
			api.refund_folio_payment(folio, -owed, "Cash", reason="UT change")
		api.check_out(res.name)
		self.assertAlmostEqual(_net(folio, "Deposit"), 0, places=2)
		self.assertAlmostEqual(_net(folio, "Guest"), 0, places=2)

	def test_advance_taken_in_house_pays_the_stay_at_once(self):
		res = make_reservation(PROP_A, self.rt, d(-1), d(1),
		                       status="Checked In", room=self.room)
		folio = guest_folio(res.name)
		api.add_folio_payment(folio, "Cash", 800, kind="Advance")
		self.assertAlmostEqual(_net(folio, "Deposit"), 0, places=2)
		self.assertAlmostEqual(_net(folio, "Guest"), -800, places=2)

	def test_backfill_patch_moves_stranded_advances_once(self):
		res, folio = self.advance_stay(1200)
		res.reload()
		res.status = "Checked In"
		res.save(ignore_permissions=True)
		# undo the transfer, as on a site from before the fix
		frappe.db.delete("Folio Ledger Entry", {
			"folio": folio, "description": ledger.ADVANCE_APPLIED})
		self.assertAlmostEqual(_net(folio, "Deposit"), -1200, places=2)
		from kamra.patches.v41 import move_advances_to_guest_ledger as patch
		patch.execute()
		patch.execute()
		self.assertAlmostEqual(_net(folio, "Deposit"), 0, places=2)
		moved = frappe.get_all("Folio Ledger Entry", filters={
			"folio": folio, "description": ledger.ADVANCE_APPLIED},
			fields=["ledger", "debit", "credit"])
		self.assertEqual(sorted((r.ledger, r.debit, r.credit) for r in moved),
		                 [("Deposit", 1200.0, 0.0), ("Guest", 0.0, 1200.0)])
		# a stay not yet in house keeps its advance as a deposit
		_pending, pending_folio = self.advance_stay(500, room=self.room2)
		patch.execute()
		self.assertAlmostEqual(_net(pending_folio, "Deposit"), -500, places=2)

	def test_a_no_show_fee_is_paid_from_the_advance(self):
		res, folio = self.advance_stay(1000)
		res.reload()
		fee = folio_mod.post_policy_fee(res, "First Night", "No-show charge (First Night)")
		self.assertGreater(fee, 0)
		# the advance paid the fee: nothing still held, and the Guest ledger
		# agrees with what the folio says is owed (or owed back)
		self.assertAlmostEqual(_net(folio, "Deposit"), 0, places=2)
		self.assertAlmostEqual(_net(folio, "Guest"), _balance(folio), places=2)

	def test_policy_fee_patch_moves_a_stranded_no_show_advance(self):
		res, folio = self.advance_stay(1000)
		res.reload()
		folio_mod.post_policy_fee(res, "First Night", "No-show charge (First Night)")
		frappe.db.set_value("Reservation", res.name, "status", "No Show")
		frappe.db.delete("Folio Ledger Entry", {
			"folio": folio, "description": ledger.ADVANCE_APPLIED})
		self.assertAlmostEqual(_net(folio, "Deposit"), -1000, places=2)
		from kamra.patches.v47 import move_policy_fee_advances_to_guest_ledger as patch
		patch.execute()
		patch.execute()
		self.assertAlmostEqual(_net(folio, "Deposit"), 0, places=2)
		self.assertAlmostEqual(_net(folio, "Guest"), _balance(folio), places=2)

	def test_a_status_edit_cannot_check_a_guest_out(self):
		res = make_reservation(PROP_A, self.rt, d(-1), TODAY,
		                       status="Checked In", room=self.room)
		res.reload()
		res.status = "Checked Out"
		with self.assertRaisesRegex(frappe.ValidationError, "Use Check out"):
			res.save(ignore_permissions=True)

	def test_a_tax_free_property_offers_only_zero_tax(self):
		from kamra.localization import generic
		frappe.db.set_value("Property", PROP_A, {"gst_rate_low": 0, "gst_rate_high": 0})
		frappe.clear_document_cache("Property", PROP_A)
		self.assertEqual(generic.tax_rate_options(PROP_A), [0])
		frappe.db.set_value("Property", PROP_A, "gst_rate_low", 5)
		frappe.clear_document_cache("Property", PROP_A)
		self.assertIn(5, generic.tax_rate_options(PROP_A))
