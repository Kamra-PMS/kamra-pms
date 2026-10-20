/*  One room, everything about it: status, who is in it now, the next weeks,
    who stayed and who cleaned, and what the room is. Opens over the Rooms
    screen (no navigation). Every change goes through an existing writer:
    set_housekeeping_status, create_room_block / release_room_block, the
    guided check-in and check-out sheets, and the room move dialog. */

import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import {
  ArrowLeftRight,
  BedDouble,
  CalendarRange,
  History,
  Info,
  ConciergeBell,
  LogIn,
  Receipt,
  LogOut,
  Wrench,
} from "lucide-react"
import { call, setHousekeepingStatus } from "../lib/api"
import {
  getRoomAvailability,
  getRoomDetail,
  getRoomHistory,
  type HkStatus,
  type RoomAvailability,
  type RoomDetail,
  type RoomHistory,
} from "../lib/rooms"
import { serverError } from "../lib/resource"
import { fmtMoney } from "../lib/money"
import { useT } from "../lib/i18n"
import { cn } from "../lib/utils"
import { Sheet } from "./ui/sheet"
import { Button } from "./ui/button"
import { Badge } from "./ui/badge"
import { HkMediaView } from "./HkMedia"
import { GuestRequests, StayBilling } from "./RoomStayPanels"

export type RoomTab =
  | "status"
  | "now"
  | "requests"
  | "billing"
  | "availability"
  | "history"
  | "details"
type Tab = RoomTab

export const HK_TONE: Record<HkStatus, string> = {
  Clean: "border-emerald-300 bg-emerald-50 text-emerald-900",
  Inspected: "border-sky-300 bg-sky-50 text-sky-900",
  Ready: "border-teal-400 bg-teal-50 text-teal-900",
  Dirty: "border-amber-300 bg-amber-50 text-amber-900",
  "Out of Order": "border-rose-300 bg-rose-50 text-rose-900",
}

const HK_SET: HkStatus[] = ["Dirty", "Clean", "Inspected", "Ready"]

/** What the person picks; the Room Block reason it is stored as. */
const OUT_KINDS = [
  { id: "ooo", reason: "Maintenance", label: "Out of order (repairs)" },
  { id: "house", reason: "House Use", label: "House use" },
  { id: "owner", reason: "Owner", label: "Owner stay" },
  { id: "vip", reason: "VIP Hold", label: "VIP hold" },
  { id: "other", reason: "Other", label: "Other reason" },
] as const

const REASON_LABEL: Record<string, string> = {
  Maintenance: "Out of order (repairs)",
  "House Use": "House use",
  Owner: "Owner stay",
  "VIP Hold": "VIP hold",
  Other: "Other reason",
}

export function useDates() {
  const { lang } = useT()
  const loc = lang === "ar" ? "ar" : undefined
  const day = (s?: string | null) =>
    s
      ? new Date(s.slice(0, 10) + "T00:00:00").toLocaleDateString(loc, {
          day: "numeric",
          month: "short",
        })
      : ""
  const when = (s?: string | null) =>
    s
      ? new Date(s.replace(" ", "T")).toLocaleString(loc, {
          day: "numeric",
          month: "short",
          hour: "2-digit",
          minute: "2-digit",
        })
      : ""
  return { day, when, loc }
}

