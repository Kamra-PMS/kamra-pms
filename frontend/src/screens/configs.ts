import type { ScreenConfig } from "../components/ResourceScreen"
import { lazy } from "react"

// Drawer panels load when a row is opened, not with the app shell
const CompanyExtras = lazy(() => import("../components/CompanyExtras"))
const EventLinks = lazy(() => import("../components/EventLinks"))
const GroupControl = lazy(() => import("../components/GroupControl"))
const RoomTypeMedia = lazy(() => import("../components/RoomTypeMedia"))
const HkTaskMediaPanel = lazy(() =>
  import("../components/HkMedia").then((m) => ({ default: m.HkTaskMediaPanel })),
)
const ReservationDetail = lazy(() => import("./ReservationDetail"))
import { cur, locale } from "../lib/money"

export const roomsConfig: ScreenConfig = {
  doctype: "Room",
  title: "Rooms",
  description: "Physical rooms - number, type, floor and live status.",
  searchFields: ["room_number", "name"],
  filters: [{ field: "housekeeping_status", label: "Status", options: ["Clean", "Dirty", "Inspected", "Ready", "Out of Order"] }],
  pageSize: 25,
  propertyScoped: true,
  orderBy: "room_number asc",
  columns: [
    { field: "room_number", label: "Room" },
    { field: "room_type", label: "Type" },
    { field: "floor", label: "Floor" },
    { field: "housekeeping_status", label: "Housekeeping", badge: true },
    { field: "occupancy_status", label: "Occupancy", badge: true },
  ],
  form: [
    { field: "room_number", label: "Room number", type: "data", required: true },
    { field: "room_type", label: "Room type", type: "link", linkDoctype: "Room Type", required: true },
    { field: "floor", label: "Floor", type: "data" },
    { field: "housekeeping_status", label: "Housekeeping status", type: "select", options: ["Clean", "Dirty", "Inspected", "Out of Order"] },
    { field: "notes", label: "Notes", type: "data" },
  ],
}

export const roomTypesConfig: ScreenConfig = {
  doctype: "Room Type",
  title: "Room Types",
  description: "Categories with occupancy-based pricing.",
  propertyScoped: true,
  orderBy: "base_price asc",
  columns: [
    { field: "room_type_name", label: "Name" },
    { field: "room_type_code", label: "Code", badge: true },
    { field: "room_category", label: "Category" },
    { field: "base_price", label: `Base ${cur()}/night` },
    { field: "base_occupancy", label: "Base occ." },
    { field: "extra_adult_price", label: `Extra adult ${cur()}` },
    { field: "tax_percent", label: "GST %" },
  ],
  form: [
    { field: "room_type_name", label: "Name", type: "data", required: true },
    { field: "room_type_code", label: "Code (e.g. DLX)", type: "data", required: true },
    { field: "listing_slug", label: "Public listing URL slug (/stay/…)", type: "data" },
    { field: "room_category", label: "Category", type: "select", options: ["Villa", "Private", "Shared"] },
    { field: "base_price", label: "Base price / night", type: "currency", required: true },
    { field: "base_occupancy", label: "Adults included in base price", type: "int" },
    { field: "single_occupancy_price", label: "Single occupancy price", type: "currency", dependsOn: (d) => d.room_category !== "Villa" },
    { field: "extra_adult_price", label: "Extra adult / night", type: "currency" },
    { field: "small_group_max_adults", label: "Small-group threshold (adults)", type: "int", hint: "Below this many adults, price per person instead of the house rate. Blank or 0 = off" },
    { field: "small_group_price_per_adult", label: "Small-group price / adult", type: "currency", dependsOn: (d) => Number(d.small_group_max_adults) > 0 },
    { field: "small_group_days", label: "Small-group days (e.g. sun, mon, tue, wed, thu)", type: "data", hint: "Blank = every day", dependsOn: (d) => Number(d.small_group_max_adults) > 0 },
    { field: "small_group_whole_stay", label: "Small-group rate needs the whole stay", type: "check", hint: "A stay touching a non-small-group day is charged at the house rate throughout", dependsOn: (d) => Number(d.small_group_max_adults) > 0 },
    { field: "children_within_base_occupancy", label: "Children count towards base occupancy", type: "check", hint: "Only guests beyond the base occupancy are charged, children included" },
    { field: "max_extra_beds", label: "Guests allowed above capacity", type: "int", hint: "Only for a single unit with no second room to split into. 0 = never over capacity; the price is agreed on each booking" },
    { field: "child_price", label: "Child / night", type: "currency" },
    { field: "adults_capacity", label: "Max adults", type: "int" },
    { field: "children_capacity", label: "Max children", type: "int" },
    { field: "tax_percent", label: "GST %", type: "float" },
    { field: "bed_type", label: "Bed type", type: "select", options: ["King", "Queen", "Twin", "Double", "Single"], dependsOn: (d) => d.room_category !== "Villa" },
    { field: "air_conditioning", label: "Air Conditioning", type: "select", options: ["AC", "Non AC"], dependsOn: (d) => d.room_category !== "Villa" },
    // { field: "bathroom", label: "Bathroom Type", type: "select", options: ["Attached", "Common"], dependsOn: (d) => d.room_category !== "Villa" },
    // { field: "kitchen", label: "Kitchen Access", type: "check", dependsOn: (d) => d.room_category !== "Villa" },
    { field: "location_name", label: "Villa/site name (only if different from property)", type: "data" },
    { field: "location_slug", label: "Site URL slug (/stay/… for all listings here)", type: "data" },
    { field: "location_address", label: "Site address", type: "data" },
    { field: "google_maps_url", label: "Google Maps link", type: "data" },
    { field: "latitude", label: "Latitude", type: "float" },
    { field: "longitude", label: "Longitude", type: "float" },
    { field: "disabled", label: "Disabled", type: "check" },
  ],
  extra: RoomTypeMedia,
}

