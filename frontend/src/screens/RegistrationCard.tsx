import { useCallback, useEffect, useState } from "react"
import {
  Camera, ArrowLeft, BedDouble, Plus, Printer, Receipt, Trash2 } from "lucide-react"
import { Link, useParams } from "react-router-dom"
import { call } from "../lib/api"
import EditableNationality from "../components/EditableNationality"
import { Button } from "../components/ui/button"
import { cur, locale, moneyLocale, taxLabel, useLocale } from "../lib/money"
import { serverError } from "../lib/resource"
import { useT } from "../lib/i18n"
import { cn } from "../lib/utils"
import RoomChangeDialog from "../components/RoomChangeDialog"

/** Printable Guest Registration Card (GRC) - sign at check-in. */

interface Occupant {
  row?: string | null
  id_file?: string | null
  full_name: string
  age: number | null
  gender: string | null
  nationality: string | null
  id_type: string | null
  id_number: string | null
  phone: string | null
}

interface Grc {
  property: {
    property_name: string
    logo_url: string | null
    address: string
    gstin: string | null
    tax_id_label?: string
    phone: string | null
    checkin_time: string
    checkout_time: string
  }
  readiness?: {
    id_on_file: boolean
    address_on_file: boolean
    occupants: number
    pax: number
    precheckin_status: string
    signed: boolean
  }
  signature?: string | null
  tax_label?: string
  reservation: {
    name: string
    status?: string
    room_number?: string | null
    room_type_name?: string | null
    room: string
    room_type: string
    check_in_date: string
    actual_check_in?: string | null
    actual_check_out?: string | null
    check_out_date: string
    nights: number
    adults: number
    children: number
    rate_total: number
    advance_paid: number
    company: string | null
    booked_by_name: string | null
    source: string
    special_requests: string | null
  }
  money?: {
    folio: string
    grand_total: number
    paid_total: number
    balance: number
    advance: number
    deposit_held: number
    refunded: number
  } | null
  guest: {
    full_name: string
    phone: string | null
    email: string | null
    nationality: string | null
    id_type: string | null
    id_number: string | null
    id_file?: string | null
    address_proof_file?: string | null
    guest_id?: string
    address: string
  }
  occupants: Occupant[]
}

const inr = (n: number) =>
  n.toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })

function Row(props: { label: string; value?: string | null }) {
  return (
    <div className="flex border-b border-zinc-200 py-1.5 text-sm">
      <span className="w-40 shrink-0 text-zinc-500">{props.label}</span>
      <span className="min-w-0 break-words font-medium">{props.value || "-"}</span>
    </div>
  )
}

const sectionCls = "mb-1 text-xs font-semibold uppercase tracking-wider text-zinc-400"

const STATUS_TONE: Record<string, string> = {
  Confirmed: "bg-sky-50 text-sky-700",
  "Checked In": "bg-emerald-50 text-emerald-700",
  "Checked Out": "bg-zinc-100 text-zinc-600",
  Cancelled: "bg-rose-50 text-rose-700",
  "No Show": "bg-amber-50 text-amber-700",
}

const emptyOccupant = (): Occupant => ({
  full_name: "", age: null, gender: "", nationality: locale().default_nationality,
  id_type: "", id_number: "", phone: "",
})

const editInputCls =
  "rounded-lg border border-zinc-300 bg-white px-2 py-1 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

