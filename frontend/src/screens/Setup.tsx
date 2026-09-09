import { useMemo, useState } from "react"
import { Check, Plus, Trash2 } from "lucide-react"
import { call, setCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { cn } from "../lib/utils"
import { cur } from "../lib/money"
import { useT } from "../lib/i18n"

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3.5 py-2.5 text-base " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

type PropertyKind = "Hotel" | "Short Term Rental"
type Topology = "rooms" | "whole_property"

interface RoomTypeRow {
  code: string
  name: string
  base_price: string
  adults: string
  numbers: string
  room_category: string
  free_child_age: string
  extra_adult_price: string
  air_conditioning: string
  weekend_price: string
}

const HOTEL_ROOM_DEFAULT: RoomTypeRow = {
  code: "STD",
  name: "Standard",
  base_price: "2500",
  adults: "2",
  numbers: "",
  room_category: "Private",
  free_child_age: "6",
  extra_adult_price: "2100",
  air_conditioning: "AC",
  weekend_price: "",
}

const STR_LISTING_DEFAULT: RoomTypeRow = {
  code: "HOME",
  name: "Entire place",
  base_price: "8500",
  adults: "4",
  numbers: "",
  room_category: "Villa",
  free_child_age: "6",
  extra_adult_price: "1500",
  air_conditioning: "",
  weekend_price: "",
}

export default function Setup() {
  const { t } = useT()
  const [kind, setKind] = useState<PropertyKind>("Hotel")
  const [topology, setTopology] = useState<Topology>("rooms")
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
    property_name: "",
    city: "",
    state: "",
    phone: "",
    gstin: "",
    checkin_time: "14:00:00",
    checkout_time: "11:00:00",
    minimum_nights: "1",
    booking_payment_mode: "Advance percent",
    advance_percent: "100",
    security_deposit_amount: "5000",
  })
  const [roomTypes, setRoomTypes] = useState<RoomTypeRow[]>([{ ...HOTEL_ROOM_DEFAULT }])
  const [mealPlans, setMealPlans] = useState([
    { code: "EP", label: "Room Only", price_per_adult: "0", on: true },
    { code: "CP", label: "Breakfast Included", price_per_adult: "300", on: true },
    { code: "MAP", label: "Breakfast + Dinner", price_per_adult: "700", on: false },
  ])
  const [csv, setCsv] = useState("")

  const isStr = kind === "Short Term Rental"
  const steps = useMemo(() => {
    if (isStr) {
      return ["Type", "Property", "Listings", "Inventory", "Review", "Import"]
    }
    return ["Type", "Property", "Room Types", "Rooms", "Meal Plans", "Review", "Import"]
  }, [isStr])

  const reviewStep = steps.length - 2
  const importStep = steps.length - 1

  const setRT = (i: number, k: keyof RoomTypeRow, v: string) =>
    setRoomTypes((rows) => rows.map((r, j) => (j === i ? { ...r, [k]: v } : r)))

  function chooseKind(next: PropertyKind) {
    setKind(next)
    if (next === "Short Term Rental") {
      setTopology("whole_property")
      setProp((p) => ({ ...p, minimum_nights: p.minimum_nights === "1" ? "2" : p.minimum_nights }))
      setRoomTypes([{ ...STR_LISTING_DEFAULT }])
    } else {
      setTopology("rooms")
      setRoomTypes([{ ...HOTEL_ROOM_DEFAULT }])
    }
  }

  async function create() {
    setBusy(true)
    setError(null)
    try {
      const payload = {
        inventory_topology: isStr ? topology : "rooms",
        property: {
          ...Object.fromEntries(
            Object.entries(prop)
              .filter(([, v]) => v)
              .map(([k, v]) => {
                if (["minimum_nights", "advance_percent", "security_deposit_amount"].includes(k)) {
                  return [k, Number(v) || 0]
                }
                return [k, v]
              }),
          ),
          property_kind: kind,
        },
        room_types: roomTypes
          .filter((r) => r.code && r.name && r.base_price)
          .map((r) => ({
            code: r.code.toUpperCase(),
            name: r.name,
            base_price: Number(r.base_price),
            adults: Number(r.adults) || 2,
            room_category:
              isStr && topology === "whole_property" ? "Villa" : r.room_category,
            free_child_age: Number(r.free_child_age) || 0,
            extra_adult_price: Number(r.extra_adult_price) || 0,
            air_conditioning:
              r.room_category === "Villa" || (isStr && topology === "whole_property")
                ? ""
                : r.air_conditioning,
            weekend_price: Number(r.weekend_price) || 0,
          })),
        rooms:
          isStr && topology === "whole_property"
            ? []
            : roomTypes
                .filter((r) => r.numbers.trim())
                .map((r) => ({
                  room_type_code: r.code.toUpperCase(),
                  numbers: r.numbers.split(",").map((n) => n.trim()).filter(Boolean),
                })),
        meal_plans: isStr
          ? []
          : mealPlans
              .filter((m) => m.on)
              .map((m, i) => ({
                code: m.code,
                label: m.label,
                price_per_adult: Number(m.price_per_adult) || 0,
                is_default: i === 1 ? 1 : 0,
              })),
      }
      const res = await call<{ property: string }>("kamra.api.setup_property", { payload })
      setCreatedProperty(res.property)
      setCurrentProperty(res.property)
      setStep(importStep)
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
      const res = await call<NonNullable<typeof preview>>("kamra.migrate.preview_import", {
        property: createdProperty,
        csv_text: csv,
        preset,
      })
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
        property: createdProperty,
        csv_text: csv,
        preset,
      })
      setImportReport(res)
      setPreview(null)
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const timeOptions = [
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
    { label: "11:00 PM", value: "23:00:00" },
  ]

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-1 text-lg font-semibold">{t("Set up a new property")}</h1>
      <p className="mb-4 text-sm text-zinc-500">
        {t("Hotel or vacation rental — same product, different defaults. Prefer talking? Connect Claude to Kamra's MCP and say \"onboard my property\".")}
      </p>

      <ol className="mb-6 flex flex-wrap gap-2">
        {steps.map((s, i) => (
          <li
            key={s}
            className={cn(
              "flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium",
              i === step
                ? "bg-brand-600 text-white"
                : i < step || (createdProperty && i <= reviewStep)
                  ? "bg-brand-50 text-brand-700"
                  : "bg-zinc-100 text-zinc-400",
            )}
          >
            {(i < step || (createdProperty && i <= reviewStep)) && (
              <Check className="size-3" aria-hidden />
            )}
            {t(s)}
          </li>
        ))}
      </ol>

      <Card>
        <CardHeader>
          <CardTitle>{t(steps[step])}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {step === 0 && (
            <div className="grid gap-3 sm:grid-cols-2">
              {(
                [
                  {
                    value: "Hotel" as const,
                    title: t("Hotel"),
                    blurb: t("Multiple rooms, optional F&B and events. Classic front-desk flow."),
                  },
                  {
                    value: "Short Term Rental" as const,
                    title: t("Vacation rental"),
                    blurb: t("Entire place or a few units. No meal plans; overbooking off by default."),
                  },
                ] as const
              ).map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => chooseKind(opt.value)}
                  className={cn(
                    "rounded-xl border px-4 py-4 text-left transition",
                    kind === opt.value
                      ? "border-brand-600 bg-brand-50 ring-1 ring-brand-600"
                      : "border-zinc-200 bg-white hover:border-zinc-300",
                  )}
                >
                  <div className="text-sm font-semibold text-zinc-900">{opt.title}</div>
                  <p className="mt-1 text-xs leading-relaxed text-zinc-500">{opt.blurb}</p>
                </button>
              ))}
            </div>
          )}

          {step === 1 && (
            <>
              {(
                [
                  ["property_name", t("Property name *"), "text", "Sunrise Residency"],
                  ["city", t("City"), "text", "Bengaluru"],
                  ["state", t("State"), "text", "Karnataka"],
                  ["phone", t("Phone"), "text", "+91 …"],
                  ["gstin", t("GSTIN"), "text", "29XXXXX…"],
                  ["checkin_time", t("Check-in Time"), "time", ""],
                  ["checkout_time", t("Check-out Time"), "time", ""],
                  ["minimum_nights", t("Minimum Nights"), "number", "1"],
                  ["booking_payment_mode", t("Booking Payment Mode"), "select", ""],
                  ["advance_percent", t("Advance Percent"), "number", "100"],
                  ["security_deposit_amount", t("Security Deposit Amount"), "number", "5000"],
                ] as const
              ).map(([k, label, type, ph]) => (
                <label key={k} className="block">
                  <span className="mb-1.5 block text-sm font-medium text-zinc-600">{label}</span>
                  {k === "booking_payment_mode" ? (
                    <select
                      className={cn(inputCls, "bg-white")}
                      value={prop[k]}
                      onChange={(e) => setProp({ ...prop, [k]: e.target.value })}
                    >
                      <option value="Full payment">{t("Full payment")}</option>
                      <option value="Advance percent">{t("Advance percent")}</option>
                      <option value="Pay at hotel">{t("Pay at hotel")}</option>
                    </select>
                  ) : type === "time" ? (
                    <select
                      className={cn(inputCls, "bg-white")}
                      value={prop[k]}
                      onChange={(e) => setProp({ ...prop, [k]: e.target.value })}
                    >
                      {timeOptions.map((opt) => (
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

          {step === 2 && (
            <div className="space-y-4">
              {roomTypes.map((rt, i) => (
                <div
                  key={i}
                  className="relative space-y-3 rounded-xl border border-zinc-200 bg-zinc-50/50 p-4"
                >
                  {roomTypes.length > 1 && (
                    <Button
                      variant="ghost"
                      aria-label={t("Remove")}
                      className="absolute top-2 right-2"
                      onClick={() => setRoomTypes((r) => r.filter((_, j) => j !== i))}
                    >
                      <Trash2 className="size-4 text-rose-500" />
                    </Button>
                  )}
                  <label className="block">
                    <span className="mb-1 block text-xs font-semibold text-zinc-500">
                      {isStr ? t("Listing code") : t("Room Type Code (e.g. STD)")}
                    </span>
                    <input
                      className={inputCls}
                      placeholder="CODE"
                      value={rt.code}
                      onChange={(e) => setRT(i, "code", e.target.value)}
                    />
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-xs font-semibold text-zinc-500">
                      {isStr ? t("Listing name") : t("Room Type Name (e.g. Standard Room)")}
                    </span>
                    <input
                      className={inputCls}
                      placeholder={isStr ? t("Entire villa") : t("Name (Deluxe)")}
                      value={rt.name}
                      onChange={(e) => setRT(i, "name", e.target.value)}
                    />
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-xs font-semibold text-zinc-500">
                      {t("Nightly price")}
                    </span>
                    <input
                      className={inputCls}
                      type="number"
                      placeholder={t("{cur}/night", { cur: cur() })}
                      value={rt.base_price}
                      onChange={(e) => setRT(i, "base_price", e.target.value)}
                    />
                  </label>
                  {isStr && (
                    <label className="block">
                      <span className="mb-1 block text-xs font-semibold text-zinc-500">
                        {t("Weekend nightly price (optional)")}
                      </span>
                      <input
                        className={inputCls}
                        type="number"
                        placeholder={t("Leave blank to skip")}
                        value={rt.weekend_price}
                        onChange={(e) => setRT(i, "weekend_price", e.target.value)}
                      />
                    </label>
                  )}
                  <label className="block">
                    <span className="mb-1 block text-xs font-semibold text-zinc-500">
                      {t("Max guests (base)")}
                    </span>
                    <input
                      className={inputCls}
                      type="number"
                      placeholder={t("Adults")}
                      value={rt.adults}
                      onChange={(e) => setRT(i, "adults", e.target.value)}
                    />
                  </label>
                  {!(isStr && topology === "whole_property") && (
                    <label className="block">
                      <span className="mb-1 block text-xs font-semibold text-zinc-500">
                        {t("Category")}
                      </span>
                      <select
                        className={cn(inputCls, "bg-white")}
                        value={rt.room_category}
                        onChange={(e) => setRT(i, "room_category", e.target.value)}
                      >
                        <option value="Private">{t("Private")}</option>
                        <option value="Villa">{t("Villa")}</option>
                        <option value="Shared">{t("Shared")}</option>
                      </select>
                    </label>
                  )}
                  {rt.room_category !== "Villa" && !(isStr && topology === "whole_property") && (
                    <label className="block">
                      <span className="mb-1 block text-xs font-semibold text-zinc-500">
                        {t("Air Conditioning")}
                      </span>
                      <select
                        className={cn(inputCls, "bg-white")}
                        value={rt.air_conditioning}
                        onChange={(e) => setRT(i, "air_conditioning", e.target.value)}
                      >
                        <option value="AC">{t("AC")}</option>
                        <option value="Non AC">{t("Non AC")}</option>
                      </select>
                    </label>
                  )}
                  <label className="block">
                    <span className="mb-1 block text-xs font-semibold text-zinc-500">
                      {t("Free Child Age Limit (Years)")}
                    </span>
                    <input
                      className={inputCls}
                      type="number"
                      placeholder="6"
                      value={rt.free_child_age}
                      onChange={(e) => setRT(i, "free_child_age", e.target.value)}
                    />
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-xs font-semibold text-zinc-500">
                      {t("Extra guest price / night")}
                    </span>
                    <input
                      className={inputCls}
                      type="number"
                      placeholder="2100"
                      value={rt.extra_adult_price}
                      onChange={(e) => setRT(i, "extra_adult_price", e.target.value)}
                    />
                  </label>
                </div>
              ))}
              <Button
                variant="outline"
                onClick={() =>
                  setRoomTypes((r) => [
                    ...r,
                    {
                      ...(isStr ? STR_LISTING_DEFAULT : HOTEL_ROOM_DEFAULT),
                      code: "",
                      name: "",
                      base_price: "",
                      numbers: "",
                    },
                  ])
                }
              >
                <Plus className="size-4" aria-hidden />{" "}
                {isStr ? t("Add listing") : t("Add room type")}
              </Button>
            </div>
          )}

          {step === 3 && isStr && (
            <div className="space-y-4">
              <p className="text-sm text-zinc-500">
                {t("How do guests book this property? This sets Sellable Units and competition groups — not a separate product fork.")}
              </p>
              <div className="grid gap-3 sm:grid-cols-2">
                {(
                  [
                    {
                      value: "whole_property" as const,
                      title: t("Entire place"),
                      blurb: t("One listing for the whole property. No room numbers required."),
                    },
                    {
                      value: "rooms" as const,
                      title: t("Individual units"),
                      blurb: t("Each unit / room sells on its own (hotel-style inventory)."),
                    },
                  ] as const
                ).map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setTopology(opt.value)}
                    className={cn(
                      "rounded-xl border px-4 py-4 text-left transition",
                      topology === opt.value
                        ? "border-brand-600 bg-brand-50 ring-1 ring-brand-600"
                        : "border-zinc-200 bg-white hover:border-zinc-300",
                    )}
                  >
                    <div className="text-sm font-semibold text-zinc-900">{opt.title}</div>
                    <p className="mt-1 text-xs leading-relaxed text-zinc-500">{opt.blurb}</p>
                  </button>
                ))}
              </div>
              {topology === "rooms" && (
                <>
                  <p className="text-sm text-zinc-500">
                    {t("Unit / room numbers per listing, comma-separated.")}
                  </p>
                  {roomTypes
                    .filter((r) => r.code)
                    .map((rt, i) => (
                      <label key={i} className="block">
                        <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                          {rt.name || rt.code}
                        </span>
                        <input
                          className={inputCls}
                          placeholder={t("Cottage 1, Cottage 2")}
                          value={rt.numbers}
                          onChange={(e) => setRT(i, "numbers", e.target.value)}
                        />
                      </label>
                    ))}
                </>
              )}
              {topology === "whole_property" && (
                <p className="rounded-lg bg-zinc-50 px-3 py-2 text-sm text-zinc-600">
                  {t("Kamra will create a whole-property sellable unit for each listing. You can add physical rooms later for housekeeping if needed.")}
                </p>
              )}
            </div>
          )}

          {step === 3 && !isStr && (
            <>
              <p className="text-sm text-zinc-500">{t("Room numbers per type, comma-separated.")}</p>
              {roomTypes
                .filter((r) => r.code)
                .map((rt, i) => (
                  <label key={i} className="block">
                    <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                      {rt.name || rt.code}
                    </span>
                    <input
                      className={inputCls}
                      placeholder={t("101, 102, 103")}
                      value={rt.numbers}
                      onChange={(e) => setRT(i, "numbers", e.target.value)}
                    />
                  </label>
                ))}
            </>
          )}

          {step === 4 && !isStr && (
            <>
              {mealPlans.map((mp, i) => (
                <div key={mp.code} className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    className="size-4 accent-brand-600"
                    checked={mp.on}
                    onChange={(e) =>
                      setMealPlans((m) =>
                        m.map((x, j) => (j === i ? { ...x, on: e.target.checked } : x)),
                      )
                    }
                  />
                  <span className="w-40 text-sm">
                    {mp.label} ({mp.code})
                  </span>
                  <input
                    className={cn(inputCls, "w-32")}
                    type="number"
                    value={mp.price_per_adult}
                    onChange={(e) =>
                      setMealPlans((m) =>
                        m.map((x, j) =>
                          j === i ? { ...x, price_per_adult: e.target.value } : x,
                        ),
                      )
                    }
                  />
                  <span className="text-xs text-zinc-400">{t("{cur}/adult/night", { cur: cur() })}</span>
                </div>
              ))}
            </>
          )}

          {step === reviewStep && (
            <div className="space-y-2 text-sm">
              <p>
                <span className="font-medium">{prop.property_name}</span>
                {prop.city && <span className="text-zinc-500"> · {prop.city}</span>}
              </p>
              <div className="flex flex-wrap gap-1.5">
                <Badge tone="brand">{t(kind)}</Badge>
                {isStr && (
                  <Badge tone="zinc">
                    {topology === "whole_property" ? t("Entire place") : t("Individual units")}
                  </Badge>
                )}
                {roomTypes
                  .filter((r) => r.code)
                  .map((r) => (
                    <Badge key={r.code} tone="zinc">
                      {r.name} {cur()}
                      {r.base_price}
                      {!isStr || topology === "rooms"
                        ? ` ×${r.numbers.split(",").filter((x) => x.trim()).length || 0}`
                        : ""}
                    </Badge>
                  ))}
                {!isStr &&
                  mealPlans
                    .filter((m) => m.on)
                    .map((m) => (
                      <Badge key={m.code} tone="brand">
                        {m.code}
                      </Badge>
                    ))}
              </div>
              <p className="text-zinc-500">
                {t("Creating sets this as your active property. Rates, seasons, vouchers and guardrails can be added later from Revenue.")}
              </p>
            </div>
          )}

          {step === importStep && (
            <div className="space-y-4">
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
                <span className="font-semibold">{createdProperty}</span> {t("is live. Bring your existing bookings over — paste a CSV, or let the AI migration assistant do the mapping via MCP.")}
              </div>
              <div className="rounded-lg border border-brand-200 bg-brand-50/60 px-4 py-3 text-sm text-zinc-800">
                <p className="font-semibold text-brand-800">
                  {t("Optional: connect HeyKoala WhatsApp")}
                </p>
                <p className="mt-1 text-zinc-600">
                  {t(
                    "After the desk is live, put an AI concierge on your WhatsApp number — it uses Kamra's tools. Metered by HeyKoala; the PMS stays free.",
                  )}
                </p>
                <a
                  href="/kamra/marketplace"
                  className="mt-2 inline-block text-sm font-medium text-brand-700 hover:underline"
                >
                  {t("Open Marketplace → HeyKoala WhatsApp")}
                </a>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <select
                  className={cn(inputCls, "w-auto")}
                  value={preset}
                  onChange={(e) => {
                    setPreset(e.target.value)
                    setPreview(null)
                  }}
                  aria-label={t("Which system is this export from?")}
                >
                  <option value="auto">{t("Auto-detect format")}</option>
                  <option value="ezee">{t("eZee export")}</option>
                  <option value="cloudbeds">{t("Cloudbeds export")}</option>
                </select>
                <label className="cursor-pointer rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm font-medium text-zinc-700 hover:border-brand-400">
                  {t("Upload CSV file")}
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    className="hidden"
                    onChange={async (e) => {
                      const f = e.target.files?.[0]
                      if (f) {
                        setCsv(await f.text())
                        setPreview(null)
                      }
                    }}
                  />
                </label>
                <span className="text-xs text-zinc-400">{t("or paste it below")}</span>
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
                  onChange={(e) => {
                    setCsv(e.target.value)
                    setPreview(null)
                  }}
                />
              </label>
              {preview && (
                <div className="space-y-2 rounded-lg bg-zinc-50 px-4 py-3 text-sm">
                  <p>
                    <span className="font-medium text-emerald-700">
                      {t("{n} ready to import", { n: preview.ok })}
                    </span>
                    {preview.skipped > 0 && (
                      <span className="ml-2 font-medium text-rose-600">
                        {t("{n} will be skipped", { n: preview.skipped })}
                      </span>
                    )}
                    <span className="ml-2 text-zinc-400">
                      {t("dates read as {format}", { format: preview.date_format })}
                    </span>
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {Object.entries(preview.mapping).map(([k, v]) => (
                      <Badge key={k} tone="zinc">
                        {v} → {k.replace(/_/g, " ")}
                      </Badge>
                    ))}
                    {preview.unmapped.map((h) => (
                      <Badge key={h} tone="amber">
                        {t("{header} (ignored)", { header: h })}
                      </Badge>
                    ))}
                  </div>
                  {preview.issues.map((iss) => (
                    <p key={iss.row} className="text-rose-600">
                      Row {iss.row}
                      {iss.guest ? ` (${iss.guest})` : ""}: {iss.error}
                    </p>
                  ))}
                </div>
              )}
              {importReport && (
                <div className="rounded-lg bg-zinc-50 px-4 py-3 text-sm">
                  <p className="font-medium text-emerald-700">
                    {t("{n} booking{s} imported{history}", {
                      n: importReport.created,
                      s: importReport.created === 1 ? "" : "s",
                      history: importReport.history
                        ? t(" ({n} as past-stay history)", { n: importReport.history })
                        : "",
                    })}
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
            {step > 0 && step < importStep ? (
              <Button variant="outline" onClick={() => setStep(step - 1)}>
                {t("Back")}
              </Button>
            ) : (
              <span />
            )}
            {step < reviewStep && (
              <Button
                disabled={step === 1 && !prop.property_name}
                onClick={() => setStep(step + 1)}
              >
                {t("Continue")}
              </Button>
            )}
            {step === reviewStep && (
              <Button disabled={busy} onClick={create}>
                {busy ? t("Creating…") : t("Create property")}
              </Button>
            )}
            {step === importStep && !preview && (
              <Button disabled={busy || !csv.trim()} onClick={previewImport}>
                {busy ? t("Checking…") : t("Preview import")}
              </Button>
            )}
            {step === importStep && preview && (
              <Button disabled={busy || preview.ok === 0} onClick={runImport}>
                {busy
                  ? t("Importing…")
                  : t("Import {n} booking{s}", {
                      n: preview.ok,
                      s: preview.ok === 1 ? "" : "s",
                    })}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
