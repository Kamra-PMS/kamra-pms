# API & developer shortcuts

Everything that talks to Kamra - desk UI, REST clients, Claude MCP and the
in-app agent - hits the same whitelist. Use these links to get unblocked
fast.

| Shortcut | What you get |
| --- | --- |
| [REST API basics](/api) | Auth, URL shape, frequently used endpoints |
| [REST API reference](/api-reference) | Full generated list of methods and parameters |
| [MCP tool reference](/mcp-tools) | Governed tools for Claude / any MCP client |
| [Postman collection](/kamra.postman_collection.json) | Import into Postman or Insomnia (download JSON) |
| [How Kamra works](/how-it-works) | Architecture, one write path, stay lifecycle |
| [Connect your AI](/ai-and-mcp) | OAuth MCP setup for Claude |

## Postman in 2 minutes

1. Download [`kamra.postman_collection.json`](/kamra.postman_collection.json).
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

Guest surfaces (`/book`, self check-in, QR menu) use `kamra.public_api`
and do not take a staff token - they are rate-limited and never trust a
price from the browser.
