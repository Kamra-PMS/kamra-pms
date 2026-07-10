/*  The Kamra app suite. One PMS, several apps - like a workspace suite:
    Front Desk is where the day happens; Housekeeping, Operations, Events,
    Revenue, Finance and Admin are their own rooms. The switcher in the top
    bar and the /apps launcher move between them; Search (Ctrl/Cmd+K) jumps
    anywhere and the sidebar follows.

    Every app is open and included - Kamra is fully open source. */

import {
  BadgePercent,
  BedDouble,
  Briefcase,
  Building2,
  CalendarDays,
  ClipboardList,
  Clock,
  Code2,
  ExternalLink,
  FileSpreadsheet,
  Home,
  IndianRupee,
  Landmark,
  LayoutGrid,
  ListChecks,
  PackageSearch,
  PartyPopper,
  Plus,
  Receipt,
  ScrollText,
  Settings as SettingsIcon,
  Smartphone,
  Sparkles,
  Store,
  Tags,
  Ticket,
  UserCog,
  Users,
  UtensilsCrossed,
  ConciergeBell,
  Brush,
  Wrench,
  TrendingUp,
  ChartLine,
  ShieldCheck,
  Globe,
  Camera,
  HelpCircle,
  Search,
  Lock,
  AlarmClock,
  LayoutDashboard,
} from "lucide-react"

export interface AppNavItem {
  to?: string
  href?: string // external (Frappe Desk, HK mobile app) - opens a new tab
  label: string
  icon: React.ComponentType<{ className?: string }>
  roles?: string[] // per-item gate on top of the app's gate
}

export interface AppDef {
  id: string
  name: string
  icon: React.ComponentType<{ className?: string }>
  tint: string // tile accent classes for switcher/launcher
  description: string
  roles: string[] // any of these roles can see the app
  items: AppNavItem[]
  /** extra route prefixes that belong to this app (detail pages etc.) */
  extraPrefixes?: string[]
}

const DESK = import.meta.env.PROD ? "" : "http://localhost:8000"

