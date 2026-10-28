# What's new

Stable releases ship from the `main` branch as `vX.Y.Z`. Kamra versions
**patch-first** (2.6.16 → 2.6.17): small features and fixes share one
minor line until maintainers deliberately cut a higher bump. Full notes:
[CHANGELOG.md](https://github.com/Kamra-PMS/kamra-pms/blob/main/CHANGELOG.md).

Install or upgrade: [Frappe Cloud Marketplace](/self-hosting/frappe-cloud)
or [self-hosting](/self-hosting/). After upgrade, open
**Admin → System Health** to confirm the site version.

## New: free video course

Released 27 Oct 2026.

A 27-part [video course](/video-course) on YouTube takes you through
Kamra from the first sign-in to night audit, reports and AI agents. Each
episode is about 8 minutes, with chapters, English captions and a link to
the matching guide. The first ten are out now, and new episodes follow
every Monday, Wednesday and Friday.
[Watch the playlist](https://www.youtube.com/playlist?list=PLcNTRQwzkzAs).

## Current stable: v2.6.22

Released 27 Oct 2026.
[GitHub release](https://github.com/Kamra-PMS/kamra-pms/releases/tag/v2.6.22).

- **Booked via an OTA** - key in Booking.com, Agoda, Airbnb and other
  sites with the OTA reference and the sold price.
- **Department report packs** - Engineering and Laundry packs; more
  datasets (tickets, laundry, POS items, shift handover, early
  departures); week-over-week comparison on pack emails.
- **MCP** - `city_ledger_aging` so agents can answer who owes money and
  how late.
- **Assistant** - chat amounts use the property's currency (thanks
  @ernestoruiz89).
- **Laundry** - stays under Housekeeping only; tidier house order cards.

## Recent stables

### v2.6.21

Released 25 Oct 2026.

- **Spanish and Arabic** - the staff app and `/docs/es/`, `/docs/ar/`
  guides are complete (RTL for Arabic).
- **Custom reports and department packs** - save and email reports;
  group and drill down; Front Office, Housekeeping, F&B and Hotel
  Manager packs in the reader's language.
- **Date ranges** - From/To on manager flash, F&B dashboard, shift
  report, folio history, room insights and the banquet pipeline.
- **Front desk** - book from an empty tape cell; room-move rate
  choices; Today tiles with balance due and Extend stay; guest list
  CSV export.
- **Booking** - international guest phone prefixes (property country
  as default).
- **Finance** - past transaction dates need Finance or Hotel Admin.
- **MCP** - MCP Read / Manage roles, AI access admin, agents only see
  the reports each role may open.

### v2.6.20

Released 24 Oct 2026.

- **Check in now, finish later** - only the room has to be done before
  check-in. Other required steps can be finished after the guest is in,
  and the desk sees a reminder to complete them.
- **Guest photos and ID images** - take a webcam photo and attach ID and
  address images on the guest profile.
- **Night audit recovery** - a stuck business date recovers, and the
  printable audit pack can be rebuilt from the desk.
- **Fixes** - a waived security deposit no longer blocks check-in.

### v2.6.19

Released 21 Oct 2026.

- **POS till** - menu first with a category rail, the cart above the
  bill, an open-bills popup, and a settle sheet that can charge any bill
  to a room. **Order history** covers up to a year of bills with search,
  filters, totals and CSV export.
- **Guest documents** - ID type, number, issue and expiry dates, scans
  and address proof on the guest profile; check-in warns on expired,
  expiring or already-used documents.
- **Alerts** - an on-screen alert and sound for new bookings, service
  tickets and laundry orders made by someone else, with separate
  switches for alerts, sound and the POS and kitchen sound.
- **Tills** - several tills per property, a cash office, and bill or KOT
  printing per station.
- **Setup** - quick or guided property setup with modules, outlets and
  tills, and a finish-setup checklist.
- **Rates** - a rate calendar, and a rates panel on bookings with BAR
  shown.
- **Guest requests** - assignee, who solved it, a timeline, filters and a
  deeper SLA view.
- **Config** - Reason Codes, Transaction Codes, and menu lists for
  allergens, stations and courses.
- The build version shows in the navigation menu and on the login
  screen.

### v2.6.18

Released 20 Oct 2026. Guided check-in and check-out, villa party rules
(extra guests, child ages, group size, holiday seasons), the Rooms screen
with insights and a configurable Today, POS cancel and void by kitchen
state, and a Frappe API key on `/mcp` for unattended agents.

### v2.6.17

- **Company credit control** - payment terms, due-date aging, warn or
  block at booking and check-out (Finance override logged).
- **Kitchen printers** - route KOTs by outlet and station; auto-accept
  and print as an F&B setting.
- **Go-live import** - CSV for companies and opening balances, preview,
  then reconcile.
- **Integrations** - outbound webhooks, external POS room-charge API,
  door-lock adapter interface.
- **Self-host** - prebuilt image pull, `:stable` tag, quickstart compose.

### v2.6.16

Pet charge on booking pages, desk form and folio; extra guests above
capacity as their own folio line.

### v2.6.15

End of Day night-audit checklist with a saved **report pack** and a
**Night Auditor** role; corporate guests settle their own extras; POS
bills cannot close unpaid; advance deposits clear at check-in.

### v2.6.14

Request-to-Book inbox, per-property no-show policy, rate lock at booking,
security deposits, day use, city-ledger payments, a
complete ledger, and a lighter first page load.

### v2.6.13

Settings hub, tiered cancellation and peak-date rules, POS auto-KOT;
night audit cannot run ahead of the calendar; no-show balances read from
the folio; whole-villa check-in; `/hk` keeps staff signed in; balanced
city-ledger transfers; Kamra Agent books by room and meal-plan name
without double-booking on retries.

### v2.6.12

Per-head pricing for small parties in whole-place lets; weekend /
weekday rate guardrails; Void on the bill screen asks for a reason;
admins see a banner when a newer Kamra release is out.

### v2.6.9 - v2.6.11

India-only integrations in the India pack (Razorpay and Cashfree payment
links, GSTR-1, **Kamra Verify** GSTIN and guest ID checks); privacy
(guest contacts hidden from the AI provider; nightly clearing of old
WhatsApp text and AI chats; children by name and age only; guest privacy
notice in Hindi, Kannada, Tamil, Telugu, Malayalam, Marathi and Bengali);
marketplace / registry packaging fixes for Frappe Cloud.

### v2.6.5 - v2.6.8

Security: property scope on staff APIs, signed webhooks, Guest DocType
scoped for restricted users; deposits before arrival; room change from
the GRC; checkout only once every bill is settled; ERPNext Company and
stock alongside Kamra.

### v2.6.2 - v2.6.4

Opera-style cashier till, folio ledger, cashier PIN, System Health,
property time zone, AI provider presets, DPDP tooling (erasure, access
export, retention, notices).

## Channels

| Channel | Source | Audience |
| --- | --- | --- |
| Stable | `main` + tag `vX.Y.Z` | Production, Marketplace, demo.kamrapms.com |
| Nightly | `develop` | nightly.kamrapms.com, testing only |

Self-host production should stay on **stable** or a pinned `vX.Y.Z`. After
trying a newer tag, go back by pinning the previous release again
(`KAMRA_TAG=… install.sh update`) - there is no in-app Downgrade control.
See [Going back (downgrade)](/quickstart#going-back-downgrade).

## Docs versioning

The manual is versioned from **v2.6.16** onward:

| URL | What it is |
| --- | --- |
| [/docs/](https://kamrapms.com/docs/) | Latest docs (tracks `develop`, labelled with the current stable) |
| [/docs/vX.Y.Z/](https://kamrapms.com/docs/v2.6.17/) | Frozen snapshot taken when that GitHub Release was published |

Use the **version** control in the top nav to switch. Older snapshots show a
banner linking back to latest. Each new GitHub Release freezes a copy
automatically: the release workflow starts `.github/workflows/docs.yml`,
which builds the snapshot and lists it in the switcher.

How maintainers cut releases: [`RELEASING.md`](https://github.com/Kamra-PMS/kamra-pms/blob/main/RELEASING.md)
in the repo. How the pieces fit together: [How Kamra works](/how-it-works).
