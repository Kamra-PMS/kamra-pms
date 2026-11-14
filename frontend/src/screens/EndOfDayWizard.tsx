/*  Night Audit - <property> - <business date>.

    One page: what needs the auditor first (blocking checks, then warnings),
    each with its list and the buttons that clear it; information-only and
    clear checks folded away; notes; and one Close button. The close runs
    the same audit the scheduler runs, and the saved audit pack opens on the
    same page. Acknowledgements live on the draft Night Audit Run, so
    reopening keeps them. */

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react"
import {
  ArrowLeft,
  CheckCircle2,
  Loader2,
  MoonStar,
  Search,
  Sparkles,
  TriangleAlert,
} from "lucide-react"
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom"
import { call } from "../lib/api"
import CheckOutDialog from "../components/CheckOutDialog"
import CheckInDialog from "../components/CheckInDialog"
import NoShowDialog from "../components/NoShowDialog"
import {
  eodAcknowledge,
  eodProgress,
  eodSession,
  recoverStuckBusinessDate,
  runNightAudit,
  type Check,
  type CheckItem,
  type EodState,
} from "../lib/eod"
import { serverError } from "../lib/resource"
import { useCashierAuth } from "../lib/cashierAuth"
import { CHECK_FIXES } from "../lib/eodFixes"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import { Card } from "../components/ui/card"
import { cur, moneyLocale } from "../lib/money"
import { useT, t as translate } from "../lib/i18n"
import { cn } from "../lib/utils"
import { AuditPackView, sessionCols, DataTable, fmtDay } from "./AuditPack"


const money = (n: unknown) =>
  n === null || n === undefined || n === ""
    ? "-"
    : Number(n).toLocaleString(moneyLocale(), { minimumFractionDigits: 2, maximumFractionDigits: 2 })

interface Column {
  key: string
  label: string
  kind?: "money" | "num" | "date"
  render?: (row: CheckItem) => ReactNode
}

/* --- a searchable, sortable list -------------------------------------------- */

