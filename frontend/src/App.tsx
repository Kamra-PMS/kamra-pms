import { Component, type ReactNode } from "react"
import {
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useOutletContext,
} from "react-router-dom"
import AppShell, { type ShellContext } from "./AppShell"
import Login from "./screens/Login"
import { useAuth } from "./lib/auth"
import { toFullPath } from "./lib/routing"
import { CalendarView } from "./components/CalendarView"
import { ResourceScreen } from "./components/ResourceScreen"
import Billing from "./screens/Billing"
import PublicBooking from "./screens/PublicBooking"
import PublicCheckin from "./screens/PublicCheckin"
import FolioView from "./screens/FolioView"
import GuestJourney from "./screens/GuestJourney"
import HkApp from "./screens/HkApp"
import Guests from "./screens/Guests"
import RegistrationCard from "./screens/RegistrationCard"
import CancellationLetter from "./screens/CancellationLetter"
import Setup from "./screens/Setup"
import Settings from "./screens/Settings"
import BookingEngine from "./screens/BookingEngine"
import Developers from "./screens/Developers"
import VenueCalendar from "./screens/VenueCalendar"
import Agents from "./screens/Agents"
import Activity from "./screens/Activity"
import AppLauncher from "./screens/AppLauncher"
import Marketplace from "./screens/Marketplace"
import Reports from "./screens/Reports"
import RevenueReports from "./screens/RevenueReports"
import OpsSLA from "./screens/OpsSLA"
import Dashboard from "./screens/Dashboard"
import CRS from "./screens/CRS"
import POS from "./screens/POS"
import Kitchen from "./screens/Kitchen"
import QrMenu from "./screens/QrMenu"
import AccountingExport from "./screens/AccountingExport"
import TapeChart from "./screens/TapeChart"
import Tickets from "./screens/Tickets"
import Laundry from "./screens/Laundry"
import Today from "./screens/Today"
import {
  companiesConfig,
  guardrailsConfig,
  housekeepingConfig,
  lostFoundConfig,
  mealPlansConfig,
  ratePlansConfig,
  reservationsConfig,
  roomBlocksConfig,
  menuItemsConfig,
  outletsConfig,
  roomTypesConfig,
  roomsConfig,
  seasonsConfig,
  shiftsConfig,
  travelAgentsConfig,
  groupsConfig,
  venueBookingsConfig,
  venuesConfig,
  vouchersConfig,
} from "./screens/configs"
import ConnectionBanner from "./components/ConnectionBanner"

class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="mx-auto max-w-lg p-8">
          <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
            <p className="font-semibold">Something broke in the UI.</p>
            <p className="mt-1 font-mono text-xs">
              {this.state.error.message}
            </p>
            <button
              className="mt-3 rounded-lg bg-rose-600 px-3 py-1.5 text-white"
              onClick={() => location.reload()}
            >
              Reload
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

function Splash() {
  return <p className="py-20 text-center text-sm text-zinc-400">Loading…</p>
}

/** Gate for the app shell: redirects to /login (remembering where you were)
 *  whenever there's no session, so the URL always matches the auth state. */
function RequireAuth() {
  const { status } = useAuth()
  const location = useLocation()
  if (status === "loading") return <Splash />
  if (status === "anon")
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: location.pathname + location.search }}
      />
    )
  return <Outlet />
}

/** The /login route. Already signed in → bounce to where you came from.
 *  On success, a full-page nav re-boots with the authenticated session's CSRF
 *  token (login rotates it); dev soft-navigates. */
function LoginPage() {
  const { status, refresh } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const from = (location.state as { from?: string } | null)?.from || "/"
  if (status === "loading") return <Splash />
  if (status === "authed") return <Navigate to={from} replace />
  return (
    <Login
      onSuccess={async () => {
        if (import.meta.env.PROD) {
          window.location.assign(toFullPath(from))
        } else {
          await refresh()
          navigate(from, { replace: true })
        }
      }}
    />
  )
}

