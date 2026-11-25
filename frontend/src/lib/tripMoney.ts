/** Where a trip's money figures take their symbol and currency code from.
 *
 *  The backend adds the trip's total, advance paid and advance due over the live stays only
 *  (kamra.reservation_state.LIVE_STATUSES), and the advance still held over the cancelled
 *  stays only. So the first stay in date order is not always the right one: a cancelled first
 *  stay in another currency would label a rupiah total with its own symbol and decimals. */
const LIVE = ["Confirmed", "Checked In", "Held", "Pending Payment"]

interface Leg { status: string; currency?: string | null; currency_symbol?: string | null }
const pick = (l?: Leg) => ({ sym: l?.currency_symbol ?? "", code: l?.currency })

export function tripMoney(legs: Leg[]) {
  return {
    /** total, advance required, advance paid, advance due */
    live: pick(legs.find((l) => LIVE.includes(l.status)) ?? legs[0]),
    /** advance still held on cancelled stays */
    held: pick(legs.find((l) => l.status === "Cancelled") ?? legs[0]),
  }
}