function StepTable({
  cols,
  rows,
  actions,
  empty,
}: {
  cols: Column[]
  rows: CheckItem[]
  actions?: (row: CheckItem) => ReactNode
  empty?: string
}) {
  const { t } = useT()
  const [q, setQ] = useState("")
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 } | null>(null)
  const shown = useMemo(() => {
    const s = q.trim().toLowerCase()
    let out = s
      ? rows.filter((r) => Object.values(r).some((v) => String(v ?? "").toLowerCase().includes(s)))
      : rows
    if (sort) {
      out = [...out].sort((a, b) => {
        const x = a[sort.key] as never
        const y = b[sort.key] as never
        if (typeof x === "number" && typeof y === "number") return (x - y) * sort.dir
        return String(x ?? "").localeCompare(String(y ?? ""), undefined, { numeric: true }) * sort.dir
      })
    }
    return out
  }, [rows, q, sort])
  const cell = (c: Column, r: CheckItem) => {
    if (c.render) return c.render(r)
    const v = r[c.key]
    if (v === null || v === undefined || v === "") return "-"
    if (c.kind === "money") return money(v)
    if (c.kind === "date") return fmtDay(v)
    return String(v)
  }
  const right = (c: Column) => (c.kind === "money" || c.kind === "num" ? "text-end tabular-nums" : "")
  return (
    <div className="rounded-lg border border-zinc-200">
      <div className="flex items-center justify-between gap-2 border-b border-zinc-100 px-3 py-2">
        <label className="relative">
          <Search className="pointer-events-none absolute start-2 top-2 size-4 text-zinc-400" aria-hidden />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t("Search")}
            className="w-56 rounded-lg border border-zinc-300 bg-white py-1.5 ps-8 pe-2 text-sm"
          />
        </label>
        <span className="text-xs text-zinc-400">{t("{n} of {m}", { n: shown.length, m: rows.length })}</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-200 text-[11px] font-medium uppercase tracking-wider text-zinc-500">
              {cols.map((c) => (
                <th key={c.key} className={cn("px-2 py-2 text-start", right(c))}>
                  <button
                    type="button"
                    className="uppercase hover:text-zinc-800"
                    onClick={() =>
                      setSort((s) => (s?.key === c.key ? { key: c.key, dir: s.dir === 1 ? -1 : 1 } : { key: c.key, dir: 1 }))
                    }
                  >
                    {t(c.label)}
                    {sort?.key === c.key ? (sort.dir === 1 ? " ↑" : " ↓") : ""}
                  </button>
                </th>
              ))}
              {actions && <th className="px-2 py-2" />}
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {shown.map((r, i) => (
              <tr key={`${String(r.order ?? r.session ?? r.folio ?? r.reservation ?? r.room_id ?? r.account ?? "")}-${i}`}>
                {cols.map((c) => (
                  <td key={c.key} className={cn("px-2 py-1.5 align-top", right(c))}>{cell(c, r)}</td>
                ))}
                {actions && <td className="whitespace-nowrap px-2 py-1.5 text-end">{actions(r)}</td>}
              </tr>
            ))}
            {shown.length === 0 && (
              <tr>
                <td colSpan={cols.length + (actions ? 1 : 0)} className="px-2 py-5 text-center text-zinc-400">
                  {t(empty ?? "Nothing here.")}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/* --- columns ---------------------------------------------------------------- */

const resLink = (r: CheckItem) =>
  r.reservation ? (
    <Link className="font-medium text-brand-700 hover:underline" to={`/reservations?q=${encodeURIComponent(String(r.reservation))}`}>
      {String(r.reservation)}
    </Link>
  ) : (
    "-"
  )
const folioLink = (r: CheckItem) =>
  r.folio ? (
    <Link className="text-brand-700 hover:underline" to={`/billing/${encodeURIComponent(String(r.folio))}`}>
      {String(r.folio)}
    </Link>
  ) : (
    "-"
  )

const STAY_COLS: Column[] = [
  { key: "reservation", label: "Confirmation", render: resLink },
  { key: "guest_name", label: "Guest" },
  { key: "check_in_date", label: "Arrival", kind: "date" },
  { key: "check_out_date", label: "Departure", kind: "date" },
  { key: "nights", label: "Nights", kind: "num" },
  { key: "room_type", label: "Room type" },
  { key: "rate_plan", label: "Rate plan" },
  { key: "rate", label: "Rate", kind: "money" },
  { key: "room", label: "Room" },
  { key: "balance", label: "Balance", kind: "money" },
  { key: "adults", label: "Ad/Ch", render: (r) => `${r.adults ?? 0}/${r.children ?? 0}` },
  { key: "source", label: "Source" },
]

/* Arrivals carry two more columns (ETA, no-show policy) and two buttons,
   so the stay's detail folds into fewer columns - the full twelve overflowed
   the card at laptop widths and cut off the policy the step is about. */
const ARRIVAL_COLS: Column[] = [
  { key: "reservation", label: "Confirmation", render: resLink },
  {
    key: "guest_name",
    label: "Guest",
    render: (r) => (
      <div className="min-w-32">
        <div>{String(r.guest_name ?? "-")}</div>
        <div className="text-xs text-zinc-500">
          {[r.room_type, r.room, `${r.adults ?? 0}/${r.children ?? 0}`, r.source]
            .filter((v) => v !== null && v !== undefined && v !== "")
            .join(" · ")}
        </div>
      </div>
    ),
  },
  {
    key: "check_in_date",
    label: "Arrival",
    kind: "date",
    render: (r) => (
      <div className="whitespace-nowrap">
        <div>{r.check_in_date ? fmtDay(r.check_in_date) : "-"}</div>
        <div className="text-xs text-zinc-500">
          {Number(r.nights) === 1 ? translate("1 night") : translate("{v0} nights", { v0: String(r.nights ?? 0) })}
        </div>
      </div>
    ),
  },
  {
    key: "rate",
    label: "Rate",
    kind: "money",
    render: (r) => (
      <div>
        <div>{r.rate === null || r.rate === undefined || r.rate === "" ? "-" : money(r.rate)}</div>
        {r.rate_plan ? <div className="text-xs text-zinc-500">{String(r.rate_plan)}</div> : null}
      </div>
    ),
  },
]

const FOLIO_COLS: Column[] = [
  { key: "folio", label: "Folio", render: folioLink },
  { key: "folio_type", label: "Type" },
  { key: "reservation", label: "Confirmation", render: resLink },
  { key: "guest_name", label: "Guest" },
  { key: "room", label: "Room" },
  { key: "check_out_date", label: "Departure", kind: "date" },
  { key: "balance", label: "Balance", kind: "money" },
]

const POS_COLS: Column[] = [
  { key: "outlet", label: "Outlet" },
  { key: "bill_no", label: "Bill no" },
  { key: "table_no", label: "Table" },
  { key: "room", label: "Room" },
  { key: "guest_name", label: "Guest" },
  { key: "state", label: "State" },
  { key: "amount", label: "Amount", kind: "money" },
]

const POSTING_COLS: Column[] = [
  { key: "outlet", label: "Outlet" },
  { key: "bill_no", label: "Bill no" },
  { key: "room", label: "Room" },
  { key: "bill_room", label: "Bill's room" },
  { key: "guest_name", label: "Guest" },
  { key: "folio", label: "Folio", render: folioLink },
  { key: "total", label: "Amount", kind: "money" },
]

/* --- small pieces ----------------------------------------------------------- */

function Message({ tone, children }: { tone: "info" | "warn" | "block" | "ok"; children: ReactNode }) {
  const cls = {
    info: "border-zinc-200 bg-zinc-50 text-zinc-700",
    ok: "border-emerald-200 bg-emerald-50 text-emerald-800",
    warn: "border-amber-200 bg-amber-50 text-amber-900",
    block: "border-rose-200 bg-rose-50 text-rose-800",
  }[tone]
  return <div className={cn("rounded-lg border px-3 py-2 text-sm", cls)}>{children}</div>
}

/** What to do about a check: usual fixes, ask the agent, or override. */
function FixHelp({ check, date }: { check: Check; date: string }) {
  const { t } = useT()
  const navigate = useNavigate()
  const fix = CHECK_FIXES[check.key]
  if (!fix) return null
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-3 text-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{t("How to clear this")}</p>
      <p className="mt-1 text-zinc-600">{t(fix.why)}</p>
      <ol className="mt-2 list-decimal space-y-1 ps-5 text-zinc-700">
        {fix.steps.map((st) => (
          <li key={st.text}>
            {t(st.text)}
            {st.to && (
              <Link to={st.to} className="ms-2 text-brand-700 hover:underline">
                {t(st.cta ?? "Open")} →
              </Link>
            )}
          </li>
        ))}
      </ol>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button
          variant="outline"
          className="h-8 px-3 text-xs"
          onClick={() => navigate("/assistant", { state: { prompt: translate(fix.ask(check.count, date)) } })}
        >
          <Sparkles className="me-1.5 size-3.5" aria-hidden />
          {t("Ask Kamra Agent to help")}
        </Button>
        <span className="text-xs text-zinc-400">{t("It opens the agent with this check described. You approve what it changes.")}</span>
      </div>
      <p className="mt-3 text-xs text-zinc-500">
        <span className="font-medium text-zinc-600">{t("If you override:")}</span> {t(fix.override)}
      </p>
    </div>
  )
}

function CheckBlock({
  check,
  children,
  state,
  onAck,
}: {
  check?: Check
  children?: ReactNode
  state: EodState
  onAck: (key: string, reason: string) => Promise<void>
}) {
  const { t } = useT()
  const [reason, setReason] = useState("")
  const [busy, setBusy] = useState(false)
  if (!check) return null
  const ack = state.acknowledgements.find((a) => a.key === check.key)
  const blocking = check.severity === "block" && check.count > 0
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-zinc-800">
          {t(check.title)}{" "}
          <Badge tone={check.count === 0 ? "green" : check.severity === "block" ? "rose" : check.severity === "warn" ? "amber" : "zinc"}>
            {check.count}
          </Badge>
        </h3>
        {check.resolve && check.count > 0 && (
          <Link to={check.resolve} className="text-xs text-brand-700 hover:underline">
            {t("Resolve")} →
          </Link>
        )}
      </div>
      {check.count > 0 && <p className="text-xs text-zinc-500">{t(check.action)}</p>}
      {check.count > 0 && !state.ran && check.severity !== "info" && (
        <FixHelp check={check} date={state.business_date} />
      )}
      {children}
      {blocking && !ack && !state.ran && (
        <div className="rounded-lg border border-rose-200 bg-rose-50/60 p-3">
          <p className="text-xs text-rose-800">
            {t("This blocks the audit. Fix it above, or override it with a reason - your name and the time are recorded on the audit.")}
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            <input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder={t("Reason")}
              className="min-w-0 flex-1 rounded-lg border border-zinc-300 bg-white px-2 py-1.5 text-sm"
            />
            <Button
              variant="outline"
              disabled={busy || reason.trim().length < 3}
              onClick={async () => {
                setBusy(true)
                try {
                  await onAck(check.key, reason.trim())
                  setReason("")
                } finally {
                  setBusy(false)
                }
              }}
            >
              {t("Override with reason")}
            </Button>
          </div>
        </div>
      )}
      {ack && (
        <p className="text-xs text-zinc-500">
          {t("Acknowledged by {who} at {when}: {why}", {
            who: ack.by_name || ack.by,
            when: String(ack.at).slice(0, 16),
            why: ack.note,
          })}
        </p>
      )}
    </div>
  )
}

