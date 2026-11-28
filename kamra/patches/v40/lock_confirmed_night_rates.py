"""Lock the nightly rates of every live booking that has none yet.

From this release a reservation carries the room rate confirmed for each
night (Reservation Night Rate) and the folio bills exactly that. Bookings
made before it were billed by re-pricing each night when it posted. This
patch freezes them so nothing they owe moves again:

- an auto-priced booking whose stored quote (quote_snapshot) still covers
  its current dates gets the nights of that quote - the rates the guest
  was actually given, demand premium included;
- any other live booking gets what the folio would bill for each night
  today (the pre-lock computation), so its billing is unchanged, only
  frozen.

Live = Confirmed, Checked In, Held or Pending Payment, departing today or
later. Amounts on the booking are not touched. Idempotent: a booking that
already has night rates is skipped.
"""

import json

import frappe
from frappe.utils import add_days, date_diff, getdate, nowdate


def execute():
	if not frappe.db.table_exists("Reservation Night Rate"):
		return
	if not frappe.db.has_column("Reservation", "rate_lock_key"):
		return
	names = frappe.db.sql(
		"""SELECT r.name FROM `tabReservation` r
		   WHERE r.status IN ('Confirmed', 'Checked In', 'Held', 'Pending Payment')
		     AND r.check_out_date >= %(today)s
		     AND NOT EXISTS (
		       SELECT 1 FROM `tabReservation Night Rate` n
		       WHERE n.parent = r.name AND n.parenttype = 'Reservation')""",
		{"today": nowdate()}, pluck=True)
	for name in names:
		try:
			lock(frappe.get_doc("Reservation", name))
		except Exception:
			frappe.log_error(title=f"Night-rate backfill failed: {name}")


def _stay_dates(doc) -> list[str]:
	nights = max(date_diff(doc.check_out_date, doc.check_in_date), 1)
	return [str(getdate(add_days(doc.check_in_date, i))) for i in range(nights)]


def _from_quote_snapshot(doc) -> dict | None:
	if not doc.get("auto_price") or not doc.get("quote_snapshot"):
		return None
	try:
		q = json.loads(doc.quote_snapshot)
	except Exception:
		return None
	nightly = q.get("nightly") or []
	if [str(n.get("date")) for n in nightly] != _stay_dates(doc):
		return None
	return q


def lock(doc) -> None:
	from kamra.folio import _nightly_gst, _nightly_room_rate

	if doc.get("night_rates"):
		return
	q = _from_quote_snapshot(doc)
	if q:
		doc.set_night_rates(q)
	else:
		meal = 0.0
		if doc.meal_plan:
			mp = frappe.db.get_value(
				"Meal Plan", doc.meal_plan,
				["price_per_adult", "price_per_child"], as_dict=True) or {}
			from kamra.pricing import meal_night_net
			meal = round(float(meal_night_net(
				doc.property, mp, doc.adults or 1, doc.children)), 6)
		for d in _stay_dates(doc):
			doc.append("night_rates", {
				"stay_date": d,
				"rate": round(_nightly_room_rate(doc, d), 2),
				"gst_rate": _nightly_gst(doc, d),
				"meal_amount": meal,
				"demand_premium_pct": 0,
			})
	for i, row in enumerate(doc.night_rates, start=1):
		row.parent, row.parenttype, row.parentfield = doc.name, "Reservation", "night_rates"
		row.idx = i
		row.db_insert()
	if doc.get("auto_price"):
		# a later save that does not change what was sold keeps these rates
		frappe.db.set_value(
			"Reservation", doc.name, "rate_lock_key",
			doc.rate_lock_key_for(doc.quote_inputs()), update_modified=False)
