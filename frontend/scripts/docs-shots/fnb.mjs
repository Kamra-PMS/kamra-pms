// Docs images for docs-site/fnb.md - the restaurant POS, kitchen display,
// kitchen printers and F&B settings. Sets up a lunch service on the sample
// hotel first (idempotent enough to re-run on a fresh seed).
import { api, done, gif, open, PROPERTY, session, settle, shot, typeSlow } from "./lib.mjs"

const TERRACE = `${PROPERTY}-The Terrace Restaurant`
const BAR = `${PROPERTY}-Poolside Bar`

const ctx = await session()
const page = await ctx.newPage()

// --- data -------------------------------------------------------------------
const MORE = [
  [TERRACE, "Tomato Shorba", "Starter", "Kitchen", 180, "Starters"],
  [TERRACE, "Chicken 65", "Starter", "Fryer", 320, "Starters"],
  [TERRACE, "Tandoori Roti", "Main", "Tandoor", 40, "North Indian"],
  [TERRACE, "Dal Makhani", "Main", "Kitchen", 290, "North Indian"],
  [TERRACE, "Fish Curry & Rice", "Main", "Kitchen", 420, "Rice"],
  [TERRACE, "Mango Kulfi", "Dessert", "Kitchen", 150, "Desserts"],
  [BAR, "Masala Chaas", "Drink", "Bar", 90, "Beverages"],
  [BAR, "Watermelon Cooler", "Drink", "Bar", 160, "Beverages"],
]
const existing = await api(ctx, "frappe.client.get_list", {
  doctype: "Menu Item", filters: { property: PROPERTY }, fields: ["name", "item_name", "outlet", "category"], limit_page_length: 200,
})
for (const [outlet, item_name, course, prep_station, price, category] of MORE) {
  const have = existing.find((m) => m.item_name === item_name)
  if (have) {
    if (have.category !== category) {
      await api(ctx, "frappe.client.set_value", { doctype: "Menu Item", name: have.name, fieldname: "category", value: category })
    }
    continue
  }
  await api(ctx, "frappe.client.insert", { doc: {
    doctype: "Menu Item", property: PROPERTY, outlet, item_name, course, prep_station, price, category,
    is_veg: /Chicken|Fish/.test(item_name) ? 0 : 1, available: 1,
  } })
}
// the seed's lime-soda photo URL is dead; a broken image is worse than none
const soda = existing.find((m) => m.item_name === "Fresh Lime Soda")
if (soda) await api(ctx, "frappe.client.set_value", { doctype: "Menu Item", name: soda.name, fieldname: "image", value: "" })
const menu = await api(ctx, "frappe.client.get_list", {
  doctype: "Menu Item", filters: { property: PROPERTY }, fields: ["name", "item_name", "outlet"], limit_page_length: 200,
})
const mi = (n) => menu.find((m) => m.item_name === n).name

// two kitchen printers: the main kitchen serves both outlets' food, the bar its drinks
const ensure = async (printer) => {
  const printers = await api(ctx, "kamra.printing.printers", { property: PROPERTY })
  const p = printers.find((x) => x.printer_name === printer.printer_name)
  return (await api(ctx, "kamra.printing.save_printer", { property: PROPERTY, name: p?.name || null, printer: JSON.stringify(printer) })).name
}
const main = await ensure({ printer_name: "Main kitchen", routes: [
  { outlet: TERRACE, prep_station: "" }] })
const bar = await ensure({ printer_name: "Bar", routes: [{ outlet: BAR, prep_station: "Bar" }] })
await ensure({ printer_name: "Main kitchen", fallback_printer: bar, routes: [{ outlet: TERRACE, prep_station: "" }] })

