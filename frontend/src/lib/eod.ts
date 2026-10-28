/*  End of Day (night audit) - the API the wizard, the landing page and the
    audit pack viewer share. Every call goes to kamra.night_audit /
    kamra.api.run_night_audit; the server decides what blocks, what a
    no-show costs and what the pack holds. */

import { call } from "./api"

export type Severity = "block" | "warn" | "info"
export type StepStatus = "pending" | "running" | "done" | "blocked" | "skipped"

export type CheckItem = Record<string, unknown>

export interface Check {
  key: string
  title: string
  severity: Severity
  count: number
  items: CheckItem[]
  truncated?: boolean
  action: string
  resolve?: string | null
  amount?: number
  threshold?: number
  enabled?: boolean
  outcomes?: Record<string, number>
  mismatches?: number
  acknowledgement?: Acknowledgement | null
  exception?: boolean
}

export interface Acknowledgement {
  key: string
  title: string
  count: number
  note: string
  by: string
  by_name?: string
  at: string
  auto?: number
}

export interface Step {
  index: number
  key: string
  title: string
  checks: string[]
  status: StepStatus
  count: number
  blocking: string[]
}

export interface Session {
  session: string
  user: string
  user_name?: string
  cashier_id?: string
  business_date?: string
  status: string
  terminal?: string
  opening_float: number
  cash: number
  card: number
  upi: number
  other: number
  paid_outs: number
  drops: number
  petty_cash: number
  expected_cash: number
  counted_cash: number | null
  variance: number | null
  opened_at?: string
  closed_at?: string
}

export interface EodState {
  property: string
  property_name: string
  currency?: string
  business_date: string
  /** Property's open BD (may still equal a closed audit day when stuck). */
  open_business_date?: string
  server_date: string
  server_time: string
  property_now: string
  require_cashier_pin: number
  blind_count: number
  high_balance_threshold: number
  auto_audit_with_blockers: string
  reports: { key: string; title: string }[]
  audit: string
  ran: boolean
  status: string
  current_step: number
  notes?: string | null
  acknowledgements: Acknowledgement[]
  checks: Check[]
  blockers?: string[]
  steps: Step[]
  sessions: Session[]
  has_pack?: boolean
  /** Completed audit for the open BD but the date roll did not stick. */
  stuck_date?: {
    audit: string
    status: string
    business_date: string
    run_trigger?: string
  } | null
}

export interface OverviewRow {
  property: string
  property_name: string
  business_date: string
  property_now: string
  arrivals_pending: number
  departures_pending: number
  open_cashiers: number
  open_pos_bills: number
  blockers: number
  blocker_keys: string[]
  draft_step: number | null
  /** next automatic audit on the property clock; null = manual only */
  next_auto_run: string | null
  /** scheduled Hold and alert: BD not rolled; resolve and run EOD. */
  held: { at: string; detail: string } | null
  /** Completed audit for current BD but date roll did not stick. */
  stuck_date: {
    audit: string
    status: string
    business_date: string
    run_trigger?: string
  } | null
  last_run: {
    audit: string
    business_date: string
    status: string
    run_trigger?: string
    has_pack?: boolean
  } | null
}

export interface RunRow {
  name: string
  business_date: string
  status: string
  room_charges_posted: number
  amount_posted: number
  no_shows_flagged: number
  late_arrivals_held: number
  folios_opened: number
  run_trigger?: string
  run_by?: string
  exceptions?: number
  creation: string
  has_pack: boolean
}

// The pack is a JSON snapshot; sections are read loosely and rendered as
// tables, so an older pack missing a section still prints the rest.
export type Pack = Record<string, any> // eslint-disable-line @typescript-eslint/no-explicit-any

export interface PackResponse {
  audit: string
  run: Record<string, unknown>
  has_pack: boolean
  pack: Pack | null
  message?: string
  can_rebuild?: boolean
}

export const eodOverview = () =>
  call<OverviewRow[]>("kamra.night_audit.eod_overview")

export const eodSession = (property: string, audit?: string | null) =>
  call<EodState>("kamra.night_audit.eod_session", { property, audit: audit ?? undefined })

export const eodProgress = (
  property: string,
  args: { step?: number; key?: string; status?: string; notes?: string },
) => call("kamra.night_audit.eod_progress", { property, ...args })

export const eodAcknowledge = (property: string, key: string, reason: string) =>
  call("kamra.night_audit.eod_acknowledge", { property, key, reason })

export const eodMarkNoShow = (reservation: string) =>
  call<{ outcome: string; fee_amount: number }>(
    "kamra.night_audit.eod_mark_no_show", { reservation })

export const runNightAudit = (property: string) =>
  call<{
    audit?: string
    already_ran?: boolean
    status?: string
    room_charges_posted?: number
    amount_posted?: number
    no_shows_flagged?: number
    next_business_date?: string
  }>("kamra.api.run_night_audit", { property })

export const auditHistory = (property: string, limit = 60) =>
  call<RunRow[]>("kamra.night_audit.night_audit_history", { property, limit })

export const auditPack = (audit: string) =>
  call<PackResponse>("kamra.night_audit.night_audit_pack", { audit })

export const rebuildAuditPack = (audit: string) =>
  call<PackResponse>("kamra.night_audit.rebuild_audit_pack", { audit })

export const recoverStuckBusinessDate = (property: string) =>
  call<{ ok: boolean; audit: string; business_date: string; next_business_date: string }>(
    "kamra.night_audit.recover_stuck_business_date",
    { property },
  )
