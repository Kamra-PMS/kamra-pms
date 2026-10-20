# MCP tool reference

Kamra exposes **112 governed tools** on the hosted MCP
endpoint (`/mcp`) and the stdio sidecar (`mcp/kamra_mcp.py`). Every
call runs as the connected user - **role** permissions apply, tools
are further filtered by the property's **enabled modules**, prices
come from the pricing engine, and each action is recorded in the
activity ledger.

This page is generated from `kamra/mcp_tools.py`. Re-run
`python3 gen_mcp_tools.py` in `docs-site/` when the registry changes.

## Front desk

### `front_desk_today()`

Today's snapshot: arrivals, departures, in-house guests, room board
and the hours-saved counter.

Endpoint: `kamra.api.front_desk_snapshot`.

### `availability(start_date, days)`

Room availability and nightly rates per room type for the next N
days. start_date YYYY-MM-DD (default today).

Endpoint: `kamra.api.availability_calendar`.

### `quote(room_type, check_in_date, check_out_date, adults, children, meal_plan, rate_plan, voucher_code, company)`

Price a stay (deterministic: occupancy pricing, seasons, meal plan,
voucher, GST). Use before every booking. Room type, meal plan and rate
plan accept the id, code or exact name; an unknown or ambiguous value
is refused with the valid options.

Endpoint: `kamra.api.get_quote`.

### `booking_options()`

Room types, meal plans, rate plans and corporate accounts available
for booking at this property.

Endpoint: `kamra.api.booking_options`.

### `create_booking(guest_name, room_type, check_in_date, check_out_date, phone, adults, children, meal_plan, rate_plan, voucher_code, company, idempotency_key)`

Create a reservation. Dedupes the guest by phone, auto-assigns a
free room, applies the voucher, prices via the engine. Room type,
meal plan and rate plan accept the id, code or exact name. Safe to
retry: a repeated call returns the existing booking (see
idempotency_key) - check idempotent_replay in the result.

Endpoint: `kamra.api.create_booking`.
Mutating - logged to the activity ledger.

### `add_to_waitlist(guest_name, room_type, check_in_date, check_out_date, phone, adults, children, idempotency_key)`

Park a stay on the waitlist (no room) - for dates that are sold out or
restricted. Promote it later with promote_waitlist when a room frees.

Endpoint: `kamra.api.create_booking`.
Mutating - logged to the activity ledger.

### `waitlist_ready()`

Waitlisted stays that can NOW be booked - a room has freed up for their
dates. Each item includes the guest name and phone, so you can proactively
reach out. Poll this to catch openings the moment they appear - the wedge
for turning a sold-out 'no' into a booking.

Endpoint: `kamra.api.waitlist_ready`.

### `promote_waitlist(reservation)`

Promote a waitlisted stay into a free room (Confirmed). Fails if no room
is free for its dates.

Endpoint: `kamra.api.promote_waitlist`.
Mutating - logged to the activity ledger.

### `cancellation_preview(reservation)`

What cancelling would cost right now (policy window, fee basis,
estimated fee). ALWAYS read this to the guest before cancelling.

Endpoint: `kamra.api.cancellation_preview`.

### `cancel_booking(reservation, reason, note, waive_fee)`

Cancel a confirmed booking. The property's cancellation policy
applies automatically - free outside the window, else the configured
fee posts to the folio. Returns a cancellation number - always give
it to the guest. Reasons: Guest request, Change of plans, Duplicate
booking, Payment failed, Weather / travel disruption, Booked
elsewhere, Other. Only waive the fee when a manager authorizes it;
the waiver is logged.

Endpoint: `kamra.api.cancel_reservation`.
Mutating - logged to the activity ledger.

### `booking_requests()`

Pending Request-to-Book stays (status Requested) waiting for the
host, with whether each can be accepted right now (rooms_free,
blocker). A request holds NO room until it is accepted.

Endpoint: `kamra.booking_requests.booking_requests`.

### `accept_booking_request(reservation, room)`

Accept a Request-to-Book stay: confirms it and takes a room of its
type (or the room given). Refused when the dates sold out meanwhile,
the villa/room lockout applies or a group block holds the rooms -
then decline it or offer other dates.

Endpoint: `kamra.booking_requests.accept_booking_request`.
Mutating - logged to the activity ledger.

### `decline_booking_request(reservation, reason)`

