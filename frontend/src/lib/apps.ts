/*  The Kamra app suite. One PMS, several apps - like a workspace suite:
    Front Desk is where the day happens; Housekeeping, Operations, Events,
    Revenue, Finance and Admin are their own rooms. The switcher in the top
    bar and the /apps launcher move between them; Search (Ctrl/Cmd+K) jumps
    anywhere and the sidebar follows.

    Every app is open and included - Kamra is fully open source. */

import {
  BadgePercent,
  Share2,
  Network,
  MessageCircle,
  PhoneCall,
  BedDouble,
  Briefcase,
  Building2,
  CalendarDays,
  CalendarRange,
  ClipboardCheck,
  ClipboardList,
  Clock,
  Code2,
  ExternalLink,
  FileSpreadsheet,
  HeartPulse,
  Home,
  Landmark,
  LayoutGrid,
  ListChecks,
  ListTodo,
  PackageSearch,
  Boxes,
  Printer,
  Plus,
  Receipt,
  ScrollText,
  Settings as SettingsIcon,
  Shirt,
  Smartphone,
  Sparkles,
  Store,
  Tags,
  Ticket,
  Compass,
  TrendingUp,
  UserCog,
  Users,
  UtensilsCrossed,
  ConciergeBell,
  BarChart3,
  ChartLine,
  ShieldCheck,
  Globe,
  Camera,
  HelpCircle,
  Search,
  Lock,
  LayoutDashboard,
  Wallet,
  BookOpen,
  History,
  Banknote,
  Calculator,
  MoonStar,
  FileUp,
  DoorOpen,
  Hash,
  ListOrdered,
} from "lucide-react"

/** "Night audit" is what most hotels call End of Day; EOD is what they type. */
const EOD_KEYWORDS = ["End of day", "EOD", "Close the day", "Roll the date"]

/** Shared tile treatment for switcher and launcher. One quiet system, not a rainbow. */
export const APP_TILE =
  "border border-zinc-200 bg-zinc-50 text-zinc-700"

export interface AppNavItem {
  to?: string
  href?: string // external (Frappe Desk, HK mobile app) - opens a new tab
  label: string
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>
  roles?: string[] // per-item gate on top of the app's gate
  /** Sidebar section label within an app (e.g. Cashier / Billing / Books). */
  group?: string
  /** Other words search (Ctrl/Cmd+K) finds this page by. */
  keywords?: string[]
  /** Drawn as a highlighted entry in the sidebar (Kamra Agent). */
  featured?: boolean
}

