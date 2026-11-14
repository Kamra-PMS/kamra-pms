import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { fmtMoney } from "../lib/money"
import { t as translate, useUILanguage } from "../lib/i18n"
import { Info } from "lucide-react"

const inr = fmtMoney

/** What each ledger card means, where to see it, how entries get there and
 *  how a mistake is put right, for the (i) on the card. */
const helpFor = (): Record<string, { what: string; where: string; changes: string; fix: string; drill: string; link?: [string, string] }> => ({
  Guest: {
    what: translate("What guests owe on their bills right now: every charge posted to a guest's folio (room nights, restaurant and laundry charged to the room, extras) less what they paid, advances applied at check-in, and bills moved to a company. Positive means guests owe the hotel."),
    where: translate("Billing and each guest's folio; departed guests who still owe are under Guests left owing in Receivables."),
    changes: translate("Added automatically: the night audit posts room nights, the restaurant and laundry post their bills, the desk adds charges and takes payments, check-out moves company bills to the city ledger."),
    fix: translate("Entries are never edited or deleted. Void a wrong charge on the open folio, post a discount (allowance), refund an overpayment, or cancel a closed invoice and reissue it. Each one adds a correcting entry."),
    drill: translate("Click the card: every folio with a balance, biggest first. Open a folio to see each line."),
    link: ["/billing", translate("Open Billing")],
  },
  Deposit: {
    what: translate("Advances held for guests who have not arrived yet. Negative means the hotel holds that money for them. An advance leaves this ledger when the guest checks in (it pays the stay) or when a no-show or cancellation fee uses it."),
    where: translate("Each booking's folio; the total is Advances held in Receivables, and the night audit pack lists every booking holding one."),
    changes: translate("Added when an advance or security deposit is taken on a booking; moved out at check-in, by a no-show or cancellation fee, or by a refund."),
    fix: translate("Refund the advance from the booking's folio, or cancel the payment the same day. Nothing is edited in place."),
    drill: translate("Click the card: every booking still holding an advance, with its status. A Cancelled or No Show one needs a refund or a fee."),
  },
  AR: {
    what: translate("What companies and travel agents owe (the city ledger). A company's guest bill lands here at check-out; the company's payments take it off."),
    where: translate("Receivables: each company's page shows every invoice, every payment and the bills it paid, with the running balance."),
    changes: translate("Added at check-out when a bill goes to a company, or by a direct company invoice. Reduced by a recorded company payment or a credit note."),
    fix: translate("Issue a credit note against the invoice, move a bill to another company (Transfer), or cancel and reissue the invoice. Each adds an entry; nothing is deleted."),
    drill: translate("Click the card: every bill still open on a company's account. Each company's full history is in Receivables."),
    link: ["/receivables", translate("Open Receivables")],
  },
  Package: {
    what: translate("Meant for prepaid packages held until they are used (for example a meal plan sold with the room). Kamra does not post to it yet, so it stays at 0."),
    where: translate("Nothing to see while it is 0."),
    changes: translate("No screen posts to it today; package revenue goes to the Guest ledger with the room."),
    fix: translate("Nothing to correct."),
    drill: translate("Nothing to drill into while it is 0."),
  },
})

type DetailRow = {
  folio: string; guest_name?: string | null; folio_type?: string | null
  folio_status?: string | null; invoice_number?: string | null
  reservation?: string | null; stay_status?: string | null; company?: string | null
  debit: number; credit: number; balance: number; last_date: string
}

type Ledger = {
  ledger: string
  debit: number
  credit: number
  balance: number
}

/** Guest + Deposit ledger postings per folio against each folio's balance
 *  (kamra.ledger.folio_reconciliation). */
type Recon = {
  in_balance: boolean
  ledger_net: number
  folios_net: number
  difference: number
  folios_out: number
  folios: { folio: string; folio_type: string; status: string; balance: number; ledger: number; difference: number }[]
}