Decline a Request-to-Book stay. A reason is required and is sent
to the guest (WhatsApp / email when the property has them set up).
No cancellation fee - the stay was never confirmed.

Endpoint: `kamra.booking_requests.decline_booking_request`.
Mutating - logged to the activity ledger.

### `check_in_readiness(reservation)`

Read-only: the property's check-in steps for a stay (ID, who
pays, room, deposit, registration card, keys...), which are done
and by whom, and which REQUIRED steps are still open. check_in is
refused until those are done by the front desk in the guided
check-in; an agent cannot do or skip them.

Endpoint: `kamra.checkin.check_in_readiness`.

### `check_in(reservation, room)`

Check a guest in (opens their folio, marks the room occupied).
Refused while a required check-in step is open; call
check_in_readiness first and tell the desk what is missing.

Endpoint: `kamra.api.check_in`.
Mutating - logged to the activity ledger.

### `check_out(reservation)`

Check a guest out (posts remaining nights to the folio, frees the
room, queues housekeeping). Refused while any folio has a balance:
collect payment or refund first. A corporate stay with credit moves
to the city ledger automatically, after the property's credit
control: over the credit limit or with overdue bills it either warns
(credit_warnings in the result) or is refused with CREDIT_BLOCKED and
the reason. An agent can never override a credit block - tell the
user; Finance or a Hotel Admin can override it at the desk. Confirm
with the user first.

Endpoint: `kamra.api.check_out`.
Mutating - logged to the activity ledger.

### `checkout_context(reservation)`

Read-only: what stands between a stay and check-out, without
changing anything. Balances per folio after the nights check-out would
still post, totals owed by the guest and owed back to the guest, a
held security deposit, what moves to the city ledger and its credit
check, open restaurant orders, each folio's invoice, and `blockers`
(every reason check_out would refuse). Use it before check_out to tell
the user what to settle; collecting or refunding money is done at the
desk.

Endpoint: `kamra.api.checkout_context`.

### `find_reservations(query, status, limit)`

Find reservations by guest name, room number, or reference  -
optionally filtered by status (Confirmed, Checked In, Checked Out,
Cancelled, No Show, Waitlisted). Resolve a room or name to a
reservation before acting.

Endpoint: `kamra.api.find_reservations`.

### `stay_detail(reservation)`

Full detail for one reservation: dates, room, guest + stay history,
folio balance (paid/due), booker, and which actions are available.

Endpoint: `kamra.api.reservation_detail`.

### `amend_stay_preview(reservation, check_in_date, check_out_date)`

What new dates would do to a stay's bill before anything changes:
current and new totals, the difference and the new nightly rates,
priced by the engine. Read-only. Call before amend_stay and tell the
guest / staff the new price.

Endpoint: `kamra.api.amend_stay_preview`.

### `amend_stay(reservation, check_in_date, check_out_date, confirm_price)`

Change a stay's dates (extend/shorten). An auto-priced stay is
re-quoted and its nightly rates re-locked; when the total changes the
call is refused unless confirm_price=1, so run amend_stay_preview
first and confirm the new price with staff. Re-checks room overlaps.

Endpoint: `kamra.api.amend_stay`.
Mutating - logged to the activity ledger.

### `move_room(reservation, new_room, confirm_price)`

Move a stay to a different room (pre-arrival or mid-stay). Overlap
guard re-runs; on a checked-in move the old room goes Dirty. A move to
another room type re-prices an auto-priced stay: check
room_move_preview and pass confirm_price=1 once the new price is
agreed. A same-type move keeps the confirmed rates.

Endpoint: `kamra.api.move_reservation`.
Mutating - logged to the activity ledger.

### `room_move_preview(reservation, new_room)`

What moving a stay to a room would do to the bill: same type keeps
the price; another type is re-quoted. Read-only.

Endpoint: `kamra.api.room_move_preview`.

### `set_late_arrival(reservation, late_arrival, eta)`

Flag a confirmed arrival as arriving late (late_arrival=1), with the
guest's ETA if known, or clear the flag (late_arrival=0). With the
property's late-arrival protection on, the night audit holds it as
Due In instead of marking a no-show.

Endpoint: `kamra.api.set_late_arrival`.
Mutating - logged to the activity ledger.

### `guest_lookup(search)`

Find guests by name or phone, with stay stats and lifetime value.

