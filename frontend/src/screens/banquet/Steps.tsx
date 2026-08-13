/*  Where this function is, and what's left.

    Flat tabs tell you what screens exist. They don't tell you that the
    quote is unsent, the hall unconfirmed and nothing collected — which is
    the only thing a banquet manager actually wants to know when they open
    a function.

    So the nav is the process, numbered and in order: each step carries a
    tick when it's genuinely done, a live line of what it holds right now,
    and — when it isn't done — the one thing standing in the way. You can
    still jump anywhere; nothing is locked. A step that isn't ready just
    says so instead of pretending. */

import { Check } from "lucide-react"

import type { FunctionSheet } from "../../lib/api"
import { inr } from "./shared"

export type StepId =
  | "enquiry"
  | "quote"
  | "margin"
  | "money"
  | "documents"
  | "close"

export interface Step {
  id: StepId
  n: number
  label: string
  /** What this step holds right now - shown under the label. */
  state: string
  done: boolean
  /** The one thing standing in the way, when it isn't done. */
  blocker?: string
}

/** Read the steps off the function itself, so the nav can never disagree
 *  with the sheet it's describing. */
export function stepsFor(fn: FunctionSheet): Step[] {
  const lines = fn.items.length
  const quoted = (fn.quote_version ?? 0) > 0
  const sold = fn.status === "Confirmed" || fn.status === "Completed"
  const costed = fn.total_cost > 0
  const collected = fn.advance_received > 0
  const paper = Boolean(fn.beo_generated_on)
  const closed = Boolean(fn.closed_out_on)

  return [
    {
      id: "enquiry",
      n: 1,
      label: "Enquiry",
      state: [
        fn.venue?.split("-").pop(),
        fn.session,
        fn.billable_pax ? `${fn.billable_pax} pax` : null,
      ]
        .filter(Boolean)
        .join(" · "),
      done: Boolean(fn.venue && fn.event_date && fn.pax_guaranteed),
      blocker: !fn.pax_guaranteed ? "No guaranteed pax yet" : undefined,
    },
    {
      id: "quote",
      n: 2,
      label: "Quote",
      state: lines
        ? `${lines} line${lines === 1 ? "" : "s"} · ${inr(fn.grand_total)}`
        : "Nothing priced",
      done: lines > 0,
      blocker: !lines ? "Add the menu and the extras" : undefined,
    },
    {
      id: "margin",
      n: 3,
      label: "Margin",
      state: costed
        ? `${fn.margin_percent}% · ${inr(fn.gross_margin)}`
        : "Not costed",
      done: costed,
      blocker: !costed ? "Choose the dishes, or cost the services" : undefined,
    },
    {
      id: "money",
      n: 4,
      label: "Money",
      state: collected
        ? `${inr(fn.advance_received)} in · ${inr(fn.balance_due)} due`
        : fn.payment_terms.length
          ? `${fn.payment_terms.length} milestones · nothing in`
          : "No terms set",
      done: collected,
      blocker: !fn.payment_terms.length
        ? "Set the payment schedule"
        : !collected
          ? "Nothing received yet"
          : undefined,
    },
    {
      id: "documents",
      n: 5,
      label: "Documents",
      state: quoted
        ? `Quote v${fn.quote_version}${paper ? " · event order out" : ""}`
        : "Nothing issued",
      done: quoted,
      blocker: !quoted ? "Stamp the quotation" : undefined,
    },
    {
      id: "close",
      n: 6,
      label: "The night",
      state: closed
        ? "Closed out"
        : sold
          ? fn.pax_actual
            ? `${fn.pax_actual} served`
            : "Not counted yet"
          : "After the function",
      done: closed,
      blocker: !sold ? "Confirm the function first" : undefined,
    },
  ]
}

export function Steps({
  steps,
  current,
  onPick,
}: {
  steps: Step[]
  current: StepId
  onPick: (id: StepId) => void
}) {
  return (
    // A grid, not a scrolling strip: six steps always fit the width they're
    // given, wrapping to two or three rows on a narrow screen rather than
    // hiding the last step off the right edge.
    <nav aria-label="Function progress">
      <ol className="grid grid-cols-2 gap-1 sm:grid-cols-3 lg:grid-cols-6">
        {steps.map((s) => {
          const active = s.id === current
          return (
            <li key={s.id} className="min-w-0">
              <button
                onClick={() => onPick(s.id)}
                aria-current={active ? "step" : undefined}
                className={
                  "group flex h-full w-full flex-col gap-1 rounded-xl border px-3 py-2.5 text-left transition-all " +
                  (active
                    ? "border-brand-600 bg-brand-50/70 ring-1 ring-brand-600/20"
                    : "border-transparent hover:border-zinc-200 hover:bg-zinc-50")
                }
              >
                <span className="flex items-center gap-2">
                  <span
                    className={
                      "flex size-5 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold " +
                      (s.done
                        ? "bg-emerald-600 text-white"
                        : active
                          ? "bg-brand-600 text-white"
                          : "bg-zinc-200 text-zinc-500 group-hover:bg-zinc-300")
                    }
                  >
                    {s.done ? <Check className="size-3" /> : s.n}
                  </span>
                  <span
                    className={
                      "truncate text-sm font-medium " +
                      (active ? "text-brand-800" : "text-zinc-700")
                    }
                  >
                    {s.label}
                  </span>
                </span>
                <span
                  title={s.done ? s.state : (s.blocker ?? s.state)}
                  className={
                    "line-clamp-2 pl-7 text-xs " +
                    (s.done
                      ? "text-zinc-500"
                      : s.blocker
                        ? "text-amber-700"
                        : "text-zinc-400")
                  }
                >
                  {s.done ? s.state : (s.blocker ?? s.state)}
                </span>
              </button>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
