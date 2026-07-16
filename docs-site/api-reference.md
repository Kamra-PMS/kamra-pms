---
outline: 2
---

# REST API reference

Every endpoint below is a whitelisted function — the same governed layer
the UI and the AI use. **151 endpoints**, generated from the source
(`docs-site/gen_api.py`), so this page always matches the code.

## Calling convention

```
POST https://<your-kamra>/api/method/kamra.<module>.<function>
Authorization: token <api_key>:<api_secret>
Content-Type: application/json
```

- Get keys from **Copilot → Connect** (per-user, role-scoped) or the
  dedicated agent user for services.
- Responses: `{"message": <return value>}`. Errors are HTTP 4xx with a
  readable reason.
- **Try it in Postman:** [download the collection](/kamra.postman_collection.json),
  set `base_url`, `api_key` and `api_secret` collection variables, go.
- Endpoints marked **public** are `allow_guest` (no token; rate-limited).


## Core (front desk, folios, guests, rooms)

### `kamra.api.whoami` <Badge type='tip' text='public' />

**GET/POST**

Current user + roles - drives which modules the UI shows.

allow_guest so the SPA's initial "am I logged in?" probe returns
{user: "Guest"} cleanly instead of a 403 in the console.

### `kamra.api.developer_info`

**GET/POST** · roles: `System Manager`, `Administrator`

REST base URL + whether the current user already has an API key.

Drives the on-site Developers page. The secret itself is never returned
here - Frappe stores it hashed; it's only shown once, at generation time.

### `kamra.api.generate_api_key`

**POST** · roles: `System Manager`, `Administrator`

Generate (or rotate) the current user's REST API key + secret.

Self-service: acts only on the signed-in user, so any authenticated staff
member can mint a key scoped to their own roles. The secret is returned
once here and stored hashed thereafter.

### `kamra.api.set_room_rate`

**GET/POST** · roles: `Revenue Manager`, `Kamra Agent`

Set the nightly rate for a room type over a date range - bounded by
the owner's Rate Guardrails (PRD FR-30). This is the Revenue Agent's
write tool: it can never price outside the rails.

Guardrails still clamp the rate; the change is recorded in the action log.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `room_type` | yes |  |
| `start_date` | yes |  |
| `end_date` | yes |  |
| `rate` | yes |  |
| `reason` | no | `''` |
| `agent` | no | `None` |

### `kamra.api.owner_briefing`

**GET/POST**

Deterministic numbers for the owner's morning briefing (PRD FR-70).
An LLM turns this into prose; it never invents the figures.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `date` | no | `None` |

### `kamra.api.setup_property`

**GET/POST**

One-call property onboarding - the wizard's submit button and the
migration agent's tool. payload = {property:{property_name, city,
gstin?, phone?, ...}, room_types:[{code,name,base_price,adults?,
extra_adult_price?,tax_percent?}], rooms:[{room_type_code,
numbers:["101","102"]}], meal_plans:[{code,label?,price_per_adult}]}

| Param | Required | Default |
| --- | --- | --- |
| `payload` | yes |  |

### `kamra.api.import_bookings`

**GET/POST**

Bulk booking import - the switch-over tool. Each row: {guest_name,
phone?, room_type_code, check_in, check_out, adults?, children?,
amount_after_tax?, channel?, status?}. Rows with a fixed amount keep
it (auto_price off); others are priced by the engine.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `bookings` | yes |  |

### `kamra.api.registration_card`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Everything the printed GRC (guest registration card) needs.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |

### `kamra.api.cash_summary`

**GET/POST** · roles: `Finance`, `Front Desk`, `Kamra Agent`

Cashier reconciliation: what the system says was collected today,
per payment mode - the number the drawer must match at shift close.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `date` | no | `None` |

### `kamra.api.record_advance`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Advance/deposit against a Confirmed booking - opens the folio early
so the money sits on the stay from day one (GM gap: deposits arrive at
booking, not at check-in).

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `amount` | yes |  |
| `mode` | no | `'UPI'` |
| `reference` | no | `None` |

### `kamra.api.folio_payment_link`

**GET/POST** · roles: `Finance`, `Front Desk`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `folio` | yes |  |

### `kamra.api.hk_queue`

**GET/POST** · roles: `Housekeeping`, `Front Desk`, `Kamra Agent`

