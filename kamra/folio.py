"""Folio lifecycle: open at check-in, post nightly charges, settle, close.

All amounts flow from the deterministic pricing engine. GST is carried
per line so a folio can mix rates (room 5/18%, F&B 5%) and still produce
a correct multi-rate invoice — the PRD's FR-60.
"""

from decimal import Decimal

import frappe
from frappe.utils import add_days, getdate, now_datetime, nowdate

FNB_GST = 5.0  # F&B / meal-plan GST rate


def _recalculate(folio):
	charges = tax = Decimal(0)
	for c in folio.charges:
		amount = Decimal(str(c.amount or 0))
		rate = Decimal(str(c.gst_rate or 0))
		c.gst_amount = float(amount * rate / 100)
		c.total = float(amount + amount * rate / 100)
		charges += amount
		tax += amount * rate / 100
	paid = sum(Decimal(str(p.amount or 0)) for p in folio.payments)
	folio.charges_total = float(charges)
	folio.tax_total = float(tax)
	folio.grand_total = float(charges + tax)
	folio.payments_total = float(paid)
	folio.balance = float(charges + tax - paid)


def open_folio(reservation) -> str:
	"""Open (or return) the folio for a reservation. Called at check-in."""
	existing = frappe.db.get_value(
		"Folio", {"reservation": reservation.name, "folio_type": "Guest"}
	)
	if existing:
		return existing
	folio = frappe.get_doc({
		"doctype": "Folio",
		"property": reservation.property,
		"reservation": reservation.name,
		"guest": reservation.guest,
		"status": "Open",
		"opened_on": now_datetime(),
	})
	if reservation.discount_amount:
		folio.append("charges", {
			"posting_date": nowdate(),
			"charge_type": "Discount",
			"description": "Booking discount (voucher)",
			"qty": 1,
			"rate": -float(reservation.discount_amount),
			"amount": -float(reservation.discount_amount),
			"gst_rate": _room_gst(reservation),
			"auto_posted": 1,
		})
	_recalculate(folio)
	folio.insert(ignore_permissions=True)
	return folio.name


def _room_gst(reservation) -> float:
	"""Effective GST for this reservation's first night (used for the
	discount line). Slab-aware."""
	from kamra.pricing import room_gst_rate

	rt = frappe.get_doc("Room Type", reservation.room_type)
	rate = Decimal(str(_nightly_room_rate(reservation, reservation.check_in_date)))
	return float(room_gst_rate(reservation.property, rt, rate))


def _nightly_room_rate(reservation, date) -> float:
	"""Taxable nightly rate: seasons applied, tax backed out when the
	property configures tax-inclusive pricing."""
	from kamra.pricing import (occupancy_rate, rates_include_tax,
	                           room_gst_rate, season_adjust)

	rt = frappe.get_doc("Room Type", reservation.room_type)
	base = occupancy_rate(rt, reservation.adults, reservation.children)
	rate = season_adjust(reservation.property, date, base)
	if rates_include_tax(reservation.property):
		gst = room_gst_rate(reservation.property, rt, rate)
		rate = rate / (Decimal(1) + gst / Decimal(100))
	return float(rate)


def _nightly_gst(reservation, date) -> float:
	from kamra.pricing import (occupancy_rate, room_gst_rate, season_adjust)

	rt = frappe.get_doc("Room Type", reservation.room_type)
	base = occupancy_rate(rt, reservation.adults, reservation.children)
	gross = season_adjust(reservation.property, date, base)
	return float(room_gst_rate(reservation.property, rt, gross))


def post_room_night(folio_doc, reservation, date, save=True) -> bool:
	"""Post one night's room (and meal plan) charge. Skips if that date
	is already posted — safe to call from both audit and checkout."""
	date = str(date)
	already = any(
		c.charge_type == "Room" and str(c.posting_date) == date
		for c in folio_doc.charges
	)
	if already:
		return False

	room_no = (reservation.room or "").split("-")[-1]
	night_rate = _nightly_room_rate(reservation, date)
	folio_doc.append("charges", {
		"posting_date": date,
		"charge_type": "Room",
		"description": f"Room {room_no} · {reservation.room_type.split('-')[-1]}"
		               + (" · day use" if getattr(reservation, "is_day_use", 0) else ""),
		"qty": 1,
		"rate": night_rate,
		"amount": night_rate,
		"gst_rate": _nightly_gst(reservation, date),
		"auto_posted": 1,
	})

	if reservation.meal_plan:
		mp = frappe.get_doc("Meal Plan", reservation.meal_plan)
		meal_amount = (
			(reservation.adults or 1) * float(mp.price_per_adult or 0)
			+ (reservation.children or 0) * float(mp.price_per_child or 0)
		)
		if meal_amount:
			folio_doc.append("charges", {
				"posting_date": date,
				"charge_type": "Meal Plan",
				"description": f"{mp.label or mp.code} × {reservation.adults} adult(s)",
				"qty": 1,
				"rate": meal_amount,
				"amount": meal_amount,
				"gst_rate": FNB_GST,
				"auto_posted": 1,
			})

	_recalculate(folio_doc)
	if save:
		folio_doc.save(ignore_permissions=True)
	return True


def post_remaining_nights(reservation) -> int:
	"""At checkout: make sure every night of the stay is on the folio."""
	folio_name = open_folio(reservation)
	folio_doc = frappe.get_doc("Folio", folio_name)
	posted = 0
	date = getdate(reservation.check_in_date)
	end = getdate(reservation.check_out_date)
	if getattr(reservation, "is_day_use", 0) and end == date:
		end = getdate(add_days(date, 1))  # day-use bills its one date
	while date < end:
		if post_room_night(folio_doc, reservation, date, save=False):
			posted += 1
		date = getdate(add_days(date, 1))
	_recalculate(folio_doc)
	folio_doc.save(ignore_permissions=True)
	return posted


