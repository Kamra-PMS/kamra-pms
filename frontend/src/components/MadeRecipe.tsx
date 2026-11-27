/*  The batch recipe of an ingredient made here, in the ingredient form: what one
    batch is made from, and what that makes a unit cost. Only bought ingredients
    are offered; the server checks the same (kamra Ingredient). */

import { useEffect, useState } from "react"
import { Plus, X } from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { recipeTotals, type CostIngredient } from "../lib/recipeCost"
import { fmtUnitCost } from "../lib/stockCost"
import { cur } from "../lib/money"
import { t as translate, useUILanguage } from "../lib/i18n"
import { Button } from "./ui/button"

interface Line { name?: string; ingredient: string; qty: number | string }
interface Part extends CostIngredient { uom: string; is_active: 0 | 1; is_made: 0 | 1 }

const box = "rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-sm"

export default function MadeRecipe({ value, onChange, draft, recordName }: {
  value: unknown
  onChange: (lines: Line[]) => void
  /** the form so far: batch size and unit */
  draft: Record<string, unknown>
  recordName?: string
}) {
  useUILanguage()
  const [parts, setParts] = useState<Part[]>([])
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    call<Part[]>("kamra.inventory.ingredients", { property: getCurrentProperty(), active_only: 0 })
      .then(setParts).catch((e) => setError(serverError(e)))
  }, [])
  const lines = (Array.isArray(value) ? value : []) as Line[]
  const edit = (i: number, change: Partial<Line>) =>
    onChange(lines.map((line, n) => (n === i ? { ...line, ...change } : line)))

  const batch = Number(draft.batch_qty ?? 0)
  const totals = recipeTotals(lines, parts, 0, (part, made) => translate("{part} (in {made})", { part, made }))
  const unitCost = totals.cost !== null && batch > 0 ? totals.cost / batch : null

  return (
    <div className="space-y-2">
      {lines.map((line, i) => {
        const picked = parts.find((p) => p.name === line.ingredient)
        const options = parts.filter((p) =>
          p.name === line.ingredient || (!p.is_made && !!p.is_active && p.name !== recordName))
        return (
          <div key={line.name ?? i} className="flex items-center gap-2">
            <select className={`${box} min-w-0 flex-1`} value={line.ingredient} aria-label={translate("Ingredient")}
              onChange={(e) => edit(i, { ingredient: e.target.value })}>
              <option value="">{translate("Pick an ingredient…")}</option>
              {options.map((p) => <option key={p.name} value={p.name}>{p.ingredient_name}</option>)}
            </select>
            <input type="number" min="0" step="any" inputMode="decimal" className={`${box} w-28 tabular-nums`}
              aria-label={`${picked?.ingredient_name ?? translate("Ingredient")} · ${translate("Quantity")}`}
              value={line.qty} onChange={(e) => edit(i, { qty: e.target.value })} />
            <span className="w-12 truncate text-sm text-zinc-400">{picked?.uom}</span>
            <button type="button" aria-label={translate("Remove")}
              onClick={() => onChange(lines.filter((_, n) => n !== i))}
              className="grid size-8 place-items-center rounded-lg text-zinc-400 hover:bg-zinc-100 hover:text-rose-600">
              <X className="size-4" />
            </button>
          </div>
        )
      })}
      <Button type="button" variant="outline" onClick={() => onChange([...lines, { ingredient: "", qty: "" }])}>
        <Plus className="size-4" />{translate("Add ingredient")}
      </Button>
      {unitCost !== null ? (
        <p className="text-sm text-zinc-600">
          {translate("Cost / {uom}", { uom: String(draft.uom ?? "") })}{" "}
          <b className="tabular-nums text-zinc-900">{cur()}{fmtUnitCost(unitCost)}</b>
          <span className="ms-2 text-xs text-zinc-400">{translate("worked out from the recipe")}</span>
        </p>
      ) : totals.missing.length > 0 && (
        <p className="text-xs text-amber-700">
          {translate("Add a cost for: {names}", { names: totals.missing.join(", ") })}
        </p>
      )}
      {error && <p role="alert" className="text-sm text-rose-700">{translate(error)}</p>}
    </div>
  )
}
