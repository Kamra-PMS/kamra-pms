# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, date_diff, formatdate, now_datetime, today


class InventoryRefused(frappe.ValidationError):
	"""No room left to sell: category sold out, room or villa already taken."""


# The SQL test for "a room type that is not a whole villa" (rt = Room Type).
# One definition shared by the villa <-> room lockout and the member-room
# fallback, so the two can never drift apart.
NON_VILLA_SQL = "(rt.room_category != 'Villa' OR rt.room_category IS NULL)"


def is_entire_place(room_type: str | None) -> bool:
	"""An entire-place (whole villa) stay: its room type is Villa-category,
	sold as one unit - the same test validate_villa_lockout uses."""
	return bool(room_type) and frappe.get_cached_value(
		"Room Type", room_type, "room_category") == "Villa"


def uses_member_rooms(property: str, room_type: str | None) -> bool:
	"""True when a whole-villa stay has no Room of its own to assign and
	instead takes the property's member rooms (the hybrid estate). A villa
	type with its own Room records checks in to one of them like any room."""
	return is_entire_place(room_type) and not frappe.db.exists(
		"Room", {"property": property, "room_type": room_type})


def entire_place_rooms(property: str, room_type: str,
                       include_out_of_order: bool = False) -> list[dict]:
	"""The member rooms (name, room_number) a whole-villa stay occupies when
	its villa type has no rooms of its own: every non-villa room on the
	property, mirroring the villa <-> room lockout. Out of Order rooms are
	left out - they are not sold and must not be touched (check-out asks
	for them only to free one that went out of order mid-stay).

	Only safe when this is the property's ONLY Villa type: with two villa
	listings there is no telling which rooms belong to which, so it refuses
	and asks for the rooms to be set up under the villa type."""
	other_villas = frappe.db.count("Room Type", {
		"property": property, "room_category": "Villa",
		"name": ("!=", room_type)})
	if other_villas:
		frappe.throw(
			_("{0} has no rooms of its own and the property has other villa "
			  "types, so Kamra can't tell which rooms it takes. Add Room "
			  "records under {0}, or assign a room before check-in.").format(
				room_type),
			title=_("Villa has no rooms"))
	ooo = "" if include_out_of_order else \
		"AND COALESCE(r.housekeeping_status, '') != 'Out of Order'"
	return frappe.db.sql(
		f"""
		SELECT r.name, r.room_number FROM `tabRoom` r
		LEFT JOIN `tabRoom Type` rt ON rt.name = r.room_type
		WHERE r.property = %s
		  AND {NON_VILLA_SQL}
		  {ooo}
		ORDER BY r.room_number
		""", property, as_dict=True)


# Statuses that hold a room (kamra.reservation_state.LIVE_STATUSES), as SQL.
_LIVE_SQL = "('Confirmed', 'Checked In', 'Held', 'Pending Payment')"


def villa_lockout_bookings(property: str, room_type: str | None, check_in,
                           check_out, exclude: str | None = None,
                           limit: int | None = None) -> list[dict]:
	"""Live reservations on the OTHER side of the villa <-> room lockout that
	overlap [check_in, check_out): for a whole-villa type, any booked
	non-villa (member) room; for any other type, a booked whole villa.

	The one query behind both the write-time guard (validate_villa_lockout)
	and every availability read (desk, booking engine, ARI push), so what
	Kamra refuses to book and what it offers for sale can never disagree.
	A property with no villa type never matches (the join finds nothing)."""
	if not room_type:
		return []
	side = NON_VILLA_SQL if is_entire_place(room_type) \
		else "rt.room_category = 'Villa'"
	return frappe.db.sql(
		f"""
		SELECT r.name, r.check_in_date, r.check_out_date FROM `tabReservation` r
		LEFT JOIN `tabRoom Type` rt ON r.room_type = rt.name
		WHERE r.property = %(property)s
		  AND r.name != %(name)s
		  AND r.status IN {_LIVE_SQL}
		  AND {side}
		  AND r.check_in_date < GREATEST(%(check_out)s, DATE_ADD(%(check_in)s, INTERVAL 1 DAY))
		  AND GREATEST(r.check_out_date, DATE_ADD(r.check_in_date, INTERVAL 1 DAY)) > %(check_in)s
		ORDER BY r.check_in_date
		{"LIMIT %d" % int(limit) if limit else ""}
		""",
		{
			"property": property,
			"name": exclude or "new",
			"check_in": check_in,
			"check_out": check_out,
		},
		as_dict=True,
	)


