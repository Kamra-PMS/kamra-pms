import { Fragment, useCallback, useEffect, useState } from "react"
import { ChevronDown, ChevronRight } from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { Button } from "../components/ui/button"
import { Card, CardContent } from "../components/ui/card"
import { fmtMoney, useLocale } from "../lib/money"
import { t as translate, uiDateLocale, useUILanguage } from "../lib/i18n"

// Cash outlook: the next 5, 15 or 30 days of money in and out
// (kamra.books.cash_forecast). Draft supplier bills count, flagged.
// Read-only: every figure is the server's.

type Item = { kind: string; date: string; label: string; amount: number; overdue: boolean; draft?: boolean }
type Day = {
  date: string
  company_bills: number
  departures: number
  deposits: number
  vendor_bills: number
  money_in: number
  money_out: number
  net: number
  closing: number
  items: Item[]
}
type Week = { from_date: string; to_date: string; money_in: number; money_out: number; net: number; closing: number }
type Forecast = {
  opening: number
  opening_source: "tills" | "entered"
  days: Day[]
  weeks: Week[]
  money_in: number
  money_out: number
  closing: number
  overdue_in: number
  overdue_out: number
  draft_out: number
}
const SPANS = [5, 15, 30] as const

const KIND: Record<string, string> = {
  company_bills: "Company bill",
  departures: "Guest leaving",
  deposits: "Deposit due",
  vendor_bills: "Supplier bill",
}

