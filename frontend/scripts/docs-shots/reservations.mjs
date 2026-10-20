// Screenshots and GIFs for docs-site/reservations.md.
//
//   KAMRA_DOCS_BASE=http://localhost:5176 KAMRA_DOCS_USER=... KAMRA_DOCS_PASSWORD=... \
//   node scripts/docs-shots/reservations.mjs [only-these,shot-names]
//
// Needs the sample hotel. Makes a few bookings of its own (future dates,
// so they stay off today's arrivals) and cancels one to show the fee.

import { session, api, open, shot, gif, typeSlow, done, PROPERTY } from "./lib.mjs"

const only = (process.argv[2] || "").split(",").filter(Boolean)
const want = (n) => !only.length || only.includes(n)

const today = new Date().toISOString().slice(0, 10)
const addDays = (d, n) => {
  const x = new Date(d + "T00:00:00Z")
  x.setUTCDate(x.getUTCDate() + n)
  return x.toISOString().slice(0, 10)
}
const ddmmyyyy = (d) => d.split("-").reverse().join("")

const ctx = await session()
const page = await ctx.newPage()

async function find(guest_name, status = "Confirmed") {
  const [r] = await api(ctx, "frappe.client.get_list", {
    doctype: "Reservation",
    filters: { property: PROPERTY, guest_name, status },
    fields: ["name", "group_booking"], limit_page_length: 1,
  })
  return r
}

/** Fill the New booking dialog: guest, room type, check-in, nights. */
async function fillBooking(p, { guest, phone, type, checkIn, nights }, slow) {
  await p.getByRole("button", { name: "New booking" }).click()
  const dlg = p.getByRole("dialog", { name: "New booking" })
  await dlg.waitFor()
  await p.waitForTimeout(800)
  const name = dlg.getByPlaceholder("Type to find or create")
  slow ? await typeSlow(name, guest, 50) : await name.fill(guest)
  const tel = dlg.locator("input[type=tel]").first()
  slow ? await typeSlow(tel, phone, 40) : await tel.fill(phone)
  await dlg.locator("select").first().selectOption(`${PROPERTY}-${type}`)
  const ci = dlg.locator("input[type=date]").first()
  await ci.click()
  await ci.pressSequentially(ddmmyyyy(checkIn))
  const n = dlg.locator("label").filter({ hasText: "Nights" }).locator("input")
  await n.fill(String(nights))
  await p.waitForTimeout(1800)
  return dlg
}

const LEELA = { guest: "Leela Menon", phone: "9810011041", type: "DLX", checkIn: addDays(today, 6), nights: 3 }

// ------------------------------------------------- the booking dialog
if (want("booking-dialog")) {
  await open(page, "/", 2500)
  // a name with no guest profile, so no returning-guest list covers the form
  // (Leela Menon has a profile once the booking GIF has run)
  const dlg = await fillBooking(page, { ...LEELA, guest: "Tara Fernandes", phone: "9810011051" }, false)
  await shot(page, "reservations/booking-dialog", { clip: { x: 480, y: 0, width: 960, height: 900 } })
  // company, add-ons and arrival details
  await dlg.getByRole("button", { name: "Company, add-ons & arrival details" }).click()
  await dlg.getByRole("button", { name: /Airport Transfer/ }).click()
  await page.waitForTimeout(1500)
  const more = dlg.getByRole("button", { name: "Company, add-ons & arrival details" }).locator("xpath=..")
  await more.scrollIntoViewIfNeeded()
  await shot(page, "reservations/booking-more", { clip: { x: 480, y: 0, width: 960, height: 900 } })
  await page.keyboard.press("Escape")
}

if (want("multi-room")) {
  await open(page, "/", 2500)
  const dlg = await fillBooking(page, { guest: "Kapoor family", phone: "9810011051", type: "STD", checkIn: addDays(today, 9), nights: 2 }, false)
  await dlg.getByRole("button", { name: "Add another room" }).click()
  await page.waitForTimeout(400)
  await dlg.getByRole("button", { name: "Add another room" }).click()
  await page.waitForTimeout(2500)
  await shot(page, "reservations/multi-room", { clip: { x: 480, y: 0, width: 960, height: 900 } })
  await page.keyboard.press("Escape")
}

// ---------------------------------------- make a booking, end to end
if (want("booking-gif") && !(await find(LEELA.guest))) {
  await gif("reservations/booking", async (p) => {
    await open(p, "/", 2000)
    const dlg = await fillBooking(p, LEELA, true)
    await p.waitForTimeout(800)
    await dlg.getByRole("button", { name: "Confirm booking" }).click()
    await p.getByText(/^Booked · /).waitFor({ timeout: 15000 })
    await p.waitForTimeout(3000)
  }, { crop: { x: 480, y: 0, width: 960, height: 900 } })
}