The housekeeper's phone view: prioritized task queue + room board.
Checkout cleans for rooms with an arrival today jump the queue.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.api.hk_update_task`

**GET/POST** · roles: `Housekeeping`, `Front Desk`, `Kamra Agent`

Start or complete a housekeeping task from the phone.

| Param | Required | Default |
| --- | --- | --- |
| `task` | yes |  |
| `status` | yes |  |

### `kamra.api.hk_assign_task`

**POST** · roles: `Front Desk`, `Housekeeping`, `Kamra Agent`

A supervisor hands a task to a specific housekeeper (awaits accept).

| Param | Required | Default |
| --- | --- | --- |
| `task` | yes |  |
| `user` | yes |  |

### `kamra.api.hk_claim_task`

**POST** · roles: `Housekeeping`, `Front Desk`, `Kamra Agent`

A housekeeper takes an unassigned task from the pool for themselves.

| Param | Required | Default |
| --- | --- | --- |
| `task` | yes |  |

### `kamra.api.hk_accept_task`

**POST** · roles: `Housekeeping`, `Front Desk`, `Kamra Agent`

The assigned housekeeper accepts the task handed to them.

| Param | Required | Default |
| --- | --- | --- |
| `task` | yes |  |

### `kamra.api.hk_reject_task`

**POST** · roles: `Housekeeping`, `Front Desk`, `Kamra Agent`

Decline a task - it drops back into the pool for someone else,
keeping the reason on record.

| Param | Required | Default |
| --- | --- | --- |
| `task` | yes |  |
| `reason` | no | `''` |

### `kamra.api.hk_log_item`

**POST** · roles: `Housekeeping`, `Front Desk`, `Kamra Agent`

A floor housekeeper logs a lost/found/missing/damaged item from the
phone. Lands in the Lost & Found register for the desk to reconcile.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `item_description` | yes |  |
| `condition` | no | `'Found'` |
| `room` | no | `None` |

### `kamra.api.hk_post_consumable`

**POST** · roles: `Housekeeping`, `Front Desk`, `Kamra Agent`

Housekeeping posts what they find in the room - minibar consumption or
laundry - onto the in-house guest's folio. Scoped to those two types so
the floor can't touch discounts, allowances or room charges.

| Param | Required | Default |
| --- | --- | --- |
| `room` | yes |  |
| `charge_type` | yes |  |
| `description` | yes |  |
| `amount` | yes |  |

### `kamra.api.create_ticket`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Create a guest-request ticket. This is also the agent tool for
'guest wants towels / AC is broken' - PRD FR-42.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `subject` | yes |  |
| `category` | yes |  |
| `priority` | no | `'Medium'` |
| `room` | no | `None` |
| `reservation` | no | `None` |
| `guest` | no | `None` |
| `description` | no | `None` |
| `source` | no | `'Manual'` |

### `kamra.api.tickets_list`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `show_closed` | no | `0` |

### `kamra.api.advance_ticket`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `ticket` | yes |  |
| `status` | yes |  |
| `resolution_note` | no | `None` |

### `kamra.api.get_folio`

**GET/POST** · roles: `Finance`, `Front Desk`, `Kamra Agent`

Folio for a reservation - opens one if the guest is checked in.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |

### `kamra.api.add_folio_charge`

**GET/POST** · roles: `Finance`, `Front Desk`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `folio` | yes |  |
| `charge_type` | yes |  |
| `description` | yes |  |
| `amount` | yes |  |
| `gst_rate` | no | `0` |
| `posting_date` | no | `None` |
| `is_alcohol` | no | `0` |
| `reservation` | no | `None` |

### `kamra.api.add_folio_payment`

**GET/POST** · roles: `Finance`, `Front Desk`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `folio` | yes |  |
| `mode` | yes |  |
| `amount` | yes |  |
| `reference` | no | `None` |
| `pin` | no | `None` |

### `kamra.api.void_folio_charge`

**GET/POST** · roles: `Finance`, `Front Desk`, `Kamra Agent`

Remove a wrong charge line from an open folio (the bill-correction
path). PIN-guarded like other money actions for humans; agents are
accountable through the action log.

| Param | Required | Default |
| --- | --- | --- |
| `folio` | yes |  |
| `charge_row` | yes |  |
| `reason` | no | `''` |
| `pin` | no | `None` |

### `kamra.api.post_stay_charge`

**GET/POST** · roles: `Finance`, `Front Desk`, `Kamra Agent`

Post a charge to a stay letting the billing rules pick the folio -
corporate room/meals land on the Company folio, alcohol and anything
unruled lands on the guest. The agent-facing way to post charges.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `charge_type` | yes |  |
| `description` | yes |  |
| `amount` | yes |  |
| `gst_rate` | no | `0` |
| `is_alcohol` | no | `0` |

### `kamra.api.set_billing_rules`

**GET/POST** · roles: `Finance`, `Front Desk`, `Kamra Agent`

Replace a company's billing rules. rules = [{charge_type, pay_by}].

| Param | Required | Default |
| --- | --- | --- |
| `company` | yes |  |
| `rules` | yes |  |

### `kamra.api.get_billing_rules`

**GET/POST** · roles: `Finance`, `Front Desk`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `company` | yes |  |

### `kamra.api.update_occupants`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Replace the stay's occupant register.
occupants = [{full_name, age, gender, nationality, id_type, id_number, phone}]

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `occupants` | yes |  |

### `kamra.api.split_folio`

**GET/POST** · roles: `Finance`, `Front Desk`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `folio_type` | no | `'Extra'` |

### `kamra.api.delete_folio`

**POST** · roles: `Finance`, `Front Desk`, `Kamra Agent`

Remove an empty split/extra folio created by mistake.

Guards: never the primary Guest folio, and only when it carries no
charges and no payments - money is never dropped this way.

| Param | Required | Default |
| --- | --- | --- |
| `folio` | yes |  |

### `kamra.api.transfer_folio_charge`

**GET/POST** · roles: `Finance`, `Front Desk`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `from_folio` | yes |  |
| `charge_row` | yes |  |
| `to_folio` | yes |  |

### `kamra.api.transfer_folio_charges`

**GET/POST** · roles: `Finance`, `Front Desk`, `Kamra Agent`

Bulk move: several charge lines to another folio of the stay.

| Param | Required | Default |
| --- | --- | --- |
| `from_folio` | yes |  |
| `charge_rows` | yes |  |
| `to_folio` | yes |  |

### `kamra.api.split_folio_charge`

**GET/POST** · roles: `Finance`, `Front Desk`, `Kamra Agent`

Split one charge line between two folios - by percent or amount.

| Param | Required | Default |
| --- | --- | --- |
| `from_folio` | yes |  |
| `charge_row` | yes |  |
| `to_folio` | yes |  |
| `percent` | no | `None` |
| `amount` | no | `None` |

### `kamra.api.reservation_folios`

**GET/POST** · roles: `Finance`, `Front Desk`, `Kamra Agent`

All folios of a stay (guest + splits) with balances - plus the
group master folio when the stay belongs to a group, so charges can
be moved between a guest's bill and the company's consolidated one.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |

### `kamra.api.group_master_folio`

**GET/POST** · roles: `Finance`, `Front Desk`, `Kamra Agent`

Get-or-create the group's consolidated company folio.

| Param | Required | Default |
| --- | --- | --- |
| `group_booking` | yes |  |

### `kamra.api.group_folios`

**GET/POST** · roles: `Finance`, `Front Desk`, `Kamra Agent`

The whole group's billing picture: the master folio plus every
member reservation's folios, with balances.

| Param | Required | Default |
| --- | --- | --- |
| `group_booking` | yes |  |

### `kamra.api.close_folio`

**GET/POST** · roles: `Finance`, `Front Desk`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `folio` | yes |  |
| `pin` | no | `None` |

### `kamra.api.post_allowance`

**POST** · roles: `Finance`, `Front Desk`, `Kamra Agent`

Write off part of a bill against a specific folio, with a reason.

| Param | Required | Default |
| --- | --- | --- |
| `folio` | yes |  |
| `amount` | yes |  |
| `reason` | yes |  |
| `gst_rate` | no | `0` |
| `pin` | no | `None` |

### `kamra.api.part_settle_folio`

**POST** · roles: `Finance`, `Front Desk`, `Kamra Agent`

Interim invoice mid-stay: freeze the paid folio, open a fresh one.

| Param | Required | Default |
| --- | --- | --- |
| `folio` | yes |  |
| `pin` | no | `None` |

### `kamra.api.cancel_invoice`

**POST** · roles: `Finance`, `Front Desk`, `Kamra Agent`

Void an invoice into the register and reopen the folio for correction.

| Param | Required | Default |
| --- | --- | --- |
| `folio` | yes |  |
| `reason` | yes |  |
| `pin` | no | `None` |

### `kamra.api.folio_invoice`

**GET/POST** · roles: `Finance`, `Front Desk`, `Kamra Agent`

Everything a GST invoice print needs, with the multi-rate breakup.

| Param | Required | Default |
| --- | --- | --- |
| `folio` | yes |  |

### `kamra.api.run_night_audit`

**GET/POST** · roles: `Front Desk`, `Finance`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `business_date` | no | `None` |

### `kamra.api.gstr1_rows`

**GET/POST**

Invoice-level rows for a GSTR-1 style export (v0: B2C summary).
Filter by property - each GSTIN files its own return.

| Param | Required | Default |
| --- | --- | --- |
| `from_date` | yes |  |
| `to_date` | yes |  |
| `property` | no | `None` |

### `kamra.api.guests_with_stats`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Guest list with stay stats - the CRM index.

| Param | Required | Default |
| --- | --- | --- |
| `search` | no | `None` |

### `kamra.api.guest_search`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Typeahead for attaching a booking to an existing profile.

| Param | Required | Default |
| --- | --- | --- |
| `q` | yes |  |

### `kamra.api.merge_guests`

**GET/POST**

Merge a duplicate profile into the surviving one: every linked
document is repointed, missing contact fields are copied over, and
the duplicate is deleted. Money is untouched - folios keep their
lines and totals.

| Param | Required | Default |
| --- | --- | --- |
| `source` | yes |  |
| `target` | yes |  |

### `kamra.api.anonymize_guest`

**GET/POST**

Right-to-erasure: strip everything that identifies the person while
keeping stays and bills intact for the books. Irreversible.

| Param | Required | Default |
| --- | --- | --- |
| `guest` | yes |  |

### `kamra.api.guest_journey`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

One guest's full story: profile, stats, chronological timeline.
This is the CRM detail view - and the context an AI concierge loads
before speaking to a returning guest.

| Param | Required | Default |
| --- | --- | --- |
| `guest` | yes |  |

### `kamra.api.my_properties`

**GET/POST**

Properties the current user may work with. frappe.get_list applies
User Permissions, so a property-restricted user sees only theirs.

### `kamra.api.front_desk_snapshot`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Everything the front desk needs for one day, in one call.

| Param | Required | Default |
| --- | --- | --- |
| `property` | no | `None` |
| `date` | no | `None` |

### `kamra.api.find_reservations`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`, `Finance`, `Revenue Manager`

