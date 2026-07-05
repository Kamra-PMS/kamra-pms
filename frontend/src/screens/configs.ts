import type { ScreenConfig } from "../components/ResourceScreen"
import BillingRulesEditor from "../components/BillingRulesEditor"

export const roomsConfig: ScreenConfig = {
  doctype: "Room",
  title: "Rooms",
  description: "Physical rooms — number, type, floor and live status.",
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
    { field: "base_price", label: "Base ₹/night" },
    { field: "base_occupancy", label: "Base occ." },
    { field: "extra_adult_price", label: "Extra adult ₹" },
    { field: "tax_percent", label: "GST %" },
  ],
  form: [
    { field: "room_type_name", label: "Name", type: "data", required: true },
    { field: "room_type_code", label: "Code (e.g. DLX)", type: "data", required: true },
    { field: "base_price", label: "Base price / night", type: "currency", required: true },
    { field: "base_occupancy", label: "Adults included in base price", type: "int" },
    { field: "single_occupancy_price", label: "Single occupancy price", type: "currency" },
    { field: "extra_adult_price", label: "Extra adult / night", type: "currency" },
    { field: "child_price", label: "Child / night", type: "currency" },
    { field: "adults_capacity", label: "Max adults", type: "int" },
    { field: "children_capacity", label: "Max children", type: "int" },
    { field: "tax_percent", label: "GST %", type: "float" },
    { field: "bed_type", label: "Bed type", type: "select", options: ["King", "Queen", "Twin", "Double", "Single"] },
    { field: "disabled", label: "Disabled", type: "check" },
  ],
}

export const ratePlansConfig: ScreenConfig = {
  doctype: "Rate Plan",
  title: "Rate Plans",
  description: "Sellable plans (BAR, non-refundable, corporate) that adjust the room total.",
  propertyScoped: true,
  columns: [
    { field: "rate_plan_name", label: "Name" },
    { field: "code", label: "Code", badge: true },
    { field: "modifier_type", label: "Modifier" },
    { field: "modifier_value", label: "Value" },
    { field: "is_default", label: "Default" },
  ],
  form: [
    { field: "rate_plan_name", label: "Name", type: "data", required: true },
    { field: "code", label: "Code", type: "data", required: true },
    { field: "modifier_type", label: "Modifier type", type: "select", options: ["Percent", "Amount", "Absolute"] },
    { field: "modifier_value", label: "Modifier value (-10 = 10% off)", type: "float" },
    { field: "cancellation_policy", label: "Cancellation policy", type: "data" },
    { field: "is_default", label: "Default plan", type: "check" },
    { field: "disabled", label: "Disabled", type: "check" },
  ],
}

export const seasonsConfig: ScreenConfig = {
  doctype: "Season",
  title: "Seasons",
  description: "Date ranges that lift or set nightly rates. Highest priority wins.",
  propertyScoped: true,
  orderBy: "start_date asc",
  columns: [
    { field: "season_name", label: "Season" },
    { field: "start_date", label: "From" },
    { field: "end_date", label: "To" },
    { field: "adjustment_type", label: "Type" },
    { field: "adjustment_value", label: "Value" },
    { field: "priority", label: "Priority" },
  ],
  form: [
    { field: "season_name", label: "Name", type: "data", required: true },
    { field: "start_date", label: "Start date", type: "date", required: true },
    { field: "end_date", label: "End date (inclusive)", type: "date", required: true },
    { field: "adjustment_type", label: "Adjustment", type: "select", options: ["Percent", "Amount", "Absolute"] },
    { field: "adjustment_value", label: "Value (20 = +20%)", type: "float" },
    { field: "priority", label: "Priority", type: "int" },
    { field: "disabled", label: "Disabled", type: "check" },
  ],
}

