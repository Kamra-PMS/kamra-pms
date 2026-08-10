import { useState } from "react"
import { Check, Plus, Trash2 } from "lucide-react"
import { call, setCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { cn } from "../lib/utils"
import { cur } from "../lib/money"

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3.5 py-2.5 text-base " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

const STEPS = ["Property", "Room Types", "Rooms", "Meal Plans", "Review", "Import"]

interface RoomTypeRow {
  code: string
  name: string
  base_price: string
  adults: string
  numbers: string // comma-separated room numbers, edited on the Rooms step
  room_category: string
  free_child_age: string
  extra_adult_price: string
  air_conditioning: string
}

export default function Setup() {
  const [step, setStep] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [createdProperty, setCreatedProperty] = useState<string | null>(null)
  const [importReport, setImportReport] = useState<{
    created: number
    history?: number
    errors: { row: number; guest: string; error: string }[]
  } | null>(null)
  const [preset, setPreset] = useState("auto")
  const [preview, setPreview] = useState<{
    mapping: Record<string, string>
    unmapped: string[]
    date_format: string
    ok: number
    skipped: number
    issues: { row: number; guest: string; error: string }[]
  } | null>(null)

  const [prop, setProp] = useState({
    property_name: "", city: "", state: "", phone: "", gstin: "",
    checkin_time: "14:00:00",
    checkout_time: "11:00:00",
    minimum_nights: "1",
    booking_payment_mode: "Advance percent",
    advance_percent: "100",
    security_deposit_amount: "5000",
  })
  const [roomTypes, setRoomTypes] = useState<RoomTypeRow[]>([
    { code: "STD", name: "Standard", base_price: "2500", adults: "2", numbers: "", room_category: "Private", free_child_age: "6", extra_adult_price: "2100", air_conditioning: "AC" },
  ])
  const [mealPlans, setMealPlans] = useState([
    { code: "EP", label: "Room Only", price_per_adult: "0", on: true },
    { code: "CP", label: "Breakfast Included", price_per_adult: "300", on: true },
    { code: "MAP", label: "Breakfast + Dinner", price_per_adult: "700", on: false },
  ])
  const [csv, setCsv] = useState("")
 
  const setRT = (i: number, k: keyof RoomTypeRow, v: string) =>
    setRoomTypes((rows) => rows.map((r, j) => (j === i ? { ...r, [k]: v } : r)))
 
  async function create() {
    setBusy(true)
    setError(null)
    try {
      const payload = {
        property: Object.fromEntries(
          Object.entries(prop)
            .filter(([, v]) => v)
            .map(([k, v]) => {
              if (["minimum_nights", "advance_percent", "security_deposit_amount"].includes(k)) {
                return [k, Number(v) || 0];
              }
              return [k, v];
            })
        ),
        room_types: roomTypes
          .filter((r) => r.code && r.name && r.base_price)
          .map((r) => ({
            code: r.code.toUpperCase(),
            name: r.name,
            base_price: Number(r.base_price),
            adults: Number(r.adults) || 2,
            room_category: r.room_category,
            free_child_age: Number(r.free_child_age) || 0,
            extra_adult_price: Number(r.extra_adult_price) || 0,
            air_conditioning: r.room_category === "Villa" ? "" : r.air_conditioning,
          })),
        rooms: roomTypes
          .filter((r) => r.numbers.trim())
          .map((r) => ({
            room_type_code: r.code.toUpperCase(),
            numbers: r.numbers.split(",").map((n) => n.trim()).filter(Boolean),
          })),
        meal_plans: mealPlans
          .filter((m) => m.on)
          .map((m, i) => ({
            code: m.code, label: m.label,
            price_per_adult: Number(m.price_per_adult) || 0,
            is_default: i === 1 ? 1 : 0,
          })),
      }
      const res = await call<{ property: string }>(
        "kamra.api.setup_property", { payload },
      )
      setCreatedProperty(res.property)
      setCurrentProperty(res.property)
      setStep(5)
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  async function previewImport() {
    setBusy(true)
    setError(null)
    setImportReport(null)
    try {
      const res = await call<NonNullable<typeof preview>>(
        "kamra.migrate.preview_import",
        { property: createdProperty, csv_text: csv, preset },
      )
      setPreview(res)
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  async function runImport() {
    setBusy(true)
    setError(null)
    try {
      const res = await call<{
        created: number
        history: number
        errors: { row: number; guest: string; error: string }[]
      }>("kamra.migrate.run_import", {
        property: createdProperty, csv_text: csv, preset,
      })
      setImportReport(res)
      setPreview(null)
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-1 text-lg font-semibold">Set up a new property</h1>
      <p className="mb-4 text-sm text-zinc-500">
        Five minutes to a working hotel. Prefer talking? Connect Claude to
        Kamra's MCP and say "onboard my hotel" - same result.
      </p>

      <ol className="mb-6 flex flex-wrap gap-2">
        {STEPS.map((s, i) => (
          <li
            key={s}
            className={cn(
              "flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium",
              i === step
                ? "bg-brand-600 text-white"
                : i < step || (createdProperty && i <= 4)
                  ? "bg-brand-50 text-brand-700"
                  : "bg-zinc-100 text-zinc-400",
            )}
          >
            {(i < step || (createdProperty && i <= 4)) && (
              <Check className="size-3" aria-hidden />
            )}
            {s}
          </li>
        ))}
      </ol>

      <Card>
        <CardHeader>
          <CardTitle>{STEPS[step]}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {step === 0 && (
            <>
              {(
                [
                  ["property_name", "Property name *", "text", "Sunrise Residency"],
                  ["city", "City", "text", "Bengaluru"],
                  ["state", "State", "text", "Karnataka"],
                  ["phone", "Phone", "text", "+91 …"],
                  ["gstin", "GSTIN", "text", "29XXXXX…"],
                  ["checkin_time", "Check-in Time", "time", ""],
                  ["checkout_time", "Check-out Time", "time", ""],
                  ["minimum_nights", "Minimum Nights", "number", "1"],
                  ["booking_payment_mode", "Booking Payment Mode", "select", ""],
                  ["advance_percent", "Advance Percent", "number", "100"],
                  ["security_deposit_amount", "Security Deposit Amount", "number", "5000"],
                ] as const
              ).map(([k, label, type, ph]) => (
                <label key={k} className="block">
                  <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                    {label}
                  </span>
                  {k === "booking_payment_mode" ? (
                    <select
                      className={cn(inputCls, "bg-white")}
                      value={prop[k]}
                      onChange={(e) => setProp({ ...prop, [k]: e.target.value })}
                    >
                      <option value="Full payment">Full payment</option>
                      <option value="Advance percent">Advance percent</option>
                      <option value="Pay at hotel">Pay at hotel</option>
                    </select>
                  ) : type === "time" ? (
                    <select
                      className={cn(inputCls, "bg-white")}
                      value={prop[k]}
                      onChange={(e) => setProp({ ...prop, [k]: e.target.value })}
                    >
                      {[
                        { label: "12:00 AM", value: "00:00:00" },
                        { label: "1:00 AM", value: "01:00:00" },
                        { label: "2:00 AM", value: "02:00:00" },
                        { label: "3:00 AM", value: "03:00:00" },
                        { label: "4:00 AM", value: "04:00:00" },
                        { label: "5:00 AM", value: "05:00:00" },
                        { label: "6:00 AM", value: "06:00:00" },
                        { label: "7:00 AM", value: "07:00:00" },
                        { label: "8:00 AM", value: "08:00:00" },
                        { label: "9:00 AM", value: "09:00:00" },
                        { label: "10:00 AM", value: "10:00:00" },
                        { label: "11:00 AM", value: "11:00:00" },
                        { label: "12:00 PM", value: "12:00:00" },
                        { label: "1:00 PM", value: "13:00:00" },
                        { label: "2:00 PM", value: "14:00:00" },
                        { label: "3:00 PM", value: "15:00:00" },
                        { label: "4:00 PM", value: "16:00:00" },
                        { label: "5:00 PM", value: "17:00:00" },
                        { label: "6:00 PM", value: "18:00:00" },
                        { label: "7:00 PM", value: "19:00:00" },
                        { label: "8:00 PM", value: "20:00:00" },
                        { label: "9:00 PM", value: "21:00:00" },
                        { label: "10:00 PM", value: "22:00:00" },
                        { label: "11:00 PM", value: "23:00:00" }
                      ].map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type={type}
                      className={inputCls}
                      placeholder={ph}
                      value={prop[k]}
                      onChange={(e) => setProp({ ...prop, [k]: e.target.value })}
                    />
                  )}
                </label>
              ))}
            </>
          )}

          {step === 1 && (
            <div className="space-y-4">
              {roomTypes.map((rt, i) => (
                <div key={i} className="space-y-3 p-4 border border-zinc-200 rounded-xl bg-zinc-50/50 relative">
                  {roomTypes.length > 1 && (
                    <Button variant="ghost" aria-label="Remove" className="absolute top-2 right-2"
                      onClick={() => setRoomTypes((r) => r.filter((_, j) => j !== i))}>
                      <Trash2 className="size-4 text-rose-500" />
                    </Button>
                  )}
                  <label className="block">
                    <span className="mb-1 block text-xs font-semibold text-zinc-500">Room Type Code (e.g. STD)</span>
                    <input className={inputCls} placeholder="CODE"
                      value={rt.code} onChange={(e) => setRT(i, "code", e.target.value)} />
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-xs font-semibold text-zinc-500">Room Type Name (e.g. Standard Room)</span>
                    <input className={inputCls} placeholder="Name (Deluxe)"
                      value={rt.name} onChange={(e) => setRT(i, "name", e.target.value)} />
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-xs font-semibold text-zinc-500">Base Price / Night</span>
                    <input className={inputCls} type="number" placeholder={`${cur()}/night`}
                      value={rt.base_price} onChange={(e) => setRT(i, "base_price", e.target.value)} />
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-xs font-semibold text-zinc-500">Base Occupancy (Adults)</span>
                    <input className={inputCls} type="number" placeholder="Adults"
                      value={rt.adults} onChange={(e) => setRT(i, "adults", e.target.value)} />
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-xs font-semibold text-zinc-500">Category</span>
                    <select className={cn(inputCls, "bg-white")} value={rt.room_category}
                      onChange={(e) => setRT(i, "room_category", e.target.value)}>
                      <option value="Private">Private</option>
                      <option value="Villa">Villa</option>
                      <option value="Shared">Shared</option>
                    </select>
                  </label>
                  {rt.room_category !== "Villa" && (
                    <label className="block">
                      <span className="mb-1 block text-xs font-semibold text-zinc-500">Air Conditioning</span>
                      <select className={cn(inputCls, "bg-white")} value={rt.air_conditioning}
                        onChange={(e) => setRT(i, "air_conditioning", e.target.value)}>
                        <option value="AC">AC</option>
                        <option value="Non AC">Non AC</option>
                      </select>
                    </label>
                  )}
                  <label className="block">
                    <span className="mb-1 block text-xs font-semibold text-zinc-500">Free Child Age Limit (Years)</span>
                    <input className={inputCls} type="number" placeholder="6"
                      value={rt.free_child_age} onChange={(e) => setRT(i, "free_child_age", e.target.value)} />
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-xs font-semibold text-zinc-500">Extra Adult Price / Night</span>
                    <input className={inputCls} type="number" placeholder="2100"
                      value={rt.extra_adult_price} onChange={(e) => setRT(i, "extra_adult_price", e.target.value)} />
                  </label>
                </div>
              ))}
              <Button variant="outline"
                onClick={() => setRoomTypes((r) => [...r,
                  { code: "", name: "", base_price: "", adults: "2", numbers: "", room_category: "Private", free_child_age: "6", extra_adult_price: "2100", air_conditioning: "AC" }])}>
                <Plus className="size-4" aria-hidden /> Add room type
              </Button>
            </div>
          )}

          {step === 2 && (
            <>
              <p className="text-sm text-zinc-500">
                Room numbers per type, comma-separated.
              </p>
              {roomTypes.filter((r) => r.code).map((rt, i) => (
                <label key={i} className="block">
                  <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                    {rt.name || rt.code}
                  </span>
                  <input className={inputCls} placeholder="101, 102, 103"
                    value={rt.numbers}
                    onChange={(e) => setRT(i, "numbers", e.target.value)} />
                </label>
              ))}
            </>
          )}

          {step === 3 && (
            <>
              {mealPlans.map((mp, i) => (
                <div key={mp.code} className="flex items-center gap-3">
                  <input type="checkbox" className="size-4 accent-brand-600"
                    checked={mp.on}
                    onChange={(e) => setMealPlans((m) =>
                      m.map((x, j) => (j === i ? { ...x, on: e.target.checked } : x)))} />
                  <span className="w-40 text-sm">{mp.label} ({mp.code})</span>
                  <input className={cn(inputCls, "w-32")} type="number"
                    value={mp.price_per_adult}
                    onChange={(e) => setMealPlans((m) =>
                      m.map((x, j) => (j === i ? { ...x, price_per_adult: e.target.value } : x)))} />
                  <span className="text-xs text-zinc-400">{cur()}/adult/night</span>
                </div>
              ))}
            </>
          )}

          {step === 4 && (
            <div className="space-y-2 text-sm">
              <p><span className="font-medium">{prop.property_name}</span>
                {prop.city && <span className="text-zinc-500"> · {prop.city}</span>}</p>
              <div className="flex flex-wrap gap-1.5">
                {roomTypes.filter((r) => r.code).map((r) => (
                  <Badge key={r.code} tone="zinc">
                    {r.name} {cur()}{r.base_price} ×{r.numbers.split(",").filter((x) => x.trim()).length}
                  </Badge>
                ))}
                {mealPlans.filter((m) => m.on).map((m) => (
                  <Badge key={m.code} tone="brand">{m.code}</Badge>
                ))}
              </div>
              <p className="text-zinc-500">
                Creating sets this as your active property. Rates, seasons,
                vouchers and guardrails can be added later from Revenue.
              </p>
            </div>
          )}

          {step === 5 && (
            <div className="space-y-4">
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
                <span className="font-semibold">{createdProperty}</span> is live.
                Bring your existing bookings over - paste a CSV, or let the AI
                migration assistant do the mapping for you via MCP.
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <select
                  className={cn(inputCls, "w-auto")}
                  value={preset}
                  onChange={(e) => { setPreset(e.target.value); setPreview(null) }}
                  aria-label="Which system is this export from?"
                >
                  <option value="auto">Auto-detect format</option>
                  <option value="ezee">eZee export</option>
                  <option value="cloudbeds">Cloudbeds export</option>
                </select>
                <label className="cursor-pointer rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm font-medium text-zinc-700 hover:border-brand-400">
                  Upload CSV file
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    className="hidden"
                    onChange={async (e) => {
                      const f = e.target.files?.[0]
                      if (f) { setCsv(await f.text()); setPreview(null) }
                    }}
                  />
                </label>
                <span className="text-xs text-zinc-400">or paste it below</span>
              </div>
              <label className="block">
                <textarea
                  className={cn(inputCls, "font-mono text-xs")}
                  rows={7}
                  placeholder={
                    "Guest Name,Mobile,Room Type,Arrival Date,Departure Date,Adults,Status\n" +
                    '"Rao, Asha",+91 98xxxx,Deluxe,25/12/2025,28/12/2025,2,Checked Out'
                  }
                  value={csv}
                  onChange={(e) => { setCsv(e.target.value); setPreview(null) }}
                />
              </label>
              {preview && (
                <div className="space-y-2 rounded-lg bg-zinc-50 px-4 py-3 text-sm">
                  <p>
                    <span className="font-medium text-emerald-700">{preview.ok} ready to import</span>
                    {preview.skipped > 0 && (
                      <span className="ml-2 font-medium text-rose-600">{preview.skipped} will be skipped</span>
                    )}
                    <span className="ml-2 text-zinc-400">dates read as {preview.date_format}</span>
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {Object.entries(preview.mapping).map(([k, v]) => (
                      <Badge key={k} tone="zinc">{v} → {k.replace(/_/g, " ")}</Badge>
                    ))}
                    {preview.unmapped.map((h) => (
                      <Badge key={h} tone="amber">{h} (ignored)</Badge>
                    ))}
                  </div>
                  {preview.issues.map((iss) => (
                    <p key={iss.row} className="text-rose-600">
                      Row {iss.row}{iss.guest ? ` (${iss.guest})` : ""}: {iss.error}
                    </p>
                  ))}
                </div>
              )}
              {importReport && (
                <div className="rounded-lg bg-zinc-50 px-4 py-3 text-sm">
                  <p className="font-medium text-emerald-700">
                    {importReport.created} booking{importReport.created === 1 ? "" : "s"} imported
                    {importReport.history ? ` (${importReport.history} as past-stay history)` : ""}
                  </p>
                  {importReport.errors.map((e) => (
                    <p key={e.row} className="text-rose-600">
                      Row {e.row} ({e.guest}): {e.error}
                    </p>
                  ))}
                </div>
              )}
            </div>
          )}

          {error && (
            <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {error}
            </div>
          )}

          <div className="flex justify-between pt-2">
            {step > 0 && step < 5 ? (
              <Button variant="outline" onClick={() => setStep(step - 1)}>
                Back
              </Button>
            ) : <span />}
            {step < 4 && (
              <Button
                disabled={step === 0 && !prop.property_name}
                onClick={() => setStep(step + 1)}
              >
                Continue
              </Button>
            )}
            {step === 4 && (
              <Button disabled={busy} onClick={create}>
                {busy ? "Creating…" : "Create property"}
              </Button>
            )}
            {step === 5 && !preview && (
              <Button disabled={busy || !csv.trim()} onClick={previewImport}>
                {busy ? "Checking…" : "Preview import"}
              </Button>
            )}
            {step === 5 && preview && (
              <Button disabled={busy || preview.ok === 0} onClick={runImport}>
                {busy ? "Importing…" : `Import ${preview.ok} booking${preview.ok === 1 ? "" : "s"}`}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
