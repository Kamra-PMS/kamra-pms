import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { Building2, Wallet } from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { useCashierAuth } from "../lib/cashierAuth"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { moneyLocale } from "../lib/money"
import { useT } from "../lib/i18n"

const inr = (n: unknown) =>
  Number(n ?? 0).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })

const CATS = [
  "Supplies",
  "Maintenance",
  "Transport",
  "Staff Welfare",
  "Miscellaneous",
]

type Voucher = {
  name: string
  voucher_date?: string
  payee?: string
  category?: string
  amount?: number
  reason?: string
  status?: string
}

type Report = {
  property: string
  property_name: string
  imprest: number
  business_date: string
  spent_today: number
  spent_month: number
  spent_all_time: number
  voucher_count: number
  vouchers: Voucher[]
}

export default function PettyCash() {
  const { t } = useT()
  const { withPin } = useCashierAuth()
  const property = getCurrentProperty()
  const [report, setReport] = useState<Report | null>(null)
  const [payee, setPayee] = useState("")
  const [amount, setAmount] = useState("")
  const [category, setCategory] = useState("Miscellaneous")
  const [reason, setReason] = useState("")
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [imprestAmt, setImprestAmt] = useState("")

  const load = useCallback(() => {
    call<Report>("kamra.cashier.petty_cash_report", {
      property: getCurrentProperty(),
    })
      .then((r) => {
        setReport(r)
        setImprestAmt(String(r.imprest ?? 0))
      })
      .catch((e) => setErr(serverError(e)))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const submit = async () => {
    setBusy(true)
    setErr(null)
    try {
      await withPin(async (pin) => {
        await call("kamra.cashier.post_petty_cash", {
          property: getCurrentProperty(),
          amount: Number(amount),
          payee,
          category,
          reason,
          pin,
        })
      })
      setPayee("")
      setAmount("")
      setReason("")
      load()
    } catch (e) {
      setErr(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const saveImprest = async () => {
    setBusy(true)
    setErr(null)
    try {
      await call("kamra.cashier.set_petty_cash_float", {
        property: getCurrentProperty(),
        amount: Number(imprestAmt || 0),
      })
      load()
    } catch (e) {
      setErr(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const rows = report?.vouchers || []
  return (
    <div className="w-full max-w-none space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-400">
            {t("Cashier")}
          </p>
          <h1 className="text-2xl font-semibold tracking-tight">{t("Petty Cash")}</h1>
          <p className="mt-1 flex flex-wrap items-center gap-1.5 text-sm text-zinc-500">
            <Building2 className="size-3.5 shrink-0" aria-hidden />
            <span className="font-medium text-zinc-800">
              {report?.property_name || property}
            </span>
            <span>· {t("This property only — switch hotel in the header to see another.")}</span>
          </p>
        </div>
        <Link
          to="/cashier"
          className="rounded-lg border border-zinc-200 px-3 py-1.5 text-sm text-zinc-600 hover:bg-zinc-50"
        >
          {t("My Till")}
        </Link>
      </div>

      {err ? <p className="text-sm text-rose-600">{err}</p> : null}

      <div className="grid gap-2 grid-cols-2 lg:grid-cols-4">
        {(
          [
            [t("Imprest (this property)"), report?.imprest, "money"],
            [t("Spent today"), report?.spent_today, "money"],
            [t("Spent this month"), report?.spent_month, "money"],
            [t("Vouchers"), report?.voucher_count, "count"],
          ] as [string, unknown, string][]
        ).map(([label, val, kind]) => (
          <div
            key={label}
            className="rounded-xl border border-zinc-200 bg-white px-3 py-2.5"
          >
            <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-400">
              {label}
            </p>
            <p className="mt-0.5 text-lg font-semibold tabular-nums text-zinc-900">
              {val == null ? "—" : kind === "count" ? String(val) : inr(val)}
            </p>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-zinc-200 bg-zinc-50/80 px-4 py-3">
        <label className="block text-sm">
          <span className="mb-1 block text-zinc-600">
            {t("Imprest for this property")}
          </span>
          <input
            className="w-40 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm"
            inputMode="decimal"
            value={imprestAmt}
            onChange={(e) => setImprestAmt(e.target.value)}
          />
        </label>
        <Button
          variant="outline"
          disabled={busy || imprestAmt === ""}
          onClick={() => void saveImprest()}
        >
          {t("Save imprest")}
        </Button>
        <p className="max-w-md text-xs text-zinc-500">
          {t(
            "Each hotel / branch keeps its own float and voucher list. Changing property in the header switches the box.",
          )}
        </p>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Wallet className="size-4" /> {t("New voucher")}
          </CardTitle>
          <p className="text-sm font-normal text-zinc-500">
            {t(
              "Posts against this property's open till. Open My Till first if the drawer is closed.",
            )}
          </p>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          <input
            className="rounded-lg border border-zinc-300 px-3 py-2 text-sm"
            placeholder={t("Payee")}
            value={payee}
            onChange={(e) => setPayee(e.target.value)}
          />
          <input
            className="rounded-lg border border-zinc-300 px-3 py-2 text-sm"
            placeholder={t("Amount")}
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
          <select
            className="rounded-lg border border-zinc-300 px-3 py-2 text-sm"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            {CATS.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
          <input
            className="rounded-lg border border-zinc-300 px-3 py-2 text-sm sm:col-span-2"
            placeholder={t("Reason")}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <Button
            disabled={busy || !payee || !amount || !reason}
            onClick={() => void submit()}
          >
            {t("Post voucher")}
          </Button>
        </CardContent>
      </Card>

      <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white">
        <div className="flex items-center justify-between border-b border-zinc-100 px-3 py-2">
          <h2 className="text-sm font-semibold text-zinc-800">
            {t("Vouchers")}
          </h2>
          <p className="text-xs text-zinc-400">
            {t("{n} posted", { n: report?.voucher_count ?? 0 })}
          </p>
        </div>
        <table className="w-full table-fixed text-left text-sm">
          <thead className="text-xs uppercase tracking-wide text-zinc-400">
            <tr>
              <th className="w-[14%] px-3 py-2">{t("Date")}</th>
              <th className="w-[22%] px-3 py-2">{t("Payee")}</th>
              <th className="w-[16%] px-3 py-2">{t("Category")}</th>
              <th className="w-[14%] px-3 py-2">{t("Amount")}</th>
              <th className="px-3 py-2">{t("Reason")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.name} className="border-t border-zinc-50">
                <td className="px-3 py-2">{String(r.voucher_date ?? "")}</td>
                <td className="px-3 py-2">{String(r.payee ?? "")}</td>
                <td className="px-3 py-2">{String(r.category ?? "")}</td>
                <td className="px-3 py-2 tabular-nums">{inr(r.amount)}</td>
                <td className="truncate px-3 py-2 text-zinc-500">
                  {String(r.reason ?? "")}
                </td>
              </tr>
            ))}
            {!rows.length ? (
              <tr>
                <td colSpan={5} className="px-3 py-10 text-center text-zinc-400">
                  {t(
                    "No petty cash vouchers for this property yet. Post one above — other hotels keep their own lists.",
                  )}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  )
}
