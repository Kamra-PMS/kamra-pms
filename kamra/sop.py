# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Property-editable SOPs for desk procedures.

Covers checkout, check-in, cancel, walk-in and deposit. Tips are
deterministic from a context dict the caller builds from folio /
registration / policy state. The AI layer may only rephrase those tips , 
it never invents amounts. Flows work with no LLM configured.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from kamra.authz import require_roles

# Charge types → review groups shown in the checkout wizard.
CHARGE_GROUPS = {
	"Room": "Room",
	"Meal Plan": "Room",
	"Early Check-in": "Room",
	"Late Checkout": "Room",
	"Cleaning Fee": "Room",
	"Room Levy": "Room",
	"Food & Beverage": "Restaurant",
	"Minibar": "Restaurant",
	"Laundry": "Laundry",
	"Spa": "Spa",
	"Discount": "Discounts",
	"Allowance": "Discounts",
	"Misc": "Extras",
}

CHECKOUT_DEFAULT_STEPS = [
	{
		"step_key": "review_bills",
		"step_type": "auto_check",
		"title": "Review the bill",
		"instruction": "Walk the guest through every open folio: room nights, extras, and credits.",
		"prompt_to_guest": "",
		"is_blocking": 1,
		"sequence": 10,
	},
	{
		"step_key": "verify_restaurant",
		"step_type": "confirm",
		"title": "Verify restaurant & minibar charges",
		"instruction": "Confirm F&B and minibar lines with the guest before collecting.",
		"prompt_to_guest": "Were there any restaurant or minibar charges we should check?",
		"is_blocking": 0,
		"sequence": 20,
	},
	{
		"step_key": "check_damages",
		"step_type": "action",
		"title": "Check damages & security deposit",
		"instruction": "Ask housekeeping / inspect for damage. Withhold from the deposit or refund the balance.",
		"prompt_to_guest": "",
		"is_blocking": 1,
		"sequence": 30,
	},
	{
		"step_key": "confirm_discounts",
		"step_type": "confirm",
		"title": "Confirm discounts & vouchers",
		"instruction": "Confirm booking discounts and any mid-stay allowances are correct.",
		"prompt_to_guest": "",
		"is_blocking": 0,
		"sequence": 40,
	},
	{
		"step_key": "confirm_bill_to",
		"step_type": "confirm",
		"title": "Confirm billing instructions",
		"instruction": "Confirm which charges bill to the company vs the guest (alcohol always guest).",
		"prompt_to_guest": "",
		"is_blocking": 1,
		"sequence": 50,
	},
	{
		"step_key": "collect_settle",
		"step_type": "action",
		"title": "Collect payment or settle",
		"instruction": "Collect what is owed, refund overpayments, or send a corporate balance to the city ledger.",
		"prompt_to_guest": "",
		"is_blocking": 1,
		"sequence": 60,
	},
	{
		"step_key": "ask_feedback",
		"step_type": "ask_guest",
		"title": "Ask for feedback",
		"instruction": "Invite a short review of the stay. It keeps the farewell warm and useful.",
		"prompt_to_guest": "How was your stay with us? Is there anything we could have done better?",
		"is_blocking": 0,
		"sequence": 70,
	},
	{
		"step_key": "farewell",
		"step_type": "ask_guest",
		"title": "Wish farewell",
		"instruction": "Thank the guest, hand over any deposit refund, and wish them a safe journey.",
		"prompt_to_guest": "Thank you for staying with us, safe travels, and we hope to welcome you again.",
		"is_blocking": 0,
		"sequence": 80,
	},
]

CHECKIN_DEFAULT_STEPS = [
	{
		"step_key": "verify_identity",
		"step_type": "auto_check",
		"title": "Verify identity",
		"instruction": "Confirm ID is on file (or capture it on the GRC). Check-in is never blocked for a missing ID.",
		"prompt_to_guest": "May I see a government ID for the registration card?",
		"is_blocking": 0,
		"sequence": 10,
	},
	{
		"step_key": "confirm_registration",
		"step_type": "confirm",
		"title": "Confirm registration details",
		"instruction": "Phone, address, and occupants should be on the GRC before the night audit.",
		"prompt_to_guest": "",
		"is_blocking": 0,
		"sequence": 20,
	},
	{
		"step_key": "confirm_room",
		"step_type": "action",
		"title": "Confirm room is ready",
		"instruction": "Prefer a Clean or Inspected room. If Dirty, warn the guest: HK will see the flip to occupied.",
		"prompt_to_guest": "",
		"is_blocking": 0,
		"sequence": 30,
	},
	{
		"step_key": "collect_deposit",
		"step_type": "action",
		"title": "Collect advance / deposit",
		"instruction": "Take any outstanding advance or security deposit before handing keys.",
		"prompt_to_guest": "",
		"is_blocking": 0,
		"sequence": 40,
	},
	{
		"step_key": "note_requests",
		"step_type": "confirm",
		"title": "Note special requests",
		"instruction": "Read special requests aloud and confirm with the guest.",
		"prompt_to_guest": "",
		"is_blocking": 0,
		"sequence": 50,
	},
	{
		"step_key": "welcome",
		"step_type": "ask_guest",
		"title": "Welcome & keys",
		"instruction": "Hand over keys / access, Wi‑Fi, breakfast times, and wish them a pleasant stay.",
		"prompt_to_guest": "Welcome, here are your keys. Breakfast is served as noted; please let us know if you need anything.",
		"is_blocking": 0,
		"sequence": 60,
	},
]

