import { useCallback, useEffect, useState } from "react"
import { X, Plus, Trash2, Search, CircleAlert } from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { Button } from "../components/ui/button"
import { cn } from "../lib/utils"
import { t as translate, useUILanguage } from "../lib/i18n"
import { cur } from "../lib/money"
import { fmtCost, recipeTotals } from "../lib/recipeCost"
import { useAuth } from "../lib/auth"
import { TrackStockForm, TrackedStock } from "../components/TrackStock"

/* Recipes: what a dish takes off the shelf when it is fired.
   Deliberately reachable from the Menu screen rather than bolted into the
   generic ResourceScreen, which has no child-table support - teaching it any
   would be a framework-sized detour to serve one editor. */

interface Dish {
  name: string
  item_name: string
  outlet: string
  outlet_name: string
  category: string | null
  available: 0 | 1
  lines: number
  price: number
  cost: number | null
  margin_pct: number | null
  tracked: boolean
}
interface IngredientRow {
  name: string
  ingredient_name: string
  uom: string
  category: string | null
  cost_per_unit: number | null
  is_active: 0 | 1
}
interface MenuRecipe {
  recipe: RecipeLine[]
  price?: number
  stock_ingredient?: string | null
  stock_name?: string
  stock_uom?: string
  stock_on_hand?: number
}
const STOCK_ROLES = ["Finance", "F&B Manager", "Hotel Admin", "System Manager", "Administrator"]
interface RecipeLine {
  ingredient: string
  ingredient_name?: string
  uom?: string
  qty: number | string
  note?: string | null
  qty_on_hand?: number | null
}

