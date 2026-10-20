// Images for docs-site/banquets.md.
// Uses the seeded functions (EVT-2026-0088 confirmed wedding reception,
// EVT-2026-0096 tentative offsite). The sample group is removed at the
// end; the enquiry the GIF opens is kept as sample data.
import { session, api, open, shot, gif, typeSlow, done, PROPERTY } from "./lib.mjs"

const P = PROPERTY
const CONFIRMED = "EVT-2026-0088"
const TENTATIVE = "EVT-2026-0096"
const ctx = await session()
const page = await ctx.newPage()
const made = []

const cardWith = (text) =>
  page.locator("div.rounded-xl.border.bg-white.shadow-sm", { has: page.getByText(text, { exact: true }) }).last()
const firstCard = () => page.locator("div.rounded-xl.border.bg-white.shadow-sm").first()
const step = (n) => page.locator('nav[aria-label="Function progress"] button').nth(n)
const TOP = { x: 248, y: 60, width: 1168, height: 320 }

const field = (root, label) =>
  root.locator(`xpath=.//label[span[normalize-space(.)="${label}"]]//*[self::input or self::select or self::textarea]`).first()

function inDays(n) {
  const d = new Date(Date.now() + n * 864e5)
  return d.toISOString().slice(0, 10)
}

try {
  // ── the pipeline ─────────────────────────────────────────────────────
  await open(page, "/banquet", 2500)
  await shot(page, "banquets/home")

  await open(page, "/banquet-diary", 2500)
  await shot(page, "banquets/diary", { locator: firstCard() })

  await open(page, "/banquet-month", 2500)
  await shot(page, "banquets/month", { locator: firstCard() })

  // ── a new enquiry, filled in (not saved) ─────────────────────────────
  await open(page, "/banquet", 2000)
  await page.getByRole("button", { name: "New enquiry" }).click()
  await page.waitForTimeout(800)
  const dlg = page.locator('[role="dialog"]')
  await field(dlg, "Customer name").fill("Kavya Reddy")
  await field(dlg, "Phone").fill("+91 98450 77120")
  await field(dlg, "Event type").selectOption("Product Launch")
  await field(dlg, "Date").fill(inDays(52))
  await field(dlg, "Expected pax").fill("150")
  await field(dlg, "Session").selectOption("Evening")
  await field(dlg, "What they asked for").fill("150 pax launch evening, cocktail snacks, LED wall, podium, DJ till 11")
  await page.waitForTimeout(1500)
  await dlg.getByRole("button", { name: /Grand Ballroom/ }).click()
  await page.waitForTimeout(400)
  await shot(page, "banquets/new-enquiry")
  await page.keyboard.press("Escape")

  // ── the function sheet, step by step ─────────────────────────────────
  await open(page, `/banquet/${CONFIRMED}`, 2500)
  await shot(page, "banquets/function", { clip: TOP })

  await step(1).click(); await page.waitForTimeout(1200)
  await shot(page, "banquets/quote", { locator: cardWith("What they're buying") })

  await step(2).click(); await page.waitForTimeout(1500)

  await step(3).click(); await page.waitForTimeout(1200)
  await shot(page, "banquets/money", { locator: cardWith("Payment terms") })

  await step(4).click(); await page.waitForTimeout(1200)
  await page.evaluate(() => window.scrollTo(0, 0)); await page.waitForTimeout(300)
  await shot(page, "banquets/documents", { clip: { x: 248, y: 360, width: 1168, height: 470 } })

  await step(5).click(); await page.waitForTimeout(1200)
  await page.getByRole("button", { name: "Close out the function" }).click()
  await page.waitForTimeout(800)
  await shot(page, "banquets/close-out")
  await page.keyboard.press("Escape"); await page.waitForTimeout(400)

  // the event order (BEO), as printed
  await open(page, `/banquet/${CONFIRMED}/beo`, 2500)
  await shot(page, "banquets/beo")

  // guest response on a tentative hold (not saved)
  await open(page, `/banquet/${TENTATIVE}`, 2500)
  await page.getByRole("button", { name: /Guest response|Guest:/ }).click()
  await page.waitForTimeout(800)
  await shot(page, "banquets/guest-response")
  await page.keyboard.press("Escape")

  // ── set-up screens ───────────────────────────────────────────────────
  await open(page, "/banquet-catalogue", 2500)
  await shot(page, "banquets/catalogue", { locator: firstCard() })

  await open(page, "/venues", 2000)
  await shot(page, "banquets/venues", { locator: firstCard() })

  await open(page, "/banquet-registers", 2500)
  await shot(page, "banquets/registers", { locator: firstCard() })


  // ── a group, for the rooms side of an event ──────────────────────────
  const g = await api(ctx, "frappe.client.insert", { doc: {
    doctype: "Group Booking", property: P, group_name: "Sharma-Verma wedding guests",
    check_in_date: "2026-11-08", check_out_date: "2026-11-10", cutoff_date: "2026-10-30",
    status: "Open", notes: "Family block for the reception" } })
  made.push(["Group Booking", g.name])
  await open(page, "/groups", 2000)
  await page.getByRole("cell", { name: "Sharma-Verma wedding guests" }).first().click()
  await page.waitForTimeout(1500)
  await shot(page, "banquets/group")
  await page.keyboard.press("Escape")

  // the group picker on the Money step: the group chosen, not tied (not saved)
  await open(page, `/banquet/${CONFIRMED}`, 2500)
  await step(3).click(); await page.waitForTimeout(1500)
  {
    const settle = cardWith("Settlement")
    await settle.scrollIntoViewIfNeeded()
    await settle.getByLabel("Group booking").selectOption(g.name)
    await page.waitForTimeout(400)
    await shot(page, "banquets/group-link", { locator: settle })
  }

  // ── GIF: take an enquiry and price it ────────────────────────────────
  // The enquiry it opens stays as sample data; one left by an earlier run
  // is cancelled as a duplicate so the pipeline doesn't fill up.
  const old = await api(ctx, "frappe.client.get_list", { doctype: "Venue Booking",
    filters: { property: P, customer_name: "Kavya Reddy", status: ["in", ["Enquiry", "Tentative"]] }, pluck: "name" })
  for (const row of process.env.SKIP_GIFS ? [] : old) {
    const name = typeof row === "string" ? row : row.name
    await api(ctx, "kamra.banquet.set_status", { function: name, status: "Cancelled", reason: "Duplicate enquiry" })
  }
  if (!process.env.SKIP_GIFS) await gif("banquets/enquiry-to-quote", async (pg, gctx) => {
    await open(pg, "/banquet", 1500)
    await pg.getByRole("button", { name: "New enquiry" }).click()
    await pg.waitForTimeout(600)
    const d = pg.locator('[role="dialog"]')
    await typeSlow(field(d, "Customer name"), "Kavya Reddy", 45)
    await typeSlow(field(d, "Phone"), "+91 98450 77120", 30)
    await field(d, "Event type").selectOption("Product Launch")
    await field(d, "Date").fill(inDays(52))
    await typeSlow(field(d, "Expected pax"), "150", 80)
    await field(d, "Session").selectOption("Evening")
    await pg.waitForTimeout(1200)
    await d.getByRole("button", { name: /Grand Ballroom/ }).click()
    await pg.waitForTimeout(500)
    await d.getByRole("button", { name: "Open the enquiry" }).click()
    await pg.waitForURL(/\/banquet\/EVT-/)
    await pg.waitForTimeout(1500)
    await pg.locator('nav[aria-label="Function progress"] button').nth(1).click()
    await pg.waitForTimeout(1000)
    await pg.getByRole("button", { name: "Menu", exact: true }).click()
    await pg.waitForTimeout(900)
    await pg.locator('[role="dialog"] li', { hasText: "Sangeet Cocktail Snacks" }).getByRole("button", { name: "Add", exact: true }).click()
    await pg.waitForTimeout(1500)
    await pg.getByRole("button", { name: "Service", exact: true }).click()
    await pg.waitForTimeout(900)
    await pg.locator('[role="dialog"] li').filter({ hasText: /LED wall/i }).first().getByRole("button", { name: "Add", exact: true }).click()
    await pg.waitForTimeout(2000)
  })
} finally {
  for (const [dt, name] of made.reverse()) {
    await api(ctx, "frappe.client.delete", { doctype: dt, name }).catch((e) => console.log("cleanup", dt, name, e.message))
  }
  await done()
}
