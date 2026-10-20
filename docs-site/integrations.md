# Integrations

::: tip The Kamra integration promise
**API access on day one, no extra fee.** Every screen in Kamra runs on the
same REST API you can call. You don't need an "interface licence" or a
partner agreement. Your hotel, your developer or your vendor can connect
on day one, without Kamra staff.
:::

Kamra is open source and runs on Frappe. Each integration below uses the
same governed functions as the front desk. The rules are the same however
a call arrives:

- role checks;
- property scope;
- prices and tax decided by the server;
- the audit log.

## At a glance

| Integration | Direction | How | Set up in |
| --- | --- | --- | --- |
| [REST API keys](#rest-api) | in | `POST /api/method/kamra.*` with a token | Developers |
| [AI agents (MCP)](#ai-agents-mcp) | in | `/mcp` with OAuth, or the stdio sidecar | Settings → Claude & MCP |
| [Outbound webhooks](#outbound-webhooks) | out | Signed JSON `POST` per event | Settings → Webhooks |
| [External POS room charges](#external-pos-room-charges) | in | `kamra.pos_interface.*` | Staff & access + Developers |
| [Channel manager (OTAs)](#channel-manager) | both | Channex, STAAH, AioSell adapters | Revenue → Channel Manager |
| [Payment links](#payments) | both | Gateway API out, gateway webhook in | Settings → Payments |
| [Door locks](#door-locks) | out | Adapter interface (bring a connector) | Settings → Front Desk |
| [Accounting export](#accounting-export) | out | Closed invoices with tax columns | Finance → Accounting Export |
| [ERPNext / Frappe HR](/self-hosting/erpnext-hr) | both | Same site, same database | — |

## REST API

Every whitelisted function is an endpoint:

```
POST https://YOUR-SITE/api/method/kamra.api.front_desk_snapshot
Authorization: token <api_key>:<api_secret>
Content-Type: application/json

{"property": "Your Property"}
```

An API key belongs to a user and acts with exactly that user's roles and
properties. For a service integration:

1. Create a user for it.
2. Give the user only the role it needs.
3. Limit the user to its property under Settings → Staff & access.

IT then issues the key on the **Developers** page.

See [REST API basics](/api) and the full [REST API reference](/api-reference).

## AI agents (MCP)

Staff connect Claude, or any MCP client, to `https://YOUR-SITE/mcp`. They
sign in with OAuth as themselves. The agent sees only the tools their role
and the property's modules allow. Every write goes through the same
function as the UI. See [Connect your AI](/ai-and-mcp) and the
[MCP tool reference](/mcp-tools).

## Outbound webhooks

Use webhooks so another system hears about changes as they happen,
instead of asking Kamra for them on a timer. Examples:

- a door-lock middleware;
- a CRM;
- a data warehouse;
- a housekeeping app;
- a revenue tool.

**Set up:** a Hotel Admin (or IT) opens **Settings → Webhooks**, then:

1. Click **Add webhook**.
2. Enter an `https://` URL.
3. Pick the events.
4. Copy the **signing secret**. It is shown once. You can rotate it any
   time.

**Send test** sends a signed `ping` and shows the result.

Subscriptions are **per property**. An endpoint only receives events for
its own property.

### Events

| Event | Fires when |
| --- | --- |
| `reservation.created` | A booking is made from any source: desk, booking engine, OTA, AI agent or import. CSV imports are muted. |
| `reservation.modified` | Any of these change: dates, room, room type, party size, rate, meal or rate plan, guest name, company, or status (for example Confirmed to No Show). The payload lists `changes` as `[old, new]`. |
| `reservation.cancelled` | A booking is cancelled. |
| `guest.checked_in` | A stay is checked in. |
| `guest.checked_out` | A stay is checked out. |
| `folio.posted` | A charge is posted to a guest, company or group folio. This covers desk charges, POS, external POS, laundry, banquet billing and deposit withholds. The night audit's room nights are summed in `night_audit.closed` instead. |
| `night_audit.closed` | The night audit closes a business date. |

### Payload

```json
{
  "id": "evt_6f1c9b0e0c4a4d8f9a7f3f5b2a1c0d9e",
  "event": "guest.checked_in",
  "api_version": 1,
  "created_at": "2026-10-19T14:02:11",
  "property": "Kamra Demo Palace",
  "data": {
    "reservation": "RES-2026-00042",
    "status": "Checked In",
    "guest_name": "Asha Rao",
    "room_type": "Kamra Demo Palace-DLX",
    "room": "Kamra Demo Palace-204",
    "room_number": "204",
    "check_in_date": "2026-10-19",
    "check_out_date": "2026-10-21",
    "nights": 2, "adults": 2, "children": 0,
    "amount_after_tax": 11800.0, "currency": "INR",
    "changes": {"status": ["Confirmed", "Checked In"]}
  }
}
```

A payload contains only the record of the subscription's own property.
Webhooks **never** send guest phone numbers, emails, ID documents or
check-in tokens. If you need guest details, fetch them with the REST API
under a key whose role allows it.

### Headers and signature

| Header | Value |
| --- | --- |
| `X-Kamra-Event` | The event name |
| `X-Kamra-Event-Id` | `id` from the body. It stays the same across retries and resends, so use it to drop duplicates. |
| `X-Kamra-Delivery` | The delivery-log row |
| `X-Kamra-Timestamp` | Unix seconds when this attempt was sent |
| `X-Kamra-Signature` | `sha256=` followed by the HMAC-SHA256 of `"{timestamp}.{raw body}"`, keyed with your secret |

To verify a delivery:

1. Compute the signature over the **raw** request body. Don't parse the
   JSON and re-serialise it first.
2. Compare the signatures in constant time.
3. Reject timestamps older than 5 minutes.

```python
import hashlib, hmac, time

def verify(secret: str, body: bytes, timestamp: str, signature: str) -> bool:
    if abs(time.time() - int(timestamp)) > 300:
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

```js
// Node.js (Express: use express.raw({ type: "application/json" }))
const crypto = require("crypto")
function verify(secret, rawBody, timestamp, signature) {
  if (Math.abs(Date.now() / 1000 - Number(timestamp)) > 300) return false
  const expected = "sha256=" + crypto.createHmac("sha256", secret)
    .update(`${timestamp}.`).update(rawBody).digest("hex")
  return expected.length === signature.length &&
    crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(signature))
}
```

### Delivery, retries and the log

The event is recorded in the same database transaction as the change.
Kamra sends it after that change is saved. A booking that fails to save
never sends an event, and a slow receiver never slows the front desk.

Reply with any **2xx** within **10 seconds**. Anything else counts as a
failure and is retried:

- **Counted as a failure:** another status, a timeout, a network error, or
  a redirect (redirects are not followed).
- **Retry schedule:** after 1 min, 5 min, 30 min, 2 h and 6 h. That is 6
  attempts over about 8.5 hours.
- **After the last attempt:** the delivery is marked **Failed**.

**Settings → Webhooks → Delivery log** shows, for each delivery:

- the event and its status;
- the HTTP code;
- the number of attempts;
- the last error;
- the exact payload.

**Resend** sends a delivery again with the same event id.

### Security

- **HTTPS only.** Plain `http://` is accepted only on a developer-mode site.
- **No internal addresses.** Kamra refuses URLs whose host resolves to a
  private, loopback, link-local (cloud metadata), CGNAT, multicast or
  reserved address. It also refuses credentials in the URL. It checks
  when you save the URL and again before every send, so a DNS change
  can't redirect deliveries into your network.
- **Protected secret.** The secret is stored encrypted, shown once and
  never written to logs.
- **Managed by admins only.** Only Hotel Admin and System Manager can
  manage webhooks. A Hotel Admin limited to some properties sees only
  those properties' webhooks.

Self-hosters testing with a receiver on the same machine can set
`"kamra_webhooks_allow_private": 1` in `site_config.json`. **Never** set it
in production.

## External POS room charges

Use this when a restaurant, bar or spa runs its own POS, not Kamra's. It
lets the POS post a ticket to an in-house guest's bill. The charge goes
through the same posting function as the front desk, with the same rules:

- the company billing rules pick the folio;
- the country pack decides the tax;
- alcohol (`is_alcohol: 1`) **always** goes to the guest's own folio,
  never a Company or Group folio.

**Set up:**

1. In **Settings → Staff & access**, create a user for the POS. Give it
   only the **POS Integrator** role, and limit it to this property.
2. IT issues the user's API key on **Developers**.
3. Optional: set a ceiling per ticket in **Settings → F&B → External
   POS**.

**Find the guest.** Only checked-in guests are returned, with the minimum
a cashier needs to confirm the charge:

```
POST /api/method/kamra.pos_interface.pos_room_lookup
{"property": "Your Property", "room": "204"}
→ [{"reservation": "RES-2026-00042", "room_number": "204",
    "guest_name": "Asha Rao", "check_out_date": "2026-10-21",
    "corporate": false, "room": "Your Property-204"}]
```

Search by `room` (number or id), `last_name` (2 or more letters), or both.
Kamra never returns the whole in-house list.

**Post the ticket:**

```
POST /api/method/kamra.pos_interface.pos_post_room_charge
{"property": "Your Property", "room": "204", "ticket_id": "BAR-1042",
 "amount": 1450, "description": "Rooftop bar", "charge_type": "Food & Beverage",
 "is_alcohol": 1, "outlet_name": "Rooftop bar"}
→ {"ok": true, "duplicate": false, "folio": "FOLIO-2026-00077",
   "folio_type": "Guest", "amount": 1450.0, "balance": 9120.0, ...}
```

- **`ticket_id` is the idempotency key** for the property.
  - Sending the same ticket again returns the first posting with
    `"duplicate": true`. Nothing is charged twice, even if two requests
    arrive at the same moment.
  - Reusing a ticket number for a different amount or stay is refused.
- **`charge_type`** must be one of: `Food & Beverage`, `Minibar`,
  `Laundry`, `Spa`, `Misc`. Room nights, fees and allowances stay with the
  hotel.
- **These are refused:**
  - a guest who is not checked in;
  - a room at another property;
  - an amount of zero or less;
  - a tax rate the country doesn't use;
  - an amount over the property's limit.
- **Every posting** appears as an *External POS Charge* record and in the
  Activity log, with the POS user who sent it. Subscribers also get a
  `folio.posted` webhook.

MCP clients have the same pair as the `pos_room_lookup` and
`pos_post_room_charge` tools.

## Channel manager

Kamra pushes availability and rates to OTAs, and receives their bookings,
through Channex.io, STAAH or AioSell. See
[Channel manager (OTA sync)](/channel-manager).

## Payments

Advances and folio balances can be paid by payment link. This is
available where the country pack supports a gateway, for example
Razorpay or Cashfree in India. The gateway calls Kamra back with a signed
webhook, and Kamra records the payment on the folio. Set it up in
**Settings → Payments**.

## Door locks

Kamra does not ship a lock vendor connector yet. It defines the interface
one plugs into, `kamra/door_lock.py`:

```python
from kamra.door_lock import DoorLockAdapter, KeyRequest, KeyResult

class AcmeAdapter(DoorLockAdapter):
    key = "acme"
    label = "Acme Locks (cloud)"
    supports_mobile_keys = True

    def issue_key(self, request: KeyRequest) -> KeyResult:
        # request.room_number, request.valid_from / valid_to, request.key_count
        ...
        return KeyResult(ok=True, adapter=self.key, key_ids=["card-881"])

    def revoke_keys(self, property, reservation, room) -> KeyResult:
        ...
        return KeyResult(ok=True, adapter=self.key)
```

Register the connector from your own Frappe app's `hooks.py`:

```python
kamra_door_lock_adapters = {"acme": "acme_kamra.locks.AcmeAdapter"}
```

Then pick it under **Settings → Front Desk → Door locks**. The built-in
`manual` adapter is the default: staff encode cards at the vendor's
encoder, and the desk gets an instruction to show.

A connector must follow these rules:

- **It never decides who gets a key.** Kamra calls it after check-in.
- **It gets only what it needs:** the room, the stay window and a key
  count. It never gets guest contact details or ID documents.
- **Credentials stay in its own encrypted settings.**
- **A failure comes back as a result**, `KeyResult(ok=False, message=...)`.
  It must never raise into check-in.

If you'd rather not run code inside Kamra, build the connector as
middleware outside it instead. Subscribe it to the `guest.checked_in` and
`guest.checked_out` webhooks.

## Accounting export

The **Accounting Export** screen (Finance, under Books) gives every
closed invoice in a date range as rows you can download. The API call is
`kamra.accounting.export_invoices`. The tax columns come from the country
pack: CGST/SGST in India, a single tax column in VAT countries. The rows
are ready for your books, for example Tally, Zoho Books or ERPNext. If ERPNext
is installed on the same site, see [ERPNext & Frappe HR](/self-hosting/erpnext-hr).