function OccupantsEditor(props: {
  reservation: string
  occupants: Occupant[]
  onSaved: () => void
}) {
  const idTypes = useLocale().id_types
  const [rows, setRows] = useState<Occupant[]>(
    props.occupants.length ? props.occupants : [emptyOccupant()],
  )
  const [busy, setBusy] = useState(false)

  function set(i: number, patch: Partial<Occupant>) {
    setRows((r) => r.map((row, j) => (j === i ? { ...row, ...patch } : row)))
  }

  async function save() {
    setBusy(true)
    try {
      const out = await call<{ rows: Occupant[] }>(
        "kamra.api.update_occupants",
        {
          reservation: props.reservation,
          occupants: rows.filter((r) => r.full_name.trim()),
        },
      )
      setRows(out.rows.length ? out.rows : [emptyOccupant()])
      props.onSaved()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mt-4 rounded-xl border border-zinc-200 bg-white p-4 print:hidden">
      <h2 className="text-sm font-semibold">Occupant register</h2>
      <p className="mb-3 mt-0.5 text-xs text-zinc-400">
        Everyone staying in the room - required for the hotel register.
        Saved occupants print on the GRC above.
      </p>
      <div className="space-y-2">
        {rows.map((o, i) => (
          <div key={i} className="flex flex-wrap items-center gap-1.5">
            <input
              className={`${editInputCls} w-40`}
              placeholder="Full name"
              value={o.full_name}
              onChange={(e) => set(i, { full_name: e.target.value })}
            />
            <input
              className={`${editInputCls} w-16`}
              type="number"
              placeholder="Age"
              value={o.age ?? ""}
              onChange={(e) =>
                set(i, { age: e.target.value === "" ? null : Number(e.target.value) })
              }
            />
            <select
              className={editInputCls}
              value={o.gender ?? ""}
              onChange={(e) => set(i, { gender: e.target.value })}
            >
              <option value="">Gender</option>
              {["Male", "Female", "Other"].map((g) => (
                <option key={g}>{g}</option>
              ))}
            </select>
            <input
              className={`${editInputCls} w-24`}
              placeholder="Nationality"
              value={o.nationality ?? ""}
              onChange={(e) => set(i, { nationality: e.target.value })}
            />
            <select
              className={editInputCls}
              value={o.id_type ?? ""}
              onChange={(e) => set(i, { id_type: e.target.value })}
            >
              <option value="">ID type</option>
              {/* a value recorded under another list stays visible */}
              {[
                ...idTypes,
                ...(o.id_type && !idTypes.includes(o.id_type) ? [o.id_type] : []),
              ].map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
            <input
              className={`${editInputCls} w-36`}
              placeholder="ID number"
              value={o.id_number ?? ""}
              onChange={(e) => set(i, { id_number: e.target.value })}
            />
            {o.row ? (
              <label
                className={`flex cursor-pointer items-center gap-1 rounded-lg border px-2 py-1 text-xs font-medium ${
                  o.id_file
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                    : "border-zinc-200 text-zinc-500 hover:border-brand-400 hover:text-brand-700"
                }`}
                title={o.id_file ? "Replace this occupant's ID document" : "Capture or upload this occupant's ID document"}
              >
                <Camera className="size-3.5" aria-hidden />
                {o.id_file ? "ID ✓ Replace" : "Capture ID"}
                <input
                  type="file"
                  accept="image/*"
                  capture="environment"
                  className="hidden"
                  onChange={async (e) => {
                    const f = e.target.files?.[0]
                    if (!f || !o.row) return
                    const r = await call<{ file: string }>(
                      "kamra.api.upload_occupant_id",
                      {
                        reservation: props.reservation,
                        row: o.row,
                        image: await fileToDataUrl(f),
                      },
                    )
                    set(i, { id_file: r.file })
                    e.target.value = ""
                  }}
                />
              </label>
            ) : (
              <span className="text-xs text-zinc-400" title="Save the register first, then capture this occupant's ID">
                save row → ID
              </span>
            )}
            <button
              className="rounded p-1 text-zinc-400 hover:text-rose-500"
              aria-label="Remove occupant"
              onClick={() => setRows((r) => r.filter((_, j) => j !== i))}
            >
              <Trash2 className="size-4" aria-hidden />
            </button>
          </div>
        ))}
      </div>
      <div className="mt-3 flex gap-2">
        <Button
          variant="outline"
          onClick={() => setRows((r) => [...r, emptyOccupant()])}
        >
          <Plus className="size-4" aria-hidden /> Add occupant
        </Button>
        <Button disabled={busy} onClick={save}>
          {busy ? "Saving…" : "Save register"}
        </Button>
      </div>
    </div>
  )
}


/** One editable "what actually happened" moment - shown on the printed
 * card, corrected inline by the desk (early check-in, late checkout). */
function toDatetimeLocalValue(raw?: string | null): string {
  // Frappe sends "YYYY-MM-DD HH:MM:SS"; <input type="datetime-local"> needs
  // "YYYY-MM-DDTHH:MM". Falling back to local now (not UTC) when empty.
  if (raw) {
    const s = String(raw).trim().replace(" ", "T")
    const m = s.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/)
    if (m) return `${m[1]}T${m[2]}`
  }
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, "0")
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  )
}

