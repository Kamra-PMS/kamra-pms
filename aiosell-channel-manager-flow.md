# Aiosell Channel Manager — Developer Guide

> How Kamra syncs with **Aiosell** (channel manager). Read this to understand the
> flow before touching the code. Companion files: `aiosell-api-context.md` (exact
> API/wire format) and `aiosell-sync-rules.md` (behavior rules).

---

## 1. What it does (the whole idea in two pipes)

Aiosell is the middleman between Kamra (the PMS) and every OTA (Booking.com,
Goibibo/MMT, Airbnb, Expedia…). There are exactly **two directions**:

```
  PIPE IN  — bookings come to Kamra
  ─────────────────────────────────
  Guest books/changes/cancels on an OTA
        │
        ▼
     Aiosell  (channel manager)
        │  POST webhook (action: book | modify | cancel)
        ▼
     Kamra    → creates / replaces / cancels the reservation


  PIPE OUT — availability & rates go to the OTAs
  ──────────────────────────────────────────────
  A room is booked, or a rate changes, in Kamra
        │
        ▼   push availability + rates
     Aiosell
        │
        ▼
  All connected OTAs update  → no double-booking
```

**Golden rule:** money & availability are computed **deterministically in Kamra**,
never by the OTA. An OTA booking obeys the exact same rules a front-desk booking does.

---

## 2. Architecture (the seam)

Kamra never talks to an OTA directly. It uses a provider-agnostic **seam**:

```
kamra/channels/*        ← ADAPTERS: protocol translation ONLY (aiosell, channex, staah)
kamra/channel_manager.py ← CORE: all consequences (booking creation, availability,
                           pricing, credit-note cancel, villa lockout, audit log)
```

Each adapter implements just two functions:

| Function | Direction | Purpose |
|----------|-----------|---------|
| `push_ari(conn, snapshot)` | Kamra → Aiosell | deliver availability + rates |
| `parse_webhook(conn, payload)` | Aiosell → Kamra | normalize an inbound booking event |

Everything with consequences lives in `channel_manager.py`, so all providers behave
identically.

### Key files
| File | Role |
|------|------|
| `kamra/channels/aiosell.py` | The Aiosell adapter — API calls, auth, webhook parsing, the `reservation_webhook` endpoint |
| `kamra/channel_manager.py` | The core — `ari_snapshot`, villa lockout, `_apply_event`, `process_webhook_events`, push triggers |
| `kamra/api.py` | Reused helpers — `_do_cancel` (credit note), `available_rooms` / `availability_calendar` (front-desk villa lock), `set_room_rate` (rate-push trigger) |
| `kamra/hooks.py` | `doc_events["Reservation"]` → `on_reservation_change` (Pipeline-1 trigger) |
| `kamra/kamra/doctype/reservation/reservation.py` | `validate_villa_lockout` — the write-time double-booking guard |
| `channel_manager_connection.json` | Connection settings (creds, hotelCode, PMS slug) |
| `channel_room_mapping` | Maps a Kamra Room Type ↔ Aiosell room/rateplan code |

---

## 3. Aiosell API (wire format)

- **Base URL:** `https://live.aiosell.com/api/v2/cm`
- **Auth:** HTTP Basic (`base64(username:password)`) — issued at partner onboarding.
- **Sandbox:** `hotelCode=sandbox-pms`, `partnerId=sample-pms`.

| Direction | Call | Body (key fields) |
|-----------|------|-------------------|
| Mapping | `GET /property_details/{hotelCode}?partnerId={pms}` | returns `hotel_id`, `rooms[].room_id`, `rooms[].rateplans[].rateplan_id` |
| Availability out | `POST /update/{pms}` | `{hotelCode, updates:[{startDate,endDate, rooms:[{roomCode, available}]}]}` |
| Rates out | `POST /update-rates/{pms}` | `{hotelCode, updates:[{startDate,endDate, rates:[{roomCode, rateplanCode, rate}]}]}` |
| Booking in | Aiosell POSTs to **our** webhook | `{action, hotelCode, channel, bookingId, checkin, checkout, amount{}, guest{}, rooms[]{roomCode, rateplanCode, occupancy{}, prices[]}}` |

`{pms}` = the partner slug Aiosell assigns. Ranges are **inclusive** and **upserts**.

---

## 4. PIPE IN — inbound bookings (Aiosell → Kamra)

**Endpoint we host:** `/api/method/kamra.channels.aiosell.reservation_webhook`

Flow when Aiosell POSTs a booking:

```
reservation_webhook(**kwargs)                         [aiosell.py]
  1. validate the inbound HTTP Basic auth header
  2. resolve the Channel Manager Connection by hotelCode
  3. log the raw payload
  4. respond {"success": true} IMMEDIATELY  (so Aiosell doesn't time out)
  5. frappe.enqueue → process_webhook_events(...)     [async, off the request path]

process_webhook_events(connection, payload)           [channel_manager.py]
  → provider.parse_webhook() normalizes the payload into events
  → for each event: _apply_event(conn, e)
  → applied atomically per booking; a bad line rolls the whole booking back + logs
```

`_apply_event` maps each action to the same path a human would take:

| action | Kamra behavior |
|--------|----------------|
| `book` | Create a Reservation (`source=OTA`, `ota_ref=bookingId`). Idempotent on `bookingId`. |
| `modify` | **Full replace** — overwrite the reservation's fields (never merge/patch). |
| `cancel` | Route through `api._do_cancel(..., issue_credit_note=1)` → free the room + issue a **6-month credit note** (no cash refund). |

Notes:
- **Multi-room booking:** one Reservation per `rooms[]` line; `ota_ref = bookingId` (single) or `bookingId-<n>` (multi). Cancel matches the whole set.
- **Guest fields are optional** — never reject a booking for missing name/email/phone.
- **OTA bookings are unassigned** — they carry a room *type*, not a physical room; staff assign the room at check-in.

