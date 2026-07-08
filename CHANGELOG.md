# Changelog

All notable changes to Kamra PMS are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/) — MAJOR for anything that breaks an
existing install on upgrade (removed doctypes, removed API endpoints),
MINOR for new features, PATCH for fixes.

## [2.0.0] - 2026-07-08

### Added
- Booking Engine: a management app for the direct-booking page — hotel
  profile with driving directions and an embedded map, a photo gallery,
  house/pets/children/extra-bed policies, an FAQ list, and SEO fields (meta
  title/description, OG image, page slug). The public booking page now
  renders a gallery, a Policies & Rules card, a Location & Directions card,
  and an FAQ accordion, and its `<title>`/meta description/OG image come from
  the SEO fields when set.
- Revenue Reports: budget vs. actual with attainment %, and a contribution
  analysis by source / company / travel agent.
- Accounting export: download closed invoices as Tally, Zoho Books or ERPNext
  import files, with tax columns driven by the property's localization pack.
- Tape chart: room-type grouping and filter, guest-type badges (VIP,
  Corporate, Group, OTA), and an Hourly view for day-use bookings with
  planned check-in/out times.
- Preference-aware room allocation suggestions ("Auto-assign arrivals") on
  the tape chart, matching guest requests to room attributes.
- Self check-in now captures consent and an e-signature, producing a signed,
  paperless Guest Registration Card.
- A Void action on open folio charges — correct a mis-posted bill without
  split/transfer/allowance gymnastics.
- Localization seam: country packs decide tax rates and invoice fields;
  India ships as the reference pack.
- Kamra as an app suite (Front Desk, Housekeeping, Operations, Events &
  Groups, Revenue, Finance, Admin) with an app switcher and launcher.
- Marketplace: connect HeyKoala (voice/WhatsApp), bring your own AI
  (Claude over MCP, or an OpenAI key for the in-app Copilot chat).
- Realtime updates: Tape Chart, Today and the room board update live.
- Centralized cross-navigation: every reservation, company and group links
  to its billing, folios and guests.
- List screens: search, filter, pagination, date range, CSV export and a
  column picker across every resource list.
- Cashier PIN on money actions (per-user, property-togglable).
- Folio finance: allowances, part-settlement for long stays, and an invoice
  cancellation register.
- MICE: room blocks, pickup-aware inventory holds, Group Rooms Control.
- Copilot: streaming responses, markdown rendering, and a Connect tab for
  bringing your own Claude via MCP.
- Centralized auth (`/login` route, consistent 401/403 handling).

### Changed
- **Kamra is fully open** — removed all "Premium" tier labeling from the
  app switcher, launcher and marketplace. Every app ships included.
- The Copilot is a plain chat over governed tools, not a bundle of named
  personas.
- Marketplace AI section reframed as "Bring your own AI" (Claude/MCP, OpenAI
  key) and "AI on your phone lines" (HeyKoala).
- Food & beverage tax on posted charges is now computed server-side from the
  localization pack, rather than trusting the caller's supplied rate.

### Removed (⚠️ breaking)
- **Native seeded agents** (NOVA, IRA, TARA, ORION, MAYA) and the underlying
  `Agent`, `Agent Autonomy Rule`, `Agent Tool` and `Pending Agent Action`
  doctypes, the autonomy/approval gate, and the Approvals inbox.
  Kamra ships the governed tools, MCP access, RBAC and an audit log; the AI
  itself is brought in — your own Claude over MCP, or HeyKoala for
  voice/WhatsApp.
  **If you installed `v1.0.0` and configured agents, upgrading deletes that
  configuration and any pending-approval history on `bench migrate` — export
  anything you need first.**

### Fixed
- The public booking page's live availability/price search was silently
  failing for every real guest (403) because it depended on a staff-only,
  role-gated internal function. It now computes availability the same way
  without the role check, so `/book` shows real per-date quotes again.
- Copilot could mis-tax a food & beverage charge, double-post a charge, and
  claim it had notified housekeeping when no such tool existed. Tax now comes
  from the tax engine, the system prompt forbids claiming un-actioned work,
  and a real ticket-raising tool reaches housekeeping/maintenance.
- Assorted Copilot UX: page jumped on click, markdown headings didn't render,
  "who checked out / arrived" lookups failed to resolve reservations.

## [1.0.0] - 2026-07-05
Initial public release.