/* --- the page ---------------------------------------------------------------- */

const SEVERITY_ORDER: Record<string, number> = { block: 0, warn: 1, info: 2 }

/** Counted cash as typed: a comma decimal works, anything else is NaN. */
const cash = (v?: string) => (v && v.trim() ? Number(v.trim().replace(/\s/g, "").replace(",", ".")) : NaN)

export default function EndOfDayWizard() {
  const { t } = useT()
  const navigate = useNavigate()
  const { property: rawProperty = "" } = useParams()
  const property = decodeURIComponent(rawProperty)
  const [params, setParams] = useSearchParams()
  const audit = params.get("audit")
  const { withPin } = useCashierAuth()

  const [state, setState] = useState<EodState | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [notes, setNotes] = useState("")
  const [counted, setCounted] = useState<Record<string, string>>({})
  const [runOut, setRunOut] = useState<Record<string, unknown> | null>(null)

  const load = useCallback(async () => {
    try {
      const s = await eodSession(property, audit)
      setState(s)
      setNotes(s.notes ?? "")
      setErr(null)
    } catch (e) {
      setErr(serverError(e))
    }
  }, [property, audit])
  useEffect(() => {
    void load()
  }, [load])

  // check-out opens the guided check-out sheet (settle, credit, invoice)
  const [checkingOut, setCheckingOut] = useState<string | null>(null)
  const [checkingIn, setCheckingIn] = useState<string | null>(null)
  const [markingNoShow, setMarkingNoShow] = useState<string | null>(null)

  async function act(label: string, fn: () => Promise<unknown>) {
    setBusy(label)
    setErr(null)
    try {
      await fn()
    } catch (e) {
      setErr(serverError(e))
    } finally {
      // reload either way: a loop that stopped half way still changed things
      await load()
      setBusy(null)
    }
  }

  const ack = (key: string, reason: string) =>
    act("ack", () => eodAcknowledge(property, key, reason))

  const saveNotes = () => {
    if (!state || state.ran || notes === (state.notes ?? "")) return
    void eodProgress(property, { notes }).catch((e) => setErr(serverError(e)))
  }

  async function runAudit() {
    setBusy("run")
    setErr(null)
    try {
      await eodProgress(property, { notes })
      const out = await runNightAudit(property)
      setRunOut(out as Record<string, unknown>)
      if (out.audit) {
        setParams({ audit: out.audit })
        setState(await eodSession(property, out.audit))
      }
    } catch (e) {
      setErr(serverError(e))
      await load()
    } finally {
      setBusy(null)
    }
  }

  if (err && !state)
    return <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{translate(err)}</p>
  if (!state) return <p className="text-sm text-zinc-400">{t("Preparing the night audit…")}</p>

  const acked = new Set(state.acknowledgements.map((a) => a.key))
  const open = (c: Check) => c.count > 0 && c.severity !== "info" && !acked.has(c.key)
  const blockers = state.checks.filter((c) => c.severity === "block" && c.count > 0 && !acked.has(c.key))
  const needs = state.checks
    .filter(open)
    .sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 3) - (SEVERITY_ORDER[b.severity] ?? 3))
  const counted_ = state.checks.filter((c) => c.severity !== "info")
  const clearN = counted_.length - needs.length
  const clear = counted_.filter((c) => c.count === 0)
  const fyi = state.checks.filter((c) => c.count > 0 && (c.severity === "info" || acked.has(c.key)))
  const ahead = state.business_date > state.server_date
  const canClose = !state.ran && !ahead && !state.stuck_date && blockers.length === 0

  /* each check's list and its buttons, under the check's heading */
  const body = (c: Check): ReactNode => {
    const items = c.items ?? []
    switch (c.key) {
      case "arrivals_pending":
        return (
          <StepTable
            cols={[
              ...ARRIVAL_COLS,
              { key: "eta", label: "ETA" },
              {
                key: "policy",
                label: "No-show policy",
                render: (r) => (
                  <span className={r.outcome === "no_show" ? "text-rose-700" : "text-amber-700"}>
                    {t(String(r.policy))}
                    {Number(r.fee_amount) > 0 ? ` · ${cur()}${money(r.fee_amount)}` : ""}
                  </span>
                ),
              },
            ]}
            rows={items}
            empty={translate("Every arrival is checked in.")}
            actions={(r) =>
              state.ran ? null : (
                <div className="flex flex-col items-stretch gap-1">
                  <Button variant="outline" className="h-7 px-2 text-xs"
                    onClick={() => setCheckingIn(String(r.reservation))}>
                    {t("Check in")}
                  </Button>
                  <Button variant="ghost" className="h-7 px-2 text-xs text-rose-700" disabled={!!busy}
                    onClick={() => setMarkingNoShow(String(r.reservation))}>
                    {t("Mark no-show")}
                  </Button>
                </div>
              )
            }
          />
        )
      case "departures_due": {
        const zero = items.filter((r) => Math.abs(Number(r.balance ?? 0)) < 0.01)
        return (
          <>
            {!state.ran && zero.length > 0 && (
              <div className="flex justify-end">
                <Button variant="outline" disabled={!!busy}
                  onClick={() =>
                    act("bulk", () =>
                      withPin(async (pin) => {
                        for (const r of zero)
                          await call("kamra.ledger.quick_checkout", { reservation: r.reservation, pin })
                      }),
                    )
                  }>
                  {t("Quick check out {n} zero-balance departures", { n: zero.length })}
                </Button>
              </div>
            )}
            <StepTable
              cols={STAY_COLS}
              rows={items}
              empty={translate("Every departure is checked out.")}
              actions={(r) =>
                state.ran ? null : (
                  <div className="flex justify-end gap-1">
                    <Button variant="outline" className="h-7 px-2 text-xs" disabled={!!busy}
                      onClick={() => setCheckingOut(String(r.reservation))}>
                      {t("Check out")}
                    </Button>
                    <Button variant="ghost" className="h-7 px-2 text-xs"
                      onClick={() => navigate(`/reservations?q=${encodeURIComponent(String(r.reservation))}`)}>
                      {t("Extend stay")}
                    </Button>
                  </div>
                )
              }
            />
          </>
        )
      }
      case "high_balance":
        return (
          <>
            {c.enabled && (
              <p className="text-xs text-zinc-500">{t("Threshold {cur}{n}", { cur: cur(), n: money(c.threshold) })}</p>
            )}
            <StepTable cols={FOLIO_COLS} rows={items} empty={translate("No in-house folio is over the threshold.")} />
          </>
        )
      case "departed_balances":
        return <StepTable cols={FOLIO_COLS} rows={items} empty={translate("No balances on departed stays.")} />
      case "credit_limit":
        return (
          <StepTable
            cols={[
              { key: "company", label: "Company" },
              { key: "credit_limit", label: "Credit limit", kind: "money" },
              { key: "ar_balance", label: "AR balance", kind: "money" },
              { key: "in_house", label: "In-house folios", kind: "money" },
              { key: "exposure", label: "Exposure", kind: "money" },
              { key: "over_by", label: "Over by", kind: "money" },
            ]}
            rows={items}
            empty={translate("No company is over its credit limit.")}
          />
        )
      case "overdue_ar":
        return (
          <StepTable
            cols={[
              { key: "company", label: "Company" },
              { key: "credit_days", label: "Terms (days)" },
              { key: "oldest_due_date", label: "Oldest due", kind: "date" },
              { key: "d1_30", label: "1-30 days", kind: "money" },
              { key: "d31_60", label: "31-60", kind: "money" },
              { key: "d61_90", label: "61-90", kind: "money" },
              { key: "d90p", label: "90+", kind: "money" },
              { key: "overdue", label: "Overdue", kind: "money" },
            ]}
            rows={items}
            empty={translate("No company has an overdue bill.")}
          />
        )
      case "open_pos_bills":
        return <StepTable cols={POS_COLS} rows={items} empty={translate("Every outlet bill is settled.")} />
      case "pos_room_postings":
        return (
          <>
            {(c.mismatches ?? 0) > 0 && (
              <Message tone="warn">{t("{n} bill(s) were taken for a different room than the folio they posted to.", { n: c.mismatches! })}</Message>
            )}
            <StepTable
              cols={[
                ...POSTING_COLS,
                {
                  key: "room_mismatch",
                  label: "Check",
                  render: (r) => (r.room_mismatch ? <Badge tone="rose">{t("Wrong room?")}</Badge> : ""),
                },
              ]}
              rows={items}
              empty={translate("No outlet bills were posted to rooms today.")}
            />
          </>
        )
      case "rate_variance":
        return (
          <StepTable
            cols={[
              { key: "room", label: "Room" },
              { key: "guest_name", label: "Guest" },
              { key: "reservation", label: "Confirmation", render: resLink },
              { key: "expected", label: "Booked rate", kind: "money" },
              { key: "posted", label: "Posted", kind: "money" },
              { key: "difference", label: "Difference", kind: "money" },
              { key: "manual", label: "Manual", render: (r) => (r.manual ? t("Yes") : t("No")) },
              { key: "folio", label: "Folio", render: folioLink },
            ]}
            rows={items}
            empty={translate("Every room night posted so far matches its booked rate.")}
          />
        )
      case "zero_rate":
        return <StepTable cols={STAY_COLS} rows={items} empty={translate("No zero-rate rooms tonight.")} />
      case "room_status":
        return (
          <StepTable
            cols={[
              { key: "room", label: "Room" },
              { key: "front_office", label: "Front office" },
              { key: "room_board", label: "Room board" },
              { key: "housekeeping_status", label: "Housekeeping" },
              { key: "guest_name", label: "Guest" },
              { key: "issue", label: "Issue", render: (r) => t(String(r.issue)) },
            ]}
            rows={items}
            empty={translate("Front office and the room board agree.")}
          />
        )
      case "vacant_rooms":
        return (
          <StepTable
            cols={[
              { key: "room", label: "Room" },
              { key: "room_type", label: "Room type" },
              { key: "housekeeping_status", label: "Housekeeping" },
              { key: "room_board", label: "Room board" },
            ]}
            rows={items}
            empty={translate("No vacant rooms.")}
          />
        )
      case "open_tills": {
        const blind = !!state.blind_count
        return (
          <StepTable
            cols={[
              { key: "cashier_id", label: "Cashier", render: (r) => String(r.cashier_id || r.user_name || r.user) },
              { key: "business_date", label: "Business date", kind: "date" },
              { key: "opened_at", label: "Opened", render: (r) => String(r.opened_at ?? "").slice(0, 16) },
              { key: "opening_float", label: "Float", kind: "money" },
              { key: "transactions", label: "Transactions", kind: "num" },
              ...(blind ? [] : [{ key: "cash_taken", label: "Cash taken", kind: "money" as const }]),
            ]}
            rows={items}
            empty={translate("Every till is closed.")}
            actions={(r) =>
              state.ran ? null : (
                <div className="flex items-center justify-end gap-1">
                  <input
                    inputMode="decimal"
                    aria-label={t("Counted cash")}
                    placeholder={t("Counted cash")}
                    value={counted[String(r.session)] ?? ""}
                    onChange={(e) => setCounted((m) => ({ ...m, [String(r.session)]: e.target.value }))}
                    className="h-7 w-28 rounded-md border border-zinc-300 px-2 text-xs"
                  />
                  <Button variant="outline" className="h-7 px-2 text-xs"
                    disabled={!!busy || !Number.isFinite(cash(counted[String(r.session)]))}
                    onClick={() =>
                      act("close", () =>
                        withPin((pin) =>
                          call("kamra.cashier.close_session", {
                            session: r.session,
                            counted_cash: cash(counted[String(r.session)]),
                            notes: "Closed at Night Audit",
                            pin,
                          }),
                        ),
                      )
                    }>
                    {t("Count and close")}
                  </Button>
                </div>
              )
            }
          />
        )
      }
      default:
        return items.length ? (
          <StepTable cols={Object.keys(items[0]).slice(0, 6).map((key) => ({ key, label: key }))} rows={items} />
        ) : null
    }
  }

  const checkCard = (c: Check) => (
    <Card key={c.key} className="p-4">
      <CheckBlock check={c} state={state} onAck={ack}>
        {body(c)}
      </CheckBlock>
    </Card>
  )

  const tillsTable = state.sessions.length > 0 && (
    <DataTable
      dense
      exportName={`tills-${state.business_date}`}
      cols={state.blind_count ? sessionCols().filter((x) => x.key !== "expected_cash" && x.key !== "variance") : sessionCols()}
      rows={state.sessions}
      empty={translate("No cashier sessions on this business date.")}
    />
  )

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      {markingNoShow && (
        <NoShowDialog
          reservation={markingNoShow}
          onClose={() => setMarkingNoShow(null)}
          onDone={() => {
            setMarkingNoShow(null)
            void load()
          }}
        />
      )}
      {checkingIn && (
        <CheckInDialog
          reservation={checkingIn}
          onClose={() => setCheckingIn(null)}
          onDone={() => {
            setCheckingIn(null)
            void load()
          }}
        />
      )}
      {checkingOut && (
        <CheckOutDialog
          reservation={checkingOut}
          onClose={() => setCheckingOut(null)}
          onDone={() => {
            setCheckingOut(null)
            void load()
          }}
          onOpenReservation={(name) => setCheckingOut(name)}
        />
      )}

      <div className="flex flex-wrap items-end justify-between gap-3 print:hidden">
        <div>
          <Link to="/end-of-day" className="inline-flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-800">
            <ArrowLeft className="size-3.5" aria-hidden />
            {t("Night Audit")}
          </Link>
          <h1 className="text-xl font-semibold text-zinc-900">
            {state.ran
              ? t("{d} closed", { d: fmtDay(state.business_date) })
              : t("Close {d}", { d: fmtDay(state.business_date) })}
          </h1>
          <p className="text-sm text-zinc-500">
            {state.property_name} · {t("property time {now}", { now: state.property_now.slice(11, 16) })}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Badge tone={state.stuck_date ? "rose" : state.ran ? "green" : blockers.length ? "rose" : needs.length ? "amber" : "green"}>
            {state.stuck_date ? (
              t("Date stuck")
            ) : state.ran ? (
              t("Closed")
            ) : needs.length ? (
              <>
                <TriangleAlert className="me-1 size-3" aria-hidden />
                {t("{n} to look at", { n: needs.length })}
              </>
            ) : (
              <>
                <CheckCircle2 className="me-1 size-3" aria-hidden />
                {t("Ready")}
              </>
            )}
          </Badge>
          {!state.ran && (
            <Button disabled={!!busy || !canClose} onClick={runAudit}>
              {busy === "run" ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <MoonStar className="size-4" aria-hidden />}
              {busy === "run" ? t("Posting…") : t("Close {d}", { d: fmtDay(state.business_date) })}
            </Button>
          )}
        </div>
      </div>

      {state.stuck_date && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800 print:hidden">
          <p>
            {t("The night audit already closed {d}, but the business date did not move. Advance it without posting again.", {
              d: fmtDay(state.stuck_date.business_date),
            })}
          </p>
          <Button
            variant="outline"
            disabled={busy === "recover"}
            onClick={() =>
              act("recover", async () => {
                await recoverStuckBusinessDate(property)
                setParams({})
              })
            }
          >
            {busy === "recover" ? t("Saving…") : t("Advance date")}
          </Button>
        </div>
      )}
      {err && <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 print:hidden">{translate(err)}</p>}

      {state.ran ? (
        <>
          <Message tone="ok">
            {runOut
              ? t("Posted {n} room nights ({amount}), {ns} no-shows. The business date is now {next}.", {
                  n: Number(runOut.room_charges_posted ?? 0),
                  amount: `${cur()}${money(runOut.amount_posted)}`,
                  ns: Number(runOut.no_shows_flagged ?? 0),
                  next: fmtDay(runOut.next_business_date),
                })
              : t("Room and tax were posted and the business date rolled.")}
          </Message>
          <AuditPackView audit={state.audit} embedded />
        </>
      ) : (
        <>
          <Card className="p-4 print:hidden">
            <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span className="font-medium text-zinc-800">
                {t("{a} of {b} checks clear", { a: clearN, b: counted_.length })}
              </span>
              <span className="text-zinc-500">
                {ahead
                  ? t("The business date is ahead of the server date. The audit for it can run once that day has started.")
                  : blockers.length
                    ? t("Fix or override {n} blocking check(s) to close the day.", { n: blockers.length })
                    : needs.length
                      ? t("Warnings do not stop the close. Look them over first.")
                      : t("Everything is clear. Closing posts room and tax for every in-house guest and rolls the date. It cannot be undone.")}
              </span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-zinc-100" aria-hidden>
              <div className="h-2 bg-brand-600" style={{ width: `${counted_.length ? (clearN / counted_.length) * 100 : 100}%` }} />
            </div>
          </Card>

          {needs.length > 0 && (
            <section className="space-y-3">
              <h2 className="text-sm font-semibold text-zinc-800">{t("Needs you")}</h2>
              {needs.map(checkCard)}
            </section>
          )}

          {fyi.length > 0 && (
            <details className="rounded-xl border border-zinc-200 bg-white p-4">
              <summary className="cursor-pointer text-sm font-semibold text-zinc-800">
                {t("For information · {n}", { n: fyi.length })}
              </summary>
              <div className="mt-3 space-y-3">{fyi.map(checkCard)}</div>
            </details>
          )}

          {clear.length > 0 && (
            <details className="rounded-xl border border-zinc-200 bg-white p-4">
              <summary className="flex cursor-pointer items-center gap-2 text-sm font-semibold text-emerald-700">
                <CheckCircle2 className="size-4" aria-hidden />
                {t("All clear · {n}", { n: clear.length })}
              </summary>
              <ul className="mt-3 flex flex-wrap gap-2">
                {clear.map((c) => (
                  <li key={c.key} className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs text-emerald-800">{t(c.title)}</li>
                ))}
              </ul>
            </details>
          )}

          {tillsTable && (
            <details className="rounded-xl border border-zinc-200 bg-white p-4">
              <summary className="cursor-pointer text-sm font-semibold text-zinc-800">{t("Tills on this date: expected and counted")}</summary>
              <div className="mt-3">{tillsTable}</div>
            </details>
          )}

          <Card className="p-4">
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-zinc-800">{t("Notes for the manager")}</span>
              <span className="mb-2 block text-xs text-zinc-500">{t("Weather, incidents, hand-over. They print on the audit pack.")}</span>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                onBlur={saveNotes}
                rows={3}
                className="w-full rounded-lg border border-zinc-300 bg-white p-3 text-sm"
              />
            </label>
            {state.acknowledgements.length > 0 && (
              <div className="mt-3">
                <DataTable
                  dense
                  cols={[
                    { key: "title", label: "Overridden check", render: (a) => t(a.title) },
                    { key: "count", label: "Items", kind: "num" },
                    { key: "by_name", label: "By", render: (a) => a.by_name || a.by },
                    { key: "at", label: "When", render: (a) => String(a.at).slice(0, 16) },
                    { key: "note", label: "Reason" },
                  ]}
                  rows={state.acknowledgements}
                />
              </div>
            )}
            <p className="mt-3 text-xs text-zinc-500">
              {t("Scheduled audit when checks block: {mode}", { mode: t(state.auto_audit_with_blockers) })}
            </p>
          </Card>
        </>
      )}
    </div>
  )
}
