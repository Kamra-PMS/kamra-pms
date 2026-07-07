import { useState } from "react"
import { Check, Plus, Trash2 } from "lucide-react"
import { call, setCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { cn } from "../lib/utils"

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
}

export default function Setup() {
  const [step, setStep] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [createdProperty, setCreatedProperty] = useState<string | null>(null)
  const [importReport, setImportReport] = useState<{
    created: number
    errors: { row: number; guest: string; error: string }[]
  } | null>(null)

  const [prop, setProp] = useState({
    property_name: "", city: "", state: "", phone: "", gstin: "",
  })
  const [roomTypes, setRoomTypes] = useState<RoomTypeRow[]>([
    { code: "STD", name: "Standard", base_price: "2500", adults: "2", numbers: "" },
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
          Object.entries(prop).filter(([, v]) => v),
        ),
        room_types: roomTypes
          .filter((r) => r.code && r.name && r.base_price)
          .map((r) => ({
            code: r.code.toUpperCase(),
            name: r.name,
            base_price: Number(r.base_price),
            adults: Number(r.adults) || 2,
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

  async function runImport() {
    setBusy(true)
    setError(null)
    try {
      const lines = csv.trim().split("\n").filter(Boolean)
      const headers = lines[0].split(",").map((h) => h.trim())
      const rows = lines.slice(1).map((line) => {
        const cells = line.split(",").map((c) => c.trim())
        return Object.fromEntries(headers.map((h, i) => [h, cells[i] ?? ""]))
      })
      const res = await call<{
        created: number
        errors: { row: number; guest: string; error: string }[]
      }>("kamra.api.import_bookings", {
        property: createdProperty, bookings: rows,
      })
      setImportReport(res)
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
                  ["property_name", "Property name *", "Sunrise Residency"],
                  ["city", "City", "Bengaluru"],
                  ["state", "State", "Karnataka"],
                  ["phone", "Phone", "+91 …"],
                  ["gstin", "GSTIN", "29XXXXX…"],
                ] as const
              ).map(([k, label, ph]) => (
                <label key={k} className="block">
                  <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                    {label}
                  </span>
                  <input
                    className={inputCls}
                    placeholder={ph}
                    value={prop[k]}
                    onChange={(e) => setProp({ ...prop, [k]: e.target.value })}
                  />
                </label>
              ))}
            </>
          )}

          {step === 1 && (
            <>
              {roomTypes.map((rt, i) => (
                <div key={i} className="flex flex-wrap items-end gap-2">
                  <input className={cn(inputCls, "w-20")} placeholder="CODE"
                    value={rt.code} onChange={(e) => setRT(i, "code", e.target.value)} />
                  <input className={cn(inputCls, "flex-1")} placeholder="Name (Deluxe)"
                    value={rt.name} onChange={(e) => setRT(i, "name", e.target.value)} />
                  <input className={cn(inputCls, "w-28")} type="number" placeholder="₹/night"
                    value={rt.base_price} onChange={(e) => setRT(i, "base_price", e.target.value)} />
                  <input className={cn(inputCls, "w-20")} type="number" placeholder="Adults"
                    value={rt.adults} onChange={(e) => setRT(i, "adults", e.target.value)} />
                  {roomTypes.length > 1 && (
                    <Button variant="ghost" aria-label="Remove"
                      onClick={() => setRoomTypes((r) => r.filter((_, j) => j !== i))}>
                      <Trash2 className="size-4 text-rose-500" />
                    </Button>
                  )}
                </div>
              ))}
              <Button variant="outline"
                onClick={() => setRoomTypes((r) => [...r,
                  { code: "", name: "", base_price: "", adults: "2", numbers: "" }])}>
                <Plus className="size-4" aria-hidden /> Add room type
              </Button>
            </>
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
                  <span className="text-xs text-zinc-400">₹/adult/night</span>
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
                    {r.name} ₹{r.base_price} ×{r.numbers.split(",").filter((x) => x.trim()).length}
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
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                  CSV - header row then data
                </span>
                <textarea
                  className={cn(inputCls, "font-mono text-xs")}
                  rows={7}
                  placeholder={
                    "guest_name,phone,room_type_code,check_in,check_out,adults\n" +
                    "Asha Rao,+91 98xxxx,STD,2026-07-10,2026-07-12,2"
                  }
                  value={csv}
                  onChange={(e) => setCsv(e.target.value)}
                />
              </label>
              {importReport && (
                <div className="rounded-lg bg-zinc-50 px-4 py-3 text-sm">
                  <p className="font-medium text-emerald-700">
                    {importReport.created} booking{importReport.created === 1 ? "" : "s"} imported
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
            {step === 5 && (
              <Button disabled={busy || !csv.trim()} onClick={runImport}>
                {busy ? "Importing…" : "Import bookings"}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