CANCEL_DEFAULT_STEPS = [
	{
		"step_key": "confirm_booking",
		"step_type": "confirm",
		"title": "Confirm the booking",
		"instruction": "Read back the guest name and arrival date so you cancel the right stay.",
		"prompt_to_guest": "",
		"is_blocking": 1,
		"sequence": 10,
	},
	{
		"step_key": "check_policy",
		"step_type": "auto_check",
		"title": "Check cancellation policy",
		"instruction": "See whether the stay is inside the free-cancel window and what fee applies.",
		"prompt_to_guest": "",
		"is_blocking": 1,
		"sequence": 20,
	},
	{
		"step_key": "explain_fee",
		"step_type": "ask_guest",
		"title": "Explain the fee (or free cancel)",
		"instruction": "Tell the guest the fee clearly before you confirm. Waive only with a manager reason.",
		"prompt_to_guest": "",
		"is_blocking": 0,
		"sequence": 30,
	},
	{
		"step_key": "record_reason",
		"step_type": "confirm",
		"title": "Record the reason",
		"instruction": "Pick a cancellation reason (and a short note if useful): it is logged on the stay.",
		"prompt_to_guest": "",
		"is_blocking": 1,
		"sequence": 40,
	},
	{
		"step_key": "confirm_cancel",
		"step_type": "action",
		"title": "Confirm cancellation",
		"instruction": "Confirm only after the guest agrees. Give them the cancellation number and letter.",
		"prompt_to_guest": "",
		"is_blocking": 1,
		"sequence": 50,
	},
	{
		"step_key": "offer_rebook",
		"step_type": "ask_guest",
		"title": "Offer to rebook",
		"instruction": "If dates changed, offer to create a new booking before they leave the desk.",
		"prompt_to_guest": "Would you like me to book new dates while you're here?",
		"is_blocking": 0,
		"sequence": 60,
	},
]

WALKIN_DEFAULT_STEPS = [
	{
		"step_key": "verify_identity",
		"step_type": "confirm",
		"title": "Verify identity",
		"instruction": "Ask for a government ID, capture it on the GRC after check-in if needed.",
		"prompt_to_guest": "May I see a government ID for registration?",
		"is_blocking": 0,
		"sequence": 10,
	},
	{
		"step_key": "pick_ready_room",
		"step_type": "action",
		"title": "Pick a ready room",
		"instruction": "Prefer Clean or Inspected. Warn the guest before handing a Dirty room.",
		"prompt_to_guest": "",
		"is_blocking": 1,
		"sequence": 20,
	},
	{
		"step_key": "confirm_rate",
		"step_type": "confirm",
		"title": "Confirm rate & meal plan",
		"instruction": "Read back tonight's rate, meal plan, and taxes before collecting.",
		"prompt_to_guest": "",
		"is_blocking": 1,
		"sequence": 30,
	},
	{
		"step_key": "collect_payment",
		"step_type": "action",
		"title": "Collect payment",
		"instruction": "Take payment for the stay (and deposit if your policy asks) before handing keys.",
		"prompt_to_guest": "",
		"is_blocking": 1,
		"sequence": 40,
	},
	{
		"step_key": "welcome",
		"step_type": "ask_guest",
		"title": "Welcome & keys",
		"instruction": "Hand over keys / access, Wi‑Fi, breakfast times, and wish them a pleasant stay.",
		"prompt_to_guest": "Welcome, here are your keys. Please let us know if you need anything.",
		"is_blocking": 0,
		"sequence": 50,
	},
]

DEPOSIT_DEFAULT_STEPS = [
	{
		"step_key": "quote_expected",
		"step_type": "auto_check",
		"title": "Quote the expected deposit",
		"instruction": "Tell the guest the policy amount (or %) still due to secure the booking.",
		"prompt_to_guest": "",
		"is_blocking": 0,
		"sequence": 10,
	},
	{
		"step_key": "collect_or_link",
		"step_type": "action",
		"title": "Collect at desk or send a link",
		"instruction": "Record cash/card at the till, or send a payment link. Either posts as an Advance on the folio.",
		"prompt_to_guest": "",
		"is_blocking": 1,
		"sequence": 20,
	},
	{
		"step_key": "confirm_receipt",
		"step_type": "confirm",
		"title": "Confirm receipt / link sent",
		"instruction": "Give a receipt or confirm the link arrived. Note any part-payment remaining.",
		"prompt_to_guest": "",
		"is_blocking": 0,
		"sequence": 30,
	},
	{
		"step_key": "remind_balance",
		"step_type": "ask_guest",
		"title": "Remind of balance before arrival",
		"instruction": "If anything is still due, say when it should be paid (before arrival or at check-in).",
		"prompt_to_guest": "Any remaining balance can be settled before arrival or at check-in.",
		"is_blocking": 0,
		"sequence": 40,
	},
]

