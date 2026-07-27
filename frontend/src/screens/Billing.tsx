import { useCallback, useEffect, useState } from "react"
import { MoonStar } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { call, getCurrentProperty } from "../lib/api"
import { listResource, serverError, type Row } from "../lib/resource"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import { cur, moneyLocale } from "../lib/money"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../components/ui/card"

const inr = (n: unknown) =>
  Number(n ?? 0).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })

const fmtDate = (d: unknown) =>
  d
    ? new Date(String(d) + "T00:00:00").toLocaleDateString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      })
    : "-"
const fmtWhen = (d: unknown) =>
  d
    ? new Date(String(d).replace(" ", "T").slice(0, 19)).toLocaleString(
        "en-IN",
        { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" },
      )
    : ""

interface CashSummary {
  date: string
  modes: { mode: string; txns: number; total: number }[]
  grand_total: number
}

interface AuditResult {
  audit?: string
  already_ran?: boolean
  room_charges_posted?: number
  amount_posted?: number
  no_shows_flagged?: number
  folios_opened?: number
}

export default function Billing() {
  const [folios, setFolios] = useState<Row[]>([])
  const [cash, setCash] = useState<CashSummary | null>(null)
  const [audit, setAudit] = useState<AuditResult | null>(null)
  const [auditErr, setAuditErr] = useState<string | null>(null)
  const [auditRuns, setAuditRuns] = useState<Row[]>([])
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  const load = useCallback(() => {
    listResource("Folio", {
      fields: [
        "name", "guest_name", "reservation", "status", "invoice_number",
        "grand_total", "payments_total", "balance",
      ],
      filters: [["property", "=", getCurrentProperty()]],
      orderBy: "modified desc",
    }).then(setFolios)
    call<CashSummary>("kamra.api.cash_summary", {
      property: getCurrentProperty(),
    }).then(setCash)
    listResource("Night Audit Run", {
      fields: [
        "name", "business_date", "status", "room_charges_posted",
        "amount_posted", "no_shows_flagged", "folios_opened", "creation",
      ],
      filters: [["property", "=", getCurrentProperty()]],
      orderBy: "creation desc",
      limit: 8,
    })
      .then(setAuditRuns)
      .catch(() => setAuditRuns([]))
  }, [])

  useEffect(load, [load])

  async function runAudit() {
    setBusy(true)
    setAuditErr(null)
    setAudit(null)
    try {
      const res = await call<AuditResult>("kamra.api.run_night_audit", {
        property: getCurrentProperty(),
      })
      setAudit(res)
      load()
    } catch (e) {
      setAuditErr(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Night audit</CardTitle>
            <p className="mt-0.5 text-xs text-zinc-400">
              Posts tonight's room charges for every in-house guest and flags
              no-shows. Runs automatically at 3 AM; run it manually anytime.
            </p>
          </div>
          <Button disabled={busy} onClick={runAudit}>
            <MoonStar className="size-4" aria-hidden />
            {busy ? "Running…" : "Run night audit"}
          </Button>
        </CardHeader>
        {auditErr && (
          <CardContent className="pt-0">
            <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {auditErr}
            </p>
          </CardContent>
        )}
        {audit && (
          <CardContent className="pt-0">
            {audit.already_ran ? (
              <p className="text-sm text-zinc-500">
                Already ran for today ({audit.audit}).
              </p>
            ) : (
              <p className="text-sm text-zinc-600">
                <span className="font-medium">{audit.audit}</span> - posted{" "}
                {audit.room_charges_posted} room night
                {audit.room_charges_posted === 1 ? "" : "s"} ({cur()}
                {inr(audit.amount_posted)}), opened {audit.folios_opened}{" "}
                folio{audit.folios_opened === 1 ? "" : "s"}, flagged{" "}
                {audit.no_shows_flagged} no-show
                {audit.no_shows_flagged === 1 ? "" : "s"}.
              </p>
            )}
          </CardContent>
        )}
        {auditRuns.length > 0 && (
          <CardContent className="pt-0">
            <div className="mb-1.5 text-xs font-medium uppercase tracking-wider text-zinc-400">
              Recent runs
            </div>
            <ul className="divide-y divide-zinc-100 text-sm">
              {auditRuns.map((r) => (
                <li
                  key={String(r.name)}
                  className="flex flex-wrap items-center justify-between gap-x-3 gap-y-0.5 py-1.5"
                >
                  <span className="w-28 font-medium">
                    {fmtDate(r.business_date)}
                  </span>
                  <span className="flex-1 text-zinc-500">
                    {Number(r.room_charges_posted) || 0} night
                    {Number(r.room_charges_posted) === 1 ? "" : "s"} · {cur()}
                    {inr(r.amount_posted)} · {Number(r.folios_opened) || 0} folio
                    {Number(r.folios_opened) === 1 ? "" : "s"} ·{" "}
                    {Number(r.no_shows_flagged) || 0} no-show
                    {Number(r.no_shows_flagged) === 1 ? "" : "s"}
                  </span>
                  <span className="text-xs text-zinc-400">
                    ran {fmtWhen(r.creation)}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        )}
      </Card>

      <Card>
        <CardHeader>
          <div>
            <CardTitle>Today's collections</CardTitle>
            <p className="mt-0.5 text-xs text-zinc-400">
              What the system says was collected - the drawer must match this
              at shift close.
            </p>
          </div>
          <span className="text-xl font-semibold">
            {cur()}{inr(cash?.grand_total ?? 0)}
          </span>
        </CardHeader>
        {cash && cash.modes.length > 0 && (
          <CardContent className="flex flex-wrap gap-2 pt-0">
            {cash.modes.map((m) => (
              <Badge key={m.mode} tone="zinc">
                {m.mode}: {cur()}{inr(m.total)} · {m.txns} txn
              </Badge>
            ))}
          </CardContent>
        )}
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Folios</CardTitle>
          <span className="text-xs text-zinc-400">
            Click a folio to post charges, settle and print the GST invoice
          </span>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-200 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                  <th className="py-2 pr-4">Folio</th>
                  <th className="py-2 pr-4">Guest</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Invoice</th>
                  <th className="py-2 pr-4">Total {cur()}</th>
                  <th className="py-2 pr-4">Paid {cur()}</th>
                  <th className="py-2 pr-4">Balance {cur()}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {folios.map((f) => (
                  <tr
                    key={f.name}
                    className="cursor-pointer hover:bg-zinc-50"
                    onClick={() => navigate(`/billing/${encodeURIComponent(f.name)}`)}
                  >
                    <td className="py-2.5 pr-4 font-medium">{f.name}</td>
                    <td className="py-2.5 pr-4">{String(f.guest_name ?? "-")}</td>
                    <td className="py-2.5 pr-4">
                      <Badge tone={f.status === "Open" ? "amber" : "green"}>
                        {String(f.status)}
                      </Badge>
                    </td>
                    <td className="py-2.5 pr-4 text-zinc-500">
                      {String(f.invoice_number ?? "-")}
                    </td>
                    <td className="py-2.5 pr-4">{cur()}{inr(f.grand_total)}</td>
                    <td className="py-2.5 pr-4">{cur()}{inr(f.payments_total)}</td>
                    <td className="py-2.5 pr-4 font-medium">
                      {Number(f.balance) > 0 ? (
                        <span className="text-amber-600">{cur()}{inr(f.balance)}</span>
                      ) : (
                        <span className="text-emerald-600">{cur()}0</span>
                      )}
                    </td>
                  </tr>
                ))}
                {folios.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-6 text-center text-zinc-400">
                      No folios yet - they open automatically at check-in.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