function ActualTimeRow(props: {
  label: string
  reservation: string
  field: "actual_check_in" | "actual_check_out"
  value?: string | null
  onSaved: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [val, setVal] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const shown = props.value
    ? props.value.replace("T", " ").slice(0, 16)
    : "—"
  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-zinc-200 py-1.5 text-sm">
      <span className="w-40 shrink-0 text-zinc-500">{props.label}</span>
      {editing ? (
        <span className="flex min-w-0 flex-wrap items-center justify-end gap-1 print:hidden">
          <input
            type="datetime-local"
            className="min-w-0 rounded-lg border border-zinc-300 px-2 py-1 text-sm"
            value={val}
            onChange={(e) => {
              setVal(e.target.value)
              setError(null)
            }}
          />
          <Button
            variant="outline"
            className="!px-2 !py-1 text-xs"
            disabled={busy || !val}
            onClick={async () => {
              if (!val) return
              setBusy(true)
              setError(null)
              try {
                // datetime-local is "YYYY-MM-DDTHH:MM" (sometimes with
                // seconds). Frappe wants "YYYY-MM-DD HH:MM:SS".
                const local = val.replace("T", " ")
                const payload = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(local)
                  ? `${local}:00`
                  : local
                await call("kamra.api.set_actual_times", {
                  reservation: props.reservation,
                  [props.field]: payload,
                })
                setEditing(false)
                props.onSaved()
              } catch (e) {
                setError(e instanceof Error ? e.message : "Could not save")
              } finally {
                setBusy(false)
              }
            }}
          >
            {busy ? "…" : "Save"}
          </Button>
          <button
            type="button"
            className="text-xs text-zinc-400"
            onClick={() => {
              setEditing(false)
              setError(null)
            }}
          >
            ✕
          </button>
          {error && (
            <span className="basis-full text-right text-xs text-rose-600">
              {error}
            </span>
          )}
        </span>
      ) : (
        <span className="flex flex-1 items-center font-medium">
          {shown}
          <button
            type="button"
            className="ms-auto text-xs font-medium text-brand-700 hover:underline print:hidden"
            onClick={() => {
              setVal(toDatetimeLocalValue(props.value))
              setError(null)
              setEditing(true)
            }}
          >
            edit
          </button>
        </span>
      )}
    </div>
  )
}

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    const url = URL.createObjectURL(file)
    img.onload = () => {
      const max = 1600
      const scale = Math.min(1, max / Math.max(img.width, img.height))
      const canvas = document.createElement("canvas")
      canvas.width = Math.round(img.width * scale)
      canvas.height = Math.round(img.height * scale)
      canvas.getContext("2d")!.drawImage(img, 0, 0, canvas.width, canvas.height)
      URL.revokeObjectURL(url)
      resolve(canvas.toDataURL("image/jpeg", 0.85))
    }
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("unreadable image")) }
    img.src = url
  })
}