def villa_lockout_conflict(property: str, room_type: str | None, check_in,
                           check_out, exclude: str | None = None) -> str | None:
	"""The reservation that stops `room_type` selling for the stay under the
	villa <-> room lockout, or None when it is free to sell."""
	rows = villa_lockout_bookings(property, room_type, check_in, check_out,
	                              exclude=exclude, limit=1)
	return rows[0].name if rows else None


def villa_locked_nights(property: str, room_type: str | None, start,
                        end) -> set[str]:
	"""The nights in [start, end) on which `room_type` cannot sell because
	the other side of the villa <-> room lockout is booked."""
	from frappe.utils import add_days, getdate
	locked: set[str] = set()
	lo, hi = getdate(start), getdate(end)
	for b in villa_lockout_bookings(property, room_type, start, end):
		ci, co = getdate(b.check_in_date), getdate(b.check_out_date)
		co = max(co, getdate(add_days(ci, 1)))  # day-use holds its date
		d = max(ci, lo)
		while d < co and d < hi:
			locked.add(str(d))
			d = getdate(add_days(d, 1))
	return locked


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
		# ADR-009: open deposit liability when property policy requires one.
		try:
			from kamra.deposit import ensure_deposit_for_reservation
			ensure_deposit_for_reservation(self)
		except Exception:
			frappe.log_error(title="Security deposit ensure failed")

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
		# Serialize bookings of a category, even before a room is assigned.
		frappe.db.get_value("Room Type", self.room_type, "name", for_update=True)
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
		dates = [str(add_days(self.check_in_date, i))
		         for i in range(min(int(nights), 366))]
		# rooms a confirmed group block holds back (until its cutoff) are
		# not for general sale; a pickup books against its own block. Only
		# a stay taking NEW inventory is held to this - a block made after
		# a booking never stops that booking being edited.
		held = {}
		if self._takes_new_inventory():
			from kamra.group_blocks import block_hold_by_night
			held = block_hold_by_night(self.property, self.room_type, dates,
			                           for_group=self.group_booking)
		for d in dates:
			cnt = frappe.db.sql(
				"""SELECT COUNT(*) FROM `tabReservation`
				   WHERE room_type = %(rt)s AND name != %(name)s
				     AND status IN ('Confirmed', 'Checked In', 'Held', 'Pending Payment')
				     AND check_in_date <= %(d)s
				     AND GREATEST(check_out_date,
				                  DATE_ADD(check_in_date, INTERVAL 1 DAY)) > %(d)s""",
				{"rt": self.room_type, "name": self.name or "new", "d": d},
			)[0][0]
			hold = held.get(d, 0)
			if cnt + hold + 1 > limit:
				if hold:
					frappe.throw(
						_("{0} is sold out for {1}: {2} of {3} rooms sold and "
						  "{4} held for group blocks until their cutoff.").format(
							self.room_type, d, cnt, total, hold),
						title=_("Held for a group"), exc=InventoryRefused)
				frappe.throw(
					_("{0} is sold out for {1}: {2} of {3} rooms sold and "
					  "the overbooking allowance ({4}%) is used up.").format(
						self.room_type, d, cnt, total, pct),
					title=_("Overbooking limit"), exc=InventoryRefused)

	def _takes_new_inventory(self) -> bool:
		"""True when this save starts holding rooms it did not hold before:
		a new live booking, one entering a live status, or a change of
		dates / room type."""
		from kamra.reservation_state import holds_inventory
		if self.is_new():
			return True
		old = self.get_doc_before_save()
		if not old or not holds_inventory(old.status):
			return True
		return (str(old.check_in_date), str(old.check_out_date), old.room_type) \
			!= (str(self.check_in_date), str(self.check_out_date), self.room_type)

	def validate(self):
		self.validate_dates()
		self.validate_past_check_in()
		self.nights = date_diff(self.check_out_date, self.check_in_date)
		self.validate_minimum_nights()
		self.validate_status_transition()
		self.validate_blacklist()
		self.validate_occupancy()
		self.validate_room_belongs_to_type()
		self.validate_no_overlap()
		self.validate_room_vacant()
		self.validate_villa_lockout()
		self.validate_type_capacity()
		self.validate_cancellation_path()
		self.apply_negotiated_rate_plan()
		self.apply_pricing()

	def apply_negotiated_rate_plan(self):
		"""A new booking for a company with no rate plan of its own takes
		the plan the company negotiated. Stored on the booking, so the quote,
		the locked night rates and every folio night agree on it. Only new
		bookings: a confirmed stay is never re-priced by a contract change."""
		if not self.is_new() or self.rate_plan or not self.get("company"):
			return
		from kamra.pricing import negotiated_rate_plan
		plan = negotiated_rate_plan(self.property, self.company)
		if plan:
			self.rate_plan = plan

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

		# Peak dates can ask for longer than the property's own floor - a
		# two-night minimum over New Year, say - and the rule lives on the
		# Season that already prices those nights.
		from kamra.pricing import stay_season_rules

		rules = stay_season_rules(self.property, self.check_in_date,
		                          self.check_out_date, self.room_type)
		if rules["minimum_nights"] > nights:
			frappe.throw(
				_("{0} needs a stay of at least {1} nights.").format(
					rules["season"] or _("These dates"),
					rules["minimum_nights"]),
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
			["adults_capacity", "children_capacity", "room_type_name",
			 "max_extra_beds"],
			as_dict=True,
		) or frappe._dict()

		# A room can take a few more than it sleeps comfortably, by
		# arrangement - a family with one more child, a group happy to share.
		# That is a decision someone makes and signs their name to, so it
		# needs a reason and stops at the extra beds the room type allows.
		beds = cint(cap.max_extra_beds)
		stated = (self.get("over_capacity_reason") or "").strip()
		allowance = beds if stated else 0
		if beds and adults > cint(cap.adults_capacity) and not stated:
			frappe.throw(_(
				"{0} sleeps {1}. Up to {2} more can be booked by arrangement "
				"- give a reason on the booking to record who agreed it."
			).format(cap.room_type_name or self.room_type,
			         cint(cap.adults_capacity), beds),
				title=_("Over room capacity"))

		over = []
		if cint(cap.adults_capacity) and adults > cint(cap.adults_capacity) + allowance:
			over.append(_("{0} adults (max {1})").format(
				adults, cint(cap.adults_capacity) + allowance))
		if cint(cap.children_capacity) and children > cint(cap.children_capacity) + allowance:
			over.append(_("{0} children (max {1})").format(
				children, cint(cap.children_capacity) + allowance))
		if over:
			frappe.throw(_(
				"{0} can't sleep {1}. Reduce the party, pick a bigger room "
				"type, or book additional rooms — use a Group Booking for "
				"large parties."
			).format(cap.room_type_name or self.room_type, " {} ".format(_("and")).join(over)),
				title=_("Over room capacity"))

	def validate_dates(self):
		diff = date_diff(self.check_out_date, self.check_in_date)
		if getattr(self, "is_day_use", 0):
			if diff != 0:
				frappe.throw(_("Day-use stays check out the same day."))
		elif diff < 1:
			frappe.throw(_("Check-out must be after check-in."))

	def validate_past_check_in(self):
		"""Check-in cannot be before calendar today for sellable stays.

		- New bookings with a past check-in are rejected.
		- Edits that *change* check-in to a past date are rejected (so desk
		  cannot quietly backdate Confirmed / Held / Checked In stays).
		- Saving an in-house stay without changing dates stays allowed —
		  arrival already happened, the nights are historical.
		- Cancelled / No Show are exempt (not inventoriable).
		- Walk-in catch-up, seeding, and imports set flags.allow_past_check_in
		  (or ignore_validate on history import).
		"""
		if self.flags.get("allow_past_check_in"):
			return
		if self.status in ("Cancelled", "No Show"):
			return
		if date_diff(today(), self.check_in_date) <= 0:
			return
		if not self.is_new():
			old = self.get_doc_before_save()
			if old and date_diff(old.check_in_date, self.check_in_date) == 0:
				return
		frappe.throw(
			_("Check-in {0} has already passed. Pick today or a later date.")
			.format(formatdate(self.check_in_date)),
			title=_("Check-in date is in the past"),
		)

	def validate_blacklist(self):
		if not self.guest or not self.is_new():
			return
		# a Hotel Admin confirmed this one guest, with a reason (api._blacklist_gate)
		if frappe.flags.get("kamra_blacklist_override") == self.guest:
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

	def quote_inputs(self) -> dict:
		"""What the pricing engine needs to price this stay as it stands."""
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
		inputs = {
			"property": self.property,
			"room_type": self.room_type,
			"check_in_date": str(self.check_in_date),
			"check_out_date": str(self.check_out_date),
			"adults": int(self.adults or 0),
			"children": billable_children,
			"meal_plan": self.meal_plan or None,
			"rate_plan": self.rate_plan or None,
			"voucher_code": voucher_code,
			"over_capacity_charge": float(self.get("over_capacity_charge") or 0),
		}
		# only when there are pets, so the rate-lock key of every booking
		# made before pets existed stays the same and nothing re-prices
		if cint(self.get("pets")) > 0:
			inputs["pets"] = cint(self.get("pets"))
		return inputs

	@staticmethod
	def rate_lock_key_for(inputs: dict) -> str:
		import hashlib
		import json
		raw = json.dumps(inputs, sort_keys=True, default=str)
		return hashlib.sha1(raw.encode()).hexdigest()[:20]  # nosec B324 -- change detector, not security

	def requote(self, check_voucher_limits: bool = False) -> dict:
		"""Price the stay as it stands now, without counting this booking
		in the house's occupancy. Used by the save path and the amendment
		previews, so a preview and the save that follows agree."""
		from kamra.pricing import quote
		return quote(**self.quote_inputs(),
		             check_voucher_limits=check_voucher_limits,
		             exclude_reservation=None if self.is_new() else self.name)

	def apply_pricing(self):
		"""Price the booking from the engine while auto_price is on, and lock
		the confirmed nightly rates (`night_rates`).

		Once the stay has its rates, a save that does not change what is
		being sold (dates, room type, party, meal / rate plan, voucher)
		keeps them: later rate, season or demand changes never re-price a
		confirmed booking. Changing what is sold re-quotes and re-locks;
		the desk endpoints (amend_stay, move_reservation) show that price
		and ask for confirmation first. Turn auto_price off to hold manually
		negotiated amounts."""
		if not getattr(self, "auto_price", 0) or not self.room_type:
			return
		inputs = self.quote_inputs()
		key = self.rate_lock_key_for(inputs)
		if (not self.is_new() and self.get("night_rates")
				and self.get("rate_lock_key") == key
				and not self.has_value_changed("auto_price")):
			self._apply_commission()
			return

		q = self.requote(
			# the voucher's dates and use limit apply when it is first
			# attached; a saved booking keeps its discount on later edits
			check_voucher_limits=bool(
				self.is_new() or self.has_value_changed("voucher")),
		)
		self.amount_before_tax = q["amount_before_tax"]
		self.tax_amount = q["tax_amount"]
		self.amount_after_tax = q["amount_after_tax"]
		self.discount_amount = q["discount"]
		# Persist immutable quote snapshot (ADR-008).
		if hasattr(self, "quote_snapshot"):
			import json
			snap = dict(q)
			snap["idempotency_key"] = getattr(self, "idempotency_key", None)
			self.quote_snapshot = json.dumps(snap, default=str)
		self.set_night_rates(q)
		self.rate_lock_key = key
		self._apply_commission()

	def set_night_rates(self, q: dict):
		"""Lock the quote's nights on the booking - the rates the folio bills.

		A rate plan works on the stay total, so each night carries its share
		of the planned total (same spread as folio._rate_plan_factor), and
		the last night absorbs rounding so the nights add up to the quote's
		room total exactly."""
		nightly = q.get("nightly") or []
		plan_free = sum(float(n["rate"]) for n in nightly)
		room_total = float(q.get("room_total") or 0)
		factor = room_total / plan_free if plan_free else 1.0
		meal = 0.0
		if self.meal_plan:
			mp = frappe.db.get_value(
				"Meal Plan", self.meal_plan,
				["price_per_adult", "price_per_child"], as_dict=True) or {}
			meal = ((self.adults or 1) * float(mp.get("price_per_adult") or 0)
			        + (self.children or 0) * float(mp.get("price_per_child") or 0))
		rows, running = [], 0.0
		for i, n in enumerate(nightly):
			rate = round(float(n["rate"]) * factor, 2)
			if i == len(nightly) - 1 and plan_free:
				rate = round(room_total - running, 2)
			running += rate
			rows.append({
				"stay_date": n["date"],
				"rate": rate,
				"gst_rate": float(n.get("gst_rate") or 0),
				"meal_amount": meal,
				"demand_premium_pct": float(n.get("demand_premium_pct") or 0),
			})
		self.set("night_rates", rows)

	def _apply_commission(self):
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
			# help the user by naming the rooms they CAN move to: rooms of the
			# reservation's own type that are free for these dates
			from kamra.api import _available_rooms_raw
			free = [
				r.room_number for r in _available_rooms_raw(
					self.property, self.room_type,
					self.check_in_date, self.check_out_date)
				if r.name != self.room
			]
			if free:
				hint = " " + _("Free {0} rooms for these dates: {1}.").format(
					self.room_type, ", ".join(free))
			else:
				hint = " " + _("No {0} rooms are free for these dates.").format(
					self.room_type)
			frappe.throw(
				_("Room {0} belongs to {1}, not {2}.").format(
					self.room, room_type, self.room_type
				) + hint
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
				exc=InventoryRefused,
			)

	def validate_room_vacant(self):
		"""One guest in a room at a time. The night-based overlap guard lets a
		new stay start on another stay's departure date - right for bookings,
		since the departing guest will be gone by then - but a guest still
		Checked In has not gone. Checking in (or moving in-house) to a room
		whose occupant has not checked out yet is refused until they do."""
		if self.status != "Checked In" or not self.room:
			return
		before = self.get_doc_before_save()
		if before and before.status == "Checked In" and before.room == self.room:
			return  # already in this room; an unrelated edit
		# the occupant holds the room until they check out: their stay runs
		# to their departure date or, while they are still in, to tomorrow
		occupant = frappe.db.sql(
			"""
			SELECT name, guest_name FROM `tabReservation`
			WHERE room = %(room)s AND name != %(name)s
			  AND status = 'Checked In'
			  AND check_in_date < GREATEST(%(check_out)s,
			                               DATE_ADD(%(check_in)s, INTERVAL 1 DAY))
			  AND GREATEST(check_out_date,
			               DATE_ADD(check_in_date, INTERVAL 1 DAY),
			               DATE_ADD(%(today)s, INTERVAL 1 DAY)) > %(check_in)s
			LIMIT 1
			FOR UPDATE
			""",
			{"room": self.room, "name": self.name or "new",
			 "check_in": self.check_in_date, "check_out": self.check_out_date,
			 "today": today()},
			as_dict=True,
		)
		if occupant:
			room_no = frappe.db.get_value("Room", self.room, "room_number") \
				or self.room
			frappe.throw(
				_("Room {0} is still occupied by {1} ({2}). Check them out "
				  "first, or choose another room.").format(
					room_no, occupant[0].guest_name or occupant[0].name,
					occupant[0].name),
				title=_("Room still occupied"),
				exc=InventoryRefused,
			)

	def validate_villa_lockout(self):
		if self.status in (
			"Cancelled", "No Show", "Checked Out", "Waitlist",
			"Inquiry", "Quoted", "Requested",
		) or not self.room_type:
			return

		conflict = villa_lockout_conflict(
			self.property, self.room_type, self.check_in_date,
			self.check_out_date, exclude=self.name)
		if not conflict:
			return
		if is_entire_place(self.room_type):
			frappe.throw(
				_("This property cannot be booked as an Entire Villa for these dates because an individual room is already booked at {0} under Reservation {1}.").format(
					self.property, conflict
				),
				title=_("Double Booking Blocked"),
				exc=InventoryRefused,
			)
		frappe.throw(
			_("This room cannot be booked for these dates because the Entire Villa is already booked at {0} under Reservation {1}.").format(
				self.property, conflict
			),
			title=_("Double Booking Blocked"),
			exc=InventoryRefused,
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
	def _occupied_rooms(self, checking_in=True) -> list[str]:
		"""The rooms this stay holds: its assigned room, or for a whole-villa
		booking whose villa type has no rooms of its own, the member rooms
		(Out of Order ones excluded)."""
		if self.room:
			return [self.room]
		if uses_member_rooms(self.property, self.room_type):
			return [r.name for r in entire_place_rooms(
				self.property, self.room_type,
				include_out_of_order=not checking_in)]
		if checking_in:
			frappe.throw(_("Assign a room before check-in."))
		return []

	def handle_check_in(self):
		rooms = self._occupied_rooms()
		self.db_set("actual_check_in", now_datetime(), update_modified=False)
		for room in rooms:
			frappe.db.set_value("Room", room, "occupancy_status", "Occupied")
		from kamra.folio import open_folio

		open_folio(self)
		# the advance stops being a deposit the moment the guest is in house:
		# it pays the stay, so it moves to the Guest ledger
		from kamra.ledger import transfer_advances_to_guest
		transfer_advances_to_guest(self.name)
		self.log_action("check_in", minutes_saved=10)

	def handle_check_out(self):
		self.db_set("actual_check_out", now_datetime(), update_modified=False)
		from kamra.folio import post_remaining_nights
		from kamra.ledger import transfer_advances_to_guest

		post_remaining_nights(self)
		# a no-op unless an advance reached the stay some other way
		transfer_advances_to_guest(self.name)
		for room in self._occupied_rooms(checking_in=False):
			hk, occ = frappe.db.get_value(
				"Room", room, ["housekeeping_status", "occupancy_status"]) or (None, None)
			if hk == "Out of Order":
				# out of service: never flipped to Dirty, no checkout clean.
				# Only one that went out of order mid-stay is freed.
				if occ == "Occupied":
					frappe.db.set_value("Room", room, "occupancy_status", "Vacant")
				continue
			frappe.db.set_value(
				"Room",
				room,
				{"occupancy_status": "Vacant", "housekeeping_status": "Dirty"},
			)
			task = frappe.get_doc(
				{
					"doctype": "Housekeeping Task",
					"property": self.property,
					"room": room,
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