// a lunch service: running tables, one with a round in the kitchen, one ready
const open_ = await api(ctx, "kamra.pos.open_orders", { outlet: TERRACE })
if (open_.length < 3) {
  const t2 = await api(ctx, "kamra.pos.send_order", { outlet: TERRACE, table_no: "T2", guests: 3,
    items: JSON.stringify([{ menu_item: mi("Paneer Tikka"), qty: 1 }, { menu_item: mi("Butter Chicken"), qty: 2 },
      { menu_item: mi("Tandoori Roti"), qty: 4, instructions: "butter on top" }]) })
  await api(ctx, "kamra.pos.send_order", { outlet: TERRACE, table_no: "T5", guests: 2,
    items: JSON.stringify([{ menu_item: mi("Masala Dosa"), qty: 2 }, { menu_item: mi("Tomato Shorba"), qty: 2 }]) })
  const f1 = await api(ctx, "kamra.pos.send_order", { outlet: TERRACE, table_no: "F1", guests: 5,
    allergy_note: "One guest: no peanuts",
    items: JSON.stringify([{ menu_item: mi("Veg Biryani"), qty: 2 }, { menu_item: mi("Dal Makhani"), qty: 1 },
      { menu_item: mi("Chicken 65"), qty: 1 }]) })
  await api(ctx, "kamra.pos.accept_ticket", { order: t2.order })
  await api(ctx, "kamra.pos.accept_ticket", { order: f1.order })
  await api(ctx, "kamra.pos.mark_prepared", { order: f1.order })
  await api(ctx, "kamra.pos.create_order", { outlet: TERRACE, table_no: "P3", guests: 2,
    items: JSON.stringify([{ menu_item: mi("Fish Curry & Rice"), qty: 2 }]) })
  await api(ctx, "kamra.pos.send_order", { outlet: BAR, table_no: "L2", guests: 4,
    items: JSON.stringify([{ menu_item: mi("Kingfisher Beer"), qty: 3 }, { menu_item: mi("Fresh Lime Soda"), qty: 1 }]) })
}
// something settled today, so the dashboard has numbers
const running = await api(ctx, "kamra.pos.open_orders", { outlet: TERRACE })
const t5 = running.find((o) => o.table_no === "T5")
// settling needs an open till; skip quietly if nobody has one open
const pay = (order, mode) => api(ctx, "kamra.pos.pay_order", { order, mode }).catch((e) => console.log("skip pay:", String(e).slice(0, 80)))
if (t5) await pay(t5.name, "Card")

// print stations would claim these; mark the backlog printed so status is clean
for (const p of [main, bar]) {
  const jobs = await api(ctx, "kamra.printing.claim_jobs", { printer: p })
  if (jobs.length) await api(ctx, "kamra.printing.ack_jobs", { printer: p, printed: JSON.stringify(jobs.map((j) => j.job)) })
}

// The POS picks its first outlet when the outlet list loads; in dev mode that
// load can land after our choice, so choose until it sticks.
const pickOutlet = async (p, label) => {
  const sel = p.locator("select").filter({ hasText: label }).first()
  for (let i = 0; i < 6; i++) {
    await sel.selectOption({ label })
    await settle(p, 1200)
    const shown = await sel.evaluate((el) => el.options[el.selectedIndex]?.text)
    if (shown === label) return
  }
  throw new Error(`outlet ${label} did not stick`)
}

const ONLY_GIFS = process.env.ONLY_GIFS === "1"
// --- screenshots --------------------------------------------------------------
if (!ONLY_GIFS) {
await open(page, "/pos", 2500)
await pickOutlet(page, "The Terrace Restaurant")
await shot(page, "fnb/pos")

// a running bill
await page.getByText("Table T2", { exact: false }).first().click()
await page.waitForTimeout(1500)
await shot(page, "fnb/pos-bill")

await open(page, "/kitchen", 2500)
await shot(page, "fnb/kitchen-display")
await page.locator("select").filter({ hasText: "Don't print here" }).first().selectOption({ label: "Print for Main kitchen" })
await page.waitForTimeout(2500)
await shot(page, "fnb/kitchen-print-for", { clip: { x: 236, y: 70, width: 1100, height: 100 } })

await open(page, "/settings/fnb", 2500)
const kotHead = page.getByText("Kitchen orders (KOT)", { exact: true })
await kotHead.scrollIntoViewIfNeeded()
const hb = await kotHead.boundingBox()
await shot(page, "fnb/settings-kot", { clip: { x: hb.x - 16, y: hb.y - 12, width: 880, height: 330 } })
const printersCard = page.locator("div.rounded-xl, div[class*='card'], section").filter({ has: page.getByText("Kitchen printers", { exact: true }) }).last()
await printersCard.scrollIntoViewIfNeeded()
await shot(page, "fnb/kitchen-printers", { locator: printersCard })
await printersCard.getByRole("button", { name: "Edit" }).nth(1).click()
await page.waitForTimeout(800)
await shot(page, "fnb/printer-form", { locator: printersCard })
await printersCard.getByRole("button", { name: "Cancel" }).click()

const speedCard = page.locator("div.rounded-xl, div[class*='card'], section").filter({ has: page.getByText("POS speed check", { exact: true }) }).last()
await speedCard.getByRole("button", { name: "Check speed" }).click()
await speedCard.getByText(/Network round trip/).waitFor({ timeout: 30_000 })
await speedCard.getByText(/Live updates/).waitFor({ timeout: 30_000 })
await page.waitForTimeout(500)
await shot(page, "fnb/speed-check", { locator: speedCard })

await open(page, "/outlets", 2000)
await shot(page, "fnb/outlets")
await page.getByText("The Terrace Restaurant").first().click()
await page.waitForTimeout(1200)
await shot(page, "fnb/outlet-form")

await open(page, "/menu-items", 2000)
await shot(page, "fnb/menu")
await open(page, "/inventory", 2000)
await pickOutlet(page, "The Terrace Restaurant").catch(() => {})
await shot(page, "fnb/inventory")
await open(page, "/qr-codes", 2000)
await shot(page, "fnb/qr-codes")
await open(page, "/pos-dashboard", 2500)
await pickOutlet(page, "The Terrace Restaurant")
await shot(page, "fnb/dashboard")

}

