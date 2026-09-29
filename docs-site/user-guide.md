# Kamra front-desk guide

The working manual for a day at the desk. Everything here assumes you're
signed in at your hotel's Kamra URL; your role decides which sections of
the sidebar you see.

## The day at a glance — Today

**Today** is home: arrivals, departures, in-house guests and the room
board, refreshed every 30 seconds.

- Every stay row carries a **payment chip** — `Paid`, `₹X due`, or
  `Unpaid` — straight from the folio.
- Arrival rows link to the **GRC** (registration card) and a
  **copy check-in link** button. Hover it: it tells you whether the link
  should go to the guest or the booker.
- "via Priya (Assistant)" on a row means the stay was booked on
  someone's behalf — hover for the booker's phone.

## Booking

**New booking** (top right, anywhere):

1. Type the guest's name — returning guests appear as you type; picking
   one attaches the stay to their profile ("Returning guest · 4 stays").
2. Pick room type, dates, occupancy, meal plan. The **quote updates live**
   and states the cancellation policy and any deposit expected. Check-in
   cannot be before today (unless recording a past stay via import or an
   explicit catch-up flag).
3. **Add another room** turns the booking into a group — one confirm
   books every room under one group reference.
4. Optional: company (bills corporate — see billing rules), travel
   agent, add-ons (posted to the folio at check-in), voucher, and
   "Booked on someone's behalf" (who arranged it + who receives links).

**Tape chart vs Calendar:** the Calendar sells (availability and rates
by room *type* — click a cell to book); the tape chart operates (who is
in which physical room — click a bar to move rooms or amend dates,
both re-priced and overlap-checked).

## Check-in

**Check in** on the arrival row opens the check-in flow:

1. **Registration at a glance** — chips show whether the guest
   pre-checked-in online, whether ID and address proof are on file,
   phone and email, and a VIP flag. Nothing blocks check-in, but you
   see what's missing. **Open GRC** is one click for capture or print.
2. **The room** — if none is assigned, the allocator suggests one with
   its reason ("VIP → high floor", preference matches). Take it, or
   pick from every free room of the type; housekeeping state shows on
   each, with a warning before handing over an uncleaned room.
3. Confirm — the room is assigned and the guest is in.

**On the GRC**: record the **occupants** (everyone in the room — the
legal register) and capture **each occupant's ID** with the camera
button on their row; capture or replace the guest's ID and address
proof; **edit the primary guest's nationality** (click **edit** next to
Nationality — updates the guest profile for the folio and printed
invoice); correct the **actual check-in/out times** when reality differs
from plan; and manage the stay's money line — advances, security
deposits, refunds (reason required, capped at what was collected).
Under Verify & Discard retention, every scan and full ID number is
masked and deleted at checkout.

### Walk-ins — one screen

For a guest standing at the counter, use **Walk-in** (top bar, or the
**Reservation / Walk-in** switch in New booking). On one screen enter the
guest's name, phone and **ID** (the ID types your country accepts), pick
the **room type and the actual room** (free tonight, clean rooms first),
the nights, and the **payment** — cash, card or transfer, the full
amount or part of it. **Check in & collect** books the stay, checks the
guest into the room and records the advance in one go. It is
all-or-nothing: if the till is closed or the room was just taken,
nothing is saved and the screen tells you why.

## Money — folios

Every stay has a folio; corporate stays may have Company/Group folios
that charges route to automatically (set per company under Corporate →
billing rules; alcohol always bills to the guest).

- **Post a charge** or **record a payment** from the folio screen.
- **Nationality** on the folio header is editable (**edit** → Save) and
  updates the guest profile for the printed bill.
- **Split** any line by percent or amount (`30%` or `1500`) to another
  folio; select several lines to **move them in bulk**.
- **Payment link** creates a gateway link for the balance and copies it.
- Night audit posts room nights at 3 AM, flags **and charges** no-shows
  per your policy. It's idempotent — safe to run manually too.

### Deposits before arrival

Secure a booking with a deposit at booking time or any time before
check-in: the **Deposit** panel appears on the booking-confirmed screen
and in the reservation drawer. It shows what the property's deposit %
expects, what has come in, and what is still due.

- **Record payment**: cash, card at the desk or a transfer (the methods
  your country pack offers). It goes through the till like any other
  payment, so the shift report and ledger include it.
- **Send payment link**: creates a gateway link for the amount due (or
  any amount you type) with a ready-made message to copy or send on
  WhatsApp. When the guest pays, the deposit posts itself.

Either way the money sits on the guest folio as an **Advance**, and at
check-in it counts against the bill, so the balance due is right. A
*Held* or *Pending Payment* booking is confirmed by its deposit.

## Cancelling

Open the reservation → **Cancel this stay…** You'll see what it costs
*before* you confirm (policy window and fee), pick a reason, optionally
waive the fee (logged). You get a **cancellation number** to give the
guest and a printable confirmation letter showing any refund due.
The status field itself refuses direct flips to Cancelled — the policy
can't be skipped by accident.

## Checkout & invoicing

Check out from the departure row (the chip warns you if money is owed).
Checkout back-fills any unposted nights. On the folio, **Close &
generate invoice** assigns the GST invoice number and produces the
printable multi-rate invoice (B2B GSTIN included when a company pays).
GSTR-1 export lives in the billing APIs for your accountant.

**Saudi Arabia:** settled bills print as a *Simplified Tax Invoice*
(*فاتورة ضريبية مبسطة*) with the ZATCA QR code; cancelling an invoice
issues a credit note. Set up the seller details once under *Settings →
ZATCA e-invoicing* — see [Country setup & ZATCA](/country-setup).

## Housekeeping

`/hk` on any phone: prioritized clean queue (rooms with arrivals jump
the line), tap Start/Done — Done marks the room clean on everyone's
board.

**Supervisors** (the *Housekeeping Supervisor* role, or the front desk)
get **Housekeeping → Room Board**: every room with its status, the guest
in it, who is due out, and each open task with its assignee — filter by
status or floor, tap a room to set its status. Attendants can mark
rooms Clean or Dirty; only a supervisor or the desk can pass a room
(Inspected) or take it Out of Order. The task list is under
**Housekeeping → Tasks**.

## WhatsApp

If your property connected its own number ([setup guide](/whatsapp)):
booking confirmations and self check-in links go out on their own.
**Operations → WhatsApp** is the inbox — threads per guest, chat on the
right, reply box at the bottom. Replies deliver while the guest's
24-hour session window is open (any message from them reopens it);
outside it, only templates deliver, and the screen says so. Messages
from in-house guests also raise a ticket on **Guest Requests**.

## The AI helpers

- **Front-desk copilot** (sparkle button, bottom right — if your admin
  enabled it): ask in plain language — "who's arriving?", "quote a
  double for the weekend", "cancel RES-2026-0142, guest request" — it
  quotes before booking, previews before cancelling, and every action
  it takes is logged.
- **MCP** — **Kamra Agent → Connect your AI → Connect Claude**. It acts
  as you. See [Connect your AI](/ai-and-mcp).
