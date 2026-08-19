---
outline: 2
---

# REST API reference

Every endpoint below is a whitelisted function — the same governed layer
the UI and the AI use. **230 endpoints**, generated from the source
(`docs-site/gen_api.py`), so this page always matches the code.

## Calling convention

```
POST https://<your-kamra>/api/method/kamra.<module>.<function>
Authorization: token <api_key>:<api_secret>
Content-Type: application/json
```

- Get keys from **Kamra Agent → Connect your AI** (Claude OAuth, role-scoped) or the
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

Record money received on the stay ledger. kind labels WHY it came
in - Payment (against the bill), Advance (collected before/at
check-in) or Security Deposit (held, refundable). Refunds go through
refund_folio_payment so they can never be entered by accident.

| Param | Required | Default |
| --- | --- | --- |
| `folio` | yes |  |
| `mode` | yes |  |
| `amount` | yes |  |
| `reference` | no | `None` |
| `pin` | no | `None` |
| `kind` | no | `'Payment'` |

### `kamra.api.refund_folio_payment`

**POST** · roles: `Finance`, `Front Desk`, `Kamra Agent`

Give money back on an open folio - a held security deposit at
checkout, or an over-collected advance. Stored as a negative ledger
row so every balance still sums exactly; a reason is mandatory.

| Param | Required | Default |
| --- | --- | --- |
| `folio` | yes |  |
| `amount` | yes |  |
| `mode` | yes |  |
| `reason` | yes |  |
| `pin` | no | `None` |

### `kamra.api.set_actual_times`

**POST** · roles: `Front Desk`, `Kamra Agent`

Correct the recorded arrival/departure moments - early check-ins
and late checkouts should show what actually happened, not just when
the button was pressed. Early/late charges stay explicit folio lines.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `actual_check_in` | no | `None` |
| `actual_check_out` | no | `None` |

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

Everything the bill needs to print itself.

A tax invoice is a legal document, not a screenshot of a table: the
service code belongs on each LINE (a room night, a restaurant cover
and a laundry bag are three different supplies), the tax has to be
named the way the country names it, the total has to appear in words,
and the guest wants a summary by what they bought before they read
forty lines. All of that is assembled here so every surface that
prints a bill - the folio screen, a PDF, an email - agrees.

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

### `kamra.api.upload_id_document`

**POST** · roles: `Front Desk`, `Kamra Agent`

Capture the guest's ID at the counter, when they never uploaded one.

Same storage as the guest path, different gate: there the token proves
ownership, here @require_roles does. This exists so that "never block
check-in" has somewhere to go - the desk flags a missing document, then
fixes it in the same breath instead of turning the guest away.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `data` | yes |  |

### `kamra.api.id_document_image`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

The ID scan as a data URL, for the desk to eyeball.

Why not just point an &lt;img> at the /private/files/ URL: Frappe would
authorise that through File.has_permission -> the Reservation's own
doctype permissions. On a site whose Custom DocPerm rows omit Front Desk
(as ours do - any custom perm on a doctype REPLACES all its standard
perms), that check says no, and the desk gets a broken image while a
Hotel Admin sees it. Kamra's authorization has always lived on the
endpoint rather than the doctype (see authz.py), so the image is served
the same way as everything else here: one gate, one rule, works for
every role the app actually grants.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |

### `kamra.api.verify_precheckin`

**POST** · roles: `Front Desk`, `Kamra Agent`

The desk has held the document against the human and agrees.

This is the write that finally makes precheckin_status="Verified" real -
the enum has existed since pre-arrival check-in shipped and no code path
ever set it. precheckin_submit already refuses to touch a Verified
booking, so the guest is locked out of rewriting a checked card the
moment this lands; that guard was clearly written for this.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |

### `kamra.api.checkin_context`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Everything the check-in flow needs in one round trip: how complete
the guest's registration is, the assigned room - or the allocator's
suggestion plus every room the desk may hand over instead.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |

### `kamra.api.check_in`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `room` | no | `None` |

### `kamra.api.upload_occupant_id`

**POST** · roles: `Front Desk`, `Kamra Agent`

ID document for one occupant on the stay register. Same security
pipeline as every ID image: decoded, re-encoded through PIL (the
sanitisation boundary), stored private, attached to the reservation
so checkout retention rules find it.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `row` | yes |  |
| `image` | yes |  |

