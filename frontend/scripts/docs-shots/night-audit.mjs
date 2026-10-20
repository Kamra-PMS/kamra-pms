// Night audit guide images (docs-site/night-audit.md).
// STAGE=before  the overview and the wizard's checks (no changes made)
// STAGE=run     records the GIF that acknowledges the blockers, closes the
//               docs user's till and runs the audit - rolls the business date
// STAGE=after   the result, the audit pack and the history
import { session, api, open, shot, gif, typeSlow, done, PROPERTY } from "./lib.mjs"

const STAGE = process.env.STAGE || "before"
const ONLY = (process.env.ONLY || "").split(",").filter(Boolean)
const want = (n) => !ONLY.length || ONLY.includes(n)
const WIZ = `/end-of-day/${encodeURIComponent(PROPERTY)}`

/** The wizard can load twice on first open; reload until it is clean. */
async function openWizard(page, route = WIZ) {
  for (let i = 0; i < 4; i++) {
    await open(page, route, 3500)
    if (!(await page.getByText("Record has changed").count())) return
  }
}
const step = (page, title) =>
  page.locator("ol button", { hasText: title }).first().click().then(() => page.waitForTimeout(1200))
const MAIN = { x: 300, y: 75, width: 1065 }
/** The wizard (step list + panel) as laid out, however wide its tables make it. */
async function wizShot(page, name, height) {
  const root = page.getByText("Manage End of Day").first().locator("xpath=ancestor::div[contains(@class,'space-y-4')][1]")
  const b = await root.boundingBox()
  const sx = await page.evaluate(() => window.scrollX)
  const sy = await page.evaluate(() => window.scrollY)
  await shot(page, name, { fullPage: true, clip: { x: b.x + sx - 12, y: b.y + sy - 12, width: b.width + 24, height: Math.min(height, b.height + 24) } })
}

const ctx = await session()
const page = await ctx.newPage()

if (STAGE === "before") {
  if (want("manage")) {
    await open(page, "/end-of-day", 3000)
    await shot(page, "night-audit/manage", { clip: { x: 260, y: 75, width: 1145, height: 715 } })
  }
  if (want("prepare")) {
    await openWizard(page)
    await wizShot(page, "night-audit/wizard", 820)
  }
  if (want("arrivals")) {
    await openWizard(page)
    await step(page, "Arrivals not checked in")
    await wizShot(page, "night-audit/arrivals", 560)
  }
  if (want("departures")) {
    await openWizard(page)
    await step(page, "Departures not checked out")
    await wizShot(page, "night-audit/departures", 620)
  }
  if (want("cashiers")) {
    await openWizard(page)
    await step(page, "Cashier closure")
    await wizShot(page, "night-audit/cashier-closure", 520)
  }
  if (want("settings")) {
    await open(page, "/settings/front-desk", 3000)
    const h = page.getByText("Night audit checklist", { exact: true }).first()
    await h.scrollIntoViewIfNeeded()
    await page.waitForTimeout(600)
    const b = await h.boundingBox()
    const sy = await page.evaluate(() => window.scrollY)
    await shot(page, "night-audit/settings", { fullPage: true, clip: { x: b.x - 12, y: b.y + sy - 12, width: 885, height: 708 } })
  }
}

if (STAGE === "run") {
  await gif("night-audit/run-end-of-day", async (p, c) => {
    await openWizard(p)
    // departures still in house: acknowledged, not checked out here
    const ack = async (title, why) => {
      await step(p, title)
      const box = p.getByPlaceholder("Reason")
      if (!(await box.count())) return
      await typeSlow(box.first(), why, 25)
      await p.getByRole("button", { name: "Acknowledge" }).first().click()
      await p.waitForTimeout(1500)
    }
    await ack("Departures not checked out", "Late checkouts approved by the duty manager")
    await ack("Outlets and room postings", "Bar tabs carried to tomorrow")
    await step(p, "Cashier closure")
    const counted = p.getByPlaceholder("Counted cash").first()
    if (await counted.count()) {
    const cs = await api(c, "kamra.cashier.current_session", { property: PROPERTY })
    const expected = cs?.expected_cash != null ? String(Math.round(cs.expected_cash)) : ""
    await typeSlow(counted, expected || "7450", 80)
    await p.getByRole("button", { name: "Close session" }).first().click()
    await p.waitForTimeout(1800)
    }
    await step(p, "Notes")
    await typeSlow(p.getByPlaceholder("Weather or notes"), "Heavy rain after 20:00. Lift 2 out of service.", 25)
    await p.getByRole("button", { name: "Save notes" }).click()
    await p.waitForTimeout(1000)
    await step(p, "Post room and tax and roll the business date")
    await p.waitForTimeout(1500)
    await p.getByRole("button", { name: "Post room and tax and roll the business date" }).last().click()
    await p.waitForTimeout(9000)
  }, { crop: { x: 240, y: 75, width: 1190, height: 790 } })
}

if (STAGE === "after") {
  if (want("result")) {
    await open(page, "/end-of-day", 3000)
    await shot(page, "night-audit/history", { clip: { x: 260, y: 75, width: 1145, height: 690 } })
  }
  if (want("pack")) {
    await open(page, "/end-of-day", 3000)
    await page.getByRole("button", { name: "View" }).first().click().catch(async () => {
      await page.getByText("View", { exact: true }).first().click()
    })
    await page.waitForTimeout(3500)
    await shot(page, "night-audit/audit-pack", { fullPage: true, clip: { x: 260, y: 75, width: 1145, height: 700 } })
  }
}

await done()
