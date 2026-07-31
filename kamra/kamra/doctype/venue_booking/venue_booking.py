# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""The banquet function sheet.

A Venue Booking is one function from first phone call to final bill:
enquiry -> tentative hold -> confirmed -> completed. Everything the
customer is buying lives in `items` - the hall itself, the menu packages,
the AV, the decor, the DJ, the accommodation - and each line says whether
it is chargeable or complimentary. Complimentary lines still print on the
event order and the pack list (someone has to carry the podium either
way); they just don't reach the quote.

Money is settled here, not by the caller: qty for per-pax lines follows
the guaranteed/actual pax rule, per-hour lines follow the function's own
hours, the negotiated discount is spread pro-rata so every line keeps its
own GST rate, and tax falls back to the rate for that kind of item rather
than whatever a caller happened to pass.
"""

from decimal import Decimal

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import (
	get_datetime,
	getdate,
	nowdate,
	time_diff_in_seconds,
)

# What a line is taxed at when nobody said. Food carries the F&B rate from
# the property's localization pack; everything else is a service.
_FNB_TYPES = ("Menu", "Food & Beverage")
_SERVICE_GST = 18.0

BLOCKING_STATUSES = ("Confirmed",)

# A hall is sold by the session, not by the stopwatch - "Saturday evening"
# is the unit a customer asks for and a banquet office answers in. These
# are the default clock hours behind each name; a function that genuinely
# runs to its own timetable picks Custom Hours and states them.
SESSION_HOURS = {
	"Morning": ("07:00:00", "12:00:00"),
	"Afternoon": ("12:00:00", "17:00:00"),
	"Evening": ("18:00:00", "23:59:00"),
	"Full Day": ("07:00:00", "23:59:00"),
}
SESSIONS = (*SESSION_HOURS, "Custom Hours")

# service charge rides the food and the people serving it, not the hall
# rental or the hired LED wall
SERVICE_CHARGE_TYPES = ("Menu", "Food & Beverage", "Alcohol", "Staffing")

# What counts as food when we ask whether the input credit is claimable.
_FOOD_TYPES = ("Menu", "Food & Beverage")


class VenueBooking(Document):
	# ── the numbers everything else reads ────────────────────────────────

	@property
	def billable_pax(self) -> int:
		"""What the menus bill on. The guarantee is the floor: if more
		people actually turned up, they're billed too."""
		guaranteed = int(self.pax_guaranteed or 0)
		actual = int(self.pax_actual or 0)
		if actual:
			return max(actual, guaranteed)
		return guaranteed or int(self.attendees or 0)

	# ── lifecycle ────────────────────────────────────────────────────────

	def validate(self):
		self._defaults()
		self._session()
		self._hours()
		self._price_lines()
		self._totals()
		self._cost_and_margin()
		self._payment_terms()
		self._guards()

	def _session(self):
		"""Pick the clock up from the session unless the function states its
		own hours - so "Saturday evening" is enough to book, and the diary
		still knows when the doors open."""
		if not self.session:
			self.session = "Custom Hours" if self.start_time else "Evening"
		hours = SESSION_HOURS.get(self.session)
		if hours and self.session != "Custom Hours":
			self.start_time, self.end_time = hours
		elif self.session == "Custom Hours" and not (self.start_time and self.end_time):
			frappe.throw(_("Custom Hours needs a start and an end time - or "
			              "pick a session."))

	def _defaults(self):
		if not self.enquiry_date:
			self.enquiry_date = nowdate()
		if not self.status:
			self.status = "Enquiry"
		if self.end_date and getdate(self.end_date) < getdate(self.event_date):
			frappe.throw(_("The function can't end before it starts."))
		if not self.pax_guaranteed and self.status in ("Confirmed", "Completed"):
			# confirming without a guarantee: the expected count becomes it
			self.pax_guaranteed = int(self.attendees or 0)

	def _hours(self):
		"""What a per-hour hall charge bills on. Spans midnight correctly -
		a 20:00-01:00 reception is five hours, not minus nineteen."""
		if not (self.start_time and self.end_time):
			self.billable_hours = 0
			return
		start = get_datetime(f"{self.event_date} {self.start_time}")
		end_day = self.end_date or self.event_date
		end = get_datetime(f"{end_day} {self.end_time}")
		hours = time_diff_in_seconds(end, start) / 3600
		if hours <= 0:
			hours += 24  # ran past midnight on the same calendar date
		self.billable_hours = round(hours, 2)

	# ── pricing ──────────────────────────────────────────────────────────

	def _default_gst(self, row) -> float:
		"""The rate a line actually carries, decided here rather than by
		whoever posted it - the same discipline folio charges follow."""
		if row.tax_exempt:
			return 0.0
		if row.gst_rate:
			return float(row.gst_rate)
		if row.banquet_menu:
			rate = frappe.db.get_value("Banquet Menu", row.banquet_menu, "gst_rate")
			if rate:
				return float(rate)
		if row.service_item:
			rate = frappe.db.get_value(
				"Banquet Service Item", row.service_item, "gst_rate")
			if rate:
				return float(rate)
		if row.item_type in _FNB_TYPES and not row.is_alcohol:
			from kamra.folio import _fnb_gst
			return float(_fnb_gst(self.property))
		return _SERVICE_GST

	def _price_lines(self):
		"""Fill in what the line is actually worth. Quantities that follow
		the function (pax, hours) are filled from the function so a menu
		can't quietly bill 1 plate for a 300-person wedding.

		Once the night is counted, `actual_qty` is what bills: the quote
		said 300 plates, 318 people ate. Until then the quoted quantity
		stands."""
		for row in self.items:
			if row.uom == "Pax" and not row.qty:
				row.qty = self.billable_pax
			elif row.uom == "Hour" and not row.qty:
				row.qty = self.billable_hours
			elif not row.qty:
				row.qty = 1
			if row.banquet_menu and row.uom == "Pax":
				min_pax = frappe.db.get_value(
					"Banquet Menu", row.banquet_menu, "min_pax")
				if min_pax and row.qty < int(min_pax):
					# the package's floor: a 50-plate minimum bills 50
					row.qty = int(min_pax)
			row.gst_rate = self._default_gst(row)
			billed = Decimal(str(row.actual_qty or row.qty or 0))
			gross = billed * Decimal(str(row.rate or 0))
			# a complimentary line is worth nothing on the bill, but we keep
			# the rate so the event order can show what was given away
			row.amount = float(gross) if row.chargeable else 0.0
			# the buy side rides the same quantity - a plate we served is a
			# plate we cooked, whether or not the customer was charged
			cost = billed * Decimal(str(row.cost_rate or 0))
			row.cost_amount = float(cost)
			row.input_tax = float(cost * self._input_gst(row) / 100)

	def _input_gst(self, row) -> Decimal:
		"""The tax the hotel PAID on this line's cost. Food is bought at the
		food rate, hired kit and sub-contractors at the services rate."""
		if row.service_item:
			rate = frappe.db.get_value(
				"Banquet Service Item", row.service_item, "cost_gst_rate")
			if rate is not None:
				return Decimal(str(rate))
		if row.item_type in _FOOD_TYPES:
			from kamra.folio import _fnb_gst
			return Decimal(str(_fnb_gst(self.property)))
		return Decimal(str(_SERVICE_GST))

	def _cost_and_margin(self):
		"""What the function costs the hotel, and what's left.

		The input credit is the part people get wrong. A supply billed at
		the 5% food rate is the composition-style scheme: the customer pays
		less tax and the hotel claims NOTHING back on what it bought. Bill
		the same food as part of an 18% banquet supply and the credit is
		claimable. So eligibility is read off the output rate, not assumed -
		and the margin uses net cost only when the credit is real."""
		food = sum((Decimal(str(r.cost_amount or 0)) for r in self.items
		            if r.item_type in _FOOD_TYPES), Decimal(0))
		total = sum((Decimal(str(r.cost_amount or 0)) for r in self.items),
		            Decimal(0))
		input_tax = sum((Decimal(str(r.input_tax or 0)) for r in self.items),
		                Decimal(0))

		food_out_rates = [float(r.gst_rate or 0) for r in self.items
		                  if r.chargeable and r.item_type in _FOOD_TYPES]
		# no food on the quote yet: judge on whatever else is being sold
		if not food_out_rates:
			food_out_rates = [float(r.gst_rate or 0) for r in self.items
			                  if r.chargeable]
		eligible = bool(food_out_rates) and min(food_out_rates) >= 12

		self.food_cost = float(food)
		self.service_cost = float(total - food)
		self.total_cost = float(total)
		self.input_tax_credit = float(input_tax)
		self.itc_eligible = 1 if eligible else 0
		self.net_cost = float(total - (input_tax if eligible else Decimal(0)))
		revenue = Decimal(str(self.taxable_amount or 0))
		self.gross_margin = float(revenue - Decimal(str(self.net_cost)))
		self.margin_percent = float(
			round(Decimal(str(self.gross_margin)) / revenue * 100, 2)
		) if revenue else 0.0

	def _totals(self):
		chargeable = [r for r in self.items if r.chargeable]
		subtotal = sum((Decimal(str(r.amount or 0)) for r in chargeable),
		               Decimal(0))
		discount = Decimal(str(self.discount_amount or 0))
		if discount < 0:
			frappe.throw(_("A discount can't be negative."))
		if discount > subtotal:
			frappe.throw(
				_("The discount ({0}) is more than the quote itself ({1}).")
				.format(frappe.format_value(float(discount), "Currency"),
				        frappe.format_value(float(subtotal), "Currency")))
		# spread the negotiated reduction across the lines so a mixed-rate
		# quote (food at 5%, AV at 18%) still taxes each line correctly
		factor = ((subtotal - discount) / subtotal) if subtotal else Decimal(1)

		tax = Decimal(0)
		for row in self.items:
			if not row.chargeable:
				row.net_amount = row.gst_amount = row.total = 0.0
				continue
			net = Decimal(str(row.amount or 0)) * factor
			gst = net * Decimal(str(row.gst_rate or 0)) / 100
			row.net_amount = float(net)
			row.gst_amount = float(gst)
			row.total = float(net + gst)
			tax += gst

		# service charge: a percentage of the food and the people who serve
		# it, added before tax and taxed itself - the way a banquet bill
		# states it. Never on the hall rental or the hired equipment.
		service = Decimal(0)
		pct = Decimal(str(self.service_charge_percent or 0))
		if pct:
			base = sum((Decimal(str(r.amount or 0)) * factor
			            for r in chargeable
			            if r.item_type in SERVICE_CHARGE_TYPES), Decimal(0))
			service = (base * pct / 100).quantize(Decimal("0.01"))
			# it carries the rate of what it's charged on (F&B, not 18%)
			rates = {float(r.gst_rate or 0) for r in chargeable
			         if r.item_type in SERVICE_CHARGE_TYPES}
			service_gst = Decimal(str(max(rates))) if rates else Decimal(0)
			tax += service * service_gst / 100
		self.service_charge = float(service)

		self.subtotal = float(subtotal)
		self.taxable_amount = float(subtotal - discount + service)
		self.tax_amount = float(tax)
		self.grand_total = float(subtotal - discount + service + tax)
		self.non_chargeable_value = float(sum(
			(Decimal(str(r.qty or 0)) * Decimal(str(r.rate or 0))
			 for r in self.items if not r.chargeable), Decimal(0)))
		# the diary, the group screens and the MCP tools read quoted_amount
		self.quoted_amount = self.grand_total

		rental = next((r for r in self.items if r.item_type == "Venue Rental"),
		              None)
		self.venue_rental_list = float(rental.list_rate or 0) if rental else 0.0
		self.venue_rental = float(rental.rate or 0) if rental else 0.0

		# Money received splits two ways and must not be added up as one.
		# An advance pays the bill down; a security deposit is the hotel
		# holding the customer's money against damage - counting it as
		# payment would make a fully-unpaid function look part-settled.
		if self.receipts:
			paid = sum(
				(Decimal(str(r.amount or 0)) * (
					Decimal(-1) if r.kind == "Refund" else Decimal(1))
				 for r in self.receipts if r.kind != "Security Deposit"),
				Decimal(0))
			self.advance_received = float(paid)
			# what's still the customer's: taken in, less what went back,
			# less what we kept for damage (that became a charge on the
			# bill at close-out, so it's revenue now - not held money)
			self.deposit_held = float(
				sum((Decimal(str(r.amount or 0)) for r in self.receipts
				     if r.kind == "Security Deposit"), Decimal(0))
				- Decimal(str(self.deposit_refunded or 0))
				- Decimal(str(self.damage_amount or 0)))
		self.balance_due = float(
			Decimal(str(self.grand_total))
			- Decimal(str(self.advance_received or 0)))

	def _payment_terms(self):
		"""A term stated as a percentage follows the quote as it moves; one
		stated as an amount is a number both sides agreed and stays put."""
		today = getdate(nowdate())
		for term in self.payment_terms:
			if term.percent and not term.amount:
				term.amount = round(
					float(self.grand_total or 0) * float(term.percent) / 100, 2)
			if term.status == "Pending" and term.due_date \
					and getdate(term.due_date) < today:
				term.status = "Overdue"
			elif term.status == "Overdue" and term.due_date \
					and getdate(term.due_date) >= today:
				term.status = "Pending"
			if term.status == "Received" and not term.received_on:
				term.received_on = nowdate()

	# ── guards ───────────────────────────────────────────────────────────

	def _guards(self):
		if self.status in ("Cancelled", "Lost") \
				and not (self.lost_reason or "").strip():
			frappe.throw(_("Say why this went away - a cancelled or lost "
			              "function needs a reason."))
		if self.status == "Confirmed":
			self._no_double_booking()
			over = self._over_capacity()
			if over:
				frappe.msgprint(over, indicator="orange", alert=True)
		alcohol_on_company = [
			r.item_name for r in self.items
			if r.is_alcohol and r.chargeable and self.company]
		if alcohol_on_company:
			# same rule the folio enforces: alcohol never rides a company bill
			frappe.msgprint(
				_("Alcohol ({0}) can't be billed to {1} - it will have to "
				  "settle separately.").format(
					", ".join(alcohol_on_company[:3]), self.company),
				indicator="orange", alert=True)

	def _over_capacity(self):
		cap = frappe.db.get_value("Venue", self.venue, "capacity")
		pax = self.billable_pax
		if cap and pax and pax > int(cap):
			return _("{0} seats {1}; this function is {2} pax.").format(
				self.venue, cap, pax)
		return None

	def _no_double_booking(self):
		"""A confirmed function owns the hall for its dates. Tentative holds
		don't block - they're meant to be pushed off by real business."""
		clash = overlapping(
			self.property, self.venue, self.event_date, self.end_date,
			self.start_time, self.end_time, exclude=self.name,
			statuses=BLOCKING_STATUSES)
		if clash:
			other = clash[0]
			frappe.throw(_(
				"{0} is already confirmed for {1} on {2}{3}. Move one of "
				"them, or use a different hall.").format(
					self.venue, other.customer_name, other.event_date,
					f" {other.start_time}-{other.end_time}"
					if other.start_time else ""))

	def on_update(self):
		self._sync_green_room()

	# ── the green room ───────────────────────────────────────────────────

	def _sync_green_room(self):
		"""Holding a changing room for the wedding party means taking it out
		of sale, not writing it on a note. The block follows the field:
		assign one and it's held, clear it or lose the function and it's
		released."""
		block = self.green_room_block
		if not self.green_room or self.status in ("Cancelled", "Lost"):
			if block and frappe.db.exists("Room Block", block):
				frappe.db.set_value("Room Block", block, "block_status",
				                    "Released", update_modified=False)
			if block:
				self.db_set("green_room_block", None, update_modified=False)
			return
		frm = getdate(self.green_room_from or self.event_date)
		# green_room_to is the last day the party needs the room; a Room
		# Block's to_date is exclusive, the way a checkout date is
		last_day = getdate(self.green_room_to or self.end_date or self.event_date)
		to = frappe.utils.add_days(max(last_day, frm), 1)
		note = _("Green room for {0} ({1})").format(self.customer_name, self.name)
		values = {"room": self.green_room, "from_date": frm, "to_date": to,
		          "block_status": "Active", "note": note}
		try:
			if block and frappe.db.exists("Room Block", block):
				doc = frappe.get_doc("Room Block", block)
				doc.update(values)
				doc.save(ignore_permissions=True)
				return
			doc = frappe.get_doc({
				"doctype": "Room Block", "property": self.property,
				"reason": "House Use", **values})
			doc.insert(ignore_permissions=True)
			self.db_set("green_room_block", doc.name, update_modified=False)
		except frappe.ValidationError as e:
			frappe.throw(_("Can't hold {0} as the green room: {1}").format(
				self.green_room, str(e)))


