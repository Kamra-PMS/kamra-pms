// Thin client for Kamra's whitelisted API. Session-cookie auth via
// Frappe's /api/method/login; unauthenticated calls surface as 401/403
// and the shell shows the login screen.

// The served boot page injects the session's CSRF token as window.csrf_token
// (see kamra/www/kamra.py). Frappe enforces it on POSTs from a logged-in
// session; guests and the dev server (ignore_csrf) don't need it.
function csrfToken(): string | undefined {
  const t = (window as unknown as { csrf_token?: string }).csrf_token
  return t && t !== "None" ? t : undefined
}

/** Marks errors where the request never reached the server (offline, server
 * restarting). Callers keep the user's session and data intact for these. */
export function isNetworkError(err: unknown): boolean {
  return Boolean((err as { network?: boolean }).network)
}

async function doFetch(path: string, init?: RequestInit) {
  const token = csrfToken()
  const request = () =>
    fetch(path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "X-Frappe-CSRF-Token": token } : {}),
        ...(init?.headers as Record<string, string> | undefined),
      },
      credentials: "include",
    })
  let res: Response
  try {
    res = await request()
  } catch {
    // the request never left: wifi blip, server restarting. One quiet retry
    // covers most of these without the user ever seeing an error.
    await new Promise((r) => setTimeout(r, 800))
    try {
      res = await request()
    } catch (err) {
      console.warn(`[kamra] network failure calling ${path}`, err)
      window.dispatchEvent(new Event("kamra:offline"))
      throw Object.assign(
        new Error("Can't reach Kamra right now. Check your connection — we'll reconnect automatically."),
        { network: true },
      )
    }
  }
  window.dispatchEvent(new Event("kamra:online"))
  if (!res.ok) {
    const body = await res.text()
    // A 401/403 on anything other than the auth endpoints means the session may
    // be gone. Signal the auth layer to re-check (and redirect to /login if so)
    // instead of leaving a dead screen. Login's own 401 (wrong password) is
    // excluded so it doesn't trigger a session re-check.
    if (
      (res.status === 401 || res.status === 403) &&
      !path.includes("/api/method/login")
    ) {
      window.dispatchEvent(new Event("kamra:auth-error"))
    }
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

/** Upload an image to Frappe's public files; resolves to its served URL.
 *  Pass doctype/docname/fieldname so Attach Image fields keep a real File
 *  link — otherwise the URL shows in the form but is easy to lose on save. */
export async function uploadFile(
  file: File,
  opts?: { doctype?: string; docname?: string; fieldname?: string },
): Promise<string> {
  const token = csrfToken()
  const fd = new FormData()
  fd.append("file", file, file.name)
  fd.append("is_private", "0")
  if (opts?.doctype) fd.append("doctype", opts.doctype)
  if (opts?.docname) fd.append("docname", opts.docname)
  if (opts?.fieldname) fd.append("fieldname", opts.fieldname)
  const res = await fetch("/api/method/upload_file", {
    method: "POST",
    // no Content-Type header: the browser sets the multipart boundary
    headers: token ? { "X-Frappe-CSRF-Token": token } : undefined,
    body: fd,
    credentials: "include",
  })
  if (!res.ok) {
    let detail = `upload failed (${res.status})`
    try {
      const body = await res.json()
      const msgs = JSON.parse(body._server_messages ?? "[]")
      if (msgs.length) {
        detail = String(JSON.parse(msgs[0]).message).replace(/<[^>]+>/g, "")
      }
    } catch {
      /* keep status text */
    }
    throw new Error(detail)
  }
  const out = (await res.json()) as { message?: { file_url?: string } }
  const url = out.message?.file_url
  if (!url) throw new Error("upload returned no file URL")
  return url
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

/** Which parts of Kamra this property runs. Empty on the server means
 *  "all of them", so an existing property is untouched. */
export const enabledModules = () =>
  call<string[]>("kamra.api.enabled_modules", {
    property: getCurrentProperty(),
  })
export const setEnabledModules = (modules: string[]) =>
  call<{ ok: boolean; modules: string[] }>("kamra.api.set_enabled_modules", {
    property: getCurrentProperty(),
    modules,
  })

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
    children_capacity: number
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

// Every Kamra site hosts exactly one Property. The public booking engine
// (/book) has no logged-in session to read a chosen property from, so it
// asks the site which one to show instead of assuming the demo property.
export const getDefaultProperty = () =>
  call<string>("kamra.public_api.default_property")

// Active property - set by the header switcher, read at call time.
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
    waitlist?: number
    addons?: { experience: string; qty: number }[]
    guest_category?: string
    stay_details?: Record<string, unknown>
    instructions?: { department: string; instruction: string }[]
  },
) =>
  call<{
    reservation: string
    room: string | null
    amount_after_tax: number
    status?: string
  }>("kamra.api.create_booking", { property: getCurrentProperty(), ...params })

