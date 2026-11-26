/* The pick-from-a-list pills used by Allergens & dietary tags and by a dish's Choices: what is picked shows
   first, each with a x that takes it off; what is left shows below as "+ Name", and a click adds it.
   One component so the two fields look and behave the same, and stay that way. */

export interface Pill {
  key: string
  label: string
  /** a hover hint; never needed to use the pill */
  title?: string
}

export default function TagPills({
  selected, available, onToggle, noneSelected,
}: {
  selected: Pill[]
  available: Pill[]
  onToggle: (key: string) => void
  noneSelected: string
}) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {selected.length === 0 && <span className="text-xs text-zinc-400">{noneSelected}</span>}
        {selected.map((p) => (
          <button
            key={p.key}
            type="button"
            title={p.title}
            onClick={() => onToggle(p.key)}
            className="inline-flex items-center gap-1 rounded-full border border-brand-200 bg-brand-50 px-2.5 py-0.5 text-xs font-medium text-brand-800 hover:bg-brand-100"
          >
            {p.label}
            <span aria-hidden className="text-brand-500">×</span>
          </button>
        ))}
      </div>
      {available.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {available.map((p) => (
            <button
              key={p.key}
              type="button"
              title={p.title}
              onClick={() => onToggle(p.key)}
              className="rounded-full border border-zinc-200 bg-white px-2.5 py-0.5 text-xs text-zinc-600 hover:border-zinc-300 hover:bg-zinc-50"
            >
              + {p.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