export const ratePlansConfig: ScreenConfig = {
  doctype: "Rate Plan",
  title: "Rate Plans",
  description:
    "Sellable plans (BAR, non-refundable, corporate). Clear Disabled to publish a plan at booking; tick it to unpublish.",
  searchFields: ["rate_plan_name", "code"],
  pageSize: 25,
  propertyScoped: true,
  columns: [
    { field: "rate_plan_name", label: "Name" },
    { field: "code", label: "Code", badge: true },
    { field: "modifier_type", label: "Modifier" },
    { field: "modifier_value", label: "Value" },
    { field: "is_default", label: "Default" },
    { field: "disabled", label: "Status", statusCheck: true },
  ],
  form: [
    { field: "rate_plan_name", label: "Name", type: "data", required: true },
    { field: "code", label: "Code", type: "data", required: true },
    { field: "modifier_type", label: "Modifier type", type: "select", options: ["Percent", "Amount", "Absolute"] },
    { field: "modifier_value", label: "Modifier value (-10 = 10% off)", type: "float" },
    { field: "cancellation_policy", label: "Cancellation policy", type: "data" },
    { field: "is_default", label: "Default plan", type: "check" },
    { field: "disabled", label: "Disabled (unpublished)", type: "check", hint: "Tick to unpublish; clear to activate at booking" },
  ],
}

export const seasonsConfig: ScreenConfig = {
  doctype: "Season",
  title: "Seasons",
  description:
    "Date ranges that lift or set nightly rates. Highest priority wins. Toggle Disabled to activate or pause a season.",
  propertyScoped: true,
  orderBy: "start_date asc",
  columns: [
    { field: "season_name", label: "Season" },
    { field: "start_date", label: "From" },
    { field: "end_date", label: "To" },
    { field: "adjustment_type", label: "Type" },
    { field: "adjustment_value", label: "Value" },
    { field: "days_of_week", label: "Days" },
    { field: "priority", label: "Priority" },
    { field: "disabled", label: "Status", statusCheck: true },
  ],
  form: [
    { field: "season_name", label: "Name", type: "data", required: true },
    { field: "room_type", label: "Room type (blank = all)", type: "link", linkDoctype: "Room Type" },
    { field: "start_date", label: "Start date", type: "date", required: true },
    { field: "end_date", label: "End date (inclusive)", type: "date", required: true },
    { field: "adjustment_type", label: "Adjustment", type: "select", options: ["Percent", "Amount", "Absolute"] },
    { field: "adjustment_value", label: "Value (20 = +20%)", type: "float" },
    { field: "days_of_week", label: "Days of week (e.g. fri, sat)", type: "data" },
    { field: "priority", label: "Priority", type: "int" },
    { field: "minimum_nights", label: "Minimum nights", type: "int", hint: "Shortest stay allowed on these dates. 0 = no minimum" },
    { field: "non_refundable", label: "Non-refundable", type: "check", hint: "A stay touching these dates cannot be cancelled free of charge" },
    { field: "full_payment", label: "Full payment on booking", type: "check", hint: "Online bookings on these dates pay the whole amount, not the usual advance" },
    { field: "advance_percent", label: "Advance % at booking", type: "float", hint: "Advance a booking on these dates owes (25, 50, 100). 0 = the property's usual deposit %. A stay crossing seasons owes the highest" },
    { field: "no_small_group", label: "No small-group rate", type: "check", hint: "Small parties pay the house rate on these dates, as on a weekend" },
    { field: "is_holiday", label: "Holiday / long weekend", type: "check", hint: "Quotes say these are holiday dates" },
    { field: "disabled", label: "Disabled", type: "check", hint: "Tick to deactivate; clear to activate" },
  ],
}

export const vouchersConfig: ScreenConfig = {
  doctype: "Discount Voucher",
  title: "Vouchers",
  description:
    "Discount codes guests or agents can apply at booking. Toggle Disabled to activate or deactivate a code.",
  searchFields: ["voucher_code"],
  pageSize: 25,
  propertyScoped: true,
  columns: [
    { field: "voucher_code", label: "Code", badge: true },
    { field: "discount_type", label: "Type" },
    { field: "value", label: "Value" },
    { field: "valid_to", label: "Valid until" },
    { field: "min_nights", label: "Min nights" },
    { field: "times_used", label: "Used" },
    { field: "max_uses", label: "Max uses" },
    { field: "disabled", label: "Status", statusCheck: true },
  ],
  form: [
    { field: "voucher_code", label: "Code", type: "data", required: true },
    { field: "discount_type", label: "Type", type: "select", options: ["Percent", "Amount"] },
    { field: "value", label: `Value (10 = 10% or ${cur()}10)`, type: "float", required: true },
    { field: "valid_from", label: "Valid from", type: "date" },
    { field: "valid_to", label: "Valid to", type: "date" },
    { field: "min_nights", label: "Minimum nights", type: "int" },
    { field: "max_uses", label: "Max uses (0 = unlimited)", type: "int" },
    { field: "times_used", label: "Times used", type: "readonly" },
    { field: "disabled", label: "Disabled", type: "check", hint: "Tick to deactivate; clear to activate" },
  ],
}

