# Frappe Cloud Marketplace listing — Kamra

Paste-ready copy for the Frappe Cloud publisher form
(frappecloud.com → Marketplace → Kamra). Keep this file in sync with the
README when the feature set changes.

Copy follows the [marketplace guidelines](https://docs.frappe.io/cloud/marketplace/marketplace-guidelines)
and [app authoring guidelines](https://docs.frappe.io/cloud/marketplace/app-authoring-guidelines):
short description 40–80 characters, no install steps, no persuasion away
from Frappe Cloud.

- **Repo / branch to build from:** `Kamra-PMS/kamra-pms`, branch `main`
- **Frappe version:** v16
- **Pricing:** Free
- **License:** AGPL-3.0
- **Category:** Hospitality (use **Other** if Hospitality is absent — do
  **not** leave it on E-Commerce)
- **Public listing (currently Not Available):** https://frappecloud.com/marketplace/apps/kamra

---

## Title

```
Kamra — Hotel & Short-Term Rental PMS
```

## Short description (one line / summary field)

40–80 characters, one sentence, do not repeat the app name.

```
Open-source PMS for hotels and short-term rentals.
```

(48 characters.)

---

## Long description (About — markdown)

Do not paste install instructions. Frappe Cloud installs the app.

```markdown
A complete property management system for hotels and short-term rentals,
built on Frappe. Front desk, direct booking, villa catalogs, restaurant POS,
housekeeping, folios and tax-correct billing — one app, no per-room or
per-module rent.

Most hotel software was built twenty years ago: click-heavy screens, add-on
fees for night audit and reports, and guest history locked in a vendor
cloud. Kamra treats every operation as a governed, audited action, so your
team (and the AI you trust) can actually run the property.

Install it on your Frappe Cloud site from this listing. The `payments` app
is pulled in automatically.

### What makes it different

- **Agent-ready, not agent-locked.** An MCP server exposes 52 role-scoped
  tools. Click Connect Claude — *"book Mr. Rao a deluxe for the
  weekend with breakfast"* — it quotes, books, and logs every action. Bring
  your own AI; there is no bundled model markup.
- **Deterministic money.** Prices, taxes and availability come from a
  pricing engine, never from a language model. Tax slabs, multi-rate
  invoices and the no-overbooking guard are code, verified by an eval suite
  in CI.
- **Full audit trail.** Every action — human or AI — is logged with who,
  what and why.
- **AGPL and free.** No per-room pricing, no per-seat fees, no license
  audits. The same code runs on Frappe Cloud and anywhere else you host a
  Frappe bench.
- **Built on Frappe.** RBAC, multi-tenancy, audit trails and the
  frappe/payments gateway app come with the stack.

### What's inside

- **Front desk** — Today dashboard with paid/due chips, a guided check-in
  flow with AI room suggestions, tape chart with a live house-position row,
  ETA/ETD and changeover warnings, guest profile hub, blacklist.
- **Direct booking engine** — a commission-free, SEO-friendly public
  booking page with check-in / check-out, Check availability, a photo
  gallery, live per-date rates, policies, FAQ, map and pay-at-hotel —
  brandable from an in-app console. Hotels get a room grid; short-term
  rentals get a villa catalog and per-listing pages.
- **Short-term rentals** — property kind Hotel vs Short Term Rental,
  sellable units (room, whole-place, package) with competition groups,
  per-villa locations, cleaning fees and refundable deposits, Instant or
  Request-to-book.
- **Bookings** — multi-room in one flow, group & corporate,
  booked-on-behalf, returning-guest typeahead, add-ons, travel agents with
  commissions, day-use.
- **Revenue** — occupancy-based pricing, seasons, rate plans, vouchers,
  meal plans, rate guardrails, demand-tier hurdle rates, a code-enforced
  overbooking allowance, and cancellation/no-show/deposit policies
  enforced in code.
- **Billing** — folios with per-line tax, corporate charge routing, group
  master folios, exact %/amount charge splits, automated night audit, tax
  invoices with B2B fields, cashier reconciliation, payment links via
  frappe/payments.
- **Restaurant POS** — area-wise table map with live states, concurrent &
  split bills, dine-in / room service / takeaway / delivery, 80mm thermal
  KOT & bill printing, kitchen display, inventory & recipes, guest QR
  ordering, room posting (alcohol-aware).
- **Operations** — service tickets with SLA, a housekeeping mobile app,
  end-to-end guest laundry, lost & found, shift handover, venues & events.
- **Guests** — self check-in with ID & address-proof capture, printable
  GRC with the legal occupant register, editable actual times, a stay
  ledger with advances/deposits/guarded refunds, retention-aware ID
  handling.
- **Messaging** — WhatsApp on your own Meta Cloud API number: automatic
  booking confirmations, check-in links, desk payment requests and a
  conversations inbox.
- **Localization** — country packs resolved per property: India GST
  (slabs), Indonesia PB1, Thailand VAT, Malaysia SST, UAE VAT (TRN), and a
  flat-tax generic for everywhere else; currency and number locale follow
  the pack.
- **Platform** — multi-property with per-user scoping, six-role RBAC, dark
  mode, onboarding wizard, CSV migration importers (eZee / Cloudbeds
  presets), and a 51-check eval harness + 13-journey front-desk persona
  suite in CI.

### Try it

Live hotel demo: [demo.kamrapms.com](https://demo.kamrapms.com) — a
sandbox; role logins are printed on the page.

Live short-term rental catalog:
[ewa.kamrapms.com/book](https://ewa.kamrapms.com/kamra/book).

After install, the product UI is at `/kamra`. Sign in as Administrator and
open `/kamra/setup` to create the first property.
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

- **App logo:** `branding/png/kamra-mark-512.png` (square, no wordmark —
  Frappe crops logos into a circle)
- Desk/app-switcher icon is already wired via `app_logo_url` in `hooks.py`.

## Required URLs

| Field | Value |
|---|---|
| Support URL | https://kamrapms.com/support |
| Privacy Policy URL | https://kamrapms.com/privacy |
| Website | https://kamrapms.com |
| Documentation | https://kamrapms.com/docs/ |
| Source | https://github.com/Kamra-PMS/kamra-pms |
| Terms | https://kamrapms.com/terms |
| Live demo | https://demo.kamrapms.com |
| Support email | hello@kamrapms.com |

## Publisher profile

- **Publisher display name:** HeyKoala (or Mohammed Azzan — match the
  Frappe Cloud team)
- **Contact:** hello@kamrapms.com
- **Website:** https://kamrapms.com

## Demo video (reviewers ask for this)

Record a 2–4 minute silent or narrated walkthrough and attach it to the
Frappe Cloud review / support ticket:

1. Open https://demo.kamrapms.com and show the printed role logins.
2. Sign in as Front Desk → Today → tape chart → new booking → folio.
3. Open `/book` and run Check availability.
4. Optional: https://ewa.kamrapms.com/kamra/book for the villa catalog.
5. Open `/kamra/setup` only if you want to show first-run (skip if it
   would mutate the shared demo).

Upload to YouTube (unlisted) or Loom and paste the URL into the listing
and the support ticket.

---

## Dashboard checklist (unhalt the listing)

The public page already exists at
https://frappecloud.com/marketplace/apps/kamra and shows **Not Available**.
Kamra is **not** in the 347 published marketplace apps. Status is Draft /
no approved release.

In https://frappecloud.com/dashboard → **Marketplace** → **Kamra**:

1. **Overview** — paste Title, Short description, Long description above.
2. **Category** — Hospitality or Other (currently E-Commerce).
3. **Logo** — `branding/png/kamra-mark-512.png`.
4. **Screenshots** — the 13 files above, in that order, with captions.
5. **Links** — Support + Privacy are mandatory; fill the rest too.
6. **Releases** — create / select the `main` release at **v2.5.0**
   (`7a50c56` / tag `v2.5.0`) and click **Publish**.
7. If a previous request is **Rejected**, cancel it and publish a new
   one from current `main`.
8. If the app has been in Draft **more than 10 days**, raise a ticket at
   https://support.frappe.io/ (SLA in the publishing docs).

### Support ticket (paste)

```
Subject: Marketplace listing for Kamra (kamra) — request to complete review

Hi Frappe Cloud team,

The Kamra marketplace app is at https://frappecloud.com/marketplace/apps/kamra
and still shows "Not Available" (Draft / no approved public release).

We submitted earlier; Semgrep findings from that review were fixed in
https://github.com/Kamra-PMS/kamra-pms/pull/16 and are on main. Stable
release is v2.5.0 (Frappe v16, AGPL-3.0, required_apps = payments).

Please re-scan main and approve the latest release.

Repo: https://github.com/Kamra-PMS/kamra-pms
Branch / tag: main / v2.5.0
Demo: https://demo.kamrapms.com
Docs: https://kamrapms.com/docs/
Support: https://kamrapms.com/support
Privacy: https://kamrapms.com/privacy
Publisher contact: hello@kamrapms.com

Happy to join a short review call or share a demo video.

Thanks,
Mohammed Azzan
HeyKoala
```

### discuss.frappe.io announcement (after it goes live)

```
Title: Kamra PMS — open-source hotel & short-term rental PMS on Frappe v16

Kamra is an AGPL property management system for hotels and short-term
rentals, built on Frappe v16. Front desk, direct booking, villa catalogs,
POS, housekeeping, folios and tax billing — install from the Frappe Cloud
Marketplace onto your site.

- Marketplace: https://frappecloud.com/marketplace/apps/kamra
- Release: https://github.com/Kamra-PMS/kamra-pms/releases/tag/v2.5.0
- Live demo: https://demo.kamrapms.com
- Villa catalog: https://ewa.kamrapms.com/kamra/book
- Docs: https://kamrapms.com/docs/
- Source: https://github.com/Kamra-PMS/kamra-pms
```
