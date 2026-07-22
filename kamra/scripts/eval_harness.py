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
	# the governed agent user posts public/HK/laundry charges. Role + user
	# only - deliberately NOT seed_rbac_v2.ensure_agent_user(): its _grant
	# writes custom DocPerms, and custom perms REPLACE the standard doctype
	# perms, revoking other roles' access on a fresh (CI) site. The standard
	# doctype JSONs already carry the Kamra Agent role.
	if not frappe.db.exists("Role", "Kamra Agent"):
		frappe.get_doc({
			"doctype": "Role", "role_name": "Kamra Agent", "desk_access": 0,
		}).insert(ignore_permissions=True)
	if not frappe.db.exists("User", "agent@kamra.local"):
		frappe.get_doc({
			"doctype": "User", "email": "agent@kamra.local",
			"first_name": "Kamra", "last_name": "Agent", "enabled": 1,
			"user_type": "System User", "send_welcome_email": 0,
			"roles": [{"role": "Kamra Agent"}],
		}).insert(ignore_permissions=True)
	if not frappe.db.exists("Property", P):
		frappe.get_doc({
			"doctype": "Property", "property_name": P, "city": "Testville",
			"gst_mode": "Slab", "gst_slab_threshold": 7500,
			"gst_rate_low": 5, "gst_rate_high": 18,
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


@check("closed folio is frozen: charges immutable, payments still settle")
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
	inv = close_folio(folio)
	assert inv.startswith("INV-"), inv
	fd = frappe.get_doc("Folio", folio)
	fd.charges[0].amount = 1
	try:
		fd.save(ignore_permissions=True)
		raise AssertionError("closed folio accepted a charge edit")
	except frappe.ValidationError:
		pass
	# settling the balance is still allowed
	out = api.add_folio_payment(folio, "UPI", 4200)
	assert out["balance"] == 0, out["balance"]


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
	api.hk_assign_task(task, "Administrator")
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
	frappe.set_user(u)
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
		frappe.set_user("Administrator")


@check("POS: order fires KOT, delivery posts F&B to the room folio with discount")
def t25():
	from kamra import pos
	from kamra.folio import post_room_night
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
	# settling frees the table into Cleaning; Mark clean returns it to vacant
	assert [t for t in pos.table_map(outlet)["tables"]
	        if t["table"] == "T2"][0]["state"] == "cleaning"
	pos.mark_table_clean(outlet, "T2")
	assert [t for t in pos.table_map(outlet)["tables"]
	        if t["table"] == "T2"][0]["state"] == "vacant"

	# a second order the same day gets the next KOT number
	o2 = pos.create_order(outlet, [{"menu_item": mi1, "qty": 1}],
	                      order_type="Takeaway")
	assert pos.fire_kot(o2["order"])["kot_no"] == fk["kot_no"] + 1
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
	from kamra.folio import post_room_night

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

	# an eZee-flavoured export: renamed headers, DD/MM dates, quoted name
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
	frappe.set_user("Guest")
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
		frappe.set_user("Administrator")

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
	api.check_out(res.name)  # the desk path - runs the retention scrub
	assert frappe.db.get_value("Guest", g, "id_number").startswith("•"), \
		frappe.db.get_value("Guest", g, "id_number")
	assert not frappe.db.get_value("Guest", g, "id_file")
	assert not frappe.get_all("File", filters={
		"attached_to_doctype": "Guest", "attached_to_name": g,
		"attached_to_field": "id_file"})
	frappe.db.set_value("Property", P, "id_retention", "Store")


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
		for fn in (t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11, t12, t13, t14, t15, t16, t17, t18, t19, t20, t21, t22, t23, t24, t25, t26, t27, t28, t29, t30, t31, t32, t33, t34):
			fn()
	finally:
		frappe.db.commit = real_commit
		frappe.db.rollback(save_point="eval_start")

	passed = sum(1 for _, ok, _ in RESULTS if ok)
	print(f"\n=== Kamra eval harness: {passed}/{len(RESULTS)} passed ===")
	for name, ok, msg in RESULTS:
		print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {msg}" if msg else ""))
	RESULTS.clear()
