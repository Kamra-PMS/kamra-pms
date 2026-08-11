# Architecture Decision Records — Short-Term Rental Support (Ewa Reserve)

Status: ADR-001 through ADR-007 **approved** (2026-08-11).
ADR-008 through ADR-014 remain draft.
Ewa Reserve operator decisions deferred; Phase 1A implementation proceeds on
the approved inventory / availability foundation.

---

## ADR-001: Sellable Inventory Unit (SIU)

### Context

Kamra currently models inventory as:

- Property (site, policies, modules)
- Room Type (catalog category, base pricing, amenities)
- Room (physical numbered space)

A Reservation is against a Room Type + optionally a Room. Availability is
computed from the count of physical Rooms per Room Type. This breaks for STR
entire-place listings where there is no numbered room, and it complicates
hybrid properties that can be sold as one whole estate or as individual rooms.

### Decision

Introduce a **Sellable Inventory Unit (SIU)** as the atomic unit of capacity.
An SIU is what can be sold or blocked for a date range. It may be:

1. **Individual unit** — maps 1:1 to a physical Room (existing hotel model).
2. **Whole-place unit** — maps to the entire Property, with an optional
   sentinel physical Room for check-in/ housekeeping / ARI compatibility.
3. **Composite unit** — maps to a set of Rooms that are sold together as a
   bundle (e.g., two cottages as one package).

The SIU is the thing that availability, booking, and ARI reference. The Room
remains the thing that housekeeping, inspection, and access operate on.

### Options considered

| Option | Pros | Cons |
|---|---|---|
| A. New `Sellable Unit` DocType | Clean model, explicit fields, easy to query | Migration, more UI, more API surface |
| B. Extend `Room` with `is_virtual`/`is_whole_property` | Reuses existing code, availability works fast | Overloads Room, leaks hotel semantics, awkward HK/room number requirements |
| C. Infer from `Room Type.room_category = Villa` | No new data model | Already causing false-unavailability, missing capacity guard, no check-in/HK path |

**Recommendation:** Option A — a new `Sellable Unit` DocType — because it makes
the model explicit, gives us the right hooks for hybrid competition, and does
not overload the hotel Room abstraction. Option B is acceptable only as a
tactical bridge with strict documentation.

### Core SIU fields

- `property` (link to Property)
- `unit_name` (internal, e.g., "Ewa Villa")
- `is_active`
- `unit_kind`: `individual` | `whole_property` | `composite`
- `room_type` (link to Room Type; may also be the listing)
- `physical_rooms` (Child Table of Room links; optional for whole_property)
- `max_occupants` / `base_occupancy`
- `competition_group` (for whole_property / hybrid rules; see ADR-004)
- `turnover_profile` (link to Turnover Profile: clean duration, inspection SLA, buffer)
- `external_ids` (channel listing IDs, JSON)
- `is_auto_assignable` (true for hotel rooms, false for whole_property until staff ready)

### Consequences

- `_available_rooms_raw`, `availability_calendar`, `ari_snapshot`, CRS search,
  and MCP queries all read SIU availability.
- Room-level overlap remains valid for individual units.
- Whole-property and composite units use competition-group rules.
- `Room Type.room_category = Villa` becomes a **presentation/operational hint**
  only, not the inventory engine.

### Questions to resolve

- Do we create a new DocType or extend Room for the MVP?
- For whole-property, do we require a sentinel Room, or allow no physical Room?
  (If no Room, we need a parallel housekeeping and access path.)

---

## ADR-002: Listing → Room Type → SIU → Room mapping

### Context

Guests see a **listing**; staff operate on physical rooms; the system books an
SIU. The current `Room Type` conflates listing and sellable category.

### Decision

| Layer | Responsibility | Maps to |
|---|---|---|
| Listing | Guest-facing catalog: title, description, hero image, gallery, amenities, channel IDs, SEO slug | New `Listing` or extended Room Type |
| Room Type | Internal operational category: base price, occupancy defaults, tax, meal-plan relationship | `Room Type` |
| Sellable Unit | Atomic capacity that can be sold/blocked | New `Sellable Unit` |
| Room | Physical space for HK, inspection, access | `Room` |

