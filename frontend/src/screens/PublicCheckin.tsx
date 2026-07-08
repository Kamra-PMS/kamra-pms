import { useEffect, useState } from "react"
import { CalendarDays, Check, Clock } from "lucide-react"
import { useParams } from "react-router-dom"
import { call } from "../lib/api"
import { Button } from "../components/ui/button"
import { SignaturePad } from "../components/SignaturePad"

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
    nationality: string | null
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
  const [consent, setConsent] = useState(false)

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
            <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3">
              <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                Registration card - your signature
              </span>
              <p className="mb-2 text-xs text-zinc-500">
                I confirm the details above are correct and agree to the hotel's
                registration terms and house rules.
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
