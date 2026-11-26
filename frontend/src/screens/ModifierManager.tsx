import { useCallback, useEffect, useMemo, useState } from "react"
import { X, Plus, Trash2, Search, SlidersHorizontal, ChevronRight } from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { Button } from "../components/ui/button"
import { cn } from "../lib/utils"
import { cur } from "../lib/money"
import { t as translate, useUILanguage } from "../lib/i18n"

/* Choices: the groups a captain is asked about when a dish goes on the bill -
   milk, ice, extras. A group belongs to one outlet and lists the dishes that
   offer it; each choice adds a price and may take ingredients off the stock
   when the dish is fired. Reached from the Menu screen, like Recipes, because
   the generic resource screen has no child-table support. */

interface Outlet { name: string; outlet_name: string }
interface Dish { name: string; item_name: string; outlet: string; category: string | null }
interface Use { ingredient: string; qty: number | string; ingredient_name?: string | null; uom?: string | null }
interface Choice { name?: string; option_name: string; price: number | string; ingredients: Use[] }
interface Group {
  name: string
  group_name: string
  outlet: string
  outlet_name?: string
  required: 0 | 1
  multi: 0 | 1
  max_choices: number
  sort_order: number
  options: Choice[]
  items: string[]
}
interface Overview { groups: Group[]; dishes: Dish[]; outlets: Outlet[] }
interface IngredientRow { name: string; ingredient_name: string; uom: string }

interface Form {
  name?: string
  outlet: string
  group_name: string
  required: boolean
  multi: boolean
  max_choices: string
  sort_order: string
  options: Choice[]
  items: Set<string>
}

const blankChoice = (): Choice => ({ option_name: "", price: "", ingredients: [] })

