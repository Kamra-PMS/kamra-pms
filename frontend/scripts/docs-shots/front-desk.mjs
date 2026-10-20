// Screenshots and GIFs for docs-site/front-desk.md.
//
//   KAMRA_DOCS_BASE=http://localhost:5176 KAMRA_DOCS_USER=... KAMRA_DOCS_PASSWORD=... \
//   node scripts/docs-shots/front-desk.mjs [only-these,shot-names]
//
// Needs the sample hotel. Creates (once) a few stays of its own so the
// check-in, walk-in and check-out flows have something to act on.

import { session, api, open, shot, gif, typeSlow, done, PROPERTY } from "./lib.mjs"

const only = (process.argv[2] || "").split(",").filter(Boolean)
const want = (n) => !only.length || only.includes(n)

const today = new Date().toISOString().slice(0, 10)
const addDays = (d, n) => {
  const x = new Date(d + "T00:00:00Z")
  x.setUTCDate(x.getUTCDate() + n)
  return x.toISOString().slice(0, 10)
}

/** Find a stay by guest name + status, or create it. */
async function ensureStay(ctx, guest_name, status, make) {
  const rows = await api(ctx, "frappe.client.get_list", {
    doctype: "Reservation",
    filters: { property: PROPERTY, guest_name, status },
    fields: ["name", "room", "precheckin_token", "guest"],
    limit_page_length: 1,
  })
  if (rows.length) return rows[0]
  const r = await make()
  const [row] = await api(ctx, "frappe.client.get_list", {
    doctype: "Reservation",
    filters: { name: r.reservation },
    fields: ["name", "room", "precheckin_token", "guest"],
  })
  return row
}

const ctx = await session()
const page = await ctx.newPage()

// An arrival today with no room yet - the check-in sheet then shows the
// allocator's suggestion.
const arrival = await ensureStay(ctx, "Nikhil Rao", "Confirmed", () =>
  api(ctx, "kamra.api.create_booking", {
    property: PROPERTY, room_type: `${PROPERTY}-DLX`,
    check_in_date: today, check_out_date: addDays(today, 2),
    guest_name: "Nikhil Rao", phone: "+919810011021", adults: 2,
    assign_room: 0, source: "Phone",
  }))

// ---------------------------------------------------------------- Today
if (want("today")) {
  await open(page, "/", 3000)
  await shot(page, "front-desk/today")
}

if (want("arrivals")) {
  await open(page, "/", 3000)
  const card = page.locator("div.rounded-xl, div.rounded-2xl").filter({ has: page.getByText("Arrivals", { exact: true }) }).filter({ has: page.getByRole("button", { name: "Check in" }) }).last()
  await shot(page, "front-desk/arrivals", { locator: card })
}

// ------------------------------------------------------- check-in sheet
if (want("checkin-sheet")) {
  await open(page, "/", 3000)
  const row = page.locator("li").filter({ hasText: "Nikhil Rao" })
  await row.getByRole("button", { name: "Check in" }).click()
  await page.getByText("Registration", { exact: true }).waitFor()
  await page.waitForTimeout(1500)
  const sheet = page.locator("[role=dialog] > div").last()
  const b = await sheet.boundingBox()
  await shot(page, "front-desk/checkin-sheet", { clip: { x: b.x, y: 0, width: b.width, height: 420 } })
  await page.keyboard.press("Escape")
}

// --------------------------------------------------- self check-in page
if (want("precheckin")) {
  const phone = await session({ viewport: { width: 420, height: 900 } })
  const p = await phone.newPage()
  await open(p, `/checkin/${arrival.precheckin_token}`, 2500)
  await shot(p, "front-desk/precheckin", { fullPage: true })
  await phone.close()
}

// ------------------------------------------------------------------ GRC
async function stayOf(guest_name, status = "Checked In") {
  const [r] = await api(ctx, "frappe.client.get_list", {
    doctype: "Reservation", filters: { property: PROPERTY, guest_name, status },
    fields: ["name"], limit_page_length: 1,
  })
  return r?.name
}
if (want("grc")) {
  const res = await stayOf("Priya Nair")
  await open(page, `/grc/${res}`, 3000)
  await shot(page, "front-desk/grc")
  const occ = page.locator("div.rounded-xl").filter({ has: page.getByRole("heading", { name: "Occupant register" }) })
  await occ.scrollIntoViewIfNeeded()
  await shot(page, "front-desk/grc-occupants", { locator: occ })
}
if (want("change-room")) {
  const res = await stayOf("Priya Nair")
  await open(page, `/grc/${res}`, 3000)
  await page.getByRole("button", { name: "Change room" }).first().click()
  await page.getByRole("dialog", { name: "Change room" }).getByRole("radio", { name: "All types (upgrade)" }).click()
  await page.waitForTimeout(800)
  const dlg = page.getByRole("dialog", { name: "Change room" })
  await dlg.getByRole("button", { name: /^30[0-9]/ }).filter({ hasNot: page.locator("svg") }).first().click().catch(() => {})
  await page.waitForTimeout(2000)
  await shot(page, "front-desk/change-room", { locator: dlg.locator("> div").last() })
  await page.keyboard.press("Escape")
}

