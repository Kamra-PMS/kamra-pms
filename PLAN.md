# Ewa Reserve: short-term-rental setup plan

## Goal

Support Ewa Reserve as a short-term rental (STR), vacation rental, or
Airbnb-style property without creating a separate product or forking hotel
reservation logic. A property kind should choose sensible defaults, workflow
copy, and enabled modules; the existing Property → Room Type → Room →
Reservation model remains the source of truth.

This is a planning document only. Do not implement this work until the
decisions in **Open decisions** are resolved.

## Current foundation

Kamra already supports several relevant primitives:

- `Room Type.room_category` supports `Villa`, `Private`, and `Shared`.
- `Reservation.validate_villa_lockout()` blocks overlapping whole-property
  and individual-room stays.
- Property fields already include check-in/out times, minimum nights,
  security-deposit amount, payment mode, cancellation settings, house rules,
  pets policy, and child policy.
- Weekend / weekday season pricing is supported through
  `Season.days_of_week`.
- Module gating already hides unused product areas per property:
  `front-desk`, `housekeeping`, `operations`, `fnb`, `events`, `revenue`,
  `finance`, `booking-engine`, and `admin`.
- Checkout currently creates a `Checkout Clean` housekeeping task when a
  room is assigned.
- The public booking engine, pre-arrival check-in, guest policies, and
  channel-manager integrations already exist.

## Core design

### One property model, not a second STR product

Add `Property.property_kind` with:

- `Hotel` — default for compatibility with every existing property.
- `Short Term Rental` — the Ewa Reserve path.

Potential future presets (`Homestay / B&B`, `Serviced apartment`) should be
additional values of the same field, not separate doctypes.

`property_kind` is a setup and presentation preset. Rules that affect money
or inventory remain explicit property, room-type, and reservation settings.
Avoid spreading `if property_kind == ...` through pricing and reservation
logic.

### Setup wizard: new first step

Add **Property type** before the current Property step:

| Choice | Intent |
|---|---|
| Hotel | Multiple sellable rooms, optional F&B and events |
| Vacation rental / short-term rental | Entire home, villa, apartment, or a small number of rental units |

The selection pre-populates the remaining wizard. It must remain editable so
operators can override a default without restarting.

## Wizard flows

### Hotel (current behaviour, cleaned up)

1. Property details
2. Room types
3. Physical room numbers
4. Meal plans
5. Review
6. Optional historical-booking import

Defaults:

- `property_kind = Hotel`
- Minimum nights: `1`
- Modules: all standard modules enabled
- Existing room and meal-plan defaults remain intact

### Short-term rental / vacation rental

1. **Property type** — select STR
2. **Property details and stay policy**
   - property name, address, timezone, contact details
   - check-in/check-out time
   - minimum nights
   - payment policy
   - security-deposit policy
   - cancellation policy preset
3. **Listings / spaces**
   - entire place, unit, private room, or shared accommodation
   - listing name, max occupancy, nightly price, extra-guest price
   - weekday/weekend pricing
   - photos, amenities, house rules
4. **Inventory topology**
   - one whole-property listing, or
   - multiple independently sellable units / rooms
5. **Turnover and guest access**
   - turnover-clean duration / buffer
   - cleaning fee
   - self-check-in and access-instruction settings
6. **Review and publish**
7. **Optional import**
   - initially generic CSV; later Airbnb / VRBO / Guesty presets

For a pure STR, skip meal-plan configuration instead of creating meaningless
EP/CP/MAP records.

### Module presets

| Module | Hotel | STR |
|---|---:|---:|
| Front desk | on | on |
| Housekeeping | on | on |
| Operations | on | off by default |
| F&B | on | off |
| Events / banquets | on | off |
| Revenue | on | on |
| Finance | on | on |
| Booking engine | on | on |
| Admin | on | on (mandatory) |

The existing module gate can enforce this presentation without new route
gates. Administrators must still be able to enable a module later.

## Workflow changes

### 1. Inventory and availability

The highest-risk workflow is whole-property availability.

For Ewa Reserve, decide one of these topologies:

1. **One entire-place listing only** — one sellable unit; the reservation must
   have a concrete inventory record so availability, check-in, housekeeping,
   and channel ARI all agree.
2. **Individual units only** — one Property with multiple Rooms, each sold
   separately.
