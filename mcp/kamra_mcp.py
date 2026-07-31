"""Kamra MCP server — connect Claude (or any MCP client) to your hotel.

Every tool wraps a governed Kamra API endpoint. The server authenticates
as a dedicated agent user (scoped role, full audit trail), so the AI can
never do more than the hotel allowed it to.

Setup:
    uv add "mcp[cli]" requests      # or: pip install "mcp[cli]" requests

Env:
    KAMRA_URL         e.g. http://kamra.localhost:8000
    KAMRA_API_KEY     from kamra.scripts.seed_rbac_v2
    KAMRA_API_SECRET  from kamra.scripts.seed_rbac_v2
    KAMRA_PROPERTY    default property name

Connect Claude Code:
    claude mcp add kamra -e KAMRA_URL=... -e KAMRA_API_KEY=... \
        -e KAMRA_API_SECRET=... -e KAMRA_PROPERTY=... \
        -- uv run /path/to/kamra_mcp.py
"""

import os

import requests
from mcp.server.fastmcp import FastMCP

KAMRA_URL = os.environ.get("KAMRA_URL", "http://kamra.localhost:8000")
API_KEY = os.environ["KAMRA_API_KEY"]
API_SECRET = os.environ["KAMRA_API_SECRET"]
PROPERTY = os.environ.get("KAMRA_PROPERTY", "Kamra Demo Palace")

mcp = FastMCP(
    "kamra",
    instructions=(
        "You are operating a hotel through Kamra PMS. Money and "
        "availability are computed by the PMS, never estimate them "
        "yourself — always quote before booking. Confirm irreversible "
        "actions (checkout, closing a folio) with the user first."
    ),
)


def call(dotted: str, **params):
    """POST to any whitelisted Kamra endpoint, e.g. "api.get_quote" or
    "banquet.create_enquiry"."""
    res = requests.post(
        f"{KAMRA_URL}/api/method/kamra.{dotted}",
        json=params,
        headers={"Authorization": f"token {API_KEY}:{API_SECRET}"},
        timeout=30,
    )
    if not res.ok:
        try:
            import json as _json

            msgs = _json.loads(res.json().get("_server_messages", "[]"))
            if msgs:
                raise RuntimeError(_json.loads(msgs[0]).get("message", res.text))
        except (ValueError, KeyError):
            pass
        res.raise_for_status()
    return res.json()["message"]


def api(method: str, **params):
    """The front-desk surface - kamra.api.*"""
    return call(f"api.{method}", **params)


def banquet(method: str, **params):
    """The function business - kamra.banquet.*"""
    return call(f"banquet.{method}", **params)


@mcp.tool()
def front_desk_today() -> dict:
    """Today's snapshot: arrivals, departures, in-house guests, room board
    and the hours-saved counter."""
    return api("front_desk_snapshot", property=PROPERTY)


@mcp.tool()
def availability(start_date: str = "", days: int = 14) -> dict:
    """Room availability and nightly rates per room type for the next N
    days. start_date YYYY-MM-DD (default today)."""
    return api("availability_calendar", property=PROPERTY,
               start_date=start_date or None, days=days)


@mcp.tool()
def quote(room_type: str, check_in_date: str, check_out_date: str,
          adults: int = 2, children: int = 0, meal_plan: str = "",
          voucher_code: str = "") -> dict:
    """Price a stay (deterministic: occupancy pricing, seasons, meal plan,
    voucher, GST). Use before every booking."""
    return api("get_quote", property=PROPERTY, room_type=room_type,
               check_in_date=check_in_date, check_out_date=check_out_date,
               adults=adults, children=children,
               meal_plan=meal_plan or None, voucher_code=voucher_code or None)


@mcp.tool()
def booking_options() -> dict:
    """Room types, meal plans, rate plans and corporate accounts available
    for booking at this property."""
    return api("booking_options", property=PROPERTY)


