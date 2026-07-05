import { useCallback, useEffect, useState } from "react"
import { MoonStar } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { call, getCurrentProperty } from "../lib/api"
import { listResource, type Row } from "../lib/resource"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../components/ui/card"

const inr = (n: unknown) =>
  Number(n ?? 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })

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
  }, [])

  useEffect(load, [load])

  async function runAudit() {
    setBusy(true)
    try {
      const res = await call<AuditResult>("kamra.api.run_night_audit", {
        property: getCurrentProperty(),
      })
      setAudit(res)
      load()
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
        {audit && (
          <CardContent className="pt-0">
            {audit.already_ran ? (
              <p className="text-sm text-zinc-500">
                Already ran for today ({audit.audit}).
              </p>
            ) : (
              <p className="text-sm text-zinc-600">
                <span className="font-medium">{audit.audit}</span> — posted{" "}
                {audit.room_charges_posted} room night
                {audit.room_charges_posted === 1 ? "" : "s"} (₹
                {inr(audit.amount_posted)}), opened {audit.folios_opened}{" "}
                folio{audit.folios_opened === 1 ? "" : "s"}, flagged{" "}
                {audit.no_shows_flagged} no-show
                {audit.no_shows_flagged === 1 ? "" : "s"}.
              </p>
            )}
          </CardContent>
        )}
      </Card>

      <Card>
        <CardHeader>
          <div>
            <CardTitle>Today's collections</CardTitle>
            <p className="mt-0.5 text-xs text-zinc-400">
              What the system says was collected — the drawer must match this
              at shift close.
            </p>
          </div>
          <span className="text-xl font-semibold">
            ₹{inr(cash?.grand_total ?? 0)}
          </span>
        </CardHeader>
        {cash && cash.modes.length > 0 && (
          <CardContent className="flex flex-wrap gap-2 pt-0">
            {cash.modes.map((m) => (
              <Badge key={m.mode} tone="zinc">
                {m.mode}: ₹{inr(m.total)} · {m.txns} txn
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
                  <th className="py-2 pr-4">Total ₹</th>
                  <th className="py-2 pr-4">Paid ₹</th>
                  <th className="py-2 pr-4">Balance ₹</th>
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
                    <td className="py-2.5 pr-4">{String(f.guest_name ?? "—")}</td>
                    <td className="py-2.5 pr-4">
                      <Badge tone={f.status === "Open" ? "amber" : "green"}>
                        {String(f.status)}
                      </Badge>
                    </td>
                    <td className="py-2.5 pr-4 text-zinc-500">
                      {String(f.invoice_number ?? "—")}
                    </td>
                    <td className="py-2.5 pr-4">₹{inr(f.grand_total)}</td>
                    <td className="py-2.5 pr-4">₹{inr(f.payments_total)}</td>
                    <td className="py-2.5 pr-4 font-medium">
                      {Number(f.balance) > 0 ? (
                        <span className="text-amber-600">₹{inr(f.balance)}</span>
                      ) : (
                        <span className="text-emerald-600">₹0</span>
                      )}
                    </td>
                  </tr>
                ))}
                {folios.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-6 text-center text-zinc-400">
                      No folios yet — they open automatically at check-in.
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
