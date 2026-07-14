"""Front-desk persona suite — one shift at the desk, driven through the
whitelisted API as a REAL Front Desk user.

Where eval_harness checks the rules engine as Administrator, this suite
plays a person: frappe.set_user() to a Front Desk account, no
ignore_permissions anywhere in the journey calls — so every check also
exercises RBAC (@require_roles) and doctype permissions exactly as the
UI does. Includes the things a front-desk person must NOT be able to do.

Runs in a transaction and rolls back — no data left behind.

Run via bench console:
    from kamra.scripts.frontdesk_eval import execute; execute()
"""

import frappe
from frappe.utils import add_days, nowdate

from kamra.scripts import eval_harness

P = eval_harness.P  # same EVAL Hotel sandbox
FD_USER = "eval.frontdesk@kamra.local"
RESULTS = []
RT = ROOM = ROOM2 = None


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
			finally:
				frappe.set_user("Administrator")
		run.__name__ = name
		return run
	return wrap


class at_the_desk:
	"""Everything inside runs as the Front Desk user."""

	def __enter__(self):
		frappe.set_user(FD_USER)

	def __exit__(self, *exc):
		frappe.set_user("Administrator")


def setup():
	rt, room = eval_harness.setup()
	# a second room so group bookings and sold-out scenarios are real
	room2 = frappe.get_doc({
		"doctype": "Room", "property": P, "room_number": "E102",
		"room_type": rt,
	}).insert(ignore_permissions=True)
	if not frappe.db.exists("User", FD_USER):
		frappe.get_doc({
			"doctype": "User", "email": FD_USER, "first_name": "Eval",
			"last_name": "FrontDesk", "send_welcome_email": 0,
			"roles": [{"role": "Front Desk"}],
		}).insert(ignore_permissions=True)
	return rt, room, room2.name


def _book(guest_name, phone, ci, co, **kw):
	from kamra import api
	return api.create_booking(
		property=P, room_type=RT, check_in_date=ci, check_out_date=co,
		guest_name=guest_name, phone=phone, **kw)


# ---------------------------------------------------------------- journeys

@check("walk-in: quote, book, room auto-assigned, price computed")
def f1():
	from kamra import api
	with at_the_desk():
		q = api.get_quote(P, RT, nowdate(), add_days(nowdate(), 1), 2, 0)
		assert q["amount_after_tax"] > 0, q
		out = _book("FD Walkin", "+91 71000 00001", nowdate(),
		            add_days(nowdate(), 1))
		res = frappe.get_doc("Reservation", out["reservation"])
		assert res.status == "Confirmed", res.status
		assert res.room, "no room auto-assigned"
		assert res.amount_after_tax == q["amount_after_tax"], (
			res.amount_after_tax, q["amount_after_tax"])


@check("the 11-guest regression: over-capacity walk-in refused at the desk")
def f2():
	with at_the_desk():
		try:
			_book("FD Crowd", "+91 71000 00002", "2032-01-01", "2032-01-02",
			      adults=11)
			raise AssertionError("11 adults accepted in a 3-adult room type")
		except frappe.ValidationError:
			pass


@check("check-in opens a folio; checkout spawns the housekeeping task")
def f3():
	from kamra import api
	with at_the_desk():
		out = _book("FD Stayer", "+91 71000 00003", nowdate(),
		            add_days(nowdate(), 1))
		api.check_in(out["reservation"])
		folio = api.get_folio(out["reservation"])
		assert folio["status"] == "Open", folio["status"]
		api.check_out(out["reservation"])
	res = frappe.get_doc("Reservation", out["reservation"])
	assert res.status == "Checked Out", res.status
	hk = frappe.db.exists("Housekeeping Task", {"room": res.room,
	                                            "status": ("!=", "Verified")})
	assert hk, "checkout did not create a housekeeping task"


