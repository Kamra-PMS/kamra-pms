"""Group contract terms: the negotiated group rate is billed, rooms per
night differ, a quotation holds nothing, the group's money and attrition
add up, and a deposit lands on the group bill."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from kamra.api import (add_folio_payment, available_rooms, create_group_with_rooming_list,
                       group_detail, group_master_folio, group_price_preview, group_quotation)
from kamra.group_blocks import block_hold_by_night


class GroupContractTestCase(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		frappe.local.lang = "en"
		self.property = frappe.get_doc({"doctype": "Property",
			"property_name": "TEST GRC " + frappe.generate_hash(length=8),
			"country": "Uganda", "currency": "UGX"}).insert(ignore_permissions=True).name
		self.room_type = frappe.get_doc({"doctype": "Room Type", "property": self.property,
			"room_type_code": "STD", "room_type_name": "Standard", "base_price": 1000,
			"adults_capacity": 2}).insert(ignore_permissions=True).name
		for n in ("101", "102", "103", "104", "105"):
			frappe.get_doc({"doctype": "Room", "property": self.property,
				"room_type": self.room_type, "room_number": n}).insert(ignore_permissions=True)
		self.ci = str(add_days(nowdate(), 10))
		self.mid = str(add_days(nowdate(), 11))
		self.co = str(add_days(nowdate(), 12))

	def make(self, blocks, guests=(), **kw):
		return create_group_with_rooming_list(
			self.property, "Offsite", self.ci, self.co, list(blocks), list(guests), **kw)

	def test_the_group_rate_is_what_the_rooms_bill(self):
		out = self.make([{"room_type": self.room_type, "rooms_blocked": 2, "block_rate": 800}],
		                [{"room_type": self.room_type, "guest_name": "Lead"}])
		res = frappe.get_doc("Reservation", out["created"][0])
		self.assertTrue(res.auto_price)
		self.assertEqual(res.agreed_rate, 800)
		self.assertEqual([r.rate for r in res.night_rates], [800, 800])
		self.assertEqual(res.amount_before_tax, 1600)

	def _booked_total(self, **extra):
		"""A group-rate room's total, and the same stay priced by the engine."""
		from kamra.api import create_booking
		from kamra.pricing import quote
		group = self.make([{"room_type": self.room_type, "rooms_blocked": 2, "block_rate": 800}])
		out = create_booking(self.property, self.room_type, self.ci, self.co, "Lead",
		                     group_booking=group["group_booking"], **extra)
		res = frappe.get_doc("Reservation", out["reservation"])
		q = quote(self.property, self.room_type, self.ci, self.co, 2, 0, agreed_rate=800,
		          pets=int(extra.get("pets") or 0),
		          over_capacity_charge=float(extra.get("over_capacity_charge") or 0))
		return res, q

	def test_a_group_rate_keeps_the_levy_the_pet_and_the_extra_guest(self):
		frappe.db.set_value("Property", self.property, {
			"pets_allowed": 1, "pet_charge": 300, "pet_charge_basis": "Per stay",
			"room_levy_percent": 2, "room_levy_taxable": 0})
		frappe.clear_document_cache("Property", self.property)
		frappe.db.set_value("Room Type", self.room_type, "max_extra_beds", 1)
		frappe.clear_document_cache("Room Type", self.room_type)
		res, q = self._booked_total(pets=1, over_capacity_guests=1, over_capacity_charge=200,
		                            over_capacity_reason="Agreed with the organiser")
		self.assertEqual(round(res.amount_after_tax, 2), round(q["amount_after_tax"], 2))
		self.assertGreater(q["room_levy"], 0)
		self.assertGreater(q["pet_charge"], 0)
		self.assertGreater(res.amount_after_tax, 1600)

	def test_a_group_rate_on_tax_inclusive_prices_adds_no_tax_on_top(self):
		frappe.db.set_value("Property", self.property, "rates_include_tax", 1)
		frappe.clear_document_cache("Property", self.property)
		res, q = self._booked_total()
		self.assertEqual(round(res.amount_after_tax, 2), 1600)
		self.assertEqual(round(q["amount_after_tax"], 2), 1600)
		preview = group_price_preview(self.property, self.ci, self.co, [
			{"room_type": self.room_type, "rooms_blocked": 1, "block_rate": 800}])
		self.assertEqual(preview["total"], 1600)

	def test_changing_dates_needs_the_new_price_confirmed(self):
		from kamra.api import PriceConfirmationRequired, amend_stay
		out = self.make([{"room_type": self.room_type, "rooms_blocked": 1, "block_rate": 800}],
		                [{"room_type": self.room_type, "guest_name": "Lead"}])
		longer = str(add_days(self.co, 1))
		with self.assertRaises(PriceConfirmationRequired):
			amend_stay(out["created"][0], self.ci, longer)
		amend_stay(out["created"][0], self.ci, longer, confirm_price=1)
		res = frappe.get_doc("Reservation", out["created"][0])
		self.assertEqual([r.rate for r in res.night_rates], [800, 800, 800])

	def test_only_a_rate_manager_can_set_a_billed_rate(self):
		from unittest.mock import patch

		from kamra.api import create_group_block, save_group_blocks
		out = self.make([{"room_type": self.room_type, "rooms_blocked": 1, "block_rate": 800}])
		with patch("kamra.api._can_set_rate", return_value=False):
			with self.assertRaises(frappe.PermissionError):
				self.make([{"room_type": self.room_type, "rooms_blocked": 1, "block_rate": 500}])
			with self.assertRaises(frappe.PermissionError):
				create_group_block(self.property, "Agent", self.ci, self.co,
				                   [{"room_type": self.room_type, "rooms_blocked": 1, "block_rate": 500}])
			with self.assertRaises(frappe.PermissionError):
				save_group_blocks(out["group_booking"],
				                  [{"room_type": self.room_type, "rooms_blocked": 1, "block_rate": 500}])
			# changing the rooms alone, at the same rate, stays with the desk
			save_group_blocks(out["group_booking"],
			                  [{"room_type": self.room_type, "rooms_blocked": 2, "block_rate": 800}])
		self.assertEqual(group_detail(out["group_booking"])["pickup"][0]["rooms_blocked"], 2)

	def test_a_direct_save_cannot_change_the_rate_either(self):
		from unittest.mock import patch
		out = self.make([{"room_type": self.room_type, "rooms_blocked": 1, "block_rate": 800}])
		gb = frappe.get_doc("Group Booking", out["group_booking"])
		gb.blocks[0].block_rate = 500
		with patch("kamra.api._can_set_rate", return_value=False):
			# the REST resource path saves the doc as it is
			with self.assertRaises(frappe.PermissionError):
				gb.save(ignore_permissions=True)
			gb.reload()
			gb.notes = "rooming list sent"
			gb.save(ignore_permissions=True)

	def test_moving_the_group_shifts_its_nights_and_keeps_own_dates(self):
		from kamra.api import group_amend_dates
		out = self.make(
			[{"room_type": self.room_type, "rooms_blocked": 3,
			  "nightly_counts": {self.ci: 1, self.mid: 3}}],
			[{"room_type": self.room_type, "guest_name": "Lead"},
			 {"room_type": self.room_type, "guest_name": "Second night only",
			  "check_in_date": self.mid, "check_out_date": self.co}])
		new_ci, new_mid, new_co = (str(add_days(nowdate(), n)) for n in (20, 21, 22))
		result = group_amend_dates(out["group_booking"], new_ci, new_co, confirm_price=1)
		self.assertFalse([x for x in result["results"] if x.get("error")], result)
		short = frappe.get_doc("Reservation", out["created"][1])
		self.assertEqual((str(short.check_in_date), str(short.check_out_date)), (new_mid, new_co))
		gb = frappe.get_doc("Group Booking", out["group_booking"])
		self.assertEqual(str(gb.check_in_date), new_ci)
		self.assertEqual(frappe.parse_json(gb.blocks[0].nightly_counts), {new_ci: 1, new_mid: 3})

	def test_a_group_stays_put_when_a_room_could_not_move(self):
		from kamra.api import group_amend_dates
		out = self.make([{"room_type": self.room_type, "rooms_blocked": 2}],
		                [{"room_type": self.room_type, "guest_name": "One"},
		                 {"room_type": self.room_type, "guest_name": "Two"}])
		new_ci, new_co = (str(add_days(nowdate(), n)) for n in (20, 22))
		group_amend_dates(out["group_booking"], new_ci, new_co, [out["created"][0]], confirm_price=1)
		self.assertEqual(str(frappe.db.get_value("Group Booking", out["group_booking"], "check_in_date")), self.ci)

	def test_held_rooms_must_be_free_on_the_new_dates(self):
		from kamra.api import create_booking, group_amend_dates
		new_ci, new_co = (str(add_days(nowdate(), n)) for n in (20, 22))
		for i in range(3):
			create_booking(self.property, self.room_type, new_ci, new_co, f"Other {i}")
		out = self.make([{"room_type": self.room_type, "rooms_blocked": 4}])
		with self.assertRaises(frappe.ValidationError):
			group_amend_dates(out["group_booking"], new_ci, new_co, confirm_price=1)
		self.assertEqual(str(frappe.db.get_value("Group Booking", out["group_booking"], "check_in_date")), self.ci)

	def test_cancelling_nothing_or_after_a_stay_leaves_the_group_open(self):
		from kamra.api import group_cancel
		empty = self.make([{"room_type": self.room_type, "rooms_blocked": 1}])
		group_cancel(empty["group_booking"], waive_fee=1)
		self.assertEqual(frappe.db.get_value("Group Booking", empty["group_booking"], "status"), "Confirmed")
		stayed = self.make([{"room_type": self.room_type, "rooms_blocked": 1}],
		                   [{"room_type": self.room_type, "guest_name": "Lead"}])
		frappe.db.set_value("Reservation", stayed["created"][0], "status", "Checked Out")
		group_cancel(stayed["group_booking"], waive_fee=1)
		self.assertEqual(frappe.db.get_value("Group Booking", stayed["group_booking"], "status"), "Confirmed")

	def test_rooms_per_night_hold_each_night_and_guests_keep_their_own_dates(self):
		out = self.make(
			[{"room_type": self.room_type, "rooms_blocked": 3,
			  "nightly_counts": {self.ci: 1, self.mid: 3}}],
			[{"room_type": self.room_type, "guest_name": "Lead"},
			 {"room_type": self.room_type, "guest_name": "Saturday only",
			  "check_in_date": self.mid, "check_out_date": self.co}])
		self.assertEqual(out["skipped"], [])
		held = block_hold_by_night(self.property, self.room_type, [self.ci, self.mid])
		# night 1: 1 blocked, 1 picked; night 2: 3 blocked, 2 picked
		self.assertEqual(held, {self.ci: 0, self.mid: 1})
		short = frappe.get_doc("Reservation", out["created"][1])
		self.assertEqual(str(short.check_in_date), self.mid)

	def test_a_guest_over_a_nights_block_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self.make(
				[{"room_type": self.room_type, "rooms_blocked": 2,
				  "nightly_counts": {self.ci: 1, self.mid: 2}}],
				[{"room_type": self.room_type, "guest_name": "A"},
				 {"room_type": self.room_type, "guest_name": "B"}])

	def test_a_quotation_holds_and_books_nothing(self):
		out = self.make([{"room_type": self.room_type, "rooms_blocked": 4}],
		                [{"room_type": self.room_type, "guest_name": "Lead"}],
		                quotation_only=1, deposit_due=5000)
		self.assertEqual((out["status"], out["created"]), ("Open", []))
		self.assertEqual(len(available_rooms(self.property, self.room_type, self.ci, self.co)), 5)
		q = group_quotation(out["group_booking"])
		self.assertEqual(q["prices"]["rows"][0]["room_nights"], 8)
		self.assertEqual(q["group"]["deposit_due"], 5000)
		self.assertGreater(q["prices"]["total"], 0)

	def test_money_and_attrition_add_up(self):
		out = self.make([{"room_type": self.room_type, "rooms_blocked": 4, "block_rate": 1000}],
		                [{"room_type": self.room_type, "guest_name": "Lead"},
		                 {"room_type": self.room_type, "guest_name": "Two"}],
		                attrition_pct=10)
		d = group_detail(out["group_booking"])
		a = d["attrition"]
		# 4 rooms x 2 nights blocked, 2 rooms x 2 nights picked up
		self.assertEqual((a["blocked_room_nights"], a["picked_room_nights"]), (8, 4))
		self.assertEqual(a["pickup_pct"], 50.0)
		self.assertAlmostEqual(a["shortfall_room_nights"], 3.2)
		self.assertTrue(a["warn"])  # cutoff is 7 days before arrival, 3 days away
		# nothing charged or paid yet: the two booked rooms are what is due
		self.assertEqual(d["money"]["due"], d["money"]["booked"])
		self.assertGreater(d["money"]["block_value"], d["money"]["booked"])

	def test_a_deposit_lands_on_the_group_bill(self):
		out = self.make([{"room_type": self.room_type, "rooms_blocked": 2}],
		                [{"room_type": self.room_type, "guest_name": "Lead"}],
		                master_index=0, master_pays="Room only")
		folio = group_master_folio(out["group_booking"])["folio"]
		add_folio_payment(folio, "Cash", 1500, kind="Advance")
		money = group_detail(out["group_booking"])["money"]
		self.assertEqual(money["deposits"], 1500)
		self.assertEqual(money["due"], round(max(0, money["booked"] - 1500), 2))

	def test_only_an_advance_counts_as_a_deposit(self):
		out = self.make([{"room_type": self.room_type, "rooms_blocked": 1}],
		                [{"room_type": self.room_type, "guest_name": "Lead"}],
		                master_index=0, master_pays="Room only")
		folio = group_master_folio(out["group_booking"])["folio"]
		add_folio_payment(folio, "Cash", 1000, kind="Advance")
		add_folio_payment(folio, "Cash", 500)
		money = group_detail(out["group_booking"])["money"]
		self.assertEqual((money["deposits"], money["paid"]), (1000, 1500))

	def test_a_checked_out_room_counts_as_used(self):
		from kamra.group_blocks import unpicked_by_night
		out = self.make([{"room_type": self.room_type, "rooms_blocked": 1}],
		                [{"room_type": self.room_type, "guest_name": "Lead"}])
		frappe.db.set_value("Reservation", out["created"][0], "status", "Checked Out")
		self.assertEqual(sum(unpicked_by_night(out["group_booking"], self.room_type).values()), 0)
