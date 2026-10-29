"""Itineraries (#411): one trip across properties, each leg an ordinary
reservation at its own hotel, priced, booked and cancelled through the
existing per-property paths."""

from __future__ import annotations

from unittest.mock import patch

import frappe

from kamra import api, crs
from kamra.tests.audit_fixtures import (PROP_A, PROP_B, AuditTestCase, d,
                                        ensure_user, make_property, make_room,
                                        make_room_type)

USER = "ut-itinerary-desk@example.com"


class _TripBase(AuditTestCase):
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


class ItineraryTestCase(_TripBase):
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


class TripAdvanceTestCase(_TripBase):
	"""One advance for the whole trip, split across the legs' folios, each
	leg owing the advance % its own dates ask for."""

	def setUp(self):
		super().setUp()
		make_property(PROP_A, free_cancel_days=0, cancellation_fee="None",
		              deposit_pct=50)
		make_property(PROP_B, free_cancel_days=3650,
		              cancellation_fee="First Night", deposit_pct=25)
		# B's dates fall in a season that wants the whole stay up front
		frappe.get_doc({"doctype": "Season", "property": PROP_B,
		                "season_name": "UT Peak", "start_date": d(3),
		                "end_date": d(5), "adjustment_type": "Percent",
		                "adjustment_value": 0, "advance_percent": 100}).insert()

	def test_allocation_rule(self):
		rows = [{"due": 100, "open": 400}, {"due": 300, "open": 300}]
		self.assertEqual(crs.allocate_trip_advance(rows, 250), [100, 150])
		self.assertEqual(crs.allocate_trip_advance(rows, 400), [100, 300])
		# the rest goes to the earliest leg, never past its bill
		self.assertEqual(crs.allocate_trip_advance(rows, 600), [300, 300])
		self.assertEqual(crs.allocate_trip_advance(rows, 700), [400, 300])

	def test_each_leg_owes_its_own_period_percent(self):
		itn = self.book()
		a, b = itn["legs"]
		self.assertEqual((a["advance_percent"], b["advance_percent"]), (50, 100))
		self.assertAlmostEqual(a["advance_required"], round(a["amount_after_tax"] / 2, 2))
		self.assertAlmostEqual(b["advance_required"], b["amount_after_tax"])
		self.assertAlmostEqual(itn["advance_due"],
		                       a["advance_required"] + b["advance_required"])
		# the same guest at B outside the season owes B's usual 25%
		q = api.get_quote(property=PROP_B, room_type=self.rt_b,
		                  check_in_date=d(10), check_out_date=d(12))
		self.assertEqual(q["advance"]["percent"], 25)
		self.assertEqual(api.get_quote(property=PROP_B, room_type=self.rt_b,
		                               check_in_date=d(3), check_out_date=d(5))
		                 ["advance"]["season"], "UT Peak")

	def test_one_payment_lands_on_each_legs_folio(self):
		itn = self.book()
		a, b = itn["legs"]
		extra = 10.0
		amount = itn["advance_due"] + extra
		preview = crs.trip_advance_preview(itn["name"], amount)
		self.assertEqual([leg["share"] for leg in preview["legs"]],
		                 [round(a["advance_required"] + extra, 2), b["advance_required"]])
		with self.assertRaises(frappe.ValidationError):
			crs.trip_advance_preview(itn["name"], itn["total"] + 1)
		out = crs.record_trip_advance(itn["name"], amount, mode="Cash")
		self.assertAlmostEqual(out["advance_paid"], amount)
		self.assertEqual(out["advance_due"], 0)
		for leg, share in zip(out["legs"], [x["share"] for x in preview["legs"]]):
			folio = frappe.get_doc("Folio", {"reservation": leg["reservation"],
			                                 "folio_type": "Guest"})
			self.assertEqual(folio.property, leg["property"])
			self.assertEqual([(p.payment_kind, p.amount) for p in folio.payments],
			                 [("Advance", share)])

	def test_trip_advance_retry_posts_once(self):
		itn = self.book()
		owed = itn["total"]
		first = crs.record_trip_advance(itn["name"], owed, idempotency_key="ut-trip-k")
		again = crs.record_trip_advance(itn["name"], owed, idempotency_key="ut-trip-k")
		self.assertEqual(again["idempotent_replay"], 1)
		self.assertAlmostEqual(again["advance_paid"], first["advance_paid"])
		self.assertAlmostEqual(first["advance_paid"], owed)
		# the full amount twice under different keys: nothing is owed now
		with self.assertRaises(frappe.ValidationError):
			crs.record_trip_advance(itn["name"], owed, idempotency_key="ut-trip-k2")
		paid = frappe.db.sql(
			"""SELECT SUM(fp.amount) FROM `tabFolio Payment` fp
			   JOIN `tabFolio` f ON f.name = fp.parent
			   WHERE f.reservation IN %s""",
			([leg["reservation"] for leg in itn["legs"]],))[0][0]
		self.assertAlmostEqual(float(paid), owed)

	def test_stay_advance_retry_posts_once(self):
		res = self.book()["legs"][0]["reservation"]
		one = api.record_advance(res, 100, mode="Cash", idempotency_key="ut-adv-k")
		two = api.record_advance(res, 100, mode="Cash", idempotency_key="ut-adv-k")
		self.assertEqual(two["idempotent_replay"], 1)
		self.assertEqual(two["folio"], one["folio"])
		self.assertEqual(frappe.db.get_value("Reservation", res, "advance_paid"), 100)
		self.assertEqual(len(frappe.get_doc("Folio", one["folio"]).payments), 1)
		# a new press is a new payment
		api.record_advance(res, 50, mode="Cash", idempotency_key="ut-adv-k2")
		self.assertEqual(frappe.db.get_value("Reservation", res, "advance_paid"), 150)

	def test_mixed_currencies_are_refused(self):
		itn = self.book()
		with patch("kamra.crs._locale", side_effect=lambda p: {
				"currency": "USD" if p == PROP_B else "INR", "currency_symbol": ""}):
			with self.assertRaises(frappe.ValidationError):
				crs.trip_advance_preview(itn["name"])

	def test_season_advance_over_100_is_refused(self):
		# more than the bill would be charged online by the booking page
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc({"doctype": "Season", "property": PROP_A,
			                "season_name": "UT Bad Advance", "start_date": d(20),
			                "end_date": d(22), "adjustment_type": "Percent",
			                "adjustment_value": 0, "advance_percent": 150}).insert()
