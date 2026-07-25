# Features tour

Everything below ships in the open-source app — no editions, no gates.

## Front desk

Tape chart (rooms × dates, drag to move, hourly view for day-use) with a
live **house-position row** (sold/capacity per day, demand arrows,
overbooking flags), **ETA/ETD on every stay** and automatic
**changeover-conflict warnings** when an arrival lands before the room
frees; the Today board (arrivals/departures/in-house with payment chips),
calendar selling by room type, group bookings with room blocks and pickup
tracking, **room blocks** for VIP/house-use/maintenance holds, self check-in links (guests attach a
**photo of their ID** — camera capture or upload — stored privately and
**deleted at checkout** under Verify & Discard retention), and a **central reservations**
screen that searches availability across every property you manage.

**Check-in is a flow, not a button**: from the arrivals board, one
click shows how ready the stay is (online check-in state, ID and
address proof on file, phone/email, VIP flag) with the GRC a click
away — then the room: the **allocator proposes one with its
reasoning** (VIP → quiet high floor, preference matches) or the desk
picks from every free room with housekeeping state shown, and a
warning before handing over an uncleaned room.

**The GRC and the register**: a printable registration card per stay
with **ID and address-proof capture** (camera or upload, privately
stored), an **occupant register** — every person in the room with
their own **ID scan per occupant** — editable actual check-in/out
times, and the stay's money line (advances, security deposits held,
refunds) with a guarded refund flow. Under **Verify & Discard**
retention, every scan and full ID number — the guest's and each
occupant's — is masked and deleted at checkout.

**Revenue controls**: a per-property (or per-room-type) **overbooking
allowance** enforced in code — unassigned bookings can never quietly
oversell a category; **hurdle rates** — when forecast occupancy crosses a
threshold, quotes carry a demand premium automatically and no rate (human
or agent) may sell below the tier's minimum; and a **position briefing**
the copilot reads to the GM: occupancy vs the overbooking ceiling,
arrivals by ETA, departures with balances, conflicts and a 7-day outlook.

## Money

A folio per stay with per-line GST; split any charge by percent or
amount; route lines between Guest/Company/Group folios (alcohol can never
reach a company folio); night audit that posts room nights idempotently
and charges no-shows per policy; GST invoices with per-property series;
allowances, part-settlement, invoice cancellation with a register;
**GSTR-1 export** in Tally / Zoho Books / ERPNext formats.

## Your country's taxes

Localization packs make invoices native to where you operate, resolved
automatically from the property's country: **India** (GST slabs by
tariff, GSTIN, GSTR-1), **Indonesia** (PB1/PBJT regional hotel tax,
NPWP, Rupiah — community-contributed), **Thailand** (7% VAT, Thai tax
invoice labels, Baht), **Malaysia** (SST with the real 8% rooms / 6%
F&B split, Tourism Tax as a folio line, SST registration number),
**UAE** (5% VAT, TRN tax invoices, Dirham), and a clean flat-tax pack
for everywhere else. **Currency symbols and number formats follow the
pack** across every screen, report and thermal ticket — an Indonesian
property reads Rp 3.300.000, an Indian one ₹ and lakhs. The pack seam
is open source; contributing your country is a single Python file.

## WhatsApp on your own number

Connect your own Meta Cloud API number (no gateway, no markup — Meta
bills you directly) and Kamra sends **booking confirmations and self
check-in links automatically**, takes **payment requests** from the
desk, and escalates housekeeping SLAs to managers. Guest replies land
in a **conversations inbox** — threads per guest, chat bubbles,
replies inside the 24-hour session window — and messages from
in-house guests also raise a Service Ticket on the desk queue.
[Step-by-step setup guide →](/whatsapp)

## F&B — POS and kitchen

