import { useCallback, useEffect, useState } from "react"
import {
  BedDouble,
  LogIn,
  LogOut,
  Users,
  Wallet,
  ListChecks,
  PieChart,
  SlidersHorizontal,
} from "lucide-react"
import { Link, useNavigate, useLocation, useOutletContext } from "react-router-dom"
import {
  call,
  getCurrentProperty,
  getSnapshot,
  setHousekeepingStatus,
  type ReservationRow,
  type RoomRow,
  type Snapshot,
} from "../lib/api"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../components/ui/card"
import { StatCard } from "../components/ui/stat-card"
import { Avatar } from "../components/ui/avatar"
import { RoomMediaButton } from "../components/HkMedia"
import { cn } from "../lib/utils"
import type { ShellContext } from "../AppShell"
import CheckInDialog from "../components/CheckInDialog"
import BookingRequests from "../components/BookingRequests"
import { serverError } from "../lib/resource"
import { cur, moneyLocale } from "../lib/money"
import { useT, t as translate, uiDateLocale } from "../lib/i18n"
import CheckOutDialog from "../components/CheckOutDialog"
import RoomDrawer, { type RoomTab } from "../components/RoomDrawer"
import RoomChangeDialog from "../components/RoomChangeDialog"
import CustomizeToday from "../components/CustomizeToday"
import OpenTasksCard from "../components/OpenTasksCard"
import {
  cachedLayout,
  DEFAULT_TODAY_LAYOUT,
  getTodayLayout,
  type TodayLayout,
  type TodayLayoutInfo,
  type WidgetId,
} from "../lib/rooms"


const HK_CYCLE: RoomRow["housekeeping_status"][] = [
  "Dirty",
  "Clean",
  "Inspected",
  "Out of Order",
]

const hkTone: Record<RoomRow["housekeeping_status"], string> = {
  Clean: "border-emerald-300 bg-emerald-50 text-emerald-900",
  Inspected: "border-sky-300 bg-sky-50 text-sky-900",
  Dirty: "border-amber-300 bg-amber-50 text-amber-900",
  "Out of Order": "border-rose-300 bg-rose-50 text-rose-900",
}

const inr0 = (n: number) =>
  Number(n).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })

/** Paid / due / unpaid at a glance - the folio is the source of truth,
 * this chip just saves the trip to Billing. */
function PaymentChip({ row }: { row: ReservationRow }) {
  const { t } = useT()
  const paid = Number(row.paid_total ?? 0)
  const due = Number(row.balance_due ?? 0)
  if (due <= 0 && paid > 0) return <Badge tone="green">{t("Paid")}</Badge>
  if (paid > 0)
    return (
      <Badge tone="amber">
        {cur()}
        {inr0(due)} {t("due")}
      </Badge>
    )
  if (due > 0) return <Badge tone="zinc">{t("Unpaid")}</Badge>
  return null
}

function SourceBadge({ row }: { row: ReservationRow }) {
  const { t } = useT()
  if (row.source === "AI Agent") return <Badge tone="brand">{t("AI Agent")}</Badge>
  if (row.source === "OTA")
    return <Badge tone="indigo">{row.channel || t("OTA")}</Badge>
  return <Badge tone="zinc">{t(row.source)}</Badge>
}

// Illustrative micro-trend for the KPI sparklines until a history endpoint
// lands; the headline value itself is always real.
const mkTrend = (n: number, up = true) =>
  Array.from({ length: 8 }, (_, i) => {
    const b = Math.max(1, Math.abs(n))
    const t = i / 7
    return b * (0.78 + (up ? t : 1 - t) * 0.3 + Math.sin(i * 1.6) * 0.05)
  })

