# Connect your AI (MCP)

Kamra is agent-native: everything staff can do, an agent can do — through
the same governed tool layer. Prices come from the pricing engine,
guardrails and policies apply, and every action lands in the activity
ledger with who/what/why.

There are two ways to put an AI to work, and they can run side by side.

## 1. The in-app copilot (bring your own key)

An optional chat assistant for staff, inside the console.

**Enable it:** Settings → *AI assistant* → Enabled, paste your provider's
API key, save.

- **Any OpenAI-compatible provider** — OpenAI, OpenRouter, Groq, or a
  local Ollama/vLLM. Set base URL and model to taste.
- **Your key, your data.** No markup, no proxying — requests go from your
  server to your provider.
- **Governed:** the model only calls Kamra's tools; it cannot invent a
  price or skip a cancellation fee — the tools refuse.
- **Role-scoped:** the copilot only sees the tools the signed-in user's
  roles allow. A front-desk session can't touch rates or finance.

## 2. MCP — Claude and any MCP client

The MCP server ships in the app (`mcp/kamra_mcp.py`) and exposes
[32 tools](/mcp-tools): availability, quotes, bookings, group billing,
splits, check-in/out, tickets, rate changes within guardrails, the owner
briefing and the night audit.

**Get credentials** — every staff user can mint their own from
**Copilot → Connect** (the key is *their* Frappe user, so their role
limits what the AI can do). For unattended agents use the scoped
`agent@kamra.local` account instead of an admin.

**Connect Claude:**

```bash
claude mcp add kamra \
  -e KAMRA_URL=https://pms.yourhotel.com \
  -e KAMRA_API_KEY=xxxx -e KAMRA_API_SECRET=xxxx \
  -e KAMRA_PROPERTY="Your Property" \
  -- python apps/kamra/mcp/kamra_mcp.py
```

Then just talk: *"Book Mr. Rao a deluxe Fri–Sun with breakfast, company
Acme pays the stay"* — it quotes, books, routes billing by the company's
rules, and logs everything.

## The autonomy rails

- **Rate guardrails** — floors/ceilings per room type; agents literally
  cannot price outside them.
- **Deterministic money** — pricing, GST, availability and policy fees
  are code, verified by the eval suite in CI on every change.
- **Hard rules** — alcohol never bills to a company folio; cancellations
  cannot skip the policy; night posting is idempotent.
- **Audit** — every action is in the Activity Log; click a row for the
  full before/after story.
