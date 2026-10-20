// Billing guide images (docs-site/billing.md). Run billing-setup.mjs once
// first. Set ONLY=name1,name2 to capture a subset.
import { session, api, open, shot, gif, typeSlow, done, PROPERTY } from "./lib.mjs"

const ONLY = (process.env.ONLY || "").split(",").filter(Boolean)
const want = (n) => !ONLY.length || ONLY.includes(n)

const ctx = await session()
const page = await ctx.newPage()
const L = (doctype, fields, filters = {}) =>
  api(ctx, "frappe.client.get_list", { doctype, fields, filters, limit_page_length: 50 })
const folioOf = async (guest, status = "Open") =>
  (await L("Folio", ["name"], { property: PROPERTY, guest_name: guest, folio_type: "Guest", status }))[0]?.name

const priya = await folioOf("Priya Nair")
const payFolio = process.env.PAY_FOLIO || priya
const MAIN = { x: 262, width: 1140 }

if (want("billing-list")) {
  await open(page, "/billing", 2500)
  await shot(page, "billing/billing-list", { clip: { x: 320, y: 75, width: 1020, height: 520 } })
}

if (want("folio")) {
  await open(page, `/billing/${priya}`, 3000)
  await shot(page, "billing/folio", { fullPage: true, clip: { ...MAIN, y: 75, height: 1095 } })
}

if (want("post-charge")) {
  await open(page, `/billing/${priya}`, 3000)
  const card = page.getByText("Post a charge", { exact: true })
  await card.scrollIntoViewIfNeeded()
  await page.locator("select", { has: page.locator("option", { hasText: "Minibar" }) }).selectOption("Minibar")
  await page.getByPlaceholder("Description").fill("Minibar - chocolate")
  const box = await card.locator("xpath=ancestor::div[contains(@class,'grid')][1]").boundingBox()
  await shot(page, "billing/post-charge", { clip: { x: box.x - 8, y: box.y - 8, width: box.width + 16, height: box.height + 16 } })
}

if (want("move-charges")) {
  await open(page, `/billing/${priya}`, 3000)
  const row = page.locator("tr", { hasText: "Spa - 60 min massage" })
  await row.locator("input[type=checkbox]").check()
  await page.waitForTimeout(400)
  await page.getByPlaceholder("30% or 1500").fill("50%")
  await page.waitForTimeout(500)
  const bar = page.getByText("Send ₹", { exact: false }).first()
  const b = await bar.locator("xpath=ancestor::div[contains(@class,'rounded-xl')][1]").boundingBox()
  await shot(page, "billing/move-charges", { clip: { x: b.x - 10, y: b.y - 10, width: b.width + 20, height: b.height + 290 } })
}

if (want("void")) {
  await open(page, `/billing/${priya}`, 3000)
  const row = page.locator("tr", { hasText: "Laundry - 4 shirts" })
  await row.getByRole("button", { name: "Void this charge" }).click()
  await row.getByPlaceholder("Reason (required - goes on the record)").fill("Not this guest's laundry")
  const r = await row.boundingBox()
  await shot(page, "billing/void", { clip: { x: r.x - 10, y: r.y - 50, width: r.width + 20, height: r.height + 100 } })
}

if (want("take-payment")) {
  await gif("billing/take-payment", async (p) => {
    await open(p, `/billing/${payFolio}`, 2500)
    await p.getByText("Grand total", { exact: false }).scrollIntoViewIfNeeded()
    await p.mouse.wheel(0, 250)
    await p.waitForTimeout(1200)
    const card = p.getByText("Record a payment", { exact: true })
    await card.scrollIntoViewIfNeeded()
    await p.waitForTimeout(600)
    const sel = p.locator("select", { has: p.locator("option", { hasText: "Payment Link" }) })
    await sel.selectOption("UPI")
    await p.waitForTimeout(500)
    await typeSlow(p.getByPlaceholder("Reference (optional)"), "UPI ref 61822")
    await p.waitForTimeout(400)
    await p.getByRole("button", { name: "Record", exact: true }).click()
    await p.waitForTimeout(1800)
    await p.getByText("Grand total", { exact: false }).scrollIntoViewIfNeeded()
    await p.mouse.wheel(0, 200)
    await p.waitForTimeout(2000)
  }, { crop: { x: 262, y: 59, width: 1140, height: 760 } })
}

if (want("tax-invoice")) {
  // Rohan's folio is paid in full: Settle & continue stay issues the
  // interim invoice and opens a fresh folio for the rest of the stay.
  let closed = await folioOf("Rohan Mehta", "Closed")
  if (!closed) {
    const rohan = await folioOf("Rohan Mehta")
    await open(page, `/billing/${rohan}`, 3000)
    await page.getByRole("button", { name: "Settle & continue stay" }).click()
    await page.waitForTimeout(3000)
    closed = rohan
  }
  await open(page, `/billing/${closed}`, 3000)
  await shot(page, "billing/tax-invoice", { fullPage: true, clip: { ...MAIN, y: 75, height: 760 } })
}

if (want("security-deposit")) {
  await open(page, "/reservations", 2500)
  await page.getByText("Priya Nair").first().click()
  await page.waitForTimeout(2500)
  const panel = page.getByText("Security deposit", { exact: true }).first()
  await panel.scrollIntoViewIfNeeded()
  const b = await panel.locator("xpath=ancestor::div[contains(@class,'rounded')][1]").boundingBox()
  await shot(page, "billing/security-deposit", { clip: { x: b.x - 6, y: b.y - 6, width: b.width + 12, height: b.height + 12 } })
}

if (want("my-till")) {
  // the till loads twice on open; retry if the first load raced
  for (let i = 0; i < 4; i++) {
    await open(page, "/cashier", 4500)
    if (!(await page.getByText("Record has changed").count())) break
  }
  await shot(page, "billing/my-till", { fullPage: true, clip: { x: 320, y: 75, width: 1020, height: 600 } })
}

if (want("shift-report")) {
  await open(page, "/cashier/shift-report", 4000)
  await shot(page, "billing/shift-report", { clip: { x: 580, y: 95, width: 505, height: 430 } })
}

if (want("petty-cash")) {
  await open(page, "/cashier/petty-cash", 4000)
  await shot(page, "billing/petty-cash", { clip: { x: 570, y: 95, width: 525, height: 425 } })
}

if (want("currency-desk")) {
  await open(page, "/cashier/fx", 4000)
  await page.getByRole("button", { name: "Calculate" }).click()
  await page.waitForTimeout(1200)
  await shot(page, "billing/currency-desk", { clip: { x: 392, y: 95, width: 880, height: 515 } })
}

if (want("voids-allowances")) {
  await open(page, "/voids-allowances", 3500)
  const root = page.getByRole("heading", { name: "Voids & Allowances" }).locator("xpath=ancestor::div[contains(@class,'max-w-5xl')][1]")
  await shot(page, "billing/voids-allowances", { locator: root })
}

if (want("ledgers")) {
  await open(page, "/ledgers", 4000)
  const root = page.getByRole("heading", { name: "Ledgers", exact: true }).locator("xpath=ancestor::div[contains(@class,'max-w-5xl')][1]")
  await shot(page, "billing/ledgers", { locator: root })
}

await done()
