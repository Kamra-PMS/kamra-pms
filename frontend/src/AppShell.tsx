import { lazy, Suspense, useEffect, useRef, useState } from "react"
import {
  IndianRupee,
  LayoutGrid,
  Moon,
  Plus,
  Search,
  Sun,
  LogOut,
} from "lucide-react"
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom"
import UpdateNag from "./components/UpdateNag"
import ErrorBoundary from "./components/ErrorBoundary"
import SetupNag from "./components/SetupNag"
import { Button } from "./components/ui/button"
import {
  appForPath,
  visibleApps,
  type AppDef,
  type AppNavItem,
} from "./lib/apps"
import {
  call,
  enabledModules,
  getCurrentProperty,
  myProperties,
  setCurrentProperty,
  type PropertyRow,
} from "./lib/api"
import { asset } from "./lib/asset"
import { useAuth } from "./lib/auth"
import { subscribeRealtime } from "./lib/realtime"
import { getTheme, setTheme } from "./lib/theme"
import { useT } from "./lib/i18n"
import { loadLocale } from "./lib/money"
import { cn } from "./lib/utils"
import { useKiosk } from "./lib/kiosk"
import { getSiteInfo, versionLabel } from "./lib/siteInfo"
import AlertSettings from "./components/AlertSettings"
import NotificationHost from "./components/NotificationHost"


// On-demand UI kept out of the entry chunk: the booking dialog opens on
// request; the palette and help panel load right after the shell paints.
const BookingDialog = lazy(() =>
  import("./components/BookingDialog").then((m) => ({ default: m.BookingDialog })),
)
const CommandPalette = lazy(() =>
  import("./components/CommandPalette").then((m) => ({ default: m.CommandPalette })),
)
const HelpPanel = lazy(() => import("./components/HelpPanel"))

export interface BookingInitial {
  room_type?: string
  /** a specific room (a vacant tape chart cell); used while room_type matches */
  room?: string
  room_number?: string
  date?: string
  guest?: string
  guest_name?: string
  phone?: string
  stays?: number
  adults?: number
  children?: number
  walkIn?: boolean
}

export interface ShellContext {
  refreshKey: number
  canBook: boolean
  openBooking: (initial: BookingInitial) => void
  /** The property's enabled_modules (empty = all; undefined while loading) -
   *  the same filter the sidebar and MCP apply. */
  modules?: string[]
}

// mirrors @require_roles on kamra.api.create_booking / walk_in (admins always pass)
const BOOKING_ROLES = [
  "Front Desk",
  "Kamra Agent",
  "Hotel Admin",
  "System Manager",
  "Administrator",
]

function SearchShortcut() {
  const { t } = useT()
  const isMac = /Mac|iP(hone|ad|od)/.test(navigator.platform)
  const combo = isMac ? "⌘K" : "Ctrl+K"
  return (
    <button
      onClick={() => window.dispatchEvent(new Event("kamra:open-palette"))}
      title={t("Search: find a guest or booking, or jump anywhere - press {combo}", { combo: isMac ? "⌘ Command" : "Ctrl" + " + K" })}
      aria-label={t("Open search")}
      className="flex w-full items-center gap-2 rounded-lg border border-zinc-200 bg-zinc-50/70 px-3 py-2 text-sm text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600"
    >
      <Search className="size-4 shrink-0" aria-hidden />
      <span className="truncate whitespace-nowrap">{t("Search guests, bookings, screens, settings…")}</span>
      <kbd className="ml-auto hidden rounded border border-zinc-200 bg-white px-1.5 py-0.5 text-[10px] font-semibold text-zinc-500 md:inline">
        {combo}
      </kbd>
    </button>
  )
}

function ThemeToggle() {
  const { t } = useT()
  const [dark, setDark] = useState(() =>
    document.documentElement.classList.contains("dark"),
  )
  return (
    <button
      aria-label={(dark ? t("Switch to light mode") : t("Switch to dark mode"))}
      className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700"
      onClick={() => {
        setTheme(dark ? "light" : "dark")
        setDark(!dark)
      }}
      title={(getTheme() === "system" ? t("Theme (system)") : t("Theme"))}
    >
      {dark ? (
        <Sun className="size-4" aria-hidden />
      ) : (
        <Moon className="size-4" aria-hidden />
      )}
    </button>
  )
}

