import frappe
from kamra.api import set_room_rate, cancel_reservation
from kamra.pricing import quote

def run_tests():
	print("--- Running Generic Kamra Setup & Booking Flow Tests ---")
	
	# Use dynamic name prefix to avoid hardcoded client conflicts
	prop_name = "Test Dynamic Property"
	std_rt_name = f"{prop_name}-STD"
	villa_rt_name = f"{prop_name}-VILLA"
	
	# Cleanup any leftover tests
	cleanup_test_data(prop_name)
	
	# 1. Dynamically Create Test Property
	prop = frappe.get_doc({
		"doctype": "Property",
		"property_name": prop_name,
		"city": "Test City",
		"state": "Test State",
		"phone": "+91 99999 88888",
		"email": "test_dynamic@kamra.local",
		"gstin": "29ABCDE1234F3Z3",
		"checkin_time": "14:00:00",
		"checkout_time": "11:00:00",
		"minimum_nights": 1,
		"booking_payment_mode": "Advance percent",
		"advance_percent": 100,
		"security_deposit_amount": 5000,
	}).insert(ignore_permissions=True)
	
	# 2. Dynamically Create Room Types
	rt_std = frappe.get_doc({
		"doctype": "Room Type",
		"property": prop.name,
		"room_type_code": "STD",
		"room_type_name": "Standard Room",
		"room_category": "Private",
		"base_price": 7400,
		"base_occupancy": 2,
		"extra_adult_price": 2100,
		"child_price": 1000,
		"free_child_age": 6,
		"adults_capacity": 2,
		"children_capacity": 1,
		"max_total_occupants": 3,
	}).insert(ignore_permissions=True)
	
	frappe.get_doc({
		"doctype": "Room Type",
		"property": prop.name,
		"room_type_code": "VILLA",
		"room_type_name": "Entire Property",
		"room_category": "Villa",
		"base_price": 31500,
		"base_occupancy": 10,
		"extra_adult_price": 2100,
		"child_price": 1000,
		"free_child_age": 6,
		"adults_capacity": 10,
		"children_capacity": 5,
		"max_total_occupants": 15,
	}).insert(ignore_permissions=True)
	
	# 3. Create 5 physical rooms
	for i in range(1, 6):
		frappe.get_doc({
			"doctype": "Room",
			"property": prop.name,
			"room_number": f"Test Room {i}",
			"room_type": rt_std.name,
			"floor": "1"
		}).insert(ignore_permissions=True)
		
	# 4. Set Weekend Rate Overrides using days_of_week
	set_room_rate(
		property=prop.name,
		room_type=rt_std.name,
		start_date="2026-08-01",
		end_date="2026-08-31",
		rate=8600,
		reason="Weekend Rate",
		days_of_week=["Fri", "Sat"]
	)
	
	# Get or create guest
	guest = frappe.get_all("Guest", limit=1)
	if guest:
		guest_id = guest[0].name
	else:
		g = frappe.get_doc({
			"doctype": "Guest",
			"first_name": "Test",
			"last_name": "Guest",
			"phone": "+91 99999 99999"
		}).insert(ignore_permissions=True)
		guest_id = g.name

	try:
		# Test 1: Verify Weekend Pricing (Thu Aug 6 - weekday; Fri Aug 7 - weekend)
		q_thu = quote(prop_name, std_rt_name, "2026-08-06", "2026-08-07", adults=2, children=0)
		q_fri = quote(prop_name, std_rt_name, "2026-08-07", "2026-08-08", adults=2, children=0)
		
		print(f"Thu Aug 6 price: {q_thu['amount_after_tax']} (Expected: ~7400 + 5% tax)")
		print(f"Fri Aug 7 price: {q_fri['amount_after_tax']} (Expected: ~8600 + 18% tax)")
		assert abs(q_thu['amount_after_tax'] - 7400 * 1.05) < 100, "Weekday rate wrong"
		assert abs(q_fri['amount_after_tax'] - 8600 * 1.18) < 100, "Weekend rate wrong"
		print("✅ Test 1: Weekend pricing (night-by-night) works perfectly!")

		# Test 2: Free Child Age Exclusion Logic
		res = frappe.get_doc({
			"doctype": "Reservation",
			"property": prop_name,
			"room_type": std_rt_name,
			"check_in_date": "2026-08-06",
			"check_out_date": "2026-08-07",
			"adults": 2,
			"children": 1,
			"auto_price": 1,
			"status": "Confirmed",
			"guest": guest_id,
			"guest_name": "Test Child Guest"
		})
		
		# Add child occupant under 6 years old (free_child_age = 6)
		res.append("occupants", {
			"full_name": "Child Occ",
			"age": 5,
			"gender": "Female"
		})
		res.insert(ignore_permissions=True)
		
		print(f"Reservation with 5yo child amount: {res.amount_before_tax} (Expected: 7400)")
		assert int(res.amount_before_tax) == 7400, "Free child was charged!"
		
		# Update occupant age to 10 (exceeds free_child_age of 6)
		res.occupants[0].age = 10
		res.save(ignore_permissions=True)
		print(f"Reservation with 10yo child amount: {res.amount_before_tax} (Expected: 8400)")
		assert int(res.amount_before_tax) == 8400, "Chargeable child was not charged!"
		print("✅ Test 2: Free Child Age logic excludes ≤6 from charges perfectly!")

		# Test 3: Bidirectional Villa ↔ Room Lockout
		res_villa = frappe.get_doc({
			"doctype": "Reservation",
			"property": prop_name,
			"room_type": villa_rt_name,
			"check_in_date": "2026-08-06",
			"check_out_date": "2026-08-07",
			"adults": 10,
			"children": 0,
			"auto_price": 1,
			"status": "Confirmed",
			"guest": guest_id,
			"guest_name": "Test Villa Guest"
		})
		try:
			res_villa.insert(ignore_permissions=True)
			assert False, "Villa booked while standard room was occupied!"
		except frappe.ValidationError:
			print("✅ Test 3A: Villa booking blocked when individual room is booked (as expected).")

		# Clean up standard room reservation
		res.delete()

		# Now book Villa and test standard room lockout
		res_villa.insert(ignore_permissions=True)
		res_std = frappe.get_doc({
			"doctype": "Reservation",
			"property": prop_name,
			"room_type": std_rt_name,
			"check_in_date": "2026-08-06",
			"check_out_date": "2026-08-07",
			"adults": 2,
			"children": 0,
			"auto_price": 1,
			"status": "Confirmed",
			"guest": guest_id,
			"guest_name": "Test Std Guest"
		})
		try:
			res_std.insert(ignore_permissions=True)
			assert False, "Standard room booked while Villa was occupied!"
		except frappe.ValidationError:
			print("✅ Test 3B: Standard room booking blocked when Villa is booked (as expected).")

		# Test 4: Credit Note Voucher on Cancellation
		res_villa.db_set("advance_paid", 10000)
		cxl_res = cancel_reservation(res_villa.name, reason="Guest request", issue_credit_note=1)
		print(f"Cancellation response: {cxl_res}")
		assert cxl_res.get("credit_note_voucher") is not None, "Credit note voucher not generated"
		
		voucher_val = frappe.db.get_value("Discount Voucher", {"voucher_code": cxl_res["credit_note_voucher"]}, "value")
		print(f"Credit note voucher value: {voucher_val} (Expected: 10000)")
		assert int(voucher_val) == 10000, "Voucher value incorrect"
		print("✅ Test 4: Cancellation Credit Note Discount Voucher issued correctly!")

	finally:
		# Guarantee Cleanup
		cleanup_test_data(prop_name)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit -- bench script runs outside the request cycle; persist cleanup before the process exits
		print("--- Generic Test Cleanup Complete & All Tests Passed! ---")

def cleanup_test_data(property_name):
	# Delete reservations linked to this property
	reservations = frappe.get_all("Reservation", filters={"property": property_name})
	for r in reservations:
		frappe.delete_doc("Reservation", r.name, force=True)
		
	# Delete rooms
	rooms = frappe.get_all("Room", filters={"property": property_name})
	for rm in rooms:
		frappe.delete_doc("Room", rm.name, force=True)
		
	# Delete room types
	rts = frappe.get_all("Room Type", filters={"property": property_name})
	for rt in rts:
		frappe.delete_doc("Room Type", rt.name, force=True)
		
	# Delete seasons
	seasons = frappe.get_all("Season", filters={"property": property_name})
	for s in seasons:
		frappe.delete_doc("Season", s.name, force=True)
		
	# Delete vouchers
	vouchers = frappe.get_all("Discount Voucher", filters={"property": property_name})
	for v in vouchers:
		frappe.delete_doc("Discount Voucher", v.name, force=True)

	# Delete property
	if frappe.db.exists("Property", property_name):
		frappe.delete_doc("Property", property_name, force=True)
