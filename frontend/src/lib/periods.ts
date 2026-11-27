/* Report periods, as calendar days ("YYYY-MM-DD"). Weeks start on Monday. */

export type Period = "today" | "yesterday" | "thisWeek" | "lastWeek" | "thisMonth" | "lastMonth"

const DAY = 86_400_000
const iso = (ms: number) => new Date(ms).toISOString().slice(0, 10)

/** [first day, last day] of a period seen from `today`; a running period ends today. */
export function periodRange(period: Period, today: string): [string, string] {
  const t = Date.parse(`${today}T00:00:00Z`)
  const [y, m] = today.split("-").map(Number)
  const monday = t - ((new Date(t).getUTCDay() + 6) % 7) * DAY
  switch (period) {
    case "yesterday": return [iso(t - DAY), iso(t - DAY)]
    case "thisWeek": return [iso(monday), today]
    case "lastWeek": return [iso(monday - 7 * DAY), iso(monday - DAY)]
    case "thisMonth": return [iso(Date.UTC(y, m - 1, 1)), today]
    case "lastMonth": return [iso(Date.UTC(y, m - 2, 1)), iso(Date.UTC(y, m - 1, 0))]
    default: return [today, today]
  }
}