EARLY_CHECKIN_DEFAULT_STEPS = [
	{
		"step_key": "confirm_time",
		"step_type": "confirm",
		"title": "Confirm early arrival time",
		"instruction": "Agree the arrival time against the property's standard check-in.",
		"prompt_to_guest": "",
		"is_blocking": 1,
		"sequence": 10,
	},
	{
		"step_key": "check_room_ready",
		"step_type": "confirm",
		"title": "Check the room is ready",
		"instruction": "HK must have the room Clean/Inspected before an early hand-over.",
		"prompt_to_guest": "",
		"is_blocking": 0,
		"sequence": 20,
	},
	{
		"step_key": "agree_fee",
		"step_type": "ask_guest",
		"title": "Agree the fee (or waive)",
		"instruction": "Quote free / half night / full night from the nightly rate, then confirm with the guest.",
		"prompt_to_guest": "",
		"is_blocking": 1,
		"sequence": 30,
	},
	{
		"step_key": "post_fee",
		"step_type": "action",
		"title": "Post the fee (or record waive)",
		"instruction": "Post Early Check-in on the folio, or waive at zero: both are logged.",
		"prompt_to_guest": "",
		"is_blocking": 1,
		"sequence": 40,
	},
]

LATE_CHECKOUT_DEFAULT_STEPS = [
	{
		"step_key": "confirm_time",
		"step_type": "confirm",
		"title": "Confirm departure time",
		"instruction": "Agree how late they will leave against the property's standard check-out.",
		"prompt_to_guest": "",
		"is_blocking": 1,
		"sequence": 10,
	},
	{
		"step_key": "check_next_guest",
		"step_type": "confirm",
		"title": "Check the next arrival",
		"instruction": "If the room has a same-day arrival, confirm HK turnaround still works.",
		"prompt_to_guest": "",
		"is_blocking": 0,
		"sequence": 20,
	},
	{
		"step_key": "agree_fee",
		"step_type": "ask_guest",
		"title": "Agree the fee (or waive)",
		"instruction": "Quote free / half night / full night. Extra calendar night is a date amend, not this fee.",
		"prompt_to_guest": "",
		"is_blocking": 1,
		"sequence": 30,
	},
	{
		"step_key": "post_fee",
		"step_type": "action",
		"title": "Post the fee (or record waive)",
		"instruction": "Post Late Checkout on the folio, or waive at zero: both are logged. ETD updates on the stay.",
		"prompt_to_guest": "",
		"is_blocking": 1,
		"sequence": 40,
	},
]

DEFAULT_SOP_SEEDS = {
	"checkout": ("Checkout", CHECKOUT_DEFAULT_STEPS),
	"checkin": ("Check-in", CHECKIN_DEFAULT_STEPS),
	"cancel": ("Cancel booking", CANCEL_DEFAULT_STEPS),
	"walkin": ("Walk-in", WALKIN_DEFAULT_STEPS),
	"deposit": ("Deposit", DEPOSIT_DEFAULT_STEPS),
	"early_checkin": ("Early check-in", EARLY_CHECKIN_DEFAULT_STEPS),
	"late_checkout": ("Late checkout", LATE_CHECKOUT_DEFAULT_STEPS),
}


def group_for_charge(charge_type: str, description: str = "") -> str:
	"""Map a folio charge line into a review group."""
	desc = (description or "").lower()
	if "damage" in desc or "withhold" in desc:
		return "Damages"
	return CHARGE_GROUPS.get(charge_type or "", "Extras")


def format_money(symbol: str, amount: float) -> str:
	return f"{symbol}{flt(amount):,.2f}"


