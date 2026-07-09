"""Guest-facing booking engine API - the only allow_guest surface.

Read: property showcase + live availability with real quotes.
Write: one endpoint, create a Website booking. Everything else stays
behind auth. Money still comes only from the pricing engine.
"""

import re

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import date_diff


@frappe.whitelist(allow_guest=True)
def site_info():
	"""Public site metadata for the login/boot screen.

	demo_mode is true only on the seeded demo site (seed_demo sets the
	`kamra_demo_mode` default), so a real install never advertises the
	demo login accounts.
	"""
	return {"demo_mode": frappe.db.get_default("kamra_demo_mode") == "1"}


@frappe.whitelist(allow_guest=True)
def showcase(property: str):
	"""Everything the public booking page needs to render."""
	prop = frappe.get_doc("Property", property)
	if not prop.get("booking_engine_enabled"):
		frappe.throw("Online booking is not enabled for this property.")

	room_types = []
	for rt_name in frappe.get_all(
		"Room Type", filters={"property": property, "disabled": 0},
		pluck="name", order_by="base_price asc",
	):
		rt = frappe.get_doc("Room Type", rt_name)
		room_types.append({
			"name": rt.name,
			"room_type_name": rt.room_type_name,
			"description": rt.description,
			"base_price": float(rt.base_price),
			"base_occupancy": rt.base_occupancy,
			"adults_capacity": rt.adults_capacity,
			"children_capacity": rt.children_capacity,
			"bed_type": rt.bed_type,
			"room_view": rt.room_view,
			"amenities": [a.strip() for a in re.split(r"[,\n]", rt.amenities or "") if a.strip()],
			"media": [
				{"media_type": m.media_type, "url": m.url, "caption": m.caption}
				for m in (rt.get("media") or [])
			],
		})

	experiences = frappe.get_all(
		"Experience",
		filters={"property": property, "disabled": 0,
		         "show_on_booking_page": 1},
		fields=["name", "experience_name", "category", "price", "duration",
		        "description", "image_url", "gst_rate"],
		order_by="category asc",
	)

	meal_plans = frappe.get_all(
		"Meal Plan", filters={"property": property, "disabled": 0},
		fields=["name", "code", "label", "price_per_adult"],
		order_by="price_per_adult asc",
	)

	return {
		"property": {
			"name": prop.name,
			"property_name": prop.property_name,
			"description": prop.get("showcase_description"),
			"logo_url": prop.get("logo_url"),
			"hero_image": prop.get("hero_image"),
			"brand_accent": prop.get("brand_accent") or "Emerald",
			"star_category": prop.get("star_category"),
			"address_line": prop.address_line,
			"city": prop.city, "state": prop.state,
			"pincode": prop.pincode,
			"phone": prop.phone, "email": prop.email,
			"website": prop.website,
			"google_reviews_url": prop.get("google_reviews_url"),
			"tripadvisor_url": prop.get("tripadvisor_url"),
			"amenities": [a.strip() for a in re.split(r"[,\n]", prop.get("property_amenities") or "") if a.strip()],
			"checkin_time": str(prop.checkin_time or ""),
			"checkout_time": str(prop.checkout_time or ""),
			"driving_directions": prop.get("driving_directions"),
			"latitude": prop.get("latitude"),
			"longitude": prop.get("longitude"),
			"gallery": [
				{"url": m.url, "caption": m.caption}
				for m in (prop.get("gallery") or [])
			],
			"faqs": [
				{"question": f.question, "answer": f.answer}
				for f in (prop.get("faqs") or [])
			],
			"house_rules": prop.get("house_rules"),
			"pets_policy": prop.get("pets_policy"),
			"children_policy": prop.get("children_policy"),
			"extra_bed_policy": prop.get("extra_bed_policy"),
			"meta_title": prop.get("meta_title"),
			"meta_description": prop.get("meta_description"),
			"og_image": prop.get("og_image"),
			"page_slug": prop.get("page_slug"),
			"booking_engine_enabled": prop.get("booking_engine_enabled"),
			"payment_mode": prop.get("booking_payment_mode") or "Pay at hotel",
			"advance_percent": float(prop.get("advance_percent") or 0),
			"registration_fee": float(prop.get("registration_fee") or 0),
		},
		"room_types": room_types,
		"meal_plans": meal_plans,
		"experiences": experiences,
	}


