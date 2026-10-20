# Rooms - every room, its status and its story

The Rooms screen is the big room board: every room as a tile, grouped by
floor, with what is happening in it today. Tap a room to change its
status, deal with the guest in it, see the next weeks, and see who stayed
and who cleaned it. **Insights** shows which rooms sell, earn and get
cleaned, and how fast.

Open it from **Front Desk → Rooms**, from **Housekeeping → Rooms**
(supervisors), or with **Open full view** on the Today room board. Front
Desk, Housekeeping Supervisor, Night Auditor, Revenue Manager, Finance and
Hotel Admin users can open it. Housekeeping attendants work from their task
list and the phone app instead.

## Read the board

Each tile shows:

- the **room number** (large) and the **room type**;
- its colour: green **Clean**, blue **Inspected**, amber **Dirty**, red
  **Out of service**, dark green when someone is staying in it;
- the guest's **surname** when it is occupied, or the arriving guest's;
- **Arr** when a guest with this room arrives today, **Dep** when the guest
  in it leaves today, and a lock when the room is held out of service.

Narrow the board with the search box (room number or guest name), the
**Floor** and **Room type** lists, and the chips: **Ready to sell**,
**Dirty**, **Occupied**, **Arriving today**, **Departing today**, **Out of
service** and **Open task**. Each chip shows how many rooms match. The
board refreshes itself every 30 seconds.

## Open a room

Tap a tile. The room opens in a panel on the same page, with these tabs.

### Status

- **Housekeeping status**: tap **Dirty**, **Clean**, **Inspected** or
  **Ready**. The same rules as everywhere else apply: a housekeeping
  supervisor or the front desk can pass a room; other roles see the status
  but cannot change it. Open housekeeping tasks for the room are listed
  under it.
- **Out of service**: tap **Take out of service**, pick why (**Out of order
  (repairs)**, **House use**, **Owner stay**, **VIP hold** or **Other
  reason**), the first night it is off sale and **Back on** (the first night
  it can be sold again), and add a note. The room leaves sale for those
  nights and shows on the Tape Chart and in **Room Blocks**. Out of order
  also marks the room **Out of Order** for housekeeping when the hold starts
  today. You cannot hold a room that is booked on those nights; move the
  guest first.
- **Back in service** releases the holds that are running now and, if the
  room was **Out of Order**, marks it **Dirty** so it is cleaned before
  anyone sleeps in it.

Taking a room out of service needs the Front Desk role (or Hotel Admin).

### Now

The guest in the room now (dates, nights, party, and the bill, paid amount
and balance) with **Check out**, **Folio and billing**, **Guest requests**,
**Move room** and **Registration card**. Below it, the next guest booked
into this room. When they arrive today and the room is free, **Check in**
opens the guided check-in. **Check out** opens the guided check-out. See
[Front desk](/front-desk).

### Guest requests

Shown while someone is staying. Lists the room's open requests with
**Start**, **Done** and **Cancel request**. Add one under **New request**:
what the guest needs, the team (Housekeeping, Room Service, Maintenance,
Front Desk, Concierge, Complaint, Other) and the priority. It is the same
ticket as in [Guest requests](/operations).

### Folio and billing

Shown while someone is staying. Each folio of the stay with its bill, paid
amount and balance, **Open full folio**, and the latest lines.

- **Post a charge**: pick the type, the amount before tax, what it is for
  and the tax rate. The hotel's billing rules pick the folio (a company may
  pay the room, the guest the bar), and food and drink take the hotel's
  food tax rate.
- **Take a payment**: pick the folio (when there is more than one), how the
  guest pays and the amount. Your till must be open and your cashier PIN
  unlocked, as on the folio screen. See [Billing](/billing).

### Availability

The next 14 or 30 nights for this room: **Booked** (and who), **Held**
(out of service) or **Free**, with the bookings in that period listed
under the strip.

### History

- **Who stayed here**: recent stays with dates, nights and room revenue
  (from the folio once nights are posted; until then the booked room
  amount, marked so), and who gave them the room.
- **Who cleaned it**: each housekeeping task, who cleaned it and when, who
  inspected it, and how long the clean took. **Status changes** lists every
  status change made by hand, with who and when.
- **Maintenance and service tickets** raised for the room.
- **Room moves**: guests moved into or out of this room, from or to which
  room, by whom and when.

### Details

The room type, category, bed, view, air conditioning, bathroom, capacity,
amenities and description, the room type's photos, the latest cleaning
photos, and the room's notes. Change these in **Settings** (room types and
rooms).

## See which rooms work hardest

Click **Insights** at the top of the screen, then **Last 30 days** or
**Last 90 days**. The numbers count nights up to last night.

- **Room nights sold** and occupancy. Occupancy counts only the nights a
  room could be sold: nights it was out of service are left out.
- **Room revenue (posted)**: room charges on folios in the period. Only
  roles that see money (Front Desk, Finance, Revenue Manager, Night
  Auditor, Hotel Admin) see revenue.
- **Nights out of service** across all rooms.
- **Average clean**: from the moment a housekeeper starts a clean on the
  phone to when they finish it. Cleans under a minute or left open for
  more than eight hours are not counted.
- **Most used rooms** and **Rarely sold rooms**: the top and bottom five.
- **Every room**: one row per room. Sort by nights, occupancy, revenue,
  nights out of service or average clean. Tap a room to open it.

The numbers are worked out on the server and kept for ten minutes.

## Good to know

- A room shows as occupied from check-in to check-out. A guest due today
  who already has this room assigned shows **Arr**; one without a room
  yet does not show on the board.
- Cleaning times come from the housekeeping phone app (**Start** then
  **Done**). Tasks closed from the desk without being started have no time.

## For developers

The screen reads `kamra.rooms.rooms_board`, `room_detail`,
`room_availability`, `room_history` and `room_insights`; all are read-only
and property-scoped. Changes go through the existing writers:
`kamra.api.set_housekeeping_status`, `create_room_block`,
`release_room_block`, `check_in`, `check_out`, `move_reservation`,
`create_ticket`, `advance_ticket`, `post_stay_charge` and
`add_folio_payment`. AI agents use the read-only `rooms_board`,
`room_detail`, `room_availability`, `room_history` and `room_insights`
tools. See [MCP tools](/mcp-tools) and the [API reference](/api-reference).