Search reservations by guest name, room number, or reference - optionally
filtered by status. The way to resolve a room number or a name to an actual
reservation before acting on it.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `query` | no | `None` |
| `status` | no | `None` |
| `limit` | no | `20` |

### `kamra.api.find_invoices`

**GET/POST** · roles: `Front Desk`, `Finance`, `Revenue Manager`, `Kamra Agent`

Resolve an invoice number (or partial) to its folio and stay, so the
command palette can jump straight from 'INV-KDP-26-00042' to the bill.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `query` | no | `None` |
| `limit` | no | `8` |

### `kamra.api.reservation_detail`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`, `Finance`, `Revenue Manager`

Everything about one booking in a single call - stay, money, guest,
booker and the actions currently available. Powers the reservation drawer.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |

### `kamra.api.check_in`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `room` | no | `None` |

### `kamra.api.cancellation_preview`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

What cancelling right now would cost - shown before confirming.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |

### `kamra.api.cancel_reservation`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Cancel a booking, applying the property's cancellation policy:
free outside the window, else the configured fee lands on the folio.
Issues a cancellation number the guest can hold on to. Pass
waive_fee=1 to cancel graciously (logged).

The cancellation is recorded in the action log.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `reason` | no | `'Guest request'` |
| `note` | no | `None` |
| `waive_fee` | no | `0` |
| `agent` | no | `None` |

