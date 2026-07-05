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
		"doctype": "Company", "company_name": "EVAL Corp",
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
		"doctype": "Company", "company_name": "EVAL Group Corp",
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
	ns = _res(g3, add_days(nowdate(), -1), nowdate())
	run_night_audit(P, nowdate())
	assert frappe.db.get_value("Reservation", ns.name, "status") == "No Show"
	ns_folio = frappe.db.get_value(
		"Folio", {"reservation": ns.name, "folio_type": "Guest"})
	assert ns_folio, "no-show folio not opened"
	charges = frappe.get_doc("Folio", ns_folio).charges
	assert any("No-show" in (c.description or "") for c in charges)


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
	# frappe.locale.get_locale_value crashes (UnboundLocalError) when no
	# language is set on the session — true in bare CI consoles.
	frappe.local.lang = frappe.local.lang or "en"
	# night audit (and friends) commit mid-run in production; under the
	# harness a commit would release the savepoint and leak test data
	real_commit, frappe.db.commit = frappe.db.commit, lambda *a, **k: None
	frappe.db.savepoint("eval_start")
	try:
		RT, ROOM = setup()
		for fn in (t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11, t12, t13, t14, t15, t16, t17, t18):
			fn()
	finally:
		frappe.db.commit = real_commit
		frappe.db.rollback(save_point="eval_start")

	passed = sum(1 for _, ok, _ in RESULTS if ok)
	print(f"\n=== Kamra eval harness: {passed}/{len(RESULTS)} passed ===")
	for name, ok, msg in RESULTS:
		print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {msg}" if msg else ""))
	RESULTS.clear()
