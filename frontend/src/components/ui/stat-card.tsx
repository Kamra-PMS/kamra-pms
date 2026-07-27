import type { ReactNode } from "react"
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
  className?: string
}) {
  const down = delta?.dir === "down"
  return (
    <div
      className={cn(
        "flex min-w-0 flex-col rounded-xl border border-zinc-200 bg-white p-4",
        className,
      )}
    >
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
          <div className="text-2xl font-semibold tracking-tight text-zinc-900 tabular-nums">
            {value}
          </div>
          {sub ? (
            <div className="mt-0.5 text-xs text-zinc-400">{sub}</div>
          ) : null}
        </div>
        {spark ? (
          <div className="shrink-0">
            <Sparkline data={spark} color={sparkColor} />
          </div>
        ) : null}
      </div>

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
    </div>
  )
}