def evaluate_checkout_step(step: dict, context: dict) -> dict:
	"""Evaluate one checkout SOP step against a checkout_context dict.

	Returns state (done / blocked / todo) and a plain-language tip. Amounts
	are taken only from context, never recomputed here.
	"""
	key = (step.get("step_key") or "").strip()
	symbol = context.get("currency_symbol") or ""
	blockers = context.get("blockers") or []
	totals = context.get("totals") or {}
	deposit = context.get("deposit") or {}
	groups = context.get("groups") or {}
	billing = context.get("billing") or {}
	actions = context.get("actions") or {}

	owed = flt(totals.get("owed") or 0)
	refund = flt(totals.get("refund_due") or 0)
	restaurant = flt((groups.get("Restaurant") or {}).get("amount") or 0)
	discounts = flt((groups.get("Discounts") or {}).get("amount") or 0)
	damages = flt((groups.get("Damages") or {}).get("amount") or 0)
	dep_bal = flt(deposit.get("balance") or 0)
	dep_held = flt(deposit.get("collected_amount") or 0)
	can_checkout = bool(actions.get("can_checkout"))
	can_city = bool(actions.get("can_city_ledger"))

	state = "todo"
	tip = (step.get("instruction") or "").strip()

	if key == "review_bills":
		n_folios = len(context.get("folios") or [])
		tip = _("Review {0} open folio(s). Total charges {1}, paid {2}.").format(
			n_folios,
			format_money(symbol, totals.get("charges") or 0),
			format_money(symbol, totals.get("paid") or 0),
		)
		state = "done" if n_folios else "todo"

	elif key == "verify_restaurant":
		if restaurant:
			tip = _("Confirm {0} in restaurant / minibar charges with the guest.").format(
				format_money(symbol, restaurant))
			state = "todo"
		else:
			tip = _("No restaurant or minibar charges on this stay.")
			state = "done"

	elif key == "check_damages":
		if damages:
			tip = _("Damage / withhold of {0} is already on the bill: confirm with the guest.").format(
				format_money(symbol, damages))
			state = "done"
		elif dep_held > 0.009 and dep_bal > 0.009:
			tip = _("Security deposit {0} is held ({1} refundable). Check the room; withhold damage or refund.").format(
				format_money(symbol, dep_held), format_money(symbol, dep_bal))
			state = "todo"
		elif dep_held > 0.009 and dep_bal <= 0.009:
			tip = _("Deposit is fully applied or refunded: nothing left to withhold.")
			state = "done"
		else:
			tip = _("No security deposit on this stay. Note any damage as a Misc charge before settling.")
			state = "done"

	elif key == "confirm_discounts":
		if discounts:
			# discounts are negative amounts
			tip = _("Confirm discount / voucher / allowance lines totaling {0}.").format(
				format_money(symbol, discounts))
			state = "todo"
		else:
			tip = _("No discount or voucher lines on the folio.")
			state = "done"

	elif key == "confirm_bill_to":
		rules = billing.get("rules") or []
		company = billing.get("company_name") or billing.get("company")
		if company and rules:
			parts = [f"{r.get('charge_type')}: {r.get('pay_by')}" for r in rules[:6]]
			tip = _("Bill-to for {0}: {1}. Alcohol always bills the guest.").format(
				company, "; ".join(parts))
		elif company:
			tip = _("Corporate stay for {0}, confirm which charges the company pays.").format(company)
		else:
			tip = _("Guest pays the bill (no company on this stay).")
			state = "done"
		if company:
			state = "todo"

	elif key == "collect_settle":
		city_amt = flt(totals.get("city_ledger_eligible") or 0)
		if owed > 0.009:
			tip = _("Collect {0} before departure.").format(format_money(symbol, owed))
			state = "blocked" if step.get("is_blocking") else "todo"
		elif refund > 0.009:
			tip = _("Refund {0} before departure.").format(format_money(symbol, refund))
			state = "blocked" if step.get("is_blocking") else "todo"
		elif can_city and city_amt > 0.009:
			# Credit company: check_out auto-transfers; tip asks the desk to confirm.
			tip = _("{0} can move to the city ledger (company has credit). Confirm, then check out.").format(
				format_money(symbol, city_amt))
			state = "todo"
		elif can_checkout:
			tip = _("Balances are clear: ready to check out.")
			state = "done"
		elif blockers:
			tip = blockers[0].get("message") or tip
			state = "blocked" if step.get("is_blocking") else "todo"
		else:
			state = "todo"

	elif key == "ask_feedback":
		tip = step.get("prompt_to_guest") or tip
		state = "todo"

	elif key == "farewell":
		if dep_bal > 0.009:
			tip = _("Wish farewell and return the remaining deposit of {0}.").format(
				format_money(symbol, dep_bal))
		else:
			tip = step.get("prompt_to_guest") or tip
		state = "todo"

	return {
		**step,
		"state": state,
		"tip": tip,
	}


