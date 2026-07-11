import { useEffect, useRef, useState } from "react"
import {
  IndianRupee,
  LayoutGrid,
  Moon,
  Plus,
  Search,
  Sun,
} from "lucide-react"
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom"
import { BookingDialog } from "./components/BookingDialog"
import { CommandPalette } from "./components/CommandPalette"
import HelpPanel from "./components/HelpPanel"
import { Button } from "./components/ui/button"
import {
  appForPath,
  visibleApps,
  type AppDef,
  type AppNavItem,
} from "./lib/apps"
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
import { t as translate, useT } from "./lib/i18n"
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

function SearchShortcut() {
  const isMac = /Mac|iP(hone|ad|od)/.test(navigator.platform)
  const combo = isMac ? "⌘K" : "Ctrl+K"
  return (
    <button
      onClick={() => window.dispatchEvent(new Event("kamra:open-palette"))}
      title={`Search: find a guest or booking, or jump anywhere - press ${isMac ? "⌘ Command" : "Ctrl"} + K`}
      aria-label="Open search"
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

/** Gmail-style grid: the app switcher popover in the top bar. */
function AppSwitcher({ apps, current }: { apps: AppDef[]; current: AppDef }) {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    window.addEventListener("mousedown", onDown)
    return () => window.removeEventListener("mousedown", onDown)
  }, [open])

  const go = (app: AppDef) => {
    setOpen(false)
    const first = app.items.find((i) => i.to)
    if (first?.to) navigate(first.to)
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label="Switch app"
        title="Switch app"
        className="flex size-9 items-center justify-center rounded-lg text-zinc-500 hover:bg-zinc-100 hover:text-zinc-700"
      >
        <LayoutGrid className="size-5" aria-hidden />
      </button>
      {open && (
        <div className="absolute left-0 top-11 z-50 w-72 rounded-2xl border border-zinc-200 bg-white p-2 shadow-2xl">
          <div className="grid grid-cols-3 gap-1">
            {apps.map((app) => (
              <button
                key={app.id}
                onClick={() => go(app)}
                className={cn(
                  "flex flex-col items-center gap-1.5 rounded-xl px-2 py-3 text-center transition",
                  app.id === current.id ? "bg-zinc-50" : "hover:bg-zinc-50",
                )}
              >
                <span
                  className={cn(
                    "flex size-10 items-center justify-center rounded-xl",
                    app.tint,
                  )}
                >
                  <app.icon className="size-5" aria-hidden />
                </span>
                <span className="text-[11px] font-medium leading-tight text-zinc-700">
                  {translate(app.name)}
                </span>
              </button>
            ))}
          </div>
          <NavLink
            to="/apps"
            onClick={() => setOpen(false)}
            className="mt-1 block rounded-lg px-3 py-2 text-center text-xs font-medium text-zinc-500 hover:bg-zinc-50 hover:text-zinc-700"
          >
            View all apps
          </NavLink>
        </div>
      )}
    </div>
  )
}

export default function AppShell() {
  const { user, roles, signOut } = useAuth()
  const { t } = useT()
  const location = useLocation()
  const [booking, setBooking] = useState<BookingInitial | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const [properties, setProperties] = useState<PropertyRow[]>([])
  const [property, setProperty] = useState(getCurrentProperty())

  useEffect(() => {
    myProperties().then((props) => {
      setProperties(props)
      if (props.length && !props.some((p) => p.name === getCurrentProperty())) {
        setCurrentProperty(props[0].name)
        setProperty(props[0].name)
      }
    })
  }, [])

  useEffect(() => subscribeRealtime(() => setRefreshKey((k) => k + 1)), [])

  function switchProperty(name: string) {
    setCurrentProperty(name)
    setProperty(name)
  }

  const apps = visibleApps(roles)
  // Which app the current route belongs to - falls back to the user's first.
  const routeApp = appForPath(location.pathname)
  const currentApp = apps.some((a) => a.id === routeApp.id) ? routeApp : apps[0]

  const items = (currentApp?.items ?? []).filter(
    (item) => !item.roles || item.roles.some((r) => roles.includes(r)),
  )

  const renderItem = (item: AppNavItem) =>
    item.href ? (
      <a
        key={item.href}
        href={item.href}
        target="_blank"
        rel="noreferrer"
        className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium text-zinc-600 hover:bg-zinc-100"
      >
        <item.icon className="size-4" aria-hidden />
        {t(item.label)}
      </a>
    ) : (
      <NavLink
        key={item.to}
        to={item.to!}
        end={item.to === "/"}
        className={({ isActive }) =>
          cn(
            "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium",
            isActive
              ? "bg-brand-50 text-brand-700"
              : "text-zinc-600 hover:bg-zinc-100",
          )
        }
      >
        <item.icon className="size-4" aria-hidden />
        {t(item.label)}
      </NavLink>
    )

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-52 shrink-0 border-r border-zinc-200 bg-white px-3 py-5 sm:sticky sm:top-0 sm:block sm:h-screen sm:overflow-y-auto">
        <div className="mb-5 flex items-center gap-2 px-1">
          <img src={asset("kamra-mark.svg")} alt="" className="size-7" aria-hidden />
          <span className="text-lg font-semibold tracking-tight">
            kamra
            <span className="ml-1 align-middle text-[10px] font-semibold tracking-[0.2em] text-brand-600">
              PMS
            </span>
          </span>
        </div>

        {currentApp && (
          <div className="mb-2 flex items-center gap-2 rounded-lg px-2 py-1.5">
            <span
              className={cn(
                "flex size-6 items-center justify-center rounded-md",
                currentApp.tint,
              )}
            >
              <currentApp.icon className="size-3.5" aria-hidden />
            </span>
            <span className="text-sm font-semibold text-zinc-800">
              {t(currentApp.name)}
            </span>
          </div>
        )}

        <nav className="space-y-0.5">{items.map(renderItem)}</nav>
      </aside>

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-40 flex items-center gap-2 border-b border-zinc-200 bg-white/90 px-4 py-2.5 backdrop-blur">
          <AppSwitcher apps={apps} current={currentApp ?? apps[0]} />
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
        <IndianRupee className="size-3" aria-hidden />
      </span>
    </div>
  )
}
