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
| `finance.read` | Folios and tax invoices (`folio_invoice`), cashier sessions and the session report, city ledger, accounts receivable and invoices on an account, company monthly bills |
| `approvals.write` | Pending allowances (approve or reject), till variance sign-off, booking requests (accept or decline) |

Every read scope also opens `kamra.apps.property_profile` (see below) and `kamra.api.property_locale` (currency, symbol and number format).

The MCP tools and endpoints behind each scope are listed in one table,
`SCOPES` in `kamra/service_accounts.py`. An endpoint only an admin may call
can't be put in a scope.

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

## Connect an app in one step (for app authors)

Instead of creating a service account by hand, an add-on app can be
connected from **Marketplace, Connected apps**. IT enters the app's address,
reads what it asks for, picks the properties and approves. Kamra then:

1. creates a service account with exactly the approved scopes and
   properties;
2. registers the app in the App Registry, so its tile shows in the app
   switcher and on the Apps page for the roles it names;
3. allows the app's OAuth redirect address for staff sign-in;
4. shows a one-time **pairing code** (for example `K7QD-2MXP-9TRA-VH4C`).
   It works once and expires after 10 minutes. Kamra keeps only its hash.

The app trades the code for its key at `kamra.apps.pair`.

### The manifest: `kamra-app.json`

Serve it at `<your app address>/kamra-app.json` over HTTPS, with no
redirect:

```json
{
  "id": "night-reports",
  "name": "Night Reports",
  "url": "https://reports.example.com",
  "icon": "https://reports.example.com/icon.png",
  "scopes": ["reports.read", "finance.read"],
  "roles": ["Finance", "Hotel Admin"],
  "redirect_uri": "https://reports.example.com/oauth/callback",
  "pair_url": "https://reports.example.com/kamra/pair",
  "signature": "<base64 Ed25519 signature>"
}
```

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Lowercase letters, digits and dashes. The `app_id` you send to `pair`. |
| `name` | yes | Shown on the consent step and the tile. |
| `url` | yes | Where the tile opens. Same host as the manifest. |
| `scopes` | yes | What the app asks for, from the table above. IT may approve fewer. |
| `icon` | no | An https image for the tile. |
| `roles` | no | Staff roles that see the tile. Admins always see it; empty means admins only. |
| `redirect_uri` | no | Your OAuth callback for staff sign-in. Exact match, https, same host. |
| `pair_url` | no | Kamra links here with `?code=&app_id=&site=` so IT does not have to copy the code. Same host. |
| `signature` | see below | Ed25519 over the canonical manifest. |

### Signing

The signature covers the manifest without the `signature` field, as JSON
with sorted keys and no spaces, in UTF-8:

```python
import base64, json
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

body = {k: v for k, v in manifest.items() if k != "signature"}
data = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
manifest["signature"] = base64.b64encode(private_key.sign(data)).decode()
```

Kamra checks it against the **trusted publisher keys** in core settings: a
list of base64 Ed25519 public keys (32 bytes each). The list ships empty.
IT sets it with:

```python
from kamra.apps import set_trust
set_trust(keys=["<base64 public key>", ...])
```

**Self-hosted apps.** An app you run yourself does not need a publisher.
IT ticks *Allow unsigned apps* in Marketplace, Connected apps (or calls
`set_trust(unsigned=1)`). The consent step then marks the app as not
signed. Leave it off unless you connect your own apps.

The manifest is fetched again when IT approves, so the browser's copy is
never trusted.

### The pairing exchange

The only endpoint here that needs no login. Call it from your server, over
HTTPS, once:

```bash
curl -X POST https://hotel.example.com/api/method/kamra.apps.pair \
  -H "Content-Type: application/json" \
  -d '{"code": "K7QD-2MXP-9TRA-VH4C", "app_id": "night-reports"}'
```

On success (HTTP 200):

```json
{"message": {
  "app_id": "night-reports",
  "site_url": "https://hotel.example.com",
  "mcp_url": "https://hotel.example.com/mcp",
  "api_key": "...",
  "api_secret": "...",
  "scopes": ["reports.read"],
  "properties": [{"property": "PROP-0001", "property_name": "Harbour View"}]
}}
```

Store the secret in your secret store; Kamra never shows it again. A wrong,
used or expired code, or a code for another `app_id`, gets HTTP 403 with
`{"message": {"error": "invalid_code", "error_description": "..."}}`. The
endpoint is rate-limited (10 tries per 10 minutes per address) and every
attempt is an `app.pair_attempt` row in the Agent Action Log. If the code
expired, IT clicks *New pairing code*.

Then call Kamra with `Authorization: token <api_key>:<api_secret>` as
described above.

### Background reads vs. what staff do

The service account is for **background reads** only: syncing reports,
pulling folios overnight. Anything a person does in your app (approving an
allowance, posting a charge) must run as that person, with their roles and
their properties, so it is theirs in the audit log.

For that, use Kamra's MCP OAuth 2.1 (`kamra/mcp_oauth.py`), the same flow
Claude uses: authorization code with PKCE S256, dynamic client registration
at `/mcp/oauth/register`, discovery from the `WWW-Authenticate` header a
401 on `/mcp` returns (`/mcp/.well-known/oauth-protected-resource`), and
per-user tokens for `/mcp`. Pairing adds your `redirect_uri` to the allowed
redirect addresses (Settings, AI access), exact match and https only, so
registration and sign-in work without IT typing it in. The token only
reaches what that staff member's MCP role allows.

### Property profile

`kamra.apps.property_profile(property)` gives a paired app with any read
scope the hotel's branding and locale, without reading a folio:

```json
{"property": "PROP-0001", "name": "Harbour View", "legal_name": "Harbour View Hotels Ltd",
 "logo_url": "https://hotel.example.com/files/logo.png",
 "address": {"line": "...", "city": "...", "state": "...", "country": "...", "postal_code": "..."},
 "phone": "...", "email": "...", "website": "...",
 "tax_id": "...", "tax_id_label": "Tax ID", "currency": "USD", "locale": "en-US",
 "language": "en", "timezone": "Asia/Dubai", "checkin_time": "14:00:00", "checkout_time": "11:00:00"}
```

It refuses a property the app was not given.

### Disconnect

**Disconnect** in Marketplace (or `kamra.apps.disconnect(app_id)`) at once:
revokes the service account (the key stops working on the next call),
removes the app's redirect address, revokes the staff sign-in tokens issued
through it, and removes the tile. Connecting again creates a new service
account and a new code.

### IT endpoints

| Endpoint | What |
| --- | --- |
| `kamra.apps.preview(app_url)` | Read and check the manifest; the consent step |
| `kamra.apps.connect(app_url, scopes, properties)` | Approve: service account, registry entry, code |
| `kamra.apps.new_pairing_code(app_id)` | A fresh code for an app that has not paired |
| `kamra.apps.disconnect(app_id)` | Off at once |
| `kamra.apps.list_apps()` | Every app with its status, scopes and properties |
| `kamra.apps.set_trust(unsigned, keys)` | Allow unsigned apps; replace the trusted keys |
| `kamra.apps.my_apps()` | Any signed-in staff member: the tiles they may see |
