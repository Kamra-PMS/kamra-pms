/* A menu item's own stock, inside the Recipes window: switching it on (a new
   stock item, or one that exists), seeing what is left, and switching it off. */

import { useState } from "react"
import { call } from "../lib/api"
import { Button } from "./ui/button"
import { t as translate, useUILanguage } from "../lib/i18n"

interface Option { name: string; ingredient_name: string; uom: string }

const box = "rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-sm"

function useAction(done: () => void) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const run = async (method: string, params: Record<string, unknown>) => {
    setBusy(true); setError(null)
    try {
      await call(`kamra.inventory.${method}`, params)
      done()
    } catch (e) {
      setError(e instanceof Error ? translate(e.message) : String(e))
    } finally {
      setBusy(false)
    }
  }
  return { busy, error, run }
}

function Refused({ error }: { error: string | null }) {
  if (!error) return null
  return <div role="alert" className="mt-2 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
}

/** `adopt`: the stock item a "1 x something" recipe already uses - then it is
 *  the only one that can become the item's own. */
export function TrackStockForm({ menuItem, itemName, ingredients, adopt, onDone, onClose }: {
  menuItem: string; itemName: string; ingredients: Option[]; adopt: string | null
  onDone: () => void; onClose: () => void
}) {
  useUILanguage()
  const [how, setHow] = useState<"new" | "existing">(adopt ? "existing" : "new")
  const [existing, setExisting] = useState(adopt ?? "")
  const [name, setName] = useState(itemName)
  const [uom, setUom] = useState("pc")
  const [cost, setCost] = useState("")
  const [buyUom, setBuyUom] = useState("")
  const [buySize, setBuySize] = useState("")
  const { busy, error, run } = useAction(onDone)
  const ready = how === "existing" ? !!existing : !!name.trim() && !!uom.trim()
  const submit = () => run("track_item_stock", how === "existing"
    ? { menu_item: menuItem, ingredient: existing }
    : {
        menu_item: menuItem, ingredient_name: name.trim(), uom: uom.trim(),
        cost_per_unit: cost === "" ? 0 : Number(cost),
        buy_uom: buyUom.trim() || null, buy_size: buySize === "" ? 0 : Number(buySize),
      })
  return (
    <div className="mt-3 rounded-xl border border-zinc-200 p-4">
      <div className="text-sm font-bold text-zinc-800">{translate("Track stock of {name}", { name: itemName })}</div>
      <label className="mt-3 flex items-center gap-2 text-sm text-zinc-700">
        <input type="radio" checked={how === "new"} disabled={!!adopt} onChange={() => setHow("new")} />
        {translate("New stock item")}
      </label>
      {how === "new" && (
        <div className="mt-2 grid gap-2 pl-6 sm:grid-cols-2">
          <input className={box} value={name} onChange={(e) => setName(e.target.value)}
            aria-label={translate("Name")} placeholder={translate("Name")} />
          <input className={box} value={uom} onChange={(e) => setUom(e.target.value)} maxLength={16}
            aria-label={translate("Unit")} placeholder={translate("Unit")} />
          <input className={box} type="number" min="0" step="any" value={cost} onChange={(e) => setCost(e.target.value)}
            aria-label={translate("Cost each")} placeholder={translate("Cost each")} />
          <div className="flex gap-2">
            <input className={`${box} min-w-0 flex-1`} value={buyUom} onChange={(e) => setBuyUom(e.target.value)} maxLength={16}
              aria-label={translate("Buying unit")} placeholder={translate("Buying unit")} />
            <input className={`${box} w-24`} type="number" min="0" step="any" value={buySize} onChange={(e) => setBuySize(e.target.value)}
              aria-label={translate("Holds")} placeholder={translate("Holds")} />
          </div>
        </div>
      )}
      <label className="mt-3 flex items-center gap-2 text-sm text-zinc-700">
        <input type="radio" checked={how === "existing"} onChange={() => setHow("existing")} />
        {translate("Use an existing one")}
      </label>
      {how === "existing" && (
        <div className="mt-2 pl-6">
          <select className={`${box} w-full`} value={existing} disabled={!!adopt}
            aria-label={translate("Use an existing one")} onChange={(e) => setExisting(e.target.value)}>
            <option value="">{translate("Pick…")}</option>
            {ingredients.map((x) => <option key={x.name} value={x.name}>{x.ingredient_name} ({x.uom})</option>)}
          </select>
          <p className="mt-1 text-xs text-zinc-400">{translate("For the same bottle sold at another outlet. Each outlet keeps its own stock.")}</p>
        </div>
      )}
      <Refused error={error} />
      <div className="mt-3 flex justify-end gap-2">
        <Button variant="outline" onClick={onClose}>{translate("Close")}</Button>
        <Button disabled={busy || !ready} onClick={submit}>{translate("Track stock")}</Button>
      </div>
    </div>
  )
}

export function TrackedStock({ menuItem, name, uom, onHand, canChange, onDone }: {
  menuItem: string; name: string; uom: string; onHand: number; canChange: boolean; onDone: () => void
}) {
  useUILanguage()
  const [asking, setAsking] = useState(false)
  const { busy, error, run } = useAction(onDone)
  const left = Math.round(onHand * 1000) / 1000
  return (
    <div className="mb-3 rounded-xl border border-emerald-200 bg-emerald-50/60 p-4 text-sm">
      <div className="font-bold text-zinc-800">
        {translate("Tracks its own stock: {name} · {qty} {uom} at this outlet", { name, qty: String(left), uom })}
      </div>
      <p className="mt-1 text-zinc-600">{translate("Each one sold takes 1 {uom}.", { uom })}</p>
      {asking ? (
        <div className="mt-3">
          <p className="font-medium text-zinc-800">{translate("Stop tracking? Selling it then takes no stock. The stock item and its history stay.")}</p>
          <div className="mt-2 flex gap-2">
            <Button variant="outline" onClick={() => setAsking(false)}>{translate("Keep tracking")}</Button>
            <Button disabled={busy} onClick={() => run("untrack_item_stock", { menu_item: menuItem })}>{translate("Stop tracking")}</Button>
          </div>
        </div>
      ) : canChange ? (
        <Button variant="outline" className="mt-3" onClick={() => setAsking(true)}>{translate("Stop tracking")}</Button>
      ) : null}
      <Refused error={error} />
    </div>
  )
}
