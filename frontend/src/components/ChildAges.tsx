/** One age picker per child on the public booking pages. The property's own
 * age bands (free under a certain age, adult over another) are applied by
 * the server from these ages - the page never decides who pays. */

export type ChildAge = number | ""

/** Keep the ages list the length of the children count. */
export function sizeAges(ages: ChildAge[], count: number): ChildAge[] {
  const n = Math.max(0, count)
  return ages.length === n
    ? ages
    : Array.from({ length: n }, (_, i) => ages[i] ?? "")
}

/** Ages ready to send, or undefined until every child has one. */
export function agesToSend(ages: ChildAge[]): number[] | undefined {
  return ages.length && ages.every((a) => a !== "")
    ? (ages as number[])
    : undefined
}

/** What search_stay says about a room type beyond its price. */
export interface StayFit {
  available?: boolean
  reason?: string
  needs_confirmation?: boolean
  confirmation_reason?: string
}

/** Can this row be reserved now? A row the party does not fit, or whose
 * dates need a longer stay, has no booking button. */
export const canReserve = (r?: StayFit & { quote: unknown }) =>
  !!r?.quote && r.available !== false

export function StayNotice({ row }: { row?: StayFit }) {
  if (!row) return null
  if (row.available === false && row.reason)
    return <p className="text-xs font-medium text-rose-600">{row.reason}</p>
  if (row.needs_confirmation)
    return (
      <p className="text-xs text-amber-700">
        {row.confirmation_reason} Your request goes to the property to confirm.
      </p>
    )
  return null
}

export default function ChildAges({
  ages,
  onChange,
  selectCls,
}: {
  ages: ChildAge[]
  onChange: (ages: ChildAge[]) => void
  selectCls: string
}) {
  if (!ages.length) return null
  const missing = ages.some((a) => a === "")
  return (
    <div className="space-y-1.5">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {ages.map((age, i) => (
          <label key={i} className="block">
            <span className="mb-1 block text-xs font-medium text-zinc-500">
              Child {i + 1} age
            </span>
            <select
              className={selectCls}
              value={age}
              onChange={(e) => {
                const next = [...ages]
                next[i] = e.target.value === "" ? "" : Number(e.target.value)
                onChange(next)
              }}
            >
              <option value="">Age…</option>
              <option value={0}>Under 1</option>
              {Array.from({ length: 17 }, (_, k) => k + 1).map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>
      {missing && (
        <p className="text-xs text-amber-700">
          Choose each child's age - it decides the price.
        </p>
      )}
    </div>
  )
}