function ReservationList(props: {
  rows: ReservationRow[]
  empty: string
  action: (row: ReservationRow) => React.ReactNode
}) {
  const { t } = useT()
  if (props.rows.length === 0) {
    return <p className="px-1 py-3 text-sm text-zinc-400">{translate(props.empty)}</p>
  }
  return (
    <ul className="divide-y divide-zinc-100">
      {props.rows.map((row) => (
        <li key={row.name} className="flex items-center gap-3 py-2.5">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="truncate text-sm font-medium">
                {row.guest_name}
              </span>
              <SourceBadge row={row} />
              <PaymentChip row={row} />
              {row.precheckin_status === "Submitted" && (
                <Badge tone="green">{t("Pre-checked-in")}</Badge>
              )}
            </div>
            <div className="mt-0.5 text-xs text-zinc-500">
              {row.room
                ? t("Room {n}", { n: row.room.split("-").pop() ?? "" })
                : t("Unassigned")}{" "}
              · {t("{n} night{s}", { n: row.nights, s: row.nights === 1 ? "" : "s" })} ·{" "}
              {t("{n} ad", { n: row.adults })}
              {row.children ? translate(" + {v0} ch", { v0: String(row.children) }) : ""}
              {row.eta && translate(" · ETA {v0}", { v0: String(row.eta) })}
              {row.booked_by_name && (
                <span
                  title={
                    ((row.booked_by_phone
                      ? `${row.booked_by_phone} · `
                      : "") +
                    t("send links & updates to: {pref}", {
                      pref: translate(row.contact_preference ?? "Booker"),
                    }))
                  }
                >
                  {" "}
                  · {t("via {name}", { name: row.booked_by_name })}
                  {row.booker_relation ? ` (${translate(row.booker_relation)})` : ""}
                </span>
              )}
              {row.status === "Confirmed" && (
                <Link
                  to={`/grc/${encodeURIComponent(row.name)}`}
                  className="ml-2 font-medium text-brand-700 hover:underline"
                  onClick={(e) => e.stopPropagation()}
                >
                  {t("GRC")}
                </Link>
              )}
              {row.status === "Confirmed" &&
                row.precheckin_status !== "Submitted" &&
                row.precheckin_token && (
                  <button
                    className="ml-2 font-medium text-brand-700 hover:underline"
                    onClick={(e) => {
                      e.stopPropagation()
                      navigator.clipboard.writeText(
                        `${window.location.origin}/checkin/${row.precheckin_token}`,
                      )
                    }}
                    title={
                      (row.contact_preference === "Booker" && row.booked_by_name
                        ? t("Copy the self check-in link - send to the booker, {name}{phone}", {
                            name: row.booked_by_name,
                            phone: row.booked_by_phone ? ` (${row.booked_by_phone})` : "",
                          })
                        : row.contact_preference === "Both" && row.booked_by_name
                          ? t("Copy the self check-in link - send to the guest and the booker ({name})", {
                              name: row.booked_by_name,
                            })
                          : t("Copy the self check-in link - send to the guest"))
                    }
                  >
                    {t("copy check-in link")}
                  </button>
                )}
            </div>
          </div>
          {props.action(row)}
        </li>
      ))}
    </ul>
  )
}

// Rooms saved without a floor still need a row on the board, or they
// silently vanish from Today. They group under this key.
const NO_FLOOR = "__none__"

function ordinalFloor(
  f: string,
  t: (s: string, vars?: Record<string, string | number>) => string,
  lang: string,
) {
  if (f === NO_FLOOR) return t("Unassigned floor")
  const n = Number(f)
  if (Number.isNaN(n)) return /floor/i.test(f) ? f : t("{f} Floor", { f })
  if (lang === "es") return t("{n} Floor", { n })
  const s = ["th", "st", "nd", "rd"]
  const v = n % 100
  return t("{n}{ord} Floor", { n, ord: s[(v - 20) % 10] || s[v] || s[0] })
}

function relDay(
  dateStr: string,
  t: (s: string, vars?: Record<string, string | number>) => string,
  today?: string,
) {
  const base = today ? new Date(today + "T00:00:00") : new Date()
  const d = Math.round(
    (new Date(dateStr + "T00:00:00").getTime() - base.getTime()) / 86_400_000,
  )
  if (d <= 0) return t("Today")
  if (d === 1) return t("Tomorrow")
  return t("In {n} days", { n: d })
}