def split_folio(reservation: str, folio_type: str = "Extra") -> str:
	"""Open an additional folio for a stay (Extra or Company) so charges
	can be routed/split — e.g. 70/30 corporate vs personal."""
	res = frappe.get_doc("Reservation", reservation)
	folio = frappe.get_doc({
		"doctype": "Folio",
		"property": res.property,
		"reservation": res.name,
		"guest": res.guest,
		"folio_type": folio_type,
		"status": "Open",
		"opened_on": now_datetime(),
	})
	_recalculate(folio)
	folio.insert(ignore_permissions=True)
	return folio.name


def transfer_charge(from_folio: str, charge_row: str, to_folio: str):
	"""Move one charge line between two open folios of the same stay."""
	src = frappe.get_doc("Folio", from_folio)
	dst = frappe.get_doc("Folio", to_folio)
	if src.reservation != dst.reservation:
		frappe.throw("Folios belong to different reservations.")
	if "Closed" in (src.status, dst.status):
		frappe.throw("Both folios must be open to transfer charges.")
	row = next((c for c in src.charges if c.name == charge_row), None)
	if not row:
		frappe.throw(f"Charge {charge_row} not found on {from_folio}.")
	dst.append("charges", {
		"posting_date": row.posting_date,
		"charge_type": row.charge_type,
		"description": row.description,
		"qty": row.qty,
		"rate": row.rate,
		"amount": row.amount,
		"gst_rate": row.gst_rate,
		"auto_posted": row.auto_posted,
	})
	src.charges.remove(row)
	_recalculate(src)
	_recalculate(dst)
	src.save(ignore_permissions=True)
	dst.save(ignore_permissions=True)


def close_folio(folio_name: str) -> str:
	"""Close the folio and assign the GST invoice number."""
	folio = frappe.get_doc("Folio", folio_name)
	if folio.status == "Closed":
		return folio.invoice_number
	from frappe.model.naming import make_autoname

	folio.status = "Closed"
	folio.closed_on = now_datetime()
	folio.invoice_number = make_autoname("INV-.YYYY.-.#####")
	_recalculate(folio)
	folio.save(ignore_permissions=True)
	return folio.invoice_number


def run_night_audit(property: str, business_date: str | None = None) -> dict:
	"""Automated end-of-day: open missing folios, post the night's room
	charges for every in-house guest, flag no-shows. Idempotent per date."""
	business_date = business_date or nowdate()
	audit_name = f"AUDIT-{business_date}"
	if frappe.db.exists("Night Audit Run", audit_name):
		return {"already_ran": True, "audit": audit_name}

	log_lines = []
	folios_opened = charges_posted = no_shows = 0
	amount_posted = Decimal(0)

	in_house = frappe.get_all(
		"Reservation",
		filters={
			"property": property,
			"status": "Checked In",
			"check_in_date": ("<=", business_date),
			"check_out_date": (">", business_date),
		},
		fields=["name"],
	)
	for row in in_house:
		res = frappe.get_doc("Reservation", row.name)
		folio_name = frappe.db.get_value(
			"Folio", {"reservation": res.name, "folio_type": "Guest"}
		)
		if not folio_name:
			folio_name = open_folio(res)
			folios_opened += 1
			log_lines.append(f"opened folio {folio_name} for {res.name}")
		folio_doc = frappe.get_doc("Folio", folio_name)
		if post_room_night(folio_doc, res, business_date):
			charges_posted += 1
			amount_posted += Decimal(str(_nightly_room_rate(res, business_date)))
			log_lines.append(f"posted room night {business_date} → {folio_name}")

	# no-shows: confirmed arrivals whose date has passed
	stale = frappe.get_all(
		"Reservation",
		filters={
			"property": property,
			"status": "Confirmed",
			"check_in_date": ("<", business_date),
		},
		fields=["name"],
	)
	for row in stale:
		frappe.db.set_value("Reservation", row.name, "status", "No Show")
		no_shows += 1
		log_lines.append(f"flagged no-show: {row.name}")

	audit = frappe.get_doc({
		"doctype": "Night Audit Run",
		"property": property,
		"business_date": business_date,
		"status": "Completed",
		"room_charges_posted": charges_posted,
		"amount_posted": float(amount_posted),
		"no_shows_flagged": no_shows,
		"folios_opened": folios_opened,
		"log": "\n".join(log_lines) or "Nothing to do.",
	})
	audit.insert(ignore_permissions=True)

	from kamra.savings import log_action
	log_action(
		action_type="night_audit",
		reference_doctype="Night Audit Run",
		reference_name=audit.name,
		property=property,
		minutes_saved=90,
		rationale=f"Posted {charges_posted} room nights, flagged {no_shows} "
		          f"no-shows for {business_date}",
		agent_name="Night Audit",
		autonomy="Full",
		channel="API",
	)
	frappe.db.commit()
	return {
		"audit": audit.name,
		"room_charges_posted": charges_posted,
		"amount_posted": float(amount_posted),
		"no_shows_flagged": no_shows,
		"folios_opened": folios_opened,
	}


def nightly_audit_all_properties():
	"""Scheduler entry point — runs the audit for every active property."""
	for p in frappe.get_all("Property", filters={"disabled": 0}):
		try:
			run_night_audit(p.name)
		except Exception:
			frappe.log_error(title=f"Night audit failed: {p.name}")
