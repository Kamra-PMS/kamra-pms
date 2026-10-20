# What's new

Stable releases ship from the `main` branch as `vX.Y.Z`. Kamra versions
**patch-first** (2.6.15 → 2.6.16): small features and fixes share one
minor line until maintainers deliberately cut a higher bump. Full notes:
[CHANGELOG.md](https://github.com/Kamra-PMS/kamra-pms/blob/main/CHANGELOG.md).

Install or upgrade: [Frappe Cloud Marketplace](/self-hosting/frappe-cloud)
or [self-hosting](/self-hosting/). After upgrade, open
**Admin → System Health** to confirm the site version.

## Current stable: v2.6.16

Released 19 Oct 2026.
[GitHub release](https://github.com/Kamra-PMS/kamra-pms/releases/tag/v2.6.16).

- **Pet charge** on public booking pages, the desk booking form and the
  folio (posted once per stay at the quoted amount).
- **Extra guests above capacity** billed as their own folio line (not
  folded into the room rate).
- Ledger: Transaction Code can store the Extra Guests charge type.

## Recent stables

### v2.6.15

End of Day night-audit checklist with a saved **report pack** and a
**Night Auditor** role; corporate guests settle their own extras; POS
bills cannot close unpaid; advance deposits clear at check-in.

### v2.6.14

Request-to-Book inbox, per-property no-show policy, rate lock at booking,
security deposits, day use, printable QR codes, city-ledger payments, a
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

How maintainers cut releases: [`RELEASING.md`](https://github.com/Kamra-PMS/kamra-pms/blob/main/RELEASING.md)
in the repo. How the pieces fit together: [How Kamra works](/how-it-works).
