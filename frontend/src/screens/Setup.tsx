import { useEffect, useMemo, useState } from "react"
import { Check, Plus, Trash2, Zap, ListChecks } from "lucide-react"
import { InfoTip } from "../components/InfoTip"
import { toFullPath } from "../lib/routing"
import { call, setCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { cn } from "../lib/utils"
import { cur, loadLocale } from "../lib/money"
import { useT, t as translate } from "../lib/i18n"
import GoLiveImport from "./GoLiveImport"


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

/** What can be switched on. The owner picks; anything left off can be
 *  turned on later in Settings. Front desk and admin are always on. */
const MODULE_CHOICES: { id: string; label: string; blurb: string; info: string; doc: string; locked?: boolean; hotelOnly?: boolean }[] = [
  { id: "front-desk", label: "Front desk and reservations", blurb: "Bookings, check-in and out, folios, the tape chart.", info: "The core of Kamra: taking bookings, checking guests in and out, billing. Always on.", doc: "front-desk", locked: true },
  { id: "booking-engine", label: "Online booking page", blurb: "A simple page guests book and pay on, no other system needed.", info: "A public /book page for your property. Good for direct bookings and small places. You can run it on its own or alongside a channel manager.", doc: "booking-engine" },
  { id: "housekeeping", label: "Housekeeping", blurb: "Room status, cleaning tasks, a phone app for attendants.", info: "Assigns and tracks room cleaning, inspections and lost and found.", doc: "housekeeping" },
  { id: "operations", label: "Guest requests", blurb: "Tickets with deadlines (SLA) and who solved what.", info: "Guest requests become tickets with a promised time. You see who has each and who solved it.", doc: "operations", hotelOnly: true },
  { id: "fnb", label: "Restaurant and POS", blurb: "Outlets, menus, orders, kitchen tickets, bills.", info: "Run one or more restaurants, bars or room service from Kamra, with kitchen tickets and bills. Turning this on adds a step for outlets, stations and tills.", doc: "fnb", hotelOnly: true },
  { id: "events", label: "Banquets and events", blurb: "Halls, function quotes, menus and event orders.", info: "For properties that host weddings, conferences or parties.", doc: "banquets", hotelOnly: true },
  { id: "revenue", label: "Revenue", blurb: "Rate plans, seasons, best available rate (BAR), rate rules.", info: "BAR is your base rate for a room. Seasons and rate plans raise or lower it by date or by deal.", doc: "revenue" },
  { id: "finance", label: "Finance", blurb: "Tills, ledgers, night audit, reports and accounting export.", info: "Cashier tills, company accounts, the end-of-day (night audit) close and books export.", doc: "billing" },
  { id: "admin", label: "Admin", blurb: "Settings, rooms, staff and access.", info: "Always on: it holds Settings, which can turn the other modules on again.", doc: "settings", locked: true },
]

const STATION_CHOICES = ["Kitchen", "Tandoor", "Grill", "Fryer", "Bar"]
const TILL_KINDS = ["Front Desk", "Restaurant", "Bar", "Spa", "Other"]

interface CountryPack {
  country: string
  currency: string | null
  timezone: string | null
  tax_label: string | null
  tax_id_label: string | null
}

export default function Setup() {
  const { t } = useT()
  // How much to ask: quick (region + name, defaults for the rest) or guided
  const [mode, setMode] = useState<"choose" | "quick" | "guided">("choose")
  const [modules, setModules] = useState<string[]>([
    "front-desk", "housekeeping", "operations", "revenue", "finance", "booking-engine", "admin",
  ])
  const [wantsChannel, setWantsChannel] = useState(false)
  const [outlets, setOutlets] = useState<{ name: string; type: string }[]>([{ name: "Restaurant", type: "Restaurant" }])
  const [stations, setStations] = useState<string[]>(["Kitchen"])
  const [tills, setTills] = useState<{ name: string; kind: string; outlet: string }[]>([
    { name: "Front desk till", kind: "Front Desk", outlet: "" },
  ])
  const [cashOffice, setCashOffice] = useState(false)
  const [kind, setKind] = useState<PropertyKind>("Hotel")
  const [topology, setTopology] = useState<Topology>("rooms")
  const [step, setStep] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [createdProperty, setCreatedProperty] = useState<string | null>(null)
  const [prop, setProp] = useState({
    country: "",
    currency: "",
    timezone: "",
    property_name: "",
    short_code: "",
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
  // The country picks the tax & invoicing pack - and with it the currency,
  // clock, ID documents and ways to pay. Asked first so nothing defaults
  // to India by accident.
  const [countries, setCountries] = useState<CountryPack[]>([])
  const [otherCountry, setOtherCountry] = useState(false)
  function pickCountry(c: CountryPack | null) {
    setOtherCountry(!c)
    setProp((p) => ({
      ...p,
      country: c?.country ?? "",
      currency: c?.currency ?? "",
      timezone: c?.timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone,
    }))
  }
  useEffect(() => {
    call<CountryPack[]>("kamra.api.localization_countries")
      .then((cs) => {
        setCountries(cs)
        // preselect from the browser clock; the operator can still change it
        const tz = Intl.DateTimeFormat().resolvedOptions().timeZone
        const guess = cs.find((c) => c.timezone === tz)
        if (guess) pickCountry(guess)
      })
      .catch(() => setCountries([]))
  }, [])
  const pack = countries.find((c) => c.country === prop.country)
  const [roomTypes, setRoomTypes] = useState<RoomTypeRow[]>([{ ...HOTEL_ROOM_DEFAULT }])
  const [mealPlans, setMealPlans] = useState([
    { code: "EP", label: "Room Only", price_per_adult: "0", on: true },
    { code: "CP", label: "Breakfast Included", price_per_adult: "300", on: true },
    { code: "MAP", label: "Breakfast + Dinner", price_per_adult: "700", on: false },
  ])

  const isStr = kind === "Short Term Rental"
  const wantsPos = modules.includes("fnb")
  const steps = useMemo(() => {
    if (isStr) {
      return ["Type", "Property", "Modules", "Listings", "Inventory", "Review", "Import"]
    }
    return [
      "Type", "Property", "Modules", "Room Types", "Rooms", "Meal Plans",
      ...(wantsPos ? ["Outlets and tills"] : []), "Review", "Import",
    ]
  }, [isStr, wantsPos])
  const stepKey = steps[step]

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
        // guided setup only; quick leaves every module on, as before
        ...(mode === "guided"
          ? {
              modules,
              wants: wantsChannel ? ["channel-manager"] : [],
              ...(wantsPos
                ? {
                    pos: {
                      outlets: outlets.filter((o) => o.name.trim()),
                      stations,
                      tills: tills.filter((x) => x.name.trim()),
                      cash_office: cashOffice,
                    },
                  }
                : {}),
            }
          : {}),
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
      // currency symbol and tax words now come from the chosen pack
      await loadLocale()
      setStep(importStep)
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  /** Quick setup: the property in its region and nothing else. Rooms,
   *  rates, outlets and the rest are finished later from Finish setup. */
  async function quickCreate() {
    setBusy(true)
    setError(null)
    try {
      const res = await call<{ property: string }>("kamra.api.setup_property", {
        payload: {
          inventory_topology: isStr ? "whole_property" : "rooms",
          property: {
            country: prop.country,
            ...(prop.currency ? { currency: prop.currency } : {}),
            ...(prop.timezone ? { timezone: prop.timezone } : {}),
            property_name: prop.property_name,
            city: prop.city || undefined,
            property_kind: kind,
          },
        },
      })
      setCurrentProperty(res.property)
      await loadLocale()
      // a full load so the shell picks up the new property
      window.location.assign(toFullPath("/finish-setup"))
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
        {t("Hotel or vacation rental - same product, different defaults. Prefer talking? Connect Claude to Kamra's MCP and say \"onboard my property\".")}
      </p>

      {mode === "choose" && (
        <div className="grid gap-3 sm:grid-cols-2">
          <button
            type="button"
            onClick={() => setMode("quick")}
            className="rounded-xl border border-zinc-200 bg-white p-5 text-start transition hover:border-brand-600"
          >
            <Zap className="mb-2 size-5 text-brand-600" aria-hidden />
            <div className="text-base font-semibold text-zinc-900">{t("Quick setup")}</div>
            <p className="mt-1 text-sm leading-relaxed text-zinc-500">
              {t("Pick your region and name the property. Currency, time zone, tax and language follow the region. Add rooms, rates and the rest later, at your pace.")}
            </p>
            <p className="mt-2 text-xs text-zinc-400">{t("About a minute")}</p>
          </button>
          <button
            type="button"
            onClick={() => setMode("guided")}
            className="rounded-xl border border-zinc-200 bg-white p-5 text-start transition hover:border-brand-600"
          >
            <ListChecks className="mb-2 size-5 text-brand-600" aria-hidden />
            <div className="text-base font-semibold text-zinc-900">{t("Guided setup")}</div>
            <p className="mt-1 text-sm leading-relaxed text-zinc-500">
              {t("Step by step: choose the modules you want, then rooms, rates, and, if you run a restaurant, outlets, stations and tills. Each step asks only what it needs.")}
            </p>
            <p className="mt-2 text-xs text-zinc-400">{t("Ten to fifteen minutes")}</p>
          </button>
        </div>
      )}

      {mode === "quick" && (
        <Card>
          <CardHeader>
            <CardTitle>{t("Quick setup")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              {(["Hotel", "Short Term Rental"] as const).map((k) => (
                <button
                  key={k}
                  type="button"
                  onClick={() => chooseKind(k)}
                  className={cn(
                    "rounded-xl border px-4 py-3 text-start text-sm font-semibold",
                    kind === k ? "border-brand-600 bg-brand-50 ring-1 ring-brand-600" : "border-zinc-200 hover:border-zinc-300",
                  )}
                >
                  {k === "Hotel" ? t("Hotel") : t("Vacation rental")}
                </button>
              ))}
            </div>
            <label className="block">
              <span className="mb-1.5 flex items-center gap-1.5 text-sm font-medium text-zinc-600">
                {t("Region *")}
                <InfoTip doc="country-setup">
                  {t("The region sets the currency, time zone, tax words and invoice format, ID types and payment methods. Time zone decides when your business day rolls over.")}
                </InfoTip>
              </span>
              <select
                className={cn(inputCls, "bg-white")}
                value={otherCountry ? "__other" : prop.country}
                onChange={(e) =>
                  pickCountry(
                    e.target.value === "__other" ? null : (countries.find((c) => c.country === e.target.value) ?? null),
                  )
                }
              >
                <option value="" disabled>{t("Select")}</option>
                {countries.map((c) => (
                  <option key={c.country} value={c.country}>{c.country}</option>
                ))}
                <option value="__other">{t("Other country")}</option>
              </select>
            </label>
            {otherCountry && (
              <div className="grid grid-cols-2 gap-3">
                <input className={inputCls} placeholder={t("Country name")} value={prop.country}
                  onChange={(e) => setProp({ ...prop, country: e.target.value })} />
                <input className={inputCls} placeholder="USD" maxLength={3} value={prop.currency}
                  onChange={(e) => setProp({ ...prop, currency: e.target.value.toUpperCase() })} />
              </div>
            )}
            {pack && (
              <p className="rounded-lg bg-zinc-50 px-3 py-2 text-sm text-zinc-600">
                {t("This sets currency {currency}, time zone {tz}, and {tax} invoices.", {
                  currency: pack.currency ?? "",
                  tz: pack.timezone ?? prop.timezone,
                  tax: pack.tax_label ?? "",
                })}
              </p>
            )}
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-zinc-600">{t("Property name *")}</span>
              <input className={inputCls} placeholder="Sunrise Residency" value={prop.property_name}
                onChange={(e) => setProp({ ...prop, property_name: e.target.value })} />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-zinc-600">{t("City")}</span>
              <input className={inputCls} value={prop.city} onChange={(e) => setProp({ ...prop, city: e.target.value })} />
            </label>
            <p className="text-sm text-zinc-500">
              {t("Everything else starts at sensible defaults. You will land on a Finish setup list: rooms and rates, the booking page, outlets, tills and your team.")}
            </p>
            {error && (
              <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{translate(error)}</div>
            )}
            <div className="flex justify-between pt-2">
              <Button variant="outline" onClick={() => setMode("choose")}>{t("Back")}</Button>
              <Button
                disabled={busy || !prop.property_name.trim() || !prop.country.trim() || (otherCountry && prop.currency.length !== 3)}
                onClick={quickCreate}
              >
                {busy ? t("Creating…") : t("Create property")}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {mode === "guided" && (
      <>
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
          {stepKey === "Type" && (
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
                  <div className="text-sm font-semibold text-zinc-900">{translate(opt.title)}</div>
                  <p className="mt-1 text-xs leading-relaxed text-zinc-500">{translate(opt.blurb)}</p>
                </button>
              ))}
            </div>
          )}

          {stepKey === "Property" && (
            <>
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                  {t("Country *")}
                </span>
                <select
                  className={cn(inputCls, "bg-white")}
                  value={otherCountry ? "__other" : prop.country}
                  onChange={(e) =>
                    pickCountry(
                      e.target.value === "__other"
                        ? null
                        : (countries.find((c) => c.country === e.target.value) ?? null),
                    )
                  }
                >
                  <option value="" disabled>
                    {t("Select")}
                  </option>
                  {countries.map((c) => (
                    <option key={c.country} value={c.country}>
                      {c.country}
                    </option>
                  ))}
                  <option value="__other">{t("Other country")}</option>
                </select>
                <span className="mt-1.5 block text-xs text-zinc-500">
                  {pack
                    ? t("Sets {currency}, {tax} invoices, local ID types and payment methods.", {
                        currency: pack.currency ?? "",
                        tax: pack.tax_label ?? "",
                      })
                    : t("Other countries run on a simple flat-tax setup - enter the currency code below.")}
                </span>
              </label>
              {otherCountry && (
                <div className="grid grid-cols-2 gap-3">
                  <label className="block">
                    <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                      {t("Country name *")}
                    </span>
                    <input
                      className={inputCls}
                      value={prop.country}
                      onChange={(e) => setProp({ ...prop, country: e.target.value })}
                    />
                  </label>
                  <label className="block">
                    <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                      {t("Currency code *")}
                    </span>
                    <input
                      className={inputCls}
                      placeholder="USD"
                      maxLength={3}
                      value={prop.currency}
                      onChange={(e) =>
                        setProp({ ...prop, currency: e.target.value.toUpperCase() })
                      }
                    />
                  </label>
                </div>
              )}
              {(
                [
                  ["property_name", t("Property name *"), "text", "Sunrise Residency"],
                  ["short_code", t("Short code (on voucher numbers, e.g. SR)"), "text", "SR"],
                  ["city", t("City"), "text", ""],
                  ["state", t("State / region"), "text", ""],
                  ["phone", t("Phone"), "text", "+…"],
                  ["gstin", pack?.tax_id_label ?? t("Tax ID"), "text", ""],
                  ["checkin_time", t("Check-in Time"), "time", ""],
                  ["checkout_time", t("Check-out Time"), "time", ""],
                  ["minimum_nights", t("Minimum Nights"), "number", "1"],
                  ["booking_payment_mode", t("Booking Payment Mode"), "select", ""],
                  ["advance_percent", t("Advance Percent"), "number", "100"],
                  ["security_deposit_amount", t("Security Deposit Amount"), "number", "5000"],
                ] as const
              ).map(([k, label, type, ph]) => (
                <label key={k} className="block">
                  <span className="mb-1.5 block text-sm font-medium text-zinc-600">{translate(label)}</span>
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
                          {translate(opt.label)}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type={type}
                      className={inputCls}
                      placeholder={translate(ph)}
                      value={prop[k]}
                      onChange={(e) => setProp({ ...prop, [k]: e.target.value })}
                    />
                  )}
                </label>
              ))}
            </>
          )}

          {(stepKey === "Room Types" || stepKey === "Listings") && (
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
                      placeholder={translate("CODE")}
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
                      placeholder={(isStr ? t("Entire villa") : t("Name (Deluxe)"))}
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

          {stepKey === "Inventory" && (
            <div className="space-y-4">
              <p className="text-sm text-zinc-500">
                {t("How do guests book this property? This sets Sellable Units and competition groups - not a separate product fork.")}
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
                    <div className="text-sm font-semibold text-zinc-900">{translate(opt.title)}</div>
                    <p className="mt-1 text-xs leading-relaxed text-zinc-500">{translate(opt.blurb)}</p>
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

          {stepKey === "Rooms" && (
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

          {stepKey === "Meal Plans" && (
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
                    {translate(mp.label)} ({mp.code})
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

          {stepKey === "Modules" && (
            <div className="space-y-3">
              <p className="text-sm text-zinc-500">
                {t("Switch on what you need. You can change this any time in Settings.")}
              </p>
              {MODULE_CHOICES.filter((m) => !(isStr && m.hotelOnly)).map((m) => {
                const on = m.locked || modules.includes(m.id)
                return (
                  <label
                    key={m.id}
                    className={cn(
                      "flex items-start gap-3 rounded-xl border px-4 py-3",
                      on ? "border-brand-600/40 bg-brand-50/40" : "border-zinc-200",
                    )}
                  >
                    <input
                      type="checkbox"
                      className="mt-1 size-4 accent-brand-600"
                      checked={on}
                      disabled={m.locked}
                      onChange={(e) =>
                        setModules((cur) => (e.target.checked ? [...cur, m.id] : cur.filter((x) => x !== m.id)))
                      }
                    />
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-1.5 text-sm font-semibold text-zinc-900">
                        {t(m.label)}
                        <InfoTip doc={m.doc}>{t(m.info)}</InfoTip>
                        {m.locked && <span className="text-xs font-normal text-zinc-400">{t("always on")}</span>}
                      </span>
                      <span className="block text-xs text-zinc-500">{t(m.blurb)}</span>
                    </span>
                  </label>
                )
              })}
              <div className="rounded-xl border border-zinc-200 px-4 py-3">
                <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-zinc-900">
                  {t("Connections")}
                  <InfoTip doc="channel-manager">
                    {t("A channel manager sends your rooms, rates and availability to booking sites and brings their bookings back. You connect it after setup; ticking this adds it to your Finish setup list.")}
                  </InfoTip>
                </p>
                <label className="flex items-center gap-2 text-sm text-zinc-700">
                  <input
                    type="checkbox"
                    className="size-4 accent-brand-600"
                    checked={wantsChannel}
                    onChange={(e) => setWantsChannel(e.target.checked)}
                  />
                  {t("I use a channel manager (OTA bookings)")}
                </label>
                <p className="mt-1 text-xs text-zinc-400">
                  {modules.includes("booking-engine")
                    ? t("The online booking page can run alongside a channel manager or on its own.")
                    : t("Without the booking page, bookings come from the front desk and your channels.")}
                </p>
              </div>
            </div>
          )}

          {stepKey === "Outlets and tills" && (
            <div className="space-y-5">
              <section className="space-y-2">
                <p className="flex items-center gap-1.5 text-sm font-semibold text-zinc-900">
                  {t("Outlets")}
                  <InfoTip doc="fnb">
                    {t("An outlet is a place that sells food or drink: a restaurant, bar, room service, a spa cafe. Each has its own menu and bills. How many do you run?")}
                  </InfoTip>
                </p>
                {outlets.map((o, i) => (
                  <div key={i} className="flex gap-2">
                    <input className={inputCls} placeholder={t("Outlet name")} value={o.name}
                      onChange={(e) => setOutlets((r) => r.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} />
                    <select className={cn(inputCls, "w-40 bg-white")} value={o.type}
                      onChange={(e) => setOutlets((r) => r.map((x, j) => (j === i ? { ...x, type: e.target.value } : x)))}>
                      {["Restaurant", "Room Service", "Bar", "Spa", "Other"].map((x) => <option key={x} value={x}>{translate(x)}</option>)}
                    </select>
                    {outlets.length > 1 && (
                      <Button variant="ghost" aria-label={t("Remove")} onClick={() => setOutlets((r) => r.filter((_, j) => j !== i))}>
                        <Trash2 className="size-4" aria-hidden />
                      </Button>
                    )}
                  </div>
                ))}
                <Button variant="outline" onClick={() => setOutlets((r) => [...r, { name: "", type: "Restaurant" }])}>
                  <Plus className="size-4" aria-hidden /> {t("Add outlet")}
                </Button>
              </section>

              <section className="space-y-2">
                <p className="flex items-center gap-1.5 text-sm font-semibold text-zinc-900">
                  {t("Kitchen stations")}
                  <InfoTip doc="fnb">
                    {t("A station is where food or drinks are prepared: the kitchen, the bar, a tandoor. Kitchen tickets (KOTs) print at the station that makes the item. Bills print separately, at the till.")}
                  </InfoTip>
                </p>
                <div className="flex flex-wrap gap-2">
                  {STATION_CHOICES.map((st) => (
                    <label key={st} className={cn("flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm",
                      stations.includes(st) ? "border-brand-600 bg-brand-50 text-brand-700" : "border-zinc-200 text-zinc-600")}>
                      <input type="checkbox" className="accent-brand-600" checked={stations.includes(st)}
                        onChange={(e) => setStations((cur) => (e.target.checked ? [...cur, st] : cur.filter((x) => x !== st)))} />
                      {t(st)}
                    </label>
                  ))}
                </div>
                <p className="text-xs text-zinc-400">
                  {t("One printer is set up per station. Connect the physical printers later under Printers.")}
                </p>
              </section>

              <section className="space-y-2">
                <p className="flex items-center gap-1.5 text-sm font-semibold text-zinc-900">
                  {t("Tills")}
                  <InfoTip doc="billing">
                    {t("A till is a cash drawer someone counts and closes each shift. Give each its own name, and tie it to an outlet if it serves one. A cash office is the safe tills drop cash into.")}
                  </InfoTip>
                </p>
                {tills.map((x, i) => (
                  <div key={i} className="flex gap-2">
                    <input className={inputCls} placeholder={t("Till name")} value={x.name}
                      onChange={(e) => setTills((r) => r.map((y, j) => (j === i ? { ...y, name: e.target.value } : y)))} />
                    <select className={cn(inputCls, "w-36 bg-white")} value={x.kind}
                      onChange={(e) => setTills((r) => r.map((y, j) => (j === i ? { ...y, kind: e.target.value } : y)))}>
                      {TILL_KINDS.map((k) => <option key={k} value={k}>{translate(k)}</option>)}
                    </select>
                    <select className={cn(inputCls, "w-40 bg-white")} value={x.outlet}
                      onChange={(e) => setTills((r) => r.map((y, j) => (j === i ? { ...y, outlet: e.target.value } : y)))}>
                      <option value="">{t("No outlet")}</option>
                      {outlets.filter((o) => o.name.trim()).map((o) => <option key={o.name}>{o.name}</option>)}
                    </select>
                    <Button variant="ghost" aria-label={t("Remove")} onClick={() => setTills((r) => r.filter((_, j) => j !== i))}>
                      <Trash2 className="size-4" aria-hidden />
                    </Button>
                  </div>
                ))}
                <div className="flex flex-wrap items-center gap-3">
                  <Button variant="outline" onClick={() => setTills((r) => [...r, { name: "", kind: "Restaurant", outlet: "" }])}>
                    <Plus className="size-4" aria-hidden /> {t("Add till")}
                  </Button>
                  <label className="flex items-center gap-2 text-sm text-zinc-700">
                    <input type="checkbox" className="size-4 accent-brand-600" checked={cashOffice}
                      onChange={(e) => setCashOffice(e.target.checked)} />
                    {t("Add a cash office (central safe)")}
                  </label>
                </div>
              </section>
            </div>
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
                {modules.length > 0 && mode === "guided" && (
                  <Badge tone="zinc">{t("{n} modules", { n: modules.length })}</Badge>
                )}
                {wantsPos && (
                  <Badge tone="zinc">
                    {t("{o} outlets, {t} tills", { o: outlets.filter((x) => x.name.trim()).length, t: tills.filter((x) => x.name.trim()).length + (cashOffice ? 1 : 0) })}
                  </Badge>
                )}
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
                <span className="font-semibold">{createdProperty}</span> {t("is live. Bring your bookings, companies and opening balances over from Kamra's CSV templates, then reconcile before you switch - or let the AI migration assistant do the mapping via MCP.")}
              </div>
              <div className="rounded-lg border border-brand-200 bg-brand-50/60 px-4 py-3 text-sm text-zinc-800">
                <p className="font-semibold text-brand-800">
                  {t("Optional: connect HeyKoala WhatsApp")}
                </p>
                <p className="mt-1 text-zinc-600">
                  {t(
                    "After the desk is live, put an AI concierge on your WhatsApp number - it uses Kamra's tools. Metered by HeyKoala; the PMS stays free.",
                  )}
                </p>
                <a
                  href="/kamra/marketplace"
                  className="mt-2 inline-block text-sm font-medium text-brand-700 hover:underline"
                >
                  {t("Open Marketplace → HeyKoala WhatsApp")}
                </a>
              </div>
              <GoLiveImport property={createdProperty} embedded />
            </div>
          )}

          {error && (
            <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {translate(error)}
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
                disabled={
                  stepKey === "Property" &&
                  (!prop.property_name ||
                    !prop.country.trim() ||
                    (otherCountry && prop.currency.length !== 3))
                }
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
          </div>
        </CardContent>
      </Card>
      </>
      )}
    </div>
  )
}