export const promoteWaitlist = (reservation: string) =>
  call<{ ok: boolean; reservation: string; room: string }>(
    "kamra.api.promote_waitlist",
    { reservation },
  )

export interface VenueBookingCell {
  name: string
  venue: string
  event_type: string
  status: string
  event_date: string
  start_time: string
  end_time: string
  customer_name: string
  attendees: number
  quoted_amount: number
  advance_received: number
}
export interface VenueCalendarData {
  start: string
  days: number
  dates: string[]
  venues: {
    name: string
    venue_name: string
    capacity: number
    base_price: number
    bookings: VenueBookingCell[]
  }[]
}
export const venueCalendar = (days = 14, startDate?: string) =>
  call<VenueCalendarData>("kamra.api.venue_calendar", {
    property: getCurrentProperty(),
    days,
    start_date: startDate ?? null,
  })

// --- Banquets: the function business, enquiry → event order → bill ---

export type FunctionStatus =
  | "Enquiry"
  | "Tentative"
  | "Confirmed"
  | "Completed"
  | "Cancelled"
  | "Lost"

export interface BanquetMenuCourse {
  name?: string
  course: string
  dishes: string | null
  choice_of: number
  is_live_counter: 0 | 1
}
export interface BanquetMenu {
  name: string
  menu_name: string
  menu_code: string | null
  meal_period: string
  food_type: string
  service_style: string
  cuisine: string | null
  rate_per_pax: number
  min_pax: number
  gst_rate: number
  inclusions: string | null
  exclusions: string | null
  courses: BanquetMenuCourse[]
}
export interface BanquetService {
  name: string
  item_name: string
  category: string
  uom: string
  rate: number
  gst_rate: number
  chargeable: 0 | 1
  is_alcohol: 0 | 1
  on_pack_list: 0 | 1
  description: string | null
}
export interface BanquetVenue {
  name: string
  venue_name: string
  venue_code: string | null
  venue_type: string
  capacity: number
  min_capacity: number
  area_sqft: number
  base_price: number
  hourly_rate: number
  min_hours: number
  gst_rate: number
  setup_styles: string | null
  amenities: string | null
}
export interface BanquetCatalogue {
  menus: BanquetMenu[]
  services: BanquetService[]
  venues: BanquetVenue[]
}

