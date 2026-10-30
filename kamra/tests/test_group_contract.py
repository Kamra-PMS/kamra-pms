"""Group contract terms: the negotiated group rate is billed, rooms per
night differ, a quotation holds nothing, the group's money and attrition
add up, and a deposit lands on the group bill."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from kamra.api import (add_folio_payment, available_rooms, create_group_with_rooming_list,
                       group_detail, group_master_folio, group_quotation)
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
			self.property, "Offsite", self.ci, self.co, list(blocks), list(guests),
			guest_name="Lead", **kw)

	def test_the_group_rate_is_what_the_rooms_bill(self):
		out = self.make([{"room_type": self.room_type, "rooms_blocked": 2, "block_rate": 800}],
		                [{"room_type": self.room_type, "guest_name": "Lead"}])
		res = frappe.get_doc("Reservation", out["created"][0])
		self.assertFalse(res.auto_price)
		self.assertEqual([r.rate for r in res.night_rates], [800, 800])
		self.assertEqual(res.amount_before_tax, 1600)

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

	def test_a_checked_out_room_counts_as_used(self):
		from kamra.group_blocks import unpicked_by_night
		out = self.make([{"room_type": self.room_type, "rooms_blocked": 1}],
		                [{"room_type": self.room_type, "guest_name": "Lead"}])
		frappe.db.set_value("Reservation", out["created"][0], "status", "Checked Out")
		self.assertEqual(sum(unpicked_by_night(out["group_booking"], self.room_type).values()), 0)