// ---------------------------------------------------------- departures
if (want("departures")) {
  await open(page, "/", 3000)
  const card = page.locator("div.rounded-xl, div.rounded-2xl").filter({ has: page.getByText("Departures", { exact: true }) }).filter({ has: page.getByRole("button", { name: "Check out" }) }).last()
  await shot(page, "front-desk/departures", { locator: card })
}

// --------------------------------------------------------------- guests
if (want("guests")) {
  await open(page, "/guests", 2500)
  await shot(page, "front-desk/guests", { locator: page.locator("main div.rounded-xl, main div.rounded-2xl").first() })
}
if (want("guest-journey")) {
  const [g] = await api(ctx, "frappe.client.get_list", {
    doctype: "Guest", filters: { full_name: "Priya Nair" }, fields: ["name"], limit_page_length: 1,
  })
  await open(page, `/guests/${g.name}`, 3000)
  await shot(page, "front-desk/guest-journey")
}

// ------------------------------------------------------------- walk-in
async function fillWalkIn(p, slow) {
  await p.getByRole("button", { name: "Walk-in", exact: true }).click()
  const dlg = p.getByRole("dialog", { name: "Walk-in" })
  await dlg.waitFor()
  await p.waitForTimeout(800)
  const name = dlg.getByPlaceholder("Type to find or create")
  slow ? await typeSlow(name, "Farhan Qureshi", 45) : await name.fill("Farhan Qureshi")
  const phone = dlg.locator("input[type=tel]").first()
  slow ? await typeSlow(phone, "9810011031", 40) : await phone.fill("9810011031")
  const idType = dlg.locator("label").filter({ hasText: "ID type" }).locator("select")
  await idType.selectOption({ index: 1 })
  const idNo = dlg.locator("label").filter({ hasText: "ID number" }).locator("input")
  slow ? await typeSlow(idNo, "XXXX XXXX 4417", 40) : await idNo.fill("XXXX XXXX 4417")
  await dlg.locator("label").filter({ hasText: "Room type" }).locator("select").selectOption(`${PROPERTY}-STD`)
  await p.waitForTimeout(1500)
  // pick a room nobody is in (the list can include a room whose guest
  // departs today but has not checked out yet)
  await dlg.locator("select").nth(2).selectOption(`${PROPERTY}-105`)
  await p.waitForTimeout(400)
  const amt = dlg.locator("label").filter({ hasText: "Amount collected" }).locator("input")
  await amt.fill("0")
  await p.waitForTimeout(1200)
  return dlg
}
if (want("walkin")) {
  await open(page, "/", 2500)
  const dlg = await fillWalkIn(page, false)
  await shot(page, "front-desk/walkin", { clip: { x: 480, y: 0, width: 960, height: 900 } })
  await page.keyboard.press("Escape")
  await dlg.getByRole("button", { name: "Cancel" }).click().catch(() => {})
}
if (want("walkin-gif")) {
  await gif("front-desk/walkin", async (p) => {
    await open(p, "/", 2500)
    const dlg = await fillWalkIn(p, true)
    await dlg.getByRole("button", { name: "Check in", exact: true }).click()
    await p.getByText(/Checked in · Room/).waitFor({ timeout: 15000 })
    await p.waitForTimeout(2500)
  }, { crop: { x: 480, y: 0, width: 960, height: 900 } })
}

// ------------------------------------------------------------ check-in
if (want("checkin-gif")) {
  await gif("front-desk/checkin", async (p) => {
    await open(p, "/", 2500)
    await p.waitForTimeout(600)
    const row = p.locator("li").filter({ hasText: "Nikhil Rao" })
    await row.getByRole("button", { name: "Check in" }).click()
    await p.getByText("Registration", { exact: true }).waitFor()
    await p.waitForTimeout(2000)
    // the suggestion can be a room whose guest leaves today but is still
    // in it - pick a room that is empty now
    await p.locator("[role=dialog] select").selectOption(`${PROPERTY}-205`)
    await p.waitForTimeout(1200)
    const go = p.locator("[role=dialog] button").filter({ hasText: "Check in to" })
    await go.hover()
    await p.waitForTimeout(600)
    await go.click()
    await p.waitForTimeout(3000)
  })
}

// ------------------------------------- check-out blocked by a balance
if (want("checkout-owed")) {
  const res = await stayOf("Nikhil Rao")
  await open(page, "/reservations", 2500)
  await page.locator("tr").filter({ hasText: res }).first().click()
  await page.getByRole("button", { name: "Check out" }).waitFor()
  await page.getByRole("button", { name: "Check out" }).click()
  await page.getByText(/Cannot check out/).waitFor({ timeout: 10000 })
  await page.waitForTimeout(500)
  const err = page.locator("div.rounded-lg.border-rose-200").filter({ hasText: "Cannot check out" }).first()
  await err.scrollIntoViewIfNeeded()
  const panel = page.locator("[role=dialog] > div").last()
  await shot(page, "front-desk/checkout-owed", { locator: err })
}

// ------------------------------------------------ check out (no image)
if (want("checkout")) {
  await open(page, "/", 2500)
  const row = page.locator("li").filter({ hasText: "Sneha Iyer" })
  await row.getByRole("button", { name: "Check out" }).click()
  await page.waitForTimeout(3000)
  const err = await page.locator("div.border-rose-200").first().textContent().catch(() => null)
  console.log("checkout Sneha Iyer:", err || "ok")
}

await page.close()
await ctx.close()
await done()
console.log("arrival", arrival)