def evaluate_checkin_step(step: dict, context: dict) -> dict:
	"""Evaluate one check-in SOP step. Never hard-blocks departure of check-in."""
	key = (step.get("step_key") or "").strip()
	ready = context.get("readiness") or {}
	room = context.get("room_assigned") or context.get("chosen_room") or {}
	suggestion = context.get("suggestion") or {}
	deposit = context.get("deposit") or {}
	requests = (context.get("special_requests") or "").strip()
	hk = room.get("housekeeping_status") or ""

	state = "todo"
	tip = (step.get("instruction") or "").strip()

	if key == "verify_identity":
		if ready.get("id_on_file"):
			tip = _("ID is on file: confirm it matches the guest at the desk.")
			state = "done"
		else:
			tip = _("No ID on file yet: capture it on the GRC (check-in still allowed).")
			state = "todo"

	elif key == "confirm_registration":
		missing = []
		if not ready.get("phone"):
			missing.append(_("phone"))
		if not ready.get("address_on_file"):
			missing.append(_("address"))
		if missing:
			tip = _("Still missing on the GRC: {0}.").format(", ".join(missing))
			state = "todo"
		else:
			tip = _("Registration details look complete.")
			state = "done"

	elif key == "confirm_room":
		num = room.get("room_number") or suggestion.get("room_number")
		if not num:
			tip = _("Pick a room before check-in.")
			state = "todo"
		elif hk == "Dirty":
			tip = _("Room {0} is Dirty: warn the guest; HK will see it flip to occupied.").format(num)
			state = "todo"
		elif hk in ("Clean", "Inspected"):
			tip = _("Room {0} is {1}: ready to hand over.").format(num, _(hk))
			state = "done"
		else:
			tip = _("Room {0} · {1}.").format(num, _(hk) if hk else _("unassigned"))
			state = "todo"

	elif key == "collect_deposit":
		due = flt(deposit.get("due") or 0)
		can_take = bool(deposit.get("can_take"))
		if can_take and due > 0.009:
			symbol = context.get("currency_symbol") or ""
			tip = _("Collect advance / deposit of {0} before handing keys.").format(
				format_money(symbol, due))
			state = "todo"
		else:
			tip = _("No deposit due at check-in.")
			state = "done"

	elif key == "note_requests":
		if requests:
			tip = _("Special requests: {0}").format(requests)
			state = "todo"
		else:
			tip = _("No special requests on this booking.")
			state = "done"

	elif key == "welcome":
		tip = step.get("prompt_to_guest") or tip
		state = "todo"

	return {**step, "state": state, "tip": tip}


def evaluate_cancel_step(step: dict, context: dict) -> dict:
	"""Evaluate one cancel-booking SOP step from cancellation_preview context."""
	key = (step.get("step_key") or "").strip()
	symbol = context.get("currency_symbol") or ""
	preview = context.get("preview") or {}
	guest = (context.get("guest_name") or "").strip()
	check_in = context.get("check_in_date") or ""
	reason = (context.get("reason") or "").strip()
	waive = bool(context.get("waive"))
	fee = flt(preview.get("estimated_fee") or 0)
	inside = bool(preview.get("inside_window"))
	basis = preview.get("fee_basis") or "None"
	days = int(preview.get("days_before_arrival") or 0)

	state = "todo"
	tip = (step.get("instruction") or "").strip()

	if key == "confirm_booking":
		if guest and check_in:
			tip = _("Cancelling {0} · arrival {1}.").format(guest, check_in)
			state = "done"
		elif guest:
			tip = _("Confirm you are cancelling {0}.").format(guest)
			state = "todo"
		else:
			tip = _("Confirm guest name and arrival before cancelling.")
			state = "todo"

	elif key == "check_policy":
		if inside and basis != "None" and fee > 0.009:
			tip = _(
				"{0} day(s) before arrival: inside the fee window. "
				"Estimated fee {1} ({2})."
			).format(days, format_money(symbol, fee), _(basis))
			state = "todo"
		else:
			tip = _(
				"{0} day(s) before arrival: outside the fee window (or no fee). "
				"Cancellation is free."
			).format(days)
			state = "done"

	elif key == "explain_fee":
		if waive and fee > 0.009:
			tip = _(
				"Fee of {0} will be WAIVED: manager call, logged on the stay. "
				"Tell the guest cancellation is free."
			).format(format_money(symbol, fee))
			state = "todo"
		elif inside and basis != "None" and fee > 0.009:
			tip = _(
				"Explain the {0} cancellation fee ({1}) before they confirm."
			).format(format_money(symbol, fee), _(basis))
			state = "todo"
		else:
			tip = _("Tell the guest cancellation is free under the policy.")
			state = "done"

	elif key == "record_reason":
		if reason:
			tip = _("Reason on file: {0}.").format(_(reason))
			state = "done"
		else:
			tip = _("Pick a cancellation reason before confirming.")
			state = "todo"

	elif key == "confirm_cancel":
		tip = _(
			"Confirm only when the guest agrees. They get a cancellation number "
			"and a printable letter."
		)
		state = "todo"

	elif key == "offer_rebook":
		tip = step.get("prompt_to_guest") or tip
		state = "todo"

	return {**step, "state": state, "tip": tip}


