"""Channex outbound: ARI by changes, through an outbox.

Channex certifies a PMS that sends only what changed, batched into date
ranges, under its rate limit (10 calls a minute per property and endpoint),
with a full sync only on demand. No HTTP here: FakeChannex stands in for
channex._send, and the clock is kamra.channel_ari._now.

Each certification case is a test named after its number (test_cert_NN_...);
its docstring gives the shape the case asks for. Dates are relative to today:
the certification guide's own dates would expire."""

import copy
import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils import add_days, getdate, nowdate

from kamra.channels import channex


def day(n: int) -> str:
	return str(add_days(nowdate(), n))


class _Response:
	def __init__(self, status_code, body=None, headers=None):
		self.status_code, self._body, self.headers = status_code, body, headers or {}
		self.text = json.dumps(body) if body is not None else ""

	def json(self):
		if self._body is None:
			raise ValueError("no json")
		return self._body


class FakeChannex:
	"""Channex's ARI and property API in memory, standing in for
	channex._send. Records every call as (method, path, params, payload), in
	order; serves room_types / rate_plans / properties; answers ARI posts with
	task ids. fail() queues an exception for a path; warn() makes a post come
	back with meta.warnings; headers are sent back on every answer."""

	def __init__(self):
		self.calls: list[tuple] = []
		self.failures: dict[str, list] = {}
		self.warn_fn = None
		self.headers: dict = {}
		self.tasks = 0
		self.property = {"id": "cx-test", "title": "Hotel Test", "currency": "USD",
		                 "timezone": "America/Guayaquil"}
		self.room_types: list[dict] = []
		self.rate_plans: list[dict] = []

	def fail(self, path: str, exc: Exception, times: int = 1) -> None:
		self.failures.setdefault(path, []).extend([exc] * times)

	def posts(self, kind: str) -> list[list[dict]]:
		"""The `values` of every POST to `kind`, in order."""
		return [payload["values"] for m, p, _, payload in self.calls if m == "POST" and p == kind]

	def _page(self, items: list[dict], params: dict) -> dict:
		page = int((params or {}).get("pagination[page]") or 1)
		limit = int((params or {}).get("pagination[limit]") or 10)
		return {"meta": {"page": page, "limit": limit, "total": len(items)},
		        "data": items[(page - 1) * limit:page * limit]}

	def __call__(self, conn, method, path, *, params=None, payload=None):
		self.calls.append((method, path, copy.deepcopy(params), copy.deepcopy(payload)))
		pending = self.failures.get(path)
		if pending:
			raise pending.pop(0)
		if method == "POST" and path in ("availability", "restrictions"):
			self.tasks += 1
			body = {"data": [{"id": f"task-{self.tasks}", "type": "task"}],
			        "meta": {"message": "Success"}}
			if self.warn_fn:
				warnings = self.warn_fn(path, payload)
				if warnings:
					body["meta"]["warnings"] = warnings
			return body, dict(self.headers)
		if method == "GET" and path == "room_types":
			return self._page(self.room_types, params), dict(self.headers)
		if method == "GET" and path == "rate_plans":
			return self._page(self.rate_plans, params), dict(self.headers)
		if method == "GET" and path.startswith("properties/"):
			attrs = dict(self.property)
			return {"data": {"type": "property", "id": attrs.pop("id"), "attributes": attrs}}, {}
		raise AssertionError(f"FakeChannex: unexpected {method} {path}")


def _conn(**kw):
	c = frappe._dict(name="CMC-X", provider="Channex", endpoint="http://channex.test/api/v1",
	                 external_property_id="prop", **kw)
	c.get_password = lambda *a, **k: "key-1"
	return c


