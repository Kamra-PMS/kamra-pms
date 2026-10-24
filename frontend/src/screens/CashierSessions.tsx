import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { Badge } from "../components/ui/badge"
import { moneyLocale } from "../lib/money"
import { t as translate, useUILanguage } from "../lib/i18n"

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
  useUILanguage()
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
    <div className="w-full max-w-none space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-400">{translate("Cashier")}</p>
          <h1 className="text-2xl font-semibold">{translate("Sessions")}</h1>
          <p className="mt-1 max-w-2xl text-sm text-zinc-500">{translate("Open and close tills on")}{" "}
            <Link to="/cashier" className="font-medium text-brand-700 hover:underline">{translate("My Till")}</Link>{translate(". There is no separate “create till” form - opening a session starts the shift.")}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to="/cashier"
            className="rounded-lg bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700"
          >{translate("Open / close till")}</Link>
          <label className="text-sm">
            <span className="mr-2 text-zinc-500">{translate("Business date")}</span>
            <input
              type="date"
              className="rounded-lg border border-zinc-300 px-2 py-1.5"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </label>
        </div>
      </div>
      {err ? (
        <p className="text-sm text-rose-600">{translate(err)}</p>
      ) : null}
      <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white">
        <table className="w-full table-fixed text-left text-sm">
          <thead className="border-b border-zinc-100 text-xs uppercase tracking-wide text-zinc-400">
            <tr>
              <th className="w-[28%] px-3 py-2">{translate("Cashier")}</th>
              <th className="w-[12%] px-3 py-2">{translate("Status")}</th>
              <th className="px-3 py-2">{translate("Float")}</th>
              <th className="px-3 py-2">{translate("Cash")}</th>
              <th className="px-3 py-2">{translate("Expected")}</th>
              <th className="px-3 py-2">{translate("Counted")}</th>
              <th className="px-3 py-2">{translate("Variance")}</th>
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
                    {translate(r.status)}
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
                <td colSpan={7} className="px-3 py-10 text-center text-zinc-400">{translate("No sessions for this date.")}{" "}
                  <Link to="/cashier" className="text-brand-700 hover:underline">{translate("Open a till")}</Link>{" "}{translate("to start.")}</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  )
}
