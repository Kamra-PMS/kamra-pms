# Front desk — arrivals, check-in and check-out

The Front Desk app is where the desk runs the day: who is arriving, who is
leaving, who is in which room, and the paperwork in between. Front Desk,
Night Auditor and Hotel Admin users see it. Making bookings is covered in
[Reservations](/reservations).

![The Today screen: counts for arrivals, departures, in-house, occupancy, revenue and open tasks; the arrivals and departures lists on the left; the room board by floor on the right](/img/front-desk/today.png)

## Before you start

1. **Set your check-in and check-out times.** **Settings → Stay policies →
   Check-in & check-out**. They print on the registration card and on the
   guest's online check-in page.
2. **Decide how self check-in links go out.** **Settings → Front Desk →
   Arrivals**. Leave **Send pre-check-in links automatically** off to copy
   each link by hand, or turn it on to send them every morning (see
   [Send the self check-in link](#send-the-self-check-in-link)).
3. **Open your till before you take money.** A walk-in that pays at the
   desk, or a deposit, goes through your cashier session: **Finance →
   Cashier → My Till**. See [Billing](/billing).

## Read the Today screen

**Front Desk → Today** is the home screen. It refreshes itself every 30
seconds.

- The six counts across the top: **Arrivals**, **Departures**,
  **In-house**, **Occupancy**, **Revenue** (with RevPAR) and **Open tasks**
  for housekeeping.
- **Arrivals** and **Departures** list today's stays. Each row shows the
  source (Website, Phone, OTA, AI Agent…), a payment chip (**Paid**,
  **₹… due** or **Unpaid**) and **Pre-checked-in** when the guest has filled
  in the online form. "via Priya (Assistant)" means someone booked on the
  guest's behalf; hover it for the booker's phone.
- **Room board** shows every room by floor. An occupied room is dark green;
  click it to open that guest's registration card. Click any other room to
  move its housekeeping status on one step: Dirty → Clean → Inspected → Out
  of Order → Dirty.
- **In-house guests** lists everyone staying, their balance and when they
  leave. Click a row for the registration card.

![The arrivals list: each guest with source and payment chips, the room, nights and party size, the GRC and copy check-in link shortcuts, and a Check in button](/img/front-desk/arrivals.png)

## Check a guest in

1. On **Today**, find the guest under **Arrivals** and click **Check in**.
2. Read the **Registration** chips: online check-in, **ID on file**,
   **Address proof**, **Phone** and **Email**. A green tick means it is
   there. Nothing here stops the check-in; it shows you what to collect.
   **Open GRC** opens the registration card in a new tab if you want to
   capture the ID first.
3. Pick the room. If the booking has a room, it shows as **Room 203 is
   assigned**. If not, Kamra suggests one with its reason (for example
   "First free room of the type"). Click the suggestion, or choose another
   free room of the same type under **Or pick another room**. Each room
   shows its housekeeping status.
4. Click **Check in to 205** (the button names the room).

![The check-in panel for Nikhil Rao: registration chips, the suggested room 202 and a list of other free rooms](/img/front-desk/checkin-sheet.png)

![Checking in an arrival from the Today screen: open the panel, pick room 205, check in, and the guest moves to the in-house list](/img/front-desk/checkin.gif)

The room turns occupied, the guest folio opens, and any deposit taken
before arrival moves onto the stay's bill.

If you pick a room that is still **Dirty**, Kamra warns you and lets you
go ahead; housekeeping sees the room flip to occupied.

You can also check in from the reservation itself: **Reservations** → click
the booking → **Check in**. That button only appears once the booking has
a room.

## Check in a walk-in

For a guest standing at the counter with no booking, use **Walk-in** in
the top bar. One screen books the stay, records the ID, checks the guest
into a room and takes the payment.

1. Click **Walk-in** (or switch **New booking** to **Walk-in**).
2. Type the **Guest name**. If the guest has stayed before, pick them from
   the list so the stay joins their profile. Add the **Phone**.
3. Choose the **ID type**, type the **ID number** and check the
   **Nationality**. The ID types come from your country pack.
4. Pick the **Room type**, then the **Room**. The list shows rooms free
   tonight, clean ones first.
5. Set **Nights** and the party size. For a few hours' stay, switch
   **Overnight** to **Day use** and set the time slot.
6. Under **Payment**, pick how the guest pays and the **Amount collected**.
   It starts at the full total; lower it for a part payment, or set it to 0
   to put everything on the bill.
7. Click **Check in & collect ₹2,940** (or **Check in** when nothing is
   collected).

![The walk-in screen filled in: guest, phone, Aadhaar ID, Standard room 105, one night, cash payment, and the live quote on the right](/img/front-desk/walkin.png)

![A walk-in from start to finish: the desk types the guest's name, phone and ID, picks the room, and checks the guest into room 105](/img/front-desk/walkin.gif)

It is all or nothing. If the room was just taken, or your till is closed,
nothing is saved and the screen tells you why. After it succeeds, **Open
bill** takes you to the guest's folio.

## Send the self check-in link

Guests can fill in their registration before they arrive: ID type and
number, a photo of the ID, address, arrival time, and a signature on the
registration card.

- **By hand:** on **Today**, click **copy check-in link** on the arrival
  row and paste it into your message to the guest. Hover the link first:
  it tells you whether to send it to the guest, the booker, or both. The
  link shows for confirmed arrivals that have not filled the form yet.
- **Automatically:** turn on **Settings → Front Desk → Arrivals → Send
  pre-check-in links automatically**. Each morning Kamra sends the link to
  guests arriving within **Send links this far ahead** (2 days by default).

![The guest's online check-in page on a phone: stay summary, ID type and number, ID photo, address proof, contact details, house rules and a signature box](/img/front-desk/precheckin.png)

When the guest submits the form, the arrival shows **Pre-checked-in**.
Before you hand over the key, compare the ID with the person: open the
booking (**Reservations** → click it) and click **Verify identity** in the
**Identity** card. After that, the guest can no longer change what they
sent.

## Complete the registration card

Every stay has a printable guest registration card (GRC). Open it from
**GRC** on an arrival row, from a room on the room board, from an
in-house guest, or with **Registration card** on the booking.

![The registration card for Priya Nair: guest and stay details on the printable card, and the registration checklist, documents and money on the right](/img/front-desk/grc.png)

1. Work down the **Registration checklist** on the right: **Guest ID on
   file**, **Address proof** (optional), **Occupants registered** and
   **Signature**.
2. Under **Documents**, click **Capture** next to **Guest ID** or
   **Address proof**. On a tablet or phone this opens the camera.
3. To correct the guest's nationality, click **edit** next to
   **Nationality**.
4. If the guest arrived or left at a different time than planned, click
   **edit** next to **Actual check-in** or **Actual check-out**.
5. Below the card, fill the **Occupant register**: one row per person in
   the room, with their own ID. Click **Add occupant** for more rows, then
   **Save register**. Once a row is saved, **Capture ID** on that row takes
   the occupant's ID. A child's row asks for name and age only, unless your
   country's register needs children's IDs too.
6. Click **Print GRC** and have the guest sign. A guest who signed online
   already has their signature on the card.

![The occupant register: full name, age, gender, nationality, ID type and number for each person, with Add occupant and Save register](/img/front-desk/grc-occupants.png)

The **Money** box shows charges, payments and the balance; **Open bill**
goes to the folio.

## Move a guest to another room

1. Open the move from any of these:
   - **Change room** on the registration card,
   - **Change room** (or **Assign room**) in the booking's **Room** card,
   - the guest's bar on the [tape chart](/reservations#move-a-stay-on-the-tape-chart).
2. Pick a room. **Same type** lists rooms of the booked type; **All types
   (upgrade)** shows every type. Free, clean rooms come first; booked rooms
   are greyed out.
3. Check the price line at the bottom. Moving to another type re-prices
   the stay, and Kamra shows the difference and the new total before
   anything changes.
4. Pick a reason (**Guest request**, **Upgrade**, **Maintenance**, **Noise
   / complaint**, **Other**), add a note if you like, and click **Move to
   303**.

![The Change room window with All types selected, room 303 picked, and the price line showing the Suite costs ₹10,395 more](/img/front-desk/change-room.png)

When the guest is already in-house, the old room is marked Dirty for
housekeeping. Every move is written to the activity log with its reason.

## Check a guest out

1. On **Today**, find the guest under **Departures**.
2. Click **Check out**.

![The departures list with a Check out button on each row](/img/front-desk/departures.png)

Before it checks the guest out, Kamra posts any nights the night audit
has not posted yet, then looks at the bill:

- If the guest still owes money, check-out stops and says how much.
  Collect it on the folio first ([Billing](/billing)).
- If the guest has paid too much, check-out stops until you refund it.
- If a company with credit pays for the stay, the company's share moves to
  the city ledger and the check-out goes ahead.

![The message shown when a guest still owes money at check-out](/img/front-desk/checkout-owed.png)

After check-out the room is marked Vacant and Dirty, and housekeeping gets
a high-priority checkout clean. The same **Check out** button is on the
booking's detail panel.

## Look up a guest

**Front Desk → Guests** lists every guest with their bookings, stays,
nights, lifetime value and last stay. Search by name or phone, and click a
guest to open their journey.

![The guests list with phone, bookings, stays, nights, lifetime value and last stay](/img/front-desk/guests.png)

The journey shows every stay and event, with:

- **Book a stay** to start a booking already attached to this guest,
- **Notes & preferences** and the **VIP** tick (VIP guests get a star on
  every screen),
- **Profile actions**: **Blacklist guest**, **Merge a duplicate**,
  **Anonymize profile** and **Export guest data**.

![A guest's journey: stay history, totals, notes and preferences, VIP, and profile actions](/img/front-desk/guest-journey.png)

## Settings

| Setting | Where | Default | What it does |
| --- | --- | --- | --- |
| Check-in time / Check-out time | Settings → Stay policies | 14:00 / 11:00 | Printed on the GRC and the online check-in page. |
| Send pre-check-in links automatically | Settings → Front Desk → Arrivals | Off | Sends the self check-in link to upcoming arrivals each morning. |
| Send links this far ahead | Settings → Front Desk → Arrivals | 2 days | How far ahead of arrival the automatic link goes out. |
| Require pre-check-in before access details | Settings → Front Desk → Arrivals | Off | Holds back the **Access instructions** (door codes, Wi-Fi) until the guest has checked in online. |
| Guest ID retention | Settings → Privacy & data | Verify & Discard | Verify & Discard masks ID numbers to the last 4 digits and deletes ID photos at check-out. Store keeps them. |
| Security deposit | Settings → Stay policies → Deposits | 0 | A refundable amount to hold during the stay. While it is held, the booking warns you before check-out. |

## Good to know

- Check-in never waits for an ID. The ID chips and warnings tell you what
  is missing; the register wants it before the night audit.
- A walk-in always arrives today. For a future date, make a normal
  booking.
- A booking needs a room before check-in. Whole-villa stays check in as
  one unit.
- The balance on **Today** includes nights the night audit has not posted
  yet, so it matches what the guest owes at check-out.
- A room whose guest is due out today but still checked in is not offered
  for a check-in or a walk-in until that guest checks out.
- **Blacklist guest** is for Hotel Admins. A reason is needed both to add
  and to lift it, and it goes to the activity log.

## Troubleshooting

**"Cannot check out: ₹… is still owed."** Open the bill (**Open bill** on
the GRC, or **Open folio** on the booking), take the payment, then check
out again. For a company that pays later, transfer the balance to the city
ledger on the folio.

**"Assign a room before check-in."** The booking has no room. Use **Assign
room** on the booking or the GRC, or check in from **Today**, where you pick
the room in the same step.

**"NO_OPEN_SESSION: open your till under Finance → Cashier first."** You
tried to take money (a walk-in payment or a deposit) without an open till.
Open it under **Finance → Cashier → My Till**, or set the walk-in's
**Amount collected** to 0.

**"Room … is still occupied by … Check them out first, or choose another
room."** The guest before is still checked in to that room. Check them out
on **Today** (under **Departures**), or pick another room.

**The check-in panel says "No free room of this type for these dates".**
Every room of the type is taken. Open the [tape chart](/reservations#move-a-stay-on-the-tape-chart)
to move another stay or upgrade this one.

## For developers

The check-in panel is `kamra.api.checkin_context` and `kamra.api.check_in`;
the walk-in is `kamra.api.walk_in`; check-out is `kamra.api.check_out`; room
moves use `kamra.api.movable_rooms`, `kamra.api.room_move_preview` and
`kamra.api.move_reservation`. AI agents use the `front_desk_today`,
`check_in`, `check_out`, `move_room`, `guest_lookup`, `guest_journey` and
`update_occupants` tools. See [MCP tools](/mcp-tools) and the
[API reference](/api-reference).
