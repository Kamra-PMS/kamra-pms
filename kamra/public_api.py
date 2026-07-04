"""Guest-facing booking engine API — the only allow_guest surface.

Read: property showcase + live availability with real quotes.
Write: one endpoint, create a Website booking. Everything else stays
behind auth. Money still comes only from the pricing engine.
"""

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import date_diff


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
			"amenities": [a.strip() for a in (rt.amenities or "").split(",") if a.strip()],
			"media": [
				{"media_type": m.media_type, "url": m.url, "caption": m.caption}
				for m in (rt.get("media") or [])
			],
		})

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
			"star_category": prop.get("star_category"),
			"city": prop.city, "state": prop.state,
			"phone": prop.phone, "email": prop.email,
			"google_reviews_url": prop.get("google_reviews_url"),
			"tripadvisor_url": prop.get("tripadvisor_url"),
			"amenities": [a.strip() for a in (prop.get("property_amenities") or "").split(",") if a.strip()],
			"checkin_time": str(prop.checkin_time or ""),
			"checkout_time": str(prop.checkout_time or ""),
		},
		"room_types": room_types,
		"meal_plans": meal_plans,
	}


@frappe.whitelist(allow_guest=True)
def search_stay(property: str, check_in_date: str, check_out_date: str,
                adults: int = 2, children: int = 0):
	"""Availability + real quoted price per room type for the stay."""
	from kamra.api import available_rooms
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
		free = available_rooms(property, rt, check_in_date, check_out_date)
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


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=3600)
def book(property: str, room_type: str, check_in_date: str,
         check_out_date: str, guest_name: str, phone: str,
         email: str = "", adults: int = 2, children: int = 0,
         meal_plan: str = "", special_requests: str = ""):
	"""Create a Website booking (pay at hotel). Guest identity is the
	phone number; staff verify at check-in."""
	if not guest_name.strip() or not phone.strip():
		frappe.throw("Name and phone are required.")

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
			source="Website",
		)
		if email or special_requests:
			frappe.db.set_value("Reservation", result["reservation"], {
				"special_requests": special_requests or None,
			})
			if email:
				frappe.db.set_value("Guest", result["guest"], "email", email)
		frappe.db.commit()
	finally:
		frappe.set_user("Guest")

	return {
		"reservation": result["reservation"],
		"amount_after_tax": result["amount_after_tax"],
		"pay_at_hotel": True,
	}