export interface FunctionItem {
  name: string
  item_type: string
  item_name: string
  banquet_menu: string | null
  service_item: string | null
  description: string | null
  qty: number
  uom: string
  list_rate: number
  rate: number
  chargeable: 0 | 1
  is_alcohol: 0 | 1
  on_pack_list: 0 | 1
  tax_exempt: 0 | 1
  amount: number
  net_amount: number
  gst_rate: number
  gst_amount: number
  total: number
  notes: string | null
}
export interface PaymentTerm {
  name: string
  milestone: string
  due_date: string | null
  percent: number
  amount: number
  status: "Pending" | "Overdue" | "Received" | "Waived"
  received_on: string | null
  reference: string | null
}
export interface OpenItem {
  name: string
  title: string
  detail: string | null
  owner_side: "Hotel" | "Client"
  due_date: string | null
  price_impact: number
  status: "Open" | "Agreed" | "Dropped"
}
export interface QuoteRevision {
  name: string
  version: number
  revised_on: string
  revised_by: string
  grand_total: number
  pax: number
  change_note: string | null
}
export interface BanquetReceipt {
  name: string
  receipt_date: string
  kind: string
  mode: string
  amount: number
  reference: string | null
}
export interface FunctionAlert {
  kind: string
  urgency: "high" | "normal"
  message: string
}
export interface FunctionSheet {
  name: string
  property: string
  venue: string
  event_type: string
  event_name: string | null
  status: FunctionStatus
  enquiry_date: string
  source: string
  sales_owner: string | null
  follow_up_date: string | null
  tentative_until: string | null
  lost_reason: string | null
  event_date: string
  end_date: string | null
  start_time: string | null
  end_time: string | null
  billable_hours: number
  session: string
  setup_style: string | null
  setup_notes: string | null
  setup_from: string | null
  teardown_by: string | null
  customer_name: string
  customer_phone: string | null
  customer_email: string | null
  company: string | null
  travel_agent: string | null
  billing_name: string | null
  gstin: string | null
  billing_address: string | null
  place_of_supply: string | null
  attendees: number
  pax_guaranteed: number
  pax_actual: number
  billable_pax: number
  rate_basis: string
  green_room: string | null
  green_room_from: string | null
  green_room_to: string | null
  green_room_complimentary: 0 | 1
  green_room_block: string | null
  venue_rental_list: number
  venue_rental: number
  subtotal: number
  discount_amount: number
  service_charge_percent: number
  service_charge: number
  taxable_amount: number
  tax_amount: number
  grand_total: number
  non_chargeable_value: number
  advance_received: number
  balance_due: number
  food_cost: number
  service_cost: number
  total_cost: number
  input_tax_credit: number
  itc_eligible: 0 | 1
  net_cost: number
  gross_margin: number
  margin_percent: number
  customer: string | null
  refundable_deposit: number
  deposit_held: number
  deposit_refunded: number
  damage_amount: number
  damage_note: string | null
  closed_out_on: string | null
  closed_out_by: string | null
  quote_version: number
  quote_sent_on: string | null
  quote_valid_till: string | null
  beo_number: string | null
  beo_generated_on: string | null
  contract_signed_on: string | null
  payment_terms_note: string | null
  requirements: string | null
  beo_notes: string | null
  internal_notes: string | null
  group_booking: string | null
  folio: string | null
  posted_to_folio: 0 | 1
  items: FunctionItem[]
  selections: {
    name: string
    banquet_menu: string
    course: string | null
    dish: string | null
    dish_name: string
    food_type: string | null
    kitchen: string | null
    supplement_per_pax: number
    cost_per_portion: number
    portion_per_pax: number
    note: string | null
  }[]
  payment_terms: PaymentTerm[]
  open_items: OpenItem[]
  revisions: QuoteRevision[]
  receipts: BanquetReceipt[]
  venue_detail: Partial<BanquetVenue>
  group_detail: { name: string; group_name: string } | null
  scheduled_total: number
  open_item_impact: number
  next_actions: FunctionAlert[]
}

export interface BanquetCalendarCell {
  name: string
  venue: string
  event_type: string
  event_name: string | null
  status: FunctionStatus
  event_date: string
  end_date: string | null
  start_time: string
  end_time: string
  customer_name: string
  company: string | null
  pax: number
  grand_total: number
  advance_received: number
  balance_due: number
  setup_style: string | null
  day_index: number
  day_span: number
}
export interface BanquetCalendarData {
  start: string
  days: number
  dates: string[]
  venues: (BanquetVenue & {
    bookings: BanquetCalendarCell[]
    by_date: Record<string, BanquetCalendarCell[]>
  })[]
}

export interface AvailabilityVenue extends BanquetVenue {
  available: boolean
  fits: boolean
  under_minimum: boolean
  conflicts: {
    name: string
    customer_name: string
    event_date: string
    start_time: string | null
    end_time: string | null
    status: string
    kind: "confirmed" | "tentative"
  }[]
}

export interface PipelineBucket {
  key: string
  count: number
  value: number
  pax: number
}
export interface PipelineMonth {
  month: string
  count: number
  pax: number
  confirmed_value: number
  pipeline_value: number
  lost_value: number
  received: number
  outstanding: number
  statuses: Record<string, { count: number; value: number; pax: number }>
}
export interface BanquetPipeline {
  from: string
  to: string
  months: PipelineMonth[]
  by_status: PipelineBucket[]
  by_event_type: PipelineBucket[]
  by_venue: PipelineBucket[]
  by_source: PipelineBucket[]
  totals: {
    functions: number
    confirmed_value: number
    pipeline_value: number
    outstanding: number
    conversion_rate: number | null
  }
  lost_reasons: { reason: string; count: number }[]
}

