// Docs images for docs-site/operations.md (guest requests, SLA settings and
// the SLA report) plus the few screens added to whatsapp.md and
// channel-manager.md. Forms on the Channels and Channel Manager screens are
// filled with placeholders and never saved.
import { api, done, gif, open, PROPERTY, session, shot, typeSlow } from "./lib.mjs"

const ctx = await session()
const page = await ctx.newPage()
const panel = { x: 480, y: 0, width: 960 } // the right-hand sheet
const card = async (title, height) => {
  const box = await page.getByText(title, { exact: true }).first()
    .locator("xpath=ancestor::div[contains(@class,'rounded')][1]").boundingBox()
  return { x: box.x - 1, y: box.y - 1, width: box.width + 2, height: height ?? box.height + 2 }
}

// --- data -------------------------------------------------------------------
// Resolved sample tickets get realistic resolve times (the seed resolves them
// in the same second it creates them), so the SLA report has numbers to show.
const tickets = await api(ctx, "frappe.client.get_list", {
  doctype: "Service Ticket", filters: { property: PROPERTY },
  fields: ["name", "subject", "status", "creation", "due_by", "resolved_on"], limit_page_length: 200,
})
const at = (iso, min) => {
  const d = new Date(new Date(iso.replace(" ", "T")).getTime() + min * 60000)
  const p = (x) => String(x).padStart(2, "0")
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}
const resolveAfter = { "Late checkout request": 18, "Crib for the baby": 26, "Noise complaint": 22, "Iron & board": 12 }
for (const t of tickets) {
  const key = Object.keys(resolveAfter).find((k) => t.subject.startsWith(k))
  if (!key || !["Resolved", "Closed"].includes(t.status)) continue
  const resolved = at(t.creation, resolveAfter[key])
  await api(ctx, "frappe.client.set_value", {
    doctype: "Service Ticket", name: t.name,
    fieldname: { resolved_on: resolved, breached: resolved > t.due_by ? 1 : 0 },
  })
}
// the ticket the GIF creates, from earlier runs
const SUBJECT = "Extra pillows for 201"
for (const t of tickets.filter((x) => x.subject === SUBJECT)) {
  await api(ctx, "frappe.client.delete", { doctype: "Service Ticket", name: t.name })
    .catch(() => api(ctx, "kamra.api.advance_ticket", { ticket: t.name, status: "Cancelled" }).catch(() => {}))
}

// --- guest requests ------------------------------------------------------------
await open(page, "/tickets", 2500)
await shot(page, "operations/guest-requests", { clip: await card("Service Tickets") })

await page.getByRole("button", { name: "New ticket" }).click()
await page.waitForTimeout(500)
const dlg = page.locator("[role=dialog]")
await dlg.getByPlaceholder("What does the guest need?").fill("Extra pillows for 201")
await dlg.locator("select").nth(0).selectOption("Housekeeping")
await dlg.locator("select").nth(2).selectOption(`${PROPERTY}-201`)
await dlg.getByPlaceholder("Anything the staff should know (optional)").fill("Two firm pillows, guest is in the room until 11")
await page.waitForTimeout(300)
await shot(page, "operations/new-ticket", { clip: { ...panel, height: 470 } })
await page.keyboard.press("Escape")

await open(page, "/tickets", 2000)
await page.getByLabel("Show closed").check()
await page.waitForTimeout(1500)
await shot(page, "operations/show-closed", { clip: await card("Service Tickets") })

// --- settings and the report -------------------------------------------------
await open(page, "/settings/operations", 2500)
await shot(page, "operations/settings", { clip: { x: 530, y: 80, width: 880, height: 445 } })
await open(page, "/ops-sla", 3000)
await shot(page, "operations/sla-report")