@mcp.tool()
def create_booking(guest_name: str, room_type: str, check_in_date: str,
                   check_out_date: str, phone: str = "", adults: int = 2,
                   children: int = 0, meal_plan: str = "",
                   voucher_code: str = "") -> dict:
    """Create a reservation. Dedupes the guest by phone, auto-assigns a
    free room, applies the voucher, prices via the engine."""
    return api("create_booking", property=PROPERTY, guest_name=guest_name,
               phone=phone or None, room_type=room_type,
               check_in_date=check_in_date, check_out_date=check_out_date,
               adults=adults, children=children,
               meal_plan=meal_plan or None,
               voucher_code=voucher_code or None, source="AI Agent")


@mcp.tool()
def add_to_waitlist(guest_name: str, room_type: str, check_in_date: str,
                    check_out_date: str, phone: str = "", adults: int = 2,
                    children: int = 0) -> dict:
    """Park a stay on the waitlist (no room) — for dates that are sold out or
    restricted. Promote it later with promote_waitlist when a room frees."""
    return api("create_booking", property=PROPERTY, guest_name=guest_name,
               phone=phone or None, room_type=room_type,
               check_in_date=check_in_date, check_out_date=check_out_date,
               adults=adults, children=children, waitlist=1, source="AI Agent")


@mcp.tool()
def waitlist_ready() -> list:
    """Waitlisted stays that can NOW be booked — a room has freed up for their
    dates. Each item includes the guest name and phone, so you can proactively
    reach out. Poll this to catch openings the moment they appear — the wedge
    for turning a sold-out 'no' into a booking."""
    return api("waitlist_ready", property=PROPERTY)


@mcp.tool()
def promote_waitlist(reservation: str) -> dict:
    """Promote a waitlisted stay into a free room (Confirmed). Fails if no room
    is free for its dates."""
    return api("promote_waitlist", reservation=reservation)


@mcp.tool()
def cancellation_preview(reservation: str) -> dict:
    """What cancelling would cost right now (policy window, fee basis,
    estimated fee). ALWAYS read this to the guest before cancelling."""
    return api("cancellation_preview", reservation=reservation)


@mcp.tool()
def cancel_booking(reservation: str, reason: str = "Guest request",
                   note: str = "", waive_fee: bool = False) -> dict:
    """Cancel a confirmed booking. The property's cancellation policy
    applies automatically — free outside the window, else the configured
    fee posts to the folio. Returns a cancellation number — always give
    it to the guest. Reasons: Guest request, Change of plans, Duplicate
    booking, Payment failed, Weather / travel disruption, Booked
    elsewhere, Other. Only waive the fee when a manager authorizes it;
    the waiver is logged."""
    return api("cancel_reservation", reservation=reservation,
               reason=reason, note=note, waive_fee=1 if waive_fee else 0)


@mcp.tool()
def check_in(reservation: str, room: str = "") -> dict:
    """Check a guest in (opens their folio, marks the room occupied)."""
    return api("check_in", reservation=reservation, room=room or None)


@mcp.tool()
def check_out(reservation: str) -> dict:
    """Check a guest out (posts remaining nights to the folio, frees the
    room, queues housekeeping). Confirm with the user first."""
    return api("check_out", reservation=reservation)


@mcp.tool()
def guest_lookup(search: str) -> list:
    """Find guests by name or phone, with stay stats and lifetime value."""
    return api("guests_with_stats", search=search)


@mcp.tool()
def guest_journey(guest: str) -> dict:
    """A guest's full history: profile, stats, chronological timeline.
    Load this before talking to a returning guest."""
    return api("guest_journey", guest=guest)


@mcp.tool()
def create_ticket(subject: str, category: str, priority: str = "Medium",
                  room: str = "", description: str = "") -> dict:
    """Log a guest request / issue as a tracked ticket. Categories:
    Housekeeping, Room Service, Maintenance, Front Desk, Concierge,
    Complaint, Other. Priority sets the SLA."""
    return api("create_ticket", property=PROPERTY, subject=subject,
               category=category, priority=priority, room=room or None,
               description=description or None, source="AI Agent")


