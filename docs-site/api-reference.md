---
outline: 2
---

# REST API reference

Every endpoint below is a whitelisted function - the same governed layer
the UI and the AI use. **418 endpoints**, generated from the source
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

### `kamra.api.enabled_modules`

**GET/POST** · roles: `Front Desk`, `Finance`, `Revenue Manager`, `Housekeeping`, `Housekeeping Supervisor`, `Kamra Agent`, `Night Auditor`

Which parts of Kamra this property runs. Empty setting = all of
them, so an existing property keeps working untouched.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.api.set_enabled_modules`

**POST** · roles: `Hotel Admin`

Turn parts of the product on or off for one property.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `modules` | yes |  |

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

### `kamra.api.upload_room_image`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`, `Hotel Admin`, `System Manager`

Uploads an image file for room types / properties to public files.

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
| `days_of_week` | no | `None` |

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

**GET/POST** · roles: `Finance`, `Front Desk`, `Night Auditor`, `Kamra Agent`

Cashier reconciliation: what the system says was collected today,
per payment mode - the number the drawer must match at shift close.

Prefers Cashier Transaction totals (FO + POS); falls back to folio
payments for properties that have not opened a till yet.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `date` | no | `None` |
| `to_date` | no | `None` |

### `kamra.api.record_advance`

**POST** · roles: `Front Desk`, `Finance`, `Kamra Agent`