// -------------------------------------------------- tape chart, calendar
if (want("tape-chart")) {
  await open(page, "/tape", 3000)
  await shot(page, "reservations/tape-chart")
}
if (want("tape-bar")) {
  await open(page, "/tape", 3000)
  await page.locator("button").filter({ hasText: "Rohan Mehta" }).first().click()
  await page.waitForTimeout(2000)
  const sheet = page.locator("[role=dialog] > div").last()
  const b = await sheet.boundingBox()
  await shot(page, "reservations/tape-bar", { clip: { x: b.x, y: 0, width: b.width, height: 470 } })
  await page.keyboard.press("Escape")
}
if (want("calendar")) {
  await open(page, "/calendar", 3000)
  await shot(page, "reservations/calendar", { locator: page.locator("main div.rounded-xl, main div.rounded-2xl").first() })
}

// --------------------------------------------- the reservation drawer
async function openDrawer(ref) {
  await open(page, "/reservations", 2500)
  await page.getByPlaceholder("Search…").fill(ref)
  await page.waitForTimeout(1500)
  await page.locator("tr").filter({ hasText: ref }).first().click()
  await page.getByText("Special requests").first().waitFor()
  await page.waitForTimeout(1800)
}
if (want("reservation")) {
  const r = await find(LEELA.guest)
  await openDrawer(r.name)
  await shot(page, "reservations/reservation")
  await page.getByRole("button", { name: "Cancel this stay…" }).scrollIntoViewIfNeeded()
  await page.waitForTimeout(600)
  await shot(page, "reservations/reservation-lower", { clip: { x: 480, y: 0, width: 960, height: 900 } })
}

// ---------------------------------------------------------- cancelling
if (want("cancel")) {
  // an arrival for today - inside the free-cancellation window
  let r = await find("Rahul Verma")
  if (!r) {
    await api(ctx, "kamra.api.create_booking", {
      property: PROPERTY, room_type: `${PROPERTY}-STD`, check_in_date: today,
      check_out_date: addDays(today, 1), guest_name: "Rahul Verma",
      phone: "+919810011071", adults: 1, assign_room: 0, source: "Phone",
    })
    r = await find("Rahul Verma")
  }
  await openDrawer(r.name)
  await page.getByRole("button", { name: "Cancel this stay…" }).click()
  await page.getByText(/before arrival/).waitFor()
  await page.waitForTimeout(800)
  const panel = page.getByRole("button", { name: "Confirm cancellation" }).locator("xpath=../..")
  await panel.scrollIntoViewIfNeeded()
  await shot(page, "reservations/cancel-preview", { locator: panel })
  await page.getByRole("button", { name: "Confirm cancellation" }).click()
  await page.getByText(/^Cancelled - CXL/).first().waitFor()
  await page.waitForTimeout(1000)
  await open(page, `/cancelled/${r.name}`, 2500)
  await shot(page, "reservations/cancellation-letter")
}

// ------------------------------------------------------ central search
if (want("crs")) {
  await open(page, "/crs", 2000)
  await page.getByRole("button", { name: "Search", exact: true }).click()
  await page.waitForTimeout(3000)
  await shot(page, "reservations/crs")
}

// ------------------------------------------------------ groups & blocks
if (want("group")) {
  let g = (await api(ctx, "frappe.client.get_list", {
    doctype: "Group Booking", filters: { property: PROPERTY, group_name: "Infosys offsite" },
    fields: ["name"], limit_page_length: 1,
  }))[0]
  if (!g) {
    const out = await api(ctx, "kamra.api.create_group_booking", {
      property: PROPERTY, group_name: "Infosys offsite",
      check_in_date: addDays(today, 15), check_out_date: addDays(today, 17),
      rooms: [{ room_type: `${PROPERTY}-DLX`, count: 2 }],
      guest_name: "Sanjay Kulkarni", phone: "+919810011081",
    })
    g = { name: out.group_booking }
  }
  await open(page, "/groups", 2500)
  await page.locator("tr").filter({ hasText: "Infosys offsite" }).first().click()
  await page.getByText("Room block").first().waitFor()
  await page.waitForTimeout(2000)
  const dlg = page.locator("[role=dialog] > div").last()
  if (!(await dlg.getByText(/picked/).count())) {
    await dlg.getByRole("button", { name: "Add room type" }).click()
    await dlg.locator("select").last().selectOption(`${PROPERTY}-DLX`)
    await dlg.getByPlaceholder("Rooms").last().fill("4")
    await dlg.locator("input[type=number]").last().fill("3800")
    await dlg.getByRole("button", { name: "Save block" }).click()
    await page.waitForTimeout(2500)
  }
  const b = await dlg.boundingBox()
  await shot(page, "reservations/group", { clip: { x: b.x, y: 0, width: b.width, height: 480 } })
  await page.keyboard.press("Escape")
}

await page.close()
await ctx.close()
await done()
