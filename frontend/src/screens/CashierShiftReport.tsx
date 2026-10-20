import { useCallback, useEffect, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { Badge } from "../components/ui/badge"
import { moneyLocale } from "../lib/money"
import { useT } from "../lib/i18n"

const inr = (n: unknown) =>
  Number(n ?? 0).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })

type SessionRow = Record<string, unknown> & {
  name: string
  cashier_id?: string
  user?: string
  status?: string
}

type Totals = {
  cash?: number
  card?: number
  upi?: number
  other?: number
  paid_outs?: number
  drops?: number
  petty_cash?: number
  opening_float?: number
  expected_cash?: number
}

export default function CashierShiftReport() {
  const { t } = useT()
  const [params, setParams] = useSearchParams()
  const [date, setDate] = useState("")
  const [report, setReport] = useState<{
    business_date: string
    sessions: SessionRow[]
    journal: { kind: string; mode: string; txns: number; total: number }[]
  } | null>(null)
  const [sessionDetail, setSessionDetail] = useState<{
    name?: string
    cashier_id?: string
    status?: string
    totals?: Totals
    expected_cash?: number
    counted_cash?: number
    variance?: number
  } | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const selected = params.get("session")

  const load = useCallback(async () => {
    try {
      const out = await call<{
        business_date: string
        sessions: SessionRow[]
        journal: { kind: string; mode: string; txns: number; total: number }[]
      }>("kamra.cashier.shift_report", {
        property: getCurrentProperty(),
        business_date: date || undefined,
      })
      setReport(out)
      if (!date) setDate(out.business_date)
      const pick =
        selected ||
        out.sessions?.find((s) => s.status === "Open")?.name ||
        out.sessions?.[0]?.name
      if (pick && !selected) {
        setParams({ session: String(pick) }, { replace: true })
        return
      }
      if (pick) {
        const d = await call<NonNullable<typeof sessionDetail>>(
          "kamra.cashier.session_report",
          { session: pick },
        )
        setSessionDetail(d)
      } else {
        setSessionDetail(null)
      }
    } catch (e) {
      setErr(serverError(e))
    }
  }, [date, selected])

  useEffect(() => {
    void load()
  }, [load])

  const pickSession = (name: string) => {
    const next = new URLSearchParams(params)
    next.set("session", name)
    setParams(next)
  }

  const totals = sessionDetail?.totals

  return (
    <div className="w-full max-w-none space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-400">
            {t("Cashier")}
          </p>
          <h1 className="text-2xl font-semibold tracking-tight">{t("Shift Report")}</h1>
          <p className="mt-1 max-w-2xl text-sm text-zinc-500">
            {t(
              "Day totals by cashier. Sessions open on My Till - guest money posts from Front Desk and POS. Click a row for that till's breakdown.",
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to="/cashier"
            className="rounded-lg border border-zinc-200 px-3 py-1.5 text-sm text-zinc-600 hover:bg-zinc-50"
          >
            {t("My Till")}
          </Link>
          <input
            type="date"
            aria-label={t("Business date")}
            className="rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </div>
      </div>
      {err ? <p className="text-sm text-rose-600">{err}</p> : null}

      <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white">
        <table className="w-full table-fixed text-left text-sm">
          <thead className="border-b text-xs uppercase text-zinc-400">
            <tr>
              <th className="w-[28%] px-3 py-2">{t("Cashier")}</th>
              <th className="w-[12%] px-3 py-2">{t("Status")}</th>
              <th className="px-3 py-2">{t("Cash")}</th>
              <th className="px-3 py-2">{t("Card")}</th>
              <th className="px-3 py-2">{t("UPI")}</th>
              <th className="px-3 py-2">{t("Variance")}</th>
            </tr>
          </thead>
          <tbody>
            {(report?.sessions || []).map((s) => {
              const active = selected === s.name
              return (
                <tr
                  key={String(s.name)}
                  className={
                    "cursor-pointer border-t hover:bg-zinc-50" +
                    (active ? " bg-brand-50/50" : "")
                  }
                  onClick={() => pickSession(String(s.name))}
                >
                  <td className="px-3 py-2.5 font-medium text-zinc-800">
                    {String(s.cashier_id || s.user)}
                  </td>
                  <td className="px-3 py-2.5">
                    <Badge tone={s.status === "Open" ? "green" : "zinc"}>
                      {String(s.status)}
                    </Badge>
                  </td>
                  <td className="px-3 py-2.5 tabular-nums">{inr(s.system_cash)}</td>
                  <td className="px-3 py-2.5 tabular-nums">{inr(s.system_card)}</td>
                  <td className="px-3 py-2.5 tabular-nums">{inr(s.system_upi)}</td>
                  <td className="px-3 py-2.5 tabular-nums">{inr(s.variance)}</td>
                </tr>
              )
            })}
            {!report?.sessions?.length ? (
              <tr>
                <td colSpan={6} className="px-3 py-10 text-center text-zinc-400">
                  {t("No sessions on this date. Open a till on My Till to start a shift.")}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      {sessionDetail && totals ? (
        <div className="space-y-2">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-sm font-semibold text-zinc-800">
              {t("Till detail")} ·{" "}
              <span className="font-medium text-zinc-600">
                {sessionDetail.cashier_id || selected}
              </span>
            </h2>
            <Badge tone={sessionDetail.status === "Open" ? "green" : "zinc"}>
              {String(sessionDetail.status || "")}
            </Badge>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
            {(
              [
                [t("Float"), totals.opening_float],
                [t("Cash"), totals.cash],
                [t("Card"), totals.card],
                [t("UPI"), totals.upi],
                [t("Paid outs"), totals.paid_outs],
                [t("Drops"), totals.drops],
                [t("Petty cash"), totals.petty_cash],
                [t("Expected"), totals.expected_cash ?? sessionDetail.expected_cash],
                [t("Counted"), sessionDetail.counted_cash],
                [t("Variance"), sessionDetail.variance],
              ] as [string, unknown][]
            ).map(([label, val]) => (
              <div
                key={label}
                className="rounded-xl border border-zinc-200 bg-white px-3 py-2.5"
              >
                <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-400">
                  {label}
                </p>
                <p className="mt-0.5 text-base font-semibold tabular-nums">
                  {inr(val)}
                </p>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div>
        <h2 className="mb-2 text-sm font-semibold text-zinc-700">
          {t("Journal by kind / mode")}
        </h2>
        <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white">
          <table className="w-full table-fixed text-left text-sm">
            <thead className="border-b text-xs uppercase text-zinc-400">
              <tr>
                <th className="w-[30%] px-3 py-2">{t("Kind")}</th>
                <th className="w-[25%] px-3 py-2">{t("Mode")}</th>
                <th className="px-3 py-2">{t("Txns")}</th>
                <th className="px-3 py-2">{t("Total")}</th>
              </tr>
            </thead>
            <tbody>
              {(report?.journal || []).map((j, i) => (
                <tr key={i} className="border-t">
                  <td className="px-3 py-2">{j.kind}</td>
                  <td className="px-3 py-2">{j.mode}</td>
                  <td className="px-3 py-2 tabular-nums">{j.txns}</td>
                  <td className="px-3 py-2 tabular-nums">{inr(j.total)}</td>
                </tr>
              ))}
              {!report?.journal?.length ? (
                <tr>
                  <td colSpan={4} className="px-3 py-8 text-center text-zinc-400">
                    {t("No journal lines for this date.")}
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