export interface ReminderRow {
  function: string
  customer_name: string
  venue: string
  event_date: string
  status: FunctionStatus
  grand_total: number
  balance_due: number
  sales_owner: string | null
  alerts: FunctionAlert[]
}

export type DocumentKind = "quote" | "contract" | "beo" | "pack_list" | "invoice"
export interface BanquetDocument {
  header: {
    kind: DocumentKind
    title: string
    number: string
    is_final: boolean
    function: string
    reference: string
    issued_on: string | null
    version: number
    printed_on: string
    valid_till: string | null
    beo_number: string | null
    amount_in_words: string
    service_code_label: string
    footer: string | null
    place_of_supply: string | null
    tax_label: string
    tax_id_label: string
  }
  property: Record<string, string | null>
  customer: Record<string, string | null>
  event: Record<string, string | number | boolean | null>
  totals: {
    subtotal: number
    discount: number
    taxable: number
    tax: number
    grand_total: number
    complimentary_value: number
    received: number
    balance_due: number
    tax_summary: { gst_rate: number; taxable: number; tax: number }[]
  }
  lines: (FunctionItem & { service_code: string | null })[]
  complimentary: (FunctionItem & { service_code: string | null })[]
  tax_breakup?: {
    rate: number
    taxable: number
    total_tax: number
    parts: { label: string; rate: number; amount: number }[]
  }[]
  terms: Omit<PaymentTerm, "name" | "received_on">[]
  terms_note: string | null
  open_items: Omit<OpenItem, "name">[]
  requirements: string | null
  menus?: {
    menu_name: string
    menu_code: string | null
    meal_period: string
    food_type: string
    service_style: string
    cuisine: string | null
    pax: number
    chargeable: boolean
    inclusions: string | null
    exclusions: string | null
    courses: BanquetMenuCourse[]
  }[]
  notes?: string | null
  pack?: {
    deliver_by: string
    collect_after: string | null
    venue: string
    total_items: number
    groups: {
      group: string
      items: {
        item_name: string
        qty: number
        uom: string
        chargeable: boolean
        notes: string | null
        description: string | null
      }[]
    }[]
  }
  signatures?: { for: string; role: string }[]
  signed_on?: string | null
  receipts?: { date: string; kind: string; mode: string; amount: number; reference: string | null }[]
}


export interface MonthCell {
  name: string
  venue: string
  session: string
  status: FunctionStatus
  event_date: string
  end_date: string | null
  customer_name: string
  event_type: string
  event_name: string | null
  grand_total: number
  balance_due: number
  pax: number
  spans_day: boolean
}
export interface MonthAvailability {
  month: string
  start: string
  end: string
  dates: string[]
  utilisation: number
  venues: BanquetVenue[]
  rows: {
    venue: string
    venue_name: string
    venue_type: string
    capacity: number
    base_price: number
    session: string
    sold_days: number
    by_date: Record<string, MonthCell[]>
  }[]
}

export interface RegisterRow {
  name: string
  event_date: string
  end_date: string | null
  session: string
  status: FunctionStatus
  customer_name: string
  company: string | null
  customer_phone: string | null
  venue: string
  event_type: string
  event_name: string | null
  pax: number
  rate_per_pax: number
  subtotal: number
  discount_amount: number
  service_charge: number
  tax_amount: number
  grand_total: number
  advance_received: number
  balance_due: number
  food_cost: number
  service_cost: number
  total_cost: number
  input_tax_credit: number
  itc_eligible: 0 | 1
  net_cost: number
  gross_margin: number
  margin_percent: number
  customer: string | null
  refundable_deposit: number
  deposit_held: number
  deposit_refunded: number
  damage_amount: number
  damage_note: string | null
  closed_out_on: string | null
  closed_out_by: string | null
  quote_version: number
  source: string | null
  lost_reason: string | null
  /** receipts register only */
  parent?: string
  receipt_date?: string
  kind?: string
  mode?: string
  amount?: number
  signed_amount?: number
  reference?: string | null
}
export interface RegisterRollup {
  key: string
  count: number
  pax: number
  value: number
  received: number
}
export interface BanquetRegister {
  register: string
  title: string
  from: string
  to: string
  rows: RegisterRow[]
  totals: {
    count: number
    pax?: number
    value: number
    received?: number
    outstanding?: number
  }
  by_mode?: { mode: string; amount: number }[]
  by_venue?: RegisterRollup[]
  by_event_type?: RegisterRollup[]
  by_session?: RegisterRollup[]
  by_source?: RegisterRollup[]
}