export const vouchersConfig: ScreenConfig = {
  doctype: "Discount Voucher",
  title: "Vouchers",
  description: "Discount codes guests or agents can apply at booking.",
  propertyScoped: true,
  columns: [
    { field: "voucher_code", label: "Code", badge: true },
    { field: "discount_type", label: "Type" },
    { field: "value", label: "Value" },
    { field: "valid_to", label: "Valid until" },
    { field: "min_nights", label: "Min nights" },
    { field: "times_used", label: "Used" },
  ],
  form: [
    { field: "voucher_code", label: "Code", type: "data", required: true },
    { field: "discount_type", label: "Type", type: "select", options: ["Percent", "Amount"] },
    { field: "value", label: "Value (10 = 10% or ₹10)", type: "float", required: true },
    { field: "valid_from", label: "Valid from", type: "date" },
    { field: "valid_to", label: "Valid to", type: "date" },
    { field: "min_nights", label: "Minimum nights", type: "int" },
    { field: "max_uses", label: "Max uses (0 = unlimited)", type: "int" },
    { field: "times_used", label: "Times used", type: "readonly" },
    { field: "disabled", label: "Disabled", type: "check" },
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
    { field: "price_per_adult", label: "₹ / adult / night" },
    { field: "price_per_child", label: "₹ / child / night" },
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

export const travelAgentsConfig: ScreenConfig = {
  doctype: "Travel Agent",
  title: "Travel Agents",
  description: "Business sources with commission tracking — commissions compute automatically on their bookings.",
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
  title: "Venues",
  description: "Banquet halls, lawns, board rooms — enquiry-based event spaces.",
  propertyScoped: true,
  columns: [
    { field: "venue_name", label: "Venue" },
    { field: "capacity", label: "Capacity" },
    { field: "base_price", label: "Indicative ₹" },
  ],
  form: [
    { field: "venue_name", label: "Venue name", type: "data", required: true },
    { field: "capacity", label: "Capacity (people)", type: "int" },
    { field: "base_price", label: "Indicative price", type: "currency" },
    { field: "amenities", label: "Amenities", type: "data" },
    { field: "disabled", label: "Disabled", type: "check" },
  ],
}

export const venueBookingsConfig: ScreenConfig = {
  doctype: "Venue Booking",
  title: "Events",
  description: "Banquet & event pipeline: enquiry → confirmed → completed.",
  propertyScoped: true,
  orderBy: "event_date asc",
  columns: [
    { field: "name", label: "Ref" },
    { field: "customer_name", label: "Customer" },
    { field: "venue", label: "Venue" },
    { field: "event_type", label: "Type", badge: true },
    { field: "event_date", label: "Date" },
    { field: "status", label: "Status", badge: true },
    { field: "quoted_amount", label: "Quoted ₹" },
  ],
  form: [
    { field: "venue", label: "Venue", type: "link", linkDoctype: "Venue", required: true },
    { field: "event_type", label: "Event type", type: "select", options: ["Wedding", "Conference", "Birthday", "Corporate Offsite", "Other"] },
    { field: "event_date", label: "Event date", type: "date", required: true },
    { field: "customer_name", label: "Customer name", type: "data", required: true },
    { field: "customer_phone", label: "Customer phone", type: "data" },
    { field: "company", label: "Company", type: "link", linkDoctype: "Company" },
    { field: "attendees", label: "Attendees", type: "int" },
    { field: "quoted_amount", label: "Quoted amount", type: "currency" },
    { field: "advance_received", label: "Advance received", type: "currency" },
    { field: "status", label: "Status", type: "select", options: ["Enquiry", "Confirmed", "Completed", "Cancelled"] },
    { field: "requirements", label: "Requirements", type: "data" },
  ],
}

export const lostFoundConfig: ScreenConfig = {
  doctype: "Lost And Found Item",
  title: "Lost & Found",
  description: "Items found on property; track storage and returns.",
  propertyScoped: true,
  orderBy: "found_on desc",
  columns: [
    { field: "name", label: "Ref" },
    { field: "item_description", label: "Item" },
    { field: "found_in_room", label: "Room" },
    { field: "found_on", label: "Found" },
    { field: "status", label: "Status", badge: true },
  ],
  form: [
    { field: "item_description", label: "Item", type: "data", required: true },
    { field: "found_in_room", label: "Found in room", type: "link", linkDoctype: "Room" },
    { field: "found_on", label: "Found on", type: "date", required: true },
    { field: "found_by", label: "Found by", type: "data" },
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
    { field: "closing_cash", label: "Closing cash ₹" },
  ],
  form: [
    { field: "shift", label: "Shift", type: "select", options: ["Morning", "Evening", "Night"], required: true },
    { field: "shift_date", label: "Date", type: "date", required: true },
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
    "Owner-set floor and ceiling. No rate move — human or AI agent — can price outside these rails.",
  propertyScoped: true,
  columns: [
    { field: "name", label: "Rail" },
    { field: "room_type", label: "Room type (blank = all)" },
    { field: "floor_price", label: "Floor ₹" },
    { field: "ceiling_price", label: "Ceiling ₹" },
  ],
  form: [
    { field: "room_type", label: "Room type (blank = all)", type: "link", linkDoctype: "Room Type" },
    { field: "floor_price", label: "Floor price / night", type: "currency", required: true },
    { field: "ceiling_price", label: "Ceiling price / night", type: "currency", required: true },
    { field: "disabled", label: "Disabled", type: "check" },
  ],
}

export const companiesConfig: ScreenConfig = {
  doctype: "Company",
  title: "Corporate Accounts",
  description: "Companies with negotiated rates and credit terms.",
  columns: [
    { field: "company_name", label: "Company" },
    { field: "gstin", label: "GSTIN" },
    { field: "contact_name", label: "Contact" },
    { field: "contact_phone", label: "Phone" },
    { field: "credit_allowed", label: "Credit" },
  ],
  form: [
    { field: "company_name", label: "Company name", type: "data", required: true },
    { field: "gstin", label: "GSTIN", type: "data" },
    { field: "contact_name", label: "Contact name", type: "data" },
    { field: "contact_phone", label: "Contact phone", type: "data" },
    { field: "contact_email", label: "Contact email", type: "data" },
    { field: "negotiated_rate_plan", label: "Negotiated rate plan", type: "link", linkDoctype: "Rate Plan" },
    { field: "credit_allowed", label: "Credit allowed (city ledger)", type: "check" },
    { field: "disabled", label: "Disabled", type: "check" },
  ],
  extra: BillingRulesEditor,
}

export const housekeepingConfig: ScreenConfig = {
  doctype: "Housekeeping Task",
  title: "Housekeeping Tasks",
  description: "Cleans and inspections. Completing a task updates the room's live status.",
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
    { field: "room", label: "Room", type: "link", linkDoctype: "Room", required: true },
    { field: "task_type", label: "Type", type: "select", options: ["Checkout Clean", "Stayover Clean", "Deep Clean", "Inspection", "Maintenance"] },
    { field: "priority", label: "Priority", type: "select", options: ["Low", "Medium", "High", "Urgent"] },
    { field: "status", label: "Status", type: "select", options: ["Pending", "In Progress", "Done", "Verified"] },
    { field: "notes", label: "Notes", type: "data" },
  ],
}

export const billingConfig: ScreenConfig = {
  doctype: "Reservation",
  title: "Billing",
  description:
    "Reservation totals. Folios, charge posting and GST invoices arrive in the next milestone.",
  propertyScoped: true,
  allowCreate: false,
  allowDelete: false,
  orderBy: "check_in_date desc",
  columns: [
    { field: "name", label: "Reservation" },
    { field: "guest_name", label: "Guest" },
    { field: "status", label: "Status", badge: true },
    { field: "check_in_date", label: "Check-in" },
    { field: "amount_before_tax", label: "Pre-tax ₹" },
    { field: "discount_amount", label: "Discount ₹" },
    { field: "tax_amount", label: "GST ₹" },
    { field: "amount_after_tax", label: "Total ₹" },
  ],
  form: [
    { field: "guest_name", label: "Guest", type: "readonly" },
    { field: "amount_before_tax", label: "Pre-tax", type: "readonly" },
    { field: "tax_amount", label: "GST", type: "readonly" },
    { field: "amount_after_tax", label: "Total", type: "readonly" },
  ],
}

export const reservationsConfig: ScreenConfig = {
  doctype: "Reservation",
  title: "Reservations",
  description: "All bookings. Create new ones with the New booking button above.",
  propertyScoped: true,
  allowCreate: false,
  orderBy: "check_in_date desc",
  columns: [
    { field: "name", label: "Ref" },
    { field: "guest_name", label: "Guest" },
    { field: "room", label: "Room" },
    { field: "check_in_date", label: "In" },
    { field: "check_out_date", label: "Out" },
    { field: "status", label: "Status", badge: true },
    { field: "booking_type", label: "Type" },
    { field: "source", label: "Source" },
    { field: "amount_after_tax", label: "Total ₹" },
  ],
  form: [
    { field: "guest_name", label: "Guest", type: "readonly" },
    { field: "room", label: "Room", type: "link", linkDoctype: "Room" },
    { field: "status", label: "Status", type: "select", options: ["Confirmed", "Checked In", "Checked Out", "Cancelled", "No Show"] },
    { field: "special_requests", label: "Special requests", type: "data" },
  ],
}