@frappe.whitelist(allow_guest=True)
def search_stay(property: str, check_in_date: str, check_out_date: str,
                adults: int = 2, children: int = 0):
	"""Availability + real quoted price per room type for the stay."""
	# available_rooms is staff-only (@require_roles) since it's also an
	# MCP/copilot tool; guests need the same availability math without the
	# role gate, so this calls the same underlying helpers directly.
	from kamra.api import _available_rooms_raw, _block_hold
	from kamra.pricing import quote

	if date_diff(check_out_date, check_in_date) < 1:
		frappe.throw("Check-out must be after check-in.")
	if date_diff(check_out_date, check_in_date) > 30:
		frappe.throw("Stays longer than 30 nights: please contact the hotel.")

	results = []
	for rt in frappe.get_all(
		"Room Type", filters={"property": property, "disabled": 0},
		pluck="name", order_by="base_price asc",
	):
		free = _available_rooms_raw(property, rt, check_in_date, check_out_date)
		hold = _block_hold(property, rt, check_in_date, check_out_date)
		if hold:
			free = free[:max(0, len(free) - hold)]
		row = {"room_type": rt, "rooms_left": len(free), "quote": None}
		if free:
			try:
				row["quote"] = quote(
					property, rt, check_in_date, check_out_date,
					int(adults), int(children),
				)
			except Exception:
				pass
		results.append(row)
	return results


def _res_by_token(token: str):
	if not token or len(token) < 20:
		frappe.throw("Invalid link.")
	name = frappe.db.get_value("Reservation", {"precheckin_token": token})
	if not name:
		frappe.throw("This check-in link is not valid anymore.")
	return frappe.get_doc("Reservation", name)


@frappe.whitelist(allow_guest=True)
def precheckin_info(token: str):
	"""Stay summary for the pre-arrival check-in page."""
	res = _res_by_token(token)
	if res.status not in ("Confirmed", "Checked In"):
		frappe.throw("This booking is no longer active.")
	prop = frappe.get_doc("Property", res.property)
	guest = frappe.get_doc("Guest", res.guest)
	return {
		"property": {
			"property_name": prop.property_name,
			"logo_url": prop.get("logo_url"),
			"city": prop.city,
			"checkin_time": str(prop.checkin_time or ""),
			"phone": prop.phone,
			"house_rules": prop.get("house_rules"),
			"pets_policy": prop.get("pets_policy"),
			"children_policy": prop.get("children_policy"),
			"extra_bed_policy": prop.get("extra_bed_policy"),
		},
		"stay": {
			"reservation": res.name,
			"room_type": res.room_type.split("-")[-1],
			"check_in_date": str(res.check_in_date),
			"check_out_date": str(res.check_out_date),
			"nights": res.nights,
			"adults": res.adults,
			"children": res.children,
			"status": res.precheckin_status,
		},
		"guest": {
			"full_name": guest.full_name,
			"phone": guest.phone,
			"email": guest.email,
			"id_type": guest.id_type,
			"nationality": guest.nationality,
		},
	}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=20, seconds=3600)
def precheckin_submit(token: str, id_type: str, id_number: str,
                      email: str = "", nationality: str = "",
                      address_line: str = "", city: str = "",
                      eta: str = "", special_requests: str = "",
                      signature: str = "", consent: int = 0):
	"""Guest completes pre-arrival check-in and signs the registration card
	(PRD FR-20 - details + declaration + e-signature; the signed card becomes
	the paperless GRC the desk views at arrival). ID photo/KYC vendor
	integration comes later."""
	if not id_type or not id_number.strip():
		frappe.throw("ID type and number are required.")
	res = _res_by_token(token)
	if res.precheckin_status == "Verified":
		frappe.throw("Check-in details were already verified by the desk.")

	# a signed card requires the declaration to be accepted
	signed = bool(signature and str(signature).startswith("data:image"))
	if signed and not int(consent or 0):
		frappe.throw("Please accept the registration declaration to sign.")

	frappe.db.set_value("Guest", res.guest, {
		"id_type": id_type,
		"id_number": id_number.strip(),
		"email": email or None,
		"nationality": nationality or None,
		"address_line": address_line or None,
		"city": city or None,
	})
	frappe.db.set_value("Reservation", res.name, {
		"precheckin_status": "Submitted",
		"precheckin_on": frappe.utils.now_datetime(),
		"eta": eta or None,
		"special_requests": special_requests or res.special_requests,
		"precheckin_signature": signature if signed else None,
		"precheckin_consent": 1 if int(consent or 0) else 0,
	})

	from kamra.savings import log_action
	log_action(
		action_type="self_checkin",
		reference_doctype="Reservation",
		reference_name=res.name,
		property=res.property,
		minutes_saved=8,
		rationale="Guest completed pre-arrival check-in online",
		agent_name="Self Check-in",
		channel="API",
	)
	frappe.db.commit()
	return {"ok": True, "reservation": res.name}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=3600)