### `kamra.api.cancellation_letter`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Everything the printable cancellation confirmation needs.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |

### `kamra.api.check_out`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |

### `kamra.api.set_housekeeping_status`

**GET/POST** · roles: `Housekeeping`, `Front Desk`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `room` | yes |  |
| `status` | yes |  |

### `kamra.api.availability_calendar`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Per room-type, per date: rooms available and the 2-adult rate.
Powers the calendar view and, later, the agent's availability tool.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `start_date` | no | `None` |
| `days` | no | `14` |

### `kamra.api.tape_chart`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Rooms × dates grid with reservation bars - the front desk's home.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `start_date` | no | `None` |
| `days` | no | `14` |

### `kamra.api.send_precheckin_link`

**POST** · roles: `Front Desk`, `Kamra Agent`

Send the guest their self check-in link (mints a token if needed). Sends
over a connected channel when there is one; otherwise returns the link for
the desk to share. Marks when it went out so the arrivals board can show it.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `channel` | no | `'WhatsApp'` |

### `kamra.api.set_stay_times`

**POST** · roles: `Front Desk`, `Kamra Agent`

Set the planned arrival (ETA) and departure (ETD) times for any stay.
These drive the hotel-position view on the tape chart: back-to-back
rooms conflict when the incoming guest lands before the outgoing one
leaves, and the day's arrival flow is planned around them.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `eta` | no | `None` |
| `etd` | no | `None` |

### `kamra.api.set_day_use_times`

**POST** · roles: `Front Desk`, `Kamra Agent`

Set planned check-in/out times for a day-use booking (drives the hourly
tape view).

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `from_time` | yes |  |
| `to_time` | yes |  |

### `kamra.api.position_briefing`

**GET/POST** · roles: `Front Desk`, `Finance`, `Kamra Agent`

The GM / front-desk position briefing - what the copilot reads out
at the morning meeting: today's occupancy against the overbooking
ceiling, arrivals with ETAs, departures with ETDs and balances,
back-to-back conflicts, the demand tier pricing is applying, and a
7-day outlook.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `date` | no | `None` |

### `kamra.api.hurdle_rates`

**GET/POST** · roles: `Front Desk`, `Finance`, `Kamra Agent`

The demand tiers: at each occupancy threshold, the premium applied
and the minimum sell rate enforced.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.api.save_hurdle_rate`

**POST** · roles: `Front Desk`, `Finance`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `occupancy_from` | yes |  |
| `premium_pct` | no | `0` |
| `min_rate` | no | `0` |
| `room_type` | no | `None` |
| `name` | no | `None` |

### `kamra.api.delete_hurdle_rate`

**POST** · roles: `Front Desk`, `Finance`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `name` | yes |  |

### `kamra.api.tape_chart_hourly`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Single-day, rooms x hours. Day-use bookings sit at their planned times;
an overnight stay covering this day shows as a full-width occupied band.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `date` | no | `None` |

### `kamra.api.venue_calendar`

**GET/POST** · roles: `Front Desk`, `Revenue Manager`, `Kamra Agent`

Venues × dates with their bookings - the banquet/function diary. Shows
each venue's schedule so you can see availability and spot conflicts.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `start_date` | no | `None` |
| `days` | no | `14` |

### `kamra.api.move_reservation`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Room move - mid-stay or before arrival. Overlap guard re-runs.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `new_room` | yes |  |

### `kamra.api.amend_stay`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Extend / shorten a stay. Re-prices when auto_price is on; the
overlap guard validates the new window.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `check_in_date` | yes |  |
| `check_out_date` | yes |  |

### `kamra.api.booking_options`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Everything the booking form needs to render its dropdowns.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.api.get_quote`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `room_type` | yes |  |
| `check_in_date` | yes |  |
| `check_out_date` | yes |  |
| `adults` | no | `2` |
| `children` | no | `0` |
| `meal_plan` | no | `None` |
| `rate_plan` | no | `None` |
| `voucher_code` | no | `None` |

### `kamra.api.create_booking`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

One-call booking: attach to an existing guest profile when given,
else dedup by phone / create one. Optional auto room assignment,
voucher applied, price computed by the engine.

waitlist=1 parks the stay with no room and status Waitlist - for dates
that are sold out or restricted; promote it later when a room frees.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `room_type` | yes |  |
| `check_in_date` | yes |  |
| `check_out_date` | yes |  |
| `guest_name` | yes |  |
| `phone` | no | `None` |
| `adults` | no | `2` |
| `children` | no | `0` |
| `meal_plan` | no | `None` |
| `rate_plan` | no | `None` |
| `voucher_code` | no | `None` |
| `booking_type` | no | `'Individual'` |
| `company` | no | `None` |
| `group_booking` | no | `None` |
| `source` | no | `'Manual'` |
| `assign_room` | no | `1` |
| `travel_agent` | no | `None` |
| `booked_by_name` | no | `None` |
| `booked_by_phone` | no | `None` |
| `booker_relation` | no | `None` |
| `contact_preference` | no | `None` |
| `guest` | no | `None` |
| `waitlist` | no | `0` |
| `addons` | no | `None` |

### `kamra.api.waitlist`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`, `Revenue Manager`

