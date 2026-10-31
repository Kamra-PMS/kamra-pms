/** All tills: who holds which, what is on its way to the cash office, tills
 *  that closed over or short, and the terminals themselves (name, outlet,
 *  which printer prints its bills). */
import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { Landmark, Lock, Plus, Unlock } from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { useAuth } from "../lib/auth"
import { useCashierAuth } from "../lib/cashierAuth"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { moneyLocale } from "../lib/money"
import { useT, t as translate } from "../lib/i18n"


const inr = (n: unknown) =>
  Number(n ?? 0).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })

const WRITE_ROLES = ["Finance", "Hotel Admin", "System Manager", "Administrator"]
const KINDS = ["Front Desk", "Restaurant", "Bar", "Spa", "Cash Office", "Other"]

type BoardSession = {
  name: string
  user: string
  cashier_id?: string
  opened_at: string
  expected_cash: number
}
type Till = {
  name: string | null
  terminal_name: string
  kind: string
  outlet: string | null
  bill_printer: string | null
  is_default: boolean
  sessions: BoardSession[]
  safe?: { balance: number; in_transit: number }
}
type Board = {
  business_date: string
  tills: Till[]
  pending_transfers: {
    name: string
    amount: number
    from_terminal: string | null
    to_terminal: string
    requested_by: string
  }[]
  variance_review: { name: string; user: string; variance: number; business_date: string }[]
}
type TerminalRow = {
  name: string
  terminal_name: string
  kind: string
  outlet: string | null
  bill_printer: string | null
  default_float: number
  disabled: 0 | 1
}
type Draft = Omit<TerminalRow, "name" | "disabled"> & { name?: string; disabled?: 0 | 1 }
type Printer = { name: string; printer_name: string; prints_bills: 0 | 1 }
type Outlet = { name: string; outlet_name: string }

const blank = (): Draft => ({
  terminal_name: "",
  kind: "Front Desk",
  outlet: null,
  bill_printer: null,
  default_float: 0,
})

