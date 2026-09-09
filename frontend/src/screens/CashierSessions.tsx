import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { Badge } from "../components/ui/badge"
import { moneyLocale } from "../lib/money"

const inr = (n: unknown) =>
  Number(n ?? 0).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })

type Row = {
  name: string
  cashier_id?: string
  user: string
  business_date: string
  status: string
  opening_float: number
  system_cash: number
  expected_cash: number
  counted_cash: number
  variance: number
  opened_at: string
  closed_at?: string
}

export default function CashierSessions() {
  const [rows, setRows] = useState<Row[]>([])
  const [date, setDate] = useState("")
  const [err, setErr] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const out = await call<{ sessions: Row[]; business_date: string }>(
        "kamra.cashier.list_sessions",
        {
          property: getCurrentProperty(),
          business_date: date || undefined,
        },
      )
      setRows(out.sessions)
      if (!date) setDate(out.business_date)
    } catch (e) {
      setErr(serverError(e))
    }
  }, [date])

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
          <h1 className="text-2xl font-semibold">Sessions</h1>
        </div>
        <label className="text-sm">
          <span className="mr-2 text-zinc-500">Business date</span>
          <input
            type="date"
            className="rounded-lg border border-zinc-300 px-2 py-1.5"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </label>
      </div>
      {err ? (
        <p className="text-sm text-rose-600">{err}</p>
      ) : null}
      <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-zinc-100 text-xs uppercase tracking-wide text-zinc-400">
            <tr>
              <th className="px-3 py-2">Cashier</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Float</th>
              <th className="px-3 py-2">Cash</th>
              <th className="px-3 py-2">Expected</th>
              <th className="px-3 py-2">Counted</th>
              <th className="px-3 py-2">Variance</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.name} className="border-t border-zinc-50">
                <td className="px-3 py-2">
                  <Link
                    to={`/cashier/shift-report?session=${r.name}`}
                    className="font-medium text-brand-700 hover:underline"
                  >
                    {r.cashier_id || r.user}
                  </Link>
                  <div className="text-xs text-zinc-400">{r.user}</div>
                </td>
                <td className="px-3 py-2">
                  <Badge tone={r.status === "Open" ? "green" : "zinc"}>
                    {r.status}
                  </Badge>
                </td>
                <td className="px-3 py-2 tabular-nums">{inr(r.opening_float)}</td>
                <td className="px-3 py-2 tabular-nums">{inr(r.system_cash)}</td>
                <td className="px-3 py-2 tabular-nums">{inr(r.expected_cash)}</td>
                <td className="px-3 py-2 tabular-nums">{inr(r.counted_cash)}</td>
                <td className="px-3 py-2 tabular-nums">{inr(r.variance)}</td>
              </tr>
            ))}
            {!rows.length ? (
              <tr>
                <td colSpan={7} className="px-3 py-8 text-center text-zinc-400">
                  No sessions for this date.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  )
}