export const longStayConfig: ScreenConfig = {
  doctype: "Long Stay Discount",
  title: "Long-stay Discounts",
  description:
    "A percentage off each room night for stays of N nights or more. The highest tier a stay reaches applies, and no night goes below its guardrail floor.",
  propertyScoped: true,
  orderBy: "min_nights asc",
  columns: [
    { field: "min_nights", label: "From nights" },
    { field: "discount_percent", label: "Discount %" },
    { field: "room_type", label: "Room type (blank = all)" },
    { field: "disabled", label: "Status", statusCheck: true },
  ],
  form: [
    { field: "min_nights", label: "Stays of at least (nights)", type: "int", required: true },
    { field: "discount_percent", label: "Discount % off the room rate", type: "float", required: true },
    { field: "room_type", label: "Room type (blank = all)", type: "link", linkDoctype: "Room Type" },
    { field: "disabled", label: "Disabled", type: "check", hint: "Tick to deactivate; clear to activate" },
  ],
}

export const mealPlansConfig: ScreenConfig = {
  doctype: "Meal Plan",
  title: "Meal Plans",
  description: "Board basis added per person, per night.",
  propertyScoped: true,
  columns: [
    { field: "code", label: "Code", badge: true },
    { field: "label", label: "Label" },
    { field: "price_per_adult", label: `${cur()} / adult / night` },
    { field: "price_per_child", label: `${cur()} / child / night` },
    { field: "is_default", label: "Default" },
  ],
  form: [
    { field: "code", label: "Code", type: "select", options: ["EP", "CP", "MAP", "AP"], required: true },
    { field: "label", label: "Label", type: "data" },
    { field: "price_per_adult", label: "Price per adult / night", type: "currency" },
    { field: "price_per_child", label: "Price per child / night", type: "currency" },
    { field: "is_default", label: "Default", type: "check" },
    { field: "disabled", label: "Disabled", type: "check" },
  ],
}

export const experiencesConfig: ScreenConfig = {
  doctype: "Experience",
  title: "Experiences",
  description:
    "Add-ons sold with a stay - spa, tours, dinners, transfers. Ticked ones show on /book.",
  searchFields: ["experience_name"],
  filters: [
    { field: "category", label: "Category", options: ["Spa", "Tour", "Dining", "Activity", "Transport", "Other"] },
  ],
  pageSize: 25,
  propertyScoped: true,
  orderBy: "experience_name asc",
  columns: [
    { field: "experience_name", label: "Experience" },
    { field: "category", label: "Category", badge: true },
    { field: "price", label: `Price ${cur()}` },
    { field: "duration", label: "Duration" },
    { field: "show_on_booking_page", label: "On booking page" },
  ],
  form: [
    { field: "experience_name", label: "Name", type: "data", required: true },
    { field: "category", label: "Category", type: "select", options: ["Spa", "Tour", "Dining", "Activity", "Transport", "Other"] },
    { field: "price", label: "Price", type: "currency" },
    { field: "gst_rate", label: "Tax %", type: "float" },
    { field: "duration", label: "Duration (e.g. 90 min, half day)", type: "data" },
    { field: "description", label: "Description (shown to guests)", type: "data" },
    { field: "image_url", label: "Photo", type: "image" },
    { field: "show_on_booking_page", label: "Show on the public booking page", type: "check" },
    { field: "disabled", label: "Disabled", type: "check" },
  ],
}

export const travelAgentsConfig: ScreenConfig = {
  doctype: "Travel Agent",
  title: "Travel Agents",
  description: "Business sources with commission tracking - commissions compute automatically on their bookings.",
  searchFields: ["agent_name"],
  pageSize: 25,
  columns: [
    { field: "agent_name", label: "Agent" },
    { field: "agent_type", label: "Type", badge: true },
    { field: "commission_pct", label: "Commission %" },
    { field: "contact_phone", label: "Phone" },
  ],
  form: [
    { field: "agent_name", label: "Agent name", type: "data", required: true },
    { field: "agent_type", label: "Type", type: "select", options: ["Travel Agent", "OTA", "Tour Operator", "Corporate Desk"] },
    { field: "commission_pct", label: "Commission %", type: "float" },
    { field: "contact_name", label: "Contact name", type: "data" },
    { field: "contact_phone", label: "Contact phone", type: "data" },
    { field: "contact_email", label: "Contact email", type: "data" },
    { field: "disabled", label: "Disabled", type: "check" },
  ],
}

export const venuesConfig: ScreenConfig = {
  doctype: "Venue",
  title: "Halls & Venues",
  description:
    "Banquet halls, lawns, poolsides, board rooms - the spaces functions are sold into.",
  propertyScoped: true,
  searchFields: ["venue_name", "venue_code"],
  filters: [
    {
      field: "venue_type",
      label: "Type",
      options: [
        "Banquet Hall",
        "Lawn",
        "Poolside",
        "Rooftop",
        "Board Room",
        "Conference Hall",
        "Restaurant",
        "Other",
      ],
    },
  ],
  columns: [
    { field: "venue_name", label: "Venue" },
    { field: "venue_type", label: "Type", badge: true },
    { field: "capacity", label: "Seats" },
    { field: "base_price", label: `Day rental ${cur()}` },
    { field: "hourly_rate", label: `Per hour ${cur()}` },
  ],
  form: [
    { field: "venue_name", label: "Venue name", type: "data", required: true },
    { field: "venue_code", label: "Code (prints on the event order)", type: "data" },
    {
      field: "venue_type",
      label: "Type",
      type: "select",
      options: [
        "Banquet Hall",
        "Lawn",
        "Poolside",
        "Rooftop",
        "Board Room",
        "Conference Hall",
        "Restaurant",
        "Other",
      ],
    },
    { field: "capacity", label: "Seats (maximum pax)", type: "int" },
    { field: "min_capacity", label: "Minimum pax it's worth opening for", type: "int" },
    { field: "area_sqft", label: "Area (sq ft)", type: "int" },
    { field: "base_price", label: "Day rental", type: "currency" },
    { field: "hourly_rate", label: "Hourly rental", type: "currency" },
    { field: "min_hours", label: "Minimum hours", type: "int" },
    { field: "gst_rate", label: "Rental GST %", type: "int" },
    { field: "setup_styles", label: "Layouts it takes", type: "data" },
    { field: "amenities", label: "Amenities", type: "data" },
    { field: "disabled", label: "Disabled", type: "check" },
  ],
}

