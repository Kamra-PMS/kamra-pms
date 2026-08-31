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
- `public_api.py` is the only `allow_guest` surface; anything else reachable
  without a session is a bug.
