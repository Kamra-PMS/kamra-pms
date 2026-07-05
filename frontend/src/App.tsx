import { Component, type ReactNode } from "react"
import { Route, Routes, useOutletContext } from "react-router-dom"
import AppShell, { type ShellContext } from "./AppShell"
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
import TapeChart from "./screens/TapeChart"
import Tickets from "./screens/Tickets"
import Today from "./screens/Today"
import {
  companiesConfig,
  guardrailsConfig,
  housekeepingConfig,
  lostFoundConfig,
  mealPlansConfig,
  ratePlansConfig,
  reservationsConfig,
  roomTypesConfig,
  roomsConfig,
  seasonsConfig,
  shiftsConfig,
  travelAgentsConfig,
  venueBookingsConfig,
  venuesConfig,
  vouchersConfig,
} from "./screens/configs"

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
      <Routes>
        {/* public booking engine — no login; stay state lives in the URL
            (/book/2026-07-10/2026-07-12/2/0) so links are shareable and
            crawlable */}
        <Route path="book" element={<PublicBooking />} />
        <Route
          path="book/:checkin/:checkout?/:adults?/:children?"
          element={<PublicBooking />}
        />
        {/* pre-arrival self check-in, tokenized per reservation */}
        <Route path="checkin/:token" element={<PublicCheckin />} />
        {/* housekeeping phone app — share the /hk URL with the HK team */}
        <Route path="hk" element={<HkApp />} />
        <Route element={<AppShell />}>
          <Route index element={<Today />} />
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
          <Route path="tickets" element={<Tickets />} />
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
      </Routes>
    </ErrorBoundary>
  )
}