@mcp.tool()
def list_tickets(show_closed: bool = False) -> list:
    """Open service tickets with SLA/overdue status."""
    return api("tickets_list", property=PROPERTY,
               show_closed=1 if show_closed else 0)


@mcp.tool()
def get_folio(reservation: str) -> dict | None:
    """The guest's bill: charge lines, payments, GST, balance."""
    return api("get_folio", reservation=reservation)


@mcp.tool()
def add_folio_charge(folio: str, charge_type: str, description: str,
                     amount: float, gst_rate: float = 5) -> dict:
    """Post a charge to an open folio (F&B, minibar, laundry, late
    checkout…). Amount is pre-tax."""
    return api("add_folio_charge", folio=folio, charge_type=charge_type,
               description=description, amount=amount, gst_rate=gst_rate)


@mcp.tool()
def post_stay_charge(reservation: str, charge_type: str, description: str,
                     amount: float, gst_rate: float = 5,
                     is_alcohol: bool = False) -> dict:
    """Post a charge to a stay and let the company billing rules pick the
    folio — corporate room/meals go to the Company folio, alcohol and
    unruled charges to the guest. Prefer this over add_folio_charge when
    you don't know which folio should carry the line."""
    return api("post_stay_charge", reservation=reservation,
               charge_type=charge_type, description=description,
               amount=amount, gst_rate=gst_rate,
               is_alcohol=1 if is_alcohol else 0)


@mcp.tool()
def group_billing(group_booking: str) -> dict:
    """A group's whole billing picture: the consolidated company (master)
    folio plus each member reservation's own folios with balances. Use
    split_folio_charge / transfer tools to move value between a member's
    bill and the master — company pays the stay, guests pay their extras."""
    return api("group_folios", group_booking=group_booking)


@mcp.tool()
def split_folio_charge(from_folio: str, charge_row: str, to_folio: str,
                       percent: float = 0, amount: float = 0) -> dict:
    """Split one charge line between two folios of the same stay — e.g.
    a 70/30 corporate deal or a shared room. Give percent OR amount (the
    part that moves to to_folio). Use get_folio / reservation_folios to
    find folio and charge row names first."""
    return api("split_folio_charge", from_folio=from_folio,
               charge_row=charge_row, to_folio=to_folio,
               percent=percent or None, amount=amount or None)


@mcp.tool()
def update_occupants(reservation: str, occupants: list) -> dict:
    """Record everyone staying in the room (the legal hotel register,
    printed on the GRC). occupants = [{full_name, age, gender,
    nationality, id_type, id_number, phone}] — replaces the list."""
    return api("update_occupants", reservation=reservation,
               occupants=occupants)


@mcp.tool()
def set_room_rate(room_type: str, start_date: str, end_date: str,
                  rate: float, reason: str = "") -> dict:
    """Set the nightly rate for a room type over a date range. Bounded by
    the owner's rate guardrails — the PMS rejects rates outside the
    floor/ceiling. Always give a reason (it goes in the audit trail)."""
    return api("set_room_rate", property=PROPERTY, room_type=room_type,
               start_date=start_date, end_date=end_date, rate=rate,
               reason=reason)


@mcp.tool()
def owner_briefing(date: str = "") -> dict:
    """The owner's morning numbers: occupancy, yesterday's revenue/ADR/
    RevPAR, arrivals/departures, open tickets, next-7-day availability,
    agent hours saved. Turn this into a short, warm briefing — never
    change the figures."""
    return api("owner_briefing", property=PROPERTY, date=date or None)


@mcp.tool()
def position_briefing(date: str = "") -> dict:
    """The hotel-position briefing for the GM and front desk: today's
    occupancy against the overbooking ceiling, arrivals sorted by ETA,
    departures with ETDs and balances due, back-to-back room conflicts
    (incoming guest lands before the outgoing one leaves), the demand
    tier pricing is applying, and a 7-day occupancy outlook. Read it out
    as a crisp shift briefing — never change the figures."""
    return api("position_briefing", property=PROPERTY, date=date or None)