function CalendarScreen() {
  const { refreshKey, openBooking } = useOutletContext<ShellContext>()
  return (
    <CalendarView
      refreshKey={refreshKey}
      onPick={(room_type, date) => openBooking({ room_type, date })}
    />
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <ConnectionBanner />
      <Routes>
        {/* public booking engine - no login; stay state lives in the URL
            (/book/2026-07-10/2026-07-12/2/0) so links are shareable and
            crawlable */}
        <Route path="book" element={<PublicBooking />} />
        <Route
          path="book/:checkin/:checkout?/:adults?/:children?"
          element={<PublicBooking />}
        />
        {/* pre-arrival self check-in, tokenized per reservation */}
        <Route path="checkin/:token" element={<PublicCheckin />} />
        {/* housekeeping phone app - share the /hk URL with the HK team */}
        <Route path="hk" element={<HkApp />} />
        <Route path="menu/:outlet" element={<QrMenu />} />
        {/* dedicated login route so signing out changes the URL */}
        <Route path="login" element={<LoginPage />} />
        <Route element={<RequireAuth />}>
          <Route element={<AppShell />}>
          <Route index element={<Today />} />
          <Route path="apps" element={<AppLauncher />} />
          <Route path="marketplace" element={<Marketplace />} />
          <Route path="agents" element={<Agents />} />
          <Route path="activity" element={<Activity />} />
          <Route path="assistant" element={<Agents />} />
          <Route path="calendar" element={<CalendarScreen />} />
          <Route path="tape" element={<TapeChart />} />
          <Route
            path="reservations"
            element={<ResourceScreen config={reservationsConfig} />}
          />
          <Route path="grc/:name" element={<RegistrationCard />} />
          <Route path="cancelled/:name" element={<CancellationLetter />} />
          <Route path="guests" element={<Guests />} />
          <Route path="guests/:name" element={<GuestJourney />} />
          <Route
            path="rooms"
            element={<ResourceScreen config={roomsConfig} />}
          />
          <Route
            path="room-types"
            element={<ResourceScreen config={roomTypesConfig} />}
          />
          <Route
            path="room-blocks"
            element={<ResourceScreen config={roomBlocksConfig} />}
          />
          <Route
            path="rate-plans"
            element={<ResourceScreen config={ratePlansConfig} />}
          />
          <Route
            path="guardrails"
            element={<ResourceScreen config={guardrailsConfig} />}
          />
          <Route
            path="seasons"
            element={<ResourceScreen config={seasonsConfig} />}
          />
          <Route
            path="vouchers"
            element={<ResourceScreen config={vouchersConfig} />}
          />
          <Route
            path="meal-plans"
            element={<ResourceScreen config={mealPlansConfig} />}
          />
          <Route path="billing" element={<Billing />} />
          <Route path="billing/:name" element={<FolioView />} />
          <Route
            path="companies"
            element={<ResourceScreen config={companiesConfig} />}
          />
          <Route
            path="travel-agents"
            element={<ResourceScreen config={travelAgentsConfig} />}
          />
          <Route
            path="events"
            element={<ResourceScreen config={venueBookingsConfig} />}
          />
          <Route
            path="venues"
            element={<ResourceScreen config={venuesConfig} />}
          />
          <Route path="venue-calendar" element={<VenueCalendar />} />
          <Route
            path="groups"
            element={<ResourceScreen config={groupsConfig} />}
          />
          <Route
            path="lost-found"
            element={<ResourceScreen config={lostFoundConfig} />}
          />
          <Route
            path="shifts"
            element={<ResourceScreen config={shiftsConfig} />}
          />
          <Route path="setup" element={<Setup />} />
          <Route path="settings" element={<Settings />} />
          <Route path="booking-settings" element={<BookingEngine />} />
          <Route path="booking-settings/:section" element={<BookingEngine />} />
          <Route path="developers" element={<Developers />} />
          <Route path="reports" element={<Reports />} />
          <Route path="revenue-reports" element={<RevenueReports />} />
          <Route path="ops-sla" element={<OpsSLA />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="crs" element={<CRS />} />
          <Route path="pos" element={<POS />} />
          <Route path="kitchen" element={<Kitchen />} />
          <Route path="menu-items" element={<ResourceScreen config={menuItemsConfig} />} />
          <Route path="outlets" element={<ResourceScreen config={outletsConfig} />} />
          <Route path="accounting-export" element={<AccountingExport />} />
          <Route path="tickets" element={<Tickets />} />
          <Route path="laundry" element={<Laundry />} />
          <Route
            path="housekeeping"
            element={<ResourceScreen config={housekeepingConfig} />}
          />
          <Route
            path="*"
            element={
              <p className="py-10 text-center text-sm text-zinc-400">
                Page not found.
              </p>
            }
          />
          </Route>
        </Route>
      </Routes>
    </ErrorBoundary>
  )
}
