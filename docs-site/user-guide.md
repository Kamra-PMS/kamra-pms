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
   and states the cancellation policy and any deposit expected.
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
proof; correct the **actual check-in/out times** when reality differs
from plan; and manage the stay's money line — advances, security
deposits, refunds (reason required, capped at what was collected).
Under Verify & Discard retention, every scan and full ID number is
masked and deleted at checkout.

## Money — folios

Every stay has a folio; corporate stays may have Company/Group folios
that charges route to automatically (set per company under Corporate →
billing rules; alcohol always bills to the guest).

- **Post a charge** or **record a payment** from the folio screen.
- **Split** any line by percent or amount (`30%` or `1500`) to another
  folio; select several lines to **move them in bulk**.
- **Payment link** creates a gateway link for the balance and copies it.
- Night audit posts room nights at 3 AM, flags **and charges** no-shows
  per your policy. It's idempotent — safe to run manually too.

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

## Housekeeping

`/hk` on any phone: prioritized clean queue (rooms with arrivals jump
the line), tap Start/Done — Done marks the room clean on everyone's
board.

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