3. **Hybrid** — entire-property booking competes with individual units. This
   uses the existing Villa lockout, but requires availability and OTA ARI to
   subtract or block the competing inventory in both directions.
4. **Portfolio** — each independently operated home is a separate Property;
   use the existing CRS / multi-property features.

The wizard must make this topology explicit. `Villa` should not silently mean
"no physical room": current availability and check-in workflows are room
oriented.

### 2. Reservation rules

- Enforce `Property.minimum_nights` in both desk booking and public booking.
- Apply cancellation and advance-payment policies consistently in direct,
  desk, imported, and OTA reservations.
- For STR, disable or hide day-use booking unless explicitly enabled.
- Continue using the Villa lockout as the reservation-level integrity guard;
  do not rely on UI filtering alone.

### 3. Pricing and folios

STR quote breakdown should support:

- nightly rate by date
- extra-guest charges (already supported)
- one-time cleaning fee
- optional weekly / monthly discounts
- refundable security deposit, separate from stay revenue
- tax treatment for each charge

Cleaning fees must be a per-stay folio line, not multiplied per night.
Deposits need a stateful lifecycle: required → collected / waived → held →
partially withheld or refunded, including a reason and audit trail.

### 4. Housekeeping and turnover

Hotel room cleaning and STR turnover are related but not identical:

- Create a property- or unit-level turnover task even for an entire-place
  booking that has no guest-room assignment.
- Support a clean / inspect / ready sequence.
- Enforce an optional turnover buffer that removes inventory from sale until
  the task is complete or the buffer expires.
- Surface task ownership and readiness before the next arrival.

### 5. Guest journey

STR booking and arrival should emphasize:

- entire-place vs private-room wording in search and confirmation
- guests, occupancy, and house rules before payment
- deposit and cleaning-fee disclosure before checkout
- arrival window, parking / gate guidance, Wi-Fi, and emergency contact
- manual or keyless entry instructions released at the configured point

The current pre-arrival flow is a useful base, but access-code / smart-lock
integration and timing need a separate design.

### 6. Booking engine and channels

The public booking engine should:

- render STR terminology (`Listing`, `Unit`, `Entire place`) where appropriate
- hide meal plans when none are enabled
- expose property policies, deposit, min-stay, cleaning fee, and room
  category in search and quote responses
- make house rules prominent before booking

For hybrid inventory, ARI channel sync must publish availability that respects
Villa-versus-room lockout. Do not enable live OTA inventory for a hybrid
property until this is covered. A temporary manual channel block procedure is
acceptable only during controlled onboarding.

### 7. Reporting and finance

Keep existing occupancy, ADR, RevPAR, and folio reporting. Add later:

- cleaning-fee and deposit reconciliation
- platform commission / payout reconciliation
- owner statements and revenue share for managed units
- STR-specific operational report: arrivals, departures, cleaning readiness,
  blocked nights, and upcoming access handoffs

## Existing-code impacts

| Area | Expected work |
|---|---|
| `Property` DocType + schema patches | Add `property_kind`; add any explicitly approved STR policy fields |
| `frontend/src/screens/Setup.tsx` | Add property-kind chooser, STR branching, presets, and review |
| `kamra.api.setup_property()` | Atomically persist the chosen kind, inventory topology, defaults, and enabled modules |
| `Reservation` validation | Enforce minimum stay; preserve the existing Villa lockout |
| `kamra/pricing.py` and folio logic | Add per-stay cleaning fees, LOS adjustments, and deposit lifecycle only after the data model is agreed |
| Public API and `PublicBooking.tsx` | Return and render STR-specific listing / policy / pricing information |
| Housekeeping | Create whole-property turnover tasks and optional readiness buffer |
| Channel manager | Correct hybrid ARI availability before live OTA sync |
| Migration import | Add Airbnb / VRBO / Guesty mapping only after the internal model is complete |
| App navigation | Reuse `enabled_modules`; add terminology helper only where STR wording is shown |

## Gaps found during review

These gaps materially change the safe implementation order:

1. **No Ewa Reserve inventory topology is defined.** The correct model differs
   for a single rentable estate, separate villas, and a hybrid estate with
   both individual rooms and entire-place bookings.