class ChannexAriAdapterTestCase(UnitTestCase):
	def test_restrictions_change_posts_a_range_with_the_rate_as_a_decimal_string(self):
		fake = FakeChannex()
		with patch.object(channex, "_send", side_effect=fake):
			channex.push_ari_changes(_conn(), "restrictions", [
				{"external_id": "rp1", "date_from": "2030-01-01", "date_to": "2030-01-05",
				 "values": {"rate": Decimal("241")}},
				{"external_id": "rp2", "date": "2030-01-07", "values": {"rate": Decimal("312.666")}}])
		self.assertEqual(fake.calls[0][:2], ("POST", "restrictions"))
		self.assertEqual(fake.posts("restrictions"), [[
			{"property_id": "prop", "rate_plan_id": "rp1", "date_from": "2030-01-01",
			 "date_to": "2030-01-05", "rate": "241.00"},
			{"property_id": "prop", "rate_plan_id": "rp2", "date": "2030-01-07", "rate": "312.67"}]])

	def test_availability_change_carries_the_room_type_and_an_integer(self):
		fake = FakeChannex()
		with patch.object(channex, "_send", side_effect=fake):
			channex.push_ari_changes(_conn(), "availability", [
				{"external_id": "rt1", "date": "2030-01-01", "values": {"availability": 7}}])
		self.assertEqual(fake.posts("availability"), [[
			{"property_id": "prop", "room_type_id": "rt1", "date": "2030-01-01", "availability": 7}]])

	def test_task_ids_and_the_rejected_change_with_its_reasons(self):
		fake = FakeChannex()
		fake.warn_fn = lambda path, payload: [dict(payload["values"][1], warning={"rate": ["must be positive"]})]
		changes = [{"external_id": "rp1", "date": "2030-01-01", "values": {"rate": Decimal("10")}},
		           {"external_id": "rp2", "date": "2030-01-02", "values": {"rate": Decimal("11")}}]
		with patch.object(channex, "_send", side_effect=fake):
			out = channex.push_ari_changes(_conn(), "restrictions", changes)
		self.assertEqual(out["task_ids"], ["task-1"])
		self.assertEqual(out["rejected"], [dict(changes[1], reasons={"rate": ["must be positive"]})])
		self.assertEqual(out["wait"], 0)

	def test_429_and_the_ratelimit_header(self):
		with patch("requests.request", return_value=_Response(
				429, {"errors": {"code": "too_many", "details": {"retry_after": 30}}}, {"Retry-After": "30"})):
			with self.assertRaises(channex.ChannexRateLimited) as ctx:
				channex.push_ari_changes(_conn(), "restrictions", [
					{"external_id": "rp1", "date": "2030-01-01", "values": {"rate": Decimal("10")}}])
		self.assertEqual(ctx.exception.retry_after, 30)
		self.assertEqual(channex.rate_limit_wait({"ratelimit": '"route";r=0;t=42, "key";r=5;t=10'}), 42)
		self.assertEqual(channex.rate_limit_wait({"ratelimit": '"route";r=3;t=42, "key";r=5;t=10'}), 0)
		self.assertEqual(channex.rate_limit_wait({"ratelimit": "garbage;;=="}), 0)
		self.assertEqual(channex.rate_limit_wait({}), 0)

	def test_send_returns_lowercase_headers_and_a_network_error_is_status_0(self):
		import requests
		with patch("requests.request", return_value=_Response(200, {"data": []}, {"RateLimit": '"a";r=1;t=5'})):
			body, headers = channex._send(_conn(), "GET", "room_types")
		self.assertEqual(body, {"data": []})
		self.assertEqual(headers, {"ratelimit": '"a";r=1;t=5'})
		with patch("requests.request", side_effect=requests.Timeout("slow")):
			with self.assertRaises(channex.ChannexError) as ctx:
				channex._send(_conn(), "GET", "room_types")
		self.assertEqual(ctx.exception.status, 0)

	def test_property_details_walk_every_page_and_tie_plans_to_their_room(self):
		fake = FakeChannex()
		fake.room_types = [{"type": "room_type", "id": f"rt{i}", "attributes": {
			"title": f"Room {i}", "count_of_rooms": i, "occ_adults": 2, "default_occupancy": 2}}
			for i in (1, 2)]
		fake.rate_plans = [{"type": "rate_plan", "id": f"rp{i}", "attributes": {
			"title": f"Plan {i}", "sell_mode": "per_room", "currency": "USD", "meal_type": "none"},
			"relationships": {"room_type": {"data": {"type": "room_type", "id": "rt1" if i % 2 else "rt2"}}}}
			for i in range(1, 106)]
		with patch.object(channex, "_send", side_effect=fake):
			details = channex.fetch_property_details(_conn())
		self.assertEqual([c[1] for c in fake.calls].count("rate_plans"), 2)
		self.assertEqual(details["hotel_id"], "cx-test")
		self.assertEqual((details["currency"], details["timezone"]), ("USD", "America/Guayaquil"))
		self.assertTrue(details["per_rate_plan"])
		rooms = {r["room_id"]: r for r in details["rooms"]}
		self.assertEqual(rooms["rt1"]["count_of_rooms"], 1)
		self.assertEqual(len(rooms["rt1"]["rateplans"]), 53)
		self.assertEqual(len(rooms["rt2"]["rateplans"]), 52)
		self.assertEqual(rooms["rt2"]["rateplans"][0], {"rateplan_id": "rp2", "rateplan_name": "Plan 2",
		                                                "sell_mode": "per_room", "currency": "USD"})

	def test_seam_push_ari_sends_ranges_in_two_calls(self):
		fake = FakeChannex()
		snapshot = [{"room_type": "T", "external_room_id": "rt1", "external_rate_id": "rp1", "days": [
			{"date": f"2030-01-0{i}", "available": 3, "rate": 100.0} for i in range(1, 6)]}]
		with patch.object(channex, "_send", side_effect=fake):
			ok, detail = channex.push_ari(_conn(), snapshot)
		self.assertTrue(ok, detail)
		self.assertEqual(len(fake.calls), 2)
		self.assertEqual(fake.posts("availability"), [[{"property_id": "prop", "room_type_id": "rt1",
			"date_from": "2030-01-01", "date_to": "2030-01-05", "availability": 3}]])
		self.assertEqual(fake.posts("restrictions"), [[{"property_id": "prop", "rate_plan_id": "rp1",
			"date_from": "2030-01-01", "date_to": "2030-01-05", "rate": "100.00"}]])


