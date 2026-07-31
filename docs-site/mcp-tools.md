# MCP tool reference

The Kamra MCP server (`mcp/kamra_mcp.py`) exposes these tools. Every call
runs as the connected user — role permissions apply, prices come from the
pricing engine, and each action is recorded in the activity ledger.


### `front_desk_today()`

Today's snapshot: arrivals, departures, in-house guests, room board
and the hours-saved counter.


### `availability(start_date, days)`

Room availability and nightly rates per room type for the next N
days. start_date YYYY-MM-DD (default today).


### `quote(room_type, check_in_date, check_out_date, adults, children, meal_plan, voucher_code)`

Price a stay (deterministic: occupancy pricing, seasons, meal plan,
voucher, GST). Use before every booking.


### `booking_options()`

Room types, meal plans, rate plans and corporate accounts available
for booking at this property.


### `create_booking(guest_name, room_type, check_in_date, check_out_date, phone, adults, children, meal_plan, voucher_code)`

Create a reservation. Dedupes the guest by phone, auto-assigns a
free room, applies the voucher, prices via the engine.


### `add_to_waitlist(guest_name, room_type, check_in_date, check_out_date, phone, adults, children)`

Park a stay on the waitlist (no room) — for dates that are sold out or
restricted. Promote it later with promote_waitlist when a room frees.


### `waitlist_ready()`

Waitlisted stays that can NOW be booked — a room has freed up for their
dates. Each item includes the guest name and phone, so you can proactively
reach out. Poll this to catch openings the moment they appear — the wedge
for turning a sold-out 'no' into a booking.


### `promote_waitlist(reservation)`

Promote a waitlisted stay into a free room (Confirmed). Fails if no room
is free for its dates.


### `cancellation_preview(reservation)`

What cancelling would cost right now (policy window, fee basis,
estimated fee). ALWAYS read this to the guest before cancelling.


### `cancel_booking(reservation, reason, note, waive_fee)`

Cancel a confirmed booking. The property's cancellation policy
applies automatically — free outside the window, else the configured
fee posts to the folio. Returns a cancellation number — always give
it to the guest. Reasons: Guest request, Change of plans, Duplicate
booking, Payment failed, Weather / travel disruption, Booked
elsewhere, Other. Only waive the fee when a manager authorizes it;
the waiver is logged.


### `check_in(reservation, room)`

Check a guest in (opens their folio, marks the room occupied).


### `check_out(reservation)`

Check a guest out (posts remaining nights to the folio, frees the
room, queues housekeeping). Confirm with the user first.


### `guest_lookup(search)`

Find guests by name or phone, with stay stats and lifetime value.


### `guest_journey(guest)`

A guest's full history: profile, stats, chronological timeline.
Load this before talking to a returning guest.


### `create_ticket(subject, category, priority, room, description)`

Log a guest request / issue as a tracked ticket. Categories:
Housekeeping, Room Service, Maintenance, Front Desk, Concierge,
Complaint, Other. Priority sets the SLA.


### `list_tickets(show_closed)`

Open service tickets with SLA/overdue status.


### `get_folio(reservation)`

The guest's bill: charge lines, payments, GST, balance.


### `add_folio_charge(folio, charge_type, description, amount, gst_rate)`

Post a charge to an open folio (F&B, minibar, laundry, late
checkout…). Amount is pre-tax.


### `post_stay_charge(reservation, charge_type, description, amount, gst_rate, is_alcohol)`

Post a charge to a stay and let the company billing rules pick the
folio — corporate room/meals go to the Company folio, alcohol and
unruled charges to the guest. Prefer this over add_folio_charge when
you don't know which folio should carry the line.


### `group_billing(group_booking)`

A group's whole billing picture: the consolidated company (master)
folio plus each member reservation's own folios with balances. Use
split_folio_charge / transfer tools to move value between a member's
bill and the master — company pays the stay, guests pay their extras.


### `split_folio_charge(from_folio, charge_row, to_folio, percent, amount)`

