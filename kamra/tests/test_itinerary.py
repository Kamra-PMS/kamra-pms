"""Itineraries (#411): one trip across properties, each leg an ordinary
reservation at its own hotel, priced, booked and cancelled through the
existing per-property paths."""

from __future__ import annotations

import frappe

from kamra import api, crs
from kamra.tests.audit_fixtures import (PROP_A, PROP_B, AuditTestCase, d,
                                        ensure_user, make_property, make_room,
                                        make_room_type)

USER = "ut-itinerary-desk@example.com"


class ItineraryTestCase(AuditTestCase):
	properties = (PROP_A, PROP_B)

	def setUp(self):
		super().setUp()
		frappe.local.lang = "en"
		make_property(PROP_A, free_cancel_days=0, cancellation_fee="None")
		# B charges the first night inside 30 days: its own policy, not A's
		make_property(PROP_B, free_cancel_days=3650, cancellation_fee="First Night")
		self.rt_a = make_room_type(PROP_A, "STD", base_price=1000)
		self.rt_b = make_room_type(PROP_B, "STD", base_price=2000)
		make_room(PROP_A, self.rt_a, "101")
		self.room_b = make_room(PROP_B, self.rt_b, "201")

	def legs(self, a=(1, 3), b=(3, 6)):
		# given out of order: the itinerary sorts them by date
		return [
			{"property": PROP_B, "room_type": self.rt_b,
			 "check_in_date": d(b[0]), "check_out_date": d(b[1])},
			{"property": PROP_A, "room_type": self.rt_a,
			 "check_in_date": d(a[0]), "check_out_date": d(a[1])},
		]

	def book(self, **kw):
		return crs.create_itinerary(legs=self.legs(), guest_name="UT Traveller",
		                            phone="+15550004111", **kw)

	def test_quote_is_each_legs_get_quote_and_their_sum(self):
		q = crs.quote_itinerary(legs=self.legs())
		self.assertEqual([leg["property"] for leg in q["legs"]], [PROP_A, PROP_B])
		for leg in q["legs"]:
			single = api.get_quote(property=leg["property"], room_type=leg["room_type"],
			                       check_in_date=leg["check_in_date"],
			                       check_out_date=leg["check_out_date"])
			self.assertEqual(leg["amount_after_tax"], single["amount_after_tax"])
			self.assertEqual(leg["available"], 1)
		self.assertAlmostEqual(q["total"], sum(leg["amount_after_tax"] for leg in q["legs"]))

	def test_create_books_one_reservation_per_leg_under_one_reference(self):
		itn = self.book()
		self.assertEqual(itn["status"], "Booked")
		self.assertEqual([leg["property"] for leg in itn["legs"]], [PROP_A, PROP_B])
		self.assertEqual((itn["check_in_date"], itn["check_out_date"]), (d(1), d(6)))
		guests = {frappe.db.get_value("Reservation", leg["reservation"], "guest")
		          for leg in itn["legs"]}
		self.assertEqual(guests, {itn["guest"]})
		self.assertAlmostEqual(itn["total"], sum(leg["amount_after_tax"] for leg in itn["legs"]))
		for leg in itn["legs"]:
			self.assertEqual(leg["status"], "Confirmed")
			self.assertTrue(leg["room"])
		listed = {r["name"]: r for r in crs.list_itineraries(search=itn["name"])}
		self.assertEqual(len(listed[itn["name"]]["legs"]), 2)

	def test_overlapping_legs_are_refused(self):
		with self.assertRaises(frappe.ValidationError):
			crs.create_itinerary(legs=self.legs(a=(1, 4), b=(3, 6)), guest_name="UT Overlap")
		self.assertFalse(frappe.db.exists("Reservation", {"guest_name": "UT Overlap"}))

	def test_amending_a_leg_into_the_next_is_refused(self):
		itn = self.book()
		first = frappe.get_doc("Reservation", itn["legs"][0]["reservation"])
		first.check_out_date = d(4)
		with self.assertRaises(frappe.ValidationError):
			first.save()

	def test_a_failing_leg_books_nothing(self):
		# B's only room is taken for the trip's nights
		api.create_booking(property=PROP_B, room_type=self.rt_b, check_in_date=d(3),
		                   check_out_date=d(6), guest_name="UT Other")
		before = frappe.db.count("Reservation", {"property": PROP_A})
		with self.assertRaises(frappe.ValidationError):
			self.book()
		self.assertEqual(frappe.db.count("Reservation", {"property": PROP_A}), before)
		self.assertFalse(frappe.db.exists("Itinerary", {"guest_name": "UT Traveller"}))

	def test_idempotency_key_replays_the_trip(self):
		first = self.book(idempotency_key="ut-itn-key")
		again = self.book(idempotency_key="ut-itn-key")
		self.assertEqual(again["name"], first["name"])
		self.assertTrue(again["idempotent_replay"])
		self.assertEqual(frappe.db.count("Reservation", {"itinerary": first["name"]}), 2)

	def test_cancel_applies_each_legs_own_policy(self):
		itn = self.book()
		preview = crs.cancel_itinerary_preview(itn["name"])
		fees = {r["property"]: r["estimated_fee"] for r in preview["legs"]}
		self.assertEqual(fees[PROP_A], 0)
		self.assertGreater(fees[PROP_B], 0)
		out = crs.cancel_itinerary(itn["name"], reason="Change of plans")
		self.assertEqual(out["status"], "Cancelled")
		by_prop = {leg["property"]: leg for leg in out["legs"]}
		self.assertEqual(by_prop[PROP_A]["cancellation_fee"], 0)
		self.assertAlmostEqual(by_prop[PROP_B]["cancellation_fee"], fees[PROP_B])
		self.assertTrue(all(leg["cancellation_number"] for leg in out["legs"]))

	def test_one_leg_cancels_alone(self):
		itn = self.book()
		api.cancel_reservation(itn["legs"][1]["reservation"], waive_fee=1)
		after = crs.get_itinerary(itn["name"])
		self.assertEqual(after["status"], "Booked")
		self.assertEqual([leg["status"] for leg in after["legs"]], ["Confirmed", "Cancelled"])
		self.assertAlmostEqual(after["total"], after["legs"][0]["amount_after_tax"])

	def test_add_leg_extends_the_trip(self):
		itn = self.book()
		out = crs.add_itinerary_leg(itn["name"], PROP_A, self.rt_a, d(6), d(8))
		self.assertEqual(str(out["legs"][-1]["check_in_date"]), d(6))
		with self.assertRaises(frappe.ValidationError):
			crs.add_itinerary_leg(itn["name"], PROP_A, self.rt_a, d(5), d(7))

	def test_restricted_user_cannot_touch_another_property(self):
		itn = self.book()
		ensure_user(USER, ["Front Desk"])
		frappe.get_doc({"doctype": "User Permission", "user": USER,
		                "allow": "Property", "for_value": PROP_A}).insert(ignore_permissions=True)
		frappe.clear_cache(user=USER)
		frappe.set_user(USER)  # nosemgrep: frappe-setuser -- acting as the restricted persona
		with self.assertRaises(frappe.PermissionError):
			crs.quote_itinerary(legs=self.legs())
		with self.assertRaises(frappe.PermissionError):
			crs.get_itinerary(itn["name"])
		self.assertNotIn(itn["name"], [r["name"] for r in crs.list_itineraries()])
		# Desk and /api/resource: the Itinerary doctype has no property field,
		# so the permission hooks carry the same rule
		self.assertNotIn(itn["name"], frappe.get_list("Itinerary", pluck="name"))
		self.assertFalse(frappe.has_permission("Itinerary", doc=itn["name"]))
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- back to the admin persona
		own = crs.create_itinerary(legs=[self.legs(a=(10, 12))[1]], guest_name="UT Scoped Trip")
		frappe.set_user(USER)  # nosemgrep: frappe-setuser -- acting as the restricted persona
		self.assertIn(own["name"], [r["name"] for r in crs.list_itineraries()])
		self.assertTrue(frappe.has_permission("Itinerary", doc=own["name"]))

	def test_leg_booked_after_a_lost_transaction_is_refused(self):
		# create_booking's deadlock retry rolls the whole transaction back,
		# taking the itinerary with it: the leg must not survive on its own
		from unittest.mock import patch
		real = api.create_booking

		def lost(**kw):
			frappe.db.delete("Itinerary", {"guest_name": "UT Traveller"})
			return real(**kw)

		with patch("kamra.api.create_booking", side_effect=lost):
			with self.assertRaises(frappe.ValidationError):
				self.book()
		self.assertFalse(frappe.db.exists("Reservation", {"guest_name": "UT Traveller"}))
