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
	pos.deliver_order(o["order"])
	# once it has left the kitchen there is nothing to recall
	try:
		pos.recall_prepared(o["order"])
		raise AssertionError("recall allowed after delivery")
	except frappe.ValidationError:
		pass


@check("kitchen display: coursing holds & fires, cook's clock starts at fire, allergen alarm")
def t39():
	from kamra import pos
	from frappe.utils import add_to_date, now_datetime
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
	assert frappe.db.exists("Stock Ledger Entry",
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
		"Stock Ledger Entry",
		{"ingredient": paneer, "reference_name": o3["order"], "reason": "Consumed"})
	assert starter_moves == 1, f"starter deducted {starter_moves} times"

	# the optional in "optional recipe": no recipe, no ledger, no noise
	rows_before = frappe.db.count("Stock Ledger Entry")
	o4 = pos.create_order(kitchen, [{"menu_item": water, "qty": 3}], table_no="S4")
	r4 = pos.fire_kot(o4["order"])
	assert frappe.db.count("Stock Ledger Entry") == rows_before, "a recipe-less dish moved stock"
	assert r4["stock_alerts"] == [], r4["stock_alerts"]

	# the cache must never drift from the ledger - the one invariant that
	# cannot bend, because every other number here is derived from it
	for outlet, ing in ((kitchen, paneer), (kitchen, chicken)):
		total = frappe.db.sql(
			"""select sum(qty_change) from `tabStock Ledger Entry`
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
	assert frappe.db.exists("Stock Ledger Entry",
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
	assert frappe.db.exists("Stock Ledger Entry",
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

	from kamra import api, public_api as pub
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
	from PIL import Image as _Image
	import io as _io
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
		api.check_out(res.name)
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
	api.check_out(res2.name)
	assert len(_id_files(res2.name)) == 1, "Store mode discarded the scan anyway"
	for n in _id_files(res2.name):  # this one has no retention to clean it up
		frappe.delete_doc("File", n, ignore_permissions=True, delete_permanently=True)


@check("ID document: desk captures and verifies, roles gate the look")
def t43():
	from kamra import api, id_documents, public_api as pub
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
	api.check_out(res.name)  # the desk path - runs the retention scrub
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
	api.check_out(res.name)
	assert not frappe.db.get_value("Guest", g, "id_file")
	assert not frappe.db.get_value("Guest", g, "address_proof_file")
	frappe.db.set_value("Property", P, "id_retention", "Store")


@check("stay ledger: advance/deposit kinds, guarded refunds, actual times on GRC")
def t37():
	from kamra import api
	from kamra.folio import post_room_night

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

	# the dict showcase / qr_menu / precheckin_info embed as ui_locale
	pub = _public_locale("EVAL Bali Hotel")
	assert pub == {"currency_symbol": "Rp", "locale": "id-ID"}, pub
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


@check("WhatsApp: native Meta send, booking flow, inbound -> ticket")
def t48():
	from kamra import whatsapp  # nosemgrep: frappe-monkey-patching-not-allowed -- offline eval harness stubs the outbound transport for tests; not a production code path
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
		                                  "subject": ("like", "WhatsApp:%")})
		assert tickets, "inbound message did not raise a Service Ticket"

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

	from PIL import Image

	from kamra.api import (_scrub_stay_ids, check_in, update_occupants,
	                       upload_occupant_id)

	from frappe.utils import add_days, nowdate

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
	from kamra.channels import channex  # nosemgrep: frappe-monkey-patching-not-allowed -- offline eval harness stubs the outbound transport for tests; not a production code path

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
		for fn in (t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11, t12, t13,
		           t14, t15, t16, t17, t18, t19, t20, t21, t22, t23, t24,
		           t25, t26, t27, t28, t29, t30, t31, t32, t33, t34, t35,
		           t36, t37, t38, t39, t40, t41, t42, t43, t44, t45, t46, t47, t48, t49, t50, t51, t53,
		           t54, t55, t56, t57, t58, t59, t60, t61, t62, t63, t64,
		           t65, t66, t67, t68, t69, t70,
		           t71, t72, t73, t74, t75, t76):
			fn()
	finally:
		frappe.db.commit = real_commit
		frappe.db.rollback(save_point="eval_start")

	passed = sum(1 for _, ok, _ in RESULTS if ok)
	print(f"\n=== Kamra eval harness: {passed}/{len(RESULTS)} passed ===")
	for name, ok, msg in RESULTS:
		print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {msg}" if msg else ""))
	RESULTS.clear()
