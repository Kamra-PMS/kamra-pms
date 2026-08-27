# FAQ

## Is anything locked behind a paid plan?

**No.** Every feature is open source and included everywhere. Kamra Cloud
adds hosting, backups, updates and support — plus *connected services*
that carry third-party licensing costs (live GST e-invoicing through a
licensed provider, WhatsApp gateway, payment gateway setup). Those are
services with real per-use costs, not feature gates. The GSTR-1 export
files are free for everyone.

## Why is there no per-room pricing?

Adding rooms doesn't make software cost more, so charging per room is a
tax on your growth. Self-hosting is free at any size; Cloud pricing
scales only with the server your property needs.

## What are the default login credentials?

There aren't any. After `bench new-site … --admin-password <password>`,
open `/kamra` and sign in as **Administrator** or **admin@example.com**
with that password. Forgot it:
`bench --site <site> set-admin-password <new-password>` (on Docker, prefix
with `docker compose exec backend`). Staff should then get their own email
logins.

## What does self-hosting really require?

A 2 vCPU / 4 GB / 40 GB VPS (~₹549–$24/month), a domain, and an
afternoon. See the [guides](/self-hosting/). You manage updates and
backups; both are one command.

## Can I move between Cloud and self-hosting?

Yes, both directions. It's standard Frappe — `bench backup` produces a
full database + files archive that restores anywhere.

## Does the AI ever set prices or taxes?

No. Rates, taxes, availability and policy fees are deterministic code,
verified by an automated eval suite in CI. AI agents call governed tools
as permission-checked users and cannot go around them.

## Which Frappe version does Kamra need?

Frappe **v16** (with the `payments` app). Install from the `main` branch
for stable; `develop` is the nightly channel.

## How do I report a bug or ask for a feature?

[GitHub issues](https://github.com/Kamra-PMS/kamra-pms/issues) for bugs
and requests, discussions for questions. Security reports: see
`SECURITY.md` — please don't open public issues for those.

## Who builds Kamra?

[HeyKoala](https://heykoala.ai). The PMS is our open-source foundation;
we make money hosting it and building AI hotel staff on top — not by
gating features.