def evaluate_walkin_step(step: dict, context: dict) -> dict:
	"""Evaluate walk-in SOP tips from booking-dialog context."""
	key = (step.get("step_key") or "").strip()
	symbol = context.get("currency_symbol") or ""
	room = context.get("room") or {}
	hk = room.get("housekeeping_status") or context.get("housekeeping_status") or ""
	room_number = room.get("room_number") or context.get("room_number") or ""
	total = flt(context.get("amount_after_tax") or context.get("grand_total") or 0)
	meal = (context.get("meal_plan_label") or context.get("meal_plan") or "").strip()
	guest = (context.get("guest_name") or "").strip()
	paid = flt(context.get("collect_amount") or context.get("paid") or 0)

	state = "todo"
	tip = (step.get("instruction") or "").strip()

	if key == "verify_identity":
		if guest:
			tip = _("Verify ID for {0}, capture on the GRC after check-in if needed.").format(
				guest)
			state = "todo"
		else:
			tip = _("Ask for the guest's name and a government ID.")
			state = "todo"

	elif key == "pick_ready_room":
		if not room_number:
			tip = _("Pick a free room for tonight before collecting.")
			state = "todo"
		elif hk == "Dirty":
			tip = _("Room {0} is Dirty: warn the guest before handing keys.").format(
				room_number)
			state = "todo"
		elif hk in ("Clean", "Inspected"):
			tip = _("Room {0} is {1}: ready for walk-in.").format(room_number, _(hk))
			state = "done"
		else:
			tip = _("Room {0} selected.").format(room_number)
			state = "todo"

	elif key == "confirm_rate":
		bits = []
		if total > 0.009:
			bits.append(format_money(symbol, total))
		if meal:
			bits.append(meal)
		if bits:
			tip = _("Confirm with the guest: {0}.").format(" · ".join(bits))
			state = "todo"
		else:
			tip = _("Confirm tonight's rate and meal plan before collecting.")
			state = "todo"

	elif key == "collect_payment":
		if paid > 0.009:
			tip = _("Collecting {0} now, then check in and hand keys.").format(
				format_money(symbol, paid))
			state = "todo"
		elif total > 0.009:
			tip = _("Collect {0} (or note company billing) before handing keys.").format(
				format_money(symbol, total))
			state = "todo"
		else:
			tip = _("Enter the amount to collect, then confirm the walk-in.")
			state = "todo"

	elif key == "welcome":
		if room_number:
			tip = _("Hand over keys for room {0}. {1}").format(
				room_number,
				step.get("prompt_to_guest") or _("Welcome, please let us know if you need anything."),
			)
		else:
			tip = step.get("prompt_to_guest") or tip
		state = "todo"

	return {**step, "state": state, "tip": tip}


def evaluate_deposit_step(step: dict, context: dict) -> dict:
	"""Evaluate deposit SOP tips from DepositState context."""
	key = (step.get("step_key") or "").strip()
	symbol = context.get("currency_symbol") or ""
	deposit = context.get("deposit") or context
	pct = flt(deposit.get("pct") or 0)
	expected = flt(deposit.get("expected") or 0)
	paid = flt(deposit.get("paid") or 0)
	due = flt(deposit.get("due") or 0)
	link_url = deposit.get("link_url")
	can_take = bool(deposit.get("can_take"))

	state = "todo"
	tip = (step.get("instruction") or "").strip()

	if key == "quote_expected":
		if expected > 0.009:
			if pct > 0:
				tip = _("Policy deposit {0} ({1}% of stay). Still due {2}.").format(
					format_money(symbol, expected),
					int(pct) if pct == int(pct) else pct,
					format_money(symbol, due),
				)
			else:
				tip = _("Expected deposit {0}. Still due {1}.").format(
					format_money(symbol, expected),
					format_money(symbol, due),
				)
			state = "done" if due <= 0.009 else "todo"
		else:
			tip = _("No fixed deposit %: take an advance amount the guest agrees.")
			state = "todo" if can_take else "done"

	elif key == "collect_or_link":
		if due <= 0.009 and paid > 0.009:
			tip = _("Deposit secured ({0} received).").format(format_money(symbol, paid))
			state = "done"
		elif link_url and due > 0.009:
			tip = _("Payment link already sent: follow up or record a desk payment of {0}.").format(
				format_money(symbol, due))
			state = "todo"
		elif can_take and due > 0.009:
			tip = _("Collect {0} at the desk or send a payment link.").format(
				format_money(symbol, due))
			state = "todo"
		else:
			tip = _("Deposit not open for collection on this booking.")
			state = "done"

	elif key == "confirm_receipt":
		if due <= 0.009 and paid > 0.009:
			tip = _("Confirm the guest has a receipt / link confirmation for {0}.").format(
				format_money(symbol, paid))
			state = "done"
		elif link_url:
			tip = _("Confirm the payment link reached the guest.")
			state = "todo"
		elif paid > 0.009:
			tip = _("Part paid {0}: give a receipt for what was taken.").format(
				format_money(symbol, paid))
			state = "todo"
		else:
			tip = _("After collecting, give a receipt or confirm the link.")
			state = "todo"

	elif key == "remind_balance":
		if due > 0.009:
			tip = _(
				"Still due {0} before arrival (or at check-in). Tell the guest clearly."
			).format(format_money(symbol, due))
			state = "todo"
		else:
			tip = step.get("prompt_to_guest") or _(
				"Deposit is secured: remaining stay balance settles at check-in / check-out."
			)
			state = "done"

	return {**step, "state": state, "tip": tip}


