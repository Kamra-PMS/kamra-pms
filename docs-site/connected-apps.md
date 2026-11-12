# Connected apps (service accounts)

A connected app (a reporting tool, an approvals bot, a guest channel) gets
its own API identity in Kamra: a **service account**. It does not borrow a
person's key, so it never has that person's full roles, and turning it off
does not lock anyone out.

Each service account has:

- **Scopes**: the exact endpoints and MCP tools it may call. Everything
  else is refused before it runs, including Frappe's generic
  `/api/resource` REST, Desk pages and every Kamra endpoint outside the
  scopes.
- **Properties**: the hotels it may touch. Calls aimed at any other
  property are refused, the same way they are for staff limited to some
  hotels.
- **A key that rotates.** Rotating issues a new secret and the old one
  stops working at once.
- **An access log.** Every call, allowed or refused, is a row in the Agent
  Action Log (`service_account.call`) with the account name, the endpoint
  or MCP tool, and the HTTP status.

## Scopes

| Scope | What it opens |
| --- | --- |
| `frontdesk.read` | Today's snapshot, availability, quotes, booking options, find bookings, stay detail |
| `reports.read` | Manager flash, night audit report, voids and allowances, SLA, report packs, custom reports, P&L, balance sheet, cash forecast |
| `cashier.read` | Cashier shifts and sessions, folios, city ledger and accounts receivable |
| `approvals.write` | Pending allowances (approve or reject), till variance sign-off, booking requests (accept or decline) |
| `concierge.guest` | Only the four signed guest concierge endpoints. No staff tool, no MCP. Can't be combined with other scopes. See [Guest channel providers](/channel-providers). |

The MCP tools behind each scope are listed in `kamra/service_accounts.py`
(`SCOPES`). An endpoint only an admin may call can't be put in a scope.

## Create a service account

Only IT (System Manager) can create, rotate or revoke service accounts.
From a bench console or a REST call made as IT:

```python
from kamra.service_accounts import create_service_account
create_service_account("Owner dashboard", ["reports.read"], ["Kamra Demo Palace"])
# {"name": "...", "user": "svc-...@service.kamra.local",
#  "api_key": "...", "api_secret": "..."}
```

The secret is shown once. Store it in the connected app's secret store.

## Call Kamra with it

REST:

```bash
curl https://your-site/api/method/kamra.reports.manager_flash \
  -H "Authorization: token <api_key>:<api_secret>" \
  -d property="Kamra Demo Palace"
```

Remote MCP: point the client at `https://your-site/mcp` with the same
`Authorization: token <api_key>:<api_secret>` header. When the account has
more than one property, add `X-Kamra-Property: <property>`. `tools/list`
shows only the scoped tools.

A call outside the scope gets HTTP 403 with
`Outside this service account's scope: <method>`.

## Rotate or revoke

```python
from kamra.service_accounts import rotate_service_account_key, revoke_service_account
rotate_service_account_key("<name>")   # new secret, old one stops now
revoke_service_account("<name>")       # off at once: user disabled, secret replaced
```

`list_service_accounts()` shows every account with its scopes, properties
and when it was last used.
