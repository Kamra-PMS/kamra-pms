/** Stay dates for the public booking pages. The stay arrives in the URL
 *  (/book/in/out/adults/children), so anything there may be a typo, a past
 *  date or not a date at all: these helpers never throw. Dates are local
 *  YYYY-MM-DD (toISOString would shift them a day east of UTC). */

const pad = (n: number) => String(n).padStart(2, "0")

export function isoDate(d: Date) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** A real calendar date, or null (2026-02-31 and "kamra-demo-palace" are not). */
export function parseDate(s?: string | null): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s ?? "")
  if (!m) return null
  const d = new Date(+m[1], +m[2] - 1, +m[3])
  return d.getMonth() === +m[2] - 1 ? d : null
}

export function todayPlus(days: number) {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return isoDate(d)
}

export function addDays(date: string, days: number) {
  const d = parseDate(date) ?? new Date()
  d.setDate(d.getDate() + days)
  return isoDate(d)
}

export function nightsBetween(a: string, b: string) {
  const x = parseDate(a), y = parseDate(b)
  if (!x || !y) return 1
  return Math.max(1, Math.round((y.getTime() - x.getTime()) / 86_400_000))
}

/** The stay a URL asks for, made sane: a missing or bad check-in is
 *  tomorrow, a past one today; check-out must follow it (else two nights);
 *  at least one adult, never negative children. */
export function stayFromParams(p: {
  checkin?: string
  checkout?: string
  adults?: string
  children?: string
}) {
  const today = todayPlus(0)
  let check_in_date = parseDate(p.checkin) ? p.checkin! : todayPlus(1)
  if (check_in_date < today) check_in_date = today
  const check_out_date =
    parseDate(p.checkout) && p.checkout! > check_in_date
      ? p.checkout!
      : addDays(check_in_date, 2)
  const whole = (v: string | undefined, min: number, dflt: number) => {
    const n = Math.floor(Number(v))
    return Number.isFinite(n) && v ? Math.max(min, n) : dflt
  }
  return {
    check_in_date,
    check_out_date,
    adults: whole(p.adults, 1, 2),
    children: whole(p.children, 0, 0),
    pets: 0,
  }
}
