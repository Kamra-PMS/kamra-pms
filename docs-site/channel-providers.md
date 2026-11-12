# Guest channel providers (concierge API)

A channel provider runs the guest-facing agent on WhatsApp, web chat or
voice. Kamra gives it what a guest conversation needs, and nothing a guest
conversation should never have: hotel facts, the caller's own stay, a way
to raise requests and a way to book. It never reaches staff MCP tools,
folios or other guests' records.

## Set it up

1. IT creates a service account with the guest concierge scope (see
   [Connected apps](/connected-apps)). It can't be combined with staff
   scopes.

   ```python
   from kamra.service_accounts import create_service_account
   create_service_account("WhatsApp concierge", ["concierge.guest"], ["Kamra Demo Palace"])
   ```

2. On the property's **Channel Provider Connection**, set the property
   line in **Phone number**, a **Webhook secret**, and pick the account in
   **Concierge service account**.

3. Give the provider the API key and secret, and the webhook secret.

## How every request is signed

Each call is a `POST` with a JSON body and two credentials:

- `Authorization: token <api_key>:<api_secret>` (the concierge service account)
- `X-Kamra-Signature: <hex HMAC-SHA256 of the JSON body>` using the
  connection's webhook secret. Sign the body serialised with sorted keys
  (in Python: `json.dumps(body, sort_keys=True)`), the same scheme as the
  voice and messaging webhooks.

Every body carries:

| Field | What |
| --- | --- |
| `phone_number` | The property line. Picks the connection, which must be linked to this key. |
| `ts` | Unix time in seconds. Requests more than 5 minutes off are refused. |

A missing or wrong signature, a stale `ts`, a key that is not a concierge
key, or a connection linked to another key all get HTTP 403.

## Endpoints

All under `/api/method/kamra.agents_channels.`

### `concierge_context`

Facts the hotel entered: FAQs, house rules, pets, children and extra bed
policies, amenities, published experiences, outlets, directions and map
position, check-in and check-out times. Nothing about any guest.

### `stay_context`

Body: `guest_phone`. The caller's own current or next stay at this
property: `reservation`, `status`, dates, room type, adults, children,
first name, `stays_count`, `last_stay`, `vip`, `category`. No folio lines,
no other guests. A phone with no current or upcoming stay here gets
`{"found": false}`.

### `guest_request`

Body: `reservation`, `kind`, `note`, and `stay_token` or `otp`.

| `kind` | Becomes |
| --- | --- |
| `early_check_in`, `late_check_out` | A Front Desk stay instruction |
| `extra_bed` | A Housekeeping stay instruction |
| `airport_transfer` | A Transport stay instruction |
| `special_occasion` | A Concierge stay instruction |
| `housekeeping`, `room_service`, `maintenance`, `concierge`, `other` | A service ticket, source WhatsApp or Voice |

A phone match alone never changes a stay. Send the guest's `stay_token`
(the token in their pre-check-in link). Without one, Kamra sends a 6-digit
code to the phone on the booking (never to a number the caller names) and
replies `{"otp_required": true}`; send the request again with `otp`. A code
lasts 10 minutes and allows 5 tries. The code is never written to the log.

### `channel_book`

Body: `room_type`, `check_in_date`, `check_out_date`, `guest_name`,
`phone`, `adults`, `children`, and optional `email`, `meal_plan`,
`special_requests`, `voucher_code`, `child_ages`, `addons`. An
`idempotency_key` is required.

It is the same booking as the public booking page: the price comes from
the pricing engine (no amount is accepted), the booking shows source
**AI Agent** and the channel (for example WhatsApp), and a retry with the
same `idempotency_key` returns the same booking with
`idempotent_replay: 1`. When an advance is due and the property has a live
payment gateway, `payment_link` carries a pay-online link.

It has its own limit per connection: 60 bookings an hour, or
`kamra_channel_book_limit` in site config. The booking page's per-IP limit
is separate and unchanged.

## What the log keeps

Every call is in the Agent Action Log under the service account's name.
The voice and messaging webhooks keep the event, the provider's short
`summary` (up to 280 characters) and the conversation reference
(`message_id` or `call_id`), never the guest's message text or the call
transcript. These rows are cleared with the property's message retention
period (**Settings → Privacy & data**, **Clear message text after**).
