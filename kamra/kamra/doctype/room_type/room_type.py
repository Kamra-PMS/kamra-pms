# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class RoomType(Document):
	def validate(self):
		from kamra.booking_slugs import slugify, unique_listing_slug

		if not (self.listing_slug or "").strip():
			self.listing_slug = unique_listing_slug(
				self.property, self.room_type_name, exclude=self.name,
			)
		else:
			self.listing_slug = slugify(self.listing_slug)
		loc = (self.location_name or "").strip()
		if loc:
			if not (self.location_slug or "").strip():
				self.location_slug = slugify(loc)
			else:
				self.location_slug = slugify(self.location_slug)
		else:
			self.location_slug = None

	def on_update(self):
		# Villa room types get a whole_property Sellable Unit (ADR-001).
		if self.room_category == "Villa":
			try:
				from kamra.siu.units import ensure_whole_property_siu
				ensure_whole_property_siu(self.name)
			except Exception:
				frappe.log_error(title="Sellable Unit sync on Room Type update")
