/** Nightly prices the desk types on New booking (#634). Pure helpers, no
 *  imports, so the arithmetic is checked by scripts/night-prices-check.mjs. */

/** One night priced by hand, as get_quote / create_booking take it. */
export interface NightPrice {
  date: string
  price: number
}

/** The server accepts at most 2 decimals per typed night. */
export const maxPriceDigits = (currencyDigits: number) => Math.min(Math.max(currencyDigits, 0), 2)

const toUnits = (n: number, digits: number) => Math.round(Number((n * 10 ** digits).toFixed(6)))

/** A typed price: a number above zero with no more than `digits` decimals,
 *  else null. Nothing is rounded for the typist - a bad figure stays bad. */
export function parsePrice(text: string, digits: number): number | null {
  const s = text.trim()
  if (!/^\d+(\.\d+)?$/.test(s)) return null
  const dot = s.indexOf(".")
  if (dot >= 0 && s.length - dot - 1 > digits) return null
  const n = Number(s)
  return Number.isFinite(n) && n > 0 ? n : null
}

/** A room total spread over `nights` so the nights add up to it exactly in
 *  the currency's smallest unit; the first nights take any odd unit. */
export function splitRoomTotal(total: number, nights: number, digits: number): number[] {
  if (nights < 1 || !(total > 0)) return []
  const units = toUnits(total, digits)
  const base = Math.floor(units / nights)
  const extra = units - base * nights
  return Array.from({ length: nights }, (_, i) => (base + (i < extra ? 1 : 0)) / 10 ** digits)
}

/** The typed nights still inside the stay (check-in .. day before
 *  check-out), oldest first - what is sent as `night_prices`. A night that
 *  fell out of the stay on a date change is dropped, never sent. */
export function typedNights(
  typed: Record<string, number>,
  dates: string[],
): NightPrice[] {
  return dates
    .filter((d) => typed[d] > 0)
    .map((d) => ({ date: d, price: typed[d] }))
}

/** A price typed equal to what Kamra would charge is not an override. */
export const isOverride = (price: number | undefined, rate: number, digits: number) =>
  price !== undefined && toUnits(price, digits) !== toUnits(rate, digits)

/** A night as the desk reads it: weekday, day and month ("Thu 11 Sep"), in the
 *  reader's locale. The date is read as written ("YYYY-MM-DD"), never shifted
 *  by the browser's time zone. */
export function nightLabel(date: string, locale?: string | string[]): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(date)
  if (!m) return date
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])).toLocaleDateString(locale, {
    weekday: "short",
    day: "numeric",
    month: "short",
  })
}

/** The night a server message is about: the first of `dates` it names. */
export function nightInMessage(message: string, dates: string[]): string | null {
  return dates.find((d) => message.includes(d)) ?? null
}

/** Every night in `dates` at one price (the desk's "same price every night");
 *  a night already at that price is not an override. */
export function samePrice(
  price: number,
  nights: { date: string; price: number }[],
  digits: number,
): Record<string, number> {
  return Object.fromEntries(nights.filter((n) => isOverride(price, n.price, digits)).map((n) => [n.date, price]))
}