All waitlisted stays for the property, by arrival date.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.api.promote_waitlist`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Promote a waitlisted stay to Confirmed when a room is free for its
dates. Assigns the first free room; the overlap guard validates it.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |

### `kamra.api.waitlist_ready`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Waitlisted stays that CAN now be accommodated - a room is free for
their dates. This is the signal the voice/WhatsApp agent watches so it
can proactively reach the guest the moment a room opens.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.api.create_group_booking`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Create a Group Booking plus one reservation per requested room.
`rooms` = [{"room_type": &lt;name>, "count": 2}, ...] (JSON string ok).

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `group_name` | yes |  |
| `check_in_date` | yes |  |
| `check_out_date` | yes |  |
| `rooms` | yes |  |
| `guest_name` | yes |  |
| `phone` | no | `None` |
| `company` | no | `None` |
| `meal_plan` | no | `None` |
| `rate_plan` | no | `None` |

### `kamra.api.available_rooms`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Rooms of a type with no overlapping live reservation - the same
logic the double-booking guard enforces, exposed as a query. Confirmed
group blocks hold their unsold rooms out of general sale; pass the
group to book against its own block.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `room_type` | yes |  |
| `check_in_date` | yes |  |
| `check_out_date` | yes |  |
| `group_booking` | no | `None` |

### `kamra.api.room_blocks`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Rooms held out of sale (house use, VIP, maintenance).

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `active_only` | no | `1` |

### `kamra.api.create_room_block`

**POST** · roles: `Front Desk`, `Kamra Agent`

Hold a room out of sale for a date range. Refused if the room is
already booked in that window (move the guest first).

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `room` | yes |  |
| `from_date` | yes |  |
| `to_date` | yes |  |
| `reason` | no | `'House Use'` |
| `note` | no | `None` |

### `kamra.api.release_room_block`

**POST** · roles: `Front Desk`, `Kamra Agent`

Free a held room before its end date (the room returns to sale).

| Param | Required | Default |
| --- | --- | --- |
| `name` | yes |  |

### `kamra.api.cashier_pin_status`

**GET/POST** · roles: `Finance`, `Front Desk`, `Revenue Manager`, `Housekeeping`

Does this property demand a PIN on money actions, and does the
signed-in user have one set yet?

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.api.set_cashier_pin`

**POST** · roles: `Finance`, `Front Desk`, `Revenue Manager`, `Housekeeping`

Set or change your own cashier PIN (4-8 digits). Changing an existing
PIN needs the current one.

| Param | Required | Default |
| --- | --- | --- |
| `pin` | yes |  |
| `current_pin` | no | `None` |

### `kamra.api.group_detail`

**GET/POST** · roles: `Front Desk`, `Revenue Manager`, `Kamra Agent`

Everything Group Rooms Control needs: the block, per-type pickup,
the rooming list, the tied event and the master folio.

| Param | Required | Default |
| --- | --- | --- |
| `group_booking` | yes |  |

### `kamra.api.save_group_blocks`

**POST** · roles: `Front Desk`, `Revenue Manager`, `Kamra Agent`

Set the room block (list of {room_type, rooms_blocked, block_rate})
and optionally the cutoff/status. Confirmed blocks hold inventory.

| Param | Required | Default |
| --- | --- | --- |
| `group_booking` | yes |  |
| `blocks` | yes |  |
| `cutoff_date` | no | `None` |
| `status` | no | `None` |

### `kamra.api.pickup_group_room`

**POST** · roles: `Front Desk`, `Kamra Agent`

Name a guest into the block: creates a reservation on the group's
dates against its held inventory.

| Param | Required | Default |
| --- | --- | --- |
| `group_booking` | yes |  |
| `room_type` | yes |  |
| `guest_name` | yes |  |
| `phone` | no | `None` |
| `adults` | no | `2` |
| `children` | no | `0` |

### `kamra.api.create_group_block`

**POST** · roles: `Front Desk`, `Revenue Manager`, `Kamra Agent`

One call drafts the whole piece of MICE business: the group, its room
block, and (optionally) the banquet event - the agent wedge: an inquiry
agent turns "30 rooms + a 200-pax wedding on Dec 12" into a proposal.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `group_name` | yes |  |
| `check_in_date` | yes |  |
| `check_out_date` | yes |  |
| `blocks` | yes |  |
| `company` | no | `None` |
| `cutoff_date` | no | `None` |
| `venue` | no | `None` |
| `event_type` | no | `None` |
| `event_date` | no | `None` |
| `attendees` | no | `0` |
| `customer_phone` | no | `None` |
| `notes` | no | `None` |

### `kamra.api.my_connector_credentials`

**POST** · roles: `Front Desk`, `Finance`, `Revenue Manager`, `Housekeeping`

Personal MCP credentials for connecting Claude (or any MCP client)
AS YOURSELF. The key acts with exactly your roles - Frappe enforces the
same gates as the UI, so a front-desk connection can do front-desk
things and nothing more. Regenerating invalidates the old secret.

Platform-wide / service keys stay on the Developers page (IT admin).

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.api.linked_records`

**GET/POST** · roles: `Front Desk`, `Finance`, `Revenue Manager`, `Housekeeping`

The connective tissue: for any record, everything it's attached to -
guest, reservation(s), folio(s), company, group, event - so every screen
can offer one-tap paths to billing and editing. One endpoint, all types.

| Param | Required | Default |
| --- | --- | --- |
| `doctype` | yes |  |
| `name` | yes |  |

### `kamra.api.property_locale`

**GET/POST** · roles: `Front Desk`, `Finance`, `Revenue Manager`, `Housekeeping`, `Kamra Agent`

Currency, number locale and tax vocabulary for this property, from its
localization pack. Drives the frontend's money formatting and tax dropdowns
so no screen hardcodes ₹ or GST %.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |


## Restaurant POS & kitchen

### `kamra.pos.outlets`

