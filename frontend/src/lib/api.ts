// Thin client for Kamra's whitelisted API. Session-cookie auth via
// Frappe's /api/method/login; unauthenticated calls surface as 401/403
// and the shell shows the login screen.

async function doFetch(path: string, init?: RequestInit) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    ...init,
  })
  if (!res.ok) {
    const body = await res.text()
    throw Object.assign(new Error(`${path} failed (${res.status})`), {
      status: res.status,
      body,
    })
  }
  return res.json()
}

export async function login(usr: string, pwd: string) {
  await doFetch("/api/method/login", {
    method: "POST",
    body: JSON.stringify({ usr, pwd }),
  })
}

export async function logout() {
  await doFetch("/api/method/logout", { method: "POST" })
}

export function isAuthError(err: unknown): boolean {
  const status = (err as { status?: number }).status
  return status === 401 || status === 403
}

export async function frappeFetch<T = unknown>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  return (await doFetch(path, init)) as T
}

export async function call<T = unknown>(
  method: string,
  params: Record<string, unknown> = {},
): Promise<T> {
  const data = await frappeFetch<{ message: T }>(`/api/method/${method}`, {
    method: "POST",
    body: JSON.stringify(params),
  })
  return data.message
}

export interface WhoAmI {
  user: string
  full_name: string
  roles: string[]
}

export const whoami = () => call<WhoAmI>("kamra.api.whoami")

export interface ReservationRow {
  name: string
  guest_name: string
  room_type: string
  room: string | null
  status: string
  source: string
  check_in_date: string
  check_out_date: string
  nights: number
  adults: number
  children: number
  special_requests: string | null
  channel: string | null
  precheckin_status: "Not Started" | "Submitted" | "Verified" | null
  eta: string | null
  precheckin_token: string | null
  booked_by_name: string | null
  booked_by_phone: string | null
  booker_relation: string | null
  contact_preference: "Guest" | "Booker" | "Both" | null
  company: string | null
  paid_total: number
  balance_due: number
}

export interface RoomRow {
  name: string
  room_number: string
  room_type: string
  floor: string | null
  housekeeping_status: "Clean" | "Dirty" | "Inspected" | "Out of Order"
  occupancy_status: "Vacant" | "Occupied"
}

export interface Snapshot {
  date: string
  arrivals: ReservationRow[]
  departures: ReservationRow[]
  in_house: ReservationRow[]
  rooms: RoomRow[]
  minutes_saved_30d: number
}

export interface CalendarCell {
  date: string
  available: number
  rate: number
}

export interface CalendarRow {
  room_type: string
  room_type_name: string
  total_rooms: number
  cells: CalendarCell[]
}

export interface CalendarData {
  start: string
  days: number
  dates: string[]
  room_types: CalendarRow[]
}

export interface BookingOptions {
  room_types: {
    name: string
    room_type_name: string
    base_price: number
    adults_capacity: number
  }[]
  meal_plans: {
    name: string
    code: string
    label: string
    price_per_adult: number
    is_default: 0 | 1
  }[]
  rate_plans: { name: string; rate_plan_name: string; code: string }[]
  companies: { name: string; company_name: string }[]
  travel_agents: { name: string; agent_name: string; commission_pct: number }[]
  experiences: {
    name: string
    experience_name: string
    category: string | null
    price: number
    gst_rate: number
  }[]
  property: {
    sell_message: string | null
    free_cancel_days: number
    cancellation_fee: "None" | "First Night" | "Full Stay"
    no_show_charge: "None" | "First Night" | "Full Stay"
    deposit_pct: number
  }
}

export interface Quote {
  nights: number
  nightly: { date: string; rate: number }[]
  room_total: number
  meal_total: number
  discount: number
  amount_before_tax: number
  tax_percent: number
  tax_amount: number
  amount_after_tax: number
}

export const DEMO_PROPERTY = "Kamra Demo Palace"

// Active property — set by the header switcher, read at call time.
let currentProperty =
  localStorage.getItem("kamra_property") || DEMO_PROPERTY

export function getCurrentProperty() {
  return currentProperty
}

export function setCurrentProperty(p: string) {
  currentProperty = p
  localStorage.setItem("kamra_property", p)
}

export interface PropertyRow {
  name: string
  property_name: string
  city: string | null
}

export const myProperties = () =>
  call<PropertyRow[]>("kamra.api.my_properties")

export const getSnapshot = () =>
  call<Snapshot>("kamra.api.front_desk_snapshot", {
    property: getCurrentProperty(),
  })

export const getCalendar = (days = 14, startDate?: string) =>
  call<CalendarData>("kamra.api.availability_calendar", {
    property: getCurrentProperty(),
    days,
    start_date: startDate ?? null,
  })

export const getBookingOptions = () =>
  call<BookingOptions>("kamra.api.booking_options", {
    property: getCurrentProperty(),
  })

export interface QuoteParams {
  room_type: string
  check_in_date: string
  check_out_date: string
  adults: number
  children: number
  meal_plan?: string
  voucher_code?: string
}

export const getQuote = (params: QuoteParams) =>
  call<Quote>("kamra.api.get_quote", { property: getCurrentProperty(), ...params })

export interface GuestHit {
  name: string
  full_name: string
  phone: string | null
  email: string | null
  vip: 0 | 1
  blacklisted: 0 | 1
  stays: number
  last_stay: string | null
}

export const guestSearch = (q: string) =>
  call<GuestHit[]>("kamra.api.guest_search", { q })

export const createBooking = (
  params: QuoteParams & {
    guest_name: string
    phone?: string
    guest?: string
    company?: string
    travel_agent?: string
    booking_type?: string
    booked_by_name?: string
    booked_by_phone?: string
    booker_relation?: string
    contact_preference?: string
    addons?: { experience: string; qty: number }[]
  },
) =>
  call<{ reservation: string; room: string | null; amount_after_tax: number }>(
    "kamra.api.create_booking",
    { property: getCurrentProperty(), ...params },
  )

export const checkIn = (reservation: string) =>
  call("kamra.api.check_in", { reservation })

export const checkOut = (reservation: string) =>
  call("kamra.api.check_out", { reservation })

export const setHousekeepingStatus = (room: string, status: string) =>
  call("kamra.api.set_housekeeping_status", { room, status })
