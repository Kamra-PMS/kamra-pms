import { useCallback, useEffect, useState } from "react"
import { ArrowLeft, Plus, Printer, Trash2 } from "lucide-react"
import { Link, useParams } from "react-router-dom"
import { call } from "../lib/api"
import { toFullPath } from "../lib/routing"
import { Button } from "../components/ui/button"

/** Printable Guest Registration Card (GRC) - sign at check-in. */

interface Occupant {
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
    phone: string | null
    checkin_time: string
    checkout_time: string
  }
  reservation: {
    name: string
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
  n.toLocaleString("en-IN", { maximumFractionDigits: 0 })

function Row(props: { label: string; value?: string | null }) {
  return (
    <div className="flex border-b border-zinc-200 py-1.5 text-sm">
      <span className="w-40 shrink-0 text-zinc-500">{props.label}</span>
      <span className="font-medium">{props.value || "-"}</span>
    </div>
  )
}

const emptyOccupant = (): Occupant => ({
  full_name: "", age: null, gender: "", nationality: "Indian",
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
      await call("kamra.api.update_occupants", {
        reservation: props.reservation,
        occupants: rows.filter((r) => r.full_name.trim()),
      })
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
              {["Aadhaar", "PAN", "Passport", "Driving License", "Voter ID", "Other"].map(
                (t) => (
                  <option key={t}>{t}</option>
                ),
              )}
            </select>
            <input
              className={`${editInputCls} w-36`}
              placeholder="ID number"
              value={o.id_number ?? ""}
              onChange={(e) => set(i, { id_number: e.target.value })}
            />
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
function ActualTimeRow(props: {
  label: string
  reservation: string
  field: "actual_check_in" | "actual_check_out"
  value?: string | null
  onSaved: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [val, setVal] = useState("")
  const shown = props.value ? props.value.slice(0, 16).replace("T", " ") : "—"
  return (
    <div className="flex items-baseline justify-between gap-2 py-0.5 text-sm">
      <span className="shrink-0 text-zinc-500">{props.label}</span>
      {editing ? (
        <span className="flex items-center gap-1 print:hidden">
          <input type="datetime-local" className="rounded-lg border border-zinc-300 px-2 py-1 text-sm"
            value={val} onChange={(e) => setVal(e.target.value)} />
          <Button variant="outline" className="!px-2 !py-1 text-xs"
            onClick={async () => {
              if (!val) return
              await call("kamra.api.set_actual_times", {
                reservation: props.reservation,
                [props.field]: val.replace("T", " ") + ":00",
              })
              setEditing(false)
              props.onSaved()
            }}>
            Save
          </Button>
          <button className="text-xs text-zinc-400" onClick={() => setEditing(false)}>✕</button>
        </span>
      ) : (
        <span className="text-right font-medium">
          {shown}
          <button
            className="ml-2 text-xs font-medium text-brand-700 hover:underline print:hidden"
            onClick={() => {
              setVal((props.value || new Date().toISOString()).slice(0, 16))
              setEditing(true)
            }}>
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
  const [d, setD] = useState<Grc | null>(null)

  const load = useCallback(() => {
    if (name)
      call<Grc>("kamra.api.registration_card", { reservation: name }).then(setD)
  }, [name])

  useEffect(load, [load])

  if (!d) return <p className="py-10 text-center text-zinc-400">Loading…</p>

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-4 flex items-center justify-between print:hidden">
        <Link to="/" className="inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-800">
          <ArrowLeft className="size-4" aria-hidden /> Today
        </Link>
        <Button onClick={() => window.print()}>
          <Printer className="size-4" aria-hidden /> Print GRC
        </Button>
      </div>

      <div className="rounded-xl border border-zinc-200 bg-white p-6 print:border-0">
        <div className="mb-5 flex items-start justify-between border-b border-zinc-300 pb-4">
          <div>
            <h1 className="text-lg font-bold">{d.property.property_name}</h1>
            <p className="text-xs text-zinc-500">{d.property.address}</p>
            <p className="text-xs text-zinc-500">
              {d.property.gstin && <>GSTIN {d.property.gstin} · </>}
              {d.property.phone}
            </p>
          </div>
          <div className="text-right">
            <p className="text-sm font-semibold">GUEST REGISTRATION CARD</p>
            <p className="text-xs text-zinc-500">{d.reservation.name}</p>
          </div>
        </div>

        <div className="grid gap-x-8 sm:grid-cols-2">
          <div>
            <h2 className="mb-1 text-xs font-semibold uppercase tracking-wider text-zinc-400">Guest</h2>
            <Row label="Name" value={d.guest.full_name} />
            <Row label="Phone" value={d.guest.phone} />
            <Row label="Email" value={d.guest.email} />
            <Row label="Nationality" value={d.guest.nationality} />
            <Row label="ID" value={d.guest.id_type ? `${d.guest.id_type} · ${d.guest.id_number ?? ""}` : null} />
            <div className="mt-2 grid grid-cols-2 gap-3 print:grid-cols-2">
              {([["id", "ID document", d.guest.id_file],
                 ["address", "Address proof", d.guest.address_proof_file]] as const).map(([kind, label, url]) => (
                <div key={kind}>
                  <span className="text-xs font-medium uppercase tracking-wide text-zinc-400">{label}</span>
                  {url ? (
                    <a href={url} target="_blank" rel="noreferrer">
                      <img src={url} alt={label}
                        className="mt-1 max-h-28 rounded-lg border border-zinc-200 object-contain" />
                    </a>
                  ) : (
                    <p className="mt-1 text-xs text-zinc-400 print:hidden">Not on file</p>
                  )}
                  <label className="mt-1 inline-block cursor-pointer text-xs font-medium text-brand-700 hover:underline print:hidden">
                    {url ? "Replace with newer" : "Capture / upload"}
                    <input type="file" accept="image/*" capture="environment" className="hidden"
                      onChange={async (e) => {
                        const f = e.target.files?.[0]
                        if (!f || !d.guest.guest_id) return
                        await call("kamra.api.upload_guest_document", {
                          guest: d.guest.guest_id, kind,
                          image: await fileToDataUrl(f),
                        })
                        load()
                      }} />
                  </label>
                </div>
              ))}
            </div>
            <Row label="Address" value={d.guest.address} />
            {d.reservation.company && <Row label="Company" value={d.reservation.company} />}
            {d.reservation.booked_by_name && (
              <Row label="Booked by" value={d.reservation.booked_by_name} />
            )}
          </div>
          <div>
            <h2 className="mb-1 text-xs font-semibold uppercase tracking-wider text-zinc-400">Stay</h2>
            <Row label="Room" value={`${d.reservation.room} · ${d.reservation.room_type}`} />
            <Row label="Check-in" value={`${d.reservation.check_in_date} (${d.property.checkin_time.slice(0, 5)})`} />
            <Row label="Check-out" value={`${d.reservation.check_out_date} (${d.property.checkout_time.slice(0, 5)})`} />
            <ActualTimeRow label="Actual check-in" reservation={d.reservation.name}
              field="actual_check_in" value={d.reservation.actual_check_in} onSaved={load} />
            <ActualTimeRow label="Actual check-out" reservation={d.reservation.name}
              field="actual_check_out" value={d.reservation.actual_check_out} onSaved={load} />
            <Row label="Nights" value={String(d.reservation.nights)} />
            <Row label="Guests" value={`${d.reservation.adults} adult(s)${d.reservation.children ? ` + ${d.reservation.children} child` : ""}`} />
            <Row label="Stay total" value={`₹${inr(d.reservation.rate_total)} (incl. GST)`} />
            <Row label="Advance paid" value={`₹${inr(d.reservation.advance_paid)}`} />
            {d.money && (
              <>
                <Row label="Ledger" value={`Paid ₹${inr(d.money.paid_total)} · Balance ₹${inr(d.money.balance)}` +
                  (d.money.deposit_held ? ` · Deposit held ₹${inr(d.money.deposit_held)}` : "")} />
                <div className="print:hidden">
                  <a className="text-sm font-medium text-brand-700 hover:underline"
                    href={toFullPath(`/billing/${encodeURIComponent(d.money.folio)}`)}>
                    Open folio — collect advance / deposit, settle & generate the invoice →
                  </a>
                </div>
              </>
            )}
            <Row label="Source" value={d.reservation.source} />
          </div>
        </div>

        {d.reservation.special_requests && (
          <p className="mt-3 text-sm"><span className="text-zinc-500">Requests: </span>{d.reservation.special_requests}</p>
        )}

        <div className="mt-5">
          <h2 className="mb-1 text-xs font-semibold uppercase tracking-wider text-zinc-400">
            Occupants
          </h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-300 text-left text-[11px] uppercase tracking-wider text-zinc-400">
                <th className="py-1 pr-3 font-medium">Name</th>
                <th className="py-1 pr-3 font-medium">Age</th>
                <th className="py-1 pr-3 font-medium">Gender</th>
                <th className="py-1 pr-3 font-medium">Nationality</th>
                <th className="py-1 font-medium">ID</th>
              </tr>
            </thead>
            <tbody>
              {d.occupants.map((o, i) => (
                <tr key={i} className="border-b border-zinc-200">
                  <td className="py-1.5 pr-3 font-medium">{o.full_name}</td>
                  <td className="py-1.5 pr-3">{o.age ?? "-"}</td>
                  <td className="py-1.5 pr-3">{o.gender || "-"}</td>
                  <td className="py-1.5 pr-3">{o.nationality || "-"}</td>
                  <td className="py-1.5">
                    {o.id_type ? `${o.id_type} · ${o.id_number ?? ""}` : "-"}
                  </td>
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
        </div>

        <p className="mt-6 text-[11px] leading-relaxed text-zinc-500">
          I certify the above details are correct. I agree to the hotel's
          policies on check-out time, damage to property and applicable
          taxes, and consent to my details being kept in the guest register
          as required by law.
        </p>

        <div className="mt-10 grid grid-cols-2 gap-8">
          <div className="border-t border-zinc-400 pt-1 text-center text-xs text-zinc-500">
            Guest signature
          </div>
          <div className="border-t border-zinc-400 pt-1 text-center text-xs text-zinc-500">
            Front desk (name & sign)
          </div>
        </div>
      </div>

      {name && (
        <OccupantsEditor
          reservation={name}
          occupants={d.occupants}
          onSaved={load}
        />
      )}
    </div>
  )
}
