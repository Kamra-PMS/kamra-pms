import { useEffect, useState } from "react"
import { call, getCurrentProperty } from "../lib/api"
import { InfoTip } from "./InfoTip"
import { cur, moneyLocale } from "../lib/money"
import { useT } from "../lib/i18n"
import { cn } from "../lib/utils"

const n0 = (n: number) => Number(n ?? 0).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })

export interface NightRate {
  date: string
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
}

interface Options {
  nights: NightRate[]
  plain: { room_total: number; amount_after_tax: number }
  plans: PlanRow[]
  voucher: { code: string; valid: boolean; discount?: number; kind?: string; value?: number; reason?: string } | null
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
}) {
  const { t } = useT()
  const [data, setData] = useState<Options | null>(null)
  const [err, setErr] = useState<string | null>(null)

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

  if (err) return <p className="text-xs text-zinc-400">{err}</p>
  if (!data) return null
  const moved = data.nights.some((x) => x.season || x.demand)
  return (
    <div className="space-y-3 rounded-xl border border-zinc-200 p-4">
      <div className="flex items-center gap-1.5">
        <h3 className="text-sm font-semibold text-zinc-800">{t("Rates for these dates")}</h3>
        <InfoTip doc="revenue">
          {t("BAR is the best available rate: the room type's base price. A season or a busy-house (demand) rule can move it for a date. A rate plan then adjusts the whole stay, and a voucher comes off the total.")}
        </InfoTip>
      </div>

      <ul className="divide-y divide-zinc-100 text-sm">
        {data.nights.map((x) => (
          <li key={x.date} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-1.5">
            <span className="w-24 text-zinc-500">{x.date.slice(5)}</span>
            <span className="font-medium tabular-nums">
              {cur()}
              {n0(x.rate)}
            </span>
            {x.rate !== x.bar && (
              <span className="text-xs text-zinc-400 tabular-nums">
                {t("BAR {r}", { r: `${cur()}${n0(x.bar)}` })}
              </span>
            )}
            {x.season && (
              <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs text-amber-800">
                {x.season.label} {x.season.change}
              </span>
            )}
            {x.demand && (
              <span className="rounded-full bg-rose-50 px-2 py-0.5 text-xs text-rose-800">
                {t("Busy house {p}%", { p: Math.round(x.occupancy) })}
                {x.demand.premium_pct ? ` +${x.demand.premium_pct}%` : ""}
              </span>
            )}
          </li>
        ))}
      </ul>
      {!moved && (
        <p className="text-xs text-zinc-400">{t("No season or demand rule applies: every night is at BAR.")}</p>
      )}

      {data.plans.length > 0 && (
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
            {data.plans.map((p) => (
              <button
                key={p.name}
                type="button"
                onClick={() => onPickPlan(p.name)}
                className={cn(
                  "flex w-full items-center justify-between rounded-lg border px-3 py-1.5 text-sm",
                  ratePlan === p.name ? "border-brand-600 bg-brand-50" : "border-zinc-200 hover:bg-zinc-50",
                )}
              >
                <span>
                  {p.label}
                  {p.code ? <span className="ms-1 text-xs text-zinc-400">{p.code}</span> : null}
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
