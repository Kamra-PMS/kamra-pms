import { useEffect, useState } from "react"
import {
  BadgePercent,
  BedDouble,
  Briefcase,
  Building2,
  CalendarDays,
  Clock,
  Landmark,
  PackageSearch,
  PartyPopper,
  ClipboardList,
  Home,
  IndianRupee,
  LayoutGrid,
  ListChecks,
  Plus,
  Receipt,
  ShieldCheck,
  Tags,
  Ticket,
  Users,
  UtensilsCrossed,
} from "lucide-react"
import { NavLink, Outlet } from "react-router-dom"
import { BookingDialog } from "./components/BookingDialog"
import { Button } from "./components/ui/button"
import {
  getCurrentProperty,
  isAuthError,
  logout,
  myProperties,
  setCurrentProperty,
  whoami,
  type PropertyRow,
  type WhoAmI,
} from "./lib/api"
import { cn } from "./lib/utils"
import Login from "./screens/Login"

export interface ShellContext {
  refreshKey: number
  openBooking: (initial: { room_type?: string; date?: string }) => void
}

interface NavItem {
  to: string
  label: string
  icon: React.ComponentType<{ className?: string }>
}

interface NavGroup {
  label: string
  roles: string[] // any of these roles can see the group
  items: NavItem[]
}

const NAV: NavGroup[] = [
  {
    label: "Front Desk",
    roles: ["Front Desk", "System Manager", "Administrator"],
    items: [
      { to: "/", label: "Today", icon: Home },
      { to: "/calendar", label: "Calendar", icon: CalendarDays },
      { to: "/reservations", label: "Reservations", icon: ClipboardList },
      { to: "/guests", label: "Guests", icon: Users },
    ],
  },
  {
    label: "Inventory",
    roles: ["Front Desk", "Revenue Manager", "System Manager", "Administrator"],
    items: [
      { to: "/rooms", label: "Rooms", icon: BedDouble },
      { to: "/room-types", label: "Room Types", icon: LayoutGrid },
    ],
  },
  {
    label: "Revenue",
    roles: ["Revenue Manager", "System Manager", "Administrator"],
    items: [
      { to: "/rate-plans", label: "Rate Plans", icon: Tags },
      { to: "/guardrails", label: "Guardrails", icon: ShieldCheck },
      { to: "/seasons", label: "Seasons", icon: CalendarDays },
      { to: "/vouchers", label: "Vouchers", icon: BadgePercent },
      { to: "/meal-plans", label: "Meal Plans", icon: UtensilsCrossed },
      { to: "/travel-agents", label: "Travel Agents", icon: Briefcase },
    ],
  },
  {
    label: "Events",
    roles: ["Front Desk", "Revenue Manager", "System Manager", "Administrator"],
    items: [
      { to: "/events", label: "Event Bookings", icon: PartyPopper },
      { to: "/venues", label: "Venues", icon: Landmark },
    ],
  },
  {
    label: "Finance",
    roles: ["Finance", "System Manager", "Administrator"],
    items: [
      { to: "/billing", label: "Billing", icon: Receipt },
      { to: "/companies", label: "Corporate", icon: Building2 },
    ],
  },
  {
    label: "Admin",
    roles: ["System Manager", "Administrator"],
    items: [{ to: "/setup", label: "New Property", icon: Plus }],
  },
  {
    label: "Ops",
    roles: ["Front Desk", "System Manager", "Administrator"],
    items: [
      { to: "/tickets", label: "Tickets", icon: Ticket },
      { to: "/housekeeping", label: "Housekeeping", icon: ListChecks },
      { to: "/lost-found", label: "Lost & Found", icon: PackageSearch },
      { to: "/shifts", label: "Shifts", icon: Clock },
    ],
  },
]

type AuthState = "loading" | "anon" | WhoAmI

export default function AppShell() {
  const [me, setMe] = useState<AuthState>("loading")
  const [booking, setBooking] = useState<{
    room_type?: string
    date?: string
  } | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const [properties, setProperties] = useState<PropertyRow[]>([])
  const [property, setProperty] = useState(getCurrentProperty())

  const loadMe = () =>
    whoami()
      .then((w) => {
        setMe(w.user === "Guest" ? "anon" : w)
        if (w.user !== "Guest")
          myProperties().then((props) => {
            setProperties(props)
            // if the stored property isn't visible to this user, snap to
            // their first allowed one
            if (props.length && !props.some((p) => p.name === getCurrentProperty())) {
              setCurrentProperty(props[0].name)
              setProperty(props[0].name)
            }
          })
      })
      .catch((e) => setMe(isAuthError(e) ? "anon" : "anon"))

  useEffect(() => {
    loadMe()
  }, [])

  function switchProperty(name: string) {
    setCurrentProperty(name)
    setProperty(name)
  }

  if (me === "loading") {
    return (
      <p className="py-20 text-center text-sm text-zinc-400">Loading…</p>
    )
  }
  if (me === "anon") {
    return <Login onSuccess={loadMe} />
  }

  const canSee = (group: NavGroup) =>
    group.roles.some((r) => me.roles.includes(r))

  async function signOut() {
    await logout().catch(() => undefined)
    setMe("anon")
  }

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-52 shrink-0 border-r border-zinc-200 bg-white px-3 py-5 sm:sticky sm:top-0 sm:block sm:h-screen sm:overflow-y-auto">
        <div className="mb-6 flex items-center gap-2 px-2">
          <img src="/kamra-mark.svg" alt="" className="size-7" aria-hidden />
          <span className="text-lg font-semibold tracking-tight">
            kamra
            <span className="ml-1 align-middle text-[10px] font-semibold tracking-[0.2em] text-brand-600">
              PMS
            </span>
          </span>
        </div>
        <nav className="space-y-5">
          {NAV.filter(canSee).map((group) => (
            <div key={group.label}>
              <div className="mb-1 px-2 text-[10px] font-semibold uppercase tracking-widest text-zinc-400">
                {group.label}
              </div>
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
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
              ))}
            </div>
          ))}
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
            <span className="hidden text-xs text-zinc-500 md:inline">
              {me.full_name}
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
