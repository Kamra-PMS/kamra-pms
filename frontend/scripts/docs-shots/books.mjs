// Books guide images (docs-site/books.md): Payables, Cash outlook and
// Profit and loss on the sample hotel. The first run adds three suppliers
// and their bills (one paid, one approved, one awaiting approval), which
// stay as sample data. Set ONLY=name1,name2 for a subset.
import { api, open, shot, done, session, PROPERTY } from "./lib.mjs"

const ONLY = (process.env.ONLY || "").split(",").filter(Boolean)
const want = (n) => !ONLY.length || ONLY.includes(n)
const ctx = await session()
const page = await ctx.newPage()
const MAIN = { x: 236, y: 75, width: 1192 }
const day = (n) => new Date(Date.now() + n * 864e5).toISOString().slice(0, 10)

const has = await api(ctx, "frappe.client.get_count", { doctype: "Vendor Bill", filters: { property: PROPERTY } })
if (!has) {
  for (const [vendor_name, expense_category, payment_terms_days, bill_number, amount, tax_rate, dated, then] of [
    ["Fresh Farms Produce", "Food & Beverage Supplies", 15, "FF-2291", 18400, 5, -20, "pay"],
    ["CleanCo Linen Services", "Linen & Laundry", 30, "CL-0874", 26500, 18, -12, "approve"],
    ["BESCOM", "Utilities", 10, "EL-10-2026", 42300, 0, -3, null],
  ]) {
    const { vendor } = await api(ctx, "kamra.payables.save_vendor", { property: PROPERTY, vendor_name, expense_category, payment_terms_days })
    const bill = await api(ctx, "kamra.payables.create_vendor_bill", {
      property: PROPERTY, vendor, bill_date: day(dated), amount, tax_rate, bill_number })
    if (then) await api(ctx, "kamra.payables.approve_vendor_bill", { bill: bill.name })
    if (then === "pay") await api(ctx, "kamra.payables.pay_vendor_bill", { bill: bill.name, amount: bill.total, reference: "NEFT 55120" })
  }
}

for (const [name, route, height] of [
  ["payables", "/payables", 560],
  ["cash-outlook", "/cash-forecast", 640],
  ["profit-and-loss", "/profit-and-loss", 760],
]) {
  if (!want(name)) continue
  await open(page, route, 3500)
  await shot(page, `books/${name}`, { clip: { ...MAIN, height } })
}

await done()
