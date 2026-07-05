"""One-off E2E verify for GM gap #32 (billing rules / occupants / ID
retention). Savepoint + rollback — leaves no data behind."""

import frappe
from frappe.utils import add_days, nowdate


def execute():
	frappe.db.savepoint("gm32")
	try:
		_run()
		print("ALL #32 CHECKS PASSED")
	finally:
		frappe.db.rollback(save_point="gm32")
		print("(rolled back)")


def _check(label, cond):
	print(("PASS  " if cond else "FAIL  ") + label)
	if not cond:
		raise AssertionError(label)


def _run():
	from kamra import api
	from kamra.folio import post_room_night

	prop = frappe.get_all("Property", filters={"disabled": 0},
	                      order_by="creation asc")[0].name
	rt = frappe.get_all("Room Type", filters={"property": prop},
	                    order_by="creation asc")[0].name
	mp = frappe.get_all("Meal Plan", filters={"property": prop}, limit=1)
	mp = mp[0].name if mp else None

	company = frappe.get_doc({
		"doctype": "Company", "company_name": "GM32 Test Corp",
		"gstin": "29AAACG0527D1Z8",
		"billing_rules": [
			{"charge_type": "Room", "pay_by": "Company"},
			{"charge_type": "Meal Plan", "pay_by": "Company"},
		],
	}).insert()

	booking = api.create_booking(
		property=prop, room_type=rt, check_in_date=nowdate(),
		check_out_date=add_days(nowdate(), 2), guest_name="GM32 Vikram",
		phone="+91-99000-32032", booking_type="Corporate",
		company=company.name, meal_plan=mp)
	res_name = booking["reservation"]
	api.check_in(res_name)
	res = frappe.get_doc("Reservation", res_name)

	# guest ID on file, to test scrubbing later
	frappe.db.set_value("Guest", res.guest, {
		"id_type": "Aadhaar", "id_number": "999988887777"})

	# 1. night posting routes room+meals to the Company folio
	_check("post_room_night returns True", post_room_night(res, nowdate()))
	rows = frappe.db.sql("""
		SELECT f.folio_type, fc.charge_type FROM `tabFolio Charge` fc
		JOIN `tabFolio` f ON fc.parent = f.name
		WHERE f.reservation = %s""", res_name, as_dict=True)
	_check("room night on Company folio",
	       any(r.folio_type == "Company" and r.charge_type == "Room"
	           for r in rows))
	if mp:
		_check("meal plan on Company folio",
		       any(r.folio_type == "Company" and r.charge_type == "Meal Plan"
		           for r in rows))
	_check("idempotent per date", not post_room_night(res, nowdate()))

	# 2. alcohol always routes to the guest folio
	out = api.post_stay_charge(res_name, "Food & Beverage",
	                           "Kingfisher 650ml", 450, 0, is_alcohol=1)
	_check("alcohol routed to Guest folio", out["folio_type"] == "Guest")

	# 3. unruled charge type routes to the guest folio
	out = api.post_stay_charge(res_name, "Laundry", "2 shirts", 200, 18)
	_check("unruled charge to Guest folio", out["folio_type"] == "Guest")

	# 4. occupants register + GRC
	api.update_occupants(res_name, [
		{"full_name": "Vikram Rao", "age": 41, "gender": "Male",
		 "id_type": "Aadhaar", "id_number": "999988887777"},
		{"full_name": "Meera Rao", "age": 38, "gender": "Female",
		 "id_type": "PAN", "id_number": "ABCPR1234F"},
	])
	grc = api.registration_card(res_name)
	_check("GRC lists 2 occupants", len(grc["occupants"]) == 2)

	# 5. Verify & Discard masks IDs at checkout
	frappe.db.set_value("Property", prop, "id_retention", "Verify & Discard")
	api.check_out(res_name)
	occ = frappe.get_doc("Reservation", res_name).occupants
	_check("occupant Aadhaar masked",
	       any(o.id_number == "••••••••7777" for o in occ))
	_check("occupant PAN masked",
	       any(o.id_number == "••••••234F" for o in occ))
	_check("guest ID masked",
	       frappe.db.get_value("Guest", res.guest, "id_number")
	       == "••••••••7777")

	# 6. checkout back-filled remaining nights, still routed to Company
	room_nights = frappe.db.sql("""
		SELECT COUNT(*) FROM `tabFolio Charge` fc
		JOIN `tabFolio` f ON fc.parent = f.name
		WHERE f.reservation = %s AND fc.charge_type = 'Room'
		  AND f.folio_type = 'Company'""", res_name)[0][0]
	_check("2 room nights on Company folio after checkout",
	       room_nights == 2)