def evaluate_early_late_step(step: dict, context: dict) -> dict:
	"""Shared tips for early check-in / late checkout fee walkthrough."""
	key = (step.get("step_key") or "").strip()
	symbol = context.get("currency_symbol") or ""
	kind = context.get("kind") or "late_checkout"
	std = context.get("standard_time") or ""
	until = context.get("until_time") or ""
	nightly = flt(context.get("nightly_rate") or 0)
	existing_n = int(context.get("existing_count") or 0)
	existing_total = flt(context.get("existing_total") or 0)
	amount = context.get("amount")
	amount_f = flt(amount) if amount is not None else None
	label = _("early check-in") if kind == "early_checkin" else _("late checkout")

	state = "todo"
	tip = (step.get("instruction") or "").strip()

	if key == "confirm_time":
		if until and std:
			tip = _("Standard {0} · agreed {1} for {2}.").format(std, until, label)
			state = "done" if until != std else "todo"
		elif std:
			tip = _("Property standard is {0}. Pick the agreed time for {1}.").format(
				std, label)
			state = "todo"
		else:
			tip = _("Confirm the agreed time for {0}.").format(label)
			state = "todo"

	elif key in ("check_room_ready", "check_next_guest"):
		tip = step.get("instruction") or tip
		state = "todo"

	elif key == "agree_fee":
		if amount_f is not None and amount_f <= 0.009:
			tip = _("Fee waived (free {0}). Confirm with the guest, then save.").format(label)
			state = "todo"
		elif amount_f is not None and amount_f > 0.009:
			tip = _("Agreed fee {0} for {1}. Confirm with the guest before posting.").format(
				format_money(symbol, amount_f), label)
			state = "todo"
		elif nightly > 0.009:
			tip = _(
				"Quote free, half night ({0}), or full night ({1}) for {2}."
			).format(
				format_money(symbol, nightly * 0.5),
				format_money(symbol, nightly),
				label,
			)
			state = "todo"
		else:
			tip = _("Agree a fee amount with the guest (or waive).")
			state = "todo"

	elif key == "post_fee":
		if existing_n:
			tip = _(
				"{0} existing {1} line(s) totaling {2}: avoid a duplicate unless intentional."
			).format(
				existing_n,
				context.get("charge_type") or label,
				format_money(symbol, existing_total),
			)
			state = "todo"
		elif amount_f is not None and amount_f <= 0.009:
			tip = _("Save as waived: no folio charge, stay time still updates.")
			state = "todo"
		elif amount_f is not None:
			tip = _("Post {0} as {1} on the folio.").format(
				format_money(symbol, amount_f),
				context.get("charge_type") or label,
			)
			state = "todo"
		else:
			tip = step.get("instruction") or tip
			state = "todo"

	return {**step, "state": state, "tip": tip}


def evaluate_sop_steps(key: str, steps: list[dict], context: dict) -> list[dict]:
	"""Evaluate template steps for a procedure key."""
	out = []
	evaluators = {
		"checkout": evaluate_checkout_step,
		"checkin": evaluate_checkin_step,
		"cancel": evaluate_cancel_step,
		"walkin": evaluate_walkin_step,
		"deposit": evaluate_deposit_step,
		"early_checkin": evaluate_early_late_step,
		"late_checkout": evaluate_early_late_step,
	}
	fn = evaluators.get(key)
	for raw in steps:
		step = {
			"step_key": raw.get("step_key") or "",
			"step_type": raw.get("step_type") or "confirm",
			"title": raw.get("title") or "",
			"instruction": raw.get("instruction") or "",
			"prompt_to_guest": raw.get("prompt_to_guest") or "",
			"is_blocking": 1 if int(raw.get("is_blocking") or 0) else 0,
			"sequence": int(raw.get("sequence") or 0),
		}
		if fn:
			out.append(fn(step, context))
		else:
			out.append({**step, "state": "todo", "tip": step["instruction"]})
	out.sort(key=lambda s: s["sequence"])
	return out


def next_tip(steps: list[dict]) -> str | None:
	"""First non-done tip, preferring blocked then todo."""
	blocked = [s for s in steps if s.get("state") == "blocked"]
	todo = [s for s in steps if s.get("state") == "todo"]
	for bucket in (blocked, todo):
		if bucket:
			return bucket[0].get("tip") or bucket[0].get("title")
	return None


def ensure_default_sops(property: str) -> int:
	"""Seed default desk SOPs for a property. Idempotent (missing keys only)."""
	if not property or not frappe.db.exists("Property", property):
		return 0
	if not frappe.db.exists("DocType", "SOP Template"):
		return 0
	created = 0
	for key, (title, steps) in DEFAULT_SOP_SEEDS.items():
		if frappe.db.exists("SOP Template", {"property": property, "key": key}):
			continue
		doc = frappe.get_doc({
			"doctype": "SOP Template",
			"property": property,
			"key": key,
			"title": title,
			"active": 1,
			"steps": list(steps),
		})
		doc.insert(ignore_permissions=True)
		created += 1
	return created


def ensure_default_sops_all_properties() -> int:
	created = 0
	for prop in frappe.get_all("Property", pluck="name"):
		created += ensure_default_sops(prop)
	return created


