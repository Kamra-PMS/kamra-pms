/*  check_out with company credit control (#238). The guided check-out
    sheet (CheckOutDialog) shows the credit check from checkout_context and
    collects an override reason; check_out re-runs the same check on the
    server, so the sheet is only the explanation, never the gate. */

import { call } from "../lib/api"

export interface CreditCheck {
  ok: boolean
  blocked: boolean
  policy: string
  company: string
  amount: number
  reasons: string[]
  credit_limit: number
  exposure: number
  over_limit_by: number
  overdue_amount: number
  oldest_due_date: string | null
  can_override?: boolean
}

interface CheckOutResult {
  ok: boolean
  credit_warnings?: { company: string; reasons: string[]; overridden: boolean }[]
}

export const checkOutWithCredit = (reservation: string, credit_override_reason?: string) =>
  call<CheckOutResult>("kamra.api.check_out", {
    reservation,
    ...(credit_override_reason ? { credit_override_reason } : {}),
  })

