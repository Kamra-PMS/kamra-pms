import { useEffect, useState } from "react"
import { Plus } from "lucide-react"

import { ResourceScreen } from "../components/ResourceScreen"
import { Sheet } from "../components/ui/sheet"
import { Button } from "../components/ui/button"
import { call, getCurrentProperty } from "../lib/api"
import { listResource, serverError } from "../lib/resource"
import { useT } from "../lib/i18n"
import { roomsConfig } from "./configs"

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

type Plan = { create: string[]; skipped: string[]; created: number }
type Opt = { value: string; label: string }

/** Add rooms: a floor, a number range and a room type, previewed first. */
export function AddRooms({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const { t } = useT()
  const [floors, setFloors] = useState<string[]>([])
  const [types, setTypes] = useState<Opt[]>([])
  const [f, setF] = useState({ floor: "", start: "", end: "", prefix: "", room_type: "" })
  const [plan, setPlan] = useState<Plan | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const property = getCurrentProperty()
  useEffect(() => {
    listResource("Floor", {
      fields: ["floor_name"], filters: [["property", "=", property], ["disabled", "=", 0]],
      orderBy: "sort_order asc, floor_name asc", limit: 200,
    }).then((r) => setFloors(r.map((x) => String(x.floor_name))))
    listResource("Room Type", {
      fields: ["name", "room_type_name"], filters: [["property", "=", property]],
      orderBy: "room_type_name asc", limit: 200,
    }).then((r) => setTypes(r.map((x) => ({ value: String(x.name), label: String(x.room_type_name) }))))
  }, [property])
  const set = (k: string, v: string) => {
    setF((p) => ({ ...p, [k]: v }))
    setPlan(null)
  }
  const ready = f.start !== "" && f.end !== "" && f.room_type !== ""
  async function run(preview: 0 | 1) {
    setBusy(true)
    setErr(null)
    try {
      const r = await call<Plan>("kamra.floors.add_rooms", { property, ...f, preview })
      if (preview) setPlan(r)
      else onDone()
    } catch (e) {
      setErr(serverError(e))
    } finally {
      setBusy(false)
    }
  }
  return (
    <Sheet
      title={t("Add rooms")}
      description={t("Create a run of rooms on one floor. Numbers that already exist are skipped.")}
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>{t("Cancel")}</Button>
          <Button variant="outline" disabled={!ready || busy} onClick={() => run(1)}>{t("Preview")}</Button>
          <Button disabled={!plan || !plan.create.length || busy} onClick={() => run(0)}>
            {t("Create {n} rooms", { n: plan?.create.length ?? 0 })}
          </Button>
        </div>
      }
    >
      <div className="grid gap-3">
        {err && <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</div>}
        <label className="text-sm">
          <span className="mb-1 block text-zinc-600">{t("Floor")}</span>
          <input list="add-rooms-floors" className={inputCls} value={f.floor}
            onChange={(e) => set("floor", e.target.value)} />
          <datalist id="add-rooms-floors">{floors.map((x) => <option key={x} value={x} />)}</datalist>
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-zinc-600">{t("Room type")}</span>
          <select className={inputCls} value={f.room_type} onChange={(e) => set("room_type", e.target.value)}>
            <option value="">-</option>
            {types.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </label>
        <div className="grid grid-cols-3 gap-3">
          <label className="text-sm">
            <span className="mb-1 block text-zinc-600">{t("Prefix (optional)")}</span>
            <input className={inputCls} value={f.prefix} onChange={(e) => set("prefix", e.target.value)} />
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-zinc-600">{t("From number")}</span>
            <input type="number" className={inputCls} value={f.start} onChange={(e) => set("start", e.target.value)} />
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-zinc-600">{t("To number")}</span>
            <input type="number" className={inputCls} value={f.end} onChange={(e) => set("end", e.target.value)} />
          </label>
        </div>
        {plan && (
          <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-sm">
            <p className="font-medium">{t("Will create {n}", { n: plan.create.length })}</p>
            <p className="text-zinc-600">{plan.create.join(", ") || "-"}</p>
            {plan.skipped.length > 0 && (
              <>
                <p className="mt-2 font-medium">{t("Already exist, skipped: {n}", { n: plan.skipped.length })}</p>
                <p className="text-zinc-600">{plan.skipped.join(", ")}</p>
              </>
            )}
          </div>
        )}
      </div>
    </Sheet>
  )
}

/** Admin > Rooms: the generic list plus the bulk Add rooms action. */
export default function AdminRooms() {
  const { t } = useT()
  const [open, setOpen] = useState(false)
  // bumping the key remounts the list so new rooms show up
  const [key, setKey] = useState(0)
  return (
    <>
      <ResourceScreen
        key={key}
        config={roomsConfig}
        headerAction={
          <Button variant="outline" onClick={() => setOpen(true)}>
            <Plus className="size-4" aria-hidden />
            {t("Add rooms")}
          </Button>
        }
      />
      {open && (
        <AddRooms
          onClose={() => setOpen(false)}
          onDone={() => {
            setOpen(false)
            setKey((k) => k + 1)
          }}
        />
      )}
    </>
  )
}
