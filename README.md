<p align="center">
  <img src="branding/png/kamra-mark-512.png" width="96" alt="Kamra — open-source hotel PMS" />
</p>

<h1 align="center">Kamra PMS</h1>

<p align="center">
  <b>Open-source hotel &amp; short-term rental PMS</b> — front desk, booking engine,<br/>
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
> Tap any role to sign in (credentials are on the page). Guest booking: [/book](https://demo.kamrapms.com/book) · Housekeeping app: [/kamra/hk](https://demo.kamrapms.com/kamra/hk) · Live villa catalog: [ewa.kamrapms.com/book](https://ewa.kamrapms.com/kamra/book)

**Kamra** is a full **property management system (PMS)** for hotels, resorts, and **short-term rentals / villas**. It runs on **Frappe** (the framework behind ERPNext), is **AGPL-3.0**, and is built so humans *and* AI agents share the same governed APIs — booking, check-in, folios, night audit, pricing — with deterministic money (never from an LLM).

---

## Contents

- [Why Kamra](#why-kamra)
- [What makes it different](#what-makes-it-different)
- [Screenshots](#screenshots)
- [Short-term rentals](#short-term-rentals)
- [Features](#features)
- [Documentation & API](#documentation--api)
- [Install](#install)
- [Quickstart (development)](#quickstart-development)
- [Who it's for](#who-its-for)
- [License & contributors](#license--contributors)

---

## Why Kamra

Most hotel PMS software was built twenty years ago: per-room SaaS rent, locked-in data, bolt-on chatbots, and screens that need a week of training.

Kamra is the alternative we wanted:

| Pain with legacy PMS | With Kamra |
|---|---|
| Per-room / per-module pricing | **Free forever** (AGPL) — cost doesn't scale with rooms |
| Data lock-in | **You host it** — on-prem, VPS, or Frappe Cloud |
| AI as a marketing slide | **MCP tools** — Claude (or any agent) books and audits with RBAC |
| Opaque pricing & tax | **Deterministic engine** — GST / SST / VAT packs in code + CI evals |
| New-hire training hell | Front desk UI a clerk can learn the same day |

---

## What makes it different

- **Agent-ready, not agent-locked.** [MCP server](https://kamrapms.com/docs/ai-and-mcp) with 50+ governed tools — role-scoped, permission-checked, fully logged. Connect Claude; no bundled agent to trust.
- **Bring your own key.** No AI markup or model lock-in. Optional [HeyKoala](https://heykoala.ai) for voice / WhatsApp concierge.
- **Deterministic money.** Rates, tax slabs, availability, and no-overbooking guards come from code — never from a language model.
- **Full audit trail.** Every human or AI action: who, what, why.
- **Built on Frappe.** RBAC, multi-tenancy, Desk escape hatch, [frappe/payments](https://github.com/frappe/payments) gateways, ERPNext-adjacent ecosystem.

---

## Screenshots

*From the [live demo](https://demo.kamrapms.com) — open it and click around.*

| | |
|---|---|
| ![Today — front desk morning view](docs/screenshots/today.png) | ![Reservation 360](docs/screenshots/reservation-360.png) |
| **Today** — arrivals, departures, in-house, paid/due chips, room board | **Reservation 360** — billing, amend dates, check-in / out / cancel |
| ![Tape chart](docs/screenshots/tape-chart.png) | ![Reports](docs/screenshots/reports.png) |
| **Tape chart** — rooms × dates, moves & stay amendments | **Reports** — occupancy, ADR, RevPAR, flash |
| ![New booking](docs/screenshots/booking-dialog.png) | ![Guest profile](docs/screenshots/guest-profile.png) |
| **New booking** — live quote, multi-room, add-ons, cancellation policy | **Guest profile** — stay strip, merge & anonymize (DPDP) |
| ![GST invoice](docs/screenshots/invoice.png) | ![Booking Engine](docs/screenshots/booking-engine.png) |
| **Folio & tax invoice** — per-line GST, splits, payment links | **Booking engine console** — gallery, policies, FAQ, SEO |
| ![Restaurant POS](docs/screenshots/pos.png) | ![Dashboard](docs/screenshots/dashboard.png) |
| **Restaurant POS** — table map, KOT / bill print, F-keys | **Dashboard** — occupancy, revenue, chain roll-up |
| ![Laundry](docs/screenshots/laundry.png) | ![Self check-in](docs/screenshots/checkin-id.png) |
| **Laundry** — pickup → return → folio; guest self-service | **Self check-in** — ID capture, e-sign, retention policy |

**Guest-facing booking page** — date range, **Check availability**, rates, gallery, policies, pay-at-hotel:

[![Public booking page](docs/screenshots/public-booking.png)](https://demo.kamrapms.com/book)

---

## Short-term rentals

Same PMS for **villas and multi-site STR portfolios**: sellable units (room / whole-place / package), competition groups, cleaning fees & deposits, Instant or Request-to-book, and a catalog that feels like a listing site.

| | |
|---|---|
| ![STR catalog](docs/screenshots/str-catalog.png) | ![STR villas](docs/screenshots/str-villas.png) |
| **Catalog** — check-in / out + Check availability | **Places to stay** — per-villa cards & from-rates |

[![Villa listing](docs/screenshots/str-listing.png)](https://ewa.kamrapms.com/kamra/book)

Live example: [ewa.kamrapms.com/book](https://ewa.kamrapms.com/kamra/book).

---

## Features

| Area | What you get |
|---|---|
| **Front desk** | Today board, check-in flow (GRC readiness + room suggestion), tape chart, ETA/ETD, guest profiles, blacklist |
| **Booking engine** | Direct booking + SEO console; hotels = room grid; STRs = villa catalog |
| **Short-term rentals** | Hotel vs STR property kind, sellable units, per-villa locations, Instant / Request-to-book |
| **Booking** | Multi-room / group / corporate, returning guests, add-ons, vouchers, travel agents, day-use |
| **Revenue** | Seasons, rate plans, guardrails, hurdle rates, overbooking allowance, cancellation & no-show policy in code |
| **Billing** | Folios, corporate routing, group masters, charge splits, night audit, tax invoices, GSTR-1, payment links |
| **F&B** | POS table map, split bills, thermal KOT, kitchen display, inventory & recipes, QR ordering, room posting |
| **Operations** | Tickets + SLA, housekeeping `/hk`, guest laundry end-to-end, lost & found, banquet / events |
| **Guests** | Online pre-check-in, GRC + occupant register, **editable nationality**, ID retention modes |
| **Messaging** | WhatsApp (Meta Cloud API) — confirmations, check-in links, inbox, desk tickets |
| **Localization** | India GST, Indonesia PB1, Thailand VAT, Malaysia SST, UAE VAT — currency & locales follow the pack |
| **Platform** | Multi-property RBAC, dark mode, CSV migration (eZee / Cloudbeds presets), eval harness in CI |

---

## Documentation & API

Full manual: **[kamrapms.com/docs](https://kamrapms.com/docs/)** — quickstart, self-hosting, features, user guide, AI/MCP, FAQ.

Going live? Use the **[go-live checklist](https://kamrapms.com/docs/go-live)**.

### REST & agents

Kamra exposes **170+ REST endpoints** — the same governed layer the UI and AI use:

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

```bash
bench get-app payments
bench get-app kamra https://github.com/Kamra-PMS/kamra-pms --branch main
bench --site your-site install-app kamra
```

After install: product UI at **`/kamra`**, booking at **`/book`**, housekeeping at **`/hk`**. Desk remains at `/app`. Sign in as **Administrator**, open `/kamra/setup`, create your property, add staff.

| Channel | Branch / tag | Use for |
|---|---|---|
| **Stable** | `main` / `vX.Y.Z` | Production, [Frappe Cloud Marketplace](https://cloud.frappe.io/marketplace/apps/kamra), [demo](https://demo.kamrapms.com), `ghcr.io/kamra-pms/kamra:latest` |
| **Nightly** | `develop` | Previews, `ghcr.io/kamra-pms/kamra:nightly` |

Production installs should use `--branch main` (`develop` is the default GitHub branch for contributors). Releases are SemVer with a **patch-first** cadence — see [`RELEASING.md`](RELEASING.md) and [`CHANGELOG.md`](CHANGELOG.md).

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

Connect Claude (hosted MCP — no local Python):

```bash
# Kamra Agent → Connect your AI → Connect Claude, or:
claude mcp add --transport http kamra https://pms.yourhotel.com/mcp
```

---

## Who it's for

- **Hotel / villa operators** — own the software and the data; costs don't grow with room count; AI is optional, not a ransom.
- **IT & integrators** — Python (Frappe) + React, documented REST + MCP, RBAC, audit trails, CI eval suite. Fork and extend.
- **Builders of hospitality AI** — a real PMS tool surface, not a demo chatbot API.

---

## License & contributors

**AGPL-3.0** — free forever. Anyone offering Kamra as a hosted service must share modifications back.

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Thanks to [@Mohammed-Muneef](https://github.com/Mohammed-Muneef) (laundry, kitchen display v2, inventory & recipes, menu import, ID-document hardening).

### Links

- **Demo:** [demo.kamrapms.com](https://demo.kamrapms.com)
- **Docs:** [kamrapms.com/docs](https://kamrapms.com/docs/)
- **Issues:** [github.com/Kamra-PMS/kamra-pms](https://github.com/Kamra-PMS/kamra-pms)
- **Email:** [hello@kamrapms.com](mailto:hello@kamrapms.com)

Built by [HeyKoala](https://heykoala.ai).

---

*Kamra means "room". The door in our logo is open on purpose.*
