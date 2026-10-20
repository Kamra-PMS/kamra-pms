---
name: kamra-dev
description: >-
  Develop Kamra PMS (Frappe + React hotel/villa PMS): add APIs, MCP tools,
  folios, POS, frontend screens, localization, tests, and docs. Use whenever
  the user works on Kamra, kamra-pms, the Frappe app, /kamra SPA, MCP, REST
  endpoints, night audit, cashier, banquets, housekeeping, WhatsApp, channel
  manager, docs-site, eval harness, or demo.kamrapms.com — even if they only
  say "the PMS", "front desk", or "add a tool".
---

# Kamra PMS — developer skill

The app lives in this repo (`kamra/`). On this Mac the checkout is
`/Users/azzax/Workspace/agenticpms/kamra` (symlink into the Frappe bench).
Marketing site is a **different** repo and skill (`kamra-website-publish`).

Read [architecture.md](architecture.md) when the change touches money,
MCP, auth, or a new module. Public docs: https://kamrapms.com/docs/how-it-works

## The rule that everything else follows

There is **one write path**. The desk UI, REST, Claude MCP, and the in-app
copilot all call the same `@frappe.whitelist` function. Prices, GST,
availability, and cancellation fees are **code** (`kamra/pricing.py`,
folio, night audit). The model never invents a rate. If a role is short
or a number is outside guardrails, the function refuses.

Do not add a second writer (raw SQL updates that skip the API, a
client-trusted amount on a public endpoint, an MCP tool that computes
its own price).

## Repo map

| Path | What |
| --- | --- |
| `kamra/api.py` | Core desk: quote, book, check-in/out, folios, HK, tickets |
| `kamra/pos.py` `laundry.py` `banquet.py` `banquet_ops.py` | F&B, laundry, functions |
| `kamra/cashier.py` `ledger.py` `folio.py` `pricing.py` | Money |
| `kamra/mcp_tools.py` `mcp_http.py` `mcp_oauth.py` | MCP registry + `/mcp` |
| `kamra/assistant.py` | In-app copilot (BYO OpenAI-compatible key) |
| `kamra/public_api.py` | Guest `/book`, `/checkin` (`allow_guest`) |
| `kamra/authz.py` | `@require_roles`, cashier PIN |
| `kamra/localization/` | Country packs (tax, invoice words, locale) |
| `frontend/src/` | React SPA. Prod basename `/kamra` |
| `docs-site/` | VitePress docs at kamrapms.com/docs |
| `mcp/kamra_mcp.py` | Stdio sidecar (air-gap) |

SPA routes: `frontend/src/App.tsx`. API client: `frontend/src/lib/api.ts`
(`call("kamra.api.get_quote", { … })`).

## Adding a staff action

1. **Whitelist** a function in the right module. Put `@require_roles(...)`
   **below** `@frappe.whitelist()`. Admins always pass. Hotel Admin is
   a business role; System Manager is IT (`require_it_admin`).
2. **Money / rooms:** go through existing helpers (`get_quote`,
   `post_stay_charge`, folio ledger, overlap guard). Alcohol never
   bills a Company folio. Cancellation uses `cancellation_preview` then
   `cancel_reservation` (policy cannot be skipped unless `waive_fee=1`,
   logged). Night audit is idempotent per business date.
3. **Frontend:** call that function. Do not fetch doctypes that skip
   Kamra authz. Match existing screen chrome (Today, tape, folio).
4. **MCP (if an agent should do it):** add a `ToolSpec` in
   `kamra/mcp_tools.py` pointing at the dotted endpoint. Set `group`
   (and thus `module`) so disabled property modules hide it. Mark
   `mutating=True` for writes. Inject `property` from the grant — do
   not ask the model for it when `inject_property` is set.
5. **Docs:** from `docs-site/`:
   ```
   python3 gen_api.py
   python3 gen_mcp_tools.py
   ```
   If you added a **new Python module** of endpoints, append it to
   `MODULES` in `gen_api.py` first.

Public (`allow_guest`) endpoints are rate-limited and **never** trust a
price or folio amount from the browser.

## Auth and modules

Roles: Front Desk, Revenue Manager, Finance, Housekeeping, Hotel Admin,
System Manager, Kamra Agent. Gates live on the endpoint
(`_kamra_roles`), not hoped-for DocPerms.

Property modules (`enabled_modules`, empty = all): `front-desk`,
`housekeeping`, `operations`, `fnb`, `events`, `revenue`, `finance`,
`booking-engine`, `admin`. MCP visibility is `role ∩ modules`.

## Frontend

- Prod URL prefix `/kamra` (`ROUTER_BASENAME`). Guest shortcuts:
  `/book` → `/kamra/book`, `/hk` → `/kamra/hk`.
- `npm run dev` in `frontend/` (Vite :5173). `npm run build` emits
  `kamra/public/frontend` — **commit the build** when shipping UI.
- After UI changes, verify in the browser (demo or local), not only a
  screenshot. Check other screens that share the state you touched.

## Tests and PR

- Python that touches pricing, folios, availability, or roles: run
  ```
  bench --site <site> console
  >>> from kamra.scripts.eval_harness import execute; execute()
  ```
  Local Docker site is usually `kamra.localhost`.
- Frontend: `cd frontend && npm run build`.
- PRs target **`develop`**. Branch `feat/<slug>`, `fix/<slug>`,
  `docs/<slug>`. Conventional Commits; versioning is **patch-first**
  (`feat:` still ships as 2.6.x unless a maintainer sets MINOR).
- Localization: new country = one file under `kamra/localization/`.
  Do not hardcode `₹` or GST % in the UI — use `property_locale`.

## Docs site

Edit `docs-site/*.md`. Screenshots: `docs-site/scripts/capture-screenshots.mjs`
against `https://demo.kamrapms.com/kamra` (system Chrome). Publish docs:

```
cd docs-site && npm run build
rsync -a --delete .vitepress/dist/ kserver:/var/www/kamrapms.com/docs/
```

macOS rsync: never `--info=`. Never `--delete` on the marketing root
(that wipes `/docs`). Full site+docs: `kamra-deploy/publish-site.sh`.

## Do not

- Put secrets in the repo or in docs screenshots of Developers keys.
- Force-push `main` / `develop`.
- Treat Desk as the product UI — staff live in `/kamra`.
- Use the website-publish skill for app/docs work, or this skill for
  kamrapms.com marketing copy.