Endpoint: `kamra.api.guests_with_stats`.

### `guest_journey(guest)`

A guest's full history: profile, stats, chronological timeline.
Load this before talking to a returning guest.

Endpoint: `kamra.api.guest_journey`.

### `update_occupants(reservation, occupants)`

Record everyone staying in the room (the legal hotel register,
printed on the GRC). occupants = [{full_name, age, gender,
nationality, id_type, id_number, phone}] - replaces the list.

Endpoint: `kamra.api.update_occupants`.
Mutating - logged to the activity ledger.

### `rooms_board()`

Every room today: housekeeping status, occupancy, the in-house
guest, who arrives or leaves today, whether the room is held out of
service, and its open housekeeping task. Read-only.

Endpoint: `kamra.rooms.rooms_board`.

### `room_detail(room)`

One room right now: its type and features, housekeeping status,
the guest in it (with balance), the next arrival, active out-of-service
holds and open housekeeping tasks. room is the room id (see
rooms_board). Read-only.

Endpoint: `kamra.rooms.room_detail`.

### `room_availability(room, start_date, days)`

One room night by night (up to 31 days): booked (by whom), held out
of service, or free. Read-only.

Endpoint: `kamra.rooms.room_availability`.

### `room_history(room, limit)`

Who stayed in a room lately (nights, room revenue), who cleaned and
inspected it and when, its service tickets, and guests moved in or out
of it. Read-only.

Endpoint: `kamra.rooms.room_history`.

### `room_insights(days)`

Per-room numbers for the last 7, 30, 90, 180 or 365 nights: room
nights and occupancy, posted room revenue, out-of-service nights and
average cleaning time, with the most and least used rooms. Read-only.

Endpoint: `kamra.rooms.room_insights`.

## Ops

### `create_ticket(subject, category, priority, room, description)`

Log a guest request / issue as a tracked ticket. Categories:
Housekeeping, Room Service, Maintenance, Front Desk, Concierge,
Complaint, Other. Priority sets the SLA.

Endpoint: `kamra.api.create_ticket`.
Mutating - logged to the activity ledger.

### `list_tickets(show_closed)`

Open service tickets with SLA/overdue status.

Endpoint: `kamra.api.tickets_list`.

### `advance_ticket(ticket, status, resolution_note)`

Move a service ticket along: In Progress, Resolved, Closed, or
Cancelled. Pass a resolution_note when resolving.

Endpoint: `kamra.api.advance_ticket`.
Mutating - logged to the activity ledger.

## Housekeeping

### `hk_queue()`

Housekeeping phone view: prioritized task queue and room board.
Checkout cleans for rooms with an arrival today jump the queue.

Endpoint: `kamra.api.hk_queue`.

### `hk_update_task(task, status)`

Start or complete a housekeeping task. Status: In Progress, Done,
or Verified.

Endpoint: `kamra.api.hk_update_task`.
Mutating - logged to the activity ledger.

### `hk_assign_task(task, user)`

Supervisor hands a task to a specific housekeeper (awaits accept).

Endpoint: `kamra.api.hk_assign_task`.
Mutating - logged to the activity ledger.

### `hk_claim_task(task)`

Housekeeper takes an unassigned task from the pool for themselves.

Endpoint: `kamra.api.hk_claim_task`.
Mutating - logged to the activity ledger.

### `set_room_hk_status(room, status)`

Set a room's housekeeping status: Clean, Dirty, Inspected, Ready,
or Out of Order.

Endpoint: `kamra.api.set_housekeeping_status`.
Mutating - logged to the activity ledger.

### `hk_post_consumable(room, charge_type, description, amount)`

Housekeeping posts Minibar or Laundry found in a room onto the
in-house guest's folio. Other charge types are refused.

Endpoint: `kamra.api.hk_post_consumable`.
Mutating - logged to the activity ledger.

## Billing

### `get_folio(reservation)`

The guest's bill: charge lines, payments, GST, balance.

Endpoint: `kamra.api.get_folio`.

### `add_folio_charge(folio, charge_type, description, amount, gst_rate)`

Post a charge to an open folio (F&B, minibar, laundry, late
checkout…). Amount is pre-tax.

Endpoint: `kamra.api.add_folio_charge`.
Mutating - logged to the activity ledger.

### `post_stay_charge(reservation, charge_type, description, amount, gst_rate, is_alcohol)`