/** App switcher in the top bar: quiet grid, one accent for the current app. */
function AppSwitcher({ apps, current }: { apps: AppDef[]; current: AppDef }) {
  const { t } = useT()
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
    if (first?.to) navigate(first.to, { state: { app: app.id } })
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label={t("Switch app")}
        title={t("Switch app")}
        className="flex size-8 items-center justify-center rounded-md text-zinc-500 hover:bg-zinc-100 hover:text-zinc-800"
      >
        <LayoutGrid className="size-4" strokeWidth={1.75} aria-hidden />
      </button>
      {open && (
        <div className="absolute left-0 top-10 z-50 w-64 rounded-lg border border-zinc-200 bg-white p-1.5 shadow-lg ring-1 ring-black/5">
          <div className="grid grid-cols-3 gap-0.5">
            {apps.map((app) => {
              const active = app.id === current.id
              return (
                <button
                  key={app.id}
                  onClick={() => go(app)}
                  className={cn(
                    "flex flex-col items-center gap-1.5 rounded-md px-1.5 py-2.5 text-center transition-colors",
                    active ? "bg-zinc-100" : "hover:bg-zinc-50",
                  )}
                >
                  <span
                    className={cn(
                      "flex size-9 items-center justify-center rounded-md border",
                      active
                        ? "border-brand-200 bg-brand-50 text-brand-700"
                        : "border-zinc-200 bg-white text-zinc-600",
                    )}
                  >
                    <app.icon className="size-4" strokeWidth={1.75} aria-hidden />
                  </span>
                  <span
                    className={cn(
                      "text-[11px] font-medium leading-tight",
                      active ? "text-zinc-900" : "text-zinc-600",
                    )}
                  >
                    {t(app.name)}
                  </span>
                </button>
              )
            })}
          </div>
          <NavLink
            to="/apps"
            onClick={() => setOpen(false)}
            className="mt-1 block rounded-md px-3 py-2 text-center text-xs font-medium text-zinc-500 hover:bg-zinc-50 hover:text-zinc-800"
          >
            {t("View all apps")}
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
  const navigate = useNavigate()
  const [booking, setBooking] = useState<BookingInitial | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const [properties, setProperties] = useState<PropertyRow[]>([])
  const [property, setProperty] = useState(getCurrentProperty())
  const [demoMode, setDemoMode] = useState(false)
  const [build, setBuild] = useState<string | null>(null)

  useEffect(() => {
    getSiteInfo().then((info) => setBuild(versionLabel(info)))
  }, [])

  useEffect(() => {
    myProperties().then((props) => {
      setProperties(props)
      if (props.length === 0) {
        // Fresh install / Frappe Cloud: force setup wizard, not empty Desk.
        if (
          location.pathname !== "/setup" &&
          !location.pathname.startsWith("/setup/")
        ) {
          navigate("/setup", { replace: true })
        }
        return
      }
      if (!props.some((p) => p.name === getCurrentProperty())) {
        setCurrentProperty(props[0].name)
        setProperty(props[0].name)
      }
    })
    call<{ demo_mode: boolean }>("kamra.public_api.site_info")
      .then((info) => setDemoMode(info.demo_mode))
      .catch(() => setDemoMode(false))
  }, [location.pathname, navigate])

  useEffect(() => subscribeRealtime(() => setRefreshKey((k) => k + 1)), [])

  // currency symbol + number locale follow the property's country pack
  useEffect(() => {
    loadLocale().then(() => setRefreshKey((k) => k + 1))
  }, [property])

  function switchProperty(name: string) {
    setCurrentProperty(name)
    setProperty(name)
  }
  // a screen can switch the property too (the owner view on a phone)
  useEffect(() => {
    const on = (e: Event) => setProperty((e as CustomEvent<string>).detail)
    window.addEventListener("kamra:property", on)
    return () => window.removeEventListener("kamra:property", on)
  }, [])

  // which parts of the product this property runs - undefined until it
  // answers, so nothing flashes in and then disappears
  const [modules, setModules] = useState<string[] | undefined>(undefined)
  useEffect(() => {
    const load = () =>
      enabledModules()
        .then(setModules)
        .catch(() => setModules(undefined))
    load()
    // Settings → Modules switches one on or off without a reload
    window.addEventListener("kamra:modules-changed", load)
    return () => window.removeEventListener("kamra:modules-changed", load)
  }, [property])

  const apps = visibleApps(roles, modules)
  // the app the desk was last in, kept across reloads of a shared page
  const lastApp = useRef<string | undefined>(
    (() => {
      try {
        return sessionStorage.getItem("kamra:app") ?? undefined
      } catch {
        return undefined
      }
    })(),
  )
  // the switcher / launcher / palette name the app they open (state.app)
  const routeApp = appForPath(
    location.pathname, apps,
    (location.state as { app?: string } | null)?.app ?? lastApp.current,
  )
  const currentApp = apps.some((a) => a.id === routeApp.id) ? routeApp : apps[0]
  useEffect(() => {
    if (!currentApp) return
    lastApp.current = currentApp.id
    try {
      sessionStorage.setItem("kamra:app", currentApp.id)
    } catch {
      /* private window: the app still follows the page */
    }
  }, [currentApp])
  const floor = location.pathname === "/pos" || location.pathname === "/kitchen"
  const { on: kiosk } = useKiosk()
  const canBook = BOOKING_ROLES.some((r) => roles.includes(r))

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
        <item.icon className="size-4 shrink-0" aria-hidden />
        <span className="truncate" title={t(item.label)}>{t(item.label)}</span>
      </a>
    ) : item.featured ? (
      <NavLink
        key={item.to}
        to={item.to!}
        className={({ isActive }) =>
          cn(
            "my-1 flex items-center gap-2.5 rounded-lg border px-2 py-1.5 text-sm font-semibold transition-colors",
            isActive
              ? "border-brand-700 bg-brand-600 text-white shadow-sm"
              : "border-brand-100 bg-gradient-to-r from-brand-50 to-white text-brand-800 hover:border-brand-200 hover:from-brand-100",
          )
        }
      >
        {({ isActive }) => (
          <>
            <span className={cn(
              "flex size-6 shrink-0 items-center justify-center rounded-md",
              isActive ? "bg-white/20 text-white" : "bg-brand-600 text-white",
            )}>
              <item.icon className="size-3.5" aria-hidden />
            </span>
            <span className="truncate" title={t(item.label)}>{t(item.label)}</span>
            <span className={cn(
              "ml-auto rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
              isActive ? "bg-white/20 text-white" : "bg-brand-100 text-brand-700",
            )}>{t("AI")}</span>
          </>
        )}
      </NavLink>
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
        <item.icon className="size-4 shrink-0" aria-hidden />
        <span className="truncate" title={t(item.label)}>{t(item.label)}</span>
      </NavLink>
    )

  return (
    // Floor pages (POS / Kitchen) get a bounded frame at lg+ so only pane
    // content scrolls; everything else keeps normal page flow.
    <div className={cn("flex min-h-screen flex-col", floor && "lg:h-screen")}>
      <NotificationHost />
      {demoMode && !kiosk && (
        <div className="bg-amber-500 px-4 py-1.5 text-center text-xs font-medium text-amber-950">
          {t("Shared playground, not your hotel. Data is wiped every night.")}
          {" "}
          <a
            href="https://kamrapms.com"
            className="underline underline-offset-2 hover:text-black"
          >
            {t("Get your own Kamra →")}
          </a>
        </div>
      )}
      {!kiosk && !demoMode && <UpdateNag />}
      {!kiosk && !demoMode && <SetupNag />}
      <div className="flex min-h-0 flex-1">
      {!kiosk && (
      <aside className="hidden w-56 shrink-0 flex-col border-r border-zinc-200 bg-white px-3 py-5 sm:sticky sm:top-0 sm:flex sm:h-screen sm:overflow-y-auto">
        <NavLink
          to="/"
          end
          aria-label={t("Home")}
          className="mb-5 flex items-center gap-2 rounded-lg px-1 outline-none focus-visible:ring-2 focus-visible:ring-brand-600"
        >
          <img src={asset("kamra-mark.svg")} alt="" className="size-7" aria-hidden />
          <span className="text-lg font-semibold tracking-tight text-zinc-900">
            kamra
            <span className="ml-1 align-middle text-[10px] font-semibold tracking-[0.2em] text-brand-600">
              PMS
            </span>
          </span>
        </NavLink>

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

        <nav className="space-y-0.5">
          {(() => {
            const groups: { label?: string; items: typeof items }[] = []
            for (const item of items) {
              const g = item.group
              const last = groups[groups.length - 1]
              if (!last || last.label !== g) {
                groups.push({ label: g, items: [item] })
              } else {
                last.items.push(item)
              }
            }
            return groups.map((g, gi) => (
              <div key={g.label ?? `ungrouped-${gi}`} className={gi > 0 ? "mt-3" : undefined}>
                {g.label ? (
                  <div className="mb-1 px-2.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-400">
                    {t(g.label)}
                  </div>
                ) : null}
                <div className="space-y-0.5">{g.items.map(renderItem)}</div>
              </div>
            ))
          })()}
        </nav>
        <div className="mt-auto pt-6">
          <AlertSettings />
        </div>
        {build ? (
          <p
            className="px-2.5 pt-2 text-[11px] text-zinc-400"
            title={t("The Kamra version this site is running")}
          >
            Kamra v{build}
          </p>
        ) : null}
      </aside>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        {!kiosk && (
        <header className="sticky top-0 z-40 flex min-w-0 items-center gap-2 border-b border-zinc-200 bg-white/90 px-4 py-2.5 backdrop-blur">
          <AppSwitcher apps={apps} current={currentApp ?? apps[0]} />
          {properties.length > 1 ? (
            <select
              className="min-w-0 max-w-[40vw] truncate rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-sm font-medium focus:outline-2 focus:outline-brand-600 lg:max-w-xs"
              value={property}
              onChange={(e) => switchProperty(e.target.value)}
              aria-label={t("Property")}
            >
              {properties.map((p) => (
                <option key={p.name} value={p.name}>
                  {p.property_name}
                  {p.city ? ` · ${p.city}` : ""}
                </option>
              ))}
            </select>
          ) : (
            <span className="min-w-0 truncate text-sm font-medium text-zinc-600">
              {properties[0]?.property_name ?? ""}
            </span>
          )}
          <div className="flex min-w-0 flex-1 justify-center px-2">
            <div className="hidden w-full max-w-md lg:block">
              <SearchShortcut />
            </div>
            <button
              type="button"
              onClick={() => window.dispatchEvent(new Event("kamra:open-palette"))}
              aria-label={t("Open search")}
              title={t("Open search")}
              className="ms-auto grid size-9 place-items-center rounded-lg text-zinc-500 hover:bg-zinc-100 lg:hidden"
            >
              <Search className="size-4" aria-hidden />
            </button>
          </div>
          <div className="flex shrink-0 items-center gap-2 sm:gap-3">
            <ThemeToggle />
            <span className="hidden text-xs text-zinc-500 xl:inline">
              {user}
            </span>
            <button
              onClick={signOut}
              className="inline-flex items-center gap-1 text-xs font-medium text-zinc-400 hover:text-zinc-700"
              aria-label={t("Sign out")}
              title={t("Sign out")}
            >
              <LogOut className="size-4 lg:hidden" aria-hidden />
              <span className="hidden lg:inline">{t("Sign out")}</span>
            </button>
            {canBook && (
              <>
                <Button
                  variant="outline"
                  className="hidden md:inline-flex"
                  onClick={() => setBooking({ walkIn: true })}
                >
                  {t("Walk-in")}
                </Button>
                <Button onClick={() => setBooking({})} aria-label={t("New booking")}>
                  <Plus className="size-4" aria-hidden />
                  <span className="hidden sm:inline">{t("New booking")}</span>
                </Button>
              </>
            )}
          </div>
        </header>
        )}

        <main
          key={property}
          className={
            floor
              ? cn(
                  "max-w-none",
                  kiosk
                    ? "h-[100dvh] overflow-hidden p-0"
                    : "min-h-[calc(100dvh-3.5rem)] overflow-auto p-3 lg:min-h-0 lg:flex-1 lg:overflow-hidden",
                )
              : "w-full max-w-none px-4 py-6 lg:px-6"
          }
        >
          <ErrorBoundary>
          <Outlet
            context={
              {
                refreshKey,
                canBook,
                modules,
                openBooking: (initial) => {
                  if (canBook) setBooking(initial)
                },
              } satisfies ShellContext
            }
          />
          </ErrorBoundary>
        </main>
      </div>

      {/* Never float over the till / kitchen pass in focus mode. */}
      {!kiosk && (
        <Suspense fallback={null}>
          <HelpPanel />
          <CommandPalette />
        </Suspense>
      )}

      {booking && canBook && (
        <Suspense fallback={null}>
          <BookingDialog
            initial={booking}
            onClose={() => setBooking(null)}
            onBooked={() => setRefreshKey((k) => k + 1)}
          />
        </Suspense>
      )}

      <span className="hidden">
        <IndianRupee className="size-3" aria-hidden />
      </span>
    </div>
    </div>
  )
}