export interface ReceiptDocument {
  header: {
    title: string
    reference: string
    receipt_no: string
    date: string
    printed_on: string
    amount_in_words: string
  }
  property: Record<string, string | null>
  customer: Record<string, string | null>
  event: Record<string, string | number | null>
  receipt: {
    kind: string
    mode: string
    amount: number
    reference: string | null
    received_by: string | null
  }
  running: {
    grand_total: number
    received: number
    deposit_held: number
    balance_due: number
  }
}

export interface MenuCard {
  header: { title: string; reference: string; printed_on: string }
  property: Record<string, string | null>
  event: Record<string, string | number | null>
  menus: NonNullable<BanquetDocument["menus"]>
  extras: {
    item_name: string
    description: string | null
    qty: number
    uom: string
    chargeable: boolean
  }[]
  notes: string | null
  signatures: { for: string; role: string }[]
}


export interface RecipeRow {
  name?: string
  ingredient: string
  qty: number
  note: string | null
}
export interface BanquetDish {
  name: string
  dish_name: string
  course_type: string
  food_type: string
  kitchen: string
  portion_per_pax: number
  cost_per_portion: number
  allergens: string | null
  description: string | null
  recipe: RecipeRow[]
}
export interface DishOption {
  dish: string
  dish_name: string
  food_type: string | null
  kitchen: string | null
  allergens: string | null
  cost_per_portion: number
  portion_per_pax: number
  supplement_per_pax: number
  is_default: boolean
  chosen: boolean
}
export interface MenuChoices {
  menu: string
  menu_name: string
  meal_period: string
  courses: {
    course: string
    choice_of: number
    is_live_counter: boolean
    free_text: string | null
    options: DishOption[]
    chosen_count: number
  }[]
}
export interface MenuCost {
  menu: string
  menu_name: string
  rate_per_pax: number
  cost_per_pax: number
  margin_per_pax: number
  margin_percent: number
  courses: { course: string; dishes: number; cost_per_pax: number; costed: boolean }[]
  uncosted_courses: string[]
}
export interface KitchenIndent {
  function: string
  customer_name: string
  event_date: string
  session: string
  venue: string
  pax: number
  total_cost: number
  shortfall_lines: number
  uncosted: string[]
  ingredients: {
    ingredient: string
    ingredient_name: string
    category: string | null
    uom: string
    required: number
    on_hand: number
    short_by: number
    cost: number
    for_dishes: string[]
  }[]
  by_kitchen: {
    kitchen: string
    dishes: {
      dish: string
      course: string
      food_type: string | null
      portions: number
      note: string | null
    }[]
  }[]
}
export interface FunctionEconomics {
  function: string
  pax: number
  revenue: {
    subtotal: number
    discount: number
    service_charge: number
    taxable: number
    tax: number
    grand_total: number
    complimentary: number
    supplementary: number
  }
  cost: {
    food: number
    service: number
    total: number
    input_tax: number
    itc_eligible: boolean
    net: number
  }
  margin: { gross: number; percent: number; per_pax: number }
  lines: {
    row: string
    item_name: string
    item_type: string
    uom: string
    quoted_qty: number
    actual_qty: number | null
    variance: number
    rate: number
    amount: number
    net_amount: number
    cost_rate: number
    cost_amount: number
    input_tax: number
    margin: number
    chargeable: boolean
    is_supplementary: boolean
  }[]
  uncosted_lines: string[]
}
export interface CustomerProfile {
  found: boolean
  guest?: {
    name: string
    full_name: string
    phone: string | null
    email: string | null
    vip: 0 | 1
    guest_notes: string | null
    guest_category: string | null
    city: string | null
    blacklisted: 0 | 1
    blacklist_reason: string | null
  }
  functions?: {
    name: string
    event_date: string
    event_type: string
    event_name: string | null
    venue: string
    session: string
    status: FunctionStatus
    grand_total: number
    balance_due: number
    company: string | null
  }[]
  stats?: {
    functions: number
    won: number
    lifetime_value: number
    average_value: number
    average_pax: number
    outstanding: number
    usual_venue: string | null
    usual_event: string | null
    room_stays: number
    last_event: string | null
  }
}

