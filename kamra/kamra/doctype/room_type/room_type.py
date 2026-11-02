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
		if not self.is_new() and self._renamed_to():
			if frappe.db.exists("Room Type", self._renamed_to()):
				frappe.throw(frappe._("Room type code {0} is already used at this property.")
				             .format(self.room_type_code))

	def _renamed_to(self) -> str | None:
		"""The ID this room type should have now that its code changed, or None.
		The ID is {property}-{code} (autoname), set once at create time."""
		if not self.has_value_changed("room_type_code") or not self.room_type_code:
			return None
		want = f"{self.property}-{self.room_type_code}"
		return want if want != self.name else None

	def on_update(self):  # nosemgrep: frappe-modifying-but-not-comitting -- rename_doc writes the new name; self.name only follows it in memory
		# a changed code renames the ID too, so staff never have to; every
		# Link to the room type (rooms, stays, rates) follows the rename
		new_name = self._renamed_to()
		if new_name:
			frappe.rename_doc("Room Type", self.name, new_name, force=True,
			                  show_alert=False)
			self.name = new_name
		# Villa room types get a whole_property Sellable Unit (ADR-001).
		if self.room_category == "Villa":
			try:
				from kamra.siu.units import ensure_whole_property_siu
				ensure_whole_property_siu(self.name)
			except Exception:
				frappe.log_error(title="Sellable Unit sync on Room Type update")