const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`

export default function RoomDrawer(props: {
  room: string
  onClose: () => void
  /** something changed (status, block, stay): refresh the board */
  onChanged: () => void
  onCheckOut: (reservation: string) => void
  onCheckIn: (reservation: string) => void
  onMove: (reservation: string, roomNumber: string) => void
  /** bump to reload after a dialog the page owns finished */
  reloadKey?: number
  /** open on this tab (e.g. billing from the Today room menu) */
  initialTab?: RoomTab
}) {
  const { t } = useT()
  const [d, setD] = useState<RoomDetail | null>(null)
  const [tab, setTab] = useState<Tab | null>(props.initialTab ?? null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    getRoomDetail(props.room)
      .then((x) => {
        setD(x)
        setError(null)
        setTab((cur) => cur ?? (x.stay || x.next_arrival?.arriving_today ? "now" : "status"))
      })
      .catch((e) => setError(serverError(e)))
  }, [props.room])

  useEffect(() => {
    load()
  }, [load, props.reloadKey])

  async function act(fn: () => Promise<unknown>) {
    setBusy(true)
    setError(null)
    try {
      await fn()
      load()
      props.onChanged()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: "status", label: t("Status"), icon: <Wrench className="size-4" /> },
    { id: "now", label: t("Now"), icon: <BedDouble className="size-4" /> },
    ...(d?.stay && d.can.desk
      ? ([
          { id: "requests", label: t("Guest requests"), icon: <ConciergeBell className="size-4" /> },
          { id: "billing", label: t("Folio and billing"), icon: <Receipt className="size-4" /> },
        ] as const)
      : []),
    { id: "availability", label: t("Availability"), icon: <CalendarRange className="size-4" /> },
    { id: "history", label: t("History"), icon: <History className="size-4" /> },
    { id: "details", label: t("Details"), icon: <Info className="size-4" /> },
  ]

  const title = d
    ? t("Room {n}", { n: d.room.room_number })
    : t("Room {n}", { n: props.room.split("-").pop() ?? "" })
  const description = d
    ? [d.room.room_type_name, d.room.floor ? t("Floor {f}", { f: d.room.floor }) : null]
        .filter(Boolean)
        .join(" · ")
    : undefined

  return (
    <Sheet title={title} description={description} onClose={props.onClose} wide>
      {error && (
        <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}
      {!d ? (
        <p className="text-sm text-zinc-400">{t("Loading…")}</p>
      ) : (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <span
              className={cn(
                "rounded-lg border px-2.5 py-1 text-sm font-semibold",
                HK_TONE[d.room.housekeeping_status],
              )}
            >
              {t(d.room.housekeeping_status)}
            </span>
            <Badge tone={d.room.occupancy_status === "Occupied" ? "brand" : "zinc"}>
              {d.room.occupancy_status === "Occupied" ? t("Occupied") : t("Vacant")}
            </Badge>
            {d.blocks.some((b) => b.current) && (
              <Badge tone="rose">{t("Out of service")}</Badge>
            )}
            {d.stay?.departing_today && <Badge tone="amber">{t("Departing today")}</Badge>}
            {d.next_arrival?.arriving_today && <Badge tone="sky">{t("Arriving today")}</Badge>}
          </div>
          <div
            role="tablist"
            className="mb-4 flex gap-1 overflow-x-auto border-b border-zinc-100"
          >
            {tabs.map((x) => (
              <button
                key={x.id}
                role="tab"
                aria-selected={tab === x.id}
                onClick={() => setTab(x.id)}
                className={cn(
                  "relative inline-flex min-h-11 shrink-0 items-center gap-1.5 px-3 text-sm font-medium",
                  tab === x.id ? "text-brand-700" : "text-zinc-500 hover:text-zinc-800",
                )}
              >
                {x.icon}
                {x.label}
                {tab === x.id && (
                  <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-brand-600" />
                )}
              </button>
            ))}
          </div>
          {tab === "status" && <StatusTab d={d} busy={busy} act={act} />}
          {tab === "now" && (
            <NowTab
              d={d}
              onCheckOut={props.onCheckOut}
              onCheckIn={props.onCheckIn}
              onMove={(res) => props.onMove(res, d.room.room_number)}
              onTab={setTab}
            />
          )}
          {tab === "requests" && d.stay && d.can.desk && (
            <GuestRequests d={d} onChanged={props.onChanged} />
          )}
          {tab === "billing" && d.stay && d.can.desk && (
            <StayBilling d={d} onChanged={props.onChanged} />
          )}
          {tab === "availability" && <AvailabilityTab room={d.room.name} />}
          {tab === "history" && <HistoryTab room={d.room.name} />}
          {tab === "details" && <DetailsTab d={d} />}
        </>
      )}
    </Sheet>
  )
}

function Section(props: { title: string; children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <section className="mb-6">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-zinc-800">{props.title}</h3>
        {props.aside}
      </div>
      {props.children}
    </section>
  )
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-zinc-400">{children}</p>
}

// --- Status -------------------------------------------------------------------

function StatusTab({
  d,
  busy,
  act,
}: {
  d: RoomDetail
  busy: boolean
  act: (fn: () => Promise<unknown>) => Promise<void>
}) {
  const { t } = useT()
  const { day } = useDates()
  const today = d.date
  const [kind, setKind] = useState<(typeof OUT_KINDS)[number]["id"]>("ooo")
  const [from, setFrom] = useState(today)
  const [to, setTo] = useState(() => {
    const x = new Date(today + "T00:00:00")
    x.setDate(x.getDate() + 1)
    return iso(x)
  })
  const [note, setNote] = useState("")
  const [formOpen, setFormOpen] = useState(false)
  const status = d.room.housekeeping_status
  const current = d.blocks.filter((b) => b.current)

  function takeOut() {
    const k = OUT_KINDS.find((x) => x.id === kind)!
    return act(async () => {
      await call("kamra.api.create_room_block", {
        property: d.room.property,
        room: d.room.name,
        from_date: from,
        to_date: to,
        reason: k.reason,
        note: note.trim() || undefined,
      })
      // a broken room is also flagged for housekeeping when the hold starts today
      if (k.id === "ooo" && from <= today && d.can.supervise && status !== "Out of Order") {
        await setHousekeepingStatus(d.room.name, "Out of Order")
      }
      setFormOpen(false)
      setNote("")
    })
  }

  function backInService() {
    return act(async () => {
      for (const b of current) {
        await call("kamra.api.release_room_block", { name: b.name })
      }
      // it needs a clean before anyone sleeps in it
      if (status === "Out of Order" && d.can.supervise) {
        await setHousekeepingStatus(d.room.name, "Dirty")
      }
    })
  }

  return (
    <div>
      <Section title={t("Housekeeping status")}>
        {d.can.supervise ? (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {HK_SET.map((s) => (
              <button
                key={s}
                disabled={busy || s === status}
                onClick={() => act(() => setHousekeepingStatus(d.room.name, s))}
                className={cn(
                  "min-h-14 rounded-xl border-2 px-3 py-2 text-base font-semibold transition-colors",
                  s === status
                    ? cn(HK_TONE[s], "ring-2 ring-brand-600 ring-offset-1")
                    : "border-zinc-200 bg-white text-zinc-700 hover:border-zinc-400",
                  "disabled:cursor-default",
                )}
              >
                {t(s)}
                {s === status && (
                  <span className="block text-[11px] font-medium opacity-70">{t("Now")}</span>
                )}
              </button>
            ))}
          </div>
        ) : (
          <Empty>{t("Your role can see the status but not change it.")}</Empty>
        )}
        {d.tasks.length > 0 && (
          <ul className="mt-3 space-y-1.5">
            {d.tasks.map((x) => (
              <li
                key={x.name}
                className="flex flex-wrap items-center gap-2 rounded-lg border border-zinc-200 px-3 py-2 text-sm"
              >
                <span className="font-medium">{t(x.task_type)}</span>
                <Badge tone={x.status === "In Progress" ? "sky" : "zinc"}>{t(x.status)}</Badge>
                <span className="text-zinc-500">{x.assignee ?? t("Not assigned")}</span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title={t("Out of service")}>
        {d.blocks.length === 0 && status !== "Out of Order" && (
          <Empty>{t("This room is in service.")}</Empty>
        )}
        {d.blocks.length > 0 && (
          <ul className="mb-3 space-y-2">
            {d.blocks.map((b) => (
              <li
                key={b.name}
                className="rounded-lg border border-rose-200 bg-rose-50/60 px-3 py-2 text-sm"
              >
                <div className="font-medium text-rose-900">
                  {t(REASON_LABEL[b.reason] ?? b.reason)}
                </div>
                <div className="text-rose-800/80">
                  {t("{from} to {to}", { from: day(b.from_date), to: day(b.to_date) })}
                  {!b.current && ` · ${t("starts later")}`}
                </div>
                {b.note && <div className="mt-0.5 text-zinc-600">{b.note}</div>}
              </li>
            ))}
          </ul>
        )}
        {(current.length > 0 || status === "Out of Order") &&
          (d.can.block || d.can.supervise) && (
            <Button
              className="min-h-11 px-4 text-base"
              disabled={busy || (current.length > 0 && !d.can.block)}
              onClick={backInService}
            >
              {t("Back in service")}
            </Button>
          )}
        {d.can.block && !formOpen && (
          <Button
            variant="outline"
            className="ms-2 min-h-11 px-4 text-base"
            onClick={() => setFormOpen(true)}
          >
            {t("Take out of service")}
          </Button>
        )}
        {d.can.block && formOpen && (
          <div className="mt-3 rounded-xl border border-zinc-200 p-3">
            <p className="mb-2 text-sm text-zinc-600">{t("Why?")}</p>
            <div className="mb-3 flex flex-wrap gap-2">
              {OUT_KINDS.map((k) => (
                <button
                  key={k.id}
                  onClick={() => setKind(k.id)}
                  className={cn(
                    "min-h-11 rounded-lg border px-3 text-sm font-medium",
                    kind === k.id
                      ? "border-brand-600 bg-brand-50 text-brand-800"
                      : "border-zinc-200 text-zinc-700 hover:border-zinc-400",
                  )}
                >
                  {t(k.label)}
                </button>
              ))}
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className="text-sm text-zinc-600">
                {t("From")}
                <input
                  type="date"
                  value={from}
                  min={today}
                  onChange={(e) => setFrom(e.target.value)}
                  className="mt-1 block min-h-11 w-full rounded-lg border border-zinc-300 px-3"
                />
              </label>
              <label className="text-sm text-zinc-600">
                {t("Back on (first night it can be sold)")}
                <input
                  type="date"
                  value={to}
                  min={from}
                  onChange={(e) => setTo(e.target.value)}
                  className="mt-1 block min-h-11 w-full rounded-lg border border-zinc-300 px-3"
                />
              </label>
            </div>
            <label className="mt-3 block text-sm text-zinc-600">
              {t("Note (what is wrong, who is fixing it)")}
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={2}
                className="mt-1 block w-full rounded-lg border border-zinc-300 px-3 py-2"
              />
            </label>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                className="min-h-11 px-4"
                disabled={busy || !from || !to || to <= from}
                onClick={takeOut}
              >
                {t("Take out of service")}
              </Button>
              <Button variant="ghost" className="min-h-11" onClick={() => setFormOpen(false)}>
                {t("Cancel")}
              </Button>
            </div>
          </div>
        )}
        {d.can.block && (
          <p className="mt-3 text-xs text-zinc-400">
            {t("Holds also show on the Tape Chart and in")}{" "}
            <Link to="/room-blocks" className="text-brand-700 hover:underline">
              {t("Room Blocks")}
            </Link>
          </p>
        )}
      </Section>
    </div>
  )
}

// --- Now ----------------------------------------------------------------------

function NowTab({
  d,
  onCheckOut,
  onCheckIn,
  onMove,
  onTab,
}: {
  d: RoomDetail
  onCheckOut: (res: string) => void
  onCheckIn: (res: string) => void
  onMove: (res: string) => void
  onTab: (tab: Tab) => void
}) {
  const { t, tn } = useT()
  const { day } = useDates()
  const s = d.stay
  const a = d.next_arrival
  return (
    <div>
      <Section title={t("In the room now")}>
        {s ? (
          <div className="rounded-xl border border-zinc-200 p-4">
            <div className="text-lg font-semibold text-zinc-900">{s.guest_name}</div>
            <div className="mt-0.5 text-sm text-zinc-500">
              {t("{from} to {to}", { from: day(s.check_in_date), to: day(s.check_out_date) })}
              {" · "}
              {tn(s.nights, "{n} night", "{n} nights")}
              {" · "}
              {tn(s.adults, "{n} adult", "{n} adults")}
              {s.children ? ` + ${tn(s.children, "{n} child", "{n} children")}` : ""}
            </div>
            {s.balance_due !== undefined && (
              <div className="mt-3 grid grid-cols-3 gap-2 text-sm">
                <Money label={t("Stay total")} value={s.total} />
                <Money label={t("Paid")} value={s.paid} />
                <Money label={t("Balance")} value={s.balance_due} strong={(s.balance_due ?? 0) > 0} />
              </div>
            )}
            {d.can.desk && (
              <div className="mt-4 flex flex-wrap gap-2">
                <Button className="min-h-11 px-4 text-base" onClick={() => onCheckOut(s.name)}>
                  <LogOut className="size-4" /> {t("Check out")}
                </Button>
                <Button variant="outline" className="min-h-11 px-4" onClick={() => onTab("billing")}>
                  <Receipt className="size-4" /> {t("Folio and billing")}
                </Button>
                <Button variant="outline" className="min-h-11 px-4" onClick={() => onTab("requests")}>
                  <ConciergeBell className="size-4" /> {t("Guest requests")}
                </Button>
                <Button variant="outline" className="min-h-11 px-4" onClick={() => onMove(s.name)}>
                  <ArrowLeftRight className="size-4" /> {t("Move room")}
                </Button>
                <Link
                  to={`/grc/${encodeURIComponent(s.name)}`}
                  className="inline-flex min-h-11 items-center rounded-lg px-3 text-sm font-medium text-brand-700 hover:bg-brand-50"
                >
                  {t("Registration card")}
                </Link>
              </div>
            )}
          </div>
        ) : (
          <Empty>{t("Nobody is staying in this room.")}</Empty>
        )}
      </Section>
      <Section title={a?.arriving_today ? t("Arriving today") : t("Next arrival")}>
        {a ? (
          <div className="rounded-xl border border-zinc-200 p-4">
            <div className="text-lg font-semibold text-zinc-900">{a.guest_name}</div>
            <div className="mt-0.5 text-sm text-zinc-500">
              {t("{from} to {to}", { from: day(a.check_in_date), to: day(a.check_out_date) })}
              {" · "}
              {tn(a.nights, "{n} night", "{n} nights")}
              {a.eta ? ` · ${t("ETA {eta}", { eta: a.eta })}` : ""}
            </div>
            {d.can.desk && (
              <div className="mt-4 flex flex-wrap gap-2">
                {a.arriving_today && !s && (
                  <Button className="min-h-11 px-4 text-base" onClick={() => onCheckIn(a.name)}>
                    <LogIn className="size-4" /> {t("Check in")}
                  </Button>
                )}
                <Button variant="outline" className="min-h-11 px-4" onClick={() => onMove(a.name)}>
                  <ArrowLeftRight className="size-4" /> {t("Move to another room")}
                </Button>
              </div>
            )}
            {a.arriving_today && s && (
              <p className="mt-2 text-sm text-amber-700">
                {t("The room is still occupied. Check the current guest out first.")}
              </p>
            )}
          </div>
        ) : (
          <Empty>{t("No arrival is booked into this room yet.")}</Empty>
        )}
      </Section>
    </div>
  )
}

function Money(props: { label: string; value?: number; strong?: boolean }) {
  return (
    <div className="rounded-lg bg-zinc-50 px-3 py-2">
      <div className="text-[11px] text-zinc-500">{props.label}</div>
      <div
        className={cn(
          "tabular-nums font-semibold",
          props.strong ? "text-amber-700" : "text-zinc-800",
        )}
      >
        {fmtMoney(props.value ?? 0)}
      </div>
    </div>
  )
}

// --- Availability -------------------------------------------------------------

function AvailabilityTab({ room }: { room: string }) {
  const { t } = useT()
  const { day, loc } = useDates()
  const [days, setDays] = useState(14)
  const [a, setA] = useState<RoomAvailability | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    setA(null)
    getRoomAvailability(room, days)
      .then(setA)
      .catch((e) => setError(serverError(e)))
  }, [room, days])

  const stays = a
    ? Array.from(
        new Map(
          a.cells
            .filter((c) => c.state === "booked" && c.reservation)
            .map((c) => [c.reservation!, c]),
        ).values(),
      )
    : []

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {[14, 30].map((n) => (
          <button
            key={n}
            onClick={() => setDays(n)}
            className={cn(
              "min-h-10 rounded-lg border px-3 text-sm font-medium",
              days === n
                ? "border-brand-600 bg-brand-50 text-brand-800"
                : "border-zinc-200 text-zinc-600",
            )}
          >
            {t("Next {n} days", { n })}
          </button>
        ))}
        {a && (
          <span className="text-sm text-zinc-500">
            {t("{free} free · {booked} booked · {blocked} held", {
              free: a.summary.free,
              booked: a.summary.booked,
              blocked: a.summary.blocked,
            })}
          </span>
        )}
      </div>
      {error && <p className="text-sm text-rose-700">{error}</p>}
      {!a ? (
        !error && <Empty>{t("Loading…")}</Empty>
      ) : (
        <>
          <div className="grid grid-cols-7 gap-1.5">
            {a.cells.map((c) => {
              const dt = new Date(c.date + "T00:00:00")
              return (
                <div
                  key={c.date}
                  title={
                    c.state === "booked"
                      ? `${c.guest_name ?? ""}`
                      : c.state === "blocked"
                        ? t(REASON_LABEL[c.reason ?? ""] ?? c.reason ?? "")
                        : t("Free")
                  }
                  className={cn(
                    "min-w-0 rounded-lg border px-1 py-1.5 text-center",
                    c.state === "booked" && "border-brand-700 bg-brand-700 text-white",
                    c.state === "blocked" && "border-rose-300 bg-rose-100 text-rose-900",
                    c.state === "free" && "border-zinc-200 bg-white text-zinc-700",
                  )}
                >
                  <div className="text-[10px] uppercase opacity-70">
                    {dt.toLocaleDateString(loc, { weekday: "short" })}
                  </div>
                  <div className="text-sm font-semibold tabular-nums">{dt.getDate()}</div>
                  <div className="truncate text-[10px]">
                    {c.state === "booked"
                      ? c.arrives
                        ? t("Arrives")
                        : t("Booked")
                      : c.state === "blocked"
                        ? t("Held")
                        : t("Free")}
                  </div>
                </div>
              )
            })}
          </div>
          <div className="mt-3 flex flex-wrap gap-3 text-xs text-zinc-500">
            <span className="inline-flex items-center gap-1">
              <span className="size-3 rounded bg-brand-700" /> {t("Booked")}
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="size-3 rounded border border-rose-300 bg-rose-100" /> {t("Held / out of service")}
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="size-3 rounded border border-zinc-300 bg-white" /> {t("Free")}
            </span>
          </div>
          {stays.length > 0 && (
            <Section title={t("Bookings in this period")}>
              <ul className="divide-y divide-zinc-100">
                {stays.map((c) => {
                  const nights = a.cells.filter((x) => x.reservation === c.reservation).length
                  return (
                    <li key={c.reservation} className="flex items-center justify-between gap-2 py-2 text-sm">
                      <span className="min-w-0 truncate font-medium">{c.guest_name}</span>
                      <span className="shrink-0 text-zinc-500">
                        {t("from {date}", { date: day(c.date) })} · {t(c.status ?? "")} ·{" "}
                        {t("{n} nights shown", { n: nights })}
                      </span>
                    </li>
                  )
                })}
              </ul>
            </Section>
          )}
        </>
      )}
    </div>
  )
}

// --- History ------------------------------------------------------------------

function HistoryTab({ room }: { room: string }) {
  const { t, tn } = useT()
  const { day, when } = useDates()
  const [h, setH] = useState<RoomHistory | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    getRoomHistory(room)
      .then(setH)
      .catch((e) => setError(serverError(e)))
  }, [room])
  if (error) return <p className="text-sm text-rose-700">{error}</p>
  if (!h) return <Empty>{t("Loading…")}</Empty>
  return (
    <div>
      <Section title={t("Who stayed here")}>
        {h.stays.length === 0 ? (
          <Empty>{t("No stays recorded in this room yet.")}</Empty>
        ) : (
          <ul className="divide-y divide-zinc-100">
            {h.stays.map((s) => (
              <li key={s.name} className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1 py-2.5">
                <div className="min-w-0">
                  <div className="truncate font-medium text-zinc-800">{s.guest_name}</div>
                  <div className="text-xs text-zinc-500">
                    {t("{from} to {to}", { from: day(s.check_in_date), to: day(s.check_out_date) })}
                    {" · "}
                    {tn(s.nights, "{n} night", "{n} nights")}
                    {s.status === "Checked In" && ` · ${t("in house")}`}
                  </div>
                  {s.room_assigned_by_name && (
                    <div className="text-xs text-zinc-400">
                      {t("Room given by {who}", { who: s.room_assigned_by_name })}
                    </div>
                  )}
                </div>
                {s.revenue !== undefined && (
                  <div className="shrink-0 text-end">
                    <div className="tabular-nums text-sm font-semibold text-zinc-800">
                      {fmtMoney(s.revenue)}
                    </div>
                    <div className="text-[11px] text-zinc-400">
                      {s.revenue_source === "posted" ? t("room revenue") : t("booked, not posted yet")}
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title={t("Who cleaned it")}>
        {h.housekeeping.length === 0 ? (
          <Empty>{t("No housekeeping work recorded yet.")}</Empty>
        ) : (
          <ul className="divide-y divide-zinc-100">
            {h.housekeeping.map((x) => (
              <li key={x.task} className="py-2.5 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-zinc-800">{t(x.type)}</span>
                  <Badge
                    tone={
                      x.status === "Verified" ? "sky" : x.status === "Done" ? "green" : "zinc"
                    }
                  >
                    {t(x.status)}
                  </Badge>
                  {x.minutes !== null && (
                    <span className="text-xs text-zinc-500">
                      {t("{n} min", { n: Math.round(x.minutes) })}
                    </span>
                  )}
                </div>
                <div className="mt-0.5 text-xs text-zinc-500">
                  {x.cleaned_by
                    ? t("Cleaned by {who}, {when}", { who: x.cleaned_by, when: when(x.cleaned_at) })
                    : x.assigned_to
                      ? t("Assigned to {who}", { who: x.assigned_to })
                      : t("Not assigned")}
                  {x.inspected_by &&
                    ` · ${t("Inspected by {who}, {when}", { who: x.inspected_by, when: when(x.inspected_at) })}`}
                </div>
              </li>
            ))}
          </ul>
        )}
        {h.status_changes.length > 0 && (
          <details className="mt-2">
            <summary className="cursor-pointer text-sm font-medium text-brand-700">
              {t("Status changes ({n})", { n: h.status_changes.length })}
            </summary>
            <ul className="mt-1 space-y-1 text-xs text-zinc-600">
              {h.status_changes.map((x, i) => (
                <li key={i}>
                  <span dir="ltr">{x.change}</span> · {x.by} · {when(x.at)}
                </li>
              ))}
            </ul>
          </details>
        )}
      </Section>

      <Section title={t("Maintenance and service tickets")}>
        {h.tickets.length === 0 ? (
          <Empty>{t("No tickets for this room.")}</Empty>
        ) : (
          <ul className="divide-y divide-zinc-100">
            {h.tickets.map((x) => (
              <li key={x.name} className="py-2.5 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-zinc-800">{x.subject}</span>
                  <Badge
                    tone={
                      x.status === "Resolved" || x.status === "Closed"
                        ? "green"
                        : x.status === "Cancelled"
                          ? "zinc"
                          : "amber"
                    }
                  >
                    {t(x.status)}
                  </Badge>
                </div>
                <div className="text-xs text-zinc-500">
                  {t(x.category)} · {when(x.creation)}
                  {x.assigned_to && ` · ${x.assigned_to}`}
                  {x.resolved_on && ` · ${t("resolved {when}", { when: when(x.resolved_on) })}`}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title={t("Room moves")}>
        {h.moves.length === 0 ? (
          <Empty>{t("No guest was moved into or out of this room.")}</Empty>
        ) : (
          <ul className="divide-y divide-zinc-100">
            {h.moves.map((m, i) => (
              <li key={i} className="py-2.5 text-sm">
                <div className="font-medium text-zinc-800">
                  {m.direction === "in"
                    ? t("{guest} moved in from room {room}", {
                        guest: m.guest_name ?? m.reservation,
                        room: m.other_room_number ?? "-",
                      })
                    : t("{guest} moved out to room {room}", {
                        guest: m.guest_name ?? m.reservation,
                        room: m.other_room_number ?? "-",
                      })}
                </div>
                <div className="text-xs text-zinc-500">
                  {t("by {who}, {when}", { who: m.by, when: when(m.at) })}
                  {m.note && ` · ${m.note}`}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  )
}

// --- Details ------------------------------------------------------------------

function DetailsTab({ d }: { d: RoomDetail }) {
  const { t } = useT()
  const rt = d.room_type
  const [cleanPhotos, setCleanPhotos] = useState<string[] | null>(null)
  useEffect(() => {
    call<string[]>("kamra.api.hk_room_media", { room: d.room.name })
      .then(setCleanPhotos)
      .catch(() => setCleanPhotos([]))
  }, [d.room.name])
  const yes = (v?: number) => (v ? t("Yes") : t("No"))
  const rows: [string, React.ReactNode][] = [
    [t("Room type"), rt.room_type_name ?? d.room.room_type_name],
    [t("Category"), rt.room_category ? t(rt.room_category) : null],
    [t("Floor"), d.room.floor],
    [t("Bed"), rt.bed_type ? t(rt.bed_type) : null],
    [t("View"), rt.room_view],
    [t("Air conditioning"), rt.air_conditioning ? t(rt.air_conditioning) : null],
    [t("Bathroom"), rt.bathroom ? t(rt.bathroom) : null],
    [t("Kitchen"), rt.kitchen !== undefined ? yes(rt.kitchen) : null],
    [t("Smoking"), rt.smoking_allowed !== undefined ? yes(rt.smoking_allowed) : null],
    [
      t("Sleeps"),
      rt.adults_capacity
        ? t("{a} adults, {c} children", {
            a: rt.adults_capacity,
            c: rt.children_capacity ?? 0,
          })
        : null,
    ],
    [t("Extra beds"), rt.max_extra_beds ? String(rt.max_extra_beds) : null],
  ]
  const amenities = (rt.amenities ?? "")
    .split(/[,\n]/)
    .map((s) => s.trim())
    .filter(Boolean)
  return (
    <div>
      <Section title={t("About this room")}>
        <dl className="grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
          {rows
            .filter(([, v]) => v !== null && v !== undefined && v !== "")
            .map(([k, v]) => (
              <div key={k} className="flex justify-between gap-3 border-b border-zinc-100 pb-1.5">
                <dt className="text-zinc-500">{k}</dt>
                <dd className="text-end font-medium text-zinc-800">{v}</dd>
              </div>
            ))}
        </dl>
        {rt.description && <p className="mt-3 text-sm text-zinc-600">{rt.description}</p>}
      </Section>
      {amenities.length > 0 && (
        <Section title={t("Amenities")}>
          <div className="flex flex-wrap gap-1.5">
            {amenities.map((a) => (
              <Badge key={a} tone="zinc">
                {a}
              </Badge>
            ))}
          </div>
        </Section>
      )}
      <Section title={t("Photos")}>
        {d.photos.length === 0 ? (
          <Empty>{t("No photos of this room type yet.")}</Empty>
        ) : (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {d.photos.map((u) => (
              <img
                key={u}
                src={u}
                alt={rt.room_type_name ?? ""}
                className="aspect-[4/3] w-full rounded-lg object-cover"
              />
            ))}
          </div>
        )}
      </Section>
      <Section title={t("Latest cleaning photos")}>
        {cleanPhotos === null ? (
          <Empty>{t("Loading…")}</Empty>
        ) : (
          <HkMediaView urls={cleanPhotos} empty={t("No cleaning photos for this room yet.")} />
        )}
      </Section>
      <Section title={t("Notes")}>
        {d.room.notes ? (
          <p className="whitespace-pre-line text-sm text-zinc-700">{d.room.notes}</p>
        ) : (
          <Empty>{t("No notes on this room.")}</Empty>
        )}
      </Section>
    </div>
  )
}
