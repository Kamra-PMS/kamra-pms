// Screenshots for the README (docs/screenshots), from the same sample hotel
// as the docs:
//
//   KAMRA_DOCS_BASE=http://localhost:5176 KAMRA_DOCS_USER=... KAMRA_DOCS_PASSWORD=... \
//   node scripts/docs-shots/readme.mjs [only-these,shot-names]

import { session, api, open, shot, done, PROPERTY } from "./lib.mjs"

const only = (process.argv[2] || "").split(",").filter(Boolean)
const want = (n) => !only.length || only.includes(n)
// shot() writes under docs-site/public/img; the README keeps its own folder
const readme = (n) => `../../../docs/screenshots/${n}`

const ctx = await session()
const page = await ctx.newPage()

async function stayOf(guest_name, status = "Checked In") {
  const [r] = await api(ctx, "frappe.client.get_list", {
    doctype: "Reservation", filters: { property: PROPERTY, guest_name, status },
    fields: ["name"], limit_page_length: 1,
  })
  return r?.name
}

if (want("checkin")) {
  // an arrival today with no room yet, so the sheet shows the suggestion
  const today = new Date().toISOString().slice(0, 10)
  const out = new Date(Date.now() + 2 * 864e5).toISOString().slice(0, 10)
  if (!(await stayOf("Meera Kapoor", "Confirmed"))) {
    await api(ctx, "kamra.api.create_booking", {
      property: PROPERTY, room_type: `${PROPERTY}-DLX`,
      check_in_date: today, check_out_date: out,
      guest_name: "Meera Kapoor", phone: "+919810099041", adults: 2,
      assign_room: 0, source: "Phone",
    })
  }
  await open(page, "/", 3000)
  const row = page.locator("li").filter({ hasText: "Meera Kapoor" })
  await row.getByRole("button", { name: "Check in" }).click()
  await page.getByRole("dialog").first().waitFor()
  await page.waitForTimeout(2000)
  await shot(page, readme("checkin"))
  await page.keyboard.press("Escape")
}

if (want("checkout")) {
  await open(page, "/", 3000)
  const row = page.locator("li").filter({ has: page.getByRole("button", { name: "Check out" }) }).first()
  await row.getByRole("button", { name: "Check out" }).click()
  await page.getByText("Stay summary").waitFor({ timeout: 15000 })
  await page.waitForTimeout(2000)
  await shot(page, readme("checkout"))
  await page.keyboard.press("Escape")
}

if (want("folio")) {
  const res = await stayOf("Priya Nair")
  const [f] = await api(ctx, "frappe.client.get_list", {
    doctype: "Folio", filters: { reservation: res }, fields: ["name"], limit_page_length: 1,
  })
  await open(page, `/billing/${f.name}`, 3000)
  await shot(page, readme("invoice"))
}

if (want("pos")) {
  await open(page, "/pos", 3500)
  // the restaurant has the fuller menu; open one of its running bills
  await page.locator("main select").first().selectOption(`${PROPERTY}-The Terrace Restaurant`)
  await page.waitForTimeout(2500)
  await page.locator("button").filter({ hasText: /in kitchen/i }).first().click()
  await page.waitForTimeout(2500)
  await shot(page, readme("pos-bills"))
  await page.getByRole("button", { name: "Back to till" }).click()
  await page.waitForTimeout(2000)
  await shot(page, readme("pos"))
}

if (want("settings")) {
  await open(page, "/settings", 2500)
  await shot(page, readme("settings"))
}

await page.close()
await ctx.close()
await done()
