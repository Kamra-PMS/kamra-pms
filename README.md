# Kamra — local development

Kamra is an open-source, AI-native hotel PMS built on Frappe v16.
This workspace holds the local dev environment (Docker) and the `kamra` app.

## Layout

```
agenticpms/
└── frappe_docker/                  # dev environment (cloned from frappe/frappe_docker)
    └── development/frappe-bench/
        └── apps/kamra/             # THE APP — schema, API, frontend
            ├── kamra/kamra/doctype/    # Property, Room Type, Room, Rate Plan,
            │                           # Guest, Reservation, Housekeeping Task,
            │                           # Agent Action Log
            ├── kamra/api.py            # whitelisted front-desk API (future agent tools)
            ├── kamra/savings.py        # savings-ledger helper
            ├── kamra/scripts/          # bootstrap_schema.py, seed_demo.py
            └── frontend/               # React 19 + Tailwind 4 + shadcn-style UI
```

## Start everything

```bash
# 1. containers (MariaDB, Redis, bench)
cd frappe_docker
docker compose -f .devcontainer/docker-compose.yml -p kamra-dev up -d

# 2. Frappe web server (port 8000)
docker exec -d -w /workspace/development/frappe-bench kamra-dev-frappe-1 \
  bash -c "bench serve --port 8000 >> /tmp/bench-serve.log 2>&1"

# 3. front-desk UI (port 5173)
cd development/frappe-bench/apps/kamra/frontend
npm run dev
```

| Surface | URL | Login |
|---|---|---|
| Front-desk console (React) | http://localhost:5173 | login screen (demo accounts below, one-tap buttons) |
| Frappe Desk (admin) | http://kamra.localhost:8000 | Administrator / admin |

### Demo accounts (seeded via `kamra.scripts.seed_users.execute`)

| User | Password | Role | Sees (in the React UI) |
|---|---|---|---|
| admin@kamra.local | KamraAdmin1! | System Manager | everything |
| frontdesk@kamra.local | KamraDesk1! | Front Desk | Front Desk, Inventory, Ops |
| revenue@kamra.local | KamraRev1! | Revenue Manager (+Front Desk) | + Revenue (rates, seasons, vouchers, meal plans) |
| finance@kamra.local | KamraFin1! | Finance | Finance (billing, corporate) |

### UI navigation (React app, :5173)

Sidebar modules → screens:
- **Front Desk**: Today (dashboard), Calendar (14-day availability), Reservations
- **Inventory**: Rooms, Room Types (full CRUD)
- **Revenue**: Rate Plans, Seasons, Vouchers, Meal Plans (full CRUD)
- **Finance**: Billing (reservation totals; folios/GST next), Corporate accounts
- **Ops**: Housekeeping tasks

Menu groups are filtered by the logged-in user's Frappe roles (`kamra.api.whoami`);
the same roles are enforced server-side via Custom DocPerms.

## Useful commands

```bash
# shell into the bench
docker exec -it -w /workspace/development/frappe-bench kamra-dev-frappe-1 bash

# re-run schema bootstrap (idempotent)
bench --site kamra.localhost execute kamra.scripts.bootstrap_schema.execute

# seed the demo hotel (idempotent)
bench --site kamra.localhost execute kamra.scripts.seed_demo.execute

# migrate after editing doctype JSON
bench --site kamra.localhost migrate
```

## What works in v7 (multi-property)

- **Property switcher** in the header (shows when the user can access >1
  property); switching remounts all screens with that property's data;
  choice persists in localStorage
- Second demo property seeded: **Kamra Beach House** (Gokarna) with its own
  room types, rooms, meal plan
- **Per-user property scoping** via native Frappe User Permissions:
  frontdesk@kamra.local is pinned to Kamra Demo Palace and can't see or
  query the Beach House; admins see the whole portfolio
- `my_properties` API returns only permitted properties

## What works in v6 (public booking engine)

- **Guest-facing booking page at http://localhost:5173/book** — no login:
  hero with property photo/category/city, Google Reviews + TripAdvisor
  links, amenity chips, date/guest search with live totals per room type
  (taxes included), room cards with photo galleries, bed/view/amenity
  details, scarcity hints ("only 2 left"), book-and-pay-at-hotel flow
- Room Type gained a **Media gallery** child table (images/videos);
  Property gained showcase fields (description, hero image, category,
  review URLs, public amenities, booking_engine_enabled)
- **SEO**: stay state lives in the URL
  (`/book/2026-08-10/2026-08-12/2/0?utm_source=…` — shareable, UTM
  preserved), dynamic title + meta description, canonical link, and
  schema.org **Hotel JSON-LD** with per-room-type offers. Property has a
  **Logo URL** slot (monogram fallback) for hotel branding.
  Production note: for crawlers that don't run JS, add prerender/SSR later.
- Public API (`kamra/public_api.py`, the only allow_guest surface):
  `showcase`, `search_stay`, `book` (rate-limited 10/hr/IP; bookings write
  through the governed agent user; source=Website)

## What works in v5 (billing correctness + guardrails + briefing)

- **Rate Guardrails** (Revenue → Guardrails): owner floor/ceiling; the
  `set_room_rate` API/MCP tool cannot price outside them
- **Owner briefing** API/MCP tool: occupancy, ADR/RevPAR from posted
  charges, arrivals/departures, tickets, 7-day availability
