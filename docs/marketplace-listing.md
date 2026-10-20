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
  **not** leave it on E-Commerce; the live page still shows E-Commerce)
- **Public listing (live):** https://frappecloud.com/marketplace/apps/kamra
- **Stable release to publish:** `main` / **v2.6.16**

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
Do not put URLs in the long description — Website / Docs / Support
fields already hold those; extra links fail the metadata audit.

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

- **Agent-ready, not agent-locked.** An MCP server exposes role-scoped
  tools, filtered by the property's enabled modules. Click Connect Claude —
  *"book Mr. Rao a deluxe for the weekend with breakfast"* — it quotes,
  books, and logs every action. Bring your own AI; there is no bundled
  model markup.
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

- **Front desk** — Today dashboard with paid/due chips, a one-screen walk-in
  (book, ID, room, payment, check-in), a guided check-in flow with AI room
  suggestions, room change from the reservation or the GRC, tape chart with
  a live house-position row, ETA/ETD and changeover warnings, guest profile
  hub, blacklist, and checkout that waits until every bill is settled.
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
  commissions, day-use, deposits taken before arrival.
- **Revenue** — occupancy-based pricing, seasons, rate plans, vouchers,
  meal plans, rate guardrails, demand-tier hurdle rates, a code-enforced
  overbooking allowance, and cancellation/no-show/deposit policies
  enforced in code.
- **Billing** — folios with per-line tax, corporate charge routing, group
  master folios, exact %/amount charge splits, automated night audit, tax
  invoices with B2B fields, Opera-style cashier till (FO+POS cash, PIN
  pad), append-only folio ledger, payment links via frappe/payments.
- **Restaurant POS** — area-wise table map with live states, concurrent &
  split bills, dine-in / room service / takeaway / delivery, full-screen
  till and kitchen pass, 80mm thermal KOT & bill printing, kitchen display,
  inventory & recipes, room posting (alcohol-aware).
- **Operations** — service tickets with SLA, a housekeeping mobile app with
  a supervisor room board, end-to-end guest laundry, lost & found, shift
  handover.
- **Banquets & events** — function management from enquiry to close-out:
  floor plans, hall deals, menu pre-costing and margin, quotations by email
  or WhatsApp, guest response, and department checklists on Confirm.
- **Guests** — self check-in with ID & address-proof capture, printable
  GRC with the legal occupant register, editable actual times, a stay
  ledger with advances/deposits/guarded refunds, retention-aware ID
  handling.
- **Privacy** — privacy by design for India's DPDP Act: complete erasure,
  access export, retention schedules, and the guest notice in Hindi,
  Kannada, Tamil, Telugu, Malayalam, Marathi and Bengali. Guest contact
  details are hidden from the AI provider.
- **Messaging** — WhatsApp on your own Meta Cloud API number: automatic
  booking confirmations, check-in links, desk payment requests and a
  conversations inbox.
- **Localization** — country packs resolved per property: India GST
  (slabs), Saudi VAT with ZATCA e-invoicing (Phase 1) and room levy,
  Indonesia PB1, Thailand VAT, Malaysia SST, UAE VAT (TRN), and a flat-tax
  generic for everywhere else. Tax, invoices, ID types, payment modes and
  statutory integrations follow the pack — India gets Razorpay and
  Cashfree payment links, GSTR-1 and GSTIN / guest ID verification. English
  and Arabic (RTL) interface.
- **Platform** — multi-property with per-user property scoping enforced on
  every record, six-role RBAC, webhooks that refuse unsigned calls, dark
  mode, property time zone, System Health diagnostics, AI provider presets
  (OpenAI, Gemini, Groq, OpenRouter, Ollama), onboarding wizard, CSV
  migration importers (eZee / Cloudbeds presets), runs alongside ERPNext
  (Company and stock), and an eval harness plus front-desk persona journeys
  in CI.

### After install

The product UI is at `/kamra`. Sign in as Administrator (or
admin@example.com) with the site password and open
`/kamra/setup` to create the first property. Put the live demo and catalog
on the Website / Documentation fields — Frappe Cloud fails the listing
audit if the long description contains any other links.
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
4. Optional: https://demo.kamrapms.com/book for the public booking page.
5. Open `/kamra/setup` only if you want to show first-run (skip if it
   would mutate the shared demo).