def _template_steps(property: str, key: str) -> tuple[dict | None, list[dict]]:
	# the SOP Template doctype is optional: without it (or before migrate)
	# the in-code defaults drive the wizards
	has_templates = bool(frappe.db.exists("DocType", "SOP Template"))
	if has_templates:
		ensure_default_sops(property)
	name = frappe.db.get_value(
		"SOP Template",
		{"property": property, "key": key, "active": 1},
		"name",
	) if has_templates else None
	if not name:
		# fall back to in-code defaults so wizards always work pre-migrate
		seed = DEFAULT_SOP_SEEDS.get(key)
		if seed:
			title, steps = seed
			return (
				{"name": None, "key": key, "title": title, "active": 1},
				list(steps),
			)
		return None, []
	doc = frappe.get_doc("SOP Template", name)
	steps = [
		{
			"step_key": s.step_key,
			"step_type": s.step_type,
			"title": s.title,
			"instruction": s.instruction or "",
			"prompt_to_guest": s.prompt_to_guest or "",
			"is_blocking": 1 if s.is_blocking else 0,
			"sequence": int(s.sequence or 0),
		}
		for s in (doc.steps or [])
	]
	meta = {
		"name": doc.name,
		"key": doc.key,
		"title": doc.title,
		"active": 1 if doc.active else 0,
	}
	return meta, steps


@frappe.whitelist()
@require_roles("Front Desk", "Kamra Agent", "Hotel Admin")
def get_sop(property: str, key: str, context=None):
	"""Return evaluated SOP steps for a procedure.

	context is optional JSON (checkout_context shape for key=checkout). When
	omitted, steps return as todo with template tips only.
	"""
	if isinstance(context, str):
		context = frappe.parse_json(context) if context else {}
	context = context or {}
	meta, steps = _template_steps(property, (key or "").strip().lower())
	if not meta:
		return {"key": key, "title": None, "steps": [], "next_tip": None}
	evaluated = evaluate_sop_steps(meta["key"], steps, context)
	return {
		"name": meta.get("name"),
		"key": meta["key"],
		"title": meta["title"],
		"steps": evaluated,
		"next_tip": next_tip(evaluated),
		"blocking_unresolved": any(
			s.get("is_blocking") and s.get("state") in ("blocked", "todo")
			and s.get("step_type") == "action"
			and s.get("state") == "blocked"
			for s in evaluated
		),
	}


@frappe.whitelist()
@require_roles("Hotel Admin", "System Manager", "Front Desk", "Kamra Agent")
def list_sops(property: str):
	"""List SOP templates for the settings editor."""
	ensure_default_sops(property)
	rows = frappe.get_all(
		"SOP Template",
		filters={"property": property},
		fields=["name", "key", "title", "active", "modified"],
		order_by="key asc",
	)
	return rows


@frappe.whitelist()
@require_roles("Hotel Admin", "System Manager")
def get_sop_template(name: str):
	doc = frappe.get_doc("SOP Template", name)
	return {
		"name": doc.name,
		"property": doc.property,
		"key": doc.key,
		"title": doc.title,
		"active": 1 if doc.active else 0,
		"steps": [
			{
				"name": s.name,
				"step_key": s.step_key,
				"step_type": s.step_type,
				"title": s.title,
				"instruction": s.instruction or "",
				"prompt_to_guest": s.prompt_to_guest or "",
				"is_blocking": 1 if s.is_blocking else 0,
				"sequence": int(s.sequence or 0),
			}
			for s in (doc.steps or [])
		],
	}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin", "System Manager")
def save_sop_template(name: str | None = None, property: str | None = None,
                      key: str | None = None, title: str | None = None,
                      active: int = 1, steps=None):
	"""Create or update an SOP template and its steps."""
	if isinstance(steps, str):
		steps = frappe.parse_json(steps) if steps else []
	steps = steps or []
	if name and frappe.db.exists("SOP Template", name):
		doc = frappe.get_doc("SOP Template", name)
	else:
		if not property or not key:
			frappe.throw(_("property and key are required to create an SOP."))
		doc = frappe.get_doc({
			"doctype": "SOP Template",
			"property": property,
			"key": key,
		})
	if title is not None:
		doc.title = title
	if key is not None and not doc.name:
		doc.key = key
	doc.active = 1 if int(active or 0) else 0
	doc.set("steps", [])
	for i, s in enumerate(steps):
		doc.append("steps", {
			"step_key": (s.get("step_key") or "").strip(),
			"step_type": s.get("step_type") or "confirm",
			"title": s.get("title") or "",
			"instruction": s.get("instruction") or "",
			"prompt_to_guest": s.get("prompt_to_guest") or "",
			"is_blocking": 1 if int(s.get("is_blocking") or 0) else 0,
			"sequence": int(s.get("sequence") if s.get("sequence") is not None else (i + 1) * 10),
		})
	if doc.is_new():
		doc.insert()
	else:
		doc.save()
	return get_sop_template(doc.name)


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin", "System Manager")
def seed_sop_templates(property: str):
	n = ensure_default_sops(property)
	return {"ok": True, "created": n}