export default function RecipeManager({ onClose }: { onClose: () => void }) {
  useUILanguage()
  const [dishes, setDishes] = useState<Dish[]>([])
  const [ings, setIngs] = useState<IngredientRow[]>([])
  const [picked, setPicked] = useState<Dish | null>(null)
  const [lines, setLines] = useState<RecipeLine[]>([])
  // the menu price comes only to people who can see costs; without it, none show
  const [price, setPrice] = useState<number | null>(null)
  const [q, setQ] = useState("")
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [own, setOwn] = useState<MenuRecipe | null>(null)
  const [tracking, setTracking] = useState(false)
  const { allowed } = useAuth()
  const canTrack = allowed("Menu Item", "edit_menu", STOCK_ROLES) && allowed("Ingredient", "manage_stock", STOCK_ROLES)

  const loadIngredients = useCallback(() => {
    // inactive ones too: a recipe may still hold one, and it still costs
    call<IngredientRow[]>("kamra.inventory.ingredients", { property: getCurrentProperty(), active_only: 0 })
      .then(setIngs).catch(() => {})
  }, [])

  const loadDishes = useCallback(() => {
    call<Dish[]>("kamra.inventory.recipe_overview", { property: getCurrentProperty() })
      .then(setDishes).catch((e) => setErr(String(e)))
  }, [])

  useEffect(() => {
    loadDishes()
    loadIngredients()
  }, [loadDishes, loadIngredients])

  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose()
    window.addEventListener("keydown", esc)
    return () => window.removeEventListener("keydown", esc)
  }, [onClose])

  const open = useCallback((d: Dish) => {
    setPicked(d); setSaved(false); setErr(null); setLines([]); setPrice(null); setOwn(null); setTracking(false)
    call<MenuRecipe>("kamra.inventory.menu_recipe", { menu_item: d.name })
      .then((r) => { setOwn(r); setLines(r.recipe); setPrice(r.price ?? null) }).catch((e) => setErr(String(e)))
  }, [])
  const reopen = () => { if (picked) open(picked); loadDishes(); loadIngredients() }
  const tracked = !!own?.stock_ingredient
  // an item can take its own stock while it has no recipe, or one that is just 1 x something
  const saved1 = own?.recipe.length === 1 && Number(own.recipe[0].qty) === 1 ? own.recipe[0].ingredient : null
  const canStart = canTrack && !!own && !tracked && (own.recipe.length === 0 || !!saved1)

  const save = useCallback(async () => {
    if (!picked) return
    setBusy(true); setErr(null)
    try {
      await call("kamra.inventory.save_recipe", {
        menu_item: picked.name,
        rows: lines
          .filter((l) => l.ingredient && Number(l.qty) > 0)
          .map((l) => ({ ingredient: l.ingredient, qty: Number(l.qty), note: l.note ?? null })),
      })
      setSaved(true)
      loadDishes()
    } catch (e) {
      setErr(e instanceof Error ? translate(e.message) : String(e))
    } finally {
      setBusy(false)
    }
  }, [picked, lines, loadDishes])

  const totals = price === null ? null : recipeTotals(lines, ings, price)

  const shown = q
    ? dishes.filter((d) => `${d.item_name} ${d.outlet_name} ${d.category ?? ""}`
        .toLowerCase().includes(q.toLowerCase()))
    : dishes

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-900/30 p-4">
      <div className="flex h-[85vh] w-full max-w-5xl flex-col rounded-2xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-3">
          <div>
            <h2 className="text-lg font-bold text-zinc-800">{translate("Recipes")}</h2>
            <p className="text-xs text-zinc-500">{translate("What each dish takes off its outlet's stock: when the kitchen fires it, or when the bill closes if it was never sent.")}</p>
          </div>
          <button onClick={onClose} aria-label={translate("Close")}
            className="grid size-9 place-items-center rounded-lg border border-zinc-300 text-zinc-500 hover:bg-zinc-100">
            <X className="size-4" />
          </button>
        </div>

        <div className="flex min-h-0 flex-1">
          <div className="flex w-72 shrink-0 flex-col border-r border-zinc-200">
            <div className="relative p-2">
              <Search className="absolute left-4 top-1/2 size-4 -translate-y-1/2 text-zinc-400" />
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={translate("Find a dish…")}
                className="w-full rounded-lg border border-zinc-300 py-1.5 pl-8 pr-2 text-sm" />
            </div>
            <ul className="flex-1 overflow-y-auto px-2 pb-2">
              {shown.map((d) => (
                <li key={d.name}>
                  <button onClick={() => open(d)}
                    className={cn("w-full rounded-lg px-2 py-1.5 text-left hover:bg-zinc-50",
                      picked?.name === d.name && "bg-brand-50 ring-1 ring-brand-200")}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-semibold text-zinc-800">{d.item_name}</span>
                      <span className={cn("shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold",
                        d.lines ? "bg-emerald-50 text-emerald-700" : "bg-zinc-100 text-zinc-400")}>
                        {d.lines || "-"}
                      </span>
                    </div>
                    <div className="truncate text-xs text-zinc-400">{d.outlet_name}
                      {d.tracked && <span className="ml-1 text-emerald-700">· {translate("own stock")}</span>}
                    </div>
                    {d.lines > 0 && (
                      <div className={cn("truncate text-xs tabular-nums",
                        d.cost === null ? "text-amber-700"
                          : d.cost > d.price ? "text-rose-600" : "text-zinc-500")}>
                        {d.cost === null ? translate("cost not complete")
                          : d.margin_pct === null ? translate("cost {cost}", { cost: fmtCost(d.cost) })
                            : translate("cost {cost} · margin {pct}%", { cost: fmtCost(d.cost), pct: d.margin_pct.toFixed(1) })}
                      </div>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div className="flex min-w-0 flex-1 flex-col">
            {!picked ? (
              <div className="grid flex-1 place-items-center p-8 text-center text-sm text-zinc-400">{translate("Pick a dish to give it a recipe.")}</div>
            ) : (
              <>
                <div className="border-b border-zinc-100 px-5 py-3">
                  <div className="text-base font-bold text-zinc-800">{picked.item_name}</div>
                  <div className="text-xs text-zinc-500">{picked.outlet_name}</div>
                </div>

                <div className="flex-1 overflow-y-auto px-5 py-3">
                  {err && (
                    <div className="mb-3 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                      {translate(err)}
                    </div>
                  )}
                  {tracked && own ? (
                    <TrackedStock menuItem={picked.name} name={own.stock_name ?? ""} uom={own.stock_uom ?? ""}
                      onHand={own.stock_on_hand ?? 0} canChange={canTrack} onDone={reopen} />
                  ) : lines.length === 0 ? (
                    <div className="rounded-xl border border-dashed border-zinc-300 p-6 text-center">
                      <CircleAlert className="mx-auto mb-2 size-5 text-zinc-300" />
                      <p className="text-sm font-semibold text-zinc-600">{translate("No recipe")}</p>
                      <p className="mt-0.5 text-xs text-zinc-400">{translate("This dish never touches inventory. That's a valid choice - most menus only ever cost their big movers.")}</p>
                    </div>
                  ) : (
                    <table className="w-full text-sm">
                      <thead className="text-left text-xs uppercase text-zinc-400">
                        <tr>
                          <th className="pb-1">{translate("Ingredient")}</th>
                          <th className="pb-1">{translate("Qty per dish")}</th>
                          <th className="pb-1">{translate("On hand")}</th>
                          {totals && <th className="pb-1 pr-2 text-right">{translate("Cost")}</th>}
                          <th className="pb-1"></th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-zinc-100">
                        {lines.map((l, i) => {
                          const meta = ings.find((x) => x.name === l.ingredient)
                          return (
                            <tr key={i}>
                              <td className="py-1.5 pr-2">
                                <select value={l.ingredient}
                                  onChange={(e) => setLines(lines.map((x, j) =>
                                    j === i ? { ...x, ingredient: e.target.value } : x))}
                                  className="w-full rounded border border-zinc-300 px-2 py-1 text-sm">
                                  <option value="">{translate("Pick…")}</option>
                                  {ings.filter((x) => x.is_active || x.name === l.ingredient).map((x) => (
                                    <option key={x.name} value={x.name}>
                                      {x.ingredient_name} ({x.uom})
                                    </option>
                                  ))}
                                </select>
                              </td>
                              <td className="py-1.5 pr-2 whitespace-nowrap">
                                <input type="number" min="0" step="any" inputMode="decimal"
                                  value={l.qty}
                                  onChange={(e) => setLines(lines.map((x, j) =>
                                    j === i ? { ...x, qty: e.target.value } : x))}
                                  className="w-24 rounded border border-zinc-300 px-2 py-1 tabular-nums" />
                                <span className="ml-1 text-xs text-zinc-400">
                                  {meta?.uom ?? l.uom ?? ""}
                                </span>
                              </td>
                              <td className="py-1.5 tabular-nums text-zinc-400">
                                {l.qty_on_hand === null || l.qty_on_hand === undefined
                                  ? "-"
                                  : <span className={cn(l.qty_on_hand < 0 && "font-bold text-rose-600")}>
                                      {l.qty_on_hand}
                                    </span>}
                              </td>
                              {totals && (
                                <td className="py-1.5 pr-2 text-right tabular-nums text-zinc-600">
                                  {totals.lines[i] !== null ? fmtCost(totals.lines[i] as number)
                                    : meta && Number(l.qty) > 0
                                      ? <span className="text-xs text-amber-700">{translate("no cost")}</span>
                                      : "-"}
                                </td>
                              )}
                              <td className="py-1.5 text-right">
                                <button aria-label={translate("Remove line")}
                                  onClick={() => setLines(lines.filter((_, j) => j !== i))}
                                  className="grid size-8 place-items-center rounded-lg text-zinc-400 hover:bg-rose-50 hover:text-rose-600">
                                  <Trash2 className="size-4" />
                                </button>
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  )}

                  {!tracked && (
                    <Button variant="outline" className="mt-3"
                      onClick={() => setLines([...lines, { ingredient: "", qty: "" }])}>
                      <Plus className="size-4" />{translate("Add ingredient")}</Button>
                  )}
                  {canStart && !tracking && (
                    <Button variant="outline" className="ml-2 mt-3" onClick={() => setTracking(true)}>
                      {translate("Track this item's own stock")}</Button>
                  )}
                  {canStart && tracking && (
                    <TrackStockForm key={picked.name} menuItem={picked.name} itemName={picked.item_name}
                      ingredients={ings.filter((x) => x.is_active || x.name === saved1)} adopt={saved1}
                      onDone={reopen} onClose={() => setTracking(false)} />
                  )}

                  {totals && lines.length > 0 && (
                    <div className="mt-4 rounded-xl border border-zinc-200 px-4 py-3 text-sm">
                      <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 tabular-nums">
                        <dt className="text-zinc-500">{translate("Cost per portion")}</dt>
                        <dd className="text-right font-semibold text-zinc-800">
                          {totals.cost === null ? "-" : `${cur()}${fmtCost(totals.cost)}`}
                        </dd>
                        <dt className="text-zinc-500">{translate("Menu price")}
                          <span className="ml-1 text-xs text-zinc-400">{translate("before tax and service charge")}</span>
                        </dt>
                        <dd className="text-right text-zinc-800">{`${cur()}${fmtCost(price ?? 0)}`}</dd>
                        <dt className="text-zinc-500">{translate("Margin")}</dt>
                        <dd className={cn("text-right font-semibold",
                          totals.margin !== null && totals.margin < 0 ? "text-rose-600" : "text-zinc-800")}>
                          {totals.margin === null ? "-"
                            : `${cur()}${fmtCost(totals.margin)}${totals.pct === null ? "" : ` · ${totals.pct.toFixed(1)}%`}`}
                        </dd>
                      </dl>
                      {totals.missing.length > 0 && (
                        <p className="mt-2 text-xs text-amber-700">
                          {translate("Add a cost for: {names}", { names: totals.missing.join(", ") })}
                        </p>
                      )}
                    </div>
                  )}

                  <p className="mt-4 text-xs text-zinc-400">{translate("Quantities are per one dish, in each ingredient's own unit - there are no conversions. Editing a recipe never rewrites history: past consumption was recorded at the quantity in force when it was fired.")}</p>
                </div>

                {!tracked && (
                  <div className="flex items-center gap-3 border-t border-zinc-200 p-4">
                    {saved && <span className="text-sm font-medium text-emerald-600">{translate("Saved")}</span>}
                    <Button className="ml-auto h-11 px-6" disabled={busy} onClick={save}>{translate("Save recipe")}</Button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
