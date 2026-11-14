# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import re

import frappe
from frappe.model.document import Document

# Arabic combining marks (fatha/damma/kasra/tanween/shadda/sukun…) that an
# Arabic keyboard leaves on a Latin code when the layout was still AR.
_AR_MARKS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
_CODE_OK = re.compile(r"[^A-Za-z0-9_-]")


def clean_room_type_code(code: str) -> str:
	"""Keep room type codes ASCII so Desk + Kamra agree on the ID."""
	code = _AR_MARKS.sub("", (code or "").strip())
	code = _CODE_OK.sub("", code)
	return code


class RoomType(Document):
	def validate(self):
		from kamra.booking_slugs import slugify, unique_listing_slug

		cleaned = clean_room_type_code(self.room_type_code)
		if not cleaned:
			frappe.throw(frappe._("Room type code must use Latin letters or digits (e.g. DLX, RWBT3)."))
		if cleaned != (self.room_type_code or ""):
			self.room_type_code = cleaned

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
		# Clash check by property+code, not by exists(new_name): MySQL
		# unicode collation can treat "prop-ٌRWBT3" as equal to "prop-RWBT3"
		# and falsely report the row as taken by itself.
		if self.room_type_code:
			clash = frappe.db.exists(
				"Room Type",
				{
					"property": self.property,
					"room_type_code": self.room_type_code,
					"name": ("!=", self.name),
				},
			)
			if clash:
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
