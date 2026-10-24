import { useT } from "../lib/i18n"

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

function translateAvailabilityNote(source: string, t: (source: string, vars?: Record<string, string | number>) => string) {
  if (source === "The property cannot accommodate the number of people requested.")
    return t("The property cannot accommodate the number of people requested.")
  const minStay = source.match(/^These dates need a stay of at least (\d+) nights(?: \((.+)\))?\.$/)
  if (minStay) {
    const n = Number(minStay[1])
    const base = n === 1
      ? t("These dates require a minimum stay of {n} night.", { n })
      : t("These dates require a minimum stay of {n} nights.", { n })
    return minStay[2] ? `${base} (${minStay[2]})` : base
  }
  const overCapacity = source.match(/^(\d+) guests? above what it sleeps: possible only if the group is happy to share beds\. The property confirms the arrangement and the price for them\.$/)
  if (overCapacity) {
    const n = Number(overCapacity[1])
    return n === 1
      ? t("The group exceeds the listed capacity by {n} guest. The property must confirm bed sharing and the price.", { n })
      : t("The group exceeds the listed capacity by {n} guests. The property must confirm bed sharing and the price.", { n })
  }
  return source
}

export function StayNotice({ row }: { row?: StayFit }) {
  const { t } = useT()
  if (!row) return null
  if (row.available === false && row.reason)
    return <p className="text-xs font-medium text-rose-600">{translateAvailabilityNote(row.reason, t)}</p>
  if (row.needs_confirmation)
    return (
      <p className="text-xs text-amber-700">
        {translateAvailabilityNote(row.confirmation_reason || "", t)} {t("Your request goes to the property to confirm.")}
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
  const { t } = useT()
  if (!ages.length) return null
  const missing = ages.some((a) => a === "")
  return (
    <div className="space-y-1.5">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {ages.map((age, i) => (
          <label key={i} className="block">
            <span className="mb-1 block text-xs font-medium text-zinc-500">
              {t("Child {n} age", { n: i + 1 })}
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
              <option value="">{t("Age…")}</option>
              <option value={0}>{t("Under 1")}</option>
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
          {t("Choose each child's age; this determines the price.")}
        </p>
      )}
    </div>
  )
}