2. **Villa availability is incomplete.** Current availability counts physical
   Room records per Room Type. A Villa without a corresponding inventory room
   appears unavailable; a placeholder-room workaround also needs explicit
   check-in and housekeeping semantics.
3. **Villa capacity is incomplete.** Room-type capacity validation returns
   early when the room type has no physical rooms, leaving an unrepresented
   entire-place listing without a capacity guard.
4. **Minimum nights is configured but not enforced.** The field is collected
   in setup but must be applied in all booking entry points.
5. **Security deposit is configured but not automated.** Existing payment and
   refund primitives are manual; there is no stay-level hold, settlement, or
   damage-withholding workflow.
6. **Hybrid OTA availability can overbook.** The reservation validator blocks
   a conflicting booking after it arrives, but outbound ARI does not yet
   represent the competing Villa and individual-room inventory.
7. **Whole-property checkout does not create a turnover task without an
   assigned Room.**
8. **STR economics are not fully modelled.** No cleaning fee, length-of-stay
   discount, platform payout, or platform commission reconciliation.
9. **Guest access is not modelled.** There are pre-arrival and WhatsApp
   primitives, but not secure key / code release or smart-lock integrations.
10. **The STR import and listing model are hotel-first.** Current migration
    presets target PMS CSVs rather than Airbnb / VRBO / Guesty exports, and
    listing content is mostly property-level.
11. **Upgrade path needs explicit patches.** New fields must use the project
    patch / migration path; one-off bootstrap scripts are not a sufficient
    upgrade strategy for existing installs.

## Second-pass review — additional gaps

A second full review against the codebase found more missing or
under-specified items. Treat these as part of the plan, not optional notes.

### Must resolve before / during Phase 1

12. **India STR compliance beyond GST invoices.** GST invoicing already exists
    via the localization pack. Still missing: tax treatment of cleaning fees
    and deposits, city short-stay / police registration expectations, tourist
    or occupancy tax if applicable, and any trade-license fields operators
    need to store.
13. **Guest identity / KYC rules for STR.** Guest ID fields and pre-arrival /
    registration-card flows exist, but the plan does not define when ID is
    required, how foreign guests are handled, or whether Form C–style
    reporting is in scope.
14. **Calendar sync is not the same as channel manager.** Current
    integrations are Channex / STAAH / AioSell ARI. There is no native iCal
    import/export. Launch must choose: direct-only, channel manager
    (Airbnb via Channex etc.), and/or iCal — do not assume “turn on channel
    manager = Airbnb done.”
15. **Instant book vs request-to-book.** Public booking currently confirms
    under payment modes. Many STRs need a host-approval / inquiry state
    before Confirmed. No Inquiry / Request status exists today.
16. **Overbooking and waitlist defaults for STR.** Hotel overbooking
    (`overbooking_pct`) and Waitlist exist. STR should default overbooking
    to `0`; decide whether waitlist applies to entire-place listings.
17. **Hotel → STR conversion path.** Plan covers new installs and later
    Airbnb CSV import, but not converting an existing hotel Property
    (modules, meal plans, Villa inventory, copy, overbooking defaults).
18. **Hotel compatibility / rollback matrix.** Defaulting `property_kind` to
    Hotel is necessary but not sufficient. Explicitly protect: empty
    `enabled_modules` still meaning “all modules,” hotel reports/MCP/Setup/
    demo/marketplace copy, and no silent behaviour change for existing
    properties.

### Should cover in Phase 2

19. **Roles and staffing model for STR hosts.** Module toggles hide apps;
    they do not rename or remap `Hotel Admin` / `Front Desk` /
    `Housekeeping`. Need host / co-host / cleaner / owner mapping if Ewa
    does not share a hotel desk team.
20. **Owner / personal-use blocks.** `Room Block` already has Owner / House
    Use reasons. Wire them into the STR ops story (host calendar blocks),
    not only a later “blocked nights” report.
21. **Damage claims beyond deposit refunds.** Deposit lifecycle is planned;
    banquet has a damage close-out pattern. Stay-side damage inspection,
    partial withhold reasons, and any insurance / host-protection workflow
    are unspecified.
22. **LOS / weekly / monthly pricing rule shape.** Plan mentions discounts;
    code has seasons and demand hurdles but no LOS rules. Define stacking
    vs seasons/hurdles and whether channels receive LOS restrictions.
