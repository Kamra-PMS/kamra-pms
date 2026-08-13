# Frappe Cloud Marketplace listing — Kamra

Paste-ready copy for the Frappe Cloud publisher form (frappecloud.com →
Marketplace → Kamra). Fill each field from the matching section below.
Keep this file in sync with the README when the feature set changes.

- **Repo / branch to build from:** `Kamra-PMS/kamra-pms`, branch `main`
- **Frappe version:** v16
- **Pricing:** Free
- **License:** AGPL-3.0
- **Category:** Hospitality (or nearest — "Other" if Hospitality is absent)

---

## Title

```
Kamra — Hotel & Short-Term Rental PMS
```

## Short description (one line / summary field)

```
The open-source, agent-ready PMS for hotels and short-term rentals — front desk, villa catalogs, direct booking, POS, housekeeping, folios and tax billing, on infrastructure you own.
```

## Tagline alternatives (pick per field length)

- `Open-source PMS for hotels and short-term rentals.`
- `Run your hotel or villa portfolio — booking, front desk, folios, POS — and bring your own AI.`

---

## Long description (About — markdown)

```markdown
**Kamra is a complete, open-source property management system for hotels and
short-term rentals, built on Frappe.** Front desk, direct booking, villa
catalogs, restaurant POS, housekeeping, folios and tax-correct billing — one
app, no per-room or per-module rent, and your data stays on infrastructure you
own.

Most hotel software was built twenty years ago: click-heavy screens, add-on
fees for night audit and reports, and your guest and rate history locked in a
vendor's cloud. Kamra is the alternative — every operation is a governed,
audited action, so your team (and the AI you trust) can actually run the
property.

### What makes Kamra different

- **Agent-ready, not agent-locked.** Kamra ships an MCP server with governed,
  role-scoped tools. Connect Claude or any MCP client — *"book Mr. Rao a deluxe
  for the weekend with breakfast"* — it quotes, books, and logs every action.
  Bring your own AI; there is no bundled model markup or lock-in.
- **Deterministic money.** Prices, taxes and availability come from a pricing
  engine, never from a language model. Tax slabs, multi-rate invoices and the
  no-overbooking guard are code, verified by an eval suite in CI.
- **Full audit trail.** Every action — human or AI — is logged with who, what
  and why.
- **Truly free.** AGPL-licensed. No per-room pricing, no per-seat fees, no
  license audits. Self-host on-prem or on any cloud, or run it here on Frappe
  Cloud.
- **Built on Frappe.** RBAC, multi-tenancy, audit trails and the frappe/payments
  gateway app come for free.

### What's inside

- **Front desk** — Today dashboard with paid/due chips, a guided check-in flow
  with AI room suggestions, tape chart with a live house-position row, ETA/ETD
  and changeover warnings, guest profile hub, blacklist.
- **Direct booking engine** — a commission-free, SEO-friendly public booking
  page with check-in / check-out, Check availability, a photo gallery, live
  per-date rates, policies, FAQ, map and pay-at-hotel — fully brandable,
  managed from an in-app console. Hotels get a room grid; short-term rentals
  get a villa catalog and per-listing pages.
- **Short-term rentals** — property kind Hotel vs Short Term Rental, sellable
  units (room, whole-place, package) with competition groups, per-villa
  locations on the public page, cleaning fees and refundable deposits, Instant
  or Request-to-book.
- **Bookings** — multi-room in one flow, group & corporate, booked-on-behalf,
  returning-guest typeahead, add-ons, travel agents with commissions, day-use.
- **Revenue** — occupancy-based pricing, seasons, rate plans, vouchers, meal
  plans, rate guardrails, demand-tier hurdle rates, a code-enforced overbooking
  allowance, and cancellation/no-show/deposit policies enforced in code.
- **Billing** — folios with per-line tax, corporate charge routing, group master
  folios, exact %/amount charge splits, automated night audit, tax invoices with
  B2B fields, cashier reconciliation, payment links via frappe/payments.
- **Restaurant POS** — area-wise table map with live states, concurrent & split
  bills, dine-in / room service / takeaway / delivery, 80mm thermal KOT & bill
  printing, kitchen display, inventory & recipes, guest QR ordering, room
  posting (alcohol-aware).
- **Operations** — service tickets with SLA, a housekeeping mobile app,
  end-to-end guest laundry, lost & found, shift handover, venues & events.
- **Guests** — self check-in with ID & address-proof capture, printable GRC with
  the legal occupant register, editable actual times, a stay ledger with
  advances/deposits/guarded refunds, retention-aware ID handling.
- **Messaging** — WhatsApp on your own Meta Cloud API number: automatic booking
  confirmations, check-in links, desk payment requests and a conversations inbox.
- **Localization** — country packs resolved per property: India GST (slabs),
  Indonesia PB1, Thailand VAT, Malaysia SST, UAE VAT (TRN), and a flat-tax
  generic for everywhere else; currency and number locale follow the pack.
- **Platform** — multi-property with per-user scoping, six-role RBAC, dark mode,
  onboarding wizard, CSV migration importers (eZee / Cloudbeds presets), and a
  51-check eval harness + 13-journey front-desk persona suite in CI.

### After you install

Open **`/kamra`** for the product UI (the Desk stays at `/app` as an admin
escape hatch). Sign in as Administrator and open **`/kamra/setup`** to create
your property and taxes, then add staff. Full manual at
**kamrapms.com/docs**.

**Try the live demo first:** [demo.kamrapms.com](https://demo.kamrapms.com) —
a sandbox pre-loaded with a sample hotel; the role logins are printed on the
page. For a live short-term rental catalog, see
[ewa.kamrapms.com/book](https://ewa.kamrapms.com/kamra/book).
```

