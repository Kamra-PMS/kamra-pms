/* Pure helpers of the POS refund screens: what the refund window asks the
   server for, a bill's refund badge, and the printed slip. */

export type RefundKind = "whole" | "items" | "amount"

/** Partly or fully refunded, for a badge; null when nothing went back. */
export function refundBadge(paid: number, refunded: number): "partly" | "full" | null {
  if (!(refunded > 0)) return null
  return paid > 0 && refunded >= paid - 0.005 ? "full" : "partly"
}

/** The parameters for refund_quote / refund_bill from what is typed, or null
 *  when there is nothing to ask yet. `back` marks lines to return to stock. */
export function refundRequest(
  kind: RefundKind, qtys: Record<string, string>, back: Record<string, boolean>, amount: string,
): { kind: RefundKind; lines?: { row: string; qty: number; back_to_stock: number }[]; amount?: number } | null {
  if (kind === "amount") {
    const value = Number(amount)
    return value > 0 ? { kind, amount: value } : null
  }
  if (kind === "whole") {
    // the server takes everything left; only the ticks matter
    return { kind, lines: Object.keys(back).filter((row) => back[row]).map((row) => ({ row, qty: 0, back_to_stock: 1 })) }
  }
  const lines = Object.entries(qtys)
    .filter(([, q]) => Number(q) > 0)
    .map(([row, q]) => ({ row, qty: Number(q), back_to_stock: back[row] ? 1 : 0 }))
  return lines.length ? { kind, lines } : null
}

/** What the refund window asks for before it can pay, from who is signed in.
 *  The right to approve comes first, then "Require cashier PIN": an approver
 *  types nothing, or their own PIN (setting one first if they have none);
 *  anyone else needs an approver to pick their name and type their PIN. The
 *  server decides again (kamra.pos_refunds._approve). */
export function refundApproval(
  who: { can_approve: boolean; pin_required: boolean; has_pin: boolean }, supervisor: string, pin: string,
): {
  ask: "nothing" | "own-pin" | "set-pin" | "supervisor"
  ready: boolean
  args: { supervisor: string | null; supervisor_pin: string | null }
} {
  const none = { supervisor: null, supervisor_pin: null }
  if (!who.can_approve) {
    return {
      ask: "supervisor", ready: !!supervisor && !!pin,
      args: { supervisor: supervisor || null, supervisor_pin: pin || null },
    }
  }
  if (!who.pin_required) return { ask: "nothing", ready: true, args: none }
  if (!who.has_pin) return { ask: "set-pin", ready: false, args: none }
  return { ask: "own-pin", ready: !!pin, args: { supervisor: null, supervisor_pin: pin || null } }
}

/** One key per attempt: the server pays a repeated key once. */
export function newAttemptKey(): string {
  const random = () => Math.random().toString(36).slice(2, 10)
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now().toString(36)}-${random()}${random()}`
}

const esc = (s: unknown) =>
  String(s ?? "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c] as string))

/** The refund slip's body, for the thermal printer. */
export function refundSlipHtml(s: {
  title: string; outlet: string; bill: string; when: string; total: string
  lines: { name: string; qty: number; amount: string }[]
  /** label and value pairs: how, why, who */
  rows: [string, string][]
  sign: string
}): string {
  const line = (l: string, v: string) => `<div class="row"><span>${esc(l)}</span><span>${esc(v)}</span></div>`
  return `
    <div class="c brand">${esc(s.outlet)}</div>
    <div class="box"><div class="cap">${esc(s.title)} ${esc(s.bill)}</div><div class="big">${esc(s.total)}</div></div>
    <div class="sm">${esc(s.when)}</div>
    <div class="hr"></div>
    ${s.lines.map((x) => line(`${x.qty} x ${x.name}`, x.amount)).join("")}
    ${s.lines.length ? '<div class="hr"></div>' : ""}
    ${s.rows.map(([l, v]) => line(l, v)).join("")}
    <div style="margin-top:28px" class="sm">${esc(s.sign)} ______________</div>
  `
}