Upload to YouTube (unlisted) or Loom and paste the URL into the listing
and the support ticket.

---

## Dashboard checklist (publish / update a release)

The public page is live at
https://frappecloud.com/marketplace/apps/kamra (installs are open).
Automated Submission Gate `AUD-kamra-00003` was **22 passed / 1 minor
warning** (no blocking Fail).

Before publishing a new SHA:

```bash
python kamra/scripts/marketplace_install_check.py
```

In https://frappecloud.com/dashboard → **Marketplace** → **Kamra**:

1. **Overview** — paste Title, Short description, Long description above
   (re-paste when the feature set changes).
2. **Category** — switch from **E-Commerce** to **Hospitality** (or Other).
3. **Logo** — `branding/png/kamra-mark-512.png` (confirm still current).
4. **Screenshots** — the 13 files above, in that order, with captions
   (confirm all are uploaded; the public page should show more than the logo).
5. **Links** — Support + Privacy are mandatory; fill the rest too.
6. **Releases** — create / select the `main` release at **v2.6.16** and
   click **Publish** (or submit for approval if the dashboard still gates it).
7. If a previous request is **Rejected**, cancel it and publish a new
   one from current `main`.
8. Optional but useful for reviewers: attach a 2–4 minute demo video
   (see above).

### Support ticket (paste — category / release update)

```
Subject: Marketplace listing for Kamra (kamra) — category + v2.6.16 release

Hi Frappe Cloud team,

Kamra is live at https://frappecloud.com/marketplace/apps/kamra.
Please:

1. Change the category from E-Commerce to Hospitality (or Other if
   Hospitality is not available).
2. Approve / publish the latest App Release from main at v2.6.16
   (Frappe v16, AGPL-3.0, required_apps = payments).

Offline install checks and CI on main are green. Registry PR for
v2.6.16 is open against frappe/marketplace.

Repo: https://github.com/Kamra-PMS/kamra-pms
Branch / tag: main / v2.6.16
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

## Frappe marketplace registry (`frappe/marketplace`)

Separate from the Frappe Cloud listing: the
[frappe/marketplace](https://github.com/frappe/marketplace) repo is the
registry `bench get-app` and Pilot read. Releases are commit-scoped and land
by PR. Kamra's entry is `apps.json` (category `Applications`) plus
`apps/kamra.json`. Current stable entry to add:

```json
{
  "version": "2.6.16",
  "branch": "main",
  "commit": "e3341b8f5795795f041e95c31fa98e0603f15db7",
  "frappe_core": ">=16.0.0-dev,<17.0.0",
  "dependencies": { "payments": ">=0.0.1,<1.0.0" },
  "channel": "stable"
}
```

The registry CI reads `version` from the `__version__` line verbatim and
rejects symlinks that point outside the repo, so keep the release-please
marker on its own lines in `kamra/__init__.py`. To add a later release,
from a checkout of the registry and of Kamra at the tag:

```bash
APP=kamra BRANCH=main COMMIT=<sha> CHANNEL=stable \
  python3 tools/add_release.py --app-dir ../kamra-pms --registry .
```

Comment `/rereview` on the registry PR to re-run its checks after a fix.

### discuss.frappe.io announcement (after a release update)

```
Title: Kamra PMS — open-source hotel & short-term rental PMS on Frappe v16

Kamra is an AGPL property management system for hotels and short-term
rentals, built on Frappe v16. Front desk, direct booking, villa catalogs,
POS, banquets, housekeeping, folios and tax billing (India GST, Saudi
ZATCA, Gulf and South-East Asian VAT) — install from the Frappe Cloud
Marketplace onto your site, or `bench get-app kamra` from the Frappe
marketplace registry.

- Marketplace: https://frappecloud.com/marketplace/apps/kamra
- Release: https://github.com/Kamra-PMS/kamra-pms/releases/tag/v2.6.16
- Live demo: https://demo.kamrapms.com
- Villa catalog: https://demo.kamrapms.com/book
- Docs: https://kamrapms.com/docs/
- Source: https://github.com/Kamra-PMS/kamra-pms
```
