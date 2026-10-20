import { useEffect, useMemo, useState } from "react"
import { call } from "../lib/api"
import { serverError } from "../lib/resource"
import { Button } from "../components/ui/button"
import { Sheet } from "../components/ui/sheet"
import { fmtMoney } from "../lib/money"

// Record a company's payment against its city ledger (AR) balance. The
// server (kamra.ledger.city_ledger_settle) decides what it clears; this
// screen previews the allocation and asks for a confirm first.

type OpenItem = {
  folio: string
  invoice_number?: string | null
  invoice_date: string
  due_date?: string
  days_overdue?: number
  guest_name?: string | null
  reservation?: string | null
  billed: number
  paid: number
  outstanding: number
}

type Account = {
  account: string
  company: string
  account_number?: string
  balance: number
  open_balance: number
  unapplied_credit: number
  credit_limit?: number
  credit_days?: number
  not_due: number
  d1_30: number
  d31_60: number
  d61_90: number
  d90p: number
  overdue: number
  open_items: OpenItem[]
  payments: { name: string; posting_date: string; credit: number; reference?: string }[]
}

type Result = {
  payment: string
  balance: number
  applied: { folio: string; amount: number }[]
  unapplied: number
}

const MODES = ["Bank Transfer", "Cheque", "Card", "UPI", "Cash", "Other"]

const r2 = (n: number) => Math.round(n * 100) / 100

