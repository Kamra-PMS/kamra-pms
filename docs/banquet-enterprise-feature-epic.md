# Banquet Enterprise — Opera-class guest journey & department orchestration

**Status:** Proposed epic (gap analysis vs Kamra today + Opera Banquet / Event Management)  
**Target:** Kamra `develop` → stable after phased delivery  
**Related:** Venue Booking (`EVT-*`), `kamra/banquet.py`, Events app in SPA

---

## Executive summary

Kamra already ships a **strong banquet core**: function sheet (Venue Booking), catalogue, quotation versioning, BEO, pack list, payment milestones, advances/deposits, pipeline, registers, kitchen indent, and internal sales reminders.

What large hotels expect from **Opera Banquet / Event Management** — and what this epic adds — is the **guest-facing commercial loop** (send quote → customer confirms → chase payments) and the **internal operations loop** (on confirmation, every department gets a checklist and alerts: HK, F&B, Engineering, Finance, HR).

| Layer | Today | This epic |
|-------|-------|-----------|
| Sales & pricing | Strong | + email/PDF send, guest confirmation |
| Money | Strong | + guest balance reminders, payment links |
| Guest comms | Print only | + email templates, tasting invites |
| Ops on confirm | Notes on BEO | + department task packs & notifications |
| Food tasting | Missing | + configurable tasting workflow |
| Equipment / AV | Service lines on pack list | + engineering checklist (WiFi, projector, coupons) |

---

## Requirement matrix (your list)

| # | Requirement | Kamra today | Gap | Epic phase |
|---|-------------|-------------|-----|------------|
| 1 | Build quotation | **Yes** — `generate_quote`, line items, revisions, margin advisor | — | — |
| 2 | Send quotation to guest | **Partial** — print/PDF from `/banquet/:name/quote`; stamps `quote_sent_on` | No email/WhatsApp to customer with PDF link | **P1** |
| 3 | Confirmation from customer | **Partial** — desk sets status Tentative → Confirmed; `contract_signed_on` field exists | No guest accept link, e-sign, or “customer confirmed” event | **P1** |
| 4 | Customisation & modification | **Yes** — menus, services, negotiate, open items, quote versions | — | — |
| 5 | Advance payment | **Yes** — `record_receipt`, milestones, default 25/50/balance | Optional: payment link to guest | **P2** |
| 6 | Quotation reminder (unsent / no response) | **Partial** — `follow_up` alert if `follow_up_date` passed; no “quote sent 7d ago, no reply” | Guest + sales chase templates | **P1** |
| 7 | Balance payment notification | **Partial** — internal `payment_due` / overdue in `banquet_reminders`; WhatsApp to `sales_owner` | Guest-facing balance reminder + payment link | **P2** |
| 8 | Food tasting — guest email | **No** | Full workflow | **P2** |
| 9 | Food tasting — chef/sales alert | **No** | Alert on tasting booked / completed | **P2** |
| 10 | Configure tasting (allow/disallow, portions, schedule) | **No** | Property + function settings | **P2** |
| 11 | On guest confirm → internal notifications | **No** — `set_status(Confirmed)` logs only | Department notification fan-out | **P1** |
| 12 | Function prospect / sales notified | **Partial** — sales_owner on record; no confirm event | Explicit confirm notification | **P1** |
| 13 | Finance / billing | **Partial** — payment terms, receipts, invoice; no “new confirm” task | Billing checklist + notify Finance role | **P1** |
| 14 | Housekeeping — arrangement / cleaning | **Partial** — green room → Room Block; HK read-only on BEO | Pre/post function HK checklist | **P1** |
| 15 | F&B — setup | **Partial** — BEO, kitchen indent, pack list | F&B setup checklist + notify | **P1** |
| 16 | Engineering — AC, IT, WiFi, speed test, coupons | **No** — AV as service lines only | Engineering checklist template | **P2** |
| 17 | Conference — projector, AV | **Partial** — Banquet Service Items (AV category) on pack list | AV sub-checklist with sign-off | **P2** |
| 18 | HR — extra staff (M/F), bar setup | **No** | HR checklist + headcount fields | **P2** |

**Legend:** Yes = production-ready · Partial = exists but manual or internal-only · No = not built

---

## What Kamra already has (don't rebuild)