export default function ModifierManager({ onClose, onChanged }: { onClose: () => void; onChanged?: () => void }) {
  useUILanguage()
  const [data, setData] = useState<Overview | null>(null)
  const [ings, setIngs] = useState<IngredientRow[] | null>(null)
  const [form, setForm] = useState<Form | null>(null)
  const [stockOpen, setStockOpen] = useState<number | null>(null)
  const [find, setFind] = useState("")
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const load = useCallback(() => {
    call<Overview>("kamra.menu_modifiers.modifier_overview", { property: getCurrentProperty() })
      .then(setData).catch((e) => setErr(serverError(e)))
  }, [])
  useEffect(() => {
    load()
    // the ingredient list needs stock rights; without them a choice simply cannot take stock
    call<IngredientRow[]>("kamra.inventory.ingredients", { property: getCurrentProperty() })
      .then(setIngs).catch(() => setIngs(null))
  }, [load])
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose()
    window.addEventListener("keydown", esc)
    return () => window.removeEventListener("keydown", esc)
  }, [onClose])

  const dishName = useMemo(() => new Map((data?.dishes ?? []).map((d) => [d.name, d.item_name])), [data])

  const startNew = () => {
    setSaved(false); setErr(null); setStockOpen(null); setFind("")
    setForm({
      outlet: data?.outlets.length === 1 ? data.outlets[0].name : "",
      group_name: "", required: false, multi: false, max_choices: "", sort_order: "0",
      options: [blankChoice()], items: new Set(),
    })
  }
  const edit = (g: Group) => {
    setSaved(false); setErr(null); setStockOpen(null); setFind("")
    setForm({
      name: g.name, outlet: g.outlet, group_name: g.group_name, required: !!g.required,
      multi: !!g.multi, max_choices: g.max_choices ? String(g.max_choices) : "",
      sort_order: String(g.sort_order ?? 0),
      options: g.options.map((o) => ({ ...o, ingredients: o.ingredients.map((u) => ({ ...u })) })),
      items: new Set(g.items),
    })
  }
  const patch = (p: Partial<Form>) => setForm((f) => (f ? { ...f, ...p } : f))
  const patchChoice = (i: number, p: Partial<Choice>) =>
    setForm((f) => f && { ...f, options: f.options.map((o, j) => (j === i ? { ...o, ...p } : o)) })

  const save = async () => {
    if (!form) return
    setBusy(true); setErr(null); setSaved(false)
    try {
      const r = await call<{ name: string }>("kamra.menu_modifiers.save_modifier_group", {
        name: form.name, outlet: form.outlet, group_name: form.group_name,
        required: form.required ? 1 : 0, multi: form.multi ? 1 : 0,
        max_choices: form.multi ? Number(form.max_choices) || 0 : 0,
        sort_order: Number(form.sort_order) || 0,
        options: form.options.map((o) => ({
          name: o.name, option_name: o.option_name, price: Number(o.price) || 0,
          ingredients: o.ingredients.filter((u) => u.ingredient)
            .map((u) => ({ ingredient: u.ingredient, qty: Number(u.qty) || 0 })),
        })),
        items: [...form.items],
      })
      setSaved(true)
      patch({ name: r.name })
      load(); onChanged?.()
    } catch (e) {
      setErr(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const remove = async () => {
    if (!form?.name) return
    const n = form.items.size
    if (!window.confirm(n
      ? translate("Delete {name}? {n} dish(es) will stop asking for it. Bills already written keep what was sold.", { name: form.group_name, n })
      : translate("Delete {name}?", { name: form.group_name }))) return
    setBusy(true); setErr(null)
    try {
      await call("kamra.menu_modifiers.delete_modifier_group", { name: form.name })
      setForm(null); load(); onChanged?.()
    } catch (e) {
      setErr(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const outletDishes = useMemo(() => {
    const q = find.trim().toLowerCase()
    return (data?.dishes ?? []).filter((d) => d.outlet === form?.outlet &&
      (!q || `${d.item_name} ${d.category ?? ""}`.toLowerCase().includes(q)))
  }, [data, form?.outlet, find])
  const toggleDish = (name: string, on: boolean) =>
    setForm((f) => {
      if (!f) return f
      const items = new Set(f.items)
      if (on) items.add(name); else items.delete(name)
      return { ...f, items }
    })
  const setMany = (names: string[], on: boolean) =>
    setForm((f) => {
      if (!f) return f
      const items = new Set(f.items)
      names.forEach((n) => (on ? items.add(n) : items.delete(n)))
      return { ...f, items }
    })

  const inputCls = "rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
  const byOutlet = useMemo(() => {
    const out = new Map<string, Group[]>()
    for (const g of data?.groups ?? []) out.set(g.outlet, [...(out.get(g.outlet) ?? []), g])
    return out
  }, [data])
  const outletLabel = (id: string) => data?.outlets.find((o) => o.name === id)?.outlet_name ?? id

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-900/30 p-4">
      <div className="flex h-[88vh] w-full max-w-5xl flex-col rounded-2xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-3">
          <div>
            <h2 className="text-lg font-bold text-zinc-800">{translate("Choices")}</h2>
            <p className="text-xs text-zinc-500">{translate("What the captain is asked when a dish goes on the bill: milk, ice, extras. Each choice can add to the price.")}</p>
          </div>
          <button onClick={onClose} aria-label={translate("Close")}
            className="grid size-9 place-items-center rounded-lg border border-zinc-300 text-zinc-500 hover:bg-zinc-100">
            <X className="size-4" />
          </button>
        </div>

        <div className="flex min-h-0 flex-1">
          <div className="flex w-72 shrink-0 flex-col border-r border-zinc-200">
            <div className="p-2">
              <Button className="w-full" onClick={startNew}><Plus className="size-4" />{translate("New group")}</Button>
            </div>
            <div className="flex-1 overflow-y-auto px-2 pb-2 pt-3">
              {data && data.groups.length === 0 && (
                <p className="px-2 py-6 text-center text-xs text-zinc-400">{translate("No groups yet.")}</p>
              )}
              {[...byOutlet.entries()].map(([outlet, list]) => (
                <div key={outlet} className="mb-2">
                  {byOutlet.size > 1 && (
                    <div className="px-2 pb-1 pt-2 text-[10px] font-bold uppercase tracking-wide text-zinc-400">{outletLabel(outlet)}</div>
                  )}
                  <ul className="space-y-1">
                    {list.map((g) => (
                      <li key={g.name}>
                        <button onClick={() => edit(g)}
                          className={cn("flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left hover:bg-zinc-50",
                            form?.name === g.name && "bg-brand-50 ring-1 ring-brand-200")}>
                          <div className="min-w-0 flex-1">
                            <div className="truncate text-sm font-semibold text-zinc-800">{g.group_name}</div>
                            <div className="truncate text-xs text-zinc-400">
                              {g.options.map((o) => o.option_name).join(" · ") || translate("No choices")}
                            </div>
                          </div>
                          <div className="flex shrink-0 flex-col items-end gap-0.5 text-[10px] font-bold">
                            {!!g.required && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-800">{translate("Required")}</span>}
                            <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-zinc-500">{translate("{n} dishes", { n: g.items.length })}</span>
                          </div>
                          <ChevronRight className="size-4 shrink-0 text-zinc-300" aria-hidden />
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>

          <div className="flex min-w-0 flex-1 flex-col">
            {!form ? (
              <div className="grid flex-1 place-items-center p-8 text-center text-sm text-zinc-400">
                <div>
                  <SlidersHorizontal className="mx-auto mb-2 size-6 text-zinc-300" aria-hidden />
                  {translate("Pick a group, or start a new one.")}
                </div>
              </div>
            ) : (
              <>
                <div className="flex-1 space-y-6 overflow-y-auto px-5 py-4">
                  {err && <div className="rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">{translate(err)}</div>}

                  <section className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <label className="block text-sm">
                      <span className="mb-1 block text-xs font-semibold text-zinc-500">{translate("Group")}</span>
                      <input className={cn(inputCls, "w-full")} value={form.group_name} maxLength={140}
                        placeholder={translate("Milk, Size, Extras…")}
                        onChange={(e) => patch({ group_name: e.target.value })} />
                    </label>
                    <label className="block text-sm">
                      <span className="mb-1 block text-xs font-semibold text-zinc-500">{translate("Outlet")}</span>
                      <select className={cn(inputCls, "w-full")} value={form.outlet} disabled={!!form.name}
                        onChange={(e) => patch({ outlet: e.target.value, items: new Set() })}>
                        <option value="">{translate("Pick…")}</option>
                        {(data?.outlets ?? []).map((o) => <option key={o.name} value={o.name}>{o.outlet_name}</option>)}
                      </select>
                    </label>
                    <label className="flex items-start gap-2 text-sm">
                      <input type="checkbox" className="mt-1 accent-brand-600" checked={form.required}
                        onChange={(e) => patch({ required: e.target.checked })} />
                      <span><span className="font-semibold text-zinc-800">{translate("Must choose")}</span>
                        <span className="block text-xs text-zinc-500">{translate("The dish cannot go on the bill until a choice is made.")}</span></span>
                    </label>
                    <div className="space-y-2">
                      <label className="flex items-start gap-2 text-sm">
                        <input type="checkbox" className="mt-1 accent-brand-600" checked={form.multi}
                          onChange={(e) => patch({ multi: e.target.checked })} />
                        <span><span className="font-semibold text-zinc-800">{translate("Several choices allowed")}</span>
                          <span className="block text-xs text-zinc-500">{translate("Off: pick one. On: tick as many as the limit allows.")}</span></span>
                      </label>
                      {form.multi && (
                        <label className="flex items-center gap-2 pl-6 text-sm">
                          <span className="text-xs font-semibold text-zinc-500">{translate("Most choices")}</span>
                          <input type="number" min="0" step="1" inputMode="numeric" className={cn(inputCls, "w-20")}
                            value={form.max_choices} placeholder="0"
                            onChange={(e) => patch({ max_choices: e.target.value })} />
                          <span className="text-xs text-zinc-400">{translate("0 = no limit")}</span>
                        </label>
                      )}
                    </div>
                    <label className="block text-sm">
                      <span className="mb-1 block text-xs font-semibold text-zinc-500">{translate("Order on the till")}</span>
                      <input type="number" step="1" inputMode="numeric" className={cn(inputCls, "w-28")}
                        value={form.sort_order} onChange={(e) => patch({ sort_order: e.target.value })} />
                      <span className="ml-2 text-xs text-zinc-400">{translate("Lowest first")}</span>
                    </label>
                  </section>

                  <section>
                    <h3 className="mb-2 text-sm font-bold text-zinc-800">{translate("Choices")}</h3>
                    <ul className="space-y-2">
                      {form.options.map((o, i) => (
                        <li key={o.name ?? `new-${i}`}>
                          <div className="flex flex-wrap items-center gap-2">
                            <input className={cn(inputCls, "min-w-0 flex-1")} value={o.option_name} maxLength={140}
                              aria-label={translate("Choice")} placeholder={translate("Oat milk")}
                              onChange={(e) => patchChoice(i, { option_name: e.target.value })} />
                            <label className="flex items-center gap-1 text-xs font-semibold text-zinc-500">
                              +{cur()}
                              <input type="number" min="0" step="any" inputMode="decimal" className={cn(inputCls, "w-28 tabular-nums")}
                                aria-label={translate("Adds to the price")} placeholder="0"
                                value={o.price} onChange={(e) => patchChoice(i, { price: e.target.value })} />
                            </label>
                            {ings && (
                              <button type="button" onClick={() => setStockOpen(stockOpen === i ? null : i)}
                                className={cn("rounded-lg border px-2 py-1.5 text-xs font-semibold",
                                  o.ingredients.length ? "border-emerald-300 bg-emerald-50 text-emerald-700" : "border-zinc-300 text-zinc-500 hover:bg-zinc-50")}>
                                {o.ingredients.length ? translate("Uses {n}", { n: o.ingredients.length }) : translate("Uses stock")}
                              </button>
                            )}
                            <button type="button" aria-label={translate("Remove choice")}
                              disabled={form.options.length <= 1}
                              onClick={() => setForm((f) => f && { ...f, options: f.options.filter((_, j) => j !== i) })}
                              className="grid size-8 place-items-center rounded-lg text-zinc-400 hover:bg-rose-50 hover:text-rose-600 disabled:opacity-30">
                              <Trash2 className="size-4" />
                            </button>
                          </div>
                          {ings && stockOpen === i && (
                            <div className="mt-2 space-y-1.5 rounded-lg bg-zinc-50 p-2">
                              <p className="text-xs text-zinc-500">{translate("What one of these takes off the outlet's stock when the dish is fired, on top of the dish's own recipe.")}</p>
                              {o.ingredients.map((u, k) => {
                                const meta = ings.find((x) => x.name === u.ingredient)
                                return (
                                  <div key={k} className="flex items-center gap-2">
                                    <select className={cn(inputCls, "min-w-0 flex-1")} value={u.ingredient}
                                      aria-label={translate("Ingredient")}
                                      onChange={(e) => patchChoice(i, { ingredients: o.ingredients.map((x, j) => j === k ? { ...x, ingredient: e.target.value } : x) })}>
                                      <option value="">{translate("Pick…")}</option>
                                      {ings.map((x) => <option key={x.name} value={x.name}>{x.ingredient_name} ({x.uom})</option>)}
                                    </select>
                                    <input type="number" min="0" step="any" inputMode="decimal" className={cn(inputCls, "w-24 tabular-nums")}
                                      aria-label={translate("Qty per dish")} value={u.qty}
                                      onChange={(e) => patchChoice(i, { ingredients: o.ingredients.map((x, j) => j === k ? { ...x, qty: e.target.value } : x) })} />
                                    <span className="w-10 text-xs text-zinc-400">{meta?.uom ?? u.uom ?? ""}</span>
                                    <button type="button" aria-label={translate("Remove line")}
                                      onClick={() => patchChoice(i, { ingredients: o.ingredients.filter((_, j) => j !== k) })}
                                      className="grid size-8 place-items-center rounded-lg text-zinc-400 hover:bg-rose-50 hover:text-rose-600">
                                      <Trash2 className="size-4" />
                                    </button>
                                  </div>
                                )
                              })}
                              <Button variant="outline" className="h-8 text-xs"
                                onClick={() => patchChoice(i, { ingredients: [...o.ingredients, { ingredient: "", qty: "" }] })}>
                                <Plus className="size-3.5" />{translate("Add ingredient")}
                              </Button>
                            </div>
                          )}
                        </li>
                      ))}
                    </ul>
                    <Button variant="outline" className="mt-2"
                      onClick={() => setForm((f) => f && { ...f, options: [...f.options, blankChoice()] })}>
                      <Plus className="size-4" />{translate("Add choice")}
                    </Button>
                  </section>

                  <section>
                    <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                      <h3 className="text-sm font-bold text-zinc-800">
                        {translate("Dishes that ask for it")} <span className="font-normal text-zinc-400">· {form.items.size}</span>
                      </h3>
                      <div className="flex items-center gap-2">
                        <div className="relative">
                          <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-zinc-400" />
                          <input value={find} onChange={(e) => setFind(e.target.value)} placeholder={translate("Find a dish…")}
                            className={cn(inputCls, "w-48 py-1 pl-8")} />
                        </div>
                        <Button variant="outline" className="h-8 text-xs" disabled={!outletDishes.length}
                          onClick={() => setMany(outletDishes.map((d) => d.name), true)}>{translate("Tick all shown")}</Button>
                        <Button variant="outline" className="h-8 text-xs" disabled={!outletDishes.length}
                          onClick={() => setMany(outletDishes.map((d) => d.name), false)}>{translate("Clear shown")}</Button>
                      </div>
                    </div>
                    {!form.outlet ? (
                      <p className="text-xs text-zinc-400">{translate("Pick the outlet to see its dishes.")}</p>
                    ) : outletDishes.length === 0 ? (
                      <p className="text-xs text-zinc-400">{translate("No dishes found.")}</p>
                    ) : (
                      <ul className="grid max-h-64 grid-cols-1 gap-x-4 overflow-y-auto rounded-xl border border-zinc-200 p-2 sm:grid-cols-2">
                        {outletDishes.map((d) => (
                          <li key={d.name}>
                            <label className="flex cursor-pointer items-center gap-2 rounded px-1.5 py-1 text-sm hover:bg-zinc-50">
                              <input type="checkbox" className="accent-brand-600" checked={form.items.has(d.name)}
                                onChange={(e) => toggleDish(d.name, e.target.checked)} />
                              <span className="min-w-0 flex-1 truncate">{d.item_name}</span>
                              <span className="shrink-0 text-xs text-zinc-400">{d.category}</span>
                            </label>
                          </li>
                        ))}
                      </ul>
                    )}
                    {[...form.items].some((n) => !dishName.has(n)) && (
                      <p className="mt-1 text-xs text-amber-700">{translate("Some dishes that ask for this group are no longer on the menu.")}</p>
                    )}
                  </section>
                </div>

                <div className="flex items-center gap-3 border-t border-zinc-200 p-4">
                  {form.name && (
                    <Button variant="outline" className="text-rose-700" disabled={busy} onClick={remove}>
                      <Trash2 className="size-4" />{translate("Delete group")}
                    </Button>
                  )}
                  {saved && <span className="text-sm font-medium text-emerald-600" role="status">{translate("Saved")}</span>}
                  <Button className="ml-auto h-11 px-6" disabled={busy || !form.group_name.trim() || !form.outlet} onClick={save}>
                    {translate("Save group")}
                  </Button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