export const roomBlocksConfig: ScreenConfig = {
  doctype: "Room Block",
  title: "Room Blocks",
  description:
    "Hold rooms out of sale for house use, VIPs, owners or maintenance. Blocked rooms don't show as available and won't sell.",
  searchFields: ["room", "note"],
  filters: [
    { field: "reason", label: "Reason", options: ["House Use", "VIP Hold", "Owner", "Maintenance", "Other"] },
    { field: "block_status", label: "Status", options: ["Active", "Released"] },
  ],
  pageSize: 25,
  propertyScoped: true,
  orderBy: "from_date asc",
  columns: [
    { field: "room", label: "Room" },
    { field: "reason", label: "Reason", badge: true },
    { field: "from_date", label: "From" },
    { field: "to_date", label: "To" },
    { field: "block_status", label: "Status", badge: true },
    { field: "note", label: "Note" },
  ],
  form: [
    { field: "room", label: "Room", type: "link", linkDoctype: "Room", required: true },
    { field: "reason", label: "Reason", type: "select", options: ["House Use", "VIP Hold", "Owner", "Maintenance", "Other"], required: true },
    { field: "from_date", label: "From date", type: "date", required: true },
    { field: "to_date", label: "To date (exclusive)", type: "date", required: true },
    { field: "block_status", label: "Status", type: "select", options: ["Active", "Released"] },
    { field: "note", label: "Note", type: "data" },
  ],
}

const FUNCTION_STATUSES = [
  "Enquiry",
  "Tentative",
  "Confirmed",
  "Completed",
  "Cancelled",
  "Lost",
]

export const venueBookingsConfig: ScreenConfig = {
  doctype: "Venue Booking",
  dateFilter: { field: "event_date", label: "Event date" },
  title: "All Functions",
  description:
    "Every function, one row each: enquiry → tentative → confirmed → completed. Open one to work on it properly.",
  searchFields: ["customer_name", "venue", "event_name"],
  filters: [
    { field: "status", label: "Status", options: FUNCTION_STATUSES },
    {
      field: "event_type",
      label: "Type",
      options: [
        "Wedding",
        "Reception",
        "Sangeet",
        "Conference",
        "Seminar",
        "Product Launch",
        "Birthday",
        "Corporate Offsite",
        "Other",
      ],
    },
  ],
  pageSize: 25,
  propertyScoped: true,
  orderBy: "event_date asc",
  columns: [
    { field: "name", label: "Ref" },
    { field: "customer_name", label: "Customer" },
    { field: "venue", label: "Hall" },
    { field: "event_type", label: "Type", badge: true },
    { field: "event_date", label: "Date" },
    { field: "pax_guaranteed", label: "Pax" },
    { field: "status", label: "Status", badge: true },
    { field: "grand_total", label: `Quote ${cur()}` },
    { field: "balance_due", label: `Due ${cur()}` },
  ],
  // The money, the menus and the negotiation live on the function sheet -
  // this form only carries the facts you'd fix in a hurry.
  form: [
    { field: "venue", label: "Hall", type: "link", linkDoctype: "Venue", required: true },
    { field: "event_type", label: "Event type", type: "select", options: ["Wedding", "Reception", "Sangeet", "Mehendi", "Engagement", "Conference", "Seminar", "Training", "Product Launch", "Birthday", "Anniversary", "Corporate Offsite", "Exhibition", "Other"] },
    { field: "event_name", label: "Event name", type: "data" },
    { field: "event_date", label: "Event date", type: "date", required: true },
    { field: "end_date", label: "Ends (multi-day only)", type: "date" },
    { field: "customer_name", label: "Customer name", type: "data", required: true },
    { field: "customer_phone", label: "Customer phone", type: "data" },
    { field: "customer_email", label: "Customer email", type: "data" },
    { field: "company", label: "Company", type: "link", linkDoctype: "Corporate Account" },
    { field: "attendees", label: "Expected pax", type: "int" },
    { field: "pax_guaranteed", label: "Guaranteed pax", type: "int" },
    { field: "status", label: "Status", type: "select", options: FUNCTION_STATUSES },
    { field: "follow_up_date", label: "Next follow-up", type: "date" },
    { field: "grand_total", label: "Quote total", type: "readonly" },
    { field: "advance_received", label: "Received", type: "readonly" },
    { field: "balance_due", label: "Balance due", type: "readonly" },
    { field: "requirements", label: "What they asked for", type: "data" },
  ],
  extra: EventLinks,
}

export const lostFoundConfig: ScreenConfig = {
  doctype: "Lost And Found Item",
  title: "Lost & Found",
  description: "Items found on property; track storage and returns.",
  propertyScoped: true,
  orderBy: "found_on desc",
  searchFields: ["item_description", "found_by"],
  filters: [
    { field: "condition", label: "Kind", options: ["Found", "Missing", "Damaged"] },
    { field: "status", label: "Status", options: ["In Storage", "Returned", "Disposed"] },
  ],
  columns: [
    { field: "name", label: "Ref" },
    { field: "condition", label: "Kind", badge: true },
    { field: "item_description", label: "Item" },
    { field: "found_in_room", label: "Room" },
    { field: "found_on", label: "Logged" },
    { field: "status", label: "Status", badge: true },
  ],
  form: [
    { field: "condition", label: "Kind", type: "select", options: ["Found", "Missing", "Damaged"], required: true },
    { field: "item_description", label: "Item", type: "data", required: true },
    { field: "found_in_room", label: "Room", type: "link", linkDoctype: "Room" },
    { field: "found_on", label: "Logged on", type: "date", required: true },
    { field: "found_by", label: "Logged by", type: "data" },
    { field: "status", label: "Status", type: "select", options: ["In Storage", "Returned", "Disposed"] },
    { field: "guest", label: "Guest (if known)", type: "link", linkDoctype: "Guest" },
    { field: "returned_on", label: "Returned on", type: "date" },
    { field: "notes", label: "Notes", type: "data" },
  ],
}

