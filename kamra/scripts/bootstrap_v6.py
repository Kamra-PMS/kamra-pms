"""Schema v6 — booking engine: room media, property showcase fields.

Run via bench console:
    from kamra.scripts.bootstrap_v6 import execute; execute()
"""

import frappe

from kamra.scripts.bootstrap_schema import f
from kamra.scripts.bootstrap_v2 import _dt
from kamra.scripts.bootstrap_v5 import add_fields


def execute():
	_dt("Room Type Media", [
		f("media_type", "Select", options="Image\nVideo", default="Image",
		  in_list_view=1),
		f("url", "Data", reqd=1, in_list_view=1,
		  description="Image URL or MP4/embed URL"),
		f("caption", "Data", in_list_view=1),
	], istable=1)

	add_fields("Room Type", [
		dict(fieldname="sb_media", fieldtype="Section Break",
		     label="Showcase Media", insert_after="image"),
		dict(fieldname="media", fieldtype="Table", options="Room Type Media",
		     label="Media Gallery", insert_after="sb_media"),
	])

	add_fields("Property", [
		dict(fieldname="sb_showcase", fieldtype="Section Break",
		     label="Booking Engine", insert_after="rates_include_tax"),
		dict(fieldname="booking_engine_enabled", fieldtype="Check",
		     label="Booking Engine Enabled", default="1",
		     insert_after="sb_showcase"),
		dict(fieldname="logo_url", fieldtype="Data", label="Logo URL",
		     insert_after="booking_engine_enabled",
		     description="Square logo shown on the booking page and invoices"),
		dict(fieldname="showcase_description", fieldtype="Small Text",
		     label="Description (public)", insert_after="logo_url"),
		dict(fieldname="hero_image", fieldtype="Data", label="Hero Image URL",
		     insert_after="showcase_description"),
		dict(fieldname="star_category", fieldtype="Select", label="Category",
		     options="\n1 Star\n2 Star\n3 Star\n4 Star\n5 Star\nBoutique\nHomestay",
		     insert_after="hero_image"),
		dict(fieldname="google_reviews_url", fieldtype="Data",
		     label="Google Reviews URL", insert_after="star_category"),
		dict(fieldname="tripadvisor_url", fieldtype="Data",
		     label="TripAdvisor URL", insert_after="google_reviews_url"),
		dict(fieldname="property_amenities", fieldtype="Small Text",
		     label="Property Amenities (public)",
		     insert_after="tripadvisor_url",
		     description="Comma-separated, e.g. Pool, Parking, Restaurant"),
	])

	frappe.db.commit()
	print("Kamra v6 schema (booking engine) ready.")