For MVP, we keep **Room Type as the listing placeholder** to avoid creating
another DocType. The mapping is:

- Room Type = guest-visible listing + operational category.
- SIU = one or more sellable units per Room Type.
- Physical Room = optional backing for SIU operations.

Later, a separate `Listing` DocType can be introduced if multi-channel content
or translations become important.

### Consequences

- Public booking engine displays Room Type as the listing card.
- Booking is against an SIU derived from Room Type.
- One Room Type can have multiple SIUs (multi-unit hotel) or one SIU
  (whole-property STR).
- Channel managers map to a Room Type + SIU, not just Room Type.

### Questions to resolve

- Does Ewa need one listing per SIU (e.g., each cottage marketed separately) or
  one listing per property?
- Does a separate Listing DocType make sense for v2, or should Room Type carry
  all guest-facing content?

---

## ADR-003: Availability Service — single source of truth

### Context

Availability is currently calculated in multiple places:

- `api.py`: `_available_rooms_raw`, `availability_calendar`, `available_rooms`
- `public_api.py`: `search_stay` uses `_available_rooms_raw`
- `channel_manager.py`: `ari_snapshot` uses `_available_rooms_raw`
- `reservation.py`: `validate_type_capacity` and `validate_villa_lockout` enforce
  rules at save time only

These paths can disagree, especially for hybrid inventory and unassigned Villa
bookings.

### Decision

Create a single Python service `kamra.siu.availability` with the
signature:

```python
def availability(
    property: str,
    siu: str | None,
    room_type: str | None,
    date_range: tuple[str, str],
    *,
    include_reasons: bool = False,
) -> dict:
```

Return shape:

```python
{
  "siu": "SIU-001",
  "sellable_per_night": [1, 1, 0, ...],  # or integer for single unit
  "blocked": [
    {"date": "2026-08-15", "reason": "reservation", "reference": "RES-123"},
    {"date": "2026-08-15", "reason": "turnover_buffer", "reference": "HK-001"},
    {"date": "2026-08-15", "reason": "owner_block", "reference": "RB-004"},
  ]
}
```

### Consumers

All of the following must use the service:

- Direct public booking search
- Desk availability / tape chart / calendar
- CRS search
- MCP tools
- Channel ARI push and webhook booking validation
- Quote/pricing engine (for min-stay, CTA, arrival/departure restrictions)

### Rules embedded

1. Reservations in live status block nights.
2. Owner / maintenance / deep-clean blocks remove sellable nights.
3. Turnover buffer removes the night after checkout until the unit is marked
   ready (or buffer duration expires).
4. Competition-group rules reduce sellable counts for whole-property vs unit
   overlap.
5. Minimum stay, arrival/departure restrictions, and max booking horizon are
   **policy filters** applied on top of availability, not part of the count.

### Consequences

- `Reservation.validate()` becomes a thin enforcer of the same rules, not the
  primary source.
- ARI and internal search will agree by construction.
- Blocking reasons enable ops dashboards and clear failure diagnostics.
- Caching strategy can be centralized.

### Performance notes

- For small properties, a per-night query is acceptable.
- For large portfolios, consider materialized availability tables refreshed by
  Frappe document events or a periodic job.
- ARI calls remain cached/refresh-driven, not on every search.

---

## ADR-004: Hybrid competition rules

### Context

A hybrid property can sell the same physical inventory in two ways: as an
entire property (e.g., "Ewa Villa") or as individual rooms/units. These sellable
units must not be double-booked.

### Decision

Model competition through a **competition group** on the SIU.

- All SIUs in the same competition group compete for the same underlying
  inventory.
- A booking for any SIU in the group reduces availability for all SIUs in the
  group for the overlapping nights.
- When a whole-property SIU is booked, its sellable count for those nights
  becomes 0 and all individual SIUs in the group become blocked by the
  `reservation` reason.
- When an individual SIU is booked, the whole-property SIU remains sellable only
  if all other individual SIUs are still free; otherwise it becomes 0/blocked.

For pure entire-place or pure multi-unit properties, the competition group may
contain only one SIU (or one SIU per unit) with no competition effects.

### Algorithm

For a competition group on a given date:

