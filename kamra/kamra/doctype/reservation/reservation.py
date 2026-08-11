# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, date_diff, now_datetime


class Reservation(Document):
	def after_insert(self):
		# every booking gets a pre-arrival check-in link
		self.db_set(
			"precheckin_token", frappe.generate_hash(length=24),
			update_modified=False,
		)
		if self.voucher:
			frappe.db.sql(
				"""UPDATE `tabDiscount Voucher`
				   SET times_used = COALESCE(times_used, 0) + 1
				   WHERE name = %s""",
				self.voucher,
			)
		# WhatsApp booking confirmation - enqueued so a booking never
		# waits on Meta; skipped entirely unless the property connected
		# its own number (Channel Provider Connection, Meta Business)
		if self.status == "Confirmed":
			from kamra import whatsapp
			if whatsapp.has_connection(self.property):
				frappe.enqueue(
					"kamra.whatsapp.notify_booking_confirmed",
					reservation=self.name, queue="short",
					enqueue_after_commit=True)

	def validate_type_capacity(self):
		"""Room-type capacity with a controlled overbooking allowance.

		The room-level overlap guard below stops physical double-booking;
		this stops UNASSIGNED bookings quietly over-selling a category. The
		allowance (room type override, else property-wide, default 0%) is a
		revenue-management decision made in Settings - never implicit.
		"""
		# waitlisted / inquiry stays hold no inventory
		from kamra.reservation_state import holds_inventory
		if not holds_inventory(self.status):
			return
		# also skip classic non-inventory statuses not in LIVE
		if self.status in ("Cancelled", "No Show", "Checked Out", "Waitlist"):
			return
		total = frappe.db.count("Room", {"room_type": self.room_type})
		if not total:
			return  # setup-time bookings before rooms exist
		pct = float(frappe.db.get_value(
			"Room Type", self.room_type, "overbooking_pct") or 0)
		if not pct:
			# db read, not the document cache - enforcement must see the
			# committed value, not a stale cached doc
			pct = float(frappe.db.get_value(
				"Property", self.property, "overbooking_pct") or 0)
		limit = int(total * (1 + pct / 100))
		from frappe.utils import add_days, date_diff
		nights = max(1, date_diff(self.check_out_date, self.check_in_date))
		for i in range(min(int(nights), 366)):
			d = str(add_days(self.check_in_date, i))
			cnt = frappe.db.sql(
				"""SELECT COUNT(*) FROM `tabReservation`
				   WHERE room_type = %(rt)s AND name != %(name)s
				     AND status IN ('Confirmed', 'Checked In', 'Held', 'Pending Payment')
				     AND check_in_date <= %(d)s
				     AND GREATEST(check_out_date,
				                  DATE_ADD(check_in_date, INTERVAL 1 DAY)) > %(d)s""",
				{"rt": self.room_type, "name": self.name or "new", "d": d},
			)[0][0]
			if cnt + 1 > limit:
				frappe.throw(
					_("{0} is sold out for {1}: {2} of {3} rooms sold and "
					  "the overbooking allowance ({4}%) is used up.").format(
						self.room_type, d, cnt, total, pct),
					title=_("Overbooking limit"))

	def validate(self):
		self.validate_dates()
		self.nights = date_diff(self.check_out_date, self.check_in_date)
		self.validate_minimum_nights()
		self.validate_status_transition()
		self.validate_blacklist()
		self.validate_occupancy()
		self.validate_room_belongs_to_type()
		self.validate_no_overlap()
		self.validate_villa_lockout()
		self.validate_type_capacity()
		self.validate_cancellation_path()
		self.apply_pricing()

	def validate_minimum_nights(self):
		"""Property.minimum_nights is a hard floor for overnight stays."""
		if self.status in ("Cancelled", "No Show", "Checked Out", "Inquiry", "Quoted"):
			return
		# day-use is nights == 0; min nights applies to overnight only
		nights = date_diff(self.check_out_date, self.check_in_date)
		if nights <= 0:
			return
		min_n = cint(frappe.db.get_value(
			"Property", self.property, "minimum_nights") or 1)
		if min_n > 1 and nights < min_n:
			frappe.throw(
				_("This property requires a stay of at least {0} nights.").format(
					min_n),
				title=_("Minimum stay"),
			)

	def validate_status_transition(self):
		if self.is_new():
			return
		old = self.get_doc_before_save()
		if not old:
			return
		from kamra.reservation_state import assert_transition
		assert_transition(old.status, self.status)
	def validate_cancellation_path(self):
		"""Cancellations must go through cancel_reservation so the
		property's cancellation policy is applied (or knowingly waived) —
		flipping the status field would silently skip the fee."""
		if self.is_new() or frappe.flags.kamra_cancelling:
			return
		old = self.get_doc_before_save()
		if old and old.status != "Cancelled" and self.status == "Cancelled":
			frappe.throw(_(
				"Use the Cancel action (or the cancel_reservation API) so "
				"the cancellation policy is applied."))

	def validate_occupancy(self):
		"""A room only sleeps so many. Checked when the party or room type
		changes — legacy over-capacity stays can still check out."""
		if not self.room_type:
			return
		old = None if self.is_new() else self.get_doc_before_save()
		if old and (
			cint(old.adults), cint(old.children), old.room_type
		) == (cint(self.adults), cint(self.children), self.room_type):
			return
		adults, children = cint(self.adults), cint(self.children)
		if adults < 1:
			frappe.throw(_("A stay needs at least one adult."),
				title=_("Room capacity"))
		cap = frappe.db.get_value(
			"Room Type", self.room_type,
			["adults_capacity", "children_capacity", "room_type_name"],
			as_dict=True,
		) or frappe._dict()
		over = []
		if cint(cap.adults_capacity) and adults > cint(cap.adults_capacity):
			over.append(_("{0} adults (max {1})").format(
				adults, cint(cap.adults_capacity)))
		if cint(cap.children_capacity) and children > cint(cap.children_capacity):
			over.append(_("{0} children (max {1})").format(
				children, cint(cap.children_capacity)))
		if over:
			frappe.throw(_(
				"{0} can't sleep {1}. Reduce the party, pick a bigger room "
				"type, or book additional rooms — use a Group Booking for "
				"large parties."
			).format(cap.room_type_name or self.room_type, _(" and ").join(over)),
				title=_("Over room capacity"))

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
		# Deduct free children under free_child_age from billing
		free_children = 0
		free_child_age = frappe.db.get_value("Room Type", self.room_type, "free_child_age")
		if free_child_age is None:
			free_child_age = 6
		else:
			free_child_age = int(free_child_age)

		if getattr(self, "occupants", None):
			for occ in self.occupants:
				if occ.age and int(occ.age) <= free_child_age:
					free_children += 1
		if getattr(self, "infants", None):
			free_children = max(free_children, int(self.infants))

		billable_children = max(0, int(self.children or 0) - free_children)

		q = quote(
			property=self.property,
			room_type=self.room_type,
			check_in_date=self.check_in_date,
			check_out_date=self.check_out_date,
			adults=self.adults,
			children=billable_children,
			meal_plan=self.meal_plan,
			rate_plan=self.rate_plan,
			voucher_code=voucher_code,
		)
		self.amount_before_tax = q["amount_before_tax"]
		self.tax_amount = q["tax_amount"]
		self.amount_after_tax = q["amount_after_tax"]
		self.discount_amount = q["discount"]
		if getattr(self, "travel_agent", None):
			pct = frappe.db.get_value(
				"Travel Agent", self.travel_agent, "commission_pct") or 0
			self.commission_amount = float(self.amount_before_tax or 0) * float(pct) / 100
		else:
			self.commission_amount = 0

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
		if not self.room or self.status in (
			"Cancelled", "No Show", "Checked Out", "Waitlist",
			"Inquiry", "Quoted", "Requested",
		):
			return
		# serialize concurrent bookings for the same room: the row lock
		# makes the second transaction wait, and the locking read below
		# then sees the first one's committed reservation — check-then-
		# insert alone would let two simultaneous requests both pass
		frappe.db.get_value("Room", self.room, "name", for_update=True)
		# a day-use stay occupies [check_in, check_in + 1 day) — GREATEST
		# normalises both sides of the comparison
		conflict = frappe.db.sql(
			"""
			SELECT name FROM `tabReservation`
			WHERE room = %(room)s
			  AND name != %(name)s
			  AND status IN ('Confirmed', 'Checked In', 'Held', 'Pending Payment')
			  AND check_in_date < GREATEST(%(check_out)s,
			                               DATE_ADD(%(check_in)s, INTERVAL 1 DAY))
			  AND GREATEST(check_out_date,
			               DATE_ADD(check_in_date, INTERVAL 1 DAY)) > %(check_in)s
			LIMIT 1
			FOR UPDATE
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

	def validate_villa_lockout(self):
		if self.status in (
			"Cancelled", "No Show", "Checked Out", "Waitlist",
			"Inquiry", "Quoted", "Requested",
		) or not self.room_type:
			return
		
		# Get Room Category of the requested Room Type
		category = frappe.db.get_value("Room Type", self.room_type, "room_category")
		
		if category == "Villa":
			# A Villa is being booked. Check if ANY individual/shared room booking is confirmed/checked-in
			overlap = frappe.db.sql(
				"""
				SELECT r.name FROM `tabReservation` r
				LEFT JOIN `tabRoom Type` rt ON r.room_type = rt.name
				WHERE r.property = %(property)s
				  AND r.name != %(name)s
				  AND r.status IN ('Confirmed', 'Checked In', 'Held', 'Pending Payment')
				  AND (rt.room_category != 'Villa' OR rt.room_category IS NULL)
				  AND r.check_in_date < GREATEST(%(check_out)s, DATE_ADD(%(check_in)s, INTERVAL 1 DAY))
				  AND GREATEST(r.check_out_date, DATE_ADD(r.check_in_date, INTERVAL 1 DAY)) > %(check_in)s
				LIMIT 1
				""",
				{
					"property": self.property,
					"name": self.name or "new",
					"check_in": self.check_in_date,
					"check_out": self.check_out_date,
				}
			)
			if overlap:
				frappe.throw(
					_("This property cannot be booked as an Entire Villa for these dates because an individual room is already booked at {0} under Reservation {1}.").format(
						self.property, overlap[0][0]
					),
					title=_("Double Booking Blocked"),
				)
		else:
			# An individual room is being booked. Check if the Entire Property (Villa) is booked.
			overlap = frappe.db.sql(
				"""
				SELECT r.name FROM `tabReservation` r
				LEFT JOIN `tabRoom Type` rt ON r.room_type = rt.name
				WHERE r.property = %(property)s
				  AND r.name != %(name)s
				  AND r.status IN ('Confirmed', 'Checked In', 'Held', 'Pending Payment')
				  AND rt.room_category = 'Villa'
				  AND r.check_in_date < GREATEST(%(check_out)s, DATE_ADD(%(check_in)s, INTERVAL 1 DAY))
				  AND GREATEST(r.check_out_date, DATE_ADD(r.check_in_date, INTERVAL 1 DAY)) > %(check_in)s
				LIMIT 1
				""",
				{
					"property": self.property,
					"name": self.name or "new",
					"check_in": self.check_in_date,
					"check_out": self.check_out_date,
				}
			)
			if overlap:
				frappe.throw(
					_("This room cannot be booked for these dates because the Entire Villa is already booked at {0} under Reservation {1}.").format(
						self.property, overlap[0][0]
					),
					title=_("Double Booking Blocked"),
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
		elif self.status == "Confirmed" and old_status in (
			"Held", "Pending Payment", "Requested", "Waitlist",
		):
			self._notify_confirmed()

	def _notify_confirmed(self):
		from kamra import whatsapp
		if whatsapp.has_connection(self.property):
			frappe.enqueue(
				"kamra.whatsapp.notify_booking_confirmed",
				reservation=self.name, queue="short",
				enqueue_after_commit=True,
			)
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
