/*  End of Day - <property> - <business date>.

    The night auditor's wizard, in Opera's order: steps on the left with a
    status each, the active step's panel on the right (a message, the
    actions, and the step's list as a searchable, sortable table). Blocking
    steps cannot be passed without resolving them or acknowledging them with
    a reason; warning steps have Continue. Progress lives on the draft Night
    Audit Run, so reopening resumes where the auditor left off. Step 10 runs
    the same audit the scheduler runs; 11 prints the saved audit pack. */

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react"
import {
  ArrowLeft,
  ArrowRight,
  Ban,
  CheckCircle2,
  Circle,
  Loader2,
  MoonStar,
  Search,
  SkipForward,
  Sparkles,
  TriangleAlert,
} from "lucide-react"
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom"
import { call } from "../lib/api"
import CheckOutDialog from "../components/CheckOutDialog"
import CheckInDialog from "../components/CheckInDialog"
import {
  eodAcknowledge,
  eodMarkNoShow,
  eodProgress,
  eodSession,
  recoverStuckBusinessDate,
  runNightAudit,
  type Check,
  type CheckItem,
  type EodState,
  type Step,
  type StepStatus,
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
import { AuditPackView, SESSION_COLS, DataTable, fmtDay } from "./AuditPack"


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
              <tr key={String(r.reservation ?? r.folio ?? r.session ?? r.order ?? r.room_id ?? r.account ?? i)}>
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

const ICON: Record<StepStatus, ReactNode> = {
  pending: <Circle className="size-4 text-zinc-300" aria-hidden />,
  running: <Loader2 className="size-4 animate-spin text-brand-600" aria-hidden />,
  done: <CheckCircle2 className="size-4 text-emerald-600" aria-hidden />,
  blocked: <Ban className="size-4 text-rose-600" aria-hidden />,
  skipped: <SkipForward className="size-4 text-zinc-400" aria-hidden />,
}

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

/* --- the wizard -------------------------------------------------------------- */

const MESSAGES: Record<string, string> = {
  arrivals: "Arrivals not checked in exist. Review them or Continue - the no-show policy applies as shown.",
  departures: "Departures not checked out exist. Check them out or extend the stay.",
  folios: "In-house folios over the high-balance threshold and balances left on departed stays.",
  outlets: "Open outlet bills block the audit. Eyeball every bill posted to a room for a wrong-room posting.",
  rates: "Room nights posted off the booked rate, and rooms at zero rate.",
  rooms: "Rooms where the front office and the room board disagree.",
  cashiers: "Every till for the business date should be counted and closed.",
}

export default function EndOfDayWizard() {
  const { t } = useT()
  const navigate = useNavigate()
  const { property: rawProperty = "" } = useParams()
  const property = decodeURIComponent(rawProperty)
  const [params, setParams] = useSearchParams()
  const audit = params.get("audit")
  const { withPin } = useCashierAuth()

  const [state, setState] = useState<EodState | null>(null)
  const [active, setActive] = useState(1)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [notes, setNotes] = useState("")
  const [counted, setCounted] = useState<Record<string, string>>({})
  const [runOut, setRunOut] = useState<Record<string, unknown> | null>(null)

  const load = useCallback(
    async (jump?: number) => {
      try {
        const s = await eodSession(property, audit)
        setState(s)
        setNotes(s.notes ?? "")
        setActive((cur) => jump ?? (cur > 1 && !s.ran ? cur : s.current_step || 1))
        setErr(null)
      } catch (e) {
        setErr(serverError(e))
      }
    },
    [property, audit],
  )
  useEffect(() => {
    void load(undefined)
  }, [load])

  const checks = useMemo(() => {
    const m: Record<string, Check> = {}
    for (const c of state?.checks ?? []) m[c.key] = c
    return m
  }, [state])

  const step: Step | undefined = state?.steps.find((s) => s.index === active)

  // check-out opens the guided check-out sheet (settle, credit, invoice)
  const [checkingOut, setCheckingOut] = useState<string | null>(null)
  const [checkingIn, setCheckingIn] = useState<string | null>(null)

  async function act(label: string, fn: () => Promise<unknown>, reload = true) {
    setBusy(label)
    setErr(null)
    try {
      await fn()
      if (reload) await load(active)
    } catch (e) {
      setErr(serverError(e))
    } finally {
      setBusy(null)
    }
  }

  const ack = (key: string, reason: string) =>
    act("ack", () => eodAcknowledge(property, key, reason))

  async function go(to: number, markDone = true) {
    if (!state || !step) return
    if (state.ran) {
      setActive(to)
      return
    }
    await act(
      "next",
      async () => {
        await eodProgress(property, {
          step: Math.min(to, 10),
          ...(markDone && to > active && step.index <= 9 ? { key: step.key, status: "done" } : {}),
          ...(step.key === "notes" ? { notes } : {}),
        })
      },
      true,
    )
    setActive(to)
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
        const s = await eodSession(property, out.audit)
        setState(s)
        setActive(11)
      }
    } catch (e) {
      setErr(serverError(e))
      await load(10)
    } finally {
      setBusy(null)
    }
  }

  if (err && !state)
    return <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{translate(err)}</p>
  if (!state || !step) return <p className="text-sm text-zinc-400">{t("Preparing End of Day…")}</p>

  const blockedSteps = state.steps.filter((s) => s.index < 10 && s.status === "blocked")
  const stepStatus = (s: Step): StepStatus =>
    busy === "run" && s.key === "run" ? "running" : s.status

  /* the active step's panel */
  let panel: ReactNode = null
  const k = step.key
  if (k === "prepare") {
    const bd = state.business_date
    const ahead = bd > state.server_date
    panel = (
      <div className="space-y-4">
        <Message tone={ahead ? "block" : "info"}>
          {ahead
            ? t("The business date is ahead of the server date. The audit for it can run once that day has started.")
            : t("The pre-checks are loaded. Work through the steps, then post room and tax to close the business date.")}
        </Message>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <div className="rounded-lg border border-zinc-200 px-3 py-2">
            <div className="text-[11px] uppercase tracking-wider text-zinc-500">{t("Business date")}</div>
            <div className="mt-0.5 text-lg font-semibold">{fmtDay(bd)}</div>
          </div>
          <div className="rounded-lg border border-zinc-200 px-3 py-2">
            <div className="text-[11px] uppercase tracking-wider text-zinc-500">{t("Server date")}</div>
            <div className="mt-0.5 text-lg font-semibold">{fmtDay(state.server_date)}</div>
            <div className="text-xs text-zinc-500">{state.server_time.slice(11)}</div>
          </div>
          <div className="rounded-lg border border-zinc-200 px-3 py-2">
            <div className="text-[11px] uppercase tracking-wider text-zinc-500">{t("Property time")}</div>
            <div className="mt-0.5 text-lg font-semibold">{state.property_now.slice(11)}</div>
            <div className="text-xs text-zinc-500">{fmtDay(state.property_now)}</div>
          </div>
        </div>
        <DataTable
          cols={[
            { key: "title", label: "Check", render: (c) => t(c.title) },
            { key: "severity", label: "Severity", render: (c) => t(c.severity) },
            { key: "count", label: "Items", kind: "num" },
          ]}
          rows={state.checks}
        />
        <p className="text-xs text-zinc-500">
          {t("Scheduled audit when checks block: {mode}", { mode: t(state.auto_audit_with_blockers) })}
        </p>
      </div>
    )
  } else if (k === "arrivals") {
    const c = checks.arrivals_pending
    panel = (
      <CheckBlock check={c} state={state} onAck={ack}>
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
          rows={c?.items ?? []}
          empty={translate("Every arrival is checked in.")}
          actions={(r) =>
            state.ran ? null : (
              <div className="flex flex-col items-stretch gap-1">
                <Button variant="outline" className="h-7 px-2 text-xs"
                  onClick={() => setCheckingIn(String(r.reservation))}>
                  {t("Check in")}
                </Button>
                <Button variant="ghost" className="h-7 px-2 text-xs text-rose-700" disabled={!!busy}
                  onClick={() => act("noshow", () => eodMarkNoShow(String(r.reservation)))}>
                  {t("Mark no-show")}
                </Button>
              </div>
            )
          }
        />
      </CheckBlock>
    )
  } else if (k === "departures") {
    const c = checks.departures_due
    const zero = (c?.items ?? []).filter((r) => Math.abs(Number(r.balance ?? 0)) < 0.01)
    panel = (
      <CheckBlock check={c} state={state} onAck={ack}>
        {!state.ran && zero.length > 0 && (
          <div className="flex justify-end">
            <Button variant="outline" disabled={!!busy}
              onClick={() =>
                act("bulk", async () => {
                  await withPin(async (pin) => {
                    for (const r of zero)
                      await call("kamra.ledger.quick_checkout", { reservation: r.reservation, pin })
                  })
                })
              }>
              {t("Quick check out {n} zero-balance departures", { n: zero.length })}
            </Button>
          </div>
        )}
        <StepTable
          cols={STAY_COLS}
          rows={c?.items ?? []}
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
      </CheckBlock>
    )
  } else if (k === "folios") {
    const hb = checks.high_balance
    panel = (
      <div className="space-y-6">
        <CheckBlock check={hb} state={state} onAck={ack}>
          {hb && !hb.enabled && <p className="text-xs text-zinc-500">{t("The high-balance check is off (threshold 0).")}</p>}
          {hb?.enabled && (
            <p className="text-xs text-zinc-500">
              {t("Threshold {cur}{n}", { cur: cur(), n: money(hb.threshold) })}
            </p>
          )}
          <StepTable cols={FOLIO_COLS} rows={hb?.items ?? []} empty={translate("No in-house folio is over the threshold.")} />
        </CheckBlock>
        <CheckBlock check={checks.departed_balances} state={state} onAck={ack}>
          <StepTable cols={FOLIO_COLS} rows={checks.departed_balances?.items ?? []} empty={translate("No balances on departed stays.")} />
        </CheckBlock>
        <CheckBlock check={checks.credit_limit} state={state} onAck={ack}>
          <StepTable
            cols={[
              { key: "company", label: "Company" },
              { key: "credit_limit", label: "Credit limit", kind: "money" },
              { key: "ar_balance", label: "AR balance", kind: "money" },
              { key: "in_house", label: "In-house folios", kind: "money" },
              { key: "exposure", label: "Exposure", kind: "money" },
              { key: "over_by", label: "Over by", kind: "money" },
            ]}
            rows={checks.credit_limit?.items ?? []}
            empty={translate("No company is over its credit limit.")}
          />
        </CheckBlock>
        <CheckBlock check={checks.overdue_ar} state={state} onAck={ack}>
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
            rows={checks.overdue_ar?.items ?? []}
            empty={translate("No company has an overdue bill.")}
          />
        </CheckBlock>
      </div>
    )
  } else if (k === "outlets") {
    const pr = checks.pos_room_postings
    panel = (
      <div className="space-y-6">
        <CheckBlock check={checks.open_pos_bills} state={state} onAck={ack}>
          <StepTable cols={POS_COLS} rows={checks.open_pos_bills?.items ?? []} empty={translate("Every outlet bill is settled.")} />
        </CheckBlock>
        <CheckBlock check={pr} state={state} onAck={ack}>
          {(pr?.mismatches ?? 0) > 0 && (
            <Message tone="warn">{t("{n} bill(s) were taken for a different room than the folio they posted to.", { n: pr!.mismatches! })}</Message>
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
            rows={pr?.items ?? []}
            empty={translate("No outlet bills were posted to rooms today.")}
          />
        </CheckBlock>
      </div>
    )
  } else if (k === "rates") {
    panel = (
      <div className="space-y-6">
        <CheckBlock check={checks.rate_variance} state={state} onAck={ack}>
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
            rows={checks.rate_variance?.items ?? []}
            empty={translate("Every room night posted so far matches its booked rate.")}
          />
        </CheckBlock>
        <CheckBlock check={checks.zero_rate} state={state} onAck={ack}>
          <StepTable cols={STAY_COLS} rows={checks.zero_rate?.items ?? []} empty={translate("No zero-rate rooms tonight.")} />
        </CheckBlock>
      </div>
    )
  } else if (k === "rooms") {
    panel = (
      <div className="space-y-6">
        <CheckBlock check={checks.room_status} state={state} onAck={ack}>
          <StepTable
            cols={[
              { key: "room", label: "Room" },
              { key: "front_office", label: "Front office" },
              { key: "room_board", label: "Room board" },
              { key: "housekeeping_status", label: "Housekeeping" },
              { key: "guest_name", label: "Guest" },
              { key: "issue", label: "Issue", render: (r) => t(String(r.issue)) },
            ]}
            rows={checks.room_status?.items ?? []}
            empty={translate("Front office and the room board agree.")}
          />
        </CheckBlock>
        <CheckBlock check={checks.vacant_rooms} state={state} onAck={ack}>
          <StepTable
            cols={[
              { key: "room", label: "Room" },
              { key: "room_type", label: "Room type" },
              { key: "housekeeping_status", label: "Housekeeping" },
              { key: "room_board", label: "Room board" },
            ]}
            rows={checks.vacant_rooms?.items ?? []}
            empty={translate("No vacant rooms.")}
          />
        </CheckBlock>
      </div>
    )
  } else if (k === "cashiers") {
    const c = checks.open_tills
    const blind = !!state.blind_count
    panel = (
      <div className="space-y-6">
        <CheckBlock check={c} state={state} onAck={ack}>
          <StepTable
            cols={[
              { key: "cashier_id", label: "Cashier", render: (r) => String(r.cashier_id || r.user_name || r.user) },
              { key: "business_date", label: "Business date", kind: "date" },
              { key: "opened_at", label: "Opened", render: (r) => String(r.opened_at ?? "").slice(0, 16) },
              { key: "opening_float", label: "Float", kind: "money" },
              { key: "transactions", label: "Transactions", kind: "num" },
              ...(blind ? [] : [{ key: "cash_taken", label: "Cash taken", kind: "money" as const }]),
            ]}
            rows={c?.items ?? []}
            empty={translate("Every till is closed.")}
            actions={(r) =>
              state.ran ? null : (
                <div className="flex items-center justify-end gap-1">
                  <input
                    inputMode="decimal"
                    placeholder={t("Counted cash")}
                    value={counted[String(r.session)] ?? ""}
                    onChange={(e) => setCounted((m) => ({ ...m, [String(r.session)]: e.target.value }))}
                    className="h-7 w-28 rounded-md border border-zinc-300 px-2 text-xs"
                  />
                  <Button variant="outline" className="h-7 px-2 text-xs"
                    disabled={!!busy || counted[String(r.session)] === undefined || counted[String(r.session)] === ""}
                    onClick={() =>
                      act("close", () =>
                        withPin((pin) =>
                          call("kamra.cashier.close_session", {
                            session: r.session,
                            counted_cash: Number(counted[String(r.session)] || 0),
                            notes: "Closed at End of Day",
                            pin,
                          }),
                        ),
                      )
                    }>
                    {t("Close session")}
                  </Button>
                </div>
              )
            }
          />
        </CheckBlock>
        <div>
          <h3 className="mb-2 text-sm font-semibold text-zinc-800">{t("Expected vs counted")}</h3>
          <DataTable
            dense
            cols={blind ? SESSION_COLS.filter((x) => x.key !== "expected_cash" && x.key !== "variance") : SESSION_COLS}
            rows={state.sessions}
            empty={translate("No cashier sessions on this business date.")}
          />
        </div>
      </div>
    )
  } else if (k === "notes") {
    panel = (
      <div className="space-y-2">
        <Message tone="info">{t("Notes for the manager - weather, incidents, hand-over. They print on the audit pack.")}</Message>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={8}
          disabled={state.ran}
          className="w-full rounded-lg border border-zinc-300 bg-white p-3 text-sm"
          placeholder={t("Weather or notes")}
        />
        {!state.ran && (
          <div className="flex justify-end">
            <Button variant="outline" disabled={!!busy} onClick={() => act("notes", () => eodProgress(property, { notes }))}>
              {t("Save notes")}
            </Button>
          </div>
        )}
      </div>
    )
  } else if (k === "run") {
    panel = (
      <div className="space-y-4">
        {state.ran ? (
          <Message tone="ok">{t("Room and tax were posted and the business date rolled.")}</Message>
        ) : blockedSteps.length ? (
          <Message tone="block">
            {t("Blocked: {steps}. Resolve or acknowledge them before posting room and tax.", {
              steps: blockedSteps.map((s) => t(s.title)).join(", "),
            })}
          </Message>
        ) : (
          <Message tone="info">
            {t("This posts tonight's room and tax for every in-house guest, applies the no-show policy, saves the audit pack and rolls the business date from {bd}. It cannot be undone.", {
              bd: fmtDay(state.business_date),
            })}
          </Message>
        )}
        {state.acknowledgements.length > 0 && (
          <DataTable
            dense
            cols={[
              { key: "title", label: "Acknowledged check", render: (a) => t(a.title) },
              { key: "count", label: "Items", kind: "num" },
              { key: "by_name", label: "By", render: (a) => a.by_name || a.by },
              { key: "at", label: "When", render: (a) => String(a.at).slice(0, 16) },
              { key: "note", label: "Reason" },
            ]}
            rows={state.acknowledgements}
          />
        )}
        {!state.ran && (
          <Button disabled={!!busy || blockedSteps.length > 0} onClick={runAudit}>
            {busy === "run" ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <MoonStar className="size-4" aria-hidden />}
            {busy === "run" ? t("Posting…") : t("Post room and tax and roll the business date")}
          </Button>
        )}
      </div>
    )
  } else if (k === "reports") {
    panel = state.ran ? <AuditPackView audit={state.audit} embedded /> : (
      <Message tone="info">{t("The final reports are printed after room and tax are posted.")}</Message>
    )
  } else if (k === "finalize") {
    const r = runOut
    panel = state.ran ? (
      <div className="space-y-3">
        <Message tone="ok">
          {t("End of Day for {bd} is complete.", { bd: fmtDay(state.business_date) })}
        </Message>
        {r && (
          <p className="text-sm text-zinc-600">
            {t("Posted {n} room nights ({amount}), {ns} no-shows. The business date is now {next}.", {
              n: Number(r.room_charges_posted ?? 0),
              amount: `${cur()}${money(r.amount_posted)}`,
              ns: Number(r.no_shows_flagged ?? 0),
              next: fmtDay(r.next_business_date),
            })}
          </p>
        )}
        <Button onClick={() => navigate("/end-of-day")}>{t("Done")}</Button>
      </div>
    ) : (
      <Message tone="info">{t("Finish the steps above first.")}</Message>
    )
  }

  const canNext =
    k !== "run" && k !== "finalize" && (state.ran ? active >= 11 : step.status !== "blocked")
  const message = MESSAGES[k]

  return (
    <div className="space-y-4">
      {checkingIn && (
        <CheckInDialog
          reservation={checkingIn}
          onClose={() => setCheckingIn(null)}
          onDone={() => {
            setCheckingIn(null)
            void load(active)
          }}
        />
      )}
      {checkingOut && (
        <CheckOutDialog
          reservation={checkingOut}
          onClose={() => setCheckingOut(null)}
          onDone={() => {
            setCheckingOut(null)
            void load(active)
          }}
          onOpenReservation={(name) => setCheckingOut(name)}
        />
      )}
      <div className="flex flex-wrap items-center justify-between gap-2 print:hidden">
        <div>
          <Link to="/end-of-day" className="inline-flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-800">
            <ArrowLeft className="size-3.5" aria-hidden />
            {t("Manage Night Audit")}
          </Link>
          <h1 className="text-lg font-semibold text-zinc-900">
            {t("Night Audit")} - {state.property_name} - {fmtDay(state.business_date)}
          </h1>
        </div>
        <Badge
          tone={
            state.stuck_date ? "rose" : state.ran ? "green" : blockedSteps.length ? "rose" : "brand"
          }
        >
          {state.stuck_date
            ? t("Date stuck")
            : state.ran
              ? t("Closed")
              : blockedSteps.length
                ? t("{n} blocker(s)", { n: blockedSteps.length })
                : t("Ready")}
        </Badge>
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
      {err && <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 print:hidden">{err}</p>}
      <div className="grid gap-4 lg:grid-cols-[280px_1fr] print:block">
        <Card className="h-fit p-2 print:hidden">
          <ol>
            {state.steps.map((s) => {
              const reachable = state.ran || s.index <= 10
              return (
                <li key={s.key}>
                  <button
                    type="button"
                    disabled={!reachable}
                    onClick={() => setActive(s.index)}
                    className={cn(
                      "flex w-full items-center gap-2 rounded-lg px-2 py-2 text-start text-sm hover:bg-zinc-100 disabled:opacity-50",
                      active === s.index && "bg-brand-50 font-medium text-brand-800",
                    )}
                  >
                    {ICON[stepStatus(s)]}
                    <span className="w-5 text-xs tabular-nums text-zinc-400">{s.index}</span>
                    <span className="flex-1">{t(s.title)}</span>
                    {s.count > 0 && s.index < 10 && (
                      <span className={cn("text-xs tabular-nums", s.status === "blocked" ? "text-rose-600" : "text-zinc-400")}>
                        {s.count}
                      </span>
                    )}
                  </button>
                </li>
              )
            })}
          </ol>
        </Card>
        <Card className="min-w-0 p-5 print:border-0 print:p-0 print:shadow-none">
          <div className="mb-4 flex items-center gap-2 print:hidden">
            {ICON[stepStatus(step)]}
            <h2 className="text-base font-semibold text-zinc-900">
              {step.index}. {t(step.title)}
            </h2>
          </div>
          {message && step.count > 0 && (
            <div className="mb-4 print:hidden">
              <Message tone={step.status === "blocked" ? "block" : "warn"}>
                {step.status === "blocked" && <TriangleAlert className="me-1 inline size-4" aria-hidden />}
                {t(message)}
              </Message>
            </div>
          )}
          {panel}
          <div className="mt-6 flex items-center justify-between border-t border-zinc-100 pt-4 print:hidden">
            <Button variant="outline" disabled={active <= 1 || !!busy} onClick={() => setActive(active - 1)}>
              <ArrowLeft className="size-4" aria-hidden />
              {t("Back")}
            </Button>
            {canNext && (
              <Button disabled={!!busy} onClick={() => go(active + 1)}>
                {active === 1 ? t("Start") : t("Continue")}
                <ArrowRight className="size-4" aria-hidden />
              </Button>
            )}
          </div>
        </Card>
      </div>
    </div>
  )
}
