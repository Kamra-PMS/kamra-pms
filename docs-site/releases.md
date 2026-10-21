# What's new

Stable releases ship from the `main` branch as `vX.Y.Z`. Kamra versions
**patch-first** (2.6.16 → 2.6.17): small features and fixes share one
minor line until maintainers deliberately cut a higher bump. Full notes:
[CHANGELOG.md](https://github.com/Kamra-PMS/kamra-pms/blob/main/CHANGELOG.md).

Install or upgrade: [Frappe Cloud Marketplace](/self-hosting/frappe-cloud)
or [self-hosting](/self-hosting/). After upgrade, open
**Admin → System Health** to confirm the site version.

## Current stable: v2.6.18

Released 20 Oct 2026.
[GitHub release](https://github.com/Kamra-PMS/kamra-pms/releases/tag/v2.6.18).

- **Guided check-in and check-out** - step by step screens from every
  Check in and Check out button; required steps are enforced and the
  check-out settles, refunds and invoices without dead ends.
- **Villa party rules** - extra guests, child ages, group size and
  holiday seasons.
- **Rooms** - a Rooms screen with a room panel, insights and a
  configurable Today; tape chart bars open a stay panel.
- **POS** - cancel or void by kitchen state, an orders list and a guest
  panel; kitchen printers are seeded with their status.
- **Agents** - a Frappe API key works on `/mcp` for unattended agents.
- **Fixes** - petty cash stays per property, desk lists use the full
  width, Today no longer scrolls sideways on phones or in Arabic, and
  the Frappe Cloud marketplace audit passes.

## Recent stables

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

## Docs versioning

The manual is versioned from **v2.6.17** onward:

| URL | What it is |
| --- | --- |
| [/docs/](https://kamrapms.com/docs/) | Latest docs (tracks `develop`, labelled with the current stable) |
| [/docs/vX.Y.Z/](https://kamrapms.com/docs/v2.6.17/) | Frozen snapshot taken when that GitHub Release was published |

Use the **version** control in the top nav to switch. Older snapshots show a
banner linking back to latest. Each new GitHub Release freezes a copy
automatically (see `.github/workflows/docs.yml`).

How maintainers cut releases: [`RELEASING.md`](https://github.com/Kamra-PMS/kamra-pms/blob/main/RELEASING.md)
in the repo. How the pieces fit together: [How Kamra works](/how-it-works).
