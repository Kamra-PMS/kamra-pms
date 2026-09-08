import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import {
  Banknote,
  Lock,
  Unlock,
  ArrowDownToLine,
  Wallet,
} from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { useCashierAuth } from "../lib/cashierAuth"
import { Button } from "../components/ui/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../components/ui/card"
import { moneyLocale } from "../lib/money"
import { useT } from "../lib/i18n"

const inr = (n: unknown) =>
  Number(n ?? 0).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })

type Session = {
  open?: boolean
  name?: string
  business_date?: string
  cashier_id?: string
  status?: string
  opening_float?: number
  system_cash?: number
  system_card?: number
  system_upi?: number
  system_other?: number
  paid_outs?: number
  drops?: number
  petty_cash?: number
  expected_cash?: number
  counted_cash?: number
  variance?: number
  totals?: Record<string, number>
  transactions?: {
    name: string
    kind: string
    mode: string
    amount: number
    folio?: string
    pos_order?: string
    reference?: string
    posted_at?: string
  }[]
}

export default function CashierTill() {
  const { t } = useT()
  const { ensureUnlocked, withPin } = useCashierAuth()
  const [session, setSession] = useState<Session | null>(null)
  const [floatAmt, setFloatAmt] = useState("2000")
  const [counted, setCounted] = useState("")
  const [paidOutAmt, setPaidOutAmt] = useState("")
  const [paidOutReason, setPaidOutReason] = useState("")
  const [dropAmt, setDropAmt] = useState("")
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      const s = await call<Session>("kamra.cashier.current_session", {
        property: getCurrentProperty(),
      })
      setSession(s)
    } catch (e) {
      setErr(serverError(e))
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const act = async (fn: () => Promise<void>) => {
    setBusy(true)
    setErr(null)
    try {
      await fn()
      await load()
    } catch (e) {
      setErr(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const open = () =>
    act(async () => {
      await ensureUnlocked()
      const s = await call<Session>("kamra.cashier.open_session", {
        property: getCurrentProperty(),
        opening_float: Number(floatAmt || 0),
      })
      setSession({ open: true, ...s })
    })

  const close = () =>
    act(async () => {
      if (!session?.name) return
      await withPin(async (pin) => {
        await call("kamra.cashier.close_session", {
          session: session.name,
          counted_cash: Number(counted || 0),
          pin,
        })
      })
    })

  const paidOut = () =>
    act(async () => {
      await withPin(async (pin) => {
        await call("kamra.cashier.post_paid_out", {
          property: getCurrentProperty(),
          amount: Number(paidOutAmt || 0),
          reason: paidOutReason,
          pin,
        })
        setPaidOutAmt("")
        setPaidOutReason("")
      })
    })

  const drop = () =>
    act(async () => {
      await withPin(async (pin) => {
        await call("kamra.cashier.cash_drop", {
          property: getCurrentProperty(),
          amount: Number(dropAmt || 0),
          pin,
        })
        setDropAmt("")
      })
    })

  const openTill = session?.open || session?.status === "Open"

  return (
    <div className="mx-auto max-w-5xl space-y-5 p-4 sm:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-400">
            {t("Cashier")}
          </p>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">
            {t("My Till")}
          </h1>
          <p className="mt-1 text-sm text-zinc-500">
            {t("Business date")}{" "}
            <span className="font-medium text-zinc-700">
              {session?.business_date ?? "—"}
            </span>
            {session?.cashier_id ? (
              <>
                {" "}
                · {t("Cashier")}{" "}
                <span className="font-medium text-zinc-700">
                  {session.cashier_id}
                </span>
              </>
            ) : null}
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            to="/cashier/sessions"
            className="rounded-lg border border-zinc-200 px-3 py-1.5 text-sm text-zinc-600 hover:bg-zinc-50"
          >
            {t("All sessions")}
          </Link>
          <Link
            to="/cashier/shift-report"
            className="rounded-lg border border-zinc-200 px-3 py-1.5 text-sm text-zinc-600 hover:bg-zinc-50"
          >
            {t("Shift report")}
          </Link>
        </div>
      </div>

      {err ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">
          {err}
        </div>
      ) : null}

      {!openTill ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Lock className="size-4" /> {t("Open till")}
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap items-end gap-3">
            <label className="block text-sm">
              <span className="mb-1 block text-zinc-600">{t("Opening float")}</span>
              <input
                className="w-36 rounded-lg border border-zinc-300 px-3 py-2 text-sm"
                inputMode="decimal"
                value={floatAmt}
                onChange={(e) => setFloatAmt(e.target.value)}
              />
            </label>
            <Button disabled={busy} onClick={open}>
              <Unlock className="mr-1.5 size-4" />
              {t("Open session")}
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              [t("Float"), session?.opening_float],
              [t("Cash in"), session?.system_cash ?? session?.totals?.cash],
              [t("Card"), session?.system_card ?? session?.totals?.card],
              [t("UPI"), session?.system_upi ?? session?.totals?.upi],
              [t("Paid outs"), session?.paid_outs],
              [t("Drops"), session?.drops],
              [t("Petty cash"), session?.petty_cash],
              [t("Expected cash"), session?.expected_cash],
            ].map(([label, val]) => (
              <Card key={String(label)}>
                <CardContent className="pt-4">
                  <p className="text-xs font-medium uppercase tracking-wide text-zinc-400">
                    {label}
                  </p>
                  <p className="mt-1 text-xl font-semibold tabular-nums">
                    {inr(val)}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Banknote className="size-4" /> {t("Paid out")}
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap items-end gap-2">
                <input
                  className="w-28 rounded-lg border border-zinc-300 px-3 py-2 text-sm"
                  placeholder={t("Amount")}
                  value={paidOutAmt}
                  onChange={(e) => setPaidOutAmt(e.target.value)}
                />
                <input
                  className="min-w-[12rem] flex-1 rounded-lg border border-zinc-300 px-3 py-2 text-sm"
                  placeholder={t("Reason")}
                  value={paidOutReason}
                  onChange={(e) => setPaidOutReason(e.target.value)}
                />
                <Button
                  variant="outline"
                  disabled={busy || !paidOutAmt || !paidOutReason}
                  onClick={paidOut}
                >
                  {t("Post")}
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <ArrowDownToLine className="size-4" /> {t("Cash drop")}
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap items-end gap-2">
                <input
                  className="w-28 rounded-lg border border-zinc-300 px-3 py-2 text-sm"
                  placeholder={t("Amount")}
                  value={dropAmt}
                  onChange={(e) => setDropAmt(e.target.value)}
                />
                <Button
                  variant="outline"
                  disabled={busy || !dropAmt}
                  onClick={drop}
                >
                  {t("Drop to safe")}
                </Button>
                <Link
                  to="/cashier/petty-cash"
                  className="text-sm text-brand-700 hover:underline"
                >
                  {t("Petty cash →")}
                </Link>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Wallet className="size-4" /> {t("Close till")}
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap items-end gap-3">
              <label className="block text-sm">
                <span className="mb-1 block text-zinc-600">
                  {t("Counted cash (expected {amount})", { amount: inr(session?.expected_cash) })}
                </span>
                <input
                  className="w-40 rounded-lg border border-zinc-300 px-3 py-2 text-sm"
                  inputMode="decimal"
                  value={counted}
                  onChange={(e) => setCounted(e.target.value)}
                />
              </label>
              {counted !== "" ? (
                <p className="text-sm text-zinc-600">
                  {t("Variance")}:{" "}
                  <span className="font-semibold tabular-nums">
                    {inr(Number(counted) - Number(session?.expected_cash || 0))}
                  </span>
                </p>
              ) : null}
              <Button disabled={busy || counted === ""} onClick={close}>
                {t("Close session")}
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t("Recent transactions")}</CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-xs uppercase tracking-wide text-zinc-400">
                  <tr>
                    <th className="py-2 pr-3">{t("Kind")}</th>
                    <th className="py-2 pr-3">{t("Mode")}</th>
                    <th className="py-2 pr-3">{t("Amount")}</th>
                    <th className="py-2 pr-3">{t("Ref")}</th>
                    <th className="py-2">{t("When")}</th>
                  </tr>
                </thead>
                <tbody>
                  {(session?.transactions || []).map((tx) => (
                    <tr key={tx.name} className="border-t border-zinc-100">
                      <td className="py-2 pr-3">{tx.kind}</td>
                      <td className="py-2 pr-3">{tx.mode}</td>
                      <td className="py-2 pr-3 tabular-nums">{inr(tx.amount)}</td>
                      <td className="py-2 pr-3 text-zinc-500">
                        {tx.reference || tx.folio || tx.pos_order || "—"}
                      </td>
                      <td className="py-2 text-zinc-500">
                        {tx.posted_at
                          ? String(tx.posted_at).replace(" ", "T").slice(11, 16)
                          : ""}
                      </td>
                    </tr>
                  ))}
                  {!session?.transactions?.length ? (
                    <tr>
                      <td colSpan={5} className="py-6 text-center text-zinc-400">
                        {t("No transactions yet this session.")}
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
