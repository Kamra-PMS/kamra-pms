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
		_post_addons(reservation, existing)
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
	_post_addons(reservation, folio.name)
	return folio.name


def _post_addons(reservation, folio_name: str):
	"""Post booking-time add-ons (experiences) that haven't hit the folio
	yet. Idempotent via the row's posted flag."""
	pending = [a for a in reservation.get("addons") or [] if not a.posted]
	if not pending:
		return
	doc = frappe.get_doc("Folio", folio_name)
	if doc.status == "Closed":
		return
	for a in pending:
		doc.append("charges", {
			"posting_date": nowdate(),
			"charge_type": "Misc",
			"reservation": reservation.name,
			"description": a.description or a.experience,
			"qty": a.qty or 1,
			"rate": a.rate,
			"amount": a.amount,
			"gst_rate": a.gst_rate,
			"auto_posted": 1,
		})
		frappe.db.set_value("Stay Addon", a.name, "posted", 1,
		                    update_modified=False)
		a.posted = 1
	_recalculate(doc)
	doc.save(ignore_permissions=True)


def open_group_folio(group_booking: str) -> str:
	"""Open (or return) the group's master folio — one consolidated bill
	for everything the company pays across all rooms of the group. It is
	anchored to the group's lead (first) reservation so invoicing and
	printing work unchanged."""
	existing = frappe.db.get_value(
		"Folio", {"group_booking": group_booking, "folio_type": "Group",
		          "status": "Open"})
	if existing:
		return existing
	lead = frappe.get_all(
		"Reservation",
		filters={"group_booking": group_booking,
		         "status": ("not in", ("Cancelled", "No Show"))},
		fields=["name", "property", "guest"],
		order_by="creation asc", limit=1)
	if not lead:
		frappe.throw(f"Group {group_booking} has no active reservations.")
	lead = lead[0]
	folio = frappe.get_doc({
		"doctype": "Folio",
		"property": lead.property,
		"reservation": lead.name,
		"guest": lead.guest,
		"folio_type": "Group",
		"group_booking": group_booking,
		"status": "Open",
		"opened_on": now_datetime(),
	})
	_recalculate(folio)
	folio.insert(ignore_permissions=True)
	return folio.name


def open_company_folio(reservation) -> str:
	"""Open (or return) the Company folio of a corporate stay."""
	existing = frappe.db.get_value(
		"Folio",
		{"reservation": reservation.name, "folio_type": "Company",
		 "status": "Open"},
	)
	if existing:
		return existing
	return split_folio(reservation.name, "Company")


def _company_pays(company: str, charge_type: str) -> bool:
	return frappe.db.get_value(
		"Company Billing Rule",
		{"parent": company, "charge_type": charge_type},
		"pay_by",
	) == "Company"


def target_folio(reservation, charge_type: str, is_alcohol: int = 0) -> str:
	"""Route a charge to the right folio of the stay.

	Group stays route company-payable charge types to the ONE group
	master folio (company pays the stay for every room, each guest pays
	their own extras). Individual corporate stays route to the stay's
	Company folio. Alcohol never bills to a company — Indian corporates
	won't settle it and most travel policies prohibit it.
	"""
	if not is_alcohol:
		group = reservation.get("group_booking")
		if group:
			company = frappe.db.get_value(
				"Group Booking", group, "company")
			if company and _company_pays(company, charge_type):
				return open_group_folio(group)
		if reservation.get("company") and _company_pays(
				reservation.company, charge_type):
			return open_company_folio(reservation)
	return open_folio(reservation)


def _charge_posted(reservation_name: str, charge_type: str, date: str) -> bool:
	"""Has this charge type already been posted for this date on ANY folio
	of the stay? Routing can land a member's room night on the GROUP
	master (anchored to the lead reservation), so we match on the line's
	own provenance first and fall back to the folio's reservation for
	lines predating the provenance field."""
	return bool(frappe.db.sql(
		"""
		SELECT 1 FROM `tabFolio Charge` fc
		JOIN `tabFolio` f ON fc.parent = f.name
		WHERE fc.charge_type = %(ct)s AND fc.posting_date = %(date)s
		  AND (fc.reservation = %(res)s
		       OR (IFNULL(fc.reservation, '') = '' AND f.reservation = %(res)s))
		LIMIT 1
		""",
		{"res": reservation_name, "ct": charge_type, "date": str(date)},
	))


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


def _append_charge(folios, reservation, charge_type, line, is_alcohol=0):
	"""Append a line to the routed folio, reusing loaded docs so a multi-
	night posting run saves each folio once."""
	name = target_folio(reservation, charge_type, is_alcohol)
	if name not in folios:
		folios[name] = frappe.get_doc("Folio", name)
	folios[name].append("charges", line)


