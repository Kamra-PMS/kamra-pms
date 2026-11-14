
import { useCallback, useEffect, useState } from "react"
import { MoonStar } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { call, getCurrentProperty } from "../lib/api"
import { listResource, type Row } from "../lib/resource"
import { auditHistory, type RunRow } from "../lib/eod"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import { cur, fmtMoney, moneyLocale } from "../lib/money"
import { DataTable } from "../components/ui/data-table"
import { useT, uiDateLocale } from "../lib/i18n"
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
    ? new Date(String(d) + "T00:00:00").toLocaleDateString(uiDateLocale(moneyLocale()), {
        day: "2-digit",
        month: "short",
        year: "numeric",
      })
    : "-"
const fmtWhen = (d: unknown) =>
  d
    ? new Date(String(d).replace(" ", "T").slice(0, 19)).toLocaleString(
        uiDateLocale(moneyLocale()),
        { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" },
      )
    : ""

type GuestOwing = {
  folio: string; guest_name: string; balance: number; reservation: string
  status: string; check_in_date: string; check_out_date: string
}

export default function Billing() {
  const { t } = useT()
  const [folios, setFolios] = useState<Row[]>([])
  const [auditRuns, setAuditRuns] = useState<RunRow[]>([])
  const [owing, setOwing] = useState<GuestOwing[]>([])
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
    // departed guests who still owe: the desk chases these, not credit control
    call<{ summary?: { guests_owing: GuestOwing[] } }>("kamra.receivables.ar_accounts", {
      property: getCurrentProperty(),
    }).then((r) => setOwing(r.summary?.guests_owing ?? [])).catch(() => setOwing([]))
    auditHistory(getCurrentProperty(), 8)
      .then(setAuditRuns)
      .catch(() => setAuditRuns([]))
  }, [])

  useEffect(load, [load])

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div>
            <CardTitle>{t("Night Audit")}</CardTitle>
            <p className="mt-0.5 text-xs text-zinc-400">
              {t("Clear what is open, post room and tax, roll the business date and print the audit pack. Runs automatically every night at the time set in Settings.")}
            </p>
          </div>
          <Button onClick={() => navigate(`/end-of-day/${encodeURIComponent(getCurrentProperty())}`)}>
            <MoonStar className="size-4" aria-hidden />
            {t("Open Night Audit")}
          </Button>
        </CardHeader>
        {auditRuns.length > 0 && (
          <CardContent className="pt-0">
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-xs font-medium uppercase tracking-wider text-zinc-400">
                {t("Recent runs")}
              </span>
              <button type="button" className="text-xs text-brand-700 hover:underline" onClick={() => navigate("/end-of-day")}>
                {t("All audits")}
              </button>
            </div>
            <ul className="divide-y divide-zinc-100 text-sm">
              {auditRuns.map((r) => (
                <li
                  key={r.name}
                  className="flex flex-wrap items-center justify-between gap-x-3 gap-y-0.5 py-1.5"
                >
                  <span className="w-28 font-medium">
                    {fmtDate(r.business_date)}
                  </span>
                  <span className="flex-1 text-zinc-500">
                    {t("{n} night{s} · {amount} · {folios} folio{s2} · {noShows} no-show{s3}", {
                      n: Number(r.room_charges_posted) || 0,
                      s: Number(r.room_charges_posted) === 1 ? "" : "s",
                      amount: `${cur()}${inr(r.amount_posted)}`,
                      folios: Number(r.folios_opened) || 0,
                      s2: Number(r.folios_opened) === 1 ? "" : "s",
                      noShows: Number(r.no_shows_flagged) || 0,
                      s3: Number(r.no_shows_flagged) === 1 ? "" : "s",
                    })}
                    {Number(r.late_arrivals_held) > 0 &&
                      ` · ${t("{n} late arrival(s) held", { n: Number(r.late_arrivals_held) })}`}
                    {Number(r.exceptions) > 0 &&
                      ` · ${t("{n} exception(s)", { n: Number(r.exceptions) })}`}
                  </span>
                  <span className="text-xs text-zinc-400">
                    {t("ran {when}", { when: fmtWhen(r.creation) })}
                  </span>
                  {r.has_pack ? (
                    <button
                      type="button"
                      className="text-xs text-brand-700 hover:underline"
                      onClick={() => navigate(`/end-of-day/pack/${encodeURIComponent(r.name)}`)}
                    >
                      {t("View audit pack")}
                    </button>
                  ) : (
                    <span className="text-xs text-zinc-300">{t("No pack")}</span>
                  )}
                </li>
              ))}
            </ul>
          </CardContent>
        )}
      </Card>

      <Card>
        <CardHeader>
          <div>
            <CardTitle>{t("Cashier till")}</CardTitle>
            <p className="mt-0.5 text-xs text-zinc-400">
              {t("Open your till, reconcile cash and close the session under Finance → Cashier. Collections live there now.")}
            </p>
          </div>
          <Button variant="outline" onClick={() => navigate("/cashier")}>
            {t("Open My Till")}
          </Button>
        </CardHeader>
      </Card>

      {owing.length ? (
        <Card>
          <CardHeader>
            <div>
              <CardTitle>{t("Guests left owing")}</CardTitle>
              <p className="mt-0.5 text-xs text-zinc-400">{t("Departed stays with a balance. Open the folio to take the payment or move it to a company.")}</p>
            </div>
          </CardHeader>
          <CardContent>
            <DataTable<GuestOwing>
              id="billing.guests_owing" exportName="guests-left-owing" rows={owing} rowKey={(g) => g.folio}
              onRowClick={(g) => navigate(`/billing/${encodeURIComponent(g.folio)}`)}
              columns={[
                { key: "guest_name", label: t("Guest"), render: (g) => <span className="font-medium">{g.guest_name}</span> },
                { key: "reservation", label: t("Booking"), render: (g) => <span className="font-mono text-xs">{g.reservation}</span> },
                { key: "check_in_date", label: t("Stay"), render: (g) => <span className="text-xs text-zinc-500">{g.check_in_date} → {g.check_out_date}</span> },
                { key: "status", label: t("Status"), render: (g) => <span className="text-xs">{t(g.status)}</span> },
                { key: "balance", label: t("Owed"), align: "right", render: (g) => <span className="font-medium">{fmtMoney(g.balance)}</span> },
              ]}
            />
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>{t("Folios")}</CardTitle>
          <span className="text-xs text-zinc-400">
            {t("Click a folio to post charges, settle and print the GST invoice")}
          </span>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-200 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                  <th className="py-2 pr-4">{t("Folio")}</th>
                  <th className="py-2 pr-4">{t("Guest")}</th>
                  <th className="py-2 pr-4">{t("Status")}</th>
                  <th className="py-2 pr-4">{t("Invoice")}</th>
                  <th className="py-2 pr-4">{t("Total {cur}", { cur: cur() })}</th>
                  <th className="py-2 pr-4">{t("Paid {cur}", { cur: cur() })}</th>
                  <th className="py-2 pr-4">{t("Balance {cur}", { cur: cur() })}</th>
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
                        {t(String(f.status))}
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
                      {t("No folios yet - they open automatically at check-in.")}
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