23. **MCP / AI agent tool surface.** Setup, quote, and booking tools are
    hotel/meal-plan oriented. STR fields (cleaning fee, deposit, turnover,
    access instructions, property kind) must update MCP docs and evals.
24. **Hk phone app for turnover.** Housekeeping mobile UX is room-number
    centric. Entire-place / no-guest-room / inspect → ready / buffer needs
    an explicit HkApp design.
25. **Terminology across all surfaces.** Booking-engine labels alone are not
    enough. Desk, tape chart, reports, WhatsApp, registration card, MCP
    descriptions, and i18n still say hotel/room/front desk.
26. **Multi-unit STR cart / group booking.** Hotel Group Booking exists.
    “Book three cottages in one stay” for STR is undesigned.
27. **Multi-currency / international guests.** Property currency is single
    (typically INR). Passport / remittance / display-currency needs are
    unscoped if Ewa hosts international guests.
28. **Demo seed and marketplace implications.** Seed and marketplace listing
    remain hotel-first. An STR demo property and marketplace wording need a
    decision so Ewa-like setups are testable and publishable.
29. **Eval harness coverage.** Phase 1 mentions regression tests; the main
    eval harness is hotel-centric. Add entire-place, hybrid, min-stay,
    deposit, cleaning-fee, and STR setup cases.

### Later (keep out of Phase 1)

30. **In-app reviews / reputation.** Only outbound Google / Tripadvisor
    URLs exist. Airbnb review sync and host–guest reputation are later.
31. **Smart-lock vendor integration.** Keep deferred until the launch choice
    is “instructions only” vs a named lock provider.
32. **Platform commission / owner statements / revenue share.** Already
    Phase 3 — leave there.

### Corrections to earlier plan wording

- Guest occupancy capacity can still run when a Villa has no Rooms; the real
  gap is inventory representation and type-capacity based on physical room
  count, not “no occupancy checks at all.”
- Security-deposit *payment kinds* and pending-refund listing already exist;
  what is missing is the hold → settle / withhold lifecycle, not every
  folio primitive.
- “Channel manager exists” does not mean Airbnb/iCal are done.
- GST invoicing largely exists; the open tax work is fee treatment and local
  STR compliance, not “whether invoices exist.”

## Architecture-level review

### Architectural verdict

The product direction remains correct: one PMS, with STR as a preset rather
than a fork. However, the current `Property → Room Type → Room` model treats
the physical Room as the sellable atom in availability, check-in,
housekeeping, and channel ARI. A wizard cannot safely paper over that
assumption.

`property_kind` must stay a **catalog / presentation preset**. It may set
module defaults, terminology, overbooking defaults, and initial policies. It
must not carry inventory topology, pricing logic, or reservation-state
semantics.

Before building the wizard, Kamra needs explicit answers for:

- what is marketed as a listing
- what is independently sellable
- what physical space operations clean and inspect
- which sellable units compete for the same underlying inventory
- which service is the sole authority for availability

### Target domain model

| Concept | Responsibility | Current approximation |
|---|---|---|
| Property | Legal / operational site, locale, policies, modules | `Property` |
| Listing | Guest-facing catalog entry, content and channel identity | Mostly `Room Type` |
| Sellable Inventory Unit (SIU) | Atomic capacity that can be sold or blocked | Physical `Room` |
| Physical Space | What staff clean, inspect, maintain and grant access to | `Room` |
| Competition Group | Units that consume the same inventory (entire estate vs rooms) | `room_category = Villa` lockout |
| Availability Service | One answer for search, quote, booking, CRS, tape chart, MCP and ARI | Fragmented SQL paths |

The SIU may eventually be a new DocType or a carefully defined extension of
Room. That is an ADR decision. A hidden placeholder Room is not an accepted
architecture unless its check-in, housekeeping, reporting, and channel
semantics are explicitly designed.

### Bounded contexts

1. **Catalog and setup**
   - Property kind presets
   - Listing content and terminology
   - Module and policy defaults
2. **Inventory and availability**
   - Sellable units
   - Physical spaces
   - competition groups
   - reservation holds, owner/maintenance blocks and turnover buffers
3. **Booking and reservation lifecycle**
   - inquiry / request / quote / hold / pending payment / confirmed
   - modification, extension, cancellation, no-show and close-out