def _advance_terms(prop, total: float) -> tuple[float, str]:
	"""What the guest pays online now, and a human label - computed from the
	property's CURRENT booking-payment policy. Snapshotted onto the booking so
	a later policy change never re-bills an existing guest."""
	mode = prop.get("booking_payment_mode") or "Pay at hotel"
	total = float(total or 0)
	if mode == "Advance percent":
		pct = float(prop.get("advance_percent") or 0)
		due = round(total * pct / 100, 2)
		return due, f"{pct:g}% advance (₹{due:,.0f}) now, rest at the hotel"
	if mode == "Registration fee":
		due = min(float(prop.get("registration_fee") or 0), total)
		return due, f"₹{due:,.0f} registration fee now, rest at the hotel"
	if mode == "Full online":
		return total, "Full amount paid online"
	return 0.0, "Pay at the hotel"


def book(property: str, room_type: str, check_in_date: str,
         check_out_date: str, guest_name: str, phone: str,
         email: str = "", adults: int = 2, children: int = 0,
         meal_plan: str = "", special_requests: str = "", addons=None,
         voucher_code: str = ""):
	"""Create a Website booking. Guest identity is the phone number; staff
	verify at check-in. The advance owed is computed from the property's
	current payment policy and snapshotted onto the booking."""
	if not guest_name.strip() or not phone.strip():
		frappe.throw("Name and phone are required.")

	prop = frappe.get_cached_doc("Property", property)

	# a guest may only add experiences the hotel actually publishes for this
	# property - never a private, disabled or another property's experience,
	# and always at the hotel's own price (qty is all the guest controls)
	if isinstance(addons, str):
		addons = frappe.parse_json(addons)
	public_ids = set(frappe.get_all(
		"Experience",
		filters={"property": property, "disabled": 0, "show_on_booking_page": 1},
		pluck="name",
	))
	safe_addons = [
		{"experience": a["experience"], "qty": max(1, int(a.get("qty") or 1))}
		for a in (addons or [])
		if a.get("experience") in public_ids
	]

	from kamra.api import create_booking

	frappe.set_user("agent@kamra.local")  # governed writer for guest bookings
	try:
		result = create_booking(
			property=property,
			room_type=room_type,
			check_in_date=check_in_date,
			check_out_date=check_out_date,
			guest_name=guest_name,
			phone=phone,
			adults=int(adults),
			children=int(children),
			meal_plan=meal_plan or None,
			voucher_code=voucher_code or None,
			source="Website",
			addons=safe_addons or None,
		)
		# snapshot the advance owed from the policy in force RIGHT NOW, so a
		# later change to the property's payment config never re-bills this guest
		total = float(result["amount_after_tax"] or 0)
		advance_due, policy = _advance_terms(prop, total)
		updates = {
			"advance_due": advance_due,
			"payment_policy": policy,
			"is_pay_at_hotel": 1 if advance_due < total else 0,
		}
		if special_requests:
			updates["special_requests"] = special_requests
		frappe.db.set_value("Reservation", result["reservation"], updates)
		if email:
			frappe.db.set_value("Guest", result["guest"], "email", email)
		frappe.db.commit()
	finally:
		frappe.set_user("Guest")

	return {
		"reservation": result["reservation"],
		"amount_after_tax": result["amount_after_tax"],
		"advance_due": advance_due,
		"payment_policy": policy,
		"pay_at_hotel": advance_due <= 0,
	}


@frappe.whitelist(allow_guest=True)
def check_voucher(property: str, code: str, nights: int = 1):
	"""Live promo-code feedback on the booking page. Never throws - returns
	{ok, message, discount_type, value} so the guest sees a friendly note."""
	from kamra.pricing import validate_voucher
	code = (code or "").strip()
	if not code:
		return {"ok": False, "message": "Enter a code."}
	try:
		v = validate_voucher(property, code, int(nights or 1))
	except Exception as e:
		return {"ok": False, "message": str(e)}
	label = (f"{v.value:g}% off" if v.discount_type == "Percent"
	         else f"₹{v.value:,.0f} off")
	return {"ok": True, "message": f"'{v.voucher_code}' applied - {label}.",
	        "discount_type": v.discount_type, "value": float(v.value)}