### `kamra.api.upload_guest_document`

**POST** · roles: `Front Desk`, `Kamra Agent`

The desk captures or replaces a guest's document while preparing
the GRC - walk-ins, or a newer copy over last visit's. kind is 'id'
or 'address'; stored privately, one current copy per slot.

| Param | Required | Default |
| --- | --- | --- |
| `guest` | yes |  |
| `kind` | yes |  |
| `image` | yes |  |

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

The GM / front-desk position briefing - what Kamra Agent reads out
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
| `guest_category` | no | `None` |
| `stay_details` | no | `None` |
| `instructions` | no | `None` |

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
| `allergy_note` | no | `None` |

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

Pass a course to send only that course and hold the rest - the table
orders once, the kitchen cooks the mains when the starters are cleared.
Each line is stamped with the moment it was fired: that, not when the
captain opened the tab, is when the cook's clock starts.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |
| `course` | no | `None` |

### `kamra.pos.kitchen_queue`

**GET/POST**

The kitchen display: fired orders the kitchen still has work on. Scope
to one outlet (each restaurant's own kitchen) and/or one station.

Each line carries a `state` the screen renders directly:
  cooking   - fired, still to make
  held      - a later course, or a round added to a running tab; the
              kitchen can see it coming but must not start it
  cancelled - voided after the KOT fired; the chef may be cooking it right
              now, so it stays on the ticket (loudly) until acknowledged
  done      - already prepared; kept for context and to allow a recall

A ticket is on the board while it has cooking, held or cancelled lines.
Done lines ride along but never hold a ticket open, so "all ready" still
clears it.

`fired_at` per line is what the display ages against - a table that sat an
hour over drinks must not hand the kitchen a ticket that is already red.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `outlet` | no | `None` |
| `station` | no | `None` |

### `kamra.pos.mark_prepared`

**POST**

Kitchen marks one line (or every cooking line) prepared. Voided lines
are never swept up by "all ready" - that food is cancelled, not cooked.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |
| `item_row` | no | `None` |

### `kamra.pos.accept_ticket`

**POST**

The kitchen takes the ticket on. Until a ticket is accepted the floor
has no evidence anyone has seen it - a KOT can print to an empty pass.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |

### `kamra.pos.recall_prepared`

**POST**

Undo a mark-prepared: the line goes back to Fired and reappears on the
display. A mis-tap on a greasy touchscreen must not be one-way.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |
| `item_row` | no | `None` |

### `kamra.pos.acknowledge_void`

**POST**

The chef has seen that a fired line was cancelled and can stop cooking
it; drop it from the display. The void itself stays on the order.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |
| `item_row` | yes |  |

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

### `kamra.laundry.import_laundry_rates`

**POST**

Bulk-load or bulk-update the rate card from a CSV - the same file
the Export button produces (item, service, rate, express rate).
Upserts by (item, service): existing rows update, new rows are
created, nothing is deleted. Headers are matched tolerantly.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `csv_text` | yes |  |

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


## Banquets (functions, quotations, event orders)

### `kamra.banquet.banquet_catalogue`

**GET/POST**

What the property sells: the menu packages (with their courses) and
the service list. This is the picker behind every line item.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.banquet.save_banquet_menu`

**POST**

Add or edit one menu package. Courses replace wholesale - the grid
the user is looking at is the truth.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `menu_name` | yes |  |
| `rate_per_pax` | yes |  |
| `courses` | no | `None` |
| `name` | no | `None` |

### `kamra.banquet.delete_banquet_menu`

**POST**

| Param | Required | Default |
| --- | --- | --- |
| `name` | yes |  |

### `kamra.banquet.save_service_item`

**POST**

Add or edit one service - a projector, an LED wall, a DJ, a podium,
a stage, a decor package, bar service. `chargeable = 0` marks the ones
the hotel throws in as standard; they still appear on the event order
and the pack list.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `item_name` | yes |  |
| `category` | yes |  |
| `rate` | no | `0` |
| `uom` | no | `'Per Event'` |
| `name` | no | `None` |

### `kamra.banquet.delete_service_item`

**POST**

| Param | Required | Default |
| --- | --- | --- |
| `name` | yes |  |

### `kamra.banquet.create_enquiry`

**POST**

Open a function sheet from an enquiry. The hall's rack rental goes on
as the first line (that's the number the conversation starts from), and
a follow-up lands in the diary so the enquiry doesn't go quiet.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `venue` | yes |  |
| `event_date` | yes |  |
| `customer_name` | yes |  |
| `event_type` | no | `'Wedding'` |
| `attendees` | no | `0` |
| `customer_phone` | no | `None` |
| `customer_email` | no | `None` |
| `company` | no | `None` |
| `end_date` | no | `None` |
| `start_time` | no | `None` |
| `end_time` | no | `None` |
| `source` | no | `'Phone'` |
| `requirements` | no | `None` |
| `follow_up_days` | no | `2` |
| `with_venue_line` | no | `1` |
| `sales_owner` | no | `None` |

### `kamra.banquet.function_sheet`

**GET/POST**

One function, everything about it - the sheet the banquet screen
renders and Kamra Agent reads.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |

### `kamra.banquet.update_function`

**POST**

Edit the sheet's own fields (not its tables - those have their own
calls, because each one means something different).

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `fields` | yes |  |

### `kamra.banquet.set_status`

**POST**

Move the function along its pipeline. Confirming takes the hall -
the controller refuses a clash with another confirmed function.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `status` | yes |  |
| `reason` | no | `None` |
| `tentative_until` | no | `None` |

### `kamra.banquet.add_menu`

**POST**

Put a menu package on the function. Left alone the quantity follows
the pax rule (guaranteed, or actual if more turned up) and the price is
the package's own plate price - pass `rate` when it's been negotiated.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `menu` | yes |  |
| `qty` | no | `None` |
| `rate` | no | `None` |
| `chargeable` | no | `1` |
| `notes` | no | `None` |

### `kamra.banquet.add_service`

**POST**

Put a service on the function - projector, LED wall, DJ, podium,
stage, decor, laptop, bar. The catalogue decides whether it's chargeable
by default; pass `chargeable` to override for this function.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `service_item` | yes |  |
| `qty` | no | `None` |
| `rate` | no | `None` |
| `chargeable` | no | `None` |
| `notes` | no | `None` |

### `kamra.banquet.save_items`

**POST**

Replace the line grid wholesale - what the user is looking at is the
truth. Rows keep their catalogue links so the event order can still
print a menu's courses.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `items` | yes |  |

### `kamra.banquet.remove_item`

**POST**

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `row` | yes |  |

### `kamra.banquet.negotiate`

**POST**

The price moves. `rows` is {line_row_name: new_rate} - or pass
`venue_rental` to move just the hall - and `discount_amount` is the
headline reduction on the whole quote.

Every move is snapshotted with what the quote was worth before and
after, so the fourth revision of a wedding quote can be explained.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `rows` | no | `None` |
| `discount_amount` | no | `None` |
| `note` | no | `None` |
| `venue_rental` | no | `None` |

### `kamra.banquet.save_open_items`

**POST**

What is still unsettled while the price is being agreed - the
sangeet stage, whether the bar is on consumption, who pays for the
extra generator. Each carries what agreeing it would do to the price.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `rows` | yes |  |

### `kamra.banquet.set_payment_terms`

**POST** · roles: `Finance`

The schedule the customer signs up to. A term stated as a percentage
follows the quote as it moves; one stated as an amount is a number both
sides agreed and stays put.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `terms` | yes |  |
| `note` | no | `None` |

### `kamra.banquet.default_payment_terms`

**POST** · roles: `Finance`

The usual three-milestone schedule, dated off this function: an
advance to hold the hall, a second call before the date, the rest on
completion. Editable afterwards like any other term.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `advance_percent` | no | `25` |
| `interim_percent` | no | `50` |
| `interim_days_before` | no | `15` |

### `kamra.banquet.record_receipt`

**POST** · roles: `Finance`

Money in against the function. Pass `settle_term` to tick off the
payment-term row it pays, so the schedule and the ledger agree.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `amount` | yes |  |
| `mode` | no | `'Bank Transfer'` |
| `kind` | no | `'Advance'` |
| `reference` | no | `None` |
| `receipt_date` | no | `None` |
| `settle_term` | no | `None` |

### `kamra.banquet.assign_green_room`

**POST**

Hold a changing room for the wedding party. The controller puts a
Room Block on it so it genuinely leaves the sellable inventory; pass
`complimentary=0` (with a rate) to bill it as an Accommodation line.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `room` | no | `None` |
| `from_date` | no | `None` |
| `to_date` | no | `None` |
| `complimentary` | no | `1` |
| `rate` | no | `0` |

### `kamra.banquet.venue_availability`

**GET/POST**

Which halls are free for these dates and hours. A confirmed function
takes the hall; a tentative one is shown as a soft hold you can still
sell over. Halls too small for the pax are flagged, not hidden.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `event_date` | yes |  |
| `end_date` | no | `None` |
| `start_time` | no | `None` |
| `end_time` | no | `None` |
| `pax` | no | `0` |
| `exclude` | no | `None` |

### `kamra.banquet.banquet_calendar`

**GET/POST**

The function diary - halls down the side, days across the top, every
function in its cell with what it's worth and what's still owed.
Multi-day functions appear on each of their days.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `start_date` | no | `None` |
| `days` | no | `31` |
| `status` | no | `None` |

### `kamra.banquet.banquet_pipeline`

**GET/POST** · roles: `Hotel Admin`

The sales view: where the business is by month and by status, what
converted, what died and why. Dated on the event, not the enquiry -
a banquet team's month is the month the function happens.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `from_date` | no | `None` |
| `to_date` | no | `None` |
| `months` | no | `6` |

### `kamra.banquet.banquet_reminders`

**GET/POST**

Everything across the property that needs chasing - the banquet
team's morning list.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `days` | no | `30` |

### `kamra.banquet.banquet_document`

**GET/POST**

The paper. One shape for every document so the front end can print
them all the same way:

  quote      what it costs, line by line, with the terms
  contract   the quote plus the terms, the policy and signature blocks
  beo        the banquet event order - the running sheet for the day
  pack_list  what physically has to reach the hall, and by when
  invoice    the bill, against what's already been received

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `kind` | no | `'quote'` |

### `kamra.banquet.generate_quote`

**POST**

Stamp a quotation. Bumps the version, dates it, and snapshots what
it was worth - so 'the price we sent on the 3rd' is answerable.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `valid_days` | no | `15` |
| `note` | no | `None` |

### `kamra.banquet.generate_beo`

**POST**

Issue the banquet event order - the sheet the banquet, kitchen and
AV teams run the day from. Only a confirmed function gets one; the
teams shouldn't be preparing for business that isn't sold.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |

### `kamra.banquet.post_to_folio`

**POST** · roles: `Finance`

Push the chargeable lines onto a bill. A function tied to a group
rides the group's master folio; otherwise pass one explicitly.

Alcohol is reported back rather than posted when the bill is a company
or group folio - the same rule the folio itself enforces - so it can be
settled separately instead of failing the whole post.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `folio` | no | `None` |

### `kamra.banquet.close_out`

**POST** · roles: `Finance`

Hand the hall back. The last ritual of a function, and the one that
usually happens on a WhatsApp message and a scrap of paper: walk the
room, count the actual covers, note what got broken, take that off the
deposit and give the rest back.

Doing it here means the deduction has a reason attached, the refund is
a real ledger line, and the function closes in one motion instead of
three people remembering to do three things.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `damage_amount` | no | `0` |
| `damage_note` | no | `None` |
| `refund_deposit` | no | `1` |
| `refund_mode` | no | `'Bank Transfer'` |
| `pax_actual` | no | `None` |

### `kamra.banquet.receipt_document`

**POST** · roles: `Finance`

One receipt, as a document the customer can keep. Every advance a
banquet office takes needs a piece of paper against it - this is that
piece of paper.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `receipt` | yes |  |

### `kamra.banquet.menu_card`

**GET/POST**

The menu the customer signs off - what will actually be served,
course by course, with nothing about money on it. The kitchen and the
customer read the same sheet, which is the whole point.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |

### `kamra.banquet.month_availability`

**GET/POST**

Every hall × every session, across a whole month.

The question a banquet office is actually asked - "do you have the
14th of December?" - is about a hall and a session, not a range of
hours. This is the grid that answers it in one look: halls down the
side split by session, days across the top, and what's in each cell.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `month` | no | `None` |

### `kamra.banquet.banquet_register`

**GET/POST** · roles: `Hotel Admin`

The listings a banquet office runs the week on - the same five books
every hall has kept on paper forever, dated and totalled:

  functions   every booking in the window, with pax, rate and value
  quotations  what was quoted, and whether it converted
  enquiries   what came in, and what happened to it
  receipts    the cash book: every payment, by mode
  sales       revenue by hall, event type and month

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `register` | no | `'functions'` |
| `from_date` | no | `None` |
| `to_date` | no | `None` |

### `kamra.banquet.dish_library`

**GET/POST**

Every dish the banquet kitchen can produce, with what it costs to
make. This is the picker behind menu building and the spine of margin.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `course_type` | no | `None` |

### `kamra.banquet.save_dish`

**POST**

Add or edit a dish. The recipe is what makes it cost something -
without one the dish is free, and so is the margin it reports.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `dish_name` | yes |  |
| `recipe` | no | `None` |
| `name` | no | `None` |

### `kamra.banquet.delete_dish`

**POST**

| Param | Required | Default |
| --- | --- | --- |
| `name` | yes |  |

### `kamra.banquet.recost_dishes`

**POST**

Ingredient prices moved - re-cost every dish. Run it after a delivery
or a price revision, so quotes stop being priced off last season's
onions.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.banquet.menu_cost`

**GET/POST**

What one plate of this menu costs to make, and what it earns.

Costs the DEFAULT selection - one dish per choice where the course
offers a choice, everything where it doesn't - so a menu can be judged
before anyone has booked it.

| Param | Required | Default |
| --- | --- | --- |
| `menu` | yes |  |
| `pax` | no | `0` |

### `kamra.banquet.menu_choices`

**GET/POST**

The course-by-course picker for one menu on one function: what the
course offers, how many the guest may take, and what's chosen so far.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `menu` | yes |  |

### `kamra.banquet.compose_menu`

**POST**

Record what the customer actually chose - "one soup of these two, the
paneer not the mushroom".

The dish NAME is stored alongside the link on purpose: renaming a dish
next season must not rewrite a menu card the customer already signed.
Any supplement the choice carries goes on as its own line, because an
upgrade is a price change and should be visible as one.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `menu` | yes |  |
| `picks` | yes |  |

### `kamra.banquet.kitchen_indent`

**GET/POST** · roles: `Housekeeping`

What the kitchen has to buy and pull for this function.

The artifact that has always sat between the event order and the store
room, written by hand: chosen dishes x portions x guaranteed pax,
exploded through the recipes into ingredient quantities, checked against
what's actually on the shelf.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |

### `kamra.banquet.issue_indent`

**POST** · roles: `Housekeeping`

Pull the indent off the shelf. Writes real stock movements through
the same single writer the restaurant uses, so the store room reflects
a banquet the way it reflects a table.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `outlet` | yes |  |
| `rows` | no | `None` |

### `kamra.banquet.record_consumption`

**POST**

What was actually served, against what was quoted.

The quote said 300 plates; 318 people ate and the bar went through
another two cases. Until this is recorded the bill is a forecast -
rows = {line_row_name: actual_qty}.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `rows` | no | `None` |
| `pax_actual` | no | `None` |

### `kamra.banquet.add_supplementary`

**POST**

Something ordered on the night that wasn't on the quote - another
round at the bar, twenty extra plates, a second cake. It bills on top
and is marked so the final bill can show it apart from what was
agreed.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `item_name` | yes |  |
| `qty` | yes |  |
| `rate` | yes |  |
| `item_type` | no | `'Food & Beverage'` |
| `uom` | no | `'Unit'` |
| `cost_rate` | no | `0` |
| `is_alcohol` | no | `0` |
| `notes` | no | `None` |

### `kamra.banquet.function_economics`

**GET/POST**

The P&L of one function: what it sold, what it cost, what the input
credit is worth, and what's left - plus where the quote and the night
disagreed.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |

### `kamra.banquet.link_customer`

**POST**

Tie the function to a real guest record instead of a name in a box.

Without this a banquet customer is a string: no history, no notes, no
'they complained about the AC last time'. With it, the banquet office
sees the same person the front desk does.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `guest` | no | `None` |

### `kamra.banquet.customer_profile`

**GET/POST**

Everything the banquet office should know before picking up the
phone: what this client has run with us, what they spent, what they
usually book, and what's still owed.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `guest` | no | `None` |
| `phone` | no | `None` |


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


## Inventory & recipes

### `kamra.inventory.ingredients`

**GET/POST**

The ingredient master - the picker behind the recipe editor.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `active_only` | no | `1` |

### `kamra.inventory.menu_recipe`

**GET/POST**

One dish's recipe, with each line's unit and what the dish's own outlet
has on hand right now - so the editor can say "you have 0.4 kg left".

| Param | Required | Default |
| --- | --- | --- |
| `menu_item` | yes |  |

### `kamra.inventory.recipe_overview`

**GET/POST**

Every dish and whether it has a recipe yet. Dishes without one are not
a problem to be nagged about - most menus will only ever cost their big
movers - but you cannot decide that without seeing the list.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.inventory.save_recipe`

**POST** · roles: `Finance`, `Hotel Admin`

Replace a dish's recipe wholesale. An empty list is valid and means
"this dish never touches inventory" - the optional in the requirement.

| Param | Required | Default |
| --- | --- | --- |
| `menu_item` | yes |  |
| `rows` | yes |  |

### `kamra.inventory.save_ingredient`

**POST**

Create or update one ingredient.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `ingredient_name` | yes |  |
| `uom` | yes |  |
| `category` | no | `None` |
| `cost_per_unit` | no | `0` |
| `is_active` | no | `1` |
| `name` | no | `None` |

### `kamra.inventory.delete_ingredient`

**POST**

Refuse if it is on a recipe or has history - deleting it would orphan a
recipe or punch a hole in the ledger. Deactivate instead.

| Param | Required | Default |
| --- | --- | --- |
| `name` | yes |  |

### `kamra.inventory.receive_stock`

**POST**

Goods in. rows = [{ingredient, qty, cost_per_unit?}]. One batch_id ties
the delivery together, which is why this needs no Stock Receipt doctype:
a receipt is just its ledger rows plus a supplier and an invoice number.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `outlet` | yes |  |
| `rows` | yes |  |
| `supplier` | no | `None` |
| `invoice_no` | no | `None` |

### `kamra.inventory.adjust_stock`

**POST**

The stock take, and the escape hatch for everything this module cannot
know. rows = [{ingredient, counted_qty}] - COUNTS, not deltas, exactly
like laundry's return_items: a human reports what is physically on the
shelf and the system works out its own error.

The note is required on purpose. A write-off with no reason is precisely
the silence this module exists to remove - the same call laundry's
shortage guard makes when it refuses to deliver a short bag unexplained.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `outlet` | yes |  |
| `rows` | yes |  |
| `note` | yes |  |

### `kamra.inventory.record_wastage`

**POST**

Stock destroyed OUTSIDE a sale: a crate of tomatoes rots, a bottle
breaks. No POS line exists, so only a real ledger row can say it happened.

Note what this is NOT for: food that was cooked and then voided. That
already left the shelf at fire and already has its Consumed row - writing
a Wastage row too would deduct it twice. Use wastage_report() for those.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `outlet` | yes |  |
| `ingredient` | yes |  |
| `qty` | yes |  |
| `reason_note` | yes |  |

### `kamra.inventory.stock_list`

**GET/POST**

Everything this outlet holds. Stock is per outlet, so there is no such
thing as a merged total across outlets and this never offers one.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `outlet` | yes |  |
| `status` | no | `None` |

### `kamra.inventory.ingredient_ledger`

**GET/POST**

Where did my paneer go? Newest first, each row carrying the balance it
produced, so the history explains the number on the shelf.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `outlet` | yes |  |
| `ingredient` | yes |  |
| `limit` | no | `50` |

### `kamra.inventory.low_stock`

**GET/POST**

Everything at or under par, out, or negative - and, for each, the
dishes that use it. That last part is what makes the flag actionable:
"Paneer is out" means nothing until you know it takes Paneer Tikka with
it. We flag and offer; a human decides. Nothing is ever auto-86'd.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `outlet` | no | `None` |

### `kamra.inventory.wastage_report`

**GET/POST**

Food that was cooked and then binned: lines voided after they fired.

Derived, deliberately. The stock already left at the fire and the Consumed
row is the truth - a second Wastage row would deduct it twice, and a
compensating pair would churn the ledger without changing a balance. This
only asks which of those consumptions turned out to be waste, and what
they cost. reason="Wastage" in the ledger stays reserved for stock
destroyed outside a sale, so SUM(qty_change) always equals reality.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `outlet` | no | `None` |
| `days` | no | `30` |

### `kamra.inventory.set_menu_availability`

**POST** · roles: `Finance`, `Hotel Admin`

86 a dish, or put it back. This is the ONLY thing that ever pulls an
item off the menu for stock reasons, and a human has to press it.

Nothing auto-86s on a zero balance, deliberately: the count is the least
trustworthy number in the building (see this module's docstring), and a
stale one would silently hide a dish the kitchen can actually cook. The
screen flags what is out and offers the button; the decision stays with
someone who can walk over and look at the shelf.

| Param | Required | Default |
| --- | --- | --- |
| `menu_item` | yes |  |
| `available` | yes |  |

### `kamra.inventory.set_par_level`

**POST**

Where LOW starts for this ingredient at this outlet. Zero = no par.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `outlet` | yes |  |
| `ingredient` | yes |  |
| `par_level` | yes |  |


## Menu bulk import

### `kamra.menu_import.preview_menu_import`

**POST**

Dry run: how the columns map, what would be created vs updated, and
every row that would be skipped. Nothing is written.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `csv_text` | yes |  |
| `outlet` | no | `None` |

### `kamra.menu_import.run_menu_import`

**POST**

Import the file. Upserts by (property, outlet, item_name): a dish
already on that outlet's menu is updated (price/flags), never duplicated.
One bad row never aborts the batch.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `csv_text` | yes |  |
| `outlet` | no | `None` |
| `update_existing` | no | `1` |

### `kamra.menu_import.menu_template`

**GET/POST**

The CSV headers + one sample row, so the file starts out right.


## Guest ID documents


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

### `kamra.reports.void_allowance_report`

**GET/POST** · roles: `Finance`, `Hotel Admin`

Audit trail of every void, allowance and invoice cancellation on a
property: who reversed what, when, and why. The compliance answer to
"show me every write-off" - read straight from the action log, so it
cannot drift from what actually happened.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `from_date` | no | `None` |
| `to_date` | no | `None` |

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
the paperless GRC the desk views at arrival). The guest can attach a
photo of their ID - camera capture or upload - stored privately.

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
| `id_image` | no | `''` |
| `address_image` | no | `''` |

### `kamra.public_api.precheckin_upload_id` <Badge type='tip' text='public' />

**POST**

The guest photographs their ID during pre-arrival check-in.

Deliberately NOT Frappe's upload_file. That endpoint would need the
site-wide `allow_guests_to_upload_files` setting, which opens
unauthenticated upload to the whole site; on its guest branch it sets
ignore_permissions and never sees a token, so it cannot tell whether this
guest owns this booking; and it takes is_private from the client - i.e.
it trusts the browser to protect an Aadhaar scan. Here the token is the
gate, the rate limit is real, and privacy is not negotiable.

Optional by design: nothing downstream requires a document. A guest with
a cracked camera or a bad lobby connection must still be able to
pre-register, so the submit gate never mentions this.

| Param | Required | Default |
| --- | --- | --- |
| `token` | yes |  |
| `data` | yes |  |

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

### `kamra.public_api.book` <Badge type='tip' text='public' />

**POST**

Create a Website booking. Guest identity is the phone number; staff
verify at check-in. The advance owed is computed from the property's
current payment policy and snapshotted onto the booking.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `room_type` | yes |  |
| `check_in_date` | yes |  |
| `check_out_date` | yes |  |
| `guest_name` | yes |  |
| `phone` | yes |  |
| `email` | no | `''` |
| `adults` | no | `2` |
| `children` | no | `0` |
| `meal_plan` | no | `''` |
| `special_requests` | no | `''` |
| `addons` | no | `None` |
| `voucher_code` | no | `''` |

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
| `country` | no | `''` |
| `interest` | no | `''` |
