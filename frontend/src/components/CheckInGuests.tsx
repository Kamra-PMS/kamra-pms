/*  Everyone on the booking, one card each, at the check-in ID step.

    The booking says how many adults and children are coming, so the desk
    sees that many cards: the main guest first, then one per extra guest.
    Each card takes the person's photo, a picture of their ID, and the ID
    details, typed or read by a scanner (IdScan). A child is kept by name
    and age only, unless the country's register needs their ID. */

import { useState } from "react"
import { Camera, Check, IdCard, Loader2, ScanLine, UserRound } from "lucide-react"
import { call } from "../lib/api"
import { serverError } from "../lib/resource"
import { useLocale } from "../lib/money"
import { useT, t as translate } from "../lib/i18n"
import { cn } from "../lib/utils"
import { Button } from "./ui/button"
import CameraCapture from "./CameraCapture"
import IdScan, { type IdRead } from "./IdScan"

export interface GuestOccupant {
  row: string
  full_name: string
  age: number | null
  gender?: string | null
  nationality?: string | null
  id_type?: string | null
  id_number?: string | null
  has_id: boolean
  exempt: boolean
  has_photo?: boolean
}

interface Draft {
  row?: string
  full_name: string
  age: string
  gender: string
  nationality: string
  id_type: string
  id_number: string
  has_id: boolean
  has_photo: boolean
}

const draft = (o?: GuestOccupant): Draft => ({
  row: o?.row,
  full_name: o?.full_name ?? "",
  age: o?.age != null ? String(o.age) : "",
  gender: o?.gender ?? "",
  nationality: o?.nationality ?? "",
  id_type: o?.id_type ?? "",
  id_number: o?.id_number ?? "",
  has_id: !!o?.has_id,
  has_photo: !!o?.has_photo,
})

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-2 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

type Shot = { who: "main" } | { who: number; kind: "id" | "photo" }