export const shiftsConfig: ScreenConfig = {
  doctype: "Shift Handover",
  title: "Shift Handover",
  description: "Cash count and follow-ups passed between shifts.",
  propertyScoped: true,
  orderBy: "shift_date desc",
  columns: [
    { field: "name", label: "Shift" },
    { field: "shift_date", label: "Date" },
    { field: "shift", label: "Slot", badge: true },
    { field: "status", label: "Status", badge: true },
    { field: "closing_cash", label: `Closing cash ${cur()}` },
  ],
  form: [
    { field: "shift", label: "Shift", type: "select", options: ["Morning", "Evening", "Night"], required: true },
    { field: "shift_date", label: "Date", type: "date", required: true, notPast: true },
    { field: "opening_cash", label: "Opening cash", type: "currency" },
    { field: "cash_collected", label: "Cash collected", type: "currency" },
    { field: "payouts", label: "Payouts", type: "currency" },
    { field: "closing_cash", label: "Closing cash", type: "currency" },
    { field: "handed_over_to", label: "Handed over to", type: "link", linkDoctype: "User" },
    { field: "status", label: "Status", type: "select", options: ["Open", "Closed"] },
    { field: "handover_notes", label: "Handover notes", type: "data" },
  ],
}

export const guardrailsConfig: ScreenConfig = {
  doctype: "Rate Guardrail",
  title: "Rate Guardrails",
  description:
    "Owner-set floor and ceiling. No rate move - human or AI agent - can price outside these rails. Toggle Disabled to activate or pause a rail.",
  propertyScoped: true,
  columns: [
    { field: "name", label: "Rail" },
    { field: "room_type", label: "Room type (blank = all)" },
    { field: "floor_price", label: `Floor ${cur()}` },
    { field: "ceiling_price", label: `Ceiling ${cur()}` },
    { field: "days_of_week", label: "Days" },
    { field: "disabled", label: "Status", statusCheck: true },
  ],
  form: [
    { field: "room_type", label: "Room type (blank = all)", type: "link", linkDoctype: "Room Type" },
    { field: "floor_price", label: "Floor price / night", type: "currency", required: true },
    { field: "ceiling_price", label: "Ceiling price / night", type: "currency", required: true },
    { field: "days_of_week", label: "Days of week (e.g. fri, sat)", type: "data", hint: "Blank = every day. Lets a weekend floor sit above the midweek one" },
    { field: "disabled", label: "Disabled", type: "check", hint: "Tick to deactivate; clear to activate" },
  ],
}

export const companiesConfig: ScreenConfig = {
  doctype: "Corporate Account",
  title: "Accounts Receivable",
  description: "Companies with negotiated rates and credit terms.",
  searchFields: ["company_name", "gstin"],
  pageSize: 25,
  columns: [
    { field: "company_name", label: "Company" },
    { field: "gstin", get label() { return locale().tax_id_label } },
    { field: "contact_name", label: "Contact" },
    { field: "contact_phone", label: "Phone" },
    { field: "credit_allowed", label: "Credit" },
  ],
  form: [
    { field: "company_name", label: "Company name", type: "data", required: true },
    { field: "gstin", get label() { return locale().tax_id_label }, type: "data" },
    { field: "contact_name", label: "Contact name", type: "data" },
    { field: "contact_phone", label: "Contact phone", type: "data" },
    { field: "contact_email", label: "Contact email", type: "data" },
    { field: "negotiated_rate_plan", label: "Negotiated rate plan", type: "link", linkDoctype: "Rate Plan" },
    { field: "credit_allowed", label: "Credit allowed (city ledger)", type: "check" },
    { field: "disabled", label: "Disabled", type: "check" },
  ],
  extra: CompanyExtras,
}

export const housekeepingConfig: ScreenConfig = {
  doctype: "Housekeeping Task",
  title: "Housekeeping Tasks",
  description: "Cleans and inspections. Completing a task updates the room's live status.",
  searchFields: ["room"],
  filters: [{ field: "status", label: "Status", options: ["Pending", "In Progress", "Done", "Verified"] }],
  pageSize: 25,
  propertyScoped: true,
  orderBy: "creation desc",
  columns: [
    { field: "name", label: "Task" },
    { field: "room", label: "Room" },
    { field: "task_type", label: "Type", badge: true },
    { field: "priority", label: "Priority" },
    { field: "status", label: "Status", badge: true },
  ],
  form: [
    { field: "room", label: "Room", type: "link", linkDoctype: "Room", linkPropertyScoped: true, required: true },
    { field: "task_type", label: "Type", type: "select", options: ["Checkout Clean", "Stayover Clean", "Deep Clean", "Inspection", "Maintenance"] },
    { field: "priority", label: "Priority", type: "select", options: ["Low", "Medium", "High", "Urgent"] },
    { field: "status", label: "Status", type: "select", options: ["Pending", "In Progress", "Done", "Verified"] },
    { field: "notes", label: "Notes", type: "data" },
  ],
  extra: HkTaskMediaPanel,
}

