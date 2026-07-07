import { Fragment, useEffect, useState } from "react"
import {
  BadgePercent,
  BedDouble,
  Briefcase,
  Building2,
  CalendarDays,
  ChevronDown,
  Clock,
  Landmark,
  PackageSearch,
  PartyPopper,
  ClipboardList,
  Home,
  IndianRupee,
  LayoutGrid,
  ListChecks,
  Moon,
  Plus,
  Receipt,
  ScrollText,
  Search,
  Settings as SettingsIcon,
  Code2,
  ExternalLink,
  UserCog,
  Sparkles,
  Sun,
  ShieldCheck,
  Tags,
  Ticket,
  Users,
  UtensilsCrossed,
} from "lucide-react"
import { NavLink, Outlet } from "react-router-dom"
import { BookingDialog } from "./components/BookingDialog"
import { CommandPalette } from "./components/CommandPalette"
import HelpPanel from "./components/HelpPanel"
import { Button } from "./components/ui/button"
import {
  getCurrentProperty,
  myProperties,
  setCurrentProperty,
  type PropertyRow,
} from "./lib/api"
import { asset } from "./lib/asset"
import { useAuth } from "./lib/auth"
import { subscribeRealtime } from "./lib/realtime"
import { getTheme, setTheme } from "./lib/theme"
import { cn } from "./lib/utils"

export interface BookingInitial {
  room_type?: string
  date?: string
  guest?: string
  guest_name?: string
  phone?: string
  stays?: number
}

export interface ShellContext {
  refreshKey: number
  openBooking: (initial: BookingInitial) => void
}

interface NavItem {
  to?: string
  href?: string // external link (e.g. the Frappe Desk), opens in a new tab
  label: string
  icon: React.ComponentType<{ className?: string }>
  roles?: string[] // optional per-item gate (in addition to the group's)
}

interface NavGroup {
  label: string
  roles: string[] // any of these roles can see the group
  items: NavItem[]
  // Configuration/admin groups - the once-in-a-while stuff. Tucked under a
  // collapsible "Setup" section (collapsed by default), the way Frappe keeps
  // day-to-day workspaces up top and masters/settings out of the way.
  setup?: boolean
}

/* Day-to-day work stays visible up top (desk → ops → money → events); the
   configuration and admin that you touch once in a while is collapsed under
   Setup. */
const NAV: NavGroup[] = [
  {
    label: "Front Desk",
    roles: ["Front Desk", "Hotel Admin", "System Manager", "Administrator"],
    items: [
      { to: "/", label: "Today", icon: Home },
      { to: "/assistant", label: "Copilot", icon: Sparkles },
      { to: "/reservations", label: "Reservations", icon: ClipboardList },
      { to: "/tape", label: "Tape Chart", icon: LayoutGrid },
      { to: "/calendar", label: "Calendar", icon: CalendarDays },
      { to: "/guests", label: "Guests", icon: Users },
    ],
  },
  {
    label: "Operations",
    roles: ["Front Desk", "Hotel Admin", "System Manager", "Administrator"],
    items: [
      { to: "/housekeeping", label: "Housekeeping", icon: ListChecks },
      { to: "/tickets", label: "Guest Requests", icon: Ticket },
      { to: "/lost-found", label: "Lost & Found", icon: PackageSearch },
      { to: "/shifts", label: "Shifts", icon: Clock },
    ],
  },
  {
    label: "Finance",
    roles: ["Finance", "Hotel Admin", "System Manager", "Administrator"],
    items: [
      { to: "/billing", label: "Billing", icon: Receipt },
      { to: "/reports", label: "Reports", icon: IndianRupee },
      { to: "/companies", label: "Companies", icon: Building2 },
    ],
  },
  {
    label: "Events",
    roles: ["Front Desk", "Revenue Manager", "Hotel Admin", "System Manager", "Administrator"],
    items: [
      { to: "/events", label: "Event Bookings", icon: PartyPopper },
      { to: "/venue-calendar", label: "Venue Calendar", icon: CalendarDays },
      { to: "/groups", label: "Groups & Blocks", icon: Users },
    ],
  },
  // ---- Setup (collapsed by default) ----
  {
    label: "Inventory",
    setup: true,
    roles: ["Front Desk", "Revenue Manager", "Hotel Admin", "System Manager", "Administrator"],
    items: [
      { to: "/rooms", label: "Rooms", icon: BedDouble },
      { to: "/room-types", label: "Room Types", icon: LayoutGrid },
      { to: "/venues", label: "Venues", icon: Landmark },
    ],
  },
  {
    label: "Rates & Offers",
    setup: true,
    roles: ["Revenue Manager", "Hotel Admin", "System Manager", "Administrator"],
    items: [
      { to: "/rate-plans", label: "Rate Plans", icon: Tags },
      { to: "/seasons", label: "Seasons", icon: CalendarDays },
      { to: "/guardrails", label: "Guardrails", icon: ShieldCheck },
      { to: "/vouchers", label: "Vouchers", icon: BadgePercent },
      { to: "/meal-plans", label: "Meal Plans", icon: UtensilsCrossed },
      { to: "/travel-agents", label: "Travel Agents", icon: Briefcase },
    ],
  },
  {
    // GM (Hotel Admin) sees high-level Settings here; the IT-only items below
    // (Developers, New Property, Frappe Desk) are gated to site admins.
    label: "Admin",
    setup: true,
    roles: ["Hotel Admin", "System Manager", "Administrator"],
    items: [
      { to: "/settings", label: "Settings", icon: SettingsIcon },
      { to: "/activity", label: "Activity Log", icon: ScrollText },
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
        // Direct to the User list. Bare /app bounces to the Kamra app (Kamra is
        // registered via add_to_apps_screen), so link a specific Desk route.
        href: import.meta.env.PROD
          ? "/app/user"
          : "http://localhost:8000/app/user",
        label: "Manage Users",
        icon: UserCog,
        roles: ["Administrator", "System Manager"],
      },
      {
        // /app/build is Frappe's default workspace (there is no "home"
        // workspace); bare /app bounces to the Kamra app.
        href: import.meta.env.PROD
          ? "/app/build"
          : "http://localhost:8000/app/build",
        label: "Frappe Desk",
        icon: ExternalLink,
        // The raw admin surface - site admins only, never a business Hotel Admin.
        roles: ["Administrator", "System Manager"],
      },
    ],
  },
]