export interface AppDef {
  id: string
  name: string
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>
  /** @deprecated kept for callers; all apps share APP_TILE */
  tint: string
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
    icon: Building2,
    tint: APP_TILE,
    description: "Arrivals, departures, bookings and guests - the day's work.",
    roles: ["Front Desk", "Night Auditor", "Hotel Admin", "System Manager", "Administrator"],
    items: [
      { to: "/", label: "Today", icon: Home },
      { to: "/assistant", label: "Kamra Agent", icon: Sparkles, featured: true,
        keywords: ["AI", "Assistant", "Copilot", "Ask"] },
      { to: "/in-house", label: "In House", icon: BedDouble,
        keywords: ["Arrivals", "Departures", "In-house guests", "Who is in", "Due out"] },
      { to: "/reservations", label: "Reservations", icon: ClipboardList },
      { to: "/tape", label: "Tape Chart", icon: LayoutGrid },
      { to: "/room-board", label: "Rooms", icon: DoorOpen,
        keywords: ["Room board", "Room status", "Out of order", "Room history"] },
      { to: "/guests", label: "Guest History", icon: Users,
        keywords: ["Guests", "Guest profiles", "Past guests"] },
      { to: "/billing", label: "Billing", icon: Receipt,
        keywords: ["Folios", "Bills", "Invoices"] },
      { to: "/end-of-day", label: "Night Audit", icon: MoonStar,
        keywords: EOD_KEYWORDS },
      { to: "/calendar", label: "Calendar", icon: CalendarDays },
      { to: "/crs", label: "Central Reservations", icon: Search },
      { to: "/room-blocks", label: "Room Blocks", icon: Lock },
      { to: "/reports", label: "Reports", icon: ChartLine },
      { to: "/settings/front-desk", label: "Settings", icon: SettingsIcon,
        roles: ["Hotel Admin", "System Manager", "Administrator"] },
    ],
    extraPrefixes: ["/grc", "/cancelled", "/agents"],
  },
  {
    id: "housekeeping",
    name: "Housekeeping",
    icon: ClipboardCheck,
    tint: APP_TILE,
    description: "Room status board, tasks, lost & found, and the phone app.",
    roles: [
      "Housekeeping", "Housekeeping Supervisor", "Front Desk", "Hotel Admin",
      "System Manager", "Administrator",
    ],
    items: [
      // the board is oversight - supervisors and the desk; attendants work
      // from their task list and the phone app
      { to: "/housekeeping-board", label: "Room Board", icon: LayoutGrid,
        roles: ["Housekeeping Supervisor", "Front Desk", "Hotel Admin",
                "System Manager", "Administrator"] },
      { to: "/room-board", label: "Rooms", icon: DoorOpen,
        roles: ["Housekeeping Supervisor", "Front Desk", "Hotel Admin",
                "System Manager", "Administrator"],
        keywords: ["Room history", "Who cleaned", "Room insights"] },
      { to: "/housekeeping", label: "Tasks", icon: ListChecks },
      { to: "/laundry", label: "Laundry", icon: Shirt },
      { to: "/lost-found", label: "Lost & Found", icon: PackageSearch },
      { to: "/reports", label: "Reports", icon: ChartLine },
      { href: "/kamra/hk", label: "Phone App", icon: Smartphone },
      { to: "/settings/housekeeping", label: "Settings", icon: SettingsIcon,
        roles: ["Housekeeping Supervisor", "Hotel Admin", "System Manager", "Administrator"] },
    ],
  },
  {
    id: "operations",
    name: "Operations",
    icon: ListTodo,
    tint: APP_TILE,
    description: "Guest requests and ops workflows.",
    roles: ["Front Desk", "Hotel Admin", "System Manager", "Administrator"],
    items: [
      { to: "/tickets", label: "Guest Requests (Tickets)", icon: Ticket, keywords: ["tickets", "service ticket", "complaint", "sla", "request"] },
      { to: "/whatsapp", label: "WhatsApp", icon: MessageCircle },
      { to: "/channels", label: "Channels", icon: PhoneCall,
        roles: ["Hotel Admin", "System Manager", "Administrator"] },
      { to: "/reports", label: "Reports", icon: ChartLine },
      { to: "/settings/operations", label: "Settings", icon: SettingsIcon,
        roles: ["Hotel Admin", "System Manager", "Administrator"] },
    ],
    extraPrefixes: ["/ops-sla"],
  },
  {
    id: "fnb",
    name: "F&B",
    icon: UtensilsCrossed,
    tint: APP_TILE,
    description: "Restaurant POS, kitchen display, the menu and kitchen stock.",
    roles: ["Front Desk", "Finance", "Hotel Admin", "System Manager", "Administrator"],
    items: [
      { to: "/pos", label: "Restaurant POS", icon: UtensilsCrossed },
      { to: "/pos-dashboard", label: "F&B Dashboard", icon: TrendingUp },
      { to: "/kitchen", label: "Kitchen Display", icon: ConciergeBell },
      { to: "/menu-items", label: "Menu", icon: ClipboardList },
      { to: "/ingredients", label: "Ingredients", icon: Boxes,
        keywords: ["Store cupboard", "UOM", "Recipes", "Stock"] },
      { to: "/inventory", label: "Kitchen Inventory", icon: PackageSearch },
      { to: "/outlets", label: "Outlets", icon: Store },
      { to: "/printers", label: "Printers", icon: Printer,
        keywords: ["Kitchen printers", "KOT", "Print station", "Thermal"] },
      { to: "/settings/fnb", label: "Settings", icon: SettingsIcon,
        roles: ["Finance", "Hotel Admin", "System Manager", "Administrator"] },
    ],
  },
  {
    id: "events",
    name: "Banquets & Groups",
    icon: CalendarRange,
    tint: APP_TILE,
    description:
      "Function prospecting, quotations and event orders - plus room blocks and pickup.",
    roles: ["Front Desk", "Revenue Manager", "Hotel Admin", "System Manager", "Administrator"],
    items: [
      { to: "/banquet", label: "Banquets", icon: CalendarRange },
      { to: "/banquet-month", label: "Month Availability", icon: CalendarRange },
      { to: "/banquet-diary", label: "Function Diary", icon: CalendarDays },
      { to: "/banquet-registers", label: "Registers", icon: ScrollText },
      { to: "/banquet-catalogue", label: "Menus & Services", icon: UtensilsCrossed },
      { to: "/events", label: "All Functions", icon: ListChecks },
      { to: "/groups", label: "Groups & Blocks", icon: Users },
      { to: "/venues", label: "Halls & Venues", icon: Landmark },
      { to: "/settings/events", label: "Settings", icon: SettingsIcon,
        roles: ["Revenue Manager", "Hotel Admin", "System Manager", "Administrator"] },
    ],
    extraPrefixes: ["/banquet"],
  },
  {
    id: "revenue",
    name: "Revenue",
    icon: BarChart3,
    tint: APP_TILE,
    description: "Rates, seasons, offers and the partners who sell you.",
    roles: ["Revenue Manager", "Hotel Admin", "System Manager", "Administrator"],
    items: [
      { to: "/dashboard", label: "Revenue Dashboard", icon: LayoutDashboard,
        keywords: ["Dashboard", "KPIs", "ADR", "RevPAR", "Portfolio"] },
      { to: "/reports", label: "Reports", icon: ChartLine },
      { to: "/channel-manager", label: "Channel Manager", icon: Share2 },
      { to: "/ota-mappings", label: "OTA Room Mappings", icon: Network },
      { to: "/rate-calendar", label: "Rate Calendar", icon: CalendarDays,
        keywords: ["bar", "best available rate", "base rate", "rack rate", "tariff", "pricing", "price by date"] },
      { to: "/rate-plans", label: "Rate Plans", icon: Tags },
      { to: "/seasons", label: "Seasons", icon: CalendarDays },
      { to: "/guardrails", label: "Guardrails", icon: ShieldCheck },
      { to: "/vouchers", label: "Vouchers", icon: BadgePercent },
      { to: "/meal-plans", label: "Meal Plans", icon: UtensilsCrossed },
      { to: "/experiences", label: "Experiences", icon: Compass },
      // also in Admin: Room Types hold the base rates revenue works from
      { to: "/room-types", label: "Room Types", icon: LayoutGrid },
      { to: "/travel-agents", label: "Travel Agents", icon: Briefcase },
      { to: "/companies", label: "Accounts Receivable", icon: Building2,
        keywords: ["Companies", "Corporate accounts", "Credit", "AR"] },
      { to: "/settings/revenue", label: "Settings", icon: SettingsIcon,
        roles: ["Revenue Manager", "Hotel Admin", "System Manager", "Administrator"] },
    ],
    extraPrefixes: ["/revenue-reports"],
  },
  {
    id: "finance",
    name: "Finance",
    icon: Landmark,
    tint: APP_TILE,
    description: "Cashier till, folios, ledgers, night audit and books export.",
    roles: [
      "Finance", "Front Desk", "Night Auditor", "Hotel Admin", "System Manager",
      "Administrator",
    ],
    items: [
      // Cashier
      { to: "/cashier", label: "My Till", icon: Wallet, group: "Cashier" },
      { to: "/cashier/board", label: "All Tills", icon: Landmark, group: "Cashier" },
      { to: "/cashier/sessions", label: "Sessions", icon: Clock, group: "Cashier" },
      { to: "/cashier/petty-cash", label: "Petty Cash", icon: Banknote, group: "Cashier" },
      { to: "/shifts", label: "Shift Handover", icon: Clock, group: "Cashier" },
      { to: "/cashier/fx", label: "Currency Desk", icon: Calculator, group: "Cashier" },
      // Billing
      { to: "/end-of-day", label: "Night Audit", icon: MoonStar, group: "Billing",
        keywords: EOD_KEYWORDS },
      { to: "/billing", label: "Billing", icon: Receipt, group: "Billing" },
      { to: "/folio-history", label: "Folio History", icon: History, group: "Billing" },
      // Books
      { to: "/ledgers", label: "Ledgers", icon: BookOpen, group: "Books" },
      { to: "/transaction-codes", label: "Transaction Codes", icon: Hash, group: "Books",
        keywords: ["Txn codes", "Revenue group", "Chart of accounts"],
        roles: ["Finance", "Hotel Admin", "System Manager", "Administrator"] },
      { to: "/reason-codes", label: "Reason Codes", icon: ListOrdered, group: "Books",
        keywords: ["Void reason", "Refund reason", "Allowance"],
        roles: ["Finance", "Hotel Admin", "System Manager", "Administrator"] },
      { to: "/reports", label: "Reports", icon: ChartLine, group: "Books" },
      { to: "/accounting-export", label: "Accounting Export", icon: FileSpreadsheet, group: "Books" },
      { to: "/settings/finance", label: "Settings", icon: SettingsIcon, group: "Books",
        roles: ["Finance", "Hotel Admin", "System Manager", "Administrator"] },
    ],
    extraPrefixes: [
      "/billing/", "/cashier/", "/ledgers", "/folio-history",
      "/end-of-day", "/night-audit", "/reason-codes", "/transaction-codes",
      "/voids-allowances",
    ],
  },
  {
    id: "booking-engine",
    name: "Booking Engine",
    icon: Globe,
    tint: APP_TILE,
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
      { to: "/settings/booking-engine", label: "Settings", icon: SettingsIcon,
        roles: ["Revenue Manager", "Hotel Admin", "System Manager", "Administrator"] },
    ],
    extraPrefixes: ["/booking-settings"],
  },
  {
    id: "admin",
    name: "Admin",
    icon: SettingsIcon,
    tint: APP_TILE,
    description: "Settings, staff and access, rooms, audit and the Marketplace.",
    roles: ["Hotel Admin", "System Manager", "Administrator"],
    // every other settings page belongs here unless a module app claims it
    extraPrefixes: ["/settings"],
    items: [
      { to: "/settings/general", label: "Settings", icon: SettingsIcon },
      { to: "/health", label: "System Health", icon: HeartPulse },
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
        to: "/go-live",
        label: "Go-live Import",
        icon: FileUp,
      },
      {
        to: "/setup",
        label: "New Property",
        icon: Plus,
        roles: ["System Manager", "Administrator"],
      },
      { to: "/settings/staff", label: "Staff & Access", icon: UserCog },
      { to: "/finish-setup", label: "Finish setup", icon: ListChecks, keywords: ["onboarding", "checklist", "getting started", "setup wizard"] },
      {
        href: `${DESK}/app/build`,
        label: "Frappe Desk",
        icon: ExternalLink,
        roles: ["Administrator", "System Manager"],
      },
    ],
  },
]

