/*  Vocabulary shared by the banquet screens: how a function's status looks,
    how money and pax are written, and the small form primitives the sheet,
    the diary and the catalogue all reuse. */

import type { ReactNode } from "react"
import type { FunctionStatus } from "../../lib/api"
import { cur, moneyLocale } from "../../lib/money"

export const inr = (n: unknown) =>
  cur() +
  Number(n || 0).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })

/** Money with paise - totals on paper, where rounding would be noticed. */
export const inrExact = (n: unknown) =>
  cur() +
  Number(n || 0).toLocaleString(moneyLocale(), {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })

export const STATUSES: FunctionStatus[] = [
  "Enquiry",
  "Tentative",
  "Confirmed",
  "Completed",
  "Cancelled",
  "Lost",
]

/** Where a status can go next - the same table the server enforces, so the
 *  UI never offers a move that will bounce. */
export const NEXT: Record<FunctionStatus, FunctionStatus[]> = {
  Enquiry: ["Tentative", "Confirmed", "Cancelled", "Lost"],
  Tentative: ["Confirmed", "Enquiry", "Cancelled", "Lost"],
  Confirmed: ["Completed", "Tentative", "Cancelled"],
  Completed: [],
  Cancelled: ["Enquiry"],
  Lost: ["Enquiry"],
}

export const STATUS_TONE: Record<FunctionStatus, string> = {
  Enquiry: "bg-sky-50 text-sky-700 ring-sky-600/20",
  Tentative: "bg-amber-50 text-amber-800 ring-amber-600/20",
  Confirmed: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  Completed: "bg-zinc-100 text-zinc-600 ring-zinc-500/20",
  Cancelled: "bg-rose-50 text-rose-700 ring-rose-600/20",
  Lost: "bg-rose-50 text-rose-700 ring-rose-600/20 line-through",
}

export const ITEM_TYPES = [
  "Venue Rental",
  "Menu",
  "Food & Beverage",
  "Alcohol",
  "Audio Visual",
  "Decor",
  "Entertainment",
  "Furniture & Setup",
  "Staffing",
  "Accommodation",
  "Stationery",
  "Other",
]
export const SERVICE_CATEGORIES = [
  "Audio Visual",
  "Decor",
  "Entertainment",
  "Furniture & Setup",
  "Staffing",
  "Beverage",
  "Alcohol",
  "Accommodation",
  "Stationery",
  "Other",
]
export const UOMS = ["Pax", "Hour", "Day", "Unit", "Lot"]

/** A hall is sold by the session, not by the stopwatch - "Saturday
 *  evening" is the unit a customer asks for. Custom Hours is the escape
 *  hatch for a function that genuinely runs to its own timetable. */
export const SESSIONS = [
  "Morning",
  "Afternoon",
  "Evening",
  "Full Day",
  "Custom Hours",
]
/** The clock behind each session - mirrors SESSION_HOURS on the server so
 *  an availability check made before saving asks about the right window. */
export const SESSION_HOURS: Record<string, [string, string]> = {
  Morning: ["07:00", "12:00"],
  Afternoon: ["12:00", "17:00"],
  Evening: ["18:00", "23:59"],
  "Full Day": ["07:00", "23:59"],
}

export const CATALOGUE_UOMS = [
  "Per Event",
  "Per Hour",
  "Per Day",
  "Per Pax",
  "Per Unit",
]
export const EVENT_TYPES = [
  "Wedding",
  "Reception",
  "Sangeet",
  "Mehendi",
  "Engagement",
  "Conference",
  "Seminar",
  "Training",
  "Product Launch",
  "Birthday",
  "Anniversary",
  "Corporate Offsite",
  "Exhibition",
  "Other",
]
export const SETUP_STYLES = [
  "Theatre",
  "Classroom",
  "U-Shape",
  "Boardroom",
  "Cluster",
  "Round Table",
  "Herringbone",
  "Floating",
  "Custom",
]
export const SOURCES = [
  "Walk-in",
  "Phone",
  "Email",
  "Website",
  "Referral",
  "Travel Agent",
  "Repeat Guest",
  "Social",
  "Other",
]
export const MEAL_PERIODS = [
  "Breakfast",
  "Brunch",
  "Lunch",
  "Hi-Tea",
  "Dinner",
  "All Day",
  "Snacks",
]
export const FOOD_TYPES = ["Veg", "Non-Veg", "Mixed", "Jain", "Vegan"]
export const SERVICE_STYLES = [
  "Buffet",
  "Plated",
  "Family Style",
  "Live Counter",
  "Boxed",
  "Cocktail",
]
export const PAY_MODES = [
  "Cash",
  "Card",
  "UPI",
  "Bank Transfer",
  "Cheque",
  "Other",
]

export const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

export const today = () => new Date().toISOString().slice(0, 10)

export function shiftDate(date: string, by: number) {
  const d = new Date(date + "T00:00:00")
  d.setDate(d.getDate() + by)
  return d.toISOString().slice(0, 10)
}

export const dayName = (d: string) =>
  new Date(d + "T00:00:00").toLocaleDateString("en-US", { weekday: "short" })

export const monthName = (ym: string) =>
  new Date(ym + "-01T00:00:00").toLocaleDateString("en-US", {
    month: "short",
    year: "numeric",
  })

/** Days between today and a date - negative means it has passed. */
export function daysAway(date: string) {
  const a = new Date(today() + "T00:00:00").getTime()
  const b = new Date(date + "T00:00:00").getTime()
  return Math.round((b - a) / 86_400_000)
}

export function StatusPill({
  status,
  className = "",
}: {
  status: FunctionStatus
  className?: string
}) {
  return (
    <span
      className={
        "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium " +
        "ring-1 ring-inset " +
        STATUS_TONE[status] +
        " " +
        className
      }
    >
      {status}
    </span>
  )
}

export function Field({
  label,
  hint,
  children,
  className = "",
}: {
  label: string
  hint?: string
  children: ReactNode
  className?: string
}) {
  return (
    <label className={"block " + className}>
      <span className="mb-1 block text-xs font-medium text-zinc-500">
        {label}
      </span>
      {children}
      {hint && <span className="mt-1 block text-[11px] text-zinc-400">{hint}</span>}
    </label>
  )
}

export function Select({
  value,
  onChange,
  options,
  className = "",
}: {
  value: string
  onChange: (v: string) => void
  options: readonly string[]
  className?: string
}) {
  return (
    <select
      className={inputCls + " " + className}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  )
}

export function Stat({
  label,
  value,
  sub,
  tone = "",
}: {
  label: string
  value: ReactNode
  sub?: ReactNode
  tone?: string
}) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white px-4 py-3">
      <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">
        {label}
      </p>
      <p className={"mt-1 text-xl font-semibold tabular-nums " + tone}>{value}</p>
      {sub && <p className="mt-0.5 text-xs text-zinc-400">{sub}</p>}
    </div>
  )
}

export function ErrorNote({ error }: { error: string | null }) {
  if (!error) return null
  return (
    <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
      {error}
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="py-10 text-center text-sm text-zinc-400">{children}</p>
}