4. **Pricing and finance**
   - immutable quote version
   - typed charge components
   - tax classification
   - payments, deposits (liabilities), refunds and disputes
5. **Stay operations**
   - KYC, arrival, secure access release
   - turnover, inspection, maintenance and incident escalation
6. **Distribution**
   - OTA / channel identities
   - ARI publication
   - webhook ingestion, idempotency, outbox and reconciliation

### Non-negotiable invariants

1. Every consumer—direct booking, desk, CRS, calendar, MCP, OTA ingress and
   ARI—uses the same availability decision service.
2. Availability returns both quantity and blocking reasons (reservation,
   hold, owner use, maintenance, turnover, entire-place competition).
3. A confirmed reservation can never produce negative inventory.
4. Booking writes are idempotent and concurrency-safe for assigned and
   unassigned inventory.
5. Quote amounts are reproducible from a stored quote / charge snapshot.
6. Security deposits are liabilities, never accommodation revenue.
7. Access instructions are released only when configured payment, KYC,
   booking-state and readiness conditions pass.
8. Existing Hotel properties retain behaviour when `property_kind` is absent
   or `Hotel`.
9. Hybrid inventory cannot enable live OTA ARI until parity tests prove that
   internal and outbound availability agree.

### Reservation state machine required

The existing status set is insufficient for a full STR workflow. Define
state transitions before changing schema:

`Inquiry → Quoted → Requested → Approved / Rejected → Held → Pending Payment
→ Confirmed → Checked In → Checked Out → Closed`

Alternative terminal or side transitions:

- Quote Expired
- Hold Expired
- Guest Cancelled
- Host Cancelled
- OTA Cancelled
- No Show
- Disputed / Deposit Review

For each transition define:

- actor / permission
- inventory effect and hold expiry
- payment and refund effect
- allowed modifications
- notification events
- OTA source-of-truth rules
- idempotency key and audit event

The state list may be simplified for v1, but request-to-book and pending
payment cannot be represented as Confirmed without creating operational and
inventory ambiguity.

### Money architecture

Do not implement STR economics as an expanding collection of amount fields on
Reservation. Define typed quote and folio components:

- accommodation by night
- cleaning fee
- extra guest / pet / early check-in / late checkout
- promotion or LOS adjustment
- tax per component
- cancellation / no-show fee
- OTA commission or gateway fee
- security deposit (payment / liability, not taxable stay revenue by default;
  final treatment requires verified finance advice)
- damage withhold and refund

Each money movement needs currency, expected amount, settled amount, provider
reference, status, timestamps, failure reason, and reconciliation state.

### Reliability and security

- Add idempotency keys to public booking writes and OTA webhooks.
- Serialize booking against the sellable inventory row / competition group;
  type-level `COUNT(*)` checks alone are race-prone.
- Use an outbox / retryable publication model for ARI and messages.
- Add periodic channel reconciliation and drift reporting.
- Treat guest identity documents and access codes as sensitive data with
  scoped roles, retention, audit and encrypted storage where applicable.
- Never store permanent access codes in generic message templates.
- Add recovery runbooks for channel outage, payment webhook failure,
  duplicate reservation, calendar drift and access-code failure.

### Architecture Decision Records required before code

1. **ADR-001 — Sellable inventory unit:** new SIU DocType vs extending Room;
   whole-property representation.
2. **ADR-002 — Listing mapping:** relationship among Listing, Room Type, SIU
   and physical Room.
3. **ADR-003 — Availability source of truth:** API, blocking reasons,
   caching, row-locking and all required consumers.
4. **ADR-004 — Hybrid competition:** whole-property / unit graph and
   bidirectional blocking semantics.
5. **ADR-005 — Property-kind boundary:** allowed preset behaviour and
   prohibited business-rule branching.
6. **ADR-006 — Reservation state machine:** request-to-book, holds, payment
   pending, modifications and OTA state mapping.
7. **ADR-007 — Concurrency and idempotency:** booking lock strategy, public
   request keys and webhook deduplication.
8. **ADR-008 — Quote and charge ledger:** component model, snapshotting,
   discount stacking and tax classification.
9. **ADR-009 — Deposit liability:** hold vs capture, damage close-out,
   withholding and refunds.
10. **ADR-010 — Turnover readiness:** clean / inspect / ready, buffer and
    authorized override.
