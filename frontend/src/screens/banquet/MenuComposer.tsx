/*  Choosing the food.

    A package says "one soup of two, three starters of six". The old way
    was to write the choices on the back of the quote and hope the kitchen
    read the same sheet. Here the customer picks, the picks are recorded,
    the menu line re-costs itself from the chosen dishes' recipes, and any
    upgrade lands on the quote as its own visible line - because an
    upgrade is a price change and shouldn't hide inside a package rate.

    The card that prints afterwards is what they chose, not what the
    catalogue could have offered. */

import { useCallback, useEffect, useMemo, useState } from "react"
import { Check, ChefHat, Flame, Sparkles } from "lucide-react"

import { banquet, type DishOption, type MenuChoices } from "../../lib/api"
import { serverError } from "../../lib/resource"
import { Button } from "../../components/ui/button"
import { Sheet } from "../../components/ui/sheet"
import { Empty, ErrorNote, inr } from "./shared"
import { t as translate, useUILanguage } from "../../lib/i18n"

type Pick = {
  course: string
  dish: string
  dish_name: string
  supplement_per_pax: number
  note?: string
}

/** Veg / non-veg reads at a glance - the first thing anyone checks. */
const DOT: Record<string, string> = {
  Veg: "bg-emerald-500",
  Vegan: "bg-emerald-600",
  Jain: "bg-emerald-400",
  Egg: "bg-amber-500",
  "Non-Veg": "bg-rose-500",
}

