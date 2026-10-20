/*  Room insights: which rooms work hardest, which rarely sell, what each
    earned, how long they were out of service and how long cleans take.
    All numbers come from kamra.rooms.room_insights (server computed). */

import { useEffect, useMemo, useState } from "react"
import { BarChart3, BedDouble, Clock, Wallet, Wrench } from "lucide-react"
import { getRoomInsights, type InsightRoom, type RoomInsights as Data } from "../lib/rooms"
import { serverError } from "../lib/resource"
import { fmtMoney } from "../lib/money"
import { useT } from "../lib/i18n"
import { cn } from "../lib/utils"
import { StatCard } from "./ui/stat-card"
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card"

type SortKey = "nights" | "occupancy_pct" | "revenue" | "out_of_service_nights" | "avg_clean_minutes"

export default function RoomInsights(props: { onOpenRoom: (room: string) => void }) {
  const { t } = useT()
  const [days, setDays] = useState(30)
  const [d, setD] = useState<Data | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sort, setSort] = useState<SortKey>("nights")

  useEffect(() => {
    setD(null)
    getRoomInsights(days)
      .then((x) => {
        setD(x)
        setError(null)
      })
      .catch((e) => setError(serverError(e)))
  }, [days])

  const sorted = useMemo(() => {
    if (!d) return []
    return [...d.rooms].sort((a, b) => {
      const av = (a[sort] ?? -1) as number
      const bv = (b[sort] ?? -1) as number
      return bv - av || a.room_number.localeCompare(b.room_number, undefined, { numeric: true })
    })
  }, [d, sort])

  const cols: { key: SortKey; label: string; show: boolean }[] = [
    { key: "nights", label: t("Nights sold"), show: true },
    { key: "occupancy_pct", label: t("Occupancy"), show: true },
    { key: "revenue", label: t("Room revenue"), show: !!d?.money },
    { key: "out_of_service_nights", label: t("Out of service"), show: true },
    { key: "avg_clean_minutes", label: t("Avg clean"), show: true },
  ]

  return (
    <div className="min-w-0">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {[30, 90].map((n) => (
          <button
            key={n}
            onClick={() => setDays(n)}
            className={cn(
              "min-h-10 rounded-lg border px-3 text-sm font-medium",
              days === n
                ? "border-brand-600 bg-brand-50 text-brand-800"
                : "border-zinc-200 bg-white text-zinc-600",
            )}
          >
            {t("Last {n} days", { n })}
          </button>
        ))}
        {d && (
          <span className="text-sm text-zinc-500">
            {t("{from} to {to}, nights up to last night", { from: d.from_date, to: d.to_date })}
          </span>
        )}
      </div>
      {error && (
        <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}
      {!d ? (
        !error && <p className="text-sm text-zinc-400">{t("Loading…")}</p>
      ) : (
        <>
          <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard
              icon={<BedDouble className="size-4" />}
              label={t("Room nights sold")}
              value={d.summary.room_nights}
              progress={d.summary.occupancy_pct}
              progressLabel={t("{pct}% occupancy", { pct: d.summary.occupancy_pct })}
            />
            {d.money && (
              <StatCard
                icon={<Wallet className="size-4" />}
                label={t("Room revenue (posted)")}
                value={fmtMoney(d.summary.revenue ?? 0)}
              />
            )}
            <StatCard
              icon={<Wrench className="size-4" />}
              label={t("Nights out of service")}
              value={d.summary.out_of_service_nights}
            />
            <StatCard
              icon={<Clock className="size-4" />}
              label={t("Average clean")}
              value={
                d.summary.avg_clean_minutes === null
                  ? "-"
                  : t("{n} min", { n: Math.round(d.summary.avg_clean_minutes) })
              }
              sub={
                d.summary.timed_cleans
                  ? t("from {n} timed cleans", { n: d.summary.timed_cleans })
                  : t("No timed cleans yet")
              }
            />
          </div>
          <div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <TopList
              title={t("Most used rooms")}
              rows={d.most_used}
              onOpen={props.onOpenRoom}
            />
            <TopList
              title={t("Rarely sold rooms")}
              rows={d.least_used}
              onOpen={props.onOpenRoom}
            />
          </div>
          <Card>
            <CardHeader>
              <CardTitle>{t("Every room")}</CardTitle>
              <BarChart3 className="size-4 text-zinc-400" aria-hidden />
            </CardHeader>
            <CardContent>
              <div className="mb-3 flex flex-wrap items-center gap-1.5 text-sm">
                <span className="text-zinc-500">{t("Sort by")}</span>
                {cols
                  .filter((c) => c.show)
                  .map((c) => (
                    <button
                      key={c.key}
                      onClick={() => setSort(c.key)}
                      className={cn(
                        "min-h-9 rounded-md px-2.5 font-medium",
                        sort === c.key ? "bg-brand-50 text-brand-800" : "text-zinc-600 hover:bg-zinc-100",
                      )}
                    >
                      {c.label}
                    </button>
                  ))}
              </div>
              {/* phones: one card per room */}
              <ul className="divide-y divide-zinc-100 md:hidden">
                {sorted.map((r) => (
                  <li key={r.room}>
                    <button
                      className="flex w-full items-center gap-3 py-2.5 text-start"
                      onClick={() => props.onOpenRoom(r.room)}
                    >
                      <span className="w-14 shrink-0 text-base font-semibold">{r.room_number}</span>
                      <span className="min-w-0 flex-1 text-xs text-zinc-500">
                        <span className="block truncate">{r.room_type_name}</span>
                        <span className="block">
                          {t("{n} nights · {pct}%", { n: r.nights, pct: r.occupancy_pct })}
                          {r.out_of_service_nights
                            ? ` · ${t("{n} out of service", { n: r.out_of_service_nights })}`
                            : ""}
                        </span>
                      </span>
                      {d.money && (
                        <span className="shrink-0 tabular-nums text-sm font-medium">
                          {fmtMoney(r.revenue ?? 0)}
                        </span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
              <div className="hidden overflow-x-auto md:block">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-start text-[11px] uppercase tracking-wider text-zinc-400">
                      <th className="pb-2 text-start font-medium">{t("Room")}</th>
                      <th className="pb-2 text-start font-medium">{t("Type")}</th>
                      {cols
                        .filter((c) => c.show)
                        .map((c) => (
                          <th key={c.key} className="pb-2 text-end font-medium">
                            {c.label}
                          </th>
                        ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100">
                    {sorted.map((r) => (
                      <tr
                        key={r.room}
                        className="cursor-pointer hover:bg-zinc-50"
                        onClick={() => props.onOpenRoom(r.room)}
                      >
                        <td className="py-2 font-semibold">{r.room_number}</td>
                        <td className="py-2 text-zinc-600">{r.room_type_name}</td>
                        <td className="py-2 text-end tabular-nums">{r.nights}</td>
                        <td className="py-2 text-end tabular-nums">
                          <OccBar pct={r.occupancy_pct} />
                        </td>
                        {d.money && (
                          <td className="py-2 text-end tabular-nums">{fmtMoney(r.revenue ?? 0)}</td>
                        )}
                        <td className="py-2 text-end tabular-nums">{r.out_of_service_nights}</td>
                        <td className="py-2 text-end tabular-nums text-zinc-600">
                          {r.avg_clean_minutes === null
                            ? "-"
                            : t("{n} min", { n: Math.round(r.avg_clean_minutes) })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}

function OccBar({ pct }: { pct: number }) {
  return (
    <span className="inline-flex items-center justify-end gap-2">
      <span className="hidden h-1.5 w-16 overflow-hidden rounded-full bg-zinc-100 lg:inline-block">
        <span
          className="block h-full rounded-full bg-brand-600"
          style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
        />
      </span>
      {pct}%
    </span>
  )
}

function TopList(props: { title: string; rows: InsightRoom[]; onOpen: (room: string) => void }) {
  const { t } = useT()
  return (
    <Card>
      <CardHeader>
        <CardTitle>{props.title}</CardTitle>
      </CardHeader>
      <CardContent className="pt-2">
        {props.rows.length === 0 ? (
          <p className="text-sm text-zinc-400">{t("No rooms yet.")}</p>
        ) : (
          <ul className="divide-y divide-zinc-100">
            {props.rows.map((r) => (
              <li key={r.room}>
                <button
                  onClick={() => props.onOpen(r.room)}
                  className="flex min-h-11 w-full items-center gap-3 py-2 text-start"
                >
                  <span className="w-14 shrink-0 text-base font-semibold">{r.room_number}</span>
                  <span className="min-w-0 flex-1 truncate text-sm text-zinc-500">
                    {r.room_type_name}
                  </span>
                  <span className="shrink-0 text-sm tabular-nums text-zinc-700">
                    {t("{n} nights · {pct}%", { n: r.nights, pct: r.occupancy_pct })}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}