11. **ADR-011 — Channel sync:** source-of-truth rules, outbox, reconciliation,
    iCal limitations and failure recovery.
12. **ADR-012 — Access security:** storage, release conditions, revocation
    and emergency fallback.
13. **ADR-013 — Migration and compatibility:** backfill, hotel → STR
    conversion, feature flags and rollback.
14. **ADR-014 — Public API / MCP contracts:** additive versioning and
    compatibility tests.

### Testing architecture

Move core invariants from ad-hoc scripts into CI-backed tests:

- unit tests for pricing component and state-transition rules
- integration tests for availability across every consumer
- property-based tests for date ranges and competition groups
- concurrent-booking tests for the final unit
- contract tests for public API, MCP and OTA payloads
- parity tests: internal availability = public search = CRS = ARI
- migration / backfill and rollback tests for existing Hotel properties
- end-to-end STR setup → booking → payment → access → turnover → deposit
  close-out

The existing eval harness should remain as a product regression suite, but it
cannot substitute for deterministic concurrency and invariant tests.

## Operating-model review

### Workflows that are launch gates, not optional enhancements

- Reservation modifications, extensions, shortening and unit moves
- Guest cancellation, host cancellation, no-show and policy waivers
- Primary guest, payer and occupant identities (including minors)
- Payment failure / retry, partial payments, duplicate webhook and chargeback
- Deposit collection, release, partial withhold and evidence
- OTA-origin booking modification and cancellation authority
- Arrival instructions, readiness gating and failed-entry escalation
- Turnover clean, inspection, linen, consumables, maintenance and re-clean
- Incident escalation: lockout, noise, safety, outage, damage and
  unauthorized occupancy
- Cutover reconciliation of future bookings, payments, deposits, blocks,
  external IDs, commissions and payouts

### Required STR operating reports

- sellable, occupied and blocked unit-nights by block reason
- arrival / departure / access readiness
- turnover and inspection SLA
- lead time, length of stay and cancellation rate
- ADR and revenue per available unit-night
- gross booking value vs net accommodation revenue
- cleaning fee vs cleaning cost
- deposit ageing and pending refunds
- expected vs received OTA payouts
- channel commission / tax reconciliation
- guest response SLA, maintenance downtime and damage incidence

### Hotel assumptions that must not leak into STR

- Every stay has a traditional room-number assignment.
- Front-desk check-in is required.
- Checkout alone completes turnover.
- A clean room is automatically inspected and ready.
- Meal plans, walk-ins, waitlists and overbooking are normal.
- The booking contact is the only operational guest.
- Settling the folio ends the financial lifecycle.
- Security deposits are advance revenue.
- Local staff may freely overwrite OTA state.
- Keys are issued at reception.
- All fees recur nightly.
- Static access instructions are safe.
- Same-day turns are safe whenever check-in follows checkout.

## Delivery order

### Phase 0 — decision and Ewa Reserve onboarding design

Before code:

1. Confirm Ewa Reserve topology: whole place, separate units, hybrid, or
   portfolio.
2. Confirm sales channels: direct only, Airbnb / VRBO / OTAs via channel
   manager, iCal, or a mix — and whether hybrid ARI is required at launch.
3. Confirm payment collection, deposit, cancellation, tax (GST on fees + any
   local tourist/occupancy tax), cleaning, and access policies.
4. Confirm book mode: instant confirm vs request-to-book / host approval.
5. Confirm overbooking default (`0` recommended) and whether waitlist is used.
6. Define guest KYC / registration minimum for Indian STR stays.
7. Define an operating runbook: who receives bookings, cleans, inspects,
   issues access, refunds deposits, and responds to guests.
8. Decide whether Ewa Reserve shares staff and permissions with an existing
   hotel property, and how host / cleaner roles map onto current roles.
9. Decide launch access model: instructions-only vs named smart-lock provider.

### Phase 0.5 — approve architecture decisions

Approve ADR-001 through ADR-007 before schema or wizard work. Also approve
the launch-relevant parts of ADR-008 through ADR-012 before accepting money
or live channel bookings.

### Phase 1A — inventory and availability foundation

1. Implement the approved sellable-unit / physical-space representation.
2. Implement one Availability Service with typed blocking reasons.
3. Move direct search, desk availability, CRS, calendar, MCP and ARI reads to
   the same service.
