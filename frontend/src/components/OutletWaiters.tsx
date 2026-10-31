import { useEffect, useState } from "react"

import { call } from "../lib/api"
import { serverError, type Row } from "../lib/resource"
import { Button } from "./ui/button"
import { t, useUILanguage } from "../lib/i18n"

export type OutletWaiterList = {
  waiters: { waiter_name: string; active: number }[]
  can_edit: boolean
}

/** The outlet's waiter list: names the till offers in its Waiter box.
 *  No login needed; unticking Active hides a name, past bills keep it. */
export default function OutletWaiters({ row }: { row: Row; reload: () => void }) {
  useUILanguage()
  const outlet = String(row.name)
  const [list, setList] = useState<OutletWaiterList | null>(null)
  const [name, setName] = useState("")
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    call<OutletWaiterList>("kamra.pos.outlet_waiters", { outlet }).then(setList)
      .catch((e) => setError(serverError(e)))
  }, [outlet])

  async function save(waiter_name: string, active: number) {
    setError(null)
    try {
      setList(await call<OutletWaiterList>("kamra.pos.save_outlet_waiter", { outlet, waiter_name, active }))
      setName("")
    } catch (e) {
      setError(serverError(e))
    }
  }

  return (
    <div className="space-y-2 border-t border-zinc-200 pt-4">
      <div className="text-xs font-semibold uppercase tracking-wider text-zinc-500">{t("Waiters")}</div>
      <p className="text-xs text-zinc-500">{t("Names the till offers in its Waiter box. No login needed.")}</p>
      {list?.waiters.length === 0 && <p className="text-xs text-zinc-500">{t("No waiters on the list yet.")}</p>}
      <ul className="space-y-1">
        {list?.waiters.map((w) => (
          <li key={w.waiter_name} className="flex items-center gap-2 text-sm">
            <label className="flex flex-1 items-center gap-2">
              <input type="checkbox" checked={!!w.active} disabled={!list.can_edit}
                onChange={(e) => { void save(w.waiter_name, e.target.checked ? 1 : 0) }} />
              <span className={w.active ? "" : "text-zinc-400 line-through"}>{w.waiter_name}</span>
            </label>
            {!w.active && <span className="text-xs text-zinc-400">{t("Inactive")}</span>}
          </li>
        ))}
      </ul>
      {list?.can_edit && (
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (name.trim()) void save(name.trim(), 1) }}>
          <input className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm" value={name}
            aria-label={t("Waiter name")} placeholder={t("Waiter name")} onChange={(e) => setName(e.target.value)} />
          <Button type="submit" variant="outline" disabled={!name.trim()}>{t("Add")}</Button>
        </form>
      )}
      {error && <p className="text-xs text-rose-600">{t(error)}</p>}
    </div>
  )
}
