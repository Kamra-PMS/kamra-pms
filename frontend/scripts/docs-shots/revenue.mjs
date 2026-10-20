// Images for docs-site/revenue.md.
// Adds a few sample revenue records (season, guardrails, rate plan, meal
// plans, voucher, company, agent) for the shots and removes them afterwards.
import { session, api, open, shot, gif, typeSlow, done, PROPERTY } from "./lib.mjs"

const P = PROPERTY
const ctx = await session()
const page = await ctx.newPage()
const made = []
async function add(doc) {
  const d = await api(ctx, "frappe.client.insert", { doc })
  made.push([doc.doctype, d.name])
  return d
}
const card = () => page.locator("div.rounded-xl.border.bg-white.shadow-sm").first()
const sheet = () => page.locator('[role="dialog"] > div.shadow-2xl')
async function openRow(text) {
  await page.getByRole("cell", { name: text, exact: true }).first().click()
  await page.waitForTimeout(900)
}
async function closeSheet() {
  await page.keyboard.press("Escape")
  await page.waitForTimeout(500)
}

try {
  const year = new Date().getFullYear()
  await add({ doctype: "Season", property: P, season_name: "Year-end peak",
    start_date: `${year}-12-24`, end_date: `${year + 1}-01-01`,
    adjustment_type: "Percent", adjustment_value: 25, priority: 10,
    minimum_nights: 2, non_refundable: 1 })
  await add({ doctype: "Season", property: P, season_name: "Monsoon saver",
    room_type: `${P}-STD`, start_date: `${year + 1}-07-01`, end_date: `${year + 1}-08-31`,
    adjustment_type: "Amount", adjustment_value: -400, priority: 5 })
  await add({ doctype: "Rate Guardrail", property: P, room_type: `${P}-DLX`,
    floor_price: 3500, ceiling_price: 9000 })
  await add({ doctype: "Rate Guardrail", property: P, room_type: `${P}-DLX`,
    floor_price: 4500, ceiling_price: 11000, days_of_week: "fri, sat" })
  await add({ doctype: "Rate Guardrail", property: P,
    floor_price: 2200, ceiling_price: 15000 })
  await add({ doctype: "Rate Plan", property: P, rate_plan_name: "Non-refundable",
    code: "NRF", modifier_type: "Percent", modifier_value: -10,
    cancellation_policy: "No refund after booking" })
  await add({ doctype: "Rate Plan", property: P, rate_plan_name: "Corporate",
    code: "CORP", modifier_type: "Percent", modifier_value: -15,
    cancellation_policy: "Free until 24 hours before arrival" })
  await add({ doctype: "Meal Plan", property: P, code: "CP", label: "Bed & breakfast",
    price_per_adult: 450, price_per_child: 225 })
  await add({ doctype: "Meal Plan", property: P, code: "MAP", label: "Breakfast & dinner",
    price_per_adult: 1100, price_per_child: 550 })
  await add({ doctype: "Discount Voucher", property: P, voucher_code: "STAYLONGER",
    discount_type: "Percent", value: 10, valid_to: `${year + 1}-03-31`, min_nights: 3, max_uses: 100 })
  await add({ doctype: "Discount Voucher", property: P, voucher_code: "WELCOME500",
    discount_type: "Amount", value: 500, valid_to: `${year}-12-31`, min_nights: 1 })
  await add({ doctype: "Corporate Account", company_name: "Northwind Analytics",
    contact_name: "Meera Rao", contact_phone: "+91 98450 22001",
    negotiated_rate_plan: made.find((m) => m[0] === "Rate Plan" && m[1].includes("CORP"))?.[1] ?? null,
    credit_allowed: 1 })
  await add({ doctype: "Travel Agent", agent_name: "Coastline Holidays",
    agent_type: "Travel Agent", commission_pct: 10, contact_phone: "+91 98860 33002" })

  // room types
  await open(page, "/room-types")
  await shot(page, "revenue/room-types", { locator: card() })
  await openRow("Deluxe")
  await shot(page, "revenue/room-type-form")
  await closeSheet()

  await open(page, "/rate-plans")
  await shot(page, "revenue/rate-plans", { locator: card() })

  await open(page, "/seasons")
  await shot(page, "revenue/seasons", { locator: card() })
  await openRow("Year-end peak")
  await shot(page, "revenue/season-form")
  await closeSheet()

  await open(page, "/guardrails")
  await shot(page, "revenue/guardrails", { locator: card() })

  await open(page, "/meal-plans")
  await shot(page, "revenue/meal-plans", { locator: card() })

  await open(page, "/vouchers")
  await shot(page, "revenue/vouchers", { locator: card() })

  await open(page, "/companies")
  await openRow("Northwind Analytics")
  await shot(page, "revenue/company-form")
  await closeSheet()

  await open(page, "/experiences")
  await shot(page, "revenue/experiences", { locator: card() })

  // a Deluxe-only demand tier next to the house-wide ones (removed below)
  const tier = await api(ctx, "kamra.api.save_hurdle_rate", {
    property: P, occupancy_from: 85, premium_pct: 25, min_rate: 0, room_type: `${P}-DLX` })
  try {
    await open(page, "/settings/revenue", 2500)
    await shot(page, "revenue/settings")
  } finally {
    await api(ctx, "kamra.api.delete_hurdle_rate", { name: tier.name })
  }


  // the quote on the desk booking form, with the season and meal plan in it
  if (!process.env.SKIP_GIFS) await gif("revenue/season-new", async (pg) => {
    await open(pg, "/seasons", 1500)
    await pg.getByRole("button", { name: "New", exact: true }).click()
    await pg.waitForTimeout(700)
    const s = pg.locator('[role="dialog"]')
    await typeSlow(s.getByLabel("Name"), "Diwali week")
    await s.getByLabel("Start date").fill(`${year}-11-06`)
    await pg.waitForTimeout(300)
    await s.getByLabel("End date (inclusive)").fill(`${year}-11-10`)
    await pg.waitForTimeout(300)
    await s.getByLabel("Adjustment").selectOption("Percent")
    await typeSlow(s.getByLabel("Value (20 = +20%)"), "20")
    await typeSlow(s.getByLabel("Priority"), "20")
    await typeSlow(s.getByLabel("Minimum nights"), "2")
    await pg.waitForTimeout(600)
    // Cancel rather than save: the shot shows the form, the sample hotel
    // keeps its rates
    await s.getByRole("button", { name: "Cancel" }).click()
    await pg.waitForTimeout(600)
  })
} finally {
  for (const [dt, name] of made.reverse()) {
    await api(ctx, "frappe.client.delete", { doctype: dt, name }).catch((e) => console.log("cleanup", dt, name, e.message))
  }
  await done()
}