---

## Screenshots (upload in this order, from `docs/screenshots/`)

Lead with the most legible, "what is this product" shots first.

| # | File | Caption |
|---|---|---|
| 1 | `today.png` | Today — arrivals, departures and in-house with paid/due chips |
| 2 | `tape-chart.png` | Tape chart — rooms × dates with room moves and a house-position row |
| 3 | `reservation-360.png` | Reservation 360 — live billing, date amend, guest journey and the right actions |
| 4 | `booking-dialog.png` | New booking — returning-guest typeahead, live quote, multi-room and add-ons |
| 5 | `invoice.png` | Folio & tax invoice — per-line tax, splits/transfers, payment links |
| 6 | `pos.png` | Restaurant POS — area-wise table map, concurrent bills, thermal KOT |
| 7 | `dashboard.png` | Property dashboard — occupancy, revenue and collections with a chain-wide roll-up |
| 8 | `public-booking.png` | Direct booking — check-in / check-out, Check availability, live rates |
| 9 | `str-catalog.png` | Short-term rental catalog — villa portfolio, date range, Check availability |
| 10 | `str-villas.png` | Places to stay — each villa at its own address with a from-rate |
| 11 | `str-listing.png` | Villa page — rooms or the whole house, live totals, caretaker call |
| 12 | `reports.png` | Manager reports — occupancy/ADR/RevPAR, MTD, collections, printable flash |
| 13 | `checkin-id.png` | Self check-in — guests photograph their ID on the phone; stored privately |

## Logo / icon

- **App logo:** `branding/png/kamra-mark-512.png` (or `kamra-square-1024.png`)
- Desk/app-switcher icon is already wired via `app_logo_url` in `hooks.py`.

## Links

| Field | Value |
|---|---|
| Website | https://kamrapms.com |
| Documentation | https://kamrapms.com/docs/ |
| Source | https://github.com/Kamra-PMS/kamra-pms |
| Support email | hello@kamrapms.com |
| Live demo | https://demo.kamrapms.com |
| Terms | https://kamrapms.com/terms *(create if the form requires one)* |
| Privacy | https://kamrapms.com/privacy *(create if the form requires one)* |

## Publisher profile

- **Publisher:** HeyKoala
- **Contact:** hello@kamrapms.com
- **Website:** https://kamrapms.com