export const APPS: AppDef[] = [
  {
    id: "front-desk",
    name: "Front Desk",
    icon: ConciergeBell,
    tint: "bg-brand-50 text-brand-700",
    description: "Arrivals, departures, bookings and guests - the day's work.",
    roles: ["Front Desk", "Hotel Admin", "System Manager", "Administrator"],
    items: [
      { to: "/", label: "Today", icon: Home },
      { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { to: "/assistant", label: "Copilot", icon: Sparkles },
      { to: "/reservations", label: "Reservations", icon: ClipboardList },
      { to: "/crs", label: "Central Reservations", icon: Search },
      { to: "/tape", label: "Tape Chart", icon: LayoutGrid },
      { to: "/calendar", label: "Calendar", icon: CalendarDays },
      { to: "/guests", label: "Guests", icon: Users },
      { to: "/room-blocks", label: "Room Blocks", icon: Lock },
    ],
    extraPrefixes: ["/grc", "/cancelled", "/agents"],
  },
  {
    id: "housekeeping",
    name: "Housekeeping",
    icon: Brush,
    tint: "bg-emerald-50 text-emerald-700",
    description: "Room status board, lost & found, and the phone app.",
    roles: ["Housekeeping", "Front Desk", "Hotel Admin", "System Manager", "Administrator"],
    items: [
      { to: "/housekeeping", label: "Room Board", icon: ListChecks },
      { to: "/lost-found", label: "Lost & Found", icon: PackageSearch },
      { href: "/kamra/hk", label: "Phone App", icon: Smartphone },
    ],
  },
  {
    id: "operations",
    name: "Operations",
    icon: Wrench,
    tint: "bg-sky-50 text-sky-700",
    description: "Guest requests and shift handovers.",
    roles: ["Front Desk", "Hotel Admin", "System Manager", "Administrator"],
    items: [
      { to: "/tickets", label: "Guest Requests", icon: Ticket },
      { to: "/ops-sla", label: "SLA Report", icon: AlarmClock },
      { to: "/shifts", label: "Shifts", icon: Clock },
    ],
  },
  {
    id: "fnb",
    name: "F&B",
    icon: UtensilsCrossed,
    tint: "bg-orange-50 text-orange-700",
    description: "Restaurant POS, kitchen display and the menu.",
    roles: ["Front Desk", "Finance", "Hotel Admin", "System Manager", "Administrator"],
    items: [
      { to: "/pos", label: "Restaurant POS", icon: UtensilsCrossed },
      { to: "/kitchen", label: "Kitchen Display", icon: ConciergeBell },
      { to: "/menu-items", label: "Menu", icon: ClipboardList },
      { to: "/outlets", label: "Outlets", icon: Store },
    ],
  },
  {
    id: "events",
    name: "Events & Groups",
    icon: PartyPopper,
    tint: "bg-violet-50 text-violet-700",
    description: "Banquets, the function diary, room blocks and pickup.",
    roles: ["Front Desk", "Revenue Manager", "Hotel Admin", "System Manager", "Administrator"],
    items: [
      { to: "/events", label: "Event Bookings", icon: PartyPopper },
      { to: "/venue-calendar", label: "Venue Calendar", icon: CalendarDays },
      { to: "/groups", label: "Groups & Blocks", icon: Users },
      { to: "/venues", label: "Venues", icon: Landmark },
    ],
  },
  {
    id: "revenue",
    name: "Revenue",
    icon: TrendingUp,
    tint: "bg-amber-50 text-amber-700",
    description: "Rates, seasons, offers and the partners who sell you.",
    roles: ["Revenue Manager", "Hotel Admin", "System Manager", "Administrator"],
    items: [
      { to: "/revenue-reports", label: "Revenue Reports", icon: ChartLine },
      { to: "/rate-plans", label: "Rate Plans", icon: Tags },
      { to: "/seasons", label: "Seasons", icon: CalendarDays },
      { to: "/guardrails", label: "Guardrails", icon: ShieldCheck },
      { to: "/vouchers", label: "Vouchers", icon: BadgePercent },
      { to: "/meal-plans", label: "Meal Plans", icon: UtensilsCrossed },
      { to: "/travel-agents", label: "Travel Agents", icon: Briefcase },
      { to: "/companies", label: "Companies", icon: Building2 },
    ],
  },
  {
    id: "finance",
    name: "Finance",
    icon: Receipt,
    tint: "bg-teal-50 text-teal-700",
    description: "Folios, invoices, the night audit and reports.",
    roles: ["Finance", "Hotel Admin", "System Manager", "Administrator"],
    items: [
      { to: "/billing", label: "Billing", icon: Receipt },
      { to: "/reports", label: "Reports", icon: IndianRupee },
      { to: "/accounting-export", label: "Accounting Export", icon: FileSpreadsheet },
    ],
    extraPrefixes: ["/billing/"],
  },
  {
    id: "booking-engine",
    name: "Booking Engine",
    icon: Globe,
    tint: "bg-indigo-50 text-indigo-700",
    description: "Manage direct booking setup, property profile, photo gallery, FAQs, and SEO rules.",
    roles: ["Revenue Manager", "Hotel Admin", "System Manager", "Administrator"],
    items: [
      { to: "/booking-settings/profile", label: "Hotel Profile", icon: Home },
      { to: "/booking-settings/amenities", label: "Amenities", icon: ClipboardList },
      { to: "/booking-settings/photos", label: "Photos", icon: Camera },
      { to: "/booking-settings/policies", label: "Policies", icon: ScrollText },
      { to: "/booking-settings/payments", label: "Payments", icon: Receipt },
      { to: "/booking-settings/faq", label: "FAQ", icon: HelpCircle },
      { to: "/booking-settings/seo", label: "SEO", icon: Search },
    ],
    extraPrefixes: ["/booking-settings"],
  },
  {
    id: "admin",
    name: "Admin",
    icon: SettingsIcon,
    tint: "bg-zinc-100 text-zinc-700",
    description: "Property setup, inventory, users, audit and the Marketplace.",
    roles: ["Hotel Admin", "System Manager", "Administrator"],
    items: [
      { to: "/settings", label: "Settings", icon: SettingsIcon },
      { to: "/rooms", label: "Rooms", icon: BedDouble },
      { to: "/room-types", label: "Room Types", icon: LayoutGrid },
      { to: "/activity", label: "Activity Log", icon: ScrollText },
      { to: "/marketplace", label: "Marketplace", icon: Store },
      {
        to: "/developers",
        label: "Developers",
        icon: Code2,
        roles: ["System Manager", "Administrator"],
      },
      {
        to: "/setup",
        label: "New Property",
        icon: Plus,
        roles: ["System Manager", "Administrator"],
      },
      {
        href: `${DESK}/app/user`,
        label: "Manage Users",
        icon: UserCog,
        roles: ["Administrator", "System Manager"],
      },
      {
        href: `${DESK}/app/build`,
        label: "Frappe Desk",
        icon: ExternalLink,
        roles: ["Administrator", "System Manager"],
      },
    ],
  },
]

/** Which app owns a path? Longest matching item route wins; "/" only exact. */
export function appForPath(pathname: string): AppDef {
  let best: { app: AppDef; len: number } | null = null
  for (const app of APPS) {
    const prefixes = [
      ...app.items.filter((i) => i.to).map((i) => i.to!),
      ...(app.extraPrefixes ?? []),
    ]
    for (const p of prefixes) {
      const hit =
        p === "/" ? pathname === "/" : pathname === p || pathname.startsWith(p + "/") || pathname.startsWith(p)
      if (hit && (!best || p.length > best.len))
        best = { app, len: p.length }
    }
  }
  return best?.app ?? APPS[0]
}

export function visibleApps(roles: string[]): AppDef[] {
  return APPS.filter((a) => a.roles.some((r) => roles.includes(r)))
}
