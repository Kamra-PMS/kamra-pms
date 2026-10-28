import { useEffect, useState } from "react"
import { Plus, Trash2, X } from "lucide-react"

import {
  call,
  getBookingOptions,
  getCurrentProperty,
  type BookingOptions,
} from "../lib/api"
import { serverError } from "../lib/resource"
import { useT } from "../lib/i18n"
import { Button } from "./ui/button"
import PhoneInput from "./PhoneInput"

/** New group booking (corporate, wedding, event): the group, its rooms, and
 *  which room is the main room whose guest pays for the group. One call to
 *  kamra.api.create_group_booking; rooms check in one by one afterwards. */

interface RoomRow {
  room_type: string
  count: number
  room: string
  guest_name: string
}

const GROUP_TYPES = ["Corporate", "Wedding", "Event", "Tour", "Other"]
// what the main room pays: keys of folio.COMPANY_BILLING_DEFAULTS
const MASTER_PAYS: { value: string; label: string }[] = [
  { value: "Room only", label: "Room + tax" },
  { value: "Room and F&B (liquor to guest)", label: "Room and F&B (liquor to guest)" },
  { value: "Everything except liquor", label: "Everything except liquor" },
]

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

const ymd = (x: Date) =>
  `${x.getFullYear()}-${`${x.getMonth() + 1}`.padStart(2, "0")}-${`${x.getDate()}`.padStart(2, "0")}`

function addDay(d: string) {
  const x = new Date(`${d}T00:00:00`)
  x.setDate(x.getDate() + 1)
  return ymd(x)
}

