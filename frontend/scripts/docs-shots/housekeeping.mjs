// Docs images for docs-site/housekeeping.md - the Room Board, tasks, the
// phone app at /hk, laundry, lost & found, shift handover and the
// housekeeping settings. Sets up a morning's worth of cleans on the sample
// hotel first; re-running clears the tasks it made last time.
import { api, done, gif, open, PROPERTY, session, shot } from "./lib.mjs"

const ME = process.env.KAMRA_DOCS_USER
const HK = "hk@kamra.local"
const room = (n) => `${PROPERTY}-${n}`
const PHONE = { width: 390, height: 844 }
const sheet = (page) => page.locator("[role=dialog] > div").nth(1)

const ctx = await session()
const page = await ctx.newPage()

// --- data -------------------------------------------------------------------
const MINE = ["104", "105", "106", "201", "203", "204"]
const old = await api(ctx, "frappe.client.get_list", {
  doctype: "Housekeeping Task",
  filters: { property: PROPERTY, room: ["in", MINE.map(room)], status: ["in", ["Pending", "In Progress"]] },
  fields: ["name"], limit_page_length: 100,
})
for (const t of old) {
  // tasks with an activity-log entry can't be deleted; close them instead
  await api(ctx, "frappe.client.delete", { doctype: "Housekeeping Task", name: t.name })
    .catch(() => api(ctx, "kamra.api.hk_update_task", { task: t.name, status: "Done" }))
}

for (const [n, s] of [["104", "Dirty"], ["105", "Dirty"], ["204", "Dirty"], ["201", "Dirty"], ["106", "Inspected"]])
  await api(ctx, "kamra.api.set_housekeeping_status", { room: room(n), status: s })

const task = async (n, task_type, priority, extra = {}) =>
  (await api(ctx, "frappe.client.insert", { doc: {
    doctype: "Housekeeping Task", property: PROPERTY, room: room(n), task_type, priority, status: "Pending", ...extra,
  } })).name
