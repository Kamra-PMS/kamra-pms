"""Kamra eval harness — deterministic checks over the governed tool layer.

The PRD's risk register calls for an eval harness before agents go live:
every rule an agent relies on (pricing, availability, guardrails, SLA)
gets a check here. Runs in a transaction and rolls back — no data left
behind.

Run via bench console:
    from kamra.scripts.eval_harness import execute; execute()
"""

import json

import frappe
from frappe.utils import add_days, get_datetime, getdate, nowdate

P = "EVAL Hotel"
RESULTS = []


def check(name):
	def wrap(fn):
		def run():
			# Isolate each check: an OperationalError aborts the MySQL
			# transaction and would poison later tests without a rollback.
			sp = f"eval_{frappe.generate_hash(length=8)}"
			frappe.db.savepoint(sp)
			try:
				fn()
				RESULTS.append((name, True, ""))
			except AssertionError as e:
				frappe.db.rollback(save_point=sp)
				RESULTS.append((name, False, str(e)))
			except Exception as e:
				frappe.db.rollback(save_point=sp)
				import traceback
				tail = " | ".join(
					line.strip()
					for line in traceback.format_exc().splitlines()[-6:]
				)
				RESULTS.append((name, False, f"{type(e).__name__}: {e} [{tail}]"))
		run.__name__ = name
		return run
	return wrap


def setup():
	# the governed agent user posts public/HK/laundry charges. Created the
	# way a real site gets it (install / migrate hook), so a site missing it
	# fails here exactly as it does in production.
	from kamra.install import ensure_agent_identity
	ensure_agent_identity()
	# the persona users the role-gate checks act as. seed_users.py is a demo
	# script CI never runs, so relying on it left these users absent: set_user
	# to a missing user yields no roles, which turns every "role X may not do
	# Y" check into a pass for the wrong reason.
	for email, first, role in (
		("frontdesk@kamra.local", "Ravi", "Front Desk"),
		("hk@kamra.local", "Lakshmi", "Housekeeping"),
	):
		if not frappe.db.exists("User", email):
			frappe.get_doc({
				"doctype": "User", "email": email, "first_name": first,
				"enabled": 1, "user_type": "System User",
				"send_welcome_email": 0, "roles": [{"role": role}],
			}).insert(ignore_permissions=True)
	if not frappe.db.exists("Property", P):
		frappe.get_doc({
			"doctype": "Property", "property_name": P, "city": "Testville",
			"gst_mode": "Slab", "gst_slab_threshold": 7500,
			"gst_rate_low": 5, "gst_rate_high": 18,
		}).insert(ignore_permissions=True)
	# a demo-seeded site pins these personas to its demo hotel; property
	# scope is enforced now, so give them the eval property too (rolled
	# back with everything else)
	for email in ("frontdesk@kamra.local", "hk@kamra.local"):
		if frappe.db.exists("User Permission", {"user": email, "allow": "Property"}) \
				and not frappe.db.exists("User Permission", {
					"user": email, "allow": "Property", "for_value": P}):
			frappe.get_doc({"doctype": "User Permission", "user": email,
			                "allow": "Property", "for_value": P,
			                }).insert(ignore_permissions=True)
	# many tests intentionally stack same-day stays on this tiny property;
	# a generous allowance keeps them off the type-capacity guard (t32
	# asserts that guard on its own isolated property)
	frappe.db.set_value("Property", P, "overbooking_pct", 400)
	rt = frappe.get_doc({
		"doctype": "Room Type", "property": P, "room_type_code": "EVL",
		"room_type_name": "Eval Room", "base_price": 4000,
		"base_occupancy": 2, "single_occupancy_price": 3200,
		"extra_adult_price": 1000, "child_price": 500,
		"free_child_age": 5, "child_age_limit": 11,
		"adults_capacity": 3, "children_capacity": 2, "tax_percent": 5,
	}).insert(ignore_permissions=True)
	room = frappe.get_doc({
		"doctype": "Room", "property": P, "room_number": "E101",
		"room_type": rt.name,
	}).insert(ignore_permissions=True)
	frappe.get_doc({
		"doctype": "Season", "property": P, "season_name": "EVAL Peak",
		"start_date": "2030-01-10", "end_date": "2030-01-12",
		"adjustment_type": "Percent", "adjustment_value": 100, "priority": 5,
	}).insert(ignore_permissions=True)
	frappe.get_doc({
		"doctype": "Discount Voucher", "property": P, "voucher_code": "EVAL10",
		"discount_type": "Percent", "value": 10, "min_nights": 2,
	}).insert(ignore_permissions=True)
	frappe.get_doc({
		"doctype": "Rate Guardrail", "property": P, "room_type": rt.name,
		"floor_price": 3000, "ceiling_price": 9000,
	}).insert(ignore_permissions=True)
	return rt.name, room.name


RT = ROOM = None


@check("occupancy pricing: 2 adults = base")
def t1():
	from kamra.pricing import quote
	q = quote(P, RT, "2030-02-01", "2030-02-02", 2, 0)
	assert q["room_total"] == 4000, q["room_total"]


@check("occupancy pricing: single rate + extra adult + child")
def t2():
	from kamra.pricing import quote
	assert quote(P, RT, "2030-02-01", "2030-02-02", 1, 0)["room_total"] == 3200
	q = quote(P, RT, "2030-02-01", "2030-02-02", 3, 1)
	assert q["room_total"] == 5500, q["room_total"]  # 4000 + 1000 extra + 500 child


@check("season doubles the rate in range only")
def t3():
	from kamra.pricing import quote
	q = quote(P, RT, "2030-01-11", "2030-01-14", 2, 0)
	rates = [n["rate"] for n in q["nightly"]]
	assert rates == [8000, 8000, 4000], rates


@check("a season only moves the room type it names")
def t3b():
	"""The villa's weekend price must never become the room's weekend
	price. A season naming a room type leaves every other type alone;
	one with the room type blank stays house-wide."""
	from decimal import Decimal

	from kamra.pricing import season_adjust

	villa = frappe.get_doc({
		"doctype": "Room Type", "property": P, "room_type_code": "EVV",
		"room_type_name": "Eval Villa", "base_price": 30000,
		"base_occupancy": 2, "adults_capacity": 4, "children_capacity": 2,
		"tax_percent": 5,
	}).insert(ignore_permissions=True)
	season = frappe.get_doc({
		"doctype": "Season", "property": P, "room_type": villa.name,
		"season_name": "EVAL Villa Weekend",
		"start_date": "2030-03-01", "end_date": "2030-03-31",
		"adjustment_type": "Absolute", "adjustment_value": 36800,
		"priority": 100,
	}).insert(ignore_permissions=True)
	try:
		base = Decimal(4000)
		priced = season_adjust(P, "2030-03-05", base, villa.name)
		assert priced == 36800, priced
		# the regression: the villa's season must not price the room
		leaked = season_adjust(P, "2030-03-05", base, RT)
		assert leaked == base, leaked
		# nor a caller that names no room type at all
		blanket = season_adjust(P, "2030-03-05", base)
		assert blanket == base, blanket
	finally:
		frappe.delete_doc("Season", season.name, force=True,
		                  ignore_permissions=True)
		frappe.delete_doc("Room Type", villa.name, force=True,
		                  ignore_permissions=True)


@check("small-group pricing is per head, and only on its own days")
def t3c():
	"""A whole-place let prices a small midweek party per head instead of
	charging the full house rate - but the rule is day-scoped, so it must
	never undercut the weekend house rate."""
	from kamra.pricing import occupancy_rate

	villa = frappe.get_doc({
		"doctype": "Room Type", "property": P, "room_type_code": "ESG",
		"room_type_name": "Eval Small Group", "base_price": 20000,
		"base_occupancy": 8, "extra_adult_price": 1600,
		"adults_capacity": 14, "children_capacity": 6,
		"small_group_max_adults": 5,
		"small_group_price_per_adult": 4000,
		"small_group_days": "sun,mon,tue,wed,thu",
	}).insert(ignore_permissions=True)
	try:
		# 2030-03-05 is a Tuesday, 2030-03-08 a Friday
		tue, fri = "2030-03-05", "2030-03-08"
		assert getdate(tue).strftime("%a").lower() == "tue"
		assert getdate(fri).strftime("%a").lower() == "fri"

		# under the threshold, midweek: per head
		assert occupancy_rate(villa, 3, 0, tue) == 12000, "3 pax midweek"
		assert occupancy_rate(villa, 4, 0, tue) == 16000, "4 pax midweek"
		# at the threshold the house rate takes over, and the two meet
		assert occupancy_rate(villa, 5, 0, tue) == 20000, "5 pax midweek"
		assert occupancy_rate(villa, 8, 0, tue) == 20000, "8 pax midweek"
		# beyond base occupancy the extra-adult charge still applies
		assert occupancy_rate(villa, 10, 0, tue) == 23200, "10 pax midweek"
		# the regression this guards: a day the rule excludes keeps the
		# house rate, so a small weekend party is not quoted per head
		assert occupancy_rate(villa, 3, 0, fri) == 20000, "3 pax weekend"
		# and children still price on top of a small-group rate
		villa.child_price = 1200
		assert occupancy_rate(villa, 3, 2, tue) == 14400, "3 pax + 2 children"
	finally:
		frappe.delete_doc("Room Type", villa.name, force=True,
		                  ignore_permissions=True)


@check("rate guardrails can hold a different floor at the weekend")
def t3d():
	"""A property that discounts midweek but holds firm at the weekend needs
	two rails. The day-scoped one wins on its own days; the general one
	covers the rest."""
	from kamra.api import _assert_within_guardrails

	rails = [
		frappe._dict({"name": "GEN", "room_type": RT, "floor_price": 19000,
		    "ceiling_price": 50000, "days_of_week": None}),
		frappe._dict({"name": "WKND", "room_type": RT, "floor_price": 22500,
		    "ceiling_price": 50000, "days_of_week": "fri,sat"}),
	]
	# Tuesday only: the midweek floor applies, 19,000 is allowed
	_assert_within_guardrails(rails, RT, 19000, "2030-03-05", "2030-03-05")
	# Friday only: the weekend rail wins, so 19,000 is refused
	try:
		_assert_within_guardrails(rails, RT, 19000, "2030-03-08", "2030-03-08")
		raise AssertionError("weekend floor did not hold")
	except frappe.ValidationError:
		pass
	# and the weekend floor itself passes
	_assert_within_guardrails(rails, RT, 22500, "2030-03-08", "2030-03-08")


@check("cancellation tiers: free, part-refund and no-refund bands")
def t3f():
	"""Most properties refund on a sliding scale - free a week out, half
	inside that, nothing in the last few days. One window and one fee basis
	cannot express the middle band."""
	from kamra.api import cancellation_tier_for

	prop = frappe.get_doc("Property", P)
	had = list(prop.get("cancellation_tiers") or [])
	prop.set("cancellation_tiers", [])
	for days, pct in ((7, 0), (3, 50), (0, 100)):
		prop.append("cancellation_tiers",
		            {"days_before": days, "charge_pct": pct})
	prop.save(ignore_permissions=True)
	try:
		def pct(d):
			t = cancellation_tier_for(P, d)
			assert t is not None, f"no tier for {d} days"
			return t["charge_pct"]

		assert pct(30) == 0, "a month out should be free"
		assert pct(7) == 0, "exactly seven days is still free"
		assert pct(6) == 50, "six days falls in the half band"
		assert pct(3) == 50, "exactly three days is still half"
		assert pct(2) == 100, "two days out is non-refundable"
		assert pct(0) == 100, "day of arrival is non-refundable"

		# the fee follows the band, not a whole-stay/first-night basis
		from kamra.folio import policy_fee
		res = frappe._dict({"amount_before_tax": 20000})
		assert policy_fee(res, "", pct=50) == 10000.0
		assert policy_fee(res, "", pct=0) == 0.0

		# a property with no tiers keeps the old single-window behaviour
		prop.set("cancellation_tiers", [])
		prop.save(ignore_permissions=True)
		assert cancellation_tier_for(P, 5) is None, "tiers should be off"
	finally:
		prop.reload()
		prop.set("cancellation_tiers", [])
		for row in had:
			prop.append("cancellation_tiers",
			            {"days_before": row.days_before,
			             "charge_pct": row.charge_pct, "label": row.label})
		prop.save(ignore_permissions=True)


@check("children fill the base occupancy when the room type says so")
def t3g():
	"""A whole-place rate buys the house up to its base occupancy. Six adults
	and two children in a house that sleeps eight have already paid for all
	eight beds - charging the children again bills the same beds twice."""
	from kamra.pricing import occupancy_rate

	villa = frappe.get_doc({
		"doctype": "Room Type", "property": P, "room_type_code": "ECH",
		"room_type_name": "Eval Child Villa", "base_price": 22500,
		"base_occupancy": 8, "extra_adult_price": 1600,
		"child_price": 1200, "adults_capacity": 14, "children_capacity": 6,
	}).insert(ignore_permissions=True)
	try:
		# default (flag off): every child is charged, as a per-room rate does
		assert occupancy_rate(villa, 6, 2) == 24900, "6+2 default"
		assert occupancy_rate(villa, 8, 2) == 24900, "8+2 default"

		villa.children_within_base_occupancy = 1
		# the party fits inside the base occupancy, so nothing extra
		assert occupancy_rate(villa, 6, 2) == 22500, "6+2 fits the house"
		assert occupancy_rate(villa, 8, 0) == 22500, "8 adults fill it"
		assert occupancy_rate(villa, 2, 2) == 22500, "a small party pays the house"
		# only the guests beyond base occupancy are charged
		assert occupancy_rate(villa, 8, 2) == 24900, "two children beyond eight"
		assert occupancy_rate(villa, 7, 3) == 24900, "two of three beyond eight"
		# adults beyond base occupancy still carry the adult rate
		assert occupancy_rate(villa, 10, 0) == 25700, "two extra adults"
		assert occupancy_rate(villa, 10, 1) == 26900, "plus one child"

		# with children inside the base occupancy they are guests like any
		# other in the small-group count too: 3 adults + 1 child are four
		# guests at the per-head rate, and 4 + 2 are six, the house rate
		villa.small_group_max_adults = 6
		villa.small_group_price_per_adult = 4000
		assert occupancy_rate(villa, 3, 1) == 16000, "four guests per head"
		assert occupancy_rate(villa, 4, 2) == 22500, "six guests pay the house"
		# flag off: the per-head rate counts adults, and each child is extra
		villa.children_within_base_occupancy = 0
		assert occupancy_rate(villa, 3, 1) == 13200, "per-head plus one child"
	finally:
		frappe.delete_doc("Room Type", villa.name, force=True,
		                  ignore_permissions=True)


@check("peak dates can demand a minimum stay and refuse refunds")
def t3h():
	"""New Year wants two nights and no refunds. That rule belongs on the
	Season that already prices those dates, not in a second calendar."""
	from kamra.pricing import stay_season_rules

	season = frappe.get_doc({
		"doctype": "Season", "property": P, "season_name": "EVAL Peak",
		"start_date": "2030-12-30", "end_date": "2031-01-02",
		"adjustment_type": "Percent", "adjustment_value": 0,
		"minimum_nights": 2, "non_refundable": 1, "priority": 50,
	}).insert(ignore_permissions=True)
	try:
		# a stay touching the peak window inherits its rules
		peak = stay_season_rules(P, "2030-12-31", "2031-01-01")
		assert peak["minimum_nights"] == 2, peak
		assert peak["non_refundable"] is True, peak
		assert peak["season"] == "EVAL Peak", peak

		# a stay that only clips the first night still counts
		edge = stay_season_rules(P, "2030-12-29", "2030-12-31")
		assert edge["minimum_nights"] == 2, edge

		# dates outside the window are untouched
		off = stay_season_rules(P, "2030-06-01", "2030-06-02")
		assert off["minimum_nights"] == 0, off
		assert off["non_refundable"] is False, off

		# and a one-night peak booking is refused
		try:
			frappe.get_doc({
				"doctype": "Reservation", "property": P, "room_type": RT,
				"guest": _guest("Eval Peak", "+91 70000 00031"),
				"check_in_date": "2030-12-31",
				"check_out_date": "2031-01-01", "adults": 2, "children": 0,
				"auto_price": 1, "status": "Confirmed",
			}).insert(ignore_permissions=True)
			raise AssertionError("one night over the peak window was allowed")
		except frappe.ValidationError:
			pass
	finally:
		frappe.delete_doc("Season", season.name, force=True,
		                  ignore_permissions=True)


@check("a stay touching a weekend loses the small-group rate throughout")
def t3i():
	"""Villas that price small midweek parties per head treat a stay that
	runs into the weekend as a weekend stay - you cannot have the Thursday
	night of a Thursday-to-Saturday booking at the per-head rate."""
	from kamra.pricing import occupancy_rate, quote, small_group_allows_stay

	villa = frappe.get_doc({
		"doctype": "Room Type", "property": P, "room_type_code": "EWS",
		"room_type_name": "Eval Weekend Stay", "base_price": 22500,
		"base_occupancy": 8, "extra_adult_price": 1600,
		"adults_capacity": 14, "children_capacity": 6, "tax_percent": 0,
		"small_group_max_adults": 6, "small_group_price_per_adult": 4000,
		"small_group_days": "sun,mon,tue,wed,thu",
		"small_group_whole_stay": 1,
	}).insert(ignore_permissions=True)
	try:
		# 2030-03-05 Tue, 2030-03-07 Thu, 2030-03-08 Fri
		assert getdate("2030-03-07").strftime("%a").lower() == "thu"
		assert getdate("2030-03-08").strftime("%a").lower() == "fri"

		# midweek only: the rate stands
		assert small_group_allows_stay(villa, "2030-03-05", "2030-03-07")
		# runs into Friday: off for every night of the stay
		assert not small_group_allows_stay(villa, "2030-03-07", "2030-03-09")

		# the Thursday night of that stay is the house rate, not 4 x 4,000
		assert occupancy_rate(villa, 4, 0, "2030-03-07",
		                      allow_small_group=False) == 22500
		# and on its own it is still per head
		assert occupancy_rate(villa, 4, 0, "2030-03-07") == 16000

		# end to end: Thursday + Friday for four guests is two house nights
		q = quote(P, villa.name, "2030-03-07", "2030-03-09", 4, 0)
		assert [n["rate"] for n in q["nightly"]] == [22500.0, 22500.0], q["nightly"]

		# with the flag off, each night is judged on its own again
		villa.small_group_whole_stay = 0
		villa.save(ignore_permissions=True)
		q2 = quote(P, villa.name, "2030-03-07", "2030-03-09", 4, 0)
		assert [n["rate"] for n in q2["nightly"]] == [16000.0, 22500.0], q2["nightly"]
	finally:
		frappe.delete_doc("Room Type", villa.name, force=True,
		                  ignore_permissions=True)


@check("over-capacity guests are booked by arrangement, at an agreed price")
def t3j():
	"""A room takes a few more than it sleeps comfortably, by arrangement.
	What those guests cost is agreed with the guest, not read off a rate
	card - so the engine stops at capacity and the booking carries the
	number and the price someone actually agreed."""
	from kamra.pricing import occupancy_rate

	villa = frappe.get_doc({
		"doctype": "Room Type", "property": P, "room_type_code": "EOC",
		"room_type_name": "Eval Over Capacity", "base_price": 22500,
		"base_occupancy": 8, "extra_adult_price": 1600,
		"adults_capacity": 14, "children_capacity": 6,
		"max_extra_beds": 3, "tax_percent": 0,
	}).insert(ignore_permissions=True)
	g = _guest("Eval Crowded", "+91 70000 00032")
	base = {
		"doctype": "Reservation", "property": P, "guest": g,
		"room_type": villa.name, "check_in_date": "2031-04-01",
		"check_out_date": "2031-04-02", "auto_price": 1,
	}
	made = []
	try:
		# the rate card covers the room as sold, and stops at its capacity
		assert occupancy_rate(villa, 14, 0) == 22500 + 6 * 1600, "at capacity"
		assert occupancy_rate(villa, 17, 0) == 22500 + 6 * 1600, \
			"the engine must not invent a price beyond capacity"

		r = frappe.get_doc({**base, "adults": 14}).insert(ignore_permissions=True)
		made.append(r.name)

		# above capacity without a reason: refused, and the message says why
		try:
			frappe.get_doc({**base, "adults": 15}).insert(ignore_permissions=True)
			raise AssertionError("15 adults went in with no reason given")
		except frappe.ValidationError as e:
			assert "arrangement" in str(e), str(e)

		# with a reason, the count and the agreed price: allowed
		r = frappe.get_doc({
			**base, "adults": 17,
			"over_capacity_reason": "Group happy to share the king beds",
			"over_capacity_guests": 3, "over_capacity_charge": 5000,
		}).insert(ignore_permissions=True)
		made.append(r.name)
		assert r.over_capacity_charge == 5000, r.over_capacity_charge

		# beyond the extra beds: still refused, reason or not
		try:
			frappe.get_doc({
				**base, "adults": 18,
				"over_capacity_reason": "Tried it on",
			}).insert(ignore_permissions=True)
			raise AssertionError("18 adults exceeded capacity plus beds")
		except frappe.ValidationError:
			pass

		# the agreed amount is its own line, not folded into the room rate -
		# the guest is told what the house costs and what the extra beds cost
		from kamra.folio import _nightly_room_rate
		assert _nightly_room_rate(r, "2031-04-01") == 22500 + 6 * 1600, \
			"the agreed charge must not inflate the room rate"

		from kamra.pricing import quote
		q = quote(P, villa.name, "2031-04-01", "2031-04-02", 17, 0,
		          over_capacity_charge=5000)
		assert q["room_total"] == 22500 + 6 * 1600, q["room_total"]
		assert q["over_capacity_total"] == 5000, q["over_capacity_total"]
		assert q["amount_before_tax"] == 22500 + 6 * 1600 + 5000, q
		components = [li["component"] for li in q["line_items"]]
		assert "over_capacity" in components, components
	finally:
		for n in made:
			frappe.delete_doc("Reservation", n, force=True,
			                  ignore_permissions=True)
		frappe.delete_doc("Room Type", villa.name, force=True,
		                  ignore_permissions=True)


@check("GST slab: 5% below threshold, 18% above")
def t4():
	from kamra.pricing import quote
	normal = quote(P, RT, "2030-02-01", "2030-02-02", 2, 0)["nightly"][0]
	peak = quote(P, RT, "2030-01-11", "2030-01-12", 2, 0)["nightly"][0]
	assert normal["gst_rate"] == 5, normal
	assert peak["gst_rate"] == 18, peak


@check("voucher: 10% off, min-nights enforced")
def t5():
	from kamra.pricing import quote
	q = quote(P, RT, "2030-02-01", "2030-02-03", 2, 0, voucher_code="EVAL10")
	assert q["discount"] == 800, q["discount"]
	try:
		quote(P, RT, "2030-02-01", "2030-02-02", 2, 0, voucher_code="EVAL10")
		raise AssertionError("1-night stay accepted a 2-night voucher")
	except frappe.ValidationError:
		pass


@check("guardrail blocks rates outside floor/ceiling")
def t6():
	from kamra.api import set_room_rate
	try:
		set_room_rate(P, RT, "2030-03-01", "2030-03-02", 2500)
		raise AssertionError("floor not enforced")
	except frappe.ValidationError:
		pass
	try:
		set_room_rate(P, RT, "2030-03-01", "2030-03-02", 9500)
		raise AssertionError("ceiling not enforced")
	except frappe.ValidationError:
		pass
	assert set_room_rate(P, RT, "2030-03-01", "2030-03-02", 5000)["rate"] == 5000


def _guest(name, phone):
	return frappe.get_doc({
		"doctype": "Guest", "first_name": name, "phone": phone,
	}).insert(ignore_permissions=True).name


def _res(guest, ci, co, room=None, day_use=0, allow_past=0):
	doc = frappe.get_doc({
		"doctype": "Reservation", "property": P, "guest": guest,
		"room_type": RT, "room": room, "check_in_date": ci,
		"check_out_date": co, "adults": 2, "is_day_use": day_use,
		"auto_price": 1,
	})
	# a back-dated booking (e.g. seeding a no-show) is a legitimate case the
	# past-check-in guard exempts via this flag
	if allow_past:
		doc.flags.allow_past_check_in = True
	return doc.insert(ignore_permissions=True)


@check("double booking blocked; adjacent stay allowed")
def t7():
	g = _guest("Eval A", "+91 70000 00001")
	_res(g, "2030-04-01", "2030-04-03", ROOM)
	try:
		_res(g, "2030-04-02", "2030-04-04", ROOM)
		raise AssertionError("overlap accepted")
	except frappe.ValidationError:
		pass
	_res(g, "2030-04-03", "2030-04-05", ROOM)  # back-to-back must pass


@check("day-use occupies its date for overlap purposes")
def t8():
	g = _guest("Eval B", "+91 70000 00002")
	_res(g, "2030-05-01", "2030-05-01", ROOM, day_use=1)
	try:
		_res(g, "2030-05-01", "2030-05-02", ROOM)
		raise AssertionError("overnight over a day-use accepted")
	except frappe.ValidationError:
		pass


@check("blacklisted guest cannot book")
def t9():
	g = _guest("Eval C", "+91 70000 00003")
	frappe.db.set_value("Guest", g, "blacklisted", 1)
	try:
		_res(g, "2030-06-01", "2030-06-02")
		raise AssertionError("blacklist not enforced")
	except frappe.ValidationError:
		pass


@check("folio: check-in opens, night posts once, balance math holds")
def t10():
	from kamra.folio import post_room_night
	g = _guest("Eval D", "+91 70000 00004")
	res = _res(g, nowdate(), add_days(nowdate(), 2), ROOM)
	res.status = "Checked In"
	res.save(ignore_permissions=True)
	folio_name = frappe.db.get_value(
		"Folio", {"reservation": res.name, "folio_type": "Guest"})
	assert folio_name, "folio not opened at check-in"
	assert post_room_night(res, nowdate()) is True
	assert post_room_night(res, nowdate()) is False, "double posted"
	folio = frappe.get_doc("Folio", folio_name)
	assert folio.charges_total == 4000, folio.charges_total
	assert folio.grand_total == 4200, folio.grand_total  # +5% GST
	assert folio.balance == 4200


@check("split folio: transfer moves value, totals conserved")
def t11():
	from kamra.folio import split_folio, transfer_charge
	g = _guest("Eval E", "+91 70000 00005")
	res = _res(g, "2030-07-01", "2030-07-02", ROOM)
	res.status = "Checked In"
	res.save(ignore_permissions=True)
	main = frappe.db.get_value(
		"Folio", {"reservation": res.name, "folio_type": "Guest"})
	from kamra.folio import post_room_night
	post_room_night(res, "2030-07-01")
	second = split_folio(res.name, "Company")
	fd = frappe.get_doc("Folio", main)
	transfer_charge(main, fd.charges[0].name, second)
	a = frappe.get_doc("Folio", main)
	b = frappe.get_doc("Folio", second)
	assert a.grand_total + b.grand_total == 4200, (a.grand_total, b.grand_total)


@check("billing rules: corporate room→Company folio, alcohol→Guest")
def t13():
	from kamra import api
	from kamra.folio import post_room_night
	comp = frappe.get_doc({
		"doctype": "Corporate Account", "company_name": "EVAL Corp",
		"billing_rules": [{"charge_type": "Room", "pay_by": "Company"}],
	}).insert(ignore_permissions=True)
	g = _guest("Eval G", "+91 70000 00007")
	res = _res(g, "2030-08-01", "2030-08-02", ROOM)
	res.booking_type = "Corporate"
	res.company = comp.name
	res.status = "Checked In"
	res.save(ignore_permissions=True)
	assert post_room_night(res, "2030-08-01") is True
	room_folio_type = frappe.db.sql("""
		SELECT f.folio_type FROM `tabFolio Charge` fc
		JOIN `tabFolio` f ON fc.parent = f.name
		WHERE f.reservation = %s AND fc.charge_type = 'Room'""",
		res.name)[0][0]
	assert room_folio_type == "Company", room_folio_type
	out = api.post_stay_charge(res.name, "Food & Beverage",
	                           "eval beer", 300, 0, is_alcohol=1)
	assert out["folio_type"] == "Guest", out
	# the guard: alcohol may never be posted onto a Company folio
	company_folio = frappe.db.get_value(
		"Folio", {"reservation": res.name, "folio_type": "Company"})
	try:
		api.add_folio_charge(company_folio, "Food & Beverage",
		                     "eval whisky", 500, 0, is_alcohol=1)
		raise AssertionError("alcohol accepted on Company folio")
	except frappe.ValidationError:
		pass


@check("split billing: % and ₹ splits conserve totals, bulk move works")
def t14():
	from kamra import api
	from kamra.folio import post_room_night, split_folio
	g = _guest("Eval H", "+91 70000 00008")
	res = _res(g, "2030-09-01", "2030-09-02", ROOM)
	res.status = "Checked In"
	res.save(ignore_permissions=True)
	post_room_night(res, "2030-09-01")
	main = frappe.db.get_value(
		"Folio", {"reservation": res.name, "folio_type": "Guest"})
	extra = split_folio(res.name, "Extra")

	fd = frappe.get_doc("Folio", main)
	room_row = next(c for c in fd.charges if c.charge_type == "Room")
	out = api.split_folio_charge(main, room_row.name, extra, percent=30)
	assert out == {"kept": 2800.0, "moved": 1200.0}, out
	a, b = frappe.get_doc("Folio", main), frappe.get_doc("Folio", extra)
	assert a.grand_total + b.grand_total == 4200, (a.grand_total, b.grand_total)

	# amount split of the split (₹200 of the ₹1200 back-ish onto a 3rd line)
	row2 = b.charges[0]
	out = api.split_folio_charge(extra, row2.name, main, amount=200)
	assert out["kept"] == 1000.0 and out["moved"] == 200.0, out
	a, b = frappe.get_doc("Folio", main), frappe.get_doc("Folio", extra)
	assert a.grand_total + b.grand_total == 4200, (a.grand_total, b.grand_total)

	# bulk transfer: move every line on main to extra in one call
	rows = [c.name for c in a.charges]
	api.transfer_folio_charges(main, rows, extra)
	a, b = frappe.get_doc("Folio", main), frappe.get_doc("Folio", extra)
	assert a.grand_total == 0 and b.grand_total == 4200, (
		a.grand_total, b.grand_total)


@check("group billing: company pays stays on ONE master, guest extras local")
def t15():
	from kamra import api
	from kamra.folio import post_room_night
	comp = frappe.get_doc({
		"doctype": "Corporate Account", "company_name": "EVAL Group Corp",
		"billing_rules": [{"charge_type": "Room", "pay_by": "Company"}],
	}).insert(ignore_permissions=True)
	room2 = frappe.get_doc({
		"doctype": "Room", "property": P, "room_number": "E102",
		"room_type": RT}).insert(ignore_permissions=True).name
	gb = frappe.get_doc({
		"doctype": "Group Booking", "property": P,
		"group_name": "EVAL Offsite", "company": comp.name,
		"check_in_date": "2030-10-01", "check_out_date": "2030-10-02",
		"status": "Confirmed"}).insert(ignore_permissions=True)
	g1 = _guest("Eval I", "+91 70000 00009")
	g2 = _guest("Eval J", "+91 70000 00010")
	r1 = _res(g1, "2030-10-01", "2030-10-02", ROOM)
	r2 = _res(g2, "2030-10-01", "2030-10-02", room2)
	for r in (r1, r2):
		r.group_booking = gb.name
		r.status = "Checked In"
		r.save(ignore_permissions=True)

	# both rooms' nights land on ONE master folio
	assert post_room_night(r1, "2030-10-01") is True
	assert post_room_night(r2, "2030-10-01") is True
	master = frappe.db.get_value(
		"Folio", {"group_booking": gb.name, "folio_type": "Group"})
	assert master, "no group master folio"
	md = frappe.get_doc("Folio", master)
	rooms = [c for c in md.charges if c.charge_type == "Room"]
	assert len(rooms) == 2 and md.charges_total == 8000, md.charges_total
	# idempotent per member even though lines live on the lead-anchored master
	assert post_room_night(r2, "2030-10-01") is False, "member double posted"

	# guest extras stay on the guest's own folio
	out = api.post_stay_charge(r2.name, "Laundry", "2 shirts", 300, 18)
	assert out["folio_type"] == "Guest", out

	# re-bill: move the extra onto the master, cross-reservation
	gf = frappe.db.get_value(
		"Folio", {"reservation": r2.name, "folio_type": "Guest"})
	gfd = frappe.get_doc("Folio", gf)
	api.transfer_folio_charges(gf, [gfd.charges[0].name], master)
	md = frappe.get_doc("Folio", master)
	assert md.charges_total == 8300, md.charges_total

	# alcohol can never reach the master
	try:
		api.add_folio_charge(master, "Food & Beverage", "wine", 900, 0,
		                     is_alcohol=1)
		raise AssertionError("alcohol accepted on Group folio")
	except frappe.ValidationError:
		pass

	# unrelated stays still cannot exchange charges
	g3 = _guest("Eval K", "+91 70000 00011")
	r3 = _res(g3, "2030-11-01", "2030-11-02", ROOM)
	r3.status = "Checked In"
	r3.save(ignore_permissions=True)
	f3 = frappe.db.get_value(
		"Folio", {"reservation": r3.name, "folio_type": "Guest"})
	try:
		api.transfer_folio_charge(master, md.charges[0].name, f3)
		raise AssertionError("cross-stay transfer accepted")
	except frappe.ValidationError:
		pass


@check("profiles: merge repoints stays & money intact; anonymize keeps books")
def t16():
	from kamra import api
	from kamra.folio import post_room_night
	dup = _guest("Eval Dup", "+91 70000 00012")
	keep = _guest("Eval Keep", "+91 70000 00013")
	frappe.db.set_value("Guest", dup, "email", "dup@eval.test")
	res = _res(dup, "2030-12-01", "2030-12-02", ROOM)
	res.status = "Checked In"
	res.save(ignore_permissions=True)
	post_room_night(res, "2030-12-01")
	folio = frappe.db.get_value(
		"Folio", {"reservation": res.name, "folio_type": "Guest"})
	total_before = frappe.db.get_value("Folio", folio, "grand_total")

	out = api.merge_guests(dup, keep)
	assert out["moved"].get("Reservation") == 1, out
	assert not frappe.db.exists("Guest", dup), "duplicate survived"
	assert frappe.db.get_value("Reservation", res.name, "guest") == keep
	assert frappe.db.get_value("Folio", folio, "guest") == keep
	assert frappe.db.get_value("Folio", folio, "grand_total") == total_before
	# survivor inherited the blank email from the duplicate
	assert frappe.db.get_value("Guest", keep, "email") == "dup@eval.test"

	out = api.anonymize_guest(keep)
	g = frappe.get_doc("Guest", keep)
	assert g.full_name == out["alias"] and not g.phone and not g.email
	assert frappe.db.get_value(
		"Reservation", res.name, "guest_name") == out["alias"]
	assert frappe.db.get_value("Folio", folio, "grand_total") == total_before


@check("add-ons: booked extras post to the folio once, priced from Experience")
def t17():
	from kamra import api
	exp = frappe.get_doc({
		"doctype": "Experience", "property": P,
		"experience_name": "EVAL Sunset Cruise", "category": "Activity",
		"price": 1500, "gst_rate": 18}).insert(ignore_permissions=True)
	out = api.create_booking(
		property=P, room_type=RT, check_in_date="2031-01-05",
		check_out_date="2031-01-06", guest_name="Eval Addon",
		phone="+91 70000 00014", addons=[{"experience": exp.name, "qty": 2}])
	api.check_in(out["reservation"])
	folio = frappe.db.get_value(
		"Folio", {"reservation": out["reservation"], "folio_type": "Guest"})
	fd = frappe.get_doc("Folio", folio)
	line = next(c for c in fd.charges if c.charge_type == "Misc")
	assert line.amount == 3000 and line.gst_rate == 18, (line.amount,
	                                                     line.gst_rate)
	# reopening the folio must not double-post
	from kamra.folio import open_folio
	res = frappe.get_doc("Reservation", out["reservation"])
	open_folio(res)
	fd = frappe.get_doc("Folio", folio)
	assert len([c for c in fd.charges if c.charge_type == "Misc"]) == 1


@check("policies: late cancel fee, free outside window, no-show charged")
def t18():
	from kamra import api
	from kamra.folio import run_night_audit
	frappe.db.set_value("Property", P, {
		"free_cancel_days": 2, "cancellation_fee": "First Night",
		"no_show_charge": "First Night"})

	# cancel far in advance → free
	g = _guest("Eval Far", "+91 70000 00015")
	far = _res(g, add_days(nowdate(), 30), add_days(nowdate(), 31))
	out = api.cancel_reservation(far.name)
	assert out["fee"] == 0, out

	# cancel inside the window → first night lands on the folio, and the
	# guest gets a cancellation number
	g2 = _guest("Eval Late", "+91 70000 00016")
	late = _res(g2, add_days(nowdate(), 1), add_days(nowdate(), 2))
	preview = api.cancellation_preview(late.name)
	assert preview["inside_window"] and preview["estimated_fee"] == 4000
	out = api.cancel_reservation(late.name, reason="Change of plans")
	assert out["fee"] == 4000, out
	assert out["cancellation_number"].startswith("CXL-"), out
	folio = frappe.db.get_value(
		"Folio", {"reservation": late.name, "folio_type": "Guest"})
	assert frappe.db.get_value("Folio", folio, "grand_total") == 4200

	# flipping the status field directly must NOT bypass the policy
	g4 = _guest("Eval Bypass", "+91 70000 00018")
	byp = _res(g4, add_days(nowdate(), 1), add_days(nowdate(), 2))
	byp.status = "Cancelled"
	try:
		byp.save(ignore_permissions=True)
		raise AssertionError("status flip bypassed the cancellation policy")
	except frappe.ValidationError:
		pass

	# yesterday's un-arrived booking → no-show flagged AND charged
	g3 = _guest("Eval NoShow", "+91 70000 00017")
	ns = _res(g3, add_days(nowdate(), -1), nowdate(), allow_past=1)
	# the audit closes only the current business date
	frappe.db.set_value("Property", P, "business_date", nowdate())
	frappe.db.delete("Night Audit Run", {"property": P, "business_date": nowdate()})
	run_night_audit(P)
	assert frappe.db.get_value("Reservation", ns.name, "status") == "No Show"
	ns_folio = frappe.db.get_value(
		"Folio", {"reservation": ns.name, "folio_type": "Guest"})
	assert ns_folio, "no-show folio not opened"
	charges = frappe.get_doc("Folio", ns_folio).charges
	assert any("No-show" in (c.description or "") for c in charges)


@check("past check-in blocked on create and on date amend; allow_past still works")
def t18b():
	g = _guest("Eval PastCI", "+91 70000 00018")
	yesterday = add_days(nowdate(), -1)
	# new booking into the past must fail
	try:
		_res(g, yesterday, nowdate())
		raise AssertionError("past check-in accepted on create")
	except frappe.ValidationError:
		pass
	# flag still allows catch-up / seeding
	res = _res(g, yesterday, nowdate(), allow_past=1)
	# saving without changing dates (in-house style) must stay ok
	res.status = "Checked In"
	res.save(ignore_permissions=True)
	# moving check-in further into the past must fail
	res.check_in_date = add_days(nowdate(), -2)
	try:
		res.save(ignore_permissions=True)
		raise AssertionError("past check-in amend accepted")
	except frappe.ValidationError:
		pass
	# Confirmed stay: amend check-in to yesterday must fail
	g2 = _guest("Eval PastCI2", "+91 70000 00028")
	live = _res(g2, add_days(nowdate(), 2), add_days(nowdate(), 3))
	live.check_in_date = yesterday
	live.check_out_date = nowdate()
	try:
		live.save(ignore_permissions=True)
		raise AssertionError("Confirmed past amend accepted")
	except frappe.ValidationError:
		pass


@check("closed folio is frozen: charges immutable, close needs a settled bill")
def t19():
	from kamra import api
	from kamra.folio import close_folio, post_room_night
	g = _guest("Eval Frozen", "+91 70000 00019")
	res = _res(g, "2031-02-01", "2031-02-02", ROOM)
	res.status = "Checked In"
	res.save(ignore_permissions=True)
	post_room_night(res, "2031-02-01")
	folio = frappe.db.get_value(
		"Folio", {"reservation": res.name, "folio_type": "Guest"})
	try:
		close_folio(folio)
		raise AssertionError("a folio with money owed was closed")
	except frappe.ValidationError:
		pass
	api.add_folio_payment(folio, "UPI",
	                      float(frappe.db.get_value("Folio", folio, "balance")))
	inv = close_folio(folio)
	assert inv.startswith("INV-"), inv
	fd = frappe.get_doc("Folio", folio)
	fd.charges[0].amount = 1
	try:
		fd.save(ignore_permissions=True)
		raise AssertionError("closed folio accepted a charge edit")
	except frappe.ValidationError:
		pass


@check("room capacity: over-occupancy booking refused, at-capacity allowed")
def t20():
	g = _guest("Eval Crowd", "+91 70000 00020")
	base = {
		"doctype": "Reservation", "property": P, "guest": g,
		"room_type": RT, "check_in_date": "2031-03-01",
		"check_out_date": "2031-03-02", "auto_price": 1,
	}
	# the reported bug: 11 adults sailed into a 3-adult room type
	try:
		frappe.get_doc({**base, "adults": 11}).insert(ignore_permissions=True)
		raise AssertionError("11 adults accepted in a 3-adult room type")
	except frappe.ValidationError:
		pass
	try:
		frappe.get_doc({**base, "adults": 2, "children": 5}).insert(
			ignore_permissions=True)
		raise AssertionError("5 children accepted in a 2-child room type")
	except frappe.ValidationError:
		pass
	try:
		frappe.get_doc({**base, "adults": 0}).insert(ignore_permissions=True)
		raise AssertionError("a stay with no adults was accepted")
	except frappe.ValidationError:
		pass
	# exactly at capacity is a legitimate full house
	ok = frappe.get_doc({**base, "adults": 3, "children": 2, "room": ROOM}).insert(
		ignore_permissions=True)
	assert ok.name
	# legacy over-capacity rows must still advance (e.g. check-out):
	# only party/room-type edits re-trigger the guard
	frappe.db.set_value("Reservation", ok.name, "adults", 9,
		update_modified=False)
	legacy = frappe.get_doc("Reservation", ok.name)
	legacy.status = "Checked In"
	legacy.save(ignore_permissions=True)  # must NOT throw
	try:
		legacy.adults = 12
		legacy.save(ignore_permissions=True)
		raise AssertionError("growing an over-capacity party was accepted")
	except frappe.ValidationError:
		pass


@check("room block: held room leaves availability, release restores it")
def t21():
	from kamra import api
	before = len(api.available_rooms(P, RT, "2033-01-10", "2033-01-12"))
	assert before >= 1, before
	b = api.create_room_block(P, ROOM, "2033-01-10", "2033-01-12",
		"VIP Hold", "eval hold")
	held = len(api.available_rooms(P, RT, "2033-01-10", "2033-01-12"))
	assert held == before - 1, (before, held)
	# a non-overlapping window is untouched
	assert len(api.available_rooms(P, RT, "2033-02-01", "2033-02-02")) == before
	api.release_room_block(b["name"])
	assert len(api.available_rooms(P, RT, "2033-01-10", "2033-01-12")) == before
	# can't hold a room that's already sold for the window
	g = _guest("Eval Held", "+91 70000 00021")
	_res(g, "2033-03-01", "2033-03-03", ROOM)
	try:
		api.create_room_block(P, ROOM, "2033-03-01", "2033-03-03", "Maintenance")
		raise AssertionError("blocked an already-booked room")
	except frappe.ValidationError:
		pass


@check("housekeeping assignment: assign, decline back to pool, claim")
def t22():
	from kamra import api
	task = frappe.get_doc({
		"doctype": "Housekeeping Task", "property": P, "room": ROOM,
		"task_type": "Checkout Clean", "priority": "High", "status": "Pending",
	}).insert(ignore_permissions=True).name
	api.hk_assign_task(task, "hk@kamra.local")
	d = frappe.get_doc("Housekeeping Task", task)
	assert d.assignment_status == "Assigned" and d.assigned_to_user, d.assignment_status
	api.hk_reject_task(task, "on break")
	d.reload()
	assert d.assignment_status == "Unassigned" and not d.assigned_to_user, "reject didn't free it"
	assert d.reject_reason, "reject reason not recorded"
	api.hk_claim_task(task)
	d.reload()
	assert d.assignment_status == "Accepted" and d.assigned_to_user, "claim failed"
	# the queue splits mine vs claimable and carries the flags
	q = api.hk_queue(P)
	row = next(t for t in q["tasks"] if t["name"] == task)
	assert row["mine"] and not row["claimable"], (row["mine"], row["claimable"])


@check("housekeeping SLA: due_by set, overdue task escalates & breaches")
def t23():
	from frappe.utils import add_to_date, now_datetime

	from kamra.housekeeping import escalate_overdue_tasks
	# a task born already overdue (due_by in the past)
	task = frappe.get_doc({
		"doctype": "Housekeeping Task", "property": P, "room": ROOM,
		"task_type": "Checkout Clean", "priority": "Urgent", "status": "Pending",
	}).insert(ignore_permissions=True)
	assert task.due_by, "SLA due_by not set on insert"
	frappe.db.set_value("Housekeeping Task", task.name, "due_by",
		add_to_date(now_datetime(), minutes=-90), update_modified=False)
	escalate_overdue_tasks()
	d = frappe.get_doc("Housekeeping Task", task.name)
	# 90 min over on a 20-min SLA → straight to level 2 (manager)
	assert d.breached == 1, "overdue task not marked breached"
	assert d.escalation_level == 2, d.escalation_level


@check("CRS access guard: a property-restricted user is blocked from others")
def t24():
	from kamra.crs import assert_property_access, permitted_properties
	u = "eval.pinned@kamra.local"
	if not frappe.db.exists("User", u):
		frappe.get_doc({
			"doctype": "User", "email": u, "first_name": "Pinned",
			"send_welcome_email": 0, "roles": [{"role": "Front Desk"}],
		}).insert(ignore_permissions=True)
	if not frappe.db.exists("User Permission",
	                        {"user": u, "allow": "Property", "for_value": P}):
		frappe.get_doc({
			"doctype": "User Permission", "user": u,
			"allow": "Property", "for_value": P,
		}).insert(ignore_permissions=True)
	frappe.set_user(u)  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow
	try:
		assert permitted_properties() == {P}, permitted_properties()
		assert_property_access(P)  # the one they're allowed
		try:
			assert_property_access("Some Other Hotel XYZ")
			raise AssertionError("guard let a restricted user reach another property")
		except frappe.PermissionError:
			pass
		# and they can't create a booking at a property they can't see
		from kamra import api
		try:
			api.create_booking(
				property="Some Other Hotel XYZ", room_type="x",
				check_in_date="2035-01-01", check_out_date="2035-01-02",
				guest_name="Nope", phone="+91 70000 09999")
			raise AssertionError("booked at an off-limits property")
		except frappe.PermissionError:
			pass
	finally:
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow


@check("POS: order fires KOT, delivery posts F&B to the room folio with discount")
def t25():
	from kamra import pos
	outlet = frappe.get_doc({
		"doctype": "POS Outlet", "property": P, "outlet_name": "Eval Cafe",
		"outlet_type": "Restaurant", "gst_rate": 5,
	}).insert(ignore_permissions=True).name
	mi = frappe.get_doc({
		"doctype": "Menu Item", "property": P, "outlet": outlet,
		"item_name": "Eval Dosa", "category": "Food", "price": 200,
		"is_veg": 1, "available": 1, "prep_station": "Kitchen",
	}).insert(ignore_permissions=True).name
	g = _guest("Eval POS", "+91 70000 00025")
	res = _res(g, "2034-01-01", "2034-01-02", ROOM)
	res.status = "Checked In"
	res.save(ignore_permissions=True)
	folio = frappe.db.get_value(
		"Folio", {"reservation": res.name, "folio_type": "Guest"})
	base = frappe.get_doc("Folio", folio).grand_total

	o = pos.create_order(outlet, [{"menu_item": mi, "qty": 2, "instructions": "hot"}],
	                     room=ROOM)
	assert o["order_total"] == 400, o["order_total"]
	pos.apply_discount(o["order"], 50, "regular")
	pos.confirm_order(o["order"])
	pos.fire_kot(o["order"])
	kq = pos.kitchen_queue(P)
	assert any(row["name"] == o["order"] for row in kq), "order not on kitchen queue"
	pos.mark_prepared(o["order"])
	out = pos.deliver_order(o["order"])
	assert out["posted_to_folio"], "delivered order did not post to folio"
	fd = frappe.get_doc("Folio", folio)
	# 350 net (400-50) + 5% F&B GST = 367.50 added
	assert round(fd.grand_total - base, 2) == 367.50, fd.grand_total - base


@check("POS: table map states, KOT numbering, void with reason, outlet settle")
def t26():
	from kamra import pos
	outlet = frappe.get_doc({
		"doctype": "POS Outlet", "property": P, "outlet_name": "Eval Diner",
		"outlet_type": "Restaurant", "gst_rate": 5, "tables": "T1\nT2\nT3",
	}).insert(ignore_permissions=True).name
	mi1 = frappe.get_doc({
		"doctype": "Menu Item", "property": P, "outlet": outlet,
		"item_name": "Eval Thali", "category": "Food", "price": 300,
		"is_veg": 1, "available": 1, "prep_station": "Kitchen",
	}).insert(ignore_permissions=True).name
	mi2 = frappe.get_doc({
		"doctype": "Menu Item", "property": P, "outlet": outlet,
		"item_name": "Eval Lassi", "category": "Beverage", "price": 100,
		"is_veg": 1, "available": 1, "prep_station": "Bar",
	}).insert(ignore_permissions=True).name

	# the cleaning flag lives in redis, which the harness rollback doesn't
	# touch - clear leftovers from any previous run first
	for t in ("T1", "T2", "T3"):
		pos.mark_table_clean(outlet, t)
	tm = pos.table_map(outlet)
	assert len(tm["tables"]) == 3, tm
	assert all(t["state"] == "vacant" for t in tm["tables"]), tm

	o = pos.create_order(outlet, [{"menu_item": mi1, "qty": 1},
	                              {"menu_item": mi2, "qty": 2}],
	                     table_no="T2", order_type="Dine In")
	assert o["order_total"] == 500, o["order_total"]
	t2 = [t for t in pos.table_map(outlet)["tables"] if t["table"] == "T2"][0]
	assert t2["state"] == "running", t2

	fk = pos.fire_kot(o["order"])
	assert fk["kot_no"] >= 1, fk  # daily sequence per outlet
	assert len(fk["fired_items"]) == 2, fk
	t2 = [t for t in pos.table_map(outlet)["tables"] if t["table"] == "T2"][0]
	assert t2["state"] == "fired", t2

	# void the lassi line with a reason - totals shrink, the line stays
	det = pos.order_detail(o["order"])
	lassi = next(i for i in det["items"] if i["item_name"] == "Eval Lassi")
	v = pos.void_item(o["order"], lassi["row"], "spilled")
	assert v["order_total"] == 300, v

	b = pos.bill_data(o["order"])
	assert b["grand_total"] == 315.0 and b["cgst"] == 7.5, b

	p = pos.pay_order(o["order"], "UPI")
	assert p["paid"] and p["order_total"] == 300, p
	doc = frappe.get_doc("POS Order", o["order"])
	assert doc.status == "Delivered" and not doc.posted_to_folio, doc.status
	# Settling frees the table into Cleaning; Mark clean returns it to vacant
	t2_after = [t for t in pos.table_map(outlet)["tables"] if t["table"] == "T2"][0]
	assert t2_after["state"] == "cleaning", t2_after
	pos.mark_table_clean(outlet, "T2")
	t2_clean = [t for t in pos.table_map(outlet)["tables"] if t["table"] == "T2"][0]
	assert t2_clean["state"] == "vacant", t2_clean

	# a second order the same day gets the next KOT number
	o2 = pos.create_order(outlet, [{"menu_item": mi1, "qty": 1}],
	                      order_type="Takeaway")
	fk2 = pos.fire_kot(o2["order"])
	assert fk2["kot_no"] == fk["kot_no"] + 1, (fk, fk2)
	pos.cancel_order(o2["order"], "guest left")
	assert frappe.db.get_value("POS Order", o2["order"], "status") == "Cancelled"


@check("POS: two parties share a table, split bill conserves the total")
def t27():
	from kamra import pos
	outlet = frappe.get_doc({
		"doctype": "POS Outlet", "property": P, "outlet_name": "Eval Bistro",
		"outlet_type": "Restaurant", "gst_rate": 5, "tables": "T1\nT2",
	}).insert(ignore_permissions=True).name
	mk = lambda n, p: frappe.get_doc({
		"doctype": "Menu Item", "property": P, "outlet": outlet,
		"item_name": n, "category": "Food", "price": p,
		"is_veg": 1, "available": 1, "prep_station": "Kitchen",
	}).insert(ignore_permissions=True).name
	soup, curry, rice = mk("Eval Soup", 150), mk("Eval Curry", 250), mk("Eval Rice", 100)

	# party A and party B share T1 - two separate bills on one table
	a = pos.create_order(outlet, [{"menu_item": soup, "qty": 1}], table_no="T1")
	b = pos.create_order(outlet, [{"menu_item": curry, "qty": 1},
	                              {"menu_item": rice, "qty": 2}], table_no="T1")
	t1 = [t for t in pos.table_map(outlet)["tables"] if t["table"] == "T1"][0]
	assert t1["bills"] == 2 and len(t1["orders"]) == 2, t1
	assert t1["order_total"] == 600, t1  # 150 + 450
	labels = {o["label"] for o in t1["orders"]}
	assert labels == {"Table T1 · 1", "Table T1 · 2"}, labels

	# split party B's bill: rice moves to its own bill, total conserved
	pos.fire_kot(b["order"])
	det = pos.order_detail(b["order"])
	rice_row = next(i["row"] for i in det["items"] if i["item_name"] == "Eval Rice")
	s = pos.split_order(b["order"], [rice_row])
	assert s["source_total"] == 250 and s["new_total"] == 200, s
	moved = pos.order_detail(s["new_order"])
	assert moved["items"][0]["kot_status"] == "Fired", moved  # kitchen state kept
	assert moved["table_no"] == "T1" and moved["kot_no"] == det["kot_no"], moved
	t1 = [t for t in pos.table_map(outlet)["tables"] if t["table"] == "T1"][0]
	assert t1["bills"] == 3 and t1["order_total"] == 600, t1

	# guard: a split can't take every line
	det_a = pos.order_detail(a["order"])
	try:
		pos.split_order(a["order"], [det_a["items"][0]["row"]])
		raise AssertionError("split of every line was allowed")
	except frappe.exceptions.ValidationError:
		pass


@check("POS: delivery & takeaway orders, seats, guests, recent bills")
def t28():
	from kamra import pos
	outlet = frappe.get_doc({
		"doctype": "POS Outlet", "property": P, "outlet_name": "Eval Express",
		"outlet_type": "Restaurant", "gst_rate": 5, "tables": "T1:2\nT2:4",
	}).insert(ignore_permissions=True).name
	mi = frappe.get_doc({
		"doctype": "Menu Item", "property": P, "outlet": outlet,
		"item_name": "Eval Biryani", "category": "Food", "price": 400,
		"is_veg": 0, "available": 1, "prep_station": "Kitchen",
	}).insert(ignore_permissions=True).name

	# seats come from the "name:seats" layout
	tm = pos.table_map(outlet)
	assert [t["seats"] for t in tm["tables"]] == [2, 4], tm

	# delivery needs the customer; carries name/phone/address end to end
	try:
		pos.create_order(outlet, [{"menu_item": mi, "qty": 1}],
		                 order_type="Delivery")
		raise AssertionError("delivery without customer accepted")
	except frappe.exceptions.ValidationError:
		pass
	d = pos.create_order(outlet, [{"menu_item": mi, "qty": 2}],
	                     order_type="Delivery", customer_name="Asha Rao",
	                     customer_phone="+91 90000 00028",
	                     delivery_address="12 MG Road")
	opened = [o for o in pos.open_orders(outlet) if o["name"] == d["order"]]
	assert opened and opened[0]["label"] == "Delivery · Asha", opened
	b = pos.bill_data(d["order"])
	assert b["delivery_address"] == "12 MG Road", b

	# dine-in with a guest count lands on the table tile
	pos.create_order(outlet, [{"menu_item": mi, "qty": 1}],
	                 table_no="T2", order_type="Dine In", guests=3)
	t2 = [t for t in pos.table_map(outlet)["tables"] if t["table"] == "T2"][0]
	assert t2["guests"] == 3 and t2["since"], t2

	# recent bills reflect settlement
	pos.fire_kot(d["order"])
	pos.pay_order(d["order"], "UPI")
	rec = [r for r in pos.recent_orders(outlet) if r["name"] == d["order"]]
	assert rec and rec[0]["paid"] and rec[0]["payment_mode"] == "UPI", rec
	assert not rec[0]["open"], rec


@check("POS: table areas, temp-table tiles, NC bills at zero with auth")
def t29():
	from kamra import pos
	outlet = frappe.get_doc({
		"doctype": "POS Outlet", "property": P, "outlet_name": "Eval Terrace",
		"outlet_type": "Restaurant", "gst_rate": 5,
		"tables": "[Hall]\nH1:4\nH2:2\n[Patio]\nP1:4",
	}).insert(ignore_permissions=True).name
	mi = frappe.get_doc({
		"doctype": "Menu Item", "property": P, "outlet": outlet,
		"item_name": "Eval Kebab", "category": "Food", "price": 350,
		"is_veg": 0, "available": 1, "prep_station": "Kitchen",
	}).insert(ignore_permissions=True).name

	# areas parse from the layout headers
	tm = pos.table_map(outlet)
	assert [(t["table"], t["area"]) for t in tm["tables"]] == [
		("H1", "Hall"), ("H2", "Hall"), ("P1", "Patio")], tm

	# a bill on a table outside the layout becomes a live temp tile
	o = pos.create_order(outlet, [{"menu_item": mi, "qty": 1}],
	                     table_no="Counter 2", order_type="Dine In")
	tm = pos.table_map(outlet)
	temp = [t for t in tm["tables"] if t.get("temp")]
	assert len(temp) == 1 and temp[0]["table"] == "Counter 2", tm
	assert temp[0]["area"] == "Temp" and temp[0]["state"] == "running", temp
	assert not tm["other"], tm["other"]  # it's a tile now, not a loose tab

	# NC: needs an authorizer, zeroes the bill, blocks payment, skips folio
	try:
		pos.mark_nc(o["order"], "")
		raise AssertionError("NC without authorizer accepted")
	except frappe.exceptions.ValidationError:
		pass
	nc = pos.mark_nc(o["order"], "GM", "regular guest birthday")
	assert nc["nc"] and nc["order_total"] == 0, nc
	pos.fire_kot(o["order"])
	b = pos.bill_data(o["order"])
	assert b["grand_total"] == 0 and b["nc_authorized_by"] == "GM", b
	assert b["nc_note"] == "regular guest birthday", b
	try:
		pos.pay_order(o["order"], "Cash")
		raise AssertionError("NC bill accepted a payment")
	except frappe.exceptions.ValidationError:
		pass
	out = pos.deliver_order(o["order"])
	assert not out["posted_to_folio"], out
	# undo path exists while a bill is open
	o2 = pos.create_order(outlet, [{"menu_item": mi, "qty": 1}],
	                      table_no="H1")
	pos.mark_nc(o2["order"], "Chef")
	back = pos.mark_nc(o2["order"], "", undo=1)
	assert not back["nc"] and back["order_total"] == 350, back


@check("POS: table reservation lifecycle and cleaning state")
def t30():
	from frappe.utils import add_to_date, now_datetime

	from kamra import pos
	outlet = frappe.get_doc({
		"doctype": "POS Outlet", "property": P, "outlet_name": "Eval Garden",
		"outlet_type": "Restaurant", "gst_rate": 5, "tables": "G1:4\nG2:2",
	}).insert(ignore_permissions=True).name
	mi = frappe.get_doc({
		"doctype": "Menu Item", "property": P, "outlet": outlet,
		"item_name": "Eval Salad", "category": "Food", "price": 200,
		"is_veg": 1, "available": 1, "prep_station": "Kitchen",
	}).insert(ignore_permissions=True).name

	for t in ("G1", "G2"):  # redis cleaning flags survive the rollback
		pos.mark_table_clean(outlet, t)

	# reserve G1 an hour out - the tile flips to Reserved with the details
	r = pos.reserve_table(outlet, "G1", "Asha Rao",
	                      str(add_to_date(now_datetime(), hours=1)),
	                      phone="+91 90000 00030", party_size=4)
	g1 = [t for t in pos.table_map(outlet)["tables"] if t["table"] == "G1"][0]
	assert g1["state"] == "reserved" and g1["res_guest"] == "Asha Rao", g1
	assert g1["res_party"] == 4 and g1["res_time"], g1

	# a reservation needs a guest name
	try:
		pos.reserve_table(outlet, "G2", "  ",
		                  str(add_to_date(now_datetime(), hours=2)))
		raise AssertionError("nameless reservation accepted")
	except frappe.exceptions.ValidationError:
		pass

	# seating clears the Reserved state
	pos.set_reservation(r["reservation"], "Seated")
	g1 = [t for t in pos.table_map(outlet)["tables"] if t["table"] == "G1"][0]
	assert g1["state"] == "vacant", g1

	# settling the party's bill flags the table for cleaning...
	o = pos.create_order(outlet, [{"menu_item": mi, "qty": 2}],
	                     table_no="G1", order_type="Dine In", guests=4)
	pos.fire_kot(o["order"])
	pos.pay_order(o["order"], "Card")
	g1 = [t for t in pos.table_map(outlet)["tables"] if t["table"] == "G1"][0]
	assert g1["state"] == "cleaning", g1
	# ...and Mark clean returns it to vacant
	pos.mark_table_clean(outlet, "G1")
	g1 = [t for t in pos.table_map(outlet)["tables"] if t["table"] == "G1"][0]
	assert g1["state"] == "vacant", g1


@check("laundry: rate card pricing, shortage guard, folio bill at 18% GST")
def t31():
	from kamra import laundry

	# rate card: upsert enforces service names and positive rates
	laundry.save_laundry_rate(P, "Shirt", "Wash & Iron", 60)
	laundry.save_laundry_rate(P, "Trousers", "Dry Clean", 140, express_rate=200)
	try:
		laundry.save_laundry_rate(P, "Shirt", "Boil", 10)
		raise AssertionError("bad service accepted")
	except frappe.exceptions.ValidationError:
		pass
	rates = laundry.laundry_rates(P)
	assert {(r["item_name"], r["service_type"]) for r in rates} >= {
		("Shirt", "Wash & Iron"), ("Trousers", "Dry Clean")}, rates
	shirt = next(r for r in rates if r["item_name"] == "Shirt")
	assert shirt["express_rate"] == 90, shirt  # blank express = 1.5x

	# an in-house guest requests a pickup; the attendant counts the bag
	# (own room - the shared eval room already has a checked-in stay)
	lroom = frappe.db.exists("Room", {"property": P, "room_number": "E102"})
	if not lroom:
		lroom = frappe.get_doc({
			"doctype": "Room", "property": P, "room_number": "E102",
			"room_type": RT,
		}).insert(ignore_permissions=True).name
	else:
		# a leaked E102 from an older run points at that run's room type;
		# realign it so this run's capacity math counts both rooms
		frappe.db.set_value("Room", lroom, "room_type", RT)
	g = _guest("Eval Laundry", "+91 70000 00031")
	res = _res(g, nowdate(), add_days(nowdate(), 2), lroom)
	res.status = "Checked In"
	res.save(ignore_permissions=True)
	folio = frappe.db.get_value(
		"Folio", {"reservation": res.name, "folio_type": "Guest"})
	base = frappe.get_doc("Folio", folio).grand_total

	r = laundry.request_pickup(P, lroom, notes="bag on door")
	c = laundry.collect_laundry(P, lroom, [
		{"item_name": "Shirt", "service_type": "Wash & Iron", "qty": 2},
		{"item_name": "Trousers", "service_type": "Dry Clean", "qty": 1},
	], order=r["order"])
	assert c["total"] == 260 and c["pieces"] == 3, c
	# unknown items can't be priced, so they can't be collected
	try:
		laundry.collect_laundry(P, lroom, [
			{"item_name": "Cape", "service_type": "Dry Clean", "qty": 1}])
		raise AssertionError("unpriced item accepted")
	except frappe.exceptions.ValidationError:
		pass

	laundry.laundry_status(r["order"], "In Process")
	laundry.laundry_status(r["order"], "Ready")
	doc = frappe.get_doc("Laundry Order", r["order"])
	laundry.return_items(r["order"], {doc.items[0].name: 2})
	# a missing piece blocks delivery unless it's explicitly noted
	try:
		laundry.deliver_laundry(r["order"])
		raise AssertionError("shortage delivered silently")
	except frappe.exceptions.ValidationError:
		pass
	laundry.return_items(r["order"], {doc.items[1].name: 1})
	out = laundry.deliver_laundry(r["order"])
	assert out["posted_to_folio"], out

	fd = frappe.get_doc("Folio", folio)
	# 260 + 18% services GST = 306.80 lands on the guest folio
	assert round(fd.grand_total - base, 2) == 306.80, fd.grand_total - base
	board = laundry.laundry_board(P)
	assert any(o["name"] == r["order"] for o in board["recent"]), board

	# express pricing: explicit express column wins over the 1.5x default
	c2 = laundry.collect_laundry(P, lroom, [
		{"item_name": "Trousers", "service_type": "Dry Clean", "qty": 1},
	], express=1)
	assert c2["total"] == 200, c2


@check("revenue: overbooking allowance, hurdle premium & floor, position briefing")
def t32():
	from kamra import api
	from kamra.pricing import demand_tier, forecast_occupancy, quote

	# isolated property so demand math isn't polluted by other tests
	P2 = "EVAL Yield Hotel"
	if not frappe.db.exists("Property", P2):
		frappe.get_doc({
			"doctype": "Property", "property_name": P2, "city": "Testville",
			"gst_mode": "Fixed", "gst_rate_low": 5, "gst_rate_high": 5,
		}).insert(ignore_permissions=True)
	rt = frappe.get_doc({
		"doctype": "Room Type", "property": P2, "room_type_code": "YLD",
		"room_type_name": "Yield Room", "base_price": 4000,
		"base_occupancy": 2, "adults_capacity": 3, "children_capacity": 2,
		"tax_percent": 5,
	}).insert(ignore_permissions=True).name
	rooms = [frappe.get_doc({
		"doctype": "Room", "property": P2, "room_number": f"Y10{i}",
		"room_type": rt,
	}).insert(ignore_permissions=True).name for i in (1, 2)]

	seq = {"n": 40}

	def book(ci, co, room=None):
		seq["n"] += 1
		g = _guest(f"Eval Yield {seq['n']}", f"+91 70000 000{seq['n']}")
		return frappe.get_doc({
			"doctype": "Reservation", "property": P2, "guest": g,
			"room_type": rt, "room": room, "check_in_date": ci,
			"check_out_date": co, "adults": 2, "auto_price": 1,
		}).insert(ignore_permissions=True)

	# 2 rooms, 0% allowance: the third unassigned booking must bounce
	book("2031-03-01", "2031-03-02", rooms[0])
	book("2031-03-01", "2031-03-02")
	try:
		book("2031-03-01", "2031-03-02")
		raise AssertionError("oversell beyond capacity accepted at 0%")
	except frappe.exceptions.ValidationError:
		pass
	# 50% allowance lifts the ceiling to 3
	frappe.db.set_value("Property", P2, "overbooking_pct", 50)
	frappe.get_cached_doc("Property", P2)  # refresh cache
	frappe.clear_document_cache("Property", P2)
	third = book("2031-03-01", "2031-03-02")
	try:
		book("2031-03-01", "2031-03-02")
		raise AssertionError("oversell beyond the allowance accepted")
	except frappe.exceptions.ValidationError:
		pass

	# demand tier: occupancy is 100%+ on that date -> premium + hurdle bite
	assert forecast_occupancy(P2, "2031-03-01") >= 100
	api.save_hurdle_rate(P2, 80, premium_pct=25, min_rate=5200)
	tier = demand_tier(P2, rt, "2031-03-01")
	assert tier and tier["premium_pct"] == 25, tier
	q = quote(P2, rt, "2031-03-01", "2031-03-02", 2, 0)
	assert q["nightly"][0]["rate"] == 5200, q["nightly"]  # 4000*1.25=5000 -> floor 5200
	assert q["nightly"][0]["demand_premium_pct"] == 25, q["nightly"]
	# a quiet date carries no premium
	q2 = quote(P2, rt, "2031-06-01", "2031-06-02", 2, 0)
	assert q2["nightly"][0]["rate"] == 4000, q2["nightly"]
	# manual rates can't undercut the hurdle while the tier is active
	try:
		api.set_room_rate(P2, rt, "2031-03-01", "2031-03-02", 4500)
		raise AssertionError("manual rate under the hurdle accepted")
	except frappe.exceptions.ValidationError:
		pass

	# position briefing: ETA/ETD flow into arrivals/departures + conflicts
	api.set_stay_times(third.name, "13:00", None)
	pb = api.position_briefing(P2, "2031-03-01")
	assert pb["capacity"] == 2 and pb["overbooking_limit"] == 3, pb
	assert pb["occupancy"] >= 100, pb
	arr = [a for a in pb["arrivals"] if a["name"] == third.name]
	assert arr and arr[0]["eta"] == "13:00", arr
	assert pb["demand_tier"] and pb["demand_tier"]["premium_pct"] == 25, pb


@check("migration: vendor CSV maps, day-first dates, history stamped, misfits skipped")
def t33():
	from kamra import migrate

	P3 = "EVAL Import Hotel"
	if not frappe.db.exists("Property", P3):
		frappe.get_doc({
			"doctype": "Property", "property_name": P3, "city": "Testville",
			"gst_mode": "Fixed", "gst_rate_low": 5, "gst_rate_high": 5,
		}).insert(ignore_permissions=True)
	rt = frappe.get_doc({
		"doctype": "Room Type", "property": P3, "room_type_code": "DLX",
		"room_type_name": "Deluxe", "base_price": 4000, "base_occupancy": 2,
		"adults_capacity": 3, "children_capacity": 2, "tax_percent": 5,
	}).insert(ignore_permissions=True).name
	frappe.get_doc({
		"doctype": "Room", "property": P3, "room_number": "I101",
		"room_type": rt,
	}).insert(ignore_permissions=True)

	# a day-first export: renamed headers, DD/MM dates, quoted name
	# with a comma, thousands separators, vendor status words
	csv_text = (
		"Guest Name,Mobile No,Email,Room Type,Arrival Date,Departure Date,"
		"Adult,Child,Total Amount,Reservation Status,Business Source\n"
		'"Rao, Import",+91 70000 00033,rao@x.in,Deluxe,25/12/2025,'
		'28/12/2025,2,1,"18,500.00",Checked Out,MakeMyTrip\n'
		"Import Two,+91 70000 00034,,Deluxe Room,14/01/2026,16/01/2026,"
		"2,0,,Cancelled,Walk-in\n"
		"Import Three,+91 70000 00035,,Deluxe,20/08/2033,22/08/2033,"
		"2,0,,Confirmed,Direct\n"
		"Import Four,+91 70000 00036,,Presidential Villa,05/09/2033,"
		"07/09/2033,2,0,,Confirmed,Direct\n")

	p = migrate.preview_import(P3, csv_text, "auto")
	assert p["mapping"]["check_in"] == "Arrival Date", p["mapping"]
	assert p["date_format"].startswith("day-first"), p["date_format"]
	assert p["ok"] == 3 and p["skipped"] == 1, (p["ok"], p["skipped"])
	assert "Presidential Villa" in p["issues"][0]["error"], p["issues"]
	assert p["sample"][0]["check_in"] == "2025-12-25", p["sample"][0]
	assert p["sample"][0]["amount_after_tax"] == 18500.0, p["sample"][0]

	r = migrate.run_import(P3, csv_text, "auto")
	assert r["created"] == 3 and r["history"] == 2, r
	assert len(r["errors"]) == 1, r["errors"]
	first = frappe.get_doc("Reservation", r["reservations"][0])
	# history keeps the vendor's final status and the fixed amount
	assert first.status == "Checked Out", first.status
	assert float(first.amount_after_tax) == 18500.0, first.amount_after_tax
	assert frappe.db.get_value("Guest", first.guest, "email") == "rao@x.in"
	# "Deluxe Room" fuzzy-resolved onto the Deluxe type
	second = frappe.get_doc("Reservation", r["reservations"][1])
	assert second.room_type == rt and second.status == "Cancelled", second


@check("kitchen display: chef context, post-fire void alert, recall undo")
def t38():
	from kamra import pos
	outlet = frappe.get_doc({
		"doctype": "POS Outlet", "property": P, "outlet_name": "Eval Kitchen",
		"outlet_type": "Restaurant", "gst_rate": 5,
	}).insert(ignore_permissions=True).name
	def _mi(name, station, veg, course="Main", allergens=None):
		return frappe.get_doc({
			"doctype": "Menu Item", "property": P, "outlet": outlet,
			"item_name": name, "category": "Food", "price": 100,
			"is_veg": veg, "available": 1, "prep_station": station,
			"course": course, "allergens": allergens,
		}).insert(ignore_permissions=True).name
	food = _mi("Eval Paneer", "Kitchen", 1)
	drink = _mi("Eval Lager", "Bar", 0)

	o = pos.create_order(outlet, [{"menu_item": food, "qty": 2, "instructions": "no onions"},
	                              {"menu_item": drink, "qty": 1}],
	                     table_no="T9", guests=3)
	# not fired yet: the kitchen must not see it
	assert not [r for r in pos.kitchen_queue(P, outlet=outlet)], "unfired order on the board"
	pos.fire_kot(o["order"])

	tick = next(r for r in pos.kitchen_queue(P, outlet=outlet) if r["name"] == o["order"])
	# the chef's context: ticket number, where it goes, who to ask
	assert tick["kot_no"] >= 1 and tick["order_type"] == "Dine In", tick
	assert tick["guests"] == 3 and tick["captain"], tick
	paneer = next(i for i in tick["items"] if i["item_name"] == "Eval Paneer")
	assert paneer["is_veg"] == 1 and paneer["state"] == "cooking", paneer
	assert paneer["instructions"] == "no onions", paneer
	# station routing splits food from drink
	assert [i["item_name"] for i in next(
		r for r in pos.kitchen_queue(P, outlet=outlet, station="Bar")
		if r["name"] == o["order"])["items"]] == ["Eval Lager"]

	# a line voided AFTER firing must shout, not vanish: the chef is cooking it
	rows = {i["item_name"]: i["row"] for i in pos.order_detail(o["order"])["items"]}
	pos.void_item(o["order"], rows["Eval Lager"], reason="guest changed mind")
	tick = next(r for r in pos.kitchen_queue(P, outlet=outlet) if r["name"] == o["order"])
	lager = next(i for i in tick["items"] if i["item_name"] == "Eval Lager")
	assert lager["state"] == "cancelled", lager
	assert lager["void_reason"] == "guest changed mind", lager

	# "all ready" must never mark cancelled food as cooked
	assert pos.mark_prepared(o["order"])["all_prepared"], "void blocked all_prepared"
	assert frappe.db.get_value("POS Order Item", rows["Eval Lager"], "kot_status") == "Fired"
	# the ack clears the alert, and with it the ticket
	pos.acknowledge_void(o["order"], rows["Eval Lager"])
	assert not [r for r in pos.kitchen_queue(P, outlet=outlet) if r["name"] == o["order"]]

	# a mis-tap is recoverable: recall puts the ticket back on the board
	pos.recall_prepared(o["order"])
	tick = next(r for r in pos.kitchen_queue(P, outlet=outlet) if r["name"] == o["order"])
	assert [i["state"] for i in tick["items"]] == ["cooking"], tick
	pos.mark_prepared(o["order"])
	# serving is the kitchen's mark_prepared; the bill closes on payment
	pos.pay_order(o["order"], "Cash")
	# once it has left the kitchen there is nothing to recall
	try:
		pos.recall_prepared(o["order"])
		raise AssertionError("recall allowed after delivery")
	except frappe.ValidationError:
		pass


@check("kitchen display: coursing holds & fires, cook's clock starts at fire, allergen alarm")
def t39():
	from frappe.utils import add_to_date, now_datetime

	from kamra import pos
	outlet = frappe.get_doc({
		"doctype": "POS Outlet", "property": P, "outlet_name": "Eval Pass",
		"outlet_type": "Restaurant", "gst_rate": 5,
	}).insert(ignore_permissions=True).name
	def _mi(name, course, station, allergens=None):
		return frappe.get_doc({
			"doctype": "Menu Item", "property": P, "outlet": outlet,
			"item_name": name, "category": "Food", "price": 100, "is_veg": 1,
			"available": 1, "prep_station": station, "course": course,
			"allergens": allergens,
		}).insert(ignore_permissions=True).name
	tikka = _mi("Pass Tikka", "Starter", "Tandoor")
	curry = _mi("Pass Curry", "Main", "Tandoor", "Nuts, Dairy")
	lager = _mi("Pass Lager", "Drink", "Bar")

	o = pos.create_order(outlet, [{"menu_item": tikka, "qty": 2},
	                              {"menu_item": curry, "qty": 1},
	                              {"menu_item": lager, "qty": 1}],
	                     table_no="C2", guests=2,
	                     allergy_note="nut allergy - child at the table")

	# coursing: only the starter goes; the rest is held where the chef can see it
	pos.fire_kot(o["order"], course="Starter")
	tick = next(r for r in pos.kitchen_queue(P, outlet=outlet) if r["name"] == o["order"])
	state = {i["item_name"]: i["state"] for i in tick["items"]}
	assert state == {"Pass Tikka": "cooking", "Pass Curry": "held",
	                 "Pass Lager": "held"}, state
	assert tick["held_courses"] == ["Main", "Drink"], tick["held_courses"]

	# the allergen alarm fires on the dish that contains it, and only that one
	curry_line = next(i for i in tick["items"] if i["item_name"] == "Pass Curry")
	assert curry_line["allergy_hits"] == ["Nuts"], curry_line["allergy_hits"]
	assert not next(i for i in tick["items"] if i["item_name"] == "Pass Tikka")["allergy_hits"]
	assert tick["allergy_note"], "guest's own words must ride along with the match"

	# THE COOK'S CLOCK: a tab opened an hour ago must not hand the kitchen a
	# ticket that is already late. Age runs from the fire, not the order.
	frappe.db.set_value("POS Order", o["order"], "creation",
	                    add_to_date(now_datetime(), hours=-1), update_modified=False)
	tick = next(r for r in pos.kitchen_queue(P, outlet=outlet) if r["name"] == o["order"])
	fired = next(i for i in tick["items"] if i["state"] == "cooking")["fired_at"]
	assert (now_datetime() - fired).total_seconds() < 120, "cook's clock inherited the tab's age"

	# each course keeps its own clock
	pos.mark_prepared(o["order"])
	frappe.db.set_value("POS Order Item", next(
		i["name"] for i in tick["items"] if i["item_name"] == "Pass Tikka"),
		"fired_at", add_to_date(now_datetime(), minutes=-30), update_modified=False)
	pos.fire_kot(o["order"], course="Main")
	tick = next(r for r in pos.kitchen_queue(P, outlet=outlet) if r["name"] == o["order"])
	main = next(i for i in tick["items"] if i["item_name"] == "Pass Curry")
	assert main["state"] == "cooking" and main["fired_at"], main
	assert (now_datetime() - main["fired_at"]).total_seconds() < 120, \
		"mains inherited the starter's clock"
	assert tick["held_courses"] == ["Drink"], tick["held_courses"]

	# a course already sent cannot be fired twice
	try:
		pos.fire_kot(o["order"], course="Main")
		raise AssertionError("re-fired a course that was already away")
	except frappe.ValidationError:
		pass

	# the floor can tell whether anyone has actually picked the ticket up
	assert not tick["accepted_at"], "ticket accepted before the kitchen touched it"
	assert tick["order_total"], "ticket carries no order value"
	pos.accept_ticket(o["order"])
	tick = next(r for r in pos.kitchen_queue(P, outlet=outlet) if r["name"] == o["order"])
	first_accept = tick["accepted_at"]
	assert first_accept, "accept did not stick"
	pos.accept_ticket(o["order"])  # accepting twice must not reset the clock
	tick = next(r for r in pos.kitchen_queue(P, outlet=outlet) if r["name"] == o["order"])
	assert tick["accepted_at"] == first_accept, "re-accept moved the timestamp"

	# station routing follows the course to its section
	bar = next(r for r in pos.kitchen_queue(P, outlet=outlet, station="Bar")
	           if r["name"] == o["order"])
	assert [i["item_name"] for i in bar["items"]] == ["Pass Lager"], bar["items"]
	assert bar["held_courses"] == ["Drink"], bar["held_courses"]

	# a menu written before coursing existed still fires with everything else
	legacy = _mi("Pass Legacy", "Main", "Kitchen")
	frappe.db.set_value("Menu Item", legacy, "course", None)
	o2 = pos.create_order(outlet, [{"menu_item": legacy, "qty": 1}], table_no="C9")
	pos.fire_kot(o2["order"], course="Main")
	t2 = next(r for r in pos.kitchen_queue(P, outlet=outlet) if r["name"] == o2["order"])
	assert t2["items"][0]["state"] == "cooking", "legacy line was held back forever"
	assert t2["items"][0]["course"] == "Main", t2["items"][0]["course"]


@check("POS: auto KOT accepts the ticket and tells the till to print")
def t39b():
	from kamra import pos, settings
	manual = frappe.get_doc({
		"doctype": "POS Outlet", "property": P, "outlet_name": "Manual Pass",
		"outlet_type": "Restaurant", "gst_rate": 5, "kot_mode": "Kitchen presses Start",
	}).insert(ignore_permissions=True).name
	auto = frappe.get_doc({
		"doctype": "POS Outlet", "property": P, "outlet_name": "Auto Pass",
		"outlet_type": "Restaurant", "gst_rate": 5, "kot_mode": "Auto-accept and print",
	}).insert(ignore_permissions=True).name
	follow = frappe.get_doc({
		"doctype": "POS Outlet", "property": P, "outlet_name": "Follow Pass",
		"outlet_type": "Restaurant", "gst_rate": 5,
	}).insert(ignore_permissions=True).name

	# The F&B setting drives outlets left on "Use F&B setting"; the
	# outlet's own choice beats it in both directions.
	def _flags():
		return {o.name: o.auto_kot for o in pos.outlets(P)}
	settings.save_settings(P, "fnb", {"pos_auto_kot": 0})
	f = _flags()
	assert (f[manual], f[auto], f[follow]) == (0, 1, 0), f
	settings.save_settings(P, "fnb", {"pos_auto_kot": 1})
	f = _flags()
	assert (f[manual], f[auto], f[follow]) == (0, 1, 1), f
	assert pos.outlet_auto_kot(follow) and not pos.outlet_auto_kot(manual)
	settings.save_settings(P, "fnb", {"pos_auto_kot": 0})

	def _mi(outlet, name):
		return frappe.get_doc({
			"doctype": "Menu Item", "property": P, "outlet": outlet,
			"item_name": name, "category": "Food", "price": 80, "is_veg": 1,
			"available": 1, "prep_station": "Kitchen", "course": "Main",
		}).insert(ignore_permissions=True).name

	dish_m = _mi(manual, "Manual Dal")
	dish_a = _mi(auto, "Auto Dal")
	om = pos.create_order(manual, [{"menu_item": dish_m, "qty": 1}], table_no="M1")
	oa = pos.create_order(auto, [{"menu_item": dish_a, "qty": 1}], table_no="A1")

	fm = pos.fire_kot(om["order"])
	assert fm["auto_print"] is False, fm
	tick_m = next(r for r in pos.kitchen_queue(P, outlet=manual) if r["name"] == om["order"])
	assert not tick_m["accepted_at"], "manual outlet accepted itself"
	assert tick_m["items"][0]["state"] == "cooking", tick_m

	fa = pos.fire_kot(oa["order"])
	assert fa["auto_print"] is True and fa["accepted_at"], fa
	assert fa["ticket"]["items"][0]["item_name"] == "Auto Dal", fa
	tick_a = next(r for r in pos.kitchen_queue(P, outlet=auto) if r["name"] == oa["order"])
	assert tick_a["accepted_at"], "auto outlet still waiting on Start"
	# a second round must not move the accept clock
	stamp = frappe.db.get_value("POS Order", oa["order"], "accepted_at")
	pos.add_items(oa["order"], [{"menu_item": dish_a, "qty": 1}])
	fa2 = pos.fire_kot(oa["order"])
	assert fa2["auto_print"] is True, fa2
	assert frappe.db.get_value("POS Order", oa["order"], "accepted_at") == stamp, \
		"second fire reset the accept time"


@check("POS: send_order / send_round = the multi-call path in one request and one save")
def t39c():
	from kamra import pos
	outlet = frappe.get_doc({
		"doctype": "POS Outlet", "property": P, "outlet_name": "Speed Pass",
		"outlet_type": "Restaurant", "gst_rate": 5, "kot_mode": "Kitchen presses Start",
	}).insert(ignore_permissions=True).name
	auto = frappe.get_doc({
		"doctype": "POS Outlet", "property": P, "outlet_name": "Speed Auto",
		"outlet_type": "Restaurant", "gst_rate": 5, "kot_mode": "Auto-accept and print",
	}).insert(ignore_permissions=True).name

	def _mi(o, name, price):
		return frappe.get_doc({
			"doctype": "Menu Item", "property": P, "outlet": o, "item_name": name,
			"category": "Food", "price": price, "is_veg": 1, "available": 1,
			"prep_station": "Kitchen", "course": "Main",
		}).insert(ignore_permissions=True).name
	dal, roti = _mi(outlet, "Speed Dal", 100), _mi(outlet, "Speed Roti", 20)

	# the old path: four calls
	old = pos.create_order(outlet, [{"menu_item": dal, "qty": 2}], table_no="S1")["order"]
	pos.apply_discount(old, 30, "")
	pos.confirm_order(old)
	f_old = pos.fire_kot(old)
	# the new path: one call
	r = pos.send_order(outlet, [{"menu_item": dal, "qty": 2}], table_no="S2",
	                   discount=30)
	new = frappe.get_doc("POS Order", r["order"])
	ref = frappe.get_doc("POS Order", old)
	for f in ("status", "order_total", "discount_amount", "kot_fired", "captain"):
		assert new.get(f) == ref.get(f), (f, new.get(f), ref.get(f))
	assert new.status == "Preparing" and new.order_total == 170, (new.status, new.order_total)
	assert r["kot_no"] == f_old["kot_no"] + 1, (r["kot_no"], f_old["kot_no"])
	assert r["fired_items"] == f_old["fired_items"], r["fired_items"]
	assert all(it.kot_status == "Fired" and it.fired_at for it in new.items)
	assert not new.accepted_at and r["auto_print"] is False, "manual outlet accepted itself"
	assert frappe.db.count("Version", {"ref_doctype": "POS Order", "docname": new.name}) <= 1, \
		"send_order saved the order more than once"

	# a round: add + fire in one save, the new line named and fired
	before = frappe.db.count("Version", {"ref_doctype": "POS Order", "docname": new.name})
	rr = pos.send_round(new.name, [{"menu_item": roti, "qty": 3}])
	assert [i["item_name"] for i in rr["fired_items"]] == ["Speed Roti"], rr["fired_items"]
	assert rr["order_total"] == 230, rr["order_total"]
	new.reload()
	roti_row = next(it for it in new.items if it.menu_item == roti)
	assert roti_row.name and roti_row.kot_status == "Fired" and roti_row.fired_at, roti_row.as_dict()
	assert frappe.db.count("Version", {"ref_doctype": "POS Order", "docname": new.name}) - before <= 1, \
		"send_round saved the order more than once"
	try:
		pos.send_round(new.name, [])
		raise AssertionError("an empty round was sent")
	except frappe.ValidationError:
		pass

	# auto KOT is honoured on the fast path too
	ra = pos.send_order(auto, [{"menu_item": _mi(auto, "Speed Auto Dal", 90), "qty": 1}], table_no="A9")
	assert ra["auto_print"] is True and ra["accepted_at"], ra

	# the speed check is read-only and answers
	sc = pos.speed_check(P, outlet=outlet)
	assert "kitchen_display_ms" in sc["server"] and "background_workers" in sc["setup"], sc


@check("kitchen printers: KOTs split by outlet and station, stations claim and ack, fallback, void slips")
def t39d():
	import json as _json

	from kamra import pos, printing, settings

	def _outlet(name):
		return frappe.get_doc({"doctype": "POS Outlet", "property": P, "outlet_name": name,
		                       "outlet_type": "Restaurant", "gst_rate": 5,
		                       "kot_mode": "Kitchen presses Start"}).insert(ignore_permissions=True).name

	def _mi(o, name, station):
		return frappe.get_doc({"doctype": "Menu Item", "property": P, "outlet": o, "item_name": name,
		                       "category": "Food", "price": 50, "is_veg": 1, "available": 1,
		                       "prep_station": station, "course": "Main"}).insert(ignore_permissions=True).name

	# start from a property with no printers: the till prints everything
	for name in frappe.get_all("Kitchen Printer", filters={"property": P}, pluck="name"):
		frappe.delete_doc("Kitchen Printer", name, ignore_permissions=True, force=True)
	a, b = _outlet("Print A"), _outlet("Print B")
	dal, beer = _mi(a, "PA Dal", "Kitchen"), _mi(a, "PA Beer", "Bar")
	roti, juice = _mi(b, "PB Roti", "Kitchen"), _mi(b, "PB Juice", "Bar")
	r0 = pos.send_order(a, [{"menu_item": dal, "qty": 1}], table_no="X0")
	assert r0["print_jobs"] == [] and len(r0["till_ticket"]["items"]) == 1, r0

	# Main Kitchen serves all of A and B's kitchen; Bar serves A's bar only
	bar = printing.save_printer(P, {"printer_name": "Eval Bar", "routes": [
		{"outlet": a, "prep_station": "Bar"}]})["name"]
	main = printing.save_printer(P, {"printer_name": "Eval Main", "copies": 2, "routes": [
		{"outlet": a, "prep_station": ""}, {"outlet": b, "prep_station": "Kitchen"}]})["name"]
	printing.save_printer(P, {"printer_name": "Eval Bar", "fallback_printer": main, "routes": [
		{"outlet": a, "prep_station": "Bar"}]}, name=bar)

	ra = pos.send_order(a, [{"menu_item": dal, "qty": 2}, {"menu_item": beer, "qty": 1}], table_no="X1")
	got = {j["printer"]: j["items"] for j in ra["print_jobs"]}
	# Main serves ALL stations at A, so it gets the beer too; Bar gets the beer
	assert got == {main: 2, bar: 1}, got
	assert ra["till_ticket"]["items"] == [] and ra["auto_print"] is False, ra

	rb = pos.send_order(b, [{"menu_item": roti, "qty": 1}, {"menu_item": juice, "qty": 1}], table_no="X2")
	assert [j["printer"] for j in rb["print_jobs"]] == [main], rb["print_jobs"]
	assert [i["item_name"] for i in rb["till_ticket"]["items"]] == ["PB Juice"], rb["till_ticket"]

	# the station claims Main's work once; a second claim gets nothing
	jobs = printing.claim_jobs(main)
	assert len(jobs) == 2, [j["ticket"]["items"] for j in jobs]
	t0 = jobs[0]["ticket"]
	assert t0["outlet"] and t0["copies"] == 2 and t0["kot_no"], t0
	assert printing.claim_jobs(main) == [], "a claimed job was handed out twice"
	printing.ack_jobs(main, printed=_json.dumps([j["job"] for j in jobs]))
	assert all(frappe.db.get_value("Print Job", j["job"], "status") == "Printed" for j in jobs)
	ps = {p.name: p for p in printing.printers(P)}
	assert ps[main].online is True and ps[main].queued == 0, ps[main]
	assert ps[bar].online is False and ps[bar].queued == 1, ps[bar]

	# Bar fails: its ticket moves to Main, marked as being for the Bar
	bj = printing.claim_jobs(bar)
	printing.ack_jobs(bar, failed=_json.dumps([bj[0]["job"]]), error="paper out")
	assert frappe.db.get_value("Print Job", bj[0]["job"], "status") == "Failed"
	moved = printing.claim_jobs(main)
	assert len(moved) == 1 and moved[0]["ticket"]["fallback_from"] == "Eval Bar", moved
	printing.ack_jobs(main, printed=_json.dumps([moved[0]["job"]]))

	# a fired line voided prints a VOID slip where it was cooked
	row = next(it.name for it in frappe.get_doc("POS Order", ra["order"]).items if it.menu_item == dal)
	pos.void_item(ra["order"], row, "guest changed mind")
	void = printing.claim_jobs(main)
	assert [j["kind"] for j in void] == ["Void"], void
	assert void[0]["ticket"]["items"][0]["item_name"] == "PA Dal", void[0]["ticket"]
	# ...unless the property turned void slips off
	settings.save_settings(P, "fnb", {"pos_print_void_slips": 0})
	pos.cancel_order(rb["order"], "walked out")
	assert printing.claim_jobs(main) == [], "void slip printed with the setting off"
	settings.save_settings(P, "fnb", {"pos_print_void_slips": 1})

	# test page, reprint, guards
	printing.test_print(main)
	tj = printing.claim_jobs(main)
	assert [j["kind"] for j in tj] == ["Test"], tj
	rp = printing.reprint(jobs[0]["job"], printer=bar)["job"]
	assert _json.loads(frappe.db.get_value("Print Job", rp, "payload"))["reprint"] is True
	for bad, msg in (({"printer_name": ""}, "no name"),
	                 ({"printer_name": "X", "connection": "Direct IP"}, "Direct IP without an address"),
	                 ({"printer_name": "X", "routes": [{"outlet": "nope"}]}, "a foreign outlet"),
	                 ({"printer_name": "Eval Main"}, "a duplicate name")):
		try:
			printing.save_printer(P, bad)
			raise AssertionError(f"saved a printer with {msg}")
		except frappe.ValidationError:
			pass
	try:
		printing.claim_jobs(frappe.get_doc({"doctype": "Kitchen Printer", "property": P,
		                                    "printer_name": "Eval IP", "connection": "Direct IP",
		                                    "ip_address": "127.0.0.1"}).insert(ignore_permissions=True).name)
		raise AssertionError("a Direct IP printer was claimed by a screen")
	except frappe.ValidationError:
		pass

	# Direct IP: ESC/POS bytes, and an unreachable printer fails over
	raw = printing.escpos({"outlet": "A", "kot_no": 7, "items": [{"item_name": "Dal", "qty": 2}]})
	assert raw.startswith(b"\x1b@") and b"KOT 7" in raw and b"Dal" in raw and raw.endswith(b"\x1dV\x41\x03"), raw
	ip = printing.save_printer(P, {"printer_name": "Eval Dead IP", "connection": "Direct IP",
	                               "ip_address": "127.0.0.1", "port": 9, "fallback_printer": main})["name"]
	job = frappe.get_doc({"doctype": "Print Job", "property": P, "printer": ip, "kind": "KOT",
	                      "status": "Queued", "payload": frappe.as_json({"kot_no": 1, "items": []})}
	                     ).insert(ignore_permissions=True).name
	printing.print_direct(job)
	assert frappe.db.get_value("Print Job", job, "status") == "Failed", "unreachable printer printed"
	assert len(printing.claim_jobs(main)) == 1, "the failed IP job did not move to the fallback"


@check("kitchen stock: fire deducts per outlet, shortage never blocks, ledger reconciles")
def t40():
	from kamra import inventory, pos
	kitchen = frappe.get_doc({
		"doctype": "POS Outlet", "property": P, "outlet_name": "Stock Kitchen",
		"outlet_type": "Restaurant", "gst_rate": 5,
	}).insert(ignore_permissions=True).name
	bar = frappe.get_doc({
		"doctype": "POS Outlet", "property": P, "outlet_name": "Stock Bar",
		"outlet_type": "Bar", "gst_rate": 18,
	}).insert(ignore_permissions=True).name

	def _ing(name, uom, cost):
		return frappe.get_doc({
			"doctype": "Ingredient", "property": P, "ingredient_name": name,
			"uom": uom, "cost_per_unit": cost, "is_active": 1,
		}).insert(ignore_permissions=True).name
	paneer = _ing("Stock Paneer", "kg", 400)
	chicken = _ing("Stock Chicken", "kg", 320)

	def _dish(name, outlet, course, recipe):
		return frappe.get_doc({
			"doctype": "Menu Item", "property": P, "outlet": outlet,
			"item_name": name, "category": "Food", "price": 300, "is_veg": 1,
			"available": 1, "prep_station": "Kitchen", "course": course,
			"recipe": [{"ingredient": i, "qty": q} for i, q in recipe],
		}).insert(ignore_permissions=True).name
	tikka = _dish("Stock Tikka", kitchen, "Starter", [(paneer, 0.2)])
	curry = _dish("Stock Curry", kitchen, "Main", [(chicken, 0.25)])
	water = _dish("Stock Water", kitchen, "Drink", [])  # no recipe, on purpose

	def _bal(outlet, ing):
		return frappe.db.get_value("Ingredient Stock", f"{outlet}::{ing}", "qty_on_hand")

	inventory.receive_stock(P, kitchen, [{"ingredient": paneer, "qty": 1.0}],
	                        supplier="Eval Farm")
	assert _bal(kitchen, paneer) == 1.0, _bal(kitchen, paneer)
	assert frappe.db.exists("Ingredient Ledger Entry",
	                        {"ingredient": paneer, "reason": "Received",
	                         "balance_after": 1.0}), "receipt left no ledger row"

	# firing is what moves stock - the chef starting to cook, not the bill
	o = pos.create_order(kitchen, [{"menu_item": tikka, "qty": 2}], table_no="S1")
	assert _bal(kitchen, paneer) == 1.0, "stock moved before the KOT fired"
	pos.fire_kot(o["order"])
	assert abs(_bal(kitchen, paneer) - 0.6) < 1e-9, _bal(kitchen, paneer)

	# stock is per outlet: the bar's paneer is not the kitchen's paneer
	assert _bal(bar, paneer) is None, "firing at one outlet touched another"

	# nothing but a fire moves stock: prepare/recall/prepare must be inert
	before = _bal(kitchen, paneer)
	pos.mark_prepared(o["order"])
	pos.recall_prepared(o["order"])
	pos.mark_prepared(o["order"])
	assert _bal(kitchen, paneer) == before, "a non-fire transition moved stock"

	# A SHORT COUNT MUST NEVER STOP SERVICE. The chef has the paneer in hand;
	# it is the number that is wrong. Fire, go negative, say so loudly.
	o2 = pos.create_order(kitchen, [{"menu_item": tikka, "qty": 10}], table_no="S2")
	r2 = pos.fire_kot(o2["order"])
	assert r2["ok"] and frappe.db.get_value("POS Order", o2["order"], "status") == "Preparing", r2
	assert all(i.kot_status == "Fired"
	           for i in frappe.get_doc("POS Order", o2["order"]).items), "a short count blocked the KOT"
	assert _bal(kitchen, paneer) < 0, _bal(kitchen, paneer)
	assert any(a["level"] == "negative" for a in r2["stock_alerts"]), r2["stock_alerts"]

	# coursing: a held course is still on the shelf and must not be deducted
	o3 = pos.create_order(kitchen, [{"menu_item": tikka, "qty": 1},
	                                {"menu_item": curry, "qty": 1}], table_no="S3")
	inventory.receive_stock(P, kitchen, [{"ingredient": chicken, "qty": 5.0}])
	pos.fire_kot(o3["order"], course="Starter")
	assert _bal(kitchen, chicken) == 5.0, "firing the starter consumed the main"
	pos.fire_kot(o3["order"], course="Main")
	assert abs(_bal(kitchen, chicken) - 4.75) < 1e-9, _bal(kitchen, chicken)
	# and the starter is not deducted a second time by the main's fire
	starter_moves = frappe.db.count(
		"Ingredient Ledger Entry",
		{"ingredient": paneer, "reference_name": o3["order"], "reason": "Consumed"})
	assert starter_moves == 1, f"starter deducted {starter_moves} times"

	# the optional in "optional recipe": no recipe, no ledger, no noise
	rows_before = frappe.db.count("Ingredient Ledger Entry")
	o4 = pos.create_order(kitchen, [{"menu_item": water, "qty": 3}], table_no="S4")
	r4 = pos.fire_kot(o4["order"])
	assert frappe.db.count("Ingredient Ledger Entry") == rows_before, "a recipe-less dish moved stock"
	assert r4["stock_alerts"] == [], r4["stock_alerts"]

	# the cache must never drift from the ledger - the one invariant that
	# cannot bend, because every other number here is derived from it
	for outlet, ing in ((kitchen, paneer), (kitchen, chicken)):
		total = frappe.db.sql(
			"""select sum(qty_change) from `tabIngredient Ledger Entry`
			   where outlet=%s and ingredient=%s""", (outlet, ing))[0][0] or 0
		assert abs(_bal(outlet, ing) - float(total)) < 1e-9, \
			f"{ing} balance {_bal(outlet, ing)} != ledger {total}"


@check("kitchen stock: post-fire void is wastage not a reversal, count is an explicit decision, no auto-86")
def t41():
	from kamra import inventory, pos
	outlet = frappe.get_doc({
		"doctype": "POS Outlet", "property": P, "outlet_name": "Waste Kitchen",
		"outlet_type": "Restaurant", "gst_rate": 5,
	}).insert(ignore_permissions=True).name
	paneer = frappe.get_doc({
		"doctype": "Ingredient", "property": P, "ingredient_name": "Waste Paneer",
		"uom": "kg", "cost_per_unit": 400, "is_active": 1,
	}).insert(ignore_permissions=True).name
	tikka = frappe.get_doc({
		"doctype": "Menu Item", "property": P, "outlet": outlet,
		"item_name": "Waste Tikka", "category": "Food", "price": 300,
		"is_veg": 1, "available": 1, "prep_station": "Tandoor", "course": "Starter",
		"recipe": [{"ingredient": paneer, "qty": 0.2}],
	}).insert(ignore_permissions=True).name

	def _bal():
		return frappe.db.get_value("Ingredient Stock", f"{outlet}::{paneer}", "qty_on_hand")

	inventory.receive_stock(P, outlet, [{"ingredient": paneer, "qty": 5.0}])

	# HEAT IS IRREVERSIBLE. A line voided after firing was cooked and binned:
	# the paneer is gone whatever the bill says. Putting it back would be a
	# lie that only surfaces at the next stock take.
	o = pos.create_order(outlet, [{"menu_item": tikka, "qty": 2}], table_no="V1")
	pos.fire_kot(o["order"])
	after_fire = _bal()
	row = pos.order_detail(o["order"])["items"][0]["row"]
	pos.void_item(o["order"], row, reason="guest changed mind")
	assert _bal() == after_fire, "a post-fire void reversed stock"
	assert frappe.db.get_value("POS Order Item", row, "stock_posted") == 1
	pos.acknowledge_void(o["order"], row)
	assert _bal() == after_fire, "acknowledging a void moved stock"

	# it surfaces as wastage instead - derived from the Consumed row that is
	# already there, never a second ledger entry that would deduct twice
	wr = inventory.wastage_report(P, outlet)
	assert wr["total_value"] > 0, wr
	assert wr["by_reason"][0]["reason"] == "guest changed mind", wr["by_reason"]

	# spoilage is the opposite case: no POS line exists, so only a real
	# Wastage row can say the stock left
	before = _bal()
	inventory.record_wastage(P, outlet, paneer, 0.5, "crate spoiled")
	assert abs(_bal() - (before - 0.5)) < 1e-9, _bal()
	assert frappe.db.exists("Ingredient Ledger Entry",
	                        {"ingredient": paneer, "reason": "Wastage"})

	# a cancelled order does not un-cook what was already fired
	o2 = pos.create_order(outlet, [{"menu_item": tikka, "qty": 1}], table_no="V2")
	pos.fire_kot(o2["order"])
	held = _bal()
	pos.cancel_order(o2["order"], reason="table walked")
	assert _bal() == held, "cancelling an order reversed cooked food"

	# a split moves food that is already cooked and already deducted; the
	# copied stock_posted flag is what stops the new bill deducting again
	o3 = pos.create_order(outlet, [{"menu_item": tikka, "qty": 1},
	                               {"menu_item": tikka, "qty": 1}], table_no="V3")
	pos.fire_kot(o3["order"])
	pre_split = _bal()
	rows = [i["row"] for i in pos.order_detail(o3["order"])["items"]]
	split = pos.split_order(o3["order"], [rows[0]], table_no="V4")
	assert _bal() == pre_split, "splitting a bill deducted the food twice"
	new_rows = pos.order_detail(split["new_order"])["items"]
	assert all(frappe.db.get_value("POS Order Item", i["row"], "stock_posted") == 1
	           for i in new_rows), "split lines lost their stock_posted flag"

	# THE ESCAPE HATCH: a count is how a human corrects everything the system
	# cannot know. It demands a note - a write-off without a reason is exactly
	# the silence this module exists to remove.
	try:
		inventory.adjust_stock(P, outlet, [{"ingredient": paneer, "counted_qty": 3}],
		                       note="   ")
		raise AssertionError("a stock take was accepted with no note")
	except frappe.ValidationError:
		pass
	res = inventory.adjust_stock(P, outlet, [{"ingredient": paneer, "counted_qty": 3.0}],
	                             note="recount after delivery")
	assert _bal() == 3.0, _bal()
	assert res["adjusted"][0]["variance"], res
	assert frappe.db.exists("Ingredient Ledger Entry",
	                        {"ingredient": paneer, "reason": "Count"})
	assert frappe.db.get_value("Ingredient Stock", f"{outlet}::{paneer}",
	                           "last_counted_at"), "a count left no counted-at stamp"

	# NOTHING AUTO-86s. The count is the least trustworthy number in the
	# building; a stale one must never silently hide a dish the kitchen can
	# actually cook. Flag it, name the dishes it threatens, let a human decide.
	o5 = pos.create_order(outlet, [{"menu_item": tikka, "qty": 30}], table_no="V5")
	pos.fire_kot(o5["order"])
	assert _bal() < 0, _bal()
	assert frappe.db.get_value("Menu Item", tikka, "available") == 1, \
		"an ingredient hitting zero auto-86'd a dish"
	low = [r for r in inventory.low_stock(P, outlet) if r["ingredient"] == paneer]
	assert low and low[0]["status"] == "NEGATIVE", low
	assert any(d["name"] == tikka for d in low[0]["dishes"]), \
		"the flag does not name the dish it takes down"
	# and the 86 itself is a deliberate human act
	inventory.set_menu_availability(tikka, 0)
	assert frappe.db.get_value("Menu Item", tikka, "available") == 0

	# looking is not moving: Front Desk reads stock, Finance moves it
	me = frappe.session.user
	try:
		frappe.set_user("frontdesk@kamra.local")  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow
		inventory.stock_list(P, outlet)  # allowed
		try:
			inventory.receive_stock(P, outlet, [{"ingredient": paneer, "qty": 1}])
			raise AssertionError("Front Desk was allowed to receive stock")
		except frappe.PermissionError:
			pass
	finally:
		frappe.set_user(me)  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow


def _id_photo(colour=(180, 40, 40)):
	"""A real PNG data URL, built in memory - no fixture file to go missing."""
	import base64
	import io

	from PIL import Image
	buf = io.BytesIO()
	Image.new("RGB", (48, 30), colour).save(buf, format="PNG")
	return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _id_files(reservation):
	return frappe.get_all("File", filters={
		"attached_to_doctype": "Reservation", "attached_to_name": reservation,
		"attached_to_field": "id_document"}, pluck="name")


@check("ID document: private storage, token gate, never blocks check-in, discarded at checkout")
def t42():
	import base64

	from kamra import api
	from kamra import public_api as pub
	g = _guest("ID Doc Guest", "+91 70000 00038")
	res = _res(g, "2035-02-01", "2035-02-03", ROOM)
	token = frappe.db.get_value("Reservation", res.name, "precheckin_token")
	assert token and len(token) >= 20, "a booking minted no pre-check-in token"

	# the guest uploads with nothing but the link they were sent
	pub.precheckin_upload_id(token, _id_photo())
	files = _id_files(res.name)
	assert len(files) == 1, files
	f = frappe.get_doc("File", files[0])
	# THE assertion: an ID scan is never reachable without a session. Frappe's
	# own upload_file would have taken is_private from the client.
	assert f.is_private == 1, "the ID scan is world-readable"
	assert f.file_url.startswith("/private/files/"), f.file_url
	assert f.owner == pub.GUEST_AGENT, f.owner
	assert frappe.db.get_value("Reservation", res.name, "id_document") == f.file_url
	assert frappe.db.get_value("Reservation", res.name, "id_document_source") == "Guest"

	# the guest page is told a boolean, never a path - a read-back would only
	# be a brute-force oracle for the token
	info = pub.precheckin_info(token)
	assert info["guest"]["has_id_document"] is True, info["guest"]
	assert not any("private/files" in str(v) for v in info["guest"].values()), info["guest"]

	# a bad link buys nothing
	for bad in ("z" * 24, "short"):
		try:
			pub.precheckin_upload_id(bad, _id_photo())
			raise AssertionError(f"upload accepted the token {bad!r}")
		except frappe.ValidationError:
			pass

	# re-encoding is the boundary: a payload wearing a JPEG's name dies, and
	# leaves nothing behind
	before = len(_id_files(res.name))
	try:
		pub.precheckin_upload_id(token, "data:image/jpeg;base64," +
		                         base64.b64encode(b"<?php system($_GET[0]); ?>").decode())
		raise AssertionError("a PHP payload was stored as an ID")
	except frappe.ValidationError:
		pass
	assert len(_id_files(res.name)) == before, "a rejected upload still wrote a File"
	try:
		pub.precheckin_upload_id(token, "data:image/png;base64," + ("A" * (6 * 1024 * 1024)))
		raise AssertionError("an oversize photo was stored")
	except frappe.ValidationError:
		pass

	# what we store is a JPEG we wrote, with the guest's home GPS stripped out
	import io as _io

	from PIL import Image as _Image
	stored = _Image.open(_io.BytesIO(frappe.get_doc("File", _id_files(res.name)[0]).get_content()))
	assert stored.format == "JPEG", stored.format
	assert not (stored.getexif() or {}), "EXIF survived - GPS may ride on the scan"

	# one scan per booking: replace, never append
	old = _id_files(res.name)[0]
	pub.precheckin_upload_id(token, _id_photo((20, 90, 20)))
	assert len(_id_files(res.name)) == 1, "a second upload appended instead of replacing"
	assert not frappe.db.exists("File", old), "the replaced file was left on disk"

	# A MISSING DOCUMENT MUST NEVER BLOCK AN ARRIVAL. This is the regression
	# test for that promise: it exists so a future `and bool(res.id_document)`
	# in can_check_in goes red instead of stranding a guest at the counter.
	frappe.db.set_value("Reservation", res.name, "id_document", None)
	d = api.reservation_detail(res.name)
	assert d["warnings"]["id_document_missing"] is True, d["warnings"]
	assert d["actions"]["can_check_in"] is True, "a missing ID blocked check-in"
	api.check_in(res.name, ROOM)
	assert frappe.db.get_value("Reservation", res.name, "status") == "Checked In"
	frappe.db.set_value("Reservation", res.name, "id_document",
	                    frappe.db.get_value("File", _id_files(res.name)[0], "file_url"))

	# Verify & Discard: the scan leaves with the guest. Masking the number
	# while a photo of the same card sat on disk would make the setting a lie.
	frappe.db.set_value("Property", P, "id_retention", "Verify & Discard")
	try:
		_checkout_unsettled(res.name)
	finally:
		frappe.db.set_value("Property", P, "id_retention", "Store")
	assert _id_files(res.name) == [], "the ID scan survived a Verify & Discard checkout"
	assert frappe.db.get_value("Reservation", res.name, "id_document") is None
	assert frappe.db.get_value("Reservation", res.name, "id_document_discarded") == 1, \
		"nothing records that the scan was discarded on purpose"
	# the pre-existing number masking still works alongside it
	assert str(frappe.db.get_value("Guest", g, "id_number") or "").startswith("•") \
		or not frappe.db.get_value("Guest", g, "id_number")

	# Store mode keeps both - the property chose to hold the register
	g2 = _guest("ID Keep Guest", "+91 70000 00039")
	res2 = _res(g2, "2035-03-01", "2035-03-03", ROOM)
	tok2 = frappe.db.get_value("Reservation", res2.name, "precheckin_token")
	pub.precheckin_upload_id(tok2, _id_photo())
	api.check_in(res2.name, ROOM)
	_checkout_unsettled(res2.name)
	assert len(_id_files(res2.name)) == 1, "Store mode discarded the scan anyway"
	for n in _id_files(res2.name):  # this one has no retention to clean it up
		frappe.delete_doc("File", n, ignore_permissions=True, delete_permanently=True)


@check("ID document: desk captures and verifies, roles gate the look")
def t43():
	from kamra import api, id_documents
	from kamra import public_api as pub
	g = _guest("ID Verify Guest", "+91 70000 00040")
	res = _res(g, "2035-04-01", "2035-04-03", ROOM)
	token = frappe.db.get_value("Reservation", res.name, "precheckin_token")

	# the desk captures at the counter for a guest who never uploaded
	frappe.set_user("frontdesk@kamra.local")  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow
	try:
		api.upload_id_document(res.name, _id_photo())
		assert frappe.db.get_value("Reservation", res.name, "id_document_source") == "Desk"
		f = frappe.get_doc("File", _id_files(res.name)[0])
		assert f.is_private == 1, "the desk's capture is world-readable"

		# the image is served through the role gate, not its private URL: this
		# site's Custom DocPerm rows omit Front Desk, so Frappe's own File
		# permission would deny the very people who must look at it
		img = api.id_document_image(res.name)
		assert img["data"].startswith("data:image/jpeg;base64,"), img["data"][:30]

		# verify makes precheckin_status="Verified" real - no code path ever
		# wrote that enum before
		frappe.db.set_value("Reservation", res.name, "precheckin_status", "Submitted")
		api.verify_precheckin(res.name)
		assert frappe.db.get_value("Reservation", res.name, "precheckin_status") == "Verified"
		assert frappe.db.get_value("Reservation", res.name,
		                           "precheckin_verified_by") == "frontdesk@kamra.local"
		assert frappe.db.get_value("Reservation", res.name, "precheckin_verified_on")
		try:
			api.verify_precheckin(res.name)
			raise AssertionError("a verified booking was verified twice")
		except frappe.ValidationError:
			pass
	finally:
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow

	# once the desk has checked the card, the guest cannot quietly swap it
	try:
		pub.precheckin_upload_id(token, _id_photo())
		raise AssertionError("the guest replaced the ID after it was verified")
	except frappe.ValidationError:
		pass

	# looking is not everyone's business
	frappe.set_user("hk@kamra.local")  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow
	try:
		for fn, args in (("id_document_image", (res.name,)),
		                 ("verify_precheckin", (res.name,)),
		                 ("upload_id_document", (res.name, _id_photo()))):
			try:
				getattr(api, fn)(*args)
				raise AssertionError(f"housekeeping was allowed to call {fn}")
			except frappe.PermissionError:
				pass
	finally:
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow

	# the harness rolls the DB back but save_file wrote real bytes to disk;
	# clean up after ourselves rather than leaving them for the runner
	id_documents.discard_id_document(res.name)
@check("pre-checkin: ID photo stored privately, discarded at checkout per policy")
def t34():
	import base64

	from kamra import api, public_api

	idroom = frappe.db.exists("Room", {"property": P, "room_number": "E103"})
	if not idroom:
		idroom = frappe.get_doc({
			"doctype": "Room", "property": P, "room_number": "E103",
			"room_type": RT,
		}).insert(ignore_permissions=True).name
	else:
		frappe.db.set_value("Room", idroom, "room_type", RT)
	g = _guest("Eval IdPhoto", "+91 70000 00034")
	res = _res(g, nowdate(), add_days(nowdate(), 1), idroom)
	tok = frappe.generate_hash(length=32)
	frappe.db.set_value("Reservation", res.name, "precheckin_token", tok)

	# a real (tiny) JPEG - frappe's File doctype runs PIL over uploads
	from io import BytesIO

	from PIL import Image
	buf = BytesIO()
	Image.new("RGB", (8, 8), (200, 180, 40)).save(buf, format="JPEG")
	jpg = base64.b64encode(buf.getvalue()).decode()
	frappe.set_user("Guest")  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow
	try:
		public_api.precheckin_submit(
			tok, "Aadhaar", "987654321012", email="id@x.in", consent=0,
			id_image=f"data:image/jpeg;base64,{jpg}")
		# junk uploads are refused
		try:
			public_api.precheckin_submit(
				tok, "Aadhaar", "987654321012",
				id_image="data:text/html;base64,PGI+")
			raise AssertionError("non-image ID accepted")
		except frappe.exceptions.ValidationError:
			pass
	finally:
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow

	f = frappe.get_all("File", filters={
		"attached_to_doctype": "Guest", "attached_to_name": g,
		"attached_to_field": "id_file"},
		fields=["name", "is_private", "file_url"])
	assert len(f) == 1 and f[0].is_private == 1, f
	assert frappe.db.get_value("Guest", g, "id_file") == f[0].file_url

	# the GRC shows the document to the desk
	card = api.registration_card(res.name)
	assert card["guest"]["id_file"] == f[0].file_url, card["guest"]

	# Verify & Discard: checkout masks the number AND deletes the photo
	frappe.db.set_value("Property", P, "id_retention", "Verify & Discard")
	res.reload()
	res.status = "Checked In"
	res.save(ignore_permissions=True)
	_checkout_unsettled(res.name)  # the desk path - runs the retention scrub
	assert frappe.db.get_value("Guest", g, "id_number").startswith("•"), \
		frappe.db.get_value("Guest", g, "id_number")
	assert not frappe.db.get_value("Guest", g, "id_file")
	assert not frappe.get_all("File", filters={
		"attached_to_doctype": "Guest", "attached_to_name": g,
		"attached_to_field": "id_file"})
	frappe.db.set_value("Property", P, "id_retention", "Store")


@check("laundry rates: CSV bulk import upserts by item+service, refuses junk")
def t35():
	from kamra import laundry

	laundry.save_laundry_rate(P, "Shirt", "Wash & Iron", 60)
	csv_text = (
		"Item,Service,Rate,Express Rate\n"
		"Shirt,Wash & Iron,75,\n"          # update (blank express -> 1.5x)
		'"Blazer, Wool",Dry Clean,300,450\n'  # create, quoted comma
		"Cap,dry clean,90,\n"               # alias-cased service -> create
		"Ghost,Boiling,50,\n"               # bad service -> skipped
		"NoRate,Iron Only,,\n")             # missing rate -> skipped
	out = laundry.import_laundry_rates(P, csv_text)
	assert out["created"] == 2 and out["updated"] == 1, out
	assert len(out["issues"]) == 2, out["issues"]
	rates = {(r["item_name"], r["service_type"]): r
	         for r in laundry.laundry_rates(P)}
	assert rates[("Shirt", "Wash & Iron")]["rate"] == 75
	assert rates[("Blazer, Wool", "Dry Clean")]["express_rate"] == 450
	assert ("Cap", "Dry Clean") in rates


@check("guest documents: address proof + staff upload + both discarded per policy")
def t36():
	import base64
	from io import BytesIO

	from PIL import Image

	from kamra import api, public_api

	def img64():
		buf = BytesIO()
		Image.new("RGB", (8, 8), (10, 20, 30)).save(buf, format="JPEG")
		return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

	docroom = frappe.db.exists("Room", {"property": P, "room_number": "E104"})
	if not docroom:
		docroom = frappe.get_doc({
			"doctype": "Room", "property": P, "room_number": "E104",
			"room_type": RT,
		}).insert(ignore_permissions=True).name
	else:
		frappe.db.set_value("Room", docroom, "room_type", RT)
	g = _guest("Eval AddrProof", "+91 70000 00036")
	res = _res(g, nowdate(), add_days(nowdate(), 1), docroom)
	tok = frappe.generate_hash(length=32)
	frappe.db.set_value("Reservation", res.name, "precheckin_token", tok)

	# guest sends BOTH documents from the self check-in page
	frappe.set_user("Guest")  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow
	try:
		public_api.precheckin_submit(tok, "Passport", "P1234567",
		                             id_image=img64(), address_image=img64())
	finally:
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow
	assert frappe.db.get_value("Guest", g, "id_file")
	addr1 = frappe.db.get_value("Guest", g, "address_proof_file")
	assert addr1

	# desk replaces the address proof with a newer copy - still ONE file
	api.upload_guest_document(g, "address", img64())
	files = frappe.get_all("File", filters={
		"attached_to_doctype": "Guest", "attached_to_name": g,
		"attached_to_field": "address_proof_file"}, fields=["is_private"])
	assert len(files) == 1 and files[0].is_private == 1, files
	card = api.registration_card(res.name)
	assert card["guest"]["address_proof_file"], card["guest"]
	assert card["guest"]["guest_id"] == g

	# Verify & Discard wipes BOTH slots at checkout
	frappe.db.set_value("Property", P, "id_retention", "Verify & Discard")
	res.reload()
	res.status = "Checked In"
	res.save(ignore_permissions=True)
	_checkout_unsettled(res.name)
	assert not frappe.db.get_value("Guest", g, "id_file")
	assert not frappe.db.get_value("Guest", g, "address_proof_file")
	frappe.db.set_value("Property", P, "id_retention", "Store")


@check("stay ledger: advance/deposit kinds, guarded refunds, actual times on GRC")
def t37():
	from kamra import api

	lroom2 = frappe.db.exists("Room", {"property": P, "room_number": "E105"})
	if not lroom2:
		lroom2 = frappe.get_doc({
			"doctype": "Room", "property": P, "room_number": "E105",
			"room_type": RT,
		}).insert(ignore_permissions=True).name
	else:
		frappe.db.set_value("Room", lroom2, "room_type", RT)
	g = _guest("Eval Ledger", "+91 70000 00037")
	res = _res(g, nowdate(), add_days(nowdate(), 1), lroom2)
	res.status = "Checked In"
	res.save(ignore_permissions=True)
	folio = frappe.db.get_value(
		"Folio", {"reservation": res.name, "folio_type": "Guest"})

	# advance and a refundable deposit land as labelled ledger rows
	api.add_folio_payment(folio, "UPI", 2000, kind="Advance")
	api.add_folio_payment(folio, "Cash", 1000, kind="Security Deposit")
	try:
		api.add_folio_payment(folio, "Cash", 100, kind="Bribe")
		raise AssertionError("junk payment kind accepted")
	except frappe.exceptions.ValidationError:
		pass

	# refunds: reason mandatory, can't exceed what was collected
	try:
		api.refund_folio_payment(folio, 5000, "Cash", "too much")
		raise AssertionError("over-refund accepted")
	except frappe.exceptions.ValidationError:
		pass
	api.refund_folio_payment(folio, 1000, "Cash", "deposit returned")
	fd = frappe.get_doc("Folio", folio)
	kinds = {(p.payment_kind, float(p.amount)) for p in fd.payments}
	assert ("Advance", 2000.0) in kinds and ("Security Deposit", 1000.0) in kinds
	assert ("Refund", -1000.0) in kinds, kinds
	assert float(fd.payments_total) == 2000.0, fd.payments_total  # 2000+1000-1000

	# actual times: corrected by the desk, visible on the GRC with money
	api.set_actual_times(res.name, actual_check_in=f"{nowdate()} 07:15:00")
	card = api.registration_card(res.name)
	assert card["reservation"]["actual_check_in"].endswith("07:15:00")
	assert card["money"]["folio"] == folio, card["money"]
	assert card["money"]["advance"] == 2000.0, card["money"]
	assert card["money"]["refunded"] == 1000.0, card["money"]


@check("Indonesia pack: PBJT flat tax, NPWP labels, Rupiah locale")
def t44():
	from kamra.localization import pack_for
	from kamra.pricing import quote

	P4 = "EVAL Bali Hotel"
	if not frappe.db.exists("Property", P4):
		frappe.get_doc({
			"doctype": "Property", "property_name": P4, "city": "Ubud",
			"country": "Indonesia",
		}).insert(ignore_permissions=True)
	rt = frappe.get_doc({
		"doctype": "Room Type", "property": P4, "room_type_code": "VIL",
		"room_type_name": "Villa", "base_price": 1500000,
		"base_occupancy": 2, "adults_capacity": 3, "children_capacity": 2,
		"tax_percent": 10,
	}).insert(ignore_permissions=True).name

	pack = pack_for(P4)
	assert pack.__name__.endswith("indonesia"), pack.__name__

	# flat PBJT: same rate whatever the tariff (no Indian slab switching)
	q = quote(P4, rt, "2031-05-01", "2031-05-02", 2, 0)
	assert q["nightly"][0]["gst_rate"] == 10, q["nightly"]
	q2 = quote(P4, rt, "2031-05-01", "2031-05-02", 3, 1)
	assert q2["nightly"][0]["gst_rate"] == 10, q2["nightly"]
	# a region with a different PBJT sets it on the room type
	frappe.db.set_value("Room Type", rt, "tax_percent", 8)
	q3 = quote(P4, rt, "2031-05-01", "2031-05-02", 2, 0)
	assert q3["nightly"][0]["gst_rate"] == 8, q3["nightly"]

	prop = frappe.get_doc("Property", P4)
	ctx = pack.invoice_context(prop)
	assert ctx["tax_id_label"] == "NPWP" and ctx["split"][0][0] == "pb1", ctx
	loc = pack.locale(prop)
	assert loc["currency_symbol"] == "Rp" and loc["locale"] == "id-ID", loc


@check("currency follows the pack: locale endpoint + public ui_locale")
def t45():
	from kamra.api import property_locale
	from kamra.public_api import _public_locale

	# staff endpoint: India property keeps the rupee, Indonesia gets Rp
	loc = property_locale(P)
	assert loc["currency_symbol"] == "₹" and loc["locale"] == "en-IN", loc
	loc4 = property_locale("EVAL Bali Hotel")  # created by t44
	assert loc4["currency_symbol"] == "Rp" and loc4["locale"] == "id-ID", loc4

	# the dict showcase / precheckin_info embed as ui_locale
	pub = _public_locale("EVAL Bali Hotel")
	assert (pub["currency_symbol"], pub["locale"]) == ("Rp", "id-ID"), pub
	# the privacy notice's regulator rides along; never India's for Bali
	assert "India" not in (pub.get("privacy_authority") or ""), pub
	assert _public_locale(P)["currency_symbol"] == "₹"


@check("SEA/ME packs: Thai VAT, Malaysian SST room/F&B split, UAE TRN")
def t46():
	from kamra.localization import pack_for
	from kamra.pricing import quote

	fixtures = [
		("EVAL Bangkok Hotel", "Thailand", "thailand", 7, "฿", "th-TH"),
		("EVAL KL Hotel", "Malaysia", "malaysia", 8, "RM", "ms-MY"),
		("EVAL Dubai Hotel", "United Arab Emirates", "uae", 5,
		 "AED ", "en-AE"),
	]
	for pname, country, mod, rate, symbol, loc_code in fixtures:
		if not frappe.db.exists("Property", pname):
			frappe.get_doc({
				"doctype": "Property", "property_name": pname,
				"city": "Eval", "country": country,
			}).insert(ignore_permissions=True)
		rt = frappe.get_doc({
			"doctype": "Room Type", "property": pname,
			"room_type_code": "STD", "room_type_name": "Standard",
			"base_price": 4000, "base_occupancy": 2,
			"adults_capacity": 2, "children_capacity": 1,
		}).insert(ignore_permissions=True).name

		pack = pack_for(pname)
		assert pack.__name__.endswith(mod), (pname, pack.__name__)
		# flat default rate, no Indian slab switching by tariff
		q = quote(pname, rt, "2031-06-01", "2031-06-02", 2, 0)
		assert q["nightly"][0]["gst_rate"] == rate, (pname, q["nightly"])
		loc = pack.locale(frappe.get_doc("Property", pname))
		assert loc["currency_symbol"] == symbol, (pname, loc)
		assert loc["locale"] == loc_code, (pname, loc)

	# Malaysia is the one seam country where F&B differs from rooms
	from kamra.localization import malaysia
	assert malaysia.fnb_tax_rate("EVAL KL Hotel") == 6.0
	ctx = malaysia.invoice_context(frappe.get_doc("Property", "EVAL KL Hotel"))
	assert ctx["tax_id_label"] == "SST Registration No.", ctx
	from kamra.localization import uae
	assert uae.invoice_context(
		frappe.get_doc("Property", "EVAL Dubai Hotel"))["tax_id_label"] == "TRN"


@check("generic pack: currency symbol comes from the Currency master")
def t47():
	from kamra.localization import pack_for

	if not frappe.db.exists("Currency", "GBP"):
		frappe.get_doc({"doctype": "Currency", "currency_name": "GBP",
		                "symbol": "£", "enabled": 1}).insert(
			ignore_permissions=True)
	P5 = "EVAL London Hotel"
	if not frappe.db.exists("Property", P5):
		frappe.get_doc({"doctype": "Property", "property_name": P5,
		                "city": "London", "country": "United Kingdom",
		                "currency": "GBP"}).insert(ignore_permissions=True)

	pack = pack_for(P5)
	assert pack.__name__.endswith("generic"), pack.__name__
	loc = pack.locale(frappe.get_doc("Property", P5))
	sym = loc["currency_symbol"]
	# the master's symbol when it has one, the code itself when it doesn't -
	# never again a bare unlabelled amount
	assert sym and ("£" in sym or sym.strip() == "GBP"), loc


@check("Saudi pack + ZATCA: vocabulary, QR, hash chain, credit note")
def t47b():
	from kamra import zatca
	from kamra.localization import front_desk_vocabulary, pack_for
	from kamra.zatca import tlv, ubl

	P6 = "EVAL Riyadh Hotel"
	if not frappe.db.exists("Property", P6):
		frappe.get_doc({"doctype": "Property", "property_name": P6,
		                "city": "Riyadh", "country": "Saudi Arabia",
		                "currency": "SAR", "gstin": "310122393500003"}).insert(
			ignore_permissions=True)
	pack = pack_for(P6)
	assert pack.__name__.endswith("saudi"), pack.__name__
	v = front_desk_vocabulary(pack)
	assert "Iqama" in v["id_types"] and "Aadhaar" not in v["id_types"], v
	assert "UPI" not in v["payment_modes"], v

	lines = [{"name": "Room night", "qty": 1, "net": 400, "rate": 15},
	         {"name": "Loyalty", "qty": 1, "net": -40, "rate": 15}]
	tag = frappe.generate_hash(length=6)
	a = zatca.issue(P6, f"EVAL-{tag}-1", lines, source_doctype="Property",
	                source_name=P6)
	b = zatca.issue(P6, f"EVAL-{tag}-2", lines, source_doctype="Property",
	                source_name=P6)
	# negative lines become an allowance: 360 net, 54 VAT, 414 with VAT
	assert (a.tax_exclusive, a.vat_total, a.tax_inclusive) == (360, 54, 414), a
	q = tlv.decode(a.qr)
	assert q[2] == "310122393500003" and q[4] == "414.00" and q[5] == "54.00", q
	assert ubl.invoice_hash(a.xml) == a.invoice_hash
	assert b.icv == a.icv + 1 and b.previous_hash == a.invoice_hash
	# idempotent: the same number never forks the chain
	assert zatca.issue(P6, f"EVAL-{tag}-1", lines, source_doctype="Property",
	                   source_name=P6).name == a.name
	cn = zatca.issue(P6, f"CN-EVAL-{tag}-1", lines, source_doctype="Property",
	                 source_name=P6, doc_type="Credit Note",
	                 billing_reference=f"EVAL-{tag}-1", reason="eval")
	assert ">381<" in cn.xml and f"EVAL-{tag}-1" in cn.xml


@check("deposit before arrival: advance on an early folio, link, carried to check-in")
def t47c():
	from frappe.utils import add_days, nowdate

	from kamra import api
	from kamra.payments import settle_payment_link

	frappe.db.set_value("Property", P, "deposit_pct", 30)
	frappe.clear_cache(doctype="Property")
	b = api.create_booking(P, RT, add_days(nowdate(), 40), add_days(nowdate(), 42),
	                       "EVAL Deposit Guest", phone="+919800011400")
	res = frappe.get_doc("Reservation", b["reservation"])
	dep = api._deposit_state(res)
	assert dep["expected"] == round(res.amount_after_tax * 0.3, 2) and dep["can_take"], dep
	r = api.record_advance(res.name, 100, mode="Cash")
	f = frappe.get_doc("Folio", r["folio"])
	assert [(p.payment_kind, p.amount) for p in f.payments] == [("Advance", 100)], f.payments
	assert r["deposit"]["paid"] == 100
	# the drawer shows the booking total, not the empty folio's
	m = api.reservation_detail(res.name)["money"]
	assert m["total"] == res.amount_after_tax and m["paid"] == 100, m
	# a paid link posts once, as an Advance
	assert settle_payment_link(f.name, "plink_EVAL", 50) is True
	assert settle_payment_link(f.name, "plink_EVAL", 50) is False
	res.reload()
	assert res.advance_paid == 150, res.advance_paid
	f.reload()
	assert f.payments[-1].payment_kind == "Advance"


@check("India pack: Razorpay/Cashfree links, GSTR-1 and Kamra Verify; other packs refuse")
def t47d():
	import hashlib
	import hmac

	from frappe.utils import add_days, nowdate

	from kamra import api, localization as loc, payments
	from kamra.connect import client
	from kamra.folio import open_folio
	from kamra.localization.india import cashfree

	# Kamra Verify is unreleased: hidden and refused unless the site opts in
	frappe.conf.kamra_verify_enabled = 0
	hidden = loc.integrations(loc.pack_for(P))
	assert not hidden["verify_tax_id"] and not hidden["verify_guest_id"], hidden
	try:
		loc.verify_tax_id(loc.pack_for(P), P, "29ABCDE1234F1Z5")
		raise AssertionError("unreleased Kamra Verify ran")
	except frappe.ValidationError:
		pass
	frappe.conf.kamra_verify_enabled = 1

	# India (EVAL Hotel has no country, so it runs on the India pack)
	assert loc.integrations(loc.pack_for(P)) == {
		"payment_gateways": ["Razorpay", "Cashfree"], "tax_return": True,
		"verify_tax_id": True, "verify_guest_id": True}, loc.integrations(loc.pack_for(P))

	SA = "EVAL Riyadh Hotel"
	if not frappe.db.exists("Property", SA):
		frappe.get_doc({"doctype": "Property", "property_name": SA,
		                "city": "Riyadh", "country": "Saudi Arabia",
		                "currency": "SAR"}).insert(ignore_permissions=True)
	saudi = loc.pack_for(SA)
	assert loc.integrations(saudi) == {
		"payment_gateways": [], "tax_return": False,
		"verify_tax_id": False, "verify_guest_id": False}, loc.integrations(saudi)

	def refused(fn, exc=frappe.ValidationError):
		try:
			fn()
		except exc:
			frappe.clear_messages()
			return True
		return False

	assert refused(lambda: api.gstr1_rows(nowdate(), nowdate(), property=SA))
	assert refused(lambda: loc.verify_tax_id(saudi, SA, "29ABCDE1234F1Z5"))
	assert refused(lambda: loc.verify_guest_id(saudi, SA, "x", "Passport", 1))
	assert refused(lambda: frappe.get_doc({
		"doctype": "Payment Gateway Settings", "property": SA,
		"gateway": "Razorpay", "enabled": 1}).insert(ignore_permissions=True))
	# GSTR-1 across the chain leaves the Saudi hotel out
	rows = api.gstr1_rows(add_days(nowdate(), -3650), nowdate())
	assert all(frappe.db.get_value("Folio", r.name, "property") != SA for r in rows)

	# India: a test-mode Razorpay link, settled once by a signed webhook
	name = frappe.db.get_value("Payment Gateway Settings", {"property": P})
	gw = frappe.get_doc("Payment Gateway Settings", name) if name \
		else frappe.new_doc("Payment Gateway Settings")
	gw.update({"property": P, "gateway": "Razorpay", "enabled": 1,
	           "test_mode": 1, "webhook_secret": "eval-whsec",
	           "key_secret": "eval-cfsec"})
	gw.save(ignore_permissions=True)
	b = api.create_booking(P, RT, add_days(nowdate(), 50), add_days(nowdate(), 51),
	                       "EVAL Gateway Guest", phone="+919800011401")
	folio = open_folio(frappe.get_doc("Reservation", b["reservation"]))
	link = payments.create_payment_link(folio, amount=50, purpose="Booking deposit")
	assert link["test_mode"] and link["url"].startswith("https://rzp.io/test/"), link

	body = json.dumps({"event": "payment_link.paid", "payload": {"payment_link": {
		"entity": {"id": link["link_id"], "amount_paid": 5000,
		           "notes": {"folio": folio}}}}}).encode()
	sig = hmac.new(b"eval-whsec", body, hashlib.sha256).hexdigest()
	assert refused(lambda: payments.handle_webhook(
		"Razorpay", body, {"x-razorpay-signature": "forged"}), frappe.PermissionError)
	assert payments.handle_webhook("Razorpay", body, {"x-razorpay-signature": sig})["posted"]
	assert not payments.handle_webhook("Razorpay", body, {"x-razorpay-signature": sig})["posted"]
	# a Cashfree callback for a Razorpay property is refused
	cf_body = json.dumps({"type": "PAYMENT_LINK_EVENT", "data": {
		"link_status": "PAID", "link_id": "cf-eval-1", "link_amount_paid": 25,
		"link_notes": {"folio": folio}}}).encode()
	cf_headers = {"x-webhook-timestamp": "1700000000",
	              "x-webhook-signature": cashfree.signature("eval-cfsec", "1700000000", cf_body)}
	assert refused(lambda: payments.handle_webhook("Cashfree", cf_body, cf_headers),
	               frappe.PermissionError)

	# switched to Cashfree: its signed callback posts, a forged one does not
	gw.reload()
	gw.gateway = "Cashfree"
	gw.save(ignore_permissions=True)
	assert refused(lambda: payments.handle_webhook(
		"Cashfree", cf_body, {**cf_headers, "x-webhook-signature": "forged"}),
		frappe.PermissionError)
	assert payments.handle_webhook("Cashfree", cf_body, cf_headers)["posted"]
	paid = [p.amount for p in frappe.get_doc("Folio", folio).payments
	        if p.mode == "Payment Link"]
	assert sorted(paid) == [25, 50], paid
	# an event that is not a payment is ignored, not an error
	assert payments.handle_webhook("Razorpay", b'{"event": "payment_link.expired"}', {}) \
		== {"ignored": True}

	# Kamra Verify through the Connect hub (stubbed in-process)
	calls = []

	def hub(name, key, json_body=None, params=None, data=None):
		calls.append((name, key))
		return {"valid": True, "gstin": json_body["gstin"], "legal_name": "Eval Pvt Ltd",
		        "status": "Active", "charged": 5}

	s = frappe.get_single("Kamra Connect Settings")
	s.connect_key, s.linked = "eval-connect-key", 1
	s.save(ignore_permissions=True)
	client.use_transport(hub)
	try:
		out = api.verify_tax_id(P, "29ABCDE1234F1Z5", "Eval")
	finally:
		client.use_transport()
	assert out["legal_name"] == "Eval Pvt Ltd" and calls == [("verify_gstin", "eval-connect-key")], (out, calls)
	# ID reading needs the guest to have been told
	assert refused(lambda: loc.verify_guest_id(loc.pack_for(P), P, "x", "Aadhaar", 0))
	frappe.conf.kamra_verify_enabled = 0


@check("WhatsApp: native Meta send, booking flow, inbound -> ticket")
def t48():
	# nosemgrep: frappe-monkey-patching-not-allowed -- offline eval harness stubs the outbound transport for tests; not a production code path
	from kamra import whatsapp
	from kamra.agents_channels import send_outbound

	# a connection with our own number - fake creds, intercepted transport
	frappe.get_doc({
		"doctype": "Channel Provider Connection", "property": P,
		"channel": "WhatsApp", "provider": "Meta Business", "active": 1,
		"phone_number": "+91 98450 00000",
		"external_account_id": "eval-phone-id",
		"credentials": "eval-token", "webhook_secret": "eval-verify",
		"meta_language": "en",
		"tpl_booking_confirmation": "kamra_booking_confirmation",
		"tpl_precheckin": "kamra_precheckin_link",
		"tpl_payment_request": "kamra_payment_request",
	}).insert(ignore_permissions=True)

	sent = []
	real_post = whatsapp._post_graph
	whatsapp._post_graph = lambda c, payload: (
		sent.append(payload) or (True, f"wamid.eval{len(sent)}"))
	try:
		# an existing confirmed stay whose guest has a phone
		res_name = frappe.get_all(
			"Reservation", filters={"property": P,
			                        "status": ("in", ["Confirmed", "Checked In"])},
			pluck="name", limit=1)[0]
		res = frappe.get_doc("Reservation", res_name)
		frappe.db.set_value("Guest", res.guest, "phone", "919812340048")
		if not res.get("precheckin_token"):
			frappe.db.set_value("Reservation", res_name,
			                    "precheckin_token", "evaltoken" + "x" * 16)

		out = whatsapp.notify_booking_confirmed(res_name)
		assert out.get("sent"), out
		# confirmation template with the 4 args + the check-in link follow-up
		assert sent[0]["type"] == "template"
		assert sent[0]["template"]["name"] == "kamra_booking_confirmation"
		params = sent[0]["template"]["components"][0]["parameters"]
		assert len(params) == 4 and params[1]["text"], params
		assert sent[1]["template"]["name"] == "kamra_precheckin_link"
		assert "/kamra/checkin/" in sent[1]["template"]["components"][0][
			"parameters"][1]["text"]

		rows = frappe.get_all("WhatsApp Message",
		                      filters={"property": P, "direction": "Outbound"},
		                      fields=["status", "template_name"])
		assert len(rows) == 2 and all(r.status == "Sent" for r in rows), rows

		# the generic channel seam now dispatches natively (no relay URL)
		r = send_outbound(P, "WhatsApp", "919812340048", "Your room is ready")
		assert r.get("sent"), r
		assert sent[-1]["type"] == "text"

		# inbound webhook block: message row + a desk ticket for the stay
		whatsapp._handle_inbound({
			"metadata": {"phone_number_id": "eval-phone-id"},
			"messages": [{"from": "919812340048", "id": "wamid.in1",
			              "type": "text",
			              "text": {"body": "Can we get a late checkout?"}}],
		})
		inbound = frappe.get_all("WhatsApp Message",
		                         filters={"property": P, "direction": "Inbound"},
		                         fields=["guest", "reservation", "status"])
		assert inbound and inbound[0].status == "Received", inbound
		assert inbound[0].reservation == res_name, inbound
		tickets = frappe.get_all("Service Ticket",
		                         filters={"property": P,
		                                  "subject": ("like", "WhatsApp:%")},
		                         fields=["name", "source"])
		assert tickets, "inbound message did not raise a Service Ticket"
		assert all(t.source == "WhatsApp" for t in tickets), tickets

		# the desk's conversation view: threads, one thread, a reply
		th = whatsapp.threads(P)
		assert any(t["number"] == "919812340048" for t in th), th
		conv = whatsapp.thread(P, "919812340048")
		assert conv["session_open"], "fresh guest message should open the window"
		assert len(conv["messages"]) >= 3
		assert conv["messages"][0]["creation"] <= conv["messages"][-1]["creation"]
		r2 = whatsapp.reply(P, "919812340048", "Late checkout till 2 PM is fine.")
		assert r2["sent"], r2
	finally:
		whatsapp._post_graph = real_post


@check("whitelist audit: every endpoint the frontend calls is callable")
def t49():
	"""Guards against decorator orphaning: inserting a helper between a
	function and its decorators silently un-whitelists the endpoint (broke
	registration_card, precheckin_submit and public book at various
	points) and, worse, whitelists the helper. Sweep every kamra.* method
	the frontend references and prove each is a registered endpoint."""
	import pathlib
	import re

	src = pathlib.Path(frappe.get_app_path("kamra")).parent / "frontend" / "src"
	assert src.exists(), f"frontend source not found at {src}"
	calls = set()
	for f in src.rglob("*.ts*"):
		calls |= set(re.findall(r'"(kamra\.\w+\.\w+)"', f.read_text()))
	assert len(calls) > 50, f"suspiciously few frontend calls found: {len(calls)}"
	# dotted strings that are NOT api calls (localStorage keys etc.)
	calls -= {"kamra.kds.chime"}

	missing = []
	for path in sorted(calls):
		try:
			target = frappe.get_attr(path)
		except Exception:
			missing.append(f"{path} (does not resolve)")
			continue
		if target not in frappe.whitelisted:
			missing.append(path)
	assert not missing, f"frontend calls unwhitelisted endpoints: {missing}"

	# and no private helper may be an endpoint
	leaked = [str(fn) for fn in frappe.whitelisted
	          if getattr(fn, "__module__", "").startswith("kamra.")
	          and fn.__name__.startswith("_")]
	assert not leaked, f"private helpers are whitelisted: {leaked}"


@check("check-in flow: context, allocator suggestion, room handover")
def t50():
	from frappe.utils import add_days, nowdate

	from kamra.api import check_in, checkin_context

	# an unassigned arrival for today - the flow's home case
	guest = frappe.get_doc({
		"doctype": "Guest", "first_name": "Flow", "last_name": "Guest",
		"phone": "+91 98111 22334", "email": "flow@example.com",
	}).insert(ignore_permissions=True)
	res = frappe.get_doc({
		"doctype": "Reservation", "property": P, "guest": guest.name,
		"room_type": RT, "check_in_date": nowdate(),
		"check_out_date": add_days(nowdate(), 2), "adults": 2,
		"source": "PMS",
	}).insert(ignore_permissions=True)
	assert not res.room

	ctx = checkin_context(res.name)
	assert ctx["reservation"]["status"] == "Confirmed"
	assert ctx["readiness"]["phone"] and ctx["readiness"]["email"]
	assert not ctx["readiness"]["id_on_file"]
	assert ctx["room_assigned"] is None
	assert ctx["rooms"], "no free rooms offered for an open room type"
	# the allocator proposes one of the offered rooms, with a reason
	assert ctx["suggestion"], "allocator made no suggestion"
	assert ctx["suggestion"]["room"] in [r["name"] for r in ctx["rooms"]]
	assert ctx["suggestion"]["why"]

	# desk takes the suggestion - check-in lands guest in that room
	out = check_in(res.name, room=ctx["suggestion"]["room"])
	assert out["room"] == ctx["suggestion"]["room"], out
	res.reload()
	assert res.status == "Checked In" and res.room == out["room"]

	# once assigned, the context reports the room instead of choices
	ctx2 = checkin_context(res.name)
	assert ctx2["room_assigned"] and ctx2["room_assigned"]["name"] == res.room
	assert ctx2["rooms"] == [] and ctx2["suggestion"] is None


@check("occupant register: per-occupant ID scans, edit-safe, discarded at checkout")
def t51():
	import base64
	import io as _io

	from frappe.utils import add_days, nowdate
	from PIL import Image

	from kamra.api import _scrub_stay_ids, update_occupants, upload_occupant_id

	guest = frappe.get_doc({
		"doctype": "Guest", "first_name": "Occ", "last_name": "Primary",
	}).insert(ignore_permissions=True)
	res = frappe.get_doc({
		"doctype": "Reservation", "property": P, "guest": guest.name,
		"room_type": RT, "check_in_date": nowdate(),
		"check_out_date": add_days(nowdate(), 1), "adults": 2,
		"source": "PMS",
	}).insert(ignore_permissions=True)

	out = update_occupants(res.name, [
		{"full_name": "Asha Kumar", "age": 34, "id_type": "Aadhaar",
		 "id_number": "987654321012"},
	])
	assert out["rows"] and out["rows"][0]["row"], out
	row = out["rows"][0]["row"]

	# a real JPEG through the sanitising pipeline
	buf = _io.BytesIO()
	Image.new("RGB", (60, 40), (200, 30, 30)).save(buf, format="JPEG")
	data_url = ("data:image/jpeg;base64,"
	            + base64.b64encode(buf.getvalue()).decode())
	up = upload_occupant_id(res.name, row, data_url)
	assert up["ok"] and up["file"].startswith("/private/"), up

	# register edits keep the scan
	out2 = update_occupants(res.name, out["rows"] + [
		{"full_name": "Dev Kumar", "age": 8}])
	kept = [r for r in out2["rows"] if r["full_name"] == "Asha Kumar"][0]
	assert kept["id_file"] == up["file"], out2["rows"]

	# Verify & Discard: the scan and the digits leave with the party
	real = frappe.db.get_value("Property", P, "id_retention")
	frappe.db.set_value("Property", P, "id_retention", "Verify & Discard")
	try:
		res.reload()
		_scrub_stay_ids(res)
		occ = frappe.get_all("Stay Occupant",
		                     filters={"parent": res.name,
		                              "full_name": "Asha Kumar"},
		                     fields=["id_number", "id_file"])[0]
		assert occ.id_file is None, occ
		assert occ.id_number.endswith("1012") and occ.id_number.startswith("•")
		assert not frappe.get_all("File", filters={"file_url": up["file"]})
	finally:
		frappe.db.set_value("Property", P, "id_retention", real)


@check("channel manager: ARI snapshot, push, OTA book/modify/cancel")
def t53():
	from frappe.utils import add_days, nowdate

	from kamra import channel_manager as cm

	# nosemgrep: frappe-monkey-patching-not-allowed -- offline eval harness stubs the outbound transport for tests; not a production code path
	from kamra.channels import channex

	conn = frappe.get_doc({
		"doctype": "Channel Manager Connection", "property": P,
		"provider": "Channex", "active": 1, "api_key": "eval-key",
		"external_property_id": "chx-prop-1", "webhook_secret": "eval-hook",
		"sync_days": 5,
	}).insert(ignore_permissions=True)
	frappe.get_doc({
		"doctype": "Channel Room Mapping", "connection": conn.name,
		"room_type": RT, "external_room_id": "chx-room-1",
		"external_rate_id": "chx-rate-1",
	}).insert(ignore_permissions=True)

	snap = cm.ari_snapshot(P, conn.name, days=3)
	assert len(snap) == 1 and len(snap[0]["days"]) == 3, snap
	assert snap[0]["external_room_id"] == "chx-room-1"
	day0 = snap[0]["days"][0]
	assert day0["available"] >= 0 and day0["rate"] > 0, day0

	pushes = []
	real_call = channex._call
	channex._call = lambda c, m, path, payload=None: (
		pushes.append((path, payload)) or (True, {"data": "ok"}))
	try:
		out = cm.push_ari(conn.name)
		assert out["ok"], out
		assert {p_ for p_, _ in pushes} == {"availability", "restrictions"}
		before = frappe.db.get_value("Channel Manager Connection",
		                             conn.name, "last_push_status")
		assert before and before.startswith("OK"), before

		# inbound booking in Channex webhook shape
		ci, co = nowdate(), add_days(nowdate(), 2)
		events = channex.parse_webhook(conn, {"payload": {
			"status": "new", "ota_reservation_code": "BDC-777",
			"ota_name": "Booking.com", "currency": "INR",
			"customer": {"name": "Nina", "surname": "Rao",
			             "phone": "+91 90000 11111",
			             "mail": "nina@example.com"},
			"rooms": [{"room_type_id": "chx-room-1",
			           "checkin_date": str(ci), "checkout_date": str(co),
			           "occupancy": {"adults": 2, "children": 1},
			           "days": {str(ci): "4200.00",
			                    str(add_days(ci, 1)): "4200.00"}}],
		}})
		assert events[0]["event"] == "book" and events[0]["total"] == 8400.0
		r1 = cm._apply_event(conn, events[0])
		assert r1["result"] == "booked", r1
		res = frappe.get_doc("Reservation", r1["reservation"])
		assert res.source == "OTA" and res.channel == "Booking.com"
		assert res.ota_ref == "BDC-777"
		assert float(res.amount_after_tax) == 8400.0, res.amount_after_tax
		assert frappe.db.get_value("Guest", res.guest, "email") 			== "nina@example.com"

		# same ref again = ignored, not double-booked
		r2 = cm._apply_event(conn, events[0])
		assert r2["result"] == "duplicate_ignored", r2

		# modify moves the dates
		mod = dict(events[0], event="modify",
		           check_out=str(add_days(ci, 3)))
		r3 = cm._apply_event(conn, mod)
		assert r3["result"] == "modified", r3
		res.reload()
		assert str(res.check_out_date) == str(add_days(ci, 3))

		# cancel closes it through the policy-safe path
		r4 = cm._apply_event(conn, dict(events[0], event="cancel"))
		assert r4["result"] == "cancelled", r4
		res.reload()
		assert res.status == "Cancelled"

		# unmapped room never lands silently
		bad = dict(events[0], ota_ref="X-1",
		           room_type_external_id="unknown-room")
		assert cm._apply_event(conn, bad)["result"] == "unmapped_room"
	finally:
		channex._call = real_call


@check("ticket SLA: priority sets due window")
def t12():
	from frappe.utils import get_datetime, now_datetime, time_diff_in_seconds
	t = frappe.get_doc({
		"doctype": "Service Ticket", "property": P, "subject": "eval",
		"category": "Housekeeping", "priority": "Urgent",
	}).insert(ignore_permissions=True)
	mins = time_diff_in_seconds(get_datetime(t.due_by), now_datetime()) / 60
	assert 13 <= mins <= 16, mins


# ══ banquets ═════════════════════════════════════════════════════════════
# Everything an agent quoting a wedding relies on: that the plate count
# follows the guarantee, that a complimentary line is free without
# disappearing, that a mixed-rate discount still taxes each line correctly,
# and that a confirmed function actually owns the hall.

BQ = {}


def _banquet_setup():
	"""A hall, a menu and two services - one billed, one thrown in."""
	if BQ:
		return BQ
	BQ["venue"] = frappe.get_doc({
		"doctype": "Venue", "property": P, "venue_name": "Eval Hall",
		"venue_type": "Banquet Hall", "capacity": 300, "base_price": 50000,
		"hourly_rate": 8000, "min_hours": 4, "gst_rate": 18,
	}).insert(ignore_permissions=True).name
	BQ["small"] = frappe.get_doc({
		"doctype": "Venue", "property": P, "venue_name": "Eval Board Room",
		"venue_type": "Board Room", "capacity": 20, "base_price": 8000,
	}).insert(ignore_permissions=True).name
	BQ["menu"] = frappe.get_doc({
		"doctype": "Banquet Menu", "property": P, "menu_name": "Eval Buffet",
		"meal_period": "Dinner", "food_type": "Veg", "rate_per_pax": 1200,
		"min_pax": 100, "gst_rate": 5,
		"courses": [{"course": "Starters", "dishes": "Paneer tikka"}],
	}).insert(ignore_permissions=True).name
	BQ["led"] = frappe.get_doc({
		"doctype": "Banquet Service Item", "property": P,
		"item_name": "LED wall", "category": "Audio Visual",
		"uom": "Per Event", "rate": 40000, "gst_rate": 18,
		"cost_rate": 25000, "cost_gst_rate": 18,
		"chargeable": 1, "on_pack_list": 1,
	}).insert(ignore_permissions=True).name
	BQ["podium"] = frappe.get_doc({
		"doctype": "Banquet Service Item", "property": P,
		"item_name": "Podium", "category": "Furniture & Setup",
		"uom": "Per Event", "rate": 2000, "gst_rate": 18,
		"chargeable": 0, "on_pack_list": 1,
	}).insert(ignore_permissions=True).name
	BQ["onion"] = frappe.get_doc({
		"doctype": "Ingredient", "property": P, "ingredient_name": "Eval Onion",
		"uom": "kg", "cost_per_unit": 40, "gst_rate": 5, "is_active": 1,
	}).insert(ignore_permissions=True).name
	BQ["chicken"] = frappe.get_doc({
		"doctype": "Ingredient", "property": P,
		"ingredient_name": "Eval Chicken", "uom": "kg", "cost_per_unit": 300,
		"gst_rate": 5, "is_active": 1,
	}).insert(ignore_permissions=True).name
	BQ["dish_veg"] = frappe.get_doc({
		"doctype": "Banquet Dish", "property": P, "dish_name": "Eval Paneer",
		"course_type": "Starters", "food_type": "Veg", "kitchen": "Tandoor",
		"portion_per_pax": 1, "cost_per_portion": 8,
		"recipe": [{"ingredient": BQ["onion"], "qty": 0.2}],
	}).insert(ignore_permissions=True).name
	BQ["dish_nv"] = frappe.get_doc({
		"doctype": "Banquet Dish", "property": P, "dish_name": "Eval Chicken Tikka",
		"course_type": "Starters", "food_type": "Non-Veg", "kitchen": "Tandoor",
		"portion_per_pax": 1, "cost_per_portion": 30,
		"recipe": [{"ingredient": BQ["chicken"], "qty": 0.1}],
	}).insert(ignore_permissions=True).name
	# a menu whose starter course offers a choice of one
	menu = frappe.get_doc("Banquet Menu", BQ["menu"])
	menu.courses[0].choice_of = 1
	course = menu.courses[0].course
	menu.set("dish_options", [
		{"course": course, "dish": BQ["dish_veg"], "is_default": 1},
		{"course": course, "dish": BQ["dish_nv"], "supplement_per_pax": 150},
	])
	menu.save(ignore_permissions=True)
	return BQ



def _starter(b):
	"""The first course's name - the eval menu's starters."""
	return frappe.get_doc("Banquet Menu", b["menu"]).courses[0].course


def _function(day_offset=60, **kw):
	from kamra import banquet as bq

	b = _banquet_setup()
	args = {
		"property": P, "venue": b["venue"],
		"event_date": add_days(nowdate(), day_offset),
		"customer_name": "Eval Banquet", "attendees": 200,
		"start_time": "19:00", "end_time": "23:00",
	}
	args.update(kw)
	return bq.create_enquiry(**args)["function"]


@check("banquet: per-pax lines bill the guarantee, and honour the menu minimum")
def t54():
	from kamra import banquet as bq

	b = _banquet_setup()
	fn = _function()
	bq.update_function(fn, {"pax_guaranteed": 180})
	bq.add_menu(fn, b["menu"])
	doc = frappe.get_doc("Venue Booking", fn)
	menu_line = next(r for r in doc.items if r.item_type == "Menu")
	assert menu_line.qty == 180, menu_line.qty
	assert menu_line.amount == 180 * 1200, menu_line.amount

	# more people turned up than were guaranteed: bill the higher count
	bq.update_function(fn, {"pax_actual": 210})
	doc.reload()
	assert doc.billable_pax == 210, doc.billable_pax

	# and a tiny function still pays the package's floor
	small = _function(day_offset=61, attendees=40)
	bq.update_function(small, {"pax_guaranteed": 40})
	bq.add_menu(small, b["menu"])
	line = next(r for r in frappe.get_doc("Venue Booking", small).items
	            if r.item_type == "Menu")
	assert line.qty == 100, f"min_pax floor not applied: {line.qty}"


@check("banquet: complimentary lines are free but never disappear")
def t55():
	from kamra import banquet as bq

	b = _banquet_setup()
	fn = _function(day_offset=62)
	bq.update_function(fn, {"pax_guaranteed": 100})
	bq.add_service(fn, b["led"])       # chargeable
	bq.add_service(fn, b["podium"])    # complimentary by catalogue default
	bq.add_service(fn, b["led"], chargeable=0)   # given away for this one
	doc = frappe.get_doc("Venue Booking", fn)
	free = [r for r in doc.items if not r.chargeable]
	assert len(free) == 2, [r.item_name for r in free]
	assert all(r.amount == 0 and r.total == 0 for r in free), "comp line billed"
	# ...but the hotel can still see what it gave away
	assert doc.non_chargeable_value == 2000 + 40000, doc.non_chargeable_value
	# and it still has to be carried to the hall
	pack = bq.banquet_document(fn, "pack_list")["pack"]
	names = [i["item_name"] for g in pack["groups"] for i in g["items"]]
	assert names.count("Podium") == 1 and names.count("LED wall") == 2, names


@check("banquet: a discount spreads pro-rata and each line keeps its own GST")
def t56():
	from kamra import banquet as bq

	b = _banquet_setup()
	fn = _function(day_offset=63)
	bq.update_function(fn, {"pax_guaranteed": 100})
	# hall 50,000 @18% + food 120,000 @5% + LED 40,000 @18% = 210,000
	bq.add_menu(fn, b["menu"])
	bq.add_service(fn, b["led"])
	doc = frappe.get_doc("Venue Booking", fn)
	assert doc.subtotal == 210000, doc.subtotal
	assert round(doc.tax_amount, 2) == round(
		50000 * .18 + 120000 * .05 + 40000 * .18, 2), doc.tax_amount

	bq.negotiate(fn, discount_amount=21000)   # 10% off the whole quote
	doc.reload()
	assert doc.taxable_amount == 189000, doc.taxable_amount
	food = next(r for r in doc.items if r.item_type == "Menu")
	assert food.gst_rate == 5, food.gst_rate
	assert round(food.net_amount, 2) == 108000, food.net_amount
	assert round(doc.tax_amount, 2) == round(
		45000 * .18 + 108000 * .05 + 36000 * .18, 2), doc.tax_amount
	assert round(doc.grand_total, 2) == round(
		189000 + doc.tax_amount, 2), doc.grand_total
	# a discount bigger than the quote is not a negotiation, it's a mistake
	try:
		bq.negotiate(fn, discount_amount=500000)
		raise AssertionError("discount exceeded the quote")
	except frappe.ValidationError:
		pass


@check("banquet: hourly halls bill real hours, including past midnight")
def t57():
	fn = _function(day_offset=64, start_time="20:00", end_time="01:00")
	doc = frappe.get_doc("Venue Booking", fn)
	assert doc.billable_hours == 5, doc.billable_hours
	row = doc.items[0]
	row.uom, row.qty, row.rate = "Hour", 0, 8000
	doc.save(ignore_permissions=True)
	assert doc.items[0].qty == 5, doc.items[0].qty
	assert doc.items[0].amount == 40000, doc.items[0].amount


@check("banquet: a confirmed function owns the hall; tentative holds don't")
def t58():
	from kamra import banquet as bq

	day = add_days(nowdate(), 70)
	first = _function(event_date=day, customer_name="Eval Wedding A")
	bq.set_status(first, "Confirmed")

	# same hall, same hours → refused
	clash = _function(event_date=day, customer_name="Eval Wedding B")
	try:
		bq.set_status(clash, "Confirmed")
		raise AssertionError("double-booked the hall")
	except frappe.ValidationError:
		pass

	# a tentative hold is a soft hold - it may be sold over
	bq.set_status(clash, "Tentative")
	# ...and a hall can take two functions in a day where the hours don't
	# actually overlap: morning and evening are two bookings, not a conflict
	morning = _function(event_date=day, customer_name="Eval Conference",
	                    start_time="09:00", end_time="13:00")
	bq.set_status(morning, "Confirmed")
	assert frappe.db.get_value("Venue Booking", morning, "status") == "Confirmed"

	avail = bq.venue_availability(P, day, start_time="19:00", end_time="23:00")
	hall = next(v for v in avail["venues"] if v["name"] == _banquet_setup()["venue"])
	assert not hall["available"], "a confirmed evening function left the hall free"
	assert any(c["kind"] == "tentative" for c in hall["conflicts"]), hall


@check("banquet: the pipeline only moves through legal states, with a reason")
def t59():
	from kamra import banquet as bq

	fn = _function(day_offset=80)
	try:
		bq.set_status(fn, "Completed")   # enquiry → completed skips the work
		raise AssertionError("illegal transition allowed")
	except frappe.ValidationError:
		pass
	try:
		bq.set_status(fn, "Lost")        # no reason
		raise AssertionError("lost a function without saying why")
	except frappe.ValidationError:
		pass
	out = bq.set_status(fn, "Lost", reason="Went to a competitor on price")
	assert out["status"] == "Lost", out
	assert frappe.db.get_value("Venue Booking", fn, "lost_reason")


@check("banquet: holding a green room takes the room out of sale")
def t60():
	from kamra import banquet as bq

	fn = _function(day_offset=90)
	bq.assign_green_room(fn, room=ROOM, complimentary=1)
	doc = frappe.get_doc("Venue Booking", fn)
	assert doc.green_room_block, "no room block created"
	block = frappe.get_doc("Room Block", doc.green_room_block)
	assert block.block_status == "Active" and block.room == ROOM, block.as_dict()
	# a complimentary green room is on the sheet but not on the bill
	line = next(r for r in doc.items if r.item_type == "Accommodation")
	assert not line.chargeable and line.amount == 0, line.as_dict()
	# losing the function gives the room back
	bq.set_status(fn, "Lost", reason="Date moved")
	assert frappe.db.get_value(
		"Room Block", doc.green_room_block, "block_status") == "Released"


@check("banquet: every price move is recorded, and quotes are versioned")
def t61():
	from kamra import banquet as bq

	b = _banquet_setup()
	fn = _function(day_offset=95)
	bq.update_function(fn, {"pax_guaranteed": 100})
	bq.add_menu(fn, b["menu"])
	first = bq.generate_quote(fn)
	assert first["header"]["version"] == 1, first["header"]

	moved = bq.negotiate(fn, venue_rental=40000, note="Matched the competitor")
	assert moved["was"] > moved["now"], moved
	assert moved["moved_by"] < 0, moved
	second = bq.generate_quote(fn)
	assert second["header"]["version"] == 2, second["header"]

	doc = frappe.get_doc("Venue Booking", fn)
	assert len(doc.revisions) == 3, [r.change_note for r in doc.revisions]
	assert doc.venue_rental == 40000, doc.venue_rental
	assert doc.venue_rental_list == 50000, doc.venue_rental_list


@check("banquet: terms follow the quote, receipts settle them")
def t62():
	from kamra import banquet as bq

	b = _banquet_setup()
	fn = _function(day_offset=100)
	bq.update_function(fn, {"pax_guaranteed": 100})
	bq.add_menu(fn, b["menu"])
	bq.default_payment_terms(fn, advance_percent=25, interim_percent=50)
	doc = frappe.get_doc("Venue Booking", fn)
	total = doc.grand_total
	assert len(doc.payment_terms) == 3, len(doc.payment_terms)
	assert round(doc.payment_terms[0].amount, 2) == round(total * .25, 2)

	advance = doc.payment_terms[0]
	bq.record_receipt(fn, advance.amount, kind="Advance", mode="UPI",
	                  settle_term=advance.name)
	doc.reload()
	assert doc.payment_terms[0].status == "Received"
	assert round(doc.advance_received, 2) == round(total * .25, 2)
	assert round(doc.balance_due, 2) == round(total * .75, 2)

	# a refund gives money back on the same ledger
	bq.record_receipt(fn, 1000, kind="Refund", mode="UPI")
	doc.reload()
	assert round(doc.advance_received, 2) == round(total * .25 - 1000, 2)


@check("banquet: the event order needs a confirmed function and prints the menu")
def t63():
	from kamra import banquet as bq

	b = _banquet_setup()
	fn = _function(day_offset=110, customer_name="Eval BEO")
	bq.update_function(fn, {"pax_guaranteed": 150})
	bq.add_menu(fn, b["menu"])
	try:
		bq.generate_beo(fn)
		raise AssertionError("issued an event order for an unsold function")
	except frappe.ValidationError:
		pass
	bq.set_status(fn, "Confirmed")
	beo = bq.generate_beo(fn)
	assert beo["header"]["beo_number"], beo["header"]
	assert beo["menus"] and beo["menus"][0]["courses"][0]["dishes"], beo["menus"]
	assert beo["event"]["billable_pax"] == 150, beo["event"]


@check("banquet: month-wise tracking counts the pipeline by event date")
def t64():
	from kamra import banquet as bq

	out = bq.banquet_pipeline(P, months=12)
	assert out["months"], "no months in the pipeline"
	assert out["totals"]["functions"] > 0, out["totals"]
	statuses = {r["key"] for r in out["by_status"]}
	assert {"Confirmed", "Lost"} <= statuses, statuses
	assert out["totals"]["conversion_rate"] is not None, out["totals"]
	assert any(r["reason"] for r in out["lost_reasons"]), out["lost_reasons"]


@check("banquet: a session sets the clock, custom hours must state one")
def t65():
	from kamra import banquet as bq

	fn = _function(day_offset=120)
	bq.update_function(fn, {"session": "Morning"})
	doc = frappe.get_doc("Venue Booking", fn)
	assert str(doc.start_time) == "7:00:00", doc.start_time
	assert doc.billable_hours == 5, doc.billable_hours

	bq.update_function(fn, {"session": "Full Day"})
	doc.reload()
	assert doc.billable_hours > 16, doc.billable_hours

	# custom hours without hours is not a booking, it's a blank
	doc.session = "Custom Hours"
	doc.start_time = doc.end_time = None
	try:
		doc.save(ignore_permissions=True)
		raise AssertionError("custom hours accepted with no times")
	except frappe.ValidationError:
		pass


@check("banquet: service charge rides the food, not the hall")
def t66():
	from kamra import banquet as bq

	b = _banquet_setup()
	fn = _function(day_offset=125)
	bq.update_function(fn, {"pax_guaranteed": 100})
	bq.add_menu(fn, b["menu"])          # 120,000 food @5%
	bq.add_service(fn, b["led"])        # 40,000 AV @18%
	# hall 50,000 @18% came with the enquiry
	bq.update_function(fn, {"service_charge_percent": 10})
	doc = frappe.get_doc("Venue Booking", fn)
	# 10% of the food only - not the hall, not the LED wall
	assert doc.service_charge == 12000, doc.service_charge
	assert doc.taxable_amount == 210000 + 12000, doc.taxable_amount
	# and it carries the food's own rate
	assert round(doc.tax_amount, 2) == round(
		50000 * .18 + 120000 * .05 + 40000 * .18 + 12000 * .05, 2), doc.tax_amount


@check("banquet: a deposit is held money, not payment")
def t67():
	from kamra import banquet as bq

	b = _banquet_setup()
	fn = _function(day_offset=130)
	bq.update_function(fn, {"pax_guaranteed": 100})
	bq.add_menu(fn, b["menu"])
	bq.set_status(fn, "Confirmed")
	doc = frappe.get_doc("Venue Booking", fn)
	total = doc.grand_total

	bq.record_receipt(fn, 25000, kind="Security Deposit", mode="Cash")
	doc.reload()
	# the deposit must NOT make an unpaid function look part-settled
	assert doc.advance_received == 0, doc.advance_received
	assert doc.deposit_held == 25000, doc.deposit_held
	assert doc.balance_due == total, doc.balance_due

	bq.record_receipt(fn, 50000, kind="Advance", mode="UPI")
	doc.reload()
	assert doc.advance_received == 50000, doc.advance_received
	assert doc.deposit_held == 25000, doc.deposit_held


@check("banquet: close-out deducts damage and returns the rest")
def t68():
	from kamra import banquet as bq

	b = _banquet_setup()
	fn = _function(day_offset=135)
	bq.update_function(fn, {"pax_guaranteed": 100})
	bq.add_menu(fn, b["menu"])
	bq.set_status(fn, "Confirmed")
	bq.record_receipt(fn, 20000, kind="Security Deposit", mode="Cash")

	# a deduction nobody can see the reason for is a dispute waiting
	try:
		bq.close_out(fn, damage_amount=3000)
		raise AssertionError("deducted damages with no reason")
	except frappe.ValidationError:
		pass
	# and you can't keep more than you hold
	try:
		bq.close_out(fn, damage_amount=50000, damage_note="everything")
		raise AssertionError("over-deducted the deposit")
	except frappe.ValidationError:
		pass

	out = bq.close_out(fn, damage_amount=3000, damage_note="Two chairs",
	                   pax_actual=118)
	assert out["refunded"] == 17000, out
	doc = frappe.get_doc("Venue Booking", fn)
	assert doc.status == "Completed", doc.status
	assert doc.deposit_held == 0, doc.deposit_held
	assert doc.pax_actual == 118, doc.pax_actual
	# the damage money is the hotel's now - it belongs on the bill
	recovery = next(r for r in doc.items if r.notes == "damage-recovery")
	assert recovery.rate == 3000 and recovery.chargeable, recovery.as_dict()
	# closing out twice would refund twice
	try:
		bq.close_out(fn)
		raise AssertionError("closed out twice")
	except frappe.ValidationError:
		pass


@check("banquet: the month grid puts a function in its own session")
def t69():
	from frappe.utils import get_first_day, getdate

	from kamra import banquet as bq

	day = add_days(nowdate(), 140)
	fn = _function(event_date=day, customer_name="Eval Month")
	bq.update_function(fn, {"session": "Morning"})
	bq.set_status(fn, "Confirmed")

	grid = bq.month_availability(P, str(get_first_day(getdate(day)))[:7])
	hall = _banquet_setup()["venue"]
	morning = next(r for r in grid["rows"]
	               if r["venue"] == hall and r["session"] == "Morning")
	evening = next(r for r in grid["rows"]
	               if r["venue"] == hall and r["session"] == "Evening")
	assert str(day) in morning["by_date"], morning["by_date"].keys()
	assert str(day) not in evening["by_date"], "a morning function blocked the evening"
	assert grid["utilisation"] >= 0, grid["utilisation"]


@check("banquet: the registers add up and the cash book reads by payment")
def t70():
	from kamra import banquet as bq

	reg = bq.banquet_register(P, "functions", add_days(nowdate(), -1),
	                          add_days(nowdate(), 200))
	assert reg["totals"]["count"] > 0, reg["totals"]
	assert reg["totals"]["value"] == sum(
		float(r["grand_total"] or 0) for r in reg["rows"]), reg["totals"]

	cash = bq.banquet_register(P, "receipts", add_days(nowdate(), -1),
	                           add_days(nowdate(), 200))
	assert cash["rows"], "no receipts in the cash book"
	assert round(cash["totals"]["value"], 2) == round(
		sum(x["amount"] for x in cash["by_mode"]), 2), cash["by_mode"]

	sales = bq.banquet_register(P, "sales", add_days(nowdate(), -1),
	                            add_days(nowdate(), 200))
	assert sales["by_venue"] and sales["by_session"], sales.keys()
	# lost business is not sales
	assert all(r["status"] not in ("Cancelled", "Lost") for r in sales["rows"])


@check("banquet: a dish costs what its recipe costs")
def t71():
	from kamra import banquet as bq

	b = _banquet_setup()
	out = bq.save_dish(P, "Eval Dal", course_type="Main Course",
	                   recipe=[{"ingredient": b["onion"], "qty": 0.5}])
	assert out["cost_per_portion"] == 20, out          # 0.5kg x ₹40

	# the price of onions moved; the quote must move with it
	frappe.db.set_value("Ingredient", b["onion"], "cost_per_unit", 60)
	re = bq.recost_dishes(P)
	assert re["recosted"] >= 1, re
	assert frappe.db.get_value(
		"Banquet Dish", out["name"], "cost_per_portion") == 30
	frappe.db.set_value("Ingredient", b["onion"], "cost_per_unit", 40)
	bq.recost_dishes(P)


@check("banquet: choosing dishes costs the menu line and prices the upgrade")
def t72():
	from kamra import banquet as bq

	b = _banquet_setup()
	fn = _function(day_offset=150)
	bq.update_function(fn, {"pax_guaranteed": 100})
	bq.add_menu(fn, b["menu"])

	choices = bq.menu_choices(fn, b["menu"])
	starters = choices["courses"][0]
	assert starters["choice_of"] == 1, starters
	assert len(starters["options"]) == 2, starters

	# the customer upgrades to the chicken, which carries a supplement
	course = choices["courses"][0]["course"]
	out = bq.compose_menu(fn, b["menu"], [
		{"course": course, "dish": b["dish_nv"],
		 "supplement_per_pax": 150, "note": "less spicy"}])
	assert out["cost_per_pax"] == 30, out
	assert out["supplement_per_pax"] == 150, out

	doc = frappe.get_doc("Venue Booking", fn)
	# the upgrade is its own visible line, not buried in the package rate
	upgrade = next(r for r in doc.items if (r.notes or "").startswith("supplement:"))
	assert upgrade.rate == 150 and upgrade.qty == 100, upgrade.as_dict()
	# and the menu line now knows what it costs to make
	menu_line = next(r for r in doc.items if r.banquet_menu == b["menu"]
	                 and not (r.notes or "").startswith("supplement:"))
	assert menu_line.cost_rate == 30, menu_line.cost_rate
	assert menu_line.cost_amount == 3000, menu_line.cost_amount

	# the card prints what they chose, not the whole catalogue
	card = bq.menu_card(fn)
	served = card["menus"][0]
	assert served["chosen"], served
	assert "Eval Chicken Tikka" in served["courses"][0]["dishes"], served


@check("banquet: input credit follows the OUTPUT rate, not the invoice")
def t73():
	from kamra import banquet as bq

	b = _banquet_setup()
	fn = _function(day_offset=155)
	bq.update_function(fn, {"pax_guaranteed": 100})
	bq.add_menu(fn, b["menu"])
	bq.compose_menu(fn, b["menu"], [{"course": _starter(b), "dish": b["dish_veg"]}])
	bq.add_service(fn, b["led"])
	doc = frappe.get_doc("Venue Booking", fn)

	# food costs 8/pax x 100, the LED wall 25,000
	assert doc.food_cost == 800, doc.food_cost
	assert doc.service_cost == 25000, doc.service_cost
	assert doc.total_cost == 25800, doc.total_cost

	# billed at the 5% food rate → that supply cannot claim the credit back
	assert not doc.itc_eligible, "claimed ITC on a 5% supply"
	assert doc.net_cost == doc.total_cost, doc.net_cost
	assert round(doc.gross_margin, 2) == round(
		doc.taxable_amount - doc.total_cost, 2), doc.gross_margin

	# bill the same food at 18% and the credit becomes real
	for r in doc.items:
		if r.item_type == "Menu":
			r.gst_rate = 18
	doc.save(ignore_permissions=True)
	assert doc.itc_eligible, "18% supply should claim the credit"
	assert doc.net_cost < doc.total_cost, (doc.net_cost, doc.total_cost)
	assert round(doc.input_tax_credit, 2) == round(
		800 * .05 + 25000 * .18, 2), doc.input_tax_credit


@check("banquet: the indent explodes the picks into ingredients")
def t74():
	from kamra import banquet as bq

	b = _banquet_setup()
	fn = _function(day_offset=160)
	bq.update_function(fn, {"pax_guaranteed": 200})
	bq.add_menu(fn, b["menu"])

	# nothing chosen: the kitchen can't be told what to pull
	try:
		bq.kitchen_indent(fn)
		raise AssertionError("indented with no menu chosen")
	except frappe.ValidationError:
		pass

	bq.compose_menu(fn, b["menu"], [{"course": _starter(b), "dish": b["dish_veg"]}])
	ind = bq.kitchen_indent(fn)
	onion = next(r for r in ind["ingredients"] if r["ingredient"] == b["onion"])
	assert onion["required"] == 40, onion      # 0.2kg x 1 portion x 200 pax
	assert onion["cost"] == 1600, onion        # x ₹40
	assert ind["pax"] == 200, ind
	# and the chefs get it split by section
	tandoor = next(k for k in ind["by_kitchen"] if k["kitchen"] == "Tandoor")
	assert tandoor["dishes"][0]["portions"] == 200, tandoor


@check("banquet: the night bills what was served, not what was quoted")
def t75():
	from kamra import banquet as bq

	b = _banquet_setup()
	fn = _function(day_offset=165)
	bq.update_function(fn, {"pax_guaranteed": 100})
	bq.add_menu(fn, b["menu"])
	bq.compose_menu(fn, b["menu"], [{"course": _starter(b), "dish": b["dish_veg"]}])
	doc = frappe.get_doc("Venue Booking", fn)
	quoted = doc.grand_total
	menu_line = next(r for r in doc.items if r.item_type == "Menu")

	# 118 turned up
	bq.record_consumption(fn, {menu_line.name: 118}, pax_actual=118)
	doc.reload()
	assert doc.grand_total > quoted, (quoted, doc.grand_total)
	line = next(r for r in doc.items if r.name == menu_line.name)
	assert line.actual_qty == 118 and line.amount == 118 * 1200, line.as_dict()
	# the cost follows the plates we actually cooked
	assert line.cost_amount == 118 * 8, line.cost_amount

	# and the bar ran on after the quote closed
	bq.add_supplementary(fn, "Extra bar round", qty=2, rate=6000,
	                     item_type="Alcohol", cost_rate=3500, is_alcohol=1)
	econ = bq.function_economics(fn)
	assert econ["revenue"]["supplementary"] > 0, econ["revenue"]
	assert any(x["is_supplementary"] for x in econ["lines"]), econ["lines"]
	assert econ["margin"]["percent"] == frappe.db.get_value(
		"Venue Booking", fn, "margin_percent")


@check("banquet: the customer is a person with a history")
def t76():
	from kamra import banquet as bq

	fn = _function(day_offset=170, customer_name="Eval Repeat Client",
	               customer_phone="+91 90000 12121")
	bq.link_customer(fn)
	guest = frappe.db.get_value("Venue Booking", fn, "customer")
	assert guest, "no guest linked"

	# a second enquiry from the same number is the same client
	again = _function(day_offset=171, customer_name="Eval Repeat Client",
	                  customer_phone="+91 90000 12121")
	bq.link_customer(again)
	assert frappe.db.get_value("Venue Booking", again, "customer") == guest

	bq.set_status(fn, "Confirmed")
	profile = bq.customer_profile(P, guest=guest)
	assert profile["found"], profile
	assert profile["stats"]["functions"] >= 2, profile["stats"]
	assert profile["stats"]["won"] >= 1, profile["stats"]
	assert profile["stats"]["lifetime_value"] > 0, profile["stats"]
	# and findable by the number the phone rang from
	assert bq.customer_profile(P, phone="+91 90000 12121")["found"]


@check("privacy: erasure reaches photos, signatures, occupants, messages, logs and history; export answers access")
def t81():
	import io

	from PIL import Image

	from kamra import api, privacy
	from kamra.savings import log_action

	g = _guest("Evalerase Person", "+91 70000 08101")
	frappe.db.set_value("Guest", g, {"email": "erase@eval.test", "id_type": "Passport",
	                                 "id_number": "Z1234567", "date_of_birth": "1990-01-31"})
	buf = io.BytesIO()
	Image.new("RGB", (8, 8), "white").save(buf, "JPEG")
	f = frappe.get_doc({"doctype": "File", "file_name": "eval-passport.jpg", "is_private": 1,
	                    "attached_to_doctype": "Guest", "attached_to_name": g,
	                    "attached_to_field": "id_file", "content": buf.getvalue()}).insert(ignore_permissions=True)
	frappe.db.set_value("Guest", g, "id_file", f.file_url)
	res = _res(g, "2031-01-10", "2031-01-12", ROOM)
	res.append("occupants", {"full_name": "Evalerase Person", "phone": "+91 70000 08101",
	                         "id_number": "Z1234567"})
	res.save(ignore_permissions=True)
	frappe.db.set_value("Reservation", res.name, {"precheckin_signature": "data:image/png;base64,AAAA",
	                                              "booked_by_phone": "+91 70000 08101"})
	wa = frappe.get_doc({"doctype": "WhatsApp Message", "property": P, "direction": "Outbound",
	                     "status": "Sent", "message_type": "Text", "to_number": "+917000008101",
	                     "guest": g, "reservation": res.name,
	                     "content": "Hi Evalerase Person, see you soon"}).insert(ignore_permissions=True)
	log_action("eval_note", "Reservation", res.name, P, rationale="Called Evalerase Person on +91 70000 08101")
	frappe.get_doc("Guest", g).save(ignore_permissions=True)          # leaves a Version row
	assert frappe.db.count("Version", {"ref_doctype": "Guest", "docname": g}) >= 0

	exported = privacy.export_guest_data(g)
	assert exported["profile"]["email"] == "erase@eval.test" and exported["stays"], exported.keys()

	out = api.anonymize_guest(g)                                          # the UI's path
	alias = out["alias"]
	row = frappe.db.get_value("Guest", g, ["full_name", "phone", "email", "id_number", "id_file",
	                                       "date_of_birth"], as_dict=True)
	assert row.full_name == alias and not any([row.phone, row.email, row.id_number, row.id_file,
	                                           row.date_of_birth]), row
	assert not frappe.db.exists("File", f.name), "ID photo survived erasure"
	r = frappe.get_doc("Reservation", res.name)
	assert not r.precheckin_signature and not r.booked_by_phone and r.guest_name == alias
	occ = r.occupants[0]
	assert occ.full_name == alias and not occ.phone and occ.id_number.endswith("4567") \
		and "Z123" not in occ.id_number, occ.as_dict()
	w = frappe.db.get_value("WhatsApp Message", wa.name, ["content", "to_number", "guest"], as_dict=True)
	assert w.content == "[erased]" and not w.to_number and not w.guest, w
	leaked = frappe.db.sql("""select count(*) from `tabAgent Action Log`
		where rationale like %s or rationale like %s""", ("%Evalerase%", "%70000 08101%"))[0][0]
	assert leaked == 0, "name or phone left in the agent log"
	assert not frappe.db.count("Version", {"ref_doctype": "Guest", "docname": g}), "change history kept PII"
	assert frappe.db.sql("""select count(*) from `tabVersion` where data like %s""", "%Evalerase%")[0][0] == 0


@check("privacy: retention erases idle guests, keeps blacklisted, booked and retention-off ones")
def t82():
	from frappe.utils import add_days

	from kamra import privacy

	frappe.db.set_value("Property", P, "guest_retention_months", 12)
	old = _guest("Evalold Idle", "+91 70000 08201")
	_res(old, add_days(nowdate(), -800), add_days(nowdate(), -798), None, allow_past=1)
	black = _guest("Evalold Banned", "+91 70000 08202")
	_res(black, add_days(nowdate(), -800), add_days(nowdate(), -798), None, allow_past=1)
	frappe.db.set_value("Guest", black, {"blacklisted": 1, "blacklist_reason": "eval"})
	recent = _guest("Evalnew Recent", "+91 70000 08203")
	_res(recent, add_days(nowdate(), -30), add_days(nowdate(), -28), None, allow_past=1)
	for g in (old, black):
		for r in frappe.get_all("Reservation", filters={"guest": g}, pluck="name"):
			frappe.db.set_value("Reservation", r, "status", "Checked Out", update_modified=False)
			frappe.db.sql("update `tabReservation` set modified=%s where name=%s",
			              (add_days(nowdate(), -790), r))
	frappe.db.sql("update `tabGuest` set modified=%s where name in (%s, %s)",
	              (add_days(nowdate(), -790), old, black))
	privacy.apply_retention()
	assert frappe.db.get_value("Guest", old, "full_name").startswith("Guest "), "idle guest kept"
	assert frappe.db.get_value("Guest", black, "full_name") == "Evalold Banned", "blacklisted guest erased"
	assert frappe.db.get_value("Guest", recent, "full_name") == "Evalnew Recent", "recent guest erased"

	frappe.db.set_value("Property", P, "guest_retention_months", 0)
	idle2 = _guest("Evalold Kept", "+91 70000 08204")
	_res(idle2, add_days(nowdate(), -800), add_days(nowdate(), -798), None, allow_past=1)
	frappe.db.sql("update `tabReservation` set status='Checked Out', modified=%s where guest=%s",
	              (add_days(nowdate(), -790), idle2))
	privacy.apply_retention()
	assert frappe.db.get_value("Guest", idle2, "full_name") == "Evalold Kept", "retention off still erased"

	# DPDP Rules: access to personal data stays logged for a year
	from kamra.patches.v34 import keep_access_logs_a_year
	keep_access_logs_a_year.execute()
	days = {r.ref_doctype: r.days for r in frappe.get_single("Log Settings").logs_to_clear}
	assert days.get("Access Log", 0) >= 365 and days.get("Activity Log", 0) >= 365, days


@check("privacy: message retention clears old WhatsApp text and chats, keeps the rows")
def t82b():
	from frappe.utils import add_days, now_datetime

	from kamra import privacy

	def msg(content, age_days):
		name = frappe.get_doc({"doctype": "WhatsApp Message", "property": P, "direction": "Outbound",
		                       "status": "Sent", "content": content}).insert(ignore_permissions=True).name
		frappe.db.sql("update `tabWhatsApp Message` set creation=%s where name=%s",
		              (add_days(now_datetime(), -age_days), name))
		return name

	def chat(age_days):
		name = frappe.get_doc({"doctype": "Copilot Conversation", "property": P, "title": "Evalchat Ravi",
		                       "messages": '[{"role": "user", "content": "Ravi 98450 12345"}]'}
		                      ).insert(ignore_permissions=True).name
		frappe.db.sql("update `tabCopilot Conversation` set modified=%s where name=%s",
		              (add_days(now_datetime(), -age_days), name))
		return name

	old, fresh = msg("Your room 204 is ready, Ravi", 120), msg("See you soon", 10)
	old_chat, fresh_chat = chat(120), chat(10)
	frappe.db.set_value("Property", P, "message_retention_days", 0)
	privacy.apply_message_retention()
	assert frappe.db.get_value("WhatsApp Message", old, "content"), "retention off still cleared"

	frappe.db.set_value("Property", P, "message_retention_days", 90)
	privacy.apply_message_retention()
	row = frappe.db.get_value("WhatsApp Message", old, ["content", "status", "direction"], as_dict=True)
	assert row and not row.content and row.status == "Sent" and row.direction == "Outbound", row
	assert frappe.db.get_value("WhatsApp Message", fresh, "content") == "See you soon", "fresh message cleared"
	c = frappe.db.get_value("Copilot Conversation", old_chat, ["messages", "title"], as_dict=True)
	assert c.messages == "[]" and c.title == privacy.CLEARED_CHAT_TITLE, c
	assert "Ravi" in frappe.db.get_value("Copilot Conversation", fresh_chat, "messages"), "fresh chat cleared"
	frappe.db.set_value("Property", P, "message_retention_days", 0)

	# an upgraded site keeps its history until the hotel chooses a period
	from kamra.patches.v38 import keep_existing_messages
	frappe.db.set_value("Property", P, "message_retention_days", 90)
	keep_existing_messages.execute()
	assert not frappe.db.get_value("Property", P, "message_retention_days")


@check("privacy: a child on the stay register keeps name and age only, unless the register needs the ID")
def t82c():
	from frappe.utils import add_days

	from kamra import api
	from kamra import localization as loc

	def refused(fn):
		try:
			fn()
		except frappe.ValidationError:
			frappe.clear_messages()
			return True
		return False

	g = _guest("Evalfam Parent", "+91 70000 08301")
	r = _res(g, add_days(nowdate(), 40), add_days(nowdate(), 42)).name
	out = api.update_occupants(r, [
		{"full_name": "Evalfam Parent", "age": 38, "nationality": "Indian",
		 "id_type": "Aadhaar", "id_number": "987654321012", "phone": "+917000008301"},
		{"full_name": "Evalfam Child", "age": 9, "nationality": "Indian",
		 "id_type": "Aadhaar", "id_number": "123412341234", "phone": "+917000008302"},
		{"full_name": "Evalfam Visitor", "age": 9, "nationality": "French",
		 "id_type": "Passport", "id_number": "19FR12345", "phone": "+33600000000"},
	])
	rows = {o["full_name"]: o for o in out["rows"]}
	adult, child, visitor = rows["Evalfam Parent"], rows["Evalfam Child"], rows["Evalfam Visitor"]
	assert adult["id_number"] == "987654321012" and adult["phone"], adult
	assert child["age"] == 9 and not (child["id_type"] or child["id_number"] or child["phone"]), child
	# Form C: a foreign child's passport is part of the register; a phone is not
	assert visitor["id_number"] == "19FR12345" and not visitor["phone"], visitor
	assert out["minors_trimmed"] == 2, out
	assert refused(lambda: api.upload_occupant_id(r, child["row"], "data:image/jpeg;base64,AAAA"))

	india, saudi = loc.pack_for(P), loc.pack_for_country("Saudi Arabia")
	assert loc.minor_id_kept(saudi, "Saudi") and not loc.minor_id_kept(india, "Indian")
	assert not loc.is_minor(india, None) and not loc.is_minor(india, "abc") and loc.is_minor(india, 17)
	terms = loc.privacy_terms(india)
	assert terms["adult_age"] == 18 and "hi" in terms["notice_languages"], terms
	assert loc.privacy_terms(loc.pack_for_country("Thailand"))["notice_languages"] == []


@check("public booking: a guest books through the governed agent the install created")
def t83():
	from kamra import public_api
	from kamra.install import AGENT_EMAIL, AGENT_ROLE, ensure_agent_identity

	perms_before = frappe.db.count("Custom DocPerm")
	ensure_agent_identity()  # idempotent on a site that already has it
	assert frappe.db.count("Custom DocPerm") == perms_before, \
		"agent identity must never write custom DocPerms"
	assert AGENT_ROLE in frappe.get_roles(AGENT_EMAIL), "agent lacks its role"

	frappe.set_user("Guest")  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow
	try:
		out = public_api.book(
			property=P, room_type=RT, check_in_date="2031-03-10",
			check_out_date="2031-03-12", guest_name="Web Guest",
			phone="+919812300083", adults=1, children=0,
		)
		assert frappe.session.user == "Guest", "book() must hand the session back"
	finally:
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow
	res = frappe.get_doc("Reservation", out["reservation"])
	assert res.source == "Website", res.source
	assert res.property == P


@check("property scope: restricted staff can't read another property's stays")
def t84():
	"""A Front Desk user pinned to one hotel must not reach another hotel's
	registration card, folio or front-desk list by passing its ids."""
	from kamra import api
	from kamra.agents_api import activity_feed

	other = "EVAL Scope Hotel"
	if not frappe.db.exists("Property", other):
		frappe.get_doc({
			"doctype": "Property", "property_name": other, "city": "Elsewhere",
			"gst_mode": "Slab", "gst_slab_threshold": 7500,
			"gst_rate_low": 5, "gst_rate_high": 18,
		}).insert(ignore_permissions=True)
	g = _guest("Scope Guest", "+91 70000 08484")
	res = _res(g, nowdate(), add_days(nowdate(), 1))  # at P, not `other`

	from kamra.savings import log_action
	log_action("eval.scope", "Reservation", res.name, property=P)
	at_p = set(frappe.get_all("Agent Action Log", {"property": P}, pluck="name"))
	assert at_p, "no activity at P to test the feed against"

	u = "eval.scoped@kamra.local"
	if not frappe.db.exists("User", u):
		frappe.get_doc({
			"doctype": "User", "email": u, "first_name": "Scoped",
			"send_welcome_email": 0, "roles": [{"role": "Front Desk"},
			                                    {"role": "Finance"}],
		}).insert(ignore_permissions=True)
	frappe.get_doc({"doctype": "User Permission", "user": u,
	                "allow": "Property", "for_value": other,
	                }).insert(ignore_permissions=True)

	def refused(fn, **kw):
		try:
			fn(**kw)
		except frappe.PermissionError:
			return
		raise AssertionError(f"{fn.__name__} let a scoped user reach {P}")

	frappe.set_user(u)  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow
	try:
		refused(api.registration_card, reservation=res.name)
		refused(api.get_folio, reservation=res.name)
		refused(api.front_desk_snapshot, property=P)
		refused(api.linked_records, doctype="Reservation", name=res.name)
		refused(api.id_document_image, reservation=res.name)
		refused(api.reservation_detail, reservation=res.name)
		# guest profiles are chain-wide; one who only stayed at P is hidden
		refused(api.guest_journey, guest=g)
		assert g not in {r["name"] for r in api.guest_search("Scope Guest")}, \
			"guest search leaked"
		assert g not in {r["name"] for r in api.guests_with_stats("Scope Guest")}, \
			"guest list leaked"
		# leaving property out must not widen the view to the whole chain
		snap = api.front_desk_snapshot()
		rows = snap["arrivals"] + snap["departures"] + snap["in_house"]
		assert res.name not in {r["name"] for r in rows}, "snapshot leaked"
		feed = {r["name"] for r in activity_feed(limit=200)}
		assert not feed & at_p, "activity feed leaked"
	finally:
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow
	# an unrestricted user is unaffected
	assert api.registration_card(res.name)["reservation"]["name"] == res.name


@check("webhooks refuse calls when no secret is configured")
def t85():
	import base64

	from kamra import channel_manager as cm
	from kamra.agents_channels import _authenticate
	from kamra.channels import aiosell

	conn = frappe.get_doc({
		"doctype": "Channel Manager Connection", "property": P,
		"provider": "Custom", "active": 1,
	}).insert(ignore_permissions=True)
	try:
		cm.webhook(connection=conn.name, event="cancel")
		raise AssertionError("channel webhook accepted with no secret set")
	except frappe.PermissionError:
		pass

	blank = frappe._dict(api_username="",
	                     get_password=lambda *a, **k: "")
	frappe.local.flags.aiosell_webhook_auth = \
		"Basic " + base64.b64encode(b":").decode()
	try:
		assert not aiosell._auth_ok(blank), "empty AioSell creds accepted"
	finally:
		frappe.local.flags.aiosell_webhook_auth = None

	frappe.get_doc({
		"doctype": "Channel Provider Connection", "property": P,
		"channel": "Voice", "provider": "Custom", "active": 1,
		"phone_number": "+91 80000 08585",
	}).insert(ignore_permissions=True)
	assert _authenticate("Voice", {"phone_number": "+91 80000 08585"}) is None, \
		"voice webhook accepted with no secret set"


def _checkout_unsettled(reservation):
	"""For checks about something other than the bill (ID retention, HK)."""
	from kamra import api
	frappe.flags.allow_unsettled_checkout = True
	try:
		return api.check_out(reservation)
	finally:
		frappe.flags.allow_unsettled_checkout = False


@check("checkout: refused while owed or owing; a credit company goes to city ledger (#132)")
def t86():
	from kamra import api
	g = _guest("Eval Checkout", "+91 70000 00086")
	res = _res(g, "2036-02-01", "2036-02-03", ROOM)
	res.status = "Checked In"
	res.save(ignore_permissions=True)
	folio = frappe.db.get_value("Folio", {"reservation": res.name, "folio_type": "Guest"})

	try:
		api.check_out(res.name)
		raise AssertionError("checked out with an unpaid bill")
	except frappe.ValidationError as e:
		assert "still owed" in str(e), e
	assert frappe.db.get_value("Reservation", res.name, "status") == "Checked In"
	owed = float(frappe.db.get_value("Folio", folio, "balance") or 0)
	assert owed > 0, "the guard did not post the stay's nights before judging the balance"

	api.add_folio_payment(folio, "Cash", owed + 500)
	try:
		api.check_out(res.name)
		raise AssertionError("checked out while the guest was owed a refund")
	except frappe.ValidationError as e:
		assert "owed" in str(e) and "refund" in str(e), e

	api.refund_folio_payment(folio, 500, "Cash", "over-collected at the desk")
	api.check_out(res.name)
	assert frappe.db.get_value("Reservation", res.name, "status") == "Checked Out"

	# the company pays the room (its billing rule): that folio goes to AR at
	# check-out; the guest's own folio is never moved there
	comp = frappe.get_doc({"doctype": "Corporate Account", "company_name": "EVAL Credit Corp",
	                       "credit_allowed": 1,
	                       "billing_rules": [{"charge_type": "Room", "pay_by": "Company"}],
	                       }).insert(ignore_permissions=True)
	g2 = _guest("Eval Corporate Checkout", "+91 70000 00087")
	res2 = _res(g2, "2036-02-05", "2036-02-06", ROOM)
	res2.booking_type = "Corporate"
	res2.company = comp.name
	res2.status = "Checked In"
	res2.save(ignore_permissions=True)
	api.check_out(res2.name)
	folio2 = frappe.db.get_value("Folio", {"reservation": res2.name, "folio_type": "Company"})
	assert folio2, "the room never reached the company folio"
	assert abs(float(frappe.db.get_value("Folio", folio2, "balance") or 0)) < 0.01
	assert frappe.db.exists("City Ledger Entry", {"folio": folio2}), "credit stay never reached AR"
	guest2 = frappe.db.get_value("Folio", {"reservation": res2.name, "folio_type": "Guest"})
	assert not frappe.db.exists("City Ledger Entry", {"folio": guest2}), "guest folio billed to AR"


@check("city ledger transfer posts balanced legs: guest ledger credited, AR debited")
def t93():
	from kamra import api
	from kamra.ledger import ledger_balances, transfer_to_city_ledger
	comp = frappe.get_doc({"doctype": "Corporate Account", "company_name": "EVAL CL Balance Corp",
	                       "credit_allowed": 1}).insert(ignore_permissions=True)
	g = _guest("Eval City Ledger", "+91 70000 00193")
	res = _res(g, "2036-03-01", "2036-03-02", ROOM)
	res.booking_type = "Corporate"
	res.company = comp.name
	res.status = "Checked In"
	res.save(ignore_permissions=True)
	folio = frappe.db.get_value("Folio", {"reservation": res.name, "folio_type": "Guest"})
	api.add_folio_charge(folio, "Misc", "eval city ledger charge", 2500)

	def side(f=None):
		rows = frappe.get_all("Folio Ledger Entry",
		                      filters={"property": P, **({"folio": f} if f else {})},
		                      fields=["ledger", "debit", "credit"])
		out = {}
		for r in rows:
			d, c = out.get(r.ledger, (0.0, 0.0))
			out[r.ledger] = (d + float(r.debit or 0), c + float(r.credit or 0))
		return out

	tb0 = ledger_balances(P)
	before = side(folio)
	amount = transfer_to_city_ledger(folio, comp.name)["amount"]
	tb1 = ledger_balances(P)
	after = side(folio)

	moved_dr = (tb1["total_debit"] - tb0["total_debit"])
	moved_cr = (tb1["total_credit"] - tb0["total_credit"])
	assert abs(moved_dr - moved_cr) < 0.01, \
		f"transfer unbalanced the trial balance: Dr {moved_dr} vs Cr {moved_cr}"
	assert abs(moved_dr - amount) < 0.01, f"AR debit {moved_dr} != transferred {amount}"
	guest_cr = after.get("Guest", (0, 0))[1] - before.get("Guest", (0, 0))[1]
	assert abs(guest_cr - amount) < 0.01, f"guest ledger not credited ({guest_cr} of {amount})"
	ar_dr = after.get("AR", (0, 0))[0] - before.get("AR", (0, 0))[0]
	assert abs(ar_dr - amount) < 0.01, f"AR not debited ({ar_dr} of {amount})"
	assert abs(float(frappe.db.get_value("Folio", folio, "balance") or 0)) < 0.01
	# the folio's own entries: what was charged and moved nets to zero across ledgers
	fd = sum(v[0] for v in after.values()) - sum(v[0] for v in before.values())
	fc = sum(v[1] for v in after.values()) - sum(v[1] for v in before.values())
	assert abs(fd - fc) < 0.01, f"folio postings Dr {fd} vs Cr {fc}"


@check("night audit refuses a future or non-current date; a no-show's due comes from its folio")
def t87():
	from kamra import api
	from kamra.folio import run_night_audit
	today = nowdate()
	saved = frappe.db.get_value("Property", P, ["business_date", "no_show_charge"],
	                            as_dict=True)
	frappe.db.set_value("Property", P, {"business_date": today,
	                                    "no_show_charge": "First Night"})
	try:
		# only the dates this check closes or probes - other checks' runs stay
		for d in (today, add_days(today, -3), add_days(today, 1), add_days(today, 2)):
			frappe.db.delete("Night Audit Run", {"property": P, "business_date": d})

		# closing a date other than the current business date is refused
		for bad in (add_days(today, -3), add_days(today, 2)):
			try:
				run_night_audit(P, bad)
				raise AssertionError(f"audit closed non-current date {bad}")
			except frappe.ValidationError:
				pass

		# the business date may not run ahead of the calendar: once today is
		# closed (bd -> tomorrow), a second click is refused, not a 2nd night
		g = _guest("Eval NoShow Due", "+91 70000 00088")
		ns = _res(g, add_days(today, -1), add_days(today, 2), allow_past=1)
		run_night_audit(P)
		assert getdate(frappe.db.get_value("Property", P, "business_date")) == getdate(add_days(today, 1))
		try:
			run_night_audit(P)
			raise AssertionError("audit ran for a business date that hasn't started")
		except frappe.ValidationError as e:
			assert "ahead of today" in str(e), e
		assert getdate(frappe.db.get_value("Property", P, "business_date")) == getdate(add_days(today, 1))

		# the no-show owes the policy fee on its folio, not the booking total
		assert frappe.db.get_value("Reservation", ns.name, "status") == "No Show"
		folio = frappe.db.get_value("Folio", {"reservation": ns.name, "folio_type": "Guest"},
		                            ["grand_total", "balance"], as_dict=True)
		money = api.reservation_detail(ns.name)["money"]
		assert money["source"] == "folio", money
		assert abs(money["due"] - float(folio.balance)) < 0.01, (money, folio)
		assert money["total"] < float(ns.amount_after_tax), (money, ns.amount_after_tax)
	finally:
		frappe.db.set_value("Property", P, {
			"business_date": saved.business_date,
			"no_show_charge": saved.no_show_charge})


@check("settings: module pages validate, save and drive the code that reads them")
def t90():
	from kamra import settings as st
	from kamra.kamra.doctype.housekeeping_task.housekeeping_task import sla_minutes

	assert st.get_setting(P, "hk_sla_urgent") == 20, "default changed"
	st.save_settings(P, "housekeeping", json.dumps({"hk_sla_urgent": 25}))
	assert sla_minutes(P, "Urgent") == 25, "HK deadline ignores the setting"
	for module, bad in (("housekeeping", {"hk_sla_urgent": 0}),           # below min
	                    ("housekeeping", {"overbooking_pct": 5}),         # other page
	                    ("policies", {"checkin_time": "25:00"}),
	                    ("policies", {"cancellation_fee": "Bogus"})):
		try:
			st.save_settings(P, module, json.dumps(bad))
		except frappe.ValidationError:
			continue
		raise AssertionError(f"accepted {bad}")
	log = frappe.get_all("Agent Action Log", {"property": P, "action_type": "settings_changed"},
	                     pluck="name")
	assert log, "a settings change wasn't logged"
	st.save_settings(P, "housekeeping", json.dumps({"hk_sla_urgent": 20}))
	st.clear_cache(P)


@check("settings: a role edits only its own pages; staff access stays inside the admin's reach")
def t91():
	from kamra import settings as st, staff

	u = "eval.revenue.settings@kamra.local"
	staff.save_staff(P, u, "Eval Revenue", json.dumps(["Revenue Manager"]), json.dumps([P]))
	row = next(r for r in staff.list_staff(P) if r["user"] == u)
	assert row["roles"] == ["Revenue Manager"] and row["properties"] == [P], row
	frappe.set_user(u)  # nosemgrep: frappe-setuser -- controlled user context switch for an RBAC check
	try:
		pages = {m["id"] for m in st.settings_schema(P)["modules"]}
		assert "revenue" in pages and "finance" not in pages, pages
		st.save_settings(P, "revenue", json.dumps({"overbooking_pct": 2}))
		for fn, kw in ((st.save_settings, {"property": P, "module": "finance",
		                                   "changes": json.dumps({"pin_max_attempts": 4})}),
		               (staff.save_staff, {"property": P, "email": "x.eval@kamra.local",
		                                   "full_name": "X", "roles": json.dumps(["Front Desk"])})):
			try:
				fn(**kw)
			except frappe.PermissionError:
				continue
			raise AssertionError(f"{fn.__name__} let a revenue manager through")
	finally:
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- controlled user context switch for an RBAC check
	# a Hotel Admin can't hand out IT's role
	gm = "eval.gm.settings@kamra.local"
	staff.save_staff(P, gm, "Eval GM", json.dumps(["Hotel Admin"]), "all")
	frappe.set_user(gm)  # nosemgrep: frappe-setuser -- controlled user context switch for an RBAC check
	try:
		staff.save_staff(P, u, "Eval Revenue", json.dumps(["System Manager"]), json.dumps([P]))
		raise AssertionError("a Hotel Admin granted System Manager")
	except frappe.PermissionError:
		pass
	finally:
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- controlled user context switch for an RBAC check
	st.save_settings(P, "revenue", json.dumps({"overbooking_pct": 0}))


@check("folio void from the bill screen: reason required, PIN-gated, ledger reversed, logged")
def t95():
	"""The bill screen voids a line with call("kamra.api.void_folio_charge",
	{folio, charge_row, reason}) as Front Desk, after the PinPad unlock.
	Issue #160: the screen sent no reason, so every void was refused."""
	from kamra import api
	g = _guest("Eval Void", "+91 70000 00196")
	res = _res(g, "2033-05-11", "2033-05-12", ROOM)
	res.status = "Checked In"
	res.save(ignore_permissions=True)
	folio = api.split_folio(res.name, "Extra")["folio"]
	api.add_folio_charge(folio, "Laundry", "eval wrong line", 400, 0)
	row = next(c.name for c in frappe.get_doc("Folio", folio).charges
	           if c.description == "eval wrong line")
	orig = frappe.db.get_value("Folio Ledger Entry", {
		"source_name": row, "reversal_of": ["in", ["", None]]}, "name")
	assert orig, "the charge left no ledger entry to reverse"
	from kamra.authz import act_as
	pin_before = frappe.db.get_value("Property", P, "require_cashier_pin")
	frappe.db.set_value("Property", P, "require_cashier_pin", 1)
	user = "frontdesk@kamra.local"
	unlock = f"kamra_cashier_unlock:{user}"
	try:
		with act_as(user):
			# no PinPad unlock yet - the PIN policy still holds
			frappe.cache.delete_value(unlock)
			try:
				api.void_folio_charge(**{"folio": folio, "charge_row": row,
				                         "reason": "posted to the wrong room"})
				raise AssertionError("a void skipped the cashier PIN")
			except frappe.ValidationError as e:
				assert "PIN" in str(e), e
			# after the unlock: the exact payload the screen sends
			frappe.cache.set_value(unlock, 1, expires_in_sec=60)
			# the pre-#160 call shape (no reason) and a blank one: refused
			for bad in ({}, {"reason": "  "}):
				try:
					api.void_folio_charge(**{"folio": folio, "charge_row": row, **bad})
					raise AssertionError(f"a void went through with {bad}")
				except frappe.ValidationError as e:
					assert "reason" in str(e).lower(), e
			out = api.void_folio_charge(**{"folio": folio, "charge_row": row,
			                               "reason": "posted to the wrong room"})
	finally:
		frappe.cache.delete_value(unlock)
		frappe.db.set_value("Property", P, "require_cashier_pin", pin_before or 0)
	assert out["removed"]["amount"] == 400, out
	doc = frappe.get_doc("Folio", folio)
	assert not any(c.name == row for c in doc.charges), "line still on the bill"
	rev = frappe.db.get_value("Folio Ledger Entry", {"reversal_of": orig},
	                          ["debit", "credit", "description"], as_dict=True)
	assert rev and float(rev.credit) == frappe.db.get_value(
		"Folio Ledger Entry", orig, "debit"), rev
	assert "posted to the wrong room" in rev.description, rev
	assert frappe.db.exists("Agent Action Log", {
		"action_type": "void_charge", "reference_name": folio}), "void not logged"


@check("whole-villa booking: checks in with no room, audits, checks out (rooms occupied then dirty)")
def t94():
	from kamra import api
	from kamra.folio import run_night_audit
	VP = "EVAL Villa Estate"
	frappe.get_doc({
		"doctype": "Property", "property_name": VP, "city": "Testville",
		"gst_mode": "Slab", "gst_slab_threshold": 7500,
		"gst_rate_low": 5, "gst_rate_high": 18,
	}).insert(ignore_permissions=True)
	villa = frappe.get_doc({
		"doctype": "Room Type", "property": VP, "room_type_code": "EVV",
		"room_type_name": "Eval Whole Villa", "base_price": 20000,
		"base_occupancy": 4, "adults_capacity": 6, "children_capacity": 2,
		"room_category": "Villa", "tax_percent": 18,
	}).insert(ignore_permissions=True)
	bed = frappe.get_doc({
		"doctype": "Room Type", "property": VP, "room_type_code": "EVB",
		"room_type_name": "Eval Villa Bedroom", "base_price": 6000,
		"base_occupancy": 2, "adults_capacity": 2, "tax_percent": 5,
	}).insert(ignore_permissions=True)
	rooms = [frappe.get_doc({
		"doctype": "Room", "property": VP, "room_number": n,
		"room_type": bed.name,
	}).insert(ignore_permissions=True).name for n in ("V1", "V2")]

	today = nowdate()
	g = _guest("Eval Villa Guest", "+91 70000 00194")
	res = frappe.get_doc({
		"doctype": "Reservation", "property": VP, "guest": g,
		"room_type": villa.name, "check_in_date": today,
		"check_out_date": add_days(today, 2), "adults": 4, "auto_price": 1,
	}).insert(ignore_permissions=True)
	assert not res.room

	assert api.reservation_detail(res.name)["actions"]["can_check_in"], \
		"whole-villa stay offered no check-in"
	ctx = api.checkin_context(res.name)
	assert ctx["entire_place"] == {"rooms": ["V1", "V2"]}, ctx["entire_place"]

	api.check_in(res.name)
	assert frappe.db.get_value("Reservation", res.name, "status") == "Checked In"
	for r in rooms:
		assert frappe.db.get_value("Room", r, "occupancy_status") == "Occupied", r
	folio = frappe.db.get_value("Folio", {"reservation": res.name, "folio_type": "Guest"})
	assert folio, "no folio opened at check-in"

	frappe.db.set_value("Property", VP, "business_date", today)
	out = run_night_audit(VP)
	assert out.get("room_charges_posted") == 1, out
	assert frappe.db.exists("Folio Charge", {
		"parent": folio, "posting_date": today, "charge_type": "Room"}), \
		"room night never reached the folio"

	try:
		api.check_out(res.name)
		raise AssertionError("checked out with an unpaid bill")
	except frappe.ValidationError as e:
		assert "still owed" in str(e), e
	owed = float(frappe.db.get_value("Folio", folio, "balance") or 0)
	assert owed > 0
	api.add_folio_payment(folio, "Cash", owed)
	api.check_out(res.name)
	assert frappe.db.get_value("Reservation", res.name, "status") == "Checked Out"
	for r in rooms:
		st = frappe.db.get_value("Room", r, ["occupancy_status", "housekeeping_status"])
		assert tuple(st) == ("Vacant", "Dirty"), (r, st)
		assert frappe.db.exists("Housekeeping Task", {
			"room": r, "reservation": res.name, "task_type": "Checkout Clean"}), r

	# a roomless stay that is NOT an entire place still needs a room
	g2 = _guest("Eval Bedroom Guest", "+91 70000 00195")
	r2 = frappe.get_doc({
		"doctype": "Reservation", "property": VP, "guest": g2,
		"room_type": bed.name, "check_in_date": add_days(today, 5),
		"check_out_date": add_days(today, 6), "adults": 2, "auto_price": 1,
	}).insert(ignore_permissions=True)
	assert not api.reservation_detail(r2.name)["actions"]["can_check_in"]
	try:
		api.check_in(r2.name)
		raise AssertionError("room-type stay checked in with no room")
	except frappe.ValidationError as e:
		assert "Assign a room" in str(e), e


@check("HK phone: posting a charge or delivering laundry keeps the staff session")
def t92():
	# hk_post_consumable / deliver_laundry post as agent@kamra.local. A bare
	# frappe.set_user() swap wiped the caller's sid + session data (csrf token,
	# expiry), Frappe cached that after the request and the housekeeper's
	# next call came back 403 "User None" - logged out mid-shift.
	from kamra import api, laundry
	room = frappe.db.exists("Room", {"property": P, "room_number": "E109"})
	if not room:
		room = frappe.get_doc({
			"doctype": "Room", "property": P, "room_number": "E109",
			"room_type": RT,
		}).insert(ignore_permissions=True).name
	else:
		frappe.db.set_value("Room", room, "room_type", RT)
	# far-dated: today's EVAL inventory is already sold out by earlier checks,
	# and both endpoints only look for a Checked In stay on the room
	res = _res(_guest("Eval HK Session", "+91 70000 00092"),
	           "2031-02-10", "2031-02-12", room)
	res.status = "Checked In"
	res.save(ignore_permissions=True)
	laundry.save_laundry_rate(P, "Shirt", "Wash & Iron", 60)

	real = frappe.local.session
	frappe.local.session = frappe._dict(
		user="Administrator", sid="eval-hk-sid",
		data=frappe._dict(csrf_token="eval-csrf", session_expiry="06:00:00"))
	try:
		def intact(step):
			s = frappe.local.session
			assert (s.user, s.sid) == ("Administrator", "eval-hk-sid"), (step, s)
			assert s.data.get("csrf_token") == "eval-csrf", (step, s.data)

		api.hk_post_consumable(room, "Minibar", "eval 1 water", 40)
		intact("hk_post_consumable")

		r = laundry.request_pickup(P, room)
		laundry.collect_laundry(P, room, [
			{"item_name": "Shirt", "service_type": "Wash & Iron", "qty": 1}],
			order=r["order"])
		laundry.laundry_status(r["order"], "In Process")
		laundry.laundry_status(r["order"], "Ready")
		doc = frappe.get_doc("Laundry Order", r["order"])
		laundry.return_items(r["order"], {doc.items[0].name: 1})
		out = laundry.deliver_laundry(r["order"])
		assert out["posted_to_folio"], out
		intact("deliver_laundry")
	finally:
		frappe.local.session = real


@check("agent booking refs: names / codes resolve to this property's IDs; unknown or ambiguous refuse with options")
def t98():
	from kamra import api
	from kamra.booking_refs import resolve_meal_plan, resolve_room_type

	frappe.db.delete("Meal Plan", {"property": P})  # rolled back after the run
	for mp, label in (("CP", "Breakfast"), ("MAP", "Half Board")):
		frappe.get_doc({"doctype": "Meal Plan", "property": P, "code": mp,
		                "label": label, "price_per_adult": 300,
		                }).insert(ignore_permissions=True)
	for v in (RT, "Eval Room", "eval room", "evl", " EVL "):
		assert resolve_room_type(P, v) == RT, v
	assert resolve_meal_plan(P, "breakfast") == f"{P}-CP"
	assert resolve_meal_plan(P, "map") == f"{P}-MAP"
	assert resolve_meal_plan(P, "") is None
	# what the agent actually sends now works end to end
	q = api.get_quote(P, "Eval Room", "2030-02-01", "2030-02-02",
	                  meal_plan="Breakfast")
	assert q["room_total"] == 4000, q
	# unknown -> refused, listing the valid options; never a guess
	try:
		api.get_quote(P, "Deluxe", "2030-02-01", "2030-02-02")
		raise AssertionError("unknown room type accepted")
	except frappe.ValidationError as e:
		assert "Eval Room" in str(e) and RT in str(e), e
	# a prefix is not a match
	try:
		resolve_room_type(P, "Eval")
		raise AssertionError("prefix guessed")
	except frappe.ValidationError:
		pass
	# ambiguous names refuse with both candidates
	frappe.get_doc({"doctype": "Meal Plan", "property": P, "code": "AP",
	                "label": "BREAKFAST", "price_per_adult": 350,
	                }).insert(ignore_permissions=True)
	try:
		resolve_meal_plan(P, "Breakfast")
		raise AssertionError("ambiguous meal plan resolved")
	except frappe.ValidationError as e:
		assert f"{P}-AP" in str(e) and f"{P}-CP" in str(e), e
	# another property's ID is refused, not booked across properties
	other = "EVAL Refs Other"
	if not frappe.db.exists("Property", other):
		frappe.get_doc({"doctype": "Property", "property_name": other,
		                "city": "Elsewhere"}).insert(ignore_permissions=True)
	ort = frappe.get_doc({"doctype": "Room Type", "property": other,
	                      "room_type_code": "OTH", "room_type_name": "Other Room",
	                      "base_price": 1000}).insert(ignore_permissions=True)
	try:
		resolve_room_type(P, ort.name)
		raise AssertionError("another property's room type accepted")
	except frappe.ValidationError as e:
		assert "another property" in str(e), e


@check("agent bookings are idempotent: retries return the first booking; desk multi-room still books")
def t96():
	from kamra import api
	from kamra.mcp_tools import TOOLS, call_tool

	spec = next(t for t in TOOLS if t.name == "create_booking")
	# earlier checks fill this tiny property; capacity isn't under test here
	frappe.db.set_value("Property", P, "overbooking_pct", 400)
	args = {"guest_name": "Eval Retry Guest", "room_type": "Eval Room",
	        "check_in_date": "2031-03-01", "check_out_date": "2031-03-03"}
	first = call_tool(spec, dict(args), P)
	again = call_tool(spec, dict(args), P)  # the model retried
	assert again["reservation"] == first["reservation"], (first, again)
	assert again.get("idempotent_replay") and again.get("duplicate_of_recent"), again
	assert frappe.db.count("Reservation", {
		"property": P, "check_in_date": "2031-03-01",
		"guest_name": "Eval Retry Guest"}) == 1
	# same guest by phone (a different spelling of the name) is still a retry
	pa = dict(args, guest_name="Eval Phone Guest", phone="+91 70000 09301")
	one = call_tool(spec, dict(pa), P)
	two = call_tool(spec, dict(pa, guest_name="eval phone guest"), P)
	assert one["reservation"] == two["reservation"], (one, two)
	# an explicit idempotency key: same key replays, a new key books again
	ka = dict(args, guest_name="Eval Key Guest", idempotency_key="eval-k-1")
	k1 = call_tool(spec, dict(ka), P)
	k1b = call_tool(spec, dict(ka), P)
	k2 = call_tool(spec, dict(ka, idempotency_key="eval-k-2"), P)
	assert k1b["reservation"] == k1["reservation"], (k1, k1b)
	assert k2["reservation"] != k1["reservation"], "a new key was refused"
	# different dates are a different booking
	other = call_tool(spec, dict(args, check_out_date="2031-03-04"), P)
	assert other["reservation"] != first["reservation"]
	# the desk books several identical rooms for one party: never blocked
	d1 = api.create_booking(P, RT, "2031-04-01", "2031-04-02", "Eval Desk Party",
	                        phone="+91 70000 09302", assign_room=0)
	d2 = api.create_booking(P, RT, "2031-04-01", "2031-04-02", "Eval Desk Party",
	                        phone="+91 70000 09302", assign_room=0)
	assert d1["reservation"] != d2["reservation"] and not d2.get("idempotent_replay"), d2


@check("agent activity log: Chat / MCP actions land in the log; a bad row is never lost silently")
def t97():
	import json as _json
	import os

	from kamra.savings import log_action

	# the doctype ships the channels the agent layers write
	path = os.path.join(os.path.dirname(frappe.get_module_path("kamra")),
	                    "kamra", "doctype", "agent_action_log", "agent_action_log.json")
	with open(path) as f:  # nosemgrep: frappe-security-file-traversal -- path is built from the installed app's own module directory and fixed names; eval script, no user input
		field = next(x for x in _json.load(f)["fields"] if x["fieldname"] == "action_channel")
	assert {"Chat", "MCP"} <= set(field["options"].split("\n")), field["options"]

	live = frappe.get_meta("Agent Action Log").get_field("action_channel").options.split("\n")
	for ch in ("Chat", "MCP", "QR"):
		name = log_action(f"eval_channel_{ch.lower()}", "Property", P, P,
		                  rationale="eval", agent_name="Eval", channel=ch)
		assert name, f"{ch} action never reached the log"
		got = frappe.db.get_value("Agent Action Log", name, ["action_channel", "rationale"], as_dict=True)
		if ch in live:
			assert got.action_channel == ch, got
		else:  # an unmigrated / unknown channel maps instead of failing the row
			assert got.action_channel == "API" and f"[channel: {ch}]" in got.rationale, got

	# the copilot's chat path writes its audit line
	from kamra import assistant
	before = frappe.db.count("Agent Action Log", {"action_type": "copilot_create_booking"})
	assistant._run_tool("create_booking", {
		"guest_name": "Eval Chat Guest", "room_type": "EVL",
		"check_in_date": "2031-05-01", "check_out_date": "2031-05-02"}, P)
	assert frappe.db.count("Agent Action Log", {"action_type": "copilot_create_booking"}) == before + 1

	# a row that can't validate is retried minimally and reported, not dropped
	errs = frappe.db.count("Error Log")
	name = log_action("eval_bad_ref", "Reservation", "NO-SUCH-RES-EVAL", P,
	                  rationale="eval", agent_name="Eval", channel="Chat")
	assert name, "fallback row not written"
	assert "log fallback" in frappe.db.get_value("Agent Action Log", name, "rationale")
	assert frappe.db.count("Error Log") > errs, "failure not reported"


@check("group pickup: an agent picks up a second room for the same party; a key makes the retry safe")
def t100():
	from kamra.mcp_tools import BY_NAME, call_tool

	frappe.db.set_value("Property", P, "overbooking_pct", 400)
	block = call_tool(BY_NAME["create_group_block"], {
		"group_name": "EVAL Pickup Party", "check_in_date": "2031-06-01",
		"check_out_date": "2031-06-03",
		"blocks": [{"room_type": "Eval Room", "rooms_blocked": 3}]}, P)
	gb = block.get("group_booking") or block.get("name")
	assert gb, block
	frappe.db.set_value("Group Booking", gb, "status", "Confirmed")
	pick = BY_NAME["pickup_group_room"]
	args = {"group_booking": gb, "room_type": "Eval Room",
	        "guest_name": "Eval Pickup Lead"}
	one = call_tool(pick, dict(args), P)
	two = call_tool(pick, dict(args), P)  # a second room for the same party
	assert one["reservation"] != two["reservation"], (one, two)
	assert not two.get("idempotent_replay"), two
	assert frappe.db.count("Reservation", {"group_booking": gb}) == 2
	# with a key, a retried pickup returns the first one
	k1 = call_tool(pick, dict(args, idempotency_key="eval-pick-1"), P)
	k1b = call_tool(pick, dict(args, idempotency_key="eval-pick-1"), P)
	assert k1b["reservation"] == k1["reservation"] and k1b.get("idempotent_replay"), k1b
	assert frappe.db.count("Reservation", {"group_booking": gb}) == 3


@check("agent duplicate guard: a changed meal plan or party size is a new booking; only live stays count")
def t101():
	from kamra.mcp_tools import BY_NAME, call_tool

	frappe.db.set_value("Property", P, "overbooking_pct", 400)
	mp = frappe.db.get_value("Meal Plan", {"property": P, "disabled": 0}) or \
		frappe.get_doc({"doctype": "Meal Plan", "property": P, "code": "EP",
		                "label": "Eval Room Only", "price_per_adult": 0,
		                }).insert(ignore_permissions=True).name
	spec = BY_NAME["create_booking"]
	args = {"guest_name": "Eval  Changed Mind ", "room_type": "Eval Room",
	        "check_in_date": "2031-07-01", "check_out_date": "2031-07-02",
	        "adults": 2}
	first = call_tool(spec, dict(args), P)
	# the same request, spelt with other whitespace and case: a retry
	again = call_tool(spec, dict(args, guest_name="eval changed mind"), P)
	assert again["reservation"] == first["reservation"] and again.get("duplicate_of_recent"), again
	meal = call_tool(spec, dict(args, meal_plan=mp), P)
	assert meal["reservation"] != first["reservation"] and not meal.get("idempotent_replay"), meal
	fewer = call_tool(spec, dict(args, adults=1), P)
	assert fewer["reservation"] not in (first["reservation"], meal["reservation"]), fewer
	assert not fewer.get("idempotent_replay"), fewer
	# a cancelled (or Inquiry) stay is not a booking to hand back
	frappe.db.set_value("Reservation", fewer["reservation"], "status", "Inquiry")
	redo = call_tool(spec, dict(args, adults=1), P)
	assert redo["reservation"] != fewer["reservation"] and not redo.get("idempotent_replay"), redo


@check("idempotency_key: a key reused for a different booking is refused, not replayed")
def t102():
	from kamra.mcp_tools import BY_NAME, call_tool

	frappe.db.set_value("Property", P, "overbooking_pct", 400)
	spec = BY_NAME["create_booking"]
	args = {"guest_name": "Eval Key Owner", "room_type": "Eval Room",
	        "check_in_date": "2031-08-01", "check_out_date": "2031-08-03",
	        "idempotency_key": "eval-reuse-1"}
	first = call_tool(spec, dict(args), P)
	same = call_tool(spec, dict(args, guest_name="eval  key owner"), P)
	assert same["reservation"] == first["reservation"] and same.get("idempotent_replay"), same
	for change in ({"check_out_date": "2031-08-04"},
	               {"guest_name": "Somebody Else"}):
		try:
			call_tool(spec, dict(args, **change), P)
			raise AssertionError(f"reused key replayed for {change}")
		except frappe.ValidationError as e:
			assert "already used for a different booking" in str(e), e


@check("copilot duplicate: caught on the Chat path, logged as Chat, no phantom Executed row")
def t103():
	from kamra import assistant

	frappe.db.set_value("Property", P, "overbooking_pct", 400)
	args = {"guest_name": "Eval Chat Retry", "room_type": "EVL",
	        "check_in_date": "2031-09-01", "check_out_date": "2031-09-02"}
	before = frappe.db.count("Agent Action Log", {"action_type": "copilot_create_booking"})
	first = assistant._run_tool("create_booking", dict(args), P)
	again = assistant._run_tool("create_booking", dict(args), P)
	assert again["reservation"] == first["reservation"] and again.get("duplicate_of_recent"), again
	assert frappe.db.get_value("Reservation", first["reservation"], "source") == "AI Agent"
	assert frappe.db.count("Agent Action Log", {
		"action_type": "copilot_create_booking"}) == before + 1, "replay logged as executed"
	live = frappe.get_meta("Agent Action Log").get_field("action_channel").options.split("\n")
	for action in ("create_reservation", "agent_duplicate_booking_blocked"):
		got = frappe.db.get_value("Agent Action Log", {
			"action_type": action, "reference_name": first["reservation"]},
			["action_channel", "rationale"], as_dict=True)
		assert got, f"no {action} row"
		if "Chat" in live:
			assert got.action_channel == "Chat", (action, got)
		else:  # an unmigrated site maps Chat to API and keeps the name
			assert "[channel: Chat]" in got.rationale, (action, got)


@check("create_group_block resolves room type names and codes; unknown is refused")
def t104():
	from kamra import api

	out = api.create_group_block(P, "EVAL Named Block", "2031-10-01", "2031-10-02",
	                             [{"room_type": "Eval Room", "rooms_blocked": 2},
	                              {"room_type": "evl", "rooms_blocked": 1}])
	gb = frappe.get_doc("Group Booking", out.get("group_booking") or out.get("name"))
	assert [b.room_type for b in gb.blocks] == [RT, RT], [b.room_type for b in gb.blocks]
	try:
		api.create_group_block(P, "EVAL Bad Block", "2031-10-01", "2031-10-02",
		                       [{"room_type": "Presidential", "rooms_blocked": 1}])
		raise AssertionError("unknown room type accepted")
	except frappe.ValidationError as e:
		assert "Eval Room" in str(e), e


@check("scheduled night audit skips a property whose business date is today; closes yesterday")
def t110():
	from unittest.mock import patch
	from kamra import folio as folio_mod
	today = nowdate()
	saved = frappe.db.get_value("Property", P, "business_date")
	calls = []
	try:
		# 04:00 on the property clock: past the default 03:00 run time
		with patch.object(folio_mod, "run_night_audit",
		                  side_effect=lambda prop, *a, **k: calls.append(prop)), \
		     patch.object(folio_mod, "audit_clock",
		                  return_value=get_datetime(f"{today} 04:00:00")):
			# staff closed yesterday by hand at 23:00: today has only just begun
			frappe.db.set_value("Property", P, "business_date", today)
			folio_mod.nightly_audit_all_properties()
			assert P not in calls, "the 03:00 cron closed a day that just started"
			# a lagging business date is still closed by the cron
			frappe.db.set_value("Property", P, "business_date", add_days(today, -1))
			folio_mod.nightly_audit_all_properties()
			assert P in calls, "the cron skipped yesterday's open business date"
	finally:
		frappe.db.set_value("Property", P, "business_date", saved)


@check("night audit retry after success answers already_ran, not an error")
def t111():
	from kamra.folio import run_night_audit
	today = nowdate()
	saved = frappe.db.get_value("Property", P, "business_date")
	frappe.db.set_value("Property", P, "business_date", today)
	try:
		frappe.db.delete("Night Audit Run", {"property": P, "business_date": today})
		first = run_night_audit(P, today)
		assert not first.get("already_ran"), first
		# the business date is now tomorrow; the same click again is a no-op
		again = run_night_audit(P, today)
		assert again.get("already_ran") is True, again
		assert frappe.db.count("Night Audit Run",
		                       {"property": P, "business_date": today}) == 1
	finally:
		frappe.db.set_value("Property", P, "business_date", saved)


@check("Today board and reservation drawer agree on what's owed (deposit, no-show refund)")
def t112():
	from kamra import api
	ci, co = "2034-07-10", "2034-07-12"
	g = _guest("Eval Money Agree", "+91 70000 00112")
	res = _res(g, ci, co)
	api.record_advance(res.name, 1500, "Cash")
	assert frappe.db.get_value("Folio", {"reservation": res.name, "folio_type": "Guest"}), \
		"deposit opened no folio"
	snap = api.front_desk_snapshot(property=P, date=ci)
	row = next(r for r in snap["arrivals"] if r.name == res.name)
	money = api.reservation_detail(res.name)["money"]
	total = float(frappe.db.get_value("Reservation", res.name, "amount_after_tax"))
	assert money["source"] == "booking" and abs(money["total"] - total) < 0.01, money
	assert abs(money["paid"] - 1500) < 0.01, money
	assert abs(row["paid_total"] - money["paid"]) < 0.01, (row, money)
	assert abs(row["balance_due"] - money["due"]) < 0.01, (row, money)
	assert abs(money["due"] - (total - 1500)) < 0.01, money

	# a no-show that never opened a folio owes nothing; its advance is a refund
	g2 = _guest("Eval Money NoShow", "+91 70000 00113")
	ns = _res(g2, "2034-07-20", "2034-07-21")
	frappe.db.set_value("Reservation", ns.name, {"status": "No Show", "advance_paid": 800})
	money = api.reservation_detail(ns.name)["money"]
	assert money["source"] == "none" and money["due"] == 0 and money["total"] == 0, money
	assert money.get("refund_due") == 800, money
	assert api._stay_balances([ns.name])[ns.name] == money, "board and drawer rules differ"


def _villa_property(name, code):
	frappe.get_doc({
		"doctype": "Property", "property_name": name, "city": "Testville",
		"gst_mode": "Slab", "gst_slab_threshold": 7500,
		"gst_rate_low": 5, "gst_rate_high": 18,
	}).insert(ignore_permissions=True)
	villa = frappe.get_doc({
		"doctype": "Room Type", "property": name, "room_type_code": code,
		"room_type_name": f"Eval Villa {code}", "base_price": 20000,
		"base_occupancy": 4, "adults_capacity": 6, "children_capacity": 2,
		"room_category": "Villa", "tax_percent": 18,
	}).insert(ignore_permissions=True)
	return villa.name


@check("whole-villa type with its own units checks in to ONE unit via the room picker")
def t113():
	from kamra import api
	VP = "EVAL Villa Units"
	villa = _villa_property(VP, "EVU")
	units = [frappe.get_doc({"doctype": "Room", "property": VP, "room_number": n,
	                         "room_type": villa}).insert(ignore_permissions=True).name
	         for n in ("U1", "U2")]
	today = nowdate()
	res = frappe.get_doc({
		"doctype": "Reservation", "property": VP,
		"guest": _guest("Eval Villa Unit Guest", "+91 70000 00114"),
		"room_type": villa, "check_in_date": today,
		"check_out_date": add_days(today, 1), "adults": 4, "auto_price": 1,
	}).insert(ignore_permissions=True)
	ctx = api.checkin_context(res.name)
	assert ctx["entire_place"] is None, ctx["entire_place"]
	assert {r["name"] for r in ctx["rooms"]} >= set(units), ctx["rooms"]
	# a refused request rolls back in production; mirror that here
	frappe.db.savepoint("eval_t113")
	try:
		api.check_in(res.name)
		raise AssertionError("a villa unit stay checked in with no unit picked")
	except frappe.ValidationError as e:
		assert "Assign a room" in str(e), e
	frappe.db.rollback(save_point="eval_t113")
	api.check_in(res.name, units[0])
	assert frappe.db.get_value("Reservation", res.name, "room") == units[0]
	assert frappe.db.get_value("Room", units[0], "occupancy_status") == "Occupied"
	assert frappe.db.get_value("Room", units[1], "occupancy_status") != "Occupied", \
		"one villa stay took every unit"


@check("villa member rooms: Out of Order room untouched by check-in/out; two villa types refuse")
def t114():
	from kamra import api
	from kamra.folio import post_remaining_nights
	VP = "EVAL Villa OOO"
	villa = _villa_property(VP, "EVO")
	bed = frappe.get_doc({
		"doctype": "Room Type", "property": VP, "room_type_code": "EVOB",
		"room_type_name": "Eval OOO Bedroom", "base_price": 6000,
		"base_occupancy": 2, "adults_capacity": 2, "tax_percent": 5,
	}).insert(ignore_permissions=True).name
	ok, ooo = [frappe.get_doc({"doctype": "Room", "property": VP, "room_number": n,
	                           "room_type": bed}).insert(ignore_permissions=True).name
	           for n in ("O1", "O2")]
	frappe.db.set_value("Room", ooo, {"housekeeping_status": "Out of Order",
	                                  "occupancy_status": "Vacant"})
	today = nowdate()
	res = frappe.get_doc({
		"doctype": "Reservation", "property": VP,
		"guest": _guest("Eval Villa OOO Guest", "+91 70000 00115"),
		"room_type": villa, "check_in_date": today,
		"check_out_date": add_days(today, 1), "adults": 4, "auto_price": 1,
	}).insert(ignore_permissions=True)
	assert api.checkin_context(res.name)["entire_place"] == {"rooms": ["O1"]}
	api.check_in(res.name)
	assert frappe.db.get_value("Room", ok, "occupancy_status") == "Occupied"
	assert tuple(frappe.db.get_value("Room", ooo, ["occupancy_status", "housekeeping_status"])) \
		== ("Vacant", "Out of Order")
	log = frappe.get_all("Agent Action Log", filters={
		"reference_name": res.name, "action_type": "check_in"}, pluck="rationale")
	assert not any("unassigned" in (r or "") for r in log), log

	doc = frappe.get_doc("Reservation", res.name)
	post_remaining_nights(doc)
	folio = frappe.db.get_value("Folio", {"reservation": res.name, "folio_type": "Guest"})
	owed = float(frappe.db.get_value("Folio", folio, "balance") or 0)
	if owed > 0:
		api.add_folio_payment(folio, "Cash", owed)
	api.check_out(res.name)
	assert tuple(frappe.db.get_value("Room", ooo, ["occupancy_status", "housekeeping_status"])) \
		== ("Vacant", "Out of Order"), "check-out flipped an Out of Order room"
	assert not frappe.db.exists("Housekeeping Task", {"room": ooo, "reservation": res.name}), \
		"check-out queued a clean for an Out of Order room"
	assert frappe.db.get_value("Room", ok, "housekeeping_status") == "Dirty"

	# a second villa type: no telling which member rooms are whose - refuse
	_ = frappe.get_doc({
		"doctype": "Room Type", "property": VP, "room_type_code": "EVO2",
		"room_type_name": "Eval Villa EVO2", "base_price": 20000,
		"base_occupancy": 4, "adults_capacity": 6, "room_category": "Villa",
		"tax_percent": 18,
	}).insert(ignore_permissions=True)
	r2 = frappe.get_doc({
		"doctype": "Reservation", "property": VP,
		"guest": _guest("Eval Villa Two Types", "+91 70000 00116"),
		"room_type": villa, "check_in_date": add_days(today, 3),
		"check_out_date": add_days(today, 4), "adults": 4, "auto_price": 1,
	}).insert(ignore_permissions=True)
	try:
		api.checkin_context(r2.name)
		raise AssertionError("member-room fallback used with two villa types")
	except frappe.ValidationError as e:
		assert "other villa types" in str(e), e


@check("public /book leaves a logged-in staff session intact")
def t115():
	from kamra import public_api
	real = frappe.local.session
	frappe.local.session = frappe._dict(
		user="Administrator", sid="eval-book-sid",
		data=frappe._dict(csrf_token="eval-csrf", session_expiry="06:00:00"))
	try:
		out = public_api.book(
			property=P, room_type=RT, check_in_date="2031-04-10",
			check_out_date="2031-04-11", guest_name="Web Staff Session",
			phone="+919812300115", adults=1, children=0,
		)
		s = frappe.local.session
		assert (s.user, s.sid) == ("Administrator", "eval-book-sid"), s
		assert s.data.get("csrf_token") == "eval-csrf", s.data
	finally:
		frappe.local.session = real
	assert frappe.db.get_value("Reservation", out["reservation"], "source") == "Website"


@check("night audit for D flags D's unarrived arrivals and dates their fee D")
def t120():
	from kamra.folio import run_night_audit
	today = nowdate()
	saved = frappe.db.get_value("Property", P, ["business_date", "no_show_charge"],
	                            as_dict=True)
	frappe.db.set_value("Property", P, {"business_date": today,
	                                    "no_show_charge": "First Night"})
	try:
		frappe.db.delete("Night Audit Run", {"property": P, "business_date": today})
		g = _guest("Eval Same Day NoShow", "+91 70000 00120")
		due = _res(g, today, add_days(today, 1))
		g2 = _guest("Eval Tomorrow Arrival", "+91 70000 00121")
		later = _res(g2, add_days(today, 1), add_days(today, 2))
		run_night_audit(P)
		assert frappe.db.get_value("Reservation", due.name, "status") == "No Show"
		assert frappe.db.get_value("Reservation", later.name, "status") == "Confirmed"
		fee = frappe.get_all("Folio Charge", filters={
			"reservation": due.name, "description": ("like", "No-show%")},
			pluck="posting_date")
		assert [str(x) for x in fee] == [str(today)], fee
	finally:
		frappe.db.set_value("Property", P, {
			"business_date": saved.business_date,
			"no_show_charge": saved.no_show_charge})


@check("room nights under a rate plan add up to the quote's room total")
def t121():
	from kamra.folio import _nightly_room_rate
	from kamra.pricing import quote
	plans = [frappe.get_doc({
		"doctype": "Rate Plan", "property": P, "rate_plan_name": name,
		"code": code, "modifier_type": kind, "modifier_value": value,
	}).insert(ignore_permissions=True).name
		for name, code, kind, value in (
			("Eval NR -15%", "EVNR15", "Percent", -15),
			("Eval Flat -500", "EVFLAT500", "Amount", -500))]
	ci, co = "2031-11-03", "2031-11-06"
	g = _guest("Eval Rate Plan Stay", "+91 70000 00122")
	for plan in plans:
		res = frappe.get_doc({
			"doctype": "Reservation", "property": P, "guest": g,
			"room_type": RT, "check_in_date": ci, "check_out_date": co,
			"adults": 2, "auto_price": 1, "rate_plan": plan,
		}).insert(ignore_permissions=True)
		q = quote(P, RT, ci, co, 2, 0, rate_plan=plan)
		nights = sum(_nightly_room_rate(res, add_days(ci, i)) for i in range(3))
		assert abs(nights - q["room_total"]) < 0.01, (plan, nights, q["room_total"])
		plain = quote(P, RT, ci, co, 2, 0)["room_total"]
		assert nights < plain, (plan, nights, plain)


@check("setup wizard rooms get a floor (derived, or the one given)")
def t140():
	from kamra import api
	assert api.default_floor("101") == "1"
	assert api.default_floor("1205") == "12"
	assert api.default_floor("007") == "Ground"
	assert api.default_floor("Room 3") == "Ground"
	out = api.setup_property({
		"property": {"property_name": "EVAL Wizard Floors", "city": "Testville"},
		"room_types": [{"code": "WZ", "name": "Wizard Room", "base_price": 3000}],
		"rooms": [
			{"room_type_code": "WZ", "numbers": ["101", "214", "Cottage"]},
			{"room_type_code": "WZ", "numbers": ["P1"], "floor": "Penthouse"},
		],
	})
	floors = dict(frappe.get_all(
		"Room", filters={"property": out["property"]},
		fields=["room_number", "floor"], as_list=True))
	assert floors == {"101": "1", "214": "2", "Cottage": "Ground",
	                  "P1": "Penthouse"}, floors


@check("property kind change in Settings applies the rental preset, keeps explicit values")
def t141():
	from kamra.property_presets import STR_MODULES
	from kamra.settings import save_settings
	a = frappe.get_doc({"doctype": "Property", "property_name": "EVAL Kind Switch A",
	                    "city": "Testville"}).insert(ignore_permissions=True)
	save_settings(a.name, "general", {"property_kind": "Short Term Rental"})
	mods = frappe.db.get_value("Property", a.name, "enabled_modules")
	assert mods == ",".join(STR_MODULES), mods
	assert "booking-engine" in mods.split(","), mods
	# and back: the untouched STR list was the preset, so hotel = all again
	save_settings(a.name, "general", {"property_kind": "Hotel"})
	assert not frappe.db.get_value("Property", a.name, "enabled_modules")

	# explicit admin choices survive a kind switch
	b = frappe.get_doc({"doctype": "Property", "property_name": "EVAL Kind Switch B",
	                    "city": "Testville", "enabled_modules": "front-desk,admin,fnb",
	                    "overbooking_pct": 7, "hold_minutes": 45,
	                    "booking_mode": "Request to Book"}).insert(ignore_permissions=True)
	save_settings(b.name, "general", {"property_kind": "Short Term Rental"})
	row = frappe.db.get_value("Property", b.name, [
		"property_kind", "enabled_modules", "overbooking_pct", "hold_minutes",
		"booking_mode"], as_dict=True)
	assert row.property_kind == "Short Term Rental", row
	assert row.enabled_modules == "front-desk,admin,fnb", row
	assert (row.overbooking_pct, row.hold_minutes, row.booking_mode) == (
		7, 45, "Request to Book"), row


@check("demo heal fills doctype defaults a defaults-skipped seed left blank")
def t142():
	from kamra.scripts.seed_demo import heal_seed_defaults
	was = frappe.flags.in_import
	frappe.flags.in_import = True  # what the old demo reset left on
	try:
		prop = frappe.get_doc({"doctype": "Property", "property_name": "EVAL Blank Seed",
		                       "city": "Testville"}).insert(ignore_permissions=True)
		rt = frappe.get_doc({"doctype": "Room Type", "property": prop.name,
		                     "room_type_code": "BLK", "room_type_name": "Blank",
		                     "base_price": 3000}).insert(ignore_permissions=True)
		room = frappe.get_doc({"doctype": "Room", "property": prop.name,
		                       "room_number": "B1", "room_type": rt.name,
		                       "floor": "1"}).insert(ignore_permissions=True)
	finally:
		frappe.flags.in_import = was
	assert not frappe.db.get_value("Room", room.name, "housekeeping_status")
	assert heal_seed_defaults((prop.name, P)) > 0
	assert frappe.db.get_value("Room", room.name, "housekeeping_status") == "Clean"
	row = frappe.db.get_value("Property", prop.name, [
		"property_kind", "booking_engine_enabled", "gst_rate_low",
		"gst_rate_high", "hold_minutes"], as_dict=True)
	assert row.property_kind == "Hotel" and row.booking_engine_enabled == 1, row
	assert (row.gst_rate_low, row.gst_rate_high, row.hold_minutes) == (5, 18, 120), row
	# a property that got its defaults is not a heal target
	assert heal_seed_defaults((P,)) == 0


@check("demo seed: defaults applied, past-dated stays seeded, rentals are STR, tickets name real rooms")
def t143():
	from kamra.scripts import seed_demo
	if frappe.db.exists("Property", seed_demo.PROPERTY):
		# a dev site that already has the demo: the idempotent path must
		# still leave the villa / homestay as bookable rentals
		seed_demo.seed_generic_properties()
	else:
		before = frappe.db.get_default("kamra_demo_mode")
		was = frappe.flags.in_import
		frappe.flags.in_import = True  # reset_demo sets it for its wipe
		try:
			seed_demo.execute()
		finally:
			frappe.flags.in_import = was
			frappe.db.set_default("kamra_demo_mode", before or "")
		assert frappe.flags.in_import == was
		dp = seed_demo.PROPERTY
		assert not frappe.db.sql(
			"select name from tabRoom where property=%s and ifnull(housekeeping_status,'')=''", dp)
		pr = frappe.db.get_value("Property", dp, [
			"booking_engine_enabled", "gst_rate_low", "checkin_time"], as_dict=True)
		assert pr.booking_engine_enabled == 1 and pr.gst_rate_low == 5 and pr.checkin_time, pr
		past = frappe.db.count("Reservation", {
			"property": dp, "status": "Checked In", "check_in_date": ("<", nowdate())})
		assert past >= 5, past
		for subject, room in frappe.get_all(
				"Service Ticket", filters={"property": dp, "room": ("is", "set")},
				fields=["subject", "room"], as_list=True):
			num = frappe.db.get_value("Room", room, "room_number")
			assert num, (subject, room)
			digits = [w for w in subject.replace(",", " ").split() if w.isdigit() and len(w) == 3]
			assert not digits or digits == [num], (subject, num)
	for name in seed_demo.RENTALS:
		row = frappe.db.get_value("Property", name, [
			"property_kind", "booking_engine_enabled", "enabled_modules"], as_dict=True)
		assert row and row.property_kind == "Short Term Rental", (name, row)
		assert row.booking_engine_enabled == 1, (name, row)
		assert "booking-engine" in (row.enabled_modules or "booking-engine"), (name, row)


@check("booking page: advance due now + balance at hotel come from the server, on search and on book")
def t150():
	from kamra import public_api
	frappe.db.set_value("Property", P, {"booking_payment_mode": "Advance percent",
	                                    "advance_percent": 25})
	frappe.clear_document_cache("Property", P)
	try:
		rows = public_api.search_stay(P, "2031-05-10", "2031-05-11", 1, 0)
		q = next(r["quote"] for r in rows if r["room_type"] == RT and r["quote"])
		total = float(q["amount_after_tax"])
		assert abs(q["advance_due"] - round(total * 0.25, 2)) < 0.01, q
		assert abs(q["balance_at_hotel"] - (total - q["advance_due"])) < 0.01, q
		out = public_api.book(
			property=P, room_type=RT, check_in_date="2031-05-10",
			check_out_date="2031-05-11", guest_name="Web Advance Guest",
			phone="+919812300150", adults=1, children=0,
		)
		total = float(out["amount_after_tax"])
		assert out["advance_due"] > 0 and not out["pay_at_hotel"], out
		assert abs(out["advance_due"] + out["balance_at_hotel"] - total) < 0.01, out
		assert "₹" not in out["payment_policy"] or public_api._public_locale(P)[
			"currency_symbol"] == "₹", out["payment_policy"]
	finally:
		frappe.db.set_value("Property", P, "booking_payment_mode", "Pay at hotel")
		frappe.clear_document_cache("Property", P)


@check("blacklist: Hotel Admin only, reason required, logged; guest_alert flags the profile by pick or phone")
def t151():
	from kamra import api
	g = _guest("Eval Blacklist Guest", "+91 70000 00151")
	me = frappe.session.user
	try:
		frappe.set_user("frontdesk@kamra.local")  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow
		try:
			api.set_guest_blacklist(g, 1, "damaged room")
			raise AssertionError("Front Desk blacklisted a guest")
		except frappe.PermissionError:
			pass
	finally:
		frappe.set_user(me)  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow
	try:
		api.set_guest_blacklist(g, 1, "  ")
		raise AssertionError("blacklisted without a reason")
	except frappe.ValidationError:
		pass
	api.set_guest_blacklist(g, 1, "damaged room")
	assert frappe.db.get_value("Guest", g, ["blacklisted", "blacklist_reason"]) == (1, "damaged room")
	assert frappe.db.exists("Agent Action Log", {
		"reference_doctype": "Guest", "reference_name": g,
		"action_type": "guest_blacklisted"})
	by_pick = api.guest_alert(guest=g)
	by_phone = api.guest_alert(phone="+91 70000 00151")
	assert by_pick["blacklisted"] == 1 and by_pick["blacklist_reason"] == "damaged room", by_pick
	assert by_phone["guest"] == g and by_phone["blacklisted"] == 1, by_phone
	assert api.guest_alert(phone="+91 70000 09999")["blacklisted"] == 0
	api.set_guest_blacklist(g, 0, "paid for damage")
	assert frappe.db.get_value("Guest", g, "blacklisted") == 0
	assert frappe.db.exists("Agent Action Log", {
		"reference_name": g, "action_type": "guest_blacklist_removed"})


@check("blacklisted guest: booking refused; only a Hotel Admin with a reason may override (logged)")
def t152():
	from kamra import api
	g = _guest("Eval Blacklist Book", "+91 70000 00152")
	frappe.db.set_value("Guest", g, {"blacklisted": 1, "blacklist_reason": "fraud"})
	kw = dict(property=P, room_type=RT, check_in_date="2031-06-01",
	          check_out_date="2031-06-02", guest_name="Eval Blacklist Book", guest=g)
	try:
		api.create_booking(**kw)
		raise AssertionError("blacklisted guest booked without override")
	except frappe.ValidationError as e:
		assert "blacklisted" in str(e).lower(), e
	me = frappe.session.user
	try:
		frappe.set_user("frontdesk@kamra.local")  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow
		try:
			api.create_booking(**kw, blacklist_override_reason="regular, settled")
			raise AssertionError("Front Desk overrode a blacklist")
		except frappe.PermissionError:
			pass
	finally:
		frappe.set_user(me)  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow
		frappe.flags.kamra_blacklist_override = None
	try:
		out = api.create_booking(**kw, blacklist_override_reason="GM approved")
	finally:
		frappe.flags.kamra_blacklist_override = None
	assert frappe.db.get_value("Reservation", out["reservation"], "guest") == g
	assert frappe.db.exists("Agent Action Log", {
		"reference_name": g, "action_type": "blacklist_override"})


@check("reservation_detail returns the meal plan's label, not its ID")
def t153():
	from kamra import api
	frappe.db.delete("Meal Plan", {"property": P, "code": "EP"})  # rolled back after the run
	mp = frappe.get_doc({"doctype": "Meal Plan", "property": P, "code": "EP",
	                     "label": "Eval Breakfast 153", "price_per_adult": 0,
	                     }).insert(ignore_permissions=True).name
	g = _guest("Eval Meal Plan Guest", "+91 70000 00153")
	res = frappe.get_doc({
		"doctype": "Reservation", "property": P, "guest": g, "room_type": RT,
		"check_in_date": "2031-07-01", "check_out_date": "2031-07-02",
		"adults": 1, "meal_plan": mp,
	}).insert(ignore_permissions=True)
	d = api.reservation_detail(res.name)
	assert d["meal_plan"] == mp and d["meal_plan_name"] == "Eval Breakfast 153", d["meal_plan_name"]



# --- security deposits, day use (t170-t179) -------------------------------

def _dep_room(number):
	name = frappe.db.exists("Room", {"property": P, "room_number": number})
	if name:
		frappe.db.set_value("Room", name, "room_type", RT)
		return name
	return frappe.get_doc({
		"doctype": "Room", "property": P, "room_number": number,
		"room_type": RT,
	}).insert(ignore_permissions=True).name


def _dep_stay(number, phone):
	from frappe.utils import add_days
	g = _guest(f"Eval Deposit {number}", phone)
	res = _res(g, nowdate(), add_days(nowdate(), 1), _dep_room(number))
	res.status = "Checked In"
	res.save(ignore_permissions=True)
	folio = frappe.db.get_value(
		"Folio", {"reservation": res.name, "folio_type": "Guest"})
	if not folio:
		from kamra.folio import open_folio
		folio = open_folio(res)
	# the stay's own bill is posted and paid, so the folio's credit is the
	# deposit (check-out would post the night otherwise)
	from kamra.folio import post_remaining_nights
	post_remaining_nights(res)
	owed = float(frappe.db.get_value("Folio", folio, "balance") or 0)
	if owed > 0:
		from kamra import api
		api.add_folio_payment(folio, "Cash", owed)
	return res, folio


def _ledger(folio, ledger):
	rows = frappe.get_all("Folio Ledger Entry",
	                      filters={"folio": folio, "ledger": ledger},
	                      fields=["debit", "credit"])
	return (sum(float(r.debit or 0) for r in rows),
	        sum(float(r.credit or 0) for r in rows))


@check("security deposit: collect is a folio payment held in the Deposit ledger, logged")
def t170():
	from kamra import api
	res, folio = _dep_stay("E170", "+91 70000 00170")
	g0 = _ledger(folio, "Guest")
	st = api.collect_security_deposit(res.name, 10000, "Cash")
	assert st["status"] == "Held" and st["held"] == 10000, st
	fd = frappe.get_doc("Folio", folio)
	assert ("Security Deposit", 10000.0) in {
		(p.payment_kind, float(p.amount)) for p in fd.payments}
	# a liability, not revenue: credited to Deposit, Guest ledger untouched
	assert _ledger(folio, "Deposit") == (0, 10000.0), _ledger(folio, "Deposit")
	assert _ledger(folio, "Guest") == g0, (_ledger(folio, "Guest"), g0)
	assert frappe.db.exists("Agent Action Log",
	                        {"action_type": "collect_security_deposit"})
	for bad in (0, -5):
		try:
			api.collect_security_deposit(res.name, bad, "Cash")
			raise AssertionError("non-positive deposit accepted")
		except frappe.ValidationError:
			pass
	try:
		api.collect_security_deposit(res.name, 100, "Bitcoin")
		raise AssertionError("unknown payment mode accepted")
	except frappe.ValidationError:
		pass


@check("security deposit: withhold posts a damage charge and moves Deposit -> Guest ledger")
def t171():
	from kamra import api
	res, folio = _dep_stay("E171", "+91 70000 00171")
	g0 = _ledger(folio, "Guest")
	api.collect_security_deposit(res.name, 10000, "Cash")
	for amt, reason in ((3000, ""), (20000, "broken lamp")):
		try:
			api.withhold_security_deposit(res.name, amt, reason)
			raise AssertionError(f"withhold {amt}/{reason!r} accepted")
		except frappe.ValidationError:
			pass
	st = api.withhold_security_deposit(res.name, 3000, "Broken lamp")
	assert st["withheld"] == 3000 and st["held"] == 7000, st
	assert st["status"] == "Withheld", st
	fd = frappe.get_doc("Folio", folio)
	dmg = [c for c in fd.charges if "withheld" in (c.description or "")]
	assert len(dmg) == 1 and float(dmg[0].amount) == 3000, dmg
	# no second payment row: the deposit already on the folio pays it
	assert sum(1 for p in fd.payments
	           if p.payment_kind == "Security Deposit") == 1
	assert abs(float(fd.balance) - (-7000)) < 0.01, fd.balance
	assert _ledger(folio, "Deposit") == (3000.0, 10000.0), _ledger(folio, "Deposit")
	# Guest: damage charge debit 3000, deposit applied credit 3000
	g1 = _ledger(folio, "Guest")
	assert (g1[0] - g0[0], g1[1] - g0[1]) == (3000.0, 3000.0), (g1, g0)
	assert frappe.db.exists("Agent Action Log",
	                        {"action_type": "withhold_security_deposit"})


@check("security deposit: refund the rest via the refund path, Deposit ledger nets to zero, check-out clears")
def t172():
	from kamra import api
	res, folio = _dep_stay("E172", "+91 70000 00172")
	g0 = _ledger(folio, "Guest")
	api.collect_security_deposit(res.name, 10000, "UPI")
	api.withhold_security_deposit(res.name, 2500, "Stained sofa")
	# check-out refuses while the guest is still owed the deposit
	try:
		api.check_out(res.name)
		raise AssertionError("check-out with a held deposit")
	except frappe.ValidationError:
		pass
	try:
		api.refund_security_deposit(res.name, 9000)
		raise AssertionError("refund above the held balance")
	except frappe.ValidationError:
		pass
	st = api.refund_security_deposit(res.name)
	assert st["held"] == 0 and st["refunded"] == 7500, st
	assert st["status"] == "Refunded", st
	fd = frappe.get_doc("Folio", folio)
	refunds = [p for p in fd.payments if p.payment_kind == "Refund"]
	assert len(refunds) == 1 and float(refunds[0].amount) == -7500, refunds
	assert refunds[0].mode == "UPI", refunds[0].mode  # back the way it came
	assert abs(float(fd.balance)) < 0.01, fd.balance
	d, c = _ledger(folio, "Deposit")
	assert abs(d - c) < 0.01, (d, c)  # liability fully released
	g1 = _ledger(folio, "Guest")
	assert (g1[0] - g0[0], g1[1] - g0[1]) == (2500.0, 2500.0), (g1, g0)
	kinds = [h["kind"] for h in st["history"]]
	assert kinds.count("Collected") == 1 and "Withheld" in kinds \
		and "Refunded" in kinds, kinds
	api.check_out(res.name)
	assert frappe.db.get_value("Reservation", res.name, "status") == "Checked Out"


@check("security deposit: refund can't take back what the bill owes; a deposit the bill used is applied at check-out")
def t173():
	from kamra import api
	res, folio = _dep_stay("E173", "+91 70000 00173")
	api.collect_security_deposit(res.name, 5000, "Cash")
	api.add_folio_charge(folio, "Misc", "Extra bed", 4000)
	try:
		api.refund_security_deposit(res.name, 5000)
		raise AssertionError("refunded a deposit the bill is using")
	except frappe.ValidationError:
		pass
	# the last 1,000 handed back through the folio's own refund form can't
	# then be refunded again from the deposit panel
	api.refund_folio_payment(folio, 1000, "Cash", "deposit change returned")
	try:
		api.refund_security_deposit(res.name, 1000)
		raise AssertionError("deposit refunded twice")
	except frappe.ValidationError:
		pass
	# the settled bill used the deposit: check-out records it as applied
	api.check_out(res.name)
	dep = frappe.get_doc("Security Deposit", {"reservation": res.name})
	assert float(dep.balance) == 0 and dep.status == "Withheld", dep.as_dict()
	assert "check-out" in (dep.reason or ""), dep.reason
	d, c = _ledger(folio, "Deposit")
	assert abs(d - c) < 0.01, (d, c)
	assert frappe.db.exists("Agent Action Log",
	                        {"action_type": "apply_security_deposit"})


@check("security deposit: waive needs a reason, is refused once paid; roles gate withhold/refund")
def t174():
	from kamra import api
	from kamra.deposit import deposit_satisfied
	frappe.db.set_value("Property", P, "security_deposit_amount", 8000)
	try:
		res, folio = _dep_stay("E174", "+91 70000 00174")
		st = api.security_deposit(res.name)
		assert st["status"] == "Required" and st["due"] == 8000, st
		assert not deposit_satisfied(res.name)
		try:
			api.waive_security_deposit(res.name, "  ")
			raise AssertionError("waived without a reason")
		except frappe.ValidationError:
			pass
		st = api.waive_security_deposit(res.name, "Repeat guest, owner approved")
		assert st["status"] == "Waived" and st["due"] == 0, st
		assert deposit_satisfied(res.name)
		try:
			api.collect_security_deposit(res.name, 8000, "Cash")
			raise AssertionError("collected on a waived deposit")
		except frappe.ValidationError:
			pass

		res2, _f = _dep_stay("E175", "+91 70000 00175")
		api.collect_security_deposit(res2.name, 8000, "Cash")
		try:
			api.waive_security_deposit(res2.name, "changed mind")
			raise AssertionError("waived a deposit already paid")
		except frappe.ValidationError:
			pass
		frappe.set_user("hk@kamra.local")  # nosemgrep: frappe-setuser -- controlled user context switch for an RBAC check
		try:
			for fn, args in ((api.withhold_security_deposit, (res2.name, 100, "x")),
			                 (api.refund_security_deposit, (res2.name,))):
				try:
					fn(*args)
					raise AssertionError(f"housekeeping ran {fn.__name__}")
				except frappe.PermissionError:
					pass
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- controlled user context switch for an RBAC check
	finally:
		frappe.db.set_value("Property", P, "security_deposit_amount", 0)


@check("security deposit: the folio's own Security Deposit payment keeps the record in step")
def t176():
	from kamra import api
	res, folio = _dep_stay("E176", "+91 70000 00176")
	api.add_folio_payment(folio, "Card", 3000, kind="Security Deposit")
	st = api.reservation_detail(res.name)["security_deposit"]
	assert st["held"] == 3000 and st["can_refund"] and st["blocks_checkout"], st


@check("day use: desk booking with a time slot, priced by the quote, refuses a backwards slot")
def t177():
	from kamra import api
	from kamra.pricing import quote
	d = "2035-03-14"
	q = quote(P, RT, d, d, 2, 0)
	assert q["day_use"] and q["nights"] == 0 and q["amount_after_tax"] > 0, q
	out = api.create_booking(P, RT, d, d, "Eval Day Use", phone="+91 70000 00177",
	                         check_in_time="11:00", check_out_time="16:30")
	r = frappe.get_doc("Reservation", out["reservation"])
	assert r.is_day_use == 1 and str(r.check_out_date) == d, r.check_out_date
	assert str(r.planned_check_in_time).startswith("11:00"), r.planned_check_in_time
	assert str(r.planned_check_out_time).startswith("16:30"), r.planned_check_out_time
	assert abs(float(r.amount_after_tax) - q["amount_after_tax"]) < 0.01, \
		(r.amount_after_tax, q["amount_after_tax"])
	for a, b in (("16:00", "11:00"), ("25:00", "26:00")):
		try:
			api.create_booking(P, RT, d, d, "Eval Day Use 2",
			                   check_in_time=a, check_out_time=b)
			raise AssertionError(f"slot {a}-{b} accepted")
		except frappe.ValidationError:
			pass


@check("day use: hourly tape places the slot, the room board flags the same-day turn")
def t178():
	from kamra import api
	room = _dep_room("E178")
	g = _guest("Eval Day Use HK", "+91 70000 00178")
	out = api.create_booking(P, RT, nowdate(), nowdate(), "Eval Day Use HK",
	                         guest=g, room=room, assign_room=0,
	                         check_in_time="09:00", check_out_time="13:00")
	tape = api.tape_chart_hourly(P, nowdate())
	row = next(x for x in tape["rooms"] if x.name == room)
	b = next(x for x in row["bookings"] if x.name == out["reservation"])
	assert b.from_hour == "09:00" and b.to_hour == "13:00" and b.overnight == 0, b
	res = frappe.get_doc("Reservation", out["reservation"])
	res.status = "Checked In"
	res.save(ignore_permissions=True)
	board = api.room_board(P)
	tile = next(x for x in board["rooms"] if x.name == room)
	assert tile["day_use"] and tile["due_out"] and tile["etd"] == "13:00", tile


@check("Security deposit MCP tools are exposed; withhold stays desk-only")
def t179():
	from kamra.mcp_tools import BY_NAME
	for n in ("security_deposit_status", "collect_security_deposit",
	          "waive_security_deposit"):
		assert n in BY_NAME, n
	assert "withhold_security_deposit" not in BY_NAME  # humans, with the PIN


# ── t160-t169: request-to-book inbox, symmetric villa/room availability,
#    group-block holds with auto-release ─────────────────────────────────


def _inv_property(name, code, rooms=2, with_villa=True, mode=None):
	"""A fresh property: a bedroom type with `rooms` rooms and (with_villa)
	a whole-villa type sold over those rooms - the hybrid estate."""
	frappe.get_doc({
		"doctype": "Property", "property_name": name, "city": "Testville",
		"gst_mode": "Slab", "gst_slab_threshold": 7500,
		"gst_rate_low": 5, "gst_rate_high": 18,
		**({"booking_mode": mode} if mode else {}),
	}).insert(ignore_permissions=True)
	bed = frappe.get_doc({
		"doctype": "Room Type", "property": name, "room_type_code": code,
		"room_type_name": f"Eval Bed {code}", "base_price": 5000,
		"base_occupancy": 2, "adults_capacity": 2, "tax_percent": 5,
	}).insert(ignore_permissions=True).name
	rooms_ = [frappe.get_doc({"doctype": "Room", "property": name,
	                          "room_number": f"{code}{i}", "room_type": bed,
	                          "housekeeping_status": "Clean"}
	                         ).insert(ignore_permissions=True).name
	          for i in range(1, rooms + 1)]
	villa = None
	if with_villa:
		villa = frappe.get_doc({
			"doctype": "Room Type", "property": name,
			"room_type_code": f"{code}V", "room_type_name": f"Eval Villa {code}",
			"base_price": 20000, "base_occupancy": 4, "adults_capacity": 6,
			"room_category": "Villa", "tax_percent": 18,
		}).insert(ignore_permissions=True).name
	return bed, villa, rooms_


def _stay(prop, rt, ci, co, room=None, status=None, group=None, name="Eval Inv"):
	doc = frappe.get_doc({
		"doctype": "Reservation", "property": prop, "room_type": rt,
		"guest": _guest(name, "+91 7%09d" % (int(frappe.generate_hash(length=8), 16) % 10**9)),
		"room": room, "check_in_date": ci, "check_out_date": co,
		"adults": 2, "auto_price": 1, "group_booking": group,
	})
	if status:
		doc.status = status
	return doc.insert(ignore_permissions=True)


def _left(prop, rt, ci, co):
	from kamra import public_api
	return next(r["rooms_left"] for r in public_api.search_stay(prop, ci, co)
	            if r["room_type"] == rt)


@check("villa lockout: a booked whole villa takes its member rooms off sale everywhere")
def t160():
	from kamra import api
	from kamra import channel_manager as cm
	VP = "EVAL Inv Villa A"
	bed, villa, _r = _inv_property(VP, "IVA", rooms=2)
	ci, co = add_days(nowdate(), 20), add_days(nowdate(), 22)
	assert (_left(VP, bed, ci, co), _left(VP, villa, ci, co)) == (2, 1), \
		(_left(VP, bed, ci, co), _left(VP, villa, ci, co))
	_stay(VP, villa, ci, co)
	assert api._available_rooms_raw(VP, bed, ci, co) == [], "member rooms still on desk sale"
	assert _left(VP, bed, ci, co) == 0, "member rooms still on the booking engine"
	assert cm._sellable(VP, bed, ci, co) == 0
	cal = api.availability_calendar(VP, ci, 3)
	cells = {r["room_type"]: [c["available"] for c in r["cells"]] for r in cal["room_types"]}
	assert cells[bed] == [0, 0, 2], cells
	# the night after check-out is free again
	assert _left(VP, bed, co, add_days(co, 1)) == 2


@check("villa lockout: any booked member room takes the whole villa off sale; ARI pushes the reduced counts")
def t161():
	from kamra import api
	from kamra import channel_manager as cm
	VP = "EVAL Inv Villa B"
	bed, villa, rooms = _inv_property(VP, "IVB", rooms=2)
	conn = frappe.get_doc({"doctype": "Channel Manager Connection", "property": VP,
	                       "provider": "AioSell", "active": 1,
	                       "external_property_id": "eval-ivb"}).insert(ignore_permissions=True)
	for rt, ext in ((bed, "bed"), (villa, "villa")):
		frappe.get_doc({"doctype": "Channel Room Mapping", "connection": conn.name,
		                "room_type": rt, "external_room_id": ext,
		                "external_rate_id": ext + "-r"}).insert(ignore_permissions=True)
	today = nowdate()
	# an OTA-style stay with no room number yet still locks the villa out
	_stay(VP, bed, add_days(today, 1), add_days(today, 2))
	assert api._available_rooms_raw(VP, villa, add_days(today, 1), add_days(today, 2)) == []
	assert _left(VP, villa, add_days(today, 1), add_days(today, 2)) == 0
	assert _left(VP, villa, add_days(today, 2), add_days(today, 3)) == 1
	snap = {r["room_type"]: [d["available"] for d in r["days"]]
	        for r in cm.ari_snapshot(VP, conn.name, days=4)}
	assert snap[villa] == [1, 0, 1, 1], snap
	assert snap[bed] == [2, 1, 2, 2], snap
	# and the other way: a villa night zeroes both bedrooms on the push
	_stay(VP, villa, add_days(today, 3), add_days(today, 4))
	snap = {r["room_type"]: [d["available"] for d in r["days"]]
	        for r in cm.ari_snapshot(VP, conn.name, days=4)}
	assert snap[bed] == [2, 1, 2, 0], snap
	assert snap[villa] == [1, 0, 1, 0], snap


@check("request to book: a Requested stay holds no room; the inbox lists it; accept assigns a room")
def t162():
	from kamra import booking_requests as br
	from kamra import public_api
	RP = "EVAL Inv Requests"
	bed, _v, rooms = _inv_property(RP, "IRQ", rooms=1, with_villa=False, mode="Request to Book")
	ci, co = add_days(nowdate(), 30), add_days(nowdate(), 32)
	out = public_api.book(property=RP, room_type=bed, check_in_date=ci,
	                      check_out_date=co, guest_name="Request Guest",
	                      phone="+919812300160", adults=2, children=0)
	name = out["reservation"]
	assert frappe.db.get_value("Reservation", name, "status") == "Requested"
	assert not frappe.db.get_value("Reservation", name, "room")
	# keeps today's behaviour: the request holds nothing until accepted
	assert _left(RP, bed, ci, co) == 1, "a Requested stay took inventory"
	inbox = br.booking_requests(RP)
	assert inbox["holds_inventory"] is False and inbox["count"] == 1, inbox
	row = inbox["requests"][0]
	assert row["name"] == name and row["can_accept"] and row["rooms_free"] == 1, row
	res = br.accept_booking_request(name)
	assert res["status"] == "Confirmed" and res["room"] == rooms[0], res
	assert _left(RP, bed, ci, co) == 0
	assert br.booking_requests(RP)["count"] == 0
	assert frappe.db.exists("Agent Action Log", {
		"reference_name": name, "action_type": "booking_request_accepted"})


@check("request to book: accept refuses clearly when the inventory is gone, or the villa lockout applies")
def t163():
	from kamra import booking_requests as br
	from kamra.kamra.doctype.reservation.reservation import InventoryRefused
	RP = "EVAL Inv Requests B"
	bed, villa, rooms = _inv_property(RP, "IRB", rooms=1)
	ci, co = add_days(nowdate(), 40), add_days(nowdate(), 41)
	req = _stay(RP, bed, ci, co, status="Requested", name="Late Request")
	_stay(RP, bed, ci, co, room=rooms[0])  # the last room sells meanwhile
	row = br.booking_requests(RP)["requests"][0]
	assert not row["can_accept"] and "free" in row["blocker"], row
	frappe.db.savepoint("eval_t163")
	try:
		br.accept_booking_request(req.name)
		raise AssertionError("accepted with no inventory")
	except InventoryRefused as e:
		assert "no Eval Bed IRB room is free" in str(e), e
	frappe.db.rollback(save_point="eval_t163")
	assert frappe.db.get_value("Reservation", req.name, "status") == "Requested"
	# a whole-villa request while a member room is booked: the lockout
	vreq = _stay(RP, villa, ci, co, status="Requested", name="Villa Request")
	frappe.db.savepoint("eval_t163b")
	try:
		br.accept_booking_request(vreq.name)
		raise AssertionError("villa accepted over a booked member room")
	except InventoryRefused as e:
		assert "villa and its rooms" in str(e), e
	frappe.db.rollback(save_point="eval_t163b")


@check("request to book: decline needs a reason, cancels with no fee, logs, and is role-gated")
def t164():
	from kamra import booking_requests as br
	RP = "EVAL Inv Requests C"
	bed, _v, _r = _inv_property(RP, "IRC", rooms=1, with_villa=False)
	ci, co = add_days(nowdate(), 50), add_days(nowdate(), 52)
	req = _stay(RP, bed, ci, co, status="Requested", name="Declined Guest")
	try:
		br.decline_booking_request(req.name, "  ")
		raise AssertionError("declined without a reason")
	except frappe.ValidationError as e:
		assert "reason" in str(e).lower(), e
	frappe.set_user("hk@kamra.local")  # nosemgrep: frappe-setuser -- controlled user context switch for an RBAC check
	try:
		br.decline_booking_request(req.name, "Closed for a private event")
		raise AssertionError("housekeeping declined a booking request")
	except frappe.PermissionError:
		pass
	finally:
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- controlled user context switch for an RBAC check
	out = br.decline_booking_request(req.name, "Closed for a private event")
	assert out["status"] == "Cancelled" and out["fee"] == 0, out
	assert out["cancellation_number"], out
	doc = frappe.get_doc("Reservation", req.name)
	assert float(doc.cancellation_fee or 0) == 0 and "private event" in doc.cancellation_note
	assert not frappe.db.exists("Folio", {"reservation": req.name}), "decline posted a fee"
	assert frappe.db.exists("Agent Action Log", {
		"reference_name": req.name, "action_type": "booking_request_declined"})
	try:
		br.accept_booking_request(req.name)
		raise AssertionError("a declined request was accepted")
	except frappe.ValidationError as e:
		assert "not a pending request" in str(e), e
	assert _left(RP, bed, ci, co) == 1


@check("group block: unpicked rooms are held off public/OTA sale; pickups are not double-counted")
def t165():
	from kamra import api
	from kamra import channel_manager as cm
	from kamra.kamra.doctype.reservation.reservation import InventoryRefused
	GP = "EVAL Inv Groups"
	bed, _v, _r = _inv_property(GP, "IGB", rooms=4, with_villa=False)
	ci, co = add_days(nowdate(), 60), add_days(nowdate(), 62)
	gb = api.create_group_block(GP, "Eval Wedding", ci, co,
	                            [{"room_type": bed, "rooms_blocked": 3}])
	name = gb["group_booking"] if isinstance(gb, dict) else gb
	assert _left(GP, bed, ci, co) == 4, "an Open (proposal) block held rooms"
	api.save_group_blocks(name, [{"room_type": bed, "rooms_blocked": 3}],
	                      status="Confirmed")
	assert _left(GP, bed, ci, co) == 1, _left(GP, bed, ci, co)
	assert cm._sellable(GP, bed, ci, co) == 1
	api.pickup_group_room(name, bed, "Eval Bride")
	# the pickup is a real reservation; the hold shrinks by one
	assert api._block_hold(GP, bed, ci, co) == 2
	assert _left(GP, bed, ci, co) == 1, "pickup double-counted"
	_stay(GP, bed, ci, co, name="Walk-in Eval")  # the one free room
	frappe.db.savepoint("eval_t165")
	try:
		_stay(GP, bed, ci, co, name="Over Block")
		raise AssertionError("sold a room the group block holds")
	except InventoryRefused as e:
		assert "held for group blocks" in str(e), e
	frappe.db.rollback(save_point="eval_t165")
	# the group itself can still pick up its held rooms
	api.pickup_group_room(name, bed, "Eval Groom")


@check("group block: default cutoff 7 days before arrival; after it the release job frees unpicked rooms once")
def t166():
	from kamra import api
	from kamra import group_blocks as gbk
	GP = "EVAL Inv Release"
	bed, _v, _r = _inv_property(GP, "IRL", rooms=3, with_villa=False)
	ci, co = add_days(nowdate(), 30), add_days(nowdate(), 31)
	gb = api.create_group_block(GP, "Eval Conference", ci, co,
	                            [{"room_type": bed, "rooms_blocked": 2}])
	name = gb["group_booking"] if isinstance(gb, dict) else gb
	assert str(frappe.db.get_value("Group Booking", name, "cutoff_date")) \
		== str(add_days(ci, -7)), frappe.db.get_value("Group Booking", name, "cutoff_date")
	# a short-lead block holds until the day before arrival
	assert gbk.default_cutoff(add_days(nowdate(), 3)) == str(add_days(nowdate(), 2))
	api.save_group_blocks(name, [{"room_type": bed, "rooms_blocked": 2}],
	                      status="Confirmed")
	api.pickup_group_room(name, bed, "Eval Speaker")
	assert _left(GP, bed, ci, co) == 1
	assert not any(r["group_booking"] == name for r in gbk.release_expired_blocks())
	# the cutoff passes
	frappe.db.set_value("Group Booking", name, "cutoff_date", add_days(nowdate(), -1))
	out = [r for r in gbk.release_expired_blocks() if r["group_booking"] == name]
	assert out == [{"group_booking": name, "rooms_released": 1}], out
	assert frappe.db.get_value("Group Booking", name, "released_on")
	row = frappe.get_all("Group Room Block", filters={"parent": name},
	                     fields=["rooms_blocked", "rooms_released"])[0]
	assert (row.rooms_blocked, row.rooms_released) == (2, 1), row
	assert _left(GP, bed, ci, co) == 2, "released rooms not back on sale"
	assert frappe.db.exists("Agent Action Log", {
		"reference_name": name, "action_type": "group_block_release"})
	assert not [r for r in gbk.release_expired_blocks() if r["group_booking"] == name], \
		"released twice"
	detail = api.group_detail(name)
	assert detail["group"]["released_on"] and not detail["group"]["holds_inventory"]
	assert detail["pickup"][0]["rooms_released"] == 1, detail["pickup"]
	# pushing the cutoff back re-opens the hold
	api.save_group_blocks(name, [{"room_type": bed, "rooms_blocked": 2}],
	                      cutoff_date=str(add_days(nowdate(), 5)))
	assert not frappe.db.get_value("Group Booking", name, "released_on")
	assert _left(GP, bed, ci, co) == 1


@check("request inbox + accept/decline are front-desk MCP tools; the release job is scheduled")
def t167():
	from kamra.hooks import scheduler_events
	from kamra.mcp_tools import BY_NAME
	for n in ("accept_booking_request", "decline_booking_request"):
		spec = BY_NAME[n]
		assert spec.mutating and spec.group == "Front desk", spec
		assert spec.module == "front-desk", spec
	assert not BY_NAME["booking_requests"].mutating
	assert BY_NAME["booking_requests"].inject_property
	assert BY_NAME["decline_booking_request"].required == ("reservation", "reason")
	assert "kamra.group_blocks.release_expired_blocks" in \
		scheduler_events["cron"]["*/15 * * * *"]


def _fle(folios, ledgers=None):
	"""(debit, credit) on these folios' ledger entries."""
	folios = [folios] if isinstance(folios, str) else list(folios)
	sql = ("SELECT COALESCE(SUM(debit), 0), COALESCE(SUM(credit), 0) "
	       "FROM `tabFolio Ledger Entry` WHERE folio IN %(f)s")
	if ledgers:
		sql += " AND ledger IN %(l)s"
	dr, cr = frappe.db.sql(sql, {"f": tuple(folios), "l": tuple(ledgers or ())})[0]
	return float(dr), float(cr)

def _assert_folio_on_ledger(folio):
	"""What the Guest + Deposit ledgers say the folio owes == its balance."""
	bal = float(frappe.db.get_value("Folio", folio, "balance") or 0)
	dr, cr = _fle(folio, ("Guest", "Deposit"))
	assert abs((dr - cr) - bal) < 0.01, \
		f"{folio}: ledger says {dr - cr:.2f}, folio says {bal:.2f}"

def _assert_level(folios):
	"""Settled books: debits == credits across every ledger of these folios."""
	dr, cr = _fle(folios)
	assert abs(dr - cr) < 0.01, f"trial balance Dr {dr:.2f} vs Cr {cr:.2f}"

def _assert_company_ar(account):
	"""Per-company AR (the AR ledger on its folios) == the sum of its open
	folios; the account balance is that less any unapplied credit; the
	aging buckets add up to the balance."""
	from kamra.ledger import city_ledger_aging, city_ledger_open_folios
	items = city_ledger_open_folios(account)
	folios = [r["folio"] for r in items]
	dr, cr = _fle(folios, ("AR",)) if folios else (0.0, 0.0)
	open_sum = sum(r["outstanding"] for r in items)
	assert abs((dr - cr) - open_sum) < 0.01, \
		f"AR ledger {dr - cr:.2f} vs open folios {open_sum:.2f}"
	prop = frappe.db.get_value("City Ledger Account", account, "property")
	row = next(a for a in city_ledger_aging(prop)["accounts"] if a["name"] == account)
	assert abs(float(row["balance"]) - (row["open_balance"] - row["unapplied_credit"])) < 0.01, row
	buckets = sum(row[k] for k in ("current", "b30", "b60", "b90", "b90p"))
	assert abs(buckets - max(float(row["balance"]), 0)) < 0.01, row
	# the due-date buckets (#238) add up to the same balance
	due = sum(row[k] for k in ("not_due", "d1_30", "d31_60", "d61_90", "d90p"))
	assert abs(due - max(float(row["balance"]), 0)) < 0.01, row
	return row

def _ledger_room(code):
	name = frappe.db.get_value("Room", {"property": P, "room_number": code})
	return name or frappe.get_doc({"doctype": "Room", "property": P, "room_number": code,
	                               "room_type": RT}).insert(ignore_permissions=True).name

def _in_house(name, phone, ci, co, room=None, company=None):
	res = _res(_guest(name, phone), ci, co, room)
	if company:
		res.booking_type = "Corporate"
		res.company = company
	res.status = "Checked In"
	res.save(ignore_permissions=True)
	folio = frappe.db.get_value("Folio", {"reservation": res.name, "folio_type": "Guest"})
	return res, folio

def _credit_corp(name):
	return frappe.get_doc({"doctype": "Corporate Account", "company_name": name,
	                       "credit_allowed": 1}).insert(ignore_permissions=True).name

@check("ledger: charge, void, advance, payment and refund keep each folio equal to its ledger; settled = level")
def t130():
	from kamra import api
	res, folio = _in_house("Eval Ledger Money", "+91 70000 00130", "2036-05-01",
	                       "2036-05-02", _ledger_room("L130"))
	api.add_folio_charge(folio, "Laundry", "eval ledger laundry", 500, gst_rate=18)
	_assert_folio_on_ledger(folio)
	wrong = api.add_folio_charge(folio, "Misc", "eval wrong line", 200)["charges"][-1]["name"]
	api.void_folio_charge(folio, wrong, reason="eval posted in error")
	_assert_folio_on_ledger(folio)
	api.add_folio_payment(folio, "Cash", 1000, kind="Advance")
	owed = float(frappe.db.get_value("Folio", folio, "balance"))
	assert owed < 0, owed
	api.refund_folio_payment(folio, -owed, "Cash", "eval over-collected")
	_assert_folio_on_ledger(folio)
	assert abs(float(frappe.db.get_value("Folio", folio, "balance"))) < 0.01
	_assert_level(folio)

@check("ledger: room night + meal plan + levy (audit/checkout path) reach the Guest ledger once")
def t131():
	from kamra.folio import post_remaining_nights, post_room_night
	saved = frappe.db.get_value("Property", P, ["room_levy_percent"], as_dict=True)
	frappe.db.set_value("Property", P, "room_levy_percent", 2)
	frappe.clear_document_cache("Property", P)
	try:
		mp = frappe.db.get_value("Meal Plan", {"property": P, "code": "CP"}) or \
			frappe.get_doc({"doctype": "Meal Plan", "property": P, "code": "CP",
			                "label": "Eval Ledger Breakfast", "price_per_adult": 300,
			                }).insert(ignore_permissions=True).name
		res, folio = _in_house("Eval Ledger Night", "+91 70000 00131", "2036-05-03",
		                       "2036-05-06", _ledger_room("L131"))
		res.meal_plan = mp
		res.save(ignore_permissions=True)
		assert post_room_night(res, "2036-05-03") is True
		assert post_room_night(res, "2036-05-03") is False, "double posted"
		post_remaining_nights(frappe.get_doc("Reservation", res.name))
		fd = frappe.get_doc("Folio", folio)
		kinds = {c.charge_type for c in fd.charges}
		assert {"Room", "Meal Plan", "Room Levy"} <= kinds, kinds
		assert len([c for c in fd.charges if c.charge_type == "Room"]) == 3
		for c in fd.charges:
			n = frappe.db.count("Folio Ledger Entry", {
				"source_doctype": "Folio Charge", "source_name": c.name})
			assert n == 1, f"{c.charge_type} {c.posting_date} has {n} ledger entries"
		_assert_folio_on_ledger(folio)
		api_pay = float(fd.balance)
		from kamra import api
		api.add_folio_payment(folio, "Card", api_pay)
		_assert_level(folio)
	finally:
		frappe.db.set_value("Property", P, "room_levy_percent", saved.room_levy_percent)
		frappe.clear_document_cache("Property", P)

@check("ledger: night audit room nights and the no-show fee land on the ledger")
def t132():
	from kamra.folio import run_night_audit
	today = nowdate()
	saved = frappe.db.get_value("Property", P, ["business_date", "no_show_charge"],
	                            as_dict=True)
	frappe.db.set_value("Property", P, {"business_date": today,
	                                    "no_show_charge": "First Night"})
	try:
		frappe.db.delete("Night Audit Run", {"property": P, "business_date": today})
		res, folio = _in_house("Eval Ledger Audit", "+91 70000 00132", today,
		                       add_days(today, 2), _ledger_room("L132"))
		ns = _res(_guest("Eval Ledger NoShow", "+91 70000 00133"),
		          add_days(today, -1), add_days(today, 1), allow_past=1)
		run_night_audit(P)
		room = frappe.get_all("Folio Charge", filters={
			"parent": folio, "charge_type": "Room", "posting_date": today}, pluck="name")
		assert room, "audit posted no room night"
		assert frappe.db.exists("Folio Ledger Entry", {
			"source_doctype": "Folio Charge", "source_name": room[0],
			"business_date": today}), "room night missing from the ledger"
		_assert_folio_on_ledger(folio)
		ns_folio = frappe.db.get_value("Folio", {"reservation": ns.name, "folio_type": "Guest"})
		assert ns_folio and float(frappe.db.get_value("Folio", ns_folio, "balance")) > 0, \
			"no-show fee not posted"
		_assert_folio_on_ledger(ns_folio)
	finally:
		frappe.db.set_value("Property", P, {
			"business_date": saved.business_date,
			"no_show_charge": saved.no_show_charge})

@check("ledger: cancellation fee, cleaning fee, add-ons and allowance reach the ledger")
def t133():
	from kamra import api
	saved = frappe.db.get_value(
		"Property", P, ["free_cancel_days", "cancellation_fee", "cleaning_fee"],
		as_dict=True)
	frappe.db.set_value("Property", P, {"free_cancel_days": 2,
	                                    "cancellation_fee": "First Night",
	                                    "cleaning_fee": 750})
	try:
		late = _res(_guest("Eval Ledger Cancel", "+91 70000 00134"),
		            add_days(nowdate(), 1), add_days(nowdate(), 2))
		assert api.cancel_reservation(late.name)["fee"] > 0
		cf = frappe.db.get_value("Folio", {"reservation": late.name, "folio_type": "Guest"})
		_assert_folio_on_ledger(cf)

		exp = frappe.get_doc({
			"doctype": "Experience", "property": P,
			"experience_name": "EVAL Ledger Spa", "category": "Activity",
			"price": 1200, "gst_rate": 18}).insert(ignore_permissions=True)
		out = api.create_booking(
			property=P, room_type=RT, check_in_date="2036-05-10",
			check_out_date="2036-05-11", guest_name="Eval Ledger Addon",
			phone="+91 70000 00135", addons=[{"experience": exp.name, "qty": 1}])
		api.check_in(out["reservation"])
		folio = frappe.db.get_value(
			"Folio", {"reservation": out["reservation"], "folio_type": "Guest"})
		kinds = {c.charge_type for c in frappe.get_doc("Folio", folio).charges}
		assert {"Cleaning Fee", "Misc"} <= kinds, kinds
		_assert_folio_on_ledger(folio)
		api.post_allowance(folio, 100, "eval service recovery")
		_assert_folio_on_ledger(folio)
	finally:
		frappe.db.set_value("Property", P, saved)

@check("ledger: transfer and split move a line's ledger with it; value conserved")
def t134():
	from kamra.folio import post_room_night, split_charge, split_folio, transfer_charge
	res, main = _in_house("Eval Ledger Split", "+91 70000 00136", "2036-05-12",
	                      "2036-05-14", _ledger_room("L134"))
	post_room_night(res, "2036-05-12")
	post_room_night(res, "2036-05-13")
	other = split_folio(res.name, "Extra")
	before = _fle([main, other])
	rows = [c.name for c in frappe.get_doc("Folio", main).charges if c.charge_type == "Room"]
	transfer_charge(main, rows[0], other)
	split_charge(main, rows[1], other, percent=30)
	for f in (main, other):
		_assert_folio_on_ledger(f)
	after = _fle([main, other])
	assert abs((after[0] - after[1]) - (before[0] - before[1])) < 0.01, (before, after)

@check("city ledger: settlement credits AR oldest first; company AR == its open folios; books level")
def t135():
	from kamra import api
	from kamra.ledger import city_ledger_settle, transfer_to_city_ledger
	corp = _credit_corp("EVAL Ledger Settle Corp")
	folios = []
	for i, phone in enumerate(("+91 70000 00137", "+91 70000 00138")):
		_, f = _in_house(f"Eval Ledger AR {i}", phone, f"2036-06-0{i + 1}",
		                 f"2036-06-0{i + 2}", _ledger_room(f"L135{i}"), company=corp)
		api.add_folio_charge(f, "Misc", "eval AR charge", 1000 * (i + 1))
		folios.append(f)
	acct = None
	for f in folios:
		acct = transfer_to_city_ledger(f, corp)["account"]
	# the first bill is the older one
	frappe.db.sql("""UPDATE `tabCity Ledger Entry` SET posting_date = '2020-01-01'
	                 WHERE folio = %s AND kind = 'Invoice'""", folios[0])
	_assert_company_ar(acct)
	owed = [float(frappe.db.get_value("City Ledger Entry",
	                                  {"folio": f, "kind": "Invoice"}, "debit")) for f in folios]
	out = city_ledger_settle(acct, owed[0] + 100, "Bank Transfer", "EVAL-UTR-1")
	assert out["applied"] == [{"folio": folios[0], "amount": owed[0]},
	                          {"folio": folios[1], "amount": 100.0}], out
	assert out["unapplied"] == 0, out
	_assert_company_ar(acct)
	city_ledger_settle(acct, owed[1] - 100, "Bank Transfer", "EVAL-UTR-2")
	row = _assert_company_ar(acct)
	assert abs(float(row["balance"])) < 0.01 and row["open_balance"] == 0, row
	for f in folios:
		_assert_folio_on_ledger(f)
	_assert_level(folios)

@check("city ledger: explicit allocation, excess kept as unapplied credit, next bill uses it")
def t136():
	from kamra import api
	from kamra.ledger import city_ledger_account, city_ledger_settle, transfer_to_city_ledger
	corp = _credit_corp("EVAL Ledger Alloc Corp")
	folios = []
	for i, phone in enumerate(("+91 70000 00139", "+91 70000 00140", "+91 70000 00141")):
		_, f = _in_house(f"Eval Ledger Alloc {i}", phone, f"2036-07-0{i + 1}",
		                 f"2036-07-0{i + 2}", _ledger_room(f"L136{i}"), company=corp)
		api.add_folio_charge(f, "Misc", "eval alloc charge", 1000)
		folios.append(f)
	acct = transfer_to_city_ledger(folios[0], corp)["account"]
	transfer_to_city_ledger(folios[1], corp)
	# explicitly pay the newer bill only, with 500 over
	owed = float(frappe.db.get_value("Folio", folios[0], "grand_total"))
	out = city_ledger_settle(acct, owed + 500, "Cheque", "EVAL-CHQ-9",
	                         allocations=[{"folio": folios[1], "amount": owed}])
	assert out["applied"] == [{"folio": folios[1], "amount": owed}], out
	assert abs(out["unapplied"] - 500) < 0.01, out
	row = _assert_company_ar(acct)
	assert abs(row["unapplied_credit"] - 500) < 0.01, row
	view = city_ledger_account(acct)
	assert [r["folio"] for r in view["open_items"]] == [folios[0]], view["open_items"]
	# overpay everything: excess stays, nothing refused
	out = city_ledger_settle(acct, owed + 1000, "Bank Transfer", "EVAL-UTR-3")
	assert abs(out["unapplied"] - 1000) < 0.01, out
	row = _assert_company_ar(acct)
	assert abs(row["unapplied_credit"] - 1500) < 0.01 and row["open_balance"] == 0, row
	assert abs(float(row["balance"]) + 1500) < 0.01, row
	# the next bill is settled from the credit at once
	moved = transfer_to_city_ledger(folios[2], corp)
	assert abs(moved["applied_from_credit"] - owed) < 0.01, moved
	row = _assert_company_ar(acct)
	assert abs(row["unapplied_credit"] - (1500 - owed)) < 0.01, row
	_assert_level(folios)

@check("city ledger: bad allocations refused; Front Desk can't record a company payment")
def t137():
	from kamra import api
	from kamra.ledger import city_ledger_settle, transfer_to_city_ledger
	corp = _credit_corp("EVAL Ledger Guard Corp")
	_, f = _in_house("Eval Ledger Guard", "+91 70000 00142", "2036-08-01",
	                 "2036-08-02", _ledger_room("L137"), company=corp)
	api.add_folio_charge(f, "Misc", "eval guard charge", 1000)
	_, stranger = _in_house("Eval Ledger Stranger", "+91 70000 00143", "2036-08-03",
	                        "2036-08-04", _ledger_room("L137"))
	acct = transfer_to_city_ledger(f, corp)["account"]
	owed = float(frappe.db.get_value("City Ledger Entry", {"folio": f}, "debit"))
	for amount, alloc, why in (
		(0, None, "positive"),
		(owed, [{"folio": stranger, "amount": 10}], "nothing open"),
		(owed + 10, [{"folio": f, "amount": owed + 10}], "can't apply"),
		(10, [{"folio": f, "amount": 20}], "more than the payment"),
	):
		try:
			city_ledger_settle(acct, amount, allocations=alloc)
			raise AssertionError(f"settle accepted: {why}")
		except frappe.ValidationError as e:
			assert why in str(e), e
	assert not frappe.db.exists("City Ledger Entry", {"account": acct, "kind": "Payment"})
	me = frappe.session.user
	frappe.set_user("frontdesk@kamra.local")  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow
	try:
		city_ledger_settle(acct, owed)
		raise AssertionError("Front Desk recorded a company payment")
	except frappe.PermissionError:
		pass
	finally:
		frappe.set_user(me)  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow
	_assert_company_ar(acct)

@check("ledger backfill: unledgered charges and payments, moved and split lines brought in step, dated; idempotent")
def t138():
	from kamra.folio import _recalculate
	from kamra.patches.v40 import backfill_charge_ledger
	res, folio = _in_house("Eval Ledger Backfill", "+91 70000 00144", "2036-09-01",
	                       "2036-09-02", _ledger_room("L138"))
	# lines written the old way: straight onto the folio, no ledger
	doc = frappe.get_doc("Folio", folio)
	for amt in (800, 1200):
		doc.append("charges", {"posting_date": "2036-09-01", "charge_type": "Room",
		                       "description": "eval legacy night", "qty": 1,
		                       "rate": amt, "amount": amt, "gst_rate": 5})
	doc.append("payments", {"posting_date": "2036-09-01", "payment_kind": "Payment",
	                        "mode": "Cash", "amount": 500})
	_recalculate(doc)
	doc.save(ignore_permissions=True)
	legacy = [c.name for c in doc.charges if c.description == "eval legacy night"]
	assert not frappe.db.exists("Folio Ledger Entry", {"source_name": ["in", legacy]})
	# a ledgered line whose row has gone, and one trimmed by an old split
	from kamra import api
	gone = api.add_folio_charge(folio, "Misc", "eval vanished", 300)["charges"][-1]["name"]
	trim = api.add_folio_charge(folio, "Misc", "eval trimmed", 1000)["charges"][-1]["name"]
	frappe.db.delete("Folio Charge", {"name": gone})
	frappe.db.set_value("Folio Charge", trim, {"amount": 700, "rate": 700, "total": 700},
	                    update_modified=False)
	doc = frappe.get_doc("Folio", folio)
	_recalculate(doc)
	doc.db_update()
	backfill_charge_ledger.execute()
	dates = frappe.get_all("Folio Ledger Entry", filters={
		"source_doctype": "Folio Charge", "source_name": ["in", legacy]},
		pluck="business_date")
	assert sorted(str(d) for d in dates) == ["2036-09-01", "2036-09-01"], dates
	_assert_folio_on_ledger(folio)
	n = frappe.db.count("Folio Ledger Entry")
	backfill_charge_ledger.execute()
	assert frappe.db.count("Folio Ledger Entry") == n, "backfill not idempotent"

@check("AR backfill: an old folio-less company payment is applied oldest first; idempotent")
def t139():
	from kamra import api
	from kamra.ledger import transfer_to_city_ledger
	from kamra.patches.v40 import apply_city_ledger_payments
	corp = _credit_corp("EVAL Ledger Old Pay Corp")
	_, f = _in_house("Eval Ledger Old Pay", "+91 70000 00145", "2036-10-01",
	                 "2036-10-02", _ledger_room("L139"), company=corp)
	api.add_folio_charge(f, "Misc", "eval old pay charge", 1000)
	acct = transfer_to_city_ledger(f, corp)["account"]
	owed = float(frappe.db.get_value("City Ledger Entry", {"folio": f}, "debit"))
	# what the old city_ledger_settle wrote: account entry only, no AR credit
	frappe.get_doc({"doctype": "City Ledger Entry", "account": acct, "property": P,
	                "posting_date": "2036-10-20", "kind": "Payment", "debit": 0,
	                "credit": owed, "reference": "EVAL-OLD"}).insert(ignore_permissions=True)
	frappe.db.set_value("City Ledger Account", acct, "balance", 0)
	apply_city_ledger_payments.execute()
	assert frappe.db.get_value("Folio Ledger Entry", {
		"folio": f, "ledger": "AR", "source_doctype": "City Ledger Entry"},
		"business_date") is not None
	row = _assert_company_ar(acct)
	assert row["open_balance"] == 0 and row["unapplied_credit"] == 0, row
	n = frappe.db.count("Folio Ledger Entry")
	apply_city_ledger_payments.execute()
	assert frappe.db.count("Folio Ledger Entry") == n, "AR backfill not idempotent"
	_assert_level(f)


FAR = "2032-05-10"  # a night no other check books

@check("a demand-premium night is billed at the quoted rate after occupancy drops")
def t180():
	from kamra.folio import _nightly_room_rate, post_room_night
	from kamra.pricing import forecast_occupancy, quote
	ci, co = FAR, add_days(FAR, 1)
	g = _guest("Eval Demand Filler", "+91 70000 00180")
	filler = _res(g, ci, co)
	occ = forecast_occupancy(P, ci)
	assert occ > 0, occ
	frappe.get_doc({
		"doctype": "Hurdle Rate", "property": P, "room_type": RT,
		"occupancy_from": occ, "premium_pct": 25,
	}).insert(ignore_permissions=True)
	g2 = _guest("Eval Demand Guest", "+91 70000 00181")
	res = _res(g2, ci, co)
	quoted = float(res.night_rates[0].rate)
	assert quoted == 5000, quoted  # 4000 + 25% premium
	assert float(res.night_rates[0].demand_premium_pct) == 25
	# the filler cancels: the house is emptier and a fresh quote drops
	frappe.db.set_value("Reservation", filler.name, "status", "Cancelled")
	fresh = quote(P, RT, ci, co, 2, 0, exclude_reservation=res.name)
	assert fresh["room_total"] == 4000, fresh["room_total"]
	# ...but the confirmed booking still bills its quoted night
	res = frappe.get_doc("Reservation", res.name)
	assert _nightly_room_rate(res, ci) == quoted
	res.special_requests = "quiet room"
	res.save(ignore_permissions=True)
	assert float(res.night_rates[0].rate) == quoted
	from kamra.folio import open_folio
	open_folio(res)
	post_room_night(res, ci)
	amt = frappe.get_all("Folio Charge", filters={
		"reservation": res.name, "charge_type": "Room"}, pluck="amount")
	assert [float(a) for a in amt] == [quoted], amt

@check("a season added after booking never re-prices the confirmed stay")
def t181():
	from kamra.folio import _nightly_room_rate
	ci, co = add_days(FAR, 3), add_days(FAR, 5)
	res = _res(_guest("Eval Season Lock", "+91 70000 00182"), ci, co)
	before = float(res.amount_after_tax)
	frappe.get_doc({
		"doctype": "Season", "property": P, "season_name": "Eval Late Season",
		"start_date": ci, "end_date": co, "adjustment_type": "Percent",
		"adjustment_value": 50, "priority": 50,
	}).insert(ignore_permissions=True)
	res = frappe.get_doc("Reservation", res.name)
	res.special_requests = "anything"
	res.save(ignore_permissions=True)
	assert float(res.amount_after_tax) == before, (res.amount_after_tax, before)
	assert _nightly_room_rate(res, ci) == 4000

@check("amend_stay re-prices only after the new price is confirmed")
def t182():
	from kamra import api
	ci, co = add_days(FAR, 8), add_days(FAR, 10)
	res = _res(_guest("Eval Amend Lock", "+91 70000 00183"), ci, co)
	frappe.get_doc({
		"doctype": "Season", "property": P, "season_name": "Eval Amend Season",
		"start_date": co, "end_date": co, "adjustment_type": "Percent",
		"adjustment_value": 50, "priority": 50,
	}).insert(ignore_permissions=True)
	new_co = add_days(co, 1)
	pv = api.amend_stay_preview(res.name, ci, new_co)
	assert pv["needs_confirmation"] and [n["rate"] for n in pv["nights"]] == [4000, 4000, 6000], pv
	try:
		api.amend_stay(res.name, ci, new_co)
		raise AssertionError("re-priced without confirm_price")
	except api.PriceConfirmationRequired:
		pass
	assert str(frappe.db.get_value("Reservation", res.name, "check_out_date")) == str(co)
	out = api.amend_stay(res.name, ci, new_co, confirm_price=1)
	assert abs(float(out["amount_after_tax"]) - pv["new_amount"]) < 0.01, (out, pv)
	rates = frappe.get_all("Reservation Night Rate", filters={"parent": res.name},
	                       fields=["rate"], order_by="stay_date asc", pluck="rate")
	assert [float(r) for r in rates] == [4000, 4000, 6000], rates

def _audit_eval(day_close, run_at, fn):
	"""Run the audit closing `day_close` with the clock pinned at run_at."""
	from datetime import datetime
	from unittest.mock import patch

	from kamra import folio
	frappe.db.set_value("Property", P, "business_date", day_close)
	frappe.db.delete("Night Audit Run", {"property": P, "business_date": day_close})
	with patch.object(folio, "audit_clock", return_value=datetime.strptime(run_at, "%Y-%m-%d %H:%M")):
		return fn()

@check("night audit holds a late arrival whose ETA is after the run, then no-shows it")
def t183():
	from kamra.folio import run_night_audit
	yesterday = add_days(nowdate(), -1)
	saved = frappe.db.get_value("Property", P, ["business_date", "no_show_charge",
	                            "protect_late_arrivals"], as_dict=True)
	frappe.db.set_value("Property", P, {"no_show_charge": "First Night",
	                                    "protect_late_arrivals": 1})
	try:
		late = _res(_guest("Eval Late ETA", "+91 70000 00184"), yesterday,
		            nowdate(), allow_past=1)
		frappe.db.set_value("Reservation", late.name, "eta", "01:30")
		out = _audit_eval(yesterday, f"{yesterday} 23:00",
		                  lambda: run_night_audit(P))
		assert frappe.db.get_value("Reservation", late.name, "status") == "Confirmed"
		assert [h["reservation"] for h in out["held_late_arrivals"]] == [late.name], out
		_audit_eval(nowdate(), f"{nowdate()} 23:30",
		                  lambda: run_night_audit(P))
		assert frappe.db.get_value("Reservation", late.name, "status") == "No Show"
	finally:
		frappe.db.set_value("Property", P, dict(saved))

@check("an OTA no-show is flagged but carries no fee (the OTA collects)")
def t184():
	from kamra.folio import run_night_audit
	today = nowdate()
	saved = frappe.db.get_value("Property", P, ["business_date", "no_show_charge",
	                            "waive_no_show_fee_for_ota"], as_dict=True)
	frappe.db.set_value("Property", P, {"no_show_charge": "First Night",
	                                    "waive_no_show_fee_for_ota": 1})
	try:
		ota = _res(_guest("Eval OTA NoShow", "+91 70000 00185"), today,
		           add_days(today, 1))
		frappe.db.set_value("Reservation", ota.name, {"source": "OTA",
		                                              "channel": "Booking.com"})
		out = _audit_eval(today, f"{today} 23:59", lambda: run_night_audit(P))
		assert frappe.db.get_value("Reservation", ota.name, "status") == "No Show"
		assert out["no_show_fees_waived"] >= 1, out
		assert not frappe.get_all("Folio Charge", filters={
			"reservation": ota.name, "description": ("like", "No-show%")})
	finally:
		frappe.db.set_value("Property", P, dict(saved))

@check("non-guaranteed same-day arrivals are released at the release time, fee-free")
def t185():
	from datetime import datetime

	from kamra.no_show import release_for_property
	day = add_days(FAR, 20)
	frappe.db.set_value("Property", P, "non_guaranteed_release_time", "18:00")
	loose = _res(_guest("Eval Release", "+91 70000 00186"), day, add_days(day, 1))
	paid = _res(_guest("Eval Release Paid", "+91 70000 00187"), day, add_days(day, 1))
	frappe.db.set_value("Reservation", paid.name, "advance_paid", 1000)
	at = lambda hm: datetime.strptime(f"{day} {hm}", "%Y-%m-%d %H:%M")  # noqa: E731
	assert release_for_property(P, now=at("17:59")) == []
	assert release_for_property(P, now=at("18:05")) == [loose.name]
	assert frappe.db.get_value("Reservation", loose.name, "status") == "Cancelled"
	assert float(frappe.db.get_value("Reservation", loose.name, "cancellation_fee") or 0) == 0
	assert frappe.db.get_value("Reservation", paid.name, "status") == "Confirmed"

@check("an OTA booking bills the channel's own nightly prices")
def t186():
	from kamra.channel_manager import lock_channel_rates
	ci, co = add_days(FAR, 25), add_days(FAR, 27)
	doc = frappe.get_doc({
		"doctype": "Reservation", "property": P, "room_type": RT,
		"guest": _guest("Eval OTA Rates", "+91 70000 00188"),
		"check_in_date": ci, "check_out_date": co, "adults": 2,
		"source": "OTA", "channel": "Agoda", "auto_price": 0,
		"amount_after_tax": 10500,
	})
	lock_channel_rates(doc, 10500, [{"date": ci, "amount": 4500},
	                                {"date": add_days(ci, 1), "amount": 6000}])
	doc.insert(ignore_permissions=True)
	rows = sorted(doc.night_rates, key=lambda r: str(r.stay_date))
	gross = [float(r.rate) * (1 + float(r.gst_rate) / 100) for r in rows]
	assert abs(sum(gross) - 10500) < 0.05, gross
	assert abs(gross[0] - 4500) < 0.05 and abs(gross[1] - 6000) < 0.05, gross


def _leak_net(folio, ledger):
	return round(float(frappe.db.sql(
		"""SELECT COALESCE(SUM(debit - credit), 0) FROM `tabFolio Ledger Entry`
		   WHERE folio = %s AND ledger = %s""", (folio, ledger))[0][0]), 2)


def _leak_corp(name):
	return frappe.get_doc({
		"doctype": "Corporate Account", "company_name": name, "credit_allowed": 1,
		"billing_rules": [{"charge_type": "Room", "pay_by": "Company"},
		                  {"charge_type": "Food & Beverage", "pay_by": "Company"}],
	}).insert(ignore_permissions=True).name


@check("check-out moves only the company's folio to the city ledger; liquor stays on the guest")
def t190():
	from kamra import api
	corp = _leak_corp("EVAL Leak Corp")
	res, guest = _in_house("Eval Leak Liquor", "+91 70000 00190", "2037-01-10",
	                       "2037-01-11", _ledger_room("L190"), company=corp)
	api.add_folio_charge(guest, "Food & Beverage", "eval whisky", 800,
	                     is_alcohol=1)
	liquor = float(frappe.db.get_value("Folio", guest, "balance"))
	try:
		api.check_out(res.name)
		raise AssertionError("checked out with the liquor unpaid")
	except frappe.ValidationError as e:
		assert "still owed" in str(e), e
	assert not frappe.get_all("City Ledger Entry", filters={"folio": guest})
	api.add_folio_payment(guest, "Cash", liquor)
	api.check_out(res.name)
	company = frappe.db.get_value(
		"Folio", {"reservation": res.name, "folio_type": "Company"})
	moved = frappe.get_all("City Ledger Entry",
	                       filters={"folio": ["in", [guest, company]]},
	                       pluck="folio")
	assert moved == [company], moved
	assert not [p for p in frappe.get_doc("Folio", guest).payments
	            if p.mode == "Company Credit"]


@check("POS: a room bill needs an in-house guest; it never closes unbilled")
def t191():
	from kamra import pos
	outlet = frappe.get_doc({
		"doctype": "POS Outlet", "property": P, "outlet_name": "Eval Leak Diner",
		"outlet_type": "Restaurant", "gst_rate": 5}).insert(ignore_permissions=True).name
	dish = frappe.get_doc({
		"doctype": "Menu Item", "property": P, "outlet": outlet,
		"item_name": "Eval Leak Idli", "category": "Food", "price": 150,
		"is_veg": 1, "available": 1, "prep_station": "Kitchen",
	}).insert(ignore_permissions=True).name
	empty = _ledger_room("L191")
	try:
		pos.create_order(outlet, [{"menu_item": dish, "qty": 1}], room=empty,
		                 order_type="Room Service")
		raise AssertionError("room service accepted for an empty room")
	except frappe.ValidationError:
		pass
	assert empty not in [r["room"] for r in pos.in_house_rooms(P)]
	res, _f = _in_house("Eval Leak RS", "+91 70000 00191", "2037-01-12",
	                    "2037-01-13", _ledger_room("L192"))
	listed = {r["room"]: r for r in pos.in_house_rooms(P)}
	assert res.room in listed and "Eval Leak RS" in listed[res.room]["guest_name"], listed
	o = pos.create_order(outlet, [{"menu_item": dish, "qty": 1}], room=res.room)
	frappe.db.set_value("Reservation", res.name, "status", "Checked Out")
	try:
		pos.deliver_order(o["order"])
		raise AssertionError("room bill delivered with no stay to post to")
	except frappe.ValidationError:
		pass
	assert pos.pay_order(o["order"], "Cash")["paid"]


@check("a folio closes only when settled; check-out counts closed folios with a balance")
def t192():
	from kamra import api
	from kamra.folio import close_folio
	res, folio = _in_house("Eval Leak Close", "+91 70000 00192", "2037-01-14",
	                       "2037-01-15", _ledger_room("L193"))
	api.add_folio_charge(folio, "Laundry", "eval laundry", 300)
	from kamra.folio import post_remaining_nights
	post_remaining_nights(res)
	try:
		close_folio(folio)
		raise AssertionError("closed with a balance")
	except frappe.ValidationError:
		pass
	frappe.db.set_value("Folio", folio, {"status": "Closed",
	                                     "invoice_number": "INV-EVAL-LEGACY"})
	try:
		api.check_out(res.name)
		raise AssertionError("checked out owing on a closed folio")
	except frappe.ValidationError as e:
		assert "still owed" in str(e), e


@check("POS: a dine-in bill signed to the room posts there, alcohol to the guest")
def t193():
	from kamra import pos
	outlet = frappe.get_doc({
		"doctype": "POS Outlet", "property": P, "outlet_name": "Eval Leak Bar",
		"outlet_type": "Restaurant", "gst_rate": 5}).insert(ignore_permissions=True).name
	gin = frappe.get_doc({
		"doctype": "Menu Item", "property": P, "outlet": outlet,
		"item_name": "Eval Leak Gin", "category": "Drinks", "price": 400,
		"is_veg": 1, "available": 1, "prep_station": "Bar", "is_alcohol": 1,
	}).insert(ignore_permissions=True).name
	corp = _leak_corp("EVAL Leak Bar Corp")
	res, guest = _in_house("Eval Leak Diner", "+91 70000 00193", "2037-01-16",
	                       "2037-01-17", _ledger_room("L194"), company=corp)
	o = pos.create_order(outlet, [{"menu_item": gin, "qty": 1}], table_no="B1",
	                     order_type="Dine In")
	pos.charge_to_room(o["order"], res.room)
	assert pos.deliver_order(o["order"])["posted_to_folio"]
	rows = frappe.get_all("Folio Charge", filters={
		"description": ["like", f"%{o['order']}%"]}, fields=["parent", "is_alcohol"])
	assert [(r.parent, r.is_alcohol) for r in rows] == [(guest, 1)], rows


@check("an advance leaves the Deposit ledger at check-in; paid check-out nets both to zero")
def t194():
	from kamra import api
	from kamra.folio import open_folio
	from kamra.ledger import transfer_advances_to_guest
	res = _res(_guest("Eval Leak Advance", "+91 70000 00194"), "2037-01-18",
	           "2037-01-19", _ledger_room("L195"))
	folio = open_folio(res)
	api.add_folio_payment(folio, "UPI", 2000, kind="Advance")
	assert _leak_net(folio, "Deposit") == -2000, _leak_net(folio, "Deposit")
	res.reload()
	res.status = "Checked In"
	res.save(ignore_permissions=True)
	assert _leak_net(folio, "Deposit") == 0, _leak_net(folio, "Deposit")
	assert transfer_advances_to_guest(res.name) == 0
	from kamra.folio import post_remaining_nights
	post_remaining_nights(res)
	owed = float(frappe.db.get_value("Folio", folio, "balance"))
	if owed > 0.009:
		api.add_folio_payment(folio, "Cash", owed)
	elif owed < -0.009:
		api.refund_folio_payment(folio, -owed, "Cash", "eval change")
	api.check_out(res.name)
	assert _leak_net(folio, "Deposit") == 0
	assert _leak_net(folio, "Guest") == 0, _leak_net(folio, "Guest")


def _routed(res_name, desc):
	"""(folio_type, is_alcohol) of the one line whose description is `desc`."""
	rows = frappe.db.sql(
		"""SELECT f.folio_type, fc.is_alcohol FROM `tabFolio Charge` fc
		   JOIN `tabFolio` f ON fc.parent = f.name
		   WHERE f.reservation = %s AND fc.description = %s""",
		(res_name, desc), as_dict=True)
	assert len(rows) == 1, (desc, rows)
	return rows[0].folio_type


def _set_company_default(value):
	frappe.db.set_value("Property", P, "default_company_billing", value)
	frappe.clear_document_cache("Property", P)


@check("credit company with no billing rules: room + food to the company, liquor and laundry to the guest")
def t200():
	from kamra import api
	from kamra.folio import post_remaining_nights
	_set_company_default("Room and F&B (liquor to guest)")
	corp = _credit_corp("EVAL Default Corp")
	res, _guest_folio = _in_house("Eval Default Corp", "+91 70000 00200", "2037-02-01",
	                              "2037-02-02", _ledger_room("L200"), company=corp)
	post_remaining_nights(res)
	room_on = frappe.db.sql(
		"""SELECT f.folio_type FROM `tabFolio Charge` fc JOIN `tabFolio` f
		   ON fc.parent = f.name WHERE f.reservation = %s AND fc.charge_type = 'Room'""",
		res.name, pluck=True)
	assert room_on == ["Company"], room_on
	api.post_stay_charge(res.name, "Food & Beverage", "eval200 lunch", 500)
	api.post_stay_charge(res.name, "Food & Beverage", "eval200 whisky", 800, is_alcohol=1)
	api.post_stay_charge(res.name, "Laundry", "eval200 laundry", 300)
	api.post_stay_charge(res.name, "Minibar", "eval200 minibar", 200)
	got = {d: _routed(res.name, d) for d in
	       ("eval200 lunch", "eval200 whisky", "eval200 laundry", "eval200 minibar")}
	assert got == {"eval200 lunch": "Company", "eval200 whisky": "Guest",
	               "eval200 laundry": "Guest", "eval200 minibar": "Guest"}, got
	shown = api.company_billing_default(corp, P)
	assert shown["applies"] and shown["default"].startswith("Room and F&B"), shown


@check("a company's own billing rules beat the property default")
def t201():
	from kamra import api
	from kamra.folio import post_remaining_nights
	_set_company_default("Everything except liquor")
	corp = frappe.get_doc({
		"doctype": "Corporate Account", "company_name": "EVAL Rules Corp",
		"credit_allowed": 1,
		"billing_rules": [{"charge_type": "Laundry", "pay_by": "Company"}],
	}).insert(ignore_permissions=True).name
	res, _g = _in_house("Eval Rules Corp", "+91 70000 00201", "2037-02-03",
	                    "2037-02-04", _ledger_room("L201"), company=corp)
	post_remaining_nights(res)
	api.post_stay_charge(res.name, "Food & Beverage", "eval201 lunch", 500)
	api.post_stay_charge(res.name, "Laundry", "eval201 laundry", 300)
	api.post_stay_charge(res.name, "Minibar", "eval201 vodka", 300, is_alcohol=1)
	assert _routed(res.name, "eval201 lunch") == "Guest"
	assert _routed(res.name, "eval201 laundry") == "Company"
	assert _routed(res.name, "eval201 vodka") == "Guest"
	room_on = frappe.db.sql(
		"""SELECT f.folio_type FROM `tabFolio Charge` fc JOIN `tabFolio` f
		   ON fc.parent = f.name WHERE f.reservation = %s AND fc.charge_type = 'Room'""",
		res.name, pluck=True)
	assert room_on == ["Guest"], room_on
	assert not api.company_billing_default(corp, P)["applies"]
	# "Everything except liquor" still keeps liquor off a rule-less company
	corp2 = _credit_corp("EVAL Everything Corp")
	res2, _g2 = _in_house("Eval Everything Corp", "+91 70000 00211", "2037-02-05",
	                      "2037-02-06", _ledger_room("L211"), company=corp2)
	api.post_stay_charge(res2.name, "Laundry", "eval201 all laundry", 300)
	api.post_stay_charge(res2.name, "Food & Beverage", "eval201 all beer", 300, is_alcohol=1)
	assert _routed(res2.name, "eval201 all laundry") == "Company"
	assert _routed(res2.name, "eval201 all beer") == "Guest"
	_set_company_default("Room and F&B (liquor to guest)")


@check("'Nothing' keeps the strict routing; a company without credit gets nothing by default")
def t202():
	from kamra import api
	from kamra.folio import post_remaining_nights
	_set_company_default("Nothing (guest pays unless rules say so)")
	corp = _credit_corp("EVAL Strict Corp")
	res, _g = _in_house("Eval Strict Corp", "+91 70000 00202", "2037-02-07",
	                    "2037-02-08", _ledger_room("L202"), company=corp)
	post_remaining_nights(res)
	api.post_stay_charge(res.name, "Food & Beverage", "eval202 lunch", 500)
	assert _routed(res.name, "eval202 lunch") == "Guest"
	assert not frappe.db.get_value("Folio", {"reservation": res.name,
	                                         "folio_type": "Company"})
	_set_company_default("Room and F&B (liquor to guest)")
	cash_corp = frappe.get_doc({"doctype": "Corporate Account",
	                            "company_name": "EVAL No Credit Corp"}
	                           ).insert(ignore_permissions=True).name
	res2, _g2 = _in_house("Eval No Credit", "+91 70000 00212", "2037-02-09",
	                      "2037-02-10", _ledger_room("L212"), company=cash_corp)
	api.post_stay_charge(res2.name, "Food & Beverage", "eval202 nc lunch", 500)
	assert _routed(res2.name, "eval202 nc lunch") == "Guest"
	assert not api.company_billing_default(cash_corp, P)["applies"]


def _eval_bill_outlet(name):
	outlet = frappe.get_doc({
		"doctype": "POS Outlet", "property": P, "outlet_name": name,
		"outlet_type": "Restaurant", "gst_rate": 5}).insert(ignore_permissions=True).name
	dish = frappe.get_doc({
		"doctype": "Menu Item", "property": P, "outlet": outlet,
		"item_name": f"{name} Thali", "category": "Food", "price": 300,
		"is_veg": 1, "available": 1, "prep_station": "Kitchen",
	}).insert(ignore_permissions=True).name
	return outlet, dish


def _refused(fn, *args):
	try:
		fn(*args)
	except frappe.ValidationError as e:
		assert any(w in str(e) for w in ("not settled", "authoriz", "payment mode")), e
		return
	raise AssertionError(f"{fn.__name__} closed an unsettled bill")


@check("POS: an unpaid dine-in or takeaway bill cannot be closed; serving it does not settle it")
def t203():
	from kamra import pos
	outlet, dish = _eval_bill_outlet("Eval Unpaid")
	o = pos.create_order(outlet, [{"menu_item": dish, "qty": 1}], table_no="U1",
	                     order_type="Dine In")
	pos.fire_kot(o["order"])
	pos.mark_prepared(o["order"])  # the kitchen served it
	assert frappe.db.get_value("POS Order", o["order"], "status") == "Preparing"
	_refused(pos.deliver_order, o["order"])
	assert frappe.db.get_value("POS Order", o["order"], "status") != "Delivered"
	# the same rule holds on a direct save, not just the endpoint
	doc = frappe.get_doc("POS Order", o["order"])
	doc.status = "Delivered"
	_refused(doc.save)
	assert pos.pay_order(o["order"], "Card")["paid"]
	assert frappe.db.get_value("POS Order", o["order"], "status") == "Delivered"

	t = pos.create_order(outlet, [{"menu_item": dish, "qty": 2}], order_type="Takeaway")
	_refused(pos.deliver_order, t["order"])
	# NC without an authorizer is not complimentary
	frappe.db.set_value("POS Order", t["order"], "nc", 1)
	_refused(pos.deliver_order, t["order"])
	frappe.db.set_value("POS Order", t["order"], "nc", 0)
	pos.mark_nc(t["order"], "GM", "eval comp")
	assert pos.deliver_order(t["order"])["status"] == "Delivered"


@check("POS: a bill closes when posted to a checked-in room, or when nothing is left on it")
def t204():
	from kamra import pos
	outlet, dish = _eval_bill_outlet("Eval Room Close")
	res, guest = _in_house("Eval Room Close", "+91 70000 00204", "2037-02-11",
	                       "2037-02-12", _ledger_room("L204"))
	o = pos.create_order(outlet, [{"menu_item": dish, "qty": 1}], table_no="R1",
	                     order_type="Dine In")
	pos.charge_to_room(o["order"], res.room)
	assert pos.deliver_order(o["order"])["posted_to_folio"]
	assert frappe.get_all("Folio Charge", filters={
		"parent": guest, "description": ["like", f"%{o['order']}%"]})
	v = pos.create_order(outlet, [{"menu_item": dish, "qty": 1}], table_no="R2",
	                     order_type="Dine In")
	row = frappe.get_doc("POS Order", v["order"]).items[0].name
	pos.void_item(v["order"], row, "guest left before ordering")
	assert pos.deliver_order(v["order"])["status"] == "Delivered"
	# a paid bill must say how it was paid
	p = pos.create_order(outlet, [{"menu_item": dish, "qty": 1}], order_type="Takeaway")
	doc = frappe.get_doc("POS Order", p["order"])
	doc.paid, doc.status = 1, "Delivered"
	_refused(doc.save)
# --- night audit checklist, blocker acknowledgement, audit pack (t205-t214) ---

def _na_setting(key, value):
	import json as _json

	from kamra import settings
	name = frappe.db.get_value("Property Setting", {"property": P, "setting_key": key})
	if name:
		frappe.db.set_value("Property Setting", name, "value", _json.dumps(value))
	else:
		frappe.get_doc({"doctype": "Property Setting", "property": P,
		                "setting_key": key, "value": _json.dumps(value)}
		               ).insert(ignore_permissions=True)
	settings.clear_cache(P)


def _na_reset():
	from kamra import settings
	frappe.db.delete("Property Setting", {"property": P, "setting_key": ("like", "na_%")})
	settings.clear_cache(P)


def _na_till():
	from kamra import cashier
	return cashier.open_session(P, opening_float=100)["name"]


def _na_blockers():
	from kamra import night_audit
	return night_audit.night_audit_precheck(P)["blockers"]


@check("night audit checklist: every check reports a severity, count and action; tills, POS bills and departures block")
def t205():
	from kamra import night_audit
	_na_reset()
	frappe.db.set_value("Property", P, "business_date", nowdate())
	out = night_audit.night_audit_precheck(P)
	keys = [c["key"] for c in out["checks"]]
	assert keys == list(night_audit.ORDER), keys
	sev = {c["key"]: c["severity"] for c in out["checks"]}
	for k in ("open_tills", "open_pos_bills", "departures_due"):
		assert sev[k] == "block", (k, sev[k])
	assert sev["pos_room_postings"] in ("info", "warn")
	assert all(c["action"] and isinstance(c["count"], int) for c in out["checks"])
	assert out["can_run"] == (not out["blockers"])


@check("a manual night audit is refused with an open till until acknowledged with a reason")
def t206():
	from kamra import api
	_na_reset()
	_na_till()

	def run():
		blockers = _na_blockers()
		assert "open_tills" in blockers, blockers
		try:
			api.run_night_audit(P)
			raise AssertionError("ran with an open till")
		except frappe.ValidationError as e:
			assert "blocked" in str(e).lower(), e
		try:
			api.run_night_audit(P, acknowledge=blockers, note="")
			raise AssertionError("acknowledged without a reason")
		except frappe.ValidationError:
			pass
		return api.run_night_audit(P, acknowledge=blockers, note="Eval: counted in the morning")
	out = _audit_eval(nowdate(), f"{nowdate()} 23:00", run)
	assert "open_tills" in out["acknowledged"], out
	import json as _json
	acks = _json.loads(frappe.db.get_value("Night Audit Run", out["audit"], "acknowledgements"))
	row = next(a for a in acks if a["key"] == "open_tills")
	assert row["by"] == frappe.session.user and row["at"] and "counted" in row["note"], row


@check("a blocking check switched to warn no longer blocks")
def t207():
	from kamra import night_audit
	_na_reset()
	frappe.db.set_value("Property", P, "business_date", nowdate())
	_na_till()
	_na_setting("na_block_open_tills", 0)
	try:
		c = {x["key"]: x for x in night_audit.night_audit_precheck(P)["checks"]}["open_tills"]
		assert c["severity"] == "warn" and c["count"] >= 1, c
		assert "open_tills" not in _na_blockers()
	finally:
		_na_reset()


@check("scheduled audit on Hold and alert leaves the business date and writes an alert")
def t208():
	from unittest.mock import patch

	from kamra.folio import run_night_audit
	_na_reset()
	_na_till()
	_na_setting("na_auto_audit_with_blockers", "Hold and alert")
	try:
		with patch("kamra.night_audit.alert_staff") as alert:
			out = _audit_eval(nowdate(), f"{nowdate()} 03:00",
			                  lambda: run_night_audit(P, mode="scheduled"))
		assert out.get("held"), out
		assert str(frappe.db.get_value("Property", P, "business_date")) == nowdate()
		assert not frappe.db.exists("Night Audit Run", {"property": P,
		                            "business_date": nowdate(), "status": ("!=", "Draft")})
		assert frappe.db.exists("Agent Action Log", {"property": P,
		                        "action_type": "night_audit_held"})
		assert alert.called
	finally:
		_na_reset()


@check("scheduled audit by default runs and reports blockers as exceptions")
def t209():
	from kamra.folio import run_night_audit
	_na_reset()
	_na_till()
	out = _audit_eval(nowdate(), f"{nowdate()} 03:00",
	                  lambda: run_night_audit(P, mode="scheduled"))
	assert out.get("status") == "Completed with Warnings", out
	assert out["exceptions"] >= 1
	assert frappe.db.get_value("Night Audit Run", out["audit"], "run_trigger") == "Scheduled"


@check("every night audit run saves an audit pack with all its sections")
def t210():
	from kamra import night_audit
	from kamra.folio import run_night_audit
	_na_reset()
	out = _audit_eval(nowdate(), f"{nowdate()} 23:00", lambda: run_night_audit(P))
	assert out["has_pack"], out
	pack = night_audit.night_audit_pack(out["audit"])
	assert pack["has_pack"]
	p = pack["pack"]
	for key in ("manager_flash", "revenue_by_transaction_code", "ledger_balances",
	            "statistics", "in_house", "departures", "arrivals", "no_shows",
	            "high_balance", "credit_limit", "pos_room_postings",
	            "rate_variance", "cashier_sessions", "prechecks", "journal",
	            "deposit_ledger", "city_ledger", "cancellations"):
		assert key in p, key
	assert not p.get("errors"), p.get("errors")
	for k in ("occupancy_pct", "adr", "revpar"):
		assert k in p["statistics"], p["statistics"]


@check("a night audit run from before packs answers has_pack false, not an error")
def t211():
	from kamra import night_audit
	day = add_days(FAR, 40)
	frappe.db.delete("Night Audit Run", {"property": P, "business_date": day})
	name = frappe.get_doc({"doctype": "Night Audit Run", "property": P,
	                       "business_date": day, "status": "Completed"}
	                      ).insert(ignore_permissions=True).name
	out = night_audit.night_audit_pack(name)
	assert out["has_pack"] is False and out["pack"] is None, out
	assert out["message"] and out.get("can_rebuild") is True, out
	rebuilt = night_audit.rebuild_audit_pack(name)
	assert rebuilt["has_pack"] and rebuilt["pack"], rebuilt
	assert "manager_flash" in rebuilt["pack"]


@check("stuck business date after a completed audit can be advanced without re-posting")
def t211b():
	from kamra import night_audit
	from kamra.business_date import get_business_date
	from kamra.folio import run_night_audit
	_na_reset()
	bd = nowdate()
	frappe.db.set_value("Property", P, "business_date", bd)
	out = _audit_eval(bd, f"{bd} 23:00", lambda: run_night_audit(P))
	assert not out.get("already_ran"), out
	# simulate restore / roll that did not stick: BD back on the closed day
	frappe.db.set_value("Property", P, "business_date", bd)
	stuck = night_audit.stuck_business_date(P)
	assert stuck and stuck["audit"] == out["audit"], stuck
	again = run_night_audit(P)
	assert again.get("already_ran") is True
	assert get_business_date(P) == bd
	rec = night_audit.recover_stuck_business_date(P)
	assert rec["next_business_date"] == add_days(bd, 1), rec
	assert get_business_date(P) == add_days(bd, 1)
	assert night_audit.stuck_business_date(P) is None


@check("the checklist's no-show forecast matches what the audit does (OTA fee waived)")
def t212():
	from kamra import night_audit
	from kamra.folio import run_night_audit
	_na_reset()
	saved = frappe.db.get_value("Property", P, ["no_show_charge",
	                            "waive_no_show_fee_for_ota"], as_dict=True)
	frappe.db.set_value("Property", P, {"no_show_charge": "First Night",
	                                    "waive_no_show_fee_for_ota": 1,
	                                    "business_date": nowdate()})
	try:
		ota = _res(_guest("Eval NA OTA", "+91 70000 00212"), nowdate(),
		           add_days(nowdate(), 1))
		frappe.db.set_value("Reservation", ota.name, {"source": "OTA", "channel": "Agoda"})
		checks = {c["key"]: c for c in night_audit.night_audit_precheck(P)["checks"]}
		row = next(i for i in checks["arrivals_pending"]["items"]
		           if i["reservation"] == ota.name)
		assert (row["outcome"], row["fee"]) == ("no_show", "waived"), row
		_audit_eval(nowdate(), f"{nowdate()} 23:59", lambda: run_night_audit(P))
		assert frappe.db.get_value("Reservation", ota.name, "status") == "No Show"
	finally:
		frappe.db.set_value("Property", P, dict(saved))


@check("End of Day: a wizard acknowledgement and notes carry into the run; a draft is not a closed day")
def t213():
	from kamra import api, night_audit
	_na_reset()
	frappe.db.set_value("Property", P, "business_date", nowdate())
	frappe.db.delete("Night Audit Run", {"property": P, "business_date": nowdate()})
	_na_till()
	s = night_audit.eod_session(P)
	assert s["status"] == "Draft" and len(s["steps"]) == 12, s["steps"]
	assert not night_audit.night_audit_precheck(P)["already_ran"]
	for key in s["blockers"]:
		night_audit.eod_acknowledge(P, key, "Eval: acknowledged in the wizard")
	night_audit.eod_progress(P, step=9, notes="Eval notes for the GM")
	from datetime import datetime
	from unittest.mock import patch

	from kamra import folio
	with patch.object(folio, "audit_clock",
	                  return_value=datetime.strptime(f"{nowdate()} 23:00", "%Y-%m-%d %H:%M")):
		out = api.run_night_audit(P)
	assert out["audit"] == s["audit"], out
	assert frappe.db.get_value("Night Audit Run", out["audit"], "auditor_notes") == "Eval notes for the GM"
	pack = night_audit.night_audit_pack(out["audit"])["pack"]
	assert pack["notes"] == "Eval notes for the GM"


@check("Night Auditor role reaches End of Day; MCP night_audit_precheck is read-only in Night audit")
def t214():
	from kamra import api, cashier, ledger, night_audit
	from kamra.mcp_tools import BY_NAME
	for fn in (api.run_night_audit, night_audit.night_audit_precheck,
	           night_audit.eod_session, night_audit.eod_acknowledge,
	           night_audit.night_audit_pack, night_audit.rebuild_audit_pack,
	           night_audit.recover_stuck_business_date,
	           api.check_in, api.check_out,
	           ledger.quick_checkout, cashier.close_session, api.get_folio):
		assert "Night Auditor" in fn._kamra_roles, fn.__name__
	assert frappe.db.exists("Role", "Night Auditor")
	spec = BY_NAME["night_audit_precheck"]
	assert spec.group == "Night audit" and not spec.mutating and spec.inject_property
	assert "acknowledge" in BY_NAME["run_night_audit"].parameters
	assert BY_NAME["rebuild_audit_pack"].mutating
	assert BY_NAME["recover_stuck_business_date"].mutating


@check("extra beds agreed at the desk bill as their own line, at the night's slab, as accommodation, and to the company billed for the room")
def t215():
	"""Extra beds agreed at the desk bill as their own line, and that line
	behaves like accommodation everywhere it lands.

	Splitting it out of the room rate is a presentation change the guest
	asked for, but it must not quietly change the tax, the company's share
	or what the invoice calls it - all three read the charge type."""
	from kamra import api
	from kamra.folio import COMPANY_BILLING_DEFAULTS, post_room_night
	from kamra.ledger import (
		CHARGE_TYPE_TO_CODE,
		ensure_default_transaction_codes,
	)
	from kamra.localization.india import service_code_for
	from kamra.pricing import quote

	rt = frappe.get_doc({
		"doctype": "Room Type", "property": P, "room_type_code": "XBED",
		"room_type_name": "Eval Extra Bed", "base_price": 7000,
		"base_occupancy": 2, "extra_adult_price": 0,
		"adults_capacity": 2, "children_capacity": 0, "max_extra_beds": 3,
	}).insert(ignore_permissions=True)

	# the slab reads the whole night's tariff: 7,000 alone is the lower
	# slab, but 7,000 with 2,000 of agreed beds is a 9,000 night
	plain = quote(P, rt.name, "2031-08-01", "2031-08-03", 2, 0)
	assert plain["line_items"][0]["tax_rate"] == 5, plain["line_items"][0]

	q = quote(P, rt.name, "2031-08-01", "2031-08-03", 2, 0,
	          over_capacity_charge=2000)
	rooms = next(li for li in q["line_items"] if li["component"] == "accommodation")
	beds = next(li for li in q["line_items"] if li["component"] == "over_capacity")
	assert rooms["tax_rate"] == 18, rooms
	assert beds["tax_rate"] == 18, beds
	assert q["room_total"] == 14000, q["room_total"]
	assert q["over_capacity_total"] == 4000, q["over_capacity_total"]
	assert q["amount_before_tax"] == 18000, q["amount_before_tax"]
	assert round(q["tax_amount"], 2) == 3240, q["tax_amount"]

	g = _guest("Eval Extra Bed", "+91 70000 00099")
	r = frappe.get_doc({
		"doctype": "Reservation", "property": P, "guest": g,
		"room_type": rt.name, "check_in_date": "2031-08-01",
		"check_out_date": "2031-08-03", "adults": 2, "auto_price": 1,
		"over_capacity_reason": "two cots in the lounge",
		"over_capacity_guests": 2, "over_capacity_charge": 2000,
	}).insert(ignore_permissions=True)
	assert float(r.amount_before_tax) == 18000, r.amount_before_tax
	assert round(float(r.tax_amount), 2) == 3240, r.tax_amount

	folio = frappe.get_doc({"doctype": "Folio", "property": P,
	                        "reservation": r.name, "guest": g})
	folio.insert(ignore_permissions=True)
	# a sundry the desk typed as Misc the same day: dedupe is by charge type
	# and date, so billing the beds as Misc made this suppress them
	api.add_folio_charge(folio.name, "Misc", "eval sundry", 250)
	for i in range(2):
		post_room_night(r, add_days("2031-08-01", i))

	folio.reload()
	beds_lines = [c for c in folio.charges if c.charge_type == "Extra Guests"]
	assert len(beds_lines) == 2, [c.charge_type for c in folio.charges]
	assert all(float(c.amount) == 2000 for c in beds_lines), beds_lines
	assert all(float(c.gst_rate) == 18 for c in beds_lines), \
		"the folio must tax the beds at the slab the quote used"
	assert len([c for c in folio.charges if c.charge_type == "Misc"]) == 1, \
		"a hand-typed Misc must survive, and must not suppress the beds"
	# the room rate itself stays clean - the guest sees two numbers
	room_lines = [c for c in folio.charges if c.charge_type == "Room"]
	assert all(float(c.amount) == 7000 for c in room_lines), room_lines

	# accommodation on the invoice, not "other services n.e.c."
	prop = frappe.get_doc("Property", P)
	assert (service_code_for(prop, "Extra Guests")["value"]
	        == service_code_for(prop, "Room")["value"] == "996311")
	# and a company billed for the room is billed for the beds on it
	assert "Extra Guests" in COMPANY_BILLING_DEFAULTS["Room only"]

	# Every charge type the ledger knows has to be spellable on both doctypes
	# that store one. Transaction Code keeps its own Select, so a charge type
	# added to Folio Charge alone passes every test that never seeds the
	# ledger, then fails the first time a site seeds its codes - which is a
	# fresh install, not a dev machine that already has them.
	ensure_default_transaction_codes()
	for doctype in ("Folio Charge", "Transaction Code"):
		allowed = set(
			frappe.get_meta(doctype).get_field("charge_type").options.split("\n"))
		missing = sorted(set(CHARGE_TYPE_TO_CODE) - allowed)
		assert not missing, f"{doctype} cannot store: {missing}"
	code = frappe.get_doc("Transaction Code", "1320")
	assert code.charge_type == "Extra Guests", code.charge_type


@check("pets: own quote line at room GST, refused when not allowed, posted once")
def t216():
	from kamra import api
	from kamra.folio import open_folio
	from kamra.ledger import CHARGE_TYPE_TO_CODE
	from kamra.pricing import quote

	def set_pets(**v):
		frappe.db.set_value("Property", P, v)
		frappe.clear_document_cache("Property", P)

	# a property that doesn't take pets refuses them rather than ignoring them
	set_pets(pets_allowed=0, pet_charge=1000, pet_charge_basis="Per stay")
	try:
		quote(P, RT, "2030-02-01", "2030-02-03", 2, 0, pets=1)
		raise AssertionError("pets quoted at a property that does not allow them")
	except frappe.ValidationError:
		pass

	set_pets(pets_allowed=1)
	none = quote(P, RT, "2030-02-01", "2030-02-03", 2, 0)
	q = quote(P, RT, "2030-02-01", "2030-02-03", 2, 0, pets=2)
	# per stay: 2 pets x 1,000 once, not per night
	assert q["pet_charge"] == 2000, q["pet_charge"]
	assert q["room_total"] == none["room_total"], "pets changed the room rate"
	line = next(li for li in q["line_items"] if li["component"] == "pet_charge")
	room = next(li for li in q["line_items"] if li["component"] == "accommodation")
	assert abs(line["tax_amount"] - 2000 * room["tax_rate"] / 100) < 0.01, (line, room)
	assert abs(q["amount_after_tax"] - none["amount_after_tax"]
	           - 2000 - line["tax_amount"]) < 0.01

	set_pets(pet_charge_basis="Per night")
	assert quote(P, RT, "2030-02-01", "2030-02-03", 2, 0, pets=1)["pet_charge"] == 2000

	# the booking carries it to the folio once, at the quoted amount
	set_pets(pet_charge_basis="Per stay")
	out = api.create_booking(
		property=P, room_type=RT, check_in_date="2031-03-10",
		check_out_date="2031-03-12", guest_name="Eval Pets",
		phone="+91 70000 00187", pets=2)
	res = frappe.get_doc("Reservation", out["reservation"])
	assert res.pets == 2
	assert abs(res.amount_after_tax - q["amount_after_tax"]) < 0.01, (
		res.amount_after_tax, q["amount_after_tax"])
	api.check_in(res.name)
	open_folio(frappe.get_doc("Reservation", res.name))  # reopening must not re-post
	folio = frappe.get_doc("Folio", frappe.db.get_value(
		"Folio", {"reservation": res.name, "folio_type": "Guest"}))
	pet_lines = [c for c in folio.charges if c.charge_type == "Pet Charge"]
	assert len(pet_lines) == 1, len(pet_lines)
	assert pet_lines[0].amount == 2000, pet_lines[0].amount
	assert abs(pet_lines[0].gst_rate - room["tax_rate"]) < 0.01, pet_lines[0].gst_rate

	# every ledger charge type must be storable on BOTH doctypes - a fresh
	# site seeds Transaction Codes lazily, so a missing option only shows in CI
	for dt in ("Folio Charge", "Transaction Code"):
		opts = frappe.get_meta(dt).get_field("charge_type").options.split("\n")
		missing = [ct for ct in CHARGE_TYPE_TO_CODE if ct not in opts]
		assert not missing, f"{dt} cannot store: {missing}"
	set_pets(pets_allowed=0, pet_charge=0)


def _t300_rooms(code):
	"""An isolated two-room type on the eval property for the 30x checks."""
	rt = frappe.get_doc({
		"doctype": "Room Type", "property": P, "room_type_code": code,
		"room_type_name": f"Eval {code}", "base_price": 4000,
		"base_occupancy": 2, "adults_capacity": 3, "children_capacity": 1,
		"tax_percent": 5,
	}).insert(ignore_permissions=True)
	rooms = [frappe.get_doc({
		"doctype": "Room", "property": P, "room_number": f"{code}{n}",
		"room_type": rt.name, "housekeeping_status": "Clean",
	}).insert(ignore_permissions=True).name for n in (1, 2)]
	return rt.name, rooms


def _t300_in_house(rt, room, guest_name, phone):
	"""A guest checked in yesterday, departing today, still in the room."""
	g = _guest(guest_name, phone)
	res = frappe.get_doc({
		"doctype": "Reservation", "property": P, "guest": g,
		"room_type": rt, "room": room,
		"check_in_date": add_days(nowdate(), -1), "check_out_date": nowdate(),
		"adults": 2, "auto_price": 1,
	})
	res.flags.allow_past_check_in = True
	res.insert(ignore_permissions=True)
	res.status = "Checked In"
	res.save(ignore_permissions=True)
	return res


@check("departure day: a room whose guest is still checked in is not offered for a check-in today, but stays bookable")
def t300():
	from kamra import api
	from kamra.allocation import suggest_allocation
	rt, (busy, free) = _t300_rooms("T3A")
	_t300_in_house(rt, busy, "Eval Departing", "+91 70000 30001")
	today, tomorrow = nowdate(), add_days(nowdate(), 1)
	now = {r["name"] for r in api.available_rooms(
		P, rt, today, tomorrow, ready_now=1)}
	assert now == {free}, now
	# a booking for tonight may still take it - the guest leaves today
	booking = {r["name"] for r in api.available_rooms(P, rt, today, tomorrow)}
	assert booking == {busy, free}, booking
	# and a stay from tomorrow is untouched either way
	later = {r["name"] for r in api.available_rooms(
		P, rt, tomorrow, add_days(tomorrow, 1), ready_now=1)}
	assert later == {busy, free}, later
	# the allocator never proposes the occupied room for today's arrival
	arr = _guest("Eval Arriving", "+91 70000 30002")
	a = frappe.get_doc({
		"doctype": "Reservation", "property": P, "guest": arr,
		"room_type": rt, "check_in_date": today, "check_out_date": tomorrow,
		"adults": 2, "auto_price": 1,
	}).insert(ignore_permissions=True)
	props = [p_ for p_ in suggest_allocation(P, today)["proposals"]
	         if p_["reservation"] == a.name]
	assert props and props[0]["suggested_room"] == free, props
	ctx = api.checkin_context(a.name)
	assert {r["name"] for r in ctx["rooms"]} == {free}, ctx["rooms"]
	# when the only free room is the occupied one, nothing is offered
	frappe.db.set_value("Room", free, "housekeeping_status", "Out of Order")
	props = [p_ for p_ in suggest_allocation(P, today)["proposals"]
	         if p_["reservation"] == a.name]
	assert not props, props


@check("check-in into a room whose guest has not checked out is refused; it goes through once they leave")
def t301():
	from kamra import api
	from kamra.kamra.doctype.reservation.reservation import InventoryRefused
	rt, (busy, _free) = _t300_rooms("T3B")
	first = _t300_in_house(rt, busy, "Eval Still In", "+91 70000 30011")
	g = _guest("Eval Next", "+91 70000 30012")
	nxt = frappe.get_doc({
		"doctype": "Reservation", "property": P, "guest": g,
		"room_type": rt, "room": busy, "check_in_date": nowdate(),
		"check_out_date": add_days(nowdate(), 1), "adults": 2,
		"auto_price": 1,
	}).insert(ignore_permissions=True)  # back-to-back booking is fine
	try:
		api.check_in(nxt.name)
		raise AssertionError("second guest checked into an occupied room")
	except InventoryRefused as e:
		assert "still occupied" in str(e), e
	assert frappe.db.get_value("Reservation", nxt.name, "status") == "Confirmed"
	frappe.flags.allow_unsettled_checkout = True
	try:
		api.check_out(first.name)
	finally:
		frappe.flags.allow_unsettled_checkout = False
	assert api.check_in(nxt.name)["room"] == busy
	# re-saving the in-house stay is not a second check-in
	doc = frappe.get_doc("Reservation", nxt.name)
	doc.special_requests = "late check-out please"
	doc.save(ignore_permissions=True)


@check("walk-in into a room whose guest departs today but is still in is refused")
def t302():
	from kamra import api
	from kamra.kamra.doctype.reservation.reservation import InventoryRefused
	rt, (busy, free) = _t300_rooms("T3C")
	_t300_in_house(rt, busy, "Eval Sneha", "+91 70000 30021")
	try:
		api.walk_in(P, rt, busy, add_days(nowdate(), 1), "Eval Walker",
		            phone="+91 70000 30022")
		raise AssertionError("walk-in was put in an occupied room")
	except InventoryRefused:
		pass
	out = api.walk_in(P, rt, free, add_days(nowdate(), 1), "Eval Walker Two",
	                  phone="+91 70000 30023")
	assert out["room"] == free, out


@check("quote cancellation terms are judged from today: a closed window never shows a past date")
def t303():
	from kamra import api
	frappe.db.set_value("Property", P, {"free_cancel_days": 2,
	                                    "cancellation_fee": "First Night"})
	frappe.db.delete("Cancellation Tier", {"parenttype": "Property",
	                                       "parent": P})
	today = nowdate()
	c = api.cancellation_outlook(P, RT, today, add_days(today, 1))
	assert c["free_now"] is False and c["free_until"] is None, c
	assert c["fee_label"] == "the first night", c
	ci = add_days(today, 10)
	c = api.cancellation_outlook(P, RT, ci, add_days(ci, 1))
	assert c["free_now"] and c["free_until"] == str(add_days(ci, -2)), c
	assert c["free_until"] >= today
	# the last free day is exactly where cancellation_preview stops charging
	g = _guest("Eval Cxl", "+91 70000 30031")
	res = _res(g, ci, add_days(ci, 1))
	assert api.cancellation_preview(res.name)["inside_window"] is False
	q = api.get_quote(P, RT, today, add_days(today, 1))
	assert q["cancellation"]["free_now"] is False, q.get("cancellation")
	frappe.db.set_value("Property", P, "cancellation_fee", "None")
	c = api.cancellation_outlook(P, RT, today, add_days(today, 1))
	assert c["free_now"] and c["free_until"] is None, c


@check("guest journey names the person who acted, never 'None'")
def t304():
	from kamra import api
	from kamra.savings import log_action
	g = _guest("Eval Journey", "+91 70000 30041")
	res = _res(g, add_days(nowdate(), 3), add_days(nowdate(), 4))
	log_action("check_in", "Reservation", res.name, P, rationale="eval")
	j = api.guest_journey(g)
	titles = [e["title"] for e in j["timeline"] if e["type"] == "agent"]
	assert titles, j["timeline"]
	assert not any(t_.startswith("None") for t_ in titles), titles
	assert any(t_.endswith("· Check in") for t_ in titles), titles


@check("a departure's balance counts the nights night audit has not posted, as check-out does, and keeps nothing")
def t305():
	from kamra import api
	rt, (room, _r2) = _t300_rooms("T3D")
	res = _t300_in_house(rt, room, "Eval Owes", "+91 70000 30051")
	folio = frappe.db.get_value("Folio", {"reservation": res.name,
	                                      "folio_type": "Guest"})
	charges_before = frappe.db.count("Folio Charge", {"parent": folio})
	posted = float(frappe.db.get_value("Folio", folio, "balance") or 0)
	log_before = list(getattr(frappe.local, "_realtime_log", []) or [])
	due = api._stay_balance(res.name)["due"]
	assert due > posted, (due, posted)
	# the projection is a read: no charge, balance or realtime ping is kept
	assert float(frappe.db.get_value("Folio", folio, "balance") or 0) == posted
	assert frappe.db.count("Folio Charge", {"parent": folio}) == charges_before
	assert list(getattr(frappe.local, "_realtime_log", []) or []) == log_before
	snap = api.front_desk_snapshot(P)
	dep = [r for r in snap["departures"] if r["name"] == res.name]
	assert dep and dep[0]["balance_due"] == due, dep
	try:
		api.check_out(res.name)
		raise AssertionError("check-out let an unpaid guest leave")
	except frappe.ValidationError as e:
		assert f"{due:,.2f}" in str(e), (due, str(e))


# --- billing / cashier / end-of-day / reports fixes (t320-t328) ---------------

@check("cashier: reading the till writes nothing (no 1020 race on load); a drifted total is refreshed")
def t320():
	from kamra import cashier
	frappe.db.set_value("Property", P, "business_date", nowdate())
	sess = _na_till()
	m0 = frappe.db.get_value("Cashier Session", sess, "modified")
	out = cashier.current_session(P)
	assert out["open"] and out["name"] == sess, out
	assert frappe.db.get_value("Cashier Session", sess, "modified") == m0, \
		"current_session rewrote an unchanged till"
	true_expected = float(out["totals"]["expected_cash"])
	frappe.db.set_value("Cashier Session", sess, "expected_cash", true_expected + 7,
	                    update_modified=False)
	cashier.current_session(P)
	got = float(frappe.db.get_value("Cashier Session", sess, "expected_cash"))
	assert abs(got - true_expected) < 0.01, (got, true_expected)


@check("End of Day: a lost create race is recognised and the wizard reuses one draft")
def t321():
	from kamra import night_audit
	assert night_audit._lost_create_race(frappe.QueryDeadlockError("1020"))
	assert night_audit._lost_create_race(frappe.DuplicateEntryError("Night Audit Run", "x"))
	assert not night_audit._lost_create_race(frappe.ValidationError("x"))
	frappe.db.set_value("Property", P, "business_date", nowdate())
	a = night_audit.eod_session(P)
	b = night_audit.eod_session(P)
	if not a["ran"]:
		assert a["audit"] == b["audit"], (a["audit"], b["audit"])
		assert frappe.db.count("Night Audit Run", {
			"property": P, "business_date": a["business_date"],
			"status": "Draft"}) == 1


@check("folio: a food & beverage charge carries the pack's F&B rate whatever is picked; the locale says so")
def t322():
	from kamra import api
	res, folio = _in_house("Eval Minibar Rate", "+91 70000 00320", "2037-01-05",
	                       "2037-01-07", _ledger_room("L320"))
	loc = api.property_locale(P)
	assert "minibar" in loc["fnb_charge_words"], loc["fnb_charge_words"]
	fnb = float(loc["fnb_tax_rate"])
	api.add_folio_charge(folio, "Minibar", "Minibar", 500, gst_rate=18)
	api.add_folio_charge(folio, "Spa", "Massage", 1000, gst_rate=18)
	rows = frappe.get_doc("Folio", folio).charges
	mini = [c for c in rows if c.charge_type == "Minibar"][-1]
	spa = [c for c in rows if c.charge_type == "Spa"][-1]
	assert abs(float(mini.gst_rate) - fnb) < 0.001, (mini.gst_rate, fnb)
	assert abs(float(spa.gst_rate) - 18) < 0.001, spa.gst_rate


@check("cashier PIN: the unlock status reports the property's own unlock window")
def t323():
	from kamra.authz import cashier_unlock_status
	_na_setting("pin_lock_minutes", 7)
	try:
		assert cashier_unlock_status(P)["unlock_minutes"] == 7
	finally:
		frappe.db.delete("Property Setting", {"property": P, "setting_key": "pin_lock_minutes"})
		from kamra import settings
		settings.clear_cache(P)


@check("portfolio: money rounds half up once per property; the tiles are the sum of the rows")
def t324():
	from kamra.dashboards import _whole, portfolio_dashboard
	assert _whole(11792.5) == 11793 and _whole(0.5) == 1 and _whole(2.49) == 2
	out = portfolio_dashboard()
	for key in ("collections_today", "revenue_today", "outstanding"):
		rows = [r[key] for r in out["properties"]]
		assert all(float(v).is_integer() for v in rows), (key, rows)
		assert out["totals"][key] == sum(rows), (key, out["totals"][key], sum(rows))


@check("ledgers: an open folio's balance is not an imbalance; a folio the ledger disagrees with is")
def t325():
	from kamra import api
	from kamra.business_date import get_business_date
	from kamra.ledger import folio_reconciliation, ledger_balances
	res, folio = _in_house("Eval Ledger Recon", "+91 70000 00325", "2037-01-10",
	                       "2037-01-12", _ledger_room("L325"))
	api.add_folio_charge(folio, "Misc", "eval recon", 1000, gst_rate=0)
	_assert_folio_on_ledger(folio)
	tb = ledger_balances(P)
	assert tb["total_debit"] > tb["total_credit"], "guest owes, so debits lead"
	recon = tb["reconciliation"]
	assert tb["in_balance"] == (recon["folios_out"] == 0), tb["in_balance"]
	assert folio not in {f["folio"] for f in folio_reconciliation(P, limit=10000)["folios"]}
	bal = float(frappe.db.get_value("Folio", folio, "balance"))
	frappe.db.set_value("Folio", folio, "balance", bal + 250)
	r2 = folio_reconciliation(P, limit=10000)
	hit = next((f for f in r2["folios"] if f["folio"] == folio), None)
	assert hit and abs(hit["difference"] - 250) < 0.01, hit
	assert ledger_balances(P)["in_balance"] is False
	assert ledger_balances(P, add_days(get_business_date(P), -1))["in_balance"] is None
	frappe.db.set_value("Folio", folio, "balance", bal)


@check("accounting export: each invoice line keeps its own service code, amounts conserved")
def t326():
	from kamra import api
	from kamra.accounting import _lines_by_code, export_invoices
	from kamra.localization import pack_for
	res, folio = _in_house("Eval Export Codes", "+91 70000 00326", "2037-01-14",
	                       "2037-01-16", _ledger_room("L326"))
	api.add_folio_charge(folio, "Laundry", "Laundry bag", 300, gst_rate=18)
	api.add_folio_charge(folio, "Food & Beverage", "Dinner", 1000, gst_rate=5)
	api.add_folio_charge(folio, "Spa", "Massage", 2000, gst_rate=18)
	inv = api.folio_invoice(folio)
	ctx = pack_for(P).invoice_context(frappe.get_cached_doc("Property", P))
	comps = [c for c, _ in ctx["split"]]
	ratios = {c: float(r) for c, r in ctx["split"]}
	lines = _lines_by_code(inv, comps, ratios)
	line_codes = {ln["service_code"] or "" for ln in inv["lines"]}
	assert {g["service_code"] for g in lines} == line_codes, (lines, line_codes)
	if len(line_codes - {""}) > 1:
		assert len({g["service_code"] for g in lines} - {""}) > 1, "codes collapsed"
	charges = frappe.get_doc("Folio", folio).charges
	assert abs(sum(g["taxable"] for g in lines) - sum(float(c.amount) for c in charges)) < 0.02
	assert abs(sum(g["total_tax"] for g in lines) - sum(float(c.gst_amount) for c in charges)) < 0.02
	out = export_invoices(P, "2000-01-01", "2099-12-31")
	assert all("lines" in r for r in out["rows"])


@check("End of Day: Manage and the wizard count open POS bills from the same check")
def t327():
	from kamra import night_audit
	from kamra.business_date import get_business_date
	frappe.db.set_value("Property", P, "business_date", nowdate())
	row = next(r for r in night_audit.eod_overview() if r["property"] == P)
	live = {c["key"]: c for c in night_audit.run_checks(P, get_business_date(P))}
	assert row["open_pos_bills"] == live["open_pos_bills"]["count"]
	st = night_audit.eod_session(P)
	if not st["ran"]:
		wiz = {c["key"]: c for c in st["checks"]}
		assert wiz["open_pos_bills"]["count"] == row["open_pos_bills"]


@check("voids & allowances report lists an allowance with its folio and reason")
def t328():
	from kamra import api
	from kamra.reports import void_allowance_report
	res, folio = _in_house("Eval Void Report", "+91 70000 00328", "2037-01-18",
	                       "2037-01-20", _ledger_room("L328"))
	api.add_folio_charge(folio, "Misc", "eval void report", 500, gst_rate=0)
	api.post_allowance(folio, 100, "eval void report reason")
	rows = void_allowance_report(P, nowdate(), nowdate())
	assert any(r["folio"] == folio and r["action"] == "Allowance" for r in rows), rows[:3]


def _as_user(user):
	"""Run a block as `user`, always returning to Administrator."""
	from contextlib import contextmanager

	@contextmanager
	def cm():
		frappe.set_user(user)  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow
		try:
			yield
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow
	return cm()


def _hk_task(task_type="Checkout Clean", **kw):
	return frappe.get_doc({
		"doctype": "Housekeeping Task", "property": P, "room": ROOM,
		"task_type": task_type, "priority": "High", "status": "Pending", **kw,
	}).insert(ignore_permissions=True).name


@check("housekeeping: an inspection passes as Verified (Inspected / Ready), never back to Clean; only a supervisor passes it")
def t310():
	from kamra import api
	from kamra.turnover import ensure_default_profile

	# hotel default: no inspection required -> a passed inspection = Inspected
	frappe.db.set_value("Room", ROOM, "housekeeping_status", "Clean")
	insp = _hk_task("Inspection")
	# the attendant cannot pass it
	with _as_user("hk@kamra.local"):
		try:
			api.hk_update_task(insp, "Done")
			raise AssertionError("an attendant passed an inspection")
		except frappe.PermissionError:
			pass
	assert frappe.db.get_value("Housekeeping Task", insp, "status") == "Pending"
	out = api.hk_update_task(insp, "Done")  # Done on an inspection = Verified
	assert out["status"] == "Verified", out
	assert frappe.db.get_value("Room", ROOM, "housekeeping_status") == "Inspected"

	# inspection required by the turnover profile -> passing it = Ready
	name = ensure_default_profile(P)
	frappe.db.set_value("Turnover Profile", name, "requires_inspection", 1)
	frappe.clear_document_cache("Turnover Profile", name)
	frappe.db.set_value("Room", ROOM, "housekeeping_status", "Dirty")
	clean = _hk_task("Checkout Clean")
	with _as_user("hk@kamra.local"):
		api.hk_update_task(clean, "Done")  # an attendant still finishes cleans
	assert frappe.db.get_value("Room", ROOM, "housekeeping_status") == "Clean"
	spawned = frappe.get_all("Housekeeping Task", filters={
		"room": ROOM, "task_type": "Inspection", "status": "Pending"}, pluck="name")
	assert spawned, "no inspection spawned after the checkout clean"
	api.hk_update_task(spawned[0], "Verified")
	assert frappe.db.get_value("Room", ROOM, "housekeeping_status") == "Ready"

	# an inspection closed as Done from the desk form never downgrades the room
	other = _hk_task("Inspection")
	d = frappe.get_doc("Housekeeping Task", other)
	d.status = "Done"
	d.save(ignore_permissions=True)
	assert frappe.db.get_value("Room", ROOM, "housekeeping_status") == "Ready"
	frappe.db.set_value("Turnover Profile", name, "requires_inspection", 0)
	frappe.clear_document_cache("Turnover Profile", name)


@check("housekeeping: only a supervisor assigns, and only to housekeeping staff of the property")
def t311():
	from kamra import api
	staff = [s["user"] for s in api.hk_staff(P)]
	assert "hk@kamra.local" in staff, staff
	assert "frontdesk@kamra.local" not in staff, staff
	task = _hk_task()
	with _as_user("hk@kamra.local"):
		try:
			api.hk_assign_task(task, "hk@kamra.local")
			raise AssertionError("an attendant assigned a task")
		except frappe.PermissionError:
			pass
	try:
		api.hk_assign_task(task, "frontdesk@kamra.local")
		raise AssertionError("assigned a task to someone who is not housekeeping")
	except frappe.ValidationError:
		pass
	out = api.hk_assign_task(task, "hk@kamra.local")
	assert out["assigned_to_user"] == "hk@kamra.local", out
	with _as_user("hk@kamra.local"):
		row = next(t for t in api.hk_queue(P)["tasks"] if t["name"] == task)
		assert row["mine"] and row["assignment_status"] == "Assigned", row


@check("settings: turnover page shows only knobs code acts on, with the doctype's defaults")
def t312():
	from kamra.settings import SETTINGS
	for key in ("clean_duration_minutes", "buffer_after_ready_minutes",
	            "same_day_turn_allowed"):
		assert key not in SETTINGS, f"{key} is offered but nothing reads it"
	meta = frappe.get_meta("Turnover Profile")
	for key in ("requires_inspection", "inspect_duration_minutes"):
		reg = SETTINGS[key][1].default
		doc_default = meta.get_field(key).default
		assert str(reg) == str(doc_default), (key, reg, doc_default)
	# a hotel's auto-created profile matches the doctype defaults
	from kamra.turnover import ensure_default_profile
	tp = frappe.get_doc("Turnover Profile", ensure_default_profile(P))
	for key in ("clean_duration_minutes", "inspect_duration_minutes",
	            "buffer_after_ready_minutes", "same_day_turn_allowed"):
		assert str(tp.get(key)) == str(meta.get_field(key).default), (
			key, tp.get(key), meta.get_field(key).default)


@check("SLA report: Resolved counts Resolved + Closed the same way in the headline and every breakdown")
def t313():
	from kamra.api import create_ticket
	from kamra.reports import sla_report
	today = frappe.utils.nowdate()
	a = create_ticket(P, "eval sla resolved", "Maintenance", "High")
	b = create_ticket(P, "eval sla closed", "Maintenance", "High")
	create_ticket(P, "eval sla open", "Maintenance", "High")
	for name, status in ((a["ticket"], "Resolved"), (b["ticket"], "Closed")):
		d = frappe.get_doc("Service Ticket", name)
		d.status = status
		d.save(ignore_permissions=True)
	r = sla_report(P, today, today)
	assert sum(c["resolved"] for c in r["by_category"]) == r["resolved"], r
	assert sum(c["resolved"] for c in r["by_priority"]) == r["resolved"], r
	cat = next(c for c in r["by_category"] if c["label"] == "Maintenance")
	assert cat["resolved"] >= 2, cat


@check("HK escalation alert names who was actually notified")
def t314():
	from kamra import housekeeping
	task = frappe._dict(name=_hk_task(), property=P, room=ROOM,
	                    task_type="Checkout Clean", priority="High")
	from unittest.mock import patch
	told = []
	with patch("kamra.housekeeping._notify_role",
	           lambda prop, role, body: told.append((role, body))):
		housekeeping._escalate(task, 1, 12)
		housekeeping._escalate(task, 2, 60)
	assert told[0][0] == "Front Desk" and "front desk" in told[0][1], told
	assert told[1][0] == "Hotel Admin" and "hotel admin" in told[1][1], told
	assert "supervisor" not in told[0][1] and "manager" not in told[1][1], told


@check("copilot raise_ticket files an AI Agent ticket, like MCP create_ticket")
def t315():
	from kamra.assistant import _run_tool
	out = _run_tool("raise_ticket", {
		"subject": "eval copilot towels", "category": "Housekeeping",
		"priority": "Low", "source": "Manual"}, P)
	name = out["ticket"]
	assert frappe.db.get_value("Service Ticket", name, "source") == "AI Agent", name


@check("laundry & HK charges: services tax from the country pack, currency from the property")
def t316():
	from kamra.localization import money_text, pack_for_country, services_tax_rate
	# India keeps 18% GST on services; every pack's services rate is one it allows
	assert services_tax_rate(pack_for_country("India"), P) == 18.0
	for country in ("India", "Saudi Arabia", "United Arab Emirates", "Malaysia",
	                "Thailand", "Indonesia", "Brazil"):
		# no property: the pack's statutory default (P is an Indian hotel
		# whose 5% room types would otherwise steer the VAT packs)
		pack = pack_for_country(country)
		rate = services_tax_rate(pack, None)
		assert rate in [float(x) for x in pack.tax_rate_options(None)], (country, rate)
	assert services_tax_rate(pack_for_country("Saudi Arabia"), None) == 15.0
	assert services_tax_rate(pack_for_country("Malaysia"), None) == 8.0
	from kamra import laundry
	assert not hasattr(laundry, "LAUNDRY_GST"), "laundry still hardcodes a GST rate"
	# activity-log money follows the property's currency, not a fixed rupee
	cur = frappe.db.get_value("Property", P, "currency")
	frappe.db.set_value("Property", P, "currency", "USD")
	frappe.db.set_value("Property", P, "country", "United States")
	frappe.clear_document_cache("Property", P)
	try:
		txt = money_text(P, 1250)
		assert "₹" not in txt and "1,250" in txt, txt
	finally:
		frappe.db.set_value("Property", P, {"currency": cur, "country": "India"})
		frappe.clear_document_cache("Property", P)


@check("stay instructions: desk adds, housekeeping reads and marks done, attendants can't add")
def t317():
	from kamra import api
	g = _guest("Eval Instr", "+91 70000 00317")
	res = _res(g, "2031-09-01", "2031-09-03").name
	rows = api.add_stay_instruction(res, "Housekeeping", "Extra pillows, no feathers")
	assert len(rows) == 1 and rows[0]["status"] == "Open", rows
	api.add_stay_instruction(res, "Front Desk", "Wake-up call 6am")
	with _as_user("hk@kamra.local"):
		try:
			api.add_stay_instruction(res, "Housekeeping", "nope")
			raise AssertionError("an attendant added an instruction")
		except frappe.PermissionError:
			pass
		rows = api.stay_instructions(res)
		assert len(rows) == 2 and rows[0]["department"] == "Housekeeping", rows
		out = api.set_stay_instruction_status(res, rows[0]["name"], "Done")
		done = next(r for r in out if r["name"] == rows[0]["name"])
		assert done["status"] == "Done" and done["done_by"] == "hk@kamra.local", done
	try:
		api.add_stay_instruction(res, "Spa", "x")
		raise AssertionError("unknown department accepted")
	except frappe.ValidationError:
		pass
	# the booking itself still loads with both rows in its table
	doc = frappe.get_doc("Reservation", res)
	assert len(doc.instructions) == 2, doc.instructions


@check("OTA mapping: a room type of another property is refused")
def t318():
	other = frappe.get_doc({
		"doctype": "Property", "property_name": "Eval Other Mapping Hotel",
		"city": "Elsewhere"}).insert(ignore_permissions=True).name
	rt2 = frappe.get_doc({
		"doctype": "Room Type", "property": other, "room_type_code": "EOM",
		"room_type_name": "Other Mapping Room", "base_price": 3000,
		"base_occupancy": 2}).insert(ignore_permissions=True).name
	conn = frappe.get_doc({
		"doctype": "Channel Manager Connection", "property": P,
		"provider": "Channex", "active": 0, "api_key": "eval-key-318",
		"external_property_id": "chx-prop-318",
	}).insert(ignore_permissions=True).name
	try:
		frappe.get_doc({
			"doctype": "Channel Room Mapping", "connection": conn,
			"room_type": rt2, "external_room_id": "x-318",
		}).insert(ignore_permissions=True)
		raise AssertionError("mapped another property's room type")
	except frappe.ValidationError:
		pass
	frappe.get_doc({
		"doctype": "Channel Room Mapping", "connection": conn,
		"room_type": RT, "external_room_id": "ok-318",
	}).insert(ignore_permissions=True)


def _other_property(name):
	"""A second, minimal property - for checks about what crosses a
	property boundary."""
	if not frappe.db.exists("Property", name):
		frappe.get_doc({
			"doctype": "Property", "property_name": name, "city": "Testville",
			"gst_mode": "Slab", "gst_slab_threshold": 7500,
			"gst_rate_low": 5, "gst_rate_high": 18,
		}).insert(ignore_permissions=True)
	return name


@check("booking engine: /stay/<property-slug> resolves, and /book scopes to the chosen property")
def t330():
	from kamra import public_api
	from kamra.booking_slugs import resolve_public_slug

	other = _other_property("EVAL Slug Two")
	frappe.db.set_value("Property", P, {"booking_engine_enabled": 1,
	                                     "page_slug": "eval-hotel-page"})
	frappe.db.set_value("Property", other, {"booking_engine_enabled": 1,
	                                         "page_slug": None})
	r = resolve_public_slug("eval-hotel-page")
	assert r == {"kind": "property", "property": P,
	             "property_slug": "eval-hotel-page"}, r
	# no page_slug: the slug of the name, as the chooser advertises it
	assert resolve_public_slug("eval-slug-two")["property"] == other

	idx = public_api.catalog_index()
	assert idx["mode"] == "properties", idx["mode"]
	slugs = {p["property_slug"]: p["name"] for p in idx["properties"]}
	assert slugs.get("eval-hotel-page") == P and slugs.get("eval-slug-two") == other, slugs

	scoped = public_api.catalog_index(property_slug="eval-hotel-page")
	assert scoped["mode"] in ("catalog", "sites", "single_listing"), scoped
	assert scoped["property"] == P, scoped
	try:
		public_api.catalog_index(property_slug="no-such-place")
		raise AssertionError("an unknown property slug resolved")
	except frappe.DoesNotExistError:
		pass
	# a property off the booking engine is not reachable by its slug
	frappe.db.set_value("Property", other, "booking_engine_enabled", 0)
	try:
		resolve_public_slug("eval-slug-two")
		raise AssertionError("a property off the booking engine resolved")
	except frappe.DoesNotExistError:
		pass


@check("banquet: a new enquiry keeps the session it was sold as")
def t331():
	from kamra.kamra.doctype.venue_booking.venue_booking import SESSION_HOURS

	fn = _function(day_offset=91, session="Evening")
	doc = frappe.get_doc("Venue Booking", fn)
	assert doc.session == "Evening", doc.session
	want = SESSION_HOURS["Evening"]
	assert (str(doc.start_time).zfill(8), str(doc.end_time).zfill(8)) == want, (
		doc.start_time, doc.end_time)
	# the form sends its clock too - a named session still wins
	fn = _function(day_offset=92, session="Morning",
	               start_time="19:00", end_time="23:00")
	doc = frappe.get_doc("Venue Booking", fn)
	assert doc.session == "Morning", doc.session
	assert str(doc.start_time).zfill(8) == SESSION_HOURS["Morning"][0], doc.start_time
	# Custom Hours, or times with no session, keep the times
	fn = _function(day_offset=93, session="Custom Hours")
	doc = frappe.get_doc("Venue Booking", fn)
	assert doc.session == "Custom Hours", doc.session
	assert str(doc.start_time).zfill(8) == "19:00:00", doc.start_time
	try:
		_function(day_offset=94, session="Midnight Feast")
		raise AssertionError("an unknown session was accepted")
	except frappe.ValidationError:
		pass


@check("banquet: a function ties to a group at its own property, and then posts to its bill")
def t332():
	from kamra import banquet as bq

	other = _other_property("EVAL Link Two")
	fn = _function(day_offset=95)
	day = add_days(nowdate(), 95)
	gb = frappe.get_doc({
		"doctype": "Group Booking", "property": P, "group_name": "EVAL Wedding Party",
		"check_in_date": day, "check_out_date": add_days(day, 2),
		"status": "Confirmed"}).insert(ignore_permissions=True).name
	far = frappe.get_doc({
		"doctype": "Group Booking", "property": other, "group_name": "EVAL Elsewhere",
		"check_in_date": day, "check_out_date": add_days(day, 2),
		"status": "Confirmed"}).insert(ignore_permissions=True).name

	assert any(g["name"] == gb for g in bq.linkable_groups(fn))
	assert not any(g["name"] == far for g in bq.linkable_groups(fn))
	try:
		bq.link_group(fn, far)
		raise AssertionError("tied a function to another property's group")
	except (frappe.ValidationError, frappe.PermissionError):
		pass
	out = bq.link_group(fn, gb)
	assert out["group_booking"] == gb, out
	assert frappe.db.get_value("Group Booking", gb, "event") == fn
	assert bq.function_sheet(fn)["group_detail"]["name"] == gb
	assert frappe.db.exists("Agent Action Log", {
		"action_type": "banquet_group_link", "reference_name": fn})

	# the group has a guest, the function is sold: Post to the bill works
	res = _res(_guest("Eval Bride", "+91 70000 03320"), add_days(day, 0),
	           add_days(day, 1))
	res.group_booking = gb
	res.save(ignore_permissions=True)
	bq.set_status(fn, "Confirmed")
	posted = bq.post_to_folio(fn)
	assert posted["posted"], posted
	assert frappe.db.get_value("Folio", posted["folio"], "group_booking") == gb
	# once billed, the group can't be swapped out from under the bill
	try:
		bq.link_group(fn, None)
		raise AssertionError("untied a billed function from its group")
	except frappe.ValidationError:
		pass


@check("banquet: Completed only through close-out; a guarded, logged reopen; re-close never refunds twice")
def t333():
	from kamra import banquet as bq

	b = _banquet_setup()
	fn = _function(day_offset=96)
	bq.update_function(fn, {"pax_guaranteed": 100})
	bq.add_menu(fn, b["menu"])
	bq.set_status(fn, "Confirmed")
	try:
		bq.set_status(fn, "Completed")
		raise AssertionError("Completed without the close-out")
	except frappe.ValidationError:
		pass
	bq.record_receipt(fn, 10000, kind="Security Deposit", mode="Cash")
	out = bq.close_out(fn, pax_actual=110)
	assert out["status"] == "Completed" and out["refunded"] == 10000, out
	try:
		bq.update_function(fn, {"beo_notes": "late change"})
		raise AssertionError("edited a closed function")
	except frappe.ValidationError:
		pass

	me = frappe.session.user
	try:
		frappe.set_user("frontdesk@kamra.local")  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow
		try:
			bq.reopen_function(fn, "guest disputes covers")
			raise AssertionError("Front Desk reopened a closed function")
		except frappe.PermissionError:
			pass
	finally:
		frappe.set_user(me)  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow
	try:
		bq.reopen_function(fn, "  ")
		raise AssertionError("reopened without a reason")
	except frappe.ValidationError:
		pass
	out = bq.reopen_function(fn, "Guest disputes the cover count")
	assert out["status"] == "Confirmed", out
	assert frappe.db.exists("Agent Action Log", {
		"action_type": "banquet_reopen", "reference_name": fn})
	bq.update_function(fn, {"beo_notes": "recounted"})   # editable again

	# the money settled at the first close-out stands
	try:
		bq.close_out(fn, damage_amount=500, damage_note="a glass")
		raise AssertionError("deducted damages twice")
	except frappe.ValidationError:
		pass
	out = bq.close_out(fn, pax_actual=105)
	assert out["status"] == "Completed" and out.get("reclosed"), out
	assert out["refunded"] == 0, out
	doc = frappe.get_doc("Venue Booking", fn)
	assert sum(1 for r in doc.receipts if r.kind == "Refund") == 1, \
		[r.as_dict() for r in doc.receipts]
	assert doc.pax_actual == 105, doc.pax_actual


@check("pricing: a company's negotiated rate plan prices its stays; an explicit plan wins")
def t334():
	from kamra import api
	from kamra.pricing import negotiated_rate_plan, quote

	rp = frappe.get_doc({
		"doctype": "Rate Plan", "property": P, "rate_plan_name": "EVAL Corp 20",
		"code": "EVCORP", "modifier_type": "Percent", "modifier_value": -20,
	}).insert(ignore_permissions=True).name
	bar = frappe.get_doc({
		"doctype": "Rate Plan", "property": P, "rate_plan_name": "EVAL BAR",
		"code": "EVBAR", "modifier_type": "Percent", "modifier_value": 0,
	}).insert(ignore_permissions=True).name
	comp = frappe.get_doc({
		"doctype": "Corporate Account", "company_name": "EVAL Negotiated Co",
		"negotiated_rate_plan": rp,
	}).insert(ignore_permissions=True).name

	ci, co = "2031-04-01", "2031-04-03"
	base = quote(P, RT, ci, co, 2, 0)
	q = quote(P, RT, ci, co, 2, 0, company=comp)
	assert q["rate_plan"] == rp, q["rate_plan"]
	assert round(q["room_total"], 2) == round(base["room_total"] * 0.8, 2), (
		q["room_total"], base["room_total"])
	# a plan the desk picked beats the contract
	q2 = quote(P, RT, ci, co, 2, 0, rate_plan=bar, company=comp)
	assert q2["rate_plan"] == bar and q2["room_total"] == base["room_total"], q2
	# the desk endpoint quotes the same number
	dq = api.get_quote(P, RT, ci, co, 2, 0, company=comp)
	assert dq["amount_after_tax"] == q["amount_after_tax"], (dq, q)

	# the booking stores the plan, so its nights and folio agree with the quote
	res = frappe.get_doc({
		"doctype": "Reservation", "property": P,
		"guest": _guest("Eval Corp Guest", "+91 70000 03340"),
		"room_type": RT, "check_in_date": ci, "check_out_date": co,
		"adults": 2, "auto_price": 1, "company": comp,
		"booking_type": "Corporate",
	}).insert(ignore_permissions=True)
	assert res.rate_plan == rp, res.rate_plan
	assert round(res.amount_after_tax, 2) == round(q["amount_after_tax"], 2), (
		res.amount_after_tax, q["amount_after_tax"])

	# at a sister property the plan with the same code stands in; none, none
	other = _other_property("EVAL Rate Two")
	assert negotiated_rate_plan(other, comp) is None
	twin = frappe.get_doc({
		"doctype": "Rate Plan", "property": other, "rate_plan_name": "EVAL Corp 20",
		"code": "EVCORP", "modifier_type": "Percent", "modifier_value": -20,
	}).insert(ignore_permissions=True).name
	assert negotiated_rate_plan(other, comp) == twin
	# a disabled contract plan applies nowhere
	frappe.db.set_value("Rate Plan", rp, "disabled", 1)
	assert negotiated_rate_plan(P, comp) is None


@check("hurdle tiers can target one room type, and only this property's")
def t335():
	from kamra import api
	from kamra.pricing import quote

	suite = frappe.get_doc({
		"doctype": "Room Type", "property": P, "room_type_code": "EVHS",
		"room_type_name": "EVAL Hurdle Suite", "base_price": 6000,
		"base_occupancy": 2, "adults_capacity": 3, "children_capacity": 1,
		"tax_percent": 18,
	}).insert(ignore_permissions=True).name
	out = api.save_hurdle_rate(P, 0, premium_pct=10, room_type=suite)
	row = next(r for r in api.hurdle_rates(P) if r["name"] == out["name"])
	assert row["room_type"] == suite, row
	assert row["room_type_name"] == "EVAL Hurdle Suite", row

	day_in, day_out = "2031-05-05", "2031-05-06"
	assert quote(P, suite, day_in, day_out, 2, 0)["nightly"][0]["demand_premium_pct"] == 10
	assert quote(P, RT, day_in, day_out, 2, 0)["nightly"][0]["demand_premium_pct"] == 0

	other = _other_property("EVAL Hurdle Two")
	far = frappe.get_doc({
		"doctype": "Room Type", "property": other, "room_type_code": "EVFAR",
		"room_type_name": "EVAL Far Room", "base_price": 3000,
		"base_occupancy": 2, "adults_capacity": 2, "tax_percent": 5,
	}).insert(ignore_permissions=True).name
	try:
		api.save_hurdle_rate(P, 50, premium_pct=5, room_type=far)
		raise AssertionError("a tier targeted another property's room type")
	except frappe.ValidationError:
		pass


# ── go-live data (#228) ─────────────────────────────────────────────────────

GL = "EVAL GoLive Hotel"


def _golive_property():
	"""A small hotel switching over today: two room types, three rooms, a
	cleaning fee that must NOT hit carried-forward stays."""
	if not frappe.db.exists("Property", GL):
		frappe.get_doc({
			"doctype": "Property", "property_name": GL, "city": "Testville",
			"gst_mode": "Fixed", "gst_rate_low": 5, "gst_rate_high": 5,
		}).insert(ignore_permissions=True)
	frappe.db.set_value("Property", GL, {"cleaning_fee": 750,
	                                     "business_date": nowdate()})
	rt = frappe.db.get_value("Room Type", {"property": GL,
	                                       "room_type_code": "GLD"})
	if not rt:
		rt = frappe.get_doc({
			"doctype": "Room Type", "property": GL, "room_type_code": "GLD",
			"room_type_name": "Golive Deluxe", "base_price": 4000,
			"base_occupancy": 2, "adults_capacity": 3,
			"children_capacity": 2, "tax_percent": 5,
		}).insert(ignore_permissions=True).name
		for n in ("G101", "G102", "G103"):
			frappe.get_doc({"doctype": "Room", "property": GL,
			                "room_number": n, "room_type": rt,
			                }).insert(ignore_permissions=True)
	return rt


def _golive_files():
	today = getdate(nowdate())
	def d(n):
		return add_days(today, n).strftime("%d/%m/%Y")
	bookings = (
		"Reservation No,Guest Name,Phone,Room Type,Room,Check In,Check Out,"
		"Adults,Total Amount,Status\n"
		f"OLD-1,Golive Inhouse,+91 70000 22801,Golive Deluxe,G101,{d(-3)},"
		f"{d(2)},2,21000,In House\n"
		f"OLD-2,Golive Settled,+91 70000 22802,Golive Deluxe,G102,{d(-1)},"
		f"{d(1)},2,8400,Checked In\n"
		f"OLD-3,Golive Future,+91 70000 22803,Golive Deluxe,,{d(10)},"
		f"{d(12)},2,8400,Confirmed\n")
	companies = (
		"Company Name,Tax ID,Contact Name,Credit Allowed,Credit Limit,Credit Days\n"
		"EVAL Golive Corp,29ABCDE1234F1Z5,Asha,Yes,\"50,000\",45\n"
		"EVAL Golive Prepaid,,Ravi,Yes,10000,\n"
		"EVAL Golive Cash Co,,,No,,\n")
	opening = (
		"Type,Reservation No,Guest Name,Room,Check In,Company,Invoice No,"
		"Invoice Date,Amount,Mode\n"
		"In-house,OLD-1,,,,,,,\"12,600.00\",\n"
		"In-house,,Golive Settled,,"
		f"{d(-1)},,,,0,\n"
		"Deposit,OLD-3,,,,,,,3000,UPI\n"
		f"City ledger,,Mr Traveller,,,EVAL Golive Corp,INV-881,{d(-40)},18000,\n"
		f"City ledger,,,,,EVAL Golive Corp,INV-902,{d(-5)},\"4,500.50\",\n"
		"City ledger,,,,,EVAL Golive Prepaid,,,(2000),\n")
	return bookings, companies, opening


@check("go-live: templates, companies upsert with credit terms, re-run is a no-op")
def t220():
	from kamra import golive
	_golive_property()
	tpl = golive.csv_template("opening")
	assert tpl["headers"][0] == "Type" and "Amount" in tpl["headers"], tpl
	assert golive.csv_template("companies")["csv"].startswith("Company Name")
	_b, companies, _o = _golive_files()
	p = golive.preview_companies(GL, companies)
	assert p["ok"] == 3 and p["on_credit"] == 2, p
	r = golive.run_companies(GL, companies)
	assert r["created"] + r["updated"] == 3 and not r["errors"], r
	assert frappe.db.get_value("Corporate Account", "EVAL Golive Corp",
	                           "credit_allowed") == 1
	assert frappe.db.get_value("Corporate Account", "EVAL Golive Cash Co",
	                           "credit_allowed") == 0
	acc = frappe.db.get_value("City Ledger Account", {
		"property": GL, "company": "EVAL Golive Corp"},
		["credit_limit", "credit_days", "use_default_credit_days"])
	assert float(acc[0]) == 50000 and acc[1] == 45 and acc[2] == 0, acc
	# no Credit Days on the row: the company follows the property default
	assert frappe.db.get_value("City Ledger Account", {
		"property": GL, "company": "EVAL Golive Prepaid"},
		"use_default_credit_days") == 1
	n = frappe.db.count("Corporate Account", {"company_name": ("like", "EVAL Golive%")})
	again = golive.run_companies(GL, companies)
	assert again["created"] == 0 and again["updated"] == 3, again
	assert frappe.db.count("Corporate Account",
	                       {"company_name": ("like", "EVAL Golive%")}) == n
	rec = golive.reconcile(GL, companies_csv=companies)
	assert rec["categories"][0]["matched"], rec


@check("go-live: in-house guests carried forward - room set, no one-time fees, re-run skips")
def t221():
	from kamra import migrate
	_golive_property()
	bookings, _c, _o = _golive_files()
	p = migrate.preview_import(GL, bookings, "auto")
	assert p["ok"] == 3 and p["skipped"] == 0, p
	r = migrate.run_import(GL, bookings, "auto")
	assert r["created"] == 3 and not r["errors"], r
	res = frappe.get_doc("Reservation", {"property": GL,
	                                     "idempotency_key": "import:OLD-1"})
	assert res.status == "Checked In" and res.room == f"{GL}-G101", (res.status, res.room)
	folio = frappe.get_doc("Folio", {"reservation": res.name, "folio_type": "Guest"})
	fees = [c.charge_type for c in folio.charges]
	assert "Cleaning Fee" not in fees, fees  # billed by the old system
	again = migrate.run_import(GL, bookings, "auto")
	assert again["created"] == 0 and again["already_imported"] == 3, again
	assert migrate.preview_import(GL, bookings, "auto")["already_imported"] == 3


@check("go-live: opening balances post through the ledgers, idempotent, reconcile to the file")
def t222():
	from kamra import golive, migrate
	from kamra.folio import post_remaining_nights
	_golive_property()
	bookings, companies, opening = _golive_files()
	golive.run_companies(GL, companies)
	migrate.run_import(GL, bookings, "auto")

	pv = golive.preview_opening(GL, opening)
	assert pv["skipped"] == 0, pv["issues"]
	cats = {c["category"]: c for c in pv["categories"]}
	assert cats["in_house"]["count"] == 2 and cats["in_house"]["total"] == 12600, cats
	assert cats["deposit"]["total"] == 3000, cats
	assert cats["ar"]["count"] == 3 and cats["ar"]["total"] == 20500.5, cats
	# not ready before anything is posted
	assert not golive.reconcile(GL, opening_csv=opening)["ready"]

	r = golive.run_opening(GL, opening)
	assert not r["errors"], r["errors"]
	assert r["posted"] == {"in_house": 2, "deposit": 1, "ar": 3}, r["posted"]

	# in-house: one labelled line on the guest folio, on the Guest ledger
	res = frappe.db.get_value("Reservation", {"property": GL,
	                                          "idempotency_key": "import:OLD-1"})
	folio = frappe.get_doc("Folio", {"reservation": res, "folio_type": "Guest"})
	ob = [c for c in folio.charges if c.charge_type == "Opening Balance"]
	assert len(ob) == 1 and ob[0].amount == 12600 and ob[0].transaction_code == "8900", ob
	assert frappe.db.get_value("Folio Ledger Entry", {
		"source_doctype": "Folio Charge", "source_name": ob[0].name,
		"ledger": "Guest"}, "debit") == 12600
	# no money in today's till
	assert not frappe.db.exists("Cashier Transaction", {"folio": folio.name})

	# deposit: an Advance in the Deposit ledger, booking's advance_paid up
	fut = frappe.get_doc("Reservation", {"property": GL,
	                                     "idempotency_key": "import:OLD-3"})
	assert float(fut.advance_paid) == 3000, fut.advance_paid
	dep = frappe.db.sql("""SELECT SUM(e.credit - e.debit) FROM `tabFolio Ledger Entry` e
	        JOIN `tabFolio` f ON f.name = e.folio
	        WHERE f.reservation = %s AND e.ledger = 'Deposit'""", fut.name)[0][0]
	assert float(dep) == 3000, dep

	# AR: the company owes both invoices, dated as billed; the prepaid
	# company carries a credit
	corp = frappe.db.get_value("City Ledger Account",
	                           {"property": GL, "company": "EVAL Golive Corp"})
	bal = frappe.db.sql("""SELECT SUM(debit - credit) FROM `tabCity Ledger Entry`
	                       WHERE account = %s""", corp)[0][0]
	assert abs(float(bal) - 22500.5) < 0.01, bal
	old, due = frappe.db.get_value("City Ledger Entry", {
		"account": corp, "invoice_number": "INV-881"}, ["posting_date", "due_date"])
	assert str(old) == str(add_days(getdate(nowdate()), -40)), old
	# due on the original invoice date + the company's 45 credit days
	assert str(due) == str(add_days(old, 45)), due
	ar = frappe.db.sql("""SELECT SUM(debit - credit) FROM `tabFolio Ledger Entry`
	                      WHERE property = %s AND ledger = 'AR'""", GL)[0][0]
	assert abs(float(ar) - 22500.5) < 0.01, ar
	prepaid = frappe.db.get_value("City Ledger Account",
	                              {"property": GL, "company": "EVAL Golive Prepaid"})
	pbal = frappe.db.sql("""SELECT SUM(debit - credit) FROM `tabCity Ledger Entry`
	                        WHERE account = %s""", prepaid)[0][0]
	assert float(pbal) == -2000, pbal
	# not revenue: the day's other revenue ignores opening balances
	# (the deposit opened the future booking's folio early, which posts its
	# cleaning fee as record_advance always has - that 750 is real revenue)
	from kamra.reports import _day_stats
	assert _day_stats(GL, nowdate(), 3)["other_revenue"] in (0, 750)

	# idempotent: the same file again posts nothing
	again = golive.run_opening(GL, opening)
	assert sum(again["posted"].values()) == 0 and again["already_posted"] == 6, again
	assert len([c for c in frappe.get_doc("Folio", folio.name).charges
	            if c.charge_type == "Opening Balance"]) == 1

	rec = golive.reconcile(GL, opening_csv=opening, companies_csv=companies,
	                       bookings_csv=bookings)
	assert rec["ready"], rec["blockers"]
	by = {c["category"]: c for c in rec["categories"]}
	assert by["ar"]["kamra_total"] == 20500.5 and by["ar"]["matched"], by["ar"]
	assert {c["company"]: c["matched"] for c in by["ar"]["by_company"]} == {
		"EVAL Golive Corp": True, "EVAL Golive Prepaid": True}, by["ar"]["by_company"]

	# a file that no longer ties out is not ready
	changed = opening.replace('"12,600.00"', "12000")
	bad = golive.reconcile(GL, opening_csv=changed)
	assert not bad["ready"] and not {c["category"]: c for c in bad["categories"]}[
		"in_house"]["matched"], bad

	# checkout bills Kamra's nights only: go-live (today) to departure
	stay = frappe.get_doc("Reservation", res)
	post_remaining_nights(stay)
	nights = frappe.db.sql("""SELECT fc.posting_date FROM `tabFolio Charge` fc
	        JOIN `tabFolio` f ON f.name = fc.parent
	        WHERE f.reservation = %s AND fc.charge_type = 'Room'""", res, pluck=True)
	assert len(nights) == 2 and min(nights) == getdate(nowdate()), nights


@check("go-live: in-house stay with no opening row blocks go-live")
def t223():
	from kamra import golive, migrate
	# runs before t222 and leaves nothing behind for it
	frappe.db.savepoint("t223_own")
	try:
		_golive_property()
		bookings, companies, opening = _golive_files()
		golive.run_companies(GL, companies)
		migrate.run_import(GL, bookings, "auto")
		only_one = "\n".join(l for l in opening.splitlines()
		                     if "Golive Settled" not in l) + "\n"
		golive.run_opening(GL, only_one)
		rec = golive.reconcile(GL, opening_csv=only_one)
		assert not rec["ready"], rec
		assert any("Golive Settled" in b for b in rec["blockers"]), rec["blockers"]
	finally:
		frappe.db.rollback(save_point="t223_own")


@check("go-live: Finance-only gate; opening balances never hand-posted")
def t224():
	from kamra import api, golive
	_golive_property()
	_b, companies, opening = _golive_files()
	frappe.set_user("frontdesk@kamra.local")  # nosemgrep: frappe-setuser -- eval role-gate check as Front Desk
	try:
		for fn, args in ((golive.run_opening, (GL, opening)),
		                 (golive.preview_opening, (GL, opening)),
		                 (golive.run_companies, (GL, companies)),
		                 (golive.reconcile, (GL, opening))):
			try:
				fn(*args)
				raise AssertionError(f"Front Desk ran {fn.__name__}")
			except frappe.PermissionError:
				pass
	finally:
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- restore eval admin context
	out = api.create_booking(
		property=P, room_type=RT, check_in_date="2031-04-10",
		check_out_date="2031-04-12", guest_name="Eval OB Desk",
		phone="+91 70000 22809")
	api.check_in(out["reservation"])
	folio = frappe.db.get_value("Folio", {"reservation": out["reservation"],
	                                      "folio_type": "Guest"})
	try:
		api.add_folio_charge(folio, "Opening Balance", "sneaky", 500)
		raise AssertionError("an opening balance was hand-posted")
	except frappe.ValidationError:
		pass


# ── company credit control (#238) ───────────────────────────────────────────

def _credit_setting(key, value):
	from kamra.settings import clear_cache
	name = frappe.db.get_value("Property Setting", {"property": P, "setting_key": key})
	if name:
		frappe.db.set_value("Property Setting", name, "value", json.dumps(value))
	else:
		frappe.get_doc({"doctype": "Property Setting", "property": P,
		                "setting_key": key, "value": json.dumps(value)}
		               ).insert(ignore_permissions=True)
	clear_cache(P)


def _credit_reset():
	from kamra.settings import clear_cache
	frappe.db.delete("Property Setting", {
		"property": P, "setting_key": ("in", ("credit_control", "default_credit_days",
		                                      "credit_overdue_grace_days"))})
	clear_cache(P)


def _credit_bill(corp, name, phone, room_code, amount, limit=0, days=0):
	"""A guest folio of `amount` billed to `corp` on the city ledger, with
	the account's terms set first. Returns (account, folio)."""
	from kamra import api
	from kamra.ledger import _ar_account, transfer_to_city_ledger
	acct = _ar_account(P, corp)
	frappe.db.set_value("City Ledger Account", acct,
	                    {"credit_limit": limit, "credit_days": days,
	                     "use_default_credit_days": 0 if days else 1})
	_, f = _in_house(name, phone, "2036-07-01", "2036-07-03", _ledger_room(room_code))
	api.add_folio_charge(f, "Misc", "eval credit bill", amount, gst_rate=0)
	transfer_to_city_ledger(f, corp, credit_check=False)
	return acct, f


def _credit_folio(name, phone, room_code, amount):
	from kamra import api
	_, f = _in_house(name, phone, "2036-07-01", "2036-07-03", _ledger_room(room_code))
	api.add_folio_charge(f, "Misc", "eval credit bill", amount, gst_rate=0)
	return f


@check("credit: a 45-day company's bill is Not due at day 35, overdue at day 50")
def t225():
	from unittest.mock import patch

	from frappe.utils import add_days

	from kamra.ledger import city_ledger_aging
	corp = _credit_corp("EVAL Credit 45 Corp")
	acct, f = _credit_bill(corp, "Eval Credit 45", "+91 70009 22501", "C2501", 1000, days=45)
	inv = frappe.db.get_value("City Ledger Entry", {"folio": f, "kind": "Invoice"},
	                          ["posting_date", "due_date"], as_dict=True)
	assert str(inv.due_date) == str(add_days(inv.posting_date, 45)), inv
	def row(day):
		with patch("kamra.ledger.nowdate", return_value=str(add_days(inv.posting_date, day))):
			return next(a for a in city_ledger_aging(P)["accounts"] if a["name"] == acct)
	r = row(35)
	assert r["not_due"] == 1000 and r["overdue"] == 0, r
	r = row(50)
	assert r["d1_30"] == 1000 and r["overdue"] == 1000, r
	_assert_company_ar(acct)


@check("credit: over-limit transfer warns under Warn, is refused under Block")
def t226():
	from kamra import credit
	from kamra.ledger import city_ledger_transfer
	try:
		corp = _credit_corp("EVAL Credit Limit Corp")
		_credit_bill(corp, "Eval Credit L0", "+91 70009 22601", "C2601", 800, limit=1000)
		f = _credit_folio("Eval Credit L1", "+91 70009 22602", "C2602", 500)
		_credit_setting("credit_control", "Warn")
		out = city_ledger_transfer(f, corp)
		assert out["credit"]["over_limit_by"] == 300 and out["credit"]["warning"], out
		f2 = _credit_folio("Eval Credit L2", "+91 70009 22603", "C2603", 200)
		_credit_setting("credit_control", "Block")
		try:
			city_ledger_transfer(f2, corp)
			raise AssertionError("over-limit transfer was not blocked")
		except credit.CreditBlocked as e:
			assert "CREDIT_BLOCKED" in str(e) and "credit limit" in str(e), e
		assert not frappe.db.exists("City Ledger Entry", {"folio": f2}), "blocked bill moved"
	finally:
		_credit_reset()


@check("credit: a Finance override is logged with who and why; Front Desk and agents can't override")
def t227():
	from kamra import credit
	from kamra.ledger import city_ledger_transfer
	fin = "finance.credit@kamra.local"
	if not frappe.db.exists("User", fin):
		frappe.get_doc({"doctype": "User", "email": fin, "first_name": "Fin",
		                "enabled": 1, "user_type": "System User",
		                "send_welcome_email": 0,
		                "roles": [{"role": "Finance"}, {"role": "Front Desk"}]}
		               ).insert(ignore_permissions=True)
	try:
		corp = _credit_corp("EVAL Credit Override Corp")
		_credit_bill(corp, "Eval Credit O0", "+91 70009 22701", "C2701", 900, limit=1000)
		f = _credit_folio("Eval Credit O1", "+91 70009 22702", "C2702", 400)
		_credit_setting("credit_control", "Block")
		frappe.set_user("frontdesk@kamra.local")  # nosemgrep: frappe-setuser -- eval role-gate check as Front Desk
		try:
			city_ledger_transfer(f, corp, credit_override_reason="desk thinks it's fine")
			raise AssertionError("Front Desk overrode a credit block")
		except frappe.PermissionError:
			pass
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- restore eval admin context
		frappe.flags.kamra_agent_call = "MCP"
		try:
			city_ledger_transfer(f, corp, credit_override_reason="agent approves")
			raise AssertionError("an agent overrode a credit block")
		except frappe.PermissionError as e:
			assert "agent" in str(e), e
		finally:
			frappe.flags.kamra_agent_call = None
		frappe.set_user(fin)  # nosemgrep: frappe-setuser -- eval Finance persona overrides the block
		try:
			out = city_ledger_transfer(f, corp, credit_override_reason="CFO approved, PO 77")
		finally:
			frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- restore eval admin context
		assert out["credit"]["overridden"], out
		logs = frappe.get_all("Agent Action Log",
		                      filters={"action_type": "credit_override", "reference_name": f},
		                      fields=["approver", "rationale", "after_snapshot"])
		assert len(logs) == 1 and logs[0].approver == fin, logs
		assert "CFO approved, PO 77" in logs[0].rationale, logs
		assert json.loads(logs[0].after_snapshot)["amount"] == 400, logs
		assert credit.can_override() is True  # Administrator again
	finally:
		_credit_reset()


@check("credit: overdue counts only past the grace period")
def t228():
	from unittest.mock import patch

	from frappe.utils import add_days

	from kamra.credit import check_company_credit
	try:
		corp = _credit_corp("EVAL Credit Grace Corp")
		acct, f = _credit_bill(corp, "Eval Credit G", "+91 70009 22801", "C2801", 700, days=30)
		due = frappe.db.get_value("City Ledger Entry", {"folio": f, "kind": "Invoice"}, "due_date")
		_credit_setting("credit_overdue_grace_days", 7)
		with patch("kamra.ledger.nowdate", return_value=str(add_days(due, 5))):
			r = check_company_credit(corp, P)
		assert r["ok"] and r["overdue_amount"] == 0, r
		with patch("kamra.ledger.nowdate", return_value=str(add_days(due, 8))):
			r = check_company_credit(acct, P)
		assert not r["ok"] and r["overdue_amount"] == 700, r
	finally:
		_credit_reset()


@check("credit: due-date backfill patch fills missing due dates and is idempotent")
def t229():
	from frappe.utils import add_days

	from kamra.patches.v42 import backfill_city_ledger_due_dates as patch_mod
	corp = _credit_corp("EVAL Credit Backfill Corp")
	acct, f = _credit_bill(corp, "Eval Credit B", "+91 70009 22901", "C2901", 300, days=15)
	entry = frappe.db.get_value("City Ledger Entry", {"folio": f, "kind": "Invoice"})
	frappe.db.set_value("City Ledger Entry", entry, {"due_date": None,
	                                                 "posting_date": "2036-01-10"})
	patch_mod.execute()
	want = str(add_days("2036-01-10", 15))
	assert str(frappe.db.get_value("City Ledger Entry", entry, "due_date")) == want
	frappe.db.set_value("City Ledger Account", acct, "credit_days", 60)
	patch_mod.execute()
	assert str(frappe.db.get_value("City Ledger Entry", entry, "due_date")) == want


@check("credit: due-date aging buckets add up to the balance with unapplied credit")
def t230():
	from kamra.ledger import city_ledger_settle
	corp = _credit_corp("EVAL Credit Buckets Corp")
	acct, f1 = _credit_bill(corp, "Eval Credit K0", "+91 70009 23001", "C3001", 500, days=30)
	_, f2 = _credit_bill(corp, "Eval Credit K1", "+91 70009 23002", "C3002", 400, days=30)
	city_ledger_settle(acct, 600, allocations=[{"folio": f1, "amount": 500}])
	row = _assert_company_ar(acct)
	assert row["unapplied_credit"] == 100 and float(row["balance"]) == 300, row


@check("budget vs actual: occupancy over nights elapsed; unposted in-house nights are counted and explained")
def t336():
	from frappe.utils import date_diff

	from kamra.reports import budget_vs_actual

	period = nowdate()[:7]
	before = budget_vs_actual(P, period)
	start = period + "-01"
	assert 0 <= before["days_elapsed"] <= before["total_days"], before
	rooms = frappe.db.count("Room", {"property": P})
	assert before["elapsed_room_nights"] == rooms * before["days_elapsed"], before
	assert before["basis"] == "posted"

	# an in-house stay nobody has run End of Day for yet
	ci, co = add_days(nowdate(), -1), add_days(nowdate(), 2)
	_res(_guest("Eval Inhouse", "+91 70000 03360"), ci, co, allow_past=1)
	after = budget_vs_actual(P, period)
	window_end = add_days(start, after["days_elapsed"])
	expect = max(0, date_diff(min(str(co), str(window_end)), max(str(ci), start)))
	assert after["on_books_nights"] - before["on_books_nights"] == expect, (
		before["on_books_nights"], after["on_books_nights"], expect)
	assert after["unposted_nights"] - before["unposted_nights"] == expect, (before, after)
	# nothing posted, nothing claimed as actual
	assert after["posted_nights"] == before["posted_nights"], (before, after)

	# a month that hasn't started has no elapsed nights; a past one has all
	future = budget_vs_actual(P, "2031-01")
	assert future["days_elapsed"] == 0 and future["rows"][1]["actual"] == 0, future
	past = budget_vs_actual(P, "2020-02")
	assert past["days_elapsed"] == past["total_days"] == 29, past


def _settle_stay(number, phone, ci="2037-03-01", co="2037-03-03"):
	"""An in-house stay in its own room whose nights are NOT posted yet:
	check-out (and the settlement preview) has to post them first."""
	g = _guest(f"Eval Settle {number}", phone)
	res = _res(g, ci, co, _dep_room(number))
	res.status = "Checked In"
	res.save(ignore_permissions=True)
	folio = frappe.db.get_value(
		"Folio", {"reservation": res.name, "folio_type": "Guest"})
	if not folio:
		from kamra.folio import open_folio
		folio = open_folio(res)
	return res, folio


@check("checkout context: reports owed and refund due exactly as check_out refuses, writes nothing")
def t340():
	from kamra import api
	res, folio = _settle_stay("E340", "+91 70000 03400")
	before = float(frappe.db.get_value("Folio", folio, "balance") or 0)
	charges = frappe.db.count("Folio Charge", {"parent": folio})
	s = api.checkout_context(res.name)
	# read-only: the nights it posted to judge the balance are rolled back
	assert float(frappe.db.get_value("Folio", folio, "balance") or 0) == before
	assert frappe.db.count("Folio Charge", {"parent": folio}) == charges
	owed = s["totals"]["owed"]
	assert owed > before + 0.01, ("preview did not count the unposted nights", s["totals"], before)
	assert s["totals"]["refund_due"] == 0 and not s["actions"]["can_checkout"], s
	assert [c["folio"] for c in s["collect"]] == [folio], s["collect"]
	assert abs(s["collect"][0]["amount"] - owed) < 0.01, s["collect"]
	assert s["payment_modes"] and any(b["code"] == "owed" for b in s["blockers"]), s
	try:
		api.check_out(res.name)
		raise AssertionError("checked out with an unpaid bill")
	except frappe.ValidationError as e:
		assert "still owed" in str(e), e
	# check_out posted the nights: the folio now owes what the preview said
	assert abs(float(frappe.db.get_value("Folio", folio, "balance")) - owed) < 0.01

	# overpaid by 750: a refund due, back by the mode it came in
	api.add_folio_payment(folio, "Card", owed + 750)
	s = api.checkout_context(res.name)
	assert (s["totals"]["owed"], s["totals"]["refund_due"],
	        s["totals"]["to_city_ledger"]) == (0, 750.0, 0), s["totals"]
	assert s["collect"] == [] and len(s["refunds"]) == 1, s
	r = s["refunds"][0]
	assert (r["kind"], r["folio"], r["amount"], r["source"], r["mode"]) == \
		("folio", folio, 750.0, "overpayment", "Card"), r
	try:
		api.check_out(res.name)
		raise AssertionError("checked out while the guest was owed a refund")
	except frappe.ValidationError as e:
		assert "is owed" in str(e), e


@check("checkout context: refunding the reported amount lets check_out through")
def t341():
	from kamra import api
	res, folio = _settle_stay("E341", "+91 70000 03410")
	owed = api.checkout_context(res.name)["totals"]["owed"]
	api.add_folio_payment(folio, "Cash", owed + 1200)
	s = api.checkout_context(res.name)
	assert s["totals"]["refund_due"] == 1200.0, s["totals"]
	for r in s["refunds"]:
		api.refund_folio_payment(r["folio"], r["amount"], r["mode"],
		                         "Refund of overpayment at check-out")
	s = api.checkout_context(res.name)
	assert s["settled"] and s["actions"]["can_checkout"] and not s["blockers"], s
	assert not s["collect"] and not s["refunds"], s
	api.check_out(res.name)
	assert frappe.db.get_value("Reservation", res.name, "status") == "Checked Out"
	# after check-out the same call shows the folio ready for its invoice
	s = api.checkout_context(res.name)
	f = next(x for x in s["folios"] if x["folio"] == folio)
	assert f["status"] == "Open" and abs(f["balance"]) < 0.01 and f["has_charges"], f
	assert any(b["code"] == "not_in_house" for b in s["blockers"]), s["blockers"]
	inv = api.close_folio(folio)["invoice_number"]
	assert inv and frappe.db.get_value("Folio", folio, "status") == "Closed"


@check("checkout context: a held security deposit is refunded through the deposit path")
def t342():
	from kamra import api
	res, folio = _dep_stay("E342", "+91 70000 03420")
	api.collect_security_deposit(res.name, 5000, "UPI")
	api.add_folio_payment(folio, "Cash", 400)  # and a little over-collected
	s = api.checkout_context(res.name)
	assert s["deposit"]["held"] == 5000 and s["deposit"]["folio"] == folio, s["deposit"]
	assert s["totals"]["refund_due"] == 5400.0, s["totals"]
	kinds = [(r["kind"], r["amount"], r["source"], r["mode"]) for r in s["refunds"]]
	assert kinds == [("deposit", 5000.0, "security_deposit", "UPI"),
	                 ("folio", 400.0, "overpayment", "Cash")], kinds
	for r in s["refunds"]:
		if r["kind"] == "deposit":
			api.refund_security_deposit(res.name, r["amount"], r["mode"],
			                            "Refund at check-out")
		else:
			api.refund_folio_payment(r["folio"], r["amount"], r["mode"],
			                         "Refund of overpayment at check-out")
	dep = frappe.db.get_value("Security Deposit", {"reservation": res.name},
	                          ["status", "balance", "refunded_amount"], as_dict=True)
	assert dep.status == "Refunded" and float(dep.balance) == 0 \
		and float(dep.refunded_amount) == 5000, dep
	d, c = _ledger(folio, "Deposit")
	assert abs(d - c) < 0.01, (d, c)  # the liability is released
	assert api.checkout_context(res.name)["actions"]["can_checkout"]
	api.check_out(res.name)
	assert frappe.db.get_value("Reservation", res.name, "status") == "Checked Out"


@check("checkout context: a folio invoiced before its nights were posted is a blocker, not a toast")
def t343():
	from kamra import api
	res, folio = _settle_stay("E343", "+91 70000 03430")
	# nothing posted yet, so the empty bill is settled and closes
	assert abs(float(frappe.db.get_value("Folio", folio, "balance") or 0)) < 0.01
	api.close_folio(folio)
	s = api.checkout_context(res.name)
	codes = [b["code"] for b in s["blockers"]]
	assert "nights_not_posted" in codes and not s["actions"]["can_checkout"], s["blockers"]
	b = next(b for b in s["blockers"] if b["code"] == "nights_not_posted")
	assert b["folio"] == folio and "invoice" in b["message"], b
	# and the preview left no message behind for the browser to toast
	assert not [m for m in (frappe.local.message_log or [])
	            if "frozen" in str(m)], frappe.local.message_log
	try:
		api.check_out(res.name)
		raise AssertionError("checked out onto an invoiced folio")
	except frappe.ValidationError:
		pass
	frappe.local.message_log = []


@check("checkout context: open restaurant bills show as pending and post to the room; each step is audited")
def t344():
	from kamra import api, pos
	res, folio = _settle_stay("E344", "+91 70000 03440")
	outlet = frappe.get_doc({
		"doctype": "POS Outlet", "property": P, "outlet_name": "Eval Checkout Cafe",
		"outlet_type": "Restaurant", "gst_rate": 5,
	}).insert(ignore_permissions=True).name
	mi = frappe.get_doc({
		"doctype": "Menu Item", "property": P, "outlet": outlet,
		"item_name": "Eval Checkout Tea", "category": "Food", "price": 100,
		"is_veg": 1, "available": 1, "prep_station": "Kitchen",
	}).insert(ignore_permissions=True).name
	o = pos.create_order(outlet, [{"menu_item": mi, "qty": 2}], room=res.room)
	s = api.checkout_context(res.name)
	bills = [b for b in s["pending_bills"] if b["kind"] == "pos"]
	assert [b["name"] for b in bills] == [o["order"]], s["pending_bills"]
	assert bills[0]["amount"] == 200 and bills[0]["can_post_to_room"], bills
	assert any(n["code"] == "pending_bills" for n in s["notices"]), s["notices"]
	owed_before = s["totals"]["owed"]
	pos.deliver_order(o["order"])
	s = api.checkout_context(res.name)
	assert not s["pending_bills"], s["pending_bills"]
	assert round(s["totals"]["owed"] - owed_before, 2) == 210.0, (owed_before, s["totals"])
	# settle, check out, invoice: every step names who did it
	for c in s["collect"]:
		api.add_folio_payment(c["folio"], "Cash", c["amount"])
	api.check_out(res.name)
	api.close_folio(folio)
	user = frappe.session.user
	for action, ref in (("folio_payment", folio), ("check_out", res.name),
	                    ("close_folio", folio)):
		assert frappe.db.exists("Agent Action Log", {
			"action_type": action, "reference_name": ref, "actor": user}), action


# ── guided check-in (t350-t355) ──────────────────────────────────────────

class _steps_enforced:
	"""The harness turns the check-in step gate off for the checks that
	only need an in-house stay; these checks test the gate itself."""

	def __enter__(self):
		frappe.flags.kamra_checkin_steps_off = False

	def __exit__(self, *exc):
		frappe.flags.kamra_checkin_steps_off = True


class _as_user:
	def __init__(self, user):
		self.user = user

	def __enter__(self):
		self.me = frappe.session.user
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser -- controlled user context switch; persona user created in setup()

	def __exit__(self, *exc):
		frappe.set_user(self.me)  # nosemgrep: frappe-setuser -- controlled user context switch; restores the previous user


class _no_deposit_policy:
	"""Property defaults ask a security deposit (5000) and earlier checks
	set a booking deposit %; checks that are not about deposits clear both
	so the deposit step does not apply."""

	def __enter__(self):
		self.was = frappe.db.get_value("Property", P, ["security_deposit_amount", "deposit_pct"])
		frappe.db.set_value("Property", P, {"security_deposit_amount": 0, "deposit_pct": 0})
		frappe.clear_document_cache("Property", P)

	def __exit__(self, *exc):
		frappe.db.set_value("Property", P, {"security_deposit_amount": self.was[0],
		                                    "deposit_pct": self.was[1]})
		frappe.clear_document_cache("Property", P)


def _ci_room(number):
	return frappe.get_doc({
		"doctype": "Room", "property": P, "room_number": number,
		"room_type": RT, "housekeeping_status": "Clean",
	}).insert(ignore_permissions=True).name


def _ci_stay(name, phone, room=None):
	g = _guest(name, phone)
	return _res(g, nowdate(), add_days(nowdate(), 2), room=room)


def _refused(fn, *args, exc=None, contains=None, **kwargs):
	try:
		fn(*args, **kwargs)
	except Exception as e:  # noqa: BLE001 - the check inspects it
		if exc is not None:
			assert isinstance(e, exc), f"{type(e).__name__}: {e}"
		if contains:
			for c in contains if isinstance(contains, (list, tuple)) else [contains]:
				assert c in str(e), f"{c!r} not in {e}"
		frappe.clear_messages()
		return str(e)
	raise AssertionError(f"{getattr(fn, '__name__', fn)} was not refused")


FD = "frontdesk@kamra.local"


@check("guided check-in: only the room hard-blocks; soft-required steps warn and backfill")
def t350():
	from kamra import checkin as ci
	from kamra.api import check_in

	# no room yet: check_in refuses
	res_bare = _ci_stay("Eval Guided Bare", "+91 70034 00000")
	assert not res_bare.room
	with _steps_enforced(), _no_deposit_policy():
		_refused(check_in, res_bare.name, exc=ci.CheckInStepsMissing, contains="room")
		bare = ci.check_in_readiness(res_bare.name)
		assert bare["ready"] is False
		assert {m["step"] for m in bare["missing_required"]} == {"assign_room"}

	room = _ci_room("G340")
	res = _ci_stay("Eval Guided", "+91 70034 00001", room=room)
	with _steps_enforced(), _no_deposit_policy():
		r = ci.check_in_readiness(res.name)
		# room assigned → ready even while soft-required steps are open
		assert r["ready"] is True and not r["missing_required"], r
		backfill = {m["step"] for m in r["pending_backfill"]}
		# India pack: registration card is soft-required by default
		assert {"guest_ids", "billing_check", "room_charges",
		        "registration_card"} <= backfill, backfill
		dep = next(s for s in r["steps"] if s["step"] == "security_deposit")
		assert dep["applies"] == 0, dep

		with _as_user(FD):
			# room cannot be skipped; soft-required can (backfill later)
			_refused(ci.skip_checkin_step, res.name, "assign_room",
			         contains="cannot be skipped")
			ci.skip_checkin_step(res.name, "guest_ids", reason="Guest in a hurry")
			ci.skip_checkin_step(res.name, "keys", reason="Code lock")
			_refused(ci.complete_checkin_step, res.name, "guest_ids",
			         contains="ID still needed")
			# check-in goes through with soft steps still open
			out = check_in(res.name)
			assert out.get("pending_backfill"), out
		assert out["checked_in_by"] == FD, out
	res.reload()
	assert res.status == "Checked In"
	assert res.checked_in_by == FD and res.checked_in_at, (res.checked_in_by, res.checked_in_at)
	# finish IDs after check-in (backfill)
	with _as_user(FD):
		ci.save_guest_details(res.name, id_type="Passport", id_number="Z1234567")
		ci.complete_checkin_step(res.name, "guest_ids")
	flow = ci.checkin_flow(res.name)
	assert flow["guest"]["id_number"].endswith("4567") and "Z123" not in flow["guest"]["id_number"]
	assert "guest_ids" not in {p["step"] for p in flow["pending_backfill"]}


@check("guided check-in: who assigned the room, issued keys and did each step is recorded (and a later move too)")
def t351():
	from kamra import checkin as ci
	from kamra.api import move_reservation

	room = _ci_room("G341")
	room2 = _ci_room("G341B")
	res = _ci_stay("Eval Audit", "+91 70034 10001")
	assert not res.room
	with _as_user(FD):
		flow = ci.checkin_flow(res.name)
		offered = [r["name"] for r in flow["rooms"]]
		assert room in offered, offered
		ci.assign_checkin_room(res.name, room)
		out = ci.issue_keys(res.name, 2, "C-11, C-12")
		assert out["key_result"]["manual"] is True, out["key_result"]
		ci.confirm_billing(res.name, "Guest", note="Card at desk")
	res.reload()
	assert res.room == room
	assert res.room_assigned_by == FD and res.room_assigned_at, res.room_assigned_by
	assert res.keys_issued_by == FD and res.key_count == 2 and res.keys_issued_at
	recs = json.loads(res.checkin_steps)
	assert recs["assign_room"]["by"] == FD and recs["keys"]["by"] == FD, recs
	assert recs["billing_check"]["payer"] == "Guest"
	logged = set(frappe.get_all("Agent Action Log", filters={
		"reference_name": res.name, "actor": FD}, pluck="action_type"))
	assert {"checkin_assign_room", "checkin_keys", "checkin_billing_check",
	        "room_move"} <= logged, logged
	# a later room change records whoever made it
	move_reservation(res.name, room2, reason="Guest asked")
	res.reload()
	assert res.room == room2 and res.room_assigned_by == "Administrator", res.room_assigned_by


@check("guided check-in: 'no charges to the room' is enforced by POS, the POS interface, laundry and minibar")
def t352():
	from kamra import checkin as ci
	from kamra.api import check_in, hk_post_consumable
	from kamra.laundry import request_pickup
	from kamra.pos import RoomChargesBlocked, _in_house_stay
	from kamra.pos_interface import pos_post_room_charge

	room = _ci_room("G342")
	res = _ci_stay("Eval NoPost", "+91 70034 20001", room=room)
	check_in(res.name)  # gate off: only the flag is under test here
	assert _in_house_stay(P, room, None)[1] == res.name
	with _as_user(FD):
		ci.set_room_charges(res.name, 0, reason="OTA prepaid, no card")
	assert frappe.db.get_value("Reservation", res.name, "room_charges_allowed") == 0
	_refused(_in_house_stay, P, room, None, exc=RoomChargesBlocked)
	_refused(_in_house_stay, P, None, res.name, exc=RoomChargesBlocked)
	_refused(pos_post_room_charge, P, "EVAL-T342-1", 120, "Bar check 1",
	         room="G342", exc=RoomChargesBlocked)
	assert not frappe.db.exists("External POS Charge", {"ticket_id": "EVAL-T342-1"})
	_refused(hk_post_consumable, room, "Minibar", "Water", 50, exc=RoomChargesBlocked)
	_refused(request_pickup, P, room, exc=RoomChargesBlocked)
	with _as_user(FD):
		ci.set_room_charges(res.name, 1)
	assert _in_house_stay(P, room, None)[1] == res.name


@check("guided check-in: property SOP sets what is required; GRC default follows the pack; deposit step when a policy is set")
def t353():
	from kamra import checkin as ci
	from kamra.api import check_in
	from kamra.deposit import waive_deposit
	from kamra.localization import pack_for_country, registration_card_required
	from kamra.sop import _template_steps, save_sop_template

	assert registration_card_required(pack_for_country("India")) is True
	assert registration_card_required(pack_for_country("United Arab Emirates")) is False

	# the property makes the registration card required
	meta, original = _template_steps(P, "checkin")
	steps = original
	assert any(s["step_key"] == "registration_card" and s["is_blocking"] for s in original), \
		"India property: registration card should be required by default"
	assert meta.get("name"), "check-in SOP template was not seeded"
	steps = [{**s, "is_blocking": 1 if s["step_key"] == "registration_card" else s["is_blocking"]}
	         for s in steps]
	# making the room optional is ignored: no room, no check-in
	steps = [{**s, "is_blocking": 0} if s["step_key"] == "assign_room" else s for s in steps]
	save_sop_template(name=meta["name"], steps=steps)
	required = {s["step_key"] for s in ci.checkin_steps(P) if s["is_blocking"]}
	assert {"registration_card", "assign_room"} <= required, required

	was_deposit = frappe.db.get_value("Property", P, "security_deposit_amount")
	frappe.db.set_value("Property", P, {"security_deposit_amount": 500, "deposit_pct": 0})
	frappe.clear_document_cache("Property", P)
	try:
		room = _ci_room("G343")
		res = _ci_stay("Eval Grc", "+91 70034 30001", room=room)
		frappe.db.set_value("Guest", res.guest, "id_number", "P7654321")
		with _steps_enforced(), _as_user(FD):
			ci.complete_checkin_step(res.name, "guest_ids")
			ci.confirm_billing(res.name, "Guest")
			ci.set_room_charges(res.name, 1)
			# soft: deposit + GRC open → check_in still allowed, listed as backfill
			ready = ci.check_in_readiness(res.name)
			assert ready["ready"] is True
			assert {"security_deposit", "registration_card"} <= {
				m["step"] for m in ready["pending_backfill"]}, ready
			_refused(ci.complete_checkin_step, res.name, "security_deposit",
			         contains="security deposit")
			waive_deposit(res.name, "Regular guest")
			ci.complete_checkin_step(res.name, "security_deposit")
			_refused(ci.sign_registration_card, res.name, contains="sign")
			ci.sign_registration_card(res.name, on_paper=1)
			check_in(res.name)
		assert frappe.db.get_value("Reservation", res.name, "status") == "Checked In"
	finally:
		# later checks run on the same property
		frappe.db.set_value("Property", P, "security_deposit_amount", was_deposit)
		frappe.clear_document_cache("Property", P)
		save_sop_template(name=meta["name"], steps=original)


@check("staff sign-ins: Frappe login records, only for this property's staff, Hotel Admin / Finance only")
def t354():
	from kamra.agents_api import staff_sign_ins

	outsider = "eval-outsider@example.com"
	if not frappe.db.exists("User", outsider):
		frappe.get_doc({"doctype": "User", "email": outsider, "first_name": "Out",
		                "send_welcome_email": 0, "user_type": "Website User",
		                }).insert(ignore_permissions=True)
	for user, op in ((FD, "Login"), (FD, "Logout"), (outsider, "Login")):
		frappe.get_doc({"doctype": "Activity Log", "subject": f"{user} {op}",
		                "operation": op, "status": "Success", "user": user,
		                "full_name": user}).insert(ignore_permissions=True)
	rows = staff_sign_ins(P, limit=200)
	users = {r["user"] for r in rows}
	assert FD in users and outsider not in users, users
	assert {r["operation"] for r in rows if r["user"] == FD} >= {"Login", "Logout"}
	assert all("ip_address" not in r for r in rows)
	with _as_user(FD):
		_refused(staff_sign_ins, P, exc=frappe.PermissionError)


@check("guided check-in: waiving the security deposit clears the deposit step (no extra Done tap)")
def t354b():
	"""Waive alone must mark Deposit and advance done — the desk was stuck on
	red 'required, not done' and could not check in after a waiver."""
	from kamra import checkin as ci
	from kamra.api import check_in
	from kamra.deposit import waive_deposit

	was = frappe.db.get_value("Property", P, ["security_deposit_amount", "deposit_pct"])
	frappe.db.set_value("Property", P, {"security_deposit_amount": 5000, "deposit_pct": 0})
	frappe.clear_document_cache("Property", P)
	try:
		room = _ci_room("G174B")
		res = _ci_stay("Eval Waive CI", "+91 70034 17401", room=room)
		frappe.db.set_value("Guest", res.guest, "id_number", "W174B001")
		with _steps_enforced(), _as_user(FD):
			ci.complete_checkin_step(res.name, "guest_ids")
			ci.confirm_billing(res.name, "Guest")
			ci.set_room_charges(res.name, 1)
			ci.sign_registration_card(res.name, on_paper=1)
			pending = {m["step"] for m in ci.check_in_readiness(res.name)["pending_backfill"]}
			assert "security_deposit" in pending, pending
			waive_deposit(res.name, "Owner said skip for this guest")
			ready = ci.check_in_readiness(res.name)
			dep = next(s for s in ready["steps"] if s["step"] == "security_deposit")
			assert dep["state"] == "done" and dep["applies"] == 1, dep
			assert "security_deposit" not in {m["step"] for m in ready["pending_backfill"]}
			assert ready["ready"] is True, ready
			# no complete_checkin_step for security_deposit — waive is enough
			check_in(res.name)
		assert frappe.db.get_value("Reservation", res.name, "status") == "Checked In"
	finally:
		frappe.db.set_value("Property", P, {
			"security_deposit_amount": was[0], "deposit_pct": was[1]})
		frappe.clear_document_cache("Property", P)


@check("walk-in: defer_check_in books and assigns, records what the counter did, then the guided check-in finishes it")
def t355():
	from kamra import checkin as ci
	from kamra.api import check_in, walk_in
	from kamra.patches.v43 import backfill_checkin_record

	room = _ci_room("G345")
	with _steps_enforced(), _no_deposit_policy(), _as_user(FD):
		out = walk_in(P, RT, room, add_days(nowdate(), 1), "Eval Walk Guided",
		              phone="+91 70034 50001", id_type="Passport",
		              id_number="W1234567", defer_check_in=1)
		assert out["checked_in"] == 0, out
		res = frappe.get_doc("Reservation", out["reservation"])
		assert res.status == "Confirmed" and res.room == room
		assert res.room_assigned_by == FD
		ready = ci.check_in_readiness(res.name)
		assert ready["ready"] is True and not ready["missing_required"]
		assert {"room_charges", "registration_card"} <= {
			m["step"] for m in ready["pending_backfill"]}, ready
		# plain walk-in checks the guest in immediately (room assigned; soft
		# steps stay as backfill)
		plain = walk_in(P, RT, _ci_room("G345B"), add_days(nowdate(), 1),
		                "Eval Walk Plain", phone="+91 70034 50002",
		                id_type="Passport", id_number="W1234568")
		assert frappe.db.get_value("Reservation", plain["reservation"],
		                           "status") == "Checked In"
		ci.set_room_charges(res.name, 1)
		ci.sign_registration_card(res.name, on_paper=1)
		check_in(res.name)
	assert frappe.db.get_value("Reservation", res.name, "checked_in_by") == FD
	# the backfill patch is idempotent and leaves recorded values alone
	backfill_checkin_record.execute()
	backfill_checkin_record.execute()
	assert frappe.db.get_value("Reservation", res.name, "checked_in_by") == FD
	assert frappe.db.get_value("Reservation", res.name, "room_charges_allowed") == 1



# --- Rooms screen + Today layout (#rooms-and-widgets) -------------------------

HKS = "hksup-eval@kamra.local"
OUTSIDER_FD = "fd-outsider-eval@kamra.local"


def _rooms_users():
	"""A housekeeping supervisor at the eval hotel, and a front-desk user
	restricted to another property."""
	other = _other_property("EVAL Rooms Elsewhere")
	for email, first, role in ((HKS, "Hema", "Housekeeping Supervisor"),
	                           (OUTSIDER_FD, "Omar", "Front Desk")):
		if not frappe.db.exists("User", email):
			frappe.get_doc({
				"doctype": "User", "email": email, "first_name": first,
				"enabled": 1, "user_type": "System User",
				"send_welcome_email": 0, "roles": [{"role": role}],
			}).insert(ignore_permissions=True)
	if not frappe.db.exists("User Permission", {"user": OUTSIDER_FD, "allow": "Property",
	                                            "for_value": other}):
		frappe.get_doc({"doctype": "User Permission", "user": OUTSIDER_FD,
		                "allow": "Property", "for_value": other}).insert(ignore_permissions=True)
	return other


def _rooms_in_house(room, guest_name, phone, ci, co):
	"""A stay that is in the room now (status set directly: the check-in
	flow itself is tested elsewhere)."""
	r = _res(_guest(guest_name, phone), ci, co, room=room, allow_past=1)
	frappe.db.set_value("Reservation", r.name, "status", "Checked In")
	frappe.db.set_value("Room", room, "occupancy_status", "Occupied")
	return r.name


@check("rooms board: tiles show the in-house surname, arriving / departing today and an out-of-service hold")
def t360():
	from kamra.rooms import rooms_board

	today = nowdate()
	occ = _ci_room("R360A")
	arr = _ci_room("R360B")
	held = _ci_room("R360C")
	_rooms_in_house(occ, "Eval Board Fernandes", "+91 70036 00001", add_days(today, -2), today)
	a = _res(_guest("Eval Board Arrival Khan", "+91 70036 00002"), today,
	         add_days(today, 2), room=arr)
	frappe.get_doc({"doctype": "Room Block", "property": P, "room": held,
	                "from_date": today, "to_date": add_days(today, 3),
	                "reason": "Maintenance", "block_status": "Active",
	                "note": "Leaking tap"}).insert(ignore_permissions=True)
	b = rooms_board(P)
	by = {r["name"]: r for r in b["rooms"]}
	assert by[occ]["stay"]["surname"] == "Fernandes", by[occ]["stay"]
	assert by[occ]["stay"]["departing_today"] is True
	assert by[arr]["arrival"]["reservation"] == a.name and by[arr]["stay"] is None
	assert by[held]["block"]["reason"] == "Maintenance", by[held]["block"]
	assert by[occ]["room_type_name"] == "Eval Room"
	assert b["can"]["block"] and b["can"]["supervise"] and b["can"]["money"], b["can"]


@check("room detail + availability: current stay with balance, next arrival, and booked / held / free nights")
def t361():
	from kamra.rooms import room_availability, room_detail

	today = nowdate()
	room = _ci_room("R361")
	stay = _rooms_in_house(room, "Eval Detail Rao", "+91 70036 10001", add_days(today, -1),
	                 add_days(today, 2))
	nxt = _res(_guest("Eval Detail Next", "+91 70036 10002"), add_days(today, 4),
	           add_days(today, 6), room=room)
	frappe.get_doc({"doctype": "Room Block", "property": P, "room": room,
	                "from_date": add_days(today, 8), "to_date": add_days(today, 10),
	                "reason": "Owner", "block_status": "Active"}).insert(ignore_permissions=True)
	d = room_detail(room)
	assert d["stay"]["name"] == stay and "balance_due" in d["stay"], d["stay"]
	assert d["next_arrival"]["name"] == nxt.name
	assert d["next_arrival"]["arriving_today"] is False
	assert [b["reason"] for b in d["blocks"]] == ["Owner"] and not d["blocks"][0]["current"]
	av = room_availability(room, days=14)
	states = [c["state"] for c in av["cells"]]
	# today, +1: in house (out on +2); +2, +3 free; +4, +5 next stay;
	# +6, +7 free; +8, +9 held; the rest free
	assert states[:10] == ["booked", "booked", "free", "free", "booked", "booked",
	                       "free", "free", "blocked", "blocked"], states
	assert av["cells"][4]["arrives"] is True and av["cells"][4]["reservation"] == nxt.name
	assert av["summary"] == {"free": 8, "booked": 4, "blocked": 2}, av["summary"]
	assert len(room_availability(room, days=90)["cells"]) == 31  # capped


@check("room history: who stayed (revenue), who cleaned and inspected it, tickets, status changes and moves in")
def t362():
	from kamra import api
	from kamra.rooms import room_history

	_rooms_users()
	today = nowdate()
	room = _ci_room("R362")
	room_b = _ci_room("R362B")
	past = _res(_guest("Eval History Old", "+91 70036 20001"), add_days(today, -6),
	            add_days(today, -4), room=room, allow_past=1)
	frappe.db.set_value("Reservation", past.name, "status", "Checked Out")
	frappe.get_doc({"doctype": "Folio", "property": P, "reservation": past.name,
	                "guest": past.guest, "charges": [
	                    {"posting_date": add_days(today, -6), "charge_type": "Room",
	                     "description": "Room night", "qty": 1, "rate": 1500, "amount": 1500},
	                    {"posting_date": add_days(today, -5), "charge_type": "Room",
	                     "description": "Room night", "qty": 1, "rate": 1500, "amount": 1500},
	                ]}).insert(ignore_permissions=True)
	task = frappe.get_doc({"doctype": "Housekeeping Task", "property": P, "room": room,
	                       "task_type": "Checkout Clean", "priority": "High",
	                       "status": "Pending", "assigned_to_user": "hk@kamra.local"}
	                      ).insert(ignore_permissions=True).name
	with _as_user("hk@kamra.local"):
		api.hk_update_task(task, "In Progress")
		api.hk_update_task(task, "Done")
	with _as_user(HKS):
		api.set_housekeeping_status(room, "Inspected")
	api.create_ticket(P, "AC not cooling", "Maintenance", room=room)
	mover = _res(_guest("Eval History Mover", "+91 70036 20002"), add_days(today, 1),
	             add_days(today, 3), room=room_b)
	api.move_reservation(mover.name, room, reason="Guest asked for a view")

	h = room_history(room)
	lakshmi = frappe.db.get_value("User", "hk@kamra.local", "full_name")
	hema = frappe.db.get_value("User", HKS, "full_name")
	assert [s["name"] for s in h["stays"]] == [past.name], h["stays"]
	assert h["stays"][0]["revenue"] == 3000 and h["stays"][0]["revenue_source"] == "posted", h["stays"]
	hk = next(x for x in h["housekeeping"] if x["task"] == task)
	assert hk["cleaned_by"] == lakshmi and hk["cleaned_at"], hk
	assert hk["started_by"] == lakshmi and hk["minutes"] is None, hk  # seconds: not a real clean
	assert any("Inspected" in c["change"] and c["by"] == hema for c in h["status_changes"]), \
		h["status_changes"]
	assert [x["subject"] for x in h["tickets"]] == ["AC not cooling"], h["tickets"]
	mv = h["moves"]
	assert len(mv) == 1 and mv[0]["direction"] == "in" and mv[0]["other_room_number"] == "R362B", mv
	assert mv[0]["guest_name"] == "Eval History Mover"
	# the room it left sees the same move going out
	out = room_history(room_b)["moves"]
	assert len(out) == 1 and out[0]["direction"] == "out", out
	# a housekeeping supervisor sees the story but not the money
	with _as_user(HKS):
		h2 = room_history(room)
	assert h2["money"] is False and "revenue" not in h2["stays"][0], h2["stays"]


@check("room insights: nights, occupancy net of out-of-service nights, posted revenue and cleaning time, per room")
def t363():
	from kamra.rooms import room_insights

	_rooms_users()
	today = nowdate()
	room = _ci_room("R363")
	gone = _res(_guest("Eval Insight Gone", "+91 70036 30001"), add_days(today, -5),
	            add_days(today, -2), room=room, allow_past=1)
	frappe.db.set_value("Reservation", gone.name, "status", "Checked Out")
	_rooms_in_house(room, "Eval Insight Here", "+91 70036 30002", add_days(today, -1),
	          add_days(today, 2))
	# a stay from before the window never counts
	old = _res(_guest("Eval Insight Old", "+91 70036 30003"), add_days(today, -60),
	           add_days(today, -58), room=room, allow_past=1)
	frappe.db.set_value("Reservation", old.name, "status", "Checked Out")
	frappe.get_doc({"doctype": "Folio", "property": P, "reservation": gone.name,
	                "guest": gone.guest, "charges": [
	                    {"posting_date": add_days(today, -5), "charge_type": "Room",
	                     "description": "Room night", "qty": 1, "rate": 1000, "amount": 1000},
	                    {"posting_date": add_days(today, -4), "charge_type": "Room",
	                     "description": "Room night", "qty": 1, "rate": 1000, "amount": 1000},
	                    {"posting_date": add_days(today, -4), "charge_type": "Misc",
	                     "description": "Sundry", "qty": 1, "rate": 300, "amount": 300},
	                ]}).insert(ignore_permissions=True)
	frappe.get_doc({"doctype": "Room Block", "property": P, "room": room,
	                "from_date": add_days(today, -12), "to_date": add_days(today, -9),
	                "reason": "Maintenance", "block_status": "Active"}).insert(ignore_permissions=True)
	task = frappe.get_doc({"doctype": "Housekeeping Task", "property": P, "room": room,
	                       "task_type": "Checkout Clean", "priority": "High",
	                       "status": "Pending"}).insert(ignore_permissions=True)
	task.status = "In Progress"
	task.save(ignore_permissions=True)
	task.status = "Done"
	task.save(ignore_permissions=True)
	# the clean took 25 minutes
	frappe.db.sql("""UPDATE `tabVersion` SET creation = DATE_ADD(creation, INTERVAL 25 MINUTE)
		WHERE ref_doctype = 'Housekeeping Task' AND docname = %s AND data LIKE %s""",
	              (task.name, '%"Done"%'))

	ins = room_insights(P, days=30, refresh=1)
	row = next(r for r in ins["rooms"] if r["room"] == room)
	assert row["nights"] == 4 and row["stays"] == 2, row  # 3 departed + 1 in house
	assert row["out_of_service_nights"] == 3 and row["sellable_nights"] == 27, row
	assert row["occupancy_pct"] == round(100 * 4 / 27, 1), row
	assert row["revenue"] == 2000, row  # room charges only, in the window
	assert row["avg_clean_minutes"] == 25 and row["cleans"] == 1, row
	assert ins["summary"]["room_nights"] >= 4 and ins["days"] == 30
	assert room_insights(P, days=13, refresh=1)["days"] == 30  # only the offered windows
	# cached: a second call returns the same numbers without recomputing
	assert room_insights(P, days=30)["rooms"] == ins["rooms"]
	with _as_user(HKS):
		hs = room_insights(P, days=30, refresh=1)
	assert hs["money"] is False and hs["summary"]["revenue"] is None
	assert next(r for r in hs["rooms"] if r["room"] == room)["revenue"] is None


@check("rooms: property scope and role gates on board, detail, availability, history and insights")
def t364():
	from kamra.rooms import (room_availability, room_detail, room_history,
	                         room_insights, rooms_board)

	other = _rooms_users()
	room = _ci_room("R364")
	with _as_user(OUTSIDER_FD):
		for fn, args in ((rooms_board, (P,)), (room_detail, (room,)),
		                 (room_availability, (room,)), (room_history, (room,)),
		                 (room_insights, (P,))):
			_refused(fn, *args, exc=frappe.PermissionError)
		# their own property is fine
		assert rooms_board(other)["rooms"] == []
	# a housekeeping attendant works from the task list, not the board
	with _as_user("hk@kamra.local"):
		_refused(rooms_board, P, exc=frappe.PermissionError)
		_refused(room_detail, room, exc=frappe.PermissionError)
	with _as_user(HKS):
		b = rooms_board(P)
		assert b["can"]["supervise"] and not b["can"]["block"] and not b["can"]["money"], b["can"]
	_refused(room_detail, "EVAL Hotel-NOPE", exc=frappe.DoesNotExistError)


@check("Today layout: per-user save and load, hotel default by Hotel Admin only, cleaned on the way in")
def t365():
	from kamra import today_layout as tl
	from kamra.settings import clear_cache

	_rooms_users()
	try:
		for u in (FD, "hk@kamra.local"):
			with _as_user(u):
				tl.reset_today_layout(P)
		with _as_user(FD):
			got = tl.get_today_layout(P)
			assert got["source"] == "default", got["source"]
			assert got["layout"] == tl.normalize(tl.DEFAULT_LAYOUT)
			assert got["layout"]["hidden"] == ["open_tasks"]
			assert got["can_set_default"] is False
			_refused(tl.save_today_layout_default, P, {"left": ["arrivals"]},
			         exc=frappe.PermissionError)
		# the Hotel Admin's hotel default: arrivals hidden, open tasks shown
		hotel = {"top": ["kpis"], "left": ["departures", "arrivals"],
		         "right": ["open_tasks", "room_board", "in_house", "housekeeping"],
		         "hidden": ["arrivals"]}
		admin = tl.save_today_layout_default(P, hotel)
		assert admin["can_set_default"] is True
		with _as_user(FD):
			got = tl.get_today_layout(P)
			assert got["source"] == "property", got["source"]
			assert got["layout"]["hidden"] == ["arrivals"], got["layout"]
			assert got["layout"]["right"][0] == "open_tasks"
			# the person's own layout: junk dropped, KPI strip kept on top,
			# a widget left out comes back in its home column
			mine = tl.save_today_layout({
				"top": [], "left": ["in_house", "kpis", "in_house", "nope"],
				"right": ["arrivals"], "hidden": ["kpis", "nope"]}, P)
			assert mine["source"] == "user"
			lay = mine["layout"]
			assert lay["top"] == ["kpis"] and lay["left"][0] == "in_house", lay
			assert lay["left"].count("in_house") == 1 and "nope" not in lay["left"], lay
			assert lay["right"][0] == "arrivals" and "room_board" in lay["right"], lay
			assert "booking_requests" in lay["left"] and lay["hidden"] == ["kpis", "open_tasks"], lay
			assert tl.get_today_layout(P)["layout"] == lay
		# per user: the housekeeper still sees the hotel default
		with _as_user("hk@kamra.local"):
			assert tl.get_today_layout(P)["source"] == "property"
		with _as_user(FD):
			assert tl.reset_today_layout(P)["source"] == "property"
		# resetting the hotel default goes back to the classic Today
		assert tl.save_today_layout_default(P, None)["property_default"] == \
			tl.normalize(tl.DEFAULT_LAYOUT)
		with _as_user(FD):
			assert tl.get_today_layout(P)["source"] == "default"
	finally:
		for u in (FD, "hk@kamra.local"):
			with _as_user(u):
				tl.reset_today_layout(P)
		clear_cache(P)


# Every endpoint the tape chart's stay panel (and its drag-to-move / drag-to-
# resize confirm steps) calls. The screen once offered no visible action on a
# bar; this keeps the endpoints behind its buttons callable by the desk.
TAPE_PANEL_ENDPOINTS = (
	"kamra.api.tape_chart", "kamra.api.tape_chart_hourly",
	"kamra.api.movable_rooms", "kamra.api.room_move_preview",
	"kamra.api.move_reservation", "kamra.api.amend_stay_preview",
	"kamra.api.amend_stay", "kamra.api.set_stay_times",
	"kamra.checkin.checkin_flow", "kamra.api.checkout_context",
)


@check("tape chart stay panel: its endpoints are whitelisted for the desk, and move / change dates round-trip with the price confirmed")
def t356():
	import os
	import re

	from kamra import api

	endpoints = set(TAPE_PANEL_ENDPOINTS)
	# the screen's own calls, read from the source when the app ships it
	root = os.path.dirname(frappe.get_app_path("kamra"))
	for rel in ("frontend/src/screens/TapeChart.tsx",
	            "frontend/src/components/RoomChangeDialog.tsx"):
		path = os.path.join(root, rel)
		if os.path.exists(path):
			with open(path, encoding="utf-8") as f:  # nosemgrep: frappe-security-file-traversal -- path is root plus a fixed list of source files; eval script, no user input
				endpoints |= set(re.findall(r"[\"'](kamra\.[a-z_]+\.[a-z_]+)[\"']", f.read()))
	fns = {ep: frappe.get_attr(ep) for ep in sorted(endpoints)}  # imports = registers
	whitelisted = {f"{w.__module__}.{w.__name__}" for w in frappe.whitelisted}
	for ep, fn in fns.items():
		assert f"{fn.__module__}.{fn.__name__}" in whitelisted, f"{ep} is not whitelisted"
		roles = getattr(fn, "_kamra_roles", None)
		assert roles is None or "Front Desk" in roles, f"{ep}: desk cannot call it ({roles})"

	room_a = _ci_room("G356A")
	room_b = _ci_room("G356B")
	g = _guest("Eval Tape Panel", "+91 70035 60001")
	ci_d, co_d = add_days(nowdate(), 3), add_days(nowdate(), 5)
	res = _res(g, ci_d, co_d, room=room_a)
	with _as_user(FD):
		tape = api.tape_chart(P, start_date=nowdate(), days=14)
		bar = next((b for r in tape["rooms"] if r["name"] == room_a
		            for b in r["bookings"] if b["name"] == res.name), None)
		assert bar, "the stay is not on the tape chart"
		for k in ("room", "status", "check_in_date", "check_out_date", "is_day_use"):
			assert k in bar, f"tape bar lacks {k}"
		movable = {r["name"]: r for r in api.movable_rooms(res.name)}
		assert movable[room_b]["free"] and movable[room_a]["current"], movable.get(room_b)
		pv = api.room_move_preview(res.name, room_b)
		for k in ("current_amount", "new_amount", "difference", "needs_confirmation", "in_house"):
			assert k in pv, f"room_move_preview lacks {k}"
		api.move_reservation(res.name, room_b, reason="Guest request",
		                     confirm_price=1 if pv["needs_confirmation"] else 0)
		assert frappe.db.get_value("Reservation", res.name, "room") == room_b
		new_co = add_days(co_d, 1)
		dv = api.amend_stay_preview(res.name, ci_d, new_co)
		assert dv["new_amount"] > dv["current_amount"], dv
		api.amend_stay(res.name, ci_d, new_co,
		               confirm_price=1 if dv["needs_confirmation"] else 0)
	assert str(frappe.db.get_value("Reservation", res.name, "check_out_date")) == str(new_co)


# --- POS: cancel / void / remove, orders list, guest panel (t370-t376) ---

SUP = "evalsup@kamra.local"
SUP_PIN = "4826"


def _pos_outlet(name, tables="T1\nT2\nT3", prop=None):
	from kamra import pos
	outlet = frappe.get_doc({
		"doctype": "POS Outlet", "property": prop or P, "outlet_name": name,
		"outlet_type": "Restaurant", "gst_rate": 5, "tables": tables,
	}).insert(ignore_permissions=True).name
	dishes = []
	for n, price in (("Dosa", 120), ("Coffee", 60)):
		dishes.append(frappe.get_doc({
			"doctype": "Menu Item", "property": prop or P, "outlet": outlet,
			"item_name": f"{name} {n}", "category": "Food", "price": price,
			"is_veg": 1, "available": 1, "prep_station": "Kitchen",
		}).insert(ignore_permissions=True).name)
	for t in (tables or "").split():
		pos.mark_table_clean(outlet, t)  # redis survives the rollback
	return outlet, dishes


def _supervisor():
	"""A Hotel Admin with a cashier PIN, who approves voids at a captain's till."""
	if not frappe.db.exists("User", SUP):
		frappe.get_doc({
			"doctype": "User", "email": SUP, "first_name": "Sunita",
			"enabled": 1, "user_type": "System User", "send_welcome_email": 0,
			"roles": [{"role": "Hotel Admin"}],
		}).insert(ignore_permissions=True)
	if not frappe.db.exists("Cashier PIN", SUP):
		frappe.get_doc({"doctype": "Cashier PIN", "user": SUP,
		                "pin": SUP_PIN}).insert(ignore_permissions=True)
	frappe.cache.delete_value(f"kamra_supervisor_pin_fails:{SUP}")
	return SUP


def _tile(outlet, table):
	from kamra import pos
	return next(t for t in pos.table_map(outlet)["tables"] if t["table"] == table)


@check("POS: a captain cancels a bill nothing was sent to the kitchen for; reason kept, logged, table freed")
def t370():
	from kamra import pos
	outlet, (dosa, coffee) = _pos_outlet("Eval Cancel Unfired")
	with _as_user(FD):
		o = pos.create_order(outlet, [{"menu_item": dosa, "qty": 2},
		                              {"menu_item": coffee, "qty": 1}],
		                     table_no="T1", order_type="Dine In")
		assert _tile(outlet, "T1")["state"] == "running"
		assert pos.order_detail(o["order"])["kitchen_lines"] == 0
		_refused(pos.cancel_order, o["order"], "  ", contains="reason")
		out = pos.cancel_order(o["order"], "guest left before ordering")
	assert out["status"] == "Cancelled" and out["kitchen_lines"] == 0, out
	assert out["voided_value"] == 300, out
	doc = frappe.get_doc("POS Order", o["order"])
	assert doc.cancel_reason == "guest left before ordering", doc.cancel_reason
	assert doc.cancelled_by == FD and doc.cancelled_at and not doc.cancel_approved_by
	assert all(it.voided for it in doc.items) and doc.order_total == 0
	log = frappe.get_all("Agent Action Log", filters={
		"action_type": "pos_cancel_order", "reference_name": o["order"]},
		fields=["actor", "rationale"])
	assert log and log[0].actor == FD and "guest left" in log[0].rationale, log
	# freed: nothing was served, so the table is vacant, not waiting on a clean
	t1 = _tile(outlet, "T1")
	assert t1["state"] == "vacant" and t1["bills"] == 0, t1
	# a closed bill cannot be cancelled again
	with _as_user(FD):
		_refused(pos.cancel_order, o["order"], "again", contains="closed")
	# the voids report lists it, with who did it
	from kamra.reports import void_allowance_report
	rows = void_allowance_report(P, nowdate(), nowdate())
	assert any(r["action"] == "POS bill cancelled" and r["pos_order"] == o["order"]
	           and r["actor"] == FD for r in rows), rows[:3]


@check("POS: once the kitchen has items, cancelling needs a supervisor's PIN; never an agent; the kitchen sees it cancelled")
def t371():
	from kamra import pos
	outlet, (dosa, coffee) = _pos_outlet("Eval Cancel Fired")
	sup = _supervisor()
	with _as_user(FD):
		o = pos.send_order(outlet, [{"menu_item": dosa, "qty": 1},
		                            {"menu_item": coffee, "qty": 1}],
		                   table_no="T2", order_type="Dine In")
		assert pos.order_detail(o["order"])["kitchen_lines"] == 2
		_refused(pos.cancel_order, o["order"], "walked out",
		         exc=pos.SupervisorRequired)
		_refused(pos.cancel_order, o["order"], "walked out",
		         supervisor=sup, supervisor_pin="0000", contains="Wrong")
		# a captain cannot approve for themselves
		_refused(pos.cancel_order, o["order"], "walked out",
		         supervisor=FD, supervisor_pin="0000", exc=frappe.PermissionError)
	frappe.cache.delete_value(f"kamra_supervisor_pin_fails:{sup}")
	# an agent never voids fired food, PIN or not
	frappe.flags.kamra_agent_call = "MCP"
	try:
		_refused(pos.cancel_order, o["order"], "agent tries",
		         supervisor=sup, supervisor_pin=SUP_PIN, exc=pos.SupervisorRequired)
	finally:
		frappe.flags.kamra_agent_call = None
	assert frappe.db.get_value("POS Order", o["order"], "status") == "Preparing"
	with _as_user(FD):
		out = pos.cancel_order(o["order"], "walked out", reason_code="VOID-GUEST",
		                       supervisor=sup, supervisor_pin=SUP_PIN)
	assert out["approved_by"] == sup and out["kitchen_lines"] == 2, out
	doc = frappe.get_doc("POS Order", o["order"])
	assert doc.status == "Cancelled" and doc.cancel_approved_by == sup
	assert doc.cancel_reason.startswith("VOID-GUEST"), doc.cancel_reason
	# the food is voided, never deleted: both lines remain, struck, approved
	assert len(doc.items) == 2 and all(it.voided and it.void_approved_by == sup
	                                   and it.voided_by == FD for it in doc.items)
	# the kitchen keeps the ticket, every line cancelled, until it acknowledges
	q = [t for t in pos.kitchen_queue(P, outlet=outlet) if t["name"] == o["order"]]
	assert q and {i["state"] for i in q[0]["items"]} == {"cancelled"}, q
	for it in doc.items:
		pos.acknowledge_void(o["order"], it.name)
	assert not [t for t in pos.kitchen_queue(P, outlet=outlet) if t["name"] == o["order"]]
	log = frappe.get_all("Agent Action Log", filters={
		"action_type": "pos_cancel_order", "reference_name": o["order"]},
		fields=["actor", "approver"])
	assert log and log[0].actor == FD and log[0].approver == sup, log
	# a paid bill is closed: no cancel
	p = pos.send_order(outlet, [{"menu_item": coffee, "qty": 1}], order_type="Takeaway")
	pos.pay_order(p["order"], "Cash")
	_refused(pos.cancel_order, p["order"], "too late", contains="closed")


@check("POS: lines not sent to the kitchen come off freely; sent lines need a supervisor to void")
def t372():
	from kamra import pos
	outlet, (dosa, coffee) = _pos_outlet("Eval Remove Line")
	sup = _supervisor()
	with _as_user(FD):
		o = pos.create_order(outlet, [{"menu_item": dosa, "qty": 1},
		                              {"menu_item": coffee, "qty": 2}], table_no="T3")
		rows = {i["item_name"]: i["row"] for i in pos.order_detail(o["order"])["items"]}
		out = pos.remove_item(o["order"], rows["Eval Remove Line Coffee"])
		assert out["order_total"] == 120, out
		d = pos.order_detail(o["order"])
		assert [i["item_name"] for i in d["items"]] == ["Eval Remove Line Dosa"], d["items"]
		# the last line cannot come off: cancel the bill instead
		_refused(pos.remove_item, o["order"], rows["Eval Remove Line Dosa"],
		         contains="last item")
		# send it; a sent line cannot be removed, and voiding it needs approval
		pos.send_round(o["order"], [{"menu_item": coffee, "qty": 1}])
		sent = next(i for i in pos.order_detail(o["order"])["items"]
		            if i["kot_status"] == "Fired")
		_refused(pos.remove_item, o["order"], sent["row"], contains="Void it")
		_refused(pos.void_item, o["order"], sent["row"], "spilled",
		         exc=pos.SupervisorRequired)
		v = pos.void_item(o["order"], sent["row"], "spilled",
		                  supervisor=sup, supervisor_pin=SUP_PIN)
		assert v["approved_by"] == sup, v
	line = frappe.db.get_value("POS Order Item", sent["row"],
	                           ["voided", "voided_by", "void_approved_by"], as_dict=True)
	assert line.voided and line.voided_by == FD and line.void_approved_by == sup, line
	assert frappe.get_all("Agent Action Log", filters={
		"action_type": "pos_void_item", "reference_name": o["order"], "approver": sup})
	# a line never sent can still be voided with a reason, no approval
	with _as_user(FD):
		o2 = pos.create_order(outlet, [{"menu_item": dosa, "qty": 1},
		                               {"menu_item": coffee, "qty": 1}], table_no="T1")
		r2 = pos.order_detail(o2["order"])["items"][1]["row"]
		assert pos.void_item(o2["order"], r2, "wrong item")["approved_by"] is None
	# an agent removes unsent lines but never voids sent ones
	frappe.flags.kamra_agent_call = "MCP"
	try:
		o3 = pos.send_order(outlet, [{"menu_item": dosa, "qty": 1}], table_no="T2")
		r3 = pos.order_detail(o3["order"])["items"][0]["row"]
		_refused(pos.void_item, o3["order"], r3, "agent", exc=pos.SupervisorRequired)
	finally:
		frappe.flags.kamra_agent_call = None


@check("POS orders list: one outlet's bills with their state, search, carried-over open bills; scoped to the property")
def t373():
	from kamra import pos
	outlet, (dosa, coffee) = _pos_outlet("Eval Orders List")
	a = pos.create_order(outlet, [{"menu_item": dosa, "qty": 1}], table_no="T1")
	b = pos.send_order(outlet, [{"menu_item": coffee, "qty": 1}], table_no="T2")
	c = pos.send_order(outlet, [{"menu_item": coffee, "qty": 2}], order_type="Takeaway",
	                   customer_name="Meera Orders", customer_phone="+91 70036 30001")
	pos.pay_order(c["order"], "Card")
	d = pos.create_order(outlet, [{"menu_item": dosa, "qty": 1}], table_no="T3")
	pos.cancel_order(d["order"], "changed mind")
	# an open bill from yesterday is carried into today's list
	e = pos.create_order(outlet, [{"menu_item": dosa, "qty": 1}], order_type="Takeaway")
	frappe.db.set_value("POS Order", e["order"], "creation",
	                    frappe.utils.add_days(frappe.utils.now_datetime(), -1),
	                    update_modified=False)
	other_outlet, (od, _oc) = _pos_outlet("Eval Orders Elsewhere", tables="")
	pos.create_order(other_outlet, [{"menu_item": od, "qty": 1}], order_type="Takeaway")

	lst = pos.orders_list(outlet)
	by = {r["name"]: r for r in lst["rows"]}
	assert set(by) == {a["order"], b["order"], c["order"], d["order"], e["order"]}, set(by)
	assert by[a["order"]]["state"] == "open" and by[b["order"]]["state"] == "sent"
	assert by[c["order"]]["state"] == "paid" and by[c["order"]]["payment_mode"] == "Card"
	assert by[d["order"]]["state"] == "cancelled" and by[d["order"]]["amount"] == 120
	assert by[d["order"]]["cancel_reason"] == "changed mind"
	assert by[e["order"]]["carried"] == 1 and by[e["order"]]["state"] == "open"
	assert lst["counts"]["open"] == 2 and lst["counts"]["cancelled"] == 1, lst["counts"]
	assert [r["name"] for r in pos.orders_list(outlet, q="Meera")["rows"]] == [c["order"]]
	assert [r["name"] for r in pos.orders_list(outlet, state="sent")["rows"]] == [b["order"]]
	# yesterday alone: just the carried bill's day
	y = pos.orders_list(outlet, date=str(frappe.utils.add_days(nowdate(), -1)))
	assert [r["name"] for r in y["rows"]] == [e["order"]], y["rows"]
	_refused(pos.orders_list, outlet, date="2036-01-01", to_date="2037-03-01",
	         contains="one year")
	# a full year is allowed (the history screen reaches back that far)
	pos.orders_list(outlet, date="2036-03-01", to_date="2037-03-01")

	# property scope: a captain limited to this hotel cannot list another's
	p2 = "Eval POS Other Hotel"
	if not frappe.db.exists("Property", p2):
		frappe.get_doc({"doctype": "Property", "property_name": p2,
		                "city": "Elsewhere"}).insert(ignore_permissions=True)
	far, (fd_dish, _x) = _pos_outlet("Eval Far Outlet", tables="", prop=p2)
	pos.create_order(far, [{"menu_item": fd_dish, "qty": 1}], order_type="Takeaway")
	added = []
	for prop in (P,):
		if not frappe.db.exists("User Permission", {"user": FD, "allow": "Property",
		                                            "for_value": prop}):
			added.append(frappe.get_doc({
				"doctype": "User Permission", "user": FD, "allow": "Property",
				"for_value": prop}).insert(ignore_permissions=True).name)
	try:
		with _as_user(FD):
			assert {r["name"] for r in pos.orders_list(outlet)["rows"]} == set(by)
			_refused(pos.orders_list, far, exc=frappe.PermissionError)
	finally:
		for n in added:
			frappe.delete_doc("User Permission", n, ignore_permissions=True, force=True)


@check("POS guest panel: attach a walk-in by phone or name, reuse the profile, see past bills at this outlet; phone masked, no ID data")
def t374():
	from kamra import pos
	outlet, (dosa, coffee) = _pos_outlet("Eval Walk-in")
	phone = "+91 70036 40001"
	with _as_user(FD):
		assert pos.find_customer(outlet, "70036 40001") == []
		o1 = pos.create_order(outlet, [{"menu_item": dosa, "qty": 1}], table_no="T1")
		_refused(pos.attach_customer, outlet, o1["order"], phone=phone,
		         contains="name")
		a1 = pos.attach_customer(outlet, o1["order"], customer_name="Kiran Visitor",
		                         phone=phone)
		assert a1["created"] and a1["full_name"] == "Kiran Visitor", a1
	guest = a1["guest"]
	assert frappe.db.get_value("POS Order", o1["order"], "guest") == guest
	pos.pay_order(o1["order"], "Cash")  # settled by the cashier
	with _as_user(FD):
		# same phone typed another way finds the same profile
		new = pos.attach_customer(outlet, phone="7003640001")
		assert new["guest"] == guest and not new["created"], new
		o2 = pos.create_order(outlet, [{"menu_item": coffee, "qty": 1}],
		                      table_no="T2", guest=guest)
		assert frappe.db.get_value("POS Order", o2["order"], "customer_name") == "Kiran Visitor"
		found = pos.find_customer(outlet, "Kiran Vis")
		row = next(r for r in found if r["guest"] == guest)
		assert row["visits"] == 2 and row["phone"] == "•••• 0001", row
		panel = pos.guest_panel(outlet, order=o2["order"])
	assert panel["kind"] == "customer" and panel["guest"]["full_name"] == "Kiran Visitor"
	assert panel["guest"]["phone"] == "•••• 0001", panel["guest"]
	h = panel["history"]
	assert h["bills"] == 1 and h["orders"][0]["name"] == o1["order"], h
	assert h["orders"][0]["state"] == "paid" and "Dosa" in h["orders"][0]["items"], h
	# only what service needs: no ID, email, address or birth date
	for k in ("id_number", "id_type", "email", "address_line", "date_of_birth",
	          "id_file", "nationality"):
		assert k not in panel["guest"], k
	# a supervisor sees the full number
	assert pos.guest_panel(outlet, order=o2["order"])["guest"]["phone"] == phone
	# take the customer off the bill
	with _as_user(FD):
		pos.attach_customer(outlet, o2["order"], clear=1)
	assert not frappe.db.get_value("POS Order", o2["order"], "guest")


@check("POS guest panel: an in-house guest's stay and the room-charge block; a blocked room cannot be charged")
def t375():
	from kamra import pos
	from kamra.pos import RoomChargesBlocked
	outlet, (dosa, _c) = _pos_outlet("Eval In House")
	res, _folio = _in_house("Eval Diner Guest", "+91 70036 50001", nowdate(),
	                        frappe.utils.add_days(nowdate(), 2), _ledger_room("P365"))
	frappe.db.set_value("Guest", res.guest, "guest_notes", "No peanuts")
	frappe.db.set_value("Reservation", res.name, "room_charges_allowed", 0)
	with _as_user(FD):
		rooms = {r["room"]: r for r in pos.in_house_rooms(P)}
		assert rooms[res.room]["room_charges_allowed"] == 0, rooms[res.room]
		panel = pos.guest_panel(outlet, room=res.room)
		assert panel["kind"] == "in_house", panel
		assert panel["stay"]["room_charges_allowed"] == 0 and panel["stay"]["room_number"] == "P365"
		assert panel["guest"]["notes"] == "No peanuts", panel["guest"]
		_refused(pos.create_order, outlet, [{"menu_item": dosa, "qty": 1}],
		         room=res.room, exc=RoomChargesBlocked)
		walk = pos.create_order(outlet, [{"menu_item": dosa, "qty": 1}], table_no="T1")
		_refused(pos.charge_to_room, walk["order"], res.room, exc=RoomChargesBlocked)
	frappe.db.set_value("Reservation", res.name, "room_charges_allowed", 1)
	with _as_user(FD):
		o = pos.create_order(outlet, [{"menu_item": dosa, "qty": 1}], room=res.room,
		                     order_type="Room Service")
		assert frappe.db.get_value("POS Order", o["order"], "guest") == res.guest
		p = pos.guest_panel(outlet, order=o["order"])
		assert p["kind"] == "in_house" and p["stay"]["room_charges_allowed"] == 1, p
		assert p["stay"]["reservation"] == res.name
		# a room bill is for its guest: no walk-in can be attached to it
		_refused(pos.attach_customer, outlet, o["order"], customer_name="Someone",
		         contains="in-house")


@check("POS: a bill nobody sent is flagged with its age; End of Day names it; the agent tool cancels only unsent bills")
def t376():
	from kamra import night_audit, pos
	from kamra.business_date import get_business_date
	from kamra.mcp_tools import TOOLS, call_tool
	outlet, (dosa, _c) = _pos_outlet("Eval Stale Bill")
	old = pos.create_order(outlet, [{"menu_item": dosa, "qty": 1}], table_no="T1")
	frappe.db.set_value("POS Order", old["order"], "creation",
	                    frappe.utils.add_to_date(frappe.utils.now_datetime(), minutes=-40),
	                    update_modified=False)
	fresh = pos.create_order(outlet, [{"menu_item": dosa, "qty": 1}], table_no="T2")
	rows = {r["name"]: r for r in pos.open_orders(outlet)}
	assert rows[old["order"]]["stale"] == 1 and rows[old["order"]]["age_min"] >= 39
	assert rows[fresh["order"]]["stale"] == 0
	chk = night_audit.check_open_pos_bills(P, get_business_date(P))
	item = next(i for i in chk["items"] if i["order"] == old["order"])
	assert item["state"] == "open, not sent to kitchen", item
	spec = {s.name: s for s in TOOLS}
	out = call_tool(spec["pos_cancel_order"], {"order": old["order"],
	                                           "reason": "forgotten bill"}, P)
	assert out["status"] == "Cancelled"
	assert frappe.get_all("Agent Action Log", filters={
		"action_type": "pos_cancel_order", "reference_name": old["order"],
		"action_channel": "MCP"})
	fired = pos.send_order(outlet, [{"menu_item": dosa, "qty": 1}], table_no="T3")
	_refused(call_tool, spec["pos_cancel_order"],
	         {"order": fired["order"], "reason": "agent"}, P, exc=pos.SupervisorRequired)
	assert frappe.db.get_value("POS Order", fired["order"], "status") == "Preparing"
	listed = call_tool(spec["pos_orders"], {"outlet": outlet, "state": "open"}, P)
	assert [r["name"] for r in listed["rows"]] == [fresh["order"]], listed["rows"]
@check("extra guests: booked on top of a full room, capped at the extra beds")
def t217():
	"""The desk fills Adults up to what the room sleeps and books anyone
	above it as extra guests - not by typing more adults."""
	villa = frappe.get_doc({
		"doctype": "Room Type", "property": P, "room_type_code": "EXG",
		"room_type_name": "Eval Extra Guests", "base_price": 22500,
		"base_occupancy": 8, "extra_adult_price": 1600,
		"adults_capacity": 14, "children_capacity": 6,
		"max_extra_beds": 3, "tax_percent": 0,
	}).insert(ignore_permissions=True)
	g = _guest("Eval Extra Count", "+91 70000 00217")
	base = {
		"doctype": "Reservation", "property": P, "guest": g,
		"room_type": villa.name, "check_in_date": "2031-05-01",
		"check_out_date": "2031-05-02", "auto_price": 1, "adults": 14,
	}

	# 14 adults + 2 extra guests, with a reason and the agreed price
	r = frappe.get_doc({
		**base, "over_capacity_guests": 2, "over_capacity_charge": 3200,
		"over_capacity_reason": "Group of 16, sharing the king beds",
	}).insert(ignore_permissions=True)
	full = 22500 + 6 * 1600
	assert abs(float(r.amount_before_tax) - (full + 3200)) < 0.01, r.amount_before_tax

	# extra guests with no reason: refused
	try:
		frappe.get_doc({**base, "over_capacity_guests": 1}).insert(ignore_permissions=True)
		raise AssertionError("an extra guest went in with no reason given")
	except frappe.ValidationError as e:
		assert "arrangement" in str(e), str(e)

	# more than the extra beds: refused even with a reason
	try:
		frappe.get_doc({
			**base, "over_capacity_guests": 4,
			"over_capacity_reason": "Tried it on",
		}).insert(ignore_permissions=True)
		raise AssertionError("4 extra guests went in past 3 extra beds")
	except frappe.ValidationError as e:
		assert "max 3" in str(e), str(e)




def _villa_like_treepie(code):
	"""A whole-villa room type priced the way Naadi's Songs of the Treepie
	is: per head below six on weekdays, the house rate for 6-8, children
	inside the base occupancy, 14 + 3 by arrangement."""
	rt = frappe.get_doc({
		"doctype": "Room Type", "property": P, "room_type_code": code,
		"room_type_name": f"Eval Villa {code}", "room_category": "Villa",
		"base_price": 22500, "base_occupancy": 8, "extra_adult_price": 1600,
		"small_group_max_adults": 6, "small_group_price_per_adult": 4000,
		"small_group_days": "sun, mon, tue, wed, thu", "small_group_whole_stay": 1,
		"children_within_base_occupancy": 1, "child_price": 1200,
		"free_child_age": 4, "child_age_limit": 11,
		"adults_capacity": 14, "children_capacity": 6, "max_extra_beds": 3,
		"tax_percent": 0,
	}).insert(ignore_permissions=True)
	frappe.get_doc({
		"doctype": "Room", "property": P, "room_number": code,
		"room_type": rt.name, "housekeeping_status": "Clean",
	}).insert(ignore_permissions=True)
	return rt.name


TUE, WED, THU = "2031-04-08", "2031-04-09", "2031-04-10"


def _row(rows, rt):
	return next(r for r in rows if r["room_type"] == rt)


@check("villa: children count toward the small-group tier and fill the base occupancy")
def t260():
	from kamra.pricing import quote
	villa = _villa_like_treepie("EVT1")
	expect = {(4, 2): 22500, (5, 1): 22500, (3, 2): 20000,
	          (8, 2): 24900, (9, 1): 25300, (3, 0): 12000}
	for (a, c), want in expect.items():
		got = quote(P, villa, TUE, WED, a, c)["room_total"]
		assert got == want, f"{a} adults + {c} children: {got} != {want}"
	# a room sold per person keeps charging every child (the flag is off)
	assert quote(P, RT, "2030-02-01", "2030-02-02", 3, 1)["room_total"] == 5500


@check("child ages: under the free age is free and uncounted, over the limit is an adult")
def t261():
	from kamra import public_api
	from kamra.pricing import party_by_age
	villa = _villa_like_treepie("EVT2")
	rt = frappe.get_doc("Room Type", villa)
	assert party_by_age(rt, 2, [3, 8, 13]) == (3, 1, 1)
	row = _row(public_api.search_stay(P, TUE, WED, adults=2, child_ages=[3, 8, 13]), villa)
	assert (row["adults"], row["children"], row["infants"]) == (3, 1, 1), row
	# four paying guests (the 3-year-old is free): 4 x 4,000
	assert row["quote"]["room_total"] == 16000, row["quote"]["room_total"]
	# a JSON string, as a form post sends it, reads the same
	row = _row(public_api.search_stay(P, TUE, WED, adults=2, child_ages="[3, 8, 13]"), villa)
	assert row["infants"] == 1, row


@check("group size: 15-17 needs the host to confirm, 18 or more is refused")
def t262():
	from kamra import public_api
	villa = _villa_like_treepie("EVT3")
	ok = _row(public_api.search_stay(P, TUE, WED, adults=14), villa)
	assert ok["available"] and not ok.get("needs_confirmation"), ok
	ask = _row(public_api.search_stay(P, TUE, WED, adults=15), villa)
	assert ask["available"] and ask["needs_confirmation"], ask
	no = _row(public_api.search_stay(P, TUE, WED, adults=18), villa)
	assert no["available"] is False and no["reason"] == public_api.TOO_MANY_GUESTS, no
	assert no["quote"] is None

	frappe.set_user("Guest")  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow
	try:
		out = public_api.book(
			property=P, room_type=villa, check_in_date=TUE, check_out_date=WED,
			guest_name="Eval Big Group", phone="+919812300262", adults=15)
		try:
			public_api.book(
				property=P, room_type=villa, check_in_date=TUE, check_out_date=WED,
				guest_name="Eval Too Big", phone="+919812300263", adults=18)
			raise AssertionError("18 guests were booked")
		except frappe.ValidationError as e:
			assert "cannot accommodate" in str(e), e
	finally:
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- controlled user context switch; target user is validated and scope-limited in this flow
	assert out["status"] == "Requested" and out["needs_confirmation"], out
	res = frappe.get_doc("Reservation", out["reservation"])
	assert res.over_capacity_guests == 1 and res.over_capacity_reason, res.as_dict()


@check("a stay needs at least one adult")
def t263():
	from kamra import public_api
	try:
		public_api.search_stay(P, TUE, WED, adults=0, children=2)
		raise AssertionError("a party of two children was quoted")
	except frappe.ValidationError as e:
		assert "at least one adult" in str(e).lower(), e


@check("holiday season: house rate for small parties, minimum stay, full payment, flagged")
def t264():
	from kamra import public_api
	villa = _villa_like_treepie("EVT4")
	frappe.db.set_value("Property", P, {"booking_payment_mode": "Advance percent",
	                                    "advance_percent": 50})
	frappe.clear_document_cache("Property", P)
	normal = _row(public_api.search_stay(P, TUE, THU, adults=4), villa)["quote"]
	assert normal["room_total"] == 2 * 16000, normal["room_total"]
	assert abs(normal["advance_due"] - normal["amount_after_tax"] / 2) < 0.01, normal

	frappe.get_doc({
		"doctype": "Season", "property": P, "season_name": "EVAL Holiday",
		"room_type": villa, "start_date": TUE, "end_date": TUE,
		"adjustment_type": "Amount", "adjustment_value": 0, "priority": 60,
		"minimum_nights": 2, "non_refundable": 1, "full_payment": 1,
		"no_small_group": 1, "is_holiday": 1,
	}).insert(ignore_permissions=True)
	one = _row(public_api.search_stay(P, TUE, WED, adults=4), villa)
	assert one["available"] is False and "at least 2 nights" in one["reason"], one
	two = _row(public_api.search_stay(P, TUE, THU, adults=4), villa)
	q = two["quote"]
	# a holiday stay is a house-rate stay throughout, like a weekend
	assert q["room_total"] == 2 * 22500, q["room_total"]
	assert q["is_holiday"] and q["stay_rules"]["holiday"] == "EVAL Holiday", q["stay_rules"]
	assert abs(q["advance_due"] - q["amount_after_tax"]) < 0.01, (q["advance_due"], q["amount_after_tax"])

# ── check-in / check-out on the desk: tills, open bills, roles (t380-t383) ──

EVAL_FIN = "eval.fin@kamra.local"


def _fin_user():
	if not frappe.db.exists("User", EVAL_FIN):
		frappe.get_doc({
			"doctype": "User", "email": EVAL_FIN, "first_name": "Farah",
			"enabled": 1, "user_type": "System User",
			"send_welcome_email": 0, "roles": [{"role": "Finance"}],
		}).insert(ignore_permissions=True)
	return EVAL_FIN


def _close_my_till():
	from kamra.cashier import close_session
	for s in frappe.get_all("Cashier Session", filters={
			"property": P, "user": frappe.session.user, "status": "Open"}, pluck="name"):
		close_session(s, 0)


@check("till: check-out shows a closed till, the desk opens it in place, then collects (no dead end)")
def t380():
	from kamra import api
	from kamra.cashier import open_session
	res, folio = _settle_stay("E370", "+91 70000 03700")
	with _as_user("frontdesk@kamra.local"):
		_close_my_till()
		s = api.checkout_context(res.name)
		t = s["till"]
		assert (t["required"], t["open"], t["can_open"]) == (True, False, True), t
		assert not s["till_open"] and t["property"] == P, s["till_open"]
		b = next(b for b in s["blockers"] if b["code"] == "till_closed")
		assert b["step"] == "settle" and "Open it here" in b["message"], b
		# the money call itself still refuses without a till: the server agrees
		_refused(api.add_folio_payment, folio, "Cash", 100, contains="NO_OPEN_SESSION")
		# the same open_session the Cashier screen uses, from the sheet
		open_session(P, 500)
		s = api.checkout_context(res.name)
		assert s["till"]["open"] and s["till_open"], s["till"]
		assert not any(b["code"] == "till_closed" for b in s["blockers"]), s["blockers"]
		for c in s["collect"]:
			api.add_folio_payment(c["folio"], "Cash", c["amount"])
		s = api.checkout_context(res.name)
		assert s["settled"] and s["actions"]["can_checkout"], s["blockers"]
		assert s["actions"]["can_check_out_role"], s["actions"]
		# the check-in sheet carries the same till state for its deposit step
		assert api_checkin_till(res.name)["open"]
		_close_my_till()


def api_checkin_till(reservation):
	from kamra.checkin import _till
	return _till(frappe.db.get_value("Reservation", reservation, "property"))


@check("till: a property that runs without tills takes payments with none; till-only moves still need one")
def t381():
	from kamra import api, cashier
	from kamra import settings as st
	res, folio = _settle_stay("E371", "+91 70000 03710")
	st.save_settings(P, "finance", {"use_cashier_tills": 0})
	try:
		with _as_user("frontdesk@kamra.local"):
			_close_my_till()
			assert cashier.require_open_session(P) is None
			s = api.checkout_context(res.name)
			assert s["till"]["open"] and not s["till"]["required"], s["till"]
			assert not any(b["code"] == "till_closed" for b in s["blockers"]), s["blockers"]
			for c in s["collect"]:
				api.add_folio_payment(c["folio"], "Card", c["amount"])
			assert api.checkout_context(res.name)["settled"]
			# a paid-out is a drawer movement: it still needs a till
			_refused(cashier.post_paid_out, P, 50, "Eval courier", contains="NO_OPEN_SESSION")
	finally:
		st.save_settings(P, "finance", {"use_cashier_tills": 1})
	with _as_user("frontdesk@kamra.local"):
		_refused(cashier.require_open_session, P, contains="NO_OPEN_SESSION")


@check("open bills at check-out: laundry still at the laundry says why, moves to Ready, hands back and bills")
def t382():
	from kamra import api, laundry
	res, folio = _settle_stay("E372", "+91 70000 03720")
	if not frappe.db.exists("Laundry Rate", {"property": P, "item_name": "Eval Shirt"}):
		frappe.get_doc({"doctype": "Laundry Rate", "property": P, "item_name": "Eval Shirt",
		                "service_type": "Wash & Iron", "rate": 100}).insert(ignore_permissions=True)
	o = laundry.collect_laundry(P, room=res.room, items=[
		{"item_name": "Eval Shirt", "service_type": "Wash & Iron", "qty": 2}])["order"]
	laundry.laundry_status(o, "In Process")
	s = api.checkout_context(res.name)
	b = next(x for x in s["pending_bills"] if x["name"] == o)
	assert b["kind"] == "laundry" and b["billable"] and b["amount"] == 200, b
	assert b["can_mark_ready"] and not b["can_post_to_room"], b
	assert "Still at the laundry" in b["hint"] and b["pieces_missing"] == 2, b
	n = next(n for n in s["notices"] if n["code"] == "pending_bills")
	assert "do not stop the check-out" in n["message"], n
	# open bills never block: they are a warning on the sheet
	assert not any(x["code"] == "pending_bills" for x in s["blockers"]), s["blockers"]
	# Finance may see the bill but not move the bag
	with _as_user(_fin_user()):
		fb = next(x for x in api.checkout_context(res.name)["pending_bills"] if x["name"] == o)
		assert not fb["can_act"] and not fb["can_mark_ready"], fb
		assert "Front Desk" in fb["act_roles"], fb
	owed = s["totals"]["owed"]
	laundry.laundry_status(o, "Ready")
	b = next(x for x in api.checkout_context(res.name)["pending_bills"] if x["name"] == o)
	assert b["can_post_to_room"] and not b["can_mark_ready"], b
	# what the sheet does on "Hand back and post to room"
	laundry.return_items(o, {i["row"]: i["qty"] for i in b["items"]})
	laundry.deliver_laundry(o)
	s = api.checkout_context(res.name)
	assert not [x for x in s["pending_bills"] if x["name"] == o], s["pending_bills"]
	assert s["totals"]["owed"] > owed + 199, (owed, s["totals"])


@check("check-out roles and retries: Finance settles but is told it can't check out; a lost snapshot is retried")
def t383():
	from kamra import api, checkout
	res, folio = _settle_stay("E373", "+91 70000 03730")
	with _as_user(_fin_user()):
		s = api.checkout_context(res.name)
		assert not s["actions"]["can_check_out_role"], s["actions"]
		b = next(b for b in s["blockers"] if b["code"] == "role_cannot_check_out")
		assert b["step"] == "confirm" and "Front Desk" in b["message"], b
		assert not s["actions"]["can_checkout"]
		_refused(api.check_out, res.name, exc=frappe.PermissionError)
	assert api.checkout_context(res.name)["actions"]["can_check_out_role"]
	# a deadlock drops the whole transaction, savepoint and all: the
	# context is computed again instead of answering with a server error
	from unittest.mock import patch
	real, calls = checkout._checkout_context, []

	def flaky(name):
		calls.append(name)
		if len(calls) == 1:
			raise checkout.SnapshotLost("kamra_checkout_ctx")
		return real(name)
	# the retry's full rollback is stubbed so the harness savepoint survives
	with patch.object(checkout, "_checkout_context", side_effect=flaky), \
			patch.object(frappe.db, "rollback"):
		s = checkout.checkout_context(res.name)
	assert len(calls) == 2 and s["reservation"]["name"] == res.name, calls



# ── AI access over MCP and bulk room assignment (t384-t386) ──

EVAL_MCP = "eval.mcp@kamra.local"


def _mcp_user(*roles):
	"""A Front Desk user holding exactly these extra roles."""
	if not frappe.db.exists("User", EVAL_MCP):
		frappe.get_doc({
			"doctype": "User", "email": EVAL_MCP, "first_name": "Mira",
			"enabled": 1, "user_type": "System User", "send_welcome_email": 0,
			"roles": [{"role": "Front Desk"}],
		}).insert(ignore_permissions=True)
	from kamra.mcp_access import MCP_ROLES, ensure_roles
	ensure_roles()
	u = frappe.get_doc("User", EVAL_MCP)
	keep = [r.role for r in u.roles if r.role not in MCP_ROLES]
	u.set("roles", [{"role": r} for r in [*keep, *roles]])
	u.save(ignore_permissions=True)
	return EVAL_MCP


@check("room assignment for arrivals: apply re-checks every pair, skips bad ones with a reason, and repeating it changes nothing")
def t384():
	from kamra.allocation import apply_allocation, suggest_allocation
	rt, (r1, r2) = _t300_rooms("T3M")
	today, tomorrow = nowdate(), add_days(nowdate(), 1)
	a = frappe.get_doc({
		"doctype": "Reservation", "property": P, "guest": _guest("Eval Assign A", "+91 70000 38401"),
		"room_type": rt, "check_in_date": today, "check_out_date": tomorrow,
		"adults": 2, "auto_price": 1,
	}).insert(ignore_permissions=True)
	b = frappe.get_doc({
		"doctype": "Reservation", "property": P, "guest": _guest("Eval Assign B", "+91 70000 38402"),
		"room_type": rt, "check_in_date": today, "check_out_date": tomorrow,
		"adults": 2, "auto_price": 1,
	}).insert(ignore_permissions=True)
	plan = {p_["reservation"]: p_["suggested_room"]
	        for p_ in suggest_allocation(P, today)["proposals"]
	        if p_["reservation"] in (a.name, b.name)}
	assert set(plan) == {a.name, b.name} and set(plan.values()) == {r1, r2}, plan
	# the same room twice, a room of another type, an unknown stay
	out = apply_allocation(P, [
		{"reservation": a.name, "room": r1},
		{"reservation": b.name, "room": r1},
		{"reservation": b.name, "room": ROOM},
		{"reservation": "RES-NOPE", "room": r2},
	])
	assert out["executed"] == [{"reservation": a.name, "room": r1}], out
	reasons = {(s_["reservation"], s_["room"]): s_["reason"] for s_ in out["skipped"]}
	assert "Already in that room" not in reasons.get((b.name, r1), ""), reasons
	assert "free" in reasons[(b.name, r1)] or "another arrival" in reasons[(b.name, r1)], reasons
	assert "another type" in reasons[(b.name, ROOM)], reasons
	assert "this property" in reasons[("RES-NOPE", r2)], reasons
	assert frappe.db.get_value("Reservation", b.name, "room") in (None, ""), "b got a room"
	# repeat: nothing new happens
	again = apply_allocation(P, [{"reservation": a.name, "room": r1}])
	assert again["executed"] == [] and again["skipped"][0]["reason"] == "Already in that room", again
	# a room taken out of order since the preview is refused
	frappe.db.set_value("Room", r2, "housekeeping_status", "Out of Order")
	late = apply_allocation(P, [{"reservation": b.name, "room": r2}])
	assert not late["executed"] and "no longer free" in late["skipped"][0]["reason"], late


@check("MCP access: no role sees nothing, MCP Read only reads, MCP Manage writes; admins always pass; changes apply at once")
def t385():
	from kamra.mcp_access import (NO_ACCESS, READ_ONLY, access_refusal, mcp_level,
	                              permitted_tools, property_policy, tool_refusal)
	from kamra.mcp_tools import BY_NAME, allowed_tools
	assert mcp_level("Administrator") == "manage"
	user = _mcp_user()
	assert access_refusal(user) == NO_ACCESS
	policy = property_policy(P)
	assert policy.enabled and not policy.read_only and not policy.blocked, policy
	with _as_user(user):
		visible = allowed_tools(property=P)
	assert not permitted_tools(visible, mcp_level(user), policy)
	_mcp_user("MCP Read")
	assert access_refusal(user, P) is None and mcp_level(user) == "read"
	with _as_user(user):
		names = {t.name for t in permitted_tools(allowed_tools(property=P), mcp_level(user), policy)}
	assert "quote" in names and "assign_rooms_preview" in names, names
	assert not any(BY_NAME[n].mutating for n in names), [n for n in names if BY_NAME[n].mutating]
	assert tool_refusal(BY_NAME["create_booking"], "read", policy) == READ_ONLY
	# promoted: the very next listing has the writes, no reconnect needed
	_mcp_user("MCP Manage")
	with _as_user(user):
		names = {t.name for t in permitted_tools(allowed_tools(property=P), mcp_level(user), policy)}
	assert "create_booking" in names and "assign_rooms_apply" in names, sorted(names)[:10]
	# still bounded by the normal role: Front Desk never gets rate tools
	assert "set_room_rate" not in names
	# city ledger aging is the same gate as Finance → Ledgers (Front Desk may)
	assert "city_ledger_aging" in names
	assert not BY_NAME["city_ledger_aging"].mutating
	assert BY_NAME["city_ledger_aging"].inject_property
	assert BY_NAME["city_ledger_aging"].module == "finance"


@check("city_ledger_aging MCP tool: Housekeeping cannot see it; Front Desk can")
def t385b():
	from kamra.mcp_tools import BY_NAME, allowed_tools, tool_allowed

	spec = BY_NAME["city_ledger_aging"]
	assert spec.dotted == "ledger.city_ledger_aging"
	assert not tool_allowed(spec, roles={"Housekeeping"})
	assert tool_allowed(spec, roles={"Front Desk"})
	with _as_user("hk@kamra.local"):
		names = {t.name for t in allowed_tools(property=P)}
	assert "city_ledger_aging" not in names
	with _as_user(FD):
		names = {t.name for t in allowed_tools(property=P)}
	assert "city_ledger_aging" in names


@check("MCP property switches: AI access off refuses everyone, read-only drops writes even for MCP Manage, blocked tools vanish")
def t386():
	from kamra.mcp_access import (access_overview, access_refusal, property_policy,
	                              set_mcp_level, set_mcp_policy, tool_refusal)
	from kamra.mcp_tools import BY_NAME
	user = _mcp_user("MCP Manage")
	try:
		set_mcp_policy(P, read_only=1, blocked_tools=["quote"])
		pol = property_policy(P)
		assert pol.read_only and pol.blocked == {"quote"}, pol
		assert "read-only" in tool_refusal(BY_NAME["create_booking"], "manage", pol)
		assert "blocked" in tool_refusal(BY_NAME["quote"], "manage", pol)
		assert tool_refusal(BY_NAME["availability"], "manage", pol) is None
		_refused(set_mcp_policy, P, blocked_tools=["no_such_tool"], contains="Unknown tool")
		set_mcp_policy(P, enabled=0)
		assert "turned off" in access_refusal(user, P)
		assert "turned off" in access_refusal("Administrator", P)
		# the admin screen changes a person's level and leaves their other roles
		set_mcp_level(P, user, "read")
		roles = set(frappe.get_roles(user))
		assert "MCP Read" in roles and "MCP Manage" not in roles and "Front Desk" in roles, roles
		row = next(s_ for s_ in access_overview(P)["staff"] if s_["user"] == user)
		assert row["level"] == "read", row
		# and a Front Desk user can't use the screen at all
		with _as_user(FD):
			_refused(access_overview, P, exc=frappe.PermissionError)
	finally:
		set_mcp_policy(P, enabled=1, read_only=0, blocked_tools=[])


@check("Brazil pack: tax rates, labels and Region list entry")
def t387():
	from kamra.localization import pack_for, supported_countries
	from kamra.pricing import quote

	pname = "EVAL Brazil Hotel"
	if not frappe.db.exists("Property", pname):
		frappe.get_doc({
			"doctype": "Property", "property_name": pname,
			"city": "São Paulo", "country": "Brazil", "currency": "BRL",
		}).insert(ignore_permissions=True)
	rt_name = f"{pname}-STD"
	if not frappe.db.exists("Room Type", rt_name):
		rt = frappe.get_doc({
			"doctype": "Room Type", "property": pname,
			"room_type_code": "STD", "room_type_name": "Standard",
			"base_price": 4000, "base_occupancy": 2,
			"adults_capacity": 2, "children_capacity": 1,
		}).insert(ignore_permissions=True).name
	else:
		rt = rt_name

	pack = pack_for(pname)
	assert pack.__name__.endswith("brazil"), pack.__name__
	assert "Brazil" in {c["country"] for c in supported_countries()}
	q = quote(pname, rt, "2031-06-01", "2031-06-02", 2, 0)
	assert q["nightly"][0]["gst_rate"] == 5, q["nightly"]
	assert pack.fnb_tax_rate(pname) == 5.0, pack.fnb_tax_rate(pname)
	loc = pack.locale(frappe.get_doc("Property", pname))
	assert loc["currency_symbol"] == "R$", loc
	assert loc["currency"] == "BRL", loc
	assert loc["locale"] == "pt-BR", loc
	ctx = pack.invoice_context(frappe.get_doc("Property", pname))
	assert ctx["tax_id_label"] == "CNPJ / CPF", ctx
	assert ctx["tax_label"] == "ISS", ctx


def execute():
	global RT, ROOM
	# frappe.locale.get_locale_value crashes (UnboundLocalError) when no
	# language is set on the session — true in bare CI consoles.
	frappe.local.lang = frappe.local.lang or "en"
	# most checks call api.check_in directly to set up an in-house stay; the
	# guided check-in's required steps are switched back on by the checks
	# that test them (t350-t355, _steps_enforced)
	frappe.flags.kamra_checkin_steps_off = True
	# night audit (and friends) commit mid-run in production; under the
	# harness a commit would release the savepoint and leak test data
	real_commit, frappe.db.commit = frappe.db.commit, lambda *a, **k: None
	frappe.db.savepoint("eval_start")
	try:
		RT, ROOM = setup()
		for fn in (t1, t2, t3, t3b, t3c, t3d, t3f, t3g, t3h, t3i, t3j, t4,
		           t5, t6, t7, t8, t9, t10, t11, t12, t13, t14, t15, t16,
		           t17, t18, t19, t20, t21, t22, t23, t24, t25, t26, t27, t28,
		           t29, t30, t31, t32, t33, t34, t35, t36, t37, t38, t39, t39b, t39c, t39d,
		           t40, t41, t42, t43, t44, t45, t46, t47, t47b, t47c, t47d, t48,
		           t49, t50, t51, t53, t54, t55, t56, t57, t58, t59, t60, t61,
		           t62, t63, t64, t65, t66, t67, t68, t69, t70, t71, t72, t73,
		           t74, t75, t76, t81, t82, t82b, t82c, t83, t84, t85, t86, t87,
		           t90, t91, t92, t93, t94, t95, t96, t97, t98, t100, t101, t102,
		           t103, t104, t110, t111, t112, t113, t114, t115, t120, t121, t140, t141,
		           t142, t143, t150, t151, t152, t153, t170, t171, t172, t173, t174, t176,
		           t177, t178, t179, t160, t161, t162, t163, t164, t165, t166, t167, t130,
		           t131, t132, t133, t134, t135, t136, t137, t138, t139, t180, t181, t182,
		           t183, t184, t185, t186, t190, t191, t192, t193, t194,
		           t200, t201, t202, t203, t204,
		           t205, t206, t207, t208, t209, t210, t211, t212, t213, t214,
		           t215, t216, t300, t301, t302, t303, t304, t305, t220, t221, t223, t222, t224,
		           t320, t321, t322, t323, t324, t325, t326, t327, t328, t310, t311, t312, t313,
		           t314, t315, t316, t317, t318, t330, t331, t332, t333, t334, t335, t336,
		           t225, t226, t227, t228, t229, t230, t340, t341, t342, t343, t344,
		           t350, t351, t352, t353, t354, t355, t356,
		           t360, t361, t362, t363, t364, t365,
		           t370, t371, t372, t373, t374, t375, t376,
		           t217, t260, t261, t262, t263, t264,
		           t380, t381, t382, t383, t384, t385, t386, t387):
			fn()
	finally:
		frappe.flags.kamra_checkin_steps_off = False
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- controlled user context switch; restores the console user after the checks
		frappe.db.commit = real_commit
		frappe.db.rollback(save_point="eval_start")

	passed = sum(1 for _, ok, _ in RESULTS if ok)
	print(f"\n=== Kamra eval harness: {passed}/{len(RESULTS)} passed ===")
	for name, ok, msg in RESULTS:
		print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {msg}" if msg else ""))
	RESULTS.clear()
