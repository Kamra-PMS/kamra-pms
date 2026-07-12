# REST API basics

Every whitelisted function is a REST endpoint — the same governed layer
the UI and the AI use.

::: tip Try it in 2 minutes
Download the **[Postman collection](/kamra.postman_collection.json)**
(all 120 endpoints, organised by domain), set three collection variables —
`base_url` (your Kamra URL), `api_key`, `api_secret` — and every request
is ready to send. The complete endpoint list with parameters is in the
**[REST API reference](/api-reference)**.
:::

```
POST /api/method/kamra.api.<function>
Authorization: token <api_key>:<api_secret>
Content-Type: application/json
```

Generate keys from **Copilot → Connect** (per-user, role-scoped) or, for
service integrations, on the dedicated agent user.

## Frequently used endpoints

| Area | Endpoints |
| --- | --- |
| Selling | `get_quote` · `create_booking` · `create_group_booking` · `available_rooms` · `availability_calendar` |
| The day | `front_desk_snapshot` · `check_in` · `check_out` · `find_reservations` · `find_invoices` |
| Money | `get_folio` · `post_stay_charge` · `add_folio_payment` · `split_folio_charge` · `transfer_folio_charges` · `close_folio` · `run_night_audit` · `gstr1_rows` |
| Policies | `cancellation_preview` · `cancel_reservation` |
| Ops | `create_ticket` · `hk_queue` · `room_blocks` |
| Chain | `crs_search` (via `kamra.crs`) · `portfolio_dashboard` (via `kamra.dashboards`) |

Guest-facing (no auth) endpoints live in `kamra.public_api` — the booking
page, QR menus and self check-in run on them; they are rate-limited and
never trust caller-supplied prices.

Responses are JSON: `{"message": <return value>}`. Errors return an HTTP
4xx with a human-readable reason — surface it to your user as-is.