export default function CashForecast() {
  useUILanguage()
  useLocale()
  const [data, setData] = useState<Forecast | null>(null)
  const [opening, setOpening] = useState("")
  const [span, setSpan] = useState<number>(5)
  const [open, setOpen] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const load = useCallback((start: string, days: number) => {
    call<Forecast>("kamra.books.cash_forecast", {
      property: getCurrentProperty(),
      days,
      opening: start === "" ? undefined : Number(start),
    })
      .then(setData)
      .catch((e) => setErr(serverError(e)))
  }, [])
  // ponytail: the opening amount applies on Update or when the span changes
  useEffect(() => load(opening, span), [load, span]) // eslint-disable-line react-hooks/exhaustive-deps

  const short = (iso: string) =>
    new Date(`${iso}T00:00:00`).toLocaleDateString(uiDateLocale(), { day: "numeric", month: "short" })

  const day = (iso: string, i: number) =>
    i === 0
      ? translate("Today")
      : new Date(`${iso}T00:00:00`).toLocaleDateString(uiDateLocale(), {
          weekday: "short", day: "numeric", month: "short",
        })

  return (
    <div className="w-full space-y-5">
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-400">{translate("Books")}</p>
        <h1 className="text-2xl font-semibold">{translate("Cash outlook")}</h1>
        <p className="text-sm text-zinc-500">{translate("Money expected in and out, day by day. Overdue items are counted today.")}</p>
      </div>
      <div className="inline-flex rounded-lg border border-zinc-200 bg-white p-0.5" role="group" aria-label={translate("Days ahead")}>
        {SPANS.map((n) => (
          <button
            key={n}
            type="button"
            aria-pressed={span === n}
            onClick={() => setSpan(n)}
            className={`rounded-md px-3 py-1.5 text-sm ${span === n ? "bg-zinc-900 text-white" : "text-zinc-600 hover:bg-zinc-50"}`}
          >
            {translate("{v0} days", { v0: n })}
          </button>
        ))}
      </div>
      {err ? <p className="text-sm text-rose-600">{translate(err)}</p> : null}

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-zinc-200 bg-zinc-50/80 px-4 py-3">
        <label className="block text-sm">
          <span className="mb-1 block text-zinc-600">{translate("Cash and bank today")}</span>
          <input
            className="w-44 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm"
            inputMode="decimal"
            placeholder={data ? String(data.opening) : ""}
            value={opening}
            onChange={(e) => setOpening(e.target.value)}
          />
        </label>
        <Button variant="outline" onClick={() => load(opening, span)}>{translate("Update")}</Button>
        <p className="max-w-md text-xs text-zinc-500">
          {data?.opening_source === "tills"
            ? translate("Starting from the cash in open tills. Kamra does not know your bank balance, so type it in for a full picture.")
            : translate("Starting from the amount you entered.")}
        </p>
      </div>

      {data ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Starting position" value={fmtMoney(data.opening)} />
          <Stat label="Money in" value={fmtMoney(data.money_in)} tone="text-emerald-700" />
          <Stat label="Money out" value={fmtMoney(data.money_out)} tone="text-rose-700" />
          <Stat label={translate("Position after {v0} days", { v0: data.days.length })} value={fmtMoney(data.closing)} tone={data.closing < 0 ? "text-rose-700" : undefined} />
        </div>
      ) : null}
      {data && (data.overdue_in > 0 || data.overdue_out > 0) ? (
        <p className="-mt-2 text-xs text-zinc-500">
          {translate("Today includes {v0} overdue to come in and {v1} overdue to pay.", {
            v0: fmtMoney(data.overdue_in), v1: fmtMoney(data.overdue_out),
          })}
        </p>
      ) : null}
      {data && data.draft_out > 0 ? (
        <p className="-mt-2 text-xs text-amber-700">
          {translate("Money out includes {v0} in draft supplier bills still awaiting approval.", { v0: fmtMoney(data.draft_out) })}
        </p>
      ) : null}

      <Card>
        <CardContent className="overflow-x-auto pt-4">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-zinc-400">
              <tr>
                <th className="py-2 pr-3">{translate("Day")}</th>
                <th className="hidden py-2 pr-3 text-right sm:table-cell">{translate("Company bills")}</th>
                <th className="hidden py-2 pr-3 text-right sm:table-cell">{translate("Guests leaving")}</th>
                <th className="hidden py-2 pr-3 text-right sm:table-cell">{translate("Deposits")}</th>
                <th className="hidden py-2 pr-3 text-right sm:table-cell">{translate("Supplier bills")}</th>
                <th className="py-2 pr-3 text-right">{translate("Net")}</th>
                <th className="py-2 text-right">{translate("Position")}</th>
              </tr>
            </thead>
            <tbody>
              {(data?.days ?? []).map((d, i) => (
                <Fragment key={d.date}>
                  <tr
                    className="cursor-pointer border-t border-zinc-100 hover:bg-zinc-50"
                    onClick={() => setOpen(open === d.date ? null : d.date)}
                  >
                    <td className="py-2 pr-3 font-medium">
                      <span className="inline-flex items-center gap-1">
                        {open === d.date ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
                        {day(d.date, i)}
                      </span>
                    </td>
                    <Money v={d.company_bills} wide />
                    <Money v={d.departures} wide />
                    <Money v={d.deposits} wide />
                    <Money v={-d.vendor_bills} wide />
                    <Money v={d.net} strong />
                    <td className={`py-2 text-right font-semibold tabular-nums ${d.closing < 0 ? "text-rose-700" : ""}`}>{fmtMoney(d.closing)}</td>
                  </tr>
                  {open === d.date ? (
                    <tr className="bg-zinc-50/60">
                      <td colSpan={7} className="px-6 py-2">
                        {d.items.length ? (
                          <ul className="divide-y divide-zinc-100 text-xs">
                            {d.items.map((it) => (
                              <li key={`${it.kind}-${it.label}`} className="flex justify-between gap-3 py-1.5">
                                <span>
                                  <span className="text-zinc-400">{translate(KIND[it.kind] ?? it.kind)}</span>{" "}
                                  {it.label}
                                  {it.overdue ? <span className="ml-1 text-rose-700">({translate("overdue")})</span> : null}
                                  {it.draft ? <span className="ml-1 text-amber-700">({translate("draft, awaiting approval")})</span> : null}
                                </span>
                                <span className={`tabular-nums ${it.kind === "vendor_bills" ? "text-rose-700" : ""}`}>
                                  {it.kind === "vendor_bills" ? "-" : ""}{fmtMoney(it.amount)}
                                </span>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="text-xs text-zinc-400">{translate("Nothing expected this day.")}</p>
                        )}
                      </td>
                    </tr>
                  ) : null}
                  {data && data.days.length > 5 && (i % 7 === 6 || i === data.days.length - 1) ? (
                    <WeekRow w={data.weeks[Math.floor(i / 7)]} label={`${short(data.weeks[Math.floor(i / 7)].from_date)} - ${short(d.date)}`} />
                  ) : null}
                </Fragment>
              ))}
              {!data ? (
                <tr><td colSpan={7} className="py-8 text-center text-zinc-400">{translate("Loading…")}</td></tr>
              ) : null}
            </tbody>
          </table>
        </CardContent>
      </Card>
      <p className="text-xs text-zinc-500">
        {translate("Not included: payroll, rent and other costs that are not entered as supplier bills, and extras guests may still spend.")}
      </p>
    </div>
  )
}

function WeekRow({ w, label }: { w: Week; label: string }) {
  useUILanguage()
  return (
    <tr className="border-t border-zinc-200 bg-zinc-100/70 text-xs font-medium">
      <td className="py-2 pr-3">{translate("Week {v0}", { v0: label })}</td>
      <td colSpan={4} className="hidden py-2 pr-3 text-right tabular-nums sm:table-cell">
        <span className="text-emerald-700">{fmtMoney(w.money_in)}</span>
        {" / "}
        <span className="text-rose-700">-{fmtMoney(w.money_out)}</span>
      </td>
      <Money v={w.net} strong />
      <td className={`py-2 text-right font-semibold tabular-nums ${w.closing < 0 ? "text-rose-700" : ""}`}>{fmtMoney(w.closing)}</td>
    </tr>
  )
}

function Money({ v, strong, wide }: { v: number; strong?: boolean; wide?: boolean }) {
  return (
    <td className={`py-2 pr-3 text-right tabular-nums ${wide ? "hidden sm:table-cell" : ""} ${strong ? "font-medium" : ""} ${v < 0 ? "text-rose-700" : v === 0 ? "text-zinc-300" : ""}`}>
      {v === 0 ? "-" : fmtMoney(v)}
    </td>
  )
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  useUILanguage()
  return (
    <div className="rounded-lg border border-zinc-200 bg-white px-3 py-2">
      <div className="text-xs text-zinc-400">{translate(label)}</div>
      <div className={`text-lg font-semibold tabular-nums ${tone ?? ""}`}>{value}</div>
    </div>
  )
}