export default function CashierBoard() {
  const { t } = useT()
  const { allowed } = useAuth()
  const { withPin } = useCashierAuth()
  const canEdit = allowed("Cashier Session", "manage_cash_office", WRITE_ROLES)
  const property = getCurrentProperty()
  const [board, setBoard] = useState<Board | null>(null)
  const [terminals, setTerminals] = useState<TerminalRow[]>([])
  const [printers, setPrinters] = useState<Printer[]>([])
  const [outlets, setOutlets] = useState<Outlet[]>([])
  const [form, setForm] = useState<Draft | null>(null)
  const [bankAmt, setBankAmt] = useState<Record<string, string>>({})
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const termName = (id: string | null) =>
    id ? (terminals.find((x) => x.name === id)?.terminal_name ?? id) : t("Default")

  const load = useCallback(async () => {
    try {
      const [b, tl, pr, ol] = await Promise.all([
        call<Board>("kamra.cashier.tills_board", { property }),
        call<TerminalRow[]>("kamra.cashier.terminals", { property, include_disabled: 1 }),
        call<Printer[]>("kamra.printing.printers", { property }),
        call<Outlet[]>("kamra.pos.outlets", { property }),
      ])
      setBoard(b)
      setTerminals(tl)
      setPrinters(pr)
      setOutlets(ol)
    } catch (e) {
      setErr(serverError(e))
    }
  }, [property])

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

  const receive = (transfer: string) =>
    act(() =>
      withPin(async (pin) => {
        await call("kamra.cashier.receive_transfer", { transfer, pin })
      }),
    )
  const approve = (session: string) =>
    act(async () => {
      await call("kamra.cashier.approve_variance", { session })
    })
  const bank = (office: string) =>
    act(() =>
      withPin(async (pin) => {
        await call("kamra.cashier.bank_deposit", {
          cash_office: office,
          amount: Number(bankAmt[office] || 0),
          pin,
        })
        setBankAmt({ ...bankAmt, [office]: "" })
      }),
    )
  const save = () =>
    act(async () => {
      if (!form) return
      await call("kamra.cashier.save_terminal", {
        property,
        name: form.name || undefined,
        terminal_name: form.terminal_name,
        kind: form.kind,
        outlet: form.outlet || undefined,
        bill_printer: form.bill_printer || undefined,
        default_float: Number(form.default_float || 0),
        disabled: form.disabled ?? 0,
      })
      setForm(null)
    })

  const billPrinters = printers.filter((p) => p.prints_bills)

  return (
    <div className="w-full max-w-none space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-400">
            {t("Cashier")}
          </p>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">{t("All tills")}</h1>
          <p className="mt-1 text-sm text-zinc-500">
            {t("Business date")}{" "}
            <span className="font-medium text-zinc-700">{board?.business_date ?? "-"}</span>
          </p>
        </div>
        <Link
          to="/cashier"
          className="rounded-lg border border-zinc-200 px-3 py-1.5 text-sm text-zinc-600 hover:bg-zinc-50"
        >
          {t("My till")}
        </Link>
      </div>

      {err ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">
          {translate(err)}
        </div>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {(board?.tills ?? []).map((tl) => (
          <Card key={tl.name ?? "default"}>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center justify-between gap-2 text-base">
                <span className="flex items-center gap-2">
                  {tl.kind === "Cash Office" ? <Landmark className="size-4" /> : null}
                  {tl.terminal_name}
                </span>
                <span
                  className={
                    "inline-flex items-center gap-1 text-xs font-normal " +
                    (tl.sessions.length ? "text-emerald-700" : "text-zinc-400")
                  }
                >
                  {tl.sessions.length ? <Unlock className="size-3" /> : <Lock className="size-3" />}
                  {tl.sessions.length ? t("Open") : t("Closed")}
                </span>
              </CardTitle>
              <p className="text-xs text-zinc-400">
                {translate(tl.kind)}
                {tl.outlet ? ` · ${outlets.find((o) => o.name === tl.outlet)?.outlet_name ?? tl.outlet}` : ""}
              </p>
            </CardHeader>
            <CardContent className="space-y-2 pt-0 text-sm">
              {tl.sessions.map((s) => (
                <div key={s.name} className="flex items-baseline justify-between gap-2">
                  <span className="truncate text-zinc-700">{s.cashier_id || s.user}</span>
                  <span className="tabular-nums text-zinc-900">
                    {inr(s.expected_cash)}
                    <span className="ml-1 text-xs text-zinc-400">
                      {String(s.opened_at).replace(" ", "T").slice(11, 16)}
                    </span>
                  </span>
                </div>
              ))}
              {tl.is_default && tl.sessions.length ? (
                <p className="text-xs text-zinc-400">
                  {t("Sessions opened without choosing a till.")}
                </p>
              ) : null}
              {tl.safe ? (
                <div className="space-y-2 border-t border-zinc-100 pt-2">
                  <div className="flex justify-between">
                    <span className="text-zinc-500">{t("In the safe")}</span>
                    <span className="font-semibold tabular-nums">{inr(tl.safe.balance)}</span>
                  </div>
                  {tl.safe.in_transit ? (
                    <div className="flex justify-between text-xs text-amber-700">
                      <span>{t("On its way")}</span>
                      <span className="tabular-nums">{inr(tl.safe.in_transit)}</span>
                    </div>
                  ) : null}
                  {canEdit && tl.name ? (
                    <div className="flex gap-2">
                      <input
                        className="w-full rounded-lg border border-zinc-300 px-3 py-1.5 text-sm"
                        placeholder={t("Amount to bank")}
                        inputMode="decimal"
                        value={bankAmt[tl.name] ?? ""}
                        onChange={(e) => setBankAmt({ ...bankAmt, [tl.name!]: e.target.value })}
                      />
                      <Button
                        variant="outline"
                        disabled={busy || !bankAmt[tl.name]}
                        onClick={() => bank(tl.name!)}
                      >
                        {t("Bank it")}
                      </Button>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </CardContent>
          </Card>
        ))}
      </div>

      {board?.pending_transfers.length ? (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">{t("Cash on its way to the cash office")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 pt-0">
            {board.pending_transfers.map((x) => (
              <div key={x.name} className="flex items-center justify-between gap-3 text-sm">
                <span className="text-zinc-600">
                  {termName(x.from_terminal)} → {termName(x.to_terminal)} · {x.requested_by}
                </span>
                <span className="flex items-center gap-3">
                  <span className="font-semibold tabular-nums">{inr(x.amount)}</span>
                  <Button variant="outline" disabled={busy} onClick={() => receive(x.name)}>
                    {t("Received")}
                  </Button>
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {board?.variance_review.length ? (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">{t("Tills to review")}</CardTitle>
            <p className="text-sm font-normal text-zinc-500">
              {t("Closed over or short by more than the allowed variance.")}
            </p>
          </CardHeader>
          <CardContent className="space-y-2 pt-0">
            {board.variance_review.map((v) => (
              <div key={v.name} className="flex items-center justify-between gap-3 text-sm">
                <span className="text-zinc-600">
                  {v.user} · {v.business_date}
                </span>
                <span className="flex items-center gap-3">
                  <span className="font-semibold tabular-nums text-rose-700">{inr(v.variance)}</span>
                  {canEdit ? (
                    <Button variant="outline" disabled={busy} onClick={() => approve(v.name)}>
                      {t("Approve")}
                    </Button>
                  ) : null}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-3 pb-2">
          <div>
            <CardTitle className="text-base">{t("Terminals")}</CardTitle>
            <p className="text-sm font-normal text-zinc-500">
              {t("Name each till, tie it to an outlet, and choose the printer that prints its bills. Without terminals everyone uses the Default till.")}
            </p>
          </div>
          {canEdit ? (
            <Button onClick={() => setForm(blank())}>
              <Plus className="mr-1.5 size-4" />
              {t("Add terminal")}
            </Button>
          ) : null}
        </CardHeader>
        <CardContent className="pt-0">
          {terminals.length ? (
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-zinc-400">
                <tr>
                  <th className="py-2 pr-3">{t("Name")}</th>
                  <th className="py-2 pr-3">{t("Kind")}</th>
                  <th className="py-2 pr-3">{t("Outlet")}</th>
                  <th className="py-2 pr-3">{t("Bill printer")}</th>
                  <th className="py-2" />
                </tr>
              </thead>
              <tbody>
                {terminals.map((x) => (
                  <tr key={x.name} className="border-t border-zinc-100">
                    <td className="py-2 pr-3">
                      {x.terminal_name}
                      {x.disabled ? (
                        <span className="ml-2 text-xs text-zinc-400">{t("Disabled")}</span>
                      ) : null}
                    </td>
                    <td className="py-2 pr-3">{translate(x.kind)}</td>
                    <td className="py-2 pr-3 text-zinc-500">
                      {outlets.find((o) => o.name === x.outlet)?.outlet_name ?? "-"}
                    </td>
                    <td className="py-2 pr-3 text-zinc-500">
                      {printers.find((p) => p.name === x.bill_printer)?.printer_name ?? t("This device")}
                    </td>
                    <td className="py-2 text-right">
                      {canEdit ? (
                        <Button variant="ghost" onClick={() => setForm({ ...x })}>
                          {t("Edit")}
                        </Button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="rounded-lg border border-dashed border-zinc-200 px-4 py-6 text-center text-sm text-zinc-500">
              {t("No terminals yet. Everyone works from the Default till, as before.")}
            </p>
          )}

          {form ? (
            <div className="mt-4 space-y-3 rounded-xl border border-zinc-200 bg-zinc-50/60 p-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block text-sm">
                  <span className="mb-1 block text-zinc-600">{t("Name")}</span>
                  <input
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm"
                    value={form.terminal_name}
                    onChange={(e) => setForm({ ...form, terminal_name: e.target.value })}
                  />
                </label>
                <label className="block text-sm">
                  <span className="mb-1 block text-zinc-600">{t("Kind")}</span>
                  <select
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm"
                    value={form.kind}
                    onChange={(e) => setForm({ ...form, kind: e.target.value })}
                  >
                    {KINDS.map((k) => (
                      <option key={k} value={k}>{translate(k)}</option>
                    ))}
                  </select>
                </label>
                <label className="block text-sm">
                  <span className="mb-1 block text-zinc-600">{t("Outlet")}</span>
                  <select
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm"
                    value={form.outlet || ""}
                    onChange={(e) => setForm({ ...form, outlet: e.target.value || null })}
                  >
                    <option value="">{t("None")}</option>
                    {outlets.map((o) => (
                      <option key={o.name} value={o.name}>
                        {o.outlet_name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block text-sm">
                  <span className="mb-1 block text-zinc-600">{t("Bill printer")}</span>
                  <select
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm"
                    value={form.bill_printer || ""}
                    onChange={(e) => setForm({ ...form, bill_printer: e.target.value || null })}
                  >
                    <option value="">{t("This device prints it")}</option>
                    {billPrinters.map((p) => (
                      <option key={p.name} value={p.name}>
                        {p.printer_name}
                      </option>
                    ))}
                  </select>
                  <span className="mt-1 block text-xs text-zinc-400">
                    {t("Only printers set to print bills are listed. KOTs are set on each printer's routes, not here.")}{" "}
                    <Link to="/printers" className="text-brand-700 hover:underline">
                      {t("Printers")}
                    </Link>
                  </span>
                </label>
                <label className="block text-sm">
                  <span className="mb-1 block text-zinc-600">{t("Default opening float")}</span>
                  <input
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm"
                    inputMode="decimal"
                    value={form.default_float}
                    onChange={(e) => setForm({ ...form, default_float: Number(e.target.value) })}
                  />
                </label>
                {form.name ? (
                  <label className="flex items-center gap-2 self-end pb-2 text-sm">
                    <input
                      type="checkbox"
                      checked={!!form.disabled}
                      onChange={(e) => setForm({ ...form, disabled: e.target.checked ? 1 : 0 })}
                    />
                    {t("Disabled")}
                  </label>
                ) : null}
              </div>
              <div className="flex gap-2">
                <Button disabled={busy || !form.terminal_name.trim()} onClick={save}>
                  {t("Save")}
                </Button>
                <Button variant="ghost" onClick={() => setForm(null)}>
                  {t("Cancel")}
                </Button>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}