export default function CityLedgerPayment(props: {
  account: string
  onClose: () => void
  onPosted: () => void
}) {
  const [acc, setAcc] = useState<Account | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [amount, setAmount] = useState("")
  const [mode, setMode] = useState(MODES[0])
  const [reference, setReference] = useState("")
  const [manual, setManual] = useState(false)
  const [picks, setPicks] = useState<Record<string, string>>({})
  const [step, setStep] = useState<"form" | "confirm" | "done">("form")
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<Result | null>(null)

  useEffect(() => {
    call<Account>("kamra.ledger.city_ledger_account", { account: props.account })
      .then(setAcc)
      .catch((e) => setErr(serverError(e)))
  }, [props.account])

  const amt = Number(amount) || 0
  const items = useMemo(() => acc?.open_items ?? [], [acc])

  // what the payment will clear - mirrors the server's rule for the preview
  const plan = useMemo(() => {
    if (manual) {
      return items
        .filter((it) => picks[it.folio] !== undefined)
        .map((it) => ({ folio: it.folio, amount: r2(Number(picks[it.folio]) || 0) }))
        .filter((p) => p.amount > 0)
    }
    let left = r2(amt)
    const out: { folio: string; amount: number }[] = []
    for (const it of items) {
      if (left <= 0) break
      const take = r2(Math.min(left, it.outstanding))
      out.push({ folio: it.folio, amount: take })
      left = r2(left - take)
    }
    return out
  }, [manual, items, picks, amt])

  const applied = r2(plan.reduce((s, p) => s + p.amount, 0))
  const unapplied = r2(amt - applied)

  const problem = (() => {
    if (amt <= 0) return "Enter the amount received."
    if (manual) {
      for (const p of plan) {
        const it = items.find((i) => i.folio === p.folio)
        if (it && p.amount > it.outstanding + 0.005)
          return `${it.invoice_number || it.folio} owes ${fmtMoney(it.outstanding)}.`
      }
      if (applied > amt + 0.005)
        return "The folios add up to more than the payment."
    }
    return null
  })()

  const toggle = (it: OpenItem) =>
    setPicks((cur) => {
      const next = { ...cur }
      if (next[it.folio] !== undefined) delete next[it.folio]
      else {
        const used = Object.values(next).reduce((s, v) => s + (Number(v) || 0), 0)
        const room = amt > 0 ? Math.max(r2(amt - used), 0) : it.outstanding
        next[it.folio] = String(r2(Math.min(it.outstanding, room)))
      }
      return next
    })

  const submit = async () => {
    setBusy(true)
    setErr(null)
    try {
      const out = await call<Result>("kamra.ledger.city_ledger_settle", {
        account: props.account,
        amount: amt,
        mode,
        reference: reference.trim() || undefined,
        allocations: manual ? JSON.stringify(plan) : undefined,
      })
      setResult(out)
      setStep("done")
      props.onPosted()
    } catch (e) {
      setErr(serverError(e))
      setStep("form")
    } finally {
      setBusy(false)
    }
  }

  const label = (folio: string) => {
    const it = items.find((i) => i.folio === folio)
    return it ? `${it.invoice_number || it.folio}${it.guest_name ? ` · ${it.guest_name}` : ""}` : folio
  }

  const footer =
    step === "form" ? (
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={props.onClose}>Cancel</Button>
        <Button disabled={!!problem || !acc} onClick={() => setStep("confirm")}>
          Review payment
        </Button>
      </div>
    ) : step === "confirm" ? (
      <div className="flex justify-end gap-2">
        <Button variant="outline" disabled={busy} onClick={() => setStep("form")}>Back</Button>
        <Button disabled={busy} onClick={() => void submit()}>
          {busy ? "Recording…" : `Confirm ${fmtMoney(amt)}`}
        </Button>
      </div>
    ) : (
      <div className="flex justify-end">
        <Button onClick={props.onClose}>Done</Button>
      </div>
    )

  return (
    <Sheet
      title="Record company payment"
      description={acc ? `${acc.company} · city ledger` : "City ledger"}
      onClose={props.onClose}
      footer={footer}
      wide
    >
      {err ? <p className="mb-3 text-sm text-rose-600">{err}</p> : null}
      {!acc ? (
        <p className="text-sm text-zinc-400">Loading account…</p>
      ) : step === "done" && result ? (
        <div className="space-y-3 text-sm">
          <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-emerald-800">
            Payment recorded. Account balance is now {fmtMoney(result.balance)}.
          </p>
          <ul className="space-y-1">
            {result.applied.map((a) => (
              <li key={a.folio} className="flex justify-between">
                <span>{label(a.folio)}</span>
                <span className="tabular-nums">{fmtMoney(a.amount)}</span>
              </li>
            ))}
          </ul>
          {result.unapplied > 0 ? (
            <p className="text-zinc-500">
              {fmtMoney(result.unapplied)} kept as unapplied credit. It settles the
              company's next city-ledger bill.
            </p>
          ) : null}
        </div>
      ) : step === "confirm" ? (
        <div className="space-y-4 text-sm">
          <p>
            Record <b>{fmtMoney(amt)}</b> from <b>{acc.company}</b> by {mode}
            {reference.trim() ? ` (ref ${reference.trim()})` : ""}.
          </p>
          <div className="rounded-lg border border-zinc-200">
            <div className="border-b border-zinc-100 px-4 py-2 text-xs uppercase text-zinc-400">
              {manual ? "Applied to the folios you picked" : "Applied oldest bill first"}
            </div>
            <ul className="divide-y divide-zinc-100">
              {plan.map((p) => (
                <li key={p.folio} className="flex justify-between px-4 py-2">
                  <span>{label(p.folio)}</span>
                  <span className="tabular-nums">{fmtMoney(p.amount)}</span>
                </li>
              ))}
              {!plan.length ? (
                <li className="px-4 py-2 text-zinc-400">No folio. All of it stays as credit.</li>
              ) : null}
            </ul>
          </div>
          {unapplied > 0 ? (
            <p className="text-amber-700">
              {fmtMoney(unapplied)} is more than the bills it pays. It stays on the
              account as unapplied credit.
            </p>
          ) : null}
          <p className="text-zinc-500">
            Balance after: {fmtMoney(r2(acc.balance - amt))}
          </p>
        </div>
      ) : (
        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Balance" value={acc.balance} />
            <Stat label="Open bills" value={acc.open_balance} />
            <Stat label="Unapplied credit" value={acc.unapplied_credit} />
            <Stat label="Overdue" value={acc.overdue} />
          </div>
          <p className="-mt-2 text-xs text-zinc-500">
            Terms: {acc.credit_days ?? 0} days from the invoice date
            {Number(acc.credit_limit || 0) > 0
              ? ` · Credit limit ${fmtMoney(Number(acc.credit_limit))}`
              : " · No credit limit"}
          </p>
          <div className="grid grid-cols-5 overflow-hidden rounded-lg border border-zinc-200 text-center text-xs">
            {([
              ["Not due", acc.not_due],
              ["1–30 overdue", acc.d1_30],
              ["31–60", acc.d31_60],
              ["61–90", acc.d61_90],
              ["90+", acc.d90p],
            ] as const).map(([k, v]) => (
              <div key={k} className="border-r border-zinc-100 px-2 py-2 last:border-r-0">
                <div className="text-zinc-400">{k}</div>
                <div className="font-medium tabular-nums">{fmtMoney(v)}</div>
              </div>
            ))}
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <label className="text-sm">
              <span className="mb-1 block text-zinc-500">Amount received</span>
              <input
                type="number"
                min="0"
                step="0.01"
                inputMode="decimal"
                className="w-full rounded-lg border border-zinc-300 px-2 py-1.5"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                autoFocus
              />
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-zinc-500">Mode</span>
              <select
                className="w-full rounded-lg border border-zinc-300 px-2 py-1.5"
                value={mode}
                onChange={(e) => setMode(e.target.value)}
              >
                {MODES.map((m) => <option key={m}>{m}</option>)}
              </select>
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-zinc-500">Reference (UTR / cheque no.)</span>
              <input
                className="w-full rounded-lg border border-zinc-300 px-2 py-1.5"
                value={reference}
                maxLength={120}
                onChange={(e) => setReference(e.target.value)}
              />
            </label>
          </div>

          <div className="flex flex-wrap gap-2 text-sm" role="radiogroup">
            <label className="flex items-center gap-1.5">
              <input type="radio" checked={!manual} onChange={() => setManual(false)} />
              Allocate oldest first
            </label>
            <label className="flex items-center gap-1.5">
              <input type="radio" checked={manual} onChange={() => setManual(true)} />
              Pick folios
            </label>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase text-zinc-400">
                <tr>
                  {manual ? <th className="py-2 pr-2" /> : null}
                  <th className="py-2 pr-3">Bill</th>
                  <th className="py-2 pr-3">Guest</th>
                  <th className="py-2 pr-3">Billed on</th>
                  <th className="py-2 pr-3">Due</th>
                  <th className="py-2 pr-3 text-right">Owed</th>
                  <th className="py-2 text-right">This payment</th>
                </tr>
              </thead>
              <tbody>
                {items.map((it) => {
                  const p = plan.find((x) => x.folio === it.folio)
                  const picked = picks[it.folio] !== undefined
                  return (
                    <tr key={it.folio} className="border-t border-zinc-100">
                      {manual ? (
                        <td className="py-2 pr-2">
                          <input type="checkbox" checked={picked} onChange={() => toggle(it)}
                            aria-label={`Pay ${it.invoice_number || it.folio}`} />
                        </td>
                      ) : null}
                      <td className="py-2 pr-3 font-mono text-xs">{it.invoice_number || it.folio}</td>
                      <td className="py-2 pr-3">{it.guest_name || "—"}</td>
                      <td className="py-2 pr-3">{it.invoice_date}</td>
                      <td className={`py-2 pr-3 ${it.days_overdue ? "text-rose-700" : ""}`}>
                        {it.due_date || "—"}
                        {it.days_overdue ? (
                          <span className="ml-1 text-xs">({it.days_overdue}d late)</span>
                        ) : null}
                      </td>
                      <td className="py-2 pr-3 text-right tabular-nums">{fmtMoney(it.outstanding)}</td>
                      <td className="py-2 text-right tabular-nums">
                        {manual && picked ? (
                          <input
                            type="number"
                            min="0"
                            step="0.01"
                            className="w-28 rounded border border-zinc-300 px-1.5 py-1 text-right"
                            value={picks[it.folio]}
                            onChange={(e) =>
                              setPicks((cur) => ({ ...cur, [it.folio]: e.target.value }))}
                          />
                        ) : p ? fmtMoney(p.amount) : "—"}
                      </td>
                    </tr>
                  )
                })}
                {!items.length ? (
                  <tr>
                    <td colSpan={manual ? 7 : 6} className="py-6 text-center text-zinc-400">
                      No open bills. A payment now is kept as credit.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>

          <p className={`text-sm ${problem ? "text-rose-600" : "text-zinc-500"}`}>
            {problem ??
              `Applies ${fmtMoney(applied)}` +
                (unapplied > 0 ? ` · ${fmtMoney(unapplied)} stays as unapplied credit` : "")}
          </p>

          {acc.payments.length ? (
            <div>
              <p className="mb-1 text-xs uppercase text-zinc-400">Recent payments</p>
              <ul className="space-y-0.5 text-sm text-zinc-600">
                {acc.payments.map((p) => (
                  <li key={p.name} className="flex justify-between">
                    <span>{p.posting_date} · {p.reference || "—"}</span>
                    <span className="tabular-nums">{fmtMoney(p.credit)}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      )}
    </Sheet>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-zinc-200 px-3 py-2">
      <div className="text-xs text-zinc-400">{label}</div>
      <div className="text-lg font-semibold tabular-nums">{fmtMoney(value)}</div>
    </div>
  )
}