export const reservationsConfig: ScreenConfig = {
  doctype: "Reservation",
  title: "Reservations",
  dateFilter: { field: "check_in_date", label: "Check-in" },
  description: "All bookings. Create new ones with the New booking button above.",
  propertyScoped: true,
  allowCreate: false,
  orderBy: "check_in_date desc",
  searchFields: ["name", "guest_name", "room"],
  filters: [
    {
      field: "status",
      label: "Status",
      options: [
        "Requested",
        "Held",
        "Pending Payment",
        "Waitlist",
        "Confirmed",
        "Checked In",
        "Checked Out",
        "Cancelled",
        "No Show",
      ],
    },
  ],
  pageSize: 25,
  columns: [
    { field: "name", label: "Ref" },
    { field: "guest_name", label: "Guest" },
    { field: "room", label: "Room" },
    { field: "check_in_date", label: "In" },
    { field: "check_out_date", label: "Out" },
    { field: "status", label: "Status", badge: true },
    { field: "booking_type", label: "Type" },
    { field: "source", label: "Source" },
    { field: "amount_after_tax", label: `Total ${cur()}` },
    { field: "advance_paid", label: `Advance ${cur()}` },
  ],
  // Editing happens in the bespoke detail panel; keep a minimal form as the
  // fallback shape the generic screen still expects.
  form: [
    { field: "special_requests", label: "Special requests", type: "data" },
  ],
  detailPanel: ReservationDetail,
}

export const groupsConfig: ScreenConfig = {
  doctype: "Group Booking",
  dateFilter: { field: "check_in_date", label: "Arrival" },
  title: "Groups & Blocks",
  description: "Group Rooms Control - blocks, pickup and rooming lists.",
  propertyScoped: true,
  orderBy: "check_in_date desc",
  pageSize: 25,
  searchFields: ["group_name", "company"],
  filters: [
    { field: "status", label: "Status", options: ["Open", "Confirmed", "Cancelled"] },
  ],
  columns: [
    { field: "group_name", label: "Group" },
    { field: "company", label: "Company" },
    { field: "check_in_date", label: "Arrive" },
    { field: "check_out_date", label: "Depart" },
    { field: "cutoff_date", label: "Cutoff" },
    { field: "status", label: "Status", badge: true },
  ],
  form: [
    { field: "group_name", label: "Group name", type: "data", required: true },
    { field: "company", label: "Company", type: "link", linkDoctype: "Corporate Account" },
    { field: "check_in_date", label: "Arrival", type: "date", required: true },
    { field: "check_out_date", label: "Departure", type: "date", required: true },
    { field: "cutoff_date", label: "Block cutoff", type: "date" },
    { field: "status", label: "Status", type: "select", options: ["Open", "Confirmed", "Cancelled"] },
    { field: "notes", label: "Notes", type: "data" },
  ],
  detailPanel: GroupControl,
}

export const outletsConfig: ScreenConfig = {
  doctype: "POS Outlet",
  title: "Outlets",
  description: "Restaurants, bars and other points of sale.",
  propertyScoped: true,
  columns: [
    { field: "outlet_name", label: "Outlet" },
    { field: "outlet_type", label: "Type", badge: true },
    { field: "gst_rate", label: "GST %" },
  ],
  form: [
    { field: "outlet_name", label: "Outlet name", type: "data", required: true },
    { field: "outlet_type", label: "Type", type: "select", options: ["Restaurant", "Room Service", "Bar", "Spa", "Other"] },
    { field: "gst_rate", label: "GST %", type: "float" },
    { field: "disabled", label: "Disabled", type: "check" },
    {
      field: "kot_mode",
      label: "KOT on send",
      type: "select",
      options: ["Use F&B setting", "Auto-accept and print", "Kitchen presses Start"],
      hint: "Auto-accept and print: sending an order prints the KOT and shows it on the kitchen display as started. Kitchen presses Start: the pass accepts each ticket. Use F&B setting follows Settings > F&B.",
    },
  ],
}

export const ingredientsConfig: ScreenConfig = {
  doctype: "Ingredient",
  title: "Ingredients",
  description:
    "The kitchen store cupboard - name, unit, category and cost. Stock movements live under Kitchen Inventory; recipes under Menu → Recipes.",
  searchFields: ["ingredient_name", "category"],
  filters: [
    { field: "is_active", label: "Active", options: ["1", "0"] },
  ],
  pageSize: 50,
  propertyScoped: true,
  orderBy: "category, ingredient_name",
  columns: [
    { field: "ingredient_name", label: "Ingredient" },
    { field: "category", label: "Category" },
    { field: "uom", label: "Unit", badge: true },
    { field: "cost_per_unit", label: `Cost / unit` },
    { field: "is_active", label: "Active", badge: true },
  ],
  form: [
    { field: "ingredient_name", label: "Ingredient", type: "data", required: true },
    { field: "category", label: "Category", type: "data",
      hint: "Produce, Dairy, Dry Goods, Bar - free text" },
    { field: "uom", label: "Unit", type: "select", required: true,
      options: ["kg", "g", "L", "ml", "pc", "bottle", "packet"],
      hint: "One unit only. Recipes and purchases both use it - buy and cook in the same unit (e.g. define in g if you cook in g)." },
    { field: "cost_per_unit", label: "Cost / unit", type: "currency",
      hint: "Last known cost, used to value wastage. Indicative only - not FIFO and not on the books." },
    { field: "gst_rate", label: "Input GST %", type: "float",
      hint: "Tax paid when buying this." },
    { field: "is_active", label: "Active", type: "check",
      hint: "Turn off instead of deleting when a recipe or stock history uses it." },
  ],
}

