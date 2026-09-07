import { useCallback, useEffect, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { moneyLocale } from "../lib/money"

const inr = (n: unknown) =>
  Number(n ?? 0).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })

export default function CashierShiftReport() {
  const [params] = useSearchParams()
  const [date, setDate] = useState("")
  const [report, setReport] = useState<{
    business_date: string
    sessions: Record<string, unknown>[]
    journal: { kind: string; mode: string; txns: number; total: number }[]
  } | null>(null)
  const [sessionDetail, setSessionDetail] = useState<Record<
    string,
    unknown
  > | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const out = await call<typeof report & object>("kamra.cashier.shift_report", {
        property: getCurrentProperty(),
        business_date: date || undefined,
      })
      setReport(out as NonNullable<typeof report>)
      if (!date) setDate((out as { business_date: string }).business_date)
      const sid = params.get("session")
      if (sid) {
        const d = await call<Record<string, unknown>>(
          "kamra.cashier.session_report",
          { session: sid },
        )
        setSessionDetail(d)
      }
    } catch (e) {
      setErr(serverError(e))
    }
  }, [date, params])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-4 sm:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-400">
            Cashier
          </p>
          <h1 className="text-2xl font-semibold">Shift Report</h1>
        </div>
        <input
          type="date"
          className="rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />
      </div>
      {err ? <p className="text-sm text-rose-600">{err}</p> : null}

      <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="border-b text-xs uppercase text-zinc-400">
            <tr>
              <th className="px-3 py-2">Cashier</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Cash</th>
              <th className="px-3 py-2">Card</th>
              <th className="px-3 py-2">UPI</th>
              <th className="px-3 py-2">Variance</th>
            </tr>
          </thead>
          <tbody>
            {(report?.sessions || []).map((s) => (
              <tr key={String(s.name)} className="border-t">
                <td className="px-3 py-2">
                  {String(s.cashier_id || s.user)}
                </td>
                <td className="px-3 py-2">{String(s.status)}</td>
                <td className="px-3 py-2 tabular-nums">{inr(s.system_cash)}</td>
                <td className="px-3 py-2 tabular-nums">{inr(s.system_card)}</td>
                <td className="px-3 py-2 tabular-nums">{inr(s.system_upi)}</td>
                <td className="px-3 py-2 tabular-nums">{inr(s.variance)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div>
        <h2 className="mb-2 text-sm font-semibold text-zinc-700">
          Journal by kind / mode
        </h2>
        <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b text-xs uppercase text-zinc-400">
              <tr>
                <th className="px-3 py-2">Kind</th>
                <th className="px-3 py-2">Mode</th>
                <th className="px-3 py-2">Txns</th>
                <th className="px-3 py-2">Total</th>
              </tr>
            </thead>
            <tbody>
              {(report?.journal || []).map((j, i) => (
                <tr key={i} className="border-t">
                  <td className="px-3 py-2">{j.kind}</td>
                  <td className="px-3 py-2">{j.mode}</td>
                  <td className="px-3 py-2">{j.txns}</td>
                  <td className="px-3 py-2 tabular-nums">{inr(j.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {sessionDetail ? (
        <pre className="overflow-x-auto rounded-xl bg-zinc-50 p-3 text-xs text-zinc-600">
          {JSON.stringify(sessionDetail.totals, null, 2)}
        </pre>
      ) : null}
    </div>
  )
}