Post a charge to a stay and let the company billing rules pick the
folio - corporate room/meals go to the Company folio, alcohol and
unruled charges to the guest. Prefer this over add_folio_charge when
you don't know which folio should carry the line.

Endpoint: `kamra.api.post_stay_charge`.
Mutating - logged to the activity ledger.

### `split_folio_charge(from_folio, charge_row, to_folio, percent, amount)`

Split one charge line between two folios of the same stay - e.g.
a 70/30 corporate deal or a shared room. Give percent OR amount (the
part that moves to to_folio). Use get_folio first to find folio and
charge row names.

Endpoint: `kamra.api.split_folio_charge`.
Mutating - logged to the activity ledger.

### `stay_folios(reservation)`

All folios of a stay (guest / extra / company / group) with
balances - plus the group master when the stay is on a block.

Endpoint: `kamra.api.reservation_folios`.

### `record_payment(folio, mode, amount, reference, kind)`

Record money received on a folio. mode: Cash, UPI, Card, Bank,
Link. kind: Payment (default), Advance, or Security Deposit.
Confirm the amount with staff before calling.

Endpoint: `kamra.api.add_folio_payment`.
Mutating - logged to the activity ledger.

### `void_charge(folio, charge_row, reason)`

Remove a WRONG charge line from an open folio (duplicate, wrong
amount, wrong guest). Pass the folio and the charge line's id (`name`
from get_folio). For settled/invoiced bills use apply_allowance.

Endpoint: `kamra.api.void_folio_charge`.
Mutating - logged to the activity ledger.

### `apply_allowance(folio, amount, reason, gst_rate)`

Credit back part of a bill on an open folio without deleting the
original line (service recovery, dispute, agreed discount). Needs a
reason; it goes on the record.

Endpoint: `kamra.api.post_allowance`.
Mutating - logged to the activity ledger.

### `move_charges(from_folio, charge_rows, to_folio)`

Move charge lines to another folio of the same stay or group.
charge_rows is a list of charge line names from get_folio.

Endpoint: `kamra.api.transfer_folio_charges`.
Mutating - logged to the activity ledger.

### `close_folio(folio)`

Close / settle an open folio and issue the invoice number. Balance
must be zero (or use part-settle elsewhere). Confirm with staff  -
irreversible.

Endpoint: `kamra.api.close_folio`.
Mutating - logged to the activity ledger.

### `send_payment_link(folio)`

Create a Razorpay payment link for a folio's outstanding balance
(SMS/email to the guest when contact details exist).

Endpoint: `kamra.api.folio_payment_link`.
Mutating - logged to the activity ledger.

### `send_deposit_link(reservation, amount)`