### DocTypes & data model
- **Venue Booking** — central function sheet (`EVT-{YYYY}-{####}`)
- **Banquet Menu / Service Item / Dish** — catalogue
- **Banquet Function Item** — priced lines (menu, AV, decor, staffing…)
- **Banquet Payment Term** — milestone schedule (Pending / Overdue / Received / Waived)
- **Banquet Receipt** — Advance, Payment, Security Deposit, Refund
- **Banquet Quote Revision** — negotiation audit trail
- **Banquet Open Item** — unsettled TBDs (Hotel/Client owner)
- **Banquet Selection** — customer dish picks → BEO + kitchen

### Pipeline
`Enquiry` → `Tentative` → `Confirmed` → `Completed` (+ `Cancelled` / `Lost`)

### Documents (print)
Quote · Contract · BEO · Pack list · Invoice · Menu card · Receipt voucher

### Reminders (internal, scheduled 08:30)
follow_up · hold_expiring · payment_due · beo_missing · pax_missing · contract_unsigned · no_advance · open_items · close_it  
Delivery: WhatsApp → `sales_owner`, else Front Desk role notify.

### UI
`/banquet` · `/banquet/:name` (6-step wizard) · month grid · diary · registers · catalogue

### API / MCP
50+ `kamra.banquet.*` endpoints; 20 MCP tools for agents.

---

## Opera Banquet Management — capability map

| Opera area | Opera typical behaviour | Kamra today | Epic adds |
|------------|-------------------------|-------------|-----------|
| **CRM / Lead** | Lead → function conversion | Enquiry on Venue Booking | Optional Lead DocType (P3) |
| **Quotation** | Build, email, track opens | Build + print | Email send + tracking (P1) |
| **Contract** | Signed contract stored | Print contract; `contract_signed_on` manual | Guest e-accept + auto stamp (P1) |
| **Deposit rules** | Property-level auto % | Manual milestones + defaults API | Rule engine on property (P3) |
| **BEO / Function sheet** | Department copies | Strong BEO + pack list | Department-specific BEO views (P2) |
| **Event checklist** | HK / ENG / F&B tasks per event type | None | **Banquet Event Checklist** (P1) |
| **Resource scheduling** | Equipment calendar | Service lines only | Equipment inventory (P3) |
| **Billing routing** | Bill to master / split | Folio post to group master | Enhanced routing (existing) |
| **Food tasting** | Tasting appointment module | None | **Banquet Food Tasting** (P2) |
| **Notifications** | Email to departments on status | Sales WhatsApp reminders | Full fan-out on Confirm (P1) |
| **Production** | Outlet production sheets | Kitchen indent | Outlet scheduling (P3) |

---

## Proposed feature design

### 1. Guest commercial loop (P1)

**Send quotation**
- Action: “Send to guest” on quote document
- Channels: email (required), WhatsApp (if property configured)
- Attach: PDF or link to guest portal `/banquet/quote/:token`
- Set `quote_sent_on`, log in activity + optional `Banquet Communication Log` child table

**Quotation reminders**
- Scheduler rules: e.g. quote sent + 3 days + no status change → email guest + alert sales
- Desk board: “Awaiting customer response” column

**Customer confirmation**
- Guest link: Accept quote / Request changes / Decline
- On accept: set `customer_confirmed_on`, optional auto-move to `Tentative` or `Confirmed` (property setting)
- Desk can still manually confirm; guest accept is additive evidence
- Stamp `contract_signed_on` when guest accepts terms checkbox

### 2. Payment comms (P2)

**Advance & balance**
- Reuse `frappe/payments` payment links tied to `Banquet Payment Term` row
- Email/WhatsApp: “Advance due”, “Balance due before event”
- Extend `_function_alerts` with `balance_due_guest` when milestone overdue

### 3. Food tasting (P2)

New child DocType **Banquet Food Tasting** (or section on Venue Booking):

| Field | Purpose |
|-------|---------|
| `tasting_allowed` | Property default + per-function override |
| `tasting_date` / `tasting_time` | Scheduled slot |
| `portions` / `pax_tasting` | How much food to prepare |
| `menu_snapshot` | Dishes to taste |
| `status` | Requested / Scheduled / Done / Waived |
| `chef_user` / `sales_owner` | Notify list |