def overlapping(property: str, venue: str, event_date, end_date,
                start_time, end_time, exclude: str | None = None,
                statuses=BLOCKING_STATUSES):
	"""Other functions in the same hall whose dates - and, when both sides
	state them, whose hours - run into this one."""
	last_day = end_date or event_date
	filters = {
		"property": property, "venue": venue,
		"status": ("in", list(statuses)),
		"event_date": ("<=", last_day),
	}
	if exclude:
		filters["name"] = ("!=", exclude)
	rows = frappe.get_all(
		"Venue Booking", filters=filters,
		fields=["name", "customer_name", "event_date", "end_date",
		        "start_time", "end_time", "status"])
	out = []
	for r in rows:
		r_last = r.end_date or r.event_date
		if getdate(r_last) < getdate(event_date):
			continue
		if start_time and end_time and r.start_time and r.end_time:
			# both sides are hourly: only a real overlap counts, so two
			# functions can share a hall morning and evening
			if not _times_overlap(event_date, start_time, end_date, end_time,
			                      r.event_date, r.start_time, r.end_date,
			                      r.end_time):
				continue
		out.append(r)
	return out


def _times_overlap(d1, s1, e1d, e1, d2, s2, e2d, e2) -> bool:
	from frappe.utils import add_to_date

	a_start = get_datetime(f"{d1} {s1}")
	a_end = get_datetime(f"{e1d or d1} {e1}")
	b_start = get_datetime(f"{d2} {s2}")
	b_end = get_datetime(f"{e2d or d2} {e2}")
	if a_end <= a_start:
		a_end = add_to_date(a_end, days=1)
	if b_end <= b_start:
		b_end = add_to_date(b_end, days=1)
	return a_start < b_end and b_start < a_end
