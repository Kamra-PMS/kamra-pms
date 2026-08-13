import frappe


def execute():
	"""Default booking_mode=Instant and hold_minutes=120 on existing properties."""
	if frappe.db.has_column("Property", "booking_mode"):
		frappe.db.sql(
			"""
			UPDATE `tabProperty`
			SET booking_mode = 'Instant'
			WHERE IFNULL(booking_mode, '') = ''
			"""
		)
	if frappe.db.has_column("Property", "hold_minutes"):
		frappe.db.sql(
			"""
			UPDATE `tabProperty`
			SET hold_minutes = 120
			WHERE IFNULL(hold_minutes, 0) = 0
			"""
		)
	frappe.clear_cache(doctype="Property")
