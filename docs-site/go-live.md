# Go-live checklist

Everything between "we chose Kamra" and "the front desk ran today on
it". Worked through top to bottom, a small property goes live in a
day; with data migration and OTA sync, plan two to three. Each step
links to the deeper guide.

## 1 — Get a server and install

- [ ] **Pick where it runs**: a 2 vCPU / 4 GB RAM / 40 GB SSD VPS is
  enough for a full property ([requirements](/self-hosting/)). Guides:
  [Hostinger](/self-hosting/hostinger) ·
  [DigitalOcean](/self-hosting/digitalocean) ·
  [Linode](/self-hosting/linode) · [AWS](/self-hosting/aws) ·
  [bench install](/self-hosting/bench) ·
  [Frappe Cloud](/self-hosting/frappe-cloud)
- [ ] Install via [Docker quickstart](/quickstart), create your site,
  point your domain, get SSL (covered in each hosting guide)
- [ ] **Log in** at `/kamra` as `Administrator` (or `admin@example.com`)
  with the password from `--admin-password`, then change it if needed
- [ ] Set up **daily backups** off the server (the hosting guides show
  `bench backup` + object storage; on Kamra Cloud we do this for you)

## 2 — Property setup

- [ ] Run the **onboarding wizard**: property name, **country** (this
  selects your [tax pack](/features#your-countrys-taxes) — GST slabs,
  PB1, VAT, SST — and your currency/number format), address, contacts
- [ ] **Room types** with base prices, occupancy/capacity limits, bed
  types, photos — then **rooms** with numbers and floors
- [ ] **Rate card**: seasons, rate plans, meal plans; optional
  guardrails, hurdle rates and an overbooking allowance (Revenue menu)
- [ ] **Taxes**: verify a test quote shows the right tax for your
  country; set your tax registration number (GSTIN / NPWP / TRN / SST
  no.) on the property
- [ ] **Policies**: check-in/out times, free-cancellation window,
  cancellation fee, no-show charge, deposit expectations — these are
  enforced in code, not just printed
- [ ] **Invoice series**: per-property invoice numbering starts clean;
  do a test invoice and check the format before real money
- [ ] **ID retention mode**: Store, or Verify & Discard (scans and ID
  numbers auto-scrubbed at checkout — the DPDP-friendly setting)

## 3 — Staff

- [ ] Create a **user per staff member** — never shared logins; the
  audit trail is only as good as this
- [ ] Assign roles: Front Desk, Housekeeping, Finance, Revenue
  Manager, Hotel Admin (menus follow the role)
- [ ] Multi-property? Scope users to their property (User Permissions)
- [ ] Bookmark the phone screens on staff devices: `/hk`
  (housekeeping), POS for captains
- [ ] Walk the desk through the [front-desk guide](/user-guide) — one
  hour covers a shift's work

## 4 — Bring your data over

- [ ] Export bookings/guests from the old system (eZee, Cloudbeds, or
  any CSV) and run the **[migration importer](/features#switching-from-another-pms)** —
  preview first, then import; past stays land as history so returning
  guests are recognised
- [ ] Spot-check 10 imported bookings against the old system: dates,
  rates, statuses
- [ ] Import the **laundry rate card** (CSV) and the **menu**
  (bulk import with preview) if you run F&B

## 5 — Distribution

- [ ] **Booking engine**: photos, description, policies, FAQs, brand
  colour; enable the public page and make a test booking on it;
  configure advance collection and the payment gateway if collecting
  online
- [ ] **Channel manager** for OTA sync —
  [setup guide](/channel-manager): Channex self-serve today, STAAH /
  AioSell with their partner credentials. Map room types, push ARI,
  send a **test booking from the OTA extranet** and watch it land as a
  reservation
- [ ] Until the channel manager is live, set OTA inventories manually
  and treat Kamra as the source of truth

## 6 — Guest communication

- [ ] **Email (SMTP)**: [set up an Email Account](/self-hosting/email)
  so confirmations and links can send
- [ ] **WhatsApp on your own number** — [guide](/whatsapp): Meta app,
  webhook, the three templates; send yourself a test confirmation and
  reply to it to see the conversations inbox work
- [ ] Print a **QR menu** card if guests order F&B by phone

## 7 — Operations

- [ ] POS: outlets, tables with areas (`[Main Hall] T1:4`), menu with
  photos, KOT printer or kitchen display at the pass
- [ ] Housekeeping: confirm every room shows on `/hk`, brief the team
  on claim/accept/done and minibar/laundry posting
- [ ] Service-ticket SLAs and the escalation contact (WhatsApp alerts
  once connected)

## 8 — Dress rehearsal (do this before cut-over)

Run one fake stay end to end and check every artifact:

- [ ] Book (on the public page or desk) → confirmation received
- [ ] Check in via the **check-in flow** → GRC prints, occupant
  register + ID captured, room assigned
- [ ] Post a room-service charge from POS → appears on the folio
- [ ] Record a payment, then **check out** → invoice generates with
  the right taxes and series
- [ ] Run the **night audit** manually once and read what it did
- [ ] Verify the backup from step 1 actually restored on a scratch
  site — an unrestored backup is a rumour

## 9 — Cut-over day

- [ ] Pick a quiet day; freeze changes in the old system at a fixed
  hour
- [ ] Re-import the delta (bookings created since the export)
- [ ] Point the channel manager live; retire the old system's OTA
  connections the same hour (two masters means double bookings)
- [ ] Keep the old system read-only for reference; first **night
  audit** on Kamra that night, first reconciliation next morning

## Need hands?

All of the above as a done-for-you package: fixed-fee
[implementation with an annual support contract](https://kamrapms.com/implementation/),
or [Kamra Cloud](https://kamrapms.com/#cloud) where the server side of
this list disappears entirely. The software is identical either way —
nothing on this page is gated.