def post_room_night(reservation, date, folios=None) -> bool:
	"""Post one night's room (and meal plan) charge, routed by the
	company's billing rules. Skips dates already posted — safe to call
	from both audit and checkout. Pass `folios` (a dict) to batch saves
	across nights; when omitted the touched folios save immediately."""
	date = str(date)
	own_batch = folios is None
	if own_batch:
		folios = {}
	posted = False

	if not _charge_posted(reservation.name, "Room", date):
		room_no = (reservation.room or "").split("-")[-1]
		night_rate = _nightly_room_rate(reservation, date)
		_append_charge(folios, reservation, "Room", {
			"posting_date": date,
			"charge_type": "Room",
			"reservation": reservation.name,
			"description": f"Room {room_no} · {reservation.room_type.split('-')[-1]}"
			               + (" · day use" if getattr(reservation, "is_day_use", 0) else ""),
			"qty": 1,
			"rate": night_rate,
			"amount": night_rate,
			"gst_rate": _nightly_gst(reservation, date),
			"auto_posted": 1,
		})
		posted = True

	if reservation.meal_plan and not _charge_posted(
			reservation.name, "Meal Plan", date):
		mp = frappe.get_doc("Meal Plan", reservation.meal_plan)
		meal_amount = (
			(reservation.adults or 1) * float(mp.price_per_adult or 0)
			+ (reservation.children or 0) * float(mp.price_per_child or 0)
		)
		if meal_amount:
			_append_charge(folios, reservation, "Meal Plan", {
				"posting_date": date,
				"charge_type": "Meal Plan",
				"reservation": reservation.name,
				"description": f"{mp.label or mp.code} × {reservation.adults} adult(s)",
				"qty": 1,
				"rate": meal_amount,
				"amount": meal_amount,
				"gst_rate": FNB_GST,
				"auto_posted": 1,
			})

	if own_batch:
		save_folios(folios)
	return posted


def save_folios(folios: dict):
	for doc in folios.values():
		_recalculate(doc)
		doc.save(ignore_permissions=True)


def post_remaining_nights(reservation) -> int:
	"""At checkout: make sure every night of the stay is on its folio(s)."""
	open_folio(reservation)  # guest folio always exists after checkout
	folios: dict = {}
	posted = 0
	date = getdate(reservation.check_in_date)
	end = getdate(reservation.check_out_date)
	if getattr(reservation, "is_day_use", 0) and end == date:
		end = getdate(add_days(date, 1))  # day-use bills its one date
	while date < end:
		if post_room_night(reservation, date, folios):
			posted += 1
		date = getdate(add_days(date, 1))
	save_folios(folios)
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
	transfer_charges(from_folio, [charge_row], to_folio)


def _folio_group(folio) -> str | None:
	return folio.get("group_booking") or frappe.db.get_value(
		"Reservation", folio.reservation, "group_booking")


def _assert_same_stay(src, dst):
	"""Charges may move within a stay, or within a group — company pays
	some rooms' charges on the master, guests settle the rest."""
	if src.reservation == dst.reservation:
		return
	sg, dg = _folio_group(src), _folio_group(dst)
	if sg and sg == dg:
		return
	frappe.throw("Folios belong to different stays.")


def transfer_charges(from_folio: str, charge_rows: list, to_folio: str):
	"""Move several charge lines at once — one save per folio, so a
	corporate re-bill of a whole stay is a single operation."""
	src = frappe.get_doc("Folio", from_folio)
	dst = frappe.get_doc("Folio", to_folio)
	_assert_same_stay(src, dst)
	if "Closed" in (src.status, dst.status):
		frappe.throw("Both folios must be open to transfer charges.")
	for charge_row in charge_rows:
		row = next((c for c in src.charges if c.name == charge_row), None)
		if not row:
			frappe.throw(f"Charge {charge_row} not found on {from_folio}.")
		if row.get("is_alcohol") and dst.folio_type in ("Company", "Group"):
			frappe.throw("Alcohol cannot be billed to a company folio.")
		dst.append("charges", {
			"posting_date": row.posting_date,
			"charge_type": row.charge_type,
			"reservation": row.get("reservation"),
			"description": row.description,
			"qty": row.qty,
			"rate": row.rate,
			"amount": row.amount,
			"gst_rate": row.gst_rate,
			"auto_posted": row.auto_posted,
			"is_alcohol": row.get("is_alcohol"),
		})
		src.charges.remove(row)
	_recalculate(src)
	_recalculate(dst)
	src.save(ignore_permissions=True)
	dst.save(ignore_permissions=True)