Split one charge line between two folios of the same stay — e.g.
a 70/30 corporate deal or a shared room. Give percent OR amount (the
part that moves to to_folio). Use get_folio / reservation_folios to
find folio and charge row names first.


### `update_occupants(reservation, occupants)`

Record everyone staying in the room (the legal hotel register,
printed on the GRC). occupants = [{full_name, age, gender,
nationality, id_type, id_number, phone}] — replaces the list.


### `set_room_rate(room_type, start_date, end_date, rate, reason)`

Set the nightly rate for a room type over a date range. Bounded by
the owner's rate guardrails — the PMS rejects rates outside the
floor/ceiling. Always give a reason (it goes in the audit trail).


### `owner_briefing(date)`

The owner's morning numbers: occupancy, yesterday's revenue/ADR/
RevPAR, arrivals/departures, open tickets, next-7-day availability,
agent hours saved. Turn this into a short, warm briefing — never
change the figures.


### `position_briefing(date)`

The hotel-position briefing for the GM and front desk: today's
occupancy against the overbooking ceiling, arrivals sorted by ETA,
departures with ETDs and balances due, back-to-back room conflicts
(incoming guest lands before the outgoing one leaves), the demand
tier pricing is applying, and a 7-day occupancy outlook. Read it out
as a crisp shift briefing — never change the figures.


### `setup_property(payload)`

Onboard a whole property in one call — the migration assistant's
tool. Ask the hotel for their room list/rate card (any format), map
it into: {property:{property_name, city, gstin?, phone?},
room_types:[{code,name,base_price,adults?}], rooms:[{room_type_code,
numbers:[..]}], meal_plans:[{code,price_per_adult}]}. Confirm the
mapping with the user before calling.


### `import_bookings(bookings, property)`

Migrate existing reservations from another PMS/spreadsheet. Each:
{guest_name, phone?, room_type_code, check_in, check_out, adults?,
amount_after_tax?, channel?, status?}. Fixed amounts are preserved;
otherwise the pricing engine quotes. Returns per-row errors — report
them to the user rather than silently dropping rows.


### `send_payment_link(folio)`

Create a Razorpay payment link for a folio's outstanding balance
(SMS/email to the guest when contact details exist).


### `run_night_audit(business_date)`

Run the end-of-day: post the night's room charges for in-house
guests and flag no-shows. Idempotent per date.


### `create_group_block(group_name, check_in_date, check_out_date, blocks, company, cutoff_date, venue, event_type, event_date, attendees, customer_phone)`

Draft a MICE piece of business in one call: a group booking with a room
block (list of {room_type, rooms_blocked, block_rate}) and optionally its
banquet event. The agent wedge: turn "30 rooms + a 200-pax wedding on
Dec 12" into a live proposal. Starts Open; confirming it holds the rooms
out of general sale until the cutoff date.


### `group_pickup_status(group_booking)`

Group Rooms Control: the block, per-room-type pickup (blocked / picked
up / remaining), rooming list, tied event and master folio.


### `pickup_group_room(group_booking, room_type, guest_name, phone)`

Name a guest into a group's room block — creates their reservation on
the group's dates against the held inventory.



## Banquets
The function business: enquiry → quotation → contract → event order →
bill → close-out. Halls, sessions, menu packages, services and the whole
negotiation live in the PMS, so an agent on the phone quotes the
property's real prices — never its own guess.

### `banquet_availability(event_date, end_date, start_time, end_time, pax)`

Which halls are free for a date, hours and pax. A confirmed function
takes the hall; a tentative hold is shown as a soft hold you can still
sell over. Two functions can share a hall morning and evening — only a
real overlap in hours counts as taken. Run this before every enquiry.

### `banquet_catalogue()`

What the property sells at a function: menu packages priced per plate
(with their courses), and the service list — LED wall, projector, DJ,
podium, stage, decor, laptop, bar. Read this before quoting anything;
never invent a price.