4. Implement competition groups for whole-property / individual-unit
   inventory.
5. Add concurrency-safe locks and idempotent booking commands.
6. Enforce minimum stay, overbooking `0`, owner/maintenance blocks and
   booking holds through the same rules.

### Phase 1B — setup preset and compatibility

1. Add `property_kind` and a STR wizard preset after the inventory model is
   stable.
2. Make `setup_property()` atomically create the selected topology, module
   defaults, policies and overbooking setting.
3. Preserve existing Hotel behaviour and add explicit backfill / rollback.
4. Add CI-backed invariant, parity, migration and concurrent-booking tests.

### Phase 2A — commercial and reservation core

1. Implement the approved typed quote / charge model.
2. Implement cleaning fees, LOS rules and tax classification.
3. Implement the security-deposit liability lifecycle and damage close-out.
4. Implement reservation states for request-to-book, holds, pending payment,
   confirmation, modification, extension, cancellation and no-show.
5. Add payment / refund / webhook idempotency and reconciliation.

### Phase 2B — operational viability

1. Turnover clean → inspect → ready workflow, including HkApp.
2. Readiness buffer, owner-use blocks, maintenance escalation and override.
3. Primary guest / occupant / KYC and retention workflow.
4. Secure arrival / access-instruction release and incident escalation.
5. STR booking-engine presentation and mandatory fee / policy disclosures.
6. Terminology pass across desk, booking engine, WhatsApp, MCP and reports.
7. MCP / public API contract updates and regression tests.
8. Required STR operations and finance reports.

### Phase 3 — distribution and scale

1. Add an ARI outbox, retry policy, alerts and channel reconciliation.
2. Prove hybrid availability parity before enabling live hybrid OTA sync.
3. Define Airbnb / VRBO / Booking.com via channel manager and native iCal
   import/export scope.
4. Add duplicate-safe migration / cutover for external IDs, bookings,
   payments, deposits, blocks, commissions and payouts.
5. Platform payout / commission reconciliation.
6. Owner reporting, revenue share and portfolio workflows.
7. Optional: review integrations and named smart-lock vendors.

## Open decisions

Do not begin development until these are answered:

1. Is Ewa Reserve sold as one entire property, individual units, or both?
2. If both, must a whole-property booking block every individual unit?
3. Which channels will sell it at launch: direct, Airbnb, Booking.com, VRBO,
   channel manager, and/or iCal?
4. Instant book or request-to-book / host approval?
5. Is a security deposit collected as an authorization hold, card/payment
   collection, cash, or a waiver?
6. Is cleaning included in nightly price or charged as a separate fee?
   How is it taxed?
7. Is same-day turnover allowed? If yes, what inspection buffer is required?
8. Is self check-in required, and which smart-lock provider (if any) is used?
9. What guest ID / KYC / police-registration minimum applies?
10. Does the property need GST invoices only, owner statements, or both?
11. Will Ewa share hotel staff/roles, or need host/co-host/cleaner mapping?
12. Is converting an existing hotel Property into STR in scope for v1, or
    only greenfield setup?

## Ewa Reserve go-live acceptance gates

Do not publish inventory until all launch-scope gates pass:

- sellable topology and all competition relationships approved
- internal availability, direct search, CRS and ARI parity verified
- final-unit concurrent booking cannot overbook
- each channel identity and source-of-truth rule verified
- inquiry / request / hold / payment / confirm / modify / cancel / no-show
  transitions tested for enabled booking modes
- primary guest, occupants, minors and applicable international-guest cases
  verified
- payment success, failure, retry, partial payment, refund and duplicate
  webhook tested
- deposit collection / hold / release / partial withhold and evidence tested
- tax and invoice outputs reviewed by the operator's finance adviser
- access withheld when payment, KYC or readiness conditions fail
- turnover task, inspection and ready status visible before next arrival
- same-day turn, minimum gap, owner block and maintenance block tested
- incident and emergency-access fallback rehearsed
- future reservations, money, blocks and external IDs imported with a
  reconciliation report
- expected OTA commission / payout reconciles for a test booking per channel
- permissions are least-privilege and sensitive access data is protected
- backup, rollback, channel outage and manual-calendar runbooks exist
- channel opening is staged and observed through a complete sync cycle