@mcp.tool()
def setup_property(payload: dict) -> dict:
    """Onboard a whole property in one call — the migration assistant's
    tool. Ask the hotel for their room list/rate card (any format), map
    it into: {property:{property_name, city, gstin?, phone?},
    room_types:[{code,name,base_price,adults?}], rooms:[{room_type_code,
    numbers:[..]}], meal_plans:[{code,price_per_adult}]}. Confirm the
    mapping with the user before calling."""
    return api("setup_property", payload=payload)


@mcp.tool()
def import_bookings(bookings: list, property: str = "") -> dict:
    """Migrate existing reservations from another PMS/spreadsheet. Each:
    {guest_name, phone?, room_type_code, check_in, check_out, adults?,
    amount_after_tax?, channel?, status?}. Fixed amounts are preserved;
    otherwise the pricing engine quotes. Returns per-row errors — report
    them to the user rather than silently dropping rows."""
    return api("import_bookings", property=property or PROPERTY,
               bookings=bookings)


@mcp.tool()
def send_payment_link(folio: str) -> dict:
    """Create a Razorpay payment link for a folio's outstanding balance
    (SMS/email to the guest when contact details exist)."""
    return api("folio_payment_link", folio=folio)


@mcp.tool()
def run_night_audit(business_date: str = "") -> dict:
    """Run the end-of-day: post the night's room charges for in-house
    guests and flag no-shows. Idempotent per date."""
    return api("run_night_audit", property=PROPERTY,
               business_date=business_date or None)


if __name__ == "__main__":
    mcp.run()


@mcp.tool()
def create_group_block(group_name: str, check_in_date: str, check_out_date: str,
                       blocks: list, company: str = None,
                       cutoff_date: str = None, venue: str = None,
                       event_type: str = None, event_date: str = None,
                       attendees: int = 0, customer_phone: str = None) -> dict:
    """Draft a MICE piece of business in one call: a group booking with a room
    block (list of {room_type, rooms_blocked, block_rate}) and optionally its
    banquet event. The agent wedge: turn "30 rooms + a 200-pax wedding on
    Dec 12" into a live proposal. Starts Open; confirming it holds the rooms
    out of general sale until the cutoff date."""
    return api("create_group_block", property=PROPERTY, group_name=group_name,
               check_in_date=check_in_date, check_out_date=check_out_date,
               blocks=blocks, company=company, cutoff_date=cutoff_date,
               venue=venue, event_type=event_type, event_date=event_date,
               attendees=attendees, customer_phone=customer_phone)


@mcp.tool()
def group_pickup_status(group_booking: str) -> dict:
    """Group Rooms Control: the block, per-room-type pickup (blocked / picked
    up / remaining), rooming list, tied event and master folio."""
    return api("group_detail", group_booking=group_booking)


@mcp.tool()
def pickup_group_room(group_booking: str, room_type: str, guest_name: str,
                      phone: str = None) -> dict:
    """Name a guest into a group's room block — creates their reservation on
    the group's dates against the held inventory."""
    return api("pickup_group_room", group_booking=group_booking,
               room_type=room_type, guest_name=guest_name, phone=phone)


# ── banquets: the function business ──────────────────────────────────────
# Enquiry to event order. The wedge here is speed on the phone: by the time
# the caller has finished describing the wedding, the hall is checked, the
# sheet exists and the menu is priced.


@mcp.tool()
def banquet_availability(event_date: str, end_date: str = None,
                         start_time: str = None, end_time: str = None,
                         pax: int = 0) -> dict:
    """Which halls are free for a date, hours and pax. A confirmed function
    takes the hall; a tentative hold is shown as a soft hold you can still
    sell over. Two functions can share a hall morning and evening — only a
    real overlap in hours counts as taken. Run this before every enquiry."""
    return banquet("venue_availability", property=PROPERTY,
                   event_date=event_date, end_date=end_date,
                   start_time=start_time, end_time=end_time, pax=pax)


