import { useEffect, useState } from "react"
import { CalendarDays, Check, Clock } from "lucide-react"
import { useParams } from "react-router-dom"
import { call } from "../lib/api"
import { Button } from "../components/ui/button"
import { SignaturePad } from "../components/SignaturePad"
import { IdDocumentField } from "../components/IdDocumentField"
import { GuestLaundryCard } from "./laundry/GuestLaundryCard"


/** Downscale a picked/captured photo so the upload stays small (max edge
 * 1600px, JPEG) - phone camera originals are 5-12 MB otherwise. */
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

function DocCapture(props: {
  title: string
  note: string
  value: string
  onChange: (v: string) => void
  onFile: (f: File) => Promise<string>
  hasExisting?: boolean
}) {
  const { title, note, value, onChange, onFile, hasExisting } = props
  return (
    <div className="rounded-xl border border-zinc-200 p-3">
      <span className="block text-sm font-medium text-zinc-600">{title}</span>
      <p className="mb-2 mt-0.5 text-xs text-zinc-400">{note}</p>
      {hasExisting && !value && (
        <p className="mb-2 rounded-lg bg-emerald-50 px-2.5 py-1.5 text-xs text-emerald-800">
          ✓ We already have this from your last visit — we'll use it.
          Add a photo below only to replace it with a newer one.
        </p>
      )}
      {value ? (
        <div className="flex items-center gap-3">
          <img src={value} alt={title} className="h-20 rounded-lg border border-zinc-200 object-cover" />
          <button type="button" className="text-sm font-medium text-rose-600 hover:underline"
            onClick={() => onChange("")}>
            Remove & retake
          </button>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          <label className="cursor-pointer rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white">
            Take photo
            <input type="file" accept="image/*" capture="environment" className="hidden"
              onChange={async (e) => {
                const f = e.target.files?.[0]
                if (f) onChange(await onFile(f))
              }} />
          </label>
          <label className="cursor-pointer rounded-lg border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700">
            Upload image
            <input type="file" accept="image/*" className="hidden"
              onChange={async (e) => {
                const f = e.target.files?.[0]
                if (f) onChange(await onFile(f))
              }} />
          </label>
        </div>
      )}
    </div>
  )
}

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3.5 py-2.5 text-base " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

interface Info {
  property: {
    property_name: string
    logo_url: string | null
    city: string
    checkin_time: string
    phone: string | null
    house_rules: string | null
    pets_policy: string | null
    children_policy: string | null
    extra_bed_policy: string | null
    id_retention: string
  }
  stay: {
    reservation: string
    room_type: string
    check_in_date: string
    check_out_date: string
    nights: number
    adults: number
    children: number
    status: string
  }
  guest: {
    full_name: string
    phone: string | null
    email: string | null
    id_type: string | null
    has_id_file?: boolean
    has_address_file?: boolean
    nationality: string | null
    has_id_document: boolean
    id_document_on: string
  }
}

const ID_TYPES = ["Aadhaar", "Passport", "Driving License", "Voter ID", "Other"]