- **GST slab auto-switch** (Property → GST Rules): nightly tariff picks the
  slab (≤₹7,500 → 5%, above → 18%, configurable); per-night, so peak
  pricing can move a room across slabs mid-stay
- **Tax-inclusive rates** (Property.rates_include_tax): engine back-computes
  taxable value from gross prices
- **Split / transfer folios**: multiple folios per stay (Guest/Extra/Company),
  move charges between them in the Folio screen — the 70/30 corporate split
- **Day-use stays**: same-day check-in/out, bills one date, occupies the
  room for overlap purposes
- **Guest blacklist**: flag on Guest; new bookings for flagged guests are
  refused with the reason

## What works in v4 (MCP — connect Claude to the PMS)

- **MCP server** at `apps/kamra/mcp/kamra_mcp.py` — 14 tools (availability,
  quote, create_booking, check-in/out, guest lookup/journey, tickets,
  folio charges, night audit). Auth: dedicated `agent@kamra.local` user
  with API keys and the scoped **Kamra Agent** role — the AI is a user,
  every action permission-checked and audit-logged.
- Regenerate agent keys: `kamra.scripts.seed_rbac_v2.execute` (prints them).
- Connect Claude Code:
  `claude mcp add kamra -e KAMRA_URL=... -e KAMRA_API_KEY=... -e KAMRA_API_SECRET=... -- <app>/mcp/.venv/bin/python <app>/mcp/kamra_mcp.py`

### RBAC

| Role | Meaning |
|---|---|
| System Manager | IT/platform admin — everything incl. schema |
| Hotel Admin | Owner/GM — full rights on all Kamra doctypes |
| Front Desk / Revenue Manager / Finance | Scoped module rights |
| Kamra Agent | What AI agents get — ops rights, no desk access |

Note (Frappe behavior): Custom DocPerm rows REPLACE built-in doctype perms,
so every role incl. System Manager needs explicit rows — handled by
`fix_perms_fields.py` + `seed_rbac_v2.py`.

## What works in v3 (service tickets)

- **Service Ticket** doctype (PRD FR-42): category, priority→SLA
  (Urgent 15m / High 30m / Medium 1h / Low 4h), auto `due_by`, breach
  tracking on resolve, source (Manual/AI Agent/Voice/WhatsApp/QR)
- Maintenance ticket moved to In Progress auto-creates a Housekeeping
  Maintenance task for the room
- AI-sourced tickets log savings minutes; APIs: `create_ticket` (the future
  agent tool), `tickets_list` (with overdue flag), `advance_ticket`
- **Ops → Tickets** screen: queue with overdue highlighting, quick
  Start/Resolve actions, new-ticket dialog

## What works in v2 (folio, night audit, GST)

- **Folio per stay** — opens automatically at check-in; charge lines
  (room/meals/F&B/minibar/…) each carry their own GST rate; payments;
  running balance. `kamra/folio.py`
- **Night audit** — manual button on Billing or 3 AM cron
  (`hooks.scheduler_events`): posts the night's room+meal charges for all
  in-house guests, opens missing folios, flags no-shows. Idempotent per date.
- **Checkout** back-fills any unposted nights, then folio can be settled and
  **closed → GST invoice number** (INV-YYYY-#####).
- **Billing UI** — folio list w/ balances, folio detail with post-charge /
  record-payment forms, multi-rate GST summary (CGST/SGST split) and a
  **printable tax invoice** (browser print, print CSS included).
- `gstr1_rows` API — invoice-level export rows (GSTR-1-lite; IRN/e-invoicing
  integration still pending).

## What works in v1 (booking layer)

- **Availability calendar** — 14-day grid per room type (available count +
  season-adjusted rate), click a cell to book
- **Booking dialog** — guest dedup by phone, meal plan, live quote
  (room + meals − voucher + GST), auto room assignment
- **Meal Plans** (EP/CP/MAP/AP), **Seasons** (percent/amount/absolute rate
  adjustments, priority), **Discount Vouchers** (percent/amount, validity,
  min-nights, max-uses with usage tracking)
- **Corporate accounts** (Company doctype, negotiated rate plan, credit flag)
  and **Group Bookings** (`create_group_booking` → N reservations under one
  GRP parent)
- Pricing engine in `kamra/pricing.py` — deterministic; occupancy pricing →
  seasons → rate plan → meals → voucher → tax
- Scripts: `bootstrap_v1.py`, `seed_v1.py` (note: run via `bench console`,
  `bench execute` has an eval quirk in v16)

## What works in v0

- Rooms, room types with occupancy-based pricing fields, rate plans, guests
- Reservations with a **double-booking guard** (overlap check on every save)
- Check-in/check-out automation: room occupancy flips, checkout auto-creates
  a Housekeeping Task, actual times stamped
- Housekeeping status loop: task Done/Verified → room Clean/Inspected
- **Agent Action Log** — the savings ledger; every automated action can record
  minutes saved (powers the hours-saved counter in the UI)
- Front-desk console: today's arrivals/departures with one-click check-in/out,
  in-house list, click-to-update room board, 30-day hours-saved counter

## Next

- Folio + line-item charges, night audit, GST invoicing (india-compliance)
- MCP tool layer over `kamra/api.py` for AI agents
- Tape chart (drag-drop reservation calendar), housekeeping mobile PWA
- ERPNext integration for accounting