### `banquet_enquiry(venue, event_date, customer_name, event_type, attendees, customer_phone, customer_email, company, end_date, start_time, end_time, source, requirements)`

Open a function sheet from an enquiry. The hall's rack rental goes on
as the first line and a follow-up is diarised, so the enquiry can't go
quiet. Check banquet_availability first.

### `banquet_sheet(function)`

One function in full: dates, pax (expected / guaranteed / actual),
every line item with its chargeable flag, the negotiation history,
payment terms, receipts, and what it still needs from somebody.

### `banquet_add_menu(function, menu, qty, rate, chargeable)`

Put a menu package on a function. Left alone the quantity follows the
pax rule (guaranteed, or actual if more turned up) and the price is the
package's own plate price. chargeable=0 gives it away — it still prints
on the event order, it just leaves the quote.

### `banquet_add_service(function, service_item, qty, rate, chargeable)`

Put a service on a function — projector, LED wall, DJ, podium, stage,
decor, laptop, bar. The catalogue decides chargeable by default; pass
chargeable=0 to throw it in for this function.

### `banquet_negotiate(function, discount_amount, venue_rental, note)`

Move the price: a headline discount on the whole quote, or the hall
rate on its own. Every move is snapshotted with what the quote was worth
before and after, so the fourth revision stays explainable. Confirm the
new total with the user before calling.

### `banquet_payment_terms(function, terms, note)`

Set the payment schedule: [{milestone, due_date, percent | amount}].
A term stated as a percentage follows the quote as it moves; one stated
as an amount is a number both sides agreed and stays put.

### `banquet_receipt(function, amount, mode, kind, reference)`

Record money in against a function (Advance / Payment / Security
Deposit / Refund).

### `banquet_status(function, status, reason)`

Move a function along: Enquiry → Tentative → Confirmed → Completed, or
out as Cancelled / Lost. Cancelling or losing needs a reason. Confirming
takes the hall and will refuse a clash with another confirmed function.

### `banquet_quote(function, valid_days)`

Stamp a quotation — bumps the version, dates it, and returns the whole
document so it can be read back or emailed.

### `banquet_event_order(function)`

Issue the banquet event order — the running sheet the banquet, kitchen
and AV teams work the day from, with the menus expanded into courses.
Only a confirmed function gets one.

### `banquet_document(function, kind)`

Fetch a function's paper without re-issuing it. kind: quote, contract,
beo, pack_list, invoice. The pack list is what physically has to reach
the hall, complimentary items included.

### `banquet_pipeline(from_date, to_date, months)`

The banquet sales picture, month by month and by status: what's
confirmed, what's still in play, what's outstanding, the conversion
rate, and why business went away. Dated on the event, not the enquiry.

### `banquet_reminders(days)`

Everything that needs chasing: follow-ups gone quiet, tentative holds
about to lapse, payments due, event orders missing before the date,
functions confirmed with nothing received.

### `banquet_month(month)`

Every hall and every session across a whole month — the grid that
answers "do you have the 14th of December?" in one look. Halls are sold
by session (Morning / Afternoon / Evening), not by the hour, so a hall
can take a morning conference and an evening wedding on the same day.
month is YYYY-MM; omit for the current one.

### `banquet_close_out(function, damage_amount, damage_note, pax_actual, refund_deposit)`

Hand the hall back after the function. Records the covers actually
served, deducts any damage from the refundable deposit — a reason is
required, and you can't deduct more than is held — and returns the rest
as a real refund line. Closes the function.

### `banquet_register(register, from_date, to_date)`

The banquet office's books for a period. register is one of:
functions (everything booked), quotations (what was quoted and whether
it landed), enquiries (what came in), receipts (the cash book, by
mode), sales (revenue rolled up by hall, event type, session and
source).

### `banquet_menu_card(function)`

What will actually be served, course by course, with no prices on it
— the sheet the customer signs off and the kitchen cooks from.

### `banquet_receipt(function, receipt)`

One receipt as a document the customer can keep, with the amount in
words and the running balance on the function.