export default function PublicCheckin() {
  const { token } = useParams()
  const [info, setInfo] = useState<Info | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)
  const [form, setForm] = useState({
    id_type: "Aadhaar", id_number: "", email: "", nationality: "Indian",
    address_line: "", city: "", eta: "", special_requests: "",
  })
  const [signature, setSignature] = useState("")
  const [idImage, setIdImage] = useState("") // data-URL of the ID photo
  const [addrImage, setAddrImage] = useState("") // data-URL of the address proof
  const [consent, setConsent] = useState(false)
  const [idUploaded, setIdUploaded] = useState(false)

  useEffect(() => {
    if (!token) return
    call<Info>("kamra.public_api.precheckin_info", { token })
      .then((i) => {
        setInfo(i)
        setForm((f) => ({
          ...f,
          email: i.guest.email ?? "",
          id_type: i.guest.id_type || "Aadhaar",
          nationality: i.guest.nationality ?? "Indian",
        }))
        // a boolean, never a URL - the guest can't be shown their own photo
        // back (Frappe refuses a Guest session any private file), so after a
        // reload this is all we can honestly say
        setIdUploaded(i.guest.has_id_document)
        if (i.stay.status === "Submitted") setDone(true)
      })
      .catch(() => setError("This check-in link isn't valid. Please contact the hotel."))
  }, [token])

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      await call("kamra.public_api.precheckin_submit", {
        token, ...form, signature, consent: consent ? 1 : 0,
        id_image: idImage || "",
        address_image: addrImage || "",
      })
      setDone(true)
    } catch {
      setError("Couldn't save - please check the details and try again.")
    } finally {
      setBusy(false)
    }
  }

  if (error && !info)
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 px-4">
        <p className="text-zinc-500">{error}</p>
      </div>
    )
  if (!info)
    return <p className="py-20 text-center text-zinc-400">Loading…</p>

  const { property: p, stay, guest } = info

  return (
    <div className="min-h-screen bg-zinc-50 px-4 py-8">
      <div className="mx-auto max-w-lg">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex size-12 items-center justify-center overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm">
            {p.logo_url ? (
              <img src={p.logo_url} alt="" className="size-full object-contain p-1" />
            ) : (
              <span className="text-lg font-bold text-brand-700">
                {p.property_name.split(" ").map((w) => w[0]).slice(0, 2).join("")}
              </span>
            )}
          </div>
          <div>
            <h1 className="text-lg font-semibold">{p.property_name}</h1>
            <p className="text-sm text-zinc-500">Online check-in · {p.city}</p>
          </div>
        </div>

        <div className="mb-5 rounded-xl border border-zinc-200 bg-white p-4 text-sm shadow-sm">
          <p className="font-medium">
            {guest.full_name} · {stay.room_type} room
          </p>
          <p className="mt-1 flex items-center gap-2 text-zinc-500">
            <CalendarDays className="size-4" aria-hidden />
            {stay.check_in_date} → {stay.check_out_date} · {stay.nights} night
            {stay.nights === 1 ? "" : "s"} · {stay.adults} adult
            {stay.adults === 1 ? "" : "s"}
            {stay.children ? ` + ${stay.children} child` : ""}
          </p>
          <p className="mt-1 flex items-center gap-2 text-zinc-500">
            <Clock className="size-4" aria-hidden />
            Rooms ready from {p.checkin_time.slice(0, 5)}
          </p>
        </div>

        {/* self-hides unless the reservation is actually Checked In —
            stay.status here is the pre-check-in status, not the stay status */}
        {token && <GuestLaundryCard token={token} />}

        {done ? (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-5 text-emerald-800">
            <p className="flex items-center gap-2 text-lg font-semibold">
              <Check className="size-5" aria-hidden />
              You're checked in online
            </p>
            <p className="mt-1 text-sm">
              Skip the paperwork at the desk - just show your ID on arrival
              and pick up the key. See you soon!
            </p>
          </div>
        ) : (
          <div className="space-y-4 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
            <p className="text-sm text-zinc-500">
              Save time at the desk - fill your details now, show the ID once
              on arrival.
            </p>
            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-zinc-600">ID type</span>
                <select className={inputCls} value={form.id_type}
                  onChange={(e) => setForm({ ...form, id_type: e.target.value })}>
                  {ID_TYPES.map((t) => <option key={t}>{t}</option>)}
                </select>
              </label>
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-zinc-600">ID number</span>
                <input className={inputCls} value={form.id_number}
                  onChange={(e) => setForm({ ...form, id_number: e.target.value })} />
              </label>
            </div>

            {/* Optional, and it stays optional: the submit button below never
                mentions this. A guest on a locked-down phone or a bad lobby
                connection must still be able to pre-register - gating here
                would just move the queue back to the desk. */}
            <IdDocumentField
              method="kamra.public_api.precheckin_upload_id"
              params={{ token }}
              uploaded={idUploaded}
              onUploaded={() => setIdUploaded(true)}
              label="Add a photo of your ID (optional)"
              hint="It speeds up arrival. Bring the original card either way."
            />
            <p className="-mt-1 text-xs text-zinc-500">
              {p.id_retention === "Verify & Discard"
                ? "Your ID photo is used only to confirm your identity at arrival, and is permanently deleted when you check out. Only hotel staff can see it."
                : "Your ID photo is kept with the guest register the hotel is required by law to maintain. Only hotel staff can see it."}
              {form.id_type === "Aadhaar" && " A masked Aadhaar (last 4 digits showing) is fine."}
            </p>

            <DocCapture
              title="Address proof (optional)"
              note="Only if your address proof is a different document from your ID."
              value={addrImage}
              onChange={setAddrImage}
              onFile={fileToDataUrl}
              hasExisting={info?.guest?.has_address_file}
            />

            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-zinc-600">Email</span>
                <input className={inputCls} type="email" value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })} />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-zinc-600">Nationality</span>
                <input className={inputCls} value={form.nationality}
                  onChange={(e) => setForm({ ...form, nationality: e.target.value })} />
              </label>
            </div>
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-zinc-600">Address</span>
              <input className={inputCls} value={form.address_line}
                placeholder="Street, area"
                onChange={(e) => setForm({ ...form, address_line: e.target.value })} />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-zinc-600">City</span>
                <input className={inputCls} value={form.city}
                  onChange={(e) => setForm({ ...form, city: e.target.value })} />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-zinc-600">Arriving around</span>
                <input className={inputCls} value={form.eta} placeholder="e.g. 14:30"
                  onChange={(e) => setForm({ ...form, eta: e.target.value })} />
              </label>
            </div>
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-zinc-600">Anything we should know?</span>
              <textarea className={inputCls} rows={2} value={form.special_requests}
                onChange={(e) => setForm({ ...form, special_requests: e.target.value })} />
            </label>
            {(p.house_rules || p.pets_policy || p.children_policy || p.extra_bed_policy) && (
              <details className="group rounded-lg border border-zinc-200 bg-zinc-50/50 p-3 text-xs">
                <summary className="flex items-center justify-between font-medium text-zinc-700 cursor-pointer select-none [&::-webkit-details-marker]:hidden">
                  <span>View Hotel House Rules & Policies</span>
                  <span className="transition group-open:rotate-180">
                    <svg fill="none" height="16" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" width="16" className="size-3.5 text-zinc-500"><polyline points="6 9 12 15 18 9"></polyline></svg>
                  </span>
                </summary>
                <div className="mt-2 space-y-2 border-t border-zinc-200/60 pt-2 text-zinc-600 leading-relaxed whitespace-pre-line">
                  {p.house_rules && (
                    <div>
                      <span className="font-semibold text-zinc-700">House Rules: </span>
                      {p.house_rules}
                    </div>
                  )}
                  {p.pets_policy && (
                    <div>
                      <span className="font-semibold text-zinc-700">Pets Policy: </span>
                      {p.pets_policy}
                    </div>
                  )}
                  {p.children_policy && (
                    <div>
                      <span className="font-semibold text-zinc-700">Children Policy: </span>
                      {p.children_policy}
                    </div>
                  )}
                  {p.extra_bed_policy && (
                    <div>
                      <span className="font-semibold text-zinc-700">Extra Bed Policy: </span>
                      {p.extra_bed_policy}
                    </div>
                  )}
                </div>
              </details>
            )}

            <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3">
              <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                Registration card - your signature
              </span>
              {/* One instrument, widened - not a second checkbox. The notice
                  has to cover the ID photo before it's collected, but adding
                  another gate to the form whose completion rate is the whole
                  point would cost more than it protects. */}
              <p className="mb-2 text-xs text-zinc-500">
                I confirm the details above are correct, agree to the hotel's
                registration terms and house rules, and consent to the hotel
                holding a copy of my ID for this stay.
              </p>
              <SignaturePad onChange={setSignature} />
              <label className="mt-2 flex items-start gap-2 text-xs text-zinc-600">
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                />
                I accept the registration declaration.
              </label>
            </div>
            {error && (
              <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {error}
              </div>
            )}
            <Button
              className="w-full justify-center py-2.5 text-base"
              disabled={busy || !form.id_number || !signature || !consent}
              onClick={submit}
            >
              {busy ? "Saving…" : "Sign & complete check-in"}
            </Button>
            <p className="text-center text-xs text-zinc-400">
              Your details and signature form the guest register required by law.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