def split_charge(from_folio: str, charge_row: str, to_folio: str,
                 percent: float | None = None,
                 amount: float | None = None) -> dict:
	"""Split one charge line between two open folios of the same stay —
	the 70/30 corporate deal, the shared room, the disputed minibar.
	Give either a percent (of the line) or an absolute amount to move.
	Conservation is exact: source keeps base − part, target gets part."""
	src = frappe.get_doc("Folio", from_folio)
	dst = frappe.get_doc("Folio", to_folio)
	if from_folio == to_folio:
		frappe.throw("Pick a different folio to split into.")
	_assert_same_stay(src, dst)
	if "Closed" in (src.status, dst.status):
		frappe.throw("Both folios must be open to split charges.")
	row = next((c for c in src.charges if c.name == charge_row), None)
	if not row:
		frappe.throw(f"Charge {charge_row} not found on {from_folio}.")
	base = Decimal(str(row.amount or 0))
	if base <= 0:
		frappe.throw("Only positive charge lines can be split.")
	if percent:
		part = (base * Decimal(str(percent)) / 100).quantize(Decimal("0.01"))
	elif amount:
		part = Decimal(str(amount)).quantize(Decimal("0.01"))
	else:
		frappe.throw("Give a percent or an amount to split off.")
	if part <= 0 or part >= base:
		frappe.throw(f"Split must be between 0 and ₹{base} (exclusive).")
	if row.get("is_alcohol") and dst.folio_type in ("Company", "Group"):
		frappe.throw("Alcohol cannot be billed to a company folio.")

	remainder = base - part
	row.amount = float(remainder)
	row.rate = float(remainder)
	row.qty = 1
	dst.append("charges", {
		"posting_date": row.posting_date,
		"charge_type": row.charge_type,
		"reservation": row.get("reservation"),
		"description": f"{row.description} · split",
		"qty": 1,
		"rate": float(part),
		"amount": float(part),
		"gst_rate": row.gst_rate,
		"auto_posted": row.auto_posted,
		"is_alcohol": row.get("is_alcohol"),
	})
	_recalculate(src)
	_recalculate(dst)
	src.save(ignore_permissions=True)
	dst.save(ignore_permissions=True)
	return {"kept": float(remainder), "moved": float(part)}


def policy_fee(reservation, basis: str) -> float:
	"""₹ for a cancellation/no-show fee basis: 'First Night' or
	'Full Stay' (pre-tax; GST rides on the folio line)."""
	if basis == "First Night":
		return float(_nightly_room_rate(reservation,
		                                reservation.check_in_date))
	if basis == "Full Stay":
		return float(reservation.amount_before_tax or 0)
	return 0.0


def post_policy_fee(reservation, basis: str, label: str) -> float:
	"""Open the guest folio and post a policy fee (no-show / late
	cancellation). Returns the pre-tax amount posted."""
	amount = policy_fee(reservation, basis)
	if amount <= 0:
		return 0.0
	folio = frappe.get_doc("Folio", open_folio(reservation))
	if folio.status == "Closed":
		return 0.0
	already = any(c.description == label for c in folio.charges)
	if already:
		return 0.0
	folio.append("charges", {
		"posting_date": nowdate(),
		"charge_type": "Misc",
		"reservation": reservation.name,
		"description": label,
		"qty": 1,
		"rate": amount,
		"amount": amount,
		"gst_rate": _room_gst(reservation),
		"auto_posted": 1,
	})
	_recalculate(folio)
	folio.save(ignore_permissions=True)
	return amount


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
	# per property AND date — a global AUDIT-<date> name would make the
	# second property's audit silently no-op every night
	audit_name = f"AUDIT-{business_date}-{property}"
	if frappe.db.exists("Night Audit Run", audit_name) or \
			frappe.db.exists("Night Audit Run",
			                 {"property": property,
			                  "business_date": business_date}):
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
		if not frappe.db.get_value(
				"Folio", {"reservation": res.name, "folio_type": "Guest"}):
			folio_name = open_folio(res)
			folios_opened += 1
			log_lines.append(f"opened folio {folio_name} for {res.name}")
		if post_room_night(res, business_date):
			charges_posted += 1
			amount_posted += Decimal(str(_nightly_room_rate(res, business_date)))
			log_lines.append(f"posted room night {business_date} for {res.name}")

	# no-shows: confirmed arrivals whose date has passed — flagged AND
	# charged per the property's policy
	no_show_basis = frappe.db.get_value(
		"Property", property, "no_show_charge") or "None"
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
		if no_show_basis != "None":
			res = frappe.get_doc("Reservation", row.name)
			fee = post_policy_fee(res, no_show_basis,
			                      f"No-show charge ({no_show_basis})")
			if fee:
				amount_posted += Decimal(str(fee))
				log_lines.append(
					f"posted no-show charge ₹{fee:,.0f} for {row.name}")

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