export default function CheckInGuests({ reservation, guest, guestName, guestHasPhoto,
  adults, children, occupants, idTypes, onChanged, onMainRead: fillMain }: {
  reservation: string
  guest: string | null
  guestName: string
  guestHasPhoto: boolean
  adults: number
  children: number
  occupants: GuestOccupant[]
  idTypes: string[]
  onChanged: () => void
  /** a scan of the main guest's ID fills the details form; it saves with it */
  onMainRead: (r: IdRead) => void
}) {
  const { t } = useT()
  const loc = useLocale()
  const others = Math.max(occupants.length, (adults || 1) + (children || 0) - 1)
  const [rows, setRows] = useState<Draft[]>(() =>
    Array.from({ length: others }, (_, i) => draft(occupants[i])))
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [scanning, setScanning] = useState<"main" | number | null>(null)
  const [mainRead, setMainRead] = useState<IdRead | null>(null)
  const [shot, setShot] = useState<Shot | null>(null)

  const minor = (d: Draft) => d.age !== "" && Number(d.age) < loc.adult_age
  const noId = (d: Draft) => minor(d) && loc.minor_ids !== "all" &&
    (!d.nationality || d.nationality.trim().toLowerCase() === loc.default_nationality.trim().toLowerCase())

  function set(i: number, patch: Partial<Draft>) {
    setRows((r) => r.map((d, j) => (j === i ? { ...d, ...patch } : d)))
    setDirty(true)
  }

  async function busyDo(fn: () => Promise<unknown>) {
    setBusy(true)
    setErr(null)
    try {
      await fn()
    } catch (e) {
      setErr(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  /** Save the register; hands back the saved rows' ids in card order. */
  async function save(): Promise<(string | undefined)[]> {
    const named = rows.filter((d) => d.full_name.trim())
    const out = await call<{ rows: { row: string }[] }>("kamra.api.update_occupants", {
      reservation,
      occupants: named.map((d) => ({
        row: d.row, full_name: d.full_name.trim(), age: d.age === "" ? null : Number(d.age),
        gender: d.gender, nationality: d.nationality, id_type: d.id_type, id_number: d.id_number,
      })),
    })
    let k = 0
    const ids = rows.map((d) => (d.full_name.trim() ? out.rows[k++]?.row : undefined))
    setRows((r) => r.map((d, i) => ({ ...d, row: ids[i] ?? d.row })))
    setDirty(false)
    onChanged()
    return ids
  }

  function onMainRead(r: IdRead) {
    setScanning(null)
    setMainRead(r)
    fillMain(r)
  }

  function onOtherRead(i: number, r: IdRead) {
    setScanning(null)
    set(i, {
      full_name: r.full_name || rows[i].full_name,
      age: r.age != null ? String(r.age) : rows[i].age,
      gender: r.gender ?? rows[i].gender,
      nationality: r.nationality ?? rows[i].nationality,
      id_type: r.id_type, id_number: r.id_number,
    })
  }

  async function takeShot(data: string) {
    const s = shot
    setShot(null)
    if (!s) return
    await busyDo(async () => {
      if (s.who === "main") {
        if (!guest) throw new Error(t("This booking has no guest profile."))
        await call("kamra.guest_documents.save_guest_file", { guest, kind: "photo", data })
        onChanged()
        return
      }
      const i = s.who
      const row = dirty || !rows[i].row ? (await save())[i] : rows[i].row
      if (!row) throw new Error(t("Type the guest's name first."))
      await call("kamra.api.upload_occupant_id", { reservation, row, image: data, kind: s.kind })
      set(i, s.kind === "id" ? { has_id: true } : { has_photo: true })
      setDirty(false)
      onChanged()
    })
  }

  const total = 1 + rows.length

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="text-sm font-semibold text-zinc-800">
          {t("Everyone staying ({n})", { n: total })}
        </h4>
        <span className="text-xs text-zinc-500">
          {t("{adults} adults, {children} children on the booking", { adults: adults || 1, children: children || 0 })}
        </span>
      </div>

      {/* main guest: the details form above edits them; here the photo and scan */}
      <div className="rounded-xl border border-zinc-200 bg-white p-3">
        <div className="flex flex-wrap items-center gap-2">
          <UserRound className="size-4 text-zinc-400" aria-hidden />
          <span className="min-w-0 flex-1 truncate text-sm font-semibold">{guestName}</span>
          <PhotoButton has={guestHasPhoto} disabled={busy || !guest} onClick={() => setShot({ who: "main" })} />
          <Button type="button" variant="outline" disabled={busy} onClick={() => setScanning("main")}>
            <ScanLine className="size-4" />{t("Scan ID")}
          </Button>
        </div>
        {scanning === "main" && (
          <div className="mt-2"><IdScan onRead={onMainRead} onClose={() => setScanning(null)} /></div>
        )}
        {mainRead && (
          <p className="mt-2 rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-900">
            {t("Read from the ID: {name}{dob}. Check it is the guest at the desk.", {
              name: mainRead.full_name || mainRead.id_number,
              dob: mainRead.date_of_birth ? ` · ${mainRead.date_of_birth}` : "",
            })}
          </p>
        )}
      </div>

      {rows.map((d, i) => (
        <div key={i} className="rounded-xl border border-zinc-200 bg-white p-3">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className="flex-1 text-xs font-semibold uppercase tracking-wider text-zinc-500">
              {t("Guest {n}", { n: i + 2 })}
            </span>
            {!noId(d) && (
              <>
                <PhotoButton has={d.has_photo} disabled={busy || !d.full_name.trim()}
                  onClick={() => setShot({ who: i, kind: "photo" })} />
                <Button type="button" variant="outline" disabled={busy || !d.full_name.trim()}
                  onClick={() => setShot({ who: i, kind: "id" })}
                  title={t("Take a picture of this guest's ID")}>
                  {d.has_id ? <Check className="size-4 text-emerald-600" /> : <IdCard className="size-4" />}
                  {t("ID picture")}
                </Button>
                <Button type="button" variant="outline" disabled={busy} onClick={() => setScanning(i)}>
                  <ScanLine className="size-4" />{t("Scan ID")}
                </Button>
              </>
            )}
          </div>
          {scanning === i && (
            <div className="mb-2"><IdScan onRead={(r) => onOtherRead(i, r)} onClose={() => setScanning(null)} /></div>
          )}
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <input className={cn(inputCls, "col-span-2")} placeholder={t("Full name")} value={d.full_name}
              onChange={(e) => set(i, { full_name: e.target.value })} />
            <input className={inputCls} placeholder={t("Age")} inputMode="numeric" value={d.age}
              onChange={(e) => set(i, { age: e.target.value.replace(/\D/g, "").slice(0, 3) })} />
            <select className={inputCls} value={d.gender} onChange={(e) => set(i, { gender: e.target.value })}
              aria-label={t("Gender")}>
              <option value="">{t("Gender")}</option>
              {["Male", "Female", "Other"].map((g) => <option key={g} value={g}>{translate(g)}</option>)}
            </select>
            {noId(d) ? (
              <p className="col-span-2 self-center text-xs text-zinc-500 sm:col-span-4">
                {t("Child: name and age are enough, no ID needed.")}
              </p>
            ) : (
              <>
                <select className={inputCls} value={d.id_type} onChange={(e) => set(i, { id_type: e.target.value })}
                  aria-label={t("ID type")}>
                  <option value="">{t("ID type")}</option>
                  {idTypes.map((x) => <option key={x} value={x}>{translate(x)}</option>)}
                </select>
                <input className={inputCls} placeholder={t("ID number")} value={d.id_number} autoComplete="off"
                  onChange={(e) => set(i, { id_number: e.target.value })} />
                <input className={cn(inputCls, "col-span-2")} placeholder={t("Nationality")} value={d.nationality}
                  onChange={(e) => set(i, { nationality: e.target.value })} />
              </>
            )}
          </div>
        </div>
      ))}

      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" variant="outline" disabled={busy}
          onClick={() => { setRows((r) => [...r, draft()]); setDirty(true) }}>
          {t("Add a guest")}
        </Button>
        {rows.length > 0 && (
          <Button type="button" disabled={busy || !dirty} onClick={() => void busyDo(save)}>
            {busy && <Loader2 className="size-4 animate-spin" />}{t("Save guests")}
          </Button>
        )}
        {dirty && <span className="text-xs text-amber-700">{t("Not saved yet")}</span>}
      </div>
      {err && <p className="text-xs font-medium text-rose-700">{err}</p>}

      {shot && (
        <CameraCapture
          title={shot.who !== "main" && shot.kind === "id" ? translate("Picture of the ID") : translate("Guest photo")}
          facing={shot.who !== "main" && shot.kind === "id" ? "environment" : "user"}
          onUse={(data) => void takeShot(data)}
          onClose={() => setShot(null)}
        />
      )}
    </section>
  )
}

function PhotoButton({ has, disabled, onClick }: { has: boolean; disabled: boolean; onClick: () => void }) {
  const { t } = useT()
  return (
    <Button type="button" variant="outline" disabled={disabled} onClick={onClick}
      title={t("Take the guest's photo")}>
      {has ? <Check className="size-4 text-emerald-600" /> : <Camera className="size-4" />}
      {t("Photo")}
    </Button>
  )
}
