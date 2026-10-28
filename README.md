<p align="center">
  <img src="branding/png/kamra-mark-512.png" width="96" alt="Kamra, open-source hotel PMS" />
</p>

<h1 align="center">Kamra PMS</h1>

<p align="center">
  <b>Open-source hotel &amp; short-term rental PMS</b>: front desk, booking engine,<br/>
  folios &amp; tax billing, housekeeping, POS, and an <b>MCP tool layer</b> so AI agents can run the property.
</p>

<p align="center">
  <a href="https://demo.kamrapms.com"><img src="https://img.shields.io/badge/demo-live-0f766e?style=flat-square" alt="Live demo" /></a>
  <a href="https://github.com/Kamra-PMS/kamra-pms/releases/latest"><img src="https://img.shields.io/github/v/release/Kamra-PMS/kamra-pms?style=flat-square&label=release" alt="Latest release" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0-blue?style=flat-square" alt="AGPL-3.0" /></a>
  <a href="https://cloud.frappe.io/marketplace/apps/kamra"><img src="https://img.shields.io/badge/Frappe%20Cloud-Marketplace-ed8936?style=flat-square" alt="Frappe Cloud Marketplace" /></a>
  <a href="https://kamrapms.com/docs/"><img src="https://img.shields.io/badge/docs-kamrapms.com-111827?style=flat-square" alt="Documentation" /></a>
  <img src="https://img.shields.io/github/stars/Kamra-PMS/kamra-pms?style=flat-square" alt="GitHub stars" />
</p>

<p align="center">
  <a href="https://demo.kamrapms.com"><b>▶ Live demo</b></a> ·
  <a href="https://kamrapms.com/docs/"><b>Docs</b></a> ·
  <a href="#install"><b>Install</b></a> ·
  <a href="https://kamrapms.com/docs/ai-and-mcp"><b>AI / MCP</b></a> ·
  <a href="mailto:hello@kamrapms.com"><b>Contact</b></a>
</p>