const banquetCall = <T,>(method: string, params: Record<string, unknown> = {}) =>
  call<T>(`kamra.banquet.${method}`, {
    property: getCurrentProperty(),
    ...params,
  })

export const banquet = {
  catalogue: () => banquetCall<BanquetCatalogue>("banquet_catalogue"),
  saveMenu: (params: Record<string, unknown>) =>
    banquetCall<{ ok: boolean; name: string }>("save_banquet_menu", params),
  deleteMenu: (name: string) =>
    call<{ ok: boolean }>("kamra.banquet.delete_banquet_menu", { name }),
  saveService: (params: Record<string, unknown>) =>
    banquetCall<{ ok: boolean; name: string }>("save_service_item", params),
  deleteService: (name: string) =>
    call<{ ok: boolean }>("kamra.banquet.delete_service_item", { name }),

  createEnquiry: (params: Record<string, unknown>) =>
    banquetCall<{ ok: boolean; function: string; grand_total: number }>(
      "create_enquiry",
      params,
    ),
  sheet: (fn: string) =>
    call<FunctionSheet>("kamra.banquet.function_sheet", { function: fn }),
  update: (fn: string, fields: Record<string, unknown>) =>
    call<{ ok: boolean; grand_total: number; balance_due: number }>(
      "kamra.banquet.update_function",
      { function: fn, fields },
    ),
  setStatus: (fn: string, status: FunctionStatus, reason?: string) =>
    call<{ ok: boolean; status: FunctionStatus; from: string }>(
      "kamra.banquet.set_status",
      { function: fn, status, reason: reason ?? null },
    ),

  addMenu: (fn: string, menu: string, opts: Record<string, unknown> = {}) =>
    call("kamra.banquet.add_menu", { function: fn, menu, ...opts }),
  addService: (fn: string, service: string, opts: Record<string, unknown> = {}) =>
    call("kamra.banquet.add_service", {
      function: fn,
      service_item: service,
      ...opts,
    }),
  saveItems: (fn: string, items: Partial<FunctionItem>[]) =>
    call("kamra.banquet.save_items", { function: fn, items }),
  removeItem: (fn: string, row: string) =>
    call("kamra.banquet.remove_item", { function: fn, row }),

  negotiate: (fn: string, params: Record<string, unknown>) =>
    call<{
      ok: boolean
      was: number
      now: number
      moved_by: number
      changes: string[]
    }>("kamra.banquet.negotiate", { function: fn, ...params }),
  saveOpenItems: (fn: string, rows: Partial<OpenItem>[]) =>
    call("kamra.banquet.save_open_items", { function: fn, rows }),
  setPaymentTerms: (fn: string, terms: Partial<PaymentTerm>[], note?: string) =>
    call("kamra.banquet.set_payment_terms", {
      function: fn,
      terms,
      note: note ?? null,
    }),
  defaultPaymentTerms: (fn: string) =>
    call("kamra.banquet.default_payment_terms", { function: fn }),
  recordReceipt: (fn: string, params: Record<string, unknown>) =>
    call<{ ok: boolean; received: number; balance_due: number }>(
      "kamra.banquet.record_receipt",
      { function: fn, ...params },
    ),
  assignGreenRoom: (fn: string, params: Record<string, unknown>) =>
    call("kamra.banquet.assign_green_room", { function: fn, ...params }),

  availability: (params: Record<string, unknown>) =>
    banquetCall<{ venues: AvailabilityVenue[] }>("venue_availability", params),
  calendar: (startDate?: string, days = 31) =>
    banquetCall<BanquetCalendarData>("banquet_calendar", {
      start_date: startDate ?? null,
      days,
    }),
  pipeline: (params: Record<string, unknown> = {}) =>
    banquetCall<BanquetPipeline>("banquet_pipeline", params),
  reminders: (days = 30) =>
    banquetCall<{ count: number; functions: ReminderRow[] }>(
      "banquet_reminders",
      { days },
    ),

  // the buy side: dishes, recipes, what a plate costs
  dishes: (courseType?: string) =>
    banquetCall<BanquetDish[]>("dish_library", {
      course_type: courseType ?? null,
    }),
  saveDish: (params: Record<string, unknown>) =>
    banquetCall<{ ok: boolean; name: string; cost_per_portion: number }>(
      "save_dish",
      params,
    ),
  deleteDish: (name: string) =>
    call<{ ok: boolean }>("kamra.banquet.delete_dish", { name }),
  recostDishes: () =>
    banquetCall<{ ok: boolean; recosted: number }>("recost_dishes"),
  menuCost: (menu: string, pax?: number) =>
    call<MenuCost>("kamra.banquet.menu_cost", { menu, pax: pax ?? 0 }),

  // what the customer chose
  menuChoices: (fn: string, menu: string) =>
    call<MenuChoices>("kamra.banquet.menu_choices", { function: fn, menu }),
  composeMenu: (fn: string, menu: string, picks: Record<string, unknown>[]) =>
    call<{
      ok: boolean
      chosen: number
      cost_per_pax: number
      supplement_per_pax: number
      grand_total: number
      margin_percent: number
    }>("kamra.banquet.compose_menu", { function: fn, menu, picks }),

  // the kitchen, and the night itself
  indent: (fn: string) =>
    call<KitchenIndent>("kamra.banquet.kitchen_indent", { function: fn }),
  issueIndent: (fn: string, outlet: string) =>
    call<{ ok: boolean; issued: number }>("kamra.banquet.issue_indent", {
      function: fn,
      outlet,
    }),
  recordConsumption: (
    fn: string,
    rows: Record<string, number>,
    paxActual?: number,
  ) =>
    call<{ ok: boolean; grand_total: number; changes: string[] }>(
      "kamra.banquet.record_consumption",
      { function: fn, rows, pax_actual: paxActual ?? null },
    ),
  addSupplementary: (fn: string, params: Record<string, unknown>) =>
    call<{ ok: boolean; grand_total: number; supplementary_total: number }>(
      "kamra.banquet.add_supplementary",
      { function: fn, ...params },
    ),
  economics: (fn: string) =>
    call<FunctionEconomics>("kamra.banquet.function_economics", {
      function: fn,
    }),

  // the customer as a person, not a string
  linkCustomer: (fn: string, guest?: string) =>
    call<{ ok: boolean; customer: string; customer_name: string }>(
      "kamra.banquet.link_customer",
      { function: fn, guest: guest ?? null },
    ),
  customerProfile: (params: { guest?: string; phone?: string }) =>
    banquetCall<CustomerProfile>("customer_profile", {
      guest: params.guest ?? null,
      phone: params.phone ?? null,
    }),

  closeOut: (fn: string, params: Record<string, unknown>) =>
    call<{
      ok: boolean
      status: FunctionStatus
      damage: number
      refunded: number
      deposit_held: number
      balance_due: number
    }>("kamra.banquet.close_out", { function: fn, ...params }),
  receiptDocument: (fn: string, receipt: string) =>
    call<ReceiptDocument>("kamra.banquet.receipt_document", {
      function: fn,
      receipt,
    }),
  menuCard: (fn: string) =>
    call<MenuCard>("kamra.banquet.menu_card", { function: fn }),
  monthAvailability: (month?: string) =>
    banquetCall<MonthAvailability>("month_availability", {
      month: month ?? null,
    }),
  register: (register: string, fromDate?: string, toDate?: string) =>
    banquetCall<BanquetRegister>("banquet_register", {
      register,
      from_date: fromDate ?? null,
      to_date: toDate ?? null,
    }),

  document: (fn: string, kind: DocumentKind) =>
    call<BanquetDocument>("kamra.banquet.banquet_document", {
      function: fn,
      kind,
    }),
  generateQuote: (fn: string, validDays = 15, note?: string) =>
    call<BanquetDocument>("kamra.banquet.generate_quote", {
      function: fn,
      valid_days: validDays,
      note: note ?? null,
    }),
  generateBeo: (fn: string) =>
    call<BanquetDocument>("kamra.banquet.generate_beo", { function: fn }),
  generateInvoice: (fn: string) =>
    call<BanquetDocument>("kamra.banquet.generate_invoice", { function: fn }),
  postToFolio: (fn: string, folio?: string) =>
    call<{
      ok: boolean
      folio: string
      posted: { item_name: string; amount: number }[]
      settle_separately: { item_name: string; amount: number }[]
      note: string | null
    }>("kamra.banquet.post_to_folio", { function: fn, folio: folio ?? null }),
}