Create a payment link for a booking's deposit before arrival - the
deposit still due (the property's deposit %) unless an amount is
given. When the guest pays, it posts to the folio as an Advance and
confirms a held booking. Returns the link and a ready-to-send message.

Endpoint: `kamra.api.deposit_payment_link`.
Mutating - logged to the activity ledger.

### `company_credit_status(company, amount)`

A company's credit position before billing it more: its credit
limit (0 = none), what it owes on the city ledger and on stays in
house, bills overdue past the grace period, and whether billing
`amount` more would be warned or blocked by the property's credit
control. Read-only. Bookings on company billing and check-outs run
the same check; an agent can't override a block.

Endpoint: `kamra.credit.company_credit_status`.

### `security_deposit_status(reservation)`

The stay's refundable security (damage) deposit: the property's
policy amount, what is held, withheld and refunded, and whether it is
still holding up check-out. Withholding and refunding are done by
staff at the desk (cashier PIN) - not by an agent.

Endpoint: `kamra.api.security_deposit`.

### `collect_security_deposit(reservation, amount, mode, reference)`

Record a refundable security deposit the guest has paid (villas:
the damage deposit). It is held on the guest folio as a liability,
not revenue, and refunded or withheld at check-out. mode: one of the
property's payment modes. Confirm the amount with staff first.

Endpoint: `kamra.api.collect_security_deposit`.
Mutating - logged to the activity ledger.

### `waive_security_deposit(reservation, reason)`

Waive the property's security deposit for one stay. A reason is
required and goes on the record; refused once money was taken.

Endpoint: `kamra.api.waive_security_deposit`.
Mutating - logged to the activity ledger.

## Revenue

### `set_room_rate(room_type, start_date, end_date, rate, reason)`

Set the nightly rate for a room type over a date range. Bounded by
the owner's rate guardrails - the PMS rejects rates outside the
floor/ceiling. Always give a reason (it goes in the audit trail).

Endpoint: `kamra.api.set_room_rate`.
Mutating - logged to the activity ledger.

## Briefings

### `owner_briefing(date)`

The owner's morning numbers: occupancy, yesterday's revenue/ADR/
RevPAR, arrivals/departures, open tickets, next-7-day availability,
agent hours saved. Turn this into a short, warm briefing - never
change the figures.

Endpoint: `kamra.api.owner_briefing`.

### `position_briefing(date)`

The hotel-position briefing for the GM and front desk: today's
occupancy against the overbooking ceiling, arrivals sorted by ETA,
departures with ETDs and balances due, back-to-back room conflicts
(incoming guest lands before the outgoing one leaves), the demand
tier pricing is applying, and a 7-day occupancy outlook. Read it out
as a crisp shift briefing - never change the figures.

Endpoint: `kamra.api.position_briefing`.

## Night audit

### `run_night_audit(business_date, acknowledge, note)`

Run the end-of-day for the property's current business date: post
the night's room charges for in-house guests at their confirmed
nightly rates, flag no-shows per the property's no-show policy, then
roll the business date forward. Call night_audit_precheck first: the
run is refused while a blocking check (open tills, open restaurant
bills, departures still in house) has items. Resolve them, or - only
when a staff member confirms and gives the reason - pass acknowledge
(the blocking check keys) and note (the reason); who acknowledged it
is recorded on the run. Late arrivals due on the closed date may be
held as Due In (held_late_arrivals); OTA no-shows may carry no fee
(no_show_fees_waived). Each run saves an audit pack (has_pack).
business_date is optional; if given it must equal the current
business date. A day that already closed returns already_ran.

Endpoint: `kamra.api.run_night_audit`.
Mutating - logged to the activity ledger.

### `night_audit_precheck()`

The night audit checklist for the current business date, read-only.
Checks: open_tills, open_pos_bills, departures_due (blocking by
default), arrivals_pending (with what the no-show policy will do),
rate_variance, pos_room_postings, high_balance, credit_limit and
room_status. Each has severity (block | warn | info), count, items
(reservation, folio, room, guest, amount, outlet / bill no) and a
suggested action. blockers lists the checks stopping a manual run;
can_run is true when there are none.

Endpoint: `kamra.night_audit.night_audit_precheck`.

## Groups

### `group_billing(group_booking)`

A group's whole billing picture: the consolidated company (master)
folio plus each member reservation's own folios with balances. Use
split_folio_charge to move value between a member's bill and the
master - company pays the stay, guests pay their extras.

Endpoint: `kamra.api.group_folios`.

### `create_group_block(group_name, check_in_date, check_out_date, blocks, company, cutoff_date, venue, event_type, event_date, attendees, customer_phone)`

Draft a MICE piece of business in one call: a group booking with a room
block (list of {room_type, rooms_blocked, block_rate}) and optionally its
banquet event. The agent wedge: turn "30 rooms + a 200-pax wedding on
Dec 12" into a live proposal. Starts Open; confirming it holds the rooms
out of general sale until the cutoff date.

Endpoint: `kamra.api.create_group_block`.
Mutating - logged to the activity ledger.

### `group_pickup_status(group_booking)`

Group Rooms Control: the block, per-room-type pickup (blocked / picked
up / remaining), rooming list, tied event and master folio.

Endpoint: `kamra.api.group_detail`.

### `pickup_group_room(group_booking, room_type, guest_name, phone, adults, children, idempotency_key)`

Name a guest into a group's room block - creates their reservation on
the group's dates against the held inventory.

Endpoint: `kamra.api.pickup_group_room`.
Mutating - logged to the activity ledger.

## Banquets

### `banquet_availability(event_date, end_date, start_time, end_time, pax)`

Which halls are free for a date, hours and pax. A confirmed function
takes the hall; a tentative hold is shown as a soft hold you can still
sell over. Two functions can share a hall morning and evening - only a
real overlap in hours counts as taken. Run this before every enquiry.

Endpoint: `kamra.banquet.venue_availability`.

### `banquet_catalogue()`

What the property sells at a function: menu packages priced per plate
(with their courses), and the service list - LED wall, projector, DJ,
podium, stage, decor, laptop, bar. Read this before quoting anything;
never invent a price.

Endpoint: `kamra.banquet.banquet_catalogue`.

### `banquet_enquiry(venue, event_date, customer_name, event_type, attendees, customer_phone, customer_email, company, end_date, session, start_time, end_time, source, requirements)`

Open a function sheet from an enquiry. The hall's rack rental goes on
as the first line and a follow-up is diarised, so the enquiry can't go
quiet. Halls sell by session: pass session (Morning / Afternoon /
Evening / Full Day) and the hours follow it, or session "Custom Hours"
with start_time and end_time. Check banquet_availability first.

Endpoint: `kamra.banquet.create_enquiry`.
Mutating - logged to the activity ledger.

### `banquet_sheet(function)`

One function in full: dates, pax (expected / guaranteed / actual),
every line item with its chargeable flag, the negotiation history,
payment terms, receipts, and what it still needs from somebody.

Endpoint: `kamra.banquet.function_sheet`.

### `banquet_add_menu(function, menu, qty, rate, chargeable)`

Put a menu package on a function. Left alone the quantity follows the
pax rule (guaranteed, or actual if more turned up) and the price is the
package's own plate price. chargeable=0 gives it away - it still prints
on the event order, it just leaves the quote.

Endpoint: `kamra.banquet.add_menu`.
Mutating - logged to the activity ledger.

### `banquet_add_service(function, service_item, qty, rate, chargeable)`

Put a service on a function - projector, LED wall, DJ, podium, stage,
decor, laptop, bar. The catalogue decides chargeable by default; pass
chargeable=0 to throw it in for this function.

Endpoint: `kamra.banquet.add_service`.
Mutating - logged to the activity ledger.

### `banquet_negotiate(function, discount_amount, venue_rental, note)`

Move the price: a headline discount on the whole quote, or the hall
rate on its own. Every move is snapshotted with what the quote was worth
before and after, so the fourth revision stays explainable. Confirm the
new total with the user before calling.

Endpoint: `kamra.banquet.negotiate`.
Mutating - logged to the activity ledger.

### `banquet_payment_terms(function, terms, note)`

Set the payment schedule: [{milestone, due_date, percent | amount}].
A term stated as a percentage follows the quote as it moves; one stated
as an amount is a number both sides agreed and stays put.

Endpoint: `kamra.banquet.set_payment_terms`.
Mutating - logged to the activity ledger.

### `banquet_record_receipt(function, amount, mode, kind, reference)`

Record money in against a function (Advance / Payment / Security
Deposit / Refund).

Endpoint: `kamra.banquet.record_receipt`.
Mutating - logged to the activity ledger.

### `banquet_status(function, status, reason)`

Move a function along: Enquiry → Tentative → Confirmed, or out as
Cancelled / Lost. Cancelling or losing needs a reason. Confirming takes
the hall and will refuse a clash with another confirmed function. A
confirmed function is completed with banquet_close_out, not here.

Endpoint: `kamra.banquet.set_status`.
Mutating - logged to the activity ledger.

### `banquet_link_group(function, group_booking)`

Tie a function to a group booking at the same property so its bill
rides the group's master folio when it is posted to the bill, or untie
it by leaving group_booking empty. Refused once the function is billed.

Endpoint: `kamra.banquet.link_group`.
Mutating - logged to the activity ledger.

### `banquet_quote(function, valid_days)`

Stamp a quotation - bumps the version, dates it, and returns the whole
document so it can be read back or emailed.

Endpoint: `kamra.banquet.generate_quote`.
Mutating - logged to the activity ledger.

### `banquet_event_order(function)`

Issue the banquet event order - the running sheet the banquet, kitchen
and AV teams work the day from, with the menus expanded into courses.
Only a confirmed function gets one.

Endpoint: `kamra.banquet.generate_beo`.
Mutating - logged to the activity ledger.

### `banquet_document(function, kind)`

Fetch a function's paper without re-issuing it. kind: quote, contract,
beo, pack_list, invoice. The pack list is what physically has to reach
the hall, complimentary items included.

Endpoint: `kamra.banquet.banquet_document`.

### `banquet_pipeline(from_date, to_date, months)`

The banquet sales picture, month by month and by status: what's
confirmed, what's still in play, what's outstanding, the conversion
rate, and why business went away. Dated on the event, not the enquiry.

Endpoint: `kamra.banquet.banquet_pipeline`.

### `banquet_reminders(days)`

Everything that needs chasing: follow-ups gone quiet, tentative holds
about to lapse, payments due, event orders missing before the date,
functions confirmed with nothing received.

Endpoint: `kamra.banquet.banquet_reminders`.

### `banquet_month(month)`

Every hall and every session across a whole month - the grid that
answers "do you have the 14th of December?" in one look. Halls are sold
by session (Morning / Afternoon / Evening), not by the hour, so a hall
can take a morning conference and an evening wedding on the same day.
month is YYYY-MM; omit for the current one.

Endpoint: `kamra.banquet.month_availability`.

### `banquet_close_out(function, damage_amount, damage_note, pax_actual, refund_deposit)`

Hand the hall back after the function. Records the covers actually
served, deducts any damage from the refundable deposit - a reason is
required, and you can't deduct more than is held - and returns the rest
as a real refund line. Closes the function.

Endpoint: `kamra.banquet.close_out`.
Mutating - logged to the activity ledger.

### `banquet_register(register, from_date, to_date)`

The banquet office's books for a period. register is one of:
functions (everything booked), quotations (what was quoted and whether
it landed), enquiries (what came in), receipts (the cash book, by
mode), sales (revenue rolled up by hall, event type, session and
source).

Endpoint: `kamra.banquet.banquet_register`.

### `banquet_menu_card(function)`

What will actually be served, course by course, with no prices on it
-  the sheet the customer signs off and the kitchen cooks from.

Endpoint: `kamra.banquet.menu_card`.

### `banquet_receipt_document(function, receipt)`

One receipt as a document the customer can keep, with the amount in
words and the running balance on the function.

Endpoint: `kamra.banquet.receipt_document`.

## F&B

### `pos_outlets()`

List F&B outlets (restaurant, bar, room service) for this property.

Endpoint: `kamra.pos.outlets`.

### `pos_menu(outlet)`

Menu items for an outlet (with courses, prices, allergens).

Endpoint: `kamra.pos.pos_menu`.

### `pos_table_map(outlet)`

Floor plan: tables with occupancy, open checks, and reservations.

Endpoint: `kamra.pos.table_map`.

### `pos_open_orders(outlet)`

Open POS checks at an outlet.

Endpoint: `kamra.pos.open_orders`.

### `pos_order_detail(order)`

One POS order: items, KOTs, totals, payment state.

Endpoint: `kamra.pos.order_detail`.

### `pos_create_order(outlet, items, table_no, room, reservation, guests, customer_name, customer_phone, order_type, notes)`

Open a POS check. items = [{item, qty, notes?}]. Optionally bind
table_no and/or a room/reservation for room charge.

Endpoint: `kamra.pos.create_order`.
Mutating - logged to the activity ledger.

### `pos_add_items(order, items)`

Add items to an open POS order. items = [{item, qty, notes?}].

Endpoint: `kamra.pos.add_items`.
Mutating - logged to the activity ledger.

### `pos_confirm_order(order)`

Confirm a draft order so it can be fired to the kitchen.

Endpoint: `kamra.pos.confirm_order`.
Mutating - logged to the activity ledger.

### `pos_fire_kot(order, course)`

Fire a kitchen order ticket (whole check or one course).

Endpoint: `kamra.pos.fire_kot`.
Mutating - logged to the activity ledger.

### `pos_send_order(outlet, items, table_no, room, reservation, guests, order_type, customer_name, customer_phone, delivery_address, allergy_note, notes)`

Open a new POS check and send it straight to the kitchen in one
step (create, confirm and fire the KOT). Use this for a normal order;
pos_create_order is for a check you will fire later. items = [{item,
qty, notes?}]. Optionally bind table_no and/or a room/reservation.

Endpoint: `kamra.pos.send_order`.
Mutating - logged to the activity ledger.

### `pos_send_round(order, items)`

Add another round to an open POS check and fire it to the kitchen in one step. items = [{item, qty, notes?}].

Endpoint: `kamra.pos.send_round`.
Mutating - logged to the activity ledger.

### `pos_kitchen_queue(outlet)`

KDS view: tickets waiting / cooking for the property (optional outlet).

Endpoint: `kamra.pos.kitchen_queue`.

### `pos_pay_order(order, mode)`

Settle a POS check. mode: Cash, UPI, Card, Room Charge, etc.
Confirm the total with staff before calling.

Endpoint: `kamra.pos.pay_order`.
Mutating - logged to the activity ledger.

### `pos_orders(outlet, date, to_date, q, state)`

Bills at an outlet for a day (default today) or a date range of up
to 31 days, newest first, each with its state: open (not sent to the
kitchen), sent, paid, room (posted to a room folio), nc, closed or
cancelled. Viewing today also lists bills still open from earlier
days. q searches bill/KOT number, table, room and customer.

Endpoint: `kamra.pos.orders_list`.

### `pos_cancel_order(order, reason)`

Cancel an open POS bill that has nothing sent to the kitchen yet,
with a reason (kept on the bill and in the activity log; the table is
freed). Refused once any item was fired: food the kitchen started is
voided by a supervisor at the till, never by an agent. Check with
pos_order_detail first (kitchen_lines must be 0).

Endpoint: `kamra.pos.cancel_order`.
Mutating - logged to the activity ledger.

### `pos_remove_item(order, item_row)`

Remove one line that has not been sent to the kitchen from an open
POS bill (row id from pos_order_detail). Lines the kitchen already has
are refused, and so is the last line (cancel the bill instead).

Endpoint: `kamra.pos.remove_item`.
Mutating - logged to the activity ledger.

### `pos_room_lookup(room, last_name)`

Find an in-house guest to charge: by room number and/or last name
(2+ letters). Only checked-in stays at this property; returns room,
guest name, reservation and departure date.

Endpoint: `kamra.pos_interface.pos_room_lookup`.

### `pos_post_room_charge(ticket_id, amount, description, room, reservation, charge_type, is_alcohol, outlet_name)`

Post an outlet ticket (bar, spa, restaurant on another POS) to an
in-house guest's bill. ticket_id is the POS check number and makes the
call safe to retry: the same ticket is never posted twice. The billing
rules pick the folio; alcohol (is_alcohol=true) always goes to the
guest's own folio. Confirm the amount with staff before calling.

Endpoint: `kamra.pos_interface.pos_post_room_charge`.
Mutating - logged to the activity ledger.

## Laundry

### `laundry_board()`

Laundry ops board: pickups, in-plant, ready, deliveries outstanding.

Endpoint: `kamra.laundry.laundry_board`.

### `laundry_rates()`

Rate card for laundry items and service types at this property.

Endpoint: `kamra.laundry.laundry_rates`.

### `laundry_collect(room, items, express, order, notes)`

Collect guest laundry. items = [{item_name, service_type, qty}].
Bills from the rate card; express=true for rush. Pass order to fill
a prior pickup request.

Endpoint: `kamra.laundry.collect_laundry`.
Mutating - logged to the activity ledger.

### `laundry_status(order, status)`

Advance a laundry bag: Collected → In Process → Ready (one step
at a time). Use laundry_deliver to finish.

Endpoint: `kamra.laundry.laundry_status`.
Mutating - logged to the activity ledger.

### `laundry_deliver(order, shortage_note)`

Mark laundry delivered to the guest/room; posts any final charges.

Endpoint: `kamra.laundry.deliver_laundry`.
Mutating - logged to the activity ledger.

## Onboarding

### `setup_property(payload)`

Onboard a whole property in one call - the migration assistant's
tool. Ask the hotel for their room list/rate card (any format), map
it into: {property:{property_name, city, gstin?, phone?},
room_types:[{code,name,base_price,adults?}], rooms:[{room_type_code,
numbers:[..]}], meal_plans:[{code,price_per_adult}]}. Confirm the
mapping with the user before calling.

Endpoint: `kamra.api.setup_property`.
Mutating - logged to the activity ledger.

### `import_bookings(bookings, property)`

Migrate existing reservations from another PMS/spreadsheet. Each:
{guest_name, phone?, room_type_code, check_in, check_out, adults?,
amount_after_tax?, channel?, status?}. Fixed amounts are preserved;
otherwise the pricing engine quotes. Returns per-row errors - report
them to the user rather than silently dropping rows.

Endpoint: `kamra.api.import_bookings`.
Mutating - logged to the activity ledger.
