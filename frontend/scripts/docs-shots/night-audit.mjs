// Night audit guide images (docs-site/night-audit.md).
// STAGE=before  the overview and the close-the-day page (no changes made)
// STAGE=run     records the GIF that overrides the blockers, closes the docs
//               user's till, adds a note and closes the day - rolls the
//               business date
// STAGE=after   the history and the audit pack
import { session, api, open, shot, gif, typeSlow, done, PROPERTY } from "./lib.mjs"

const STAGE = process.env.STAGE || "before"
const ONLY = (process.env.ONLY || "").split(",").filter(Boolean)
const want = (n) => !ONLY.length || ONLY.includes(n)
const PAGE = `/end-of-day/${encodeURIComponent(PROPERTY)}`

/** The page can load twice on first open; reload until it is clean. */
async function openDay(page) {
  for (let i = 0; i < 4; i++) {
    await open(page, PAGE, 3500)
    if (!(await page.getByText("Record has changed").count())) return
  }
}

const ctx = await session()
const page = await ctx.newPage()

if (STAGE === "before") {
  if (want("manage")) {
    await open(page, "/end-of-day", 4000)
    await shot(page, "night-audit/manage", { clip: { x: 248, y: 75, width: 1168, height: 715 } })
  }
  if (want("close-day")) {
    await openDay(page)
    await shot(page, "night-audit/close-day", { clip: { x: 248, y: 75, width: 1168, height: 800 } })
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
  await gif("night-audit/run-close", async (p, c, rec) => {
    await openDay(p)
    rec()
    // every blocker that is still open: override it with a reason
    const reasons = ["Late checkouts approved by the duty manager", "Bar tabs carried to tomorrow"]
    for (const why of reasons) {
      const box = p.getByPlaceholder("Reason")
      if (!(await box.count())) break
      await box.first().scrollIntoViewIfNeeded()
      await typeSlow(box.first(), why, 25)
      await p.getByRole("button", { name: "Override with reason" }).first().click()
      await p.waitForTimeout(1800)
    }
    // the docs user's own till, counted at what it should hold
    const counted = p.getByPlaceholder("Counted cash").first()
    if (await counted.count()) {
      await counted.scrollIntoViewIfNeeded()
      const cs = await api(c, "kamra.cashier.current_session", { property: PROPERTY })
      const expected = cs?.expected_cash != null ? String(Math.round(cs.expected_cash)) : ""
      await typeSlow(counted, expected || "7450", 80)
      await p.getByRole("button", { name: "Count and close" }).first().click()
      await p.waitForTimeout(2000)
    }
    const notes = p.getByLabel("Notes for the manager")
    await notes.scrollIntoViewIfNeeded()
    await typeSlow(notes, "Heavy rain after 20:00. Lift 2 out of service.", 25)
    await p.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }))
    await p.waitForTimeout(1200)
    await p.getByRole("button", { name: /^Close / }).first().click()
    await p.waitForTimeout(9000)
  }, { crop: { x: 240, y: 75, width: 1190, height: 790 } })
}

if (STAGE === "after") {
  if (want("result")) {
    await open(page, "/end-of-day", 4000)
    await shot(page, "night-audit/history", { clip: { x: 248, y: 75, width: 1168, height: 690 } })
  }
  if (want("pack")) {
    await open(page, "/end-of-day", 4000)
    // the pack opens from Print in the history's Audit pack column
    await page.getByText("Print", { exact: true }).first().click()
    await page.waitForLoadState("networkidle").catch(() => {})
    await page.waitForTimeout(3500)
    await shot(page, "night-audit/audit-pack", { clip: { x: 248, y: 75, width: 1168, height: 800 } })
  }
}

await done()
