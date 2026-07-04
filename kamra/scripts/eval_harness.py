"""Kamra eval harness — deterministic checks over the governed tool layer.

The PRD's risk register calls for an eval harness before agents go live:
every rule an agent relies on (pricing, availability, guardrails, SLA)
gets a check here. Runs in a transaction and rolls back — no data left
behind.

Run via bench console:
    from kamra.scripts.eval_harness import execute; execute()
"""

import frappe
from frappe.utils import add_days, nowdate

P = "EVAL Hotel"
RESULTS = []


def check(name):
	def wrap(fn):
		def run():
			try:
				fn()
				RESULTS.append((name, True, ""))
			except AssertionError as e:
				RESULTS.append((name, False, str(e)))
			except Exception as e:
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
	if not frappe.db.exists("Property", P):
		frappe.get_doc({
			"doctype": "Property", "property_name": P, "city": "Testville",
			"gst_mode": "Slab", "gst_slab_threshold": 7500,
			"gst_rate_low": 5, "gst_rate_high": 18,
		}).insert(ignore_permissions=True)
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


def _res(guest, ci, co, room=None, day_use=0):
	return frappe.get_doc({
		"doctype": "Reservation", "property": P, "guest": guest,
		"room_type": RT, "room": room, "check_in_date": ci,
		"check_out_date": co, "adults": 2, "is_day_use": day_use,
		"auto_price": 1,
	}).insert(ignore_permissions=True)


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
	folio = frappe.get_doc("Folio", folio_name)
	assert post_room_night(folio, res, nowdate()) is True
	folio = frappe.get_doc("Folio", folio_name)
	assert post_room_night(folio, res, nowdate()) is False, "double posted"
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
	fd = frappe.get_doc("Folio", main)
	post_room_night(fd, res, "2030-07-01")
	second = split_folio(res.name, "Company")
	fd = frappe.get_doc("Folio", main)
	transfer_charge(main, fd.charges[0].name, second)
	a = frappe.get_doc("Folio", main)
	b = frappe.get_doc("Folio", second)
	assert a.grand_total + b.grand_total == 4200, (a.grand_total, b.grand_total)


@check("ticket SLA: priority sets due window")
def t12():
	from frappe.utils import get_datetime, now_datetime, time_diff_in_seconds
	t = frappe.get_doc({
		"doctype": "Service Ticket", "property": P, "subject": "eval",
		"category": "Housekeeping", "priority": "Urgent",
	}).insert(ignore_permissions=True)
	mins = time_diff_in_seconds(get_datetime(t.due_by), now_datetime()) / 60
	assert 13 <= mins <= 16, mins


def execute():
	global RT, ROOM
	frappe.db.savepoint("eval_start")
	try:
		RT, ROOM = setup()
		for fn in (t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11, t12):
			fn()
	finally:
		frappe.db.rollback(save_point="eval_start")

	passed = sum(1 for _, ok, _ in RESULTS if ok)
	print(f"\n=== Kamra eval harness: {passed}/{len(RESULTS)} passed ===")
	for name, ok, msg in RESULTS:
		print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {msg}" if msg else ""))
	RESULTS.clear()
