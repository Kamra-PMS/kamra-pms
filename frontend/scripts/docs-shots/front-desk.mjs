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
  await page.getByRole("dialog").first().waitFor()
  await page.waitForTimeout(2000)
  await shot(page, "front-desk/checkin-sheet", { clip: { x: 480, y: 0, width: 960, height: 900 } })
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
  // the first rows are enough; a hotel with history has hundreds of guests
  const b = await page.locator("main div.rounded-xl, main div.rounded-2xl").first().boundingBox()
  await shot(page, "front-desk/guests", { clip: { x: b.x, y: b.y, width: b.width, height: Math.min(b.height, 640) } })
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
  await dlg.locator("label").filter({ hasText: "Room type" }).locator("select").first().selectOption(`${PROPERTY}-STD`)
  await p.waitForTimeout(1500)
  // pick a room nobody is in (the list can include a room whose guest
  // departs today but has not checked out yet)
  await dlg.locator("label").filter({ hasText: /^Room/ }).locator("select:not([disabled])").last().selectOption({ index: 1 })
  await p.waitForTimeout(400)
  const amt = dlg.locator("label").filter({ hasText: "Amount collected" }).locator("input")
  await amt.fill("0")
  await p.waitForTimeout(1200)
  // show the guest, ID and room part, not the payment box at the bottom
  await dlg.getByPlaceholder("Type to find or create").evaluate((el) => el.scrollIntoView({ block: "start" }))
  await p.waitForTimeout(400)
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
    await p.getByRole("dialog").first().waitFor()
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

// ------------------------------------------------------ check-out sheet
if (want("checkout-sheet")) {
  await open(page, "/", 3000)
  const row = page.locator("li").filter({ has: page.getByRole("button", { name: "Check out" }) }).first()
  await row.getByRole("button", { name: "Check out" }).click()
  await page.getByText("Stay summary").waitFor({ timeout: 15000 })
  await page.waitForTimeout(1500)
  await shot(page, "front-desk/checkout-sheet", { clip: { x: 480, y: 0, width: 960, height: 900 } })
  await page.keyboard.press("Escape")
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

if (want("in-house")) {
  await open(page, "/in-house?tab=in-house", 3000)
  await shot(page, "front-desk/in-house")
}

if (want("agent-cards")) {
  // a saved chat whose reply carries a stay card and a quote card, so the
  // shot needs no AI key; the cards load live from the stay itself
  const [stay] = await api(ctx, "frappe.client.get_list", {
    doctype: "Reservation", filters: { property: PROPERTY, status: "Checked In" },
    fields: ["name", "guest_name"], limit_page_length: 1, order_by: "check_out_date asc",
  })
  const c = await api(ctx, "kamra.assistant.create_conversation", {
    property: PROPERTY, title: "Docs: check out",
  })
  await api(ctx, "kamra.assistant.save_conversation", {
    name: c.name,
    messages: JSON.stringify([
      { role: "user", content: `check out ${stay.guest_name}` },
      {
        role: "assistant",
        content: `${stay.guest_name} is in house. Here is the stay; check out from the card once the bill is settled.\n\nRef: ${stay.name}`,
        actions: [{ tool: "find_reservations", ok: true }, { tool: "checkout_context", ok: true }],
        cards: [{ type: "stay", reservation: stay.name }],
      },
    ]),
  })
  await open(page, "/assistant", 2500)
  await page.getByText("Docs: check out", { exact: true }).first().click()
  await page.waitForTimeout(3500)
  await shot(page, "ai/agent-cards")
  await api(ctx, "kamra.assistant.delete_conversation", { name: c.name })
}

await page.close()
await ctx.close()
await done()
console.log("arrival", arrival)
