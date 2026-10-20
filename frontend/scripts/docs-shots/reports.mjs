// Reports guide images (docs-site/reports.md). Best run after a night
// audit has posted room nights, so the numbers are not all zero.
import { session, api, open, shot, gif, typeSlow, done, PROPERTY } from "./lib.mjs"

const ONLY = (process.env.ONLY || "").split(",").filter(Boolean)
const want = (n) => !ONLY.length || ONLY.includes(n)
const ctx = await session()
const page = await ctx.newPage()
const box = async (loc, pad = 8) => {
  const b = await loc.boundingBox()
  const sy = await page.evaluate(() => window.scrollY)
  return { x: b.x - pad, y: b.y + sy - pad, width: b.width + 2 * pad, height: b.height + 2 * pad }
}

if (want("dashboard")) {
  await open(page, "/dashboard", 3500)
  await shot(page, "reports/dashboard", { clip: { x: 340, y: 75, width: 985, height: 590 } })
}
if (want("portfolio")) {
  await open(page, "/dashboard", 3000)
  await page.getByRole("button", { name: "All properties" }).click()
  await page.waitForTimeout(3000)
  await shot(page, "reports/portfolio", { clip: { x: 340, y: 75, width: 985, height: 445 } })
}
if (want("flash")) {
  await open(page, "/reports", 4000)
  const root = page.locator("div", { has: page.getByText("Manager flash", { exact: true }), hasText: "Next 7 days" }).last()
  await shot(page, "reports/manager-flash", { fullPage: true, clip: await box(root, 12) })
}
if (want("budget")) {
  const period = new Date().toISOString().slice(0, 7)
  await api(ctx, "kamra.reports.save_budget", {
    property: PROPERTY, period, room_revenue_target: 1200000,
    occupancy_target: 72, adr_target: 4800, revpar_target: 3450,
  })
  await open(page, "/revenue-reports", 4000)
  const card = page.getByText("Budget vs Actual", { exact: true }).locator("xpath=ancestor::div[contains(@class,'rounded-xl')][1]")
  await shot(page, "reports/budget-vs-actual", { fullPage: true, clip: await box(card) })
}
if (want("contribution")) {
  await open(page, "/revenue-reports", 4000)
  const card = page.getByText("Contribution analysis", { exact: true }).locator("xpath=ancestor::div[contains(@class,'rounded-xl')][1]")
  await card.scrollIntoViewIfNeeded()
  await shot(page, "reports/contribution", { fullPage: true, clip: await box(card) })
}
if (want("sla")) {
  await open(page, "/ops-sla", 4000)
  await shot(page, "reports/sla", { fullPage: true, clip: { x: 224, y: 59, width: 1216, height: 760 } })
}
if (want("export")) {
  await open(page, "/accounting-export", 4000)
  await shot(page, "reports/accounting-export", { clip: { x: 224, y: 59, width: 1216, height: 300 } })
}
if (want("budget-gif")) {
  await gif("reports/set-targets", async (p) => {
    await open(p, "/revenue-reports", 3000)
    await p.getByRole("button", { name: "Edit targets" }).click()
    await p.waitForTimeout(600)
    const inputs = p.locator("table input")
    await inputs.nth(2).fill("")
    await typeSlow(inputs.nth(2), "5000", 120)
    await p.waitForTimeout(500)
    await p.getByRole("button", { name: "Save targets" }).click()
    await p.waitForTimeout(2500)
  }, { crop: { x: 300, y: 59, width: 1080, height: 480 } })
}

await done()