export default function MenuComposer({
  fn,
  menu,
  pax,
  onClose,
  onSaved,
}: {
  fn: string
  menu: string
  pax: number
  onClose: () => void
  onSaved: () => void
}) {
  useUILanguage()
  const [data, setData] = useState<MenuChoices | null>(null)
  const [picks, setPicks] = useState<Pick[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    banquet
      .menuChoices(fn, menu)
      .then((d) => {
        setData(d)
        // start from what's already chosen; if nothing is, seed the
        // package's own defaults so the sheet is never blank
        const seeded: Pick[] = []
        for (const c of d.courses) {
          const already = c.options.filter((o) => o.chosen)
          const source = already.length
            ? already
            : c.options.filter((o) => o.is_default)
          for (const o of source)
            seeded.push({
              course: c.course,
              dish: o.dish,
              dish_name: o.dish_name,
              supplement_per_pax: o.supplement_per_pax,
            })
        }
        setPicks(seeded)
      })
      .catch((e) => setError(serverError(e)))
  }, [fn, menu])
  useEffect(load, [load])

  const chosenIn = (course: string) => picks.filter((p) => p.course === course)
  const isPicked = (course: string, dish: string) =>
    picks.some((p) => p.course === course && p.dish === dish)

  function toggle(course: string, limit: number, o: DishOption) {
    setPicks((prev) => {
      const here = prev.filter((p) => p.course === course)
      if (here.some((p) => p.dish === o.dish))
        return prev.filter((p) => !(p.course === course && p.dish === o.dish))
      // a course that allows exactly one swaps rather than stacking - 
      // clicking the second soup should replace the first, not error
      const next =
        limit === 1
          ? prev.filter((p) => p.course !== course)
          : limit && here.length >= limit
            ? prev.filter((p) => !(p.course === course && p.dish === here[0].dish))
            : prev
      return [
        ...next,
        {
          course,
          dish: o.dish,
          dish_name: o.dish_name,
          supplement_per_pax: o.supplement_per_pax,
        },
      ]
    })
  }

  const totals = useMemo(() => {
    if (!data) return { cost: 0, supplement: 0 }
    const byDish = new Map<string, DishOption>()
    for (const c of data.courses) for (const o of c.options) byDish.set(o.dish, o)
    let cost = 0
    let supplement = 0
    for (const p of picks) {
      const o = byDish.get(p.dish)
      if (!o) continue
      cost += o.cost_per_portion * (o.portion_per_pax || 1)
      supplement += o.supplement_per_pax || 0
    }
    return { cost, supplement }
  }, [picks, data])

  const incomplete = (data?.courses ?? []).filter(
    (c) => c.choice_of && chosenIn(c.course).length < c.choice_of,
  )

  return (
    <Sheet
      title={(data ? translate("Choose the {v0}", { v0: String(data.menu_name) }) : translate("Choose the menu"))}
      description={translate("What they pick is what the kitchen cooks and what the card prints.")}
      onClose={onClose}
      wide
      footer={
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm">
            {incomplete.length > 0 ? (
              <span className="text-amber-700">{translate("Still to choose:")}{" "}
                {incomplete
                  .map(
                    (c) =>
                      `${translate(c.course)} (${chosenIn(c.course).length}/${c.choice_of})`,
                  )
                  .join(", ")}
              </span>
            ) : (
              <span className="text-zinc-500">
                {picks.length}{translate(" dish")}{picks.length === 1 ? "" : translate("es")} ·{" "}
                {inr(totals.cost)}{translate("/pax to make")}{totals.supplement > 0 && (
                  <span className="text-amber-700">
                    {" "}
                    · +{inr(totals.supplement)}{translate("/pax upgrades")}</span>
                )}
              </span>
            )}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={onClose}>{translate("Cancel")}</Button>
            <Button
              disabled={busy || !picks.length}
              onClick={async () => {
                setBusy(true)
                setError(null)
                try {
                  await banquet.composeMenu(fn, menu, picks)
                  onSaved()
                  onClose()
                } catch (e) {
                  setError(serverError(e))
                } finally {
                  setBusy(false)
                }
              }}
            >{translate("Save the menu")}</Button>
          </div>
        </div>
      }
    >
      <ErrorNote error={error} />
      {!data ? (
        <Empty>{translate("Loading…")}</Empty>
      ) : data.courses.every((c) => c.options.length === 0) ? (
        <Empty>{translate("This package has no dishes attached yet - add them to its courses under Menus & Services, and the customer can start choosing.")}</Empty>
      ) : (
        <div className="space-y-5">
          {data.courses.map((c) => {
            const taken = chosenIn(c.course).length
            const done = !c.choice_of || taken >= c.choice_of
            return (
              <section key={translate(c.course)}>
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="flex items-center gap-1.5 text-sm font-semibold">
                    {translate(c.course)}
                    {c.is_live_counter && (
                      <span className="inline-flex items-center gap-1 rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">
                        <Flame className="size-3" />{translate("live")}</span>
                    )}
                  </h3>
                  <span
                    className={
                      "text-xs " + (done ? "text-emerald-600" : "text-amber-700")
                    }
                  >
                    {c.choice_of
                      ? translate("choose {v0} · {v1} picked", { v0: String(c.choice_of), v1: String(taken) })
                      : translate("{v0} picked", { v0: String(taken) })}
                  </span>
                </div>

                {c.options.length === 0 ? (
                  <p className="rounded-lg bg-zinc-50 px-3 py-2 text-sm text-zinc-500">
                    {c.free_text || translate("Nothing listed for this course.")}
                  </p>
                ) : (
                  <div className="grid gap-2 sm:grid-cols-2">
                    {c.options.map((o) => {
                      const on = isPicked(c.course, o.dish)
                      return (
                        <button
                          key={o.dish}
                          onClick={() => toggle(c.course, c.choice_of, o)}
                          className={
                            "flex items-start gap-2.5 rounded-lg border px-3 py-2 text-left transition-all " +
                            (on
                              ? "border-brand-600 bg-brand-50 ring-1 ring-brand-600/20"
                              : "border-zinc-200 hover:border-zinc-300 hover:bg-zinc-50")
                          }
                        >
                          <span
                            className={
                              "mt-1 size-2.5 shrink-0 rounded-full " +
                              (DOT[o.food_type ?? ""] ?? "bg-zinc-300")
                            }
                            title={translate(o.food_type ?? "")}
                          />
                          <span className="min-w-0 flex-1">
                            <span className="flex items-center gap-1.5 font-medium">
                              {o.dish_name}
                              {o.is_default && !on && (
                                <span className="text-[10px] font-normal text-zinc-400">{translate("standard")}</span>
                              )}
                            </span>
                            <span className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-zinc-400">
                              {o.kitchen && (
                                <span className="inline-flex items-center gap-1">
                                  <ChefHat className="size-3" />
                                  {o.kitchen}
                                </span>
                              )}
                              {o.allergens && (
                                <span className="text-amber-700">
                                  {o.allergens}
                                </span>
                              )}
                              {o.supplement_per_pax > 0 && (
                                <span className="inline-flex items-center gap-0.5 font-medium text-amber-700">
                                  <Sparkles className="size-3" />
                                  +{inr(o.supplement_per_pax)}{translate("/pax")}</span>
                              )}
                            </span>
                          </span>
                          {on && (
                            <Check className="mt-0.5 size-4 shrink-0 text-brand-600" />
                          )}
                        </button>
                      )
                    })}
                  </div>
                )}
              </section>
            )
          })}

          {pax > 0 && (
            <div className="rounded-xl bg-zinc-50 px-4 py-3 text-sm">
              <p className="text-zinc-500">{translate("At ")}{pax}{translate(" pax this menu costs")}{" "}
                <span className="font-semibold text-zinc-900">
                  {inr(totals.cost * pax)}
                </span>{" "}{translate("to produce")}{totals.supplement > 0 && (
                  <>{translate(", and the upgrades add")}{" "}
                    <span className="font-semibold text-amber-700">
                      {inr(totals.supplement * pax)}
                    </span>{" "}{translate("to the quote")}</>
                )}
                .
              </p>
            </div>
          )}
        </div>
      )}
    </Sheet>
  )
}
