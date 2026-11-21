/** Reception dates in the reader's format.
 *
 * Spanish and Portuguese read the day first, as their date pickers do: a moment as dd-mm (dd-mm-aaaa outside the
 * current year) and hh:mm with no seconds. Other languages keep the format Kamra
 * already uses (RoomDrawer's useDates): day and short month, and hh:mm, in the browser's locale (Arabic in "ar"),
 * with the year outside the current one.
 *
 * Server values are naive "YYYY-MM-DD[ HH:MM[:SS]]" on the property's clock, so the wall time is read as written.
 * Pure: no React, no DOM; scripts/local-dates-check.mjs runs it in Node. */

const DAY_FIRST = new Set(["es", "pt"])
const STAMP = /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?/

const kamraLocale = (lang: string, locale?: string) => (lang === "ar" ? "ar" : locale)

/** A server moment as {date, time} for "{date} at {time}" sentences; null when it is not a date. */
export function momentParts(
  value: string | null | undefined,
  lang: string,
  options: { locale?: string; now?: Date } = {},
): { date: string; time: string } | null {
  const match = STAMP.exec(value ?? "")
  if (!match) return null
  const [, year, month, day, hour = "00", minute = "00"] = match
  const thisYear = Number(year) === (options.now ?? new Date()).getFullYear()
  if (DAY_FIRST.has(lang)) {
    return { date: thisYear ? `${day}-${month}` : `${day}-${month}-${year}`, time: `${hour}:${minute}` }
  }
  const at = new Date(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute))
  const locale = kamraLocale(lang, options.locale)
  return {
    date: at.toLocaleDateString(locale, { day: "numeric", month: "short", ...(thisYear ? {} : { year: "numeric" }) }),
    time: at.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" }),
  }
}