export default function RegistrationCard() {
  const { name } = useParams()
  const { t } = useT()
  const [d, setD] = useState<Grc | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [changingRoom, setChangingRoom] = useState(false)
  const [uploading, setUploading] = useState<string | null>(null)

  const load = useCallback(() => {
    if (name)
      call<Grc>("kamra.api.registration_card", { reservation: name })
        .then((g) => {
          setD(g)
          setError(null)
        })
        .catch((e) => setError(serverError(e)))
  }, [name])

  useEffect(load, [load])

  if (error && !d)
    return (
      <div className="mx-auto max-w-2xl rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
        {error}
      </div>
    )
  if (!d) return <p className="py-10 text-center text-zinc-400">{t("Loading…")}</p>

  const r = d.reservation
  const roomLabel = r.room_number
    ? `${r.room_number} · ${r.room_type_name ?? r.room_type}`
    : t("Unassigned")
  const canMove = r.status === "Confirmed" || r.status === "Checked In"
  const rd = d.readiness
  const checks: { ok: boolean; label: string; hint?: string }[] = rd
    ? [
        { ok: rd.id_on_file, label: t("Guest ID on file") },
        { ok: rd.address_on_file, label: t("Address proof"), hint: t("optional") },
        {
          ok: rd.occupants >= rd.pax,
          label: t("Occupants registered ({n} of {pax})", { n: rd.occupants, pax: rd.pax }),
        },
        {
          ok: rd.signed || rd.precheckin_status === "Verified",
          label: rd.signed ? t("Signed online") : t("Signature"),
          hint: rd.signed ? undefined : t("sign the printed card"),
        },
      ]
    : []

  async function upload(kind: "id" | "address", f: File) {
    if (!d?.guest.guest_id) return
    setUploading(kind)
    try {
      await call("kamra.api.upload_guest_document", {
        guest: d.guest.guest_id,
        kind,
        image: await fileToDataUrl(f),
      })
      load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setUploading(null)
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      {/* action bar - never printed */}
      <div className="mb-4 flex flex-wrap items-center gap-3 print:hidden">
        <Link to="/reservations" className="inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-800">
          <ArrowLeft className="size-4" aria-hidden /> {t("Reservations")}
        </Link>
        <div className="flex min-w-0 items-center gap-2">
          <h1 className="truncate text-lg font-semibold text-zinc-900">{t("Registration card")}</h1>
          <span className="font-mono text-sm text-zinc-500">{r.name}</span>
          {r.status && (
            <span className={cn("rounded-full px-2 py-0.5 text-xs font-semibold", STATUS_TONE[r.status] ?? "bg-zinc-100 text-zinc-700")}>
              {t(r.status)}
            </span>
          )}
        </div>
        <div className="ms-auto flex flex-wrap gap-2">
          {canMove && (
            <Button variant="outline" onClick={() => setChangingRoom(true)}>
              <BedDouble className="size-4" aria-hidden />
              {r.room_number ? t("Change room") : t("Assign room")}
            </Button>
          )}
          {d.money && (
            <Link
              to={`/billing/${encodeURIComponent(d.money.folio)}`}
              className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
            >
              <Receipt className="size-4" aria-hidden /> {t("Open bill")}
            </Link>
          )}
          <Button onClick={() => window.print()}>
            <Printer className="size-4" aria-hidden /> {t("Print GRC")}
          </Button>
        </div>
      </div>

      {error && (
        <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 print:hidden">
          {error}
        </div>
      )}

      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_17rem]">
        {/* ── the printable card ─────────────────────────────── */}
        <div className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm print:border-0 print:p-0 print:shadow-none">
          <div className="mb-5 flex items-start justify-between gap-4 border-b border-zinc-300 pb-4">
            <div className="flex items-start gap-3">
              {d.property.logo_url && (
                <img src={d.property.logo_url} alt="" className="size-12 shrink-0 rounded object-contain" />
              )}
              <div>
                <p className="text-lg font-bold">{d.property.property_name}</p>
                <p className="text-xs text-zinc-500">{d.property.address}</p>
                <p className="text-xs text-zinc-500">
                  {d.property.gstin && (
                    <>
                      {d.property.tax_id_label ?? "GSTIN"} {d.property.gstin} ·{" "}
                    </>
                  )}
                  {d.property.phone}
                </p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-sm font-semibold tracking-wide">{t("GUEST REGISTRATION CARD")}</p>
              <p className="font-mono text-xs text-zinc-500">{r.name}</p>
            </div>
          </div>

          <div className="grid gap-x-8 gap-y-5 sm:grid-cols-2">
            <section>
              <h2 className={sectionCls}>{t("Guest")}</h2>
              <Row label={t("Name")} value={d.guest.full_name} />
              <Row label={t("Phone")} value={d.guest.phone} />
              <Row label={t("Email")} value={d.guest.email} />
              {d.guest.guest_id ? (
                <EditableNationality
                  guestId={d.guest.guest_id}
                  value={d.guest.nationality}
                  variant="row"
                  onSaved={(nationality) =>
                    setD((prev) => (prev ? { ...prev, guest: { ...prev.guest, nationality } } : prev))
                  }
                />
              ) : (
                <Row label={t("Nationality")} value={d.guest.nationality} />
              )}
              <Row
                label={t("ID")}
                value={d.guest.id_type ? `${t(d.guest.id_type)} · ${d.guest.id_number ?? ""}` : null}
              />
              <Row label={t("Address")} value={d.guest.address} />
              {r.company && <Row label={t("Company")} value={r.company} />}
              {r.booked_by_name && <Row label={t("Booked by")} value={r.booked_by_name} />}
            </section>

            <section>
              <h2 className={sectionCls}>{t("Stay")}</h2>
              <div className="flex items-center border-b border-zinc-200 py-1.5 text-sm">
                <span className="w-40 shrink-0 text-zinc-500">{t("Room")}</span>
                <span className="font-semibold">{roomLabel}</span>
                {canMove && (
                  <button
                    type="button"
                    onClick={() => setChangingRoom(true)}
                    className="ms-auto text-xs font-medium text-brand-700 hover:underline print:hidden"
                  >
                    {t("Change")}
                  </button>
                )}
              </div>
              <Row label={t("Check-in")} value={`${r.check_in_date} (${d.property.checkin_time.slice(0, 5)})`} />
              <Row label={t("Check-out")} value={`${r.check_out_date} (${d.property.checkout_time.slice(0, 5)})`} />
              <ActualTimeRow label={t("Actual check-in")} reservation={r.name}
                field="actual_check_in" value={r.actual_check_in} onSaved={load} />
              <ActualTimeRow label={t("Actual check-out")} reservation={r.name}
                field="actual_check_out" value={r.actual_check_out} onSaved={load} />
              <Row label={t("Nights")} value={String(r.nights)} />
              <Row
                label={t("Guests")}
                value={
                  t("{n} adult{s}", { n: r.adults, s: r.adults === 1 ? "" : "s" }) +
                  (r.children ? ` + ${t("{n} child", { n: r.children })}` : "")
                }
              />
              <Row
                label={t("Stay total")}
                value={`${cur()}${inr(r.rate_total)} (${t("incl. {tax}", { tax: d.tax_label ?? taxLabel() })})`}
              />
              <Row label={t("Advance paid")} value={`${cur()}${inr(r.advance_paid)}`} />
              <Row label={t("Source")} value={r.source} />
            </section>
          </div>

          {r.special_requests && (
            <p className="mt-4 rounded-lg bg-zinc-50 px-3 py-2 text-sm print:bg-transparent print:px-0">
              <span className="text-zinc-500">{t("Requests")}: </span>
              {r.special_requests}
            </p>
          )}

          {/* documents on file - printed with the card */}
          {(d.guest.id_file || d.guest.address_proof_file) && (
            <div className="mt-5 grid grid-cols-2 gap-4">
              {(
                [
                  ["id", t("ID document"), d.guest.id_file],
                  ["address", t("Address proof"), d.guest.address_proof_file],
                ] as const
              ).map(([kind, label, url]) =>
                url ? (
                  <figure key={kind}>
                    <figcaption className={sectionCls}>{label}</figcaption>
                    <a href={url} target="_blank" rel="noreferrer">
                      <img src={url} alt={label} className="max-h-32 rounded-lg border border-zinc-200 object-contain" />
                    </a>
                  </figure>
                ) : null,
              )}
            </div>
          )}

          <section className="mt-5">
            <h2 className={sectionCls}>{t("Occupants")}</h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-300 text-left text-[11px] uppercase tracking-wider text-zinc-400">
                  <th className="py-1 pe-3 font-medium">{t("Name")}</th>
                  <th className="py-1 pe-3 font-medium">{t("Age")}</th>
                  <th className="py-1 pe-3 font-medium">{t("Gender")}</th>
                  <th className="py-1 pe-3 font-medium">{t("Nationality")}</th>
                  <th className="py-1 font-medium">{t("ID")}</th>
                </tr>
              </thead>
              <tbody>
                {d.occupants.map((o, i) => (
                  <tr key={i} className="border-b border-zinc-200">
                    <td className="py-1.5 pe-3 font-medium">{o.full_name}</td>
                    <td className="py-1.5 pe-3">{o.age ?? "-"}</td>
                    <td className="py-1.5 pe-3">{o.gender ? t(o.gender) : "-"}</td>
                    <td className="py-1.5 pe-3">{o.nationality || "-"}</td>
                    <td className="py-1.5">{o.id_type ? `${t(o.id_type)} · ${o.id_number ?? ""}` : "-"}</td>
                  </tr>
                ))}
                {d.occupants.length === 0 &&
                  [0, 1, 2].map((i) => (
                    <tr key={i} className="border-b border-zinc-200">
                      <td className="py-4" colSpan={5} />
                    </tr>
                  ))}
              </tbody>
            </table>
          </section>

          <p className="mt-6 text-[11px] leading-relaxed text-zinc-500">
            {t("I certify the above details are correct. I agree to the hotel's policies on check-out time, damage to property and applicable taxes, and consent to my details being kept in the guest register as required by law.")}
          </p>

          <div className="mt-8 grid grid-cols-2 gap-8">
            <div className="text-center text-xs text-zinc-500">
              <div className="flex h-16 items-end justify-center">
                {d.signature && (
                  <img src={d.signature} alt={t("Guest signature")} className="max-h-16 object-contain" />
                )}
              </div>
              <div className="border-t border-zinc-400 pt-1">
                {t("Guest signature")}
                {d.signature && <span className="block text-[10px] text-zinc-400">{t("signed online at pre-check-in")}</span>}
              </div>
            </div>
            <div className="text-center text-xs text-zinc-500">
              <div className="h-16" />
              <div className="border-t border-zinc-400 pt-1">{t("Front desk (name & sign)")}</div>
            </div>
          </div>
        </div>

        {/* ── the desk's rail - never printed ────────────────── */}
        <aside className="space-y-4 print:hidden lg:sticky lg:top-4">
          <div className="rounded-xl border border-zinc-200 bg-white p-4">
            <h2 className="mb-2 text-sm font-semibold text-zinc-800">{t("Registration checklist")}</h2>
            <ul className="space-y-1.5 text-sm">
              {checks.map((c) => (
                <li key={c.label} className="flex items-start gap-2">
                  <span
                    className={cn(
                      "mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full text-[10px] font-bold",
                      c.ok ? "bg-emerald-100 text-emerald-700" : "bg-zinc-100 text-zinc-400",
                    )}
                    aria-hidden
                  >
                    {c.ok ? "✓" : "·"}
                  </span>
                  <span className={c.ok ? "text-zinc-800" : "text-zinc-500"}>
                    {c.label}
                    {!c.ok && c.hint && <span className="text-xs text-zinc-400"> · {c.hint}</span>}
                  </span>
                </li>
              ))}
            </ul>
            {rd && (
              <p className="mt-2 text-xs text-zinc-400">
                {t("Online check-in {status}", { status: t(rd.precheckin_status) })}
              </p>
            )}
          </div>

          <div className="rounded-xl border border-zinc-200 bg-white p-4">
            <h2 className="mb-2 text-sm font-semibold text-zinc-800">{t("Documents")}</h2>
            <div className="space-y-2">
              {(
                [
                  ["id", t("Guest ID"), d.guest.id_file],
                  ["address", t("Address proof"), d.guest.address_proof_file],
                ] as const
              ).map(([kind, label, url]) => (
                <label
                  key={kind}
                  className="flex cursor-pointer items-center justify-between gap-2 rounded-lg border border-zinc-200 px-3 py-2 text-sm hover:bg-zinc-50"
                >
                  <span className="flex items-center gap-2">
                    <Camera className="size-4 text-zinc-400" aria-hidden />
                    {label}
                  </span>
                  <span className="text-xs font-medium text-brand-700">
                    {uploading === kind ? t("Saving…") : url ? t("Replace") : t("Capture")}
                  </span>
                  <input
                    type="file"
                    accept="image/*"
                    capture="environment"
                    className="hidden"
                    onChange={(e) => {
                      const f = e.target.files?.[0]
                      if (f) upload(kind, f)
                    }}
                  />
                </label>
              ))}
            </div>
          </div>

          {d.money && (
            <div className="rounded-xl border border-zinc-200 bg-white p-4">
              <h2 className="mb-2 text-sm font-semibold text-zinc-800">{t("Money")}</h2>
              <dl className="space-y-1 text-sm">
                {(
                  [
                    [t("Charges"), d.money.grand_total, ""],
                    [t("Paid"), d.money.paid_total, "text-emerald-700"],
                    ...(d.money.advance ? [[t("of which advance"), d.money.advance, "text-zinc-500"]] : []),
                    ...(d.money.deposit_held ? [[t("Deposit held"), d.money.deposit_held, "text-zinc-500"]] : []),
                    [t("Balance"), d.money.balance, d.money.balance > 0 ? "font-semibold text-rose-600" : "font-semibold text-zinc-400"],
                  ] as [string, number, string][]
                ).map(([k, v, cls]) => (
                  <div key={k} className="flex justify-between">
                    <dt className="text-zinc-500">{k}</dt>
                    <dd className={cn("tabular-nums", cls)}>{cur()}{inr(v)}</dd>
                  </div>
                ))}
              </dl>
              <Link
                to={`/billing/${encodeURIComponent(d.money.folio)}`}
                className="mt-3 block text-sm font-medium text-brand-700 hover:underline"
              >
                {t("Open bill - take payment, settle, invoice →")}
              </Link>
            </div>
          )}
        </aside>
      </div>

      {name && (
        <div className="print:hidden">
          <OccupantsEditor reservation={name} occupants={d.occupants} onSaved={load} />
        </div>
      )}

      {changingRoom && (
        <RoomChangeDialog
          reservation={r.name}
          currentRoomNumber={r.room_number}
          onClose={() => setChangingRoom(false)}
          onMoved={load}
        />
      )}
    </div>
  )
}