@mcp.tool()
def banquet_catalogue() -> dict:
    """What the property sells at a function: menu packages priced per plate
    (with their courses), and the service list — LED wall, projector, DJ,
    podium, stage, decor, laptop, bar. Read this before quoting anything;
    never invent a price."""
    return banquet("banquet_catalogue", property=PROPERTY)


@mcp.tool()
def banquet_enquiry(venue: str, event_date: str, customer_name: str,
                    event_type: str = "Wedding", attendees: int = 0,
                    customer_phone: str = None, customer_email: str = None,
                    company: str = None, end_date: str = None,
                    start_time: str = None, end_time: str = None,
                    source: str = "Phone", requirements: str = None) -> dict:
    """Open a function sheet from an enquiry. The hall's rack rental goes on
    as the first line and a follow-up is diarised, so the enquiry can't go
    quiet. Check banquet_availability first."""
    return banquet("create_enquiry", property=PROPERTY, venue=venue,
                   event_date=event_date, customer_name=customer_name,
                   event_type=event_type, attendees=attendees,
                   customer_phone=customer_phone, customer_email=customer_email,
                   company=company, end_date=end_date, start_time=start_time,
                   end_time=end_time, source=source, requirements=requirements)


@mcp.tool()
def banquet_sheet(function: str) -> dict:
    """One function in full: dates, pax (expected / guaranteed / actual),
    every line item with its chargeable flag, the negotiation history,
    payment terms, receipts, and what it still needs from somebody."""
    return banquet("function_sheet", function=function)


@mcp.tool()
def banquet_add_menu(function: str, menu: str, qty: float = 0,
                     rate: float = None, chargeable: int = 1) -> dict:
    """Put a menu package on a function. Left alone the quantity follows the
    pax rule (guaranteed, or actual if more turned up) and the price is the
    package's own plate price. chargeable=0 gives it away — it still prints
    on the event order, it just leaves the quote."""
    return banquet("add_menu", function=function, menu=menu, qty=qty or None,
                   rate=rate, chargeable=chargeable)


@mcp.tool()
def banquet_add_service(function: str, service_item: str, qty: float = 0,
                        rate: float = None, chargeable: int = None) -> dict:
    """Put a service on a function — projector, LED wall, DJ, podium, stage,
    decor, laptop, bar. The catalogue decides chargeable by default; pass
    chargeable=0 to throw it in for this function."""
    return banquet("add_service", function=function, service_item=service_item,
                   qty=qty or None, rate=rate, chargeable=chargeable)


@mcp.tool()
def banquet_negotiate(function: str, discount_amount: float = None,
                      venue_rental: float = None, note: str = None) -> dict:
    """Move the price: a headline discount on the whole quote, or the hall
    rate on its own. Every move is snapshotted with what the quote was worth
    before and after, so the fourth revision stays explainable. Confirm the
    new total with the user before calling."""
    return banquet("negotiate", function=function,
                   discount_amount=discount_amount, venue_rental=venue_rental,
                   note=note)


@mcp.tool()
def banquet_payment_terms(function: str, terms: list = None,
                          note: str = None) -> dict:
    """Set the payment schedule: [{milestone, due_date, percent | amount}].
    A term stated as a percentage follows the quote as it moves; one stated
    as an amount is a number both sides agreed and stays put."""
    return banquet("set_payment_terms", function=function, terms=terms or [],
                   note=note)


@mcp.tool()
def banquet_receipt(function: str, amount: float, mode: str = "Bank Transfer",
                    kind: str = "Advance", reference: str = None) -> dict:
    """Record money in against a function (Advance / Payment / Security
    Deposit / Refund)."""
    return banquet("record_receipt", function=function, amount=amount,
                   mode=mode, kind=kind, reference=reference)