const past = (min) => {
  const d = new Date(Date.now() - min * 60000)
  const p = (x) => String(x).padStart(2, "0")
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:00`
}

const t203 = await task("203", "Checkout Clean", "High", { notes: "Arrival today - fresh flowers on the desk" })
const t104 = await task("104", "Checkout Clean", "High")
await task("105", "Checkout Clean", "Medium")
await task("201", "Stayover Clean", "Medium", { due_by: past(12) })
const t204 = await task("204", "Checkout Clean", "Medium")
await api(ctx, "kamra.api.hk_assign_task", { task: t203, user: ME })
await api(ctx, "kamra.api.hk_assign_task", { task: t104, user: ME })
await api(ctx, "kamra.api.hk_accept_task", { task: t104 })
await api(ctx, "kamra.api.hk_assign_task", { task: t204, user: HK })

// a laundry pickup waiting at room 101 (old ones from earlier runs removed)
const oldLaundry = await api(ctx, "frappe.client.get_list", {
  doctype: "Laundry Order", filters: { property: PROPERTY, room: room("101") }, fields: ["name"], limit_page_length: 50,
})
for (const o of oldLaundry) {
  await api(ctx, "frappe.client.delete", { doctype: "Laundry Order", name: o.name })
    .catch(() => api(ctx, "kamra.laundry.cancel_laundry", { order: o.name, reason: "Docs re-run" }).catch(() => {}))
}
await api(ctx, "kamra.laundry.request_pickup", { property: PROPERTY, room: room("101"), notes: "Bag on the door after 3 pm" })

// --- the Room Board ------------------------------------------------------------
const SHOTS = !process.env.ONLY_GIFS // ONLY_GIFS=1 re-records just the GIFs
if (SHOTS) {
// one room out of order and one passed inspection (Ready), put back after
await api(ctx, "kamra.api.set_housekeeping_status", { room: room("303"), status: "Out of Order" })
await api(ctx, "kamra.api.set_housekeeping_status", { room: room("103"), status: "Ready" })
try {
  await open(page, "/housekeeping-board", 2500)
  await shot(page, "housekeeping/room-board")
} finally {
  await api(ctx, "kamra.api.set_housekeeping_status", { room: room("303"), status: "Clean" })
  await api(ctx, "kamra.api.set_housekeeping_status", { room: room("103"), status: "Clean" })
}
await open(page, "/housekeeping-board", 2500)
await page.getByRole("button", { name: /^105/ }).click()
await page.waitForTimeout(400)
// the menu: Mark … options, then (for a supervisor) the assign list
{
  const menu = await page.getByRole("menu").boundingBox()
  await shot(page, "housekeeping/room-board-menu", {
    clip: { x: 272, y: 370, width: 1120, height: Math.max(290, menu.y + menu.height + 16 - 370) },
  })
}

// --- the task list ------------------------------------------------------------
await open(page, "/housekeeping", 2500)
{
  // newest first: the open cleans on top (earlier runs leave Done rows below)
  const box = await page.getByText("Housekeeping Tasks").locator("xpath=ancestor::div[contains(@class,'rounded')][1]").boundingBox()
  await shot(page, "housekeeping/tasks", { clip: { x: box.x - 1, y: box.y - 1, width: box.width + 2, height: 400 } })
}
await page.getByRole("button", { name: "New", exact: true }).click()
await page.waitForTimeout(600)
await shot(page, "housekeeping/new-task", { clip: { x: 480, y: 0, width: 960, height: 340 } })

// --- settings -----------------------------------------------------------------
await open(page, "/settings/housekeeping", 2500)
await page.setViewportSize({ width: 1440, height: 1500 })
await page.waitForTimeout(400)
await shot(page, "housekeeping/settings", { clip: { x: 530, y: 80, width: 880, height: 895 } })
await page.setViewportSize({ width: 1440, height: 900 })

// --- laundry ----------------------------------------------------------------
await open(page, "/laundry", 2500)
await shot(page, "housekeeping/laundry-board")
await page.getByRole("button", { name: "Price menu" }).click()
await page.waitForTimeout(800)
await shot(page, "housekeeping/laundry-price-menu", { clip: { x: 430, y: 80, width: 805, height: 520 } })
await page.getByRole("button", { name: "Board" }).click()
await page.waitForTimeout(500)
await page.setViewportSize({ width: 1440, height: 640 })
await page.getByRole("button", { name: "Return & deliver" }).first().click()
await page.waitForTimeout(600)
const more = page.locator("[role=dialog] button[aria-label='more']")
await more.nth(0).click(); await more.nth(0).click()
await page.locator("[role=dialog] input, [role=dialog] textarea").last().fill("Saree still at the dry cleaner - back tomorrow")
await page.waitForTimeout(300)
await shot(page, "housekeeping/laundry-return", { locator: sheet(page) })
await page.setViewportSize({ width: 1440, height: 900 })

// --- lost & found, shift handover -------------------------------------------
await open(page, "/shifts", 2500)
await shot(page, "housekeeping/shift-handover", { locator: page.locator("main .rounded-xl, main [class*=card]").first() })

// --- the phone app --------------------------------------------------------------
const phone = await session({ viewport: PHONE })
const p = await phone.newPage()
await open(p, "/hk", 2500)
await shot(p, "housekeeping/hk-my-tasks")
// an inspection card: a supervisor sees Pass inspection (removed again below)
{
  const insp = await task("106", "Inspection", "High")
  try {
    await api(ctx, "kamra.api.hk_assign_task", { task: insp, user: ME })
    await api(ctx, "kamra.api.hk_accept_task", { task: insp })
    await open(p, "/hk", 2500)
    const card = p.locator("li").filter({ has: p.getByText("106", { exact: true }) })
    await card.scrollIntoViewIfNeeded()
    await shot(p, "housekeeping/hk-inspection", { locator: card })
  } finally {
    await api(ctx, "frappe.client.delete", { doctype: "Housekeeping Task", name: insp })
      .catch(() => api(ctx, "frappe.client.set_value", { doctype: "Housekeeping Task", name: insp, fieldname: "status", value: "Done" }))
  }
}
await p.getByRole("button", { name: /^Available/ }).click()
await p.waitForTimeout(500)
await shot(p, "housekeeping/hk-available", { clip: { x: 0, y: 0, width: 390, height: 580 } })
await p.getByRole("button", { name: /^Rooms$/ }).click()
await p.waitForTimeout(500)
await p.getByRole("button", { name: /^101/ }).click()
await p.waitForTimeout(300)
await p.getByPlaceholder("e.g. 2 cola, 1 water").fill("2 cola, 1 water")
await p.getByPlaceholder(/^Amount/).fill("240")
await p.waitForTimeout(300)
await shot(p, "housekeeping/hk-post-charge")
await p.keyboard.press("Escape")
await open(p, "/hk", 2000)
await p.getByRole("button", { name: "Log a lost or found item" }).click()
await p.waitForTimeout(300)
await p.getByPlaceholder("What is it? (e.g. black umbrella)").fill("Grey hoodie")
await p.locator("select").selectOption(room("204"))
await p.waitForTimeout(300)
await shot(p, "housekeeping/hk-log-item")
const logged = await api(ctx, "frappe.client.get_list", {
  doctype: "Lost And Found Item", filters: { property: PROPERTY, item_description: "Grey hoodie" }, fields: ["name"],
})
if (!logged.length) {
  await p.getByRole("button", { name: "Log it" }).click()
  await p.waitForTimeout(800)
}

await open(page, "/lost-found", 2500)
await shot(page, "housekeeping/lost-found", { locator: page.locator("main .rounded-xl, main [class*=card]").first() })
}

// a housekeeper takes room 105 from the pool, starts it and finishes it
if (!process.env.SKIP_GIFS) {
await gif("housekeeping/hk-take-and-finish", async (g) => {
  await open(g, "/hk", 2000)
  await g.waitForTimeout(600)
  await g.getByRole("button", { name: /^Available/ }).click()
  await g.waitForTimeout(1200)
  const card = g.locator("li").filter({ has: g.getByText("105", { exact: true }) })
  await card.getByRole("button", { name: "Take this room" }).click()
  await g.waitForTimeout(1200)
  await g.getByRole("button", { name: /^My Tasks/ }).click()
  await g.waitForTimeout(1200)
  const mine = g.locator("li").filter({ has: g.getByText("105", { exact: true }) })
  await mine.scrollIntoViewIfNeeded()
  await g.waitForTimeout(600)
  await mine.getByRole("button", { name: "Start" }).click()
  await g.waitForTimeout(1500)
  await mine.getByRole("button", { name: /^Done/ }).click()
  await g.waitForTimeout(1500)
  await g.getByRole("button", { name: /^Rooms$/ }).click()
  await g.waitForTimeout(1500)
}, { viewport: PHONE, width: 390 })

// laundry: count a bag with the guest at room 101
await gif("housekeeping/laundry-collect", async (g) => {
  await open(g, "/laundry", 2200)
  await g.waitForTimeout(600)
  await g.getByRole("button", { name: "Collect & count" }).first().click()
  await g.waitForTimeout(1000)
  const plus = g.locator("[role=dialog] button[aria-label='more']")
  await plus.first().waitFor()
  for (const i of [0, 0, 1, 3]) { await plus.nth(i).click(); await g.waitForTimeout(450) }
  await g.waitForTimeout(800)
  await g.locator("[role=dialog]").getByRole("button", { name: /^Collect \d/ }).click()
  await g.waitForTimeout(1800)
}, { width: 960, crop: { x: 250, y: 0, width: 1190, height: 900 } })
}

await done()