> **Try it in 30 seconds → [demo.kamrapms.com](https://demo.kamrapms.com)**  
> Tap any role to sign in (credentials are on the page). Guest booking: [/book](https://demo.kamrapms.com/book) · Housekeeping app: [/kamra/hk](https://demo.kamrapms.com/kamra/hk)

**Kamra** is a full **property management system (PMS)** for hotels, resorts, and **short-term rentals / villas**. It runs on **Frappe** (the framework behind ERPNext), is **AGPL-3.0**, and is built so humans *and* AI agents share the same governed APIs (booking, check-in, folios, night audit, pricing), with deterministic money (never from an LLM).

---

## Contents

- [What's new](#whats-new)
- [Why Kamra](#why-kamra)
- [What makes it different](#what-makes-it-different)
- [Screenshots](#screenshots)
- [Short-term rentals](#short-term-rentals)
- [Features](#features)
- [Countries](#countries)
- [How it's built](#how-its-built)
- [Documentation & API](#documentation--api)
- [Install](#install)
- [Quickstart (development)](#quickstart-development)
- [Contributing](#contributing)
- [Who it's for](#who-its-for)
- [License & contributors](#license--contributors)

---

## What's new

Latest release: **[v2.6.17](https://github.com/Kamra-PMS/kamra-pms/releases/latest)**
(`develop` ships nightly).

- **2.6.17**: kitchen printers on the local network; auto-accept KOT setting;
  faster POS and live kitchen display; company credit terms; go-live
  opening balances; webhooks and a door-lock interface
- **2.6.16**: pet charge per pet, stay or night; guests above room capacity
  billed as their own line
- **2.6.15**: End of Day night-audit checklist with a saved report pack and a
  Night Auditor role; corporate guests settle their own extras; POS bills
  can't close unpaid; advance deposits clear at check-in
- **2.6.14**: Request-to-Book inbox, per-property no-show policy, rate lock
  at booking, security deposits, day use, city-ledger
  payments, a complete ledger, and a lighter first page load
- **2.6.13**: settings hub, tiered cancellation and peak-date rules, POS
  auto-KOT; night audit can't run ahead of the calendar, no-show balances read
  from the folio, whole-villa check-in, `/hk` app keeps staff signed in,
  balanced city-ledger transfers, and the Kamra Agent books by room and
  meal-plan name without double-booking on retries
- **2.6.12**: per-head pricing for small parties in whole-place lets,
  weekend / weekday rate guardrails, the bill screen's Void button asks for a
  reason, and admins see a banner when a newer Kamra release is out
- **2.6.9 to 2.6.10**: India-only integrations live in the India pack (Razorpay and
  Cashfree payment links, GSTR-1, **Kamra Verify** GSTIN and guest ID checks);
  privacy: guest contact details hidden from the AI provider, nightly clearing
  of old WhatsApp text and AI chats, children recorded by name and age only,
  and the guest privacy notice in **Hindi, Kannada, Tamil, Telugu, Malayalam,
  Marathi and Bengali**; vouchers stay on saved bookings; folio charges refuse
  zero, minus and unknown tax rates
- **2.6.5 to 2.6.8**: security fixes (property scope, webhooks, Guest on
  REST/Desk), deposits before arrival, room change from the GRC, checkout only
  once every bill is settled, ERPNext Company and stock working alongside Kamra
- **2.6.2 to 2.6.4**: Opera-style cashier till, folio ledger, cashier PIN,
  System Health, property time zone, AI provider presets, DPDP by design
  (erasure, access export, retention, notices)

Notes live in [`CHANGELOG.md`](CHANGELOG.md). This list is a pointer, not a
second release note. How we cut stables: [`RELEASING.md`](RELEASING.md).

---

## Why Kamra

Most hotel PMS software was built twenty years ago: per-room SaaS rent, locked-in data, bolt-on chatbots, and screens that need a week of training.

Kamra is the alternative we wanted:

| Pain with legacy PMS | With Kamra |
|---|---|
| Per-room / per-module pricing | **Free forever** (AGPL): cost doesn't scale with rooms |
| Data lock-in | **You host it**: on-prem, VPS, or Frappe Cloud |
| AI as a marketing slide | **MCP tools**: Claude (or any agent) books and audits with RBAC |
| Opaque pricing & tax | **Deterministic engine**: GST / SST / VAT / PB1 country packs in code + CI evals |
| New-hire training hell | Front desk UI a clerk can learn the same day |

**Why open source, and why now?** Most hotels can't change their PMS, connect a new tool, or let AI in, because the system is closed. AI coding agents now let a hotel's own team or a local agency build what they need, but only on an open system. Kamra gives hotels freedom to choose, ownership of their data and where it lives, privacy you can inspect, extensibility, readiness for AI agents over MCP, and no licence cost. We have nothing against other PMS; we want the next 100,000 hotels, resorts, boutiques, short-term rental companies and hosts to have an open option. Full story: [kamrapms.com/why-kamra](https://kamrapms.com/why-kamra/).

### How Kamra makes money

The software is free, and we would rather be open about the business than ask for trust. [HeyKoala](https://heykoala.ai) (Koala AI Solutions Pvt Ltd), which builds Kamra, earns from:

- **Sponsorship** by companies that rely on Kamra. It funds maintainers, releases and security work, never control of the roadmap.
- **Partner listing fees** from implementers listed for their market on [kamrapms.com/partners](https://kamrapms.com/partners/).
- **Custom implementation**: go-live, migration, customisation and annual support, on a fixed quote.
- **AI automation** for hotels with [HeyKoala](https://heykoala.ai): guest calls, WhatsApp, booking and in-stay requests.

We never charge for rooms, users, features, data export or API access. An **enterprise edition** (deeper customisation, AI built into the PMS) is on the roadmap; open-source Kamra stays open and complete. Need more customisation, or want to sponsor? [hello@kamrapms.com](mailto:hello@kamrapms.com). Details: [kamrapms.com/how-kamra-makes-money](https://kamrapms.com/how-kamra-makes-money/).

---

## What makes it different

- **Agent-ready, not agent-locked.** [MCP server](https://kamrapms.com/docs/ai-and-mcp) with **116** governed tools: role-scoped, module-gated, permission-checked, fully logged. A hotel admin picks who may use it (MCP Read or MCP Manage) and can make a property read-only for AI. Connect Claude or ChatGPT; no bundled agent to trust.
- **Bring your own key.** No AI markup or model lock-in. Optional [HeyKoala](https://heykoala.ai) for voice / WhatsApp concierge.
- **Deterministic money.** Rates, tax slabs, availability, and no-overbooking guards come from code, never from a language model.
- **Full audit trail.** Every human or AI action: who, what, why.
- **Privacy by design.** DPDP / GDPR-friendly defaults: ID verify-and-discard, erasure and access export, retention for guests and messages, children's data kept to name and age, and guest contact details kept out of AI prompts.
- **Country packs.** Tax, invoices, ID types, payment gateways and statutory reports per country. India's Razorpay, Cashfree and GSTR-1 never reach a Saudi hotel, which gets ZATCA instead.
- **Built on Frappe.** RBAC, multi-tenancy, Desk escape hatch, ERPNext-adjacent ecosystem (Company and stock work alongside Kamra).

---

## Screenshots

*From the [live demo](https://demo.kamrapms.com): open it and click around.*

| | |
|---|---|
| ![Today, front desk morning view](docs/screenshots/today.png) | ![Reservation 360](docs/screenshots/reservation-360.png) |
| **Today**: arrivals, departures, in-house, paid/due chips, room board | **Reservation 360**: billing, amend dates, check-in / out / cancel |
| ![Check-in](docs/screenshots/checkin.png) | ![Check-out](docs/screenshots/checkout.png) |
| **Check-in**: step by step, guest and IDs, who pays, room, deposit, registration card, keys | **Check-out**: the bill and why the total, late check-out, payment, invoice |
| ![Folio](docs/screenshots/invoice.png) | ![Settings](docs/screenshots/settings.png) |
| **Folio & tax invoice**: per-line GST, void, move, split, proforma, payment links | **Settings**: one searchable page per module, staff & access, integrations |
| ![Restaurant POS](docs/screenshots/pos.png) | ![Open bills](docs/screenshots/pos-bills.png) |
| **Restaurant POS**: running bills on top, menu by category, KOT, settle, F-keys | **Open bills**: every running table at a glance, bills never sent flagged |
| ![Tape chart](docs/screenshots/tape-chart.png) | ![Reports](docs/screenshots/reports.png) |
| **Tape chart**: rooms × dates, moves & stay amendments | **Reports**: occupancy, ADR, RevPAR, flash |
| ![New booking](docs/screenshots/booking-dialog.png) | ![Guest profile](docs/screenshots/guest-profile.png) |
| **New booking**: live quote, multi-room, add-ons, cancellation policy | **Guest profile**: stay strip, merge & anonymize (DPDP) |
| ![Booking Engine](docs/screenshots/booking-engine.png) | ![Dashboard](docs/screenshots/dashboard.png) |
| **Booking engine console**: gallery, policies, FAQ, SEO | **Dashboard**: occupancy, revenue, chain roll-up |
| ![Laundry](docs/screenshots/laundry.png) | ![Self check-in](docs/screenshots/checkin-id.png) |
| **Laundry**: pickup → return → folio; guest self-service | **Self check-in**: ID capture, e-sign, retention policy |

**Guest-facing booking page**: date range, **Check availability**, rates, gallery, policies, pay-at-hotel:

[![Public booking page](docs/screenshots/public-booking.png)](https://demo.kamrapms.com/book)

---

## Short-term rentals

Same PMS for **villas and multi-site STR portfolios**: sellable units (room / whole-place / package), competition groups, cleaning fees, security deposits (collect / withhold / refund), Instant or Request-to-book, and a catalog that feels like a listing site.

| | |
|---|---|
| ![STR catalog](docs/screenshots/str-catalog.png) | ![STR villas](docs/screenshots/str-villas.png) |
| **Catalog**: check-in / out + Check availability | **Places to stay**: per-villa cards & from-rates |

[![Villa listing](docs/screenshots/str-listing.png)](https://demo.kamrapms.com/book)

Live example: [demo.kamrapms.com/book](https://demo.kamrapms.com/book).

---

## Features

| Area | What you get |
|---|---|
| **Front desk** | Today board, Request-to-Book inbox, check-in flow (GRC readiness + room suggestion), tape chart, ETA/ETD, guest profiles, blacklist with logged override, per-property no-show policy |
| **Booking engine** | Direct booking + SEO console; hotels = room grid; STRs = villa catalog |
| **Short-term rentals** | Hotel vs STR property kind, sellable units, per-villa locations, whole-villa check-in as one unit, villa / room availability that blocks both ways, security deposits, Instant / Request-to-book |
| **Booking** | Multi-room / group / corporate, returning guests, add-ons, vouchers, travel agents, day-use from the booking screen, rate lock at booking |
| **Revenue** | Seasons, rate plans, guardrails, hurdle rates, overbooking allowance, cancellation & no-show policy in code |
| **Billing** | Folios, corporate routing, group masters, charge splits, deposits, End of Day (night audit checklist + saved report pack, Night Auditor role), city-ledger payments (oldest bills first), tax invoices, cashier till (FO+POS cash, PIN pad), folio ledger; India: Razorpay / Cashfree payment links and GSTR-1 |
| **F&B** | POS table map, full-screen till and kitchen pass, split bills, thermal KOT, kitchen display, inventory & recipes, room posting |
| **Operations** | Tickets + SLA, housekeeping `/hk`, guest laundry end-to-end, lost & found, banquet / events (send quote, guest response, dept checklists) |
| **Guests** | Online pre-check-in, GRC + occupant register, **editable nationality**, ID retention modes |
| **Privacy** | Erasure, access export, guest and message retention, children's data minimised, AI-prompt redaction, privacy notice in English, Arabic and seven Indian languages |
| **Messaging** | WhatsApp (Meta Cloud API): confirmations, check-in links, inbox, desk tickets |
| **Localization** | Six country packs plus a flat-tax fallback (see [Countries](#countries)); English / العربية UI |
| **Platform** | Multi-property RBAC, dark mode, property time zone, System Health, AI provider presets, CSV migration (eZee / Cloudbeds presets), eval harness in CI |

---

## Countries

The property's country picks its pack. The pack decides tax, invoice wording,
ID types, payment modes, the privacy notice and any country-only
integrations. The core PMS never mentions GST or VAT, and one country's
integrations are never offered in another.

| Country | Tax on rooms and F&B | Invoices and filings | Front desk and integrations |
|---|---|---|---|
| 🇮🇳 India | GST slab by nightly tariff (5% / 18% around ₹7,500) or fixed; F&B 5% | CGST + SGST or IGST from the GSTIN, SAC per line, amount in lakh / crore, GSTR-1 export | Aadhaar, PAN, Voter ID; UPI; Razorpay and Cashfree payment links; Form C for foreign guests; notice in 7 Indian languages |
| 🇸🇦 Saudi Arabia | VAT 15%; municipality fee as a room levy | ZATCA Phase 1: UUID, hash chain, UBL 2.1 XML and QR on every invoice and POS bill; Phase 2 groundwork | National ID, Iqama, GCC ID; Shomoos register (children's IDs kept too); Arabic UI |
| 🇦🇪 UAE | VAT 5%; municipality fee as a room levy | TRN on "Tax Invoice" | Emirates ID, GCC ID |
| 🇲🇾 Malaysia | SST 8% on rooms, 6% on F&B | Tourism Tax note for foreign guests | MyKad |
| 🇹🇭 Thailand | VAT 7% | 13-digit Tax ID; service charge as its own line | Thai ID card |
| 🇮🇩 Indonesia | Regional hotel tax (PB1 / PBJT) 10% by default | | KTP, KITAS |
| Anywhere else | One flat rate from property settings | Plain tax invoice | Passport, national ID |

Rates are defaults. The operator can change them on the property or room type
when the law changes. A new country is one Python module behind the
`kamra_localization` hook; see [Country packs](CONTRIBUTING.md#country-packs).

---

## How it's built

```mermaid
flowchart LR
  desk["Front desk SPA<br/>React + Vite"] --> api
  book["Booking engine<br/>/book"] --> api
  hk["Housekeeping<br/>/hk"] --> api
  agent["Claude / any MCP client"] --> mcp["MCP server<br/>116 tools"] --> api
  api["Governed API<br/>RBAC · property scope · audit log"] --> core["PMS core<br/>pricing · folios · night audit"]
  core --> pack["Country pack<br/>tax · invoices · integrations"]
  core --> db[("Frappe v16<br/>MariaDB")]
```

- **One API for everyone.** The UI, the booking engine, the housekeeping app
  and AI agents all call the same whitelisted methods. Each call checks the
  user's role and property, and every change is logged.
- **Money is code.** Quotes, tax, deposits and availability are computed in
  Python with `Decimal`. An AI agent can ask for a quote or post a charge, but
  never invents a number.
- **Evals in CI.** `kamra/scripts/eval_harness.py` runs 88 checks of real
  hotel flows (double booking, split folios, tax slabs, POS, banquets,
  privacy, every country pack, property scope) on a fresh site for every PR,
  alongside Semgrep, CodeQL and a fresh-install check.

| Path | What lives there |
|---|---|
| `kamra/` | Frappe app: doctypes, `api.py` and the domain modules (folio, pricing, cashier, POS, housekeeping, banquet, privacy…) |
| `kamra/localization/` | Country packs (`india/`, `saudi.py`, `uae.py`…) and the `generic` fallback |
| `kamra/zatca/` | Saudi e-invoicing: UBL XML, hash chain, TLV QR |
| `kamra/mcp_tools.py`, `mcp/` | MCP tool layer (hosted at `/mcp`) and the stdio server |
| `kamra/scripts/` | Eval harness, demo seed data, migrations from other PMSs |
| `frontend/` | React SPA. The build is committed to `kamra/public/frontend`, so `bench get-app` needs no Node |
| `docs-site/` | Source of [kamrapms.com/docs](https://kamrapms.com/docs/), including the generated API and MCP references |
| `deploy/` | Self-host installer and one-click cloud images |

---

## Documentation & API

Full manual: **[kamrapms.com/docs](https://kamrapms.com/docs/)** (quickstart, self-hosting, features, user guide, AI/MCP, FAQ).

Going live? Use the **[go-live checklist](https://kamrapms.com/docs/go-live)**.

### REST & agents

Kamra exposes **267 REST endpoints**, the same governed layer the UI and AI use:

- [REST API reference](https://kamrapms.com/docs/api-reference)
- [Postman collection](https://kamrapms.com/docs/kamra.postman_collection.json)
- [MCP tool reference](https://kamrapms.com/docs/mcp-tools)

```bash
curl -X POST https://<your-kamra>/api/method/kamra.api.get_quote \
  -H "Authorization: token <api_key>:<api_secret>" \
  -H "Content-Type: application/json" \
  -d '{"property":"Your Property","room_type":"Your Property-DLX",
       "check_in_date":"2026-08-01","check_out_date":"2026-08-03"}'
```

In-repo: [`docs/`](docs/) · [user guide](docs/user-guide.md) · [AI & API](docs/ai-and-api.md) · [self-hosting](docs/self-hosting.md) · [dev notes](docs-dev.md) · [branding](branding/README.md)

---

## Install

| Method | For | How |
| --- | --- | --- |
| **Hostinger VPS** | Cheapest self-host (India / SEA) | Buy KVM 2 via the [Kamra referral link](https://www.hostinger.com/in?REFERRALCODE=kamrapms) (**20% off**, or coupon `KAMRAPMS`; it helps keep Kamra afloat), paste the Docker one-liner below · [guide](https://kamrapms.com/docs/self-hosting/hostinger) |
| **Docker on any VPS** | DigitalOcean, Linode, AWS, your own box | One-liner below · [quickstart](https://kamrapms.com/docs/quickstart) |
| **Bench** | Existing Frappe / ERPNext benches | Commands below · [guide](https://kamrapms.com/docs/self-hosting/bench) |
| **Frappe Cloud Marketplace** | Managed Frappe hosting | [Install Kamra](https://cloud.frappe.io/marketplace/apps/kamra) on a private bench |

**Docker:**

```bash
curl -fsSL https://raw.githubusercontent.com/Kamra-PMS/kamra-pms/main/deploy/install.sh | bash
```

Three prompts: site domain, admin email, admin password. By default it
builds a local `kamra:local` image, 20 to 45 minutes the first time; 2 vCPU /
4 GB minimum (swap is added automatically under 8 GB). Then open
`/kamra/setup`. Update later with `sudo /opt/kamra/install.sh update`
(takes a `bench backup --with-files` first and stops if that fails).
Details: [deploy/](deploy/).

**Prebuilt image:** releases are also published as
`ghcr.io/kamra-pms/kamra` with tags `stable` (newest release), `vX.Y.Z` (pin
these in production) and `nightly` (testing). With registry access (the
package is not public yet: `docker login ghcr.io` with a `read:packages`
token), `KAMRA_PULL=1` makes the installer pull and pin it instead of
building (a few minutes) and
[`deploy/compose/quickstart.yaml`](deploy/compose/quickstart.yaml) runs it
on a laptop for evaluation. The image holds only public code (Frappe,
payments, Kamra); site data and secrets stay in volumes and env on your
server.

**Bench / Frappe Cloud:**

```bash
bench get-app payments
bench get-app kamra https://github.com/Kamra-PMS/kamra-pms --branch main
bench --site your-site install-app kamra
```

After install: product UI at **`/kamra`**, booking at **`/book`**, housekeeping at **`/hk`**. Desk remains at `/app`. Sign in as **Administrator**, open `/kamra/setup`, create your property, add staff.

| Channel | Branch / tag | Use for |
|---|---|---|
| **Stable** | `main` / `vX.Y.Z` | Production, [Frappe Cloud Marketplace](https://cloud.frappe.io/marketplace/apps/kamra), [demo](https://demo.kamrapms.com) |
| **Nightly** | `develop` | Previews (nightly.kamrapms.com) |

Production installs should use `--branch main` (`develop` is the default GitHub branch for contributors). Releases are SemVer with a **patch-first** cadence; see [`RELEASING.md`](RELEASING.md) and [`CHANGELOG.md`](CHANGELOG.md).

---

## Quickstart (development)

```bash
bench init --frappe-branch v16.25.0 frappe-bench && cd frappe-bench
bench get-app payments
bench get-app kamra https://github.com/Kamra-PMS/kamra-pms
bench new-site kamra.localhost --admin-password admin
bench --site kamra.localhost install-app kamra
bench serve --port 8000
cd apps/kamra/frontend && npm install && npm run dev   # hot-reload UI on :5173
```

Rebuild the SPA with `npm run build` at the app root (emits `kamra/public/frontend`). Seed demo data: `bench --site … execute kamra.scripts.seed_demo.execute`. Details: [docs-dev.md](docs-dev.md).

Connect Claude (hosted MCP, no local Python):

```bash
# Kamra Agent → Connect your AI → Connect Claude, or:
claude mcp add --transport http kamra https://pms.yourhotel.com/mcp
```

No public HTTPS (air-gapped or localhost)? Run the stdio server in
[`mcp/kamra_mcp.py`](mcp/kamra_mcp.py) instead; it serves the same tools.

---

## Contributing

Issues and PRs are welcome. The short version of
[CONTRIBUTING.md](CONTRIBUTING.md):

- Branch from **`develop`** and open the PR against it. `main` only moves on a release.
- Use [Conventional Commits](https://www.conventionalcommits.org/) (`fix:`,
  `feat:`, `docs:`). release-please writes the changelog from them.
- Changed the UI? Run `npm run build` and commit `kamra/public/frontend` with your change.
- Changed Python? Run the eval harness on a dev site and add a check for the
  behaviour you changed:

  ```bash
  bench --site kamra.localhost console
  >>> from kamra.scripts.eval_harness import execute; execute()
  ```

- Put anything country-specific (a tax, an ID type, a gateway) in that
  country's pack, not the core.

Every merged PR and every issue that shapes a feature is credited in the
release notes and below.

---

## Who it's for

- **Hotel / villa operators**: own the software and the data; costs don't grow with room count; AI is optional, not a ransom.
- **IT & integrators**: Python (Frappe) + React, documented REST + MCP, RBAC, audit trails, CI eval suite. Fork and extend.
- **Builders of hospitality AI**: a real PMS tool surface, not a demo chatbot API.

---

## License & contributors

**AGPL-3.0**: free forever. Anyone offering Kamra as a hosted service must share modifications back.

Contributions welcome: see [CONTRIBUTING.md](CONTRIBUTING.md). The full list lives on the docs site: [Contributors](https://kamrapms.com/docs/contributors).

**Code**

- [@Kruthikagowda12](https://github.com/Kruthikagowda12): the AioSell channel-manager adapter and its fixes ([#40](https://github.com/Kamra-PMS/kamra-pms/pull/40), [#46](https://github.com/Kamra-PMS/kamra-pms/pull/46), [#52](https://github.com/Kamra-PMS/kamra-pms/pull/52)), housekeeping proof media and room swap / upgrade ([#74](https://github.com/Kamra-PMS/kamra-pms/pull/74)), phone validation ([#69](https://github.com/Kamra-PMS/kamra-pms/pull/69)), season scoping ([#80](https://github.com/Kamra-PMS/kamra-pms/pull/80)), property / booking flow work ([#22](https://github.com/Kamra-PMS/kamra-pms/pull/22)), and per-head small-group rates with weekend / weekday guardrails ([#162](https://github.com/Kamra-PMS/kamra-pms/pull/162))
- [@Mohammed-Muneef](https://github.com/Mohammed-Muneef): laundry, kitchen display v2, inventory & recipes, menu import, ID-document hardening
- [@faresalslahi-collab](https://github.com/faresalslahi-collab): booking guest and room summary ([#83](https://github.com/Kamra-PMS/kamra-pms/pull/83))
- [@ShaikhAmerPasha](https://github.com/ShaikhAmerPasha): saved bookings keep their voucher after it expires or hits its limit ([#142](https://github.com/Kamra-PMS/kamra-pms/issues/142), [#143](https://github.com/Kamra-PMS/kamra-pms/pull/143)), folio charges refuse zero or minus amounts and unknown tax rates ([#146](https://github.com/Kamra-PMS/kamra-pms/issues/146), [#147](https://github.com/Kamra-PMS/kamra-pms/pull/147)), and the bill screen's Void button, which now asks for a reason ([#160](https://github.com/Kamra-PMS/kamra-pms/issues/160), [#161](https://github.com/Kamra-PMS/kamra-pms/pull/161))
- [@ernestoruiz89](https://github.com/ernestoruiz89): Spanish localization and menu navigation fixes (fork [#320](https://github.com/Kamra-PMS/kamra-pms/pull/320), landed via [#324](https://github.com/Kamra-PMS/kamra-pms/pull/324), included in 2.6.21), international guest phone prefixes ([#345](https://github.com/Kamra-PMS/kamra-pms/pull/345), [#360](https://github.com/Kamra-PMS/kamra-pms/pull/360)), and the chat assistant using the property's currency ([#368](https://github.com/Kamra-PMS/kamra-pms/pull/368), 2.6.22)
- [@SandroG1977](https://github.com/SandroG1977): Brazil country pack: ISS, BRL, CNPJ/CPF, NFS-e ([#378](https://github.com/Kamra-PMS/kamra-pms/pull/378)); Portuguese (pt-BR) staff UI ([#377](https://github.com/Kamra-PMS/kamra-pms/pull/377), landed via [#383](https://github.com/Kamra-PMS/kamra-pms/pull/383))

**Docs and guides**

- [@caseylee-TC](https://github.com/caseylee-TC): [Write a country pack](https://kamrapms.com/docs/write-a-country-pack) tutorial ([#362](https://github.com/Kamra-PMS/kamra-pms/pull/362), fixes [#258](https://github.com/Kamra-PMS/kamra-pms/issues/258))

**Hotels and users who shaped it through issues**

- [@lhertig](https://github.com/lhertig): folio payments in the property currency ([#341](https://github.com/Kamra-PMS/kamra-pms/issues/341)), `max_total_occupants` on mixed adult/child bookings ([#342](https://github.com/Kamra-PMS/kamra-pms/issues/342)), pre-arrival advance refunds releasing Deposit and reducing `advance_paid` ([#343](https://github.com/Kamra-PMS/kamra-pms/issues/343)), and concurrent booking `tabSeries` deadlock retries ([#344](https://github.com/Kamra-PMS/kamra-pms/issues/344))
- [@faresalslahi-collab](https://github.com/faresalslahi-collab) (Sarawat Park Hotel & Resort): the one-screen walk-in ([#97](https://github.com/Kamra-PMS/kamra-pms/issues/97)), which led to the Saudi Arabia pack and ZATCA, Arab-world dial codes ([#98](https://github.com/Kamra-PMS/kamra-pms/issues/98)), and Kamra's kitchen ledger clashing with ERPNext stock on a shared site ([#131](https://github.com/Kamra-PMS/kamra-pms/issues/131))
- [@atomic-glitch](https://github.com/atomic-glitch): the housekeeping Room Board and role checks ([#99](https://github.com/Kamra-PMS/kamra-pms/issues/99)), room change from the reservation and GRC ([#113](https://github.com/Kamra-PMS/kamra-pms/issues/113)), and deposits before arrival ([#114](https://github.com/Kamra-PMS/kamra-pms/issues/114))
- [@ali-qa-sudo](https://github.com/ali-qa-sudo): role-aware Walk-in / New booking buttons ([#120](https://github.com/Kamra-PMS/kamra-pms/issues/120))
- [@omar99elnemr](https://github.com/omar99elnemr): checkout refused until the bill is settled ([#132](https://github.com/Kamra-PMS/kamra-pms/issues/132))
- [@Syzygy2048](https://github.com/Syzygy2048): current OpenAI models in the assistant ([#23](https://github.com/Kamra-PMS/kamra-pms/issues/23))

**Security**

- **[@archnexus707](https://github.com/archnexus707)**: found and responsibly disclosed cross-property access ([GHSA-6cr2](https://github.com/Kamra-PMS/kamra-pms/security/advisories/GHSA-6cr2-jm8f-6jrx)), fixed in 2.6.5
- [@kta1kri](https://github.com/kta1kri): unauthenticated webhooks ([GHSA-5hcx](https://github.com/Kamra-PMS/kamra-pms/security/advisories/GHSA-5hcx-h257-qr5j)) and an independent report of GHSA-6cr2, both fixed in 2.6.5

### Links

- **Demo:** [demo.kamrapms.com](https://demo.kamrapms.com)
- **Docs:** [kamrapms.com/docs](https://kamrapms.com/docs/)
- **Issues:** [github.com/Kamra-PMS/kamra-pms](https://github.com/Kamra-PMS/kamra-pms)
- **Email:** [hello@kamrapms.com](mailto:hello@kamrapms.com)

Built by [HeyKoala](https://heykoala.ai).

---

*Kamra means "room". The door in our logo is open on purpose.*
