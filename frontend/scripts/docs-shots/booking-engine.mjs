// Images for docs-site/booking-engine.md.
// The console shots are taken as the docs user; the public pages as a guest
// (cookies cleared, so nothing is logged in). The GIF makes one real
// booking at Kamra Demo Palace through /book, which stays as sample data.
//
// While the /book shots are taken, the two villa properties are switched
// off the booking engine so /book shows the hotel; they are switched back on
// at the end.
import { session, api, open, shot, gif, typeSlow, done, PROPERTY } from "./lib.mjs"

const VILLAS = ["Kamra Beach Homestay", "Kamra Lakeside Villa"]
const day = (n) => new Date(Date.now() + n * 864e5).toISOString().slice(0, 10)
const CI = day(30), CO = day(32)
const BOOK = `/book/${CI}/${CO}/2/0`

const staff = await session()
const page = await staff.newPage()
const card = (p) => p.locator("div.rounded-xl.border.bg-white.shadow-sm")
const restore = []

try {
  // ── the console ──────────────────────────────────────────────────────
  await open(page, "/booking-settings/profile", 2500)
  await shot(page, "booking-engine/console")
  await open(page, "/booking-settings/payments", 2000)
  await shot(page, "booking-engine/payments", { locator: card(page).nth(1) })
  await open(page, "/booking-settings/policies", 2000)
  await shot(page, "booking-engine/policies", { locator: card(page).nth(1) })
  await open(page, "/settings/booking-engine", 2500)
  await shot(page, "booking-engine/settings")

  // ── a guest's view ───────────────────────────────────────────────────
  const guest = await session(); await guest.clearCookies()
  const g = await guest.newPage()

  // a villa listing (short-term rental) while every engine is still on
  await open(g, `/stay/entire-property/${CI}/${CO}/2/0`, 3500)
  await shot(g, "booking-engine/stay-villa")

  // with several properties live, /book starts with a chooser
  await open(g, `/book/${CI}/${CO}/2/0`, 3500)
  await shot(g, "booking-engine/properties", { clip: { x: 200, y: 40, width: 1040, height: 590 } })

  for (const name of VILLAS) {
    const was = (await api(staff, "frappe.client.get_value", {
      doctype: "Property", filters: { name }, fieldname: "booking_engine_enabled" })).booking_engine_enabled
    if (Number(was)) {
      await api(staff, "frappe.client.set_value", { doctype: "Property", name, fieldname: "booking_engine_enabled", value: 0 })
      restore.push(name)
    }
  }

  await open(g, BOOK, 3500)
  await shot(g, "booking-engine/book")
  await g.mouse.move(720, 600)
  await g.mouse.wheel(0, 560); await g.waitForTimeout(1000)
  await shot(g, "booking-engine/rooms")

  await g.getByRole("button", { name: "Book now" }).nth(1).click()
  await g.waitForTimeout(1200)
  const sh = g.locator('[role="dialog"]')
  await sh.getByLabel("Full name").fill("Arjun Mehta")
  await sh.getByLabel("Phone", { exact: true }).fill("+91 98450 66110")
  await sh.getByRole("button", { name: "Add", exact: true }).first().click()
  await g.waitForTimeout(2500)
  await shot(g, "booking-engine/booking-sheet")
  await g.keyboard.press("Escape")

  await open(g, `/stay/deluxe/${CI}/${CO}/2/0`, 3500)
  await shot(g, "booking-engine/stay-room")

  // ── GIF: a guest books on /book ──────────────────────────────────────
  // Set KAMRA_DOCS_BOOK=1 to record it (it makes a real booking); without
  // it the check-in shot uses the booking an earlier run made.
  let reservation = null
  if (process.env.KAMRA_DOCS_BOOK === "1") await gif("booking-engine/guest-booking", async (pg, gctx) => {
    await gctx.clearCookies()
    await open(pg, BOOK, 1500)
    await pg.mouse.move(720, 600)
    await pg.mouse.wheel(0, 560)
    await pg.waitForTimeout(900)
    await pg.getByRole("button", { name: "Book now" }).nth(1).click()
    await pg.waitForTimeout(1000)
    const d = pg.locator('[role="dialog"]')
    await typeSlow(d.getByLabel("Full name"), "Nisha Kapoor", 50)
    await typeSlow(d.getByLabel("Phone", { exact: true }), "+91 98450 66124", 35)
    await pg.waitForTimeout(400)
    await d.getByRole("button", { name: "Add", exact: true }).first().click()
    await pg.waitForTimeout(1200)
    await d.getByRole("button", { name: "Book now" }).click()
    await d.getByText("Booking confirmed").waitFor({ timeout: 20000 })
    await pg.waitForTimeout(2200)
    reservation = (await d.locator("p.text-lg.font-semibold").first().textContent())?.trim()
    await shot(pg, "booking-engine/confirmed", { clip: { x: 480, y: 0, width: 960, height: 200 } })
  })
  if (!reservation) {
    const rows = await api(staff, "frappe.client.get_list", { doctype: "Reservation",
      filters: { guest_name: ["in", ["Arjun Mehta", "Nisha Kapoor"]], source: "Website" }, fields: ["name"],
      order_by: "creation desc", limit_page_length: 1 })
    reservation = rows[0]?.name ?? null
  }
  console.log("booking", reservation)

  // ── the guest's self check-in link for that booking ──────────────────
  if (reservation) {
    let token = (await api(staff, "frappe.client.get_value", {
      doctype: "Reservation", filters: { name: reservation }, fieldname: "precheckin_token" })).precheckin_token
    if (!token) {
      await api(staff, "kamra.api.send_precheckin_link", { reservation }).catch((e) => console.log(e.message))
      token = (await api(staff, "frappe.client.get_value", {
        doctype: "Reservation", filters: { name: reservation }, fieldname: "precheckin_token" })).precheckin_token
    }
    if (token) {
      await open(g, `/checkin/${token}`, 3000)
      await shot(g, "booking-engine/checkin", { fullPage: true })
    }
  }
} finally {
  for (const name of restore) {
    await api(staff, "frappe.client.set_value", { doctype: "Property", name, fieldname: "booking_engine_enabled", value: 1 })
      .catch((e) => console.log("restore", name, e.message))
  }
  await done()
}