**GET/POST**

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.pos.pos_menu`

**GET/POST**

The digital menu for an outlet: available items grouped by category.

| Param | Required | Default |
| --- | --- | --- |
| `outlet` | yes |  |

### `kamra.pos.create_order`

**POST**

Captain takes an order. If a room is given but no reservation, the
in-house stay is resolved so it can post to the folio later. Takeaway
and delivery carry the customer's details instead of a table/room.

| Param | Required | Default |
| --- | --- | --- |
| `outlet` | yes |  |
| `items` | yes |  |
| `property` | no | `None` |
| `room` | no | `None` |
| `reservation` | no | `None` |
| `table_no` | no | `None` |
| `source` | no | `'Manual'` |
| `notes` | no | `None` |
| `order_type` | no | `None` |
| `guests` | no | `None` |
| `customer_name` | no | `None` |
| `customer_phone` | no | `None` |
| `delivery_address` | no | `None` |

### `kamra.pos.open_orders`

**GET/POST**

Every running tab at an outlet - the tables/rooms being served right
now, so a captain can juggle several at once.

| Param | Required | Default |
| --- | --- | --- |
| `outlet` | yes |  |

### `kamra.pos.table_map`

**GET/POST**

The table view a captain starts from: every table at the outlet with
its live state - vacant, running (open bill), fired (KOT in the kitchen)
or ready (everything prepared, awaiting service/settle). A table holds
any number of bills (separate parties, split bills); the tile carries
them all and shows the most urgent state.

| Param | Required | Default |
| --- | --- | --- |
| `outlet` | yes |  |

### `kamra.pos.reserve_table`

**POST**

Reserve a table - it shows as Reserved on the map from an hour
before the time until it's seated, cancelled or marked a no-show.

| Param | Required | Default |
| --- | --- | --- |
| `outlet` | yes |  |
| `table_no` | yes |  |
| `guest_name` | yes |  |
| `reserved_at` | yes |  |
| `phone` | no | `None` |
| `party_size` | no | `None` |
| `notes` | no | `None` |

### `kamra.pos.set_reservation`

**POST**

Seat / cancel / no-show a table reservation.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `status` | yes |  |

### `kamra.pos.mark_table_clean`

**POST**

Housekeeping done - the table goes back to vacant on the map.

| Param | Required | Default |
| --- | --- | --- |
| `outlet` | yes |  |
| `table_no` | yes |  |

### `kamra.pos.recent_orders`

**GET/POST**

The outlet's latest bills, newest first - open or settled - so a
captain can jump back to a running bill or reprint a settled one.

| Param | Required | Default |
| --- | --- | --- |
| `outlet` | yes |  |
| `limit` | no | `8` |

### `kamra.pos.split_order`

**POST**

Split a bill: move the chosen lines to a new bill on the same table
(or a named one) - separate bills for two parties sharing a table, or
one party paying separately. Fired lines keep their kitchen status, and
the two bills conserve the original total.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |
| `item_rows` | yes |  |
| `table_no` | no | `None` |

### `kamra.pos.order_detail`

**GET/POST**

One order's full contents - to load a running tab back into the till.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |

### `kamra.pos.add_items`

**POST**

Add rounds to a running tab - new lines are priced from the menu and
start as New (a later fire_kot sends them to the kitchen).

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |
| `items` | yes |  |

### `kamra.pos.confirm_order`

**POST**

Captain confirmation - a guest's QR order isn't fired to the kitchen
until a captain has vetted it.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |

### `kamra.pos.apply_discount`

**POST**

The guest-discount popup - a captain grants a discount with a reason.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |
| `amount` | yes |  |
| `reason` | no | `''` |

### `kamra.pos.fire_kot`

**POST**

Send the order to the kitchen: new lines become Fired and show on the
kitchen display. Stamps the KOT number (a daily sequence per outlet) and
returns just-fired lines so the till can print the thermal KOT ticket.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |

### `kamra.pos.kitchen_queue`

**GET/POST**

The kitchen display: fired orders with items still to prepare. Scope
to one outlet (each restaurant's own kitchen) and/or one station.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `outlet` | no | `None` |
| `station` | no | `None` |

### `kamra.pos.mark_prepared`

**POST**

Kitchen marks one line (or the whole order) prepared.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |
| `item_row` | no | `None` |

### `kamra.pos.deliver_order`

**POST**

Order served - moves to Delivered, which posts it to the room folio
(controller) when there's a linked stay.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |

### `kamra.pos.pay_order`

**POST**

Settle a bill at the outlet (walk-ins, takeaway - or a guest who'd
rather pay now than post to the room). Records the payment mode and
closes the order without touching any folio.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |
| `mode` | yes |  |

### `kamra.pos.mark_nc`

**POST**

Mark a bill NC (no charge / complimentary). Needs who authorized it
(captain, chef, GM, management…) and takes a free-text reference (the
occasion, the complaint ticket, the promise made). The items still fire
to the kitchen and print on the KOT - the bill just closes at zero and
never touches a folio. `undo=1` lifts it.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |
| `authorized_by` | yes |  |
| `note` | no | `''` |
| `undo` | no | `0` |

### `kamra.pos.cancel_order`

**POST**

Cancel a running order - needs a reason (it's kept on the order for
the audit trail). Closed orders can't be cancelled.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |
| `reason` | yes |  |

### `kamra.pos.void_item`

**POST**

Void one line with a reason - the line stays on the order (struck
through, amount zero) so the KOT-vs-bill audit holds up.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |
| `item_row` | yes |  |
| `reason` | yes |  |

### `kamra.pos.bill_data`

**GET/POST**

Everything the thermal bill print needs: outlet and property names,
live lines, the discount, and the CGST/SGST split at the outlet's rate.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |


## Laundry (housekeeping)

### `kamra.laundry.laundry_rates`

**GET/POST** · roles: `Finance`

The property's laundry price list (the card the attendant quotes
from). Grouped by item for the pickers.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.laundry.save_laundry_rate`