// --- Assistant conversations (full-page module) ---
export interface ChatMsg {
  role: "user" | "assistant"
  content: string
  actions?: { tool: string; ok: boolean }[]
}
export interface ConversationSummary {
  name: string
  title: string
  modified: string
}
export const listConversations = () =>
  call<ConversationSummary[]>("kamra.assistant.list_conversations", {
    property: getCurrentProperty(),
  })
export const getConversation = (name: string) =>
  call<{ name: string; title: string; messages: ChatMsg[] }>(
    "kamra.assistant.get_conversation",
    { name },
  )
export const createConversation = (title?: string) =>
  call<{ name: string; title: string }>("kamra.assistant.create_conversation", {
    property: getCurrentProperty(),
    title: title ?? "New chat",
  })
export const saveConversation = (
  name: string,
  messages: ChatMsg[],
  title?: string,
) =>
  call<{ ok: boolean }>("kamra.assistant.save_conversation", {
    name,
    messages,
    title: title ?? null,
  })
export const deleteConversation = (name: string) =>
  call<{ ok: boolean }>("kamra.assistant.delete_conversation", { name })
export const renameConversation = (name: string, title: string) =>
  call<{ ok: boolean }>("kamra.assistant.rename_conversation", { name, title })

export const checkIn = (reservation: string) =>
  call("kamra.api.check_in", { reservation })

