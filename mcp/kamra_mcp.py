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


def api(method: str, **params):
    res = requests.post(
        f"{KAMRA_URL}/api/method/kamra.api.{method}",
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
