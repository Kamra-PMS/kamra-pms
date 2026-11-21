---
title: Kamra is Apache-2.0
description: Kamra PMS core is now under the Apache License 2.0. What changed, what stayed the same, and why we opened further.
---

# Kamra is Apache-2.0

Kamra PMS core is now licensed under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0). The same complete hotel PMS, the same free Community edition, and a clearer path for hotels, chains and integrators whose legal teams could not adopt AGPL.

This is a deliberate step toward more openness and more contribution. Every contributor whose code is in core agreed on [GitHub #591](https://github.com/Kamra-PMS/kamra-pms/issues/591). Apache-2.0 starts with **Kamra 2.8.0**.

## What changed

- **New releases** of Kamra core ship as Apache-2.0.
- You may use, change, host and sell Kamra under that license, including inside a proprietary product, with the attribution and patent terms Apache-2.0 requires.
- Hotels, partners and software vendors who blocked AGPL can now evaluate and ship on Kamra without a special licence deal.

## What did not change

- Every release already published stays **AGPL-3.0**. Nothing is taken back.
- The product stays **free**: no per-room fee, no per-seat fee, no edition that removes features from open source.
- The [Kamra Open Pledge](https://kamrapms.com/open-pledge/) still holds: open features stay open, your data exports free, and the API, webhooks and MCP tools stay free.
- The **Kamra** name and mark stay under [TRADEMARK.md](https://github.com/Kamra-PMS/kamra-pms/blob/develop/TRADEMARK.md). Run Kamra and say so; give a changed fork its own name.
- Contributor names stay in the credits, the release notes and the git history.

## Why Apache-2.0

AGPL protected the early project well. It also stopped many hotels, chains and integrators whose counsel will not approve copyleft for internal or customer-facing systems.

Apache-2.0 is a standard permissive licence. It keeps the code free to use and change, asks for attribution, and includes an explicit patent grant. That combination is familiar to legal teams and to Frappe / ERPNext-adjacent shops that already ship permissive apps.

We want Kamra to be easy to adopt, easy to build on, and easy to contribute to. A permissive licence is how we make that true for more of hospitality.

## What "open" means here

Kamra is still:

- **One app.** Front desk, housekeeping, billing, F&B, banquets, booking engine and MCP tools ship together. No feature locked behind a Community vs Enterprise wall in the open-source tree.
- **Self-hostable.** Docker, classic bench, or [Frappe Cloud Marketplace](/self-hosting/frappe-cloud). Your data on your site.
- **Agent-ready.** Every staff action is a governed [MCP tool](/ai-and-mcp). Prices and taxes come from code, never from a model.

Enterprise work, if any, only adds services around that open core. It does not take features out of it.

## For hotels and partners

- Install from the Marketplace or [self-host](/self-hosting/).
- Build custom flows on the [REST API](/api) and [MCP tools](/mcp-tools).
- Resell implementation and support. Do not put a paid price on the Kamra software itself on a cloud marketplace listing; sell the work around it.

## For contributors

New pull requests land under Apache-2.0. See [CONTRIBUTING.md](https://github.com/Kamra-PMS/kamra-pms/blob/develop/CONTRIBUTING.md). Country packs, docs and product fixes are all welcome.

## Thank you

This change needed a yes from everyone whose code is in Kamra core, and they all said it within a week:

- Paul Mwanje ([@pmwanje2](https://github.com/pmwanje2))
- Kruthika Gowda ([@Kruthikagowda12](https://github.com/Kruthikagowda12))
- Ernesto Ruiz ([@ernestoruiz89](https://github.com/ernestoruiz89))
- Muneef ([@muneef-m](https://github.com/muneef-m)) and Mohammed Muneef ([@Mohammed-Muneef](https://github.com/Mohammed-Muneef))
- Sandro Garcia ([@SandroG1977](https://github.com/SandroG1977))
- Shaikh Ameer Pasha ([@ShaikhAmerPasha](https://github.com/ShaikhAmerPasha))
- Madhukar Hiranya ([@madhukarah](https://github.com/madhukarah)), for Pace Wisdom
- Kentrick Felix Kepawitono ([@kentrick22](https://github.com/kentrick22))
- 白羽 ([@baiyu0616a](https://github.com/baiyu0616a)), for the Simplified Chinese interface (#618, #647). Agreed in #591 on 19 Nov 2026 to relicense under MIT or Apache-2.0, so zh-CN stays in core.

Fares Alslahi ([@faresalslahi-collab](https://github.com/faresalslahi-collab)) gave Kamra the booking guest and room summary (#83). That idea stays credited. The confirmation summary in core was rewritten for this licence change.

## Read more

- [Why Kamra](/why-kamra)
- [The Kamra Open Pledge](https://kamrapms.com/open-pledge/)
- [How Kamra makes money](https://kamrapms.com/how-kamra-makes-money/)
- Contributor vote: [GitHub #591](https://github.com/Kamra-PMS/kamra-pms/issues/591)
- Source: [github.com/Kamra-PMS/kamra-pms](https://github.com/Kamra-PMS/kamra-pms)
