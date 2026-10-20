// Sample money for the Billing guide: opens the docs user's till and puts
// charges, payments, a void and an allowance on folios of stays the seed
// already has in house. Run once before billing.mjs; running it again adds
// the same lines again, so don't.
import { session, api, done, PROPERTY } from "./lib.mjs"

const ctx = await session()
const L = (doctype, fields, filters = {}) =>
  api(ctx, "frappe.client.get_list", { doctype, fields, filters, limit_page_length: 50 })
const guestFolio = async (guest) =>
  (await L("Folio", ["name"], { property: PROPERTY, guest_name: guest, folio_type: "Guest", status: "Open" }))[0]?.name

await api(ctx, "kamra.cashier.open_session", { property: PROPERTY, opening_float: 5000 })

const priya = await guestFolio("Priya Nair")
const charge = (folio, charge_type, description, amount, gst_rate = 0, is_alcohol = 0) =>
  api(ctx, "kamra.api.add_folio_charge", { folio, charge_type, description, amount, gst_rate, is_alcohol })

await charge(priya, "Food & Beverage", "Dinner - Terrace restaurant", 1850, 5)
await charge(priya, "Food & Beverage", "Bar - two glasses of wine", 1200, 18, 1)
await charge(priya, "Minibar", "Minibar - water, nuts", 420, 18)
await charge(priya, "Laundry", "Laundry - 4 shirts", 600, 18)
await charge(priya, "Spa", "Spa - 60 min massage", 3500, 18)
const dup = await charge(priya, "Minibar", "Minibar - water, nuts", 420, 18)
const dupRow = dup.charges.at(-1).name
await api(ctx, "kamra.api.void_folio_charge", { folio: priya, charge_row: dupRow, reason: "Posted twice by mistake" })
await api(ctx, "kamra.api.post_allowance", { folio: priya, amount: 300, reason: "Late room service - goodwill", gst_rate: 5 })
await api(ctx, "kamra.api.add_folio_payment", { folio: priya, mode: "Cash", amount: 3000, kind: "Payment" })
await api(ctx, "kamra.api.add_folio_payment", { folio: priya, mode: "Card", amount: 5000, kind: "Security Deposit", reference: "Slip 4471" })

// Rohan: a paid folio for the interim invoice (Settle & continue stay)
const rohan = await guestFolio("Rohan Mehta")
await charge(rohan, "Food & Beverage", "Lunch - room service", 980, 5)
await charge(rohan, "Laundry", "Laundry - express", 450, 18)
const f = await api(ctx, "kamra.api.folio_invoice", { folio: rohan })
await api(ctx, "kamra.api.add_folio_payment", { folio: rohan, mode: "Card", amount: f.folio.balance, kind: "Payment", reference: "POS 8812" })

// petty cash and a paid-out so the till has movement
await api(ctx, "kamra.cashier.post_petty_cash", { property: PROPERTY, amount: 350, payee: "City Florists", category: "Supplies", reason: "Lobby flowers" })
await api(ctx, "kamra.cashier.post_paid_out", { property: PROPERTY, amount: 200, reason: "Taxi fare advanced for guest", payee: "Room 201" })
await api(ctx, "kamra.ledger.upsert_exchange_rate", { property: PROPERTY, currency: "USD", buy_rate: 83.2, sell_rate: 84.6, service_tax_pct: 0 })
await api(ctx, "kamra.ledger.upsert_exchange_rate", { property: PROPERTY, currency: "EUR", buy_rate: 90.1, sell_rate: 92.0, service_tax_pct: 0 })
console.log("folios", { priya, rohan })
await done()