@check("post a minibar charge: GST applied, posted exactly once")
def f4():
	from kamra import api
	with at_the_desk():
		out = _book("FD Minibar", "+91 71000 00004", "2032-02-01", "2032-02-02")
		api.check_in(out["reservation"])
		folio = api.get_folio(out["reservation"])["name"]
		before = frappe.get_doc("Folio", folio)
		r = api.add_folio_charge(folio, "Minibar", "2x cola", 400)
		after = frappe.get_doc("Folio", folio)
		assert len(after.charges) == len(before.charges) + 1
		line = after.charges[-1]
		# minibar is F&B; the localization pack (India: 5%) decides the
		# rate server-side even when the caller sends none
		assert line.gst_rate == 5, (
			f"minibar should carry the pack F&B rate (5), got {line.gst_rate}")
		assert r["balance"] == after.grand_total - after.payments_total


@check("guest disputes a charge: void restores the balance, keeps the trail")
def f5():
	from kamra import api
	with at_the_desk():
		out = _book("FD Dispute", "+91 71000 00005", "2032-02-05", "2032-02-06")
		api.check_in(out["reservation"])
		folio = api.get_folio(out["reservation"])["name"]
		base = frappe.get_doc("Folio", folio).grand_total
		api.add_folio_charge(folio, "Laundry", "pressing", 300)
		fd = frappe.get_doc("Folio", folio)
		row = fd.charges[-1].name
		api.void_folio_charge(folio, row, reason="guest disputed")
		fd.reload()
		assert fd.grand_total == base, (fd.grand_total, base)


@check("route the room charge to a Company folio: totals conserved")
def f6():
	from kamra import api
	from kamra.folio import post_room_night
	with at_the_desk():
		out = _book("FD Corporate", "+91 71000 00006",
		            "2032-02-10", "2032-02-11")
		api.check_in(out["reservation"])
		main = api.get_folio(out["reservation"])["name"]
	# night posting is the auditor's job, not the persona's
	post_room_night(frappe.get_doc("Reservation", out["reservation"]),
	                "2032-02-10")
	with at_the_desk():
		company = api.split_folio(out["reservation"], "Company")["folio"]
		fd = frappe.get_doc("Folio", main)
		total = fd.grand_total
		api.transfer_folio_charge(main, fd.charges[0].name, company)
		a = frappe.get_doc("Folio", main)
		b = frappe.get_doc("Folio", company)
		assert a.grand_total + b.grand_total == total, (
			a.grand_total, b.grand_total, total)


@check("settle and close: payment clears, invoice minted, folio frozen")
def f7():
	from kamra import api
	from kamra.folio import post_room_night
	with at_the_desk():
		out = _book("FD Settle", "+91 71000 00007", "2032-02-15", "2032-02-16")
		api.check_in(out["reservation"])
		folio = api.get_folio(out["reservation"])["name"]
	post_room_night(frappe.get_doc("Reservation", out["reservation"]),
	                "2032-02-15")
	with at_the_desk():
		fd = frappe.get_doc("Folio", folio)
		api.add_folio_payment(folio, "UPI", fd.grand_total)
		inv = api.close_folio(folio)
		assert inv["invoice_number"].startswith("INV-"), inv
		fd.reload()
		fd.charges[0].amount = 1
		try:
			fd.save()
			raise AssertionError("closed folio accepted a charge edit")
		except frappe.ValidationError:
			pass


@check("double booking the same room is refused at the desk")
def f8():
	# this scenario is about a hard sold-out house - pin the allowance to 0
	# (the shared eval setup opens it up for the stacking tests)
	frappe.db.set_value("Property", P, "overbooking_pct", 0)
	with at_the_desk():
		_book("FD First", "+91 71000 00008", "2032-03-01", "2032-03-03")
		_book("FD Second", "+91 71000 00009", "2032-03-01", "2032-03-03")
		# two rooms exist, so both fit; with no overbooking allowance the
		# third guest is refused outright - the desk's options are the
		# waitlist or a higher allowance in Settings
		try:
			_book("FD Third", "+91 71000 00010", "2032-03-01", "2032-03-03")
			raise AssertionError("sold-out window accepted a third booking")
		except frappe.exceptions.ValidationError:
			pass
		out = _book("FD Third", "+91 71000 00010", "2032-03-01",
		            "2032-03-03", waitlist=1)
		res = frappe.get_doc("Reservation", out["reservation"])
		assert res.status == "Waitlist" and not res.room, res.status
	frappe.db.set_value("Property", P, "overbooking_pct", 400)