/** Which app owns a path? Longest matching item route wins; "/" only exact.
 *  A page listed in two apps (End of Day, Room Types) belongs to
 *  the first one *among* the apps given - pass the user's visible apps so
 *  the page opens inside an app they can actually see. */
export function appForPath(pathname: string, among: AppDef[] = APPS, keep?: string): AppDef {
  const pool = among.length ? among : APPS
  // The app you are in stays put: a page it lists (Rooms from Housekeeping,
  // Reports from Finance) or a drill-in (a folio, a GRC, a guest) opens
  // inside it. Only another app's own menu page switches apps.
  const kept = keep ? pool.find((a) => a.id === keep) : undefined
  if (kept) {
    const owns = (a: AppDef) =>
      [...a.items.filter((i) => i.to).map((i) => i.to!), ...(a.extraPrefixes ?? [])].some(
        (p) => (p === "/" ? pathname === "/" : pathname === p || pathname.startsWith(p.endsWith("/") ? p : p + "/")),
      )
    if (owns(kept)) return kept
    const menuApp = pool.find((a) => a.items.some((i) => i.to === pathname))
    return menuApp ?? kept
  }
  let best: { app: AppDef; len: number } | null = null
  for (const app of pool) {
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

/** The apps this user can reach: their roles must allow it AND the
 *  property must actually run it. Roles alone were never enough - Front
 *  Desk unlocks both F&B and Banquets, so a serviced-apartment operator
 *  had no way to not see them. */
export function visibleApps(roles: string[], modules?: string[]): AppDef[] {
  return APPS.filter(
    (a) =>
      a.roles.some((r) => roles.includes(r)) &&
      (!modules?.length || modules.includes(a.id)),
  )
}