function SearchShortcut() {
  // One habit to teach: the palette. Mac shows ⌘K, everyone else Ctrl+K.
  const isMac = /Mac|iP(hone|ad|od)/.test(navigator.platform)
  const combo = isMac ? "\u2318K" : "Ctrl+K"
  return (
    <button
      onClick={() => window.dispatchEvent(new Event("kamra:open-palette"))}
      title={`Search: find a guest or booking, or jump anywhere - press ${isMac ? "\u2318 Command" : "Ctrl"} + K`}
      aria-label="Open the Concierge (search and commands)"
      className="flex items-center gap-1.5 rounded-lg border border-zinc-200 px-2.5 py-1.5 text-sm text-zinc-500 hover:bg-zinc-100 hover:text-zinc-700"
    >
      <Search className="size-4" aria-hidden />
      <span className="hidden md:inline">Search</span>
      <kbd className="hidden rounded border border-zinc-200 bg-zinc-50 px-1.5 py-0.5 text-[10px] font-semibold text-zinc-500 md:inline">
        {combo}
      </kbd>
    </button>
  )
}

function ThemeToggle() {
  const [dark, setDark] = useState(() =>
    document.documentElement.classList.contains("dark"),
  )
  return (
    <button
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700"
      onClick={() => {
        setTheme(dark ? "light" : "dark")
        setDark(!dark)
      }}
      title={getTheme() === "system" ? "Theme (system)" : "Theme"}
    >
      {dark ? (
        <Sun className="size-4" aria-hidden />
      ) : (
        <Moon className="size-4" aria-hidden />
      )}
    </button>
  )
}