Take a deposit / advance on a booking before arrival (#114). Opens
the guest folio early so the money sits on the stay from day one and
the balance at check-in is right; recorded through add_folio_payment,
so the till, cashier PIN and ledger see it like any other payment.
A Held / Pending Payment booking is confirmed by it.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `amount` | yes |  |
| `mode` | no | `'Cash'` |
| `reference` | no | `None` |
| `pin` | no | `None` |

### `kamra.api.deposit_payment_link`

**POST** · roles: `Front Desk`, `Finance`, `Kamra Agent`

A payment link for the booking deposit - the deposit still due by
default, or any amount the desk agrees with the guest. Paid through the
gateway, it posts to the folio as an Advance (settle_payment_link).

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `amount` | no | `None` |

### `kamra.api.simulate_payment_link`

**POST** · roles: `Front Desk`, `Finance`, `Hotel Admin`

Test mode only: act as the gateway and mark the outstanding link
paid - for demos and training, never on a live gateway.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |

### `kamra.api.security_deposit`

**GET/POST** · roles: `Front Desk`, `Finance`, `Hotel Admin`, `Kamra Agent`

The stay's refundable security (damage) deposit: policy amount, what
is held, withheld and refunded, its history and which actions are open.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |

### `kamra.api.collect_security_deposit`

**POST** · roles: `Front Desk`, `Finance`, `Kamra Agent`

Take a refundable security deposit (villas: the damage deposit). Lands
on the guest folio as a Security Deposit payment and in the Deposit
ledger - a liability held for the guest, never revenue. Cashier PIN and
open till as for any payment.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `amount` | yes |  |
| `mode` | no | `'Cash'` |
| `reference` | no | `None` |
| `pin` | no | `None` |

### `kamra.api.waive_security_deposit`

**POST** · roles: `Front Desk`, `Hotel Admin`, `Kamra Agent`

Waive the property's security deposit for this stay (reason required).
Refused once money has been taken - refund it instead.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `reason` | yes |  |

### `kamra.api.withhold_security_deposit`

**POST** · roles: `Front Desk`, `Finance`, `Hotel Admin`

Keep all or part of the held deposit against damage (reason required).
The withheld part posts as a damage charge on the guest folio and moves
from the Deposit ledger to the Guest ledger to pay it.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `amount` | yes |  |
| `reason` | yes |  |
| `evidence` | no | `None` |
| `pin` | no | `None` |

### `kamra.api.refund_security_deposit`

**POST** · roles: `Front Desk`, `Finance`, `Hotel Admin`

Refund what is still held (all of it by default) through the folio
refund path - till, folio and a Deposit-ledger debit. Cashier PIN.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `amount` | no | `None` |
| `mode` | no | `None` |
| `note` | no | `None` |
| `pin` | no | `None` |

### `kamra.api.release_access_instructions`

**GET/POST** · roles: `Front Desk`, `Hotel Admin`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `force` | no | `0` |

### `kamra.api.confirm_pending_reservation`

**GET/POST** · roles: `Front Desk`, `Hotel Admin`, `Kamra Agent`

Mark Held / Pending Payment / Requested as Confirmed (host or payment).

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |

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

An Inspection is completed by passing it: Done on an inspection is taken
as Verified, which moves the room to Ready (inspection required by the
turnover profile) or Inspected - never back to plain Clean. Verifying -
an inspection or anyone's clean - is a supervisor's call, the same rule
set_housekeeping_status applies to Inspected / Ready.

| Param | Required | Default |
| --- | --- | --- |
| `task` | yes |  |
| `status` | yes |  |

### `kamra.api.hk_upload_media`

**POST** · roles: `Housekeeping`, `Front Desk`, `Kamra Agent`

Attach a completion photo/video (proof of clean) to a housekeeping task.

Uploaded from the housekeeper's phone while the room is being serviced. Stored
public and attached to the task, so it stays with the record after the task
closes and drops out of the live queue.

| Param | Required | Default |
| --- | --- | --- |
| `task` | yes |  |

### `kamra.api.hk_delete_media`

**POST** · roles: `Housekeeping`, `Front Desk`, `Kamra Agent`

Remove a completion photo/video from a housekeeping task.

| Param | Required | Default |
| --- | --- | --- |
| `task` | yes |  |
| `file_url` | yes |  |

### `kamra.api.hk_task_media`

**GET/POST** · roles: `Housekeeping`, `Front Desk`, `Hotel Admin`, `Kamra Agent`

Completion photos/videos attached to one housekeeping task (newest first).

| Param | Required | Default |
| --- | --- | --- |
| `task` | yes |  |

### `kamra.api.hk_room_media`

**GET/POST** · roles: `Housekeeping`, `Front Desk`, `Hotel Admin`, `Kamra Agent`

Photos/videos from the room's LATEST cleaning only - so the front desk
sees just the most recent clean, not older cycles. Lets reception confirm a
room is genuinely guest-ready.

| Param | Required | Default |
| --- | --- | --- |
| `room` | yes |  |

### `kamra.api.hk_staff`

**GET/POST** · roles: `Housekeeping Supervisor`, `Front Desk`, `Kamra Agent`

Who a supervisor can hand a housekeeping task to at this property.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.api.hk_assign_task`

**POST** · roles: `Front Desk`, `Housekeeping`, `Kamra Agent`

A supervisor hands a task to a specific housekeeper (awaits accept).
Attendants take work from the pool with hk_claim_task; handing a task to
someone else is the supervisor's (or desk's) call, and only to a
housekeeper who can work this property.

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

**GET/POST** · roles: `Finance`, `Front Desk`, `Night Auditor`, `Kamra Agent`

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
| `reason_code` | no | `None` |
| `supervisor_pin` | no | `None` |

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
accountable through the action log. Posts a ledger reversal.

| Param | Required | Default |
| --- | --- | --- |
| `folio` | yes |  |
| `charge_row` | yes |  |
| `reason` | no | `''` |
| `pin` | no | `None` |
| `reason_code` | no | `None` |
| `supervisor_pin` | no | `None` |

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

### `kamra.api.company_billing_default`

**GET/POST** · roles: `Finance`, `Front Desk`, `Kamra Agent`

What this company pays when it has no billing rules: the property's
`default_company_billing` for a credit company, nothing otherwise.
`charge_types` is None when every charge type (except liquor) is covered.

| Param | Required | Default |
| --- | --- | --- |
| `company` | yes |  |
| `property` | no | `None` |

### `kamra.api.update_occupants`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Replace the stay's occupant register.
occupants = [{full_name, age, gender, nationality, id_type, id_number, phone}]
A child keeps name and age only: no phone, and ID details only where the
country's register needs them (see localization.minor_id_kept).

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

**GET/POST** · roles: `Front Desk`, `Finance`, `Night Auditor`, `Kamra Agent`

Close the current business date. Refused while a blocking pre-check
(kamra.night_audit.night_audit_precheck) has items, unless each is
listed in `acknowledge` (check keys) with a `note` giving the reason.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `business_date` | no | `None` |
| `acknowledge` | no | `None` |
| `note` | no | `None` |

### `kamra.api.gstr1_rows`

**GET/POST**

Invoice-level rows for a GSTR-1 style export (v0: B2C summary).
Filter by property - each GSTIN files its own return. The return is the
India pack's: a property elsewhere is refused, and without a property
only the user's India properties are included.

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

### `kamra.api.guest_alert`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Is the guest a booking would attach to blacklisted? The desk asks
before booking so the warning shows up front, not as a refusal at the
end. Resolves exactly like create_booking: the chosen profile, else the
profile with this phone number.

| Param | Required | Default |
| --- | --- | --- |
| `guest` | no | `None` |
| `phone` | no | `None` |

### `kamra.api.set_guest_blacklist`

**POST**

Blacklist a guest, or lift it. Hotel Admin only; a reason is required
either way and lands in the activity log with the before/after.

| Param | Required | Default |
| --- | --- | --- |
| `guest` | yes |  |
| `blacklisted` | yes |  |
| `reason` | yes |  |

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

Right to erasure (DPDP s.12): see kamra.privacy.erase_guest. Stays
and bills stay for the books. Irreversible.

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

**GET/POST** · roles: `Front Desk`, `Night Auditor`, `Kamra Agent`, `Finance`, `Revenue Manager`

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

### `kamra.api.stay_instructions`

**GET/POST** · roles: `Front Desk`, `Housekeeping`, `Kamra Agent`

The special instructions on a stay (a VIP amenity, a 6am wake-up, a
no-feather pillow) - each for one department, Open until someone marks
it Done.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |

### `kamra.api.add_stay_instruction`

**POST** · roles: `Front Desk`, `Kamra Agent`

Add an instruction to a stay for one department. Written as its own
child row so it never re-saves (and re-validates) the whole booking.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `department` | yes |  |
| `instruction` | yes |  |

### `kamra.api.set_stay_instruction_status`

**POST** · roles: `Front Desk`, `Housekeeping`, `Kamra Agent`

Mark one instruction Done (stamping who and when), or reopen it.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `row` | yes |  |
| `status` | yes |  |

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

**GET/POST** · roles: `Front Desk`, `Night Auditor`, `Kamra Agent`

Everything the check-in flow needs in one round trip: how complete
the guest's registration is, the assigned room - or the allocator's
suggestion plus every room the desk may hand over instead.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |

### `kamra.api.check_in`

**GET/POST** · roles: `Front Desk`, `Night Auditor`, `Kamra Agent`

Check the guest in: the last step of the guided check-in.

Hard gate: a room must be assigned (or passed here). Soft-required
steps (ID, deposit, registration card, …) may still be open  -  the desk
is warned and finishes them later. kamra.checkin.check_in_readiness
lists hard blockers and pending backfill. Records who checked the guest
in and when; a connected door-lock system then makes the keys recorded
in the Keys step.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `room` | no | `None` |

### `kamra.api.walk_in`

**POST** · roles: `Front Desk`, `Kamra Agent`

Walk-in in one step: book, register the ID, check into the chosen
room and take the money - the counter flow that used to be four screens.

defer_check_in=1 books, assigns the room and takes the money (as an
advance) but leaves the stay Confirmed, so the desk finishes it in the
guided check-in. Without it, check_in runs now (room is enough; other
soft-required steps stay as backfill). The walk-in records the steps it
does itself (room, who pays, the ID when given).

It is the same writers chained (create_booking → check_in →
add_folio_payment), inside one request, so it is all-or-nothing: a
refused PIN or a room that just sold rolls the booking back too.
Arrival is always today (calendar, like every new booking - a lagging
night audit must not turn walk-ins away); a future stay is a normal
booking, not a walk-in.

An OTA guest who books and arrives the same day is a walk-in booked
via that site: booked_via / ota_ref / ota_total / ota_commission_pct
work as in create_booking (the stay's source is then OTA).

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `room_type` | yes |  |
| `room` | yes |  |
| `check_out_date` | yes |  |
| `guest_name` | yes |  |
| `phone` | no | `None` |
| `guest` | no | `None` |
| `adults` | no | `2` |
| `children` | no | `0` |
| `meal_plan` | no | `None` |
| `voucher_code` | no | `None` |
| `company` | no | `None` |
| `id_type` | no | `None` |
| `rate_plan` | no | `None` |
| `id_number` | no | `None` |
| `nationality` | no | `None` |
| `payment_mode` | no | `None` |
| `payment_amount` | no | `0` |
| `payment_reference` | no | `None` |
| `pin` | no | `None` |
| `idempotency_key` | no | `None` |
| `check_in_time` | no | `None` |
| `check_out_time` | no | `None` |
| `blacklist_override_reason` | no | `None` |
| `credit_override_reason` | no | `None` |
| `defer_check_in` | no | `0` |
| `booked_via` | no | `None` |
| `ota_ref` | no | `None` |
| `ota_total` | no | `0` |
| `ota_commission_pct` | no | `None` |

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
| `issue_credit_note` | no | `0` |

### `kamra.api.cancellation_letter`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Everything the printable cancellation confirmation needs.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |

### `kamra.api.checkout_context`

**GET/POST** · roles: `Front Desk`, `Finance`, `Night Auditor`, `Kamra Agent`

Everything the guided check-out needs in one round trip, without
changing anything: each folio with its lines and invoice, as it will
stand once check-out posts the remaining nights (worked out inside a
savepoint that is always rolled back), bills not on the folio yet (open
restaurant orders, laundry), a late check-out, what the guest owes
(`collect`) or is owed (`refunds`: a held security deposit first, through
its own refund path), what moves to the city ledger and its credit
check, whether a cashier PIN and an open till are needed, every refusal
check-out would give (`blockers`, each tied to its step) and the
property's check-out SOP. check_out judges the balances with the same
helper (kamra.checkout.settlement_position), so the two never disagree.
Safe to call again and again: opening the sheet writes nothing.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |

### `kamra.api.check_out`

**GET/POST** · roles: `Front Desk`, `Night Auditor`, `Kamra Agent`

Check a guest out. What the company pays moves to the city ledger,
after the property's credit control: a warning comes back in
`credit_warnings`; a block refuses (CREDIT_BLOCKED) unless Finance or a
Hotel Admin passes `credit_override_reason` (logged). Agents can't
override.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `credit_override_reason` | no | `None` |

### `kamra.api.set_housekeeping_status`

**POST** · roles: `Housekeeping`, `Front Desk`, `Kamra Agent`

Change a room's housekeeping status - role, property and DocPerm
checked (#99): an attendant can mark Clean / Dirty, only a supervisor
can pass a room or take it out of order, nobody can touch a room of a
property they aren't assigned to, and removing Write on Room in the
role permissions actually removes the ability.

| Param | Required | Default |
| --- | --- | --- |
| `room` | yes |  |
| `status` | yes |  |

### `kamra.api.room_board`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Every room at a glance for the housekeeping supervisor: status,
occupancy, who is in it, and its open task - the board the desk has,
inside the Housekeeping module (#99).

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

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

**GET/POST**

The demand tiers: at each occupancy threshold, the premium applied
and the minimum sell rate enforced. A row with a room type applies to
that type only and beats the property-wide row at the same threshold.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.api.save_hurdle_rate`

**POST**

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `occupancy_from` | yes |  |
| `premium_pct` | no | `0` |
| `min_rate` | no | `0` |
| `room_type` | no | `None` |
| `name` | no | `None` |

### `kamra.api.delete_hurdle_rate`

**POST**

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

Room move / upgrade - mid-stay or before arrival. Overlap guard re-runs.
One writer for the tape chart, the reservation drawer and the GRC (#113).

The new room may be a DIFFERENT room type (e.g. Standard -> Suite): the
reservation's room type follows the room it moves into, so upgrades and
downgrades are allowed. If the booking auto-prices, the new type's rate
is quoted and locked - shown first by room_move_preview, and refused
unless confirm_price=1 when it changes the bill. A same-type move keeps
the locked nightly rates; a manually-priced booking keeps its amount.

rate_mode: "destination" (the new type's rate, above), "source" (keep
what the guest pays now) or "custom" (agreed_rate per night; Revenue
Manager / admins only).

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `new_room` | yes |  |
| `reason` | no | `None` |
| `confirm_price` | no | `0` |
| `rate_mode` | no | `'destination'` |
| `agreed_rate` | no | `None` |

### `kamra.api.room_move_preview`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

What a move would do to the bill before the desk confirms it: a
same-type swap keeps the price (and the locked nightly rates); an
upgrade / downgrade on an auto-priced booking is re-quoted at the new
type's rate by the pricing engine, and move_reservation then needs
confirm_price=1.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `new_room` | yes |  |
| `rate_mode` | no | `'destination'` |
| `agreed_rate` | no | `None` |

### `kamra.api.movable_rooms`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Every room the booking could move into - across ALL room types, so the
front desk can upgrade (Standard -> Suite) as well as swap same-type. Each
room is flagged free/occupied for the dates and carries its type name; the
booking's current type is listed first.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `check_in_date` | no | `None` |
| `check_out_date` | no | `None` |

### `kamra.api.amend_stay_preview`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

What new dates would do to the bill, before anything changes: the
current and new totals and the new nightly rates, priced by the engine
from today's rules. amend_stay needs confirm_price=1 when the total
changes.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `check_in_date` | yes |  |
| `check_out_date` | yes |  |

### `kamra.api.amend_stay`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Extend / shorten a stay; the overlap guard validates the new window.

An auto-priced stay is re-quoted for its new dates and its nightly
rates re-locked. That changes what the guest pays, so call
amend_stay_preview first, show the new price, and pass confirm_price=1;
without it a change in the total is refused. A manually-priced stay
keeps its amount.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `check_in_date` | yes |  |
| `check_out_date` | yes |  |
| `confirm_price` | no | `0` |

### `kamra.api.set_late_arrival`

**POST** · roles: `Front Desk`, `Kamra Agent`

Flag (or unflag) a confirmed arrival as arriving late, optionally with
the ETA the guest gave. With the property's late-arrival protection on,
the night audit holds a flagged arrival as Due In instead of marking it
a no-show; the next audit decides.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `late_arrival` | no | `1` |
| `eta` | no | `None` |

### `kamra.api.booking_options`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Everything the booking form needs to render its dropdowns.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.api.get_quote`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Price a stay. With a company and no rate plan, the company's
negotiated plan applies - the same plan create_booking stores.

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
| `over_capacity_charge` | no | `0` |
| `pets` | no | `0` |
| `company` | no | `None` |

### `kamra.api.create_booking`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

One-call booking: attach to an existing guest profile when given,
else dedup by phone / create one. Optional auto room assignment,
voucher applied, price computed by the engine.

waitlist=1 parks the stay with no room and status Waitlist - for dates
that are sold out or restricted; promote it later when a room frees.

status / idempotency_key / hold_expires_on support Instant public booking
(ADR-006 / ADR-007). Desk callers leave them unset → Confirmed.

Day use: check_out_date == check_in_date books a same-day stay, priced
by the quote engine (one billable date). check_in_time / check_out_time
(HH:MM) are its slot - they place it on the hourly tape and tell
housekeeping when the room turns; on an overnight stay they are the
ETA / ETD.

A stay billed to a company on credit runs the property's credit control
(kamra.credit) for its amount: a warning comes back as `credit_warning`;
a block refuses (CREDIT_BLOCKED) unless Finance or a Hotel Admin passes
`credit_override_reason`, which is logged. Agents can't override.

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
| `room` | no | `None` |
| `status` | no | `None` |
| `idempotency_key` | no | `None` |
| `hold_expires_on` | no | `None` |
| `over_capacity_reason` | no | `None` |
| `over_capacity_guests` | no | `0` |
| `over_capacity_charge` | no | `0` |
| `check_in_time` | no | `None` |
| `check_out_time` | no | `None` |
| `blacklist_override_reason` | no | `None` |
| `pets` | no | `0` |
| `credit_override_reason` | no | `None` |
| `booked_via` | no | `None` |
| `ota_ref` | no | `None` |
| `ota_total` | no | `0` |
| `ota_commission_pct` | no | `None` |
| `marketing_consent` | no | `0` |

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

Booked via an OTA (see create_booking): every room carries the site and
the one OTA reference, and the sold total (`ota_total`, tax included) is
split across the rooms in proportion to their rate-card prices, each
room locked to its share.

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
| `booked_via` | no | `None` |
| `ota_ref` | no | `None` |
| `ota_total` | no | `0` |
| `ota_commission_pct` | no | `None` |

### `kamra.api.inventory_availability`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`, `Revenue Manager`, `Hotel Admin`

Sellable Unit availability (ADR-003). Prefer this over ad-hoc room SQL.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `check_in_date` | yes |  |
| `check_out_date` | yes |  |
| `room_type` | no | `None` |
| `siu` | no | `None` |
| `include_reasons` | no | `0` |

### `kamra.api.available_rooms`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Rooms of a type with no overlapping live reservation - the same
logic the double-booking guard enforces, exposed as a query. Confirmed
group blocks hold their unsold rooms out of general sale; pass the
group to book against its own block.

A stay may start on another's departure date, so a room whose guest
departs today is "free" for a booking. Pass ready_now=1 when the guest
is being put in the room now (check-in, walk-in, allocation for today):
a room whose occupant is still Checked In is then left out until they
check out - the same rule Reservation.validate_room_vacant enforces.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `room_type` | yes |  |
| `check_in_date` | yes |  |
| `check_out_date` | yes |  |
| `group_booking` | no | `None` |
| `ready_now` | no | `0` |

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
signed-in user have one set yet? Includes unlock / lockout state.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.api.set_cashier_pin`

**POST** · roles: `Finance`, `Front Desk`, `Revenue Manager`, `Housekeeping`

Set or change your own cashier PIN (4-8 digits). Changing an existing
PIN needs the current one  -  unless must_reset was set by an admin.

| Param | Required | Default |
| --- | --- | --- |
| `pin` | yes |  |
| `current_pin` | no | `None` |

### `kamra.api.reset_cashier_pin`

**POST** · roles: `Hotel Admin`

Admin reset: wipe the user's PIN and force re-enrollment.

| Param | Required | Default |
| --- | --- | --- |
| `user` | yes |  |

### `kamra.api.verify_cashier_pin`

**POST** · roles: `Finance`, `Front Desk`, `Revenue Manager`, `Housekeeping`

PinPad unlock: validate PIN and open a 15-minute sliding window.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `pin` | yes |  |

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
dates against its held inventory. Every call books a room (a block is
several identical rooms for one party); pass idempotency_key to make a
retry safe.

| Param | Required | Default |
| --- | --- | --- |
| `group_booking` | yes |  |
| `room_type` | yes |  |
| `guest_name` | yes |  |
| `phone` | no | `None` |
| `adults` | no | `2` |
| `children` | no | `0` |
| `idempotency_key` | no | `None` |

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
so no screen hardcodes ₹ or GST %. `integrations` says which country
integrations (gateways, tax return, ID checks) this property has.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.api.verify_tax_id`

**POST** · roles: `Front Desk`, `Finance`

Check a buyer's tax ID before the invoice goes out, where the
property's country pack offers it.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `tax_id` | yes |  |
| `business_name` | no | `''` |

### `kamra.api.verify_guest_id`

**POST** · roles: `Front Desk`

Read the guest's ID document on file into the profile, where the
property's country pack offers it. consent: the desk confirms the guest
was told.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `guest` | yes |  |
| `id_type` | yes |  |
| `consent` | no | `0` |

### `kamra.api.zatca_settings`

**GET/POST** · roles: `Finance`

The property's ZATCA (Saudi e-invoicing) settings, created from the
property on first use, plus what is still missing for a valid invoice
and where the invoice chain stands.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.api.zatca_invoice_xml`

**GET/POST** · roles: `Finance`

The UBL XML behind an issued invoice or credit note - for the
accountant, an auditor or a ZATCA query.

| Param | Required | Default |
| --- | --- | --- |
| `invoice_number` | yes |  |
| `property` | yes |  |
| `document_type` | no | `'Invoice'` |

### `kamra.api.localization_countries`

**GET/POST**

Countries with a dedicated tax & invoicing pack, with the currency,
time zone and tax vocabulary picking one sets up. Read-only reference
data for the setup wizard and Settings.

### `kamra.api.pending_deposit_refunds`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Returns a list of checked-out reservations with pending security deposit refunds
for NEFT processing (e.g. Tuesday/Saturday payout batches).

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |


## Request to Book (accept / decline)

### `kamra.booking_requests.booking_requests`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

Pending Request-to-Book stays (status Requested), oldest first, each
with whether it can be accepted right now. Requests hold no inventory
until accepted - rooms_free is live availability, not a reservation.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.booking_requests.accept_booking_request`

**POST** · roles: `Front Desk`, `Kamra Agent`

Accept a Request-to-Book stay: confirm it and take the inventory,
assigning a free room of its type (or `room`). Every booking rule runs
again - double-booking guard, villa &lt;-> room lockout, category capacity,
group-block holds - so a request whose dates sold in the meantime is
refused with the reason; decline it instead.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `room` | no | `None` |

### `kamra.booking_requests.decline_booking_request`

**POST** · roles: `Front Desk`, `Kamra Agent`

Decline a Request-to-Book stay with a reason (required). The stay is
cancelled with no cancellation fee - a request was never confirmed - and
any room it pointed at is freed. The guest is told by WhatsApp / email
when the property has them set up; otherwise the decline is just logged.
An OTA request must also be declined on the OTA's side.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `reason` | yes |  |


## Restaurant POS & kitchen

### `kamra.pos.outlets`

**GET/POST**

Open outlets, each with `auto_kot` already resolved against the F&B
setting, so the till never has to know where the answer came from.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.pos.pos_menu`

**GET/POST**

The digital menu for an outlet: available items grouped by category.

| Param | Required | Default |
| --- | --- | --- |
| `outlet` | yes |  |

### `kamra.pos.in_house_rooms`

**GET/POST**

Rooms with a checked-in guest, for the till's room picker: only these
can take a room charge. "101 · Guest Name". `room_charges_allowed` is the
check-in's decision; a blocked room is shown but cannot be charged.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.pos.charge_to_room`

**POST**

Point a running bill (a dine-in table, say) at an in-house guest's
room, so Deliver posts it to their folio through the same controller
path as room service - billing rules and the alcohol rule included.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |
| `room` | yes |  |

### `kamra.pos.create_order`

**POST**

Captain takes an order. A room (room service, or a dine-in guest
charging to their room) must have a checked-in stay: it is resolved now
so the bill posts to that folio on delivery. A room with nobody in house
is refused - take it as a walk-in bill instead. Takeaway and delivery
carry the customer's details instead of a table/room. `guest` ties the
bill to a guest profile (a walk-in found or added with find_customer or
attach_customer); a room bill takes the in-house guest by itself.

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
| `guest` | no | `None` |

### `kamra.pos.open_orders`

**GET/POST**

Every running tab at an outlet - the tables/rooms being served right
now, so a captain can juggle several at once. A bill nobody has sent to
the kitchen carries its age in minutes and turns `stale` after the F&B
setting's limit, so a forgotten order is sent or cancelled.

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

One order's full contents - to load a running tab back into the till,
or to look at a closed one from the orders list. `kitchen_lines` counts
the live lines the kitchen already has: while it is zero the captain can
cancel the bill alone; after that a supervisor approves.

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

Captain confirmation for a Placed order that has no captain yet
(legacy guest QR). Sets the captain and moves Placed -> Confirmed.

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

With auto KOT on (the F&B setting, or the outlet's override) this also
accepts the ticket, so the kitchen does not press Start, and the
response tells the till to print.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |
| `course` | no | `None` |

### `kamra.pos.send_order`

**POST**

A captain's new bill straight to the kitchen, in one call: what
create_order, apply_discount, confirm_order and fire_kot do one after
another, in one request and one transaction. The till waits for one
round trip instead of four, and the kitchen gets a single update.

| Param | Required | Default |
| --- | --- | --- |
| `outlet` | yes |  |
| `items` | yes |  |
| `property` | no | `None` |
| `room` | no | `None` |
| `reservation` | no | `None` |
| `table_no` | no | `None` |
| `notes` | no | `None` |
| `order_type` | no | `None` |
| `guests` | no | `None` |
| `customer_name` | no | `None` |
| `customer_phone` | no | `None` |
| `delivery_address` | no | `None` |
| `allergy_note` | no | `None` |
| `discount` | no | `0` |
| `discount_reason` | no | `''` |
| `guest` | no | `None` |

### `kamra.pos.send_round`

**POST**

Another round on a running bill, straight to the kitchen: add_items
and fire_kot in one call and one save.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |
| `items` | yes |  |

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
closes the order without touching any folio. Posts into the open
cashier session so FO + POS cash reconcile together.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |
| `mode` | yes |  |
| `pin` | no | `None` |

### `kamra.pos.change_payment_mode`

**POST**

Correct the tender on a bill that was settled with the wrong mode (Card
pressed for Cash). The till keeps its history: a reversing entry for the
old mode and a new entry for the right one, same till session, with a
comment on the bill. Only while that till is still open - once it is
counted and closed, the day's cash is final and a manager must correct it
from the till screens.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |
| `mode` | yes |  |
| `reason` | no | `''` |
| `pin` | no | `None` |

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

Cancel an open bill with a reason. Nothing sent to the kitchen yet: the
captain (or an agent) cancels alone. Items already sent: every live line
is voided rather than deleted, the kitchen gets a VOID slip and sees the
ticket as cancelled, and a supervisor approves (`supervisor` +
`supervisor_pin`, or a supervisor's own session). Paid, posted or
already cancelled bills are refused. Who, why and who approved are kept
on the bill and in the activity log; the table is freed.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |
| `reason` | no | `''` |
| `reason_code` | no | `None` |
| `supervisor` | no | `None` |
| `supervisor_pin` | no | `None` |

### `kamra.pos.void_item`

**POST**

Void one line with a reason. The line stays on the order (struck
through, amount zero) so the KOT-vs-bill audit holds up. A line the
kitchen already has needs a supervisor's approval (see cancel_order) and
prints a VOID slip; a line never sent is simpler to remove_item.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |
| `item_row` | yes |  |
| `reason` | no | `''` |
| `reason_code` | no | `None` |
| `supervisor` | no | `None` |
| `supervisor_pin` | no | `None` |

### `kamra.pos.remove_item`

**POST**

Take a line off a bill before it goes to the kitchen: a mis-tap or a
change of mind. No reason and no approval, because nothing was cooked.
A line the kitchen has is refused (void it instead), and so is the last
line (cancel the bill instead).

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |
| `item_row` | yes |  |

### `kamra.pos.void_approvers`

**GET/POST**

Who can approve a void at this outlet's till: enabled Hotel Admin and
Finance users with access to the property and a cashier PIN set. Names
only.

| Param | Required | Default |
| --- | --- | --- |
| `outlet` | yes |  |

### `kamra.pos.orders_list`

**GET/POST**

The outlet's bills for a day, or a range of up to a year, newest
first: open (not sent to the kitchen), sent, paid, posted to a room, NC,
closed or cancelled, with the table, who it was for, the amount and the
time. `q` searches the bill and KOT number, table, room, customer name
and phone, and the in-house guest's name. `state` keeps one state,
`order_type` one kind of order and `mode` one way of paying (Cash, Card,
UPI, Room). Pages come back `limit` at a time from `offset`; `total`,
`has_more`, `counts` and `totals` always cover every bill the filters
match, not only the page, so nothing is hidden by paging.
Looking at today also brings in bills still open from earlier days
(`carried`), so a forgotten order cannot hide. Only this outlet's bills.

| Param | Required | Default |
| --- | --- | --- |
| `outlet` | yes |  |
| `date` | no | `None` |
| `to_date` | no | `None` |
| `q` | no | `None` |
| `state` | no | `None` |
| `limit` | no | `200` |
| `offset` | no | `0` |
| `order_type` | no | `None` |
| `mode` | no | `None` |

### `kamra.pos.orders_export`

**GET/POST**

The outlet's bill history as CSV for a day or up to a year: every
bill with its state, payment mode, amount, discount, who it was for and
who cancelled it. Same search and state filters as the orders list;
`mode` keeps one payment mode (Cash, Card, UPI). A phone number is masked
except to a supervisor, as on the till. Returns {filename, csv, rows}.

| Param | Required | Default |
| --- | --- | --- |
| `outlet` | yes |  |
| `date` | no | `None` |
| `to_date` | no | `None` |
| `q` | no | `None` |
| `state` | no | `None` |
| `mode` | no | `None` |
| `order_type` | no | `None` |

### `kamra.pos.find_customer`

**GET/POST**

Find a guest profile for a bill by phone (4+ digits) or name (3+
letters): the same guest records the front desk uses. Each match says
how often they ate at this outlet and whether they are in house now.
Phones show their last digits only.

| Param | Required | Default |
| --- | --- | --- |
| `outlet` | yes |  |
| `q` | yes |  |

### `kamra.pos.attach_customer`

**POST**

Say who a walk-in bill is for: an existing guest profile (`guest`),
or a name and phone. A phone that matches a profile reuses it; otherwise
a lightweight guest profile is added (name and phone only), the same
record the front desk uses. Without `order` it only finds or adds the
profile, for a bill the till is about to create. `clear=1` takes the
customer off the bill. A room bill is always for its in-house guest.

| Param | Required | Default |
| --- | --- | --- |
| `outlet` | yes |  |
| `order` | no | `None` |
| `guest` | no | `None` |
| `customer_name` | no | `None` |
| `phone` | no | `None` |
| `clear` | no | `0` |

### `kamra.pos.guest_panel`

**GET/POST**

Who a bill is for, without leaving the till. For a room bill: the
in-house guest, room, stay dates and whether the stay can take room
charges (the check-in's decision, which posting also enforces). For a
walk-in: the attached guest profile. Either way: VIP, the guest's notes
(preferences, allergies), the bill's allergy note, and their past bills
at this outlet. Pass `order`, or `guest` / `room` for a bill not created
yet.

| Param | Required | Default |
| --- | --- | --- |
| `outlet` | yes |  |
| `order` | no | `None` |
| `guest` | no | `None` |
| `room` | no | `None` |

### `kamra.pos.bill_data`

**GET/POST**

Everything the thermal bill print needs: outlet and property names,
live lines, the discount, and the CGST/SGST split at the outlet's rate.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |

### `kamra.pos.outlet_dashboard`

**GET/POST**

One shift at a glance: what the outlet sold, what's still open, the
exceptions that need a manager's eye (NC, voids, cancellations), and how
fast the kitchen is turning tickets. Defaults to today.

| Param | Required | Default |
| --- | --- | --- |
| `outlet` | yes |  |
| `date` | no | `None` |
| `to_date` | no | `None` |

### `kamra.pos.speed_check`

**GET/POST** · roles: `Hotel Admin`, `Finance`

Why does the POS feel slow here? Times what a till and a kitchen
display ask for on every refresh and reports the server's set-up, so
support can tell our code from the hosting in a minute. Read-only.

With echo=1 it also sends a realtime ping to the caller; the browser
times how long it takes to arrive, which proves live updates work.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `outlet` | no | `None` |
| `echo` | no | `0` |


## Setup checklist (finish setting up a property)

### `kamra.onboarding.setup_checklist`

**GET/POST** · roles: `Front Desk`, `Finance`, `Hotel Admin`, `Kamra Agent`

What is set up and what is still to do, for the Finish setup screen.
Only items that matter for the modules this property runs.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |


## Rates (rate calendar, what moves a rate)

> These explain a price; they never set one. The quote is the only source of a charge.

### `kamra.rates.rate_calendar`

**GET/POST**

Every room type's rate for each of the next `days` dates, with what
moved it. A room type's own days are read with the same functions the
quote uses; nothing here sets a price.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `from_date` | no | `None` |
| `days` | no | `14` |
| `adults` | no | `2` |
| `children` | no | `0` |

### `kamra.rates.rate_options`

**GET/POST**

For the booking dialog: this stay night by night (BAR, season,
demand), the whole stay under each active rate plan against the plain
rate, and what the voucher would do. Each total is a real quote.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `room_type` | yes |  |
| `check_in_date` | yes |  |
| `check_out_date` | yes |  |
| `adults` | no | `2` |
| `children` | no | `0` |
| `meal_plan` | no | `None` |
| `voucher_code` | no | `None` |


## Service tickets (assign, resolve, timeline)

### `kamra.tickets.tickets_search`

**GET/POST**

Tickets for a property with the filters a supervisor needs.

view: open (default), mine, unassigned, overdue, resolved, all. Old
tickets are never hidden: 'all' and 'resolved' go back as far as the
data does, and older_than_days narrows to the ones still open past that.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `view` | no | `'open'` |
| `category` | no | `None` |
| `priority` | no | `None` |
| `q` | no | `None` |
| `assignee` | no | `None` |
| `older_than_days` | no | `0` |
| `limit` | no | `200` |

### `kamra.tickets.ticket_detail`

**GET/POST**

One ticket in full: its fields, SLA, and the timeline.

| Param | Required | Default |
| --- | --- | --- |
| `ticket` | yes |  |

### `kamra.tickets.ticket_assignees`

**GET/POST**

Staff a ticket can be handed to.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.tickets.assign_ticket`

**POST**

Hand a ticket to someone, or clear the assignee (user empty).

| Param | Required | Default |
| --- | --- | --- |
| `ticket` | yes |  |
| `user` | no | `None` |
| `note` | no | `None` |

### `kamra.tickets.claim_ticket`

**POST**

Take a ticket yourself.

| Param | Required | Default |
| --- | --- | --- |
| `ticket` | yes |  |

### `kamra.tickets.start_ticket`

**POST**

Begin work: moves it to In Progress and, if nobody has it, gives it to you.

| Param | Required | Default |
| --- | --- | --- |
| `ticket` | yes |  |

### `kamra.tickets.add_ticket_note`

**POST**

A comment on the timeline (what was tried, who was called).

| Param | Required | Default |
| --- | --- | --- |
| `ticket` | yes |  |
| `note` | yes |  |

### `kamra.tickets.resolve_ticket`

**POST**

Mark a ticket solved, recording who did it and what was done.

| Param | Required | Default |
| --- | --- | --- |
| `ticket` | yes |  |
| `resolution_note` | no | `None` |
| `close` | no | `0` |

### `kamra.tickets.reopen_ticket`

**POST**

A solved ticket that came back. Needs a reason; it is kept in the timeline.

| Param | Required | Default |
| --- | --- | --- |
| `ticket` | yes |  |
| `reason` | yes |  |


## Guest documents (photo, ID and address proof images)

> Stored privately and served as data URLs to the desk. A property on Verify & Discard keeps no ID images.

### `kamra.guest_documents.save_guest_file`

**POST** · roles: `Front Desk`, `Kamra Agent`

Keep a photo, ID image or address proof on the profile, replacing the
previous one. A property on Verify & Discard keeps no ID images, so only
the photo is accepted there (the check-in ID step verifies and discards).

| Param | Required | Default |
| --- | --- | --- |
| `guest` | yes |  |
| `kind` | yes |  |
| `data` | yes |  |

### `kamra.guest_documents.guest_file`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`

One of the profile's images as a data URL.

| Param | Required | Default |
| --- | --- | --- |
| `guest` | yes |  |
| `kind` | yes |  |

### `kamra.guest_documents.remove_guest_file`

**POST** · roles: `Front Desk`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `guest` | yes |  |
| `kind` | yes |  |


## Kitchen printers (routing, print stations, print queue)

### `kamra.printing.print_bill`

**POST**

Send a bill to the station set up to print bills. No bill printer
configured: nothing is queued and the till prints from its own device,
exactly as before.

| Param | Required | Default |
| --- | --- | --- |
| `order` | yes |  |
| `terminal` | no | `None` |

### `kamra.printing.claim_jobs`

**POST**

A print station asks for its printer's work. Hands over every queued
job (and any claimed one nobody confirmed within a minute) and marks
them Printing. The station prints them and calls ack_jobs.

| Param | Required | Default |
| --- | --- | --- |
| `printer` | yes |  |

### `kamra.printing.ack_jobs`

**POST**

The station's answer. Printed jobs are done; failed ones move to the
printer's fallback, or stay Failed for a reprint.

| Param | Required | Default |
| --- | --- | --- |
| `printer` | yes |  |
| `printed` | no | `None` |
| `failed` | no | `None` |
| `error` | no | `None` |

### `kamra.printing.printers`

**GET/POST**

Every printer with its routes and whether it's online - for the
F&B Printers screen and for a kitchen screen choosing what to print for.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.printing.save_printer`

**POST**

Add or change a printer and its routes. Logged to the Activity log.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `printer` | yes |  |
| `name` | no | `None` |

### `kamra.printing.delete_printer`

**POST**

| Param | Required | Default |
| --- | --- | --- |
| `name` | yes |  |

### `kamra.printing.test_print`

**POST**

Queue a test page on one printer.

| Param | Required | Default |
| --- | --- | --- |
| `name` | yes |  |

### `kamra.printing.reprint`

**POST**

Print a job again - on its own printer or another one.

| Param | Required | Default |
| --- | --- | --- |
| `job` | yes |  |
| `printer` | no | `None` |

### `kamra.printing.order_print_status`

**GET/POST**

Where an order's tickets went and whether they printed - for the till.

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

session is how the hall is sold (Morning / Afternoon / Evening / Full
Day): a named session sets the clock itself, so times sent alongside it
are ignored. Custom Hours, or no session with times, keeps the times.

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
| `follow_up_days` | no | `None` |
| `with_venue_line` | no | `1` |
| `sales_owner` | no | `None` |
| `session` | no | `None` |

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

### `kamra.banquet.linkable_groups`

**GET/POST**

Group bookings this function could ride: same property, not
cancelled, staying within a month either side of the event.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |

### `kamra.banquet.link_group`

**POST**

Tie a function to a group booking so its bill can ride the group's
master folio (post_to_folio), or untie it (group_booking empty).

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `group_booking` | no | `None` |

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
completion. Editable afterwards like any other term. Unset arguments
come from Settings -> Banquets & Groups.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `advance_percent` | no | `None` |
| `interim_percent` | no | `None` |
| `interim_days_before` | no | `None` |

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

### `kamra.banquet.generate_invoice`

**POST** · roles: `Finance`

Raise the tax invoice for a function.

The number is assigned once and never moves - re-printing an invoice
must give the same document, because the customer's books and ours
have to agree on what it was called.

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

### `kamra.banquet.reopen_function`

**POST**

Reopen a closed (Completed) function so its sheet can be corrected.
It goes back to Confirmed; receipts, refunds and the damage line stay
as they were, and closing it again re-counts covers only. Needs a
reason, and lands on the activity log.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `reason` | yes |  |

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

### `kamra.banquet.quote_advisor`

**GET/POST** · roles: `Finance`

Would this function make money at the price we're about to send?

Margin after the event is an autopsy. The number that changes a
decision is the one on screen while the discount is still being typed
- so this answers, for the price as it stands: what's left, how much
more could be given away before it stops being worth doing, and where
the cost actually sits.

`at_discount` prices a what-if without touching the quote.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `at_discount` | no | `None` |

### `kamra.banquet.offer_amenities`

**POST**

Put the hall's chargeable extras on the function.

A hall's air-conditioning and generator come with it; its extra mics,
its valet parking and its second generator do not. Those live on the
venue, and this is how they reach a quote - either priced onto it, or
parked as open items when the customer hasn't decided yet, which is
where most of them actually sit while a wedding is being agreed.

| Param | Required | Default |
| --- | --- | --- |
| `function` | yes |  |
| `amenities` | no | `None` |
| `as_open_items` | no | `0` |

### `kamra.banquet.venue_detail`

**GET/POST**

One hall in full: what it holds, what it comes with, what it costs
to open, and which other spaces it shares its floor with.

| Param | Required | Default |
| --- | --- | --- |
| `venue` | yes |  |


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

Import the file (see _run_import). Migrated stays are not new
business, so they never reach outbound webhook subscribers.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `csv_text` | yes |  |
| `preset` | no | `'auto'` |


## Go-live data (companies, opening balances, reconciliation)

### `kamra.golive.csv_template`

**GET/POST** · roles: `Finance`

The header row of one of Kamra's go-live CSV templates.

| Param | Required | Default |
| --- | --- | --- |
| `kind` | yes |  |

### `kamra.golive.preview_companies`

**POST** · roles: `Finance`

Dry run of the companies file: column mapping, which companies are
new and which already exist (they are updated, never duplicated).

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `csv_text` | yes |  |

### `kamra.golive.run_companies`

**POST** · roles: `Finance`

Create or update each company (an upsert, so a re-run changes
nothing) and, for a company on credit, its city ledger account at this
property with the credit limit.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `csv_text` | yes |  |

### `kamra.golive.preview_opening`

**POST** · roles: `Finance`

Dry run of the opening-balance file: what each row matched, totals
per category, what is already posted (a re-run skips it) and every row
that can't be posted. Nothing is written.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `csv_text` | yes |  |

### `kamra.golive.run_opening`

**POST** · roles: `Finance`

Post the opening balances. Each item is posted once: a re-run of the
same file finds it in Kamra and skips it (and says so). Company bills
go in before company credits, so a credit settles the oldest bill.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `csv_text` | yes |  |

### `kamra.golive.reconcile`

**POST** · roles: `Finance`

Counts and totals in each go-live file against what is now in Kamra,
per category. `ready` is true only when every category matches and no
row of any file was left out - the gate before the hotel goes live.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `opening_csv` | no | `None` |
| `companies_csv` | no | `None` |
| `bookings_csv` | no | `None` |


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
| `gst_rate` | no | `None` |
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

**GET/POST** · roles: `Finance`, `Front Desk`, `Night Auditor`, `Kamra Agent`

The daily flash: yesterday's performance, month to date, today's
movement, collections by mode, and the 7-day outlook. With from_date,
the day figures, trend, movement and collections cover from_date..date.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `date` | no | `None` |
| `from_date` | no | `None` |

### `kamra.reports.budget_vs_actual`

**GET/POST** · roles: `Finance`, `Revenue Manager`, `Kamra Agent`

Monthly target vs actual: room revenue, occupancy %, ADR, RevPAR - with
variance. period is 'YYYY-MM' (defaults to the current month).

"Actual" is posted money: Room charges on folios, dated inside the month.
A room night reaches a folio when End of Day (night audit) posts it, so a
stay in-house tonight counts once its night is audited - not before.
Occupancy and RevPAR divide by the room nights elapsed so far (to the
business date), not the whole month, so a month-to-date figure compares
with a monthly occupancy target. `on_books_nights` / `unposted_nights`
say how many sold nights in the same window are still waiting for End
of Day, so a zero is explained rather than mysterious.

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

Who brings the business: revenue + room nights + share + the
commission paid for it (travel agent or OTA), grouped by booking source,
company, travel agent or OTA channel.
by = source | company | travel_agent | channel.

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


## Custom reports (builder, save, email)

> Whitelisted datasets only - no Desk Query Reports or free SQL. Saved definitions live on Kamra Custom Report; staff use Finance → Reports.

### `kamra.custom_reports.list_report_datasets`

**GET/POST** · roles: `Front Desk`, `Finance`, `Hotel Admin`, `Revenue Manager`, `Housekeeping`, `Kamra Agent`, `Night Auditor`

Whitelisted datasets the current user may run on this property.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.custom_reports.list_report_packs`

**GET/POST** · roles: `Front Desk`, `Finance`, `Hotel Admin`, `Revenue Manager`, `Housekeeping`, `Kamra Agent`, `Night Auditor`

Department packs with the sections this user may run here.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.custom_reports.run_report_pack`

**GET/POST** · roles: `Front Desk`, `Finance`, `Hotel Admin`, `Revenue Manager`, `Housekeeping`, `Kamra Agent`, `Night Auditor`

Run a department pack (id from list_report_packs) for a date range.
format=json (sections of rows) or html (one printable page).
compare=1 (default) adds this-vs-previous totals on each section.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `pack` | yes |  |
| `from_date` | no | `None` |
| `to_date` | no | `None` |
| `format` | no | `'json'` |
| `lang` | no | `'en'` |
| `compare` | no | `1` |

### `kamra.custom_reports.list_custom_reports`

**GET/POST** · roles: `Front Desk`, `Finance`, `Hotel Admin`, `Revenue Manager`, `Housekeeping`, `Kamra Agent`, `Night Auditor`

Saved reports visible to this user on the property.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.custom_reports.get_custom_report`

**GET/POST** · roles: `Front Desk`, `Finance`, `Hotel Admin`, `Revenue Manager`, `Housekeeping`, `Kamra Agent`, `Night Auditor`

Full saved definition for the builder.

| Param | Required | Default |
| --- | --- | --- |
| `name` | yes |  |
| `property` | no | `None` |

### `kamra.custom_reports.save_custom_report`

**POST** · roles: `Finance`, `Hotel Admin`, `System Manager`, `Front Desk`, `Revenue Manager`, `Housekeeping`, `Kamra Agent`, `Night Auditor`

Create or update a saved custom report definition. lang (en, es, ar)
is the language its scheduled emails go out in.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `title` | yes |  |
| `dataset` | yes |  |
| `columns` | no | `None` |
| `filters` | no | `None` |
| `group_by` | no | `None` |
| `sort` | no | `None` |
| `is_shared` | no | `0` |
| `schedule_frequency` | no | `'Off'` |
| `schedule_time` | no | `'07:00'` |
| `schedule_weekday` | no | `'Mon'` |
| `recipients` | no | `''` |
| `name` | no | `None` |
| `lang` | no | `None` |

### `kamra.custom_reports.delete_custom_report`

**POST** · roles: `Finance`, `Hotel Admin`, `System Manager`, `Front Desk`, `Revenue Manager`, `Housekeeping`, `Kamra Agent`, `Night Auditor`

Delete a saved report the user can edit.

| Param | Required | Default |
| --- | --- | --- |
| `name` | yes |  |
| `property` | no | `None` |

### `kamra.custom_reports.run_custom_report`

**GET/POST** · roles: `Front Desk`, `Finance`, `Hotel Admin`, `Revenue Manager`, `Housekeeping`, `Kamra Agent`, `Night Auditor`

Run a saved report or an ad-hoc definition. format=json|csv|html.
compare=1 adds this-vs-previous totals for number columns.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `dataset` | no | `None` |
| `from_date` | no | `None` |
| `to_date` | no | `None` |
| `columns` | no | `None` |
| `filters` | no | `None` |
| `group_by` | no | `None` |
| `sort` | no | `None` |
| `name` | no | `None` |
| `format` | no | `'json'` |
| `lang` | no | `'en'` |
| `compare` | no | `0` |

### `kamra.custom_reports.email_custom_report`

**POST** · roles: `Finance`, `Hotel Admin`, `System Manager`, `Front Desk`, `Revenue Manager`, `Housekeeping`, `Kamra Agent`, `Night Auditor`

Run a report and email it (CSV or HTML attachment).

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `recipients` | yes |  |
| `name` | no | `None` |
| `dataset` | no | `None` |
| `from_date` | no | `None` |
| `to_date` | no | `None` |
| `columns` | no | `None` |
| `filters` | no | `None` |
| `group_by` | no | `None` |
| `sort` | no | `None` |
| `lang` | no | `'en'` |
| `attach_format` | no | `'csv'` |


## Ledgers (trial balance, city ledger / AR, FX desk)

### `kamra.ledger.ledger_balances`

**GET/POST** · roles: `Finance`, `Front Desk`, `Hotel Admin`, `Night Auditor`, `Kamra Agent`

Four-ledger trial balance for a property (optionally as-of a date).

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `business_date` | no | `None` |

### `kamra.ledger.journal_by_transaction_code`

**GET/POST** · roles: `Finance`, `Front Desk`, `Hotel Admin`, `Night Auditor`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `business_date` | no | `None` |

### `kamra.ledger.financial_activity`

**GET/POST** · roles: `Finance`, `Hotel Admin`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `business_date` | no | `None` |
| `user` | no | `None` |

### `kamra.ledger.city_ledger_transfer`

**POST** · roles: `Finance`, `Front Desk`, `Kamra Agent`

Move a folio's unpaid balance to the company's city ledger. Runs the
property's credit control: over the credit limit or with overdue bills
it warns, or refuses (CREDIT_BLOCKED) unless Finance or a Hotel Admin
passes `credit_override_reason`. Agents can't override.

| Param | Required | Default |
| --- | --- | --- |
| `folio` | yes |  |
| `company` | no | `None` |
| `pin` | no | `None` |
| `credit_override_reason` | no | `None` |

### `kamra.ledger.city_ledger_settle`

**POST** · roles: `Finance`, `Hotel Admin`, `Kamra Agent`

Record a company's payment against its city ledger account and clear
the AR it pays. By default it pays the oldest open bills first;
`allocations` ([{folio, amount}]) names the folios instead. Any excess
stays on the account as unapplied credit and settles the company's next
bill.

| Param | Required | Default |
| --- | --- | --- |
| `account` | yes |  |
| `amount` | yes |  |
| `mode` | no | `'Bank Transfer'` |
| `reference` | no | `None` |
| `allocations` | no | `None` |

### `kamra.ledger.city_ledger_aging`

**GET/POST** · roles: `Finance`, `Hotel Admin`, `Front Desk`, `Night Auditor`, `Kamra Agent`

Every company's AR at the property, aged by due date (not_due,
d1_30, d31_60, d61_90, d90p and their sum `overdue`). The invoice-age
keys (current, b30, b60, b90, b90p) are kept for older callers.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.ledger.city_ledger_account`

**GET/POST** · roles: `Finance`, `Hotel Admin`, `Front Desk`, `Kamra Agent`

One company's city ledger: balance, aging, each open bill (oldest
first) and recent payments - what the payment screen needs.

| Param | Required | Default |
| --- | --- | --- |
| `account` | yes |  |

### `kamra.ledger.force_advance_bill`

**POST** · roles: `Front Desk`, `Finance`, `Kamra Agent`

Post future room (+ meal) charges ahead of night audit.

nights: 'tonight' | 'entire' | integer string of nights.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `nights` | no | `'entire'` |
| `pin` | no | `None` |

### `kamra.ledger.generate_proforma`

**POST** · roles: `Front Desk`, `Finance`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `folio` | yes |  |
| `notes` | no | `None` |

### `kamra.ledger.issue_credit_note`

**POST** · roles: `Finance`, `Hotel Admin`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `folio` | yes |  |
| `amount` | yes |  |
| `reason` | yes |  |
| `pin` | no | `None` |

### `kamra.ledger.record_folio_reprint`

**POST** · roles: `Front Desk`, `Finance`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `folio` | yes |  |
| `document` | no | `'Guest Folio'` |
| `reason` | no | `None` |

### `kamra.ledger.folio_history`

**GET/POST** · roles: `Front Desk`, `Finance`, `Hotel Admin`, `Night Auditor`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `query` | no | `None` |
| `status` | no | `None` |
| `from_date` | no | `None` |
| `to_date` | no | `None` |

### `kamra.ledger.batch_post_charge`

**POST** · roles: `Front Desk`, `Finance`, `Kamra Agent`

Post the same charge to many folios (group / event).

| Param | Required | Default |
| --- | --- | --- |
| `folios` | yes |  |
| `charge_type` | yes |  |
| `amount` | yes |  |
| `description` | no | `None` |
| `pin` | no | `None` |

### `kamra.ledger.batch_print_folios`

**POST** · roles: `Front Desk`, `Finance`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `folios` | yes |  |

### `kamra.ledger.quick_checkout`

**POST** · roles: `Front Desk`, `Night Auditor`, `Kamra Agent`

Check out and close the guest folio in one step. check_out settles the
stay the one way: the company's folio (Company, or the group master)
moves to the city ledger when the company has credit, and the guest's
own folio must already be paid - liquor and extras are never billed to
the company.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `pin` | no | `None` |

### `kamra.ledger.group_checkout`

**POST** · roles: `Front Desk`, `Kamra Agent`

Quick-checkout every Checked In reservation on a group.

| Param | Required | Default |
| --- | --- | --- |
| `group` | yes |  |
| `pin` | no | `None` |

### `kamra.ledger.list_exchange_rates`

**GET/POST** · roles: `Front Desk`, `Finance`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.ledger.upsert_exchange_rate`

**POST** · roles: `Finance`, `Hotel Admin`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `currency` | yes |  |
| `buy_rate` | yes |  |
| `sell_rate` | yes |  |
| `service_tax_pct` | no | `0` |
| `max_exchange` | no | `None` |

### `kamra.ledger.currency_calculator`

**GET/POST** · roles: `Front Desk`, `Finance`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `currency` | yes |  |
| `fx_amount` | yes |  |
| `direction` | no | `'Buy'` |

### `kamra.ledger.post_exchange`

**POST** · roles: `Front Desk`, `Finance`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `currency` | yes |  |
| `fx_amount` | yes |  |
| `direction` | no | `'Buy'` |
| `folio` | no | `None` |
| `guest` | no | `None` |
| `pin` | no | `None` |

### `kamra.ledger.exchange_history`

**GET/POST** · roles: `Front Desk`, `Finance`, `Hotel Admin`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `business_date` | no | `None` |

### `kamra.ledger.list_reason_codes`

**GET/POST** · roles: `Front Desk`, `Finance`, `Kamra Agent`

| Param | Required | Default |
| --- | --- | --- |
| `category` | no | `None` |


## Company credit (payment terms, credit limit, overdue check)

> Credit control is enforced inside check_out, create_booking and city_ledger_transfer; these endpoints explain and configure it.

### `kamra.credit.company_credit_status`

**GET/POST** · roles: `Front Desk`, `Finance`, `Hotel Admin`, `Night Auditor`, `Revenue Manager`, `Kamra Agent`

The credit check for billing `amount` more to a company, without
doing anything: what the booking dialog shows before a company stay is
booked. `applies` is False for a company not on credit.

| Param | Required | Default |
| --- | --- | --- |
| `company` | yes |  |
| `property` | yes |  |
| `amount` | no | `0` |

### `kamra.credit.checkout_credit_preview`

**GET/POST** · roles: `Front Desk`, `Finance`, `Hotel Admin`, `Night Auditor`, `Kamra Agent`

Before check-out: the credit check for each company the stay's bills
would move to, so the desk can warn, or ask Finance / a Hotel Admin to
override a block. Check-out re-runs the same check itself.

Check-out first posts any night not yet on the folio, so the preview
does the same inside a savepoint it rolls back - the amounts match
what check-out will move, and nothing is written.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |

### `kamra.credit.company_credit_terms`

**GET/POST** · roles: `Front Desk`, `Finance`, `Hotel Admin`, `Revenue Manager`

A company's credit terms at one property: limit, credit days and
what it owes (for the corporate account editor).

| Param | Required | Default |
| --- | --- | --- |
| `company` | yes |  |
| `property` | yes |  |

### `kamra.credit.set_company_credit_terms`

**POST** · roles: `Finance`, `Hotel Admin`

Set a company's credit limit (0 = no limit) and payment terms at one
property: `use_default_credit_days` 1 follows the property's default
payment terms; 0 uses `credit_days` as given (0 = due on the invoice
date). Creates its city ledger account if it has none. Logged with
before / after.

| Param | Required | Default |
| --- | --- | --- |
| `company` | yes |  |
| `property` | yes |  |
| `credit_limit` | no | `None` |
| `credit_days` | no | `None` |
| `use_default_credit_days` | no | `None` |


## Company statements (print, email; daily payment reminders)

### `kamra.statements.company_statement`

**GET/POST** · roles: `Finance`, `Hotel Admin`

One company's statement at its property: open bills with invoice
date, due date, days overdue and amounts, unapplied credit, recent
payments, totals and aging by due date. format=html returns the
printable page (print or save as PDF from the browser).

| Param | Required | Default |
| --- | --- | --- |
| `account` | yes |  |
| `format` | no | `'json'` |
| `lang` | no | `'en'` |

### `kamra.statements.email_company_statement`

**POST** · roles: `Finance`, `Hotel Admin`

Email a company its statement (HTML attachment). Without recipients
it goes to the company's billing contact email.

| Param | Required | Default |
| --- | --- | --- |
| `account` | yes |  |
| `recipients` | no | `None` |
| `lang` | no | `'en'` |


## Night audit (End of Day checklist, audit pack)

### `kamra.night_audit.night_audit_precheck`

**GET/POST**

The night audit checklist for the property's current business date.
Read-only. Each check: key, title, severity (block | warn | info),
count, items (with reservation / folio / room / guest / amount /
outlet and bill no where they apply) and a suggested action. A manual
audit refuses while a blocking check has items, unless each one is
acknowledged with a reason (run_night_audit acknowledge=[keys], note).

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.night_audit.night_audit_pack`

**GET/POST**

The saved audit pack of one Night Audit Run. Missing packs answer
has_pack: false with a message; rebuild_audit_pack can recreate them.

| Param | Required | Default |
| --- | --- | --- |
| `audit` | yes |  |

### `kamra.night_audit.rebuild_audit_pack`

**POST**

Rebuild and save the printable audit pack for a completed run.
Use when the automatic night left has_pack false, or to refresh the
pack. Does not re-post charges or roll the business date.

| Param | Required | Default |
| --- | --- | --- |
| `audit` | yes |  |

### `kamra.night_audit.recover_stuck_business_date`

**POST** · roles: `Finance`, `Hotel Admin`, `Night Auditor`, `Kamra Agent`

Advance the business date when a completed audit exists for the
current date but the roll did not stick. Never re-posts room nights.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.night_audit.night_audit_history`

**GET/POST**

Recent Night Audit Runs of a property, newest first, with whether
each has a saved audit pack.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `limit` | no | `20` |

### `kamra.night_audit.night_audit_schedule`

**GET/POST** · roles: `Finance`, `Hotel Admin`, `Night Auditor`

The automatic night audit at a glance: on or off, the next run on the
property clock (None = manual only), the business date and the last 30
runs, scheduled and manual, from the Night Audit Log.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.night_audit.eod_session`

**POST**

Open (or resume) End of Day for the property's current business date:
the draft run that keeps the wizard's progress, every pre-check and
the step list with each step's status (pending, done, blocked). With
`audit`, a finished run is shown at its final reports.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `audit` | no | `None` |

### `kamra.night_audit.eod_progress`

**POST**

Save the wizard's place: the current step (1-based), a step's status
(`key` + `status`: done | skipped | pending) and the manager notes.
A blocked step cannot be marked done - acknowledge it first.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `step` | no | `None` |
| `status` | no | `None` |
| `key` | no | `None` |
| `notes` | no | `None` |

### `kamra.night_audit.eod_acknowledge`

**POST**

Acknowledge a blocking check with a reason so End of Day can go on.
Who and when are recorded on the run and in the Activity log.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `key` | yes |  |
| `reason` | yes |  |

### `kamra.night_audit.eod_mark_no_show`

**POST** · roles: `Front Desk`, `Night Auditor`, `Hotel Admin`, `Kamra Agent`

End of Day: mark an arrival that did not come a No Show now, with the
property's no-show fee policy applied exactly as the audit applies it
(fee posted on the business date, or waived for an OTA booking).

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `reason` | no | `None` |

### `kamra.night_audit.eod_overview`

**GET/POST**

Manage End of Day: one row per property the user can access - the
business date, the property's local time, arrivals and departures
pending, open cashiers and POS bills, and the number of blockers.


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

Everything one ledger row knows  -  including the before/after
snapshots that are too heavy for the feed.

| Param | Required | Default |
| --- | --- | --- |
| `name` | yes |  |

### `kamra.agents_api.staff_sign_ins`

**GET/POST** · roles: `Hotel Admin`, `Finance`, `System Manager`

Who signed in to and out of Kamra, newest first: Frappe's own Login /
Logout records (Activity Log), limited to this property's staff. Only
what Frappe already stores is shown - who, when, in or out, and whether
the attempt worked. IP addresses are left out.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `limit` | no | `50` |
| `start` | no | `0` |
| `user` | no | `None` |


## Settings hub (module settings)

### `kamra.settings.menu_masters`

**GET/POST** · roles: `Finance`, `Front Desk`, `Night Auditor`, `Kamra Agent`

Allergen tags, prep stations, courses and category suggestions for
the Menu form and kitchen display. Edited under Settings → F&B → Menu
master lists.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.settings.settings_schema`

**GET/POST** · roles: `Front Desk`, `Finance`, `Revenue Manager`, `Housekeeping`, `Housekeeping Supervisor`

Every settings page this user may see for the property, with current
values. Pages they can't change come back read-only (can_edit=False).

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.settings.save_settings`

**POST** · roles: `Finance`, `Revenue Manager`, `Housekeeping Supervisor`

Change some settings on one module page. Validates every key against
the registry, refuses keys from another module, and writes one
Activity log row with the before/after values.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `module` | yes |  |
| `changes` | yes |  |

### `kamra.settings.set_module_enabled`

**POST** · roles: `Hotel Admin`

Switch one module on or off for the property.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `module` | yes |  |
| `enabled` | yes |  |


## Rooms (room board, room detail and history, insights)

> Read-only. Room changes go through set_housekeeping_status, the room block endpoints, check_in / check_out and move_reservation.

### `kamra.rooms.rooms_board`

**GET/POST**

Every room of the property as a tile: housekeeping status, who is in
it, who arrives or leaves today, whether it is out of service, and its
open housekeeping task. One call, a fixed number of queries.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.rooms.room_detail`

**GET/POST**

Everything about one room right now: what it is, its status, who is
in it (with the balance), who arrives next, whether it is held out of
service, and its open housekeeping work.

| Param | Required | Default |
| --- | --- | --- |
| `room` | yes |  |

### `kamra.rooms.room_availability`

**GET/POST**

This room, night by night: booked (by whom), held out of service, or
free. Same overlap rules as the tape chart and the block guard (the
check-out night is free; a day-use stay holds its own date).

| Param | Required | Default |
| --- | --- | --- |
| `room` | yes |  |
| `start_date` | no | `None` |
| `days` | no | `14` |

### `kamra.rooms.room_history`

**GET/POST**

Who stayed in this room lately (nights, room revenue), who cleaned
and checked it and when, its service tickets, and the guests moved in
or out of it.

| Param | Required | Default |
| --- | --- | --- |
| `room` | yes |  |
| `limit` | no | `15` |

### `kamra.rooms.room_insights`

**GET/POST**

Per-room numbers for the last `days` nights (7, 30, 90, 180 or 365,
up to yesterday): room nights sold and occupancy, room revenue posted to
folios, out-of-service nights, and how long cleans take. Cached for a
few minutes (refresh=1 recomputes); one query per measure, never one
per room.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `days` | no | `30` |
| `refresh` | no | `0` |
| `from_date` | no | `None` |
| `to_date` | no | `None` |


## Today layout (per-user widgets, hotel default)

### `kamra.today_layout.get_today_layout`

**GET/POST**

The layout this person sees on Today, and where it came from
("user", "property" or "default").

| Param | Required | Default |
| --- | --- | --- |
| `property` | no | `None` |

### `kamra.today_layout.save_today_layout`

**POST**

Save this person's own Today layout.

| Param | Required | Default |
| --- | --- | --- |
| `layout` | yes |  |
| `property` | no | `None` |

### `kamra.today_layout.reset_today_layout`

**POST**

Drop this person's own layout: back to the hotel default.

| Param | Required | Default |
| --- | --- | --- |
| `property` | no | `None` |

### `kamra.today_layout.save_today_layout_default`

**POST** · roles: `Hotel Admin`

Hotel Admin: the layout everyone at this property sees until they
customise their own. Pass no layout to go back to the built-in one.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `layout` | no | `None` |


## Desk procedures (check-out, check-in and other SOPs)

### `kamra.sop.get_sop`

**GET/POST** · roles: `Front Desk`, `Kamra Agent`, `Hotel Admin`

Return evaluated SOP steps for a procedure.

context is optional JSON (checkout_context shape for key=checkout). When
omitted, steps return as todo with template tips only.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `key` | yes |  |
| `context` | no | `None` |

### `kamra.sop.list_sops`

**GET/POST** · roles: `Hotel Admin`, `System Manager`, `Front Desk`, `Kamra Agent`

List SOP templates for the settings editor.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.sop.get_sop_template`

**GET/POST** · roles: `Hotel Admin`, `System Manager`

| Param | Required | Default |
| --- | --- | --- |
| `name` | yes |  |

### `kamra.sop.save_sop_template`

**POST** · roles: `Hotel Admin`, `System Manager`

Create or update an SOP template and its steps.

| Param | Required | Default |
| --- | --- | --- |
| `name` | no | `None` |
| `property` | no | `None` |
| `key` | no | `None` |
| `title` | no | `None` |
| `active` | no | `1` |
| `steps` | no | `None` |

### `kamra.sop.seed_sop_templates`

**POST** · roles: `Hotel Admin`, `System Manager`

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |


## Guided check-in (steps, who did each, room-charges permission)

> kamra.api.check_in refuses until every check-in step the property marks required is done. check_in_readiness says what is missing.

### `kamra.checkin.checkin_flow`

**GET/POST**

Everything the guided check-in shows, in one round trip: the steps
(required or optional, done, skipped or to do, and who did them), plus
what each step screen needs.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |

### `kamra.checkin.check_in_readiness`

**GET/POST** · roles: `Front Desk`, `Night Auditor`, `Finance`, `Hotel Admin`, `Kamra Agent`

Read-only: which check-in steps are done, whether check_in would go
through now (room assigned), and which soft-required steps are still
open to finish later. Agents read this; they cannot do the desk's
steps for it.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |

### `kamra.checkin.complete_checkin_step`

**POST**

The desk marks a step done (a confirm-only step, or the review of
what the guest sent online). Refused while what the step stands for is
not true yet - an ID still missing, a deposit not taken.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `step` | yes |  |
| `note` | no | `None` |

### `kamra.checkin.skip_checkin_step`

**POST**

Skip a step to finish later. Only the room cannot be skipped.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `step` | yes |  |
| `reason` | no | `None` |

### `kamra.checkin.save_guest_details`

**POST**

Correct the primary guest's contact and ID details at the desk. Only
what is passed changes; an ID type must be one the country recognises.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `phone` | no | `None` |
| `email` | no | `None` |
| `id_type` | no | `None` |
| `id_number` | no | `None` |
| `nationality` | no | `None` |

### `kamra.checkin.confirm_billing`

**POST**

The desk confirms who pays (OTA, guest, company, group).

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `payer` | yes |  |
| `note` | no | `None` |

### `kamra.checkin.assign_checkin_room`

**POST**

Keep the assigned room, or put the guest in another free room of
the booked type. Upgrades and downgrades (a different type, maybe a
new price) go through the room move screen (room_move_preview +
move_reservation), which also records who assigned the room.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `room` | no | `None` |

### `kamra.checkin.sign_registration_card`

**POST**

The guest signs the registration card on screen (stored like the
online signature) or on the printed card (on_paper=1).

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `signature` | no | `None` |
| `on_paper` | no | `0` |

### `kamra.checkin.issue_keys`

**POST**

Record the keys handed to the guest, and who handed them. With a
connected lock system the keys are made by it as soon as the guest is
checked in (now, if already in house); with no lock system the desk
encodes the cards at the encoder and notes the card numbers here.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `key_count` | no | `1` |
| `key_cards` | no | `None` |

### `kamra.checkin.log_checkin_requests`

**POST**

Quick requests at check-in become service tickets (one each); a free
note is kept on the step and, if given alone, raised as one ticket.

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `requests` | no | `None` |
| `note` | no | `None` |

### `kamra.checkin.set_room_charges`

**POST** · roles: `Front Desk`, `Night Auditor`, `Finance`, `Hotel Admin`

May the guest charge outlets, laundry and minibar to the room? POS,
laundry and minibar postings check this flag. Changeable later in the
stay by the desk or finance (logged).

| Param | Required | Default |
| --- | --- | --- |
| `reservation` | yes |  |
| `allowed` | no | `1` |
| `reason` | no | `None` |


## Staff & access

### `kamra.staff.staff_roles`

**GET/POST**

The roles a person can hold, and whether the caller may hand each out.

### `kamra.staff.list_staff`

**GET/POST**

Everyone with a Kamra role who can reach this property.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.staff.save_staff`

**POST**

Add a person, or change an existing person's roles, property access
and whether they can sign in.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `email` | yes |  |
| `full_name` | yes |  |
| `roles` | yes |  |
| `properties` | no | `None` |
| `enabled` | no | `1` |
| `send_welcome` | no | `0` |

### `kamra.staff.role_matrix`

**GET/POST**

Per role, the settings pages it may change (admins: all of them).


## Outbound webhooks (subscriptions, delivery log)

> Hotel Admin / System Manager. Events are signed with HMAC-SHA256 - see the Integrations page.

### `kamra.webhooks.webhook_events`

**GET/POST** · roles: `Hotel Admin`

The events a webhook can subscribe to.

### `kamra.webhooks.list_webhooks`

**GET/POST** · roles: `Hotel Admin`

This property's webhook subscriptions (never the secrets).

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |

### `kamra.webhooks.save_webhook`

**POST** · roles: `Hotel Admin`

Create or update a subscription. A new one gets a signing secret,
returned once in `secret` - store it on the receiving side now.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `url` | yes |  |
| `events` | yes |  |
| `label` | no | `None` |
| `active` | no | `1` |
| `name` | no | `None` |

### `kamra.webhooks.rotate_webhook_secret`

**POST** · roles: `Hotel Admin`

Issue a new signing secret (returned once); the old one stops working.

| Param | Required | Default |
| --- | --- | --- |
| `name` | yes |  |
| `property` | no | `None` |

### `kamra.webhooks.delete_webhook`

**POST** · roles: `Hotel Admin`

Remove a subscription and its delivery log.

| Param | Required | Default |
| --- | --- | --- |
| `name` | yes |  |
| `property` | no | `None` |

### `kamra.webhooks.webhook_deliveries`

**GET/POST** · roles: `Hotel Admin`

The delivery log, newest first.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `webhook` | no | `None` |
| `status` | no | `None` |
| `limit` | no | `50` |

### `kamra.webhooks.delivery_detail`

**GET/POST** · roles: `Hotel Admin`

One delivery with the exact payload that was (or will be) sent.

| Param | Required | Default |
| --- | --- | --- |
| `delivery` | yes |  |

### `kamra.webhooks.resend_delivery`

**POST** · roles: `Hotel Admin`

Send a delivery again now - same event id, so the receiver can tell
it is the same event.

| Param | Required | Default |
| --- | --- | --- |
| `delivery` | yes |  |

### `kamra.webhooks.send_test_event`

**POST** · roles: `Hotel Admin`

Send a signed `ping` to one endpoint right now and report the result.

| Param | Required | Default |
| --- | --- | --- |
| `name` | yes |  |
| `property` | no | `None` |


## External POS (room charges from a third-party POS)

> For a POS Integrator service user. ticket_id makes every posting idempotent.

### `kamra.pos_interface.pos_room_lookup`

**GET/POST**

In-house stays matching a room number and/or the guest's last name.
Only checked-in guests, only this property, only what a cashier needs to
confirm the charge: room, guest name, reservation and departure date.
Ask with a room or a last name (2+ letters) - never the whole list.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `room` | no | `None` |
| `last_name` | no | `None` |

### `kamra.pos_interface.pos_post_room_charge`

**POST**

Post one POS ticket to an in-house guest's bill.

`ticket_id` is the idempotency key: the same ticket again returns the
first posting with duplicate=true. Name the stay by room (number or id)
and/or reservation. The billing rules choose the folio; anything with
alcohol (is_alcohol=1) always goes to the guest's own folio, never the
company's. Tax is the hotel's rule for the charge type, not the POS's.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `ticket_id` | yes |  |
| `amount` | yes |  |
| `description` | yes |  |
| `room` | no | `None` |
| `reservation` | no | `None` |
| `charge_type` | no | `'Food & Beverage'` |
| `is_alcohol` | no | `0` |
| `tax_rate` | no | `0` |
| `outlet_name` | no | `None` |


## Public (no auth - booking page, check-in)

> These are allow_guest endpoints: no token needed, rate-limited.

### `kamra.public_api.catalog_index` <Badge type='tip' text='public' />

**GET/POST**

Entry point for /book  -  how many properties, sites, or listings to show.

Several properties live: mode "properties" lists them, and the guest
picks one - /book?property=&lt;slug> (or /stay/&lt;slug>) calls back with
that property's slug and gets its own sites / listings / catalog.

| Param | Required | Default |
| --- | --- | --- |
| `property_slug` | no | `None` |

### `kamra.public_api.resolve_slug` <Badge type='tip' text='public' />

**GET/POST**

Resolve /stay/:slug to a listing or multi-listing site.

| Param | Required | Default |
| --- | --- | --- |
| `slug` | yes |  |

### `kamra.public_api.site_info` <Badge type='tip' text='public' />

**GET/POST**

Public site metadata for the login/boot screen.

demo_mode is true only on the seeded demo site (seed_demo sets the
`kamra_demo_mode` default), so a real install never advertises the
demo login accounts. The running version is public on purpose: it is
what a bug report and the login screen quote.

### `kamra.public_api.default_property` <Badge type='tip' text='public' />

**GET/POST**

Which Property the public booking engine (``/book``) should show.

Each Kamra deploy is single-tenant: one site = one hotel/villa. The
frontend used to hardcode the demo property name, which only worked
on the seeded demo site and broke the booking engine on every other
tenant (``Property &lt;name> not found`` / permission error for Guest).

Picks the Property with booking_engine_enabled=1; if none are flagged
(fresh install) or several are, falls back to the first Property so
the page still renders instead of hanging on a guest permission error.

### `kamra.public_api.showcase` <Badge type='tip' text='public' />

**GET/POST**

Everything the public booking page needs to render.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `listing_slug` | no | `None` |
| `location_slug` | no | `None` |

### `kamra.public_api.search_stay` <Badge type='tip' text='public' />

**GET/POST**

Availability + real quoted price per room type for the stay.

`child_ages` (e.g. [3, 8, 13]) lets each room type's age bands decide who
is free, a child or an adult; without it `children` are all children.
Each row says whether the room type can take the party: `available`, a
`reason` when it cannot, and `needs_confirmation` when the party is above
what it sleeps but within the extra guests it allows by arrangement.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `check_in_date` | yes |  |
| `check_out_date` | yes |  |
| `adults` | no | `2` |
| `children` | no | `0` |
| `listing_slug` | no | `None` |
| `location_slug` | no | `None` |
| `pets` | no | `0` |
| `child_ages` | no | `None` |

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
Read-only  -  the guest sees what things cost, never a folio.

| Param | Required | Default |
| --- | --- | --- |
| `token` | yes |  |

### `kamra.public_api.request_guest_laundry` <Badge type='tip' text='public' />

**POST**

In-house guest asks housekeeping to pick their laundry up. Written on
the guest's behalf by the governed agent  -  the guest never touches pricing
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

Instant mode (default): Confirmed when nothing is due now, else
Pending Payment with a hold window. Request to Book: Requested (no
inventory) until the host approves. A party above what the room sleeps,
within the extra guests it allows, is also Requested: the host confirms
the sleeping arrangement and agrees the price for them.

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
| `idempotency_key` | no | `''` |
| `pets` | no | `0` |
| `child_ages` | no | `None` |
| `marketing_consent` | no | `0` |

### `kamra.public_api.access_info` <Badge type='tip' text='public' />

**GET/POST**

Guest access instructions when gates pass (precheckin token).

| Param | Required | Default |
| --- | --- | --- |
| `token` | yes |  |

### `kamra.public_api.check_voucher` <Badge type='tip' text='public' />

**GET/POST**

Live promo-code feedback on the booking page. Never throws - returns
{ok, message, discount_type, value} so the guest sees a friendly note.

| Param | Required | Default |
| --- | --- | --- |
| `property` | yes |  |
| `code` | yes |  |
| `nights` | no | `1` |

### `kamra.public_api.hosting_enquiry` <Badge type='tip' text='public' />

**POST**

Hosting / implementation enquiry from kamrapms.com. Stored first (a lead is
never lost even without SMTP), then a best-effort email to the team.

Leads are System Manager-only and purged after
``hosting_enquiry_retention_months`` (default 24) unless status is Won.

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