Outlet-based restaurant POS with a photo menu, per-item instructions and
guest discounts. The captain works from a colour-coded **table map**
(vacant / running / in kitchen / ready) and can juggle several running
bills at once — dine-in, room service, takeaway and delivery (with the
customer's name, phone and address carried onto the KOT and bill). A table holds **any
number of bills** (two parties sharing a table each get their own), bills
**split by items** onto a new bill with kitchen status preserved, and
ad-hoc **temp tables** can be named on the fly (they appear as live
tiles until settled). Table layouts group **area-wise** — Main Hall,
Patio, Rooftop — with area filters on the map. **NC (no charge)** bills
need an authorizer (captain / chef / GM) and a reference, print "NC — NO
CHARGE" on the KOT and bill, close at zero and never touch a folio. Tables can be **reserved**
(guest, phone, party size, time) - the tile shows "Res 10:30" with
seat / no-show / cancel actions - and a settled table flips to
**Cleaning** until marked done (auto-clears in 30 min). Firing a KOT stamps a
daily **KOT number** and prints an **80mm thermal ticket** (KDS-only
kitchens can turn printing off); a live **kitchen display** per outlet
(Kitchen/Bar stations, colour-aged tickets) runs alongside. Bills print on
thermal with the CGST/SGST split; walk-ins **settle by cash/card/UPI** at
the outlet while room-service posts straight to the folio. Line voids and
order cancellations require a reason, so the KOT-vs-bill audit holds up.
Guests scan a **QR menu** to order — a captain confirms before anything
fires. The **kitchen display v2** works like a real pass: new KOTs chime
in (sound toggle), the kitchen **accepts/starts** each ticket, items
bump per station and course with **allergy highlighting**, guests and
captain on every card, a timeline with progress, LATE/COOKING aging,
and a **recall** when something bumped too soon. **Inventory & recipes**:
ingredients with a stock ledger, recipes per menu item, consumption
posted as KOTs fire; and the **menu imports in bulk** from a spreadsheet
with a preview.

## Housekeeping

A phone app for floor staff: task assignment *and* a self-claim pool,
accept/decline with reasons, VIP and arrival context on every card,
minibar/laundry posting from the room grid, lost & found logging, and
SLA escalation (overdue → supervisor → manager, with WhatsApp alerts
when a channel is connected).

**Guest laundry, end to end**: a per-item **rate card** (wash & iron /
dry clean / iron only, with express pricing) managed in Settings; pickup
requests queue to the floor; the attendant **counts the bag with the
guest** — priced from the card, never by hand; the bag tracks
Collected → In Process → Ready; items **return piece by piece**, and a
missing piece blocks delivery unless a shortage note says why. Delivery
bills the stay automatically at the services GST rate through the same
governed path as the minibar. Guests can **request pickup themselves**
from their in-stay page; the desk gets a **laundry console** with
promised ready-by times, overdue flags, printable dockets and a revenue
panel; **house laundry** (uniforms, hotel linen) and complimentary bags
are tracked as volume but never billed.

## Direct bookings

A public booking page with live availability and real quotes, photo
galleries, policies and FAQs, promo codes, **experiences as add-ons**
(spa, safari, dinner), configurable advance collection (percent / fixed /
full / pay-at-hotel — terms are snapshotted per booking), your brand
colour, and SEO baked in (schema.org hotel markup, OG images).

## Multi-property

One login, a property switcher, **shared guest profiles across the
chain**, per-user property permissions (enforced server-side), central
reservations, and a portfolio dashboard rolling up occupancy, revenue
and collections per property.

## Dashboards & reports

Property dashboard by department (front desk / housekeeping / finance),
month-to-date statistics (ADR, RevPAR, occupancy), manager flash,
budget vs actual, contribution by source/company/agent, operations SLA
report, cashier reconciliation.

## Switching from another PMS

Export your bookings from eZee, Cloudbeds or anything that produces a
CSV, and the importer does the rest: it recognises each vendor's column
names, detects the date convention (day-first vs month-first), matches
room types by code or name, and maps their status words onto ours. A
**preview** shows the mapping, the rows that will import and exactly why
any row would be skipped — before anything is written. Past stays come
in as guest **history** (checked-out / cancelled / no-show) without
tripping live-booking rules, so returning guests are recognised from day
one.

## AI & audit

An MCP server with 32 governed tools, an in-app copilot (bring your own
key), rate guardrails agents cannot price outside, deterministic pricing
verified by an automated eval suite, and an activity ledger recording
every action — human or AI — with who, what and why.