1. Count total individual SIUs in group: `N`.
2. Let `i` = number of individual SIUs booked in live status.
3. Let `w` = 1 if whole-property SIU is booked, else 0.
4. Whole-property sellable = `1 if i == 0 and w == 0 else 0`.
5. Each individual SIU sellable = `1 if w == 0 and that SIU is not individually booked else 0`.

### Consequences

- The existing `validate_villa_lockout()` becomes a defense-in-depth check that
  mirrors the availability rule.
- ARI push must reflect the same math, so channel availability is correct for
  hybrid properties.
- Staff cannot silently overbook a whole-property booking by also selling
  individual rooms.

### Questions to resolve

- For Ewa, does a whole-property booking block **every** individual unit, or
  only a defined subset? (e.g., all bedrooms but not the manager's quarters)
- If there are multiple whole-property listings on the same estate, do they
  compete with each other too?

---

## ADR-005: property_kind boundary

### Context

The plan proposes adding a `Property.property_kind` field (Hotel vs Short Term
Rental) to drive wizard defaults and module selection. It must not become a
silent forking mechanism for business logic.

### Decision

`property_kind` is a **catalog / setup / presentation preset**. It may influence:

- Default enabled modules
- Default terminology (hotel vs listing/entire place/unit)
- Default overbooking percentage (`0` for STR)
- Default day-use visibility (`false` for STR)
- Default meal-plan step visibility
- Default booking mode (instant vs request-to-book)
- Default policy copy

It must **not** influence:

- Pricing rules or tax calculations
- Reservation state machine
- Availability engine behavior
- Deposit lifecycle rules
- Channel sync mechanics
- Whether a whole-property vs unit booking is allowed

Those rules are driven by explicit SIU, competition group, and policy settings.

### Consequences

- Existing properties with `property_kind` unset or `Hotel` continue unchanged.
- A Hotel property can later be configured to sell a Villa as an entire-place
  SIU without changing its `property_kind`.
- An STR property can later enable F&B/events modules if the operator wants.
- The codebase remains one product, not two.

### Questions to resolve

- Should `property_kind` include `Homestay / B&B` and `Serviced Apartment` in v1?
- Is it acceptable to default all unset properties to `Hotel`?

---

## ADR-006: Reservation state machine

### Context

Current statuses: `Waitlist | Confirmed | Checked In | Checked Out | Cancelled | No Show`.
STR workflows require inquiry, quote, request-to-book, temporary hold, and
pending payment states that are not present today.

### Decision

Extend the Reservation status set with the following states, at minimum for STR:

- `Inquiry` — guest asked a question; no inventory held.
- `Quoted` — quote generated; no inventory held (quote expires separately).
- `Requested` — guest requested to book; host approval pending; **no inventory held** unless configured.
- `Held` — temporary hold (e.g., payment pending); inventory held; **expires**.
- `Pending Payment` — approved but payment not yet settled; inventory held.
- `Confirmed` — live booking; inventory held; payment (or payment policy) settled.
- `Checked In` / `Checked Out` / `Cancelled` / `No Show` — unchanged.

For hotel v1, only `Confirmed` and above may be used. The new states can be
introduced incrementally as the STR booking engine and state transitions are
implemented.

### Transition rules (to be refined)

| From | To | Actor | Inventory | Payment | Notes |
|---|---|---|---|---|---|
| Inquiry | Quoted | System | none | none | Quote expires independently |
| Quoted | Requested | Guest | none | none | Awaiting host approval |
| Requested | Held | Host approves | held | deposit required | Hold expiry set |
| Requested | Rejected | Host rejects | none | none | Notify guest |
| Held | Pending Payment | Guest | held | advance required | Payment link / authorization |
| Held | Cancelled | System timeout | released | none | Hold expired |
| Pending Payment | Confirmed | Payment settles | held | recorded | OTA status may move directly to Confirmed |
| Confirmed | Checked In | Staff | held | — | Check-in rules apply |
| Confirmed | Cancelled | Guest/Host | released | per policy | Refund/credit note |
| Confirmed | No Show | System | released | per policy | No-show charge posted |

### Consequences

- OTA webhooks must map their statuses to this state machine; conflicts need
  explicit rules (e.g., OTA says Confirmed but local host has not approved).
- Inventory holds require an expiry mechanism to avoid phantom inventory.
- Public booking engine must not confirm a booking in request-to-book mode.
- MCP tools must be updated to expose the correct state transitions.

### Questions to resolve

- Is Ewa launch instant-book or request-to-book?
- If request-to-book, what is the default approval timeout and hold policy?
- Do we implement full state machine in v1, or simplify to `Confirmed` + `Held`
  for launch?

---

## ADR-007: Concurrency and booking idempotency

### Context

The current booking path uses `FOR UPDATE` on the assigned Room row for
room-level double-booking protection. Type-level capacity (`validate_type_capacity`)
does not serialize competing inserts, and unassigned whole-property bookings
rely on the `validate_villa_lockout()` check at save time, which is also
unsynchronized with search/ARI.

### Decision

1. **Use the SIU as the concurrency lock target.** Every booking command must
   acquire a row-level lock on the relevant SIU(s) before reading availability
   and inserting the Reservation.
2. **For competition-group bookings, lock the group.** A whole-property booking
   locks the whole-property SIU plus all individual SIUs in the group; an
   individual booking locks the individual SIU and the whole-property SIU.
3. **Booking writes are idempotent.** Public and OTA booking endpoints accept
   an `idempotency_key` (caller-supplied or derived from OTA reservation ID).
   Duplicate keys with the same payload return the existing Reservation without
   creating a second one.
4. **OTA webhook deduplication continues using `ota_ref`.** Extend it to include
   channel + reservation ID + modification timestamp.
5. **Holds are first-class reservations with a status and expiry.** They consume
   inventory and release it on expiry via a scheduled job.

### Consequences

- The public booking API must be updated to accept and store `idempotency_key`.
- The OTA ingress path must lock SIUs, not just Room rows.
- Competition-group locking must be ordered to avoid deadlocks (e.g., always
  lock whole-property SIU before individual SIUs).
- ARI push must be eventually consistent with the same locked transaction, but
  not required inside the booking transaction.

### Questions to resolve

- Is Frappe's `frappe.db.sql(..., for_update=True)` sufficient for SIU locking,
  or do we need a Frappe-level lock helper with retry logic?
- What is the idempotency key TTL and deduplication window?

---

## ADR-008: Quote and charge ledger

### Context

Pricing is currently represented as a few amount fields on Reservation:
`amount_before_tax`, `tax_amount`, `amount_after_tax`, `discount_amount`. The
folio has charge types but no `Cleaning Fee`, `Security Deposit`, or
`Length-of-Stay Discount` types. This is too coarse for STR economics.

### Decision

Introduce a typed **Quote component model** that is stored with the Reservation
as a snapshot. Every booking has a `quote_snapshot` (JSON or child table) with:

- `line_items`: list of components, each with:
  - `component`: `accommodation`, `cleaning_fee`, `extra_guest_fee`, `pet_fee`,
    `early_checkin`, `late_checkout`, `los_adjustment`, `promotion`, `cancellation_fee`,
    `damage_charge`, `other`
  - `description`
  - `amount`
  - `tax_amount` / `tax_rate` (where applicable)
  - `is_tax_inclusive`
  - `nights_applied`
- `totals`: `subtotal`, `tax`, `total`, `discount`, `deposit_required`
- `currency`
- `quote_version` and `quoted_at` timestamp
- `idempotency_key` of the booking command

Folio charges and payments are generated from the quote snapshot on booking,
modification, cancellation, and close-out. The snapshot is immutable: a
modification creates a new quote version with a delta.

### Consequences

- `quote()` in `pricing.py` returns a structured quote, not just totals.
- The Reservation stores the quote snapshot; the folio remains the ledger.
- Invoice generation and accounting export use the components.
- Tax treatment can be configured per component and per country pack.

### Questions to resolve

- Which components are taxable for Ewa? (Needs operator/CA verification.)
- Should the quote snapshot be a Child Table or a JSON field?
- How do promotions and LOS discounts stack with seasons and demand hurdles?

---

## ADR-009: Deposit liability

### Context

Security deposits are currently handled as a payment kind with manual tracking.
There is no lifecycle: required → collected/held → released/withheld.

### Decision

Model the security deposit as a **stay-level liability** with the following
states:

1. **Required** — at booking/confirmation, based on Property policy.
2. **Waived** — staff may waive with reason.
3. **Collected** — actual payment or authorization captured.
4. **Held** — held during stay.
5. **Withheld** — partial or full retain for damage/cancellation/late checkout.
6. **Refunded** — balance returned to guest.

Each state change is an audit event with amount, reason, evidence reference,
and actor. The banquet `close_out()` pattern is the reference implementation.

A new `Security Deposit` child table on Reservation (or a dedicated DocType)
tracks:

- `required_amount`
- `method`: `authorization`, `payment`, `cash`, `waiver`
- `status`
- `transactions` (authorizations, captures, releases, refunds)
- `withhold_reasons` and `evidence`
- `refund_reference`

### Consequences

- Deposits never appear as accommodation revenue.
- Refunds, withholds and damage claims are traceable.
- Owner statements can distinguish net revenue from deposit movements.
- Wallet balance / folio must reconcile to the deposit liability table.

### Questions to resolve

- Is the deposit an authorization hold or a collected payment? (Gateway capability.)
- Who approves partial withholds and what evidence is required?
- Does Ewa want damage close-out at check-out or after inspection?

---

## ADR-010: Turnover readiness

### Context

Hotel checkout creates a `Checkout Clean` Housekeeping Task only when a Room is
assigned. Whole-property STR stays may not have a Room, and the full turnover
is clean + inspect + ready, not just a checkout clean.

### Decision

Define a **Turnover Profile** (configurable per SIU or Room Type):

- `clean_duration` (e.g., 2 hours)
- `inspect_duration` (e.g., 30 minutes)
- `buffer_after_ready` (e.g., 0 or 30 minutes)
- `same_day_turn_allowed` (default false for STR unless proven operationally)
- `requires_inspection` (true for STR, false for some hotel rooms)
- `ready_marked_by` role (e.g., Housekeeping Inspector)

Checkout creates the following sequence for the SIU's backing Rooms or
whole-property SIU:

1. `Departure Clean` task assigned to cleaner.
2. Cleaner completes; `Inspection` task created if required.
3. Inspector completes; unit is `Ready` or `Not Ready` (with defects/evidence).
4. If not ready, unit is blocked and re-clean is triggered.
5. Once ready, the turnover buffer clears and the unit is sellable for the next
   arrival.

For SIUs with no physical Room, the SIU itself carries the turnover state and
tasks are property-scoped.

### Consequences

- `availability()` blocks nights by `turnover_buffer` until ready.
- HkApp needs a flow for whole-property / no-room turnovers.
- Ready status is the gate for access code release.
- Late or incomplete turnovers trigger alerts.

### Questions to resolve

- Does Ewa allow same-day turns? If yes, what SLA and staffing supports it?
- Who marks a unit ready — cleaner, inspector, or property manager?
- What happens if a unit is not ready and the next guest arrives?

---

## ADR-011: Channel sync and source of truth

### Context

Current channel integration is Channex / STAAH / AioSell via ARI push and
webhook ingestion. There is no native iCal, no outbox, and no reconciliation.
Hybrid ARI is especially risky because availability can be wrong before a booking
arrives.

### Decision

For each enabled channel connection, define:

- **Source of truth**: rates, availability, content, cancellation authority.
- **External identifiers**: property, listing, SIU, rate plan.
- **Sync mode**: push only, pull only, or bidirectional.
- **Failure policy**: retry, alert, manual block, or pause.

Implement an **ARI outbox** (a simple Frappe DocType or queue table):

- One row per (connection, SIU, date) update event.
- Retries with exponential backoff.
- Failure state visible in Revenue/Channels UI.
- Reconciliation job compares internal availability to last successful push.

For iCal (if supported in v1 or v2):

- Treat it as **calendar blocks only**, not authoritative for guest/payment data.
- Poll interval documented; acknowledge polling lag creates overbooking risk.
- Export an iCal feed for hosts who want to block personal calendars.

### Consequences

- Hybrid properties cannot enable live ARI until parity tests pass.
- Failed ARI pushes are visible and recoverable.
- Manual channel blocks can be applied during outages.
- OTA inbound bookings are validated against the Availability Service.

### Questions to resolve

- Which channels are live at launch for Ewa?
- Is the launch direct-only, channel-manager, or iCal?
- What is the acceptable sync delay for each channel?

---

## ADR-012: Access security

### Context

STRs commonly use self check-in. Access information (key codes, smart-lock
tokens, lockbox combinations) must be released securely and only when conditions
are met.

### Decision

Store access instructions in a dedicated child table on Reservation, not in the
generic `Stay Instruction` field. Model:

- `access_type`: `staffed`, `lockbox`, `smart_lock`, `manual_code`, `instructions_only`
- `access_payload`: encrypted or role-scoped; for smart locks, the rotating token
- `release_conditions`: `confirmed`, `payment_received`, `deposit_collected`, `kyc_complete`, `unit_ready`, `check_in_time`
- `release_at`: datetime or status trigger
- `revoke_at`: checkout or early departure
- `emergency_override`: role-based temporary reveal with audit
- `last_viewed_by` and `last_viewed_at` for audit

Access is never released until **all configured conditions** pass. Codes are
rotated or revoked on checkout. Permanent codes are never stored in message
templates.

### Consequences

- Access release is a launch gate, not a template feature.
- Sensitive data is scoped and audited.
- Staff can override with reason in emergencies.
- Integration with smart-lock providers will be adapter-based behind this model.

### Questions to resolve

- Is Ewa launch instructions-only or a specific smart lock?
- What is the minimum KYC/ID data before access is released?
- Who is on-call if the guest cannot access the unit?

---

## ADR-013: Migration and compatibility

### Context

Adding `property_kind` and SIU fields requires a migration path. Existing
properties must remain Hotel-compatible and unchanged. The project currently
has `patches.txt` and one-off bootstrap scripts, but no documented hotel→STR
conversion path.

### Decision

1. Add `property_kind` via a Frappe patch that defaults all existing properties
   to `Hotel`.
2. Add SIU creation as a one-time backfill for existing Room Types / Rooms:
   - Each existing Room becomes an `individual` SIU.
   - Each existing Room Type with `room_category = Villa` becomes a
     `whole_property` SIU in its own competition group, optionally linked to a
     sentinel Room if one exists.
3. New `setup_property()` writes SIUs and competition groups atomically.
4. Keep the old `_available_rooms_raw` path as a fallback behind a feature flag
   until the Availability Service is fully validated.
5. Provide a rollback script that reverts SIU-related changes and restores the
   original Room-centric model for a property if needed.

### Consequences

- Existing Hotel properties continue without action.
- Conversion to STR is possible but tested manually before production.
- The feature flag limits blast radius during rollout.

### Questions to resolve

- Is converting an existing hotel Property to STR in v1 scope, or only
  greenfield setup?
- Should the backfill run automatically on migrate or be opt-in?

---

## ADR-014: Public API and MCP contracts

### Context

MCP tools and public API responses are currently hotel-oriented: meal plans,
room types, and Room-based availability. STR needs SIU, listing, deposit,
cleaning fee, and state machine fields.

### Decision

Use **additive versioning**:

- Keep existing API responses unchanged for backward compatibility.
- Add `siu` and `siu_kind` to booking/quote responses.
- Add `cleaning_fee`, `deposit_required`, and `line_items` to quote responses.
- Add `property_kind` and `request_to_book` to public showcase/booking.
- MCP tools get new optional parameters; old calls remain valid.
- Update the MCP documentation and eval harness with STR scenarios.

All API changes must be covered by contract tests before release.

### Consequences

- Existing integrations and MCP clients are not broken.
- STR booking engine uses the new fields.
- Hotel clients ignore the new STR fields.
- Versioning strategy is additive until a breaking v2 is justified.

---

## Next steps after these ADRs are approved

1. Resolve operator decisions in `PLAN.md` (topology, channels, book mode,
   deposit/tax/access).
2. Get ADR-001 through ADR-007 approved by the relevant stakeholders.
3. Resolve the per-ADR questions that require operator input.
4. Begin Phase 1A: implement SIU DocType and Availability Service.
5. Begin Phase 1B: implement `property_kind`, wizard branching, and atomic
   `setup_property()` defaults.
6. Add invariant tests and availability parity tests before accepting live
   bookings.
