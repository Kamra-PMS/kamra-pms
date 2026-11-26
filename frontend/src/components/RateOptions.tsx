import { useEffect, useRef, useState } from "react"
import { call, getCurrentProperty } from "../lib/api"
import { InfoTip } from "./InfoTip"
import { cur, moneyDigits, moneyLocale, fmtAmount } from "../lib/money"
import { isOverride, maxPriceDigits, nightLabel, parsePrice, splitRoomTotal } from "../lib/nightPrices"
import { useT, t as translate, uiDateLocale } from "../lib/i18n"
import { cn } from "../lib/utils"


const n0 = (n: number) => fmtAmount(n ?? 0)

export interface Restriction {
  name: string
  rate_plan: string | null
  min_nights: number
  max_nights: number
  closed_to_arrival: boolean
  closed_to_departure: boolean
  stop_sell: boolean
}

export interface NightRate {
  date: string
  /** the Rate Restrictions on this date, every plan (rate calendar only) */
  restrictions?: Restriction[]
  bar: number
  after_season: number
  rate: number
  season: { label: string; change: string } | null
  demand: { premium_pct: number; min_rate: number; from_occupancy: number } | null
  occupancy: number
}

interface PlanRow {
  name: string
  label: string
  code: string | null
  room_total: number
  vs_plain: number
  /** why this stay can't be booked on the plan (a Rate Restriction) */
  restriction?: string | null
}

interface Options {
  nights: NightRate[]
  plain: { room_total: number; amount_after_tax: number; restriction?: string | null }
  plans: PlanRow[]
  voucher: { code: string; valid: boolean; discount?: number; kind?: string; value?: number; reason?: string } | null
  /** the figures above (and a typed night price) include tax */
  tax_inclusive?: boolean
  /** ... and the room levy */
  levy_inclusive?: boolean
}

/** The stay's rate, explained: each night's BAR and what moved it, the whole
 *  stay under each rate plan, and the voucher. Every figure is a real quote;
 *  picking a plan here picks it on the booking. */
