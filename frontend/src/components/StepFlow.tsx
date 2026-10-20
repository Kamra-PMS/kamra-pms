/*  StepFlow: the one guided-procedure pattern for desk flows (check-out,
    check-in, ...). A stepper header (step names with done / skipped /
    needed / blocked state), the caller's body, and a footer with Back,
    Skip (optional steps only) and Continue.

    Two ways to use it:
    - inside a Sheet: put <StepFlowHeader> at the top of the body and
      <StepFlowFooter> in the Sheet's `footer` prop (the footer stays pinned);
    - standalone: <StepFlow> renders header, body and footer together.

    `useStepFlow(steps)` keeps the current step and moves between the
    visible ones; hidden steps (not needed for this case) are never shown.
    Strings shown here are the caller's, already translated, plus the
    footer labels, which go through t(). Works from phone width up: the
    header scrolls sideways rather than wrapping into a wall of pills. */

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react"
import { Check, Minus, TriangleAlert } from "lucide-react"
import { useT } from "../lib/i18n"
import { cn } from "../lib/utils"
import { Button } from "./ui/button"

export type StepStatus = "todo" | "current" | "done" | "skipped" | "blocked"

export interface FlowStep {
  /** Stable key, e.g. "settle". */
  key: string
  /** Translated label shown in the header. */
  label: string
  /** Done / skipped / blocked; "todo" when omitted. The current step is
   *  drawn as current whatever its status. */
  status?: Exclude<StepStatus, "current">
  /** Optional steps get a Skip button. */
  optional?: boolean
  /** Not needed for this case: left out of the header and navigation. */
  hidden?: boolean
}

/** Current-step state over the visible steps. */
export function useStepFlow(steps: FlowStep[], initial?: string) {
  const visible = useMemo(() => steps.filter((s) => !s.hidden), [steps])
  const [current, setCurrent] = useState<string>(initial ?? visible[0]?.key ?? "")
  // a step that became hidden (its work is done) hands over to the next one
  useEffect(() => {
    if (!visible.length) return
    if (!visible.some((s) => s.key === current)) {
      const order = steps.map((s) => s.key)
      const at = order.indexOf(current)
      const next = visible.find((s) => order.indexOf(s.key) > at) ?? visible[visible.length - 1]
      setCurrent(next.key)
    }
  }, [visible, steps, current])
  const index = Math.max(0, visible.findIndex((s) => s.key === current))
  const next = useCallback(() => {
    const n = visible[index + 1]
    if (n) setCurrent(n.key)
  }, [visible, index])
  const back = useCallback(() => {
    const p = visible[index - 1]
    if (p) setCurrent(p.key)
  }, [visible, index])
  return {
    visible,
    current: visible[index]?.key ?? current,
    step: visible[index] as FlowStep | undefined,
    index,
    isFirst: index === 0,
    isLast: index === visible.length - 1,
    goTo: setCurrent,
    next,
    back,
  }
}

export function StepFlowHeader(props: {
  steps: FlowStep[]
  current: string
  /** Lets the desk jump back to a step; return false to refuse. */
  onSelect?: (key: string) => void
  className?: string
}) {
  const { t } = useT()
  const visible = props.steps.filter((s) => !s.hidden)
  return (
    <nav aria-label={t("Steps")} className={cn("-mx-1 overflow-x-auto pb-1", props.className)}>
      <ol className="flex min-w-max items-center gap-1 px-1">
        {visible.map((s, i) => {
          const isCurrent = s.key === props.current
          const status: StepStatus = isCurrent ? "current" : s.status ?? "todo"
          return (
            <li key={s.key} className="flex items-center gap-1">
              {i > 0 && <span aria-hidden className="h-px w-3 bg-zinc-200 sm:w-5" />}
              <button
                type="button"
                disabled={!props.onSelect}
                onClick={() => props.onSelect?.(s.key)}
                aria-current={isCurrent ? "step" : undefined}
                className={cn(
                  "flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
                  status === "current" && "border-brand-500 bg-brand-50 text-brand-800",
                  status === "done" && "border-emerald-200 bg-emerald-50 text-emerald-800",
                  status === "skipped" && "border-zinc-200 bg-zinc-50 text-zinc-400",
                  status === "blocked" && "border-rose-200 bg-rose-50 text-rose-800",
                  status === "todo" && "border-zinc-200 text-zinc-500",
                )}
              >
                <span
                  aria-hidden
                  className={cn(
                    "flex size-4 items-center justify-center rounded-full text-[10px] font-semibold",
                    status === "current" && "bg-brand-600 text-white",
                    status === "done" && "bg-emerald-500 text-white",
                    status === "skipped" && "bg-zinc-200 text-zinc-500",
                    status === "blocked" && "bg-rose-500 text-white",
                    status === "todo" && "bg-zinc-100 text-zinc-500",
                  )}
                >
                  {status === "done" ? (
                    <Check className="size-3" />
                  ) : status === "skipped" ? (
                    <Minus className="size-3" />
                  ) : status === "blocked" ? (
                    <TriangleAlert className="size-2.5" />
                  ) : (
                    i + 1
                  )}
                </span>
                {s.label}
                <span className="sr-only">
                  {status === "done"
                    ? t("done")
                    : status === "skipped"
                      ? t("skipped")
                      : status === "blocked"
                        ? t("needs attention")
                        : ""}
                </span>
              </button>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

export function StepFlowFooter(props: {
  /** Left-hand slot, e.g. a Cancel button. */
  start?: ReactNode
  /** Shown above the buttons, in red: the last server refusal. */
  error?: string | null
  onBack?: () => void
  /** Only shown when given: pass it for optional steps. */
  onSkip?: () => void
  onContinue?: () => void
  continueLabel?: string
  continueDisabled?: boolean
  /** Why Continue is disabled, shown next to it, so a greyed-out button
   *  never leaves the desk guessing. */
  disabledReason?: string
  busy?: boolean
}) {
  const { t } = useT()
  return (
    <div className="flex w-full flex-col gap-2">
      {props.error ? (
        <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {props.error}
        </p>
      ) : null}
      {props.continueDisabled && props.disabledReason && !props.busy ? (
        <p className="text-end text-xs text-zinc-500" data-testid="disabled-reason">
          {props.disabledReason}
        </p>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        {props.start}
        <div className="ms-auto flex flex-wrap items-center justify-end gap-2">
          {props.onBack && (
            <Button variant="outline" disabled={props.busy} onClick={props.onBack}>
              {t("Back")}
            </Button>
          )}
          {props.onSkip && (
            <Button variant="ghost" disabled={props.busy} onClick={props.onSkip}>
              {t("Skip")}
            </Button>
          )}
          {props.onContinue && (
            <Button disabled={props.busy || props.continueDisabled} onClick={props.onContinue}>
              {props.continueLabel ?? t("Continue")}
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

/** Header, body and footer together, for a surface without its own footer. */
export function StepFlow(
  props: {
    steps: FlowStep[]
    current: string
    onSelect?: (key: string) => void
    children: ReactNode
  } & Parameters<typeof StepFlowFooter>[0],
) {
  const { steps, current, onSelect, children, ...footer } = props
  return (
    <div className="flex flex-col gap-4">
      <StepFlowHeader steps={steps} current={current} onSelect={onSelect} />
      <div>{children}</div>
      <div className="border-t border-zinc-100 pt-3">
        <StepFlowFooter {...footer} />
      </div>
    </div>
  )
}
