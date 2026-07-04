# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import date_diff, now_datetime


class Reservation(Document):
	def validate(self):
		self.validate_dates()
		self.nights = date_diff(self.check_out_date, self.check_in_date)
		self.validate_blacklist()
		self.validate_room_belongs_to_type()
		self.validate_no_overlap()
		self.apply_pricing()

	def validate_dates(self):
		diff = date_diff(self.check_out_date, self.check_in_date)
		if getattr(self, "is_day_use", 0):
			if diff != 0:
				frappe.throw(_("Day-use stays check out the same day."))
		elif diff < 1:
			frappe.throw(_("Check-out must be after check-in."))

	def validate_blacklist(self):
		if not self.guest or not self.is_new():
			return
		flagged, reason = frappe.db.get_value(
			"Guest", self.guest, ["blacklisted", "blacklist_reason"]
		) or (0, None)
		if flagged:
			frappe.throw(
				_("Guest {0} is blacklisted{1}. Remove the flag on the guest "
				  "profile to book.").format(
					self.guest_name or self.guest,
					f" — {reason}" if reason else "",
				),
				title=_("Blacklisted guest"),
			)

	def apply_pricing(self):
		"""Recompute money from the pricing engine while auto_price is on.
		Turn auto_price off to hold manually negotiated amounts."""
		if not getattr(self, "auto_price", 0) or not self.room_type:
			return
		from kamra.pricing import quote

		voucher_code = None
		if self.voucher:
			voucher_code = frappe.db.get_value(
				"Discount Voucher", self.voucher, "voucher_code"
			)
		q = quote(
			property=self.property,
			room_type=self.room_type,
			check_in_date=self.check_in_date,
			check_out_date=self.check_out_date,
			adults=self.adults,
			children=self.children,
			meal_plan=self.meal_plan,
			rate_plan=self.rate_plan,
			voucher_code=voucher_code,
		)
		self.amount_before_tax = q["amount_before_tax"]
		self.tax_amount = q["tax_amount"]
		self.amount_after_tax = q["amount_after_tax"]
		self.discount_amount = q["discount"]

	def after_insert(self):
		if self.voucher:
			frappe.db.sql(
				"""UPDATE `tabDiscount Voucher`
				   SET times_used = COALESCE(times_used, 0) + 1
				   WHERE name = %s""",
				self.voucher,
			)

	def validate_room_belongs_to_type(self):
		if not self.room:
			return
		room_type = frappe.db.get_value("Room", self.room, "room_type")
		if room_type != self.room_type:
			frappe.throw(
				_("Room {0} belongs to {1}, not {2}.").format(
					self.room, room_type, self.room_type
				)
			)

	def validate_no_overlap(self):
		"""A physical room can hold only one live reservation per night.

		This check is the seed of Kamra's no-overbooking guarantee: it runs
		on every insert/update, regardless of whether a human or an AI agent
		created the booking.
		"""
		if not self.room or self.status in ("Cancelled", "No Show", "Checked Out"):
			return
		# a day-use stay occupies [check_in, check_in + 1 day) — GREATEST
		# normalises both sides of the comparison
		conflict = frappe.db.sql(
			"""
			SELECT name FROM `tabReservation`
			WHERE room = %(room)s
			  AND name != %(name)s
			  AND status IN ('Confirmed', 'Checked In')
			  AND check_in_date < GREATEST(%(check_out)s,
			                               DATE_ADD(%(check_in)s, INTERVAL 1 DAY))
			  AND GREATEST(check_out_date,
			               DATE_ADD(check_in_date, INTERVAL 1 DAY)) > %(check_in)s
			LIMIT 1
			""",
			{
				"room": self.room,
				"name": self.name or "new",
				"check_in": self.check_in_date,
				"check_out": self.check_out_date,
			},
		)
		if conflict:
			frappe.throw(
				_("Room {0} is already booked ({1}) for these dates.").format(
					self.room, conflict[0][0]
				),
				title=_("Double booking blocked"),
			)

	def on_update(self):
		previous = self.get_doc_before_save()
		old_status = previous.status if previous else None
		if self.status == old_status:
			return
		if self.status == "Checked In":
			self.handle_check_in()
		elif self.status == "Checked Out":
			self.handle_check_out()

	def handle_check_in(self):
		if not self.room:
			frappe.throw(_("Assign a room before check-in."))
		self.db_set("actual_check_in", now_datetime(), update_modified=False)
		frappe.db.set_value("Room", self.room, "occupancy_status", "Occupied")
		from kamra.folio import open_folio

		open_folio(self)
		self.log_action("check_in", minutes_saved=10)

	def handle_check_out(self):
		self.db_set("actual_check_out", now_datetime(), update_modified=False)
		from kamra.folio import post_remaining_nights

		post_remaining_nights(self)
		if self.room:
			frappe.db.set_value(
				"Room",
				self.room,
				{"occupancy_status": "Vacant", "housekeeping_status": "Dirty"},
			)
			task = frappe.get_doc(
				{
					"doctype": "Housekeeping Task",
					"property": self.property,
					"room": self.room,
					"task_type": "Checkout Clean",
					"priority": "High",
					"status": "Pending",
					"reservation": self.name,
				}
			)
			task.insert(ignore_permissions=True)
		self.log_action("check_out", minutes_saved=12)

	def log_action(self, action_type, minutes_saved=0):
		from kamra.savings import log_action

		log_action(
			action_type=action_type,
			reference_doctype="Reservation",
			reference_name=self.name,
			property=self.property,
			minutes_saved=minutes_saved if self.source == "AI Agent" else 0,
			rationale=f"Reservation {self.name} moved to {self.status}",
		)
