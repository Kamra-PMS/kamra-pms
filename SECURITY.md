# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Instead use
GitHub's private reporting: **Security → Report a vulnerability** on this
repository (or email hello@kamrapms.com if you can't use GitHub).

You can expect an acknowledgement within 72 hours. Fixes ship as PATCH
releases on the latest stable line (e.g. `2.6.1`, `2.6.2`); we'll credit you
in the release notes unless you prefer otherwise.

## Supported versions

Only the latest stable release line receives security fixes. Hosted demo
instances (demo/nightly.kamrapms.com) contain synthetic data only — but a
PMS holds guest PII in real deployments, so we treat authentication,
role-permission, and data-exposure reports as highest priority.

## Scope notes

- The AI/agent surface (MCP server, copilot tools) is permission-checked as
  the calling Frappe user; a bypass of `require_roles` / `_tool_allowed`
  gating is in scope and high severity.
- Guest-reachable (`allow_guest`) surfaces are `public_api.py` (booking
  engine, pre-check-in, QR menu) and the inbound webhooks: `payments.razorpay_webhook`,
  `channel_manager.webhook`, `channels.aiosell.reservation_webhook`,
  `agents_channels.voice_webhook` / `messaging_webhook` and `whatsapp.webhook`.
  Every webhook must authenticate against a configured secret and refuse the
  call when none is set. Anything else reachable without a session is a bug.
- Property scope: staff restricted to some properties (Frappe User
  Permissions on Property) must not read or change another property's data.
  `require_roles` enforces this for record arguments; a bypass is in scope.

## Acknowledgements

Thank you to the researchers who reported issues responsibly:

- **[@archnexus707](https://github.com/archnexus707)** - first report of
  cross-property access by property-restricted staff, including guest ID
  documents and guest profiles
  ([GHSA-6cr2-jm8f-6jrx](https://github.com/Kamra-PMS/kamra-pms/security/advisories/GHSA-6cr2-jm8f-6jrx),
  2026-09).
- **kta1kri** - independent report of the same cross-property access, and
  inbound webhooks that accepted unauthenticated calls when no secret was
  configured (2026-09).