Workflow:
1. Sales schedules tasting → email guest with calendar invite + menu
2. Chef + sales get in-app + WhatsApp alert
3. After tasting, notes feed back into negotiation / menu composer

### 4. Department orchestration on Confirm (P1 — core differentiator)

When status → **Confirmed**, fan-out **Banquet Event Checklist** instances from property templates:

| Department | Template tasks (examples) |
|------------|----------------------------|
| **Sales / Banquet** | Finalise BEO, confirm pax, issue contract |
| **Finance** | Verify advance received, payment schedule, GSTIN |
| **Housekeeping** | Pre-function clean, green room, post-function reset |
| **F&B** | Kitchen indent, setup style, bar placement |
| **Engineering** | AC setpoint, projector/AV test, WiFi SSID, speed test, guest coupons |
| **HR** | Extra staff count (male/female), bar setup crew |

**Data model (proposed):**
- `Banquet Checklist Template` (per property, per event type)
- `Banquet Checklist Task` (child: department, title, due_offset_days, assignee_role)
- `Banquet Function Checklist` (instance on Venue Booking, status Open/Done)

**Notifications:**
- On confirm: notify each role (reuse `_notify_role` + WhatsApp + email)
- Daily digest until all pre-event tasks done
- HK app (`/hk`) optional view for HK tasks only

### 5. Engineering / AV checklist (P2)

Extend service catalogue + checklist:
- WiFi network name, password/coupon batch, speed test result field
- Projector resolution test, HDMI check, microphone count
- Link to existing AV **Banquet Service Item** lines on pack list

### 6. HR / bar setup (P2)

Fields on Venue Booking or checklist:
- `staff_male` / `staff_female` required
- `bar_setup` (yes/no, style)
- HR checklist task auto-created

---

## Delivery phases

### Phase 1 — Guest quote & confirm + department fan-out (MVP)
- [ ] Email send quotation (+ PDF)
- [ ] Guest confirmation link (accept/decline)
- [ ] Quotation no-response reminders (guest + sales)
- [ ] On Confirm → checklist instantiation from templates
- [ ] Notify Finance, HK, F&B, Sales roles
- [ ] Checklist UI on function sheet + `/banquet` board
- [ ] Tests + eval harness additions

### Phase 2 — Tasting + payments + Engineering/HR
- [ ] Food tasting workflow + emails + chef/sales alerts
- [ ] Property tasting policy (allow, default portions)
- [ ] Guest balance/advance payment links + reminders
- [ ] Engineering + HR checklist templates
- [ ] AV/WiFi sub-checklist

### Phase 3 — Opera parity extras
- [ ] Guest portal (view quote, pay, confirm, upload PO)
- [ ] Equipment resource calendar
- [ ] Property-level deposit rule engine
- [ ] Weighted pipeline forecasting
- [ ] E-sign integration (DocuSign / native)

---

## Technical touchpoints (implementation hint)

| Area | Files / modules |
|------|-----------------|
| Backend | `kamra/banquet.py`, new `kamra/banquet_checklists.py`, `venue_booking.json` |
| Notifications | `kamra/agents_channels.py`, `kamra/housekeeping._notify_role`, email templates |
| Scheduler | `kamra/hooks.py` — extend `run_banquet_reminders` |
| Frontend | `BanquetFunction.tsx`, new `BanquetChecklist.tsx`, guest public page |
| Guest-facing | `kamra/public_api.py` — tokenised quote/confirm routes |
| Tests | `kamra/tests/test_banquet.py`, new `test_banquet_enterprise.py` |

---

## Success criteria

1. Sales can **send a quote by email** and see when it was sent / reminded.
2. Guest can **confirm online**; desk sees confirmation timestamp.
3. On **Confirmed**, Finance, HK, and F&B receive **actionable notifications** within 1 minute.
4. Each department has a **checklist** due before event date; banquet manager sees % complete.
5. **Food tasting** can be scheduled with guest email and chef alert.
6. **Balance due** triggers guest reminder with pay link before event.
7. No regression in existing BEO, billing, or pipeline flows (CI eval harness green).

---

## References

- In-repo: `kamra/banquet.py`, `frontend/src/screens/Banquet*.tsx`, `docs-site/features.md`
- Opera OHIP / Opera Cloud Banquet & Event Management (department BEO, event checklists, deposit policies) — conceptual parity target, not a UI clone.