export const menuItemsConfig: ScreenConfig = {
  doctype: "Menu Item",
  title: "Menu",
  description:
    "Dishes and drinks across your outlets - photo, price, veg/non-veg. Allergens, stations and courses are edited under Settings → F&B → Menu master lists.",
  searchFields: ["item_name", "category"],
  pageSize: 50,
  propertyScoped: true,
  orderBy: "category, item_name",
  columns: [
    { field: "item_name", label: "Item" },
    { field: "outlet", label: "Outlet" },
    { field: "category", label: "Category" },
    { field: "price", label: "Price" },
    { field: "available", label: "Available", badge: true },
  ],
  form: [
    { field: "outlet", label: "Outlet", type: "link", linkDoctype: "POS Outlet", required: true },
    { field: "item_name", label: "Item name", type: "data", required: true },
    { field: "category", label: "Category", type: "data", optionsFrom: "categories",
      hint: "Pick a suggestion or type a new one" },
    { field: "price", label: "Price", type: "currency", required: true },
    { field: "image", label: "Photo", type: "image",
      hint: "800x600px landscape JPG/WebP, under 500 KB - shows on the POS card" },
    { field: "description", label: "Description", type: "data" },
    { field: "course", label: "Course", type: "select", optionsFrom: "courses",
      options: ["Starter", "Main", "Dessert", "Drink"],
      hint: "When it is served - kitchen holds later courses until the table is ready" },
    { field: "prep_station", label: "Prep station", type: "select",
      optionsFrom: "prep_stations",
      options: ["Kitchen", "Tandoor", "Grill", "Fryer", "Bar"],
      hint: "Which KOT this item prints to" },
    { field: "allergens", label: "Allergens & dietary tags", type: "tags",
      optionsFrom: "allergens",
      options: ["Egg", "Dairy", "Nuts", "Peanuts", "Gluten", "Soy", "Shellfish", "Fish", "Sesame", "Sulphites"],
      hint: "Edit the list under Settings → F&B → Menu master lists. Matched against the guest allergy note on the kitchen display." },
    { field: "is_veg", label: "Vegetarian", type: "check" },
    { field: "is_alcohol", label: "Alcohol", type: "check",
      hint: "Alcohol always bills the guest folio, never the company" },
    { field: "available", label: "Available", type: "check" },
  ],
}

export const channelConnectionsConfig: ScreenConfig = {
  doctype: "Channel Provider Connection",
  title: "Channels",
  description:
    "Phone and messaging lines connected to this property. For WhatsApp on your own number, add a Meta Business connection: phone number ID, access token, webhook verify token, and the names of your approved templates.",
  searchFields: ["phone_number", "provider"],
  filters: [
    { field: "channel", label: "Channel", options: ["WhatsApp", "Voice", "SMS"] },
    { field: "active", label: "Active", options: ["1", "0"] },
  ],
  pageSize: 20,
  propertyScoped: true,
  orderBy: "modified desc",
  columns: [
    { field: "channel", label: "Channel", badge: true },
    { field: "provider", label: "Provider" },
    { field: "phone_number", label: "Number" },
    { field: "active", label: "Active", badge: true },
  ],
  form: [
    { field: "channel", label: "Channel", type: "select", options: ["WhatsApp", "Voice", "SMS"], required: true },
    { field: "provider", label: "Provider", type: "select", options: ["Meta Business", "HeyKoala", "Twilio", "Retell", "Vapi", "Custom"], required: true },
    { field: "phone_number", label: "Phone number (display)", type: "data" },
    { field: "external_account_id", label: "Meta phone number ID", type: "data", hint: "From Meta Business Manager > WhatsApp > API setup" },
    { field: "credentials", label: "Access token", type: "data", hint: "Permanent Cloud API token - stored encrypted" },
    { field: "webhook_secret", label: "Webhook verify token", type: "data", hint: "Any string; use the same one in Meta's webhook setup" },
    { field: "app_secret", label: "Meta App Secret", type: "data", hint: "App settings > Basic. Required: inbound messages are signature-checked with it - stored encrypted" },
    { field: "meta_language", label: "Template language code", type: "data" },
    { field: "tpl_booking_confirmation", label: "Template: booking confirmation", type: "data", hint: "Args: guest, property, check-in, check-out" },
    { field: "tpl_precheckin", label: "Template: self check-in link", type: "data", hint: "Args: guest, link" },
    { field: "tpl_payment_request", label: "Template: payment request", type: "data", hint: "Args: guest, amount, note" },
    { field: "tpl_room_charge", label: "Template: room charge alert", type: "data", hint: "Args: guest, amount, what and where, balance. Sent only when Front Desk settings turn on room charge alerts" },
    { field: "active", label: "Active", type: "check" },
  ],
}

export const channelManagerConfig: ScreenConfig = {
  doctype: "Channel Manager Connection",
  title: "Channel Manager",
  description:
    "Two-way OTA sync through a channel manager. Bring your own Channex.io account (self-serve, covers Booking.com / Agoda / Expedia / Airbnb); STAAH and AioSell adapters activate with their partner credentials. Map your room types under OTA Room Mappings, then availability and rates push automatically every hour and after every booking - and their bookings land as reservations here.",
  searchFields: ["provider", "external_property_id"],
  filters: [
    { field: "provider", label: "Provider", options: ["Channex", "STAAH", "AioSell", "Custom"] },
    { field: "active", label: "Active", options: ["1", "0"] },
  ],
  pageSize: 20,
  propertyScoped: true,
  orderBy: "modified desc",
  columns: [
    { field: "provider", label: "Provider", badge: true },
    { field: "external_property_id", label: "Property ID" },
    { field: "last_push", label: "Last push" },
    { field: "last_push_status", label: "Result" },
    { field: "active", label: "Active", badge: true },
  ],
  form: [
    { field: "provider", label: "Provider", type: "select", options: ["Channex", "STAAH", "AioSell", "Custom"], required: true },
    { field: "api_key", label: "API key / token", type: "data", hint: "Stored encrypted. Channex: your user API key; STAAH/AioSell: from partner onboarding" },
    { field: "external_property_id", label: "Provider's property ID", type: "data", required: true },
    { field: "endpoint", label: "API endpoint override", type: "data", hint: "Leave blank for the provider default" },
    { field: "webhook_secret", label: "Webhook secret", type: "data", hint: "Set the same value on the provider's booking webhook" },
    { field: "sync_days", label: "Days to push", type: "int" },
    { field: "active", label: "Active", type: "check" },
  ],
}