export const checkOut = (reservation: string) =>
  call("kamra.api.check_out", { reservation })

export const setHousekeepingStatus = (room: string, status: string) =>
  call("kamra.api.set_housekeeping_status", { room, status })

export interface ReservationDetail {
  name: string
  status: string
  source: string | null
  channel: string | null
  booking_type: string | null
  property: string
  check_in_date: string
  check_out_date: string
  nights: number
  adults: number
  children: number
  room: string | null
  room_type: string | null
  room_type_name: string | null
  meal_plan: string | null
  rate_plan: string | null
  special_requests: string | null
  eta: string | null
  precheckin_status: string | null
  precheckin_token: string | null
  amount_after_tax: number
  advance_paid: number
  company: string | null
  travel_agent: string | null
  folio_name: string | null
  money: { total: number; paid: number; due: number; has_folio: boolean }
  guest: {
    name: string
    full_name: string
    phone: string | null
    email: string | null
    vip: 0 | 1
    blacklisted: 0 | 1
    stays: number
    last_stay: string | null
  } | null
  booker: {
    name: string
    phone: string | null
    relation: string | null
    contact_preference: string | null
  } | null
  cancellation: {
    reason: string | null
    note: string | null
    number: string | null
    fee: number
    cancelled_on: string | null
  } | null
  id_document: string | null
  id_document_source: string | null
  id_document_on: string | null
  id_document_discarded: 0 | 1
  precheckin_verified_by: string | null
  precheckin_verified_on: string | null
  actions: {
    can_check_in: boolean
    can_check_out: boolean
    can_cancel: boolean
    can_amend: boolean
  }
  /** Things the desk should see but which must never gate an arrival. Kept
   *  apart from `actions` on purpose: a missing ID is a warning, not a
   *  capability, and conflating the two is how check-in quietly gets blocked. */
  warnings: {
    id_document_missing: boolean
    id_unverified: boolean
  }
}

export const reservationDetail = (name: string) =>
  call<ReservationDetail>("kamra.api.reservation_detail", { reservation: name })

/** The ID scan as a data URL. Served through a role-gated endpoint rather than
 *  its /private/files/ URL: Frappe would authorise that via the Reservation's
 *  doctype perms, which this site's Custom DocPerm rows deny to Front Desk. */
export const idDocumentImage = (reservation: string) =>
  call<{ data: string; captured_on: string }>("kamra.api.id_document_image", { reservation })

export const verifyPrecheckin = (reservation: string) =>
  call<{ ok: boolean; status: string }>("kamra.api.verify_precheckin", { reservation })

export const developerInfo = () =>
  call<{ user: string; has_key: boolean; base_url: string }>(
    "kamra.api.developer_info",
  )

export const generateApiKey = () =>
  call<{ api_key: string; api_secret: string }>("kamra.api.generate_api_key")

export const amendStay = (
  reservation: string,
  check_in_date: string,
  check_out_date: string,
) =>
  call<{ nights: number; amount_after_tax: number }>("kamra.api.amend_stay", {
    reservation,
    check_in_date,
    check_out_date,
  })