---

## 5. PIPE OUT — availability & rates (Kamra → Aiosell)

Kamra computes a snapshot and pushes it. Triggered:
- **hourly** (cron `push_all_ari`),
- **after any reservation change** (`on_reservation_change` doc_event),
- **after a rate change** (`set_room_rate` → `enqueue_property_push`),
- **manually** (`push_ari(connection)`).

```
ari_snapshot(property, connection, days)              [channel_manager.py]
  for each mapped room type, per night:
     available = SIU capacity (if Sellable Units active)  else  physical rooms − bookings − holds
     rate      = pricing engine's 2-adult sell rate
  → _apply_villa_lockout(...)   (see §6)

push_ari(connection)
  → adapter.push_ari(conn, snapshot)
       → build_push_bodies() → POST /update (availability) + POST /update-rates (rates)
```

`build_push_bodies()` collapses consecutive same-value days into inclusive date ranges
(upserts), and only sends rates for room types that have a `rateplanCode` mapped.

---

## 6. Villa ↔ Room lockout (the key villa feature)

A property can be sold **room-by-room AND as the whole villa** (Entire Property). Those
must never clash. The lockout is bidirectional: **book the villa → all rooms close;
book any room → the villa closes.** A Room Type with `room_category = "Villa"` is the
whole-property bundle; every other room type is a member.

It's enforced in **three layers** (all consistent):

| Layer | Where | Purpose |
|-------|-------|---------|
| **Write-time guard** | `reservation.py :: validate_villa_lockout` | Kamra *rejects* a conflicting booking (manual + OTA + modify all run `validate()`) |
| **Front-desk availability** | `api.py :: available_rooms`, `availability_calendar` (via `_villa_lock_conflict`) | UI *shows* rooms as full when the villa is booked (and vice-versa) |
| **Push-side** | `channel_manager.py :: _apply_villa_lockout` | Kamra *pushes 0* to the OTAs so they never surface the conflict |

Per night: villa is sold → all member rooms push `0`; any member sold → villa pushes `0`.
A property with no Villa-category room type is a no-op (unchanged behavior).

---

## 7. Cancellation policy (no OTA exception)

On **every** cancel (direct or OTA-sourced), Kamra applies the property's money terms:
100% advance already collected → **no cash refund** → issues a **credit note valid
6 months** (a `CN-…` Discount Voucher). OTA cancels reuse the exact front-desk path
(`api._do_cancel(..., issue_credit_note=1)`), so there is no separate refund logic.

---

## 8. Setup / configuration

**Channel Manager Connection** (one per property):
| Field | Meaning |
|-------|---------|
| `provider` | `AioSell` |
| `external_property_id` | Aiosell **hotelCode** |
| `pms_slug` | Aiosell **partner id** (`{pms}` path segment) |
| `api_username` | Basic-auth username |
| `api_key` | Basic-auth password |
| `webhook_secret` | (unused for Aiosell — auth is Basic) |

**Channel Room Mapping** (one per room type): `room_type` ↔ `external_room_id` (roomCode)
+ `external_rate_id` (rateplanCode). Populate via `import_room_mappings(connection)`
(calls `property_details`) or by hand.

Credentials & `{pms}` stay as `<USERNAME>` / `<PASSWORD>` / `<PMS_SLUG>` placeholders
until partner onboarding — `push_ari` reports "pending" rather than faking a sync.

---

## 9. Testing

1. **Sandbox push** (before onboarding, on `apidocs.aiosell.com` "Try it"): property-details
   → inventory push → rate push; confirm the numbers land on `live.aiosell.com`.
2. **Webhook**: fire `book` / `modify` / `cancel` at `reservation_webhook`.
3. **Unit tests**: `bench --site <site> run-tests --app kamra --module kamra.tests.test_aiosell`
   (webhook parsing, villa lockout math, push-body shapes, credentials gate).
4. **One-command demo**: `bench --site <site> execute kamra.scripts.demo_aiosell.run`
   (book → modify → cancel + credit note + villa lockout) and `...demo_aiosell.preview`
   (shows the exact JSON Kamra would POST).

---

## 10. Go-live checklist

The code is one thing; going live also needs **credentials** and **deployment**:

1. **Register** the property on Aiosell; ask the partner team to **add Kamra as a partner PMS**.
2. Receive **API username + password**, **PMS slug**, and **hotelCode** per property.
3. Enter them on the Channel Manager Connection; create Room Mappings.
4. **Deploy the code** to the live server (`git pull` + `bench migrate` + `bench build`) —
   the `reservation_webhook` endpoint must exist on the live domain.
5. Give Aiosell the webhook URL: `https://<your-domain>/api/method/kamra.channels.aiosell.reservation_webhook`
6. Run one sandbox/test push and one test booking → confirm both directions.

> ⚠️ A webhook URL only works once the code is **deployed** to that server. Registering
> the property and deploying the code are independent — both are required to go live.

---

## 11. Quick reference

```
Inbound URL   /api/method/kamra.channels.aiosell.reservation_webhook
Adapter       kamra/channels/aiosell.py
Core          kamra/channel_manager.py
Villa guard   kamra/kamra/doctype/reservation/reservation.py :: validate_villa_lockout
Push trigger  hooks.py doc_events["Reservation"] → on_reservation_change
Cron          hooks.py "0 * * * *" → push_all_ari
Demo          kamra/scripts/demo_aiosell.py  (run / preview / reset)
Tests         kamra/tests/test_aiosell.py
Spec          aiosell-api-context.md   Rules   aiosell-sync-rules.md
```