export default function Ledgers() {
  useUILanguage()
  const [date, setDate] = useState("")
  const [ledgers, setLedgers] = useState<Ledger[]>([])
  const [help, setHelp] = useState<string | null>(null)
  const [open, setOpen] = useState<string | null>(null)
  const [detail, setDetail] = useState<DetailRow[] | null>(null)
  useEffect(() => {
    if (!open) { setDetail(null); return }
    setDetail(null)
    call<{ rows: DetailRow[] }>("kamra.ledger.ledger_detail", {
      property: getCurrentProperty(), ledger: open, business_date: date || undefined,
    }).then((r) => setDetail(r.rows)).catch(() => setDetail([]))
  }, [open, date])
  const [inBalance, setInBalance] = useState<boolean | null>(true)
  const [recon, setRecon] = useState<Recon | null>(null)
  const [totals, setTotals] = useState({ debit: 0, credit: 0 })
  const [journal, setJournal] = useState<
    { transaction_code: string; description: string; debit: number; credit: number; entries: number }[]
  >([])
  const [aging, setAging] = useState<Record<string, unknown>[]>([])
  const [err, setErr] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const bal = await call<{
        business_date: string
        ledgers: Ledger[]
        total_debit: number
        total_credit: number
        in_balance: boolean | null
        reconciliation: Recon | null
      }>("kamra.ledger.ledger_balances", {
        property: getCurrentProperty(),
        business_date: date || undefined,
      })
      setLedgers(bal.ledgers)
      setInBalance(bal.in_balance)
      setRecon(bal.reconciliation)
      setTotals({ debit: bal.total_debit, credit: bal.total_credit })
      if (!date) setDate(bal.business_date)
      const j = await call<{ rows: typeof journal }>(
        "kamra.ledger.journal_by_transaction_code",
        {
          property: getCurrentProperty(),
          business_date: bal.business_date,
        },
      )
      setJournal(j.rows)
      const a = await call<{ accounts: Record<string, unknown>[] }>(
        "kamra.ledger.city_ledger_aging",
        { property: getCurrentProperty() },
      )
      setAging(a.accounts)
    } catch (e) {
      setErr(serverError(e))
    }
  }, [date])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <div className="w-full space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-400">{translate("Books")}</p>
          <h1 className="text-2xl font-semibold">{translate("Ledgers")}</h1>
          <p className="text-sm text-zinc-500">{translate("Guest · Deposit · AR · Package trial balance")}</p>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="date"
            className="rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
          <Button variant="outline" onClick={() => void load()}>{translate("Refresh")}</Button>
        </div>
      </div>
      {err ? <p className="text-sm text-rose-600">{translate(err)}</p> : null}

      {/* These are subsidiary ledgers: a charge's revenue side and a
          payment's cash side live in the books the accounting export feeds,
          so debits exceed credits by what guests owe. The real check is that
          the Guest + Deposit ledgers agree with every folio's balance. */}
      <div
        className={`rounded-lg border px-4 py-2 text-sm ${
          inBalance === null
            ? "border-zinc-200 bg-zinc-50 text-zinc-700"
            : inBalance
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : "border-amber-200 bg-amber-50 text-amber-900"
        }`}
      >
        {inBalance === null ? (
          translate("Ledgers as of {v0}. Debits {v1} · credits {v2}. The check against folio balances runs for the current business date.", { v0: String(date), v1: String(inr(totals.debit)), v2: String(inr(totals.credit)) })
        ) : inBalance ? (
          translate("Ledgers agree with folios - Guest + Deposit net {v0} equals the {v1} folios carry. Debits exceed credits by what guests owe ({v2}); that is not an imbalance.", { v0: String(inr(recon?.ledger_net)), v1: String(inr(recon?.folios_net)), v2: String(inr(totals.debit - totals.credit)) })
        ) : (
          <div>
            <p className="font-medium">
              {translate("Ledger differs from folios on {v0} folio(s) by {v1}.", { v0: String(recon?.folios_out ?? 0), v1: String(inr(recon?.difference)) })}
            </p>
            <p className="mt-0.5 text-xs">{translate("A posting reached the folio but not the ledger, or the other way round.")}</p>
            <ul className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-xs">
              {(recon?.folios ?? []).map((f) => (
                <li key={f.folio}>
                  <Link className="underline" to={`/billing/${encodeURIComponent(f.folio)}`}>
                    {f.folio}
                  </Link>{" "}{translate("folio ")}{inr(f.balance)}{translate(" · ledger ")}{inr(f.ledger)}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {ledgers.map((l) => (
          <Card key={l.ledger}
            className={`cursor-pointer transition hover:border-zinc-300 ${open === l.ledger ? "ring-2 ring-emerald-600/40" : ""}`}
            onClick={() => setOpen(open === l.ledger ? null : l.ledger)}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-zinc-500">
                {l.ledger}{translate(" ledger")}</CardTitle>
              <button type="button" aria-label={translate("What is this ledger?")}
                className={`rounded-full p-1 hover:bg-zinc-100 ${help === l.ledger ? "text-emerald-700" : "text-zinc-400"}`}
                onClick={(e) => { e.stopPropagation(); setHelp(help === l.ledger ? null : l.ledger) }}>
                <Info className="size-4" />
              </button>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-semibold tabular-nums">
                {inr(l.balance)}
              </p>
              <p className="mt-1 text-xs text-zinc-400">{translate("Dr ")}{inr(l.debit)}{translate(" · Cr ")}{inr(l.credit)}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      {help && helpFor()[help] ? (
        <Card className="border-emerald-200 bg-emerald-50/40">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-base">{translate(help)}{translate(" ledger")}</CardTitle>
            <Button variant="ghost" onClick={() => setHelp(null)}>{translate("Close")}</Button>
          </CardHeader>
          <CardContent>
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              {([
                [translate("What it is"), helpFor()[help].what],
                [translate("Where to see it"), helpFor()[help].where],
                [translate("How entries get here"), helpFor()[help].changes],
                [translate("Correcting a mistake"), helpFor()[help].fix],
                [translate("Drill down"), helpFor()[help].drill],
              ] as const).map(([k, v]) => (
                <div key={k}>
                  <dt className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{k}</dt>
                  <dd className="mt-0.5 text-zinc-700">{v}</dd>
                </div>
              ))}
            </dl>
            {helpFor()[help].link ? (
              <Link className="mt-3 inline-block text-sm font-medium text-emerald-700 hover:underline"
                to={helpFor()[help].link![0]}>{helpFor()[help].link![1]}</Link>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {open ? (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">{translate(open)}{translate(" ledger")}{translate(": who makes up the balance")}</CardTitle>
            <Button variant="ghost" onClick={() => setOpen(null)}>{translate("Close")}</Button>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase text-zinc-400">
                <tr>
                  <th className="py-2 pr-3">{translate("Folio")}</th>
                  <th className="py-2 pr-3">{translate("Guest")}</th>
                  <th className="py-2 pr-3">{translate("Booking")}</th>
                  <th className="py-2 pr-3">{translate("Status")}</th>
                  <th className="py-2 pr-3">{translate("Last entry")}</th>
                  <th className="py-2 pr-3 text-right">{translate("Debit")}</th>
                  <th className="py-2 pr-3 text-right">{translate("Credit")}</th>
                  <th className="py-2 text-right">{translate("Balance")}</th>
                </tr>
              </thead>
              <tbody>
                {(detail ?? []).map((r) => (
                  <tr key={r.folio} className="border-t border-zinc-100">
                    <td className="py-2 pr-3 font-mono text-xs">
                      <Link className="hover:underline" to={`/billing/${encodeURIComponent(r.folio)}`}>
                        {r.invoice_number || r.folio}</Link>
                    </td>
                    <td className="py-2 pr-3">{r.guest_name || "-"}
                      {r.company ? <span className="block text-xs text-zinc-400">{r.company}</span> : null}</td>
                    <td className="py-2 pr-3 font-mono text-xs">{r.reservation || "-"}</td>
                    <td className="py-2 pr-3 text-xs">{translate(r.stay_status || r.folio_status || "-")}</td>
                    <td className="py-2 pr-3 text-xs text-zinc-500">{r.last_date}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{inr(r.debit)}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{inr(r.credit)}</td>
                    <td className="py-2 text-right font-medium tabular-nums">{inr(r.balance)}</td>
                  </tr>
                ))}
                {detail && !detail.length ? (
                  <tr><td colSpan={8} className="py-6 text-center text-zinc-400">{translate("Nothing on this ledger.")}</td></tr>
                ) : null}
                {!detail ? (
                  <tr><td colSpan={8} className="py-6 text-center text-zinc-400">{translate("Loading…")}</td></tr>
                ) : null}
              </tbody>
            </table>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{translate("Journal by transaction code")}</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-zinc-400">
              <tr>
                <th className="py-2 pr-3">{translate("Code")}</th>
                <th className="py-2 pr-3">{translate("Description")}</th>
                <th className="py-2 pr-3">{translate("Debit")}</th>
                <th className="py-2 pr-3">{translate("Credit")}</th>
                <th className="py-2">{translate("Entries")}</th>
              </tr>
            </thead>
            <tbody>
              {journal.map((r) => (
                <tr key={r.transaction_code} className="border-t border-zinc-100">
                  <td className="py-2 pr-3 font-mono text-xs">
                    {r.transaction_code}
                  </td>
                  <td className="py-2 pr-3">{r.description}</td>
                  <td className="py-2 pr-3 tabular-nums">{inr(r.debit)}</td>
                  <td className="py-2 pr-3 tabular-nums">{inr(r.credit)}</td>
                  <td className="py-2">{r.entries}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{translate("City ledger aging")}</CardTitle>
          <span className="text-xs text-zinc-400">{translate("By due date - invoice date + the company's credit days")}</span>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-zinc-400">
              <tr>
                <th className="py-2 pr-3">{translate("Company")}</th>
                <th className="py-2 pr-3">{translate("Terms")}</th>
                <th className="py-2 pr-3">{translate("Balance")}</th>
                <th className="py-2 pr-3">{translate("Not due")}</th>
                <th className="py-2 pr-3">{translate("1 to 30")}</th>
                <th className="py-2 pr-3">{translate("31 to 60")}</th>
                <th className="py-2 pr-3">{translate("61 to 90")}</th>
                <th className="py-2 pr-3">90+</th>
                <th className="py-2 pr-3">{translate("Overdue")}</th>
                <th className="py-2 pr-3">{translate("Credit")}</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {aging.map((a) => {
                const overdue = Number(a.overdue || 0)
                const limit = Number(a.credit_limit || 0)
                const over = limit > 0 && Number(a.balance || 0) > limit
                return (
                  <tr key={String(a.name)} className="border-t border-zinc-100">
                    <td className="py-2 pr-3">
                      {String(a.company)}
                      {over ? (
                        <span className="ml-2 rounded bg-rose-50 px-1.5 py-0.5 text-[10px] font-medium text-rose-700">{translate("Over limit")}</span>
                      ) : null}
                    </td>
                    <td className="py-2 pr-3 text-xs text-zinc-500">
                      {Number(a.credit_days ?? 0)}{translate(" days")}</td>
                    <td className="py-2 pr-3 tabular-nums">{inr(a.balance)}</td>
                    <td className="py-2 pr-3 tabular-nums">{inr(a.not_due)}</td>
                    <td className="py-2 pr-3 tabular-nums">{inr(a.d1_30)}</td>
                    <td className="py-2 pr-3 tabular-nums">{inr(a.d31_60)}</td>
                    <td className="py-2 pr-3 tabular-nums">{inr(a.d61_90)}</td>
                    <td className="py-2 pr-3 tabular-nums">{inr(a.d90p)}</td>
                    <td
                      className={`py-2 pr-3 tabular-nums ${overdue ? "font-medium text-rose-700" : ""}`}
                    >
                      {overdue ? inr(overdue) : "-"}
                    </td>
                    <td className="py-2 pr-3 tabular-nums">
                      {Number(a.unapplied_credit || 0) ? inr(a.unapplied_credit) : "-"}
                    </td>
                    <td className="py-2 text-right">
                      {/* bills, payments, statement: one place, the company's account */}
                      <Link to={`/receivables/${encodeURIComponent(String(a.name))}`}
                        className="text-sm font-medium text-emerald-700 hover:underline">
                        {translate("Open account")}
                      </Link>
                    </td>
                  </tr>
                )
              })}
              {!aging.length ? (
                <tr>
                  <td colSpan={11} className="py-6 text-center text-zinc-400">{translate("No city ledger accounts yet.")}</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}