export function RateOptions({
  roomType,
  checkIn,
  checkOut,
  adults,
  children,
  mealPlan,
  voucher,
  ratePlan,
  onPickPlan,
  nightPrices,
  onNightPrices,
  canSetPrice,
  lockedNote,
  showPlans = true,
  copyFrom,
  showNote = true,
  plansLocked = false,
}: {
  roomType: string
  checkIn: string
  checkOut: string
  adults: number
  children: number
  mealPlan?: string
  voucher?: string
  ratePlan: string
  onPickPlan: (plan: string) => void
  /** nights the desk priced by hand: date -> price, in the basis shown here */
  nightPrices: Record<string, number>
  onNightPrices: (prices: Record<string, number>) => void
  /** the desk may type a night's price (right to set rates, not an OTA total) */
  canSetPrice: boolean
  /** why the prices cannot be typed, when it is not a missing right */
  lockedNote?: string
  /** list the rate plans (a booking's main room); an added room has none of its own */
  showPlans?: boolean
  /** the first room's hand-set nights (date -> price): an added room can take the same prices */
  copyFrom?: Record<string, number>
  /** say that hand-set prices cannot be combined with a rate plan or a voucher (the booking says it once) */
  showNote?: boolean
  /** another room of this booking has hand-set prices, so no rate plan can be picked */
  plansLocked?: boolean
}) {
  const { t } = useT()
  const [data, setData] = useState<Options | null>(null)
  const [err, setErr] = useState<string | null>(null)
  // what is being typed, before it is a valid price (a night's text, or the room total)
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const inputs = useRef<Record<string, HTMLInputElement | null>>({})

  useEffect(() => {
    if (!roomType || !checkIn || !checkOut) return
    let live = true
    const h = setTimeout(() => {
      call<Options>("kamra.rates.rate_options", {
        property: getCurrentProperty(),
        room_type: roomType,
        check_in_date: checkIn,
        check_out_date: checkOut,
        adults,
        children,
        meal_plan: mealPlan || undefined,
        voucher_code: voucher || undefined,
      })
        .then((d) => {
          if (live) {
            setData(d)
            setErr(null)
          }
        })
        .catch(() => live && setErr(t("Could not load the rates.")))
    }, 350)
    return () => {
      live = false
      clearTimeout(h)
    }
  }, [roomType, checkIn, checkOut, adults, children, mealPlan, voucher, t])

  if (err) return <p className="text-xs text-zinc-400">{translate(err)}</p>
  if (!data) return null
  const moved = data.nights.some((x) => x.season || x.demand)
  const digits = maxPriceDigits(moneyDigits())
  const plain = (n: number) => String(Number(n.toFixed(digits)))
  const priceOf = (x: NightRate) => nightPrices[x.date] ?? x.rate
  const hasTyped = data.nights.some((x) => isOverride(nightPrices[x.date], x.rate, digits))
  const roomTotal = data.nights.reduce((sum, x) => sum + priceOf(x), 0)
  const basis = data.levy_inclusive
    ? data.tax_inclusive
      ? t("Prices include tax and the levy.")
      : t("Prices include the levy, before tax.")
    : data.tax_inclusive
      ? t("Prices include tax.")
      : t("Prices are before tax.")

  /** Set one night; a price equal to what Kamra charges, or none, is not an override. */
  function setNight(x: NightRate, price: number | null) {
    const next = { ...nightPrices }
    if (price === null || !isOverride(price, x.rate, digits)) delete next[x.date]
    else next[x.date] = price
    onNightPrices(next)
  }
  const draft = (key: string, text: string | null) =>
    setDrafts((d) => {
      const { [key]: _gone, ...rest } = d
      return text === null ? rest : { ...rest, [key]: text }
    })
  function typeNight(x: NightRate, text: string) {
    draft(x.date, text)
    if (text.trim() === "") return setNight(x, null)
    const price = parsePrice(text, digits)
    if (price !== null) setNight(x, price)
  }
  function typeTotal(text: string) {
    draft("total", text)
    const total = parsePrice(text, digits)
    if (total === null || !data) return
    const parts = splitRoomTotal(total, data.nights.length, digits)
    const next: Record<string, number> = {}
    data.nights.forEach((x, i) => {
      if (isOverride(parts[i], x.rate, digits)) next[x.date] = parts[i]
    })
    onNightPrices(next)
  }
  /** the first room's hand-set prices on the nights this room is quoted for; a night
   *  already at this room's rate is not an override */
  const copyable = copyFrom
    ? data.nights.filter((x) => copyFrom[x.date] !== undefined && isOverride(copyFrom[x.date], x.rate, digits))
    : []
  function copyFirstRoom() {
    if (!copyFrom) return
    setDrafts({})
    onNightPrices(Object.fromEntries(copyable.map((x) => [x.date, copyFrom[x.date]])))
  }
  function onNightKey(e: React.KeyboardEvent<HTMLInputElement>, i: number, x: NightRate) {
    if (e.key === "ArrowUp" || e.key === "ArrowDown") {
      const other = data?.nights[i + (e.key === "ArrowUp" ? -1 : 1)]
      if (other) {
        e.preventDefault()
        inputs.current[other.date]?.focus()
        inputs.current[other.date]?.select()
      }
    } else if (e.key === "Backspace" && e.altKey) {
      e.preventDefault()
      draft(x.date, null)
      setNight(x, null)
    }
  }
  return (
    <div className="space-y-3 rounded-xl border border-zinc-200 p-4">
      <div className="flex items-center gap-1.5">
        <h3 className="text-sm font-semibold text-zinc-800">{t("Rates for these dates")}</h3>
        <InfoTip doc="revenue">
          {t("BAR is the best available rate: the room type's base price. A season or a busy-house (demand) rule can move it for a date. A rate plan then adjusts the whole stay, and a voucher comes off the total.")}
        </InfoTip>
      </div>

      {canSetPrice && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
          <label htmlFor="night-room-total" className="text-zinc-600">
            {t("Room total")}
          </label>
          <span className="inline-flex items-center gap-1">
            <span className="text-zinc-500">{cur()}</span>
            <input
              id="night-room-total"
              inputMode="decimal"
              className={cn(
                "w-28 rounded-md border px-2 py-1 text-right tabular-nums",
                drafts.total !== undefined && parsePrice(drafts.total, digits) === null
                  ? "border-rose-400"
                  : "border-zinc-300",
              )}
              value={drafts.total ?? plain(roomTotal)}
              aria-invalid={drafts.total !== undefined && parsePrice(drafts.total, digits) === null}
              onChange={(e) => typeTotal(e.target.value)}
              onBlur={() => draft("total", null)}
            />
          </span>
          <span className="text-xs text-zinc-400">{basis}</span>
          {copyFrom && Object.keys(copyFrom).length > 0 && (
            <button
              type="button"
              className="text-xs text-brand-700 underline disabled:text-zinc-400 disabled:no-underline"
              disabled={copyable.length === 0}
              onClick={copyFirstRoom}
            >
              {t("Same as room 1")}
            </button>
          )}
        </div>
      )}
      {!canSetPrice && lockedNote && <p className="text-xs text-zinc-400">{lockedNote}</p>}

      <ul className="divide-y divide-zinc-100 text-sm">
        {data.nights.map((x, i) => {
          const typed = isOverride(nightPrices[x.date], x.rate, digits)
          const bad = drafts[x.date] !== undefined && drafts[x.date].trim() !== "" && parsePrice(drafts[x.date], digits) === null
          return (
            <li
              key={x.date}
              className={cn(
                "flex flex-wrap items-center gap-x-3 gap-y-1 py-1.5",
                typed && "-mx-2 rounded-md bg-brand-50 px-2",
              )}
            >
              <span className="w-28 shrink-0 text-zinc-500">{nightLabel(x.date, uiDateLocale(moneyLocale()))}</span>
              {canSetPrice ? (
                <span className="inline-flex items-center gap-1">
                  <span className="text-zinc-500">{cur()}</span>
                  <input
                    ref={(el) => {
                      inputs.current[x.date] = el
                    }}
                    inputMode="decimal"
                    aria-label={t("Price for {d}", { d: nightLabel(x.date, uiDateLocale(moneyLocale())) })}
                    aria-invalid={bad}
                    className={cn(
                      "w-28 rounded-md border px-2 py-1 text-right font-medium tabular-nums",
                      bad ? "border-rose-400" : typed ? "border-brand-600" : "border-zinc-300",
                    )}
                    value={drafts[x.date] ?? plain(priceOf(x))}
                    onChange={(e) => typeNight(x, e.target.value)}
                    onKeyDown={(e) => onNightKey(e, i, x)}
                    onBlur={() => draft(x.date, null)}
                  />
                </span>
              ) : (
                <span className="font-medium tabular-nums">
                  {cur()}
                  {n0(priceOf(x))}
                </span>
              )}
              {typed ? (
                <>
                  <span className="text-xs text-zinc-400 tabular-nums line-through">
                    {t("BAR {r}", { r: `${cur()}${n0(x.rate)}` })}
                  </span>
                  <button
                    type="button"
                    className="text-xs text-brand-700 underline"
                    onClick={() => {
                      draft(x.date, null)
                      setNight(x, null)
                    }}
                  >
                    {t("Back to BAR")}
                  </button>
                </>
              ) : (
                x.rate !== x.bar && (
                  <span className="text-xs text-zinc-400 tabular-nums">
                    {t("BAR {r}", { r: `${cur()}${n0(x.bar)}` })}
                  </span>
                )
              )}
              {x.season && (
                <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs text-amber-800">
                  {x.season.label} {x.season.change}
                </span>
              )}
              {x.demand && !typed && (
                <span className="rounded-full bg-rose-50 px-2 py-0.5 text-xs text-rose-800">
                  {t("Busy house {p}%", { p: Math.round(x.occupancy) })}
                  {x.demand.premium_pct ? ` +${x.demand.premium_pct}%` : ""}
                </span>
              )}
            </li>
          )
        })}
      </ul>
      {canSetPrice && (
        <p className="text-xs text-zinc-400">
          {t("Type a price to set a night by hand. Up and down arrows move between nights; Alt+Backspace returns a night to BAR.")}
        </p>
      )}
      {showNote && hasTyped && (
        <p className="text-xs text-zinc-500">
          {t("Prices set by hand cannot be combined with a rate plan or a voucher.")}
        </p>
      )}
      {!moved && (
        <p className="text-xs text-zinc-400">{t("No season or demand rule applies: every night is at BAR.")}</p>
      )}

      {showPlans && data.plans.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-500">{t("Rate plans")}</p>
          <div className="space-y-1">
            <button
              type="button"
              onClick={() => onPickPlan("")}
              className={cn(
                "flex w-full items-center justify-between rounded-lg border px-3 py-1.5 text-sm",
                !ratePlan ? "border-brand-600 bg-brand-50" : "border-zinc-200 hover:bg-zinc-50",
              )}
            >
              <span>{t("Standard rate")}</span>
              <span className="tabular-nums">
                {cur()}
                {n0(data.plain.room_total)}
              </span>
            </button>
            {data.plain.restriction && <p className="px-1 text-xs text-rose-700">{translate(data.plain.restriction)}</p>}
            {data.plans.map((p) => (
              <button
                key={p.name}
                type="button"
                onClick={() => onPickPlan(p.name)}
                disabled={hasTyped || plansLocked || !!p.restriction}
                title={p.restriction ? translate(p.restriction) : undefined}
                className={cn(
                  "flex w-full items-center justify-between rounded-lg border px-3 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-50",
                  ratePlan === p.name ? "border-brand-600 bg-brand-50" : "border-zinc-200 hover:bg-zinc-50",
                )}
              >
                <span>
                  {p.label}
                  {p.code ? <span className="ms-1 text-xs text-zinc-400">{p.code}</span> : null}
                  {p.restriction ? <span className="block text-start text-xs text-rose-700">{translate(p.restriction)}</span> : null}
                </span>
                <span className="tabular-nums">
                  {cur()}
                  {n0(p.room_total)}
                  {p.vs_plain !== 0 && (
                    <span className={cn("ms-2 text-xs", p.vs_plain < 0 ? "text-emerald-700" : "text-rose-700")}>
                      {p.vs_plain > 0 ? "+" : ""}
                      {n0(p.vs_plain)}
                    </span>
                  )}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {data.voucher && (
        <p className={cn("text-sm", data.voucher.valid ? "text-emerald-700" : "text-rose-700")}>
          {data.voucher.valid
            ? t("Voucher {code} takes {amt} off.", { code: data.voucher.code, amt: `${cur()}${n0(data.voucher.discount ?? 0)}` })
            : data.voucher.reason}
        </p>
      )}
    </div>
  )
}