// --- GIFs -----------------------------------------------------------------------
// earlier runs' T7 bills: settle them so the GIF starts from a free table
for (const o of await api(ctx, "kamra.pos.open_orders", { outlet: TERRACE })) {
  if (o.table_no === "T7") await pay(o.name, "Cash")
}
await gif("fnb/send-order", async (p, _c, rec) => {
  await open(p, "/pos", 2000)
  await pickOutlet(p, "The Terrace Restaurant")
  rec()
  await p.waitForTimeout(600)
  await p.getByRole("button", { name: /New Bill/ }).click()
  await p.waitForTimeout(500)
  const tableSel = p.locator("select").filter({ hasText: "Table…" }).first()
  const t7 = await tableSel.locator("option").filter({ hasText: /^T7\b/ }).first().getAttribute("value")
  await tableSel.selectOption(t7)
  await p.waitForTimeout(500)
  await typeSlow(p.getByPlaceholder(/Search menu items/), "dal")
  await p.getByText("Dal Makhani").first().waitFor({ timeout: 15_000 })
  await p.waitForTimeout(400)
  await p.getByText("Dal Makhani").first().click()
  await p.getByPlaceholder(/Search menu items/).fill("")
  await p.waitForTimeout(400)
  await p.getByText("Tandoori Roti").first().click()
  await p.getByText("Tandoori Roti").first().click()
  await p.waitForTimeout(700)
  await p.getByRole("button", { name: /Send to kitchen|Send and print/ }).click()
  await p.waitForTimeout(2500)
})

await gif("fnb/kitchen-flow", async (p, _c, rec) => {
  await open(p, "/kitchen", 2500)
  rec()
  await p.waitForTimeout(600)
  const start = p.getByRole("button", { name: "Start" }).first()
  if (await start.count()) { await start.click(); await p.waitForTimeout(1500) }
  const ready = p.getByRole("button", { name: /Mark ready|All ready|Ready/ }).first()
  if (await ready.count()) { await ready.click(); await p.waitForTimeout(1800) }
}, { crop: { x: 224, y: 60, width: 1216, height: 760 } })

// what a kitchen screen does every few seconds: check in for its printer,
// so both show as online while the settings GIF records
for (const p of [main, bar]) await api(ctx, "kamra.printing.claim_jobs", { printer: p })
await gif("fnb/printer-setup", async (p, _c, rec) => {
  await open(p, "/settings/fnb", 2000)
  const card = p.locator("div.rounded-xl, div[class*='card'], section").filter({ has: p.getByText("Kitchen printers", { exact: true }) }).last()
  await card.scrollIntoViewIfNeeded()
  rec()
  await p.waitForTimeout(800)
  await card.getByRole("button", { name: "Add printer" }).click()
  await p.waitForTimeout(500)
  await typeSlow(card.getByPlaceholder("Main kitchen"), "Tandoor")
  await p.waitForTimeout(300)
  await card.getByLabel("The Terrace Restaurant - Tandoor").check()
  await p.waitForTimeout(400)
  await card.locator("select").filter({ hasText: "None" }).selectOption({ label: "Main kitchen" })
  await p.waitForTimeout(600)
  await card.getByRole("button", { name: "Save printer" }).click()
  await p.waitForTimeout(1800)
})
// the GIF's printer was for show
const after = await api(ctx, "kamra.printing.printers", { property: PROPERTY })
for (const p of after.filter((x) => x.printer_name === "Tandoor")) {
  await api(ctx, "kamra.printing.delete_printer", { name: p.name })
}

await done()
