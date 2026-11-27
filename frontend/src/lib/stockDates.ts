/* When a kitchen stock entry happened, and when it was typed. */

/** A datetime-local value ("2026-11-02T18:00") as the server takes it; blank means now. */
export function postedAt(input: string): string | undefined {
  const v = input.trim()
  if (!v) return undefined
  return v.replace("T", " ") + (v.length === 16 ? ":00" : "")
}

const ms = (s: string) => new Date(s.slice(0, 19).replace(" ", "T")).getTime()

/** The line was typed more than a minute after the moment it is dated. */
export function enteredLater(row: { posted_at?: string | null; creation: string }): boolean {
  if (!row.posted_at) return false
  return Math.abs(ms(row.creation) - ms(row.posted_at)) > 60_000
}