@mcp.tool()
def banquet_status(function: str, status: str, reason: str = None) -> dict:
    """Move a function along: Enquiry → Tentative → Confirmed → Completed, or
    out as Cancelled / Lost. Cancelling or losing needs a reason. Confirming
    takes the hall and will refuse a clash with another confirmed function."""
    return banquet("set_status", function=function, status=status,
                   reason=reason)


@mcp.tool()
def banquet_quote(function: str, valid_days: int = 15) -> dict:
    """Stamp a quotation — bumps the version, dates it, and returns the whole
    document so it can be read back or emailed."""
    return banquet("generate_quote", function=function, valid_days=valid_days)


@mcp.tool()
def banquet_event_order(function: str) -> dict:
    """Issue the banquet event order — the running sheet the banquet, kitchen
    and AV teams work the day from, with the menus expanded into courses.
    Only a confirmed function gets one."""
    return banquet("generate_beo", function=function)


@mcp.tool()
def banquet_document(function: str, kind: str = "quote") -> dict:
    """Fetch a function's paper without re-issuing it. kind: quote, contract,
    beo, pack_list, invoice. The pack list is what physically has to reach
    the hall, complimentary items included."""
    return banquet("banquet_document", function=function, kind=kind)


@mcp.tool()
def banquet_pipeline(from_date: str = None, to_date: str = None,
                     months: int = 6) -> dict:
    """The banquet sales picture, month by month and by status: what's
    confirmed, what's still in play, what's outstanding, the conversion
    rate, and why business went away. Dated on the event, not the enquiry."""
    return banquet("banquet_pipeline", property=PROPERTY, from_date=from_date,
                   to_date=to_date, months=months)


@mcp.tool()
def banquet_reminders(days: int = 30) -> dict:
    """Everything that needs chasing: follow-ups gone quiet, tentative holds
    about to lapse, payments due, event orders missing before the date,
    functions confirmed with nothing received."""
    return banquet("banquet_reminders", property=PROPERTY, days=days)


@mcp.tool()
def banquet_month(month: str = None) -> dict:
    """Every hall and every session across a whole month — the grid that
    answers "do you have the 14th of December?" in one look. Halls are sold
    by session (Morning / Afternoon / Evening), not by the hour, so a hall
    can take a morning conference and an evening wedding on the same day.
    month is YYYY-MM; omit for the current one."""
    return banquet("month_availability", property=PROPERTY, month=month)


@mcp.tool()
def banquet_close_out(function: str, damage_amount: float = 0,
                      damage_note: str = None, pax_actual: int = None,
                      refund_deposit: int = 1) -> dict:
    """Hand the hall back after the function. Records the covers actually
    served, deducts any damage from the refundable deposit — a reason is
    required, and you can't deduct more than is held — and returns the rest
    as a real refund line. Closes the function."""
    return banquet("close_out", function=function,
                   damage_amount=damage_amount, damage_note=damage_note,
                   pax_actual=pax_actual, refund_deposit=refund_deposit)


@mcp.tool()
def banquet_register(register: str = "functions", from_date: str = None,
                     to_date: str = None) -> dict:
    """The banquet office's books for a period. register is one of:
    functions (everything booked), quotations (what was quoted and whether
    it landed), enquiries (what came in), receipts (the cash book, by
    mode), sales (revenue rolled up by hall, event type, session and
    source)."""
    return banquet("banquet_register", property=PROPERTY, register=register,
                   from_date=from_date, to_date=to_date)


@mcp.tool()
def banquet_menu_card(function: str) -> dict:
    """What will actually be served, course by course, with no prices on it
    — the sheet the customer signs off and the kitchen cooks from."""
    return banquet("menu_card", function=function)


@mcp.tool()
def banquet_receipt(function: str, receipt: str) -> dict:
    """One receipt as a document the customer can keep, with the amount in
    words and the running balance on the function."""
    return banquet("receipt_document", function=function, receipt=receipt)
