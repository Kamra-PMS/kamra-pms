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

From the arrival row: open the **GRC**, record the **occupants**
(everyone in the room — the legal register), print, sign, then
**Check in**. Pre-checked-in guests arrive with ID details already
submitted.

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

## The AI helpers

- **Front-desk copilot** (sparkle button, bottom right — if your admin
  enabled it): ask in plain language — "who's arriving?", "quote a
  double for the weekend", "cancel RES-2026-0142, guest request" — it
  quotes before booking, previews before cancelling, and every action
  it takes is logged.
- **MCP** connects Claude or any MCP client to the same tools — see
  [AI & API setup](ai-and-api.md).