class _AriFixture:
	"""An Ecuador/USD property: Twin (8 rooms) and Double (4), the plans BAR
	(no Rate Plan: the base price) and BB (Rate Plan Amount +20), a Channex
	connection cx-test and its 4 mappings."""

	def setUp(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		frappe.local.lang = "en"
		tag = frappe.generate_hash(length=6).upper()
		self.property = frappe.get_doc({"doctype": "Property",
			"property_name": "TEST ARI " + tag, "country": "Ecuador",
			"currency": "USD"}).insert(ignore_permissions=True).name
		self.twin = self._room_type("TWN" + tag, "Twin", 100, 8)
		self.double = self._room_type("DBL" + tag, "Double", 120, 4)
		self.bb = frappe.get_doc({"doctype": "Rate Plan", "property": self.property,
			"rate_plan_name": "Bed and Breakfast", "code": "BB" + tag, "modifier_type": "Amount",
			"modifier_value": 20}).insert(ignore_permissions=True).name
		self.conn = frappe.get_doc({"doctype": "Channel Manager Connection",
			"property": self.property, "provider": "Channex", "active": 1,
			"external_property_id": "cx-test", "webhook_secret": "ut-hook",
			"ari_batch_seconds": 0}).insert(ignore_permissions=True)
		for rt, ext in ((self.twin, "twin"), (self.double, "double")):
			for plan, rate_plan in (("bar", None), ("bb", self.bb)):
				frappe.get_doc({"doctype": "Channel Room Mapping", "connection": self.conn.name,
					"room_type": rt, "external_room_id": f"rt-{ext}",
					"external_rate_id": f"rp-{ext}-{plan}", "rate_plan": rate_plan,
				}).insert(ignore_permissions=True)
		self.fake = FakeChannex()
		self.clock = [1_900_000_000.0]
		self.clear_cache()

	def clear_cache(self):
		# connection names come back after each test's rollback; their cache keys must not
		for key in ("channex_ari_error::{c}", "channex_pause::{c}", "channex_feed_error::{c}"):
			frappe.cache.delete_value(key.format(c=self.conn.name))
		for kind in ("availability", "restrictions"):
			frappe.cache.delete_value(f"channex_ari_pause::{self.conn.name}::{kind}")
			frappe.cache.delete_value(f"channex_ari_calls::{self.conn.name}::{kind}")

	def _room_type(self, code, name, price, rooms) -> str:
		rt = frappe.get_doc({"doctype": "Room Type", "property": self.property,
			"room_type_code": code, "room_type_name": name, "base_price": price,
			"adults_capacity": 2}).insert(ignore_permissions=True).name
		for i in range(rooms):
			frappe.get_doc({"doctype": "Room", "property": self.property, "room_type": rt,
				"room_number": f"{code}-{i + 1}"}).insert(ignore_permissions=True)
		return rt

	def season(self, room_type, start: int, end: int | None = None, value=150, kind="Absolute"):
		return frappe.get_doc({"doctype": "Season", "property": self.property,
			"season_name": f"S {start}-{end}", "room_type": room_type, "start_date": day(start),
			"end_date": day(start if end is None else end), "adjustment_type": kind,
			"adjustment_value": value, "priority": 10}).insert(ignore_permissions=True)

	def book(self, room_type, start: int, nights: int = 1):
		guest = frappe.get_doc({"doctype": "Guest", "first_name": "Ari",
			"last_name": "Prueba"}).insert(ignore_permissions=True).name
		return frappe.get_doc({"doctype": "Reservation", "property": self.property,
			"room_type": room_type, "guest": guest, "status": "Confirmed",
			"check_in_date": day(start), "check_out_date": day(start + nights),
			"adults": 2}).insert(ignore_permissions=True)


class ChannexAriCellsTestCase(_AriFixture, IntegrationTestCase):
	def test_compress_joins_consecutive_equal_days(self):
		from kamra import channel_ari
		cells = {"rp1": {day(i): {"rate": Decimal("241.00")} for i in range(1, 11)}}
		cells["rp1"].update({day(i): {"rate": Decimal("312.66")} for i in range(11, 18)})
		self.assertEqual(channel_ari.compress(cells), [
			{"external_id": "rp1", "date_from": day(1), "date_to": day(10), "values": {"rate": Decimal("241.00")}},
			{"external_id": "rp1", "date_from": day(11), "date_to": day(17), "values": {"rate": Decimal("312.66")}}])
		gap = {"rp2": {day(1): {"rate": Decimal("5")}, day(2): {"rate": Decimal("5")},
		               day(4): {"rate": Decimal("5")}, day(5): {"rate": Decimal("6")}},
		       "rp1": {day(3): {"stop_sell": True}}}
		self.assertEqual(channel_ari.compress(gap), [
			{"external_id": "rp1", "date": day(3), "values": {"stop_sell": True}},
			{"external_id": "rp2", "date_from": day(1), "date_to": day(2), "values": {"rate": Decimal("5")}},
			{"external_id": "rp2", "date": day(4), "values": {"rate": Decimal("5")}},
			{"external_id": "rp2", "date": day(5), "values": {"rate": Decimal("6")}}])

	def test_diff_keeps_only_the_changed_fields_of_the_changed_days(self):
		from kamra import channel_ari
		cells = {"rp1": {day(1): {"rate": Decimal("100.00"), "stop_sell": False},
		                 day(2): {"rate": Decimal("100.00"), "stop_sell": False}}}
		sent = {"rp1": {day(1): {"rate": "100.00", "stop_sell": False},
		                day(2): {"rate": "100.00", "stop_sell": False}}}
		self.assertEqual(channel_ari.diff_cells(cells, sent), {})
		cells["rp1"][day(2)]["rate"] = Decimal("120.00")
		self.assertEqual(channel_ari.diff_cells(cells, sent), {"rp1": {day(2): {"rate": Decimal("120.00")}}})
		self.assertEqual(channel_ari.diff_cells({"rt9": {day(1): {"availability": 3}}}, sent),
		                 {"rt9": {day(1): {"availability": 3}}})

	def test_a_season_prices_both_plans_of_its_room_type(self):
		from kamra import channel_ari
		self.season(self.double, 3, value=150, kind="Absolute")
		cells = channel_ari.restriction_cells(self.conn, day(2), day(4))
		self.assertEqual(cells["rp-double-bar"][day(3)]["rate"], Decimal("150.00"))
		self.assertEqual(cells["rp-double-bb"][day(3)]["rate"], Decimal("170.00"))
		self.assertEqual(cells["rp-double-bar"][day(2)], {"rate": Decimal("120.00"), "stop_sell": False})
		self.assertEqual(cells["rp-twin-bb"][day(3)]["rate"], Decimal("120.00"))
		self.assertEqual(sorted(cells), ["rp-double-bar", "rp-double-bb", "rp-twin-bar", "rp-twin-bb"])

	def test_a_day_without_a_price_stops_sale_and_sends_no_rate(self):
		from kamra import channel_ari
		with patch("kamra.pricing.quote", side_effect=frappe.ValidationError("closed")):
			cells = channel_ari.restriction_cells(self.conn, day(1), day(1))
		self.assertEqual(cells["rp-twin-bar"][day(1)], {"stop_sell": True})

	def test_availability_counts_a_booking_once_per_room_type(self):
		from kamra import channel_ari
		self.book(self.twin, 2)
		cells = channel_ari.availability_cells(self.conn, day(1), day(3))
		self.assertEqual(sorted(cells), ["rt-double", "rt-twin"])
		self.assertEqual({d: v["availability"] for d, v in cells["rt-twin"].items()},
		                 {day(1): 8, day(2): 7, day(3): 8})
		self.assertEqual(cells["rt-double"][day(2)], {"availability": 4})

	def test_two_mappings_cannot_share_a_provider_rate_id(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc({"doctype": "Channel Room Mapping", "connection": self.conn.name,
				"room_type": self.double, "external_room_id": "rt-double",
				"external_rate_id": "rp-twin-bar"}).insert(ignore_permissions=True)


class _AriWorkerMixin(_AriFixture):
	"""The fixture, with the clock patched for the whole test and what the
	fixture queued already 'sent': Channel ARI State holds today..+40, so a
	test sees only the calls its own change causes."""

	BASELINE_DAYS = 41

	def setUp(self):
		super().setUp()
		from kamra import channel_ari
		self.ari = channel_ari
		clock = patch("kamra.channel_ari._now", side_effect=lambda: self.clock[0])
		clock.start()
		self.addCleanup(clock.stop)
		self.baseline(self.BASELINE_DAYS)

	def baseline(self, days: int):
		frappe.db.delete("Channel ARI Outbox", {"connection": self.conn.name})
		end = day(days - 1)
		self.ari._remember(self.conn.name, "availability",
		                   self.ari.availability_cells(self.conn, day(0), end))
		self.ari._remember(self.conn.name, "restrictions",
		                   self.ari.restriction_cells(self.conn, day(0), end))

	def tick(self, seconds: float):
		self.clock[0] += seconds

	def flush(self) -> dict:
		"""One flush_outbox pass as the worker runs it, against FakeChannex.
		Each commit is a savepoint; a bare rollback goes back to the last one."""
		state = {"sp": "ari_" + frappe.generate_hash(length=8)}
		frappe.db.savepoint(state["sp"])
		rollback = frappe.db.rollback

		def worker_commit(*args, **kwargs):
			state["sp"] = "ari_" + frappe.generate_hash(length=8)
			frappe.db.savepoint(state["sp"])

		def worker_rollback(*args, **kwargs):
			if args or kwargs:
				return rollback(*args, **kwargs)
			return rollback(save_point=state["sp"])

		with patch.object(frappe.db, "commit", side_effect=worker_commit), \
		     patch.object(frappe.db, "rollback", side_effect=worker_rollback), \
		     patch.object(channex, "_send", side_effect=self.fake):
			return self.ari.flush_outbox(self.conn.name)

	def sent(self, kind: str, ext_id: str) -> dict:
		name = f"{self.conn.name}|{kind}|{ext_id}"
		raw = frappe.db.get_value("Channel ARI State", name, "sent_values")
		return json.loads(raw or "{}")

	def rows(self, **filters) -> list:
		return frappe.get_all("Channel ARI Outbox", filters=dict(connection=self.conn.name, **filters),
		                      fields=["name", "status", "attempts", "next_attempt_at", "detail",
		                              "date_from", "date_to", "kinds", "reason", "task_ids"],
		                      order_by="creation asc")

	def error_logs(self, title: str) -> int:
		return frappe.db.count("Error Log", {"method": title})


class ChannexAriFlushTestCase(_AriWorkerMixin, IntegrationTestCase):
	def test_cert_02_single_date_single_rate(self):
		"""Case 2: one rate, one day, one plan, set in the UI -> the call goes
		out alone: 1 POST restrictions with that day (Twin's BAR and BB), no
		availability."""
		self.season(self.twin, 5, value=150)
		out = self.flush()
		self.assertEqual(self.fake.posts("availability"), [])
		self.assertEqual(self.fake.posts("restrictions"), [[
			{"property_id": "cx-test", "rate_plan_id": "rp-twin-bar", "date": day(5), "rate": "150.00"},
			{"property_id": "cx-test", "rate_plan_id": "rp-twin-bb", "date": day(5), "rate": "170.00"}]])
		self.assertEqual(out["restrictions"]["sent"], 2)
		self.assertEqual({r.status for r in self.rows()}, {"Sent"})
		self.assertEqual(self.rows()[0].task_ids, "task-1")
		self.assertEqual(self.sent("restrictions", "rp-twin-bb")[day(5)]["rate"], "170.00")
		self.assertTrue(frappe.db.get_value("Channel Manager Connection", self.conn.name,
		                                    "last_push_status").startswith("OK"))

	def test_cert_03_three_rates_one_call(self):
		"""Case 3: three rates on different days and room types, saved within
		20 s, with a 30 s batch window -> 1 call carrying the three days."""
		self.conn.db_set("ari_batch_seconds", 30)
		self.season(self.twin, 3)
		self.tick(10)
		self.season(self.double, 8)
		self.tick(10)
		self.season(self.twin, 12)
		self.tick(5)
		out = self.flush()
		self.assertIn("waiting", out["restrictions"])
		self.assertEqual(self.fake.calls, [])
		self.tick(6)
		self.flush()
		posts = self.fake.posts("restrictions")
		self.assertEqual(len(posts), 1)
		self.assertEqual(sorted((v["rate_plan_id"], v["date"]) for v in posts[0]), sorted([
			("rp-twin-bar", day(3)), ("rp-twin-bb", day(3)), ("rp-double-bar", day(8)),
			("rp-double-bb", day(8)), ("rp-twin-bar", day(12)), ("rp-twin-bb", day(12))]))

	def test_cert_04_ranges_one_call(self):
		"""Case 4: three ranges (10, 7 and 20 days) on several plans -> 1 call
		of range changes (BAR and BB of each), none of a single day."""
		self.season(self.twin, 2, 11, value=241)
		self.season(self.double, 5, 11, value=312.66)
		self.season(self.double, 15, 34, value=111)
		self.flush()
		posts = self.fake.posts("restrictions")
		self.assertEqual(len(posts), 1)
		self.assertTrue(all("date_from" in v and "date" not in v for v in posts[0]), posts[0])
		self.assertEqual(sorted((v["rate_plan_id"], v["date_from"], v["date_to"], v["rate"]) for v in posts[0]),
		                 sorted([("rp-twin-bar", day(2), day(11), "241.00"), ("rp-twin-bb", day(2), day(11), "261.00"),
		                         ("rp-double-bar", day(5), day(11), "312.66"),
		                         ("rp-double-bb", day(5), day(11), "332.66"),
		                         ("rp-double-bar", day(15), day(34), "111.00"),
		                         ("rp-double-bb", day(15), day(34), "131.00")]))

	def test_cert_09_booking_lowers_availability(self):
		"""Case 9: a booking on Twin one day and another on Double another day
		-> at most 2 POST availability in all, with 7 and 3 on those days."""
		self.book(self.twin, 4)
		self.book(self.double, 9)
		self.flush()
		posts = self.fake.posts("availability")
		self.assertLessEqual(len(posts), 2)
		values = [v for call in posts for v in call]
		self.assertEqual(sorted((v["room_type_id"], v["date"], v["availability"]) for v in values),
		                 [("rt-double", day(9), 3), ("rt-twin", day(4), 7)])

	def test_cert_10_availability_ranges(self):
		"""Case 10: availability by ranges (rooms out for 7 and 8 nights) -> 1
		POST availability with 2 ranges."""
		for rt, start, nights in ((self.twin, 3, 7), (self.double, 12, 8)):
			room = frappe.get_all("Room", filters={"room_type": rt}, pluck="name", limit=1)[0]
			frappe.get_doc({"doctype": "Room Block", "property": self.property, "room": room,
				"reason": "Maintenance", "from_date": day(start),
				"to_date": day(start + nights)}).insert(ignore_permissions=True)
		self.flush()
		self.assertEqual(self.fake.posts("availability"), [[
			{"property_id": "cx-test", "room_type_id": "rt-double", "date_from": day(12), "date_to": day(19),
			 "availability": 3},
			{"property_id": "cx-test", "room_type_id": "rt-twin", "date_from": day(3), "date_to": day(9),
			 "availability": 7}]])

	def test_what_was_sent_is_not_sent_again(self):
		self.season(self.twin, 5)
		self.flush()
		calls = len(self.fake.calls)
		self.ari.enqueue_ari_change(self.property, day(0), day(30), reason="test")
		out = self.flush()
		self.assertEqual(len(self.fake.calls), calls)
		self.assertEqual(out["restrictions"]["sent"], 0)
		self.assertEqual({r.status for r in self.rows()}, {"Sent"})

	def test_cert_12_rate_limit(self):
		"""Case 12: no bombarding the API. 25 one-day rates saved in the same
		minute, a flush after each -> at most 10 POST restrictions (Channex
		allows 10 a minute per endpoint); 61 s later one flush sends all that
		was left in 1 call, and the record holds the 25 days."""
		for n in range(1, 26):
			self.season(self.twin, n, value=150 + n % 2)
			self.flush()
		self.assertLessEqual(len(self.fake.posts("restrictions")), 10)
		self.tick(61)
		before = len(self.fake.posts("restrictions"))
		self.flush()
		self.assertEqual(len(self.fake.posts("restrictions")), before + 1)
		self.assertEqual(self.rows(status="Pending"), [])
		sent = self.sent("restrictions", "rp-twin-bar")
		self.assertEqual({d: sent[d]["rate"] for d in map(day, range(1, 26))},
		                 {day(n): f"{150 + n % 2}.00" for n in range(1, 26)})

	def test_a_429_pauses_that_endpoint_only(self):
		self.fake.fail("restrictions", channex.ChannexRateLimited(429, "slow down", 30))
		self.season(self.twin, 5)
		out = self.flush()
		self.assertEqual(out["restrictions"], {"paused": 30})
		self.assertEqual(self.rows(status="Pending")[0].kinds, "restrictions")
		self.book(self.twin, 6)
		self.tick(29)
		self.flush()
		self.assertEqual(len(self.fake.posts("restrictions")), 1)  # the 429 itself
		self.assertEqual(len(self.fake.posts("availability")), 1)  # not paused
		self.assertIsNone(frappe.cache.get_value(f"channex_pause::{self.conn.name}"))
		self.tick(2)
		self.flush()
		self.assertEqual(len(self.fake.posts("restrictions")), 2)
		self.assertEqual(self.rows(status="Pending"), [])

	def test_a_ratelimit_header_at_zero_holds_the_next_call(self):
		self.fake.headers = {"ratelimit": '"ari";r=0;t=40'}
		self.season(self.twin, 5)
		self.flush()
		self.fake.headers = {}
		self.season(self.twin, 6)
		self.tick(20)
		self.assertIn("waiting", self.flush()["restrictions"])
		self.tick(21)
		self.flush()
		self.assertEqual(len(self.fake.posts("restrictions")), 2)

	def test_5xx_backs_off_then_sends(self):
		self.fake.fail("restrictions", channex.ChannexError(500, "boom"), times=2)
		self.season(self.twin, 5)
		t0 = self.clock[0]
		self.flush()
		row = self.rows()[0]
		self.assertEqual((row.status, row.attempts), ("Pending", 1))
		self.assertEqual(frappe.utils.get_datetime(row.next_attempt_at), self.ari._dt(t0 + 30))
		self.flush()  # not due yet: no call
		self.assertEqual(len(self.fake.posts("restrictions")), 1)
		self.tick(30)
		self.flush()
		row = self.rows()[0]
		self.assertEqual(row.attempts, 2)
		self.assertEqual(frappe.utils.get_datetime(row.next_attempt_at), self.ari._dt(t0 + 90))
		self.tick(60)
		self.flush()
		self.assertEqual(self.rows()[0].status, "Sent")
		self.assertEqual(self.error_logs(f"Channex ARI {self.conn.name}"), 1)

	def test_a_4xx_fails_the_rows(self):
		self.fake.fail("restrictions", channex.ChannexError(422, "{'details': {'rate': ['invalid']}}"))
		self.season(self.twin, 5)
		self.flush()
		row = self.rows()[0]
		self.assertEqual(row.status, "Failed")
		self.assertIn("422", row.detail)
		self.assertTrue(frappe.db.get_value("Channel Manager Connection", self.conn.name,
		                                    "last_push_status").startswith("FAILED"))
		self.assertEqual(self.sent("restrictions", "rp-twin-bar")[day(5)]["rate"], "100.00")

	def test_a_rejected_value_is_not_recorded(self):
		def reject_bb(path, payload):
			return [dict(v, warning={"rate": ["is invalid"]}) for v in payload["values"]
			        if v.get("rate_plan_id") == "rp-twin-bb"]
		self.fake.warn_fn = reject_bb
		self.season(self.twin, 5)
		self.flush()
		self.assertEqual(self.sent("restrictions", "rp-twin-bar")[day(5)]["rate"], "150.00")
		self.assertEqual(self.sent("restrictions", "rp-twin-bb")[day(5)]["rate"], "120.00")
		self.assertIn("rp-twin-bb", self.rows()[0].detail)
		self.assertEqual(self.error_logs(f"Channex ARI rejected {self.conn.name}"), 1)

	def test_a_rolled_back_change_leaves_no_row(self):
		before = len(self.rows())
		frappe.db.savepoint("ari_rb")
		self.season(self.twin, 5)
		self.assertEqual(len(self.rows()), before + 1)
		frappe.db.rollback(save_point="ari_rb")
		self.assertEqual(len(self.rows()), before)


class ChannexAriClaimTestCase(_AriWorkerMixin, IntegrationTestCase):
	"""The worker claims its rows before it computes the cells: a change saved
	while the call is on the wire gets a row of its own and goes out next."""

	def change_during(self, season, value, path="restrictions"):
		"""warn_fn: the revenue manager saves `season` at `value` while the
		worker's `path` call is on the wire (once)."""
		state = {"done": False}

		def during(p, payload):
			if p == path and not state["done"]:
				state["done"] = True
				doc = frappe.get_doc("Season", season.name)
				doc.adjustment_value = value
				doc.save(ignore_permissions=True)
			return None
		return during

	def rates(self, plan="rp-twin-bar") -> list:
		return [v.get("rate") for call in self.fake.posts("restrictions") for v in call
		        if v.get("rate_plan_id") == plan]

	def test_a_change_saved_during_the_call_is_not_lost(self):
		season = self.season(self.twin, 5, value=150)
		self.fake.warn_fn = self.change_during(season, 160)
		self.flush()
		self.fake.warn_fn = None
		pending = self.rows(status="Pending")
		self.assertEqual(len(pending), 1, f"rows after the 1st flush: {self.rows()}")
		self.assertEqual(self.rows(status="Sending"), [])
		self.tick(120)
		self.flush()
		self.assertEqual(self.rates(), ["150.00", "160.00"])
		self.assertEqual(self.sent("restrictions", "rp-twin-bar")[day(5)]["rate"], "160.00")
		self.assertEqual({r.status for r in self.rows()}, {"Sent"})

	def test_a_5xx_gives_the_claimed_rows_back_with_their_wait_and_no_copies(self):
		self.fake.fail("restrictions", channex.ChannexError(500, "boom"))
		season = self.season(self.twin, 5, value=150)
		before = [r.name for r in self.rows()]
		t0 = self.clock[0]
		self.assertIn("retry", self.flush()["restrictions"])
		rows = self.rows()
		self.assertEqual([r.name for r in rows], before)
		self.assertEqual([(r.status, r.attempts) for r in rows], [("Pending", 1)])
		self.assertEqual(frappe.utils.get_datetime(rows[0].next_attempt_at), self.ari._dt(t0 + 30))
		# a change saved during the retried call joins nothing: it waits in its own row
		self.tick(30)
		self.fake.warn_fn = self.change_during(season, 160)
		self.flush()
		self.fake.warn_fn = None
		self.assertEqual(len(self.rows(status="Pending")), 1)
		self.tick(120)
		self.flush()
		self.assertEqual(self.rates(), ["150.00", "150.00", "160.00"])
		self.assertEqual({r.status for r in self.rows()}, {"Sent"})

	def test_a_429_gives_the_claimed_rows_back_with_the_pause_and_no_copies(self):
		self.fake.fail("restrictions", channex.ChannexRateLimited(429, "slow down", 30))
		self.season(self.twin, 5)
		before = [r.name for r in self.rows()]
		self.assertEqual(self.flush()["restrictions"], {"paused": 30})
		rows = self.rows()
		self.assertEqual([r.name for r in rows], before)
		self.assertEqual([(r.status, r.kinds, r.attempts) for r in rows], [("Pending", "restrictions", 0)])
		self.tick(31)
		self.flush()
		self.assertEqual(self.rates(), ["150.00", "150.00"])
		self.assertEqual({r.status for r in self.rows()}, {"Sent"})

	def test_a_waiting_kind_gives_its_rows_back_untouched(self):
		frappe.db.set_value("Channel Manager Connection", self.conn.name, "ari_batch_seconds", 60)
		self.season(self.twin, 5)
		self.assertIn("waiting", self.flush()["restrictions"])
		rows = self.rows()
		self.assertEqual([(r.status, r.attempts, r.next_attempt_at) for r in rows], [("Pending", 0, None)])
		self.tick(61)
		self.flush()
		self.assertEqual({r.status for r in self.rows()}, {"Sent"})

	def test_an_unexpected_error_gives_the_claimed_rows_back(self):
		self.season(self.twin, 5)
		with patch.object(self.ari, "restriction_cells", side_effect=RuntimeError("bug")):
			with self.assertRaises(RuntimeError):
				self.flush()
		self.assertEqual([(r.status, r.next_attempt_at) for r in self.rows()], [("Pending", None)])
		self.flush()
		self.assertEqual({r.status for r in self.rows()}, {"Sent"})

	def test_a_row_another_worker_holds_is_left_alone_until_its_claim_lapses(self):
		self.season(self.twin, 5)
		name = self.rows()[0].name
		frappe.db.set_value("Channel ARI Outbox", name, {
			"status": "Sending", "next_attempt_at": self.ari._dt(self.clock[0] + 60)})
		self.assertEqual(self.flush()["restrictions"], {"nothing": True})
		self.assertEqual(self.fake.posts("restrictions"), [])
		self.assertEqual(self.ari.outbox_status(self.conn.name)["pending"], 1)
		with patch.object(self.ari, "enqueue_flush") as enqueue:
			self.ari.enqueue_ari_flushes()
		self.assertIn(self.conn.name, [c.args[0] for c in enqueue.call_args_list])
		# the worker died mid-call: once its claim lapses the row is taken again
		self.tick(61)
		self.flush()
		self.assertEqual(self.rates(), ["150.00"])
		self.assertEqual(self.rows()[0].status, "Sent")

	def test_a_change_never_joins_a_row_another_transaction_queued(self):
		# a Pending row another request committed: the worker may be claiming it
		# right now, unseen by this transaction's snapshot
		other = self.ari._insert_row({"connection": self.conn.name, "property": self.property,
			"status": "Pending", "kinds": "both", "full": 0, "date_from": day(5), "date_to": day(5),
			"attempts": 0, "queued_at": self.ari._dt(self.clock[0])})
		mine = self.ari.enqueue_ari_change(self.property, day(5), day(5), reason="test")
		self.assertTrue(mine and other not in mine, (other, mine))
		# the same change twice in one transaction is still one row
		self.assertEqual(self.ari.enqueue_ari_change(self.property, day(5), day(5), reason="test"), mine)


class ChannexAriTriggersTestCase(_AriWorkerMixin, IntegrationTestCase):
	BASELINE_DAYS = 0

	@staticmethod
	def priced(property, room_type, rate_plan, d):
		"""A deterministic price per day (the real quote, 2000 times, would be
		slow): it varies by weekday and by plan like a real hotel's."""
		n = (getdate(d) - getdate(nowdate())).days
		return Decimal(100 + 7 * (n % 7) + (20 if rate_plan else 0) + (30 if "DBL" in room_type else 0))

	def test_cert_01_full_sync_two_calls_500_days(self):
		"""Case 1: Full Sync - 500 days of availability, rates and
		restrictions, every room type and plan, in 2 calls (1 availability,
		1 rates/restrictions), with varied values like a real hotel."""
		from kamra.channel_ari import request_full_sync
		self.season(self.twin, 30, 40, value=180)
		frappe.get_doc({"doctype": "Hurdle Rate", "property": self.property, "room_type": self.double,
			"occupancy_from": 50, "premium_pct": 10}).insert(ignore_permissions=True)
		self.book(self.twin, 3, nights=4)
		with patch("kamra.channel_ari._plan_night_rate", side_effect=self.priced):
			self.assertEqual(request_full_sync(self.conn.name), {"queued": True})
			self.flush()
		self.assertEqual([c[1] for c in self.fake.calls], ["availability", "restrictions"])
		for kind, ids in (("availability", {"rt-twin", "rt-double"}),
		                  ("restrictions", {"rp-twin-bar", "rp-twin-bb", "rp-double-bar", "rp-double-bb"})):
			values = self.fake.posts(kind)[0]
			id_field = "room_type_id" if kind == "availability" else "rate_plan_id"
			self.assertEqual({v[id_field] for v in values}, ids)
			self.assertEqual(min(v.get("date") or v["date_from"] for v in values), day(0))
			self.assertEqual(max(v.get("date") or v["date_to"] for v in values), day(499))
		rates = {v["rate"] for v in self.fake.posts("restrictions")[0] if "rate" in v}
		self.assertGreater(len(rates), 10)
		self.assertIn({"property_id": "cx-test", "room_type_id": "rt-twin", "date_from": day(3),
		               "date_to": day(6), "availability": 7}, self.fake.posts("availability")[0])
		self.assertTrue(frappe.db.get_value("Channel Manager Connection", self.conn.name, "last_full_sync"))

	def test_a_second_full_sync_within_24h_asks_first(self):
		from kamra.channel_ari import request_full_sync
		with patch("kamra.channel_ari._plan_night_rate", side_effect=self.priced):
			self.assertEqual(request_full_sync(self.conn.name), {"queued": True})
			self.flush()
		again = request_full_sync(self.conn.name)
		self.assertTrue(again["needs_confirm"])
		self.assertTrue(again["last_full_sync"])
		self.assertEqual([r.status for r in self.rows(full=1)], ["Sent"])
		self.assertEqual(request_full_sync(self.conn.name, confirm=1), {"queued": True})
		self.assertEqual([r.status for r in self.rows(full=1)], ["Sent", "Pending"])
		# confirmed again before the worker runs: still the one row waiting
		self.assertEqual(request_full_sync(self.conn.name, confirm=1), {"queued": True})
		self.assertEqual([r.status for r in self.rows(full=1)], ["Sent", "Pending"])

	def test_cert_13_no_timer_full_sync(self):
		"""Case 13: only changes - no full sync on a timer. No scheduled job
		sends one for Channex (the hourly push_all_ari skips the outbox
		connection); the nightly sweep sends nothing when nothing changed and
		only the day that just entered the horizon otherwise."""
		from kamra import channel_manager as cm
		from kamra import hooks
		cron = hooks.scheduler_events["cron"]
		jobs = [m for methods in cron.values() for m in methods]
		self.assertNotIn("kamra.channel_ari.request_full_sync", jobs)
		self.assertIn("kamra.channel_ari.enqueue_ari_flushes", cron["* * * * *"])
		self.assertEqual([k for k, v in cron.items() if "kamra.channel_ari.nightly_sweep" in v], ["20 6 * * *"])
		adapter = MagicMock()
		with patch.object(cm, "provider_for", return_value=adapter):
			cm.push_all_ari(self.property)
		adapter.push_ari.assert_not_called()

		with patch("kamra.channel_ari._plan_night_rate", side_effect=self.priced):
			self.baseline(self.ari.ARI_HORIZON_DAYS)
			old = frappe.get_doc({"doctype": "Channel ARI Outbox", "connection": self.conn.name,
				"property": self.property, "status": "Sent", "reason": "old",
				"sent_at": frappe.utils.add_days(frappe.utils.now_datetime(), -31)}).insert(ignore_permissions=True)
			self.ari.nightly_sweep()
			self.assertFalse(frappe.db.exists("Channel ARI Outbox", old.name))
			self.flush()
			self.assertEqual(self.fake.calls, [])
			# tomorrow: day 499 was never sent, the rest is known
			for kind, ext_id in (("availability", "rt-twin"), ("restrictions", "rp-double-bb")):
				name = f"{self.conn.name}|{kind}|{ext_id}"
				known = json.loads(frappe.db.get_value("Channel ARI State", name, "sent_values"))
				known.pop(day(499))
				frappe.db.set_value("Channel ARI State", name, "sent_values", json.dumps(known))
			self.ari.nightly_sweep()
			self.flush()
		self.assertEqual(self.fake.posts("availability"), [[{"property_id": "cx-test", "room_type_id": "rt-twin",
			"date": day(499), "availability": 8}]])
		self.assertEqual([(v["rate_plan_id"], v["date"]) for v in self.fake.posts("restrictions")[0]],
		                 [("rp-double-bb", day(499))])

	def test_room_status_only_counts_out_of_order(self):
		room = frappe.get_doc("Room", frappe.get_all("Room", filters={"room_type": self.twin}, pluck="name")[0])
		room.housekeeping_status = "Dirty"
		room.save(ignore_permissions=True)
		frappe.db.delete("Channel ARI Outbox", {"connection": self.conn.name})
		room.housekeeping_status = "Clean"
		room.save(ignore_permissions=True)
		self.assertEqual(self.rows(), [])
		room.housekeeping_status = "Out of Order"
		room.save(ignore_permissions=True)
		self.assertEqual([r.kinds for r in self.rows()], ["availability"])

	def test_a_moved_booking_covers_the_old_and_new_dates(self):
		res = self.book(self.twin, 10)
		frappe.db.delete("Channel ARI Outbox", {"connection": self.conn.name})
		res.reload()
		res.check_in_date, res.check_out_date = day(20), day(21)
		res.save(ignore_permissions=True)
		row = self.rows()[0]
		self.assertEqual((str(row.date_from), str(row.date_to), row.kinds), (day(10), day(20), "both"))
		self.assertIn(res.name, row.reason)

	def test_a_failing_outbox_never_blocks_the_save(self):
		with patch("kamra.channel_ari._insert_row", side_effect=RuntimeError("outbox down")):
			season = self.season(self.twin, 5)
		self.assertTrue(frappe.db.exists("Season", season.name))
		self.assertEqual(self.error_logs("Channex ARI enqueue"), 1)

	def test_deleting_a_mapping_forgets_what_it_sent(self):
		self.baseline(3)
		name = f"{self.conn.name}|restrictions|rp-double-bb"
		self.assertTrue(frappe.db.exists("Channel ARI State", name))
		mapping = frappe.db.get_value("Channel Room Mapping", {"external_rate_id": "rp-double-bb",
		                              "connection": self.conn.name})
		frappe.delete_doc("Channel Room Mapping", mapping, ignore_permissions=True)
		self.assertFalse(frappe.db.exists("Channel ARI State", name))
		self.assertTrue(frappe.db.exists("Channel ARI State", f"{self.conn.name}|availability|rt-double"))
		self.assertEqual(self.rows()[-1].kinds, "both")

	def test_outbox_status(self):
		self.season(self.twin, 5)
		status = self.ari.outbox_status(self.conn.name)
		self.assertEqual((status["pending"], status["failed"]), (1, 0))
		self.assertEqual(status["paused"], {})
		self.assertIs(status["outbox"], True)
		frappe.db.set_value("Channel Manager Connection", self.conn.name, "provider", "AioSell")
		self.assertIs(self.ari.outbox_status(self.conn.name)["outbox"], False)


class ChannexAriImportTestCase(_AriFixture, IntegrationTestCase):
	"""The mapping import, one mapping per Channex rate plan."""

	def setUp(self):
		super().setUp()
		frappe.db.delete("Channel Room Mapping", {"connection": self.conn.name})
		frappe.db.set_value("Property", self.property, "timezone", "America/Guayaquil")
		bb_code = frappe.db.get_value("Rate Plan", self.bb, "code")
		self.fake.room_types = [
			{"type": "room_type", "id": "rt-twin", "attributes": {"title": "Twin", "count_of_rooms": 8}},
			{"type": "room_type", "id": "rt-double", "attributes": {"title": "Double", "count_of_rooms": 4}}]
		self.fake.rate_plans = [self._plan(i, title, room) for i, (title, room) in enumerate([
			("Best Available Rate", "rt-twin"), ("Bed and Breakfast", "rt-twin"),
			("BAR", "rt-double"), (bb_code, "rt-double")])]

	@staticmethod
	def _plan(i, title, room, sell_mode="per_room"):
		ids = ["rp-twin-bar", "rp-twin-bb", "rp-double-bar", "rp-double-bb"]
		return {"type": "rate_plan", "id": ids[i] if i < 4 else f"rp-{i}", "attributes": {
			"title": title, "sell_mode": sell_mode, "currency": "USD"},
			"relationships": {"room_type": {"data": {"type": "room_type", "id": room}}}}

	def run_import(self, dry_run=0) -> dict:
		from kamra import channel_manager as cm
		with patch.object(channex, "_send", side_effect=self.fake):
			return cm.import_room_mappings(self.conn.name, dry_run=dry_run)

	def mapped(self) -> dict:
		return {m.external_rate_id: (m.room_type, m.external_room_id, m.rate_plan) for m in frappe.get_all(
			"Channel Room Mapping", filters={"connection": self.conn.name},
			fields=["external_rate_id", "room_type", "external_room_id", "rate_plan"])}

	def test_one_mapping_per_channex_rate_plan(self):
		out = self.run_import()
		self.assertEqual(len(out["created"]), 4)
		self.assertEqual(out["unmatched"], [])
		self.assertEqual(self.mapped(), {
			"rp-twin-bar": (self.twin, "rt-twin", None), "rp-twin-bb": (self.twin, "rt-twin", self.bb),
			"rp-double-bar": (self.double, "rt-double", None), "rp-double-bb": (self.double, "rt-double", self.bb)})

	def test_dry_run_writes_nothing(self):
		out = self.run_import(dry_run=1)
		self.assertEqual(len(out["created"]), 4)
		self.assertEqual(self.mapped(), {})

	def test_importing_again_updates_and_does_not_duplicate(self):
		self.run_import()
		out = self.run_import()
		self.assertEqual((len(out["created"]), len(out["updated"])), (0, 4))
		self.assertEqual(len(self.mapped()), 4)

	def test_the_five_warnings(self):
		self.fake.property.update(currency="EUR", timezone="Europe/Madrid")
		self.fake.room_types[0]["attributes"]["count_of_rooms"] = 9
		self.fake.rate_plans[2] = self._plan(2, "BAR", "rt-double", sell_mode="per_person")
		codes = [w["code"] for w in self.run_import()["warnings"]]
		self.assertEqual(sorted(codes), ["count_of_rooms", "currency", "fixed_amount", "per_person", "timezone"])
		frappe.db.set_value("Rate Plan", self.bb, "modifier_type", "Percent")
		self.fake.property.update(currency="USD", timezone="America/Guayaquil")
		self.fake.room_types[0]["attributes"]["count_of_rooms"] = 8
		self.fake.rate_plans[2] = self._plan(2, "BAR", "rt-double")
		self.assertEqual(self.run_import()["warnings"], [])

	def test_two_loose_plans_of_a_room_go_to_unmatched(self):
		self.fake.rate_plans.append(self._plan(7, "Non Refundable", "rt-twin"))
		out = self.run_import()
		self.assertEqual(sorted(u["rateplan_id"] for u in out["unmatched"]), ["rp-7", "rp-twin-bar"])
		self.assertNotIn("rp-twin-bar", self.mapped())