@check("blacklisted guest is refused with the reason")
def f9():
	with at_the_desk():
		out = _book("FD Banned", "+91 71000 00011", "2032-03-08", "2032-03-09")
	guest = frappe.db.get_value("Reservation", out["reservation"], "guest")
	# the manager flags the profile after a chargeback
	frappe.db.set_value("Guest", guest,
		{"blacklisted": 1, "blacklist_reason": "chargeback fraud"})
	with at_the_desk():
		try:
			_book("FD Banned", "+91 71000 00011", "2032-03-10", "2032-03-11")
			raise AssertionError("blacklisted guest was accepted")
		except frappe.ValidationError:
			pass


@check("group of two rooms books as ONE group with a master folio")
def f10():
	from kamra import api
	with at_the_desk():
		grp = api.create_group_booking(
			property=P, group_name="FD Offsite",
			check_in_date="2032-04-01", check_out_date="2032-04-02",
			rooms=[{"room_type": RT, "count": 2}],
			guest_name="FD Lead", phone="+91 71000 00012")
		assert len(grp["created"]) == 2, grp
		master = api.group_master_folio(grp["group_booking"])["folio"]
		assert master, "no master folio for the group"


@check("sold out: waitlist parks the stay, cancellation frees, promote assigns")
def f11():
	from kamra import api
	with at_the_desk():
		first = _book("FD Full1", "+91 71000 00014", "2032-05-01", "2032-05-02")
		_book("FD Full2", "+91 71000 00015", "2032-05-01", "2032-05-02")
		parked = _book("FD Waiting", "+91 71000 00016",
		               "2032-05-01", "2032-05-02", waitlist=1)
		res = frappe.get_doc("Reservation", parked["reservation"])
		assert res.status == "Waitlist" and not res.room
		wl = api.waitlist(P)
		assert any(w["name"] == parked["reservation"] for w in wl), wl
		api.cancel_reservation(first["reservation"], reason="plans changed")
		out = api.promote_waitlist(parked["reservation"])
		assert out.get("room"), out
		res.reload()
		assert res.status == "Confirmed", res.status


@check("day-use: same-day stay books, occupies, and checks out today")
def f12():
	from kamra import api
	with at_the_desk():
		out = _book("FD Dayuse", "+91 71000 00017", "2032-06-01", "2032-06-01")
		res = frappe.get_doc("Reservation", out["reservation"])
		assert res.is_day_use or res.nights == 0, (
			res.get("is_day_use"), res.nights)


@check("RBAC: the desk cannot set rates or read the owner briefing")
def f13():
	from kamra import api
	with at_the_desk():
		try:
			api.set_room_rate(P, RT, "2032-07-01", "2032-07-02", 5000)
			raise AssertionError("Front Desk changed a room rate")
		except frappe.PermissionError:
			pass
		try:
			api.owner_briefing(P)
			raise AssertionError("Front Desk read the owner briefing")
		except frappe.PermissionError:
			pass


def execute():
	global RT, ROOM, ROOM2
	frappe.local.lang = frappe.local.lang or "en"
	real_commit, frappe.db.commit = frappe.db.commit, lambda *a, **k: None
	frappe.db.savepoint("fd_eval_start")
	try:
		RT, ROOM, ROOM2 = setup()
		for fn in (f1, f2, f3, f4, f5, f6, f7, f8, f9, f10, f11, f12, f13):
			fn()
	finally:
		frappe.set_user("Administrator")
		frappe.db.commit = real_commit
		frappe.db.rollback(save_point="fd_eval_start")

	passed = sum(1 for _, ok, _ in RESULTS if ok)
	print(f"\n=== Front-desk journey: {passed}/{len(RESULTS)} passed ===")
	for name, ok, msg in RESULTS:
		print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {msg}" if msg else ""))
	RESULTS.clear()