export default function AppShell() {
  // Auth is centralized; RequireAuth guarantees we only mount when signed in.
  const { user, roles, signOut } = useAuth()
  const [booking, setBooking] = useState<BookingInitial | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const [properties, setProperties] = useState<PropertyRow[]>([])
  const [property, setProperty] = useState(getCurrentProperty())

  useEffect(() => {
    myProperties().then((props) => {
      setProperties(props)
      // if the stored property isn't visible to this user, snap to their first
      if (props.length && !props.some((p) => p.name === getCurrentProperty())) {
        setCurrentProperty(props[0].name)
        setProperty(props[0].name)
      }
    })
  }, [])

  // live updates: any watched change on the server nudges every screen
  useEffect(() => subscribeRealtime(() => setRefreshKey((k) => k + 1)), [])

  function switchProperty(name: string) {
    setCurrentProperty(name)
    setProperty(name)
  }

  // Which Setup groups are expanded - collapsed by default, remembered locally.
  const [openSetup, setOpenSetup] = useState<Set<string>>(() => {
    try {
      return new Set(
        JSON.parse(localStorage.getItem("kamra:nav-setup") || "[]"),
      )
    } catch {
      return new Set()
    }
  })
  function toggleSetup(label: string) {
    setOpenSetup((prev) => {
      const next = new Set(prev)
      if (next.has(label)) next.delete(label)
      else next.add(label)
      localStorage.setItem("kamra:nav-setup", JSON.stringify([...next]))
      return next
    })
  }

  const canSee = (group: NavGroup) =>
    group.roles.some((r) => roles.includes(r))

  const renderItem = (item: NavItem) =>
    item.href ? (
      <a
        key={item.href}
        href={item.href}
        target="_blank"
        rel="noreferrer"
        className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm font-medium text-zinc-600 hover:bg-zinc-100"
      >
        <item.icon className="size-4" aria-hidden />
        {item.label}
      </a>
    ) : (
      <NavLink
        key={item.to}
        to={item.to!}
        end={item.to === "/"}
        className={({ isActive }) =>
          cn(
            "flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm font-medium",
            isActive
              ? "bg-brand-50 text-brand-700"
              : "text-zinc-600 hover:bg-zinc-100",
          )
        }
      >
        <item.icon className="size-4" aria-hidden />
        {item.label}
      </NavLink>
    )

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-52 shrink-0 border-r border-zinc-200 bg-white px-3 py-5 sm:sticky sm:top-0 sm:block sm:h-screen sm:overflow-y-auto">
        <div className="mb-6 flex items-center gap-2 px-2">
          <img src={asset("kamra-mark.svg")} alt="" className="size-7" aria-hidden />
          <span className="text-lg font-semibold tracking-tight">
            kamra
            <span className="ml-1 align-middle text-[10px] font-semibold tracking-[0.2em] text-brand-600">
              PMS
            </span>
          </span>
        </div>
        <nav className="space-y-5">
          {(() => {
            let setupSeen = false
            return NAV.filter(canSee).map((group) => {
              const items = group.items.filter(
                (item) =>
                  !item.roles || item.roles.some((r) => roles.includes(r)),
              )
              if (items.length === 0) return null
              const firstSetup = group.setup && !setupSeen
              if (group.setup) setupSeen = true
              const expanded = openSetup.has(group.label)
              return (
                <Fragment key={group.label}>
                  {firstSetup && (
                    <div className="!mt-6 border-t border-zinc-100 px-2 pb-1 pt-4 text-[10px] font-semibold uppercase tracking-widest text-zinc-300">
                      Setup
                    </div>
                  )}
                  <div className={firstSetup ? "!mt-1" : undefined}>
                    {group.setup ? (
                      <button
                        onClick={() => toggleSetup(group.label)}
                        className="mb-1 flex w-full items-center justify-between rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-widest text-zinc-400 hover:text-zinc-600"
                      >
                        {group.label}
                        <ChevronDown
                          className={cn(
                            "size-3 transition-transform",
                            expanded ? "" : "-rotate-90",
                          )}
                          aria-hidden
                        />
                      </button>
                    ) : (
                      <div className="mb-1 px-2 text-[10px] font-semibold uppercase tracking-widest text-zinc-400">
                        {group.label}
                      </div>
                    )}
                    {(!group.setup || expanded) && items.map(renderItem)}
                  </div>
                </Fragment>
              )
            })
          })()}
        </nav>
      </aside>

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-40 flex items-center gap-3 border-b border-zinc-200 bg-white/90 px-4 py-2.5 backdrop-blur">
          <span className="text-sm text-zinc-500 sm:hidden">kamra</span>
          {properties.length > 1 ? (
            <select
              className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-sm font-medium focus:outline-2 focus:outline-brand-600"
              value={property}
              onChange={(e) => switchProperty(e.target.value)}
              aria-label="Property"
            >
              {properties.map((p) => (
                <option key={p.name} value={p.name}>
                  {p.property_name}
                  {p.city ? ` · ${p.city}` : ""}
                </option>
              ))}
            </select>
          ) : (
            <span className="text-sm font-medium text-zinc-600">
              {properties[0]?.property_name ?? ""}
            </span>
          )}
          <div className="ml-auto flex items-center gap-3">
            <SearchShortcut />
            <ThemeToggle />
            <span className="hidden text-xs text-zinc-500 md:inline">
              {user}
            </span>
            <button
              onClick={signOut}
              className="text-xs font-medium text-zinc-400 hover:text-zinc-700"
            >
              Sign out
            </button>
            <Button onClick={() => setBooking({})}>
              <Plus className="size-4" aria-hidden />
              New booking
            </Button>
          </div>
        </header>

        {/* keyed by property: switching remounts every screen with fresh data */}
        <main key={property} className="mx-auto max-w-6xl px-4 py-6">
          <Outlet
            context={
              {
                refreshKey,
                openBooking: (initial) => setBooking(initial),
              } satisfies ShellContext
            }
          />
        </main>
      </div>

      <HelpPanel />
      <CommandPalette />

      {booking && (
        <BookingDialog
          initial={booking}
          onClose={() => setBooking(null)}
          onBooked={() => setRefreshKey((k) => k + 1)}
        />
      )}

      <span className="hidden">
        {/* icon kept for future rupee stat usage */}
        <IndianRupee className="size-3" aria-hidden />
      </span>
    </div>
  )
}