function InHouseTable({
  rows,
  today,
}: {
  rows: ReservationRow[]
  today?: string
}) {
  const { t } = useT()
  const navigate = useNavigate()
  if (!rows.length) {
    return (
      <p className="px-1 py-3 text-sm text-zinc-400">
        {t("Nobody is checked in right now.")}
      </p>
    )
  }
  return (
    <>
    {/* phones: one card per guest, nothing to scroll sideways */}
    <ul className="divide-y divide-zinc-100 sm:hidden">
      {rows.map((row) => {
        const due = Number(row.balance_due ?? 0)
        return (
          <li key={row.name}>
            <button
              type="button"
              onClick={() => navigate(`/grc/${row.name}`)}
              className="flex w-full items-center gap-3 py-3 text-start"
            >
              <Avatar name={row.guest_name} />
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium text-zinc-800">{row.guest_name}</span>
                <span className="block text-xs text-zinc-500">
                  {row.room ? t("Room {room}", { room: row.room.split("-").pop() ?? "" }) : t("No room yet")}
                  {" · "}
                  {t("Leaves {when}", { when: relDay(row.check_out_date, t, today) })}
                </span>
              </span>
              {due > 0 ? (
                <span className="shrink-0 tabular-nums text-sm text-amber-700">
                  {cur()}
                  {inr0(due)} {t("Due")}
                </span>
              ) : (
                <span className="shrink-0 tabular-nums text-sm text-zinc-400">{cur()}0</span>
              )}
            </button>
          </li>
        )
      })}
    </ul>
    <div className="hidden overflow-x-auto sm:block">
      <table className="w-full min-w-[560px] text-sm">
        <thead>
          <tr className="text-start text-[11px] font-medium uppercase tracking-wider text-zinc-400">
            <th className="pb-2 ps-1 font-medium">{t("Guest")}</th>
            <th className="pb-2 font-medium">{t("Room")}</th>
            <th className="pb-2 font-medium">{t("Source")}</th>
            <th className="pb-2 font-medium">{t("Balance")}</th>
            <th className="pb-2 font-medium">{t("Stay")}</th>
            <th className="pb-2 pe-1 text-end font-medium">{t("Check-out")}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100">
          {rows.map((row) => {
            const due = Number(row.balance_due ?? 0)
            return (
              <tr
                key={row.name}
                onClick={() => navigate(`/grc/${row.name}`)}
                className="cursor-pointer hover:bg-zinc-50/70"
              >
                <td className="py-2.5 ps-1">
                  <div className="flex items-center gap-2.5">
                    <Avatar name={row.guest_name} />
                    <span className="font-medium text-zinc-800">
                      {row.guest_name}
                    </span>
                  </div>
                </td>
                <td className="py-2.5 tabular-nums text-zinc-600">
                  {row.room ? row.room.split("-").pop() : t("No room yet")}
                </td>
                <td className="py-2.5">
                  <SourceBadge row={row} />
                </td>
                <td className="py-2.5">
                  {due > 0 ? (
                    <span className="inline-flex items-center gap-1.5 tabular-nums text-zinc-700">
                      {cur()}
                      {inr0(due)}
                      <Badge tone="amber">{t("Due")}</Badge>
                    </span>
                  ) : (
                    <span className="tabular-nums text-zinc-400">{cur()}0</span>
                  )}
                </td>
                <td className="py-2.5 text-zinc-500">
                  {t("{n} night{s}", { n: row.nights, s: row.nights === 1 ? "" : "s" })} ·{" "}
                  {t("{n} adult{s}", { n: row.adults, s: row.adults === 1 ? "" : "s" })}
                </td>
                <td className="py-2.5 pe-1 text-end">
                  <div className="tabular-nums text-zinc-600">
                    {row.check_out_date}
                  </div>
                  <div className="text-[11px] text-zinc-400">
                    {relDay(row.check_out_date, t, today)}
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
    </>
  )
}

export default function Today() {
  const { t, lang } = useT()
  const { refreshKey } = useOutletContext<ShellContext>()
  const navigate = useNavigate()
  const [snap, setSnap] = useState<Snapshot | null>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [kpi, setKpi] = useState<any>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [checkingIn, setCheckingIn] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [floor, setFloor] = useState("All")
  // the widget layout: last one seen paints first, the server copy wins
  const [layout, setLayout] = useState<TodayLayout>(
    () => cachedLayout() ?? DEFAULT_TODAY_LAYOUT,
  )
  const [layoutInfo, setLayoutInfo] = useState<TodayLayoutInfo | null>(null)
  const [customizing, setCustomizing] = useState(false)
  useEffect(() => {
    getTodayLayout()
      .then((info) => {
        if (info && info.layout) {
          setLayoutInfo(info)
          setLayout(info.layout)
        }
      })
      .catch(() => {
        /* keep the cached / built-in layout */
      })
  }, [])

  const refresh = useCallback(async () => {
    try {
      const [s, k] = await Promise.all([
        getSnapshot(),
        call("kamra.dashboards.property_dashboard", {
          property: getCurrentProperty(),
        }).catch(() => null),
      ])
      setSnap(s)
      setKpi(k)
      setError(null)
    } catch (e) {
      setError(serverError(e))
    }
  }, [])

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 30_000)
    return () => clearInterval(t)
  }, [refresh, refreshKey])

  // other screens (tape chart, command palette, a group companion) open
  // the check-out sheet here with navigate("/", { state: { checkout } })
  const location = useLocation()
  const [checkingOut, setCheckingOut] = useState<string | null>(null)
  const [roomMenu, setRoomMenu] = useState<string | null>(null)
  // the room panel from the Rooms screen, opened over Today
  const [roomPanel, setRoomPanel] = useState<{ room: string; tab?: RoomTab } | null>(null)
  const [moving, setMoving] = useState<{ res: string; number: string } | null>(null)
  const [panelKey, setPanelKey] = useState(0)
  useEffect(() => {
    const res = (location.state as { checkout?: string } | null)?.checkout
    if (res) {
      setCheckingOut(res)
      // a reload must not reopen it
      navigate(".", { replace: true, state: null })
    }
  }, [location.state, navigate])

  async function act(key: string, fn: () => Promise<unknown>) {
    setBusy(key)
    try {
      await fn()
      await refresh()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(null)
    }
  }

  const occupied = snap?.rooms.filter(
    (r) => r.occupancy_status === "Occupied",
  ).length
  const occupancyPct = snap?.rooms.length
    ? Math.round(((occupied ?? 0) / snap.rooms.length) * 100)
    : 0
  const arrivalsN = snap?.arrivals.length ?? 0
  const departuresN = snap?.departures.length ?? 0
  const inhouseN = snap?.in_house.length ?? 0
  const roomsN = snap?.rooms.length ?? 0
  const revenue = Number(kpi?.revenue_today ?? 0)
  // Today's RevPAR (room revenue / rooms). MTD lives on statistics.revpar.
  const revpar = Number(kpi?.revpar ?? kpi?.statistics?.revpar ?? 0)
  const roomRevenueToday = Number(kpi?.room_revenue_today ?? 0)
  const tasksN = Number(kpi?.housekeeping?.open_tasks ?? 0)
  const overdueN = Number(kpi?.housekeeping?.overdue_tasks ?? 0)
  const allRooms = snap?.rooms ?? []
  const floorOf = (r: RoomRow) => (r.floor || "").trim() || NO_FLOOR
  const floors = Array.from(new Set(allRooms.map(floorOf))).sort((a, b) =>
    a === NO_FLOOR ? 1 : b === NO_FLOOR ? -1 : a.localeCompare(b, undefined, { numeric: true }),
  )
  const shownFloors = floor === "All" ? floors : [floor]
  const renderRoom = (room: RoomRow) => {
    const next =
      HK_CYCLE[
        (HK_CYCLE.indexOf(room.housekeeping_status) + 1) % HK_CYCLE.length
      ]
    const occupied = room.occupancy_status === "Occupied"
    const stay = occupied
      ? (snap?.in_house ?? []).find((r) => r.room === room.name)
      : undefined
    // a guest due in today who already has this room: the tile checks them in
    const arriving = !occupied
      ? (snap?.arrivals ?? []).find((r) => r.room === room.name)
      : undefined
    const hasMenu = !!(stay || arriving)
    const item = "block w-full px-3 py-2.5 text-start hover:bg-zinc-50"
    const openRoom = (tab?: RoomTab) => {
      setRoomMenu(null)
      setRoomPanel({ room: room.name, tab })
    }
    return (
      <div key={room.name} className="relative">
        <button
          title={
            (stay
              ? t("{guest} · check out or open registration", { guest: stay.guest_name })
              : arriving
                ? t("{guest} arrives today · check in", { guest: arriving.guest_name })
                : t("Housekeeping: {from} → {to} (click to advance)", {
                    from: room.housekeeping_status,
                    to: next,
                  }))
          }
          disabled={busy === room.name}
          aria-haspopup={hasMenu ? "menu" : undefined}
          aria-expanded={hasMenu ? roomMenu === room.name : undefined}
          onClick={() =>
            hasMenu
              ? setRoomMenu((m) => (m === room.name ? null : room.name))
              : act(room.name, () => setHousekeepingStatus(room.name, next))
          }
          className={cn(
            "w-full cursor-pointer rounded-lg border px-2 pb-1.5 pt-2 text-start transition-transform",
            "hover:-translate-y-0.5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600",
            occupied
              ? "border-brand-700 bg-brand-700 text-white"
              : hkTone[room.housekeeping_status],
          )}
        >
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold">{room.room_number}</span>
            {occupied && <BedDouble className="size-3.5" aria-hidden />}
            {arriving && <LogIn className="size-3.5" aria-hidden />}
          </div>
          {/* room on the end side for the photo button, so it never covers the label */}
          <div className="mt-0.5 truncate pe-6 text-[9px] font-medium uppercase tracking-wide opacity-80">
            {occupied ? t("Occupied") : arriving ? t("Arriving") : t(room.housekeeping_status)}
          </div>
          {/* ponytail: glance balance; drawer still has full money */}
          {stay?.balance_due != null && Number(stay.balance_due) > 0 && (
            <div className="mt-0.5 truncate pe-6 text-[9px] font-semibold tabular-nums">
              {cur()}
              {inr0(stay.balance_due)} {t("due")}
            </div>
          )}
        </button>
        {(occupied || room.housekeeping_status === "Clean") && (
          <RoomMediaButton room={room.name} />
        )}
        {hasMenu && roomMenu === room.name && (
          <div
            role="menu"
            className="fixed inset-x-4 bottom-4 z-40 overflow-hidden rounded-xl border border-zinc-200 bg-white py-1 text-base shadow-2xl sm:absolute sm:inset-x-auto sm:bottom-auto sm:start-0 sm:top-full sm:z-20 sm:mt-1 sm:w-52 sm:rounded-lg sm:text-sm sm:shadow-lg"
          >
            <p className="truncate px-3 py-1 text-xs text-zinc-500">
              {(stay ?? arriving)!.guest_name}
            </p>
            {stay && (
              <>
                <button
                  role="menuitem"
                  className={cn(item, "font-medium text-zinc-800")}
                  onClick={() => {
                    setRoomMenu(null)
                    setCheckingOut(stay.name)
                  }}
                >
                  {t("Check out")}
                </button>
                <button
                  role="menuitem"
                  className={cn(item, "text-zinc-700")}
                  onClick={() => {
                    setRoomMenu(null)
                    navigate(`/reservations/${stay.name}`)
                  }}
                >
                  {t("Extend stay")}
                </button>
                <button
                  role="menuitem"
                  className={cn(item, "text-zinc-700")}
                  onClick={() => openRoom("billing")}
                >
                  {t("Folio and billing")}
                </button>
                <button
                  role="menuitem"
                  className={cn(item, "text-zinc-700")}
                  onClick={() => openRoom("requests")}
                >
                  {t("Guest requests")}
                </button>
                <button
                  role="menuitem"
                  className={cn(item, "text-zinc-700")}
                  onClick={() => navigate(`/grc/${stay.name}`)}
                >
                  {t("Registration card")}
                </button>
              </>
            )}
            {arriving && (
              <>
                <button
                  role="menuitem"
                  className={cn(item, "font-medium text-zinc-800")}
                  onClick={() => {
                    setRoomMenu(null)
                    setCheckingIn(arriving.name)
                  }}
                >
                  {t("Check in")}
                </button>
                <button
                  role="menuitem"
                  className={cn(item, "text-zinc-700")}
                  onClick={() => {
                    setRoomMenu(null)
                    void act(room.name, () => setHousekeepingStatus(room.name, next))
                  }}
                >
                  {t("Housekeeping: mark {to}", { to: t(next) })}
                </button>
              </>
            )}
            <button
              role="menuitem"
              className={cn(item, "text-zinc-700")}
              onClick={() => openRoom()}
            >
              {t("Room details")}
            </button>
          </div>
        )}
      </div>
    )
  }
  // the old Front Desk dashboard's money row, folded into Today
  const outstanding = Number(kpi?.finance?.outstanding ?? 0)
  const moneyTiles: { label: string; value: string; to: string; tone?: string }[] = [
    { label: t("Collected today"), value: `${cur()}${inr0(Number(kpi?.collections_today ?? 0))}`, to: "/cashier/board" },
    { label: t("Outstanding"), value: `${cur()}${inr0(outstanding)}`, to: "/ledgers", tone: outstanding ? "text-amber-700" : undefined },
    { label: t("Open folios"), value: String(kpi?.finance?.open_folios ?? 0), to: "/billing" },
    { label: t("ADR, month to date"), value: `${cur()}${inr0(Number(kpi?.statistics?.adr ?? 0))}`, to: "/dashboard" },
    { label: t("RevPAR, month to date"), value: `${cur()}${inr0(Number(kpi?.statistics?.revpar ?? 0))}`, to: "/dashboard" },
    { label: t("Occupancy, month to date"), value: `${kpi?.statistics?.mtd_occupancy_pct ?? 0}%`, to: "/reports/flash" },
  ]
  const hkRoom = kpi?.housekeeping?.room_status ?? {}
  const hkStats = [
    { label: t("Clean"), value: hkRoom.Clean ?? 0, dot: "bg-emerald-500" },
    { label: t("Dirty"), value: hkRoom.Dirty ?? 0, dot: "bg-amber-500" },
    { label: t("Inspected"), value: hkRoom.Inspected ?? 0, dot: "bg-sky-500" },
    {
      label: t("Out of Order"),
      value: hkRoom["Out of Order"] ?? 0,
      dot: "bg-rose-500",
    },
  ]
  const hh = new Date().getHours()
  const greeting =
    hh < 12 ? t("Good morning") : hh < 17 ? t("Good afternoon") : t("Good evening")
  const prettyDate = snap?.date
    ? new Date(snap.date + "T00:00:00").toLocaleDateString(uiDateLocale(undefined), {
        weekday: "short",
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : ""

  // Today is a set of widgets; each person picks which show and in what
  // order (Customize). The built-in layout is the classic Today.
  const widgets: Record<WidgetId, React.ReactNode> = {
    kpis: (
      <div className="mb-6 space-y-3">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <StatCard
          icon={<LogIn className="size-4" />}
          label={t("Arrivals")}
          value={arrivalsN}
          spark={mkTrend(arrivalsN)}
          to="/in-house?tab=arrivals"
        />
        <StatCard
          icon={<LogOut className="size-4" />}
          label={t("Departures")}
          value={departuresN}
          spark={mkTrend(departuresN, false)}
          sparkColor="var(--color-amber-600)"
          to="/in-house?tab=departures"
        />
        <StatCard
          icon={<Users className="size-4" />}
          label={t("In-house")}
          value={inhouseN}
          spark={mkTrend(inhouseN)}
          to="/in-house?tab=in-house"
        />
        <StatCard
          icon={<PieChart className="size-4" />}
          label={t("Occupancy")}
          to="/room-board"
          value={`${occupancyPct}%`}
          progress={occupancyPct}
          progressLabel={t("{occupied} of {total} rooms", {
            occupied: occupied ?? 0,
            total: roomsN,
          })}
        />
        <StatCard
          icon={<Wallet className="size-4" />}
          label={t("Revenue")}
          value={`${cur()}${inr0(revenue)}`}
          sub={
            (roomRevenueToday > 0 || revpar > 0
              ? t("RevPAR {amount} · room {room}", {
                  amount: `${cur()}${inr0(revpar)}`,
                  room: `${cur()}${inr0(roomRevenueToday)}`,
                  // keep "room ₹18,480" together if the line has to wrap
                }).replace(/ (\S+)$/, "\u00a0$1")
              : t("RevPAR {amount} · no room charges posted today", {
                  amount: `${cur()}${inr0(revpar)}`,
                }))
          }
          spark={mkTrend(revenue)}
          to="/dashboard"
        />
        <StatCard
          icon={<ListChecks className="size-4" />}
          label={t("Open tasks")}
          value={tasksN}
          sub={
            (overdueN
              ? t("{n} overdue · Housekeeping", { n: overdueN })
              : t("Housekeeping"))
          }
          to={"/housekeeping"}
        />
      </div>
      {kpi && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">
          {moneyTiles.map((m) => (
            <Link
              key={m.label}
              to={m.to}
              className="rounded-lg border border-zinc-200 bg-white px-3 py-2 transition-colors hover:border-brand-300"
            >
              <div className="text-[11px] font-medium text-zinc-500">{m.label}</div>
              <div className={cn("text-sm font-semibold tabular-nums", m.tone ?? "text-zinc-900")}>{m.value}</div>
            </Link>
          ))}
        </div>
      )}
      </div>
    ),
    booking_requests: <BookingRequests refreshKey={refreshKey} onChanged={refresh} />,
    arrivals: (
      <Card>
        <CardHeader>
          <CardTitle>{t("Arrivals")}</CardTitle>
          <Link to="/in-house?tab=arrivals" className="text-xs font-medium text-brand-700 hover:underline">{t("View all")}</Link>
        </CardHeader>
        <CardContent className="pt-1">
          <ReservationList
            rows={snap?.arrivals ?? []}
            empty={t("No arrivals expected today.")}
            action={(row) => (
              <Button
                disabled={busy === row.name}
                onClick={() => setCheckingIn(row.name)}
              >
                {t("Check in")}
              </Button>
            )}
          />
        </CardContent>
      </Card>
    ),
    departures: (
      <Card>
        <CardHeader>
          <CardTitle>{t("Departures")}</CardTitle>
          <Link to="/in-house?tab=departures" className="text-xs font-medium text-brand-700 hover:underline">{t("View all")}</Link>
        </CardHeader>
        <CardContent className="pt-1">
          <ReservationList
            rows={snap?.departures ?? []}
            empty={t("No departures due today.")}
            action={(row) => (
              <Button
                variant="outline"
                disabled={busy === row.name}
                onClick={() => setCheckingOut(row.name)}
              >
                {t("Check out")}
              </Button>
            )}
          />
        </CardContent>
      </Card>
    ),
    room_board: (
      <Card>
        <CardHeader>
          <CardTitle>{t("Room board")}</CardTitle>
          <span className="flex min-w-0 items-center gap-3">
            <span className="hidden truncate text-xs text-zinc-400 sm:inline">
              {t("Click a room to advance its housekeeping status")}
            </span>
            <Link
              to="/room-board"
              className="shrink-0 text-sm font-medium text-brand-700 hover:underline"
            >
              {t("Open full view")}
            </Link>
          </span>
        </CardHeader>
        <CardContent>
          <div className="mb-3 flex flex-wrap gap-1 border-b border-zinc-100">
            {["All", ...floors].map((f) => (
              <button
                key={f}
                onClick={() => setFloor(f)}
                className={cn(
                  "relative px-3 py-1.5 text-sm font-medium",
                  floor === f
                    ? "text-brand-700"
                    : "text-zinc-500 hover:text-zinc-700",
                )}
              >
                {f === "All" ? t("All Floors") : ordinalFloor(f, t, lang)}
                {floor === f && (
                  <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-brand-600" />
                )}
              </button>
            ))}
          </div>
          <div className="space-y-3">
            {shownFloors.map((fl) => (
              <div key={fl} className="flex items-start gap-3">
                <div className="w-16 shrink-0 pt-2 text-xs font-medium text-zinc-500">
                  {ordinalFloor(fl, t, lang)}
                </div>
                <div className="grid flex-1 grid-cols-[repeat(auto-fill,minmax(6.25rem,1fr))] gap-2">
                  {allRooms
                    .filter((r) => floorOf(r) === fl)
                    .map((room) => renderRoom(room))}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-xs text-zinc-500">
            <Badge tone="green">{t("Clean")}</Badge>
            <Badge tone="sky">{t("Inspected")}</Badge>
            <Badge tone="amber">{t("Dirty")}</Badge>
            <Badge tone="rose">{t("Out of Order")}</Badge>
            <span className="inline-flex items-center gap-1">
              <BedDouble className="size-3.5" aria-hidden /> {t("occupied")}
            </span>
          </div>
        </CardContent>
      </Card>
    ),
    in_house: (
      <Card>
        <CardHeader>
          <CardTitle>{t("In-house guests")}</CardTitle>
          <Link to="/in-house?tab=in-house" className="text-xs font-medium text-brand-700 hover:underline">
            {t("{n} staying", { n: inhouseN })}
          </Link>
        </CardHeader>
        <CardContent className="pt-1">
          <InHouseTable rows={snap?.in_house ?? []} today={snap?.date} />
        </CardContent>
      </Card>
    ),
    housekeeping: (
      <Card>
        <CardHeader>
          <CardTitle>{t("Housekeeping")}</CardTitle>
          <span className="text-xs text-zinc-400">
            {t("{pct}% occupied · {occupied} of {total}", {
              pct: occupancyPct,
              occupied: occupied ?? 0,
              total: roomsN,
            })}
          </span>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {hkStats.map((s) => (
              <Link
                to="/housekeeping-board"
                key={s.label}
                className="flex items-center gap-2 rounded-lg border border-zinc-200 px-3 py-2 hover:border-brand-300"
              >
                <span className={cn("size-2 rounded-full", s.dot)} />
                <span className="text-lg font-semibold tabular-nums">
                  {s.value}
                </span>
                <span className="text-xs text-zinc-500">{translate(s.label)}</span>
              </Link>
            ))}
          </div>
        </CardContent>
      </Card>
    ),
    open_tasks: <OpenTasksCard refreshKey={refreshKey} />,
  }
  const activeLayout = layout ?? DEFAULT_TODAY_LAYOUT
  const visible = (ids?: WidgetId[]) => (ids ?? []).filter((id) => !activeLayout.hidden?.includes(id))
  const top = visible(activeLayout.top)
  const left = visible(activeLayout.left)
  const right = visible(activeLayout.right)

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-zinc-900">
            {t("Front Desk Overview")}
          </h1>
          <p className="mt-0.5 text-sm text-zinc-500">
            {greeting}. {t("Here's what's happening today.")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-sm font-medium tabular-nums text-zinc-600">
            {prettyDate}
          </div>
          <Button
            variant="outline"
            disabled={!layoutInfo}
            onClick={() => setCustomizing(true)}
            title={t("Choose what Today shows")}
          >
            <SlidersHorizontal className="size-4" aria-hidden />
            {t("Customize")}
          </Button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">
          {translate(error)}
        </div>
      )}

      {top.map((id) => (
        <div key={id}>{widgets[id]}</div>
      ))}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        {left.length > 0 && (
          <div className={cn("min-w-0 space-y-4", right.length ? "lg:col-span-2" : "lg:col-span-5")}>
            {left.map((id) => (
              <div key={id} className="min-w-0">
                {widgets[id]}
              </div>
            ))}
          </div>
        )}
        {right.length > 0 && (
          <div className={cn("min-w-0 space-y-4", left.length ? "lg:col-span-3" : "lg:col-span-5")}>
            {right.map((id) => (
              <div key={id} className="min-w-0">
                {widgets[id]}
              </div>
            ))}
          </div>
        )}
      </div>
      {customizing && layoutInfo && (
        <CustomizeToday
          info={layoutInfo}
          current={layout}
          onClose={() => setCustomizing(false)}
          onSaved={(info) => {
            setLayoutInfo(info)
            setLayout(info.layout)
          }}
        />
      )}
      {checkingOut && (
        <CheckOutDialog
          reservation={checkingOut}
          onClose={() => setCheckingOut(null)}
          onDone={() => {
            setCheckingOut(null)
            setPanelKey((k) => k + 1)
            void refresh()
          }}
          onOpenReservation={(name) => setCheckingOut(name)}
        />
      )}
      {roomPanel && !checkingOut && !checkingIn && !moving && (
        <RoomDrawer
          room={roomPanel.room}
          initialTab={roomPanel.tab}
          reloadKey={panelKey}
          onClose={() => setRoomPanel(null)}
          onChanged={() => void refresh()}
          onCheckOut={setCheckingOut}
          onCheckIn={setCheckingIn}
          onMove={(res, number) => setMoving({ res, number })}
        />
      )}
      {moving && (
        <RoomChangeDialog
          reservation={moving.res}
          currentRoomNumber={moving.number}
          onClose={() => setMoving(null)}
          onMoved={() => {
            setMoving(null)
            setPanelKey((k) => k + 1)
            void refresh()
          }}
        />
      )}
      {checkingIn && (
        <CheckInDialog
          reservation={checkingIn}
          onClose={() => setCheckingIn(null)}
          onDone={() => {
            setCheckingIn(null)
            setPanelKey((k) => k + 1)
            refresh()
          }}
        />
      )}
    </div>
  )
}
