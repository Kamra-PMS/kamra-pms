import type { ReactNode } from "react"
import { Link } from "react-router-dom"
import { ArrowUpRight, ArrowDownRight } from "lucide-react"
import { cn } from "../../lib/utils"
import { Sparkline } from "./sparkline"

/**
 * One headline metric in the front-desk KPI strip: a soft-green icon chip,
 * a quiet label, the big number, and either a sparkline or a progress bar,
 * with an optional delta vs. a prior period.
 */
export function StatCard({
  icon,
  label,
  value,
  spark,
  sparkColor,
  progress,
  progressLabel,
  delta,
  sub,
  accent,
  to,
  className,
}: {
  icon: ReactNode
  label: string
  value: ReactNode
  spark?: number[]
  sparkColor?: string
  progress?: number // 0..100
  progressLabel?: string
  delta?: { value: string; dir?: "up" | "down" } // e.g. { value: "20% vs yesterday", dir: "up" }
  sub?: ReactNode
  accent?: boolean
  /** When set, the whole card navigates here (e.g. Open tasks → HK). */
  to?: string
  className?: string
}) {
  const down = delta?.dir === "down"
  const inner = (
    <>
      <div className="flex items-center gap-2">
        <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-700">
          {icon}
        </span>
        <span className="truncate text-[13px] font-medium text-zinc-500">
          {label}
        </span>
      </div>
      <div className="mt-2.5 flex items-end justify-between gap-2">
        <div className="min-w-0">
          <div
            className={cn(
              "text-2xl font-semibold tracking-tight tabular-nums",
              accent ? "text-brand-700" : "text-zinc-900",
            )}
          >
            {value}
          </div>
        </div>
        {spark ? (
          <div className="shrink-0">
            <Sparkline data={spark} color={sparkColor} />
          </div>
        ) : null}
      </div>
      {/* full card width, so it never wraps into a thin column beside the chart */}
      {sub ? <div className="mt-1 text-xs text-zinc-400">{sub}</div> : null}

      {progress !== undefined ? (
        <div className="mt-3">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-100">
            <div
              className="h-full rounded-full bg-brand-600"
              style={{ width: `${Math.max(0, Math.min(100, progress))}%` }}
            />
          </div>
          {progressLabel ? (
            <div className="mt-1 text-xs text-zinc-400">{progressLabel}</div>
          ) : null}
        </div>
      ) : null}

      {delta ? (
        <div
          className={cn(
            "mt-3 flex items-center gap-1 text-xs font-medium",
            down ? "text-rose-600" : "text-emerald-600",
          )}
        >
          {down ? (
            <ArrowDownRight className="size-3.5" />
          ) : (
            <ArrowUpRight className="size-3.5" />
          )}
          <span className="text-zinc-500">{delta.value}</span>
        </div>
      ) : null}
    </>
  )

  const shell = cn(
    "flex min-w-0 flex-col rounded-xl border border-zinc-200 bg-white p-4",
    to && "transition-colors hover:border-brand-300 hover:bg-brand-50/30",
    className,
  )

  if (to) {
    return (
      <Link to={to} className={shell}>
        {inner}
      </Link>
    )
  }
  return <div className={shell}>{inner}</div>
}
