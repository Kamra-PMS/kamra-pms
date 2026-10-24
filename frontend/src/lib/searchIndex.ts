/** Things search (Ctrl/Cmd+K) can jump to besides the sidebar pages: the
 *  jobs people think of by name ("cash drop", "refund", "night audit") and
 *  where they are done. Pages come from the app registry; settings come
 *  from the settings registry on the server; these are the in-between. */

export interface FeatureEntry {
  label: string
  to: string
  /** where it lives, shown under the label */
  where: string
  keywords: string[]
  /** a role that can use it; empty = anyone who can reach the route */
  roles?: string[]
}

export const FEATURES: FeatureEntry[] = [
  { label: "Close the day", to: "/end-of-day", where: "End of Day / Night Audit", keywords: ["night audit", "eod", "roll date", "business date", "3 am", "audit pack", "blockers"] },
  { label: "Fix End of Day blockers", to: "/end-of-day", where: "End of Day / Night Audit", keywords: ["blocker", "acknowledge", "override", "cannot close", "stuck"] },
  { label: "Add a till or terminal", to: "/cashier/board", where: "Finance · All tills", keywords: ["cash office", "register", "pos station", "drawer", "terminal"] },
  { label: "Cash drop", to: "/cashier", where: "Finance · My Till", keywords: ["safe", "paid out", "float", "count cash", "close till", "open till"] },
  { label: "Petty cash voucher", to: "/cashier/petty-cash", where: "Finance · Petty Cash", keywords: ["imprest", "expense", "voucher"] },
  { label: "Currency exchange", to: "/cashier/fx", where: "Finance · Currency Desk", keywords: ["fx", "forex", "exchange rate"] },
  { label: "Refund a payment", to: "/billing", where: "Finance · Billing", keywords: ["credit note", "reverse", "chargeback"] },
  { label: "Print an invoice", to: "/billing", where: "Finance · Billing", keywords: ["gst invoice", "tax invoice", "reprint", "bill"] },
  { label: "Change a room rate", to: "/rate-plans", where: "Revenue · Rate Plans", keywords: ["bar", "best available rate", "base price", "rack rate", "tariff", "pricing"] },
  { label: "Seasonal pricing", to: "/seasons", where: "Revenue · Seasons", keywords: ["peak", "weekend rate", "festival", "date range", "bar"] },
  { label: "Move a guest to another room", to: "/", where: "Front Desk · Today", keywords: ["room change", "upgrade", "downgrade", "swap room"] },
  { label: "Extend a stay", to: "/reservations", where: "Front Desk · Reservations", keywords: ["late checkout", "change dates", "amend"] },
  { label: "Cancel a booking", to: "/reservations", where: "Front Desk · Reservations", keywords: ["no show", "cancellation fee", "waive fee"] },
  { label: "Block a room", to: "/room-blocks", where: "Front Desk · Room Blocks", keywords: ["maintenance", "out of order", "hold"] },
  { label: "Assign housekeeping", to: "/housekeeping", where: "Housekeeping", keywords: ["clean room", "turndown", "attendant", "dirty"] },
  { label: "Lost and found", to: "/lost-and-found", where: "Housekeeping", keywords: ["lost item", "found item"] },
  { label: "Raise a service ticket", to: "/tickets", where: "Operations · Tickets", keywords: ["complaint", "maintenance request", "sla", "issue", "request"] },
  { label: "Take a restaurant order", to: "/pos", where: "F&B · POS", keywords: ["kot", "table", "bill", "room service", "dine in", "takeaway"] },
  { label: "Set up printers", to: "/printers", where: "F&B · Printers", keywords: ["kot printer", "bill printer", "receipt", "thermal"] },
  { label: "Edit the menu", to: "/menu-items", where: "F&B · Menu", keywords: ["dish", "price", "recipe", "item", "category"] },
  { label: "Book a banquet or function", to: "/banquet", where: "Events", keywords: ["wedding", "conference", "hall", "venue", "party"] },
  { label: "Connect a channel manager", to: "/settings/front-desk", where: "Settings", keywords: ["ota", "booking.com", "makemytrip", "aiosell", "staah", "channel"] },
  { label: "Invite or manage staff", to: "/settings/staff", where: "Admin · Staff & Access", keywords: ["user", "role", "permission", "password", "pin"] },
  { label: "Turn the AI agent on", to: "/settings/ai", where: "Settings · AI", keywords: ["api key", "openai", "claude", "mcp", "assistant", "agent"] },
  { label: "Manage AI access (MCP)", to: "/settings/claude", where: "Settings · AI access (MCP)", keywords: ["mcp", "claude", "chatgpt", "mcp read", "mcp manage", "disconnect", "block tools", "permissions"] },
  { label: "Reports and exports", to: "/reports", where: "Finance · Reports", keywords: ["occupancy", "adr", "revpar", "tally", "accounting export", "csv", "custom report", "email report", "schedule"] },
  { label: "Custom report builder", to: "/reports", where: "Finance · Reports", keywords: ["saved report", "dataset", "mail", "arrivals list", "contribution"] },
]
