/*  The choices a dish asks for (milk, ice, extras) - a sheet on the till.

    The server owns the rules and the prices: it judges what is sent against the
    dish's own groups (kamra.menu_modifiers.resolve). This sheet only makes the
    right picks easy and says what is still missing, so a captain is never sent
    back by an error after tapping Send. */

import { useEffect, useMemo, useState } from "react"
import { Check, X } from "lucide-react"
import { Button } from "../../components/ui/button"
import { cn } from "../../lib/utils"
import { cur, fmtAmount } from "../../lib/money"
import { useT } from "../../lib/i18n"

export interface ModOption { name: string; option_name: string; price: number }
export interface ModGroup {
  name: string
  group_name: string
  required: 0 | 1
  multi: 0 | 1
  /** 0 = no limit (several choices allowed) */
  max_choices: number
  options: ModOption[]
}

/** What the picked choices add to ONE of the dish. */
export function extrasOf(groups: ModGroup[], picked: string[]): number {
  let sum = 0
  for (const g of groups) for (const o of g.options) if (picked.includes(o.name)) sum += Number(o.price) || 0
  return sum
}

/** The groups still to be answered: a compulsory group with nothing picked. */
export function missingGroups(groups: ModGroup[], picked: string[]): ModGroup[] {
  return groups.filter((g) => g.required && !g.options.some((o) => picked.includes(o.name)))
}

/** The picks that belong to these groups, in the order the groups list them: the id list the server is sent. */
export function orderedPicks(groups: ModGroup[], picked: string[]): string[] {
  return groups.flatMap((g) => g.options.filter((o) => picked.includes(o.name)).map((o) => o.name))
}

export default function ModifierSheet({
  title, price, groups, initial, confirmLabel, onConfirm, onClose,
}: {
  title: string
  /** the dish's own price, before the choices */
  price: number
  groups: ModGroup[]
  initial: string[]
  confirmLabel: string
  onConfirm: (picked: string[]) => void
  onClose: () => void
}) {
  const { t } = useT()
  const [picked, setPicked] = useState<string[]>(() => orderedPicks(groups, initial))
  const missing = useMemo(() => missingGroups(groups, picked), [groups, picked])
  const total = price + extrasOf(groups, picked)

  const toggle = (g: ModGroup, o: ModOption) => setPicked((prev) => {
    const on = prev.includes(o.name)
    if (g.multi) {
      if (on) return prev.filter((x) => x !== o.name)
      const have = g.options.filter((x) => prev.includes(x.name)).length
      return g.max_choices && have >= g.max_choices ? prev : [...prev, o.name]
    }
    const others = prev.filter((x) => !g.options.some((y) => y.name === x))
    // a single choice swaps; tapping the one that is on clears it, unless the group is compulsory
    return on ? (g.required ? prev : others) : [...others, o.name]
  })

  const ready = missing.length === 0
  const submit = () => { if (ready) onConfirm(orderedPicks(groups, picked)) }

  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", key)
    return () => window.removeEventListener("keydown", key)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-zinc-900/40 p-0 sm:items-center sm:p-4"
      role="dialog" aria-modal="true" aria-label={title}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="flex max-h-[92vh] w-full max-w-lg flex-col rounded-t-2xl bg-white shadow-2xl sm:rounded-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-zinc-200 px-5 py-3">
          <div className="min-w-0">
            <h2 className="truncate text-lg font-bold text-zinc-900">{title}</h2>
            <p className="text-sm tabular-nums text-zinc-500">{cur()}{fmtAmount(price)}</p>
          </div>
          <button type="button" onClick={onClose} aria-label={t("Close")}
            className="grid size-9 shrink-0 place-items-center rounded-lg border border-zinc-300 text-zinc-500 hover:bg-zinc-100">
            <X className="size-4" />
          </button>
        </div>

        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-5 py-4">
          {groups.map((g) => {
            const have = g.options.filter((o) => picked.includes(o.name)).length
            const full = !!g.multi && g.max_choices > 0 && have >= g.max_choices
            const rule = g.multi
              ? (g.max_choices ? t("Choose up to {n}", { n: g.max_choices }) : t("Choose any"))
              : t("Choose one")
            return (
              <fieldset key={g.name}>
                <legend className="mb-2 flex w-full flex-wrap items-baseline gap-x-2">
                  <span className="text-sm font-bold text-zinc-900">{g.group_name}</span>
                  <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide",
                    g.required ? "bg-amber-100 text-amber-800" : "bg-zinc-100 text-zinc-500")}>
                    {g.required ? t("Required") : t("Optional")}
                  </span>
                  <span className="text-xs text-zinc-400">{rule}</span>
                </legend>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2" role={g.multi ? "group" : "radiogroup"}>
                  {g.options.map((o) => {
                    const on = picked.includes(o.name)
                    const blocked = !on && full
                    return (
                      <button key={o.name} type="button" role={g.multi ? "checkbox" : "radio"}
                        aria-checked={on} disabled={blocked}
                        onClick={() => toggle(g, o)}
                        className={cn(
                          "flex min-h-12 items-center justify-between gap-2 rounded-xl border-2 px-3 py-2 text-left text-sm font-semibold transition",
                          on ? "border-brand-600 bg-brand-50 text-brand-800"
                            : "border-zinc-200 bg-white text-zinc-800 hover:border-brand-300",
                          blocked && "cursor-not-allowed opacity-40")}>
                        <span className="flex min-w-0 items-center gap-2">
                          <span className={cn("grid size-5 shrink-0 place-items-center border-2",
                            g.multi ? "rounded" : "rounded-full",
                            on ? "border-brand-600 bg-brand-600 text-white" : "border-zinc-300")}>
                            {on && <Check className="size-3" aria-hidden />}
                          </span>
                          <span className="truncate">{o.option_name}</span>
                        </span>
                        {o.price > 0 && (
                          <span className="shrink-0 text-xs font-bold tabular-nums text-zinc-600">
                            +{cur()}{fmtAmount(o.price)}
                          </span>
                        )}
                      </button>
                    )
                  })}
                </div>
              </fieldset>
            )
          })}
        </div>

        <div className="space-y-2 border-t border-zinc-200 px-5 py-3">
          {/* the row keeps its height when it empties, so the button does not jump under a finger */}
          <p className="min-h-4 text-xs font-medium text-amber-700" role="status">
            {!ready && t("Choose {group} to continue.", { group: missing.map((g) => g.group_name).join(", ") })}
          </p>
          <Button className="h-12 w-full text-base" disabled={!ready} onClick={submit}>
            {confirmLabel} · {cur()}{fmtAmount(total)}
          </Button>
        </div>
      </div>
    </div>
  )
}
