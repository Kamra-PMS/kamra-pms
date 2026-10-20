# API, MCP & developer shortcuts

**Kamra's uniqueness is the governed MCP layer:** an agent and a
receptionist share one write path, deterministic prices, and a full audit
trail. Everything else on this page - REST and Postman - talks to that
same whitelist.

Start with MCP if you are evaluating why Kamra is different:
[Connect your AI](/ai-and-mcp) · [MCP tool reference](/mcp-tools).

| Shortcut | What you get |
| --- | --- |
| [Connect your AI (MCP)](/ai-and-mcp) | Hosted `/mcp` OAuth setup for Claude |
| [MCP tool reference](/mcp-tools) | All governed tools (name, args, endpoint) |
| [REST API basics](/api) | Auth, URL shape, frequently used endpoints |
| [REST API reference](/api-reference) | Full generated list of methods and parameters |
| [Postman collection](https://kamrapms.com/docs/kamra.postman_collection.json) | Import into Postman or Insomnia (download JSON) |
| [How Kamra works](/how-it-works) | Architecture, one write path, stay lifecycle |

## MCP in 2 minutes

1. Site must be **public HTTPS** (Claude talks from Anthropic's cloud).
2. In Kamra: **Kamra Agent → Connect your AI → Connect Claude**.
3. Allow the OAuth grant for a property. Enable Kamra under Claude's
   Connectors.
4. Ask in hotel language: *"Book Mr. Rao a deluxe Fri-Sun with breakfast."*

Full setup and guardrails: [Connect your AI](/ai-and-mcp). Every tool:
[MCP tool reference](/mcp-tools). Stdio sidecar for air-gapped benches:
`mcp/kamra_mcp.py` in the repo.

## Postman in 2 minutes

1. Download [`kamra.postman_collection.json`](https://kamrapms.com/docs/kamra.postman_collection.json).
2. Import → Collection in Postman (or Insomnia / Bruno).
3. Set collection variables:
   - `base_url` - your site, e.g. `https://demo.kamrapms.com`
   - `api_key` / `api_secret` - from **Developers** or **Kamra Agent → Connect your AI**
4. Send any request. Responses are `{"message": …}`.

The collection is regenerated with the API reference on every docs build
(`python3 gen_api.py` in `docs-site/`).

## Call shape

```
POST /api/method/kamra.<module>.<function>
Authorization: token <api_key>:<api_secret>
Content-Type: application/json
```

Guest surfaces (`/book`, self check-in) use `kamra.public_api`
and do not take a staff token - they are rate-limited and never trust a
price from the browser.
