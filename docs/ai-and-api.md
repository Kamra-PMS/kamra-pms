# AI & API setup

Kamra is agent-native: everything staff can do, an agent can do — through
the same governed tool layer. Prices come from the pricing engine,
guardrails and policies apply, and every action lands in the **Agent
Action Log** with who/what/why and the minutes it saved.

There are two ways to put an AI to work, and they can run side by side.

## 1. The in-app copilot (bring your own key)

An optional chat assistant for staff, right inside the console.

**Enable it:** Settings → *AI assistant* → tick Enabled, paste your
provider's API key, save. The sparkle button appears bottom-right for
everyone at that property.

- **Any OpenAI-compatible provider works** — OpenAI
  (`https://api.openai.com/v1`), OpenRouter, Groq, a local Ollama/vLLM.
  Set the base URL and model to taste.
- **Your key, your data.** Kamra adds no markup and proxies nothing
  through third parties — requests go from your server to your provider.
- **Governed:** the model can only call Kamra's tools (quote, book,
  check-in/out, folios, splits, payments, cancellations with policy
  preview, rates within guardrails, night audit). It cannot invent a
  price or skip a fee — the tools refuse.
- **Audited:** every state-changing call is logged as
  `copilot_<tool>` with its arguments, on top of the API's own logging.
  Filter the Agent Action Log by channel "Chat" to review a shift.

## 2. MCP — connect Claude (or any MCP client)

The MCP server ships with the app (`mcp/kamra_mcp.py`) and exposes 25+
tools: availability, quotes, bookings, group billing, splits, occupant
register, GRC data, rate changes, cancellations, owner briefing, night
audit, property setup and AI-assisted booking imports.

**Get credentials** (token auth, per user — use the scoped agent
account, not an admin):

1. Desk → `Users` → `agent@kamra.local` → **API Access → Generate Keys**.
2. Copy the API secret immediately (shown once).

**Connect** (the exact command with your URL is on Settings → *Agent
access*):

```bash
claude mcp add kamra \
  -e KAMRA_URL=https://your-hotel.example.com \
  -e KAMRA_API_KEY=xxxx -e KAMRA_API_SECRET=xxxx \
  -e KAMRA_PROPERTY="Your Property" \
  -- python apps/kamra/mcp/kamra_mcp.py
```

Then just talk: *"Book Mr. Rao a deluxe Fri–Sun with breakfast, company
Acme pays the stay"* — the agent quotes, books, routes billing by the
company's rules, and logs it all.

## Direct REST

Every whitelisted function is a REST endpoint:

```
POST /api/method/kamra.api.<function>
Authorization: token <api_key>:<api_secret>
Content-Type: application/json
```

Key endpoints: `get_quote`, `create_booking`, `create_group_booking`,
`check_in`, `check_out`, `get_folio`, `post_stay_charge`,
`split_folio_charge`, `transfer_folio_charges`, `add_folio_payment`,
`cancellation_preview`, `cancel_reservation`, `group_folios`,
`update_occupants`, `registration_card`, `owner_briefing`,
`cash_summary`, `run_night_audit`, `gstr1_rows`.

## The autonomy rails

- **Rate guardrails**: floors/ceilings per room type — agents literally
  cannot price outside them.
- **Deterministic money**: pricing, GST, availability, policy fees are
  code, verified by the 18-check eval harness in CI.
- **Hard rules**: alcohol never bills to a company folio; cancellations
  can't skip the policy; night posting is idempotent.
- **Savings ledger**: automated actions record minutes saved — the
  owner's ROI dashboard is data, not marketing.
