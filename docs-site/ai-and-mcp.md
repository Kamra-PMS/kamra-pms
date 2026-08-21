# Connect your AI (MCP)

Kamra is agent-native: everything staff can do through a governed tool,
an agent can do — through the same layer. Prices come from the pricing
engine, guardrails and policies apply, and every action lands in the
activity ledger with who / what / why.

There are two ways to put an AI to work, and they can run side by side.

## How it works

```
Claude  →  HTTPS /mcp (OAuth as you)  →  Kamra tools  →  pricing engine,
           RBAC, folio rules, night audit, Activity Log
```

The model never invents a rate or skips a cancellation fee. It calls a
tool; the tool refuses if the number is wrong or the role is short. The
in-app copilot (bring-your-own key) uses the same APIs.

Staff connect **as themselves**. A front-desk session can quote, book and
check in; it cannot change rates or run finance. Unattended jobs
(HeyKoala, night scripts) use a service key from Developers.

## 1. Connect Claude (the usual path)

Your Kamra site must be **public HTTPS** — Claude talks to it from
Anthropic's cloud, not from the laptop.

1. In Kamra open **Kamra Agent → Connect your AI**.
2. Click **Connect Claude**. Claude opens with this hotel's MCP URL
   filled in.
3. Confirm **Add**, then sign in to Kamra if asked, pick the property,
   **Allow**.
4. In a Claude chat, open the **+** menu → Connectors and enable Kamra.

Then talk in hotel language: *"Book Mr. Rao a deluxe Fri–Sun with
breakfast, company Acme pays the stay"* — it quotes, books, routes
billing by the company's rules, and logs everything.

**Claude Code** (same OAuth, from a terminal):

```bash
claude mcp add --transport http kamra https://pms.yourhotel.com/mcp
```

Then `/mcp` in the session and complete the browser sign-in.

Disconnect from the same Connect panel — that revokes the grant. Claude
must sign in again.

### Localhost and air-gapped sites

If the origin is `http://` or `*.localhost`, Connect Claude is disabled:
Anthropic cannot reach you. Use Claude Code against the same `/mcp`
URL on that machine, or the stdio sidecar in `mcp/kamra_mcp.py` with a
personal API key from Developers.

### Cloudflare / WAF

Remote MCP requests come from Anthropic's egress range
`160.79.104.0/21`. If Super Bot Fight Mode is on, allowlist that range
on the MCP host or Claude will OAuth successfully and then fail to call
tools.

## 2. The in-app copilot (bring your own key)

An optional chat assistant for staff, inside the console.

**Enable it:** Settings → *AI assistant* → Enabled, paste your
provider's API key, save.

- **Any OpenAI-compatible provider** — OpenAI, OpenRouter, Groq, or a
  local Ollama/vLLM. Set base URL and model to taste.
- **Your key, your data.** No markup, no proxying — requests go from
  your server to your provider.
- **Governed:** the model only calls Kamra's tools; it cannot invent a
  price or skip a cancellation fee — the tools refuse.
- **Role-scoped:** the copilot only sees the tools the signed-in user's
  roles allow.

## What work it can do

Kamra currently ships **52 governed tools** (see the
[tool reference](/mcp-tools)). Roughly, by job:

| Job | Tools |
| --- | --- |
| Front desk | Today's board, availability, quote, book, waitlist, check-in / out, guest lookup and journey, occupant register |
| Billing | Folio, post a charge (rules pick the folio), split a line, payment *link* |
| Revenue | Rate changes inside the owner's floor / ceiling |
| Briefings | Owner briefing, hotel-position briefing — never change the figures |
| Night audit | Idempotent end-of-day posting and no-shows |
| Groups | Draft a block, pickup status, name a guest into the block, group billing |
| Banquets | Availability, catalogue, enquiry → quote → event order → close-out |
| Onboarding | `setup_property`, `import_bookings` — only if the user's role allows |

### How to talk to it

Say the hotel work, not the API:

- "Who's arriving today, and who still owes?"
- "Quote a deluxe Friday to Sunday, two adults, breakfast."
- "Book that for Priya Sharma, 98765 43210."
- "The Rao booking wants to cancel — what's the fee?"
- "Post ₹450 minibar to 214, not alcohol."
- "Do we have the hall on 14 December for 180 pax?"
- "Morning briefing for the owner."

Confirm irreversible steps (checkout with a balance, cancelling inside
the window, closing a folio) in the chat before the tool runs.

## Keep using it

- Enable the connector **per conversation** in Claude's + menu. It does
  not stay sticky across every chat unless you pin it.
- Check **Activity** in Kamra — every MCP call is a row with your name.
- Rotate access with **Disconnect** on the Connect panel, not by
  rotating a Frappe API key.
- The in-app copilot is still there for a desk terminal that should not
  leave the browser.

Named always-on jobs (a night auditor that runs at 3am, an owner brief
on WhatsApp, waitlist chase) are on the backlog below. Until they ship,
Claude is the loop: you open a chat, it uses the tools.

## Limitations

Be honest with the model, and with buyers:

- **No taking a payment, amending dates, moving a room, or closing a
  folio** on MCP yet. The copilot has some of these; MCP will catch up.
- **No housekeeping queue, POS, laundry, or OTA / channel-manager
  tools** on MCP.
- **Tickets** can be created and listed, not started or resolved.
- **Claude must reach the site.** NAT / private bench → stdio fallback.
- **Custom connector confirm.** Until Kamra is in Anthropic's directory,
  Claude shows "this URL came from an external link" — click through it.
- **Front Desk cannot change rates.** Revenue Manager (or admin) can,
  inside guardrails.
- **Irreversible actions still need a human in the Claude chat.** The
  tools will not phone the guest for you.

## The autonomy rails

- **Rate guardrails** — floors / ceilings per room type; agents
  literally cannot price outside them.
- **Deterministic money** — pricing, GST, availability and policy fees
  are code, verified by the eval suite in CI on every change.
- **Hard rules** — alcohol never bills to a company folio; cancellations
  cannot skip the policy; night posting is idempotent.
- **Audit** — every action is in the Activity Log; click a row for the
  full before / after story.

## Backlog (not in this release)

Kept visible so the differentiator has a next chapter. None of this is
required to Connect Claude today.

**Named jobs**

- Night Auditor — scheduled close + morning WhatsApp, every line a tool call
- Public quote-and-book number (voice)
- Owner Brief — daily occupancy / arrivals / cash
- Villa turnover agent — checkout → housekeeping → availability
- Waitlist chase — poll `waitlist_ready` and reach out
- Guest WhatsApp thread that posts to the folio
- Public `/try-the-agent` playground with a tool trace
- Submit Kamra to Anthropic's Connectors Directory

**Tool holes**

- `find_reservations`, take a payment, amend / move a stay, close a
  folio, run HK / POS / laundry / OTA, advance a ticket past create/list

**Housekeeping**

- `agent@kamra.local` created on install (today: `seed_rbac_v2` only)
- Tear down dormant autonomy / approvals UI
- STR-shaped MCP (cleaning fee, deposits, access instructions)