**POST**

Add or edit one line of the rate card.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `item_name` | yes |  |
| `service_type` | yes |  |
| `rate` | yes |  |
| `express_rate` | no | `None` |
| `name` | no | `None` |
| `disabled` | no | `0` |

### `kamra.laundry.delete_laundry_rate`

**POST**

| Param | Required | Default |
| --- | --- | --- |
| `name` | yes |  |

### `kamra.laundry.request_pickup`

**POST**

Log that a guest wants laundry picked up - it lands on the floor
team's queue. Items are counted at the door, not here. A House order
(staff uniforms / hotel linen) needs no room or guest and is never billed.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `room` | no | `None` |
| `notes` | no | `None` |
| `express` | no | `0` |
| `order_type` | no | `'Guest'` |
| `house_label` | no | `None` |

### `kamra.laundry.collect_laundry`

**POST**

The attendant counts the bag with the guest. Prices come from the
rate card (express uses the express column, or 1.5x). Pass `order` to
fulfil a pickup request, or omit it to log a walk-up collection. A House
walk-up (uniforms / linen) needs no room or guest and is never billed.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `room` | no | `None` |
| `items` | no | `None` |
| `order` | no | `None` |
| `express` | no | `None` |
| `notes` | no | `None` |
| `order_type` | no | `'Guest'` |
| `house_label` | no | `None` |
| `complimentary` | no | `0` |

### `kamra.laundry.laundry_status`

**POST**

Move the bag along: Collected -> In Process -> Ready.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |
| `status` | yes |  |

### `kamra.laundry.return_items`

**POST**

Tick items back in as they return from the laundry. rows =
{child_row_name: returned_qty} - counts, not deltas.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |
| `rows` | yes |  |

### `kamra.laundry.deliver_laundry`

**POST**

Hand the bag back and bill the stay. If pieces are still pending, a
shortage note is required - the discrepancy is recorded, never silent.
Posting rides the governed agent path (HK can only bill laundry).

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |
| `shortage_note` | no | `None` |

### `kamra.laundry.cancel_laundry`

**POST**

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |
| `reason` | yes |  |

### `kamra.laundry.laundry_board`

**GET/POST** · roles: `Finance`

Everything the floor and the desk need at a glance: open bags by
status with piece counts and what's still pending, plus the last few
delivered ones for reprints/queries.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.laundry.laundry_revenue`

**GET/POST** · roles: `Finance`, `Front Desk`, `Hotel Admin`, `Kamra Agent`

Delivered-laundry revenue over the last N days, with a per-service
breakdown. Only billed guest orders count as revenue; House and
complimentary bags are counted as volume but earn nothing.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `days` | no | `30` |


## Migration (CSV import)

### `kamra.migrate.preview_import`

**POST**

Dry run: how the file's columns map, which date convention was
detected, and every row that would be skipped - nothing is written.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `csv_text` | yes |  |
| `preset` | no | `'auto'` |

### `kamra.migrate.run_import`

**POST**

Import the file. Live rows (confirmed / in-house) go through the
full booking validation; history rows (checked-out / cancelled /
no-show) are stored as records with their status stamped directly, so
guest history survives the migration.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `csv_text` | yes |  |
| `preset` | no | `'auto'` |


## Central reservations (chain)

### `kamra.crs.crs_search`

**GET/POST** · roles: `Front Desk`, `Revenue Manager`, `Hotel Admin`, `Kamra Agent`

Find a room across the chain: for every property the user can access,
the room types with space for these dates and their all-in rate.

| Param | Required | Default |
| --- | --- | --- |
| `check_in_date` | yes |  |
| `check_out_date` | yes |  |
| `adults` | no | `2` |
| `children` | no | `0` |


## Dashboards

### `kamra.dashboards.property_dashboard`

**GET/POST** · roles: `Front Desk`, `Finance`, `Revenue Manager`, `Hotel Admin`, `Kamra Agent`

Everything one hotel's dashboard needs, by department.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `date` | no | `None` |

### `kamra.dashboards.portfolio_dashboard`

**GET/POST** · roles: `Finance`, `Revenue Manager`, `Hotel Admin`, `Kamra Agent`

The chain's central view: headline metrics rolled up across every
property the signed-in user may access, plus a per-property table.

| Param | Required | Default |
| --- | --- | --- |
| `date` | no | `None` |


## Reports

### `kamra.reports.manager_flash`

**GET/POST** · roles: `Finance`, `Front Desk`, `Kamra Agent`

The daily flash: yesterday's performance, month to date, today's
movement, collections by mode, and the 7-day outlook.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `date` | no | `None` |

### `kamra.reports.budget_vs_actual`

**GET/POST** · roles: `Finance`, `Revenue Manager`, `Kamra Agent`

Monthly target vs actual: room revenue, occupancy %, ADR, RevPAR - with
variance. period is 'YYYY-MM' (defaults to the current month).

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `period` | no | `None` |

### `kamra.reports.save_budget`

**POST** · roles: `Revenue Manager`, `Hotel Admin`, `Finance`

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `period` | yes |  |
| `room_revenue_target` | no | `0` |
| `occupancy_target` | no | `0` |
| `adr_target` | no | `0` |
| `revpar_target` | no | `0` |

### `kamra.reports.contribution`

**GET/POST** · roles: `Finance`, `Revenue Manager`, `Kamra Agent`

Who brings the business: revenue + room nights + share, grouped by
booking source, company or travel agent. by = source | company | travel_agent.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `from_date` | yes |  |
| `to_date` | yes |  |
| `by` | no | `'source'` |

### `kamra.reports.sla_report`

**GET/POST** · roles: `Front Desk`, `Hotel Admin`, `Kamra Agent`

Operations SLA health from Service Tickets over a window: overall
resolution and breach rates, a breakdown by category and by priority,
and the currently-overdue queue aged by how long it's past its due time.

Time-to-resolve is measured creation -> resolved_on; a ticket counts as
breached if it was resolved after due_by, or is still open past due_by.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `from_date` | yes |  |
| `to_date` | yes |  |


## Activity ledger

### `kamra.agents_api.activity_feed`

**GET/POST** · roles: `Front Desk`, `Finance`, `Revenue Manager`, `Kamra Agent`

The one ledger: every action anyone took - human or AI - newest first.
actor_kind filters to "human" or "agent".

| Param | Required | Default |
| --- | --- | --- |
| `property` | no | `None` |
| `actor_kind` | no | `None` |
| `action_type` | no | `None` |
| `limit` | no | `50` |
| `start` | no | `0` |

### `kamra.agents_api.activity_detail`

**GET/POST** · roles: `Front Desk`, `Finance`, `Revenue Manager`, `Kamra Agent`

Everything one ledger row knows — including the before/after
snapshots that are too heavy for the feed.

| Param | Required | Default |
| --- | --- | --- |
| `name` | yes |  |


## Public (no auth - booking page, QR menu)

> These are allow_guest endpoints: no token needed, rate-limited.

### `kamra.public_api.site_info` <Badge type='tip' text='public' />

**GET/POST**

Public site metadata for the login/boot screen.

demo_mode is true only on the seeded demo site (seed_demo sets the
`kamra_demo_mode` default), so a real install never advertises the
demo login accounts.

### `kamra.public_api.showcase` <Badge type='tip' text='public' />

**GET/POST**

Everything the public booking page needs to render.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.public_api.search_stay` <Badge type='tip' text='public' />

