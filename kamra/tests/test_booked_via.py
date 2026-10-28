"""A booking keyed in from an OTA email is tagged like a channel booking."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from kamra.api import booking_options, create_booking
from kamra.channel_manager import canonical_channel


class BookedViaTestCase(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		frappe.local.lang = "en"
		self.property = frappe.get_doc({"doctype": "Property",
			"property_name": "TEST VIA " + frappe.generate_hash(length=8),
			"country": "Uganda", "currency": "UGX"}).insert(ignore_permissions=True).name
		self.room_type = frappe.get_doc({"doctype": "Room Type", "property": self.property,
			"room_type_code": "STD", "room_type_name": "Standard", "base_price": 1000,
			"adults_capacity": 2}).insert(ignore_permissions=True).name
		for n in ("101", "102", "103", "104", "105"):
			frappe.get_doc({"doctype": "Room", "property": self.property,
				"room_type": self.room_type, "room_number": n}).insert(ignore_permissions=True)

	def book(self, **kw):
		return create_booking(self.property, self.room_type, nowdate(),
		                      str(add_days(nowdate(), 2)), "Via Guest", **kw)

	def test_names_are_one_per_site(self):
		for raw in ("BookingCom", "booking.com", "booking", "Booking.com"):
			self.assertEqual(canonical_channel(raw), "Booking.com")
		self.assertEqual(canonical_channel("makemytrip"), "MakeMyTrip")
		self.assertEqual(canonical_channel("Cleartrip"), "Cleartrip")
		self.assertIsNone(canonical_channel("  "))

	def test_ota_booking_keeps_site_ref_and_sold_price(self):
		ref = "BDC-" + frappe.generate_hash(length=6)
		r = frappe.get_doc("Reservation", self.book(
			booked_via="booking.com", ota_ref=ref, ota_total=2600)["reservation"])
		self.assertEqual((r.source, r.channel, r.ota_ref), ("OTA", "Booking.com", ref))
		self.assertEqual(r.auto_price, 0)
		self.assertAlmostEqual(float(r.amount_after_tax), 2600, places=0)
		self.assertEqual(len(r.night_rates), 2)
		# the same email cannot be keyed twice
		self.assertRaises(frappe.ValidationError, self.book,
		                  booked_via="Booking.com", ota_ref=ref)
		self.assertIn("Booking.com", booking_options(self.property)["ota_channels"])

	def test_other_site_without_price_uses_rate_card(self):
		r = frappe.get_doc("Reservation", self.book(booked_via="Cleartrip")["reservation"])
		self.assertEqual((r.source, r.channel, r.auto_price), ("OTA", "Cleartrip", 1))
		self.assertIn("Cleartrip", booking_options(self.property)["ota_channels"])

	def test_direct_booking_unchanged(self):
		r = frappe.get_doc("Reservation", self.book()["reservation"])
		self.assertEqual(r.source, "Manual")
		self.assertFalse(r.channel)

	def ota(self, pct=15):
		"""A site with a default commission (its Travel Agent of type OTA)."""
		name = "TestSite" + frappe.generate_hash(length=6)
		frappe.get_doc({"doctype": "Travel Agent", "agent_name": name,
			"agent_type": "OTA", "commission_pct": pct}).insert(ignore_permissions=True)
		return name

	def group(self, **kw):
		from kamra.api import create_group_booking
		return create_group_booking(
			self.property, "Via group", nowdate(), str(add_days(nowdate(), 2)),
			[{"room_type": self.room_type, "count": 1, "adults": 2},
			 {"room_type": self.room_type, "count": 1, "adults": 1}],
			"Via Guest", **kw)

	def test_multi_room_shares_ref_and_splits_sold_price(self):
		ref = "AGD-" + frappe.generate_hash(length=6)
		out = self.group(booked_via="Agoda", ota_ref=ref, ota_total=5001)
		self.assertEqual(out["skipped"], [])
		rs = [frappe.get_doc("Reservation", n) for n in out["created"]]
		self.assertEqual(len(rs), 2)
		for r in rs:
			self.assertEqual((r.source, r.channel, r.ota_ref, r.auto_price),
			                 ("OTA", "Agoda", ref, 0))
			self.assertEqual(len(r.night_rates), 2)
		# same room type and rate card: an even split, to the unit
		self.assertAlmostEqual(sum(float(r.amount_after_tax) for r in rs), 5001, places=2)
		self.assertAlmostEqual(float(rs[0].amount_after_tax), 2500.5, places=2)
		# a second, separate booking with that reference is refused
		self.assertRaises(frappe.ValidationError, self.book, booked_via="Agoda", ota_ref=ref)
		self.assertRaises(frappe.ValidationError, self.group, booked_via="Agoda", ota_ref=ref)

	def test_walk_in_booked_via(self):
		from kamra.api import walk_in
		site = self.ota(pct=10)
		room = frappe.get_all("Room", filters={"property": self.property}, pluck="name")[0]
		out = walk_in(self.property, self.room_type, room, str(add_days(nowdate(), 1)),
		              "Walk Via", booked_via=site, ota_ref="W-1", ota_total=1100,
		              defer_check_in=1)
		r = frappe.get_doc("Reservation", out["reservation"])
		self.assertEqual((r.source, r.channel, r.ota_ref), ("OTA", site, "W-1"))
		self.assertAlmostEqual(float(r.amount_after_tax), 1100, places=0)
		pre = sum(float(n.rate) for n in r.night_rates)
		self.assertAlmostEqual(float(r.commission_amount), round(pre * 0.10, 2), places=2)

	def test_default_commission_prefill_and_override(self):
		site = self.ota(pct=18)
		self.assertEqual(booking_options(self.property)["ota_commission"][site], 18)
		r = frappe.get_doc("Reservation", self.book(booked_via=site, ota_total=2000)["reservation"])
		pre = sum(float(n.rate) for n in r.night_rates)
		self.assertAlmostEqual(float(r.commission_amount), round(pre * 0.18, 2), places=2)
		# the desk's own % wins, and a later save keeps it
		r = frappe.get_doc("Reservation", self.book(
			booked_via=site, ota_total=2000, ota_commission_pct=12)["reservation"])
		self.assertAlmostEqual(float(r.commission_amount), round(pre * 0.12, 2), places=2)
		r.save(ignore_permissions=True)
		self.assertAlmostEqual(float(r.commission_amount), round(pre * 0.12, 2), places=2)
		# a rate-card OTA booking keeps its commission through a re-save too
		r = frappe.get_doc("Reservation", self.book(booked_via=site)["reservation"])
		self.assertGreater(float(r.commission_amount), 0)
		r.save(ignore_permissions=True)
		self.assertGreater(float(r.reload().commission_amount), 0)
		# a direct booking has none
		r = frappe.get_doc("Reservation", self.book()["reservation"])
		self.assertEqual(float(r.commission_amount or 0), 0)

	def test_channel_manager_booking_gets_default_commission(self):
		from kamra import channel_manager as cm
		site = self.ota(pct=20)
		conn = frappe.get_doc({"doctype": "Channel Manager Connection", "property": self.property,
			"provider": "AioSell", "active": 1,
			"external_property_id": "via-" + frappe.generate_hash(length=6)}).insert(ignore_permissions=True)
		frappe.get_doc({"doctype": "Channel Room Mapping", "connection": conn.name,
			"room_type": self.room_type, "external_room_id": "std"}).insert(ignore_permissions=True)
		ev = {"event": "book", "channel": site, "room_type_external_id": "std",
		      "check_in": nowdate(), "check_out": str(add_days(nowdate(), 1)),
		      "guest_name": "CM Guest", "total": 1200, "currency": "UGX"}
		r = frappe.get_doc("Reservation", cm._apply_event(
			conn, dict(ev, ota_ref="CM-" + frappe.generate_hash(length=6)))["reservation"])
		pre = sum(float(n.rate) for n in r.night_rates)
		self.assertAlmostEqual(float(r.commission_amount), round(pre * 0.20, 2), places=2)
		# a payload that carries its own commission keeps it
		r = frappe.get_doc("Reservation", cm._apply_event(
			conn, dict(ev, ota_ref="CM-" + frappe.generate_hash(length=6),
			           commission=99))["reservation"])
		self.assertEqual(float(r.commission_amount), 99)

	def test_commission_report_groups_by_channel(self):
		from kamra.reports import contribution
		site = self.ota(pct=10)
		self.book(booked_via=site, ota_total=2200)
		self.book(booked_via=site, ota_total=2200)
		rows = {x["label"]: x for x in contribution(
			self.property, nowdate(), nowdate(), by="channel")["rows"]}
		self.assertEqual(rows[site]["bookings"], 2)
		self.assertGreater(rows[site]["commission"], 0)
		src = {x["label"]: x for x in contribution(
			self.property, nowdate(), nowdate(), by="source")["rows"]}
		self.assertEqual(src["OTA"]["commission"], rows[site]["commission"])
