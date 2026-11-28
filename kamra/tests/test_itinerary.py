"""Itineraries (#411): one trip across properties, each leg an ordinary
reservation at its own hotel, priced, booked and cancelled through the
existing per-property paths."""

from __future__ import annotations

from unittest.mock import patch

import frappe

from kamra import api, crs, guest_booking, public_api
from kamra.ledger import round_to
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
		# refused exactly like a trip that doesn't exist: hotel B is never named
		with self.assertRaises(frappe.DoesNotExistError) as cm:
			crs.get_itinerary(itn["name"])
		self.assertNotIn(PROP_B, str(cm.exception))
		with self.assertRaises(frappe.DoesNotExistError) as missing:
			crs.get_itinerary("ITN-NONE")
		self.assertEqual(str(cm.exception), str(missing.exception))
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

	def restricted(self):
		ensure_user(USER, ["Front Desk"])
		if not frappe.db.exists("User Permission", {"user": USER, "allow": "Property"}):
			frappe.get_doc({"doctype": "User Permission", "user": USER, "allow": "Property",
			                "for_value": PROP_A}).insert(ignore_permissions=True)
		frappe.clear_cache(user=USER)
		frappe.set_user(USER)  # nosemgrep: frappe-setuser -- acting as the restricted persona

	def tearDown(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- restore
		super().tearDown()

	def test_restricted_overlap_never_shows_the_other_hotels_dates(self):
		itn = self.book()
		self.restricted()
		first = frappe.get_doc("Reservation", itn["legs"][0]["reservation"])
		first.check_out_date = d(4)
		with self.assertRaisesRegex(frappe.ValidationError, "another stay on this trip") as cm:
			first.save()
		self.assertNotIn(d(6), str(cm.exception))
		self.assertNotIn(PROP_B, str(cm.exception))

	def test_trip_links_are_written_only_by_the_trip(self):
		itn = self.book()
		other = crs.create_itinerary(legs=[self.legs(a=(10, 12))[1]], guest_name="UT Other Trip")
		res = frappe.get_doc("Reservation", itn["legs"][0]["reservation"])
		res.itinerary = other["name"]
		with self.assertRaises(frappe.PermissionError):
			res.save()
		res.reload()
		res.itinerary = None
		with self.assertRaises(frappe.PermissionError):
			res.save()
		# the desk reads trips; only kamra.crs writes them
		self.restricted()
		self.assertTrue(frappe.has_permission("Itinerary", "read"))
		self.assertFalse(frappe.has_permission("Itinerary", "create"))
		self.assertFalse(frappe.has_permission("Itinerary", "write"))

	def test_a_trip_with_no_legs_is_hidden_from_restricted_users(self):
		empty = frappe.get_doc({"doctype": "Itinerary", "guest": self.book()["guest"]}
		                       ).insert(ignore_permissions=True).name
		self.restricted()
		self.assertNotIn(empty, frappe.get_list("Itinerary", pluck="name"))
		self.assertFalse(frappe.has_permission("Itinerary", doc=empty))
		with self.assertRaises(frappe.DoesNotExistError):
			crs.get_itinerary(empty)

	def test_a_leg_with_no_children_keeps_zero(self):
		legs = self.legs()
		legs[0]["children"] = 0  # B: adults only, though the trip has a child
		q = crs.quote_itinerary(legs=legs, adults=2, children=1)
		by_prop = {leg["property"]: leg for leg in q["legs"]}
		self.assertEqual(by_prop[PROP_B]["children"], 0)
		itn = crs.create_itinerary(legs=legs, guest_name="UT Kids", adults=2, children=1)
		kids = {leg["property"]: leg["children"] for leg in itn["legs"]}
		self.assertEqual(kids, {PROP_A: 1, PROP_B: 0})

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


	def test_search_gives_each_hotels_currency_and_keeps_its_decimals(self):
		"""Central reservations shows each hotel's rates in that hotel's money."""
		frappe.db.set_value("Property", PROP_B, "currency", "USD")
		frappe.clear_document_cache("Property", PROP_B)
		frappe.db.set_value("Room Type", self.rt_b, "base_price", 2000.55)
		found = {p["property"]: p for p in crs.crs_search(d(3), d(6))["properties"]}
		self.assertEqual((found[PROP_A]["currency"], found[PROP_B]["currency"]), ("INR", "USD"))
		leg = crs.quote_itinerary(legs=self.legs())["legs"][1]
		self.assertEqual(found[PROP_B]["currency_symbol"], leg["currency_symbol"])
		quote = api.get_quote(property=PROP_B, room_type=self.rt_b,
		                      check_in_date=d(3), check_out_date=d(6))
		room = found[PROP_B]["room_types"][0]
		self.assertEqual(room["total"], round(quote["amount_after_tax"], 3))
		self.assertNotEqual(room["total"], round(room["total"]), "the cents were rounded away")
		self.assertEqual(room["per_night"], round(quote["amount_after_tax"] / 3, 3))
		self.assertEqual(found[PROP_B]["from_rate"], room["per_night"])


	def test_search_ranks_by_price_only_within_one_currency(self):
		"""A bare number can't compare two currencies: hotels are grouped by
		currency, cheapest first inside each."""
		def order():
			found = crs.crs_search(d(3), d(4))["properties"]
			return [p["property"] for p in found if p["property"] in (PROP_A, PROP_B)]

		frappe.db.set_value("Room Type", self.rt_b, "base_price", 500)
		self.assertEqual(order(), [PROP_B, PROP_A], "same currency: cheapest first")
		frappe.db.set_value("Property", PROP_B, "currency", "USD")
		frappe.clear_document_cache("Property", PROP_B)
		self.assertEqual(order(), [PROP_A, PROP_B], "500 dollars or cents are not under 1,000 rupees")

	def totals(self, currency, *amounts):
		"""A booked two-stay trip with these stay prices, read back."""
		for prop in (PROP_A, PROP_B):
			frappe.db.set_value("Property", prop, "currency", currency)
			frappe.clear_document_cache("Property", prop)
		itn = self.book()
		for leg, amount in zip(itn["legs"], amounts):
			frappe.db.set_value("Reservation", leg["reservation"], "amount_after_tax", amount)
		return crs.get_itinerary(itn["name"])

	def test_a_trip_total_is_its_stays_added_up_as_printed(self):
		# each stay prints as 100.13, so the trip is 200.26, not 200.25
		self.assertEqual(self.totals("INR", 100.125, 100.125)["total"], 200.26)

	def test_a_rupiah_trip_total_adds_up_the_whole_rupiah_stays(self):
		self.assertEqual(self.totals("IDR", 935000.5, 935000.5)["total"], 1870002)

	def test_the_printed_total_can_be_taken_as_the_advance(self):
		trip = self.totals("INR", 100.125, 100.125)
		plan = crs.trip_advance_preview(trip["name"], amount=trip["total"])
		self.assertEqual((plan["unpaid"], [leg["share"] for leg in plan["legs"]]),
		                 (200.26, [100.13, 100.13]))


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

	def test_advance_left_on_a_cancelled_leg_is_reported(self):
		itn = self.book()
		out = crs.record_trip_advance(itn["name"], itn["advance_due"], mode="Cash")
		b = out["legs"][1]
		api.cancel_reservation(b["reservation"], waive_fee=1)
		after = crs.get_itinerary(itn["name"])
		self.assertAlmostEqual(after["advance_paid"], out["legs"][0]["advance_paid"])
		self.assertAlmostEqual(after["advance_held_cancelled"], b["advance_paid"])

	def test_season_advance_between_25_and_100(self):
		def season(pct, name):
			return frappe.get_doc({"doctype": "Season", "property": PROP_A,
			                       "season_name": name, "start_date": d(20),
			                       "end_date": d(22), "adjustment_type": "Percent",
			                       "adjustment_value": 0, "advance_percent": pct}).insert()
		with self.assertRaises(frappe.ValidationError):
			season(10, "UT Low Advance")
		season(25, "UT Quarter Advance")
		season(0, "UT Default Advance")  # empty: the property's usual deposit

	def test_season_advance_over_100_is_refused(self):
		# more than the bill would be charged online by the booking page
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc({"doctype": "Season", "property": PROP_A,
			                "season_name": "UT Bad Advance", "start_date": d(20),
			                "end_date": d(22), "adjustment_type": "Percent",
			                "adjustment_value": 0, "advance_percent": 150}).insert()


class AdvanceRoundingTestCase(_TripBase):
	"""Advances keep the currency's own decimals, and never fewer than the two
	a bill can carry."""

	def setUp(self):
		super().setUp()
		for prop in (PROP_A, PROP_B):
			make_property(prop, free_cancel_days=0, cancellation_fee="None",
			              deposit_pct=100)

	def currency(self, code):
		for prop in (PROP_A, PROP_B):
			frappe.db.set_value("Property", prop, "currency", code)
			frappe.clear_document_cache("Property", prop)

	def trip(self, code, *amounts):
		"""A booked two-stay trip, each stay asking its whole price up front."""
		self.currency(code)
		itn = self.book()
		for leg, amount in zip(itn["legs"], amounts):
			frappe.db.set_value("Reservation", leg["reservation"], "amount_after_tax", amount)
		return crs.get_itinerary(itn["name"])

	def paid_on_folios(self, trip):
		return [float(frappe.get_doc("Folio", {"reservation": leg["reservation"],
		                                       "folio_type": "Guest"}).payments[0].amount)
		        for leg in trip["legs"]]

	def test_rupiah_stays_with_sen_can_take_the_advance_they_ask_for(self):
		# the trip prints as 1,650,000; the stays ask 1,650,000.40 between them
		trip = self.trip("IDR", 935000.4, 715000.0)
		plan = crs.trip_advance_preview(trip["name"])
		self.assertEqual((plan["amount"], [leg["share"] for leg in plan["legs"]]),
		                 (1650000.4, [935000.4, 715000.0]))
		out = crs.record_trip_advance(trip["name"], plan["amount"], mode="Cash")
		self.assertEqual(out["advance_due"], 0)
		self.assertEqual(self.paid_on_folios(out), [935000.4, 715000.0])

	def test_a_rupiah_trips_printed_total_can_still_be_typed(self):
		down = self.trip("IDR", 935000.4, 715000.0)
		plan = crs.trip_advance_preview(down["name"], amount=down["total"])
		self.assertEqual([leg["share"] for leg in plan["legs"]], [935000.4, 714999.6])
		for leg, amount in zip(down["legs"], (935000.6, 715000.0)):
			frappe.db.set_value("Reservation", leg["reservation"], "amount_after_tax", amount)
		up = crs.get_itinerary(down["name"])
		plan = crs.trip_advance_preview(up["name"], amount=up["total"])
		self.assertEqual((up["total"], [leg["share"] for leg in plan["legs"]]),
		                 (1650001, [935001.0, 715000.0]))

	def test_a_dinar_advance_keeps_its_third_decimal(self):
		trip = self.trip("KWD", 100.125, 100.125)
		self.assertEqual([leg["deposit_due"] for leg in trip["legs"]], [100.125, 100.125])
		self.assertEqual((trip["total"], trip["advance_due"]), (200.25, 200.25))
		plan = crs.trip_advance_preview(trip["name"], amount=trip["total"])
		self.assertEqual((plan["amount"], [leg["share"] for leg in plan["legs"]]),
		                 (200.25, [100.125, 100.125]))
		out = crs.record_trip_advance(trip["name"], 200.25, mode="Cash")
		self.assertEqual(out["advance_due"], 0)
		self.assertEqual(self.paid_on_folios(out), [100.125, 100.125])

	def test_one_fils_more_than_the_trip_owes_is_refused(self):
		trip = self.trip("KWD", 100.125, 100.125)
		with self.assertRaises(frappe.ValidationError) as refused:
			crs.trip_advance_preview(trip["name"], amount=200.251)
		self.assertIn("200.251", str(refused.exception))

	def test_two_decimal_advances_round_as_before(self):
		"""A bill ending in half a cent can't be settled in cents whichever way
		its advance rounds, so that figure waits for rounded bills (#753)."""
		trip = self.trip("USD", 252.945, 100.0)
		self.assertEqual(trip["legs"][0]["advance_required"], 252.94)
		self.assertEqual((trip["total"], trip["advance_due"]), (352.95, 352.94))
		for amount in (None, trip["total"]):
			plan = crs.trip_advance_preview(trip["name"], amount=amount)
			self.assertEqual(plan["amount"], amount or 352.94)
		# a percentage that lands on half a cent rounds as it always has
		for total, pct in ((33.3, 15.0), (0.14, 75.0), (16.9, 15.0)):
			policy = frappe._dict(name=PROP_A, booking_payment_mode="Advance percent",
			                      advance_percent=pct)
			self.assertEqual(public_api._advance_terms(policy, total)[0],
			                 round(total * pct / 100, 2), (total, pct))

	def test_the_quote_asks_the_advance_in_the_currencys_decimals(self):
		self.currency("KWD")
		frappe.db.set_value("Room Type", self.rt_a, "base_price", 100.125)
		q = api.get_quote(property=PROP_A, room_type=self.rt_a,
		                  check_in_date=d(1), check_out_date=d(2))
		total = q["amount_after_tax"]
		self.assertNotEqual(round(total, 3), round(total, 2), "needs a third decimal")
		self.assertEqual(q["advance"]["amount"],
		                 round_to(total, 3))

	def test_the_booking_page_asks_the_same_figure_as_the_desk(self):
		make_property(PROP_A, booking_payment_mode="Advance percent",
		              advance_percent=50)
		self.currency("KWD")
		split = public_api._payment_split(
			frappe.get_cached_doc("Property", PROP_A), 100.125)
		self.assertEqual((split["advance_due"], split["balance_at_hotel"]),
		                 (50.063, 50.062))

	def test_a_guest_booking_is_not_paid_up_while_fils_are_owing(self):
		self.currency("KWD")
		state = guest_booking._status(frappe._dict(
			name="UT", property=PROP_A, status="Held", advance_due=100.125,
			advance_paid=100.12, amount_after_tax=100.125))
		self.assertEqual(state["still_due_now"], 0.005)
