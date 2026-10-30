import { Link, useOutletContext } from "react-router-dom"
import {
  BarChart3,
  BookOpen,
  ChartLine,
  ClipboardCheck,
  FileSpreadsheet,
  FileX2,
  History,
  LayoutDashboard,
  MoonStar,
  ScrollText,
  Smartphone,
  Timer,
  TrendingUp,
  type LucideIcon,
} from "lucide-react"

import { useAuth } from "../lib/auth"
import { visibleApps } from "../lib/apps"
import type { ShellContext } from "../AppShell"
import { useT } from "../lib/i18n"

/** Every report in one place. Each sits in the app that owns it, so the
 *  list only shows what this person's roles and the property's modules
 *  already let them open; the page behind each link checks again. */

interface ReportLink {
  to: string
  label: string
  blurb: string
  icon: LucideIcon
  app?: string
  roles?: string[]
}

const MONEY_ROLES = ["Finance", "Hotel Admin", "System Manager", "Administrator"]
// the report builder's own gate (custom_reports.py), not one app's
const BUILDER_ROLES = [...MONEY_ROLES, "Front Desk", "Revenue Manager", "Night Auditor",
  "Housekeeping", "Housekeeping Supervisor", "F&B Manager"]

// who sees the hotel's figures (kamra.dashboards.owner_snapshot)
const FIGURE_ROLES = [...MONEY_ROLES, "Revenue Manager", "Night Auditor"]

const SECTIONS: { title: string; items: ReportLink[] }[] = [
  {
    title: "Your reports",
    items: [
      { to: "/reports/packs", label: "Department packs", blurb: "Front Office, Housekeeping, F&B, Engineering, Laundry and Hotel Manager — one page each, with week-over-week comparison, emailed weekly.", icon: ClipboardCheck, roles: BUILDER_ROLES },
      { to: "/reports/custom", label: "Custom reports", blurb: "Build a report from arrivals, payments, POS and more; save it, share it, email it on a schedule.", icon: FileSpreadsheet, roles: BUILDER_ROLES },
    ],
  },
  {
    title: "Daily",
    items: [
      { to: "/owner", label: "Owner view", blurb: "Today, yesterday or the month on your phone: revenue, occupancy, money owed, the next 7 days and the last night audits.", icon: Smartphone, roles: FIGURE_ROLES },
      { to: "/reports/flash", label: "Manager flash", blurb: "Occupancy, ADR, RevPAR, revenue and collections for a day, with the month to date.", icon: ChartLine, app: "finance" },
      { to: "/end-of-day", label: "Night audit history", blurb: "Each closed business date and its audit pack.", icon: MoonStar, app: "finance" },
      { to: "/cashier/shift-report", label: "Shift report", blurb: "What each till took, by payment mode.", icon: ScrollText, app: "finance" },
    ],
  },
  {
    title: "Revenue",
    items: [
      { to: "/dashboard", label: "Revenue dashboard", blurb: "Today and month to date by department, or the whole portfolio.", icon: LayoutDashboard, app: "revenue" },
      { to: "/revenue-reports", label: "Revenue reports", blurb: "Pickup, pace, source and segment mix.", icon: TrendingUp, app: "revenue" },
      { to: "/pos-dashboard", label: "F&B dashboard", blurb: "Outlet sales, covers and top items.", icon: BarChart3, app: "fnb" },
      { to: "/banquet-registers", label: "Banquet registers", blurb: "Functions, quotations, enquiries, receipts and sales.", icon: ScrollText, app: "events" },
    ],
  },
  {
    title: "Finance",
    items: [
      { to: "/ledgers", label: "Ledgers", blurb: "Guest, city ledger, deposit and AR aging.", icon: BookOpen, app: "finance" },
      { to: "/folio-history", label: "Folio history", blurb: "Closed bills and invoices.", icon: History, app: "finance" },
      { to: "/voids-allowances", label: "Voids and allowances", blurb: "Every void and allowance, with who and why.", icon: FileX2, app: "finance", roles: MONEY_ROLES },
      { to: "/accounting-export", label: "Accounting export", blurb: "Books for your accounting software.", icon: FileSpreadsheet, app: "finance" },
    ],
  },
  {
    title: "Operations",
    items: [
      { to: "/ops-sla", label: "SLA report", blurb: "Guest requests against their response times.", icon: Timer, app: "operations" },
      { to: "/housekeeping", label: "Housekeeping tasks", blurb: "Open, overdue and finished room tasks.", icon: ClipboardCheck, app: "housekeeping" },
    ],
  },
]

export default function ReportsHub() {
  const { t } = useT()
  const { roles } = useAuth()
  const shell = useOutletContext<ShellContext | undefined>()
  const apps = new Set(visibleApps(roles, shell?.modules).map((a) => a.id))
  const sections = SECTIONS.map((s) => ({
    ...s,
    items: s.items.filter(
      (r) => (!r.app || apps.has(r.app)) && (!r.roles || r.roles.some((x) => roles.includes(x))),
    ),
  })).filter((s) => s.items.length)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-zinc-900">{t("Reports")}</h1>
        <p className="text-xs text-zinc-500">{t("Every report in one place.")}</p>
      </div>
      {sections.length === 0 && (
        <p className="text-sm text-zinc-500">{t("Your role has no reports.")}</p>
      )}
      {sections.map((s) => (
        <section key={s.title}>
          <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-zinc-400">{t(s.title)}</h2>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {s.items.map((r) => (
              <Link
                key={r.to}
                to={r.to}
                className="group flex gap-3 rounded-xl border border-zinc-200 bg-white p-4 shadow-sm transition-colors hover:border-brand-300"
              >
                <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-700">
                  <r.icon className="size-4" aria-hidden />
                </span>
                <span className="min-w-0">
                  <span className="block text-sm font-semibold text-zinc-900 group-hover:text-brand-700">{t(r.label)}</span>
                  <span className="mt-0.5 block text-xs text-zinc-500">{t(r.blurb)}</span>
                </span>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}
