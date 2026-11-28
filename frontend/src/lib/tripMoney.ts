/** How the trip screens and the chain search print another hotel's money, and where a
 *  trip's money figures take their symbol and currency code from.
 *
 *  The backend adds the trip's total, advance paid and advance due over the live stays only
 *  (kamra.reservation_state.LIVE_STATUSES), and the advance still held over the cancelled
 *  stays only. So the first stay in date order is not always the right one: a cancelled first
 *  stay in another currency would label a rupiah total with its own symbol and decimals. */
import { fmtAmount, locale } from "./money"

const LIVE = ["Confirmed", "Checked In", "Held", "Pending Payment"]

interface Priced { currency?: string | null; currency_symbol?: string | null }
interface Leg extends Priced { status: string }
interface Money { sym: string; code?: string | null }

/** One stay's (or one hotel's) symbol and currency code. */
export const moneyOf = (l?: Priced): Money => ({ sym: l?.currency_symbol ?? "", code: l?.currency })

/** More than one currency among the stays: then every amount names its own. */
export const mixedCurrency = (legs: Priced[]) =>
  new Set(legs.map((l) => l.currency).filter(Boolean)).size > 1

/** An amount in a stay's own currency. The desk's currency keeps its symbol; another one,
 *  or any figure on a trip that mixes currencies, takes the ISO code instead ("$" is shared
 *  by several dollars, and a printed confirmation is clearer with the code). */
export function amt(n: unknown, money: Money, mixed = false) {
  const desk = locale().currency
  const named = money.code && (mixed || (!!desk && money.code !== desk))
  return `${named ? `${money.code}\u00a0` : money.sym}${fmtAmount(n ?? 0, money.code)}`
}

/** Search results with the desk's own currency first. The server groups the hotels by
 *  currency, cheapest first in each: a bare number can't rank two currencies. */
export function deskFirst<T extends Priced>(rows: T[]): T[] {
  const desk = locale().currency
  return [...rows].sort((a, b) => Number(a.currency !== desk) - Number(b.currency !== desk))
}

export function tripMoney(legs: Leg[]) {
  return {
    /** total, advance required, advance paid, advance due */
    live: moneyOf(legs.find((l) => LIVE.includes(l.status)) ?? legs[0]),
    /** advance still held on cancelled stays */
    held: moneyOf(legs.find((l) => l.status === "Cancelled") ?? legs[0]),
  }
}