export default function GroupBookingDialog(props: {
  onClose: () => void
  onDone: () => void
}) {
  const { t } = useT()
  const today = ymd(new Date())
  const [options, setOptions] = useState<BookingOptions | null>(null)
  const [step, setStep] = useState(1)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [g, setG] = useState({
    group_name: "",
    group_type: "Wedding",
    check_in_date: today,
    check_out_date: addDay(today),
    payer: "main" as "main" | "company",
    company: "",
    guest_name: "",
    phone: "",
  })
  const [rows, setRows] = useState<RoomRow[]>([])
  const [free, setFree] = useState<Record<string, { name: string; room_number: string }[]>>({})
  const [masterRow, setMasterRow] = useState(0)
  const [pays, setPays] = useState("Room only")
  const [result, setResult] = useState<{
    group_booking: string
    created: string[]
    skipped: { room_type: string; reason: string }[]
  } | null>(null)

  useEffect(() => {
    getBookingOptions()
      .then((o) => {
        setOptions(o)
        setRows([{ room_type: o.room_types[0]?.name ?? "", count: 1, room: "", guest_name: "" }])
      })
      .catch((e) => setError(serverError(e)))
  }, [])

  // free rooms per type for the dates, to pin a specific room on a row
  const types = [...new Set(rows.map((r) => r.room_type).filter(Boolean))].join("|")
  useEffect(() => {
    if (!types) return
    for (const rt of types.split("|")) {
      call<{ name: string; room_number: string }[]>("kamra.api.available_rooms", {
        property: getCurrentProperty(),
        room_type: rt,
        check_in_date: g.check_in_date,
        check_out_date: g.check_out_date,
      })
        .then((rs) => setFree((f) => ({ ...f, [rt]: rs })))
        .catch(() => {})
    }
  }, [types, g.check_in_date, g.check_out_date])

  const total = rows.reduce((s, r) => s + (r.count || 0), 0)
  const byMain = g.payer === "main"
  const step1Ok =
    g.group_name.trim() &&
    g.guest_name.trim() &&
    g.check_in_date &&
    g.check_out_date > g.check_in_date &&
    (byMain || g.company)
  const step2Ok = total > 0 && rows.every((r) => r.room_type && r.count > 0)
  const setRow = (i: number, patch: Partial<RoomRow>) =>
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)))

  async function create() {
    setBusy(true)
    setError(null)
    // one spec per room, so the main room is an exact index and every
    // unnamed room gets a placeholder name the desk fixes at check-in
    const placeholder = t("Guest of {group}", { group: g.group_name.trim() })
    const specs: { room_type: string; count: 1; room?: string; guest_name: string }[] = []
    let masterIndex = 0
    rows.forEach((r, i) => {
      for (let n = 0; n < r.count; n++) {
        const main = i === masterRow && n === 0
        if (main) masterIndex = specs.length
        specs.push({
          room_type: r.room_type,
          count: 1,
          room: r.count === 1 && r.room ? r.room : undefined,
          guest_name:
            (n === 0 && r.guest_name.trim()) || (main ? g.guest_name.trim() : placeholder),
        })
      }
    })
    try {
      const out = await call<NonNullable<typeof result>>("kamra.api.create_group_booking", {
        property: getCurrentProperty(),
        group_name: g.group_name.trim(),
        group_type: g.group_type,
        check_in_date: g.check_in_date,
        check_out_date: g.check_out_date,
        rooms: specs,
        guest_name: g.guest_name.trim(),
        phone: g.phone || undefined,
        company: byMain ? undefined : g.company,
        ...(byMain ? { master_index: masterIndex, master_pays: pays } : {}),
      })
      setResult(out)
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const steps = [t("Group"), t("Rooms"), t("Main room and billing")]

  return (
    <div
      className="fixed inset-0 z-50"
      role="dialog"
      aria-modal="true"
      aria-label={t("New group booking")}
      onKeyDown={(e) => e.key === "Escape" && props.onClose()}
    >
      <div className="absolute inset-0 bg-black/40 animate-fade-in" onClick={props.onClose} aria-hidden />
      <div className="absolute inset-y-0 right-0 flex h-full w-full flex-col bg-white shadow-2xl animate-sheet-in md:w-2/3 lg:w-1/2">
        <header className="flex shrink-0 items-center justify-between gap-4 border-b border-zinc-200 px-6 py-4">
          <div className="min-w-0">
            <h2 className="text-xl font-semibold tracking-tight text-zinc-900">{t("New group booking")}</h2>
            <ol className="mt-1 flex flex-wrap gap-3 text-xs">
              {steps.map((s, i) => (
                <li key={s} className={i + 1 === step ? "font-semibold text-brand-700" : "text-zinc-400"}>
                  {i + 1}. {s}
                </li>
              ))}
            </ol>
          </div>
          <button onClick={props.onClose} aria-label={t("Close")} className="text-zinc-400 hover:text-zinc-700">
            <X className="size-5" />
          </button>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto px-6 py-5">
          {error && (
            <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
          )}

          {result ? (
            <div className="space-y-3 text-sm">
              <p className="text-base font-medium text-zinc-900">
                {t("Group {group} booked: {n} room(s).", { group: result.group_booking, n: String(result.created.length) })}
              </p>
              {result.skipped.length > 0 && (
                <ul className="list-disc space-y-1 pl-5 text-amber-700">
                  {result.skipped.map((s, i) => (
                    <li key={i}>{s.room_type}: {s.reason}</li>
                  ))}
                </ul>
              )}
              <p className="text-zinc-500">{t("Check rooms in one by one from the group's rooming list.")}</p>
            </div>
          ) : step === 1 ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block sm:col-span-2">
                <span className="mb-1 block text-sm font-medium text-zinc-600">{t("Group name")}</span>
                <input className={inputCls} value={g.group_name} placeholder={t("e.g. Sharma Wedding")}
                  onChange={(e) => setG({ ...g, group_name: e.target.value })} />
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-zinc-600">{t("Group type")}</span>
                <select className={inputCls} value={g.group_type} onChange={(e) => setG({ ...g, group_type: e.target.value })}>
                  {GROUP_TYPES.map((x) => <option key={x} value={x}>{t(x)}</option>)}
                </select>
              </label>
              <div />
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-zinc-600">{t("Arrival")}</span>
                <input type="date" className={inputCls} value={g.check_in_date}
                  onChange={(e) => setG({ ...g, check_in_date: e.target.value,
                    check_out_date: g.check_out_date > e.target.value ? g.check_out_date : addDay(e.target.value) })} />
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-zinc-600">{t("Departure")}</span>
                <input type="date" className={inputCls} value={g.check_out_date} min={addDay(g.check_in_date)}
                  onChange={(e) => setG({ ...g, check_out_date: e.target.value })} />
              </label>
              <fieldset className="sm:col-span-2">
                <legend className="mb-1 text-sm font-medium text-zinc-600">{t("Who pays")}</legend>
                <div className="flex flex-wrap gap-4 text-sm">
                  <label className="flex items-center gap-2">
                    <input type="radio" checked={byMain} onChange={() => setG({ ...g, payer: "main" })} />
                    {t("The main room's guest")}
                  </label>
                  <label className="flex items-center gap-2">
                    <input type="radio" checked={!byMain} onChange={() => setG({ ...g, payer: "company" })} />
                    {t("A company")}
                  </label>
                </div>
              </fieldset>
              {!byMain && (
                <label className="block sm:col-span-2">
                  <span className="mb-1 block text-sm font-medium text-zinc-600">{t("Company")}</span>
                  <select className={inputCls} value={g.company} onChange={(e) => setG({ ...g, company: e.target.value })}>
                    <option value="">{t("Choose a company…")}</option>
                    {options?.companies.map((c) => <option key={c.name} value={c.name}>{c.company_name}</option>)}
                  </select>
                </label>
              )}
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-zinc-600">{byMain ? t("Main guest") : t("Contact name")}</span>
                <input className={inputCls} value={g.guest_name} onChange={(e) => setG({ ...g, guest_name: e.target.value })} />
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-zinc-600">{t("Phone")}</span>
                <PhoneInput value={g.phone} onChange={(v) => setG({ ...g, phone: v })} />
              </label>
            </div>
          ) : step === 2 ? (
            <div className="space-y-3">
              {rows.map((r, i) => (
                <div key={i} className="grid items-end gap-2 rounded-lg border border-zinc-200 p-3 sm:grid-cols-[2fr_5rem_1.5fr_2fr_auto]">
                  <label className="block">
                    <span className="mb-1 block text-xs text-zinc-500">{t("Room type")}</span>
                    <select className={inputCls} value={r.room_type} onChange={(e) => setRow(i, { room_type: e.target.value, room: "" })}>
                      {options?.room_types.map((rt) => <option key={rt.name} value={rt.name}>{rt.room_type_name}</option>)}
                    </select>
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-xs text-zinc-500">{t("Rooms")}</span>
                    <input type="number" min={1} className={inputCls} value={r.count}
                      onChange={(e) => setRow(i, { count: Math.max(0, Number(e.target.value) || 0), room: "" })} />
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-xs text-zinc-500">{t("Room")}</span>
                    <select className={inputCls} value={r.room} disabled={r.count !== 1}
                      onChange={(e) => setRow(i, { room: e.target.value })}>
                      <option value="">{t("Any room")}</option>
                      {(free[r.room_type] ?? []).map((x) => <option key={x.name} value={x.name}>{x.room_number}</option>)}
                    </select>
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-xs text-zinc-500">{t("Guest name (optional)")}</span>
                    <input className={inputCls} value={r.guest_name} onChange={(e) => setRow(i, { guest_name: e.target.value })} />
                  </label>
                  <button aria-label={t("Remove room row")} disabled={rows.length === 1}
                    onClick={() => { setRows((rs) => rs.filter((_, j) => j !== i)); setMasterRow(0) }}
                    className="pb-2 text-zinc-300 hover:text-rose-500 disabled:opacity-30">
                    <Trash2 className="size-4" />
                  </button>
                </div>
              ))}
              <Button variant="outline" onClick={() =>
                setRows((rs) => [...rs, { room_type: options?.room_types[0]?.name ?? "", count: 1, room: "", guest_name: "" }])}>
                <Plus className="size-4" />{t("Add room type")}
              </Button>
              <p className="text-xs text-zinc-500">{t("Unnamed rooms are booked as \"Guest of {group}\" and named at check-in.", { group: g.group_name || "…" })}</p>
            </div>
          ) : (
            <div className="space-y-4 text-sm">
              {byMain ? (
                <>
                  <div>
                    <div className="mb-1 font-medium text-zinc-600">{t("Main room")}</div>
                    <div className="space-y-1">
                      {rows.map((r, i) => (
                        <label key={i} className="flex items-center gap-2">
                          <input type="radio" checked={masterRow === i} onChange={() => setMasterRow(i)} />
                          {options?.room_types.find((x) => x.name === r.room_type)?.room_type_name ?? r.room_type}
                          {r.room && ` · ${(free[r.room_type] ?? []).find((x) => x.name === r.room)?.room_number ?? r.room}`}
                          <span className="text-zinc-400">· {r.guest_name || (masterRow === i ? g.guest_name : t("Guest of {group}", { group: g.group_name }))}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                  <label className="block">
                    <span className="mb-1 block font-medium text-zinc-600">{t("The main room pays")}</span>
                    <select className={inputCls} value={pays} onChange={(e) => setPays(e.target.value)}>
                      {MASTER_PAYS.map((m) => <option key={m.value} value={m.value}>{t(m.label)}</option>)}
                    </select>
                    <span className="mt-1 block text-xs text-zinc-500">{t("For every room of the group, on one group bill. Each guest pays their own extras; liquor always stays with the guest.")}</span>
                  </label>
                </>
              ) : (
                <p className="text-zinc-600">{t("The company's billing rules decide what it pays, on one group bill.")}</p>
              )}
              <div className="rounded-lg bg-zinc-50 px-4 py-3">
                <div className="font-medium">{g.group_name} · {t(g.group_type)}</div>
                <div className="text-zinc-500">
                  {g.check_in_date} → {g.check_out_date} · {t("{n} room(s)", { n: String(total) })}
                </div>
              </div>
            </div>
          )}
        </div>

        <footer className="flex shrink-0 items-center justify-between gap-2 border-t border-zinc-200 px-6 py-3">
          {result ? (
            <>
              <span />
              <Button onClick={props.onDone}>{t("Done")}</Button>
            </>
          ) : (
            <>
              <Button variant="outline" onClick={() => (step === 1 ? props.onClose() : setStep(step - 1))}>
                {step === 1 ? t("Cancel") : t("Back")}
              </Button>
              {step < 3 ? (
                <Button disabled={step === 1 ? !step1Ok : !step2Ok} onClick={() => setStep(step + 1)}>{t("Next")}</Button>
              ) : (
                <Button disabled={busy} onClick={create}>{t("Create group booking")}</Button>
              )}
            </>
          )}
        </footer>
      </div>
    </div>
  )
}