export const channelRoomMappingsConfig: ScreenConfig = {
  doctype: "Channel Room Mapping",
  title: "OTA Room Mappings",
  description:
    "Your room types matched to the channel manager's room and rate-plan ids. Every mapped type gets availability and rates pushed; incoming bookings resolve their room through this table.",
  searchFields: ["external_room_id", "room_type"],
  pageSize: 30,
  orderBy: "modified desc",
  columns: [
    { field: "connection", label: "Connection" },
    { field: "room_type", label: "Room Type" },
    { field: "external_room_id", label: "Provider room ID" },
    { field: "external_rate_id", label: "Provider rate ID" },
  ],
  form: [
    { field: "connection", label: "Connection", type: "link", linkDoctype: "Channel Manager Connection", linkPropertyScoped: true, required: true },
    { field: "room_type", label: "Room type", type: "link", linkDoctype: "Room Type", linkPropertyScoped: true, required: true },
    { field: "external_room_id", label: "Provider room ID", type: "data", required: true },
    { field: "external_rate_id", label: "Provider rate plan ID", type: "data" },
  ],
}

export const reasonCodesConfig: ScreenConfig = {
  doctype: "Reason Code",
  title: "Reason Codes",
  description:
    "Coded reasons for voids, adjustments, refunds and paid-outs. Prefer these over free text so Voids & Allowances and audits stay consistent. Defaults are seeded; disable instead of deleting codes already on the books.",
  searchFields: ["code", "description"],
  filters: [
    { field: "category", label: "Category",
      options: ["Void", "Adjust", "Rate Change", "Refund", "Paid Out", "NC"] },
    { field: "disabled", label: "Disabled", options: ["0", "1"] },
  ],
  pageSize: 50,
  orderBy: "category, code",
  columns: [
    { field: "code", label: "Code" },
    { field: "description", label: "Description" },
    { field: "category", label: "Category", badge: true },
    { field: "requires_supervisor", label: "Supervisor", badge: true },
    { field: "disabled", label: "Status", statusCheck: true },
  ],
  form: [
    { field: "code", label: "Code", type: "data", required: true,
      hint: "Short stable id (e.g. VOID-GUEST). Becomes the document name - do not rename after use." },
    { field: "description", label: "Description", type: "data", required: true },
    { field: "category", label: "Category", type: "select", required: true,
      options: ["Void", "Adjust", "Rate Change", "Refund", "Paid Out", "NC"] },
    { field: "requires_supervisor", label: "Requires supervisor", type: "check",
      hint: "Only Finance / Hotel Admin may use this code when ticked." },
    { field: "disabled", label: "Disabled", type: "check",
      hint: "Turn off instead of deleting when a void or refund already used it." },
  ],
}

export const transactionCodesConfig: ScreenConfig = {
  doctype: "Transaction Code",
  title: "Transaction Codes",
  description:
    "Chart of posting codes for the folio journal - revenue, payment, tax, package and adjustment. Ledgers and night audit group by these. Leave Property blank for every property; set it to override for one hotel only.",
  searchFields: ["code", "description", "revenue_group"],
  filters: [
    { field: "txn_type", label: "Type",
      options: ["Revenue", "Payment", "Tax", "Package", "Adjustment"] },
    { field: "disabled", label: "Disabled", options: ["0", "1"] },
  ],
  pageSize: 50,
  orderBy: "txn_type, code",
  columns: [
    { field: "code", label: "Code" },
    { field: "description", label: "Description" },
    { field: "txn_type", label: "Type", badge: true },
    { field: "revenue_group", label: "Group" },
    { field: "default_tax_rate", label: "Tax %" },
    { field: "disabled", label: "Status", statusCheck: true },
  ],
  form: [
    { field: "code", label: "Code", type: "data", required: true,
      hint: "Short stable id (e.g. 1000). Becomes the document name - do not rename after use." },
    { field: "description", label: "Description", type: "data", required: true },
    { field: "property", label: "Property", type: "link", linkDoctype: "Property",
      hint: "Blank = all properties. Set only for a property-specific override." },
    { field: "txn_type", label: "Type", type: "select", required: true,
      options: ["Revenue", "Payment", "Tax", "Package", "Adjustment"] },
    { field: "revenue_group", label: "Revenue group", type: "data",
      hint: "e.g. Rooms, F&B, Other - used on ledgers and exports." },
    { field: "subgroup", label: "Subgroup", type: "data" },
    { field: "default_tax_rate", label: "Default tax %", type: "float" },
    { field: "is_alcohol", label: "Alcohol", type: "check",
      hint: "Alcohol never bills a Company folio." },
    { field: "charge_type", label: "Legacy charge type", type: "select",
      options: [
        "Room", "Meal Plan", "Food & Beverage", "Minibar", "Laundry", "Spa", "Taxi",
        "Early Check-in", "Late Checkout", "Early Departure", "Cleaning Fee", "Extra Guests",
        "Pet Charge", "Room Levy", "Discount", "Misc", "Allowance", "Opening Balance",
      ],
      hint: "Maps to Folio Charge.charge_type for display on older lines." },
    { field: "disabled", label: "Disabled", type: "check",
      hint: "Turn off instead of deleting when the journal already posted it." },
  ],
}