// --- stay instructions on a reservation (removed again after the shot) ----------
if (!process.env.SKIP_INSTRUCTIONS) {
  const RES = process.env.KAMRA_DOCS_INSTR_RES || "RES-2026-00035"
  const added = []
  try {
    for (const [department, instruction] of [
      ["Housekeeping", "Fruit basket and a welcome card before arrival"],
      ["Transport", "Airport pickup, flight 6E 512 lands 14:20"],
    ]) {
      const rows = await api(ctx, "kamra.api.add_stay_instruction", { reservation: RES, department, instruction })
      added.push(rows.at(-1).name)
    }
    await api(ctx, "kamra.api.set_stay_instruction_status", { reservation: RES, row: added[1], status: "Done" })
    await open(page, "/reservations", 2500)
    await page.getByPlaceholder("Search…").fill(RES)
    await page.waitForTimeout(1500)
    await page.locator("tr").filter({ hasText: RES }).first().click()
    const instr = page.getByPlaceholder("e.g. Fruit basket before arrival")
      .locator("xpath=ancestor::div[contains(@class,'rounded-xl')][1]")
    await instr.waitFor()
    await instr.scrollIntoViewIfNeeded()
    await page.waitForTimeout(1200)
    await instr.locator("select").selectOption("F&B")
    await instr.getByPlaceholder("e.g. Fruit basket before arrival").fill("Gluten-free breakfast every morning")
    await page.waitForTimeout(300)
    await shot(page, "operations/stay-instructions", { locator: instr })
    await page.keyboard.press("Escape")
  } finally {
    for (const name of added)
      await api(ctx, "frappe.client.delete", { doctype: "Stay Instruction", name }).catch(() => {})
  }
}

// --- WhatsApp and Channels (whatsapp.md) --------------------------------------
await open(page, "/whatsapp", 2500)
await shot(page, "whatsapp/inbox", { clip: { x: 250, y: 70, width: 1170, height: 530 } })
await open(page, "/channels", 2500)
await page.getByRole("button", { name: "New", exact: true }).click()
await page.waitForTimeout(600)
const fields = dlg.locator("select, input:not([type=checkbox])")
await fields.nth(0).selectOption("WhatsApp")
await fields.nth(1).selectOption("Meta Business")
const vals = ["+91 98450 00000", "104xxxxxxxxxxxx", "(your permanent System User token)",
  "kamra-verify-7f3a", "(App settings → Basic → App secret)", "en",
  "kamra_booking_confirmation", "kamra_precheckin_link", "kamra_payment_request"]
for (const [i, v] of vals.entries()) await fields.nth(i + 2).fill(v)
await dlg.locator("input[type=checkbox]").first().check()
await page.waitForTimeout(300)
await shot(page, "whatsapp/channel-form", { clip: { ...panel, height: 900 } })
await page.keyboard.press("Escape")

// --- Channel Manager (channel-manager.md) ---------------------------------------
await open(page, "/channel-manager", 2500)
await page.getByRole("button", { name: "New", exact: true }).click()
await page.waitForTimeout(600)
await fields.nth(0).selectOption("Channex")
for (const [i, v] of ["(your Channex user API key)", "(Channex property id)", "", "my-webhook-secret-42"].entries())
  if (v) await fields.nth(i + 1).fill(v)
await fields.nth(5).fill("90")
await dlg.locator("input[type=checkbox]").first().check()
await page.waitForTimeout(300)
await shot(page, "channel-manager/new-connection", { clip: { ...panel, height: 525 } })
await page.keyboard.press("Escape")

await open(page, "/ota-mappings", 2500)
await page.getByRole("button", { name: "New", exact: true }).click()
await page.waitForTimeout(600)
const types = await fields.nth(1).locator("option").evaluateAll((os) => os.map((o) => o.value))
await fields.nth(1).selectOption(types.find((v) => v.startsWith(PROPERTY)))
await fields.nth(2).fill("(Channex room_type_id)")
await fields.nth(3).fill("(Channex rate_plan_id)")
await page.waitForTimeout(300)
await shot(page, "channel-manager/room-mapping", { clip: { ...panel, height: 300 } })

// --- GIF: a desk agent logs a request and starts it ---------------------------------
await gif("operations/new-ticket", async (g) => {
  await open(g, "/tickets", 2000)
  await g.waitForTimeout(500)
  await g.getByRole("button", { name: "New ticket" }).click()
  await g.waitForTimeout(600)
  const d = g.locator("[role=dialog]")
  await typeSlow(d.getByPlaceholder("What does the guest need?"), SUBJECT, 45)
  await d.locator("select").nth(0).selectOption("Housekeeping")
  await g.waitForTimeout(400)
  await d.locator("select").nth(2).selectOption(`${PROPERTY}-201`)
  await g.waitForTimeout(600)
  await d.getByRole("button", { name: "Create ticket" }).click()
  await g.waitForTimeout(1500)
  const row = g.locator("li", { hasText: SUBJECT })
  await row.getByRole("button", { name: "Start" }).click()
  await g.waitForTimeout(1800)
}, { width: 960, crop: { x: 240, y: 0, width: 1200, height: 900 } })

await done()
