---
layout: home

hero:
  name: Kamra
  text: The hotel PMS agents can actually run
  tagline: Open-source PMS with a governed MCP layer - Claude (or any agent) quotes, books and posts charges as a permission-checked user. Prices stay in code. Every action is audited.
  image:
    src: /kamra-mark.svg
    alt: Kamra
  actions:
    - theme: brand
      text: Connect Claude (MCP)
      link: /ai-and-mcp
    - theme: alt
      text: MCP tool reference
      link: /mcp-tools
    - theme: alt
      text: API · Postman
      link: /developers
    - theme: alt
      text: Live demo
      link: /demo

features:
  - title: MCP is the product edge
    details: 100+ governed tools on /mcp. Same whitelist as the desk. Role-scoped, module-gated, fully logged. The model never invents a rate.
    link: /ai-and-mcp
  - title: Every MCP tool
    details: Name, arguments and endpoint for the full tool registry - regenerated from code on every docs build.
    link: /mcp-tools
  - title: How Kamra works
    details: One write path for UI, REST and agents. Architecture diagrams, stay lifecycle and money rules.
    link: /how-it-works
  - title: REST API & Postman
    details: Call the same methods from your stack. Download the Postman collection and go.
    link: /developers
  - title: Features & latest release
    details: Front desk through banquets, F&B, WhatsApp and country tax packs - plus what's new in v2.6.17.
    link: /features
  - title: Install
    details: Docker on a VPS, classic bench, or the Frappe Cloud Marketplace. Same complete AGPL app.
    link: /self-hosting/
---

## What makes Kamra different

Most hotel software bolts a chatbot onto a closed SaaS. **Kamra is built
so an agent and a receptionist share one governed write path.**

1. **MCP first.** Connect Claude (or any MCP client) to `/mcp`. Tools are
   filtered by the signed-in user's roles and the property's enabled
   modules.
2. **Deterministic money.** Quotes, taxes, availability and cancellation
   fees come from `pricing.py` and the folio ledger - never from the
   model. Guardrails refuse out-of-range rates.
3. **Full audit.** Every mutating tool call lands in the Activity Log
   with who / what / why.
4. **Same APIs for everyone.** Desk UI, REST, MCP and the in-app Kamra
   Agent call the same `@frappe.whitelist` functions. No second writer.

Start here: **[Connect your AI (MCP)](/ai-and-mcp)** ·
**[MCP tool reference](/mcp-tools)** ·
**[How Kamra works](/how-it-works)** ·
**[Developer shortcuts](/developers)**

**Current stable:** [v2.6.17](/releases) ·
[Live demo](https://demo.kamrapms.com) ·
[Frappe Cloud Marketplace](https://frappecloud.com/marketplace/apps/kamra)

![Kamra's Today screen: arrivals, departures, the room board and in-house guests](/img/front-desk/today.png)

## Where to start

- **You want the AI story:** [Connect your AI](/ai-and-mcp), then the
  [MCP tool reference](/mcp-tools). Architecture and the one write path:
  [How Kamra works](/how-it-works).
- **You're integrating:** [API, MCP & Postman](/developers) - REST basics,
  full [API reference](/api-reference),
  [Postman collection ↓](https://kamrapms.com/docs/kamra.postman_collection.json).
- **You run the hotel:** [Guides by role](/user-guide) and the module
  guides in the side bar.
- **You're installing:** [Quickstart](/quickstart),
  [Self-hosting](/self-hosting/), or
  [Frappe Cloud](/self-hosting/frappe-cloud).

**Quick links:** [Connect MCP](/ai-and-mcp) · [MCP tools](/mcp-tools) ·
[API basics](/api) · [API reference](/api-reference) ·
[Postman ↓](https://kamrapms.com/docs/kamra.postman_collection.json) ·
[What's new](/releases) ·
[changelog](https://github.com/Kamra-PMS/kamra-pms/blob/main/CHANGELOG.md)