**GET/POST**

Availability + real quoted price per room type for the stay.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `check_in_date` | yes |  |
| `check_out_date` | yes |  |
| `adults` | no | `2` |
| `children` | no | `0` |

### `kamra.public_api.precheckin_info` <Badge type='tip' text='public' />

**GET/POST**

Stay summary for the pre-arrival check-in page.

| Param | Required | Default |
| --- | --- | --- |
| `token` | yes |  |

### `kamra.public_api.precheckin_submit` <Badge type='tip' text='public' />

**POST**

Guest completes pre-arrival check-in and signs the registration card
(PRD FR-20 - details + declaration + e-signature; the signed card becomes
the paperless GRC the desk views at arrival). ID photo/KYC vendor
integration comes later.

| Param | Required | Default |
| --- | --- | --- |
| `token` | yes |  |
| `id_type` | yes |  |
| `id_number` | yes |  |
| `email` | no | `''` |
| `nationality` | no | `''` |
| `address_line` | no | `''` |
| `city` | no | `''` |
| `eta` | no | `''` |
| `special_requests` | no | `''` |
| `signature` | no | `''` |
| `consent` | no | `0` |

### `kamra.public_api.laundry_info` <Badge type='tip' text='public' />

**GET/POST**

Laundry price list + stay context for the in-stay guest page.
Read-only — the guest sees what things cost, never a folio.

| Param | Required | Default |
| --- | --- | --- |
| `token` | yes |  |

### `kamra.public_api.request_guest_laundry` <Badge type='tip' text='public' />

**POST**

In-house guest asks housekeeping to pick their laundry up. Written on
the guest's behalf by the governed agent — the guest never touches pricing
or the folio; staff count and price the bag at the door (status
'Requested', exactly where a staff-logged pickup lands).

| Param | Required | Default |
| --- | --- | --- |
| `token` | yes |  |
| `notes` | no | `''` |
| `express` | no | `0` |

### `kamra.public_api.check_voucher` <Badge type='tip' text='public' />

**GET/POST**

Live promo-code feedback on the booking page. Never throws - returns
{ok, message, discount_type, value} so the guest sees a friendly note.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `code` | yes |  |
| `nights` | no | `1` |

### `kamra.public_api.qr_menu` <Badge type='tip' text='public' />

**GET/POST**

The guest-facing digital menu behind a table/room QR code. Only shows
outlets a hotel has published items for; no prices are trusted from the
guest - they're read here.

| Param | Required | Default |
| --- | --- | --- |
| `outlet` | yes |  |

### `kamra.public_api.qr_order` <Badge type='tip' text='public' />

**POST**

A guest places an order from the QR menu. It lands as a QR order that
a captain must confirm before it fires to the kitchen or touches a bill -
the guest can never post directly to a folio.

| Param | Required | Default |
| --- | --- | --- |
| `outlet` | yes |  |
| `items` | yes |  |
| `room` | no | `None` |
| `table_no` | no | `None` |

### `kamra.public_api.hosting_enquiry` <Badge type='tip' text='public' />

**POST**

Kamra Cloud hosting enquiry from kamrapms.com. Stored first (a lead is
never lost even without SMTP), then a best-effort email to the team.

| Param | Required | Default |
| --- | --- | --- |
| `full_name` | yes |  |
| `email` | yes |  |
| `phone` | no | `''` |
| `property_name` | no | `''` |
| `rooms` | no | `0` |
| `city` | no | `''` |
| `message` | no | `''` |
